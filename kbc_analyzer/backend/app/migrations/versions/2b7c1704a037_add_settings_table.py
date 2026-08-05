"""add settings table

Revision ID: 2b7c1704a037
Revises: 1149a517cb33
Create Date: 2026-08-05 11:30:51.120480

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b7c1704a037'
down_revision: Union[str, Sequence[str], None] = '1149a517cb33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('settings',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    # NOTE: autogenerate also proposed dropping transactions' UNIQUE(account_id,
    # external_id) constraint here — a false positive, since models.py's Transaction
    # class never declared that constraint at the ORM level even though it's real in
    # the database (added in the S1-02/S2-01 baseline). Removed by hand; the model was
    # fixed in the same commit so future autogenerate runs won't propose this again.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('settings')
