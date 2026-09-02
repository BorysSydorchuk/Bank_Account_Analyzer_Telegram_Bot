"""S10-03 — POST /api/transactions/sync must never leave the sync lock and
job record stuck at "processing" when the Celery enqueue itself fails (e.g.
the broker is briefly unreachable). Uses the real `sync_lock`/`job_store`
Redis client (see conftest.py's TEST_REDIS_URL, db 15) — only `run_sync_job
.delay` itself is faked, since simulating a genuinely down broker from a
test process would mean tearing down infrastructure other tests share.
"""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import kombu.exceptions

from app import job_store, sync_lock
from app.models import User


def _make_verified_user(db_session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash", email_verified=True)
    db_session.add(user)
    db_session.commit()
    return user


def _login_session_cookie(db_session, email: str) -> tuple[User, dict]:
    from app.auth.session import SESSION_COOKIE_NAME, create_session

    user = _make_verified_user(db_session, email)
    session_id = create_session(user.id)
    return user, {SESSION_COOKIE_NAME: session_id}


def _sync_body() -> dict:
    today = date.today()
    return {"date_from": (today - timedelta(days=7)).isoformat(), "date_to": today.isoformat()}


def test_enqueue_success_leaves_lock_held_and_job_processing(client, db_session):
    """Regression: the normal path must be unaffected by the new try/except."""
    user, cookies = _login_session_cookie(db_session, f"{uuid.uuid4()}@example.com")
    client.cookies.update(cookies)

    with patch("app.routers.transactions.run_sync_job.delay") as fake_delay:
        response = client.post("/api/transactions/sync", json=_sync_body())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    job_id = body["job_id"]
    fake_delay.assert_called_once()

    assert sync_lock.get_holder(user.id) == job_id
    job = job_store.get_job(job_id)
    assert job["status"] == "processing"

    sync_lock.release(job_id, user.id)


def test_broker_unreachable_during_enqueue_releases_lock_and_fails_job_immediately(client, db_session):
    """Adversarial: simulates the broker being unreachable at enqueue time
    with the real exception type Celery/Kombu raises for that condition —
    the acceptance test is that this failure is handled synchronously, in
    this request, not that nothing could ever go wrong finding out."""
    user, cookies = _login_session_cookie(db_session, f"{uuid.uuid4()}@example.com")
    client.cookies.update(cookies)

    with patch(
        "app.routers.transactions.run_sync_job.delay",
        side_effect=kombu.exceptions.OperationalError("Error 111 connecting to redis:6379. Connection refused."),
    ) as fake_delay:
        response = client.post("/api/transactions/sync", json=_sync_body())

    assert response.status_code == 503
    assert "try again" in response.json()["detail"].lower()

    # The job_id passed to the failed .delay() call is the same one this
    # request generated internally — recovered from the mock's own call
    # args, since a 503 response never carries it.
    job_id = fake_delay.call_args[0][0]

    job = job_store.get_job(job_id)
    assert job["status"] == "failed"
    assert "try again" in job["error"].lower()

    # The lock must be free immediately — not sitting until LOCK_TTL_SECONDS
    # (11 minutes) expires on its own.
    assert sync_lock.get_holder(user.id) is None

    # Confirm the lock is truly gone, not just soon-to-expire, by
    # successfully re-acquiring it.
    new_job_id = str(uuid.uuid4())
    assert sync_lock.acquire(new_job_id, user.id) is True
    sync_lock.release(new_job_id, user.id)
