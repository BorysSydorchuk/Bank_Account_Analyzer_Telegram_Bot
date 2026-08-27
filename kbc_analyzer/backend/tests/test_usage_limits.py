"""S8-04 — per-user daily/monthly LLM-action caps.

Exercises the real mechanism directly (try_record_usage against a real
db_session, real UsageEvent rows) rather than mocking around it — this is
exactly the kind of "did the cap actually stop the Nth call" logic that's
easy to get off-by-one wrong in code review alone.
"""
from datetime import datetime, timezone

import pytest

from app.models import User, UsageEvent
from app.usage_limits import DAILY_LIMITS, MONTHLY_LIMITS, try_record_usage


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def test_daily_cap_hit_after_exactly_the_limit(db_session):
    """The (limit)th call succeeds, the (limit + 1)th is rejected — proves
    the boundary is exact, not off-by-one in either direction."""
    user = _make_user(db_session, "usage-daily@example.com")
    limit = DAILY_LIMITS["chat"]

    for i in range(limit):
        result = try_record_usage(db_session, user.id, "chat")
        assert result is None, f"call {i + 1}/{limit} should have succeeded, got: {result}"

    blocked = try_record_usage(db_session, user.id, "chat")
    assert blocked is not None
    assert "today's beta limit" in blocked
    assert "chat messages" in blocked

    # The blocked call must not have recorded a row — a rejected action
    # doesn't cost a cap slot, so a real user retrying tomorrow isn't
    # penalized for today's rejections.
    count = db_session.query(UsageEvent).filter(UsageEvent.user_id == user.id).count()
    assert count == limit


def test_monthly_cap_hit_even_with_daily_cap_untouched(db_session):
    """Real scenario: all of this month's usage happened on a single earlier
    day (so today's own count is zero, nowhere near the daily cap), yet the
    monthly total alone still blocks — proves the two windows are checked
    independently, not just the daily one. Backdated within the current
    month (day 1) rather than tied to "today minus N," so this doesn't
    depend on how far into the month the test happens to run."""
    user = _make_user(db_session, "usage-monthly@example.com")
    monthly_limit = MONTHLY_LIMITS["categorize"]

    now = datetime.now(timezone.utc)
    if now.day == 1:
        pytest.skip("no earlier day exists within the current month to backdate into on the 1st")
    month_start = now.replace(day=1, hour=1, minute=0, second=0, microsecond=0)
    for _ in range(monthly_limit):
        db_session.add(UsageEvent(user_id=user.id, action="categorize", created_at=month_start))
    db_session.commit()

    blocked = try_record_usage(db_session, user.id, "categorize")
    assert blocked is not None
    assert "this month's beta limit" in blocked
    assert "categorization runs" in blocked


def test_caps_are_independent_per_action(db_session):
    """Hitting the chat cap must not block categorize or insights for the
    same user — these are separate budgets, not one shared pool."""
    user = _make_user(db_session, "usage-independent@example.com")

    for _ in range(DAILY_LIMITS["chat"]):
        assert try_record_usage(db_session, user.id, "chat") is None
    assert try_record_usage(db_session, user.id, "chat") is not None

    # Different action, same user, same day — must succeed.
    assert try_record_usage(db_session, user.id, "categorize") is None
    assert try_record_usage(db_session, user.id, "insights") is None


def test_caps_are_independent_per_user(db_session):
    """One user hitting their cap must never affect a different user."""
    user_a = _make_user(db_session, "usage-user-a@example.com")
    user_b = _make_user(db_session, "usage-user-b@example.com")

    for _ in range(DAILY_LIMITS["insights"]):
        assert try_record_usage(db_session, user_a.id, "insights") is None
    assert try_record_usage(db_session, user_a.id, "insights") is not None

    # user_b has never called this action — must succeed regardless of
    # user_a's exhausted cap.
    assert try_record_usage(db_session, user_b.id, "insights") is None
