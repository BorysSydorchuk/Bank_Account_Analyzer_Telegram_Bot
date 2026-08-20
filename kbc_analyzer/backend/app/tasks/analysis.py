"""Background version of the full sync pipeline (S3-04's categorization +
insight generation, joined by S4-02's Enable Banking fetch + store) — runs
everything POST /api/transactions/sync used to do inline, now entirely on
the celery_worker process so the API request can return almost immediately
regardless of how long Enable Banking or the LLM calls take.
"""
import asyncio
import logging
from datetime import date
from uuid import UUID

from .. import analysis_service, crud, job_store, sync_lock
from ..celery_app import celery_app
from ..db import SessionLocal
from ..eb_service import EnableBankingAuthError, EnableBankingError, EnableBankingService

logger = logging.getLogger(__name__)


@celery_app.task
def run_sync_job(job_id: str, date_from: str, date_to: str, user_id: str) -> None:
    """job_id: the key this task reports progress under (job:{job_id} in
    Redis, via job_store). date_from/date_to: ISO date strings — Celery
    serializes task arguments to JSON, so a date object wouldn't survive the
    trip; every caller passes .isoformat() and this converts them back.
    user_id: same reasoning, string form of the UUID (S6-06) — the
    authenticated user who requested this sync, threaded through the whole
    pipeline and stamped into every job_store status update so
    GET /api/jobs/{job_id} can check ownership.

    Celery tasks are plain synchronous functions, but the agents/provider
    code is async (it awaits HTTP calls to the LLM) — asyncio.run() is the
    bridge, same reasoning as the FastAPI routes needing `await` for the same
    calls.
    """
    asyncio.run(_run(job_id, date.fromisoformat(date_from), date.fromisoformat(date_to), UUID(user_id)))


async def _run(job_id: str, date_from: date, date_to: date, user_id: UUID) -> None:
    db = SessionLocal()
    # Tracked so the catch-all except below can report which stage an
    # unexpected exception actually interrupted, instead of a stage name
    # left over from before this task had more than one of them.
    current_stage = "fetching"
    try:
        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "user_id": str(user_id),                "status": "processing",
                "stage": "fetching",
                "progress": 0,
                "message": "Fetching transactions from KBC...",
            },
        )

        # Was a synchronous call inside the router before this ticket, where an
        # EnableBankingAuthError/EnableBankingError became an HTTP 401/502
        # straight from POST /sync. There's no HTTP response left to attach
        # that to once the fetch happens here instead — the job's own `error`
        # field is now what carries the same message the exception handlers
        # used to (S4-02's "auth errors surface through job status" requirement).
        eb = EnableBankingService()
        try:
            account_uids = eb.get_account_uids()
            fetched_by_account: list[tuple[str, list[dict]]] = []
            fetched = 0
            for account_uid in account_uids:
                txs = eb.fetch_transactions(account_uid, date_from, date_to)
                fetched += len(txs)
                fetched_by_account.append((account_uid, txs))
        except (EnableBankingAuthError, EnableBankingError) as exc:
            job_store.set_job(
                job_id,
                {"job_id": job_id, "user_id": str(user_id), "status": "failed", "stage": "fetching", "error": str(exc)},
            )
            return

        current_stage = "storing"
        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "user_id": str(user_id),                "status": "processing",
                "stage": "storing",
                "progress": 0,
                "message": f"Storing {fetched} transactions...",
            },
        )

        stored = duplicates_skipped = 0
        for account_uid, txs in fetched_by_account:
            account_stored, account_duplicates = crud.upsert_transactions(db, user_id, account_uid, txs)
            stored += account_stored
            duplicates_skipped += account_duplicates
        logger.info(
            "Sync job %s: fetched=%d stored=%d duplicates_skipped=%d", job_id, fetched, stored, duplicates_skipped
        )

        def on_batch_complete(completed_batches: int, total_batches: int) -> None:
            progress = round(completed_batches / total_batches * 100) if total_batches else 100
            job_store.set_job(
                job_id,
                {
                    "job_id": job_id,
                    "user_id": str(user_id),                    "status": "processing",
                    "stage": "categorizing",
                    "progress": progress,
                    "message": f"Categorizing batch {completed_batches} of {total_batches}...",
                },
            )

        current_stage = "categorizing"
        # The router already seeded job:{job_id} with a "fetching" state right
        # after enqueueing — so a poll that lands before this worker process
        # even picks up the task still gets a valid response instead of a
        # 404. That's immediately overwritten by this function's own first
        # set_job call above; nothing to re-seed here.
        categorization = await analysis_service.categorize_transactions(
            db, user_id, date_from, date_to, on_batch_complete=on_batch_complete
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
                    "user_id": str(user_id),                    "status": "failed",
                    "stage": "categorizing",
                    "error": categorization["error_message"]
                    or "Categorization failed for every transaction — the AI provider may be temporarily "
                    "unavailable or its usage quota may be exhausted. Try syncing again shortly.",
                },
            )
            return

        current_stage = "generating_insights"
        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "user_id": str(user_id),                "status": "processing",
                "stage": "generating_insights",
                "progress": 50,
                "message": "Generating insights...",
            },
        )

        insights = await analysis_service.generate_insights(db, user_id, date_from, date_to)

        # Only replace the persisted set on an actual successful generation
        # (S3-07 Item 3) — if this run's LLM call failed, the range keeps
        # whatever insights a previous successful sync left behind rather
        # than being wiped out by this run's failure.
        if insights["error_message"] is None:
            crud.replace_insights(
                db, user_id, date_from, date_to, insights["insights"], insights["provider"], insights["generated_at"]
            )

        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "user_id": str(user_id),                "status": "complete",
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
        logger.exception("Background sync job %s failed unexpectedly during %s", job_id, current_stage)
        job_store.set_job(
            job_id,
            {
                "job_id": job_id,
                "user_id": str(user_id),                "status": "failed",
                "stage": current_stage,
                "error": "Something went wrong while processing this sync. Please try again.",
            },
        )
    finally:
        # S5-05: released on every exit path — success, a handled failure
        # (either early-return above), or the catch-all except block — so a
        # normal-completing job never holds the lock past its own finish.
        # A worker that crashes hard enough to skip even this (killed, not
        # raising) leaves the lock to expire on its own TTL instead; that's
        # the deliberate backstop, not a gap this line is meant to cover.
        sync_lock.release(job_id, user_id)
        db.close()
