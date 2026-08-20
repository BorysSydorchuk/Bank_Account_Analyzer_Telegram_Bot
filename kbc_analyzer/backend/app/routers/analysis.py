"""POST /api/analysis/categorize and POST /api/analysis/insights."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import analysis_service
from ..auth.dependency import get_current_user
from ..db import get_db
from ..models import User
from ..rate_limit import ANALYSIS_RATE_LIMIT, limiter
from ..schemas import CategorizeRequest, CategorizeResponse, InsightsRequest, InsightsResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/categorize", response_model=CategorizeResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def categorize(
    request: Request,
    body: CategorizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategorizeResponse:
    result = await analysis_service.categorize_transactions(db, current_user.id, body.date_from, body.date_to)
    return CategorizeResponse(**result)


@router.post("/insights", response_model=InsightsResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def insights(
    request: Request,
    body: InsightsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InsightsResponse:
    result = await analysis_service.generate_insights(db, current_user.id, body.date_from, body.date_to)
    return InsightsResponse(**result)
