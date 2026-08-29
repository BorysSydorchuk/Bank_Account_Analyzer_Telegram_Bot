"""S9-03 — POST /api/billing/webhook: signature verification and the four
event types this app actually handles. Every payload here is a real,
correctly-shaped Stripe event body, signed the same way Stripe itself
signs a real delivery (HMAC-SHA256 over "{timestamp}.{payload}") — this
exercises the real `stripe.Webhook.construct_event` verification path, not
a mocked one. Only the outbound call to Stripe (`client.subscriptions
.retrieve`, needed by checkout.session.completed) is faked, via
fixtures/fake_stripe.py.
"""
import hashlib
import hmac
import json
import time
import uuid

from app import crud
from app.models import User

WEBHOOK_SECRET = "whsec_test_fake_secret_for_tests_only"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    timestamp = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _post_webhook(client, event: dict, *, secret: str = WEBHOOK_SECRET, timestamp: int | None = None):
    payload = json.dumps(event).encode()
    signature = _sign(payload, secret=secret, timestamp=timestamp)
    return client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


# ── Signature verification — the security-critical path ────────────────────


def test_webhook_rejects_missing_signature(client):
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}).encode()
    response = client.post("/api/billing/webhook", content=payload, headers={"content-type": "application/json"})
    assert response.status_code == 400


def test_webhook_rejects_forged_signature(client):
    """A real adversarial case: an attacker who knows the payload shape but
    not the signing secret cannot forge a valid signature — this is what
    stops "anyone can grant themselves a free paid subscription" (the
    ticket's own stated stakes for this endpoint)."""
    event = {"type": "checkout.session.completed", "data": {"object": {}}}
    payload = json.dumps(event).encode()
    forged_signature = _sign(payload, secret="wrong_secret_an_attacker_might_guess")
    response = client.post(
        "/api/billing/webhook",
        content=payload,
        headers={"stripe-signature": forged_signature, "content-type": "application/json"},
    )
    assert response.status_code == 400


def test_webhook_rejects_expired_timestamp_replay(client):
    """Stripe's own replay-attack defense: a signature computed against a
    stale timestamp (default tolerance is 5 minutes) is rejected even if
    the HMAC itself is otherwise valid for that (payload, timestamp) pair —
    protects against a captured, previously-valid request being resent."""
    event = {"type": "checkout.session.completed", "data": {"object": {}}}
    payload = json.dumps(event).encode()
    ancient_timestamp = int(time.time()) - 3600
    response = _post_webhook(client, event, timestamp=ancient_timestamp)
    assert response.status_code == 400


# ── Real event handling ─────────────────────────────────────────────────────


def test_checkout_completed_creates_paid_subscription(client, db_session, fake_stripe_client):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    fake_stripe_client.add_subscription(
        "sub_test_1", status="active", current_period_end=1893456000
    )
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "customer": "cus_test_1",
                "subscription": "sub_test_1",
                "client_reference_id": str(user.id),
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200

    subscription = crud.get_subscription(db_session, user.id)
    assert subscription.tier == "paid"
    assert subscription.status == "active"
    assert subscription.stripe_customer_id == "cus_test_1"
    assert subscription.stripe_subscription_id == "sub_test_1"
    assert crud.get_user_tier(db_session, user.id) == "paid"


def test_checkout_completed_reads_period_end_from_subscription_item(client, db_session, fake_stripe_client):
    """Regression test for a real bug found during this ticket's own live
    checkout test: this account's real, current Stripe API version has
    moved current_period_end off the top-level Subscription object onto
    each subscription item — a top-level read silently returns None
    instead of raising, so this needs its own explicit test rather than
    relying on the happy-path test above (which uses top-level
    current_period_end and would not catch a regression here)."""
    from types import SimpleNamespace

    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    fake_stripe_client.add_subscription(
        "sub_test_item_level",
        status="active",
        current_period_end=None,
        items=SimpleNamespace(data=[SimpleNamespace(current_period_end=1893456000)]),
    )
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_item_level",
                "customer": "cus_test_item_level",
                "subscription": "sub_test_item_level",
                "client_reference_id": str(user.id),
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200

    subscription = crud.get_subscription(db_session, user.id)
    assert subscription.current_period_end is not None


def test_checkout_completed_with_unknown_user_id_is_ignored_not_500(client, db_session, fake_stripe_client):
    """A malformed/unexpected client_reference_id must never crash the
    endpoint — Stripe retries on any non-2xx, and a 500 here would just
    make it retry a payload this app can never satisfy."""
    fake_stripe_client.add_subscription("sub_test_2", status="active", current_period_end=None)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_2",
                "customer": "cus_test_2",
                "subscription": "sub_test_2",
                "client_reference_id": "not-a-uuid",
            }
        },
    }
    response = _post_webhook(client, event)
    assert response.status_code == 200


def test_subscription_updated_changes_status_and_period(client, db_session, fake_stripe_client):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    fake_stripe_client.add_subscription("sub_test_3", status="active", current_period_end=1893456000)
    _post_webhook(client, {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_3", "customer": "cus_test_3", "subscription": "sub_test_3", "client_reference_id": str(user.id)}},
    })

    response = _post_webhook(client, {
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_test_3", "status": "past_due", "current_period_end": 1896134400}},
    })
    assert response.status_code == 200

    subscription = crud.get_subscription(db_session, user.id)
    assert subscription.status == "past_due"
    # past_due isn't in the paid-status set — tier correctly reflects that.
    assert subscription.tier == "free"


def test_subscription_deleted_reverts_to_free_tier(client, db_session, fake_stripe_client):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    fake_stripe_client.add_subscription("sub_test_4", status="active", current_period_end=1893456000)
    _post_webhook(client, {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_4", "customer": "cus_test_4", "subscription": "sub_test_4", "client_reference_id": str(user.id)}},
    })
    assert crud.get_user_tier(db_session, user.id) == "paid"

    response = _post_webhook(client, {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_test_4", "status": "canceled"}},
    })
    assert response.status_code == 200

    subscription = crud.get_subscription(db_session, user.id)
    assert subscription.tier == "free"
    assert subscription.status == "canceled"
    assert subscription.canceled_at is not None
    assert crud.get_user_tier(db_session, user.id) == "free"


def test_payment_failed_marks_subscription_past_due(client, db_session, fake_stripe_client):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    fake_stripe_client.add_subscription("sub_test_5", status="active", current_period_end=1893456000)
    _post_webhook(client, {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_5", "customer": "cus_test_5", "subscription": "sub_test_5", "client_reference_id": str(user.id)}},
    })

    response = _post_webhook(client, {
        "type": "invoice.payment_failed",
        "data": {"object": {"id": "in_test_5", "subscription": "sub_test_5"}},
    })
    assert response.status_code == 200

    subscription = crud.get_subscription(db_session, user.id)
    assert subscription.status == "past_due"


def test_payment_failed_for_unknown_subscription_is_a_safe_no_op(client, db_session):
    """An invoice.payment_failed event for a subscription this app has no
    row for (e.g. Stripe test data unrelated to a real checkout) must not
    error — see crud.update_subscription_by_stripe_subscription_id's
    docstring for why a 500 here would be actively harmful."""
    response = _post_webhook(client, {
        "type": "invoice.payment_failed",
        "data": {"object": {"id": "in_test_unknown", "subscription": "sub_never_seen"}},
    })
    assert response.status_code == 200


def test_unhandled_event_type_is_acknowledged_not_processed(client):
    """Any event type outside this app's four handled ones still gets a
    200 — Stripe retries indefinitely on non-2xx, and this app only
    subscribes to what S9-03 actually needs."""
    response = _post_webhook(client, {
        "type": "customer.updated",
        "data": {"object": {"id": "cus_irrelevant"}},
    })
    assert response.status_code == 200
