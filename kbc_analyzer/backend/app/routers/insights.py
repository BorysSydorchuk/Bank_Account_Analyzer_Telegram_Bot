"""GET /api/insights — cached insights from the last sync for a date range
(S3-07 Item 3). Lets the frontend show real insights on page load instead of
an empty state until a new sync runs.
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud
from ..db import get_db
from ..schemas import CachedInsightsResponse

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("", response_model=CachedInsightsResponse)
def get_insights(date_from: date, date_to: date, db: Session = Depends(get_db)) -> CachedInsightsResponse:
    rows = crud.list_insights(db, date_from, date_to)
    if not rows:
        return CachedInsightsResponse(insights=[])
    return CachedInsightsResponse(
        insights=[
            {"type": row.type, "title": row.title, "body": row.body, "severity": row.severity} for row in rows
        ],
        provider=rows[0].provider,
        generated_at=rows[0].generated_at,
    )
