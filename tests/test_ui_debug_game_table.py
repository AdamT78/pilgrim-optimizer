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

from tools.ui_debug.generate_game_setup import (
    DEFAULT_START_ROLL,
    EDGE_HEX_PATH,
    START_HEX_BY_ROLL,
    acolyte_places,
    available_setup_buildings,
    donated_vp_by_level,
    setup_placements,
)
from tools.ui_debug.generate_game_table import (
    DEFAULT_CONTROL_PLAYER_SEAT,
    DEFAULT_PLAYER_COUNT,
    FIRST_PLAYER_SEAT_AT_START,
    PAGE_TITLE,
    PLAYER_COUNTS,
    RESOURCE_ABBREVIATIONS,
    RESOURCE_FLOOR,
    SETUP_CITY_CUBES,
    SETUP_ROLLS,
    building_control_data,
    default_output_path,
    duty_control_data,
    duty_wheel_seating,
    generate_game_table_page,
    render_turn_flow_script,
    resource_control_data,
    seat_numbers_by_player,
    visible_seats_by_count,
)
from tools.ui_debug.render_alms_table import (
    CUBE_SIZE as ALMS_CUBE_SIZE,
)
from tools.ui_debug.render_alms_table import (
    RANK_FIRST,
    SEASON_END_LABEL_FONT_SIZE,
    UNITS_PER_PLAYER_UNIT,
    alms_rules,
    load_alms_config,
    load_alms_table_layout,
    placeholder_slots,
    render_alms_table_controls_html,
)
from tools.ui_debug.render_alms_table import STAR_LABEL_FONT_SIZE as TRACK_STAR_FONT_SIZE
from tools.ui_debug.render_alms_table import STAR_OUTER_RADIUS as TRACK_STAR_RADIUS
from tools.ui_debug.render_buildings import HEX_RADIUS as TILE_HEX_RADIUS
from tools.ui_debug.render_buildings import load_building_catalog
from tools.ui_debug.render_donated_buildings import HEX_RADIUS as DONATED_HEX_RADIUS
from tools.ui_debug.render_donated_buildings import (
    STAR_OUTER_RADIUS as DONATED_STAR_RADIUS,
)
from tools.ui_debug.render_donated_buildings import (
    VP_TEXT_FONT_SIZE as DONATED_VP_FONT_SIZE,
)
from tools.ui_debug.render_donated_buildings import load_donated_building_tiles
from tools.ui_debug.render_duty_wheel import (
    CITY_STACK_HEIGHT,
    CORNUCOPIA_TOKEN,
    board_edges,
    board_positions,
    duty_position_by_id,
    duty_setups,
    load_duty_wheel_layout,
    merchant_path,
    render_duty_wheel_controls_html,
    tally_pieces,
)
from tools.ui_debug.render_duty_wheel import (
    CUBE_SIZE as DUTY_CUBE_SIZE,
)
from tools.ui_debug.render_map import load_map_layout, render_map_svg
from tools.ui_debug.render_piety_track_v2 import load_piety_track_v2_layout, variant_by_id
from tools.ui_debug.render_pilgrimage_sites import STAR_OUTER_RADIUS as SITE_STAR_RADIUS
from tools.ui_debug.render_pilgrimage_sites import VP_TEXT_FONT_SIZE as SITE_VP_FONT_SIZE
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites
from tools.ui_debug.render_player_boards_v2 import (
    BUILDING_SLOT_HEX_SIZE,
    MARKER_CUBE,
    ROLE_FONT_SIZE,
    TOKEN_RADIUS,
    _darker_surface_colour,
    board_geometry,
    load_player_boards_v2_layout,
    player_by_id,
    players_of,
)
from tools.ui_debug.render_table_layout import (
    BODY_CHROME,
    GAP_PX,
    PANEL_CHROME,
    PIETY_VARIANT_ID,
    REF_AVAIL_WIDTH,
    REF_VIEWPORT_HEIGHT,
    SEAT_COLS,
    SEATED_PLAYERS,
    board_measurements,
    crop_svg,
    duty_hexagon,
    regular_hexagon_path,
    regularise_duty_hexagon,
    solve_table_scale,
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
def placements() -> list[dict]:
    """The setup map the page opens on, which is what the buy dropdown is drawn from."""
    return setup_placements(DEFAULT_START_ROLL, load_building_catalog(), load_pilgrimage_sites())


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


def _turn_control_plaques(markup: str) -> list[tuple[float, float, float, float]]:
    """Every plaque the wheel's turn-control shell draws, as x, y, width, height."""
    start = markup.index('<g data-component="duty-wheel-turn-controls"')
    overlay = markup[start : markup.index("</svg>", start)]
    return [
        tuple(float(value) for value in rect)
        for rect in re.findall(
            r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)" rx=', overlay
        )
    ]


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
    assert '<div class="game-table-stage"' in written.read_text(encoding="utf-8")


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
    assert body.index('<div class="game-table-stage"') < body.index("<svg")


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
    assert '<div class="game-table-stage"' in page
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
    assert ".seats {" in page
    assert "display: flex; gap: var(--gap);" in page
    assert "align-self: stretch; justify-content: center;" in page
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
    # counted in the markup: the compact rows' script names the board too, to drive it
    markup = page[: page.index("<script")]
    assert markup.count('data-component="duty-wheel"') == 1


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
        ("1", "player_one", "red"),
        ("2", "player_two", "yellow"),
        ("3", "player_three", "blue"),
        ("4", "player_four", "white"),
    ]
    assert seat_numbers_by_player() == {
        "player_one": 1,
        "player_two": 2,
        "player_three": 3,
        "player_four": 4,
    }


def test_no_board_at_this_table_says_who_starts(page: str) -> None:
    """The first-player card is gone from the board, and so is the seat that used to carry it.

    The card was layout state to look at, with no control to move it, and the corner it sat in is
    the resources' now. The marker itself has since arrived on the Piety Track, which is where the
    thing that decides it is drawn -- so this is about the boards, not about the whole page, and it
    is checked on the seats rather than by looking for the words anywhere at all.
    """
    seats = _block(page, "seats")

    assert "first-player" not in seats
    assert ">First player</text>" not in page
    assert re.findall(r'data-player="(\w+)" data-player-color="\w+" data-active-seat=', seats) == (
        list(SEATED_PLAYERS)
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
    # then the three that move a piece: the wheel's tiles, the ship, the Merchant
    assert 'data-duty-randomize-button="true">R</button>' in body
    assert 'data-ship-advance="true">S+</button>' in body
    assert 'data-merchant-advance-button="true">M+</button>' in body
    assert body.index(">6<") < body.index(">R<") < body.index(">S+<") < body.index(">M+<")


def test_row_one_ends_with_the_control_that_says_who_holds_the_marker(page: str) -> None:
    """A table-level thing, so it sits in the table-level row with the count and the setup roll."""
    controls = _block(page, "table-controls")
    row_one = re.search(r'data-controls-row="1">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_one is not None
    body = row_one.group(1)

    assert 'id="first-player-seat"' in body
    assert body.index(">M+<") < body.index('id="first-player-seat"')
    seats = re.findall(
        r'<option value="(\d)"( selected)?>(Red|Yellow|Blue|White)</option>',
        body,
    )
    assert [seat for seat, _, _ in seats] == ["1", "2", "3", "4"]
    # No "nobody" entry: the marker always sits with someone.
    assert len(seats) == len(SEATED_PLAYERS)
    assert [seat for seat, chosen, _ in seats if chosen] == [str(FIRST_PLAYER_SEAT_AT_START)]


def test_the_table_opens_with_the_marker_on_the_seat_that_starts_the_game(page: str) -> None:
    """Every piety disc starts on 0, so the tie resolves to the first board: seat 1, red."""
    assert FIRST_PLAYER_SEAT_AT_START == 1
    assert SEATED_PLAYERS[FIRST_PLAYER_SEAT_AT_START - 1] == "player_one"  # red
    assert f"firstPlayerSeat: {FIRST_PLAYER_SEAT_AT_START}," in page
    assert f'data-first-player-seat="{FIRST_PLAYER_SEAT_AT_START}"' in page


def test_the_track_carries_every_seat_s_seal_so_the_page_never_strikes_wax(page: str) -> None:
    """The point of the renderer's mode: the page shows and hides, it does not draw."""
    piety = _block(page, "panel p-piety")
    groups = re.findall(r"<g data-first-player-seal=[^>]*>", piety)

    assert len(groups) == len(SEATED_PLAYERS)
    assert sum('visibility="hidden"' in group for group in groups) == len(SEATED_PLAYERS) - 1
    held = next(group for group in groups if 'visibility="hidden"' not in group)
    assert f'data-player-seat="{FIRST_PLAYER_SEAT_AT_START}"' in held
    assert 'data-player-color="red"' in held


def test_a_seat_that_leaves_the_table_hands_the_marker_back_rather_than_to_nobody(
    page: str,
) -> None:
    """Mirrors what the active seat already does on a count change, and for the same reason."""
    assert (
        f"state.firstPlayerSeat > count ? {FIRST_PLAYER_SEAT_AT_START} : state.firstPlayerSeat"
        in page
    )
    assert f"setActiveSeat(state.activeSeat > count ? {DEFAULT_CONTROL_PLAYER_SEAT}" in page


def test_moving_the_marker_shows_and_hides_and_never_computes_a_colour(page: str) -> None:
    """The whole reason every seal is struck up front, held here so it cannot quietly be undone.

    A colour derived in JavaScript would be a second copy of `darken()` in a second language, to be
    kept agreeing with the first. The script may set visibility on a seal and nothing else.
    """
    script = page[page.index("<script>") :]
    seal_work = re.findall(r"^.*(?:Seal|firstPlayerSeat).*$", script, re.M)

    assert seal_work, "nothing in the script touches the marker"
    for line in seal_work:
        assert "fill" not in line
        assert "#" not in line
        assert "darken" not in line.lower()
    reveal = "seal.style.visibility = seat === state.firstPlayerSeat ? 'visible' : 'hidden';"
    assert reveal in script
    # The attribute names the holder, so it moves with the marker rather than going stale.
    assert "pietyTrack.setAttribute('data-first-player-seat', String(seat));" in script


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

    options = re.findall(
        r'<option value="(\d)"(?: selected)?>(Red|Yellow|Blue|White)</option>',
        body,
    )
    assert options == [("1", "Red"), ("2", "Yellow"), ("3", "Blue"), ("4", "White")]
    assert 'id="disc-player-seat"' in body
    assert 'data-disc-track="alms" data-disc-delta="1">A+</button>' in body
    assert 'data-disc-track="alms" data-disc-delta="-1">A-</button>' in body
    assert 'data-disc-track="piety" data-disc-delta="1">P+</button>' in body
    assert 'data-disc-track="piety" data-disc-delta="-1">P-</button>' in body


def test_row_two_steps_the_resources_after_the_discs(page: str) -> None:
    """The resource steps share the row's player dropdown, so they come after the disc steps."""
    controls = _block(page, "table-controls")
    row_two = re.search(r'data-controls-row="2">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_two is not None
    body = row_two.group(1)

    steps = re.findall(r'data-resource-button="([\w:+-]+)">([^<]+)</button>', body)
    assert steps == [
        ("wheat:+", "Wh+"),
        ("wheat:-", "Wh-"),
        ("stone:+", "St+"),
        ("stone:-", "St-"),
        ("silver:+", "Si+"),
        ("silver:-", "Si-"),
    ]
    assert body.index(">P-<") < body.index(">Wh+<")


def test_the_resource_steps_name_the_resources_the_board_draws(page: str) -> None:
    """A step button and the readout it moves are the same resource, named the same way."""
    resources = [resource["id"] for resource in load_player_boards_v2_layout()["resources"]]
    seats = _block(page, "seats")

    assert resources == ["wheat", "stone", "silver"]
    assert set(RESOURCE_ABBREVIATIONS) == set(resources)
    for resource in resources:
        assert seats.count(f'data-player-resource="{resource}"') == len(SEATED_PLAYERS)


def test_row_three_carries_the_season_end_winner_controls(page: str) -> None:
    controls = _block(page, "table-controls")
    row_three = re.search(r'data-controls-row="3">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_three is not None
    body = row_three.group(1)

    options = re.findall(
        r'<option value="(\d)"(?: selected)?>(Red|Yellow|Blue|White)</option>',
        body,
    )
    assert options == [("1", "Red"), ("2", "Yellow"), ("3", "Blue"), ("4", "White")]
    assert 'id="alms-winner-player-seat" data-alms-winner-player-select="true"' in body
    assert 'data-alms-winner-button="add">AT+</button>' in body
    assert 'data-alms-winner-button="reset">ATr</button>' in body
    assert body.index(">AT+<") < body.index(">ATr<")


def test_row_three_also_buys_and_donates_buildings(page: str) -> None:
    """Buy and Donate share the row's player dropdown, so they follow the winner buttons."""
    controls = _block(page, "table-controls")
    row_three = re.search(r'data-controls-row="3">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_three is not None
    body = row_three.group(1)

    assert 'id="buy-building" data-building-buy-select="true"' in body
    assert 'data-building-buy-button="true">Buy</button>' in body
    assert 'id="donate-building-slot" data-building-donate-slot-select="true"' in body
    assert 'data-building-donate-button="true">Donate</button>' in body
    assert body.index(">ATr<") < body.index("buy-building") < body.index(">Buy<")
    assert body.index(">Buy<") < body.index("donate-building-slot") < body.index(">Donate<")


def test_the_building_dropdown_offers_what_is_standing_on_the_setup_map(
    page: str, placements: list[dict]
) -> None:
    controls = _block(page, "table-controls")
    select = re.search(r'id="buy-building".*?>(.*?)</select>', controls, flags=re.DOTALL)
    assert select is not None

    buildings = available_setup_buildings(placements)
    offered = re.findall(r'<option value="(\d+)"(?: selected)?>([^<]+)</option>', select.group(1))

    assert offered == [(str(item["setupSlot"]), item["label"]) for item in buildings]
    # keyed by the setup slot, not the hex, so a roll moves a building without renaming it
    assert all(label.endswith(")") for _, label in offered)


def test_the_donate_dropdown_numbers_the_slots_the_board_has(page: str) -> None:
    controls = _block(page, "table-controls")
    select = re.search(r'id="donate-building-slot".*?>(.*?)</select>', controls, flags=re.DOTALL)
    assert select is not None

    count = int(load_player_boards_v2_layout()["building_slot_count"])
    numbered = re.findall(r'<option value="(\d)"(?: selected)?>(\d)</option>', select.group(1))

    assert count == 6
    assert numbered == [(str(number), str(number)) for number in range(1, count + 1)]


def test_row_four_has_acolyte_controls_with_game_setup_places(page: str) -> None:
    controls = _block(page, "table-controls")
    row_four = re.search(r'data-controls-row="4">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_four is not None
    body = row_four.group(1)

    assert 'id="acolyte-player-seat"' in body
    assert 'id="acolyte-source"' in body
    assert 'id="acolyte-target"' in body
    assert 'id="move-acolyte">Move acolyte</button>' in body

    places = acolyte_places(load_player_boards_v2_layout())
    for place_id, label in places:
        expected = f'<option value="{place_id}"'
        assert expected in body
        assert f">{label}</option>" in body


def test_the_cube_moves_share_the_player_the_row_already_names(page: str) -> None:
    """One button each rather than the setup page's four: the row already says whose board it is.

    They read left to right in the order a cube travels -- around the board, then off it -- and all
    four take the seat from the one dropdown the row opens with.
    """
    controls = _block(page, "table-controls")
    row_four = re.search(r'data-controls-row="4">(.+?)</div>', controls, flags=re.DOTALL)
    assert row_four is not None
    body = row_four.group(1)
    moves = [
        "data-serf-to-abbey-button",
        "data-abbey-to-city-button",
        "data-village-to-city-button",
    ]

    assert '<button type="button" data-serf-to-abbey-button="true">S-&gt;A</button>' in body
    assert '<button type="button" data-abbey-to-city-button="true">A-&gt;C</button>' in body
    assert '<button type="button" data-village-to-city-button="true">V-&gt;C</button>' in body
    assert all(body.count(move) == 1 for move in moves)
    places = [body.index('id="acolyte-player-seat"'), body.index('id="move-acolyte"')]
    assert places + [body.index(move) for move in moves] == sorted(
        places + [body.index(move) for move in moves]
    )


def test_controls_stay_compact_without_explanatory_text(page: str) -> None:
    controls = _block(page, "table-controls")

    for forbidden in ("<label", "<p ", "<h1", "<h2", "<h3", "slot-list", "subtitle"):
        assert forbidden not in controls
    assert controls.count('data-controls-row="') == 4


def test_player_count_script_hides_later_seats_by_taking_them_out_of_flow(page: str) -> None:
    assert visible_seats_by_count() == {"2": [1, 2], "3": [1, 2, 3], "4": [1, 2, 3, 4]}
    assert 'var VISIBLE = {"2":[1,2],"3":[1,2,3],"4":[1,2,3,4]};' in page
    assert f"var DEFAULT_COUNT = {DEFAULT_PLAYER_COUNT};" in page
    assert "board.style.display" in page
    assert "disc.style.visibility" in page


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


def test_the_resource_script_starts_from_the_amounts_the_board_is_drawn_holding(page: str) -> None:
    """Every seat opens on the board's own amounts, so the page reads the same before a click."""
    board_layout = load_player_boards_v2_layout()
    data = resource_control_data(board_layout)

    assert data["ids"] == ["wheat", "stone", "silver"]
    assert data["state"] == {
        str(seat): {"wheat": 1, "stone": 1, "silver": 1}
        for seat in range(1, len(SEATED_PLAYERS) + 1)
    }
    assert "var RESOURCES = " + json.dumps(data, separators=(",", ":")) + ";" in page


def test_a_resource_stops_at_nothing_and_only_moves_the_seat_it_is_given(page: str) -> None:
    """Every stock moves through one place, and that place is told whose stock it is.

    Row two's steppers act on row two's dropdown; a tithe pays whoever's turn it is. Those are two
    different seats most of the time, so the seat is an argument rather than something read out of
    the page from inside -- reading the dropdown for a tithe would pay the wrong player in silence.
    """
    assert RESOURCE_FLOOR == 0
    assert "function creditResource(seat, id, delta)" in page
    assert "var amounts = state.resources[String(seat)];" in page
    assert "amounts[id] = Math.max(RESOURCES.floor, amounts[id] + delta);" in page
    assert "function stepResource(id, delta)" in page
    assert "creditResource(discPlayerSeat.value, id, delta);" in page
    assert "board.querySelector('[data-player-resource=\"' + id + '\"]')" in page
    assert "readout.textContent = String(amounts[id]);" in page
    # Nothing else may read the debug dropdown to decide who is paid.
    assert page.count("discPlayerSeat.value") == 2  # the stepper, and moveDisc's own seat


def test_a_tithe_pays_the_seat_whose_turn_it_is(page: str) -> None:
    """Not the debug dropdown, which is the seat the resource steppers act on and nothing else."""
    assert "function takeTithe()" in page
    assert "payTithe(state.activeSeat, token);" in page
    assert "if (resolution === 'tithe') {\n      takeTithe();\n    }" in page


def test_the_token_is_read_off_the_tile_lying_at_the_position_not_the_position(page: str) -> None:
    """A turn moves by board position; an arrangement is written against the slots tiles lie in.

    The space carries both names, so it is where one is turned into the other. A second table
    pairing them up would be a thing to keep in step by hand every time the wheel is re-laid.
    """
    assert "function titheTokenAt(position)" in page
    assert "var space = spaceAt(position);" in page
    assert "var slot = space ? space.getAttribute('data-duty') : null;" in page
    assert "if (entry.position === slot) {" in page
    assert "token = entry.tithe_icon;" in page


def test_the_tile_that_brings_no_token_offers_nothing_to_take(page: str) -> None:
    """Taxation. The plaque goes dark, and pressing it anyway is not a move."""
    assert "if (resolution === 'tithe' && !titheTokenAt(state.turn.duty)) {" in page
    assert "if (chosen && !titheTokenAt(state.turn.duty)) {\n          chosen = false;" in page
    landed = {
        entry["position"]: entry["tithe_icon"]
        for entry in duty_setups(load_duty_wheel_layout())[0]
    }
    assert landed["taxation"] is None
    assert [slot for slot, token in landed.items() if token is None] == ["taxation"]


def test_the_cornucopia_asks_the_seat_instead_of_paying_it(page: str) -> None:
    assert f"var CORNUCOPIA = '{CORNUCOPIA_TOKEN}';" in page
    assert "if (token === CORNUCOPIA) {\n      openTitheChoice();" in page
    assert "state.turn.titheChoice = 'pending';" in page
    # The payment is the key press, which is why a Reset before one costs the seat nothing.
    assert "function chooseTitheResource(id)" in page
    assert "if (state.turn.titheChoice !== 'pending') {\n      return;\n    }" in page
    assert "closeTitheChoice();\n    payTithe(seat, id);" in page


def test_only_the_seat_being_asked_has_its_board_light(page: str) -> None:
    """Three other boards are on screen and not one of them is anyone else's to press."""
    assert (
        "var asking = Number(board.getAttribute('data-player-seat')) === state.activeSeat;" in page
    )
    assert "board.setAttribute('data-resource-choice', 'true');" in page
    assert "board.removeAttribute('data-resource-choice');" in page
    # And the key checks the board it stands on, so a revealed key still cannot pay a bystander.
    guard = "if (!board || Number(board.getAttribute('data-player-seat')) !== state.activeSeat) {"
    assert guard in page


def test_the_wheel_stays_lit_while_the_board_is_being_asked(page: str) -> None:
    """The press has been taken but the turn is not done with it, and the answer is elsewhere.

    Without this the plaque goes quiet the moment it is pressed while nothing on the wheel has
    changed, and anyone watching the wheel presses it again. Nothing moves on its own here, so the
    lit plaque is the only thing saying the turn is still waiting.
    """
    assert "if (state.turn.titheChoice === 'pending') {\n          chosen = true;" in page


def test_putting_a_turn_down_takes_an_unanswered_choice_with_it(page: str) -> None:
    assert "state.turn.resolution = null;" in page
    assert page.index("closeTitheChoice();") < page.index("function resetTurnFlow()")
    assert "function clearTurnMarks()" in page


def test_a_tithe_writes_down_what_it_paid_rather_than_where_it_came_from(page: str) -> None:
    """A receipt, not a rule: seat, stock and amount, kept by the turn that paid them.

    Working it out again from the tile on the way back would be a different question asked at a
    different time. The R button rewrites which duty lies where, so the tile that answers at reset
    need not be the tile that paid -- and a Cornucopia never said what it paid at all.
    """
    assert "function payTithe(seat, id) {" in page
    assert "creditResource(seat, id, 1);" in page
    assert "state.turn.paid = { seat: seat, id: id, amount: 1 };" in page
    # Both ways of paying go through it, so neither can pay without leaving the receipt.
    assert "payTithe(state.activeSeat, token);" in page
    assert "payTithe(seat, id);" in page
    assert "creditResource(state.activeSeat, token, 1);" not in page


def test_reset_takes_back_exactly_what_was_paid_and_no_more(page: str) -> None:
    """Named seat, named stock, named amount, and no floor on the way down.

    A floor would be a guess that the subtraction might be wrong. It cannot be: the only thing
    ever taken back is something this same turn added, so the stock cannot go below what the turn
    found -- and a floor would quietly forgive the day that stopped being true.
    """
    assert "function takeTitheBack() {" in page
    assert "creditResource(paid.seat, paid.id, -paid.amount);" in page
    assert "Math.max" not in page[page.index("function takeTitheBack()") :][:400]
    # Nothing recorded, nothing to take back: a still-pending choice needs no case of its own.
    assert "var paid = state.turn.paid;\n    if (!paid) {\n      return;\n    }" in page
    body = page[page.index("function resetTurnFlow()") :][:200]
    assert body.index("takeTitheBack();") < body.index("putCubesBack();")


def test_a_turn_that_has_been_handed_on_is_out_of_reach_of_the_next_reset(page: str) -> None:
    """The receipt is torn up as the wheel passes, so Reset can only ever reach its own turn."""
    ending = page[page.index("function endTurn()") :]
    ending = ending[: ending.index("\n  }")]

    assert "state.turn.paid = null;" in ending
    assert ending.index("state.turn.paid = null;") < ending.index("clearTurnMarks();")
    # And the ledgers go the same way, so what the turn sowed and sent home stands.
    for ledger in ("pickedUp", "sown", "recalled", "standingInCity"):
        assert f"state.turn.{ledger} = [];" in ending


def test_confirm_lights_only_once_there_is_a_finished_turn_to_end(page: str) -> None:
    """A Cornucopia still asking is a press taken, not a turn resolved.

    The wheel says as much by keeping `Tithe` lit, and the two plaques have to agree: one saying
    the turn is waiting while the other offers to end it is the table contradicting itself.
    """
    resolved = (
        "var resolved =\n"
        "      state.turn.phase === 'resolution_selected'"
        " && state.turn.titheChoice !== 'pending';"
    )
    assert resolved in page
    assert "setTurnControlState('confirm', state.setup.on ? sown : resolved, false);" in page
    # And the handler asks the same two questions, so the darkness is a statement and not a look.
    guard = "if (state.setup.on || state.turn.phase !== 'resolution_selected') {"
    assert guard in page
    assert "if (state.turn.titheChoice === 'pending') {\n      return;\n    }" in page


def test_confirm_hands_the_wheel_to_the_next_seat_the_count_actually_seats(page: str) -> None:
    """White back to red at four, and the pair alternating at two.

    The list is asked for rather than counted to, so the wrap is whatever the table currently
    seats: a count change that empties a chair cannot leave the wheel pointing at it.
    """
    assert "function nextSeatedSeat(seat) {" in page
    assert "var seats = seatsAtTable();" in page
    assert "return seats[(at + 1) % seats.length];" in page
    assert "setActiveSeat(nextSeatedSeat(state.activeSeat));" in page
    # Turn order is not being decided here: no start player, and no reordering of anything.
    ending = page[page.index("function endTurn()") :][:900]
    assert "firstPlayerSeat" not in ending
    assert "sort" not in ending


def test_one_plaque_confirms_two_different_things(page: str) -> None:
    """A setup sow while setup is on, and a finished turn the rest of the time.

    Setup keeps the path it had; ending a turn is the branch that did not exist before, which is
    why the branch is on `state.setup.on` and not on anything the turn knows.
    """
    handler = page[page.index("turnControl('confirm').addEventListener") :][:260]

    assert "if (state.setup.on) {" in handler
    assert "confirmSetupSow();" in handler
    assert "endTurn();" in handler


def test_ending_a_turn_still_writes_down_nothing_the_flow_does_not_own(page: str) -> None:
    """Confirm accepts the turn without reaching into the tallies the compact rows keep.

    The consequence is stated rather than hidden: `A->C` redraws the City column from the kept
    count, so pressing it after a turn is confirmed puts the recalled cubes back. Keeping the flow
    on its own side of the line is the smaller of the two, and moving the line is a decision of its
    own rather than something an unrelated PR does on the way past.
    """
    ending = page[page.index("function endTurn()") :][:900]

    assert "state.city" not in ending
    assert "renderCity" not in ending


def test_the_board_draws_the_keys_and_the_script_only_shows_them(page: str) -> None:
    """The seal's bargain again: the renderer strikes them, the page reveals and hides."""
    boards = re.findall(r'<rect data-resource-choice-key="(\w+)"[^>]*>', page)

    assert boards == ["wheat", "stone", "silver"] * len(SEATED_PLAYERS)
    assert page.count('data-resource-choice-key="wheat" x="453.5" y="45"') == len(SEATED_PLAYERS)
    board_background = load_player_boards_v2_layout()["palette"]["panel_background"]
    board_border = _darker_surface_colour(board_background)
    for key in re.findall(r"<rect data-resource-choice-key=[^>]*>", page):
        assert 'visibility="hidden"' in key
        assert f'fill="{board_background}"' in key
        assert f'stroke="{board_border}"' in key
    assert '[data-resource-choice="true"] [data-resource-choice-key] {' in page
    assert '[data-resource-choice="true"] [data-resource-divider] {' in page


def test_the_choice_keys_have_no_motion_yet(page: str) -> None:
    """TEMPORARY. Delete this test when the confirmation flash lands.

    The flash is deferred, not refused: "no animation for now" was the ask, and this holds the
    page to it until the work arrives. So this is a guard on an unfinished decision rather than a
    property of the page, and it is expected to fail exactly once -- when the flash is written --
    at which point deleting it is the right fix and the only one.

    That distinction matters because the other reading is corrosive: a test whose first act is to
    be deleted so the new code passes teaches that assertions are obstacles. Saying here, in
    advance, that this one is due to go stops its removal from being an argument.
    """
    script = page[page.rindex("<script>") :]

    moving = ("setTimeout", "setInterval", "requestAnimationFrame", "transition", "@keyframes")
    for name in moving:
        assert name not in script, name


def test_a_winner_cube_comes_out_of_the_abbey_it_is_taken_from(page: str) -> None:
    """AT+ moves a cube rather than making one: the Abbey it left is one cube shorter."""
    assert "function addWinner()" in page
    assert "if (state.winners.length >= WINNERS.slotCount || playerState.abbeyAcolytes < 1)" in page
    assert "playerState.abbeyAcolytes -= 1;" in page
    assert "state.winners.push(seat);" in page
    assert "renderBoardCubes(seat);" in page


def test_the_row_of_winners_is_as_long_as_the_record_has_sockets(page: str) -> None:
    layout, config = load_alms_table_layout(), load_alms_config()
    slots = len(placeholder_slots(layout, alms_rules(config)))

    assert slots == 4
    assert 'var WINNERS = {"slotCount":' + str(slots) + "};" in page


def test_a_placed_cube_takes_its_dashed_socket_out_from_under_it(page: str) -> None:
    """The cube exactly fills the socket, so a socket left showing would fringe it."""
    assert "function renderWinners()" in page
    assert "for (var slot = 1; slot <= WINNERS.slotCount; slot += 1)" in page
    assert "almsPanel.querySelectorAll('[data-season-end-winner-slot=\"' + slot + '\"]')" in page
    assert "show(cube, cube.getAttribute('data-player') === owner);" in page
    assert "almsPanel.querySelector('[data-placeholder-slot=\"' + slot + '\"]')" in page
    assert "show(socket, !owner);" in page


def test_a_reset_sends_every_cube_back_to_the_abbey_it_came_from(page: str) -> None:
    """Colours are kept because the seat is what is remembered, not the cube."""
    assert "function resetWinners()" in page
    assert "if (!state.winners.length)" in page
    assert "var returning = state.winners.slice();" in page
    assert "state.winners = [];" in page
    assert "ACOLYTES.abbeyCapacity, playerState.abbeyAcolytes + 1" in page


def test_a_serf_walks_to_the_abbey_and_becomes_an_acolyte_there(page: str) -> None:
    """One cube crosses the board rather than a cube being made: the Village is one shorter.

    The same two conditions the game setup page checks, and for the same reasons: an empty Village
    has nobody to send, and a full Abbey has nowhere to put him.
    """
    assert "function canMoveSerf()" in page
    assert (
        "return playerState.villageSerfs > 0 && playerState.abbeyAcolytes < ACOLYTES.abbeyCapacity;"
        in page
    )
    assert "if (!canMoveSerf())" in page
    assert "playerState.villageSerfs -= 1;" in page
    assert "playerState.abbeyAcolytes += 1;" in page


def test_the_serf_button_takes_the_seat_the_acolyte_row_is_set_to(page: str) -> None:
    """The row already names a player, so the button reads that rather than carrying four of its
    own, which is what the game setup page needs.
    """
    assert "var serfToAbbey = document.querySelector('[data-serf-to-abbey-button]');" in page
    assert page.count("acolytePlayerSeat.value") >= 2
    assert "serfToAbbey.disabled = !canMoveSerf();" in page
    assert "control.addEventListener('change', refreshBoardButtons);" in page


def test_a_board_draws_its_village_from_the_count_it_holds(page: str) -> None:
    """Serfs had no reason to be redrawn until one could leave; now they do.

    Both grids are drawn the same way, from the number of cubes standing in them, which is what
    lets a serf leaving the Village and arriving in the Abbey be the one move it looks like.
    """
    held = "var held = { village: playerState.villageSerfs, abbey: playerState.abbeyAcolytes };"

    assert "function renderBoardCubes(seat)" in page
    assert held in page
    assert "board.querySelectorAll('[data-token=\"' + area + '\"]')" in page
    assert "show(slot, Number(slot.getAttribute('data-token-index')) < held[area]);" in page
    assert "renderAcolyteBoard" not in page


def test_a_cube_sent_to_the_city_leaves_the_board_it_was_standing_on(page: str) -> None:
    """Abbey or Village, it is the one move: take from there, stand in the City column."""
    assert "function sendToCity(seat, area)" in page
    assert "if (!playerState || !cityRoom(seat) || playerState[area] < 1)" in page
    assert "playerState[area] -= 1;" in page
    assert "state.city[String(seat)] += 1;" in page
    assert "renderBoardCubes(seat);\n    renderCity(seat);" in page
    assert "sendToCity(String(acolytePlayerSeat.value), 'abbeyAcolytes');" in page
    assert "sendToCity(String(acolytePlayerSeat.value), 'villageSerfs');" in page


def test_a_city_column_takes_no_more_cubes_than_it_has_room_for(page: str) -> None:
    """Six a seat, opening on two, and the wheel is the one asked how many that is."""
    duty = duty_control_data(load_duty_wheel_layout())

    assert duty["city"] == {"capacity": CITY_STACK_HEIGHT, "opening": 2}
    assert CITY_STACK_HEIGHT == 6
    assert '"city":{"capacity":6,"opening":2}' in page
    assert "function cityRoom(seat)" in page
    assert "return state.city[String(seat)] < DUTY.city.capacity;" in page
    assert "opening[seat] = DUTY.city.opening;" in page
    assert "city: cityOpening()," in page


def test_a_full_city_or_an_empty_board_leaves_the_buttons_dead(page: str) -> None:
    assert "abbeyToCity.disabled = !cityRoom(seat) || playerState.abbeyAcolytes < 1;" in page
    assert "villageToCity.disabled = !cityRoom(seat) || playerState.villageSerfs < 1;" in page
    assert "var abbeyToCity = document.querySelector('[data-abbey-to-city-button]');" in page
    assert "var villageToCity = document.querySelector('[data-village-to-city-button]');" in page


def test_a_city_column_is_redrawn_in_every_tally_the_wheel_holds(page: str) -> None:
    """The wheel draws one tally per player count, so a column stands in three of them at once.

    Redrawing all three is what lets the count buttons keep doing the only thing they did before:
    show a tally. A seat that walked cubes into the City finds them there at any table size.
    """
    assert "function renderCity(seat)" in page
    assert "var playerId = (state.acolytes[String(seat)] || {}).playerId;" in page
    assert "dutyPanel.querySelectorAll('[data-city-column-player=\"' + playerId + '\"]')" in page
    assert "show(cube, Number(cube.getAttribute('data-city-cube')) < standing);" in page
    # The count buttons still only pick a tally; they deal no cubes of their own.
    assert "function renderDutyTallies()" in page
    assert "renderCity" not in page[page.index("function renderDutyTallies()") :].split("}")[0]


def test_the_city_only_seats_the_players_the_table_is_playing(page: str) -> None:
    """A dropped seat's City column goes with the tally it was drawn in, like every other column."""
    wheel = _block(page, "panel p-action")
    tallies = re.findall(
        r'data-cube-tally="city" data-player-count="(\d)"[^>]*opacity="(\d)"', wheel
    )
    columns = {
        count: set(
            re.findall(
                r'data-city-column-player="(\w+)"',
                wheel[wheel.index(f'data-cube-tally="city" data-player-count="{count}"') :].split(
                    "</g>"
                )[0],
            )
        )
        for count, _ in tallies
    }

    assert [count for count, opacity in tallies if opacity == "1"] == [str(DEFAULT_PLAYER_COUNT)]
    assert columns["2"] == {SEATED_PLAYERS[0], SEATED_PLAYERS[1]}
    assert columns["3"] == set(SEATED_PLAYERS[:3])
    assert columns["4"] == set(SEATED_PLAYERS)
    # The City seats players and nobody else: the neutral column belongs to the ring.
    assert all("neutral" not in column for column in columns.values())


def test_every_building_starts_on_the_map_owing_to_nobody(
    page: str, placements: list[dict]
) -> None:
    board_layout = load_player_boards_v2_layout()
    data = building_control_data(board_layout, placements)

    assert data["slotCount"] == int(board_layout["building_slot_count"])
    assert list(data["state"]["players"]) == [str(seat) for seat in range(1, 5)]
    assert all(
        slots["buildingSlots"] == [None] * data["slotCount"]
        for slots in data["state"]["players"].values()
    )
    assert list(data["state"]["available"]) == [
        str(building["setupSlot"]) for building in available_setup_buildings(placements)
    ]
    assert "var BUILDINGS = " + json.dumps(data, separators=(",", ":")) + ";" in page


def test_a_bought_building_leaves_the_map_and_the_list_it_was_bought_from(page: str) -> None:
    assert "function buyBuilding()" in page
    assert "var building = state.buildings.available[setupSlot];" in page
    assert "var number = firstEmptyBuildingSlot(seat);" in page
    assert "if (!building || !number)" in page
    assert "delete state.buildings.available[setupSlot];" in page
    assert "option.parentNode.removeChild(option);" in page
    assert "buyButton.addEventListener('click', buyBuilding);" in page


def test_a_bought_building_stands_in_the_first_empty_slot(page: str) -> None:
    """The slot is found the way the setup page finds it: the first one holding nothing."""
    assert "function firstEmptyBuildingSlot(seat)" in page
    assert "if (slots[index] === null)" in page
    assert "return index + 1;" in page
    assert "buildingSlotsOf(seat)[number - 1] = {" in page


def test_a_slot_shows_its_building_by_pointing_at_content_the_page_defined(page: str) -> None:
    """Buying and donating change a reference; no SVG is built in the browser."""
    assert "function renderBuildingSlots(seat)" in page
    assert "board.querySelector('[data-player-board-slot=\"' + (index + 1) + '\"]')" in page
    assert "group.querySelector('[data-building-content]')" in page
    assert (
        "content.setAttribute('href', donated ? entry.donatedContent : entry.boughtContent);"
        in page
    )
    assert (
        "'data-building-slot-state', entry === null ? 'empty' : (donated ? 'donated' : 'bought')"
        in page
    )


def test_a_building_keeps_the_dashed_border_of_the_slot_it_fills(page: str) -> None:
    """A filled slot is bordered like an empty one: the dashes are the slot, not a placeholder.

    They land on the building exactly, because a building's hexagon is the slot's hexagon drawn
    from the same centre at the same size, so the border reads as the slot's own edge rather than
    as something showing round what took it.
    """
    assert "show(content, entry !== null);" in page
    assert "data-slot-outline" not in page.split("<script")[-1]


def test_the_donated_side_of_a_slot_is_the_donated_tile_for_that_level(
    page: str, placements: list[dict]
) -> None:
    """Level 1 is 2 VP, level 2 is 4 VP, level 3 is 6 VP -- the tiles say so, not the page."""
    assert donated_vp_by_level(load_donated_building_tiles()) == {1: 2, 2: 4, 3: 6}

    defs = re.search(r'<svg[^>]*class="content-defs".*?</svg>', page, flags=re.DOTALL)
    assert defs is not None
    for level in (1, 2, 3):
        assert f'<g id="donated-level-{level}">' in defs.group(0)
    for building in available_setup_buildings(placements):
        assert f'<g id="bought-{building["buildingId"]}">' in defs.group(0)
        assert building["donatedContent"] == f"#donated-level-{building['level']}"


def test_a_slot_can_only_be_flipped_once_and_only_when_it_holds_something(page: str) -> None:
    assert "function donateBuilding()" in page
    assert "function canDonateBuilding(seat, number)" in page
    assert "return Boolean(entry) && !entry.donated;" in page
    assert "if (!canDonateBuilding(seat, number))" in page
    assert "buildingSlotsOf(seat)[number - 1].donated = true;" in page
    assert "donateButton.addEventListener('click', donateBuilding);" in page


def test_a_setup_roll_does_not_sell_a_bought_building_back_to_the_map(page: str) -> None:
    """The roll moves every overlay, so what is still for sale has to be said again after it."""
    assert "function renderMapBuildings()" in page
    assert "'#setup-fills g[data-building-id], #setup-labels g[data-building-id]'" in page
    assert "Object.prototype.hasOwnProperty.call(state.buildings.available, slot)" in page

    applied = re.search(r"function applySetupRoll\(roll\) \{(.+?)\n  \}", page, flags=re.DOTALL)
    assert applied is not None
    assert "renderMapBuildings();" in applied.group(1)


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
        ("1", "1", "player_one", "red"),
        ("2", "2", "player_two", "yellow"),
        ("3", "3", "player_three", "blue"),
        ("4", "4", "player_four", "white"),
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


def test_the_duty_wheel_is_driven_from_the_compact_rows_not_its_own_controls(page: str) -> None:
    """The wheel's own control bar would add height, so this page drives the board directly."""
    action = _block(page, "panel p-action")

    assert "data-player-count-button" not in action
    assert "duty-wheel-controls" not in page
    assert "duty-wheel-readout" not in page
    # the interactive board is what the compact rows switch between
    assert 'data-cube-tally="city"' in action
    assert 'data-token="merchant"' in action


def test_the_wheel_seats_the_players_this_table_seats(page: str) -> None:
    """Every board on this page counts players in the same seat order."""
    layout = duty_wheel_seating(load_duty_wheel_layout())
    colours = {player["id"]: player["color"] for player in layout["players"]}
    columns = {
        count: [
            colours.get(piece["id"], piece["color"])
            for piece in tally_pieces(layout, duty_position_by_id(layout, "produce"), count)
        ]
        for count in PLAYER_COUNTS
    }

    assert columns[2] == ["red", "yellow", "black"]
    assert columns[3] == ["red", "yellow", "blue", "black"]
    assert columns[4] == ["red", "yellow", "blue", "white"]
    assert layout["default_player_count"] == DEFAULT_PLAYER_COUNT
    # the City is not on the duty ring, so no neutral column stands on it
    city = tally_pieces(layout, duty_position_by_id(layout, layout["city_id"]), 2)
    assert [colours[piece["id"]] for piece in city] == ["red", "yellow"]


def test_the_wheels_own_page_seats_the_first_two_boards_at_two_players() -> None:
    """The standalone wheel now shares the table's left-to-right seat order."""
    layout = load_duty_wheel_layout()

    assert layout["seats_by_player_count"]["2"] == ["player_one", "player_two"]
    assert layout["default_player_count"] == 2


def test_the_player_count_picks_the_wheels_tally_rather_than_dealing_cubes(page: str) -> None:
    """Every count's tally is already drawn, centred for that many columns; this picks one."""
    assert "function renderDutyTallies()" in page
    assert "dutyPanel.querySelectorAll('[data-cube-tally]')" in page
    assert "show(tally, tally.getAttribute('data-player-count') === String(state.count));" in page

    applied = re.search(r"function applyPlayerCount\(count\) \{(.+?)\n  \}", page, flags=re.DOTALL)
    assert applied is not None
    assert "renderDutyTallies();" in applied.group(1)


def test_the_r_button_cycles_the_wheels_own_sample_setups(page: str) -> None:
    """The same three arrangements the wheel's own button walks, and in the same order."""
    layout = duty_wheel_seating(load_duty_wheel_layout())
    data = duty_control_data(layout)

    assert data["setups"] == duty_setups(layout)
    assert len(data["setups"]) == 3
    assert "var DUTY = " + json.dumps(data, separators=(",", ":")) + ";" in page
    assert "function randomizeDuties()" in page
    assert "state.dutySetup = (state.dutySetup + 1) % DUTY.setups.length;" in page
    assert "dutyRandomize.addEventListener('click', randomizeDuties);" in page
    assert "label.textContent = entry.label;" in page
    assert "show(icon, icon.getAttribute('data-tithe-token') === entry.tithe_icon);" in page


def test_taxation_stays_put_and_stays_the_tile_without_a_tithe_token(page: str) -> None:
    """It is the one duty with no Tithe token, so it is the one position drawn without a capsule."""
    layout = duty_wheel_seating(load_duty_wheel_layout())

    for setup in duty_setups(layout):
        landed = {entry["position"]: entry for entry in setup}
        assert landed["taxation"]["duty"] == "taxation"
        assert landed["taxation"]["label"] == "Taxation"
        assert landed["taxation"]["tithe_icon"] in (None, "")
    assert duty_position_by_id(layout, layout["city_id"])["label"] == "City"


def test_the_merchant_walks_the_ring_and_never_stands_in_the_city(page: str) -> None:
    layout = load_duty_wheel_layout()
    path = merchant_path(layout)

    assert path == list(layout["clockwise_order"])
    assert len(path) == 8
    assert "taxation" in path
    assert layout["city_id"] not in path
    assert layout["merchant_token"]["starts_on"] == "taxation"

    assert "function advanceMerchant()" in page
    assert "state.merchant = path[(path.indexOf(state.merchant) + 1) % path.length];" in page
    assert "merchantAdvance.addEventListener('click', advanceMerchant);" in page
    assert "show(token, token.getAttribute('data-duty-position') === state.merchant);" in page


def test_the_wheel_brings_its_turn_controls_onto_the_table(page: str) -> None:
    """The table is the page the shell was designed for, so it asks for it by name."""
    action = _block(page, "panel p-action")

    assert 'data-component="duty-wheel-turn-controls"' in action
    assert 'data-turn-state="idle"' in action
    assert re.findall(r'data-turn-control="(\w+)"', action) == [
        "sow",
        "reset",
        "confirm",
        "action",
        "tithe",
    ]
    assert 'data-turn-counter="cubes-in-hand"' in action
    assert 'data-turn-counter-value="0"' in action


def test_the_turn_plaques_survive_the_crop_the_table_takes_of_the_wheel(page: str, scale) -> None:
    """The table points the wheel's viewBox at its hexagon, so a plaque outside that box is gone.

    This is the question the shell was built to answer: the corners it stands in belong to the
    hexagon's own box, which is what gets cropped to, so the plaques are carried onto the table at
    the wheel's scale rather than being cut off the side of it.
    """
    left, top, width, height = scale[3].crop["action"]
    # The cube the wheel draws, in the units the crop is written in.
    cube = DUTY_CUBE_SIZE * load_duty_wheel_layout()["board"]["scale"]
    plaques = _turn_control_plaques(_block(page, "panel p-action"))

    assert len(plaques) == 6
    for x, y, plaque_width, plaque_height in plaques:
        assert left <= x and x + plaque_width <= left + width
        assert top <= y and y + plaque_height <= top + height
    # And they keep clear of the edge rather than sitting on the cut.
    assert min(x for x, _, _, _ in plaques) - left > cube
    assert left + width - max(x + plaque_width for x, _, plaque_width, _ in plaques) > cube
    assert min(y for _, y, _, _ in plaques) - top > cube
    assert top + height - max(y + plaque_height for _, y, _, plaque_height in plaques) > cube


# ---------------------------------------------------------------------------------------------
# The turn drawn on the wheel
# ---------------------------------------------------------------------------------------------


def test_a_turn_is_five_phases_and_the_clicks_that_move_between_them(page: str) -> None:
    """Sow arms the board, a space is picked, the hand walks, and a fork waits to be told."""
    assert "phase: 'idle'," in page
    for phase in ("sow_armed", "sowing", "branch_choice", "sow_complete"):
        assert f"setTurnPhase('{phase}');" in page, phase
    assert "turnOverlay.setAttribute('data-turn-state', phase);" in page
    # Each click only acts from the phase it belongs to, so a stray one changes nothing.
    for opening, phase in (
        ("function selectStartSpace(position) {", "sow_armed"),
        ("function chooseRoute(arrow) {", "branch_choice"),
    ):
        assert f"{opening}\n    if (state.turn.phase !== '{phase}') {{" in page, opening
    # And `Sow` asks only when there is something to ask: not mid-turn, and not during a setup.
    assert "function armSow() {\n    if (state.setup.on || state.turn.phase !== 'idle') {" in page


def test_every_plaque_on_the_wheel_is_wired_to_something(page: str) -> None:
    """Five of them now: the last, `Confirm`, only has a setup sow to accept."""
    script = page[page.index("<script>") :]

    assert "turnControl('sow').addEventListener('click', armSow);" in script
    assert "turnControl('reset').addEventListener('click', function () {" in script
    assert "turnControl(resolution).addEventListener('click', function () {" in script
    assert "turnControl('confirm').addEventListener('click', function () {" in script
    # Sow stays lit and turns active while a turn is open; Reset is only lit once one is.
    assert "setTurnControlState('sow', asking, asking && started);" in script
    assert "setTurnControlState('reset', started || state.setup.on, false);" in script
    assert "var started = state.turn.phase !== 'idle';" in script


def test_a_turn_starts_from_a_board_position_not_from_a_tile(page: str) -> None:
    """Every space is one of the engine's nine positions, and that is what a click hands on.

    A duty tile can be turned to another position; a position stays where it is. Keying the flow
    to the tiles would have it walking the wrong way round the board the first time they moved.
    """
    action = _block(page, "panel p-action")
    positions = re.findall(r'<g data-duty="\w+"[^>]*? data-board-position="(\w+)"', action)

    assert positions == board_positions()
    assert len(positions) == 9
    assert (
        "var dutySpaces = dutyPanel ? dutyPanel.querySelectorAll('[data-board-position]') : [];"
        in page
    )
    assert "var position = space.getAttribute('data-board-position');" in page
    assert "selectStartSpace(position);\n      selectDuty(position);" in page
    assert "space.getAttribute('data-board-position') === position" in page
    assert "space.setAttribute('data-turn-start-candidate', 'true');" in page
    assert "space.setAttribute('data-turn-start-selected', 'true');" in page
    # The tile lying on a space is drawn and named, and never asked about a move.
    assert 'data-duty-category="clerical"' in action
    assert "data-duty-category" not in render_turn_flow_script()


def test_the_cubes_a_space_is_showing_are_lifted_into_the_counter(page: str) -> None:
    """The tally the table is playing, so the count buttons decide what there is to pick up.

    It is looked for inside the space rather than by name, so the one hook that matters is the
    board position and the tally's own id never comes into it.
    """
    tally = "space.querySelector('[data-cube-tally][data-player-count=\"' + state.count + '\"]')"

    assert "var space = spaceAt(position);" in page
    assert tally in page
    assert "dutyPanel.querySelector('[data-board-position=\"' + position + '\"]')" in page
    assert "return cube.getAttribute('opacity') !== '0';" in page
    assert "cube.setAttribute('opacity', '0');" in page
    assert "setCubesInHand(cubes.length);" in page
    assert "counter.setAttribute('data-turn-counter-value', String(count));" in page
    assert "label.textContent = '\\u00d7 ' + count;" in page


def test_a_seat_can_only_pick_up_its_own_cubes(page: str) -> None:
    """A space is shared: the other seats' cubes and the neutral column's are standing on it too.

    Every cube on the wheel is drawn with the player it belongs to, so the hand is one filter over
    the cubes that space is showing. The neutral column is nobody's -- its cubes say `dummy` -- and
    the City slots nobody is standing in are hidden, so neither can be picked up by accident.
    """
    column = page[page.index("function columnForPosition(position, playerId)") :]
    column = column[: column.index("\n  }")]
    picked = page[page.index("function visibleActivePlayerCubesForPosition(position)") :]
    picked = picked[: picked.index("\n  }")]

    assert "return cube.getAttribute('data-player') === playerId;" in column
    assert "return columnForPosition(position, activePlayerId()).filter(function (cube) {" in picked
    assert "return cube.getAttribute('opacity') !== '0';" in picked
    # The hand is the seat's cubes, and the counter is how many of those there were.
    assert "var cubes = visibleActivePlayerCubesForPosition(position);" in page
    assert "hidePickupCubes(cubes);" in page
    assert "function hidePickupCubes(cubes) {" in page
    # Nothing sorts cubes by colour, id or column: the cube itself says whose it is.
    for guess in ("dummy", "data-city-column-player", "player_one", "fill"):
        assert guess not in picked, guess


def test_a_space_holding_nothing_of_the_seat_s_is_nothing_to_start_from(page: str) -> None:
    """The click is spent rather than refused: the board stays armed, so the next one still works.

    Marking a space with no cubes on it would put the turn into a phase holding an empty hand,
    and Reset would then be the only way back out of a turn that never began.
    """
    select = page[page.index("function beginSowFrom(position, options)") :]
    select = select[: select.index("\n  }\n")]
    nothing = select[: select.index("state.turn.start = position;")]

    assert (
        "var cubes = visibleActivePlayerCubesForPosition(position);\n"
        "    if (!cubes.length) {\n      return;\n    }"
    ) in nothing
    # Nothing has happened yet at the point it gives up: no marking, no hiding, no phase change.
    for untouched in ("markStartSpace", "hidePickupCubes", "setTurnPhase", "armStartSpaces"):
        assert untouched not in nothing, untouched


def test_the_board_whose_turn_it_is_is_asked_who_it_is(page: str) -> None:
    """The flow reads the player id from the rendered board at that seat."""
    active = page[page.index("function seatBoard(seat)") :]
    active = active[: active.index("function updateActiveSeatIndicator()")]

    seat_query = "'[data-component=\"player-board-v2\"][data-player-seat=\"' + seat"
    assert f"{seat_query} + '\"]'" in active
    assert "return seatBoard(state.activeSeat);" in active
    assert "return playerIdForSeat(state.activeSeat);" in active
    assert "return board ? board.getAttribute('data-player') : null;" in active
    assert "return board ? board.getAttribute('data-player-color') : null;" in active
    # The seat the flow opens on, and the boards it can ask about.
    assert "activeSeat: TURN.seat," in page
    seats = re.findall(
        r'data-component="player-board-v2" data-player-seat="(\d)"'
        r' data-player="(\w+)" data-player-color="(\w+)"',
        page,
    )
    assert seats == [
        ("1", "player_one", "red"),
        ("2", "player_two", "yellow"),
        ("3", "player_three", "blue"),
        ("4", "player_four", "white"),
    ]


def test_the_seat_whose_turn_it_is_lights_its_own_board_and_says_so(page: str) -> None:
    """One board lit in its own colour, and the same seat named on the stage for anything else.

    The board says it itself, with the wash its renderer drew up off its bottom edge and left
    hidden. Nothing here draws or sizes anything: each board is told whether it is the one, and the
    only rule is the one that turns that layer up from nothing, so the row cannot move.
    """
    assert 'data-active-player-seat="1"' in page
    assert 'data-active-player-color="red"' in page
    seats = _block(page, "seats")
    assert 'data-player-color="red" data-active-seat="true"' in seats
    assert seats.count('data-active-seat="true"') == 1
    assert seats.count('data-active-seat="false"') == 3
    assert (
        '.p-player[data-active-seat="true"] [data-active-player-glow="true"] { opacity: 1; }'
    ) in page
    assert "board.setAttribute('data-active-seat', active ? 'true' : 'false');" in page
    assert "stage.setAttribute('data-active-player-color', activePlayerColor() || '');" in page


def test_no_seat_is_ringed_round_the_outside_of_its_panel(page: str) -> None:
    """A ring round the outside of a board is a browser's idea of a selected thing, not a table's.

    Which is the whole reason the wash exists, so nothing is left drawing one: no outline on a
    panel, and the seat's colour reaches the board through the layer inside it and nowhere else.
    """
    assert "outline:" not in page
    assert "outline-offset" not in page
    assert ".p-player[data-active-seat" not in page.replace(
        '.p-player[data-active-seat="true"] [data-active-player-glow="true"]', ""
    )
    # And it is the wash the boards are drawn holding, not one the table adds on top of them.
    assert page.count('data-active-player-glow="true"') == 5
    assert "data-active-player-glow" not in render_turn_flow_script()


def test_a_cube_taken_off_the_board_is_the_cube_put_back_on_it(page: str) -> None:
    """What each cube was showing is remembered, which a half-full City column needs it to be.

    The City draws all six of a column's slots and hides the ones nobody is standing in, so
    putting cubes back by simply showing them would stand a seat in slots it never held. The hand
    that picks cubes up to sow them and the recall that sends them home both take them off the
    board the same way, so they are remembered and put back by the one pair of helpers.
    """
    assert "var held = { cube: cube, opacity: cube.getAttribute('opacity') };" in page
    assert "if (entry.opacity === null) {\n        entry.cube.removeAttribute('opacity');" in page
    assert "entry.cube.setAttribute('opacity', entry.opacity);" in page
    assert "state.turn.pickedUp = hideCubes(cubes);" in page
    assert "restoreCubes(state.turn.pickedUp);\n    state.turn.pickedUp = [];" in page
    assert "state.turn.recalled = hideCubes(sent);" in page
    assert "restoreCubes(state.turn.recalled);\n    state.turn.recalled = [];" in page


def test_reset_puts_the_board_back_the_way_sow_found_it(page: str) -> None:
    """A reset is the cubes and the marks, and it is written as those two halves.

    Confirming a setup sow wants the second half without the first -- the marks off, the cubes
    where the seat put them -- so the halves are separate functions rather than one run of
    statements a caller has to stop halfway through.
    """
    reset = page[page.index("function resetTurnFlow()") :]
    reset = reset[: reset.index("\n  }")]
    assert reset.index("putCubesBack();") < reset.index("clearTurnMarks();")

    put_back = page[page.index("function putCubesBack()") :]
    put_back = put_back[: put_back.index("\n  }")]
    marks = page[page.index("function clearTurnMarks()") :]
    marks = marks[: marks.index("\n  }\n")]

    for step in (
        "undoRecall();",
        "resetSownCubes();",
        "restorePickupCubes();",
    ):
        assert step in put_back, step
    # The turn is undone in the order it was done, last thing first: a cube can be sown into the
    # slot it was picked up from and then recalled out of it again.
    assert put_back.index("undoRecall();") < put_back.index("resetSownCubes();")
    assert put_back.index("resetSownCubes();") < put_back.index("restorePickupCubes();")

    for step in (
        "setCubesInHand(0);",
        "armStartSpaces(false);",
        "markStartSpace(null);",
        "armDutyChoices(false);",
        "markDutyChoice(null);",
        "clearBranchChoices();",
        "state.turn.start = null;",
        "state.turn.current = null;",
        "state.turn.route = [];",
        "state.turn.routeChoice = null;",
        "state.turn.duty = null;",
        "state.turn.resolution = null;",
        "turnOverlay.removeAttribute('data-last-route-choice');",
        "turnOverlay.removeAttribute('data-turn-current-position');",
        "turnOverlay.removeAttribute('data-turn-route');",
        "turnOverlay.removeAttribute('data-turn-duty');",
        "turnOverlay.removeAttribute('data-turn-resolution');",
        "setTurnPhase('idle');",
    ):
        assert step in marks, step
    # And clearing the marks moves nothing, which is what makes it safe on an accepted setup.
    for moves_a_cube in ("opacity", "hideCubes", "restoreCubes", "standColumn", "renderCity"):
        assert moves_a_cube not in marks, moves_a_cube


def test_the_table_moves_on_the_graph_the_engine_moves_on(page: str) -> None:
    """The wheel draws the board graph plus Kogge's four City-spoke reversals, and reads them.

    Nothing lists which positions branch: a position with one arrow leaving it offers no choice,
    and the City, east and west are simply the three with more than one. That stays true however
    the tiles are turned, which is the whole reason for keying any of this to positions.
    """
    action = _block(page, "panel p-action")
    leaving: dict[str, set[str]] = {}
    for origin, target in re.findall(
        r'data-from-position="(\w+)" data-to-position="(\w+)"', action
    ):
        leaving.setdefault(origin, set()).add(target)

    expected = {position: set(ways) for position, ways in board_edges().items()}
    expected["city"] |= {"east", "west"}
    expected["north"] |= {"city"}
    expected["south"] |= {"city"}
    assert leaving == expected
    assert {position: sorted(ways) for position, ways in leaving.items() if len(ways) > 1} == {
        "city": ["east", "north", "south", "west"],
        "east": ["city", "south_east"],
        "north": ["city", "north_east"],
        "south": ["city", "south_west"],
        "west": ["city", "north_west"],
    }
    assert "dutyPanel.querySelectorAll('[data-from-position][data-to-position]')" in page
    assert "var from = arrow.getAttribute('data-from-position');" in page
    assert "return outgoingEdgesByPosition[position] || [];" in page
    assert "var ways = branchArrowsFrom(state.turn.current);" in page
    assert "if (ways.length > 1) {" in page
    assert "arrow.setAttribute('data-turn-branch-choice', 'true');" in page


def test_turning_the_tiles_moves_a_duty_and_never_a_position(page: str) -> None:
    """Which is what the whole split is for: labels are the tiles', the graph is the board's.

    The roll writes the duty that landed on a space into `data-duty-category` and rewrites its
    title and Tithe token. It never touches a board position, an arrow, or an index, so a turn
    started after a roll branches at exactly the same three places as one started before it.
    """
    setup = page[page.index("function renderDutySetup()") :]
    setup = setup[: setup.index("\n  }")]

    assert "space.setAttribute('data-duty-category', entry.duty);" in setup
    assert "label.textContent = entry.label;" in setup
    assert "icon.getAttribute('data-tithe-token') === entry.tithe_icon" in setup
    for untouched in ("data-board-position", "data-from-position", "data-to-position"):
        assert untouched not in setup, untouched
    # The roll is the only thing that rewrites a space's category, and it is not the turn flow.
    assert page.count("setAttribute('data-duty-category'") == 1


def test_taking_a_road_puts_a_cube_down_and_walks_on(page: str) -> None:
    """The answer to a fork is one cube at the far end of the arrow, and then the walk resumes.

    The arrow has to be one of the ways out of where the hand is actually standing: a click on a
    green arrow left over anywhere else would sow from a position the hand had already left.
    """
    choose = page[page.index("function chooseRoute(arrow)") :]
    choose = choose[: choose.index("\n  }\n")]

    assert "if (arrow.getAttribute('data-from-position') !== state.turn.current) {" in choose
    assert (
        "arrow.getAttribute('data-from-position') + ':' + arrow.getAttribute('data-to-position');"
        in choose
    )
    assert "turnOverlay.setAttribute('data-last-route-choice', state.turn.routeChoice);" in choose
    assert "clearBranchChoices();" in choose
    assert "if (sowAlong(arrow)) {\n      continueSowing();\n    }" in choose
    assert "if (arrow.getAttribute('data-turn-branch-choice') === 'true') {" in page


def test_the_hand_walks_the_forced_ways_and_stops_only_at_a_fork(page: str) -> None:
    """One way out is not a choice, so the walk never asks about it; two are, so it waits.

    Nothing lists the forks. The hand puts a cube down and looks at how many arrows leave where it
    now stands, which is the same question `configs/board.json` answers, and it keeps answering it
    the same way however the tiles are turned.
    """
    sowing = page[page.index("function continueSowing()") :]
    sowing = sowing[: sowing.index("\n  }\n")]

    assert "while (state.turn.cubesInHand > 0) {" in sowing
    assert "highlightBranchChoices(ways);\n        setTurnPhase('branch_choice');" in sowing
    assert "if (!ways.length || !sowAlong(ways[0])) {\n        return;\n      }" in sowing
    assert sowing.rstrip().endswith("completeSowing();")
    # The start is picked up and then walked from, in that order.
    begin = page[page.index("function beginSowFrom(position, options)") :]
    begin = begin[: begin.index("\n  }\n")]
    assert begin.index("hidePickupCubes(cubes);") < begin.index("setCurrentPosition(position);")
    assert begin.rstrip().endswith("continueSowing();")


def test_a_cube_is_put_down_by_standing_it_in_an_empty_slot(page: str) -> None:
    """The reverse of a pickup, and the reason the wheel draws slots nothing is standing in.

    Nothing is drawn into the board and nothing is cut out of it, so a turn is a set of opacities
    to put back. A cube can even be sown into the slot it was lifted out of, which is why Reset
    puts the sown cubes away before it puts the picked-up ones back.
    """
    empty = page[page.index("function firstEmptySlotForPosition(position)") :]
    empty = empty[: empty.index("\n  }\n")]

    assert "var playerId = activePlayerId();" in empty
    assert "return cube.getAttribute('data-player') === playerId\n" in empty
    assert "&& cube.getAttribute('opacity') === '0';" in empty
    assert "slot.setAttribute('opacity', '1');" in page
    assert "state.turn.sown.push(slot);" in page
    assert "setCubesInHand(state.turn.cubesInHand - 1);" in page
    assert "slot.setAttribute('opacity', '0');" in page
    assert "state.turn.sown = [];" in page


def test_a_column_with_no_room_stops_the_walk_where_it_stands(page: str) -> None:
    """A tile shows a seat three cubes and the rules cap nothing, so a column can fill up.

    The hand keeps what it is still holding and the counter goes on showing it, which is the whole
    of the signal: there is nowhere to put the next one. Reset is the way out, and it is lit,
    because the turn is not over.
    """
    place = page[page.index("function placeOneCubeAtPosition(position)") :]
    place = place[: place.index("\n  }\n")]

    assert "if (!slot) {\n      return false;\n    }" in place
    # A stopped walk is still a sow: the counter keeps its cubes and Reset stays lit.
    assert "var started = state.turn.phase !== 'idle';" in page
    assert "setTurnControlState('reset', started || state.setup.on, false);" in page
    sowing = page[page.index("function continueSowing()") :]
    assert "setCubesInHand(0)" not in sowing[: sowing.index("\n  }\n")]


def test_an_empty_hand_leaves_the_duties_the_sow_reached_to_be_picked_from(page: str) -> None:
    """The green goes out, and the tiles the cubes landed on are offered as the duty to take."""
    complete = page[page.index("function completeSowing()") :]
    complete = complete[: complete.index("\n  }\n")]

    assert "clearBranchChoices();" in complete
    assert "setTurnPhase('sow_complete');" in complete
    # Unless the sow was a setup sow, which chooses no duty at the end of it.
    assert "armDutyChoices(!state.setup.on);" in complete


def test_the_duties_on_offer_are_the_ones_the_seat_is_standing_on(page: str) -> None:
    """Read off the board, not off the way the hand walked.

    A seat has acolytes out on the wheel before its turn begins, and those are as much its own as
    the ones it has just sown; asking where the walk went would offer it the tiles it happened to
    pass and hide the rest of its own. So the question is which tiles it has a cube standing on --
    which is the same question the hand asks before it picks anything up, and asking it the same
    way is what leaves the other three kinds of cube out of the choice without naming any of them.
    """
    positions = page[page.index("function occupiedDutyPositions()") :]
    positions = positions[: positions.index("\n  }\n")]

    assert "visibleActivePlayerCubesForPosition(position).length > 0" in positions
    assert "space.getAttribute('data-board-position');" in positions
    # And no reading of where the walk went is left anywhere near the choice.
    assert "state.turn.route" not in positions
    assert "state.turn.sown" not in positions
    assert "data-duty-category" not in positions
    assert "sownDutyPositions" not in page
    # The City is not a duty. It is asked for by the one thing that sets it apart on this board.
    assert "position !== cityPosition" in positions
    assert "if (!space.hasAttribute('data-duty-ring-index')) {" in page
    assert "cityPosition = space.getAttribute('data-board-position');" in page
    assert re.findall(r'data-board-position="city"[^>]*data-duty-ring-index', page) == []
    assert len(re.findall(r'<g data-duty="\w+"[^>]*data-duty-ring-index="\d"', page)) == 8


def test_only_the_seats_own_standing_cubes_put_a_tile_on_offer(page: str) -> None:
    """Which is not a rule written here: it is the one helper the hand already picks up by.

    A tile holding only another seat's cubes, only the neutral column's black ones, or only slots
    nobody is standing in is a tile this seat has none of its own standing on, and none of those
    three had to be named to be left out. What is asked is who the cube belongs to and whether it
    is showing, and the wheel draws a seat's empty slots hidden rather than not at all.
    """
    cubes = page[page.index("function visibleActivePlayerCubesForPosition(position)") :]
    cubes = cubes[: cubes.index("\n  }\n")]
    column = page[page.index("function columnForPosition(position, playerId)") :]
    column = column[: column.index("\n  }\n")]

    assert "columnForPosition(position, activePlayerId())" in cubes
    assert "cube.getAttribute('opacity') !== '0'" in cubes
    assert "cube.getAttribute('data-player') === playerId" in column
    # The tally the table is playing, so a hidden count's cubes are nobody's to be offered either.
    assert "activeTallyForPosition(position)" in column


def test_a_taken_duty_sends_home_everything_of_the_seats_that_is_standing_there(
    page: str,
) -> None:
    """Not only what this turn put there, now that a tile it never reached can be the one chosen.

    Which needs nothing said: the recall asks the same question the offer did, and remembers each
    cube by what it was showing rather than by how it came to be there, so a cube that was standing
    on that tile before the turn began goes home with the rest and comes back with them.
    """
    resolve = page[page.index("function resolveDuty(resolution)") :]
    resolve = resolve[: resolve.index("\n  }\n")]
    undo = page[page.index("function undoRecall()") :]
    undo = undo[: undo.index("\n  }\n")]

    sends_home = "visibleActivePlayerCubesForPosition(state.turn.duty).forEach(function (cube) {"
    assert sends_home in resolve
    assert "state.turn.recalled = hideCubes(sent);" in resolve
    for untouched in ("state.turn.route", "state.turn.sown", "state.turn.pickedUp"):
        assert untouched not in resolve, untouched
    # Every cube it hid is a cube it can put back exactly as it found it, whenever it got there.
    assert "restoreCubes(state.turn.recalled);" in undo
    assert "state.turn.standingInCity.forEach(function (slot) {" in undo


def test_a_duty_can_be_picked_and_picked_again_before_it_is_taken(page: str) -> None:
    """Only from what is on offer, and the mark moves to whichever is picked last.

    What is on offer is what `armDutyChoices` marked, and asking the mark is the whole of the
    check: it is put on when the hand empties, taken off when one of them is taken, and never put
    on at all during a setup sow. A second reading of who is eligible could only drift from it.
    """
    select = page[page.index("function selectDuty(position)") :]
    select = select[: select.index("\n  }\n")]

    assert "var space = spaceAt(position);" in select
    assert "if (!space || space.getAttribute('data-turn-duty-candidate') !== 'true') {" in select
    assert "state.turn.duty = position;" in select
    assert "turnOverlay.setAttribute('data-turn-duty', position);" in select
    assert "setTurnPhase('duty_selected');" in select

    # The tile is ringed and its trefoil coloured in, and whatever was marked before is not.
    mark = page[page.index("function markDutyChoice(position)") :]
    mark = mark[: mark.index("\n  }\n")]
    assert mark.index("space.removeAttribute('data-turn-duty-selected');") < mark.index(
        "node.setAttribute('data-turn-duty-selected', 'true');"
    )
    assert "ornament.removeAttribute('data-turn-duty-selected');" in mark
    assert "[spaceAt(position), ornamentAt(position)].forEach(function (node) {" in mark
    assert '[data-turn-duty-selected="true"] .board-circle {' in page
    # Filled, and still outlined as the board drew it: the lobes overlap, so without the lines
    # between them a coloured trefoil is a coloured blob.
    assert '[data-ornament-position][data-turn-duty-selected="true"] circle {' in page
    assert "fill: var(--active-player); stroke-opacity: 0.7;" in page


def test_the_trefoil_over_a_space_can_be_found_from_the_space(page: str) -> None:
    """The ornaments are one layer drawn over the whole board, not part of the nine spaces.

    So each says which position it stands over. Without that the only way to the right trefoil
    would be counting groups in the order they were drawn, which is exactly what every other hook
    on this board exists to avoid.
    """
    action = _block(page, "panel p-action")
    over = re.findall(r'<g data-ornament-position="(\w+)"', action)

    # One over each of the nine spaces. What order they were drawn in is what the hook makes moot.
    assert sorted(over) == sorted(board_positions())
    assert len(over) == 9
    assert "dutyPanel.querySelectorAll('[data-ornament-position]')" in page
    assert "dutyPanel.querySelector('[data-ornament-position=\"' + position + '\"]')" in page


def test_action_and_tithe_wake_up_only_once_a_duty_is_chosen(page: str) -> None:
    """Not while the hand is still walking, and not on an empty board: only on a chosen duty.

    Which of the two was pressed is kept and shown, because it is the one thing about them this
    page knows.
    """
    controls = page[page.index("function refreshTurnControls()") :]
    controls = controls[: controls.index("\n  }\n")]

    assert "['action', 'tithe'].forEach(function (name) {" in controls
    assert "var chosen = !state.setup.on && state.turn.phase === 'duty_selected';" in controls
    assert "setTurnControlState(name, chosen, state.turn.resolution === name);" in controls
    assert "setTurnControlState('confirm', state.setup.on ? sown : resolved, false);" in controls
    # Both plaques are wired to the one thing there is to do, and it is the phase that gates them.
    assert "['action', 'tithe'].forEach(function (resolution) {" in page
    assert "resolveDuty(resolution);" in page
    resolve = page[page.index("function resolveDuty(resolution)") :]
    resolve = resolve[: resolve.index("\n  }\n")]
    assert "if (state.turn.phase !== 'duty_selected') {\n      return;\n    }" in resolve
    assert "state.turn.resolution = resolution;" in resolve
    assert "turnOverlay.setAttribute('data-turn-resolution', resolution);" in resolve
    assert "setTurnPhase('resolution_selected');" in resolve


def test_taking_a_duty_sends_that_seat_s_cubes_home_and_nobody_else_s(page: str) -> None:
    """Off the chosen tile and into the seat's own City column, one slot per cube.

    It is the pickup's filter again, so the other seats' cubes and the neutral column's stay
    standing on the tile, and it is the sow's slot search again, so the cubes arrive in the City
    the same way a sown cube arrives anywhere. A cube with no slot waiting for it is left where it
    is: the City draws a seat six and the rules cap nothing, so a column can fill.
    """
    resolve = page[page.index("function resolveDuty(resolution)") :]
    resolve = resolve[: resolve.index("\n  }\n")]

    assert "visibleActivePlayerCubesForPosition(state.turn.duty).forEach(function (cube) {" in (
        resolve
    )
    assert "var slot = firstEmptySlotForPosition(cityPosition);" in resolve
    assert "if (!slot) {\n        return;\n      }" in resolve
    assert "slot.setAttribute('opacity', '1');" in resolve
    assert "home.push(slot);\n      sent.push(cube);" in resolve
    assert "state.turn.standingInCity = home;" in resolve
    assert "state.turn.recalled = hideCubes(sent);" in resolve
    # Nothing here sorts a cube by colour, by column, or by the tile it is standing on.
    for guess in ("fill", "dummy", "data-city-column-player", "data-duty-category"):
        assert guess not in resolve, guess


def test_the_setup_button_stands_between_the_wheel_and_the_ship(page: str) -> None:
    """One more button on the first row, and nothing else about the rows changes."""
    row = _block(page, 'control-row" data-controls-row="1')
    labels = re.findall(r"<button[^>]*>([^<]+)</button>", row)

    assert labels == ["2P", "3P", "4P", "1", "2", "3", "4", "5", "6", "R", "Setup", "S+", "M+"]
    assert '<button type="button" data-setup-mode-button="true" aria-pressed="false">' in row
    assert page.count("data-setup-mode-button") == 2
    assert "var setupButton = document.querySelector('[data-setup-mode-button]');" in page
    assert "setupButton.addEventListener('click', enterSetupMode);" in page


def test_a_setup_deals_every_seat_five_acolytes_in_the_city_and_clears_the_tiles(
    page: str,
) -> None:
    """The game before the game: nobody is on the wheel yet and everybody is holding five.

    The seats are dealt to by name, so the neutral column's black cubes are not touched by it --
    they are seeded onto the ring at the start and no seat plays them. The number is five because
    that is what the engine's own setup deals; this page reads nothing from it.

    The deal is made on the tally the table is playing and nowhere else. The wheel drew a tally for
    every count and shows one at a time, and `renderCity` writes a seat's City column in all of
    them at once -- which would leave the other three saying a seat is in the City while their own
    duty tiles still hold the cubes it sowed out of it.
    """
    deal = page[page.index("function dealSetupCubes()") :]
    deal = deal[: deal.index("\n  }\n")]

    assert f"var SETUP_CUBES = {SETUP_CITY_CUBES};" in page
    assert SETUP_CITY_CUBES == 5
    assert "seatsAtTable().forEach(function (seat) {" in deal
    assert "var playerId = playerIdForSeat(seat);" in deal
    assert "standColumn(position, playerId, position === cityPosition ? SETUP_CUBES : 0);" in deal
    assert "state.city[String(seat)] = SETUP_CUBES;" in deal
    assert "renderCity" not in deal
    # Only the seats in play are dealt to, so a hidden seat's cubes are left where they were drawn.
    seats = page[page.index("function seatsAtTable()") :]
    assert "for (var seat = 1; seat <= state.count; seat += 1) {" in seats[: seats.index("\n  }\n")]
    # Standing a column is the same trick as sowing: the wheel drew the slots, this shows them.
    stand = page[page.index("function standColumn(position, playerId, standing)") :]
    stand = stand[: stand.index("\n  }\n")]
    assert "columnForPosition(position, playerId).forEach(function (cube, index) {" in stand
    assert "cube.setAttribute('opacity', index < standing ? '1' : '0');" in stand


def test_a_setup_sow_starts_itself_from_the_city_with_nothing_to_ask(page: str) -> None:
    """There is one place a setup sow can start from, so asking which would be a click for nothing.

    The seat's five come up into the hand the moment the wheel reaches it and the walk begins,
    which -- starting where it starts -- means it stops at the City's fork straight away with the
    two ways out lit. So `Sow` has nothing to ask and is dark for the whole of a setup, and no
    space is ever armed to be clicked.
    """
    start = page[page.index("function startSetupSow()") :]
    start = start[: start.index("\n  }\n")]
    enter = page[page.index("function enterSetupMode()") :]
    enter = enter[: enter.index("\n  }\n")]

    assert start == "function startSetupSow() {\n    beginSowFrom(cityPosition, { ring: false });"
    # Dealt to, seated, and then set going, in that order.
    assert enter.index("dealSetupCubes();") < enter.index("setActiveSeat(1);")
    assert enter.index("setActiveSeat(1);") < enter.index("startSetupSow();")
    # The next seat is set going the same way, and so is a seat starting over.
    assert "setActiveSeat(waiting[0]);\n      startSetupSow();" in page
    restart = page[page.index("function restartSetupSow()") :]
    assert restart[: restart.index("\n  }\n")].rstrip().endswith("startSetupSow();")
    # Nothing is armed to be clicked, because nothing is waiting to be asked.
    assert "armStartSpaces(true);" in page[page.index("function armSow()") :][:200]
    for setup in ("function startSetupSow()", "function enterSetupMode()"):
        block = page[page.index(setup) :]
        assert "armStartSpaces" not in block[: block.index("\n  }\n")], setup


def test_the_city_is_not_ringed_for_a_setup_sow_it_was_never_asked_about(page: str) -> None:
    """The ring marks the space a seat chose to start from, and a setup seat chose nothing.

    Every setup sow begins at the City -- pressing `Setup`, confirming onto the next seat, and
    `Reset` all go through the one function -- so colouring it in would be an answer shown to a
    question never asked, on the one space it could ever be shown on. The two green roads out of
    the City are what a setup is waiting on, and they are lit as they are for any other fork.
    """
    begin = page[page.index("function beginSowFrom(position, options)") :]
    begin = begin[: begin.index("\n  }\n")]

    assert "markStartSpace(options && options.ring === false ? null : position);" in begin
    # Passing nothing rings the space, so an ordinary turn is asked for in the same words as before.
    assert "beginSowFrom(position);" in page
    # And the one that is not rung is the one the seat never picked.
    assert "beginSowFrom(cityPosition, { ring: false });" in page
    assert page.count("beginSowFrom(") == 3
    # Not ringing it means clearing the ring, so no space is left wearing one from before.
    mark = page[page.index("function markStartSpace(position)") :]
    mark = mark[: mark.index("\n  }\n")]
    assert "space.removeAttribute('data-turn-start-selected');" in mark
    # The roads are lit by the walk itself, which a setup sow runs like any other.
    assert begin.rstrip().endswith("continueSowing();")
    assert "highlightBranchChoices(ways);" in page


def test_a_setup_sow_offers_no_duty_at_the_end_of_it(page: str) -> None:
    """The seat was putting its acolytes out, not taking a duty.

    So the two plaques that do something to a duty stay dark the whole way through, nothing is
    marked to be picked from, and `Confirm` -- which in a normal turn ends the turn -- is here
    waiting on the hand emptying instead.
    """
    controls = page[page.index("function refreshTurnControls()") :]
    controls = controls[: controls.index("\n  }\n")]

    assert "var sown = state.turn.phase === 'sow_complete';" in controls
    assert "var chosen = !state.setup.on && state.turn.phase === 'duty_selected';" in controls
    assert "setTurnControlState('confirm', state.setup.on ? sown : resolved, false);" in controls
    assert "armDutyChoices(!state.setup.on);" in page
    # `Sow` is dark all through it, and `Reset` -- the only way back to the start of one -- is lit.
    assert "var asking = !state.setup.on;" in controls
    assert "setTurnControlState('sow', asking, asking && started);" in controls
    assert "setTurnControlState('reset', started || state.setup.on, false);" in controls
    # And a setup sow is a sow like any other: setup starts one and does none of the walking.
    setup = page[page.index("function dealSetupCubes()") :]
    setup = setup[: setup.index("function applyPlayerCount")]
    for untouched in ("continueSowing", "selectStartSpace", "sowAlong", "placeOneCubeAtPosition"):
        assert untouched not in setup, untouched


def test_confirming_a_setup_sow_hands_the_wheel_to_the_next_seat(page: str) -> None:
    """And the acolytes it put out stay out: what a reset would need in order to take them back is
    dropped rather than played back, which is the whole of what confirming means here.

    The seats go in the order they are dealt to, and when the last has sown the table goes back to
    the first to begin. Setup lets go of the board then, and the button comes back up.
    """
    confirm = page[page.index("function confirmSetupSow()") :]
    confirm = confirm[: confirm.index("\n  }\n")]

    assert "if (!state.setup.on || state.turn.phase !== 'sow_complete') {" in confirm
    assert "state.setup.done.push(seat);" in confirm
    assert "state.city[String(seat)] = " in confirm
    assert "visibleActivePlayerCubesForPosition(cityPosition).length;" in confirm
    # The ledgers are dropped and only the marks come off, so no cube is moved by confirming.
    assert "state.turn.pickedUp = [];" in confirm
    assert confirm.index("state.turn.sown = [];") < confirm.index("clearTurnMarks();")
    assert "return state.setup.done.indexOf(other) === -1;" in confirm
    assert "setActiveSeat(waiting[0]);" in confirm
    assert "state.setup.on = false;\n      state.setup.finished = true;" in confirm
    assert "setActiveSeat(1);" in confirm
    assert "turnControl('confirm').addEventListener('click', function () {" in page


def test_the_last_seat_to_confirm_leaves_the_wheel_exactly_as_it_stands(page: str) -> None:
    """A confirmed placement is confirmed whoever made it, so the last seat is not a special case.

    The one thing the last seat does differently is what comes after: there is no seat to hand the
    wheel to, so the table goes back to the first to begin and setup lets go of the board. Nothing
    on that path deals, redeals, stands a column up or puts a turn back -- the whole of the
    finishing is a flag, a seat number and the marks coming off -- so what the four of them sowed
    is still standing there when the button comes back up.
    """
    confirm = page[page.index("function confirmSetupSow()") :]
    confirm = confirm[: confirm.index("\n  }\n")]
    finish = confirm[confirm.index("} else {") :]
    finish = finish[: finish.index("\n    }") + len("\n    }")]

    for moves_a_cube in (
        "dealSetupCubes",
        "restartSetupSow",
        "resetTurnFlow",
        "putCubesBack",
        "standColumn",
        "renderCity",
        "renderDutyTallies",
        "hideCubes",
        "restoreCubes",
        "opacity",
    ):
        assert moves_a_cube not in confirm, moves_a_cube
    assert [line.strip() for line in finish.splitlines() if line.strip()] == [
        "} else {",
        "state.setup.on = false;",
        "state.setup.finished = true;",
        "setActiveSeat(1);",
        "}",
    ]
    # And the button comes up and `Sow` goes back to work, both off the one flag.
    assert "setupButton.setAttribute('aria-pressed', state.setup.on ? 'true' : 'false');" in page
    assert "var asking = !state.setup.on;" in page


def test_reset_in_a_setup_restarts_the_sow_in_hand_and_no_other(page: str) -> None:
    """The seats that have already confirmed keep what they placed, and setup stays on the board.

    Which is the ordinary reset, the seat's five acolytes stood back up -- the compact rows can
    move acolytes in and out of the City between one press and the next -- and then the same seat
    set going again from the City, since that is the only place a setup sow starts from and `Sow`
    is dark. It is also the way back from anything that has put the flow down mid-setup.
    """
    restart = page[page.index("function restartSetupSow()") :]
    restart = restart[: restart.index("\n  }\n")]

    assert "resetTurnFlow();" in restart
    assert "standColumn(cityPosition, activePlayerId(), SETUP_CUBES);" in restart
    assert "state.city[String(state.activeSeat)] = SETUP_CUBES;" in restart
    assert restart.index("standColumn(") < restart.index("startSetupSow();")
    for untouched in ("state.setup.on", "setActiveSeat", "state.setup.done"):
        assert untouched not in restart, untouched
    assert "if (state.setup.on) {\n        restartSetupSow();\n      } else if (" in page


def test_a_setup_says_where_it_has_got_to(page: str) -> None:
    """Three words for the board and the seats that have finished with it.

    Which seat is sowing is not among them: the board already rings it, and the stage already says
    so. A second copy could only fall out of step with the first.
    """
    refresh = page[page.index("function refreshSetupMode()") :]
    refresh = refresh[: refresh.index("\n  }\n")]

    assert "setupButton.setAttribute('aria-pressed', state.setup.on ? 'true' : 'false');" in refresh
    assert "state.setup.on ? 'active' : state.setup.finished ? 'complete' : 'inactive');" in refresh
    assert "'data-setup-completed-seats', state.setup.done.join(',')" in refresh
    assert "data-setup-active-seat" not in page
    assert "stage.setAttribute('data-active-player-seat', String(state.activeSeat));" in page
    assert "setup: {\n      on: false,\n      done: [],\n      finished: false\n    }" in page


def test_a_deal_changes_what_is_kept_and_a_turn_does_not(page: str) -> None:
    """Which is why the two live apart.

    A turn hides cubes and remembers them, so Reset can hand the board straight back. A deal is
    meant to stick, so it writes the City count the compact rows keep -- the same one `A->C` and
    `V->C` read and redraw from -- rather than leaving the board saying one thing and the rows
    another.
    """
    flow = render_turn_flow_script()

    assert "state.city" not in flow
    assert "renderCity" not in flow
    assert "function dealSetupCubes()" not in flow
    # What the flow does know is whether a setup is on, which is what a plaque hangs off.
    assert "state.setup.on" in flow


def test_a_phase_only_ever_sets_a_word_on_the_board(page: str) -> None:
    """Which is what lets the styling live in the stylesheet rather than in the handlers."""
    assert ".game-table-stage { --active-player: #C94C4C; }" in page
    assert '[data-turn-control][data-turn-control-enabled="false"] { opacity: 0.4; }' in page
    assert '[data-turn-control][data-turn-control-active="true"] rect { fill: #F2EEDF; }' in page
    assert '[data-turn-start-candidate="true"] { cursor: pointer; }' in page
    assert '[data-turn-start-candidate="true"] .board-circle { stroke: #F2EEDF' in page
    assert "stroke: var(--active-player); stroke-width: 5.5;" in page
    assert '[data-turn-branch-choice="true"] .arrow-interior { fill: #1E7A34; }' in page
    # The seat whose turn it is is what both the board's ring and the outline are coloured from.
    assert '"seat":1' in page
    assert '"colors":{"1":"#C94C4C","2":"#E3C64A","3":"#3B6EA5","4":"#FFFFFF"}' in page
    assert "setProperty('--active-player', TURN.colors[String(state.activeSeat)]);" in page


def test_a_change_of_table_size_puts_a_turn_down_first(page: str) -> None:
    """A count change redraws the very tallies a turn may be holding cubes out of.

    Resetting first is the whole of the rule: the buttons keep working exactly as they did, and a
    turn cannot be left holding cubes that a redraw has since put back on the board.
    """
    count = page[page.index("function applyPlayerCount(count)") :]
    count = count[: count.index("\n  }\n")]

    assert count[: count.index("state.count = count;")].endswith("resetTurnFlow();\n    ")
    # And a seat that has just left the table cannot be left holding the turn.
    assert "setActiveSeat(state.activeSeat > count ? 1 : state.activeSeat);" in count
    # A setup is dealt again for the same reason, onto a tally drawn as the wheel opens.
    assert "if (state.setup.on) {\n      enterSetupMode();\n    } else {" in count
    assert "state.setup.finished = false;" in count
    # The City buttons redraw a column too, so they put a turn down before they move a cube.
    city = page[page.index("function sendToCity(seat, area)") :]
    assert "resetTurnFlow();\n    playerState[area] -= 1;" in city[: city.index("\n  }\n\n")]


def test_a_turn_changes_what_is_drawn_and_nothing_that_is_kept(page: str) -> None:
    """It hides cubes and remembers them. It moves none, and it owns nothing else on the page.

    The compact rows keep the tallies -- who is standing where, in the City, on the tracks -- and
    the turn flow does not reach into any of them. That is what makes it safe for Reset to hand
    the board straight back, and it is the line the next PR will have to cross deliberately.
    """
    flow = render_turn_flow_script()
    kept = ("city", "acolytes", "discs", "resources", "buildings")

    assert flow in page
    for owned in kept:
        assert f"state.{owned}" not in flow, owned
    for redraw in ("renderCity(", "renderBoardCubes(", "renderDutyTallies(", "fetch("):
        assert redraw not in flow, redraw
    assert "state.turn.cubesInHand = count;" in flow


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


def test_the_left_column_is_the_artworks_width_and_not_its_widest_sentence(page: str) -> None:
    """Otherwise the boards rescale whenever the text under them gets longer.

    `.left` holds the Alms Table over whatever a page puts in the slack beneath it -- controls
    here, the event log on the play view. With no width of its own a flex column takes its widest
    child's, so the first logged sentence stretched it and the artwork above rescaled to match, by
    an amount that depended on the wording rather than on the layout. Pinning it to the Alms
    Table's own width makes the text wrap inside the column instead.

    The width has to be `--w-alms`, not a number: every panel here is solved from the one cube, so
    a column measured in pixels would come loose from the board it is supposed to be as wide as.
    """
    rule = re.search(r"\.left \{(.*?)\}", page, re.S)
    assert rule, "the left column has no rule at all"
    width = re.search(r"width: ([^;]+);", rule.group(1))
    assert width, "the left column is still sized by whichever child is widest"
    assert "var(--w-alms)" in width.group(1)
    # Panel and all: the column is as wide as the Alms Table comes out on screen, which is the
    # drawing plus the border and padding every panel carries.
    assert width.group(1) == f"calc(var(--w-alms) + {PANEL_CHROME}px)"


def test_the_left_column_gives_way_before_the_page_does(page: str) -> None:
    """A column that grows past the row makes the whole page taller, and that is not a local cost.

    Every panel here is sized from `100vh`, so a page that scrolls is also a page drawing at a
    smaller scale. That is how the play view and the debug table came out looking like two
    different layouts on a short window while being identical at a matched one: the log pushed one
    of them into a scrollbar and the scrollbar re-solved the cube.

    So the column is capped at the row it sits in, and whatever lives in the slack finds its own
    way to fit. The overflow is the backstop for a tenant that cannot: the debug table's controls
    have a fixed height, and hiding a control with no way to reach it would be worse than the
    taller page.
    """
    rule = re.search(r"\.left \{(.*?)\}", page, re.S)
    assert rule, "the left column has no rule at all"
    assert "max-height: var(--row-height);" in rule.group(1)
    assert "overflow-y: auto;" in rule.group(1)


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


def test_a_donated_buildings_star_reads_at_the_size_of_a_pilgrimage_sites_star(scale) -> None:
    """Both are VP stars, so on a table showing both they should be the one piece.

    Neither tile is drawn at its own size here: a site goes into a map hex and a donated building
    into a player board's building slot, and those two are not scaled alike. A star of the same
    size in either tile's own units therefore does not come out the same size on the page, which
    is why the donated renderer's `STAR_OUTER_RADIUS` is written for this page rather than for its
    own. This is the measurement it was written from.
    """
    _, _, _, solved = scale
    tile_into_map = load_map_layout()["hex_size"] / TILE_HEX_RADIUS
    tile_into_slot = BUILDING_SLOT_HEX_SIZE / DONATED_HEX_RADIUS

    site_star = SITE_STAR_RADIUS * tile_into_map * _per_unit(solved, "map")
    donated_star = DONATED_STAR_RADIUS * tile_into_slot * _per_unit(solved, "player")
    site_vp = SITE_VP_FONT_SIZE * tile_into_map * _per_unit(solved, "map")
    donated_vp = DONATED_VP_FONT_SIZE * tile_into_slot * _per_unit(solved, "player")

    assert donated_star == pytest.approx(site_star, rel=1e-4)
    assert donated_vp == pytest.approx(site_vp, rel=1e-4)


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
    assert seat["panel_width"] * player / alms == pytest.approx(464.3, abs=0.5)


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


def test_a_building_slot_renders_the_size_of_the_map_hex_it_stands_for(scale) -> None:
    """A building is the same hexagon whether it is still on the map or bought into a slot.

    This is the measurement `BUILDING_SLOT_HEX_SIZE` is written from, and the reason it cannot be
    worked out from the board alone: the table draws the map at the full cube and a seat at the
    shortfall the duty wheel is fitted to, so a slot has to be drawn about a quarter larger in the
    board's units to come out level. Re-measure here if either board's scale ever moves.

    It was long the other way about -- the slot was a map hex counted in MARKER_CUBEs, the unit the
    board writes its geometry in, which stopped being its cube when the cubes were matched to the
    wheel -- and it rendered a fifth short.
    """
    _, _, cubes, solved = scale
    slot = BUILDING_SLOT_HEX_SIZE * _per_unit(solved, "player")
    map_hex = load_map_layout()["hex_size"] * _per_unit(solved, "map")

    assert cubes["player"] == 2 * TOKEN_RADIUS
    assert slot == pytest.approx(map_hex, rel=1e-4)
    # Larger in the board's own units than the hex is in the map's, by the seats' shortfall.
    assert BUILDING_SLOT_HEX_SIZE > load_map_layout()["hex_size"]


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
    # size of the answer rather than the answer. Solving at that height puts it at 1188.
    assert width_bound * solved.stack_cubes + solved.stack_fixed == pytest.approx(1194, abs=10)
    # And the cube it settles at there, which is a fifth larger than the two-seat table reached.
    assert width_bound == pytest.approx(10.6, abs=0.2)


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

    The building content the board slots point at is the one SVG that is not a panel: it draws
    nothing itself and is sized 0 by 0, so it is measured by no rule of the page's.
    """
    roots = [root for root in re.findall(r"<svg\b[^>]*>", page) if "content-defs" not in root]

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
    resource_steps = 2 * len(RESOURCE_ABBREVIATIONS)
    # counts, setup rolls, R/Setup/S+/M+, four disc steps, the resource steps, AT+/ATr, Buy,
    # Donate, Move acolyte, S->A, A->C and V->C
    compact_buttons = len(PLAYER_COUNTS) + len(SETUP_ROLLS) + 4 + 4 + resource_steps + 2 + 2 + 4
    assert page.count("<button") == compact_buttons
    assert page.count("<script") == 1
    assert "data-player-count-button" in page
    assert "data-setup-roll-button" in page
    assert "data-disc-track" in page
    assert "data-resource-button" in page
    assert "data-alms-winner-button" in page
    assert "data-building-buy-button" in page
    assert "data-building-donate-button" in page
    assert "data-duty-randomize-button" in page
    assert "data-merchant-advance-button" in page
    assert "move-acolyte" in page
    assert "data-serf-to-abbey-button" in page
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
