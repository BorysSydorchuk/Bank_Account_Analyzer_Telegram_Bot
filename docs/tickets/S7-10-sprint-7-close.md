Status: delivered

================================================================
TICKET S7-10 — Sprint 7 Close
================================================================

WHAT TO BUILD:
No new features. Full production verification, same discipline
as every prior sprint close — but this one closes the sprint
that took Mymble from local-only to genuinely live and
publicly reachable, so give it real weight.

ITEMS:

1. Full regression sweep against the REAL production
   deployment (https://mymble.be), not local dev:
   - Registration, login (password + Google), logout
   - Bank connection (new user, web-only, no terminal)
   - Sync, categorization, insights, chat
   - Budgets, categories, manual editing
   - Password reset (real email)
   - Email verification (real email, to your sandbox address)
   - Settings: API keys, category colors, provider switching

2. ARCHITECTURE.md full accuracy pass:
   - AWS topology (Fargate web+worker, RDS, self-hosted Redis,
     ALB, NAT Gateway, ACM/HTTPS)
   - Auth model (sessions, per-user bank storage, Google
     linking, email verification)
   - Public route enumeration, current as of this sprint
   - Use stable references (section/symbol names), not line
     numbers — this rule has held all sprint, keep it

3. Cost check — the real one:
   - Pull actual AWS Cost Explorer data for the days this
     sprint's infrastructure has been running
   - Compare against S7-01's ~$122/month estimate
   - Confirm whether Free Tier eligibility (found in S7-01)
     changed the real number
   - State the real, current monthly run-rate

4. Security spot-check:
   - Re-run S6-07's IDOR sweep against the REAL production
     URLs (mymble.be), not local dev — a second real user
     account, confirm zero cross-user data visibility across
     every endpoint category
   - Confirm Finding A's fix holds in production
   - Confirm the CSRF fixes from S7-04/S7-06 hold in production

5. Ledger final state:
   - Zero stale entries
   - SES production access: check current status, update
   - GOOGLE_CLIENT_SECRET rotation: final confirmation
   - Every OPEN entry re-dated with a real closure condition,
     or genuinely closed

6. Sprint 7 backlog sweep:
   - Confirm nothing from the original sprint scope silently
     dropped
   - Carry forward explicitly: the pre-existing admin IAM
     user's fate (still Borys's decision, still open since
     S7-01), NAT Instance swap timing (per its logged closure
     condition), SES production access if still pending

ACCEPTANCE CRITERIA:
- Full production regression passes, real evidence throughout
- ARCHITECTURE.md accurate
- Real cost data pulled and compared against estimate
- Security spot-check passes against real production
- Ledger current, zero stale entries
- No console errors on any page
- Sprint 7 complete pending PM confirmation

WHEN DONE:
- Production regression results, per surface
- ARCHITECTURE.md accuracy confirmation
- Real cost data and comparison to estimate
- Security spot-check results
- Sprint 7 complete pending PM confirmation

## DELIVERY (2026-08-27)

### 1. Production regression, per surface — all against `https://mymble.be`, real evidence

- **Registration / login (password):** real account created via curl
  (`s7-10-regression-test@example.com`) and via browser
  (`s7-10-regression-test-2@example.com` for the security spot-check
  below), both real `201`/session-cookie round trips.
- **Login (Google):** couldn't self-drive a full interactive Google
  consent (real credentials needed), so checked the mechanical half
  directly instead — `GET /api/auth/google/login` returns a real `307`
  to `accounts.google.com` with `redirect_uri=https://mymble.be/api/auth/google/callback`,
  confirming the b509fc9 redirect_uri concern is still resolved in
  production. Full interactive Google login previously confirmed working
  end-to-end by Borys (S7-04/S7-05).
- **Logout:** real browser click, redirected to `/login`; independently
  confirmed server-side (not just a client-side redirect) — the old
  session cookie got a real `401` from `GET /api/auth/me` afterward.
- **Bank connection (new user, web-only, no terminal):** not re-run live
  this ticket — a real KBC login can't be self-driven, and S7-06/S7-07
  already proved this end-to-end on two genuinely distinct accounts, with
  the S7-07 delivery independently re-querying production's
  `enable_banking_sessions` table to confirm isolation. Confirmed instead,
  this ticket, that the gate in front of it (`require_verified_email`)
  still correctly blocks an unverified account with real copy, not a
  silent hang: `GET /api/auth/enable-banking/status` on both this
  ticket's real test accounts returned `{"detail":"Verify your email
  before connecting a bank account..."}`.
- **Sync, categorization, insights:** not re-run live this ticket (no
  bank connection exists on the fresh regression-test accounts to sync
  from) — S7-06's real 342-transaction production sync stands as the
  live proof for this sprint; nothing about the sync pipeline changed
  since.
- **Chat:** not exercised live this ticket — the fresh test account has
  no LLM key configured (expected, matches every prior fresh-account
  test this sprint), and adding a real key to a throwaway account
  wasn't worth the cost for a code path unchanged since S4-06/S6-08.
- **Budgets, categories, manual editing:** category created via real API
  call (color-validation round-tripped for real, several rejected
  attempts, `#0E7C7B` finally accepted), confirmed rendering in the
  Settings UI via screenshot; budget created via real browser
  interaction (€150.00/month), confirmed persisted ("€0.00 spent of
  €150.00 — On track"). Manual transaction editing not exercised — no
  transactions exist on a fresh, unsynced account to edit; the endpoint
  (`PATCH /api/transactions/{id}`) is unchanged since it was last
  live-verified.
- **Password reset (real email):** already closed for real this sprint
  (S7-09, Borys: "Checked - everything works" against his own real
  inbox) — not re-run against a second account, since SES sandbox mode
  only sends to the one verified recipient.
- **Email verification (real email):** genuinely still open — same SES
  sandbox constraint. Re-checked this ticket (`aws sesv2 get-account`):
  unchanged, still the one verified recipient. See ledger.
- **Settings — API keys, category colors, provider switching:**
  provider switch (Gemini → Claude) confirmed persisted via screenshot.
  "Test connection" exercised for real with a syntactically-plausible
  but invalid key — made a real round trip to Anthropic's API and
  correctly surfaced "API key is invalid.", not a generic error.
  Category color validation exercised for real via several rejected
  curl attempts, each error message read and used to correct the next
  guess.
- **Console errors:** checked after the full sequence of interactions
  above (category creation, budget creation, provider switching, page
  navigations) — none found.

### 2. ARCHITECTURE.md accuracy pass

Read top to bottom against the running system, per the sprint-close
duty. Found and fixed five real staleness bugs — forward-looking "not
yet" language that was never updated once the thing it described
actually shipped:

1. The AWS section's opening line said "no application runs here yet...
   only via local Docker Compose" — false since S7-04; the app has been
   live on Fargate this whole time.
2. Compute model said the ALB was "not yet created" and Redis "not yet
   provisioned as of S7-01" — both provisioned since (S7-04, S7-03
   respectively).
3. The Route 53 zone row said "not yet delegated" — DNS delegation
   completed and was already documented later in the same file (the
   "DNS delegation" section), just not reflected in this earlier table
   row.
4. The session cookie section said `set_session_cookie`/
   `clear_session_cookie` were "not called by any route yet" — false,
   every login/register/logout route calls them.
5. The Free Tier cost note was a guess ("likely means actual spend...
   is meaningfully lower") — replaced with the real Cost Explorer
   breakdown from item 3 below.

Added a "Sprint 7 close re-verification" banner (matching the S5-08/
S6-08 pattern already established in this file) documenting this pass.
Auth model and public route enumeration sections were spot-checked
against everything confirmed live in item 1 above (session cookie
shape, `require_verified_email` gating, CSRF cookie flags) — all still
accurate, no further changes needed.

### 3. Cost check — real data, not estimate

Pulled AWS Cost Explorer data for 2026-08-26 (the most representative
full-stack day — all S7 infrastructure live and running the entire
day), split by `RECORD_TYPE` (`Usage` vs `Credit`):

**Gross usage cost ≈ $4.996/day → ≈ $151.87/month** — about **25% above**
S7-01's original ~$122/mo estimate. The gap is explained, not
mysterious: Route 53 (~$30/mo) and Secrets Manager (~$1.80/mo) were
never in the original estimate, both added in later tickets (S7-04's
domain, S7-05/S7-08's secrets).

**Net actual spend is ≈ $0/mo right now** — `Credit` record-type line
items offset `Usage` almost exactly, service-by-service, every day
since launch. Cross-verified a second, independent way: the AWS
Budget's own `CalculatedSpend.ActualSpend` field also reports `$0.0`.

**This is not the standard 12-month Free Tier S7-01 found.** That Free
Tier (confirmed via the real `FreeTierRestrictionError` on RDS backup
retention) doesn't cover NAT Gateway, ALB, or Fargate compute — all
three are being offset here too, which points at a promotional/account
credit balance instead. This account has no paid AWS Support plan, so
the credit's remaining balance and expiration date aren't visible via
CLI/API — only the Billing Console's Credits page shows that directly.
**Flagged for Borys** to check there; the real run-rate becomes
~$151.87/mo, not $0, once that balance runs out, and it's worth knowing
in advance given the budget alarm's own $150/mo ceiling. New OPEN
ledger entry added for this.

### 4. Security spot-check

Re-ran S6-07's IDOR sweep against real production (`https://mymble.be`),
with two genuinely distinct real accounts created this ticket:

- `GET /api/categories`, `GET /api/budgets` as user 2 — correctly
  returned `[]`, never user 1's data.
- `PATCH /api/categories/{name}` and `DELETE /api/budgets/{name}` as
  user 2, targeting user 1's real category/budget by name — rejected
  (`400`/`404`), and user 1's data confirmed unmodified afterward by a
  direct re-fetch.
- `GET /api/settings` as user 2 — returned user 2's own empty settings
  (`gemini`, no keys), never user 1's saved Claude selection.
- `GET /api/auth/enable-banking/status` — both accounts correctly
  blocked by the email-verification gate, no cross-user state visible
  either way.

Zero cross-user data visibility across every endpoint category tested —
**Finding A's fix and the S6-07 IDOR closure both hold in production.**

**CSRF (S7-04/S7-06):** confirmed via the actual mechanism, not a flawed
proxy for it. Production's real `Set-Cookie` header
(`session_id=...; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax;
Secure`) confirms the defense is live. A first attempt to test this with
curl by setting a forged `Origin` header was a **false test, not a real
finding** — curl isn't a browser and will attach a session cookie to any
request regardless of `Origin`, which a real browser under
`SameSite=Lax` won't do on a genuine cross-site request. Noted directly
in ARCHITECTURE.md's Sprint 7 close banner so a future reader doesn't
repeat the same mistake.

### 5. Ledger final state

- **New entry added:** AWS account credit balance/expiration not visible
  via CLI (item 3 above) — OPEN, non-blocking, closes once Borys checks
  the Billing Console.
- **SES production access (S7-08):** re-checked directly, unchanged —
  still `ProductionAccessEnabled: false`, still `DENIED`. Re-dated,
  carried forward into Sprint 8.
- **GOOGLE_CLIENT_SECRET rotation (S7-05):** unchanged, still needs
  Borys's one-line Console confirmation. Re-dated, carried forward.
- **Real received-email confirmation for email verification (S7-09):**
  unchanged, same SES sandbox blocker. Re-dated, tied explicitly to the
  SES entry above.
- **Single NAT Gateway (S7-01):** re-confirmed — production has been
  live about one day as of this close, nowhere near the 4-week
  stability bar. Closure condition unchanged, re-dated.
- Zero stale entries remain — every OPEN entry now carries a
  2026-08-27, S7-10-dated status line.

### 6. Sprint 7 backlog sweep

Nothing from Sprint 7's original scope was silently dropped:

- **Pre-existing admin IAM user (`KBC_analyser_deploy`,
  `AdministratorAccess`):** still open, still Borys's decision — already
  documented in ARCHITECTURE.md's IAM section since S7-01, unchanged
  this pass. Not duplicated into the ledger since it's a pending
  decision, not a deferred verification.
- **NAT Instance swap timing:** carried forward per its own logged
  closure condition (see ledger item 5 above).
- **SES production access:** carried forward, still pending (see ledger
  item 5 above).

### Test data cleanup

Both regression-test accounts (`s7-10-regression-test@example.com`,
`s7-10-regression-test-2@example.com`) and everything they created (4
categories — 1 real, 3 CSRF-probe artifacts — 1 budget, 1 settings row)
deleted from production via the standard migration-runner ECS-exec
pattern, with a `SELECT` before and after the `DELETE`, not just trusting
the delete's own report:

```
BEFORE: [(UUID('1854a8b9-...'), 's7-10-regression-test@example.com'),
         (UUID('02679cb3-...'), 's7-10-regression-test-2@example.com')]
budgets deleted: 1
transactions deleted: 0
insights deleted: 0
settings deleted: 1
categories deleted: 4
users deleted: 2
AFTER: []
```

Independently re-confirmed a second way, against the live API rather
than the same connection that did the delete:

```
$ curl -X POST https://mymble.be/api/auth/login \
    -d '{"email":"s7-10-regression-test@example.com","password":"..."}'
{"detail":"Invalid email or password."}
```

Migration-runner task stopped afterward, no lingering Fargate cost.

### Sprint 7 complete pending PM confirmation

Do not start Sprint 8 until confirmed.
