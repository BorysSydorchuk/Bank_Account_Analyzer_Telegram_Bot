Status: in-progress
Source: docs/tickets/S6-00-sprint-plan.md

---

================================================================
TICKET S6-06 — Full Query Scoping & Ownership Checks
================================================================

PRIORITY: The core security work of the sprint. This is
where S5-01's IDOR findings get fixed for real.

WHAT TO BUILD:
Every remaining endpoint gets get_current_user, and every
query gets scoped to that user. Two categories, handled
differently:

  Category A — list/create endpoints (add user_id filter):
  transactions, insights, statistics, compare, chat context
  assembly, sync, settings, all categories/budgets endpoints
  not already covered by S6-05.

  Category B — by-ID lookup endpoints (add real ownership
  checks, not just filtering — the IDOR-shaped gap S5-01
  named explicitly):
  GET /api/jobs/{job_id} — the job's user_id must match
  the requester; if not, 404 (not 403 — don't confirm the
  resource exists to an unauthorized requester).
  PATCH /api/transactions/{id} — same pattern.
  Any other by-ID route discovered during this sweep.

  job_store.py specifically: job keys in Redis need a
  user_id component added to the key or stored in the value
  with a check on read — audit this against S5-01's finding
  that job keys are currently fully unscoped.

CHAT CONTEXT:
  chat_service.build_context() currently has CURRENT_USER_ID
  = None hardcoded (flagged in S5-01's audit) — this is the
  ticket that removes it for real, threading the actual
  authenticated user through.

SYNC:
  The sync flow needs to use the authenticated user's own
  Enable Banking session, not a single global
  eb_session.json. This ticket scopes the DATA correctly;
  per-user bank session STORAGE is Sprint 7's job (it needs
  the public deployment context to do properly) — for this
  sprint, it's acceptable for the single existing
  eb_session.json to remain tied to Borys's account
  specifically, as long as that's enforced (only Borys's
  user_id can trigger sync against it) rather than left open.
  State this limitation explicitly in ARCHITECTURE.md.

ACCEPTANCE CRITERIA:
- Every endpoint requires authentication except the
  explicitly public ones (health, login, register, OAuth
  callback) — enumerate the public list explicitly in
  ARCHITECTURE.md so it's an intentional, reviewable set
- Every list/create endpoint filters by user_id
- Every by-ID endpoint checks ownership and returns 404 (not
  403) on mismatch
- job_store keys are user-scoped or ownership-checked on read
- chat_service's CURRENT_USER_ID hardcoding is gone
- Sync is restricted to the account it's currently tied to
- A real test: create a second test user (throwaway, not
  Borys's account), confirm they see zero of Borys's data
  anywhere and get 404s on his resource IDs, not data leaks

WHEN DONE:
- Enumerate the full public-route list
- Show the second-test-user isolation check passing for
  every endpoint category
- Show a 404 (not 403) on a cross-user by-ID request
- Do not start S6-07 until confirmed

---

## Addition (Borys, 2026-08-21)

Before starting the main sweep: audit every remaining GET endpoint for
the same silent-empty-result failure mode S6-05 found in
`GET /api/budgets` — not just the by-ID ownership checks this ticket
already names. A `crud.*` function that already accepts `user_id` but is
still called with a `None`/placeholder sentinel now matches nothing
against a `NOT NULL` column (S6-02), which fails silently (an empty
list, not an error) rather than loudly.

**Audit result:** the landmine only exists where a `crud.*` function
already accepts an explicit `user_id` parameter — every other read
function in `crud.py` has no `user_id` parameter at all yet (fully
unscoped, returns every user's rows unconditionally — a different
problem, the one this ticket's Category A work fixes directly). Only
`get_budget`/`create_budget`/`update_budget_amount`/`delete_budget`/
`list_budgets_with_status` accept `user_id` today. Full inventory of
every call site using the `None` sentinel:

- `routers/budgets.py`'s `POST`/`PATCH`/`DELETE` (`CURRENT_USER_ID =
  None`) — already tracked since S6-02, `GET` fixed in S6-05.
- **`chat_service.py`'s `_budgets_text` (`crud.list_budgets_with_status(db,
  CURRENT_USER_ID)`, `CURRENT_USER_ID = None`) — newly found by this
  audit.** Since S6-02, `POST /api/chat` has been silently telling every
  user "No budgets set." in the AI's context even when real budgets
  exist — a live, real bug, not a hypothetical. This is the exact same
  hardcoded constant this ticket's own "CHAT CONTEXT" section already
  names for removal, confirming it needs to happen, not just that it's
  stale.

No other occurrences found (`list_categories`'s optional `user_id`,
default `None`, is deliberate/S6-05-documented, not a landmine — it
stays unscoped only for `POST /api/categories`'s still-unauthenticated
duplicate check).
