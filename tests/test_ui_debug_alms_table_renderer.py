import json
import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_alms_table import (
    default_output_path,
    generate_alms_table_page,
)
from tools.ui_debug.render_alms_table import (
    CUBE_GAP,
    CUBE_PITCH,
    CUBE_SIZE,
    INK_FONT,
    ORNAMENT_RULE_CLEARANCE,
    ORNAMENT_RULE_GAP,
    ORNAMENT_STROKE_WIDTH,
    ORNAMENT_TREFOIL_RADIUS,
    PLAYER_CUBE_GAP,
    PLAYER_UNIT,
    RANK_FIRST,
    SEASON_END_LABEL_FONT_SIZE,
    STAR_INNER_RADIUS,
    STAR_LABEL_FONT_SIZE,
    STAR_LABEL_OFFSET,
    STAR_OUTER_RADIUS,
    STEP_NUMBER_FONT_SIZE,
    THRESHOLD_LABEL_FONT_SIZE,
    alms_position_target,
    alms_rules,
    bonus_pocket_center_x,
    cube_rect,
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
    ornament_rule_arm,
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
from tools.ui_debug.render_duty_wheel import (
    CUBE_COLUMN_WIDTH as DUTY_CUBE_COLUMN_WIDTH,
)
from tools.ui_debug.render_duty_wheel import CUBE_SIZE as DUTY_CUBE_SIZE
from tools.ui_debug.render_duty_wheel import (
    ORNAMENT_RULE_GAP as DUTY_ORNAMENT_RULE_GAP,
)
from tools.ui_debug.render_duty_wheel import (
    ORNAMENT_TREFOIL_RADIUS as DUTY_ORNAMENT_TREFOIL_RADIUS,
)
from tools.ui_debug.render_player_boards_v2 import (
    MARKER_CUBE,
    ROLE_FONT_SIZE,
    TOKEN_GAP,
    TOKEN_RADIUS,
    load_player_boards_v2_layout,
)
from tools.ui_debug.render_player_boards_v2 import (
    board_geometry as player_board_geometry,
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

# Where `Alms Table` stops. There is no font metric to compute this from, so it is measured: at the
# title's 15 units of Georgia bold the text runs from x=15.6 to here. It is what the header rule's
# left arm has to stay clear of, and the only reason that arm is not free to be any length.
TITLE_RIGHT_EDGE = 101.9

# What the board measured before the pass that widened it to the width of a seat. The tests keep
# these so they can say which way each number moved, rather than only pinning it where it landed.
BEFORE_WIDENING = {
    "panel_width": 517.0,
    "divider_x": 379.0,
    "record_x": 392.0,
    "record_width": 111.0,
    "rule_span": 111.0,
    "right_margin": 14.0,
    "cube_size": 13,
    "heading_font_size": 9.5,
    "pocket_center_x": 344.0,
    "trefoil_rule_span": 256.0,
    "star_outer_radius": 16,
    "star_label_font_size": 9,
}


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
        bonus_pocket_center_x(layout()),
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
    v2 = json.loads((UI_DEBUG_DIR / "player_boards_v2_layout.json").read_text(encoding="utf-8"))
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
    assert "board.querySelector('[data-placeholder-slot=\"' + slot + '\"]');" in page
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

    center = [bonus_pocket_center_x(layout()), pocket["center_y"]]
    target = json.dumps({RANK_FIRST: center}).strip("{}")
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
    return element.startswith("<rect") and f' width="{CUBE_SIZE:.1f}"' in element


def _one_cube_stroke(element: str) -> str:
    """The baseline drew each kind of cube at its own weight; the renderer settles on one."""
    width = layout()["record"]["cube"]["stroke_width"]
    return re.sub(r'stroke-width="[\d.]+"', f'stroke-width="{width:g}"', element)


def test_the_race_track_survived_the_widening_element_for_element() -> None:
    """The board is wider than the baseline now, but the race it draws is the baseline's own.

    Only the record side was meant to move. The steps, the rules between them, the ticks under the
    steps that pay and the reward lines underneath are all still the prototype's elements, byte for
    byte, which is the thing a width change is most likely to disturb without anyone noticing.
    """
    baseline = _drawing_elements(BASELINE_SVG.read_text(encoding="utf-8"))
    kept = set(baseline) & set(_drawing_elements(svg()))

    numbered = [
        element
        for element in kept
        if element.startswith("<text") and f'font-size="{STEP_NUMBER_FONT_SIZE:g}"' in element
    ]
    assert len(numbered) == rules().max_position + 1
    # One rule closing each step, and a tick under each step that pays.
    assert len([e for e in kept if e.startswith("<line") and 'stroke-opacity="0.22"' in e]) == 7
    assert len([e for e in kept if 'fill-opacity="0.65"' in e]) == len(THRESHOLD_POSITIONS)
    for prose in layout()["reward_text"].values():
        assert any(prose in element for element in kept)
    # Four discs on step zero. Who sits in which corner was remapped for the game-table
    # player-count control (red/yellow stay in the left column), so the coloured circles are no
    # longer byte-identical to the baseline — only the four corner centres still are.
    on_step_zero = {disc_center(layout(), player, 0) for player in players_of(layout())}
    assert len(on_step_zero) == 4
    baseline_disc_centres = {
        (float(match.group(1)), float(match.group(2)))
        for match in re.finditer(
            r'<circle[^>]*\bcx="([\d.]+)" cy="([\d.]+)"[^>]*\br="9"', "".join(baseline)
        )
    }
    assert on_step_zero <= baseline_disc_centres


def test_the_extra_width_all_went_to_the_record_side_of_the_divider() -> None:
    """A wider board, not a rescaled one: the race keeps its place and the record spreads out."""
    board, record = layout()["board"], layout()["record"]
    divider = layout()["zone_divider"]["x"]

    assert board["panel_width"] > BEFORE_WIDENING["panel_width"]
    assert board["panel_height"] == 247.0
    # Nothing left of the divider moved: same track, same rewards, same title, same divider.
    assert step_centers(layout()) == [36.0, 80.0, 124.0, 168.0, 212.0, 256.0, 300.0]
    assert divider == BEFORE_WIDENING["divider_x"]
    assert layout()["threshold_rows"]["badge_center_x"] == 26.0
    assert board["title_anchor"] == {"x": 16.0, "y": 29.0}

    # The width the board gained went into the record, which starts where it always did and now
    # runs further, and into the margin past it.
    assert record["x"] == BEFORE_WIDENING["record_x"] > divider
    assert record["width"] > BEFORE_WIDENING["record_width"]
    assert record["rule"]["x2"] - record["rule"]["x1"] > BEFORE_WIDENING["rule_span"]
    assert board["panel_width"] - record["rule"]["x2"] > BEFORE_WIDENING["right_margin"]
    # And the record still clears the panel's own hairline frame.
    assert record["rule"]["x2"] < board["panel_width"] - board["inset"]


def test_the_board_carries_its_width_as_native_geometry() -> None:
    """The width is native geometry, not a transform: the viewBox is what grew.

    536 is a seat's 692.8 units at the ratio that held when this board was widened. The ratio has
    moved since -- the game table stopped stretching a seat to the duty wheel's height and started
    sizing it from the wheel's cube, which made a seat narrower -- so 536 now renders about a
    seventh proud of the boards it stands above. Re-fitting it is a pass over this board's own
    layout; the game table is where the overhang is measured for real.
    """
    board = layout()["board"]
    seat = player_board_geometry(len(load_player_boards_v2_layout()["worker_roles"]))

    assert board["panel_width"] == 536.0
    assert board["panel_width"] > seat["panel_width"] * PLAYER_UNIT
    # The viewBox carries the width, and carries the padding the board has always had around it.
    assert board["view_box"]["width"] == board["panel_width"] + 2 * board["outer_padding"]
    assert board["view_box"]["min_x"] == -board["outer_padding"]
    content = svg()
    assert f'viewBox="-18 -18 {board["view_box"]["width"]:.1f}' in content
    assert f'width="{board["view_box"]["width"]:.1f}"' in content
    assert "transform=" not in content
    assert "scale(" not in content


def test_the_season_end_cubes_are_the_cubes_a_seat_plays_with() -> None:
    """Same piece, same size, same air between them -- a cube won here came off a player board.

    And a seat's cube is the duty wheel's, so the three boards draw one piece at one size. Both
    numbers are read from the seats rather than written here: when this board wrote its own, they
    were the seats' cube of the day, and they stayed behind when the seats' cube moved.
    """
    assert CUBE_SIZE == pytest.approx(2 * TOKEN_RADIUS * PLAYER_UNIT, abs=0.005)
    assert CUBE_GAP == pytest.approx(TOKEN_GAP * PLAYER_UNIT, abs=0.005)
    assert CUBE_PITCH == CUBE_SIZE + CUBE_GAP
    assert PLAYER_CUBE_GAP == TOKEN_GAP
    # The seats take their cube from the wheel, so this board is drawing the wheel's cube too.
    assert 2 * TOKEN_RADIUS == DUTY_CUBE_SIZE
    # Smaller and airier than what this board drew when it held the seats' older cube itself.
    assert CUBE_SIZE < MARKER_CUBE * PLAYER_UNIT
    assert CUBE_GAP > 6.0 * PLAYER_UNIT

    slots = placeholder_slots(layout(), rules())
    spacing = [b["center_x"] - a["center_x"] for a, b in zip(slots, slots[1:], strict=False)]
    assert spacing == [pytest.approx(CUBE_PITCH)] * (len(slots) - 1)
    # Smaller than the cube the board used to draw, which is the point: it was 20% oversized.
    assert CUBE_SIZE < BEFORE_WIDENING["cube_size"]


def test_a_cube_covers_the_socket_it_fills_exactly() -> None:
    """One helper draws the box for both, so there is no way for the two to drift apart."""
    slot = season_end_slot_by_index(layout(), rules(), 1)
    box = cube_rect(slot["center_x"], slot["center_y"])
    content = render_alms_table_svg(layout(), config(), interactive=True)

    socket = re.search(rf'<rect {re.escape(box)}[^>]*data-placeholder-slot="1"[^>]*/>', content)
    assert socket is not None
    assert "stroke-dasharray" in socket.group(0)
    for player in players_of(layout()):
        cube = re.search(
            rf'<rect {re.escape(box)}[^>]*data-season-end-winner-slot="1"'
            rf'[^>]*data-player="{player["id"]}"[^>]*/>',
            content,
        )
        assert cube is not None
        assert "stroke-dasharray" not in cube.group(0)
    # Every cube on the board is drawn in a box this helper made, sockets and printed key alike.
    side = re.escape(f"{CUBE_SIZE:.1f}")
    boxes = re.findall(rf'<rect (x="[\d.]+" y="[\d.]+" width="{side}" height="{side}")', content)
    assert len(boxes) == 4 + 10 + 4 * len(PLAYER_IDS)


def test_the_season_end_heading_and_the_reward_numbers_read_as_a_seat_labels_do() -> None:
    """`Season end winners` and the `2`/`4`/`6` are the size of `Fields` on a player board."""
    assert SEASON_END_LABEL_FONT_SIZE == pytest.approx(ROLE_FONT_SIZE * PLAYER_UNIT, abs=0.005)
    assert THRESHOLD_LABEL_FONT_SIZE == SEASON_END_LABEL_FONT_SIZE
    # It is written in fewer of this board's units than before the widening, and still renders
    # larger: a seat is drawn at a bigger scale here than it was when that figure was measured.
    assert SEASON_END_LABEL_FONT_SIZE < BEFORE_WIDENING["heading_font_size"]
    # The track's own numbers keep their own size; only the reward badges follow the heading.
    assert STEP_NUMBER_FONT_SIZE != THRESHOLD_LABEL_FONT_SIZE

    content = svg()
    heading = layout()["record"]["heading"]
    size = f'font-size="{SEASON_END_LABEL_FONT_SIZE:g}"'
    assert f'x="{heading["x"]:.1f}" y="{heading["y"]:.1f}"' in content
    assert content.count(size) == 1 + len(THRESHOLD_POSITIONS)
    for position in THRESHOLD_POSITIONS:
        assert re.search(rf"{size}[^>]*>{position}</text>", content)


def test_one_spacing_runs_through_every_row_of_cubes_on_the_board() -> None:
    """The dashed sockets and the printed key below them are one grid, not two.

    Both are drawn on `CUBE_PITCH`, so the air between two cubes reads the same wherever a row of
    them appears, and both follow the seats when the seats' cube moves.
    """
    content = svg()
    boxes = re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)"', content)
    rows: dict[str, list[float]] = {}
    for x, y, side in boxes:
        if side == f"{CUBE_SIZE:.1f}":
            rows.setdefault(y, []).append(float(x))

    # Four sockets, then the key's ladder of one, two, three and four.
    assert sorted(len(xs) for xs in rows.values()) == [1, 2, 3, 4, 4]
    for xs in rows.values():
        xs.sort()
        steps = [round(right - left, 2) for left, right in zip(xs, xs[1:], strict=False)]
        # Corners are printed to a tenth, so a step measured off two of them can be a tenth out.
        assert steps == [pytest.approx(CUBE_PITCH, abs=0.1)] * len(steps)


def test_where_the_socket_row_starts_is_worked_out_rather_than_written_down() -> None:
    """The layout no longer names an x for it, because that x is not the layout's to know.

    It falls out of the record zone, the number of sockets and the cube, and the cube belongs to
    the seats. A number here would be one that quietly goes stale the next time they resize.
    """
    record = layout()["record"]
    slots = placeholder_slots(layout(), rules())
    span = slots[-1]["center_x"] - slots[0]["center_x"]

    assert "first_center_x" not in record["placeholder_slots"]
    assert span == pytest.approx((len(slots) - 1) * CUBE_PITCH)
    assert slots[0]["center_x"] == pytest.approx(
        record["x"] + record["width"] / 2 - span / 2, abs=0.01
    )


def test_the_heading_and_its_cubes_are_centred_in_the_record_zone() -> None:
    record = layout()["record"]
    middle = record["x"] + record["width"] / 2
    slots = placeholder_slots(layout(), rules())

    # To the hundredth of a unit the layout is written to, which is a thousandth of a pixel.
    assert record["heading"]["x"] == pytest.approx(middle, abs=0.01)
    assert (slots[0]["center_x"] + slots[-1]["center_x"]) / 2 == pytest.approx(middle, abs=0.01)
    # The scoring key sits under them, cubes on the left and the star it pays on the right.
    key = record["scoring_key"]
    assert key["first_cube_center_x"] > record["x"]
    widest_row = key["first_cube_center_x"] + 3 * CUBE_PITCH + CUBE_SIZE / 2
    assert widest_row < key["star_center_x"] - STAR_OUTER_RADIUS
    assert key["star_center_x"] + STAR_OUTER_RADIUS < record["x"] + record["width"]


def test_a_star_holds_its_vp_at_the_size_the_track_numbers_its_steps() -> None:
    """The VP is the track's own number size, and the star is drawn big enough to hold it."""
    key = layout()["record"]["scoring_key"]

    assert STAR_LABEL_FONT_SIZE == STEP_NUMBER_FONT_SIZE
    assert STAR_LABEL_OFFSET == pytest.approx(STAR_LABEL_FONT_SIZE / 3)
    assert STAR_LABEL_FONT_SIZE > BEFORE_WIDENING["star_label_font_size"]
    assert STAR_OUTER_RADIUS > BEFORE_WIDENING["star_outer_radius"]

    # What caps the star: five-pointed, so it stands `outer` above its centre and sin(54) of that
    # below, and four of them come down the record one row_height apart without touching.
    height = STAR_OUTER_RADIUS * (1 + math.sin(math.radians(54)))
    assert height < key["row_height"]
    # And the widest VP has to sit inside the star's waist rather than across its points. Every
    # digit of the family the board sets its ink in is 0.556 of the size wide.
    waist = 2 * STAR_INNER_RADIUS
    assert len(str(max(SEASON_END_VP))) * 0.556 * STAR_LABEL_FONT_SIZE < waist

    # And it is set plain, where the board's other numbers are bold: the star around it is doing
    # the work of standing the score out, so the digits do not have to as well.
    content = svg()
    fill = layout()["palette"]["star_label_fill"]
    for row, vp in zip(scoring_key_rows(layout(), rules()), SEASON_END_VP, strict=True):
        baseline = row["center_y"] + STAR_LABEL_OFFSET
        assert (
            f'<text x="{key["star_center_x"]:.1f}" y="{baseline:.1f}"'
            f' text-anchor="middle" font-family="{INK_FONT}"'
            f' font-size="{STAR_LABEL_FONT_SIZE:g}" fill="{fill}">{vp}</text>' in content
        )


def test_the_first_place_pocket_is_centred_in_the_lane_it_stands_in() -> None:
    """Equal air either side: the lane is the track's last rule to the zone divider."""
    track, pocket = layout()["track"], layout()["track"]["bonus_pocket"]
    last_rule_x = step_centers(layout())[-1] + track["step_pitch"] / 2
    divider = layout()["zone_divider"]["x"]
    center_x = bonus_pocket_center_x(layout())

    assert center_x - last_rule_x == pytest.approx(divider - center_x)
    assert last_rule_x < center_x - pocket["width"] / 2
    assert center_x + pocket["width"] / 2 < divider
    # It used to sit off to the left of that lane, on the track's pitch rather than in the space.
    assert center_x > BEFORE_WIDENING["pocket_center_x"]

    # The label and the pocket under it share the one centre, so neither can drift off the other.
    content = svg()
    assert f'<text x="{center_x:.1f}" y="{track["number_label_y"]:.1f}"' in content
    assert f'<rect x="{center_x - pocket["width"] / 2:.1f}"' in content
    assert f'<circle cx="{center_x:.1f}" cy="{pocket["center_y"]:.1f}"' in content


def test_the_header_ornament_is_the_duty_wheels_ornament() -> None:
    """Same mark at the same size: written in cubes, which is what the two boards share."""
    in_cubes = lambda value, cube: value / cube  # noqa: E731

    assert in_cubes(ORNAMENT_TREFOIL_RADIUS, CUBE_SIZE) == pytest.approx(
        in_cubes(DUTY_ORNAMENT_TREFOIL_RADIUS, DUTY_CUBE_SIZE), rel=1e-3
    )
    assert in_cubes(ORNAMENT_RULE_GAP, CUBE_SIZE) == pytest.approx(
        in_cubes(DUTY_ORNAMENT_RULE_GAP, DUTY_CUBE_SIZE), rel=1e-3
    )
    assert in_cubes(ORNAMENT_STROKE_WIDTH, CUBE_SIZE) == pytest.approx(1.3 / DUTY_CUBE_SIZE, 1e-3)

    # The arms are the one departure. The wheel runs each out to the end of that space's cube
    # tally, which is a fraction of what this board's header has to span.
    duty_arm = 4 * DUTY_CUBE_COLUMN_WIDTH / 2 - DUTY_ORNAMENT_RULE_GAP
    assert ornament_rule_arm(layout()) > duty_arm * CUBE_SIZE / DUTY_CUBE_SIZE

    content = svg()
    assert content.count(f'r="{ORNAMENT_TREFOIL_RADIUS:.1f}" />') == 3
    assert f'stroke-opacity="0.34" stroke-width="{ORNAMENT_STROKE_WIDTH:.1f}"' in content


def test_the_ornament_rule_spans_the_header_symmetrically_and_touches_neither_end() -> None:
    """It reaches almost to the zone divider, mirrors that to the left, and clears the title.

    The right arm is the one with a reach of its own; the left is given the same length, so the
    mark is symmetrical about the lobes. What that has to be checked against is the title, which
    the left arm is the only thing on the board that could ever run into.
    """
    center_x = layout()["ornament"]["trefoil"]["center_x"]
    divider = layout()["zone_divider"]["x"]
    drawn = re.search(
        r'<path d="M ([\d.]+),[\d.]+ H ([\d.]+) M ([\d.]+),[\d.]+ H ([\d.]+)" />', svg()
    )
    assert drawn is not None
    left_end, left_start, right_start, right_end = (float(value) for value in drawn.groups())

    # Symmetrical: the same air off the lobes and the same length of arm on either side.
    assert center_x - left_start == pytest.approx(right_start - center_x)
    assert center_x - left_end == pytest.approx(right_end - center_x)
    assert left_start - left_end == pytest.approx(right_end - right_start)
    assert left_start < center_x < right_start
    assert center_x - left_start == pytest.approx(ORNAMENT_RULE_GAP, abs=0.05)
    assert left_start - left_end == pytest.approx(ornament_rule_arm(layout()), abs=0.05)

    # Almost to the divider on the right, and clear of the title on the left.
    assert right_end < divider
    assert divider - right_end == pytest.approx(ORNAMENT_RULE_CLEARANCE, abs=0.05)
    assert left_end > TITLE_RIGHT_EDGE
    assert left_end - TITLE_RIGHT_EDGE > ORNAMENT_RULE_CLEARANCE
    # Long enough to read as a rule: most of the way from the title to the divider.
    assert (right_end - left_end) / (divider - TITLE_RIGHT_EDGE) > 0.9


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
