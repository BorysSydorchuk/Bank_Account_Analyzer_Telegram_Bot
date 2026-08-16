"""Business logic for POST /api/chat (S4-06): assembles the financial context
injected into ChatAgent's system prompt, and does every synchronous step
(provider lookup, database reads) before streaming starts — so a missing API
key or a DB error is a normal JSON error response, never a broken SSE stream
the frontend has to parse mid-flight.
"""
from datetime import date, timedelta
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from . import crud
from .agents.chat import ChatAgent
from .agents.providers.base import LLMProvider
from .agents.registry import get_provider
from .statistics import compute_statistics

RECENT_TRANSACTIONS_LIMIT = 20
SUMMARY_WINDOW_DAYS = 90
MAX_HISTORY_MESSAGES = 20

# TODO(Sprint 6): pass the authenticated user's id through —
# crud.list_budgets_with_status already takes user_id as an explicit
# parameter (S4-05 pattern), so deferred until Sprint 6 auth exists to
# actually supply a real value; this sprint only has to change this one
# constant, not any function signature.
CURRENT_USER_ID = None


def _format_amount(value: float) -> str:
    """Belgian locale (period for thousands, comma for decimals) — matches
    the frontend's Intl.NumberFormat('de-BE') used everywhere else in the
    app, e.g. € 1.234,56."""
    return f"€ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _summary_text(db: Session, today: date) -> str:
    date_from = today - timedelta(days=SUMMARY_WINDOW_DAYS - 1)
    transactions = crud.list_transactions(db, date_from, today)
    stats = compute_statistics(transactions, date_from, today)
    summary = stats["summary"]
    if not stats["by_category"]:
        return "No spending recorded in the last 90 days."

    lines = [
        f"Total spent: {_format_amount(summary['total_spent'])}",
        f"Total received: {_format_amount(summary['total_received'])}",
        f"Net: {_format_amount(summary['net'])}",
    ]
    biggest = summary["biggest_expense"]
    if biggest is not None:
        lines.append(
            f"Biggest expense: {_format_amount(biggest['amount'])} at {biggest['description']} on {biggest['date']}"
        )
    lines += [f"- {cat['category']}: {_format_amount(cat['total'])} ({cat['percentage']}%)" for cat in stats["by_category"]]
    return "\n".join(lines)


def _transactions_text(db: Session) -> str:
    recent = crud.get_recent_transactions(db, RECENT_TRANSACTIONS_LIMIT)
    if not recent:
        return "No transactions on file yet."
    return "\n".join(
        f"{t.booking_date} | {t.description} | {_format_amount(float(t.amount))} | {t.category or 'Uncategorized'}"
        for t in recent
    )


def _budgets_text(db: Session) -> str:
    budgets = crud.list_budgets_with_status(db, CURRENT_USER_ID)
    if not budgets:
        return "No budgets set."
    return "\n".join(
        f"- {b['category']}: {_format_amount(b['spent_this_month'])} of {_format_amount(b['amount'])} "
        f"({b['percentage_used']}%, {b['status']})"
        for b in budgets
    )


def build_context(db: Session) -> dict:
    """Fresh financial context for one chat message — never cached, so every
    turn reflects the database as it is right now, not as it was when the
    conversation started."""
    today = date.today()
    date_range = crud.get_transaction_date_range(db)
    earliest, latest = date_range if date_range else (today, today)
    return {
        "today": today.isoformat(),
        "earliest_date": earliest.isoformat(),
        "latest_date": latest.isoformat(),
        "summary_text": _summary_text(db, today),
        "transactions_text": _transactions_text(db),
        "budgets_text": _budgets_text(db),
    }


def start_chat_stream(
    db: Session, message: str, history: list[dict]
) -> tuple[AsyncGenerator[str, None], LLMProvider]:
    """Resolves the configured provider and builds the financial context —
    both synchronous — then returns the agent's (not-yet-started) token
    stream together with the provider instance, so the router can read
    provider.last_usage once the stream is exhausted.

    Raises ProviderNotConfiguredError (from agents.registry) if no API key
    is set. Nothing here has started streaming yet when that happens.
    """
    provider = get_provider(db)
    context = build_context(db)
    truncated_history = history[-MAX_HISTORY_MESSAGES:]
    agent = ChatAgent(provider)
    return agent.stream(message, truncated_history, context), provider
