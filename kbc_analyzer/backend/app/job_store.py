"""Transient background-job status storage in Redis (S3-04) — `job:{job_id}`
keys holding the JSON blob GET /api/jobs/{job_id} serves, each with a 24-hour
TTL. Deliberately not PostgreSQL: this state only matters while a sync's
background work is in flight or freshly finished, never queried historically,
so it doesn't belong in the durable, backed-up database.
"""
import json
import os
from datetime import datetime, timezone

import redis

JOB_TTL_SECONDS = 24 * 60 * 60

_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def set_job(job_id: str, status: dict) -> None:
    """Overwrites the job's status wholesale and resets its 24h TTL — callers
    always pass the complete status object, not a partial patch.

    Stamps heartbeat_at (S5-05) on every call, not just a dedicated "still
    alive" ping — every stage transition and every categorization batch
    already calls this, so it's already the natural checkpoint frequency a
    separate heartbeat mechanism would have had to invent. GET
    /api/jobs/{job_id} uses this to detect a worker that died mid-job: no
    write means no progress, however long it's actually been running.
    """
    payload = {**status, "heartbeat_at": datetime.now(timezone.utc).isoformat()}
    _client.set(_job_key(job_id), json.dumps(payload), ex=JOB_TTL_SECONDS)


def get_job(job_id: str) -> dict | None:
    """None means the job never existed or its 24h TTL has expired — the
    router treats both the same way, as 404."""
    raw = _client.get(_job_key(job_id))
    return json.loads(raw) if raw is not None else None
