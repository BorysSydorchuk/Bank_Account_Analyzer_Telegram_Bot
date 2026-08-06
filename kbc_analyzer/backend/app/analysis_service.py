"""Orchestrates the categorization and insight agents against the database —
shared by the standalone POST /api/analysis/* endpoints and the automatic
steps at the end of POST /api/transactions/sync, so both go through the exact
same logic instead of copies that could drift.
"""
import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from . import crud
from .agents.categorization import CategorizationAgent
from .agents.insight import InsightAgent
from .agents.registry import ProviderNotConfiguredError, get_provider
from .settings_service import get_settings
from .statistics import compute_statistics

logger = logging.getLogger(__name__)


async def categorize_transactions(
    db: Session, date_from: date | None = None, date_to: date | None = None
) -> dict:
    """Returns {categorized, skipped_already_categorized, failed, provider,
    error_message}. error_message is only set when categorization couldn't run
    at all (no API key configured) — a per-batch LLM failure instead shows up
    as a nonzero `failed` count with error_message left as None, since sync
    should still report success in that case.
    """
    provider_name = get_settings(db)["llm_provider"]
    skipped = crud.count_categorized_transactions(db, date_from, date_to)
    uncategorized = crud.get_uncategorized_transactions(db, date_from, date_to)

    if not uncategorized:
        return {
            "categorized": 0,
            "skipped_already_categorized": skipped,
            "failed": 0,
            "provider": provider_name,
            "error_message": None,
        }

    try:
        provider = get_provider(db)
    except ProviderNotConfiguredError as exc:
        logger.warning("Categorization skipped: %s", exc)
        return {
            "categorized": 0,
            "skipped_already_categorized": skipped,
            "failed": len(uncategorized),
            "provider": provider_name,
            "error_message": str(exc),
        }

    payloads = [
        {
            "id": str(t.id),
            "description": t.description,
            "amount": float(t.amount),
            "booking_date": t.booking_date.isoformat() if t.booking_date else None,
        }
        for t in uncategorized
    ]

    agent = CategorizationAgent(provider)
    results = await agent.run(payloads)

    if results:
        crud.update_transaction_categories(db, results)

    return {
        "categorized": len(results),
        "skipped_already_categorized": skipped,
        "failed": len(uncategorized) - len(results),
        "provider": provider_name,
        "error_message": None,
    }


async def generate_insights(db: Session, date_from: date, date_to: date) -> dict:
    """Returns {insights, provider, generated_at, error_message}. Unlike
    categorization, a single failed LLM call has no partial result to fall
    back on, so `insights` is simply empty and error_message explains why —
    the caller (sync) still succeeds regardless.
    """
    provider_name = get_settings(db)["llm_provider"]
    generated_at = datetime.now(timezone.utc)

    try:
        provider = get_provider(db)
    except ProviderNotConfiguredError as exc:
        logger.warning("Insight generation skipped: %s", exc)
        return {"insights": [], "provider": provider_name, "generated_at": generated_at, "error_message": str(exc)}

    transactions = crud.list_transactions(db, date_from, date_to)
    statistics = compute_statistics(transactions, date_from, date_to)

    agent = InsightAgent(provider)
    try:
        insights = await agent.run(statistics)
    except Exception:
        logger.exception("Insight generation failed")
        return {
            "insights": [],
            "provider": provider_name,
            "generated_at": generated_at,
            "error_message": "Could not generate insights right now.",
        }

    return {"insights": insights, "provider": provider_name, "generated_at": generated_at, "error_message": None}
