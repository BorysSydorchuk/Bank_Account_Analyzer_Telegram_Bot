"""Gemini implementation of LLMProvider.

Uses the `google-genai` SDK (the current unified Google SDK — `from google import
genai`), not the older `google-generativeai` package the ticket named by habit.
kbc_analyzer/analysis.py (the existing CLI) already depends on google-genai for
the exact same job, so this reuses that dependency instead of adding a second,
redundant Google SDK for no benefit.
"""
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
