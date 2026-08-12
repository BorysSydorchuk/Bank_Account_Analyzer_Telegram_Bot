"""GET /api/budgets, POST /api/budgets, PATCH /api/budgets/{category}, and
DELETE /api/budgets/{category} (S4-05).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud
from ..db import get_db
from ..schemas import BudgetOut, CreateBudgetRequest, PatchBudgetRequest

router = APIRouter(prefix="/api/budgets", tags=["budgets"])

# TODO(Sprint 6): replace with the authenticated user's id once auth exists.
# Every crud.* call below already takes user_id as an explicit parameter so
# that sprint only has to change this one value, not the function signatures.
CURRENT_USER_ID = None


def _budget_out(db: Session, category: str) -> BudgetOut:
    """Re-reads one budget with its computed spend/status via the same query
    GET /api/budgets uses, so a freshly created or edited budget is reported
    with exactly the numbers a follow-up GET would show — no separate
    percentage/status calculation to keep in sync with list_budgets_with_status.
    """
    budgets = crud.list_budgets_with_status(db, CURRENT_USER_ID)
    return next(BudgetOut(**b) for b in budgets if b["category"] == category)


@router.get("", response_model=list[BudgetOut])
def get_budgets(db: Session = Depends(get_db)) -> list[BudgetOut]:
    return [BudgetOut(**b) for b in crud.list_budgets_with_status(db, CURRENT_USER_ID)]


@router.post("", response_model=BudgetOut, status_code=201)
def create_budget(body: CreateBudgetRequest, db: Session = Depends(get_db)) -> BudgetOut:
    """A new monthly spending limit for one category."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Budget amount must be greater than zero.")

    existing = crud.get_budget(db, CURRENT_USER_ID, body.category)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"A budget for '{body.category}' already exists.")

    crud.create_budget(db, CURRENT_USER_ID, body.category, Decimal(str(body.amount)))
    return _budget_out(db, body.category)


@router.patch("/{category}", response_model=BudgetOut)
def patch_budget(category: str, body: PatchBudgetRequest, db: Session = Depends(get_db)) -> BudgetOut:
    """Changes an existing budget's monthly limit."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Budget amount must be greater than zero.")

    budget = crud.update_budget_amount(db, CURRENT_USER_ID, category, Decimal(str(body.amount)))
    if budget is None:
        raise HTTPException(status_code=404, detail=f"No budget set for '{category}'.")
    return _budget_out(db, category)


@router.delete("/{category}", status_code=204)
def delete_budget(category: str, db: Session = Depends(get_db)) -> None:
    deleted = crud.delete_budget(db, CURRENT_USER_ID, category)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No budget set for '{category}'.")
