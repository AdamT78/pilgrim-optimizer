from pathlib import Path

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
    assert "prototypes/alms_table.html" in content
    assert "Alms Table prototype baseline" in content
    assert "prototypes/alms_table.svg" in content
    assert "Alms Table SVG prototype baseline" in content
    assert "prototypes/seal_prototypes.html" in content
    assert "Wax seals prototype baseline" in content
