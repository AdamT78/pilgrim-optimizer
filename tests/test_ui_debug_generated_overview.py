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
    assert written.player_boards_v2 == tmp_path / "player_boards_v2.html"
    assert written.donated_building_tiles == tmp_path / "donated_building_tiles.html"
    assert written.ship_marker == tmp_path / "ship_marker.html"
    assert written.piety_tracks == tmp_path / "piety_tracks.html"
    assert written.piety_tracks_v2 == tmp_path / "piety_tracks_v2.html"
    assert written.pilgrimage_sites == tmp_path / "pilgrimage_sites.html"
    assert written.duty_wheel == tmp_path / "duty_wheel.html"
    assert written.seal_prototypes == tmp_path / "seal_prototypes.html"
    assert written.alms_table == tmp_path / "alms_table.html"
    assert written.game_setup == tmp_path / "game_setup.html"
    assert written.game_table == tmp_path / "game_table.html"
    assert written.overview == tmp_path / "debug_overview.html"
    for path in written.as_tuple():
        assert path.is_file()


def test_the_overview_asks_for_every_page_by_destination_and_writes_nowhere_else(
    tmp_path: Path,
) -> None:
    """The seal generator is the only one whose own default writes a file the repo tracks.

    Everything here is a local artifact, so the overview handing out destinations is what keeps it
    that way. Were it to call that generator bare, a routine rebuild would rewrite a committed page
    -- harmlessly while the two agree, and silently the moment they stop.
    """
    committed = UI_DEBUG_DIR / "prototypes" / "seal_prototypes.html"
    before = committed.read_bytes()

    written = generate_debug_views(output_dir=tmp_path)

    assert committed.read_bytes() == before
    assert all(path.parent == tmp_path for path in written.as_tuple())


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
    boards_v2 = written.player_boards_v2.read_text(encoding="utf-8")
    assert "PILGRIM — Player Board" in boards_v2
    assert "Player boards for up to 4 players" in boards_v2
    assert "PILGRIM — Special Tiles" in written.donated_building_tiles.read_text(encoding="utf-8")
    assert "PILGRIM — Ship Building Tiles" in written.ship_marker.read_text(encoding="utf-8")
    assert "Piety tracks" in written.piety_tracks.read_text(encoding="utf-8")
    piety_v2 = written.piety_tracks_v2.read_text(encoding="utf-8")
    assert "Piety tracks v2" in piety_v2
    assert 'data-component="piety-track-v2"' in piety_v2
    sites = written.pilgrimage_sites.read_text(encoding="utf-8")
    assert "PILGRIM — Pilgrimage Sites" in sites
    duty_wheel = written.duty_wheel.read_text(encoding="utf-8")
    assert "PILGRIM — 3x3 Circle Grid" in duty_wheel
    assert "Merchant token" in duty_wheel
    seals = written.seal_prototypes.read_text(encoding="utf-8")
    assert "Wax seals — isolated" in seals
    assert "On the tile parchment" in seals
    alms_table = written.alms_table.read_text(encoding="utf-8")
    assert "Alms Table" in alms_table
    assert "Season end winners" in alms_table
    assert "PILGRIM — Game Setup Debug View" in written.game_setup.read_text(encoding="utf-8")
    # The table page carries no heading of its own: it opens straight into the boards.
    game_table = written.game_table.read_text(encoding="utf-8")
    assert "<title>Pilgrim — Game Table</title>" in game_table
    assert "game-table-stage" in game_table
    assert 'data-component="alms-table"' in game_table
    assert 'data-component="duty-wheel"' in game_table


def test_overview_page_titles_and_links_generated_views(tmp_path: Path) -> None:
    overview = generate_debug_views(output_dir=tmp_path).overview
    content = overview.read_text(encoding="utf-8")

    assert "Pilgrim UI Debug" in content
    assert "Generated Views" in content
    assert 'href="map.html"' in content
    assert 'href="building_tiles.html"' in content
    assert 'href="player_board.html"' in content
    assert 'href="player_boards_v2.html"' in content
    assert 'href="donated_building_tiles.html"' in content
    assert 'href="ship_marker.html"' in content
    assert 'href="piety_tracks.html"' in content
    assert 'href="piety_tracks_v2.html"' in content
    assert 'href="pilgrimage_sites.html"' in content
    assert 'href="duty_wheel.html"' in content
    assert 'href="seal_prototypes.html"' in content
    assert 'href="alms_table.html"' in content
    assert 'href="game_setup.html"' in content
    assert 'href="game_table.html"' in content


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
    assert "prototypes/player_boards_v2.html" in content
    assert "generated/player_boards_v2.html" in content
    assert "prototypes/donated_building_tiles.html" in content
    assert "generated/donated_building_tiles.html" in content
    assert "prototypes/ship_marker.html" in content
    assert "generated/ship_marker.html" in content
    assert "prototypes/piety_tracks.html" in content
    assert "generated/piety_tracks.html" in content
    assert "prototypes/piety_tracks_v2.html" in content
    assert "generated/piety_tracks_v2.html" in content
    assert "prototypes/pilgrimage_sites.html" in content
    assert "generated/pilgrimage_sites.html" in content
    assert "prototypes/duty_wheel.html" in content
    assert "prototypes/duty_wheel.svg" in content
    assert "generated/duty_wheel.html" in content
    assert "prototypes/seal_prototypes.html" in content
    assert "generated/seal_prototypes.html" in content
    assert "prototypes/alms_table.html" in content
    assert "prototypes/alms_table.svg" in content
    assert "generated/alms_table.html" in content
    assert "generated/game_setup.html" in content
    assert "generated/game_table.html" in content
    assert "Generated game table layout" in content
