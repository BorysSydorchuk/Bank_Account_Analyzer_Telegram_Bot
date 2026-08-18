Status: delivered
Source: chat handoff to Tester session (TESTER.md boot prompt)

---

================================================================
TICKET S5-04 — Core Invariant & Regression Tests  [TESTER]
================================================================

WHAT TO BUILD:
Tests covering every invariant the product depends on, plus
a regression test for every bug found so far in this
project. From this sprint on, these run before any ticket
is confirmed.

## INVARIANT TESTS:

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
  - The categorization UPDATE re-checks manually_edited
    IS FALSE in its own WHERE clause, not just an earlier
    SELECT (the race-condition protection found during
    interview-prep study — test that a row edited between
    the SELECT and the UPDATE is still protected)

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

  Referential integrity (S5-02):
  - The FK rejects an unknown category at the DB level
  - The categorization agent's pre-write filter excludes
    unknown categories before any write is attempted,
    so the FK rejection above should never fire in
    normal operation — test both layers independently

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
sprint.

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

---

DELIVERY NOTES (Tester)

9 new test files, 53 new tests, on top of S5-03's 3 smoke tests — full
suite now 57 tests. All invariants and all six named regressions are
covered except two that are genuinely frontend-only (see FLAGGED below,
and docs/verification_debt.md's new OPEN entry).

WHEN DONE:

1. Run command and full output — `pytest` from `backend/`:

   57 passed, 1 warning in 5.03s

   (ran clean-state twice more back to back: 4.69s and 4.56s — no
   flakiness, no test-order dependency. Also ran a subset in forward and
   reverse file order — `test_job_pipeline.py`, `test_colors.py`,
   `test_referential_integrity.py` — specifically because
   `test_job_pipeline.py` is the one file that writes real, non-rolled-back
   rows (see `raw_db` below); both orders passed identically.)

2. Coverage number — **76%** (`app/`, 1578 statements, 381 missed), printed
   automatically by `pytest` now (`--cov=app --cov-report=term-missing` in
   `pyproject.toml`'s `addopts`). Not chasing a target this sprint per the
   ticket. Lowest-covered areas are all either provider SDK wrappers this
   suite deliberately never calls live (`gemini.py` 42%, `claude.py` 48% —
   TESTER.md prime directive 3), or routers/services S5-04 didn't touch
   because they weren't in scope (`categories.py` 41%, `settings.py` 41%,
   `comparison_service.py` 35%, `tasks/auth.py` 30% — the interactive-auth
   background poller, out of scope here).

3. Previously-manual verifications now automated (docs/verification_debt.md
   updated in this commit with pointers on both):
   - S5-02's FK rejection + pre-write filter (both layers, done live by
     hand against the real 350-row dataset on 2026-08-18) →
     `tests/test_referential_integrity.py` (both tests).
   - S4-06's biggest_expense-in-chat-context fix (verified live against the
     real dataset on 2026-08-17) → `tests/test_chat_context.py`.
   No entry moved to CLOSED, because neither original entry was OPEN debt
   to begin with — both were already live-verified and are now
   additionally guarded by a permanent test, which is noted inline on each
   CLOSED entry rather than as a new closure.

4. Hardest invariant to test, and why: **job state transitions**
   (`tests/test_job_pipeline.py`). Every other invariant in this ticket is
   testable through `db_session`/`client` — S5-03's transactional fixture
   already covers it. `app/tasks/analysis.py::_run()` breaks that pattern:
   it's a Celery task, not a FastAPI route, so it calls `SessionLocal()`
   directly instead of receiving a session through `get_db` dependency
   injection. That means `db_session`'s rollback-on-teardown session is
   invisible to it — data written through `db_session` in a test setup
   simply isn't there when `_run()` opens its own connection. Had to add a
   second fixture (`raw_db`, in `conftest.py`) that accepts real, committed
   writes and explicitly deletes everything it touched (plus resets
   `categories` back to seeded state) in teardown, since there's no
   transaction to roll back. The second complication compounding it: one
   provider instance serves three differently-shaped LLM calls in a row
   (categorization, color assignment, insights) inside a single run — the
   shared `fake_llm_provider` fixture only returns one fixed shape, so a
   dedicated multi-shape fake provider (`_OrchestrationFakeProvider`,
   local to that file) had to be built, dispatching on which agent's
   system prompt is asking.

FLAGGED (out of scope):
- **S2-02 and S3-04 regression tests, and S3-06's frontend half, are not
  built.** All three bugs and their fixes live in frontend TypeScript
  (`SessionBanner.tsx`, `useDashboard.ts`, `lib/api.ts`) with no test
  runner configured in `kbc_analyzer/frontend/` at all yet (confirmed: no
  vitest/jest, no test script in `package.json`). Standing up a frontend
  test harness is itself an S5-03-sized task; folding it unprompted into
  this backend-focused ticket would be scope creep past what S5-04 asked
  for. Recorded as a new OPEN entry in docs/verification_debt.md with the
  specific close-out procedure. Suggest a dedicated frontend-test-infra
  ticket, PM's call on which sprint.
- **`colors.py`'s "too light" upper-lightness rule (lightness > 55%) looks
  unreachable in practice.** Constructed and swept colors across hue/
  saturation combinations trying to isolate it from the contrast check —
  at every saturation inside the valid 40–80% range, contrast against
  white already drops below the 4.5:1 minimum before lightness reaches
  56%, so the contrast check (which runs first and returns immediately)
  always fires first. `tests/test_colors.py` tests the rule that's
  actually reachable (`FAILS_LIGHTNESS_TOO_LOW`) and both saturation
  bounds, contrast, and hue — all five confirmed independently reachable.
  Not fixing (TESTER.md: report, never touch application code) — worth a
  look next time `colors.py` is touched, in case the lightness upper bound
  was meant to catch something the contrast check doesn't.
- **The 401 error-contract test
  (`test_expired_bank_session_maps_to_401_with_a_message_field`) calls
  `app.main.eb_auth_error_handler` directly, not through a live route.**
  Traced this while writing the test: since S4-02 moved the Enable Banking
  fetch into the background Celery job, the only place that raises
  `EnableBankingAuthError` (`EnableBankingService.get_account_uids`,
  called from `tasks/analysis.py`) now catches it itself and writes a job
  status — no current route lets that exception reach FastAPI's
  registered handler. The handler itself is still correct and still
  registered; it's presently dead code from any live request's
  perspective. Testing it directly proves the contract exists in case a
  future route needs it, but doesn't prove any current endpoint actually
  returns a 401 this way (because none does). Worth a PM decision: remove
  the now-unreachable handler, or is there a planned route that will use
  it?

Ready for S5-05 whenever you confirm this one.
