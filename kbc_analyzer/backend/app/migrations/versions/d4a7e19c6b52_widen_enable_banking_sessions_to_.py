"""widen enable_banking_sessions to composite (user_id, institution) key

S8-01: enable_banking_sessions.user_id was the table's sole primary key
(S7-06), so storage held exactly one bank connection per user — connecting
a second institution overwrote the first's session row via ON CONFLICT
(user_id) DO UPDATE rather than adding to it. Sprint 8's goal (KBC and ING
connected simultaneously) needs both to coexist. institution is a plain
text tag ("KBC", "ING" — see app/institutions.py), not a foreign key to a
lookup table.

Same nullable-then-backfill-then-enforce discipline as S6-02's multi-user
migration: institution is added nullable first, backfilled to 'KBC' (the
only bank this app has ever connected — every existing row, if any, is a
KBC session by construction), then set NOT NULL and folded into the
primary key. A real row exists in production today (Borys's live KBC
connection, S4-10/S7-06) and must survive this migration with its
session_id/account_uids/valid_until untouched — only the key shape changes.

Revision ID: d4a7e19c6b52
Revises: b8e4f2a9c317
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7e19c6b52'
down_revision: Union[str, Sequence[str], None] = 'b8e4f2a9c317'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: add nullable — no existing row would satisfy NOT NULL yet.
    op.add_column('enable_banking_sessions', sa.Column('institution', sa.Text(), nullable=True))

    # Step 2: backfill. Every row that exists today predates multi-bank
    # support, so it can only be a KBC connection.
    op.execute("UPDATE enable_banking_sessions SET institution = 'KBC' WHERE institution IS NULL")

    # Step 3: enforce, now that every row has a value.
    op.alter_column('enable_banking_sessions', 'institution', nullable=False)

    # Step 4: widen the primary key. Postgres has no direct "add a column to
    # an existing PK" — drop and recreate. The table's FK to users(id) on
    # user_id is a separate constraint (declared independently in the
    # a3f6c8e2b704 migration), so it is untouched by this.
    op.drop_constraint('enable_banking_sessions_pkey', 'enable_banking_sessions', type_='primary')
    op.create_primary_key(
        'enable_banking_sessions_pkey', 'enable_banking_sessions', ['user_id', 'institution']
    )


def downgrade() -> None:
    """Downgrade schema.

    Only safe if no user has more than one row (i.e. no simultaneous
    connections exist yet) — collapsing back to a user_id-only primary key
    would otherwise violate uniqueness. Mirrors the same real-world
    constraint the forward migration was written to lift.
    """
    op.drop_constraint('enable_banking_sessions_pkey', 'enable_banking_sessions', type_='primary')
    op.create_primary_key('enable_banking_sessions_pkey', 'enable_banking_sessions', ['user_id'])
    op.drop_column('enable_banking_sessions', 'institution')
