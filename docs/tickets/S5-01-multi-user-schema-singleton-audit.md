Status: in-progress
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
