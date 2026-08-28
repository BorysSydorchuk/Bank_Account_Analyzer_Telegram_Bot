"""Transactional email via Resend (S8-05) — sends S7-09's verification and
password-reset links.

Was AWS SES (S7-08) — replaced because this AWS account's SES production
access request was denied and the follow-up Support Case went unanswered
past its own stated response window (real, not a guess: see
ARCHITECTURE.md's Auth section and docs/verification_debt.md's SES entry
for the full timeline), leaving sandbox mode permanently blocking any real
stranger's registration. Real research (S8-05) found Resend has no
new-account approval gate for transactional domain-verified sending, unlike
the two other real candidates checked — the actual reason this one, not a
coin flip. Real cost of the switch: SES's IAM-role auth needed zero stored
credentials; this needs a real API key (`RESEND_API_KEY`), stored in
Secrets Manager the same way every other app-level secret here already is
(GOOGLE_CLIENT_SECRET, the Enable Banking private key) — a genuine tradeoff,
not free.

Two templates only, matching what S7-09 needs — plain HTML + a text
fallback, no templating engine dependency for two static strings with one
substitution each.
"""
import os

import resend

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


def send_templated_email(to_email: str, template_name: str, **template_vars) -> None:
    """Send one of the templates in _TEMPLATES to to_email, substituting
    template_vars into it. Raises UnknownEmailTemplateError for an unknown
    template_name (a 400-shaped caller error, not a template author's typo
    surfacing as an unhandled 500) and whatever resend's own exception is
    for a real send failure — callers decide how to handle/log that
    themselves, same as every other external-API boundary in this codebase.
    """
    render = _TEMPLATES.get(template_name)
    if render is None:
        raise UnknownEmailTemplateError(
            f"Unknown email template: {template_name!r}. Known templates: {sorted(_TEMPLATES)}"
        )
    subject, html_body, text_body = render(**template_vars)

    # resend.api_key is a real, live secret — set once per process from the
    # env var (itself injected via Secrets Manager, never a literal here),
    # not cached in a client object the way _ses_client() used to be:
    # resend's SDK is a thin module-level wrapper, not a constructed client.
    resend.api_key = os.environ["RESEND_API_KEY"]
    resend.Emails.send(
        {
            "from": os.environ["EMAIL_SENDER_ADDRESS"],
            "to": [to_email],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }
    )
