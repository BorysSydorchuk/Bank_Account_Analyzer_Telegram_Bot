"""categories composite primary key

Sprint 6 (S6-02) Step 4 — categories' primary key becomes (user_id, name):
a category name is only unique per user now (PM ruling, 2026-08-17). Both
existing FKs into categories.name (transactions.category, S5-02;
budgets.category, S4-05) become composite (user_id, category) ->
categories(user_id, name), since Postgres requires a foreign key to
reference a unique constraint or primary key on the exact column set it
points at — a single-column FK to name alone stops being valid the moment
name alone is no longer unique on its own.

Order matters here: drop the old single-column FKs before dropping
categories' old primary key (Postgres won't drop a primary key while a FK
still references it), then rebuild the primary key, then add the new
composite FKs. Must run after 9e3c5a1f7d42 (NOT NULL on user_id) — a FK
into (user_id, name) is only meaningful once user_id can't be NULL on
either side (a NULL user_id on the referencing row would never match
anything, silently breaking the FK's whole purpose rather than raising).

Revision ID: 2a8d914f6c37
Revises: 9e3c5a1f7d42
Create Date: 2026-08-20 00:00:00.000004

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2a8d914f6c37'
down_revision: Union[str, Sequence[str], None] = '9e3c5a1f7d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("fk_transactions_category_categories_name", "transactions", type_="foreignkey")
    op.drop_constraint("budgets_category_fkey", "budgets", type_="foreignkey")

    op.drop_constraint("categories_pkey", "categories", type_="primary")
    op.create_primary_key("categories_pkey", "categories", ["user_id", "name"])

    op.create_foreign_key(
        "fk_transactions_category_categories_name",
        "transactions",
        "categories",
        ["user_id", "category"],
        ["user_id", "name"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "budgets_category_fkey",
        "budgets",
        "categories",
        ["user_id", "category"],
        ["user_id", "name"],
        onupdate="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_transactions_category_categories_name", "transactions", type_="foreignkey")
    op.drop_constraint("budgets_category_fkey", "budgets", type_="foreignkey")

    op.drop_constraint("categories_pkey", "categories", type_="primary")
    op.create_primary_key("categories_pkey", "categories", ["name"])

    op.create_foreign_key(
        "fk_transactions_category_categories_name",
        "transactions",
        "categories",
        ["category"],
        ["name"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "budgets_category_fkey",
        "budgets",
        "categories",
        ["category"],
        ["name"],
        onupdate="CASCADE",
    )
