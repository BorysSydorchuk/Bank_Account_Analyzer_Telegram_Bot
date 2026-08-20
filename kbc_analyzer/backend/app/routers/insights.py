"""GET /api/insights — cached insights from the last sync for a date range
(S3-07 Item 3). Lets the frontend show real insights on page load instead of
an empty state until a new sync runs.

GET /api/insights/compare (S4-08) — spending deltas between two arbitrary
date ranges; see comparison_service for the actual logic.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import comparison_service, crud
from ..auth.dependency import get_current_user
from ..date_range import require_valid_date_range
from ..db import get_db
from ..models import User
from ..schemas import CachedInsightsResponse, ComparisonResponse

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("", response_model=CachedInsightsResponse)
def get_insights(
    date_range: tuple[date, date] = Depends(require_valid_date_range),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CachedInsightsResponse:
    date_from, date_to = date_range
    rows = crud.list_insights(db, current_user.id, date_from, date_to)
    if not rows:
        return CachedInsightsResponse(insights=[])
    return CachedInsightsResponse(
        insights=[
            {"type": row.type, "title": row.title, "body": row.body, "severity": row.severity} for row in rows
        ],
        provider=rows[0].provider,
        generated_at=rows[0].generated_at,
    )


@router.get("/compare", response_model=ComparisonResponse)
def compare_insights(
    period_a_from: date,
    period_a_to: date,
    period_b_from: date,
    period_b_to: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonResponse:
    """Statistics for both periods are always computed live from
    transactions; insights are read from storage exactly as stored for each
    exact range (S4-04 Option B) — never generated here on the fly.
    """
    try:
        result = comparison_service.compare_periods(
            db, current_user.id, period_a_from, period_a_to, period_b_from, period_b_to
        )
    except comparison_service.InvalidDateRangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ComparisonResponse(**result)
