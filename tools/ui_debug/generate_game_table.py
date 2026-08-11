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
under the alms table. Under that table sits one compact three-row control stack: player count with
setup roll buttons, Alms/Piety disc movement, and acolyte movement. These controls are local page
state only: no GameState, no rules, and no scaling solve changes.

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
    load_duty_wheel_layout,
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

# The setup rolls and players the compact controls offer.
SETUP_ROLLS = tuple(sorted(START_HEX_BY_ROLL))
DEFAULT_CONTROL_PLAYER_SEAT = 1

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
        '<button type="button" data-ship-advance="true">S+</button>'
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


def render_compact_controls_script(
    map_layout: dict,
    piety_layout: dict,
    board_layout: dict,
    alms_layout: dict,
    alms_config: dict,
    placements: list[dict],
) -> str:
    """Compact local controls: player count, setup roll, discs, resources, winners, buildings,
    acolytes.

    Duty Wheel player-count behaviour is intentionally deferred.
    """
    buildings = json.dumps(building_control_data(board_layout, placements), separators=(",", ":"))
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
    buildings: JSON.parse(JSON.stringify(BUILDINGS.state))
  }};

  var countButtons = document.querySelectorAll('[data-player-count-button]');
  var rollButtons = document.querySelectorAll('[data-setup-roll-button]');
  var seatBoards = document.querySelectorAll('[data-player-seat].p-player');
  var discButtons = document.querySelectorAll('[data-disc-track][data-disc-delta]');
  var discPlayerSeat = document.getElementById('disc-player-seat');
  var acolytePlayerSeat = document.getElementById('acolyte-player-seat');
  var acolyteSource = document.getElementById('acolyte-source');
  var acolyteTarget = document.getElementById('acolyte-target');
  var moveAcolyte = document.getElementById('move-acolyte');
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
  var almsPanel = document.querySelector('.p-alms');
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

  function renderAcolyteBoard(seat) {{
    var board = boardForSeat(seat);
    var playerState = state.acolytes[String(seat)];
    if (!board || !playerState) {{
      return;
    }}
    var abbeySlots = board.querySelectorAll('[data-token="abbey"]');
    Array.prototype.forEach.call(abbeySlots, function (slot) {{
      show(slot, Number(slot.getAttribute('data-token-index')) < playerState.abbeyAcolytes);
    }});

    ACOLYTES.roles.forEach(function (role) {{
      var count = Number(playerState.roles[role] || 0);
      var roleSlots = board.querySelectorAll('[data-role="' + role + '"]');
      Array.prototype.forEach.call(roleSlots, function (slot) {{
        show(slot, count === (slot.getAttribute('data-role-slot') === 'single' ? 1 : 2));
      }});
    }});
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
    renderAcolyteBoard(seat);
    renderWinners();
    refreshMoveAcolyteButton();
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
      renderAcolyteBoard(seat);
    }});
    renderWinners();
    refreshMoveAcolyteButton();
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

  function refreshMoveAcolyteButton() {{
    moveAcolyte.disabled = !canMoveAcolyte();
  }}

  function applyPlayerCount(count) {{
    state.count = count;
    renderSeatBoards();
    renderDiscTrack('alms');
    renderDiscTrack('piety');
    Array.prototype.forEach.call(countButtons, function (button) {{
      var active = Number(button.getAttribute('data-player-count-button')) === count;
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});
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
    renderAcolyteBoard(seat);
    refreshMoveAcolyteButton();
  }});

  [acolytePlayerSeat, acolyteSource, acolyteTarget].forEach(function (control) {{
    control.addEventListener('change', refreshMoveAcolyteButton);
  }});

  Object.keys(state.acolytes).forEach(function (seat) {{
    renderAcolyteBoard(seat);
    renderResources(seat);
  }});
  renderWinners();
  renderBuildings();
  applySetupRoll(SETUP.defaultRoll);
  applyPlayerCount(DEFAULT_COUNT);
  refreshMoveAcolyteButton();
  /* Duty Wheel player-count behaviour is deferred to a later PR. */
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
            render_piety_track_v2_svg(piety_layout, piety_config, PIETY_VARIANT_ID),
            scale.crop["piety"],
        )
    )
    placements = setup_placements(DEFAULT_START_ROLL, catalog, site_data)
    map_svg = crop_svg(render_setup_map_svg(map_layout, placements), scale.crop["map"])
    # Every side of every building a board slot can show, defined once and pointed at, so buying
    # or donating is a change of reference rather than SVG built in the browser.
    content_defs = render_building_content_defs(placements, load_donated_building_tiles())
    # The wheel's own controls stay off: they would add height, and the player count does not
    # reach the wheel yet in any case. TODO: duty wheel player-count behaviour, a later pass.
    duty_svg = crop_svg(
        regularise_duty_hexagon(render_duty_wheel_svg(duty_wheel_layout), hexagon),
        scale.crop["action"],
    )
    panels = []
    for index, seat in enumerate(SEATED_PLAYERS, start=1):
        player = player_by_id(board_layout, seat)
        board = tag_resource_readouts(
            render_player_board_v2_svg(board_layout, player, interactive=True), board_layout
        )
        panels.append(
            f'<div class="panel p-player" data-component="player-board-v2"'
            f' data-player-seat="{index}"'
            f' data-player="{player["id"]}" data-player-color="{player["color"]}">'
            f"{crop_svg(board, scale.crop['player'])}</div>"
        )
    seats = "\n      ".join(panels)
    controls = render_compact_controls(board_layout, placements)
    control_script = render_compact_controls_script(
        map_layout, piety_layout, board_layout, alms_layout, alms_config, placements
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
  <div class="game-table-stage">
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
