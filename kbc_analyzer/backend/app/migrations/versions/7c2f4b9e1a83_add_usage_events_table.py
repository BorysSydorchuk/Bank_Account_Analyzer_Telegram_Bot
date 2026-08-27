"""add usage_events table

S8-04: per-user daily/monthly caps on LLM-calling actions (chat, categorize,
insights) — a real beta cost/abuse guardrail, not a rate limiter (S5-07's
slowapi limiter already covers short-window burst protection; this is a
long-window cumulative cap, a different mechanism for a different purpose).
One row per action actually taken, not a pre-aggregated counter — see
app/models.py's UsageEvent docstring for why.

Revision ID: 7c2f4b9e1a83
Revises: d4a7e19c6b52
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7c2f4b9e1a83'
down_revision: Union[str, Sequence[str], None] = 'd4a7e19c6b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(
        'ix_usage_events_user_action_created', 'usage_events', ['user_id', 'action', 'created_at']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_usage_events_user_action_created', table_name='usage_events')
    op.drop_table('usage_events')
