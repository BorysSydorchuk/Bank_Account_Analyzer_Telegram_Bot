"""S8-09 — new accounts get real default categories, atomically with
creation, and budget creation rejects an unknown category cleanly instead
of hitting a raw FK IntegrityError.
"""
from app import crud
from app.agents.categorization import CATEGORIES
from app.models import BetaInvite


def test_create_user_from_password_seeds_default_categories(db_session):
    user = crud.create_user_from_password(db_session, "seeded-pw@example.com", "irrelevant-hash")

    categories = crud.list_categories(db_session, user.id)
    assert {c.name for c in categories} == set(CATEGORIES)
    assert all(c.source == "seed" and c.is_custom is False for c in categories)


def test_create_user_from_google_seeds_default_categories(db_session):
    user = crud.create_user_from_google(db_session, "google-sub-seeded", "seeded-google@example.com", None)

    categories = crud.list_categories(db_session, user.id)
    assert {c.name for c in categories} == set(CATEGORIES)


def test_register_endpoint_gives_a_fresh_account_working_categories(client, db_session):
    db_session.add(BetaInvite(email="freshcategorize@example.com"))
    db_session.flush()

    response = client.post(
        "/api/auth/register", json={"email": "freshcategorize@example.com", "password": "a-real-password-123"}
    )
    assert response.status_code == 201, response.text

    categories_response = client.get("/api/categories")
    assert categories_response.status_code == 200
    assert {c["name"] for c in categories_response.json()} == set(CATEGORIES)


def test_create_budget_rejects_an_unknown_category_cleanly(client, db_session):
    db_session.add(BetaInvite(email="budgettest@example.com"))
    db_session.flush()
    register_response = client.post(
        "/api/auth/register", json={"email": "budgettest@example.com", "password": "a-real-password-123"}
    )
    assert register_response.status_code == 201, register_response.text

    response = client.post("/api/budgets", json={"category": "Not A Real Category", "amount": 100})

    assert response.status_code == 400
    assert "Not A Real Category" in response.json()["detail"]
    # No IntegrityError raised, no partial write — the real seeded
    # categories are unaffected by the rejected attempt.
    user_id = register_response.json()["id"]
    assert {c.name for c in crud.list_categories(db_session, user_id)} == set(CATEGORIES)


def test_create_budget_succeeds_for_a_real_seeded_category(client, db_session):
    db_session.add(BetaInvite(email="budgetok@example.com"))
    db_session.flush()
    register_response = client.post(
        "/api/auth/register", json={"email": "budgetok@example.com", "password": "a-real-password-123"}
    )
    assert register_response.status_code == 201, register_response.text

    response = client.post("/api/budgets", json={"category": "Groceries", "amount": 250})

    assert response.status_code == 201, response.text
    assert response.json()["category"] == "Groceries"
