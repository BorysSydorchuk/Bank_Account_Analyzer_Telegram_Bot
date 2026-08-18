Status: confirmed
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

## WHEN DONE — answered (2026-08-18, all live against the real stack):

**Two concurrent syncs → one job + a 409, with the in-flight job_id:**
Fired a real sync (`job_id: e682a4e0-...`), then immediately a second —
`409 {"message":"A sync is already running.","job_id":"e682a4e0-..."}`,
the same job_id as the first, not a new one. Repeated later while the
worker was dead (job `af7b9a1c-...`) with the same result — the lock
doesn't care whether the holder is alive, only whether it's still held.
Also reproduced through the real frontend (two browser tabs, then a
Redis-seeded held lock against a live tab click): `POST
/api/transactions/sync` → `409`, and `useDashboard.ts`'s `onError`
(`SyncConflictError` branch) attached to the in-flight job's polling
instead of showing an error toast — button stayed in its normal syncing
state, status line showed the in-flight job's real message
("Categorizing batch 2 of 5..."), no toast, no console errors.

**Killed worker → failed with correct stage:** started a real sync,
`docker compose kill celery_worker` within ~1s (job frozen at stage
`fetching`). `GET /api/jobs/{job_id}` kept returning `status: "processing"`
until the heartbeat crossed the 2-minute staleness threshold, then
flipped to `{"status":"failed","stage":"fetching","error":"Processing
stopped unexpectedly during fetching transactions — please try again."}`
— correct stage, no polling required past that point.

**Lock releases after a crash — post-TTL sync succeeds:** confirmed via
Redis directly (`TTL sync_lock:global`) that the lock stayed held (509s →
64s → ...) the entire time the crash-detection above was already
reporting `failed` — the two mechanisms are genuinely independent, as
documented in ARCHITECTURE.md. Polled Redis until the key's TTL expired
naturally (~9 more minutes, no code released it — the worker was still
dead), then fired a new sync: `200`, new `job_id`, normal processing.
Brought `celery_worker` back up afterward; it picked up the queued
message from its restart and completed normally, confirming Celery
itself also recovers cleanly once a worker returns.

**Lock released on success and failure paths:** `sync_lock.release()`
sits in a single `finally` block wrapping the task's entire `try` body
(`tasks/analysis.py`) — the same `finally` that already runs `db.close()`
on every path, whether that's the success return, either of the two
early-return failure paths (Enable Banking error, "every categorization
batch failed"), or the catch-all `except Exception`. Python's `finally`
runs on all of those unconditionally; the success path was directly
live-verified (a completed job's lock released immediately, next sync
got `200` right away) — didn't force the two `job_store.set_job(...,
"failed")` early-return branches individually via live faults, since
doing so would mean deliberately breaking the live Enable Banking session
or the LLM provider key, which isn't something to do unilaterally per
CLAUDE.md's testing standard on destructive verifications. The one path
that does **not** release the lock — a hard kill, no exception raised at
all — was the crash test above, and that's by design: it's the TTL's job,
not `finally`'s.

**Why Redis for the lock, not a database row or an in-process lock?**
An in-process lock (a Python-level `threading.Lock`, say) only holds
within one process — `backend` (uvicorn) and `celery_worker` are
separate containers/processes, and the lock genuinely needs to be
visible across both: `backend` acquires it in the router, and only
`celery_worker`'s task knows when to release it. A database row would
work for correctness but adds a table this state doesn't deserve — it's
the same reasoning `job_store.py`'s own docstring already gives for
Redis over Postgres for job status ("this state only matters while a
sync's background work is in flight or freshly finished, never queried
historically"), and it would need its own TTL-equivalent (a cron
sweeping stale rows, or a `CHECK`-constrained expiry column) to get the
same "cannot deadlock forever" guarantee Redis's `EX` gives for free.
Redis is also already the broker/backend for the exact Celery task this
lock coordinates, and already holds the job state the lock's value
(`job_id`) points back into — one less moving part, one less connection
to manage, for a lock that's meant to be ephemeral by nature anyway.

**Flag to the Tester agent (S5-04's suite extension, not built here):**
- `sync_lock.acquire()`/`release()` unit-level: NX-acquire refuses a
  second acquire while held; release only clears the key if the caller's
  job_id still owns it (the Lua compare-and-delete) — a release call from
  a job that no longer holds the lock (already expired, already
  reassigned) must be a safe no-op, not an accidental delete of a
  different job's lock. Both are easy to construct directly against a
  real (or fakeredis) Redis instance without touching the HTTP layer.
- `POST /api/transactions/sync` integration: first call 200s and creates
  a job; an immediate second call 409s with the first call's job_id;
  after the first job reaches `done`/`failed`, a third call 200s again
  immediately (not waiting on TTL).
- `GET /api/jobs/{job_id}` staleness: a job manually seeded in Redis with
  a `heartbeat_at` older than `STALE_THRESHOLD_SECONDS` reads back as
  `failed` with the stage-specific message; one with a fresh heartbeat
  stays `processing` unchanged.
- Full lifecycle integration (the one genuinely worth a real Celery
  worker in the test environment, not just Redis fakes): start a sync,
  kill/never-start the worker, poll until the staleness threshold trips,
  assert the failure message names the right stage, then assert the lock
  itself only frees at TTL expiry (not at the moment staleness was
  detected) — this ordering is the one behavior in this ticket most
  likely to regress silently if someone "helpfully" makes staleness
  detection release the lock early later.
