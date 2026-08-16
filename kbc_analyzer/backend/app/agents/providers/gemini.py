"""Gemini implementation of LLMProvider.

Uses the `google-genai` SDK (the current unified Google SDK — `from google import
genai`), not the older `google-generativeai` package the ticket named by habit.
kbc_analyzer/analysis.py (the existing CLI) already depends on google-genai for
the exact same job, so this reuses that dependency instead of adding a second,
redundant Google SDK for no benefit.
"""
from typing import AsyncGenerator

from google import genai
from google.genai import types

from .base import LLMProvider, parse_json_response

# The ticket named "gemini-2.0-flash", but Google has since deprecated it (404
# NOT_FOUND, confirmed live while smoke-testing this file). kbc_analyzer/analysis.py
# already uses this "-latest" alias successfully for the same fast/cheap tier —
# reusing it here avoids pinning to another dated snapshot Google can retire next.
MODEL = "gemini-flash-latest"


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)
        self.last_usage: dict[str, int] | None = None

    @property
    def name(self) -> str:
        return "gemini"

    async def complete(self, system: str, user: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=MODEL,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return response.text

    async def complete_json(self, system: str, user: str) -> dict:
        text = await self.complete(system, user)
        return parse_json_response(text)

    async def stream_complete(self, system: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        # Gemini's roles are "user"/"model", not "user"/"assistant" — the only
        # translation needed, since our own history format otherwise matches
        # Anthropic's role names directly.
        contents = [
            types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]
        self.last_usage = None
        stream = await self._client.aio.models.generate_content_stream(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        async for chunk in stream:
            # usage_metadata's exact per-chunk timing isn't live-verified (see
            # docs/verification_debt.md) — the field exists on every chunk per
            # google-genai 2.18.1's types, and other streaming APIs report it
            # cumulatively, so keeping only the latest value read should end up
            # with the final total either way.
            if chunk.usage_metadata is not None:
                self.last_usage = {
                    "input": chunk.usage_metadata.prompt_token_count or 0,
                    "output": chunk.usage_metadata.candidates_token_count or 0,
                }
            if chunk.text:
                yield chunk.text

    async def test_connection(self) -> None:
        # Listing models is the cheapest authenticated call available — unlike
        # generate_content, it doesn't spend any generation quota, just
        # confirms the key itself is accepted. One item is enough; the pager
        # would otherwise walk the entire model catalog.
        pager = await self._client.aio.models.list()
        async for _ in pager:
            break
