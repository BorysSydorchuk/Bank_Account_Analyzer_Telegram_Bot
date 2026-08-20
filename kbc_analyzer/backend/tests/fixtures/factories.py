"""Factory helpers for the ORM models tests write most often. Data here is
invented but realistic — Belgian merchants, EUR amounts, plausible dates —
never Borys's real bank data (TESTER.md prime directive 3).

Each fixture returns a builder function rather than a fixed object, so a
test can override exactly the field it cares about:

    def test_x(db_session, transaction_factory):
        txn = transaction_factory(amount=Decimal("-12.50"), manually_edited=True)
        db_session.add(txn)
        db_session.flush()
"""
import itertools
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import Budget, Category, Insight, Transaction, User

# A small, varied pool — enough to make list-of-transactions tests look like
# real data without needing a full merchant database.
_BELGIAN_MERCHANTS = [
    "Delhaize Ixelles",
    "Colruyt Anderlecht",
    "STIB-MIVB",
    "Proximus",
    "Carrefour Express Etterbeek",
    "Kinepolis Brussels",
    "Exki Louise",
]

_counter = itertools.count(1)


def _next_external_id() -> str:
    return f"test-ext-{next(_counter):06d}"


@pytest.fixture
def test_user(db_session):
    """A real, flushed User row (S6-06) — every table's user_id is NOT NULL
    now, so every factory below needs a real row to point at, not just a
    UUID. Function-scoped like db_session, so it rolls back with everything
    else the test wrote."""
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="test-fixture-hash")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def transaction_factory(db_session, test_user):
    def _make(**overrides) -> Transaction:
        defaults = dict(
            id=uuid.uuid4(),
            user_id=test_user.id,
            account_id="test-account-uid",
            external_id=_next_external_id(),
            booking_date=date(2026, 8, 5),
            amount=Decimal("-23.45"),
            currency="EUR",
            description=_BELGIAN_MERCHANTS[next(_counter) % len(_BELGIAN_MERCHANTS)],
            category=None,
            subcategory=None,
            manually_edited=False,
            raw_data={},
        )
        defaults.update(overrides)
        # transactions.category is a composite FK -> categories(user_id, name)
        # (S6-02) — a test overriding category to a real name needs test_user
        # to actually own a row under that name first, same reasoning as
        # budget_factory's own get_or_create below.
        if defaults["category"] is not None:
            key = (defaults["user_id"], defaults["category"])
            if db_session.get(Category, key) is None:
                db_session.add(Category(user_id=key[0], name=key[1], color="#64748B"))
                db_session.flush()
        return Transaction(**defaults)

    return _make


@pytest.fixture
def budget_factory(db_session, test_user):
    def _make(**overrides) -> Budget:
        defaults = dict(
            id=uuid.uuid4(),
            user_id=test_user.id,
            category="Groceries",
            amount=Decimal("250.00"),
            period="monthly",
        )
        defaults.update(overrides)
        # budgets.category is a composite FK -> categories(user_id, name)
        # (S6-02) — test_user needs their own row under this exact name
        # before a budget can reference it. get_or_create rather than
        # always adding: a test overriding category to the same name twice
        # (or two budget_factory() calls for the same category) would
        # otherwise try to insert the same (user_id, name) pair twice in
        # one flush.
        existing = db_session.get(Category, (defaults["user_id"], defaults["category"]))
        if existing is None:
            db_session.add(Category(user_id=defaults["user_id"], name=defaults["category"], color="#64748B"))
            db_session.flush()
        return Budget(**defaults)

    return _make


@pytest.fixture
def insight_factory(test_user):
    def _make(**overrides) -> Insight:
        defaults = dict(
            id=uuid.uuid4(),
            user_id=test_user.id,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            type="summary",
            title="Spending steady this month",
            body="Groceries and transport made up most of August's spending.",
            severity="info",
            provider="fake",
            generated_at=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        return Insight(**defaults)

    return _make
