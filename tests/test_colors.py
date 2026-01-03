"""Tests for color utilities."""

from habit_tracker.colors import (
    DEFAULT_GRAY,
    blend_colors,
    get_option_color,
    hex_to_rgb,
    interpolate_color,
    rgb_to_hex,
)


def test_hex_to_rgb():
    """hex_to_rgb converts hex string to RGB tuple."""
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("#0000ff") == (0, 0, 255)
    assert hex_to_rgb("#ffffff") == (255, 255, 255)
    assert hex_to_rgb("#000000") == (0, 0, 0)


def test_hex_to_rgb_without_hash():
    """hex_to_rgb works with or without # prefix."""
    assert hex_to_rgb("ff0000") == (255, 0, 0)


def test_rgb_to_hex():
    """rgb_to_hex converts RGB tuple to hex string."""
    assert rgb_to_hex((255, 0, 0)) == "#ff0000"
    assert rgb_to_hex((0, 255, 0)) == "#00ff00"
    assert rgb_to_hex((0, 0, 255)) == "#0000ff"


def test_blend_colors_empty():
    """blend_colors returns gray for empty list."""
    assert blend_colors([]) == DEFAULT_GRAY


def test_blend_colors_single():
    """blend_colors returns color unchanged for single color."""
    assert blend_colors(["#ff0000"]) == "#ff0000"


def test_blend_colors_two():
    """blend_colors averages two colors."""
    # Red + Blue = Purple (127, 0, 127)
    result = blend_colors(["#ff0000", "#0000ff"])
    assert result == "#7f007f"


def test_blend_colors_three():
    """blend_colors averages multiple colors."""
    # Red + Green + Blue = Gray (85, 85, 85)
    result = blend_colors(["#ff0000", "#00ff00", "#0000ff"])
    assert result == "#555555"


def test_interpolate_color_zero():
    """interpolate_color at 0.0 returns from_color."""
    result = interpolate_color("#000000", "#ffffff", 0.0)
    assert result == "#000000"


def test_interpolate_color_one():
    """interpolate_color at 1.0 returns to_color."""
    result = interpolate_color("#000000", "#ffffff", 1.0)
    assert result == "#ffffff"


def test_interpolate_color_half():
    """interpolate_color at 0.5 returns midpoint."""
    result = interpolate_color("#000000", "#ffffff", 0.5)
    # Midpoint of 0 and 255 is 127
    assert result == "#7f7f7f"


def test_interpolate_color_clamps():
    """interpolate_color clamps ratio to [0, 1]."""
    assert interpolate_color("#000000", "#ffffff", -0.5) == "#000000"
    assert interpolate_color("#000000", "#ffffff", 1.5) == "#ffffff"


def test_get_option_color_custom():
    """get_option_color returns custom color if defined."""
    result = get_option_color("good", {"good": "#aabbcc"}, ["good", "bad"])
    assert result == "#aabbcc"


def test_get_option_color_default_palette():
    """get_option_color uses default palette for undefined colors."""
    result = get_option_color("good", {}, ["good", "bad"])
    # First option gets first palette color
    assert result == "#22c55e"

    result = get_option_color("bad", {}, ["good", "bad"])
    # Second option gets second palette color
    assert result == "#3b82f6"


def test_get_option_color_unknown():
    """get_option_color returns gray for unknown option."""
    result = get_option_color("unknown", {}, ["good", "bad"])
    assert result == DEFAULT_GRAY
