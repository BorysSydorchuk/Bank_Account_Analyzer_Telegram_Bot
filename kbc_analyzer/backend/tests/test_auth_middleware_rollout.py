"""S6-05 — the first two real routes wired to get_current_user
(GET /api/categories, GET /api/budgets), plus GET /api/auth/me. Real
scoping is the point here, not just gating: two different users get two
different (Category name, Budget) sets, even when they share a category
name — proven by creating both and checking each user only ever sees
their own.
"""
import uuid
from decimal import Decimal

import pytest

from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models import Budget, Category, User


def _authenticated_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def _login_as(client, user: User) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))


# ── GET /api/categories ──────────────────────────────────────────────────


def test_get_categories_requires_authentication(client):
    response = client.get("/api/categories")
    assert response.status_code == 401


def test_get_categories_returns_only_the_authenticated_users_categories(client, db_session):
    user_a = _authenticated_user(db_session, "user-a@example.com")
    user_b = _authenticated_user(db_session, "user-b@example.com")
    # Same name, both users — the composite (user_id, name) primary key
    # (S6-02) makes this legal; scoping is what keeps them from mixing up.
    db_session.add(Category(user_id=user_a.id, name="Groceries", color="#111111"))
    db_session.add(Category(user_id=user_b.id, name="Groceries", color="#222222"))
    db_session.add(Category(user_id=user_b.id, name="Only Bs Category", color="#333333"))
    db_session.flush()

    _login_as(client, user_a)
    response = client.get("/api/categories")

    assert response.status_code == 200
    # The 7 seed categories (fbde2dbcc78d) already belong to the S6-02
    # bootstrap user in this test database, not user_a — so user_a sees
    # exactly the one category created for them above, nothing seeded and
    # nothing belonging to user_b.
    names_and_colors = {(c["name"], c["color"]) for c in response.json()}
    assert names_and_colors == {("Groceries", "#111111")}


# ── GET /api/budgets ──────────────────────────────────────────────────────


def test_get_budgets_requires_authentication(client):
    response = client.get("/api/budgets")
    assert response.status_code == 401


def test_get_budgets_returns_only_the_authenticated_users_budgets(client, db_session):
    user_a = _authenticated_user(db_session, "budget-user-a@example.com")
    user_b = _authenticated_user(db_session, "budget-user-b@example.com")
    # budgets.category is a composite FK -> categories(user_id, name)
    # (S6-02) — each user needs their own "Groceries" row before a budget
    # under that name can exist for them.
    db_session.add(Category(user_id=user_a.id, name="Groceries", color="#111111"))
    db_session.add(Category(user_id=user_b.id, name="Groceries", color="#222222"))
    db_session.flush()
    db_session.add(Budget(id=uuid.uuid4(), user_id=user_a.id, category="Groceries", amount=Decimal("111.00")))
    db_session.add(Budget(id=uuid.uuid4(), user_id=user_b.id, category="Groceries", amount=Decimal("999.00")))
    db_session.flush()

    _login_as(client, user_a)
    response = client.get("/api/budgets")

    assert response.status_code == 200
    amounts = [b["amount"] for b in response.json()]
    assert amounts == [111.0]


# ── GET /api/auth/me ──────────────────────────────────────────────────────


def test_get_me_requires_authentication(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_get_me_returns_the_authenticated_user(client, db_session):
    user = _authenticated_user(db_session, "whoami@example.com")
    _login_as(client, user)

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": "whoami@example.com"}
