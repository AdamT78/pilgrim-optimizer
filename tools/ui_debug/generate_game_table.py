"""Write the generated game table layout page.

This page is composition only: it arranges renderers that already exist into the three-column
2-player table the physical game reads as. The renderers keep owning what each component looks
like; nothing here draws geometry of its own.

    column 1        column 2        column 3

    alms table      piety track     map
    player board    duty wheel
    player board

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

CROPPED, NOT REDRAWN
Those same standalone pages put a heading, a subtitle and a backdrop inside the viewBox -- nearly
half of the duty wheel's box is page furniture -- which would otherwise be paid for in the middle
of a table. Each fragment's viewBox is therefore pointed at its own panel instead. Nothing is
deleted: the extra elements are simply outside the view, and no renderer changes.

Nothing here reads or writes `GameState`, picks legal actions, or applies any rule. There are no
controls on this page at all; `game_setup.html` remains the control-heavy debug sandbox.

Run from the repo root:

    python3 tools/ui_debug/generate_game_table.py
"""

from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.generate_game_setup import (  # noqa: E402
    DEFAULT_START_ROLL,
    render_setup_map_svg,
    setup_placements,
)
from tools.ui_debug.render_alms_table import (  # noqa: E402
    CUBE_SIZE as ALMS_CUBE_UNITS,
)
from tools.ui_debug.render_alms_table import (
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_svg,
)
from tools.ui_debug.render_buildings import load_building_catalog  # noqa: E402
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
    render_piety_track_v2_svg,
    track_geometry,
    variant_by_id,
)
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites  # noqa: E402
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    TOKEN_RADIUS as PLAYER_TOKEN_RADIUS,  # noqa: E402
)
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    PANEL_STROKE_WIDTH as PLAYER_PANEL_STROKE,  # noqa: E402
)
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    board_geometry,
    load_player_boards_v2_layout,
    player_by_id,
    render_player_board_v2_svg,
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

# The two seats this table shows. They are the second column of the four-seat grid the layout
# describes, which is what the 2-player reference layout kept; the first column (white, yellow) is
# simply not drawn. This is debug/layout state to look at, not a seating rule: player counts are
# not wired up here, and no board says who starts.
SEATED_PLAYERS = ("player_two", "player_four")

# --- page chrome, in px ----------------------------------------------------------------------
# The gap between panels, and between the two player boards.
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

# Every board's size is solved against the original four-seat block -- two rows of two -- so that
# showing two of them changes what is drawn and nothing about how big anything is. Only the
# rendered grid is told there is one column now.
SEAT_ROWS = 2
SEAT_COLS = 2
RENDER_SEAT_COLS = 1

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
    left_cubes: float
    left_panels: float
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

        # Each panel's outer height, in cubes.
        map_cubes = mult["map"] * aspect["map"]
        duty_cubes = mult["action"] * duty_scale * aspect["action"]
        piety_cubes = mult["action"] * duty_scale * piety_share * aspect["piety"]
        alms_cubes = piety_cubes * alms_over_piety * aspect["alms"] / aspect["piety"]

        # `--avail` has already taken the body padding out of the width, so only the panels' own
        # chrome and the gaps between them are counted here. The height budgets below work off a
        # raw 100vh, so they have to subtract the page's own chrome themselves.
        width_cubes = mult["action"] * duty_scale + mult["map"] + SEAT_COLS * player_k
        width_fixed = (2 + SEAT_COLS) * PANEL_CHROME + (1 + SEAT_COLS) * GAP_PX
        # The alms table over the seats: three panels and two gaps, standing to whatever height
        # they come to. They used to be stretched to the duty wheel's height instead, which is
        # what made this column the tall one by construction; now either it or the map can be.
        left_cubes = alms_cubes + SEAT_ROWS * player_k * player_aspect
        left_panels = (1 + SEAT_ROWS) * PANEL_CHROME + SEAT_ROWS * GAP_PX

        cube = min(
            (REF_AVAIL_WIDTH - width_fixed) / width_cubes,
            (REF_VIEWPORT_HEIGHT - BODY_CHROME - left_panels) / left_cubes,
            (REF_VIEWPORT_HEIGHT - BODY_CHROME - PANEL_CHROME) / map_cubes,
        )

        # A seat is sized so its cube comes out the size the duty wheel's does, which is what makes
        # a player's piece one piece across the table. It cannot be sized from `cube` to manage it:
        # the wheel is the one panel not drawn at that size, being handed whatever height the row
        # has left over instead, so matching it means reading that height back.
        #
        # Which makes the two mutually dependent -- the seats stand in one of the columns the row's
        # height is the greater of -- so they are left to settle together in the fixed point rather
        # than one being solved before the other.
        row_height = max(cube * map_cubes + PANEL_CHROME, cube * left_cubes + left_panels)
        duty_height = row_height - cube * piety_cubes - 2 * PANEL_CHROME - GAP_PX
        duty_cube_px = cubes["action"] * duty_height / crop["action"][3]
        player_k = mult["player"] * duty_cube_px / cube

        # What a player board's margin comes to on screen, and the same in every other board's
        # units, which is what the next pass crops to.
        margin_px = PLAYER_MARGIN * cube * player_k / player_crop[2]
        per_unit = {
            "action": cube * mult["action"] * duty_scale / crop["action"][2],
            "map": cube * mult["map"] / crop["map"][2],
            "piety": cube * mult["action"] * duty_scale * piety_share / crop["piety"][2],
        }
        margins = {key: margin_px / value for key, value in per_unit.items()}

    # The piety track keeps the size it has here. The duty wheel does not: it grows into whatever
    # height the row has left over, which the stylesheet works out for itself from these
    # coefficients rather than from a scale frozen at one window size.
    piety_coef = mult["action"] * duty_scale * piety_share

    return TableScale(
        cube=cube,
        crop=crop,
        mult=mult,
        width_cubes=width_cubes,
        width_fixed=width_fixed,
        left_cubes=left_cubes,
        left_panels=left_panels,
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

    alms_svg = crop_svg(render_alms_table_svg(alms_layout, alms_config), scale.crop["alms"])
    piety_svg = crop_svg(
        render_piety_track_v2_svg(piety_layout, piety_config, PIETY_VARIANT_ID),
        scale.crop["piety"],
    )
    map_svg = crop_svg(
        render_setup_map_svg(map_layout, setup_placements(DEFAULT_START_ROLL, catalog, site_data)),
        scale.crop["map"],
    )
    # No controls: this page is about where things sit, and the buttons would only add height.
    duty_svg = crop_svg(
        regularise_duty_hexagon(render_duty_wheel_svg(duty_wheel_layout), hexagon),
        scale.crop["action"],
    )
    panels = []
    for seat in SEATED_PLAYERS:
        player = player_by_id(board_layout, seat)
        board = render_player_board_v2_svg(board_layout, player)
        panels.append(
            f'<div class="panel p-player" data-component="player-board-v2"'
            f' data-player="{player["id"]}" data-player-color="{player["color"]}">'
            f"{crop_svg(board, scale.crop['player'])}</div>"
        )
    seats = "\n        ".join(panels)

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

    /* The row competes for the width, and the two columns that stand to their
       own height for the height; the cube is the smallest solution, so the
       table fits the window. The piety-over-duty column is not part of it: the
       wheel is sized afterwards to fill exactly what the row leaves it, so it
       cannot need more room than the row already provides. */
    --cube: min(
      calc((var(--avail) - {scale.width_fixed:.2f}px) / {scale.width_cubes:.3f}),
      calc((100vh - {BODY_CHROME + scale.left_panels:.0f}px) / {scale.left_cubes:.3f}),
      calc((100vh - {BODY_CHROME + PANEL_CHROME}px) / {scale.map_cubes:.3f})
    );

    /* How tall the row comes out: whichever of the map or the alms-over-seats
       column needs more of it. Neither depends on the duty wheel, so this can
       be read before the wheel is sized. */
    --row-height: max(
      calc(var(--cube) * {scale.map_cubes:.3f} + {PANEL_CHROME}px),
      calc(var(--cube) * {scale.left_cubes:.3f} + {scale.left_panels:.0f}px)
    );
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

  .game-table-stage {{
    display: flex; flex-direction: column; gap: var(--gap); align-items: center;
  }}
  /* All three columns stretch to the row's height, whichever of them is tallest. */
  .row  {{ display: flex; gap: var(--gap); align-items: stretch; }}
  /* .col pins the piety track to the TOP of that space and the duty wheel to
     the BOTTOM. The wheel is sized so the pair comes to exactly one gap short
     of the row, so space-between produces precisely that gap rather than a
     leftover of whatever height happens to remain. */
  .col, .left {{
    display: flex; flex-direction: column; align-items: center;
    align-self: stretch; justify-content: space-between; gap: var(--gap);
  }}
  /* The left column no longer fills the row -- the seats are sized from the
     cube rather than stretched to the wheel's height, and come to less -- so
     its panels stay together at the top and the slack falls under them. */
  .left {{ justify-content: flex-start; }}
  .seats {{
    display: grid;
    grid-template-columns: repeat({RENDER_SEAT_COLS}, max-content);
    gap: var(--gap);
  }}

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

  /* Stacked, there is no row height to fill, so the wheel goes back to being
     sized by width like everything else. */
  @media (max-width: {STACK_BELOW}px) {{
    :root {{ --cube: calc((100vw - 60px) / {scale.mult["action"]:.3f}); }}
    .row {{ flex-wrap: wrap; }}
    .col, .left {{ align-self: flex-start; gap: var(--gap); }}
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
        <div class="seats">
        {seats}
        </div>
      </div>
      <div class="col">
        <div class="panel p-piety">{piety_svg}</div>
        <div class="panel p-action">{duty_svg}</div>
      </div>
      <div class="panel p-map">{map_svg}</div>
    </div>
  </div>
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
