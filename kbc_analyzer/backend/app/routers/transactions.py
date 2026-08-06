"""POST /api/transactions/sync and GET /api/transactions."""
import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import analysis_service, crud
from ..db import get_db
from ..eb_service import EnableBankingService
from ..schemas import SyncRequest, SyncResponse, TransactionsListResponse

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
    # `async def` (required so it can `await` the categorization step below),
    # so the fetch itself has to move to a thread or it would stall the whole
    # event loop, including unrelated requests, for as long as it takes.
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

    categorization = await analysis_service.categorize_transactions(db, body.date_from, body.date_to)
    insights = await analysis_service.generate_insights(db, body.date_from, body.date_to)

    return SyncResponse(
        fetched=fetched,
        stored=stored,
        duplicates_skipped=duplicates_skipped,
        categorized=categorization["categorized"],
        categorization_provider=categorization["provider"],
        error_message=categorization["error_message"],
        insights=insights["insights"],
        insights_generated_at=insights["generated_at"],
        insights_error_message=insights["error_message"],
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
