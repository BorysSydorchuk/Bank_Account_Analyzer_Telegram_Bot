Status: plan
Source: issued directly in Claude Code session, 2026-08-17

---

================================================================
SPRINT 5 — "HARDENING & TEST FOUNDATION"
KBC Personal Finance Analyzer
================================================================

SPRINT GOAL:
Make the codebase safe to put authentication and real users
on top of. No new user-facing features. At sprint end there
is an automated test suite guarding every invariant, a
documented migration plan for multi-user, no known
standing-rule violations in shipped code, and an empty-or-
current verification ledger.

Sprint 4 is fully committed, confirmed, and pushed. Start
from that state.

PROCESS CHANGE (new this sprint):
Before S5-01 begins, commit this entire sprint plan to
docs/tickets/S5-00-sprint-plan.md with Status: plan. This
closes the gap where the authoritative ticket text lived
only on Borys's machine. Individual tickets still get their
own files with their own lifecycle as before.

Also add one line to AGENTS.md's coordination rules:
"Cloud agents cannot reach Borys's local stack
(localhost:8000). Any instruction to 'retry later' or
'run tomorrow' is unexecutable — deferred live
verification requires Borys to resume the session."

TESTER AGENT ACTIVATION:
The Tester agent (TESTER.md, already in the repo) activates
at S5-03. S5-03 and S5-04 are TESTER tickets, not Codee
tickets — Borys will boot a separate Tester session for
them. Codee: do not build the test suite yourself.

HOW TO WORK THROUGH THESE TICKETS:
Build in order S5-01 through S5-08. After each ticket
explain what you built and why, following the CLAUDE.md
explanation standard. Do not start the next ticket until
Borys confirms the current one is done. Every ticket goes
through Reviewer review before confirmation.

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

================================================================
TICKET S5-02 — Categories Referential Integrity Decision
================================================================

BACKGROUND (from the supervision report):
categories.name is a primary key. transactions.category is
free text with no foreign key. budgets.category HAS a
proper FK with ON UPDATE CASCADE. Nothing renames categories
today, so this is dormant — but the moment a rename feature
exists, transactions orphan silently and their colors break.

WHAT TO BUILD:

Part 1 — Present the decision, wait for Borys's answer
before implementing:

  Option A — Add the foreign key:
  ALTER TABLE transactions ADD CONSTRAINT ...
  FOREIGN KEY (category) REFERENCES categories(name)
  ON UPDATE CASCADE ON DELETE SET NULL.
  Requires: backfill validation first (every distinct
  transactions.category value must exist in categories, or
  the constraint fails to apply). Renames then propagate
  automatically; category deletion nulls the transaction's
  category rather than orphaning it.
  Cost: the categorization agent writes category values
  from LLM output — if it ever emits a category name not
  in the table, the insert now fails hard instead of
  silently storing an unknown value. This is arguably
  correct behavior, but it is a behavior change and needs
  handling in the agent's write path.

  Option B — Formally forbid renames:
  No schema change. Document in ARCHITECTURE.md Invariants
  that category names are immutable once created, and that
  any future rename feature must be implemented as
  create-new + reassign-transactions + delete-old, never
  an UPDATE to categories.name.
  Cost: the protection is documentation, not enforcement —
  a future ticket could violate it.

  PM RECOMMENDATION: Option A. The failure mode Option B
  guards against is exactly the kind that survives review
  and detonates later; a hard constraint is worth the
  agent write-path handling. But present both fairly and
  take Borys's call.

Part 2 — Implement the chosen option.
  Option A: run the backfill validation FIRST and report
  results before applying the constraint (if any
  transactions.category value has no matching categories
  row, that is a data issue to surface, not silently
  fix). Then the migration, then the agent write-path
  handling.
  Option B: ARCHITECTURE.md Invariants entry plus a
  comment at the categories model.

ACCEPTANCE CRITERIA:
- Decision presented with both options and their real
  costs; Borys's choice recorded before implementation
- If A: backfill validation results shown BEFORE the
  migration is applied; constraint verified live; the
  categorization agent's behavior on an unknown category
  name is tested and described
- If B: invariant documented in both places
- ARCHITECTURE.md updated in the same commit

WHEN DONE:
- State the chosen option and show the implementation
- If A: show the backfill validation output and a live
  test of the constraint (rename a category, show
  transactions follow)
- Explain: why does budgets.category already have this
  FK while transactions.category does not?
- Do not start S5-03 until confirmed

================================================================
TICKET S5-03 — Test Infrastructure  [TESTER TICKET]
================================================================

THIS IS A TESTER AGENT TICKET. Borys boots a separate
Tester session (TESTER.md boot prompt) for S5-03 and S5-04.
Codee does not build these.

WHAT TO BUILD:
The test foundation everything else runs on. No behavior
tests yet — this ticket is fixtures, configuration, and
proving the harness works.

REQUIRED:

  ## Runner and layout
  pytest, configured in backend/pyproject.toml or
  pytest.ini. Tests live in backend/tests/. One command
  runs everything from backend/. Document the command in
  backend/tests/README.md.

  ## Test database
  A separate, disposable Postgres database — never the dev
  database. Created and migrated by a session-scoped
  fixture running the REAL Alembic chain (this also tests
  that migrations apply cleanly from scratch, which has
  never been verified end-to-end). Torn down after the
  run.

  ## Fixtures
  - db_session: function-scoped, transactional, rolled
    back after each test so tests never see each other's
    writes
  - client: FastAPI TestClient with the db dependency
    overridden to the test session
  - Seeded reference data: the 7 categories with colors
  - Factory helpers for transactions, budgets, insights —
    invented but realistic data (Belgian merchants, EUR,
    plausible dates). NEVER Borys's real data.

  ## External boundaries mocked
  - LLMProvider: a fake provider returning canned
    structured responses; no live Gemini or Claude calls
    ever
  - Enable Banking client: mocked at the client boundary;
    no live bank calls ever
  - Celery: task_always_eager so tasks run inline
  - Redis: fakeredis or an equivalent, or a dedicated test
    Redis database index

  ## Determinism
  Time frozen where tests depend on "today" (freezegun or
  equivalent) — budget month boundaries and session-expiry
  logic both need this. No sleeps as synchronization. No
  test-order dependencies.

  ## Proof the harness works
  Three smoke tests: one that hits GET /health through the
  client fixture, one that writes and reads a transaction
  through db_session, one that runs the fake LLM provider.

ACCEPTANCE CRITERIA:
- One command runs the suite from a clean state
- The test database is created via the real Alembic chain
  and is definitively not the dev database (show the
  connection string logic)
- Fixtures roll back — two tests writing the same row do
  not collide
- No test touches a live external service
- The three smoke tests pass

WHEN DONE:
- Show the run command and its full output
- Show the test database creation/teardown working
- Confirm no live external calls (how is this enforced,
  not just intended?)
- Explain: why run the real Alembic chain instead of
  create_all() from the models?
- Do not start S5-04 until confirmed

================================================================
TICKET S5-04 — Core Invariant & Regression Tests  [TESTER]
================================================================

THIS IS A TESTER AGENT TICKET.

WHAT TO BUILD:
Tests covering every invariant the product depends on, plus
a regression test for every bug found so far in this
project. From this sprint on, these run before any ticket
is confirmed.

## INVARIANT TESTS (the permanent regression targets from
TESTER.md):

  Sync idempotency / dedup:
  - Same external_id is never inserted twice
  - Insertion is deduplicated even when account_id differs
    between the two attempts (the exact S4-01 failure)
  - Re-sync of an already-synced range stores 0 rows

  Manual edit protection:
  - A row with manually_edited=TRUE is skipped by the
    categorization agent
  - It is skipped even when its category is NULL (the
    subtle case verified live in S3-05)

  Statistics correctness:
  - by_day contains every calendar day in range, including
    zero-activity days
  - by_week likewise
  - by_category percentages sum to exactly 100.0 across
    several awkward distributions (largest-remainder)
  - biggest_expense is the largest negative amount in range

  Color validation:
  - Valid colors accepted; each rejection rule fires
    (contrast <4.5:1, hue too near brand colors,
    saturation and lightness out of bounds)
  - A rejected AI color falls back to the category's
    existing color, never a random one
  - source='user' colors are never overwritten by AI

  Budget status:
  - Boundary cases: 79.9% on_track, 80.0% warning, 100.0%
    warning, 100.1% exceeded
  - spent_this_month uses the calendar month, not a
    rolling 30 days (freeze time across a month boundary
    and assert the reset)

  Job state transitions:
  - fetching → storing → categorizing →
    generating_insights → done
  - A failure at each stage writes status=failed with a
    message naming the correct stage

  Insight replace semantics (Option B):
  - Regenerating for a range deletes prior insights for
    that range only, leaving other ranges intact

  Error contracts:
  - Expired bank session → 401 with a message field
  - Database unavailable → 503 with a message field
  - Both {"message": ...} and {"detail": ...} shapes are
    handled (the S3-06 parser bug)

## REGRESSION TESTS (one per historical bug):
  - S4-01: account_id churn causing duplicate inserts
  - S3-06: HTTPException {"detail"} vs {"message"} parsing
  - S2-02: expiry-warning threshold rounding (7.7 days
    must trigger a 7-day warning — the Math.ceil bug)
  - S3-04: job timeout must fire even when poll responses
    are byte-identical (test the timer, not the payload)
  - S4-06: chat context includes biggest_expense
  - S3-07: color hash collision (now moot with the
    categories table, but assert two categories never
    share a color)

## COVERAGE REPORTING:
Add coverage measurement to the run command. Report the
current percentage; do not chase a target number this
sprint — the goal is that the invariants above are
covered, not that every line is.

ACCEPTANCE CRITERIA:
- All invariant tests present and passing
- All six regression tests present and passing
- Every test uses invented data, never Borys's real data
- Suite runs in under 2 minutes
- Coverage percentage reported
- docs/verification_debt.md updated: any manual
  verification now automated moves to CLOSED with a
  pointer to the test that replaced it

WHEN DONE:
- Full suite output with timings
- The coverage number
- List which previously-manual verifications are now
  automated
- Explain: which invariant was hardest to test and why?
- Do not start S5-05 until confirmed

================================================================
TICKET S5-05 — Job Reliability: Concurrency Lock & Crash
                 Detection
================================================================

BACKGROUND:
Two known gaps, both documented in ARCHITECTURE.md:
(1) No server-side lock on sync — two browser tabs or a
retry can run two sync jobs concurrently, double-running
categorization and insight generation on the same range
(found during S4-03's audit).
(2) If the Celery worker crashes mid-job, the job freezes
on its last written stage forever; only the frontend's
10-minute timeout surfaces it, as a generic "taking longer
than expected" (found in S4-02).

WHAT TO BUILD:

Part 1 — Sync concurrency lock:
  A Redis-based lock preventing concurrent sync jobs.
  - Key: sync_lock (scoped per user once Sprint 6 lands —
    write the key derivation so adding user_id later is a
    one-line change)
  - Acquired when a sync job is created, released when the
    job reaches done or failed
  - TTL slightly longer than the frontend's 10-minute
    timeout, so a crashed worker cannot deadlock sync
    permanently
  - POST /api/transactions/sync returns 409 with a clear
    message if a sync is already running, including the
    in-flight job_id so the frontend can attach to it
  - Frontend: on 409, attach to the existing job's polling
    rather than showing an error — the user clicked sync,
    a sync is happening, that is not an error state

Part 2 — Worker crash detection:
  - The Celery task writes a heartbeat timestamp into its
    Redis job state at each stage transition and
    periodically during long stages (categorization
    batches are the natural checkpoint)
  - GET /api/jobs/{job_id} computes staleness: if the job
    is not done/failed and the heartbeat is older than a
    threshold (suggest 2 minutes, justify your choice),
    return status=failed with a message naming the stage
    it died in ("Processing stopped unexpectedly during
    categorization — please try again")
  - The frontend's 10-minute timeout remains as a
    backstop, but should now rarely be what surfaces a
    crash

ACCEPTANCE CRITERIA:
- Two concurrent sync requests: the second gets 409 with
  the in-flight job_id, not a second job
- The frontend attaches to the existing job on 409
- Killing the celery_worker mid-job causes GET /api/jobs
  to report failed with the correct stage within the
  staleness threshold
- The lock is released on both success and failure paths
- The lock TTL cannot deadlock sync permanently (test
  this: kill the worker holding the lock, confirm sync
  works again after TTL expiry)
- Tests for all of the above (coordinate with the Tester
  agent — these are integration tests over the job
  lifecycle)

WHEN DONE:
- Show two concurrent syncs producing one job + a 409
- Show a killed worker surfacing as failed with the
  correct stage
- Show the lock releasing after a crash (post-TTL sync
  succeeds)
- Explain: why Redis for the lock rather than a database
  row or an in-process lock?
- Do not start S5-06 until confirmed

================================================================
TICKET S5-06 — Verification Debt Burn-Down
================================================================

WHAT TO BUILD:
Close every open entry in docs/verification_debt.md that
can be closed, and bring the rest current. This is the
ticket where four sprints of "structurally verified only"
gets resolved.

ITEMS:

  1. Claude provider live test — CONDITIONAL:
     If ANTHROPIC_API_KEY is now available: save via
     Settings, switch provider, run a full sync
     (categorization + insights), run a chat conversation
     with streaming, verify insights differ in character
     from Gemini's, switch back to Gemini. Close every
     Claude-related ledger entry (S2-04, S2-05, S2-06,
     S4-06 chat streaming).
     If still unavailable: re-date the entries, restate
     closure conditions, and state plainly that the Claude
     provider has never executed live — this must be
     resolved before Sprint 6 ships to any user who might
     select it. Consider whether the provider should be
     hidden in the Settings UI until verified, and
     recommend either way.

  2. Windows bind-mount permissions (S4-09):
     Cannot close on this host. Re-date, confirm closure
     condition is Sprint 6's Linux deployment.

  3. Any remaining open entries:
     Review each. Close what the new test suite (S5-03/04)
     now covers automatically — with a pointer to the
     specific test. Re-date and restate the rest.

  4. Ledger hygiene:
     At sprint close the ledger must contain zero entries
     without a current date and a concrete closure
     condition. Add a short header documenting the file's
     own conventions (statuses used, what a closure
     condition must contain) so future sessions maintain
     it consistently.

ACCEPTANCE CRITERIA:
- Every open entry either CLOSED with evidence, or OPEN
  with a current date and concrete closure condition
- Claude entries resolved or explicitly escalated with a
  recommendation
- Entries now covered by automated tests point to the test
- Ledger header documents its own conventions

WHEN DONE:
- Before/after ledger state
- The Claude decision and recommendation
- Count of entries closed vs carried
- Do not start S5-07 until confirmed

================================================================
TICKET S5-07 — Security Pass
================================================================

PRIORITY WITHIN TICKET: Item 1 first — it is a live
violation of a non-optional CLAUDE.md rule in shipped code.

WHAT TO BUILD:

  ITEM 1 — Date-range validation on all endpoints:
  CLAUDE.md mandates: "Validate date ranges on the backend.
  date_from must be before date_to. Maximum range: 365
  days. Return 400 with a clear message if violated."
  Verified in S4-10 review: only GET /api/insights/compare
  enforces this. GET /api/statistics, GET /api/transactions,
  GET /api/insights, and POST /api/transactions/sync all
  return 200 for backwards and >365-day ranges.
  Fix: extract the existing validation from the compare
  endpoint into a shared dependency or validator, apply it
  to all five. Same error shape everywhere.

  ITEM 2 — Input validation audit:
  Every endpoint taking user input: confirm Pydantic
  models constrain what they should (string lengths,
  numeric ranges, enum values where applicable). Report
  anything unconstrained. Fix what is clearly wrong; flag
  anything requiring a product decision.

  ITEM 3 — Rate limiting:
  Add basic rate limiting, prioritizing the endpoints that
  cost money or hit third parties: POST /api/chat, POST
  /api/transactions/sync, POST /api/analysis/*.
  Suggest slowapi or an equivalent lightweight approach.
  Limits should be generous for a single user but present
  — the point is a ceiling before Sprint 6 exposes this
  publicly, not throttling normal use. State the limits
  chosen and why.

  ITEM 4 — CORS production configuration:
  Current CORS accepts FRONTEND_ORIGIN. Verify it is not
  wildcard in any configuration path, and that the
  production deployment in Sprint 6 will have a correct
  value. Document what Sprint 6 must set.

  ITEM 5 — Secrets handling review:
  Audit against CLAUDE.md's rules: no secrets in code or
  comments, nothing sensitive at INFO log level (the
  logging fix in S4-09 enabled INFO — re-audit every
  logger call now that they actually emit), .gitignore
  covers .env, eb_session.json, dedup logs, certs, and
  any test artifacts. Confirm no financial data appears
  in logs at any level that runs in production.

ACCEPTANCE CRITERIA:
- All five date-range endpoints return 400 for backwards
  and >365-day ranges, with a consistent message shape
- Input validation findings reported; clear issues fixed
- Rate limiting active on the named endpoints, limits
  documented and justified
- CORS verified non-wildcard; Sprint 6 requirements
  documented
- Secrets audit complete, with the INFO-level log audit
  explicitly covered
- Tests for the date-range validation across all five
  endpoints (coordinate with Tester)

WHEN DONE:
- Show 400 responses from all five endpoints
- Report the input validation and secrets audit findings
- State the rate limits and the reasoning
- Explain: why is the INFO-level log audit specifically
  necessary now when it wasn't before?
- Do not start S5-08 until confirmed

================================================================
TICKET S5-08 — Sprint 5 Close
================================================================

WHAT TO BUILD:
No new work. Verification, regression, and documentation
accuracy.

ITEMS:

  1. Full test suite run — green, with timings and
     coverage reported.

  2. Full regression check against Sprint 1–4 features.
     The test suite covers the invariants; this covers the
     user-facing surfaces:
     a. Dashboard: summary cards, category donut, both
        time charts, budget widget, insights panel,
        compare periods
     b. Transactions: list, filters, search, pagination,
        manual edit with the edited badge
     c. Chat: empty state, streaming, multi-turn, markdown
     d. Settings: provider selection, API key, categories
        with color picker, budgets, bank connection status
     e. Sync end-to-end with real data

  3. ARCHITECTURE.md sprint-close audit (CLAUDE.md duty).
     Note: use section or symbol names rather than line
     numbers in references — line numbers went stale twice
     during Sprint 4.

  4. docs/multi_user_migration_plan.md re-verification:
     S5-02, S5-05, and S5-07 all changed the schema or
     endpoints. Confirm the plan from S5-01 is still
     accurate against the code as it now stands, and
     update it where those tickets changed the picture.
     Sprint 6 executes this plan — it must be correct at
     handoff, not correct at the moment it was written.

  5. Ledger final state: zero stale entries.

ACCEPTANCE CRITERIA:
- Test suite green
- All regression surfaces verified working
- ARCHITECTURE.md accurate, line-number references
  replaced with stable ones
- Multi-user migration plan re-verified post-S5-02/05/07
- Ledger current
- No console errors on any page

WHEN DONE:
- Suite output and coverage
- Regression results per surface
- What the migration plan re-verification changed
- Sprint 5 complete pending PM confirmation

================================================================
SPRINT 5 → SPRINT 6 HANDOFF
================================================================
Sprint 6 is "Multi-User & Deployment": execute the
migration plan, Google OAuth, per-user bank sessions,
public deployment with real HTTPS (retiring mkcert), and
first-time bank authorization entirely in the web UI (no
terminal step). The plan produced by S5-01 and re-verified
by S5-08 is its primary input.

================================================================
END OF SPRINT 5 TICKETS
================================================================
