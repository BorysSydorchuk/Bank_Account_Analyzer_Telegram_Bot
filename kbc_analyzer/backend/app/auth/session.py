"""Server-side session storage in Redis (S6-01) — the session id is a bare
opaque token, never a JWT; all session state (which user, when created)
lives here, not in anything the client can read or forge. Same
Redis-as-transient-state pattern as job_store.py/sync_lock.py: a session
is meaningful only while it's live, never queried historically, so it
belongs in Redis, not Postgres.
"""
import json
import os
import secrets
from datetime import datetime, timezone
from uuid import UUID

import redis
from fastapi import Response

__all__ = [
    "SESSION_COOKIE_NAME",
    "SESSION_TTL_SECONDS",
    "create_session",
    "get_session",
    "destroy_session",
    "set_session_cookie",
    "clear_session_cookie",
]

# 30 days, sliding — a user who keeps using the app never has to log back
# in; one who genuinely abandons it eventually falls out of Redis on its
# own instead of accumulating forever. Sliding rather than a fixed expiry
# because a fixed 30-day cutoff would log out an active daily user just as
# readily as an abandoned one — the thing worth expiring is *inactivity*,
# not the mere passage of time.
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60

# get_session() only re-issues the TTL once less than this much of it is
# left (i.e. once the session hasn't been touched in ~25 days), not on
# every single authenticated request. A refresh-on-every-request policy
# would mean one Redis EXPIRE write per API call for the app's entire
# lifetime, for a session that in practice almost never sits idle for
# close to 30 days — this bounds refresh writes to roughly once every 5
# days of continuous use per user while still keeping any active session
# alive indefinitely.
REFRESH_THRESHOLD_SECONDS = 5 * 24 * 60 * 60

SESSION_COOKIE_NAME = "session_id"

# Secure must be off for local dev: backend/frontend both run over plain
# http:// today (ARCHITECTURE.md's URLs & Redirects), and a browser will
# refuse to ever send a Secure cookie back to a plain http:// origin.
# Chromium-family browsers do special-case http://localhost as a
# "potentially trustworthy" origin for some secure-context APIs, but that
# exemption is not reliably specified to also cover the cookie Secure
# attribute across every browser/version this app might be developed in —
# an explicit env-driven flag (matching the FRONTEND_ORIGIN dev/prod split
# already in docker-compose.yml/.env.example) is safer than relying on an
# implicit browser quirk for a security-relevant flag. Defaults to off
# (current, correct default for every environment this app runs in today);
# Sprint 7's real production HTTPS is expected to set COOKIE_SECURE=true.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


def _session_key(session_id: str) -> str:
    """The Redis key a session's record is stored under."""
    return f"session:{session_id}"


def create_session(user_id: UUID) -> str:
    """Creates a new session for user_id, returns the session id to store in
    the cookie. token_urlsafe(32) is 256 bits of randomness from Python's
    CSPRNG — not practically guessable, and unrelated to the user's own id
    or any other predictable value.
    """
    session_id = secrets.token_urlsafe(32)
    payload = {"user_id": str(user_id), "created_at": datetime.now(timezone.utc).isoformat()}
    _client.set(_session_key(session_id), json.dumps(payload), ex=SESSION_TTL_SECONDS)
    return session_id


def get_session(session_id: str) -> UUID | None:
    """The session's user_id, or None if session_id is missing, expired, or
    malformed (a tampered cookie value almost always just misses the Redis
    key outright, since it's an opaque random token, not a value with a
    predictable structure to tamper into something that still resolves).
    Refreshes the session's TTL if it's within REFRESH_THRESHOLD_SECONDS of
    expiring (sliding expiry — see SESSION_TTL_SECONDS above).
    """
    key = _session_key(session_id)
    raw = _client.get(key)
    if raw is None:
        return None
    try:
        user_id = UUID(json.loads(raw)["user_id"])
    except (KeyError, TypeError, ValueError):
        # Malformed payload — the key exists but isn't a valid session record.
        # Should never happen from normal use (only create_session ever
        # writes this key), but a corrupt/tampered value is treated as no
        # session rather than raising, same as a missing one.
        return None

    ttl = _client.ttl(key)
    if 0 <= ttl < REFRESH_THRESHOLD_SECONDS:
        _client.expire(key, SESSION_TTL_SECONDS)

    return user_id


def destroy_session(session_id: str) -> None:
    """Logs out session_id. A no-op, not an error, if it's already gone
    (expired or already destroyed) — every caller can call this
    unconditionally without checking existence first.
    """
    _client.delete(_session_key(session_id))


def set_session_cookie(response: Response, session_id: str) -> None:
    """Sets the session cookie on a login/register/OAuth-callback response
    (S6-03/S6-04). httpOnly: never readable by client-side JS, closing off
    the main XSS-driven session-theft path. SameSite=Lax: sent on top-level
    navigation (so an OAuth-callback redirect still carries it) but not on
    cross-site subrequests, which is CSRF protection sufficient for a
    cookie-only session with no state-changing GET routes.
    """
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Clears the session cookie on logout (S6-03). Attributes must match
    set_session_cookie's exactly (path, domain, etc.) — a mismatched
    delete_cookie call sets a new, differently-scoped cookie rather than
    actually clearing the original one.
    """
    response.delete_cookie(key=SESSION_COOKIE_NAME, httponly=True, secure=COOKIE_SECURE, samesite="lax")
