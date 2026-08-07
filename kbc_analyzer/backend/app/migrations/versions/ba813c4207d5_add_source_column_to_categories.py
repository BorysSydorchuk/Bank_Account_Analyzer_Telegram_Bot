"""add source column to categories

Tracks where each category's color came from: 'seed' (S3-01's static
palette), 'ai' (S3-02's color-assignment agent), or 'user' (a manual
override, coming in S3-06). The color-assignment step reads this column to
find rows still eligible for an AI color — anything already 'ai' or 'user'
is left untouched. A constant Postgres DEFAULT on ADD COLUMN backfills all
existing rows to 'seed' as part of this same migration, so the 7 rows S3-01
seeded need no separate UPDATE.

Revision ID: ba813c4207d5
Revises: fbde2dbcc78d
Create Date: 2026-08-07 12:46:14.041533

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba813c4207d5'
down_revision: Union[str, Sequence[str], None] = 'fbde2dbcc78d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('categories', sa.Column('source', sa.Text(), server_default='seed', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('categories', 'source')
