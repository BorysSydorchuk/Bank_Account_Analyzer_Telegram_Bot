"""Abstract LLM provider interface — Gemini and Claude both implement this so
every agent talks to "a provider," never to a specific vendor's SDK.
"""
import json
import re
from abc import ABC, abstractmethod

__all__ = ["LLMProvider", "parse_json_response"]


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Send a prompt, return the text response."""

    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict:
        """Send a prompt, return parsed JSON. Raises ValueError on invalid JSON."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging: 'gemini' or 'claude'."""


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def parse_json_response(text: str) -> dict:
    """Strip a markdown code fence if the model wrapped its JSON in one, then parse.

    Shared by both providers' complete_json() — LLMs asked for "JSON only" still
    sometimes wrap the answer in ```json ... ``` anyway, and both providers need
    to tolerate that the same way rather than each growing their own regex.
    """
    cleaned = text.strip()
    fence_match = _FENCE_RE.match(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {text[:200]!r}") from exc
