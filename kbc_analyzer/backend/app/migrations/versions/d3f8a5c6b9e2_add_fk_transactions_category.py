"""add fk transactions.category -> categories.name

S5-02 (Categories Referential Integrity Decision, Option A — Borys's
call). categories.name is a primary key; transactions.category was a bare
Text column with no FK, so nothing renamed categories today but a future
rename feature would have orphaned every transaction that referenced the
old name and broken its color lookup. budgets.category already has this
exact FK (see c4a91d6e0f3b) — it was added when the table was still
empty, so there was no backfill risk to weigh. transactions already holds
real synced data, so this migration validates before constraining rather
than assuming the data is clean.

ON UPDATE CASCADE: a category rename (once that feature exists) carries
every transaction referencing it along automatically, matching budgets'
behavior.
ON DELETE SET NULL, not RESTRICT: deleting a category should not block on
"some transaction still references it" — it nulls the transaction's
category instead of orphaning it as unparseable text, which is exactly
the failure mode this ticket exists to close off.

Pre-flight validation (upgrade only, no separate script): before adding
the constraint, this queries for any transactions.category value with no
matching categories.name row and raises with the offending values rather
than letting `ALTER TABLE ... ADD CONSTRAINT` fail with Postgres's own
less-actionable violation error, or worse, silently coercing the data.
If this raises, the fix is a data decision (backfill the missing
category row, or null out/reassign the orphaned transactions) made
before re-running the migration — never automatic.

Revision ID: d3f8a5c6b9e2
Revises: c4a91d6e0f3b
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3f8a5c6b9e2'
down_revision: Union[str, Sequence[str], None] = 'c4a91d6e0f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    orphaned_categories = connection.execute(
        sa.text(
            "SELECT DISTINCT t.category FROM transactions t "
            "LEFT JOIN categories c ON c.name = t.category "
            "WHERE t.category IS NOT NULL AND c.name IS NULL"
        )
    ).scalars().all()
    if orphaned_categories:
        raise RuntimeError(
            "Cannot add transactions.category FK: these transactions.category "
            f"values have no matching categories.name row: {sorted(orphaned_categories)}. "
            "Backfill the missing categories.name rows (or reassign/null those "
            "transactions) before re-running this migration."
        )

    op.create_foreign_key(
        "fk_transactions_category_categories_name",
        "transactions",
        "categories",
        ["category"],
        ["name"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_transactions_category_categories_name", "transactions", type_="foreignkey")