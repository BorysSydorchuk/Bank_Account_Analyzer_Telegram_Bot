"""The second agent (S2-06): turns a statistics snapshot into 5 narrative
insights. Unlike categorization, this isn't batched — one statistics object,
one LLM call, one JSON array back.
"""
import json

from .base import BaseAgent

SYSTEM_PROMPT = """You are a personal finance analyst. Analyze spending data and return exactly 5 insights as a JSON array.
Each insight must:
- Be specific: reference actual amounts, dates, merchants
- Be actionable or observational — not generic advice
- Be tagged with a type from: ["pattern", "anomaly", "saving", "rhythm", "category"]
- All amounts in the data are in EUR — write them with the € symbol (e.g. €47.00), never $ or USD
Focus on: daily/weekly rhythm, peak spending days, category trends, unusual transactions, one saving suggestion.
Return ONLY a JSON array, no prose, no markdown."""


class InsightAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "insight"

    async def run(self, statistics: dict) -> list[dict]:
        """statistics: the full object from GET /api/statistics (summary,
        by_category, by_day, by_week). Returns exactly 5
        {type, title, body, severity} dicts — or fewer if the LLM shorts the
        count; the caller doesn't second-guess the model's output further.
        """
        date_from = statistics["by_day"][0]["date"] if statistics["by_day"] else "unknown"
        date_to = statistics["by_day"][-1]["date"] if statistics["by_day"] else "unknown"

        user_message = (
            f"Here is the spending data for {date_from} to {date_to}:\n"
            f"{json.dumps(statistics, default=str)}\n\n"
            'Return: [{"type": "pattern|anomaly|saving|rhythm|category", '
            '"title": "Short headline (max 8 words)", '
            '"body": "Specific insight referencing real data (2-3 sentences)", '
            '"severity": "info|warning|positive"}]'
        )
        result = await self.provider.complete_json(SYSTEM_PROMPT, user_message)
        if not isinstance(result, list):
            raise ValueError(f"Expected a JSON array from the LLM, got {type(result).__name__}")
        return result
