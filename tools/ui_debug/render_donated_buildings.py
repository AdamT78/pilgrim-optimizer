"""Structured renderer for the donated/flipped building tile debug view.

These tiles are the VP markers shown when a building is donated (flipped): one hex per
building level/colour, carrying a yellow star with the victory point value.

This is a debug/visual tool only. It reads `donated_building_tiles.json` and emits SVG/HTML.
It is not connected to `GameState` and does not implement any game rules.

Geometry constants mirror `prototypes/donated_building_tiles.html`, which stays the visual
baseline for the hex and its colours. The tile colours are shared with `render_buildings.py` so the
two views cannot drift apart. The star has deliberately moved away from the baseline: it is drawn
at the size a pilgrimage site's star comes out on the composed game table, with the VP inside it at
the piety track's star-to-label proportion, so the two kinds of VP star read as one piece. It stays
in the middle of the hex, unlike the site's, which hangs below the ship marker.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from tools.ui_debug.render_alms_table import STAR_LABEL_FONT_SIZE as TRACK_STAR_FONT_SIZE
from tools.ui_debug.render_alms_table import STAR_OUTER_RADIUS as TRACK_STAR_RADIUS
from tools.ui_debug.render_buildings import COLOR_GROUP_PALETTES, ColorPalette

HEX_RADIUS = 60.0
COLUMN_SPACING = 160.0
MARGIN = 78.0

# The pilgrimage site's star written in this tile's units. A donated tile is only ever seen in a
# player board's building slot and a site only on a map hex, so the two match on the page when they
# are the same share of the hex each is scaled onto -- and a site's star is 22.386 of a building
# tile's 52, which is this of a donated tile's 60. It used to take a larger figure than that, since
# a slot came out well short of a map hex on the composed table and the star had to make the
# difference up; the slots are drawn at a map hex's size now, so the plain proportion is the whole
# of it. `test_ui_debug_game_table.py` measures the two against each other on the real solve.
STAR_OUTER_RADIUS = 25.830
STAR_INNER_RATIO = 0.45
STAR_POINTS = 5
STAR_FILL = "#F4D03F"
STAR_STROKE = "#B8960C"

VP_TEXT_FILL = "#000000"
# The VP is set inside the star the way the piety track and the pilgrimage site set their own: the
# same share of the star's size, on the same third-of-the-font drop below its middle. Taken from
# the track rather than from the site renderer because that one already reads its star from here,
# and the two cannot be made to read from each other.
VP_TEXT_FONT_SIZE = STAR_OUTER_RADIUS * TRACK_STAR_FONT_SIZE / TRACK_STAR_RADIUS
VP_TEXT_OFFSET = VP_TEXT_FONT_SIZE / 3.0

BACKGROUND_COLOR = "#000000"
TITLE = "PILGRIM — Special Tiles"
SUBTITLE = "One hex per building color, with a yellow star and its number."
DATA_FILENAME = "donated_building_tiles.json"


def default_data_path() -> Path:
    return Path(__file__).resolve().parent / DATA_FILENAME


def load_donated_building_tiles(path: Path | None = None) -> dict:
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


def hex_points(cx: float, cy: float) -> list[tuple[float, float]]:
    """Flat-top hexagon vertices, starting at the right corner and going clockwise."""
    return [
        (
            cx + HEX_RADIUS * math.cos(math.radians(angle)),
            cy + HEX_RADIUS * math.sin(math.radians(angle)),
        )
        for angle in range(0, 360, 60)
    ]


def _hex_path_data(cx: float, cy: float) -> str:
    points = hex_points(cx, cy)
    head = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    tail = " ".join(f"L {px:.2f},{py:.2f}" for px, py in points[1:])
    return f"{head} {tail} Z"


def star_points(cx: float, cy: float, outer_r: float, inner_r: float) -> list[tuple[float, float]]:
    """Star vertices alternating outer and inner radius, starting at the top point."""
    step = 180.0 / STAR_POINTS
    radii = (outer_r, inner_r)
    return [
        (
            cx + radii[index % 2] * math.cos(math.radians(-90.0 + index * step)),
            cy + radii[index % 2] * math.sin(math.radians(-90.0 + index * step)),
        )
        for index in range(2 * STAR_POINTS)
    ]


def render_star_path(cx: float, cy: float, outer_r: float, inner_r: float) -> str:
    points = star_points(cx, cy, outer_r, inner_r)
    head = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    tail = " ".join(f"L {px:.2f},{py:.2f}" for px, py in points[1:])
    return (
        f'<path d="{head} {tail} Z" fill="{STAR_FILL}" stroke="{STAR_STROKE}"'
        ' stroke-width="1.5" stroke-linejoin="round"/>'
    )


def render_donated_building_hex(tile: dict, x: float, y: float) -> str:
    palette = palette_for(tile)
    return (
        f'<path d="{_hex_path_data(x, y)}" fill="{palette.fill}" stroke="{palette.stroke}"'
        ' stroke-width="2.5" stroke-linejoin="round"/>'
    )


def render_donated_building_contents(
    tile: dict, x: float = 0.0, y: float = 0.0, scale: float = 1.0
) -> str:
    """The star and its VP number, without the hex around them.

    Drawn on its own so a caller that already has a hex — the game setup view recolours a player
    board's building slot instead of stacking a tile on it — can reuse the contents at its own
    size, and without the tile's border.
    """
    outer = STAR_OUTER_RADIUS * scale
    return (
        render_star_path(x, y, outer, outer * STAR_INNER_RATIO)
        + f'<text x="{x:.1f}" y="{y + VP_TEXT_OFFSET * scale:.1f}" text-anchor="middle"'
        ' font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{VP_TEXT_FONT_SIZE * scale:g}" font-weight="600"'
        f' fill="{VP_TEXT_FILL}">{escape(str(tile["vp"]))}</text>'
    )


def render_donated_building_tile(tile: dict, x: float, y: float) -> str:
    """Render one donated building tile (hex, star, VP number) centred on (x, y)."""
    return render_donated_building_hex(tile, x, y) + render_donated_building_contents(tile, x, y)


def _view_box(tile_count: int) -> tuple[float, float, float, float]:
    min_x = -HEX_RADIUS - MARGIN
    max_x = (tile_count - 1) * COLUMN_SPACING + HEX_RADIUS + MARGIN
    min_y = -HEX_RADIUS - MARGIN
    return min_x, min_y, max_x - min_x, 2 * (HEX_RADIUS + MARGIN)


def render_donated_building_tiles_svg(data: dict | list) -> str:
    tiles = tiles_of(data)
    min_x, min_y, width, height = _view_box(len(tiles))

    background = (
        f'<rect x="{min_x:.1f}" y="{min_y:.1f}" width="{width:.1f}" height="{height:.1f}"'
        f' fill="{BACKGROUND_COLOR}"/>'
    )
    row = "".join(
        render_donated_building_tile(tile, index * COLUMN_SPACING, 0.0)
        for index, tile in enumerate(tiles)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{min_x:.1f} {min_y:.1f} {width:.1f} {height:.1f}"'
        f' width="{round(width)}" height="{round(height)}">'
        f"\n  {background}\n  {row}\n</svg>"
    )


def render_donated_building_tiles_html(data: dict | list) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Special Tiles (generated)</title>
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
    {render_donated_building_tiles_svg(data)}
  </div>
</body>
</html>
"""
