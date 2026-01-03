"""Color utilities for calendar rendering."""


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color (#RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color (#RRGGBB)."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def blend_colors(colors: list[str]) -> str:
    """Blend multiple hex colors by averaging RGB values."""
    if not colors:
        return "#e5e5e5"  # default gray
    if len(colors) == 1:
        return colors[0]

    rgbs = [hex_to_rgb(c) for c in colors]
    avg_r = sum(c[0] for c in rgbs) // len(rgbs)
    avg_g = sum(c[1] for c in rgbs) // len(rgbs)
    avg_b = sum(c[2] for c in rgbs) // len(rgbs)

    return rgb_to_hex((avg_r, avg_g, avg_b))


def interpolate_color(from_color: str, to_color: str, ratio: float) -> str:
    """Interpolate between two colors based on ratio (0.0 to 1.0)."""
    ratio = max(0.0, min(1.0, ratio))  # Clamp to [0, 1]

    from_rgb = hex_to_rgb(from_color)
    to_rgb = hex_to_rgb(to_color)

    result = (
        int(from_rgb[0] + (to_rgb[0] - from_rgb[0]) * ratio),
        int(from_rgb[1] + (to_rgb[1] - from_rgb[1]) * ratio),
        int(from_rgb[2] + (to_rgb[2] - from_rgb[2]) * ratio),
    )

    return rgb_to_hex(result)


# Default gray for no entry
DEFAULT_GRAY = "#e5e5e5"

# Default color palette for options without custom colors
DEFAULT_PALETTE = [
    "#22c55e",  # green
    "#3b82f6",  # blue
    "#8b5cf6",  # purple
    "#ec4899",  # pink
    "#fbbf24",  # amber
    "#14b8a6",  # teal
    "#ef4444",  # red
    "#86efac",  # light green
    "#f97316",  # orange
]


def get_option_color(
    option: str, option_colors: dict[str, str], all_options: list[str]
) -> str:
    """Get color for an option, using custom color or default from palette."""
    if option in option_colors:
        return option_colors[option]
    # Use palette based on option index
    if option in all_options:
        idx = all_options.index(option)
        return DEFAULT_PALETTE[idx % len(DEFAULT_PALETTE)]
    return DEFAULT_GRAY
