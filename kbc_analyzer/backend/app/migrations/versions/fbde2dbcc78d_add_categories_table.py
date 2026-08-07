"""add categories table

Seeds the 7 categories the categorization agent (S2-05) already produces,
with a backup palette color each — see the S3-01 handoff notes for why this
seeds real colors now rather than leaving them blank until S3-02's AI
assignment. This same seed data incidentally fixes the "Income" pill
cosmetic bug flagged (not fixed) at the end of Sprint 2.

Revision ID: fbde2dbcc78d
Revises: 2b7c1704a037
Create Date: 2026-08-07 10:58:06.449761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbde2dbcc78d'
down_revision: Union[str, Sequence[str], None] = '2b7c1704a037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_COLORS = {
    "Restaurants and Cafes": "#F97316",
    "Groceries": "#10B981",
    "Traveling": "#F59E0B",
    "Rent/Housing": "#6366F1",
    "Income": "#0EA5E9",
    "Transfers": "#8B5CF6",
    "Other": "#64748B",
}


def upgrade() -> None:
    """Upgrade schema."""
    categories_table = op.create_table(
        'categories',
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('color', sa.Text(), nullable=False),
        sa.Column('is_custom', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('name')
    )
    op.bulk_insert(
        categories_table,
        [{"name": name, "color": color, "is_custom": False} for name, color in SEED_COLORS.items()],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('categories')
