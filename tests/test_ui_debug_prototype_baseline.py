import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
PROTOTYPES_DIR = UI_DEBUG_DIR / "prototypes"
PROTOTYPE_SOURCES_DIR = UI_DEBUG_DIR / "prototype_sources"

INDEX_HTML = UI_DEBUG_DIR / "index.html"
README_MD = UI_DEBUG_DIR / "README.md"
MAP_HTML = PROTOTYPES_DIR / "map.html"
BUILDING_TILES_HTML = PROTOTYPES_DIR / "building_tiles.html"
PLAYER_BOARD_HTML = PROTOTYPES_DIR / "player_board.html"
PLAYER_BOARDS_V2_HTML = PROTOTYPES_DIR / "player_boards_v2.html"
PLAYER_BOARDS_V2_SOURCE = PROTOTYPE_SOURCES_DIR / "player_boards_v2.py.txt"
DONATED_BUILDING_TILES_HTML = PROTOTYPES_DIR / "donated_building_tiles.html"
SHIP_MARKER_HTML = PROTOTYPES_DIR / "ship_marker.html"
PIETY_TRACKS_HTML = PROTOTYPES_DIR / "piety_tracks.html"
PIETY_TRACKS_SOURCE = PROTOTYPE_SOURCES_DIR / "piety_tracks.py.txt"
PIETY_TRACKS_V2_HTML = PROTOTYPES_DIR / "piety_tracks_v2.html"
PIETY_TRACK_V2_SVG = PROTOTYPES_DIR / "piety_track_v2.svg"
PIETY_TRACK_2P_V2_SVG = PROTOTYPES_DIR / "piety_track_2p_v2.svg"
PIETY_TRACKS_V2_SOURCE = PROTOTYPE_SOURCES_DIR / "piety_tracks_v2.py.txt"
PILGRIMAGE_SITES_HTML = PROTOTYPES_DIR / "pilgrimage_sites.html"
PILGRIMAGE_SITES_SOURCE = PROTOTYPE_SOURCES_DIR / "pilgrimage_sites.py.txt"
DUTY_WHEEL_HTML = PROTOTYPES_DIR / "duty_wheel.html"
DUTY_WHEEL_SVG = PROTOTYPES_DIR / "duty_wheel.svg"
DUTY_WHEEL_BUILD_SOURCE = PROTOTYPE_SOURCES_DIR / "duty_wheel_build.py.txt"
DUTY_WHEEL_RENDER_SOURCE = PROTOTYPE_SOURCES_DIR / "duty_wheel_render.py.txt"
ALMS_TABLE_HTML = PROTOTYPES_DIR / "alms_table.html"
ALMS_TABLE_SVG = PROTOTYPES_DIR / "alms_table.svg"
ALMS_TABLE_SOURCE = PROTOTYPE_SOURCES_DIR / "alms_table.py.txt"
SEALS_HTML = PROTOTYPES_DIR / "seal_prototypes.html"
DUTY_TILE_TURN_HTML = PROTOTYPES_DIR / "duty_tile_turn.html"
DUTY_TILE_TURN_SOURCE = PROTOTYPE_SOURCES_DIR / "duty_tile_turn_build.py.txt"

DUTY_WHEEL_V2_HTML = PROTOTYPES_DIR / "duty_wheel_v2.html"
DUTY_WHEEL_V2_SVG = PROTOTYPES_DIR / "duty_wheel_v2.svg"
DUTY_WHEEL_V2_LAYOUT = UI_DEBUG_DIR / "duty_wheel_v2_layout.json"
DUTY_WHEEL_V2_LAYOUT_1500 = UI_DEBUG_DIR / "duty_wheel_v2_1500_layout.json"
DUTY_WHEEL_V2_BUILD = UI_DEBUG_DIR / "build_duty_wheel_v2.py"
DUTY_WHEEL_V2_RENDER = UI_DEBUG_DIR / "render_duty_wheel_v2.py"
DUTY_WHEEL_V2_GENERATE = UI_DEBUG_DIR / "generate_duty_wheel_v2.py"

# The nine faces of the v2 wheel, by position and in grid order, top-left to bottom-right.
DUTY_WHEEL_V2_POSITIONS = (
    "north_west", "north", "north_east",
    "west", "centre", "east",
    "south_west", "south", "south_east",
)

# The four glyphs a seal can be struck with, and the numbers the page is drawn to.
SEAL_GLYPHS = ("square", "shield", "S", "A")
SEAL_COLOURS = ("#DC6A61", "#6E1A14", "#A83F36")

# The three threshold rewards the board prints beside steps 2, 4, and 6.
ALMS_THRESHOLD_TEXT = (
    "Move a serf from the village to the abbey",
    "Move an acolyte from the abbey to the city",
    "Move a serf directly to the city",
)

DUTY_NAMES = (
    "Produce",
    "Allocation",
    "Clerical",
    "Build Roads",
    "Taxation",
    "Ordination",
    "Construct",
    "Give Alms",
)


def test_ui_debug_index_page_exists() -> None:
    assert INDEX_HTML.is_file()


def test_ui_debug_readme_exists() -> None:
    assert README_MD.is_file()


def test_all_three_prototype_pages_exist() -> None:
    assert MAP_HTML.is_file()
    assert BUILDING_TILES_HTML.is_file()
    assert PLAYER_BOARD_HTML.is_file()


def test_map_prototype_is_identifiable() -> None:
    content = MAP_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Hex" in content
    assert "PILGRIM — Hex Grid" in content


def test_building_tiles_prototype_is_identifiable() -> None:
    content = BUILDING_TILES_HTML.read_text(encoding="utf-8")
    assert "Building Tiles" in content


def test_player_board_prototype_is_identifiable() -> None:
    content = PLAYER_BOARD_HTML.read_text(encoding="utf-8")
    assert "Player Board" in content


def test_player_boards_v2_prototype_page_and_source_exist() -> None:
    assert PLAYER_BOARDS_V2_HTML.is_file()
    assert PLAYER_BOARDS_V2_SOURCE.is_file()
    # v2 is a second baseline, not a replacement: v1 stays where it is.
    assert PLAYER_BOARD_HTML.is_file()


def test_player_boards_v2_prototype_is_identifiable() -> None:
    content = PLAYER_BOARDS_V2_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Player Board" in content
    assert "PILGRIM — Player Board" in content


def test_player_boards_v2_prototype_shows_four_boards_and_the_first_player_marker() -> None:
    content = PLAYER_BOARDS_V2_HTML.read_text(encoding="utf-8")
    assert "Player boards for up to 4 players" in content
    assert "first player marker" in content
    assert content.count("<svg") == 4


def test_player_boards_v2_prototype_source_is_the_generator_code() -> None:
    content = PLAYER_BOARDS_V2_SOURCE.read_text(encoding="utf-8")
    assert "Produces a 2x2 grid of player boards" in content
    assert "first player marker" in content
    assert "red/yellow/blue cubes" in content


def test_special_marker_prototype_pages_exist() -> None:
    assert DONATED_BUILDING_TILES_HTML.is_file()
    assert SHIP_MARKER_HTML.is_file()


def test_donated_building_tiles_prototype_is_identifiable() -> None:
    content = DONATED_BUILDING_TILES_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Special Tiles" in content
    assert "PILGRIM — Special Tiles" in content


def test_ship_marker_prototype_is_identifiable() -> None:
    content = SHIP_MARKER_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Ship Building Tiles" in content
    assert "PILGRIM — Ship Building Tiles" in content


def test_piety_tracks_prototype_page_and_source_exist() -> None:
    assert PIETY_TRACKS_HTML.is_file()
    assert PIETY_TRACKS_SOURCE.is_file()


def test_piety_tracks_prototype_is_identifiable() -> None:
    content = PIETY_TRACKS_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Piety tracks" in content
    assert "Pilgrim — Piety Tracks" in content


def test_piety_tracks_prototype_shows_both_player_count_variants() -> None:
    content = PIETY_TRACKS_HTML.read_text(encoding="utf-8")
    assert "3-4 player" in content
    assert "2 player" in content


def test_piety_tracks_prototype_source_is_the_generator_code() -> None:
    content = PIETY_TRACKS_SOURCE.read_text(encoding="utf-8")
    assert "Horizontal 12-square score/progress track" in content
    assert "render_fused" in content


def test_piety_tracks_v2_prototype_pages_and_source_exist() -> None:
    assert PIETY_TRACKS_V2_HTML.is_file()
    assert PIETY_TRACK_V2_SVG.is_file()
    assert PIETY_TRACK_2P_V2_SVG.is_file()
    assert PIETY_TRACKS_V2_SOURCE.is_file()
    # v2 is a second baseline, not a replacement: v1 stays where it is.
    assert PIETY_TRACKS_HTML.is_file()
    assert PIETY_TRACKS_SOURCE.is_file()


def test_piety_tracks_v2_prototype_is_identifiable() -> None:
    content = PIETY_TRACKS_V2_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Piety Track" in content
    assert "Piety track — with house ornament" in content


def test_piety_tracks_v2_prototype_shows_both_player_count_variants() -> None:
    content = PIETY_TRACKS_V2_HTML.read_text(encoding="utf-8")
    assert "3–4 player" in content
    assert "2 player" in content
    assert content.count("<svg") == 2


def test_piety_tracks_v2_prototype_wears_the_house_ornament() -> None:
    """The point of v2: the inset hairline and the titled header the other boards already have."""
    content = PIETY_TRACKS_V2_HTML.read_text(encoding="utf-8")

    assert "house ornament" in content
    assert "inset" in content
    # v2 puts the board's name in the artwork; v1 leaves it to the HTML heading alone.
    assert "<text" in content
    assert ">Piety Track</text>" in content
    assert ">Piety Track</text>" not in PIETY_TRACKS_HTML.read_text(encoding="utf-8")


def test_piety_track_v2_svg_baselines_are_the_two_tracks_on_their_own() -> None:
    for path in (PIETY_TRACK_V2_SVG, PIETY_TRACK_2P_V2_SVG):
        content = path.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "Piety Track" in content
        assert content.count("<svg") == 1

    # One disc per player, all at position 0: four seats on one track, two on the other.
    assert PIETY_TRACK_V2_SVG.read_text(encoding="utf-8").count('r="9"') == 4
    assert PIETY_TRACK_2P_V2_SVG.read_text(encoding="utf-8").count('r="9"') == 2


def test_piety_tracks_v2_prototype_source_is_the_generator_code() -> None:
    content = PIETY_TRACKS_V2_SOURCE.read_text(encoding="utf-8")

    assert "Piety track with the house ornament applied" in content
    assert "ornament-inset" in content
    assert "ornament-header" in content
    assert "3–4 player" in content
    assert "2 player" in content


def test_pilgrimage_sites_prototype_page_and_source_exist() -> None:
    assert PILGRIMAGE_SITES_HTML.is_file()
    assert PILGRIMAGE_SITES_SOURCE.is_file()


def test_pilgrimage_sites_prototype_is_identifiable() -> None:
    content = PILGRIMAGE_SITES_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Pilgrimage Sites" in content
    assert "PILGRIM — Pilgrimage Sites" in content


def test_pilgrimage_sites_prototype_shows_five_site_tiles() -> None:
    content = PILGRIMAGE_SITES_HTML.read_text(encoding="utf-8")
    assert "5 special" in content
    assert "Pilgrimage Site" in content


def test_pilgrimage_sites_prototype_source_is_the_generator_code() -> None:
    content = PILGRIMAGE_SITES_SOURCE.read_text(encoding="utf-8")
    assert 'Generate the Pilgrim "Pilgrimage Sites" special tiles' in content
    assert "N_TILES = 5" in content


def test_duty_wheel_prototype_pages_and_sources_exist() -> None:
    assert DUTY_WHEEL_HTML.is_file()
    assert DUTY_WHEEL_SVG.is_file()
    assert DUTY_WHEEL_BUILD_SOURCE.is_file()
    assert DUTY_WHEEL_RENDER_SOURCE.is_file()


def test_duty_wheel_prototype_is_identifiable() -> None:
    content = DUTY_WHEEL_HTML.read_text(encoding="utf-8")
    assert "PILGRIM" in content
    assert "City" in content
    assert "Produce" in content
    assert "Taxation" in content


def test_duty_wheel_prototype_names_every_duty_around_the_city() -> None:
    content = DUTY_WHEEL_HTML.read_text(encoding="utf-8")
    for duty in DUTY_NAMES:
        assert duty in content


def test_duty_wheel_prototype_draws_both_families_of_arrows() -> None:
    content = DUTY_WHEEL_HTML.read_text(encoding="utf-8")
    assert "Clockwise outer arrows" in content
    assert "Middle directional arrows" in content


def test_duty_wheel_svg_baseline_is_the_same_board_on_its_own() -> None:
    content = DUTY_WHEEL_SVG.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "City" in content
    assert "Produce" in content
    assert "Taxation" in content


def test_duty_wheel_prototype_sources_are_the_generator_and_render_helper() -> None:
    build = DUTY_WHEEL_BUILD_SOURCE.read_text(encoding="utf-8")
    render = DUTY_WHEEL_RENDER_SOURCE.read_text(encoding="utf-8")

    assert "Build the Pilgrim board" in build
    assert "TILES" in build
    assert "Clockwise outer arrows" in build
    assert "Render pilgrim_board.html" in render
    assert "headless Chromium" in render


def test_alms_table_prototype_pages_and_source_exist() -> None:
    assert ALMS_TABLE_HTML.is_file()
    assert ALMS_TABLE_SVG.is_file()
    assert ALMS_TABLE_SOURCE.is_file()


def test_alms_table_prototype_is_identifiable() -> None:
    content = ALMS_TABLE_HTML.read_text(encoding="utf-8")
    assert "Pilgrim" in content
    assert "Alms" in content
    # The caption drawn on the board, which is what names the component.
    assert "Alms Table" in content


def test_alms_table_prototype_draws_the_race_and_the_season_end_record() -> None:
    """The two halves of the board: the row players race along, and what survives the reset."""
    content = ALMS_TABLE_HTML.read_text(encoding="utf-8")

    assert "1st" in content
    assert "Season end winners" in content
    for text in ALMS_THRESHOLD_TEXT:
        assert text in content


def test_alms_table_svg_baseline_is_the_same_board_on_its_own() -> None:
    content = ALMS_TABLE_SVG.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "Alms Table" in content
    assert "Season end winners" in content


def test_alms_table_prototype_source_is_the_generator_code() -> None:
    content = ALMS_TABLE_SOURCE.read_text(encoding="utf-8")
    assert 'TITLE = "Alms Table"' in content
    assert "Season end winners" in content


def test_seal_prototype_page_exists_and_the_root_is_clear_of_it() -> None:
    """Filed with the other baselines rather than left at the top of the repo where it was drawn.

    Its generator is a module rather than a `prototype_sources` reference copy, because for this
    one page the script is not a throwaway that has to be read for intent: it is still what writes
    the page. `tests/test_ui_debug_seal_renderer.py` is where that end of it is covered.
    """
    assert SEALS_HTML.is_file()
    assert not (PROTOTYPE_SOURCES_DIR / "seal_prototypes.py.txt").exists()
    assert not (REPO_ROOT / "seal_prototypes.html").exists()
    assert not (REPO_ROOT / "build_seal_prototypes.txt").exists()


def test_seal_prototype_shows_four_glyphs_on_the_tile_parchment() -> None:
    """The page is the artwork on its own, so what it is for is the four seals and one background.

    A seal is struck on a duty tile and nowhere else, so the chip behind each one is that tile's
    parchment: judging the wax against anything else would be judging it against a colour it will
    never be seen on.
    """
    content = SEALS_HTML.read_text(encoding="utf-8")

    assert "On the tile parchment" in content
    for glyph in SEAL_GLYPHS:
        assert f"<figcaption>{glyph}</figcaption>" in content
    assert content.count("<svg") == len(SEAL_GLYPHS)
    assert content.count("background:#EFE4C6") == len(SEAL_GLYPHS)


def test_seal_prototype_writes_down_the_geometry_it_was_drawn_to() -> None:
    """Which is the point of it as a debug view: the artwork beside the numbers behind it.

    A glyph has to sit inside the impression ring with wax still showing between the two, and that
    clearance is the whole of what the four seals are being reviewed for. Read off the page rather
    than measured off the picture, so a change to either can be seen against the other.
    """
    content = SEALS_HTML.read_text(encoding="utf-8")

    for measure in ("seal radius", "impression ring", "glyph box", "glyph corner reach"):
        assert measure in content, measure
    assert "clearance" in content
    for colour in SEAL_COLOURS:
        assert colour in content
    # Each colour is named in the table and then used by all four seals.
    assert content.count("#DC6A61") == len(SEAL_GLYPHS) + 1


def test_seal_prototype_is_the_artwork_and_asks_nothing_of_the_page_it_is_on() -> None:
    """No image, no script, no fetch: a baseline that needed any of those could not be a baseline.

    It is a standalone document like every other prototype here, styled in its own head, so it
    opens from the file system on its own and there is nothing for it to drift out of step with.
    """
    content = SEALS_HTML.read_text(encoding="utf-8")

    assert content.startswith("<!DOCTYPE html>")
    assert "<style>" in content
    for asked_for in ("<script", "<img", "<link", "fetch(", ".css", ".png"):
        assert asked_for not in content, asked_for
    # The only address on the page is the SVG namespace, which names a dialect and fetches nothing.
    assert content.count("http") == content.count('xmlns="http://www.w3.org/2000/svg"')


def test_index_page_links_to_every_prototype() -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")
    assert "prototypes/map.html" in content
    assert "prototypes/building_tiles.html" in content
    assert "prototypes/player_board.html" in content
    assert "prototypes/player_boards_v2.html" in content
    assert "Player boards v2 prototype baseline" in content
    assert "prototypes/donated_building_tiles.html" in content
    assert "prototypes/ship_marker.html" in content
    assert "prototypes/piety_tracks.html" in content
    assert "prototypes/piety_tracks_v2.html" in content
    assert "Piety tracks v2 prototype baseline" in content
    assert "prototypes/piety_track_v2.svg" in content
    assert "Piety track v2 SVG prototype baseline" in content
    assert "prototypes/piety_track_2p_v2.svg" in content
    assert "Piety track 2p v2 SVG prototype baseline" in content
    assert "prototypes/pilgrimage_sites.html" in content
    assert "Pilgrimage sites prototype baseline" in content
    assert "prototypes/duty_wheel.html" in content
    assert "Duty wheel prototype baseline" in content
    assert "prototypes/duty_wheel.svg" in content
    assert "Duty wheel SVG prototype baseline" in content
    assert "prototypes/duty_wheel_v2.html" in content
    assert "Duty wheel v2 prototype baseline" in content
    assert "prototypes/duty_wheel_v2.svg" in content
    assert "Duty wheel v2 SVG prototype baseline" in content
    assert "prototypes/alms_table.html" in content
    assert "Alms Table prototype baseline" in content
    assert "prototypes/alms_table.svg" in content
    assert "Alms Table SVG prototype baseline" in content
    assert "prototypes/seal_prototypes.html" in content
    assert "Wax seals prototype baseline" in content


def test_duty_tile_turn_prototype_page_and_source_exist() -> None:
    assert DUTY_TILE_TURN_HTML.is_file()
    assert DUTY_TILE_TURN_SOURCE.is_file()


def test_duty_tile_turn_prototype_is_identifiable() -> None:
    content = DUTY_TILE_TURN_HTML.read_text(encoding="utf-8")
    assert "explain a game turn for Player 3" in content
    assert content.count('class="dgt"') == 9
    # The commentary is the point of this baseline: it is a proposal with its argument attached,
    # and a page that lost the panel would still look right while saying nothing.
    assert content.count('class="n" data-cells') == 7


def test_duty_tile_turn_prototype_carries_its_pictures() -> None:
    """The pictures are embedded, because nothing in the repository serves them.

    They were cropped from images generated with ChatGPT (OpenAI) and live nowhere else in the
    tree -- so a baseline that referenced them by path would render as empty boxes the moment it
    was opened from a checkout, and look like a design decision rather than a missing file.
    """
    content = DUTY_TILE_TURN_HTML.read_text(encoding="utf-8")
    assert "data:image/webp;base64" in content
    assert "src=" not in content.split("<svg", 1)[-1][:2000]


def test_duty_tile_turn_prototype_is_linked_from_the_index() -> None:
    assert "prototypes/duty_tile_turn.html" in INDEX_HTML.read_text(encoding="utf-8")


def test_duty_tile_turn_prototype_records_that_its_art_is_generated() -> None:
    """The one place its provenance is written down.

    `verify_assets.py` walks ui/assets and ui/assets-gothic; nothing checks tools/. The pictures
    here are embedded rather than committed as files, so this README section is the only record
    that they are OpenAI-generated and not hand-drawn.
    """
    readme = README_MD.read_text(encoding="utf-8")
    assert "## Duty tile turn prototype" in readme
    assert "generated with ChatGPT (OpenAI)" in readme
    assert "not** manually illustrated" in readme


# --------------------------------------------------------------------------- duty wheel v2
#
# v2 is the oval wheel. Unlike every other prototype here it is its renderer's OUTPUT rather than
# a hand-drawn baseline, so there is no artwork to protect -- what these guard is the geometry it
# claims, because a wheel that is three per cent asymmetric, or whose channel has drifted, still
# looks exactly like a wheel. Everything below is recomputed from the committed outlines; the
# `checks` block in the layout is checked against that recomputation rather than trusted.


def _v2_layout() -> dict:
    return json.loads(DUTY_WHEEL_V2_LAYOUT.read_text(encoding="utf-8"))


def _v2_points(cell: dict) -> list[tuple[float, float]]:
    """A face's outline from `d_poly`, which is the M/L/Z copy of the Bezier path."""
    n = [float(v) for v in cell["d_poly"].replace("M", " ").replace("L", " ")
         .replace("Z", " ").split()]
    return [(n[i], n[i + 1]) for i in range(0, len(n), 2)]


def _v2_faces() -> dict[str, list[tuple[float, float]]]:
    return {c["position"]: _v2_points(c) for c in _v2_layout()["cells"]}


def _nearest(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    return min(math.dist(p, q) for p in a for q in b)


def _shape_distance(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """How far two outlines are apart AS SHAPES.

    Not a point-by-point difference: a face and its own mirror may be sampled starting at
    different places and running in opposite directions, which says nothing about whether they
    are the same shape.
    """
    return max(max(min(math.dist(p, q) for q in b) for p in a),
               max(min(math.dist(p, q) for p in a) for q in b))


def test_duty_wheel_v2_files_exist() -> None:
    assert DUTY_WHEEL_V2_HTML.is_file()
    assert DUTY_WHEEL_V2_SVG.is_file()
    assert DUTY_WHEEL_V2_LAYOUT.is_file()
    assert DUTY_WHEEL_V2_BUILD.is_file()
    assert DUTY_WHEEL_V2_RENDER.is_file()
    assert DUTY_WHEEL_V2_GENERATE.is_file()
    # v2 is a second baseline, not a replacement: v1 stays where it is.
    assert DUTY_WHEEL_HTML.is_file()
    assert DUTY_WHEEL_SVG.is_file()
    assert (UI_DEBUG_DIR / "duty_wheel_layout.json").is_file()


def test_duty_wheel_v2_prototype_is_identifiable() -> None:
    content = DUTY_WHEEL_V2_HTML.read_text(encoding="utf-8")
    assert "PILGRIM" in content
    assert "Duty wheel v2" in content


def test_duty_wheel_v2_names_its_faces_by_position_and_never_by_duty() -> None:
    """The nine are places, not duties.

    Duty tiles are shuffled at setup, so which duty stands on which face is an arrangement and
    not a fact -- the same point `gen_duty_grid.DUTY_NAMES` makes about its own list. A duty name
    appearing in this layout would be that arrangement quietly hardening into an identity.
    """
    layout = _v2_layout()
    positions = [c["position"] for c in layout["cells"]]
    assert positions == list(DUTY_WHEEL_V2_POSITIONS)
    assert [c["index"] for c in layout["cells"]] == list(range(9))
    blob = json.dumps(layout)
    for duty in DUTY_NAMES:
        assert duty not in blob


def test_duty_wheel_v2_holds_geometry_and_not_gameplay_numbers() -> None:
    layout = _v2_layout()
    assert layout["version"] == 2
    assert set(layout["drawn"]) == {"north_west", "north", "west", "centre"}
    for cell in layout["cells"]:
        assert cell["d"].startswith("M ") and cell["d"].endswith(" Z")
        # cubic Beziers, with an M/L/Z copy beside them because gen_duty_grid._points()
        # parses only M, L and Z
        assert " C " in cell["d"]
        assert " C " not in cell["d_poly"]
        assert len(_v2_points(cell)) == layout["control_points"]


def test_duty_wheel_v2_channel_is_the_width_it_claims() -> None:
    """The frame is the gap between faces, and it is even because both neighbours are inset from
    the same curve. If that ever becomes two separate shrinks these numbers spread."""
    layout = _v2_layout()
    faces = _v2_faces()
    ring = ["north_west", "north", "north_east", "east",
            "south_east", "south", "south_west", "west"]
    between = [_nearest(faces[ring[k]], faces[ring[(k + 1) % 8]]) for k in range(8)]
    around = [_nearest(faces["centre"], faces[n]) for n in ring]

    assert min(between) == pytest.approx(layout["frame"]["between_faces"], abs=0.15)
    assert max(between) == pytest.approx(layout["frame"]["between_faces"], abs=0.15)
    # the heavier ring round the centre sits slightly under its target where the outline curves
    # away from a face; 2% is the measured dip, not a licence to drift
    assert min(around) > layout["frame"]["around_centre"] * 0.97
    assert max(around) < layout["frame"]["around_centre"] * 1.03
    assert min(around) > max(between) * 1.4          # it has to READ as heavier

    assert layout["checks"]["frame_between_faces"] == [
        pytest.approx(min(between), abs=0.02), pytest.approx(max(between), abs=0.02)]
    assert layout["checks"]["frame_around_centre"] == [
        pytest.approx(min(around), abs=0.02), pytest.approx(max(around), abs=0.02)]


def test_duty_wheel_v2_is_mirrored_and_not_rotated() -> None:
    """Five faces are a flip of another and four are their own flip.

    Point symmetry would satisfy a half-turn check and fail this one, which is the distinction
    the wheel was rebuilt for: west is east FLIPPED, not east turned.
    """
    layout = _v2_layout()
    faces = _v2_faces()
    cx = layout["ellipse"]["cx"]
    cy = layout["ellipse"]["cy"]

    def flip(pts, axis):
        return ([(2 * cx - x, y) for x, y in pts] if axis == "vertical"
                else [(x, 2 * cy - y) for x, y in pts])

    worst = 0.0
    for dst, m in layout["mirrors"].items():
        worst = max(worst, _shape_distance(faces[dst], flip(faces[m["of"]], m["axis"])))
    assert worst < 0.01
    assert layout["checks"]["mirror_error"] == pytest.approx(worst, abs=0.01)

    own = max(_shape_distance(faces[n], flip(faces[n], axis)) for n, axis in (
        ("north", "vertical"), ("south", "vertical"), ("east", "horizontal"),
        ("west", "horizontal"), ("centre", "vertical"), ("centre", "horizontal")))
    assert own < 0.01


def test_duty_wheel_v2_stays_inside_its_ellipse() -> None:
    layout = _v2_layout()
    e = layout["ellipse"]
    worst = max(math.hypot((x - e["cx"]) / e["rx"], (y - e["cy"]) / e["ry"])
                for pts in _v2_faces().values() for x, y in pts)
    assert worst <= 1.0
    # and it nearly touches: a wheel sitting well inside its own rim has lost the room it claims
    assert worst > 0.98


def test_duty_wheel_v2_ring_faces_are_within_a_sixth_of_each_other() -> None:
    """Equal 45-degree spokes give equal ellipse sector area, which is what keeps the faces even
    while the wheel still reads as three across the top."""
    faces = _v2_faces()

    def area(pts):
        n = len(pts)
        return 0.5 * abs(sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                             for i in range(n)))

    ring = [area(p) for n, p in faces.items() if n != "centre"]
    assert max(ring) / min(ring) < 1.17


def test_duty_wheel_v2_svg_baseline_is_the_wheel_on_its_own() -> None:
    content = DUTY_WHEEL_V2_SVG.read_text(encoding="utf-8")
    assert content.startswith("<?xml")
    assert "<svg" in content
    for position in DUTY_WHEEL_V2_POSITIONS:
        assert 'id="%s"' % position in content
    # the standalone SVG carries no debug labels, unlike the one embedded in the page
    assert 'id="labels"' not in content
    assert 'id="labels"' in DUTY_WHEEL_V2_HTML.read_text(encoding="utf-8")


def test_duty_wheel_v2_records_that_it_is_its_renderers_output() -> None:
    """The one place the inversion is written down.

    Every other prototype here is a hand-drawn baseline its renderer is measured against. This
    one is generated, so somebody who edits the HTML by hand needs to find out from the README
    that the next run will overwrite them.
    """
    readme = README_MD.read_text(encoding="utf-8")
    assert "## Duty wheel v2 renderer extraction" in readme
    assert "renderer's committed output" in readme
    assert "the v2 duty wheel are the two" in readme
    page = DUTY_WHEEL_V2_HTML.read_text(encoding="utf-8")
    assert "committed output" in page


def test_duty_wheel_v2_records_that_its_aspect_is_unsettled() -> None:
    """The aspect costs 31% of tile area at today's canvas and pays at a wider one. That is a
    live decision, and it travels with the file rather than living in a chat log."""
    layout = _v2_layout()
    assert layout["aspect"] == pytest.approx(1.778, abs=0.001)
    assert "2283" in layout["aspect_is_open"]
    assert "THE ASPECT" in DUTY_WHEEL_V2_BUILD.read_text(encoding="utf-8")
    assert "2283" in README_MD.read_text(encoding="utf-8")


def test_both_duty_wheel_v2_layouts_rebuild_byte_for_byte(tmp_path: Path) -> None:
    """The 1.500 wheel used to be a source file, because nothing could make it again. It is
    output now, and this is what keeps it that way: a layout no script can regenerate goes
    quietly wrong the first time a constant beside it moves, and nothing notices.

    Byte-for-byte, not close-enough. The hub is held as a ratio against the rim it had at 1.778
    precisely so the 1.778 layout comes back unchanged; if that stops being true the refactor has
    silently moved the wheel that everything downstream is measured against.
    """
    pytest.importorskip("numpy", reason="the faces are built from parametric curves")
    for layout, extra in ((DUTY_WHEEL_V2_LAYOUT, ()),
                          (DUTY_WHEEL_V2_LAYOUT_1500, ("--aspect", "1.5"))):
        out = tmp_path / layout.name
        result = subprocess.run(
            [sys.executable, str(DUTY_WHEEL_V2_BUILD), "--out", str(out), *extra],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert result.returncode == 0, (
            "build_duty_wheel_v2.py failed for %s\n\n%s"
            % (layout.name, "\n".join(
                x for x in (result.stdout.strip(), result.stderr.strip()) if x)[-3000:]))
        assert out.read_bytes() == layout.read_bytes(), (
            "%s is no longer what build_duty_wheel_v2.py produces. Either a constant moved and "
            "the file was not regenerated, or the file was edited by hand. Rebuild with\n"
            "    python3 tools/ui_debug/build_duty_wheel_v2.py%s"
            % (layout.name, "".join(" " + a for a in extra) +
               (" --out " + layout.name if extra else "")))


def test_duty_wheel_v2_build_script_is_live_code_and_not_a_frozen_reference() -> None:
    """`build_duty_wheel_v2.py` deliberately breaks this folder's `prototype_sources/*.py.txt`
    rule: the nine outlines are not the base, the constants that produce them are, and one of
    those is still open. A frozen `.txt` copy would mean editing geometry by hand."""
    assert DUTY_WHEEL_V2_BUILD.suffix == ".py"
    assert not (PROTOTYPE_SOURCES_DIR / "duty_wheel_v2_build.py.txt").exists()
    source = DUTY_WHEEL_V2_BUILD.read_text(encoding="utf-8")
    for constant in ("ASPECT", "D_FRAME", "D_HUB", "ROUND_RIM", "HUB_LOBE", "SPOKES"):
        assert constant in source
