Status: confirmed
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

## WHEN DONE — answered:

**Built:** `app/models.py`'s `User` model + migration `1f7634448483_add_users_table.py`
(CHECK constraint declared in both, same reason as `Transaction`'s
`UniqueConstraint`/`Budget`'s `CheckConstraint` — so `alembic revision
--autogenerate` diffs against the real constraint). `app/auth/password.py`
(`hash_password`/`verify_password`, passlib bcrypt). `app/auth/session.py`
(`create_session`/`get_session`/`destroy_session`, plus
`set_session_cookie`/`clear_session_cookie` helpers for S6-03/S6-04 to
reuse without redefining the cookie's attributes a second time).
`app/auth/dependency.py` (`get_current_user`, not imported by any router
yet). `requirements.txt` gained `passlib[bcrypt]` and `bcrypt<4.1` (pinned
— see WATCH OUT). `ARCHITECTURE.md` gained an Auth section.

**Round-trip test for all three primitives** — real Redis (test db 15, per
`tests/conftest.py`), `pytest tests/test_auth_primitives.py -v`:

```
test_session_round_trip PASSED
test_get_session_returns_none_for_unknown_session_id PASSED
test_get_current_user_rejects_missing_cookie PASSED
test_get_current_user_rejects_expired_or_unknown_session PASSED
test_get_current_user_rejects_tampered_session_id PASSED
test_get_current_user_accepts_valid_session PASSED
10 passed in 2.13s
```

`test_session_round_trip` covers `create_session` → `get_session` (returns
the same `user_id`) → `destroy_session` → `get_session` (now `None`).
`get_current_user`'s three rejection paths are each their own test: no
cookie at all, a cookie naming a session that was never created (stands in
for "expired" — Redis TTL expiry and "never existed" are indistinguishable
once the key is gone, which is also why a genuinely expired session needs
no separate fixture), and a cookie value mutated by one character
("tampered"). All three 401.

**CHECK constraint rejecting an invalid row** — real disposable Postgres
(Alembic's actual migration chain run against it, not `create_all()`):

```
test_check_constraint_rejects_row_with_neither_auth_method PASSED
test_check_constraint_allows_password_only_account PASSED
test_check_constraint_allows_google_only_account PASSED
```

The rejection test asserts `IntegrityError` matching `users_has_auth_method`
on `db_session.flush()` for a `User(email=..., password_hash=None,
google_id=None)` row; the other two confirm each valid shape (password-only,
google-only) is accepted.

Full suite: `67 passed` (all prior Sprint 4/5 tests still green — the new
`users` table and its migration don't touch any existing table).

**Why sliding TTL, and what's the refresh threshold?** A fixed 30-day
expiry would log out a daily active user exactly as readily as an
abandoned session — the thing actually worth expiring is inactivity, not
elapsed time. `get_session()` re-issues the full 30-day TTL only once less
than `REFRESH_THRESHOLD_SECONDS` (5 days) remains on the key, rather than
on every authenticated request — that bounds Redis `EXPIRE` writes to
roughly once per 5 days of continuous use per session, instead of one
write per API call for the app's whole lifetime, while an actively-used
session still never expires.

KEY DECISIONS:
- **Bcrypt over argon2id** (passlib's `CryptContext`) → no unusual
  offline-cracking threat model here, and no extra native dependency
  beyond what `passlib[bcrypt]` already pulls in (argon2id needs
  `argon2-cffi` separately) → the alternative (argon2id) is also
  acceptable per the ticket, just not the one picked.
- **`bcrypt` pinned `<4.1`** in `requirements.txt` → passlib 1.7.4's
  bcrypt backend reads `bcrypt.__about__.__version__`, an attribute
  bcrypt 4.1 removed; unpinned, every `hash_password`/`verify_password`
  call logs a spurious "error reading bcrypt version" warning (confirmed
  by installing unpinned first, then re-pinning) → the alternative was
  living with the warning noise (harmless but adds log clutter to every
  registration/login once S6-04 ships) or switching off passlib entirely,
  which the ticket didn't ask for.
- **`COOKIE_SECURE` is an env var, default `false`, not hardcoded `true`**
  → `backend`/`frontend` both run over plain `http://` in every
  environment this app runs in today, and a browser refuses to send a
  `Secure` cookie back to a plain-`http://` origin — hardcoding `true`
  would break every local dev login starting S6-03 → the alternative was
  relying on Chromium's `http://localhost`-is-trustworthy exemption, not
  taken because that exemption isn't reliably specified to cover the
  cookie `Secure` attribute across every browser this might be developed
  in; an explicit flag (same pattern as `FRONTEND_ORIGIN`'s existing
  dev/prod split) is the safer choice for a security-relevant attribute.
  **Flagging as asked:** this does not break local `http://` dev
  workflows — `COOKIE_SECURE` defaults off, so nothing changes locally;
  Sprint 7's real HTTPS is expected to set it `true`.
- **Session id is `secrets.token_urlsafe(32)`, not a UUID** → 256 bits
  from Python's CSPRNG vs. a UUID4's 122 bits of actual randomness (the
  other 6 are fixed version/variant bits) — session ids are exactly the
  kind of value S6-07's Security Auditor pass will try to guess/forge, so
  the wider margin costs nothing and closes that question before it's
  asked.

WATCH OUT FOR:
- `requirements.txt` changed (`passlib[bcrypt]`, pinned `bcrypt`) —
  `backend`/`celery_worker` docker images need `docker compose build`
  before their next `up`, not just a container restart, or they'll import
  against the old image's package set. Not done in this ticket (no route
  uses these primitives yet, so nothing breaks meanwhile); flagging so
  S6-02/S6-03 don't hit a stale-image `ModuleNotFoundError` unexpectedly.
- `get_current_user`'s "user row no longer exists" branch (session valid,
  `db.get(User, user_id)` returns `None`) has no dedicated test — it can't
  happen yet since nothing can delete a user this sprint, but once
  account deletion exists this path is real and worth its own test then.
- Migration `1f7634448483` only adds the table — no bootstrap row, no
  backfill onto other tables. That's S6-02's job entirely.

HOW IT CONNECTS: Nothing consumes any of this yet — no router imports
`get_current_user`, no endpoint calls `create_session`. This ticket exists
purely so S6-02 has a `users` table to seed Borys's real account against,
and so S6-03/S6-04's login routes have `create_session`/
`set_session_cookie`/`hash_password` ready to call rather than inventing
them mid-ticket.

Ready for S6-02 whenever you confirm this one.
