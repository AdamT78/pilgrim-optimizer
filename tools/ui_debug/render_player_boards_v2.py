"""Structured renderer for the player board v2 debug view.

Four boards on one page — white, red, yellow, and blue — laid out in a 2x2 grid, each one a
parchment panel with the Village and Abbey banners, the starting worker tokens, six worker-role
circles, six empty building slots, and a colour tag folded into the top-right corner. The three
resource readouts stand side by side in the top-right, each amount under its own icon, with a thin
rule between one and the next.

This is a debug/visual tool only. It reads `player_boards_v2_layout.json` and emits SVG/HTML. It
is not connected to `GameState` and it implements no game rules. It also does not replace
`render_player_board.py`, which still draws the v1 board.

The board is six columns wide, and it is the building slots along the bottom that set how wide a
column is: they are the biggest thing on the board, being map hexes, and everything above them --
the banners, the resource readouts, the role circles -- lines up on the columns they make. The
layout JSON says what a board carries; this module says where it goes.

This is a wider board than `prototypes/player_boards_v2.html` draws. The prototype's slots were
about two thirds of a map hex, which left the bottom row looking like six placeholders rather than
six places a tile goes; sizing them properly is what pushed the columns apart. Nothing on the board
was rescaled to do it -- the text and the role circles are the sizes they always were, and the
board is the height it always was -- so a board still renders at exactly the scale it used to
wherever it is shown.

The cubes are the one thing here that has been resized, and they were resized to the duty wheel's.
A player's piece should read as one piece wherever it is standing, so the Village and Abbey grids
and the acolytes on the role circles are drawn at the wheel's cube size and spaced the way the
wheel spaces its tallies. The board around them did not move to make room: the grids stand in the
band they always stood in, and the slots along the bottom are the size they always were.

What did move is the resources. They used to be three large circles strung across the middle of the
board; they are a plain row of icon over amount in the top-right corner now, standing in the two
columns the banners leave free. The gap they came out of stays open. Closing it would take about a
tenth off the board's height, and a seat on the composed game table is sized by fitting two boards
into the duty wheel's height -- so a shorter board is a wider seat drawn at a larger scale, and a
cube in a Village would stop matching the same cube on a duty tile. Nothing here was rescaled or
moved to make room: every piece of the board is the size and in the place it was.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from tools.ui_debug.render_duty_wheel import CUBE_CELL_HEIGHT as DUTY_CUBE_CELL_HEIGHT
from tools.ui_debug.render_duty_wheel import CUBE_COLUMN_WIDTH as DUTY_CUBE_COLUMN_WIDTH
from tools.ui_debug.render_duty_wheel import CUBE_SIZE as DUTY_CUBE_SIZE

LAYOUT_FILENAME = "player_boards_v2_layout.json"
PAGE_BACKGROUND = "#000000"
BOARD_GAP = 60
# Which board a page that has to pick one starts on.
DEFAULT_PLAYER = "player_one"

# Cubes are serfs while they sit in the Village and acolytes once they reach the Abbey or a role
# circle. A role circle holds at most two acolytes: one centred, two side by side.
ROLE_ACOLYTE_LIMIT = 2

# A building slot is a map hex, and the two are drawn the same way -- flat-top, from the centre out
# to a corner -- so a slot ought to come out on screen the size a map hex does. It does not follow
# from the arithmetic, because the composed table draws the map at one scale and a seat at another:
# the wheel is fitted to the height its row leaves it and comes out about three quarters of the
# size the table's cube would make it, and a seat is shrunk by that same shortfall so a Village cube
# keeps matching a duty tile's. The map never was. So a slot has to be drawn this much larger in the
# board's own units to land at a map hex's size once both shortfalls are taken -- measured off the
# real solve, and held there by a test in `test_ui_debug_game_table.py`, which is what to re-run if
# either board's scale ever moves.
BUILDING_SLOT_HEX_SIZE = 62.394
# Clear air between neighbouring slots, and between the columns the board is spaced on.
BUILDING_SLOT_GAP = 10.0
# Half of one of the board's six columns. The slots used to set this -- they were the widest thing
# in a column, and the column was drawn around them -- and it is still the width they had then, so
# nothing on the grid has moved. They no longer set it: a slot that big will not fit six to a row,
# so the slots left the row and took a zigzag of their own, and the columns the banners, the role
# circles and the readouts line up on are their own measurement now.
COLUMN_HALF_WIDTH = 49.4
# Clear air between the bottom of a role circle and the top of the slot below it.
BUILDING_ROW_GAP = 12.0

# A role circle's own radius. It is no longer the slot's: the slots grew and the circles did not.
ROLE_CIRCLE_RADIUS = 34.0

# Left of the first slot and right of the last, which is all the horizontal margin a board has.
SIDE_MARGIN = 25.0
PANEL_CORNER_RADIUS = 12
PANEL_STROKE_WIDTH = 2

# How strong the active seat's wash is where it is strongest, along the very bottom edge. Enough to
# read as a colour against the parchment across a room, and not enough to be read as a thing on the
# board: everything drawn over it -- cubes, ink, the dashed slots -- has to stay exactly as legible.
# The ceiling is about a third. Past that the bottom of the board stops being parchment lit by a
# colour and becomes a panel painted in one, which is the highlight box this was drawn to avoid.
ACTIVE_GLOW_OPACITY = 0.28

BANNER_CENTER_Y = 30.0
BANNER_HEIGHT = 26.0
# Village and Abbey are set to read at the size the duty wheel sets its duty names -- Produce,
# Taxation, Give Alms and the rest. Same trick as the building slots: two boards drawn at
# different scales agree on screen when they agree in cubes, and a duty name is 15.5 units against
# that board's 13.0-unit cube, so 1.192 cubes, which is 1.192 * MARKER_CUBE in this board's units.
BANNER_FONT_SIZE = 16.7
BANNER_NOTCH_RATIO = 0.35
BANNER_TEXT_BASELINE_RATIO = 0.35

# The cubes are the duty wheel's cubes. A player's piece is the same piece whether it is waiting in
# the Village, standing on a role circle or sitting on a duty tile, so it should read as one piece
# in all three places. On the composed game table a unit of this board and a unit of the wheel land
# within a couple of percent of each other -- the seats are fitted to the wheel's height rather than
# drawn at its scale, so the two never agree exactly and what is left over moves with the window --
# and at that distance taking the wheel's numbers across as written is what makes the cubes match.
# The game table tests measure the two against the real solve rather than trusting this.
#
# The wheel writes its grid as pitches rather than gaps -- a column is CUBE_COLUMN_WIDTH from the
# next, a cube CUBE_CELL_HEIGHT from the one above it -- so the air between two cubes is what is
# left of a pitch once the cube is taken out of it. The wheel spaces its cubes wider side to side
# than it stacks them, and the grids here are spaced the same way.
TOKEN_RADIUS = DUTY_CUBE_SIZE / 2
TOKEN_GAP = DUTY_CUBE_COLUMN_WIDTH - DUTY_CUBE_SIZE
TOKEN_ROW_GAP = DUTY_CUBE_CELL_HEIGHT - DUTY_CUBE_SIZE
TOKEN_GRID_TOP_GAP = 12.0
# The band the Village and Abbey grids stand in, held at the height it had when a cube was 14 units
# so that resizing the cubes does not drag the role circles and the building slots up with them. A
# grid shorter than its band centres itself in it and everything below stays where it was.
TOKEN_BAND_HEIGHT = 34.0

# Air between the bottom of the board's top section and the top of the role labels. The readouts
# used to stand in this gap and left a third of the board empty when they went to the corner, so
# the labels are hung off whatever is above them now rather than off a distance fixed when they
# were not.
ROLE_LABEL_TOP_GAP = 16.0
# How deep a role label can be. "Road Engineer" and "Alms House" wrap to two lines and nothing on
# the board wraps to three, so the circles are set below a two-line label whether or not the label
# above any one of them needs both -- which is what keeps all six circles on one line. Checked
# against the layout in the tests.
ROLE_LABEL_MAX_LINES = 2
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

# How far each icon reaches above and below the point it is drawn from, per unit of the size it is
# asked for. Measured off the rendered artwork rather than derived, so they hold only while the
# drawings do. None of the three is symmetric about that point -- the wheat least of all, being a
# sheaf that fans upwards -- so a row that wants its icon centred has to know both numbers.
ICON_RISE_RATIO = {"wheat": 1.1244, "cube": 0.6, "coin": 0.6}
ICON_FOOT_RATIO = {"wheat": 0.6, "cube": 0.62, "coin": 0.62}

# A readout is an icon with its amount under it, and the three of them stand side by side in the
# top-right corner. The banners take four of the board's six columns, so the readouts get the two
# on the right and split them three ways: one centres in each third, and a rule falls on each of
# the two seams between them. The ends are left open -- a rule out there would bracket the readouts
# rather than divide them.
RESOURCE_READOUT_COUNT = 3
RESOURCE_BAND_COLUMNS = 2
RESOURCE_COUNT_FONT_SIZE = 16
# Digits, so the amounts are set on their cap height rather than a baseline that would leave a
# one-digit readout and a two-digit one sitting at different heights.
RESOURCE_COUNT_CAP_RATIO = 0.72
# Air between the bottom of the icons' band and the top of the amounts under them.
RESOURCE_VALUE_GAP = 6.0
# The rules are run a little past the readouts at both ends, so they read as divisions between
# them rather than as a frame drawn around each one.
RESOURCE_DIVIDER_OVERHANG = 4.0
RESOURCE_DIVIDER_WIDTH = 1.5

# The three keys a page shows when something asks this seat to pick a stock -- the Cornucopia is
# the one that does. A key is the whole pill and not the picture on it: the silver coin is about 23
# across and the amounts are set at 16, and neither is a thing to ask anyone to aim at.
RESOURCE_CHOICE_WIDTH = 66.0
RESOURCE_CHOICE_HEIGHT = 61.0
RESOURCE_CHOICE_TOP = 45.0
RESOURCE_CHOICE_RADIUS = 9.0
RESOURCE_CHOICE_FILL = "#F3EAD2"
RESOURCE_CHOICE_STROKE = "#B8952F"
RESOURCE_CHOICE_STROKE_WIDTH = 1.6

# The one key a page shows when the whole BOARD is the answer -- naming a start player is the
# question that asks it. An outline round the panel and nothing inside it, in the same parchment
# the duty wheel outlines an offered space with, because that is already what this page's "you may
# point at this" looks like.
#
# Deliberately not the seat's own colour and deliberately not a wash. A wash of a board's own
# colour already means something here: it is how the page says whose turn it is, and it sits on one
# board at a time. This mark sits on SEVERAL boards at once and means the opposite kind of thing --
# pick one of these, most of which are not acting. Two lit boards in the same language would read
# as two active players.
SEAT_CHOICE_STROKE = "#F2EEDF"
SEAT_CHOICE_STROKE_WIDTH = 6.0
SEAT_CHOICE_INSET = SEAT_CHOICE_STROKE_WIDTH / 2

# The unit this board's geometry is written in, and the size its cubes were drawn at before they
# were matched to the duty wheel's. The banner type is still a multiple of it, so it stays where it
# is: resizing the cubes was never a reason to reset the type. The building slots were multiples of
# it too, and should not have been -- a slot stands for a map hex, so it has to be measured against
# what a map hex renders at rather than against a unit that stopped being this board's cube.
MARKER_CUBE = 14.0

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
        # No slot holds anything in the sample. A page that knows what its seats have built says
        # so; a page that does not gets six empty slots, which is the truthful drawing of a board
        # nobody has told it about.
        "slots": (),
    }


def building_slot_centers(layout: dict) -> list[tuple[float, float]]:
    """Where the six bottom building slots sit, left to right — slot 1 is the first of them."""
    geometry = board_geometry(len(layout["worker_roles"]))
    return list(zip(geometry["building_x"], geometry["building_y"], strict=True))


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


def slot_band_half_height() -> float:
    """Half the depth the zigzag of slots takes up.

    Two rows offset by an apothem, each an apothem deep either side of its own middle, so the band
    is three apothems from the top of the high row to the bottom of the low one.
    """
    return 1.5 * slot_apothem()


def column_pitch() -> float:
    """Centre to centre between neighbouring columns."""
    return 2 * COLUMN_HALF_WIDTH + BUILDING_SLOT_GAP


def resource_block(panel_width: float) -> dict:
    """Where the three readouts stand, and the rules that divide one from the next.

    Across the board they are the board's own columns: the banners take four of the six, so the
    readouts take the two on the right and split them three ways, which puts a readout in the
    middle of each third and a rule on each seam.

    Down the board they hang from the colour tag, the other thing that wants this corner: the rules
    start exactly where the tag stops running down the board's right-hand edge, so the two divide
    the corner between them rather than the readouts having to be tucked under a diagonal. Under
    the rules' start comes a band deep enough for the tallest of the three icons -- each one centres
    itself in it, so they keep a level line however differently they are drawn -- and then the
    amounts, all on one baseline.
    """
    icon_band = max(resource_icon_height(icon) for icon in ICON_RISE_RATIO)
    right = panel_width - SIDE_MARGIN
    pitch = RESOURCE_BAND_COLUMNS * column_pitch() / RESOURCE_READOUT_COUNT
    left = right - RESOURCE_READOUT_COUNT * pitch
    top = CORNER_TAG_SIZE + RESOURCE_DIVIDER_OVERHANG
    # Digits sit on their baseline, so the bottom of the amounts is the bottom of the block.
    baseline = (
        top + icon_band + RESOURCE_VALUE_GAP + RESOURCE_COUNT_CAP_RATIO * (RESOURCE_COUNT_FONT_SIZE)
    )

    return {
        "cell_x": [left + (index + 0.5) * pitch for index in range(RESOURCE_READOUT_COUNT)],
        "divider_x": [left + (index + 1) * pitch for index in range(RESOURCE_READOUT_COUNT - 1)],
        "icon_cy": top + icon_band / 2,
        "value_baseline": baseline,
        "left": left,
        "right": right,
        "top": top,
        "bottom": baseline,
    }


def board_geometry(role_count: int) -> dict:
    """Every coordinate a board needs.

    The building slots are the widest thing on a board, so they are what it is spaced around: one
    column per slot, and the banners, the role circles and the resource readouts all line up on
    those columns -- the banners taking two each and the readouts sharing the two left over.

    Down the board nothing has moved. The readouts came out of the gap between the cubes and the
    role labels and everything below it stayed where it was, so a board is the height it has always
    been and a seat on the composed table is drawn at the scale it always was.
    """
    pitch = column_pitch()
    role_x = [SIDE_MARGIN + COLUMN_HALF_WIDTH + index * pitch for index in range(role_count)]
    panel_width = role_x[-1] + COLUMN_HALF_WIDTH + SIDE_MARGIN

    band_top = BANNER_CENTER_Y + BANNER_HEIGHT / 2 + TOKEN_GRID_TOP_GAP
    tokens_bottom = band_top + TOKEN_BAND_HEIGHT
    token_top = band_top + (TOKEN_BAND_HEIGHT - (2 * 2 * TOKEN_RADIUS + TOKEN_ROW_GAP)) / 2

    # The labels run the whole width of the board, so they hang below whichever half of the top
    # section reaches lower: the Village and Abbey grids over the left of it, or the readouts and
    # their rules over the right. It is the readouts, which is why moving them into the corner is
    # what let the rest of the board come up behind them.
    resources = resource_block(panel_width)
    top_section_bottom = max(tokens_bottom, resources["bottom"] + RESOURCE_DIVIDER_OVERHANG)
    # Rounded because the readouts' depth comes off icon artwork and carries a long tail, and
    # everything below here is measured from it. Paths are written at two decimals, so keeping the
    # chain there is what lets a placed building land on the dashed slot's own numbers exactly.
    label_top = round(top_section_bottom + ROLE_LABEL_TOP_GAP, 2)
    role_baseline = label_top + (ROLE_LABEL_MAX_LINES - 1) * ROLE_LINE_HEIGHT + LABEL_ASCENT
    role_circle_top = role_baseline + ROLE_LABEL_GAP

    # The slots hang off the bottom of the role circles as one band, and zigzag inside it: a slot
    # is wider than the column it would have stood in, so a straight row of six will not fit across
    # the board. Offsetting every other one by an apothem is how a flat-top hexagon packs against
    # its neighbour, which buys the width back out of the depth -- six of them laid this way take
    # less across the board than the smaller six took in a row, at the cost of a band half again as
    # deep. The band is centred where the row's middle was, so the slots grew about it evenly.
    band_middle = round(
        role_circle_top + 2 * ROLE_CIRCLE_RADIUS + BUILDING_ROW_GAP + slot_band_half_height(), 2
    )
    # The row still spans the board's whole inner width, as it did when the slots were the columns:
    # the first and last sit against the side margins and the rest divide what is between them.
    # There are as many slots as roles -- six of each -- even though a slot no longer stands in a
    # role's column.
    slot_count = role_count
    inner = panel_width - 2 * SIDE_MARGIN - 2 * BUILDING_SLOT_HEX_SIZE
    slot_pitch = inner / (slot_count - 1)
    # Rounded for the same reason the band's middle is: a slot's path is written at two decimals and
    # a building is placed by carrying that centre, so the centre has to be a number the path can
    # hold exactly or a placed building lands a hundredth off its own dashes.
    building_x = [
        round(SIDE_MARGIN + BUILDING_SLOT_HEX_SIZE + index * slot_pitch, 2)
        for index in range(slot_count)
    ]
    # Slot 1 rides high, and they alternate from there.
    building_y = [
        round(band_middle + (-1 if index % 2 == 0 else 1) * slot_apothem() / 2, 2)
        for index in range(slot_count)
    ]

    top_margin = BANNER_CENTER_Y - BANNER_HEIGHT / 2
    panel_height = round(band_middle + slot_band_half_height() + top_margin, 2)

    return {
        "panel_width": panel_width,
        "panel_height": panel_height,
        "role_x": role_x,
        "role_circle_cy": role_circle_top + ROLE_CIRCLE_RADIUS,
        "role_label_baseline": role_baseline,
        "token_grid_top": token_top,
        "resources": resources,
        "building_x": building_x,
        "building_y": building_y,
    }


def banner_center_x(geometry: dict, first_role_index: int) -> tuple[float, float]:
    """A banner spans two whole columns, which is what makes them all the same width.

    Two columns, not two role circles: it is the columns the board is built on, and spanning them
    is what puts the outer banners' ends flush with the board's side margins.
    """
    left = geometry["role_x"][first_role_index] - COLUMN_HALF_WIDTH
    right = geometry["role_x"][first_role_index + 1] + COLUMN_HALF_WIDTH
    return (left + right) / 2, right - left


def banner_centers(layout: dict, geometry: dict) -> list[float]:
    return [
        banner_center_x(geometry, banner["first_role_index"])[0] for banner in layout["banners"]
    ]


def _render_panel(geometry: dict, palette: dict) -> str:
    return (
        f'<rect x="0" y="0" width="{geometry["panel_width"]:.0f}"'
        f' height="{geometry["panel_height"]:.0f}" rx="{PANEL_CORNER_RADIUS:g}"'
        f' fill="{palette["panel_background"]}" stroke="{palette["parchment_edge"]}"'
        f' stroke-width="{PANEL_STROKE_WIDTH:g}"/>'
    )


def _render_active_glow(geometry: dict, player: dict) -> str:
    """A wash of the seat's own colour up off the bottom edge, for a page that wants to say whose
    turn it is. It is drawn here dark and hidden, at `opacity="0"`; the page that knows about turns
    is the one that turns it on, and the boards' own page never does.

    Off the bottom rather than round the outside, because a board is a thing on a table and a ring
    round it is a browser's idea of a selected thing. It covers the whole panel and takes the
    panel's corner radius, so the shaping is the fade's work and not a clip's: the colour is at its
    strongest along the bottom edge and gone by the top of the building band, which leaves the
    slots to be passed behind and the role circles, the readouts and the banners never reached.
    """
    height = geometry["panel_height"]
    # Where the band of building slots begins, read back off the height it was one of the terms in.
    band_top = height - (BANNER_CENTER_Y - BANNER_HEIGHT / 2) - 2 * slot_band_half_height()
    fade = (height - band_top) / height
    colour = player.get("glow", player["fill"])
    gradient_id = f"activeGlow_{player['fill'].lstrip('#')}"
    return (
        f'<defs><linearGradient id="{gradient_id}" x1="0" y1="1" x2="0" y2="0">'
        f'<stop offset="0" stop-color="{colour}" stop-opacity="{ACTIVE_GLOW_OPACITY:g}"/>'
        f'<stop offset="{fade:.3f}" stop-color="{colour}" stop-opacity="0"/>'
        "</linearGradient></defs>"
        f'<rect data-active-player-glow="true" x="0" y="0"'
        f' width="{geometry["panel_width"]:.0f}" height="{height:.0f}"'
        f' rx="{PANEL_CORNER_RADIUS:g}" fill="url(#{gradient_id})" opacity="0"/>'
    )


def _render_seat_choice_key(geometry: dict, player: dict) -> str:
    """One key covering the whole board, drawn hidden, for a page that has to ask WHICH SEAT.

    The whole panel because the whole panel is the answer: the question is which player, and a
    player is their board. There is nothing smaller to aim at and inventing one -- a corner, a
    banner -- would be putting a target somewhere the rule never pointed.

    Struck here rather than in the page's script for the same reason the stock keys and the first
    player seal are: the script reveals and hides, and never assigns a fill. The key carries the id
    of the player it stands for, so a page can tell which board was pressed without knowing where
    any of them sit -- and without turning a player into a chair number, which is the translation
    that has gone wrong here before.

    `pointer-events="all"` because the key is an outline. A shape painted `fill="none"` is hit
    tested on its stroke and nowhere else, so without this a click in the middle of a board falls
    straight through the key to the artwork behind it and the choice never registers -- while the
    key still LOOKS like a target, which is the part that makes it hard to spot. The building key
    on the map is an outline for the same reason and says this the same way.
    """
    inset = SEAT_CHOICE_INSET
    return (
        f'<rect data-seat-choice-key="{escape(str(player["id"]))}"'
        f' x="{inset:g}" y="{inset:g}"'
        f' width="{geometry["panel_width"] - 2 * inset:.0f}"'
        f' height="{geometry["panel_height"] - 2 * inset:.0f}"'
        f' rx="{PANEL_CORNER_RADIUS:g}" fill="none" pointer-events="all"'
        f' stroke="{SEAT_CHOICE_STROKE}"'
        f' stroke-width="{SEAT_CHOICE_STROKE_WIDTH:g}" visibility="hidden"/>'
    )


def seat_choice_styles() -> str:
    """What one attribute on a board does to it, for any page that shows the seat key.

    The key is drawn hidden and this is the only thing that shows it, so a page asks by setting
    `data-seat-choice="true"` on the board and takes it off again when the choice is answered.
    Reveal and a cursor -- no colour is named here or anywhere the script can reach.
    """
    return (
        '  [data-seat-choice="true"] [data-seat-choice-key] {\n'
        "    visibility: visible; cursor: pointer;\n"
        "  }\n"
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
    across = 2 * TOKEN_RADIUS + TOKEN_GAP
    down = 2 * TOKEN_RADIUS + TOKEN_ROW_GAP
    grid_width = columns * 2 * TOKEN_RADIUS + (columns - 1) * TOKEN_GAP
    first_x = cx - grid_width / 2 + TOKEN_RADIUS
    tokens = []
    for row in range(rows):
        token_y = top_y + TOKEN_RADIUS + row * down
        for column in range(columns):
            index = row * columns + column
            tags = f' data-token="{tag}" data-token-index="{index}"' if tag else ""
            tokens.append(
                _render_square_token(
                    first_x + column * across,
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


def resource_icon_height(icon: str) -> float:
    """How tall an icon is drawn, top of it to bottom."""
    return (ICON_RISE_RATIO[icon] + ICON_FOOT_RATIO[icon]) * resource_icon_size(icon)


def resource_icon_center_y(icon: str) -> float:
    """From the middle of the icons' band to the point an icon is drawn from, centring it there.

    An icon is drawn around a point that is not the middle of the shape it draws, and by a different
    amount for each of the three, so a band that placed them all on its own middle would stand them
    at three different heights.
    """
    size = resource_icon_size(icon)
    return (ICON_RISE_RATIO[icon] - ICON_FOOT_RATIO[icon]) * size / 2


def _render_resource(block: dict, cx: float, resource: dict, palette: dict) -> str:
    """One readout: the icon, and its amount centred under it."""
    icon = resource["icon"]
    if icon not in _ICON_RENDERERS:
        raise KeyError(f"unknown resource icon: {icon}")
    return (
        f'<g data-resource="{escape(str(resource["id"]))}">'
        + _ICON_RENDERERS[icon](
            cx,
            block["icon_cy"] + resource_icon_center_y(icon),
            resource_icon_size(icon),
            palette["ink"],
        )
        + f'<text x="{cx:.1f}" y="{block["value_baseline"]:.1f}" text-anchor="middle"'
        ' font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{RESOURCE_COUNT_FONT_SIZE:g}" font-weight="700"'
        f' fill="{palette["ink"]}">{escape(str(resource["count"]))}</text>'
        "</g>"
    )


def _render_resource_choice_keys(block: dict, resources: list[dict]) -> str:
    """One key per stock, drawn hidden, for a page that has to ask this seat which one it wants.

    Struck here rather than in the page's script for the same reason the first player seal is: the
    script reveals and hides, and never assigns a fill. A key carries the id of the stock it stands
    for, so a page can tell which was pressed without knowing where any of them sit.
    """
    return "".join(
        f'<rect data-resource-choice-key="{escape(str(resource["id"]))}"'
        f' x="{cx - RESOURCE_CHOICE_WIDTH / 2:.1f}" y="{RESOURCE_CHOICE_TOP:g}"'
        f' width="{RESOURCE_CHOICE_WIDTH:g}" height="{RESOURCE_CHOICE_HEIGHT:g}"'
        f' rx="{RESOURCE_CHOICE_RADIUS:g}" fill="{RESOURCE_CHOICE_FILL}"'
        f' stroke="{RESOURCE_CHOICE_STROKE}" stroke-width="{RESOURCE_CHOICE_STROKE_WIDTH:g}"'
        ' visibility="hidden"/>'
        for cx, resource in zip(block["cell_x"], resources, strict=True)
    )


def _render_resource_block(
    geometry: dict, resources: list[dict], palette: dict, choice_keys: bool = False
) -> str:
    """The three readouts in their corner, with a rule standing on each seam between them.

    The keys go down between the rules and the readouts. SVG has no z-index and only document
    order, so a key appended after them would bury the icon and the amount it is meant to be
    highlighting; drawn here it lies under both and behind neither.
    """
    block = geometry["resources"]
    parts = [
        f'<line data-resource-divider="true" x1="{x:.1f}"'
        f' y1="{block["top"] - RESOURCE_DIVIDER_OVERHANG:.1f}" x2="{x:.1f}"'
        f' y2="{block["bottom"] + RESOURCE_DIVIDER_OVERHANG:.1f}"'
        f' stroke="{palette["parchment_edge"]}" stroke-width="{RESOURCE_DIVIDER_WIDTH:g}"'
        ' stroke-linecap="round"/>'
        for x in block["divider_x"]
    ]
    if choice_keys:
        parts.append(_render_resource_choice_keys(block, resources))
    parts += [
        _render_resource(block, cx, resource, palette)
        for cx, resource in zip(block["cell_x"], resources, strict=True)
    ]
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


def _render_building_slot(
    cx: float,
    cy: float,
    palette: dict,
    number: int,
    tagged: bool = False,
    holding: dict | None = None,
) -> str:
    """One of the six bottom slots, empty unless it is holding something.

    A tagged slot is the interactive form. It splits into the three layers a filled slot needs:
    the slot's own fill, the `use` that takes whatever building content a page points it at, and
    the dashed outline drawn last. Content goes inside the slot rather than on top of it, so the
    dashed border stays the only boundary a slot ever has, whether it holds a building or not.

    The `use` carries the slot's centre and nothing else -- no scale, no nudge -- so content drawn
    around the origin at this same hex size lands exactly on the dashes. The centre is written to
    the same two decimals the path is, so the two cannot part company in the rounding.

    `holding` is the other way of filling a slot, for a page that knows at render time what stands
    in it and has no script to point a `use` anywhere. The content arrives already drawn, around
    the origin, and is moved onto the slot centre here -- so this function keeps knowing WHERE a
    slot is and goes on not knowing what a building looks like, which is the split that lets the
    same drawing serve a page that fills its slots from a script and a page that never has one.
    """
    path = hex_path_data(cx, cy)
    dashes = (
        f' stroke="{palette["slot_stroke"]}" stroke-width="2"'
        f' stroke-dasharray="{BUILDING_SLOT_DASH_ARRAY}" stroke-linejoin="round"/>'
    )
    if holding is not None:
        return (
            f'<g data-player-board-slot="{number}"'
            f' data-building-slot-state="{escape(str(holding["state"]))}"'
            f' data-building-id="{escape(str(holding["id"]))}"'
            f' data-donated="{"true" if holding["state"] == "donated" else "false"}">'
            f'<path d="{path}" fill="{palette["slot_fill"]}" stroke="none"/>'
            f'<g transform="translate({cx:.2f},{cy:.2f})">{holding["content"]}</g>'
            f'<path data-slot-outline="true" d="{path}" fill="none"{dashes}'
            "</g>"
        )
    if not tagged:
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
    board_state: dict | None = None,
    interactive: bool = False,
    choice_keys: bool = False,
    seat_key: bool = False,
) -> str:
    """One player's board, holding `board_state` (the layout's sample when none is given).

    The sample is a plausible position, not an empty one -- eight serfs, three acolytes and cubes
    standing on two roles -- so a page that draws a real seat and passes nothing here does not look
    unfinished, it looks wrong, which is harder to notice. Pass what the seat actually has.

    `interactive` tags the cubes and draws every slot they can occupy, hidden where the state does
    not need them, so a page can move a cube by flipping opacity.

    `choice_keys` adds the three hidden keys a page needs to ask this seat which stock it wants.
    Opt in, because a page that will never ask should not carry three rects a board it has no way
    of ever showing. Pair it with `resource_choice_styles()`: without those, nothing can reveal
    them and the keys are exactly the dead markup this flag exists to avoid.

    `seat_key` adds the one hidden key a page needs to ask for this board ITSELF, which is a
    different question from anything on it. Separate from `choice_keys` rather than folded in with
    them: the stock keys are asked of one seat and this is asked of several at once, and the pages
    that carry one have no use for the other. Pair it with `seat_choice_styles()`.
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

    parts = [_render_panel(geometry, palette), _render_active_glow(geometry, player)]
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

    parts.append(_render_resource_block(geometry, layout["resources"], palette, choice_keys))

    role_cy = geometry["role_circle_cy"]
    label_baseline = geometry["role_label_baseline"]
    for cx, role in zip(geometry["role_x"], roles, strict=True):
        parts.append(_render_worker_circle(cx, role_cy, palette))
        parts.append(_render_role_label(cx, label_baseline, role["label"], palette["ink"]))
    for cx, role in zip(geometry["role_x"], roles, strict=True):
        count = int(state["roles"].get(role["id"], 0))
        if count or interactive:
            parts.append(_render_role_acolytes(cx, role_cy, count, player, role["id"], interactive))

    held = list(state.get("slots", ()))
    for number, (cx, cy) in enumerate(
        zip(geometry["building_x"], geometry["building_y"], strict=True), start=1
    ):
        holding = held[number - 1] if number <= len(held) else None
        parts.append(_render_building_slot(cx, cy, palette, number, interactive, holding))
    parts.append(_render_corner_tag(geometry, player))
    # Last, so the outline lies over everything it encloses rather than under the panel's own edge.
    if seat_key:
        parts.append(_render_seat_choice_key(geometry, player))

    return (
        '<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {geometry["panel_width"]:.0f} {geometry["panel_height"]:.0f}"'
        f' width="{geometry["panel_width"]:.0f}" height="{geometry["panel_height"]:.0f}">'
        f"{''.join(parts)}</svg>"
    )


def render_player_boards_v2_grid(layout: dict) -> str:
    """The four boards in the layout's grid, as a fragment a host page can drop into its own page.

    The grid is the layout's own — two rows of two — so a page that shows the boards beside other
    components keeps the same footprint the standalone page uses. Pair it with
    `player_board_v2_grid_styles()`, which is where the rows and the gaps are described.
    """
    grid = layout["grid"]

    wraps = [
        f'    <div class="board-wrap" data-component="player-board-v2"'
        f' data-player="{player["id"]}" data-player-color="{player["color"]}">'
        f"{render_player_board_v2_svg(layout, player)}</div>"
        for player in players_of(layout)
    ]
    rows = "\n".join(
        '  <div class="board-row">\n'
        + "\n".join(wraps[index : index + grid["columns"]])
        + "\n  </div>"
        for index in range(0, len(wraps), grid["columns"])
    )
    return f'<div class="board-col">\n{rows}\n  </div>'


def resource_choice_styles() -> str:
    """What one attribute on a board does to it, for any page that shows the choice keys.

    The keys are drawn hidden and this is the only thing that shows them, so a page asks by setting
    `data-resource-choice="true"` on the board and takes it off again when the choice is answered.
    Reveal, hide, and a cursor -- no fill is named here or anywhere the script can reach.

    The rules between the readouts go while the keys are up. During a choice these three are keys
    rather than readouts, and keys with rules ruled between them read as a table again.
    """
    return (
        '  [data-resource-choice="true"] [data-resource-choice-key] {\n'
        "    visibility: visible; cursor: pointer;\n"
        "  }\n"
        '  [data-resource-choice="true"] [data-resource-divider] {\n'
        "    visibility: hidden;\n"
        "  }\n"
    )


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
{resource_choice_styles()}"""


def render_resource_choice_panel(layout: dict) -> str:
    """One board mid-question, beside the same board at rest.

    A board being asked which stock it wants is a state this board can be in, so this page shows
    it: that is what the page is for. Rendered by asking the real renderer for the keys and then
    setting the real attribute, rather than drawn as a picture of the state, so what is reviewed
    here is what the game table puts on screen.

    The pair is the point. The keys are only legible against the readouts they replace -- the rules
    going is half of what the change is -- and one board on its own does not show that.
    """
    player = players_of(layout)[0]
    asked = (
        '    <figure class="board-wrap" data-resource-choice="true">'
        f"{render_player_board_v2_svg(layout, player, choice_keys=True)}"
        "<figcaption>Being asked which stock: three keys, and the rules stood down"
        "</figcaption></figure>"
    )
    resting = (
        '    <figure class="board-wrap">'
        f"{render_player_board_v2_svg(layout, player)}"
        "<figcaption>The same board at rest</figcaption></figure>"
    )
    return (
        "  <h2>The resource choice</h2>\n"
        '  <div class="board-row">\n' + asked + "\n" + resting + "\n  </div>"
    )


def render_player_boards_v2_html(layout: dict) -> str:
    """All four boards in the layout's grid, and the one state of a board that is not a board."""
    page = layout["page"]
    boards = render_player_boards_v2_grid(layout)
    choice = render_resource_choice_panel(layout)

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
  h2 {{ font-family: Georgia, serif; font-size: 18px; color: #F2EEDF; margin: 34px 0 14px; }}
  figure.board-wrap {{ margin: 0; }}
  figcaption {{ color: #A8A296; font-size: 12px; margin-top: 9px; text-align: center; }}
</style>
</head>
<body>
  <h1>{page["title"]}</h1>
  <p class="subtitle">{escape(page["subtitle"])} Generated from {LAYOUT_FILENAME}.</p>
  {boards}
{choice}
</body>
</html>
"""
