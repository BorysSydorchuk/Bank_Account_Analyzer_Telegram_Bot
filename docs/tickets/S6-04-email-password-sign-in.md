Status: in-progress
Source: docs/tickets/S6-00-sprint-plan.md

---

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
