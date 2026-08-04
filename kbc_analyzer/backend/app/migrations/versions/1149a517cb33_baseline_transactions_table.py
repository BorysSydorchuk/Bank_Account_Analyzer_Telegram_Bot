"""baseline transactions table

Mirrors db/init/001_transactions.sql (S1-01/S1-02) exactly, so that
`alembic upgrade head` against a genuinely empty database produces the same
schema Sprint 1 created by hand. On the existing dev database — where this
table already exists with real data — this revision is stamped, not run
(see the S2-01 handoff notes for why).

Revision ID: 1149a517cb33
Revises:
Create Date: 2026-08-04 22:55:45.330452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1149a517cb33'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.Text(), server_default="EUR"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("subcategory", sa.Text(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("account_id", "external_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("transactions")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
