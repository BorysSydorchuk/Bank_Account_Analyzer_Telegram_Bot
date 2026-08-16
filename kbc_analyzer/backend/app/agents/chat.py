"""The chat agent (S4-06): answers freeform questions grounded in the user's
real transaction data. Unlike the other agents, this yields incrementally
rather than returning one structured result — the endpoint forwards each
chunk to the client as an SSE frame instead of waiting for the full reply.
"""
from typing import AsyncGenerator

from .base import BaseAgent

SYSTEM_PROMPT_TEMPLATE = """You are a personal finance assistant with access to the user's real bank transaction data. Answer concisely and specifically — always reference actual amounts, dates, and merchant names from the data.

Today's date: {today}
Data available from: {earliest_date} to {latest_date}

SPENDING SUMMARY (last 90 days):
{summary}

RECENT TRANSACTIONS (last 20):
{transactions}

ACTIVE BUDGETS:
{budgets}

Rules:
- If the answer requires data outside what's provided, say so — never invent transactions or amounts
- Under 150 words unless the user asks for detail
- Format amounts in Belgian locale, e.g. € 1.234,56 (period for thousands, comma for decimals)"""


class ChatAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "chat"

    def _build_system_prompt(self, context: dict) -> str:
        """context: assembled by chat_service.build_context() — must contain
        today, earliest_date, latest_date, summary_text, transactions_text,
        budgets_text (all pre-formatted strings, already grounded in the
        real database — this method only arranges them into the prompt)."""
        return SYSTEM_PROMPT_TEMPLATE.format(
            today=context["today"],
            earliest_date=context["earliest_date"],
            latest_date=context["latest_date"],
            summary=context["summary_text"],
            transactions=context["transactions_text"],
            budgets=context["budgets_text"],
        )

    async def stream(self, message: str, history: list[dict], context: dict) -> AsyncGenerator[str, None]:
        """message: the user's latest question. history: prior turns for this
        session, oldest first, [{"role": "user"|"assistant", "content": ...}] —
        truncation to a maximum length is the caller's responsibility
        (chat_service), not this method's. context: see _build_system_prompt.
        """
        system_prompt = self._build_system_prompt(context)
        messages = [*history, {"role": "user", "content": message}]
        async for chunk in self.provider.stream_complete(system_prompt, messages):
            yield chunk

    async def run(self, **kwargs) -> dict:
        """Non-streaming form required by BaseAgent's abstract contract —
        collects stream() into one string. The SSE endpoint calls stream()
        directly for real-time output and never uses this."""
        return {"response": "".join([chunk async for chunk in self.stream(**kwargs)])}
