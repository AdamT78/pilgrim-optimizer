"""Structured renderer for the duty wheel debug view.

The duty wheel holds the duty tiles away from the map so the map stays readable: eight duty
spaces ringed around a central City on a green hexagon, joined by clockwise ring arrows and four
arrows running to and from the middle. Each duty shows the cubes standing on it as four columns
on a shared baseline, and most of them carry a capsule with a Tithe token icon.

Two pieces of the picture are named here so a later renderer does not have to guess:

- the purple disc is the **Merchant token**, drawn on whichever duty `merchant_token.starts_on`
  names (Produce, for now);
- the resource icons in the capsules are **Tithe tokens**.

Neither moves. This module draws one fixed picture: there is no Merchant movement, no skipping
of Taxation, no Tithe token logic, and no sowing. It is a debug/visual tool that reads
`duty_wheel_layout.json` and emits SVG/HTML, connected to nothing.

Geometry mirrors `prototypes/duty_wheel.svg`, which stays the visual baseline. Every space is
placed from one anchor, the centre of its arc, and everything else on that space — the flat-top
capsule outline, the title, the cube tally, the Tithe capsule, the ornaments — is a fixed offset
from it. The layout JSON says what a space carries and where its anchor sits; this module says
how the pieces around that anchor are drawn. The three traced artwork paths (the two arrow
silhouettes and the cornucopia horn) live in the JSON too, since they are shapes nobody derives.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

LAYOUT_FILENAME = "duty_wheel_layout.json"

# One space: a flat top with a round bottom, the arc centre acting as its anchor.
SPACE_RADIUS = 101.5
SPACE_STROKE_WIDTH = 2.438679
LABEL_OFFSET_Y = -50.7
LABEL_FONT_SIZE = 15.5

# Cube tally: four columns on a shared baseline, one per player, kept even at zero so the
# stack tops stay comparable across spaces.
CUBE_SIZE = 13.0
CUBE_CELL_HEIGHT = 18.0
CUBE_COLUMN_WIDTH = 22.0
CUBE_STACK_LIMIT = 3
TALLY_OFFSET_Y = 19.0

# Tithe capsule: a stadium under the title, its left cap holding the Tithe token icon and its
# right cap the Merchant token when the Merchant stands here.
CAPSULE_OFFSET_Y = 34.0
CAPSULE_CAP_RADIUS = 24.0
CAPSULE_WAIST = 44.0

# Ornament: the inset margin and the trefoil above each title. It is identical on all nine
# spaces on purpose — a mark that never varies cannot be read as per-space meaning.
ORNAMENT_INSET = 7.5
ORNAMENT_HEADER_OFFSET_Y = -78.0
ORNAMENT_TREFOIL_RADIUS = 4.6
ORNAMENT_RULE_GAP = 15.0

RING_ARROW_COUNT = 8

_WHEAT_STALKS = (
    (-8.2, -10.8, -6.8, -9.4, -22),
    (-4.6, -13.0, -3.8, -11.3, -10),
    (0.9, -13.8, 0.6, -12.1, 2),
    (5.9, -12.3, 4.7, -10.8, 14),
    (9.6, -9.1, 8.0, -7.6, 24),
)
_STONE_FACES = (
    ("M 0,-17.3 L 8.8,-12.3 L 0,-7.3 L -8.8,-12.3 Z", "0.9"),
    ("M 8.8,-12.3 L 8.8,-2.3 L 0,2.7 L 0,-7.3 Z", "0.55"),
    ("M -8.8,-12.3 L 0,-7.3 L 0,2.7 L -8.8,-2.3 Z", "0.75"),
)
_CORNUCOPIA_FRUIT = ((9.48, -7.31, 2.94), (4.98, -11.18, 2.10), (10.95, -1.69, 2.03))


def _num(value: float) -> str:
    """A layout value written out as given, so nothing is lost to formatting."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _class_name(duty_id: str, suffix: str) -> str:
    return f"{duty_id.replace('_', '-')}-{suffix}"


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def load_duty_wheel_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def duties_of(layout: dict) -> list[dict]:
    return list(layout["duties"])


def duty_position_by_id(layout: dict, duty_id: str) -> dict:
    for duty in duties_of(layout):
        if duty["id"] == duty_id:
            return duty
    raise KeyError(f"unknown duty: {duty_id!r}")


def ring_duties(layout: dict) -> list[dict]:
    """The eight duties around the City, clockwise from the top."""
    return [duty_position_by_id(layout, duty_id) for duty_id in layout["clockwise_order"]]


def default_duty_wheel_state(layout: dict) -> dict:
    """The cubes the baseline shows standing on each duty.

    This is sample debug state, not `GameState`: it is what a debug page has to draw before
    anything real is wired up.
    """
    player_ids = [player["id"] for player in layout["players"]]
    return {
        duty["id"]: {
            player_id: int(duty.get("sample_cubes", {}).get(player_id, 0))
            for player_id in player_ids
        }
        for duty in duties_of(layout)
    }


def space_path_data(cx: float, cy: float, radius: float = SPACE_RADIUS) -> str:
    """A flat top on the arc centre's level, closed by a half circle below it."""
    top = cy - radius
    return (
        f"M {cx - radius:.1f},{top:.1f} H {cx + radius:.1f} V {cy:.1f}"
        f" A {radius:.1f},{radius:.1f} 0 0 1 {cx - radius:.1f},{cy:.1f} V {top:.1f} Z"
    )


def _render_space(duty: dict) -> str:
    cx, cy = duty["center"]
    return (
        f'<path d="{space_path_data(cx, cy)}" class="board-circle"/>'
        f'<text x="{cx:.1f}" y="{cy + LABEL_OFFSET_Y:.1f}"'
        f' class="circle-label">{escape(duty["label"])}</text>'
    )


def render_cube_tally(layout: dict, duty: dict, counts: dict) -> str:
    """The cubes standing on one duty, one column per player, growing up from the baseline."""
    cx, cy = duty["center"]
    players = layout["players"]
    width = len(players) * CUBE_COLUMN_WIDTH
    left = cx - width / 2
    baseline = cy + TALLY_OFFSET_Y
    ink = layout["palette"]["ink"]

    parts = [
        f'<line x1="{left:.1f}" y1="{baseline:.1f}" x2="{left + width:.1f}" y2="{baseline:.1f}"'
        f' stroke="{ink}" stroke-opacity="0.55" stroke-width="1.6" stroke-linecap="round"/>'
    ]
    for column, player in enumerate(players):
        x = left + column * CUBE_COLUMN_WIDTH + (CUBE_COLUMN_WIDTH - CUBE_SIZE) / 2
        for index in range(min(int(counts.get(player["id"], 0)), CUBE_STACK_LIMIT)):
            y = baseline - (index + 1) * CUBE_CELL_HEIGHT + (CUBE_CELL_HEIGHT - CUBE_SIZE) / 2
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{CUBE_SIZE:g}" height="{CUBE_SIZE:g}"'
                f' fill="{player["fill"]}" stroke="#000000"'
                f' stroke-width="{player["cube_stroke_width"]:g}"'
                f' data-player="{player["id"]}"/>'
            )
    return (
        f'<g class="{_class_name(duty["id"], "cube-tally")}" data-cube-tally="{duty["id"]}"'
        f' aria-label="cube counts">{"".join(parts)}</g>'
    )


def _capsule_path_data(cx: float, cy: float) -> str:
    left = cx - CAPSULE_WAIST / 2
    right = cx + CAPSULE_WAIST / 2
    top = cy + CAPSULE_OFFSET_Y
    bottom = top + 2 * CAPSULE_CAP_RADIUS
    radius = f"{CAPSULE_CAP_RADIUS:g},{CAPSULE_CAP_RADIUS:g}"
    return (
        f"M {left:.1f},{top:.1f} H {right:.1f} A {radius} 0 0 1 {right:.1f},{bottom:.1f}"
        f" H {left:.1f} A {radius} 0 0 1 {left:.1f},{top:.1f} Z"
    )


def _capsule_caps(cx: float, cy: float) -> tuple[float, float, float]:
    """Where the two cap centres sit: the Tithe icon's, the Merchant's, and their shared level."""
    cap_y = cy + CAPSULE_OFFSET_Y + CAPSULE_CAP_RADIUS
    return cx - CAPSULE_WAIST / 2, cx + CAPSULE_WAIST / 2, cap_y


def _icon_coin(ink: str) -> str:
    return (
        f'<circle cx="0" cy="0" r="9.6" fill="none" stroke="{ink}" stroke-width="1.45"/>'
        f'<circle cx="0" cy="0" r="6.55" fill="none" stroke="{ink}" stroke-width="0.98"/>'
        f'<line x1="2.0" y1="-4.8" x2="6.2" y2="-4.8" stroke="{ink}" stroke-width="1.08"'
        ' stroke-linecap="round"/>'
        f'<line x1="4.1" y1="-6.9" x2="4.1" y2="-2.7" stroke="{ink}" stroke-width="1.08"'
        ' stroke-linecap="round"/>'
    )


def _icon_stone(ink: str) -> str:
    return "".join(
        f'<path d="{face}" fill="{ink}" fill-opacity="{opacity}" stroke="{ink}"'
        ' stroke-width="1.0" stroke-linejoin="round"/>'
        for face, opacity in _STONE_FACES
    )


def _icon_wheat(ink: str) -> str:
    parts = []
    for tip_x, tip_y, seed_x, seed_y, angle in _WHEAT_STALKS:
        parts.append(
            f'<line x1="0" y1="7.0" x2="{tip_x:.1f}" y2="{tip_y:.1f}" stroke="{ink}"'
            ' stroke-width="1.35" stroke-linecap="round"/>'
        )
        parts.append(
            f'<ellipse cx="{seed_x:.1f}" cy="{seed_y:.1f}" rx="1.95" ry="3.25" fill="{ink}"'
            f' transform="rotate({angle:g} {seed_x:.1f} {seed_y:.1f})"/>'
        )
    parts.append(f'<line x1="-5.2" y1="8.0" x2="5.2" y2="8.0" stroke="{ink}" stroke-width="1.46"/>')
    return "".join(parts)


def _icon_cornucopia(ink: str, horn_path: str) -> str:
    fruit = "".join(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="none" stroke="{ink}"'
        ' stroke-width="1.4"/>'
        for cx, cy, r in _CORNUCOPIA_FRUIT
    )
    return (
        f'<path d="{horn_path}" fill="none" stroke="{ink}" stroke-width="1.7"'
        ' stroke-linecap="round" stroke-linejoin="round"/>'
        '<ellipse cx="2.21" cy="-3.11" rx="7.0" ry="3.15"'
        f' transform="rotate(-120.0 2.21 -3.11)" fill="none" stroke="{ink}" stroke-width="1.6"/>'
        + fruit
    )


_ICON_BODIES = {"coin": _icon_coin, "stone": _icon_stone, "wheat": _icon_wheat}


def render_tithe_icon(layout: dict, icon_id: str, cx: float, cy: float) -> str:
    """One Tithe token icon, drawn at its own scale in the left cap of a duty's capsule."""
    spec = layout["tithe_icons"][icon_id]
    ink = layout["palette"]["ink"]
    if icon_id == "cornucopia":
        body = _icon_cornucopia(ink, layout["artwork"]["cornucopia_horn_path"])
    elif icon_id in _ICON_BODIES:
        body = _ICON_BODIES[icon_id](ink)
    else:
        raise KeyError(f"unknown tithe icon: {icon_id!r}")
    return (
        f'<g class="{icon_id}-icon" data-tithe-token="{icon_id}"'
        f' transform="translate({cx:.1f} {cy + spec["offset_y"]:.1f}) scale({spec["scale"]:g})"'
        f' aria-label="{escape(spec["label"])}">{body}</g>'
    )


def render_merchant_token(layout: dict, cx: float, cy: float) -> str:
    """The purple disc. It sits where the layout says and does not move."""
    merchant = layout["merchant_token"]
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CAPSULE_CAP_RADIUS:g}"'
        f' fill="{merchant["color"]}" stroke="{merchant["edge"]}" stroke-width="2"'
        f' data-token="merchant" aria-label="{escape(merchant["label"])}"/>'
    )


def _render_tithe_capsule(layout: dict, duty: dict, icon_id: str, merchant: bool) -> str:
    """The capsule under a duty's title: its Tithe token, and the Merchant when he stands here.

    With the Merchant present the two discs are drawn clipped to the capsule, so the pair reads
    as one joined shape with a single outline rather than two circles that happen to touch.
    """
    palette = layout["palette"]
    tithe_x, merchant_x, cap_y = _capsule_caps(*duty["center"])
    capsule = _capsule_path_data(*duty["center"])
    stroke = f'stroke="{palette["capsule_edge"]}" stroke-width="2" stroke-linecap="round"'

    if merchant:
        shape = (
            f'<g clip-path="url(#{duty["id"]}-capsule-clip)">'
            f'<circle cx="{tithe_x:.1f}" cy="{cap_y:.1f}" r="{CAPSULE_CAP_RADIUS:g}"'
            f' fill="{palette["capsule_fill"]}"/>'
            f"{render_merchant_token(layout, merchant_x, cap_y)}</g>"
            f'<path d="{capsule}" fill="none" {stroke} stroke-linejoin="round"/>'
        )
    else:
        shape = (
            f'<path d="{capsule}" fill="{palette["capsule_fill"]}" {stroke}'
            ' stroke-linejoin="round"/>'
        )
    icon = render_tithe_icon(layout, icon_id, tithe_x, cap_y)
    return f'<g class="{_class_name(duty["id"], "tithe-shape")}">{shape}{icon}</g>'


def render_duty_space(layout: dict, duty: dict, counts: dict, merchant: bool = False) -> str:
    """One duty: its space, title, cube tally, and the capsule holding its Tithe token."""
    parts = [_render_space(duty)]
    if duty["id"] != layout["city_id"]:
        parts.append(render_cube_tally(layout, duty, counts))
    icon_id = duty.get("tithe_icon")
    if icon_id:
        parts.append(_render_tithe_capsule(layout, duty, icon_id, merchant))
    return f'<g data-duty="{duty["id"]}">{"".join(parts)}</g>'


def _render_ornaments(layout: dict) -> str:
    """The inset margin and the trefoil rule above each title, identical on all nine spaces."""
    ink = layout["palette"]["ink"]
    insets, headers = [], []
    for duty in duties_of(layout):
        cx, cy = duty["center"]
        radius = SPACE_RADIUS - ORNAMENT_INSET
        insets.append(
            f'<path d="{space_path_data(cx, cy, radius)}" fill="none" stroke="{ink}"'
            ' stroke-opacity="0.28" stroke-width="1.2"/>'
        )
        y = cy + ORNAMENT_HEADER_OFFSET_Y
        lobes = "".join(
            f'<circle cx="{cx + ORNAMENT_TREFOIL_RADIUS * math.cos(math.radians(angle)):.1f}"'
            f' cy="{y + ORNAMENT_TREFOIL_RADIUS * math.sin(math.radians(angle)):.1f}"'
            f' r="{ORNAMENT_TREFOIL_RADIUS:g}"/>'
            for angle in (-90, 30, 150)
        )
        half = len(layout["players"]) * CUBE_COLUMN_WIDTH / 2
        headers.append(
            f'<g fill="none" stroke="{ink}" stroke-opacity="0.34" stroke-width="1.3"'
            f' stroke-linecap="round">{lobes}'
            f'<path d="M {cx - half:.1f},{y:.1f} H {cx - ORNAMENT_RULE_GAP:.1f}'
            f' M {cx + ORNAMENT_RULE_GAP:.1f},{y:.1f} H {cx + half:.1f}"/></g>'
        )
    return (
        f'<g class="ornament-inset" aria-hidden="true">{"".join(insets)}</g>'
        f'<g class="ornament-header" aria-hidden="true">{"".join(headers)}</g>'
    )


def _render_ring_arrows(layout: dict) -> str:
    cx, cy = layout["board"]["center"]
    path = layout["artwork"]["ring_arrow_path"]
    step = 360 // RING_ARROW_COUNT
    return (
        '<g aria-label="Clockwise outer arrows">'
        + "".join(
            f'<g transform="rotate({index * step:g} {_num(cx)} {_num(cy)})"'
            f' data-ring-arrow="{index}">'
            f'<path d="{path}" class="arrow-border"/><path d="{path}" class="arrow-interior"/></g>'
            for index in range(RING_ARROW_COUNT)
        )
        + "</g>"
    )


def _render_middle_arrows(layout: dict) -> str:
    path = layout["artwork"]["middle_arrow_path"]
    arrows = []
    for arrow in layout["middle_arrows"]:
        x, y = arrow["at"]
        transform = f"translate({_num(x)} {_num(y)})"
        if arrow["rotate"]:
            transform += f" rotate({arrow['rotate']:g})"
        arrows.append(
            f'<g transform="{transform}" data-middle-arrow="{arrow["id"]}"'
            f' data-toward="{arrow["toward"]}">'
            f'<path d="{path}" class="arrow-border"/><path d="{path}" class="arrow-interior"/></g>'
        )
    return '<g aria-label="Middle directional arrows">' + "".join(arrows) + "</g>"


_STYLE_TEMPLATE = (
    ".board-circle {{ fill: url(#parchment-gradient); stroke: {space_edge};"
    " stroke-width: {space_stroke_width}; }}"
    '.circle-label {{ fill: {ink}; font-family: Georgia, "Times New Roman", serif;'
    " font-size: {label_font_size:g}px; font-weight: 700; text-anchor: middle;"
    " dominant-baseline: middle; }}"
    ".arrow-border {{ fill: none; stroke: {arrow_border}; stroke-width: 6;"
    " stroke-linecap: round; stroke-linejoin: round; }}"
    ".arrow-interior {{ fill: {arrow_interior}; stroke: none; }}"
)


def _render_defs(layout: dict, merchant_duty_id: str) -> str:
    palette = layout["palette"]
    parchment_from, parchment_to = palette["parchment"]
    ground_from, ground_to = palette["ground"]
    clip = ""
    if merchant_duty_id:
        cx, cy = duty_position_by_id(layout, merchant_duty_id)["center"]
        clip = (
            f'<clipPath id="{merchant_duty_id}-capsule-clip">'
            f'<path d="{_capsule_path_data(cx, cy)}"/></clipPath>'
        )
    style = _STYLE_TEMPLATE.format(
        space_edge=palette["space_edge"],
        space_stroke_width=_num(SPACE_STROKE_WIDTH),
        ink=palette["ink"],
        label_font_size=LABEL_FONT_SIZE,
        arrow_border=palette["arrow_border"],
        arrow_interior=palette["arrow_interior"],
    )
    return (
        "<defs>"
        '<radialGradient id="parchment-gradient" cx="42%" cy="35%" r="72%">'
        f'<stop offset="0%" stop-color="{parchment_from}"/>'
        f'<stop offset="100%" stop-color="{parchment_to}"/></radialGradient>'
        '<radialGradient id="hex-gradient" cx="50%" cy="44%" r="70%">'
        f'<stop offset="0%" stop-color="{ground_from}"/>'
        f'<stop offset="100%" stop-color="{ground_to}"/></radialGradient>'
        f"{clip}<style>{style}</style></defs>"
    )


def render_duty_wheel_svg(layout: dict, board_state: dict | None = None) -> str:
    """The whole board: title, ground, arrows, and the nine spaces with their contents."""
    board = layout["board"]
    palette = layout["palette"]
    page = layout["page"]
    state = default_duty_wheel_state(layout) if board_state is None else board_state
    merchant_duty_id = layout["merchant_token"]["starts_on"]
    cx, cy = board["center"]
    frame = board["frame"]

    subtitle = "".join(
        f'<tspan x="{board["width"] / 2:g}" dy="{0 if index == 0 else 17:g}">{escape(line)}</tspan>'
        for index, line in enumerate(page["subtitle"])
    )

    spaces = [_render_space(duty_position_by_id(layout, layout["city_id"]))]
    for duty in ring_duties(layout):
        spaces.append(
            render_duty_space(
                layout,
                duty,
                state.get(duty["id"], {}),
                merchant=duty["id"] == merchant_duty_id,
            )
        )
    spaces.append(_render_ornaments(layout))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{board["width"]:g}"'
        f' height="{board["height"]:g}" viewBox="{board["view_box"]}" role="img"'
        ' aria-labelledby="svg-title svg-description" data-component="duty-wheel"'
        f' data-merchant-token="{merchant_duty_id}">'
        f'<title id="svg-title">{escape(page["board_title"])}</title>'
        f'<desc id="svg-description">{escape(page["description"])}</desc>'
        f"{_render_defs(layout, merchant_duty_id)}"
        f'<rect width="{board["width"]:g}" height="{board["height"]:g}"'
        f' fill="{palette["page_background"]}"/>'
        f'<rect x="{frame["x"]:g}" y="{frame["y"]:g}" width="{frame["width"]:g}"'
        f' height="{frame["height"]:g}" rx="{frame["corner_radius"]:g}" fill="none"'
        f' stroke="{palette["frame_stroke"]}" stroke-width="1.5"/>'
        f'<text x="{board["width"] / 2:g}" y="{board["title_baseline"]:g}"'
        f' fill="{palette["title"]}" font-family="Georgia, \'Times New Roman\', serif"'
        f' font-size="30" font-weight="700" text-anchor="middle">'
        f'{escape(page["board_title"])}</text>'
        f'<text x="{board["width"] / 2:g}" y="{board["subtitle_baseline"]:g}"'
        f' fill="{palette["subtitle"]}" font-family="Helvetica, Arial, sans-serif"'
        f' font-size="13.5" text-anchor="middle">{subtitle}</text>'
        f'<g transform="translate({_num(cx)} {_num(cy)})'
        f' scale({_num(board["scale"])}) translate({_num(-cx)} {_num(-cy)})">'
        f'<path d="{board["ground_path"]}" fill="url(#hex-gradient)"'
        f' stroke="{palette["ground_edge"]}" stroke-width="4" stroke-linejoin="round"/>'
        f"{_render_ring_arrows(layout)}{_render_middle_arrows(layout)}"
        f'<g aria-label="Board spaces">{"".join(spaces)}</g>'
        "</g></svg>"
    )


def render_duty_wheel_html(layout: dict, board_state: dict | None = None) -> str:
    """The board on its own page, the way the baseline prototype presents it."""
    palette = layout["palette"]
    merchant = layout["merchant_token"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Pilgrim — Duty Wheel (generated)</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ min-height: 100%; margin: 0; background: {palette["page_background"]}; }}
  body {{
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: Helvetica, Arial, sans-serif;
  }}
  svg {{ display: block; width: min(100vw, {layout["board"]["width"]:g}px); height: auto; }}
  p.note {{
    color: #A8A296;
    font-size: 13px;
    margin: 0 0 32px;
    padding: 0 16px;
    text-align: center;
    max-width: 720px;
  }}
</style>
</head>
<body>
{render_duty_wheel_svg(layout, board_state)}
  <p class="note">
    Generated from {LAYOUT_FILENAME}. The purple disc is the {escape(merchant["label"])} and the
    resource icons are Tithe tokens; neither moves yet. Visual/debug only — no GameState
    integration and no gameplay rules.
  </p>
</body>
</html>
"""
