Status: in-progress
Source: issued directly in Claude Code session, 2026-08-17

---

================================================================
TICKET S4-10 — Sprint 4 Polish, Verification-Debt Burn-Down &
                 End-to-End Check
================================================================

The sprint closer. No new features.

POLISH ITEMS:
1. Chat nav item: position (between Dashboard and
   Transactions), active state, hover style all correct.
2. Budget widget: appears only when budgets exist,
   disappears when all budgets are deleted, card click
   navigates to Settings → Budgets.
3. Comparison section: collapsed on every page load, not
   just the first.
4. Streaming error recovery — CONSENTED LIVE TEST, procedure
   already recorded in docs/verification_debt.md:
   kill the backend container mid-response → verify partial
   text + "Response interrupted" marker renders → bring the
   container back up.
5. No-API-key toast — CONSENTED LIVE TEST, procedure already
   recorded in the ledger: back up the current Gemini key
   value → blank it via Settings → send a chat message →
   verify the toast directs to Settings → restore the key →
   verify chat works again.
6. Dedup stability: run 3+ consecutive syncs, transaction
   count stays constant.

VERIFICATION-DEBT BURN-DOWN:
Go through every OPEN entry in docs/verification_debt.md:
- Close what the polish items above close (items 4 and 5).
- The Docker-ps port diff owed since S4-03: run
  docker compose ps now and diff against ARCHITECTURE.md's
  Services & Ports table; close the entry.
- Anything that cannot close this sprint gets its status
  re-confirmed as current and its closure condition
  re-stated (Claude live test → S5-06 or key arrival;
  Windows bind-mount permissions → Sprint 6 Linux
  deployment).
The ledger at sprint close should contain zero stale
entries — every line either CLOSED or OPEN with a current
date and a concrete closure condition.

FULL END-TO-END CHECK (document each step's result):
  a. docker compose up from a clean stop — 5 containers
     healthy, no SecurityWarning anywhere, non-root uids
  b. POST /sync → job_id in <500ms
  c. Poll: fetching → storing → categorizing (batch X/Y)
     → generating_insights → done
  d. Dashboard: categories, colors, insights correct
  e. Chat: "What was my biggest expense?" → matches
     GET /api/statistics (the S4-06 bounce fix, end-to-end)
  f. Two more chat messages — history holds
  g. Budgets in Settings reflect current-month spending
     correctly
  h. Dashboard budget widget states (on-track/warning/
     exceeded) match GET /api/budgets
  i. Transactions → manual edit one row
  j. Re-sync → edited row untouched
  k. Compare Periods: July vs August → deltas match
     statistics; arbitrary range works; Option B insight
     display correct
  l. Change a category color in Settings → donut + pills
     update
  m. Reconnect flow end-to-end (no copy-paste)
  n. 3+ syncs → stable transaction count
  o. If Claude key available: switch provider, re-sync,
     verify insights + chat streaming on Claude
     (if not: already covered by the ledger)

ARCHITECTURE.md SPRINT-CLOSE AUDIT (CLAUDE.md duty):
Read ARCHITECTURE.md top to bottom and verify every claim
against the running system. Stale claims are bugs — fix
them in this commit. Explicitly re-check: Services & Ports
(now with non-root uids), Data Flow (chat + comparison
flows), Database Tables (budgets), Invariants (including
the documented-as-NOT-enforced sync lock).

ACCEPTANCE CRITERIA:
- All 6 polish items pass, including both consented live
  error tests executed per their recorded procedures
- Ledger has zero stale entries
- End-to-end a–n pass (o conditional on the key)
- ARCHITECTURE.md verified accurate in this commit
- No console errors on any page; no regressions in
  Sprint 1–3 features

WHEN DONE:
- Per-step results for the full end-to-end check
- Before/after ledger state (which entries closed, which
  re-confirmed)
- The two error-test results specifically (screenshot or
  exact observed behavior)
- Any stale ARCHITECTURE.md claims found and fixed
- Sprint 4 complete pending PM confirmation
