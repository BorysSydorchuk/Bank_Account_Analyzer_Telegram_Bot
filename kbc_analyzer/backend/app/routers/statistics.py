"""GET /api/statistics."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud
from ..auth.dependency import get_current_user
from ..date_range import require_valid_date_range
from ..db import get_db
from ..models import User
from ..schemas import StatisticsResponse
from ..statistics import compute_statistics

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("", response_model=StatisticsResponse)
def get_statistics(
    date_range: tuple[date, date] = Depends(require_valid_date_range),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatisticsResponse:
    date_from, date_to = date_range
    transactions = crud.list_transactions(db, current_user.id, date_from, date_to)
    return compute_statistics(transactions, date_from, date_to)
