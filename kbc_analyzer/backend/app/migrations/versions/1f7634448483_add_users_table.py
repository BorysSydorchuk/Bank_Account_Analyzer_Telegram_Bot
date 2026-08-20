"""add users table

Sprint 6 (S6-01) — the users table Sprint 6's whole auth model builds on.
No user_id backfill onto existing tables here; that's S6-02, once this
table (and a real bootstrap row) exists to backfill against.

password_hash and google_id are both nullable — a user can sign in with
either Google OAuth or email/password (S6-03/S6-04), and account-linking
(S6-03) means a single row can end up with both set. What's never valid is
neither: the CHECK constraint below is the same rule already declared on
the ORM model (app/models.py's User), kept in sync for the same reason
Transaction's UniqueConstraint and Budget's CheckConstraint are declared
in both places — so `alembic revision --autogenerate` diffs against the
real constraint instead of proposing to drop it.

Revision ID: 1f7634448483
Revises: d3f8a5c6b9e2
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1f7634448483'
down_revision: Union[str, Sequence[str], None] = 'd3f8a5c6b9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=True),
        sa.Column('google_id', sa.Text(), nullable=True),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id'),
        sa.CheckConstraint(
            'password_hash IS NOT NULL OR google_id IS NOT NULL',
            name='users_has_auth_method',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
