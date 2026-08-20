"""FastAPI entry point. Run with: uvicorn app.main:app --reload (from /backend).

S1-01 wired up the skeleton (CORS, /health). S1-02 added /api/transactions.
S1-03 adds /api/statistics.
"""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .db import engine
from .eb_service import EnableBankingAuthError, EnableBankingError
from .rate_limit import limiter
from .routers import (
    analysis,
    auth,
    budgets,
    categories,
    chat,
    insights,
    jobs,
    settings,
    statistics,
    transactions,
    user_auth,
)
from .sync_lock import SyncAlreadyRunningError

# S4-09 Item 3 surfaced this: without any handler configured, Python's root
# logger only emits WARNING and above (its built-in "handler of last
# resort") — every logger.info() call anywhere in this app (registry.py's
# provider-cache hit/miss, tasks/analysis.py's sync summary) was silently
# dropped for this process. celery_worker doesn't have this problem — its
# `--loglevel=info` CLI flag already configures the root logger for that
# process. INFO only, never DEBUG: CLAUDE.md reserves DEBUG for anything
# that could carry transaction amounts/descriptions, and INFO must stay
# safe to leave on in production.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

app = FastAPI(title="KBC Analyzer API")
app.state.limiter = limiter

# The Vite dev server runs on a different origin (port) than the API, so the
# browser needs an explicit CORS allowance during local development.
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
    # S6-03: the session cookie only ever gets attached to a cross-origin
    # fetch (frontend :5173 -> backend :8000) if the browser is told both
    # sides allow it — this flag on the server side, `credentials:
    # "include"` on the client side (lib/api.ts). Safe alongside a single
    # explicit allow_origins entry (never "*", per CLAUDE.md) — the browser
    # itself refuses to honor allow_credentials with a wildcard origin.
    allow_credentials=True,
)

app.include_router(transactions.router)
app.include_router(statistics.router)
app.include_router(auth.router)
app.include_router(user_auth.router)
app.include_router(settings.router)
app.include_router(analysis.router)
app.include_router(categories.router)
app.include_router(jobs.router)
app.include_router(insights.router)
app.include_router(budgets.router)
app.include_router(chat.router)


# Currently unreachable — S4-02 moved the Enable Banking fetch into the background
# job, so no live route raises this synchronously today. Kept registered because
# Sprint 6's web-based bank authorization (see Sprint 5→6 handoff) will likely add
# a route that does. Flagged as dead code in S5-04's review; PM decision: keep,
# documented, 2026-08.
@app.exception_handler(EnableBankingAuthError)
async def eb_auth_error_handler(request: Request, exc: EnableBankingAuthError) -> JSONResponse:
    # No valid cached session — this is a client-fixable problem (re-authorize), not a
    # server crash, so it maps to 401 rather than 500.
    return JSONResponse(status_code=401, content={"message": str(exc)})


@app.exception_handler(EnableBankingError)
async def eb_error_handler(request: Request, exc: EnableBankingError) -> JSONResponse:
    # Enable Banking itself rejected or failed the request — we're a client of a
    # remote service that misbehaved, hence 502 (bad gateway) rather than 500.
    return JSONResponse(status_code=502, content={"message": str(exc)})


@app.exception_handler(SyncAlreadyRunningError)
async def sync_already_running_handler(request: Request, exc: SyncAlreadyRunningError) -> JSONResponse:
    # 409 Conflict: the request is well-formed but can't proceed against the
    # server's current state (a sync is already in flight) — distinct from a
    # 400 (bad request) or 401/403 (auth). job_id lets the frontend attach to
    # the existing job's polling instead of just showing an error.
    return JSONResponse(
        status_code=409,
        content={"message": str(exc), "job_id": exc.in_flight_job_id},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # S5-07: 429 Too Many Requests — the request is otherwise valid, it's
    # just arriving faster than the endpoint's limit allows. exc.detail is
    # slowapi's own "N per M" description of the limit that was hit.
    return JSONResponse(
        status_code=429,
        content={"message": f"Rate limit exceeded ({exc.detail}). Please try again shortly."},
    )


@app.exception_handler(OperationalError)
async def db_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"message": "Database unavailable. Please try again shortly."},
    )


@app.get("/health")
def health() -> dict:
    """Basic liveness + DB connectivity check used to verify docker-compose wiring."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
