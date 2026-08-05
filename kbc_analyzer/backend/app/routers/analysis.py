"""POST /api/analysis/categorize."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import analysis_service
from ..db import get_db
from ..schemas import CategorizeRequest, CategorizeResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/categorize", response_model=CategorizeResponse)
async def categorize(body: CategorizeRequest, db: Session = Depends(get_db)) -> CategorizeResponse:
    result = await analysis_service.categorize_transactions(db, body.date_from, body.date_to)
    return CategorizeResponse(**result)
