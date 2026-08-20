"""Test infrastructure (S5-03) — env bootstrap, test-database lifecycle,
transactional db_session, TestClient, and the live-network guard.

Import order matters here: app/db.py builds its SQLAlchemy engine from
DATABASE_URL at *module import time*, not lazily inside a function. So every
env var below must be set before the first `import app.*` anywhere in the
test session — including pytest's own collection of other test files. That's
why this all happens at module level in conftest.py (which pytest always
imports before collecting anything else) rather than inside a fixture.
"""
import os
import socket
from pathlib import Path

from dotenv import load_dotenv

# ── 1. Resolve connection details from the repo-root .env ──────────────────
# .env's DATABASE_URL/REDIS_URL point at Docker Compose service hostnames
# ("db", "redis") that only resolve *inside* the compose network. Tests run
# on the host, so we don't use DATABASE_URL/REDIS_URL from .env directly —
# we reuse only the credentials/port and rebuild host-reachable URLs below.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
_POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
_POSTGRES_USER = os.getenv("POSTGRES_USER", "kbc")
_POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me_locally")
_POSTGRES_DEV_DB = os.getenv("POSTGRES_DB", "kbc_analyzer")

# Never the dev database: the test database is always the dev database's name
# with "_test" appended, so it can never collide even if someone changes
# POSTGRES_DB later. The assertions below are a hard guard, not a comment —
# if they ever fail, every fixture that depends on TEST_DATABASE_URL refuses
# to run rather than risk touching real data.
TEST_DB_NAME = f"{_POSTGRES_DEV_DB}_test"
TEST_DATABASE_URL = (
    f"postgresql+psycopg://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}"
    f"@{TEST_DB_HOST}:{_POSTGRES_PORT}/{TEST_DB_NAME}"
)
_MAINTENANCE_DATABASE_URL = (
    f"postgresql+psycopg://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}"
    f"@{TEST_DB_HOST}:{_POSTGRES_PORT}/postgres"
)
_DEV_DATABASE_URL = (
    f"postgresql+psycopg://{_POSTGRES_USER}:{_POSTGRES_PASSWORD}"
    f"@{TEST_DB_HOST}:{_POSTGRES_PORT}/{_POSTGRES_DEV_DB}"
)
assert TEST_DB_NAME.endswith("_test") and TEST_DB_NAME != _POSTGRES_DEV_DB, (
    "test database name must be derived from, and distinct from, the dev database name"
)
assert TEST_DATABASE_URL != _DEV_DATABASE_URL, (
    "refusing to run: test database URL resolved to the same URL as the dev database"
)

# Dedicated Redis logical database (index 15) on the same local Redis
# container the dev stack already runs — not fakeredis, so job_store's
# real redis.Redis client (module-level singleton, see app/job_store.py)
# is exercised as-is. Index 15 is never used by the dev app (job_store.py
# and celery_app.py both default to indexes 0/1), so it can never collide
# with real job data even if both stacks run at once.
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")

# ── 2. Point the app at test infrastructure BEFORE any app.* import ────────
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
# Celery: eager execution needs no real broker, so point it somewhere inert
# rather than the dev Redis instance — task_always_eager is set on the
# Celery app object itself below, once it's safe to import it.
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")
os.environ.setdefault("SETTINGS_SECRET", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
# Enable Banking: never real credentials. eb_service.EnableBankingService()
# constructs a real EnableBankingClient in __init__, which reads this path —
# the mock_enable_banking_client fixture (fixtures/fake_enable_banking.py)
# replaces the class before that constructor ever runs, but these still need
# to be syntactically present so unrelated imports don't KeyError.
os.environ.setdefault("ENABLEBANKING_APP_ID", "test-app-id")
os.environ.setdefault("ENABLEBANKING_PRIVATE_KEY_PATH", str(Path(__file__).parent / "fixtures" / "unused.pem"))
# Google OAuth (S6-03): never real credentials. app/google_oauth.py's
# build_authorize_url() reads these directly (no dependency-injection seam
# to override) — tests/test_google_oauth.py monkeypatches the actual
# outbound HTTP calls (exchange_code_for_tokens/fetch_userinfo), but
# building the initial redirect URL still needs a syntactically present
# client id, same reasoning as the Enable Banking values above.
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

pytest_plugins = [
    "tests.fixtures.factories",
    "tests.fixtures.fake_llm_provider",
    "tests.fixtures.fake_enable_banking",
]


# ── 3. Live-network guard ───────────────────────────────────────────────────
# Enforced, not just intended: any outbound socket connect() to a host other
# than localhost/127.0.0.1/::1 raises. This is what actually stops a test
# from reaching Enable Banking or a real Gemini/Claude endpoint even if a
# fixture is forgotten somewhere — mocking the boundary is the primary
# defense, this is the backstop. (psycopg's libpq and any C-level driver
# don't go through Python's socket module, so this doesn't interfere with
# the local Postgres/Redis connections tests legitimately make.)
_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
_real_connect = socket.socket.connect


def _guarded_connect(self, address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) else address
    if host not in _ALLOWED_HOSTS:
        raise RuntimeError(
            f"Blocked outbound network connection to {host!r}. Tests must never "
            "reach a live external service (Enable Banking, Gemini, Claude). Mock "
            "the boundary instead — see tests/fixtures/fake_llm_provider.py and "
            "tests/fixtures/fake_enable_banking.py."
        )
    return _real_connect(self, address, *args, **kwargs)


@pytest.fixture(autouse=True, scope="session")
def _block_live_network():
    socket.socket.connect = _guarded_connect
    yield
    socket.socket.connect = _real_connect


# ── 4. Celery eager mode ────────────────────────────────────────────────────
@pytest.fixture(autouse=True, scope="session")
def _celery_eager():
    from app.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    # Without this, an exception raised inside an eager task is swallowed
    # into the (never-checked) result object instead of propagating — a
    # test asserting sync failure behavior would see nothing happen.
    celery_app.conf.task_eager_propagates = True


# ── 5. Test database lifecycle (session-scoped) ─────────────────────────────
@pytest.fixture(scope="session")
def test_db_engine():
    """Creates a disposable Postgres database, runs the real Alembic chain
    against it, yields an engine bound to it, then drops it.

    Running the real migration chain (rather than Base.metadata.create_all())
    is deliberate — see backend/tests/README.md for why.
    """
    maintenance_engine = create_engine(_MAINTENANCE_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with maintenance_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    maintenance_engine.dispose()

    alembic_cfg = Config(str(_REPO_ROOT / "backend" / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_REPO_ROOT / "backend" / "app" / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()

    maintenance_engine = create_engine(_MAINTENANCE_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with maintenance_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
    maintenance_engine.dispose()


@pytest.fixture
def db_session(test_db_engine):
    """Function-scoped, transactional. Everything the test does — including
    application code that calls db.commit() (crud.py does, throughout) —
    happens inside one outer transaction on a dedicated connection, via a
    SAVEPOINT so inner commits don't end it, and that outer transaction is
    always rolled back. Two tests writing the "same" row never collide
    because neither write ever becomes visible outside its own test.
    """
    connection = test_db_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with the get_db dependency overridden to the
    test's transactional session, so requests made through it see (and roll
    back with) the same data as db_session.
    """
    from app.db import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# Mirrors app/migrations/versions/fbde2dbcc78d_add_categories_table.py's
# SEED_COLORS exactly — duplicated here (not imported) so this fixture keeps
# working even if that migration file is ever renamed, and so a test reading
# this file doesn't have to go find the migration to know what it resets to.
_CATEGORY_SEED_COLORS = {
    "Restaurants and Cafes": "#F97316",
    "Groceries": "#10B981",
    "Traveling": "#F59E0B",
    "Rent/Housing": "#6366F1",
    "Income": "#0EA5E9",
    "Transfers": "#8B5CF6",
    "Other": "#64748B",
}


@pytest.fixture
def raw_db(test_db_engine):
    """A SessionLocal()-backed session — real commits against the disposable
    test database, NOT wrapped in db_session's rollback-only SAVEPOINT.

    Only tests/test_job_pipeline.py needs this: app/tasks/analysis.py's
    _run() calls SessionLocal() directly (it's a Celery task, not a FastAPI
    route, so there's no `get_db` dependency for the `client` fixture to
    override) — on its own connection, outside whatever transaction
    db_session might be holding open. A test using db_session to set up data
    and then invoking _run() would see _run() unable to read that data at
    all (it's uncommitted on a different connection), so tests that exercise
    _run() must write their fixture data through this same kind of session
    instead.

    Because these writes are real, teardown must undo them explicitly rather
    than relying on rollback: every row in transactions/insights created
    during the test is deleted, and categories are reset to their seeded
    color/source so a test that triggers AI color assignment doesn't leave
    later tests (in this same session-scoped database) starting from a
    different state depending on run order.
    """
    from app.db import SessionLocal
    from app.models import Category, Insight, Transaction

    session = SessionLocal()
    yield session
    session.rollback()
    session.query(Transaction).delete()
    session.query(Insight).delete()
    session.query(Category).update({"source": "seed", "ai_color": None})
    for name, color in _CATEGORY_SEED_COLORS.items():
        session.query(Category).filter(Category.name == name).update({"color": color})
    session.commit()
    session.close()


@pytest.fixture
def seeded_categories(db_session):
    """The 7 categories are seeded by the Alembic migration itself
    (fbde2dbcc78d_add_categories_table.py), not re-inserted here — that
    migration already ran as part of test_db_engine, and its INSERTs were
    committed before any test transaction began, so they're visible in
    every test's transaction for free. This fixture just hands back the
    rows so tests don't have to know the seed values themselves.
    """
    from app.models import Category

    categories = db_session.query(Category).order_by(Category.name).all()
    assert len(categories) == 7, f"expected 7 seeded categories, found {len(categories)}"
    return categories
