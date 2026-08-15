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
    first_player_seat,
    player_record,
    resources_for,
    seated_player_ids,
    state_header,
    timeline_slots,
    tithe_by_position_name,
)
from tools.ui_debug.render_buildings import load_building_catalog
from tools.ui_debug.render_donated_buildings import load_donated_building_tiles
from tools.ui_debug.render_duty_wheel import load_duty_wheel_layout
from tools.ui_debug.render_pilgrimage_sites import load_pilgrimage_sites
from tools.ui_debug.render_play_view import (
    _board_state_for,
    duty_board_state_for,
    duty_layout_for,
    map_placements_for,
    piety_variant_for,
    render_play_view_from_payload,
    seat_of,
    ship_hex_for,
)
from tools.ui_debug.render_player_boards_v2 import (
    default_player_board_v2_state,
    load_player_boards_v2_layout,
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


def _player(
    mancala,
    *,
    wheat=1,
    stone=1,
    silver=1,
    alms=0,
    piety=0,
    village=3,
    abbey=2,
    roles=None,
    active=(),
    donated=(),
):
    """One seat's engine record.

    The village and abbey defaults are deliberately NOT the layout's eight and three. A fixture
    that happened to match the sample would let a board drawing the sample pass every check on it,
    which is the whole failure mode these tests exist to catch.
    """
    return {
        "victory_points": 0,
        "piety": piety,
        "alms_position": alms,
        "trade_routes_count": 0,
        "resources": {"stone": stone, "silver": silver, "wheat": wheat},
        "workforce": {
            "mancala": list(mancala),
            "village": village,
            "abbey": abbey,
            "committed": {
                "roads": 0,
                "shrines": 0,
                "market_ports": 0,
                "pilgrimage_sites": 0,
                "alms_table": 0,
            },
        },
        "special_activities": dict(
            {
                "fields": 0,
                "road_engineer": 0,
                "stone_mason": 0,
                "alms_house": 0,
                "engraver": 0,
                "vestry": 0,
            },
            **(roles or {}),
        ),
        "player_board_slots": {
            "active_buildings": list(active),
            "donated_buildings": list(donated),
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
        # South, where this fixture's Taxation tile lies, because that is where the Merchant opens.
        # Never 0: that is the City, and the Merchant does not stand there.
        "merchant_board_position": 5,
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
# Seating
# ---------------------------------------------------------------------------------------------


def test_two_players_sit_in_the_first_two_chairs() -> None:
    """At 2P the occupied seats are 1 and 2, in the same seat order as every other page."""
    payload = _payload([_player([5] + [0] * 8), _player([5] + [0] * 8)])
    seated = seated_player_ids(payload)
    assert seated == ["player_one", "player_two"]
    assert [seat_of(player_id) for player_id in seated] == [1, 2]

    boards = json.loads((UI_DEBUG / "player_boards_v2_layout.json").read_text(encoding="utf-8"))
    color = {player["id"]: player["color"] for player in boards["players"]}
    assert [color[player_id] for player_id in seated] == ["red", "yellow"]


def test_three_players_leave_the_white_chair_empty() -> None:
    payload = _payload([_player([5] + [0] * 8) for _ in range(3)])
    assert seated_player_ids(payload) == ["player_one", "player_two", "player_three"]


def test_the_short_table_gets_the_board_that_is_actually_shorter() -> None:
    """The two-player piety track is a different board, not a narrower one: one row of discs."""
    assert piety_variant_for(["player_one", "player_two"]) == "2_player"
    assert piety_variant_for(["player_one", "player_two", "player_three"]) == "3_4_player"


# ---------------------------------------------------------------------------------------------
# The seal sits with whoever holds the marker, which is not whoever begins the round
# ---------------------------------------------------------------------------------------------


def _seal_in(page: str) -> dict[str, str] | None:
    found = re.search(
        r'<g data-first-player-seal="true" data-player="(\w+)" data-player-color="(\w+)"',
        page,
    )
    return None if found is None else {"player": found.group(1), "color": found.group(2)}


def test_the_seal_goes_to_the_marker_holder_through_the_seating_order() -> None:
    """A player, turned into a chair the way every per-player value on this page is turned into one.

    Blue is `player_three`, who is the third id and the THIRD seat, so an adapter reaching for
    the players array by index would put this seal one chair along -- and would look right doing it
    at four seats, which is the whole reason this is checked by colour at three.
    """
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(3)],
        first_player_marker="player_three",
        start_player_id="player_one",
    )
    assert first_player_seat(payload) == 3

    seal = _seal_in(render_play_view_from_payload(payload))
    assert seal == {"player": "player_three", "color": "blue"}


def test_the_seal_and_the_wash_come_apart_when_a_holder_gives_the_round_away() -> None:
    """THE PAYOFF, as a picture. Two boards lit for two different reasons, and that is the rule.

    The wash says who is acting and the seal says who holds the marker. Through every position
    anyone had looked at they were the same board, which is exactly why the seal used to be drawn
    off the start player and nobody noticed. A holder who names somebody else separates them, and
    this is the frame where a screenshot shows what the marker is worth.
    """
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(4)],
        first_player_marker="player_two",
        start_player_id="player_four",
        active_player="player_four",
    )
    page = render_play_view_from_payload(payload)

    assert _seal_in(page) == {"player": "player_two", "color": "yellow"}
    washed = re.findall(
        r'data-player="(\w+)" data-player-color="\w+"[^>]*data-active-seat="true"', page
    )
    assert washed == ["player_four"]


def test_a_position_that_does_not_know_its_holder_is_drawn_without_a_seal() -> None:
    """No marker, no wax. A scenario from before the engine kept one cannot be asked who has it.

    Drawn on the likeliest seat it would be a guess wearing the one mark on this page that is
    supposed to be a fact, and every one of the committed fixtures is in this case.
    """
    payload = _payload([_player([5] + [0] * 8) for _ in range(4)])
    assert "first_player_marker" not in payload["state"]
    assert first_player_seat(payload) is None

    page = render_play_view_from_payload(payload)
    assert _seal_in(page) is None
    assert "data-first-player-seat" not in page


def test_a_holder_who_is_not_at_the_table_is_treated_as_no_holder() -> None:
    """Blue holds nothing at a three-player table, and an empty chair is not given a seal."""
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(3)],
        first_player_marker="player_four",
    )
    assert first_player_seat(payload) is None


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


def test_the_city_on_the_page_holds_what_the_position_puts_in_it() -> None:
    """The state reaching the wheel was never the trouble; the drawing of it was.

    `duty_board_state_for` has always reported the City correctly. The wheel then threw it away
    and drew `city_sample_cubes_per_seat` instead, so this had to be asserted on the rendered page
    rather than on the state, which is where it was passing all along. Two seats holding different
    numbers, and neither of them the sample, so a page drawing one number for everybody cannot
    pass by accident.
    """
    sample = int(load_duty_wheel_layout()["city_sample_cubes_per_seat"])
    payload = _payload([_player([5, 0, 0, 0, 0, 0, 0, 0, 0]), _player([4, 3, 0, 0, 0, 0, 0, 0, 0])])
    page = render_play_view_from_payload(payload)

    assert sample not in (5, 4)
    assert _cubes_standing_on(page, "city") == {"player_one": 5, "player_two": 4}
    # And what left the City is standing where it went, rather than the ring drawing zero because
    # only the City was wired.
    assert _cubes_standing_on(page, "produce") == {"player_two": 3}


def _cubes_standing_on(page: str, space: str) -> dict[str, int]:
    """How many cubes each seat's column draws on one space of the rendered wheel."""
    start = page.index(f'data-cube-tally="{space}"')
    tally = page[start : page.index("</g>", start)]
    counted: dict[str, int] = {}
    for seat in re.findall(r'<rect [^>]*data-player="(\w+)"', tally):
        counted[seat] = counted.get(seat, 0) + 1
    return counted


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
    assert header == {"Status": "Round 3 - 1 of 4 turns played"}
    for removed in ("Active player", "Start player", "Phase", "Season", "Setup sow", "Players done"):
        assert removed not in header


def test_the_header_row_is_setup_progress_while_setup_sow_is_running() -> None:
    payload = _payload([_player([5] + [0] * 8) for _ in range(4)])
    page = render_play_view_from_payload(payload)
    assert "Turn in round" not in page
    assert "Players done" not in page
    assert "Setup - 0 of 4 sown" in page
    assert "Round 1" not in page


def test_the_header_row_switches_to_round_progress_after_setup() -> None:
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(4)],
        phase="turn",
        timing={
            "absolute_turn": 1,
            "round_number": 1,
            "season_number": 1,
            "turn_in_round": 0,
        },
        setup={
            "setup_sow_required": True,
            "setup_sow_complete": True,
            "setup_sow_completed_by": ["player_one", "player_two", "player_three", "player_four"],
        },
    )
    page = render_play_view_from_payload(payload)

    assert "Round 1 - 0 of 4 turns played" in page


def test_the_header_omits_the_removed_rows() -> None:
    page = render_play_view_from_payload(_payload([_player([5] + [0] * 8) for _ in range(4)]))
    line = re.search(r'<div class="log-status-line"[^>]*>(.*?)</div>', page, re.S)

    assert line is not None
    assert page.count('class="log-status-line"') == 1
    assert 'class="log-key"' not in page
    assert 'class="log-value"' not in page
    status_rule = re.search(r"\.log-status-line \{(.*?)\}", page, re.S)
    assert status_rule is not None
    assert "text-align: left" in status_rule.group(1)
    for removed in ("Active player", "Start player", "Phase", "Season", "Setup sow"):
        assert removed not in line.group(1)


@pytest.mark.parametrize("missing", [False, True])
def test_start_player_presence_does_not_change_the_one_line_header(missing: bool) -> None:
    payload = _payload([_player([5] + [0] * 8) for _ in range(2)])
    before = dict(state_header(payload))
    if missing:
        del payload["state"]["start_player_id"]
    else:
        payload["state"]["start_player_id"] = None
    assert dict(state_header(payload)) == before


def test_the_transcript_is_written_backwards_so_it_opens_on_its_newest_line() -> None:
    """The two halves of one trick, asserted together because either alone is a bug.

    A box that scrolls has to open at the end, or it silently shows the oldest event -- which is
    worse than the taller page it replaced. There is no script to scroll it with: a page served
    with nothing to decide carries none, and a second one would break what the turn script's guard
    claims to cover. So the events are written newest first and `column-reverse` turns them back,
    which puts the scrolling start at the bottom of the box.

    Reverse the markup without the CSS and the log reads backwards; drop the CSS without the markup
    and it opens on the oldest line. Neither is visible from the other half, so both are held here.
    """
    payload = _payload([_player([5] + [0] * 8)]) | {"log": ["oldest", "middle", "newest"]}
    page = render_play_view_from_payload(payload)

    assert re.findall(r'<div class="log-event">([^<]*)</div>', page) == [
        "newest",
        "middle",
        "oldest",
    ]
    rule = re.search(r"\.log-transcript \{(.*?)\}", page, re.S)
    assert rule, "the transcript has no rule of its own"
    assert "column-reverse" in rule.group(1)
    # And it is the thing that gives when the column runs short: no floor, and its own scrollbar.
    assert "min-height: 0" in rule.group(1)
    assert "overflow-y: auto" in rule.group(1)
    assert "flex: 1 1 auto" in rule.group(1)
    log_box_rule = re.search(r"\.play-log \{(.*?)\}", page, re.S)
    assert log_box_rule, "the play box has no CSS rule"
    assert "flex: 1 1 auto" in log_box_rule.group(1)


def test_the_one_line_header_reads_setup_progress_from_the_completed_by_list() -> None:
    payload = _payload(
        [_player([5] + [0] * 8) for _ in range(2)],
        setup={
            "setup_sow_required": True,
            "setup_sow_complete": False,
            "setup_sow_completed_by": ["player_one"],
        },
    )
    assert dict(state_header(payload)) == {"Status": "Setup - 1 of 2 sown"}


def _payload_with_turn_candidates(active_player: str) -> dict:
    payload = _payload([_player([5] + [0] * 8) for _ in range(4)], active_player=active_player)
    payload["turn_candidates"] = [
        {
            "steps": [],
            "action_id": "sample",
            "summary": "sample summary",
            "variants": 1,
            "unresolved": [],
        }
    ]
    return payload


def test_offer_ring_colour_follows_the_active_seat_for_two_different_seats() -> None:
    fills = {
        player["id"]: player["fill"]
        for player in load_player_boards_v2_layout()["players"]
    }
    seen: dict[str, tuple[str, str]] = {}
    for player_id in ("player_one", "player_two"):
        page = render_play_view_from_payload(_payload_with_turn_candidates(player_id))
        start = re.search(
            r'\[data-turn-start-candidate="true"\]\s+\.board-circle\s*\{([^}]*)\}',
            page,
            re.S,
        )
        duty = re.search(
            r'\[data-turn-duty-candidate="true"\]\s+\.board-circle\s*\{([^}]*)\}',
            page,
            re.S,
        )
        chosen = re.search(
            r'\[data-turn-duty-selected="true"\]\s+\.board-circle\s*\{([^}]*)\}',
            page,
            re.S,
        )
        assert start is not None, "start-candidate board-circle rule was not present"
        assert duty is not None, "duty-candidate board-circle rule was not present"
        assert chosen is not None, "duty-selected board-circle rule was not present"

        start_rule = " ".join(start.group(1).split())
        duty_rule = " ".join(duty.group(1).split())
        chosen_rule = " ".join(chosen.group(1).split())
        assert f"stroke: {fills[player_id]}" in start_rule
        assert f"stroke: {fills[player_id]}" in duty_rule
        assert f"stroke: {fills[player_id]}" in chosen_rule
        assert "stroke-dasharray: 8 4" in start_rule
        assert "stroke-dasharray: 8 4" in duty_rule
        assert "stroke-dasharray" not in chosen_rule
        seen[player_id] = (start_rule, duty_rule)

    assert seen["player_one"] != seen["player_two"], "offer ring colour stopped following seat"


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
    assert chairs == [("1", "true"), ("2", "true"), ("3", "false"), ("4", "false")]
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
    return re.findall(r'<g data-resource="[a-z]+"[^>]*>.*?<text[^>]*>(\d+)</text>', fragment)


def _merchant_space_index(page: str) -> int:
    """The board position index of the space the Merchant token was drawn inside.

    Read off the space rather than off the token, because the space is what the mapping is supposed
    to have chosen. `data-merchant-token` on the SVG root names a duty, which is the wheel's own way
    of marking it and is exactly the thing these tests must not take at face value.
    """
    wheel = _wheel(page)
    token = wheel.index('data-token="merchant"')
    groups = list(re.finditer(r'data-board-position-index="(\d+)"', wheel[:token]))
    assert groups, "the Merchant token was drawn outside any board space"
    return int(groups[-1].group(1))


def _generated_payload(tmp_path: Path, seed: int) -> dict:
    import subprocess

    from pilgrim.io.scenarios import load_scenario
    from pilgrim.io.view import view_payload

    destination = tmp_path / f"seed_{seed}.json"
    subprocess.run(
        [
            "python3",
            "-m",
            "pilgrim.cli",
            "generate-setup",
            "--players",
            "2",
            "--seed",
            str(seed),
            "--out",
            str(destination),
        ],
        check=True,
        capture_output=True,
    )
    scenario = load_scenario(destination)
    return view_payload(scenario.state, scenario.config)


def test_the_merchant_is_drawn_on_the_space_the_engine_put_it_on(tmp_path: Path) -> None:
    """Three seeds that deal Taxation onto three different spaces, and the token follows it.

    This is what kills a mapping keyed on a FIXED space: the Merchant opens on Taxation, Taxation
    is dealt somewhere new each seed, so a token nailed to one position index is wrong on two of
    the three. The seeds are chosen for that spread and the spread is asserted, so the test cannot
    quietly stop discriminating if the generator's dealing changes.
    """
    indices = {}
    for seed in (1, 2, 3):
        payload = _generated_payload(tmp_path, seed)
        page = render_play_view_from_payload(payload)
        taxation = next(
            tile["position"] for tile in payload["duty_tiles"] if tile["duty"] == "taxation"
        )
        assert _merchant_space_index(page) == payload["state"]["merchant_board_position"]
        assert _merchant_space_index(page) == taxation
        indices[seed] = taxation

    assert len(set(indices.values())) == 3, f"seeds no longer spread Taxation about: {indices}"


def test_the_merchant_walks_the_ring_clockwise_and_wraps_past_north_west(tmp_path: Path) -> None:
    """Advancing the engine's Merchant moves the drawn token the same way, wrap included.

    Keyed on the space at every step, and advanced by the engine's own walk rather than by a step
    this test works out for itself -- otherwise it would be checking the page against a second
    opinion instead of against the rule.

    This is the check that a mapping asking the layout for `merchant_token.starts_on` cannot pass.
    That answer is "taxation" forever, which happens to be right on a freshly dealt board however
    the tiles fell, and is wrong the moment the Merchant leaves it.
    """
    import subprocess

    from pilgrim.io.scenarios import load_scenario
    from pilgrim.io.view import view_payload
    from pilgrim.rules.merchant import advance_merchant_position

    destination = tmp_path / "walk.json"
    subprocess.run(
        [
            "python3",
            "-m",
            "pilgrim.cli",
            "generate-setup",
            "--players",
            "2",
            "--seed",
            "2",
            "--out",
            str(destination),
        ],
        check=True,
        capture_output=True,
    )
    scenario = load_scenario(destination)
    state, config = scenario.state, scenario.config
    names = list(view_payload(state, config)["board_positions"])

    walked = []
    for _step in range(8):
        page = render_play_view_from_payload(view_payload(state, config))
        assert _merchant_space_index(page) == state.merchant_board_position
        walked.append(names[state.merchant_board_position])
        state = state.with_merchant_board_position(
            advance_merchant_position(state.merchant_board_position, config)
        )

    # Eight steps visit all eight duty spaces exactly once and never the City.
    assert len(set(walked)) == 8
    assert "city" not in walked
    # The wrap itself, named rather than left implied by the set above.
    assert walked[(walked.index("north_west") + 1) % 8] == "north"
    # And back where it started, which is what makes it a ring rather than a line.
    assert state.merchant_board_position == scenario.state.merchant_board_position


def test_the_merchant_token_is_visible_on_taxation_which_has_no_capsule(tmp_path: Path) -> None:
    """Taxation carries no tithe counter, so there is no capsule for the token to share.

    It goes in the empty band under the label instead. The risk is not that it is drawn but that it
    is drawn somewhere the space's own clip path throws away, so this checks it is inside the space
    and below its label rather than merely present in the markup.
    """
    payload = _generated_payload(tmp_path, 2)
    page = render_play_view_from_payload(payload)
    wheel = _wheel(page)

    taxation_start = wheel.index('data-duty="taxation"')
    taxation = wheel[
        taxation_start : wheel.index("</g>", wheel.index("cube-tally", taxation_start))
    ]
    assert "data-tithe-icon" not in taxation, "Taxation should carry no counter to share a capsule"

    token = re.search(
        r'<circle cx="([\d.]+)" cy="([\d.]+)" r="(\d+)"[^>]*data-token="merchant"', wheel
    )
    assert token is not None, "no Merchant token was drawn"
    label = re.search(r'<text x="([\d.]+)" y="([\d.]+)" class="circle-label"[^>]*taxation', wheel)
    assert label is not None
    assert float(token.group(2)) > float(label.group(2)), "token should sit below the label"
    assert float(token.group(3)) > 0


# ---------------------------------------------------------------------------------------------
# The player board, which used to draw the layout's sample whatever the state said
# ---------------------------------------------------------------------------------------------


SAMPLE_VILLAGE = 8
SAMPLE_ABBEY = 3
SAMPLE_ROLES = {"stone_mason": 1, "vestry": 2}


def _board_state(payload: dict, player_id: str) -> dict:
    return _board_state_for(
        payload,
        load_player_boards_v2_layout(),
        player_id,
        load_building_catalog(),
        load_donated_building_tiles(),
    )


def _panel(page: str, player_id: str) -> str:
    """One seat's panel, cut out of the page so nothing on the map can be mistaken for it."""
    parts = re.split(r'<div class="panel p-player"', page)[1:]
    return next(part for part in parts if f'data-player="{player_id}"' in part)


def _cubes_on(page: str, player_id: str) -> int:
    """How many cubes are actually inked on one seat's board.

    Both grids draw all eight slots whatever the count and hide the spare ones, so what is on
    screen is the ones left at full opacity. Counted rather than located: where a cube sits is the
    renderer's business and this is only asking how many a seat is shown to have.
    """
    return len(re.findall(r"<rect[^>]*opacity=\"1\"", _panel(page, player_id)))


def _slots_on(page: str, player_id: str) -> list[tuple[str, str]]:
    """What is standing in this seat's building slots, as (state, building id)."""
    return [
        (state, building)
        for _number, state, building in re.findall(
            r'data-player-board-slot="(\d+)" data-building-slot-state="(\w+)"'
            r' data-building-id="([a-z_]*)"',
            _panel(page, player_id),
        )
    ]


def test_the_board_shows_the_seats_own_acolytes_and_not_the_layouts_sample() -> None:
    """The values are read off the seat, and the fixture is built so the sample cannot pass.

    Village and abbey both differ from the eight and three the layout draws, and in opposite
    directions, so a board that had simply swapped them would be caught too.
    """
    payload = _payload([_player([5] + [0] * 8, village=2, abbey=6) for _ in range(4)])
    state = _board_state(payload, "player_one")

    assert (state["village_serfs"], state["abbey_acolytes"]) == (2, 6)
    assert state["village_serfs"] != SAMPLE_VILLAGE
    assert state["abbey_acolytes"] != SAMPLE_ABBEY
    assert _cubes_on(render_play_view_from_payload(payload), "player_one") == 8


def test_the_village_and_the_abbey_are_two_values_and_not_one() -> None:
    """Swapping them has to change the drawing, or only their total was ever wired.

    Both grids hold eight, so a page that added them up and drew the total would put the same
    number of cubes on screen either way round and every count above would still pass.
    """
    few_in_the_village = _payload([_player([5] + [0] * 8, village=2, abbey=6) for _ in range(4)])
    many_in_the_village = _payload([_player([5] + [0] * 8, village=6, abbey=2) for _ in range(4)])

    assert _panel(render_play_view_from_payload(few_in_the_village), "player_one") != _panel(
        render_play_view_from_payload(many_in_the_village), "player_one"
    )


def test_the_role_circles_follow_the_special_activities() -> None:
    """Nobody holds a role at the opening, and the layout draws three cubes standing on two.

    So this is the one wired value that was wrong on the very first frame rather than after a few
    turns: the sample has a Stone Mason and two Vestry, and a fresh game has neither.
    """
    empty = _payload([_player([5] + [0] * 8) for _ in range(4)])
    assert set(_board_state(empty, "player_one")["roles"].values()) == {0}

    staffed = _payload(
        [_player([5] + [0] * 8, roles={"fields": 2, "engraver": 1}) for _ in range(4)]
    )
    roles = _board_state(staffed, "player_one")["roles"]
    assert roles["fields"] == 2
    assert roles["engraver"] == 1
    assert roles["stone_mason"] == 0, "the sample's Stone Mason survived into a real board"
    assert roles["vestry"] == 0, "the sample's Vestry survived into a real board"
    # And they reach the drawing: three more cubes on the board than a seat holding no role.
    assert (
        _cubes_on(render_play_view_from_payload(staffed), "player_one")
        == _cubes_on(render_play_view_from_payload(empty), "player_one") + 3
    )


def test_a_building_a_seat_has_built_stands_in_a_slot_on_that_seats_board_alone() -> None:
    """THE SYMPTOM. A constructed building used to leave the market and land nowhere."""
    payload = _payload(
        [
            _player([5] + [0] * 8, active=["chapter_house"]),
            _player([5] + [0] * 8),
            _player([5] + [0] * 8),
            _player([5] + [0] * 8),
        ]
    )
    page = render_play_view_from_payload(payload)

    assert _slots_on(page, "player_one") == [("bought", "chapter_house")]
    for empty_handed in ("player_two", "player_three", "player_four"):
        assert _slots_on(page, empty_handed) == [], "a building landed on the wrong board"


def test_a_donated_building_is_drawn_on_its_donated_side() -> None:
    """Donated buildings have a home -- the same six slots -- and a face of their own.

    The star and the number, which is what a donated tile is; drawing it in the building's own
    colours and label would say it was still working for the seat that gave it away.
    """
    payload = _payload(
        [
            _player([5] + [0] * 8, active=["chapter_house"], donated=["mint"]),
            *[_player([5] + [0] * 8) for _ in range(3)],
        ]
    )
    page = render_play_view_from_payload(payload)

    assert _slots_on(page, "player_one") == [("bought", "chapter_house"), ("donated", "mint")]
    panel = _panel(page, "player_one")
    assert ">Chapter<" in panel and ">House<" in panel, "the bought building lost its name"
    assert ">Mint<" not in panel, "the donated building was drawn as if it were still in use"
    # What a donated tile is instead: a star with its victory points written in it.
    assert 'data-donated="true"' in panel


def test_a_seat_that_is_not_at_the_table_is_drawn_from_the_sample_and_hidden() -> None:
    """An empty chair has no record to read, and must not be made to look like one."""
    payload = _payload([_player([5] + [0] * 8, village=2) for _ in range(2)])
    state = _board_state(payload, "player_four")

    assert state == default_player_board_v2_state(load_player_boards_v2_layout())
    assert 'data-player="player_four" data-player-color' in render_play_view_from_payload(payload)
    assert 'data-seat-taken="false"' in _panel(
        render_play_view_from_payload(payload), "player_four"
    )


# ---------------------------------------------------------------------------------------------
# Two deliberate bugs in the board wiring
# ---------------------------------------------------------------------------------------------


def test_falling_back_to_the_sample_for_one_value_is_caught(monkeypatch) -> None:
    """MUTATION. Put the layout's abbey count back and the board must stop matching the seat.

    The likeliest way this regresses is not a rewrite but a merge: one key dropped out of the dict
    and the sample underneath it fills the gap silently, because that is exactly what the sample is
    for. It leaves five values right and one lying, which is the hardest version to spot.
    """
    from tools.ui_debug import render_play_view

    truthful = render_play_view._board_state_for

    def abbey_from_the_sample(payload, board_layout, player_id, catalog, donated_data):
        state = truthful(payload, board_layout, player_id, catalog, donated_data)
        return dict(state, abbey_acolytes=SAMPLE_ABBEY)

    payload = _payload([_player([5] + [0] * 8, village=2, abbey=6) for _ in range(4)])
    before = _cubes_on(render_play_view_from_payload(payload), "player_one")

    monkeypatch.setattr(render_play_view, "_board_state_for", abbey_from_the_sample)
    after = _cubes_on(render_play_view_from_payload(payload), "player_one")

    assert after != before, "the sample and the seat agreed, so this fixture proves nothing"
    assert after == 2 + SAMPLE_ABBEY


def test_drawing_a_seats_board_from_its_neighbour_is_caught(monkeypatch) -> None:
    """MUTATION, and the one that matters. Four boards drawn from the wrong players look fine.

    Nothing is missing, nothing is the sample, every number is a real number off a real seat -- and
    the whole row is a lie. It is the same mistake the seating order has caused three times, and
    the only defence is that the seats hold values that cannot be mistaken for each other, which is
    what the fixture below arranges.
    """
    from tools.ui_debug import render_play_view

    truthful = render_play_view._board_state_for
    order = ["player_one", "player_two", "player_three", "player_four"]

    def one_seat_over(payload, board_layout, player_id, catalog, donated_data):
        neighbour = order[(order.index(player_id) + 1) % len(order)]
        return truthful(payload, board_layout, neighbour, catalog, donated_data)

    # Four seats, four different numbers of cubes, so no two boards can be swapped unnoticed.
    payload = _payload([_player([5] + [0] * 8, village=seat, abbey=1) for seat in (1, 2, 3, 4)])
    page = render_play_view_from_payload(payload)
    honest = {player_id: _cubes_on(page, player_id) for player_id in order}
    assert len(set(honest.values())) == len(order), "the seats were not told apart by the fixture"

    monkeypatch.setattr(render_play_view, "_board_state_for", one_seat_over)
    shifted_page = render_play_view_from_payload(payload)
    shifted = {player_id: _cubes_on(shifted_page, player_id) for player_id in order}

    assert shifted != honest
    for player_id in order:
        neighbour = order[(order.index(player_id) + 1) % len(order)]
        assert shifted[player_id] == honest[neighbour]


# ---------------------------------------------------------------------------------------------
# The ship, which used to stand on round 1 whatever the state said
# ---------------------------------------------------------------------------------------------


def _ship_center(page: str) -> tuple[float, float]:
    """Where the ship marker was translated to, off the page rather than off the layout."""
    marker = re.search(r'<g id="ship-marker" transform="translate\((-?[\d.]+),(-?[\d.]+)\)"', page)
    assert marker is not None, "no ship was drawn"
    return float(marker.group(1)), float(marker.group(2))


def test_the_ship_stands_where_the_state_says_and_not_on_round_one(tmp_path: Path) -> None:
    """Proven MID-GAME, because at round 1 the sample is right and proves nothing.

    `ship_position` counts from the slot round 1 sits on, so position 0 and "the first hex" are
    the same hex, and a page that never read the state passed every check anyone could write on a
    fresh board. Three positions here, all of them past that.
    """
    payload = _generated_payload(tmp_path, 4)
    opening = _ship_center(render_play_view_from_payload(payload))

    seen = {}
    for position in (0, 4, 11):
        payload["state"]["ship_position"] = position
        seen[position] = _ship_center(render_play_view_from_payload(payload))

    assert seen[0] == opening, "position 0 is the opening hex and should not have moved"
    assert len(set(seen.values())) == 3, "the ship stood in the same place at three positions"


def test_the_ship_walks_the_same_ring_the_track_is_laid_along(tmp_path: Path) -> None:
    """Its hex at position N is the hex the track gives round N+1, which is what makes it a ring."""
    payload = _generated_payload(tmp_path, 4)
    placements = {
        placement["round"]: placement["hex"]
        for placement in map_placements_for(
            payload, load_building_catalog(), load_pilgrimage_sites()
        )
    }

    for position, round_number in ((0, 1), (5, 6), (9, 10)):
        payload["state"]["ship_position"] = position
        assert ship_hex_for(payload) == placements[round_number]


def test_taking_the_ship_back_to_round_one_is_caught(tmp_path: Path, monkeypatch) -> None:
    """MUTATION. Draw it on the first slot again and a mid-game page must notice.

    This is what the page did until now, and it is invisible on the board the page is generated
    from -- which is why the check above is written against a position the opening cannot reach.
    """
    from tools.ui_debug import render_play_view

    payload = _generated_payload(tmp_path, 4)
    payload["state"]["ship_position"] = 7
    wired = _ship_center(render_play_view_from_payload(payload))

    monkeypatch.setattr(render_play_view, "ship_hex_for", lambda payload: "J3")
    assert _ship_center(render_play_view_from_payload(payload)) != wired
