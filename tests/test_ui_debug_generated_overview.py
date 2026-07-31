from pathlib import Path

from tools.ui_debug.generate_debug_overview import (
    default_output_dir,
    generate_debug_views,
    render_debug_overview_html,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
GENERATOR_SCRIPT = UI_DEBUG_DIR / "generate_debug_overview.py"
INDEX_HTML = UI_DEBUG_DIR / "index.html"


def test_overview_generator_script_exists() -> None:
    assert GENERATOR_SCRIPT.is_file()
    assert default_output_dir() == UI_DEBUG_DIR / "generated"


def test_generator_writes_all_pages_to_a_temp_directory(tmp_path: Path) -> None:
    written = generate_debug_views(output_dir=tmp_path)

    assert written.map_page == tmp_path / "map.html"
    assert written.building_tiles == tmp_path / "building_tiles.html"
    assert written.player_board == tmp_path / "player_board.html"
    assert written.donated_building_tiles == tmp_path / "donated_building_tiles.html"
    assert written.ship_marker == tmp_path / "ship_marker.html"
    assert written.overview == tmp_path / "debug_overview.html"
    for path in written.as_tuple():
        assert path.is_file()


def test_generator_creates_missing_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    written = generate_debug_views(output_dir=output_dir)

    assert output_dir.is_dir()
    assert written.overview.is_file()


def test_generated_pages_contain_their_own_views(tmp_path: Path) -> None:
    written = generate_debug_views(output_dir=tmp_path)

    assert "PILGRIM — Hex Grid" in written.map_page.read_text(encoding="utf-8")
    assert "PILGRIM — Building Tiles" in written.building_tiles.read_text(encoding="utf-8")
    assert "PILGRIM — Player Board" in written.player_board.read_text(encoding="utf-8")
    assert "PILGRIM — Special Tiles" in written.donated_building_tiles.read_text(encoding="utf-8")
    assert "PILGRIM — Ship Building Tiles" in written.ship_marker.read_text(encoding="utf-8")


def test_overview_page_titles_and_links_generated_views(tmp_path: Path) -> None:
    overview = generate_debug_views(output_dir=tmp_path).overview
    content = overview.read_text(encoding="utf-8")

    assert "Pilgrim UI Debug" in content
    assert "Generated Views" in content
    assert 'href="map.html"' in content
    assert 'href="building_tiles.html"' in content
    assert 'href="player_board.html"' in content
    assert 'href="donated_building_tiles.html"' in content
    assert 'href="ship_marker.html"' in content


def test_overview_page_states_current_limitations() -> None:
    content = render_debug_overview_html()

    assert "Generated map rendering is visual/debug only" in content
    assert "Map rendering is still baseline-only." not in content
    assert "No GameState integration yet." in content
    assert "No gameplay rules are implemented in the UI layer." in content


def test_overview_page_does_not_use_iframes() -> None:
    assert "<iframe" not in render_debug_overview_html()


def test_prototype_index_links_to_generated_overview() -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")

    assert "generated/debug_overview.html" in content
    assert "Generated debug overview" in content
    assert "prototypes/map.html" in content
    assert "generated/map.html" in content
    assert "prototypes/building_tiles.html" in content
    assert "generated/building_tiles.html" in content
    assert "prototypes/player_board.html" in content
    assert "generated/player_board.html" in content
    assert "prototypes/donated_building_tiles.html" in content
    assert "generated/donated_building_tiles.html" in content
    assert "prototypes/ship_marker.html" in content
    assert "generated/ship_marker.html" in content
