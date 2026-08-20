Status: confirmed
Source: docs/tickets/S6-00-sprint-plan.md

---

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

---

## WHEN DONE — answered:

**Real live Google OAuth flow — flagged, not faked, per this ticket's own
acceptance criteria.** No `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` existed
anywhere before this ticket. Flagged to Borys before building
(`AskUserQuestion`); he's setting up a real Google Cloud OAuth client
while this ticket's code was built, so it's ready to test the moment
credentials exist. **This ticket is not fully closed** — logged as an OPEN
entry in `docs/verification_debt.md` ("Real live Google OAuth flow — not
run (S6-03)"), closing once Borys completes a real sign-in himself
(same posture as Enable Banking's real KBC login — Codee doesn't handle
real Google credentials either).

**What was verified live instead, against real Postgres + Redis (not
mocks), with only Google's own two HTTP calls faked at the exact seam
`routers/user_auth.py` imports them through** —
`tests/test_google_oauth.py`, 6/6 passing:

- `test_new_google_sign_in_creates_a_user_and_session` — a fresh
  `google_id`/email creates a real `User` row (`google_id` set,
  `password_hash` NULL) and a real session whose `get_session()` resolves
  to that user's id.
- `test_google_sign_in_links_to_an_existing_password_account` — **the
  account-linking case.** Pre-seeded a password-only `User` row, then ran
  the Google flow against the same email: exactly one row for that email
  afterward, its `google_id` now set, its `password_hash` untouched — not
  a duplicate account.
- `test_returning_google_user_reuses_their_existing_row` — running the
  flow twice with the same `google_id` resolves to the same user both
  times, doesn't create a second row.
- `test_callback_with_wrong_state_rejects_without_creating_a_session` —
  **the CSRF check, exercised for real** (a genuine `oauth_state` cookie
  from a real `/google/login` call, then a callback with a *different*
  state value): `303` to `/login?error=...`, no session cookie set.
- `test_google_login_with_no_client_id_configured_redirects_cleanly` —
  the exact situation this ticket started in (`GOOGLE_CLIENT_ID` unset):
  a clean redirect to `/login?error=...`, not a raw 500/traceback
  (CLAUDE.md's error-handling rule — this wasn't in the original code
  until I caught it while building and fixed it before it ever ran).
- `test_logout_destroys_the_session` — **logout invalidating the
  session, live:** `POST /api/auth/logout` returns `204`, and
  `get_session(session_id)` returns `None` immediately after.

Full suite: `26 failed` (the exact, unchanged S6-02-tracked set — nothing
in this ticket touches those call sites), `47 passed` (41 carried over +
6 new). No regression anywhere else.

**Frontend:** `/login` (`LoginPage.tsx`) builds clean (`tsc -b`, no
errors), lints clean (`oxlint`), and Vite serves its compiled module with
no transform error. **Could not visually confirm rendering/click-through
in a real browser** — the Chrome extension wasn't connected in this
session. Also logged in `verification_debt.md`, closing at the same real
sign-in test as the OAuth flow itself (that test necessarily loads
`/login` in a real browser anyway).

KEY DECISIONS:
- **Plain `requests` calls against Google's documented endpoints, not a
  dedicated OAuth SDK** (`app/google_oauth.py`) → this flow only ever
  needs three HTTP calls (authorize URL, token exchange, userinfo) against
  fixed endpoints, and `requests` is already a dependency → the
  alternative, `google-auth-oauthlib`, would add a dependency for three
  calls this app doesn't need a library to make.
- **State CSRF token in a short-lived cookie, not Redis** → the state
  value has no meaning beyond "does this callback answer the request that
  set this cookie" — a plain cookie round-trip proves that without a
  server-side store to manage/expire → Redis would've meant a second
  storage mechanism for something a cookie already does correctly.
- **Account linking requires `email_verified: true` from Google**
  (`google_oauth.fetch_userinfo`) → S6-07's Security Auditor brief names
  account-linking abuse explicitly (item 4) — linking on an unverified
  email would let anyone claim an existing password account by typing its
  email into a Google signup without proving ownership of it → closing
  this off now, not leaving it for the audit to find.
- **`allow_credentials=True` added to CORS, `credentials: "include"`
  added to every frontend fetch** → not explicitly listed in the ticket's
  own steps, but mechanically required — without it, the session cookie
  this ticket sets can never reach a cross-origin API call, making the
  whole login flow non-functional in local dev (frontend `:5173`, backend
  `:8000`) → flagged here since it's a real, if small, scope addition
  beyond the ticket's literal text.

WATCH OUT FOR:
- Real Google OAuth verification is still open — see
  `docs/verification_debt.md`. Until it closes, "does this work against
  Google's real consent screen" is verified only by faithful mocking of
  Google's documented API shape, not by an actual round-trip.
- `/login`'s actual rendering/interaction is likewise unverified in a
  real browser — same closure condition.
- The existing-different-`google_id`-on-this-email branch in
  `google_callback` (a would-be account-takeover shape) has no test —
  it can't happen through this ticket's own code paths (nothing else
  writes `google_id`), so there's nothing to construct that state with
  yet; worth a test once S6-04's registration flow exists alongside this.

HOW IT CONNECTS: S6-04 adds the second sign-in method to the same `users`
table and session primitives this ticket exercised for real; S6-05/S6-06
are what actually put `get_current_user` in front of real routes — this
ticket only proves the login *side* works, not that anything is
protected yet.

**Update (2026-08-20):** real credentials added to `.env`; a
`redirect_uri_mismatch` surfaced and was fixed (the callback URL wasn't
yet registered on the Google Cloud OAuth client); Borys then completed a
real sign-in and confirmed it worked. All of S6-03's acceptance criteria
are now met. Closed in `docs/verification_debt.md`.

Ready for S6-04.
