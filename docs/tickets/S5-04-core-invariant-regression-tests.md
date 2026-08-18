Status: in-progress
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
