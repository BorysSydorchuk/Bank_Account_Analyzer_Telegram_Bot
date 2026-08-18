"""S5-04 — color validation invariant, AI color fallback behavior, and the
S3-07 regression (color collisions).

The rejection-rule test colors below aren't guessed — each one was
constructed with colorsys.hls_to_rgb from a known (hue, lightness,
saturation) triple chosen to trip exactly one of colors.py's rules, then
verified against the real describe_validation_failure() before being pinned
here. See docs/tickets/S5-04-*.md delivery notes for the derivation.
"""
import pytest

from app import crud
from app.analysis_service import assign_ai_colors
from app.colors import BACKUP_PALETTE, describe_validation_failure, validate_color
from tests.fixtures.fake_llm_provider import FakeLLMProvider

VALID_COLOR = "#7A29A3"  # also literally BACKUP_PALETTE[3] — passes every rule
FAILS_CONTRAST = "#C285E0"  # light enough to fail the 4.5:1-on-white check
FAILS_HUE_TOO_CLOSE_TO_PRIMARY = "#294FA3"  # within 30 degrees of #2563EB
FAILS_SATURATION_TOO_LOW = "#6D527A"
FAILS_SATURATION_TOO_HIGH = "#850AC2"
FAILS_LIGHTNESS_TOO_LOW = "#2E0F3D"


@pytest.mark.parametrize(
    "hex_color",
    [VALID_COLOR, *BACKUP_PALETTE],
)
def test_valid_colors_are_accepted(hex_color):
    assert validate_color(hex_color) is True
    assert describe_validation_failure(hex_color) is None


@pytest.mark.parametrize(
    "hex_color, expected_failure_substring",
    [
        (FAILS_CONTRAST, "Too light"),
        (FAILS_HUE_TOO_CLOSE_TO_PRIMARY, "Too close to an existing app color"),
        (FAILS_SATURATION_TOO_LOW, "Too dull"),
        (FAILS_SATURATION_TOO_HIGH, "Too vivid"),
        (FAILS_LIGHTNESS_TOO_LOW, "Too dark"),
        ("not-a-hex-color", "valid hex color"),
        ("#ZZZZZZ", "valid hex color"),
    ],
)
def test_each_rejection_rule_fires(hex_color, expected_failure_substring):
    assert validate_color(hex_color) is False
    reason = describe_validation_failure(hex_color)
    assert expected_failure_substring in reason


@pytest.mark.asyncio
async def test_rejected_ai_color_falls_back_to_the_categorys_existing_color(db_session, seeded_categories):
    """assign_ai_colors is the only place an LLM-chosen color reaches the
    database — it must never write a color that fails validate_color()."""
    existing = next(c for c in seeded_categories if c.name == "Groceries")
    existing_color = existing.color

    provider = FakeLLMProvider(json_response=[{"name": "Groceries", "color": FAILS_CONTRAST}])

    await assign_ai_colors(db_session, provider, ["Groceries"])

    db_session.refresh(existing)
    assert existing.color == existing_color
    assert existing.color != FAILS_CONTRAST


@pytest.mark.asyncio
async def test_rejected_ai_color_for_a_brand_new_category_falls_back_to_backup_palette_not_a_random_color(db_session):
    """A category with no existing row (never seeded, never AI-colored
    before) has nothing to fall back to — BACKUP_PALETTE is the fallback,
    not some ad-hoc default."""
    provider = FakeLLMProvider(json_response=[{"name": "Brand New Category", "color": FAILS_CONTRAST}])

    await assign_ai_colors(db_session, provider, ["Brand New Category"])

    saved = crud.get_categories_by_name(db_session, ["Brand New Category"])["Brand New Category"]
    assert saved.color in BACKUP_PALETTE


@pytest.mark.asyncio
async def test_source_user_colors_are_never_overwritten_by_ai(db_session, seeded_categories):
    category = next(c for c in seeded_categories if c.name == "Groceries")
    crud.set_category_color(db_session, "Groceries", VALID_COLOR)
    db_session.refresh(category)
    assert category.source == "user"

    provider = FakeLLMProvider(json_response=[{"name": "Groceries", "color": "#416F20"}])
    await assign_ai_colors(db_session, provider, ["Groceries"])

    db_session.refresh(category)
    assert category.color == VALID_COLOR
    assert category.source == "user"


def test_no_two_seeded_categories_share_a_color_S3_07_regression(seeded_categories):
    """S3-07: the old hash-derived color scheme could collide two categories
    onto the same color. That scheme is gone now that every category is a
    real row with its own explicit color (app/migrations/versions/
    fbde2dbcc78d_add_categories_table.py's SEED_COLORS) — this pins that
    fact so a future migration can't silently reintroduce a collision.
    """
    colors = [c.color for c in seeded_categories]
    assert len(colors) == len(set(colors))
