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

### `POST /api/chat` — no live run against either provider (S4-06)

- **What was deferred:** The ticket's acceptance criteria call for a real
  ≥3-exchange conversation with Gemini live-verified and Claude structurally
  verified. **Neither provider was live-tested in this session** — Docker
  Desktop's daemon was not running (`docker compose ps` fails to connect,
  the same condition already recorded in ARCHITECTURE.md's verification
  note from S4-03), so Postgres/Redis/the backend/the Celery worker never
  started, and no HTTP request reached this endpoint or either LLM API.
- **Why:** Docker unavailable in this environment. This is a stricter gap
  than the ticket assumed — it isn't just "Claude has no key," it's "nothing
  in the stack was running to call at all."
- **What was verified instead:** `python -m py_compile` on every
  new/changed backend module (`providers/base.py`, `providers/gemini.py`,
  `providers/claude.py`, `agents/chat.py`, `chat_service.py`,
  `routers/chat.py`, `crud.py`, `schemas.py`, `main.py`). A full `import
  app.main` in an isolated scratch environment (FastAPI, SQLAlchemy,
  Pydantic, `google-genai` 2.18.1, `anthropic` 0.122.0 installed there,
  `DATABASE_URL` set to a placeholder since `create_engine` doesn't connect
  until first use) confirmed the app and the new `/api/chat` route wire up
  and import without error. `google-genai` 2.18.1's
  `AsyncModels.generate_content_stream` and `anthropic` 0.122.0's
  `Messages.stream`/`AsyncMessageStreamManager`/`get_final_message` were
  read directly from installed source (matching this project's
  `google-genai>=1.0.0` / `anthropic>=0.40.0` floors) to confirm the exact
  call shapes, role names (`user`/`model` for Gemini vs `user`/`assistant`
  for Claude and this app's own history format), and usage-field names
  (`usage_metadata.prompt_token_count`/`candidates_token_count` for Gemini,
  `usage.input_tokens`/`output_tokens` for Claude) that `stream_complete()`
  relies on in both providers.
- **What would close it:** `docker compose up` (Docker Desktop running),
  then a real ≥3-exchange `POST /api/chat` conversation with Gemini (the
  currently-configured default provider), checking SSE frames arrive
  incrementally (`curl -N` or the browser network tab) and that a
  "what was my biggest expense?" answer matches `GET /api/statistics`.
- **Status:** OPEN — blocked on Docker Desktop being available. Re-run
  `docker compose ps` first per the existing ARCHITECTURE.md caveat.

### Claude provider — chat streaming, no API key (S4-06)

- **What was deferred:** Live verification of
  `backend/app/agents/providers/claude.py::ClaudeProvider.stream_complete`
  against the real Anthropic API, specifically — even once Docker is
  available, this one stays blocked separately.
- **Why:** No `ANTHROPIC_API_KEY` has ever been available in this project
  (approval still pending as of this ticket). Same underlying gap as
  `ClaudeProvider.complete()`/`complete_json()` from Sprint 2 — never
  live-tested for the same reason.
- **What was verified instead:** See the source-level SDK verification
  described in the entry above — applies equally to Claude's streaming
  method.
- **What would close it:** A real `ANTHROPIC_API_KEY` saved via Settings,
  provider switched to Claude, and a real multi-turn `POST /api/chat`
  conversation run against it — then commit as `chore: close Sprint 2
  Claude provider gap` per the existing handoff note, updating this entry
  alongside.
- **Status:** OPEN — blocked on Borys/PM providing a real Anthropic API key
  (independent of the Docker blocker above).
