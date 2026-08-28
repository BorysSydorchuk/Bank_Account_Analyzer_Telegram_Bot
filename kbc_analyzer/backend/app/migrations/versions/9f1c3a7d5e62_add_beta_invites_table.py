"""add beta_invites table

S8-06: closed-beta gate for registration (10-20 real people, Borys
grants each one by email — see backend/ops/grant_beta_invite.py). Every
new account, whether created via password registration or a first
Google sign-in, must match an unused row here before it's created.
email is stored lowercased (app/crud.py's beta-invite helpers own
that normalization) so this table doesn't inherit the pre-existing
case-sensitivity gap flagged against the users table (S8-06 pre-check
finding, docs/verification_debt.md).

Revision ID: 9f1c3a7d5e62
Revises: 7c2f4b9e1a83
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9f1c3a7d5e62'
down_revision: Union[str, Sequence[str], None] = '7c2f4b9e1a83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'beta_invites',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('invited_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_beta_invites_email'),
        # ON DELETE SET NULL, not the default RESTRICT: this table is an
        # audit trail of who was invited and when, not a live reference —
        # deleting a user account (closing it, GDPR erasure, a bad test
        # account) must never be blocked by, or cascade into deleting,
        # their own invite history. Found the hard way: the naive FK
        # (no ondelete) made a real test's account-deletion step fail
        # with an IntegrityError.
        sa.ForeignKeyConstraint(['used_by_user_id'], ['users.id'], ondelete='SET NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('beta_invites')
