"""Claude implementation of LLMProvider, using the Anthropic SDK's async client."""
from anthropic import AsyncAnthropic

from .base import LLMProvider, parse_json_response

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = AsyncAnthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return "claude"

    async def complete(self, system: str, user: str) -> str:
        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    async def complete_json(self, system: str, user: str) -> dict:
        text = await self.complete(system, user)
        return parse_json_response(text)

    async def test_connection(self) -> None:
        # Anthropic has no key-only "ping" endpoint, so the cheapest real
        # check is the ticket's own suggestion: a real completion capped at
        # 1 output token — enough to prove the key is accepted, negligible
        # cost either way.
        await self._client.messages.create(
            model=MODEL,
            max_tokens=1,
            messages=[{"role": "user", "content": "Hi"}],
        )
