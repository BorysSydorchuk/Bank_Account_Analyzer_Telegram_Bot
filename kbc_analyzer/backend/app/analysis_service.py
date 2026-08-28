"""Orchestrates the categorization and insight agents against the database —
shared by the standalone POST /api/analysis/* endpoints and the automatic
steps at the end of POST /api/transactions/sync, so both go through the exact
same logic instead of copies that could drift.
"""
import logging
from datetime import date, datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from . import crud
from .agents.categorization import CategorizationAgent
from .agents.color_assignment import ColorAssignmentAgent
from .agents.insight import InsightAgent
from .agents.providers.base import LLMProvider
from .agents.registry import ProviderNotConfiguredError, get_provider
from .colors import BACKUP_PALETTE, validate_color
from .settings_service import get_settings
from .statistics import compute_statistics
from .usage_limits import try_record_usage

logger = logging.getLogger(__name__)


async def categorize_transactions(
    db: Session,
    user_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    on_batch_complete: Callable[[int, int], None] | None = None,
) -> dict:
    """Returns {categorized, skipped_already_categorized, failed, provider,
    error_message}. error_message is set for two distinct hard-stop cases:
    no API key configured, or every returned classification rejected because
    none of the categories the LLM used exist in this account yet (S8-09) —
    a real, actionable cause, not a transient provider issue. A genuine
    per-batch LLM failure (the call itself raised) instead shows up as a
    nonzero `failed` count with error_message left as None, since sync
    should still report success in that case.

    on_batch_complete: forwarded to CategorizationAgent.run() — S3-04's
    background job passes this to report real per-batch progress; the
    standalone POST /api/analysis/categorize endpoint has no progress UI to
    feed, so it just omits it.
    """
    provider_name = get_settings(db, user_id)["llm_provider"]
    skipped = crud.count_categorized_transactions(db, user_id, date_from, date_to)
    uncategorized = crud.get_uncategorized_transactions(db, user_id, date_from, date_to)
    # Categories still on their S3-01 seed color — checked on every run, not
    # just when there are new transactions to categorize, so a category
    # already in use gets a real AI color even on a sync where nothing new
    # came in to categorize.
    seeded_category_names = crud.list_seeded_category_names(db, user_id)

    if not uncategorized and not seeded_category_names:
        return {
            "categorized": 0,
            "skipped_already_categorized": skipped,
            "failed": 0,
            "provider": provider_name,
            "error_message": None,
        }

    try:
        provider = get_provider(db, user_id)
    except ProviderNotConfiguredError as exc:
        logger.warning("Categorization skipped: %s", exc)
        return {
            "categorized": 0,
            "skipped_already_categorized": skipped,
            "failed": len(uncategorized),
            "provider": provider_name,
            "error_message": str(exc),
        }

    # S8-04: checked here, not before the provider lookup — a categorize
    # call with nothing to do (the early return above) or no provider
    # configured never reaches the LLM, so it shouldn't cost a cap slot.
    cap_message = try_record_usage(db, user_id, "categorize")
    if cap_message:
        return {
            "categorized": 0,
            "skipped_already_categorized": skipped,
            "failed": len(uncategorized),
            "provider": provider_name,
            "error_message": cap_message,
        }

    results: list[dict] = []
    unknown_category_names: set[str] = set()
    if uncategorized:
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
        raw_results = await agent.run(payloads, on_batch_complete=on_batch_complete)

        if raw_results:
            # S5-02: transactions.category is now FK'd to categories.name, so a
            # category the LLM invents (drifts off the fixed CATEGORIES list, a
            # typo, a provider hallucination) can no longer be written at all —
            # the FK would reject the whole statement. Filtering here, before
            # the write, keeps that one bad row from taking out the rest of the
            # batch's otherwise-valid results; it's treated the same as any
            # other per-transaction categorization failure (counted in `failed`
            # below), not a reason to fail the run.
            known_category_names = {c.name for c in crud.list_categories(db, user_id)}
            unknown = [r for r in raw_results if r.get("category") not in known_category_names]
            if unknown:
                unknown_category_names = {r.get("category") for r in unknown}
                logger.warning(
                    "Categorization agent returned %d unknown category name(s) not in "
                    "categories table, skipping: %s",
                    len(unknown),
                    sorted(unknown_category_names),
                )
            results = [r for r in raw_results if r.get("category") in known_category_names]

        if results:
            crud.update_transaction_categories(db, user_id, results)

    if seeded_category_names:
        await assign_ai_colors(db, user_id, provider, seeded_category_names)

    error_message = None
    if unknown_category_names and not results:
        # S8-09: found live — the LLM can answer correctly (real 200s, real
        # valid category names) while this account's own categories table
        # is the actual gap, and the S5-02 filter above silently discarded
        # every result as a result. That used to leave error_message None
        # here, so tasks/analysis.py's generic "AI provider may be
        # temporarily unavailable" fallback fired instead — technically
        # not silent, but actively wrong: retrying does nothing, since the
        # cause isn't the provider. Distinguished from a genuine LLM/
        # provider failure (raw_results itself empty, unknown_category_names
        # never populated) by construction — this branch only reaches when
        # the agent's calls succeeded and the app's own data was the block.
        error_message = (
            "The AI suggested categories that don't exist in your account yet "
            f"({', '.join(sorted(unknown_category_names))}). This usually means "
            "your account is missing its default categories — please contact "
            "support."
        )

    return {
        "categorized": len(results),
        "skipped_already_categorized": skipped,
        "failed": len(uncategorized) - len(results),
        "provider": provider_name,
        "error_message": error_message,
    }


async def assign_ai_colors(db: Session, user_id: UUID, provider: LLMProvider, category_names: list[str]) -> None:
    """Runs the S3-02 color-assignment prompt for category_names (all still on
    their S3-01 seed color) and persists the result with source='ai'.

    A color that fails colors.validate_color() never reaches the database:
    it falls back to the category's own existing seed color when one exists,
    or the next unused color in colors.BACKUP_PALETTE for a category with no
    prior row at all. A failure of the LLM call itself is logged and
    swallowed — like insight generation, this is a nice-to-have on top of a
    successful sync, not something that should fail it.
    """
    existing_by_name = crud.get_categories_by_name(db, user_id, category_names)

    agent = ColorAssignmentAgent(provider)
    try:
        assignments = await agent.run(category_names)
    except Exception:
        logger.exception("AI color assignment failed for categories: %s", category_names)
        return

    assigned_color_by_name = {
        a["name"]: a["color"] for a in assignments if isinstance(a, dict) and a.get("name") and a.get("color")
    }

    colors_by_name: dict[str, str] = {}
    next_backup_index = 0
    for name in category_names:
        color = assigned_color_by_name.get(name)
        if color and validate_color(color):
            colors_by_name[name] = color
            continue

        if color:
            logger.warning("AI color %r for category %r failed validation, falling back", color, name)

        existing_row = existing_by_name.get(name)
        if existing_row is not None:
            colors_by_name[name] = existing_row.color
        else:
            colors_by_name[name] = BACKUP_PALETTE[next_backup_index % len(BACKUP_PALETTE)]
            next_backup_index += 1

    crud.upsert_category_colors(db, user_id, colors_by_name, source="ai")


async def generate_insights(db: Session, user_id: UUID, date_from: date, date_to: date) -> dict:
    """Returns {insights, provider, generated_at, error_message}. Unlike
    categorization, a single failed LLM call has no partial result to fall
    back on, so `insights` is simply empty and error_message explains why —
    the caller (sync) still succeeds regardless.
    """
    provider_name = get_settings(db, user_id)["llm_provider"]
    generated_at = datetime.now(timezone.utc)

    try:
        provider = get_provider(db, user_id)
    except ProviderNotConfiguredError as exc:
        logger.warning("Insight generation skipped: %s", exc)
        return {"insights": [], "provider": provider_name, "generated_at": generated_at, "error_message": str(exc)}

    cap_message = try_record_usage(db, user_id, "insights")
    if cap_message:
        return {"insights": [], "provider": provider_name, "generated_at": generated_at, "error_message": cap_message}

    transactions = crud.list_transactions(db, user_id, date_from, date_to)
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
