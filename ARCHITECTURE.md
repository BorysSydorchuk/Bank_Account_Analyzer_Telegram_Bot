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

## Services & Ports

| Service | Image/build | Port | Serves |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | Postgres, `pg_isready` healthcheck |
| `backend` | `backend/Dockerfile` | 8000 | FastAPI (`app.main:app`); runs `alembic upgrade head` then `uvicorn --reload` on every start |
| `frontend` | `frontend/Dockerfile` | 5173 | Vite dev server |
| `redis` | `redis:7-alpine` | 6379 | Celery broker (db 0) + result backend (db 1) |
| `celery_worker` | `backend/Dockerfile` (same image as backend) | **3001** | `celery -A app.celery_app worker`, **and** the Enable Banking OAuth callback catcher |

`celery_worker`, not `backend`, publishes port 3001 — deliberate
(`docker-compose.yml:59-64`): the OAuth redirect lands in the user's real
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
| Enable Banking redirect URI | `https://localhost:3001/callback` | `celery_worker` / `eb_callback_server.py` (`enablebanking.py:37`) |
| Frontend origin (CORS) | `FRONTEND_ORIGIN`, default `http://localhost:5173` | `backend/app/main.py:34-40`, `CORSMiddleware` |
| Frontend's API base | `VITE_API_URL`, default `http://localhost:8000` | `frontend/src/lib/api.ts:22`, injected via compose, no `.env` file on disk |

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

`POST /api/transactions/sync` (`routers/transactions.py:18-39`) does
almost nothing synchronously: creates a `job_id`, seeds Redis with
`{"status": "processing", "stage": "fetching"}`, dispatches
`run_sync_job.delay(...)`, returns immediately.

Celery task `run_sync_job` (`tasks/analysis.py:19-201`) runs the pipeline,
updating the Redis job record as it progresses:
`fetching` → `storing` (`crud.upsert_transactions`, upsert on
`external_id` conflict) → `categorizing` (batch progress reported via
`on_batch_complete`) → `generating_insights` (only on success does
`crud.replace_insights` run — a failed generation leaves prior insights
untouched) → `complete`/`failed`.

Job state lives only in Redis (`job_store.py`, key `job:{job_id}`, 24h
TTL) — never Postgres. `GET /api/jobs/{job_id}` 404s once the key expires.

Frontend polling (`frontend/src/hooks/useDashboard.ts`): `useQuery` with
`refetchInterval` of 2s while `status === "processing"`,
`refetchIntervalInBackground: true`, plus an independent `setTimeout`
enforcing a 10-minute cap (React Query's structural sharing means a dead
worker never produces a new `data` reference to key an effect off).

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
`summary.biggest_expense` (`statistics.py:151-159`), and `_summary_text()`
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
| `transactions` | One row per bank transaction | `external_id` **UNIQUE** (not `account_id` — see below); `manually_edited` boolean, default `false` |
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

`insights` delete-and-replace is a deliberate decision (S4-04), not an
oversight — see Invariants below.

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
the one internal decrypt used by the provider registry. Both providers also
implement `stream_complete()` (S4-06, chat) — Gemini's is live-verified
(2026-08-16); Claude's is structurally verified only, since no
`ANTHROPIC_API_KEY` has ever been available, the same gap as its
non-streaming methods (see docs/verification_debt.md).

**mkcert certificate**: `backend/certs/localhost.pem`, valid
2026-08-08 → **2028-11-08**, SANs `localhost`/`127.0.0.1`/`::1`. Regenerate
with mkcert before expiry, or retire in favor of real HTTPS by Sprint 6.

## Invariants

- **Manual edits outrank AI categorization.** Enforced server-side (see
  Database Tables above) — not just a frontend convention.
- **Colors come only from the `categories` table.** No component stores
  or hardcodes a per-transaction color; the donut chart and category
  pills read the same source, and validation is centralized in `colors.py`.
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
- **One sync job at a time (per user) — NOT currently enforced.** No
  locking exists around `POST /api/transactions/sync`; nothing server-side
  stops two overlapping sync jobs. The only related lock in the codebase
  guards the OAuth callback port (3001) against a second concurrent
  *reconnect*, which is a different flow. The only guard against duplicate
  syncs today is client-side (`useDashboard.ts`'s sync-in-flight state).
  Flagged separately below — documented here as-is, not as-intended.
- **CLAUDE.md's date-range validation (`date_from <= date_to`, ≤365 days)
  is enforced only on `GET /api/insights/compare` (S4-08) — NOT on
  `GET /api/statistics`, `POST /api/transactions/sync`,
  `GET /api/transactions`, or `GET /api/insights`.** Discovered during the
  S4-10 sprint-close audit while verifying the compare endpoint's own
  validation. Pre-existing on every endpoint except the newest one, not
  introduced this sprint — documented here as-is; candidate for a shared
  validation helper in a future sprint rather than four copy-pasted checks.
