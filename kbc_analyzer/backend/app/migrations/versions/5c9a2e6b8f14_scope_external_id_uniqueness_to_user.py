"""scope external_id uniqueness to user

Sprint 6 (S6-02) Step 6 — applies the Step 0 decision (see
docs/multi_user_migration_plan.md): Enable Banking's own FAQ docs state
entry_reference ("external_id" in this schema) is not globally unique, so
a bare UNIQUE(external_id) risks one user's sync upserting into a
different user's transaction row (crud.upsert_transactions' ON CONFLICT
already matches this new constraint shape as of this same ticket — see
app/crud.py).

Revision ID: 5c9a2e6b8f14
Revises: 6f1b3d8c4e29
Create Date: 2026-08-20 00:00:00.000006

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5c9a2e6b8f14'
down_revision: Union[str, Sequence[str], None] = '6f1b3d8c4e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("transactions_external_id_key", "transactions", type_="unique")
    op.create_unique_constraint("uq_transactions_user_id_external_id", "transactions", ["user_id", "external_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_transactions_user_id_external_id", "transactions", type_="unique")
    op.create_unique_constraint("transactions_external_id_key", "transactions", ["external_id"])
