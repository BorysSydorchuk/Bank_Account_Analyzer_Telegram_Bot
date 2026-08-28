"""S8-07 — POST /api/feedback. Real Postgres/Redis, fake Resend (same
pattern as test_email_verification_and_password_reset.py).
"""
import os

from app.models import BetaInvite


def _register(client, db_session, email: str) -> None:
    db_session.add(BetaInvite(email=email.lower()))
    db_session.flush()
    response = client.post("/api/auth/register", json={"email": email, "password": "a-real-password-123"})
    assert response.status_code == 201, response.text


def test_feedback_requires_authentication(client):
    response = client.post("/api/feedback", json={"message": "Hello"})

    assert response.status_code == 401


def test_feedback_sends_an_email_with_sender_and_message(client, db_session, _fake_resend_client):
    _register(client, db_session, "feedbacksender@example.com")
    sent_before_feedback = len(_fake_resend_client.sent)  # registration itself sends a verify-email

    response = client.post("/api/feedback", json={"message": "The sync button did nothing for me."})

    assert response.status_code == 204, response.text
    assert len(_fake_resend_client.sent) == sent_before_feedback + 1
    sent = _fake_resend_client.sent[-1]
    assert sent["to"] == [os.environ["FEEDBACK_RECIPIENT_EMAIL"]]
    assert "feedbacksender@example.com" in sent["subject"]
    assert "The sync button did nothing for me." in sent["text"]
    assert "The sync button did nothing for me." in sent["html"]


def test_feedback_escapes_html_in_the_message(client, db_session, _fake_resend_client):
    _register(client, db_session, "htmltest@example.com")

    response = client.post("/api/feedback", json={"message": "<script>alert(1)</script>"})

    assert response.status_code == 204, response.text
    sent = _fake_resend_client.sent[-1]
    assert "<script>" not in sent["html"]
    assert "&lt;script&gt;" in sent["html"]


def test_feedback_rejects_an_empty_message(client, db_session):
    _register(client, db_session, "emptytest@example.com")

    response = client.post("/api/feedback", json={"message": ""})

    assert response.status_code == 422


def test_feedback_returns_a_clean_502_when_the_send_fails(client, db_session, monkeypatch):
    _register(client, db_session, "sendfails@example.com")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated Resend outage")

    monkeypatch.setattr("app.routers.feedback.send_templated_email", _boom)

    response = client.post("/api/feedback", json={"message": "Does this still work?"})

    assert response.status_code == 502
    assert "try again" in response.json()["message"].lower()
