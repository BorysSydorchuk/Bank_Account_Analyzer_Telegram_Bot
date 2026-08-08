"""add insights table

S3-07 Item 3: insights previously only lived in Redis for the lifetime of a
sync job (S3-04) — a page refresh lost them entirely. This table persists the
last generated set per date range; the Celery task replaces old rows for a
range with fresh ones on every sync rather than accumulating history, since
an insight is only ever meaningful as "the current read on this range," not
as a record of what was said before.

Revision ID: f6814a7b1a78
Revises: 2b3e0feb15ac
Create Date: 2026-08-08 17:36:26.772948

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6814a7b1a78'
down_revision: Union[str, Sequence[str], None] = '2b3e0feb15ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('insights',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('date_from', sa.Date(), nullable=False),
    sa.Column('date_to', sa.Date(), nullable=False),
    sa.Column('type', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('severity', sa.Text(), nullable=False),
    sa.Column('provider', sa.Text(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # GET /api/insights always filters on this exact pair — every row for a
    # range is replaced together (crud.replace_insights), so this index is
    # what keeps that lookup and the delete-before-insert both fast as the
    # table accumulates ranges over time.
    op.create_index('ix_insights_date_range', 'insights', ['date_from', 'date_to'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_insights_date_range', table_name='insights')
    op.drop_table('insights')
