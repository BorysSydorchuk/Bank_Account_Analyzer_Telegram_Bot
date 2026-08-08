"""POST /api/transactions/sync and GET /api/transactions."""
import math
from datetime import date
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import crud, job_store
from ..db import get_db
from ..eb_service import EnableBankingService
from ..schemas import SyncRequest, SyncResponse, TransactionsListResponse
from ..tasks.analysis import categorize_and_analyze

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_eb_service() -> EnableBankingService:
    return EnableBankingService()


@router.post("/sync", response_model=SyncResponse)
async def sync_transactions(
    body: SyncRequest,
    db: Session = Depends(get_db),
    eb: EnableBankingService = Depends(get_eb_service),
) -> SyncResponse:
    # The Enable Banking fetch is a blocking `requests` call — this endpoint is
    # `async def` (required so it can `await` run_in_threadpool below), so the
    # fetch itself has to move to a thread or it would stall the whole event
    # loop, including unrelated requests, for as long as it takes.
    def _fetch_and_store() -> tuple[int, int, int]:
        account_uids = eb.get_account_uids()
        fetched = stored = duplicates_skipped = 0
        for account_uid in account_uids:
            txs = eb.fetch_transactions(account_uid, body.date_from, body.date_to)
            fetched += len(txs)
            account_stored, account_duplicates = crud.upsert_transactions(db, account_uid, txs)
            stored += account_stored
            duplicates_skipped += account_duplicates
        return fetched, stored, duplicates_skipped

    fetched, stored, duplicates_skipped = await run_in_threadpool(_fetch_and_store)

    # S3-04: categorization + insight generation moved to the celery_worker
    # (app/tasks/analysis.py) so this request can return immediately instead
    # of blocking on however long the LLM calls take. The job's progress
    # lives in Redis (job_store), polled via GET /api/jobs/{job_id}.
    job_id = str(uuid4())
    job_store.set_job(
        job_id,
        {
            "job_id": job_id,
            "status": "processing",
            "stage": "categorizing",
            "progress": 0,
            "message": "Categorizing transactions...",
        },
    )
    categorize_and_analyze.delay(job_id, body.date_from.isoformat(), body.date_to.isoformat())

    return SyncResponse(
        fetched=fetched,
        stored=stored,
        duplicates_skipped=duplicates_skipped,
        job_id=job_id,
        status="processing",
    )


@router.get("", response_model=TransactionsListResponse)
def get_transactions(
    date_from: date,
    date_to: date,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    category: list[str] | None = Query(None),
    amount_type: Literal["all", "spent", "received"] = "all",
    db: Session = Depends(get_db),
) -> TransactionsListResponse:
    rows, total = crud.list_transactions_paginated(db, date_from, date_to, page, limit, category, amount_type)
    return TransactionsListResponse(
        transactions=rows,
        total=total,
        page=page,
        pages=max(1, math.ceil(total / limit)),
    )
