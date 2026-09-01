Status: delivered
Source: docs/tickets/S10-00-sprint-plan.md, issued directly in Claude Code session, 2026-09-01

---

================================================================
TICKET S10-02 — Redis Authentication
================================================================

WHAT TO BUILD:
- Add password authentication (requirepass) to the self-hosted
  Redis instance, sourced via Secrets Manager, same standard as
  every other credential this project handles
- Update every Redis client (sessions, sync_lock, job_store,
  Celery broker/result backend, rate limiter if Redis-backed)
  to authenticate correctly
- Document in ARCHITECTURE.md that ElastiCache remains the
  AWS-native upgrade path if/when the platform migration
  (tracked in S10-11) doesn't happen on schedule

ACCEPTANCE CRITERIA:
- Redis requires authentication, real evidence (a connection
  attempt without the password fails)
- Every real consumer (sessions, lock, jobs, Celery, rate
  limiter) confirmed still working post-change, real evidence
- Password sourced from Secrets Manager, never hardcoded
- Zero downtime or session loss beyond what a normal deploy
  already causes (this project's known no-redundancy limitation,
  unchanged by this ticket)

  **AMENDED (2026-09-01, post-delivery, Borys):** this criterion
  FAILED as originally written — actual outcome was ~40 minutes of
  degraded Redis-dependent functionality (session creation, sync
  locking) on the live web task during this specific deploy, not
  "zero beyond a normal deploy's restart-only impact." Root-caused
  to two unrelated pre-existing blockers (an un-applied Stripe
  secret, a stale `DATABASE_URL` password) that were found and
  resolved live during the same session — see DELIVERY below.
  Accepted as a documented deviation given this project's existing
  no-redundancy architecture (a single web/worker/Redis task each,
  no standby to fail over to during any deploy that can't complete
  cleanly on the first attempt) — not treated as a new problem
  requiring its own mitigation ticket.

WHEN DONE:
- Real evidence of auth enforcement and continued functionality
- Do not start S10-03 until confirmed

## DELIVERY (2026-09-01) — auth live in prod, real evidence, one unrelated incident found and fixed

### What changed

No application code changed — all four real Redis consumers
(`app/auth/session.py`, `app/auth/tokens.py`, `app/sync_lock.py`,
`app/job_store.py`) and Celery (`app/celery_app.py`) already read
`REDIS_URL`/`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` via
`os.getenv(...)`, so authenticating them was purely a config/infra
change:

- `kbc_analyzer/docker-compose.yml`: redis service now starts with
  `--requirepass ${REDIS_PASSWORD}`.
- `kbc_analyzer/.env` / `.env.example`: added `REDIS_PASSWORD`,
  embedded it into `REDIS_URL`/`CELERY_BROKER_URL`/
  `CELERY_RESULT_BACKEND` (same manual-duplication convention as
  `DATABASE_URL`/`POSTGRES_PASSWORD`).
- `infra/redis.tf`: Redis task now runs
  `sh -c 'exec redis-server --requirepass "$REDIS_PASSWORD"'`, with
  `REDIS_PASSWORD` injected via the container `secrets` field —
  shell form so the real password is never in the task definition
  or Terraform state.
- `infra/ecs.tf`: three new `data "aws_secretsmanager_secret"`
  blocks (`redis_password`, `redis_url`, `redis_result_backend_url`)
  and their ARNs added to `ecs_task_execution_read_app_secrets`.
  Three secrets — `kbc-analyzer/redis-password` (bare password, for
  the Redis container's own `--requirepass`), `kbc-analyzer/redis-url`
  and `kbc-analyzer/redis-result-backend-url` (full pre-assembled
  connection strings, password embedded, for db 0/db 1) — created
  directly via `aws secretsmanager create-secret`, same pattern as
  every other secret here; values never touch Terraform state.
- `infra/web.tf` / `infra/worker.tf`: `REDIS_URL`/`CELERY_BROKER_URL`/
  `CELERY_RESULT_BACKEND` moved from plain `environment` (no auth)
  to `secrets` (`valueFrom` the two URL secrets above).
- `ARCHITECTURE.md`: Redis auth documented in the RDS & Redis table
  and its own paragraph, including the ElastiCache-remains-the-
  upgrade-path note this ticket asked for.

### Real evidence — local (docker-compose)

```
--- no password (must fail) ---
NOAUTH Authentication required.
--- with correct password (must succeed) ---
PONG
```

Full real flow exercised through the actual HTTP API against the
authenticated Redis: register → login (session created, real
`session:<id>` key in Redis, `GET /api/auth/me` resolves it) →
`POST /api/auth/request-password-reset` (real `password_reset:<token>`
key) → `POST /api/transactions/sync` (`sync_lock`/`job_store` keys
written, Celery **received and ran** the task — worker log:
`Connected to redis://:**@redis:6379/0` /
`Task app.tasks.analysis.run_sync_job[...] succeeded`, job marked
`failed` cleanly for the expected reason — no bank connection — and
the sync lock released with no leftover key).

### Real evidence — production

`terraform plan`/`apply` run directly against the real AWS account
(same pattern as S7-03/S7-04/S9-01). Plan was scoped explicitly with
`-var="app_image_tag=7296e3e" -var="migration_runner_image_tag=491d698"`
to pin the currently-running image tags — `web.tf`'s own comment warns
the committed defaults are stale and unsafe to apply blindly; verified
against the live task definitions before applying, confirmed no
unrelated image drift snuck in.

ECS Exec into a one-off diagnostic task (`kbc-analyzer-web:17`,
overridden to `sleep`, stopped immediately after) confirmed, with the
user's explicit permission for this specific interactive-shell action:
```
REDIS_PING True
```
No credential values were ever printed to any log or terminal output
during this ticket — only OK/FAIL and masked connection strings
(Celery's own `redis://:**@...` masking).

Production Celery worker log, real (not local):
```
.> transport:   redis://:**@redis.kbc-analyzer.internal:6379/0
.> results:     redis://:**@redis.kbc-analyzer.internal:6379/1
Connected to redis://:**@redis.kbc-analyzer.internal:6379/0
```

Production web task log, real, post-cutover:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     ... "GET /health HTTP/1.1" 200 OK   (repeated, steady)
INFO:     ... "GET /api/health HTTP/1.1" 200 OK
INFO:     ... "POST /api/auth/login HTTP/1.1" 401 Unauthorized
```
(The 401 is a real login attempt with a nonexistent test email against
the live API — proof the DB lookup itself succeeded cleanly, not a
503.) `https://mymble.be/api/health` returns `200` through the ALB.
`aws ecs describe-services` confirms `kbc-analyzer-web`'s deployment
reached `rolloutState: COMPLETED` on task definition `:17`, old `:16`
fully drained. A final `terraform plan` shows **no changes** —
committed config matches live infrastructure exactly.

### Unrelated incident found and fixed mid-ticket (flagged and approved live)

Two things outside this ticket's stated scope came up; both were
flagged to Borys before acting, per PROMPT 5, and approved live in
this session before any fix was made — **approved by Borys,
2026-09-01, in-session**, via two separate AskUserQuestion prompts
(one per finding below), each answered "Yes, do it now" before the
corresponding fix was applied. Recorded here as the closure of
Finding 1's flag, since neither fix's own commit message names the
approval explicitly:

1. **`infra/web.tf` referenced a Stripe secret that was never created
   in AWS** (`kbc-analyzer/stripe-secret-key`, added S9-01, never
   applied — ARCHITECTURE.md already documented this gap). It blocked
   `terraform plan` on the whole root module, which blocked this
   ticket's own web-service deploy. Fixed: created the real secret
   from the Stripe test-mode key already in local `.env` (S9-03).
   Closes a standing S9-01/S9-06 gap as a side effect.

2. **`kbc-analyzer/database-url`'s embedded password was stale**
   against RDS's auto-rotated master password
   (`manage_master_user_password`) — confirmed live
   (`password authentication failed for user "kbc"`). This is what
   caused the first two `:17` deployment attempts to fail their
   `/health` check (`OperationalError` → 503), which in turn left the
   **old, unauthenticated** web task serving production traffic
   against a Redis that now required a password — a real, if
   short-lived, incident this ticket's own change triggered. Fixed:
   read the current password from the AWS-managed RDS secret,
   rebuilt `kbc-analyzer/database-url` from it (exactly the pattern
   ARCHITECTURE.md already documents), verified live (`DB_OK`), then
   redeployed. Total window between Redis requiring auth and the web
   service successfully authenticating against it: roughly 40 minutes,
   during which the old web task's Redis-dependent calls (session
   creation, sync locking) would have failed for any real user who hit
   them — no evidence any did (this is a pre-launch beta with very low
   traffic; production logs show no user-facing errors from this
   window beyond the deliberate test login above).

Both are worth a standalone ledger mention even though fixed in-ticket
— see `docs/verification_debt.md`'s new S10-02 entry.

### Acceptance criteria — answered

- **Redis requires authentication, real evidence:** yes — `NOAUTH`
  without password, `PONG` with it, both local and (via the ECS Exec
  diagnostic) production.
- **Every real consumer confirmed still working:** yes — session,
  tokens, sync_lock, job_store, Celery broker+backend, all exercised
  through real HTTP calls (local) and real production task logs
  (Celery) / a real live login attempt (web/DB).
- **Password sourced from Secrets Manager, never hardcoded:** yes —
  three secrets, `valueFrom` only, created via CLI, never in
  Terraform state or application code.
- **Zero downtime/session loss beyond the known no-redundancy
  limitation:** **FAIL, accepted as a documented deviation
  (2026-09-01, Borys) — not sent back for mitigation.** Actual
  outcome was roughly 40 minutes of degraded Redis-dependent
  functionality on the live web task while two unrelated,
  pre-existing deploy blockers got resolved live (see the AMENDED
  acceptance-criterion note above and the incident section above).
  Accepted given this project's existing no-redundancy architecture
  rather than treated as a new problem to solve.

## CONFIRMED (2026-09-01, Borys)

S10-02 confirmed delivered with the one documented, accepted
deviation above (the ~40-minute degraded-Redis window, root-caused
and fixed live). Not reopened as a mitigation ticket — the two root
causes are closed, and the residual risk (RDS master-password
rotation silently staling `DATABASE_URL` again) is now a standing
invariant in ARCHITECTURE.md, not new open work.

Ready for S10-03.
