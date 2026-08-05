import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_alms_table import (
    default_output_path,
    generate_alms_table_page,
)
from tools.ui_debug.render_alms_table import (
    alms_rules,
    default_alms_config_path,
    default_layout_path,
    disc_center,
    initial_positions,
    load_alms_config,
    load_alms_table_layout,
    placeholder_slots,
    players_of,
    position_by_index,
    render_alms_table_html,
    render_alms_table_svg,
    scoring_key_rows,
    step_centers,
    threshold_rewards,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
PROTOTYPES_DIR = UI_DEBUG_DIR / "prototypes"

LAYOUT_JSON = UI_DEBUG_DIR / "alms_table_layout.json"
BASELINE_HTML = PROTOTYPES_DIR / "alms_table.html"
BASELINE_SVG = PROTOTYPES_DIR / "alms_table.svg"
BASELINE_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "alms_table.py.txt"

PLAYER_IDS = ("player_one", "player_two", "player_three", "player_four")
PLAYER_COLORS = ("white", "red", "yellow", "blue")
SEASON_END_VP = (5, 11, 18, 26)
THRESHOLD_POSITIONS = (2, 4, 6)


def layout() -> dict:
    return load_alms_table_layout()


def config() -> dict:
    return load_alms_config()


def rules():
    return alms_rules(config())


def svg() -> str:
    return render_alms_table_svg(layout(), config())


def test_layout_and_config_are_where_the_renderer_looks_for_them() -> None:
    assert LAYOUT_JSON.is_file()
    assert default_layout_path() == LAYOUT_JSON
    assert default_alms_config_path() == REPO_ROOT / "configs" / "alms.json"


def test_layout_anchors_every_alms_position_the_config_defines() -> None:
    centers = step_centers(layout())

    assert len(centers) == rules().max_position + 1
    assert centers == sorted(centers)
    assert position_by_index(layout(), 0)["label"] == "0"
    assert position_by_index(layout(), 6)["center_x"] == centers[6]


def test_asking_for_a_step_off_the_track_is_an_error() -> None:
    with pytest.raises(KeyError):
        position_by_index(layout(), 7)


def test_a_layout_that_disagrees_with_the_config_is_rejected() -> None:
    """The board must not quietly draw a different track from the one the rules use."""
    short = layout()
    short["track"]["step_centers"] = short["track"]["step_centers"][:-1]

    with pytest.raises(ValueError, match="steps"):
        render_alms_table_svg(short, config())


def test_reward_rows_come_from_the_config_and_read_from_the_layout() -> None:
    rewards = threshold_rewards(layout(), rules())

    assert [reward["position"] for reward in rewards] == list(THRESHOLD_POSITIONS)
    assert [reward["reward"] for reward in rewards] == [
        "village_to_abbey",
        "abbey_to_city",
        "village_to_city",
    ]
    assert rewards[0]["text"] == "Move a serf from the village to the abbey"
    # Stacked one line under the next.
    assert [reward["center_y"] for reward in rewards] == [156.0, 180.0, 204.0]


def test_a_reward_with_no_prose_is_an_error() -> None:
    without_text = layout()
    without_text["reward_text"].pop("abbey_to_city")

    with pytest.raises(ValueError, match="reward text"):
        threshold_rewards(without_text, rules())


def test_scoring_key_prints_the_configured_vp_per_cube() -> None:
    rows = scoring_key_rows(layout(), rules())

    assert [row["cubes"] for row in rows] == [1, 2, 3, 4]
    assert [row["vp"] for row in rows] == list(SEASON_END_VP)
    # Owning nothing scores nothing, so the board has no row for it.
    assert all(row["cubes"] > 0 for row in rows)


def test_one_placeholder_slot_per_scoring_row() -> None:
    slots = placeholder_slots(layout(), rules())

    assert [slot["slot"] for slot in slots] == [1, 2, 3, 4]
    assert [slot["round"] for slot in slots] == [1, 2, 3, 4]
    assert len(slots) == len(scoring_key_rows(layout(), rules()))
    assert [slot["center_x"] for slot in slots] == sorted(slot["center_x"] for slot in slots)


def test_layout_seats_four_players_by_colour() -> None:
    players = players_of(layout())

    assert [player["id"] for player in players] == list(PLAYER_IDS)
    assert [player["color"] for player in players] == list(PLAYER_COLORS)
    # Each player owns one corner of the 2x2, so four discs on a step stay legible.
    assert len({(p["seat"]["column"], p["seat"]["row"]) for p in players}) == 4


def test_every_player_starts_on_position_zero() -> None:
    assert initial_positions(layout()) == dict.fromkeys(PLAYER_IDS, 0)


def test_discs_are_spread_around_the_centre_of_their_step() -> None:
    data = layout()
    centers = [disc_center(data, player, 0) for player in players_of(data)]

    assert len(set(centers)) == 4
    xs = [x for x, _ in centers]
    ys = [y for _, y in centers]
    assert sum(xs) / len(xs) == position_by_index(data, 0)["center_x"]
    assert sum(ys) / len(ys) == data["track"]["disc_grid_center_y"]


def test_renderer_returns_an_svg_tagged_as_the_alms_table() -> None:
    content = svg()

    assert content.startswith("<svg")
    assert content.endswith("</svg>")
    assert 'data-component="alms-table"' in content


def test_svg_prints_the_board_title_and_both_zones() -> None:
    content = svg()

    assert "Alms Table" in content
    assert "Season end winners" in content
    assert "1st" in content


def test_svg_labels_every_step_and_its_rewards() -> None:
    content = svg()

    for index in range(7):
        assert f'data-alms-position="{index}"' in content
    for position in THRESHOLD_POSITIONS:
        assert f'data-alms-threshold="{position}"' in content
    for reward in threshold_rewards(layout(), rules()):
        assert reward["text"] in content


def test_svg_prints_the_season_end_values() -> None:
    content = svg()

    for rank, vp in enumerate(SEASON_END_VP, start=1):
        assert f'data-season-end-rank="{rank}"' in content
        assert f'data-season-end-vp="{vp}"' in content
        assert f">{vp}</text>" in content


def test_svg_draws_exactly_four_discs_all_on_position_zero() -> None:
    content = svg()

    discs = re.findall(r"<circle[^>]*data-player-disc=\"true\"[^>]*/>", content)
    assert len(discs) == 4
    for player_id in PLAYER_IDS:
        assert f'data-player="{player_id}"' in content
    assert all('data-alms-position="0"' in disc for disc in discs)


def test_discs_can_be_moved_along_the_track_without_any_controls() -> None:
    """The renderer takes disc positions; a later PR moves them without new geometry."""
    data = layout()
    moved = render_alms_table_svg(data, config(), {**initial_positions(data), "player_two": 4})

    disc = re.search(r"<circle[^>]*data-player=\"player_two\"[^>]*/>", moved)
    assert disc is not None
    assert 'data-alms-position="4"' in disc.group(0)
    expected_x, _ = disc_center(data, players_of(data)[1], 4)
    assert f'cx="{expected_x:.1f}"' in disc.group(0)


def test_svg_draws_a_dashed_placeholder_for_every_round() -> None:
    content = svg()

    for slot in (1, 2, 3, 4):
        assert f'data-placeholder-slot="{slot}"' in content
    slots = re.findall(r"<rect[^>]*data-placeholder-slot=\"\d\"[^>]*/>", content)
    assert len(slots) == 4
    assert all("stroke-dasharray" in slot for slot in slots)


def test_html_page_wraps_the_board_and_names_it() -> None:
    content = render_alms_table_html(layout(), config())

    assert content.startswith("<!DOCTYPE html>")
    assert "<h1>Alms Table</h1>" in content
    assert 'data-component="alms-table"' in content
    assert 'data-player="player_one"' in content
    assert 'data-placeholder-slot="1"' in content
    assert "<iframe" not in content


def test_renderer_is_deterministic() -> None:
    assert render_alms_table_html(layout(), config()) == render_alms_table_html(layout(), config())


def test_generator_writes_the_page_to_a_temp_path(tmp_path: Path) -> None:
    destination = tmp_path / "alms_table.html"
    written = generate_alms_table_page(output_path=destination)

    assert written == destination
    content = destination.read_text(encoding="utf-8")
    assert "Alms Table" in content
    assert 'data-component="alms-table"' in content


def test_generator_creates_a_missing_output_directory(tmp_path: Path) -> None:
    destination = tmp_path / "generated" / "alms_table.html"
    generate_alms_table_page(output_path=destination)

    assert destination.is_file()
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "alms_table.html"


def _drawing_elements(content: str) -> list[str]:
    """Every drawn element, stripped of the data hooks the baseline has no need for."""
    found = re.findall(r"<(?:rect|circle|line|path|text)\b[^>]*?(?:/>|>[^<]*</text>)", content)
    return [re.sub(r'\s*data-[a-z-]+="[^"]*"', "", element) for element in found]


def _is_step_disc(element: str) -> bool:
    return element.startswith("<circle") and ' r="9"' in element and "dasharray" not in element


def test_generated_board_matches_the_baseline_element_for_element() -> None:
    """Only the discs differ: the baseline diagrams all seven steps, this draws player state."""
    baseline = _drawing_elements(BASELINE_SVG.read_text(encoding="utf-8"))
    generated = _drawing_elements(svg())

    on_step_zero = {
        f'cx="{x:.1f}"' for x, _ in (disc_center(layout(), p, 0) for p in players_of(layout()))
    }
    expected = [
        element
        for element in baseline
        if not (_is_step_disc(element) and not any(c in element for c in on_step_zero))
    ]

    assert generated == expected
    # Six steps of four diagram discs each, which the generated board leaves empty.
    assert len(baseline) - len(expected) == 24


def test_baseline_prototypes_are_still_present_and_untouched() -> None:
    for path in (BASELINE_HTML, BASELINE_SVG):
        content = path.read_text(encoding="utf-8")
        assert "Alms Table" in content
        assert "data-component" not in content


def test_prototype_source_is_still_the_reference_copy() -> None:
    content = BASELINE_SOURCE.read_text(encoding="utf-8")

    assert 'TITLE = "Alms Table"' in content
