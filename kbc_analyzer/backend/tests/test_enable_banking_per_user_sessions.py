"""S7-06 — per-user Enable Banking session storage.

Unlike test_enable_banking_callback_csrf.py, these tests do NOT use the
mock_enable_banking_client fixture (fixtures/fake_enable_banking.py) —
that fixture replaces the whole EnableBankingClient class with a fake
that keeps its state in memory, which would bypass exactly the thing
this ticket needs proven: that complete_auth_with_code() really writes
through app.eb_session_store.DatabaseSessionStore, really Fernet-encrypts
at rest, and really keeps two users' rows independent. So here only the
outbound HTTP call (EnableBankingClient._post) is mocked — TESTER.md
prime directive 3 ("no live bank calls, ever") — while every layer above
it (complete_auth_with_code, the session store, encryption) is real.
"""
import pytest

from app.crypto import decrypt
from app.eb_service import EnableBankingService
from app.eb_session_store import DatabaseSessionStore
from app.models import EnableBankingSession, User
from kbc_analyzer.enablebanking import EnableBankingClient


@pytest.fixture
def fake_eb_post(monkeypatch):
    """Patches the real EnableBankingClient's outbound HTTP call so
    complete_auth_with_code() runs for real — including the part this
    ticket actually needs proven, the session_store.save() call — without
    ever hitting Enable Banking's real API."""

    def _post(self, path, body):
        if path == "/sessions":
            return {
                "session_id": f"real-session-for-{body['code']}",
                "accounts": [{"uid": f"acct-uid-for-{body['code']}"}],
            }
        raise AssertionError(f"unexpected path in this test: {path}")

    monkeypatch.setattr(EnableBankingClient, "_post", _post)


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def test_two_users_get_independent_encrypted_sessions(db_session, fake_eb_post):
    user_a = _make_user(db_session, "eb-iso-a@example.com")
    user_b = _make_user(db_session, "eb-iso-b@example.com")

    EnableBankingService(db_session, user_a.id).complete_reauthorization("code-for-a")
    EnableBankingService(db_session, user_b.id).complete_reauthorization("code-for-b")

    row_a = db_session.get(EnableBankingSession, user_a.id)
    row_b = db_session.get(EnableBankingSession, user_b.id)
    assert row_a is not None and row_b is not None

    # Encrypted at rest: the raw column never contains the plaintext
    # session_id, and two different users' ciphertexts are never equal
    # (would be a real tell that encryption wasn't actually happening).
    assert "code-for-a" not in row_a.session_id_encrypted
    assert "code-for-b" not in row_b.session_id_encrypted
    assert row_a.session_id_encrypted != row_b.session_id_encrypted
    assert row_a.account_uids_encrypted != row_b.account_uids_encrypted

    # Decrypts correctly — and to the RIGHT user's value, the real proof
    # this isn't just "two different blobs," it's "each user's own data."
    assert decrypt(row_a.session_id_encrypted) == "real-session-for-code-for-a"
    assert decrypt(row_b.session_id_encrypted) == "real-session-for-code-for-b"

    # get_account_uids() goes through the real session_valid() check too,
    # not just a direct decrypt — proves the whole read path is correct,
    # not only storage.
    assert EnableBankingService(db_session, user_a.id).get_account_uids() == ["acct-uid-for-code-for-a"]
    assert EnableBankingService(db_session, user_b.id).get_account_uids() == ["acct-uid-for-code-for-b"]


def test_a_second_users_reauthorization_never_touches_the_first_users_row(db_session, fake_eb_post):
    """The on_conflict_do_update in DatabaseSessionStore.save() is keyed
    on user_id — this proves that scoping is real, not just declared:
    user B completing their own reauthorization must leave user A's
    already-saved row byte-for-byte unchanged."""
    user_a = _make_user(db_session, "eb-noclobber-a@example.com")
    user_b = _make_user(db_session, "eb-noclobber-b@example.com")

    EnableBankingService(db_session, user_a.id).complete_reauthorization("code-for-a")
    row_a_before = db_session.get(EnableBankingSession, user_a.id)
    session_id_before = row_a_before.session_id_encrypted
    account_uids_before = row_a_before.account_uids_encrypted
    valid_until_before = row_a_before.valid_until

    EnableBankingService(db_session, user_b.id).complete_reauthorization("code-for-b")

    db_session.expire_all()  # force a real re-read from Postgres, not the session's identity-map cache
    row_a_after = db_session.get(EnableBankingSession, user_a.id)
    assert row_a_after.session_id_encrypted == session_id_before
    assert row_a_after.account_uids_encrypted == account_uids_before
    assert row_a_after.valid_until == valid_until_before


def test_expiry_status_is_independent_per_user(db_session):
    """Backs the 'reconnect banner is correctly scoped per user' criterion
    at the service layer that actually decides active/expired — the
    frontend hook fetches this per-session-cookie automatically, so the
    real scoping question is whether the backend ever mixes two users'
    expiry states, which this proves directly against two rows written
    with deliberately different valid_until values."""
    from datetime import datetime, timedelta

    user_fresh = _make_user(db_session, "eb-expiry-fresh@example.com")
    user_expired = _make_user(db_session, "eb-expiry-expired@example.com")

    DatabaseSessionStore(db_session, user_fresh.id).save(
        {
            "session_id": "fresh-session",
            "account_uids": ["fresh-acct"],
            "valid_until": (datetime.now() + timedelta(days=60)).isoformat(),
        }
    )
    DatabaseSessionStore(db_session, user_expired.id).save(
        {
            "session_id": "expired-session",
            "account_uids": ["expired-acct"],
            "valid_until": (datetime.now() - timedelta(days=1)).isoformat(),
        }
    )

    fresh_status = EnableBankingService(db_session, user_fresh.id).get_session_status()
    expired_status = EnableBankingService(db_session, user_expired.id).get_session_status()

    assert fresh_status["status"] == "active"
    assert expired_status["status"] == "expired"
    # Never the other user's expiry leaking through.
    assert expired_status["expires_at"] is None
    assert fresh_status["expires_at"] != expired_status.get("expires_at")
