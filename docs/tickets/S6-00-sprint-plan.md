Status: plan
Source: issued directly in Claude Code session, 2026-08-20

---

================================================================
SPRINT 6 — "MULTI-USER CORE"
KBC Personal Finance Analyzer
================================================================

SPRINT GOAL:
The application is genuinely multi-user, correctly and
verifiably so. Google OAuth and email/password sign-in both
work. Every table and endpoint is scoped to the authenticated
user. Every ownership-shaped endpoint (jobs, transaction
edits) actually checks ownership, not just ID lookup. A
Security Auditor pass has reviewed the whole auth flow
adversarially before this is called done. Still runs locally
— no public deployment yet, that's Sprint 7.

Sprint 5 is fully closed. Start from that state. Read
docs/multi_user_migration_plan.md (S5-01, re-verified S5-08)
before touching anything — it is this sprint's primary input
and its "Ordering" section is the dependency sequence below.

DECISIONS ALREADY MADE (do not re-litigate):
- Sessions: server-side in Redis, httpOnly cookie holding
  the session id. Not JWT.
- Sign-in: Google OAuth AND email/password, both required
  this sprint.
- No transactional email infrastructure exists yet —
  email verification and email-based password reset are
  explicitly OUT of scope this sprint (flag, don't build).

PRE-SPRINT ACTION — STEP 0 FROM THE MIGRATION PLAN:
Before S6-02 touches the external_id constraint, resolve the
open question from S5-01: check Enable Banking's
documentation for the actual uniqueness scope of
entry_reference (per-bank, per-account, or globally unique
across their whole customer base). If undocumented, treat it
as per-bank and design the constraint as
UNIQUE (user_id, external_id) accordingly — this is the
conservative, safe assumption either way, but confirm and
record which case applies before writing the migration.

HOW TO WORK THROUGH THESE TICKETS:
Build in order S6-01 through S6-08. Every ticket goes through
Reviewer review before confirmation, same as every prior
sprint. Do not start the next ticket until Borys confirms the
current one. Follow the S5-00 convention: commit this sprint
plan to docs/tickets/S6-00-sprint-plan.md (Status: plan)
before S6-01 begins.

================================================================
TICKET S6-01 — Users Table & Auth Primitives
================================================================

WHAT TO BUILD:
The foundational users table and the password/session
primitives everything else in this sprint builds on. No
login flow yet — that's S6-03/S6-04.

MIGRATION:
  CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT,              -- NULL for OAuth-only users
    google_id     TEXT UNIQUE,       -- NULL for password-only users
    display_name  TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT users_has_auth_method CHECK (
      password_hash IS NOT NULL OR google_id IS NOT NULL
    )
  );

PASSWORD HASHING:
  Use passlib with bcrypt. Justify in KEY DECISIONS if you'd
  rather use argon2id instead — either is acceptable, state
  why you picked one.

SESSION PRIMITIVES: backend/app/auth/session.py
  create_session(user_id) -> session_id
    Writes session:{session_id} -> {"user_id": ..., 
    "created_at": ...} to Redis, TTL 30 days, sliding
    (refresh TTL on each authenticated request within some
    reasonable window — state your refresh threshold and why).
  get_session(session_id) -> user_id | None
  destroy_session(session_id) -> None (logout)

AUTH DEPENDENCY: backend/app/auth/dependency.py
  get_current_user(request) -> User
    Reads the session cookie, looks up Redis, loads the user
    row, raises 401 if missing/expired/invalid. This becomes
    the dependency every protected route uses starting S6-06 —
    not wired into any route yet in this ticket.

COOKIE:
  httpOnly, Secure (even in local dev over https via mkcert —
  confirm this doesn't break local http:// dev workflows;
  flag if it does and propose the dev-mode handling),
  SameSite=Lax, name and exact attributes documented in
  ARCHITECTURE.md.

ACCEPTANCE CRITERIA:
- users table exists with the CHECK constraint enforced
  (test: inserting a row with both password_hash and
  google_id NULL fails)
- create_session/get_session/destroy_session round-trip
  correctly against real Redis
- get_current_user correctly rejects a missing, expired, and
  tampered session id (test all three)
- No route wired to auth yet — this is infrastructure only
- ARCHITECTURE.md gains a new Auth section documenting the
  session model and cookie attributes

WHEN DONE:
- Show the round-trip test for all three primitives
- Show the CHECK constraint rejecting an invalid row
- Explain: why sliding TTL rather than a fixed expiry, and
  what's the refresh threshold?
- Do not start S6-02 until confirmed

================================================================
TICKET S6-02 — Schema Migration: user_id Everywhere
================================================================

PRIORITY: This is the ticket the whole sprint's data
integrity rests on. Take the time to get the backfill right —
this is real data, same category of care as S4-01's dedup
cleanup.

BEFORE WRITING THE MIGRATION:
Ask Borys directly for the email address he wants as his
real login. Seed exactly one real user row with that email
in this migration (password_hash set via a value Borys
provides separately and securely — do not have Borys paste a
plaintext password into any chat; either have him set it via
a follow-up flow in S6-04, or generate a one-time reset token
he uses on first login). Do not invent a placeholder email —
this becomes the actual account Borys logs into starting this
sprint.

WHAT TO BUILD:

  Step 1 — Add nullable user_id to every table:
  transactions, categories, settings, budgets, insights.
  (job_store's Redis keys and the sync_lock/rate_limit
  singletons are handled separately — see below, not a SQL
  migration.)

  Step 2 — Backfill:
  Every existing row in every table gets user_id set to the
  one real user seeded above. Verify counts before and after
  match exactly (same technique as S4-01's dedup — log what
  you're about to do, then do it, then verify).

  Step 3 — Tighten to NOT NULL once backfilled.

  Step 4 — Fix the S5-08-discovered conflict:
  categories' primary key becomes (user_id, name). This means
  transactions.category can no longer FK to categories.name
  alone — it must reference (user_id, name), and the FK
  column set on transactions must include user_id. Rebuild
  the FK from S5-02 accordingly. Verify the rename-cascade
  behavior (ON UPDATE CASCADE) still works with the composite
  key — this was tested in S5-02 against the old single-column
  key; retest it against the new composite one.

  Step 5 — settings table:
  This one isn't a bolt-on, per S5-01's finding — its PK is
  the key itself. Redesign as
  (user_id, key) composite PK, or a per-user JSONB blob — your
  call, justify it. Whichever you choose, the encrypted
  API-key storage (Fernet) must continue working exactly as
  before, just scoped per user now.

  Step 6 — external_id constraint:
  Apply the decision from this sprint's Step 0 pre-work.
  Change UNIQUE(external_id) to UNIQUE(user_id, external_id)
  (or leave global if Step 0's vendor check concluded
  external_id is genuinely globally unique — state which).
  Update the sync upsert's ON CONFLICT clause to match.

  Step 7 — Singletons (S4-09/S5-05 findings):
  agents/registry.py's _provider_cache becomes keyed by
  (user_id, provider_name), not just provider_name.
  sync_lock.py's lock key becomes user-scoped (the ticket
  that built it already wrote the key derivation to make
  this a one-line change — confirm that holds).
  rate_limit.py: confirm whether it should move from IP-keyed
  to user-keyed now that real user identity exists — your
  call, justify it (IP-keyed still has value pre-login, e.g.
  the login endpoints themselves).

ACCEPTANCE CRITERIA:
- All 5 tables have NOT NULL user_id after backfill
- Real Borys account seeded with his real email, real data
  correctly attributed to it (spot-check: his 331+
  transactions all show the right user_id)
- categories composite PK + transactions FK verified live
  (repeat S5-02's rename-cascade test against the new key
  shape)
- settings redesign preserves working encrypted API keys
- external_id constraint matches the Step 0 decision
- _provider_cache, sync_lock, rate_limit all user-aware
  where appropriate
- Full test suite still passes (coordinate with Tester —
  this migration will break existing tests that assume
  single-user data; flag what needs updating rather than
  silently changing test expectations yourself)

WHEN DONE:
- Show before/after row counts for every table
- Show the composite-key rename-cascade test passing
- Show a real API key still decrypting correctly post-
  migration
- State the external_id decision and why
- Do not start S6-03 until confirmed

================================================================
TICKET S6-03 — Google OAuth Sign-In
================================================================

WHAT TO BUILD:
Backend OAuth flow + frontend login page, Google side only
(email/password is S6-04).

BACKEND:
  GET /api/auth/google/login
    Redirects to Google's OAuth consent screen.
  GET /api/auth/google/callback
    Exchanges the code, fetches the Google profile, finds or
    creates a user by google_id (if a user with that email
    already exists via password sign-up, link the accounts —
    state how you detect and handle this case), creates a
    session, sets the cookie, redirects to the dashboard.
  POST /api/auth/logout
    Destroys the session, clears the cookie.

FRONTEND:
  /login route. Not gated behind auth (obviously). "Sign in
  with Google" button. Redirect-to-login for any unauthenticated
  request to a protected route (this activates fully once
  S6-06 wires protection onto real routes — for now, just
  build the page and the button).

ACCEPTANCE CRITERIA:
- Real live Google OAuth flow works end-to-end (you'll need
  real Google OAuth credentials — flag this to Borys if you
  don't have them, don't fake it)
- A new Google sign-in creates a real user row
- An existing password-registered email signing in via Google
  links to the same account, doesn't create a duplicate
- Session cookie set correctly, matches S6-01's spec
- Logout destroys the session (verify: session lookup fails
  after logout)

WHEN DONE:
- Show a real Google sign-in creating a session (redacted
  screenshots ok given this sprint's history — no real
  personal Google data in commit messages or ticket files)
- Show the account-linking case working
- Show logout invalidating the session
- Do not start S6-04 until confirmed
================================================================
TICKET S6-04 — Email/Password Sign-In
================================================================

WHAT TO BUILD:
The second sign-in method. No email verification, no
email-based password reset (out of scope this sprint, no
email infra exists — flag this limitation clearly in the
frontend copy so users aren't confused, e.g. "forgot
password" leads to a clear "not available yet, contact
support" state rather than a broken link).

BACKEND:
  POST /api/auth/register
    Body: {email, password}. Validates password strength
    (state your minimum bar and why — e.g. length 8+, no
    other requirements, matching common modern guidance over
    complexity-rule theater). Hashes, creates user, creates
    session, sets cookie.
  POST /api/auth/login
    Body: {email, password}. Verifies hash, creates session,
    sets cookie. Generic error message on failure ("invalid
    email or password") — never reveal whether the email
    exists, that's a user-enumeration leak.

BORYS'S ACCOUNT:
  Handle the real seeded account from S6-02 here: either a
  one-time "set your password" flow using a token generated
  at migration time, or Borys simply registers fresh with
  the same email if the migration left password_hash NULL
  pending this step — your call, state which and why. Either
  way, confirm Borys can actually log into his real account
  with real data by the end of this ticket.

FRONTEND:
  /login gets an email/password form alongside the Google
  button. /register route for new sign-ups.

RATE LIMITING:
  Apply rate limiting to /login and /register specifically —
  these are the two endpoints most exposed to brute-force/
  enumeration attempts, and S5-07's existing rate_limit.py
  should extend here.

ACCEPTANCE CRITERIA:
- Register + login round-trip works with a real test account
- Generic error message on wrong password AND on
  nonexistent email (identical response, timing-comparable —
  state whether you addressed timing-based enumeration or
  are flagging it as a known gap)
- Borys can log into his real seeded account with real data
- Rate limiting active on both endpoints

WHEN DONE:
- Show register + login working
- Show the identical-error-message behavior for both failure
  modes
- Confirm Borys's real account login works
- Explain: what's your minimum password bar and why?
- Do not start S6-05 until confirmed

================================================================
TICKET S6-05 — Auth Middleware Rollout (Partial)
================================================================

WHAT TO BUILD:
Wire get_current_user (built in S6-01) onto the frontend's
routing and a first batch of low-risk backend routes, to
prove the whole login→protected-route→logout loop works
before S6-06's full sweep across every endpoint.

BACKEND:
  Protect GET /api/health with nothing (stays public, it's a
  health check). Protect GET /api/categories and GET
  /api/budgets with get_current_user as a first real test —
  choose these two because they're simple reads with
  low blast radius if something's subtly wrong.

FRONTEND:
  Route guard: any route under the main app layout redirects
  to /login if no valid session (a lightweight
  GET /api/auth/me check on load, or reading session state
  from the two now-protected endpoints' 401 responses).
  Add a user menu (avatar/email, logout button) to the
  sidebar.

ACCEPTANCE CRITERIA:
- Logged-out access to any main app route redirects to /login
- The two protected endpoints correctly 401 without a session
  and correctly return data with one
- Logout correctly kicks the user back to /login
- Logging in as Borys shows Borys's real data on those two
  endpoints specifically (nobody else's — there's only one
  real user yet, but confirm the scoping logic, not just
  that data appears)

WHEN DONE:
- Show the redirect-to-login behavior
- Show both protected endpoints correctly gated
- Confirm data scoping is real (trace the query, not just
  eyeball the response)
- Do not start S6-06 until confirmed

================================================================
TICKET S6-06 — Full Query Scoping & Ownership Checks
================================================================

PRIORITY: The core security work of the sprint. This is
where S5-01's IDOR findings get fixed for real.

WHAT TO BUILD:
Every remaining endpoint gets get_current_user, and every
query gets scoped to that user. Two categories, handled
differently:

  Category A — list/create endpoints (add user_id filter):
  transactions, insights, statistics, compare, chat context
  assembly, sync, settings, all categories/budgets endpoints
  not already covered by S6-05.

  Category B — by-ID lookup endpoints (add real ownership
  checks, not just filtering — the IDOR-shaped gap S5-01
  named explicitly):
  GET /api/jobs/{job_id} — the job's user_id must match
  the requester; if not, 404 (not 403 — don't confirm the
  resource exists to an unauthorized requester).
  PATCH /api/transactions/{id} — same pattern.
  Any other by-ID route discovered during this sweep.

  job_store.py specifically: job keys in Redis need a
  user_id component added to the key or stored in the value
  with a check on read — audit this against S5-01's finding
  that job keys are currently fully unscoped.

CHAT CONTEXT:
  chat_service.build_context() currently has CURRENT_USER_ID
  = None hardcoded (flagged in S5-01's audit) — this is the
  ticket that removes it for real, threading the actual
  authenticated user through.

SYNC:
  The sync flow needs to use the authenticated user's own
  Enable Banking session, not a single global
  eb_session.json. This ticket scopes the DATA correctly;
  per-user bank session STORAGE is Sprint 7's job (it needs
  the public deployment context to do properly) — for this
  sprint, it's acceptable for the single existing
  eb_session.json to remain tied to Borys's account
  specifically, as long as that's enforced (only Borys's
  user_id can trigger sync against it) rather than left open.
  State this limitation explicitly in ARCHITECTURE.md.

ACCEPTANCE CRITERIA:
- Every endpoint requires authentication except the
  explicitly public ones (health, login, register, OAuth
  callback) — enumerate the public list explicitly in
  ARCHITECTURE.md so it's an intentional, reviewable set
- Every list/create endpoint filters by user_id
- Every by-ID endpoint checks ownership and returns 404 (not
  403) on mismatch
- job_store keys are user-scoped or ownership-checked on read
- chat_service's CURRENT_USER_ID hardcoding is gone
- Sync is restricted to the account it's currently tied to
- A real test: create a second test user (throwaway, not
  Borys's account), confirm they see zero of Borys's data
  anywhere and get 404s on his resource IDs, not data leaks

WHEN DONE:
- Enumerate the full public-route list
- Show the second-test-user isolation check passing for
  every endpoint category
- Show a 404 (not 403) on a cross-user by-ID request
- Do not start S6-07 until confirmed

================================================================
TICKET S6-07 — Security Auditor Pass
================================================================

THIS IS A SECURITY AUDITOR TICKET, NOT A CODEE TICKET.

Per AGENTS.md, the Security Auditor role activates now,
before auth ships to any real second user. Boot a separate
Claude Code session for this — it never writes code, same
posture as the Reviewer, but its brief is adversarial: try to
find a way through, don't just check the intended path works.

BRIEF FOR THE AUDITOR (paste this as its task):

  Review the full authentication and authorization
  implementation from S6-01 through S6-06. You are not
  checking "does the happy path work" — the Reviewer already
  confirmed that ticket by ticket. Your job is to try to
  break it. Specifically:

  1. Session security: can a session id be guessed, forged,
     or replayed? Is the cookie correctly httpOnly/Secure/
     SameSite? What happens to a session after logout — is it
     truly dead, or just removed client-side?
  2. Password handling: is there any path where a password
     or its hash could leak into logs, error messages, or the
     verification_debt.md ledger (this project's specific
     known risk pattern from S5-06/S5-07)?
  3. IDOR sweep: independently attempt cross-user access on
     every by-ID endpoint, not just the ones S6-06's own test
     covered — look for ones that might have been missed.
  4. Account-linking logic (S6-03): can the Google/password
     linking be abused to take over an account (e.g.
     registering a password account with someone else's
     email, then linking via Google)?
  5. Rate limiting: are login/register genuinely protected
     against brute-force, or does the limit reset in a way
     that's trivially bypassed?
  6. The Category A/B distinction from S6-06: spot-check
     that nothing was miscategorized (a by-ID-shaped endpoint
     treated as list-shaped, missing its ownership check).

  Report findings the same way the Reviewer does — CRITERIA
  CHECK / FINDINGS / VERDICT — but weighted toward "what did
  I break," not "did it match the ticket."

ACCEPTANCE CRITERIA:
- Full audit report produced
- Every finding triaged: fixed immediately (if small), or
  a bounce back to Codee (if it touches real code), same
  confirm/bounce loop as every other ticket
- No sprint-close until this audit's findings are resolved,
  not just filed

WHEN DONE (this is Borys's summary once the audit and any
resulting fixes land):
- Audit report attached/summarized
- Every finding's resolution stated
- Do not start S6-08 until confirmed

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

================================================================
SPRINT 6 → SPRINT 7 HANDOFF
================================================================
Sprint 7 — "Deployment & Public Onboarding": public hosting
(Railway/Render — decide at Sprint 7 kickoff), real HTTPS
retiring mkcert, per-user Enable Banking session storage
(properly, not the single-account restriction accepted this
sprint), the web-only first-time bank auth flow (finally
possible with a public callback URL), production CORS/env
config, and email infrastructure to close S6-08's Item 5
ledger entries.

================================================================
END OF SPRINT 6 TICKETS
================================================================
