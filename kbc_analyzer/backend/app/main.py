"""FastAPI entry point. Run with: uvicorn app.main:app --reload (from /backend).

Sprint 1 only wires up the skeleton: CORS for the Vite dev server and a /health
check that confirms the app can reach Postgres. Ticket S1-02 adds the real
/api/transactions endpoints; S1-03 adds /api/statistics.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .db import engine

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


@app.get("/health")
def health() -> dict:
    """Basic liveness + DB connectivity check used to verify docker-compose wiring."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}