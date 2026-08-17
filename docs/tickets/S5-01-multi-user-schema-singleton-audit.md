Status: delivered
Source: docs/tickets/S5-00-sprint-plan.md

---

================================================================
TICKET S5-01 — Multi-User Schema & Singleton Audit
================================================================

PRIORITY: First. Sprint 6 executes the plan this ticket
produces. Nothing else in Sprint 5 should proceed on
assumptions this audit might overturn.

WHAT TO BUILD:
A written audit — not code changes. Produce
docs/multi_user_migration_plan.md: a complete inventory of
everything that assumes a single user, and the concrete
plan to fix each, ready for Sprint 6 to execute.

REQUIRED CONTENT:

  ## Tables
  Every table, with: does it need user_id, does it have one
  today, and the migration step required. Cover at minimum
  transactions, categories, settings, budgets, insights.
  For each, state the backfill strategy (all existing rows
  belong to the first user) and whether the column becomes
  NOT NULL.

  ## Constraints
  Every unique constraint that must become user-scoped.
  Note specifically: transactions.external_id is currently
  globally unique — two different users legitimately having
  the same external_id from the same bank is possible; state
  what this must become (likely UNIQUE (user_id,
  external_id)) and the risk if it isn't changed.

  ## Endpoints
  Every endpoint, with the query scoping change required.
  Flag any that currently return all rows unconditionally.

  ## Singletons and module-level state
  Known: agents/registry.py's _provider_cache (module-level
  global dict, flagged in S4-09 review — will serve one
  user's provider to everyone once auth lands). The
  settings table (global key-value, grandfathered from the
  multi-user rule in Sprint 4). Search for others:
  module-level caches, global clients, anything holding
  per-user state outside a request.

  ## Files on disk
  eb_session.json is a single global bank session. State
  what per-user session storage must look like, and note
  that Sprint 6's public deployment changes this anyway
  (per-user OAuth, not a shared file).

  ## Ordering
  The dependency-ordered sequence Sprint 6 should execute
  these in, with what breaks if the order is violated.

VERIFICATION:
Every claim in the document must be verified against the
actual code and schema, not recalled. State how each
section was verified (e.g. "\d+ against the live database",
"grep across routers/").

ACCEPTANCE CRITERIA:
- docs/multi_user_migration_plan.md exists with all six
  sections
- Every table, endpoint, and constraint in the current
  system appears — completeness matters more than depth
- The registry cache and settings singleton are both
  addressed explicitly
- Each claim states its verification method
- ARCHITECTURE.md updated if the audit finds anything its
  current text gets wrong

WHEN DONE:
- Show the full document
- State how many endpoints/tables/constraints need changes
- Explain: which single item in this plan carries the most
  risk of silent cross-user data leakage if missed?
- Do not start S5-02 until confirmed

---

## Delivery notes (Codee)

`docs/multi_user_migration_plan.md` written, all six required sections
present (Tables, Constraints, Endpoints, Singletons and module-level
state, Files on disk, Ordering), each ending with a "Verified via" note
naming the exact command/read that produced it.

While verifying the Ordering section's precedent against `budgets`'s own
migration, found my first draft's claim wrong (I'd said `budgets` split
its nullable column and its constraint into two migrations — it didn't,
it did both in one, because it was a brand-new table with nothing to
backfill). Corrected it in the document itself rather than silently
fixing it, since the ticket's whole point is that every claim must be
verified, not recalled — leaving the correction visible seemed more
honest than a quiet edit.

No code changes made, per this ticket's own scope. ARCHITECTURE.md
updated with one cross-reference (not a correction — nothing existing
was factually wrong, but the Database Tables section didn't previously
say *which* tables are still fully global, which this audit now answers
precisely).

WHEN DONE — answered:

**How many need changes:**
- **Tables:** 4 of 5. `transactions` and `insights` definitely need a
  `user_id` column added. `categories` and `settings` need one *if* the
  product decision (see document) goes per-user — both currently global
  by design, and I recommended per-user with reasoning, but flagged it as
  Borys/PM's call, not mine to make unilaterally. `budgets` is already
  done (S4-05) — only needs its existing nullable column backfilled and
  made `NOT NULL`.
- **Constraints:** at least 1 definite (`transactions.external_id`'s
  global `UNIQUE`), 2 more conditional on the categories/settings
  decision. `budgets`'s constraint is already correct as designed.
- **Endpoints:** 21 of 25 need `user_id` threaded through in some form
  (only the 4 budget endpoints don't). Of those 21, two are worse than
  "needs scoping" — `GET /api/jobs/{job_id}` and `PATCH
  /api/transactions/{id}` both look up a single resource by its own ID
  with zero ownership check today, which is an authorization gap, not
  just a missing filter.

**Highest risk of silent cross-user leakage:**
`transactions.external_id`'s global `UNIQUE (external_id)` constraint,
without question. Every other gap on this list produces *visible*
breakage or a *loud* failure once multi-user is live and something goes
wrong — a missing `WHERE user_id = ...` on a list endpoint shows the
wrong rows on screen, which someone notices fast. This one is different:
if two different real users' banks both hand Enable Banking the same
`external_id` (unverified whether Enable Banking guarantees global
uniqueness across all its client apps, not just within one bank), the
existing `ON CONFLICT (external_id) DO UPDATE` in `crud.upsert_
transactions` means the second user's sync silently *overwrites* the
first user's transaction row with their own data — no error, no 409, no
visible sign anything went wrong, just one user's bank data quietly
replaced by another's on the next sync. It's also structurally the exact
same incident class as S4-01 (account_id churn), just with a different
column doing the false-uniqueness job — which is exactly the kind of
repeat failure a written plan like this is supposed to prevent.

Do not start S5-02 until confirmed, per the ticket.
