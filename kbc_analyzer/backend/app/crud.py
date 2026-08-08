"""Database read/write helpers for transactions — the Postgres-backed replacement for
kbc_analyzer.cache for anything reachable through the API.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Category, Insight, Setting, Transaction


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


def search_transactions(db: Session, query: str, limit: int) -> list[Transaction]:
    """Global search (S3-07 Item 4) — across every transaction ever synced,
    not scoped to any date range or the current page. Distinct from the
    Transactions page's own date-scoped, paginated list above."""
    stmt = (
        select(Transaction)
        .where(Transaction.description.ilike(f"%{query}%"))
        .order_by(Transaction.booking_date.desc(), Transaction.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())


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
    # manually_edited excludes a row even if its category is null — a user
    # clearing a category by hand (S3-05) is still a decision, not something
    # for the next categorize run to silently fill back in.
    stmt = select(Transaction).where(Transaction.category.is_(None), Transaction.manually_edited.is_(False))
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

    The WHERE clause re-checks category IS NULL AND manually_edited IS FALSE
    rather than trusting that the rows passed in are still eligible — never
    overwrites a category a manual edit (S3-05) or a concurrent categorize
    run already set.
    """
    for u in updates:
        db.execute(
            update(Transaction)
            .where(
                Transaction.id == u["id"],
                Transaction.category.is_(None),
                Transaction.manually_edited.is_(False),
            )
            .values(category=u["category"], subcategory=u.get("subcategory"))
        )
    db.commit()


def update_transaction(db: Session, transaction_id: UUID, updates: dict) -> Transaction | None:
    """updates: a dict of already-validated column/value pairs (category,
    subcategory, description — whichever were actually present in the PATCH
    body). Always stamps manually_edited = True, even if none of the
    provided values differ from what's already stored — the point is
    recording that a human looked at this row, not just changing its data.
    """
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        return None
    for field, value in updates.items():
        setattr(transaction, field, value)
    transaction.manually_edited = True
    db.commit()
    db.refresh(transaction)
    return transaction


def list_categories(db: Session) -> list[Category]:
    return list(db.execute(select(Category).order_by(Category.name)).scalars())


def list_seeded_category_names(db: Session) -> list[str]:
    """Category names still on their S3-01 seed color — the set eligible for
    S3-02's AI color assignment. 'ai' and 'user' rows are excluded."""
    return list(db.execute(select(Category.name).where(Category.source == "seed")).scalars())


def get_categories_by_name(db: Session, names: list[str]) -> dict[str, Category]:
    """Existing rows for the given names, keyed by name. Used by the AI color
    step to read a category's own seed color as its fallback if the LLM's
    color fails validation."""
    if not names:
        return {}
    rows = db.execute(select(Category).where(Category.name.in_(names))).scalars()
    return {row.name: row for row in rows}


def upsert_category_colors(db: Session, colors_by_name: dict[str, str], source: str) -> None:
    """The AI color-assignment path (S3-02) — always called with source='ai'.
    Never overwrites a row whose existing source is 'user' — user color
    choices are final. Also mirrors the color into ai_color, so a later user
    override (S3-06) has something concrete to "Reset to AI" back to."""
    for name, color in colors_by_name.items():
        stmt = pg_insert(Category).values(name=name, color=color, source=source, ai_color=color)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Category.name],
            set_={"color": stmt.excluded.color, "source": stmt.excluded.source, "ai_color": stmt.excluded.ai_color},
            where=Category.source != "user",
        )
        db.execute(stmt)
    db.commit()


def set_category_color(db: Session, name: str, color: str) -> Category | None:
    """A user-initiated color change (PATCH /api/categories/{name}, S3-06).
    Unlike upsert_category_colors' AI path, this always applies — a user
    editing their own category again is not the same case as the AI trying
    to silently overwrite a user's existing choice. Leaves ai_color alone,
    so "Reset to AI" still has the original AI answer to go back to."""
    category = db.get(Category, name)
    if category is None:
        return None
    category.color = color
    category.source = "user"
    db.commit()
    db.refresh(category)
    return category


def reset_category_to_ai(db: Session, name: str) -> Category | None:
    """Restores a category's AI-assigned color after a user override.
    Returns None if the category doesn't exist, or if it has no ai_color to
    reset to (never AI-colored in the first place) — both cases the router
    treats as "nothing to reset"."""
    category = db.get(Category, name)
    if category is None or category.ai_color is None:
        return None
    category.color = category.ai_color
    category.source = "ai"
    db.commit()
    db.refresh(category)
    return category


def create_category(db: Session, name: str, color: str) -> Category:
    """A brand-new, user-defined category (S3-06) — always is_custom=True,
    source='user'. No ai_color, since the AI never assigned one."""
    category = Category(name=name, color=color, is_custom=True, source="user")
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def replace_insights(
    db: Session,
    date_from: date,
    date_to: date,
    insights: list[dict],
    provider: str,
    generated_at: datetime,
) -> None:
    """Swaps out all insights for one date range in a single transaction —
    never accumulates history, since an insight is only ever meaningful as
    "the current read on this range" (S3-07 Item 3). Deleting first means a
    sync that produces zero insights (e.g. every category empty) correctly
    leaves the range with none, rather than stale ones from the last sync
    that did.
    """
    db.execute(delete(Insight).where(Insight.date_from == date_from, Insight.date_to == date_to))
    for item in insights:
        db.add(
            Insight(
                date_from=date_from,
                date_to=date_to,
                type=item["type"],
                title=item["title"],
                body=item["body"],
                severity=item["severity"],
                provider=provider,
                generated_at=generated_at,
            )
        )
    db.commit()


def list_insights(db: Session, date_from: date, date_to: date) -> list[Insight]:
    return list(
        db.execute(
            select(Insight)
            .where(Insight.date_from == date_from, Insight.date_to == date_to)
            .order_by(Insight.generated_at)
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
