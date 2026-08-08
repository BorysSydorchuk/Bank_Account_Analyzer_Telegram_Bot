"""GET /api/categories, PATCH /api/categories/{name}, POST /api/categories,
and POST /api/categories/{name}/reset (S3-06).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud
from ..colors import describe_validation_failure
from ..db import get_db
from ..schemas import CategoryOut, CreateCategoryRequest, PatchCategoryRequest

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def get_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    return crud.list_categories(db)


@router.patch("/{name}", response_model=CategoryOut)
def patch_category(name: str, body: PatchCategoryRequest, db: Session = Depends(get_db)) -> CategoryOut:
    """A manual color override — validated by the same rules as the S3-02
    AI assignment, so a user's pick is held to the same bar as the AI's.
    """
    reason = describe_validation_failure(body.color)
    if reason:
        raise HTTPException(status_code=400, detail=reason)

    category = crud.set_category_color(db, name, body.color)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Category '{name}' not found.")
    return category


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CreateCategoryRequest, db: Session = Depends(get_db)) -> CategoryOut:
    """A brand-new, user-defined category — immediately available anywhere
    GET /api/categories is read from, including the S3-05 manual editor's
    category dropdown."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name can't be empty.")

    existing_names = {c.name.lower() for c in crud.list_categories(db)}
    if name.lower() in existing_names:
        raise HTTPException(status_code=400, detail=f"A category named '{name}' already exists.")

    reason = describe_validation_failure(body.color)
    if reason:
        raise HTTPException(status_code=400, detail=reason)

    return crud.create_category(db, name, body.color)


@router.post("/{name}/reset", response_model=CategoryOut)
def reset_category(name: str, db: Session = Depends(get_db)) -> CategoryOut:
    """Restores the last AI-assigned color after a user override. 404s both
    when the category doesn't exist and when it has no AI color to reset
    to — the frontend only shows this action when ai_color is present, so
    reaching this with nothing to reset means the category changed under it.
    """
    category = crud.reset_category_to_ai(db, name)
    if category is None:
        raise HTTPException(status_code=404, detail=f"'{name}' has no AI-assigned color to reset to.")
    return category
