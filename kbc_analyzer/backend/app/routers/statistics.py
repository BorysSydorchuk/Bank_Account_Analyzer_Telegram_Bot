"""GET /api/statistics."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud
from ..date_range import require_valid_date_range
from ..db import get_db
from ..schemas import StatisticsResponse
from ..statistics import compute_statistics

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("", response_model=StatisticsResponse)
def get_statistics(
    date_range: tuple[date, date] = Depends(require_valid_date_range),
    db: Session = Depends(get_db),
) -> StatisticsResponse:
    date_from, date_to = date_range
    transactions = crud.list_transactions(db, date_from, date_to)
    return compute_statistics(transactions, date_from, date_to)
