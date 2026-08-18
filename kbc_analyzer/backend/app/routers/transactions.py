"""POST /api/transactions/sync, GET /api/transactions, and PATCH /api/transactions/{id}."""
import math
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import crud, job_store, sync_lock
from ..db import get_db
from ..schemas import PatchTransactionRequest, SyncRequest, SyncResponse, TransactionOut, TransactionsListResponse
from ..sync_lock import SyncAlreadyRunningError
from ..tasks.analysis import run_sync_job

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("/sync", response_model=SyncResponse)
def sync_transactions(body: SyncRequest) -> SyncResponse:
    # S4-02: the Enable Banking fetch used to happen here, synchronously,
    # before this endpoint could return — 4 to 18 seconds of the request just
    # waiting on a third-party API. Fetch, store, categorize, and generate
    # insights now all happen inside the one Celery job; this endpoint's only
    # job is to create that job and hand back its id, which is why it no
    # longer needs `db` or an EnableBankingService of its own at all.
    job_id = str(uuid4())

    # S5-05: the lock's value IS this job_id, so a successful acquire means
    # this job is now the one and only in-flight sync — no separate "create
    # the job" step could race a concurrent request in between, since
    # acquire() is a single atomic Redis command.
    if not sync_lock.acquire(job_id):
        in_flight_job_id = sync_lock.get_holder()
        if in_flight_job_id is None:
            # Rare race: the lock was released (TTL expiry, or the holder
            # finishing) between our failed acquire() and this read — it's
            # free again, so retry once rather than reporting a conflict
            # against a job that no longer exists.
            if not sync_lock.acquire(job_id):
                raise SyncAlreadyRunningError(sync_lock.get_holder() or job_id)
        else:
            raise SyncAlreadyRunningError(in_flight_job_id)

    job_store.set_job(
        job_id,
        {
            "job_id": job_id,
            "status": "processing",
            "stage": "fetching",
            "progress": 0,
            "message": "Fetching transactions from KBC...",
        },
    )
    run_sync_job.delay(job_id, body.date_from.isoformat(), body.date_to.isoformat())

    return SyncResponse(job_id=job_id, status="processing")


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


@router.get("/search", response_model=TransactionsListResponse)
def search_transactions(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> TransactionsListResponse:
    """Global search (S3-07 Item 4) — across every synced transaction, not
    scoped to the Transactions page's current date range or page. `total`/
    `pages` are both trivially 1 here; this endpoint returns matches
    directly, it doesn't paginate them."""
    rows = crud.search_transactions(db, q, limit)
    return TransactionsListResponse(transactions=rows, total=len(rows), page=1, pages=1)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def patch_transaction(
    transaction_id: UUID,
    body: PatchTransactionRequest,
    db: Session = Depends(get_db),
) -> TransactionOut:
    """Manual correction (S3-05). Only fields actually present in the request
    body are touched — model_dump(exclude_unset=True) is what makes
    `{"subcategory": null}` mean "clear it" while an omitted field means
    "leave it alone," which a plain .model_dump() can't distinguish.
    """
    updates = body.model_dump(exclude_unset=True)

    if "category" in updates and updates["category"] is not None:
        known_categories = {c.name for c in crud.list_categories(db)}
        if updates["category"] not in known_categories:
            raise HTTPException(
                status_code=400,
                detail=f"'{updates['category']}' isn't a known category. Use an existing category name or null.",
            )

    transaction = crud.update_transaction(db, transaction_id, updates)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return transaction
