Status: confirmed
Source: sprint4_tickets_v2.txt (revised set)
Shipped as: 68e697a — feat: S4-03 add ARCHITECTURE.md living document

---

================================================================
TICKET S4-03 — ARCHITECTURE.md Living Document  (NEW)
================================================================

PRIORITY: First. Two spec-drift incidents (the sub-2s sync
criterion written against stale architecture, and the
redirect-page fix targeting a URL that had moved) happened
because no current-state architecture record exists. This
document prevents the third incident.

WHAT TO BUILD:
Create ARCHITECTURE.md at the monorepo root. It is a
CURRENT-STATE document — what IS, never what WAS or what
is planned. Keep it under ~150 lines; it must be readable
in two minutes.

REQUIRED SECTIONS:

  ## Services & Ports
  Every container, its port, and what it serves.
  Include: the eb_callback_server (celery_worker process,
  port 3001, HTTPS via mkcert) — the exact component the
  redirect-page incident missed.

  ## URLs & Redirects
  Every URL that exists outside our code: the Enable
  Banking registered redirect URI, the frontend origin,
  the API base. State explicitly which component serves
  each one.

  ## Data Flow
  The sync pipeline as it works TODAY:
  POST /sync (45ms) → job record → Celery task
  (fetch → store → categorize → insights) → Redis job
  state → frontend polling.

  ## Database Tables
  One line per table: name, purpose, key constraints
  (the external_id UNIQUE, manually_edited semantics,
  source column values).

  ## External Dependencies & Their Guarantees
  Enable Banking: what we rely on (external_id stability)
  and what we must NOT rely on (account_id stability —
  documented burn from S4-01). Gemini/Claude: model
  aliases in use. mkcert cert expiry date.

  ## Invariants
  Rules that must never break: manual edits outrank AI;
  colors come only from the categories table; job state
  is Redis-only; one sync job at a time per user.

MAINTENANCE RULE (also being added to CLAUDE.md via
separate prompt): any ticket that changes a port, URL,
data flow, table, or invariant updates ARCHITECTURE.md
in the same commit. A PR that changes architecture
without touching this file is incomplete.

ACCEPTANCE CRITERIA:
- ARCHITECTURE.md exists, accurate against the running
  system (verify each claim against docker-compose.yml,
  the code, and the live stack — do not write from memory)
- Every section above present
- A developer who has never seen the repo could identify
  which component serves the OAuth redirect in under
  a minute

WHEN DONE:
- Show the full document
- Confirm each Services & Ports entry was verified against
  docker compose ps, not recalled
- Do not start S4-04 until confirmed
