Status: in-progress
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
