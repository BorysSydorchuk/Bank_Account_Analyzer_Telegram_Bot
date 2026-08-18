"""GET /api/jobs/{job_id} — background sync job status (S3-04)."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from .. import job_store
from ..schemas import JobStatusResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# S5-05: how long a "processing" job can go without a heartbeat before it's
# treated as a dead celery_worker rather than a slow one. Heartbeats land on
# every stage transition and every categorization batch (job_store.set_job's
# docstring) — the one stage with no intra-stage checkpoint at all is
# generating_insights, a single LLM call with no per-chunk progress to hook
# a heartbeat into. 2 minutes gives that single call real room (the S4-06
# live-verified Gemini run completed multi-turn chat exchanges in low tens
# of seconds each) while still surfacing a genuine crash far sooner than the
# frontend's 10-minute poll timeout, which this is meant to make rare rather
# than replace.
STALE_THRESHOLD_SECONDS = 2 * 60

_STAGE_LABELS = {
    "fetching": "fetching transactions",
    "storing": "storing transactions",
    "categorizing": "categorization",
    "generating_insights": "insight generation",
}


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    """Returns whichever of the processing/complete/failed shapes matches the
    job's current state in Redis. A missing job means it never existed or its
    24h TTL expired — both read the same to the caller.

    A "processing" job whose heartbeat has gone stale (STALE_THRESHOLD_SECONDS)
    is reported as failed here rather than left to poll forever — the most
    likely cause is a celery_worker that crashed or was killed mid-job, which
    otherwise only ever surfaces via the frontend's 10-minute give-up timer as
    a generic "taking longer than expected." This is a read-time computation,
    not a write to Redis: the job's own sync_lock still only releases on its
    own TTL (see tasks/analysis.py), so a fast client retry right after seeing
    this "failed" status can still hit a 409 until the lock expires — a
    deliberate, ticket-scoped tradeoff, not an oversight.
    """
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired. Try syncing again.")

    if job.get("status") == "processing":
        heartbeat_at = datetime.fromisoformat(job["heartbeat_at"])
        age_seconds = (datetime.now(timezone.utc) - heartbeat_at).total_seconds()
        if age_seconds > STALE_THRESHOLD_SECONDS:
            stage = job.get("stage", "processing")
            job = {
                "job_id": job_id,
                "status": "failed",
                "stage": stage,
                "error": f"Processing stopped unexpectedly during "
                f"{_STAGE_LABELS.get(stage, stage)} — please try again.",
            }

    return job