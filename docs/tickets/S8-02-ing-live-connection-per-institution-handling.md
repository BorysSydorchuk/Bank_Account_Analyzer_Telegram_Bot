Status: in-progress

================================================================
TICKET S8-02 — ING Live Connection & Per-Institution Handling
================================================================

WHAT TO BUILD:
- Complete real, live ING connection flow — same evidence
  standard as every credential-touching ticket this project has
  had: this needs Borys to have or create a real ING account
  (or a test/sandbox path if Enable Banking + ING offers one —
  check first, flag if a real account is the only option)
- Handle any real data-shape differences between KBC and ING
  transaction data: description formats, account structure,
  currency handling, date formats — whatever a real connection
  reveals, don't assume KBC's shape generalizes
- Confirm the existing categorization/sync/insights pipeline
  works correctly against real ING data without KBC-specific
  assumptions baked in anywhere

ACCEPTANCE CRITERIA:
- A real ING connection completes successfully end-to-end,
  same web-only flow standard as S7-07
- Real ING transactions sync, categorize, and appear correctly
  in the dashboard
- Any per-institution quirks found are documented in
  ARCHITECTURE.md, not silently special-cased without
  explanation
- Existing KBC connection/data unaffected — real regression
  check, not assumption
- **AMENDED (S8-01, 2026-08-27):** "unaffected" means: with the
  composite-key `enable_banking_sessions` model, the real KBC
  connection remains live and independently usable *while* the
  ING connection is also live — not just "reconnecting doesn't
  corrupt old transaction rows." Both connections coexisting
  simultaneously is the actual test.
- **ADDED (S8-01, 2026-08-27):** real evidence that
  `transactions.account_id` correctly disambiguates KBC-sourced
  from ING-sourced rows once both are connected, checked against
  real data from both banks, not assumed.
- **ADDED (2026-08-27, this ticket's own scope now):** the real
  production migration for `enable_banking_sessions`' composite
  key (`d4a7e19c6b52`, committed in S8-01 but deliberately not
  yet run in production — see S8-01's ticket file and
  ARCHITECTURE.md's Multi-bank section for why deferring was
  correct, not a gap). Must run before any real ING connection
  can be attempted in production, since production's
  `enable_banking_sessions` is still on the old `user_id`-only
  primary key. Same nullable → backfill → verify care as every
  prior real-data migration here (S6-02) — Borys's actual live
  KBC session must survive it, confirmed with real evidence
  (row present, same session_id/valid_until, now labelled
  `institution = 'KBC'`), not assumed from the local dev
  rehearsal alone.

WHEN DONE:
- Real evidence of a live ING connection and sync
- Any data-shape differences found, and how they were handled
- Confirm KBC still works, unaffected (per the amended
  simultaneous-connection meaning above)
- Real evidence the production migration ran cleanly and
  Borys's live KBC session survived it intact
- Do not start S8-03 until confirmed

--- IAM NOTE, logged as it happened (2026-08-27) ---

Widening `kbc-analyzer-deploy` (this ticket's real production
migration needs `terraform apply`/`ecs run-task`/`ecs
execute-command`, not just ECR push/pull) required bootstrapping via
`KBC_analyser_deploy`, the admin user retired last session — a scoped
user can never grant itself more IAM permissions. Borys reactivated
it three times for three separate small `terraform apply` runs (the
three new deploy policies; a 2048-byte inline-policy-size fix that
required converting `deploy_migration_runner` to a managed policy;
two missing read actions — `ecr:DescribeRepositories`,
`secretsmanager:GetResourcePolicy` — found only by actually running
the real apply). After the third, Borys explicitly chose to leave it
active for the rest of Sprint 8 rather than repeat
deactivate-then-reactivate for every further IAM tweak, scoped to IAM
changes only — see ARCHITECTURE.md's IAM section for the current,
accurate state (supersedes the "Retired 2026-08-27" note from the
prior session's commit, which is now stale as a permanent record but
accurate as a description of what happened at that moment).
