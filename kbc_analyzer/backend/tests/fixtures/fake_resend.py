"""A fake Resend client (TESTER.md prime directive 3: no live external calls,
ever) — patches resend.Emails.send directly (module-level function, not a
constructed client the way boto3's SES client was), so real template
rendering and the real send call shape are still exercised. Autouse (S7-09):
register() and request_password_reset() send real email unconditionally on
every call, so every test needs this patched, not just the ones specifically
about email.
"""
import pytest


class FakeResendClient:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, params: dict) -> dict:
        self.sent.append(params)
        return {"id": "fake-email-id"}


@pytest.fixture(autouse=True)
def _fake_resend_client(monkeypatch):
    fake = FakeResendClient()
    monkeypatch.setattr("app.email_service.resend.Emails.send", fake.send)
    return fake
