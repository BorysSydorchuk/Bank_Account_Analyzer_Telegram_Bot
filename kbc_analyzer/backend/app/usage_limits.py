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
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import UsageEvent

__all__ = ["try_record_usage", "DAILY_LIMITS", "MONTHLY_LIMITS"]

# Separate caps per action, not one combined budget — a chatty user
# shouldn't crowd out their own categorization/insight allowance, and each
# action has a very different real usage frequency (chat is normal-use
# frequent; categorize/insights typically run once or twice a day via
# sync). Numbers are generous for real single-user-scale beta use, a real
# ceiling against a bug or a scripted abuse pattern.
DAILY_LIMITS = {"chat": 50, "categorize": 10, "insights": 10}
MONTHLY_LIMITS = {"chat": 500, "categorize": 100, "insights": 100}

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
    """
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    label = ACTION_LABELS[action]

    daily_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(UsageEvent.user_id == user_id, UsageEvent.action == action, UsageEvent.created_at >= day_start)
    ).scalar_one()
    if daily_count >= DAILY_LIMITS[action]:
        return (
            f"You've reached today's beta limit for {label} ({DAILY_LIMITS[action]}/day). "
            "Try again tomorrow."
        )

    monthly_count = db.execute(
        select(func.count())
        .select_from(UsageEvent)
        .where(UsageEvent.user_id == user_id, UsageEvent.action == action, UsageEvent.created_at >= month_start)
    ).scalar_one()
    if monthly_count >= MONTHLY_LIMITS[action]:
        return (
            f"You've reached this month's beta limit for {label} ({MONTHLY_LIMITS[action]}/month). "
            "It resets next month."
        )

    db.add(UsageEvent(user_id=user_id, action=action))
    db.commit()
    return None
