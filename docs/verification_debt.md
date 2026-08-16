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

### Chat frontend error paths — not live-triggered (S4-07)

- **What was deferred:** Live verification of two of `ChatInput`'s error
  paths: (1) the "no API key configured" toast (`useChatSession.ts`'s
  `onError` with `hadPartialResponse: false`), and (2) the mid-stream
  "Response interrupted — please try again" marker (`hadPartialResponse:
  true`).
- **Why:** Both require the request to actually fail. Triggering (1) live
  means removing the real, working Gemini API key from Settings — a
  destructive change to Borys's live configuration, not performed without
  explicit consent per CLAUDE.md's verification rules. Triggering (2) means
  killing the connection mid-response, which browser devtools can do but
  wasn't attempted this session.
- **What was verified instead:** Every *other* acceptance criterion was
  live-tested in a real browser against the real 331-transaction dataset
  (see S4-07's delivery notes) — empty state, suggestion chips, streaming,
  multi-turn, markdown (bold/list/italic), input disabled while streaming,
  the 400/500-character counter and cap, Shift+Enter vs Enter, and Clear
  conversation. The two error paths themselves were code-reviewed: `onError`
  branches correctly on `hadPartialResponse`, the toast uses the backend's
  own message (which already says "Add one in Settings..."), and the
  interrupted marker is a fixed string independent of the underlying error.
  `tsc -b` and `oxlint` both pass clean.
- **What would close it — CONSENT GRANTED 2026-08-17, deferred to S4-10:**
  Borys approved both live triggers during S4-07 confirmation, with this
  exact procedure, so S4-10 can execute it directly without re-asking:
  1. **No-API-key toast:** back up the current Gemini key value from
     Settings first (copy it somewhere safe — Settings only ever shows the
     masked `••••••••` once saved, so the real value must be captured
     *before* blanking it, not re-read after). Blank the key via Settings,
     send a chat message, confirm a toast appears and no empty assistant
     bubble is left behind. Restore the backed-up key value via Settings
     immediately after, then confirm normal chat still works (e.g. re-run
     the biggest-expense check) before considering this closed.
  2. **Mid-stream interrupted marker:** send a chat message, then kill the
     `backend` container mid-response (`docker compose kill backend` —
     `backend`, not `celery_worker`; `POST /api/chat` is served by the
     FastAPI/uvicorn process, not the Celery worker). Confirm the partial
     assistant bubble gets the "Response interrupted — please try again"
     marker rather than hanging forever. Bring `backend` back up afterward
     (`docker compose up -d backend`) and confirm normal chat still works
     before considering this closed.
- **Status:** OPEN — scheduled for S4-10's polish pass, consent already on
  file (see above); do not defer further without checking back with Borys.

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
  Re-checked 2026-08-17 as S4-09 Item 5 (conditional Claude live test) —
  `GET /api/settings` still shows `anthropic_api_key: ""`; explicitly
  deferred again, no new information. This entry already covers the exact
  close-out procedure Item 5 asked for.

---

## CLOSED (recent)

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
