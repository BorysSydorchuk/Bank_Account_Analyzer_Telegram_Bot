"""add manually_edited column to transactions

Backs S3-05's manual transaction editor. The categorization agent's
uncategorized-transactions query now excludes any row with
manually_edited = TRUE, even one a user cleared back to no category — a
deliberate manual "unset" is still a decision, not something for the AI to
silently re-guess on the next sync.

Revision ID: 39f7ff68ca00
Revises: ba813c4207d5
Create Date: 2026-08-08 15:46:24.771574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39f7ff68ca00'
down_revision: Union[str, Sequence[str], None] = 'ba813c4207d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transactions', sa.Column('manually_edited', sa.Boolean(), server_default='false', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transactions', 'manually_edited')
