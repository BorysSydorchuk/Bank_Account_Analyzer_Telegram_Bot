"""Shared date-range validation (S5-07) — CLAUDE.md mandates date_from <=
date_to and a 365-day maximum on every endpoint that takes a date range,
enforced with a 400 and a clear message. Only GET /api/insights/compare
(S4-08) enforced this until now; this module is the one source of truth
the other four date-range endpoints (and compare) all validate against, so
the rule can't drift between them again.
"""
from datetime import date

from fastapi import HTTPException

MAX_RANGE_DAYS = 365


class InvalidDateRangeError(Exception):
    """A date range fails CLAUDE.md's rules — a 400, not a 500."""


def validate_date_range(date_from: date, date_to: date, label: str = "date_from/date_to") -> None:
    """Raises InvalidDateRangeError if date_from is after date_to, or the
    range exceeds MAX_RANGE_DAYS. label distinguishes which range failed
    when a caller validates more than one (e.g. compare's period A/B)."""
    if date_from > date_to:
        raise InvalidDateRangeError(f"{label}: date_from must be before or equal to date_to.")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise InvalidDateRangeError(f"{label}: range cannot exceed {MAX_RANGE_DAYS} days.")


def require_valid_date_range(date_from: date, date_to: date) -> tuple[date, date]:
    """FastAPI dependency for endpoints whose date_from/date_to are query
    parameters — GET /api/statistics, GET /api/transactions, GET
    /api/insights. Converts InvalidDateRangeError into the standard 400 so
    every endpoint returns the same error shape without repeating the
    try/except at each call site.
    """
    try:
        validate_date_range(date_from, date_to)
    except InvalidDateRangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return date_from, date_to


def validate_date_range_body(date_from: date, date_to: date) -> None:
    """For endpoints where date_from/date_to arrive in a POST body (e.g.
    POST /api/transactions/sync) rather than as query parameters, so
    require_valid_date_range's Depends()-based query extraction doesn't
    apply — same validation, same 400 shape, called explicitly instead.
    """
    try:
        validate_date_range(date_from, date_to)
    except InvalidDateRangeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
