import json
import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_game_setup import (
    PIETY_VARIANT_ID,
    SHIP_COLOR,
    SHIP_HEX_PATH,
    SHIP_POSITION_COUNT,
    SHIP_SKIPPED_HEXES,
    default_output_path,
    ship_anchor_offset_y,
    ship_path_points,
    ship_scale,
    write_game_setup_page,
)
from tools.ui_debug.render_map import hex_center, label_to_coord, load_map_layout, render_map_svg
from tools.ui_debug.render_piety_track import (
    load_piety_config,
    load_piety_track_layout,
    piety_vp_values,
    position_center_x,
    track_geometry,
    variant_by_id,
)
from tools.ui_debug.render_ship_marker import HULL_OUTLINE, MASTS

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
    """The map comes from the renderer, not from copied prototype HTML."""
    map_svg = render_map_svg(load_map_layout())

    assert map_svg[: map_svg.rindex("</svg>")] in page


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

    assert len(SHIP_HEX_PATH) == SHIP_POSITION_COUNT == 26
    assert len(set(SHIP_HEX_PATH)) == len(SHIP_HEX_PATH)
    assert SHIP_HEX_PATH[0] == "J3"
    # Clockwise: J3 leads to J2, not back up the other side of the board to K4.
    assert SHIP_HEX_PATH[1] == "J2"
    assert SHIP_HEX_PATH[-1] == "K4"
    for label in (*SHIP_HEX_PATH, *SHIP_SKIPPED_HEXES):
        q, r = coords[label]
        assert max(abs(q), abs(r), abs(q + r)) == radius, f"{label} is not an edge hex"
    for label in SHIP_SKIPPED_HEXES:
        assert label not in SHIP_HEX_PATH
    # The stops plus the skipped hexes are the whole ring, so nothing else was left out.
    assert len(SHIP_HEX_PATH) + len(SHIP_SKIPPED_HEXES) == 6 * radius


def test_ship_jumps_the_skipped_hexes_in_clockwise_order() -> None:
    steps = list(zip(SHIP_HEX_PATH, SHIP_HEX_PATH[1:], strict=False))

    for before, after in (("G1", "E1"), ("B5", "B7"), ("F11", "H11"), ("K7", "K5")):
        assert (before, after) in steps
    assert (SHIP_HEX_PATH[-1], SHIP_HEX_PATH[0]) == ("K4", "J3"), "the path wraps K4 -> J3"


def test_ship_only_ever_jumps_over_a_skipped_hex() -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)

    jumped = set()
    for index, label in enumerate(SHIP_HEX_PATH):
        after = SHIP_HEX_PATH[(index + 1) % len(SHIP_HEX_PATH)]
        steps = _hex_distance(coords[label], coords[after])
        assert steps <= 2, f"{label} -> {after} cuts across the board instead of following the edge"
        if steps == 1:
            continue
        hopped = [
            skipped
            for skipped in SHIP_SKIPPED_HEXES
            if _hex_distance(coords[skipped], coords[label]) == 1
            and _hex_distance(coords[skipped], coords[after]) == 1
        ]
        assert len(hopped) == 1, f"{label} -> {after} is a gap over something else"
        jumped.update(hopped)

    assert jumped == set(SHIP_SKIPPED_HEXES)


def test_ship_stops_sit_on_the_upper_part_of_their_hex() -> None:
    layout = load_map_layout()
    coords = label_to_coord(layout)
    offset = ship_anchor_offset_y(layout)
    path = ship_path_points(layout)

    assert offset < 0, "the ship rides above the middle of its hex, not on it"
    assert len(path) == SHIP_POSITION_COUNT
    for label, stop in zip(SHIP_HEX_PATH, path, strict=True):
        center_x, center_y = hex_center(layout, *coords[label])
        assert stop == pytest.approx((center_x, center_y + offset))


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
    """Only the ship shows where it is; the other 25 stops stay unmarked."""
    for marker_class in ("ship-path", "ship-position-dot", "ship-anchor", "debug-dot"):
        assert marker_class not in page
    # The four player discs are the only circles the page draws.
    assert page.count("<circle") == len(PLAYER_LABELS)


def test_page_draws_the_ship_in_black(page: str) -> None:
    marker = re.search(r'<g id="ship-marker".*?</g>', page, re.S)

    assert marker is not None
    assert f'fill="{SHIP_COLOR}"' in marker.group(0)
    assert "#F2EEDF" not in marker.group(0)


def test_ship_marker_starts_on_the_first_path_stop(page: str) -> None:
    path = _setup_data(page)["shipPath"]
    start_x, start_y = path[0]

    assert len(path) == SHIP_POSITION_COUNT
    assert f'<g id="ship-marker" transform="translate({start_x:.1f},{start_y:.1f})">' in page


def test_page_drives_the_ship_from_the_hex_labels(page: str) -> None:
    data = _setup_data(page)

    assert data["shipHexPath"] == list(SHIP_HEX_PATH)
    assert len(data["shipPath"]) == len(data["shipHexPath"])
    # The readout names the hex, not just the index.
    assert "shipHexPath[shipPosition]" in page
    assert '<strong id="ship-position">0 / J3</strong>' in page
    assert f"skipping\n        {', '.join(SHIP_SKIPPED_HEXES)}" in page


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
