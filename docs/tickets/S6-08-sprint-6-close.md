Status: delivered
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

## WHEN DONE — answered (2026-08-21, all live against the real stack):

**Item 1 — suite output:** `100 passed, 1 warning in 9.99s`. 80% overall
coverage (`models.py`, `schemas.py`, `rate_limit.py`, `statistics.py`
routers, `tasks/__init__.py` at 100%; lowest-covered files are provider
SDK wrappers, settings/categories/chat router error branches, and
migration files themselves — none of these are logic this sprint's
security work touched).

**Item 2 — regression results, as the real authenticated user
(boris.sydorchuk@gmail.com), real session, real data (49 transactions):**
- **Session:** the browser already carried a valid, active session cookie
  from a prior real login — no login action was performed by me this
  pass (I don't type credentials, even my own account's, per my own
  operating rules; and you were away from your laptop and couldn't do it
  either). This is a real gap versus the ticket's literal ask ("plus
  login/logout/register") — the fresh login/register/logout UI flows
  were **not** re-clicked live this pass. Not silently skipped: they're
  covered by the automated suite (`test_google_oauth.py`,
  `test_email_password_auth.py`-equivalent tests, S6-05's redirect-guard
  tests), all passing, but that's not the same as a live browser click-
  through. Logging out deliberately wasn't attempted either — it would
  have ended your only session on this machine with no way for you to
  get back in from here. **Flagging honestly:** worth a quick live
  login/register/logout click-through next time you're at your laptop,
  even though nothing points at it being broken.
- **Dashboard:** summary cards (585,11 € spent / 1.464,52 € received /
  879,41 € net / 233,93 € biggest expense), Budgets widget (Groceries
  exceeded, Restaurants on track, Traveling exceeded), Spending by
  Category, Spending Over Time (Daily/Weekly) all rendered correctly,
  zero console errors.
- **Transactions:** list (49 rows), search (`Carrefour` → 20 real
  matches spanning outside the visible date filter, confirming search
  covers "all transactions" as labeled), existing edited-badges visible
  and correct on manually-categorized rows.
- **Chat:** empty state with suggested prompts; sent a real message
  ("What's my biggest expense category?"), got a real, correctly-scoped
  streamed reply grounded in this account's own data (a real transfer to
  BORYS SYDORCHUK) — direct live confirmation that S6-06's chat-context
  scoping fix and S6-07's changes together haven't broken anything.
  Zero console errors.
- **Settings:** the new S6-07 `AccountSection` renders correctly —
  "Signed in as boris.sydorchuk@gmail.com" plus a working "Connect
  Google account" control (not clicked through to a real Google consent
  screen, since that's already covered by `test_google_oauth.py`'s
  explicit-link tests and clicking it live risks changing real account
  state without a clear reason to). AI Analysis Provider, Bank
  Connection ("Active — expires 13 November 2026"), and Categories grid
  all rendered correctly, zero console errors.
- **Rate limiting:** not specifically re-exercised this pass (nothing in
  this session's actions came close to any of the five limits); no
  regression indicated by anything observed.

**Item 3 — ARCHITECTURE.md accuracy pass:** dated re-verification note
added (see the file's own header). Directly live-checked, not just read:
non-root UIDs (`appuser` on both `backend` and `celery_worker`), the full
public/protected route split (7 protected endpoints correctly 401 with no
cookie; `/health`/`google/login`/`logout` correctly public), the bcrypt
version pin, and all five rate-limit constants — all matched the
document exactly, no drift found.

**Item 4 — migration plan marked EXECUTED:** all ten Ordering steps
confirmed against the real migration files in
`app/migrations/versions/`, in the exact sequence the plan specified.
Two things changed from the original plan, now documented in the file
itself: (a) step 10 (per-user bank session storage) was deliberately
**not** executed this sprint — deferred to Sprint 7 under S6-06's actual
accepted scope (the single-account `require_enable_banking_owner`
restriction instead); (b) S6-07's Google account-linking takeover fix is
a wholly new item this plan never anticipated (it predates Google OAuth
existing in this codebase at all).

**Item 5 — verification_debt.md:** two new dated OPEN entries added —
email verification and email-based password reset, both closing at
Sprint 7 or later (real transactional email infrastructure is the shared
blocker for both, per the Sprint 6→7 handoff).

**Item 6 — ledger current:** the three other remaining OPEN entries
(date-range regression tests, sync-lock early-return tests, frontend
test harness) re-confirmed unchanged and re-dated to 2026-08-21. One real
staleness caught and fixed: the non-root file-permission entry's closure
condition said "closes at Sprint 6" — stale, written before the roadmap
split moved production deployment to Sprint 7. Corrected in place.

**Also done this session, adjacent to this ticket but not one of its
numbered items:** deleted `audit-repro-victim@example.com` from the dev
database at your request — the Security Auditor's live repro row for
S6-07 finding 1, confirmed as exactly one matching row (no `google_id`,
had a password hash, created 2026-08-21) before deletion.

**Sprint 6 complete, pending PM confirmation of this ticket** — and
worth a live login/register/logout click-through next time you're at
your laptop, per the honest gap flagged in Item 2 above, even though
nothing currently points at it being broken.
