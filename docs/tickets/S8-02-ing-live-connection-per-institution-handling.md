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

**Real evidence of a live ING connection and sync:** the connection
itself is real and live — Enable Banking's own `GET /sessions/{id}`
confirms `"status": "AUTHORIZED"` for the real ING session on
`boris.sydorchuk@gmail.com`. But it reports zero linked accounts
(`"accounts": []`), both on first connect and after reconnecting with
explicit account selection at ING's own consent screen. No sync ran
against real ING transaction data because there is none to fetch —
`get_account_uids()` correctly returns an empty list for this
connection, so the sync loop correctly does nothing for it.

**Any data-shape differences found, and how they were handled:** none
found — no real ING transaction data existed to compare against KBC's
shape. Cannot be answered honestly beyond that.

**Confirm KBC still works, unaffected:** yes, real evidence. Both
KBC and ING sessions coexist simultaneously on the same real account
(`boris.sydorchuk@gmail.com`) — the core thing S8-01's migration exists
to make possible. KBC's existing data (56 transactions across its two
account UIDs, all fully categorized) is unchanged after the ING
connection work and a real sync run.

**Real evidence the production migration ran cleanly and Borys's live
KBC session survived it intact:** yes — see S8-01/S8-02's earlier
entries above; re-confirmed again here via the same real account,
still intact.

**Not confirmed, deferred, Borys's explicit call — not fixed by
forcing a synthetic pass:** the real cause of ING reporting zero
accounts is unresolved. Real ING transaction-data verification
(categorization, data-shape handling, `account_id` disambiguation
between two live datasets) is logged in `docs/verification_debt.md`,
closes when Borys tests with a different, actively-used real ING
account in a later ticket.

**Status: core infrastructure delivered and real (production
migration, code deploy, IAM, real simultaneous KBC+ING connection,
KBC confirmed unaffected). Real ING transaction-data verification
explicitly deferred, not silently skipped — see verification_debt.md.
Do not start S8-03 assuming ING transaction data has been verified;
S8-03's own real dual-connection collision test may itself need to
wait for that same deferred real ING data, worth checking against
S8-03's actual requirements before starting it.**

--- IAM NOTE, logged as it happened (2026-08-27) ---

Widening `kbc-analyzer-deploy` (this ticket's real production
migration needs `terraform apply`/`ecs run-task`/`ecs
execute-command`, not just ECR push/pull) required bootstrapping via
`KBC_analyser_deploy`, the admin user retired last session — a scoped
user can never grant itself more IAM permissions. Borys reactivated
it four times across four separate small `terraform apply` runs: the
three new deploy policies; a 2048-byte inline-policy-size fix that
required converting `deploy_migration_runner` to a managed policy;
two missing read actions (`ecr:DescribeRepositories`, then
`ecr:ListTagsForResource`, widened to `ecr:Describe*`/`ecr:List*`) and
`secretsmanager:GetResourcePolicy`; and `ecs:TagResource` (this
provider's `default_tags` auto-tags every new resource) — all found
only by actually running the real apply, not anticipated in advance.
After the third, Borys explicitly chose to leave it active for the
rest of Sprint 8 rather than repeat deactivate-then-reactivate for
every further IAM tweak, scoped to IAM changes only — see
ARCHITECTURE.md's IAM section for the current, accurate state
(supersedes the "Retired 2026-08-27" note from the prior session's
commit, which is now stale as a permanent record but accurate as a
description of what happened at that moment).

--- PRODUCTION MIGRATION: DONE, real evidence (2026-08-27) ---

Also found running for real, not anticipated at S8-01: the worker
image has no `psql` binary (only the `psycopg` Python driver), and
raw `psycopg.connect()` doesn't understand SQLAlchemy's
`postgresql+psycopg://` URL scheme — verification queries used
SQLAlchemy's `create_engine`/`connect()` instead, matching the app's
own real connection path rather than a workaround.

Also found and fixed: `infra/migration_runner.tf` never injected
`DATABASE_URL` (unlike `web.tf`/`worker.tf`) — `alembic/env.py` reads
it directly, so `alembic current` failed outright until this task
definition got the same secret injection those two already had. Full
detail and the fix itself in ARCHITECTURE.md's Multi-bank section and
`infra/migration_runner.tf`'s own comment.

Real command sequence, task revision 9 (revision 8 registered before
the `DATABASE_URL` fix, stopped without being used):

    $ alembic current
    b8e4f2a9c317
    $ alembic upgrade head
    Running upgrade b8e4f2a9c317 -> d4a7e19c6b52, widen
    enable_banking_sessions to composite (user_id, institution) key
    $ alembic current
    d4a7e19c6b52 (head)

Row-count/identity check, before and after (SQLAlchemy query inside
the migration-runner container): production held two real
`enable_banking_sessions` rows, not one (Borys plus a second real
user who has also connected KBC) — both survived byte-for-byte
identical (`user_id`, `valid_until` unchanged), now labelled
`institution = 'KBC'`. Task stopped immediately after (confirmed via
`describe-tasks` polling to `STOPPED`, then an empty
`list-tasks --family kbc-analyzer-migration-runner` — no lingering
Fargate cost).
