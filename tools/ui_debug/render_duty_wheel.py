"""Structured renderer for the duty wheel debug view.

The duty wheel holds the duty tiles away from the map so the map stays readable: eight duty
spaces ringed around a central City on a green hexagon, joined by clockwise ring arrows and four
arrows running to and from the middle. Each space shows the cubes standing on it as one column per
seat on a shared baseline, and most of the duties carry a capsule with a Tithe token icon.

A duty tile's tally is the seats in play followed by a neutral column for the dummy acolytes a
reduced table plays against; a full table has no neutrals, so it is seats alone. The City takes
seats only either way, since dummy acolytes are seeded and moved on the duty ring and the City is
not on it.

Two pieces of the picture are named here so a later renderer does not have to guess:

- the purple disc is the **Merchant token**, drawn on whichever duty `merchant_token.starts_on`
  names (Taxation, for the debug page);
- the resource icons in the capsules are **Tithe tokens**.

Two more things are named because movement depends on telling them apart. A **board position** is
where a space stands — `city`, `north`, `north_east` and the rest, as `configs/board.json` names
and orders them — and a **duty category** is the tile lying on it. Turning the tiles moves the
categories around and moves no position at all, so the arrows and anything that walks them are
keyed to positions: every space carries `data-board-position`, and every arrow the pair of
positions it joins. This board's own ids — `clerical`, `construct` and the rest — are the
prototype's default arrangement of the tiles, kept as stable names for the spaces and no use at all
for saying where a cube may go.

Asked for `turn_controls`, the board also carries a shell of the turn flow to come: small plaques
standing in the four black corners the green hexagon leaves — Sow, what is in hand, Reset and
Confirm, Action and Tithe. They are a picture and nothing else. Nothing is clickable, nothing is
counted, and only Sow is drawn as reachable; the rest are dimmed so the shape of a turn can be read
off the board before any of it is wired up.

Drawn plain, this is one fixed picture. Drawn `interactive`, the board also carries every slot the
page's debug buttons can turn on — a Merchant token on each duty, every Tithe token icon on each
duty that has a capsule, and a cube tally per player count — hidden until they are wanted, so a
click flips opacity instead of redrawing the board. Those buttons cycle sample setups, walk the
Merchant around the ring, and switch between the two-, three-, and four-player views; they touch
nothing else. There is no sowing, no sow animation, no Tithe token logic, and no rule saying what
any of this means. It is a debug/visual tool that reads `duty_wheel_layout.json` and emits
SVG/HTML, connected to nothing.

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

# The engine's board, read rather than copied. `configs/board.json` names the nine positions and
# the directed edges between them, and both are what movement on this wheel means: a space's
# position is where it stands, and the arrows drawn between spaces are those edges. The wheel's own
# ids -- `clerical`, `construct` and the rest -- are the prototype's default arrangement of the
# tiles and say nothing about movement, because a tile can be turned round the ring and a position
# cannot. Only the two data files are read here; no rules code is imported, and the Kogge and
# Cloisters modifiers that add or skip edges are not part of this graph.
BOARD_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "board.json"

# One space: a flat top with a round bottom, the arc centre acting as its anchor.
SPACE_RADIUS = 101.5
SPACE_STROKE_WIDTH = 2.438679
LABEL_OFFSET_Y = -50.7
LABEL_FONT_SIZE = 15.5

# Cube tally: one column per seat on a shared baseline, kept even at zero so the stack tops stay
# comparable across spaces. The columns are centred on the duty, so a shorter table narrows the
# tally around the middle of the space instead of leaving a gap on the right.
#
# The cube keeps the size it has always had. It is the reference the rest of the table is
# calibrated against -- `render_player_boards_v2` sizes a building slot by how many of these a map
# hex measures -- so what it is worth in another board's units is not this renderer's to restate.
CUBE_SIZE = 13.0
CUBE_CELL_HEIGHT = 18.0
CUBE_COLUMN_WIDTH = 22.0
TALLY_OFFSET_Y = 19.0

# How tall a column can stand. These are the room a column has rather than what is standing in it:
# an interactive board draws every slot and hides the empty ones, so a page can put a cube on a
# space by turning one on rather than by drawing into the wheel.
#
# A tile's three are what fits between its baseline and its title -- a fourth would be drawn across
# the words -- and the room under the title is all the room there is, since the Tithe capsule takes
# the space below the baseline. The engine caps nothing, so a seat can hold more acolytes on a
# position than a tile can show; a page that puts cubes on the board has to stop when a column is
# full rather than draw over the title. The City stacks a seat's whole holding rather than a tile's
# handful, so its columns are taller and stand lower in the space to make room for it.
TILE_STACK_HEIGHT = 3
CITY_STACK_HEIGHT = 6

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
# Held to a full table's width rather than to the tally below it, which now narrows and widens
# with the table size. A mark that never varies is the point of this one.
ORNAMENT_RULE_HALF_WIDTH = 4 * CUBE_COLUMN_WIDTH / 2

# Where the City's taller stack stands: centred in the room the space has under its title, which
# runs from that title's baseline down to the inset margin above the bottom of the arc.
CITY_TALLY_OFFSET_Y = (
    LABEL_OFFSET_Y + SPACE_RADIUS - ORNAMENT_INSET + CITY_STACK_HEIGHT * CUBE_CELL_HEIGHT
) / 2.0

RING_ARROW_COUNT = 8

# Turn controls: small plaques standing in the black corners the hexagon leaves, drawn in the
# board's own root units so they are part of the wheel rather than furniture around it -- the game
# table sizes the wheel by its SVG and crops it to the hexagon's box, and a plaque inside that box
# is carried along by both. The look is the game table's compact control bar, borrowed rather than
# reinvented so the two read as one set of controls: charcoal fill, thin grey edge, pale text.
TURN_CONTROL_FILL = "#1C1C1C"
TURN_CONTROL_STROKE = "#4A4A4A"
TURN_CONTROL_TEXT = "#F2EEDF"
TURN_CONTROL_ACTIVE_FILL = "#F2EEDF"
TURN_CONTROL_ACTIVE_TEXT = "#1C1C1C"
TURN_CONTROL_DISABLED_OPACITY = "0.4"

TURN_CONTROL_HEIGHT = 40.0
TURN_CONTROL_RADIUS = 8.0
TURN_CONTROL_STROKE_WIDTH = 1.6
TURN_CONTROL_FONT_SIZE = 20.0
TURN_CONTROL_PADDING_X = 14.0
TURN_CONTROL_GAP = 8.0
# The plaque is sized from the label rather than measured, so a button is as wide as its word at
# roughly the average width of a Helvetica glyph, and never narrower than a two-letter one.
TURN_CONTROL_CHAR_WIDTH = 11.0
TURN_CONTROL_MIN_WIDTH = 62.0

# Cubes in hand: a count of cubes picked up, which a sow can hold in more than one colour, so the
# cube on the plaque is a neutral stone rather than any seat's.
TURN_COUNTER_CUBE_SIZE = 16.0
TURN_COUNTER_CUBE_FILL = "#B9B2A2"
TURN_COUNTER_GAP = 8.0
TURN_COUNTER_IDLE_VALUE = 0
# `x` and a space and two figures, which is more cubes than any space on the board can hold.
TURN_COUNTER_WIDEST_LABEL = 4

# How far the movable duty tiles are turned around the ring in each sample setup. The first is
# the board as the layout describes it; the others are just far enough apart to look different.
DUTY_SETUP_ROTATIONS = (0, 1, 3)

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


def load_board_config(path: Path | None = None) -> dict:
    """The engine's `configs/board.json`: the nine position names and the edges between them."""
    board_path = BOARD_CONFIG_PATH if path is None else Path(path)
    return json.loads(board_path.read_text(encoding="utf-8"))


def board_positions(board: dict | None = None) -> list[str]:
    """The nine positions in the order the engine indexes them, City first."""
    return list((board or load_board_config())["positions"])


def board_edges(board: dict | None = None) -> dict[str, list[str]]:
    """Where a cube may step to from each position, as the engine's directed graph."""
    return {
        position: list(targets)
        for position, targets in (board or load_board_config())["edges"].items()
    }


def board_position_index(position: str, board: dict | None = None) -> int:
    """A position's engine index, which is what the rules pass around instead of the name."""
    positions = board_positions(board)
    try:
        return positions.index(position)
    except ValueError as exc:
        raise KeyError(f"unknown board position: {position!r}") from exc


def branching_positions(board: dict | None = None) -> list[str]:
    """The positions a cube can leave more than one way, in board order.

    Nothing lists them: they fall out of the graph, and on this board they are the City and the two
    ring positions the middle arrows run in from.
    """
    edges = board_edges(board)
    return [position for position in board_positions(board) if len(edges.get(position, ())) > 1]


def duties_of(layout: dict) -> list[dict]:
    return list(layout["duties"])


def board_position_of(duty: dict) -> str:
    """Which position on the engine's board one space of this wheel stands at.

    The layout carries the pairing so it can be read and checked rather than inferred from a name
    that means something else. A test holds it to the drawing: each space's position is the compass
    point it is actually drawn at, so the two cannot drift apart silently.
    """
    return str(duty["board_position"])


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


def players_for_count(layout: dict, count: int) -> list[dict]:
    """The colours that sit down at a two-, three-, or four-player table, in seat order.

    Which seats those are is the layout's to say rather than simply the first few: a two-player
    table takes red and blue, the pair that carries against parchment, and the others fill in
    around them.
    """
    if count not in layout["player_counts"]:
        raise ValueError(f"no {count}-player view: the layout offers {layout['player_counts']}")
    by_id = {player["id"]: player for player in layout["players"]}
    return [by_id[seat] for seat in layout["seats_by_player_count"][str(count)]]


def dummy_acolytes(layout: dict, count: int) -> dict | None:
    """The neutral column, on the table sizes that play with one.

    Reduced tables seed neutral dummy acolytes onto the duty ring to compete with the players; a
    full table has none, so its tally is seats only. They are pieces on the board, not a seat:
    they take no turn and hold nothing.
    """
    dummy = layout["dummy_acolytes"]
    return dummy if count in dummy["player_counts"] else None


def tally_pieces(layout: dict, duty: dict, count: int) -> list[dict]:
    """The columns standing on one space, left to right: the seats, then the neutrals.

    The City takes no neutral column. Dummy acolytes are seeded and moved around the duty ring
    only, and the City is not on that ring.
    """
    pieces = list(players_for_count(layout, count))
    dummy = dummy_acolytes(layout, count)
    if dummy is not None and duty["id"] != layout["city_id"]:
        pieces.append(dummy)
    return pieces


def tally_columns(layout: dict, duty: dict, count: int) -> list[dict]:
    """Where each column stands on one space, left to right.

    The group of visible columns is centred on the space, so dropping seats narrows the tally
    around the middle of it rather than leaving it hanging off to one side. `x` is the left edge
    of a cube, `center_x` the middle of the column it stands in.
    """
    cx, _ = duty["center"]
    pieces = tally_pieces(layout, duty, count)
    left = cx - len(pieces) * CUBE_COLUMN_WIDTH / 2
    return [
        {
            "player": piece["id"],
            "x": left + column * CUBE_COLUMN_WIDTH + (CUBE_COLUMN_WIDTH - CUBE_SIZE) / 2,
            "center_x": left + (column + 0.5) * CUBE_COLUMN_WIDTH,
        }
        for column, piece in enumerate(pieces)
    ]


def cubes_standing(layout: dict, duty: dict, piece: dict, counts: dict, count: int) -> int:
    """How many cubes one column shows.

    A seat on a duty tile shows what the debug state puts there, capped at what a tile has room
    for. Every City column opens on the same sample, which is well short of what the space holds so
    that a page with buttons has somewhere to put a cube. The neutral column reads its own seeding
    out of the layout, since neutrals are not part of the players' state.
    """
    if piece["id"] == layout["dummy_acolytes"]["id"]:
        seeded = layout["dummy_acolytes"]["sample_cubes"].get(str(count), {})
        return int(seeded.get(duty["id"], 0))
    if duty["id"] == layout["city_id"]:
        return int(layout["city_sample_cubes_per_seat"])
    return min(int(counts.get(piece["id"], 0)), TILE_STACK_HEIGHT)


def column_room(layout: dict, duty: dict, piece: dict, interactive: bool) -> int | None:
    """How many slots a column draws, or `None` when it only draws what is standing in it.

    A board that is going to be clicked draws every slot a seat could stand in and hides the empty
    ones, so a page can put a cube on a space by turning one on rather than by drawing into the
    wheel. The neutral column gets none of this: no seat plays those cubes, so nothing will ever
    arrive there. A board that is only being looked at draws the cubes and stops.
    """
    if not interactive or piece["id"] == layout["dummy_acolytes"]["id"]:
        return None
    return CITY_STACK_HEIGHT if duty["id"] == layout["city_id"] else TILE_STACK_HEIGHT


def merchant_path(layout: dict) -> list[str]:
    """The positions the Merchant can stand on: all eight duty tiles, clockwise.

    The City is not one of them — it is not a duty tile, and no ring arrow runs through it.
    """
    return list(layout["clockwise_order"])


def next_merchant_position(layout: dict, current: str) -> str:
    """The next duty tile clockwise, wrapping round the ring."""
    path = merchant_path(layout)
    return path[(path.index(current) + 1) % len(path)]


def duty_setups(layout: dict) -> list[list[dict]]:
    """Sample arrangements of the duty tiles, one entry per ring position, clockwise.

    Debug fodder, not a setup rule: the first is the board as the layout describes it, and the
    rest turn the movable tiles around the ring by a fixed number of places. A tile keeps its own
    Tithe token wherever it lands, which is why Taxation holds its position in all of them: it is
    the one duty with no Tithe token, so it is also the one position drawn without a capsule to
    put a token in. The City is not a duty tile at all and never takes part.
    """
    order = layout["clockwise_order"]
    movable = [duty["id"] for duty in ring_duties(layout) if duty["tithe_icon"]]

    setups = []
    for rotation in DUTY_SETUP_ROTATIONS:
        turned = movable[rotation:] + movable[:rotation]
        landed = dict(zip(movable, turned, strict=True))
        setups.append(
            [
                {
                    "position": position,
                    "duty": landed.get(position, position),
                    "label": duty_position_by_id(layout, landed.get(position, position))["label"],
                    "tithe_icon": duty_position_by_id(layout, landed.get(position, position))[
                        "tithe_icon"
                    ],
                }
                for position in order
            ]
        )
    return setups


def merchant_slot_center(duty: dict) -> tuple[float, float]:
    """Where the Merchant stands on a duty: the capsule's right cap, or the empty band on
    Taxation, which has no capsule to share."""
    cx, cy = duty["center"]
    _, merchant_x, cap_y = _capsule_caps(cx, cy)
    return (merchant_x if duty.get("tithe_icon") else cx), cap_y


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
        f'<text x="{cx:.1f}" y="{cy + LABEL_OFFSET_Y:.1f}" class="circle-label"'
        f' data-duty-label="{duty["id"]}">{escape(duty["label"])}</text>'
    )


def render_cube_tally(
    layout: dict,
    duty: dict,
    counts: dict,
    count: int | None = None,
    visible: bool = True,
    interactive: bool = False,
) -> str:
    """The cubes standing on one space, one column per piece, growing up from the baseline.

    `count` picks how many seats are in play; the columns and the baseline under them are drawn
    centred on the space either way, so the two- and three-player tallies sit in the middle of it
    rather than off to the left. On a duty tile the seats are followed by the neutral column when
    the table plays with one. The City's stacks are taller, so they stand lower in their space.

    An interactive board draws every slot a seat's column has room for and hides the ones nothing
    is standing on, in the same way the boards draw every slot a cube can stand in: a page can then
    put a cube on a space by turning one on rather than by drawing into the wheel.
    """
    _, cy = duty["center"]
    seats = count or layout["default_player_count"]
    pieces = tally_pieces(layout, duty, seats)
    columns = tally_columns(layout, duty, seats)
    is_city = duty["id"] == layout["city_id"]
    baseline = cy + (CITY_TALLY_OFFSET_Y if is_city else TALLY_OFFSET_Y)
    left = columns[0]["center_x"] - CUBE_COLUMN_WIDTH / 2
    right = columns[-1]["center_x"] + CUBE_COLUMN_WIDTH / 2
    ink = layout["palette"]["ink"]

    parts = [
        f'<line x1="{left:.1f}" y1="{baseline:.1f}" x2="{right:.1f}" y2="{baseline:.1f}"'
        f' stroke="{ink}" stroke-opacity="0.55" stroke-width="1.6" stroke-linecap="round"/>'
    ]
    city_slots = is_city and interactive
    for piece, column in zip(pieces, columns, strict=True):
        standing = cubes_standing(layout, duty, piece, counts, seats)
        room = column_room(layout, duty, piece, interactive)
        for index in range(standing if room is None else room):
            y = baseline - (index + 1) * CUBE_CELL_HEIGHT + (CUBE_CELL_HEIGHT - CUBE_SIZE) / 2
            city_hooks = (
                f' data-city-column-player="{piece["id"]}" data-city-cube="{index}"'
                if city_slots
                else ""
            )
            slot = (
                "" if room is None else f'{city_hooks} opacity="{1 if index < standing else 0:g}"'
            )
            parts.append(
                f'<rect x="{column["x"]:.1f}" y="{y:.1f}" width="{CUBE_SIZE:g}"'
                f' height="{CUBE_SIZE:g}" fill="{piece["fill"]}" stroke="#000000"'
                f' stroke-width="{piece["cube_stroke_width"]:g}"'
                f' data-player="{piece["id"]}"{slot}/>'
            )
    capacity = f' data-city-capacity="{CITY_STACK_HEIGHT}"' if city_slots else ""
    return (
        f'<g class="{_class_name(duty["id"], "cube-tally")}" data-cube-tally="{duty["id"]}"'
        f' data-player-count="{seats}"{capacity} opacity="{1 if visible else 0}"'
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


def render_tithe_icon(
    layout: dict,
    icon_id: str,
    cx: float,
    cy: float,
    position: str = "",
    visible: bool = True,
) -> str:
    """One Tithe token icon, drawn at its own scale in the left cap of a duty's capsule.

    An icon tagged with the ring `position` it belongs to is one the controls can turn on; it is
    drawn hidden unless it is the one that position currently shows.
    """
    spec = layout["tithe_icons"][icon_id]
    ink = layout["palette"]["ink"]
    if icon_id == "cornucopia":
        body = _icon_cornucopia(ink, layout["artwork"]["cornucopia_horn_path"])
    elif icon_id in _ICON_BODIES:
        body = _ICON_BODIES[icon_id](ink)
    else:
        raise KeyError(f"unknown tithe icon: {icon_id!r}")
    tags = f' data-duty-position="{position}" opacity="{1 if visible else 0:g}"' if position else ""
    return (
        f'<g class="{icon_id}-icon" data-tithe-token="{icon_id}"{tags}'
        f' transform="translate({cx:.1f} {cy + spec["offset_y"]:.1f}) scale({spec["scale"]:g})"'
        f' aria-label="{escape(spec["label"])}">{body}</g>'
    )


def render_merchant_token(
    layout: dict, cx: float, cy: float, position: str = "", visible: bool = True
) -> str:
    """The purple disc.

    Tagged with the ring `position` it stands on, it becomes one of the slots the Move Merchant
    button turns on and off; the disc itself carries no rules and moves nothing but itself.
    """
    merchant = layout["merchant_token"]
    tags = f' data-duty-position="{position}" opacity="{1 if visible else 0:g}"' if position else ""
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{CAPSULE_CAP_RADIUS:g}"'
        f' fill="{merchant["color"]}" stroke="{merchant["edge"]}" stroke-width="2"'
        f' data-token="merchant"{tags} aria-label="{escape(merchant["label"])}"/>'
    )


def _capsule_fill(layout: dict, duty: dict) -> str:
    palette = layout["palette"]
    return (
        f'<path d="{_capsule_path_data(*duty["center"])}" fill="{palette["capsule_fill"]}"'
        f' stroke="{palette["capsule_edge"]}" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"/>'
    )


def _capsule_outline(layout: dict, duty: dict) -> str:
    """The capsule border on its own, redrawn over the discs so they stay inside one outline."""
    palette = layout["palette"]
    return (
        f'<path d="{_capsule_path_data(*duty["center"])}" fill="none"'
        f' stroke="{palette["capsule_edge"]}" stroke-width="2" stroke-linecap="round"'
        ' stroke-linejoin="round"/>'
    )


def _render_tithe_capsule(layout: dict, duty: dict, icon_id: str, merchant: bool) -> str:
    """The capsule under a duty's title: its Tithe token, and the Merchant when he stands here.

    With the Merchant present the two discs are drawn clipped to the capsule, so the pair reads
    as one joined shape with a single outline rather than two circles that happen to touch.
    """
    palette = layout["palette"]
    tithe_x, merchant_x, cap_y = _capsule_caps(*duty["center"])

    if merchant:
        shape = (
            f'<g clip-path="url(#{duty["id"]}-capsule-clip)">'
            f'<circle cx="{tithe_x:.1f}" cy="{cap_y:.1f}" r="{CAPSULE_CAP_RADIUS:g}"'
            f' fill="{palette["capsule_fill"]}"/>'
            f"{render_merchant_token(layout, merchant_x, cap_y)}</g>"
            f"{_capsule_outline(layout, duty)}"
        )
    else:
        shape = _capsule_fill(layout, duty)
    icon = render_tithe_icon(layout, icon_id, tithe_x, cap_y)
    return f'<g class="{_class_name(duty["id"], "tithe-shape")}">{shape}{icon}</g>'


def _render_interactive_capsule(layout: dict, duty: dict, merchant: bool) -> str:
    """The capsule with every slot the controls can turn on: the Merchant, and each Tithe token.

    The Merchant is drawn between the capsule's fill and its border, clipped to the capsule, so
    turning him on joins the two discs into one shape exactly as the static board draws it.
    """
    tithe_x, merchant_x, cap_y = _capsule_caps(*duty["center"])
    icons = "".join(
        render_tithe_icon(
            layout, icon_id, tithe_x, cap_y, duty["id"], icon_id == duty["tithe_icon"]
        )
        for icon_id in layout["tithe_icons"]
    )
    return (
        f'<g class="{_class_name(duty["id"], "tithe-shape")}">'
        f"{_capsule_fill(layout, duty)}"
        f'<g clip-path="url(#{duty["id"]}-capsule-clip)">'
        f"{render_merchant_token(layout, merchant_x, cap_y, duty['id'], merchant)}</g>"
        f"{_capsule_outline(layout, duty)}{icons}</g>"
    )


def _render_tallies(layout: dict, duty: dict, counts: dict, interactive: bool) -> str:
    """The cube tally, or — interactive — one tally per player count with the default showing.

    Each count gets its own group because the columns move when seats drop out: the visible ones
    stay centred on the duty. Switching views is then a matter of flipping which group is drawn.
    """
    if not interactive:
        return render_cube_tally(layout, duty, counts)
    default = layout["default_player_count"]
    return "".join(
        render_cube_tally(layout, duty, counts, count, visible=count == default, interactive=True)
        for count in layout["player_counts"]
    )


def render_duty_space(
    layout: dict,
    duty: dict,
    counts: dict,
    merchant: bool = False,
    interactive: bool = False,
    ring_index: int | None = None,
) -> str:
    """One space: its parchment, title, cube tally, and the capsule holding its Tithe token."""
    parts = [_render_space(duty), _render_tallies(layout, duty, counts, interactive)]

    # The City is not a duty tile: it holds no Tithe token, and the Merchant never stands on it.
    if duty["id"] != layout["city_id"]:
        icon_id = duty["tithe_icon"]
        if icon_id and interactive:
            parts.append(_render_interactive_capsule(layout, duty, merchant))
        elif icon_id:
            parts.append(_render_tithe_capsule(layout, duty, icon_id, merchant))
        elif interactive or merchant:
            # Taxation has no capsule for the Merchant to share, so he stands in the empty band.
            slot_x, slot_y = merchant_slot_center(duty)
            position = duty["id"] if interactive else ""
            parts.append(render_merchant_token(layout, slot_x, slot_y, position, merchant))

    index = "" if ring_index is None else f' data-duty-ring-index="{ring_index}"'
    position = board_position_of(duty)
    # Three names for one space, and they answer three different questions. `data-duty` is the
    # prototype's id for it and is only good for finding the same space twice. `data-board-position`
    # is where it stands on the engine's board, which is what movement is defined in terms of and
    # what a turned tile leaves alone. `data-duty-category` is the tile lying there now, which is
    # exactly what turning the tiles changes.
    return (
        f'<g data-duty="{duty["id"]}"{index}'
        f' data-board-position="{position}"'
        f' data-board-position-index="{board_position_index(position)}"'
        f' data-duty-category="{duty["id"]}">{"".join(parts)}</g>'
    )


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
        half = ORNAMENT_RULE_HALF_WIDTH
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


def ring_arrow_ends(layout: dict, index: int) -> tuple[str, str]:
    """The two board positions one clockwise arrow runs between, in the order it points.

    The arrows are one shape turned around the board, so which pair an arrow stands between is a
    matter of how far it has been turned rather than anything drawn into it: the arrow at rotation
    zero sits between the last space clockwise and the first, and each turn moves it on one. What
    comes back is the pair of board positions, because that is what a move is made of; the spaces
    were only how the turning was counted.
    """
    order = layout["clockwise_order"]
    ends = (order[(index - 1) % len(order)], order[index % len(order)])
    origin, destination = (
        board_position_of(duty_position_by_id(layout, duty_id)) for duty_id in ends
    )
    return origin, destination


def _arrow_ends_markup(origin: str, destination: str, board: dict) -> str:
    """The pair of positions one arrow joins, named and numbered as the engine names them."""
    return (
        f' data-from-position="{origin}" data-to-position="{destination}"'
        f' data-from-position-index="{board_position_index(origin, board)}"'
        f' data-to-position-index="{board_position_index(destination, board)}"'
    )


def _render_ring_arrows(layout: dict) -> str:
    cx, cy = layout["board"]["center"]
    path = layout["artwork"]["ring_arrow_path"]
    step = 360 // RING_ARROW_COUNT
    board = load_board_config()
    arrows = []
    for index in range(RING_ARROW_COUNT):
        origin, destination = ring_arrow_ends(layout, index)
        arrows.append(
            f'<g transform="rotate({index * step:g} {_num(cx)} {_num(cy)})"'
            f' data-ring-arrow="{index}"{_arrow_ends_markup(origin, destination, board)}>'
            f'<path d="{path}" class="arrow-border"/><path d="{path}" class="arrow-interior"/></g>'
        )
    return '<g aria-label="Clockwise outer arrows">' + "".join(arrows) + "</g>"


def _render_middle_arrows(layout: dict) -> str:
    """The four arrows across the middle, tagged with the pair of positions each one joins.

    The ring arrows carry the same pair of attributes, so a page asking which ways lead out of a
    position puts the one question to both families of arrow -- and gets an answer in the names the
    engine moves cubes by rather than in the names this board happens to print on its tiles.
    """
    path = layout["artwork"]["middle_arrow_path"]
    board = load_board_config()
    arrows = []
    for arrow in layout["middle_arrows"]:
        x, y = arrow["at"]
        transform = f"translate({_num(x)} {_num(y)})"
        if arrow["rotate"]:
            transform += f" rotate({arrow['rotate']:g})"
        origin, destination = (
            board_position_of(duty_position_by_id(layout, arrow[end])) for end in ("from", "to")
        )
        arrows.append(
            f'<g transform="{transform}" data-middle-arrow="{arrow["id"]}"'
            f"{_arrow_ends_markup(origin, destination, board)}>"
            f'<path d="{path}" class="arrow-border"/><path d="{path}" class="arrow-interior"/></g>'
        )
    return '<g aria-label="Middle directional arrows">' + "".join(arrows) + "</g>"


# ---------------------------------------------------------------------------------------------
# Turn controls
# ---------------------------------------------------------------------------------------------


def turn_control_width(label: str) -> float:
    """How wide a plaque has to be to hold its label."""
    return max(
        TURN_CONTROL_MIN_WIDTH, len(label) * TURN_CONTROL_CHAR_WIDTH + 2 * TURN_CONTROL_PADDING_X
    )


def _plaque(x: float, y: float, width: float, fill: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}"'
        f' height="{TURN_CONTROL_HEIGHT:g}" rx="{TURN_CONTROL_RADIUS:g}" fill="{fill}"'
        f' stroke="{TURN_CONTROL_STROKE}" stroke-width="{TURN_CONTROL_STROKE_WIDTH:g}"/>'
    )


def _plaque_text(x: float, y: float, label: str, fill: str, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}"'
        ' font-family="Helvetica, Arial, sans-serif"'
        f' font-size="{TURN_CONTROL_FONT_SIZE:g}" text-anchor="{anchor}"'
        f' dominant-baseline="middle">{escape(label)}</text>'
    )


def render_turn_control_button(
    x: float, y: float, label: str, control: str, enabled: bool = True, active: bool = False
) -> str:
    """One control plaque, its top-left corner at `x, y`.

    A control that cannot be used is dimmed rather than removed, so the row keeps its shape while
    a turn moves through it. Nothing here listens for a click: the plaque is the shell a later
    turn flow fills in, and `data-turn-control` is the handle it will take hold of.
    """
    fill = TURN_CONTROL_ACTIVE_FILL if active else TURN_CONTROL_FILL
    ink = TURN_CONTROL_ACTIVE_TEXT if active else TURN_CONTROL_TEXT
    width = turn_control_width(label)
    dimmed = "" if enabled else f' opacity="{TURN_CONTROL_DISABLED_OPACITY}" aria-disabled="true"'
    return (
        f'<g data-turn-control="{control}" data-turn-control-enabled="{str(enabled).lower()}"'
        f' role="button" aria-label="{escape(label)}"{dimmed}>'
        f"{_plaque(x, y, width, fill)}"
        f"{_plaque_text(x + width / 2, y + TURN_CONTROL_HEIGHT / 2, label, ink)}</g>"
    )


def turn_counter_width(value: int) -> float:
    """A counter is its cube, its gap, and the `x N` beside them, inside the same padding.

    The count is measured at its widest rather than at the value the plaque opens on, so a page
    that counts a handful up into two figures writes a longer number into a plaque already wide
    enough to hold it, and the shell never has to be redrawn to fit what it says.
    """
    label = _turn_counter_label(value)
    return (
        2 * TURN_CONTROL_PADDING_X
        + TURN_COUNTER_CUBE_SIZE
        + TURN_COUNTER_GAP
        + max(len(label), TURN_COUNTER_WIDEST_LABEL) * TURN_CONTROL_CHAR_WIDTH
    )


def _turn_counter_label(value: int) -> str:
    return f"\u00d7 {value}"


def render_turn_cube_counter(x: float, y: float, value: int = TURN_COUNTER_IDLE_VALUE) -> str:
    """The cubes-in-hand plaque, its top-left corner at `x, y`.

    A readout rather than a button, so it takes no role and no enabled state. The cube on it is a
    neutral stone: a handful picked up off a duty tile can hold more than one seat's colour, and a
    plaque painted in one of them would be saying something the count does not.
    """
    width = turn_counter_width(value)
    middle = y + TURN_CONTROL_HEIGHT / 2
    cube_x = x + TURN_CONTROL_PADDING_X
    count = _plaque_text(
        cube_x + TURN_COUNTER_CUBE_SIZE + TURN_COUNTER_GAP,
        middle,
        _turn_counter_label(value),
        TURN_CONTROL_TEXT,
        anchor="start",
    )
    return (
        f'<g data-turn-counter="cubes-in-hand" data-turn-counter-value="{value}"'
        f' aria-label="Cubes in hand: {value}">'
        f"{_plaque(x, y, width, TURN_CONTROL_FILL)}"
        f'<rect x="{cube_x:.1f}" y="{middle - TURN_COUNTER_CUBE_SIZE / 2:.1f}"'
        f' width="{TURN_COUNTER_CUBE_SIZE:g}" height="{TURN_COUNTER_CUBE_SIZE:g}"'
        f' fill="{TURN_COUNTER_CUBE_FILL}"/>{count}</g>'
    )


def _turn_control_row(anchor: dict, corner: str, buttons: tuple[tuple[str, str, bool], ...]) -> str:
    """A row of plaques hung on one corner anchor, growing away from the corner it stands in."""
    widths = [turn_control_width(label) for label, _, _ in buttons]
    total = sum(widths) + TURN_CONTROL_GAP * (len(buttons) - 1)
    left = anchor["x"] - total if corner.endswith("right") else anchor["x"]
    top = anchor["y"] - TURN_CONTROL_HEIGHT if corner.startswith("bottom") else anchor["y"]

    rendered = []
    for (label, control, enabled), width in zip(buttons, widths, strict=True):
        rendered.append(render_turn_control_button(left, top, label, control, enabled=enabled))
        left += width + TURN_CONTROL_GAP
    return "".join(rendered)


def render_turn_control_overlay(layout: dict, state: str = "idle") -> str:
    """The four corner plaques, drawn in the board's root units above everything else.

    This is the shell of a turn and none of its behaviour: the wheel draws Sow, what is in hand,
    and the four ways a turn ends, so that the shape of the turn flow can be read off the board
    before any of it is wired up. `data-turn-state` names the state the whole set is in, which is
    `idle` and only `idle` until something can change it.

    The plaques stand in the black the green hexagon leaves in the four corners of its box. That
    is the one part of the canvas nothing else uses, and it is inside the box the game table crops
    the wheel to, so the controls travel with the board rather than being cut off the side of it.

    Each anchor in the layout is the corner of its own group nearest the corner of the board it
    hangs in -- a left anchor gives the left edge and a bottom anchor the bottom edge -- so a row
    grows inward and downward from the corner it belongs to whichever way round it is written.
    """
    anchors = layout["turn_controls"]
    parts = [
        _turn_control_row(anchors["top_left"], "top_left", (("Sow", "sow", True),)),
        render_turn_cube_counter(
            anchors["top_right"]["x"] - turn_counter_width(TURN_COUNTER_IDLE_VALUE),
            anchors["top_right"]["y"],
        ),
        _turn_control_row(
            anchors["bottom_left"],
            "bottom_left",
            (("Reset", "reset", False), ("Confirm", "confirm", False)),
        ),
        _turn_control_row(
            anchors["bottom_right"],
            "bottom_right",
            (("Action", "action", False), ("Tithe", "tithe", False)),
        ),
    ]
    return (
        f'<g data-component="duty-wheel-turn-controls" data-turn-state="{state}"'
        f' aria-label="Turn controls">{"".join(parts)}</g>'
    )


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


def _render_defs(layout: dict, merchant_duty_id: str, interactive: bool = False) -> str:
    """The gradients, the capsule clips, and the board's own stylesheet.

    A static board only needs the clip belonging to the duty the Merchant stands on; an
    interactive one needs every capsule's, since he can be turned on at any of them.
    """
    palette = layout["palette"]
    parchment_from, parchment_to = palette["parchment"]
    ground_from, ground_to = palette["ground"]
    if interactive:
        clipped = [duty for duty in ring_duties(layout) if duty["tithe_icon"]]
    else:
        clipped = [duty_position_by_id(layout, merchant_duty_id)] if merchant_duty_id else []
    clip = "".join(
        f'<clipPath id="{duty["id"]}-capsule-clip">'
        f'<path d="{_capsule_path_data(*duty["center"])}"/></clipPath>'
        for duty in clipped
        if duty["tithe_icon"]
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


def render_duty_wheel_svg(
    layout: dict,
    board_state: dict | None = None,
    merchant_on: str | None = None,
    interactive: bool = False,
    turn_controls: bool = False,
) -> str:
    """The whole board: title, ground, arrows, and the nine spaces with their contents.

    `merchant_on` overrides where the Merchant stands, which the baseline parity check uses to
    ask for the board the prototype drew. `interactive` adds the hidden slots the page's debug
    controls switch between; left off, the board is the fixed picture the prototype shows.
    `turn_controls` adds the turn-control shell in the corners, which is a picture of a turn flow
    and none of its behaviour; it is off unless a page asks for it, so a page that has not been
    designed around it does not quietly grow a set of controls.
    """
    board = layout["board"]
    palette = layout["palette"]
    page = layout["page"]
    state = default_duty_wheel_state(layout) if board_state is None else board_state
    merchant_duty_id = merchant_on or layout["merchant_token"]["starts_on"]
    cx, cy = board["center"]
    frame = board["frame"]

    subtitle = "".join(
        f'<tspan x="{board["width"] / 2:g}" dy="{0 if index == 0 else 17:g}">{escape(line)}</tspan>'
        for index, line in enumerate(page["subtitle"])
    )

    city = duty_position_by_id(layout, layout["city_id"])
    spaces = [render_duty_space(layout, city, state.get(city["id"], {}), interactive=interactive)]
    for index, duty in enumerate(ring_duties(layout)):
        spaces.append(
            render_duty_space(
                layout,
                duty,
                state.get(duty["id"], {}),
                merchant=duty["id"] == merchant_duty_id,
                interactive=interactive,
                ring_index=index if interactive else None,
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
        f"{_render_defs(layout, merchant_duty_id, interactive)}"
        f'<rect width="{board["width"]:g}" height="{board["height"]:g}"'
        f' fill="{palette["page_background"]}"/>'
        f'<rect x="{frame["x"]:g}" y="{frame["y"]:g}" width="{frame["width"]:g}"'
        f' height="{frame["height"]:g}" rx="{frame["corner_radius"]:g}" fill="none"'
        f' stroke="{palette["frame_stroke"]}" stroke-width="1.5"/>'
        f'<text x="{board["width"] / 2:g}" y="{board["title_baseline"]:g}"'
        f' fill="{palette["title"]}" font-family="Georgia, \'Times New Roman\', serif"'
        f' font-size="30" font-weight="700" text-anchor="middle">'
        f"{escape(page['board_title'])}</text>"
        f'<text x="{board["width"] / 2:g}" y="{board["subtitle_baseline"]:g}"'
        f' fill="{palette["subtitle"]}" font-family="Helvetica, Arial, sans-serif"'
        f' font-size="13.5" text-anchor="middle">{subtitle}</text>'
        f'<g transform="translate({_num(cx)} {_num(cy)})'
        f' scale({_num(board["scale"])}) translate({_num(-cx)} {_num(-cy)})">'
        f'<path d="{board["ground_path"]}" fill="url(#hex-gradient)"'
        f' stroke="{palette["ground_edge"]}" stroke-width="4" stroke-linejoin="round"/>'
        f"{_render_ring_arrows(layout)}{_render_middle_arrows(layout)}"
        f'<g aria-label="Board spaces">{"".join(spaces)}</g>'
        "</g>"
        # Outside the scaled group: the corners are measured on the canvas the page is cropped
        # against, so the plaques are written in those same units rather than the board's.
        f"{render_turn_control_overlay(layout) if turn_controls else ''}"
        "</svg>"
    )


_CONTROLS_HTML = """  <div class="duty-wheel-controls">
    <button type="button" id="duty-wheel-randomize">Randomize Duty tiles</button>
    <button type="button" id="duty-wheel-move-merchant">Move Merchant</button>
    <span class="duty-wheel-counts" role="group" aria-label="Player count">{player_counts}</span>
    <span class="duty-wheel-readout" id="duty-wheel-readout">{readout}</span>
  </div>
"""

_PLAYER_COUNT_BUTTON = (
    '<button type="button" data-player-count="{count}" aria-pressed="{pressed}">{count}p</button>'
)

# Every hook the controls own is prefixed, because the generated setup view drops this panel into
# a page that already has its own `.controls` row and `.readout` spans.
DUTY_WHEEL_CONTROL_STYLES = """  .duty-wheel-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .duty-wheel-controls button {
    background: #1C1C1C;
    border: 1px solid #4A4A4A;
    border-radius: 6px;
    color: #F2EEDF;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
    padding: 7px 12px;
  }
  .duty-wheel-controls button:hover { background: #2A2A2A; }
  .duty-wheel-counts { display: flex; gap: 4px; }
  .duty-wheel-counts button[aria-pressed="true"] {
    background: #F2EEDF;
    border-color: #F2EEDF;
    color: #1C1C1C;
  }
  .duty-wheel-readout { color: #A8A296; font-size: 13px; }
"""

# Plain inline JavaScript, no dependencies. It flips opacity on slots the renderer already drew
# and rewrites the eight duty titles; it decides nothing about the game.
_CONTROLS_SCRIPT = """<script>
(function () {
  var SETUPS = __SETUPS__;
  var MERCHANT_PATH = __MERCHANT_PATH__;
  var board = document.querySelector('[data-component="duty-wheel"]');
  var readout = document.getElementById('duty-wheel-readout');
  var countButtons = document.querySelectorAll('.duty-wheel-counts button');
  var setupIndex = 0;
  var merchant = __START__;
  var playerCount = __PLAYER_COUNT__;

  function currentSetup() {
    return SETUPS[setupIndex];
  }

  function entryFor(position) {
    return currentSetup().filter(function (entry) { return entry.position === position; })[0];
  }

  /* Turning the tiles changes which duty lies at a position -- its title, its Tithe token, and
     the category the space reports. Where the space stands is not the tiles' to change, so the
     board-position hooks the arrows and any movement are keyed to are left alone. */
  function applySetup() {
    currentSetup().forEach(function (entry) {
      var space = board.querySelector('[data-duty="' + entry.position + '"]');
      if (space) { space.setAttribute('data-duty-category', entry.duty); }
      var label = board.querySelector('[data-duty-label="' + entry.position + '"]');
      if (label) { label.textContent = entry.label; }
      var icons = board.querySelectorAll(
        '[data-duty-position="' + entry.position + '"][data-tithe-token]'
      );
      Array.prototype.forEach.call(icons, function (icon) {
        var shown = icon.getAttribute('data-tithe-token') === entry.tithe_icon;
        icon.setAttribute('opacity', shown ? '1' : '0');
      });
    });
  }

  function applyMerchant() {
    var tokens = board.querySelectorAll('[data-token="merchant"]');
    Array.prototype.forEach.call(tokens, function (token) {
      var here = token.getAttribute('data-duty-position') === merchant;
      token.setAttribute('opacity', here ? '1' : '0');
    });
    board.setAttribute('data-merchant-token', merchant);
  }

  // The next duty tile clockwise, wrapping round the ring. The City is not on the path.
  function nextMerchantPosition(current) {
    return MERCHANT_PATH[(MERCHANT_PATH.indexOf(current) + 1) % MERCHANT_PATH.length];
  }

  // Each player count has its own tally drawn on every duty, already centred for that many
  // seats, so switching views only decides which of them shows.
  function applyPlayerCount() {
    var tallies = board.querySelectorAll('[data-cube-tally]');
    Array.prototype.forEach.call(tallies, function (tally) {
      var shown = tally.getAttribute('data-player-count') === String(playerCount);
      tally.setAttribute('opacity', shown ? '1' : '0');
    });
    Array.prototype.forEach.call(countButtons, function (button) {
      var active = button.getAttribute('data-player-count') === String(playerCount);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function updateReadout() {
    readout.textContent =
      'Setup ' + (setupIndex + 1) + ' of ' + SETUPS.length +
      ' \\u2014 Merchant on ' + entryFor(merchant).label +
      ' \\u2014 ' + playerCount + ' players';
  }

  document.getElementById('duty-wheel-randomize').addEventListener('click', function () {
    setupIndex = (setupIndex + 1) % SETUPS.length;
    applySetup();
    updateReadout();
  });

  document.getElementById('duty-wheel-move-merchant').addEventListener('click', function () {
    merchant = nextMerchantPosition(merchant);
    applyMerchant();
    updateReadout();
  });

  Array.prototype.forEach.call(countButtons, function (button) {
    button.addEventListener('click', function () {
      playerCount = Number(button.getAttribute('data-player-count'));
      applyPlayerCount();
      updateReadout();
    });
  });

  updateReadout();
})();
</script>
"""


def duty_wheel_readout(
    layout: dict,
    setup_index: int = 0,
    merchant: str | None = None,
    player_count: int | None = None,
) -> str:
    """What the controls report: the sample setup, where the Merchant stands, and the seat count."""
    position = merchant or layout["merchant_token"]["starts_on"]
    seats = player_count or layout["default_player_count"]
    setups = duty_setups(layout)
    label = next(entry["label"] for entry in setups[setup_index] if entry["position"] == position)
    return f"Setup {setup_index + 1} of {len(setups)} — Merchant on {label} — {seats} players"


def render_duty_wheel_controls_script(layout: dict) -> str:
    """The page's debug buttons, wired to the slots the interactive board draws.

    The whole thing is one IIFE reaching for prefixed hooks only, so a host page can drop it in
    beside its own scripts without sharing a name with them.
    """
    return (
        _CONTROLS_SCRIPT.replace("__SETUPS__", json.dumps(duty_setups(layout)))
        .replace("__MERCHANT_PATH__", json.dumps(merchant_path(layout)))
        .replace("__START__", json.dumps(layout["merchant_token"]["starts_on"]))
        .replace("__PLAYER_COUNT__", json.dumps(layout["default_player_count"]))
    )


def render_duty_wheel_controls_html(layout: dict) -> str:
    """The debug buttons and their readout, with the default player count already pressed."""
    buttons = "".join(
        _PLAYER_COUNT_BUTTON.format(
            count=count, pressed=str(count == layout["default_player_count"]).lower()
        )
        for count in layout["player_counts"]
    )
    return _CONTROLS_HTML.format(player_counts=buttons, readout=escape(duty_wheel_readout(layout)))


def render_duty_wheel_panel(
    layout: dict,
    board_state: dict | None = None,
    include_controls: bool = True,
    turn_controls: bool = False,
) -> str:
    """The controls and the board as one fragment a host page can drop into its own layout.

    This is what the generated setup view shows: it brings its own wrapper, heading, and width,
    and pairs this with `DUTY_WHEEL_CONTROL_STYLES` and `render_duty_wheel_controls_script()`.
    Without controls the board is the fixed picture, so no hidden slots are drawn either. The
    turn-control shell is asked for separately, since it is drawn on the board rather than beside
    it and a host page may want the one without the other.
    """
    controls = render_duty_wheel_controls_html(layout) if include_controls else ""
    board = render_duty_wheel_svg(
        layout, board_state, interactive=include_controls, turn_controls=turn_controls
    )
    return f"{controls}{board}"


def render_duty_wheel_html(
    layout: dict,
    board_state: dict | None = None,
    interactive: bool = False,
    turn_controls: bool = False,
) -> str:
    """The board on its own page, the way the baseline prototype presents it.

    `interactive` is what the generated page uses: it adds the two debug buttons, which cycle
    sample duty setups and walk the Merchant token around the ring. `turn_controls` adds the
    corner plaques the turn flow will one day be driven from.
    """
    palette = layout["palette"]
    merchant = layout["merchant_token"]
    panel = render_duty_wheel_panel(
        layout, board_state, include_controls=interactive, turn_controls=turn_controls
    )
    script = render_duty_wheel_controls_script(layout) if interactive else ""
    moves = (
        "The buttons above cycle sample Duty tile setups, walk the Merchant clockwise around the "
        "eight duty tiles — the City is not on his path — and switch the cube tallies between "
        "the two-, three-, and four-player views."
        if interactive
        else "Neither moves."
    )
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
{DUTY_WHEEL_CONTROL_STYLES}  .duty-wheel-controls {{ padding: 16px 12px 4px; }}
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
{panel}
  <p class="note">
    Generated from {LAYOUT_FILENAME}. The purple disc is the {escape(merchant["label"])} and the
    resource icons are Tithe tokens. {moves} Visual/debug only — no GameState integration, no
    gameplay rules, and no sow animation.
  </p>
{script}</body>
</html>
"""
