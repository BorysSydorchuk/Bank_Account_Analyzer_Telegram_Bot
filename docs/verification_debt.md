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

## OPEN

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
- **What would close it:** With Borys's consent, temporarily clear the
  Gemini key in Settings and send a chat message (should toast, no bubble
  left behind) — then restore the key; separately, throttle/kill the
  network mid-stream via devtools and confirm the partial bubble gets the
  interrupted marker.
- **Status:** OPEN — low priority; both paths are simple, type-checked, and
  mirror the backend's already-live-verified 400/mid-stream-error handling.

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
