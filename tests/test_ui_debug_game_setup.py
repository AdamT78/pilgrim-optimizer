import json
import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_game_setup import (
    DEFAULT_START_ROLL,
    EDGE_HEX_PATH,
    PIETY_VARIANT_ID,
    SETUP_SLOTS,
    SHIP_COLOR,
    SHIP_POSITION_COUNT,
    SKIPPED_HEXES,
    START_HEX_BY_ROLL,
    acolyte_places,
    available_setup_buildings,
    building_by_name,
    building_ownership_state,
    buy_building,
    can_donate_building_slot,
    default_output_path,
    donate_building,
    donated_vp_by_level,
    first_empty_building_slot,
    hex_centers,
    parse_setup_building_label,
    parse_setup_site_label,
    player_board_ui_state,
    render_board_slot_building,
    render_board_slot_donated,
    render_board_slot_fill,
    render_setup_building_fill,
    render_setup_building_label,
    render_setup_site_fill,
    rotated_edge_path,
    setup_placements,
    ship_anchor_offset_y,
    ship_scale,
    write_game_setup_page,
)
from tools.ui_debug.render_buildings import (
    COLOR_GROUP_PALETTES,
    load_building_catalog,
    render_building_tile,
    tile_text_lines,
)
from tools.ui_debug.render_donated_buildings import (
    STAR_FILL,
    STAR_STROKE,
    load_donated_building_tiles,
    tiles_of,
)
from tools.ui_debug.render_map import (
    hex_center,
    hex_vertices,
    label_to_coord,
    load_map_layout,
    render_map_svg,
)
from tools.ui_debug.render_piety_track import (
    load_piety_config,
    load_piety_track_layout,
    piety_vp_values,
    position_center_x,
    track_geometry,
    variant_by_id,
)
from tools.ui_debug.render_pilgrimage_sites import (
    SITE_FILL,
    SITE_STROKE,
    load_pilgrimage_sites,
    sites_of,
)
from tools.ui_debug.render_player_boards_v2 import (
    BUILDING_SLOT_DASH_ARRAY,
    DEFAULT_FIRST_PLAYER,
    ROLE_ACOLYTE_LIMIT,
    building_slot_centers,
    default_player_board_v2_state,
    hex_path_data,
    load_player_boards_v2_layout,
    players_of,
    render_player_board_v2_svg,
    token_slot_count,
)
from tools.ui_debug.render_player_boards_v2 import HEX_SIZE as BOARD_HEX_SIZE
from tools.ui_debug.render_ship_marker import HULL_OUTLINE, MASTS, render_ship_icon

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
GENERATOR_SCRIPT = UI_DEBUG_DIR / "generate_game_setup.py"
INDEX_HTML = UI_DEBUG_DIR / "index.html"

TITLE = "PILGRIM — Game Setup Debug View"
PLAYER_LABELS = ("Player 1", "Player 2", "Player 3", "Player 4")


@pytest.fixture(scope="module")
def page(tmp_path_factory: pytest.TempPathFactory) -> str:
    output = tmp_path_factory.mktemp("game_setup") / "game_setup.html"
    return write_game_setup_page(output).read_text(encoding="utf-8")


def _setup_data(page: str) -> dict:
    match = re.search(r'<script id="setup-data" type="application/json">(.*?)</script>', page, re.S)
    assert match is not None
    return json.loads(match.group(1))


def test_generator_script_exists() -> None:
    assert GENERATOR_SCRIPT.is_file()
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "game_setup.html"


def test_generator_writes_the_page_to_a_temp_path(tmp_path: Path) -> None:
    written = write_game_setup_page(tmp_path / "nested" / "game_setup.html")

    assert written == tmp_path / "nested" / "game_setup.html"
    assert written.is_file()
    assert TITLE in written.read_text(encoding="utf-8")


def test_page_shows_the_title_and_both_kinds_of_control(page: str) -> None:
    assert TITLE in page
    assert "Advance ship" in page
    assert "Reset ship" in page
    for label in PLAYER_LABELS:
        assert label in page
    assert page.count("+1 piety") == len(PLAYER_LABELS)
    assert page.count("-1 piety") == len(PLAYER_LABELS)


def test_page_carries_its_own_debug_state(page: str) -> None:
    assert "let shipPosition = 0;" in page
    assert "pietyValues" in page


def test_page_embeds_the_generated_map_svg(page: str) -> None:
    """The map comes from the renderer, not from copied prototype HTML.

    The setup overlay is inserted into the map rather than drawn over it, so the check is that
    every element the renderer emits still reaches the page untouched.
    """
    plain = render_map_svg(load_map_layout())

    assert "setup" not in plain, "the standalone map is drawn without any setup overlay"
    for element in plain.splitlines()[1:-1]:
        assert element.strip() in page


def _setup_area(page: str) -> str:
    """The map/piety half of the page, without the player boards standing next to it."""
    left, marker, _ = page.partition('<div class="player-board-panel">')
    assert marker, "the page no longer has a player-board panel"
    return left


def _piety_panel(page: str) -> str:
    pattern = rf'<div class="panel" data-piety-variant="{PIETY_VARIANT_ID}">.*?</div>'
    match = re.search(pattern, page, re.S)
    assert match is not None
    return match.group(0)


def test_page_embeds_the_rendered_piety_track(page: str) -> None:
    """One VP star per piety position, labelled from the piety config."""
    vp_values = piety_vp_values(load_piety_config())
    panel = _piety_panel(page)

    for vp in vp_values:
        assert f">{vp}</text>" in panel
    stars = re.findall(rf'<path d="M [^"]*" fill="{STAR_FILL}"', panel)
    assert len(stars) == len(vp_values)


def test_page_uses_the_three_four_player_track_only(page: str) -> None:
    layout = load_piety_track_layout()

    assert f'data-piety-variant="{PIETY_VARIANT_ID}"' in page
    assert variant_by_id(layout, PIETY_VARIANT_ID)["label"] in page
    # One fused strip rect means one track strip was drawn.
    assert _piety_panel(page).count('<rect x="0" y="0"') == 1


def test_page_does_not_show_the_two_player_track(page: str) -> None:
    layout = load_piety_track_layout()

    assert variant_by_id(layout, "two_player")["label"] not in page
    assert "two_player" not in page


def test_player_discs_use_the_track_token_colours(page: str) -> None:
    layout = load_piety_track_layout()
    variant = variant_by_id(layout, PIETY_VARIANT_ID)
    tokens = variant["tokens"]
    offset = track_geometry(layout, variant["token_rows"])["token_offset"]
    start_x = position_center_x(layout, layout["track"]["token_position"])

    assert len(tokens) == len(PLAYER_LABELS)
    for index, token in enumerate(tokens):
        disc = re.search(rf'<circle id="piety-disc-{index}"[^>]*/>', page)
        assert disc is not None
        assert f'fill="{token["fill"]}"' in disc.group(0)
        assert f'cx="{start_x + token["col"] * offset:.1f}"' in disc.group(0)


def test_piety_positions_in_the_script_match_the_renderer(page: str) -> None:
    layout = load_piety_track_layout()
    expected = [
        round(position_center_x(layout, index), 1)
        for index in range(layout["track"]["position_count"])
    ]

    assert _setup_data(page)["pietyPositions"] == expected


def _hex_distance(first: tuple[int, int], second: tuple[int, int]) -> int:
    q, r = first[0] - second[0], first[1] - second[1]
    return (abs(q) + abs(r) + abs(q + r)) // 2


def test_ship_path_covers_the_edge_hexes_except_the_skipped_ones() -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)
    radius = layout["edge_length"] - 1

    assert len(EDGE_HEX_PATH) == SHIP_POSITION_COUNT == 26
    assert len(set(EDGE_HEX_PATH)) == len(EDGE_HEX_PATH)
    assert EDGE_HEX_PATH[0] == "J3"
    # Clockwise: J3 leads to J2, not back up the other side of the board to K4.
    assert EDGE_HEX_PATH[1] == "J2"
    assert EDGE_HEX_PATH[-1] == "K4"
    for label in (*EDGE_HEX_PATH, *SKIPPED_HEXES):
        q, r = coords[label]
        assert max(abs(q), abs(r), abs(q + r)) == radius, f"{label} is not an edge hex"
    for label in SKIPPED_HEXES:
        assert label not in EDGE_HEX_PATH
    # The stops plus the skipped hexes are the whole ring, so nothing else was left out.
    assert len(EDGE_HEX_PATH) + len(SKIPPED_HEXES) == 6 * radius


def test_ship_jumps_the_skipped_hexes_in_clockwise_order() -> None:
    steps = list(zip(EDGE_HEX_PATH, EDGE_HEX_PATH[1:], strict=False))

    for before, after in (("G1", "E1"), ("B5", "B7"), ("F11", "H11"), ("K7", "K5")):
        assert (before, after) in steps
    assert (EDGE_HEX_PATH[-1], EDGE_HEX_PATH[0]) == ("K4", "J3"), "the path wraps K4 -> J3"


def test_ship_only_ever_jumps_over_a_skipped_hex() -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)

    jumped = set()
    for index, label in enumerate(EDGE_HEX_PATH):
        after = EDGE_HEX_PATH[(index + 1) % len(EDGE_HEX_PATH)]
        steps = _hex_distance(coords[label], coords[after])
        assert steps <= 2, f"{label} -> {after} cuts across the board instead of following the edge"
        if steps == 1:
            continue
        hopped = [
            skipped
            for skipped in SKIPPED_HEXES
            if _hex_distance(coords[skipped], coords[label]) == 1
            and _hex_distance(coords[skipped], coords[after]) == 1
        ]
        assert len(hopped) == 1, f"{label} -> {after} is a gap over something else"
        jumped.update(hopped)

    assert jumped == set(SKIPPED_HEXES)


def test_ship_stops_sit_on_the_upper_part_of_their_hex(page: str) -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)
    offset = ship_anchor_offset_y(layout)
    centers = hex_centers(layout)

    assert offset < 0, "the ship rides above the middle of its hex, not on it"
    assert len(centers) == SHIP_POSITION_COUNT
    for label, center in centers.items():
        assert center == pytest.approx(hex_center(layout, *coords[label]))
    # The lift is baked into the icon, so both layers are placed on a plain hex centre.
    icon = render_ship_icon(0.0, offset, scale=ship_scale(layout), color=SHIP_COLOR)
    assert icon in page


def test_ship_is_black_and_fits_inside_its_hex() -> None:
    layout = load_map_layout()
    scale = ship_scale(layout)
    mast_height = -min(mast_top for _, mast_top, _ in MASTS)
    hull_half_width = max(abs(x) for x, _ in HULL_OUTLINE)
    apothem = layout["hex_size"] * math.sin(math.radians(60.0))

    assert SHIP_COLOR == "#000000"
    assert abs(ship_anchor_offset_y(layout)) + mast_height * scale <= apothem
    assert hull_half_width * scale <= layout["hex_size"]


def test_page_does_not_mark_the_ship_stops(page: str) -> None:
    """Only the ship shows where it is; the stops it is not on stay unmarked."""
    for marker_class in ("ship-path", "ship-position-dot", "ship-anchor", "debug-dot"):
        assert marker_class not in page
    # The four player discs are the only circles the map and its track draw.
    assert _setup_area(page).count("<circle") == len(PLAYER_LABELS)


def test_page_draws_the_ship_in_black(page: str) -> None:
    marker = re.search(r'<g id="ship-marker".*?</g>', page, re.S)

    assert marker is not None
    assert f'fill="{SHIP_COLOR}"' in marker.group(0)
    assert "#F2EEDF" not in marker.group(0)


def test_ship_marker_starts_on_the_hex_of_setup_slot_one(page: str) -> None:
    data = _setup_data(page)
    start_hex = START_HEX_BY_ROLL[DEFAULT_START_ROLL]
    start_x, start_y = data["hexCenters"][start_hex]

    assert data["startRoll"] == DEFAULT_START_ROLL
    assert f'<g id="ship-marker" transform="translate({start_x:.1f},{start_y:.1f})">' in page
    assert f'<strong id="ship-position">0 / {start_hex}</strong>' in page


def test_page_drives_the_ship_from_the_hex_labels(page: str) -> None:
    data = _setup_data(page)

    assert data["edgePath"] == list(EDGE_HEX_PATH)
    assert sorted(data["hexCenters"]) == sorted(EDGE_HEX_PATH)
    # The readout names the hex, not just the index.
    assert 'shipReadout.textContent = shipPosition + " / " + path[shipPosition];' in page
    assert f"skipping\n        {', '.join(SKIPPED_HEXES)}" in page


def _occupied_slots() -> list[tuple[int, str, str]]:
    return [slot for slot in SETUP_SLOTS if slot[2] != "empty"]


def test_setup_slots_are_the_hard_coded_example_schedule() -> None:
    rounds = [round_number for round_number, _, _ in SETUP_SLOTS]
    kinds = {kind for _, _, kind in SETUP_SLOTS}

    assert rounds == list(range(1, SHIP_POSITION_COUNT + 1))
    assert kinds == {"site", "building", "empty"}
    assert len(_occupied_slots()) == 16


def test_start_roll_picks_the_hex_setup_slot_one_sits_on() -> None:
    assert START_HEX_BY_ROLL == {1: "E1", 2: "D1", 3: "D2", 4: "C3", 5: "C4", 6: "B5"}
    for start_hex in START_HEX_BY_ROLL.values():
        assert start_hex in EDGE_HEX_PATH


@pytest.mark.parametrize("start_hex", START_HEX_BY_ROLL.values())
def test_rotated_edge_path_is_the_same_ring_from_a_different_hex(start_hex: str) -> None:
    path = rotated_edge_path(start_hex)

    assert len(path) == SHIP_POSITION_COUNT
    assert path[0] == start_hex
    assert set(path) == set(EDGE_HEX_PATH)
    for skipped in SKIPPED_HEXES:
        assert skipped not in path
    # Still clockwise: every hex keeps the successor it has on the unrotated ring.
    for index, label in enumerate(path):
        source = EDGE_HEX_PATH.index(label)
        assert path[(index + 1) % len(path)] == EDGE_HEX_PATH[(source + 1) % len(EDGE_HEX_PATH)]


def test_setup_placements_follow_the_start_roll() -> None:
    placements = setup_placements(3, load_building_catalog())
    by_round = {placement["round"]: placement for placement in placements}

    assert by_round[1]["hex"] == "D2"
    assert by_round[1]["kind"] == "site"
    assert by_round[2]["hex"] == "C3"
    assert by_round[2]["kind"] == "empty"
    assert by_round[3]["hex"] == "C4"
    assert by_round[3]["label"] == "Guild (level 1)"
    assert by_round[3]["building"]["name"] == "Guild"
    assert by_round[4]["hex"] == "B5"

    path = rotated_edge_path("D2")
    for placement in placements:
        assert placement["hex"] == path[placement["round"] - 1]


def test_setup_building_labels_name_a_catalog_building() -> None:
    buildings = building_by_name(load_building_catalog())

    assert parse_setup_building_label("Guild (level 1)") == ("Guild", 1)
    assert parse_setup_building_label("Chapter House (level 1)") == ("Chapter House", 1)
    assert parse_setup_building_label("Stone Yard (level 2)") == ("Stone Yard", 2)
    assert parse_setup_building_label("Wagon Yard (level 3)") == ("Wagon Yard", 3)
    with pytest.raises(ValueError):
        parse_setup_building_label("Pilgrimage site 1")

    for _, label, kind in _occupied_slots():
        if kind != "building":
            continue
        name, level = parse_setup_building_label(label)
        assert name in buildings, f"{name} is not in the building catalog"
        assert buildings[name]["level"] == level


def _building_names() -> list[str]:
    return [
        parse_setup_building_label(label)[0]
        for _, label, kind in _occupied_slots()
        if kind == "building"
    ]


def test_page_colours_the_building_hexes_in_the_catalog_palette(page: str) -> None:
    buildings = building_by_name(load_building_catalog())
    names = _building_names()

    assert len(names) == 12
    for name in names:
        palette = COLOR_GROUP_PALETTES[buildings[name]["color_group"]]
        for word in name.split():
            assert f">{word}</text>" in page
        assert f'fill="{palette.fill}"' in page
        assert f'fill="{palette.stroke}"' in page
    for palette in COLOR_GROUP_PALETTES.values():
        assert palette.fill in page
    assert page.count('class="setup-building-fill"') == len(names)
    assert page.count('class="setup-building-label"') == len(names)


def test_building_fills_take_the_map_hex_shape_and_draw_no_outline(page: str) -> None:
    layout = load_map_layout()
    building = building_by_name(load_building_catalog())["Guild"]
    points = " ".join(f"{x:.2f},{y:.2f}" for x, y in hex_vertices(0.0, 0.0, layout["hex_size"]))

    fill = render_setup_building_fill(layout, building)
    assert fill == (
        f'<polygon points="{points}" fill="'
        f'{COLOR_GROUP_PALETTES[building["color_group"]].fill}" stroke="none"/>'
    )
    assert fill in page
    # No second hex on top of the map's own: no inset shape, no tile stroke, no old overlay class.
    assert "setup-building-overlay" not in page
    assert render_building_tile(building, 0.0, 0.0) not in page
    for stroked in ('<polygon points="[^"]*" fill="[^"]*" stroke="#', 'class="setup-\\w+" stroke'):
        assert re.search(stroked, page) is None


def test_building_fills_sit_under_the_map_border_lines(page: str) -> None:
    """The map draws its edges and labels after the fills, so a placed building keeps both."""
    assert page.index('<g id="setup-fills">') < page.index("<line ")
    assert page.index("<line ") < page.index('<g id="setup-labels">')


def _slot_groups(page: str) -> list[tuple[int, str, str]]:
    """Every placed group as (round, class, body), split on the openings rather than parsed."""
    groups = []
    for chunk in page.split("<g class=")[1:]:
        match = re.match(r'"([\w-]+)" data-slot="(\d+)"[^>]*>', chunk)
        if match is None:
            continue
        body = chunk[match.end() :].split("</g>")[0]
        groups.append((int(match.group(2)), match.group(1), body))
    return groups


def test_page_does_not_number_the_setup_slots(page: str) -> None:
    """The slots are placed, not annotated: the round a slot belongs to is not drawn on the map."""
    groups = _slot_groups(page)

    assert {round_number for round_number, _, _ in groups} == {
        round_number for round_number, _, _ in _occupied_slots()
    }
    for marker_name in ("setup-slot-number", "round-number", "slot-number-badge", "round-badge"):
        assert marker_name not in page
    for round_number, class_name, body in groups:
        assert "<circle" not in body, f"slot {round_number} still draws a number badge"
        assert f">{round_number}</text>" not in body
        assert class_name in (
            "setup-building-fill",
            "setup-site-fill",
            "setup-building-label",
            "setup-site-content",
        )


SITE_ROUNDS = (1, 7, 15, 19)


def _site_slots() -> list[tuple[int, str, str]]:
    return [slot for slot in SETUP_SLOTS if slot[2] == "site"]


def test_setup_site_slots_take_the_first_four_sites_in_file_order() -> None:
    sites = sites_of(load_pilgrimage_sites())
    placements = setup_placements(3, load_building_catalog(), load_pilgrimage_sites())
    placed = [placement for placement in placements if placement["kind"] == "site"]

    assert [round_number for round_number, _, _ in _site_slots()] == list(SITE_ROUNDS)
    assert parse_setup_site_label("Pilgrimage site 2") == 2
    with pytest.raises(ValueError):
        parse_setup_site_label("Guild (level 1)")

    assert len(placed) == 4
    for index, placement in enumerate(placed):
        assert placement["site"] == sites[index]
    # The fifth site is left in the box for now.
    assert sites[4] not in [placement["site"] for placement in placed]
    assert [placement["site"]["vp"] for placement in placed] == [5, 5, 5, 6]


def test_setup_placements_leave_sites_unresolved_without_the_site_data() -> None:
    """The site data is optional, the way the catalog is: the slots still know where they sit."""
    placements = setup_placements(3)

    assert all(placement["site"] is None for placement in placements)
    assert [placement["hex"] for placement in placements][:3] == ["D2", "C3", "C4"]


def test_page_fills_the_site_hexes_in_pilgrimage_site_orange(page: str) -> None:
    layout = load_map_layout()
    filled = {
        round_number: body
        for round_number, class_name, body in _slot_groups(page)
        if class_name == "setup-site-fill"
    }

    points = " ".join(f"{x:.2f},{y:.2f}" for x, y in hex_vertices(0.0, 0.0, layout["hex_size"]))

    assert set(filled) == set(SITE_ROUNDS)
    # The map's own hex, recoloured: no inset tile, no second outline.
    assert (
        render_setup_site_fill(layout)
        == f'<polygon points="{points}" fill="{SITE_FILL}" stroke="none"/>'
    )
    for round_number, body in filled.items():
        fill = re.search(rf'<polygon points="[^"]*" fill="{SITE_FILL}" stroke="none"/>', body)
        assert fill is not None, f"site slot {round_number} does not recolour its hex"


def test_page_draws_the_site_star_and_values_inside_the_hex(page: str) -> None:
    sites = sites_of(load_pilgrimage_sites())[:4]
    contents = {
        round_number: body.split("</g>")[0]
        for round_number, class_name, body in _slot_groups(page)
        if class_name == "setup-site-content"
    }

    assert set(contents) == set(SITE_ROUNDS)
    for site, round_number in zip(sites, SITE_ROUNDS, strict=True):
        body = contents[round_number]
        assert f'fill="{STAR_FILL}" stroke="{STAR_STROKE}"' in body
        for value in (site["vp"], site["piety"], "P", site["stone"], "S"):
            assert f">{value}</text>" in body
        assert f'fill="{SITE_STROKE}"' in body, "the values are written in the site's own ink"
    for color in (SITE_FILL, SITE_STROKE, STAR_FILL, STAR_STROKE):
        assert color in page


def test_site_values_read_the_way_the_standalone_tiles_do(page: str) -> None:
    """P over S, first three sites 3/3, 3/3, 4/4, then 3/4."""
    sites = sites_of(load_pilgrimage_sites())[:4]

    assert [(site["piety"], site["stone"]) for site in sites] == [(3, 3), (3, 3), (4, 4), (3, 4)]
    contents = {
        round_number: body.split("</g>")[0]
        for round_number, class_name, body in _slot_groups(page)
        if class_name == "setup-site-content"
    }
    for site, round_number in zip(sites, SITE_ROUNDS, strict=True):
        texts = re.findall(r">([^<]+)</text>", contents[round_number])
        assert texts == [str(site["vp"]), str(site["piety"]), "P", str(site["stone"]), "S"]


def test_site_content_stays_in_the_lower_half_of_its_hex(page: str) -> None:
    """The upper half belongs to the map's hex label and the ship, as it does for buildings."""
    layout = load_map_layout()
    apothem = layout["hex_size"] * math.sin(math.radians(60.0))
    bodies = [
        body.split("</g>")[0]
        for _, class_name, body in _slot_groups(page)
        if class_name == "setup-site-content"
    ]

    assert bodies
    for body in bodies:
        for x, y in re.findall(r'<text x="(-?[\d.]+)" y="(-?[\d.]+)"', body):
            assert 0.0 < float(y) < apothem
            assert abs(float(x)) < layout["hex_size"]


def test_page_leaves_empty_slots_and_skipped_hexes_alone(page: str) -> None:
    data = _setup_data(page)
    empty_rounds = {round_number for round_number, _, kind in SETUP_SLOTS if kind == "empty"}
    placed = {round_number for round_number, _, _ in _slot_groups(page)}

    assert placed.isdisjoint(empty_rounds)
    for skipped in SKIPPED_HEXES:
        assert skipped not in data["hexCenters"]
    # A site shows the values off its tile, not the slot's own bookkeeping label.
    assert ">Pilgrimage site" not in page


def test_page_draws_the_ship_above_the_setup_slots(page: str) -> None:
    assert page.index('<g id="setup-fills">') < page.index('<g id="ship-marker"')
    assert page.index('<g id="setup-labels">') < page.index('<g id="ship-marker"')


def test_page_offers_a_start_roll_for_every_face_of_the_die(page: str) -> None:
    assert "Start roll" in page
    for roll in START_HEX_BY_ROLL:
        assert f'data-start-roll="{roll}"' in page
    assert _setup_data(page)["startHexByRoll"] == {
        str(roll): start_hex for roll, start_hex in START_HEX_BY_ROLL.items()
    }
    # Changing the roll re-places the slots and sends the ship back to the new first hex.
    assert "shipPosition = 0;" in page
    assert "renderSlots();" in page


def test_page_stays_a_static_local_debug_view(page: str) -> None:
    assert "<iframe" not in page
    assert "http://" not in page.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in page
    for forbidden in ("apply_action", "legal_actions", "fetch(", "XMLHttpRequest"):
        assert forbidden not in page


def test_index_links_to_the_generated_game_setup_page() -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")

    assert "generated/game_setup.html" in content
    assert "Generated game setup debug view" in content


ROLE_LABELS = (
    "Fields",
    "Road Engineer",
    "Stone Mason",
    "Alms House",
    "Engraver",
    "Vestry",
)
PLAYER_BOARD_FILLS = ("#FFFFFF", "#B7382E", "#D9B33B", "#3B6EA5")


def _player_board(page: str, player_id: str) -> str:
    pattern = rf'<div class="panel player-board"[^>]*data-player="{player_id}"[^>]*>.*?</div>'
    match = re.search(pattern, page, re.S)
    assert match is not None, f"no player board for {player_id}"
    return match.group(0)


def _cubes(board: str, selector: str) -> tuple[int, int]:
    """(slots drawn, cubes shown) for one area of a board, since hidden slots stay in the SVG."""
    slots = re.findall(rf"<rect[^>]*{selector}[^>]*/>", board)
    return len(slots), len([slot for slot in slots if 'opacity="1"' in slot])


def test_page_shows_the_four_player_boards(page: str) -> None:
    layout = load_player_boards_v2_layout()

    assert "Player board v2" in page
    for player, fill in zip(players_of(layout), PLAYER_BOARD_FILLS, strict=True):
        board = _player_board(page, player["id"])
        assert f'data-player-color="{player["color"]}"' in board
        assert player["label"] in board
        assert fill in board
    for label in ("Village", "Abbey", *ROLE_LABELS):
        assert label in page


def test_boards_start_on_the_default_board_state(page: str) -> None:
    """Eight serfs in the Village, three acolytes in the Abbey, three acolytes on roles."""
    layout = load_player_boards_v2_layout()
    capacity = token_slot_count(layout)

    for player in players_of(layout):
        board = _player_board(page, player["id"])
        assert _cubes(board, 'data-token="village"') == (capacity, 8)
        assert _cubes(board, 'data-token="abbey"') == (capacity, 3)
        for role, shown in (("stone_mason", 1), ("vestry", 2), ("fields", 0)):
            # Both the centred slot and the pair are drawn, so a move only flips opacity.
            assert _cubes(board, f'data-role="{role}"') == (ROLE_ACOLYTE_LIMIT + 1, shown)


def test_only_the_first_player_carries_the_marker(page: str) -> None:
    assert page.count('data-first-player-marker="true"') == 1
    assert page.count('data-first-player-marker="false"') == len(PLAYER_LABELS) - 1
    assert 'data-first-player-marker="true"' in _player_board(page, DEFAULT_FIRST_PLAYER)


def test_page_offers_first_player_marker_buttons(page: str) -> None:
    layout = load_player_boards_v2_layout()

    for player, label in zip(players_of(layout), PLAYER_LABELS, strict=True):
        assert f'data-first-player="{player["id"]}"' in page
        assert f"Move first player marker to {label}" in page


def test_page_offers_a_serf_button_per_player(page: str) -> None:
    layout = load_player_boards_v2_layout()

    for player, label in zip(players_of(layout), PLAYER_LABELS, strict=True):
        assert f'data-serf-player="{player["id"]}"' in page
        assert f"Move serf to Abbey: {label}" in page


def test_acolyte_controls_cover_the_abbey_and_every_role_but_not_the_village(page: str) -> None:
    layout = load_player_boards_v2_layout()
    places = acolyte_places(layout)

    assert [label for _, label in places] == ["Abbey", *ROLE_LABELS]
    assert "village" not in [place for place, _ in places]
    for select in ("acolyte-player", "acolyte-source", "acolyte-target"):
        assert f'<select id="{select}">' in page
    assert "Move acolyte" in page
    source = re.search(r'<select id="acolyte-source">(.*?)</select>', page, re.S)
    target = re.search(r'<select id="acolyte-target">(.*?)</select>', page, re.S)
    assert source is not None and target is not None
    for options in (source.group(1), target.group(1)):
        for place, label in places:
            assert f'<option value="{place}"' in options
            assert f">{label}</option>" in options
        assert ">Village</option>" not in options
    assert '<option value="abbey" selected>' in source.group(1)
    assert '<option value="fields" selected>' in target.group(1)


def test_default_board_state_is_the_one_the_prototype_draws() -> None:
    state = default_player_board_v2_state(load_player_boards_v2_layout())

    assert state["village_serfs"] == 8
    assert state["abbey_acolytes"] == 3
    assert state["roles"] == {
        "fields": 0,
        "road_engineer": 0,
        "stone_mason": 1,
        "alms_house": 0,
        "engraver": 0,
        "vestry": 2,
    }


def test_panel_state_gives_every_player_the_default_board() -> None:
    layout = load_player_boards_v2_layout()
    state = player_board_ui_state(layout)

    assert state["firstPlayer"] == DEFAULT_FIRST_PLAYER == "player_one"
    assert sorted(state["players"]) == sorted(player["id"] for player in players_of(layout))
    for board in state["players"].values():
        assert board["villageSerfs"] == 8
        assert board["abbeyAcolytes"] == 3
        assert board["roles"]["stone_mason"] == 1
        assert board["roles"]["vestry"] == 2


def test_role_circles_hold_at_most_two_acolytes() -> None:
    layout = load_player_boards_v2_layout()
    state = default_player_board_v2_state(layout)
    state["roles"]["fields"] = ROLE_ACOLYTE_LIMIT + 3

    svg = render_player_board_v2_svg(
        layout, players_of(layout)[0], board_state=state, interactive=True
    )

    assert ROLE_ACOLYTE_LIMIT == 2
    assert _cubes(svg, 'data-role="fields"') == (ROLE_ACOLYTE_LIMIT + 1, ROLE_ACOLYTE_LIMIT)


def test_page_hands_the_boards_their_limits(page: str) -> None:
    layout = load_player_boards_v2_layout()
    boards = _setup_data(page)["playerBoards"]

    assert boards["roleLimit"] == ROLE_ACOLYTE_LIMIT
    assert boards["abbeyCapacity"] == token_slot_count(layout)
    assert boards["abbeyId"] == "abbey"
    assert boards["roles"] == [role["id"] for role in layout["worker_roles"]]
    assert boards["state"] == player_board_ui_state(layout)


SETUP_BUILDING_NAMES = (
    "Guild",
    "Mint",
    "Chapter House",
    "Infirmary",
    "Dormitory",
    "Cloisters",
    "Brewery",
    "Stone Yard",
    "Pulpit",
    "Inquisition",
    "Wagon Yard",
    "Kogge",
)


def _placements(start_roll: int = DEFAULT_START_ROLL) -> list[dict]:
    return setup_placements(start_roll, load_building_catalog(), load_pilgrimage_sites())


def _ownership_state() -> dict:
    return building_ownership_state(load_player_boards_v2_layout(), _placements())


def _select_options(page: str, select_id: str) -> str:
    match = re.search(rf'<select id="{select_id}">(.*?)</select>', page, re.S)
    assert match is not None, f"no {select_id} dropdown"
    return match.group(1)


def test_page_offers_buy_and_donate_controls(page: str) -> None:
    layout = load_player_boards_v2_layout()

    assert "Buy building" in page
    assert "Donate building" in page
    for select in ("buy-player", "buy-building", "donate-player", "donate-slot"):
        assert f'<select id="{select}">' in page
    for player, label in zip(players_of(layout), PLAYER_LABELS, strict=True):
        for select in ("buy-player", "donate-player"):
            assert f'<option value="{player["id"]}"' in _select_options(page, select)
        assert label in page
    slots = _select_options(page, "donate-slot")
    for number in range(1, int(layout["building_slot_count"]) + 1):
        assert f'<option value="{number}"' in slots
        assert f">Slot {number}</option>" in slots


def test_available_buildings_are_the_building_slots_only(page: str) -> None:
    """Empty slots have nothing to sell and site slots hold a pilgrimage site, not a building."""
    available = available_setup_buildings(_placements())
    building_rounds = [round_number for round_number, _, kind in SETUP_SLOTS if kind == "building"]
    options = _select_options(page, "buy-building")

    assert [building["name"] for building in available] == list(SETUP_BUILDING_NAMES)
    assert [building["setupSlot"] for building in available] == building_rounds
    for building in available:
        assert f'<option value="{building["setupSlot"]}"' in options
        assert f">{building['label']}</option>" in options
    assert ">Empty</option>" not in options
    assert ">Pilgrimage site" not in options


def test_donated_buildings_are_worth_two_four_and_six(page: str) -> None:
    mapping = donated_vp_by_level(load_donated_building_tiles())
    exposed = _setup_data(page)["buildingOwnership"]["donatedVpByLevel"]

    assert mapping == {1: 2, 2: 4, 3: 6}
    assert exposed == {"1": 2, "2": 4, "3": 6}


def test_first_empty_building_slot_walks_the_board() -> None:
    state = _ownership_state()
    slots = state["players"]["player_one"]["buildingSlots"]

    assert first_empty_building_slot(slots) == 1
    assert buy_building(state, "player_one", 3) == 1
    assert first_empty_building_slot(slots) == 2
    for setup_slot in (4, 5, 6, 9, 10):
        buy_building(state, "player_one", setup_slot)
    assert first_empty_building_slot(slots) is None
    # A full board buys nothing, and the building it could not take stays on the map.
    assert buy_building(state, "player_one", 11) is None
    assert "11" in state["available"]


def test_buying_takes_a_building_off_the_map_for_one_player_only() -> None:
    state = _ownership_state()

    assert buy_building(state, "player_two", 22) == 1
    entry = state["players"]["player_two"]["buildingSlots"][0]

    assert entry == {
        "setupSlot": 22,
        "buildingId": "kogge",
        "name": "Kogge",
        "level": 3,
        "donated": False,
    }
    assert "22" not in state["available"]
    assert state["players"]["player_one"]["buildingSlots"] == [None] * 6
    # The same building cannot be bought twice.
    assert buy_building(state, "player_one", 22) is None


def test_donating_flips_a_bought_building_once() -> None:
    state = _ownership_state()
    slots = state["players"]["player_one"]["buildingSlots"]
    buy_building(state, "player_one", 3)

    assert can_donate_building_slot(slots, 1) is True
    assert donate_building(state, "player_one", 1) is True
    assert slots[0]["donated"] is True
    # Once flipped it stays in its slot, and it cannot be flipped again.
    assert slots[0]["setupSlot"] == 3
    assert can_donate_building_slot(slots, 1) is False
    assert donate_building(state, "player_one", 1) is False
    # An empty slot has nothing to donate.
    assert can_donate_building_slot(slots, 2) is False
    assert donate_building(state, "player_one", 2) is False
    assert can_donate_building_slot(slots, 7) is False


def test_a_bought_building_is_keyed_to_its_setup_slot_not_its_hex() -> None:
    """Changing the start roll moves a building around the map; it does not give it back."""
    state = _ownership_state()
    buy_building(state, "player_one", 3)
    entry = state["players"]["player_one"]["buildingSlots"][0]

    rotated = {placement["round"]: placement for placement in _placements(3)}
    original = {placement["round"]: placement for placement in _placements()}

    assert rotated[3]["hex"] != original[3]["hex"]
    assert rotated[entry["setupSlot"]]["building"]["id"] == entry["buildingId"]
    assert "3" not in state["available"]


def test_setup_building_overlays_name_the_building_they_draw(page: str) -> None:
    """Both layers carry the building's id, so a bought building can leave the map by name."""
    catalog = building_by_name(load_building_catalog())
    named = re.findall(
        r'<g class="setup-(building|site)-(?:fill|label|content)" data-slot="(\d+)"'
        r'(?: data-building-id="([\w_]+)")?',
        page,
    )
    buildings = {slot: building_id for kind, slot, building_id in named if kind == "building"}
    sites = {slot: building_id for kind, slot, building_id in named if kind == "site"}

    assert len(buildings) == len(SETUP_BUILDING_NAMES)
    assert set(sites.values()) == {""}, "a pilgrimage site is not a building and is not for sale"
    for placement in _placements():
        if placement["building"] is None:
            continue
        name, _ = parse_setup_building_label(placement["label"])
        assert buildings[str(placement["round"])] == catalog[name]["id"]


def _defs(page: str) -> str:
    match = re.search(r"<defs>(.*?)</defs>", page, re.S)
    assert match is not None
    return match.group(1)


def test_page_defines_the_content_a_board_slot_can_show(page: str) -> None:
    """Every building and every donated level is drawn once and pointed at by reference."""
    available = available_setup_buildings(_placements())
    defs = _defs(page)

    for building in available:
        assert f'<g id="bought-{building["buildingId"]}">' in defs
        assert f">{building['name'].split()[0]}</text>" in defs
    for level, vp in donated_vp_by_level(load_donated_building_tiles()).items():
        donated = re.search(rf'<g id="donated-level-{level}">(.*?)</g>', defs, re.S)
        assert donated is not None
        assert f'fill="{STAR_FILL}"' in donated.group(1)
        assert f">{vp}</text>" in donated.group(1)


def test_board_slot_content_recolours_the_slot_without_a_tile_border(page: str) -> None:
    """A bought or donated building fills the slot's own hex and draws no border of its own."""
    defs = _defs(page)
    slot_hex = hex_path_data(0.0, 0.0, BOARD_HEX_SIZE)
    fills = re.findall(rf'<path d="{re.escape(slot_hex)}"[^>]*/>', defs)

    assert len(fills) == len(SETUP_BUILDING_NAMES) + len(tiles_of(load_donated_building_tiles()))
    for fill in fills:
        assert 'stroke="none"' in fill
        assert "stroke-width" not in fill
    # A tile's own border colour is never stroked here; the labels only write in it.
    for palette in COLOR_GROUP_PALETTES.values():
        assert f'stroke="{palette.stroke}"' not in defs


def test_bought_slot_content_is_the_tile_colour_and_label_only() -> None:
    building = building_by_name(load_building_catalog())["Guild"]
    palette = COLOR_GROUP_PALETTES[building["color_group"]]
    content = render_board_slot_building(building)

    assert content.startswith(render_board_slot_fill(palette.fill))
    assert f'stroke="{palette.stroke}"' not in content
    assert f">{building['name']}</text>" in content


def _label_baselines(content: str) -> list[float]:
    return [float(y) for y in re.findall(r'<text x="0" y="(-?[\d.]+)"', content)]


def test_a_bought_building_labels_the_lower_half_of_its_slot() -> None:
    """The slot reads like a map hex: every line below the centre, none of it past the edge."""
    apothem = BOARD_HEX_SIZE * math.sin(math.radians(60.0))

    for name in ("Kogge", "Chapter House"):
        building = building_by_name(load_building_catalog())[name]
        baselines = _label_baselines(render_board_slot_building(building))

        assert len(baselines) == len(tile_text_lines(building))
        assert baselines == sorted(baselines)
        for baseline in baselines:
            assert 0.0 < baseline < apothem


def test_a_bought_building_is_labelled_at_the_same_proportions_as_on_the_map() -> None:
    building = building_by_name(load_building_catalog())["Kogge"]
    map_layout = load_map_layout()
    ratio = BOARD_HEX_SIZE / map_layout["hex_size"]

    slot = _label_baselines(render_board_slot_building(building))
    on_map = _label_baselines(render_setup_building_label(map_layout, building))

    assert slot and len(slot) == len(on_map)
    for slot_y, map_y in zip(slot, on_map, strict=True):
        assert slot_y == pytest.approx(map_y * ratio, abs=0.05)


def test_donated_slot_content_keeps_the_star_and_drops_the_tile_border() -> None:
    tile = tiles_of(load_donated_building_tiles())[0]
    palette = COLOR_GROUP_PALETTES[tile["color_group"]]
    content = render_board_slot_donated(tile)

    assert content.startswith(render_board_slot_fill(palette.fill))
    assert f'stroke="{palette.stroke}"' not in content
    assert f'fill="{STAR_FILL}" stroke="{STAR_STROKE}"' in content
    assert f">{tile['vp']}</text>" in content


def test_board_building_slots_start_empty(page: str) -> None:
    """Fill, then the building content, then the dashed outline that stays the slot's boundary."""
    layout = load_player_boards_v2_layout()
    palette = layout["palette"]
    slot_count = int(layout["building_slot_count"])

    assert len(building_slot_centers(layout)) == slot_count
    for player in players_of(layout):
        board = _player_board(page, player["id"])
        for number, (cx, cy) in enumerate(building_slot_centers(layout), start=1):
            slot = re.search(
                rf'<g data-player-board-slot="{number}" data-building-slot-state="empty"'
                r"[^>]*>(.*?)</g>",
                board,
                re.S,
            )
            assert slot is not None, f"slot {number} is not a taggable group"
            body = slot.group(1)
            path = hex_path_data(cx, cy)
            fill = f'<path d="{path}" fill="{palette["slot_fill"]}" stroke="none"/>'
            content = f'<use data-building-content="true" x="{cx:.1f}" y="{cy:.1f}" opacity="0"/>'
            assert body.startswith(fill)
            assert content in body
            assert body.endswith(
                f'<path data-slot-outline="true" d="{path}" fill="none"'
                f' stroke="{palette["slot_stroke"]}" stroke-width="2"'
                f' stroke-dasharray="{BUILDING_SLOT_DASH_ARRAY}" stroke-linejoin="round"/>'
            )
        assert "No buildings bought yet." in board
        assert "No buildings bought yet." in board


def test_player_board_panel_leaves_the_map_controls_alone(page: str) -> None:
    """The boards sit beside the setup area, and the buttons there keep their own attributes."""
    assert page.index('<div class="setup-main">') < page.index('<div class="player-board-panel">')
    assert page.index('<g id="ship-marker"') < page.index('<div class="player-board-panel">')
    piety_buttons = re.findall(r'<button[^>]*data-piety-delta="[^"]*"[^>]*>', page)
    assert len(piety_buttons) == 2 * len(PLAYER_LABELS)
    for button in piety_buttons:
        assert "data-serf-player" not in button and "data-first-player" not in button
