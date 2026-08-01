"""SQLAlchemy engine/session setup for the Postgres-backed web app.

Replaces kbc_analyzer/cache.py (SQLite) for everything reachable through the API.
The CLI and Telegram bot are untouched and keep using the SQLite cache.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency that yields a request-scoped session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()