"""The play view, and the line between the engine and the drawing of it.

The tests that matter most here are the ones that would fail if a value were baked in rather than
mapped. A page that looks right for one scenario proves nothing: the layout JSON's sample position
is a plausible position, so every check below either uses a fixture whose values differ from the
sample or renders two scenarios and holds them against each other.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from tools.ui_debug.play_view_adapter import (
    acolytes_by_position,
    dummy_acolytes_by_position,
    duty_by_position_name,
    player_record,
    resources_for,
    seated_player_ids,
    state_header,
    timeline_slots,
    tithe_by_position_name,
)
from tools.ui_debug.render_buildings import load_building_catalog
from tools.ui_debug.render_duty_wheel import load_duty_wheel_layout
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites
from tools.ui_debug.render_play_view import (
    duty_board_state_for,
    duty_layout_for,
    map_placements_for,
    piety_variant_for,
    render_play_view_from_payload,
    seat_of,
)

UI_DEBUG = Path(__file__).resolve().parents[1] / "tools" / "ui_debug"

CANONICAL = (
    "city",
    "north",
    "north_east",
    "east",
    "south_east",
    "south",
    "south_west",
    "west",
    "north_west",
)


def _player(mancala, *, wheat=1, stone=1, silver=1, alms=0, piety=0):
    return {
        "victory_points": 0,
        "piety": piety,
        "alms_position": alms,
        "trade_routes_count": 0,
        "resources": {"stone": stone, "silver": silver, "wheat": wheat},
        "workforce": {
            "mancala": list(mancala),
            "village": 3,
            "abbey": 2,
            "committed": {
                "roads": 0,
                "shrines": 0,
                "market_ports": 0,
                "pilgrimage_sites": 0,
                "alms_table": 0,
            },
        },
        "special_activities": {
            "fields": 0,
            "road_engineer": 0,
            "stone_mason": 0,
            "alms_house": 0,
            "engraver": 0,
            "vestry": 0,
        },
        "player_board_slots": {
            "active_buildings": [],
            "donated_buildings": [],
            "cardinal_favor_tiles": 0,
        },
    }


def _payload(players, *, duty=None, tithe=None, dummy=None, **state):
    """A payload by hand, with no engine anywhere near it.

    That the adapter can be exercised this way is the point of it taking a dict: an engine in the
    room would make every one of these tests a test of the engine as well.
    """
    duty = duty or {
        "north": "produce",
        "north_east": "allocation",
        "east": "clerical",
        "south_east": "build_roads",
        "south": "taxation",
        "south_west": "ordination",
        "west": "construct",
        "north_west": "give_alms",
    }
    tithe = tithe or dict.fromkeys(duty, "wheat") | {"south": None}
    base = {
        "active_player": "player_one",
        "start_player_id": "player_one",
        "phase": "setup_sow",
        "turn": 0,
        "timing": {
            "absolute_turn": 0,
            "round_number": 1,
            "season_number": 1,
            "turn_in_round": 0,
        },
        "setup": {
            "setup_sow_required": True,
            "setup_sow_complete": False,
            "setup_sow_completed_by": [],
        },
        "game_over": False,
        "table_player_count": len(players),
        "ship_position": 0,
        "completed_rounds": 0,
        "merchant_position": 0,
        "building_market": [],
        "building_availability": {},
        "pilgrimage_rounds": [],
        "dummy_acolytes": {
            "north_group": [0] * 9,
            "south_group": [0] * 9,
            "total": list(dummy or [0] * 9),
        },
        "players": players,
        "acolytes": [player["workforce"]["mancala"] for player in players],
    }
    base.update(state)
    return {
        "state": base,
        "board_positions": list(CANONICAL),
        "duty_tiles": [
            {
                "position": index,
                "position_name": name,
                "duty": duty[name],
                "tithe": tithe[name],
            }
            for index, name in enumerate(CANONICAL)
            if index != 0
        ],
    }


# ---------------------------------------------------------------------------------------------
# The line: nothing under tools/ui_debug may import the engine
# ---------------------------------------------------------------------------------------------


CONFIG_READER = "pilgrim.model.config"

# The three renderers that read a rules value out of the game's own config with the game's own
# parser, so a printed number cannot drift from the rule behind it. Pinned by name: the exception
# is defensible for exactly this and would stop being defensible the moment it grew.
CONFIG_READER_USERS = {
    "render_alms_table.py",
    "render_piety_track.py",
    "render_piety_track_v2.py",
}


def _engine_imports(module_path: Path) -> list[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return sorted(name for name in imported if name == "pilgrim" or name.startswith("pilgrim."))


@pytest.mark.parametrize("module_path", sorted(UI_DEBUG.rglob("*.py")), ids=lambda p: p.name)
def test_no_page_of_the_ui_reaches_for_the_engines_state_or_rules(module_path: Path) -> None:
    """The whole point of a dict crossing the seam is that only one side knows the engine.

    Asserted rather than agreed: an import added in passing is invisible in review and is the one
    change that would let a rule start living on the drawing side.

    `pilgrim.model.config` is the single exception, and it is not a hole in the seam: it parses
    the game's config FILES and touches no state, no action and no rule. The pinning test below
    keeps it to the three renderers that already have a reason for it.
    """
    offenders = [name for name in _engine_imports(module_path) if name != CONFIG_READER]
    assert offenders == [], f"{module_path.name} reaches into the engine: {offenders}"


def test_the_only_engine_import_the_ui_has_is_the_config_reader_and_only_where_it_was() -> None:
    """The exception does not spread. Anything new that wants it has to argue for it here first."""
    users = {path.name for path in UI_DEBUG.rglob("*.py") if CONFIG_READER in _engine_imports(path)}
    assert users == CONFIG_READER_USERS


def test_neither_the_adapter_nor_the_play_view_imports_the_engine_at_all() -> None:
    """The two files this PR adds on the drawing side take the rule without the exception."""
    for name in ("play_view_adapter.py", "render_play_view.py", "render_table_layout.py"):
        assert _engine_imports(UI_DEBUG / name) == []


# ---------------------------------------------------------------------------------------------
# Seating, which is not the players array's order
# ---------------------------------------------------------------------------------------------


def test_two_players_sit_at_the_two_ends_of_the_row_and_not_the_first_two_chairs() -> None:
    """The trap fact (c) names. Checked by colour, because index is what gets this wrong.

    A two-player game seats `player_one` and `player_two`. The boards layout makes `player_one`
    white and the table seats red first, so the pair on the table is white and red -- seats 4 and 1.
    Slicing the seating order to its first two would seat red and yellow and look entirely
    plausible while being the wrong two players.
    """
    payload = _payload([_player([5] + [0] * 8), _player([5] + [0] * 8)])
    seated = seated_player_ids(payload)
    assert seated == ["player_two", "player_one"]
    assert [seat_of(player_id) for player_id in seated] == [1, 4]

    boards = json.loads((UI_DEBUG / "player_boards_v2_layout.json").read_text(encoding="utf-8"))
    color = {player["id"]: player["color"] for player in boards["players"]}
    assert [color[player_id] for player_id in seated] == ["red", "white"]


def test_three_players_leave_the_blue_chair_empty() -> None:
    payload = _payload([_player([5] + [0] * 8) for _ in range(3)])
    assert seated_player_ids(payload) == ["player_two", "player_three", "player_one"]


def test_the_short_table_gets_the_board_that_is_actually_shorter() -> None:
    """The two-player piety track is a different board, not a narrower one: one row of discs."""
    assert piety_variant_for(["player_two", "player_one"]) == "2_player"
    assert piety_variant_for(["player_two", "player_three", "player_one"]) == "3_4_player"


# ---------------------------------------------------------------------------------------------
# The four facts the adapter must not rediscover
# ---------------------------------------------------------------------------------------------


def test_a_seats_acolytes_are_read_at_the_index_the_board_already_uses() -> None:
    """Fact (a): the mancala index IS the UI board position index, so there is no lookup.

    The vector below is deliberately all different, so an off-by-one or a reversal shows up rather
    than hiding behind a row of equal numbers.
    """
    payload = _payload([_player([1, 2, 3, 4, 5, 6, 7, 8, 9])])
    assert acolytes_by_position(payload, "player_one") == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_the_adapter_carries_no_translation_table_between_the_two_namings() -> None:
    """The agreement in fact (a) holds already; a copy of it here could only go stale."""
    source = (UI_DEBUG / "play_view_adapter.py").read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]
    assert "north_east" not in body
    assert "south_west" not in body


def test_the_wheel_is_drawn_from_the_scenario_and_not_from_its_own_default() -> None:
    """Fact (b): the arrangement is config, so it arrives in the payload or the wheel is a guess."""
    shuffled = {
        "north": "taxation",
        "north_east": "give_alms",
        "east": "produce",
        "south_east": "construct",
        "south": "build_roads",
        "south_west": "clerical",
        "west": "allocation",
        "north_west": "ordination",
    }
    payload = _payload([_player([5] + [0] * 8)], duty=shuffled, tithe=dict.fromkeys(shuffled, None))
    tiles = duty_layout_for(payload, load_duty_wheel_layout())["duties"]
    drawn = {tile["board_position"]: tile["id"] for tile in tiles if tile["id"] != "city"}
    assert drawn == shuffled


def test_a_tile_takes_its_name_with_it_and_leaves_the_counter_on_the_space() -> None:
    """The counter is dealt onto a position after the tiles are shuffled, so it stays put.

    Drawn with a tile it would follow the tile around the ring and pay out the wrong resource on
    every space but the ones that happened not to move.
    """
    duty = {
        "north": "give_alms",
        "north_east": "produce",
        "east": "clerical",
        "south_east": "build_roads",
        "south": "taxation",
        "south_west": "ordination",
        "west": "construct",
        "north_west": "allocation",
    }
    tithe = dict.fromkeys(duty, "wheat") | {"north": "cornucopia", "south": None}
    payload = _payload([_player([5] + [0] * 8)], duty=duty, tithe=tithe)
    tiles = {
        tile["board_position"]: tile
        for tile in duty_layout_for(payload, load_duty_wheel_layout())["duties"]
    }
    assert tiles["north"]["id"] == "give_alms"
    assert tiles["north"]["tithe_icon"] == "cornucopia"
    # Taxation carries none, and the key is present and null rather than missing: a space with no
    # counter is a fact about it.
    assert tiles["south"]["tithe_icon"] is None
    assert "tithe_icon" in tiles["south"]


def test_the_wheels_cubes_are_keyed_by_tile_but_counted_by_position() -> None:
    """Both at once, which is where this is easiest to get wrong.

    The wheel's own state is keyed by the duty lying on a space; the mancala vector is indexed by
    the space. Keying the vector by tile would scatter every seat's acolytes around the ring.
    """
    duty = {
        "north": "taxation",
        "north_east": "give_alms",
        "east": "produce",
        "south_east": "construct",
        "south": "build_roads",
        "south_west": "clerical",
        "west": "allocation",
        "north_west": "ordination",
    }
    payload = _payload(
        [_player([0, 7, 0, 0, 0, 0, 0, 0, 0])], duty=duty, tithe=dict.fromkeys(duty, None)
    )
    layout = duty_layout_for(payload, load_duty_wheel_layout())
    state = duty_board_state_for(payload, layout)
    # Seven acolytes stand at position 1, which is north, on which taxation lies.
    assert state["taxation"]["player_one"] == 7
    assert sum(counts["player_one"] for counts in state.values()) == 7


def test_the_derived_acolytes_array_is_not_the_one_that_is_read() -> None:
    """Fact (d): `acolytes` is a backward-compatible view of the same tuples. One is read, not two.

    Given a payload whose two copies disagree, the authoritative one wins -- which is the only way
    to tell from the outside which was read.
    """
    payload = _payload([_player([5, 0, 0, 0, 0, 0, 0, 0, 0])])
    payload["state"]["acolytes"] = [[9, 9, 9, 9, 9, 9, 9, 9, 9]]
    assert acolytes_by_position(payload, "player_one") == [5, 0, 0, 0, 0, 0, 0, 0, 0]


# ---------------------------------------------------------------------------------------------
# The values that would otherwise be indistinguishable from the sample
# ---------------------------------------------------------------------------------------------


def test_a_seats_stocks_are_its_own_and_not_the_boards_printed_one() -> None:
    """The layout prints 1 wheat, 1 stone, 1 silver -- which is also what a fresh game deals.

    So a scenario at its starting position cannot tell a mapped stock from the sample, and this
    uses one that has moved on.
    """
    payload = _payload(
        [
            _player([5] + [0] * 8, wheat=4, stone=0, silver=9),
            _player([5] + [0] * 8, wheat=1, stone=1, silver=1),
        ]
    )
    assert resources_for(payload, "player_one") == {"wheat": 4, "stone": 0, "silver": 9}
    assert resources_for(payload, "player_two") == {"wheat": 1, "stone": 1, "silver": 1}

    page = render_play_view_from_payload(payload)
    white = _seat_panel(page, seat_of("player_one"))
    assert _resource_amounts(white) == ["4", "0", "9"]
    red = _seat_panel(page, seat_of("player_two"))
    assert _resource_amounts(red) == ["1", "1", "1"]


def test_each_seat_stands_on_the_alms_row_the_state_puts_it_on() -> None:
    """Every disc starts on row 0, so a page drawn at the start proves nothing about this."""
    payload = _payload(
        [_player([5] + [0] * 8, alms=5), _player([5] + [0] * 8, alms=2)],
    )
    assert player_record(payload, "player_one")["alms_position"] == 5
    page = render_play_view_from_payload(payload)
    rows = dict(
        re.findall(r'data-player="(\w+)" data-player-color="\w+" data-alms-position="(\d+)"', page)
    )
    assert rows["player_one"] == "5"
    assert rows["player_two"] == "2"


def test_the_neutral_acolytes_are_the_ones_the_engine_dealt() -> None:
    """Three per group at two players, two at three, none at four -- already decided upstream.

    Nothing here counts players to work it out; the vector is read as given.
    """
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(2)],
        dummy=[0, 1, 1, 1, 0, 1, 1, 1, 0],
    )
    assert dummy_acolytes_by_position(payload) == [0, 1, 1, 1, 0, 1, 1, 1, 0]
    assert sum(dummy_acolytes_by_position(payload)) == 6


def test_the_border_track_carries_the_buildings_this_scenario_deals() -> None:
    """The map's own slot list is one fixed arrangement; this is the scenario's instead."""
    payload = _payload(
        [_player([5] + [0] * 8)],
        pilgrimage_rounds=[1, 5],
        building_market=["quarry", "well"],
        building_availability={"quarry": 3, "well": 4},
    )
    slots = {slot["round"]: slot for slot in timeline_slots(payload)}
    assert slots[1]["kind"] == "site"
    assert slots[3]["building_id"] == "quarry"
    assert slots[4]["building_id"] == "well"
    assert slots[2]["kind"] == "empty"


# ---------------------------------------------------------------------------------------------
# The log, and what the page refuses to be
# ---------------------------------------------------------------------------------------------


def test_the_log_says_the_position_and_works_none_of_it_out() -> None:
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(4)],
        active_player="player_three",
        start_player_id="player_two",
        phase="turn",
        timing={
            "absolute_turn": 9,
            "round_number": 3,
            "season_number": 2,
            "turn_in_round": 1,
        },
        setup={
            "setup_sow_required": True,
            "setup_sow_complete": True,
            "setup_sow_completed_by": ["player_one", "player_two"],
        },
    )
    header = dict(state_header(payload))
    assert header["Active player"] == "player_three"
    assert header["Start player"] == "player_two"
    assert header["Round"] == "3"
    assert header["Season"] == "2"
    assert header["Turn in round"] == "1"
    assert header["Setup sow"] == "complete"


def test_a_setup_that_is_part_done_says_who_has_sown() -> None:
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(2)],
        setup={
            "setup_sow_required": True,
            "setup_sow_complete": False,
            "setup_sow_completed_by": ["player_one"],
        },
    )
    assert dict(state_header(payload))["Setup sow"] == "sown by player_one"


def test_the_page_offers_nothing_to_press() -> None:
    """Read-only is the design, so it is asserted rather than left to whoever edits next."""
    page = render_play_view_from_payload(_payload([_player([5] + [0] * 8) for _ in range(4)]))
    for control in ("<button", "<select", "<input", "<script", "onclick"):
        assert control not in page


def test_the_log_stands_where_the_debug_tables_controls_do() -> None:
    page = render_play_view_from_payload(_payload([_player([5] + [0] * 8) for _ in range(4)]))
    left = page[page.index('<div class="left">') : page.index('<div class="col">')]
    assert 'class="panel p-alms"' in left
    assert 'class="play-log"' in left


def test_an_empty_chair_keeps_its_width_so_the_others_do_not_slide() -> None:
    """Four chairs are always drawn; two of them are simply hidden at a two-player table."""
    page = render_play_view_from_payload(_payload([_player([5] + [0] * 8) for _ in range(2)]))
    chairs = re.findall(
        r'data-player-seat="(\d)" data-player="\w+" data-player-color="\w+"'
        r' data-seat-taken="(true|false)"',
        page,
    )
    assert chairs == [("1", "true"), ("2", "false"), ("3", "false"), ("4", "true")]
    assert '.p-player[data-seat-taken="false"] { visibility: hidden; }' in page


# ---------------------------------------------------------------------------------------------
# The differential: two scenarios differ where they differ, and nowhere else
# ---------------------------------------------------------------------------------------------


def test_two_arrangements_change_the_wheel_and_leave_the_seats_alone() -> None:
    """A page that looks right for one scenario may only be the layout's sample position.

    So the check is not that one page looks right; it is that a change upstream shows up in the
    panel it belongs to and in no other.
    """
    players = [_player([5] + [0] * 8) for _ in range(4)]
    first = _payload(players)
    second = _payload(
        players,
        duty={
            "north": "taxation",
            "north_east": "give_alms",
            "east": "produce",
            "south_east": "construct",
            "south": "build_roads",
            "south_west": "clerical",
            "west": "allocation",
            "north_west": "ordination",
        },
        tithe={
            "north": None,
            "north_east": "cornucopia",
            "east": "silver",
            "south_east": "silver",
            "south": "wheat",
            "south_west": "wheat",
            "west": "stone",
            "north_west": "stone",
        },
    )
    assert duty_by_position_name(first) != duty_by_position_name(second)
    assert tithe_by_position_name(first) != tithe_by_position_name(second)

    page_one, page_two = (render_play_view_from_payload(p) for p in (first, second))
    assert page_one != page_two
    assert _seat_panels(page_one) == _seat_panels(page_two)


def test_two_building_deals_change_the_map_and_leave_the_wheel_alone() -> None:
    players = [_player([5] + [0] * 8) for _ in range(4)]
    common = {"pilgrimage_rounds": [1, 7]}
    first = _payload(
        players,
        building_market=["quarry"],
        building_availability={"quarry": 3},
        **common,
    )
    second = _payload(
        players,
        building_market=["well"],
        building_availability={"well": 3},
        **common,
    )
    assert render_play_view_from_payload(first) != render_play_view_from_payload(second)
    assert _wheel(render_play_view_from_payload(first)) == _wheel(
        render_play_view_from_payload(second)
    )


def test_the_map_places_what_the_scenario_deals_on_the_round_it_is_live_on() -> None:
    payload = _payload(
        [_player([5] + [0] * 8)],
        pilgrimage_rounds=[1],
        building_market=["kogge"],
        building_availability={"kogge": 4},
    )
    placements = {
        slot["round"]: slot
        for slot in map_placements_for(payload, load_building_catalog(), load_pilgrimage_sites())
    }
    assert placements[4]["building"]["id"] == "kogge"
    assert placements[1]["site"] is not None


def _seat_panel(page: str, seat: int) -> str:
    start = page.index(f'data-player-seat="{seat}"')
    return page[start : page.index("</div>", start)]


def _seat_panels(page: str) -> str:
    return page[page.index('<div class="seats">') :]


def _wheel(page: str) -> str:
    start = page.index('<div class="panel p-action">')
    return page[start : page.index('<div class="panel p-map">', start)]


def _resource_amounts(fragment: str) -> list[str]:
    return re.findall(r'<g data-resource="[a-z]+">.*?<text[^>]*>(\d+)</text>', fragment)
