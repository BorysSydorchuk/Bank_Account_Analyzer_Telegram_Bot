"""POST /api/transactions/sync, GET /api/transactions, GET /api/transactions/search,
and PATCH /api/transactions/{id}."""
import logging
import math
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import crud, job_store, sync_lock
from ..auth.dependency import get_current_user, require_verified_email
from ..date_range import require_valid_date_range, validate_date_range_body
from ..db import get_db
from ..models import User
from ..rate_limit import SYNC_RATE_LIMIT, limiter
from ..schemas import PatchTransactionRequest, SyncRequest, SyncResponse, TransactionOut, TransactionsListResponse
from ..sync_lock import SyncAlreadyRunningError
from ..tasks.analysis import run_sync_job

router = APIRouter(prefix="/api/transactions", tags=["transactions"])
logger = logging.getLogger(__name__)

# S10-03: the enqueue error message shown to both the job's own `error`
# field and the request's own HTTPException detail — the client sees this
# either way, whether it reads it from the failed 503 response or (if it
# raced ahead and already started polling GET /api/jobs/{job_id}) from the
# job record itself.
_ENQUEUE_FAILED_MESSAGE = "Could not start the sync job. Please try again shortly."


@router.post("/sync", response_model=SyncResponse)
@limiter.limit(SYNC_RATE_LIMIT)
def sync_transactions(
    request: Request, body: SyncRequest, current_user: User = Depends(require_verified_email)
) -> SyncResponse:
    # S4-02: the Enable Banking fetch used to happen here, synchronously,
    # before this endpoint could return — 4 to 18 seconds of the request just
    # waiting on a third-party API. Fetch, store, categorize, and generate
    # insights now all happen inside the one Celery job; this endpoint's only
    # job is to create that job and hand back its id, which is why it no
    # longer needs `db` or an EnableBankingService of its own at all.
    # S5-07: validated before the lock is touched — a rejected request
    # should never acquire (and then have to release) sync_lock.
    validate_date_range_body(body.date_from, body.date_to)

    job_id = str(uuid4())

    # S5-05/S6-06: the lock's value IS this job_id, so a successful acquire
    # means this job is now the one and only in-flight sync — no separate
    # "create the job" step could race a concurrent request in between,
    # since acquire() is a single atomic Redis command. Scoped to
    # current_user.id (S6-06) — sync_lock.py's key derivation was already
    # written for this at S5-05, so this is the one-line change that
    # ticket anticipated.
    if not sync_lock.acquire(job_id, current_user.id):
        in_flight_job_id = sync_lock.get_holder(current_user.id)
        if in_flight_job_id is None:
            # Rare race: the lock was released (TTL expiry, or the holder
            # finishing) between our failed acquire() and this read — it's
            # free again, so retry once rather than reporting a conflict
            # against a job that no longer exists.
            if not sync_lock.acquire(job_id, current_user.id):
                raise SyncAlreadyRunningError(sync_lock.get_holder(current_user.id) or job_id)
        else:
            raise SyncAlreadyRunningError(in_flight_job_id)

    job_store.set_job(
        job_id,
        {
            "job_id": job_id,
            "user_id": str(current_user.id),
            "status": "processing",
            "stage": "fetching",
            "progress": 0,
            "message": "Fetching transactions from KBC...",
        },
    )
    # S10-03: a broker outage (or anything else .delay() can raise) used to
    # leave this job stuck at "processing" forever and the lock held for its
    # full 11-minute TTL — nothing would ever pick the job back up to mark it
    # failed, since the task was never actually enqueued for a worker to run.
    # Releasing the lock and marking the job failed here, synchronously, is
    # the only place that can happen: this request is the only code that
    # knows the enqueue itself failed.
    try:
        run_sync_job.delay(job_id, body.date_from.isoformat(), body.date_to.isoformat(), str(current_user.id))
    except Exception:
        logger.exception("Failed to enqueue sync job %s for user %s", job_id, current_user.id)
        sync_lock.release(job_id, current_user.id)
        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "user_id": str(current_user.id),
                "status": "failed",
                "stage": "fetching",
                "error": _ENQUEUE_FAILED_MESSAGE,
            },
        )
        raise HTTPException(status_code=503, detail=_ENQUEUE_FAILED_MESSAGE)

    return SyncResponse(job_id=job_id, status="processing")


@router.get("", response_model=TransactionsListResponse)
def get_transactions(
    date_range: tuple[date, date] = Depends(require_valid_date_range),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    category: list[str] | None = Query(None),
    amount_type: Literal["all", "spent", "received"] = "all",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionsListResponse:
    date_from, date_to = date_range
    rows, total = crud.list_transactions_paginated(
        db, current_user.id, date_from, date_to, page, limit, category, amount_type
    )
    return TransactionsListResponse(
        transactions=rows,
        total=total,
        page=page,
        pages=max(1, math.ceil(total / limit)),
    )


@router.get("/search", response_model=TransactionsListResponse)
def search_transactions(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionsListResponse:
    """Global search (S3-07 Item 4) — across every transaction this user has
    ever synced, not scoped to the Transactions page's current date range
    or page. `total`/`pages` are both trivially 1 here; this endpoint
    returns matches directly, it doesn't paginate them."""
    rows = crud.search_transactions(db, current_user.id, q, limit)
    return TransactionsListResponse(transactions=rows, total=len(rows), page=1, pages=1)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def patch_transaction(
    transaction_id: UUID,
    body: PatchTransactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionOut:
    """Manual correction (S3-05). Only fields actually present in the request
    body are touched — model_dump(exclude_unset=True) is what makes
    `{"subcategory": null}` mean "clear it" while an omitted field means
    "leave it alone," which a plain .model_dump() can't distinguish.

    S6-06 — the IDOR-shaped gap S5-01 named explicitly: crud.update_transaction
    now scopes its lookup by (transaction_id, user_id) together, so a
    transaction_id belonging to another user reads identically to one that
    doesn't exist — 404 below either way, never a 403 that would confirm
    someone else's transaction exists.
    """
    updates = body.model_dump(exclude_unset=True)

    if "category" in updates and updates["category"] is not None:
        known_categories = {c.name for c in crud.list_categories(db, current_user.id)}
        if updates["category"] not in known_categories:
            raise HTTPException(
                status_code=400,
                detail=f"'{updates['category']}' isn't a known category. Use an existing category name or null.",
            )

    transaction = crud.update_transaction(db, current_user.id, transaction_id, updates)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return transaction
