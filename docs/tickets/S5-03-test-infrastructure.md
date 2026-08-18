Status: delivered
Source: chat handoff to Tester session (TESTER.md boot prompt)

---

================================================================
TICKET S5-03 — Test Infrastructure  [TESTER TICKET]
================================================================

THIS IS A TESTER AGENT TICKET. Borys boots a separate
Tester session (TESTER.md boot prompt) for S5-03 and S5-04.
Codee does not build these.

WHAT TO BUILD:
The test foundation everything else runs on. No behavior
tests yet — this ticket is fixtures, configuration, and
proving the harness works.

REQUIRED:

  ## Runner and layout
  pytest, configured in backend/pyproject.toml or
  pytest.ini. Tests live in backend/tests/. One command
  runs everything from backend/. Document the command in
  backend/tests/README.md.

  ## Test database
  A separate, disposable Postgres database — never the dev
  database. Created and migrated by a session-scoped
  fixture running the REAL Alembic chain (this also tests
  that migrations apply cleanly from scratch, which has
  never been verified end-to-end). Torn down after the
  run.

  ## Fixtures
  - db_session: function-scoped, transactional, rolled
    back after each test so tests never see each other's
    writes
  - client: FastAPI TestClient with the db dependency
    overridden to the test session
  - Seeded reference data: the 7 categories with colors
  - Factory helpers for transactions, budgets, insights —
    invented but realistic data (Belgian merchants, EUR,
    plausible dates). NEVER Borys's real data.

  ## External boundaries mocked
  - LLMProvider: a fake provider returning canned
    structured responses; no live Gemini or Claude calls
    ever
  - Enable Banking client: mocked at the client boundary;
    no live bank calls ever
  - Celery: task_always_eager so tasks run inline
  - Redis: fakeredis or an equivalent, or a dedicated test
    Redis database index

  ## Determinism
  Time frozen where tests depend on "today" (freezegun or
  equivalent) — budget month boundaries and session-expiry
  logic both need this. No sleeps as synchronization. No
  test-order dependencies.

  ## Proof the harness works
  Three smoke tests: one that hits GET /health through the
  client fixture, one that writes and reads a transaction
  through db_session, one that runs the fake LLM provider.

ACCEPTANCE CRITERIA:
- One command runs the suite from a clean state
- The test database is created via the real Alembic chain
  and is definitively not the dev database (show the
  connection string logic)
- Fixtures roll back — two tests writing the same row do
  not collide
- No test touches a live external service
- The three smoke tests pass

WHEN DONE:
- Show the run command and its full output
- Show the test database creation/teardown working
- Confirm no live external calls (how is this enforced,
  not just intended?)
- Explain: why run the real Alembic chain instead of
  create_all() from the models?
- Do not start S5-04 until confirmed

---

DELIVERY NOTES (Tester)

This ticket was picked up mid-flight after a previous Tester
session was interrupted (session closed, not reverted). All
files below existed uncommitted in the working tree when this
session started; this session verified them empirically against
the acceptance criteria, resolved one environment blocker
(unrelated to the test code itself), and committed.

RECOVERY: nothing had been committed for S5-03. The working
tree had docs/tickets/S5-03-test-infrastructure.md,
backend/tests/{conftest.py, test_smoke.py, README.md,
fixtures/*}, and a backend/pyproject.toml diff adding the
`test` optional-dependency group and `[tool.pytest.ini_options]`
— all untracked/unstaged. Read in full and assessed against
this ticket's acceptance criteria before touching anything
further; matched closely enough to continue rather than
restart (Borys confirmed).

ENVIRONMENT BLOCKER FOUND AND RESOLVED (not app-code, not
test-code): a native Windows `postgres.exe` service was also
bound to port 5432 alongside Docker's container port mapping,
so host-side test connections to `localhost:5432` landed on
the wrong Postgres server (wrong credentials) instead of the
dev stack's `db` container. Confirmed via `docker exec ...
psql` that the container itself accepted the same credentials
fine — this was a host-machine port collision, not a defect in
conftest.py. Borys stopped the native service; re-ran after.

WHEN DONE:

1. Run command and full output — `pytest` from `backend/`:

   tests/test_smoke.py::test_health_endpoint_reachable_through_client_fixture PASSED [ 33%]
   tests/test_smoke.py::test_db_session_writes_and_reads_a_transaction PASSED [ 66%]
   tests/test_smoke.py::test_fake_llm_provider_returns_canned_responses PASSED [100%]
   ======================== 3 passed, 1 warning in 1.82s =========================

   (warning is FastAPI's own httpx/TestClient deprecation notice,
   unrelated to this suite.) Ran the full suite twice in a row —
   both green.

2. Test database creation/teardown — verified empirically, not
   just by reading the fixture. Before any run, `kbc_analyzer_test`
   does not exist. After each of two consecutive full runs,
   `psql -c "\l"` against the `db` container shows `kbc_analyzer_test`
   absent again — the session-scoped `test_db_engine` fixture drops
   it on teardown every time, and recreates + re-migrates it cleanly
   on the next run. `kbc_analyzer` (dev db) was never touched, and
   conftest.py asserts `TEST_DB_NAME != POSTGRES_DB` and
   `TEST_DATABASE_URL != DEV_DATABASE_URL` at import time — a hard
   guard, not just naming convention.

   Also proved rollback isolation directly, beyond what the smoke
   tests cover: wrote a throwaway two-test file (not committed)
   where both tests inserted a transaction row with the identical
   fixed primary key and external_id via `db_session`. Both passed.
   If `db_session`'s per-test SAVEPOINT rollback weren't working,
   the second test would have hit a primary-key/unique violation
   from the first test's still-visible row. It didn't — confirms
   "two tests writing the same row do not collide" from the
   acceptance criteria.

3. No live external calls — enforced two ways, not merely
   intended: (a) `LLMProvider` and the Enable Banking client are
   mocked at their real boundaries (`fake_llm_provider.py`,
   `fake_enable_banking.py`), so nothing in the test suite ever
   holds a reference to the real SDK/client; (b) an autouse,
   session-scoped fixture monkeypatches `socket.socket.connect`
   to raise on any address outside `{localhost, 127.0.0.1, ::1}`
   — this is the backstop that fires even if a future test forgets
   to use a mock fixture. Confirmed via the passing suite (which
   only reaches local Postgres/Redis) that the guard doesn't
   interfere with legitimate local connections.

4. Why the real Alembic chain instead of `Base.metadata.create_all()`:
   `create_all()` builds tables straight from the current ORM model
   definitions — it can't fail the way a real migration can, and it
   would silently paper over any migration that's broken, out of
   order, or diverges from what the models say (a real risk here:
   this codebase already has a categories-table migration with
   seed-data INSERTs, S5-02's FK backfill/rename, etc. — behavior
   that only exists in migration files, not in the models). Running
   `alembic upgrade head` for real means every test run is also,
   for free, an end-to-end test that the full migration chain
   applies cleanly from empty — something TESTER.md and the ticket
   both note had never been verified before this ticket. The
   tradeoff is slower test-session startup (one full migrate per
   run) versus `create_all()`'s near-instant schema build; correctness
   of the thing actually deployed was judged more important than
   startup speed for a session-scoped fixture that only pays that
   cost once per run.

COVERAGE NOTE: all five acceptance criteria are met and verified
live (not structurally-only), so no docs/verification_debt.md
entry is needed for this ticket.

Ready for S5-04 whenever you confirm this one.
