"""S5-04 — sync idempotency / dedup invariant, plus the S4-01 regression test
(account_id churn causing duplicate inserts). crud.upsert_transactions is the
single unit under test for all of these — it's the only place a transaction
is ever inserted.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app import crud
from app.models import Transaction


def _raw_tx(external_id: str, description: str = "Delhaize Ixelles", amount: str = "-12.34", day: str = "2026-08-05") -> dict:
    """A transaction dict shaped like what eb_service.fetch_transactions
    returns — what crud.upsert_transactions actually receives, not an ORM
    object."""
    return {"id": external_id, "date": day, "amount": amount, "description": description}


def test_same_external_id_is_never_inserted_twice(db_session):
    stored_1, dupes_1 = crud.upsert_transactions(db_session, "account-a", [_raw_tx("ext-001")])
    stored_2, dupes_2 = crud.upsert_transactions(db_session, "account-a", [_raw_tx("ext-001")])

    assert (stored_1, dupes_1) == (1, 0)
    assert (stored_2, dupes_2) == (0, 1)

    rows = db_session.execute(select(Transaction).where(Transaction.external_id == "ext-001")).scalars().all()
    assert len(rows) == 1


def test_dedup_holds_even_when_account_id_differs_S4_01_regression(db_session):
    """The exact S4-01 production incident: Enable Banking issues a new
    internal account_id on every reconnect, but external_id is stable for
    the same real-world transaction. A naive (account_id, external_id)
    composite key treats the second sync as brand new and duplicates it —
    78 duplicate pairs accumulated this way in production before the fix.
    Regression: the same external_id synced under two different account_ids
    must still collapse to one row.
    """
    stored_1, _ = crud.upsert_transactions(db_session, "account-before-reconnect", [_raw_tx("ext-stable-ref")])
    stored_2, dupes_2 = crud.upsert_transactions(db_session, "account-after-reconnect", [_raw_tx("ext-stable-ref")])

    assert stored_1 == 1
    assert stored_2 == 0
    assert dupes_2 == 1

    rows = db_session.execute(select(Transaction).where(Transaction.external_id == "ext-stable-ref")).scalars().all()
    assert len(rows) == 1
    # account_id is first-seen, never overwritten by a later reconnect's sync.
    assert rows[0].account_id == "account-before-reconnect"


def test_resync_of_already_synced_range_stores_zero_rows(db_session):
    batch = [_raw_tx("ext-100"), _raw_tx("ext-101"), _raw_tx("ext-102")]
    crud.upsert_transactions(db_session, "account-a", batch)

    stored, duplicates_skipped = crud.upsert_transactions(db_session, "account-a", batch)

    assert stored == 0
    assert duplicates_skipped == 3


def test_conflicting_update_refreshes_amount_and_description(db_session):
    """Not a duplicate-count assertion, but proves the ON CONFLICT DO UPDATE
    path actually updates the mutable fields (amount/description/date can
    legitimately change between the bank's pending and booked views of the
    same transaction) rather than silently ignoring the second sync."""
    crud.upsert_transactions(db_session, "account-a", [_raw_tx("ext-200", description="Pending", amount="-5.00")])
    crud.upsert_transactions(db_session, "account-a", [_raw_tx("ext-200", description="Booked - Delhaize", amount="-5.43")])

    row = db_session.execute(select(Transaction).where(Transaction.external_id == "ext-200")).scalar_one()
    assert row.description == "Booked - Delhaize"
    assert row.amount == Decimal("-5.43")
