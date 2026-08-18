"""A fake LLMProvider (TESTER.md prime directive 3: no live Gemini/Claude
calls, ever) returning canned, configurable responses instead of calling any
SDK. Implements the same abstract interface real providers do
(app/agents/providers/base.py), so anything written against
"a LLMProvider" — the whole point of that interface — accepts this instead.
"""
from typing import AsyncGenerator

import pytest

from app.agents.providers.base import LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(
        self,
        complete_response: str = "This is a fake completion.",
        json_response: dict | None = None,
        stream_tokens: list[str] | None = None,
    ):
        self.complete_response = complete_response
        self.json_response = json_response if json_response is not None else {"result": "ok"}
        self.stream_tokens = stream_tokens if stream_tokens is not None else ["Hel", "lo", "!"]
        self.last_usage: dict[str, int] | None = None
        self.calls: list[tuple[str, str, str]] = []  # (method, system, user_or_messages)

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, system: str, user: str) -> str:
        self.calls.append(("complete", system, user))
        return self.complete_response

    async def complete_json(self, system: str, user: str) -> dict:
        self.calls.append(("complete_json", system, user))
        return self.json_response

    async def stream_complete(self, system: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        self.calls.append(("stream_complete", system, str(messages)))
        self.last_usage = {"input": 10, "output": len(self.stream_tokens)}
        for token in self.stream_tokens:
            yield token

    async def test_connection(self) -> None:
        self.calls.append(("test_connection", "", ""))


@pytest.fixture
def fake_llm_provider():
    return FakeLLMProvider()
