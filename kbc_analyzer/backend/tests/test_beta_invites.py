"""S8-06 — crud.py's beta-invite helpers directly, below the HTTP layer
already covered by test_email_password_auth.py and test_google_oauth.py's
invite-gate tests. Real Postgres throughout, same as every other crud
test in this suite.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app import crud
from app.models import User


def test_create_beta_invite_stores_email_lowercased(db_session):
    invite = crud.create_beta_invite(db_session, "MixedCase@Example.com")

    assert invite.email == "mixedcase@example.com"
    assert invite.used_at is None


def test_create_beta_invite_rejects_a_duplicate_email(db_session):
    crud.create_beta_invite(db_session, "dup@example.com")

    with pytest.raises(IntegrityError):
        crud.create_beta_invite(db_session, "dup@example.com")


def test_get_unused_beta_invite_by_email_matches_case_insensitively(db_session):
    """The whole reason this table normalizes to lowercase on write (see
    models.py's BetaInvite docstring) — an invite granted for one casing
    must still match a registration attempt using a different casing of
    the same real address, unlike the pre-existing users.email gap this
    ticket's own pre-check found."""
    crud.create_beta_invite(db_session, "someone@example.com")

    found = crud.get_unused_beta_invite_by_email(db_session, "SomeOne@Example.com")

    assert found is not None
    assert found.email == "someone@example.com"


def test_get_unused_beta_invite_by_email_returns_none_for_an_unknown_email(db_session):
    assert crud.get_unused_beta_invite_by_email(db_session, "nobody@example.com") is None


def test_get_unused_beta_invite_by_email_ignores_an_already_used_invite(db_session):
    invite = crud.create_beta_invite(db_session, "consumed@example.com")
    user = User(email="consumed@example.com", password_hash="irrelevant")
    db_session.add(user)
    db_session.flush()
    crud.mark_beta_invite_used(db_session, invite, user)

    assert crud.get_unused_beta_invite_by_email(db_session, "consumed@example.com") is None


def test_mark_beta_invite_used_records_who_and_when(db_session):
    invite = crud.create_beta_invite(db_session, "marked@example.com")
    user = User(email="marked@example.com", password_hash="irrelevant")
    db_session.add(user)
    db_session.flush()

    updated = crud.mark_beta_invite_used(db_session, invite, user)

    assert updated.used_at is not None
    assert updated.used_by_user_id == user.id
