"""S3-02 smoke test: proves colors.validate_color() rejects unsafe colors for
the reasons the ticket specifies, and that assign_ai_colors() falls back
correctly — without a real seed for that scenario, since the live LLM has no
reliable way to be *made* to return a bad color on demand.

Usage: python -m scripts.smoke_test_color_validation  (run from /backend,
same reasoning as scripts/smoke_test_providers.py's own docstring)
"""
import asyncio

from dotenv import load_dotenv

load_dotenv()

from app.colors import validate_color
from app.db import SessionLocal
from app import analysis_service, crud


def test_validate_color() -> None:
    print("--- colors.validate_color() ---")
    cases = [
        ("#3C6029", True, "dark olive green, 30+ hue degrees from the success token — satisfies all four rules"),
        ("#FFFF00", False, "bright yellow — fails the 4.5:1 contrast-on-white rule"),
        ("#2563EB", False, "is the forbidden primary-blue token itself — fails hue-distance"),
        ("#1D4ED8", False, "near-identical blue — within 30 hue degrees of the primary token"),
    ]
    for hex_color, expected, reason in cases:
        actual = validate_color(hex_color)
        status = "OK" if actual == expected else "MISMATCH"
        print(f"  [{status}] validate_color({hex_color!r}) = {actual} (expected {expected}) — {reason}")


class _StubProvider:
    """A fake LLMProvider so this test doesn't depend on a real, non-deterministic
    LLM call to happen to produce an invalid color on demand."""

    name = "stub"

    def __init__(self, response: list[dict]):
        self._response = response

    async def complete(self, system: str, user: str) -> str:
        raise NotImplementedError

    async def complete_json(self, system: str, user: str) -> list[dict]:
        return self._response


async def test_assign_ai_colors_fallback() -> None:
    print("\n--- analysis_service.assign_ai_colors() fallback path ---")
    db = SessionLocal()
    try:
        before = {c.name: c.color for c in crud.list_categories(db)}
        if "Other" not in before:
            print("  SKIPPED — no 'Other' category row to test against (run S3-01's migration first)")
            return
        seed_color_before = before["Other"]

        crud.upsert_category_colors(db, {"Other": seed_color_before}, source="seed")

        stub = _StubProvider([{"name": "Other", "color": "#FFFF00"}])  # deliberately invalid
        await analysis_service.assign_ai_colors(db, stub, ["Other"])

        after = crud.get_categories_by_name(db, ["Other"])["Other"]
        fell_back_correctly = after.color == seed_color_before and after.source == "ai"
        status = "OK" if fell_back_correctly else "MISMATCH"
        print(f"  [{status}] LLM returned invalid #FFFF00 for 'Other' -> stored color={after.color!r}, "
              f"source={after.source!r} (expected color={seed_color_before!r}, source='ai')")
    finally:
        db.close()


async def main() -> None:
    test_validate_color()
    await test_assign_ai_colors_fallback()


if __name__ == "__main__":
    asyncio.run(main())
