Status: in-progress
Source: docs/tickets/S6-00-sprint-plan.md

---

================================================================
TICKET S6-02 — Schema Migration: user_id Everywhere
================================================================

PRIORITY: This is the ticket the whole sprint's data
integrity rests on. Take the time to get the backfill right —
this is real data, same category of care as S4-01's dedup
cleanup.

BEFORE WRITING THE MIGRATION:
Ask Borys directly for the email address he wants as his
real login. Seed exactly one real user row with that email
in this migration (password_hash set via a value Borys
provides separately and securely — do not have Borys paste a
plaintext password into any chat; either have him set it via
a follow-up flow in S6-04, or generate a one-time reset token
he uses on first login). Do not invent a placeholder email —
this becomes the actual account Borys logs into starting this
sprint.

WHAT TO BUILD:

  Step 1 — Add nullable user_id to every table:
  transactions, categories, settings, budgets, insights.
  (job_store's Redis keys and the sync_lock/rate_limit
  singletons are handled separately — see below, not a SQL
  migration.)

  Step 2 — Backfill:
  Every existing row in every table gets user_id set to the
  one real user seeded above. Verify counts before and after
  match exactly (same technique as S4-01's dedup — log what
  you're about to do, then do it, then verify).

  Step 3 — Tighten to NOT NULL once backfilled.

  Step 4 — Fix the S5-08-discovered conflict:
  categories' primary key becomes (user_id, name). This means
  transactions.category can no longer FK to categories.name
  alone — it must reference (user_id, name), and the FK
  column set on transactions must include user_id. Rebuild
  the FK from S5-02 accordingly. Verify the rename-cascade
  behavior (ON UPDATE CASCADE) still works with the composite
  key — this was tested in S5-02 against the old single-column
  key; retest it against the new composite one.

  Step 5 — settings table:
  This one isn't a bolt-on, per S5-01's finding — its PK is
  the key itself. Redesign as
  (user_id, key) composite PK, or a per-user JSONB blob — your
  call, justify it. Whichever you choose, the encrypted
  API-key storage (Fernet) must continue working exactly as
  before, just scoped per user now.

  Step 6 — external_id constraint:
  Apply the decision from this sprint's Step 0 pre-work.
  Change UNIQUE(external_id) to UNIQUE(user_id, external_id)
  (or leave global if Step 0's vendor check concluded
  external_id is genuinely globally unique — state which).
  Update the sync upsert's ON CONFLICT clause to match.

  Step 7 — Singletons (S4-09/S5-05 findings):
  agents/registry.py's _provider_cache becomes keyed by
  (user_id, provider_name), not just provider_name.
  sync_lock.py's lock key becomes user-scoped (the ticket
  that built it already wrote the key derivation to make
  this a one-line change — confirm that holds).
  rate_limit.py: confirm whether it should move from IP-keyed
  to user-keyed now that real user identity exists — your
  call, justify it (IP-keyed still has value pre-login, e.g.
  the login endpoints themselves).

ACCEPTANCE CRITERIA:
- All 5 tables have NOT NULL user_id after backfill
- Real Borys account seeded with his real email, real data
  correctly attributed to it (spot-check: his 331+
  transactions all show the right user_id)
- categories composite PK + transactions FK verified live
  (repeat S5-02's rename-cascade test against the new key
  shape)
- settings redesign preserves working encrypted API keys
- external_id constraint matches the Step 0 decision
- _provider_cache, sync_lock, rate_limit all user-aware
  where appropriate
- Full test suite still passes (coordinate with Tester —
  this migration will break existing tests that assume
  single-user data; flag what needs updating rather than
  silently changing test expectations yourself)

WHEN DONE:
- Show before/after row counts for every table
- Show the composite-key rename-cascade test passing
- Show a real API key still decrypting correctly post-
  migration
- State the external_id decision and why
- Do not start S6-03 until confirmed

---

## Ruling (Borys, 2026-08-20) — supersedes one acceptance criterion

Before this ticket's build began, a real conflict was flagged between two
of the acceptance criteria above: "Full test suite still passes" versus
this ticket's own scope being schema/constraints only (crud.py's
`upsert_transactions`, `create_category`, `upsert_category_colors`,
`replace_insights`, `upsert_setting` all write with no `user_id` today —
threading `user_id` through them is the migration plan's Ordering steps
7–8, which is **S6-06**'s job, not this one). Making `user_id` `NOT NULL`
on those tables without also touching `crud.py` necessarily breaks those
write paths and the tests that exercise them.

**Decision: Option 1 (schema-only), with conditions.** S6-02 stays exactly
as scoped above — migrations, backfill, constraints, singletons. It does
**not** thread `user_id` through `crud.py` write paths; that stays S6-06's
job. In exchange:

- **"Full test suite still passes" is superseded by:** *"Full test suite
  run produces a complete, explicit list of every now-failing test and its
  cause; zero unexplained failures."* This ticket is not done if any test
  fails for a reason not accounted for on that list.
- That failing-test list is **S6-06's literal checklist** — a test only
  leaves the list when S6-06's crud/router threading actually fixes the
  call site it names, not by being deleted or its expectation quietly
  rewritten.
- The Tester agent must be told directly (not just noted in this file)
  that the suite is expected to be red for exactly the tickets between
  S6-02 and S6-06's completion, so a red run in that window isn't chased
  as a regression.

Also decided: the per-account (not just per-bank/per-user) uniqueness
nuance found during this ticket's Step 0 research belongs in
`docs/multi_user_migration_plan.md` as a Sprint 7 watch-item, not only in
a delivery report — that document is what Sprint 7 will actually read.
