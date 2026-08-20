Status: confirmed
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

---

## WHEN DONE — answered:

**Register + login, live against real Postgres (not just tests):**

```
POST /api/auth/register {"email":"livetest-s604@example.com","password":"correct-horse-battery"}
  -> 201 {"id":"...","email":"livetest-s604@example.com"}, session cookie set
POST /api/auth/login    {"email":"livetest-s604@example.com","password":"correct-horse-battery"}
  -> 200 {"id":"...","email":"livetest-s604@example.com"}, session cookie set
POST /api/auth/logout   (with that session cookie)
  -> 204, session confirmed dead immediately after
```
Throwaway account deleted afterward — not left in the real dev database.
Also 11 automated tests (`tests/test_email_password_auth.py`), covering
the same ground plus duplicate-email rejection, weak-password rejection,
a Google-only account's failed login, `set-password`'s auth requirement,
and the rate limit itself (6 rapid `/login` attempts: 5 real `401`s, the
6th a real `429`).

**Identical-error-message behavior, live:**

```
POST /api/auth/login {"email":"livetest-s604@example.com","password":"wrong-one"}
  -> 401 {"detail":"Invalid email or password."}
POST /api/auth/login {"email":"nope-s604@example.com","password":"whatever"}
  -> 401 {"detail":"Invalid email or password."}
```
Byte-identical `detail` for wrong password and nonexistent email — and,
per `tests/test_email_password_auth.py`'s
`test_login_fails_for_a_google_only_account_with_the_identical_message`,
also identical for a real account that simply has no password set yet
(Google-only). **Timing-based enumeration: partially addressed, not
fully closed** — `login()` always runs a real `bcrypt` verify (against a
fixed dummy hash when no user matches), so the dominant timing signal
(bcrypt's own ~tens-of-milliseconds cost) is equalized across all three
failure cases. Not addressed: sub-millisecond variance from the DB query
itself and ordinary network jitter, which a sufficiently patient/averaging
attacker could in principle still exploit. Flagging this as the honest
state rather than claiming a complete fix.

**Borys's real account:** not registered fresh (his row already exists,
`email` is unique, and inventing a "register onto an existing row"
special case in the public `/register` endpoint would itself be an
account-takeover shape — anyone typing his email into a signup form
could otherwise claim his account). Instead: he already has a live
session from S6-03's confirmed Google sign-in, so `POST
/api/auth/set-password` (new in this ticket, `get_current_user`-gated)
lets him add a real password to that same session without a
register/reset detour. **Needs Borys to actually run this and confirm** —
from a browser tab where he's still signed in (or after signing in again
via Google), open DevTools console and run:
```js
fetch("http://localhost:8000/api/auth/set-password", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  credentials: "include",
  body: JSON.stringify({password: "<a real password of your choosing, 8+ chars>"})
})
```
A `204` confirms it's set; he can then log in normally at `/login` with
his real email and that password.

**Minimum password bar: 8–128 characters, no complexity rules**
(`app/auth/password.py`'s `MIN_PASSWORD_LENGTH`/`MAX_PASSWORD_LENGTH`).
Matches NIST 800-63B's current guidance: mandatory
uppercase/digit/symbol rules don't meaningfully raise the real search
space an attacker faces — they push people toward predictable
substitutions ("Password1!") instead — while length is what actually
does. The 128 ceiling isn't a security requirement on its own; it closes
a gap S6-01's `password.py` docstring explicitly flagged and deferred to
this ticket: bcrypt silently truncates at 72 bytes, so without an upper
bound an absurdly long input would hash down to its first 72 bytes
without the caller ever being told, rather than being rejected outright.

Full suite: `58 passed` (47 carried over + 11 new), `26 failed`
(unchanged S6-02-tracked set). Frontend: `tsc -b` clean, `oxlint` clean,
both `/login` and `/register` confirmed served (`200`) by the live Vite
dev server with no transform error — same real-browser-rendering caveat
as S6-03 (not visually confirmed by me; unlike S6-03 this doesn't block
the ticket, since nothing here needs Google's real consent screen to
verify — the backend round-trip above is the actual functional proof).

KEY DECISIONS:
- **`set-password` over a reset-token flow for Borys's account** →
  he already has a live, real session from S6-03 — reusing it needed no
  new machinery, where a token flow would've meant building (and then
  never reusing) infrastructure for a one-time bootstrap need → the
  ticket's other stated option ("register fresh") wasn't actually safe to
  build the way it reads literally (see above).
- **`set-password` is a general authenticated endpoint, not
  Borys-specific** → any Google-only account might want to add password
  sign-in later; special-casing it to one email would be both more code
  and a worse design than the general form → no extra cost to generalize
  it correctly the first time.
- **Login always runs a real bcrypt verify, even for a nonexistent
  email** → closes the cheapest, largest timing-enumeration gap for
  near-zero extra code (one dummy hash, computed once) → the alternative
  (short-circuit on "no such user") is what most naive implementations
  do, and is exactly the shape S6-07's audit would flag.
- **`register` rejects a duplicate email with a specific message,
  `login` never varies its message** → these look inconsistent but
  aren't: register's own existence already confirms account creation is
  possible, so a specific "already exists" reveals nothing new; login's
  entire job is authenticating an existing claim, where confirming
  "exists but wrong password" vs. "doesn't exist" is the actual leak.

WATCH OUT FOR:
- Timing-based enumeration is only partially closed (see above) — a
  determined, statistically-patient attacker still has a theoretical
  edge. Not treated as blocking (this matches common practice, not a
  known-broken state), but worth S6-07 spot-checking.
- `set-password` has no rate limit — unlike register/login, it requires
  an existing session to reach at all, which is a meaningfully higher
  bar than an anonymous brute-force target; flagged rather than silently
  assumed fine.
- Frontend `/login`/`/register` rendering still isn't visually confirmed
  in a real browser this session (Chrome extension unavailable) — not
  blocking here since the backend round-trip is independently proven,
  but still worth a real look whenever convenient.

HOW IT CONNECTS: both sign-in methods (S6-03, S6-04) now write to and
read from the exact same `users` table and session primitives (S6-01).
S6-05 is what actually starts checking `get_current_user` in front of the
app's real feature routes — this ticket's own use of it (`set-password`)
was narrow and auth-settings-specific, not a preview of that sweep.

Ready for **S6-05** whenever you confirm this one AND run the
`set-password` call above for your real account.
