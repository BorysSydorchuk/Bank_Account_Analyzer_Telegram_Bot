"""S9-03: Stripe Checkout + webhook handling.

POST /api/billing/checkout deliberately writes nothing to our own database
— it only ever calls Stripe's API. Only a *confirmed* webhook event
(POST /api/billing/webhook) ever creates or updates a subscriptions row.
Rejected alternative: writing a pending row when checkout starts — that
would let an abandoned checkout leave stale state behind, and there's
nothing useful to show a user for a subscription that was never actually
paid for. See docs/tickets/S9-03-stripe-checkout-webhook-handling.md's KEY
DECISIONS for the full reasoning.

POST /api/billing/webhook is genuinely public (Stripe itself is the
caller, which has no session cookie) — Stripe's signature scheme
(app/stripe_client.py's STRIPE_WEBHOOK_SECRET) is what proves the caller
is really Stripe, not a session or an API key. This is the single most
security-sensitive endpoint in the billing feature: a forged event here
could grant free paid access to anyone who can guess the URL.
"""
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import crud
from ..auth.dependency import get_current_user
from ..db import get_db
from ..models import User
from ..schemas import CheckoutSessionOut
from ..stripe_client import get_stripe_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

# Subscription statuses that count as "paid" for tier purposes. `trialing`
# is included even though this app doesn't currently configure a trial
# period on the Price object — if one is ever added later, a trialing
# subscriber shouldn't read as free while their trial is active.
_PAID_STATUSES = {"active", "trialing"}


def _tier_for_status(status: str) -> str:
    return "paid" if status in _PAID_STATUSES else "free"


def _from_unix(timestamp: int | None) -> datetime | None:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp is not None else None


def _period_end_from_subscription(subscription) -> datetime | None:
    """Stripe moved `current_period_end` off the top-level Subscription
    object onto each subscription item as of a recent API version —
    confirmed empirically against this account's real pinned API version
    during this ticket's own live checkout test, where reading the
    top-level field came back silently None (not an error) rather than
    the real value. Falls back to the first line item's value since every
    subscription this app creates has exactly one item — a single paid
    price, no add-ons or metered components.
    """
    top_level = getattr(subscription, "current_period_end", None)
    if top_level is not None:
        return _from_unix(top_level)
    items = getattr(subscription, "items", None)
    if items is None or not items.data:
        return None
    return _from_unix(getattr(items.data[0], "current_period_end", None))


@router.post("/checkout", response_model=CheckoutSessionOut)
def create_checkout_session(current_user: User = Depends(get_current_user)) -> CheckoutSessionOut:
    """Creates a real Stripe-hosted Checkout Session for the S9-01 paid
    price and returns its URL for the frontend to redirect the browser to.
    `client_reference_id` is how the webhook handler below maps the
    resulting Stripe objects back to this specific user — Stripe's own
    documented mechanism for this, not something this app invented.
    """
    client = get_stripe_client()
    frontend_origin = os.environ["FRONTEND_ORIGIN"]
    session = client.v1.checkout.sessions.create({
        "mode": "subscription",
        "line_items": [{"price": os.environ["STRIPE_PRICE_ID_PRO"], "quantity": 1}],
        "client_reference_id": str(current_user.id),
        "customer_email": current_user.email,
        "success_url": f"{frontend_origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{frontend_origin}/billing/cancel",
    })
    return CheckoutSessionOut(checkout_url=session.url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """No auth dependency — see this module's docstring for why signature
    verification, not a session, is this endpoint's real gate. Reads the
    raw body directly (not a Pydantic model) because Stripe's signature is
    computed over the exact bytes sent; parsing and re-serializing first
    would break verification for a payload with different key ordering or
    whitespace than what Stripe actually signed.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ["STRIPE_WEBHOOK_SECRET"]

    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        logger.warning("Rejected a webhook call with an invalid or missing Stripe signature")
        raise HTTPException(status_code=400, detail="Invalid signature.")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db, data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(db, data)
    # Any other event type is acknowledged (200, so Stripe doesn't retry)
    # but otherwise ignored — this app only subscribes to what S9-03
    # actually needs, not everything in the account's event stream.

    return {"received": True}


def _handle_checkout_completed(db: Session, session: dict) -> None:
    # Real Stripe event objects (stripe.StripeObject) are NOT dicts — no
    # .get(), only attribute access and __getitem__ — hence getattr(...,
    # None) rather than session.get(...) throughout this module.
    raw_user_id = getattr(session, "client_reference_id", None)
    if not raw_user_id:
        logger.warning("checkout.session.completed with no client_reference_id — ignoring")
        return
    try:
        user_id = UUID(raw_user_id)
    except ValueError:
        logger.warning("checkout.session.completed with an unparseable client_reference_id — ignoring")
        return

    # The Checkout Session itself doesn't carry the subscription's status/
    # period fields — only customer.subscription.* events do — so the real
    # Subscription object is fetched here rather than guessed at.
    client = get_stripe_client()
    subscription = client.v1.subscriptions.retrieve(session.subscription)

    crud.upsert_subscription_from_checkout(
        db,
        user_id=user_id,
        stripe_customer_id=session.customer,
        stripe_subscription_id=subscription.id,
        tier=_tier_for_status(subscription.status),
        status=subscription.status,
        current_period_end=_period_end_from_subscription(subscription),
    )


def _handle_subscription_updated(db: Session, subscription: dict) -> None:
    crud.update_subscription_by_stripe_subscription_id(
        db,
        stripe_subscription_id=subscription.id,
        tier=_tier_for_status(subscription.status),
        status=subscription.status,
        current_period_end=_period_end_from_subscription(subscription),
    )


def _handle_subscription_deleted(db: Session, subscription: dict) -> None:
    crud.update_subscription_by_stripe_subscription_id(
        db,
        stripe_subscription_id=subscription.id,
        tier="free",
        status="canceled",
        canceled_at=datetime.now(timezone.utc),
    )


def _handle_payment_failed(db: Session, invoice: dict) -> None:
    subscription_id = getattr(invoice, "subscription", None)
    if not subscription_id:
        # An invoice can fail for something other than a subscription
        # renewal (e.g. a one-off charge) — nothing in this table to update.
        return
    crud.update_subscription_by_stripe_subscription_id(
        db,
        stripe_subscription_id=subscription_id,
        status="past_due",
    )
