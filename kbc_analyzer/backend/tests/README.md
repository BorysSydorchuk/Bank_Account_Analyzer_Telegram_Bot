# backend/tests

## Prerequisites

- The dev Docker Compose stack running (`docker compose up -d` from the repo
  root) — tests reuse the already-running `db` and `redis` containers, on
  their host-published ports, rather than starting their own. They never
  touch the `kbc_analyzer` database inside that Postgres server; they create
  and drop a separate `kbc_analyzer_test` database of their own on the same
  server (see `tests/conftest.py` for the connection-string logic).
- Test dependencies installed: `pip install -e ".[test]"` from `backend/`
  (installs pytest, pytest-asyncio, httpx, freezegun on top of the app's own
  runtime dependencies, which the test suite also imports).

## Run everything

From `backend/`:

```
pytest
```

That's the one command — configuration lives in `pyproject.toml`
(`[tool.pytest.ini_options]`), so no extra flags are needed. `conftest.py`
creates the test database and runs the real Alembic chain against it once
per run (session-scoped), then tears it down when the run finishes.

## What each test gets

- `db_session` — a SQLAlchemy session inside a transaction that's always
  rolled back at the end of the test. Nothing a test writes is ever visible
  to another test.
- `client` — a FastAPI `TestClient` with the `get_db` dependency overridden
  to that same `db_session`.
- `seeded_categories` — the 7 categories the `fbde2dbcc78d` migration seeds
  (Restaurants and Cafes, Groceries, Traveling, Rent/Housing, Income,
  Transfers, Other), fetched from the database rather than duplicated here.
- `transaction_factory` / `budget_factory` / `insight_factory` — builder
  functions for the three tables tests create rows in most often. Data is
  invented but realistic (Belgian merchants, EUR amounts) — never real bank
  data.
- `fake_llm_provider` — a `FakeLLMProvider` implementing the real
  `LLMProvider` interface with canned, configurable responses.
- `mock_enable_banking_client` — patches `app.eb_service.EnableBankingClient`
  so any `EnableBankingService()` built during the test gets a
  `FakeEnableBankingClient` instead of a real one.
- Celery tasks run eagerly and inline (`task_always_eager`, set once per
  session) — no worker process, no real broker.
- A dedicated Redis logical database (index 15, on the same local Redis
  container) backs `app.job_store`, isolated from the dev app's indexes 0/1.

None of this reaches a live external service — see "No live external calls"
in the S5-03 delivery report for how that's enforced, not just intended.

## Determinism

`freezegun` is installed for any test whose behavior depends on "today"
(budget month boundaries, session-expiry checks) — decorate or wrap with
`freezegun.freeze_time("2026-08-18")` as needed. No test relies on
`sleep()` for synchronization, and no test depends on another test's
ordering or side effects (`db_session`'s rollback is what makes that true).
