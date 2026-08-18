# Verification Debt Ledger

Tracks every verification that was deferred, or completed structurally-only
(no live execution), per CLAUDE.md's testing standard. Each entry: what was
deferred, why, what would close it, and current status. Entries are removed
(not just marked closed) once the live verification actually runs — git
history is the record of when that happened.

Formal creation of this file is an S4-10 deliverable; created early per the
S4-06 handoff instruction ("if you defer any verification before then,
create it early rather than tracking by memory").

## Conventions (S5-06)

- **Every OPEN entry needs, at minimum:** what was deferred, why (the actual
  blocker, not just "not done yet"), what would close it (a concrete,
  actionable procedure — not "verify this eventually"), and a `Status:`
  line that is both current-dated and states a real closure condition
  (an event: "closes at Sprint 6," "closes once a real API key exists" —
  not an open-ended "someday").
- **An entry with no plausible closure date** (e.g. blocked on a platform
  limitation this host can't fix) still needs a *closure condition*, even
  if that condition is itself a future sprint or an external dependency.
  "Can't close on this host" is acceptable; "not sure when" is not.
- **Re-dating at sprint close:** every sprint-close ticket (S4-10 did this
  for Sprint 4; S5-06 for Sprint 5) re-confirms every remaining OPEN entry
  against current reality — re-date it if still accurate, restate it if the
  situation changed, close it if something (a new test, a new credential, a
  new environment) finally made closure possible.
- **CLOSED entries stay in this file** (a `CLOSED (recent)` section, not
  deleted) as long as they're useful evidence of *how* something was
  verified — trimmed or archived once stale enough that git history alone
  is a sufficient record.
- **Evidence for a CLOSED entry must be shape-and-schema only** (field
  names, response structure, counts) — never real transaction amounts,
  real merchant names, or real budget figures. Use placeholder values
  (`€XXX.XX`, `Merchant Name`) even when the real live-test output had
  specifics. This file is meant to stay safe to read/share without being
  a second copy of financial data (CLAUDE.md's logging rules exist for
  the same reason). Pre-existing entries written before this rule
  (S4-06, S5-06) are **not** retroactively edited for it — flagged as
  known exceptions in place rather than rewriting a two-sprint-old
  exposure that isn't worth a force-push.

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
- **Status (re-confirmed 2026-08-18, S5-06):** OPEN — architectural debt,
  not verification debt in the "unverified" sense; closes naturally as
  part of Sprint 6's multi-user migration (`docs/multi_user_migration_plan.md`
  covers the exact sequencing). No test can meaningfully close this in the
  single-user era — there's only ever one provider selection to observe.

## OPEN

### Sync lock release on two failure early-returns — never empirically triggered (S5-05)

- **What was deferred:** `sync_lock.release()` (S5-05) sits in a single
  `finally` block wrapping the whole task body in `tasks/analysis.py`, so
  it runs on every exit path by Python's own unconditional `finally`
  guarantee — but only the success path and a hard-killed-worker path
  were actually exercised live. The two in-code failure early-returns
  never had a real run go through them while checking the lock
  afterward:
  1. The Enable Banking auth/error early-return (`tasks/analysis.py`
     around line 67-72, `except (EnableBankingAuthError,
     EnableBankingError)`).
  2. The `every_batch_failed` early-return (line 130-142) — every
     categorization batch call to the LLM failing while a provider *is*
     configured. Distinct from, and not covered by, the existing
     `test_categorizing_stage_failure_when_no_provider_configured_reports_failed_status`
     test, which exercises the earlier "no API key configured" branch in
     `analysis_service.categorize_transactions`, not this one.
- **Why:** Reasoned from Python's `finally` semantics instead — the same
  block already covers the success path, which was live-verified (a
  completed job's lock released immediately, a following sync got `200`
  without waiting on TTL). Forcing either failure path live in this
  session would have meant deliberately breaking the real Enable Banking
  session or the real Gemini API key, which per CLAUDE.md's testing
  standard on destructive verifications isn't something to do
  unilaterally — Borys's call, not made yet.
- **What would close it:** The same monkeypatch technique
  `test_storing_stage_failure_reports_failed_status_naming_that_stage`
  and `test_fetching_stage_failure_reports_failed_status_naming_that_stage`
  already use in `tests/test_job_pipeline.py` (`mock_enable_banking_client
  .expire_session()` for the first path; a fake provider whose batches all
  raise, for the `every_batch_failed` path) — extended in each case to
  also assert `sync_lock.get_holder()` is `None` after the run, not just
  that `job_store` reports `status: "failed"`. This is Tester-agent scope
  (S5-04's follow-on suite), not something to build here.
- **Status:** OPEN (2026-08-18) — no target session assigned yet; belongs
  to the Tester's S5-04 follow-on work.

### Three regression tests deferred — no frontend test harness yet (S5-04)

- **What was deferred:** Automated regression tests for S2-02 (the
  `Math.ceil` expiry-warning rounding bug), S3-04 (job-timeout must fire
  even when poll responses are byte-identical), and the frontend half of
  S3-06 (the `{"message"}` vs `{"detail"}` error-shape parser).
- **Why:** All three bugs — and their fixes — live in frontend TypeScript
  (`SessionBanner.tsx`'s `WARNING_THRESHOLD_DAYS` comparison,
  `useDashboard.ts`'s poll-timeout timer, `lib/api.ts`'s error parser), not
  backend Python. `kbc_analyzer/frontend/` has no test runner configured at
  all yet (no vitest/jest, no `package.json` test script) — TESTER.md's own
  SUITE RULES anticipate this ("`npm test` from frontend/ when frontend
  tests exist"). Standing up a frontend test harness from scratch is
  itself an S5-03-sized task, not something to fold unprompted into S5-04's
  backend invariant/regression ticket (PROMPT 5 scope discipline). The
  backend half of S3-06 (that both response shapes are genuinely,
  currently produced by the live API) IS covered —
  `tests/test_error_contracts.py::test_both_message_and_detail_error_shapes_are_genuinely_live_S3_06_regression`.
- **What would close it:** A frontend test ticket (vitest + React Testing
  Library, most likely) standing up `npm test`, followed by three targeted
  regression tests: one asserting the 7.7-day case renders the warning
  banner, one asserting a stalled poll still times out on identical
  payloads, one asserting the api client surfaces an error message from
  either JSON shape.
- **Status (re-confirmed 2026-08-18, S5-06 sprint close):** OPEN —
  `kbc_analyzer/frontend/package.json` still has no `test` script and no
  vitest/jest dependency; nothing has changed since S5-04. Flagged to PM
  for a frontend-test-infrastructure ticket; no target sprint assigned yet.

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
- **Status (re-confirmed 2026-08-18, S5-06 sprint close):** OPEN — closes
  naturally at Sprint 6, when production deployment moves off Windows
  Docker Desktop onto a real (Linux) host. Closure condition unchanged
  from S4-09/S4-10; nothing about this host changed.

---

## CLOSED (recent)

### Claude provider — full live verification (S2-04/S2-05/S2-06/S4-06, closed 2026-08-18)

*(Pre-existing exception to the Conventions section's shape-only evidence
rule, added after this entry was written — contains real transaction
amounts, a real merchant name, and real budget figures. Not retroactively
scrubbed.)*

A real `ANTHROPIC_API_KEY` became available (saved via `PATCH /api/settings`,
provider switched to `claude`). First live attempt against
`POST /api/analysis/categorize` (5 transactions manually cleared back to
`category IS NULL`, values recorded first, for a real categorization call —
everything else was already categorized from prior sessions) failed
immediately with `"No API key configured for claude"` despite the key
showing as saved — **a real bug, not a missing-key situation**:
`settings_service.get_decrypted_api_key(db, provider)` looked up
`f"{provider}_api_key"`, i.e. `"claude_api_key"` for the Claude provider,
but the actual stored field has always been named `"anthropic_api_key"`
(named after the vendor, not the model family — Gemini's provider name and
field prefix happen to match, which is why this never surfaced there).
This means **every previously-closed Claude ledger entry back to S2-04 was
blocked on two things, not one** — no key ever existed to expose the second
blocker until now. Flagged to Borys, who chose the explicit
`API_KEY_FIELD_BY_PROVIDER` mapping fix (`settings_service.py`) over
renaming the field — zero blast radius, no frontend/DB changes.

With the fix live-reloaded (`docker compose logs backend` confirmed a
clean reload, no traceback), re-ran everything:

- **Categorization** (`POST /api/analysis/categorize`, same 5 transactions):
  `{"categorized":5,"skipped_already_categorized":40,"failed":0,"provider":"claude","error_message":null}`.
  4 of 5 matched the original Gemini-assigned categories exactly (Groceries,
  Traveling/Transport ×2, Restaurants and Cafes); the fifth (a €233.93
  KU LEUVEN payment) got `Other/Shopping` from Claude versus the original
  `Other/Rest` from Gemini — a real, defensible difference in model
  judgment, not an error. All 5 transactions restored to their original
  recorded values afterward.
- **Insights** (`POST /api/analysis/insights`, same date range): 5 real
  insights generated, `"provider":"claude"`. Style is genuinely
  distinguishable from Gemini's (see the S4-06 CLOSED entry below for a
  Gemini sample from the same kind of data): Claude's insights lean
  quantitative and prescriptive — precise percentages and ratios ("83% of
  daily spend," "3.2× the first," a concrete "20–30% reduction" estimate
  with a specific suggested action) — where Gemini's read more narrative/
  descriptive. Not restored (insights are documented as delete-and-replace,
  ephemeral by design — see ARCHITECTURE.md Invariants; a future sync with
  Gemini active regenerates them normally).
- **Chat streaming** (`POST /api/chat`, real SSE via `curl -N`): two-turn
  conversation. Turn 1 ("what was my biggest expense, groceries vs
  transport") returned real incremental token frames (not one flush),
  correct grounded numbers matching `GET /api/statistics`/`GET /api/budgets`
  exactly (€800,00 biggest expense; Groceries €772,92/11.4%; Traveling
  €583,11/8.6%; budget overages 511.9% and 623.0%), and real
  `usage: {"input": 1046, "output": 229}` from `stream_complete()`'s
  `get_final_message()` path — the exact code path S4-06's entry could only
  verify structurally before. Turn 2, with turn 1 in `history`, correctly
  built on it (recommended cutting groceries first, referencing the same
  budget figures and specific real merchants — Carrefour, Delhaize, Too
  Good To Go, NMBS, De Lijn — from the actual transaction data), confirming
  multi-turn history works identically to Gemini's already-verified path.

Provider switched back to `gemini` afterward, matching the ticket's
explicit instruction and this project's normal running state.

This closes **S2-04** (provider structural verification — now live, and the
`get_decrypted_api_key` bug it never caught is fixed), **S2-05**
(categorization), **S2-06** (insights), and **S4-06**'s Claude half (chat
streaming) — all four were tracked as one entry
("Claude provider — chat streaming, no API key (S4-06)") since the
underlying blocker (no key) was identical; that entry is removed from OPEN
above as of this closure.

### Categories FK backfill validation & live constraint test (S5-02, closed 2026-08-18)

Docker Desktop restarted and became responsive. `docker compose up -d`
brought the stack up; the backend container's own startup (`alembic
upgrade head`) applied migration `d3f8a5c6b9e2` automatically — logs show
`Running upgrade c4a91d6e0f3b -> d3f8a5c6b9e2` with no `RuntimeError`,
confirming the pre-flight backfill check found zero orphaned
`transactions.category` values against the real 350-row dataset (8
distinct categories in use, two of them user-created custom categories —
`Pet Care`, `Investments` — not in the categorization agent's hardcoded
list, both present in `categories` already so neither was orphaned).

`\d transactions` confirmed the live constraint:
`fk_transactions_category_categories_name FOREIGN KEY (category)
REFERENCES categories(name) ON UPDATE CASCADE ON DELETE SET NULL`.

Rename-cascade test: `UPDATE categories SET name = 'Test Rename' WHERE
name = 'Other'` — all 62 transactions previously on `'Other'` read back
as `'Test Rename'` with zero orphans, zero manual reassignment needed;
renamed back, category counts matched the pre-test snapshot exactly.

Unknown-category handling: a raw `UPDATE transactions SET category =
'Totally Not A Category' ...` was rejected live by the FK (`violates
foreign key constraint`, transaction rolled back cleanly, no data
changed) — confirming the failure mode the ticket flagged as Option A's
cost is real. Rather than waiting for an LLM to spontaneously hallucinate
a category (not reliably reproducible on demand), the exact set-membership
filter now in `analysis_service.categorize_transactions` was run
standalone inside the backend container against the real
`crud.list_categories(db)` result: an unknown name was correctly excluded
from the write set while a valid one passed through — proving the guard
that keeps the FK rejection above from ever reaching the live
categorization write path.

Migration downgrade path, `models.py`'s `ForeignKey` declaration, and
`analysis_service.py`'s filter were already reviewed by reading at commit
time (2026-08-17) — this closure is the live-execution half.

**S5-04 (2026-08-18):** both layers verified here by hand are now permanent,
automated regression tests — `tests/test_referential_integrity.py::test_fk_rejects_an_unknown_category_at_the_db_level`
and `::test_categorization_pre_write_filter_excludes_unknown_categories_before_any_write`
— so this can never silently regress without the suite catching it.

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

*(Pre-existing exception to the Conventions section's shape-only evidence
rule, added after this entry was written — contains real spending totals
and budget figures. Not retroactively scrubbed.)*

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

**S5-04 (2026-08-18):** this omission is now a permanent regression test —
`tests/test_chat_context.py::test_chat_context_summary_mentions_biggest_expense`.
