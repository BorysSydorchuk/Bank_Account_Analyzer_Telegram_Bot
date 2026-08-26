"""S7-04 — CSRF state validation on GET /api/auth/enable-banking/callback.

Enable Banking's own start_auth() request used to carry a state value that
was generated and immediately discarded ("not checked by us but required
by the spec") — harmless while the callback only ever ran on localhost,
a real gap once it's a public URL (see app/routers/auth.py's module
docstring for the full incident writeup). These tests exercise the fix
through the real HTTP routes with a real session cookie, not an isolated
unit test of the comparison logic alone.

Reviewer found the happy-path case here had never actually been run: the
fixture's FakeEnableBankingClient.start_auth() didn't accept the new
`state` parameter eb_service.get_reauthorize_url passes positionally, so
this test would TypeError before ever reaching an assertion. Fixed in
tests/fixtures/fake_enable_banking.py; this file was re-run against that
fix before being committed (see the ticket file for the real output).
"""
import os

from app import job_store
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models import User

_EB_OWNER_EMAIL = os.environ["ENABLE_BANKING_OWNER_EMAIL"]


def _make_eb_owner(db_session) -> User:
    # require_enable_banking_owner only lets this one email through
    # (S6-06) — every other user would 403 before the CSRF logic is ever
    # reached. Found live (not assumed): a user with this exact email is
    # already seeded by the 7b2e4c9a1d05 bootstrap migration whenever
    # ENABLE_BANKING_OWNER_EMAIL resolves to the real local .env value
    # (conftest.py's os.environ.setdefault is a no-op once .env has
    # already set it) — inserting a second row with the same email
    # violates the users.email unique constraint. Reuse it if present,
    # create it only for the case where the env var is some other value
    # (e.g. a CI environment with no matching bootstrap-seeded row).
    existing = db_session.query(User).filter(User.email == _EB_OWNER_EMAIL).first()
    if existing is not None:
        return existing
    user = User(email=_EB_OWNER_EMAIL, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def _login_as(client, user: User) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))


def test_reauthorize_sets_state_cookie_matching_the_real_outgoing_state(
    client, db_session, mock_enable_banking_client
):
    user = _make_eb_owner(db_session)
    _login_as(client, user)

    response = client.post("/api/auth/enable-banking/reauthorize")
    assert response.status_code == 200, response.text

    cookie_state = response.cookies.get("eb_oauth_state")
    assert cookie_state is not None, "no eb_oauth_state cookie was set"
    assert cookie_state == mock_enable_banking_client.last_state, (
        "the state stored in the cookie must be the same value actually "
        "sent to Enable Banking, or the CSRF check on callback is comparing "
        "against nothing meaningful"
    )
    assert response.json()["auth_url"].endswith(f"state={cookie_state}")


def test_callback_rejects_mismatched_state(client, db_session):
    user = _make_eb_owner(db_session)
    _login_as(client, user)
    client.cookies.set("eb_oauth_state", "value-the-cookie-actually-holds")

    response = client.get(
        "/api/auth/enable-banking/callback",
        params={"code": "some-code", "state": "a-different-value-entirely"},
    )

    assert response.status_code == 400
    assert "no longer valid" in response.text


def test_callback_rejects_a_forged_link_with_no_cookie_at_all(client, db_session):
    user = _make_eb_owner(db_session)
    _login_as(client, user)
    # No eb_oauth_state cookie set at all — simulates a forged callback
    # link an attacker sends directly, never having gone through
    # /reauthorize in this browser.

    response = client.get(
        "/api/auth/enable-banking/callback",
        params={"code": "some-code", "state": "attacker-guessed-value"},
    )

    assert response.status_code == 400
    assert "no longer valid" in response.text


def test_callback_with_matching_state_completes_reauthorization(
    client, db_session, mock_enable_banking_client
):
    """The real success path — Reviewer's finding was specifically that
    this case had never actually been exercised. Real matching state,
    real cookie, real call through to EnableBankingService via the
    fake client (not a mocked-out complete_reauthorization)."""
    user = _make_eb_owner(db_session)
    _login_as(client, user)

    reauthorize_response = client.post("/api/auth/enable-banking/reauthorize")
    assert reauthorize_response.status_code == 200
    state = reauthorize_response.cookies.get("eb_oauth_state")
    assert state is not None

    # A fresh client carrying the same cookie jar the reauthorize response
    # set, standing in for "the same browser" completing the redirect.
    client.cookies.set("eb_oauth_state", state)
    callback_response = client.get(
        "/api/auth/enable-banking/callback",
        params={"code": "real-authorization-code", "state": state},
    )

    assert callback_response.status_code == 200, callback_response.text
    assert "connected successfully" in callback_response.text
    assert mock_enable_banking_client.completed_codes == ["real-authorization-code"]
    # The state cookie is single-use — same convention as user_auth.py's
    # oauth_state — so a replayed callback with the same state can't
    # succeed a second time.
    assert "eb_oauth_state" not in callback_response.cookies
