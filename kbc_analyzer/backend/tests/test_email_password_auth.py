"""S6-04 — /api/auth/register, /api/auth/login, /api/auth/set-password.
Real Postgres/Redis throughout — nothing external to fake here (unlike
Google OAuth), so no monkeypatching needed.
"""
import pytest

from app import crud
from app.auth.session import SESSION_COOKIE_NAME, create_session, get_session
from app.models import BetaInvite, User
from app.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """slowapi's in-memory limiter is keyed on remote address, and
    Starlette's TestClient reports a fixed address ("testclient") for
    every request — meaning every test in this file would otherwise share
    one rate-limit bucket across the whole pytest run, not just within
    each test. Reset before each test so LOGIN_RATE_LIMIT/
    REGISTER_RATE_LIMIT only ever apply to calls *within* the test that's
    deliberately exercising them.
    """
    limiter.reset()
    yield


def _invite(db_session, email: str) -> None:
    """S8-06: register now requires an unused beta invite. Every test
    below that exercises a real /api/auth/register call needs one seeded
    first — this stays a plain helper, not a fixture, so each test's
    invited email is visible right at its own call site."""
    db_session.add(BetaInvite(email=email.lower()))
    db_session.flush()


def test_register_creates_user_and_session(client, db_session):
    _invite(db_session, "newuser@example.com")
    response = client.post("/api/auth/register", json={"email": "newuser@example.com", "password": "correct-horse"})

    assert response.status_code == 201
    assert response.json()["email"] == "newuser@example.com"
    assert SESSION_COOKIE_NAME in response.cookies

    user = db_session.query(User).filter(User.email == "newuser@example.com").one()
    assert user.password_hash is not None
    assert user.google_id is None
    assert get_session(response.cookies[SESSION_COOKIE_NAME]) == user.id


def test_register_rejects_duplicate_email(client, db_session):
    db_session.add(User(email="taken@example.com", password_hash="irrelevant"))
    db_session.flush()

    response = client.post("/api/auth/register", json={"email": "taken@example.com", "password": "correct-horse"})

    assert response.status_code == 400
    assert SESSION_COOKIE_NAME not in response.cookies


@pytest.mark.parametrize("password", ["short", "1234567"])
def test_register_rejects_a_password_under_the_minimum_length(client, db_session, password):
    _invite(db_session, "weak@example.com")
    response = client.post("/api/auth/register", json={"email": "weak@example.com", "password": password})

    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


def test_register_rejects_an_uninvited_email(client, db_session):
    response = client.post(
        "/api/auth/register", json={"email": "never-invited@example.com", "password": "correct-horse-battery"}
    )

    assert response.status_code == 403
    assert "invite-only" in response.json()["detail"]
    assert SESSION_COOKIE_NAME not in response.cookies
    assert db_session.query(User).filter(User.email == "never-invited@example.com").one_or_none() is None


def test_register_consumes_the_invite_so_it_cannot_be_reused(client, db_session):
    _invite(db_session, "onetime@example.com")

    first = client.post("/api/auth/register", json={"email": "onetime@example.com", "password": "correct-horse-1"})
    assert first.status_code == 201

    # Deleting the account (simulating a fresh signup attempt against the
    # same, already-consumed invite) rather than reusing the same email
    # while it's taken — isolates "was the invite itself burned" from the
    # already-covered duplicate-email case above.
    db_session.query(User).filter(User.email == "onetime@example.com").delete()
    db_session.flush()

    second = client.post("/api/auth/register", json={"email": "onetime@example.com", "password": "correct-horse-2"})
    assert second.status_code == 403


def test_register_and_login_round_trip(client, db_session):
    _invite(db_session, "roundtrip@example.com")
    register_response = client.post(
        "/api/auth/register", json={"email": "roundtrip@example.com", "password": "correct-horse-battery"}
    )
    assert register_response.status_code == 201

    # A fresh client — logging in shouldn't depend on register's own session
    # cookie still being attached.
    login_response = client.post(
        "/api/auth/login", json={"email": "roundtrip@example.com", "password": "correct-horse-battery"}
    )

    assert login_response.status_code == 200
    assert login_response.json()["email"] == "roundtrip@example.com"
    assert SESSION_COOKIE_NAME in login_response.cookies


def test_login_fails_with_wrong_password(client, db_session):
    _invite(db_session, "realaccount@example.com")
    client.post("/api/auth/register", json={"email": "realaccount@example.com", "password": "the-real-password"})

    response = client.post("/api/auth/login", json={"email": "realaccount@example.com", "password": "wrong-guess"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."
    assert SESSION_COOKIE_NAME not in response.cookies


def test_login_fails_with_nonexistent_email_with_the_identical_message(client):
    response = client.post("/api/auth/login", json={"email": "never-registered@example.com", "password": "anything"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_fails_for_a_google_only_account_with_the_identical_message(client, db_session):
    """A Google-only account (no password_hash) trying /login shouldn't
    get a different error than a wrong password or a nonexistent email —
    all three are exactly the same enumeration-safe shape."""
    user = User(email="google-only@example.com", google_id="google-sub-no-password")
    db_session.add(user)
    db_session.flush()

    response = client.post("/api/auth/login", json={"email": "google-only@example.com", "password": "anything"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_set_password_requires_authentication(client):
    response = client.post("/api/auth/set-password", json={"password": "a-new-password"})
    assert response.status_code == 401


def test_set_password_lets_a_google_only_account_add_password_sign_in(client, db_session):
    user = User(email="adding-password@example.com", google_id="google-sub-adding-password")
    db_session.add(user)
    db_session.flush()
    session_id = create_session(user.id)

    client.cookies.set(SESSION_COOKIE_NAME, session_id)
    set_response = client.post("/api/auth/set-password", json={"password": "brand-new-password"})
    assert set_response.status_code == 204

    # Drop the session cookie and prove the password actually works via
    # the normal login path, not just that the database row changed.
    client.cookies.delete(SESSION_COOKIE_NAME)
    login_response = client.post(
        "/api/auth/login", json={"email": "adding-password@example.com", "password": "brand-new-password"}
    )

    assert login_response.status_code == 200


def test_login_rate_limit_returns_429_after_too_many_attempts(client, db_session):
    _invite(db_session, "ratelimited@example.com")
    client.post("/api/auth/register", json={"email": "ratelimited@example.com", "password": "the-real-password"})

    responses = [
        client.post("/api/auth/login", json={"email": "ratelimited@example.com", "password": "wrong"})
        for _ in range(6)
    ]

    assert [r.status_code for r in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
