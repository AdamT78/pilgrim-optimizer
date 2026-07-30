"""Structured renderer for the player board debug view.

This is a debug/visual tool only. It reads `player_board_layout.json` and a mock player
state, then emits SVG/HTML. It is not connected to `GameState` and does not implement any
game rules.

Coordinates mirror `prototypes/player_board.html`, which stays the visual baseline.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

LAYOUT_FILENAME = "player_board_layout.json"
TITLE = "PILGRIM — Player Board"
SUBTITLE = "Village/Abbey banners and resources squeezed above a fused worker+building hex snake."
PAGE_BACKGROUND = "#000000"

# Wheat stalks as (tip_dx, tip_dy, ear_rotation_degrees) offsets from the icon centre.
_WHEAT_STALKS = (
    (-5.5, -10.5, -22),
    (-2.5, -12.5, -10),
    (0.5, -13.0, 2),
    (3.5, -12.0, 14),
    (6.0, -9.5, 24),
)
_WHEAT_ROOT = (0.0, 1.5)
_WHEAT_BASE_HALF_WIDTH = 3.0
_WHEAT_BASE_DY = 2.0
_WHEAT_EAR_RX = 1.30
_WHEAT_EAR_RY = 2.20

# Isometric cube faces as (offsets, fill_opacity) pairs, relative to the icon centre.
_STONE_FACES = (
    (((0.0, -12.1), (7.0, -8.0), (0.0, -4.0), (-7.0, -8.0)), "0.9"),
    (((7.0, -8.0), (7.0, 0.0), (0.0, 4.1), (0.0, -4.0)), "0.55"),
    (((-7.0, -8.0), (0.0, -4.0), (0.0, 4.1), (-7.0, 0.0)), "0.75"),
)

_SILVER_DY = -4.0
_SILVER_OUTER_RADIUS = 8.06
_SILVER_INNER_RADIUS = 4.43
_SILVER_CROSS_HALF_LENGTH = 4.4


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def load_player_board_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def default_player_state() -> dict:
    """Mock state standing in for a real `GameState` player until wiring exists."""
    return {
        "player_label": "Player: 1",
        "village_count": 8,
        "abbey_count": 3,
        "resources": {"wheat": 1, "stone": 1, "silver": 1},
        "occupied_special_activities": {"stone_mason": 1, "vestry": 2},
    }


def hex_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    """Flat-top hexagon vertices, starting at the right corner and going clockwise."""
    return [
        (
            cx + radius * math.cos(math.radians(angle)),
            cy + radius * math.sin(math.radians(angle)),
        )
        for angle in range(0, 360, 60)
    ]


def _hex_path_data(cx: float, cy: float, radius: float) -> str:
    points = hex_points(cx, cy, radius)
    head = f"M {points[0][0]:.2f},{points[0][1]:.2f}"
    tail = " ".join(f"L {px:.2f},{py:.2f}" for px, py in points[1:])
    return f"{head} {tail} Z"


def _label_lines(label: str) -> list[str]:
    return label.split()


def _render_board(layout: dict) -> str:
    board = layout["board"]
    return (
        f'<rect x="0" y="0" width="{board["width"]:g}" height="{board["height"]:g}"'
        f' rx="{board["corner_radius"]:g}" fill="{board["background"]}"'
        f' stroke="{board["stroke"]}" stroke-width="{board["stroke_width"]:g}"/>'
    )


def _render_banner(banner: dict, label: str, layout: dict) -> str:
    palette = layout["palette"]
    notch = layout["banner_notch"]
    left = banner["x"]
    right = left + banner["width"]
    top = banner["y"]
    bottom = top + banner["height"]
    middle = top + banner["height"] / 2.0
    path = (
        f"M {left:.1f},{top:.1f} L {right:.1f},{top:.1f} L {right - notch:.1f},{middle:.1f}"
        f" L {right:.1f},{bottom:.1f} L {left:.1f},{bottom:.1f} L {left + notch:.1f},{middle:.1f} Z"
    )
    text_x = (left + right) / 2.0
    text_y = top + layout["banner_text_offset"]
    return (
        f'<path d="{path}" fill="{palette["banner_fill"]}" stroke="{palette["banner_stroke"]}"'
        ' stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="middle"'
        ' font-family="Georgia, serif" font-size="11" font-weight="bold"'
        f' fill="{palette["ink"]}">{escape(label)}</text>'
    )


def _render_token(cx: float, cy: float, radius: float, layout: dict, *, visible: bool) -> str:
    palette = layout["palette"]
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:g}" fill="{palette["token_fill"]}"'
        f' stroke="{palette["line"]}" stroke-width="1.2" opacity="{1 if visible else 0}"/>'
    )


def _render_slot_row(slots: list[dict], filled: int, layout: dict) -> list[str]:
    radius = layout["token_radius"]
    return [
        _render_token(slot["cx"], slot["cy"], radius, layout, visible=index < filled)
        for index, slot in enumerate(slots)
    ]


def _render_wheat_icon(cx: float, cy: float, ink: str) -> str:
    root_x = cx + _WHEAT_ROOT[0]
    root_y = cy + _WHEAT_ROOT[1]
    parts = []
    for tip_dx, tip_dy, rotation in _WHEAT_STALKS:
        tip_x = cx + tip_dx
        tip_y = cy + tip_dy
        parts.append(
            f'<line x1="{root_x:.1f}" y1="{root_y:.1f}" x2="{tip_x:.1f}" y2="{tip_y:.1f}"'
            f' stroke="{ink}" stroke-width="1.20" stroke-linecap="round"/>'
        )
        parts.append(
            f'<ellipse cx="{tip_x:.1f}" cy="{tip_y:.1f}" rx="{_WHEAT_EAR_RX:.2f}"'
            f' ry="{_WHEAT_EAR_RY:.2f}" fill="{ink}"'
            f' transform="rotate({rotation} {tip_x:.1f} {tip_y:.1f})"/>'
        )
    base_y = cy + _WHEAT_BASE_DY
    parts.append(
        f'<line x1="{cx - _WHEAT_BASE_HALF_WIDTH:.1f}" y1="{base_y:.1f}"'
        f' x2="{cx + _WHEAT_BASE_HALF_WIDTH:.1f}" y2="{base_y:.1f}"'
        f' stroke="{ink}" stroke-width="1.20"/>'
    )
    return "".join(parts)


def _render_stone_icon(cx: float, cy: float, ink: str) -> str:
    parts = []
    for offsets, fill_opacity in _STONE_FACES:
        corners = [(cx + dx, cy + dy) for dx, dy in offsets]
        head = f"M {corners[0][0]:.1f},{corners[0][1]:.1f}"
        tail = " ".join(f"L {px:.1f},{py:.1f}" for px, py in corners[1:])
        parts.append(
            f'<path d="{head} {tail} Z" fill="{ink}" fill-opacity="{fill_opacity}"'
            f' stroke="{ink}" stroke-width="1" stroke-linejoin="round"/>'
        )
    return "".join(parts)


def _render_silver_icon(cx: float, cy: float, ink: str) -> str:
    coin_y = cy + _SILVER_DY
    half = _SILVER_CROSS_HALF_LENGTH
    return (
        f'<circle cx="{cx:.1f}" cy="{coin_y:.1f}" r="{_SILVER_OUTER_RADIUS:.2f}" fill="none"'
        f' stroke="{ink}" stroke-width="1.45"/>'
        f'<circle cx="{cx:.1f}" cy="{coin_y:.1f}" r="{_SILVER_INNER_RADIUS:.2f}" fill="none"'
        f' stroke="{ink}" stroke-width="1.00"/>'
        f'<line x1="{cx - half:.1f}" y1="{coin_y:.1f}" x2="{cx + half:.1f}" y2="{coin_y:.1f}"'
        f' stroke="{ink}" stroke-width="1.00"/>'
        f'<line x1="{cx:.1f}" y1="{coin_y - half:.1f}" x2="{cx:.1f}" y2="{coin_y + half:.1f}"'
        f' stroke="{ink}" stroke-width="1.00"/>'
    )


_ICON_RENDERERS = {
    "wheat": _render_wheat_icon,
    "stone": _render_stone_icon,
    "silver": _render_silver_icon,
}


def _render_resource(resource: dict, count: int, layout: dict) -> str:
    palette = layout["palette"]
    cx = resource["cx"]
    cy = resource["cy"]
    icon = resource["icon"]
    if icon not in _ICON_RENDERERS:
        raise KeyError(f"unknown resource icon: {icon}")
    count_y = cy + layout["resource_count_offset"]
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{layout["resource_radius"]:g}"'
        f' fill="{palette["panel_fill"]}" stroke="{palette["line"]}" stroke-width="2"/>'
        + _ICON_RENDERERS[icon](cx, cy, palette["ink"])
        + f'<text x="{cx:.1f}" y="{count_y:.1f}" text-anchor="middle"'
        ' font-family="Helvetica, Arial, sans-serif" font-size="9" font-weight="700"'
        f' fill="{palette["ink"]}">{escape(str(count))}</text>'
    )


def _render_special_activity(activity: dict, layout: dict) -> str:
    palette = layout["palette"]
    cx = activity["cx"]
    cy = activity["cy"]
    lines = _label_lines(activity["label"])
    line_height = layout["special_activity_line_height"]
    first_y = cy + layout["special_activity_label_offset"] - (len(lines) - 1) * line_height / 2.0
    parts = [
        f'<path d="{_hex_path_data(cx, cy, layout["hex_radius"])}"'
        f' fill="{palette["panel_fill"]}" stroke="{palette["line"]}" stroke-width="2"'
        ' stroke-linejoin="round"/>'
    ]
    for index, line in enumerate(lines):
        parts.append(
            f'<text x="{cx:.1f}" y="{first_y + index * line_height:.1f}" text-anchor="middle"'
            ' font-family="Helvetica, Arial, sans-serif" font-size="8" font-weight="700"'
            f' fill="{palette["ink"]}">{escape(line)}</text>'
        )
    return "".join(parts)


def _render_special_activity_tokens(activity: dict, count: int, layout: dict) -> list[str]:
    spacing = layout["special_activity_token_spacing"]
    token_y = activity["cy"] + layout["special_activity_token_offset"]
    radius = layout["token_radius"]
    palette = layout["palette"]
    tokens = []
    for index in range(count):
        token_x = activity["cx"] + (index - (count - 1) / 2.0) * spacing
        tokens.append(
            f'<circle cx="{token_x:.1f}" cy="{token_y:.1f}" r="{radius:g}"'
            f' fill="{palette["token_fill"]}" stroke="{palette["line"]}" stroke-width="1.2"/>'
        )
    return tokens


def _render_building_slot(slot: dict, layout: dict) -> str:
    palette = layout["palette"]
    return (
        f'<path d="{_hex_path_data(slot["cx"], slot["cy"], layout["hex_radius"])}"'
        f' fill="{palette["slot_fill"]}" stroke="{palette["slot_stroke"]}" stroke-width="2"'
        f' stroke-dasharray="{layout["building_slot_dash_array"]}" stroke-linejoin="round"/>'
    )


def _banner_label(banner: dict, player_state: dict) -> str:
    if banner["id"] == "player":
        return str(player_state.get("player_label", banner["label"]))
    return str(banner["label"])


def render_player_board_svg(layout: dict, player_state: dict | None = None) -> str:
    state = default_player_state() if player_state is None else player_state
    board = layout["board"]
    resource_counts = state.get("resources", {})
    occupied = state.get("occupied_special_activities", {})

    parts = [_render_board(layout)]
    for banner in layout["banners"]:
        parts.append(_render_banner(banner, _banner_label(banner, state), layout))

    parts.extend(
        _render_slot_row(layout["village_slots"], int(state.get("village_count", 0)), layout)
    )
    parts.extend(_render_slot_row(layout["abbey_slots"], int(state.get("abbey_count", 0)), layout))

    for resource in layout["resources"]:
        parts.append(
            _render_resource(resource, int(resource_counts.get(resource["id"], 0)), layout)
        )

    for activity in layout["special_activities"]:
        parts.append(_render_special_activity(activity, layout))
    for activity in layout["special_activities"]:
        count = int(occupied.get(activity["id"], 0))
        parts.extend(_render_special_activity_tokens(activity, count, layout))

    for slot in layout["building_slots"]:
        parts.append(_render_building_slot(slot, layout))

    body = "".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{board["view_box"]}"'
        f' width="{board["width"]:g}" height="{board["height"]:g}">{body}</svg>'
    )


def render_player_board_html(layout: dict, player_state: dict | None = None) -> str:
    svg = render_player_board_svg(layout, player_state)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Player Board (generated)</title>
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
  h1 {{ font-family: Georgia, serif; font-size: 24px; color: #F2EEDF; margin: 0 0 2px; }}
  p.subtitle {{
    color: #A8A296;
    font-size: 13px;
    margin: 0 0 18px;
    text-align: center;
    max-width: 640px;
  }}
  .board-wrap {{
    background: {PAGE_BACKGROUND}; border: 1px solid #333333; border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5); padding: 10px;
  }}
  svg {{ display: block; max-width: 95vw; height: auto; }}
</style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="subtitle">{escape(SUBTITLE)} Generated from {LAYOUT_FILENAME}.</p>
  <div class="board-wrap">{svg}</div>
</body>
</html>
"""
