"""Server-side statistics computation for GET /api/statistics.

Aggregation happens here in Python, not SQL. With a personal-finance dataset (hundreds
to low thousands of rows per query), fetching the range once and aggregating in-process
is simpler and easier to get exactly right than hand-rolled SQL — especially the two
trickiest requirements: zero-filling every day/week so charts never see a gap, and
rounding category percentages so they sum to exactly 100.0 (plain per-category rounding
can land on 99.9 or 100.1). If the dataset ever grew large enough for this to matter,
the day/week zero-filling could move into a SQL generate_series join — not worth the
complexity at this scale.
"""
from collections import defaultdict
from datetime import date, timedelta

from .models import Transaction

OTHER_CATEGORY = "Other"


def _daterange(date_from: date, date_to: date) -> list[date]:
    return [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]


def _distribute_percentages(totals: dict[str, float], grand_total: float) -> dict[str, float]:
    """Round each category's share to 1 decimal place so the set sums to exactly 100.0.

    Uses the largest-remainder method, worked in integer tenths-of-a-percent to avoid
    float drift: truncate each share, then hand out the leftover tenths (however many
    are needed to reach exactly 1000 tenths = 100.0%) to the categories with the
    largest truncated-away remainder first.
    """
    if grand_total <= 0 or not totals:
        return {cat: 0.0 for cat in totals}

    exact_tenths = {cat: (amt / grand_total) * 1000 for cat, amt in totals.items()}
    floor_tenths = {cat: int(v) for cat, v in exact_tenths.items()}
    leftover = 1000 - sum(floor_tenths.values())

    by_remainder_desc = sorted(totals, key=lambda cat: exact_tenths[cat] - floor_tenths[cat], reverse=True)
    for cat in by_remainder_desc[:leftover]:
        floor_tenths[cat] += 1

    return {cat: floor_tenths[cat] / 10 for cat in totals}


def _format_date_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.strftime('%b')} {start.day}–{end.day}"
    return f"{start.strftime('%b')} {start.day}–{end.strftime('%b')} {end.day}"


def _aggregate_weeks(by_day: list[dict]) -> list[dict]:
    weeks: dict[tuple[int, int], dict] = {}
    order: list[tuple[int, int]] = []

    for entry in by_day:
        d = entry["date"]
        iso_year, iso_week, _ = d.isocalendar()
        key = (iso_year, iso_week)
        if key not in weeks:
            weeks[key] = {"days": [], "spent": 0.0, "received": 0.0}
            order.append(key)
        weeks[key]["days"].append(d)
        weeks[key]["spent"] += entry["spent"]
        weeks[key]["received"] += entry["received"]

    result = []
    for iso_year, iso_week in order:
        w = weeks[(iso_year, iso_week)]
        result.append({
            "week": f"W{iso_week:02d}",
            "date_range": _format_date_range(w["days"][0], w["days"][-1]),
            "spent": round(w["spent"], 2),
            "received": round(w["received"], 2),
        })
    return result


def compute_statistics(transactions: list[Transaction], date_from: date, date_to: date) -> dict:
    total_spent = 0.0
    total_received = 0.0
    biggest_expense: dict | None = None

    category_totals: dict[str, float] = defaultdict(float)
    category_counts: dict[str, int] = defaultdict(int)
    subcategory_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    subcategory_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    by_day = {d: {"spent": 0.0, "received": 0.0} for d in _daterange(date_from, date_to)}

    for t in transactions:
        amount = float(t.amount)
        d = t.booking_date

        if amount < 0:
            spent = -amount
            total_spent += spent
            if biggest_expense is None or spent > biggest_expense["amount"]:
                biggest_expense = {"description": t.description, "amount": spent, "date": d}

            category = t.category or OTHER_CATEGORY
            category_totals[category] += spent
            category_counts[category] += 1
            if t.subcategory:
                subcategory_totals[category][t.subcategory] += spent
                subcategory_counts[category][t.subcategory] += 1
        else:
            total_received += amount

        if d is not None and d in by_day:
            if amount < 0:
                by_day[d]["spent"] += -amount
            else:
                by_day[d]["received"] += amount

    percentages = _distribute_percentages(dict(category_totals), total_spent)

    by_category = []
    for cat in sorted(category_totals, key=lambda c: category_totals[c], reverse=True):
        sub_totals = subcategory_totals.get(cat, {})
        sub_percentages = _distribute_percentages(dict(sub_totals), category_totals[cat])
        subcategories = [
            {
                "category": sub,
                "total": round(sub_totals[sub], 2),
                "count": subcategory_counts[cat][sub],
                "percentage": sub_percentages[sub],
                "subcategories": [],
            }
            for sub in sorted(sub_totals, key=lambda s: sub_totals[s], reverse=True)
        ]
        by_category.append({
            "category": cat,
            "total": round(category_totals[cat], 2),
            "count": category_counts[cat],
            "percentage": percentages[cat],
            "subcategories": subcategories,
        })

    by_day_list = [
        {"date": d, "spent": round(v["spent"], 2), "received": round(v["received"], 2)}
        for d, v in sorted(by_day.items())
    ]

    return {
        "summary": {
            "total_spent": round(total_spent, 2),
            "total_received": round(total_received, 2),
            "net": round(total_received - total_spent, 2),
            "transaction_count": len(transactions),
            "biggest_expense": (
                {
                    "description": biggest_expense["description"],
                    "amount": round(biggest_expense["amount"], 2),
                    "date": biggest_expense["date"],
                }
                if biggest_expense
                else None
            ),
        },
        "by_category": by_category,
        "by_day": by_day_list,
        "by_week": _aggregate_weeks(by_day_list),
    }
