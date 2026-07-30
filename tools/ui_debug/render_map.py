"""Structured renderer for the map debug view.

This is a debug/visual tool only. It reads `map_layout.json` and emits SVG/HTML. It is not
connected to `GameState` and does not implement any game rules.

Geometry and the 18xx-style label function mirror `prototypes/map.html`, which stays the
visual baseline. The label function in particular must not drift: the top hex is `B6`, the
bottom hex is `L6`, and the middle row runs `G1`..`G11`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

LAYOUT_FILENAME = "map_layout.json"
TITLE = "PILGRIM — Hex Grid (blank yellow tiles)"
SUBTITLE = (
    "Clean flat-top hex board, uniform yellow tiles, 18xx-style coordinate labels only. "
    "Fully filled regular hexagon, 6 hexes along each of its six edges (91 tiles total). "
    "Placeholder board shape; swap the hex set in map_layout.json for the real layout once "
    "you have it."
)
PAGE_BACKGROUND = "#000000"

# Axial neighbour deltas for edge 0..5 of a flat-top hex, matching the vertex order below.
_EDGE_NEIGHBOURS = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))

# The prototype places G6 at the origin, so labels are offset from the middle of the grid.
_LABEL_ORIGIN = 6


def _n(value: float, decimals: int = 2) -> str:
    """Format a coordinate, normalising negative zero so output stays stable."""
    return f"{round(value, decimals) + 0.0:.{decimals}f}"


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def load_map_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def hex_label(q: int, r: int) -> str:
    """18xx-style label used by the prototype: letter row, numbered column."""
    letter = chr(ord("A") + r + (q // 2) + _LABEL_ORIGIN)
    return f"{letter}{q + _LABEL_ORIGIN}"


def axial_coords(layout: dict) -> list[tuple[int, int]]:
    radius = layout["edge_length"] - 1
    return [
        (q, r)
        for q in range(-radius, radius + 1)
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1)
    ]


def label_to_coord(layout: dict) -> dict[str, tuple[int, int]]:
    return {hex_label(q, r): (q, r) for q, r in axial_coords(layout)}


def hex_center(layout: dict, q: int, r: int) -> tuple[float, float]:
    size = layout["hex_size"]
    return (1.5 * size * q, size * math.sin(math.radians(60.0)) * (2 * r + q))


def hex_vertices(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    """Flat-top hexagon vertices, starting at the right corner and going clockwise."""
    return [
        (
            cx + size * math.cos(math.radians(angle)),
            cy + size * math.sin(math.radians(angle)),
        )
        for angle in range(0, 360, 60)
    ]


def edge_midpoint(layout: dict, cx: float, cy: float, edge: int) -> tuple[float, float]:
    size = layout["hex_size"]
    apothem = size * math.sin(math.radians(60.0))
    angle = math.radians(30.0 + 60.0 * edge)
    return (cx + apothem * math.cos(angle), cy + apothem * math.sin(angle))


def generate_hexes(layout: dict) -> list[dict]:
    color_groups = layout["color_groups"]
    overrides = layout["color_overrides"]
    default_group = layout["default_color_group"]
    hidden = set(layout["hidden_labels"])

    hexes = []
    for q, r in axial_coords(layout):
        label = hex_label(q, r)
        group_name = overrides.get(label, default_group)
        group = color_groups[group_name]
        cx, cy = hex_center(layout, q, r)
        hexes.append(
            {
                "label": label,
                "q": q,
                "r": r,
                "cx": cx,
                "cy": cy,
                "color_group": group_name,
                "fill": group["fill"],
                "label_color": group["label_color"],
                "hidden": label in hidden,
            }
        )
    return hexes


def _view_box(layout: dict) -> tuple[float, float, float, float]:
    board = layout["board"]
    radius = board["edge_hex_radius"]
    margin = board["margin"]
    half_width = radius * math.sin(math.radians(60.0)) + margin
    half_height = radius + margin
    return (-half_width, -half_height, 2 * half_width, 2 * half_height)


def _render_board_edge_hex(layout: dict) -> str:
    board = layout["board"]
    radius = board["edge_hex_radius"]
    # A hexagon is point-symmetric, so mirroring three vertices keeps opposite corners
    # exactly opposite instead of drifting apart by floating-point noise.
    half = [
        (
            radius * math.cos(math.radians(60.0 * index - 90.0)),
            radius * math.sin(math.radians(60.0 * index - 90.0)),
        )
        for index in range(3)
    ]
    points = half + [(-px, -py) for px, py in half]
    head = f"M {_n(points[0][0])},{_n(points[0][1])}"
    tail = " ".join(f"L {_n(px)},{_n(py)}" for px, py in points[1:])
    return (
        f'<path d="{head} {tail} Z" fill="{board["edge_hex_fill"]}"'
        f' stroke="{board["edge_hex_stroke"]}"'
        f' stroke-width="{board["edge_hex_stroke_width"]:g}" stroke-linejoin="round"/>'
    )


def _render_tile(hex_data: dict, layout: dict) -> str:
    points = hex_vertices(hex_data["cx"], hex_data["cy"], layout["hex_size"])
    head = f"M {_n(points[0][0])},{_n(points[0][1])}"
    tail = " ".join(f"L {_n(px)},{_n(py)}" for px, py in points[1:])
    return f'<path d="{head} {tail} Z" fill="{hex_data["fill"]}" stroke="none"/>'


def _render_tile_edges(hex_data: dict, layout: dict, hidden_coords: set) -> list[str]:
    points = hex_vertices(hex_data["cx"], hex_data["cy"], layout["hex_size"])
    width = layout["edge_stroke_width"]
    lines = []
    for edge in range(6):
        start = points[edge]
        end = points[(edge + 1) % 6]
        neighbour = (
            hex_data["q"] + _EDGE_NEIGHBOURS[edge][0],
            hex_data["r"] + _EDGE_NEIGHBOURS[edge][1],
        )
        inside_hidden_cluster = hex_data["hidden"] and neighbour in hidden_coords
        stroke = layout["hidden_edge_stroke"] if inside_hidden_cluster else layout["default_stroke"]
        lines.append(
            f'<line x1="{_n(start[0])}" y1="{_n(start[1])}" x2="{_n(end[0])}"'
            f' y2="{_n(end[1])}" stroke="{stroke}" stroke-width="{width:g}"'
            ' stroke-linecap="round"/>'
        )
    return lines


def _render_label(hex_data: dict, layout: dict) -> str:
    text_x = hex_data["cx"] + layout["label_offset_x"]
    text_y = hex_data["cy"] + layout["label_offset_y"]
    return (
        f'<text x="{_n(text_x, 1)}" y="{_n(text_y, 1)}"'
        ' font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{layout["label_font_size"]:g}" fill="{hex_data["label_color"]}"'
        f' font-weight="600">{escape(hex_data["label"])}</text>'
    )


def _river_path_data(river: dict, layout: dict, centers: dict) -> str:
    hexes = river["hexes"]
    first = centers[hexes[0]]
    last = centers[hexes[-1]]
    points = [edge_midpoint(layout, first[0], first[1], river["from_edge"])]
    points.extend(centers[label] for label in hexes)
    points.append(edge_midpoint(layout, last[0], last[1], river["to_edge"]))
    head = f"M {_n(points[0][0])},{_n(points[0][1])}"
    tail = " ".join(f"L {_n(px)},{_n(py)}" for px, py in points[1:])
    return f"{head} {tail}"


def _render_rivers(layout: dict, centers: dict) -> list[str]:
    halo_opacity = layout["river_halo_opacity"]
    parts = []
    for river in layout["rivers"]:
        data = _river_path_data(river, layout, centers)
        for stroke, width, opacity in (
            (layout["river_halo_stroke"], layout["river_halo_stroke_width"], halo_opacity),
            (layout["river_stroke"], layout["river_stroke_width"], None),
        ):
            suffix = "" if opacity is None else f' opacity="{opacity:g}"'
            parts.append(
                f'<path d="{data}" fill="none" stroke="{stroke}" stroke-width="{width:g}"'
                f' stroke-linecap="butt" stroke-linejoin="round"{suffix}/>'
            )
    return parts


def _render_track_segments(layout: dict, centers: dict) -> list[str]:
    parts = []
    for segment in layout["track_segments"]:
        cx, cy = centers[segment["label"]]
        start = edge_midpoint(layout, cx, cy, segment["from_edge"])
        end = edge_midpoint(layout, cx, cy, segment["to_edge"])
        parts.append(
            f'<line x1="{_n(start[0])}" y1="{_n(start[1])}" x2="{_n(end[0])}"'
            f' y2="{_n(end[1])}" stroke="{layout["river_stroke"]}"'
            f' stroke-width="{layout["river_stroke_width"]:g}" stroke-linecap="round"/>'
        )
    return parts


def _render_curve_segments(layout: dict, centers: dict) -> list[str]:
    parts = []
    for segment in layout["curve_segments"]:
        cx, cy = centers[segment["label"]]
        start = edge_midpoint(layout, cx, cy, segment["from_edge"])
        control = edge_midpoint(layout, cx, cy, segment["control_edge"])
        end = edge_midpoint(layout, cx, cy, segment["to_edge"])
        parts.append(
            f'<path d="M {_n(start[0])},{_n(start[1])} Q {_n(control[0])},{_n(control[1])}'
            f' {_n(end[0])},{_n(end[1])}" fill="none" stroke="{layout["river_stroke"]}"'
            f' stroke-width="{layout["river_stroke_width"]:g}" stroke-linecap="round"/>'
        )
    return parts


def render_map_svg(layout: dict) -> str:
    hexes = generate_hexes(layout)
    centers = {item["label"]: (item["cx"], item["cy"]) for item in hexes}
    hidden_coords = {(item["q"], item["r"]) for item in hexes if item["hidden"]}
    min_x, min_y, width, height = _view_box(layout)

    parts = [
        f'<rect x="{_n(min_x, 1)}" y="{_n(min_y, 1)}" width="{_n(width, 1)}"'
        f' height="{_n(height, 1)}" fill="{layout["board"]["background"]}"/>',
        _render_board_edge_hex(layout),
    ]
    parts.extend(_render_tile(item, layout) for item in hexes)
    parts.extend(_render_rivers(layout, centers))
    for item in hexes:
        parts.extend(_render_tile_edges(item, layout, hidden_coords))
    parts.extend(_render_track_segments(layout, centers))
    parts.extend(_render_curve_segments(layout, centers))
    parts.extend(_render_label(item, layout) for item in hexes if not item["hidden"])

    body = "\n  ".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="{_n(min_x, 1)} {_n(min_y, 1)} {_n(width, 1)} {_n(height, 1)}"'
        f' width="{round(width)}" height="{round(height)}">\n  {body}\n</svg>'
    )


def render_map_html(layout: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Hex Map (generated)</title>
<style>
  body {{
    margin: 0;
    background: {PAGE_BACKGROUND};
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
    background: {PAGE_BACKGROUND};
    border: 1px solid #333333;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    padding: 10px;
  }}
  svg {{ display: block; max-width: 92vw; height: auto; }}
</style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="subtitle">{escape(SUBTITLE)}</p>
  <div class="board-wrap">
    {render_map_svg(layout)}
  </div>
</body>
</html>
"""
