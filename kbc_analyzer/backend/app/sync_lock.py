"""Redis-based lock preventing two sync jobs from running concurrently (S5-05).

Real per-user locking as of S6-06: routers/transactions.py's
sync_transactions passes the authenticated user's real id, so two
different users can each have their own sync in flight at once, each
locked independently. user_id stays optional (default None) only because
nothing outside that one call site has a reason to pass anything else —
the key derivation itself has taken user_id since S5-05.
"""
import os
from uuid import UUID

import redis

# Must outlive the frontend's own give-up timeout (useDashboard.ts's
# MAX_POLL_DURATION_MS, 10 minutes) — otherwise a crashed worker's lock
# would still be held past the point the user could plausibly retry,
# deadlocking sync until manual intervention. 11 minutes, not exactly 10, so
# a job still legitimately running at the 10-minute mark (where the frontend
# gives up polling, not where the lock expires) doesn't get evicted mid-flight.
LOCK_TTL_SECONDS = 11 * 60

_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

# Atomic compare-and-delete: a plain GET-then-DELETE from Python has a race
# window where another job's acquire could land between the two calls, so
# this job's release could delete a *different* job's lock. Redis guarantees
# a single EVAL runs to completion without another command interleaving.
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class SyncAlreadyRunningError(Exception):
    """Raised when a sync is requested while another one already holds the
    lock. Carries the in-flight job's id so the caller can hand it back to
    the frontend instead of just saying no."""

    def __init__(self, in_flight_job_id: str):
        self.in_flight_job_id = in_flight_job_id
        super().__init__("A sync is already running.")


def _lock_key(user_id: UUID | None = None) -> str:
    return f"sync_lock:{user_id or 'global'}"


def acquire(job_id: str, user_id: UUID | None = None) -> bool:
    """Atomically claims the sync lock for job_id. True if acquired, False if
    another job already holds it. SET NX EX is atomic in Redis — no separate
    check-then-set race is possible between two concurrent requests."""
    return bool(_client.set(_lock_key(user_id), job_id, nx=True, ex=LOCK_TTL_SECONDS))


def get_holder(user_id: UUID | None = None) -> str | None:
    """The job_id currently holding the lock, or None if it's free."""
    return _client.get(_lock_key(user_id))


def release(job_id: str, user_id: UUID | None = None) -> None:
    """Releases the lock only if job_id still holds it. Safe to call even if
    the lock already expired or was never held by this job — a no-op, not an
    error, since every caller releases unconditionally in a finally block."""
    _client.eval(_RELEASE_SCRIPT, 1, _lock_key(user_id), job_id)
