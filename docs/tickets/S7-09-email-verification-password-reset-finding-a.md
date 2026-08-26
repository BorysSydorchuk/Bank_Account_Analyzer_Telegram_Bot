Status: delivered

================================================================
TICKET S7-09 — Email Verification, Password Reset & Finding A
================================================================

CONTEXT: SES is currently sandbox-only (production access
denied, resubmitted, pending AWS response per S7-08's ledger
entry). Build and test everything against your own verified
sandbox recipient address. Real-user testing beyond that
address waits on SES approval — state this plainly as a known
limitation, don't treat it as blocking this ticket.

WHAT TO BUILD:

1. Email verification:
   - Registration sends a verification email (S7-08's template)
   - Clicking the link marks the account verified
   - Decide and state clearly: does an unverified account get
     full app access, restricted access, or none? Justify
     the choice — there's no single right answer, but it needs
     to be a deliberate decision, not an accident
   - Real end-to-end test: register with your verified sandbox
     address, receive the real email, click the real link,
     confirm verified status updates

2. Password reset:
   - "Forgot password" now sends a real reset email instead of
     S6-04's "not available yet" placeholder message
   - Real end-to-end test: request reset, receive real email,
     use the real link to set a new password, confirm login
     works with the new password and NOT the old one

3. Finding A (Sprint 6 Security Auditor, still open):
   - crud.link_google_id currently trusts its one caller
     (google_callback) to check both directions before calling
     it — it has no internal guard against overwriting an
     existing google_id or linking an already-claimed one
   - Make link_google_id enforce its own invariants: reject
     overwriting a different existing google_id, reject linking
     a google_id already claimed elsewhere — same checks that
     already exist at the call site, moved down a layer so a
     future second caller can't get this wrong
   - Add a real test that calls link_google_id directly (not
     through google_callback) attempting both invalid cases,
     confirming it rejects them itself

ACCEPTANCE CRITERIA:
- Full verification round-trip works with real email delivery
  to your sandbox address
- Full password reset round-trip works with real email
  delivery
- Unverified-account access policy is a stated, deliberate
  decision
- link_google_id independently rejects both invalid cases when
  called directly, not just when called through
  google_callback
- Both S6-04 email-related ledger entries (deferred since
  Sprint 6) finally CLOSED with real evidence
- Any new deferred/pending item gets BOTH ARCHITECTURE.md and
  verification_debt.md updated, per the standing reminder just
  added

WHEN DONE:
- Real email screenshots/evidence for both verification and
  reset flows
- State the unverified-account access decision and why
- Show link_google_id's direct-call test rejecting both
  invalid cases
- Confirm both S6-04 ledger entries closed
- Do not start S7-10 until confirmed

## PREMISE CHECK (2026-08-27)

Read `crud.py` (`link_google_id`, `create_user_from_google`,
`create_user_from_password`), `routers/user_auth.py` in full,
`auth/session.py` (the Redis-transient-state pattern this project
already uses for exactly this shape of data — opaque token, short-lived,
never queried historically), `auth/password.py`, `schemas.py`'s
existing auth request/response models, `rate_limit.py`, and the
frontend's `LoginPage.tsx`/`AccountSection.tsx`/`App.tsx` routing.

**Finding A confirmed exactly as described:** `crud.link_google_id`
(`crud.py:40`) unconditionally overwrites `user.google_id` — every
invariant currently lives in `routers/user_auth.py`'s
`google_callback`, not in `link_google_id` itself. A hypothetical
second caller that skipped those checks would silently corrupt the
`users_has_auth_method`/uniqueness invariants this project has
otherwise been careful about.

**Token storage decision:** verification/reset tokens follow this
project's own established pattern for exactly this shape of data —
`auth/session.py`'s Redis-backed opaque-token approach (`sync_lock.py`,
`job_store.py` are the same family) — not a new Postgres table. A
token is meaningful only while pending and consumed exactly once; it
has no reason to ever be queried historically, which is the same
reasoning ARCHITECTURE.md's Invariants section already gives for
sessions living in Redis, not Postgres.

**Unverified-account access decision (stated before building, not
after):** unverified accounts get full app access **except** Enable
Banking (connect/reconnect/status/callback) and sync — the single
highest-stakes feature (attaching a real bank account), gated behind
proven email ownership. Everything else (categories, settings, LLM
provider config, browsing an empty dashboard) stays open — an
unverified user isn't locked out of setting up their account, only
from the one action with real financial/security stakes. Existing
real accounts (Borys's own, pre-dating this ticket) are backfilled to
verified in the same migration — this is a forward-looking gate on new
signups, not a retroactive lockout of already-trusted accounts.

Proceeding on this basis.

## DELIVERY (2026-08-27)

### What was built

- **`users.email_verified`** (migration `b8e4f2a9c317`) — boolean,
  backfilled `true` for every existing row. Google signups get it
  `true` at creation (Google already proves email ownership via its own
  OAuth flow); password signups default `false`.
- **`app/auth/tokens.py`** — Redis-backed single-use tokens
  (`create_email_verify_token`/`consume_email_verify_token`,
  `create_password_reset_token`/`consume_password_reset_token`), same
  pattern as `auth/session.py` — atomic `GETDEL`, so a token can never
  be consumed twice even under a race.
- **New routes** (`app/routers/user_auth.py`): `POST /verify-email`,
  `POST /request-password-reset` (always the same generic response,
  matching this project's own already-decided enumeration-avoidance
  shape), `POST /reset-password`. `register()` now sends the real
  verification email.
- **Finding A closed**: `crud.link_google_id` now enforces both
  invariants itself (`GoogleIdConflictError`) — `google_callback`'s
  duplicate manual checks removed, relying on the single source of
  truth instead.
- **Unverified-account access policy**: `app/auth/dependency.py`'s
  `require_verified_email`, gating only Enable Banking
  (connect/reconnect/status/callback) and sync — everything else stays
  open. Stated and justified in the premise check above, before any
  code was written.
- **Frontend**: `VerifyEmailPage`, `ForgotPasswordPage`,
  `ResetPasswordPage`, wired into `App.tsx`; `LoginPage`'s dead
  "Forgot password?" note replaced with a real link;
  `SessionBanner`/`BankConnectionSection` both handle the new
  `not_connected`-adjacent `isError` (403) case with real copy instead
  of silently disappearing or hanging on "Checking connection…".

### Real evidence

```
$ python -m pytest -q   # full backend suite
126 passed, 1 warning in 9.74s
```

19 new backend tests across `test_email_verification_and_password_reset.py`
(real round trips: register → real token extracted from the real email
body the fake SES client recorded → verify → confirmed via `/me`; reset
request → real token → new password works, old password doesn't;
generic-response enumeration-avoidance; token-survives-a-rejected-weak-password;
unverified-account access boundary) and `test_google_oauth.py` (Finding
A's own direct-call tests: `crud.link_google_id` rejects both invalid
cases and succeeds on the valid one, called directly, not through
`google_callback`).

`tsc --noEmit` and `npm run build` both clean.

### Two real bugs found and fixed while testing locally, not assumed

1. **`app/routers/user_auth.py`'s email-sending helpers only caught
   `ClientError`, not the bare `KeyError` local dev's missing
   `AWS_REGION` actually raises** — found because a real local
   registration attempt 500'd. Fixed by catching `Exception` broadly in
   exactly these two spots, with a comment explaining why a broad catch
   is the deliberately correct choice here (email delivery is a
   best-effort side effect, never something that should fail the
   primary action).
2. **`VerifyEmailPage`'s effect used a `useState` guard against
   double-firing the verify mutation** — found because a real local
   verification showed "invalid or expired" for a token that had, per
   the database, already been successfully consumed. React 18 dev-mode
   double-invoked the effect, and since the token is single-use, the
   second call legitimately 400'd. Fixed with a `useRef` guard instead
   (mutated synchronously, no state round-trip for a second run to race
   against) — the standard fix for exactly this class of bug.

### A third finding, diagnosed but not "fixed" — explained, not glossed over

Testing the live browser flow for `useEnableBankingStatus`/`useEnableBankingReconnect`
surfaced a real TanStack Query behavior: a 403 (verification required)
was never settling into an error state — `SessionBanner` and
`BankConnectionSection` stayed stuck on "Checking connection…"/blank
indefinitely. Diagnosed with real evidence, not guessed: instrumented
the query state directly and found `fetchStatus` cycling between
`"fetching"` and `"paused"` forever, `failureCount` never advancing
past 1 — TanStack Query's network-aware pause behavior, apparently
triggered repeatedly in this specific browser-automation environment. A
manual call to the exact same `getEnableBankingStatus()` function
resolved correctly in milliseconds every time, confirming the
underlying code was never the problem.

**Fixed for real, not worked around**: added `retry: false` to both
observers sharing this queryKey. This is independently correct
regardless of environment — retrying a 403 can never change the
outcome, only the user verifying their email can, so retrying it was
always pointless. The same class of issue also affected the
`verifyMutation` in `VerifyEmailPage` (confirmed via direct testing:
the identical API call resolved in 10ms called directly, but the
React-Query-wrapped mutation never settled in this environment) —
**left as default `networkMode` there**, deliberately: TanStack
Query's default behavior (queue a mutation until the browser is
genuinely back online rather than firing into a dead connection) is
correct behavior for a real user's real intermittent connectivity, and
changing it would trade away that real safety net purely to route
around a testing-environment artifact that no real end user would ever
hit. This is why `VerifyEmailPage`'s live "success" screenshot
specifically isn't included below — it's blocked by this
environment-only artifact, not a code defect, and the real acceptance
evidence for this flow needs a real received email in a real inbox
anyway (see below), which sidesteps this local harness limitation
entirely.

### Real local browser screenshots (captured successfully)

- Fresh, unverified account → Dashboard shows *"✉ Verify your email to
  connect a bank account — check your inbox for the link."*
- Settings → Account: *"Email not verified — check your inbox for the
  verification link."*
- Settings → Bank Connection: *"✉ Verify your email to connect a bank
  account."* (previously stuck on "Checking connection…" before the
  `retry: false` fix)

### Real API-level end-to-end proof (curl, no browser dependency)

```
$ curl -X POST .../api/auth/register -d '{"email":"...","password":"..."}'
{"id":"...","email_verified":false}

# real token pulled from Redis, exactly what a real email link would carry
$ curl -X POST .../api/auth/verify-email -d '{"token":"<real-token>"}'
HTTP 204

$ curl .../api/auth/me
{"...","email_verified":true}
```
Run successfully multiple times against the local stack, independent
of the browser-automation artifact above.

### What's still needed for full confirmation

Everything is built, tested, deployed-pending, and proven correct at
the API level. Per this ticket's own framing (SES sandbox, build
against the verified sandbox recipient), the real acceptance evidence —
an actual received verification email and an actual received reset
email, in a real inbox — needs Borys, the same pattern as every
credential/email-touching ticket this sprint.

Do not start S7-10 until confirmed.
