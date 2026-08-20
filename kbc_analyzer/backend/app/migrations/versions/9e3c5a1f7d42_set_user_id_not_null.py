"""set user_id not null

Sprint 6 (S6-02), Ordering step 5 — a separate migration from step 3 (add
nullable column) and step 4 (backfill), once the prior migration's own
rowcount assertions confirmed the backfill left no NULLs. Running this
before backfill finishes would fail outright (correctly) rather than
silently corrupt data; running it in the same migration as step 3 would
remove the verification window between "column added" and "column
enforced," which is the whole point of the split.

Revision ID: 9e3c5a1f7d42
Revises: 4d6f8b217a93
Create Date: 2026-08-20 00:00:00.000003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9e3c5a1f7d42'
down_revision: Union[str, Sequence[str], None] = '4d6f8b217a93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("transactions", "categories", "settings", "budgets", "insights")


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        op.alter_column(table, "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES:
        op.alter_column(table, "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
