import json
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_alms_table import (
    default_output_path,
    generate_alms_table_page,
)
from tools.ui_debug.render_alms_table import (
    RANK_FIRST,
    alms_position_target,
    alms_rules,
    default_alms_config_path,
    default_layout_path,
    disc_center,
    disc_targets,
    initial_positions,
    load_alms_config,
    load_alms_table_layout,
    mover_id,
    mover_path,
    next_mover_position,
    placeholder_slots,
    players_of,
    position_by_index,
    previous_mover_position,
    render_alms_table_html,
    render_alms_table_svg,
    scoring_key_rows,
    season_end_slot_by_index,
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
    # The generated debug page is the one with the controls on it.
    assert "Move Player 1 up" in content
    assert "Add white cube to Season end winner" in content


def test_generator_creates_a_missing_output_directory(tmp_path: Path) -> None:
    destination = tmp_path / "generated" / "alms_table.html"
    generate_alms_table_page(output_path=destination)

    assert destination.is_file()
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "alms_table.html"


def test_a_disc_starts_at_zero_and_walks_up_the_track() -> None:
    board_rules = rules()

    assert initial_positions(layout())[mover_id(layout())] == 0
    assert board_rules.max_position == 6
    assert next_mover_position(board_rules, 0) == 1
    assert next_mover_position(board_rules, 5) == 6
    assert previous_mover_position(board_rules, 6) == 5
    # The first step is the bottom of the track.
    assert previous_mover_position(board_rules, 0) == 0


def test_the_place_past_the_last_step_is_the_first_place_pocket() -> None:
    board_rules = rules()

    assert mover_path(board_rules) == [0, 1, 2, 3, 4, 5, 6, RANK_FIRST]
    assert next_mover_position(board_rules, 6) == RANK_FIRST
    assert next_mover_position(board_rules, RANK_FIRST) == RANK_FIRST
    assert previous_mover_position(board_rules, RANK_FIRST) == 6


def test_a_disc_in_the_first_place_pocket_sits_on_the_pocket_itself() -> None:
    """Not in its seat corner: the pocket holds one disc, so it takes the pocket's centre."""
    mover = players_of(layout())[0]
    pocket = layout()["track"]["bonus_pocket"]

    assert pocket["label"] == "1st"
    assert alms_position_target(layout(), rules(), mover, RANK_FIRST) == (
        pocket["center_x"],
        pocket["center_y"],
    )
    assert alms_position_target(layout(), rules(), mover, 0) == disc_center(layout(), mover, 0)


def test_the_first_place_pocket_is_not_a_season_end_cube_socket() -> None:
    """Two different places: the disc races into one, the cubes are recorded in the other."""
    mover = players_of(layout())[0]
    pocket = alms_position_target(layout(), rules(), mover, RANK_FIRST)
    slot = season_end_slot_by_index(layout(), rules(), 1)

    assert pocket != (slot["center_x"], slot["center_y"])
    # The pocket is down on the race track, left of the divider; the sockets are up in the record.
    assert pocket[0] < slot["center_x"]
    assert pocket[1] > slot["center_y"]


def test_the_track_offers_a_target_for_every_place_a_disc_can_stand() -> None:
    targets = disc_targets(layout(), rules(), "player_one")

    assert sorted(targets) == ["0", "1", "2", "3", "4", "5", "6", RANK_FIRST]
    steps = [targets[str(index)] for index in range(rules().max_position + 1)]
    assert [x for x, _ in steps] == sorted(x for x, _ in steps)
    assert steps[0] == list(disc_center(layout(), players_of(layout())[0], 0))
    # The pocket is one more space along the track, past the last step.
    assert targets[RANK_FIRST][0] > steps[-1][0]


def test_winner_slots_can_be_looked_up_by_number() -> None:
    slot = season_end_slot_by_index(layout(), rules(), 1)

    assert slot["slot"] == 1
    assert slot["center_x"] == placeholder_slots(layout(), rules())[0]["center_x"]
    with pytest.raises(KeyError):
        season_end_slot_by_index(layout(), rules(), 5)


def test_winner_cubes_are_the_player_board_v2_cubes() -> None:
    """They are the player's own cube moved onto this board, not a new piece."""
    v2 = json.loads(
        (UI_DEBUG_DIR / "player_boards_v2_layout.json").read_text(encoding="utf-8")
    )
    v2_cubes = {player["id"]: (player["fill"], player["stroke"]) for player in v2["players"]}

    for player in players_of(layout()):
        assert (player["cube_fill"], player["cube_stroke"]) == v2_cubes[player["id"]]


def test_the_static_board_carries_no_controls_or_hidden_slots() -> None:
    """Asked for the picture, the renderer draws the picture, so baseline parity holds."""
    content = render_alms_table_html(layout(), config())

    assert "data-season-end-winner-slot" not in content
    assert "data-alms-discs" not in content
    assert "<script" not in content
    assert "Move Player 1 up" not in content


def test_the_interactive_page_offers_every_control() -> None:
    content = render_alms_table_html(layout(), config(), interactive=True)

    assert "Move Player 1 up" in content
    assert "Move Player 1 down" in content
    for color in PLAYER_COLORS:
        assert f"Add {color} cube to Season end winner" in content
    assert 'data-player="player_one"' in content
    assert 'data-player-disc="true"' in content
    assert 'data-placeholder-slot="1"' in content


def test_the_interactive_page_opens_in_the_state_it_says_it_is_in() -> None:
    """Rendered ready, so the page reads correctly even before the script runs."""
    content = render_alms_table_html(layout(), config(), interactive=True)

    assert "Player 1 on step 0 &middot; 0 of 4 winner cubes" in content
    # Nobody can move below the first step, so the button says so from the start.
    assert re.search(r'id="alms-move-down"\s+disabled', content)
    assert not re.search(r'id="alms-move-up"\s+disabled', content)


def test_every_winner_cube_is_drawn_once_per_slot_and_starts_hidden() -> None:
    content = render_alms_table_svg(layout(), config(), interactive=True)

    cubes = re.findall(r"<rect[^>]*data-season-end-winner-slot=\"(\d)\"[^>]*/>", content)
    assert len(cubes) == 4 * len(PLAYER_IDS)
    assert sorted(set(cubes)) == ["1", "2", "3", "4"]
    hidden = re.findall(r"<rect[^>]*data-season-end-winner-slot[^>]*/>", content)
    assert all('opacity="0"' in cube for cube in hidden)


def _box(element: str) -> tuple[float, float, float, float]:
    def value(name: str) -> float:
        return float(re.search(rf'\b{name}="([\d.]+)"', element).group(1))

    return value("x"), value("y"), value("width"), value("height")


def test_a_winner_cube_covers_the_slot_it_fills() -> None:
    """Exactly the placeholder's box, so no dashed edge is left showing around a placed cube."""
    content = render_alms_table_svg(layout(), config(), interactive=True)

    placeholder = re.search(r'<rect[^>]*data-placeholder-slot="1"[^>]*/>', content).group()
    cube = re.search(
        r'<rect[^>]*data-season-end-winner-slot="1"[^>]*data-player="player_one"[^>]*/>', content
    ).group()

    assert _box(cube) == _box(placeholder)
    # And the script takes the socket out from under it, so no dash can peek past the stroke.
    page = render_alms_table_html(layout(), config(), interactive=True)
    assert 'board.querySelector(\'[data-placeholder-slot="\' + slot + \'"]\');' in page
    assert 'placeholder.setAttribute("opacity", "0");' in page


def test_the_page_carries_the_path_the_disc_walks() -> None:
    """The whole of the movement rule, handed to the page as data rather than as branches."""
    content = render_alms_table_html(layout(), config(), interactive=True)

    assert f"var PATH = {json.dumps(mover_path(rules()))};" in content
    # Both ends of it are where the buttons switch off.
    assert "up.disabled = at === PATH[PATH.length - 1];" in content
    assert "down.disabled = at === PATH[0];" in content


def test_the_page_carries_the_pocket_the_disc_moves_to_not_a_cube_socket() -> None:
    content = render_alms_table_html(layout(), config(), interactive=True)
    pocket = layout()["track"]["bonus_pocket"]
    slot = season_end_slot_by_index(layout(), rules(), 1)

    target = json.dumps({RANK_FIRST: [pocket["center_x"], pocket["center_y"]]}).strip("{}")
    assert target in content
    assert json.dumps([slot["center_x"], slot["center_y"]]) not in content
    # The pocket is labelled on the board and hooked for the disc that lands in it.
    assert f'data-alms-position="{RANK_FIRST}"' in content
    assert 'data-alms-bonus-pocket="true"' in content


def test_the_moving_disc_is_drawn_after_the_pocket_it_can_land_in() -> None:
    """The pocket is painted solid, so a disc drawn before it would slide in behind it."""
    content = render_alms_table_svg(layout(), config(), interactive=True)

    assert content.index('data-alms-bonus-pocket="true"') < content.index('data-alms-discs="true"')


def test_a_movable_disc_is_not_parented_to_the_step_it_started_on() -> None:
    """It slides along the track, so it lives in its own layer rather than in a step group."""
    content = render_alms_table_svg(layout(), config(), interactive=True)

    disc_layer = re.search(r'<g data-alms-discs="true">(.*?)</g>', content, re.S)
    assert disc_layer is not None
    assert disc_layer.group(1).count("data-player-disc") == len(PLAYER_IDS)
    # The step groups keep their labels and reward ticks, but hold no discs.
    for group in re.findall(r'<g data-alms-position="\d">(.*?)</g>', content, re.S):
        assert "data-player-disc" not in group


def test_the_controls_script_keeps_itself_to_itself() -> None:
    content = render_alms_table_html(layout(), config(), interactive=True)

    assert "initAlmsTableControls" in content
    assert "})();" in content
    # Namespaced hooks, so this can join a page that already has controls of its own.
    for hook in ("alms-move-up", "alms-move-down", "alms-readout", "alms-table-controls"):
        assert hook in content
    assert "React" not in content
    assert "<iframe" not in content


def _drawing_elements(content: str) -> list[str]:
    """Every drawn element, stripped of the data hooks the baseline has no need for."""
    found = re.findall(r"<(?:rect|circle|line|path|text)\b[^>]*?(?:/>|>[^<]*</text>)", content)
    return [re.sub(r'\s*data-[a-z-]+="[^"]*"', "", element) for element in found]


def _is_step_disc(element: str) -> bool:
    return element.startswith("<circle") and ' r="9"' in element and "dasharray" not in element


def _is_cube(element: str) -> bool:
    size = layout()["record"]["cube"]["size"]
    return element.startswith("<rect") and f' width="{size:g}"' in element


def _one_cube_stroke(element: str) -> str:
    """The baseline drew each kind of cube at its own weight; the renderer settles on one."""
    width = layout()["record"]["cube"]["stroke_width"]
    return re.sub(r'stroke-width="[\d.]+"', f'stroke-width="{width:g}"', element)


def test_generated_board_matches_the_baseline_element_for_element() -> None:
    """Only the discs and the cube strokes differ, and both are deliberate."""
    baseline = _drawing_elements(BASELINE_SVG.read_text(encoding="utf-8"))
    generated = _drawing_elements(svg())

    on_step_zero = {
        f'cx="{x:.1f}"' for x, _ in (disc_center(layout(), p, 0) for p in players_of(layout()))
    }
    expected = [
        _one_cube_stroke(element) if _is_cube(element) else element
        for element in baseline
        if not (_is_step_disc(element) and not any(c in element for c in on_step_zero))
    ]

    assert generated == expected
    # Six steps of four diagram discs each, which the generated board leaves empty.
    assert len(baseline) - len(expected) == 24
    # Four sockets and ten key cubes, all restroked, and nothing else touched.
    assert len([element for element in baseline if _is_cube(element)]) == 14


def test_every_cube_on_the_board_is_drawn_at_one_weight() -> None:
    """Socket, winner's cube, and printed key cube are the same piece, so they read alike."""
    content = render_alms_table_svg(layout(), config(), interactive=True)
    width = layout()["record"]["cube"]["stroke_width"]

    cubes = [element for element in _drawing_elements(content) if _is_cube(element)]
    # Four sockets, ten printed key cubes, and a hidden winner's cube per player per socket.
    assert len(cubes) == 14 + 4 * len(PLAYER_IDS)
    assert all(f'stroke-width="{width:g}"' in cube for cube in cubes)
    # The same weight Player Board v2 draws its cubes at, since it is the same piece.
    assert width == 1.2


def test_baseline_prototypes_are_still_present_and_untouched() -> None:
    for path in (BASELINE_HTML, BASELINE_SVG):
        content = path.read_text(encoding="utf-8")
        assert "Alms Table" in content
        assert "data-component" not in content


def test_prototype_source_is_still_the_reference_copy() -> None:
    content = BASELINE_SOURCE.read_text(encoding="utf-8")

    assert 'TITLE = "Alms Table"' in content
