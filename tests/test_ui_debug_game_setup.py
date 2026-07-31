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
    SITE_TINT_COLOR,
    SKIPPED_HEXES,
    START_HEX_BY_ROLL,
    building_by_name,
    default_output_path,
    hex_centers,
    parse_setup_building_label,
    render_setup_building_fill,
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


def test_page_embeds_the_rendered_piety_track(page: str) -> None:
    """One VP star per piety position, labelled from the piety config."""
    vp_values = piety_vp_values(load_piety_config())

    for vp in vp_values:
        assert f">{vp}</text>" in page
    stars = re.findall(r'<path d="M [^"]*" fill="#F4D03F"', page)
    assert len(stars) == len(vp_values)


def test_page_uses_the_three_four_player_track_only(page: str) -> None:
    layout = load_piety_track_layout()

    assert f'data-piety-variant="{PIETY_VARIANT_ID}"' in page
    assert variant_by_id(layout, PIETY_VARIANT_ID)["label"] in page
    # One fused strip rect means one track strip was drawn.
    assert page.count('<rect x="0" y="0"') == 1


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
    # The four player discs are the only circles the page draws.
    assert page.count("<circle") == len(PLAYER_LABELS)


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
        groups.append((int(match.group(2)), match.group(1), chunk[match.end() :]))
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
        assert f">{round_number}</text>" not in body.split("</g>")[0]
        assert class_name in ("setup-building-fill", "setup-site-fill", "setup-building-label")


def test_page_marks_pilgrimage_sites_with_a_tint_and_nothing_else(page: str) -> None:
    site_rounds = [round_number for round_number, _, kind in SETUP_SLOTS if kind == "site"]
    tinted = {
        round_number: body
        for round_number, class_name, body in _slot_groups(page)
        if class_name == "setup-site-fill"
    }

    assert site_rounds == [1, 7, 15, 19]
    assert set(tinted) == set(site_rounds)
    for round_number, body in tinted.items():
        tint = re.search(rf'<polygon points="[^"]*" fill="{SITE_TINT_COLOR}"[^>]*/>', body)
        assert tint is not None, f"site slot {round_number} has no tint"
        assert "<text" not in body.split("</g>")[0], "sites do not get an invented tile"


def test_page_leaves_empty_slots_and_skipped_hexes_alone(page: str) -> None:
    data = _setup_data(page)
    empty_rounds = {round_number for round_number, _, kind in SETUP_SLOTS if kind == "empty"}
    placed = {round_number for round_number, _, _ in _slot_groups(page)}

    assert placed.isdisjoint(empty_rounds)
    for skipped in SKIPPED_HEXES:
        assert skipped not in data["hexCenters"]
    # Pilgrimage sites are a tint only: no invented tile, no label text.
    assert "Pilgrimage site" not in page


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
