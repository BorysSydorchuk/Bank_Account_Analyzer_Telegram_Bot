"""SQLAlchemy models mapping to the tables created in db/init/."""
from sqlalchemy import Column, Date, DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

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
