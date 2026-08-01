"""Write the generated game setup debug page.

The page composes four existing renderers — the map, the 3-4 player piety track, the building
tiles, and the pilgrimage sites — and adds a ship marker plus one piety disc per player, moved by
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
    TILE_TEXT_FONT_SIZE,
    TILE_TEXT_LINE_HEIGHT,
    TILE_TEXT_TOP_OFFSET,
    load_building_catalog,
    palette_for,
    tile_text_lines,
)
from tools.ui_debug.render_map import (  # noqa: E402
    hex_center,
    hex_vertices,
    label_to_coord,
    load_map_layout,
    render_map_svg,
)
from tools.ui_debug.render_piety_track import (  # noqa: E402
    load_piety_config,
    load_piety_track_layout,
    piety_vp_values,
    position_center_x,
    render_piety_track_variant_svg,
    track_geometry,
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
    DEFAULT_FIRST_PLAYER,
    ROLE_ACOLYTE_LIMIT,
    default_player_board_v2_state,
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
    "Generated map with the 3-4 player piety track above it, one hard-coded example setup laid "
    "out on the edge hexes, and the four player boards beside them. The start roll, ship, piety, "
    "and player board buttons move markers and cubes only: no GameState, no rules, no actions."
)
PAGE_BACKGROUND = "#000000"

# The setup page has four players, so it uses the 3-4 player track: two token rows on the
# starting space, one disc per player, in the token order white, red, yellow, blue.
PIETY_VARIANT_ID = "three_four_player"

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


def render_setup_building_label(map_layout: dict, building: dict) -> str:
    """The tile's own wrapped label, at the tile's own proportions, in the lower half of the hex.

    The map hex is smaller than a building tile, so the tile's text geometry is scaled between the
    two rather than restated. That keeps the upper half free for the hex label and the ship.
    """
    palette = palette_for(building)
    ratio = _tile_ratio(map_layout)

    lines = []
    for index, line in enumerate(tile_text_lines(building)):
        text_y = ratio * (TILE_TEXT_TOP_OFFSET + index * TILE_TEXT_LINE_HEIGHT)
        lines.append(
            f'<text x="0" y="{text_y:.1f}" text-anchor="middle"'
            ' font-family="Helvetica, Arial, sans-serif"'
            f' font-size="{ratio * TILE_TEXT_FONT_SIZE:.1f}" font-weight="600"'
            f' fill="{palette.stroke}">{escape(line)}</text>'
        )
    return "".join(lines)


def _placed(map_layout: dict, placement: dict, class_name: str, body: str) -> str:
    """One slot's share of a layer, moved as a whole when the start roll changes."""
    center_x, center_y = hex_centers(map_layout)[placement["hex"]]
    return (
        f'<g class="{class_name}" data-slot="{placement["round"]}"'
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


def player_discs(piety_layout: dict, variant: dict) -> list[dict]:
    """One disc per player, taking colour and start offset from the track's own token data."""
    geometry = track_geometry(piety_layout, variant["token_rows"])
    offset = geometry["token_offset"]
    return [
        {
            "label": f"Player {index + 1}",
            "fill": token["fill"],
            "stroke": token["stroke"],
            "cx_offset": token["col"] * offset,
            "cy": geometry["tokens_cy"] + token["row"] * offset,
        }
        for index, token in enumerate(variant["tokens"])
    ]


def render_piety_disc_overlay(piety_layout: dict, discs: list[dict], start_position: int) -> str:
    token = piety_layout["track"]["token"]
    start_x = position_center_x(piety_layout, start_position)
    return "".join(
        f'<circle id="piety-disc-{index}" cx="{start_x + disc["cx_offset"]:.1f}"'
        f' cy="{disc["cy"]:.1f}" r="{token["radius"]}" fill="{disc["fill"]}"'
        f' stroke="{disc["stroke"]}" stroke-width="{token["stroke_width"]}"/>'
        for index, disc in enumerate(discs)
    )


def _with_overlay(svg: str, overlay: str) -> str:
    """Drop an extra fragment into a rendered SVG, drawn on top of what is already there."""
    closing = svg.rindex("</svg>")
    return f"{svg[:closing]}  {overlay}\n{svg[closing:]}"


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


def acolyte_places(board_layout: dict) -> list[tuple[str, str]]:
    """Everywhere an acolyte can stand: the Abbey, then the six role circles.

    The Village is deliberately not on this list. Cubes there are serfs, and the only way one
    leaves is the serf button, which turns it into an acolyte in the Abbey.
    """
    return [(ABBEY_PLACE_ID, ABBEY_PLACE_LABEL)] + [
        (role["id"], role["label"]) for role in board_layout["worker_roles"]
    ]


def render_first_player_controls(board_layout: dict) -> str:
    return "\n".join(
        f'      <button type="button" data-first-player="{player["id"]}">'
        f"Move first player marker to {escape(player['label'])}</button>"
        for player in players_of(board_layout)
    )


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
        f'        <select id="acolyte-player">{_options(players, DEFAULT_FIRST_PLAYER)}</select>\n'
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


def player_board_ui_state(board_layout: dict) -> dict:
    """The state the panel starts from: the default board for every player, marker on player one.

    This is the page's own state. It is never read back into the engine.
    """
    default = default_player_board_v2_state(board_layout)
    return {
        "firstPlayer": DEFAULT_FIRST_PLAYER,
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
    """The four boards, each tagged so the page can move its cubes and its marker."""
    boards = []
    for player in players_of(board_layout):
        svg = render_player_board_v2_svg(
            board_layout,
            player,
            include_first_player_marker=player["id"] == DEFAULT_FIRST_PLAYER,
            interactive=True,
        )
        boards.append(
            f'    <div class="panel player-board" data-component="player-board-v2"'
            f' data-player="{player["id"]}" data-player-color="{player["color"]}">\n'
            f"      <h2>{escape(player['label'])} — {escape(player['color'])}</h2>\n"
            f'      <p class="readout" style="width: auto;">Village serfs'
            f' <strong data-readout="village">0</strong>, Abbey acolytes'
            f' <strong data-readout="abbey">0</strong>, acolytes on roles'
            f' <strong data-readout="roles">0</strong></p>\n'
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

  function renderPiety(index) {
    const value = pietyValues[index];
    const disc = document.getElementById("piety-disc-" + index);
    disc.setAttribute("cx", (pietyPositions[value] + players[index].cxOffset).toFixed(1));
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

    const marker = board.querySelector("[data-first-player-marker]");
    const hasMarker = boardState.firstPlayer === playerId;
    marker.setAttribute("data-first-player-marker", hasMarker ? "true" : "false");
    show(marker, hasMarker);

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

  const firstPlayerButtons = document.querySelectorAll("button[data-first-player]");
  Array.prototype.forEach.call(firstPlayerButtons, function (button) {
    button.addEventListener("click", function () {
      boardState.firstPlayer = button.getAttribute("data-first-player");
      renderPlayerBoards();
    });
  });

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

  renderSlots();
  renderShip();
  players.forEach(function (_, index) { renderPiety(index); });
  renderPlayerBoards();
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
) -> str:
    variant = variant_by_id(piety_layout, PIETY_VARIANT_ID)
    vp_values = piety_vp_values(piety_config)
    start_position = piety_layout["track"]["token_position"]
    discs = player_discs(piety_layout, variant)

    # The discs are the movable copy of the starting tokens, so the track is drawn without its
    # static ones instead of stacking two sets of circles on the starting space.
    track_svg = render_piety_track_variant_svg(piety_layout, vp_values, {**variant, "tokens": []})
    track_svg = _with_overlay(
        track_svg, render_piety_disc_overlay(piety_layout, discs, start_position)
    )

    placements = setup_placements(DEFAULT_START_ROLL, catalog, site_data)
    occupied = [placement["round"] for placement in placements if placement["kind"] != "empty"]
    centers = hex_centers(map_layout)

    # The fills go under the map's own edges and labels, so a placed building recolours its hex
    # instead of covering it. The names and the ship go on top of the finished map.
    map_svg = render_map_svg(map_layout, render_setup_fill_layer(map_layout, placements))
    map_svg = _with_overlay(map_svg, render_setup_label_layer(map_layout, placements))
    map_svg = _with_overlay(map_svg, render_ship_overlay(map_layout, placements[0]["hex"]))

    setup_data = json.dumps(
        {
            "edgePath": list(EDGE_HEX_PATH),
            "hexCenters": {label: [round(x, 1), round(y, 1)] for label, (x, y) in centers.items()},
            "startHexByRoll": {str(roll): hex_ for roll, hex_ in START_HEX_BY_ROLL.items()},
            "startRoll": DEFAULT_START_ROLL,
            "occupiedSlots": occupied,
            "pietyPositions": [
                round(position_center_x(piety_layout, index), 1) for index in range(len(vp_values))
            ],
            "players": [{"cxOffset": disc["cx_offset"]} for disc in discs],
            "playerBoards": {
                "abbeyId": ABBEY_PLACE_ID,
                "abbeyCapacity": token_slot_count(board_layout),
                "roleLimit": ROLE_ACOLYTE_LIMIT,
                "roles": [role["id"] for role in board_layout["worker_roles"]],
                "state": player_board_ui_state(board_layout),
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
      <h2>Player board v2 — first player marker</h2>
{render_first_player_controls(board_layout)}
    </div>
    <div class="panel board-controls">
      <h2>Player board v2 — serfs</h2>
      <p class="slot-list">A serf leaving the Village becomes an acolyte in the Abbey, which
        holds {token_slot_count(board_layout)} cubes: the button stops once those slots are
        full.</p>
{render_serf_controls(board_layout)}
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
  <script id="setup-data" type="application/json">{setup_data}</script>
  <script>{SETUP_SCRIPT}</script>
</body>
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
) -> Path:
    destination = default_output_path() if output_path is None else Path(output_path)
    html = render_game_setup_html(
        load_map_layout(map_layout_path),
        load_piety_track_layout(piety_layout_path),
        load_piety_config(piety_config_path),
        load_building_catalog(catalog_path),
        load_pilgrimage_sites(site_data_path),
        load_player_boards_v2_layout(board_layout_path),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return destination


def main() -> None:
    written = write_game_setup_page()
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
