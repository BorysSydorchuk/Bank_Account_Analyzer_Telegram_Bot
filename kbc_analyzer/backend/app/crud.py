"""Database read/write helpers for transactions — the Postgres-backed replacement for
kbc_analyzer.cache for anything reachable through the API.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Category, Setting, Transaction


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


def list_transactions_paginated(
    db: Session,
    date_from: date,
    date_to: date,
    page: int,
    limit: int,
    categories: list[str] | None = None,
    amount_type: str = "all",
) -> tuple[list[Transaction], int]:
    """Newest-first, paginated — for the Transactions page (S2-07). Distinct from
    list_transactions() above, which stays unpaginated/chronological for
    statistics and insight generation, which need every row in date order.

    category/amount_type filters happen here (not client-side) so pagination
    stays correct — "page 2 of Groceries" has to mean the database's second
    page of Groceries rows, not the second page of everything with any
    non-Groceries rows stripped out afterwards.
    """
    stmt = select(Transaction).where(Transaction.booking_date >= date_from, Transaction.booking_date <= date_to)
    if categories:
        stmt = stmt.where(Transaction.category.in_(categories))
    if amount_type == "spent":
        stmt = stmt.where(Transaction.amount < 0)
    elif amount_type == "received":
        stmt = stmt.where(Transaction.amount > 0)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = list(
        db.execute(
            stmt.order_by(Transaction.booking_date.desc(), Transaction.id.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        ).scalars()
    )
    return rows, total


def get_uncategorized_transactions(
    db: Session, date_from: date | None = None, date_to: date | None = None
) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.category.is_(None))
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    return list(db.execute(stmt).scalars())


def count_categorized_transactions(
    db: Session, date_from: date | None = None, date_to: date | None = None
) -> int:
    stmt = select(func.count()).select_from(Transaction).where(Transaction.category.is_not(None))
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)
    return db.execute(stmt).scalar_one()


def update_transaction_categories(db: Session, updates: list[dict]) -> None:
    """updates: [{"id": "<uuid str>", "category": "...", "subcategory": "..."|None}].

    The WHERE clause re-checks category IS NULL rather than trusting that the rows
    passed in are still uncategorized — never overwrites a category a Sprint 3
    manual edit (or a concurrent categorize run) already set.
    """
    for u in updates:
        db.execute(
            update(Transaction)
            .where(Transaction.id == u["id"], Transaction.category.is_(None))
            .values(category=u["category"], subcategory=u.get("subcategory"))
        )
    db.commit()


def list_categories(db: Session) -> list[Category]:
    return list(db.execute(select(Category).order_by(Category.name)).scalars())


def get_all_settings(db: Session) -> dict[str, str]:
    rows = db.execute(select(Setting)).scalars()
    return {row.key: row.value for row in rows}


def upsert_setting(db: Session, key: str, value: str) -> None:
    stmt = pg_insert(Setting).values(key=key, value=value)
    stmt = stmt.on_conflict_do_update(index_elements=[Setting.key], set_={"value": stmt.excluded.value})
    db.execute(stmt)
    db.commit()
