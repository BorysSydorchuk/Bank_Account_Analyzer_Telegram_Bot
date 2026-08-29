"""Per-user daily/monthly caps on LLM-calling actions (S8-04) — a real beta
cost/abuse ceiling, not a rate limiter. `app/rate_limit.py`'s slowapi
limiter already covers short-window burst protection (N per minute, IP-keyed,
guards against a runaway client or a stuck retry loop); this is a different
mechanism for a different problem — cumulative daily/monthly cost from a
real but excessive usage pattern, keyed on the authenticated user. The two
don't overlap: a user could comfortably stay under every per-minute rate
limit while still running up real LLM cost over a day, which is exactly what
this closes.

Deliberately blunt, on purpose — Sprint 9's handoff note calls S8-04's caps
"blunt beta caps," to be replaced by real plan limits once real usage
patterns are known. Not tuned per-user, no grace period, no soft warning
before the hard cut — just a generous ceiling.

S9-04 wires in S9-01's billing kill switch and S9-02's tier: with billing
off, `crud.get_user_tier` is never even called — behavior is byte-for-byte
Sprint 8 (see tests/test_usage_limits.py, unmodified, which is this
ticket's own kill-switch-off regression evidence). With billing on, a free
user still gets exactly DAILY_LIMITS/MONTHLY_LIMITS; a paid user gets
PAID_DAILY_LIMITS/PAID_MONTHLY_LIMITS instead — still a real ceiling, not
unlimited, per S9-01's confirmed free-vs-paid distinction.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import crud
from .billing import is_billing_enabled
from .models import UsageEvent

__all__ = ["try_record_usage", "DAILY_LIMITS", "MONTHLY_LIMITS", "PAID_DAILY_LIMITS", "PAID_MONTHLY_LIMITS"]

# Separate caps per action, not one combined budget — a chatty user
# shouldn't crowd out their own categorization/insight allowance, and each
# action has a very different real usage frequency (chat is normal-use
# frequent; categorize/insights typically run once or twice a day via
# sync). Numbers are generous for real single-user-scale beta use, a real
# ceiling against a bug or a scripted abuse pattern. These are also the
# free-tier numbers once billing is on — kept as the same names or the
# kill-switch-off path (and every pre-S9-04 caller) would need to change.
DAILY_LIMITS = {"chat": 50, "categorize": 10, "insights": 10}
MONTHLY_LIMITS = {"chat": 500, "categorize": 100, "insights": 100}

# S9-04: paid tier gets 3x the free-tier ceiling (Borys's call, confirmed
# 2026-08-29) — still a real technical backstop against a compromised or
# runaway paid account, not unlimited, per S9-01's confirmed free-vs-paid
# distinction ("caps still apply at a higher threshold, per Recommended
# option — keeps a technical backstop against runaway LLM API cost even on
# a paid/compromised account").
PAID_DAILY_LIMITS = {"chat": 150, "categorize": 30, "insights": 30}
PAID_MONTHLY_LIMITS = {"chat": 1500, "categorize": 300, "insights": 300}

ACTION_LABELS = {
    "chat": "chat messages",
    "categorize": "categorization runs",
    "insights": "insight generations",
}


def try_record_usage(db: Session, user_id: UUID, action: str) -> str | None:
    """Check this user's daily/monthly cap for `action`, and record a real
    usage event if they're still under it. Returns a clear, user-facing
    message if the cap is hit (nothing is recorded); returns None and
    records the event otherwise.

    Checked in this order — daily first — since it's the more common real
    hit and gives the more specific, actionable message ("try again
    tomorrow" vs "resets next month").

    Tier is only ever consulted when billing is on (S9-01's kill switch) —
    with it off, this function's behavior is identical to before S9-04
    existed, including the exact wording of every message it returns.
    """
    billing_on = is_billing_enabled(db)
    is_paid = billing_on and crud.get_user_tier(db, user_id) == "paid"
    daily_limits = PAID_DAILY_LIMITS if is_paid else DAILY_LIMITS
    monthly_limits = PAID_MONTHLY_LIMITS if is_paid else MONTHLY_LIMITS
    # Only a free-tier user, with billing actually on, ever sees the
    # upgrade-mentioning message (S9-04's own requirement) — a paid user
    # hitting their own (higher) cap has nothing further to upgrade to in
    # this two-tier model, and the kill-switch-off path must keep S8-04's
    # original wording verbatim regardless of a user's stored tier.
    mention_upgrade = billing_on and not is_paid

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    label = ACTION_LABELS[action]

    daily_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(UsageEvent.user_id == user_id, UsageEvent.action == action, UsageEvent.created_at >= day_start)
    ).scalar_one()
    if daily_count >= daily_limits[action]:
        return _cap_message(label, daily_limits[action], "day", "today's", "Try again tomorrow.", mention_upgrade)

    monthly_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(UsageEvent.user_id == user_id, UsageEvent.action == action, UsageEvent.created_at >= month_start)
    ).scalar_one()
    if monthly_count >= monthly_limits[action]:
        return _cap_message(
            label, monthly_limits[action], "month", "this month's", "It resets next month.", mention_upgrade
        )

    db.add(UsageEvent(user_id=user_id, action=action))
    db.commit()
    return None


def _cap_message(
    label: str, limit: int, period: str, period_phrase: str, reset_phrase: str, mention_upgrade: bool
) -> str:
    """The free-tier-with-billing-on message is the only wording S9-04
    changes — every other case (billing off, or a paid user hitting their
    own cap) keeps S8-04's exact original phrasing.
    """
    if mention_upgrade:
        return (
            f"You've reached {period_phrase} free-tier limit for {label} ({limit}/{period}). "
            "Upgrade to Mymble Pro for a higher limit."
        )
    return f"You've reached {period_phrase} beta limit for {label} ({limit}/{period}). {reset_phrase}"
