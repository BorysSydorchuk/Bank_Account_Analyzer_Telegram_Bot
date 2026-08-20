"""GET /api/budgets, POST /api/budgets, PATCH /api/budgets/{category}, and
DELETE /api/budgets/{category} (S4-05).

GET is the only one of these four protected/scoped so far (S6-05, a
first real test of get_current_user before S6-06's full sweep) — POST,
PATCH, and DELETE still use the CURRENT_USER_ID=None placeholder below,
a deliberate partial state, not an oversight. Since S6-02 made
budgets.user_id NOT NULL, CURRENT_USER_ID=None means those three routes
now query/write against a user_id no real budget has (`WHERE user_id IS
NULL` matches nothing, `INSERT ... user_id=NULL` fails outright) — the
same tracked, deliberate breakage as every other un-threaded crud.py
write path (see docs/tickets/S6-02-schema-migration-user-id-everywhere.md).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud
from ..auth.dependency import get_current_user
from ..db import get_db
from ..models import User
from ..schemas import BudgetOut, CreateBudgetRequest, PatchBudgetRequest

router = APIRouter(prefix="/api/budgets", tags=["budgets"])

# TODO(Sprint 6, S6-06): replace with the authenticated user's id on the
# three routes below once they're wired to get_current_user too. GET
# (below) no longer uses this — it takes current_user.id directly.
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
def get_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[BudgetOut]:
    return [BudgetOut(**b) for b in crud.list_budgets_with_status(db, current_user.id)]


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
