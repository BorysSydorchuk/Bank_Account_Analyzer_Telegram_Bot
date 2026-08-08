"""Programmatic validation for category colors — WCAG contrast, semantic hue
separation from the app's own design tokens, and saturation/lightness bounds.
The S3-02 color-assignment agent is asked to follow these same rules, but its
output is never trusted without running back through here first.
"""
import colorsys

# The app's own primary/success/danger tokens — a category color landing too
# close to one of these would read as that UI element, not a distinct category.
FORBIDDEN_HUES_HEX = ["#2563EB", "#16A34A", "#DC2626"]
MIN_HUE_DISTANCE_DEGREES = 30
MIN_CONTRAST_RATIO = 4.5
SATURATION_RANGE = (40, 80)
LIGHTNESS_RANGE = (25, 55)

# Fallback colors for a category with no existing row to fall back to (a
# brand-new category, never seeded in S3-01) whose AI-assigned color fails
# validation. Cycled in order if more than 8 such categories need one in a
# single run.
BACKUP_PALETTE = ["#0EA5E9", "#8B5CF6", "#F59E0B", "#10B981", "#EF4444", "#6366F1", "#14B8A6", "#F97316"]


def is_valid_hex(hex_color: str) -> bool:
    """True if hex_color is a well-formed "#RRGGBB" string."""
    if not isinstance(hex_color, str) or not hex_color.startswith("#") or len(hex_color) != 7:
        return False
    try:
        _hex_to_rgb(hex_color)
        return True
    except ValueError:
        return False


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        normalized = value / 255
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_color: str, background_hex: str = "#FFFFFF") -> float:
    """WCAG contrast ratio of hex_color against background_hex (white by
    default — the background every category pill and chart slice renders on).
    """
    l1 = _relative_luminance(_hex_to_rgb(hex_color))
    l2 = _relative_luminance(_hex_to_rgb(background_hex))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _hue_degrees(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)
    hue, _lightness, _saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return hue * 360


def _hue_distance(a_degrees: float, b_degrees: float) -> float:
    diff = abs(a_degrees - b_degrees) % 360
    return min(diff, 360 - diff)


def validate_color(hex_color: str) -> bool:
    """True only if hex_color is safe to store as a category color: valid hex,
    readable on a white background, distinct from the app's own primary/
    success/danger tokens, and saturated/dark enough to read as an intentional
    color rather than a near-white or near-grey mistake.
    """
    return describe_validation_failure(hex_color) is None


def describe_validation_failure(hex_color: str) -> str | None:
    """None if hex_color passes every rule validate_color() checks; otherwise
    a specific, user-facing reason (S3-06: shown inline in the color picker
    popover, e.g. "Too light — won't be visible on white backgrounds") rather
    than a bare pass/fail a person can't act on.
    """
    if not is_valid_hex(hex_color):
        return "Enter a valid hex color, like #2E7D4F."

    if contrast_ratio(hex_color) < MIN_CONTRAST_RATIO:
        return "Too light — won't be visible on white backgrounds."

    hue = _hue_degrees(hex_color)
    too_close_to_a_token = any(
        _hue_distance(hue, _hue_degrees(forbidden)) <= MIN_HUE_DISTANCE_DEGREES for forbidden in FORBIDDEN_HUES_HEX
    )
    if too_close_to_a_token:
        return "Too close to an existing app color (the primary, success, or danger color)."

    r, g, b = _hex_to_rgb(hex_color)
    _hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    saturation_pct, lightness_pct = saturation * 100, lightness * 100
    if saturation_pct < SATURATION_RANGE[0]:
        return "Too dull — pick a more saturated color."
    if saturation_pct > SATURATION_RANGE[1]:
        return "Too vivid — pick a slightly more muted color."
    if lightness_pct < LIGHTNESS_RANGE[0]:
        return "Too dark — pick a lighter shade."
    if lightness_pct > LIGHTNESS_RANGE[1]:
        return "Too light — won't be visible on white backgrounds."

    return None
