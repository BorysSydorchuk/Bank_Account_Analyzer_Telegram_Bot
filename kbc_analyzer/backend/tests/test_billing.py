"""S9-01 — the billing kill switch (app_settings.BILLING_ENABLED).

Exercises the real mechanism against a real db_session, not a mock — the
one property that matters is that it defaults to off and a direct value
flip is picked up on the very next read, with no caching layer to stub out.
"""
from app import crud
from app.billing import is_billing_enabled


def test_billing_defaults_off_with_no_row(db_session):
    """A fresh database with no app_settings row at all reads as billing-off."""
    assert is_billing_enabled(db_session) is False


def test_billing_flips_on_and_off_immediately(db_session):
    crud.set_app_setting(db_session, "BILLING_ENABLED", "true")
    assert is_billing_enabled(db_session) is True

    crud.set_app_setting(db_session, "BILLING_ENABLED", "false")
    assert is_billing_enabled(db_session) is False


def test_get_app_setting_falls_back_to_default_for_unknown_key(db_session):
    assert crud.get_app_setting(db_session, "NOT_A_REAL_KEY", default="fallback") == "fallback"
