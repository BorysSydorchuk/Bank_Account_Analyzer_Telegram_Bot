"""S7-09 — email verification and password reset, real round trips through
the actual HTTP routes. The email client is faked (conftest.py's autouse
_fake_resend_client, provider switched to Resend at S8-05), but everything
else is real: real token generation (auth/tokens.py, real Redis), real
template rendering, and the token used to complete each flow is extracted
from the actual email body the fake client recorded — not generated
separately in the test, which would only prove the test's own token works,
not that the real one sent to the user does.
"""
import re

import pytest

from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models import BetaInvite, User
from app.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Same reasoning as test_email_password_auth.py's fixture of the
    same name — slowapi's in-memory limiter is keyed on remote address,
    and TestClient reports a fixed address for every request, so without
    this every test in this file would share one bucket with every other
    test in the whole run, not just within itself."""
    limiter.reset()
    yield


def _extract_token(sent_calls: list[dict], link_prefix: str) -> str:
    """Pulls the real token out of the real email body the fake Resend
    client recorded, the same way a real user copying a real link out of
    a real inbox would end up with it."""
    assert len(sent_calls) == 1, f"expected exactly one email sent, got {len(sent_calls)}"
    text_body = sent_calls[0]["text"]
    match = re.search(rf"{re.escape(link_prefix)}\?token=(\S+)", text_body)
    assert match is not None, f"no {link_prefix}?token=... link found in the real email body: {text_body!r}"
    return match.group(1)


# ── Email verification ──────────────────────────────────────────────────────


def test_registration_sends_a_verification_email_and_the_real_link_verifies_the_account(
    client, db_session, _fake_resend_client
):
    db_session.add(BetaInvite(email="verify-me@example.com"))
    db_session.flush()
    register_response = client.post(
        "/api/auth/register", json={"email": "verify-me@example.com", "password": "a-real-password-123"}
    )
    assert register_response.status_code == 201, register_response.text
    assert register_response.json()["email_verified"] is False

    token = _extract_token(_fake_resend_client.sent, "http://localhost:5173/verify-email")

    verify_response = client.post("/api/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 204, verify_response.text

    me_response = client.get("/api/auth/me")
    assert me_response.json()["email_verified"] is True


def test_verify_email_rejects_an_invalid_token(client):
    response = client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
    assert response.status_code == 400
    assert "invalid or has expired" in response.text


def test_verify_email_token_is_single_use(client, db_session, _fake_resend_client):
    db_session.add(BetaInvite(email="single-use@example.com"))
    db_session.flush()
    client.post("/api/auth/register", json={"email": "single-use@example.com", "password": "a-real-password-123"})
    token = _extract_token(_fake_resend_client.sent, "http://localhost:5173/verify-email")

    first = client.post("/api/auth/verify-email", json={"token": token})
    assert first.status_code == 204

    second = client.post("/api/auth/verify-email", json={"token": token})
    assert second.status_code == 400, "a replayed verification link must not succeed a second time"


# ── Password reset ───────────────────────────────────────────────────────────


def _make_user_with_password(db_session, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash, email_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def test_password_reset_sends_a_real_email_and_the_real_link_sets_a_working_new_password(
    client, db_session, _fake_resend_client
):
    from app.auth.password import hash_password

    user = _make_user_with_password(db_session, "reset-me@example.com", hash_password("the-old-password-123"))

    request_response = client.post("/api/auth/request-password-reset", json={"email": "reset-me@example.com"})
    assert request_response.status_code == 200
    assert "we've sent a password reset link" in request_response.json()["message"]

    token = _extract_token(_fake_resend_client.sent, "http://localhost:5173/reset-password")

    reset_response = client.post("/api/auth/reset-password", json={"token": token, "password": "a-brand-new-password-456"})
    assert reset_response.status_code == 204, reset_response.text

    # Real proof, not narration: log in with the NEW password succeeds...
    new_login = client.post(
        "/api/auth/login", json={"email": "reset-me@example.com", "password": "a-brand-new-password-456"}
    )
    assert new_login.status_code == 200, new_login.text

    # ...and the OLD password no longer works.
    old_login = client.post(
        "/api/auth/login", json={"email": "reset-me@example.com", "password": "the-old-password-123"}
    )
    assert old_login.status_code == 401


def test_request_password_reset_returns_the_same_generic_response_whether_or_not_the_email_exists(
    client, db_session, _fake_resend_client
):
    """S6-04's own decided shape for this endpoint (verification_debt.md) —
    never lets the response reveal which emails have accounts."""
    _make_user_with_password(db_session, "real-account@example.com", "irrelevant-hash")

    real_response = client.post("/api/auth/request-password-reset", json={"email": "real-account@example.com"})
    fake_response = client.post("/api/auth/request-password-reset", json={"email": "no-such-account@example.com"})

    assert real_response.status_code == fake_response.status_code == 200
    assert real_response.json() == fake_response.json()
    # Only the real account actually got an email — the identical response
    # doesn't mean identical side effects, just an identical observable one.
    assert len(_fake_resend_client.sent) == 1
    assert _fake_resend_client.sent[0]["to"] == ["real-account@example.com"]


def test_reset_password_rejects_an_invalid_token(client):
    response = client.post("/api/auth/reset-password", json={"token": "not-a-real-token", "password": "a-real-password-123"})
    assert response.status_code == 400
    assert "invalid or has expired" in response.text


def test_reset_password_validates_strength_before_consuming_the_token(client, db_session, _fake_resend_client):
    """A rejected request must never burn a valid, still-usable token —
    same discipline S5-07 already established for sync_lock (validate
    before acquiring)."""
    _make_user_with_password(db_session, "weak-password-test@example.com", "irrelevant-hash")
    client.post("/api/auth/request-password-reset", json={"email": "weak-password-test@example.com"})
    token = _extract_token(_fake_resend_client.sent, "http://localhost:5173/reset-password")

    weak_response = client.post("/api/auth/reset-password", json={"token": token, "password": "short"})
    assert weak_response.status_code == 400
    assert "at least" in weak_response.text

    # The token must still be valid — the weak-password attempt never consumed it.
    real_response = client.post(
        "/api/auth/reset-password", json={"token": token, "password": "a-real-password-123"}
    )
    assert real_response.status_code == 204, real_response.text


# ── Unverified-account access policy ────────────────────────────────────────


def test_unverified_account_is_blocked_from_enable_banking(client, db_session):
    user = User(email="unverified@example.com", password_hash="irrelevant-hash", email_verified=False)
    db_session.add(user)
    db_session.flush()
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))

    status_response = client.get("/api/auth/enable-banking/status")
    assert status_response.status_code == 403
    assert "Verify your email" in status_response.text


def test_unverified_account_still_has_full_access_to_everything_else(client, db_session):
    """The deliberate policy: unverified blocks Enable Banking/sync only,
    not the whole app."""
    user = User(email="unverified-but-fine@example.com", password_hash="irrelevant-hash", email_verified=False)
    db_session.add(user)
    db_session.flush()
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))

    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/categories").status_code == 200
    assert client.get("/api/settings").status_code == 200


def test_verified_account_can_reach_enable_banking_status(client, db_session):
    user = User(email="verified-user@example.com", password_hash="irrelevant-hash", email_verified=True)
    db_session.add(user)
    db_session.flush()
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))

    response = client.get("/api/auth/enable-banking/status")
    assert response.status_code == 200
