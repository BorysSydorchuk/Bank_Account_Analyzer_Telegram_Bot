"""add budgets table

Per-category monthly spending limits (S4-05). `user_id` is nullable and
unused today (always NULL) — added now, ahead of Sprint 6's multi-user
migration, so that migration only has to backfill and add NOT NULL rather
than retrofit a whole new column onto a table already holding real data.

The unique constraint uses UNIQUE NULLS NOT DISTINCT (Postgres 15+; this
image is postgres:16-alpine) rather than a plain UNIQUE, because Postgres
treats NULLs as distinct from each other by default — a plain UNIQUE on
(user_id, category, period) would let the same category get two budgets
in the single-user era, since every row's user_id is NULL and NULL never
equals NULL for uniqueness purposes. NULLS NOT DISTINCT closes that gap
without waiting for Sprint 6 to give every row a real user_id.

Revision ID: c4a91d6e0f3b
Revises: 827da7c749b8
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4a91d6e0f3b'
down_revision: Union[str, Sequence[str], None] = '827da7c749b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('period', sa.Text(), server_default='monthly', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['category'], ['categories.name'], onupdate='CASCADE'),
        sa.CheckConstraint('amount > 0', name='ck_budgets_amount_positive'),
    )
    # NULLS NOT DISTINCT has no first-class op.create_unique_constraint spelling
    # guaranteed across SQLAlchemy versions yet, so it's issued directly.
    op.execute(
        "ALTER TABLE budgets ADD CONSTRAINT uq_budgets_user_category_period "
        "UNIQUE NULLS NOT DISTINCT (user_id, category, period)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('budgets')
