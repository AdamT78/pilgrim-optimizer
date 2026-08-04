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
PILGRIMAGE_SITES_HTML = PROTOTYPES_DIR / "pilgrimage_sites.html"
PILGRIMAGE_SITES_SOURCE = PROTOTYPE_SOURCES_DIR / "pilgrimage_sites.py.txt"
DUTY_WHEEL_HTML = PROTOTYPES_DIR / "duty_wheel.html"
DUTY_WHEEL_SVG = PROTOTYPES_DIR / "duty_wheel.svg"
DUTY_WHEEL_BUILD_SOURCE = PROTOTYPE_SOURCES_DIR / "duty_wheel_build.py.txt"
DUTY_WHEEL_RENDER_SOURCE = PROTOTYPE_SOURCES_DIR / "duty_wheel_render.py.txt"

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
    assert "prototypes/pilgrimage_sites.html" in content
    assert "Pilgrimage sites prototype baseline" in content
    assert "prototypes/duty_wheel.html" in content
    assert "Duty wheel prototype baseline" in content
    assert "prototypes/duty_wheel.svg" in content
    assert "Duty wheel SVG prototype baseline" in content
