import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_player_boards_v2 import (
    default_output_path,
    generate_player_boards_v2_page,
)
from tools.ui_debug.render_player_boards_v2 import (
    board_geometry,
    default_layout_path,
    load_player_boards_v2_layout,
    player_by_id,
    players_of,
    render_player_board_v2_svg,
    render_player_boards_v2_html,
    wrap_label,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
LAYOUT_PATH = UI_DEBUG_DIR / "player_boards_v2_layout.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "player_boards_v2.html"
BASELINE_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "player_boards_v2.py.txt"
PLAYER_BOARD_V1_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "player_board.html"

TITLE = "PILGRIM — Player Board"
SUBTITLE_START = "Player boards for up to 4 players"
PLAYER_COLORS = {
    "player_one": ("white", "#FFFFFF", "#8B7B4E"),
    "player_two": ("red", "#B7382E", "#7A241C"),
    "player_three": ("yellow", "#D9B33B", "#8A6B1E"),
    "player_four": ("blue", "#3B6EA5", "#254A73"),
}
WORKER_ROLES = (
    "Fields",
    "Road Engineer",
    "Stone Mason",
    "Alms House",
    "Engraver",
    "Vestry",
)


@pytest.fixture(scope="module")
def layout() -> dict:
    return load_player_boards_v2_layout()


@pytest.fixture(scope="module")
def page(layout: dict) -> str:
    return render_player_boards_v2_html(layout)


def _svg_bodies(text: str) -> list[str]:
    return re.findall(r"<svg\b.*?</svg>", text, re.S)


def _board_wraps(text: str) -> list[str]:
    return re.findall(r'<div class="board-wrap"[^>]*>', text)


def test_layout_file_exists(layout: dict) -> None:
    assert LAYOUT_PATH.is_file()
    assert default_layout_path() == LAYOUT_PATH
    assert layout["version"] == 1


def test_layout_has_the_four_players_in_seating_order(layout: dict) -> None:
    players = players_of(layout)

    assert len(players) == 4
    assert [player["id"] for player in players] == list(PLAYER_COLORS)
    for player in players:
        color, fill, stroke = PLAYER_COLORS[player["id"]]
        assert (player["color"], player["fill"], player["stroke"]) == (color, fill, stroke)
    with pytest.raises(KeyError):
        player_by_id(layout, "player_five")


def test_layout_names_the_six_worker_roles(layout: dict) -> None:
    roles = layout["worker_roles"]

    assert [role["label"] for role in roles] == list(WORKER_ROLES)
    assert [role["id"] for role in roles] == [
        "fields",
        "road_engineer",
        "stone_mason",
        "alms_house",
        "engraver",
        "vestry",
    ]


def test_layout_holds_the_starting_position(layout: dict) -> None:
    village, abbey = layout["banners"]

    assert (village["label"], abbey["label"]) == ("Village", "Abbey")
    assert layout["starting_worker_grid"] == {"rows": 2, "columns": 4}
    assert (village["visible_workers"], abbey["visible_workers"]) == (8, 3)
    assert layout["placed_workers"] == {"stone_mason": 1, "vestry": 2}
    assert [(r["id"], r["count"]) for r in layout["resources"]] == [
        ("wheat", 1),
        ("stone", 1),
        ("silver", 1),
    ]
    assert layout["building_slot_count"] == 6
    assert layout["grid"]["rows"] == layout["grid"]["columns"] == 2


def test_wrap_label_splits_a_role_name_evenly() -> None:
    assert wrap_label("Fields") == ["Fields"]
    assert wrap_label("Road Engineer") == ["Road", "Engineer"]
    assert wrap_label("First player marker") == ["First player", "marker"]


def test_one_board_draws_its_slots_labels_and_colour_tag(layout: dict) -> None:
    player = player_by_id(layout, "player_three")
    svg = render_player_board_v2_svg(layout, player)
    geometry = board_geometry(len(layout["worker_roles"]))

    assert svg.startswith("<svg") and svg.endswith("</svg>")
    # Six building slots, six worker circles, and three resource circles.
    assert svg.count('stroke-dasharray="5,3"') == layout["building_slot_count"]
    assert svg.count(f'r="{34:g}"') == len(layout["worker_roles"])
    assert svg.count(f'r="{27:g}"') == len(layout["resources"])
    for role in WORKER_ROLES:
        for line in wrap_label(role):
            assert f">{line}</text>" in svg
    assert svg.count(f'fill="{player["fill"]}"') > 0
    assert f'clip-path="url(#panelClip_{player["fill"].lstrip("#")})"' in svg
    assert len(geometry["role_x"]) == len(geometry["building_y"]) == 6


def test_html_shows_four_boards_in_a_two_by_two_grid(page: str) -> None:
    assert page.startswith("<!DOCTYPE html>")
    assert TITLE in page
    assert SUBTITLE_START in page
    assert len(_svg_bodies(page)) == 4
    assert page.count('<div class="board-row">') == 2
    assert page.count('data-component="player-board-v2"') == 4
    assert "<iframe" not in page


def test_html_carries_the_board_labels_and_player_colours(page: str) -> None:
    for text in ("Village", "Abbey", "First player", "marker", *WORKER_ROLES[:1]):
        assert f">{text}</text>" in page
    for role in WORKER_ROLES:
        for line in wrap_label(role):
            assert f">{line}</text>" in page
    for _, fill, stroke in PLAYER_COLORS.values():
        assert fill in page
        assert stroke in page


def test_first_player_marker_is_drawn_once_on_the_white_board(page: str) -> None:
    wraps = _board_wraps(page)

    assert page.count(">First player</text>") == 1
    assert page.count(">marker</text>") == 1
    assert page.count('data-first-player-marker="true"') == 1
    assert 'data-player="player_one" data-player-color="white"' in wraps[0]
    assert 'data-first-player-marker="true"' in wraps[0]
    marker_board = _svg_bodies(page)[0]
    assert ">First player</text>" in marker_board


def test_first_player_can_be_moved_to_another_board(layout: dict) -> None:
    page = render_player_boards_v2_html(layout, first_player="player_two")
    boards = _svg_bodies(page)
    wraps = _board_wraps(page)

    assert page.count(">First player</text>") == 1
    assert ">First player</text>" not in boards[0]
    assert ">First player</text>" in boards[1]
    assert 'data-first-player-marker="false"' in wraps[0]
    assert 'data-first-player-marker="true"' in wraps[1]
    with pytest.raises(KeyError):
        render_player_boards_v2_html(layout, first_player="player_five")


def test_generator_default_output_is_the_generated_player_boards_v2_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "player_boards_v2.html"


def test_generator_writes_generated_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "player_boards_v2.html"
    written = generate_player_boards_v2_page(output_path=output_path)

    assert written == output_path
    content = output_path.read_text(encoding="utf-8")
    assert TITLE in content
    assert len(_svg_bodies(content)) == 4


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    content = BASELINE_PROTOTYPE.read_text(encoding="utf-8")

    assert TITLE in content
    assert SUBTITLE_START in content
    assert "first player marker" in content


def test_baseline_prototype_source_is_untouched() -> None:
    assert BASELINE_SOURCE.is_file()
    content = BASELINE_SOURCE.read_text(encoding="utf-8")

    assert "Produces a 2x2 grid of player boards" in content
    assert "red/yellow/blue cubes" in content


def test_v1_player_board_is_left_alone() -> None:
    """v2 is a second view, not a replacement: the v1 baseline and renderer stay as they were."""
    assert PLAYER_BOARD_V1_PROTOTYPE.is_file()
    assert "Player Board" in PLAYER_BOARD_V1_PROTOTYPE.read_text(encoding="utf-8")
    assert (UI_DEBUG_DIR / "render_player_board.py").is_file()
    assert (UI_DEBUG_DIR / "generate_player_board.py").is_file()
    assert (UI_DEBUG_DIR / "player_board_layout.json").is_file()


def test_generated_boards_are_the_baseline_boards(tmp_path: Path) -> None:
    """Parity is exact here, so the check can be exact: same four SVGs, element for element."""
    generated = generate_player_boards_v2_page(output_path=tmp_path / "player_boards_v2.html")

    assert _svg_bodies(generated.read_text(encoding="utf-8")) == _svg_bodies(
        BASELINE_PROTOTYPE.read_text(encoding="utf-8")
    )


def test_generated_page_matches_baseline_facts(page: str) -> None:
    baseline = BASELINE_PROTOTYPE.read_text(encoding="utf-8")

    for text in (TITLE, SUBTITLE_START, ">First player</text>", ">marker</text>"):
        assert text in baseline
        assert text in page
    for _, fill, _ in PLAYER_COLORS.values():
        assert fill in baseline
        assert fill in page
    assert len(_svg_bodies(baseline)) == len(_svg_bodies(page)) == 4
