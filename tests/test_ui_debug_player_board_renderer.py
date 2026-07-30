from pathlib import Path

from tools.ui_debug.generate_player_board import (
    default_output_path,
    generate_player_board_page,
)
from tools.ui_debug.render_player_board import (
    default_layout_path,
    default_player_state,
    load_player_board_layout,
    render_player_board_svg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
LAYOUT_PATH = UI_DEBUG_DIR / "player_board_layout.json"
BASELINE_PROTOTYPE = UI_DEBUG_DIR / "prototypes" / "player_board.html"

EXPECTED_SPECIAL_ACTIVITY_IDS = (
    "fields",
    "road_engineer",
    "stone_mason",
    "alms_house",
    "engraver",
    "vestry",
)

EXPECTED_SVG_TEXT = (
    "Village",
    "Abbey",
    "Player",
    "Fields",
    "Road",
    "Engineer",
    "Stone",
    "Mason",
    "Alms",
    "House",
    "Engraver",
    "Vestry",
)


def test_player_board_layout_file_exists() -> None:
    assert LAYOUT_PATH.is_file()
    assert default_layout_path() == LAYOUT_PATH


def test_layout_contains_village_abbey_and_player_banners() -> None:
    layout = load_player_board_layout()
    banners = {banner["id"]: banner for banner in layout["banners"]}
    assert banners["village"]["label"] == "Village"
    assert banners["abbey"]["label"] == "Abbey"
    assert banners["player"]["label"].startswith("Player")
    assert len(layout["village_slots"]) == 8
    assert len(layout["abbey_slots"]) == 8


def test_layout_contains_six_special_activities() -> None:
    layout = load_player_board_layout()
    activity_ids = tuple(activity["id"] for activity in layout["special_activities"])
    assert activity_ids == EXPECTED_SPECIAL_ACTIVITY_IDS


def test_layout_contains_wheat_stone_and_silver_resources() -> None:
    layout = load_player_board_layout()
    resource_ids = [resource["id"] for resource in layout["resources"]]
    assert resource_ids == ["wheat", "stone", "silver"]


def test_render_player_board_svg_returns_svg_string() -> None:
    svg = render_player_board_svg(load_player_board_layout(), default_player_state())
    assert isinstance(svg, str)
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")


def test_rendered_svg_contains_banner_and_activity_labels() -> None:
    svg = render_player_board_svg(load_player_board_layout(), default_player_state())
    for expected_text in EXPECTED_SVG_TEXT:
        assert expected_text in svg


def test_rendered_svg_uses_beige_prototype_colors() -> None:
    svg = render_player_board_svg(load_player_board_layout(), default_player_state())
    assert "#E4D9BC" in svg
    assert "#EFE4C6" in svg
    assert "#D8CCA9" in svg


def test_rendered_svg_reflects_mock_player_state() -> None:
    layout = load_player_board_layout()
    player_state = {
        "player_label": "Player: player_one",
        "village_count": 2,
        "abbey_count": 0,
        "resources": {"wheat": 4, "stone": 5, "silver": 6},
        "occupied_special_activities": {"fields": 1},
    }
    svg = render_player_board_svg(layout, player_state)

    assert "Player: player_one" in svg
    assert svg.count('opacity="1"') == 2
    assert ">4</text>" in svg
    assert ">5</text>" in svg
    assert ">6</text>" in svg


def test_generator_default_output_is_generated_player_board_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "player_board.html"


def test_generator_writes_generated_player_board_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "player_board.html"
    written = generate_player_board_page(output_path=output_path)

    assert written == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "PILGRIM — Player Board" in content


def test_baseline_prototype_is_untouched() -> None:
    assert BASELINE_PROTOTYPE.is_file()
    assert "PILGRIM — Player Board" in BASELINE_PROTOTYPE.read_text(encoding="utf-8")
