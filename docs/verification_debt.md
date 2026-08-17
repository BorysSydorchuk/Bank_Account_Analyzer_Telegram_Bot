# Verification Debt Ledger

Tracks every verification that was deferred, or completed structurally-only
(no live execution), per CLAUDE.md's testing standard. Each entry: what was
deferred, why, what would close it, and current status. Entries are removed
(not just marked closed) once the live verification actually runs — git
history is the record of when that happened.

Formal creation of this file is an S4-10 deliverable; created early per the
S4-06 handoff instruction ("if you defer any verification before then,
create it early rather than tracking by memory").

---

## SPRINT 5 AUDIT SCOPE

Architectural findings flagged for the Sprint 5 schema/global-singleton
audit (CLAUDE.md's MULTI-USER READINESS rule) — not verification debt in
the sense of "unverified," but real debt this project has knowingly taken
on that the audit needs to resolve before Sprint 6 multi-user auth lands.

- `agents/registry.py`'s `_provider_cache` (added S4-09 Item 3) is a
  module-level global keyed on provider name, not on user — exactly the
  "no new global singletons keyed on 'the user'" pattern CLAUDE.md already
  warns against for the `settings` table. Fine in the single-user era (one
  provider selection total), but at Sprint 6 it must become user-scoped
  (keyed on `(user_id, provider_name)` or moved into a per-request/
  per-session scope) or one user's cached provider instance — and API
  key — could leak across users. Flagged in S4-09 review.

## OPEN

### Categories FK backfill validation & live constraint test — Docker unreachable this session (S5-02)

- **What was deferred:** The ticket's Part 2 requirement to show backfill
  validation output (every distinct `transactions.category` value has a
  matching `categories.name` row) *before* the migration is applied, then
  verify the FK live (rename a category, confirm transactions follow) and
  confirm the categorization agent's unknown-category handling against a
  real LLM run.
- **Why:** `docker compose ps` / `docker version` hung indefinitely (no
  output after 90s+) every time this session tried to reach the local
  stack — the Docker Desktop backend processes are running (confirmed via
  `Get-Process`) but not responding to the CLI, so Postgres is unreachable
  from here. This matches the known cloud-agent/local-stack limit already
  noted in AGENTS.md (added S5-00): a session that can't reach
  `localhost:8000` can't run live verification, and "retry later" isn't
  something this session can act on itself.
- **What was verified instead:** The migration's pre-flight check
  (`d3f8a5c6b9e2_add_fk_transactions_category.py`) queries for orphaned
  `transactions.category` values and raises with the offending list before
  attempting `ADD CONSTRAINT`, rather than relying on a human reading a
  report — so the "surface, don't silently fix" requirement is enforced by
  the migration itself even though nobody has watched it run yet. Migration
  logic, `models.py`'s matching `ForeignKey` declaration, and
  `analysis_service.py`'s unknown-category filter were reviewed by reading
  (no `python -m py_compile` run either, same blocker — no working
  Python env confirmed reachable outside the container this session).
- **What would close it:** With Docker Desktop responsive: `docker compose
  up -d`, `docker compose exec backend alembic upgrade head`, capture the
  real output (either a clean apply, or the pre-flight `RuntimeError` with
  real orphaned category names if any exist); if clean, `UPDATE categories
  SET name = 'Test Rename' WHERE name = 'Other'` and confirm via
  `SELECT category FROM transactions WHERE category = 'Test Rename'` that
  every previously-'Other' transaction followed, then rename back; run one
  real categorization sync and inspect `docker compose logs backend` for
  the unknown-category warning path (or confirm it never fires because the
  LLM stayed within `CATEGORIES`).
- **Status:** OPEN — blocked on Borys resuming this session (or a new one)
  once Docker Desktop responds locally.

*(Two entries below re-confirmed 2026-08-17, S4-10 sprint close — dates and closure conditions still accurate.)*

### Non-root file-permission protection — unverifiable on Windows Docker Desktop (S4-09 Item 1)

- **What was deferred:** Confirming that the non-root `appuser` (added
  S4-09 Item 1) actually protects anything — i.e. that a real permission
  boundary exists between `appuser` and files a different/root process
  might have written.
- **Why:** Verified only that `appuser` can read/write
  `eb_session.json`/`certs/` — necessary but not sufficient. Docker
  Desktop's Windows bind mounts (`./backend:/app`) report `rwxrwxrwx` to
  every UID regardless of the container's actual user, so this host can't
  demonstrate the failure mode the non-root user is meant to prevent
  (root-owned files becoming inaccessible), and by the same token can't
  demonstrate the fix actually closes it either. The security property is
  asserted from the Dockerfile change and Debian/Linux `USER` semantics
  generally, not observed working on this host.
- **What would close it:** Run the same stack on a native Linux Docker
  host (real bind-mount ownership, not synthesized 777) — create a file as
  root inside a container, confirm `appuser` genuinely cannot write it,
  confirm the app still runs correctly end-to-end as non-root.
- **Status:** OPEN — closes naturally at Sprint 6, when production
  deployment moves off Windows Docker Desktop onto a real (Linux) host.

### Claude provider — chat streaming, no API key (S4-06)

- **What was deferred:** Live verification of
  `backend/app/agents/providers/claude.py::ClaudeProvider.stream_complete`
  against the real Anthropic API.
- **Why:** No `ANTHROPIC_API_KEY` has ever been available in this project
  (approval still pending as of this ticket). Same underlying gap as
  `ClaudeProvider.complete()`/`complete_json()` from Sprint 2 — never
  live-tested for the same reason. (Gemini's equivalent gap closed
  2026-08-16 — see CLOSED below; Docker being down was never Claude's only
  blocker.)
- **What was verified instead:** `anthropic` 0.122.0's
  `messages.stream()` / `AsyncMessageStreamManager` / `get_final_message()`
  signatures read directly from installed source (matching this project's
  `anthropic>=0.40.0` floor) to confirm the async-context-manager usage and
  the `usage.input_tokens` / `usage.output_tokens` fields this code relies
  on. `python -m py_compile` confirms the module has no syntax errors. No
  request was ever sent to Anthropic's API.
- **What would close it:** A real `ANTHROPIC_API_KEY` saved via Settings,
  provider switched to Claude, and a real multi-turn `POST /api/chat`
  conversation run against it (mirroring the Gemini verification below) —
  then commit as `chore: close Sprint 2 Claude provider gap` per the
  existing handoff note, updating this entry alongside.
- **Status:** OPEN — blocked on Borys/PM providing a real Anthropic API key.
  Re-checked 2026-08-17 twice: as S4-09 Item 5 (conditional Claude live
  test) and again at S4-10 sprint close — both times `GET /api/settings`
  showed `anthropic_api_key: ""`; explicitly deferred again, no new
  information. Suggested next checkpoint: S5-06 (per Sprint 5's schema
  audit) or whenever a real key arrives, whichever is first. This entry
  already covers the exact close-out procedure needed.

---

## CLOSED (recent)

### Chat frontend error paths — live-triggered (S4-07 → closed S4-10, 2026-08-17)

Both consented tests executed exactly per the procedure Borys approved at
S4-07 confirmation:

1. **No-API-key toast:** backed up the real (encrypted) `gemini_api_key`
   value directly at the database level (`SELECT`/copy into a temp table,
   never decrypted, never seen in plaintext) rather than relying on
   Settings' masked display. Blanked it via `PATCH /api/settings`, sent a
   chat message: a toast appeared reading *"No API key configured for
   gemini. Add one in Settings before running analysis."*, and no empty
   assistant bubble was left in the thread. Restored the exact encrypted
   value via direct `UPDATE`, dropped the temp table, sent another message:
   real Gemini reply came back normally.
2. **Mid-stream interrupted marker:** sent a long chat message, ran
   `docker compose kill backend` mid-stream. Partial response text stayed
   in the bubble, followed by *"Response interrupted — please try again"*
   in red, input re-enabled (not stuck). Brought `backend` back up
   (`docker compose up -d backend`), sent a follow-up message: real reply
   came back, prior history intact.

Both matched `onError`'s two branches (`hadPartialResponse: false` /
`true`) exactly as code-reviewed at S4-07. No regressions.

### `POST /api/chat` — Gemini live verification (S4-06, closed 2026-08-16)

Docker Desktop came up; ran a real 3-exchange conversation against the real
331-transaction dataset with the actually-configured Gemini key. Confirmed:
SSE frames arrive incrementally via `curl -N` (not one flush); a transient
Gemini `503 UNAVAILABLE` mid-stream was caught and surfaced as a clean SSE
error frame, never a raw traceback; a retried request succeeded; multi-turn
history was respected across 3 turns; every number the assistant computed
from the summary/category/budget context (total spent €7.180,30, total
received €6.840,72, Groceries €647,18/9.0%, Groceries budget €47,40 of
€40,00 exceeded, Traveling €5,20 of €6,00 warning) matched
`GET /api/statistics` and `GET /api/budgets` exactly. No financial data
appeared in `docker compose logs backend` at INFO level.

One real, non-blocking limitation surfaced by this run (see
ARCHITECTURE.md's chat-flow note, not tracked here as debt — it's a
documented behavior, not an unverified one): "last 20 transactions" is a
small slice of a much larger summary window when more than 20 transactions
fall in it (293 did, here). Asked for the single biggest expense across the
full 90 days, the assistant correctly declined to guess beyond its visible
20 rows rather than inventing a number — exactly per its system-prompt
rule — but that means a true 90-day-max query can't be answered from
today's context shape.

**Update 2026-08-17 (S4-06 review bounce):** Reviewer found this was a
one-line omission, not a design gap — `compute_statistics()` already
returns `summary.biggest_expense`; `chat_service._summary_text()` just
wasn't surfacing it. Fixed in-ticket; re-verified live against the same
dataset (exact match: €800.00, [REDACTED-NAME], 2026-07-27). See
`docs/tickets/S4-06-ai-chat-backend.md`'s amendment history for the full
sequence.
