"""settings composite primary key

Sprint 6 (S6-02) Step 5. settings was a flat key-value store (key TEXT
PRIMARY KEY) — not a bolt-on user_id addition like transactions/insights,
a real shape change, per S5-01's finding. Widened to (user_id, key)
composite primary key rather than a separate user_settings table: a
shared API key funds every other user's LLM calls otherwise (a billing
hole, PM ruling 2026-08-17), and the existing key-value row shape didn't
need to change, only its identity — crypto.py's encrypt-on-write is
untouched by this migration (it operates on a value string, never on a
row's key), so encrypted API keys keep working exactly as before, just
scoped per user.

Revision ID: 6f1b3d8c4e29
Revises: 2a8d914f6c37
Create Date: 2026-08-20 00:00:00.000005

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6f1b3d8c4e29'
down_revision: Union[str, Sequence[str], None] = '2a8d914f6c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("settings_pkey", "settings", type_="primary")
    op.create_primary_key("settings_pkey", "settings", ["user_id", "key"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("settings_pkey", "settings", type_="primary")
    op.create_primary_key("settings_pkey", "settings", ["key"])
