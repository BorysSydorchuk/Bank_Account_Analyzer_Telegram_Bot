"""Per-user, Postgres-backed Enable Banking session storage (S7-06).

Replaces the single global eb_session.json file kbc_analyzer.enablebanking
used to read/write directly — that file was never actually durable in
production (an ECS Fargate redeploy wipes a task's local filesystem) and
never shared between the web and worker services (two separate tasks,
two separate filesystems). This store implements the same load()/save()
shape EnableBankingClient expects, scoped to one user_id, backed by the
enable_banking_sessions table — durable across redeploys and visible to
both services because both already share the same RDS instance.
"""
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .crypto import decrypt, encrypt
from .models import EnableBankingSession

__all__ = ["DatabaseSessionStore"]


class DatabaseSessionStore:
    """Fernet-encrypted, per-user session storage — the session_store
    EnableBankingClient is given when running inside the web app, as
    opposed to the FileSessionStore it defaults to for the terminal/bot.
    """

    def __init__(self, db: Session, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id

    def load(self) -> dict | None:
        row = self.db.get(EnableBankingSession, self.user_id)
        if row is None:
            return None
        return {
            "session_id": decrypt(row.session_id_encrypted),
            "account_uids": json.loads(decrypt(row.account_uids_encrypted)),
            # Stripped of tzinfo before returning: kbc_analyzer/enablebanking.py
            # compares valid_until against bare datetime.now()/utcnow()
            # throughout (a deliberate, documented convention — S7-04's CSRF
            # fixture bug was exactly a naive/aware mismatch here). The
            # column itself is timestamptz because every other timestamp
            # column in this schema is; this keeps that an internal-storage
            # detail instead of leaking into the comparison logic.
            "valid_until": row.valid_until.replace(tzinfo=None).isoformat(),
        }

    def save(self, data: dict) -> None:
        stmt = pg_insert(EnableBankingSession).values(
            user_id=self.user_id,
            session_id_encrypted=encrypt(data["session_id"]),
            account_uids_encrypted=encrypt(json.dumps(data["account_uids"])),
            valid_until=datetime.fromisoformat(data["valid_until"]),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[EnableBankingSession.user_id],
            set_={
                "session_id_encrypted": stmt.excluded.session_id_encrypted,
                "account_uids_encrypted": stmt.excluded.account_uids_encrypted,
                "valid_until": stmt.excluded.valid_until,
            },
        )
        self.db.execute(stmt)
        self.db.commit()
