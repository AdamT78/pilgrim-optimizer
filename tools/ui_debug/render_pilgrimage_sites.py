"""Structured renderer for the pilgrimage site tile debug view.

Five orange hexes in one row, each carrying a yellow star with its VP value and one value on
either side of it: `P` on the left and `S` on the right, each number standing above the hex's mid
line with its letter hanging below, set at the size a building tile sets its name at.

The tiles are the size of a building tile on purpose, so the two read as the same kind of piece,
and the star is the one the donated building tiles and the piety track already draw. It is drawn
at the size the piety track draws its own, measured where the two stand together on the composed
game table, with the VP inside it at the track's star-to-label proportion. Matching the track makes
the star large enough to run into the ship marker, so it is hung below the ship's keel: on a map
hex carrying both, they stand one under the other.

This is a debug/visual tool only. It reads `pilgrimage_sites.json` and emits SVG/HTML. It is not
connected to `GameState`, it does not draw pilgrimage sites at random, and it implements no rules.

`prototypes/pilgrimage_sites.html` stays the visual baseline for the hex and its colours, and for
what a tile prints; how the star and the values are set has deliberately moved away from it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from tools.ui_debug.render_alms_table import STAR_LABEL_FONT_SIZE as TRACK_STAR_FONT_SIZE
from tools.ui_debug.render_alms_table import STAR_OUTER_RADIUS as TRACK_STAR_RADIUS
from tools.ui_debug.render_buildings import (
    HEX_RADIUS,
    TILE_NAME_FONT_SIZE,
    TILE_NAME_LINE_HEIGHT,
    hex_points,
)
from tools.ui_debug.render_donated_buildings import (
    STAR_INNER_RATIO,
    render_star_path,
)
from tools.ui_debug.render_ship_marker import SHIP_BOTTOM_Y

TILE_GAP = 26.0
COLUMN_SPACING = 2.0 * HEX_RADIUS + TILE_GAP
MARGIN = HEX_RADIUS * 1.3
HEX_APOTHEM = HEX_RADIUS * math.sin(math.radians(60.0))
HEX_STROKE_WIDTH = 2.5

SITE_FILL = "#F7CBA0"
SITE_STROKE = "#A85D1D"

# A five-pointed star stands its outer radius above its middle and this much of it below.
STAR_FOOT_RATIO = math.cos(math.radians(36.0))
STAR_STROKE_WIDTH = 1.5
# The piety track's star written in this tile's units: what it has to be drawn at here to come out
# the size the track draws it, once the composed game table has scaled a map hex and the track to
# their places. `test_ui_debug_game_table.py` measures the two against each other and holds this
# figure to it, so the table is what to re-measure if either board's scale ever moves.
STAR_OUTER_RADIUS = 22.386
# The star hangs below the ship marker, so a map hex carrying both can show them one under the
# other. The ship is scaled onto a map hex by the same ratio as the site's contents, so its keel
# sits at the same height in either board's units and this reads the same on both.
STAR_SHIP_CLEARANCE = 2.0
STAR_CENTER_Y = SHIP_BOTTOM_Y + STAR_OUTER_RADIUS + STAR_SHIP_CLEARANCE

TEXT_FILL = "#000000"
# The VP is set inside the star the way the piety track sets its own: the same share of the star's
# size, on the same third-of-the-font drop below its middle.
VP_TEXT_FONT_SIZE = STAR_OUTER_RADIUS * TRACK_STAR_FONT_SIZE / TRACK_STAR_RADIUS
VP_TEXT_OFFSET = VP_TEXT_FONT_SIZE / 3.0

# Helvetica's capitals stand about this much of the font size above their baseline.
CAP_HEIGHT_RATIO = 0.72
# The values beside the star are set like a building tile's name, at the same size and the same
# line spacing, so a site tile and a building tile read as the same kind of piece.
TEXT_FONT_SIZE = TILE_NAME_FONT_SIZE
LABEL_LINE_HEIGHT = TILE_NAME_LINE_HEIGHT
# The pair straddles the hex's mid line: the number stands above it, its letter hangs below.
LABEL_VALUE_Y = -(LABEL_LINE_HEIGHT - CAP_HEIGHT_RATIO * TEXT_FONT_SIZE) / 2.0
LABEL_LETTER_Y = LABEL_VALUE_Y + LABEL_LINE_HEIGHT
# Far enough out to clear the star's widest points, which are its two shoulders.
LABEL_GAP = 9.7
LABEL_COLUMN_X = STAR_OUTER_RADIUS * math.sin(math.radians(72.0)) + LABEL_GAP
PIETY_LABEL = "P"
STONE_LABEL = "S"

BACKGROUND_COLOR = "#000000"
TITLE = "PILGRIM — Pilgrimage Sites"
SUBTITLE = (
    '5 special "Pilgrimage Site" tiles, one row, all orange, each with a star below its middle.'
)
DATA_FILENAME = "pilgrimage_sites.json"


def default_data_path() -> Path:
    return Path(__file__).resolve().parent / DATA_FILENAME


def load_pilgrimage_sites(path: Path | None = None) -> dict:
    data_path = default_data_path() if path is None else Path(path)
    return json.loads(data_path.read_text(encoding="utf-8"))


def sites_of(data: dict | list) -> list[dict]:
    """Accept either a bare site list or the wrapped `{"sites": [...]}` document."""
    return list(data) if isinstance(data, list) else list(data["sites"])


def site_by_index(data: dict | list, index: int) -> dict:
    """The nth site in file order, which is the order the sites are handed out."""
    return sites_of(data)[index]


def _hex_path_data(cx: float, cy: float) -> str:
    points = hex_points(cx, cy)
    head = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    tail = " ".join(f"L {px:.2f},{py:.2f}" for px, py in points[1:])
    return f"{head} {tail} Z"


def star_center(cx: float, cy: float, scale: float = 1.0) -> tuple[float, float]:
    """The middle of the hex, by the star's own box rather than its geometric centre."""
    return cx, cy + STAR_CENTER_Y * scale


def _text(x: float, y: float, value: str, font_size: float, ink: str) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle"'
        ' font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{round(font_size, 2):g}" font-weight="600"'
        f' fill="{ink}">{escape(value)}</text>'
    )


def render_pilgrimage_site_hex(x: float, y: float) -> str:
    return (
        f'<path d="{_hex_path_data(x, y)}" fill="{SITE_FILL}" stroke="{SITE_STROKE}"'
        ' stroke-width="2.5" stroke-linejoin="round"/>'
    )


def render_pilgrimage_site_contents(
    site: dict,
    x: float = 0.0,
    y: float = 0.0,
    scale: float = 1.0,
    ink: str = TEXT_FILL,
) -> str:
    """Everything a site tile carries: the star with its VP value, and the P and S values.

    Drawn without the hex around it, so a caller that already has a hex — the game setup view
    recolours a map hex instead of stacking a tile on it — can reuse the contents at its own size.
    """
    star_x, star_y = star_center(x, y, scale)
    outer = STAR_OUTER_RADIUS * scale
    top = y + LABEL_VALUE_Y * scale
    bottom = y + LABEL_LETTER_Y * scale
    left = x - LABEL_COLUMN_X * scale
    right = x + LABEL_COLUMN_X * scale
    font_size = TEXT_FONT_SIZE * scale

    return "".join(
        [
            render_star_path(star_x, star_y, outer, outer * STAR_INNER_RATIO),
            _text(
                star_x,
                star_y + VP_TEXT_OFFSET * scale,
                str(site["vp"]),
                VP_TEXT_FONT_SIZE * scale,
                ink,
            ),
            _text(left, top, str(site["piety"]), font_size, ink),
            _text(left, bottom, PIETY_LABEL, font_size, ink),
            _text(right, top, str(site["stone"]), font_size, ink),
            _text(right, bottom, STONE_LABEL, font_size, ink),
        ]
    )


def render_pilgrimage_site_tile(site: dict, x: float, y: float) -> str:
    """Render one pilgrimage site tile (hex, star, values) centred on (x, y)."""
    return render_pilgrimage_site_hex(x, y) + render_pilgrimage_site_contents(site, x, y)


def _view_box(site_count: int) -> tuple[float, float, float, float]:
    min_x = -HEX_RADIUS - MARGIN
    max_x = (site_count - 1) * COLUMN_SPACING + HEX_RADIUS + MARGIN
    min_y = -HEX_RADIUS - MARGIN
    return min_x, min_y, max_x - min_x, 2 * (HEX_RADIUS + MARGIN)


def render_pilgrimage_sites_svg(data: dict | list) -> str:
    sites = sites_of(data)
    min_x, min_y, width, height = _view_box(len(sites))
    centers = [index * COLUMN_SPACING for index in range(len(sites))]

    background = (
        f'<rect x="{min_x:.1f}" y="{min_y:.1f}" width="{width:.1f}" height="{height:.1f}"'
        f' fill="{BACKGROUND_COLOR}"/>'
    )
    # Hexes first, then every star: the baseline draws the row in those two passes.
    hexes = "".join(render_pilgrimage_site_hex(x, 0.0) for x in centers)
    stars = "".join(
        render_pilgrimage_site_contents(site, x, 0.0)
        for site, x in zip(sites, centers, strict=True)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{min_x:.1f} {min_y:.1f} {width:.1f} {height:.1f}"'
        f' width="{round(width)}" height="{round(height)}">'
        f"\n  {background}\n  {hexes}\n  {stars}\n</svg>"
    )


def render_pilgrimage_sites_html(data: dict | list) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Pilgrimage Sites (generated)</title>
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
    {render_pilgrimage_sites_svg(data)}
  </div>
</body>
</html>
"""
