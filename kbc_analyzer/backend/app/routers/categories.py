"""GET /api/categories."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud
from ..db import get_db
from ..schemas import CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def get_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    return crud.list_categories(db)
