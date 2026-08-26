"""Transactional email via AWS SES (S7-08) — sends S7-09's verification and
password-reset links. No SDK client, no API key: boto3's SES client picks up
credentials automatically from the ECS task's IAM role (infra/ses.tf's
ecs_task_send_email policy), the same way every AWS SDK call anywhere in this
sprint's infra tooling has worked — nothing here is hardcoded, and there is
no secret to rotate or leak, unlike a plain SMTP username/password would be.

Two templates only, matching what S7-09 needs — plain HTML + a text
fallback, no templating engine dependency for two static strings with one
substitution each.
"""
import os
from functools import lru_cache

import boto3

__all__ = ["send_templated_email", "UnknownEmailTemplateError"]


class UnknownEmailTemplateError(Exception):
    """Raised for a template_name send_templated_email doesn't recognize."""


def _render_verify_email(link: str) -> tuple[str, str, str]:
    subject = "Verify your Mymble email address"
    html = (
        "<p>Welcome to Mymble.</p>"
        f'<p><a href="{link}">Click here to verify your email address</a>.</p>'
        "<p>If you didn't create a Mymble account, you can ignore this email.</p>"
    )
    text = f"Welcome to Mymble.\n\nVerify your email address: {link}\n\nIf you didn't create a Mymble account, you can ignore this email."
    return subject, html, text


def _render_password_reset(link: str) -> tuple[str, str, str]:
    subject = "Reset your Mymble password"
    html = (
        "<p>A password reset was requested for your Mymble account.</p>"
        f'<p><a href="{link}">Click here to reset your password</a>. This link expires soon.</p>'
        "<p>If you didn't request this, you can ignore this email — your password won't change.</p>"
    )
    text = (
        f"A password reset was requested for your Mymble account.\n\n"
        f"Reset your password: {link}\nThis link expires soon.\n\n"
        f"If you didn't request this, you can ignore this email — your password won't change."
    )
    return subject, html, text


# S7-09 will add real token-generation call sites; this map is the whole
# "template registry" — deliberately not a class hierarchy or a file-based
# template loader for two entries.
_TEMPLATES = {
    "verify_email": _render_verify_email,
    "password_reset": _render_password_reset,
}


@lru_cache(maxsize=1)
def _ses_client():
    return boto3.client("ses", region_name=os.environ["AWS_REGION"])


def send_templated_email(to_email: str, template_name: str, **template_vars) -> None:
    """Send one of the templates in _TEMPLATES to to_email, substituting
    template_vars into it. Raises UnknownEmailTemplateError for an unknown
    template_name (a 400-shaped caller error, not a template author's typo
    surfacing as an unhandled 500) and whatever boto3's ClientError is for a
    real SES failure — callers decide how to handle/log that themselves,
    same as every other external-API boundary in this codebase.
    """
    render = _TEMPLATES.get(template_name)
    if render is None:
        raise UnknownEmailTemplateError(
            f"Unknown email template: {template_name!r}. Known templates: {sorted(_TEMPLATES)}"
        )
    subject, html_body, text_body = render(**template_vars)

    _ses_client().send_email(
        Source=os.environ["SES_SENDER_EMAIL"],
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": text_body, "Charset": "UTF-8"},
            },
        },
    )
