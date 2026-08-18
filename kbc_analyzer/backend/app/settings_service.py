"""Business logic for the settings table: defaults, masking, and the
encrypt-on-write / never-decrypt-for-display rule for API keys.

get_decrypted_api_key() is the one exception to "never decrypt" — used only by
the LLM provider registry (S2-04) to actually call the configured provider,
never by anything that returns a response to the frontend.
"""
from sqlalchemy.orm import Session

from . import crud
from .crypto import decrypt, encrypt

__all__ = ["InvalidSettingError", "get_settings", "patch_setting", "get_decrypted_api_key"]

API_KEY_FIELDS = {"gemini_api_key", "anthropic_api_key"}
VALID_PROVIDERS = {"gemini", "claude"}

# The settings field is named after the vendor (Anthropic); the provider name
# used everywhere else in code (llm_provider's value, registry.py's branch,
# ClaudeProvider) is named after the model family (Claude) — a deliberate
# distinction, not an inconsistency, so get_decrypted_api_key needs an
# explicit map rather than assuming f"{provider}_api_key" (S5-06: that
# assumption was silently wrong for Claude since S2-04 — "claude_api_key"
# was never a real field — and nothing surfaced it until a real
# ANTHROPIC_API_KEY finally existed to exercise this path).
API_KEY_FIELD_BY_PROVIDER = {"gemini": "gemini_api_key", "claude": "anthropic_api_key"}

# Fixed-length mask regardless of real key length, so the response never leaks
# even how long the stored secret is.
MASK = "••••••••"

DEFAULTS = {
    "llm_provider": "gemini",
    "gemini_api_key": "",
    "anthropic_api_key": "",
}


class InvalidSettingError(Exception):
    """A PATCH request's key or value isn't valid — a 400, not a 500."""


def _mask_if_key(key: str, value: str) -> str:
    if key in API_KEY_FIELDS:
        return MASK if value else ""
    return value


def get_settings(db: Session) -> dict:
    stored = crud.get_all_settings(db)
    merged = {**DEFAULTS, **stored}
    return {key: _mask_if_key(key, value) for key, value in merged.items() if key in DEFAULTS}


def patch_setting(db: Session, key: str, value: str) -> dict:
    if key == "llm_provider" and value not in VALID_PROVIDERS:
        raise InvalidSettingError(f"llm_provider must be one of {sorted(VALID_PROVIDERS)}, got {value!r}")

    stored_value = encrypt(value) if key in API_KEY_FIELDS else value
    crud.upsert_setting(db, key, stored_value)
    return {"key": key, "value": _mask_if_key(key, value)}


def get_decrypted_api_key(db: Session, provider: str) -> str:
    """Return the real, usable API key for a provider ("gemini" or "claude").
    Empty string if none is saved yet.
    """
    stored = crud.get_all_settings(db).get(API_KEY_FIELD_BY_PROVIDER[provider], "")
    return decrypt(stored)
