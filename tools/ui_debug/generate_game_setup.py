"""Write the generated game setup debug page.

The page composes four existing renderers — the map, the 3-4 player piety track v2, the building
tiles, and the pilgrimage sites — and adds a ship marker, moving the track's own player discs with
plain buttons.

The setup slots are a hard-coded example schedule, not the output of `pilgrim.setup.generator`:
the sites are always the first four in file order, never drawn at random.
Everything here is visual only: nothing reads or writes `GameState`, picks legal actions, or
applies any rule, and moving a marker changes an SVG attribute and nothing else.

Run from the repo root:

    python3 tools/ui_debug/generate_game_setup.py
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from xml.sax.saxutils import escape

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ui_debug.render_buildings import HEX_RADIUS as TILE_HEX_RADIUS  # noqa: E402
from tools.ui_debug.render_buildings import (  # noqa: E402
    TILE_NAME_CENTER_Y_OFFSET,
    TILE_NAME_FONT_SIZE,
    TILE_NAME_LINE_HEIGHT,
    load_building_catalog,
    palette_for,
    tile_text_lines,
)
from tools.ui_debug.render_donated_buildings import HEX_RADIUS as DONATED_HEX_RADIUS  # noqa: E402
from tools.ui_debug.render_donated_buildings import (  # noqa: E402
    load_donated_building_tiles,
    render_donated_building_contents,
    tiles_of,
)
from tools.ui_debug.render_duty_wheel import (  # noqa: E402
    DUTY_WHEEL_CONTROL_STYLES,
    load_duty_wheel_layout,
    render_duty_wheel_controls_script,
    render_duty_wheel_panel,
)
from tools.ui_debug.render_map import (  # noqa: E402
    hex_center,
    hex_vertices,
    label_to_coord,
    load_map_layout,
    render_map_svg,
)
from tools.ui_debug.render_piety_track_v2 import (  # noqa: E402
    load_piety_config,
    load_piety_track_v2_layout,
    position_center_x,
    render_piety_track_v2_svg,
    seated_players,
    variant_by_id,
)
from tools.ui_debug.render_pilgrimage_sites import (  # noqa: E402
    DATA_FILENAME as SITE_DATA_FILENAME,
)
from tools.ui_debug.render_pilgrimage_sites import (  # noqa: E402
    SITE_FILL,
    SITE_STROKE,
    load_pilgrimage_sites,
    render_pilgrimage_site_contents,
    site_by_index,
)
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    BUILDING_SLOT_HEX_SIZE as BOARD_HEX_SIZE,
)
from tools.ui_debug.render_player_boards_v2 import (  # noqa: E402
    DEFAULT_PLAYER,
    ROLE_ACOLYTE_LIMIT,
    default_player_board_v2_state,
    hex_path_data,
    load_player_boards_v2_layout,
    players_of,
    render_player_board_v2_svg,
    token_slot_count,
)
from tools.ui_debug.render_ship_marker import (  # noqa: E402
    SHIP_ANCHOR_OFFSET_Y as TILE_SHIP_ANCHOR_OFFSET_Y,
)
from tools.ui_debug.render_ship_marker import (  # noqa: E402
    SHIP_SCALE as TILE_SHIP_SCALE,
)
from tools.ui_debug.render_ship_marker import render_ship_icon  # noqa: E402

GENERATED_DIRNAME = "generated"
OUTPUT_FILENAME = "game_setup.html"

TITLE = "PILGRIM — Game Setup Debug View"
SUBTITLE = (
    "Generated map with the 3-4 player piety track v2 above it, one hard-coded example setup laid "
    "out on the edge hexes, and the four player boards beside them. The start roll, ship, piety, "
    "and player board buttons move markers and cubes only: no GameState, no rules, no actions."
)
PAGE_BACKGROUND = "#000000"

# The setup page has four players, so it uses the 3-4 player track: two disc rows on the starting
# space, one disc per player, in the seat order red, yellow, blue, white. The 2 player variant is
# not drawn here; it stays on the standalone piety track v2 page.
PIETY_VARIANT_ID = "3_4_player"

# The edge hexes clockwise from J3, skipping the four special corner hexes below. That leaves 26
# eligible hexes, which is also the engine's round track length. The ship and the setup slots both
# ride this path; the setup slots start wherever the start roll says, the ship follows them.
EDGE_HEX_PATH = (
    "J3",
    "J2",
    "I1",
    "H1",
    "G1",
    "E1",
    "D1",
    "D2",
    "C3",
    "C4",
    "B5",
    "B7",
    "C8",
    "C9",
    "D10",
    "D11",
    "E11",
    "F11",
    "H11",
    "I11",
    "J10",
    "J9",
    "K8",
    "K7",
    "K5",
    "K4",
)
SKIPPED_HEXES = ("F1", "B6", "G11", "L6")
SHIP_POSITION_COUNT = len(EDGE_HEX_PATH)

SHIP_COLOR = "#000000"

# The outline a building wears while it is one of the ones that may be constructed. Deliberately
# the parchment an offered duty space on the wheel is ringed in, and deliberately not the
# building's own palette: a building already draws itself in its level's colours, and lighting an
# offered one in more of the same would read as a property of the building rather than as
# something being asked about it right now.
BUILDING_CHOICE_STROKE = "#F2EEDF"
BUILDING_CHOICE_STROKE_WIDTH = 4.0

# The start roll decides which eligible hex carries setup slot 1; the rest follow clockwise.
START_HEX_BY_ROLL = {1: "E1", 2: "D1", 3: "D2", 4: "C3", 5: "C4", 6: "B5"}
DEFAULT_START_ROLL = 1

# One hard-coded example schedule, in slot order: (round, label, kind). It stands in for the real
# setup generator, which this page deliberately does not call.
SETUP_SLOTS = (
    (1, "Pilgrimage site 1", "site"),
    (2, "Empty", "empty"),
    (3, "Guild (level 1)", "building"),
    (4, "Mint (level 1)", "building"),
    (5, "Chapter House (level 1)", "building"),
    (6, "Infirmary (level 1)", "building"),
    (7, "Pilgrimage site 2", "site"),
    (8, "Empty", "empty"),
    (9, "Dormitory (level 2)", "building"),
    (10, "Cloisters (level 2)", "building"),
    (11, "Brewery (level 2)", "building"),
    (12, "Stone Yard (level 2)", "building"),
    (13, "Empty", "empty"),
    (14, "Empty", "empty"),
    (15, "Pilgrimage site 3", "site"),
    (16, "Empty", "empty"),
    (17, "Pulpit (level 3)", "building"),
    (18, "Inquisition (level 3)", "building"),
    (19, "Pilgrimage site 4", "site"),
    (20, "Empty", "empty"),
    (21, "Wagon Yard (level 3)", "building"),
    (22, "Kogge (level 3)", "building"),
    (23, "Empty", "empty"),
    (24, "Empty", "empty"),
    (25, "Empty", "empty"),
    (26, "Empty", "empty"),
)

_SETUP_BUILDING_LABEL = re.compile(r"^(?P<name>.+) \(level (?P<level>\d+)\)$")
_SETUP_SITE_LABEL = re.compile(r"^Pilgrimage site (?P<number>\d+)$")


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / GENERATED_DIRNAME / OUTPUT_FILENAME


def _tile_ratio(map_layout: dict) -> float:
    """Map hexes are smaller than building tile hexes, so ship geometry is scaled between them."""
    return map_layout["hex_size"] / TILE_HEX_RADIUS


def ship_scale(map_layout: dict) -> float:
    return TILE_SHIP_SCALE * _tile_ratio(map_layout)


def ship_anchor_offset_y(map_layout: dict) -> float:
    return TILE_SHIP_ANCHOR_OFFSET_Y * _tile_ratio(map_layout)


def hex_centers(
    map_layout: dict, labels: Sequence[str] = EDGE_HEX_PATH
) -> dict[str, tuple[float, float]]:
    """Where each named hex sits in map coordinates.

    The centres are resolved through the map's own label table, so an overlay cannot end up on a
    hex the map does not draw, or drift if the labelling ever changes.
    """
    coords = label_to_coord(map_layout)
    return {label: hex_center(map_layout, *coords[label]) for label in labels}


def rotated_edge_path(start_hex: str) -> list[str]:
    """The eligible edge hexes, still clockwise, but starting on `start_hex`."""
    offset = EDGE_HEX_PATH.index(start_hex)
    return list(EDGE_HEX_PATH[offset:] + EDGE_HEX_PATH[:offset])


def start_hex_for_roll(start_roll: int) -> str:
    return START_HEX_BY_ROLL[start_roll]


def parse_setup_building_label(label: str) -> tuple[str, int]:
    """`"Stone Yard (level 2)"` -> `("Stone Yard", 2)`, the catalog name and its level."""
    match = _SETUP_BUILDING_LABEL.match(label)
    if match is None:
        raise ValueError(f"not a setup building label: {label!r}")
    return match["name"], int(match["level"])


def parse_setup_site_label(label: str) -> int:
    """`"Pilgrimage site 2"` -> `2`, the site's place in the schedule."""
    match = _SETUP_SITE_LABEL.match(label)
    if match is None:
        raise ValueError(f"not a setup site label: {label!r}")
    return int(match["number"])


def building_by_name(catalog: dict) -> dict[str, dict]:
    return {building["name"]: building for building in catalog["buildings"]}


def setup_placements(
    start_roll: int, catalog: dict | None = None, site_data: dict | list | None = None
) -> list[dict]:
    """One entry per setup slot, resolved onto the edge hex it occupies for this start roll.

    The four site slots take the first four sites in file order. Drawing sites at random is a job
    for the real setup generator, which this page does not call.
    """
    buildings = building_by_name(catalog) if catalog is not None else {}
    path = rotated_edge_path(start_hex_for_roll(start_roll))

    placements = []
    for round_number, label, kind in SETUP_SLOTS:
        placement = {
            "round": round_number,
            "label": label,
            "kind": kind,
            "hex": path[round_number - 1],
            "building": None,
            "site": None,
        }
        if kind == "building" and buildings:
            name, level = parse_setup_building_label(label)
            building = buildings[name]
            if building["level"] != level:
                raise ValueError(f"{name} is level {building['level']}, not level {level}")
            placement["building"] = building
        if kind == "site" and site_data is not None:
            placement["site"] = site_by_index(site_data, parse_setup_site_label(label) - 1)
        placements.append(placement)
    return placements


def _hex_polygon(map_layout: dict, fill: str) -> str:
    """The map's own hex shape around the origin, filled and unstroked."""
    points = " ".join(f"{x:.2f},{y:.2f}" for x, y in hex_vertices(0.0, 0.0, map_layout["hex_size"]))
    return f'<polygon points="{points}" fill="{fill}" stroke="none"/>'


def render_setup_building_fill(map_layout: dict, building: dict) -> str:
    """A building slot recolours its hex; it does not lay a second hex on top of it."""
    return _hex_polygon(map_layout, palette_for(building).fill)


def render_setup_site_fill(map_layout: dict) -> str:
    """A site slot recolours its hex too, in the pilgrimage site orange."""
    return _hex_polygon(map_layout, SITE_FILL)


def render_setup_site_contents(map_layout: dict, site: dict) -> str:
    """The site tile's star and values, scaled from the tile hex down to the map hex.

    The site's own dark orange is the ink here, the way a placed building writes in its palette's
    stroke colour, so the values read as part of the recoloured hex rather than as a tile on it.
    """
    return render_pilgrimage_site_contents(site, scale=_tile_ratio(map_layout), ink=SITE_STROKE)


def render_building_label(building: dict, hex_size: float) -> str:
    """The tile's own label, at the tile's own proportions, in the lower half of the hex.

    A hex the label lands in — a map hex or a player board's building slot — is smaller than a
    building tile, so the tile's text geometry is scaled between the two rather than restated.
    Every line stays below the centre, which is what keeps the upper half free for the map's own
    hex label and the ship, and is how a bought building reads the same on a board slot.
    """
    palette = palette_for(building)
    ratio = hex_size / TILE_HEX_RADIUS

    lines = []
    for index, line in enumerate(tile_text_lines(building)):
        text_y = ratio * (TILE_NAME_CENTER_Y_OFFSET + index * TILE_NAME_LINE_HEIGHT)
        lines.append(
            f'<text x="0" y="{text_y:.1f}" text-anchor="middle"'
            ' font-family="Helvetica, Arial, sans-serif"'
            f' font-size="{ratio * TILE_NAME_FONT_SIZE:.1f}" font-weight="600"'
            f' fill="{palette.stroke}">{escape(line)}</text>'
        )
    return "".join(lines)


def render_setup_building_label(map_layout: dict, building: dict) -> str:
    return render_building_label(building, map_layout["hex_size"])


def _placed(map_layout: dict, placement: dict, class_name: str, body: str) -> str:
    """One slot's share of a layer, moved as a whole when the start roll changes.

    A building also names itself, so a page can take it off the map when it is bought without
    having to know which hex the current start roll put it on.
    """
    center_x, center_y = hex_centers(map_layout)[placement["hex"]]
    building = placement["building"]
    named = f' data-building-id="{building["id"]}"' if building is not None else ""
    return (
        f'<g class="{class_name}" data-slot="{placement["round"]}"{named}'
        f' transform="translate({center_x:.1f},{center_y:.1f})">{body}</g>'
    )


def render_setup_fill_layer(map_layout: dict, placements: list[dict]) -> str:
    """The recoloured hexes, drawn onto the map's tile fills and under its own edges and labels."""
    groups = []
    for placement in placements:
        if placement["building"] is not None:
            body = render_setup_building_fill(map_layout, placement["building"])
            class_name = "setup-building-fill"
        elif placement["kind"] == "site":
            body = render_setup_site_fill(map_layout)
            class_name = "setup-site-fill"
        else:
            continue
        groups.append(_placed(map_layout, placement, class_name, body))
    return f'<g id="setup-fills">{"".join(groups)}</g>'


def render_setup_label_layer(map_layout: dict, placements: list[dict]) -> str:
    """What each slot says: building names and site values, drawn over the finished map.

    Both sit in the lower half of their hex, so the map's own edges and labels stay readable and
    the ship still has the upper half to itself.
    """
    groups = []
    for placement in placements:
        if placement["building"] is not None:
            body = render_setup_building_label(map_layout, placement["building"])
            class_name = "setup-building-label"
        elif placement["site"] is not None:
            body = render_setup_site_contents(map_layout, placement["site"])
            class_name = "setup-site-content"
        else:
            continue
        groups.append(_placed(map_layout, placement, class_name, body))
    return f'<g id="setup-labels">{"".join(groups)}</g>'


def render_setup_choice_layer(
    map_layout: dict,
    placements: list[dict],
    conversion_building_ids: Sequence[str] = (),
) -> str:
    """One key per building on the track, drawn hidden, for a page that has to ask WHICH BUILDING.

    On the map, because that is where a building already is. The market is not a list anywhere in
    this game -- a building stands on the round it goes live on, and a player looking for one looks
    at the track. Asking in a panel beside the board would mean naming the buildings a second time,
    in a second order, and leaving the player to match the name they picked against the hex they
    had been reading.

    The key is the whole hex rather than the name written on it, for the reason the stock keys are
    the whole pill: the label is two short lines of 8pt type and is not a thing to ask anyone to
    aim at. `fill="none"` with `pointer-events="all"` makes the hex catch the click without putting
    anything over the building it encloses, so the name stays readable while it is being offered.

    Struck here rather than in the page's script, like every other affordance: the script reveals
    and hides and never assigns a fill. A key carries the id of the building it stands for, so a
    page can tell which was pressed without knowing which hex this start roll put it on -- and the
    rotation is a layout sample, so that is not a thing any page should be made to know.
    """
    hex_size = map_layout["hex_size"]
    points = " ".join(f"{x:.2f},{y:.2f}" for x, y in hex_vertices(0.0, 0.0, hex_size))
    centers = hex_centers(map_layout)
    keys = []
    for placement in placements:
        building = placement["building"]
        if building is None:
            continue
        center_x, center_y = centers[placement["hex"]]
        keys.append(
            f'<polygon data-building-choice-key="{escape(str(building["id"]))}"'
            f' data-building-id="{escape(str(building["id"]))}"'
            f' points="{points}" transform="translate({center_x:.1f},{center_y:.1f})"'
            f' fill="none" pointer-events="all" stroke="{BUILDING_CHOICE_STROKE}"'
            f' stroke-width="{BUILDING_CHOICE_STROKE_WIDTH:g}" visibility="hidden"/>'
        )
    conversion_ids = set(conversion_building_ids)
    conversion_keys = []
    for placement in placements:
        building = placement["building"]
        if building is None or building["id"] not in conversion_ids:
            continue
        center_x, center_y = centers[placement["hex"]]
        conversion_keys.append(
            f'<polygon data-turn-step-building-id="{escape(str(building["id"]))}"'
            f' data-building-id="{escape(str(building["id"]))}"'
            ' data-turn-step-market="true" data-turn-step-offered="false"'
            f' points="{points}" transform="translate({center_x:.1f},{center_y:.1f})"'
            ' fill="none" pointer-events="all" visibility="hidden"/>'
        )
    return (
        f'<g id="setup-choice-keys">{"".join(keys)}</g>'
        f'<g id="conversion-choice-keys">{"".join(conversion_keys)}</g>'
    )


def building_choice_styles() -> str:
    """What one attribute on a key does to it, for any page that shows the building keys.

    Only the offered ones, and there is no container flag to pair it with. The stock keys have one
    because a page must say WHICH SEAT is being asked, and the seat keys have one because a page
    must say which boards are in the answer; there is one map, so "which map" is not a question and
    a flag for it would be a flag with one possible value. Reveal and a cursor -- no colour is named
    here or anywhere the script can reach.
    """
    return (
        '  [data-building-choice-key][data-turn-offered="true"] {\n'
        "    visibility: visible; cursor: pointer;\n"
        "  }\n"
    )


def render_ship_overlay(map_layout: dict, start_hex: str) -> str:
    """The ship marker alone: the other stops stay unmarked, the ship is moved onto them.

    Like a setup slot the marker is anchored on the hex centre, with the lift into the upper part
    of the hex baked into the icon, so both layers are positioned the same way.
    """
    start_x, start_y = hex_centers(map_layout)[start_hex]
    ship = render_ship_icon(
        0.0, ship_anchor_offset_y(map_layout), scale=ship_scale(map_layout), color=SHIP_COLOR
    )
    return f'<g id="ship-marker" transform="translate({start_x:.1f},{start_y:.1f})">{ship}</g>'


def player_discs(piety_layout: dict) -> list[dict]:
    """One disc per player, as the track itself seats them, so the page moves what it drew."""
    return seated_players(piety_layout, PIETY_VARIANT_ID)


def _with_overlay(svg: str, overlay: str) -> str:
    """Drop an extra fragment into a rendered SVG, drawn on top of what is already there."""
    closing = svg.rindex("</svg>")
    return f"{svg[:closing]}  {overlay}\n{svg[closing:]}"


def render_setup_map_svg(
    map_layout: dict,
    placements: list[dict],
    choice_keys: bool = False,
    ship_hex: str | None = None,
    conversion_building_ids: Sequence[str] = (),
) -> str:
    """The map with a round's setup on it: the fills under the map, the names and ship over it.

    The fills go under the map's own edges and labels, so a placed building recolours its hex
    instead of covering it. The names and the ship go on top of the finished map.

    This page and the composed game table both draw the map this way, so they draw it from here.

    `choice_keys` adds the hidden keys a page needs to ask which building is being constructed,
    struck last so a key lies over the hex it catches clicks for rather than under the label on it.
    Opt in for the reason the board's keys are: a page that will never ask should not carry a key
    per building that no stylesheet it has can reveal, which is not hidden markup but dead markup.

    `ship_hex` is where the ship stands. Left out it stands on the first slot, which is the setup
    page's whole subject and is where a game begins -- but is a guess on any board that has been
    played, and one that looks right for exactly as long as it takes to finish round one.
    """
    map_svg = render_map_svg(map_layout, render_setup_fill_layer(map_layout, placements))
    map_svg = _with_overlay(map_svg, render_setup_label_layer(map_layout, placements))
    map_svg = _with_overlay(
        map_svg,
        render_ship_overlay(map_layout, placements[0]["hex"] if ship_hex is None else ship_hex),
    )
    if choice_keys:
        map_svg = _with_overlay(
            map_svg,
            render_setup_choice_layer(
                map_layout,
                placements,
                conversion_building_ids=conversion_building_ids,
            ),
        )
    return map_svg


def render_player_controls(discs: list[dict]) -> str:
    rows = []
    for index, disc in enumerate(discs):
        rows.append(
            '      <div class="player-row">\n'
            f'        <span class="swatch" style="background: {disc["fill"]};'
            f' border-color: {disc["stroke"]};"></span>\n'
            f'        <span class="player-name">{escape(disc["label"])}</span>\n'
            f'        <span class="readout">piety <strong id="piety-value-{index}">0</strong>'
            "</span>\n"
            f'        <button type="button" data-player="{index}" data-piety-delta="1">+1 piety'
            "</button>\n"
            f'        <button type="button" data-player="{index}" data-piety-delta="-1">-1 piety'
            "</button>\n"
            "      </div>"
        )
    return "\n".join(rows)


ABBEY_PLACE_ID = "abbey"
ABBEY_PLACE_LABEL = "Abbey"


def available_setup_buildings(placements: list[dict]) -> list[dict]:
    """The buildings standing on the setup map, in slot order.

    Only `"building"` slots are for sale: empty slots have nothing on them and site slots hold a
    pilgrimage site. A building is keyed by its setup slot, not by the hex it happens to sit on,
    so changing the start roll moves it around the map without changing who owns it.
    """
    return [
        {
            "setupSlot": placement["round"],
            "buildingId": placement["building"]["id"],
            "name": placement["building"]["name"],
            "level": placement["building"]["level"],
            "label": placement["label"],
            "boughtContent": f"#{bought_content_id(placement['building'])}",
            "donatedContent": f"#{donated_content_id(placement['building']['level'])}",
        }
        for placement in placements
        if placement["building"] is not None
    ]


def donated_vp_by_level(donated_data: dict | list) -> dict[int, int]:
    """What a flipped building is worth: level 1 -> 2 VP, level 2 -> 4 VP, level 3 -> 6 VP."""
    return {int(tile["level"]): int(tile["vp"]) for tile in tiles_of(donated_data)}


def first_empty_building_slot(slots: Sequence[dict | None]) -> int | None:
    """The slot a bought building goes into, numbered from 1, or `None` on a full board."""
    for number, entry in enumerate(slots, start=1):
        if entry is None:
            return number
    return None


def can_donate_building_slot(slots: Sequence[dict | None], number: int) -> bool:
    """A slot can be flipped once, and only while a bought building is standing in it."""
    if not 1 <= number <= len(slots):
        return False
    entry = slots[number - 1]
    return entry is not None and not entry["donated"]


def building_ownership_state(board_layout: dict, placements: list[dict]) -> dict:
    """The state the buy and donate controls start from: everything still on the map, no owners.

    The page's JavaScript keeps its own copy of this shape and moves buildings between the two
    halves. `buy_building` and `donate_building` are the same two moves in Python, so the rules
    they follow can be tested without a browser.
    """
    return {
        "available": {
            str(building["setupSlot"]): building
            for building in available_setup_buildings(placements)
        },
        "players": {
            player["id"]: {"buildingSlots": [None] * int(board_layout["building_slot_count"])}
            for player in players_of(board_layout)
        },
    }


def buy_building(state: dict, player_id: str, setup_slot: int) -> int | None:
    """Take an available building off the map onto that player's first empty slot.

    Returns the slot it landed in, or `None` when the building is gone or the board is full.
    """
    building = state["available"].get(str(setup_slot))
    slots = state["players"][player_id]["buildingSlots"]
    number = first_empty_building_slot(slots)
    if building is None or number is None:
        return None
    slots[number - 1] = {
        "setupSlot": building["setupSlot"],
        "buildingId": building["buildingId"],
        "name": building["name"],
        "level": building["level"],
        "donated": False,
    }
    del state["available"][str(setup_slot)]
    return number


def donate_building(state: dict, player_id: str, number: int) -> bool:
    """Flip the bought building in that slot to its donated side. Says whether anything flipped."""
    slots = state["players"][player_id]["buildingSlots"]
    if not can_donate_building_slot(slots, number):
        return False
    slots[number - 1]["donated"] = True
    return True


def bought_content_id(building: dict) -> str:
    return f"bought-{building['id']}"


def donated_content_id(level: int) -> str:
    return f"donated-level-{level}"


def render_board_slot_fill(fill: str, size: float = BOARD_HEX_SIZE) -> str:
    """A building recolours the slot it stands in; it does not lay a tile on top of it.

    Like a setup slot on the map, the fill takes the slot's own hex shape and draws no border of
    its own: the board's dashed outline, drawn over this, stays the slot's only boundary.
    """
    return f'<path d="{hex_path_data(0.0, 0.0, size)}" fill="{fill}" stroke="none"/>'


def render_board_slot_building(building: dict, size: float = BOARD_HEX_SIZE) -> str:
    """A bought building filling a player-board slot, in the tile's colour and label.

    The label sits in the lower half of the slot, exactly as it does on a map hex, so a building
    reads the same whether it is still on the map or already bought.
    """
    return render_board_slot_fill(palette_for(building).fill, size) + render_building_label(
        building, size
    )


def render_board_slot_donated(tile: dict, size: float = BOARD_HEX_SIZE) -> str:
    """The donated side of a building: the slot in the level's colour, with the tile's star and VP.

    The donated tile's own border is left out for the same reason a bought building's is.
    """
    return render_board_slot_fill(palette_for(tile).fill, size) + render_donated_building_contents(
        tile, scale=size / DONATED_HEX_RADIUS
    )


def render_building_content_defs(placements: list[dict], donated_data: dict | list) -> str:
    """Every piece of content a board slot can show, defined once and drawn by reference.

    A slot's `use` element points at one of these, so buying or donating is a change of reference
    rather than a redraw, and the same building never has to be rendered four times over.
    """
    fragments = [
        f'<g id="{bought_content_id(placement["building"])}">'
        f"{render_board_slot_building(placement['building'])}</g>"
        for placement in placements
        if placement["building"] is not None
    ]
    fragments += [
        f'<g id="{donated_content_id(tile["level"])}">{render_board_slot_donated(tile)}</g>'
        for tile in tiles_of(donated_data)
    ]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" class="content-defs" width="0" height="0"'
        f' aria-hidden="true"><defs>{"".join(fragments)}</defs></svg>'
    )


def acolyte_places(board_layout: dict) -> list[tuple[str, str]]:
    """Everywhere an acolyte can stand: the Abbey, then the six role circles.

    The Village is deliberately not on this list. Cubes there are serfs, and the only way one
    leaves is the serf button, which turns it into an acolyte in the Abbey.
    """
    return [(ABBEY_PLACE_ID, ABBEY_PLACE_LABEL)] + [
        (role["id"], role["label"]) for role in board_layout["worker_roles"]
    ]


def render_serf_controls(board_layout: dict) -> str:
    return "\n".join(
        f'      <button type="button" data-serf-player="{player["id"]}">'
        f"Move serf to Abbey: {escape(player['label'])}</button>"
        for player in players_of(board_layout)
    )


def _options(choices: list[tuple[str, str]], selected: str) -> str:
    return "".join(
        f'<option value="{value}"{" selected" if value == selected else ""}>{escape(label)}'
        "</option>"
        for value, label in choices
    )


def render_acolyte_controls(board_layout: dict) -> str:
    """Pick a player, a source, and a target; the button moves one acolyte between them."""
    players = [(player["id"], player["label"]) for player in players_of(board_layout)]
    places = acolyte_places(board_layout)
    first_role = places[1][0]
    return (
        '      <div class="player-row">\n'
        '        <label class="player-name" for="acolyte-player">Player</label>\n'
        f'        <select id="acolyte-player">{_options(players, DEFAULT_PLAYER)}</select>\n'
        "      </div>\n"
        '      <div class="player-row">\n'
        '        <label class="player-name" for="acolyte-source">Source</label>\n'
        f'        <select id="acolyte-source">{_options(places, ABBEY_PLACE_ID)}</select>\n'
        "      </div>\n"
        '      <div class="player-row">\n'
        '        <label class="player-name" for="acolyte-target">Target</label>\n'
        f'        <select id="acolyte-target">{_options(places, first_role)}</select>\n'
        "      </div>\n"
        '      <button type="button" id="move-acolyte">Move acolyte</button>'
    )


def render_buy_controls(board_layout: dict, placements: list[dict]) -> str:
    """Pick a player and one of the buildings still on the map; the button buys it for them."""
    players = [(player["id"], player["label"]) for player in players_of(board_layout)]
    buildings = [
        (str(building["setupSlot"]), building["label"])
        for building in available_setup_buildings(placements)
    ]
    return (
        '      <div class="player-row">\n'
        '        <label class="player-name" for="buy-player">Player</label>\n'
        f'        <select id="buy-player">{_options(players, DEFAULT_PLAYER)}</select>\n'
        "      </div>\n"
        '      <div class="player-row">\n'
        '        <label class="player-name" for="buy-building">Building</label>\n'
        f'        <select id="buy-building">{_options(buildings, buildings[0][0])}</select>\n'
        "      </div>\n"
        '      <button type="button" id="buy-building-button">Buy building</button>'
    )


def render_donate_controls(board_layout: dict) -> str:
    """Pick a player and one of their six slots; the button flips what is standing in it."""
    players = [(player["id"], player["label"]) for player in players_of(board_layout)]
    slots = [
        (str(number), f"Slot {number}")
        for number in range(1, int(board_layout["building_slot_count"]) + 1)
    ]
    return (
        '      <div class="player-row">\n'
        '        <label class="player-name" for="donate-player">Player</label>\n'
        f'        <select id="donate-player">{_options(players, DEFAULT_PLAYER)}</select>\n'
        "      </div>\n"
        '      <div class="player-row">\n'
        '        <label class="player-name" for="donate-slot">Slot</label>\n'
        f'        <select id="donate-slot">{_options(slots, "1")}</select>\n'
        "      </div>\n"
        '      <button type="button" id="donate-building-button">Donate building</button>'
    )


def player_board_ui_state(board_layout: dict) -> dict:
    """The state the panel starts from: the default board for every player.

    This is the page's own state. It is never read back into the engine.
    """
    default = default_player_board_v2_state(board_layout)
    return {
        "players": {
            player["id"]: {
                "villageSerfs": default["village_serfs"],
                "abbeyAcolytes": default["abbey_acolytes"],
                "roles": dict(default["roles"]),
            }
            for player in players_of(board_layout)
        },
    }


def render_player_boards(board_layout: dict) -> str:
    """The four boards, each tagged so the page can move its cubes."""
    boards = []
    for player in players_of(board_layout):
        svg = render_player_board_v2_svg(board_layout, player, interactive=True)
        boards.append(
            f'    <div class="panel player-board" data-component="player-board-v2"'
            f' data-player="{player["id"]}" data-player-color="{player["color"]}">\n'
            f"      <h2>{escape(player['label'])} — {escape(player['color'])}</h2>\n"
            f'      <p class="readout" style="width: auto;">Village serfs'
            f' <strong data-readout="village">0</strong>, Abbey acolytes'
            f' <strong data-readout="abbey">0</strong>, acolytes on roles'
            f' <strong data-readout="roles">0</strong></p>\n'
            f'      <p class="slot-list" data-readout="buildings">No buildings bought yet.</p>\n'
            f"      {svg}\n"
            "    </div>"
        )
    return "\n".join(boards)


SETUP_SCRIPT = """
(function () {
  const data = JSON.parse(document.getElementById("setup-data").textContent);
  const edgePath = data.edgePath;
  const hexCenters = data.hexCenters;
  const startHexByRoll = data.startHexByRoll;
  const pietyPositions = data.pietyPositions;
  const players = data.players;

  let shipPosition = 0;
  let startRoll = data.startRoll;
  let path = rotatedPath(startRoll);
  const pietyValues = players.map(function () { return 0; });

  const shipMarker = document.getElementById("ship-marker");
  const shipReadout = document.getElementById("ship-position");
  const startHexReadout = document.getElementById("start-hex");
  // Scoped to the track: `data-player` is on the player boards and the buttons as well.
  const pietyTrack = document.querySelector('[data-component="piety-track-v2"]');
  // A slot has one group per layer — its fill and its label — and both carry the same slot number.
  const slotGroups = document.querySelectorAll("g[data-slot]");

  function rotatedPath(roll) {
    const offset = edgePath.indexOf(startHexByRoll[roll]);
    return edgePath.slice(offset).concat(edgePath.slice(0, offset));
  }

  function place(element, label) {
    const center = hexCenters[label];
    element.setAttribute("transform", "translate(" + center[0] + "," + center[1] + ")");
  }

  function renderShip() {
    place(shipMarker, path[shipPosition]);
    shipReadout.textContent = shipPosition + " / " + path[shipPosition];
  }

  function renderSlots() {
    Array.prototype.forEach.call(slotGroups, function (group) {
      place(group, path[Number(group.getAttribute("data-slot")) - 1]);
    });
    startHexReadout.textContent = startRoll + " / " + path[0];
  }

  function pietyDisc(playerId) {
    return pietyTrack.querySelector(
      '[data-player-disc="true"][data-player="' + playerId + '"]');
  }

  function renderPiety(index) {
    const value = pietyValues[index];
    const player = players[index];
    const disc = pietyDisc(player.id);
    disc.setAttribute("cx", (pietyPositions[value] + player.cxOffset).toFixed(1));
    disc.setAttribute("data-piety-position", value);
    document.getElementById("piety-value-" + index).textContent = value;
  }

  document.getElementById("advance-ship").addEventListener("click", function () {
    shipPosition = (shipPosition + 1) % path.length;
    renderShip();
  });

  document.getElementById("reset-ship").addEventListener("click", function () {
    shipPosition = 0;
    renderShip();
  });

  const rollButtons = document.querySelectorAll("button[data-start-roll]");
  Array.prototype.forEach.call(rollButtons, function (button) {
    button.addEventListener("click", function () {
      startRoll = Number(button.getAttribute("data-start-roll"));
      path = rotatedPath(startRoll);
      shipPosition = 0;
      Array.prototype.forEach.call(rollButtons, function (other) {
        other.classList.toggle("is-active", other === button);
      });
      renderSlots();
      renderShip();
    });
  });

  const pietyButtons = document.querySelectorAll("button[data-piety-delta]");
  Array.prototype.forEach.call(pietyButtons, function (button) {
    button.addEventListener("click", function () {
      const index = Number(button.getAttribute("data-player"));
      const delta = Number(button.getAttribute("data-piety-delta"));
      const bounded = Math.max(0, Math.min(pietyPositions.length - 1, pietyValues[index] + delta));
      pietyValues[index] = bounded;
      renderPiety(index);
    });
  });

  // Player boards. A cube is a serf in the Village and an acolyte once it reaches the Abbey or a
  // role circle. Every slot a cube can stand in is already drawn, so a move is a change of
  // opacity rather than a redraw.
  const boards = data.playerBoards;
  const boardState = boards.state;
  const acolytePlayer = document.getElementById("acolyte-player");
  const acolyteSource = document.getElementById("acolyte-source");
  const acolyteTarget = document.getElementById("acolyte-target");
  const moveAcolyteButton = document.getElementById("move-acolyte");
  const serfButtons = document.querySelectorAll("button[data-serf-player]");

  function boardElement(playerId) {
    return document.querySelector(
      '[data-component="player-board-v2"][data-player="' + playerId + '"]'
    );
  }

  function show(element, visible) {
    element.setAttribute("opacity", visible ? "1" : "0");
  }

  function acolytesAt(state, place) {
    return place === boards.abbeyId ? state.abbeyAcolytes : state.roles[place];
  }

  function setAcolytesAt(state, place, count) {
    if (place === boards.abbeyId) {
      state.abbeyAcolytes = count;
    } else {
      state.roles[place] = count;
    }
  }

  function capacityOf(place) {
    return place === boards.abbeyId ? boards.abbeyCapacity : boards.roleLimit;
  }

  function renderBoard(playerId) {
    const board = boardElement(playerId);
    const state = boardState.players[playerId];
    const cubesInArea = { village: state.villageSerfs, abbey: state.abbeyAcolytes };
    Object.keys(cubesInArea).forEach(function (area) {
      const slots = board.querySelectorAll('[data-token="' + area + '"]');
      Array.prototype.forEach.call(slots, function (slot) {
        show(slot, Number(slot.getAttribute("data-token-index")) < cubesInArea[area]);
      });
    });

    let onRoles = 0;
    boards.roles.forEach(function (role) {
      const count = state.roles[role];
      onRoles += count;
      const slots = board.querySelectorAll('[data-role="' + role + '"]');
      Array.prototype.forEach.call(slots, function (slot) {
        // One acolyte stands in the centred slot, two stand in the pair.
        show(slot, count === (slot.getAttribute("data-role-slot") === "single" ? 1 : 2));
      });
    });

    board.querySelector('[data-readout="village"]').textContent = state.villageSerfs;
    board.querySelector('[data-readout="abbey"]').textContent = state.abbeyAcolytes;
    board.querySelector('[data-readout="roles"]').textContent = onRoles;
  }

  function canMoveSerf(playerId) {
    const state = boardState.players[playerId];
    return state.villageSerfs > 0 && state.abbeyAcolytes < boards.abbeyCapacity;
  }

  function canMoveAcolyte() {
    const state = boardState.players[acolytePlayer.value];
    const source = acolyteSource.value;
    const target = acolyteTarget.value;
    return (
      source !== target &&
      acolytesAt(state, source) > 0 &&
      acolytesAt(state, target) < capacityOf(target)
    );
  }

  function renderPlayerBoards() {
    Object.keys(boardState.players).forEach(renderBoard);
    Array.prototype.forEach.call(serfButtons, function (button) {
      button.disabled = !canMoveSerf(button.getAttribute("data-serf-player"));
    });
    moveAcolyteButton.disabled = !canMoveAcolyte();
  }

  Array.prototype.forEach.call(serfButtons, function (button) {
    button.addEventListener("click", function () {
      const playerId = button.getAttribute("data-serf-player");
      if (!canMoveSerf(playerId)) { return; }
      const state = boardState.players[playerId];
      state.villageSerfs -= 1;
      state.abbeyAcolytes += 1;
      renderPlayerBoards();
    });
  });

  moveAcolyteButton.addEventListener("click", function () {
    if (!canMoveAcolyte()) { return; }
    const state = boardState.players[acolytePlayer.value];
    const source = acolyteSource.value;
    const target = acolyteTarget.value;
    setAcolytesAt(state, source, acolytesAt(state, source) - 1);
    setAcolytesAt(state, target, acolytesAt(state, target) + 1);
    renderPlayerBoards();
  });

  [acolytePlayer, acolyteSource, acolyteTarget].forEach(function (select) {
    select.addEventListener("change", renderPlayerBoards);
  });

  // Buildings. One on the map is available, one in a player-board slot is bought, and a bought
  // one that has been flipped is donated. A slot shows its building by pointing at content the
  // page already defined, so buying and donating only change a reference.
  const ownership = data.buildingOwnership;
  const ownershipState = ownership.state;
  const buyPlayer = document.getElementById("buy-player");
  const buyBuilding = document.getElementById("buy-building");
  const buyButton = document.getElementById("buy-building-button");
  const donatePlayer = document.getElementById("donate-player");
  const donateSlot = document.getElementById("donate-slot");
  const donateButton = document.getElementById("donate-building-button");

  function buildingSlots(playerId) {
    return ownershipState.players[playerId].buildingSlots;
  }

  function firstEmptyBuildingSlot(playerId) {
    const slots = buildingSlots(playerId);
    for (let index = 0; index < slots.length; index += 1) {
      if (slots[index] === null) { return index + 1; }
    }
    return 0;
  }

  function canDonate(playerId, number) {
    const entry = buildingSlots(playerId)[number - 1];
    return Boolean(entry) && !entry.donated;
  }

  function describeSlot(number, entry) {
    const vp = ownership.donatedVpByLevel[entry.level];
    return "Slot " + number + " " + entry.name + (entry.donated ? ", donated " + vp + " VP" : "");
  }

  function renderMapBuildings() {
    // A bought building leaves the map: its recoloured hex and its label both go, and the map's
    // own hex is underneath them, unchanged. Sites and empty slots are not for sale.
    const overlays = document.querySelectorAll(
      "#setup-fills g[data-building-id], #setup-labels g[data-building-id]"
    );
    Array.prototype.forEach.call(overlays, function (overlay) {
      const slot = overlay.getAttribute("data-slot");
      show(overlay, Object.prototype.hasOwnProperty.call(ownershipState.available, slot));
    });
  }

  function renderBuildingSlots(playerId) {
    const board = boardElement(playerId);
    const summary = [];
    buildingSlots(playerId).forEach(function (entry, index) {
      const number = index + 1;
      const group = board.querySelector('[data-player-board-slot="' + number + '"]');
      const content = group.querySelector("[data-building-content]");
      const donated = Boolean(entry) && entry.donated;
      group.setAttribute(
        "data-building-slot-state", entry === null ? "empty" : (donated ? "donated" : "bought")
      );
      group.setAttribute("data-building-id", entry === null ? "" : entry.buildingId);
      group.setAttribute("data-setup-slot", entry === null ? "" : entry.setupSlot);
      group.setAttribute("data-donated", donated ? "true" : "false");
      // The dashed outline is drawn over the content and never moves, so a filled slot keeps the
      // same border an empty one has.
      show(content, entry !== null);
      if (entry !== null) {
        content.setAttribute("href", donated
          ? ownership.donatedContent[entry.level]
          : ownership.boughtContent[entry.buildingId]);
        summary.push(describeSlot(number, entry));
      }
    });
    board.querySelector('[data-readout="buildings"]').textContent =
      summary.length ? summary.join(". ") : "No buildings bought yet.";
  }

  function renderOwnership() {
    Object.keys(ownershipState.players).forEach(renderBuildingSlots);
    renderMapBuildings();
    buyButton.disabled = !(buyBuilding.value && firstEmptyBuildingSlot(buyPlayer.value));
    donateButton.disabled = !canDonate(donatePlayer.value, Number(donateSlot.value));
  }

  buyButton.addEventListener("click", function () {
    const playerId = buyPlayer.value;
    const setupSlot = buyBuilding.value;
    const building = ownershipState.available[setupSlot];
    const number = firstEmptyBuildingSlot(playerId);
    if (!building || !number) { return; }
    buildingSlots(playerId)[number - 1] = {
      setupSlot: building.setupSlot,
      buildingId: building.buildingId,
      name: building.name,
      level: building.level,
      donated: false
    };
    delete ownershipState.available[setupSlot];
    const option = buyBuilding.querySelector('option[value="' + setupSlot + '"]');
    if (option) { option.remove(); }
    renderOwnership();
  });

  donateButton.addEventListener("click", function () {
    const playerId = donatePlayer.value;
    const number = Number(donateSlot.value);
    if (!canDonate(playerId, number)) { return; }
    buildingSlots(playerId)[number - 1].donated = true;
    renderOwnership();
  });

  [buyPlayer, buyBuilding, donatePlayer, donateSlot].forEach(function (select) {
    select.addEventListener("change", renderOwnership);
  });

  renderSlots();
  renderShip();
  players.forEach(function (_, index) { renderPiety(index); });
  renderPlayerBoards();
  renderOwnership();
})();
"""


def render_start_roll_controls(start_roll: int) -> str:
    buttons = []
    for roll in sorted(START_HEX_BY_ROLL):
        active = " is-active" if roll == start_roll else ""
        buttons.append(
            f'      <button type="button" class="roll-button{active}"'
            f' data-start-roll="{roll}">{roll}</button>'
        )
    return "\n".join(buttons)


def render_game_setup_html(
    map_layout: dict,
    piety_layout: dict,
    piety_config: dict,
    catalog: dict,
    site_data: dict | list,
    board_layout: dict,
    donated_data: dict | list,
    duty_wheel_layout: dict,
) -> str:
    variant = variant_by_id(piety_layout, PIETY_VARIANT_ID)
    discs = player_discs(piety_layout)

    # The track draws its own discs on the starting space, already tagged with whose they are, so
    # the page moves those rather than laying a second set of circles over them.
    track_svg = render_piety_track_v2_svg(piety_layout, piety_config, PIETY_VARIANT_ID)

    placements = setup_placements(DEFAULT_START_ROLL, catalog, site_data)
    occupied = [placement["round"] for placement in placements if placement["kind"] != "empty"]
    centers = hex_centers(map_layout)
    available = available_setup_buildings(placements)
    donated_vp = donated_vp_by_level(donated_data)

    map_svg = render_setup_map_svg(map_layout, placements)

    setup_data = json.dumps(
        {
            "edgePath": list(EDGE_HEX_PATH),
            "hexCenters": {label: [round(x, 1), round(y, 1)] for label, (x, y) in centers.items()},
            "startHexByRoll": {str(roll): hex_ for roll, hex_ in START_HEX_BY_ROLL.items()},
            "startRoll": DEFAULT_START_ROLL,
            "occupiedSlots": occupied,
            "pietyPositions": [
                round(position_center_x(piety_layout, index), 1)
                for index in range(piety_layout["track"]["position_count"])
            ],
            "players": [{"id": disc["id"], "cxOffset": disc["cx_offset"]} for disc in discs],
            "playerBoards": {
                "abbeyId": ABBEY_PLACE_ID,
                "abbeyCapacity": token_slot_count(board_layout),
                "roleLimit": ROLE_ACOLYTE_LIMIT,
                "roles": [role["id"] for role in board_layout["worker_roles"]],
                "state": player_board_ui_state(board_layout),
            },
            "buildingOwnership": {
                "slotCount": board_layout["building_slot_count"],
                "donatedVpByLevel": donated_vp,
                "boughtContent": {
                    building["buildingId"]: building["boughtContent"] for building in available
                },
                "donatedContent": {level: f"#{donated_content_id(level)}" for level in donated_vp},
                "state": building_ownership_state(board_layout, placements),
            },
        }
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pilgrim — Game Setup (generated)</title>
<style>
  body {{
    margin: 0;
    background: {PAGE_BACKGROUND};
    color: #F2EEDF;
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
    margin: 0 0 2px;
  }}
  h2 {{
    font-size: 13px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #A8A296;
    font-weight: 600;
    margin: 0 0 8px;
  }}
  p.subtitle {{
    color: #A8A296;
    font-size: 14px;
    margin: 0 0 18px;
    text-align: center;
    max-width: 720px;
  }}
  .setup-layout {{
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: center;
    gap: 14px;
    width: min(1560px, 96vw);
  }}
  .setup-main {{ flex: 1 1 700px; max-width: 1014px; min-width: 0; }}
  .player-board-panel {{ flex: 1 1 340px; max-width: 460px; min-width: 0; }}
  .board-column, .controls {{
    width: 100%;
  }}
  .panel {{
    background: {PAGE_BACKGROUND};
    border: 1px solid #333333;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.5);
    padding: 10px;
    margin-bottom: 14px;
  }}
  .panel svg {{ display: block; width: 100%; height: auto; }}
  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
  }}
  .controls .panel {{ flex: 1 1 320px; margin-bottom: 0; }}
  .player-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0;
  }}
  .swatch {{
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 1px solid;
    box-sizing: border-box;
  }}
  .player-name {{ width: 70px; font-size: 14px; }}
  .readout {{ width: 78px; color: #A8A296; font-size: 13px; }}
  button {{
    background: #1A1A1A;
    color: #F2EEDF;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
  }}
  button:hover {{ background: #2A2A2A; }}
  .roll-button {{ min-width: 34px; }}
  .roll-button.is-active {{
    background: #F2EEDF;
    color: #1A1A1A;
    border-color: #F2EEDF;
  }}
  .slot-list {{
    color: #A8A296;
    font-size: 13px;
    line-height: 1.5;
    margin: 8px 0 0;
  }}
  .board-controls button {{ margin: 0 6px 6px 0; }}
  .board-controls button[disabled] {{
    opacity: 0.45;
    cursor: default;
  }}
  select {{
    background: #1A1A1A;
    color: #F2EEDF;
    border: 1px solid #555555;
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 13px;
    font-family: inherit;
  }}
  .player-board h2 {{ margin-bottom: 2px; }}
  .player-board .readout {{ margin: 0 0 8px; }}
  .duty-wheel-panel {{ width: min(1560px, 96vw); }}
  /* The wheel is a tall board, so it keeps its own width instead of filling the panel. */
  .duty-wheel-panel svg {{ width: min(100%, 760px); margin: 0 auto; }}
{DUTY_WHEEL_CONTROL_STYLES}  .duty-wheel-controls {{ margin: 4px 0 10px; }}
</style>
</head>
<body>
  <h1>{TITLE}</h1>
  <p class="subtitle">{escape(SUBTITLE)}</p>
  <div class="setup-layout">
  <div class="setup-main">
  <div class="board-column">
    <div class="panel" data-piety-variant="{PIETY_VARIANT_ID}">
      <h2>{escape(variant["label"])}</h2>
      {track_svg}
    </div>
    <div class="panel">
      <h2>Map with setup slots and ship marker</h2>
      {map_svg}
    </div>
  </div>
  <div class="controls">
    <div class="panel">
      <h2>Setup slots</h2>
      <p class="readout" style="width: auto;">Start roll
        <strong id="start-hex">{DEFAULT_START_ROLL} / {placements[0]["hex"]}</strong></p>
{render_start_roll_controls(DEFAULT_START_ROLL)}
      <p class="slot-list">{len(occupied)} of {len(SETUP_SLOTS)} slots are taken; the rest stay
        empty. Buildings recolour their hex in the catalog palette and the four sites in
        pilgrimage site orange, under the map's own borders and labels. The sites are always the
        first four in {SITE_DATA_FILENAME}: they are not drawn at random yet.</p>
    </div>
    <div class="panel">
      <h2>Ship controls</h2>
      <p class="readout" style="width: auto;">Ship position
        <strong id="ship-position">0 / {placements[0]["hex"]}</strong></p>
      <p class="readout" style="width: auto;">{len(EDGE_HEX_PATH)} edge hexes, skipping
        {", ".join(SKIPPED_HEXES)}</p>
      <button type="button" id="advance-ship">Advance ship</button>
      <button type="button" id="reset-ship">Reset ship</button>
    </div>
    <div class="panel">
      <h2>Player piety controls</h2>
{render_player_controls(discs)}
    </div>
  </div>
  </div>
  <div class="player-board-panel">
    <div class="panel board-controls">
      <h2>Player board v2 — serfs</h2>
      <p class="slot-list">A serf leaving the Village becomes an acolyte in the Abbey, which
        holds {token_slot_count(board_layout)} cubes: the button stops once those slots are
        full.</p>
{render_serf_controls(board_layout)}
    </div>
    <div class="panel board-controls">
      <h2>Player board v2 — buy a building</h2>
      <p class="slot-list">An available building is one still standing on the setup map. Buying it
        takes it off the map and puts it in the player's first empty building slot, where it stays
        however the start roll rotates the map afterwards.</p>
{render_buy_controls(board_layout, placements)}
    </div>
    <div class="panel board-controls">
      <h2>Player board v2 — donate a building</h2>
      <p class="slot-list">Donating flips a bought building in slots
        1-{board_layout["building_slot_count"]} to its donated side, which is worth
        {donated_vp[1]}, {donated_vp[2]}, or {donated_vp[3]} VP by level. It stays in its slot and
        cannot be flipped twice.</p>
{render_donate_controls(board_layout)}
    </div>
    <div class="panel board-controls">
      <h2>Player board v2 — acolytes</h2>
      <p class="slot-list">Acolytes move between the Abbey and the role circles. A role circle
        holds at most {ROLE_ACOLYTE_LIMIT}: one sits centred, two sit side by side. The Village is
        not a source or a target here.</p>
{render_acolyte_controls(board_layout)}
    </div>
{render_player_boards(board_layout)}
  </div>
  </div>
  <div class="panel duty-wheel-panel">
    <h2>Duty wheel</h2>
    <p class="slot-list">The duty tiles, kept off the map so both stay readable. The purple disc
      is the Merchant token and the icons in the capsules are Tithe tokens. The buttons cycle
      sample Duty tile setups, walk the Merchant clockwise around the eight duty tiles — the City
      is not on his path — and switch the cube tallies between the two-, three-, and four-player
      views. Visual/debug only, like the rest of this page: no GameState, no rules, and no sow
      animation.</p>
{render_duty_wheel_panel(duty_wheel_layout)}
  </div>
  {render_building_content_defs(placements, donated_data)}
  <script id="setup-data" type="application/json">{setup_data}</script>
  <script>{SETUP_SCRIPT}</script>
{render_duty_wheel_controls_script(duty_wheel_layout)}</body>
</html>
"""


def write_game_setup_page(
    output_path: Path | None = None,
    *,
    map_layout_path: Path | None = None,
    piety_layout_path: Path | None = None,
    piety_config_path: Path | None = None,
    catalog_path: Path | None = None,
    site_data_path: Path | None = None,
    board_layout_path: Path | None = None,
    donated_data_path: Path | None = None,
    duty_wheel_layout_path: Path | None = None,
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    html = render_game_setup_html(
        load_map_layout(map_layout_path),
        load_piety_track_v2_layout(piety_layout_path),
        load_piety_config(piety_config_path),
        load_building_catalog(catalog_path),
        load_pilgrimage_sites(site_data_path),
        load_player_boards_v2_layout(board_layout_path),
        load_donated_building_tiles(donated_data_path),
        load_duty_wheel_layout(duty_wheel_layout_path),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination


def main() -> None:
    written = write_game_setup_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
