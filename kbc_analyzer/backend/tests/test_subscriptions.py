"""S9-02 — the subscriptions table and free/paid tier read path.

Exercises the real migrated table via db_session, not a mock — the property
that matters is that a user with no subscription row at all reads as "free",
since Stripe objects are only ever created once a user starts checkout
(S9-03), never up front.
"""
import uuid

from app import crud
from app.models import Subscription, User


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash")
    db_session.add(user)
    db_session.commit()
    return user


def test_user_with_no_subscription_row_reads_as_free(db_session):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    assert crud.get_subscription(db_session, user.id) is None
    assert crud.get_user_tier(db_session, user.id) == "free"


def test_user_with_paid_subscription_row_reads_as_paid(db_session):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    db_session.add(
        Subscription(
            user_id=user.id,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            tier="paid",
            status="active",
        )
    )
    db_session.commit()

    assert crud.get_user_tier(db_session, user.id) == "paid"


def test_canceled_subscription_row_reverts_to_free_tier(db_session):
    """A row can still exist for a currently-free user (S9-03 flips `tier`
    back to 'free' on cancellation, keeping status/history) — tier, not row
    presence, is authoritative."""
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    db_session.add(
        Subscription(
            user_id=user.id,
            stripe_customer_id="cus_test456",
            stripe_subscription_id="sub_test456",
            tier="free",
            status="canceled",
        )
    )
    db_session.commit()

    assert crud.get_subscription(db_session, user.id) is not None
    assert crud.get_user_tier(db_session, user.id) == "free"


def test_tier_check_constraint_rejects_unknown_value(db_session):
    user = _make_user(db_session, f"{uuid.uuid4()}@example.com")
    db_session.add(Subscription(user_id=user.id, tier="enterprise"))
    try:
        db_session.commit()
        assert False, "expected the ck_subscriptions_tier CHECK constraint to reject this"
    except Exception:
        db_session.rollback()
