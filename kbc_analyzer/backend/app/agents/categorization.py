"""The first real agent (S2-05): classifies transactions into a fixed category
list by sending them to the configured LLM in batches.
"""
import json
import logging
import math
from typing import Callable

from .base import BaseAgent

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Restaurants and Cafes",
    "Groceries",
    "Traveling",
    "Rent/Housing",
    "Income",
    "Transfers",
    "Other",
]

SUBCATEGORIES_OF_OTHER = [
    "Entertainment",
    "Health",
    "Shopping",
    "Utilities & Bills",
    "Rest",
    "Subscriptions",
]

SUBCATEGORIES_OF_TRAVELING = ["Transport", "Housing", "Food", "Entertainment"]

SYSTEM_PROMPT = f"""You are a financial transaction categorizer. Classify each transaction using EXACTLY these categories:
{json.dumps(CATEGORIES)}
For "Other" use a subcategory from: {json.dumps(SUBCATEGORIES_OF_OTHER)}
For "Traveling" use a subcategory from: {json.dumps(SUBCATEGORIES_OF_TRAVELING)}
For all other categories set subcategory to null.
Rules:
- Negative amounts are money spent
- Positive amounts are income or transfers
- Return ONLY a JSON array, no prose, no markdown
- Every transaction in input must appear in output"""


class CategorizationAgent(BaseAgent):
    # Transactions per LLM call. Large enough that a typical sync (tens to low
    # hundreds of transactions) takes only a handful of calls; small enough that
    # one call's response stays well inside normal output-token limits.
    BATCH_SIZE = 50

    @property
    def name(self) -> str:
        return "categorization"

    async def run(
        self, transactions: list[dict], on_batch_complete: Callable[[int, int], None] | None = None
    ) -> list[dict]:
        """transactions: [{id, description, amount, booking_date}, ...].
        on_batch_complete: optional callback invoked after every batch (whether
        it succeeded or was skipped) with (completed_batches, total_batches) —
        S3-04's background job uses this to report real progress instead of a
        timed guess.

        Returns [{id, category, subcategory}, ...] — only for transactions whose
        batch actually succeeded. Batches run sequentially, not concurrently, to
        stay under the provider's rate limit; a batch that raises is logged and
        skipped rather than failing the whole run, since partial categorization
        beats none.
        """
        results: list[dict] = []
        total_batches = math.ceil(len(transactions) / self.BATCH_SIZE) if transactions else 0
        for batch_number, i in enumerate(range(0, len(transactions), self.BATCH_SIZE), start=1):
            batch = transactions[i : i + self.BATCH_SIZE]
            try:
                results.extend(await self._classify_batch(batch))
            except Exception:
                logger.exception("Categorization batch of %d transactions failed", len(batch))
            if on_batch_complete:
                on_batch_complete(batch_number, total_batches)
        return results

    async def _classify_batch(self, batch: list[dict]) -> list[dict]:
        user_message = (
            "Classify these transactions:\n"
            f"{json.dumps(batch, default=str)}\n\n"
            'Return: [{"id": "...", "category": "...", "subcategory": "..."}]'
        )
        result = await self.provider.complete_json(SYSTEM_PROMPT, user_message)
        if not isinstance(result, list):
            raise ValueError(f"Expected a JSON array from the LLM, got {type(result).__name__}")
        return result
