"""SQLAlchemy models — schema for these lives in app/migrations/versions/ (Alembic)."""
from sqlalchemy import Column, Date, DateTime, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"
    # Matches the baseline migration exactly — declared here too (not just in the
    # migration) so `alembic revision --autogenerate` diffs against the real
    # constraint instead of proposing to drop it, which it silently did once
    # already (S2-03) before this was added.
    __table_args__ = (UniqueConstraint("account_id", "external_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    account_id = Column(Text, nullable=False)
    external_id = Column(Text, nullable=False)
    booking_date = Column(Date)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, server_default="EUR")
    description = Column(Text)
    category = Column(Text)
    subcategory = Column(Text)
    raw_data = Column(JSONB)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    # Simple key/value store — deliberately not one column per setting, so adding a
    # new setting later never needs a migration, just a new seeded row.
    key = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)
