"""S9-04 — wiring S9-01's billing kill switch and S9-02's tier into
try_record_usage. tests/test_usage_limits.py (unmodified by this ticket)
is the kill-switch-off regression evidence; these tests cover the
kill-switch-on behavior it doesn't touch: free vs. paid caps, and the
free-tier upgrade-mentioning message.
"""
from datetime import datetime, timezone

import pytest

from app import crud
from app.models import Subscription, UsageEvent, User
from app.usage_limits import DAILY_LIMITS, MONTHLY_LIMITS, PAID_DAILY_LIMITS, PAID_MONTHLY_LIMITS, try_record_usage


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def _make_paid_user(db_session, email: str) -> User:
    user = _make_user(db_session, email)
    db_session.add(Subscription(user_id=user.id, tier="paid", status="active"))
    db_session.commit()
    return user


def _enable_billing(db_session) -> None:
    crud.set_app_setting(db_session, "BILLING_ENABLED", "true")


def test_billing_on_free_tier_hits_free_cap_with_upgrade_message(db_session):
    _enable_billing(db_session)
    user = _make_user(db_session, "tiered-free-daily@example.com")
    limit = DAILY_LIMITS["chat"]

    for _ in range(limit):
        assert try_record_usage(db_session, user.id, "chat") is None

    blocked = try_record_usage(db_session, user.id, "chat")
    assert blocked is not None
    assert "free-tier limit" in blocked
    assert "Upgrade to Mymble Pro" in blocked


def test_billing_on_paid_tier_gets_higher_cap_not_free_cap(db_session):
    """The defining behavior this ticket exists to add: a paid user must
    keep succeeding past the free-tier daily limit."""
    _enable_billing(db_session)
    user = _make_paid_user(db_session, "tiered-paid-daily@example.com")
    free_limit = DAILY_LIMITS["chat"]
    paid_limit = PAID_DAILY_LIMITS["chat"]
    assert paid_limit > free_limit, "test assumes the paid cap is actually higher"

    for i in range(free_limit + 1):
        result = try_record_usage(db_session, user.id, "chat")
        assert result is None, f"paid user's call {i + 1} (past the free limit of {free_limit}) should still succeed"


def test_billing_on_paid_tier_still_hits_its_own_cap_no_upgrade_message(db_session):
    """Paid isn't unlimited — S9-01's confirmed distinction — and the
    message when it IS hit must not tell an already-paying user to
    upgrade (nothing to upgrade to in this two-tier model)."""
    _enable_billing(db_session)
    user = _make_paid_user(db_session, "tiered-paid-cap@example.com")
    limit = PAID_DAILY_LIMITS["categorize"]

    for _ in range(limit):
        assert try_record_usage(db_session, user.id, "categorize") is None

    blocked = try_record_usage(db_session, user.id, "categorize")
    assert blocked is not None
    assert "beta limit" in blocked
    assert "Upgrade" not in blocked
    assert str(limit) in blocked


def test_billing_on_free_tier_monthly_cap_mentions_upgrade(db_session):
    _enable_billing(db_session)
    user = _make_user(db_session, "tiered-free-monthly@example.com")
    now = datetime.now(timezone.utc)
    if now.day == 1:
        pytest.skip("no earlier day exists within the current month to backdate into on the 1st")
    month_start = now.replace(day=1, hour=1, minute=0, second=0, microsecond=0)
    for _ in range(MONTHLY_LIMITS["insights"]):
        db_session.add(UsageEvent(user_id=user.id, action="insights", created_at=month_start))
    db_session.commit()

    blocked = try_record_usage(db_session, user.id, "insights")
    assert blocked is not None
    assert "this month's free-tier limit" in blocked
    assert "Upgrade to Mymble Pro" in blocked


def test_billing_off_ignores_stored_tier_entirely(db_session):
    """The literal acceptance criterion: with the kill switch off, a user
    who is ALREADY tagged 'paid' in subscriptions must still get the
    free-tier (Sprint 8) caps — tier is never consulted at all when
    billing is off, not just "defaults to free for untagged users"."""
    # BILLING_ENABLED defaults to 'false' — no _enable_billing(...) call.
    user = _make_paid_user(db_session, "tiered-off-paid@example.com")
    free_limit = DAILY_LIMITS["chat"]

    for _ in range(free_limit):
        assert try_record_usage(db_session, user.id, "chat") is None

    blocked = try_record_usage(db_session, user.id, "chat")
    assert blocked is not None
    assert "beta limit" in blocked
    assert "free-tier" not in blocked
    assert "Upgrade" not in blocked
