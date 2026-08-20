"""backfill user_id from bootstrap user

Sprint 6 (S6-02), Ordering step 4. Every existing row in every touched
table gets user_id set to the one real user seeded in
7b2e4c9a1d05_seed_bootstrap_user.py — same care as S4-01's dedup cleanup:
count what's about to change, do it, verify the count matches exactly.

Each table's UPDATE is followed by an assertion that its rowcount equals
that table's pre-migration row count (not a hardcoded number — computed
live against whatever database this actually runs against) — if a single
row were somehow unreachable by the WHERE clause, this raises and rolls
back the whole migration rather than silently leaving an orphaned NULL
that step 5 (NOT NULL) would otherwise just fail loudly on anyway. This
also doubles as a stronger check than step 5 alone: NOT NULL alone would
only catch remaining NULLs, not silently mismatched *counts* if this
UPDATE somehow overwrote more or fewer rows than expected.

Revision ID: 4d6f8b217a93
Revises: c1a7f083e26b
Create Date: 2026-08-20 00:00:00.000002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d6f8b217a93'
down_revision: Union[str, Sequence[str], None] = 'c1a7f083e26b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BOOTSTRAP_USER_EMAIL = "boris.sydorchuk@gmail.com"
_BACKFILLED_TABLES = ("transactions", "categories", "settings", "budgets", "insights")


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    bootstrap_user_id = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email").bindparams(email=BOOTSTRAP_USER_EMAIL)
    ).scalar_one()

    for table in _BACKFILLED_TABLES:
        expected = bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()

        result = bind.execute(
            sa.text(f"UPDATE {table} SET user_id = :user_id WHERE user_id IS NULL").bindparams(
                user_id=bootstrap_user_id
            )
        )

        if result.rowcount != expected:
            raise RuntimeError(
                f"Backfill mismatch on {table}: expected to update {expected} rows "
                f"(its full row count — every row should have been NULL going in), "
                f"actually updated {result.rowcount}. Rolling back rather than leaving "
                f"the table in a partially-backfilled state."
            )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    bootstrap_user_id = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email").bindparams(email=BOOTSTRAP_USER_EMAIL)
    ).scalar_one()

    for table in _BACKFILLED_TABLES:
        bind.execute(
            sa.text(f"UPDATE {table} SET user_id = NULL WHERE user_id = :user_id").bindparams(
                user_id=bootstrap_user_id
            )
        )
