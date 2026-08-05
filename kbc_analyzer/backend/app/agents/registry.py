"""Resolves the currently-configured LLM provider. Every agent gets its provider
through get_provider() — nothing instantiates GeminiProvider/ClaudeProvider
directly, so switching providers in Settings changes behavior everywhere at once.
"""
from sqlalchemy.orm import Session

from .. import settings_service
from .providers.base import LLMProvider
from .providers.claude import ClaudeProvider
from .providers.gemini import GeminiProvider

__all__ = ["ProviderNotConfiguredError", "get_provider"]


class ProviderNotConfiguredError(Exception):
    """The selected provider's API key hasn't been set in Settings yet."""


def get_provider(db: Session) -> LLMProvider:
    settings = settings_service.get_settings(db)
    provider_name = settings["llm_provider"]
    api_key = settings_service.get_decrypted_api_key(db, provider_name)

    if not api_key:
        raise ProviderNotConfiguredError(
            f"No API key configured for {provider_name}. Add one in Settings before running analysis."
        )

    if provider_name == "gemini":
        return GeminiProvider(api_key)
    if provider_name == "claude":
        return ClaudeProvider(api_key)
    raise ProviderNotConfiguredError(f"Unknown provider: {provider_name!r}")
