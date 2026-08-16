"""Business logic for GET /api/insights/compare (S4-08): spending deltas
between two arbitrary date ranges. Statistics are always computed live from
transactions — deterministic and correct regardless of insight regeneration.
Insights are read from storage exactly as they are for each exact range
(the S4-04 Option B decision) and never generated here on the fly; a range
that was never synced with insight generation simply has none to show.
"""
from datetime import date

from sqlalchemy.orm import Session

from . import crud
from .schemas import CategoryChange, ComparisonDelta, InsightItem, PeriodComparison
from .statistics import compute_statistics, format_date_range

MAX_RANGE_DAYS = 365


class InvalidDateRangeError(Exception):
    """A comparison range fails CLAUDE.md's date-range rules — a 400, not a 500."""


def _validate_range(date_from: date, date_to: date, label: str) -> None:
    if date_from > date_to:
        raise InvalidDateRangeError(f"{label}: date_from must be before or equal to date_to.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise InvalidDateRangeError(f"{label}: range cannot exceed {MAX_RANGE_DAYS} days.")


def _build_period(db: Session, date_from: date, date_to: date) -> PeriodComparison:
    transactions = crud.list_transactions(db, date_from, date_to)
    stats = compute_statistics(transactions, date_from, date_to)
    insight_rows = crud.list_insights(db, date_from, date_to)
    return PeriodComparison(
        date_range=format_date_range(date_from, date_to),
        total_spent=stats["summary"]["total_spent"],
        by_category=stats["by_category"],
        insights=[
            InsightItem(type=row.type, title=row.title, body=row.body, severity=row.severity)
            for row in insight_rows
        ],
        insights_generated_at=insight_rows[0].generated_at if insight_rows else None,
    )


def _pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return round((new - old) / old * 100, 1)


def _build_delta(period_a: PeriodComparison, period_b: PeriodComparison) -> ComparisonDelta:
    totals_a = {c.category: c.total for c in period_a.by_category}
    totals_b = {c.category: c.total for c in period_b.by_category}
    # Union, not intersection — a category present in only one period still
    # gets an entry (0 on the other side), so e.g. a category that vanished
    # month-over-month shows up as a full decrease instead of being dropped.
    categories = sorted(set(totals_a) | set(totals_b))

    category_changes = [
        CategoryChange(
            category=category,
            period_a=totals_a.get(category, 0.0),
            period_b=totals_b.get(category, 0.0),
            change=round(totals_b.get(category, 0.0) - totals_a.get(category, 0.0), 2),
            change_pct=_pct_change(totals_a.get(category, 0.0), totals_b.get(category, 0.0)),
        )
        for category in categories
    ]
    category_changes.sort(key=lambda c: abs(c.change), reverse=True)

    return ComparisonDelta(
        total_spent_change=round(period_b.total_spent - period_a.total_spent, 2),
        total_spent_change_pct=_pct_change(period_a.total_spent, period_b.total_spent),
        category_changes=category_changes,
    )


def compare_periods(
    db: Session, period_a_from: date, period_a_to: date, period_b_from: date, period_b_to: date
) -> dict:
    """Returns {period_a, period_b, delta} — see schemas.ComparisonResponse.
    Raises InvalidDateRangeError if either range is backwards or exceeds
    MAX_RANGE_DAYS.
    """
    _validate_range(period_a_from, period_a_to, "period_a")
    _validate_range(period_b_from, period_b_to, "period_b")

    period_a = _build_period(db, period_a_from, period_a_to)
    period_b = _build_period(db, period_b_from, period_b_to)
    return {"period_a": period_a, "period_b": period_b, "delta": _build_delta(period_a, period_b)}
