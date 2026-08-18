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

from app.models import Budget, Insight, Transaction

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
def transaction_factory():
    def _make(**overrides) -> Transaction:
        defaults = dict(
            id=uuid.uuid4(),
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
        return Transaction(**defaults)

    return _make


@pytest.fixture
def budget_factory():
    def _make(**overrides) -> Budget:
        defaults = dict(
            id=uuid.uuid4(),
            user_id=None,
            category="Groceries",
            amount=Decimal("250.00"),
            period="monthly",
        )
        defaults.update(overrides)
        return Budget(**defaults)

    return _make


@pytest.fixture
def insight_factory():
    def _make(**overrides) -> Insight:
        defaults = dict(
            id=uuid.uuid4(),
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
