from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
PROTOTYPES_DIR = UI_DEBUG_DIR / "prototypes"

INDEX_HTML = UI_DEBUG_DIR / "index.html"
README_MD = UI_DEBUG_DIR / "README.md"
MAP_HTML = PROTOTYPES_DIR / "map.html"
BUILDING_TILES_HTML = PROTOTYPES_DIR / "building_tiles.html"
PLAYER_BOARD_HTML = PROTOTYPES_DIR / "player_board.html"


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


def test_index_page_links_to_every_prototype() -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")
    assert "prototypes/map.html" in content
    assert "prototypes/building_tiles.html" in content
    assert "prototypes/player_board.html" in content
