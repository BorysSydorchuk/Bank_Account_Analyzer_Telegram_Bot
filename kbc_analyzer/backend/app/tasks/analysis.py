"""Background version of analysis_service's work (S3-04) — runs the real
categorization + insight generation that used to run inline inside
POST /api/transactions/sync, now on the celery_worker process so the API
request returns immediately after fetch + store.
"""
import asyncio
import logging
from datetime import date

from .. import analysis_service, job_store
from ..celery_app import celery_app
from ..db import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task
def categorize_and_analyze(job_id: str, date_from: str, date_to: str) -> None:
    """job_id: the key this task reports progress under (job:{job_id} in
    Redis, via job_store). date_from/date_to: ISO date strings — Celery
    serializes task arguments to JSON, so a date object wouldn't survive the
    trip; every caller passes .isoformat() and this converts them back.

    Celery tasks are plain synchronous functions, but the agents/provider
    code is async (it awaits HTTP calls to the LLM) — asyncio.run() is the
    bridge, same reasoning as the FastAPI routes needing `await` for the same
    calls.
    """
    asyncio.run(_run(job_id, date.fromisoformat(date_from), date.fromisoformat(date_to)))


async def _run(job_id: str, date_from: date, date_to: date) -> None:
    db = SessionLocal()
    try:
        def on_batch_complete(completed_batches: int, total_batches: int) -> None:
            progress = round(completed_batches / total_batches * 100) if total_batches else 100
            job_store.set_job(
                job_id,
                {
                    "job_id": job_id,
                    "status": "processing",
                    "stage": "categorizing",
                    "progress": progress,
                    "message": f"Categorizing batch {completed_batches} of {total_batches}...",
                },
            )

        # The router already seeded job:{job_id} with this same "starting"
        # state right after enqueueing — so a poll that lands before this
        # worker process even picks up the task still gets a valid response
        # instead of a 404. Nothing to re-seed here; on_batch_complete below
        # is the first real update.
        categorization = await analysis_service.categorize_transactions(
            db, date_from, date_to, on_batch_complete=on_batch_complete
        )

        # error_message is only set when categorization couldn't run at all
        # (no API key configured) — analysis_service already crafts this as a
        # safe, user-facing message, so it's fine to surface directly.
        #
        # A batch that raises (a quota-exhausted or momentarily-overloaded
        # LLM, say) is logged and skipped rather than raised further, by
        # design (see CategorizationAgent.run()) — a couple of failed batches
        # out of several should still leave the job "complete" with a lower
        # categorized count. But if EVERY batch failed, that's functionally
        # the same as the provider being unavailable, and reporting
        # "complete, 0 categorized" with no explanation would fail silently
        # instead of telling the user anything useful.
        every_batch_failed = categorization["categorized"] == 0 and categorization["failed"] > 0
        if categorization["error_message"] or every_batch_failed:
            job_store.set_job(
                job_id,
                {
                    "job_id": job_id,
                    "status": "failed",
                    "stage": "categorizing",
                    "error": categorization["error_message"]
                    or "Categorization failed for every transaction — the AI provider may be temporarily "
                    "unavailable or its usage quota may be exhausted. Try syncing again shortly.",
                },
            )
            return

        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "status": "processing",
                "stage": "generating_insights",
                "progress": 50,
                "message": "Generating insights...",
            },
        )

        insights = await analysis_service.generate_insights(db, date_from, date_to)

        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "status": "complete",
                "stage": "done",
                "progress": 100,
                "categorized": categorization["categorized"],
                "insights": insights["insights"],
                "insights_provider": insights["provider"],
                "insights_generated_at": insights["generated_at"].isoformat(),
                "insights_error_message": insights["error_message"],
                "message": (
                    f"Done — {categorization['categorized']} transactions categorized, "
                    f"{len(insights['insights'])} insights generated"
                ),
            },
        )
    except Exception:
        # Never surface the raw exception to the job's `error` field — it's
        # user-facing (rendered as a toast), not a debug log. The real
        # exception still goes to the worker's own logs for us to debug.
        logger.exception("Background sync job %s failed unexpectedly", job_id)
        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "status": "failed",
                "stage": "categorizing",
                "error": "Something went wrong while processing this sync. Please try again.",
            },
        )
    finally:
        db.close()
