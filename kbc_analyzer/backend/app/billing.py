"""Sprint 9 billing plumbing. `is_billing_enabled` is the one kill switch
every billing-aware code path must check first — S9-04 wires this into
usage_limits.py's actual enforcement; nothing reads it yet, so flipping the
app_settings row today has no observable effect anywhere in the app.

Global (not per-user), reversible from the database with no deploy — see
app/models.py's AppSetting docstring for why this isn't a `settings` row.
"""
from sqlalchemy.orm import Session

from . import crud

BILLING_ENABLED_KEY = "BILLING_ENABLED"

__all__ = ["is_billing_enabled"]


def is_billing_enabled(db: Session) -> bool:
    """True only if the app_settings BILLING_ENABLED row is explicitly 'true'; defaults to off."""
    return crud.get_app_setting(db, BILLING_ENABLED_KEY, default="false") == "true"
