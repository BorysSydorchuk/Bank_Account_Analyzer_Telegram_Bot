"""The third agent (S3-02): assigns a semantically meaningful, contrast-safe
hex color to a category name. Deliberately a separate prompt from
categorization (agents/categorization.py) — color design and transaction
classification are different cognitive tasks, and bundling them into one
prompt degrades quality on both.
"""
import json

from .base import BaseAgent

SYSTEM_PROMPT = """You are a UI color designer for a personal finance app. Assign a hex color to each spending category.

Semantic color families to follow:
  Food-related (Groceries, Restaurants, Cafes, Dining): greens (#16A34A range, avoid our success token exactly)
  Financial (Transfers, Income, Banking): blues (#2563EB range, avoid our primary token exactly)
  Travel (Traveling, Transport, Flights, Hotels): ambers and warm yellows
  Health (Medical, Pharmacy, Fitness): teals
  Entertainment (Cinema, Events, Streaming): purples
  Shopping (Retail, Clothing, Electronics): oranges
  Housing/Utilities (Rent, Bills, Insurance): cool slates and greys
  Unknown/Other: neutral grey (#64748B range)

Hard constraints — every color MUST:
  - Achieve minimum 4.5:1 contrast ratio against #FFFFFF
  - Not be within 30 hue degrees of #2563EB (primary blue), #16A34A (success green), or #DC2626 (danger red)
  - Have saturation between 40% and 80%
  - Have lightness between 25% and 55%

Return ONLY a JSON array, no prose, no markdown."""


class ColorAssignmentAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "color_assignment"

    async def run(self, category_names: list[str]) -> list[dict]:
        """category_names: categories with no color yet, or still sitting on
        their S3-01 seed color. Returns [{name, color}, ...].

        This agent only asks the LLM — it enforces nothing itself. Callers
        must run every returned color through colors.validate_color() before
        writing it to the database.
        """
        user_message = (
            "Assign colors to these categories:\n"
            f"{json.dumps(category_names)}\n\n"
            # The example color itself must satisfy the hard constraints above —
            # an example that violates its own rules (e.g. a vivid mid-tone
            # green like #22C55E, which fails the 4.5:1-on-white check) biases
            # the model toward picking similarly invalid colors.
            'Return: [{"name": "Groceries", "color": "#3C6029"}]'
        )
        result = await self.provider.complete_json(SYSTEM_PROMPT, user_message)
        if not isinstance(result, list):
            raise ValueError(f"Expected a JSON array from the LLM, got {type(result).__name__}")
        return result
