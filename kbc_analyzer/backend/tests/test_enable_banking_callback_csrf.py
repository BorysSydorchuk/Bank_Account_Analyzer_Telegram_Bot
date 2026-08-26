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

S7-06: require_enable_banking_owner is gone (any authenticated user can
now reauthorize their own connection), so these tests use a plain test
user rather than one seeded with ENABLE_BANKING_OWNER_EMAIL. Also added:
tests for the new eb_oauth_user_id cookie, which binds a reauthorize
attempt to the user who started it — closing the account-switch-mid-flow
race a single state cookie alone doesn't cover (see routers/auth.py's
module-level comment on _EB_USER_COOKIE_NAME).
"""
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models import User


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def _login_as(client, user: User) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))


def test_reauthorize_sets_state_cookie_matching_the_real_outgoing_state(
    client, db_session, mock_enable_banking_client
):
    user = _make_user(db_session, "eb-csrf-state@example.com")
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

    cookie_user_id = response.cookies.get("eb_oauth_user_id")
    assert cookie_user_id == str(user.id), (
        "eb_oauth_user_id must name the user who actually started this "
        "reauthorize attempt, or the callback's user-binding check is "
        "comparing against nothing meaningful"
    )


def test_callback_rejects_mismatched_state(client, db_session):
    user = _make_user(db_session, "eb-csrf-mismatch@example.com")
    _login_as(client, user)
    client.cookies.set("eb_oauth_state", "value-the-cookie-actually-holds")
    client.cookies.set("eb_oauth_user_id", str(user.id))

    response = client.get(
        "/api/auth/enable-banking/callback",
        params={"code": "some-code", "state": "a-different-value-entirely"},
    )

    assert response.status_code == 400
    assert "no longer valid" in response.text


def test_callback_rejects_a_forged_link_with_no_cookie_at_all(client, db_session):
    user = _make_user(db_session, "eb-csrf-forged@example.com")
    _login_as(client, user)
    # No eb_oauth_state/eb_oauth_user_id cookies set at all — simulates a
    # forged callback link an attacker sends directly, never having gone
    # through /reauthorize in this browser.

    response = client.get(
        "/api/auth/enable-banking/callback",
        params={"code": "some-code", "state": "attacker-guessed-value"},
    )

    assert response.status_code == 400
    assert "no longer valid" in response.text


def test_callback_rejects_a_valid_state_from_a_different_logged_in_user(
    client, db_session, mock_enable_banking_client
):
    """S7-06's own real case: user A starts /reauthorize, then the same
    browser ends up logged in as user B (an account switch, or a second
    tab) before Enable Banking's redirect lands. The state cookie alone
    would still match — this is exactly why eb_oauth_user_id exists."""
    user_a = _make_user(db_session, "eb-user-a@example.com")
    user_b = _make_user(db_session, "eb-user-b@example.com")

    _login_as(client, user_a)
    reauthorize_response = client.post("/api/auth/enable-banking/reauthorize")
    state = reauthorize_response.cookies.get("eb_oauth_state")
    assert state is not None

    # Same browser (same cookie jar keeps eb_oauth_state/eb_oauth_user_id),
    # but now logged in as a different user — overwrites only the session
    # cookie, the way a real account switch would.
    _login_as(client, user_b)

    callback_response = client.get(
        "/api/auth/enable-banking/callback",
        params={"code": "real-authorization-code", "state": state},
    )

    assert callback_response.status_code == 400
    assert "no longer valid" in callback_response.text
    assert mock_enable_banking_client.completed_codes == [], (
        "user A's authorization code must never be completed against user B's session"
    )


def test_callback_with_matching_state_completes_reauthorization(
    client, db_session, mock_enable_banking_client
):
    """The real success path — Reviewer's finding was specifically that
    this case had never actually been exercised. Real matching state,
    real cookie, real call through to EnableBankingService via the
    fake client (not a mocked-out complete_reauthorization)."""
    user = _make_user(db_session, "eb-csrf-success@example.com")
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
    # Both cookies are single-use — same convention as user_auth.py's
    # oauth_state — so a replayed callback can't succeed a second time.
    assert "eb_oauth_state" not in callback_response.cookies
    assert "eb_oauth_user_id" not in callback_response.cookies
