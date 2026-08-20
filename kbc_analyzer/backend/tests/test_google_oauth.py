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


def test_google_sign_in_links_to_an_existing_password_account(client, db_session, monkeypatch):
    existing = User(email="already-registered@example.com", password_hash="not-a-real-hash")
    db_session.add(existing)
    db_session.flush()
    existing_id = existing.id

    response = _complete_google_sign_in(
        client, monkeypatch, google_id="google-sub-linking", email="already-registered@example.com"
    )

    assert response.status_code == 303
    # Still exactly one user row for this email — linked, not duplicated.
    matches = db_session.query(User).filter(User.email == "already-registered@example.com").all()
    assert len(matches) == 1
    linked = matches[0]
    assert linked.id == existing_id
    assert linked.google_id == "google-sub-linking"
    assert linked.password_hash == "not-a-real-hash"  # untouched by linking


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
