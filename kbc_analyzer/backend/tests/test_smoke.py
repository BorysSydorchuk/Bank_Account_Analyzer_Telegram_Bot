"""S5-03 — proof the test harness itself works. No application behavior is
asserted here beyond "the plumbing is connected"; behavior tests start in
S5-04.
"""
import pytest

from app.models import Transaction


def test_health_endpoint_reachable_through_client_fixture(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_db_session_writes_and_reads_a_transaction(db_session, transaction_factory):
    txn = transaction_factory(description="Delhaize Ixelles")
    db_session.add(txn)
    db_session.flush()

    fetched = db_session.get(Transaction, txn.id)

    assert fetched is not None
    assert fetched.description == "Delhaize Ixelles"
    assert fetched.currency == "EUR"


@pytest.mark.asyncio
async def test_fake_llm_provider_returns_canned_responses(fake_llm_provider):
    text_response = await fake_llm_provider.complete("system prompt", "user prompt")
    json_response = await fake_llm_provider.complete_json("system prompt", "user prompt")
    tokens = [chunk async for chunk in fake_llm_provider.stream_complete("system", [{"role": "user", "content": "hi"}])]

    assert text_response == "This is a fake completion."
    assert json_response == {"result": "ok"}
    assert tokens == ["Hel", "lo", "!"]
    assert len(fake_llm_provider.calls) == 3
