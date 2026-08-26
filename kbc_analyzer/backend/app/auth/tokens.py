"""Single-use tokens for email verification and password reset (S7-09).

Same shape and same reasoning as session.py's session storage: an opaque,
high-entropy value that's meaningful only while pending and consumed
exactly once — never queried historically, so it belongs in Redis, not a
Postgres table (the same family as sync_lock.py/job_store.py). GETDEL is
one atomic Redis command, so a token can never be consumed twice even
under a race (two requests racing to use the same link).
"""
import os
import secrets
from uuid import UUID

import redis

__all__ = [
    "create_email_verify_token",
    "consume_email_verify_token",
    "create_password_reset_token",
    "consume_password_reset_token",
]

# 24 hours — generous for a real person to get to their inbox, short
# enough that an old, unused verification link isn't a standing liability
# forever.
_EMAIL_VERIFY_TTL_SECONDS = 24 * 60 * 60

# 1 hour — deliberately shorter than the verification token: this one
# grants the ability to set a new password outright, a more sensitive
# action than proving email ownership.
_PASSWORD_RESET_TTL_SECONDS = 60 * 60

_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


def _create_token(prefix: str, user_id: UUID, ttl_seconds: int) -> str:
    token = secrets.token_urlsafe(32)  # 256 bits, same as session.py's session id
    _client.set(f"{prefix}:{token}", str(user_id), ex=ttl_seconds)
    return token


def _consume_token(prefix: str, token: str) -> UUID | None:
    """Atomically reads and deletes the token — a second attempt with the
    same token (a replayed link, a race between two tabs) always misses,
    the same way a used-up single-use value should.
    """
    raw = _client.getdel(f"{prefix}:{token}")
    if raw is None:
        return None
    try:
        return UUID(raw)
    except ValueError:
        # Should be unreachable — this key only ever holds a value _create_token wrote.
        return None


def create_email_verify_token(user_id: UUID) -> str:
    return _create_token("email_verify", user_id, _EMAIL_VERIFY_TTL_SECONDS)


def consume_email_verify_token(token: str) -> UUID | None:
    return _consume_token("email_verify", token)


def create_password_reset_token(user_id: UUID) -> str:
    return _create_token("password_reset", user_id, _PASSWORD_RESET_TTL_SECONDS)


def consume_password_reset_token(token: str) -> UUID | None:
    return _consume_token("password_reset", token)
