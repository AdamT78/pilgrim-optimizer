import json
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_duty_wheel import (
    default_output_path,
    generate_duty_wheel_page,
)
from tools.ui_debug.render_duty_wheel import (
    default_layout_path,
    duties_of,
    duty_position_by_id,
    duty_setups,
    duty_wheel_readout,
    load_duty_wheel_layout,
    merchant_path,
    next_merchant_position,
    players_for_count,
    render_duty_wheel_html,
    render_duty_wheel_svg,
    ring_duties,
    tally_columns,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
LAYOUT_JSON = UI_DEBUG_DIR / "duty_wheel_layout.json"
PROTOTYPE_HTML = UI_DEBUG_DIR / "prototypes" / "duty_wheel.html"
PROTOTYPE_SVG = UI_DEBUG_DIR / "prototypes" / "duty_wheel.svg"
BUILD_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "duty_wheel_build.py.txt"
RENDER_SOURCE = UI_DEBUG_DIR / "prototype_sources" / "duty_wheel_render.py.txt"

RING_DUTY_LABELS = (
    "Produce",
    "Allocation",
    "Clerical",
    "Build Roads",
    "Taxation",
    "Ordination",
    "Construct",
    "Give Alms",
)
PLAYER_SEATS = ("player_one", "player_two", "player_three", "player_four")
PLAYER_COLOURS = ("white", "red", "yellow", "blue")
PLAYER_FILLS = {
    "player_one": "#FFFFFF",
    "player_two": "#C94C4C",
    "player_three": "#E3C64A",
    "player_four": "#3B6EA5",
}
MERCHANT_PURPLE = "#8E63D7"
ALLOWED_DRIFT = 0.1


def layout() -> dict:
    return load_duty_wheel_layout()


def generated_svg() -> str:
    return render_duty_wheel_svg(layout())


def interactive_html() -> str:
    return render_duty_wheel_html(layout(), interactive=True)


def baseline_svg() -> str:
    content = PROTOTYPE_SVG.read_text(encoding="utf-8")
    return content[content.index("<svg") :]


def drawing_elements(svg: str) -> list[tuple[str, tuple[float, ...]]]:
    """Every drawn element as its tag plus the numbers in its attributes, in document order."""
    flat = re.sub(r"\s+", " ", svg)
    return [
        (
            match.group(1),
            tuple(float(number) for number in re.findall(r"-?\d+\.?\d*", match.group(2))),
        )
        for match in re.finditer(r"<(path|rect|circle|line|ellipse|text)\b([^>]*)>", flat)
    ]


def test_duty_wheel_layout_exists_and_is_the_renderer_default() -> None:
    assert LAYOUT_JSON.is_file()
    assert default_layout_path() == LAYOUT_JSON
    assert json.loads(LAYOUT_JSON.read_text(encoding="utf-8")) == layout()


def test_layout_holds_nine_duty_positions_including_the_city() -> None:
    duties = duties_of(layout())

    assert len(duties) == 9
    assert {duty["id"] for duty in duties} == {
        "produce",
        "allocation",
        "clerical",
        "build_roads",
        "taxation",
        "ordination",
        "construct",
        "give_alms",
        "city",
    }
    for duty in duties:
        assert len(duty["center"]) == 2


def test_layout_labels_every_duty_and_the_city() -> None:
    data = layout()
    labels = [duty["label"] for duty in duties_of(data)]

    assert set(RING_DUTY_LABELS) <= set(labels)
    assert duty_position_by_id(data, data["city_id"])["label"] == "City"


def test_layout_orders_the_ring_clockwise_from_produce() -> None:
    data = layout()

    assert data["clockwise_order"][0] == "produce"
    assert [duty["label"] for duty in ring_duties(data)] == list(RING_DUTY_LABELS)
    assert data["city_id"] not in data["clockwise_order"]


def test_layout_describes_the_merchant_token() -> None:
    merchant = layout()["merchant_token"]

    assert merchant["label"] == "Merchant token"
    assert merchant["color"] == MERCHANT_PURPLE
    assert merchant["starts_on"] == "taxation"
    # Where the prototype drew him, which is what the parity check below asks for.
    assert merchant["baseline_position"] == "produce"


def test_layout_names_the_four_seats_with_their_cube_colours() -> None:
    players = layout()["players"]

    assert [player["id"] for player in players] == list(PLAYER_SEATS)
    assert [player["color"] for player in players] == list(PLAYER_COLOURS)
    assert [player["label"] for player in players] == [f"Player {seat}" for seat in (1, 2, 3, 4)]
    assert {player["id"]: player["fill"] for player in players} == PLAYER_FILLS


def test_layout_offers_the_two_three_and_four_player_views() -> None:
    data = layout()

    assert data["player_counts"] == [2, 3, 4]
    # Four is the view the prototype drew, so it is what the page opens on.
    assert data["default_player_count"] == 4


def test_players_for_count_seats_the_table_in_order() -> None:
    data = layout()
    seated = {count: players_for_count(data, count) for count in data["player_counts"]}

    assert [player["color"] for player in seated[2]] == ["white", "red"]
    assert [player["color"] for player in seated[3]] == ["white", "red", "yellow"]
    assert [player["color"] for player in seated[4]] == ["white", "red", "yellow", "blue"]
    assert [player["id"] for player in seated[4]] == list(PLAYER_SEATS)


def test_players_for_count_refuses_a_count_the_layout_does_not_offer() -> None:
    data = layout()

    for count in (1, 5):
        with pytest.raises(ValueError):
            players_for_count(data, count)


def test_every_player_count_centres_its_cube_columns_on_the_duty() -> None:
    data = layout()
    duty = duty_position_by_id(data, "produce")
    center_x = duty["center"][0]

    for count in data["player_counts"]:
        columns = tally_columns(data, duty, count)
        assert len(columns) == count
        assert [column["player"] for column in columns] == list(PLAYER_SEATS[:count])
        # The columns sit symmetrically about the duty, so a shorter table stays in the middle.
        assert round(sum(column["center_x"] for column in columns) / count, 6) == center_x
        assert round(columns[0]["center_x"] + columns[-1]["center_x"], 6) == round(2 * center_x, 6)


def test_dropping_seats_narrows_the_tally_from_both_sides() -> None:
    data = layout()
    duty = duty_position_by_id(data, "produce")
    spans = {
        count: (
            tally_columns(data, duty, count)[0]["center_x"],
            tally_columns(data, duty, count)[-1]["center_x"],
        )
        for count in data["player_counts"]
    }

    assert spans[2][0] > spans[3][0] > spans[4][0]
    assert spans[2][1] < spans[3][1] < spans[4][1]


def test_layout_gives_every_ring_duty_a_tithe_icon_except_taxation() -> None:
    data = layout()
    icons = {duty["id"]: duty["tithe_icon"] for duty in ring_duties(data)}

    assert icons["taxation"] is None
    assert set(icons.values()) - {None} <= set(data["tithe_icons"])
    assert icons["clerical"] == "cornucopia"


def test_rendered_svg_is_an_svg_document() -> None:
    svg = generated_svg()

    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert 'data-component="duty-wheel"' in svg


def test_rendered_svg_names_the_city_every_duty_and_both_arrow_families() -> None:
    svg = generated_svg()

    assert ">City</text>" in svg
    for label in RING_DUTY_LABELS:
        assert f">{label}</text>" in svg
    assert 'aria-label="Clockwise outer arrows"' in svg
    assert 'aria-label="Middle directional arrows"' in svg


def test_rendered_svg_draws_nine_spaces_eight_ring_arrows_and_four_middle_arrows() -> None:
    svg = generated_svg()

    assert svg.count('class="board-circle"') == 9
    assert len(re.findall(r'data-ring-arrow="', svg)) == 8
    assert len(re.findall(r'data-middle-arrow="', svg)) == 4
    # Each arrow is drawn twice: a black outline with the white interior on top.
    assert svg.count('class="arrow-border"') == 12
    assert svg.count('class="arrow-interior"') == 12


def test_rendered_svg_starts_the_merchant_on_taxation() -> None:
    svg = generated_svg()

    assert 'data-merchant-token="taxation"' in svg
    assert MERCHANT_PURPLE in svg
    assert svg.count('data-token="merchant"') == 1


def test_merchant_path_covers_all_eight_duty_tiles_and_leaves_out_the_city() -> None:
    data = layout()
    path = merchant_path(data)

    assert path == data["clockwise_order"]
    assert "taxation" in path
    assert data["city_id"] not in path
    assert len(path) == 8


def test_next_merchant_position_is_simply_the_next_tile_clockwise() -> None:
    data = layout()

    # He starts on Taxation, so the first move is to the tile clockwise of it.
    assert next_merchant_position(data, "taxation") == "ordination"
    assert next_merchant_position(data, "produce") == "allocation"
    # Taxation is a stop like any other, so the tile before it hands over to it.
    assert next_merchant_position(data, "build_roads") == "taxation"
    assert next_merchant_position(data, "give_alms") == "produce"


def test_walking_the_ring_visits_every_duty_tile_and_comes_back_to_taxation() -> None:
    data = layout()
    start = data["merchant_token"]["starts_on"]
    position = start
    visited = []
    for _ in range(len(merchant_path(data))):
        position = next_merchant_position(data, position)
        visited.append(position)

    assert visited[0] == "ordination"
    assert set(visited) == set(data["clockwise_order"])
    assert visited[-1] == start


def test_rendered_svg_marks_the_tithe_token_icons() -> None:
    svg = generated_svg()

    assert 'data-tithe-token="coin"' in svg
    assert 'data-tithe-token="cornucopia"' in svg
    assert 'data-tithe-token="wheat"' in svg
    assert 'data-tithe-token="stone"' in svg
    # Taxation is a duty tile like the rest, but the one drawn without a Tithe capsule.
    assert 'data-duty="taxation"' in svg
    assert "taxation-tithe-shape" not in svg


def test_rendered_svg_tallies_cubes_in_every_player_colour() -> None:
    svg = generated_svg()

    for seat, fill in PLAYER_FILLS.items():
        assert f'fill="{fill}"' in svg
        assert f'data-player="{seat}"' in svg
    # Drawn plain, each duty carries the one tally the prototype shows: the four-player view.
    assert len(re.findall(r'data-cube-tally="', svg)) == 8
    assert len(re.findall(r'data-player-count="4"', svg)) == 8
    assert 'data-player-count="2"' not in svg


def test_sample_setups_start_from_the_layout_and_then_turn_the_tiles() -> None:
    data = layout()
    setups = duty_setups(data)

    assert len(setups) > 1
    assert [entry["position"] for entry in setups[0]] == data["clockwise_order"]
    assert [entry["duty"] for entry in setups[0]] == data["clockwise_order"]
    assert [entry["label"] for entry in setups[0]] == list(RING_DUTY_LABELS)
    for setup in setups[1:]:
        assert [entry["duty"] for entry in setup] != data["clockwise_order"]


def test_every_sample_setup_keeps_taxation_where_it_is_and_leaves_the_city_out() -> None:
    data = layout()

    for setup in duty_setups(data):
        taxation = next(entry for entry in setup if entry["position"] == "taxation")
        assert taxation["duty"] == "taxation"
        assert taxation["label"] == "Taxation"
        assert {entry["duty"] for entry in setup} == set(data["clockwise_order"])
        assert data["city_id"] not in {entry["duty"] for entry in setup}
        assert data["city_id"] not in {entry["position"] for entry in setup}


def test_every_sample_setup_gives_a_tithe_token_to_every_duty_but_taxation() -> None:
    data = layout()

    for setup in duty_setups(data):
        for entry in setup:
            if entry["position"] == "taxation":
                assert entry["tithe_icon"] is None
            else:
                assert entry["tithe_icon"] in data["tithe_icons"]


def test_interactive_board_draws_a_merchant_slot_on_every_ring_position() -> None:
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    slots = re.findall(r'data-token="merchant" data-duty-position="(\w+)" opacity="(\d)"', svg)

    assert [position for position, _ in slots] == data["clockwise_order"]
    assert [position for position, opacity in slots if opacity == "1"] == ["taxation"]


def test_interactive_board_draws_every_tithe_token_a_position_can_show() -> None:
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    icons = re.findall(r'data-tithe-token="(\w+)" data-duty-position="(\w+)" opacity="(\d)"', svg)
    shown = {position: icon for icon, position, opacity in icons if opacity == "1"}

    assert len(icons) == 7 * len(data["tithe_icons"])
    # Taxation has no capsule, so it has no icon to switch to in any setup.
    assert "taxation" not in {position for _, position, _ in icons}
    assert shown == {
        duty["id"]: duty["tithe_icon"] for duty in ring_duties(data) if duty["tithe_icon"]
    }


def test_interactive_board_tags_each_ring_position_with_its_index() -> None:
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    tagged = re.findall(r'data-duty="(\w+)" data-duty-ring-index="(\d)"', svg)

    assert [duty for duty, _ in tagged] == data["clockwise_order"]
    assert [index for _, index in tagged] == [str(index) for index in range(8)]
    assert f'data-duty="{data["city_id"]}" data-duty-ring-index' not in svg


def test_interactive_board_draws_a_cube_tally_for_every_player_count() -> None:
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    tallies = re.findall(r'data-cube-tally="(\w+)" data-player-count="(\d)" opacity="(\d)"', svg)
    shown = [(duty, count) for duty, count, opacity in tallies if opacity == "1"]

    assert len(tallies) == 8 * len(data["player_counts"])
    # Every duty offers all three views, and opens on the four-player one.
    assert shown == [(duty, "4") for duty in data["clockwise_order"]]
    assert data["city_id"] not in {duty for duty, _, _ in tallies}


def test_interactive_board_only_draws_the_seats_a_player_count_seats() -> None:
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    produce = svg[svg.index('data-cube-tally="produce" data-player-count="2"') :]
    two_player = produce[: produce.index("</g>")]

    assert 'data-player="player_one"' in two_player
    assert 'data-player="player_two"' in two_player
    assert 'data-player="player_three"' not in two_player
    assert 'data-player="player_four"' not in two_player


def test_interactive_page_offers_all_three_debug_controls() -> None:
    html = interactive_html()

    assert "Randomize Duty tiles" in html
    assert "Move Merchant" in html
    assert 'id="randomize-duties"' in html
    assert 'id="move-merchant"' in html
    assert "Setup 1 of 3 — Merchant on Taxation — 4 players" in html
    assert duty_wheel_readout(layout()) == "Setup 1 of 3 — Merchant on Taxation — 4 players"


def test_interactive_page_offers_a_button_per_player_count_with_four_selected() -> None:
    html = interactive_html()
    pattern = r'<button type="button" data-player-count="(\d)" aria-pressed="(\w+)">(\dp)</button>'
    buttons = re.findall(pattern, html)

    assert [label for _, _, label in buttons] == ["2p", "3p", "4p"]
    assert [count for count, _, _ in buttons] == ["2", "3", "4"]
    assert [count for count, pressed, _ in buttons if pressed == "true"] == ["4"]


def test_interactive_page_hands_the_script_the_player_count_it_opens_on() -> None:
    data = layout()
    html = interactive_html()
    script = html[html.index("<script>") : html.index("</script>")]

    assert f"var playerCount = {data['default_player_count']};" in script
    assert "players" in duty_wheel_readout(data, player_count=2)
    assert duty_wheel_readout(data, player_count=2).endswith("2 players")


def test_interactive_page_hands_the_script_the_ring_it_walks() -> None:
    data = layout()
    html = interactive_html()
    script = html[html.index("<script>") : html.index("</script>")]

    assert json.dumps(merchant_path(data)) in script
    assert json.dumps(data["merchant_token"]["starts_on"]) in script
    assert json.dumps(duty_setups(data)) in script
    # The walk the script is handed runs over all eight duty tiles and never the City.
    assert json.dumps(merchant_path(data)) == json.dumps(data["clockwise_order"])
    assert data["city_id"] not in merchant_path(data)
    # The controls only ever move tokens and rewrite titles.
    assert "GameState" not in script
    assert "legal_actions" not in script


def test_plain_page_has_no_controls() -> None:
    html = render_duty_wheel_html(layout())

    assert "Randomize Duty tiles" not in html
    assert "<button" not in html
    assert "<script>" not in html
    assert "<svg" in html


def test_rendered_html_wraps_the_board_and_explains_what_it_is_not() -> None:
    html = render_duty_wheel_html(layout())

    assert html.startswith("<!DOCTYPE html>")
    assert "<svg" in html
    assert "Duty Wheel" in html
    assert "Merchant token" in html
    assert "Tithe tokens" in html
    assert "no GameState" in html
    assert "<iframe" not in html


def test_generator_writes_the_page_to_a_temp_path(tmp_path: Path) -> None:
    written = generate_duty_wheel_page(output_path=tmp_path / "duty_wheel.html")

    assert written == tmp_path / "duty_wheel.html"
    assert written.is_file()
    assert "Produce" in written.read_text(encoding="utf-8")
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "duty_wheel.html"


def test_generator_creates_a_missing_output_directory(tmp_path: Path) -> None:
    written = generate_duty_wheel_page(output_path=tmp_path / "generated" / "duty_wheel.html")

    assert written.is_file()


def test_generated_board_matches_the_baseline_element_for_element() -> None:
    """Coarse parity: the same shapes at the same coordinates, in the same order.

    Asked for the board the prototype drew — static, Merchant on Produce — the renderer reproduces
    it. The one tolerated gap is the Allocation title, which the baseline puts 0.1px above the
    offset its other eight titles share; the renderer uses the shared offset instead.
    """
    data = layout()
    generated = drawing_elements(
        render_duty_wheel_svg(data, merchant_on=data["merchant_token"]["baseline_position"])
    )
    baseline = drawing_elements(baseline_svg())

    assert len(generated) == len(baseline)
    for mine, theirs in zip(generated, baseline, strict=True):
        assert mine[0] == theirs[0]
        assert len(mine[1]) == len(theirs[1])
        for value, expected in zip(mine[1], theirs[1], strict=True):
            assert abs(round(value - expected, 6)) <= ALLOWED_DRIFT


def test_generated_and_baseline_share_their_identifying_text() -> None:
    generated = interactive_html()
    baseline = baseline_svg()

    for fragment in (
        "City",
        "Produce",
        "Taxation",
        "Clockwise outer arrows",
        "Middle directional arrows",
        MERCHANT_PURPLE,
    ):
        assert fragment in generated
        assert fragment in baseline


def test_baseline_prototype_files_are_still_there_and_untouched() -> None:
    html = PROTOTYPE_HTML.read_text(encoding="utf-8")
    svg = PROTOTYPE_SVG.read_text(encoding="utf-8")

    for content in (html, svg):
        assert "PILGRIM" in content
        assert "City" in content
        assert "Produce" in content
        assert "Taxation" in content
    # The baseline knows nothing about the renderer's tagging.
    assert "data-component" not in html
    assert "data-duty" not in svg


def test_prototype_sources_are_still_reference_only_copies() -> None:
    assert "Build the Pilgrim board" in BUILD_SOURCE.read_text(encoding="utf-8")
    assert "Render pilgrim_board.html" in RENDER_SOURCE.read_text(encoding="utf-8")
