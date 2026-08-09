"""fix transactions unique constraint to external_id only

S4-01: Enable Banking issues a new internal account_id every time the bank
connection is reauthorized, but external_id (its own transaction reference)
is stable and unique across the whole bank, not just within one account
session. Keying the constraint on (account_id, external_id) meant every
reconnect re-inserted every previously-synced transaction under the new
account_id instead of being recognized as already present — 78 duplicate
pairs were found this way. external_id alone is the correct natural key.

Run scripts/deduplicate.py BEFORE this migration — it will fail to apply
while duplicate external_id rows still exist in the table.

Revision ID: 827da7c749b8
Revises: f6814a7b1a78
Create Date: 2026-08-09 06:27:12.514814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '827da7c749b8'
down_revision: Union[str, Sequence[str], None] = 'f6814a7b1a78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('transactions_account_id_external_id_key', 'transactions', type_='unique')
    op.create_unique_constraint('transactions_external_id_key', 'transactions', ['external_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('transactions_external_id_key', 'transactions', type_='unique')
    op.create_unique_constraint('transactions_account_id_external_id_key', 'transactions', ['account_id', 'external_id'])
