"""add subscriptions table

S9-02: per-user Stripe subscription state — `user_id` primary key, not a
surrogate id, same shape as `enable_banking_sessions` (a2b6e91d4f37's
sibling table for the same reason): one row tracks one user's *current*
subscription, updated in place by S9-03's webhook handler rather than
appended to as a history log. No row at all is the normal state for a
free user who has never touched checkout; `crud.get_user_tier` reads that
absence as "free" (see app/models.py's Subscription docstring). Purely
additive — no existing table is touched, so no existing user or row is
affected by this migration.

Revision ID: 59a0e1c55d1a
Revises: a2b6e91d4f37
Create Date: 2026-08-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '59a0e1c55d1a'
down_revision: Union[str, Sequence[str], None] = 'a2b6e91d4f37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'subscriptions',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_customer_id', sa.Text(), nullable=True),
        sa.Column('stripe_subscription_id', sa.Text(), nullable=True),
        sa.Column('tier', sa.Text(), nullable=False, server_default='free'),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('stripe_customer_id', name='uq_subscriptions_stripe_customer_id'),
        sa.UniqueConstraint('stripe_subscription_id', name='uq_subscriptions_stripe_subscription_id'),
        sa.CheckConstraint("tier IN ('free', 'paid')", name='ck_subscriptions_tier'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('subscriptions')
