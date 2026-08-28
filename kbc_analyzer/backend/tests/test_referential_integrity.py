"""S5-04 — referential integrity invariant (S5-02). Two independent layers,
tested independently as the ticket asks: the FK itself (the last line of
defense at the database) and analysis_service's pre-write filter (what
actually stops that FK from ever firing in normal operation).
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app import crud
from app.analysis_service import categorize_transactions
from tests.fixtures.fake_llm_provider import FakeLLMProvider


def test_fk_rejects_an_unknown_category_at_the_db_level(db_session, transaction_factory):
    row = transaction_factory(category=None)
    db_session.add(row)
    db_session.flush()

    row.category = "Not A Real Category"
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.asyncio
async def test_categorization_pre_write_filter_excludes_unknown_categories_before_any_write(
    db_session, test_user, transaction_factory, monkeypatch
):
    """The agent can only hallucinate a category name because nothing forces
    its LLM output to match the fixed CATEGORIES list — this is exactly that
    failure mode, simulated by a fake provider returning a name that isn't
    in the categories table at all. If the filter weren't there, this write
    would hit the FK IntegrityError proven above and fail the whole batch
    (crud.update_transaction_categories has no per-row error handling)."""
    row = transaction_factory(category=None, manually_edited=False)
    db_session.add(row)
    db_session.flush()

    hallucinated_category = "Miscellaneous Nonsense"
    assert hallucinated_category not in {c.name for c in crud.list_categories(db_session, test_user.id)}

    provider = FakeLLMProvider(json_response=[{"id": str(row.id), "category": hallucinated_category, "subcategory": None}])
    monkeypatch.setattr("app.analysis_service.get_provider", lambda db, user_id: provider)

    result = await categorize_transactions(db_session, test_user.id, on_batch_complete=None)

    db_session.refresh(row)
    assert row.category is None
    assert result["categorized"] == 0
    assert result["failed"] == 1
    # S8-09: every result rejected as an unknown category is now a real,
    # surfaced error — not silently None (which used to make
    # tasks/analysis.py fall back to a misleading "AI provider may be
    # temporarily unavailable" message for what's actually a missing-
    # categories problem, not a provider problem).
    assert result["error_message"] is not None
    assert hallucinated_category in result["error_message"]
