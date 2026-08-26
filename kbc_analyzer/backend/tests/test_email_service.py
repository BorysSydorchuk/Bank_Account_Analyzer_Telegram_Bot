"""S7-08 — app/email_service.py. TESTER.md prime directive 3 (no live
external calls, ever) applies here the same as Enable Banking: the boto3
SES client itself is monkeypatched, but template rendering and the real
substitution logic run for real.
"""
import os

import pytest

os.environ.setdefault("AWS_REGION", "eu-central-1")
os.environ.setdefault("SES_SENDER_EMAIL", "no-reply@mymble.be")

from app.email_service import UnknownEmailTemplateError, send_templated_email  # noqa: E402


class FakeSesClient:
    def __init__(self):
        self.sent: list[dict] = []

    def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "fake-message-id"}


@pytest.fixture
def fake_ses(monkeypatch):
    fake = FakeSesClient()
    monkeypatch.setattr("app.email_service._ses_client", lambda: fake)
    return fake


def test_verify_email_renders_real_link_no_placeholder_leftover(fake_ses):
    send_templated_email(
        "someone@example.com", "verify_email", link="https://mymble.be/verify-email?token=real-token-abc"
    )

    assert len(fake_ses.sent) == 1
    call = fake_ses.sent[0]
    assert call["Source"] == "no-reply@mymble.be"
    assert call["Destination"] == {"ToAddresses": ["someone@example.com"]}
    html = call["Message"]["Body"]["Html"]["Data"]
    text = call["Message"]["Body"]["Text"]["Data"]
    assert "real-token-abc" in html
    assert "real-token-abc" in text
    # No unsubstituted placeholder syntax left in either body — the real
    # proof this is substitution, not a template string with a literal
    # "{link}" shipped by mistake.
    assert "{link}" not in html and "{link}" not in text
    assert "{{" not in html and "{{" not in text


def test_password_reset_renders_real_link_no_placeholder_leftover(fake_ses):
    send_templated_email(
        "someone@example.com", "password_reset", link="https://mymble.be/reset-password?token=real-token-xyz"
    )

    call = fake_ses.sent[0]
    html = call["Message"]["Body"]["Html"]["Data"]
    text = call["Message"]["Body"]["Text"]["Data"]
    assert "real-token-xyz" in html
    assert "real-token-xyz" in text
    assert "{link}" not in html and "{link}" not in text


def test_unknown_template_raises_a_clear_error_not_a_keyerror(fake_ses):
    with pytest.raises(UnknownEmailTemplateError) as exc_info:
        send_templated_email("someone@example.com", "does_not_exist", link="https://example.com")

    assert "does_not_exist" in str(exc_info.value)
    assert fake_ses.sent == []
