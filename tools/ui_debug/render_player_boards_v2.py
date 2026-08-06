"""Structured renderer for the player board v2 debug view.

Four boards on one page — white, red, yellow, and blue — laid out in a 2x2 grid, each one a
parchment panel with the Village and Abbey banners, the starting worker tokens, three resource
readouts, six worker-role circles, six empty building slots, and a colour tag folded into the
top-right corner. The first-player marker card is drawn on whichever board is named first player.

This is a debug/visual tool only. It reads `player_boards_v2_layout.json` and emits SVG/HTML. It
is not connected to `GameState`, it does not decide who the first player is, and it implements no
game rules. It also does not replace `render_player_board.py`, which still draws the v1 board.

The board is six columns wide, and it is the building slots along the bottom that set how wide a
column is: they are the biggest thing on the board, being map hexes, and everything above them --
the banners, the resource readouts, the role circles -- lines up on the columns they make. The
layout JSON says what a board carries; this module says where it goes.

This is a wider board than `prototypes/player_boards_v2.html` draws. The prototype's slots were
about two thirds of a map hex, which left the bottom row looking like six placeholders rather than
six places a tile goes; sizing them properly is what pushed the columns apart. Nothing on the board
was rescaled to do it -- the cubes, the text and the role circles are the sizes they always were,
and the board is the height it always was -- so a board still renders at exactly the scale it used
to wherever it is shown.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

LAYOUT_FILENAME = "player_boards_v2_layout.json"
PAGE_BACKGROUND = "#000000"
BOARD_GAP = 60
DEFAULT_FIRST_PLAYER = "player_one"

# Cubes are serfs while they sit in the Village and acolytes once they reach the Abbey or a role
# circle. A role circle holds at most two acolytes: one centred, two side by side.
ROLE_ACOLYTE_LIMIT = 2

# A building slot is a map hex, and the two are drawn the same way -- flat-top, from the centre out
# to a corner -- so making a building tile the size on a board that it is on the map comes down to
# one number: how many cubes it measures across. That number is the map's:
#
#   a map hex is 46.0 map units across the radius, and a cube renders as 13.03 map units,
#   so a hex is 3.531 cubes; and a cube here is MARKER_CUBE units, so a slot is 3.531 * 14.0.
#
# Written out rather than read from `map_layout.json`, so that drawing a player board does not mean
# loading the map. The arithmetic is checked against the real map layout in the tests instead.
BUILDING_SLOT_HEX_SIZE = 49.4
# Clear air between neighbouring slots. The slots are the widest thing in a column, so this is what
# sets the column pitch and, through it, the width of the board.
BUILDING_SLOT_GAP = 10.0
# Clear air between the bottom of a role circle and the top of the slot below it.
BUILDING_ROW_GAP = 12.0

# A role circle's own radius. It is no longer the slot's: the slots grew and the circles did not.
ROLE_CIRCLE_RADIUS = 34.0

# Left of the first slot and right of the last, which is all the horizontal margin a board has.
SIDE_MARGIN = 25.0
PANEL_CORNER_RADIUS = 12
PANEL_STROKE_WIDTH = 2

BANNER_CENTER_Y = 30.0
BANNER_HEIGHT = 26.0
# Village and Abbey are set to read at the size the duty wheel sets its duty names -- Produce,
# Taxation, Give Alms and the rest. Same trick as the building slots: two boards drawn at
# different scales agree on screen when they agree in cubes, and a duty name is 15.5 units against
# that board's 13.0-unit cube, so 1.192 cubes, which is 1.192 * MARKER_CUBE here.
BANNER_FONT_SIZE = 16.7
BANNER_NOTCH_RATIO = 0.35
BANNER_TEXT_BASELINE_RATIO = 0.35

TOKEN_RADIUS = 7.0
TOKEN_GAP = 6.0
TOKEN_GRID_TOP_GAP = 12.0

# The role labels sit a fixed distance below the token grid, which leaves the resource readouts
# free to centre themselves in the gap without the two chasing each other.
ROLE_ROW_GAP_FROM_TOKENS = 130.0
# Both are properties of the type rather than choices, so every point of it on the board derives
# them from its own size: a line needs 1.1 times its size to sit clear of the next, and its glyphs
# reach 0.91 of it above their baseline. Measured at size 10, where they were written out as 11.0
# and 9.1.
LINE_HEIGHT_RATIO = 1.1
ASCENT_RATIO = 0.91

ROLE_FONT_SIZE = 14
ROLE_LINE_HEIGHT = LINE_HEIGHT_RATIO * ROLE_FONT_SIZE
LABEL_ASCENT = ASCENT_RATIO * ROLE_FONT_SIZE
ROLE_LABEL_GAP = 10.0

BUILDING_SLOT_DASH_ARRAY = "5,3"

# The icons are sized against the duty wheel, which draws these same three things, compared in
# cubes the way everything else here is. The wheat gets its own size because it needs one: it is
# the big shape of the three and the wheel's is 2.126 cubes tall, so sizing it off the other two
# left it visibly bigger than the wheel's -- the one difference here that is easy to see. At 17.26
# it matches the wheel's within a percent in both height and width.
WHEAT_ICON_SIZE = 17.26
# The stone and the coin land a touch under the wheel's 1.769 and 1.802 cubes rather than exactly
# on them, which is where they read right next to everything else on this board.
COMPACT_ICON_SIZE = 18.70

# How far each icon reaches below its own centre, per unit of the size it is asked for. The three
# are placed by their feet rather than their centres, so they stand on one line whatever sizes they
# are given and the amount below sits the same distance under each.
ICON_FOOT_RATIO = {"wheat": 0.6, "cube": 0.62, "coin": 0.62}

# The readout is an icon in the top of a circle with the amount under it. The circle is drawn to
# hold the tallest of the three with the margin it had before; that the two never touch and both
# stay inside the rim is checked rather than eyeballed.
RESOURCE_RADIUS = 33.5
RESOURCE_ICON_FOOT = 2.6
RESOURCE_COUNT_OFFSET = 25.0
RESOURCE_COUNT_FONT_SIZE = 16

MARKER_CUBE = 14.0
MARKER_CARD_MIN_WIDTH = 92.0
MARKER_CARD_PAD_X = 10.0
MARKER_CARD_PAD_Y = 8.0
MARKER_TEXT_TO_ICON_GAP = 6.0
# The card names itself on one line, so its label has to fit MARKER_CARD_MIN_WIDTH: "First player"
# comes to 86 units at this size, against the 92 the card allows.
MARKER_LABEL_FONT_SIZE = 16
MARKER_CARD_CORNER_RADIUS = 6
MARKER_SCALLOP_COUNT = 6

CORNER_TAG_SIZE = 48.0
# The tag runs a little past the panel edge so the clip path, not the raw triangle, is what draws
# the visible edge; the clip is inflated by the panel stroke's half width for the same reason.
CORNER_TAG_OVERSHOOT = 2.0
CORNER_CLIP_PAD = 1

_WHEAT_TIPS = ((-0.55, -0.65), (-0.25, -0.85), (0.05, -0.9), (0.35, -0.8), (0.6, -0.55))
_CUBE_FACE_OPACITIES = ("0.9", "0.55", "0.75")


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / LAYOUT_FILENAME


def load_player_boards_v2_layout(path: Path | None = None) -> dict:
    layout_path = default_layout_path() if path is None else Path(path)
    return json.loads(layout_path.read_text(encoding="utf-8"))


def players_of(layout: dict) -> list[dict]:
    return list(layout["players"])


def player_by_id(layout: dict, player_id: str) -> dict:
    for player in players_of(layout):
        if player["id"] == player_id:
            return player
    raise KeyError(f"unknown player: {player_id!r}")


def banner_by_id(layout: dict, banner_id: str) -> dict:
    for banner in layout["banners"]:
        if banner["id"] == banner_id:
            return banner
    raise KeyError(f"unknown banner: {banner_id!r}")


def default_player_board_v2_state(layout: dict) -> dict:
    """The board the baseline draws: serfs in the Village, acolytes in the Abbey and on two roles.

    One of these per player is all the state a board has. Nothing here is `GameState`; it is what
    a debug page moves cubes around in.
    """
    roles = {role["id"]: 0 for role in layout["worker_roles"]}
    roles.update({role_id: int(count) for role_id, count in layout["placed_workers"].items()})
    return {
        "village_serfs": int(banner_by_id(layout, "village")["visible_workers"]),
        "abbey_acolytes": int(banner_by_id(layout, "abbey")["visible_workers"]),
        "roles": roles,
    }


def building_slot_centers(layout: dict) -> list[tuple[float, float]]:
    """Where the six bottom building slots sit, left to right — slot 1 is the first of them."""
    geometry = board_geometry(len(layout["worker_roles"]))
    return list(zip(geometry["role_x"], geometry["building_y"], strict=True))


def token_slot_count(layout: dict) -> int:
    """How many cubes the Village or Abbey grid has room for."""
    grid = layout["starting_worker_grid"]
    return int(grid["rows"]) * int(grid["columns"])


def wrap_label(label: str) -> list[str]:
    """One word stays on one line; anything longer splits into the most even two lines."""
    words = label.split()
    if len(words) == 1:
        return [label]
    splits = [(" ".join(words[:index]), " ".join(words[index:])) for index in range(1, len(words))]
    return list(min(splits, key=lambda pair: max(len(pair[0]), len(pair[1]))))


def hex_path_data(cx: float, cy: float, size: float = BUILDING_SLOT_HEX_SIZE) -> str:
    """A flat-top hexagon centred on (cx, cy), `size` from the centre out to a corner.

    The same convention the map draws its tiles with, which is what lets a slot and a tile be
    compared by their one number.
    """
    corners = [
        (
            cx + size * math.cos(math.radians(60 * index)),
            cy + size * math.sin(math.radians(60 * index)),
        )
        for index in range(6)
    ]
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in corners) + " Z"


def slot_apothem() -> float:
    """Half a slot's height. A flat-top hexagon is shorter than it is wide by this much."""
    return BUILDING_SLOT_HEX_SIZE * math.sqrt(3) / 2


def column_pitch() -> float:
    """Centre to centre between neighbouring columns, which the building slots set."""
    return 2 * BUILDING_SLOT_HEX_SIZE + BUILDING_SLOT_GAP


def board_geometry(role_count: int) -> dict:
    """Every coordinate a board needs.

    The building slots are the widest thing on a board, so they are what it is spaced around: one
    column per slot, and the banners, resource readouts and role circles all line up on those
    columns. Vertically nothing has moved -- the row of slots is deeper than it used to be, but it
    starts from the same role circles and ends on the same bottom margin.
    """
    pitch = column_pitch()
    role_x = [SIDE_MARGIN + BUILDING_SLOT_HEX_SIZE + index * pitch for index in range(role_count)]
    panel_width = role_x[-1] + BUILDING_SLOT_HEX_SIZE + SIDE_MARGIN

    token_top = BANNER_CENTER_Y + BANNER_HEIGHT / 2 + TOKEN_GRID_TOP_GAP
    tokens_bottom = token_top + 2 * 2 * TOKEN_RADIUS + TOKEN_GAP

    role_circle_top = tokens_bottom + ROLE_ROW_GAP_FROM_TOKENS
    role_baseline = role_circle_top - ROLE_LABEL_GAP
    label_top = role_baseline - ROLE_LINE_HEIGHT - LABEL_ASCENT

    # The slots hang off the bottom of the role circles, all six level with each other.
    building_cy = role_circle_top + 2 * ROLE_CIRCLE_RADIUS + BUILDING_ROW_GAP + slot_apothem()

    top_margin = BANNER_CENTER_Y - BANNER_HEIGHT / 2
    panel_height = building_cy + slot_apothem() + top_margin

    return {
        "panel_width": panel_width,
        "panel_height": panel_height,
        "role_x": role_x,
        "role_circle_cy": role_circle_top + ROLE_CIRCLE_RADIUS,
        "role_label_baseline": role_baseline,
        "token_grid_top": token_top,
        "resource_cy": (tokens_bottom + label_top) / 2,
        "building_y": [building_cy] * role_count,
    }


def banner_center_x(geometry: dict, first_role_index: int) -> tuple[float, float]:
    """A banner spans two whole columns, which is what makes them all the same width.

    Two columns, not two role circles: it is the columns the board is built on, and spanning them
    is what puts the outer banners' ends flush with the board's side margins.
    """
    left = geometry["role_x"][first_role_index] - BUILDING_SLOT_HEX_SIZE
    right = geometry["role_x"][first_role_index + 1] + BUILDING_SLOT_HEX_SIZE
    return (left + right) / 2, right - left


def banner_centers(layout: dict, geometry: dict) -> list[float]:
    return [
        banner_center_x(geometry, banner["first_role_index"])[0] for banner in layout["banners"]
    ]


def resource_centers(layout: dict, geometry: dict) -> list[float]:
    """The readouts keep the banners' rhythm: under each banner, then one step further right."""
    village_cx, abbey_cx = banner_centers(layout, geometry)
    step = abbey_cx - village_cx
    return [village_cx, abbey_cx, abbey_cx + step]


def _render_panel(geometry: dict, palette: dict) -> str:
    return (
        f'<rect x="0" y="0" width="{geometry["panel_width"]:.0f}"'
        f' height="{geometry["panel_height"]:.0f}" rx="{PANEL_CORNER_RADIUS:g}"'
        f' fill="{palette["panel_background"]}" stroke="{palette["parchment_edge"]}"'
        f' stroke-width="{PANEL_STROKE_WIDTH:g}"/>'
    )


def _render_banner(cx: float, width: float, label: str, palette: dict) -> str:
    left = cx - width / 2
    top = BANNER_CENTER_Y - BANNER_HEIGHT / 2
    right = left + width
    bottom = top + BANNER_HEIGHT
    middle = top + BANNER_HEIGHT / 2
    notch = BANNER_HEIGHT * BANNER_NOTCH_RATIO
    path = (
        f"M {left:.1f},{top:.1f} L {right:.1f},{top:.1f} L {right - notch:.1f},{middle:.1f}"
        f" L {right:.1f},{bottom:.1f} L {left:.1f},{bottom:.1f} L {left + notch:.1f},{middle:.1f} Z"
    )
    text_y = BANNER_CENTER_Y + BANNER_FONT_SIZE * BANNER_TEXT_BASELINE_RATIO
    return (
        f'<path d="{path}" fill="{palette["parchment"]}" stroke="{palette["parchment_edge"]}"'
        ' stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="{cx:.1f}" y="{text_y:.1f}" text-anchor="middle"'
        f' font-family="Georgia, serif" font-size="{BANNER_FONT_SIZE:g}" font-weight="bold"'
        f' fill="{palette["ink"]}">{escape(label)}</text>'
    )


def _render_square_token(
    cx: float, cy: float, player: dict, opacity: int = 1, tags: str = ""
) -> str:
    side = 2 * TOKEN_RADIUS
    return (
        f'<rect x="{cx - TOKEN_RADIUS:.1f}" y="{cy - TOKEN_RADIUS:.1f}" width="{side:.1f}"'
        f' height="{side:.1f}" fill="{player["fill"]}" stroke="{player["stroke"]}"'
        f' stroke-width="1.2" opacity="{opacity:g}"{tags}/>'
    )


def _render_token_grid(
    cx: float,
    top_y: float,
    rows: int,
    columns: int,
    visible: int,
    player: dict,
    tag: str = "",
) -> str:
    """The starting workers. Hidden tokens keep their slot so both grids stay the same shape."""
    step = 2 * TOKEN_RADIUS + TOKEN_GAP
    grid_width = columns * 2 * TOKEN_RADIUS + (columns - 1) * TOKEN_GAP
    first_x = cx - grid_width / 2 + TOKEN_RADIUS
    tokens = []
    for row in range(rows):
        token_y = top_y + TOKEN_RADIUS + row * step
        for column in range(columns):
            index = row * columns + column
            tags = f' data-token="{tag}" data-token-index="{index}"' if tag else ""
            tokens.append(
                _render_square_token(
                    first_x + column * step,
                    token_y,
                    player,
                    1 if index < visible else 0,
                    tags,
                )
            )
    return "".join(tokens)


def _render_role_label(cx: float, baseline: float, label: str, ink: str) -> str:
    """The role name above its circle, with the last line always the same distance from the rim."""
    lines = wrap_label(label)
    return "".join(
        f'<text x="{cx:.1f}" y="{baseline - (len(lines) - 1 - index) * ROLE_LINE_HEIGHT:.1f}"'
        ' text-anchor="middle" font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{ROLE_FONT_SIZE:g}" font-weight="700" fill="{ink}">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def _icon_wheat(cx: float, cy: float, size: float, ink: str) -> str:
    base_x, base_y = cx, cy + size * 0.55
    parts = []
    for dx, dy in _WHEAT_TIPS:
        tip_x, tip_y = cx + dx * size, cy + dy * size
        parts.append(
            f'<line x1="{base_x:.1f}" y1="{base_y:.1f}" x2="{tip_x:.1f}" y2="{tip_y:.1f}"'
            f' stroke="{ink}" stroke-width="{max(size * 0.09, 1.2):.2f}" stroke-linecap="round"/>'
        )
        parts.append(
            f'<ellipse cx="{tip_x:.1f}" cy="{tip_y:.1f}" rx="{size * 0.13:.2f}"'
            f' ry="{size * 0.22:.2f}" fill="{ink}"'
            f' transform="rotate({dx * 40:.0f} {tip_x:.1f} {tip_y:.1f})"/>'
        )
    parts.append(
        f'<line x1="{base_x - size * 0.3:.1f}" y1="{base_y + size * 0.05:.1f}"'
        f' x2="{base_x + size * 0.3:.1f}" y2="{base_y + size * 0.05:.1f}"'
        f' stroke="{ink}" stroke-width="{max(size * 0.1, 1.2):.2f}"/>'
    )
    return "".join(parts)


def _icon_cube(cx: float, cy: float, size: float, ink: str) -> str:
    half = size * 0.62
    wide = half * 0.87
    faces = (
        ((cx, cy - half), (cx + wide, cy - half * 0.5), (cx, cy), (cx - wide, cy - half * 0.5)),
        (
            (cx + wide, cy - half * 0.5),
            (cx + wide, cy + half * 0.5),
            (cx, cy + half),
            (cx, cy),
        ),
        (
            (cx - wide, cy - half * 0.5),
            (cx, cy),
            (cx, cy + half),
            (cx - wide, cy + half * 0.5),
        ),
    )
    parts = []
    for corners, opacity in zip(faces, _CUBE_FACE_OPACITIES, strict=True):
        path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in corners) + " Z"
        parts.append(
            f'<path d="{path}" fill="{ink}" fill-opacity="{opacity}" stroke="{ink}"'
            ' stroke-width="1" stroke-linejoin="round"/>'
        )
    return "".join(parts)


def _icon_coin(cx: float, cy: float, size: float, ink: str) -> str:
    radius = size * 0.62
    sparkle_x, sparkle_y = cx + radius * 0.42, cy - radius * 0.5
    arm = radius * 0.22
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.2f}" fill="none" stroke="{ink}"'
        f' stroke-width="{max(radius * 0.16, 1.3):.2f}"/>'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius * 0.68:.2f}" fill="none" stroke="{ink}"'
        f' stroke-width="{max(radius * 0.08, 0.9):.2f}"/>'
        f'<line x1="{sparkle_x - arm:.1f}" y1="{sparkle_y:.1f}" x2="{sparkle_x + arm:.1f}"'
        f' y2="{sparkle_y:.1f}" stroke="{ink}" stroke-width="1" stroke-linecap="round"/>'
        f'<line x1="{sparkle_x:.1f}" y1="{sparkle_y - arm:.1f}" x2="{sparkle_x:.1f}"'
        f' y2="{sparkle_y + arm:.1f}" stroke="{ink}" stroke-width="1" stroke-linecap="round"/>'
    )


_ICON_RENDERERS = {"wheat": _icon_wheat, "cube": _icon_cube, "coin": _icon_coin}


def resource_icon_size(icon: str) -> float:
    """How big a resource icon is drawn. The wheat is sized on its own; the other two share one."""
    return WHEAT_ICON_SIZE if icon == "wheat" else COMPACT_ICON_SIZE


def resource_icon_center_y(icon: str) -> float:
    """An icon's centre, relative to its circle's, standing it on the shared foot line."""
    return RESOURCE_ICON_FOOT - ICON_FOOT_RATIO[icon] * resource_icon_size(icon)


def _render_resource(cx: float, cy: float, resource: dict, palette: dict) -> str:
    icon = resource["icon"]
    if icon not in _ICON_RENDERERS:
        raise KeyError(f"unknown resource icon: {icon}")
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{RESOURCE_RADIUS:g}"'
        f' fill="{palette["worker_fill"]}" stroke="{palette["worker_edge"]}" stroke-width="2"/>'
        + _ICON_RENDERERS[icon](
            cx, cy + resource_icon_center_y(icon), resource_icon_size(icon), palette["ink"]
        )
        + f'<text x="{cx:.1f}" y="{cy + RESOURCE_COUNT_OFFSET:.1f}" text-anchor="middle"'
        ' font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{RESOURCE_COUNT_FONT_SIZE:g}" font-weight="700"'
        f' fill="{palette["ink"]}">{escape(str(resource["count"]))}</text>'
    )


def _render_first_player_marker(cx: float, palette: dict, label: str) -> str:
    """The scallop shell in its labelled card, aligned with the top edge of the banners."""
    marker_width, marker_height = 3 * MARKER_CUBE, 2 * MARKER_CUBE

    card_top = BANNER_CENTER_Y - BANNER_HEIGHT / 2
    baseline = card_top + MARKER_CARD_PAD_Y + ASCENT_RATIO * MARKER_LABEL_FONT_SIZE
    icon_top = baseline + MARKER_TEXT_TO_ICON_GAP
    card_height = icon_top + marker_height + MARKER_CARD_PAD_Y - card_top
    card_width = max(marker_width, MARKER_CARD_MIN_WIDTH) + 2 * MARKER_CARD_PAD_X

    return (
        f'<rect x="{cx - card_width / 2:.1f}" y="{card_top:.1f}" width="{card_width:.1f}"'
        f' height="{card_height:.1f}" rx="{MARKER_CARD_CORNER_RADIUS:g}"'
        f' fill="{palette["marker_fill"]}" stroke="{palette["marker_stroke"]}"'
        ' stroke-width="1.5"/>'
        f'<text x="{cx:.1f}" y="{baseline:.1f}"'
        ' text-anchor="middle" font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{MARKER_LABEL_FONT_SIZE:g}" font-weight="700"'
        f' fill="{palette["ink"]}">{escape(label)}</text>'
        + _render_scallop_shell(
            cx, icon_top + marker_height / 2, marker_width, marker_height, palette
        )
    )


def _render_scallop_shell(cx: float, cy: float, width: float, height: float, palette: dict) -> str:
    """A solid scallop shell, the pilgrimage symbol, with parchment ribs fanning from the hinge."""
    ink = palette["ink"]
    hinge_x, hinge_y = cx, cy + height * 0.42
    half_width = width * 0.46
    top_y = cy - height * 0.42

    def rib_top(index: int) -> tuple[float, float]:
        fraction = index / MARKER_SCALLOP_COUNT
        return (
            hinge_x - half_width + fraction * 2 * half_width,
            top_y - math.sin(fraction * math.pi) * height * 0.10,
        )

    outline = [(hinge_x, hinge_y)]
    for index in range(MARKER_SCALLOP_COUNT + 1):
        x, y = rib_top(index)
        on_end = index in (0, MARKER_SCALLOP_COUNT)
        notch = 0.0 if on_end or index % 2 else height * 0.05
        outline.append((x, y + notch))

    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in outline) + " Z"
    parts = [
        f'<path d="{path}" fill="{ink}" stroke="{ink}" stroke-width="1" stroke-linejoin="round"/>'
    ]
    for index in range(1, MARKER_SCALLOP_COUNT):
        x, y = rib_top(index)
        parts.append(
            f'<line x1="{hinge_x:.1f}" y1="{hinge_y:.1f}" x2="{x:.1f}" y2="{y:.1f}"'
            f' stroke="{palette["parchment"]}" stroke-width="0.8" stroke-opacity="0.55"/>'
        )
    return "".join(parts)


def _render_worker_circle(cx: float, cy: float, palette: dict) -> str:
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{ROLE_CIRCLE_RADIUS:g}"'
        f' fill="{palette["worker_fill"]}"'
        f' stroke="{palette["worker_edge"]}" stroke-width="2"/>'
    )


def _render_role_acolytes(
    cx: float,
    cy: float,
    count: int,
    player: dict,
    role_id: str = "",
    interactive: bool = False,
) -> str:
    """Acolytes standing on a role: one centred, two side by side, never more than the limit.

    An interactive board draws every slot a role can use — the centred one and the pair — and
    hides the ones this count does not need, so a page can move an acolyte by flipping opacity
    instead of redrawing the board.
    """
    step = 2 * TOKEN_RADIUS + TOKEN_GAP
    count = min(count, ROLE_ACOLYTE_LIMIT)
    if not interactive:
        first_x = cx - (count - 1) * step / 2
        return "".join(
            _render_square_token(first_x + index * step, cy, player) for index in range(count)
        )
    slots = ((cx, "single", 1), (cx - step / 2, "pair", 2), (cx + step / 2, "pair", 2))
    return "".join(
        _render_square_token(
            x,
            cy,
            player,
            1 if count == shown_at else 0,
            f' data-token="role" data-role="{role_id}" data-role-slot="{slot}"',
        )
        for x, slot, shown_at in slots
    )


def _render_building_slot(cx: float, cy: float, palette: dict, number: int = 0) -> str:
    """One of the six bottom slots, empty.

    A numbered slot is the interactive form. It splits into the three layers a filled slot needs:
    the slot's own fill, the `use` that takes whatever building content a page points it at, and
    the dashed outline drawn last. Content goes inside the slot rather than on top of it, so the
    dashed border stays the only boundary a slot ever has.

    The `use` carries the slot's centre and nothing else -- no scale, no nudge -- so content drawn
    around the origin at this same hex size lands exactly on the dashes. The centre is written to
    the same two decimals the path is, so the two cannot part company in the rounding.
    """
    path = hex_path_data(cx, cy)
    dashes = (
        f' stroke="{palette["slot_stroke"]}" stroke-width="2"'
        f' stroke-dasharray="{BUILDING_SLOT_DASH_ARRAY}" stroke-linejoin="round"/>'
    )
    if not number:
        return f'<path d="{path}" fill="{palette["slot_fill"]}"{dashes}'
    return (
        f'<g data-player-board-slot="{number}" data-building-slot-state="empty"'
        ' data-building-id="" data-setup-slot="" data-donated="false">'
        f'<path d="{path}" fill="{palette["slot_fill"]}" stroke="none"/>'
        f'<use data-building-content="true" x="{cx:.2f}" y="{cy:.2f}" opacity="0"/>'
        f'<path data-slot-outline="true" d="{path}" fill="none"{dashes}'
        "</g>"
    )


def _render_corner_tag(geometry: dict, player: dict) -> str:
    """The player-colour triangle folded into the top-right corner, clipped to the panel shape."""
    width = geometry["panel_width"]
    height = geometry["panel_height"]
    clip_id = f"panelClip_{player['fill'].lstrip('#')}"
    path = (
        f"M {width + CORNER_TAG_OVERSHOOT:.1f},{-CORNER_TAG_OVERSHOOT:.1f}"
        f" L {width + CORNER_TAG_OVERSHOOT:.1f},{CORNER_TAG_SIZE:.1f}"
        f" L {width - CORNER_TAG_SIZE:.1f},{-CORNER_TAG_OVERSHOOT:.1f} Z"
    )
    return (
        f'<clipPath id="{clip_id}"><rect x="{-CORNER_CLIP_PAD:g}" y="{-CORNER_CLIP_PAD:g}"'
        f' width="{width + 2 * CORNER_CLIP_PAD:.0f}" height="{height + 2 * CORNER_CLIP_PAD:.0f}"'
        f' rx="{PANEL_CORNER_RADIUS + CORNER_CLIP_PAD:g}"/></clipPath>'
        f'<path d="{path}" fill="{player["fill"]}" stroke="{player["stroke"]}"'
        f' stroke-width="1.5" stroke-linejoin="miter" clip-path="url(#{clip_id})"/>'
    )


def render_player_board_v2_svg(
    layout: dict,
    player: dict,
    include_first_player_marker: bool = False,
    board_state: dict | None = None,
    interactive: bool = False,
) -> str:
    """One player's board, holding `board_state` (the starting board when none is given).

    `interactive` tags the cubes and the marker card and draws every slot they can occupy, hidden
    where the state does not need them, so a page can move a cube by flipping opacity. Left off,
    the board is exactly the one the baseline prototype draws.
    """
    palette = layout["palette"]
    roles = layout["worker_roles"]
    grid = layout["starting_worker_grid"]
    state = default_player_board_v2_state(layout) if board_state is None else board_state
    capacity = token_slot_count(layout)
    geometry = board_geometry(len(roles))
    visible_cubes = {
        "village": min(int(state["village_serfs"]), capacity),
        "abbey": min(int(state["abbey_acolytes"]), capacity),
    }

    parts = [_render_panel(geometry, palette)]
    for banner in layout["banners"]:
        cx, width = banner_center_x(geometry, banner["first_role_index"])
        parts.append(_render_banner(cx, width, banner["label"], palette))
    for banner in layout["banners"]:
        cx, _ = banner_center_x(geometry, banner["first_role_index"])
        parts.append(
            _render_token_grid(
                cx,
                geometry["token_grid_top"],
                grid["rows"],
                grid["columns"],
                visible_cubes[banner["id"]],
                player,
                banner["id"] if interactive else "",
            )
        )

    resource_x = resource_centers(layout, geometry)
    if include_first_player_marker or interactive:
        marker = _render_first_player_marker(
            resource_x[2], palette, layout["first_player_marker"]["label"]
        )
        if interactive:
            shown = "true" if include_first_player_marker else "false"
            marker = (
                f'<g data-first-player-marker="{shown}"'
                f' opacity="{1 if include_first_player_marker else 0:g}">{marker}</g>'
            )
        parts.append(marker)
    for cx, resource in zip(resource_x, layout["resources"], strict=True):
        parts.append(_render_resource(cx, geometry["resource_cy"], resource, palette))

    role_cy = geometry["role_circle_cy"]
    label_baseline = geometry["role_label_baseline"]
    for cx, role in zip(geometry["role_x"], roles, strict=True):
        parts.append(_render_worker_circle(cx, role_cy, palette))
        parts.append(_render_role_label(cx, label_baseline, role["label"], palette["ink"]))
    for cx, role in zip(geometry["role_x"], roles, strict=True):
        count = int(state["roles"].get(role["id"], 0))
        if count or interactive:
            parts.append(_render_role_acolytes(cx, role_cy, count, player, role["id"], interactive))

    for number, (cx, cy) in enumerate(
        zip(geometry["role_x"], geometry["building_y"], strict=True), start=1
    ):
        parts.append(_render_building_slot(cx, cy, palette, number if interactive else 0))
    parts.append(_render_corner_tag(geometry, player))

    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {geometry["panel_width"]:.0f} {geometry["panel_height"]:.0f}"'
        f' width="{geometry["panel_width"]:.0f}" height="{geometry["panel_height"]:.0f}">'
        f"{''.join(parts)}</svg>"
    )


def render_player_boards_v2_grid(layout: dict, first_player: str = DEFAULT_FIRST_PLAYER) -> str:
    """The four boards in the layout's grid, as a fragment a host page can drop into its own page.

    The grid is the layout's own — two rows of two — so a page that shows the boards beside other
    components keeps the same footprint the standalone page uses. Pair it with
    `player_board_v2_grid_styles()`, which is where the rows and the gaps are described.
    """
    player_by_id(layout, first_player)
    grid = layout["grid"]

    wraps = [
        f'    <div class="board-wrap" data-component="player-board-v2"'
        f' data-player="{player["id"]}" data-player-color="{player["color"]}"'
        f' data-first-player-marker="{"true" if player["id"] == first_player else "false"}">'
        f"{render_player_board_v2_svg(layout, player, player['id'] == first_player)}</div>"
        for player in players_of(layout)
    ]
    rows = "\n".join(
        '  <div class="board-row">\n'
        + "\n".join(wraps[index : index + grid["columns"]])
        + "\n  </div>"
        for index in range(0, len(wraps), grid["columns"])
    )
    return f'<div class="board-col">\n{rows}\n  </div>'


def player_board_v2_grid_styles(layout: dict, gap: float | None = None) -> str:
    """The CSS the grid fragment needs. A host page sets the board width itself.

    `gap` overrides the layout's own spacing, which a page showing the boards in a narrow column
    wants: the standalone page can afford 60px between full-size boards, a column beside the map
    cannot.
    """
    gap = f"{layout['grid']['gap'] if gap is None else gap:g}px"
    return f"""  .board-col {{
    display: flex;
    flex-direction: column;
    gap: {gap};
  }}
  .board-row {{
    display: flex;
    flex-direction: row;
    align-items: flex-start;
    gap: {gap};
  }}
  .board-wrap {{
    background: {PAGE_BACKGROUND}; border: 1px solid #333333; border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5); padding: 10px;
  }}
"""


def render_player_boards_v2_html(layout: dict, first_player: str = DEFAULT_FIRST_PLAYER) -> str:
    """All four boards in the layout's grid. `first_player` picks which one carries the marker."""
    page = layout["page"]
    boards = render_player_boards_v2_grid(layout, first_player)

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
{player_board_v2_grid_styles(layout)}  svg {{ display: block; max-width: 95vw; height: auto; }}
</style>
</head>
<body>
  <h1>{page["title"]}</h1>
  <p class="subtitle">{escape(page["subtitle"])} Generated from {LAYOUT_FILENAME}.</p>
  {boards}
</body>
</html>
"""
