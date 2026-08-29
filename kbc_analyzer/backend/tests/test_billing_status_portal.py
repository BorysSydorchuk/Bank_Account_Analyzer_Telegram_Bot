"""S9-05 — GET /api/billing/status and POST /api/billing/portal, the two
new endpoints the Settings page reads from and posts to.
"""
import uuid

from app import crud
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models import Subscription, User


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


def _login(client, db_session, email: str) -> User:
    user = _make_user(db_session, email)
    client.cookies.update({SESSION_COOKIE_NAME: create_session(user.id)})
    return user


def test_status_requires_authentication(client):
    assert client.get("/api/billing/status").status_code == 401


def test_status_free_user_billing_off(client, db_session):
    _login(client, db_session, f"{uuid.uuid4()}@example.com")
    body = client.get("/api/billing/status").json()
    assert body == {"billing_enabled": False, "tier": "free", "status": None}


def test_status_free_user_billing_on(client, db_session):
    crud.set_app_setting(db_session, "BILLING_ENABLED", "true")
    _login(client, db_session, f"{uuid.uuid4()}@example.com")
    body = client.get("/api/billing/status").json()
    assert body == {"billing_enabled": True, "tier": "free", "status": None}


def test_status_paid_user_reports_tier_and_status(client, db_session):
    user = _login(client, db_session, f"{uuid.uuid4()}@example.com")
    db_session.add(Subscription(user_id=user.id, tier="paid", status="active", stripe_customer_id="cus_test_1"))
    db_session.commit()

    body = client.get("/api/billing/status").json()
    assert body["tier"] == "paid"
    assert body["status"] == "active"


def test_portal_requires_authentication(client):
    assert client.post("/api/billing/portal").status_code == 401


def test_portal_rejects_user_with_no_billing_account(client, db_session):
    """A free user who's never touched checkout has no Stripe customer to
    manage — a clear 400, not a confusing Stripe error surfaced raw."""
    _login(client, db_session, f"{uuid.uuid4()}@example.com")
    response = client.post("/api/billing/portal")
    assert response.status_code == 400


def test_portal_creates_real_shaped_session_for_paid_user(client, db_session, fake_stripe_client):
    user = _login(client, db_session, f"{uuid.uuid4()}@example.com")
    db_session.add(Subscription(user_id=user.id, tier="paid", status="active", stripe_customer_id="cus_test_2"))
    db_session.commit()

    response = client.post("/api/billing/portal")
    assert response.status_code == 200
    assert response.json()["portal_url"].startswith("https://billing.stripe.com/")

    params = fake_stripe_client.created_portal_params[0]
    assert params["customer"] == "cus_test_2"


def test_portal_available_even_with_billing_off(client, db_session, fake_stripe_client):
    """A real paying customer must always be able to manage their own real
    Stripe subscription — the kill switch only gates usage-limit
    enforcement (S9-04), not access to a user's own billing management."""
    user = _login(client, db_session, f"{uuid.uuid4()}@example.com")
    db_session.add(Subscription(user_id=user.id, tier="paid", status="active", stripe_customer_id="cus_test_3"))
    db_session.commit()
    # BILLING_ENABLED defaults to 'false' — no crud.set_app_setting call.

    response = client.post("/api/billing/portal")
    assert response.status_code == 200
