import re
from html import escape
from pathlib import Path

import pytest

from tools.ui_debug.generate_player_boards_v2 import (
    default_output_path,
    generate_player_boards_v2_page,
)
from tools.ui_debug.render_duty_wheel import CUBE_SIZE as DUTY_CUBE_SIZE
from tools.ui_debug.render_duty_wheel import LABEL_FONT_SIZE as DUTY_LABEL_FONT_SIZE
from tools.ui_debug.render_player_boards_v2 import (
    ASCENT_RATIO,
    BANNER_CENTER_Y,
    BANNER_FONT_SIZE,
    BANNER_HEIGHT,
    BUILDING_ROW_GAP,
    BUILDING_SLOT_DASH_ARRAY,
    BUILDING_SLOT_GAP,
    BUILDING_SLOT_HEX_SIZE,
    COMPACT_ICON_SIZE,
    ICON_FOOT_RATIO,
    LABEL_ASCENT,
    LINE_HEIGHT_RATIO,
    MARKER_CARD_MIN_WIDTH,
    MARKER_CUBE,
    MARKER_LABEL_FONT_SIZE,
    RESOURCE_COUNT_FONT_SIZE,
    RESOURCE_COUNT_OFFSET,
    RESOURCE_ICON_FOOT,
    RESOURCE_RADIUS,
    ROLE_CIRCLE_RADIUS,
    ROLE_FONT_SIZE,
    ROLE_LINE_HEIGHT,
    SIDE_MARGIN,
    TOKEN_GAP,
    TOKEN_RADIUS,
    WHEAT_ICON_SIZE,
    board_geometry,
    building_slot_centers,
    column_pitch,
    default_layout_path,
    hex_path_data,
    load_player_boards_v2_layout,
    player_by_id,
    players_of,
    render_player_board_v2_svg,
    render_player_boards_v2_html,
    resource_icon_center_y,
    resource_icon_size,
    slot_apothem,
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
    assert wrap_label("Stone Mason Yard") == ["Stone", "Mason Yard"]


def test_one_board_draws_its_slots_labels_and_colour_tag(layout: dict) -> None:
    player = player_by_id(layout, "player_three")
    svg = render_player_board_v2_svg(layout, player)
    geometry = board_geometry(len(layout["worker_roles"]))

    assert svg.startswith("<svg") and svg.endswith("</svg>")
    # Six building slots, six worker circles, and three resource circles.
    assert svg.count('stroke-dasharray="5,3"') == layout["building_slot_count"]
    assert svg.count(f'r="{ROLE_CIRCLE_RADIUS:g}"') == len(layout["worker_roles"])
    assert svg.count(f'r="{RESOURCE_RADIUS:g}"') == len(layout["resources"])
    for role in WORKER_ROLES:
        for line in wrap_label(role):
            assert f">{line}</text>" in svg
    assert svg.count(f'fill="{player["fill"]}"') > 0
    assert f'clip-path="url(#panelClip_{player["fill"].lstrip("#")})"' in svg
    assert len(geometry["role_x"]) == len(geometry["building_y"]) == 6


def test_an_interactive_board_slot_keeps_its_dashed_outline_on_top(layout: dict) -> None:
    """A page fills a slot by pointing its `use` at content, and the outline is drawn over it."""
    player = player_by_id(layout, "player_one")
    svg = render_player_board_v2_svg(layout, player, interactive=True)
    palette = layout["palette"]

    slots = re.findall(r'<g data-player-board-slot="\d+".*?</g>', svg, re.S)

    assert len(slots) == layout["building_slot_count"]
    assert svg.count('stroke-dasharray="5,3"') == layout["building_slot_count"]
    for number, (slot, (cx, cy)) in enumerate(
        zip(slots, building_slot_centers(layout), strict=True), start=1
    ):
        path = hex_path_data(cx, cy)
        assert f'data-player-board-slot="{number}"' in slot
        # Content is anchored on the slot centre, so a fragment drawn in the lower half of a hex
        # lands in the lower half of the slot.
        assert f'<use data-building-content="true" x="{cx:.2f}" y="{cy:.2f}"' in slot
        # Fill first, then the building content, then the border, which never carries a fill.
        assert slot.index(f'fill="{palette["slot_fill"]}" stroke="none"') < slot.index("<use")
        assert slot.index("<use") < slot.index('data-slot-outline="true"')
        assert slot.endswith(
            f'<path data-slot-outline="true" d="{path}" fill="none"'
            f' stroke="{palette["slot_stroke"]}" stroke-width="2"'
            f' stroke-dasharray="{BUILDING_SLOT_DASH_ARRAY}" stroke-linejoin="round"/></g>'
        )


def test_a_plain_board_slot_stays_the_single_dashed_hex_of_the_baseline(layout: dict) -> None:
    player = player_by_id(layout, "player_one")
    svg = render_player_board_v2_svg(layout, player)

    assert "data-player-board-slot" not in svg
    assert "<use" not in svg
    for cx, cy in building_slot_centers(layout):
        assert (
            f'<path d="{hex_path_data(cx, cy)}" fill="{layout["palette"]["slot_fill"]}"'
            f' stroke="{layout["palette"]["slot_stroke"]}" stroke-width="2"'
            f' stroke-dasharray="{BUILDING_SLOT_DASH_ARRAY}" stroke-linejoin="round"/>'
        ) in svg


def test_the_board_got_wider_without_getting_taller(layout: dict) -> None:
    """The whole point of the widening: more room across, and not a pixel more down.

    The height matters more than it looks. Wherever a board is shown beside other components it is
    given a height and takes its width from that, so leaving the height alone is what guarantees
    that everything already on the board still renders at exactly the size it used to.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    baseline = _svg_bodies(BASELINE_PROTOTYPE.read_text(encoding="utf-8"))[0]
    was_width, was_height = _view_box(baseline)

    assert geometry["panel_width"] > was_width * 1.25
    assert abs(geometry["panel_height"] - was_height) < 1.0


def test_the_slots_are_the_widest_thing_on_the_board_and_set_its_columns(layout: dict) -> None:
    """One hex size and one pitch: there are no other horizontal spacings to get wrong."""
    geometry = board_geometry(len(layout["worker_roles"]))
    slots = building_slot_centers(layout)
    xs = [x for x, _ in slots]

    assert len(slots) == int(layout["building_slot_count"]) == 6
    assert len(set(slots)) == len(slots)
    # Left to right, level with each other, and evenly spaced.
    assert xs == sorted(xs)
    assert len({y for _, y in slots}) == 1
    assert [b - a for a, b in zip(xs, xs[1:], strict=False)] == [pytest.approx(column_pitch())] * 5
    # Wider than a role circle, which is what made the board grow in the first place.
    assert BUILDING_SLOT_HEX_SIZE > ROLE_CIRCLE_RADIUS
    assert geometry["role_x"] == [x for x, _ in slots]


def test_a_slot_clears_its_neighbours_the_circle_above_it_and_the_board_edge(layout: dict) -> None:
    geometry = board_geometry(len(layout["worker_roles"]))
    slots = building_slot_centers(layout)
    cy = slots[0][1]

    assert column_pitch() - 2 * BUILDING_SLOT_HEX_SIZE == pytest.approx(BUILDING_SLOT_GAP)
    # Below the role circles, and by the stated gap.
    circle_bottom = geometry["role_circle_cy"] + ROLE_CIRCLE_RADIUS
    assert cy - slot_apothem() - circle_bottom == pytest.approx(BUILDING_ROW_GAP)
    # The same margin either side, and the bottom margin the banners get at the top.
    assert slots[0][0] - BUILDING_SLOT_HEX_SIZE == pytest.approx(SIDE_MARGIN)
    assert geometry["panel_width"] - (slots[-1][0] + BUILDING_SLOT_HEX_SIZE) == pytest.approx(
        SIDE_MARGIN
    )
    assert geometry["panel_height"] - (cy + slot_apothem()) == pytest.approx(
        BANNER_CENTER_Y - BANNER_HEIGHT / 2
    )


def test_the_role_circles_and_cubes_did_not_grow_with_the_slots(layout: dict) -> None:
    """Widening is not scaling: the slots are the only thing on the board that changed size."""
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))

    assert ROLE_CIRCLE_RADIUS == 34.0
    assert MARKER_CUBE == 14.0
    assert svg.count(f'r="{ROLE_CIRCLE_RADIUS:g}"') == len(layout["worker_roles"])
    assert svg.count(f'width="{MARKER_CUBE:.1f}" height="{MARKER_CUBE:.1f}"') > 0


def test_every_slot_is_drawn_from_the_one_hex_size(layout: dict) -> None:
    """Six slots, one shape: the same hexagon moved along the row, not six hexagons.

    Only as equal as two decimals of a path let them be, which is the precision they are written
    at, so a corner is allowed to be half a hundredth of a unit out and no more.
    """
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))
    dashed = re.findall(r'<path d="([^"]+)" [^>]*stroke-dasharray="5,3"', svg)
    reference = _corners(hex_path_data(0.0, 0.0))

    assert len(dashed) == int(layout["building_slot_count"])
    assert len(reference) == 12
    for path, center in zip(dashed, building_slot_centers(layout), strict=True):
        drawn = [value - center[index % 2] for index, value in enumerate(_corners(path))]
        assert drawn == pytest.approx(reference, abs=0.005)


def test_village_and_abbey_read_at_the_size_the_duty_wheel_sets_its_duty_names(
    layout: dict,
) -> None:
    """The same argument the building slots settled, applied to type.

    Two boards drawn at different scales agree on screen when they agree in cubes, so a duty name
    at 15.5 against the wheel's 13.0-unit cube and a banner at 16.7 against this board's 14.0-unit
    cube are the same size. Neither board is scaled to suit the other; the table decides that, and
    what it decides moves with the window.
    """
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))

    assert BANNER_FONT_SIZE / MARKER_CUBE == pytest.approx(
        DUTY_LABEL_FONT_SIZE / DUTY_CUBE_SIZE, rel=0.002
    )
    for banner in layout["banners"]:
        assert f'font-size="{BANNER_FONT_SIZE:g}" font-weight="bold"' in svg
        assert f">{banner['label']}</text>" in svg
    # Set inside its band, descenders and all: 'Village' has a g on it.
    baseline = BANNER_CENTER_Y + BANNER_FONT_SIZE * 0.35
    assert baseline - 0.91 * BANNER_FONT_SIZE > BANNER_CENTER_Y - BANNER_HEIGHT / 2
    assert baseline + 0.21 * BANNER_FONT_SIZE < BANNER_CENTER_Y + BANNER_HEIGHT / 2


def test_the_role_labels_grew_and_the_spacing_that_depends_on_them_followed(layout: dict) -> None:
    """Fields, Stone Mason and the rest, a little larger, with the type's own metrics in tow.

    A line height and an ascent are properties of the type rather than free choices, so they are
    written as ratios of its size. Set them once and a change of size cannot leave two-line labels
    overlapping or a row of them dropped onto the circles below.
    """
    was = 10
    geometry = board_geometry(len(layout["worker_roles"]))
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))

    # Larger than they were, and still secondary to the banners naming the two halves of the board.
    assert was < ROLE_FONT_SIZE < BANNER_FONT_SIZE
    assert ROLE_LINE_HEIGHT == pytest.approx(LINE_HEIGHT_RATIO * ROLE_FONT_SIZE)
    assert LABEL_ASCENT == pytest.approx(ASCENT_RATIO * ROLE_FONT_SIZE)
    assert svg.count(f'font-size="{ROLE_FONT_SIZE:g}"') >= len(layout["worker_roles"])
    # The tallest label is two lines, and it clears the readouts above it.
    label_top = geometry["role_label_baseline"] - ROLE_LINE_HEIGHT - LABEL_ASCENT
    assert wrap_label("Road Engineer") == ["Road", "Engineer"]
    assert label_top > geometry["resource_cy"] + RESOURCE_RADIUS


# How tall each icon is drawn, per unit of the size it is asked for, and how far it reaches above
# its own centre. Measured off the rendered artwork with getBBox rather than derived, so they hold
# only while the drawings do -- they are here to size the readouts, not to police the pictures.
ICON_HEIGHT_PER_UNIT = {"wheat": 1.7243, "cube": 1.2400, "coin": 1.2400}
ICON_RISE_PER_UNIT = {"wheat": 1.1244, "cube": 0.6000, "coin": 0.6000}
# The same measurement of the duty wheel's three, in its cubes, which is how they compare.
DUTY_ICON_HEIGHT_IN_CUBES = {"wheat": 2.1255, "cube": 1.7692, "coin": 1.8018}


def test_the_resource_icons_are_the_size_the_duty_wheel_draws_the_same_things(layout: dict) -> None:
    """Wheat, stone and silver, drawn here as big as the wheel draws its tithes.

    In cubes again. The wheat is held close to the wheel's because it is the big shape of the three
    and being over was easy to see; the stone and the coin sit a little under, which is where they
    read right on this board and is not something the eye picks up.
    """
    icons = [resource["icon"] for resource in layout["resources"]]
    height = {
        icon: ICON_HEIGHT_PER_UNIT[icon] * resource_icon_size(icon) / MARKER_CUBE
        for icon in DUTY_ICON_HEIGHT_IN_CUBES
    }

    assert icons == ["wheat", "cube", "coin"]
    assert height["wheat"] == pytest.approx(DUTY_ICON_HEIGHT_IN_CUBES["wheat"], rel=0.02)
    for icon in ("cube", "coin"):
        assert 0.9 < height[icon] / DUTY_ICON_HEIGHT_IN_CUBES[icon] < 1.0
    # The wheat is sized on its own because it has to be: put it on the size the other two share
    # and it goes back over the wheel's, which is the state this came from.
    assert WHEAT_ICON_SIZE < COMPACT_ICON_SIZE
    shared = ICON_HEIGHT_PER_UNIT["wheat"] * COMPACT_ICON_SIZE / MARKER_CUBE
    assert shared > DUTY_ICON_HEIGHT_IN_CUBES["wheat"] * 1.05


def test_a_resource_readout_holds_its_icon_over_its_amount_inside_the_circle(layout: dict) -> None:
    """An icon in the top of the circle and the amount under it, with both clear of the rim."""
    was = 27
    tops = {
        icon: resource_icon_center_y(icon) - ICON_RISE_PER_UNIT[icon] * resource_icon_size(icon)
        for icon in ICON_FOOT_RATIO
    }
    feet = {
        icon: resource_icon_center_y(icon) + ICON_FOOT_RATIO[icon] * resource_icon_size(icon)
        for icon in ICON_FOOT_RATIO
    }
    amount_top = RESOURCE_COUNT_OFFSET - 0.91 * RESOURCE_COUNT_FONT_SIZE

    assert RESOURCE_RADIUS > was
    # All three stand on one line however they are sized, so the amount is the same distance below
    # each of them rather than nearer the smaller ones.
    assert {round(foot, 6) for foot in feet.values()} == {round(RESOURCE_ICON_FOOT, 6)}
    # The amount is under the icons with a gap, and below the circle's middle.
    assert max(feet.values()) < amount_top
    assert 0 < amount_top < RESOURCE_COUNT_OFFSET < RESOURCE_RADIUS
    # Each icon is in the top of the circle: its middle above the centre, and only the foot of it
    # -- a tenth of the radius at most -- reaching past.
    assert max(feet.values()) < RESOURCE_RADIUS * 0.1
    for icon, top in tops.items():
        assert top > -RESOURCE_RADIUS, icon
        assert (top + feet[icon]) / 2 < 0, icon


def test_the_marker_card_names_itself_on_one_line(layout: dict) -> None:
    """ "First player", set at its own size and unbroken.

    The card is the one thing on a board that says what it is, so it carries the largest point of
    sans on the board rather than borrowing the role labels'. It stays on one line because the
    label fits the card at that size, and breaking a two-word phrase to no purpose reads worse.
    """
    label = layout["first_player_marker"]["label"]
    svg = render_player_board_v2_svg(
        layout, player_by_id(layout, "player_one"), include_first_player_marker=True
    )
    # The average advance of this face, measured off the rendered label: 0.45 of its size a glyph.
    drawn_width = len(label) * MARKER_LABEL_FONT_SIZE * 0.45

    assert label == "First player"
    assert MARKER_LABEL_FONT_SIZE > ROLE_FONT_SIZE
    assert f'font-size="{MARKER_LABEL_FONT_SIZE:g}" font-weight="700"' in svg
    assert f">{escape(label)}</text>" in svg
    # One line, and it fits inside the card it names.
    assert wrap_label(label) != [label]
    assert svg.count(f">{escape(label)}</text>") == 1
    assert drawn_width < MARKER_CARD_MIN_WIDTH


def test_the_bigger_readouts_still_clear_the_workers_above_them(layout: dict) -> None:
    """The readouts grew into a gap that was already there, rather than pushing the board about."""
    geometry = board_geometry(len(layout["worker_roles"]))
    tokens_bottom = geometry["token_grid_top"] + 2 * 2 * TOKEN_RADIUS + TOKEN_GAP

    assert geometry["resource_cy"] - RESOURCE_RADIUS > tokens_bottom


def _corners(path: str) -> list[float]:
    """A path's corners, flattened to x, y, x, y so they can be compared with a tolerance."""
    return [float(value) for value in re.findall(r"-?[\d.]+", path)]


def test_html_shows_four_boards_in_a_two_by_two_grid(page: str) -> None:
    assert page.startswith("<!DOCTYPE html>")
    assert TITLE in page
    assert SUBTITLE_START in page
    assert len(_svg_bodies(page)) == 4
    assert page.count('<div class="board-row">') == 2
    assert page.count('data-component="player-board-v2"') == 4
    assert "<iframe" not in page


def test_html_carries_the_board_labels_and_player_colours(page: str) -> None:
    for text in ("Village", "Abbey", "First player", *WORKER_ROLES[:1]):
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


def test_generated_boards_are_the_baseline_boards_on_a_wider_board(tmp_path: Path) -> None:
    """Everything these boards no longer share with the prototype, and nothing else.

    Two departures, both deliberate. The board got wider, because the prototype's building slots
    are two thirds of a map hex and these are a whole one. Then the type and the resource readouts
    grew, because they were sized for a board that narrow and read small on this one. What is left
    is what the prototype set and no reason has come up to change: the height, the cubes, the
    worker circles, and the number of every piece.
    """
    generated = _svg_bodies(
        generate_player_boards_v2_page(output_path=tmp_path / "player_boards_v2.html").read_text(
            encoding="utf-8"
        )
    )
    baseline = _svg_bodies(BASELINE_PROTOTYPE.read_text(encoding="utf-8"))
    grew = {
        'font-size="11"': f'font-size="{BANNER_FONT_SIZE:g}"',
        'font-size="10"': f'font-size="{ROLE_FONT_SIZE:g}"',
        'font-size="13"': f'font-size="{RESOURCE_COUNT_FONT_SIZE:g}"',
        'r="27"': f'r="{RESOURCE_RADIUS:g}"',
    }
    kept = ('width="14.0" height="14.0"', 'r="34"')

    assert len(generated) == len(baseline) == 4
    for board, was in zip(generated, baseline, strict=True):
        width, height = _view_box(board)
        old_width, old_height = _view_box(was)

        assert width > old_width
        assert height == old_height
        for size in kept:
            assert board.count(size) == was.count(size), size
        # Drawn bigger, with nothing left behind at the old size.
        for before, now in grew.items():
            assert before not in board, before
            assert now in board, now
            assert float(now.split('"')[1]) > float(before.split('"')[1])
    # As many of each as the prototype drew, counted on a board without the marker card: its label
    # is no longer set at the role size, and shares a size with the resource amounts.
    board, was = generated[1], baseline[1]
    assert "data-first-player-marker" not in board
    for before, now in grew.items():
        if before != 'font-size="13"':
            assert board.count(now) == was.count(before), now


def _view_box(svg: str) -> tuple[float, float]:
    _, _, width, height = re.search(r'viewBox="([^"]+)"', svg).group(1).split()
    return float(width), float(height)


def test_generated_page_matches_baseline_facts(page: str) -> None:
    baseline = BASELINE_PROTOTYPE.read_text(encoding="utf-8")

    for text in (TITLE, SUBTITLE_START, ">First player</text>"):
        assert text in baseline
        assert text in page
    for _, fill, _ in PLAYER_COLORS.values():
        assert fill in baseline
        assert fill in page
    assert len(_svg_bodies(baseline)) == len(_svg_bodies(page)) == 4
    # The card is the one label that reads differently: the prototype broke "First player marker"
    # over two lines, and it now says just what it is, on one.
    assert ">marker</text>" in baseline
    assert ">marker</text>" not in page
