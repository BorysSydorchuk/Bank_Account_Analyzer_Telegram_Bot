"""GET /api/categories, PATCH /api/categories/{name}, POST /api/categories,
and POST /api/categories/{name}/reset (S3-06).

All four scoped to the authenticated user as of S6-06 — GET was S6-05's
first real test; this ticket finishes the other three.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud
from ..auth.dependency import get_current_user
from ..colors import describe_validation_failure
from ..db import get_db
from ..models import User
from ..schemas import CategoryOut, CreateCategoryRequest, PatchCategoryRequest

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def get_categories(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[CategoryOut]:
    return crud.list_categories(db, current_user.id)


@router.patch("/{name}", response_model=CategoryOut)
def patch_category(
    name: str,
    body: PatchCategoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CategoryOut:
    """A manual color override — validated by the same rules as the S3-02
    AI assignment, so a user's pick is held to the same bar as the AI's.

    S6-06 — a `name` belonging to another user now reads identically to
    one that doesn't exist at all: crud.set_category_color looks up the
    composite (user_id, name) key, so there's no separate ownership check
    to get wrong — the 404 below is the only possible "not found" shape.
    """
    reason = describe_validation_failure(body.color)
    if reason:
        raise HTTPException(status_code=400, detail=reason)

    category = crud.set_category_color(db, current_user.id, name, body.color)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Category '{name}' not found.")
    return category


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    body: CreateCategoryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> CategoryOut:
    """A brand-new, user-defined category — immediately available anywhere
    GET /api/categories is read from, including the S3-05 manual editor's
    category dropdown."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name can't be empty.")

    existing_names = {c.name.lower() for c in crud.list_categories(db, current_user.id)}
    if name.lower() in existing_names:
        raise HTTPException(status_code=400, detail=f"A category named '{name}' already exists.")

    reason = describe_validation_failure(body.color)
    if reason:
        raise HTTPException(status_code=400, detail=reason)

    return crud.create_category(db, current_user.id, name, body.color)


@router.post("/{name}/reset", response_model=CategoryOut)
def reset_category(
    name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> CategoryOut:
    """Restores the last AI-assigned color after a user override. 404s both
    when the category doesn't exist for this user and when it has no AI
    color to reset to — the frontend only shows this action when ai_color
    is present, so reaching this with nothing to reset means the category
    changed under it.
    """
    category = crud.reset_category_to_ai(db, current_user.id, name)
    if category is None:
        raise HTTPException(status_code=404, detail=f"'{name}' has no AI-assigned color to reset to.")
    return category
