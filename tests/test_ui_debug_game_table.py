"""The generated game table page is composition only, so these tests are about arrangement.

They check that every component reached the page through its own renderer, that the three columns
hold the right things in the right order, that the shared cube scale is what sizes them, and that
the page adds no controls or state of its own. Nothing here looks at the drawing itself; each
renderer's own tests do that, and nothing here renders a browser.
"""

import math
import re
from pathlib import Path

import pytest

from tools.ui_debug.generate_game_table import (
    GAP_PX,
    MARKER_SEAT,
    PAGE_TITLE,
    PANEL_CHROME,
    PIETY_VARIANT_ID,
    SEAT_COLS,
    SEAT_ROWS,
    SEATED_PLAYERS,
    board_measurements,
    crop_svg,
    default_output_path,
    duty_hexagon,
    generate_game_table_page,
    regular_hexagon_path,
    regularise_duty_hexagon,
    solve_table_scale,
)
from tools.ui_debug.render_alms_table import (
    load_alms_config,
    load_alms_table_layout,
    render_alms_table_controls_html,
)
from tools.ui_debug.render_duty_wheel import load_duty_wheel_layout, render_duty_wheel_controls_html
from tools.ui_debug.render_map import load_map_layout, render_map_svg
from tools.ui_debug.render_piety_track_v2 import load_piety_track_v2_layout
from tools.ui_debug.render_player_boards_v2 import (
    BUILDING_SLOT_HEX_SIZE,
    load_player_boards_v2_layout,
    players_of,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DEBUG_DIR = REPO_ROOT / "tools" / "ui_debug"
GENERATOR_SCRIPT = UI_DEBUG_DIR / "generate_game_table.py"
INDEX_HTML = UI_DEBUG_DIR / "index.html"

# The text the page used to carry above the table, and no longer should.
FORMER_HEADING = "PILGRIM — Generated game table layout"
FORMER_BLURB = "The existing debug renderers composed into one 2-player table"


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
    start = page.index(f'<div class="{class_name}">')
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
    """Only the page's own stylesheet; the renderers keep their own fonts and colours."""
    stylesheet = page[page.index("<style>") : page.index("</style>")]

    for stale in ("game-table-subtitle", "h1 ", "--ink", "Georgia", "color:", "font-family"):
        assert stale not in stylesheet, stale


def test_page_has_a_three_column_stage(page: str) -> None:
    """One row of three: the alms/seats column, the piety/duty column, and the map."""
    assert '<div class="game-table-stage">' in page
    row = _block(page, "row")

    for class_name in ("left", "col", "panel p-map"):
        assert f'<div class="{class_name}">' in row, class_name
    assert row.index('class="left"') < row.index('class="col"') < row.index('class="panel p-map"')


def test_column_one_holds_the_alms_table_above_the_player_boards(page: str) -> None:
    left = _block(page, "left")

    assert left.index("p-alms") < left.index('class="seats"')
    assert left.index("p-alms") < left.index("p-player")
    assert 'data-component="alms-table"' in left
    assert left.count('data-component="player-board-v2"') == len(SEATED_PLAYERS)


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


def test_page_seats_two_of_the_four_players(page: str) -> None:
    """Two boards of the four the layout describes, drawn one above the other.

    Which two is layout state to look at rather than a seating rule: player counts are not wired
    up on this page, so the pair is fixed.
    """
    layout = load_player_boards_v2_layout()
    seats = _block(page, "seats")

    assert len(SEATED_PLAYERS) == 2
    assert seats.count('data-component="player-board-v2"') == 2
    assert {player["id"] for player in players_of(layout)} >= set(SEATED_PLAYERS)
    for player_id in SEATED_PLAYERS:
        assert f'data-player="{player_id}"' in seats


def test_the_marker_card_goes_on_the_top_board_and_only_that_one(page: str) -> None:
    """One first-player marker at this table, on the board at the top of the column.

    Layout state to look at, like the choice of seats: nothing here works out who starts, and there
    is no control to move the card. The four-seat page still gives it to white, who is not seated
    here, so the table names its own holder rather than inheriting one.
    """
    seats = _block(page, "seats")
    marked = re.findall(
        r'data-player="(\w+)" data-player-color="\w+"'
        r' data-first-player-marker="(\w+)"',
        seats,
    )

    assert MARKER_SEAT == SEATED_PLAYERS[0]
    assert marked == [(SEATED_PLAYERS[0], "true"), (SEATED_PLAYERS[1], "false")]
    # And the card itself is drawn on that board, once.
    assert seats.count(">First player</text>") == 1
    assert seats.index(">First player</text>") < seats.index(f'data-player="{SEATED_PLAYERS[1]}"')


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
    assert "--row-height: max(" in page
    assert "--h-action: calc(" in page
    assert "var(--row-height) - var(--cube)" in page
    assert "- var(--gap)" in page
    assert ".p-action > svg { height: var(--h-action); width: auto; }" in page


def test_the_alms_table_and_the_piety_track_share_a_scale(scale) -> None:
    """Both draw the same player disc, so matching their units-per-pixel matches the discs.

    This is what `--w-alms` being a multiple of `--w-piety` buys, and it is the reason the alms
    table is not simply given the width of the seats underneath it.
    """
    content, _, cubes, solved = scale

    assert cubes["alms"] == pytest.approx(cubes["piety"])
    # same units per pixel, so the width ratio is just the ratio of the crops
    assert solved.alms_over_piety == pytest.approx(solved.crop["alms"][2] / solved.crop["piety"][2])
    assert content["alms"][2] < content["piety"][2], "narrower, so it is centred over the seats"


def test_the_duty_wheel_and_the_map_are_anchored_on_the_same_hexagon(scale) -> None:
    """Neither board draws a cube, so the shared board hexagon is what sizes them.

    The map's cube is derived so that at one cube size the two hexagons come out the same width.
    """
    _, hexes, cubes, solved = scale

    assert cubes["map"] / cubes["action"] == pytest.approx(hexes["map"][2] / hexes["action"][2])
    assert solved.mult["action"] == pytest.approx(solved.mult["map"], abs=0.5)


def test_a_building_slot_is_the_same_number_of_cubes_across_as_a_map_hex(scale) -> None:
    """Where the player board's slot size comes from, checked against the map it was taken from.

    A slot and a map hex are both flat-top hexagons measured from the centre out to a corner, so
    the two are the same size on screen exactly when they are the same number of cubes across.
    `BUILDING_SLOT_HEX_SIZE` is that number written out in the player board's own units; this is
    the arithmetic behind it, run against the real map layout rather than trusted.
    """
    _, _, cubes, _ = scale
    hex_in_cubes = load_map_layout()["hex_size"] / cubes["map"]

    assert BUILDING_SLOT_HEX_SIZE / cubes["player"] == pytest.approx(hex_in_cubes, rel=0.002)


def test_the_seats_are_wider_than_they_are_tall(scale) -> None:
    """The seats got wider, and the table gave them the room rather than shrinking them to fit.

    A seat's width is solved from its shape, so a wider board is a wider seat -- there is no
    separate width for the table to have opinions about. The table may come out wider for it.
    """
    _, _, _, solved = scale
    crop = solved.crop["player"]

    assert crop[2] > crop[3]
    assert solved.width_cubes > SEAT_COLS * solved.player_k > 0


def test_two_seats_stack_to_the_height_of_the_duty_wheel(scale) -> None:
    """The seat block is solved to the duty wheel's own panel height, which is what pins the
    left column's height to the middle one's and lets both bottoms land on the map's."""
    _, _, _, solved = scale
    aspect = solved.crop["player"][3] / solved.crop["player"][2]

    board_width = solved.cube * solved.player_k + solved.player_c
    seats = SEAT_ROWS * (board_width * aspect + PANEL_CHROME) + (SEAT_ROWS - 1) * GAP_PX

    assert seats == pytest.approx(solved.cube * solved.duty_cubes + PANEL_CHROME)
    assert solved.left_cubes > solved.duty_cubes, "the alms table sits above the seats"


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


def test_page_carries_no_controls_or_state(page: str) -> None:
    """Layout only: the control-heavy sandbox is still game_setup.html."""
    assert "<button" not in page
    assert "<script" not in page
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
