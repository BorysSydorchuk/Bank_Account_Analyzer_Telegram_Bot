"""Orchestrates the categorization agent against the database — shared by the
standalone POST /api/analysis/categorize endpoint and the automatic
categorization step at the end of POST /api/transactions/sync, so both go
through the exact same logic instead of two copies that could drift.
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from . import crud
from .agents.categorization import CategorizationAgent
from .agents.registry import ProviderNotConfiguredError, get_provider
from .settings_service import get_settings

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
