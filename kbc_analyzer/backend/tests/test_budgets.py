"""S5-04 — budget status invariant: the on_track/warning/exceeded thresholds
and the calendar-month (not rolling 30-day) spending window.
"""
from datetime import date
from decimal import Decimal

from freezegun import freeze_time

from app import crud


def _spend(db_session, transaction_factory, category: str, amount: str, day: date):
    db_session.add(transaction_factory(category=category, amount=Decimal(amount), booking_date=day))
    db_session.flush()


@freeze_time("2026-08-18")
def test_budget_status_boundaries(db_session, seeded_categories, transaction_factory):
    # A 100.00 budget makes the percentage-used numbers land exactly on the
    # ticket's named boundaries: spend X euros -> X% used.
    crud.create_budget(db_session, None, "Groceries", Decimal("100.00"))
    crud.create_budget(db_session, None, "Traveling", Decimal("100.00"))
    crud.create_budget(db_session, None, "Rent/Housing", Decimal("100.00"))
    crud.create_budget(db_session, None, "Other", Decimal("100.00"))

    _spend(db_session, transaction_factory, "Groceries", "-79.90", date(2026, 8, 10))
    _spend(db_session, transaction_factory, "Traveling", "-80.00", date(2026, 8, 10))
    _spend(db_session, transaction_factory, "Rent/Housing", "-100.00", date(2026, 8, 10))
    _spend(db_session, transaction_factory, "Other", "-100.10", date(2026, 8, 10))

    statuses = {b["category"]: b["status"] for b in crud.list_budgets_with_status(db_session, None)}

    assert statuses["Groceries"] == "on_track"     # 79.9%
    assert statuses["Traveling"] == "warning"       # 80.0% — the boundary itself is "warning", not "exceeded"
    assert statuses["Rent/Housing"] == "warning"     # 100.0% — still "warning" per the > vs >= split
    assert statuses["Other"] == "exceeded"           # 100.1%


@freeze_time("2026-08-01")
def test_spent_this_month_uses_calendar_month_and_resets_on_month_boundary(db_session, transaction_factory):
    """Regression against a rolling-30-day window: a transaction from the
    tail end of the *previous* calendar month must not count towards this
    month's spend, even though it's well within the last 30 days.
    """
    crud.create_budget(db_session, None, "Groceries", Decimal("200.00"))
    # July 31 — one day before "today" (Aug 1), well inside a rolling 30-day
    # window, but in the previous calendar month.
    _spend(db_session, transaction_factory, "Groceries", "-150.00", date(2026, 7, 31))

    budgets = crud.list_budgets_with_status(db_session, None)
    groceries = next(b for b in budgets if b["category"] == "Groceries")

    assert groceries["spent_this_month"] == 0.0
    assert groceries["status"] == "on_track"


@freeze_time("2026-09-01")
def test_spend_from_a_prior_month_does_not_carry_over_after_the_boundary(db_session, transaction_factory):
    crud.create_budget(db_session, None, "Groceries", Decimal("200.00"))
    _spend(db_session, transaction_factory, "Groceries", "-190.00", date(2026, 8, 31))  # last day of August
    _spend(db_session, transaction_factory, "Groceries", "-20.00", date(2026, 9, 1))    # first day of September

    budgets = crud.list_budgets_with_status(db_session, None)
    groceries = next(b for b in budgets if b["category"] == "Groceries")

    # Only September's 20.00 counts — August's 190.00 reset away at the
    # boundary, exactly the behavior a rolling window would NOT have.
    assert groceries["spent_this_month"] == 20.0
    assert groceries["status"] == "on_track"
