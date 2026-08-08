"""add ai_color column to categories

Backs S3-06's "Reset to AI" button — the color a user's override replaces
would otherwise be gone with no way back. Backfills ai_color = color for
every row already sitting on an S3-02 AI assignment (source = 'ai'), so
"Reset to AI" has something real to restore on categories colored before
this column existed, not just ones colored from now on.

Revision ID: 2b3e0feb15ac
Revises: 39f7ff68ca00
Create Date: 2026-08-08 16:26:36.221959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b3e0feb15ac'
down_revision: Union[str, Sequence[str], None] = '39f7ff68ca00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('categories', sa.Column('ai_color', sa.Text(), nullable=True))
    op.execute("UPDATE categories SET ai_color = color WHERE source = 'ai'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('categories', 'ai_color')
