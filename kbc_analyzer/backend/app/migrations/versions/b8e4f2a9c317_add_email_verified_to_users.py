"""add email_verified to users

S7-09: gates Enable Banking connect/sync (app/auth/dependency.py's
require_verified_email) behind proven email ownership. Backfilled true
for every existing row — a forward-looking gate on new signups, not a
retroactive lockout of already-trusted accounts that pre-date this
column.

Revision ID: b8e4f2a9c317
Revises: a3f6c8e2b704
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e4f2a9c317'
down_revision: Union[str, Sequence[str], None] = 'a3f6c8e2b704'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False),
    )
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'email_verified')
