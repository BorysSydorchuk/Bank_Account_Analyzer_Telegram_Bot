# Verification Debt Ledger

Tracks every verification that was deferred, or completed structurally-only
(no live execution), per CLAUDE.md's testing standard. Each entry: what was
deferred, why, what would close it, and current status. Entries are removed
(not just marked closed) once the live verification actually runs — git
history is the record of when that happened.

Formal creation of this file is an S4-10 deliverable; created early per the
S4-06 handoff instruction ("if you defer any verification before then,
create it early rather than tracking by memory").

## Conventions (S5-06)

- **Every OPEN entry needs, at minimum:** what was deferred, why (the actual
  blocker, not just "not done yet"), what would close it (a concrete,
  actionable procedure — not "verify this eventually"), and a `Status:`
  line that is both current-dated and states a real closure condition
  (an event: "closes at Sprint 6," "closes once a real API key exists" —
  not an open-ended "someday").
- **An entry with no plausible closure date** (e.g. blocked on a platform
  limitation this host can't fix) still needs a *closure condition*, even
  if that condition is itself a future sprint or an external dependency.
  "Can't close on this host" is acceptable; "not sure when" is not.
- **Re-dating at sprint close:** every sprint-close ticket (S4-10 did this
  for Sprint 4; S5-06 for Sprint 5) re-confirms every remaining OPEN entry
  against current reality — re-date it if still accurate, restate it if the
  situation changed, close it if something (a new test, a new credential, a
  new environment) finally made closure possible.
- **CLOSED entries stay in this file** (a `CLOSED (recent)` section, not
  deleted) as long as they're useful evidence of *how* something was
  verified — trimmed or archived once stale enough that git history alone
  is a sufficient record.
- **Evidence for a CLOSED entry must be shape-and-schema only** (field
  names, response structure, counts) — never real transaction amounts,
  real merchant names, or real budget figures. Use placeholder values
  (`€XXX.XX`, `Merchant Name`) even when the real live-test output had
  specifics. This file is meant to stay safe to read/share without being
  a second copy of financial data (CLAUDE.md's logging rules exist for
  the same reason). Pre-existing entries written before this rule
  (S4-06, S5-06) are **not** retroactively edited for it — flagged as
  known exceptions in place rather than rewriting a two-sprint-old
  exposure that isn't worth a force-push.

---

## OPEN

### Real ING transaction-data verification — no data available from this test account (S8-02, narrowed S8-03)

- **What was deferred:** verifying the categorization/sync/insights
  pipeline against real ING transaction data, per-institution
  data-shape handling (description formats, currency, dates), and
  `transactions.account_id`'s ability to disambiguate KBC-sourced from
  ING-sourced rows with two live, real datasets.
  **Narrowed by S8-03 (2026-08-28):** the `external_id` collision
  question this entry originally also covered is now separately
  resolved — S8-03 verified the core `UNIQUE (user_id, external_id)`
  mechanism for real using two distinct real KBC accounts (Enable
  Banking's collision risk is scoped per-account, not
  per-institution, so this is the same mechanism a KBC+ING test would
  exercise). Zero collisions found across 343 real transactions
  (ARCHITECTURE.md's Invariants section). What remains open here is
  narrower: categorization/data-shape verification against real ING
  content, and the specifically cross-institution (KBC+ING) variant of
  the collision test — not the collision mechanism itself, which no
  longer needs ING data to be considered verified.
- **Why:** the real ING connection made on `boris.sydorchuk@gmail.com`
  is genuinely valid — Enable Banking's own `GET /sessions/{id}`
  confirms `"status": "AUTHORIZED"` — but reports zero linked accounts
  (`"accounts": []`), both before and after reconnecting with explicit
  account selection at ING's own consent screen. Borys reports this
  real ING account had real transactions roughly six months ago,
  which argues against simple account dormancy as the explanation.
  The actual cause is unresolved as of this entry — not confirmed to
  be an Enable Banking/ING quirk, not confirmed to be something this
  app's code could fix, genuinely unknown. With zero accounts, there
  is no real ING transaction data to verify any of the above against.
- **What would close it:** Borys connects a different, actively-used
  real ING account (his own or someone else's, with consent) in a
  later ticket and a real sync is run against it — his explicit call,
  not fixed here by forcing a synthetic pass.
- **Status (re-confirmed 2026-08-28, S8-03):** OPEN, narrowed — the
  collision-risk portion this entry used to cover is closed (see
  ARCHITECTURE.md's Invariants section); what's left is
  categorization/data-shape verification against real ING content and
  the cross-institution collision variant specifically. Closes
  whenever that real test happens, ticket number not yet assigned.

### AWS account credit balance and expiration — not visible via CLI (S7-10)

- **What was deferred:** confirming when the credit currently offsetting
  this account's entire AWS bill runs out. Real Cost Explorer data (see
  ARCHITECTURE.md's Sprint 7 close re-verification note) shows gross
  infrastructure usage running ≈$151.87/mo, but `Credit` record-type
  line items offset `Usage` almost exactly, service-by-service, every
  day since production launch — net actual spend is ≈$0/mo, cross-
  confirmed against the AWS Budget's own `ActualSpend` field.
- **Why:** this doesn't look like the standard 12-month RDS/EC2 Free
  Tier S7-01 originally found (that doesn't cover NAT Gateway, ALB, or
  Fargate compute, all three of which are being offset here too) — it
  reads more like a promotional/account credit balance. This account
  has no paid AWS Support plan, so its remaining balance and expiration
  date aren't visible through the CLI/API at all; only the Billing
  Console's Credits page shows that directly.
- **What would close it:** Borys checks the Billing Console's Credits
  page directly and reports the remaining balance and expiration date.
  Once known, the real monthly run-rate (gross ≈$151.87/mo, since that's
  what applies once the credit is exhausted) should be compared against
  the $150/mo budget alarm threshold — they're close enough that the
  budget notification at 100% may fire close to when the credit itself
  runs out, worth knowing in advance rather than discovering via a
  billing surprise.
- **Status (2026-08-27, S7-10):** OPEN — non-blocking (net spend is
  currently $0, nothing is at risk today); closes once Borys reports the
  credit balance/expiration from the Billing Console.


### GOOGLE_CLIENT_SECRET rotation — AWS-side confirmed, Google Console side not independently verifiable from this environment (S7-05)

- **What was deferred:** S7-04 disclosed the real
  `GOOGLE_CLIENT_SECRET` was printed in full during a debug session and
  recommended regenerating it in Google Cloud Console. S7-05's audit
  found strong circumstantial evidence this happened (the secret has two
  Secrets Manager versions, changed via `PutSecretValue` ~7 minutes
  after the commit that disclosed the exposure and made the
  recommendation), but Google Cloud Console's own audit trail — the
  only place that could directly confirm a new secret was generated
  there and the old one is no longer valid — is outside this
  environment's access entirely.
- **Why:** No API/CLI access to Google Cloud Console exists in this
  project's tooling; only Borys can check the OAuth client's secret
  list in Console directly.
- **What would close it:** Borys confirms in Console that the secret
  currently in Secrets Manager corresponds to a freshly-generated value
  (not the exposed one), or regenerates it now if it doesn't.
- **Status (re-confirmed 2026-08-27, S7-10 sprint close):** OPEN — still
  no Google Cloud Console API/CLI access exists in this environment;
  nothing about this changed since S7-05. Carried forward into Sprint 8.
  Closes on Borys's one-line confirmation (or a fresh rotation if the
  confirmation comes back negative).

### Date-range validation regression tests — not built (S5-07)

- **What was deferred:** Automated tests for the S5-07 date-range fix
  across all five endpoints (`GET /api/statistics`, `GET
  /api/transactions`, `GET /api/insights`, `POST /api/transactions/sync`,
  `GET /api/insights/compare`) — one backwards-range and one >365-day
  case per endpoint, asserting the shared `{"detail": "date_from/date_to:
  ..."}` error shape from `date_range.py`.
- **Why:** Test-suite structure (`tests/`, `pyproject.toml`'s `test`
  dependency group) is Tester-owned this sprint, matching the convention
  established at S5-04/S5-05 — Codee flags what's needed rather than
  extending that suite directly.
- **What would close it:** Ten small tests (five endpoints × two cases),
  most naturally alongside `test_error_contracts.py` or a new
  `test_date_range.py` — each just needs a live TestClient call with a
  backwards or >365-day range and an assertion on the 400 body.
- **Status (re-confirmed 2026-08-27, S7-10 sprint close):** OPEN — content
  unchanged since S6-08; no target session assigned yet, still belongs to
  the Tester's S5-04 follow-on work, same as the sync-lock entry below.

### Sync lock release on two failure early-returns — never empirically triggered (S5-05)

- **What was deferred:** `sync_lock.release()` (S5-05) sits in a single
  `finally` block wrapping the whole task body in `tasks/analysis.py`, so
  it runs on every exit path by Python's own unconditional `finally`
  guarantee — but only the success path and a hard-killed-worker path
  were actually exercised live. The two in-code failure early-returns
  never had a real run go through them while checking the lock
  afterward:
  1. The Enable Banking auth/error early-return (`tasks/analysis.py`
     around line 67-72, `except (EnableBankingAuthError,
     EnableBankingError)`).
  2. The `every_batch_failed` early-return (line 130-142) — every
     categorization batch call to the LLM failing while a provider *is*
     configured. Distinct from, and not covered by, the existing
     `test_categorizing_stage_failure_when_no_provider_configured_reports_failed_status`
     test, which exercises the earlier "no API key configured" branch in
     `analysis_service.categorize_transactions`, not this one.
- **Why:** Reasoned from Python's `finally` semantics instead — the same
  block already covers the success path, which was live-verified (a
  completed job's lock released immediately, a following sync got `200`
  without waiting on TTL). Forcing either failure path live in this
  session would have meant deliberately breaking the real Enable Banking
  session or the real Gemini API key, which per CLAUDE.md's testing
  standard on destructive verifications isn't something to do
  unilaterally — Borys's call, not made yet.
- **What would close it:** The same monkeypatch technique
  `test_storing_stage_failure_reports_failed_status_naming_that_stage`
  and `test_fetching_stage_failure_reports_failed_status_naming_that_stage`
  already use in `tests/test_job_pipeline.py` (`mock_enable_banking_client
  .expire_session()` for the first path; a fake provider whose batches all
  raise, for the `every_batch_failed` path) — extended in each case to
  also assert `sync_lock.get_holder()` is `None` after the run, not just
  that `job_store` reports `status: "failed"`. This is Tester-agent scope
  (S5-04's follow-on suite), not something to build here.
- **Status (re-confirmed 2026-08-27, S7-10 sprint close):** OPEN — content
  unchanged since S6-08; no target session assigned yet, still belongs to
  the Tester's S5-04 follow-on work.

### Three regression tests deferred — no frontend test harness yet (S5-04)

- **What was deferred:** Automated regression tests for S2-02 (the
  `Math.ceil` expiry-warning rounding bug), S3-04 (job-timeout must fire
  even when poll responses are byte-identical), and the frontend half of
  S3-06 (the `{"message"}` vs `{"detail"}` error-shape parser).
- **Why:** All three bugs — and their fixes — live in frontend TypeScript
  (`SessionBanner.tsx`'s `WARNING_THRESHOLD_DAYS` comparison,
  `useDashboard.ts`'s poll-timeout timer, `lib/api.ts`'s error parser), not
  backend Python. `kbc_analyzer/frontend/` has no test runner configured at
  all yet (no vitest/jest, no `package.json` test script) — TESTER.md's own
  SUITE RULES anticipate this ("`npm test` from frontend/ when frontend
  tests exist"). Standing up a frontend test harness from scratch is
  itself an S5-03-sized task, not something to fold unprompted into S5-04's
  backend invariant/regression ticket (PROMPT 5 scope discipline). The
  backend half of S3-06 (that both response shapes are genuinely,
  currently produced by the live API) IS covered —
  `tests/test_error_contracts.py::test_both_message_and_detail_error_shapes_are_genuinely_live_S3_06_regression`.
- **What would close it:** A frontend test ticket (vitest + React Testing
  Library, most likely) standing up `npm test`, followed by three targeted
  regression tests: one asserting the 7.7-day case renders the warning
  banner, one asserting a stalled poll still times out on identical
  payloads, one asserting the api client surfaces an error message from
  either JSON shape.
- **Status (re-confirmed 2026-08-27, S7-10 sprint close):** OPEN —
  `kbc_analyzer/frontend/package.json` still has no `test` script and no
  vitest/jest dependency; nothing has changed since S5-04. Flagged to PM
  for a frontend-test-infrastructure ticket; no target sprint assigned yet.

---

### Single NAT Gateway — NAT Instance swap deferred (S7-01)

- **What was deferred:** S7-01's final architecture uses a managed AWS NAT
  Gateway (~$38/mo in eu-central-1: $0.052/hr + $0.052/GB processed) rather
  than a self-managed NAT Instance (~$3-8/mo on a t4g.nano/micro), even
  though the NAT Instance is cheaper and was seriously considered.
- **Why:** A NAT Instance has no AWS-provided failover — a single EC2
  instance is a manual-recovery single point of failure for all outbound
  traffic from the private subnets (RDS updates, ECR pulls, external API
  calls). For an app about to hold real bank data, on a deployment that
  hasn't run in production at all yet, that risk isn't worth the ~$30-35/mo
  saving until the deployment has proven itself stable. This was an
  explicit ticket instruction (S7-01), not an oversight — see
  `docs/tickets/S7-01-aws-foundation.md`.
- **What would close it:** Once the production deployment (S7-04 onward)
  has run stable for a sustained period (proposed: 4 consecutive weeks with
  no NAT-related incident), swap `aws_nat_gateway.single` in
  `infra/vpc.tf` for a self-managed NAT instance (EC2 t4g.nano/micro with
  IP forwarding + a route table update), and document the swap's own
  downtime/rollback plan before doing it on a live system.
- **Status (re-confirmed 2026-08-27, S7-10 sprint close):** OPEN —
  production has been live since S7-04 (2026-08-26), roughly one day as
  of this close, nowhere near the 4-week stability bar. Closure condition
  still makes sense as written — revisit again at the next sprint close.

---

## CLOSED (recent)

### SES still in sandbox mode — production access request pending (S7-08, closed 2026-08-28, S8-05)

- **What was deferred:** real users other than the one verified test
  recipient (`boris.sydorchuk@gmail.com`) could not receive email from
  Mymble — SES sandbox mode only sends to individually-verified
  recipient identities. Sandbox-mode sending itself was confirmed
  working (real email, real receipt, S7-08).
- **Why it stayed open so long:** `aws sesv2 put-account-details` came
  back `ReviewDetails.Status: DENIED` almost immediately — not a final
  rejection, but AWS's automated first pass asking for more detail
  (sending frequency, recipient-list handling, bounce/complaint/
  unsubscribe handling, example emails). A full reply with real,
  verified account facts was submitted via AWS Support Center (Case
  `178778410400368`) — this account has no paid AWS Support plan, so
  there was no API visibility into the review reasoning or a way to
  poll case status/communications programmatically; only the console
  showed it, and only a human could act on it. Re-confirmed
  2026-08-28 (S8-05): still `ProductionAccessEnabled: false`,
  `ReviewDetails.Status: DENIED`, unchanged since S7-08/S7-10, more
  than 24 hours past the point AWS said it would give an initial
  response. Two real registration attempts failed for exactly this
  reason in the meantime — `liyaberry27@gmail.com` and
  `secta022024@gmail.com`, both confirmed unverified, with real
  `AccessDenied` tracebacks in CloudWatch Logs naming the *recipient's*
  identity ARN specifically (sandbox mode's IAM check for
  `ses:SendEmail` authorizes both sender and recipient ARNs, not just
  the sender — a real, non-obvious finding, not documented anywhere
  else once `infra/ses.tf` stops being the live path). A fresh
  `put-account-details` resubmission with a stronger use-case
  description was rejected outright (`ConflictException`) — no
  API-only path was left. The account's Support Case was entirely
  unreachable via API (Basic support tier,
  `SubscriptionRequiredException` confirmed on both `describe-cases`
  and `describe-severity-levels`) — only the AWS Console could read or
  post to it, and this environment has CLI credentials only, never
  console access. Per this ticket's own instruction ("if AWS doesn't
  respond within a short, explicit window, escalate to Borys directly
  rather than silently waiting"), that window passed and the blocker
  was escalated directly rather than left for a further quiet
  re-check.
- **How it actually closed:** not via AWS ever responding — Borys
  checked the Support Center console directly and confirmed AWS had
  genuinely gone silent (Basic support carries no committed SLA at
  all), then chose to adopt a provider switch rather than wait
  unbounded. S8-05 switched the app's transactional email path from
  SES to Resend (real DNS verification on `mymble.be`, real production
  deploy, full detail in ARCHITECTURE.md's Transactional Email
  section) — this blocker is closed because the underlying problem
  ("real strangers can't receive email from Mymble") is resolved, not
  because AWS's case ever resolved. Case `178778410400368` may still
  be sitting open and unanswered in the Support Center for all this
  environment can tell; that no longer matters to this project.
- **Status:** CLOSED. Kept here rather than trimmed, per this file's
  own convention, because the recipient-ARN IAM quirk and the
  Basic-support-tier dead end are real diagnostic content not fully
  preserved anywhere else in the ledger, and were the actual reason
  Resend was adopted.

### Real received-email confirmation for email verification (S7-09, closed 2026-08-28, S8-05)

- **What was deferred:** an actual verification email, received in a
  real inbox and clicked through for real, by someone other than
  Borys's own already-verified account. Everything up to that point
  was built and proven at the API level since S7-09; SES sandbox mode
  (see the entry above) blocked any real recipient other than
  pre-verified test identities from ever completing the round-trip.
- **How it actually closed:** not via SES at all — once `mymble.be`
  was verified on Resend and deployed to production,
  `liyaberry27@gmail.com`'s existing unverified row
  (`email_verified: false`, from the earlier SES-blocked attempt) was
  deleted so the same address could register fresh. That real
  registration went through Resend for real: direct database query
  confirms `email_verified: true`, `created_at: 2026-08-28 11:40:35` —
  a genuinely new registration, real send, real receipt, real click,
  not a re-check of stale state.
- **Status:** CLOSED. The proof this entry existed to get — a real
  stranger receiving and using a real verification email — now
  exists, via a different provider than originally planned but
  satisfying the exact same standard.

### Old production code + new DB schema risk window — closed same day (S8-02, closed 2026-08-27)

Was OPEN for the gap between running S8-02's real production migration
(`enable_banking_sessions` widened to composite `(user_id,
institution)` key) and deploying code that matched it — old code's
`ON CONFLICT (user_id)` no longer matched any real constraint, so any
real bank connect/reconnect attempt would have hard-failed. Closed by
building/pushing web+worker images from current `master`, updating
both task definitions, and rolling both ECS services to them —
real evidence: `aws ecs describe-services` showed both deployments
reach `rolloutState: COMPLETED` on the new task-definition revisions
(`kbc-analyzer-web:11`, `kbc-analyzer-worker:10`), and a real
unauthenticated request to `https://mymble.be/api/auth/enable-banking/status`
returned the expected `401 {"detail":"Not authenticated..."}` from the
live service, not a stale response.

### Non-root file-permission protection — verified for real on production Fargate (S4-09 Item 1, closed 2026-08-27, S7-10)

Was OPEN since S4-09: Windows Docker Desktop's bind mounts report
`rwxrwxrwx` to every UID regardless of the container's actual user, so
local dev could never demonstrate the failure mode `appuser` is meant to
prevent. Its own closure condition ("closes at Sprint 7, when deployment
moves off Windows Docker Desktop onto a real Linux host") became
checkable for the first time once production ECS Exec was available —
this ticket ran the actual test rather than re-dating around it.

**Real evidence, not narration.** Exec'd into the live, currently-serving
`kbc-analyzer-web` Fargate task (`aws ecs execute-command`, real
production, not a throwaway task) — genuine Linux (Debian 13), no
synthesized Windows permissions involved.

First confirmed the process actually handling live traffic runs
non-root, via `/proc`, not assumed from the Dockerfile:

```
PID:1 OWNER:appuser CMD:python -m uvicorn app.main:app --host ... --port 8...
```

Then created a root-owned, `600`-permission file and attempted every
operation `appuser` might need to defeat the boundary with:

```
+ chown root:root /app/root_owned_test_file
+ chmod 600 /app/root_owned_test_file
-rw-------. 1 root root 20 Aug 27 07:19 /app/root_owned_test_file

+ su appuser -s /bin/sh -c "cat /app/root_owned_test_file"
cat: /app/root_owned_test_file: Permission denied      (exit 1)

+ su appuser -s /bin/sh -c "echo overwritten >> /app/root_owned_test_file"
sh: cannot create /app/root_owned_test_file: Permission denied   (exit 2)

+ su appuser -s /bin/sh -c "rm -f /app/root_owned_test_file"
rm: cannot remove '/app/root_owned_test_file': Permission denied   (exit 1)

FINAL STATE: -rw-------. 1 root root 20 ... /app/root_owned_test_file
cat: secret-root-content        (unchanged — the write attempt above never landed)
```

Read, write, and delete all genuinely rejected — real `Permission
denied` errors and non-zero exit codes, not a synthesized 777. The
file's content was independently re-read afterward and confirmed
unchanged, closing the possibility that the "denied" write silently
partially succeeded. Test file deleted by root immediately after.
**The app itself is simultaneously proof it "runs correctly end-to-end
as non-root"** — this was the live production `kbc-analyzer-web` task,
actually serving real traffic as `appuser` the entire time this test ran.

### Real received-email confirmation for password reset (closed 2026-08-27, S7-09)

Was tracked alongside email verification as one combined "needs a real
received email" item. Closed for real: `POST
/api/auth/request-password-reset` called against production for
Borys's real, existing account (`boris.sydorchuk@gmail.com`) — a real
email arrived, he clicked the real link, set a new password, and
confirmed directly ("Checked - everything works"). Email verification
stays open separately (see above) — that same account is already
verified from S7-09's backfill migration, so it couldn't exercise that
specific flow.

### Email verification — built, real API round-trip proven (closed 2026-08-27, S7-09)

Was OPEN since S6-08: no transactional email infrastructure existed,
so no email address was ever verified. Closed by S7-08 (real SES
sending) + S7-09 (the actual verification flow):
`users.email_verified` (migration `b8e4f2a9c317`), `auth/tokens.py`'s
single-use Redis tokens, `POST /api/auth/register` sends a real email,
`POST /api/auth/verify-email` consumes the token.

**Real evidence, not narration:** a real local registration, a real
token pulled from the real Redis key the send created, a real
`POST /api/auth/verify-email` call, confirmed via a real `GET
/api/auth/me` showing `email_verified: true` — run multiple times.
Backend test suite: 126 passed, including real round-trip tests
extracting the token from the actual email body the fake-SES fixture
recorded (not a token generated separately by the test).

**Not yet closed within this entry:** a real *received* email in a
real inbox, clicked through by a human — tracked separately (see the
OPEN "Real received-email confirmation" entry above), since that's a
categorically different kind of proof and needs Borys, same as every
other credential/email-touching step this sprint.

### Email-based password reset — built, real API round-trip proven (closed 2026-08-27, S7-09)

Was OPEN since S6-08, same root blocker as email verification above.
Closed by S7-08 + S7-09: `POST /api/auth/request-password-reset`
(generic response regardless of whether the email exists, rate-limited),
`POST /api/auth/reset-password` (separate 1h-TTL token, password
strength validated before the token is consumed).

**Real evidence:** a real reset request, a real token pulled from the
real email the fake-SES fixture recorded, a real
`POST /api/auth/reset-password` call setting a new password, then a
real login confirming the NEW password works and the OLD one no longer
does. Also confirmed the generic-response shape genuinely doesn't
depend on whether the email exists (same response, different real
side effect only for the real account).

**Not yet closed within this entry:** same as email verification
above — a real received email, clicked through by a human, tracked
separately.

### S7-07 real second-account KBC login — completed, isolation confirmed (closed 2026-08-27)

Was OPEN: the ticket's acceptance criterion needed a real, live KBC
login through the browser, on a genuinely new account — something
Codee cannot do (never touches real bank credentials).

**Closed for real:** Borys completed the full browser-only flow end to
end on a second, genuinely distinct account — no terminal step at any
point. The categorization stage failed afterward, expected and
unrelated: the fresh account has no Gemini API key configured yet, same
non-issue the original S7-06 sync hit on its own fresh account.

Independently re-verified, not just taken on report — queried
production directly for every `enable_banking_sessions` row and its
owning account:

```
('boryssydorchuk@gmail.com', valid_until=2026-11-23, updated_at=2026-08-26 21:51)
('bathsters@gmail.com',       valid_until=2026-11-23, updated_at=2026-08-26 22:30)
```

Two distinct real accounts, two distinct rows, real ~90-day expiries —
the second account's connection exists and is isolated from the first,
exactly as S7-06/S7-07 were built to guarantee.

### S7-05 test account cleanup — SSM plugin installed, row deleted from production (closed 2026-08-26)

Was OPEN: `s7-05-verify-test@example.com` left in the production
database after the COOKIE_SECURE round-trip test, because `aws ecs
execute-command` (the same cleanup path S7-04 used) needs the Session
Manager plugin, not installed on this machine.

**Closed for real:** installed the plugin (`winget install
Amazon.SessionManagerPlugin`, v1.2.835.0), added it to `PATH`, then
re-ran the migration-runner exec pattern with a `SELECT` before and
after the `DELETE` — not just trusting the delete's own report:

```
BEFORE: [(UUID('7a0cad13-...'), 's7-05-verify-test@example.com')]
DELETED rowcount: 1
AFTER: []
```

Independently re-confirmed a third way, against the live API rather
than the same migration-runner connection that did the delete:

```
$ curl -X POST https://mymble.be/api/auth/login \
    -d '{"email":"s7-05-verify-test@example.com","password":"..."}'
{"detail":"Invalid email or password."}
HTTP 401
```

Migration-runner task stopped afterward (`STOPPED`, no lingering
Fargate cost). RDS Query Editor was checked first as a possibly-faster
path and ruled out with evidence, not assumed: `aws rds
describe-db-instances` confirms this instance's engine is plain
`postgres` (16.13) — Query Editor is an Aurora + Data API feature only,
not available here regardless of console settings.

### Borys's real-account set-password + /login /register real-browser render (S6-04, closed 2026-08-21)

Two items: (1) `POST /api/auth/set-password` against Borys's real
account, (2) `/login`/`/register` rendering in a real browser — both
required Borys's own real, already-live session, not something available
to this session directly.

**What's directly confirmed:** the real database now shows Borys's
account (`boris.sydorchuk@gmail.com`) with `password_hash IS NOT NULL`,
where before this ticket it held the S6-02 bootstrap migration's locked,
unusable placeholder — proof `set-password` ran successfully against his
real row, not just the throwaway test account this ticket's own
structural verification used. Also incidentally confirms `/login` was
opened in a real browser at least once (Google sign-in, needed to get the
session `set-password` used), closing item (2).

**Not separately confirmed:** a report from Borys that logging in via
`/login`'s email/password form specifically (as opposed to Google) with
the new password worked — he moved on to the next ticket without stating
that explicitly. Not re-opening this entry on that basis: the database
state is direct, verifiable evidence the password write succeeded, and
`login()`'s own logic (verified structurally against the exact same code
path via a throwaway account in S6-04's own delivery) has no dependency
on *how* the account was created that would make his case behave
differently.

Also cleaned up: `reviewer-check-1787259224@example.com`, a throwaway
account the Reviewer created during S6-04's independent verification,
deleted from the dev database at Borys's request (2026-08-21) — unrelated
to this entry's closure but done in the same session.

### Real live Google OAuth flow — confirmed (S6-03, closed 2026-08-20)

S6-03's own acceptance criteria required "a real live Google OAuth flow
works end-to-end." Structural verification (`tests/test_google_oauth.py`,
6 tests against real Postgres/Redis with only Google's two HTTP calls
faked) landed with the ticket; the real click-through was blocked first
on no credentials existing at all, then on a `redirect_uri_mismatch`
(the callback URL wasn't yet registered as an Authorized redirect URI on
the Google Cloud OAuth client).

Both closed same-day: Borys added real `GOOGLE_CLIENT_ID`/
`GOOGLE_CLIENT_SECRET` to `.env` (gitignored, never committed) and
registered the redirect URI in Google Cloud Console. **Borys confirmed a
real sign-in worked** — no personal Google account details recorded here
per this file's shape-only evidence convention. This also closes the
`/login` frontend page's browser-rendering verification, which had the
same gap (no Chrome extension connection available during the build
session) and the same closure condition (a real page load, which a real
sign-in necessarily requires).

### `agents/registry.py`'s `_provider_cache` — user-scoped (S4-09/S5-08 finding, closed S6-02, 2026-08-20)

Flagged S4-09, tracked as OPEN architectural debt through the S5-08
Sprint 5 close (previously this file's own "SPRINT 5 AUDIT SCOPE"
section, now removed — its one entry is this one, closed, not left as an
empty stub). `_provider_cache` was keyed on provider name alone; once
Sprint 6 gave every user their own API key, the first user to call a
given provider would have their cached client instance (and the API key
it holds) served to every other user's requests.

**Closed by S6-02** (commit `e29224c`, "feat: S6-02 schema migration —
user_id everywhere"): `_provider_cache` is now keyed on `(user_id,
provider_name)`; `get_provider(db, user_id: UUID | None = None)` defaults
to `None` so the three existing call sites (`analysis_service.py` ×2,
`chat_service.py` ×1) needed no changes — S6-06 passing a real `user_id`
there is a one-line change per call site, the same pattern
`sync_lock.py`'s key derivation already established. Verified structurally
(the cache key shape, not a live two-user test — no second real user
exists yet to actually observe cross-user isolation with; that live
observation becomes possible once S6-06 threads a real `user_id` through
and S6-07's Security Auditor pass can attempt it adversarially).

### Claude provider — full live verification (S2-04/S2-05/S2-06/S4-06, closed 2026-08-18)

*(Pre-existing exception to the Conventions section's shape-only evidence
rule, added after this entry was written — contains real transaction
amounts, a real merchant name, and real budget figures. Not retroactively
scrubbed.)*

A real `ANTHROPIC_API_KEY` became available (saved via `PATCH /api/settings`,
provider switched to `claude`). First live attempt against
`POST /api/analysis/categorize` (5 transactions manually cleared back to
`category IS NULL`, values recorded first, for a real categorization call —
everything else was already categorized from prior sessions) failed
immediately with `"No API key configured for claude"` despite the key
showing as saved — **a real bug, not a missing-key situation**:
`settings_service.get_decrypted_api_key(db, provider)` looked up
`f"{provider}_api_key"`, i.e. `"claude_api_key"` for the Claude provider,
but the actual stored field has always been named `"anthropic_api_key"`
(named after the vendor, not the model family — Gemini's provider name and
field prefix happen to match, which is why this never surfaced there).
This means **every previously-closed Claude ledger entry back to S2-04 was
blocked on two things, not one** — no key ever existed to expose the second
blocker until now. Flagged to Borys, who chose the explicit
`API_KEY_FIELD_BY_PROVIDER` mapping fix (`settings_service.py`) over
renaming the field — zero blast radius, no frontend/DB changes.

With the fix live-reloaded (`docker compose logs backend` confirmed a
clean reload, no traceback), re-ran everything:

- **Categorization** (`POST /api/analysis/categorize`, same 5 transactions):
  `{"categorized":5,"skipped_already_categorized":40,"failed":0,"provider":"claude","error_message":null}`.
  4 of 5 matched the original Gemini-assigned categories exactly (Groceries,
  Traveling/Transport ×2, Restaurants and Cafes); the fifth (a €233.93
  KU LEUVEN payment) got `Other/Shopping` from Claude versus the original
  `Other/Rest` from Gemini — a real, defensible difference in model
  judgment, not an error. All 5 transactions restored to their original
  recorded values afterward.
- **Insights** (`POST /api/analysis/insights`, same date range): 5 real
  insights generated, `"provider":"claude"`. Style is genuinely
  distinguishable from Gemini's (see the S4-06 CLOSED entry below for a
  Gemini sample from the same kind of data): Claude's insights lean
  quantitative and prescriptive — precise percentages and ratios ("83% of
  daily spend," "3.2× the first," a concrete "20–30% reduction" estimate
  with a specific suggested action) — where Gemini's read more narrative/
  descriptive. Not restored (insights are documented as delete-and-replace,
  ephemeral by design — see ARCHITECTURE.md Invariants; a future sync with
  Gemini active regenerates them normally).
- **Chat streaming** (`POST /api/chat`, real SSE via `curl -N`): two-turn
  conversation. Turn 1 ("what was my biggest expense, groceries vs
  transport") returned real incremental token frames (not one flush),
  correct grounded numbers matching `GET /api/statistics`/`GET /api/budgets`
  exactly (€800,00 biggest expense; Groceries €772,92/11.4%; Traveling
  €583,11/8.6%; budget overages 511.9% and 623.0%), and real
  `usage: {"input": 1046, "output": 229}` from `stream_complete()`'s
  `get_final_message()` path — the exact code path S4-06's entry could only
  verify structurally before. Turn 2, with turn 1 in `history`, correctly
  built on it (recommended cutting groceries first, referencing the same
  budget figures and specific real merchants — Carrefour, Delhaize, Too
  Good To Go, NMBS, De Lijn — from the actual transaction data), confirming
  multi-turn history works identically to Gemini's already-verified path.

Provider switched back to `gemini` afterward, matching the ticket's
explicit instruction and this project's normal running state.

This closes **S2-04** (provider structural verification — now live, and the
`get_decrypted_api_key` bug it never caught is fixed), **S2-05**
(categorization), **S2-06** (insights), and **S4-06**'s Claude half (chat
streaming) — all four were tracked as one entry
("Claude provider — chat streaming, no API key (S4-06)") since the
underlying blocker (no key) was identical; that entry is removed from OPEN
above as of this closure.

**Re-confirmed 2026-08-19 (S5-08 sprint close):** still accurate and still
closed. Live-verified again during S5-08's regression sweep — switched
the provider to Claude and back to Gemini via the real Settings UI (not
just the API), both round-trips clean, `GET /api/settings` correctly
reflecting each switch, no console errors. Nothing about this has
regressed since S5-06.

### Categories FK backfill validation & live constraint test (S5-02, closed 2026-08-18)

Docker Desktop restarted and became responsive. `docker compose up -d`
brought the stack up; the backend container's own startup (`alembic
upgrade head`) applied migration `d3f8a5c6b9e2` automatically — logs show
`Running upgrade c4a91d6e0f3b -> d3f8a5c6b9e2` with no `RuntimeError`,
confirming the pre-flight backfill check found zero orphaned
`transactions.category` values against the real 350-row dataset (8
distinct categories in use, two of them user-created custom categories —
`Pet Care`, `Investments` — not in the categorization agent's hardcoded
list, both present in `categories` already so neither was orphaned).

`\d transactions` confirmed the live constraint:
`fk_transactions_category_categories_name FOREIGN KEY (category)
REFERENCES categories(name) ON UPDATE CASCADE ON DELETE SET NULL`.

Rename-cascade test: `UPDATE categories SET name = 'Test Rename' WHERE
name = 'Other'` — all 62 transactions previously on `'Other'` read back
as `'Test Rename'` with zero orphans, zero manual reassignment needed;
renamed back, category counts matched the pre-test snapshot exactly.

Unknown-category handling: a raw `UPDATE transactions SET category =
'Totally Not A Category' ...` was rejected live by the FK (`violates
foreign key constraint`, transaction rolled back cleanly, no data
changed) — confirming the failure mode the ticket flagged as Option A's
cost is real. Rather than waiting for an LLM to spontaneously hallucinate
a category (not reliably reproducible on demand), the exact set-membership
filter now in `analysis_service.categorize_transactions` was run
standalone inside the backend container against the real
`crud.list_categories(db)` result: an unknown name was correctly excluded
from the write set while a valid one passed through — proving the guard
that keeps the FK rejection above from ever reaching the live
categorization write path.

Migration downgrade path, `models.py`'s `ForeignKey` declaration, and
`analysis_service.py`'s filter were already reviewed by reading at commit
time (2026-08-17) — this closure is the live-execution half.

**S5-04 (2026-08-18):** both layers verified here by hand are now permanent,
automated regression tests — `tests/test_referential_integrity.py::test_fk_rejects_an_unknown_category_at_the_db_level`
and `::test_categorization_pre_write_filter_excludes_unknown_categories_before_any_write`
— so this can never silently regress without the suite catching it.

Both consented tests executed exactly per the procedure Borys approved at
S4-07 confirmation:

1. **No-API-key toast:** backed up the real (encrypted) `gemini_api_key`
   value directly at the database level (`SELECT`/copy into a temp table,
   never decrypted, never seen in plaintext) rather than relying on
   Settings' masked display. Blanked it via `PATCH /api/settings`, sent a
   chat message: a toast appeared reading *"No API key configured for
   gemini. Add one in Settings before running analysis."*, and no empty
   assistant bubble was left in the thread. Restored the exact encrypted
   value via direct `UPDATE`, dropped the temp table, sent another message:
   real Gemini reply came back normally.
2. **Mid-stream interrupted marker:** sent a long chat message, ran
   `docker compose kill backend` mid-stream. Partial response text stayed
   in the bubble, followed by *"Response interrupted — please try again"*
   in red, input re-enabled (not stuck). Brought `backend` back up
   (`docker compose up -d backend`), sent a follow-up message: real reply
   came back, prior history intact.

Both matched `onError`'s two branches (`hadPartialResponse: false` /
`true`) exactly as code-reviewed at S4-07. No regressions.

### `POST /api/chat` — Gemini live verification (S4-06, closed 2026-08-16)

*(Pre-existing exception to the Conventions section's shape-only evidence
rule, added after this entry was written — contains real spending totals
and budget figures. Not retroactively scrubbed.)*

Docker Desktop came up; ran a real 3-exchange conversation against the real
331-transaction dataset with the actually-configured Gemini key. Confirmed:
SSE frames arrive incrementally via `curl -N` (not one flush); a transient
Gemini `503 UNAVAILABLE` mid-stream was caught and surfaced as a clean SSE
error frame, never a raw traceback; a retried request succeeded; multi-turn
history was respected across 3 turns; every number the assistant computed
from the summary/category/budget context (total spent €7.180,30, total
received €6.840,72, Groceries €647,18/9.0%, Groceries budget €47,40 of
€40,00 exceeded, Traveling €5,20 of €6,00 warning) matched
`GET /api/statistics` and `GET /api/budgets` exactly. No financial data
appeared in `docker compose logs backend` at INFO level.

One real, non-blocking limitation surfaced by this run (see
ARCHITECTURE.md's chat-flow note, not tracked here as debt — it's a
documented behavior, not an unverified one): "last 20 transactions" is a
small slice of a much larger summary window when more than 20 transactions
fall in it (293 did, here). Asked for the single biggest expense across the
full 90 days, the assistant correctly declined to guess beyond its visible
20 rows rather than inventing a number — exactly per its system-prompt
rule — but that means a true 90-day-max query can't be answered from
today's context shape.

**Update 2026-08-17 (S4-06 review bounce):** Reviewer found this was a
one-line omission, not a design gap — `compute_statistics()` already
returns `summary.biggest_expense`; `chat_service._summary_text()` just
wasn't surfacing it. Fixed in-ticket; re-verified live against the same
dataset (exact match: €800.00, [REDACTED-NAME], 2026-07-27). See
`docs/tickets/S4-06-ai-chat-backend.md`'s amendment history for the full
sequence.

**S5-04 (2026-08-18):** this omission is now a permanent regression test —
`tests/test_chat_context.py::test_chat_context_summary_mentions_biggest_expense`.
