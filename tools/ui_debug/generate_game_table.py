"""Write the generated game table layout page.

This page is composition only: it arranges renderers that already exist into the four-player table
the physical game reads as -- the shared boards across the top, the seats in a row underneath. The
renderers keep owning what each component looks like; nothing here draws geometry of its own.

    alms table      piety track     map
    2P 3P 4P 1..6   duty wheel
    P1 A+ A- P+ P-
    P1 src dst Move

    red seat        seat            seat            seat

The stage is left-aligned, so the two rows start on the same vertical and the red seat comes out
under the alms table. Under that table sits one compact four-row control stack: the table's own
buttons, then Alms/Piety discs and resources, then winners and buildings, then a seat's cubes and
where they walk -- around its own board, and out to the City in the middle of the wheel. These
controls are local page state only: no GameState, no rules, and no scaling solve changes.

ONE SHARED SCALE
Each renderer draws in its own units and was authored as its own standalone page, so handing
every panel a width by eye makes the same wooden cube come out a different size on each board.
The fix is to stop choosing panel widths. One physical reference -- a cube -- is measured in each
board's own units, and every display width falls out of it:

    display width = --cube * (cropped viewBox width / cube size in that board's units)

so a single `--cube` in the stylesheet drives the whole table and every board stays in proportion
when it changes. Two boards draw no cube, so each is anchored on a piece it does share: the piety
track on the disc it shares with the alms table, and the map on the board hexagon the duty wheel's
was derived from.

The duty wheel is the exception. It is given whatever height the row has left rather than a width of
its own, so it draws a smaller cube than `--cube` names, and a seat -- which has to match it piece
for piece -- is sized against the wheel rather than against the cube. That is what lets a player
board be any shape it likes: the seats used to be stacked to the wheel's height instead, which made
a board's proportions decide the scale it was drawn at here.

The two rows then compete differently. Each asks for the window's width on its own, since neither is
inside the other, while for height they take the window one after the other. Nothing is scaled to
fit: there is one cube and every panel is a fixed multiple of it, so seating four rather than two
shows up as a smaller cube for the whole table rather than as a board drawn at a size of its own.

CROPPED, NOT REDRAWN
Those same standalone pages put a heading, a subtitle and a backdrop inside the viewBox -- nearly
half of the duty wheel's box is page furniture -- which would otherwise be paid for in the middle
of a table. Each fragment's viewBox is therefore pointed at its own panel instead. Nothing is
deleted: the extra elements are simply outside the view, and no renderer changes.

Nothing here reads or writes `GameState`, picks legal actions, or applies any rule. The controls
below the Alms Table move only this page's own SVG elements and state; `game_setup.html` remains
the full control-heavy debug sandbox.

Run from the repo root:

    python3 tools/ui_debug/generate_game_table.py
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.generate_game_setup import (  # noqa: E402
    ABBEY_PLACE_ID,
    DEFAULT_START_ROLL,
    EDGE_HEX_PATH,
    START_HEX_BY_ROLL,
    acolyte_places,
    available_setup_buildings,
    building_ownership_state,
    hex_centers,
    render_building_content_defs,
    render_setup_map_svg,
    setup_placements,
)
from tools.ui_debug.render_alms_table import (  # noqa: E402
    CUBE_SIZE as ALMS_CUBE_UNITS,
)
from tools.ui_debug.render_alms_table import (
    RANK_FIRST,
    alms_position_target,
    alms_rules,
    load_alms_config,
    load_alms_table_layout,
    placeholder_slots,
    players_of as alms_players,
    render_alms_table_svg,
)
from tools.ui_debug.render_buildings import load_building_catalog  # noqa: E402
from tools.ui_debug.render_donated_buildings import (  # noqa: E402
    load_donated_building_tiles,
)
from tools.ui_debug.render_duty_wheel import (  # noqa: E402
    CUBE_SIZE as DUTY_CUBE_UNITS,  # noqa: E402
)
from tools.ui_debug.render_duty_wheel import (  # noqa: E402
    CITY_STACK_HEIGHT,
    duty_setups,
    load_duty_wheel_layout,
    merchant_path,
    render_duty_wheel_svg,
)
from tools.ui_debug.render_map import load_map_layout  # noqa: E402
from tools.ui_debug.render_piety_track_v2 import (  # noqa: E402
    load_piety_config,
    load_piety_track_v2_layout,
    position_center_x,
    render_piety_track_v2_svg,
    seated_players,
    track_geometry,
    variant_by_id,
)
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites  # noqa: E402
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    ROLE_ACOLYTE_LIMIT,
    TOKEN_RADIUS as PLAYER_TOKEN_RADIUS,  # noqa: E402
    default_player_board_v2_state,
)
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    PANEL_STROKE_WIDTH as PLAYER_PANEL_STROKE,  # noqa: E402
)
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    board_geometry,
    load_player_boards_v2_layout,
    player_by_id,
    render_player_board_v2_svg,
    token_slot_count,
)

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "game_table.html"

# The tab only. The page itself carries no text: it opens straight into the table, so that what
# is being judged is the arrangement rather than a page about the arrangement.
PAGE_TITLE = "Pilgrim — Game Table"
PAGE_BACKGROUND = "#000000"

# Four seats are drawn in the layout, so the 3-4 player track. The 2 player variant stays on the
# standalone v2 page.
PIETY_VARIANT_ID = "3_4_player"

# Every seat the layout describes, in the order they sit along the row. It is the layout's own
# order read from the red board rather than from the first one, so the run is the seating order
# the layout already gives and red simply leads it. The 2P/3P/4P control only toggles which of
# these fixed seats are visible; it does not reseat anyone or ask the scale to recompute.
SEATED_PLAYERS = ("player_two", "player_three", "player_four", "player_one")

# --- page chrome, in px ----------------------------------------------------------------------
# The gap between panels, between the two rows, and between the player boards.
GAP_PX = 20
PANEL_PADDING = 9
PANEL_BORDER = 1
PANEL_CHROME = 2 * (PANEL_PADDING + PANEL_BORDER)
BODY_PADDING = 20
BODY_CHROME = 2 * BODY_PADDING

# The window the scale is solved against. `--cube` itself stays responsive; this is only the size
# at which the crop margins are read off, and they barely move with it.
REF_AVAIL_WIDTH = 1860.0
REF_VIEWPORT_HEIGHT = 900.0

# The seats stand in one row of four under the main row, so the block is as wide as four boards
# and as tall as one. Every seat is drawn whatever the player count is; the count only decides
# which of them are visible, so that nothing moves when it changes.
SEAT_COLS = len(SEATED_PLAYERS)

# The player counts the control bar offers, and the count it opens on.
PLAYER_COUNTS = (2, 3, 4)
DEFAULT_PLAYER_COUNT = 4

# Who holds the first player marker when the table opens. Turn order is decided on the Piety Track
# -- highest piety takes the marker -- and every disc starts on 0, so the tie resolves to the first
# board: seat 1, red. It falls back here whenever the holder's seat leaves the table, because the
# marker is always with someone. Nothing here makes the holder the first player; this PR moves a
# seal and models no turn order at all.
FIRST_PLAYER_SEAT_AT_START = 1

# The turn flow's own colours. The board rings the seat whose turn it is, and the space that seat
# starts from, in that seat's own colour, and lights the ways out of it in a green dark enough to
# read against the ground the arrows are drawn on. The fallback is only what the stylesheet opens
# with; the page sets the variable from the seat itself.
ACTIVE_PLAYER_FALLBACK = "#C94C4C"
TURN_BRANCH_GREEN = "#1E7A34"
TURN_BRANCH_EDGE = "#0C3D1A"
TURN_DIMMED_OPACITY = "0.4"

# The setup rolls and players the compact controls offer.
SETUP_ROLLS = tuple(sorted(START_HEX_BY_ROLL))
DEFAULT_CONTROL_PLAYER_SEAT = 1

# What each seat has in the City to sow out before the first turn. The engine's own setup deals the
# same five -- `_starting_player_state` in `pilgrim/setup/generator.py` -- but this page reads
# nothing from it: the number is written down here so the board can be dealt without asking.
SETUP_CITY_CUBES = 5

# What a resource's step buttons are called. The board writes the names out in full beside its
# icons; a control row this tight has room for two letters, so the buttons say `Wh+` where the
# board says `Wheat`. Keyed by the layout's own resource ids, so a resource the board stops
# drawing takes its buttons with it rather than leaving a pair that steps nothing.
RESOURCE_ABBREVIATIONS = {"wheat": "Wh", "stone": "St", "silver": "Si"}

# A resource cannot go below nothing. There is no ceiling: what a player may actually hold is a
# rule, and no rule is applied on this page.
RESOURCE_FLOOR = 0

# Dead canvas left around a player board, in its own units. Every other board's margin is solved
# to match whatever this comes out as on screen.
PLAYER_MARGIN = 6.0

# Somewhere to start the fixed point below; none of these survives the first few passes.
_MARGIN_SEED = {"action": 10.0, "map": 12.0, "piety": 4.0}
_SEAT_SEED = 50.0
_CUBE_SEED = 8.0
_SOLVE_PASSES = 200

# The duty wheel draws its hexagon with this stroke, in the units of its own board group.
DUTY_GROUND_STROKE = 4.0

STACK_BELOW = 1080


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


# ---------------------------------------------------------------------------------------------
# What is actually on each board, measured in that board's own units
# ---------------------------------------------------------------------------------------------


def _visible_frame(width: float, height: float, stroke: float) -> tuple[float, float, float, float]:
    """A frame rect at the origin grown by half its own stroke: the panel edge you see.

    Not the bounding box of everything drawn. Each of these renderers starts with a page backdrop
    that overhangs the panel -- by 18 units on the alms table and 20 on the piety track, against 1
    on a player board -- and that backdrop is invisible against a black page but still geometry.
    Cropping to it would bury the two ornamented panels in far more black than a player board
    carries. Measuring the frame is what makes a margin added here mean the same on all three.
    """
    half = stroke / 2
    return (-half, -half, width + stroke, height + stroke)


def _polygon_bounds(path_data: str) -> tuple[float, float, float, float]:
    """x, y, width, height of a path made only of straight moves, in its own coordinates."""
    numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", path_data)]
    xs, ys = numbers[0::2], numbers[1::2]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _grow(box: tuple[float, float, float, float], margin: float) -> tuple[float, ...]:
    x, y, width, height = box
    return (
        round(x - margin, 2),
        round(y - margin, 2),
        round(width + 2 * margin, 2),
        round(height + 2 * margin, 2),
    )


def regular_hexagon_path(cx: float, cy: float, half_width: float) -> tuple[str, float]:
    """A pointy-top regular hexagon and its half-height, which is 2/root-3 of the half-width."""
    half_height = 2 * half_width / math.sqrt(3.0)
    quarter = half_height / 2
    points = [
        (cx, cy - half_height),
        (cx + half_width, cy - quarter),
        (cx + half_width, cy + quarter),
        (cx, cy + half_height),
        (cx - half_width, cy + quarter),
        (cx - half_width, cy - quarter),
    ]
    return ("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z", half_height)


def duty_hexagon(layout: dict) -> dict:
    """The duty wheel's green hexagon: the one it draws, a regular one, and where that lands.

    The duty wheel and the map are meant to read as the same physical board, so the table crops
    both to their hexagon rather than to whatever content happens to sit around it. The wheel's
    was drawn by hand and came out about 2.5% taller than a regular hexagon of the same width, so
    at equal widths the two greens do not read as the same shape. `regular` replaces it with a
    true regular hexagon of the same width and centre -- only how far the empty top and bottom
    points reach changes, and no tile on the board moves.

    This is the one place the table touches what a renderer drew rather than only where it sits.
    It is done here so the standalone duty wheel page keeps the hexagon it has always had.
    """
    board = layout["board"]
    x, y, width, height = _polygon_bounds(board["ground_path"])
    half_width = width / 2
    hex_cx, hex_cy = x + half_width, y + height / 2
    regular, half_height = regular_hexagon_path(hex_cx, hex_cy, half_width)

    # The renderer scales the whole board group about board["center"], so a point at `p` in group
    # units lands at centre + (p - centre) * scale in the SVG's root units. The regular hexagon is
    # the one to measure, since that is what the page will be drawing.
    scale = board["scale"]
    centre_x, centre_y = board["center"]
    stroke = DUTY_GROUND_STROKE * scale
    left = centre_x + (hex_cx - half_width - centre_x) * scale
    top = centre_y + (hex_cy - half_height - centre_y) * scale
    return {
        "drawn": board["ground_path"],
        "regular": regular,
        # the visible shape: the path grown by half a stroke, since the stroke is the same green
        "visible_box": (
            left - stroke / 2,
            top - stroke / 2,
            2 * half_width * scale + stroke,
            2 * half_height * scale + stroke,
        ),
    }


def map_hexagon_box(layout: dict) -> tuple[float, float, float, float]:
    """The map's board hexagon, grown by half its stroke, in the map SVG's own units.

    It is a true regular hexagon centred on the origin, so its half-height is the radius the
    layout gives and its half-width is that times sin 60.
    """
    board = layout["board"]
    radius = board["edge_hex_radius"]
    half_width = radius * math.sin(math.radians(60.0))
    stroke = board["edge_hex_stroke_width"]
    return (
        -half_width - stroke / 2,
        -radius - stroke / 2,
        2 * half_width + stroke,
        2 * radius + stroke,
    )


def board_measurements(
    alms_layout: dict, piety_layout: dict, board_layout: dict, duty_layout: dict, map_layout: dict
) -> tuple[dict, dict, dict]:
    """The content box, hexagon box and cube size of every board, in each board's own units."""
    alms_board = alms_layout["board"]
    piety_variant = variant_by_id(piety_layout, PIETY_VARIANT_ID)
    piety_panel = track_geometry(piety_layout, piety_variant["disc_rows"])
    player_panel = board_geometry(len(board_layout["worker_roles"]))
    hexagon = duty_hexagon(duty_layout)

    content = {
        "alms": _visible_frame(
            alms_board["panel_width"], alms_board["panel_height"], alms_board["stroke_width"]
        ),
        "piety": _visible_frame(
            piety_panel["panel_width"],
            piety_panel["panel_height"],
            piety_layout["panel"]["stroke_width"],
        ),
        "player": _visible_frame(
            player_panel["panel_width"], player_panel["panel_height"], PLAYER_PANEL_STROKE
        ),
    }
    hexes = {"action": hexagon["visible_box"], "map": map_hexagon_box(map_layout)}

    # A cube is drawn 13 units across on the duty wheel -- but inside a group the renderer scales,
    # so in the SVG's own root units it is smaller than that.
    action_cube = DUTY_CUBE_UNITS * duty_layout["board"]["scale"]
    cubes = {
        "action": action_cube,
        "alms": ALMS_CUBE_UNITS,
        # The cube a player board actually draws, which is the wheel's carried across into that
        # board's units. Its geometry is written in a larger unit that is no longer a cube.
        "player": 2 * PLAYER_TOKEN_RADIUS,
        # The piety track has no cube. It shares a player disc with the alms table -- the same
        # diameter on both -- so giving it the alms table's cube for that same disc is what makes
        # the two discs come out the same size on screen.
        "piety": ALMS_CUBE_UNITS
        * (piety_layout["track"]["disc"]["radius"] / alms_layout["disc"]["radius"]),
        # The map has no cube either, and is anchored on the board hexagon instead: this is the
        # cube that makes its hexagon render exactly as wide as the duty wheel's.
        "map": action_cube * (hexes["map"][2] / hexes["action"][2]),
    }
    return content, hexes, cubes


# ---------------------------------------------------------------------------------------------
# The one converged solve
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TableScale:
    """Everything the stylesheet needs to draw the table from a single cube size."""

    cube: float
    crop: dict[str, tuple[float, ...]]
    mult: dict[str, float]
    width_cubes: float
    width_fixed: float
    seats_cubes: float
    seats_fixed: float
    stack_cubes: float
    stack_fixed: float
    row_cubes: float
    map_cubes: float
    piety_cubes: float
    duty_cubes: float
    map_scale: float
    piety_coef: float
    player_k: float
    alms_over_piety: float
    margin_px: float


def _duty_scale(crop: dict, hexes: dict, mult: dict) -> float:
    """How wide the duty wheel is relative to the map, as a share of the map's width.

    Both hexagons are regular and both sit centred in their crop, so putting the duty wheel's top
    point on the map's upper-left shoulder -- a quarter of a hexagon's height below its top point
    -- is a single equation once the two panels are bottom-aligned.
    """

    def geometry(key: str) -> tuple[float, float, float]:
        _, _, crop_width, crop_height = crop[key]
        hexagon_height = hexes[key][3]
        return (
            (crop_height - hexagon_height) / (2 * crop_width),
            hexagon_height / crop_width,
            crop_height / crop_width,
        )

    action_top, _, action_aspect = geometry("action")
    map_top, map_hexagon, map_aspect = geometry("map")
    ratio = (map_top - map_aspect + map_hexagon / 4) / (action_top - action_aspect)
    return ratio * mult["map"] / mult["action"]


def solve_table_scale(content: dict, hexes: dict, cubes: dict) -> TableScale:
    """Find the one cube size the whole table is drawn from.

    Every board is cropped to its own content plus a margin, and that margin has to come out the
    SAME NUMBER OF PIXELS on all of them -- which is whatever a player board's 6 units happen to
    render as. But that figure depends on how big everything is, the sizes depend on the crops,
    and the crops depend on the margins. Rather than pretend that chain has a first link, the
    whole thing is iterated to a fixed point: guess margins, solve the layout, read off what a
    player board's margin renders as, and set every other margin to match.
    """
    margins = dict(_MARGIN_SEED)
    player_crop = _grow(content["player"], PLAYER_MARGIN)
    # The margin is part of what gets drawn, so the shape a seat takes up is the crop's, not the
    # board's.
    player_aspect = player_crop[3] / player_crop[2]
    # The seat is part of the fixed point too, for the reason given below. Seeds only; neither
    # survives the first few passes.
    player_k, cube = _SEAT_SEED, _CUBE_SEED

    for _ in range(_SOLVE_PASSES):
        crop = {
            "action": _grow(hexes["action"], margins["action"]),
            "map": _grow(hexes["map"], margins["map"]),
            "piety": _grow(content["piety"], margins["piety"]),
            # The alms table takes the piety track's margin in units, not in pixels. It is pinned
            # to the piety track's scale anyway, so the same units there mean the same pixels.
            "alms": _grow(content["alms"], margins["piety"]),
            "player": player_crop,
        }
        mult = {key: box[2] / cubes[key] for key, box in crop.items()}
        aspect = {key: box[3] / box[2] for key, box in crop.items()}
        duty_scale = _duty_scale(crop, hexes, mult)

        # The piety track is drawn to sit exactly on the duty wheel's hexagon, so its width is a
        # fraction of the wheel's rather than a size of its own.
        hexagon_share = hexes["action"][2] / crop["action"][2]
        piety_share = hexagon_share * crop["piety"][2] / content["piety"][2]
        alms_over_piety = crop["alms"][2] / crop["piety"][2]

        # Each panel's outer width and height, in cubes.
        duty_coef = mult["action"] * duty_scale
        piety_coef = duty_coef * piety_share
        alms_coef = piety_coef * alms_over_piety
        map_cubes = mult["map"] * aspect["map"]
        duty_cubes = duty_coef * aspect["action"]
        piety_cubes = piety_coef * aspect["piety"]
        alms_cubes = alms_coef * aspect["alms"]

        # The page is two rows: the alms table, the piety-over-duty column and the map across the
        # top, then the four seats underneath. Each row competes for the width on its own, and the
        # two of them stack for the height.
        #
        # `--avail` has already taken the body padding out of the width, so only the panels' own
        # chrome and the gaps between them are counted here. The height budget below works off a
        # raw 100vh, so it has to subtract the page's own chrome itself.
        width_cubes = alms_coef + duty_coef + mult["map"]
        width_fixed = 3 * PANEL_CHROME + 2 * GAP_PX
        seats_cubes = SEAT_COLS * player_k
        seats_fixed = SEAT_COLS * PANEL_CHROME + (SEAT_COLS - 1) * GAP_PX
        # How tall the main row comes out: whichever of the map or the alms table stands taller.
        # The piety-over-duty column is not in it -- the wheel is sized afterwards to fill exactly
        # what the row leaves, so it cannot ask for more room than the row already has.
        row_cubes = max(map_cubes, alms_cubes)
        stack_cubes = row_cubes + player_k * player_aspect
        stack_fixed = BODY_CHROME + 2 * PANEL_CHROME + GAP_PX

        cube = min(
            (REF_AVAIL_WIDTH - width_fixed) / width_cubes,
            (REF_AVAIL_WIDTH - seats_fixed) / seats_cubes,
            (REF_VIEWPORT_HEIGHT - stack_fixed) / stack_cubes,
        )

        # A seat is sized so its cube comes out the size the duty wheel's does, which is what makes
        # a player's piece one piece across the table. It cannot be sized from `cube` to manage it:
        # the wheel is the one panel not drawn at that size, being handed whatever height the row
        # has left over instead, so matching it means reading that height back.
        #
        # Which makes the two mutually dependent -- the seat row is part of the height the cube is
        # solved against -- so they are left to settle together in the fixed point rather than one
        # being solved before the other.
        row_height = cube * row_cubes + PANEL_CHROME
        duty_height = row_height - cube * piety_cubes - 2 * PANEL_CHROME - GAP_PX
        duty_cube_px = cubes["action"] * duty_height / crop["action"][3]
        player_k = mult["player"] * duty_cube_px / cube

        # What a player board's margin comes to on screen, and the same in every other board's
        # units, which is what the next pass crops to.
        margin_px = PLAYER_MARGIN * cube * player_k / player_crop[2]
        per_unit = {
            "action": cube * duty_coef / crop["action"][2],
            "map": cube * mult["map"] / crop["map"][2],
            "piety": cube * piety_coef / crop["piety"][2],
        }
        margins = {key: margin_px / value for key, value in per_unit.items()}

    # The piety track keeps the size it has here. The duty wheel does not: it grows into whatever
    # height the row has left over, which the stylesheet works out for itself from these
    # coefficients rather than from a scale frozen at one window size.

    return TableScale(
        cube=cube,
        crop=crop,
        mult=mult,
        width_cubes=width_cubes,
        width_fixed=width_fixed,
        seats_cubes=seats_cubes,
        seats_fixed=seats_fixed,
        stack_cubes=stack_cubes,
        stack_fixed=stack_fixed,
        row_cubes=row_cubes,
        map_cubes=map_cubes,
        piety_cubes=piety_cubes,
        duty_cubes=duty_cubes,
        # Matching the map's height to the piety-over-duty column the same way would need it about
        # 8.5% wider on top of the wheel's own growth, and the row has no width left for that: it
        # clips the player board and the map's own right edge at ordinary window sizes. The map
        # keeps its size instead, and sits at the bottom of the row.
        map_scale=1.0,
        piety_coef=piety_coef,
        player_k=player_k,
        alms_over_piety=alms_over_piety,
        margin_px=margin_px,
    )


# ---------------------------------------------------------------------------------------------
# Pointing each fragment at its own panel
# ---------------------------------------------------------------------------------------------


def crop_svg(fragment: str, box: tuple[float, ...]) -> str:
    """Point an SVG's viewBox at `box`, and drop the size the renderer wrote on it.

    Nothing is deleted: the heading, subtitle and backdrop each renderer draws for its own
    standalone page are simply outside the view. Dropping width and height is what lets the
    page's own `--cube` rule decide how big the board comes out.
    """
    head_end = fragment.index(">") + 1
    head, body = fragment[:head_end], fragment[head_end:]
    head = re.sub(r'\s(?:width|height)="[^"]*"', "", head)
    head = re.sub(r'viewBox="[^"]*"', 'viewBox="{:g} {:g} {:g} {:g}"'.format(*box), head, count=1)
    return head + body


def regularise_duty_hexagon(fragment: str, hexagon: dict) -> str:
    """Swap the wheel's hand-drawn hexagon for the regular one the crop is measured against."""
    if hexagon["drawn"] not in fragment:
        raise ValueError(
            "the duty wheel's hexagon path is not the one the game table measured; re-measure "
            "duty_hexagon() against render_duty_wheel before generating"
        )
    return fragment.replace(hexagon["drawn"], hexagon["regular"], 1)


def seat_numbers_by_player() -> dict[str, int]:
    """Seat index for each seated player id: red is 1, then yellow, blue, white."""
    return {player_id: index for index, player_id in enumerate(SEATED_PLAYERS, start=1)}


def visible_seats_by_count() -> dict[str, list[int]]:
    """Which seat numbers stay visible at each player count.

    Seats are fixed slots. Lower counts only drop the later ones, so nothing moves.
    """
    return {str(count): list(range(1, count + 1)) for count in PLAYER_COUNTS}


def tag_player_discs(fragment: str) -> str:
    """Stamp each rendered disc with the seat number the player-count control uses.

    The standalone renderers already tag discs with `data-player`; this only adds the seat index
    the composed page needs, without changing what the standalone pages emit.
    """
    tagged = fragment
    for player_id, seat in seat_numbers_by_player().items():
        needle = f'data-player-disc="true" data-player="{player_id}"'
        if needle not in tagged:
            raise ValueError(f"no disc for {player_id} to tag with seat {seat}")
        tagged = tagged.replace(
            needle,
            f'data-player-disc="{seat}" data-player-seat="{seat}" data-player="{player_id}"',
            1,
        )
    return tagged


def tag_resource_readouts(fragment: str, board_layout: dict) -> str:
    """Stamp each resource amount with the id of the resource it counts.

    The renderer already names the readout's group; the amount inside it is the only text there,
    and this is what lets the control row find it without reaching through the group's shape.
    Done here rather than in the renderer so the standalone board page is unchanged.
    """
    tagged = fragment
    for resource in board_layout["resources"]:
        resource_id = resource["id"]
        group = re.compile(rf'(<g data-resource="{re.escape(resource_id)}">.*?)<text ', re.DOTALL)
        tagged, count = group.subn(
            rf'\1<text data-player-resource="{resource_id}" ', tagged, count=1
        )
        if not count:
            raise ValueError(f"no {resource_id} readout to tag on the player board")
    return tagged


def _options(choices: list[tuple[str, str]], selected: str) -> str:
    return "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{label}</option>'
        for value, label in choices
    )


def _control_player_options() -> list[tuple[str, str]]:
    return [(str(seat), f"P{seat}") for seat in range(1, len(SEATED_PLAYERS) + 1)]


def _first_player_options() -> list[tuple[str, str]]:
    """The seats the marker can sit with, and no other entry.

    There is no `nobody` here on purpose: the marker always sits with someone. The renderer will
    draw a panel with no marker on it, which is what leaves the standalone pages alone, but that is
    a rendering default and not a state this table can be in.
    """
    return [(str(seat), f"FP{seat}") for seat in range(1, len(SEATED_PLAYERS) + 1)]


def _resource_buttons(board_layout: dict) -> str:
    """A pair of steps per resource, in the order the board draws its readouts."""
    return "".join(
        f'<button type="button" data-resource-button="{resource["id"]}:{sign}">'
        f"{RESOURCE_ABBREVIATIONS[resource['id']]}{sign}</button>"
        for resource in board_layout["resources"]
        for sign in ("+", "-")
    )


def _building_options(placements: list[dict]) -> list[tuple[str, str]]:
    """Every building still for sale, keyed by the setup slot it stands on.

    The slot is the key rather than the hex, so a setup roll can move a building around the map
    without changing which entry in this list it is.
    """
    return [
        (str(building["setupSlot"]), escape(building["label"]))
        for building in available_setup_buildings(placements)
    ]


def _building_slot_options(board_layout: dict) -> list[tuple[str, str]]:
    """The board's building slots, by number. The row is tight, so they are numbered, not named."""
    return [
        (str(number), str(number))
        for number in range(1, int(board_layout["building_slot_count"]) + 1)
    ]


def render_compact_controls(board_layout: dict, placements: list[dict]) -> str:
    """Four compact rows under the Alms Table, with no labels or help text."""
    count_buttons = "".join(
        f'<button type="button" data-player-count-button="{count}"'
        f' aria-pressed="{"true" if count == DEFAULT_PLAYER_COUNT else "false"}">{count}P</button>'
        for count in PLAYER_COUNTS
    )
    setup_buttons = "".join(
        f'<button type="button" data-setup-roll-button="{roll}"'
        f' aria-pressed="{"true" if roll == DEFAULT_START_ROLL else "false"}">{roll}</button>'
        for roll in SETUP_ROLLS
    )
    players = _control_player_options()
    places = acolyte_places(board_layout)
    first_role = places[1][0] if len(places) > 1 else places[0][0]
    buildings = _building_options(placements)
    slots = _building_slot_options(board_layout)
    return (
        '<div class="table-controls" data-component="game-table-controls">'
        '<div class="control-row" data-controls-row="1">'
        f"{count_buttons}{setup_buttons}"
        '<button type="button" data-duty-randomize-button="true">R</button>'
        '<button type="button" data-setup-mode-button="true" aria-pressed="false">Setup</button>'
        '<button type="button" data-ship-advance="true">S+</button>'
        '<button type="button" data-merchant-advance-button="true">M+</button>'
        '<select id="first-player-seat" data-first-player-select="true">'
        f"{_options(_first_player_options(), str(FIRST_PLAYER_SEAT_AT_START))}</select>"
        "</div>"
        '<div class="control-row" data-controls-row="2">'
        f'<select id="disc-player-seat">{_options(players, str(DEFAULT_CONTROL_PLAYER_SEAT))}</select>'
        '<button type="button" data-disc-track="alms" data-disc-delta="1">A+</button>'
        '<button type="button" data-disc-track="alms" data-disc-delta="-1">A-</button>'
        '<button type="button" data-disc-track="piety" data-disc-delta="1">P+</button>'
        '<button type="button" data-disc-track="piety" data-disc-delta="-1">P-</button>'
        f"{_resource_buttons(board_layout)}"
        "</div>"
        '<div class="control-row" data-controls-row="3">'
        '<select id="alms-winner-player-seat" data-alms-winner-player-select="true">'
        f"{_options(players, str(DEFAULT_CONTROL_PLAYER_SEAT))}</select>"
        '<button type="button" data-alms-winner-button="add">AT+</button>'
        '<button type="button" data-alms-winner-button="reset">ATr</button>'
        '<select id="buy-building" data-building-buy-select="true">'
        f"{_options(buildings, buildings[0][0] if buildings else '')}</select>"
        '<button type="button" data-building-buy-button="true">Buy</button>'
        '<select id="donate-building-slot" data-building-donate-slot-select="true">'
        f"{_options(slots, slots[0][0])}</select>"
        '<button type="button" data-building-donate-button="true">Donate</button>'
        "</div>"
        '<div class="control-row" data-controls-row="4">'
        f'<select id="acolyte-player-seat">{_options(players, str(DEFAULT_CONTROL_PLAYER_SEAT))}</select>'
        f'<select id="acolyte-source">{_options(places, ABBEY_PLACE_ID)}</select>'
        f'<select id="acolyte-target">{_options(places, first_role)}</select>'
        '<button type="button" id="move-acolyte">Move acolyte</button>'
        '<button type="button" data-serf-to-abbey-button="true">S-&gt;A</button>'
        '<button type="button" data-abbey-to-city-button="true">A-&gt;C</button>'
        '<button type="button" data-village-to-city-button="true">V-&gt;C</button>'
        "</div>"
        "</div>"
    )


def setup_roll_data(map_layout: dict) -> dict:
    centers = hex_centers(map_layout)
    return {
        "edgePath": list(EDGE_HEX_PATH),
        "hexCenters": {label: [round(x, 1), round(y, 1)] for label, (x, y) in centers.items()},
        "startHexByRoll": {str(roll): label for roll, label in START_HEX_BY_ROLL.items()},
        "defaultRoll": DEFAULT_START_ROLL,
    }


def disc_motion_data(alms_layout: dict, alms_config: dict, piety_layout: dict) -> dict:
    seat_by_player = seat_numbers_by_player()
    rules = alms_rules(alms_config)
    alms_max = int(rules.max_position)
    piety_max = int(piety_layout["track"]["position_count"]) - 1
    alms_by_id = {player["id"]: player for player in alms_players(alms_layout)}

    alms_targets = {}
    for player_id, seat in seat_by_player.items():
        player = alms_by_id[player_id]
        alms_targets[str(seat)] = {
            str(position): [
                round(target[0], 1),
                round(target[1], 1),
            ]
            for position in range(alms_max + 1)
            for target in [alms_position_target(alms_layout, rules, player, position)]
        }
        first_target = alms_position_target(alms_layout, rules, player, RANK_FIRST)
        alms_targets[str(seat)][RANK_FIRST] = [round(first_target[0], 1), round(first_target[1], 1)]

    piety_targets = {}
    for player in seated_players(piety_layout, PIETY_VARIANT_ID):
        seat = seat_by_player[player["id"]]
        piety_targets[str(seat)] = {
            str(position): [
                round(position_center_x(piety_layout, position) + player["cx_offset"], 1),
                round(player["cy"], 1),
            ]
            for position in range(piety_max + 1)
        }

    def pair_columns(targets: dict[str, dict[str, list[float]]]) -> dict[str, list[float]]:
        return {
            position: [
                round((targets["1"][position][0] + targets["3"][position][0]) / 2, 1),
                targets["1"][position][1],
                targets["2"][position][1],
            ]
            for position in targets["1"]
        }

    starts = {
        "alms": {
            str(seat): int(alms_layout["starting_position"])
            for seat in range(1, len(SEATED_PLAYERS) + 1)
        },
        "piety": {
            str(seat): int(piety_layout["track"]["disc_position"])
            for seat in range(1, len(SEATED_PLAYERS) + 1)
        },
    }
    return {
        "targets": {"alms": alms_targets, "piety": piety_targets},
        "pair": {"alms": pair_columns(alms_targets), "piety": pair_columns(piety_targets)},
        "initial": starts,
        "max": {"alms": alms_max, "piety": piety_max},
        "first": {"alms": RANK_FIRST},
    }


def resource_control_data(board_layout: dict) -> dict:
    """Every seat's resources, starting from the amounts the board is drawn holding."""
    resources = board_layout["resources"]
    return {
        "ids": [resource["id"] for resource in resources],
        "floor": RESOURCE_FLOOR,
        "state": {
            str(seat): {resource["id"]: int(resource["count"]) for resource in resources}
            for seat in range(1, len(SEATED_PLAYERS) + 1)
        },
    }


def duty_wheel_seating(layout: dict) -> dict:
    """The wheel drawn with this table's seating rather than its own.

    The wheel's layout seats a short table on red and blue, the pair that carries against its own
    parchment. This page seats P1 to P4 in one order everywhere else it counts players -- the boards
    in the row, the discs on both tracks -- so a wheel that dropped a different colour would be the
    one board disagreeing about who is playing. Only who sits where changes: the neutral column, the
    geometry, and the standalone wheel page are all untouched.
    """
    seated = dict(layout)
    seated["seats_by_player_count"] = {
        str(count): list(SEATED_PLAYERS[:count]) for count in layout["player_counts"]
    }
    # This table opens on four players, so that is the tally the wheel should open showing.
    seated["default_player_count"] = DEFAULT_PLAYER_COUNT
    return seated


def duty_control_data(layout: dict) -> dict:
    """What the wheel's buttons walk through: its sample setups, the Merchant's ring, and the City.

    The City is the one space cubes arrive at from off the wheel, so the room a column has and the
    number opening in it are both read from the wheel rather than restated here.
    """
    return {
        "setups": duty_setups(layout),
        "merchantPath": merchant_path(layout),
        "merchantStart": layout["merchant_token"]["starts_on"],
        "city": {
            "capacity": CITY_STACK_HEIGHT,
            "opening": int(layout["city_sample_cubes_per_seat"]),
        },
    }


def building_control_data(board_layout: dict, placements: list[dict]) -> dict:
    """Where every building stands before anything is bought: all on the map, no board owns one.

    This is `building_ownership_state` with the players re-keyed to seat numbers, because the
    compact rows pick a seat rather than a player id. The shape is otherwise the setup page's,
    so the buy and donate moves the script makes are the ones `buy_building` and
    `donate_building` already describe in Python.
    """
    ownership = building_ownership_state(board_layout, placements)
    seats = seat_numbers_by_player()
    return {
        "slotCount": int(board_layout["building_slot_count"]),
        "state": {
            "available": ownership["available"],
            "players": {
                str(seat): ownership["players"][player_id]
                for player_id, seat in sorted(seats.items(), key=lambda pair: pair[1])
            },
        },
    }


def season_winner_data(alms_layout: dict, alms_config: dict) -> dict:
    """How many winner sockets the record has, which is what caps the row."""
    return {"slotCount": len(placeholder_slots(alms_layout, alms_rules(alms_config)))}


def acolyte_control_data(board_layout: dict) -> dict:
    default = default_player_board_v2_state(board_layout)
    roles = [role["id"] for role in board_layout["worker_roles"]]
    return {
        "abbeyId": ABBEY_PLACE_ID,
        "abbeyCapacity": token_slot_count(board_layout),
        "roleLimit": ROLE_ACOLYTE_LIMIT,
        "roles": roles,
        "places": [{"id": place_id, "label": label} for place_id, label in acolyte_places(board_layout)],
        "state": {
            str(seat): {
                "playerId": player_id,
                "villageSerfs": int(default["village_serfs"]),
                "abbeyAcolytes": int(default["abbey_acolytes"]),
                "roles": {role: int(default["roles"].get(role, 0)) for role in roles},
            }
            for seat, player_id in enumerate(SEATED_PLAYERS, start=1)
        },
    }


def turn_flow_data(duty_layout: dict) -> dict:
    """Who the turn belongs to, and the colour the board should ring their choices in.

    One seat, because nothing on this page picks an active player yet: the compact rows each name
    a seat of their own for the move they make, and none of them speaks for the turn. The whole
    map is carried anyway, so the seat a turn belongs to becomes a variable rather than a rewrite
    when there is something to set it from.
    """
    fills = {player["id"]: player["fill"] for player in duty_layout["players"]}
    return {
        "seat": DEFAULT_CONTROL_PLAYER_SEAT,
        "colors": {
            str(seat): fills[player_id] for seat, player_id in enumerate(SEATED_PLAYERS, start=1)
        },
    }


def render_turn_flow_script() -> str:
    """The turn flow, as the phases a click moves the wheel between.

        idle -> sow_armed -> sowing -> sow_complete -> duty_selected -> resolution_selected
                                ^         |
                                |         v
                          branch_choice   idle

    Sow arms the nine spaces; clicking one lifts the active seat's cubes there into the counter in
    the corner and the hand starts walking, putting one cube down at each position it comes to. It
    stops at a fork, lights the ways out and waits for one to be clicked; then it walks on. When the
    hand is empty the tiles it reached are offered as the duty to take, and taking one with `Action`
    or `Tithe` sends that seat's cubes there home to the City. `Reset` puts the board back the way
    Sow found it at any point along the way.

    A setup sow is the same walk with a different frame around it: every seat starts with five
    acolytes in the City and puts them out, one seat after another, before the first turn. It
    starts itself, since the City is the only place it could start from -- so `Sow` has nothing to
    ask and stays dark, and the walk stops at the City's fork straight away. And it ends with no
    duty offered, `Action` and `Tithe` dark, and `Confirm` lit to hand the wheel to the next seat.

    What any of it is worth is another matter. Nothing here resolves an action or a tithe, scores
    anything, or reads or writes `GameState`: this is the shape of a turn drawn on a board.

    Everything it moves by is a board position -- `city`, `north`, `north_east` and the rest, as
    `configs/board.json` names them -- read off `data-board-position` and the arrows' own
    `data-from-position` and `data-to-position`. The names printed on the tiles are never consulted,
    because turning the tiles moves a duty to another position and moves no position at all.

    Both halves of it are the same trick, run in opposite directions: a cube is picked up by hiding
    the rect it stands in and put down by showing an empty one, so nothing is ever drawn into or
    cut out of the wheel and Reset can hand the board straight back -- including a City column that
    was only partly standing to begin with.
    """
    return """
  /* --- the turn flow ------------------------------------------------------------------------
     Local UI phases only: nothing below sows a cube, resolves an action, or touches GameState. */
  var turnOverlay = dutyPanel
    ? dutyPanel.querySelector('[data-component="duty-wheel-turn-controls"]')
    : null;
  /* Movement is in board positions -- city, north, north_east and the rest -- and never in the
     names printed on the tiles. Turning the tiles moves a duty to another position; it moves no
     position anywhere, so a flow keyed to the labels would start walking the wrong way round the
     board the first time the tiles were turned. */
  var dutySpaces = dutyPanel ? dutyPanel.querySelectorAll('[data-board-position]') : [];
  var dutyOrnaments = dutyPanel ? dutyPanel.querySelectorAll('[data-ornament-position]') : [];
  var dutyArrows = dutyPanel
    ? dutyPanel.querySelectorAll('[data-from-position][data-to-position]')
    : [];
  /* The middle space, as the one the ring of arrows does not run through: every duty tile has a
     place in that ring and says which, and the City is the space that has none. */
  var cityPosition = null;
  Array.prototype.forEach.call(dutySpaces, function (space) {
    if (!space.hasAttribute('data-duty-ring-index')) {
      cityPosition = space.getAttribute('data-board-position');
    }
  });
  /* The board's directed graph, as the arrows drawn on it: every way out of every position. */
  var outgoingEdgesByPosition = {};
  Array.prototype.forEach.call(dutyArrows, function (arrow) {
    var from = arrow.getAttribute('data-from-position');
    outgoingEdgesByPosition[from] = (outgoingEdgesByPosition[from] || []).concat([arrow]);
  });

  function turnControl(name) {
    return turnOverlay ? turnOverlay.querySelector('[data-turn-control="' + name + '"]') : null;
  }

  /* Enabled is what the plaque looks like, not what it accepts: the handlers ask the phase. */
  function setTurnControlState(name, enabled, active) {
    var control = turnControl(name);
    if (!control) {
      return;
    }
    control.setAttribute('data-turn-control-enabled', enabled ? 'true' : 'false');
    control.setAttribute('data-turn-control-active', active ? 'true' : 'false');
    control.setAttribute('aria-disabled', enabled ? 'false' : 'true');
  }

  /* A setup sow is not a turn: the seat is putting its acolytes out, not taking a duty. So the
     two plaques that do something to a duty stay dark all through it, and `Confirm` -- which has
     nothing behind it in a normal turn -- is the one that lights, to hand the wheel to the next
     seat. */
  function refreshTurnControls() {
    var started = state.turn.phase !== 'idle';
    var sown = state.turn.phase === 'sow_complete';
    /* A setup sow starts itself from the City, so `Sow` has nothing to ask and stays dark; and
       `Reset`, which is then the only way back to the start of one, stays lit throughout. */
    var asking = !state.setup.on;
    setTurnControlState('sow', asking, asking && started);
    setTurnControlState('reset', started || state.setup.on, false);
    /* A duty has to be chosen before there is anything to do to it, and once one of the two has
       been pressed the pressed one stays lit to say which it was. */
    ['action', 'tithe'].forEach(function (name) {
      var chosen = !state.setup.on && state.turn.phase === 'duty_selected';
      setTurnControlState(name, chosen, state.turn.resolution === name);
    });
    setTurnControlState('confirm', state.setup.on && sown, false);
  }

  function setTurnPhase(phase) {
    state.turn.phase = phase;
    if (turnOverlay) {
      turnOverlay.setAttribute('data-turn-state', phase);
    }
    refreshTurnControls();
  }

  function setCubesInHand(count) {
    state.turn.cubesInHand = count;
    var counter = turnOverlay ? turnOverlay.querySelector('[data-turn-counter]') : null;
    if (!counter) {
      return;
    }
    counter.setAttribute('data-turn-counter-value', String(count));
    counter.setAttribute('aria-label', 'Cubes in hand: ' + count);
    var label = counter.querySelector('text');
    if (label) {
      label.textContent = '\\u00d7 ' + count;
    }
  }

  function spaceAt(position) {
    return dutyPanel
      ? dutyPanel.querySelector('[data-board-position="' + position + '"]')
      : null;
  }

  /* The trefoil drawn over a space. The ornaments are one layer across the whole board rather
     than part of the spaces, so each says which position it stands over. */
  function ornamentAt(position) {
    return dutyPanel
      ? dutyPanel.querySelector('[data-ornament-position="' + position + '"]')
      : null;
  }

  function seatBoard(seat) {
    return document.querySelector(
      '[data-component="player-board-v2"][data-player-seat="' + seat + '"]');
  }

  function activeSeatElement() {
    return seatBoard(state.activeSeat);
  }

  function playerIdForSeat(seat) {
    var board = seatBoard(seat);
    return board ? board.getAttribute('data-player') : null;
  }

  /* The seats in play, in the order they are dealt to and take their turns. */
  function seatsAtTable() {
    var seats = [];
    for (var seat = 1; seat <= state.count; seat += 1) {
      seats.push(seat);
    }
    return seats;
  }

  /* Which player a seat is, asked of the board that is actually on the table rather than worked
     out here. Seat order and player ids are not the same list -- the first seat is red, and red is
     `player_two` -- so anything pairing them up itself would pair them wrongly. */
  function activePlayerId() {
    return playerIdForSeat(state.activeSeat);
  }

  function activePlayerColor() {
    var board = activeSeatElement();
    return board ? board.getAttribute('data-player-color') : null;
  }

  /* The board whose turn it is says so itself, with the wash of its own colour its renderer left
     hidden along its bottom edge; the same colour rings the space that turn starts from. Nothing
     is restyled and no size is written, so the row's widths and heights do not move: each board is
     told whether it is the one, and the stylesheet does the rest. */
  function updateActiveSeatIndicator() {
    Array.prototype.forEach.call(seatBoards, function (board) {
      var active = Number(board.getAttribute('data-player-seat')) === state.activeSeat;
      board.setAttribute('data-active-seat', active ? 'true' : 'false');
    });
    if (!stage) {
      return;
    }
    stage.setAttribute('data-active-player-seat', String(state.activeSeat));
    stage.setAttribute('data-active-player-color', activePlayerColor() || '');
    stage.style.setProperty('--active-player', TURN.colors[String(state.activeSeat)]);
  }

  function setActiveSeat(seat) {
    state.activeSeat = seat;
    updateActiveSeatIndicator();
  }

  function armStartSpaces(armed) {
    Array.prototype.forEach.call(dutySpaces, function (space) {
      if (armed) {
        space.setAttribute('data-turn-start-candidate', 'true');
      } else {
        space.removeAttribute('data-turn-start-candidate');
      }
    });
  }

  function markStartSpace(position) {
    Array.prototype.forEach.call(dutySpaces, function (space) {
      if (space.getAttribute('data-board-position') === position) {
        space.setAttribute('data-turn-start-selected', 'true');
      } else {
        space.removeAttribute('data-turn-start-selected');
      }
    });
  }

  /* The tally the table is playing: every count has one drawn, and only this one is showing. It
     is looked for inside the space itself, so what the tally happens to be named never matters. */
  function activeTallyForPosition(position) {
    var space = spaceAt(position);
    return space
      ? space.querySelector('[data-cube-tally][data-player-count="' + state.count + '"]')
      : null;
  }

  function visibleCubesForPosition(position) {
    var tally = activeTallyForPosition(position);
    if (!tally) {
      return [];
    }
    return Array.prototype.filter.call(tally.querySelectorAll('rect'), function (cube) {
      return cube.getAttribute('opacity') !== '0';
    });
  }

  /* One seat's column on one space, bottom cube first, which is the order the wheel draws them
     in. Every cube says whose it is, so this is also what keeps the other seats' cubes and the
     neutral column's black ones out of anything a seat does. */
  function columnForPosition(position, playerId) {
    var tally = activeTallyForPosition(position);
    if (!tally) {
      return [];
    }
    return Array.prototype.filter.call(tally.querySelectorAll('rect'), function (cube) {
      return cube.getAttribute('data-player') === playerId;
    });
  }

  /* A hand picks up its own cubes and nothing else: the other seats' cubes, the neutral column's,
     and the slots nobody is standing in -- drawn but hidden, so not visible -- all stay put. */
  function visibleActivePlayerCubesForPosition(position) {
    return columnForPosition(position, activePlayerId()).filter(function (cube) {
      return cube.getAttribute('opacity') !== '0';
    });
  }

  /* Stand a column at a given height, which is how a deal is made: the wheel draws every slot a
     column has room for, so setting one is showing the cubes up to it and hiding the rest. */
  function standColumn(position, playerId, standing) {
    columnForPosition(position, playerId).forEach(function (cube, index) {
      cube.setAttribute('opacity', index < standing ? '1' : '0');
    });
  }

  /* Where the next cube can be put down: the lowest empty slot in the active seat's column there.
     The wheel draws every slot a column has room for and hides the empty ones, so putting a cube
     on a space is turning one of them on rather than drawing into the board. A column with none
     left is a column with no room, which is what stops a sow short. */
  function firstEmptySlotForPosition(position) {
    var playerId = activePlayerId();
    var tally = activeTallyForPosition(position);
    if (!tally) {
      return null;
    }
    return Array.prototype.filter.call(tally.querySelectorAll('rect'), function (cube) {
      return cube.getAttribute('data-player') === playerId
        && cube.getAttribute('opacity') === '0';
    })[0] || null;
  }

  function placeOneCubeAtPosition(position) {
    var slot = firstEmptySlotForPosition(position);
    if (!slot) {
      return false;
    }
    slot.setAttribute('opacity', '1');
    state.turn.sown.push(slot);
    setCubesInHand(state.turn.cubesInHand - 1);
    return true;
  }

  function resetSownCubes() {
    state.turn.sown.forEach(function (slot) {
      slot.setAttribute('opacity', '0');
    });
    state.turn.sown = [];
  }

  /* Taken off the board, not taken away: what each cube was showing is remembered, so putting it
     back cannot stand a seat in a slot it was not standing in. Both the hand that picks cubes up
     to sow them and the recall that sends them home from a duty use this pair. */
  function hideCubes(cubes) {
    return cubes.map(function (cube) {
      var held = { cube: cube, opacity: cube.getAttribute('opacity') };
      cube.setAttribute('opacity', '0');
      return held;
    });
  }

  function restoreCubes(held) {
    held.forEach(function (entry) {
      if (entry.opacity === null) {
        entry.cube.removeAttribute('opacity');
      } else {
        entry.cube.setAttribute('opacity', entry.opacity);
      }
    });
  }

  function hidePickupCubes(cubes) {
    state.turn.pickedUp = hideCubes(cubes);
    setCubesInHand(cubes.length);
  }

  function restorePickupCubes() {
    restoreCubes(state.turn.pickedUp);
    state.turn.pickedUp = [];
  }

  /* Every way out of a position, ring arrows and middle arrows alike, since both carry the pair
     of positions they join. One way out is not a choice, so only a position with more than one
     lights up: on this board that is the City, east and west, and no rule had to be written down
     to say so -- it falls out of the graph, and it keeps falling out of it however the tiles are
     turned. Kogge and Cloisters would add and drop edges here; neither is drawn yet. */
  function branchArrowsFrom(position) {
    return outgoingEdgesByPosition[position] || [];
  }

  function highlightBranchChoices(arrows) {
    arrows.forEach(function (arrow) {
      arrow.setAttribute('data-turn-branch-choice', 'true');
    });
  }

  function clearBranchChoices() {
    Array.prototype.forEach.call(dutyArrows, function (arrow) {
      arrow.removeAttribute('data-turn-branch-choice');
    });
  }

  function armSow() {
    if (state.setup.on || state.turn.phase !== 'idle') {
      return;
    }
    armStartSpaces(true);
    setTurnPhase('sow_armed');
  }

  /* Where the hand stands, and the way it came. */
  function setCurrentPosition(position) {
    state.turn.current = position;
    state.turn.route.push(position);
    if (turnOverlay) {
      turnOverlay.setAttribute('data-turn-current-position', position);
      turnOverlay.setAttribute('data-turn-route', state.turn.route.join('>'));
    }
  }

  function sowAlong(arrow) {
    var next = arrow.getAttribute('data-to-position');
    if (!placeOneCubeAtPosition(next)) {
      return false;
    }
    setCurrentPosition(next);
    return true;
  }

  /* The hand walks the board and puts one cube down at each position it comes to. It stops only
     at a fork: one way out is not a choice, so nothing is asked about it, and the walk runs on
     until either the hand is empty or the board asks which way.

     It also stops where there is nowhere to put the next cube -- a column with no room left, or a
     position with no way out of it. Neither should happen on this board, since every position has
     an arrow leaving it and a sow is short, but a tile only shows three cubes to a seat while the
     rules cap nothing, so a column can fill. The hand keeps what it is still holding, the counter
     goes on showing it, and `Reset` is the way out. */
  function continueSowing() {
    setTurnPhase('sowing');
    while (state.turn.cubesInHand > 0) {
      var ways = branchArrowsFrom(state.turn.current);
      if (ways.length > 1) {
        highlightBranchChoices(ways);
        setTurnPhase('branch_choice');
        return;
      }
      if (!ways.length || !sowAlong(ways[0])) {
        return;
      }
    }
    completeSowing();
  }

  /* A setup sow ends with no duty on offer: the seat was putting its acolytes out, not taking a
     duty, and what is waiting for it is `Confirm` rather than `Action` or `Tithe`. */
  function completeSowing() {
    clearBranchChoices();
    setTurnPhase('sow_complete');
    armDutyChoices(!state.setup.on);
  }

  /* The duties a finished sow leaves standing to be picked from: every tile the seat has an
     acolyte standing on, less the City, which is not a duty.

     It is read off the board rather than off the way the hand walked. A seat has acolytes out on
     the wheel before its turn begins and they are as much its own as the ones it has just sown, so
     asking where the walk went would offer it only the tiles it happened to pass and hide the rest
     of its own. Asking the board is also the whole of what makes the other three kinds of cube no
     part of the choice: another seat's, the neutral column's, and the slots nobody is standing in
     -- drawn but hidden, so not visible -- are none of them this seat's visible cubes. */
  function occupiedDutyPositions() {
    return Array.prototype.map
      .call(dutySpaces, function (space) {
        return space.getAttribute('data-board-position');
      })
      .filter(function (position) {
        return position !== cityPosition
          && visibleActivePlayerCubesForPosition(position).length > 0;
      });
  }

  function armDutyChoices(armed) {
    var eligible = armed ? occupiedDutyPositions() : [];
    Array.prototype.forEach.call(dutySpaces, function (space) {
      if (eligible.indexOf(space.getAttribute('data-board-position')) === -1) {
        space.removeAttribute('data-turn-duty-candidate');
      } else {
        space.setAttribute('data-turn-duty-candidate', 'true');
      }
    });
  }

  /* The chosen duty is marked twice over: ringed like the space the turn started from, and with
     the three lobes of its trefoil coloured in. The trefoil is drawn in a layer of its own above
     the board rather than inside the space, so the two are marked separately. */
  function markDutyChoice(position) {
    Array.prototype.forEach.call(dutySpaces, function (space) {
      space.removeAttribute('data-turn-duty-selected');
    });
    Array.prototype.forEach.call(dutyOrnaments, function (ornament) {
      ornament.removeAttribute('data-turn-duty-selected');
    });
    [spaceAt(position), ornamentAt(position)].forEach(function (node) {
      if (node) {
        node.setAttribute('data-turn-duty-selected', 'true');
      }
    });
  }

  /* What may be picked is what is on offer, and what is on offer is what `armDutyChoices` marked:
     the tiles the seat is standing on, from when the hand empties until one of them is taken.
     Nothing is ever marked during a setup sow, so nothing can be picked during one either. */
  function selectDuty(position) {
    var space = spaceAt(position);
    if (!space || space.getAttribute('data-turn-duty-candidate') !== 'true') {
      return;
    }
    state.turn.duty = position;
    markDutyChoice(position);
    if (turnOverlay) {
      turnOverlay.setAttribute('data-turn-duty', position);
    }
    setTurnPhase('duty_selected');
  }

  /* Both plaques do the one thing there is to do yet: the seat's cubes come off the duty it chose
     and go home to its City column. What either of them is actually for -- resolving the duty,
     taking the tithe -- is still to come, so all that is kept is which of them was pressed.

     A cube that finds no room in the City is left standing where it is. The City draws a seat six
     slots while the rules cap nothing, so a column can fill; a cube is only ever hidden in one
     place and shown in another, so nothing is lost either way. */
  function resolveDuty(resolution) {
    if (state.turn.phase !== 'duty_selected') {
      return;
    }
    var home = [];
    var sent = [];
    visibleActivePlayerCubesForPosition(state.turn.duty).forEach(function (cube) {
      var slot = firstEmptySlotForPosition(cityPosition);
      if (!slot) {
        return;
      }
      slot.setAttribute('opacity', '1');
      home.push(slot);
      sent.push(cube);
    });
    state.turn.standingInCity = home;
    state.turn.recalled = hideCubes(sent);
    state.turn.resolution = resolution;
    /* The choice is closed once the cubes are home, so the other tiles stop offering themselves. */
    armDutyChoices(false);
    if (turnOverlay) {
      turnOverlay.setAttribute('data-turn-resolution', resolution);
    }
    setTurnPhase('resolution_selected');
  }

  function undoRecall() {
    state.turn.standingInCity.forEach(function (slot) {
      slot.setAttribute('opacity', '0');
    });
    state.turn.standingInCity = [];
    restoreCubes(state.turn.recalled);
    state.turn.recalled = [];
  }

  /* The seat's cubes there come up into the hand and the walk begins. A space with none of them
     on it is nothing to start from, so nothing happens at all.

     A turn is asked which space to start from and a setup sow is not -- it always starts from the
     City -- so where the start comes from is the caller's business, and only the starting is
     here. For the same reason a setup sow passes `{ ring: false }`: the ring round a space is the
     answer to a question, and one that was never asked has no answer to show. What a setup is
     waiting for is a road, and the roads are lit. */
  function beginSowFrom(position, options) {
    var cubes = visibleActivePlayerCubesForPosition(position);
    if (!cubes.length) {
      return;
    }
    state.turn.start = position;
    armStartSpaces(false);
    markStartSpace(options && options.ring === false ? null : position);
    hidePickupCubes(cubes);
    setCurrentPosition(position);
    continueSowing();
  }

  /* Clicking an armed space. The click is spent either way, so the board stays armed for another
     one rather than refusing this one. */
  function selectStartSpace(position) {
    if (state.turn.phase !== 'sow_armed') {
      return;
    }
    beginSowFrom(position);
  }

  /* The way out that was asked for: one cube goes down at the far end of the arrow, and the walk
     picks up again from there. */
  function chooseRoute(arrow) {
    if (state.turn.phase !== 'branch_choice') {
      return;
    }
    if (arrow.getAttribute('data-from-position') !== state.turn.current) {
      return;
    }
    state.turn.routeChoice =
      arrow.getAttribute('data-from-position') + ':' + arrow.getAttribute('data-to-position');
    if (turnOverlay) {
      turnOverlay.setAttribute('data-last-route-choice', state.turn.routeChoice);
    }
    clearBranchChoices();
    setTurnPhase('sowing');
    if (sowAlong(arrow)) {
      continueSowing();
    }
  }

  /* Putting a turn down is two separate things, and they are kept apart because there is one
     caller -- a confirmed setup sow -- that wants the second without the first.

     Every cube goes back where the turn found it, in the order the turn moved them, last thing
     first: what the recall took home, then what the sow put down, then what the hand picked up. A
     cube can be sown into the very slot it was lifted out of and recalled out of that same slot
     again, so each layer has to hand the board back to the one beneath it before that one has its
     say. Which cubes those are is the three ledgers, and nothing else: a turn that has been
     accepted drops them, and then this moves nothing at all. */
  function putCubesBack() {
    undoRecall();
    resetSownCubes();
    restorePickupCubes();
  }

  /* And everything the turn wrote on the board about itself comes off. Not one cube is touched
     here, which is what lets an accepted setup sow be cleaned up without being undone. */
  function clearTurnMarks() {
    setCubesInHand(0);
    armStartSpaces(false);
    markStartSpace(null);
    armDutyChoices(false);
    markDutyChoice(null);
    clearBranchChoices();
    state.turn.start = null;
    state.turn.current = null;
    state.turn.route = [];
    state.turn.routeChoice = null;
    state.turn.duty = null;
    state.turn.resolution = null;
    if (turnOverlay) {
      turnOverlay.removeAttribute('data-last-route-choice');
      turnOverlay.removeAttribute('data-turn-current-position');
      turnOverlay.removeAttribute('data-turn-route');
      turnOverlay.removeAttribute('data-turn-duty');
      turnOverlay.removeAttribute('data-turn-resolution');
    }
    setTurnPhase('idle');
  }

  function resetTurnFlow() {
    putCubesBack();
    clearTurnMarks();
  }

  /* A space is clicked for two different reasons at two different points in a turn: to start from
     before the sow, and to choose a duty after it. */
  Array.prototype.forEach.call(dutySpaces, function (space) {
    space.addEventListener('click', function () {
      var position = space.getAttribute('data-board-position');
      selectStartSpace(position);
      selectDuty(position);
    });
  });

  Array.prototype.forEach.call(dutyArrows, function (arrow) {
    arrow.addEventListener('click', function () {
      if (arrow.getAttribute('data-turn-branch-choice') === 'true') {
        chooseRoute(arrow);
      }
    });
  });

  if (turnControl('sow')) {
    turnControl('sow').addEventListener('click', armSow);
  }

  if (turnControl('reset')) {
    turnControl('reset').addEventListener('click', function () {
      if (state.setup.on) {
        restartSetupSow();
      } else if (state.turn.phase !== 'idle') {
        resetTurnFlow();
      }
    });
  }

  if (turnControl('confirm')) {
    turnControl('confirm').addEventListener('click', confirmSetupSow);
  }

  ['action', 'tithe'].forEach(function (resolution) {
    if (turnControl(resolution)) {
      turnControl(resolution).addEventListener('click', function () {
        resolveDuty(resolution);
      });
    }
  });

  updateActiveSeatIndicator();
"""


def render_compact_controls_script(
    map_layout: dict,
    piety_layout: dict,
    board_layout: dict,
    alms_layout: dict,
    alms_config: dict,
    placements: list[dict],
    duty_layout: dict,
) -> str:
    """Compact local controls: player count, setup roll, discs, resources, winners, buildings,
    serfs and acolytes, the duty wheel, and the turn flow drawn on it.
    """
    buildings = json.dumps(building_control_data(board_layout, placements), separators=(",", ":"))
    duty = json.dumps(duty_control_data(duty_layout), separators=(",", ":"))
    turn_flow = render_turn_flow_script()
    return f"""<script>
(function () {{
  var VISIBLE = {json.dumps(visible_seats_by_count(), separators=(",", ":"))};
  var DEFAULT_COUNT = {DEFAULT_PLAYER_COUNT};
  var SETUP = {json.dumps(setup_roll_data(map_layout), separators=(",", ":"))};
  var DISC = {json.dumps(disc_motion_data(alms_layout, alms_config, piety_layout), separators=(",", ":"))};
  var ACOLYTES = {json.dumps(acolyte_control_data(board_layout), separators=(",", ":"))};
  var RESOURCES = {json.dumps(resource_control_data(board_layout), separators=(",", ":"))};
  var WINNERS = {json.dumps(season_winner_data(alms_layout, alms_config), separators=(",", ":"))};
  var BUILDINGS = {buildings};
  var DUTY = {duty};
  var TURN = {json.dumps(turn_flow_data(duty_layout), separators=(",", ":"))};
  var SETUP_CUBES = {SETUP_CITY_CUBES};

  function cityOpening() {{
    var opening = {{}};
    Object.keys(ACOLYTES.state).forEach(function (seat) {{
      opening[seat] = DUTY.city.opening;
    }});
    return opening;
  }}

  var state = {{
    count: DEFAULT_COUNT,
    roll: SETUP.defaultRoll,
    path: [],
    shipPosition: 0,
    discs: JSON.parse(JSON.stringify(DISC.initial)),
    acolytes: JSON.parse(JSON.stringify(ACOLYTES.state)),
    resources: JSON.parse(JSON.stringify(RESOURCES.state)),
    /* Seat numbers in slot order, so the row of sockets is just this list drawn. */
    winners: [],
    buildings: JSON.parse(JSON.stringify(BUILDINGS.state)),
    /* What each seat is standing in the City, which every column opens holding. */
    city: cityOpening(),
    dutySetup: 0,
    merchant: DUTY.merchantStart,
    /* Whose turn it is. Nothing advances it yet, so it stays on the first seat; it is kept out
       here rather than inside the turn because a seat outlives any one sow. */
    activeSeat: TURN.seat,
    /* Which seat the first player marker sits with. It is always with someone, and it opens with
       seat 1 because every piety disc starts on 0 and the tie resolves to the first board. It
       decides nothing about turn order here: it moves a seal and that is all. */
    firstPlayerSeat: {FIRST_PLAYER_SEAT_AT_START},
    /* The turn drawn on the wheel: which phase it is in, where it started and where the hand
       stands now, the way it came, what is in hand, the cubes lifted off the board to put it
       there, the slots it has since stood cubes in, which way out was last picked, the duty it
       chose at the end of it, and what it chose to do there. */
    turn: {{
      phase: 'idle',
      start: null,
      current: null,
      route: [],
      cubesInHand: 0,
      pickedUp: [],
      sown: [],
      routeChoice: null,
      duty: null,
      resolution: null,
      recalled: [],
      standingInCity: []
    }},
    /* The setup sow: whether the board is dealt for one now, which seats have confirmed theirs,
       and whether one has been run through to the end since the page opened. */
    setup: {{
      on: false,
      done: [],
      finished: false
    }}
  }};

  var countButtons = document.querySelectorAll('[data-player-count-button]');
  var rollButtons = document.querySelectorAll('[data-setup-roll-button]');
  var seatBoards = document.querySelectorAll('[data-player-seat].p-player');
  var discButtons = document.querySelectorAll('[data-disc-track][data-disc-delta]');
  var discPlayerSeat = document.getElementById('disc-player-seat');
  var firstPlayerSeat = document.getElementById('first-player-seat');
  var firstPlayerSeals = document.querySelectorAll('[data-first-player-seal][data-player-seat]');
  var pietyTrack = document.querySelector('[data-first-player-seat]');
  var acolytePlayerSeat = document.getElementById('acolyte-player-seat');
  var acolyteSource = document.getElementById('acolyte-source');
  var acolyteTarget = document.getElementById('acolyte-target');
  var moveAcolyte = document.getElementById('move-acolyte');
  var serfToAbbey = document.querySelector('[data-serf-to-abbey-button]');
  var abbeyToCity = document.querySelector('[data-abbey-to-city-button]');
  var villageToCity = document.querySelector('[data-village-to-city-button]');
  var shipButton = document.querySelector('[data-ship-advance]');
  var resourceButtons = document.querySelectorAll('[data-resource-button]');
  var winnerButtons = document.querySelectorAll('[data-alms-winner-button]');
  /* Row three's dropdown is shared: it picks the seat for the winner cube and for the
     buildings alike, which is why it is not named after either. */
  var rowThreeSeat = document.getElementById('alms-winner-player-seat');
  var buildingSelect = document.getElementById('buy-building');
  var buyButton = document.querySelector('[data-building-buy-button]');
  var donateSlot = document.getElementById('donate-building-slot');
  var donateButton = document.querySelector('[data-building-donate-button]');
  var dutyRandomize = document.querySelector('[data-duty-randomize-button]');
  var setupButton = document.querySelector('[data-setup-mode-button]');
  var merchantAdvance = document.querySelector('[data-merchant-advance-button]');
  var stage = document.querySelector('.game-table-stage');
  var almsPanel = document.querySelector('.p-alms');
  var dutyPanel = document.querySelector('.p-action');
  var mapPanel = document.querySelector('.p-map');
  var setupGroups = mapPanel ? mapPanel.querySelectorAll('g[data-slot]') : [];
  var shipMarker = mapPanel ? mapPanel.querySelector('#ship-marker') : null;

  function visibleSeats(count) {{
    return VISIBLE[String(count)] || VISIBLE[String(DEFAULT_COUNT)] || [];
  }}

  function boardDiscs(track) {{
    var board = document.querySelector(track === 'alms' ? '.p-alms' : '.p-piety');
    return board ? board.querySelectorAll('[data-player-disc][data-player-seat]') : [];
  }}

  function discPoint(track, seat, position) {{
    return DISC.targets[track][String(seat)][String(position)];
  }}

  function pairPoint(track, position) {{
    return DISC.pair[track][String(position)];
  }}

  function isAlmsFirst(position) {{
    return String(position) === String(DISC.first.alms);
  }}

  function almsFirstOccupied(exceptSeat) {{
    return Object.keys(state.discs.alms).some(function (seat) {{
      return Number(seat) !== exceptSeat && isAlmsFirst(state.discs.alms[seat]);
    }});
  }}

  function nextAlmsPosition(current, delta, seat) {{
    var maximum = Number(DISC.max.alms);
    if (delta > 0) {{
      if (isAlmsFirst(current)) {{
        return DISC.first.alms;
      }}
      var step = Number(current);
      if (step < maximum) {{
        return step + 1;
      }}
      if (step === maximum && !almsFirstOccupied(seat)) {{
        return DISC.first.alms;
      }}
      return maximum;
    }}
    if (delta < 0) {{
      if (isAlmsFirst(current)) {{
        return maximum;
      }}
      return Math.max(0, Number(current) - 1);
    }}
    return current;
  }}

  function renderDiscTrack(track) {{
    var shown = visibleSeats(state.count);
    Array.prototype.forEach.call(boardDiscs(track), function (disc) {{
      var seat = Number(disc.getAttribute('data-player-seat'));
      var position = state.discs[track][String(seat)];
      var point = discPoint(track, seat, position);
      var x = point[0];
      var y = point[1];
      if (state.count === 2 && (seat === 1 || seat === 2)) {{
        var pair = pairPoint(track, position);
        x = pair[0];
        y = seat === 1 ? pair[1] : pair[2];
      }}
      disc.setAttribute('cx', Number(x).toFixed(1));
      disc.setAttribute('cy', Number(y).toFixed(1));
      disc.style.visibility = shown.indexOf(seat) === -1 ? 'hidden' : 'visible';
      disc.setAttribute(track === 'alms' ? 'data-alms-position' : 'data-piety-position', String(position));
    }});
  }}

  /* Every seat's seal is already struck into the panel, in that seat's own colour, and all but one
     are hidden. So moving the marker is showing one and hiding the rest -- exactly what
     renderDiscTrack does with the discs. Nothing here computes a colour, and nothing here may:
     the wax, the rim, the ring and the crown are all derived in the renderer, and a second
     derivation written in JavaScript would be a copy to keep in step with the first. */
  function renderFirstPlayerSeal() {{
    Array.prototype.forEach.call(firstPlayerSeals, function (seal) {{
      var seat = Number(seal.getAttribute('data-player-seat'));
      seal.style.visibility = seat === state.firstPlayerSeat ? 'visible' : 'hidden';
    }});
  }}

  function setFirstPlayerSeat(seat) {{
    state.firstPlayerSeat = seat;
    if (firstPlayerSeat) {{
      firstPlayerSeat.value = String(seat);
    }}
    /* The attribute is what names the holder, so it moves with the marker rather than staying on
       whichever seat the renderer struck it for. */
    if (pietyTrack) {{
      pietyTrack.setAttribute('data-first-player-seat', String(seat));
    }}
    renderFirstPlayerSeal();
  }}

  function moveDisc(track, delta) {{
    var seat = Number(discPlayerSeat.value);
    var key = String(seat);
    var current = state.discs[track][key];
    var next = current;
    if (track === 'alms') {{
      next = nextAlmsPosition(current, delta, seat);
    }} else {{
      var maximum = Number(DISC.max[track]);
      next = Math.max(0, Math.min(maximum, Number(current) + delta));
    }}
    state.discs[track][key] = next;
    renderDiscTrack(track);
  }}

  function renderSeatBoards() {{
    var shown = visibleSeats(state.count);
    Array.prototype.forEach.call(seatBoards, function (board) {{
      var seat = Number(board.getAttribute('data-player-seat'));
      /* visibility, not display: hidden seats keep their width, so the row's geometry
         and scale never move with player count. */
      board.style.visibility = shown.indexOf(seat) === -1 ? 'hidden' : 'visible';
    }});
  }}

  function rotatedPath(roll) {{
    var startHex = SETUP.startHexByRoll[String(roll)];
    var offset = SETUP.edgePath.indexOf(startHex);
    return SETUP.edgePath.slice(offset).concat(SETUP.edgePath.slice(0, offset));
  }}

  function placeOnHex(element, hexLabel) {{
    var center = SETUP.hexCenters[hexLabel];
    element.setAttribute(
      'transform',
      'translate(' + Number(center[0]).toFixed(1) + ',' + Number(center[1]).toFixed(1) + ')'
    );
  }}

  function renderShip() {{
    if (shipMarker) {{
      placeOnHex(shipMarker, state.path[state.shipPosition]);
    }}
  }}

  /* One stop clockwise, wrapping at the end of the path -- the same walk the
     setup page's Advance ship button takes. There is no reset button here; a
     setup roll puts the ship back on the first stop. */
  function advanceShip() {{
    state.shipPosition = (state.shipPosition + 1) % state.path.length;
    renderShip();
  }}

  function applySetupRoll(roll) {{
    state.roll = roll;
    state.path = rotatedPath(roll);
    state.shipPosition = 0;
    Array.prototype.forEach.call(setupGroups, function (group) {{
      var slot = Number(group.getAttribute('data-slot'));
      placeOnHex(group, state.path[slot - 1]);
    }});
    /* The roll moves every overlay, including the ones a bought building left behind, so what
       is on the map is said again afterwards. */
    renderMapBuildings();
    renderShip();
    Array.prototype.forEach.call(rollButtons, function (button) {{
      var active = Number(button.getAttribute('data-setup-roll-button')) === roll;
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});
  }}

  function acolytesAt(playerState, place) {{
    return place === ACOLYTES.abbeyId ? playerState.abbeyAcolytes : Number(playerState.roles[place] || 0);
  }}

  function setAcolytesAt(playerState, place, count) {{
    if (place === ACOLYTES.abbeyId) {{
      playerState.abbeyAcolytes = count;
    }} else {{
      playerState.roles[place] = count;
    }}
  }}

  function capacityOf(place) {{
    return place === ACOLYTES.abbeyId ? ACOLYTES.abbeyCapacity : ACOLYTES.roleLimit;
  }}

  function show(element, visible) {{
    if (element) {{
      element.setAttribute('opacity', visible ? '1' : '0');
    }}
  }}

  function boardForSeat(seat) {{
    return document.querySelector('.p-player[data-player-seat="' + seat + '"]');
  }}

  /* A cube is a serf while it stands in the Village and an acolyte once it reaches the Abbey or a
     role circle, so both grids are drawn from the one count each holds: every slot is already on
     the board and a move is a change of opacity. */
  function renderBoardCubes(seat) {{
    var board = boardForSeat(seat);
    var playerState = state.acolytes[String(seat)];
    if (!board || !playerState) {{
      return;
    }}
    var held = {{ village: playerState.villageSerfs, abbey: playerState.abbeyAcolytes }};
    Object.keys(held).forEach(function (area) {{
      var slots = board.querySelectorAll('[data-token="' + area + '"]');
      Array.prototype.forEach.call(slots, function (slot) {{
        show(slot, Number(slot.getAttribute('data-token-index')) < held[area]);
      }});
    }});

    ACOLYTES.roles.forEach(function (role) {{
      var count = Number(playerState.roles[role] || 0);
      var roleSlots = board.querySelectorAll('[data-role="' + role + '"]');
      Array.prototype.forEach.call(roleSlots, function (slot) {{
        show(slot, count === (slot.getAttribute('data-role-slot') === 'single' ? 1 : 2));
      }});
    }});
  }}

  /* The City column a seat stands in, in every tally the wheel drew: a column is redrawn once and
     the player-count buttons then show whichever of those tallies the table is playing. */
  function renderCity(seat) {{
    var playerId = (state.acolytes[String(seat)] || {{}}).playerId;
    var standing = state.city[String(seat)];
    if (!dutyPanel || !playerId) {{
      return;
    }}
    var cubes = dutyPanel.querySelectorAll('[data-city-column-player="' + playerId + '"]');
    Array.prototype.forEach.call(cubes, function (cube) {{
      show(cube, Number(cube.getAttribute('data-city-cube')) < standing);
    }});
  }}

  /* A cube leaves the seat's board and stands in its City column. Nothing is checked but room:
     somewhere to take it from, and somewhere for it to stand. */
  function cityRoom(seat) {{
    return state.city[String(seat)] < DUTY.city.capacity;
  }}

  function sendToCity(seat, area) {{
    var playerState = state.acolytes[String(seat)];
    if (!playerState || !cityRoom(seat) || playerState[area] < 1) {{
      return;
    }}
    /* This redraws the City column, so a turn holding cubes out of it is put back first. */
    resetTurnFlow();
    playerState[area] -= 1;
    state.city[String(seat)] += 1;
    renderBoardCubes(seat);
    renderCity(seat);
    refreshBoardButtons();
  }}

  function renderResources(seat) {{
    var board = boardForSeat(seat);
    var amounts = state.resources[String(seat)];
    if (!board || !amounts) {{
      return;
    }}
    RESOURCES.ids.forEach(function (id) {{
      var readout = board.querySelector('[data-player-resource="' + id + '"]');
      if (readout) {{
        readout.textContent = String(amounts[id]);
      }}
    }});
  }}

  function stepResource(id, delta) {{
    var seat = String(discPlayerSeat.value);
    var amounts = state.resources[seat];
    if (!amounts) {{
      return;
    }}
    amounts[id] = Math.max(RESOURCES.floor, amounts[id] + delta);
    renderResources(seat);
  }}

  /* The record's sockets, drawn from `state.winners`: slot n shows the cube of whichever seat
     is nth in the list, and an empty slot shows its dashed socket back. Every cube is already
     on the board, hidden, so this only ever flips opacity. */
  function renderWinners() {{
    if (!almsPanel) {{
      return;
    }}
    for (var slot = 1; slot <= WINNERS.slotCount; slot += 1) {{
      var seat = state.winners[slot - 1];
      var cubes = almsPanel.querySelectorAll('[data-season-end-winner-slot="' + slot + '"]');
      var owner = seat ? ACOLYTES.state[String(seat)].playerId : null;
      Array.prototype.forEach.call(cubes, function (cube) {{
        show(cube, cube.getAttribute('data-player') === owner);
      }});
      /* The socket goes out from under its cube, so no dashed edge shows around it. */
      var socket = almsPanel.querySelector('[data-placeholder-slot="' + slot + '"]');
      show(socket, !owner);
    }}
  }}

  function addWinner() {{
    var seat = Number(rowThreeSeat.value);
    var playerState = state.acolytes[String(seat)];
    if (state.winners.length >= WINNERS.slotCount || playerState.abbeyAcolytes < 1) {{
      return;
    }}
    playerState.abbeyAcolytes -= 1;
    state.winners.push(seat);
    renderBoardCubes(seat);
    renderWinners();
    refreshBoardButtons();
  }}

  function resetWinners() {{
    if (!state.winners.length) {{
      return;
    }}
    var returning = state.winners.slice();
    state.winners = [];
    returning.forEach(function (seat) {{
      var playerState = state.acolytes[String(seat)];
      /* The Abbey holds what it holds: a cube coming back to a full one has nowhere to
         stand, so it is not counted twice over. */
      playerState.abbeyAcolytes = Math.min(
        ACOLYTES.abbeyCapacity, playerState.abbeyAcolytes + 1
      );
      renderBoardCubes(seat);
    }});
    renderWinners();
    refreshBoardButtons();
  }}

  /* Each player count has its own tally drawn on every space, already centred for that many
     columns, so the count only decides which of them shows. A short table plays a black neutral
     column beside the seats and a full one plays none, which is the wheel's own seeding: this
     picks a tally, it does not deal any cubes. */
  function renderDutyTallies() {{
    if (!dutyPanel) {{
      return;
    }}
    var tallies = dutyPanel.querySelectorAll('[data-cube-tally]');
    Array.prototype.forEach.call(tallies, function (tally) {{
      show(tally, tally.getAttribute('data-player-count') === String(state.count));
    }});
  }}

  /* One of the wheel's sample arrangements: the eight titles are rewritten and each space shows
     the Tithe token the tile that landed there brought with it. Taxation is the one tile with no
     Tithe token, so it is drawn without a capsule and stays where it is. */
  /* Turning the tiles changes which duty lies at a position -- its title, its Tithe token, and
     the category the space reports. Where the space stands is not the tiles' to change, so the
     board positions the arrows and the turn flow move by are left exactly as they were. */
  function renderDutySetup() {{
    if (!dutyPanel) {{
      return;
    }}
    DUTY.setups[state.dutySetup].forEach(function (entry) {{
      var space = dutyPanel.querySelector('[data-duty="' + entry.position + '"]');
      if (space) {{
        space.setAttribute('data-duty-category', entry.duty);
      }}
      var label = dutyPanel.querySelector('[data-duty-label="' + entry.position + '"]');
      if (label) {{
        label.textContent = entry.label;
      }}
      var icons = dutyPanel.querySelectorAll(
        '[data-duty-position="' + entry.position + '"][data-tithe-token]');
      Array.prototype.forEach.call(icons, function (icon) {{
        show(icon, icon.getAttribute('data-tithe-token') === entry.tithe_icon);
      }});
    }});
  }}

  function renderMerchant() {{
    if (!dutyPanel) {{
      return;
    }}
    var tokens = dutyPanel.querySelectorAll('[data-token="merchant"]');
    Array.prototype.forEach.call(tokens, function (token) {{
      show(token, token.getAttribute('data-duty-position') === state.merchant);
    }});
    var board = dutyPanel.querySelector('[data-component="duty-wheel"]');
    if (board) {{
      board.setAttribute('data-merchant-token', state.merchant);
    }}
  }}

  function randomizeDuties() {{
    state.dutySetup = (state.dutySetup + 1) % DUTY.setups.length;
    renderDutySetup();
  }}

  /* The next duty tile clockwise, wrapping round the ring. The City is not on the path. */
  function advanceMerchant() {{
    var path = DUTY.merchantPath;
    state.merchant = path[(path.indexOf(state.merchant) + 1) % path.length];
    renderMerchant();
  }}

  function buildingSlotsOf(seat) {{
    return state.buildings.players[String(seat)].buildingSlots;
  }}

  function firstEmptyBuildingSlot(seat) {{
    var slots = buildingSlotsOf(seat);
    for (var index = 0; index < slots.length; index += 1) {{
      if (slots[index] === null) {{
        return index + 1;
      }}
    }}
    return 0;
  }}

  function canDonateBuilding(seat, number) {{
    var entry = buildingSlotsOf(seat)[number - 1];
    return Boolean(entry) && !entry.donated;
  }}

  /* A bought building leaves the map: its recoloured hex and its label both go, and the map's
     own hex underneath them is untouched. What is still for sale is kept here rather than read
     off the map, so a setup roll moves the overlays around without selling anything back. */
  function renderMapBuildings() {{
    if (!mapPanel) {{
      return;
    }}
    var overlays = mapPanel.querySelectorAll(
      '#setup-fills g[data-building-id], #setup-labels g[data-building-id]');
    Array.prototype.forEach.call(overlays, function (overlay) {{
      var slot = overlay.getAttribute('data-slot');
      show(overlay, Object.prototype.hasOwnProperty.call(state.buildings.available, slot));
    }});
  }}

  /* A slot shows its building by pointing at content the page has already defined, so buying
     and donating change a reference rather than drawing anything. The dashed outline is drawn
     over that content and never moves, so a filled slot keeps the border an empty one has. */
  function renderBuildingSlots(seat) {{
    var board = boardForSeat(seat);
    if (!board) {{
      return;
    }}
    buildingSlotsOf(seat).forEach(function (entry, index) {{
      var group = board.querySelector('[data-player-board-slot="' + (index + 1) + '"]');
      if (!group) {{
        return;
      }}
      var donated = Boolean(entry) && entry.donated;
      group.setAttribute(
        'data-building-slot-state', entry === null ? 'empty' : (donated ? 'donated' : 'bought'));
      group.setAttribute('data-building-id', entry === null ? '' : entry.buildingId);
      group.setAttribute('data-setup-slot', entry === null ? '' : entry.setupSlot);
      group.setAttribute('data-donated', donated ? 'true' : 'false');
      var content = group.querySelector('[data-building-content]');
      show(content, entry !== null);
      if (entry !== null && content) {{
        content.setAttribute('href', donated ? entry.donatedContent : entry.boughtContent);
      }}
    }});
  }}

  function renderBuildings() {{
    Object.keys(state.buildings.players).forEach(function (seat) {{
      renderBuildingSlots(seat);
    }});
    renderMapBuildings();
    refreshBuildingButtons();
  }}

  function refreshBuildingButtons() {{
    var seat = Number(rowThreeSeat.value);
    buyButton.disabled = !(buildingSelect.value && firstEmptyBuildingSlot(seat));
    donateButton.disabled = !canDonateBuilding(seat, Number(donateSlot.value));
  }}

  /* Off the map and onto the first empty slot of the chosen board. Nothing is checked but the
     two things that make the move impossible: the building is gone, or the board is full. */
  function buyBuilding() {{
    var seat = Number(rowThreeSeat.value);
    var setupSlot = buildingSelect.value;
    var building = state.buildings.available[setupSlot];
    var number = firstEmptyBuildingSlot(seat);
    if (!building || !number) {{
      return;
    }}
    buildingSlotsOf(seat)[number - 1] = {{
      setupSlot: building.setupSlot,
      buildingId: building.buildingId,
      name: building.name,
      level: building.level,
      boughtContent: building.boughtContent,
      donatedContent: building.donatedContent,
      donated: false
    }};
    delete state.buildings.available[setupSlot];
    /* Sold is sold: it leaves the list it was bought from as well as the map. */
    var option = buildingSelect.querySelector('option[value="' + setupSlot + '"]');
    if (option) {{
      option.parentNode.removeChild(option);
    }}
    renderBuildings();
  }}

  /* One flip, one way: an empty slot has nothing to turn over and a donated one is already
     turned. */
  function donateBuilding() {{
    var seat = Number(rowThreeSeat.value);
    var number = Number(donateSlot.value);
    if (!canDonateBuilding(seat, number)) {{
      return;
    }}
    buildingSlotsOf(seat)[number - 1].donated = true;
    renderBuildings();
  }}

  function canMoveAcolyte() {{
    var seat = String(acolytePlayerSeat.value);
    var playerState = state.acolytes[seat];
    var source = acolyteSource.value;
    var target = acolyteTarget.value;
    return (
      source !== target &&
      acolytesAt(playerState, source) > 0 &&
      acolytesAt(playerState, target) < capacityOf(target)
    );
  }}

  /* A serf becomes an acolyte by walking to the Abbey, so the move needs a cube in the Village
     and a free slot in the Abbey -- the same pair of conditions the game setup page checks. */
  function canMoveSerf() {{
    var playerState = state.acolytes[String(acolytePlayerSeat.value)];
    return playerState.villageSerfs > 0 && playerState.abbeyAcolytes < ACOLYTES.abbeyCapacity;
  }}

  function refreshBoardButtons() {{
    var seat = String(acolytePlayerSeat.value);
    var playerState = state.acolytes[seat];
    moveAcolyte.disabled = !canMoveAcolyte();
    serfToAbbey.disabled = !canMoveSerf();
    abbeyToCity.disabled = !cityRoom(seat) || playerState.abbeyAcolytes < 1;
    villageToCity.disabled = !cityRoom(seat) || playerState.villageSerfs < 1;
  }}

  /* --- the setup sow -------------------------------------------------------------------------
     The game before the game. Every seat starts with five acolytes in the City and sows them out
     onto the wheel, one seat after another, and only when the last has finished does the first
     turn begin. The sowing is the turn flow's, unchanged: setup only deals the board for it, then
     hands it from seat to seat. What is dealt is a board to click on rather than a position in a
     game -- nothing here is worth anything until something that knows the rules is asked.

     It sits with the compact rows and not with the turn flow because it changes what they keep. A
     turn hides cubes and remembers them, so Reset can hand the board straight back; a deal is
     meant to stick, and the City count it writes is the same one `A->C` and `V->C` read. */

  /* A deal is made on the tally the table is playing and nowhere else. The wheel drew a tally for
     every count and shows one at a time, and `renderCity` writes a seat's City column in all of
     them at once -- which would leave the other three saying a seat is in the City while their own
     duty tiles still hold the cubes it sowed out of it. So the columns are stood by hand here, and
     the City count the compact rows keep is written to match what was dealt. */
  function dealSetupCubes() {{
    seatsAtTable().forEach(function (seat) {{
      var playerId = playerIdForSeat(seat);
      Array.prototype.forEach.call(dutySpaces, function (space) {{
        var position = space.getAttribute('data-board-position');
        standColumn(position, playerId, position === cityPosition ? SETUP_CUBES : 0);
      }});
      state.city[String(seat)] = SETUP_CUBES;
    }});
  }}

  /* Pressing `Setup` deals again from the top, whether or not one was already under way. */
  function enterSetupMode() {{
    resetTurnFlow();
    state.setup.on = true;
    state.setup.done = [];
    dealSetupCubes();
    setActiveSeat(1);
    startSetupSow();
    refreshSetupMode();
  }}

  /* A setup sow always starts from the City, so there is nothing to ask the seat and nothing for
     `Sow` to do: its five acolytes come up into the hand the moment the wheel reaches it, and what
     it is waiting for is the first fork -- which, starting where it starts, is immediate.

     And the City is not ringed for it. The ring marks the space a seat chose to start from, and
     this seat chose nothing; ringing it would colour in an answer to a question it was never
     asked. The two green roads out are the whole of what a setup is waiting on. */
  function startSetupSow() {{
    beginSowFrom(cityPosition, {{ ring: false }});
  }}

  /* Which seat is sowing is not written down again here: the board already rings it, and says so
     on the stage as `data-active-player-seat`. */
  function refreshSetupMode() {{
    if (setupButton) {{
      setupButton.setAttribute('aria-pressed', state.setup.on ? 'true' : 'false');
    }}
    if (stage) {{
      stage.setAttribute(
        'data-setup-mode',
        state.setup.on ? 'active' : state.setup.finished ? 'complete' : 'inactive');
      stage.setAttribute('data-setup-completed-seats', state.setup.done.join(','));
    }}
    refreshTurnControls();
  }}

  /* Where a seat put its acolytes is where they stay. So confirming moves not one cube: the sow's
     ledgers -- what it would need in order to take them back -- are dropped rather than played
     back, and only the marks the sow made about itself are cleared. The City count the compact
     rows keep is set to what the seat actually left there, which is a number in the record and not
     a redraw of the board; the board is already showing it, because the sow put it there.

     That holds for the last seat as much as for the others. All that is different about the last
     is what happens next: there is no seat to hand the wheel to, so the table goes back to the
     first to begin and setup lets go of the board exactly as it stands. */
  function confirmSetupSow() {{
    if (!state.setup.on || state.turn.phase !== 'sow_complete') {{
      return;
    }}
    var seat = state.activeSeat;
    state.setup.done.push(seat);
    state.city[String(seat)] = visibleActivePlayerCubesForPosition(cityPosition).length;
    state.turn.pickedUp = [];
    state.turn.sown = [];
    clearTurnMarks();
    var waiting = seatsAtTable().filter(function (other) {{
      return state.setup.done.indexOf(other) === -1;
    }});
    if (waiting.length) {{
      setActiveSeat(waiting[0]);
      startSetupSow();
    }} else {{
      state.setup.on = false;
      state.setup.finished = true;
      setActiveSeat(1);
    }}
    refreshSetupMode();
  }}

  /* `Reset` in setup hands the seat its five acolytes back and sets it going again from the City,
     which is the only place a setup sow starts. The seats that have already confirmed keep what
     they placed: there is nothing of theirs left to undo.

     It is also the way out of anything that has put the flow down mid-setup -- a compact row that
     redraws a City column, say -- which is why `Reset` stays lit all through a setup even when
     there is no sow standing to be put down. */
  function restartSetupSow() {{
    resetTurnFlow();
    standColumn(cityPosition, activePlayerId(), SETUP_CUBES);
    state.city[String(state.activeSeat)] = SETUP_CUBES;
    startSetupSow();
  }}

  /* A count change redraws the tallies a turn may have cubes lifted out of, so the turn is put
     back first rather than being left holding cubes the board has since redrawn. A setup deals
     again afterwards for the same reason: the tally now on the table is a different one, drawn as
     the wheel opens rather than as a setup left it, and the seats it holds are a different list. */
  function applyPlayerCount(count) {{
    resetTurnFlow();
    state.count = count;
    renderSeatBoards();
    renderDiscTrack('alms');
    renderDiscTrack('piety');
    renderDutyTallies();
    Array.prototype.forEach.call(countButtons, function (button) {{
      var active = Number(button.getAttribute('data-player-count-button')) === count;
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});
    /* A seat that has just left the table cannot be the one whose turn it is. */
    setActiveSeat(state.activeSeat > count ? {DEFAULT_CONTROL_PLAYER_SEAT} : state.activeSeat);
    /* Nor can it be holding the marker. It goes back to the seat it starts the game with, never
       to nobody: there is no state in which the marker is off the table. */
    setFirstPlayerSeat(
      state.firstPlayerSeat > count ? {FIRST_PLAYER_SEAT_AT_START} : state.firstPlayerSeat
    );
    if (state.setup.on) {{
      enterSetupMode();
    }} else {{
      /* The tally now on the table is one no setup has dealt, whatever was done to the last. */
      state.setup.finished = false;
      refreshSetupMode();
    }}
  }}

  Array.prototype.forEach.call(countButtons, function (button) {{
    button.addEventListener('click', function () {{
      applyPlayerCount(Number(button.getAttribute('data-player-count-button')));
    }});
  }});

  Array.prototype.forEach.call(rollButtons, function (button) {{
    button.addEventListener('click', function () {{
      applySetupRoll(Number(button.getAttribute('data-setup-roll-button')));
    }});
  }});

  if (shipButton) {{
    shipButton.addEventListener('click', advanceShip);
  }}

  if (dutyRandomize) {{
    dutyRandomize.addEventListener('click', randomizeDuties);
  }}

  if (setupButton) {{
    setupButton.addEventListener('click', enterSetupMode);
  }}

  if (merchantAdvance) {{
    merchantAdvance.addEventListener('click', advanceMerchant);
  }}

  Array.prototype.forEach.call(resourceButtons, function (button) {{
    button.addEventListener('click', function () {{
      var step = button.getAttribute('data-resource-button').split(':');
      stepResource(step[0], step[1] === '-' ? -1 : 1);
    }});
  }});

  buyButton.addEventListener('click', buyBuilding);
  donateButton.addEventListener('click', donateBuilding);

  [rowThreeSeat, buildingSelect, donateSlot].forEach(function (select) {{
    select.addEventListener('change', refreshBuildingButtons);
  }});

  Array.prototype.forEach.call(winnerButtons, function (button) {{
    button.addEventListener('click', function () {{
      if (button.getAttribute('data-alms-winner-button') === 'add') {{
        addWinner();
      }} else {{
        resetWinners();
      }}
    }});
  }});

  Array.prototype.forEach.call(discButtons, function (button) {{
    button.addEventListener('click', function () {{
      var track = button.getAttribute('data-disc-track');
      var delta = Number(button.getAttribute('data-disc-delta'));
      moveDisc(track, delta);
    }});
  }});

  moveAcolyte.addEventListener('click', function () {{
    if (!canMoveAcolyte()) {{
      return;
    }}
    var seat = String(acolytePlayerSeat.value);
    var playerState = state.acolytes[seat];
    var source = acolyteSource.value;
    var target = acolyteTarget.value;
    setAcolytesAt(playerState, source, acolytesAt(playerState, source) - 1);
    setAcolytesAt(playerState, target, acolytesAt(playerState, target) + 1);
    renderBoardCubes(seat);
    refreshBoardButtons();
  }});

  serfToAbbey.addEventListener('click', function () {{
    if (!canMoveSerf()) {{
      return;
    }}
    var seat = String(acolytePlayerSeat.value);
    var playerState = state.acolytes[seat];
    playerState.villageSerfs -= 1;
    playerState.abbeyAcolytes += 1;
    renderBoardCubes(seat);
    refreshBoardButtons();
  }});

  abbeyToCity.addEventListener('click', function () {{
    sendToCity(String(acolytePlayerSeat.value), 'abbeyAcolytes');
  }});

  villageToCity.addEventListener('click', function () {{
    sendToCity(String(acolytePlayerSeat.value), 'villageSerfs');
  }});

  [acolytePlayerSeat, acolyteSource, acolyteTarget].forEach(function (control) {{
    control.addEventListener('change', refreshBoardButtons);
  }});

  if (firstPlayerSeat) {{
    firstPlayerSeat.addEventListener('change', function () {{
      setFirstPlayerSeat(Number(firstPlayerSeat.value));
    }});
  }}

{turn_flow}
  Object.keys(state.acolytes).forEach(function (seat) {{
    renderBoardCubes(seat);
    renderResources(seat);
    renderCity(seat);
  }});
  renderWinners();
  renderBuildings();
  renderDutySetup();
  renderMerchant();
  applySetupRoll(SETUP.defaultRoll);
  applyPlayerCount(DEFAULT_COUNT);
  refreshBoardButtons();
}})();
</script>"""


# ---------------------------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------------------------


def render_game_table_html(
    map_layout: dict,
    piety_layout: dict,
    piety_config: dict,
    catalog: dict,
    site_data: dict | list,
    board_layout: dict,
    duty_wheel_layout: dict,
    alms_layout: dict,
    alms_config: dict,
) -> str:
    content, hexes, cubes = board_measurements(
        alms_layout, piety_layout, board_layout, duty_wheel_layout, map_layout
    )
    scale = solve_table_scale(content, hexes, cubes)
    hexagon = duty_hexagon(duty_wheel_layout)

    # The `1st` pocket is painted solid, so a disc that can be moved into it has to be drawn
    # after it. That is what the renderer's interactive form is for: it lifts the discs out of
    # their step groups into one layer above the pocket. Nothing about the board's drawing
    # changes -- the four discs still start on step 0.
    alms_svg = tag_player_discs(
        crop_svg(
            render_alms_table_svg(alms_layout, alms_config, interactive=True),
            scale.crop["alms"],
        )
    )
    piety_svg = tag_player_discs(
        crop_svg(
            render_piety_track_v2_svg(
                piety_layout,
                piety_config,
                PIETY_VARIANT_ID,
                FIRST_PLAYER_SEAT_AT_START,
                interactive=True,
            ),
            scale.crop["piety"],
        )
    )
    placements = setup_placements(DEFAULT_START_ROLL, catalog, site_data)
    map_svg = crop_svg(render_setup_map_svg(map_layout, placements), scale.crop["map"])
    # Every side of every building a board slot can show, defined once and pointed at, so buying
    # or donating is a change of reference rather than SVG built in the browser.
    content_defs = render_building_content_defs(placements, load_donated_building_tiles())
    # The wheel's own controls stay off -- they would add height, and this page drives it from the
    # compact rows instead. Its interactive form is what they drive: every tally, Tithe token and
    # Merchant slot drawn hidden, so a click flips opacity rather than redrawing the board.
    duty_seated = duty_wheel_seating(duty_wheel_layout)
    duty_svg = crop_svg(
        regularise_duty_hexagon(
            render_duty_wheel_svg(duty_seated, interactive=True, turn_controls=True), hexagon
        ),
        scale.crop["action"],
    )
    panels = []
    active_color = ""
    for index, seat in enumerate(SEATED_PLAYERS, start=1):
        player = player_by_id(board_layout, seat)
        active = index == DEFAULT_CONTROL_PLAYER_SEAT
        if active:
            active_color = player["color"]
        board = tag_resource_readouts(
            render_player_board_v2_svg(board_layout, player, interactive=True), board_layout
        )
        panels.append(
            f'<div class="panel p-player" data-component="player-board-v2"'
            f' data-player-seat="{index}"'
            f' data-player="{player["id"]}" data-player-color="{player["color"]}"'
            f' data-active-seat="{str(active).lower()}">'
            f"{crop_svg(board, scale.crop['player'])}</div>"
        )
    seats = "\n      ".join(panels)
    # Whose turn it is, said once where anything on the page can read it.
    active_seat_hooks = (
        f'data-active-player-seat="{DEFAULT_CONTROL_PLAYER_SEAT}"'
        f' data-active-player-color="{active_color}"'
    )
    controls = render_compact_controls(board_layout, placements)
    control_script = render_compact_controls_script(
        map_layout, piety_layout, board_layout, alms_layout, alms_config, placements, duty_seated
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{PAGE_TITLE}</title>
<style>
  /* ==================================================================
     ONE KNOB: --cube is the rendered size of a wooden cube, in px.
     Every board's width is that times a constant derived from how big a
     cube is in that board's own units, so all the pieces match and the
     whole table rescales together. Nothing else sets a panel width.
     ================================================================== */
  :root {{
    --gap: {GAP_PX}px;
    --avail: min(2400px, 100vw - {BODY_CHROME}px);

    /* Each of the two rows competes for the width on its own, and the two of
       them stack for the height; the cube is the smallest solution, so the
       table fits the window. The piety-over-duty column is not part of it: the
       wheel is sized afterwards to fill exactly what the row leaves it, so it
       cannot need more room than the row already provides. */
    --cube: min(
      calc((var(--avail) - {scale.width_fixed:.2f}px) / {scale.width_cubes:.3f}),
      calc((var(--avail) - {scale.seats_fixed:.2f}px) / {scale.seats_cubes:.3f}),
      calc((100vh - {scale.stack_fixed:.0f}px) / {scale.stack_cubes:.3f})
    );

    /* How tall the main row comes out: whichever of the map or the alms table
       stands taller. Neither depends on the duty wheel, so this can be read
       before the wheel is sized. */
    --row-height: calc(var(--cube) * {scale.row_cubes:.3f} + {PANEL_CHROME}px);
    /* The duty wheel is then handed whatever height that leaves once the piety
       track, both panels' chrome and one gap are taken out -- so the space
       between the two is var(--gap) exactly, at any window size, and the
       wheel's bottom lands on the map's. Its width follows from its own aspect
       ratio, which is why nothing sets one. */
    --h-action: calc(
      var(--row-height) - var(--cube) * {scale.piety_cubes:.5f}
      - {2 * PANEL_CHROME}px - var(--gap));
    --w-map:    calc(var(--cube) * {scale.mult["map"]:.3f} * {scale.map_scale:.5f});
    /* Its own size, frozen before the duty wheel started growing. */
    --w-piety:  calc(var(--cube) * {scale.piety_coef:.5f});
    /* Sized so a seat's cube comes out the size the wheel's does: the
       coefficient is how many cubes wide a seat is, times the wheel's own
       shortfall against --cube. */
    --w-player: calc(var(--cube) * {scale.player_k:.3f});
  /* Locked to the piety track's scale rather than the seats' width, which is
     what makes the coloured discs the same size on both boards. The alms table
     is then drawn wide enough in its own units that at that scale it still
     comes out the width of a seat -- see UNITS_PER_PLAYER_UNIT there. */
    --w-alms:   calc(var(--w-piety) * {scale.alms_over_piety:.5f});
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: {PAGE_BACKGROUND};
    display: flex; flex-direction: column; align-items: center;
    padding: {BODY_PADDING}px;
  }}

  /* Left-aligned rather than centred so the seat row starts on the same
     vertical as the main row does -- which is what puts the red board under
     the alms table, the two of them being the leftmost panel of each row. */
  .game-table-stage {{
    display: flex; flex-direction: column; gap: var(--gap); align-items: flex-start;
  }}
  /* The row stands to whichever of its three needs the most height, and they
     stretch to it unless they say otherwise. Only the piety-over-duty column
     wants to: the other two are single panels or short stacks, and a panel
     taller than its own drawing is a border round empty canvas. */
  .row  {{ display: flex; gap: var(--gap); align-items: stretch; }}
  /* Alms Table over the compact controls. The controls sit in the slack under
     the alms table rather than stretching the left column past the map, so the scale
     solver never has to know about it. */
  .left {{
    display: flex; flex-direction: column; align-items: center;
    align-self: stretch; justify-content: flex-start; gap: 8px;
  }}
  /* .col pins the piety track to the TOP of that space and the duty wheel to
     the BOTTOM. The wheel is sized so the pair comes to exactly one gap short
     of the row, so space-between produces precisely that gap rather than a
     leftover of whatever height happens to remain. */
  .col {{
    display: flex; flex-direction: column; align-items: center;
    align-self: stretch; justify-content: space-between; gap: var(--gap);
  }}
  /* One row of four fixed slots, under the main row. Hiding a seat leaves its
     width in place so the others do not slide. */
  .seats {{ display: flex; gap: var(--gap); }}

  .panel {{
    width: fit-content;
    background: {PAGE_BACKGROUND}; border: {PANEL_BORDER}px solid #333333; border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,.5);
    padding: {PANEL_PADDING}px;
  }}
  .panel > svg {{ display: block; height: auto; }}
  /* The map is shorter than the row, so .row's stretch would pad its panel out
     with blank space under the hexagon and break the crop's even margin.
     Sizing to its own content keeps the margin even; flex-end then drops the
     shorter panel until its bottom edge sits on the row's bottom -- the same
     line the duty wheel's bottom sits on. Its width is untouched. */
  .p-map {{ align-self: flex-end; }}
  /* The only panel sized by height rather than width; see --h-action. */
  .p-action > svg {{ height: var(--h-action); width: auto; }}
  .p-map    > svg {{ width: var(--w-map); }}
  .p-player > svg {{ width: var(--w-player); }}
  .p-piety  > svg {{ width: var(--w-piety); }}
  .p-alms   > svg {{ width: var(--w-alms); }}

  .table-controls {{
    display: flex; flex-direction: column; align-items: center; gap: 4px;
  }}
  .control-row {{
    display: flex; align-items: center; justify-content: center; gap: 4px;
    flex-wrap: wrap;
  }}
  .control-row button,
  .control-row select {{
    background: #1C1C1C; border: 1px solid #4A4A4A; border-radius: 6px;
    color: #F2EEDF; font: inherit; font-size: 13px;
  }}
  .control-row button {{
    cursor: pointer; min-width: 2.55em; padding: 6px 10px;
  }}
  .control-row select {{
    min-width: 54px; padding: 5px 6px;
  }}
  .control-row button:hover {{ background: #2A2A2A; }}
  .control-row button[aria-pressed="true"] {{
    background: #F2EEDF; border-color: #F2EEDF; color: #1C1C1C;
  }}

  /* The turn flow, drawn on the wheel. The renderer draws the plaques, the spaces and the
     arrows; these say what a phase changes about them. Everything a phase touches is an
     attribute, so a click sets a word rather than restyling anything. */
  .game-table-stage {{ --active-player: {ACTIVE_PLAYER_FALLBACK}; }}
  /* Whose turn it is, said once in the seat's own colour and read here and on the wheel. The board
     says it itself, with the wash of its own colour the renderer drew up off its bottom edge and
     left hidden: a board is a thing on a table, and a ring drawn round the outside of one is a
     browser's idea of a selected thing rather than a table's. Only the showing of it is here, so
     nothing about the board moves or is restyled -- the rule turns a layer up from nothing. */
  .p-player[data-active-seat="true"] [data-active-player-glow="true"] {{ opacity: 1; }}
  [data-turn-control][data-turn-control-enabled="true"] {{ opacity: 1; cursor: pointer; }}
  [data-turn-control][data-turn-control-enabled="false"] {{ opacity: {TURN_DIMMED_OPACITY}; }}
  [data-turn-control][data-turn-control-active="true"] rect {{ fill: #F2EEDF; }}
  [data-turn-control][data-turn-control-active="true"] text {{ fill: #1C1C1C; }}
  /* A space that can be started from is outlined rather than filled: the green under a duty
     tile means the board, not a selection. */
  [data-turn-start-candidate="true"] {{ cursor: pointer; }}
  [data-turn-start-candidate="true"] .board-circle {{ stroke: #F2EEDF; stroke-width: 4; }}
  [data-turn-start-selected="true"] .board-circle {{
    stroke: var(--active-player); stroke-width: 5.5;
  }}
  /* And a duty a finished sow left standing to be picked from, in the same cream and then the
     same colour: what marks the chosen one apart from the space the turn started at is its
     trefoil, coloured in above the title. */
  [data-turn-duty-candidate="true"] {{ cursor: pointer; }}
  [data-turn-duty-candidate="true"] .board-circle {{ stroke: #F2EEDF; stroke-width: 4; }}
  [data-turn-duty-selected="true"] .board-circle {{
    stroke: var(--active-player); stroke-width: 3.5;
  }}
  /* Filled, but still outlined as it was drawn: the three lobes overlap, and without the lines
     between them a coloured trefoil is a coloured blob. */
  [data-ornament-position][data-turn-duty-selected="true"] circle {{
    fill: var(--active-player); stroke-opacity: 0.7;
  }}
  [data-turn-branch-choice="true"] {{ cursor: pointer; }}
  [data-turn-branch-choice="true"] .arrow-interior {{ fill: {TURN_BRANCH_GREEN}; }}
  [data-turn-branch-choice="true"] .arrow-border {{ stroke: {TURN_BRANCH_EDGE}; }}

  /* Stacked, there is no row height to fill, so the wheel goes back to being
     sized by width like everything else. */
  @media (max-width: {STACK_BELOW}px) {{
    :root {{ --cube: calc((100vw - 60px) / {scale.mult["action"]:.3f}); }}
    .row, .seats {{ flex-wrap: wrap; }}
    .left, .col {{ align-self: flex-start; gap: var(--gap); }}
    .p-action > svg {{ height: auto; width: calc(var(--cube) * {scale.mult["action"]:.3f}); }}
    .p-map {{ align-self: flex-start; }}
  }}
</style>
</head>
<body>
  <div class="game-table-stage" {active_seat_hooks}>
    <div class="row">
      <div class="left">
        <div class="panel p-alms">{alms_svg}</div>
        {controls}
      </div>
      <div class="col">
        <div class="panel p-piety">{piety_svg}</div>
        <div class="panel p-action">{duty_svg}</div>
      </div>
      <div class="panel p-map">{map_svg}</div>
    </div>
    <div class="seats">
      {seats}
    </div>
  </div>
  {content_defs}
  {control_script}
</body>
</html>
"""


def generate_game_table_page(
    *,
    map_layout_path: Path | None = None,
    piety_layout_path: Path | None = None,
    piety_config_path: Path | None = None,
    catalog_path: Path | None = None,
    site_data_path: Path | None = None,
    board_layout_path: Path | None = None,
    duty_wheel_layout_path: Path | None = None,
    alms_layout_path: Path | None = None,
    alms_config_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    html = render_game_table_html(
        load_map_layout(map_layout_path),
        load_piety_track_v2_layout(piety_layout_path),
        load_piety_config(piety_config_path),
        load_building_catalog(catalog_path),
        load_pilgrimage_sites(site_data_path),
        load_player_boards_v2_layout(board_layout_path),
        load_duty_wheel_layout(duty_wheel_layout_path),
        load_alms_table_layout(alms_layout_path),
        load_alms_config(alms_config_path),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination


def main() -> None:
    written = generate_game_table_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
