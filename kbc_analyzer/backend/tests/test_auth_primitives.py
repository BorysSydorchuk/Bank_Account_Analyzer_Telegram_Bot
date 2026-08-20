"""S6-01 — users table CHECK constraint, session round-trip (real Redis,
db 15 per conftest.py), and get_current_user's three rejection paths
(missing/expired/tampered cookie). No route exists yet to exercise this
through — S6-01 is infrastructure only — so get_current_user is exercised
through a throwaway single-route FastAPI app built in this file, the same
dependency-override pattern the `client` fixture already uses against the
real app.
"""
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.auth.dependency import get_current_user
from app.auth.password import hash_password, verify_password
from app.auth.session import SESSION_COOKIE_NAME, create_session, destroy_session, get_session
from app.db import get_db
from app.models import User


def _make_user(db_session, **overrides) -> User:
    defaults = dict(email=f"{uuid.uuid4()}@example.com", password_hash=hash_password("correct horse battery"))
    defaults.update(overrides)
    user = User(**defaults)
    db_session.add(user)
    db_session.flush()
    return user


# ── users table CHECK constraint ────────────────────────────────────────────

def test_check_constraint_rejects_row_with_neither_auth_method(db_session):
    db_session.add(User(email="nobody@example.com"))
    with pytest.raises(IntegrityError, match="users_has_auth_method"):
        db_session.flush()


def test_check_constraint_allows_password_only_account(db_session):
    user = _make_user(db_session, email="password-only@example.com", google_id=None)
    assert user.id is not None


def test_check_constraint_allows_google_only_account(db_session):
    user = User(email="google-only@example.com", password_hash=None, google_id="google-sub-123")
    db_session.add(user)
    db_session.flush()
    assert user.id is not None


# ── password hashing ─────────────────────────────────────────────────────────

def test_password_hash_verifies_correct_and_rejects_wrong():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


# ── session round-trip (real Redis) ──────────────────────────────────────────

def test_session_round_trip():
    user_id = uuid.uuid4()
    session_id = create_session(user_id)

    assert get_session(session_id) == user_id

    destroy_session(session_id)
    assert get_session(session_id) is None


def test_get_session_returns_none_for_unknown_session_id():
    # A "tampered" cookie value in practice: an opaque random token mutated
    # into something else. It simply misses the Redis key.
    assert get_session("this-session-id-was-never-issued") is None


# ── get_current_user's three rejection paths ────────────────────────────────

def _whoami_app(db_session) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session

    @app.get("/whoami")
    def whoami(user: User = Depends(get_current_user)):
        return {"id": str(user.id), "email": user.email}

    return app


def test_get_current_user_rejects_missing_cookie(db_session):
    client = TestClient(_whoami_app(db_session))
    response = client.get("/whoami")
    assert response.status_code == 401


def test_get_current_user_rejects_expired_or_unknown_session(db_session):
    client = TestClient(_whoami_app(db_session))
    client.cookies.set(SESSION_COOKIE_NAME, "expired-or-never-existed")
    response = client.get("/whoami")
    assert response.status_code == 401


def test_get_current_user_rejects_tampered_session_id(db_session):
    user = _make_user(db_session)
    real_session_id = create_session(user.id)
    tampered = real_session_id[:-1] + ("A" if real_session_id[-1] != "A" else "B")

    client = TestClient(_whoami_app(db_session))
    client.cookies.set(SESSION_COOKIE_NAME, tampered)
    response = client.get("/whoami")

    assert response.status_code == 401
    destroy_session(real_session_id)


def test_get_current_user_accepts_valid_session(db_session):
    user = _make_user(db_session)
    session_id = create_session(user.id)

    client = TestClient(_whoami_app(db_session))
    client.cookies.set(SESSION_COOKIE_NAME, session_id)
    response = client.get("/whoami")

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": user.email}
    destroy_session(session_id)
