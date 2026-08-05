"""Database read/write helpers for transactions — the Postgres-backed replacement for
kbc_analyzer.cache for anything reachable through the API.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Setting, Transaction


def upsert_transactions(db: Session, account_id: str, txs: list[dict]) -> tuple[int, int]:
    """Upsert normalized transactions for one account.

    Returns (stored, duplicates_skipped). Enable Banking's own transaction reference
    (entry_reference, exposed as `id` on the normalized dict) is the natural key —
    checked per account_id, since the same reference could in principle repeat across
    different accounts.
    """
    if not txs:
        return 0, 0

    external_ids = [t["id"] for t in txs]
    existing = set(
        db.execute(
            select(Transaction.external_id).where(
                Transaction.account_id == account_id,
                Transaction.external_id.in_(external_ids),
            )
        ).scalars()
    )

    for t in txs:
        stmt = pg_insert(Transaction).values(
            account_id=account_id,
            external_id=t["id"],
            booking_date=date.fromisoformat(t["date"]) if t.get("date") else None,
            amount=Decimal(str(t["amount"])),
            description=t["description"],
            raw_data=t,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Transaction.account_id, Transaction.external_id],
            set_={
                "booking_date": stmt.excluded.booking_date,
                "amount": stmt.excluded.amount,
                "description": stmt.excluded.description,
                "raw_data": stmt.excluded.raw_data,
            },
        )
        db.execute(stmt)

    db.commit()

    duplicates_skipped = len(existing)
    stored = len(txs) - duplicates_skipped
    return stored, duplicates_skipped


def list_transactions(db: Session, date_from: date, date_to: date) -> list[Transaction]:
    return list(
        db.execute(
            select(Transaction)
            .where(Transaction.booking_date >= date_from, Transaction.booking_date <= date_to)
            .order_by(Transaction.booking_date)
        ).scalars()
    )


def get_all_settings(db: Session) -> dict[str, str]:
    rows = db.execute(select(Setting)).scalars()
    return {row.key: row.value for row in rows}


def upsert_setting(db: Session, key: str, value: str) -> None:
    stmt = pg_insert(Setting).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(index_elements=[Setting.key], set_={"value": stmt.excluded.value})
    db.execute(stmt)
    db.commit()
