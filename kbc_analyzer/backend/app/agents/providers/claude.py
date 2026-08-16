"""Claude implementation of LLMProvider, using the Anthropic SDK's async client."""
from typing import AsyncGenerator

from anthropic import AsyncAnthropic

from .base import LLMProvider, parse_json_response

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self.last_usage: dict[str, int] | None = None

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

    async def stream_complete(self, system: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        # NOTE: structurally implemented only — no live ANTHROPIC_API_KEY has
        # ever been available to run this against the real API (see
        # docs/verification_debt.md). Anthropic's roles are already
        # "user"/"assistant", so messages passes through unchanged.
        self.last_usage = None
        async with self._client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final_message = await stream.get_final_message()
            self.last_usage = {
                "input": final_message.usage.input_tokens,
                "output": final_message.usage.output_tokens,
            }

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
