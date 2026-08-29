"""S9-03 — POST /api/billing/checkout. Confirms it calls Stripe correctly
(via the faked client — see fixtures/fake_stripe.py) and, per this
ticket's key decision, writes nothing to our own database: only a
confirmed webhook event ever creates a subscriptions row.
"""
import uuid

from app import crud
from app.models import User


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


def _login_session_cookie(client, db_session, email: str) -> tuple[User, dict]:
    from app.auth.session import SESSION_COOKIE_NAME, create_session

    user = _make_user(db_session, email)
    session_id = create_session(user.id)
    return user, {SESSION_COOKIE_NAME: session_id}


def test_checkout_requires_authentication(client):
    response = client.post("/api/billing/checkout")
    assert response.status_code == 401


def test_checkout_creates_real_shaped_session_and_writes_no_subscription_row(
    client, db_session, fake_stripe_client
):
    user, cookies = _login_session_cookie(client, db_session, f"{uuid.uuid4()}@example.com")
    client.cookies.update(cookies)

    response = client.post("/api/billing/checkout")
    assert response.status_code == 200
    assert response.json()["checkout_url"].startswith("https://checkout.stripe.com/")

    params = fake_stripe_client.created_checkout_params[0]
    assert params["mode"] == "subscription"
    assert params["client_reference_id"] == str(user.id)
    assert params["customer_email"] == user.email

    # Key decision under test: starting checkout must not create a row —
    # only a confirmed webhook event does (see app/routers/billing.py's
    # module docstring).
    assert crud.get_subscription(db_session, user.id) is None
    assert crud.get_user_tier(db_session, user.id) == "free"
