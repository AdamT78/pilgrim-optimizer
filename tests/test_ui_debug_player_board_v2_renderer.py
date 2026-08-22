import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_player_boards_v2 import (
    default_output_path,
    generate_player_boards_v2_page,
)
from tools.ui_debug.render_duty_wheel import CUBE_CELL_HEIGHT as DUTY_CUBE_CELL_HEIGHT
from tools.ui_debug.render_duty_wheel import CUBE_COLUMN_WIDTH as DUTY_CUBE_COLUMN_WIDTH
from tools.ui_debug.render_duty_wheel import CUBE_SIZE as DUTY_CUBE_SIZE
from tools.ui_debug.render_duty_wheel import LABEL_FONT_SIZE as DUTY_LABEL_FONT_SIZE
from tools.ui_debug.render_player_boards_v2 import (
    ACTIVE_GLOW_OPACITY,
    ASCENT_RATIO,
    BANNER_CENTER_Y,
    BANNER_FONT_SIZE,
    BANNER_HEIGHT,
    BUILDING_ROW_GAP,
    BUILDING_SLOT_DASH_ARRAY,
    BUILDING_SLOT_GAP,
    BUILDING_SLOT_HEX_SIZE,
    COLUMN_HALF_WIDTH,
    COMPACT_ICON_SIZE,
    CORNER_TAG_OVERSHOOT,
    CORNER_TAG_SIZE,
    ICON_FOOT_RATIO,
    ICON_RISE_RATIO,
    LABEL_ASCENT,
    LINE_HEIGHT_RATIO,
    MARKER_CUBE,
    PANEL_CORNER_RADIUS,
    RESOURCE_BAND_COLUMNS,
    RESOURCE_CHOICE_HEIGHT,
    RESOURCE_CHOICE_TOP,
    RESOURCE_CHOICE_WIDTH,
    RESOURCE_COUNT_FONT_SIZE,
    RESOURCE_DIVIDER_OVERHANG,
    RESOURCE_READOUT_COUNT,
    ROLE_ACOLYTE_LIMIT,
    ROLE_CIRCLE_RADIUS,
    ROLE_FONT_SIZE,
    ROLE_LABEL_GAP,
    ROLE_LABEL_MAX_LINES,
    ROLE_LABEL_TOP_GAP,
    ROLE_LINE_HEIGHT,
    SIDE_MARGIN,
    TOKEN_BAND_HEIGHT,
    TOKEN_GAP,
    TOKEN_GRID_TOP_GAP,
    TOKEN_RADIUS,
    TOKEN_ROW_GAP,
    WHEAT_ICON_SIZE,
    banner_center_x,
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
    resource_choice_styles,
    resource_icon_center_y,
    resource_icon_height,
    resource_icon_size,
    slot_apothem,
    slot_band_half_height,
    token_slot_count,
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
    "player_one": ("red", "#B7382E", "#7A241C"),
    "player_two": ("yellow", "#D9B33B", "#8A6B1E"),
    "player_three": ("blue", "#3B6EA5", "#254A73"),
    "player_four": ("white", "#FFFFFF", "#8B7B4E"),
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


def _boards_grid(text: str) -> str:
    """The page's grid, stopping where the state panels below it begin.

    The grid is a fixed four; what follows is however many of the board's states are worth
    showing, and that number moves. A test about the grid has to say which of the two it is
    counting, or it starts failing every time the page grows a panel.
    """
    return text[: text.index("<h2>")]


def _board_wraps(text: str) -> list[str]:
    return re.findall(r'<div class="board-wrap"[^>]*>', text)


def _tagged_cubes(svg: str, token: str) -> list[tuple[float, float, str]]:
    """The cubes an interactive board tags as one grid's, each by its corner and its side."""
    return [
        (float(x), float(y), side)
        for x, y, side in re.findall(
            rf'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)"[^>]*data-token="{token}"', svg
        )
    ]


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
    # Six building slots, six worker circles, and three resource readouts.
    assert svg.count('stroke-dasharray="5,3"') == layout["building_slot_count"]
    assert svg.count(f'r="{ROLE_CIRCLE_RADIUS:g}"') == len(layout["worker_roles"])
    assert svg.count("<g data-resource=") == len(layout["resources"])
    for role in WORKER_ROLES:
        for line in wrap_label(role):
            assert f">{line}</text>" in svg
    assert svg.count(f'fill="{player["fill"]}"') > 0
    assert f'clip-path="url(#panelClip_{player["fill"].lstrip("#")})"' in svg
    assert len(geometry["role_x"]) == len(geometry["building_y"]) == 6


@pytest.mark.parametrize("player_id", sorted(PLAYER_COLORS))
def test_a_board_is_drawn_holding_a_wash_of_its_own_colour_it_does_not_show(
    layout: dict, player_id: str
) -> None:
    """For a page that has turns to show. Drawn dark at `opacity="0"`, and never shown from here.

    It goes second, straight onto the panel and under everything else, so that whatever is turned
    up is only ever the parchment's colour changing under the board rather than a film over it.
    """
    player = player_by_id(layout, player_id)
    svg = render_player_board_v2_svg(layout, player)
    geometry = board_geometry(len(layout["worker_roles"]))
    gradient_id = f"activeGlow_{player['fill'].lstrip('#')}"

    assert svg.count('data-active-player-glow="true"') == 1
    assert f'fill="url(#{gradient_id})" opacity="0"' in svg
    assert f'<linearGradient id="{gradient_id}" x1="0" y1="1" x2="0" y2="0">' in svg
    # Second of all, so the panel is under it and every drawn thing is over it.
    assert svg.index("<rect") < svg.index("<defs>") < svg.index("<g ")
    assert svg.index("data-active-player-glow") < svg.index("Village")
    assert svg.index("data-active-player-glow") < svg.index('stroke-dasharray="5,3"')
    # It covers the panel and takes the panel's corner, so no clip is needed to shape it.
    assert (
        f'x="0" y="0" width="{geometry["panel_width"]:.0f}"'
        f' height="{geometry["panel_height"]:.0f}" rx="{PANEL_CORNER_RADIUS:g}"'
    ) in svg
    assert "clip-path" not in svg[svg.index("<defs>") : svg.index("Village")]


def test_the_wash_is_strongest_at_the_bottom_edge_and_gone_by_the_building_band(
    layout: dict,
) -> None:
    """So it is under the slots and never reaches the circles, the readouts or the banners.

    Which is the fade's own work: the rect covers the whole board, and where the colour has run out
    is where the board stops being washed. Reading it back off the height means the two cannot
    drift apart -- the band is one of the terms that height was added up from.
    """
    player = player_by_id(layout, "player_two")
    svg = render_player_board_v2_svg(layout, player)
    geometry = board_geometry(len(layout["worker_roles"]))
    height = geometry["panel_height"]
    stops = re.findall(
        r'<stop offset="([\d.]+)" stop-color="(\S+?)" stop-opacity="([\d.]+)"/>', svg
    )

    assert stops == [
        ("0", player["fill"], str(ACTIVE_GLOW_OPACITY)),
        ("0.430", player["fill"], "0"),
    ]
    # Strong enough at the edge to be a colour and not a suggestion, and short of the third at
    # which the bottom of the board stops being parchment lit by a colour and becomes a panel
    # painted in one.
    assert 0.25 <= ACTIVE_GLOW_OPACITY <= 0.3
    # Nothing above the top of the slot band is touched, and the slots are only passed behind.
    band_top = height - (BANNER_CENTER_Y - BANNER_HEIGHT / 2) - 2 * slot_band_half_height()
    reaches = height - float(stops[1][0]) * height
    assert reaches == pytest.approx(band_top, abs=0.5)
    assert reaches < min(building_y for _, building_y in building_slot_centers(layout))
    assert reaches > geometry["role_circle_cy"] + ROLE_CIRCLE_RADIUS


def test_the_white_seat_is_washed_in_the_colour_its_own_pieces_are_drawn_with(
    layout: dict,
) -> None:
    """White on parchment is barely a change, and turned up until it is one it reads as a glow.

    So the wash is a colour of its own in the layout beside the fill and the stroke, and white's is
    the warm brown its cubes are outlined in -- the colour that already exists on that board to
    make white legible against this parchment, which is the same problem being solved twice.
    """
    white = player_by_id(layout, "player_four")

    assert white["fill"] == "#FFFFFF"
    assert white["glow"] == white["stroke"] == "#8B7B4E"
    assert f'stop-color="{white["glow"]}"' in render_player_board_v2_svg(layout, white)
    # The other three have nothing to solve: their own colour is a colour on parchment.
    for player_id in ("player_one", "player_two", "player_three"):
        player = player_by_id(layout, player_id)
        assert player["glow"] == player["fill"]


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


def test_the_board_got_wider_and_then_taller(layout: dict) -> None:
    """Wider across for the columns, and taller down for the slots that outgrew them.

    The height was held for a long time because a seat on the composed game table was sized by
    fitting two boards into the duty wheel's height, which made the board's shape decide the scale
    it was drawn at there. The table sizes a seat from the wheel's cube now, so the height is the
    board's own business again -- which is what let the slots grow to the size of a map hex and
    take the depth they needed for it.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    baseline = _svg_bodies(BASELINE_PROTOTYPE.read_text(encoding="utf-8"))[0]
    was_width, was_height = _view_box(baseline)

    assert geometry["panel_width"] > was_width * 1.25
    assert geometry["panel_height"] > was_height * 1.03


def test_the_slots_zigzag_across_the_board_rather_than_standing_in_its_columns(
    layout: dict,
) -> None:
    """Six of them are wider laid out than the board is, so they interlock instead.

    A slot is a map hex, and a map hex is wider than one of this board's columns -- so the slots
    cannot each stand in one any more. Offsetting every other slot by an apothem is how a flat-top
    hexagon packs against its neighbour, and it buys back enough width to fit all six across a board
    that has not grown at all.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    slots = building_slot_centers(layout)
    xs = [x for x, _ in slots]
    ys = [y for _, y in slots]

    assert len(slots) == int(layout["building_slot_count"]) == 6
    assert len(set(slots)) == len(slots)
    # Left to right, evenly spaced, and alternating high and low from a high first slot.
    assert xs == sorted(xs)
    # Evenly to the hundredth the centres are rounded to.
    steps = [b - a for a, b in zip(xs, xs[1:], strict=False)]
    assert steps == [pytest.approx(steps[0], abs=0.011)] * 5
    assert len(set(ys)) == 2
    assert ys[0] < ys[1]
    assert ys == [ys[index % 2] for index in range(6)]
    # A row of six would not fit; this does, and with room to spare.
    assert 6 * 2 * BUILDING_SLOT_HEX_SIZE > geometry["panel_width"] - 2 * SIDE_MARGIN
    assert xs[-1] + BUILDING_SLOT_HEX_SIZE <= geometry["panel_width"] - SIDE_MARGIN + 0.005
    # Wider than the column it used to stand in, which is the whole reason it left.
    assert BUILDING_SLOT_HEX_SIZE > ROLE_CIRCLE_RADIUS
    assert BUILDING_SLOT_HEX_SIZE > COLUMN_HALF_WIDTH


def test_a_slot_clears_its_neighbours_the_circle_above_it_and_the_board_edge(layout: dict) -> None:
    geometry = board_geometry(len(layout["worker_roles"]))
    slots = building_slot_centers(layout)
    xs = [x for x, _ in slots]
    top, bottom = slots[0][1], slots[1][1]

    # Neighbours are a row apart and clear of each other by the stated gap, as they were when they
    # stood side by side -- across the board now rather than corner to corner.
    assert bottom - top == pytest.approx(slot_apothem(), abs=0.01)
    assert xs[1] - xs[0] - 1.5 * BUILDING_SLOT_HEX_SIZE == pytest.approx(
        BUILDING_SLOT_GAP, abs=0.05
    )
    # The band hangs below the role circles by the stated gap. The centres are rounded to the two
    # decimals a path is written at, so it holds to within half a hundredth.
    circle_bottom = geometry["role_circle_cy"] + ROLE_CIRCLE_RADIUS
    assert top - slot_apothem() - circle_bottom == pytest.approx(BUILDING_ROW_GAP, abs=0.005)
    # The same margin either side, and the bottom margin the banners get at the top.
    assert xs[0] - BUILDING_SLOT_HEX_SIZE == pytest.approx(SIDE_MARGIN, abs=0.005)
    assert geometry["panel_width"] - (xs[-1] + BUILDING_SLOT_HEX_SIZE) == pytest.approx(
        SIDE_MARGIN, abs=0.005
    )
    assert geometry["panel_height"] - (bottom + slot_apothem()) == pytest.approx(
        BANNER_CENTER_Y - BANNER_HEIGHT / 2, abs=0.005
    )


def test_the_columns_kept_the_width_the_slots_used_to_give_them(layout: dict) -> None:
    """Nothing above the slots moved when they grew: the grid is its own measurement now.

    The banners, the role circles and the readouts are all spaced on the board's six columns, and
    those columns were the slots' width back when a slot stood in one. Freezing that width where it
    was is what let the slots grow without dragging the whole board wider with them.
    """
    geometry = board_geometry(len(layout["worker_roles"]))

    assert column_pitch() == pytest.approx(2 * COLUMN_HALF_WIDTH + BUILDING_SLOT_GAP)
    assert geometry["panel_width"] == pytest.approx(692.8)
    assert geometry["role_x"][0] - COLUMN_HALF_WIDTH == pytest.approx(SIDE_MARGIN)
    assert geometry["panel_width"] - (geometry["role_x"][-1] + COLUMN_HALF_WIDTH) == pytest.approx(
        SIDE_MARGIN
    )


def test_the_role_circles_did_not_grow_with_the_slots(layout: dict) -> None:
    """Widening is not scaling: the slots are the only thing the widening changed the size of."""
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))

    assert ROLE_CIRCLE_RADIUS == 34.0
    assert svg.count(f'r="{ROLE_CIRCLE_RADIUS:g}"') == len(layout["worker_roles"])


def test_a_cube_here_is_the_cube_the_duty_wheel_draws() -> None:
    """One piece, one size. A cube is a cube whether it is in a Village or on a duty tile."""
    assert 2 * TOKEN_RADIUS == DUTY_CUBE_SIZE


def test_cubes_are_spaced_the_way_the_wheel_spaces_its_tallies() -> None:
    """The wheel writes pitches; the air between two of its cubes is a pitch less the cube.

    Wider side to side than top to bottom, on the wheel and so here too, which is why the grids
    take two numbers rather than one.
    """
    assert TOKEN_GAP == DUTY_CUBE_COLUMN_WIDTH - DUTY_CUBE_SIZE
    assert TOKEN_ROW_GAP == DUTY_CUBE_CELL_HEIGHT - DUTY_CUBE_SIZE
    assert TOKEN_GAP > TOKEN_ROW_GAP


def test_the_village_and_abbey_grids_are_drawn_at_that_cube_and_that_spacing(
    layout: dict,
) -> None:
    """Both grids, every slot in them, at the wheel's size and on the wheel's two pitches."""
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"), interactive=True)
    grid = layout["starting_worker_grid"]

    for banner in layout["banners"]:
        cubes = _tagged_cubes(svg, banner["id"])
        rows = sorted({y for _, y, _ in cubes})
        columns = sorted({x for x, _, _ in cubes})

        assert len(cubes) == token_slot_count(layout)
        assert {side for *_, side in cubes} == {f"{DUTY_CUBE_SIZE:.1f}"}
        assert len(rows) == int(grid["rows"])
        assert len(columns) == int(grid["columns"])
        assert rows[1] - rows[0] == pytest.approx(DUTY_CUBE_CELL_HEIGHT, abs=0.05)
        steps = {round(right - left, 1) for left, right in zip(columns, columns[1:], strict=False)}
        assert steps == {DUTY_CUBE_COLUMN_WIDTH}


def test_the_acolytes_on_a_role_circle_are_the_same_cube_at_the_same_pitch(layout: dict) -> None:
    """A cube that walks from the Abbey to a role does not change size on the way."""
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"), interactive=True)
    paired = re.findall(
        r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)"[^>]*data-role-slot="pair"', svg
    )
    geometry = board_geometry(len(layout["worker_roles"]))

    assert ROLE_ACOLYTE_LIMIT == 2
    assert len(paired) == ROLE_ACOLYTE_LIMIT * len(layout["worker_roles"])
    assert {width for *_, width in paired} == {f"{DUTY_CUBE_SIZE:.1f}"}
    for left, right in zip(paired[::2], paired[1::2], strict=True):
        assert float(right[0]) - float(left[0]) == pytest.approx(DUTY_CUBE_COLUMN_WIDTH, abs=0.05)
        # Centred on the circle, side to side and top to bottom, and clear of its rim.
        middle = (float(left[0]) + float(right[0]) + DUTY_CUBE_SIZE) / 2
        assert min(abs(middle - x) for x in geometry["role_x"]) == pytest.approx(0.0, abs=0.05)
        assert float(left[1]) + DUTY_CUBE_SIZE / 2 == pytest.approx(
            geometry["role_circle_cy"], abs=0.05
        )
        assert middle - float(left[0]) < ROLE_CIRCLE_RADIUS


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
    # The tallest label is two lines, and it clears the corner the readouts stand in.
    label_top = geometry["role_label_baseline"] - ROLE_LINE_HEIGHT - LABEL_ASCENT
    assert wrap_label("Road Engineer") == ["Road", "Engineer"]
    assert label_top > geometry["resources"]["bottom"]


# How tall each icon is drawn, per unit of the size it is asked for. Measured off the rendered
# artwork with getBBox rather than derived, so it holds only while the drawings do -- it is here to
# size the readouts, not to police the pictures. The renderer keeps the same measurement split into
# the part above the point an icon is drawn from and the part below, which is what a row needs to
# centre one; this is the check that the two say the same thing.
ICON_HEIGHT_PER_UNIT = {"wheat": 1.7243, "cube": 1.2400, "coin": 1.2400}
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
    # What the renderer thinks an icon's height is, against the measurement. The two are within a
    # couple of percent rather than equal: the renderer's is the artwork's own construction and the
    # measurement takes in the stroke drawn around it.
    for icon, per_unit in ICON_HEIGHT_PER_UNIT.items():
        assert resource_icon_height(icon) == pytest.approx(
            per_unit * resource_icon_size(icon), rel=0.02
        )
    assert height["wheat"] == pytest.approx(DUTY_ICON_HEIGHT_IN_CUBES["wheat"], rel=0.02)
    for icon in ("cube", "coin"):
        assert 0.9 < height[icon] / DUTY_ICON_HEIGHT_IN_CUBES[icon] < 1.0
    # The wheat is sized on its own because it has to be: put it on the size the other two share
    # and it goes back over the wheel's, which is the state this came from.
    assert WHEAT_ICON_SIZE < COMPACT_ICON_SIZE
    shared = ICON_HEIGHT_PER_UNIT["wheat"] * COMPACT_ICON_SIZE / MARKER_CUBE
    assert shared > DUTY_ICON_HEIGHT_IN_CUBES["wheat"] * 1.05


def _readouts(svg: str) -> list[tuple[str, str, float, str]]:
    """Each readout: its id, its artwork, where its amount is centred, and what the amount says."""
    rows = []
    for resource in re.finditer(r'<g data-resource="(\w+)"[^>]*>', svg):
        amount_start = svg.index('<text x="', resource.end())
        row_end = svg.index('</g>', amount_start) + len('</g>')
        row = svg[resource.start() : row_end]
        amount = re.search(r'<text x="(-?[\d.]+)"[^>]*>(\d+)</text>', row)
        rows.append(
            (
                resource.group(1),
                row[: row.index("<text")],
                float(amount.group(1)),
                amount.group(2),
            )
        )
    return rows


def test_the_three_readouts_share_the_two_columns_the_banners_leave_free(layout: dict) -> None:
    """Icon over amount, three of them side by side, standing on the board's own column grid.

    The board is six columns and the banners take two each, so the readouts get the two left over
    and split them three ways -- which is what stands them in a row of even pitch whose left-hand
    end lands exactly where the Abbey banner's right-hand end does.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    block = geometry["resources"]
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))
    rows = _readouts(svg)
    abbey = banner_center_x(geometry, 2)

    assert [row[0] for row in rows] == [resource["id"] for resource in layout["resources"]]
    assert len(rows) == RESOURCE_READOUT_COUNT == len(block["cell_x"])
    assert [row[3] for row in rows] == [str(r["count"]) for r in layout["resources"]]
    # Each amount centred under its own icon rather than strung out along a shared edge.
    assert [row[2] for row in rows] == [round(x, 1) for x in block["cell_x"]]
    for (_, artwork, _, _), cell_x in zip(rows, block["cell_x"], strict=True):
        assert f"{cell_x:.1f}" in artwork
    # Even pitch, filling exactly the columns the banners do not.
    steps = [b - a for a, b in zip(block["cell_x"], block["cell_x"][1:], strict=False)]
    band = RESOURCE_BAND_COLUMNS * column_pitch()
    assert steps == [pytest.approx(band / RESOURCE_READOUT_COUNT)] * (RESOURCE_READOUT_COUNT - 1)
    assert block["right"] == geometry["panel_width"] - SIDE_MARGIN
    assert block["left"] == pytest.approx(abbey[0] + abbey[1] / 2)
    assert block["right"] - block["left"] == pytest.approx(band)
    # All of it in the top third, beside the Village and Abbey grids rather than under them. It
    # was the top quarter before the board was shortened; the block did not move, the board did.
    assert block["bottom"] < geometry["panel_height"] / 3


def test_every_icon_centres_in_the_band_however_it_is_drawn(layout: dict) -> None:
    """The three are different sizes and none is drawn around the middle of its own shape.

    The wheat is the awkward one: it fans upwards from the point it is drawn from and reaches
    barely half as far below it. Placed on the band's middle it would ride high; centred by its own
    box, the three stand on one line.
    """
    tops = {
        icon: resource_icon_center_y(icon) - ICON_RISE_RATIO[icon] * resource_icon_size(icon)
        for icon in ICON_RISE_RATIO
    }
    feet = {
        icon: resource_icon_center_y(icon) + ICON_FOOT_RATIO[icon] * resource_icon_size(icon)
        for icon in ICON_FOOT_RATIO
    }

    for icon, top in tops.items():
        assert top == pytest.approx(-resource_icon_height(icon) / 2), icon
        assert feet[icon] == pytest.approx(resource_icon_height(icon) / 2), icon
    # The wheat is the one that has to be moved to manage it, and downwards.
    assert resource_icon_center_y("wheat") > 1
    assert abs(resource_icon_center_y("cube")) < 0.5


def test_every_stock_gets_a_key_big_enough_to_press(layout: dict) -> None:
    """The key is the whole pill, not the picture on it.

    Silver's coin is about 23 across and the amounts are set at 16. Neither is a thing to ask
    anyone to aim at, so the target is the pill and the artwork merely sits inside it.
    """
    svg = render_player_board_v2_svg(layout, players_of(layout)[0], choice_keys=True)
    keys = re.findall(r"<rect data-resource-choice-key=\"(\w+)\"[^>]*/>", svg)
    block = board_geometry(len(layout["worker_roles"]))["resources"]

    assert keys == [resource["id"] for resource in layout["resources"]]
    for cx, resource in zip(block["cell_x"], layout["resources"], strict=True):
        assert (
            f'data-resource-choice-key="{resource["id"]}"'
            f' x="{cx - RESOURCE_CHOICE_WIDTH / 2:.1f}" y="{RESOURCE_CHOICE_TOP:g}"'
            f' width="{RESOURCE_CHOICE_WIDTH:g}" height="{RESOURCE_CHOICE_HEIGHT:g}"'
        ) in svg
    assert RESOURCE_CHOICE_WIDTH == 66.0 and RESOURCE_CHOICE_HEIGHT == 61.0
    assert resource_icon_size("coin") < RESOURCE_CHOICE_WIDTH / 2


def test_resource_artwork_is_decorative_and_never_takes_pointer_events(layout: dict) -> None:
    svg = render_player_board_v2_svg(layout, players_of(layout)[0], choice_keys=True)
    readouts = re.findall(r'<g data-resource="\w+"[^>]*>', svg)

    assert readouts, "no resource readouts were drawn"
    for readout in readouts:
        assert 'pointer-events="none"' in readout


def test_a_key_is_drawn_hidden_and_only_an_attribute_shows_it(layout: dict) -> None:
    """So the page reveals and hides, and never has a fill to assign."""
    svg = render_player_board_v2_svg(layout, players_of(layout)[0], choice_keys=True)

    for key in re.findall(r"<rect data-resource-choice-key=[^>]*/>", svg):
        assert 'visibility="hidden"' in key
    styles = resource_choice_styles()
    assert '[data-resource-choice="true"] [data-resource-choice-key]' in styles
    assert "visibility: visible; cursor: pointer;" in styles
    # And the rules go while the keys are up: three keys with rules between them read as a table.
    assert '[data-resource-choice="true"] [data-resource-divider]' in styles
    assert styles.count("visibility: hidden;") == 1
    assert "fill" not in styles and "#" not in styles


def test_the_keys_go_under_the_artwork_they_highlight(layout: dict) -> None:
    """SVG has no z-index and only document order, so an appended key would bury the readout."""
    svg = render_player_board_v2_svg(layout, players_of(layout)[0], choice_keys=True)
    order = [
        match.lastgroup
        for match in re.finditer(
            r"(?P<divider>data-resource-divider)|(?P<key>data-resource-choice-key)"
            r"|(?P<readout><g data-resource=)",
            svg,
        )
    ]

    assert order == ["divider"] * 2 + ["key"] * 3 + ["readout"] * 3


def test_a_board_that_will_never_be_asked_does_not_carry_the_keys(layout: dict) -> None:
    """Opt in, as the first player seal does.

    Three rects a board that no stylesheet on the page can reveal and no script on it would ever
    want to are not hidden markup, they are dead markup: nothing distinguishes them from a mistake,
    and the next reader has to prove they are unreachable before touching anything near them.
    """
    plain = render_player_board_v2_svg(layout, players_of(layout)[0])

    assert "data-resource-choice-key" not in plain
    # And nothing else moves when they are asked for: the keys are the whole of the difference.
    asked = render_player_board_v2_svg(layout, players_of(layout)[0], choice_keys=True)
    stripped = re.sub(r"<rect data-resource-choice-key=[^>]*/>", "", asked)
    stripped = re.sub(r' data-resource-choice-glyph="\w+"', "", stripped)
    assert stripped == plain


def test_the_page_that_shows_the_board_shows_it_being_asked(layout: dict) -> None:
    """A board mid-question is a state of the board, so the page for the board's states has it.

    Shown by asking the renderer for the keys and then setting the attribute the game table sets,
    rather than by drawing a picture of the state, so what is reviewed here is what is shipped.
    """
    page = render_player_boards_v2_html(layout)
    panel = page[page.index("<h2>") :]

    assert panel.count('data-resource-choice="true"') == 1
    assert panel.count("data-resource-choice-key") == 3
    # The pair is the point: the rules going is half of what the choosing state looks like.
    assert panel.count("<figcaption>") == 2
    assert '[data-resource-choice="true"] [data-resource-divider]' in page
    # And the four boards the page opened with are not touched by any of it.
    assert page[: page.index("<h2>")].count("data-resource-choice-key") == 1


def test_the_readouts_start_where_the_colour_tag_stops(layout: dict) -> None:
    """Two things want this corner, and they divide it between them.

    The tag runs down the board's right-hand edge as far as its own size, and the rules pick up
    from exactly there, so the boundary between them is one line rather than a judged gap. Under
    that the tag is a diagonal cutting back to the edge, and the readouts clear it with room over.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    block = geometry["resources"]

    def tag_reaches(x: float) -> float:
        """How far down the tag has come by the time its edge gets to `x`."""
        return x - geometry["panel_width"] + CORNER_TAG_SIZE - CORNER_TAG_OVERSHOOT

    assert block["top"] - RESOURCE_DIVIDER_OVERHANG == CORNER_TAG_SIZE
    # Which is below the banners rather than level with them: the tag is the deeper of the two.
    assert CORNER_TAG_SIZE > BANNER_CENTER_Y + BANNER_HEIGHT / 2
    # The right-hand readout is the one under the tag, and the tag has cut well back by then.
    assert tag_reaches(block["right"]) < block["top"]
    # The block is inside the panel on every side.
    assert block["top"] > 0
    assert block["right"] < geometry["panel_width"]
    assert block["left"] > 0


def test_a_rule_stands_on_every_seam_between_one_readout_and_the_next(layout: dict) -> None:
    """Thin vertical lines, on the seams only, running past the readouts at both ends.

    Two of them for three readouts. The ends of the row are left open: a rule out there would read
    as a frame drawn around the block rather than as a division inside it.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    block = geometry["resources"]
    svg = render_player_board_v2_svg(layout, player_by_id(layout, "player_one"))
    rules = re.findall(r"<line data-resource-divider=\"true\"[^>]*/>", svg)

    assert len(rules) == len(block["divider_x"]) == RESOURCE_READOUT_COUNT - 1
    for rule, x in zip(rules, block["divider_x"], strict=True):
        ends = [float(value) for value in re.findall(r'[xy][12]="(-?[\d.]+)"', rule)]
        assert ends[0] == ends[2] == round(x, 1)
        assert ends[1] == pytest.approx(block["top"] - RESOURCE_DIVIDER_OVERHANG, abs=0.05)
        assert ends[3] == pytest.approx(block["bottom"] + RESOURCE_DIVIDER_OVERHANG, abs=0.05)
    # Each one halfway between the readouts it divides, and clear of both.
    neighbours = list(zip(block["cell_x"], block["cell_x"][1:], strict=False))
    for x, (left, right) in zip(block["divider_x"], neighbours, strict=True):
        assert x == pytest.approx((left + right) / 2)
        assert x - left > resource_icon_height("coin") / 2
    # And nothing at the ends of the row.
    assert min(block["divider_x"]) > block["left"]
    assert max(block["divider_x"]) < block["right"]


def test_no_board_carries_a_first_player_marker_any_more(layout: dict) -> None:
    """The card is gone, and so is the corner it stood in: the readouts have it now.

    It was never anything but layout state to look at -- no board here decides who starts -- and it
    would have sat on top of the readouts, so it went rather than moving.
    """
    page = render_player_boards_v2_html(layout)
    interactive = render_player_board_v2_svg(
        layout, player_by_id(layout, "player_one"), interactive=True
    )

    assert "first_player_marker" not in layout
    assert "First player" not in page
    assert "first-player" not in page
    assert "first-player" not in interactive
    # The card's own colours went with it.
    assert not [key for key in layout["palette"] if key.startswith("marker")]


def test_the_board_closed_the_gap_the_readouts_came_out_of(layout: dict) -> None:
    """The readouts left a third of the board empty when they went to the corner. This is it shut.

    The labels used to hang a fixed 130 units below the cube grid, a distance set when the readouts
    stood in that space. They hang off whatever is above them now, so the band is as deep as the
    labels need and no deeper, and everything below comes up with them.

    The game table had to be taught to size a seat from the duty wheel's cube before this could
    move: it used to stretch two boards to the wheel's height, which made a shorter board render
    larger and a Village cube stop matching a duty tile's.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    tokens_bottom = geometry["token_grid_top"] + 2 * 2 * TOKEN_RADIUS + TOKEN_ROW_GAP
    label_top = geometry["role_label_baseline"] - ROLE_LINE_HEIGHT - LABEL_ASCENT

    # Measured to the top of the slots rather than to the bottom of the board, so it reads the gap
    # this closed and not the depth the slots later took when they grew to a map hex's size.
    band_top = geometry["building_y"][0] - slot_apothem()
    assert band_top == pytest.approx(237.42, abs=0.005)
    assert band_top < 299.0
    # The labels clear the readouts' rules, which hang lower than the cubes do, by that one gap.
    rules_bottom = geometry["resources"]["bottom"] + RESOURCE_DIVIDER_OVERHANG
    assert tokens_bottom < rules_bottom
    assert label_top - rules_bottom == pytest.approx(ROLE_LABEL_TOP_GAP, abs=0.005)
    # And the circles sit one label-block below that, deep enough for the two-line labels.
    assert geometry["role_circle_cy"] - ROLE_CIRCLE_RADIUS - label_top == pytest.approx(
        (ROLE_LABEL_MAX_LINES - 1) * ROLE_LINE_HEIGHT + LABEL_ASCENT + ROLE_LABEL_GAP
    )
    assert max(len(wrap_label(role["label"])) for role in layout["worker_roles"]) == (
        ROLE_LABEL_MAX_LINES
    )


def test_the_smaller_cubes_centre_in_the_band_rather_than_pulling_the_board_up(
    layout: dict,
) -> None:
    """The grids kept the band the older, larger cubes needed rather than closing up around the
    smaller ones, so the two rows still sit in the middle of the space the banners leave them.

    What hangs below the band did move, but not because of this: the readouts went to the corner
    and the gap they had stood in was closed.
    """
    geometry = board_geometry(len(layout["worker_roles"]))
    band_top = BANNER_CENTER_Y + BANNER_HEIGHT / 2 + TOKEN_GRID_TOP_GAP
    grid_height = 2 * 2 * TOKEN_RADIUS + TOKEN_ROW_GAP

    assert TOKEN_BAND_HEIGHT == 2 * MARKER_CUBE + 6.0
    assert grid_height < TOKEN_BAND_HEIGHT
    assert geometry["token_grid_top"] - band_top == pytest.approx(
        band_top + TOKEN_BAND_HEIGHT - (geometry["token_grid_top"] + grid_height)
    )


def _corners(path: str) -> list[float]:
    """A path's corners, flattened to x, y, x, y so they can be compared with a tolerance."""
    return [float(value) for value in re.findall(r"-?[\d.]+", path)]


def test_html_shows_four_boards_in_a_two_by_two_grid(page: str) -> None:
    assert page.startswith("<!DOCTYPE html>")
    assert TITLE in page
    assert SUBTITLE_START in page
    grid = _boards_grid(page)
    assert len(_svg_bodies(grid)) == 4
    assert grid.count('<div class="board-row">') == 2
    assert grid.count('data-component="player-board-v2"') == 4
    assert "<iframe" not in page


def test_html_carries_the_board_labels_and_player_colours(page: str) -> None:
    for text in ("Village", "Abbey", *WORKER_ROLES[:1]):
        assert f">{text}</text>" in page
    for role in WORKER_ROLES:
        for line in wrap_label(role):
            assert f">{line}</text>" in page
    for _, fill, stroke in PLAYER_COLORS.values():
        assert fill in page
        assert stroke in page


def test_every_board_on_the_page_carries_its_own_resources(page: str) -> None:
    """Four boards, each with the same three readouts: no board is singled out any more."""
    assert 'data-player="player_one" data-player-color="red"' in _board_wraps(page)[0]
    for board in _svg_bodies(page):
        assert len(_readouts(board)) == RESOURCE_READOUT_COUNT
        assert board.count("data-resource-divider") == RESOURCE_READOUT_COUNT - 1


def test_generator_default_output_is_the_generated_player_boards_v2_page() -> None:
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "player_boards_v2.html"


def test_generator_writes_generated_page(tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "player_boards_v2.html"
    written = generate_player_boards_v2_page(output_path=output_path)

    assert written == output_path
    content = output_path.read_text(encoding="utf-8")
    assert TITLE in content
    assert len(_svg_bodies(_boards_grid(content))) == 4


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

    Six departures, all deliberate. The board got wider, because the prototype's building slots are
    two thirds of a map hex and these are a whole one. Then the type grew, because it was sized for
    a board that narrow and read small on this one. Then the cubes shrank to the duty wheel's, so
    that a player's piece reads as one piece across the table. Then the resource readouts came out
    of their circles and went to the corner, and the first-player card went with them. Then the
    board got shorter, closing the gap they had stood in. Then the slots grew to the size a map hex
    renders at on the composed table, which took more depth than that gap gave back. What is left is
    what the prototype set and no reason has come up to change: the worker circles, and the number
    of every piece.
    """
    generated = _svg_bodies(
        _boards_grid(
            generate_player_boards_v2_page(
                output_path=tmp_path / "player_boards_v2.html"
            ).read_text(encoding="utf-8")
        )
    )
    baseline = _svg_bodies(BASELINE_PROTOTYPE.read_text(encoding="utf-8"))
    grew = {
        'font-size="11"': f'font-size="{BANNER_FONT_SIZE:g}"',
        'font-size="10"': f'font-size="{ROLE_FONT_SIZE:g}"',
        'font-size="13"': f'font-size="{RESOURCE_COUNT_FONT_SIZE:g}"',
    }
    cube = 'width="14.0" height="14.0"'
    now_cube = f'width="{DUTY_CUBE_SIZE:.1f}" height="{DUTY_CUBE_SIZE:.1f}"'
    kept = ('r="34"',)

    assert len(generated) == len(baseline) == 4
    for board, was in zip(generated, baseline, strict=True):
        width, height = _view_box(board)
        old_width, old_height = _view_box(was)

        assert width > old_width
        assert height > old_height
        for size in kept:
            assert board.count(size) == was.count(size), size
        # Drawn bigger, with nothing left behind at the old size.
        for before, now in grew.items():
            assert before not in board, before
            assert now in board, now
            assert float(now.split('"')[1]) > float(before.split('"')[1])
        # Drawn smaller, and every cube the prototype drew is still there.
        assert cube not in board
        assert DUTY_CUBE_SIZE < MARKER_CUBE
        assert board.count(now_cube) == was.count(cube)
        # The readouts are a row in the corner where the prototype drew three circles in the
        # middle, and the card the prototype gave its first board is on none of these.
        assert 'r="27"' in was and 'r="27"' not in board
        assert len(_readouts(board)) == RESOURCE_READOUT_COUNT
        assert "first-player" not in board
    # As many of each as the prototype drew, counted on a board the prototype did not give the
    # card to: its label was set at the size the amounts are.
    board, was = generated[1], baseline[1]
    for before, now in grew.items():
        assert board.count(now) == was.count(before), now


def _view_box(svg: str) -> tuple[float, float]:
    _, _, width, height = re.search(r'viewBox="([^"]+)"', svg).group(1).split()
    return float(width), float(height)


def test_generated_page_matches_baseline_facts(page: str) -> None:
    baseline = BASELINE_PROTOTYPE.read_text(encoding="utf-8")

    for text in (TITLE, SUBTITLE_START):
        assert text in baseline
        assert text in page
    for _, fill, _ in PLAYER_COLORS.values():
        assert fill in baseline
        assert fill in page
    assert len(_svg_bodies(baseline)) == len(_svg_bodies(_boards_grid(page))) == 4
    # The first-player card is the one thing the prototype names that these boards do not draw.
    assert ">First player</text>" in baseline and ">marker</text>" in baseline
    assert "First player" not in page
