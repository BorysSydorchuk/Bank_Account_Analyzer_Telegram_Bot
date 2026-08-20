Status: in-progress
Source: docs/tickets/S6-00-sprint-plan.md

---

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
