"""Resolves the currently-configured LLM provider. Every agent gets its provider
through get_provider() — nothing instantiates GeminiProvider/ClaudeProvider
directly, so switching providers in Settings changes behavior everywhere at once.
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from .. import settings_service
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

__all__ = ["ProviderNotConfiguredError", "get_provider", "invalidate_provider_cache"]


class ProviderNotConfiguredError(Exception):
    """The selected provider's API key hasn't been set in Settings yet."""


# S4-09 Item 3: one provider instance per (user, provider name), reused
# across requests instead of re-authenticating a fresh SDK client on every
# call. Keyed on user_id too as of S6-02 — settings (and so API keys) are
# per-user, so a cache keyed on provider name alone would let the first
# user to call a given provider's API key serve every other user's
# requests. user_id is required as of S6-06 — every call site now has a
# real authenticated user to pass.
# routers/settings.py calls invalidate_provider_cache() after ANY
# successful PATCH /api/settings, not just an llm_provider switch, because
# editing a key in place (same provider name, new key) would otherwise
# keep serving a cached instance built from the old key.
_provider_cache: dict[tuple[UUID, str], LLMProvider] = {}


def invalidate_provider_cache() -> None:
    """Drops every cached provider instance — call after any Settings
    change that could affect what get_provider() should return next."""
    _provider_cache.clear()


def get_provider(db: Session, user_id: UUID) -> LLMProvider:
    settings = settings_service.get_settings(db, user_id)
    provider_name = settings["llm_provider"]
    cache_key = (user_id, provider_name)

    cached = _provider_cache.get(cache_key)
    if cached is not None:
        logger.info("Provider cache hit for %r", provider_name)
        return cached

    api_key = settings_service.get_decrypted_api_key(db, user_id, provider_name)
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

    _provider_cache[cache_key] = provider
    logger.info("Provider cache miss for %r — created a new instance", provider_name)
    return provider
