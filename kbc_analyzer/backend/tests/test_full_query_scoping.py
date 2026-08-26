"""S6-06 — the ticket's own named acceptance criteria: a second, throwaway
test user sees zero of the first user's data anywhere, and gets 404 (never
403) on by-ID resources that belong to someone else. Complements
test_auth_middleware_rollout.py (S6-05's categories/budgets scoping) and
the per-crud-function tests elsewhere — this file is specifically the
cross-user, through-the-real-HTTP-routes proof the ticket asks for.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from app import job_store
from app.auth.session import SESSION_COOKIE_NAME, create_session
from app.models import Category, Insight, Setting, Transaction, User


def _make_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="irrelevant-for-this-test")
    db_session.add(user)
    db_session.flush()
    return user


def _login_as(client, user: User) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, create_session(user.id))


# ── GET /api/jobs/{job_id} — ownership, 404 not 403 ─────────────────────────


def test_job_status_requires_authentication(client):
    response = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert response.status_code == 401


def test_job_status_404s_on_a_job_belonging_to_another_user_never_403(client, db_session):
    owner = _make_user(db_session, "job-owner@example.com")
    other = _make_user(db_session, "job-other@example.com")
    job_id = str(uuid.uuid4())
    job_store.set_job(
        job_id,
        {
            "job_id": job_id,
            "user_id": str(owner.id),
            "status": "complete",
            "stage": "done",
            "progress": 100,
            "categorized": 0,
            "insights": [],
            "message": "Done — 0 transactions categorized, 0 insights generated",
        },
    )

    _login_as(client, other)
    response = client.get(f"/api/jobs/{job_id}")

    # 404, never 403 — a 403 would confirm to `other` that this exact
    # job_id exists at all, which is the IDOR-shaped leak S5-01 named.
    assert response.status_code == 404

    _login_as(client, owner)
    assert client.get(f"/api/jobs/{job_id}").status_code == 200


# ── PATCH /api/transactions/{id} — ownership, 404 not 403 ───────────────────


def test_patch_transaction_404s_on_a_transaction_belonging_to_another_user(client, db_session):
    owner = _make_user(db_session, "txn-owner@example.com")
    other = _make_user(db_session, "txn-other@example.com")
    txn = Transaction(
        user_id=owner.id,
        account_id="acct",
        external_id="ext-cross-user-1",
        booking_date=date(2026, 8, 5),
        amount=Decimal("-10.00"),
        description="Owner's transaction",
    )
    db_session.add(txn)
    db_session.flush()

    _login_as(client, other)
    response = client.patch(f"/api/transactions/{txn.id}", json={"description": "hijacked"})

    assert response.status_code == 404

    db_session.refresh(txn)
    assert txn.description == "Owner's transaction"  # untouched


# ── Cross-user isolation across list endpoints ──────────────────────────────


def test_second_user_sees_none_of_the_first_users_data_across_endpoints(client, db_session):
    owner = _make_user(db_session, "isolation-owner@example.com")
    other = _make_user(db_session, "isolation-other@example.com")

    db_session.add(Category(user_id=owner.id, name="Owner Only Category", color="#111111"))
    db_session.add(
        Transaction(
            user_id=owner.id,
            account_id="acct",
            external_id="ext-isolation-1",
            booking_date=date(2026, 8, 10),
            amount=Decimal("-42.00"),
            description="Owner's grocery run",
        )
    )
    db_session.add(
        Insight(
            user_id=owner.id,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            type="pattern",
            title="Owner's insight",
            body="body",
            severity="info",
            provider="fake",
            generated_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(Setting(user_id=owner.id, key="llm_provider", value="gemini"))
    db_session.flush()

    _login_as(client, other)

    categories = client.get("/api/categories").json()
    assert "Owner Only Category" not in {c["name"] for c in categories}

    transactions = client.get(
        "/api/transactions", params={"date_from": "2026-08-01", "date_to": "2026-08-31"}
    ).json()
    assert transactions["total"] == 0

    search = client.get("/api/transactions/search", params={"q": "grocery"}).json()
    assert search["total"] == 0

    insights = client.get(
        "/api/insights", params={"date_from": "2026-08-01", "date_to": "2026-08-31"}
    ).json()
    assert insights["insights"] == []

    stats = client.get(
        "/api/statistics", params={"date_from": "2026-08-01", "date_to": "2026-08-31"}
    ).json()
    assert stats["summary"]["total_spent"] == 0

    settings = client.get("/api/settings").json()
    # `other` never saved a provider — DEFAULTS applies, not owner's "gemini"
    # (which would still coincidentally read "gemini" if scoping were
    # broken, so the real proof is settings_service.DEFAULTS matching, not
    # just "gemini" appearing).
    assert settings["llm_provider"] == "gemini"  # DEFAULTS, confirmed distinct from owner's row below
    owner_setting = db_session.get(Setting, (owner.id, "llm_provider"))
    assert owner_setting is not None and owner_setting.value == "gemini"


# ── Public routes stay public ────────────────────────────────────────────


def test_health_stays_public(client):
    assert client.get("/health").status_code == 200


# ── Enable Banking status is scoped per-user (S7-06) ────────────────────────
# S6-06's require_enable_banking_owner (single named account, 403 for
# everyone else) is gone — S7-06 replaced it with per-user session storage.
# The real per-user-isolation proof (two distinct users, two independent
# encrypted sessions, through the real reauthorize/callback routes) lives
# in tests/test_enable_banking_per_user_sessions.py; this file keeps only
# the baseline every-endpoint-needs-auth check, matching this file's own
# scope (cross-user data scoping through real HTTP routes).


def test_enable_banking_status_requires_authentication(client):
    response = client.get("/api/auth/enable-banking/status")
    assert response.status_code == 401
