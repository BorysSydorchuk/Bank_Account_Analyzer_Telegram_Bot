"""A fake SES client (TESTER.md prime directive 3: no live external calls,
ever) — patches app.email_service's _ses_client factory, not
send_templated_email itself, so real template rendering and the real
send_email call shape are still exercised. Autouse (S7-09): register()
and request_password_reset() send real email unconditionally on every
call, so every test needs this patched, not just the ones specifically
about email.
"""
import pytest


class FakeSesClient:
    def __init__(self):
        self.sent: list[dict] = []

    def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "fake-message-id"}


@pytest.fixture(autouse=True)
def _fake_ses_client(monkeypatch):
    fake = FakeSesClient()
    monkeypatch.setattr("app.email_service._ses_client", lambda: fake)
    return fake
