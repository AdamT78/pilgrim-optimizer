import json
import math
import re
from collections import Counter
from pathlib import Path

import pytest

from tools.ui_debug.generate_duty_wheel import (
    default_output_path,
    generate_duty_wheel_page,
)
from tools.ui_debug.render_duty_wheel import (
    BOARD_CONFIG_PATH,
    CITY_STACK_HEIGHT,
    CITY_TALLY_OFFSET_Y,
    CUBE_CELL_HEIGHT,
    CUBE_SIZE,
    LABEL_OFFSET_Y,
    ORNAMENT_INSET,
    RING_ARROW_COUNT,
    SPACE_RADIUS,
    TALLY_OFFSET_Y,
    TILE_STACK_HEIGHT,
    TURN_CONTROL_DISABLED_OPACITY,
    board_edges,
    board_position_of,
    board_positions,
    branching_positions,
    default_layout_path,
    dummy_acolytes,
    duties_of,
    duty_position_by_id,
    duty_setups,
    duty_wheel_readout,
    load_duty_wheel_layout,
    merchant_path,
    next_merchant_position,
    players_for_count,
    render_duty_wheel_controls_html,
    render_duty_wheel_controls_script,
    render_duty_wheel_html,
    render_duty_wheel_panel,
    render_duty_wheel_svg,
    ring_arrow_ends,
    ring_duties,
    tally_columns,
    tally_pieces,
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
DUMMY_BLACK = "#1F1F1F"
MERCHANT_PURPLE = "#8E63D7"
ALLOWED_DRIFT = 0.1

# The engine's nine positions, in its own order, written out here rather than read from the
# renderer so that the file both are checked against has something to be checked against.
BOARD_POSITIONS = [
    "city",
    "north",
    "north_east",
    "east",
    "south_east",
    "south",
    "south_west",
    "west",
    "north_west",
]


def layout() -> dict:
    return load_duty_wheel_layout()


def generated_svg() -> str:
    return render_duty_wheel_svg(layout())


def interactive_html() -> str:
    return render_duty_wheel_html(layout(), interactive=True)


def baseline_svg() -> str:
    content = PROTOTYPE_SVG.read_text(encoding="utf-8")
    return content[content.index("<svg") :]


def _tally_of(markup: str, position: str, count: int | None = None) -> str:
    """One space's cube tally: the group drawn for a player count, or the only one a plain board
    draws."""
    opening = f'data-cube-tally="{position}"'
    if count is not None:
        opening += f' data-player-count="{count}"'
    start = markup.index(opening)
    return markup[start : markup.index("</g>", start)]


def _boxes(tally: str, standing_only: bool = False) -> list[tuple[float, float]]:
    """Where each of a tally's cubes is drawn, optionally only the ones standing."""
    return [
        (float(rect["x"]), float(rect["y"]))
        for rect in re.finditer(r'<rect x="(?P<x>[\d.]+)" y="(?P<y>[\d.]+)"[^>]*?/>', tally)
        if not (standing_only and 'opacity="0"' in rect.group(0))
    ]


def _cubes(tally: str) -> list[tuple[str, str | None]]:
    """Every cube a tally draws: whose it is, and what it is showing where that is said at all."""
    return [
        (found["player"], found["opacity"])
        for found in re.finditer(
            r'data-player="(?P<player>\w+)"(?:[^/>]*?opacity="(?P<opacity>\d)")?', tally
        )
    ]


def turn_control_overlay(markup: str) -> str:
    """The turn-control group, from its opening tag to the end of the SVG it is drawn last in."""
    start = markup.index('<g data-component="duty-wheel-turn-controls"')
    return markup[start : markup.index("</svg>", start)]


def turn_control_plaques(markup: str) -> list[tuple[float, float, float, float]]:
    """Every plaque the shell draws, as x, y, width, height, without the cube on the counter."""
    rects = re.findall(
        r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)" rx=',
        turn_control_overlay(markup),
    )
    return [tuple(float(value) for value in rect) for rect in rects]


def rect_corners(rect: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    x, y, width, height = rect
    return [(x, y), (x + width, y), (x, y + height), (x + width, y + height)]


def hexagon_corners(data: dict) -> list[tuple[float, float]]:
    """The green hexagon's six points in the SVG's own units, scaling included.

    The board is drawn inside a group the renderer scales about the board's centre, so a point at
    `p` in the group's units lands at centre + (p - centre) * scale on the canvas.
    """
    board = data["board"]
    scale = board["scale"]
    cx, cy = board["center"]
    points = [
        tuple(float(value) for value in pair.split(","))
        for pair in re.findall(r"(-?[\d.]+,-?[\d.]+)", board["ground_path"])
    ]
    return [(cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in points]


def inside_polygon(polygon: list[tuple[float, float]], point: tuple[float, float]) -> bool:
    """Whether a point falls inside a convex polygon, edges counting as inside."""
    turns = [
        (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
        for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True)
    ]
    return all(turn >= 0 for turn in turns) or all(turn <= 0 for turn in turns)


def _is_cube(tag: str, body: str) -> bool:
    """A cube is the only rect the board draws at a cube's size, on either side of the compare."""
    if tag != "rect":
        return False
    width = re.search(r'width="([\d.]+)"', body)
    return width is not None and float(width.group(1)) == CUBE_SIZE


def _is_rule(body: str) -> bool:
    """The baseline rule the cubes stand on, which the tally draws with the columns."""
    return 'stroke-opacity="0.55"' in body


def drawing_elements(svg: str, without_cubes: bool = False) -> list[tuple[str, tuple[float, ...]]]:
    """Every drawn element as its tag plus the numbers in its attributes, in document order.

    `without_cubes` drops the tally — the cubes and the baseline rule under them — which is the
    part of the board this renderer no longer draws the way the prototype did.
    """
    flat = re.sub(r"\s+", " ", svg)
    elements = [
        (match.group(1), match.group(2))
        for match in re.finditer(r"<(path|rect|circle|line|ellipse|text)\b([^>]*)>", flat)
    ]
    if without_cubes:
        elements = [
            (tag, body) for tag, body in elements if not _is_cube(tag, body) and not _is_rule(body)
        ]
    return [
        (tag, tuple(float(number) for number in re.findall(r"-?\d+\.?\d*", body)))
        for tag, body in elements
    ]


def cube_rects(svg: str) -> list[str]:
    """Every cube standing on the board, in document order."""
    flat = re.sub(r"\s+", " ", svg)
    return [
        match.group(0)
        for match in re.finditer(r"<rect\b([^>]*)>", flat)
        if _is_cube("rect", match.group(1))
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
    # Two is the view the board opens on: two seats and the neutrals they play against.
    assert data["default_player_count"] == 2


def test_players_for_count_seats_the_colours_the_layout_sits_at_each_table() -> None:
    """Which colours sit down is the layout's to say, not simply the first few in the list."""
    data = layout()
    seated = {count: players_for_count(data, count) for count in data["player_counts"]}

    assert [player["color"] for player in seated[2]] == ["red", "blue"]
    assert [player["color"] for player in seated[3]] == ["white", "red", "blue"]
    assert [player["color"] for player in seated[4]] == ["white", "red", "yellow", "blue"]
    assert [player["id"] for player in seated[4]] == list(PLAYER_SEATS)
    # Every roster is a subset of the four seats, kept in the order the layout names them.
    for count, players in seated.items():
        ids = [player["id"] for player in players]
        assert len(ids) == count
        assert ids == [seat for seat in PLAYER_SEATS if seat in set(ids)]


def test_the_neutral_column_joins_the_reduced_tables_only() -> None:
    """Dummy acolytes are seeded for two- and three-player tables; a full table has none."""
    data = layout()

    assert dummy_acolytes(data, 2)["color"] == "black"
    assert dummy_acolytes(data, 3)["color"] == "black"
    assert dummy_acolytes(data, 4) is None
    assert dummy_acolytes(data, 2)["id"] not in {player["id"] for player in data["players"]}


def test_a_duty_tile_carries_the_neutral_column_and_the_city_does_not() -> None:
    """Dummies are seeded and moved on the duty ring, and the City is not on that ring."""
    data = layout()
    tile = duty_position_by_id(data, "produce")
    city = duty_position_by_id(data, data["city_id"])

    assert [piece["color"] for piece in tally_pieces(data, tile, 2)] == ["red", "blue", "black"]
    assert [piece["color"] for piece in tally_pieces(data, city, 2)] == ["red", "blue"]
    # A full table seats no neutrals, so the tile and the City agree again.
    assert [piece["color"] for piece in tally_pieces(data, tile, 4)] == list(PLAYER_COLOURS)
    assert [piece["color"] for piece in tally_pieces(data, city, 4)] == list(PLAYER_COLOURS)


def test_the_neutrals_are_seeded_where_the_dummy_acolyte_rules_seed_them() -> None:
    """Two groups of three, clockwise from the top and from the bottom, and two of two at three
    players. Sample debug state, but taken from `docs/rules/DummyAcolytes.md` rather than invented.
    """
    seeded = layout()["dummy_acolytes"]["sample_cubes"]

    assert set(seeded["2"]) == {"produce", "allocation", "clerical"} | {
        "taxation",
        "ordination",
        "construct",
    }
    assert set(seeded["3"]) == {"produce", "allocation", "taxation", "ordination"}
    assert set(seeded["2"].values()) == {1}
    assert set(seeded["3"].values()) == {1}


def test_players_for_count_refuses_a_count_the_layout_does_not_offer() -> None:
    data = layout()

    for count in (1, 5):
        with pytest.raises(ValueError):
            players_for_count(data, count)


def test_every_player_count_centres_its_cube_columns_on_the_space() -> None:
    data = layout()
    for space_id in ("produce", data["city_id"]):
        duty = duty_position_by_id(data, space_id)
        center_x = duty["center"][0]

        for count in data["player_counts"]:
            columns = tally_columns(data, duty, count)
            pieces = tally_pieces(data, duty, count)
            middles = [column["center_x"] for column in columns]
            assert [column["player"] for column in columns] == [piece["id"] for piece in pieces]
            # The columns sit symmetrically about the space, so a shorter table stays in the middle.
            assert round(sum(middles) / len(middles), 6) == center_x
            assert round(middles[0] + middles[-1], 6) == round(2 * center_x, 6)


def test_a_duty_tile_shows_three_columns_at_the_table_the_board_opens_on() -> None:
    data = layout()
    tile = duty_position_by_id(data, "produce")
    city = duty_position_by_id(data, data["city_id"])
    opening = data["default_player_count"]

    assert len(tally_columns(data, tile, opening)) == 3
    assert len(tally_columns(data, city, opening)) == 2


def test_dropping_seats_narrows_the_tally_from_both_sides() -> None:
    """Counted in columns rather than seats: at two and three players the neutrals take one."""
    data = layout()
    duty = duty_position_by_id(data, "produce")
    widths = {count: len(tally_columns(data, duty, count)) for count in data["player_counts"]}
    spans = {
        count: (
            tally_columns(data, duty, count)[0]["center_x"],
            tally_columns(data, duty, count)[-1]["center_x"],
        )
        for count in data["player_counts"]
    }

    assert widths == {2: 3, 3: 4, 4: 4}
    assert spans[2][0] > spans[3][0]
    assert spans[2][1] < spans[3][1]
    assert spans[3] == spans[4]


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


def test_rendered_svg_tallies_cubes_in_the_colours_the_opening_table_seats() -> None:
    data = layout()
    svg = generated_svg()
    seated = {player["id"] for player in players_for_count(data, data["default_player_count"])}

    for seat, fill in PLAYER_FILLS.items():
        if seat in seated:
            assert f'fill="{fill}"' in svg
            assert f'data-player="{seat}"' in svg
        else:
            assert f'data-player="{seat}"' not in svg
    assert f'fill="{DUMMY_BLACK}"' in svg
    # Drawn plain, all nine spaces carry the one tally the board opens on.
    assert len(re.findall(r'data-cube-tally="', svg)) == 9
    assert len(re.findall(r'data-player-count="2"', svg)) == 9
    assert 'data-player-count="4"' not in svg


def test_the_city_stands_below_its_title_with_room_for_a_full_column() -> None:
    """The space is measured for what a column can hold, not for what is standing in it."""
    data = layout()
    city = duty_position_by_id(data, data["city_id"])
    svg = generated_svg()
    tally = svg[svg.index('data-cube-tally="city"') :]
    cubes = re.findall(r'<rect [^>]*data-player="(\w+)"', tally[: tally.index("</g>")])
    opening = int(data["city_sample_cubes_per_seat"])
    _, cy = city["center"]

    # Drawn plain, a column is the cubes standing in it and no more.
    assert opening < CITY_STACK_HEIGHT
    assert Counter(cubes) == {"player_two": opening, "player_four": opening}
    # It stands lower than a duty tile's, with the room under the title shared evenly around it.
    assert CITY_TALLY_OFFSET_Y > TALLY_OFFSET_Y
    title = cy + LABEL_OFFSET_Y
    inset_bottom = cy + SPACE_RADIUS - ORNAMENT_INSET
    top = cy + CITY_TALLY_OFFSET_Y - CITY_STACK_HEIGHT * CUBE_CELL_HEIGHT
    assert top - title == pytest.approx(inset_bottom - (cy + CITY_TALLY_OFFSET_Y))


def test_the_city_holds_six_cubes_a_seat_and_opens_holding_two() -> None:
    """Room for six, two standing in it: the four left over are what a page can fill.

    The cubes are the size and the pitch they have everywhere else on the wheel -- what changed to
    make room is where the column stands, not how big the cubes in it are.
    """
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    tally = svg[svg.index('data-cube-tally="city" data-player-count="2"') :]
    two_player = tally[: tally.index("</g>")]
    drawn = re.findall(
        r'data-city-column-player="(\w+)" data-city-cube="(\d)" opacity="(\d)"', two_player
    )
    standing = [player for player, _, opacity in drawn if opacity == "1"]

    assert CITY_STACK_HEIGHT == 6
    assert int(data["city_sample_cubes_per_seat"]) == 2
    assert f'data-city-capacity="{CITY_STACK_HEIGHT}"' in two_player
    # Every space in the column is drawn, numbered from the baseline up, and the first two of each
    # are the ones standing.
    assert Counter(player for player, _, _ in drawn) == {
        "player_two": CITY_STACK_HEIGHT,
        "player_four": CITY_STACK_HEIGHT,
    }
    for column in ("player_two", "player_four"):
        indices = [index for player, index, _ in drawn if player == column]
        assert indices == [str(index) for index in range(CITY_STACK_HEIGHT)]
    assert Counter(standing) == {"player_two": 2, "player_four": 2}

    # Same cube and same pitch as everywhere else on the wheel: the column found its room by
    # standing lower, not by drawing anything smaller or closer together.
    boxes = re.findall(r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)"', two_player)
    assert {width for _, _, width in boxes} == {f"{CUBE_SIZE:g}"}
    column = sorted(float(y) for x, y, _ in boxes if x == boxes[0][0])
    assert [b - a for a, b in zip(column, column[1:], strict=False)] == [
        pytest.approx(CUBE_CELL_HEIGHT)
    ] * (CITY_STACK_HEIGHT - 1)


def test_a_tile_draws_the_three_cubes_it_has_room_for_and_stands_what_it_stood_before() -> None:
    """The room a tile has, not what is on it: the empty slots are where a sown cube can arrive.

    Three is what fits between the baseline the cubes have always stood on and the title above
    them -- a fourth would be drawn across the words, and the Tithe capsule has the space below --
    so a column is drawn out to its room and no further. The cubes are the size and the pitch they
    are everywhere else on the wheel; the only new thing is the slots nothing is standing in.
    """
    data = layout()
    slotted = _tally_of(render_duty_wheel_svg(data, interactive=True), "produce", count=4)

    assert TILE_STACK_HEIGHT == 3
    assert Counter(player for player, _ in _cubes(slotted)) == {
        player: TILE_STACK_HEIGHT for player in PLAYER_FILLS
    }
    # A tile is not a City column, and keeps the City's hooks off it.
    assert "data-city-cube" not in slotted
    assert "data-city-capacity" not in slotted

    # Nothing that was showing before there were slots to hide has changed: the same seats stand
    # the same cubes, in the same boxes, at the same pitch.
    plain = _tally_of(generated_svg(), "produce")
    seated = _tally_of(render_duty_wheel_svg(data, interactive=True), "produce", count=2)
    assert Counter(player for player, showing in _cubes(seated) if showing != "0") == Counter(
        player for player, _ in _cubes(plain)
    )
    assert _boxes(seated, standing_only=True) == _boxes(plain)
    assert set(re.findall(r'<rect [^>]*?width="([\d.]+)"', slotted)) == {f"{CUBE_SIZE:g}"}
    column = sorted(y for x, y in _boxes(slotted) if x == _boxes(slotted)[0][0])
    assert [b - a for a, b in zip(column, column[1:], strict=False)] == [
        pytest.approx(CUBE_CELL_HEIGHT)
    ] * (TILE_STACK_HEIGHT - 1)


def test_a_column_is_only_given_room_where_a_cube_could_arrive() -> None:
    """The neutral column gets none: no seat plays those cubes, so none will ever be put there.

    Nor does a board that is only being looked at. Drawing the empty slots is what makes a board
    clickable -- a page stands a cube on a space by turning one on, rather than by drawing into the
    wheel -- and a page with no clicks in it has nothing to turn on.
    """
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    dummy = data["dummy_acolytes"]["id"]

    for position, standing in data["dummy_acolytes"]["sample_cubes"]["2"].items():
        drawn = [
            showing
            for player, showing in _cubes(_tally_of(svg, position, count=2))
            if player == dummy
        ]
        assert drawn == [None] * standing, position
    # And a plain board draws no empty slot at all, tile or City: every cube on it is standing.
    plain = generated_svg()
    for position in [data["city_id"], *data["clockwise_order"]]:
        showing = [showing for _, showing in _cubes(_tally_of(plain, position))]
        assert showing and set(showing) == {None}, position
    assert "data-city-cube" not in plain


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
    tallies = re.findall(
        r'data-cube-tally="(\w+)" data-player-count="(\d)"[^>]*? opacity="(\d)"', svg
    )
    shown = [(duty, count) for duty, count, opacity in tallies if opacity == "1"]
    spaces = [data["city_id"], *data["clockwise_order"]]

    assert len(tallies) == len(spaces) * len(data["player_counts"])
    # Every space offers all three views, the City included, and opens on the two-player one.
    assert shown == [(space, "2") for space in spaces]


def test_interactive_board_only_draws_the_seats_a_player_count_seats() -> None:
    data = layout()
    svg = render_duty_wheel_svg(data, interactive=True)
    produce = svg[svg.index('data-cube-tally="produce" data-player-count="2"') :]
    two_player = produce[: produce.index("</g>")]

    assert 'data-player="player_two"' in two_player
    assert 'data-player="player_four"' in two_player
    assert 'data-player="player_one"' not in two_player
    assert 'data-player="player_three"' not in two_player
    # And the neutrals stand beside them, on the duty tile but not in the City.
    assert 'data-player="dummy"' in two_player
    city = svg[svg.index('data-cube-tally="city" data-player-count="2"') :]
    assert 'data-player="dummy"' not in city[: city.index("</g>")]


def test_interactive_page_offers_all_three_debug_controls() -> None:
    html = interactive_html()

    assert "Randomize Duty tiles" in html
    assert "Move Merchant" in html
    # Every hook is prefixed, so the setup view can host the panel without a name clash.
    assert 'id="duty-wheel-randomize"' in html
    assert 'id="duty-wheel-move-merchant"' in html
    assert "Setup 1 of 3 — Merchant on Taxation — 2 players" in html
    assert duty_wheel_readout(layout()) == "Setup 1 of 3 — Merchant on Taxation — 2 players"


def test_interactive_page_offers_a_button_per_player_count_with_two_selected() -> None:
    html = interactive_html()
    pattern = r'<button type="button" data-player-count="(\d)" aria-pressed="(\w+)">(\dp)</button>'
    buttons = re.findall(pattern, html)

    assert [label for _, _, label in buttons] == ["2p", "3p", "4p"]
    assert [count for count, _, _ in buttons] == ["2", "3", "4"]
    assert [count for count, pressed, _ in buttons if pressed == "true"] == ["2"]


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


def test_panel_hands_a_host_page_the_controls_and_the_board() -> None:
    data = layout()
    panel = render_duty_wheel_panel(data)

    assert panel.index("Randomize Duty tiles") < panel.index("<svg")
    assert "Move Merchant" in panel
    assert 'data-component="duty-wheel"' in panel
    # A fragment, not a page: the host brings its own document, heading, and scripts.
    assert "<!DOCTYPE html>" not in panel
    assert "<body" not in panel
    assert "<script>" not in panel


def test_panel_without_controls_is_the_fixed_picture() -> None:
    data = layout()
    panel = render_duty_wheel_panel(data, include_controls=False)

    assert "Randomize Duty tiles" not in panel
    assert "<button" not in panel
    assert panel == render_duty_wheel_svg(data)


def test_panel_control_hooks_are_all_prefixed() -> None:
    data = layout()
    controls = render_duty_wheel_controls_html(data)
    script = render_duty_wheel_controls_script(data)

    for hook in re.findall(r'(?:id|class)="([\w -]+)"', controls):
        for name in hook.split():
            assert name.startswith("duty-wheel-"), name
    # The script reaches for those hooks and the board, and nothing else on the host page.
    assert "duty-wheel-randomize" in script
    assert "duty-wheel-move-merchant" in script
    assert "duty-wheel-counts" in script
    assert script.lstrip().startswith("<script>\n(function ()")


def test_plain_page_has_no_controls() -> None:
    html = render_duty_wheel_html(layout())

    assert "Randomize Duty tiles" not in html
    assert "<button" not in html
    assert "<script>" not in html
    assert "<svg" in html


def test_the_board_the_wheel_is_drawn_from_is_the_board_the_engine_plays_on() -> None:
    """Read, not copied: `configs/board.json` is the engine's file, and the wheel loads it."""
    board = json.loads((REPO_ROOT / "configs" / "board.json").read_text(encoding="utf-8"))

    assert BOARD_CONFIG_PATH == REPO_ROOT / "configs" / "board.json"
    assert board_positions() == BOARD_POSITIONS == board["positions"]
    assert board_edges() == board["edges"]


def test_every_space_stands_at_a_board_position_the_engine_knows() -> None:
    """The nine positions of `configs/board.json`, each on the space that is drawn where it is.

    The wheel's own ids are the prototype's default arrangement of the tiles, so `clerical` names
    the space Clerical happened to start on rather than anything about the board. Movement is in
    positions, and the two vocabularies are kept side by side rather than one being made to stand
    in for the other.
    """
    svg = generated_svg()
    spaces = re.findall(
        r'<g data-duty="(\w+)"[^>]*? data-board-position="(\w+)"'
        r' data-board-position-index="(\d)" data-duty-category="(\w+)"',
        svg,
    )

    assert [position for _, position, _, _ in spaces] == BOARD_POSITIONS
    assert [int(index) for _, _, index, _ in spaces] == list(range(len(BOARD_POSITIONS)))
    # A space opens holding the tile it is named after; turning the tiles is what parts them.
    assert [duty for duty, _, _, _ in spaces] == [category for _, _, _, category in spaces]
    assert {duty for duty, _, _, _ in spaces} == {layout()["city_id"], *layout()["clockwise_order"]}


def test_a_space_stands_at_the_compass_point_it_is_drawn_at() -> None:
    """Which is what makes the pairing a fact about the board rather than a decision about it.

    The layout carries the pairing so it can be read; this holds it to the drawing. Take the
    bearing of each space from the middle of the board, round it to the nearest eighth of a turn,
    and the position it is paired with is the one it is standing on.
    """
    data = layout()
    cx, cy = data["board"]["center"]
    ring = [position for position in BOARD_POSITIONS if position != "city"]

    for duty in duties_of(data):
        if duty["id"] == data["city_id"]:
            # The middle space is the middle position, and it is the only one off the ring.
            assert board_position_of(duty) == "city"
            assert math.dist(duty["center"], (cx, cy)) < SPACE_RADIUS
            continue
        x, y = duty["center"]
        bearing = (math.degrees(math.atan2(x - cx, cy - y)) + 360) % 360
        assert board_position_of(duty) == ring[round(bearing / 45) % 8], duty["id"]


def test_the_arrows_drawn_on_the_board_are_the_moves_the_engine_allows() -> None:
    """Edge for edge, the same directed graph -- which is the whole point of this renderer.

    The ring arrows are one shape turned around the board, so nothing in the markup said which
    pair each stood between; it is worked out from how far each has been turned and then named in
    the engine's terms. Kogge and Cloisters add and drop edges of their own; neither is drawn here.
    """
    svg = generated_svg()
    drawn: dict[str, set[str]] = {}
    for origin, target in re.findall(
        r'data-from-position="(\w+)" data-to-position="(\w+)"', svg
    ):
        drawn.setdefault(origin, set()).add(target)

    assert drawn == {position: set(ways) for position, ways in board_edges().items()}
    assert sum(len(ways) for ways in drawn.values()) == len(
        re.findall(r"data-from-position=", svg)
    )


def test_an_arrow_carries_the_numbers_the_rules_move_cubes_by() -> None:
    """Names read, indexes travel: the engine passes positions around as their board index."""
    svg = generated_svg()
    indexed = re.findall(
        r'data-from-position="(\w+)" data-to-position="(\w+)"'
        r' data-from-position-index="(\d)" data-to-position-index="(\d)"',
        svg,
    )

    assert len(indexed) == RING_ARROW_COUNT + len(layout()["middle_arrows"])
    for origin, target, origin_index, target_index in indexed:
        assert BOARD_POSITIONS[int(origin_index)] == origin
        assert BOARD_POSITIONS[int(target_index)] == target
    # And the ring arrows still say what they say by where they were turned to.
    assert [ring_arrow_ends(layout(), index) for index in range(RING_ARROW_COUNT)] == [
        (origin, target)
        for origin, target in re.findall(
            r'data-ring-arrow="\d" data-from-position="(\w+)" data-to-position="(\w+)"', svg
        )
    ]


def test_only_three_positions_have_more_than_one_way_out_of_them() -> None:
    """Which is the whole of the branching on this board, and nobody had to write it down.

    A position with one arrow leaving it offers no choice at all. The City, east and west each
    have two, and they are the three a turn has to stop and ask about -- whatever duty tiles
    happen to be lying on them at the time.
    """
    svg = generated_svg()
    drawn: dict[str, set[str]] = {}
    for origin, target in re.findall(
        r'data-from-position="(\w+)" data-to-position="(\w+)"', svg
    ):
        drawn.setdefault(origin, set()).add(target)

    assert branching_positions() == ["city", "east", "west"]
    assert sorted(position for position, ways in drawn.items() if len(ways) > 1) == [
        "city",
        "east",
        "west",
    ]
    assert {position: sorted(drawn[position]) for position in branching_positions()} == {
        "city": ["north", "south"],
        "east": ["city", "south_east"],
        "west": ["city", "north_west"],
    }
    # And every position leads somewhere, so no start space is a dead end.
    assert set(drawn) == set(BOARD_POSITIONS)


def test_the_tiles_are_still_the_ones_the_board_has_always_shown() -> None:
    """The new vocabulary is added beside the old one rather than in place of it."""
    svg = generated_svg()
    data = layout()

    assert dict(re.findall(r'data-duty-label="(\w+)">([^<]+)</text>', svg)) == {
        duty["id"]: duty["label"] for duty in duties_of(data)
    }
    for duty in duties_of(data):
        assert f'data-duty="{duty["id"]}"' in svg
    assert re.findall(r'data-duty-ring-index="(\d)"', interactive_html()) == [
        str(index) for index in range(len(data["clockwise_order"]))
    ]


def test_the_corners_stay_empty_until_a_page_asks_for_the_turn_controls() -> None:
    """A page that was not designed around the shell does not quietly grow one."""
    data = layout()

    assert "duty-wheel-turn-controls" not in render_duty_wheel_svg(data)
    assert "duty-wheel-turn-controls" not in render_duty_wheel_svg(data, interactive=True)
    assert "duty-wheel-turn-controls" not in render_duty_wheel_panel(data)
    assert "duty-wheel-turn-controls" not in render_duty_wheel_html(data, interactive=True)
    # The generated page is one of the two that does ask.
    assert "duty-wheel-turn-controls" in render_duty_wheel_html(
        data, interactive=True, turn_controls=True
    )


def test_the_shell_names_every_control_a_turn_will_be_driven_from() -> None:
    """The whole turn is on the board: sow it, see what is in hand, and the four ways it ends."""
    overlay = turn_control_overlay(render_duty_wheel_svg(layout(), turn_controls=True))
    controls = re.findall(r'data-turn-control="(\w+)"', overlay)
    labels = re.findall(r"<text[^>]*>([^<]+)</text>", overlay)

    assert 'data-turn-state="idle"' in overlay
    assert controls == ["sow", "reset", "confirm", "action", "tithe"]
    assert labels == ["Sow", "\u00d7 0", "Reset", "Confirm", "Action", "Tithe"]
    # The counter is a readout rather than a button, so it takes no control name of its own.
    assert 'data-turn-counter="cubes-in-hand"' in overlay
    assert 'data-turn-counter-value="0"' in overlay


def test_nothing_but_sow_can_be_reached_before_a_turn_has_started() -> None:
    """Dimmed rather than dropped, so the corners keep their shape as a turn moves through them."""
    overlay = turn_control_overlay(render_duty_wheel_svg(layout(), turn_controls=True))
    dimmed = re.findall(r'data-turn-control="(\w+)" data-turn-control-enabled="(\w+)"', overlay)

    assert dimmed == [
        ("sow", "true"),
        ("reset", "false"),
        ("confirm", "false"),
        ("action", "false"),
        ("tithe", "false"),
    ]
    assert overlay.count('aria-disabled="true"') == 4
    assert overlay.count(f'opacity="{TURN_CONTROL_DISABLED_OPACITY}"') == 4
    assert 'data-turn-control="sow" data-turn-control-enabled="true" role="button"' in overlay


def test_the_shell_is_a_picture_of_a_turn_and_none_of_its_behaviour() -> None:
    """This PR asks whether the controls fit, not what they do."""
    html = render_duty_wheel_html(layout(), interactive=True, turn_controls=True)
    overlay = turn_control_overlay(html)

    assert "onclick" not in overlay
    assert "<button" not in overlay
    for word in ("sow(", "GameState", "legal_actions", "addEventListener"):
        assert word not in overlay
    # Nothing on the page reaches for the shell either: there is no turn flow to drive yet.
    assert "data-turn-control" not in html[html.index("<script>") :]


def test_the_plaques_stand_in_the_black_the_hexagon_leaves_in_its_corners() -> None:
    """The one part of the canvas nothing else uses, and the part the game table crops to.

    A plaque that strayed onto the green would cover a duty tile, an arrow or a tally; one that
    strayed outside the hexagon's own box would be cut off the side of the board on the table.
    """
    data = layout()
    plaques = turn_control_plaques(render_duty_wheel_svg(data, turn_controls=True))
    green = hexagon_corners(data)
    box = (
        min(x for x, _ in green),
        min(y for _, y in green),
        max(x for x, _ in green),
        max(y for _, y in green),
    )

    assert len(plaques) == 5 + 1
    for corner in [point for plaque in plaques for point in rect_corners(plaque)]:
        assert not inside_polygon(green, corner), corner
        assert box[0] <= corner[0] <= box[2], corner
        assert box[1] <= corner[1] <= box[3], corner
    # And they hang off the four corners of it evenly, rather than drifting toward one side.
    insets = (
        min(x for x, _, _, _ in plaques) - box[0],
        box[2] - max(x + width for x, _, width, _ in plaques),
        min(y for _, y, _, _ in plaques) - box[1],
        box[3] - max(y + height for _, y, _, height in plaques),
    )
    assert insets[0] == pytest.approx(insets[1], abs=1.0)
    assert insets[2] == pytest.approx(insets[3], abs=1.0)
    assert all(inset > 0 for inset in insets)


def test_the_shell_is_drawn_on_the_board_rather_than_beside_it() -> None:
    """It has to travel with the wheel: the game table sizes the wheel by its SVG and crops it."""
    html = render_duty_wheel_html(layout(), interactive=True, turn_controls=True)
    board = html[html.index("<svg") : html.index("</svg>")]

    assert "duty-wheel-turn-controls" in board
    assert html.count("duty-wheel-turn-controls") == 1
    # Drawn after the board group closes, so the plaques sit above the board in root units and
    # take none of the scaling the spaces are drawn under.
    svg = render_duty_wheel_svg(layout(), turn_controls=True)
    assert svg.index("</g>") < svg.index("duty-wheel-turn-controls")
    assert svg.rindex("</g>") < svg.rindex("</svg>")


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


def test_the_board_around_the_cubes_is_still_the_baseline_element_for_element() -> None:
    """Coarse parity, with the cubes taken out of both sides.

    Asked for the board the prototype drew — static, Merchant on Produce — the renderer reproduces
    everything the tally does not touch: the spaces, the arrows, the capsules, the titles and the
    ornaments, the same shapes at the same coordinates in the same order. The one tolerated gap is
    the Allocation title, which the baseline puts 0.1px above the offset its other eight titles
    share; the renderer uses the shared offset instead.
    """
    data = layout()
    generated = drawing_elements(
        render_duty_wheel_svg(data, merchant_on=data["merchant_token"]["baseline_position"]),
        without_cubes=True,
    )
    baseline = drawing_elements(baseline_svg(), without_cubes=True)

    assert len(generated) == len(baseline)
    for mine, theirs in zip(generated, baseline, strict=True):
        assert mine[0] == theirs[0]
        assert len(mine[1]) == len(theirs[1])
        for value, expected in zip(mine[1], theirs[1], strict=True):
            assert abs(round(value - expected, 6)) <= ALLOWED_DRIFT


def test_the_cubes_are_what_moved_away_from_the_baseline() -> None:
    """The baseline stands four seats on each duty tile and nothing in the City; this board stands
    two seats and the neutrals they play against, and gives the City a holding of its own.
    """
    data = layout()
    generated = render_duty_wheel_svg(data, merchant_on=data["merchant_token"]["baseline_position"])

    assert len(cube_rects(generated)) != len(cube_rects(baseline_svg()))
    assert cube_rects(generated) != cube_rects(baseline_svg())
    # The baseline draws every one of the four seats; this board draws the two that sit down.
    assert PLAYER_FILLS["player_three"] in baseline_svg()
    assert PLAYER_FILLS["player_three"] not in generated
    assert DUMMY_BLACK not in baseline_svg()


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
