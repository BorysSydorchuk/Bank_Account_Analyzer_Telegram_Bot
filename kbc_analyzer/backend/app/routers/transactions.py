"""POST /api/transactions/sync and GET /api/transactions."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud
from ..db import get_db
from ..eb_service import EnableBankingService
from ..schemas import SyncRequest, SyncResponse, TransactionsListResponse

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def get_eb_service() -> EnableBankingService:
    return EnableBankingService()


@router.post("/sync", response_model=SyncResponse)
def sync_transactions(
    body: SyncRequest,
    db: Session = Depends(get_db),
    eb: EnableBankingService = Depends(get_eb_service),
) -> SyncResponse:
    account_uids = eb.get_account_uids()

    fetched = stored = duplicates_skipped = 0
    for account_uid in account_uids:
        txs = eb.fetch_transactions(account_uid, body.date_from, body.date_to)
        fetched += len(txs)
        account_stored, account_duplicates = crud.upsert_transactions(db, account_uid, txs)
        stored += account_stored
        duplicates_skipped += account_duplicates

    return SyncResponse(fetched=fetched, stored=stored, duplicates_skipped=duplicates_skipped)


@router.get("", response_model=TransactionsListResponse)
def get_transactions(
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
) -> TransactionsListResponse:
    rows = crud.list_transactions(db, date_from, date_to)
    return TransactionsListResponse(transactions=rows, total=len(rows))
