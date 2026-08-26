Status: delivered

================================================================
TICKET S7-06 — Per-User Enable Banking Session Storage
================================================================

BACKGROUND: Sprint 6 explicitly accepted a limitation — sync
restricted to Borys's account only, enforced rather than
built properly, because doing this right needed the public
deployment context Sprint 7 provides. That context now exists:
mymble.be is live, HTTPS is real, per-user auth is working.
This ticket removes that limitation for real.

PREMISE CHECK FIRST: read the current eb_service.py,
eb_callback_server.py's replacement (retired in S7-04 — confirm
what replaced its role for the reconnect flow), and how the
single eb_session.json was migrated/handled through S7-01 to
S7-05. Confirm exactly what "the current single-account
restriction" consists of in code today before changing it —
per this sprint's established discipline, don't assume, check.

WHAT TO BUILD:
- Replace the single global Enable Banking session (wherever
  it currently lives post-S7-04's mkcert retirement — likely
  Secrets Manager or a DB-backed equivalent by now, confirm)
  with PER-USER session storage
- Encrypted at rest, same Fernet pattern already used for
  API keys and other per-user secrets (per S6-02's settings
  redesign)
- Keyed by user_id
- Each user's Enable Banking OAuth flow (requisition, session
  token, refresh, expiry) becomes fully independent — one
  user's session state never touches another's
- The reconnect/expiry banner becomes correctly per-user: one
  user's expiring session should never show a banner to
  another logged-in user
- Migrate Borys's existing real session into the new per-user
  store — his real bank connection must survive this migration
  working, same care standard as every prior real-data
  migration in this project (S4-01, S7-03)
- The Enable Banking callback route (S7-04's real production
  route, now with its CSRF fix) needs to correctly resolve
  WHICH user's session it's completing for — likely via the
  existing eb_oauth_state cookie pattern already carrying
  enough context, confirm and extend if needed rather than
  inventing a new mechanism

ACCEPTANCE CRITERIA:
- No global/single-account session storage remains anywhere
  in the codebase — confirmed via grep, real evidence
- A second real or test user can establish their own
  independent Enable Banking connection without touching or
  seeing Borys's session in any way
- Expiry/reconnect banner correctly scoped per user — real
  test with two distinct sessions at different expiry states,
  not just code review
- Borys's existing real connection continues working
  correctly through and after the migration — real live sync
  test against his real data, not narration
- Encryption confirmed working (a real session decrypts
  correctly) — same evidence standard as every credential-
  touching ticket this sprint
- ARCHITECTURE.md updated with the new per-user session model

WHEN DONE:
- Show the per-user storage structure (real schema/structure,
  not description)
- Show two independent sessions coexisting — real evidence,
  ideally an actual second test user completing a real or
  realistic Enable Banking flow, not just a database row
  inserted directly
- Show Borys's real connection working post-migration (a
  real sync against his real data)
- Do not start S7-07 until confirmed

## PREMISE CHECK (2026-08-26)

Read `app/eb_service.py`, `kbc_analyzer/enablebanking.py`, `app/routers/auth.py`,
`app/auth/dependency.py`, `app/tasks/analysis.py`, `app/routers/transactions.py`,
and `app/models.py` directly, not from memory.

**"The current single-account restriction" is exactly one thing:**
`app/auth/dependency.py`'s `require_enable_banking_owner` — composed on
`get_current_user`, checks `current_user.email == ENABLE_BANKING_OWNER_EMAIL`,
403s everyone else. It gates all three `/api/auth/enable-banking/*`
routes plus `POST /api/transactions/sync`.

**Where the session actually lives today:** `kbc_analyzer/enablebanking.py`'s
`EnableBankingClient` reads/writes a single local file, `eb_session.json`
(`SESSION_FILE` constant), directly — `session_valid()`, `get_cached_uids()`,
`get_session_info()`, and `complete_auth_with_code()` all touch it
directly. **Not** Secrets Manager, **not** a DB-backed equivalent — the
ticket's own "likely Secrets Manager or DB-backed by now, confirm" guess
was wrong; nothing beyond S7-04's mkcert retirement ever touched this
file's storage mechanism.

**Real, unprompted finding — checked empirically, not assumed:** execed
into the currently-running production web task
(`aws ecs execute-command`) before writing any code. `eb_session.json`
does not exist there — `ls: cannot access 'eb_session.json': No such
file or directory`. S7-04's real Enable Banking reconnect (confirmed
working by Borys) happened before `fc06592`'s redeploy; that redeploy
replaced the task and wiped its local filesystem, taking the session
with it. Separately, and independent of that: `web` and `celery_worker`
are two different ECS tasks with two different filesystems (confirmed —
no EFS or shared volume exists anywhere in `infra/`), so even without a
redeploy, a session written by the web container's callback route was
never visible to the worker container that actually runs sync. This
means production sync against a real Enable Banking session may never
have actually worked end-to-end at all — S7-04's "live round-trip"
only exercised the callback completing, not a subsequent sync reading
the result. This ticket's move to Postgres-backed storage (shared by
both services) fixes this structurally, as a side effect of doing the
per-user work correctly.

**Consequence for "migrate Borys's existing session":** there is nothing
to migrate — it's already gone. Flagging this now rather than silently
reinterpreting the ticket: the acceptance criterion "Borys's existing
real connection continues working correctly through and after the
migration" cannot be met as literally written, because no existing
connection survived to be migrated. The achievable equivalent: Borys
reconnects once through the ordinary UI after this ships (identical
user action to what any new user will do), and that write is the real
proof the new storage works — not a data migration, but the same
real-evidence bar this project has always required for a live Enable
Banking test.

Proceeding on this basis — full build below, second-user isolation
proven via committed tests + real code paths (not narration), Borys's
real reconnect requested as the closing step rather than assumed
already done.

## DELIVERY (2026-08-26)

### What was built

- **`enable_banking_sessions` table** (`app/models.py`'s
  `EnableBankingSession`, migration `a3f6c8e2b704`) — one row per
  `user_id`, `session_id_encrypted`/`account_uids_encrypted` Fernet-
  encrypted (`app/crypto.py`, same pattern as `settings`'s API keys),
  `valid_until` plain.
- **`app/eb_session_store.py`'s `DatabaseSessionStore`** — implements
  the same `load()`/`save()` shape `EnableBankingClient` already
  expected, scoped to `(db, user_id)`.
- **`kbc_analyzer/enablebanking.py`** — `EnableBankingClient` now takes
  a pluggable `session_store` (new `FileSessionStore`, unchanged
  behavior, stays the default for the terminal/bot flow). Every method
  that used to touch `SESSION_FILE` directly now goes through
  `self.session_store` instead.
- **`app/eb_service.py`** — `EnableBankingService(db, user_id)`, builds
  a `DatabaseSessionStore` for the given user.
- **`app/routers/auth.py`** — `require_enable_banking_owner` replaced
  with plain `get_current_user` on all three endpoints. New
  `eb_oauth_user_id` cookie (mirrors `user_auth.py`'s
  `oauth_link_user_id` from S6-07) binds a reauthorize attempt to the
  user who started it — closes a real cross-user race the state cookie
  alone doesn't cover (see ARCHITECTURE.md's Auth section for the full
  writeup).
- **`app/tasks/analysis.py`, `app/routers/transactions.py`** —
  `EnableBankingService(db, user_id)` / `get_current_user` respectively.
- **`app/auth/dependency.py`** — `require_enable_banking_owner` deleted
  outright, not deprecated in place.
- **Infra** — `ENABLE_BANKING_OWNER_EMAIL` removed from
  `infra/web.tf`/`worker.tf`/`variables.tf` and `.env.example`.

### Real test evidence (not narration)

```
$ python -m pytest -v tests/test_enable_banking_per_user_sessions.py tests/test_enable_banking_callback_csrf.py --no-cov
tests/test_enable_banking_per_user_sessions.py::test_two_users_get_independent_encrypted_sessions PASSED
tests/test_enable_banking_per_user_sessions.py::test_a_second_users_reauthorization_never_touches_the_first_users_row PASSED
tests/test_enable_banking_per_user_sessions.py::test_expiry_status_is_independent_per_user PASSED
tests/test_enable_banking_callback_csrf.py::test_reauthorize_sets_state_cookie_matching_the_real_outgoing_state PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_rejects_mismatched_state PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_rejects_a_forged_link_with_no_cookie_at_all PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_rejects_a_valid_state_from_a_different_logged_in_user PASSED
tests/test_enable_banking_callback_csrf.py::test_callback_with_matching_state_completes_reauthorization PASSED
8 passed

$ python -m pytest -q   # full suite
108 passed, 1 warning in 13.92s
```

The new isolation tests deliberately do **not** use the existing
`mock_enable_banking_client` fixture — that fixture replaces the whole
`EnableBankingClient` class with an in-memory fake, which would bypass
exactly what needed proving (that `complete_auth_with_code()` really
writes through `DatabaseSessionStore`, really Fernet-encrypts). Only the
outbound HTTP call (`EnableBankingClient._post`) is mocked (TESTER.md
prime directive 3), so `complete_auth_with_code`, the session store, and
encryption are all real code paths.

`test_two_users_get_independent_encrypted_sessions` proves: two users'
raw `session_id_encrypted` values never contain the plaintext, are never
equal to each other, and decrypt correctly to each user's own value —
real ciphertext, real Fernet round-trip, not asserted from reading the
code. `test_a_second_users_reauthorization_never_touches_the_first_users_row`
proves the `on_conflict_do_update` is genuinely scoped to `user_id` (a
second user's write leaves the first user's row byte-for-byte
unchanged, re-read from Postgres, not the SQLAlchemy identity-map
cache). `test_expiry_status_is_independent_per_user` proves the banner
logic never leaks one user's expiry into another's.
`test_callback_rejects_a_valid_state_from_a_different_logged_in_user`
proves the new cross-user race is actually closed, not just described.

### Grep evidence — no global session storage remains

```
$ grep -rln "require_enable_banking_owner\|ENABLE_BANKING_OWNER_EMAIL" --include="*.py" --include="*.tf" --include="*.example" . | grep -v docs/tickets
./kbc_analyzer/backend/app/routers/auth.py
./kbc_analyzer/backend/tests/test_enable_banking_callback_csrf.py
./kbc_analyzer/backend/tests/test_full_query_scoping.py
```

Checked what those three actually are: all three are explanatory
comments describing what was retired and why (this project's standing
practice for "replaces X" comments, same treatment S7-04 gave its mkcert
grep). Confirmed separately — zero matches for an actual function
definition or `getenv`/`environ[...]` call:

```
$ grep -rn "def require_enable_banking_owner\|getenv(\"ENABLE_BANKING_OWNER_EMAIL\"\|os.environ\[.ENABLE_BANKING_OWNER_EMAIL.\]" --include="*.py" --include="*.tf" .
(empty)
```

```
$ grep -n "open(SESSION_FILE\|os.path.exists(SESSION_FILE" kbc_analyzer/backend/kbc_analyzer/enablebanking.py
(empty — SESSION_FILE is only FileSessionStore's default path now)
```

### Status against acceptance criteria

- No global/single-account session storage remains: **done**, grep
  evidence above.
- A second (test) user establishes an independent connection without
  touching Borys's: **done** via the real code path, proven by the
  isolation tests above. Not yet done as an actual second *real* human
  clicking through the browser flow — see below.
- Expiry/reconnect banner correctly scoped per user: **done**, real
  test with two distinct expiry states.
- Borys's existing connection continues working post-migration: **not
  achievable as written** — see the premise check above. Reframed:
  waiting on Borys's one real reconnect through the live UI.
- Encryption confirmed working: **done**, real Fernet round-trip in the
  isolation tests, not asserted from code review.
- ARCHITECTURE.md updated: **done**.

### Deployed (2026-08-26, real evidence)

Migration run for real against the production RDS instance, via the
migration-runner pattern (same as S7-03), before either service was
redeployed — production images don't run `alembic upgrade head`
automatically (that's a local-dev-only Dockerfile CMD override), so
running it first mattered, not just as a formality:

```
$ alembic current
5c9a2e6b8f14
$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade 5c9a2e6b8f14 -> a3f6c8e2b704, add enable_banking_sessions table
$ alembic current
a3f6c8e2b704 (head)
```

Real schema, queried directly on RDS (not read back from the migration
file):
```
('user_id', 'uuid')
('session_id_encrypted', 'text')
('account_uids_encrypted', 'text')
('valid_until', 'timestamp with time zone')
('updated_at', 'timestamp with time zone')
```

Both images built from `Dockerfile.prod`, tagged `7bc18df`, pushed to
ECR, deployed via `terraform apply` (removed `ENABLE_BANKING_OWNER_EMAIL`
from both task definitions in the same apply). Both services confirmed
`ecs wait services-stable`, running count 1/1 on the new task
definitions. `GET /health` returns `200` post-deploy.

**Real production test — the owner gate is actually gone, not just in
task-def env vars:** registered a throwaway test user
(`s7-06-verify-test@example.com`), hit
`GET /api/auth/enable-banking/status` with their session — `200
{"status":"expired","expires_at":null}`, not the `403` this exact
request would have returned before this ticket. `POST /reauthorize`
for that same user returned a real Enable Banking authorization URL
(`https://tilisy.enablebanking.com/ais/start?sessionid=...`) and set
both cookies — the cookie jar confirms `eb_oauth_user_id` carried this
test user's own real UUID
(`b53077d0-e887-4079-8951-809bdc615a92`), matching their registration
response exactly. Test account deleted afterward (migration-runner
pattern, `DELETED 1`, independently re-confirmed via a `401` on a
follow-up login attempt), same discipline as every other test account
this project has created and cleaned up.

### What's still needed before this is confirmed

1. **Borys does one real reconnect** through `https://mymble.be`'s
   Settings page — this is both "restore his bank connection" and the
   real live-flow evidence the ticket originally asked for, correctly
   reframed given the premise-check finding that there was nothing left
   to migrate (his prior session was already gone before this ticket
   started).
2. After (1): a real sync against his real data, proving the
   web-writes/worker-reads gap identified in the premise check is
   actually closed, not just theoretically fixed by moving storage into
   Postgres.

Do not start S7-07 until (1)–(2) are complete and confirmed.
