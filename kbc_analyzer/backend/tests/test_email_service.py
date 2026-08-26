"""S7-08 — app/email_service.py. TESTER.md prime directive 3 (no live
external calls, ever) applies here the same as Enable Banking: the boto3
SES client itself is monkeypatched (conftest.py's autouse
_fake_ses_client fixture, tests/fixtures/fake_ses.py), but template
rendering and the real substitution logic run for real.
"""
import pytest

from app.email_service import UnknownEmailTemplateError, send_templated_email


def test_verify_email_renders_real_link_no_placeholder_leftover(_fake_ses_client):
    send_templated_email(
        "someone@example.com", "verify_email", link="https://mymble.be/verify-email?token=real-token-abc"
    )

    assert len(_fake_ses_client.sent) == 1
    call = _fake_ses_client.sent[0]
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


def test_password_reset_renders_real_link_no_placeholder_leftover(_fake_ses_client):
    send_templated_email(
        "someone@example.com", "password_reset", link="https://mymble.be/reset-password?token=real-token-xyz"
    )

    call = _fake_ses_client.sent[0]
    html = call["Message"]["Body"]["Html"]["Data"]
    text = call["Message"]["Body"]["Text"]["Data"]
    assert "real-token-xyz" in html
    assert "real-token-xyz" in text
    assert "{link}" not in html and "{link}" not in text


def test_unknown_template_raises_a_clear_error_not_a_keyerror(_fake_ses_client):
    with pytest.raises(UnknownEmailTemplateError) as exc_info:
        send_templated_email("someone@example.com", "does_not_exist", link="https://example.com")

    assert "does_not_exist" in str(exc_info.value)
    assert _fake_ses_client.sent == []
