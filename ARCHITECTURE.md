# ARCHITECTURE.md

Current-state record of the KBC Personal Finance Analyzer. Describes what
**is**, never what was or what's planned — see git history for the former,
sprint tickets for the latter. Project root is `kbc_analyzer/`; all paths
below are relative to it unless stated otherwise.

**Verification note:** Services & Ports below verified live 2026-08-17
(S4-10 sprint close) via `docker compose ps` against a clean
`docker compose down && docker compose up -d` — all five containers
healthy, port bindings match exactly. (Originally written S4-03 against
static config only, since Docker Desktop's daemon wasn't running then;
that gap is now closed.)

**Sprint 5 close re-verification (2026-08-19, S5-08):** every claim in this
file re-checked against the running system and current source, top to
bottom — non-root UIDs confirmed live (`docker compose exec backend
whoami` / `celery_worker` → `appuser`), every referenced symbol name
confirmed to still exist at its stated location, Database Tables
cross-checked against `models.py` column-by-column (no drift), sync-lock
enforcement re-confirmed live. All line-number references (`file.py:NN`)
replaced with stable section/symbol names throughout this file — line
numbers had already gone stale twice during Sprint 4 and are no longer
used as anchors here.

## Services & Ports

| Service | Image/build | Port | Serves |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | Postgres, `pg_isready` healthcheck |
| `backend` | `backend/Dockerfile` | 8000 | FastAPI (`app.main:app`); runs `alembic upgrade head` then `uvicorn --reload` on every start |
| `frontend` | `frontend/Dockerfile` | 5173 | Vite dev server |
| `redis` | `redis:7-alpine` | 6379 | Celery broker (db 0) + result backend (db 1) |
| `celery_worker` | `backend/Dockerfile` (same image as backend) | **3001** | `celery -A app.celery_app worker`, **and** the Enable Banking OAuth callback catcher |

`celery_worker`, not `backend`, publishes port 3001 — deliberate
(`docker-compose.yml`'s `celery_worker` service, `ports:` mapping): the OAuth redirect lands in the user's real
browser on the host, and the catcher (`app/eb_callback_server.py`) runs
inside the Celery process (`app/tasks/auth.py`), not the FastAPI process.
It's a Celery task (`catch_enable_banking_callback`), TLS via
`certs/localhost.pem`/`localhost-key.pem` (mkcert, expires 2028-11-08 —
regenerate or retire per Sprint 6 production HTTPS), handles exactly one
request then shuts down, and raises `CallbackPortBusyError` if a second
reconnect races the first.

`backend` and `celery_worker` both run as a non-root `appuser`
(`backend/Dockerfile`, S4-09 Item 1) — the image's final `USER appuser`
directive, after dependencies are installed and the source is copied as
root. Verified this doesn't break `eb_session.json`/cert access: Docker
Desktop's Windows bind mounts report `rwxrwxrwx` regardless of the
container's UID, so this isn't the classic root-owned-files failure mode a
native Linux host would hit — worth re-verifying if this project ever runs
on a Linux Docker host.

`frontend`'s Vite dev server watches with polling (`vite.config.ts`,
S4-09 Item 2: `usePolling: true, interval: 1000`) — Docker Desktop's
bind-mounted volumes don't reliably deliver native filesystem change
events into the container, so the default watcher silently missed edits
without this.

`backend` has `logging.basicConfig(level=logging.INFO, ...)` (`main.py`,
S4-09 Item 3) — before this, the uvicorn process had no logging
configuration at all, so every `logger.info()` call anywhere in the app
was silently dropped for it (Python's root-logger fallback only emits
WARNING+). `celery_worker` never had this problem — its `--loglevel=info`
CLI flag already configures its own root logger.

## URLs & Redirects

| URL | Value | Served by |
|---|---|---|
| Enable Banking redirect URI | `https://localhost:3001/callback` | `celery_worker` / `app/eb_callback_server.py`'s `CALLBACK_PORT` constant |
| Frontend origin (CORS) | `FRONTEND_ORIGIN`, default `http://localhost:5173` | `backend/app/main.py`'s `CORSMiddleware` setup |
| Frontend's API base | `VITE_API_URL`, default `http://localhost:8000` | `frontend/src/lib/api.ts`'s `API_URL` constant, injected via compose, no `.env` file on disk |

The redirect URI must be `https://` — Enable Banking's `/auth` endpoint
rejects `http://` live (400), which is why the mkcert cert exists.
`POST /api/auth/enable-banking/callback` is a manual fallback only; the
frontend no longer calls it now that reconnect auto-catches the redirect.

Live-verified end-to-end 2026-08-17 (S4-10 step m, with Borys completing
the real KBC login himself — Codee never handles bank credentials):
`SessionBanner.tsx`'s warning threshold was temporarily raised so the
real (not-actually-expiring) session tripped the banner without faking
anything; after a real reconnect, `GET /api/auth/enable-banking/status`
returned a genuinely new ~90-day expiry, auto-caught by the port-3001
callback catcher with zero copy-paste — confirming this flow works
exactly as described above, not just as designed.

## Data Flow

`POST /api/transactions/sync` (`routers/transactions.py`) does almost
nothing synchronously: creates a `job_id`, acquires `sync_lock` (S5-05,
below) for it, seeds Redis with `{"status": "processing", "stage":
"fetching"}`, dispatches `run_sync_job.delay(...)`, returns immediately.
If the lock is already held, no job is created — the endpoint raises
`SyncAlreadyRunningError`, mapped by `main.py`'s
`sync_already_running_handler` to `409 {"message": ..., "job_id":
<in-flight job's id>}`.

Celery task `run_sync_job` (`tasks/analysis.py`) runs the pipeline,
updating the Redis job record as it progresses:
`fetching` → `storing` (`crud.upsert_transactions`, upsert on
`external_id` conflict) → `categorizing` (batch progress reported via
`on_batch_complete`) → `generating_insights` (only on success does
`crud.replace_insights` run — a failed generation leaves prior insights
untouched) → `complete`/`failed`. `sync_lock.release()` runs in a
`finally` block around the whole task (S5-05) — released on every path
that returns or raises inside the task; a worker killed hard enough to
skip even that leaves the lock to its own TTL instead (see Invariants).

Job state lives only in Redis (`job_store.py`, key `job:{job_id}`, 24h
TTL) — never Postgres. Every `job_store.set_job` call (every stage
transition, every categorization batch) also stamps `heartbeat_at`
(S5-05). `GET /api/jobs/{job_id}` 404s once the key expires; while a job
is `processing`, it also checks `heartbeat_at` against a 2-minute
staleness threshold and reports `status: "failed"` (naming the stage) if
exceeded — this is computed at read time, not written back to Redis, and
does not itself release `sync_lock` (see Invariants).

Frontend polling (`frontend/src/hooks/useDashboard.ts`): `useQuery` with
`refetchInterval` of 2s while `status === "processing"`,
`refetchIntervalInBackground: true`, plus an independent `setTimeout`
enforcing a 10-minute cap — now mostly a backstop behind the 2-minute
server-side staleness check above, kept because it also covers a job
whose Redis key vanished outright (React Query's structural sharing means
a dead worker never produces a new `data` reference to key an effect
off, so a plain state-comparison effect can't detect it either). On a
sync request's `409`, the frontend attaches to the in-flight job's
polling instead of showing an error (`useDashboard.ts`'s
`syncMutation.onError`, `SyncConflictError`) — the user asked for a sync,
one is already running, that's not a failure.

`POST /api/chat` (`routers/chat.py`, S4-06) streams a chat reply as
Server-Sent Events. `chat_service.start_chat_stream` runs everything
synchronous first — resolves the configured provider
(`agents/registry.get_provider`) and assembles a fresh financial context
(last-90-days summary, last 20 transactions, active budgets, all read
straight from Postgres, never cached) — so a missing API key is a normal
400 JSON error, not a broken stream. Only then does
`ChatAgent.stream()` (`agents/chat.py`) start yielding tokens from
`LLMProvider.stream_complete()`, forwarded one SSE frame per chunk
(`{"token": ..., "done": false}`), ending with
`{"token": "", "done": true, "usage": {...}}`. Conversation history is
entirely client-held — the backend is stateless across turns; no
`chat_messages` table exists.

Live-verified 2026-08-16 (Gemini, real 331-row dataset): tokens arrive as
separate incremental frames, not one flush; a 3-turn conversation correctly
built on prior turns; every number the assistant computed from the summary/
category/budget context matched `GET /api/statistics` and `GET /api/budgets`
exactly. That first run surfaced a real gap: the "last 20 transactions"
section is a small slice of a much larger summary window (293 transactions
fell in the 90-day window tested), so a "what was my single biggest
expense" question couldn't be answered from it — the assistant correctly
said so rather than guessing. Review caught that this was a one-line
omission, not a design limitation: `compute_statistics()` already returns
`summary.biggest_expense`, and `_summary_text()`
just wasn't surfacing it. Fixed in-ticket (S4-06 review bounce,
2026-08-17) — `summary_text` now includes a `Biggest expense: ...` line,
re-verified live against the same dataset: exact match on amount,
merchant, and date.

Frontend consumption (`frontend/src/pages/ChatPage.tsx` + `lib/api.ts`'s
`streamChat`, S4-07): plain `fetch` with `response.body.getReader()`, not
`EventSource` — `EventSource` only supports GET, and this endpoint needs a
POST body (message + history). `useChatSession` (a hook, not React Query —
there's nothing here to cache) owns the message list as plain React state;
history is never persisted, matching the backend's statelessness.

`GET /api/insights/compare` (`routers/insights.py`, `comparison_service.py`,
S4-08) computes spending deltas between two arbitrary date ranges.
`total_spent`/`by_category` for both ranges are always computed live from
`transactions` via `statistics.compute_statistics` — never read from a
stored snapshot. `insights` per range are read from the `insights` table
exactly as stored for that exact range (the S4-04 Option B decision) and
never generated on the fly; a range with no matching stored insights just
returns an empty list, labeled `insights_generated_at: null`. Both ranges
are validated (`date_from <= date_to`, ≤365 days) before either is queried,
returning 400 on violation. Frontend:
`components/dashboard/ComparePeriodsSection.tsx`, collapsed on every page
load (plain `useState`, no persistence), a `useMutation`
(`hooks/useCompareInsights.ts`) rather than a cached query — nothing else
in the app reads a comparison result.

## Database Tables

| Table | Purpose | Key constraints |
|---|---|---|
| `transactions` | One row per bank transaction | `external_id` **UNIQUE** (not `account_id` — see below); `manually_edited` boolean, default `false`; `category` FK → `categories(name)` `ON UPDATE CASCADE ON DELETE SET NULL` (S5-02) |
| `settings` | Flat key/value store (LLM provider + encrypted API keys) | `key` TEXT primary key; avoids a migration per new setting |
| `categories` | Category → display color | `name` TEXT primary key; `source` ∈ `seed`\|`ai`\|`user`; `ai_color` holds the last AI color separately so "reset to AI" survives a user override |
| `insights` | Generated AI insight cards per date range | indexed on `(date_from, date_to)`; **delete-and-replace** per range on every successful sync — no history retained |
| `budgets` | Monthly spending limit per category (S4-05) | `category` FK → `categories(name)` `ON UPDATE CASCADE`; `amount` CHECK `> 0`; `user_id` nullable UUID, always `NULL` today (pre-Sprint 6 multi-user readiness, same pattern as future new tables); `UNIQUE NULLS NOT DISTINCT (user_id, category, period)` so a plain `UNIQUE` wouldn't have blocked duplicate budgets while every row's `user_id` is `NULL` |

`manually_edited`: true once a human has set category/subcategory/
description by hand; the categorization agent excludes these rows even
when `category` is null again (a manual clear is still a decision).
Enforced in `crud.get_uncategorized_transactions` and
`crud.update_transaction_categories`, both filtering
`manually_edited IS FALSE` server-side. Any `PATCH /api/transactions/{id}`
sets it to `true` unconditionally, even for a no-op edit.

Only `budgets` has a `user_id` column today; `transactions`, `settings`,
`categories`, and `insights` are still fully global (every query against
them is unscoped — there's exactly one user). `docs/multi_user_migration_
plan.md` (S5-01) is the complete, code-verified inventory of what each
table/constraint/endpoint/singleton needs before Sprint 6's auth lands.

`insights` delete-and-replace is a deliberate decision (S4-04), not an
oversight — see Invariants below.

## Auth

**S6-01 — infrastructure only. No route is wired to auth yet; this section
describes the session model and cookie contract every login flow (S6-03
Google OAuth, S6-04 email/password) and every protected route (S6-05,
S6-06) will use once built.**

Sessions are server-side state in Redis, referenced by an opaque cookie
value — not a JWT. The cookie carries no claims of its own; every request
looks the session id up in Redis to resolve the real user, so a session
can be killed server-side (logout) with the client having no way to keep
using a token it still physically holds, unlike a JWT that stays valid
until its own expiry regardless of server-side state.

`users` table (`app/models.py`'s `User`, migration `1f7634448483`):
`id` UUID PK, `email` TEXT unique, `password_hash` TEXT nullable
(NULL = OAuth-only account), `google_id` TEXT unique nullable (NULL =
password-only account), `display_name` TEXT nullable, `created_at`.
`CHECK (password_hash IS NOT NULL OR google_id IS NOT NULL)` — a row with
neither is unrepresentable, enforced at the database level, not just in
application code.

Password hashing: `app/auth/password.py`, passlib's bcrypt scheme (bcrypt
chosen over argon2id — no unusual threat model here, and no extra native
dependency beyond what `passlib[bcrypt]` already pulls in). `bcrypt`
pinned `<4.1` in `requirements.txt` — passlib 1.7.4's bcrypt backend reads
an attribute bcrypt 4.1 removed, otherwise logging a spurious warning on
every hash/verify call.

Session storage: `app/auth/session.py`, Redis key `session:{session_id}`
→ `{"user_id": ..., "created_at": ...}`. `session_id` is
`secrets.token_urlsafe(32)` (256 bits from Python's CSPRNG) — not derived
from anything guessable. TTL 30 days, **sliding**: `get_session()`
re-issues the full 30-day TTL once less than `REFRESH_THRESHOLD_SECONDS`
(5 days) remains, rather than on every request — bounds Redis `EXPIRE`
writes to roughly once per 5 days of continuous use per session instead of
once per API call, while still keeping any actively-used session alive
indefinitely. A fixed (non-sliding) expiry was rejected: it would log out
a daily active user exactly as readily as an abandoned session, when the
thing actually worth expiring is inactivity, not elapsed time.

Cookie (`app/auth/session.py`'s `set_session_cookie`/`clear_session_cookie`,
not called by any route yet): name `session_id`, `httpOnly` (never
readable by client-side JS — closes the main XSS session-theft path),
`SameSite=Lax` (sent on top-level navigation, including the OAuth-callback
redirect, but not cross-site subrequests — CSRF protection sufficient for
a cookie-only session with no state-changing GET routes), `Secure`
controlled by the `COOKIE_SECURE` env var, **default `false`**. Not
hardcoded `true`: `backend`/`frontend` both run over plain `http://` in
every environment this app runs in today (see URLs & Redirects — the only
TLS in this stack is the unrelated port-3001 OAuth-callback catcher's
mkcert cert), and a browser refuses to ever send a `Secure` cookie back to
a plain-`http://` origin. Chromium-family browsers do special-case
`http://localhost` as a "potentially trustworthy" origin for some
secure-context APIs, but that exemption isn't reliably specified to also
cover the cookie `Secure` attribute across every browser/version — an
explicit env flag (same dev/prod split pattern as `FRONTEND_ORIGIN`) was
chosen over relying on an implicit browser quirk for a security-relevant
attribute. **Sprint 7's real production HTTPS is expected to set
`COOKIE_SECURE=true`.**

`app/auth/dependency.py`'s `get_current_user` (FastAPI dependency, not
wired to any route until S6-05/S6-06): reads the `session_id` cookie,
resolves it via `get_session`, loads the `User` row, raises `401` if the
cookie is missing, the session is expired/invalid, or the session's
`user_id` no longer has a matching row.

## External Dependencies & Their Guarantees

**Enable Banking** — rely on: `external_id` is stable and unique across
the whole bank. Do **not** rely on: `account_id` — it changes on every
reconnect (burned S4-01: keying the old unique constraint on
`(account_id, external_id)` caused 78 duplicate rows on reconnect; fixed
by migration `827da7c749b8`). `account_id` is still stored but is
first-seen-only and never overwritten on conflict.

**AI providers** — resolved via `agents/registry.py`, switching in
Settings changes behavior everywhere at once. `get_provider()` caches one
instance per provider name at module level (S4-09 Item 3) instead of
re-authenticating an SDK client on every call; `routers/settings.py`
drops the whole cache after any successful `PATCH /api/settings` (not
just an `llm_provider` switch — editing a key under the same provider
name must also force a fresh instance). Gemini alias:
`gemini-flash-latest` (`gemini-2.0-flash` was live-confirmed deprecated,
404). Claude alias: `claude-haiku-4-5-20251001`. Provider API keys are
**not** read from `.env` by the running app — only
`scripts/smoke_test_providers.py` does that. The app reads them from the
`settings` table, Fernet-encrypted at rest, masked on every read except
the one internal decrypt used by the provider registry.
`settings_service.get_decrypted_api_key` maps provider name to settings
field explicitly (`API_KEY_FIELD_BY_PROVIDER`) rather than assuming
`f"{provider}_api_key"` — that assumption silently broke Claude specifically
(the field is `anthropic_api_key`, named after the vendor, not
`claude_api_key`) from S2-04 until a real key finally existed to expose it
at S5-06. Both providers also implement `stream_complete()` (S4-06, chat) —
both are now live-verified (Gemini 2026-08-16, Claude 2026-08-18, see
docs/verification_debt.md's CLOSED section for both).

**mkcert certificate**: `backend/certs/localhost.pem`, valid
2026-08-08 → **2028-11-08**, SANs `localhost`/`127.0.0.1`/`::1`. Regenerate
with mkcert before expiry, or retire in favor of real HTTPS by Sprint 6.

## Invariants

- **Manual edits outrank AI categorization.** Enforced server-side (see
  Database Tables above) — not just a frontend convention.
- **Colors come only from the `categories` table.** No component stores
  or hardcodes a per-transaction color; the donut chart and category
  pills read the same source, and validation is centralized in `colors.py`.
- **`transactions.category` must exist in `categories.name` (S5-02, enforced by FK).**
  A category can no longer be renamed by updating `categories.name` in place
  without every referencing transaction following automatically — the FK's
  `ON UPDATE CASCADE` makes that happen at the database level, not by
  convention. The categorization agent's write path
  (`analysis_service.categorize_transactions`) filters LLM output against
  known category names before writing, so an unknown/hallucinated category
  name is skipped and logged (counted in that sync's `failed`), not a hard
  failure of the whole batch. `PATCH /api/transactions/{id}` already
  validated its `category` field against known categories before this FK
  existed (S3-05) — the FK is a second, database-level guarantee, not a
  replacement for that check.
- **Insight history is not retained (S4-04, decided).** `insights` is
  delete-and-replace per date range on every successful sync
  (`crud.replace_insights`) — "history" means whatever the latest sync
  generated, nothing more. This is safe because no feature depends on it
  for correctness: the period-comparison feature (S4-08) computes its
  numbers live from `transactions`, and only shows stored insights as
  supplementary context labeled `generated_at`. If a future sprint needs
  true insight history, that's a new `generation_number` column and a
  "latest per range" query — a clean addition, not a fix to a bug.
- **Job state is Redis-only.** No `jobs` table exists in any migration;
  sync progress never touches Postgres.
- **One sync job at a time (per user), enforced server-side (S5-05).**
  `sync_lock.py`, Redis key `sync_lock:{user_id or 'global'}` (always
  `global` pre-Sprint 6 — the key derivation already takes `user_id` so
  Sprint 6 only needs to start passing a real one). `SET NX EX` on
  acquire (atomic — no check-then-set race between two concurrent
  requests); release is an atomic Lua compare-and-delete (`sync_lock.py`'s
  `_RELEASE_SCRIPT`) so a job never deletes a *different* job's lock. TTL
  11 minutes — deliberately longer than the frontend's 10-minute give-up
  timeout, so a crashed worker's lock cannot deadlock sync permanently;
  it expires on its own even though nothing ever calls `release()` for a
  hard-killed worker. This is a separate mechanism from the 2-minute
  heartbeat-staleness check above — a worker crash is typically reported
  to the user (via a "failed" job status) well before the lock itself
  expires, meaning a fast retry can still 409 for up to the remainder of
  that 11 minutes. The OAuth callback port (3001) lock is unrelated — it
  guards a second concurrent *reconnect*, a different flow.
- **CLAUDE.md's date-range validation (`date_from <= date_to`, ≤365 days)
  is enforced on all five date-range endpoints (S5-07).** `date_range.py`
  is the one source of truth (`validate_date_range` /
  `require_valid_date_range` for query-param endpoints /
  `validate_date_range_body` for `POST /api/transactions/sync`'s body) —
  extracted from `GET /api/insights/compare`'s original S4-08
  implementation, which was the only endpoint that had this until now.
  `GET /api/statistics`, `GET /api/transactions`, `GET /api/insights`, and
  `POST /api/transactions/sync` all now 400 with the same message shape
  (`"date_from/date_to: ..."`) on a backwards or >365-day range. Found
  missing by the S4-10 sprint-close audit; closed by S5-07. `POST
  /api/analysis/categorize` (optional dates) and `POST
  /api/analysis/insights` (required dates) were **not** included — outside
  this ticket's named scope, flagged as a related gap for a PM decision,
  not fixed unprompted.
- **Rate limiting on cost/third-party-hitting endpoints (S5-07).**
  `rate_limit.py`, `slowapi`, keyed on remote address (single-user era —
  no caller identity to key on yet; Sprint 6 should key on `user_id`
  instead once real auth exists, since IP-keying behind a shared proxy
  would throttle unrelated users together). In-memory storage — fine
  while `backend` is one uvicorn process; move to Redis (already in this
  stack) if it ever runs with more than one worker. `POST /api/chat`: 20
  requests/minute. `POST /api/transactions/sync`, `POST
  /api/analysis/categorize`, `POST /api/analysis/insights`: 10/minute
  each. Generous for real single-user use — the point is a ceiling before
  Sprint 6 exposes this publicly, not throttling normal use. A 429 uses
  the same `{"message": ...}` error shape as every other handled
  exception in `main.py`.
- **CORS never accepts a wildcard origin.** `main.py`'s `CORSMiddleware`
  has exactly one configuration path — `allow_origins=[frontend_origin]`,
  always a single explicit origin read from `FRONTEND_ORIGIN`, never `"*"`
  and never a hardcoded list (verified: no other CORS configuration exists
  anywhere in the codebase). `docker-compose.yml` currently hardcodes
  `FRONTEND_ORIGIN: http://localhost:${FRONTEND_PORT:-5173}` for the
  `backend` service — a dev-only value. **Sprint 6 must set
  `FRONTEND_ORIGIN` to the real production frontend URL** (e.g.
  `https://app.example.com`), not derived from `FRONTEND_PORT` at all;
  there is no production compose file or override yet, so this is a real
  gap to close before any public deployment, not just a value to swap.
- **`settings_service.VALID_PROVIDERS` is derived from
  `API_KEY_FIELD_BY_PROVIDER` (S5-07), not a second hand-kept set.** The
  two used to be independent literals — S5-06 found this let
  `patch_setting()` accept an `llm_provider` value that
  `get_decrypted_api_key()` then `KeyError`'d on, an unhandled 500. Adding
  a provider now only ever means editing `API_KEY_FIELD_BY_PROVIDER`.
- **Chat and category-name inputs are length-capped (S5-07).**
  `ChatRequest.message`/`ChatMessage.content` (4000 chars),
  `ChatRequest.history` (50 turns), `CreateCategoryRequest.name` (100
  chars — `categories.name` is an unbounded `Text` primary key with no
  DB-level bound), `GET /api/transactions/search`'s `q` (200 chars). Chat
  message emptiness is checked in the router (a clear 400), not via a
  Pydantic `min_length`, so that common case doesn't turn into a generic
  422 the way the length caps above deliberately do — hitting a cap is
  meant to be rare. `PatchTransactionRequest.description`/`subcategory`
  remain unconstrained — flagged, not fixed (what's a reasonable
  transaction-description length is a product call, not an obvious one).
- **No transaction amounts/descriptions reach `backend`/`celery_worker`
  logs at any level (S5-07 audit, every `logger.*` call site checked).**
  Confirmed safe: all `logger.info`/`.warning`/`.exception` calls in
  `app/` log only ids, counts, provider/category names, or exception
  messages — none embed a real amount or description. One pre-existing,
  unrelated finding, now resolved: `kbc_analyzer/backend/kbc_analyzer/
  analysis.py` (the legacy CLI/Telegram-bot module, untouched by the web
  app) hardcoded real IBANs and the account holder's real name directly
  in its Gemini system prompt — not a logging issue, a real
  PII/financial-identifier exposure in committed source. Moved to
  environment variables and a precautionary full git history rewrite was
  performed and verified. See `docs/security_excursion_2026-08.md` for
  the full record.
