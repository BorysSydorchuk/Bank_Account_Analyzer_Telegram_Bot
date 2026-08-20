"""S5-04 — S4-06 regression: the AI chat assistant's context must include
biggest_expense, not just the summary totals. chat_service._summary_text is
what actually gets injected into ChatAgent's system prompt.
"""
from datetime import date
from decimal import Decimal

from freezegun import freeze_time

from app.chat_service import _summary_text


@freeze_time("2026-08-18")
def test_chat_context_summary_mentions_biggest_expense(db_session, test_user, transaction_factory):
    db_session.add_all(
        [
            transaction_factory(booking_date=date(2026, 8, 10), amount=Decimal("-12.00"), description="Colruyt Anderlecht"),
            transaction_factory(booking_date=date(2026, 8, 12), amount=Decimal("-289.99"), description="Kinepolis Brussels"),
        ]
    )
    db_session.flush()

    summary = _summary_text(db_session, test_user.id, date(2026, 8, 18))

    assert "Biggest expense" in summary
    assert "Kinepolis Brussels" in summary
    assert "289,99" in summary  # Belgian locale formatting, per _format_amount


@freeze_time("2026-08-18")
def test_chat_context_summary_has_no_biggest_expense_line_when_nothing_was_spent(db_session, test_user, transaction_factory):
    db_session.add(transaction_factory(booking_date=date(2026, 8, 10), amount=Decimal("500.00")))
    db_session.flush()

    summary = _summary_text(db_session, test_user.id, date(2026, 8, 18))

    assert "Biggest expense" not in summary
