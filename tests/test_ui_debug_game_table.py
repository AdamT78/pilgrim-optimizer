"""The generated game table page is composition only, so these tests are about arrangement.

They check that every component reached the page through its own renderer, that the three columns
hold the right things in the right order, that the shared cube scale is what sizes them, and that
the compact control stack under the Alms Table wires only local debug behaviour. Nothing here looks
at the drawing itself; each renderer's own tests do that, and nothing here renders a browser.
"""

import json
import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_game_table import (
    BODY_CHROME,
    DEFAULT_PLAYER_COUNT,
    GAP_PX,
    PAGE_TITLE,
    PANEL_CHROME,
    PIETY_VARIANT_ID,
    PLAYER_COUNTS,
    REF_AVAIL_WIDTH,
    REF_VIEWPORT_HEIGHT,
    SEAT_COLS,
    SEATED_PLAYERS,
    SETUP_ROLLS,
    board_measurements,
    crop_svg,
    default_output_path,
    duty_hexagon,
    generate_game_table_page,
    regular_hexagon_path,
    regularise_duty_hexagon,
    seat_numbers_by_player,
    solve_table_scale,
    visible_seats_by_count,
)
from tools.ui_debug.generate_game_setup import EDGE_HEX_PATH, START_HEX_BY_ROLL, acolyte_places
from tools.ui_debug.render_alms_table import (
    CUBE_SIZE as ALMS_CUBE_SIZE,
)
from tools.ui_debug.render_alms_table import (
    RANK_FIRST,
    SEASON_END_LABEL_FONT_SIZE,
    UNITS_PER_PLAYER_UNIT,
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_controls_html,
)
from tools.ui_debug.render_alms_table import STAR_LABEL_FONT_SIZE as TRACK_STAR_FONT_SIZE
from tools.ui_debug.render_alms_table import STAR_OUTER_RADIUS as TRACK_STAR_RADIUS
from tools.ui_debug.render_buildings import HEX_RADIUS as TILE_HEX_RADIUS
from tools.ui_debug.render_duty_wheel import (
    CUBE_SIZE as DUTY_CUBE_SIZE,
)
from tools.ui_debug.render_duty_wheel import (
    load_duty_wheel_layout,
    render_duty_wheel_controls_html,
)
from tools.ui_debug.render_map import load_map_layout, render_map_svg
from tools.ui_debug.render_piety_track_v2 import load_piety_track_v2_layout, variant_by_id
from tools.ui_debug.render_pilgrimage_sites import STAR_OUTER_RADIUS as SITE_STAR_RADIUS
from tools.ui_debug.render_pilgrimage_sites import VP_TEXT_FONT_SIZE as SITE_VP_FONT_SIZE
from tools.ui_debug.render_player_boards_v2 import (
    BUILDING_SLOT_HEX_SIZE,
    MARKER_CUBE,
    ROLE_FONT_SIZE,
    TOKEN_RADIUS,
    board_geometry,
    load_player_boards_v2_layout,
    player_by_id,
    players_of,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
GENERATOR_SCRIPT = UI_DEBUG_DIR / "generate_game_table.py"
INDEX_HTML = UI_DEBUG_DIR / "index.html"

# The text the page used to carry above the table, and no longer should.
FORMER_HEADING = "PILGRIM — Generated game table layout"
FORMER_BLURB = "The existing debug renderers composed into one 2-player table"

ALMS_LAYOUT = load_alms_table_layout()


def _row_height(solved) -> float:
    """How tall the main row comes out: whichever of the map or the alms table needs more of it."""
    return solved.cube * solved.row_cubes + PANEL_CHROME


def _per_unit(solved, board: str) -> float:
    """Pixels one of a board's own units renders as, at the cube size the table solved for.

    The duty wheel is the one board the stylesheet sizes by its height rather than its width: it
    is handed whatever the row has left once the piety track and the chrome are out of it, so it
    is measured down its own crop instead of across it.
    """
    if board == "action":
        height = _row_height(solved) - solved.cube * solved.piety_cubes - 2 * PANEL_CHROME - GAP_PX
        return height / solved.crop["action"][3]
    width = {
        "alms": solved.cube * solved.piety_coef * solved.alms_over_piety,
        "piety": solved.cube * solved.piety_coef,
        "player": solved.cube * solved.player_k,
        "map": solved.cube * solved.mult["map"] * solved.map_scale,
    }[board]
    return width / solved.crop[board][2]


@pytest.fixture(scope="module")
def page(tmp_path_factory: pytest.TempPathFactory) -> str:
    output = tmp_path_factory.mktemp("game_table") / "game_table.html"
    return generate_game_table_page(output_path=output).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def scale():
    content, hexes, cubes = board_measurements(
        load_alms_table_layout(),
        load_piety_track_v2_layout(),
        load_player_boards_v2_layout(),
        load_duty_wheel_layout(),
        load_map_layout(),
    )
    return content, hexes, cubes, solve_table_scale(content, hexes, cubes)


def _block(page: str, class_name: str) -> str:
    """One `<div class="...">` and its contents, nested divs included."""
    match = re.search(rf'<div\b[^>]*\bclass="{re.escape(class_name)}"[^>]*>', page)
    if match is None:
        raise AssertionError(f"{class_name} is not on the page")
    start = match.start()
    depth = 0
    for tag in re.finditer(r"<div\b|</div>", page[start:]):
        depth += 1 if tag.group(0).startswith("<div") else -1
        if depth == 0:
            return page[start : start + tag.end()]
    raise AssertionError(f"{class_name} is never closed")


def test_generator_script_exists() -> None:
    assert GENERATOR_SCRIPT.is_file()
    assert default_output_path() == UI_DEBUG_DIR / "generated" / "game_table.html"


def test_generator_writes_the_page_to_a_temp_path(tmp_path: Path) -> None:
    written = generate_game_table_page(output_path=tmp_path / "nested" / "game_table.html")

    assert written == tmp_path / "nested" / "game_table.html"
    assert written.is_file()
    assert '<div class="game-table-stage">' in written.read_text(encoding="utf-8")


def test_the_page_opens_straight_into_the_table(page: str) -> None:
    """No heading, no blurb: the first thing on the page is the table itself.

    A debug view of an arrangement should show the arrangement, not a page about it. The tab
    keeps a name, since that is the one piece of text a window needs.
    """
    assert f"<title>{PAGE_TITLE}</title>" in page

    body = page[page.index("<body>") :]
    assert FORMER_HEADING not in page
    assert FORMER_BLURB not in page
    for tag in ("<h1", "<h2", "<header", "<p "):
        assert tag not in body, tag
    assert body.index('<div class="game-table-stage">') < body.index("<svg")


def test_no_styling_is_left_over_from_the_removed_heading(page: str) -> None:
    """The old page heading is gone; compact-control chrome is page-local only."""
    stylesheet = page[page.index("<style>") : page.index("</style>")]
    controls = stylesheet[stylesheet.index(".table-controls") :]

    for stale in ("game-table-subtitle", "h1 ", "--ink", "Georgia"):
        assert stale not in stylesheet, stale
    # Colour only appears once the compact controls' rules begin.
    assert "color:" not in stylesheet[: stylesheet.index(".table-controls")]
    assert "color:" in controls


def test_the_main_row_is_the_alms_column_the_piety_duty_column_and_the_map(page: str) -> None:
    """Three across, in that order, and no seat among them.

    The left column is only the Alms Table and compact control stack under it. The seats stay in
    their own row below, so changing player count never has to ask this column for more height.
    """
    assert '<div class="game-table-stage">' in page
    row = _block(page, "row")
    left = _block(page, "left")

    for class_name in ("left", "col", "panel p-map"):
        assert f'<div class="{class_name}">' in row, class_name
    assert row.index('class="left"') < row.index('class="col"') < row.index("p-map")
    assert "p-player" not in row
    assert left.index("p-alms") < left.index("table-controls")
    assert "p-player" not in left


def test_the_seats_stand_in_one_row_below_the_main_row(page: str) -> None:
    """All four boards side by side, under everything else on the stage.

    The stage is left-aligned rather than centred, which is what lines the row up: the seat row
    and the main row start on the same vertical, so the first board sits under the first panel of
    the row above -- the alms table.
    """
    stage = _block(page, "game-table-stage")
    seats = _block(page, "seats")

    assert stage.index('<div class="row">') < stage.index('<div class="seats">')
    assert seats.count('data-component="player-board-v2"') == 4
    assert ".seats { display: flex; gap: var(--gap); }" in page
    assert "align-items: flex-start" in page[page.index(".game-table-stage") :][:200]


def test_column_two_holds_the_piety_track_above_the_duty_wheel(page: str) -> None:
    column = _block(page, "col")

    assert column.index("p-piety") < column.index("p-action")
    assert column.index('data-component="piety-track-v2"') < column.index(
        'data-component="duty-wheel"'
    )


def test_column_three_holds_the_map(page: str) -> None:
    """The map is its own panel rather than a column, since nothing sits above it."""
    assert '<div class="panel p-map">' in page
    map_panel = _block(page, "panel p-map")

    assert 'id="ship-marker"' in map_panel
    assert "setup-building-fill" in map_panel
    assert 'data-component="alms-table"' not in map_panel


def test_page_embeds_the_rendered_map(page: str) -> None:
    """The map arrives through the renderer, with the setup overlay the setup page draws."""
    plain = render_map_svg(load_map_layout())

    for element in plain.splitlines()[1:-1]:
        assert element.strip() in page


def test_page_embeds_the_duty_wheel(page: str) -> None:
    assert 'data-component="duty-wheel"' in page
    assert 'data-token="merchant"' in page
    assert page.count('data-component="duty-wheel"') == 1


def test_page_embeds_the_alms_table(page: str) -> None:
    assert page.count('data-component="alms-table"') == 1
    assert "Alms Table" in page


def test_page_shows_only_the_three_four_player_piety_track(page: str) -> None:
    assert PIETY_VARIANT_ID == "3_4_player"
    assert f'data-piety-variant="{PIETY_VARIANT_ID}"' in page
    assert 'data-piety-variant="2_player"' not in page
    assert page.count('data-component="piety-track-v2"') == 1
    assert "Piety Track" in page


def test_the_table_seats_every_player_the_layout_describes(page: str) -> None:
    """All four boards now, where it used to draw the second column of a four-seat grid.

    Which board leads is layout state to look at rather than a seating rule: the 2P/3P/4P control
    only hides later seats, it does not reseat anyone.
    """
    layout = load_player_boards_v2_layout()
    seats = _block(page, "seats")

    assert len(SEATED_PLAYERS) == SEAT_COLS == 4
    assert seats.count('data-component="player-board-v2"') == 4
    assert {player["id"] for player in players_of(layout)} == set(SEATED_PLAYERS)
    for player_id in SEATED_PLAYERS:
        assert f'data-player="{player_id}"' in seats


def test_the_red_board_leads_the_row_and_the_rest_follow_in_the_layouts_order(page: str) -> None:
    """Red first, then the layout's own order read on from it and round to the board it skipped.

    Reading on rather than restarting keeps the run the seating order the layout already gives,
    with red simply the board it is read from.
    """
    layout = load_player_boards_v2_layout()
    order = [player["id"] for player in players_of(layout)]
    seats = _block(page, "seats")

    seated = re.findall(r'data-player="(\w+)" data-player-color="(\w+)"', seats)
    assert [colour for _, colour in seated] == ["red", "yellow", "blue", "white"]
    assert seated[0][1] == "red"

    start = order.index(seated[0][0])
    rotated = order[start:] + order[:start]
    assert [player_id for player_id, _ in seated] == rotated


def test_the_four_seat_slots_carry_stable_player_count_hooks(page: str) -> None:
    """Fixed slots 1–4 in seat order, so the count control can hide without reshuffling."""
    seats = _block(page, "seats")
    hooks = re.findall(
        r'data-player-seat="(\d)" data-player="(\w+)" data-player-color="(\w+)"',
        seats,
    )

    assert hooks == [
        ("1", "player_two", "red"),
        ("2", "player_three", "yellow"),
        ("3", "player_four", "blue"),
        ("4", "player_one", "white"),
    ]
    assert seat_numbers_by_player() == {
        "player_two": 1,
        "player_three": 2,
        "player_four": 3,
        "player_one": 4,
    }


def test_no_board_at_this_table_says_who_starts(page: str) -> None:
    """The first-player card is gone from the board, and so is the seat that used to carry it.

    Nothing here ever worked out who starts -- it was layout state to look at, with no control to
    move it -- and the corner it sat in is the resources' now.
    """
    seats = _block(page, "seats")

    assert "first-player" not in page
    assert ">First player</text>" not in page
    assert re.findall(r'data-player="(\w+)" data-player-color="\w+">', seats) == list(
        SEATED_PLAYERS
    )


# ---------------------------------------------------------------------------------------------
# Compact controls
# ---------------------------------------------------------------------------------------------


def test_the_compact_controls_sit_under_the_alms_table(page: str) -> None:
    left = _block(page, "left")
    controls = _block(page, "table-controls")

    assert left.index("p-alms") < left.index("table-controls")
    assert "p-action" not in left
    assert 'data-component="game-table-controls"' in controls
    assert PLAYER_COUNTS == (2, 3, 4)
    assert DEFAULT_PLAYER_COUNT == 4
    assert SETUP_ROLLS == (1, 2, 3, 4, 5, 6)


def test_row_one_has_player_count_then_setup_roll_buttons(page: str) -> None:
    controls = _block(page, "table-controls")
    row_one = re.search(r'data-controls-row="1">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_one is not None
    body = row_one.group(1)

    assert "2P</button>" in body
    assert "3P</button>" in body
    assert "4P</button>" in body
    assert body.index(">2P<") < body.index(">3P<") < body.index(">4P<")
    for roll in SETUP_ROLLS:
        assert f'data-setup-roll-button="{roll}"' in body
        assert f">{roll}</button>" in body
    assert body.index(">4P<") < body.index(">1<")
    # the ship comes last, after the setup rolls it rides with
    assert 'data-ship-advance="true">S+</button>' in body
    assert body.index(">6<") < body.index(">S+<")


def test_player_count_and_setup_roll_defaults_are_tagged(page: str) -> None:
    controls = _block(page, "table-controls")
    count_buttons = re.findall(
        r'data-player-count-button="(\d)" aria-pressed="(\w+)">([^<]+)</button>',
        controls,
    )
    roll_buttons = re.findall(
        r'data-setup-roll-button="(\d)" aria-pressed="(\w+)">([^<]+)</button>',
        controls,
    )

    assert count_buttons == [("2", "false", "2P"), ("3", "false", "3P"), ("4", "true", "4P")]
    assert [button[0] for button in roll_buttons] == [str(roll) for roll in SETUP_ROLLS]
    assert roll_buttons[0] == ("1", "true", "1")


def test_row_two_has_disc_player_dropdown_and_step_buttons(page: str) -> None:
    controls = _block(page, "table-controls")
    row_two = re.search(r'data-controls-row="2">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_two is not None
    body = row_two.group(1)

    options = re.findall(r'<option value="(\d)"(?: selected)?>(P\d)</option>', body)
    assert options == [("1", "P1"), ("2", "P2"), ("3", "P3"), ("4", "P4")]
    assert 'id="disc-player-seat"' in body
    assert 'data-disc-track="alms" data-disc-delta="1">A+</button>' in body
    assert 'data-disc-track="alms" data-disc-delta="-1">A-</button>' in body
    assert 'data-disc-track="piety" data-disc-delta="1">P+</button>' in body
    assert 'data-disc-track="piety" data-disc-delta="-1">P-</button>' in body


def test_row_three_has_acolyte_controls_with_game_setup_places(page: str) -> None:
    controls = _block(page, "table-controls")
    row_three = re.search(r'data-controls-row="3">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_three is not None
    body = row_three.group(1)

    assert 'id="acolyte-player-seat"' in body
    assert 'id="acolyte-source"' in body
    assert 'id="acolyte-target"' in body
    assert 'id="move-acolyte">Move acolyte</button>' in body

    places = acolyte_places(load_player_boards_v2_layout())
    for place_id, label in places:
        expected = f'<option value="{place_id}"'
        assert expected in body
        assert f">{label}</option>" in body


def test_controls_stay_compact_without_explanatory_text(page: str) -> None:
    controls = _block(page, "table-controls")

    for forbidden in ("<label", "<p ", "<h1", "<h2", "<h3", "slot-list", "subtitle"):
        assert forbidden not in controls
    assert controls.count('data-controls-row="') == 3


def test_player_count_script_hides_later_seats_without_reflowing(page: str) -> None:
    assert visible_seats_by_count() == {"2": [1, 2], "3": [1, 2, 3], "4": [1, 2, 3, 4]}
    assert 'var VISIBLE = {"2":[1,2],"3":[1,2,3],"4":[1,2,3,4]};' in page
    assert f"var DEFAULT_COUNT = {DEFAULT_PLAYER_COUNT};" in page
    assert "board.style.visibility" in page
    assert "disc.style.visibility" in page
    assert "display: none" not in page


def test_setup_roll_script_uses_game_setup_mapping(page: str) -> None:
    mapping = json.dumps(
        {str(roll): label for roll, label in START_HEX_BY_ROLL.items()},
        separators=(",", ":"),
    )
    edge_path = json.dumps(list(EDGE_HEX_PATH), separators=(",", ":"))

    assert '"startHexByRoll":' + mapping in page
    assert '"defaultRoll":1' in page
    assert "function rotatedPath(roll)" in page
    assert "setupGroups" in page
    assert "placeOnHex(group, state.path[slot - 1]);" in page
    assert "shipMarker" in page
    assert "data-setup-roll-button" in page
    assert '"edgePath":' + edge_path in page


def test_the_ship_button_walks_the_path_the_setup_rolls_rotate(page: str) -> None:
    """S+ takes one stop clockwise and wraps, as the setup page's Advance ship does.

    It rides `state.path`, so it follows whichever rotation the last setup roll produced, and a
    roll puts it back on the first stop -- which is the reset the setup page has a button for.
    """
    assert "function advanceShip()" in page
    assert "state.shipPosition = (state.shipPosition + 1) % state.path.length;" in page
    assert "shipButton.addEventListener('click', advanceShip);" in page
    assert "state.shipPosition = 0;" in page
    assert "placeOnHex(shipMarker, state.path[state.shipPosition]);" in page
    # no reset button was asked for, so none was added
    assert "reset-ship" not in page
    assert "Reset ship" not in page


def test_alms_and_piety_scripts_clamp_movement_deterministically(page: str) -> None:
    assert "function moveDisc(track, delta)" in page
    assert "Math.max(0, Math.min(maximum" in page
    assert "function nextAlmsPosition(current, delta, seat)" in page
    assert "almsFirstOccupied(seat)" in page
    assert "if (step === maximum && !almsFirstOccupied(seat))" in page
    assert "return DISC.first.alms;" in page
    assert "renderDiscTrack('alms')" in page
    assert "renderDiscTrack('piety')" in page
    assert "data-disc-track" in page
    assert '"max":{"alms":' in page
    assert '"piety":12' in page
    assert f'"first":{{"alms":"{RANK_FIRST}"}}' in page


def test_a_disc_in_the_first_pocket_is_drawn_on_top_of_it(page: str) -> None:
    """The pocket is painted solid, so the discs have to be drawn after it, not inside a step.

    A disc parented to its step group renders under the pocket, which is why one moved there
    vanished rather than filling the dashed socket. The renderer's interactive form lifts every
    disc into one layer above the pocket, and that is what this page asks for.
    """
    alms = _block(page, "panel p-alms")

    assert 'data-alms-bonus-pocket="true"' in alms
    assert 'data-alms-discs="true"' in alms
    assert alms.index('data-alms-bonus-pocket="true"') < alms.index('data-alms-discs="true"')
    # every disc is in that one layer, so none is left parented to a step
    layer = alms[alms.index('data-alms-discs="true"') :]
    assert len(re.findall(r'data-player-disc="\d"', layer)) == len(SEATED_PLAYERS)
    assert len(re.findall(r'data-player-disc="\d"', alms)) == len(SEATED_PLAYERS)


def test_alms_and_piety_discs_share_the_seat_order_the_boards_use(page: str) -> None:
    """Red/yellow/blue/white on both boards, stamped with the same seat numbers as the row."""
    alms = _block(page, "panel p-alms")
    piety = _block(page, "panel p-piety")

    def discs(fragment: str) -> list[tuple[str, str, str]]:
        return re.findall(
            r'data-player-disc="(\d)" data-player-seat="(\d)" data-player="(\w+)"'
            r' data-player-color="(\w+)"',
            fragment,
        )

    expected = {
        ("1", "1", "player_two", "red"),
        ("2", "2", "player_three", "yellow"),
        ("3", "3", "player_four", "blue"),
        ("4", "4", "player_one", "white"),
    }
    assert set(discs(alms)) == expected
    assert set(discs(piety)) == expected


def test_two_player_mode_centres_the_red_over_yellow_stack(page: str) -> None:
    """2P keeps red over yellow but centres both columns on the value."""
    alms_players = {
        player["color"]: (player["seat"]["column"], player["seat"]["row"])
        for player in load_alms_table_layout()["players"]
    }
    piety_seats = {
        player_by_id(load_player_boards_v2_layout(), seat["player"])["color"]: (
            seat["column"],
            seat["row"],
        )
        for seat in variant_by_id(load_piety_track_v2_layout(), PIETY_VARIANT_ID)["seats"]
    }

    assert alms_players["red"] == (-1, -1)
    assert alms_players["yellow"] == (-1, 1)
    assert alms_players["blue"] == (1, -1)
    assert alms_players["white"] == (1, 1)
    assert piety_seats == alms_players

    assert '"pair":{"alms":' in page
    assert '"piety":' in page
    assert "pairPoint(track, position)" in page
    assert "if (state.count === 2 && (seat === 1 || seat === 2))" in page
    assert "y = seat === 1 ? pair[1] : pair[2];" in page


def test_the_duty_wheel_is_not_wired_to_the_player_count_buttons(page: str) -> None:
    """Buttons may sit near the wheel, but they must not drive its tallies yet."""
    action = _block(page, "panel p-action")

    assert "data-player-count-button" not in action
    assert "duty-wheel-controls" not in page
    assert "deferred to a later PR" in page


# ---------------------------------------------------------------------------------------------
# One shared scale
# ---------------------------------------------------------------------------------------------


def test_every_panel_is_sized_from_the_one_cube(page: str) -> None:
    """No panel carries a width of its own: each is the shared cube times its own constant."""
    assert "--cube: min(" in page
    assert f"--gap: {GAP_PX}px;" in page
    for variable in ("--w-map", "--w-piety", "--w-player"):
        assert f"{variable}:" in page
        assert "var(--cube)" in page[page.index(f"{variable}:") :][:200], variable
    # the alms table hangs off the piety track rather than off the cube directly, which is what
    # locks their two discs to the same size
    assert "--w-alms:   calc(var(--w-piety) *" in page
    for panel, width in (
        ("p-map", "--w-map"),
        ("p-player", "--w-player"),
        ("p-piety", "--w-piety"),
        ("p-alms", "--w-alms"),
    ):
        rule = rf"\.{panel}\s*> svg \{{ width: var\({width}\); \}}"
        assert re.search(rule, page), panel


def test_the_duty_wheel_is_the_one_panel_sized_by_height(page: str) -> None:
    """It fills what the row has left, so the gap above it is the gap used everywhere else.

    Sizing it by height rather than by a scale factor is what keeps that true at any window size,
    rather than only at the one the constants were solved against.
    """
    assert "--row-height: calc(" in page
    assert "--h-action: calc(" in page
    assert "var(--row-height) - var(--cube)" in page
    assert "- var(--gap)" in page
    assert ".p-action > svg { height: var(--h-action); width: auto; }" in page


def test_the_alms_table_and_the_piety_track_share_a_scale(scale) -> None:
    """Both draw the same player disc, so matching their units-per-pixel matches the discs.

    This is what `--w-alms` being a multiple of `--w-piety` buys. It is also why the alms table is
    not simply handed the seats' width: the width it wants is bought in its own units instead.
    """
    content, _, cubes, solved = scale

    assert cubes["alms"] == pytest.approx(cubes["piety"])
    # same units per pixel, so the width ratio is just the ratio of the crops
    assert solved.alms_over_piety == pytest.approx(solved.crop["alms"][2] / solved.crop["piety"][2])
    assert content["alms"][2] < content["piety"][2]

    disc = ALMS_LAYOUT["disc"]["radius"]
    piety_disc = load_piety_track_v2_layout()["track"]["disc"]["radius"]
    assert 2 * disc * _per_unit(solved, "alms") == pytest.approx(
        2 * piety_disc * _per_unit(solved, "piety")
    )

    # The discs match because a unit is a unit on both boards, not because the two were sized to
    # agree. That is also what lets the piety track set its numbers, its rules, its title and its
    # stars from the Alms Table's own constants and have them come out the same size here.
    assert _per_unit(solved, "alms") == pytest.approx(_per_unit(solved, "piety"))
    # And both are cropped to the same height above their panel, so with the row's tops level the
    # same y on the two boards is the same y on the table. The piety track's stars are placed on
    # the Alms Table's second key row that way.
    assert solved.crop["alms"][1] == pytest.approx(solved.crop["piety"][1])


def test_a_pilgrimage_sites_star_reads_at_the_size_of_a_piety_track_star(scale) -> None:
    """The site renderer's star size is written for this page, so this is what checks it.

    The site tile is drawn into a map hex, so its star crosses two scales to get here -- the tile's
    own units into the map's, and the map's into the table's -- and neither is the piety track's.
    `STAR_OUTER_RADIUS` in the site renderer is that round trip solved for; if a board's scale ever
    moves, this is the test that says so and the figure to re-measure.
    """
    _, _, _, solved = scale
    tile_into_map = load_map_layout()["hex_size"] / TILE_HEX_RADIUS

    site_star = SITE_STAR_RADIUS * tile_into_map * _per_unit(solved, "map")
    track_star = TRACK_STAR_RADIUS * _per_unit(solved, "piety")
    site_vp = SITE_VP_FONT_SIZE * tile_into_map * _per_unit(solved, "map")
    track_vp = TRACK_STAR_FONT_SIZE * _per_unit(solved, "piety")

    assert site_star == pytest.approx(track_star, rel=1e-4)
    assert site_vp == pytest.approx(track_vp, rel=1e-4)


def test_a_seats_pieces_carry_over_to_the_alms_table_at_the_size_they_are_written(scale) -> None:
    """What `UNITS_PER_PLAYER_UNIT` buys: sizes written in a seat's units come out a seat's size.

    The alms table is drawn at the piety track's scale rather than the seats', so a unit of it is
    not a unit of a player board. That ratio is written down in the alms renderer so the board can
    size a cube or a label in a seat's units and get a seat's pixels back, and this is where the
    number is checked against the solve rather than trusted. It moved when the seats stopped being
    stretched to the duty wheel's height, because that changed the scale a seat is drawn at.

    The solve is for one reference viewport. Both panels carry fixed chrome that does not scale
    with the cube, so the two drift a little either side of it at other window sizes.
    """
    _, _, _, solved = scale
    alms, player = _per_unit(solved, "alms"), _per_unit(solved, "player")

    assert alms / player == pytest.approx(UNITS_PER_PLAYER_UNIT, rel=1e-3)
    assert ALMS_CUBE_SIZE * alms == pytest.approx(2 * TOKEN_RADIUS * player, rel=1e-3)
    assert SEASON_END_LABEL_FONT_SIZE * alms == pytest.approx(ROLE_FONT_SIZE * player, rel=1e-3)


def test_the_alms_table_now_overhangs_the_seats_it_stands_above(scale) -> None:
    """A width the seats no longer share, recorded rather than asserted away.

    The alms table is 536 of its own units across because at the ratio that held when that was
    chosen, 536 came out a seat's width exactly. Sizing a seat from the duty wheel's cube instead
    of stretching it to the wheel's height made the seats narrower, and this board did not follow:
    it is pinned to the piety track, which is what keeps the two boards' player discs the same
    size. Closing the gap means re-fitting this board's own width, which is a change to its layout
    rather than to the table, so for now it stands about a seventh proud of the boards below it.
    """
    _, _, _, solved = scale
    alms, player = _per_unit(solved, "alms"), _per_unit(solved, "player")
    seat = board_geometry(len(load_player_boards_v2_layout()["worker_roles"]))

    overhang = ALMS_LAYOUT["board"]["panel_width"] * alms / (seat["panel_width"] * player)

    assert overhang == pytest.approx(1.145, abs=0.01)
    # The width it would have to be drawn in to sit flush again.
    assert seat["panel_width"] * player / alms == pytest.approx(465.9, abs=0.5)


def test_a_players_cube_is_the_same_cube_in_a_village_and_on_a_duty_tile(scale) -> None:
    """The one size the whole table is judged on, seen on all three boards that draw it.

    The seats used to be stretched to the duty wheel's height, which made a seat's scale a
    consequence of the board's shape: it came within two percent of the wheel's only because the
    board happened to be the height it was, and shortening it took that to twenty. A seat is sized
    from the wheel's own rendered cube now, so the match is exact and holds whatever shape the
    board is drawn in -- which is what let the board be shortened at all.
    """
    _, _, _, solved = scale
    wheel_unit = _per_unit(solved, "action") * load_duty_wheel_layout()["board"]["scale"]

    duty_cube = DUTY_CUBE_SIZE * wheel_unit
    village_cube = 2 * TOKEN_RADIUS * _per_unit(solved, "player")
    won_cube = ALMS_CUBE_SIZE * _per_unit(solved, "alms")

    assert 2 * TOKEN_RADIUS == DUTY_CUBE_SIZE
    assert village_cube == pytest.approx(duty_cube, rel=1e-6)
    # The alms table takes its cube from a seat, so it comes along at the same size.
    assert won_cube == pytest.approx(duty_cube, rel=1e-3)
    assert won_cube == pytest.approx(village_cube, rel=1e-3)
    # And the unit the board writes its geometry in is not a cube, which is the thing that made
    # the seats read a tenth too big before they were given one.
    assert MARKER_CUBE > DUTY_CUBE_SIZE
    assert MARKER_CUBE * _per_unit(solved, "player") > duty_cube * 1.07


def test_the_duty_wheel_and_the_map_are_anchored_on_the_same_hexagon(scale) -> None:
    """Neither board draws a cube, so the shared board hexagon is what sizes them.

    The map's cube is derived so that at one cube size the two hexagons come out the same width.
    """
    _, hexes, cubes, solved = scale

    assert cubes["map"] / cubes["action"] == pytest.approx(hexes["map"][2] / hexes["action"][2])
    assert solved.mult["action"] == pytest.approx(solved.mult["map"], abs=0.5)


def test_a_building_slot_is_the_map_hex_measured_in_the_unit_the_board_writes_in(scale) -> None:
    """Where the player board's slot size comes from, checked against the map it was taken from.

    `BUILDING_SLOT_HEX_SIZE` was solved as a number of MARKER_CUBEs, the unit the board writes its
    geometry in -- which was the board's cube when the figure was chosen, and has not been one
    since the cubes were resized to the duty wheel's. So this is the arithmetic behind the constant
    rather than a claim about what renders; the next test is what renders.
    """
    _, _, cubes, _ = scale
    hex_in_cubes = load_map_layout()["hex_size"] / cubes["map"]

    assert cubes["player"] == 2 * TOKEN_RADIUS
    assert BUILDING_SLOT_HEX_SIZE / MARKER_CUBE == pytest.approx(hex_in_cubes, rel=0.002)


def test_a_building_slot_does_not_yet_render_the_size_of_a_map_hex(scale) -> None:
    """The gap that constant leaves, recorded rather than asserted away.

    A slot and a map hex are both flat-top hexagons measured from the centre out to a corner, so
    the two are the same size on screen exactly when they are the same number of CUBES across --
    and a slot is that many MARKER_CUBEs across, which is a larger unit. It has therefore always
    rendered short of a map hex; sizing the seats from the wheel's cube widened the gap, because
    it moved the scale a seat is drawn at without moving the map's.

    Closing it means drawing the slots bigger, which sets the board's column pitch and so its
    width. That is a change to the player board rather than to the table, and is left alone here.
    """
    _, _, _, solved = scale
    slot = BUILDING_SLOT_HEX_SIZE * _per_unit(solved, "player")
    map_hex = load_map_layout()["hex_size"] * _per_unit(solved, "map")

    assert slot / map_hex == pytest.approx(0.798, abs=0.01)
    # What the board would have to draw a slot at for the two to meet.
    assert map_hex / _per_unit(solved, "player") == pytest.approx(61.9, abs=0.5)


def test_the_seats_are_wider_than_they_are_tall(scale) -> None:
    """The seats got wider, and the table gave them the room rather than shrinking them to fit.

    A seat's width is solved from its shape, so a wider board is a wider seat -- there is no
    separate width for the table to have opinions about. The table may come out wider for it.
    """
    _, _, _, solved = scale
    crop = solved.crop["player"]

    assert crop[2] > crop[3]
    assert solved.seats_cubes > 0
    assert solved.seats_cubes == pytest.approx(SEAT_COLS * solved.player_k)


def test_the_two_rows_each_ask_for_the_width_and_stack_for_the_height(scale) -> None:
    """The shape the page solves against, now that the seats are a row rather than a column.

    Neither row is inside the other any more, so neither one's width bounds the other's; what they
    do share is the window's height, which they take one after the other. That is the whole of
    what moved: the seats left the left column and became the second row of the stack.
    """
    _, _, _, solved = scale

    assert solved.seats_cubes == pytest.approx(SEAT_COLS * solved.player_k)
    assert solved.seats_fixed == SEAT_COLS * PANEL_CHROME + (SEAT_COLS - 1) * GAP_PX
    assert solved.width_fixed == 3 * PANEL_CHROME + 2 * GAP_PX, "three panels across, two gaps"

    aspect = solved.crop["player"][3] / solved.crop["player"][2]
    seat_height = solved.cube * solved.player_k * aspect
    assert solved.stack_cubes * solved.cube + solved.stack_fixed == pytest.approx(
        _row_height(solved) + GAP_PX + seat_height + PANEL_CHROME + BODY_CHROME
    )
    # The map is what the main row stands to; the alms table alone no longer reaches it.
    assert solved.row_cubes == pytest.approx(solved.map_cubes)


def test_the_window_height_is_what_the_table_is_solved_against(scale) -> None:
    """Two rows in the same window is what sets the cube now, where three panels across used to.

    Nothing is scaled to fit: there is one cube and every panel is a fixed multiple of it, so the
    seats joining the stack shows up as a smaller cube for everything rather than as a board drawn
    at a size of its own. It only binds on a short window -- give the page the height the two rows
    want and the width takes over again, at a larger cube than the two-seat table ever reached.
    """
    _, _, _, solved = scale

    height_bound = (REF_VIEWPORT_HEIGHT - solved.stack_fixed) / solved.stack_cubes
    width_bound = min(
        (REF_AVAIL_WIDTH - solved.width_fixed) / solved.width_cubes,
        (REF_AVAIL_WIDTH - solved.seats_fixed) / solved.seats_cubes,
    )

    assert solved.cube == pytest.approx(height_bound)
    assert height_bound < width_bound
    # Roughly what the window would have to give the stack for the width to bind instead -- read
    # off these coefficients, which are themselves solved at the reference height, so it is the
    # size of the answer rather than the answer. Solving at that height puts it at 1142.
    assert width_bound * solved.stack_cubes + solved.stack_fixed == pytest.approx(1142, abs=10)
    # And the cube it settles at there, which is a fifth larger than the two-seat table reached.
    assert width_bound == pytest.approx(10.5, abs=0.2)


def test_the_solve_settles(scale) -> None:
    """The margins, the crops and the cube are solved together, so it has to reach a fixed point.

    Re-running it from the answer has to give the answer back, or the numbers baked into the page
    depend on how many passes it happened to take.
    """
    content, hexes, cubes, solved = scale
    again = solve_table_scale(content, hexes, cubes)

    assert again.cube == pytest.approx(solved.cube)
    assert again.crop == solved.crop
    assert again.margin_px == pytest.approx(solved.margin_px)


def test_every_board_gets_the_same_margin_on_screen(scale) -> None:
    """Each board is cropped to its own content plus a margin in its own units, and those units
    differ, so the margins are solved to land on the same number of pixels."""
    _, _, _, solved = scale

    assert solved.margin_px > 0
    for key in ("alms", "piety", "action", "map", "player"):
        crop = solved.crop[key]
        assert crop[2] > 0 and crop[3] > 0, key


# ---------------------------------------------------------------------------------------------
# Cropping, which is the only thing done to a rendered fragment
# ---------------------------------------------------------------------------------------------


def test_each_fragment_is_cropped_to_its_own_panel(page: str) -> None:
    """Every renderer draws page furniture around its board for its own standalone page.

    The table points each viewBox at the board instead. Nothing is removed, so the count of SVGs
    and what they contain is unchanged; only the window onto them moves.
    """
    roots = re.findall(r"<svg\b[^>]*>", page)

    # the alms table, the piety track, the duty wheel and the map, plus one board per seat
    assert len(roots) == 4 + len(SEATED_PLAYERS)
    for root in roots:
        assert "viewBox=" in root
        assert not re.search(r'\s(?:width|height)="', root), "the page's own rule sets the size"


def test_crop_svg_moves_the_window_without_touching_the_drawing() -> None:
    fragment = '<svg xmlns="x" viewBox="0 0 10 10" width="10" height="10"><rect width="4"/></svg>'

    cropped = crop_svg(fragment, (-1, -2, 12.5, 13))

    assert cropped == '<svg xmlns="x" viewBox="-1 -2 12.5 13"><rect width="4"/></svg>'


def test_the_duty_wheel_hexagon_is_replaced_with_a_regular_one() -> None:
    """The wheel's was drawn about 2.5% taller than regular, so at equal widths it and the map do
    not read as the same board. The swap changes only how far the empty points reach.

    This is the one place the table touches what a renderer drew. It guards itself: if the wheel
    stops drawing the path measured here, generating fails rather than cropping to the wrong box.
    """
    layout = load_duty_wheel_layout()
    hexagon = duty_hexagon(layout)

    assert hexagon["drawn"] == layout["board"]["ground_path"]
    assert hexagon["drawn"] != hexagon["regular"]
    with pytest.raises(ValueError):
        regularise_duty_hexagon("<svg><path d='something else'/></svg>", hexagon)
    assert hexagon["regular"] in regularise_duty_hexagon(
        f'<svg><path d="{hexagon["drawn"]}"/></svg>', hexagon
    )


def test_a_regular_hexagon_is_two_over_root_three_as_tall_as_it_is_wide() -> None:
    path, half_height = regular_hexagon_path(0.0, 0.0, 100.0)

    assert half_height == pytest.approx(200.0 / math.sqrt(3.0))
    assert path.startswith("M 0.00,-115.47")
    assert path.endswith("Z")


def test_the_two_hexagons_keep_their_own_widths(scale) -> None:
    """Matched on width, which is what the eye compares side by side. The map's is regular and
    the wheel's is made regular, so at equal widths they are the same shape."""
    _, hexes, _, _ = scale

    assert hexes["map"][2] > 0 and hexes["action"][2] > 0
    map_aspect = hexes["map"][3] / hexes["map"][2]
    duty_aspect = hexes["action"][3] / hexes["action"][2]
    assert map_aspect == pytest.approx(duty_aspect, rel=1e-3)


# ---------------------------------------------------------------------------------------------
# What this page is not
# ---------------------------------------------------------------------------------------------


def test_page_carries_only_local_compact_controls(page: str) -> None:
    """Controls stay local to this page; richer setup controls remain in game_setup.html."""
    # counts, setup rolls, the ship, the four disc steps, and Move acolyte
    compact_buttons = len(PLAYER_COUNTS) + len(SETUP_ROLLS) + 1 + 4 + 1
    assert page.count("<button") == compact_buttons
    assert page.count("<script") == 1
    assert "data-player-count-button" in page
    assert "data-setup-roll-button" in page
    assert "data-disc-track" in page
    assert "move-acolyte" in page
    assert render_duty_wheel_controls_html(load_duty_wheel_layout()) not in page
    assert render_alms_table_controls_html(load_alms_table_layout(), load_alms_config()) not in page


def test_the_old_two_column_layout_is_gone(page: str) -> None:
    """The page was a two-column grid before, and none of that should still be described."""
    for stale in (
        "game-table-left-main",
        "game-table-duty-wheel",
        "game-table-player-boards",
        "game-table-piety-panel",
        "game-table-map-panel",
        "game-table-alms-panel",
        "--game-table-board-grid-width",
        "--game-table-duty-wheel-width",
        "--game-table-alms-width",
        "--game-table-left-col",
        "--game-table-right-col",
    ):
        assert stale not in page, stale
    assert "grid-column:" not in page and "grid-row:" not in page


def test_page_does_not_use_iframes(page: str) -> None:
    assert "<iframe" not in page


def test_page_wraps_the_row_on_narrow_screens(page: str) -> None:
    media = re.search(r"@media \(max-width: (\d+)px\)", page)

    assert media is not None
    assert "flex-wrap: wrap;" in page


def test_index_links_the_generated_page() -> None:
    content = INDEX_HTML.read_text(encoding="utf-8")

    assert "generated/game_table.html" in content
    assert "Generated game table layout" in content
    assert "generated/game_setup.html" in content
    assert "generated/debug_overview.html" in content
