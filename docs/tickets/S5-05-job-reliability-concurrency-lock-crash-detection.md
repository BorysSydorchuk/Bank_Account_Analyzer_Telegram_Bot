Status: in-progress
Source: issued directly in Claude Code session, 2026-08-18

---

================================================================
TICKET S5-05 — Job Reliability: Concurrency Lock & Crash
                 Detection
================================================================

FIRST, BEFORE THE MAIN WORK: add the retention comment to
colors.py per the flagged S5-04 finding (your memory should
have surfaced this already) — one line above the
lightness>55% check: "Currently unreachable within the
valid 40-80% saturation range: contrast against white always
fails first before lightness reaches this bound. Kept as
defense in depth in case the saturation bounds change."
Commit that separately first: docs: annotate unreachable
color-lightness branch (S5-04 finding).

BACKGROUND:
Two known gaps, both documented in ARCHITECTURE.md:
(1) No server-side lock on sync — two browser tabs or a
retry can run two sync jobs concurrently, double-running
categorization and insight generation on the same range
(found during S4-03's audit).
(2) If the Celery worker crashes mid-job, the job freezes
on its last written stage forever; only the frontend's
10-minute timeout surfaces it, as a generic "taking longer
than expected" (found in S4-02).

WHAT TO BUILD:

Part 1 — Sync concurrency lock:
  A Redis-based lock preventing concurrent sync jobs.
  - Key: sync_lock (scoped per user once Sprint 6 lands —
    write the key derivation so adding user_id later is a
    one-line change, per the S5-01 migration plan)
  - Acquired when a sync job is created, released when the
    job reaches done or failed
  - TTL slightly longer than the frontend's 10-minute
    timeout, so a crashed worker cannot deadlock sync
    permanently
  - POST /api/transactions/sync returns 409 with a clear
    message if a sync is already running, including the
    in-flight job_id so the frontend can attach to it
  - Frontend: on 409, attach to the existing job's polling
    rather than showing an error — the user clicked sync,
    a sync is happening, that is not an error state

Part 2 — Worker crash detection:
  - The Celery task writes a heartbeat timestamp into its
    Redis job state at each stage transition and
    periodically during long stages (categorization
    batches are the natural checkpoint)
  - GET /api/jobs/{job_id} computes staleness: if the job
    is not done/failed and the heartbeat is older than a
    threshold (suggest 2 minutes, justify your choice),
    return status=failed with a message naming the stage
    it died in ("Processing stopped unexpectedly during
    categorization — please try again")
  - The frontend's 10-minute timeout remains as a
    backstop, but should now rarely be what surfaces a
    crash

ACCEPTANCE CRITERIA:
- Two concurrent sync requests: the second gets 409 with
  the in-flight job_id, not a second job
- The frontend attaches to the existing job on 409
- Killing the celery_worker mid-job causes GET /api/jobs
  to report failed with the correct stage within the
  staleness threshold
- The lock is released on both success and failure paths
- The lock TTL cannot deadlock sync permanently (test
  this: kill the worker holding the lock, confirm sync
  works again after TTL expiry)
- Flag to the Tester agent afterward: these behaviors need
  integration tests over the job lifecycle — don't build
  them yourself, but scope them clearly in your delivery
  notes so S5-04's suite can be extended

WHEN DONE:
- Show two concurrent syncs producing one job + a 409
- Show a killed worker surfacing as failed with the
  correct stage
- Show the lock releasing after a crash (post-TTL sync
  succeeds)
- Explain: why Redis for the lock rather than a database
  row or an in-process lock?
- Do not start S5-06 until confirmed
