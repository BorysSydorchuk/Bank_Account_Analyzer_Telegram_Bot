Status: confirmed
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

---

## WHEN DONE — answered:

**Before/after row counts (dev database, live):**

| Table | Before | After | Notes |
|---|---|---|---|
| `users` | 0 | 1 | Bootstrap row, `boris.sydorchuk@gmail.com` |
| `transactions` | 366 | 366 | All 366 attribute to Borys's `user_id` (spot-checked via `COUNT(*) WHERE user_id = <his id>` = 366, exact match) |
| `categories` | 10 | 10 | |
| `settings` | 3 | 3 | |
| `budgets` | 3 | 3 | |
| `insights` | 50 | 50 | |

The backfill migration's own rowcount assertion (every `UPDATE ... WHERE
user_id IS NULL`'s `rowcount` checked against that table's pre-count)
passed silently for all five tables — a mismatch would have raised
`RuntimeError` and rolled back the whole migration. `alembic upgrade head`
ran clean end to end, `d3f8a5c6b9e2 -> ... -> 5c9a2e6b8f14`, no manual
intervention.

**Composite-key rename-cascade test, live** (inside a transaction, rolled
back — no permanent change to real data): renamed `'Other'` →
`'Test Rename S6-02'` for Borys's user row in `categories`. All 63
transactions previously on `'Other'` read back as `'Test Rename S6-02'`,
zero left on the old name — the composite FK (`transactions(user_id,
category) -> categories(user_id, name)`, `ON UPDATE CASCADE`) carries the
rename exactly like the old single-column FK did in S5-02.

**Real API key decryption, live, post-migration:** both `gemini_api_key`
and `anthropic_api_key` rows (now under the composite `(user_id, key)`
primary key) decrypt correctly via the real `crypto.decrypt()` — confirmed
by prefix only (`AIzaSy...`, `sk-ant...`), never the full key.

**external_id decision:** `UNIQUE (user_id, external_id)`, not
`UNIQUE (external_id)` alone. Enable Banking's own FAQ docs, fetched live
during this ticket's Step 0: *"the `entry_reference` value is not globally
unique, and the same entry references may occur for transactions
belonging to completely different accounts."* This isn't the "safe
default absent vendor confirmation" the plan allowed for — it's a direct
vendor statement that a bare `UNIQUE(external_id)` would eventually let
one user's sync collide with another's, the same incident class as
S4-01's `account_id` burn. `crud.upsert_transactions`'s `ON CONFLICT`
clause updated to match (`index_elements=[Transaction.user_id,
Transaction.external_id]`). See `docs/multi_user_migration_plan.md` and
`ARCHITECTURE.md`'s External Dependencies section for the full quote and
the Sprint 7 per-account watch-item this also surfaced.

**Singletons (Step 7):**
- `agents/registry.py`'s `_provider_cache` — now keyed on `(user_id,
  provider_name)` (was provider name alone). `get_provider(db, user_id:
  UUID | None = None)` — default `None` means the 3 existing call sites
  (`analysis_service.py` ×2, `chat_service.py` ×1) need no changes; S6-06
  passing a real value there is a one-line change per call site, matching
  `sync_lock.py`'s own pattern.
- `sync_lock.py` — confirmed unchanged and correct as designed: `_lock_key`
  already takes `user_id: UUID | None = None`. Nothing to do here now.
- `rate_limit.py` — **decision: stays IP-keyed for now, not switched in
  this ticket.** `slowapi`'s `key_func` only receives the raw `Request`;
  no route resolves a real `user_id` until `get_current_user` is wired in
  S6-05/S6-06, and deriving one inside `key_func` would mean re-implementing
  session lookup outside `get_current_user` rather than reusing it. S6-06
  is the right point to switch `/chat`, `/sync`, `/analysis/*` to
  `user_id`-keyed; `/login`/`/register` (S6-04) should likely stay
  IP-keyed even then, since user identity is exactly what's absent when a
  brute-force attempt hits those two. Documented in `ARCHITECTURE.md`.

**Full test suite — explicit failing-test list (per Borys's ruling above),
not "still passes":** `67` total, `41 passed`, `26 failed`. Every failure
traced to one of 6 root causes, all `crud.py` write paths this ticket
deliberately does not thread `user_id` through (S6-06's job) or one
factory fixture that doesn't set it. **Zero unexplained failures** — every
one of the 26 is accounted for below, and this table is the literal S6-06
checklist per the ruling: a row leaves this list only when S6-06's
threading actually fixes the site it names.

| Root cause | Failure mode | Tests (26 total) |
|---|---|---|
| `crud.upsert_transactions` writes no `user_id` | `NotNullViolation` on `transactions.user_id` | `test_sync_dedup.py`: `test_same_external_id_is_never_inserted_twice`, `test_dedup_holds_even_when_account_id_differs_S4_01_regression`, `test_resync_of_already_synced_range_stores_zero_rows`, `test_conflicting_update_refreshes_amount_and_description`; `test_job_pipeline.py` (via `tasks/analysis.py`'s storing stage): `test_happy_path_transitions_through_every_stage_in_order`, `test_categorization_result_is_actually_written`, `test_categorizing_stage_failure_when_no_provider_configured_reports_failed_status`, `test_generating_insights_stage_failure_reports_failed_status_naming_that_stage` |
| `tests/fixtures/factories.py`'s `transaction_factory` builds a `Transaction()` with no `user_id` | `NotNullViolation` on `transactions.user_id` | `test_chat_context.py`: `test_chat_context_summary_mentions_biggest_expense`, `test_chat_context_summary_has_no_biggest_expense_line_when_nothing_was_spent`; `test_manual_edit_protection.py`: `test_manually_edited_row_is_excluded_from_the_categorization_query`, `test_manually_edited_row_excluded_even_when_category_is_null_S3_05`, `test_update_never_overwrites_an_already_categorized_row`, `test_race_condition_row_edited_between_select_and_update_stays_protected`; `test_referential_integrity.py`: `test_fk_rejects_an_unknown_category_at_the_db_level`, `test_categorization_pre_write_filter_excludes_unknown_categories_before_any_write`; `test_smoke.py`: `test_db_session_writes_and_reads_a_transaction` |
| `crud.create_budget` called with `user_id=None` literally by the test itself (function already accepts `user_id` — `budgets.user_id` is what's newly `NOT NULL`) | `NotNullViolation` on `budgets.user_id` | `test_budgets.py`: `test_budget_status_boundaries`, `test_spent_this_month_uses_calendar_month_and_resets_on_month_boundary`, `test_spend_from_a_prior_month_does_not_carry_over_after_the_boundary` |
| `crud.upsert_category_colors` writes no `user_id` | `NotNullViolation` on `categories.user_id` | `test_colors.py`: `test_rejected_ai_color_falls_back_to_the_categorys_existing_color`, `test_rejected_ai_color_for_a_brand_new_category_falls_back_to_backup_palette_not_a_random_color` |
| `crud.set_category_color`/`reset_category_to_ai`'s `db.get(Category, name)` — a single-value PK lookup against what's now a composite `(user_id, name)` PK | `InvalidRequestError: Incorrect number of values in identifier` | `test_colors.py`: `test_source_user_colors_are_never_overwritten_by_ai` |
| `crud.replace_insights` writes no `user_id` | `NotNullViolation` on `insights.user_id` | `test_insights.py`: `test_regenerating_a_range_deletes_only_that_ranges_prior_insights`, `test_regenerating_with_zero_insights_leaves_the_range_empty_not_stale`, `test_replace_is_a_single_transaction_row_count_matches_exactly` |

No test failed for a reason outside this table (confirmed by reading every
failure's traceback, not just the summary line — `crud.upsert_setting` has
no direct test coverage today, so it contributes no row here, but is the
same shape of gap and belongs on S6-06's list regardless).

**On "tell the Tester agent directly":** flagging rather than doing this
as asked — AGENTS.md's own Coordination rules state agents "coordinate
through repo files, never through each other" and specifically that
"the Reviewer and Tester never instruct Codee directly; all direction
flows through Borys/PM." I have no channel to a live Tester session (none
is running, and nothing in my toolset addresses one), so a direct message
isn't something I can actually send — this ticket file plus
`ARCHITECTURE.md`'s new Database Tables note are the repo-file channel
AGENTS.md defines for exactly this. **Borys: please relay this section
(or just "the suite is expected to be red on these 26 tests until S6-06,
not a regression") when you boot the Tester session** — that's the
missing link this ruling assumed I could close myself but can't.

Do not start S6-03 until confirmed.
