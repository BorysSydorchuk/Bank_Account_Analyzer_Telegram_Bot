"""Resolves the currently-configured LLM provider. Every agent gets its provider
through get_provider() — nothing instantiates GeminiProvider/ClaudeProvider
directly, so switching providers in Settings changes behavior everywhere at once.
"""
import logging

from sqlalchemy.orm import Session

from .. import settings_service
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

__all__ = ["ProviderNotConfiguredError", "get_provider", "invalidate_provider_cache"]


class ProviderNotConfiguredError(Exception):
    """The selected provider's API key hasn't been set in Settings yet."""


# S4-09 Item 3: one provider instance per name, reused across requests
# instead of re-authenticating a fresh SDK client on every call. Keyed on
# provider name, not on the API key value — routers/settings.py calls
# invalidate_provider_cache() after ANY successful PATCH /api/settings, not
# just an llm_provider switch, because editing a key in place (same
# provider name, new key) would otherwise keep serving a cached instance
# built from the old key.
_provider_cache: dict[str, LLMProvider] = {}


def invalidate_provider_cache() -> None:
    """Drops every cached provider instance — call after any Settings
    change that could affect what get_provider() should return next."""
    _provider_cache.clear()


def get_provider(db: Session) -> LLMProvider:
    settings = settings_service.get_settings(db)
    provider_name = settings["llm_provider"]

    cached = _provider_cache.get(provider_name)
    if cached is not None:
        logger.info("Provider cache hit for %r", provider_name)
        return cached

    api_key = settings_service.get_decrypted_api_key(db, provider_name)
    if not api_key:
        raise ProviderNotConfiguredError(
            f"No API key configured for {provider_name}. Add one in Settings before running analysis."
        )

    if provider_name == "gemini":
        provider: LLMProvider = GeminiProvider(api_key)
    elif provider_name == "claude":
        provider = ClaudeProvider(api_key)
    else:
        raise ProviderNotConfiguredError(f"Unknown provider: {provider_name!r}")

    _provider_cache[provider_name] = provider
    logger.info("Provider cache miss for %r — created a new instance", provider_name)
    return provider
