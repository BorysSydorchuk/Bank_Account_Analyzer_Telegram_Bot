"""add app_settings table

S9-01: a genuinely global (not per-user) key/value config table, seeded with
BILLING_ENABLED=false — the Sprint 9 kill switch. Kept separate from the
existing `settings` table (which is per-user, (user_id, key) primary key,
widened at S6-02 specifically so nothing is shared across users) — see
app/models.py's AppSetting docstring for why overloading that table with a
no-user row would be the wrong move.

Revision ID: a2b6e91d4f37
Revises: 9f1c3a7d5e62
Create Date: 2026-08-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b6e91d4f37'
down_revision: Union[str, Sequence[str], None] = '9f1c3a7d5e62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'app_settings',
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    op.execute(
        "INSERT INTO app_settings (key, value) VALUES ('BILLING_ENABLED', 'false')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('app_settings')
