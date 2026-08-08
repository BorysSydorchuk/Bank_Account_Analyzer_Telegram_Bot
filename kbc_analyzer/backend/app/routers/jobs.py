"""GET /api/jobs/{job_id} — background sync job status (S3-04)."""
from fastapi import APIRouter, HTTPException

from .. import job_store
from ..schemas import JobStatusResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    """Returns whichever of the processing/complete/failed shapes matches the
    job's current state in Redis. A missing job means it never existed or its
    24h TTL expired — both read the same to the caller.
    """
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired. Try syncing again.")
    return job
