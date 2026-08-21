Status: in-progress
Source: issued directly in Claude Code session, 2026-08-21

---

================================================================
TICKET S6-08 — Sprint 6 Close
================================================================

WHAT TO BUILD:
No new features. Verification and documentation accuracy,
same shape as every sprint close so far.

ITEMS:
  1. Full test suite green (coordinate with Tester — this
     sprint changed enormous amounts of schema and query
     logic; the suite needs real updates, not just a rerun)
  2. Full regression sweep, now AS the real logged-in user
     (Borys's real account) rather than the old no-auth
     state — every surface from prior sprint-close checks,
     plus login/logout/register
  3. ARCHITECTURE.md accuracy pass — Auth section, the public
     route enumeration, updated Data Flow reflecting
     scoped queries throughout
  4. docs/multi_user_migration_plan.md — mark it EXECUTED,
     not just planned; note anything that changed from the
     plan during real implementation
  5. verification_debt.md: log email verification and
     email-based password reset as explicit, dated OPEN
     items with Sprint 7 or later as the closure condition
     (transactional email infra needed)
  6. Ledger current, zero stale entries, as always

ACCEPTANCE CRITERIA:
- Test suite green
- Full regression passes as a real authenticated user
- ARCHITECTURE.md and migration plan both accurate
- No console errors
- Sprint 6 complete pending PM confirmation

WHEN DONE:
- Suite output
- Regression results
- Sprint 6 complete pending PM confirmation
