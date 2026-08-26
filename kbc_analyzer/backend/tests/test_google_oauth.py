"""S6-03 — the Google OAuth flow end to end, with the vendor boundary
(exchange_code_for_tokens/fetch_userinfo) faked at the same seam
user_auth.py imports it through — no live call to Google, ever (same
policy as fake_enable_banking.py/fake_llm_provider.py). Real Redis
sessions, real Postgres user rows; only the two outbound HTTP calls to
Google are replaced.
"""
import pytest

from app import crud
from app.auth.session import SESSION_COOKIE_NAME, get_session
from app.models import User


def _fake_google_profile(monkeypatch, *, google_id: str, email: str, name: str = "Test User"):
    """Patches the two Google-facing calls user_auth.py makes, at the
    import site (app.routers.user_auth), not the defining module —
    matches how the module actually looks them up."""

    def fake_exchange(code: str) -> dict:
        assert code == "fake-auth-code"
        return {"access_token": "fake-access-token"}

    def fake_userinfo(access_token: str) -> dict:
        assert access_token == "fake-access-token"
        return {"sub": google_id, "email": email, "email_verified": True, "name": name}

    monkeypatch.setattr("app.routers.user_auth.exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr("app.routers.user_auth.fetch_userinfo", fake_userinfo)


def _complete_google_sign_in(client, monkeypatch, *, google_id: str, email: str):
    """Drives the real two-request flow: GET /google/login (to get a real
    state cookie the way a browser would), then GET /google/callback with
    that same state — exercising the CSRF check for real, not bypassing
    it."""
    _fake_google_profile(monkeypatch, google_id=google_id, email=email)

    login_response = client.get("/api/auth/google/login", follow_redirects=False)
    state = login_response.cookies["oauth_state"]

    return client.get(
        f"/api/auth/google/callback?code=fake-auth-code&state={state}",
        follow_redirects=False,
    )


def test_new_google_sign_in_creates_a_user_and_session(client, db_session, monkeypatch):
    response = _complete_google_sign_in(client, monkeypatch, google_id="google-sub-new", email="newuser@example.com")

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:5173"
    assert SESSION_COOKIE_NAME in response.cookies

    user = db_session.query(User).filter(User.email == "newuser@example.com").one()
    assert user.google_id == "google-sub-new"
    assert user.password_hash is None

    session_user_id = get_session(response.cookies[SESSION_COOKIE_NAME])
    assert session_user_id == user.id


def test_google_sign_in_on_an_email_with_an_existing_password_account_is_a_conflict_not_a_silent_link(
    client, db_session, monkeypatch
):
    """S6-07 finding 1 — the actual adversarial case, not the benign
    same-person one: an attacker registers a password account under a
    victim's real (unverified) email *first*. When "the real owner"
    later signs in with Google using that same email, this must NOT
    silently attach to the attacker's row — that would hand the attacker
    standing password access to whatever the real owner does under this
    account from then on. Before this fix, google_callback treated
    "email matches, no google_id set yet" as an unconditional linking
    case; this test is what would have caught that.
    """
    attacker_row = User(email="victim@example.com", password_hash="attacker-controlled-hash")
    db_session.add(attacker_row)
    db_session.flush()
    attacker_row_id = attacker_row.id

    response = _complete_google_sign_in(
        client, monkeypatch, google_id="victims-real-google-sub", email="victim@example.com"
    )

    # A conflict redirect, not a sign-in success — no session was created
    # for whoever completed this Google flow.
    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:5173/login?error=google_email_already_registered"
    assert SESSION_COOKIE_NAME not in response.cookies

    # The attacker's row is completely untouched — still exactly one row
    # for this email, still the attacker's password hash, still no
    # google_id attached to it. The real owner's Google identity was
    # never attached to an account they don't control.
    matches = db_session.query(User).filter(User.email == "victim@example.com").all()
    assert len(matches) == 1
    assert matches[0].id == attacker_row_id
    assert matches[0].password_hash == "attacker-controlled-hash"
    assert matches[0].google_id is None
    assert db_session.query(User).filter(User.google_id == "victims-real-google-sub").count() == 0


def test_google_link_requires_authentication(client):
    response = client.get("/api/auth/google/link", follow_redirects=False)
    assert response.status_code == 401


def test_google_link_attaches_google_id_to_the_authenticated_users_own_account(client, db_session, monkeypatch):
    """The only legitimate path to linking (S6-07 finding 1): the real
    account owner is already authenticated (via password), then
    explicitly initiates linking — never as a side effect of a Google
    sign-in attempt."""
    owner = User(email="real-owner@example.com", password_hash="a-real-hash")
    db_session.add(owner)
    db_session.flush()
    owner_id = owner.id

    from app.auth.session import SESSION_COOKIE_NAME as _SESSION_COOKIE, create_session

    client.cookies.set(_SESSION_COOKIE, create_session(owner_id))
    _fake_google_profile(monkeypatch, google_id="owners-real-google-sub", email="real-owner@example.com")

    link_response = client.get("/api/auth/google/link", follow_redirects=False)
    state = link_response.cookies["oauth_state"]
    assert "oauth_link_user_id" in link_response.cookies

    callback_response = client.get(
        f"/api/auth/google/callback?code=fake-auth-code&state={state}", follow_redirects=False
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == "http://localhost:5173/settings?linked=google"

    db_session.refresh(owner)
    assert owner.google_id == "owners-real-google-sub"
    assert owner.password_hash == "a-real-hash"  # untouched
    # Still exactly one row — linking never created a second account.
    assert db_session.query(User).filter(User.email == "real-owner@example.com").count() == 1


def test_google_link_rejects_a_google_identity_already_linked_to_someone_else(client, db_session, monkeypatch):
    already_linked_elsewhere = User(email="other-user@example.com", google_id="claimed-google-sub")
    db_session.add(already_linked_elsewhere)
    linking_user = User(email="wants-to-link@example.com", password_hash="a-real-hash")
    db_session.add(linking_user)
    db_session.flush()
    linking_user_id = linking_user.id

    from app.auth.session import SESSION_COOKIE_NAME as _SESSION_COOKIE, create_session

    client.cookies.set(_SESSION_COOKIE, create_session(linking_user_id))
    _fake_google_profile(monkeypatch, google_id="claimed-google-sub", email="wants-to-link@example.com")

    link_response = client.get("/api/auth/google/link", follow_redirects=False)
    state = link_response.cookies["oauth_state"]

    callback_response = client.get(
        f"/api/auth/google/callback?code=fake-auth-code&state={state}", follow_redirects=False
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == "http://localhost:5173/settings?error=google_link_failed"

    db_session.refresh(linking_user)
    assert linking_user.google_id is None  # never attached


def test_google_link_rejects_when_the_account_already_has_a_different_google_id(client, db_session, monkeypatch):
    user = User(email="already-linked@example.com", google_id="original-google-sub", password_hash="a-real-hash")
    db_session.add(user)
    db_session.flush()
    user_id = user.id

    from app.auth.session import SESSION_COOKIE_NAME as _SESSION_COOKIE, create_session

    client.cookies.set(_SESSION_COOKIE, create_session(user_id))
    _fake_google_profile(monkeypatch, google_id="a-different-google-sub", email="already-linked@example.com")

    link_response = client.get("/api/auth/google/link", follow_redirects=False)
    state = link_response.cookies["oauth_state"]

    callback_response = client.get(
        f"/api/auth/google/callback?code=fake-auth-code&state={state}", follow_redirects=False
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == "http://localhost:5173/settings?error=google_link_failed"

    db_session.refresh(user)
    assert user.google_id == "original-google-sub"  # unchanged


# ── S7-09, Sprint 6 Security Auditor Finding A ──────────────────────────────
# The two tests above already prove google_callback rejects both invalid
# cases — but that only proves the router's own pre-checks worked, which
# is exactly what Finding A said wasn't good enough: those checks used to
# live only at the one call site. These two call crud.link_google_id
# directly, bypassing the router and its cookies/session entirely, to
# prove the function rejects both cases itself, for any caller.


def test_link_google_id_directly_rejects_overwriting_a_different_existing_google_id(db_session):
    user = User(email="direct-call-a@example.com", google_id="original-sub", password_hash="a-real-hash")
    db_session.add(user)
    db_session.flush()

    with pytest.raises(crud.GoogleIdConflictError):
        crud.link_google_id(db_session, user, "a-different-sub")

    db_session.refresh(user)
    assert user.google_id == "original-sub"  # unchanged


def test_link_google_id_directly_rejects_a_google_id_already_claimed_elsewhere(db_session):
    already_linked = User(email="direct-call-owner@example.com", google_id="claimed-sub")
    db_session.add(already_linked)
    wants_to_link = User(email="direct-call-b@example.com", password_hash="a-real-hash")
    db_session.add(wants_to_link)
    db_session.flush()

    with pytest.raises(crud.GoogleIdConflictError):
        crud.link_google_id(db_session, wants_to_link, "claimed-sub")

    db_session.refresh(wants_to_link)
    assert wants_to_link.google_id is None  # never attached


def test_link_google_id_directly_succeeds_for_a_genuinely_new_link(db_session):
    """The positive case, so the two rejection tests above aren't proving
    link_google_id rejects everything — confirms it still does its one
    real job when neither invariant is violated."""
    user = User(email="direct-call-success@example.com", password_hash="a-real-hash")
    db_session.add(user)
    db_session.flush()

    result = crud.link_google_id(db_session, user, "a-fresh-sub")

    assert result.google_id == "a-fresh-sub"
    db_session.refresh(user)
    assert user.google_id == "a-fresh-sub"


def test_returning_google_user_reuses_their_existing_row(client, db_session, monkeypatch):
    first = _complete_google_sign_in(client, monkeypatch, google_id="google-sub-repeat", email="repeat@example.com")
    first_user_id = get_session(first.cookies[SESSION_COOKIE_NAME])

    second = _complete_google_sign_in(client, monkeypatch, google_id="google-sub-repeat", email="repeat@example.com")
    second_user_id = get_session(second.cookies[SESSION_COOKIE_NAME])

    assert first_user_id == second_user_id
    assert db_session.query(User).filter(User.google_id == "google-sub-repeat").count() == 1


def test_callback_with_wrong_state_rejects_without_creating_a_session(client, monkeypatch):
    _fake_google_profile(monkeypatch, google_id="google-sub-csrf", email="csrf@example.com")

    client.get("/api/auth/google/login", follow_redirects=False)  # sets a real oauth_state cookie
    response = client.get(
        "/api/auth/google/callback?code=fake-auth-code&state=attacker-supplied-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:5173/login?error=google_sign_in_failed"
    assert SESSION_COOKIE_NAME not in response.cookies


def test_google_login_with_no_client_id_configured_redirects_cleanly(client, monkeypatch):
    """Never a raw 500/traceback (CLAUDE.md's error-handling rule) — a
    missing GOOGLE_CLIENT_ID is a real state before real credentials
    exist, and should degrade to the same /login?error= page as any other
    Google-side failure."""
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    response = client.get("/api/auth/google/login", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:5173/login?error=google_sign_in_failed"


def test_logout_destroys_the_session(client):
    from app.auth.session import create_session
    import uuid

    session_id = create_session(uuid.uuid4())
    assert get_session(session_id) is not None

    client.cookies.set(SESSION_COOKIE_NAME, session_id)
    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert get_session(session_id) is None
