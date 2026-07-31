"""Structured renderer for the pilgrimage site tile debug view.

Five orange hexes in one row, each carrying a yellow star with its VP value and one value on
either side of it: `P` on the left and `S` on the right, exactly as the baseline prints them.

This is a debug/visual tool only. It reads `pilgrimage_sites.json` and emits SVG/HTML. It is not
connected to `GameState`, it does not draw pilgrimage sites at random, and it implements no rules.

Geometry constants mirror `prototypes/pilgrimage_sites.html`, which stays the visual baseline. The
tiles are the size of a building tile on purpose, so the two read as the same kind of piece, and
the star is the one the donated building tiles and the piety track already draw.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from tools.ui_debug.render_buildings import HEX_RADIUS, hex_points
from tools.ui_debug.render_donated_buildings import (
    STAR_INNER_RATIO,
    render_star_path,
)

TILE_GAP = 26.0
COLUMN_SPACING = 2.0 * HEX_RADIUS + TILE_GAP
MARGIN = HEX_RADIUS * 1.3

SITE_FILL = "#F7CBA0"
SITE_STROKE = "#A85D1D"

STAR_OUTER_RADIUS = 18.0
# The star sits in the lower half of the hex, lifted a little to balance the values beside it.
STAR_LIFT = 4.0

TEXT_FILL = "#000000"
TEXT_FONT_SIZE = 9.0
VP_TEXT_OFFSET = 3.0
# Where the top of a digit sits above its own baseline at this font and size, measured from the
# prototype: it is what lines the side values up with the top point of the star.
LABEL_CAP_TOP_OFFSET = 8.01
LABEL_LINE_HEIGHT = 10.0
LABEL_GAP = 9.0
PIETY_LABEL = "P"
STONE_LABEL = "S"

BACKGROUND_COLOR = "#000000"
TITLE = "PILGRIM — Pilgrimage Sites"
SUBTITLE = (
    '5 special "Pilgrimage Site" tiles, one row, all orange, each with a star in the lower half.'
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
    """The middle of the hex's lower half, lifted by `STAR_LIFT`."""
    apothem = HEX_RADIUS * math.sin(math.radians(60.0))
    return cx, cy + (apothem * 0.5 - STAR_LIFT) * scale


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
    top = star_y - outer + LABEL_CAP_TOP_OFFSET * scale
    bottom = top + LABEL_LINE_HEIGHT * scale
    left = star_x - outer - LABEL_GAP * scale
    right = star_x + outer + LABEL_GAP * scale
    font_size = TEXT_FONT_SIZE * scale

    return "".join(
        [
            render_star_path(star_x, star_y, outer, outer * STAR_INNER_RATIO),
            _text(star_x, star_y + VP_TEXT_OFFSET * scale, str(site["vp"]), font_size, ink),
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
