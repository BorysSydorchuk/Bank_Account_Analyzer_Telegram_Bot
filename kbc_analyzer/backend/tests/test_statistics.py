"""S5-04 — statistics correctness invariant. compute_statistics() is pure
(list[Transaction] in, dict out) so these build lightweight, unsaved
Transaction objects directly rather than going through the database —
nothing here needs db_session at all.
"""
from datetime import date
from decimal import Decimal

from app.models import Transaction
from app.statistics import compute_statistics


def _tx(day: date, amount: str, category: str | None = None) -> Transaction:
    return Transaction(
        account_id="a", external_id=f"ext-{day.isoformat()}-{amount}-{category}",
        booking_date=day, amount=Decimal(amount), currency="EUR",
        description="test", category=category,
    )


def test_by_day_zero_fills_every_calendar_day_including_zero_activity_days():
    date_from, date_to = date(2026, 8, 1), date(2026, 8, 5)
    transactions = [_tx(date(2026, 8, 1), "-10.00"), _tx(date(2026, 8, 5), "-5.00")]

    result = compute_statistics(transactions, date_from, date_to)

    by_day_dates = [entry["date"] for entry in result["by_day"]]
    assert by_day_dates == [date(2026, 8, d) for d in range(1, 6)]
    zero_activity_day = next(e for e in result["by_day"] if e["date"] == date(2026, 8, 3))
    assert zero_activity_day == {"date": date(2026, 8, 3), "spent": 0.0, "received": 0.0}


def test_by_week_covers_every_week_in_range_including_a_quiet_one():
    # Aug 2026: week 32 = Aug 3-9, week 33 = Aug 10-16, week 34 = Aug 17-23.
    # Week 33 gets no transactions at all — it must still appear as a
    # zero-spend week, not be silently absent from the list.
    date_from, date_to = date(2026, 8, 3), date(2026, 8, 23)
    transactions = [_tx(date(2026, 8, 4), "-20.00"), _tx(date(2026, 8, 20), "-30.00")]

    result = compute_statistics(transactions, date_from, date_to)

    weeks = [w["week"] for w in result["by_week"]]
    assert weeks == ["W32", "W33", "W34"]
    quiet_week = next(w for w in result["by_week"] if w["week"] == "W33")
    assert quiet_week["spent"] == 0.0


def test_by_category_percentages_sum_to_exactly_100_across_awkward_distributions():
    # Three categories that don't divide evenly — classic largest-remainder
    # bait: naive per-category rounding lands on 99.9 or 100.1 here.
    date_from = date_to = date(2026, 8, 1)
    transactions = [
        _tx(date_from, "-33.33", "Groceries"),
        _tx(date_from, "-33.33", "Traveling"),
        _tx(date_from, "-33.34", "Other"),
    ]

    result = compute_statistics(transactions, date_from, date_to)

    total_percentage = sum(cat["percentage"] for cat in result["by_category"])
    assert total_percentage == 100.0


def test_by_category_percentages_sum_to_100_with_seven_way_split():
    date_from = date_to = date(2026, 8, 1)
    amounts = ["-14.00", "-14.00", "-14.00", "-14.00", "-14.00", "-14.00", "-16.00"]
    transactions = [_tx(date_from, amt, f"Cat{i}") for i, amt in enumerate(amounts)]

    result = compute_statistics(transactions, date_from, date_to)

    assert sum(cat["percentage"] for cat in result["by_category"]) == 100.0


def test_biggest_expense_is_the_largest_negative_amount_in_range():
    date_from = date_to = date(2026, 8, 1)
    transactions = [
        _tx(date_from, "-5.00"),
        Transaction(
            account_id="a", external_id="ext-big", booking_date=date_from,
            amount=Decimal("-247.80"), currency="EUR", description="Kinepolis Brussels",
        ),
        _tx(date_from, "-12.00"),
        _tx(date_from, "500.00"),  # income — must never be picked as "biggest expense"
    ]

    result = compute_statistics(transactions, date_from, date_to)

    assert result["summary"]["biggest_expense"] == {
        "description": "Kinepolis Brussels", "amount": 247.80, "date": date_from,
    }


def test_biggest_expense_is_none_when_there_is_no_spending():
    date_from = date_to = date(2026, 8, 1)
    transactions = [_tx(date_from, "500.00")]

    result = compute_statistics(transactions, date_from, date_to)

    assert result["summary"]["biggest_expense"] is None
