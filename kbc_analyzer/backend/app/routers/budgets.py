"""GET /api/budgets, POST /api/budgets, PATCH /api/budgets/{category}, and
DELETE /api/budgets/{category} (S4-05).

All four scoped to the authenticated user as of S6-06 — GET was S6-05's
first real test; this ticket finishes the other three, removing the
CURRENT_USER_ID=None placeholder for good.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud
from ..auth.dependency import get_current_user
from ..db import get_db
from ..models import User
from ..schemas import BudgetOut, CreateBudgetRequest, PatchBudgetRequest

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


def _budget_out(db: Session, user_id: UUID, category: str) -> BudgetOut:
    """Re-reads one budget with its computed spend/status via the same query
    GET /api/budgets uses, so a freshly created or edited budget is reported
    with exactly the numbers a follow-up GET would show — no separate
    percentage/status calculation to keep in sync with list_budgets_with_status.
    """
    budgets = crud.list_budgets_with_status(db, user_id)
    return next(BudgetOut(**b) for b in budgets if b["category"] == category)


@router.get("", response_model=list[BudgetOut])
def get_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BudgetOut]:
    return [BudgetOut(**b) for b in crud.list_budgets_with_status(db, current_user.id)]


@router.post("", response_model=BudgetOut, status_code=201)
def create_budget(
    body: CreateBudgetRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BudgetOut:
    """A new monthly spending limit for one category."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Budget amount must be greater than zero.")

    # S8-09: category is FK'd to categories(user_id, name) — without this
    # check, a name that doesn't exist for this user (found live: every
    # account except the original bootstrap one had zero categories) hit
    # an unhandled IntegrityError, a raw 500 rather than a clean error.
    known_category_names = {c.name for c in crud.list_categories(db, current_user.id)}
    if body.category not in known_category_names:
        raise HTTPException(status_code=400, detail=f"'{body.category}' isn't a known category.")

    existing = crud.get_budget(db, current_user.id, body.category)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"A budget for '{body.category}' already exists.")

    crud.create_budget(db, current_user.id, body.category, Decimal(str(body.amount)))
    return _budget_out(db, current_user.id, body.category)


@router.patch("/{category}", response_model=BudgetOut)
def patch_budget(
    category: str,
    body: PatchBudgetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BudgetOut:
    """Changes an existing budget's monthly limit.

    S6-06 — a `category` belonging to another user now reads identically
    to one that doesn't exist: crud.update_budget_amount's lookup is
    already scoped by (user_id, category), so the 404 below is the only
    "not found" shape, no separate ownership check needed.
    """
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Budget amount must be greater than zero.")

    budget = crud.update_budget_amount(db, current_user.id, category, Decimal(str(body.amount)))
    if budget is None:
        raise HTTPException(status_code=404, detail=f"No budget set for '{category}'.")
    return _budget_out(db, current_user.id, category)


@router.delete("/{category}", status_code=204)
def delete_budget(
    category: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> None:
    deleted = crud.delete_budget(db, current_user.id, category)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No budget set for '{category}'.")
