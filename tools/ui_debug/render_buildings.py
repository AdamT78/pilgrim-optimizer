"""Structured renderer for the building tiles debug view.

This is a debug/visual tool only. It reads `building_catalog.json` and emits SVG/HTML.
It is not connected to `GameState` and does not implement any game rules.

Geometry constants mirror `prototypes/building_tiles.html`, which stays the visual baseline.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

HEX_RADIUS = 52.0
HEX_HALF_HEIGHT = HEX_RADIUS * math.sin(math.radians(60.0))
COLUMN_SPACING = 130.0
ROW_GAP = 60.0
ROW_SPACING = 2.0 * HEX_HALF_HEIGHT + ROW_GAP

ROW_LABEL_OFFSET = 36.0
ROW_LABEL_BASELINE_OFFSET = 6.0
ROW_LABEL_GUTTER = 222.0

TILE_TEXT_TOP_OFFSET = 16.5
TILE_TEXT_LINE_HEIGHT = 12.0
TILE_TEXT_FONT_SIZE = 10.0

MARGIN_X = 68.0
MARGIN_Y = 75.0

BACKGROUND_COLOR = "#000000"
TITLE = "PILGRIM — Building Tiles"
CATALOG_FILENAME = "building_catalog.json"

_LEVEL_NUMERALS = {1: "I", 2: "II", 3: "III"}


@dataclass(frozen=True)
class ColorPalette:
    fill: str
    stroke: str


COLOR_GROUP_PALETTES: dict[str, ColorPalette] = {
    "light_blue": ColorPalette(fill="#AEE0F7", stroke="#1E5A78"),
    "light_red": ColorPalette(fill="#F7B9B9", stroke="#7A2020"),
    "light_green": ColorPalette(fill="#BFE8B4", stroke="#2E5C24"),
}


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent / CATALOG_FILENAME


def load_building_catalog(path: Path | None = None) -> dict:
    catalog_path = default_catalog_path() if path is None else Path(path)
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def palette_for(building: dict) -> ColorPalette:
    color_group = building["color_group"]
    if color_group not in COLOR_GROUP_PALETTES:
        raise KeyError(f"unknown color group: {color_group}")
    return COLOR_GROUP_PALETTES[color_group]


def level_numeral(level: int) -> str:
    if level not in _LEVEL_NUMERALS:
        raise KeyError(f"unknown building level: {level}")
    return _LEVEL_NUMERALS[level]


def buildings_in_group(catalog: dict, color_group_id: str) -> list[dict]:
    return [
        building for building in catalog["buildings"] if building["color_group"] == color_group_id
    ]


def hex_points(x: float, y: float) -> list[tuple[float, float]]:
    """Flat-top hexagon vertices, starting at the right corner and going clockwise."""
    return [
        (
            x + HEX_RADIUS * math.cos(math.radians(angle)),
            y + HEX_RADIUS * math.sin(math.radians(angle)),
        )
        for angle in range(0, 360, 60)
    ]


def _hex_path_data(x: float, y: float) -> str:
    points = hex_points(x, y)
    head = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    tail = " ".join(f"L {px:.2f},{py:.2f}" for px, py in points[1:])
    return f"{head} {tail} Z"


def tile_text_lines(building: dict) -> list[str]:
    """The label as the tile wraps it: the level numeral, then one line per word of the name."""
    return [level_numeral(building["level"]), *building["name"].split()]


def render_building_tile(building: dict, x: float, y: float) -> str:
    """Render one hex tile (shape plus wrapped label) centred on (x, y)."""
    palette = palette_for(building)
    parts = [
        f'<path d="{_hex_path_data(x, y)}" fill="{palette.fill}" stroke="{palette.stroke}"'
        ' stroke-width="2.5" stroke-linejoin="round"/>'
    ]
    for index, line in enumerate(tile_text_lines(building)):
        text_y = y + TILE_TEXT_TOP_OFFSET + index * TILE_TEXT_LINE_HEIGHT
        parts.append(
            f'<text x="{x:.1f}" y="{text_y:.1f}" text-anchor="middle"'
            ' font-family="Helvetica, Arial, sans-serif"'
            f' font-size="{TILE_TEXT_FONT_SIZE:g}" font-weight="600"'
            f' fill="{palette.stroke}">{escape(line)}</text>'
        )
    return "".join(parts)


def _render_row_label(label: str, stroke: str, row_y: float) -> str:
    label_x = -HEX_RADIUS - ROW_LABEL_OFFSET
    label_y = row_y + ROW_LABEL_BASELINE_OFFSET
    return (
        f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="end"'
        ' font-family="Georgia, serif" font-size="18" font-weight="bold"'
        f' fill="{stroke}">{escape(label)}</text>'
    )


def _view_box(row_count: int, column_count: int) -> tuple[float, float, float, float]:
    min_x = -HEX_RADIUS - ROW_LABEL_OFFSET - ROW_LABEL_GUTTER
    max_x = (column_count - 1) * COLUMN_SPACING + HEX_RADIUS + MARGIN_X
    min_y = -HEX_HALF_HEIGHT - MARGIN_Y
    max_y = (row_count - 1) * ROW_SPACING + HEX_HALF_HEIGHT + MARGIN_Y
    return min_x, min_y, max_x - min_x, max_y - min_y


def render_building_catalog_svg(catalog: dict) -> str:
    color_groups = catalog["color_groups"]
    rows = [(group, buildings_in_group(catalog, group["id"])) for group in color_groups]
    column_count = max((len(buildings) for _, buildings in rows), default=0)
    min_x, min_y, width, height = _view_box(len(rows), column_count)

    body = [
        f'<rect x="{min_x:.1f}" y="{min_y:.1f}" width="{width:.1f}" height="{height:.1f}"'
        f' fill="{BACKGROUND_COLOR}"/>'
    ]
    for row_index, (group, buildings) in enumerate(rows):
        row_y = row_index * ROW_SPACING
        stroke = COLOR_GROUP_PALETTES[group["id"]].stroke
        body.append(_render_row_label(group["label"], stroke, row_y))
        for column_index, building in enumerate(buildings):
            body.append(render_building_tile(building, column_index * COLUMN_SPACING, row_y))

    lines = "\n  ".join(body)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{min_x:.1f} {min_y:.1f} {width:.1f} {height:.1f}"'
        f' width="{round(width)}" height="{round(height)}">\n  {lines}\n</svg>'
    )


def _subtitle(catalog: dict) -> str:
    color_groups = catalog["color_groups"]
    labels = [group["label"].lower() for group in color_groups]
    if len(labels) > 1:
        joined = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    else:
        joined = labels[0]
    per_group = len(buildings_in_group(catalog, color_groups[0]["id"]))
    return (
        f"{len(catalog['buildings'])} placeable building tiles, {per_group} each in "
        f"{joined}, in the order listed. Generated from {CATALOG_FILENAME}."
    )


def render_building_catalog_html(catalog: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Building Tiles (generated)</title>
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
  <p class="subtitle">{escape(_subtitle(catalog))}</p>
  <div class="board-wrap">
    {render_building_catalog_svg(catalog)}
  </div>
</body>
</html>
"""
