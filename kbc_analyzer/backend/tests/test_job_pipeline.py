"""S5-04 — job state transition invariant: fetching -> storing ->
categorizing -> generating_insights -> done, and a failure at each stage
writing status=failed with a message naming the correct stage.

Uses raw_db (see conftest.py), not db_session: app/tasks/analysis.py's
_run() is a Celery task, not a FastAPI route — it opens its own
SessionLocal() rather than accepting one through dependency injection, so
db_session's rollback-on-teardown session is invisible to it. Fixture data
for these tests has to be written (and cleaned up) for real.
"""
import json
import uuid
from datetime import date
from typing import AsyncGenerator

import pytest

from app import job_store
from app.agents.providers.base import LLMProvider
from app.models import Transaction
from app.tasks.analysis import _run


class _OrchestrationFakeProvider(LLMProvider):
    """Unlike tests/fixtures/fake_llm_provider.py's FakeLLMProvider (one
    fixed response for every call), a full sync pipeline run makes three
    *different-shaped* complete_json calls in sequence — categorization,
    color assignment, insights — through the same provider instance. This
    dispatches on which agent's system prompt is asking, local to this file
    since nothing else needs it.

    category_by_id overrides the category for specific transaction ids (used
    when a test needs a known id categorized a specific way); every other id
    in the batch — including ones this fake was never told about, since a
    real sync's transaction ids aren't known until after the storing stage —
    falls back to default_category, extracted straight out of the batch JSON
    CategorizationAgent embeds in its user message.
    """

    def __init__(self, category_by_id: dict[str, str] | None = None, default_category: str = "Other"):
        self._category_by_id = category_by_id or {}
        self._default_category = default_category

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, system: str, user: str) -> str:
        return ""

    async def complete_json(self, system: str, user: str) -> list | dict:
        if "categorizer" in system:
            # user is "Classify these transactions:\n<json array>\n\nReturn: ..."
            # — the trailing "Return: ..." instruction also contains a
            # literal {"id": "...", ...} example, so the batch has to be
            # parsed as JSON rather than regex-matched for "id" (a naive
            # regex would pick up that placeholder "..." as a fourth id).
            batch_json = user.split("Classify these transactions:\n", 1)[1].split("\n\n", 1)[0]
            batch = json.loads(batch_json)
            return [
                {
                    "id": t["id"],
                    "category": self._category_by_id.get(t["id"], self._default_category),
                    "subcategory": None,
                }
                for t in batch
            ]
        if "color designer" in system:
            return []  # every category falls back to its existing seed color
        if "finance analyst" in system:
            return [{"type": "pattern", "title": "Steady spending", "body": "Nothing unusual this period.", "severity": "info"}]
        raise AssertionError(f"unexpected system prompt in orchestration test: {system[:60]!r}")

    async def stream_complete(self, system: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        yield ""

    async def test_connection(self) -> None:
        pass


def _raw_tx(external_id: str, amount: str = "-12.34", description: str = "Delhaize Ixelles") -> dict:
    return {"id": external_id, "date": "2026-08-05", "amount": amount, "description": description}


@pytest.fixture
def connected_kbc_session(raw_db, raw_db_user, mock_enable_banking_client):
    """S8-01: _run() now looks up which institutions a user has actually
    connected via EnableBankingService.connected_institutions — a real
    enable_banking_sessions query — before fetching from any of them, so
    the fake client's always-valid session alone (mock_enable_banking_client)
    is no longer enough to make _run() proceed past 'fetching'. Writes a
    real row directly (Fernet-encrypt + insert, no HTTP call) rather than
    going through the real OAuth exchange, keeping TESTER.md's "no live
    bank calls, ever" intact.
    """
    from datetime import datetime, timedelta

    from app.eb_session_store import DatabaseSessionStore

    DatabaseSessionStore(raw_db, raw_db_user.id, "KBC").save(
        {
            "session_id": "test-kbc-session",
            "account_uids": ["test-kbc-account-uid"],
            "valid_until": (datetime.now() + timedelta(days=90)).isoformat(),
        }
    )
    return mock_enable_banking_client


def _stage_sequence(monkeypatch) -> list[str]:
    """Records every stage `_run()` reports, in order, by wrapping the real
    job_store.set_job — the only way to observe the transition sequence
    itself, since job_store only ever holds the latest status."""
    stages: list[str] = []
    original_set_job = job_store.set_job

    def _recording_set_job(job_id: str, status: dict) -> None:
        stages.append(status.get("stage"))
        original_set_job(job_id, status)

    monkeypatch.setattr("app.tasks.analysis.job_store.set_job", _recording_set_job)
    return stages


@pytest.mark.asyncio
async def test_happy_path_transitions_through_every_stage_in_order(
    raw_db, raw_db_user, mock_enable_banking_client, connected_kbc_session, monkeypatch
):
    mock_enable_banking_client.set_transactions([_raw_tx("ext-job-001")])
    job_id = str(uuid.uuid4())

    provider = _OrchestrationFakeProvider()
    monkeypatch.setattr("app.analysis_service.get_provider", lambda db, user_id: provider)
    stages = _stage_sequence(monkeypatch)

    await _run(job_id, date(2026, 8, 1), date(2026, 8, 31), raw_db_user.id)

    # Not asserting exact call count (categorizing reports once per batch),
    # just that these five stages appear, in this relative order.
    seen_in_order = list(dict.fromkeys(stages))
    assert seen_in_order == ["fetching", "storing", "categorizing", "generating_insights", "done"]

    final = job_store.get_job(job_id)
    assert final["status"] == "complete"
    assert final["stage"] == "done"
    assert final["user_id"] == str(raw_db_user.id)

    stored_row = raw_db.query(Transaction).filter(Transaction.external_id == "ext-job-001").one()
    assert stored_row.category == "Other"
    assert stored_row.user_id == raw_db_user.id


@pytest.mark.asyncio
async def test_categorization_result_is_actually_written(
    raw_db, raw_db_user, mock_enable_banking_client, connected_kbc_session, monkeypatch
):
    """Pre-seeds a transaction directly (equivalent to what a prior sync
    already stored) rather than round-tripping it through this run's own
    fetch/store stages — the fake provider needs the transaction's real id
    to answer with, which only exists once a row has been committed.
    """
    tx = Transaction(
        user_id=raw_db_user.id,
        account_id="a", external_id="ext-job-002", booking_date=date(2026, 8, 5),
        amount=-12.34, currency="EUR", description="Delhaize Ixelles",
    )
    raw_db.add(tx)
    raw_db.commit()

    provider = _OrchestrationFakeProvider({str(tx.id): "Groceries"})
    monkeypatch.setattr("app.analysis_service.get_provider", lambda db, user_id: provider)
    mock_enable_banking_client.set_transactions([])  # nothing new to fetch this run

    job_id = str(uuid.uuid4())
    await _run(job_id, date(2026, 8, 1), date(2026, 8, 31), raw_db_user.id)

    raw_db.refresh(tx)
    assert tx.category == "Groceries"
    assert job_store.get_job(job_id)["status"] == "complete"


@pytest.mark.asyncio
async def test_fetching_stage_failure_reports_failed_status_naming_that_stage(
    raw_db, raw_db_user, mock_enable_banking_client
):
    mock_enable_banking_client.expire_session()
    job_id = str(uuid.uuid4())

    await _run(job_id, date(2026, 8, 1), date(2026, 8, 31), raw_db_user.id)

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["stage"] == "fetching"
    assert job["error"]


@pytest.mark.asyncio
async def test_storing_stage_failure_reports_failed_status_naming_that_stage(
    raw_db, raw_db_user, mock_enable_banking_client, connected_kbc_session, monkeypatch
):
    mock_enable_banking_client.set_transactions([_raw_tx("ext-job-003")])
    job_id = str(uuid.uuid4())

    def _broken_upsert(db, user_id, account_id, txs):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr("app.tasks.analysis.crud.upsert_transactions", _broken_upsert)

    await _run(job_id, date(2026, 8, 1), date(2026, 8, 31), raw_db_user.id)

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["stage"] == "storing"
    # Never the raw exception text (CLAUDE.md: no stack traces to the API consumer).
    assert "simulated storage failure" not in job["error"]


@pytest.mark.asyncio
async def test_categorizing_stage_failure_when_no_provider_configured_reports_failed_status(
    raw_db, raw_db_user, mock_enable_banking_client, connected_kbc_session
):
    """No monkeypatch of get_provider here — the point is the real,
    unconfigured-by-default state (no API key ever saved in the test
    database) genuinely fails categorize_transactions on its own."""
    mock_enable_banking_client.set_transactions([_raw_tx("ext-job-004")])
    job_id = str(uuid.uuid4())

    await _run(job_id, date(2026, 8, 1), date(2026, 8, 31), raw_db_user.id)

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["stage"] == "categorizing"
    assert "API key" in job["error"]


@pytest.mark.asyncio
async def test_generating_insights_stage_failure_reports_failed_status_naming_that_stage(
    raw_db, raw_db_user, mock_enable_banking_client, connected_kbc_session, monkeypatch
):
    mock_enable_banking_client.set_transactions([])  # nothing to categorize -> categorizing succeeds trivially
    provider = _OrchestrationFakeProvider({})
    monkeypatch.setattr("app.analysis_service.get_provider", lambda db, user_id: provider)

    async def _broken_generate_insights(db, user_id, date_from, date_to):
        raise RuntimeError("simulated insight generation crash")

    monkeypatch.setattr("app.tasks.analysis.analysis_service.generate_insights", _broken_generate_insights)

    job_id = str(uuid.uuid4())
    await _run(job_id, date(2026, 8, 1), date(2026, 8, 31), raw_db_user.id)

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert job["stage"] == "generating_insights"
    assert "simulated insight generation crash" not in job["error"]
