"""add enable_banking_sessions table

S7-06: replaces the single global eb_session.json file with one encrypted
row per user. The file it replaces was never actually durable in
production — an ECS Fargate redeploy wipes a task's local filesystem, and
the web/worker services are two separate tasks that never shared it in
the first place (confirmed empirically during this ticket's premise
check: the file was gone from the running web container immediately
after S7-04's post-reconnect redeploy). This table fixes both problems
at once by moving session state into Postgres, which both services
already share.

Revision ID: a3f6c8e2b704
Revises: 5c9a2e6b8f14
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3f6c8e2b704'
down_revision: Union[str, Sequence[str], None] = '5c9a2e6b8f14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'enable_banking_sessions',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id_encrypted', sa.Text(), nullable=False),
        sa.Column('account_uids_encrypted', sa.Text(), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('enable_banking_sessions')
