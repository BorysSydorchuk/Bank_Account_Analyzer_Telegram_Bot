"""FastAPI entry point. Run with: uvicorn app.main:app --reload (from /backend).

S1-01 wired up the skeleton (CORS, /health). S1-02 added /api/transactions.
S1-03 adds /api/statistics.
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .db import engine
from .eb_service import EnableBankingAuthError, EnableBankingError
from .routers import analysis, auth, settings, statistics, transactions

app = FastAPI(title="KBC Analyzer API")

# The Vite dev server runs on a different origin (port) than the API, so the
# browser needs an explicit CORS allowance during local development.
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(statistics.router)
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(analysis.router)


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
