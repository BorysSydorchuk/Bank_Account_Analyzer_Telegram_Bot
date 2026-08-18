Status: in-progress
Source: issued directly in Claude Code session, 2026-08-18

---

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
  While here: also check settings_service.py's
  VALID_PROVIDERS vs API_KEY_FIELD_BY_PROVIDER — the
  KeyError robustness gap flagged in S5-06's review.
  Collapse them into one source of truth (a single dict
  or enum that both derive from) so a future provider
  added to one can't silently miss the other.

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
  While here: apply the new verification_debt.md
  Conventions rule (shape-and-schema evidence only, no
  real amounts/merchants) as a general check — confirm
  no OTHER committed file besides the two already-flagged
  ledger entries carries real financial data. If any do,
  flag them the same way (documented exception), don't
  silently edit.

ACCEPTANCE CRITERIA:
- All five date-range endpoints return 400 for backwards
  and >365-day ranges, with a consistent message shape
- Input validation findings reported; clear issues fixed
- VALID_PROVIDERS / API_KEY_FIELD_BY_PROVIDER collapsed
  to one source of truth
- Rate limiting active on the named endpoints, limits
  documented and justified
- CORS verified non-wildcard; Sprint 6 requirements
  documented
- Secrets audit complete, with the INFO-level log audit
  explicitly covered, and a repo-wide real-data check done
- Tests for the date-range validation across all five
  endpoints (coordinate with Tester — flag to them, don't
  build the tests yourself if S5-04's suite structure
  isn't yours to extend directly; check current convention
  established this sprint)

WHEN DONE:
- Show 400 responses from all five endpoints
- Report the input validation, provider-mapping, and
  secrets audit findings
- State the rate limits and the reasoning
- Explain: why is the INFO-level log audit specifically
  necessary now when it wasn't before?
- Do not start S5-08 until confirmed
