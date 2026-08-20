"""add nullable user_id columns

Sprint 6 (S6-02), Ordering step 3: nullable first, deliberately — same
pattern budgets already used at S4-05. Backfilling happens in the next
migration; NOT NULL is a separate migration after that, once the backfill
is verified. Splitting these into three migrations (rather than one) is
what actually gives a verification window between "column exists" and
"column enforced," not just a comment saying one exists.

transactions, insights: brand-new user_id column, nullable.
categories, settings: also brand-new user_id column here, nullable — their
primary-key changes (composite (user_id, name) / (user_id, key)) come
later, once every row is backfilled (a primary key column can't be NULL,
so those tables can't become their final shape until then).
budgets: already has a nullable user_id column since S4-05 — this
migration only adds the FK to users(id) it never had (users didn't exist
before Sprint 6), not a new column.

Revision ID: c1a7f083e26b
Revises: 7b2e4c9a1d05
Create Date: 2026-08-20 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c1a7f083e26b'
down_revision: Union[str, Sequence[str], None] = '7b2e4c9a1d05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    for table in ("transactions", "insights", "categories", "settings"):
        op.add_column(table, sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_user_id_users",
            table,
            "users",
            ["user_id"],
            ["id"],
        )

    op.create_foreign_key(
        "fk_budgets_user_id_users",
        "budgets",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_budgets_user_id_users", "budgets", type_="foreignkey")

    for table in ("transactions", "insights", "categories", "settings"):
        op.drop_constraint(f"fk_{table}_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "user_id")
