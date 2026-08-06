"""Structured renderer for the ship marker debug view.

These are the first building tile of each colour with a ship silhouette drawn in the upper part
of the hex. The ship itself is a standalone SVG primitive (`render_ship_icon`) so it can later be
reused as an overlay elsewhere — map edge, round track — without dragging tile geometry along.

This is a debug/visual tool only. It reads `ship_marker_examples.json` and emits SVG/HTML. It is
not connected to `GameState` and does not implement any game rules; the ship is a marker drawn on
a tile, not a rule about the tile.

Geometry constants mirror `prototypes/ship_marker.html`, which stays the visual baseline. The
tile colours, radius, and label layout are shared with `render_buildings.py` so the two views
cannot drift apart.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from tools.ui_debug.render_buildings import (
    COLOR_GROUP_PALETTES,
    HEX_RADIUS,
    TILE_TEXT_LINE_HEIGHT,
    TILE_TEXT_TOP_OFFSET,
    ColorPalette,
    hex_points,
    level_numeral,
)

COLUMN_SPACING = 134.0
MARGIN = 67.6

SHIP_COLOR = "#000000"
SHIP_SCALE = 0.85
SHIP_ANCHOR_OFFSET_Y = -11.0

# Ship geometry in ship units, measured from the anchor point: x from the mid-hull, y from the
# waterline, negative y towards the mast tops. `render_ship_icon` scales it around that anchor.
HULL_OUTLINE = (
    (-24.0, 0.0),  # stern, waterline
    (-4.0, 16.0),  # keel control point
    (18.0, 0.0),  # bow, waterline
    (14.0, 0.0),  # bow, deck
    (-4.0, -2.0),  # deck control point
    (-20.0, 0.0),  # stern, deck
)
# How deep the keel hangs below the waterline, in the units of the hex the ship is drawn on. The
# hull is one quadratic from stern to bow, and a quadratic reaches its extreme halfway along, at
# half the depth of its control point.
KEEL_DEPTH = SHIP_SCALE * HULL_OUTLINE[1][1] / 2.0
# The lowest the ship reaches on that hex, which is what anything sharing the hex has to clear.
SHIP_BOTTOM_Y = SHIP_ANCHOR_OFFSET_Y + KEEL_DEPTH

BOWSPRIT = ((14.0, -2.0), (24.0, -8.0))
RIGGING_STROKE_WIDTH = 1.2

# One entry per mast: x, mast top y, and the width of the sail hanging off it.
MASTS = (
    (-18.0, -18.0, 10.0),
    (-5.0, -29.0, 13.0),
    (8.0, -22.0, 9.0),
)
MAST_FOOT_Y = 1.0
SAIL_FOOT_Y = -1.0
SAIL_OUTER_CONTROL_RATIO = 1.15
SAIL_INNER_CONTROL_RATIO = 0.35
SAIL_INNER_CONTROL_Y = -3.0

PENNANT_MAST_INDEX = 1
PENNANT_LENGTH = 7.0
PENNANT_TIP_DROP = 3.0
PENNANT_FOOT_DROP = 6.0

BACKGROUND_COLOR = "#000000"
TITLE = "PILGRIM — Ship Building Tiles"
SUBTITLE = "First tile of each color, with a ship silhouette in the upper part of the hex."
DATA_FILENAME = "ship_marker_examples.json"


def default_data_path() -> Path:
    return Path(__file__).resolve().parent / DATA_FILENAME


def load_ship_marker_examples(path: Path | None = None) -> dict:
    data_path = default_data_path() if path is None else Path(path)
    return json.loads(data_path.read_text(encoding="utf-8"))


def tiles_of(data: dict | list) -> list[dict]:
    """Accept either a bare tile list or the wrapped `{"tiles": [...]}` document."""
    return list(data) if isinstance(data, list) else list(data["tiles"])


def palette_for(tile: dict) -> ColorPalette:
    color_group = tile["color_group"]
    if color_group not in COLOR_GROUP_PALETTES:
        raise KeyError(f"unknown color group: {color_group}")
    return COLOR_GROUP_PALETTES[color_group]


def _coord(value: float) -> str:
    """Format a ship coordinate with one decimal, rounding halves upwards.

    Scaling by 0.85 lands on halves such as -10.15 or 129.75 often enough to matter, and the
    baseline resolves those upwards (-10.1, 129.8). Plain float formatting picks a side from the
    binary representation instead, which is what makes the two drift apart.
    """
    return f"{math.floor(value * 10.0 + 0.5) / 10.0:.1f}"


def _hex_path_data(x: float, y: float) -> str:
    points = hex_points(x, y)
    head = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    tail = " ".join(f"L {px:.2f},{py:.2f}" for px, py in points[1:])
    return f"{head} {tail} Z"


def render_ship_icon(
    cx: float,
    cy: float,
    scale: float = SHIP_SCALE,
    color: str = SHIP_COLOR,
) -> str:
    """Render the ship silhouette as a standalone SVG fragment.

    `(cx, cy)` is the middle of the hull at the waterline: the ship is centred horizontally on
    `cx` and rises above `cy`. The fragment is self-contained (no transform, no group), so it can
    be dropped into any SVG that later needs a ship overlay.
    """

    def point(bx: float, by: float) -> str:
        return f"{_coord(cx + scale * bx)},{_coord(cy + scale * by)}"

    def line(x1: float, y1: float, x2: float, y2: float) -> str:
        return (
            f'<line x1="{_coord(cx + scale * x1)}" y1="{_coord(cy + scale * y1)}"'
            f' x2="{_coord(cx + scale * x2)}" y2="{_coord(cy + scale * y2)}"'
            f' stroke="{color}" stroke-width="{scale * RIGGING_STROKE_WIDTH:.2f}"/>'
        )

    hull = [point(bx, by) for bx, by in HULL_OUTLINE]
    parts = [
        f'<path d="M {hull[0]} Q {hull[1]} {hull[2]} L {hull[3]} Q {hull[4]} {hull[5]}'
        f' Z" fill="{color}"/>'
    ]

    (bowsprit_x1, bowsprit_y1), (bowsprit_x2, bowsprit_y2) = BOWSPRIT
    parts.append(line(bowsprit_x1, bowsprit_y1, bowsprit_x2, bowsprit_y2))
    for mast_x, mast_top_y, _ in MASTS:
        parts.append(line(mast_x, MAST_FOOT_Y, mast_x, mast_top_y))

    for mast_x, mast_top_y, sail_width in MASTS:
        outer_control = point(
            mast_x + SAIL_OUTER_CONTROL_RATIO * sail_width, (mast_top_y + SAIL_FOOT_Y) / 2.0
        )
        inner_control = point(mast_x + SAIL_INNER_CONTROL_RATIO * sail_width, SAIL_INNER_CONTROL_Y)
        parts.append(
            f'<path d="M {point(mast_x, mast_top_y)}'
            f" Q {outer_control} {point(mast_x + sail_width, SAIL_FOOT_Y)}"
            f" Q {inner_control} {point(mast_x, SAIL_FOOT_Y)}"
            f' Z" fill="{color}"/>'
        )

    pennant_x, pennant_top_y, _ = MASTS[PENNANT_MAST_INDEX]
    parts.append(
        f'<path d="M {point(pennant_x, pennant_top_y)}'
        f" L {point(pennant_x + PENNANT_LENGTH, pennant_top_y + PENNANT_TIP_DROP)}"
        f" L {point(pennant_x, pennant_top_y + PENNANT_FOOT_DROP)}"
        f' Z" fill="{color}"/>'
    )
    return "".join(parts)


def _tile_text_lines(tile: dict) -> list[str]:
    label = tile.get("level_label") or level_numeral(tile["level"])
    return [label, *tile["name"].split()]


def render_ship_marker_tile(tile: dict, x: float, y: float) -> str:
    """Render one ship marker tile (hex, ship overlay, wrapped label) centred on (x, y)."""
    palette = palette_for(tile)
    parts = [
        f'<path d="{_hex_path_data(x, y)}" fill="{palette.fill}" stroke="{palette.stroke}"'
        ' stroke-width="2.5" stroke-linejoin="round"/>',
        render_ship_icon(x, y + SHIP_ANCHOR_OFFSET_Y),
    ]
    for index, line in enumerate(_tile_text_lines(tile)):
        text_y = y + TILE_TEXT_TOP_OFFSET + index * TILE_TEXT_LINE_HEIGHT
        parts.append(
            f'<text x="{x:.1f}" y="{text_y:.1f}" text-anchor="middle"'
            ' font-family="Helvetica, Arial, sans-serif" font-size="10" font-weight="600"'
            f' fill="{palette.stroke}">{escape(line)}</text>'
        )
    return "".join(parts)


def _view_box(tile_count: int) -> tuple[float, float, float, float]:
    min_x = -HEX_RADIUS - MARGIN
    max_x = (tile_count - 1) * COLUMN_SPACING + HEX_RADIUS + MARGIN
    min_y = -HEX_RADIUS - MARGIN
    return min_x, min_y, max_x - min_x, 2 * (HEX_RADIUS + MARGIN)


def render_ship_marker_examples_svg(data: dict | list) -> str:
    tiles = tiles_of(data)
    min_x, min_y, width, height = _view_box(len(tiles))

    background = (
        f'<rect x="{min_x:.1f}" y="{min_y:.1f}" width="{width:.1f}" height="{height:.1f}"'
        f' fill="{BACKGROUND_COLOR}"/>'
    )
    row = "".join(
        render_ship_marker_tile(tile, index * COLUMN_SPACING, 0.0)
        for index, tile in enumerate(tiles)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{min_x:.1f} {min_y:.1f} {width:.1f} {height:.1f}"'
        f' width="{round(width)}" height="{round(height)}">'
        f"\n  {background}\n  {row}\n</svg>"
    )


def render_ship_marker_examples_html(data: dict | list) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Ship Building Tiles (generated)</title>
<style>
  body {{
    margin: 0;
    background: {BACKGROUND_COLOR};
    font-family: Helvetica, Arial, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 12px 40px;
    box-sizing: border-box;
  }}
  h1 {{
    font-family: Georgia, serif;
    font-size: 26px;
    color: #F2EEDF;
    margin: 0 0 2px;
  }}
  p.subtitle {{
    color: #A8A296;
    font-size: 14px;
    margin: 0 0 18px;
    text-align: center;
    max-width: 640px;
  }}
  .board-wrap {{
    background: {BACKGROUND_COLOR};
    border: 1px solid #333333;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    padding: 10px;
  }}
  svg {{ display: block; max-width: 95vw; height: auto; }}
</style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="subtitle">{escape(SUBTITLE)} Generated from {DATA_FILENAME}.</p>
  <div class="board-wrap">
    {render_ship_marker_examples_svg(data)}
  </div>
</body>
</html>
"""
