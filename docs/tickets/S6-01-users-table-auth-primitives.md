Status: in-progress
Source: docs/tickets/S6-00-sprint-plan.md

---

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
