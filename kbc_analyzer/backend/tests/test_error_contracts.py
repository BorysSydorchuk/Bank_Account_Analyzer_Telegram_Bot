"""S5-04 — error contract invariant, and the S3-06 regression (the frontend
had one parser that needed to read both {"message": ...} and {"detail": ...}
error shapes — this proves both shapes are genuinely, currently produced by
the live API, which is the backend half of that bug; the parser itself is
frontend code with no test harness yet, see delivery notes).

401 note: EnableBankingAuthError's handler (app/main.py) is exercised here by
calling it directly rather than through a live route. As of S4-02, the only
place that raises EnableBankingAuthError (EnableBankingService.get_account_uids,
called from tasks/analysis.py) now catches it itself and writes a job status
instead of letting it reach FastAPI's exception-handling layer — so no
current route actually returns a 401 through this handler. The handler is
still registered and still correct, but it's presently unreachable from any
endpoint; flagged to the PM as a stale-premise finding in delivery notes.
"""
import pytest
from fastapi import Request
from sqlalchemy.exc import OperationalError

from app.eb_service import EnableBankingAuthError
from app.main import db_error_handler, eb_auth_error_handler


def _fake_request() -> Request:
    return Request(scope={"type": "http", "headers": []})


@pytest.mark.asyncio
async def test_expired_bank_session_maps_to_401_with_a_message_field():
    response = await eb_auth_error_handler(_fake_request(), EnableBankingAuthError("session expired"))

    assert response.status_code == 401
    assert response.body
    import json

    body = json.loads(response.body)
    assert "message" in body
    assert body["message"] == "session expired"


@pytest.mark.asyncio
async def test_database_unavailable_maps_to_503_with_a_message_field_handler():
    response = await db_error_handler(_fake_request(), OperationalError("statement", {}, Exception("connection refused")))

    assert response.status_code == 503
    import json

    body = json.loads(response.body)
    assert body == {"message": "Database unavailable. Please try again shortly."}


def test_database_unavailable_maps_to_503_through_a_live_route(client, monkeypatch):
    """Unlike the 401 case, this one IS reachable live: GET /health calls
    engine.connect() directly, so breaking that call end-to-end proves the
    whole registered-handler wiring, not just the handler function alone."""
    from app import main

    class _BrokenEngine:
        def connect(self):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(main, "engine", _BrokenEngine())

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"message": "Database unavailable. Please try again shortly."}


def test_both_message_and_detail_error_shapes_are_genuinely_live_S3_06_regression(client, test_user):
    """The custom exception handlers (401/502/503) always emit {"message":
    ...}. But routes that raise a bare FastAPI HTTPException — like PATCH
    /api/transactions/{id} with an unknown category — get FastAPI's own
    default handler, which emits {"detail": ...}. Both shapes coexist in the
    live API today; a frontend parser that only reads one of them silently
    swallows the other's error message (the S3-06 bug). This pins the
    {"detail": ...} half of that fact so it can't quietly change shape
    without a test noticing.
    """
    from uuid import uuid4

    from app.auth.session import SESSION_COOKIE_NAME, create_session

    client.cookies.set(SESSION_COOKIE_NAME, create_session(test_user.id))
    response = client.patch(f"/api/transactions/{uuid4()}", json={"category": "Not A Real Category"})

    assert response.status_code == 400
    body = response.json()
    assert "detail" in body
    assert "message" not in body
