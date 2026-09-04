"""The engine side of the seam: what is serialized, what joins it, and what the server answers.

The setup sow is playable now, so these also hold the applying half: what a submission must quote
to be accepted, what is refused and leaves the position alone, and that the board that comes back
was drawn from the new state rather than patched by the page.

The narrowing the page does is tested by RUNNING it. `sow_script_harness.js` executes the shipped
script against a stub board under node, so what the assertions below are compared against is the
JavaScript that ships, not a second copy of its logic written in Python. Those tests skip where
node is absent rather than quietly reducing to nothing.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import socket
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from pilgrim.io.event_text import format_event_for_players
from pilgrim.io.logs import state_to_record
from pilgrim.io.scenarios import load_scenario
from pilgrim.io.view import duty_tiles_record, view_payload
from pilgrim.model.actions import (
    BuildingActivationStep,
    BuildingConversionStep,
    EndTurnAction,
    FullTurnAction,
    SetupSowAction,
    StartPlayerSelectionAction,
    action_id,
    action_summary_for_players,
)
from pilgrim.model.enums import (
    CANONICAL_POSITION_NAMES,
    EventType,
    PlayerId,
    TurnResolutionType,
)
from pilgrim.rules import transition
from pilgrim.rules.buildings import (
    BUILDING_ABILITY_REASONS,
    BuildingAbilityReason,
    BuildingAbilitySource,
    building_ability_source,
)
from pilgrim.rules.merchant import CORNUCOPIA_COUNTER
from pilgrim.rules.ordination import ordination_outcome
from pilgrim.rules.special_activities import allocation_outcome
from pilgrim.rules.transition import (
    TaxationMajorityUnlock,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)
from tools import play_server
from tools.play_server import PlayServer, actions_document, state_token
from tools.ui_debug import render_play_view
from tools.ui_debug.render_play_view import (
    SEAT_COLOURS,
    building_tooltip_script,
    render_play_view_from_payload,
)
from tools.ui_debug.render_table_layout import SEATED_PLAYERS

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"
PLAYTEST_SCENARIOS = SCENARIOS / "playtest"
PLAYTEST_CLOISTERS = "cloisters_reach_2p.json"
PLAYTEST_CLOISTERS_LOOP = "cloisters_loop_2p.json"
PLAYTEST_KOGGE_AND_CLOISTERS = "kogge_and_cloisters_2p.json"
PLAYTEST_CONVERSIONS = "conversions_2p.json"
PLAYTEST_MOVEMENT = "movement_2p.json"
PLAYTEST_PULPIT = "pulpit_2p.json"
PLAYTEST_POSITION_NAMES = (
    PLAYTEST_CLOISTERS,
    PLAYTEST_CLOISTERS_LOOP,
    PLAYTEST_KOGGE_AND_CLOISTERS,
    PLAYTEST_CONVERSIONS,
    PLAYTEST_MOVEMENT,
    PLAYTEST_PULPIT,
)
CITY_REVERSAL_ARROWS = frozenset({"city->east", "city->west", "north->city", "south->city"})
ROUTE_BUILDING_REFUSAL_FIELDS = frozenset(
    {
        "sow_route_building_id",
        "sow_route_secondary_building_id",
        "sow_route_secondary_building_source",
    }
)
SPACE_QUESTION_KINDS = frozenset(
    {
        "origin",
        "skip",
        "duty",
    }
)
TURN_SCRIPT_RELOCATION_BUILDING_LITERAL_EXEMPTIONS = (
    "dormitory",
    "inquisition",
    "library",
    "dormitory",
)


@pytest.fixture(scope="module")
def scenario():
    return load_scenario(str(SCENARIOS / "alms_sandbox_001.json"))


def _payload_from_corpus(scenario, actions) -> dict[str, Any]:
    """Build one uncached page payload from a shared state/action load."""
    state_payload = view_payload(scenario.state, scenario.config)
    route_payload = play_server.route_family_payload(
        scenario.state,
        scenario.config,
        actions=actions,
        include_preview_effects=False,
    )
    return dict(
        state_payload,
        state_token=state_token(state_payload),
        **route_payload,
        log=[],
        log_blocks=[],
        phase_column=play_server.phase_column_payload(
            scenario.state,
            [],
            turn_candidates=route_payload["turn_candidates"],
        ),
    )


def _all_corpus_actions(corpus_actions, playtest_actions):
    return (*corpus_actions, *playtest_actions)


@pytest.fixture(scope="module")
def play_payload_corpus(corpus_actions, playtest_actions):
    """The page-facing route-family payload for every committed scenario, built once per module."""
    corpus = tuple(
        (scenario_path, _payload_from_corpus(scenario, actions))
        for scenario_path, scenario, actions in _all_corpus_actions(
            corpus_actions, playtest_actions
        )
    )
    assert len(corpus) >= 320, f"only {len(corpus)} scenarios reached the play payload"
    return corpus


# ---------------------------------------------------------------------------------------------
# What the state record carries
# ---------------------------------------------------------------------------------------------


def test_the_record_carries_the_seat_values_it_used_to_drop(scenario) -> None:
    """`alms_position` sits between `piety` and `victory_points`, and both were already here."""
    record = state_to_record(scenario.state)
    for seat, player in zip(record["players"], scenario.state.players, strict=True):
        assert seat["alms_position"] == player.alms_position
        assert seat["trade_routes_count"] == player.trade_routes_count


def test_the_record_carries_the_clock(scenario) -> None:
    """A log box cannot say what round it is from a turn counter alone."""
    timing = state_to_record(scenario.state)["timing"]
    assert timing["round_number"] == scenario.state.timing.round_number
    assert timing["season_number"] == scenario.state.timing.season_number
    assert timing["turn_in_round"] == scenario.state.timing.turn_in_round


def test_the_record_says_whether_the_game_has_started(scenario) -> None:
    setup = state_to_record(scenario.state)["setup"]
    assert setup["setup_sow_required"] == scenario.state.setup_sow_required
    assert setup["setup_sow_complete"] == scenario.state.setup_sow_complete
    assert setup["setup_sow_completed_by"] == [
        player_id.name.lower() for player_id in scenario.state.setup_sow_completed_by
    ]


def test_the_record_stays_a_state_record_and_takes_nothing_from_the_config(scenario) -> None:
    """The duty arrangement is not on the state, so it must not appear to be."""
    record = state_to_record(scenario.state)
    assert "duty_tiles" not in record
    assert "tithe_counters" not in record


def test_the_record_is_json_and_nothing_in_it_needs_an_encoder(scenario) -> None:
    json.dumps(state_to_record(scenario.state))


# ---------------------------------------------------------------------------------------------
# The join: state plus the config facts a board cannot be drawn without
# ---------------------------------------------------------------------------------------------


def test_every_duty_position_but_the_city_gets_a_tile(scenario) -> None:
    tiles = duty_tiles_record(scenario.config)
    assert [tile["position"] for tile in tiles] == list(range(1, 9))
    assert [tile["position_name"] for tile in tiles] == list(CANONICAL_POSITION_NAMES[1:])


def test_the_tile_named_at_a_position_is_the_one_the_engine_puts_there(scenario) -> None:
    """Read back through the engine's own accessor rather than through a second reading of it."""
    from pilgrim.model.duties import duty_category_at_position

    for tile in duty_tiles_record(scenario.config):
        assert tile["duty"] == duty_category_at_position(scenario.config, tile["position"])


def test_taxation_is_the_one_space_with_no_counter_on_it(scenario) -> None:
    tiles = duty_tiles_record(scenario.config)
    without = [tile for tile in tiles if tile["tithe"] is None]
    assert [tile["duty"] for tile in without] == ["taxation"]


def test_the_payload_is_the_record_and_the_join_and_nothing_invented(scenario) -> None:
    payload = view_payload(scenario.state, scenario.config)
    assert sorted(payload) == ["board_positions", "duty_tiles", "state"]
    assert payload["state"] == state_to_record(scenario.state)
    assert payload["board_positions"] == list(CANONICAL_POSITION_NAMES)


def test_the_payload_says_nothing_about_whose_turn_is_next_or_what_is_legal(scenario) -> None:
    """A serializer that answered either would be the second rules implementation starting."""
    payload = json.dumps(view_payload(scenario.state, scenario.config))
    for decided in ("legal", "next_player", "score", "can_", "allowed"):
        assert decided not in payload


# ---------------------------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------------------------


def test_the_action_list_is_structured_all_the_way_down(scenario) -> None:
    """Fields, not the CLI's sentence. A client parsing that string would be a rules parser."""
    payload = view_payload(scenario.state, scenario.config)
    document = actions_document(scenario.state, scenario.config, payload)
    assert document["count"] == len(legal_actions(scenario.state, scenario.config))
    assert document["count"] > 0
    for entry in document["actions"]:
        assert entry["action_id"]
        assert isinstance(entry["fields"], dict)
        assert "origin" in entry["fields"]
        assert "route" in entry["fields"]
    json.dumps(document)


def test_every_action_is_named_by_something_a_client_can_quote_back(scenario) -> None:
    """An index into this list means nothing once the list is built again; an id keeps meaning."""
    payload = view_payload(scenario.state, scenario.config)
    ids = [
        entry["action_id"]
        for entry in actions_document(scenario.state, scenario.config, payload)["actions"]
    ]
    assert len(set(ids)) == len(ids)


def test_the_token_names_the_position_the_list_came_from(scenario) -> None:
    """So the next PR can refuse a submission quoting a list that has since gone stale."""
    payload = view_payload(scenario.state, scenario.config)
    assert state_token(payload) == state_token(view_payload(scenario.state, scenario.config))

    moved = json.loads(json.dumps(payload))
    moved["state"]["players"][0]["piety"] += 1
    assert state_token(moved) != state_token(payload)


def test_a_fresh_scenario_opens_on_the_start_player_decision_and_nothing_else(
    tmp_path: Path,
) -> None:
    """A game now opens by asking who begins, before anybody sows anything.

    It used to open on the setup sows, because who began was written into the generator. The sows
    are still the next thing, and are reached by answering this.
    """
    from pilgrim.cli import main as cli_main

    path = tmp_path / "fresh.json"
    cli_main(["generate-setup", "--players", "4", "--seed", "99", "--output", str(path)])
    scenario = load_scenario(str(path))
    payload = view_payload(scenario.state, scenario.config)
    document = actions_document(scenario.state, scenario.config, payload)
    assert document["count"] > 0
    assert {entry["action_type"] for entry in document["actions"]} == {"StartPlayerSelectionAction"}
    assert all(
        entry["action_id"].startswith("start_player_selection:") for entry in document["actions"]
    )

    chosen = document["actions"][1]["action_id"]
    begun = apply_action(
        scenario.state,
        next(
            action
            for action in legal_actions(scenario.state, scenario.config)
            if action_id(action) == chosen
        ),
        scenario.config,
    ).state
    document = actions_document(begun, scenario.config, view_payload(begun, scenario.config))
    assert {entry["action_type"] for entry in document["actions"]} == {"SetupSowAction"}


def test_the_read_routes_answer_and_none_of_them_change_anything(tmp_path: Path) -> None:
    """Reading the position must never move it, however much the page can now do to it.

    This asserted the page carried no button at all, which was the walking skeleton's promise that
    nothing could be pressed. The page is playable now, so that clause has been replaced by the one
    that still holds and is what it was really guarding: GET changes nothing.
    """
    from pilgrim.cli import main as cli_main

    path = tmp_path / "scenario.json"
    cli_main(["generate-setup", "--players", "4", "--seed", "99", "--output", str(path)])

    server = PlayServer(("127.0.0.1", 0), path)
    before = server.state
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/", timeout=10) as response:
            page = response.read().decode("utf-8")
        with urllib.request.urlopen(f"{base}/state.json", timeout=10) as response:
            state = json.loads(response.read())
        with urllib.request.urlopen(f"{base}/actions.json", timeout=10) as response:
            actions = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()

    assert page.startswith("<!DOCTYPE html>")
    assert state == server.state_payload
    assert actions["count"] == len(actions["actions"]) > 0
    assert actions["state_token"] == state_token(server.state_payload)
    # Nothing was applied: the position the server holds is the one it was handed.
    assert server.state is before


def test_a_second_server_on_an_occupied_address_keeps_the_os_error() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()

        with pytest.raises(OSError):
            PlayServer(occupied.getsockname())


def test_the_page_the_server_serves_is_the_page_the_file_writer_writes(tmp_path: Path) -> None:
    """One renderer, so a page reviewed as a file is the page seen behind the server."""
    from tools.ui_debug.render_play_view import (
        generate_play_view_page,
        render_play_view_from_payload,
    )

    scenario = load_scenario(str(SCENARIOS / "alms_sandbox_001.json"))
    payload = view_payload(scenario.state, scenario.config)
    written = generate_play_view_page(payload, tmp_path / "play_view.html")
    assert written.read_text(encoding="utf-8") == render_play_view_from_payload(payload)


def _start_fields(
    *,
    player_count: int,
    seed: int,
    test_position: str | None = None,
) -> dict[str, str]:
    fields = {
        "player_count": str(player_count),
        "setup_mode": "random",
        "seed": str(seed),
    }
    if test_position is not None:
        fields["test_position"] = test_position
    for seat in range(1, player_count + 1):
        fields[f"seat_{seat}_role"] = "human"
    return fields


def _style_block(page: str) -> str:
    match = re.search(r"<style>\n(.*?)\n</style>", page, re.S)
    assert match is not None, "page carried no stylesheet"
    return match.group(1)


def _script_block(page: str) -> str:
    match = re.search(r"<script>\n(.*?)\n</script>", page, re.S)
    assert match is not None, "page carried no script"
    return match.group(1)


def _display_declarations(styles: str) -> list[tuple[str, str]]:
    declarations: list[tuple[str, str]] = []
    cleaned = re.sub(r"/\*.*?\*/", "", styles, flags=re.S)
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", cleaned, re.S):
        selectors = [selector.strip() for selector in rule.group(1).split(",")]
        display = re.search(r"display\s*:\s*([^;]+);", rule.group(2))
        if display is None:
            continue
        value = " ".join(display.group(1).split())
        declarations.extend((selector, value) for selector in selectors if selector)
    return declarations


def _pointer_events_declarations(styles: str) -> list[tuple[str, str]]:
    declarations: list[tuple[str, str]] = []
    cleaned = re.sub(r"/\*.*?\*/", "", styles, flags=re.S)
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", cleaned, re.S):
        selectors = [selector.strip() for selector in rule.group(1).split(",")]
        pointer_events = re.search(r"pointer-events\s*:\s*([^;]+);", rule.group(2))
        if pointer_events is None:
            continue
        value = " ".join(pointer_events.group(1).split())
        declarations.extend((selector, value) for selector in selectors if selector)
    return declarations


def _declared_pointer_events(styles: str, selector: str) -> str | None:
    value = None
    for written_selector, written_value in _pointer_events_declarations(styles):
        if written_selector == selector:
            value = written_value
    return value


def _arrangement_pointer_rules(page: str) -> dict[str, dict[str, bool]]:
    """Reachability gates copied from CSS into harness data, so tests fail on real mouse misses."""
    styles = _style_block(page)
    return {
        "blanket": {
            "abbeyToken": _declared_pointer_events(
                styles, '[data-component="player-board-v2"] [data-token="abbey"]'
            )
            == "none",
            "roleToken": _declared_pointer_events(
                styles, '[data-component="player-board-v2"] [data-token="role"]'
            )
            == "none",
            "roleCircle": _declared_pointer_events(
                styles, '[data-component="player-board-v2"] [data-role-circle]'
            )
            == "none",
        },
        "live": {
            "abbeyLiftVisible": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-token="abbey"]'
                '[data-arrangement-can-lift="true"][opacity="1"]',
            )
            == "all",
            "abbeyCanPlace": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-token="abbey"][data-arrangement-can-place="true"]',
            )
            == "all",
            "abbeyHeld": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-token="abbey"][data-arrangement-held="true"]',
            )
            == "all",
            "roleLiftVisible": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-token="role"]'
                '[data-arrangement-can-lift="true"][opacity="1"]',
            )
            == "all",
            "roleHeld": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-token="role"][data-arrangement-held="true"]',
            )
            == "all",
            "roleCircleCanPlace": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-role-circle][data-arrangement-can-place="true"]',
            )
            == "all",
            "roleCircleHeld": _declared_pointer_events(
                styles,
                '[data-arrangement-choice="true"] [data-role-circle][data-arrangement-held="true"]',
            )
            == "all",
        },
    }


def _declared_display(styles: str, selector: str) -> str | None:
    value = None
    for written_selector, written_display in _display_declarations(styles):
        if written_selector == selector:
            value = written_display
    return value


def _assert_hidden_display_pairing(page: str) -> None:
    """If script sets `hidden` on display-styled elements, CSS must switch them off via `[hidden]`."""
    styles = _style_block(page)
    script = _script_block(page)
    hidden_selectors = [
        selector
        for variable, selector in re.findall(
            r"var\s+([A-Za-z_]\w*)\s*=\s*document\.querySelectorAll\('([^']+)'\);",
            script,
        )
        if re.search(rf"\b{re.escape(variable)}\b.*?\.hidden\s*=", script, re.S)
    ]
    assert hidden_selectors, "script never sets hidden on any selector"

    for selector in hidden_selectors:
        attr_names = re.findall(r"\[([a-zA-Z0-9_-]+)\]", selector)
        class_names: set[str] = set()
        for attr_name in attr_names:
            for class_attr in re.findall(
                rf'class="([^"]*)"[^>]*\b{re.escape(attr_name)}=',
                page,
            ):
                class_names.update(token for token in class_attr.split() if token)
        assert class_names, f"no class names found for hidden selector {selector!r}"
        for class_name in class_names:
            base_display = _declared_display(styles, f".{class_name}")
            if base_display is None:
                continue
            hidden_display = _declared_display(styles, f".{class_name}[hidden]")
            assert hidden_display == "none", (
                f".{class_name} sets display={base_display!r} but .{class_name}[hidden] "
                "does not set display: none"
            )


def _computed_seat_row_display(styles: str, *, hidden: bool) -> str:
    """Display for a setup seat row under this stylesheet, using a tiny cascade model."""
    # UA baseline for [hidden], then author rules in source order.
    display = "none" if hidden else "block"
    for selector, value in _display_declarations(styles):
        if selector == ".seat-row":
            display = value
        elif selector == ".seat-row[hidden]" and hidden:
            display = value
        elif selector == "[hidden]" and hidden:
            display = value
    return display


def test_no_argument_server_serves_a_setup_page_before_any_game_exists() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, page = _get(base, "/")

    assert status == 200
    assert "<!DOCTYPE html>" in page
    assert '<form method="post" action="/start">' in page
    assert 'name="player_count"' in page
    assert "Bot (disabled)" in page
    assert "Basic (disabled)" in page
    assert "Seat 1 (Red)" in page
    assert "Seat 2 (Yellow)" in page
    assert "Seat 3 (Blue)" in page
    assert "Seat 4 (White)" in page


def test_setup_page_lists_discovered_playtest_positions_with_blank_fresh_default() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, page = _get(base, "/")

    assert status == 200
    assert 'id="test_position"' in page
    assert '<option value="" selected>Deal a fresh game</option>' in page
    assert f'value="{PLAYTEST_CLOISTERS}"' in page
    assert f'value="{PLAYTEST_CLOISTERS_LOOP}"' in page
    assert f'value="{PLAYTEST_KOGGE_AND_CLOISTERS}"' in page
    assert f'value="{PLAYTEST_CONVERSIONS}"' in page
    assert f'value="{PLAYTEST_MOVEMENT}"' in page
    assert f'value="{PLAYTEST_PULPIT}"' in page
    assert ">cloisters_reach_2p<" in page
    assert ">cloisters_loop_2p<" in page
    assert ">kogge_and_cloisters_2p<" in page
    assert ">movement_2p<" in page
    assert ">pulpit_2p<" in page


def test_setup_page_hides_extra_rows_by_computed_display_not_only_hidden_attribute() -> None:
    page = play_server._render_setup_page(
        suggested_seed=4471,
        playtest_positions=play_server._available_playtest_positions(),
    )
    styles = _style_block(page)
    for player_count, shown in ((2, (1, 2)), (3, (1, 2, 3))):
        for seat in (1, 2, 3, 4):
            hidden = seat > player_count
            display = _computed_seat_row_display(styles, hidden=hidden)
            height = 0 if display == "none" else 1
            if seat in shown:
                assert display != "none", (player_count, seat, display)
                assert height > 0, (player_count, seat, height)
            else:
                assert display == "none", (player_count, seat, display)
                assert height == 0, (player_count, seat, height)


def test_setup_styles_pair_display_rules_with_hidden_overrides() -> None:
    page = play_server._render_setup_page(
        suggested_seed=4471,
        playtest_positions=play_server._available_playtest_positions(),
    )
    _assert_hidden_display_pairing(page)


def test_removing_hidden_display_override_is_caught() -> None:
    page = play_server._render_setup_page(
        suggested_seed=4471,
        playtest_positions=play_server._available_playtest_positions(),
    )
    mutated = page.replace(".seat-row[hidden] { display: none; }", "", 1)
    assert mutated != page, "mutation matched nothing"
    with pytest.raises(AssertionError, match=r"\.seat-row\[hidden\]"):
        _assert_hidden_display_pairing(mutated)


@pytest.mark.parametrize("player_count,expected_dummy", [(2, 6), (3, 4), (4, 0)])
def test_starting_counts_2_3_4_loads_matching_board_and_neutral_acolytes(
    player_count: int, expected_dummy: int
) -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, page = _post_form(base, "/start", _start_fields(player_count=player_count, seed=99))
        assert status == 200
        assert 'data-component="play-log"' in page
        state = _get_json(base, "/state.json")

    assert len(state["state"]["players"]) == player_count
    assert sum(int(value) for value in state["state"]["dummy_acolytes"]["total"]) == expected_dummy


def test_start_with_blank_test_position_still_deals_a_fresh_generated_game() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, page = _post_form(
            base,
            "/start",
            _start_fields(player_count=3, seed=4471, test_position=""),
        )
        state = _get_json(base, "/state.json")

    assert status == 200
    assert "New game - 3 players, seed 4471." in page
    assert len(state["state"]["players"]) == 3


def test_start_rejects_an_unknown_test_position_name() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, body = _post_form(
            base,
            "/start",
            _start_fields(
                player_count=4,
                seed=99,
                test_position="../../configs/board.json",
            ),
        )

    assert status == 422
    assert "Unknown test position" in json.loads(body)["error"]


@pytest.mark.parametrize(
    "position_name,position_label,expected_active_buildings,expected_resources",
    [
        (PLAYTEST_CLOISTERS, "cloisters_reach_2p", ["cloisters"], {"stone": 9, "silver": 9, "wheat": 9}),
        (PLAYTEST_CLOISTERS_LOOP, "cloisters_loop_2p", ["cloisters"], {"stone": 9, "silver": 9, "wheat": 9}),
        (PLAYTEST_KOGGE_AND_CLOISTERS, "kogge_and_cloisters_2p", ["kogge", "cloisters"], {"stone": 9, "silver": 9, "wheat": 9}),
        (PLAYTEST_CONVERSIONS, "conversions_2p", ["stone_yard", "grain_store"], {"stone": 9, "silver": 9, "wheat": 9}),
        (PLAYTEST_MOVEMENT, "movement_2p", ["cloisters", "dormitory"], {"stone": 4, "silver": 9, "wheat": 4}),
        (PLAYTEST_PULPIT, "pulpit_2p", [], {"stone": 0, "silver": 0, "wheat": 1}),
    ],
)
def test_starting_from_test_position_uses_the_file_count_and_seed(
    position_name: str,
    position_label: str,
    expected_active_buildings: list[str],
    expected_resources: dict[str, int],
) -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, page = _post_form(
            base,
            "/start",
            _start_fields(
                player_count=4,
                seed=1234,
                test_position=position_name,
            ),
        )
        state = _get_json(base, "/state.json")

    assert status == 200
    assert f"Loaded test position - {position_label}." in page
    assert len(state["state"]["players"]) == 2
    assert state["state"]["players"][0]["piety"] == 4
    assert state["state"]["players"][0]["resources"] == expected_resources
    assert (
        state["state"]["players"][0]["player_board_slots"]["active_buildings"]
        == expected_active_buildings
    )
    assert server.session.player_count == 2
    assert server.session.seed == 99


def test_starting_with_the_same_count_and_seed_twice_reproduces_the_same_state() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        _post_form(base, "/start", _start_fields(player_count=3, seed=4471))
        first = _get_json(base, "/state.json")
        status, setup_page = _post_form(base, "/new-game", {})
        assert status == 200
        assert '<form method="post" action="/start">' in setup_page
        _post_form(base, "/start", _start_fields(player_count=3, seed=4471))
        second = _get_json(base, "/state.json")

    assert first == second


def test_setup_session_facts_stay_out_of_scenarios_and_view_payloads() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        _post_form(base, "/start", _start_fields(player_count=3, seed=99))
        _ = _get_json(base, "/state.json")
        _ = _get_json(base, "/actions.json")

    assert server.session.game_loaded is True
    assert server.session.seat_roles == {
        "player_one": "human",
        "player_two": "human",
        "player_three": "human",
    }
    assert server._latest_generated_scenario is not None
    forbidden = ("seat_roles", "game_loaded", "setup_mode", "not_started", "session")
    for payload in (
        server._latest_generated_scenario,
        server.state_payload,
        server.payload,
        actions_document(server.state, server.config, server.state_payload),
    ):
        text = json.dumps(payload)
        for marker in forbidden:
            assert marker not in text


def test_json_routes_answer_clearly_before_a_game_exists() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        state_status, state_body = _get(base, "/state.json")
        actions_status, actions_body = _get(base, "/actions.json")

    assert state_status == 409
    assert actions_status == 409
    assert json.loads(state_body)["status"] == "no_game_loaded"
    actions = json.loads(actions_body)
    assert actions["status"] == "no_game_loaded"
    assert actions["count"] == 0
    assert actions["actions"] == []


def test_setup_started_board_opens_with_seed_line_and_restart_control() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, page = _post_form(base, "/start", _start_fields(player_count=3, seed=4471))
        refreshed_status, refreshed = _get(base, "/")

    assert status == 200
    assert refreshed_status == 200
    assert "New game - 3 players, seed 4471." in page
    assert "New game - 3 players, seed 4471." in refreshed
    assert 'class="session-reset"' in refreshed
    assert "Start a new game (discard this game)" in refreshed
    panel = refreshed[refreshed.index('data-component="play-turn"') : refreshed.index("</body>")]
    assert "session-reset" not in panel


def test_file_argument_still_serves_the_board_directly(tmp_path: Path) -> None:
    server = PlayServer(("127.0.0.1", 0), _generated(tmp_path))
    with _running(server) as base:
        status, page = _get(base, "/")

    assert status == 200
    assert "<!DOCTYPE html>" in page
    assert 'data-component="play-log"' in page
    assert '<form method="post" action="/start">' not in page
    assert "Start a new game (discard this game)" not in page


def test_every_playtest_scenario_loads_validates_and_can_be_served() -> None:
    checked = 0
    seen: set[str] = set()
    for path in sorted(PLAYTEST_SCENARIOS.glob("*.json")):
        _ = load_scenario(str(path))
        server = PlayServer(("127.0.0.1", 0), path)
        with _running(server) as base:
            status, page = _get(base, "/")
        assert status == 200
        assert 'data-component="play-log"' in page
        seen.add(path.name)
        checked += 1

    assert checked == 6
    assert seen == set(PLAYTEST_POSITION_NAMES)


def test_pulpit_playtest_offers_the_hired_step_for_hand_exercise() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_PULPIT))
    steps = play_server.turn_steps_payload(scenario.state, scenario.config)
    pulpit = next(step for step in steps if step["building_id"] == "pulpit")

    assert pulpit["source"] == "market"
    assert pulpit["hire_payment"] == "wheat"
    assert pulpit["ability"]["status_text"] == "Usable: pay 1 wheat to bank."
    assert pulpit["answers"] == [
        {"field": "building", "label": "Pulpit", "value": "pulpit"},
        {"field": "hire_payment", "label": "wheat", "value": "wheat"},
    ]
    assert pulpit["hire_text"] == "Hire Pulpit from market for 1 wheat."


def test_turn_step_answers_put_hire_payment_before_conversion_and_piety_destination() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS))
    player_two_turn = replace(scenario.state, active_player=PlayerId.PLAYER_TWO)
    steps = play_server.turn_steps_payload(player_two_turn, scenario.config)

    stone_yard = [step for step in steps if step["building_id"] == "stone_yard"]
    assert len(stone_yard) == 4
    assert {
        tuple(answer["field"] for answer in step["answers"])
        for step in stone_yard
    } == {("building", "hire_payment", "direction", "amount")}
    assert {step["hire_text"] for step in stone_yard} == {
        "Hire Stone Yard from Red for 1 resource of your choice."
    }

    indulgences = [step for step in steps if step["building_id"] == "indulgences"]
    assert indulgences
    assert {
        tuple(answer["field"] for answer in step["answers"])
        for step in indulgences
    } == {("building", "direction", "piety_destination")}


def test_cornucopia_ability_status_names_a_resource_choice_not_a_horn() -> None:
    source = BuildingAbilitySource(
        building_key="test_building",
        source_type="opponent_active_hire",
        owner="player_one",
        hire_resource="cornucopia",
        hire_cost=1,
        payable_to="player_one",
        usable=True,
    )

    assert play_server._building_ability_status_text(source) == (
        "Usable: pay 1 resource of your choice to Red."
    )


def test_opponent_hire_sentence_names_the_owner_as_its_source() -> None:
    source = BuildingAbilitySource(
        building_key="kogge",
        source_type="opponent_active_hire",
        owner="player_two",
        hire_resource="silver",
        hire_cost=1,
        payable_to="player_two",
        usable=True,
    )

    assert play_server._building_hire_sentence("Kogge", source) == (
        "Hire Kogge from Yellow for 1 silver."
    )


def test_market_hire_sentence_names_the_market_not_its_bank_payee() -> None:
    source = BuildingAbilitySource(
        building_key="library",
        source_type="live_market_hire",
        hire_resource="silver",
        hire_cost=1,
        payable_to="bank",
        usable=True,
    )

    assert play_server._building_hire_sentence("Library", source) == (
        "Hire Library from market for 1 silver."
    )


@pytest.mark.parametrize(
    ("scenario_name", "expected_hire_text"),
    (
        (
            "kogge_hire_market_city_to_east_001.json",
            "This route uses Kogge — 1 wheat to bank.",
        ),
        (
            "kogge_hire_opponent_city_to_west_001.json",
            "This route uses Kogge — 1 wheat to Yellow.",
        ),
    ),
)
def test_route_hire_arrow_carries_the_server_written_cost_fact(
    scenario_name: str, expected_hire_text: str
) -> None:
    scenario = load_scenario(str(SCENARIOS / scenario_name))
    hire_texts = {
        step["hire_text"]
        for candidate in play_server.turn_candidates(
            scenario.state,
            scenario.config,
            include_preview_effects=False,
        )
        for step in candidate["steps"]
        if "hire_text" in step
    }

    assert expected_hire_text in hire_texts


def test_city_to_east_candidates_share_kogge_cost_before_cloisters_is_settled() -> None:
    scenario = load_scenario(str(SCENARIOS / "kogge_cloisters_hire_both_market_001.json"))
    city_to_east_candidates = [
        candidate
        for candidate in play_server.turn_candidates(
            scenario.state, scenario.config, include_preview_effects=False
        )
        if [step["value"] for step in candidate["steps"][:2]] == [0, "city->east"]
    ]

    assert len(city_to_east_candidates) == 58
    assert {
        next(step["hire_text"] for step in candidate["steps"] if "hire_text" in step)
        for candidate in city_to_east_candidates
    } == {
        "This route uses Kogge — 1 wheat to bank.",
        "This route uses Kogge — 1 wheat to bank.\nand the Cloisters — 1 wheat to bank.",
    }


def test_route_hire_cost_fact_reuses_the_turn_step_sentence_helper(monkeypatch) -> None:
    scenario = load_scenario(str(SCENARIOS / "kogge_hire_market_city_to_east_001.json"))
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction) and action.sow_route_building_id == "kogge"
    )
    source = BuildingAbilitySource(
        building_key="kogge",
        source_type="live_market_hire",
        hire_resource="cornucopia",
        hire_cost=1,
        payable_to="bank",
        usable=True,
    )
    seen: list[BuildingAbilitySource] = []

    def shared_cost_phrase(resolved_source: BuildingAbilitySource) -> str:
        seen.append(resolved_source)
        return "the helper's shared price"

    monkeypatch.setattr(play_server, "building_ability_source", lambda *_args, **_kwargs: source)
    monkeypatch.setattr(play_server, "_building_hire_cost_phrase", shared_cost_phrase)

    route_sentence = play_server._route_hire_sentence(action, scenario.state, scenario.config)
    turn_step_sentence = play_server._building_hire_sentence("Kogge", source)

    assert route_sentence == "This route uses Kogge — the helper's shared price to bank."
    assert turn_step_sentence == "Hire Kogge from market for the helper's shared price."
    assert seen == [source, source]


def test_route_edge_metadata_states_each_building_dependency_for_the_page() -> None:
    scenario = load_scenario(str(SCENARIOS / "kogge_cloisters_hire_both_market_001.json"))
    candidates = play_server.turn_candidates(
        scenario.state, scenario.config, include_preview_effects=False
    )
    candidate = next(
        candidate
        for candidate in candidates
        if [step["value"] for step in candidate["steps"] if step["kind"] == "edge"]
        == ["city->north", "north->city", "city->east"]
    )
    edges = [step for step in candidate["steps"] if step["kind"] == "edge"]

    assert candidate["family"] == [0, 1]
    route_buildings_by_index = {
        family["i"]: family for family in play_server._ROUTE_BUILDING_PRESENTATION
    }
    assert [
        None if step.get("family") is None else route_buildings_by_index[step["family"]]
        for step in edges
    ] == [
        None,
        {"i": 0, "building_id": "kogge", "paint": "route-opening", "priority": 1},
        {"i": 1, "building_id": "cloisters", "paint": "route-extra-step", "priority": 2},
    ]


@pytest.mark.parametrize(
    ("scenario_name", "expected_labels"),
    (
        (
            "allocation_hire_infirmary_market_001.json",
            {"Don't hire", "Hire Infirmary from market"},
        ),
        (
            "allocation_hire_infirmary_opponent_001.json",
            {"Don't hire", "Hire Infirmary from player_two"},
        ),
        (
            "deep_round_eighteen_seed_seven_two_player_001.json",
            {
                "Don't hire",
                "Hire Infirmary from market",
                "Hire Mint from market",
                "Hire Well from market",
            },
        ),
    ),
)
def test_sow_hire_options_name_the_source_without_naming_a_payment_stock(
    scenario_name: str, expected_labels: set[str]
) -> None:
    scenario = load_scenario(str(SCENARIOS / scenario_name))
    labels = {
        step["label"]
        for candidate in play_server.turn_candidates(
            scenario.state,
            scenario.config,
            include_preview_effects=False,
        )
        for step in candidate["steps"]
        if step["kind"] == "hire"
    }

    assert labels == expected_labels


def test_sow_hire_label_leaves_the_cost_to_its_following_payment_step(monkeypatch) -> None:
    scenario = load_scenario(str(SCENARIOS / "allocation_hire_infirmary_market_001.json"))
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction) and action.hired_building_id == "infirmary"
    )
    source = BuildingAbilitySource(
        building_key="infirmary",
        source_type="live_market_hire",
        hire_resource="cornucopia",
        hire_cost=1,
        payable_to="bank",
        usable=True,
    )
    seen: list[BuildingAbilitySource] = []

    def shared_cost_phrase(resolved_source: BuildingAbilitySource) -> str:
        seen.append(resolved_source)
        return "the helper's shared price"

    monkeypatch.setattr(play_server, "building_ability_source", lambda *_args, **_kwargs: source)
    monkeypatch.setattr(play_server, "_building_hire_cost_phrase", shared_cost_phrase)

    sow_step, _fields = play_server._hire_step(action, scenario.state, scenario.config)
    turn_step_sentence = play_server._building_hire_sentence("Infirmary", source)

    assert sow_step["label"] == "Hire Infirmary from market"
    assert turn_step_sentence == "Hire Infirmary from market for the helper's shared price."
    assert seen == [source]


def test_fixed_hire_payment_immediately_names_the_cost_and_building() -> None:
    scenario = load_scenario(SCENARIOS / "allocation_hire_infirmary_market_001.json")
    actions = {
        action_id(action): action for action in legal_actions(scenario.state, scenario.config)
    }
    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        actions=list(actions.values()),
        include_preview_effects=False,
    )
    paid = next(
        candidate
        for candidate in candidates
        if any(
            step["kind"] == "hire" and step["value"] == "infirmary:market"
            for step in candidate["steps"]
        )
    )
    declined = next(
        candidate
        for candidate in candidates
        if any(step["kind"] == "hire" and step["value"] == "none" for step in candidate["steps"])
    )

    paid_hire_index = next(
        index for index, step in enumerate(paid["steps"]) if step["kind"] == "hire"
    )
    declined_hire_index = next(
        index for index, step in enumerate(declined["steps"]) if step["kind"] == "hire"
    )
    assert paid["steps"][paid_hire_index]["label"] == "Hire Infirmary from market"
    payment = paid["steps"][paid_hire_index + 1]
    assert (payment["kind"], payment["value"], payment["prompt"]) == (
        "resource",
        "wheat",
        "player_one: Pay 1 wheat to hire the Infirmary.",
    )
    assert declined["steps"][declined_hire_index + 1]["kind"] == "arrangement"
    before = scenario.state.player_state(scenario.state.active_player).resources
    declined_result = apply_action(
        scenario.state,
        actions[declined["action_id"]],
        scenario.config,
    )
    after = declined_result.state.player_state(scenario.state.active_player).resources
    assert after == before


def test_owned_bank_substitution_is_a_hire_stock_before_arrangement() -> None:
    scenario = load_scenario(SCENARIOS / "allocation_hire_infirmary_chapter_house_bank_001.json")
    actions = {
        action_id(action): action for action in legal_actions(scenario.state, scenario.config)
    }
    candidates = [
        candidate
        for candidate in play_server.turn_candidates(
            scenario.state,
            scenario.config,
            actions=list(actions.values()),
            include_preview_effects=False,
        )
        if any(
            step["kind"] == "hire" and step["value"] == "infirmary:market"
            for step in candidate["steps"]
        )
    ]
    groups: dict[tuple[Any, ...], list[dict]] = {}
    for candidate in candidates:
        resource_index = next(
            index for index, step in enumerate(candidate["steps"]) if step["kind"] == "resource"
        )
        key = tuple(
            step["value"]
            for index, step in enumerate(candidate["steps"])
            if index != resource_index
        )
        groups.setdefault(key, []).append(candidate)
    siblings = next(group for group in groups.values() if len(group) == 2)
    by_stock = {
        next(step["value"] for step in candidate["steps"] if step["kind"] == "resource"):
        candidate
        for candidate in siblings
    }

    assert set(by_stock) == {"silver", "wheat"}
    before = scenario.state.player_state(scenario.state.active_player).resources
    for stock, candidate in by_stock.items():
        steps = candidate["steps"]
        hire_index = next(index for index, step in enumerate(steps) if step["kind"] == "hire")
        payment = steps[hire_index + 1]
        assert payment["kind"] == "resource"
        assert payment["prompt"] == (
            "player_one: The Bank lets you pay in coins instead of wheat. Choose how to pay."
        )
        assert all(step["kind"] != "combination" for step in steps[hire_index + 1 :])

        result = apply_action(scenario.state, actions[candidate["action_id"]], scenario.config)
        after = result.state.player_state(scenario.state.active_player).resources
        assert getattr(before, stock) - getattr(after, stock) == 1
        other = "wheat" if stock == "silver" else "silver"
        assert getattr(before, other) == getattr(after, other)


def test_turn_script_never_names_a_building_to_order_answers() -> None:
    script = Path("tools/ui_debug/play_view_turn.js").read_text(encoding="utf-8")
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS))
    catalogue_ids = {building.id for building in scenario.config.buildings.catalogue}
    script_literals = re.findall(r'''(?<![A-Za-z0-9_])['"]([a-z][a-z0-9_]*)['"]''', script)
    named_buildings = {literal for literal in script_literals if literal in catalogue_ids}

    # These relocation previews need their visual treatment until the renderer carries it. The
    # subset means their exception can shrink, but a newly hardcoded building cannot slip in.
    assert named_buildings <= set(TURN_SCRIPT_RELOCATION_BUILDING_LITERAL_EXEMPTIONS)
    assert not {"kogge", "cloisters"} & named_buildings


def test_turn_script_control_updates_do_not_set_offered_attributes() -> None:
    script = Path("tools/ui_debug/play_view_turn.js").read_text(encoding="utf-8")
    control_updates = script[
        script.index("function setControl"):script.index("function setConfirmLabel")
    ]

    assert "data-turn-offered" not in control_updates


def test_cloisters_reach_playtest_position_has_expected_action_totals() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS))
    actions = list(legal_actions(scenario.state, scenario.config))
    skipped = sum(
        1
        for action in actions
        if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None
    )
    assert len(actions) == 220
    assert skipped == 165
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS)
    try:
        assert len(server.payload["turn_candidates"]) == 220
    finally:
        server.server_close()


def test_cloisters_reach_playtest_turn_candidates_have_no_dead_edge_steps() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS)
    try:
        drawn = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
        dead = _dead_candidates_by_missing_edges(server.payload["turn_candidates"], drawn)
        assert not dead, f"playtest candidates still ask for undrawn arrows: {dead[:10]}"
    finally:
        server.server_close()


def test_sow_payload_auto_advances_only_unambiguous_cloisters_edges() -> None:
    """The server, not the page, distinguishes a forced route from a route choice."""
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS))
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    assert {
        step["kind"]
        for candidate in candidates
        for step in candidate["steps"]
        if step.get("auto")
    } == {"edge"}

    def offered(prefix: list[object]) -> set[tuple[object, object, tuple[int, ...]]]:
        index = len(prefix)
        return {
            (
                candidate["steps"][index]["kind"],
                candidate["steps"][index]["value"],
                tuple(candidate["steps"][index].get("auto", [])),
            )
            for candidate in candidates
            if len(candidate["steps"]) > index
            and [step["value"] for step in candidate["steps"][:index]] == prefix
        }

    assert offered([1]) == {
        ("edge", "north->north_east", (0, 2)),
        ("edge", "north->north_east", (2,)),
    }
    assert offered([1, "north->north_east"]) == {
        ("edge", "north_east->east", (0, 2)),
        ("edge", "north_east->east", (2,)),
    }
    assert offered([1, "north->north_east", "north_east->east"]) == {
        ("duty", 2, ()),
        ("duty", 3, ()),
        ("duty", 4, ()),
        ("duty", 7, ()),
        ("edge", "east->city", ()),
        ("edge", "east->south_east", ()),
    }


def _turn_candidate_frontiers(candidates: list[dict]) -> list[dict[str, Any]]:
    """Group candidate steps exactly as the page groups its next answer."""
    frontiers: dict[tuple[Any, ...], dict[str, Any]] = {}
    for candidate_index, candidate in enumerate(candidates):
        prefix: list[Any] = []
        for step_index, step in enumerate(candidate["steps"]):
            key = tuple(prefix)
            frontier = frontiers.setdefault(
                key,
                {
                    "prefix": key,
                    "steps": [],
                    "cursor": {"candidateIndex": candidate_index, "depth": step_index},
                },
            )
            frontier["steps"].append(step)
            prefix.append(play_server._frontier_value(step["value"]))
    return list(frontiers.values())


def _distinct_frontier_options(frontier: dict[str, Any]) -> dict[tuple[Any, Any], dict]:
    return {
        (step["kind"], play_server._frontier_value(step["value"])): step
        for step in frontier["steps"]
    }


def _route_family_selections(family_indexes: list[int]) -> list[frozenset[int]]:
    """Every enabled-family combination the server evaluates for this candidate set."""
    return [
        frozenset(family for index, family in enumerate(family_indexes) if mask & (1 << index))
        for mask in range(1 << len(family_indexes))
    ]


def _candidate_is_reachable_with_families(candidate: dict, selection: frozenset[int]) -> bool:
    return set(candidate.get("family", ())).issubset(selection)


def _auto_advance_for_families(step: dict, selection: frozenset[int]) -> bool:
    selection_mask = sum(1 << family for family in selection)
    return selection_mask in step.get("auto", [])


def _auto_advance_selection_masks(family_indexes: list[int]) -> set[int]:
    """The masks the server can publish for the exact family index list it named."""
    return {
        sum(1 << family for index, family in enumerate(family_indexes) if mask & (1 << index))
        for mask in range(1 << len(family_indexes))
    }


def _resting_auto_advance_family_mask(
    abilities: list[dict[str, Any]], families: tuple[dict[str, str], ...], family_indexes: list[int]
) -> int:
    """Read the route visibility the page starts from, using only server-written ability state."""
    visibility = {
        ability["building_id"]: ability.get("family_visibility") for ability in abilities
    }
    families_by_index = {family["i"]: family for family in families}
    return sum(
        1 << index
        for index in family_indexes
        if visibility.get(families_by_index[index]["building_id"]) == "always"
    )


def _assert_auto_advance_frontiers(
    scenario_name: str, candidates: list[dict], family_indexes: list[int]
) -> int:
    """Check the metadata whose only consumer is the generic page loop.

    A route toggle changes which candidate families the page can show, so its automatic marker is
    correct only relative to that exact server-enumerated selection.
    """
    checked = 0
    for selection in _route_family_selections(family_indexes):
        reachable = [
            candidate
            for candidate in candidates
            if _candidate_is_reachable_with_families(candidate, selection)
        ]
        frontiers = _turn_candidate_frontiers(reachable)
        for frontier in frontiers:
            options = _distinct_frontier_options(frontier)
            marked = [
                step
                for step in frontier["steps"]
                if _auto_advance_for_families(step, selection)
            ]
            if marked:
                assert all(step["kind"] == "edge" for step in marked), (
                    f"{scenario_name} marked a non-edge automatic for {sorted(selection)!r} at "
                    f"{frontier['prefix']!r}: "
                    f"{[(step['kind'], step['value']) for step in marked]!r}"
                )
                assert len(options) == 1, (
                    f"{scenario_name} marked an edge automatic for {sorted(selection)!r} at its "
                    f"multi-option frontier {frontier['prefix']!r}: {list(options)!r}"
                )
            sole_steps = next(iter(options.values())) if len(options) == 1 else None
            offered_sole_steps = (
                [
                    step
                    for step in frontier["steps"]
                    if (step["kind"], play_server._frontier_value(step["value"]))
                    == (sole_steps["kind"], play_server._frontier_value(sole_steps["value"]))
                ]
                if sole_steps is not None
                else []
            )
            expected = (
                sole_steps is not None
                and sole_steps["kind"] == "edge"
                and not any("hire_text" in step for step in offered_sole_steps)
            )
            assert len(marked) == (len(frontier["steps"]) if expected else 0), (
                f"{scenario_name} auto_advance did not match family selection "
                f"{sorted(selection)!r} at {frontier['prefix']!r}: {list(options)!r}"
            )
        checked += len(frontiers)
    return checked


def test_auto_advance_is_exactly_the_unambiguous_edge_at_every_corpus_frontier() -> None:
    """Building fixtures must not get a step kind the generic automatic loop swallows."""
    checked = 0
    top_level_paths = sorted(SCENARIOS.glob("*.json"))
    playtest_paths = sorted(PLAYTEST_SCENARIOS.glob("*.json"))
    for scenario_path in [*top_level_paths, *playtest_paths]:
        scenario = load_scenario(str(scenario_path))
        payload = play_server.route_family_payload(scenario.state, scenario.config)
        candidates = payload["turn_candidates"]
        family_indexes = payload["auto_family_indexes"]
        resting_mask = _resting_auto_advance_family_mask(
            payload["building_abilities"], payload["families"], family_indexes
        )
        assert resting_mask in _auto_advance_selection_masks(family_indexes), (
            f"{scenario_path.name} resting family visibility produced {resting_mask}, outside "
            f"the server's selections for {family_indexes!r}"
        )
        checked += _assert_auto_advance_frontiers(scenario_path.name, candidates, family_indexes)

    assert len(top_level_paths) >= 314, (
        f"only {len(top_level_paths)} top-level scenarios were checked"
    )
    assert [path.name for path in playtest_paths] == sorted(PLAYTEST_POSITION_NAMES)
    # This now counts every offered family selection, each with its own page-visible frontier.
    assert checked >= 9000, f"only {checked} corpus selection-frontiers were checked"


def test_every_auto_mask_uses_only_server_enumerated_family_bits(play_payload_corpus) -> None:
    """A mask with an unknown bit makes the page silently discard an automatic continuation."""
    checked_masks = 0
    unknown_masks: list[tuple[str, str | None, int, int, tuple[int, ...]]] = []
    for scenario_path, payload in play_payload_corpus:
        family_indexes = payload["auto_family_indexes"]
        allowed_mask = sum(1 << index for index in family_indexes)
        for candidate in payload["turn_candidates"]:
            for step in candidate["steps"]:
                for mask in step.get("auto", ()):
                    checked_masks += 1
                    unknown_bits = mask & ~allowed_mask
                    if unknown_bits:
                        unknown_masks.append(
                            (
                                scenario_path.name,
                                candidate["action_id"],
                                mask,
                                unknown_bits,
                                tuple(family_indexes),
                            )
                        )

    assert checked_masks > 0 and not unknown_masks, (
        f"checked {checked_masks} automatic masks; masks with unknown family bits: "
        f"{unknown_masks[:10]}"
    )


def test_family_visibility_appears_only_on_offered_route_family_buildings(
    play_payload_corpus,
) -> None:
    """The page must never receive a route toggle for a building this turn did not offer."""
    checked_visibility = 0
    unexpected_visibility: list[tuple[str, str, str, tuple[str, ...]]] = []
    for scenario_path, payload in play_payload_corpus:
        offered_buildings = tuple(
            sorted(play_server._route_family_building_ids(payload["auto_family_indexes"]))
        )
        ability_groups = [("current", payload["building_abilities"])]
        ability_groups.extend(
            (window, payload["building_ability_windows"][window]["abilities"])
            for window in ("beginning", "sow", "end")
        )
        for window, abilities in ability_groups:
            for ability in abilities:
                if "family_visibility" not in ability:
                    continue
                checked_visibility += 1
                if ability["building_id"] not in offered_buildings:
                    unexpected_visibility.append(
                        (
                            scenario_path.name,
                            window,
                            ability["building_id"],
                            offered_buildings,
                        )
                    )

    assert checked_visibility > 0 and not unexpected_visibility, (
        f"checked {checked_visibility} family-visibility fields; unexpected fields: "
        f"{unexpected_visibility[:10]}"
    )


def _movement_payload_after_relocation(building_id: str, selected_position: int) -> dict:
    """Apply one committed relocation so route metadata is measured on its resulting sow."""
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    relocation = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.building_id == building_id and step.selected_position == selected_position
    )
    state = apply_turn_step(scenario.state, scenario.config, relocation)
    return play_server.route_family_payload(state, scenario.config)


def _frontier_steps_for_families(
    candidates: list[dict], prefix: tuple[object, ...], selection: frozenset[int]
) -> list[dict]:
    return [
        candidate["steps"][len(prefix)]
        for candidate in candidates
        if _candidate_is_reachable_with_families(candidate, selection)
        and len(candidate["steps"]) > len(prefix)
        and tuple(step["value"] for step in candidate["steps"][: len(prefix)]) == prefix
    ]


def test_dormitory_relocation_auto_advance_respects_the_kogge_toggle() -> None:
    """A hidden Kogge reversal cannot make the free City continuations look ambiguous."""
    payload = _movement_payload_after_relocation("dormitory", selected_position=4)
    candidates = payload["turn_candidates"]
    empty = frozenset()
    kogge = frozenset({play_server._ROUTE_FAMILY_BY_BUILDING_ID["kogge"].i})
    full = frozenset(payload["auto_family_indexes"])

    for prefix, expected_edge in (
        ((0, "city->south"), "south->south_west"),
        ((0, "city->north"), "north->north_east"),
    ):
        free_steps = _frontier_steps_for_families(candidates, prefix, empty)
        assert {step["value"] for step in free_steps} == {expected_edge}
        assert all(_auto_advance_for_families(step, empty) for step in free_steps)

        for selection in (kogge, full):
            steps = _frontier_steps_for_families(candidates, prefix, selection)
            assert len({step["value"] for step in steps}) == 2
            assert not any(_auto_advance_for_families(step, selection) for step in steps)


def test_inquisition_relocation_auto_advance_respects_the_kogge_toggle() -> None:
    """The free Construct sow advances twice, but a Kogge selection keeps both decisions visible."""
    payload = _movement_payload_after_relocation("inquisition", selected_position=4)
    candidates = payload["turn_candidates"]
    empty = frozenset()
    kogge = frozenset({play_server._ROUTE_FAMILY_BY_BUILDING_ID["kogge"].i})
    full = frozenset(payload["auto_family_indexes"])

    first_prefix = (4,)
    second_prefix = (4, "south_east->south")
    for prefix, expected_edge in (
        (first_prefix, "south_east->south"),
        (second_prefix, "south->south_west"),
    ):
        free_steps = _frontier_steps_for_families(candidates, prefix, empty)
        assert {step["value"] for step in free_steps} == {expected_edge}
        assert all(_auto_advance_for_families(step, empty) for step in free_steps)

        for selection in (kogge, full):
            steps = _frontier_steps_for_families(candidates, prefix, selection)
            assert not any(_auto_advance_for_families(step, selection) for step in steps)


def test_cloisters_loop_playtest_turn_candidates_have_no_dead_edge_steps() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP)
    try:
        drawn = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
        dead = _dead_candidates_by_missing_edges(server.payload["turn_candidates"], drawn)
        assert not dead, f"loop playtest candidates still ask for undrawn arrows: {dead[:10]}"
    finally:
        server.server_close()


@pytest.mark.parametrize(
    "position_name,expected_arrow_count,expected_reversals",
    [
        (PLAYTEST_CLOISTERS, 12, frozenset()),
        (PLAYTEST_CLOISTERS_LOOP, 12, frozenset()),
        (PLAYTEST_KOGGE_AND_CLOISTERS, 16, CITY_REVERSAL_ARROWS),
    ],
)
def test_play_view_draws_only_position_usable_city_reversal_arrows(
    position_name: str,
    expected_arrow_count: int,
    expected_reversals: frozenset[str],
) -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / position_name)
    try:
        drawn = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
        assert len(drawn) == expected_arrow_count
        assert (drawn & CITY_REVERSAL_ARROWS) == expected_reversals
    finally:
        server.server_close()


def test_kogge_and_cloisters_playtest_position_has_expected_totals() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_KOGGE_AND_CLOISTERS))
    actions = list(legal_actions(scenario.state, scenario.config))
    skipped = sum(
        1
        for action in actions
        if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None
    )
    board = scenario.config.board
    city = board.index_for_name("city")
    north = board.index_for_name("north")
    south = board.index_for_name("south")
    east = board.index_for_name("east")
    west = board.index_for_name("west")
    against_flow_spokes = {(north, city), (south, city), (city, east), (city, west)}
    against_flow = 0
    for action in actions:
        if not isinstance(action, FullTurnAction):
            continue
        walked = (action.origin, *action.route)
        if any(
            (walked[index], walked[index + 1]) in against_flow_spokes
            for index in range(len(walked) - 1)
        ):
            against_flow += 1

    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_KOGGE_AND_CLOISTERS)
    try:
        page = render_play_view_from_payload(server.payload)
        reversal_occurrences = Counter(
            str(step["value"])
            for candidate in server.payload["turn_candidates"]
            for step in candidate["steps"]
            if step["kind"] == "edge" and str(step["value"]) in CITY_REVERSAL_ARROWS
        )
        assert len(server.payload["turn_candidates"]) == 991
        assert len(page.encode("utf-8")) < 2_000_000
        assert reversal_occurrences == Counter(
            {
                "north->city": 145,
                "south->city": 252,
                "city->east": 365,
                "city->west": 338,
            }
        )
    finally:
        server.server_close()

    max_on_any_duty_tile_after_turn = 0
    for action in actions:
        if not isinstance(action, FullTurnAction):
            continue
        result = apply_action(scenario.state, action, scenario.config)
        player_one = result.state.player_state(PlayerId.PLAYER_ONE)
        max_on_any_duty_tile_after_turn = max(
            max_on_any_duty_tile_after_turn,
            max(
                int(value)
                for position, value in enumerate(player_one.workforce.mancala)
                if position != city
            ),
        )

    assert len(actions) == 1044
    assert skipped == 909
    assert against_flow == 543
    assert max_on_any_duty_tile_after_turn <= 3


def test_kogge_and_cloisters_playtest_turn_candidates_have_no_dead_edge_steps() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_KOGGE_AND_CLOISTERS)
    try:
        drawn = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
        dead = _dead_candidates_by_missing_edges(server.payload["turn_candidates"], drawn)
        assert not dead, (
            f"kogge+cloisters playtest candidates still ask for undrawn arrows: {dead[:10]}"
        )
    finally:
        server.server_close()


def test_conversions_playtest_exposes_and_applies_all_conversion_paths() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS))
    actions = list(legal_actions(scenario.state, scenario.config))
    candidates = play_server.turn_candidates(scenario.state, scenario.config, actions=actions)
    steps = list(turn_steps(scenario.state, scenario.config))

    assert len(actions) == 63
    assert (
        len(candidates),
        sum(candidate["action_id"] is None for candidate in candidates),
    ) == (63, 0)
    assert {step.building_id for step in steps} == {
        "stone_yard",
        "grain_store",
        "brewery",
        "indulgences",
    }
    hired = [step for step in steps if step.hire_payment is not None]
    assert hired and {step.hire_payment for step in hired} == {"wheat", "stone", "silver"}

    after_grain_store = apply_turn_step(
        scenario.state,
        scenario.config,
        next(step for step in steps if step.building_id == "grain_store"),
    )
    assert {step.building_id for step in turn_steps(after_grain_store, scenario.config)} == {
        "stone_yard",
        "brewery",
        "indulgences",
    }


def test_sell_piety_payload_silver_is_the_engine_conversion_delta_across_the_corpus() -> None:
    observations = 0
    for scenario_path in sorted(SCENARIOS.rglob("*.json")):
        try:
            scenario = load_scenario(str(scenario_path))
        except Exception:
            continue
        steps = list(turn_steps(scenario.state, scenario.config))
        payload_by_id = {
            entry["step_id"]: entry
            for entry in play_server.turn_steps_payload(scenario.state, scenario.config)
        }
        for step in steps:
            if not isinstance(step, BuildingConversionStep):
                continue
            if step.direction != "sell_piety":
                continue
            observations += 1
            before = scenario.state.player_state(scenario.state.active_player)
            result = apply_turn_step(scenario.state, scenario.config, step)
            after = result.player_state(scenario.state.active_player)
            total_silver = after.resources.silver - before.resources.silver
            hire_silver = sum(
                -int(dict(event.details).get("amount", 0))
                for event in result.events
                if event.event_type is EventType.BUILDING_HIRED
                and event.action_id == play_server.turn_step_id(step)
                and dict(event.details).get("resource") == "silver"
            )
            conversion_silver = total_silver - hire_silver
            assert conversion_silver == abs(after.piety - before.piety)
            assert (
                payload_by_id[play_server.turn_step_id(step)]["silver_delta"] == conversion_silver
            )
    assert observations > 0


def _complete_first_available_turn(state, config):
    """Resolve the first offered full turn, including its mandatory End of Turn pass."""
    for _ in range(20):
        actions = list(legal_actions(state, config))
        assert actions, "playtest stopped before it offered a full turn"
        result = apply_action(state, actions[0], config)
        if result.state.turn_progress.resolution_committed:
            return apply_action(result.state, EndTurnAction(), config).state
        state = result.state
    raise AssertionError("playtest never reached an End of Turn window")


def test_conversions_playtest_runs_for_twenty_turns() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS))
    state = scenario.state
    for _ in range(20):
        state = _complete_first_available_turn(state, scenario.config)


def test_conversions_playtest_reaches_metadata_driven_alms_season_end() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS))
    state = scenario.state
    season_end_action_count = None
    season_end_game_turn = None
    season_end_events: list[str] = []
    for turn_index in range(1, 100):
        actions = list(legal_actions(state, scenario.config))
        assert actions, "conversion playtest ended before its first season end"
        if state.turn_progress.resolution_committed:
            assert actions == [EndTurnAction()]
        result = apply_action(state, actions[0], scenario.config)
        event_types = [event.event_type.value for event in result.events]
        if EventType.ALMS_SEASON_END.value in event_types:
            season_end_action_count = turn_index
            season_end_game_turn = result.state.turn
            season_end_events = event_types
            state = result.state
            break
        state = result.state

    assert season_end_action_count == 16
    assert season_end_game_turn == 6
    assert state.timing.round_number == 5
    assert {
        EventType.ALMS_SEASON_END.value,
        EventType.ALMS_SEASON_REWARD.value,
        EventType.ALMS_RESET.value,
    } <= set(season_end_events)


def test_every_committed_turn_candidate_edge_is_drawn(corpus_actions) -> None:
    checked_candidates = 0
    dead: list[tuple[str, list[tuple[str | None, list[str]]]]] = []
    for scenario_path, scenario, actions in corpus_actions:
        payload = _payload_from_corpus(scenario, actions)
        drawn = set(_arrows_drawn(render_play_view_from_payload(payload)))
        candidates = payload["turn_candidates"]
        checked_candidates += len(candidates)
        # Structural now for City reversals (they are drawn from candidate edges), still a real
        # corpus guard for the always-drawn map arrows.
        missing = _dead_candidates_by_missing_edges(candidates, drawn)
        if missing:
            dead.append((scenario_path.name, missing[:5]))

    assert checked_candidates > 0, "committed corpus had no turn candidates"
    assert not dead, f"{len(dead)} scenarios still have dead edge candidates: {dead[:5]}"


def test_every_drawn_city_reversal_arrow_is_used_by_a_candidate(corpus_actions) -> None:
    checked_reversal_arrows = 0
    orphaned: list[tuple[str, list[str]]] = []
    for scenario_path, scenario, actions in corpus_actions:
        payload = _payload_from_corpus(scenario, actions)
        drawn = set(_arrows_drawn(render_play_view_from_payload(payload)))
        drawn_reversals = drawn & CITY_REVERSAL_ARROWS
        checked_reversal_arrows += len(drawn_reversals)
        candidate_edges = _candidate_edges(payload["turn_candidates"])
        unused = sorted(drawn_reversals - candidate_edges)
        if unused:
            orphaned.append((scenario_path.name, unused))

    assert checked_reversal_arrows > 0, "committed corpus drew no City reversal arrows to verify"
    assert not orphaned, (
        f"{len(orphaned)} scenarios drew unused City reversal arrows: {orphaned[:5]}"
    )


def test_corpus_has_no_refused_groups_blocked_on_kogge_cloisters_route_building_fields(
    corpus_actions, playtest_actions
) -> None:
    blocked: list[tuple[str, tuple[str, ...], int]] = []
    for scenario_path, scenario, actions in _all_corpus_actions(corpus_actions, playtest_actions):
        payload = _payload_from_corpus(scenario, actions)
        for candidate in payload["turn_candidates"]:
            if candidate.get("action_id") is not None:
                continue
            unresolved = tuple(sorted(str(name) for name in candidate.get("unresolved", [])))
            if ROUTE_BUILDING_REFUSAL_FIELDS <= set(unresolved):
                blocked.append((scenario_path.name, unresolved, int(candidate.get("variants", 0))))

    assert not blocked, (
        f"route-building refusals remained in {len(blocked)} candidate groups: {blocked[:10]}"
    )


def test_space_questions_never_overlap_on_one_reachable_prefix(
    corpus_actions, playtest_actions
) -> None:
    """One ring family is safe only while at most one wheel question is live at once."""
    overlaps: list[tuple[str, tuple[str, ...], tuple[Any, ...]]] = []
    for scenario_path, scenario, actions in _all_corpus_actions(corpus_actions, playtest_actions):
        payload = _payload_from_corpus(scenario, actions)
        for prefix, kinds in _offered_kinds_by_prefix(payload["turn_candidates"]).items():
            simultaneous = tuple(sorted(SPACE_QUESTION_KINDS & kinds))
            if len(simultaneous) > 1:
                overlaps.append((scenario_path.name, simultaneous, prefix))

    assert not overlaps, (
        f"wheel question kinds overlapped on {len(overlaps)} prefixes: {overlaps[:10]}"
    )


def test_hire_payments_are_not_in_refusals(
    corpus_actions, playtest_actions
) -> None:
    hire_payment_blocked: list[tuple[str, tuple[str, ...], int]] = []
    refused = 0
    for scenario_path, scenario, actions in _all_corpus_actions(corpus_actions, playtest_actions):
        payload = _payload_from_corpus(scenario, actions)
        for candidate in payload["turn_candidates"]:
            if candidate.get("action_id") is not None:
                continue
            refused += 1
            unresolved = tuple(sorted(str(name) for name in candidate.get("unresolved", ())))
            unresolved_set = set(unresolved)
            if "hire_payments" in unresolved_set:
                hire_payment_blocked.append(
                    (scenario_path.name, unresolved, int(candidate.get("variants", 0)))
                )

    assert refused > 0, "corpus had no refused groups, so this checked nothing"
    assert not hire_payment_blocked, (
        f"hire_payments still block {len(hire_payment_blocked)} candidate groups: "
        f"{hire_payment_blocked[:10]}"
    )


def test_blocked_candidate_census_matches_the_current_affordance_backlog(
    corpus_actions, playtest_actions
) -> None:
    """The count should fall as affordances are built; a rise means something regressed."""
    blocked = Counter(
        tuple(candidate.get("unresolved", ()))
        for _scenario_path, scenario, actions in _all_corpus_actions(
            corpus_actions, playtest_actions
        )
        for candidate in _payload_from_corpus(scenario, actions)["turn_candidates"]
        if candidate.get("action_id") is None
    )

    expected = Counter(
        {
            ("construct_plan",): 8,
        }
    )

    assert blocked == expected, (
        f"blocked-candidate census moved from {sum(expected.values())} "
        f"to {sum(blocked.values())}: {blocked}"
    )


def test_optional_modifier_steps_are_atomic_server_written_options() -> None:
    own_scriptorium = load_scenario(
        str(SCENARIOS / "scriptorium_active_majority_selected_duty_001.json")
    )
    wagon_yard = load_scenario(
        str(SCENARIOS / "wagon_yard_active_free_hire_market_guild_001.json")
    )
    hired_scriptorium = load_scenario(
        str(SCENARIOS / "scriptorium_hire_market_majority_selected_duty_001.json")
    )
    hired_step = next(
        step
        for step in turn_steps(hired_scriptorium.state, hired_scriptorium.config)
        if step.building_id == "scriptorium"
    )
    after_hire = apply_turn_step(
        hired_scriptorium.state,
        hired_scriptorium.config,
        hired_step,
    )

    def options_at(scenario, resolution: str, *, state=None) -> list[dict[str, str]]:
        current = scenario.state if state is None else state
        candidates = play_server.turn_candidates(current, scenario.config)
        return sorted(
            (
                {
                    "value": str(step["value"]),
                    "label": str(step["label"]),
                    "prompt": str(step["prompt"]),
                }
                for candidate in candidates
                if any(
                    step["kind"] == "resolution" and step["value"] == resolution
                    for step in candidate["steps"]
                )
                for step in candidate["steps"]
                if step["kind"] == "combination"
                and str(step["value"]).startswith(("effective_acolyte:", "free_hire:"))
            ),
            key=lambda option: option["value"],
        )

    assert {
        "own_scriptorium": options_at(own_scriptorium, "clerical_devotion"),
        "hired_scriptorium": options_at(
            hired_scriptorium,
            "clerical_devotion",
            state=after_hire,
        ),
        "wagon_yard": options_at(wagon_yard, "clerical_devotion"),
    } == {
        "own_scriptorium": [
            {
                "value": "effective_acolyte:decline",
                "label": "Don't use the Scriptorium",
                "prompt": "player_one: Choose whether to use the Scriptorium.",
            },
            {
                "value": "effective_acolyte:scriptorium:own_active",
                "label": (
                    "Use the Scriptorium for +1 effective acolyte on occupied Duty tiles"
                ),
                "prompt": "player_one: Choose whether to use the Scriptorium.",
            },
        ],
        "hired_scriptorium": [
            {
                "value": "effective_acolyte:decline",
                "label": "Don't use the Scriptorium",
                "prompt": "player_one: Choose whether to use the Scriptorium.",
            },
            {
                "value": "effective_acolyte:scriptorium:committed",
                "label": (
                    "Use the Scriptorium for +1 effective acolyte on occupied Duty tiles"
                ),
                "prompt": "player_one: Choose whether to use the Scriptorium.",
            },
        ],
        "wagon_yard": [
            {
                "value": "free_hire:decline",
                "label": "Don't use the Wagon Yard",
                "prompt": "player_one: Choose whether to use the Wagon Yard's free hire.",
            },
            {
                "value": "free_hire:wagon_yard:guild:market",
                "label": "Use the Wagon Yard to hire Guild from the market for free",
                "prompt": "player_one: Choose whether to use the Wagon Yard's free hire.",
            },
        ],
    }


def test_wagon_yard_option_list_keeps_distinct_non_null_bundles() -> None:
    scenario = load_scenario(
        str(SCENARIOS / "wagon_yard_active_free_hire_market_guild_001.json")
    )
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.resolution is TurnResolutionType.CLERICAL_DEVOTION
    ]
    declined = next(
        action for action in actions if action.free_hire_enabler_building_id is None
    )
    market = next(
        action for action in actions if action.free_hire_target_building_source == "market"
    )
    opponent = replace(market, free_hire_target_building_source="player_two")

    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        actions=(declined, market, opponent),
        include_preview_effects=False,
    )
    options = {
        step["value"]
        for candidate in candidates
        for step in candidate["steps"]
        if step["kind"] == "combination" and str(step["value"]).startswith("free_hire:")
    }

    assert (options, [candidate["variants"] for candidate in candidates], {
        tuple(candidate["unresolved"]) for candidate in candidates
    }) == (
        {
            "free_hire:decline",
            "free_hire:wagon_yard:guild:market",
            "free_hire:wagon_yard:guild:player_two",
        },
        [1, 1, 1],
        {()},
    )


def test_no_refused_candidate_names_a_decided_field(corpus_actions, playtest_actions) -> None:
    decided_field_blocked: list[tuple[str, tuple[str, ...], int]] = []
    for scenario_path, scenario, actions in _all_corpus_actions(corpus_actions, playtest_actions):
        payload = _payload_from_corpus(scenario, actions)
        for candidate in payload["turn_candidates"]:
            if candidate.get("action_id") is not None:
                continue
            unresolved = tuple(sorted(str(name) for name in candidate.get("unresolved", ())))
            if set(unresolved) & set(play_server.DECIDED_FIELDS):
                decided_field_blocked.append(
                    (scenario_path.name, unresolved, int(candidate.get("variants", 0)))
                )

    assert not decided_field_blocked, (
        f"decided fields still block {len(decided_field_blocked)} candidate groups: "
        f"{decided_field_blocked[:10]}"
    )


def test_every_unresolved_field_has_server_written_player_text(
    corpus_actions, playtest_actions
) -> None:
    """The page may receive an engine field only beside the sentence it is to show."""
    scenarios_checked = 0
    fields_seen: set[str] = set()
    unnamed: list[tuple[str, str]] = []
    for scenario_path, scenario, actions in _all_corpus_actions(corpus_actions, playtest_actions):
        scenarios_checked += 1
        payload = _payload_from_corpus(scenario, actions)
        for candidate in payload["turn_candidates"]:
            unresolved = candidate["unresolved"]
            unresolved_text = candidate.get("unresolved_text", [])
            if len(unresolved) != len(unresolved_text):
                unnamed.append((scenario_path.name, ", ".join(unresolved)))
                continue
            fields_seen.update(unresolved)
            for field, text in zip(unresolved, unresolved_text, strict=True):
                if not isinstance(text, str) or not text:
                    unnamed.append((scenario_path.name, field))

    assert scenarios_checked == 324, "the player-wording check no longer walks the full corpus"
    assert not unnamed, f"unresolved fields without player text: {unnamed[:10]}"
    # Own-active Bank variants now have a whole payment step, so these fields are deliberately no
    # longer part of a corpus-wide unresolved candidate. Keep the corpus walk proving that exact
    # disappearance rather than letting a stale label-presence assertion call it a regression.
    assert fields_seen == set(play_server.UNRESOLVED_FIELD_TEXT) - set(
        play_server.OWN_ACTIVE_BANK_PAYMENT_FIELDS
    )


def test_an_unmapped_unresolved_field_stops_candidate_construction(
    monkeypatch, corpus_actions
) -> None:
    """MUTATION. A new residue field needs wording before a player can encounter it."""
    def opening_candidates():
        for _scenario_path, scenario, actions in corpus_actions:
            yield from play_server.turn_candidates(
                scenario.state,
                scenario.config,
                actions=actions,
                include_preview_effects=False,
            )

    with _one_field_gone_unasked_without_text(monkeypatch):
        with pytest.raises(RuntimeError, match="tithe_resource.*no player-facing name"):
            tuple(opening_candidates())


def test_an_undecided_turn_renders_the_server_written_field_name(
    monkeypatch, corpus_actions
) -> None:
    """The renderer reads the completed sentence, never the field that led to it."""
    with _one_field_gone_unasked(monkeypatch):
        candidate = next(
            candidate
            for _scenario_path, scenario, actions in corpus_actions
            for candidate in _payload_from_corpus(scenario, actions)["turn_candidates"]
            if UNPRESENTED in candidate["unresolved"]
        )
        page = render_play_view.render_turn_panel({"turn_candidates": [candidate]})

    assert {
        "server_words_shown": "which resource to tithe" in page,
        "engine_field_hidden": UNPRESENTED not in page,
    } == {"server_words_shown": True, "engine_field_hidden": True}


@pytest.mark.parametrize(
    ("position_name", "expected_refused"),
    [
        (PLAYTEST_CLOISTERS_LOOP, 0),
        (PLAYTEST_KOGGE_AND_CLOISTERS, 0),
    ],
)
def test_playtest_positions_have_expected_refused_counts(
    position_name: str, expected_refused: int
) -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / position_name)
    try:
        refused = sum(
            1 for candidate in server.payload["turn_candidates"] if candidate["action_id"] is None
        )
        assert refused == expected_refused
    finally:
        server.server_close()


def test_cloisters_route_permutation_spellings_land_in_the_same_state_record(
    corpus_actions, playtest_actions
) -> None:
    def completed_turn_record(scenario, action: FullTurnAction) -> dict:
        result = apply_action(scenario.state, action, scenario.config)
        state = result.state
        if state.turn_progress.resolution_committed:
            state = apply_action(state, EndTurnAction(), scenario.config).state
        return state_to_record(state)

    compared = 0
    mismatches: list[tuple[str, str, str, tuple[int, ...], tuple[int, ...]]] = []
    for scenario_path, scenario, all_actions in _all_corpus_actions(
        corpus_actions, playtest_actions
    ):
        actions = [
            action
            for action in all_actions
            if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None
        ]
        grouped: dict[tuple[Any, ...], list[FullTurnAction]] = {}
        for action in actions:
            key = (
                tuple(sorted(tuple(action.route or ()))),
                *(getattr(action, name) for name in play_server._FULL_TURN_FIELDS_EXCEPT_ROUTE),
            )
            grouped.setdefault(key, []).append(action)

        for spellings in grouped.values():
            if len(spellings) < 2:
                continue
            first, *others = spellings
            first_route = tuple(first.route or ())
            first_record = completed_turn_record(scenario, first)
            for other in others:
                other_route = tuple(other.route or ())
                if other_route == first_route:
                    continue
                compared += 1
                other_record = completed_turn_record(scenario, other)
                if other_record != first_record:
                    mismatches.append(
                        (
                            scenario_path.name,
                            action_id(first),
                            action_id(other),
                            first_route,
                            other_route,
                        )
                    )

    assert compared > 0, "corpus offered no route-order Cloisters spelling pairs to compare"
    assert not mismatches, (
        f"{len(mismatches)} route-order Cloisters spelling pairs changed resulting state: "
        f"{mismatches[:10]}"
    )


def test_hire_payments_stays_in_residue_for_full_turn_actions() -> None:
    scenario = load_scenario(str(SCENARIOS / "building_hire_opponent_owned_001.json"))
    action = next(
        (
            candidate
            for candidate in legal_actions(scenario.state, scenario.config)
            if isinstance(candidate, FullTurnAction) and tuple(candidate.hire_payments or ())
        ),
        None,
    )
    assert action is not None, "fixture offered no action carrying hire_payments"
    assert "hire_payments" in play_server._residue_fields(action)


def test_settled_candidates_never_alias_more_than_one_legal_action(
    corpus_actions, playtest_actions
) -> None:
    aliased: list[tuple[str, str, int, list[str]]] = []
    settled = 0
    for scenario_path, scenario, actions in _all_corpus_actions(corpus_actions, playtest_actions):
        payload = _payload_from_corpus(scenario, actions)
        for candidate in payload["turn_candidates"]:
            if candidate.get("action_id") is None:
                continue
            settled += 1
            variants = int(candidate.get("variants", 0))
            if variants == 1:
                continue
            aliased.append(
                (
                    scenario_path.name,
                    str(candidate["action_id"]),
                    variants,
                    [
                        f"{step.get('kind')}={step.get('value')}"
                        for step in candidate.get("steps", ())[:8]
                    ],
                )
            )

    assert settled > 0, "corpus had no settled candidates, so this checked nothing"
    assert not aliased, (
        f"{len(aliased)} settled candidates still matched multiple legal actions: {aliased[:10]}"
    )


@pytest.mark.parametrize("position_name", PLAYTEST_POSITION_NAMES)
def test_playtest_position_can_be_played_for_twelve_turns_and_advances_round(
    position_name: str,
) -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / position_name))
    state = scenario.state
    start_round = state.timing.round_number
    for _ in range(12):
        state = _complete_first_available_turn(state, scenario.config)
    assert state.timing.round_number > start_round


def test_cloisters_loop_playtest_position_has_expected_action_and_candidate_totals() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP))
    actions = list(legal_actions(scenario.state, scenario.config))
    skipped = sum(
        1
        for action in actions
        if isinstance(action, FullTurnAction) and action.sow_route_omitted_location is not None
    )
    assert len(actions) == 870
    assert skipped == 753
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP)
    try:
        assert len(server.payload["turn_candidates"]) == 801
    finally:
        server.server_close()


def test_cloisters_loop_city_origin_offers_city_skip_candidates() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP)
    try:
        drawn = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
        city_candidates = [
            candidate
            for candidate in server.payload["turn_candidates"]
            if candidate["action_id"] is not None
            and any(
                step["kind"] == "origin" and int(step["value"]) == 0 for step in candidate["steps"]
            )
            and any(
                step["kind"] == "skip" and int(step["value"]) == 0 for step in candidate["steps"]
            )
            and {str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"}
            <= drawn
        ]
        assert city_candidates, (
            "no reachable city-origin candidate offers city as the skipped space"
        )
    finally:
        server.server_close()


def test_cloisters_loop_every_legal_action_applies() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP))
    unexpected: list[str] = []
    for action in legal_actions(scenario.state, scenario.config):
        try:
            apply_action(scenario.state, action, scenario.config)
        except Exception as exc:  # pragma: no cover - diagnostic path
            unexpected.append(f"{action_id(action)} :: {exc}")
    assert not unexpected, f"loop playtest exposed unappliable legal actions: {unexpected[:10]}"


def test_cloisters_loop_playtest_keeps_player_one_stacks_at_two_or_less_after_one_turn() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP)
    try:
        settled = next(
            candidate
            for candidate in server.payload["turn_candidates"]
            if candidate["action_id"] is not None
        )
        server.apply(str(settled["action_id"]), str(server.payload["state_token"]))
        player_one = server.state.player_state(PlayerId.PLAYER_ONE)
        assert max(int(value) for value in player_one.workforce.mancala) <= 2
    finally:
        server.server_close()


def test_cloisters_loop_fixture_proves_revisit_was_the_counter_bug() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP))
    player_id = play_server._speaking_player_id(scenario.state)
    actions = list(legal_actions(scenario.state, scenario.config))
    (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    ) = _offer_flags_by_action_id(
        actions,
        state=scenario.state,
        config=scenario.config,
    )
    revisits = 0
    old_logic_last_not_zero = 0
    fixed_last_not_zero = 0

    for action in actions:
        if not isinstance(action, FullTurnAction) or action.sow_route_omitted_location is None:
            continue
        edge_destinations, omitted_edge_index = play_server._route_destinations_for_steps(
            action, scenario.config
        )
        assert omitted_edge_index is not None
        omitted_location = edge_destinations[omitted_edge_index]
        if edge_destinations.count(omitted_location) > 1:
            revisits += 1

        # Pre-fix behavior: withheld decrements by destination value, so revisits under-counted.
        old_remaining = len(action.route)
        for destination in edge_destinations:
            if destination != omitted_location:
                old_remaining -= 1
        if old_remaining != 0:
            old_logic_last_not_zero += 1

        steps = play_server.decision_steps(
            action,
            player_id,
            state=scenario.state,
            config=scenario.config,
            offer_hire=offer_hire_by_action_id[action_id(action)],
            hire_payment_buildings=hire_payment_buildings_by_action_id[action_id(action)],
        )
        edge_steps = [step for step in steps if step["kind"] == "edge"]
        assert edge_steps, "Cloisters action should always present at least one edge step"
        if int(edge_steps[-1]["counter"]) != 0:
            fixed_last_not_zero += 1

    assert revisits > 0, "loop fixture no longer revisits an omitted space; bug guard lost its case"
    assert revisits == 140
    assert old_logic_last_not_zero == 140
    assert fixed_last_not_zero == 0


def test_cloisters_loop_candidate_edge_counters_are_non_negative_and_end_at_zero() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CLOISTERS_LOOP)
    try:
        checked = 0
        for candidate in server.payload["turn_candidates"]:
            edge_steps = [step for step in candidate["steps"] if step["kind"] == "edge"]
            if not edge_steps:
                continue
            checked += 1
            counters = [step.get("counter") for step in edge_steps]
            assert all(isinstance(counter, int) for counter in counters), (
                candidate.get("action_id"),
                counters,
            )
            assert all(int(counter) >= 0 for counter in counters), (
                candidate.get("action_id"),
                counters,
            )
            assert int(counters[-1]) == 0, (
                candidate.get("action_id"),
                counters,
            )
        assert checked > 0, "loop playtest had no edge-step candidates"
    finally:
        server.server_close()


def test_every_candidate_edge_counter_is_non_negative_and_ends_at_zero_across_corpus(
    corpus_actions,
) -> None:
    checked = 0
    for scenario_path, scenario, actions in corpus_actions:
        payload = _payload_from_corpus(scenario, actions)
        for candidate in payload["turn_candidates"]:
            edge_steps = [step for step in candidate["steps"] if step["kind"] == "edge"]
            if not edge_steps:
                continue
            checked += 1
            counters = [step.get("counter") for step in edge_steps]
            assert all(isinstance(counter, int) for counter in counters), (
                scenario_path.name,
                candidate.get("action_id"),
                counters,
            )
            assert all(int(counter) >= 0 for counter in counters), (
                scenario_path.name,
                candidate.get("action_id"),
                counters,
            )
            assert int(counters[-1]) == 0, (
                scenario_path.name,
                candidate.get("action_id"),
                counters,
            )
    assert checked > 0, "corpus had no edge-step candidates, so this checked nothing"


# ---------------------------------------------------------------------------------------------
# Playing a setup sow
# ---------------------------------------------------------------------------------------------

HARNESS = Path(__file__).resolve().parent / "turn_script_harness.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
REFERENCE = Path(__file__).resolve().parents[1] / "scenarios" / "play_view_reference_4p_001.json"


def _generated(tmp_path: Path, players: int = 4, seed: int = 99) -> Path:
    """A fresh board, written out, with nothing about it yet decided."""
    from pilgrim.cli import main as cli_main

    path = tmp_path / "scenario.json"
    cli_main(
        ["generate-setup", "--players", str(players), "--seed", str(seed), "--output", str(path)]
    )
    return path


def _served(tmp_path: Path, players: int = 4, seed: int = 99):
    """A server on a fresh game, already past the decision that opens one.

    A generated game opens by asking who begins, and these tests are about the setup sows and the
    turns that follow it. That opening is the subject of its own test, which is where it is asserted
    rather than being incidentally rehearsed by every test that needs a board.
    """
    return _past_the_start_player_decision(
        PlayServer(("127.0.0.1", 0), _generated(tmp_path, players, seed))
    )


UNPRESENTED = "tithe_resource"


@contextmanager
def _one_field_gone_unasked_without_text(monkeypatch):
    """Take one presented field off the page without giving its residue player wording."""
    monkeypatch.setattr(
        play_server,
        "RESOURCE_CHOICE_FIELDS",
        tuple(name for name in play_server.RESOURCE_CHOICE_FIELDS if name != UNPRESENTED),
    )
    yield


@contextmanager
def _one_field_gone_unasked(monkeypatch):
    """Take one presented field back off the page, so a turn becomes genuinely unanswerable.

    Natural terminal dead ends are present in the committed scenario corpus, so the refusal is
    also exercised through the page as it is shipped. This manufactured case remains valuable
    because it takes a field that is normally presented and proves the generic refusal notices and
    names it when that affordance disappears. The natural case guards today's real backlog; this
    one guards the mechanism independently of which fields happen to be unfinished today.
    """
    with _one_field_gone_unasked_without_text(monkeypatch):
        monkeypatch.setitem(
            play_server.UNRESOLVED_FIELD_TEXT,
            UNPRESENTED,
            "which resource to tithe",
        )
        yield


def _played_until_the_page_must_refuse(server, limit: int = 40):
    """Play on, a settled turn at a time, until the page meets a turn it cannot finish.

    Not a pinned seed and turn number: which turns are ambiguous depends on what is unpresented,
    and that changes. This looks for one, under the field removed by `_one_field_gone_unasked`.
    """
    for _turn in range(limit):
        server._refresh()
        if any(candidate["unresolved"] for candidate in server.payload["turn_candidates"]):
            return server
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"])
        _apply_settled_turn_and_pass(server, settled)
    raise AssertionError(f"no turn in {limit} needed refusing, so the refusal went unexercised")


def _past_the_start_player_decision(server, choice: int = 0):
    """Answer whoever holds the First Player marker, so a test can get on to what it is about.

    Through a candidate now, like every other answer here. It used to go round the page by id off
    `legal_actions`, because the page had no way to ask a table who should begin; the point of that
    was to work around the refusal rather than assert it away, and there is no longer one to work
    around.
    """
    while server.payload["state"]["phase"] == "start_player_selection":
        candidate = server.payload["turn_candidates"][choice]
        server.apply(candidate["action_id"], server.payload["state_token"])
    return server


def _played_through_setup(server):
    """Take the four setup sows so the position is one where a normal turn is legal."""
    _past_the_start_player_decision(server)
    while server.payload["state"]["phase"] == "setup_sow":
        server.apply(
            server.payload["turn_candidates"][0]["action_id"], server.payload["state_token"]
        )
    return server


_RESOLUTION_NAMES = tuple(resolution.value for resolution in TurnResolutionType)


def _log_blocks_by_resolution_from_fixture(
    tmp_path: Path,
) -> tuple[dict[str, list[str]], tuple[str, ...]]:
    """One transcript block per reached resolution, and the names not reached from this fixture."""
    server = _played_through_setup(_served(tmp_path))
    reached: dict[str, list[str]] = {}
    max_absolute_turns = int(server.config.timing.max_absolute_turns)
    for _ in range(480):
        if len(reached) == len(_RESOLUTION_NAMES):
            break
        if int(server.state.timing.absolute_turn) >= max_absolute_turns:
            break
        actions = list(legal_actions(server.state, server.config))
        if not actions:
            break
        full_turns = [
            action for action in actions if getattr(action, "resolution", None) is not None
        ]
        if not full_turns:
            server.apply(action_id(actions[0]), server.payload["state_token"])
            continue
        chosen = next(
            (action for action in full_turns if action.resolution.value not in reached),
            full_turns[0],
        )
        resolution = chosen.resolution.value
        server.apply(action_id(chosen), server.payload["state_token"])
        if resolution not in reached:
            reached[resolution] = list(server.payload["log_blocks"][-1]["lines"])
        _pass_end_turn_window(server)
    missing = tuple(name for name in _RESOLUTION_NAMES if name not in reached)
    return reached, missing


@pytest.fixture(scope="module")
def resolution_guard_sample(tmp_path_factory):
    """Reachable-resolution sample used by the player-language guard below."""
    return _log_blocks_by_resolution_from_fixture(tmp_path_factory.mktemp("resolution_guard"))


@contextlib.contextmanager
def _running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _post(base: str, action_id_value: str, token: str):
    request = urllib.request.Request(
        f"{base}/action",
        data=json.dumps({"action_id": action_id_value, "state_token": token}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read().decode("utf-8")


def _post_form(base: str, route: str, fields: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(
        f"{base}{route}",
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read().decode("utf-8")


def _get(base: str, route: str) -> tuple[int, str]:
    request = urllib.request.Request(f"{base}{route}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read().decode("utf-8")


def _get_json(base: str, route: str):
    with urllib.request.urlopen(f"{base}{route}", timeout=10) as response:
        return json.loads(response.read())


def _run_script(
    server,
    clicks,
    tmp_path: Path,
    *,
    reset: bool = False,
    confirm: bool = False,
    mutate=None,
    job_fields: dict[str, Any] | None = None,
):
    """Execute the page's own turn script against a stub board, and report what it did.

    `mutate` rewrites the script before it runs, which is how a deliberate bug is put into the
    shipped code to check that something catches it.
    """
    page = render_play_view_from_payload(server.payload)
    script = re.search(r"<script>\n(.*?)\n</script>", page, re.S)
    assert script is not None, "the page carried no turn script"
    source = script.group(1)
    if mutate is not None:
        source = mutate(source)
        assert source != script.group(1), "the mutation matched nothing, so nothing was mutated"

    candidates = server.payload["turn_candidates"]
    spaces = [
        {"index": index, "name": name}
        for index, name in enumerate(server.payload["board_positions"])
    ]
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps(
            {
                "script": source,
                # Every question any candidate asks, which is what the renderer draws. The stub
                # gets all of them for the same reason it gets every building on the track: a page
                # holding only the right answer cannot show a script picking the wrong one.
                "prompts": _prompts_drawn(candidates),
                "resolutions": _key_values(candidates, "resolution"),
                "combinations": _key_values(candidates, "combination"),
                "arrows": _arrows_drawn(page),
                "controls": _controls_drawn(page),
                "arrangementPointerRules": _arrangement_pointer_rules(page),
                "counters": sorted(
                    {
                        str(value)
                        for candidate in candidates
                        for value in [
                            candidate.get("counter_start"),
                            *[
                                step.get("counter")
                                for step in candidate.get("steps", ())
                                if step.get("counter") is not None
                            ],
                        ]
                        if value is not None
                    }
                ),
                "spaces": spaces,
                "cubes": _cube_slots(server),
                "playerCount": len(server.payload["state"]["players"]),
                # Every building on the track, not only the constructible ones, because the page
                # draws a key for every one of them. A stub holding only the right answers cannot
                # show a script reaching past them.
                "buildings": _buildings_on_the_track(server),
                # The status targets carry their already-worded engine payload. The harness reads
                # the script's rendered value back, so a future fallback or client-side reason
                # translation cannot hide behind a browser-only tooltip test.
                "buildingAbilityTargets": server.payload.get("building_abilities", []),
                # These are the tiles the page actually makes into committed-step affordances,
                # including unavailable ones that need to show why they cannot be used.
                "turnStepBuildings": _turn_step_buildings_on_payload(server.payload),
                # Every seat, with the page's own word for which one is on, so the script has four
                # boards to choose wrongly between rather than one it cannot help but get right.
                # Always four, however many are playing, because the page always draws four and
                # hides the empty ones. A stub with only the occupied chairs in it would take the
                # empty ones out of reach of anything that wrongly lit them.
                "seats": [
                    (
                        {
                            "seat": seat,
                            "player": player_id,
                            "taken": player_id in _seated(server),
                            "active": player_id == server.payload["state"]["active_player"],
                        }
                        | _seat_allocation_state(server, player_id)
                    )
                    for seat, player_id in enumerate(SEATED_PLAYERS, start=1)
                ],
                "panels": [candidate["action_id"] for candidate in candidates],
                "clicks": clicks,
                "reset": reset,
                "confirm": confirm,
            }
            | (job_fields or {})
        ),
        encoding="utf-8",
    )
    finished = subprocess.run(
        ["node", str(HARNESS), str(job)], capture_output=True, text=True, check=True
    )
    return json.loads(finished.stdout)


@needs_node
def test_kogge_and_cloisters_page_expands_candidates_to_the_server_payload(tmp_path: Path) -> None:
    """The transport compaction must disappear before the turn script reads a candidate."""
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_KOGGE_AND_CLOISTERS)
    try:
        expanded = _run_script(
            server,
            [],
            tmp_path,
            job_fields={"expandedCandidates": True},
        )
        assert expanded == json.loads(json.dumps(server.payload["turn_candidates"]))
    finally:
        server.server_close()


def test_candidate_summaries_share_one_wire_entry() -> None:
    """A repeated player sentence stays one string until the page restores the candidates."""
    scenario = load_scenario(PLAYTEST_SCENARIOS / PLAYTEST_KOGGE_AND_CLOISTERS)
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    wire = render_play_view._compact_turn_candidates_for_page(candidates)
    summaries = [
        candidate["summary"] for candidate in candidates if candidate["summary"] is not None
    ]

    assert len(wire["$s"]) == len(set(summaries))
    assert all(
        wire["$s"][compact["summary"]] == candidate["summary"]
        for compact, candidate in zip(wire["c"], candidates, strict=True)
        if candidate["summary"] is not None
    )


TURN_STAGE_ORDER = (
    "beginning_buildings",
    "lift_acolytes",
    "walk_route",
    "take_duty",
    "action_or_tithe",
    "end_buildings",
    "end_turn",
)
TURN_STEP_STAGE_KEYS = frozenset(
    {"lift_acolytes", "walk_route", "take_duty", "action_or_tithe", "end_turn"}
)


def _phase_column_at_stages(column: dict, open_stages: set[str]) -> dict:
    """Keep the server's row structure, changing only its supplied open set."""
    return {
        **column,
        "rows": [
            {
                **row,
                "stages": [
                    {
                        **stage,
                        "state": "open" if stage["key"] in open_stages else "not-open",
                    }
                    for stage in row["stages"]
                ],
            }
            for row in column["rows"]
        ],
    }


def _server_stage_snapshot(column: dict) -> dict[str, list[str]]:
    page = render_play_view._turn_phase_column({"phase_column": column})
    return {
        "open": re.findall(
            r'data-turn-stage="([^"]+)" data-turn-stage-state="open"', page
        ),
        "painted": re.findall(
            r'data-turn-stage="([^"]+)"[^>]*data-turn-stage-current="true"', page
        ),
    }


def _phase_named_at_frontier(frontier: dict[str, Any]) -> str:
    phases = {step["turn_phase"] for step in frontier["steps"]}
    assert len(phases) == 1, f"one page cursor carried several server phases: {phases!r}"
    return phases.pop()


def _open_stages_from_steps(steps: list[dict[str, Any]]) -> set[str]:
    return {
        stage
        for step in steps
        for stage in (step.get("turn_stage"), step.get("building_stage"))
        if stage is not None
    }


def _painted_stage(open_stages: set[str]) -> list[str]:
    return [
        next(stage for stage in TURN_STAGE_ORDER if stage in open_stages & TURN_STEP_STAGE_KEYS)
    ]


def _prompting_step(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Mirror promptsOf: the first offered step carrying the one sentence the page shows."""
    return next((step for step in steps if step.get("prompt")), None)


def _phase_after_the_page_follows_automatic_steps(
    candidates: list[dict], cursor: dict[str, int], selection: frozenset[int]
) -> tuple[str, set[str], str, str | None]:
    """Read the phase, open set, and prompting stage after automatic continuation."""
    selected = candidates[cursor["candidateIndex"]]["steps"][: cursor["depth"]]
    prefix = [step["value"] for step in selected]
    while True:
        live = [
            candidate
            for candidate in candidates
            if set(candidate.get("family", ())).issubset(selection)
            if len(candidate["steps"]) >= len(prefix)
            and [step["value"] for step in candidate["steps"][: len(prefix)]] == prefix
        ]
        offered = {
            (step["kind"], play_server._frontier_value(step["value"])): step
            for candidate in live
            if len(candidate["steps"]) > len(prefix)
            for step in [candidate["steps"][len(prefix)]]
        }
        if len(offered) == 1 and _auto_advance_for_families(
            next(iter(offered.values())), selection
        ):
            prefix.append(next(iter(offered.values()))["value"])
            continue
        if offered:
            phases = {step["turn_phase"] for step in offered.values()}
            offered_steps = list(offered.values())
            open_stages = _open_stages_from_steps(offered_steps)
            prompting_step = _prompting_step(offered_steps)
            current_stage = (
                prompting_step["turn_stage"]
                if prompting_step is not None
                else offered_steps[0]["turn_stage"]
            )
            prompt = None if prompting_step is None else prompting_step["prompt"]
        else:
            phases = {candidate["settled_turn_phase"] for candidate in live}
            open_stages = {
                stage
                for candidate in live
                for stage in (
                    candidate.get("settled_turn_stage"),
                    candidate.get("settled_building_stage"),
                )
                if stage is not None
            }
            current_stages = {candidate["settled_turn_stage"] for candidate in live}
            assert len(current_stages) == 1
            current_stage = current_stages.pop()
            prompt = None
        assert len(phases) == 1, f"one page cursor carried several server phases: {phases!r}"
        return phases.pop(), open_stages, current_stage, prompt


def _candidates_at_cursor(candidates: list[dict], cursor: dict[str, int]) -> list[dict]:
    """Put one payload cursor at the front without translating its server-written steps."""
    selected = candidates[cursor["candidateIndex"]]["steps"][: cursor["depth"]]
    prefix = [step["value"] for step in selected]
    return [
        {**candidate, "steps": candidate["steps"][len(prefix) :]}
        for candidate in candidates
        if len(candidate["steps"]) >= len(prefix)
        and [step["value"] for step in candidate["steps"][: len(prefix)]] == prefix
    ]


def _always_visible_route_families(payload: dict) -> frozenset[int]:
    """The route-family indices that are live without one of the page's toggle clicks."""
    visibility = {
        ability["building_id"]: ability.get("family_visibility")
        for ability in payload["building_abilities"]
    }
    families_by_index = {family["i"]: family for family in payload["families"]}
    return frozenset(
        index
        for index in payload.get("auto_family_indexes", [])
        for family in [families_by_index[index]]
        if visibility.get(family["building_id"]) == "always"
    )


def _run_phase_cursors(
    server, candidates: list[dict], cursors: list[dict[str, int]], tmp_path: Path
) -> list[dict]:
    """Run the shipped script once per cursor without replacing its phase logic in Python."""
    always_visible = _always_visible_route_families(server.payload)
    families_by_index = {family["i"]: family for family in server.payload["families"]}
    output = _run_script(
        server,
        [],
        tmp_path,
        job_fields={
            "phaseColumn": server.payload["phase_column"],
            "phaseOnly": True,
            "phaseCandidateRuns": [
                {
                    "candidates": _candidates_at_cursor(candidates, cursor),
                    "enabledFamilies": [
                        families_by_index[index]["building_id"]
                        for index in sorted(
                            always_visible
                            | frozenset(candidates[cursor["candidateIndex"]].get("family", ()))
                        )
                    ],
                }
                for cursor in cursors
            ],
        },
    )
    assert isinstance(output, list)
    return output


@needs_node
def test_every_playtest_frontier_paints_the_stage_owning_its_shown_prompt(
    tmp_path: Path,
) -> None:
    """The one shown server sentence and the one green server stage never disagree."""
    checked = 0
    scenario_names = []
    for scenario_path in sorted(PLAYTEST_SCENARIOS.glob("*.json")):
        server = PlayServer(("127.0.0.1", 0), scenario_path)
        try:
            candidates = server.payload["turn_candidates"]
            frontiers = _turn_candidate_frontiers(candidates)
            scenario_names.append(scenario_path.name)
            for frontier in frontiers:
                assert _phase_named_at_frontier(frontier) in {"sow", "end"}
            cursors = [frontier["cursor"] for frontier in frontiers]

            for frontier in frontiers:
                open_stages = _open_stages_from_steps(frontier["steps"])
                column = _phase_column_at_stages(server.payload["phase_column"], open_stages)
                assert _server_stage_snapshot(column)["open"] == [
                    stage for stage in TURN_STAGE_ORDER if stage in open_stages
                ]

            painted = _run_phase_cursors(server, candidates, cursors, tmp_path)
            assert len(painted) == len(frontiers)
            selection = _always_visible_route_families(server.payload)
            for frontier, observed in zip(frontiers, painted, strict=True):
                cursor = frontier["cursor"]
                cursor_selection = selection | frozenset(
                    candidates[cursor["candidateIndex"]].get("family", ())
                )
                (
                    expected_phase,
                    expected_stages,
                    expected_current_stage,
                    expected_prompt,
                ) = _phase_after_the_page_follows_automatic_steps(
                    candidates, cursor, cursor_selection
                )
                assert observed == {
                    "phaseRows": [],
                    "openStageRows": [
                        stage for stage in TURN_STAGE_ORDER if stage in expected_stages
                    ],
                    "paintedStageRows": [expected_current_stage],
                    "promptRows": [] if expected_prompt is None else [expected_prompt],
                }, (
                    f"{scenario_path.name} client painted {observed!r} at "
                    f"{frontier['prefix']!r}; its server payload names "
                    f"{expected_phase!r} and {expected_stages!r}"
                )
            checked += len(frontiers)

            settled = next(
                candidate for candidate in candidates if candidate["action_id"] is not None
            )
            server.apply(settled["action_id"], server.payload["state_token"])
            assert _server_stage_snapshot(server.payload["phase_column"])["painted"] == [
                "end_turn"
            ]
            assert _run_script(
                server,
                [],
                tmp_path,
                job_fields={"phaseColumn": server.payload["phase_column"], "phaseOnly": True},
            )["paintedStageRows"] == ["end_turn"]
        finally:
            server.server_close()

    assert sorted(scenario_names) == sorted(PLAYTEST_POSITION_NAMES)
    assert checked >= 1700, f"only {checked} playtest frontiers were checked"


def test_turn_stage_contract_covers_mixed_frontiers_and_the_short_setup_spine(
    play_payload_corpus,
) -> None:
    expected_stage_by_kind = {
        "origin": "lift_acolytes",
        "edge": "walk_route",
        "skip": "walk_route",
        "duty": "take_duty",
        "resolution": "action_or_tithe",
        "resource": "action_or_tithe",
        "combination": "action_or_tithe",
        "hire": "action_or_tithe",
        "building": "action_or_tithe",
        "arrangement": "action_or_tithe",
        "ordination": "action_or_tithe",
    }
    mixed_frontiers = []
    setup_positions = []
    setup_candidates = 0

    for scenario_path, payload in play_payload_corpus:
        candidates = payload["turn_candidates"]
        for candidate in candidates:
            for step in candidate["steps"]:
                assert step["turn_stage"] == expected_stage_by_kind[step["kind"]]
                if step["kind"] == "origin" and payload["state"]["phase"] == "sow":
                    assert step["turn_phase"] == "sow"
                    assert step["building_ability_window"] == "beginning"
        for frontier in _turn_candidate_frontiers(candidates):
            open_step_stages = {step["turn_stage"] for step in frontier["steps"]}
            if {"walk_route", "take_duty"}.issubset(open_step_stages):
                mixed_frontiers.append((scenario_path.name, frontier["prefix"]))

        if payload["state"]["phase"] == "setup_sow":
            setup_positions.append(scenario_path.name)
            setup_candidates += len(candidates)
            stages = [
                stage["key"]
                for row in payload["phase_column"]["rows"]
                for stage in row["stages"]
            ]
            assert stages == ["lift_acolytes", "walk_route"]

    assert len(mixed_frontiers) == 95
    assert len(setup_positions) == 5
    assert setup_candidates == 30


def test_building_stage_opens_from_committed_steps_or_route_family_candidates() -> None:
    for scenario_name, expected_source in (
        (PLAYTEST_CONVERSIONS, "turn_steps"),
        (PLAYTEST_KOGGE_AND_CLOISTERS, "route_family"),
    ):
        scenario = load_scenario(PLAYTEST_SCENARIOS / scenario_name)
        steps = play_server.turn_steps_payload(scenario.state, scenario.config)
        route_payload = play_server.route_family_payload(
            scenario.state,
            scenario.config,
            available_turn_steps=steps,
        )
        column = play_server.phase_column_payload(
            scenario.state,
            [],
            available_turn_steps=steps,
            turn_candidates=route_payload["turn_candidates"],
        )
        states = {
            stage["key"]: stage["state"]
            for row in column["rows"]
            for stage in row["stages"]
        }

        assert states["beginning_buildings"] == "open"
        assert states["end_buildings"] == "not-open"
        assert (bool(steps), bool(route_payload["auto_family_indexes"])) == (
            expected_source == "turn_steps",
            expected_source == "route_family",
        )


def test_round_end_phase_markup_keeps_its_flat_existing_shape() -> None:
    column = {
        "scope": "round_end",
        "rows": [
            {"key": "round_marker", "label": "Round marker advanced", "current": False},
            {"key": "merchant", "label": "Merchant advanced", "current": True},
        ],
    }

    assert render_play_view._turn_phase_column({"phase_column": column}) == (
        '<div class="phase-column" data-phase-column="round_end">'
        '<div class="phase-row" data-round-end-phase="round_marker">'
        "Round marker advanced</div>"
        '<div class="phase-row" data-round-end-phase="merchant" '
        'data-phase-current="true">Merchant advanced</div></div>'
    )


def _buildings_on_the_track(server) -> list[str]:
    """Read off the page, which is where the keys really are, rather than off the state."""
    return _buildings_on_payload(server.payload)


def _buildings_on_payload(payload: dict) -> list[str]:
    page = render_play_view_from_payload(payload)
    return re.findall(r'data-building-choice-key="([a-z_]+)"', page)


def _turn_step_buildings_on_payload(payload: dict) -> list[str]:
    page = render_play_view_from_payload(payload)
    return sorted(set(re.findall(r'data-turn-step-building-id="([a-z_]+)"', page)))


@needs_node
def test_building_ability_reason_is_rendered_and_missing_reason_stays_blank(tmp_path: Path) -> None:
    """The script copies the server-written tile text; it does not invent an absent reason."""
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    try:
        opening = _run_script(server, [], tmp_path)["buildingAbilityTexts"][-1]
        assert opening["mill"] == "Cannot be hired: this building was not selected for this game."
        assert opening["kogge"] == (
            "Pick up acolytes first, then show the routes it opens — "
            "1 silver to Yellow if you use one."
        )

        def without_mill_reason(abilities: list[dict]) -> list[dict]:
            return [
                (
                    {**ability, "reason": None, "status_text": None}
                    if ability["building_id"] == "mill"
                    else ability
                )
                for ability in abilities
            ]

        server.payload["building_abilities"] = without_mill_reason(
            server.payload["building_abilities"]
        )
        server.payload["building_ability_windows"]["beginning"]["abilities"] = (
            without_mill_reason(
                server.payload["building_ability_windows"]["beginning"]["abilities"]
            )
        )
        without_reason = _run_script(server, [], tmp_path)["buildingAbilityTexts"][-1]
        assert without_reason["mill"] == ""
    finally:
        server.server_close()


@needs_node
def test_building_steps_close_during_the_server_described_sow_window(tmp_path: Path) -> None:
    """Sow closes doer activations while permitters retain their already-live effects."""
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    try:
        candidate = next(
            candidate
            for candidate in server.payload["turn_candidates"]
            if len(candidate["steps"]) > 1 and candidate["steps"][1]["turn_phase"] == "sow"
        )
        clicks = _clicks_to(server, _engine_decisions(server), [candidate["steps"][0]["value"]])
        transcript = _run_script(server, clicks, tmp_path)
        opening = sorted({step["building_id"] for step in server.payload["turn_steps"]})
        sow_greyed = {
            ability["building_id"]
            for ability in server.payload["building_ability_windows"]["sow"]["abilities"]
            if ability["greyed"]
        }
        sow_reason_census = Counter(
            str(ability["reason"])
            for ability in server.payload["building_ability_windows"]["sow"]["abilities"]
        )
        mid_sow_buildings = {
            ability["building_id"]
            for ability in server.payload["building_ability_windows"]["sow"]["abilities"]
            if ability["reason"] == "mid_sow"
        }
        assert {
            "offers": transcript["turnStepOffers"],
            "greyed": {
                building_id
                for building_id, greyed in transcript["buildingAbilityGreyscale"][-1].items()
                if greyed
            },
            "own_building_status": transcript["buildingAbilityTexts"][-1]["dormitory"],
            "reason_census": sow_reason_census,
            "mid_sow_buildings": mid_sow_buildings,
        } == {
            "offers": [opening, []],
            "greyed": sow_greyed,
            "own_building_status": "Cannot be used: sowing is in progress.",
            "reason_census": Counter({"not_selected": 18, "mid_sow": 4, "None": 2}),
            "mid_sow_buildings": {"dormitory", "guild", "inquisition", "library"},
        }
    finally:
        server.server_close()


@pytest.mark.slow
def test_every_scenario_draws_exactly_the_buildings_that_can_answer_a_plain_pick(
    corpus_actions,
) -> None:
    missing_by_scenario: dict[str, list[str]] = {}
    extra_by_scenario: dict[str, list[str]] = {}
    for scenario_path, scenario, actions in corpus_actions:
        payload = _payload_from_corpus(scenario, actions)
        drawn = set(_buildings_on_payload(payload))
        market = set(payload["state"]["building_market"])
        owned = {
            building_id
            for player in payload["state"]["players"]
            for building_id in player["player_board_slots"]["active_buildings"]
        }
        expected = market | (owned if payload["turn_candidates"] else set())
        missing = sorted(expected - drawn)
        extra = sorted(drawn - expected)
        if missing:
            missing_by_scenario[scenario_path.name] = missing
        if extra:
            extra_by_scenario[scenario_path.name] = extra

    assert not missing_by_scenario, f"missing building choice keys: {missing_by_scenario}"
    assert not extra_by_scenario, f"unexpected building choice keys: {extra_by_scenario}"


def test_every_hired_candidate_in_the_corpus_asks_the_hire_step(corpus_actions) -> None:
    """Every candidate that commits a hired building must ask for that hire explicitly.

    This guards against silent cost consent: unambiguous branches still need the explicit hire
    question in the turn panel before any effect step that depends on that payment.
    """
    checked = 0
    missing: list[tuple[str, tuple, list[str], int]] = []
    for scenario_path, scenario, actions in corpus_actions:
        payload = _payload_from_corpus(scenario, actions)
        player_id = play_server._speaking_player_id(scenario.state)
        (
            offer_hire_by_action_id,
            hire_payment_buildings_by_action_id,
        ) = _offer_flags_by_action_id(
            actions,
            state=scenario.state,
            config=scenario.config,
        )

        def key_for_steps(steps: list[dict]) -> tuple:
            return tuple(
                tuple(step["value"]) if isinstance(step["value"], tuple) else step["value"]
                for step in steps
            )

        by_key: dict[tuple, list[FullTurnAction]] = {}
        for action in actions:
            steps = play_server.decision_steps(
                action,
                player_id,
                state=scenario.state,
                config=scenario.config,
                offer_hire=offer_hire_by_action_id[action_id(action)],
                hire_payment_buildings=hire_payment_buildings_by_action_id[action_id(action)],
            )
            by_key.setdefault(key_for_steps(steps), []).append(action)

        candidates_by_key = {
            key_for_steps(candidate["steps"]): candidate for candidate in payload["turn_candidates"]
        }

        for key, members in by_key.items():
            if not any(
                isinstance(member, FullTurnAction) and member.hired_building_id is not None
                for member in members
            ):
                continue
            checked += 1
            candidate = candidates_by_key.get(key)
            if candidate is None:
                missing.append((scenario_path.name, key, [], len(members)))
                continue
            if not any(step["kind"] == "hire" for step in candidate["steps"]):
                missing.append(
                    (
                        scenario_path.name,
                        key,
                        [str(step["kind"]) for step in candidate["steps"]],
                        len(members),
                    )
                )
    assert checked > 0, "corpus had no hired candidates, so this checked nothing"
    assert not missing, f"missing hire step on {len(missing)} hired candidates: {missing[:10]}"


def test_corpus_hire_payments_are_immediate_exact_and_single_bank_use(
    corpus_actions, playtest_actions
) -> None:
    """Applied actions, not their page copy, are the authority for every offered hire stock."""
    shape_counts: Counter[tuple[str, tuple[str, ...]]] = Counter()
    frontiers: dict[
        tuple[str, tuple[Any, ...], str], tuple[set[str], set[str]]
    ] = {}
    missing_or_late: list[tuple[str, str, list[str], list[str]]] = []
    resource_mismatches: list[tuple[str, str, list[str], list[str]]] = []
    state_delta_mismatches: list[tuple[str, str, dict[str, int], dict[str, int]]] = []
    double_bank_substitutions: list[tuple[str, str, int]] = []
    hire_questions = 0
    paid_resolution_hires = 0
    bank_actions = 0

    for scenario_path, scenario, scenario_actions in _all_corpus_actions(
        corpus_actions, playtest_actions
    ):
        actions = {action_id(action): action for action in scenario_actions}
        applied: dict[str, Any] = {}
        candidates = play_server.turn_candidates(
            scenario.state,
            scenario.config,
            actions=list(scenario_actions),
            include_preview_effects=False,
        )
        for candidate in candidates:
            steps = candidate["steps"]
            hire_index = next(
                (index for index, step in enumerate(steps) if step["kind"] == "hire"),
                None,
            )
            if hire_index is None:
                continue
            hire_questions += 1
            move_id = candidate["action_id"]
            assert move_id is not None, (
                f"{scenario_path.name} left a hire-bearing candidate unresolved"
            )
            action = actions[move_id]
            assert isinstance(action, FullTurnAction)

            if action.hired_building_id is None:
                cost_kind = "none"
            else:
                paid_resolution_hires += 1
                source = building_ability_source(
                    scenario.state,
                    scenario.config,
                    acting_player=scenario.state.active_player,
                    building_key=action.hired_building_id,
                )
                cost_kind = (
                    "choice"
                    if source.hire_resource == CORNUCOPIA_COUNTER
                    and not source.hire_resource_chosen
                    else "fixed"
                )
            shape_counts[(cost_kind, tuple(step["kind"] for step in steps[hire_index:]))] += 1

            payment_buildings = [
                building_id for building_id, _resource in tuple(action.hire_payments or ())
            ]
            if action.hired_building_id in payment_buildings:
                payment_buildings.remove(action.hired_building_id)
                payment_buildings.insert(0, action.hired_building_id)
            payment_steps = steps[hire_index + 1 : hire_index + 1 + len(payment_buildings)]
            if [step["kind"] for step in payment_steps] != ["resource"] * len(
                payment_buildings
            ):
                missing_or_late.append(
                    (
                        scenario_path.name,
                        move_id,
                        payment_buildings,
                        [step["kind"] for step in steps[hire_index:]],
                    )
                )
                continue
            if (
                not payment_buildings
                and hire_index + 1 < len(steps)
                and steps[hire_index + 1]["kind"] == "resource"
            ):
                missing_or_late.append(
                    (
                        scenario_path.name,
                        move_id,
                        [],
                        [step["kind"] for step in steps[hire_index:]],
                    )
                )

            result = applied.get(move_id)
            if result is None:
                result = apply_action(scenario.state, action, scenario.config)
                applied[move_id] = result
            applied_hires = {
                str(details["building_id"]): str(details["resource"])
                for event in result.events
                if event.event_type is EventType.BUILDING_HIRED
                and event.action_id == move_id
                for details in (dict(event.details),)
            }
            actually_paid = [applied_hires[building_id] for building_id in payment_buildings]
            presented = [str(step["value"]) for step in payment_steps]
            if presented != actually_paid:
                resource_mismatches.append(
                    (scenario_path.name, move_id, presented, actually_paid)
                )

            before = scenario.state.player_state(scenario.state.active_player).resources
            after = result.state.player_state(scenario.state.active_player).resources
            actual_delta = {
                resource: getattr(after, resource) - getattr(before, resource)
                for resource in ("stone", "silver", "wheat")
            }
            event_delta = {
                resource: sum(
                    int(dict(event.details).get(resource, 0))
                    for event in result.events
                    if event.event_type is EventType.RESOURCE_DELTA
                    and event.action_id == move_id
                )
                for resource in ("stone", "silver", "wheat")
            }
            if actual_delta != event_delta:
                state_delta_mismatches.append(
                    (scenario_path.name, move_id, actual_delta, event_delta)
                )

            for offset, (building_id, payment_step) in enumerate(
                zip(payment_buildings, payment_steps, strict=True)
            ):
                step_index = hire_index + 1 + offset
                frontier = (
                    scenario_path.name,
                    tuple(step["value"] for step in steps[:step_index]),
                    building_id,
                )
                offered, applied_resources = frontiers.setdefault(frontier, (set(), set()))
                offered.add(str(payment_step["value"]))
                applied_resources.add(applied_hires[building_id])

        for move_id, action in actions.items():
            if not isinstance(action, FullTurnAction) or action.bank_payment_building_id is None:
                continue
            bank_actions += 1
            result = applied.get(move_id)
            if result is None:
                result = apply_action(scenario.state, action, scenario.config)
                applied[move_id] = result
            substitutions = sum(
                event.event_type is EventType.BUILDING_BONUS
                and dict(event.details).get("action") == "payment_substitution"
                and event.action_id == move_id
                for event in result.events
            )
            if substitutions > 1:
                double_bank_substitutions.append((scenario_path.name, move_id, substitutions))

    expected_shapes = Counter(
        {
            ("choice", ("hire", "resource", "resource", "arrangement")): 198,
            ("fixed", ("hire", "resource", "arrangement")): 110,
            ("choice", ("hire", "resource", "resource")): 51,
            ("choice", ("hire", "resource", "arrangement")): 44,
            ("none", ("hire", "resource", "arrangement")): 36,
            ("none", ("hire", "arrangement")): 29,
            ("fixed", ("hire", "resource", "combination")): 20,
            ("none", ("hire", "combination")): 19,
            ("choice", ("hire", "resource")): 12,
            ("fixed", ("hire", "resource", "ordination")): 10,
            ("fixed", ("hire", "resource")): 9,
            ("none", ("hire", "ordination")): 8,
            ("fixed", ("hire", "resource", "resource")): 2,
        }
    )
    frontier_mismatches = [
        (frontier, offered, applied_resources)
        for frontier, (offered, applied_resources) in frontiers.items()
        if offered != applied_resources
    ]
    assert hire_questions == 548
    assert paid_resolution_hires == 456
    assert shape_counts == expected_shapes
    assert not missing_or_late, f"late or missing hire payments: {missing_or_late[:10]}"
    assert not resource_mismatches, f"hire payment stocks disagree: {resource_mismatches[:10]}"
    assert not state_delta_mismatches, (
        "applied resource events disagree with player resource diffs: "
        f"{state_delta_mismatches[:10]}"
    )
    assert frontiers
    assert not frontier_mismatches, f"offered hire stocks disagree: {frontier_mismatches[:10]}"
    assert bank_actions > 0, "corpus carried no Bank substitutions to audit"
    assert not double_bank_substitutions, (
        f"actions carrying two Bank substitutions: {double_bank_substitutions[:10]}"
    )


def test_every_cloisters_skip_candidate_in_the_corpus_asks_the_skip_step(corpus_actions) -> None:
    """Every candidate that commits a Cloisters skip must ask for that skipped space."""
    checked = 0
    missing: list[tuple[str, tuple, list[str], int]] = []
    for scenario_path, scenario, actions in corpus_actions:
        payload = _payload_from_corpus(scenario, actions)
        player_id = play_server._speaking_player_id(scenario.state)
        (
            offer_hire_by_action_id,
            hire_payment_buildings_by_action_id,
        ) = _offer_flags_by_action_id(
            actions,
            state=scenario.state,
            config=scenario.config,
        )

        def key_for_steps(steps: list[dict]) -> tuple:
            return tuple(
                tuple(step["value"]) if isinstance(step["value"], tuple) else step["value"]
                for step in steps
            )

        by_key: dict[tuple, list[FullTurnAction]] = {}
        for action in actions:
            steps = play_server.decision_steps(
                action,
                player_id,
                state=scenario.state,
                config=scenario.config,
                offer_hire=offer_hire_by_action_id[action_id(action)],
                hire_payment_buildings=hire_payment_buildings_by_action_id[action_id(action)],
            )
            by_key.setdefault(key_for_steps(steps), []).append(action)

        candidates_by_key = {
            key_for_steps(candidate["steps"]): candidate for candidate in payload["turn_candidates"]
        }

        for key, members in by_key.items():
            if not any(
                isinstance(member, FullTurnAction) and member.sow_route_omitted_location is not None
                for member in members
            ):
                continue
            checked += 1
            candidate = candidates_by_key.get(key)
            if candidate is None:
                missing.append((scenario_path.name, key, [], len(members)))
                continue
            if not any(step["kind"] == "skip" for step in candidate["steps"]):
                missing.append(
                    (
                        scenario_path.name,
                        key,
                        [str(step["kind"]) for step in candidate["steps"]],
                        len(members),
                    )
                )
    assert checked > 0, "corpus had no skip candidates, so this checked nothing"
    assert not missing, f"missing skip step on {len(missing)} Cloisters candidates: {missing[:10]}"


def test_construct_building_level2_draws_keys_for_all_eight_constructible_buildings() -> None:
    """Regression: this fixture offered eight construct moves while the page drew one key."""
    server = PlayServer(("127.0.0.1", 0), str(SCENARIOS / "construct_building_level2_001.json"))
    try:
        keys = set(_buildings_on_the_track(server))
        constructible = {
            action.construct_building_id
            for action in legal_actions(server.state, server.config)
            if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
            and action.construct_building_id is not None
        }
        assert len(constructible) == 8
        assert constructible <= keys
    finally:
        server.server_close()


def _seated(server) -> set[str]:
    """The engine ids that have a chair at this player count."""
    count = len(server.payload["state"]["players"])
    return {f"player_{word}" for word in ("one", "two", "three", "four")[:count]}


def _key_values(candidates: list[dict], kind: str) -> list[str]:
    """Every distinct value of one kind of step, which is one key each on the page."""
    asked_kinds = (
        {"combination", "hire"} if kind == "combination" else {kind}
    )
    return sorted(
        {step["value"] for c in candidates for step in c["steps"] if step["kind"] in asked_kinds}
    )


def _prompts_drawn(candidates: list[dict]) -> list[str]:
    """Every distinct question the candidates ask, which is one line each on the page.

    By prompt and not by kind. Several of these questions are answered the same way -- by pointing at
    a space -- and ask about different things, so a page that drew one line per kind would ask for
    an origin when it wanted the next space on a route.
    """
    return sorted({step["prompt"] for c in candidates for step in c["steps"] if "prompt" in step})


def _arrows_drawn(page: str) -> list[str]:
    # Hired Kogge companions are server-rendered SVG kept as JSON-escaped markup until the player
    # turns on that already-offered family. Treat those supplied elements as drawn for the seam
    # audit without mistaking an inactive template for a wheel element in the browser.
    return sorted(set(re.findall(r'data-arrow="([^"]+)"', page.replace(r'\"', '"'))))


def _candidate_edges(candidates: list[dict]) -> set[str]:
    return {
        str(step["value"])
        for candidate in candidates
        for step in candidate["steps"]
        if step["kind"] == "edge"
    }


def _dead_candidates_by_missing_edges(
    candidates: list[dict],
    drawn_edges: set[str],
) -> list[tuple[str | None, list[str]]]:
    dead: list[tuple[str | None, list[str]]] = []
    for candidate in candidates:
        edges = {str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"}
        missing = sorted(edges - drawn_edges)
        if missing:
            dead.append((candidate.get("action_id"), missing))
    return dead


def _offered_kinds_by_prefix(candidates: list[dict]) -> dict[tuple[Any, ...], set[str]]:
    """Kinds offered at each reachable prefix, keyed exactly as the page narrows by value."""
    offered: dict[tuple[Any, ...], set[str]] = {}
    for candidate in candidates:
        prefix: list[Any] = []
        for step in candidate.get("steps", ()):
            offered.setdefault(tuple(prefix), set()).add(str(step["kind"]))
            prefix.append(step["value"])
    return offered


def _first_settled_skip_candidate(server: PlayServer) -> dict | None:
    drawn_arrows = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
    return next(
        (
            offered
            for offered in server.payload["turn_candidates"]
            if offered["action_id"] is not None
            and any(step["kind"] == "skip" for step in offered["steps"])
            and {str(step["value"]) for step in offered["steps"] if step["kind"] == "edge"}
            <= drawn_arrows
        ),
        None,
    )


def _controls_drawn(page: str) -> dict[str, bool]:
    return {
        name: enabled == "true"
        for name, enabled in re.findall(
            r'data-turn-control="([^"]+)"[^>]*data-turn-control-enabled="([^"]+)"', page
        )
    }


def _cube_slots(server) -> dict[str, list[dict[str, str]]]:
    slots: dict[str, list[dict[str, str]]] = {}
    seated = [player_id for player_id in SEATED_PLAYERS if player_id in _seated(server)]
    names = list(server.payload["board_positions"])
    for position_index, position_name in enumerate(names):
        room = 6 if position_name == "city" else 3
        columns: list[dict[str, str]] = []
        for player_id in seated:
            standing = server.payload["state"]["acolytes"][SEATED_PLAYERS.index(player_id)][
                position_index
            ]
            columns.extend(
                {
                    "player": player_id,
                    "opacity": "1" if slot < standing else "0",
                }
                for slot in range(room)
            )
        slots[position_name] = columns
    return slots


def _seat_allocation_state(server, player_id: str) -> dict[str, object]:
    from tools.ui_debug.play_view_adapter import player_record

    roles = ("fields", "road_engineer", "stone_mason", "alms_house", "engraver", "vestry")
    record = player_record(server.payload, player_id)
    if record is None:
        return {"village": 0, "abbey": 0, "roles": {role: 0 for role in roles}}
    return {
        "village": int(record["workforce"]["village"]),
        "abbey": int(record["workforce"]["abbey"]),
        "roles": {role: int(record["special_activities"].get(role, 0)) for role in roles},
    }


def _at(value):
    return {"kind": "position", "value": value}


def _press(name: str):
    return {"kind": "control", "value": name}


def _follow(value: str):
    return {"kind": "edge", "value": value}


def _do(name):
    return {"kind": "resolution", "value": name}


def _take(stock: str, seat: int):
    """Press a stock key on one seat's board -- named, so a test can press the wrong one."""
    return {"kind": "resource", "value": stock, "seat": seat}


def _pay(combination: str):
    return {"kind": "combination", "value": combination}


def _name(player_id: str):
    """Press a whole board, which is how a player is named."""
    return {"kind": "seat", "value": player_id}


def _build(building_id: str):
    """Press a building where it stands on the round track."""
    return {"kind": "building", "value": building_id}


def _lift_from(slot: str) -> dict[str, str]:
    if slot == "abbey":
        return {"kind": "abbey", "value": "abbey"}
    return {"kind": "role", "value": slot}


def _place_on(slot: str) -> dict[str, str]:
    if slot == "abbey":
        return {"kind": "abbey", "value": "abbey"}
    return {"kind": "role", "value": slot, "target": "circle"}


def _ordain_click() -> dict[str, str]:
    return {"kind": "village", "value": "ordain"}


def _mission_click() -> dict[str, str]:
    return {"kind": "abbey", "value": "mission"}


def _arrangement_clicks(value: str) -> list[dict[str, str]]:
    """Two-click moves rebuilt from an offered net delta vector."""
    if value == "none":
        return []
    deltas: list[tuple[str, int]] = []
    for part in value.split(","):
        slot, raw = part.split("=", 1)
        deltas.append((slot, int(raw)))
    sources = [slot for slot, delta in deltas if delta < 0 for _ in range(-delta)]
    destinations = [slot for slot, delta in deltas if delta > 0 for _ in range(delta)]
    assert len(sources) == len(destinations), value
    clicks: list[dict[str, str]] = []
    for source, destination in zip(sources, destinations, strict=True):
        clicks.append(_lift_from(source))
        clicks.append(_place_on(destination))
    return clicks


def _ordination_counts(value: str) -> tuple[int, int]:
    if value == "none":
        return (0, 0)
    counts = {"ordain": 0, "mission": 0}
    for part in value.split(","):
        name, amount = part.split("=", 1)
        counts[name] = int(amount)
    return (counts["ordain"], counts["mission"])


def _ordination_clicks(value: str) -> list[dict[str, str]]:
    ordain, mission = _ordination_counts(value)
    return [_ordain_click() for _ in range(ordain)] + [_mission_click() for _ in range(mission)]


def _legal_ordination_orders(
    *,
    start_village: int,
    start_abbey: int,
    ordain_count: int,
    mission_count: int,
) -> list[tuple[str, ...]]:
    orders: list[tuple[str, ...]] = []

    def walk(
        village: int, abbey: int, ordains_left: int, missions_left: int, path: tuple[str, ...]
    ) -> None:
        if ordains_left == 0 and missions_left == 0:
            orders.append(path)
            return
        if ordains_left > 0 and village > 0:
            walk(village - 1, abbey + 1, ordains_left - 1, missions_left, (*path, "ordain"))
        if missions_left > 0 and abbey > 0:
            walk(village, abbey - 1, ordains_left, missions_left - 1, (*path, "mission"))

    walk(start_village, start_abbey, ordain_count, mission_count, ())
    return orders


def _click_for(server, step: dict) -> dict:
    """The click that answers one step, chosen by the step's kind and never by what it is about."""
    if step["kind"] in {"position", "origin", "skip", "duty"}:
        return _at(step["value"])
    if step["kind"] == "edge":
        return _follow(step["value"])
    if step["kind"] == "resource":
        return _take(step["value"], _active_seat(server))
    if step["kind"] == "combination":
        return _pay(step["value"])
    if step["kind"] == "hire":
        return _pay(step["value"])
    if step["kind"] == "seat":
        return _name(step["value"])
    if step["kind"] == "building":
        return _build(step["value"])
    return _do(step["value"])


def _active_seat(server) -> int:
    return SEATED_PLAYERS.index(server.payload["state"]["active_player"]) + 1


# ---------------------------------------------------------------------------------------------
# What the engine says may come next
# ---------------------------------------------------------------------------------------------


ALMS_PAIR = ("alms_payment_silver", "alms_payment_wheat")


def _hire_step_value(action: FullTurnAction) -> str:
    if action.hired_building_id is None:
        return "none"
    return f"{action.hired_building_id}:{action.hired_building_source or 'unknown'}"


def _offer_flags_by_action_id(
    actions: list[Any],
    *,
    state: Any,
    config: Any,
) -> tuple[dict[str, bool], dict[str, tuple[str, ...]]]:
    """Mirror play-server context gating for hire-step emission."""
    hire_contexts = play_server._hire_contexts(actions, config)
    player_id = play_server._speaking_player_id(state)
    offer_hire_by_action_id: dict[str, bool] = {}
    hire_payment_buildings_by_action_id: dict[str, tuple[str, ...]] = {}
    for action in actions:
        move_id = action_id(action)
        offer_hire_by_action_id[move_id] = isinstance(action, FullTurnAction) and (
            play_server._resolution_context_key(action, config) in hire_contexts
        )
    hire_payment_buildings_by_action_id = play_server._hire_payment_question_buildings_by_action_id(
        actions,
        player_id=player_id,
        state=state,
        config=config,
        offer_hire_by_action_id=offer_hire_by_action_id,
    )
    return (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    )


def _engine_steps(
    action,
    *,
    config: Any,
    offer_hire: bool = False,
    hire_payment_buildings: tuple[str, ...] = (),
) -> list[dict]:
    """One legal action as the sequence of decisions that reaches it, spelled out here by hand.

    Deliberately not `decision_steps`: comparing the page against the same function that fed it
    would only show the page copied it faithfully. Every field is read off the action itself, so
    what the offers are checked against is the engine's own answer about what is legal.
    """

    def paid_resource_for(building_id: str) -> str:
        for paid_building, paid_resource in tuple(action.hire_payments or ()):
            if paid_building == building_id:
                return paid_resource
        return "none"

    route, _omitted_edge_index = play_server._route_destinations_for_steps(action, config)
    steps: list[dict] = []
    steps.append({"kind": "origin", "value": action.origin})
    path = (action.origin, *route)
    steps += [
        {
            "kind": "edge",
            "value": f"{CANONICAL_POSITION_NAMES[path[index]]}"
            f"->{CANONICAL_POSITION_NAMES[path[index + 1]]}",
        }
        for index in range(len(route))
    ]
    if isinstance(action, SetupSowAction):
        return steps
    if action.sow_route_omitted_location is not None:
        steps.append({"kind": "skip", "value": action.sow_route_omitted_location})
    steps.append({"kind": "duty", "value": action.selected_duty})
    steps.append({"kind": "resolution", "value": action.resolution.value})
    if offer_hire:
        steps.append({"kind": "hire", "value": _hire_step_value(action)})
    for building_id in hire_payment_buildings:
        steps.append({"kind": "resource", "value": paid_resource_for(building_id)})
    for name in ("tithe_resource", "taxation_step1_resource"):
        # Read through the constant so that a test which takes a field off the page takes it off
        # this side too. Everywhere else the two are the same tuple, and this mirror is still built
        # by hand from the action rather than from `decision_steps`.
        if name not in play_server.RESOURCE_CHOICE_FIELDS:
            continue
        if getattr(action, name) is not None:
            steps.append({"kind": "resource", "value": getattr(action, name)})
    if action.construct_building_id is not None:
        steps.append({"kind": "building", "value": action.construct_building_id})
    if action.resolution.value == "give_alms_paid":
        silver, wheat = (getattr(action, name) for name in ALMS_PAIR)
        steps.append(
            {
                "kind": "combination",
                "value": f"silver={silver},wheat={wheat}",
                "resource_allocation": True,
                "resource_allocation_any_total": True,
            }
        )
    if action.resolution.value == "taxation":
        taken = tuple(action.taxation_step2_resources or ())
        counted = ",".join(f"{noun}={taken.count(noun)}" for noun in ("stone", "silver", "wheat"))
        steps.append(
            {
                "kind": "combination",
                "value": counted,
                "resource_allocation": True,
                "resource_total": len(taken),
            }
        )
    if action.resolution.value == "allocation":
        outcome = allocation_outcome(action.allocation_moves)
        encoded = ",".join(f"{slot}={delta:+d}" for slot, delta in outcome) if outcome else "none"
        steps.append({"kind": "arrangement", "value": encoded})
    if action.resolution.value == "ordination":
        counts = dict(ordination_outcome(action.ordination_steps))
        ordain = int(counts.get("ordain", 0))
        mission = int(counts.get("mission", 0))
        terms: list[str] = []
        if ordain:
            terms.append(f"ordain={ordain}")
        if mission:
            terms.append(f"mission={mission}")
        steps.append({"kind": "ordination", "value": ",".join(terms) if terms else "none"})
    return steps


def _engine_decisions(server) -> list[list[dict]]:
    """Every legal move as its sequence of decisions, with no two the same."""
    actions = list(legal_actions(server.state, server.config))
    (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    ) = _offer_flags_by_action_id(
        actions,
        state=server.state,
        config=server.config,
    )
    decisions: list[list[dict]] = []
    for action in actions:
        move_id = action_id(action)
        steps = _engine_steps(
            action,
            config=server.config,
            offer_hire=offer_hire_by_action_id[move_id],
            hire_payment_buildings=hire_payment_buildings_by_action_id[move_id],
        )
        if steps not in decisions:
            decisions.append(steps)
    return decisions


def _values(steps: list[dict]) -> list:
    return [step["value"] for step in steps]


def _values_except(steps: list[dict], kind: str) -> list:
    """Everything a move decides apart from one kind of question, for finding its siblings."""
    return [step["value"] for step in steps if step["kind"] != kind]


def _next_steps(decisions: list[list[dict]], prefix: list) -> list[dict]:
    live = [steps for steps in decisions if _values(steps)[: len(prefix)] == prefix]
    seen: list[dict] = []
    for steps in live:
        if len(steps) > len(prefix) and steps[len(prefix)]["value"] not in _values(seen):
            seen.append(steps[len(prefix)])
    return seen


def _next_values(decisions: list[list[dict]], prefix: list) -> list:
    return _values(_next_steps(decisions, prefix))


def _page_auto_advances(
    server, prefix: list, step: dict, enabled_route_toggles: set[str] | None = None
) -> bool:
    """Whether this engine step is one the payload says the page has already followed."""
    enabled_route_toggles = enabled_route_toggles or set()
    selection = _always_visible_route_families(server.payload) | frozenset(
        family["i"]
        for family in server.payload["families"]
        if (
            family["i"] in server.payload.get("auto_family_indexes", [])
            and family["building_id"] in enabled_route_toggles
        )
    )
    index = len(prefix)
    matching = [
        candidate["steps"][index]
        for candidate in server.payload["turn_candidates"]
        if _candidate_is_reachable_with_families(candidate, selection)
        and len(candidate["steps"]) > index
        and [previous["value"] for previous in candidate["steps"][:index]] == prefix
        and candidate["steps"][index]["kind"] == step["kind"]
        and candidate["steps"][index]["value"] == step["value"]
    ]
    assert matching, f"no page candidate matched engine step {step!r} after {prefix!r}"
    return all(_auto_advance_for_families(current, selection) for current in matching)


def _route_toggle_ids_for_edge(server, prefix: list, step: dict) -> tuple[str, ...]:
    """The server-described tile toggles needed to make this particular edge visible."""
    assert step["kind"] == "edge"
    index = len(prefix)
    visibility_by_building_id = {
        ability["building_id"]: ability.get("family_visibility")
        for ability in server.payload["building_abilities"]
    }
    families_by_index = {family["i"]: family for family in server.payload["families"]}
    route_building_ids = {
        families_by_index[building_index]["building_id"]
        for candidate in server.payload["turn_candidates"]
        if len(candidate["steps"]) > index
        and [previous["value"] for previous in candidate["steps"][:index]] == prefix
        and candidate["steps"][index]["kind"] == "edge"
        and candidate["steps"][index]["value"] == step["value"]
        for building_index in candidate.get("family", ())
    }
    return tuple(
        sorted(
            building_id
            for building_id in route_building_ids
            if visibility_by_building_id.get(building_id) == "toggle"
        )
    )


def _clicks_to(server, decisions: list[list[dict]], target: list) -> list[dict]:
    """The clicks that reach one particular move, except server-marked route continuations.

    Which affordance each click uses comes from the engine's own step kind, so a test never has to
    know that a tithe's stock is pressed on a board and an alms payment beside it.
    """
    clicks: list[dict] = []
    prefix: list = []
    enabled_route_toggles: set[str] = set()
    while True:
        if len(prefix) >= len(target):
            return clicks
        value = target[len(prefix)]
        step = next(s for s in _next_steps(decisions, prefix) if s["value"] == value)
        if _page_auto_advances(server, prefix, step, enabled_route_toggles):
            prefix.append(value)
            continue
        if step["kind"] == "arrangement":
            prefix.append(value)
            clicks += _arrangement_clicks(str(value))
            continue
        if step["kind"] == "ordination":
            prefix.append(value)
            clicks += _ordination_clicks(str(value))
            continue
        if step["kind"] == "combination" and step.get("resource_allocation"):
            counts = _counts(value)
            for resource in ("stone", "silver", "wheat"):
                clicks.extend(
                    _take(resource, _active_seat(server)) for _ in range(counts.get(resource, 0))
                )
            return clicks
        if step["kind"] == "resolution":
            options = [s for s in _next_steps(decisions, prefix) if s["kind"] == "resolution"]
            if value == "tithe":
                clicks.append(_press("tithe"))
            else:
                clicks.append(_press("action"))
                if len([s for s in options if s["value"] != "tithe"]) > 1:
                    clicks.append(_do(value))
            prefix.append(value)
            continue
        if step["kind"] == "edge":
            for building_id in _route_toggle_ids_for_edge(server, prefix, step):
                if building_id not in enabled_route_toggles:
                    clicks.append({"kind": "route_toggle", "value": building_id})
                    enabled_route_toggles.add(building_id)
        prefix.append(value)
        clicks.append(_click_for(server, step))


@needs_node
@pytest.mark.parametrize("phase", ["setup_sow", "sow"])
def test_what_is_offered_is_what_the_engine_says_may_come_next(phase, tmp_path: Path) -> None:
    """The options at each point are the distinct next decisions of the surviving moves, no more.

    Held against `legal_actions` rather than against any route somebody typed out, and run on both
    a setup sow and a normal turn, because a normal turn asks two questions the sow never does:
    which duty was selected, and what to do with it.
    """
    server = _served(tmp_path)
    if phase == "sow":
        _played_through_setup(server)
    assert server.payload["state"]["phase"] == phase

    decisions = _engine_decisions(server)
    clicks: list = []
    prefix: list = []
    for _question in range(3):
        next_steps = _next_steps(decisions, prefix)
        expected = _values(next_steps)
        while len(next_steps) == 1 and _page_auto_advances(server, prefix, next_steps[0]):
            prefix.append(next_steps[0]["value"])
            next_steps = _next_steps(decisions, prefix)
            expected = _values(next_steps)
        transcript = _run_script(server, list(clicks), tmp_path)
        if all(step["kind"] == "resolution" for step in next_steps):
            grouped = []
            if any(step["value"] != "tithe" for step in next_steps):
                grouped.append("action")
            if any(step["value"] == "tithe" for step in next_steps):
                grouped.append("tithe")
            assert sorted(map(str, transcript["offered"][-1])) == sorted(map(str, grouped))
        else:
            assert sorted(map(str, transcript["offered"][-1])) == sorted(map(str, expected))
        step = next(s for s in next_steps if s["value"] == expected[0])
        prefix.append(expected[0])
        if step["kind"] == "resolution":
            if step["value"] == "tithe":
                clicks.append(_press("tithe"))
            else:
                clicks.append(_press("action"))
                if (
                    len(
                        [
                            s
                            for s in next_steps
                            if s["kind"] == "resolution" and s["value"] != "tithe"
                        ]
                    )
                    > 1
                ):
                    clicks.append(_do(step["value"]))
        else:
            clicks.append(_click_for(server, step))
    assert clicks, "the position asked nothing, so nothing was checked"


@needs_node
def test_pulpit_asks_its_sow_acts_and_auto_advances_its_sole_edge(tmp_path: Path) -> None:
    """The thin Pulpit board still makes its pickup and duty visible acts."""
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_PULPIT)
    try:
        origin, edge, duty = server.payload["turn_candidates"][0]["steps"][:3]
        assert origin.get("auto") is None
        assert edge["auto"] == [0]
        assert duty.get("auto") is None
        expected = (
            ([], "Choose a space to lift acolytes from.", [1]),
            ([_at(1)], "Choose a duty to take.", [2]),
        )
        for clicks, prompt_end, offered in expected:
            transcript = _run_script(server, clicks, tmp_path)
            assert transcript["asking"][-1][0].endswith(prompt_end)
            assert transcript["offered"][-1] == offered
    finally:
        server.server_close()


@needs_node
def test_enabled_kogge_keeps_the_dormitory_sow_route_choice_visible(tmp_path: Path) -> None:
    """The page consumes the server's Kogge selection marker instead of auto-following a fork."""
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    try:
        dormitory = next(
            step
            for step in server.payload["turn_steps"]
            if step["building_id"] == "dormitory" and step.get("selected_position") == 4
        )
        server.apply_turn_step(dormitory["step_id"], server.payload["state_token"])

        transcript = _run_script(
            server,
            [
                {"kind": "position", "value": 0},
                {"kind": "route_toggle", "value": "kogge"},
                {"kind": "edge", "value": "city->south"},
            ],
            tmp_path,
        )
        assert transcript["offered"][-1] == ["south->city", "south->south_west"]
    finally:
        server.server_close()


@needs_node
def test_page_reports_an_enabled_route_family_missing_from_the_server_mask_list(
    tmp_path: Path,
) -> None:
    """A payload drift must be loud instead of merely disabling all automatic continuations."""
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    try:
        server.payload["auto_family_indexes"] = []
        transcript = _run_script(
            server,
            [
                {"kind": "position", "value": 0},
                {"kind": "route_toggle", "value": "kogge"},
            ],
            tmp_path,
        )
        assert any(
            error.startswith("auto-advance family mask mismatch: enabled family index 0")
            for error in transcript["consoleErrors"]
        )
    finally:
        server.server_close()


@needs_node
def test_every_playtest_end_window_directly_confirms_its_only_engine_action(tmp_path: Path) -> None:
    """Every sampled End window must let Confirm submit the EndTurnAction it alone permits."""
    observed: list[tuple[str, str, str]] = []
    for scenario_path in sorted(PLAYTEST_SCENARIOS.glob("*.json")):
        server = PlayServer(("127.0.0.1", 0), scenario_path)
        try:
            full_turn = next(
                action
                for action in legal_actions(server.state, server.config)
                if isinstance(action, FullTurnAction)
            )
            server.apply(action_id(full_turn), server.payload["state_token"])
            assert list(legal_actions(server.state, server.config)) == [EndTurnAction()]
            transcript = _run_script(server, [], tmp_path)
            observed.append(
                (
                    scenario_path.name,
                    transcript["controls"][-1]["confirm"],
                    transcript["confirmLabels"][-1],
                )
            )
        finally:
            server.server_close()

    assert len(observed) == len(PLAYTEST_POSITION_NAMES) == 6
    assert all(enabled == "true" and label == "end_turn" for _, enabled, label in observed), observed

    for scenario_path, _, _ in observed:
        server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / scenario_path)
        try:
            full_turn = next(
                action
                for action in legal_actions(server.state, server.config)
                if isinstance(action, FullTurnAction)
            )
            server.apply(action_id(full_turn), server.payload["state_token"])
            transcript = _run_script(server, [], tmp_path, confirm=True)
            assert transcript["posted"]["action_id"] == action_id(EndTurnAction())
        finally:
            server.server_close()


def test_a_move_runs_to_no_fixed_number_of_decisions(tmp_path: Path) -> None:
    """Nothing may assume how many decisions a move takes, and the same script walks any of them.

    This used to say the two phases never run the same length, which stopped being true the moment
    Taxation gained its bonus step: a taxation turn now decides six things, exactly as a setup sow
    does. The guarantee was never really about the phases differing, though -- it is that no number
    is written down anywhere to be assumed, and a single turn position now reaching several lengths
    at once says that better than two phases that happened not to collide.

    A route is as long as the number of acolytes lifted, so lengths vary by origin as well.
    """
    server = _served(tmp_path)
    setup_lengths = {len(steps) for steps in _engine_decisions(server)}
    _played_through_setup(server)
    turn_lengths = {len(steps) for steps in _engine_decisions(server)}

    assert len(turn_lengths) > 1, "every turn here ran to one length, so nothing varies"
    assert len(setup_lengths | turn_lengths) > len(setup_lengths)


# ---------------------------------------------------------------------------------------------
# Playing a turn
# ---------------------------------------------------------------------------------------------


def test_four_players_sow_in_turn_and_the_board_comes_back_with_the_acolytes_on_it(
    tmp_path: Path,
) -> None:
    """The payoff: after a sow the pieces are where they landed, drawn from the state.

    The page that comes back is rendered by the server from the position it now holds. Nothing in
    the browser draws a piece, so the cubes counted below could only have got there by the board
    being redrawn -- which is the whole reason the response is a page and not a patch.
    """
    server = _served(tmp_path)
    with _running(server) as base:
        first = server.payload["state"]["active_player"]
        city_before = server.payload["state"]["acolytes"][0][0]
        page_before = render_play_view_from_payload(server.payload)

        pages = []
        for _seat in range(4):
            candidate = server.payload["turn_candidates"][0]
            status, page = _post(base, candidate["action_id"], server.payload["state_token"])
            assert status == 200
            pages.append(page)
        final = _get_json(base, "/state.json")

    sown = [
        CANONICAL_POSITION_NAMES.index(step["value"].split("->", 1)[1])
        for step in candidate["steps"]
        if step["kind"] == "edge"
    ]
    assert _cubes_at(page_before, sown[0], first) == 0
    assert _cubes_at(pages[0], sown[0], first) > 0
    assert final["state"]["acolytes"][0][0] < city_before

    # Setup is over: the phase has turned and the seat on is the one the round starts with.
    assert final["state"]["phase"] == "sow"
    assert final["state"]["active_player"] == final["state"]["start_player_id"]
    log = server.payload["log"]
    assert any("Setup complete." in line for line in log)
    assert any(final["state"]["start_player_id"] in line for line in log)


def test_a_normal_turn_moves_the_cubes_pays_for_itself_and_passes_the_seat(
    tmp_path: Path,
) -> None:
    """A whole turn, played the way the page plays it, and the board comes back changed."""
    server = _played_through_setup(_served(tmp_path))
    with _running(server) as base:
        before = _get_json(base, "/state.json")
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"])
        resolution_status, _page = _post(
            base,
            settled["action_id"],
            server.payload["state_token"],
        )
        assert server.state.turn_progress.resolution_committed
        status, _page = _post(
            base,
            action_id(EndTurnAction()),
            server.payload["state_token"],
        )
        after = _get_json(base, "/state.json")

    assert resolution_status == 200
    assert status == 200
    assert after["state"]["acolytes"] != before["state"]["acolytes"], "no cube moved"
    assert after["state"]["players"] != before["state"]["players"], "nothing was gained or spent"
    assert after["state"]["active_player"] != before["state"]["active_player"]


@needs_node
def test_a_turn_is_shown_in_words_before_it_is_sent_and_needs_a_press(tmp_path: Path) -> None:
    """Nothing is committed by running out of questions. The last click is agreeing to it.

    The words are player-facing, and the line above Confirm comes from the same formatter the log
    block will use for this action.
    """
    server = _played_through_setup(_served(tmp_path))
    decisions = _engine_decisions(server)
    candidates = server.payload["turn_candidates"]
    index = next(
        i
        for i, c in enumerate(candidates)
        if c["action_id"]
        and not any(step.get("resource_allocation_any_total") for step in c["steps"])
    )
    candidate = candidates[index]
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])

    answered = _run_script(server, clicks, tmp_path)
    assert answered["shownPanel"][-1] == index, "the decided turn was not the one shown"
    assert answered["posted"] is None, "the turn went without anybody agreeing to it"

    chosen = next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    assert candidate["summary"] == action_summary_for_players(
        chosen, server.config, actor=server.state.active_player, state=server.state
    )

    confirmed = _run_script(server, clicks, tmp_path, confirm=True)
    assert confirmed["posted"]["action_id"] == candidate["action_id"]
    assert confirmed["posted"]["state_token"] == server.payload["state_token"]


def test_confirm_summary_and_logged_action_line_are_identical(tmp_path: Path) -> None:
    server = _played_through_setup(_served(tmp_path))
    candidate = next(c for c in server.payload["turn_candidates"] if c["action_id"])
    summary = candidate["summary"]
    assert summary is not None

    server.apply(candidate["action_id"], server.payload["state_token"])
    block = server.payload["log_blocks"][-1]
    assert block["lines"][0] == summary


@needs_node
def test_resetting_a_half_built_turn_sends_nothing_and_moves_nothing(tmp_path: Path) -> None:
    """Nothing goes until confirm is pressed, so giving up is local and must stay local."""
    server = _played_through_setup(_served(tmp_path))
    with _running(server) as base:
        before = _get_json(base, "/state.json")
        transcript = _run_script(server, [_at(1)], tmp_path, reset=True)
        after = _get_json(base, "/state.json")

    assert transcript["posted"] is None, "a half-built turn was submitted"
    assert transcript["afterReset"]["shown"] == -1, "reset left a turn ready to commit"
    assert after == before


# ---------------------------------------------------------------------------------------------
# The questions a resolution goes on to ask
# ---------------------------------------------------------------------------------------------


def _reference_server():
    """The committed reference board, played through setup to the first normal turn.

    The reference board rather than a generated one because it is the position the play view is
    drawn for, and it happens to reach a Cornucopia, the Taxation tile and a paid alms in the same
    turn -- which is all three of the questions this PR gives the page a way to ask.
    """
    return _played_through_setup(PlayServer(("127.0.0.1", 0), REFERENCE))


def _with_counter_under_the_merchant(scenario, value: str):
    """Put one tithe counter on the tile the Merchant occupies, leaving everything else alone."""
    position_name = scenario.config.board.positions[scenario.state.merchant_board_position]
    counters = scenario.config.tithe_counters
    moved = tuple(
        (name, value if name == position_name else resource)
        for name, resource in counters.counters_by_position
    )
    return replace(scenario.config, tithe_counters=replace(counters, counters_by_position=moved))


def _with_stock(state, *, stone: int, silver: int, wheat: int):
    """Set the acting player's goods so affordability is under test and not fixture drift."""
    player = state.active_player
    player_state = state.player_state(player)
    resources = replace(player_state.resources, stone=stone, silver=silver, wheat=wheat)
    return state.with_player_state(player, replace(player_state, resources=resources))


def _stocks(server, player_id: str) -> dict:
    """One seat's three stocks, off the payload the page is drawn from."""
    from tools.ui_debug.play_view_adapter import player_record

    return dict(player_record(server.payload, player_id)["resources"])


def _resolves(candidate: dict, resolution: str) -> bool:
    """Whether one candidate's turn resolves the named way.

    Matched on kind and value, which is what a step IS. The other things it carries are what a
    player reads -- the label on a combination key, the sentence asking the question -- and two
    steps that differ only in those are the same decision worded twice, which is exactly why the
    grouping key on the server is built from the values alone.
    """
    return any(
        step["kind"] == "resolution" and step["value"] == resolution for step in candidate["steps"]
    )


def _asked(server, resolution: str, kind: str) -> list[dict]:
    """Candidates for one resolution that go on to ask a further question of the given kind."""
    return [
        candidate
        for candidate in server.payload["turn_candidates"]
        if _resolves(candidate, resolution)
        and any(step["kind"] == kind for step in candidate["steps"])
    ]


def _siblings(candidates: list[dict], candidate: dict, kind: str) -> list[dict]:
    """The candidates alike in everything but their answer to one kind of question."""
    wanted = _values_except(candidate["steps"], kind)
    return [other for other in candidates if _values_except(other["steps"], kind) == wanted]


def _answer(candidate: dict, kind: str):
    return next(step["value"] for step in candidate["steps"] if step["kind"] == kind)


def _action_for_candidate(server: PlayServer, candidate: dict) -> Any:
    return next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )


def _pass_end_turn_window(server: PlayServer) -> None:
    assert server.state.turn_progress.resolution_committed
    server.apply(action_id(EndTurnAction()), server.payload["state_token"])


def _apply_settled_turn_and_pass(server: PlayServer, candidate: dict) -> None:
    server.apply(candidate["action_id"], server.payload["state_token"])
    if server.state.turn_progress.resolution_committed:
        _pass_end_turn_window(server)


def test_dormitory_turn_step_payload_names_the_selected_duty_and_applies_it() -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "dormitory_active_return_duty_to_city_001.json"
    )
    try:
        step = next(
            step for step in server.payload["turn_steps"] if step["building_id"] == "dormitory"
        )
        city = server.config.board.index_for_name("city")
        chosen_from = int(step["selected_position"])
        before = server.state.player_vector(server.state.active_player)
        server.apply_turn_step(str(step["step_id"]), str(server.payload["state_token"]))

        assert step["kind"] == "relocation"
        assert step["source"] == "own_active"
        assert (
            server.state.player_vector(server.state.active_player)[chosen_from]
            == before[chosen_from] - 1
        )
        assert server.state.player_vector(server.state.active_player)[city] == before[city] + 1
    finally:
        server.server_close()


def test_inquisition_turn_step_payload_names_the_selected_duty_and_applies_it() -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "inquisition_active_city_to_duty_001.json")
    try:
        step = next(
            step for step in server.payload["turn_steps"] if step["building_id"] == "inquisition"
        )
        city = server.config.board.index_for_name("city")
        chosen_to = int(step["selected_position"])
        before = server.state.player_vector(server.state.active_player)
        server.apply_turn_step(str(step["step_id"]), str(server.payload["state_token"]))

        assert step["kind"] == "relocation"
        assert step["source"] == "own_active"
        assert server.state.player_vector(server.state.active_player)[city] == before[city] - 1
        assert (
            server.state.player_vector(server.state.active_player)[chosen_to]
            == before[chosen_to] + 1
        )
    finally:
        server.server_close()


def test_library_turn_step_is_offered_only_in_the_end_of_turn_window() -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "library_active_city_to_duty_001.json")
    try:
        assert not any(step["building_id"] == "library" for step in server.payload["turn_steps"])
        candidate = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        server.apply(str(candidate["action_id"]), str(server.payload["state_token"]))
        city = server.config.board.index_for_name("city")
        library_step = next(
            step
            for step in server.payload["turn_steps"]
            if step["building_id"] == "library" and step["selected_position"] == "abbey"
        )
        assert library_step["kind"] == "relocation"
        before = server.state.player_vector(server.state.active_player)
        server.apply_turn_step(str(library_step["step_id"]), str(server.payload["state_token"]))
        assert server.state.player_vector(server.state.active_player)[city] == before[city] - 1
        assert server.state.player_state(server.state.active_player).workforce.abbey >= 1
    finally:
        server.server_close()


def _played_from_the_page(server, candidate: dict, tmp_path: Path):
    """Walk the page to one candidate, agree to it, and apply exactly what it sent."""
    decisions = _engine_decisions(server)
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])
    transcript = _run_script(server, clicks, tmp_path, confirm=True)
    assert transcript["posted"] is not None, "the page found nothing to submit"
    assert transcript["posted"]["action_id"] == candidate["action_id"]
    server.apply(transcript["posted"]["action_id"], transcript["posted"]["state_token"])
    return transcript


def _allocation_candidates(server) -> list[dict]:
    return [
        candidate
        for candidate in server.payload["turn_candidates"]
        if _resolves(candidate, "allocation")
        and any(step["kind"] == "arrangement" for step in candidate["steps"])
    ]


def _ordination_candidates(server) -> list[dict]:
    return [
        candidate
        for candidate in server.payload["turn_candidates"]
        if _resolves(candidate, "ordination")
        and any(step["kind"] == "ordination" for step in candidate["steps"])
    ]


def _hire_candidates(server, resolution: str) -> list[dict]:
    return [
        candidate
        for candidate in server.payload["turn_candidates"]
        if candidate["action_id"] is not None
        and _resolves(candidate, resolution)
        and any(step["kind"] == "hire" for step in candidate["steps"])
    ]


def _step_index(candidate: dict, kind: str) -> int:
    return next(index for index, step in enumerate(candidate["steps"]) if step["kind"] == kind)


def _arrangement_terms(value: str) -> list[tuple[str, int]]:
    if value == "none":
        return []
    return [(slot, int(delta)) for slot, delta in (part.split("=", 1) for part in value.split(","))]


def _clicks_before_arrangement(server, candidate: dict) -> list[dict]:
    decisions = _engine_decisions(server)
    prefix: list = []
    for step in candidate["steps"]:
        if step["kind"] == "arrangement":
            break
        prefix.append(step["value"])
    return _clicks_to(server, decisions, prefix)


def _clicks_before_ordination(server, candidate: dict) -> list[dict]:
    decisions = _engine_decisions(server)
    prefix: list = []
    for step in candidate["steps"]:
        if step["kind"] == "ordination":
            break
        prefix.append(step["value"])
    return _clicks_to(server, decisions, prefix)


@needs_node
def test_allocation_arrangements_reached_in_two_orders_submit_one_canonical_action(
    tmp_path: Path,
) -> None:
    first = PlayServer(("127.0.0.1", 0), SCENARIOS / "allocation_multi_move_001.json")
    candidates = _allocation_candidates(first)
    assert candidates, "no allocation candidates were offered"

    target = next(
        (
            candidate
            for candidate in candidates
            if any(
                slot == "abbey" and delta <= -2
                for slot, delta in _arrangement_terms(_answer(candidate, "arrangement"))
            )
            and len(
                [
                    slot
                    for slot, delta in _arrangement_terms(_answer(candidate, "arrangement"))
                    if delta > 0
                ]
            )
            >= 2
        ),
        None,
    )
    assert target is not None, "fixture had no two-drop allocation arrangement to exercise order"
    terms = _arrangement_terms(_answer(target, "arrangement"))
    destinations = [slot for slot, delta in terms if delta > 0]
    first_then_second = _clicks_before_arrangement(first, target) + [
        _lift_from("abbey"),
        _place_on(destinations[0]),
        _lift_from("abbey"),
        _place_on(destinations[1]),
    ]
    posted_a = _run_script(first, first_then_second, tmp_path, confirm=True)["posted"]
    assert posted_a is not None
    assert posted_a["action_id"] == target["action_id"]

    second = PlayServer(("127.0.0.1", 0), SCENARIOS / "allocation_multi_move_001.json")
    twin = next(
        candidate
        for candidate in _allocation_candidates(second)
        if candidate["action_id"] == target["action_id"]
    )
    second_then_first = _clicks_before_arrangement(second, twin) + [
        _lift_from("abbey"),
        _place_on(destinations[1]),
        _lift_from("abbey"),
        _place_on(destinations[0]),
    ]
    posted_b = _run_script(second, second_then_first, tmp_path, confirm=True)["posted"]
    assert posted_b is not None
    assert posted_b["action_id"] == target["action_id"]


@needs_node
def test_ordination_counts_reached_in_two_orders_submit_one_canonical_action(
    tmp_path: Path,
) -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "ordination_mill_active_three_steps_one_wheat_001.json"
    )
    try:
        candidates = _ordination_candidates(server)
        assert candidates, "fixture offered no ordination candidates"

        active = server.payload["state"]["active_player"]
        start = _seat_allocation_state(server, active)
        start_village = int(start["village"])
        start_abbey = int(start["abbey"])

        for candidate in candidates:
            ordain_count, mission_count = _ordination_counts(_answer(candidate, "ordination"))
            if ordain_count <= 0 or mission_count <= 0:
                continue
            orders = _legal_ordination_orders(
                start_village=start_village,
                start_abbey=start_abbey,
                ordain_count=ordain_count,
                mission_count=mission_count,
            )
            if len(orders) < 2:
                continue

            for index, first_order in enumerate(orders[:-1]):
                clicks_a = _clicks_before_ordination(server, candidate) + [
                    _ordain_click() if step == "ordain" else _mission_click()
                    for step in first_order
                ]
                try:
                    posted_a = _run_script(server, clicks_a, tmp_path, confirm=True)["posted"]
                except subprocess.CalledProcessError:
                    continue
                if posted_a is None or posted_a["action_id"] != candidate["action_id"]:
                    continue

                for second_order in orders[index + 1 :]:
                    twin_server = PlayServer(
                        ("127.0.0.1", 0),
                        SCENARIOS / "ordination_mill_active_three_steps_one_wheat_001.json",
                    )
                    try:
                        twin = next(
                            offered
                            for offered in _ordination_candidates(twin_server)
                            if offered["action_id"] == candidate["action_id"]
                        )
                        clicks_b = _clicks_before_ordination(twin_server, twin) + [
                            _ordain_click() if step == "ordain" else _mission_click()
                            for step in second_order
                        ]
                        try:
                            posted_b = _run_script(twin_server, clicks_b, tmp_path, confirm=True)[
                                "posted"
                            ]
                        except subprocess.CalledProcessError:
                            continue
                        if posted_b is not None and posted_b["action_id"] == candidate["action_id"]:
                            return
                    finally:
                        twin_server.server_close()
    finally:
        server.server_close()

    raise AssertionError("no ordination outcome was playable in two legal click orders")


def test_ordination_candidate_summary_names_steps_and_cost() -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "ordination_mill_active_three_steps_one_wheat_001.json"
    )
    try:
        candidate = next(
            (
                offered
                for offered in _ordination_candidates(server)
                if _answer(offered, "ordination") == "ordain=1,mission=1"
            ),
            None,
        )
        assert candidate is not None, "fixture offered no one-ordain one-mission ordination outcome"
        assert (
            candidate["summary"]
            == "player_one chose Ordination at Ordination — ordained 1 serf into the Abbey; sent 1 acolyte on mission to the City; paid 0 wheat (2 due, 2 waived by the Mill)."
        )
        server.apply(candidate["action_id"], server.payload["state_token"])
        block = server.payload["log_blocks"][-1]
        assert block["lines"][0] == "player_one chose Ordination at Ordination."
    finally:
        server.server_close()


def _ordination_choice(step: dict, value: str) -> dict:
    return next(choice for choice in step["choices"] if choice["value"] == value)


def _ordination_choice_state(choice: dict, at: str) -> dict:
    return next(state for state in choice["states"] if state["at"] == at)


def test_ordination_choices_carry_server_availability_and_reasons() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_ordination_substitution_001.json")
    steps = [
        step
        for candidate in play_server.turn_candidates(
            scenario.state, scenario.config, include_preview_effects=False
        )
        for step in candidate["steps"]
        if step["kind"] == "ordination"
    ]
    assert steps, "fixture offered no Ordination choices"

    for step in steps:
        ordain = _ordination_choice(step, "ordain")
        mission = _ordination_choice(step, "mission")
        assert ordain["available"] is True
        assert "reason" not in ordain
        assert mission["available"] is False
        assert mission["reason"] == "No acolyte in the Abbey."
        assert _ordination_choice_state(ordain, "ordain=1")["available"] is True
        assert _ordination_choice_state(mission, "ordain=1")["available"] is True
        assert _ordination_choice_state(ordain, "ordain=2") == {
            "at": "ordain=2",
            "available": False,
        }
        assert _ordination_choice_state(mission, "ordain=2") == {
            "at": "ordain=2",
            "available": False,
        }
        assert step["prompt"] == "player_one: Move serfs and acolytes, up to 2 in total."


def test_ordination_choices_name_an_affordability_block() -> None:
    scenario = load_scenario(SCENARIOS / "ordination_hire_mill_insufficient_resource_001.json")
    step = next(
        step
        for candidate in play_server.turn_candidates(
            scenario.state, scenario.config, include_preview_effects=False
        )
        for step in candidate["steps"]
        if step["kind"] == "ordination"
    )

    assert _ordination_choice_state(_ordination_choice(step, "mission"), "ordain=1") == {
        "at": "ordain=1",
        "available": False,
        "reason": "You cannot afford another move.",
    }


def test_the_corpus_retains_silent_spent_capacity_ordination_states() -> None:
    silent: list[tuple[str, str, str]] = []
    for scenario_path in sorted((*SCENARIOS.glob("*.json"), *PLAYTEST_SCENARIOS.glob("*.json"))):
        scenario = load_scenario(scenario_path)
        seen: set[tuple[str, str]] = set()
        for candidate in play_server.turn_candidates(
            scenario.state, scenario.config, include_preview_effects=False
        ):
            for step in candidate["steps"]:
                if step["kind"] != "ordination":
                    continue
                for choice in step["choices"]:
                    for status in choice["states"]:
                        key = (str(choice["value"]), str(status["at"]))
                        if key in seen:
                            continue
                        seen.add(key)
                        if status["available"] or status.get("reason"):
                            continue
                        silent.append((scenario_path.name, *key))
    # An Infirmary can make an extra continuation live after the ordinary capacity has been used,
    # so the capacity controls themselves are silent without requiring the whole frontier to stop.
    assert len(silent) >= 2, "the corpus no longer reaches silent spent-capacity states"
    assert {
        ("bank_active_ordination_substitution_001.json", "ordain", "ordain=2"),
        ("bank_active_ordination_substitution_001.json", "mission", "ordain=2"),
    }.issubset(silent)


@needs_node
def test_an_empty_allocation_outcome_lights_confirm_without_moving_cubes(tmp_path: Path) -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "allocation_multi_move_001.json")
    candidate = next(
        (c for c in _allocation_candidates(server) if _answer(c, "arrangement") == "none"), None
    )
    if candidate is None:
        pytest.skip("fixture had no empty arrangement outcome")

    clicks = _clicks_before_arrangement(server, candidate)
    transcript = _run_script(server, clicks, tmp_path)
    active = str(_active_seat(server))
    assert transcript["controls"][-1]["confirm"] == "true"
    assert (
        transcript["arrangements"][-1][active]["abbey"]
        == transcript["arrangements"][0][active]["abbey"]
    )
    assert (
        transcript["arrangements"][-1][active]["roles"]
        == transcript["arrangements"][0][active]["roles"]
    )

    posted = _run_script(server, clicks, tmp_path, confirm=True)["posted"]
    assert posted is not None
    assert posted["action_id"] == candidate["action_id"]

    from tools.ui_debug.play_view_adapter import player_record

    actor = server.payload["state"]["active_player"]
    before = player_record(server.payload, actor)
    before_turn = int(server.payload["state"]["timing"]["absolute_turn"])
    before_abbey = int(before["workforce"]["abbey"])
    before_roles = dict(before["special_activities"])
    server.apply(posted["action_id"], posted["state_token"])
    _pass_end_turn_window(server)
    after = player_record(server.payload, actor)
    assert int(server.payload["state"]["timing"]["absolute_turn"]) == before_turn + 1
    assert int(after["workforce"]["abbey"]) == before_abbey
    assert dict(after["special_activities"]) == before_roles


@needs_node
def test_allocation_role_to_role_and_role_to_abbey_use_the_same_click_path(tmp_path: Path) -> None:
    role_to_role = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "allocation_special_activity_to_special_activity_001.json"
    )
    role_candidate = next(
        candidate
        for candidate in _allocation_candidates(role_to_role)
        if len(
            [
                slot
                for slot, _delta in _arrangement_terms(_answer(candidate, "arrangement"))
                if slot == "abbey"
            ]
        )
        == 0
    )
    role_terms = _arrangement_terms(_answer(role_candidate, "arrangement"))
    source_role = next(slot for slot, delta in role_terms if delta < 0)
    destination_role = next(slot for slot, delta in role_terms if delta > 0)
    posted_role = _run_script(
        role_to_role,
        _clicks_before_arrangement(role_to_role, role_candidate)
        + [_lift_from(source_role), _place_on(destination_role)],
        tmp_path,
        confirm=True,
    )["posted"]
    assert posted_role is not None
    assert posted_role["action_id"] == role_candidate["action_id"]

    role_to_abbey = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "allocation_all_special_occupied_001.json"
    )
    abbey_candidate = next(
        candidate
        for candidate in _allocation_candidates(role_to_abbey)
        if any(
            slot == "abbey" and delta == 1
            for slot, delta in _arrangement_terms(_answer(candidate, "arrangement"))
        )
        and len(
            [
                slot
                for slot, delta in _arrangement_terms(_answer(candidate, "arrangement"))
                if delta < 0
            ]
        )
        == 1
    )
    abbey_terms = _arrangement_terms(_answer(abbey_candidate, "arrangement"))
    source = next(slot for slot, delta in abbey_terms if delta < 0)
    posted_abbey = _run_script(
        role_to_abbey,
        _clicks_before_arrangement(role_to_abbey, abbey_candidate)
        + [_lift_from(source), _place_on("abbey")],
        tmp_path,
        confirm=True,
    )["posted"]
    assert posted_abbey is not None
    assert posted_abbey["action_id"] == abbey_candidate["action_id"]


@needs_node
def test_allocation_click_targets_are_mouse_reachable_only_on_the_asked_board(
    tmp_path: Path,
) -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "allocation_multi_move_001.json")
    candidate = next(
        (
            c
            for c in _allocation_candidates(server)
            if any(
                slot != "abbey" and delta > 0
                for slot, delta in _arrangement_terms(_answer(c, "arrangement"))
            )
        ),
        None,
    )
    assert candidate is not None, "fixture had no allocation outcome that placed on a role circle"
    destination = next(
        slot
        for slot, delta in _arrangement_terms(_answer(candidate, "arrangement"))
        if slot != "abbey" and delta > 0
    )
    transcript = _run_script(
        server,
        _clicks_before_arrangement(server, candidate)
        + [_lift_from("abbey"), _place_on(destination)],
        tmp_path,
    )

    active = str(_active_seat(server))
    active_markers = transcript["arrangements"][-1][active]
    assert active_markers["arrangementChoice"] is True
    assert active_markers["pointerEvents"]["visibleAbbeyToken"] == "all"
    assert active_markers["pointerEvents"]["occupiedRoleToken"] == "all"
    assert active_markers["pointerEvents"]["emptyRoleCircle"] == "none"

    active_player = server.payload["state"]["active_player"]
    inactive_player = next(
        player_id
        for player_id in SEATED_PLAYERS
        if player_id in _seated(server) and player_id != active_player
    )
    inactive = str(SEATED_PLAYERS.index(inactive_player) + 1)
    inactive_markers = transcript["arrangements"][-1][inactive]
    assert inactive_markers["arrangementChoice"] is False
    assert inactive_markers["pointerEvents"]["firstAbbeyToken"] == "none"
    assert inactive_markers["pointerEvents"]["firstRoleToken"] == "none"
    assert inactive_markers["pointerEvents"]["emptyRoleCircle"] == "none"


@needs_node
def test_a_role_circle_covered_by_one_token_can_still_take_a_place_click_while_holding(
    tmp_path: Path,
) -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "allocation_chapter_house_second_acolyte_001.json"
    )
    candidate = next(
        (
            c
            for c in _allocation_candidates(server)
            if _answer(c, "arrangement") == "abbey=-1,vestry=+1"
        ),
        None,
    )
    assert candidate is not None, "fixture had no abbey-to-vestry arrangement to exercise"
    prefix = _clicks_before_arrangement(server, candidate)
    active = str(_active_seat(server))

    opening = _run_script(server, prefix, tmp_path)["arrangements"][-1][active]
    assert opening["roles"]["vestry"] == 1
    assert opening["roleCenterLayers"]["vestry"]["drawOrder"] == [
        "role-circle:vestry",
        "role-token:vestry:single",
    ]
    assert opening["roleCenterLayers"]["vestry"]["topmostLive"] == "role-token:vestry:single"

    held = _run_script(server, prefix + [_lift_from("abbey")], tmp_path)["arrangements"][-1][active]
    assert held["roleCenterLayers"]["vestry"]["topmostLive"] == "role-circle:vestry"

    placed = _run_script(
        server,
        prefix + [_lift_from("abbey"), _place_on("vestry")],
        tmp_path,
    )
    after = placed["arrangements"][-1][active]
    assert after["abbey"] == opening["abbey"] - 1
    assert after["roles"]["vestry"] == 2
    assert placed["controls"][-1]["confirm"] == "true"
    posted = _run_script(
        server,
        prefix + [_lift_from("abbey"), _place_on("vestry")],
        tmp_path,
        confirm=True,
    )["posted"]
    assert posted is not None
    assert posted["action_id"] == candidate["action_id"]


@pytest.mark.slow
def test_allocation_candidates_no_longer_refuse_on_allocation_moves() -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "deep_round_eighteen_seed_seven_two_player_001.json"
    )
    candidates = _allocation_candidates(server)
    assert candidates, "deep fixture offered no allocation turns to check"
    assert all("allocation_moves" not in candidate["unresolved"] for candidate in candidates)


def test_ordination_candidates_no_longer_refuse_on_ordination_steps() -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "ordination_mill_active_three_steps_one_wheat_001.json"
    )
    candidates = _ordination_candidates(server)
    assert candidates, "fixture offered no ordination candidates to check"
    assert all("ordination_steps" not in candidate["unresolved"] for candidate in candidates)


def test_allocation_hire_step_precedes_arrangement_and_controls_move_count() -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "allocation_hire_infirmary_market_001.json")
    legal = {action_id(action): action for action in legal_actions(server.state, server.config)}
    candidates = _hire_candidates(server, "allocation")
    assert candidates, "fixture offered no allocation candidates with a hire step"
    assert {"none", "infirmary:market"} <= {_answer(candidate, "hire") for candidate in candidates}
    assert all(
        _step_index(candidate, "hire") < _step_index(candidate, "arrangement")
        for candidate in candidates
    )

    no_hire_moves = {
        len(legal[candidate["action_id"]].allocation_moves)
        for candidate in candidates
        if _answer(candidate, "hire") == "none"
    }
    hired_moves = {
        len(legal[candidate["action_id"]].allocation_moves)
        for candidate in candidates
        if _answer(candidate, "hire") != "none"
    }
    assert no_hire_moves == {1}
    assert any(count >= 2 for count in hired_moves)


def test_ordination_hire_step_precedes_ordination_and_controls_step_count() -> None:
    server = PlayServer(
        ("127.0.0.1", 0), SCENARIOS / "ordination_hire_mill_market_three_steps_001.json"
    )
    legal = {action_id(action): action for action in legal_actions(server.state, server.config)}
    candidates = _hire_candidates(server, "ordination")
    assert candidates, "fixture offered no ordination candidates with a hire step"
    assert {"none", "mill:market"} <= {_answer(candidate, "hire") for candidate in candidates}
    assert all(
        _step_index(candidate, "hire") < _step_index(candidate, "ordination")
        for candidate in candidates
    )

    no_hire_steps = {
        len(legal[candidate["action_id"]].ordination_steps)
        for candidate in candidates
        if _answer(candidate, "hire") == "none"
    }
    hired_steps = {
        len(legal[candidate["action_id"]].ordination_steps)
        for candidate in candidates
        if _answer(candidate, "hire") != "none"
    }
    assert no_hire_steps and hired_steps
    assert 3 in hired_steps
    assert 3 not in no_hire_steps


@pytest.mark.parametrize(
    ("scenario_name", "bank_value", "expected_hire_prompt", "expected_hire_text"),
    (
        (
            "bank_hire_market_ordination_001.json",
            "bank:market",
            "player_one: Hire the Bank from the market for 1 silver? "
            "It lets you pay in coins instead of wheat.",
            "This action uses the Bank — 1 silver to hire it from the market, and "
            "1 silver in place of 1 wheat.",
        ),
        (
            "bank_hire_opponent_ordination_001.json",
            "bank:player_two",
            "player_one: Hire the Bank from Yellow for 1 silver? "
            "It lets you pay in coins instead of wheat.",
            "This action uses the Bank — 1 silver to hire it from Yellow, and "
            "1 silver in place of 1 wheat.",
        ),
    ),
)
def test_paid_bank_hire_asks_before_its_board_payment(
    scenario_name: str,
    bank_value: str,
    expected_hire_prompt: str,
    expected_hire_text: str,
) -> None:
    scenario = load_scenario(SCENARIOS / scenario_name)
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    hire_steps = [
        step
        for candidate in candidates
        for step in candidate["steps"]
        if step.get("ends_ordination") is True
    ]
    payment_steps = [
        step
        for candidate in candidates
        for step in candidate["steps"]
        if step.get("resource_allocation") is True
    ]

    assert {(step["value"], step["label"], step["prompt"]) for step in hire_steps} == {
        ("none", "Pay without it", expected_hire_prompt),
        (bank_value, "Hire the Bank for 1 silver", expected_hire_prompt),
    }
    assert {step.get("ordination_next_move_consequence") for step in hire_steps} == {
        "Another move can only be paid by hiring the Bank."
    }
    assert all(step.get("hire_text") is None for step in hire_steps)
    assert {(step["value"], step["resource_total"], step["label"]) for step in payment_steps} == {
        ("wheat=1", 1, "Pay 1 wheat."),
        ("silver=2", 2, "Pay 2 silver."),
        ("silver=2,wheat=1", 3, "Pay 2 silver and 1 wheat."),
    }
    assert {step.get("hire_text") for step in payment_steps} == {None, expected_hire_text}
    assert all(
        step["resource_allocation_no_undo"] is True
        and step["requires_explicit_answer"] is True
        for step in payment_steps
    )
    assert all(candidate["action_id"] is not None for candidate in candidates)


def test_paid_bank_ordination_warning_stays_off_when_another_move_needs_no_hire() -> None:
    """Extra stock and a serf leave a non-hiring second Ordination move in the frontier."""
    scenario = load_scenario(SCENARIOS / "bank_hire_market_ordination_001.json")

    def hire_steps_after_one_ordination_move(state) -> list[dict]:
        return [
            step
            for candidate in play_server.turn_candidates(
                state, scenario.config, include_preview_effects=False
            )
            if any(
                step["kind"] == "ordination" and step["value"] == "ordain=1"
                for step in candidate["steps"]
            )
            for step in candidate["steps"]
            if step.get("ends_ordination") is True
        ]

    unmutated_steps = hire_steps_after_one_ordination_move(scenario.state)
    assert {step["value"] for step in unmutated_steps} == {"none", "bank:market"}
    assert {step.get("ordination_next_move_consequence") for step in unmutated_steps} == {
        "Another move can only be paid by hiring the Bank."
    }

    player_id = scenario.state.active_player
    player = scenario.state.player_state(player_id)
    state = scenario.state.with_player_state(
        player_id,
        replace(
            player,
            resources=replace(player.resources, wheat=3, silver=2),
            workforce=replace(player.workforce, village=3),
        ),
    )
    mutated_steps = hire_steps_after_one_ordination_move(state)
    assert {step["value"] for step in mutated_steps} == {"none", "bank:market"}
    assert {step.get("ordination_next_move_consequence") for step in mutated_steps} == {None}


def test_cornucopia_bank_hire_asks_which_stock_pays_before_its_board_payment() -> None:
    """The Bank's wild hire stock stays an engine choice before the combined payment opens."""
    scenario = load_scenario(SCENARIOS / "bank_hire_market_ordination_001.json")
    state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)
    config = _with_counter_under_the_merchant(scenario, "cornucopia")
    legal = {action_id(action): action for action in legal_actions(state, config)}
    candidates = play_server.turn_candidates(state, config)
    bank_candidates = [
        candidate
        for candidate in candidates
        if any(step["value"] == "bank:market" for step in candidate["steps"])
    ]

    bank_choices = {
        step["label"]
        for candidate in bank_candidates
        for step in candidate["steps"]
        if step["value"] == "bank:market"
    }
    asked_stocks = {
        next(step["value"] for step in candidate["steps"] if step["kind"] == "resource")
        for candidate in bank_candidates
    }
    assert bank_choices == {"Hire the Bank for 1 resource of your choice"}
    assert asked_stocks == {"stone", "silver", "wheat"}
    assert all(
        next(step for step in candidate["steps"] if step["kind"] == "resource")[
            "ends_ordination"
        ]
        is True
        for candidate in bank_candidates
    )
    assert all(
        dict(legal[candidate["action_id"]].hire_payments)["bank"]
        == next(step["value"] for step in candidate["steps"] if step["kind"] == "resource")
        for candidate in bank_candidates
    )


def test_taxation_merchant_without_a_resource_does_not_offer_the_bank() -> None:
    """Taxation leaves the Bank at its engine-recorded Merchant-resource-none source state."""
    scenario = load_scenario(SCENARIOS / "alms_season_end_fourth_season_game_end_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=scenario.state.active_player,
        building_key="bank",
    )
    actions = legal_actions(scenario.state, scenario.config)

    assert source.reason is BuildingAbilityReason.MERCHANT_RESOURCE_NONE
    assert not source.usable
    assert not any(
        isinstance(action, FullTurnAction) and action.bank_payment_building_id == "bank"
        for action in actions
    )
    assert not any(
        step.get("ends_ordination") is True
        for candidate in play_server.turn_candidates(
            scenario.state,
            scenario.config,
            actions=actions,
        )
        for step in candidate["steps"]
    )


def test_owned_bank_payment_mix_resolves_the_bank_fields_after_ordination() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_ordination_substitution_001.json")
    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        include_preview_effects=False,
    )
    ordain_one = [
        candidate
        for candidate in candidates
        if any(
            step["kind"] == "ordination" and step["value"] == "ordain=1"
            for step in candidate["steps"]
        )
    ]
    payment_steps = [
        next(
            step
            for step in candidate["steps"]
            if step.get("prompt")
            == "player_one: The Bank lets you pay in coins instead of wheat. Choose how to pay."
        )
        for candidate in ordain_one
    ]

    assert len(ordain_one) == 2
    assert all(candidate["variants"] == 1 for candidate in ordain_one)
    assert all(candidate["action_id"] is not None for candidate in ordain_one)
    assert all(candidate["unresolved"] == [] for candidate in ordain_one)
    assert {step["value"] for step in payment_steps} == {"wheat=1", "silver=1"}
    assert all(
        candidate["steps"].index(payment_step)
        > next(
            index
            for index, step in enumerate(candidate["steps"])
            if step["kind"] == "resolution"
        )
        for candidate, payment_step in zip(ordain_one, payment_steps, strict=True)
    )
    assert all(
        step["resource_allocation"] is True
        and step["resource_total"] == 1
        and step["resource_allocation_no_undo"] is True
        and step["resource_unit_deltas"]["silver"] == {
            "stone": 0,
            "silver": -1,
            "wheat": 0,
        }
        and step["requires_explicit_answer"] is True
        and not {"auto", "default", "preselected"}.intersection(step)
        for step in payment_steps
    )


def test_owned_bank_with_only_silver_still_asks_for_its_single_payment_mix() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_ordination_full_substitution_001.json")
    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        include_preview_effects=False,
    )
    ordain_two = [
        candidate
        for candidate in candidates
        if any(
            step["kind"] == "ordination" and step["value"] == "ordain=2"
            for step in candidate["steps"]
        )
    ]
    payment_steps = [
        step
        for candidate in ordain_two
        for step in candidate["steps"]
        if step.get("prompt")
        == "player_one: The Bank lets you pay in coins instead of wheat. Choose how to pay."
    ]

    assert len(payment_steps) == 1
    assert payment_steps[0]["value"] == "silver=2"
    assert payment_steps[0]["resource_allocation"] is True
    assert payment_steps[0]["resource_total"] == 2
    assert payment_steps[0]["resource_allocation_no_undo"] is True
    assert not {"auto", "default", "preselected"}.intersection(payment_steps[0])


def test_owned_bank_stays_in_effect_during_the_sow_payment_window() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_ordination_substitution_001.json")
    windows = play_server.building_ability_windows_payload(scenario.state, scenario.config)

    assert {
        window: tuple(
            next(
                ability
                for ability in payload["abilities"]
                if ability["building_id"] == "bank"
            )[field]
            for field in ("usable", "reason", "greyed", "status_text")
        )
        for window, payload in windows.items()
    } == {
        "beginning": (True, None, False, "Usable: no payment."),
        "sow": (True, None, False, "Usable: no payment."),
        "end": (True, None, False, "Usable: no payment."),
    }


def test_owned_bank_ordination_summaries_name_each_resource_paid() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_ordination_substitution_001.json")
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    summaries_by_ordination = {
        ordination: {
            candidate["summary"]
            for candidate in candidates
            if any(
                step["kind"] == "ordination" and step["value"] == ordination
                for step in candidate["steps"]
            )
        }
        for ordination in {
            step["value"]
            for candidate in candidates
            for step in candidate["steps"]
            if step["kind"] == "ordination"
        }
    }

    full_substitution = load_scenario(
        SCENARIOS / "bank_active_ordination_full_substitution_001.json"
    )
    full_candidates = play_server.turn_candidates(full_substitution.state, full_substitution.config)
    full_summary = next(
        candidate["summary"]
        for candidate in full_candidates
        if any(
            step["kind"] == "ordination" and step["value"] == "ordain=2"
            for step in candidate["steps"]
        )
    )
    no_bank = load_scenario(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    ordinary_two_ordination = next(
        action
        for action in legal_actions(no_bank.state, no_bank.config)
        if isinstance(action, FullTurnAction)
        and action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
        and action.bank_payment_building_id is None
    )
    assert {
        "partial_substitution": summaries_by_ordination,
        "full_substitution": full_summary,
        "no_bank": action_summary_for_players(
            ordinary_two_ordination,
            no_bank.config,
            actor=no_bank.state.active_player,
            state=no_bank.state,
        ),
    } == {
        "partial_substitution": {
            "ordain=1": {
                "player_one chose Ordination at Ordination — ordained 1 serf into the Abbey; "
                "paid 1 wheat.",
                "player_one chose Ordination at Ordination — ordained 1 serf into the Abbey; "
                "paid 1 silver via the Bank.",
            },
            "ordain=2": {
                "player_one chose Ordination at Ordination — ordained 2 serfs into the Abbey; "
                "paid 1 wheat and 1 silver via the Bank."
            },
            "ordain=1,mission=1": {
                "player_one chose Ordination at Ordination — ordained 1 serf into the Abbey; "
                "sent 1 acolyte on mission to the City; paid 1 wheat and 1 silver via the Bank."
            },
        },
        "full_substitution": (
            "player_one chose Ordination at Ordination — ordained 2 serfs into the Abbey; "
            "paid 2 silver via the Bank."
        ),
        "no_bank": (
            "player_one chose Ordination at Ordination — ordained 2 serfs into the Abbey; "
            "paid 2 wheat."
        ),
    }


def test_owned_bank_construct_payment_names_retained_stone_and_context_resource() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_construct_minority_substitution_001.json")
    player = scenario.state.player_state(scenario.state.active_player)
    state = scenario.state.with_player_state(
        scenario.state.active_player,
        replace(player, resources=replace(player.resources, stone=2, silver=2)),
    )
    candidates = play_server.turn_candidates(state, scenario.config, include_preview_effects=False)
    payment_steps = [
        step
        for candidate in candidates
        if any(
            step["kind"] == "building" and step["value"] == "brewery"
            for step in candidate["steps"]
        )
        for step in candidate["steps"]
        if step["kind"] == "combination"
    ]

    assert {step["prompt"] for step in payment_steps} == {
        "player_one: The Bank lets you pay in coins instead of stone. Choose how to pay."
    }
    assert {(step["value"], step["label"]) for step in payment_steps} == {
        ("stone=2", "Pay 2 stone."),
        ("stone=1,silver=1", "Pay 1 stone and 1 silver."),
    }


def test_owned_bank_construct_payment_allocates_the_engine_payment_mix() -> None:
    scenario = load_scenario(SCENARIOS / "bank_active_construct_minority_substitution_001.json")

    def payments_for(candidates: list[dict], building_ids: set[str]) -> set[tuple[str, str, int]]:
        return {
            (
                next(
                    step["value"]
                    for step in candidate["steps"]
                    if step["kind"] == "building"
                ),
                step["value"],
                step["resource_total"],
            )
            for candidate in candidates
            if any(
                step["kind"] == "building" and step["value"] in building_ids
                for step in candidate["steps"]
            )
            for step in candidate["steps"]
            if step["kind"] == "combination"
        }

    base_candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        include_preview_effects=False,
    )
    player = scenario.state.player_state(scenario.state.active_player)
    substituted_state = scenario.state.with_player_state(
        scenario.state.active_player,
        replace(player, resources=replace(player.resources, stone=2, silver=2)),
    )
    substituted_candidates = play_server.turn_candidates(
        substituted_state,
        scenario.config,
        include_preview_effects=False,
    )
    construct_candidates = [
        candidate
        for candidate in base_candidates
        if any(step["kind"] == "resolution" and step["value"] == "construct_building"
               for step in candidate["steps"])
    ]
    construct_bank_actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.bank_payment_building_id == "bank"
    ]
    allocation_steps = [
        step
        for candidate in construct_candidates
        for step in candidate["steps"]
        if step["kind"] == "combination"
    ]
    observed = {
        "base": payments_for(base_candidates, {"well", "chapel", "mint", "quarry"}),
        "partial_substitution": payments_for(
            substituted_candidates,
            {"brewery", "chapel", "customs_house"},
        ),
        "allocation_metadata": {
            (
                step["resource_allocation"],
                step["resource_allocation_no_undo"],
                step["requires_explicit_answer"],
                tuple(
                    (resource, tuple(sorted(delta.items())))
                    for resource, delta in sorted(step["resource_unit_deltas"].items())
                ),
            )
            for step in allocation_steps
        },
        "ordination_only": [
            (step["kind"], key)
            for candidate in construct_candidates
            for step in candidate["steps"]
            for key in step
            if step["kind"] == "ordination"
            or key in {"ends_ordination", "ordination_next_move_consequence"}
        ],
        "construct_bank_sources": [
            action.bank_payment_building_source for action in construct_bank_actions
        ],
    }

    assert observed == {
        "base": {
            ("well", "silver=1", 1),
            ("chapel", "silver=1", 1),
            ("mint", "silver=1", 1),
            ("quarry", "silver=1", 1),
        },
        "partial_substitution": {
            ("brewery", "stone=2", 2),
            ("brewery", "stone=1,silver=1", 2),
            ("chapel", "silver=1", 1),
            ("chapel", "stone=1", 1),
            ("customs_house", "stone=2,silver=1", 3),
        },
        "allocation_metadata": {
            (
                True,
                True,
                True,
                (
                    ("silver", (("silver", -1), ("stone", 0), ("wheat", 0))),
                    ("stone", (("silver", 0), ("stone", -1), ("wheat", 0))),
                    ("wheat", (("silver", 0), ("stone", 0), ("wheat", -1))),
                ),
            )
        },
        "ordination_only": [],
        "construct_bank_sources": ["own_active", "own_active", "own_active", "own_active"],
    }


def test_hired_bank_construct_asks_after_building_and_allocates_every_applied_cost() -> None:
    scenario = load_scenario(SCENARIOS / "bank_hire_market_construct_substitution_001.json")
    actions = {
        action_id(action): action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    }
    before = scenario.state.player_state(scenario.state.active_player).resources
    ordination_only_fields = {"ends_ordination", "ordination_next_move_consequence"}
    observed: dict[str, set[tuple[str | None, str, int, str, str | None]]] = {}
    for candidate in play_server.turn_candidates(
        scenario.state,
        scenario.config,
    ):
        action = actions[candidate["action_id"]]
        payments = [step for step in candidate["steps"] if step.get("resource_allocation")]
        if action.resolution is not TurnResolutionType.CONSTRUCT_BUILDING or not payments:
            continue
        assert len(payments) == 1
        result = apply_action(scenario.state, action, scenario.config)
        after = result.state.player_state(scenario.state.active_player).resources
        spent = {
            resource: max(0, getattr(before, resource) - getattr(after, resource))
            for resource in ("stone", "silver", "wheat")
        }
        question = next(
            (
                step
                for step in candidate["steps"]
                if step["kind"] == "combination" and not step.get("resource_allocation")
            ),
            None,
        )
        payment = payments[0]
        fee_step = next(step for step in candidate["steps"] if step.get("minority_fee"))
        question_value = question["value"] if question is not None else None
        observed.setdefault(action.construct_building_id, set()).add(
            (
                question_value,
                payment["value"],
                payment["resource_total"],
                payment["label"],
                payment.get("hire_text"),
            )
        )
        assert spent == {
            resource: int(payment["value"].split(f"{resource}=", 1)[1].split(",", 1)[0])
            if f"{resource}=" in payment["value"]
            else 0
            for resource in ("stone", "silver", "wheat")
        } | {"silver": fee_step["minority_fee"] + (
            int(payment["value"].split("silver=", 1)[1].split(",", 1)[0])
            if "silver=" in payment["value"]
            else 0
        )}
        assert not ordination_only_fields.intersection(payment)
        if question is not None:
            assert not ordination_only_fields.intersection(question)

    hire_fact = (
        "This action uses the Bank — 1 silver to hire it from the market, and "
        "1 silver in place of 1 stone."
    )
    assert observed == {
        building: {
            ("none", "stone=1", 1, "Pay 1 stone.", None),
            ("bank:market", "silver=2", 2, "Pay 2 silver.", hire_fact),
        }
        for building in ("well", "chapel", "mint", "quarry")
    } | {
        building: {
            ("none", "stone=2", 2, "Pay 2 stone.", None),
            ("bank:market", "stone=1,silver=2", 3, "Pay 1 stone and 2 silver.", hire_fact),
        }
        for building in ("brewery", "cloisters", "dormitory", "grain_store")
    } | {
        building: {
            (None, "stone=2,silver=2", 4, "Pay 2 stone and 2 silver.", hire_fact),
        }
        for building in ("wagon_yard", "customs_house", "inquisition", "bank")
    }


def test_minority_fee_precedes_construct_payment_and_leaves_every_engine_cost_accounted_for(
) -> None:
    scenario = load_scenario(SCENARIOS / "bank_hire_market_construct_substitution_001.json")
    actions = {
        action_id(action): action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    }
    before = scenario.state.player_state(scenario.state.active_player).resources
    observed: dict[str, set[tuple[int, int, int]]] = {}
    for candidate in play_server.turn_candidates(
        scenario.state,
        scenario.config,
    ):
        action = actions[candidate["action_id"]]
        if action.resolution is not TurnResolutionType.CONSTRUCT_BUILDING:
            continue
        resolution_index = next(
            index
            for index, step in enumerate(candidate["steps"])
            if step["kind"] == "resolution"
        )
        fee_step = candidate["steps"][resolution_index + 1]
        assert fee_step["minority_fee"] == 1
        assert fee_step["value"] == "silver"
        assert fee_step["prompt"] == (
            "player_one: You are in the minority here. Pay 1 silver to take this Duty Action."
        )
        payment = next(
            (step for step in candidate["steps"] if step.get("resource_allocation")),
            None,
        )
        if payment is not None:
            stated = {
                resource: int(payment["value"].split(f"{resource}=", 1)[1].split(",", 1)[0])
                if f"{resource}=" in payment["value"]
                else 0
                for resource in ("stone", "silver", "wheat")
            }
            stated_total = payment["resource_total"]
        else:
            # A route-hired Construct has no separate allocation control. Its building step is
            # still server-described with the residual action cost after the fee.
            action_cost_steps = [
                step
                for step in candidate["steps"][resolution_index + 2 :]
                if "resource_delta" in step
            ]
            assert len(action_cost_steps) == 1
            stated = {
                resource: max(0, -int(action_cost_steps[0]["resource_delta"][resource]))
                for resource in ("stone", "silver", "wheat")
            }
            stated_total = sum(stated.values())
        result = apply_action(scenario.state, action, scenario.config)
        after = result.state.player_state(scenario.state.active_player).resources
        spent = {
            resource: max(0, getattr(before, resource) - getattr(after, resource))
            for resource in ("stone", "silver", "wheat")
        }
        assert spent == {
            **stated,
            "silver": stated["silver"] + fee_step["minority_fee"],
        }
        observed.setdefault(action.construct_building_id, set()).add(
            (fee_step["minority_fee"], stated_total, sum(spent.values()))
        )

    assert observed == {
        building: {(1, 1, 2), (1, 2, 3)}
        for building in ("well", "chapel", "mint", "quarry")
    } | {
        building: {(1, 2, 3), (1, 3, 4)}
        for building in ("brewery", "cloisters", "dormitory", "grain_store")
    } | {
        building: {(1, 4, 5)}
        for building in ("wagon_yard", "customs_house", "inquisition", "bank")
    }


def test_minority_taxation_preview_delta_is_not_attached_to_take_nothing_twice() -> None:
    scenario = load_scenario(SCENARIOS / "taxation_minor_cost_001.json")
    actions = {
        action_id(action): action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    }
    before = scenario.state.player_state(scenario.state.active_player).resources
    minority_taxation = [
        (candidate, actions[candidate["action_id"]])
        for candidate in play_server.turn_candidates(scenario.state, scenario.config)
        if actions[candidate["action_id"]].resolution is TurnResolutionType.TAXATION
        and any(step.get("minority_fee") for step in candidate["steps"])
    ]

    assert len(minority_taxation) == 3
    for candidate, action in minority_taxation:
        steps = candidate["steps"]
        take_nothing = next(
            step
            for step in steps
            if step["kind"] == "combination" and step["label"] == "take nothing"
        )
        assert take_nothing.get("resource_delta") == {"stone": 0, "silver": 0, "wheat": 0}

        result = apply_action(scenario.state, action, scenario.config)
        after = result.state.player_state(scenario.state.active_player).resources
        actual_delta = {
            resource: getattr(after, resource) - getattr(before, resource)
            for resource in ("stone", "silver", "wheat")
        }
        preview_delta = {
            resource: sum(
                int(step.get("resource_delta", {}).get(resource, 0)) for step in steps
            )
            for resource in ("stone", "silver", "wheat")
        }
        assert preview_delta == actual_delta


def test_minority_fee_is_a_category_blind_non_tithe_step_in_the_corpus(corpus_actions) -> None:
    fee_scenarios: set[str] = set()
    fees = 0
    ordination_candidates = 0
    for scenario_path, scenario, actions in corpus_actions:
        candidates = play_server.turn_candidates(
            scenario.state,
            scenario.config,
            actions=actions,
            include_preview_effects=False,
        )
        player_id = scenario.state.active_player.name.lower()
        for candidate in candidates:
            steps = candidate["steps"]
            resolution_index = next(
                (index for index, step in enumerate(steps) if step["kind"] == "resolution"),
                None,
            )
            if resolution_index is None:
                continue
            fee_step = steps[resolution_index + 1] if resolution_index + 1 < len(steps) else None
            if fee_step is not None and fee_step.get("minority_fee"):
                assert steps[resolution_index]["value"] != "tithe"
                assert fee_step["value"] == "silver"
                assert fee_step["prompt"] == (
                    f"{player_id}: You are in the minority here. Pay 1 silver to take this "
                    "Duty Action."
                )
                fees += 1
                fee_scenarios.add(scenario_path.name)
            if steps[resolution_index]["value"] == "ordination":
                ordination_candidates += 1
                assert fee_step is None or "minority_fee" not in fee_step

    assert fees >= 39, "the corpus no longer exercises a population of minority fee steps"
    assert len(fee_scenarios) >= 6, "the corpus no longer exercises several duty categories"
    assert ordination_candidates > 0, "the corpus no longer contains Ordination candidates"


def test_bank_payment_labels_keep_one_as_an_explicit_price_amount() -> None:
    assert [
        play_server._bank_payment_label(amounts)
        for amounts in (
            [("wheat", 2), ("silver", 0)],
            [("wheat", 1), ("silver", 1)],
            [("wheat", 0), ("silver", 2)],
        )
    ] == ["Pay 2 wheat.", "Pay 1 wheat and 1 silver.", "Pay 2 silver."]


@pytest.mark.parametrize(
    ("scenario_name", "expected"),
    (
        (
            "bank_hire_market_ordination_001.json",
            (True, None, False, "Usable: choose it when an action asks how to pay."),
        ),
        (
            "kogge_donated_no_extra_routes_001.json",
            (False, None, True, "Cannot be used: no action this turn can use the Bank."),
        ),
    ),
)
def test_paid_bank_tile_follows_whether_an_action_offers_its_payment(
    scenario_name: str,
    expected: tuple[bool, None, bool, str],
) -> None:
    scenario = load_scenario(SCENARIOS / scenario_name)
    actions = list(legal_actions(scenario.state, scenario.config))
    tile = next(
        ability
        for ability in play_server.building_abilities_payload(
            scenario.state,
            scenario.config,
            actions=actions,
        )
        if ability["building_id"] == "bank"
    )

    assert tuple(tile[field] for field in ("usable", "reason", "greyed", "status_text")) == expected
    assert play_server._paid_bank_payment_on_offer(actions) is expected[0]


def test_paid_bank_hire_fact_is_absent_when_only_the_dominated_option_is_pruned() -> None:
    scenario = load_scenario(SCENARIOS / "kogge_donated_no_extra_routes_001.json")

    candidates = play_server.turn_candidates(scenario.state, scenario.config)

    assert candidates
    assert not {
        step["hire_text"]
        for candidate in candidates
        for step in candidate["steps"]
        if step.get("hire_text", "").startswith("This action uses the Bank")
    }


def test_wagon_yard_free_bank_hire_keeps_its_committed_step_wording() -> None:
    scenario = load_scenario(
        SCENARIOS / "wagon_yard_active_free_hire_market_bank_ordination_001.json"
    )
    tile = next(
        ability
        for ability in play_server.building_abilities_payload(scenario.state, scenario.config)
        if ability["building_id"] == "bank"
    )
    free_step = next(
        step
        for step in play_server.turn_steps_payload(scenario.state, scenario.config)
        if step["building_id"] == "bank"
    )

    assert tuple(tile[field] for field in ("usable", "reason", "greyed", "status_text")) == (
        False,
        BuildingAbilityReason.MERCHANT_RESOURCE_NONE,
        True,
        "Cannot be hired: the Merchant names no hire resource.",
    )
    assert (free_step["hire_payment"], free_step["ability"]["status_text"]) == (
        None,
        "Usable: no payment.",
    )


def _bank_player_texts_at_state(
    state: Any,
    config: Any,
    *,
    actions: list[Any],
) -> tuple[set[str], bool]:
    """Collect every Bank-specific sentence the page can show in one exact state."""
    bank_texts: set[str] = set()
    ability_payloads = [
        play_server.building_abilities_payload(state, config, actions=actions),
        *(
            window["abilities"]
            for window in play_server.building_ability_windows_payload(
                state,
                config,
                actions=actions,
            ).values()
        ),
    ]
    bank_texts.update(
        str(ability["status_text"])
        for abilities in ability_payloads
        for ability in abilities
        if ability["building_id"] == "bank" and ability["status_text"]
    )
    bank_texts.update(
        str(value)
        for step in play_server.turn_steps_payload(state, config)
        if step["building_id"] == "bank"
        for value in (
            step["prompt"],
            step["hire_text"],
            step["ability"]["status_text"],
            *(answer["label"] for answer in step["answers"]),
        )
        if value
    )
    for candidate in play_server.turn_candidates(state, config, actions=actions):
        if not any(
            step.get("hire_text", "").startswith("This action uses the Bank")
            for step in candidate["steps"]
        ):
            continue
        bank_texts.update(
            str(value)
            for step in candidate["steps"]
            for value in (step.get("prompt"), step.get("label"), step.get("hire_text"))
            if value
        )
        if candidate["summary"]:
            bank_texts.add(str(candidate["summary"]))
    return (
        bank_texts,
        any(
            ability["building_id"] == "bank"
            and ability["reason"] == BuildingAbilityReason.INSUFFICIENT_RESOURCE
            for abilities in ability_payloads
            for ability in abilities
        ),
    )


def test_bank_player_text_never_names_the_supply_as_its_payee() -> None:
    """Walk every Bank-specific play surface, including every one-transition-derived tile state."""
    bank_texts: set[str] = set()
    saw_insufficient_bank_tile = False
    checked_scenarios = 0
    paths = [*sorted(SCENARIOS.glob("*.json")), *sorted(PLAYTEST_SCENARIOS.glob("*.json"))]
    for scenario_path in paths:
        scenario = load_scenario(scenario_path)
        actions = list(legal_actions(scenario.state, scenario.config))
        state_texts, insufficient_bank_tile = _bank_player_texts_at_state(
            scenario.state,
            scenario.config,
            actions=actions,
        )
        bank_texts.update(state_texts)
        saw_insufficient_bank_tile |= insufficient_bank_tile
        for action in actions:
            result = apply_action(scenario.state, action, scenario.config)
            state_texts, insufficient_bank_tile = _bank_player_texts_at_state(
                result.state,
                scenario.config,
                actions=list(legal_actions(result.state, scenario.config)),
            )
            bank_texts.update(state_texts)
            saw_insufficient_bank_tile |= insufficient_bank_tile
            bank_texts.update(
                text
                for event in result.events
                if dict(event.details).get("building_id") == "bank"
                or dict(event.details).get("building") == "bank"
                if (text := format_event_for_players(event, scenario.config)) is not None
            )
        for step in turn_steps(scenario.state, scenario.config):
            after_step = apply_turn_step(scenario.state, scenario.config, step)
            state_texts, insufficient_bank_tile = _bank_player_texts_at_state(
                after_step,
                scenario.config,
                actions=list(legal_actions(after_step, scenario.config)),
            )
            bank_texts.update(state_texts)
            saw_insufficient_bank_tile |= insufficient_bank_tile
            bank_texts.update(
                text
                for event in after_step.events
                if event.action_id == play_server.turn_step_id(step)
                and (
                    dict(event.details).get("building_id") == "bank"
                    or dict(event.details).get("building") == "bank"
                )
                if (text := format_event_for_players(event, scenario.config)) is not None
            )
        checked_scenarios += 1

    assert checked_scenarios >= 320, f"only {checked_scenarios} scenarios checked"
    assert saw_insufficient_bank_tile
    assert bank_texts
    assert not {
        text for text in bank_texts if re.search(r"\bto (?:the )?bank\b", text.lower())
    }


@needs_node
def test_a_cloisters_turn_is_playable_end_to_end_with_skip_then_duty(tmp_path: Path) -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "kogge_cloisters_own_own_skip_duty_001.json")
    candidate = _first_settled_skip_candidate(server)
    assert candidate is not None, "fixture offered no settled Cloisters candidate with a skip step"
    assert _step_index(candidate, "skip") < _step_index(candidate, "duty")

    transcript = _played_from_the_page(server, candidate, tmp_path)
    assert transcript["posted"] is not None, "Cloisters turn did not submit"
    assert transcript["posted"]["action_id"] == candidate["action_id"]


def test_starting_a_test_position_offers_clickable_cloisters_skip_candidates() -> None:
    server = PlayServer(("127.0.0.1", 0))
    with _running(server) as base:
        status, _page = _post_form(
            base,
            "/start",
            _start_fields(player_count=4, seed=1234, test_position=PLAYTEST_CLOISTERS),
        )
        assert status == 200

        drawn = set(_arrows_drawn(render_play_view_from_payload(server.payload)))
        skip_candidates = [
            candidate
            for candidate in server.payload["turn_candidates"]
            if any(step["kind"] == "skip" for step in candidate["steps"])
        ]
        assert skip_candidates, "selected test position offered no Cloisters skip candidates"
        dead = [
            candidate
            for candidate in skip_candidates
            if {str(step["value"]) for step in candidate["steps"] if step["kind"] == "edge"} - drawn
        ]
        assert not dead, (
            "selected test position still offered Cloisters candidates with undrawn edges"
        )


@needs_node
def test_a_cornucopia_tithe_is_playable_and_only_the_stock_that_was_picked_moves(
    tmp_path: Path,
) -> None:
    """The payoff for the stock keys: the seat picks, and what it picked is what it gets.

    A Cornucopia is the one counter that does not say what it pays, so all three stocks are on
    offer. The two that were not picked are checked FIRST, because a page that moved the right
    stock and something else besides would still pass a check that only looked at the right one.
    """
    server = _reference_server()
    asked = _asked(server, "tithe", "resource")
    assert asked, "no tithe on this board asked which stock, so nothing was exercised"

    candidate = asked[0]
    offered = _siblings(asked, candidate, "resource")
    assert len(offered) > 1, "a stock was 'chosen' from a single option"
    picked = _answer(candidate, "resource")
    seat = server.payload["state"]["active_player"]
    before = _stocks(server, seat)

    _played_from_the_page(server, candidate, tmp_path)
    after = _stocks(server, seat)

    untouched = [stock for stock in before if stock != picked]
    assert [after[stock] for stock in untouched] == [before[stock] for stock in untouched]
    assert after[picked] == before[picked] + 1


@needs_node
def test_a_cornucopia_tithe_writes_one_player_line_without_sow_path_noise(tmp_path: Path) -> None:
    server = _reference_server()
    candidate = _asked(server, "tithe", "resource")[0]
    picked = _answer(candidate, "resource")
    duty_index = _answer(candidate, "duty")
    duty_position = server.payload["board_positions"][duty_index]
    duty_tile = next(
        tile for tile in server.payload["duty_tiles"] if tile["position_name"] == duty_position
    )
    duty_label = duty_tile["duty"].replace("_", " ")
    actor = server.payload["state"]["active_player"]

    _played_from_the_page(server, candidate, tmp_path)

    block = server.payload["log_blocks"][-1]
    assert block["round_end"] is False
    assert len(block["lines"]) == 1
    line = block["lines"][0].lower()
    assert actor in line
    assert duty_label in line
    assert f"gained {picked}" in line
    assert "invariant_check" not in line
    assert "route " not in line


def test_a_cornucopia_hire_asks_which_stock_pays_and_honours_the_one_chosen() -> None:
    scenario = load_scenario(str(SCENARIOS / "building_hire_opponent_owned_001.json"))
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "building_hire_opponent_owned_001.json")
    try:
        server.state = _with_stock(scenario.state, stone=5, silver=5, wheat=5)
        server.config = _with_counter_under_the_merchant(scenario, "cornucopia")
        server._refresh()

        asked = [
            candidate
            for candidate in server.payload["turn_candidates"]
            if candidate.get("action_id") is not None
            and any(step["kind"] == "hire" for step in candidate["steps"])
            and any(step["kind"] == "resource" for step in candidate["steps"])
        ]
        assert asked, "fixture offered no settled hire candidate asking for payment stock"

        group = next(
            (
                siblings
                for candidate in asked
                if len((siblings := _siblings(asked, candidate, "resource"))) > 1
            ),
            None,
        )
        assert group is not None, "cornucopia hire offered no payment-stock choice"
        offered = sorted({_answer(candidate, "resource") for candidate in group})
        assert len(offered) > 1, "cornucopia hire offered only one payment stock"

        by_resource = {
            resource: next(
                candidate for candidate in group if _answer(candidate, "resource") == resource
            )
            for resource in offered
        }
        for resource, candidate in by_resource.items():
            action = _action_for_candidate(server, candidate)
            payment = dict(action.hire_payments).get(action.hired_building_id)
            assert payment == resource

        first_resource, second_resource = offered[0], offered[1]
        first_action = _action_for_candidate(server, by_resource[first_resource])
        second_action = _action_for_candidate(server, by_resource[second_resource])
        first_after = (
            apply_action(server.state, first_action, server.config)
            .state.player_state(server.state.active_player)
            .resources
        )
        second_after = (
            apply_action(server.state, second_action, server.config)
            .state.player_state(server.state.active_player)
            .resources
        )
        assert getattr(first_after, first_resource) < getattr(second_after, first_resource), (
            f"picking {first_resource} did not spend more {first_resource} than an alternative payment"
        )
    finally:
        server.server_close()


def test_round_closing_actions_are_marked_as_round_end_log_blocks(tmp_path: Path) -> None:
    server = _played_through_setup(_served(tmp_path))
    opening_round = server.payload["state"]["timing"]["round_number"]

    for _ in range(20):
        if server.payload["state"]["timing"]["round_number"] > opening_round:
            break
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)

    assert server.payload["state"]["timing"]["round_number"] > opening_round
    assert any(block["round_end"] for block in server.payload["log_blocks"])
    page = render_play_view_from_payload(server.payload)
    assert 'data-round-end="true"' in page
    assert ">Round end<" in page


def _phase_row_keys(server: PlayServer) -> list[str]:
    return [row["key"] for row in server.payload["phase_column"]["rows"]]


def _current_phase_row_keys(server: PlayServer) -> list[str]:
    return [row["key"] for row in server.payload["phase_column"]["rows"] if row["current"]]


def test_turn_window_prompt_names_only_available_building_kinds() -> None:
    assert play_server._turn_window_prompt(
        resolution_committed=False, available_turn_steps=[]
    ) == "Pick up acolytes for sowing."
    assert play_server._turn_window_prompt(
        resolution_committed=False,
        available_turn_steps=[{"hire_payment": "silver"}, {"hire_payment": None}],
    ) == "Pick up acolytes for sowing. Buildings can be used here — some free, some hired."
    assert play_server._turn_window_prompt(
        resolution_committed=True, available_turn_steps=[]
    ) == ""
    assert play_server._turn_window_prompt(
        resolution_committed=True,
        available_turn_steps=[{"hire_payment": "silver"}, {"hire_payment": None}],
    ) == "Buildings can be used here — some free, some hired."
    assert play_server._turn_window_prompt(
        resolution_committed=True,
        available_turn_steps=[{"hire_payment": "silver"}],
    ) == "A building can be hired here."
    assert play_server._turn_window_prompt(
        resolution_committed=True,
        available_turn_steps=[{"hire_payment": None}],
    ) == "A building can be used here, free."


def test_movement_turn_window_counts_each_available_hire() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    steps = play_server.turn_steps_payload(scenario.state, scenario.config)

    assert sum(step["hire_payment"] is not None for step in steps) == 9
    assert play_server.phase_column_payload(
        scenario.state,
        [],
        available_turn_steps=steps,
    )["prompts"] == {
        "beginning": "Pick up acolytes for sowing. Buildings can be used here — some free, some hired."
    }


def _remove_confession_box_from_market(server: PlayServer) -> None:
    server.state = replace(
        server.state,
        building_market=tuple(
            building_id
            for building_id in server.state.building_market
            if building_id != "confession_box"
        ),
        building_availability=tuple(
            entry for entry in server.state.building_availability if entry[0] != "confession_box"
        ),
    )
    server._refresh()


def _apply_first_settled_round_end(server: PlayServer) -> None:
    candidate = next(
        candidate for candidate in server.payload["turn_candidates"] if candidate["action_id"]
    )
    _apply_settled_turn_and_pass(server, candidate)


def test_ordinary_round_end_phase_rows_derive_income_and_marker_from_pass_events() -> None:
    server = PlayServer(
        ("127.0.0.1", 0),
        SCENARIOS / "round_end_trade_route_income_basic_001.json",
    )
    try:
        _remove_confession_box_from_market(server)
        _apply_first_settled_round_end(server)

        assert server.payload["phase_column"]["scope"] == "round_end"
        page = render_play_view_from_payload(server.payload)
        assert 'data-phase-column="round_end"' in page
        assert 'data-round-end-phase="choose_first_player" data-phase-current="true"' in page
        assert _phase_row_keys(server) == [
            "round_marker",
            "merchant",
            "trade_route_income",
            "choose_first_player",
        ]
        assert _current_phase_row_keys(server) == ["choose_first_player"]
        assert "season_end" not in _phase_row_keys(server)
    finally:
        server.server_close()


def test_capped_round_end_adds_excess_row_only_when_resources_were_returned() -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "round_end_excess_001.json")
    try:
        _remove_confession_box_from_market(server)
        _apply_first_settled_round_end(server)

        assert _phase_row_keys(server) == [
            "excess",
            "round_marker",
            "merchant",
            "choose_first_player",
        ]
        assert _current_phase_row_keys(server) == ["choose_first_player"]
    finally:
        server.server_close()


def test_pilgrimage_round_end_inserts_season_end_between_marker_and_merchant() -> None:
    server = PlayServer(
        ("127.0.0.1", 0),
        SCENARIOS / "round_end_non_final_pilgrimage_continues_001.json",
    )
    try:
        _remove_confession_box_from_market(server)
        _apply_first_settled_round_end(server)

        assert _phase_row_keys(server) == [
            "round_marker",
            "season_end",
            "merchant",
            "trade_route_income",
            "choose_first_player",
        ]
        assert _current_phase_row_keys(server) == ["choose_first_player"]
    finally:
        server.server_close()


def test_confession_phase_rows_survive_each_subquestion_before_first_player_choice() -> None:
    server = PlayServer(
        ("127.0.0.1", 0),
        SCENARIOS / "confession_box_multiple_players_player_order_001.json",
    )
    try:
        candidate = next(
            candidate
            for candidate in server.payload["turn_candidates"]
            if candidate["action_id"]
            and any(
                step["kind"] == "resolution" and step["value"] == "tithe"
                for step in candidate["steps"]
            )
        )
        _apply_settled_turn_and_pass(server, candidate)

        assert _phase_row_keys(server) == ["round_marker", "merchant", "confession"]
        assert _current_phase_row_keys(server) == ["confession"]
        assert "choose_first_player" not in _phase_row_keys(server)

        answer = next(
            candidate for candidate in server.payload["turn_candidates"] if candidate["action_id"]
        )
        server.apply(answer["action_id"], server.payload["state_token"])

        assert server.payload["log_blocks"][-1]["round_end"] is False
        assert _phase_row_keys(server) == ["round_marker", "merchant", "confession"]
        assert _current_phase_row_keys(server) == ["confession"]

        while server.payload["state"]["phase"] == "start_player_confession":
            answer = next(
                candidate
                for candidate in server.payload["turn_candidates"]
                if candidate["action_id"]
            )
            server.apply(answer["action_id"], server.payload["state_token"])

        assert _phase_row_keys(server) == [
            "round_marker",
            "merchant",
            "confession",
            "choose_first_player",
        ]
        assert _current_phase_row_keys(server) == ["choose_first_player"]
    finally:
        server.server_close()


def test_guild_merchant_event_does_not_duplicate_the_round_end_merchant_row() -> None:
    server = PlayServer(
        ("127.0.0.1", 0),
        SCENARIOS / "guild_round_end_moves_merchant_twice_001.json",
    )
    try:
        assert server.config.merchant.advance_at_round_end is True
        guild = next(
            step
            for step in server.payload["turn_steps"]
            if step["kind"] == "activation" and step["building_id"] == "guild"
        )
        server.apply_turn_step(guild["step_id"], server.payload["state_token"])
        candidate = next(
            candidate for candidate in server.payload["turn_candidates"] if candidate["action_id"]
        )
        server.apply(candidate["action_id"], server.payload["state_token"])
        assert server.payload["log_blocks"][-1]["round_end"] is False
        assert EventType.MERCHANT_ADVANCE.value in server.payload["log_blocks"][-1]["event_types"]

        _pass_end_turn_window(server)

        assert server.payload["log_blocks"][-1]["round_end"] is True
        assert EventType.MERCHANT_ADVANCE.value in server.payload["log_blocks"][-1]["event_types"]
        assert _phase_row_keys(server) == [
            "round_marker",
            "merchant",
            "choose_first_player",
        ]
        assert _phase_row_keys(server).count("merchant") == 1
        assert _phase_row_keys(server).index("merchant") == 1
        assert _current_phase_row_keys(server) == ["choose_first_player"]
    finally:
        server.server_close()


def test_game_over_keeps_the_three_turn_phase_rows_dim() -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "scoring_basic_breakdown_001.json")
    try:
        assert server.state.game_over is True
        assert server.payload["phase_column"] == {
            "scope": "inactive",
            "rows": [
                {"key": "beginning", "label": "Beginning of Turn", "current": False},
                {"key": "sow", "label": "Sow", "current": False},
                {"key": "end", "label": "End of Turn", "current": False},
            ],
        }
    finally:
        server.server_close()


def test_player_log_drops_developer_dump_lines_in_ordinary_play(tmp_path: Path) -> None:
    server = _played_through_setup(_served(tmp_path))
    for _ in range(4):
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)

    lines = [line for block in server.payload["log_blocks"] for line in block["lines"]]
    assert lines, "ordinary play produced no log lines"
    assert not any("DUTY_DEFERRED" in line for line in lines)
    assert not any("START_PLAYER_TIE_BREAK" in line for line in lines)
    assert not any(re.search(r"\b[A-Z_]+: .*; .*", line) for line in lines), lines


def test_recall_is_a_turn_step_and_round_end_prefixes_stay_on_round_end_steps(
    tmp_path: Path,
) -> None:
    server = _played_through_setup(_served(tmp_path))

    first_turn = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
    server.apply(first_turn["action_id"], server.payload["state_token"])
    turn_lines = server.payload["log_blocks"][-1]["lines"]
    recall_line = next((line for line in turn_lines if "recalled" in line.lower()), None)
    assert recall_line is not None, f"turn block had no recall line: {turn_lines}"
    assert not recall_line.startswith("Round end:"), recall_line
    _pass_end_turn_window(server)

    while server.payload["state"]["timing"]["round_number"] == 1:
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)

    round_end_lines = server.payload["log_blocks"][-1]["lines"]
    for expected in ("ship advanced", "Merchant advanced", "First Player marker"):
        matched = [line for line in round_end_lines if expected in line]
        assert matched, f"no round-end line mentioning {expected!r}: {round_end_lines}"
        assert all(line.startswith("Round end:") for line in matched), matched


def _contains_compass_position_name(text: str) -> bool:
    lowered = text.lower()
    for name in CANONICAL_POSITION_NAMES[1:]:
        pattern = rf"\b{name.replace('_', r'[_ ]')}\b"
        if re.search(pattern, lowered):
            return True
    return False


@pytest.mark.parametrize("resolution", _RESOLUTION_NAMES)
def test_reachable_resolution_log_lines_stay_in_player_language(
    resolution: str, resolution_guard_sample
) -> None:
    reached, missing = resolution_guard_sample
    if resolution not in reached:
        pytest.skip(
            f"fixture cannot reach resolution: {resolution}; missing set: {', '.join(missing)}"
        )

    lines = reached[resolution]
    assert lines, f"{resolution} produced no player log lines"
    missing_text = ", ".join(missing) if missing else "none"
    for line in lines:
        spoken = unescape(render_play_view.say(line))
        assert "_" not in spoken, (
            f"{resolution} leaked underscore text: {spoken!r}. "
            f"fixture missing resolutions: {missing_text}"
        )
        assert "->" not in spoken and "-&gt;" not in spoken, (
            f"{resolution} leaked arrow text: {spoken!r}. "
            f"fixture missing resolutions: {missing_text}"
        )
        assert not re.match(r"^[A-Z_]+:\s", spoken), (
            f"{resolution} leaked developer prefix text: {spoken!r}. "
            f"fixture missing resolutions: {missing_text}"
        )
        assert not _contains_compass_position_name(spoken), (
            f"{resolution} leaked board-position name: {spoken!r}. "
            f"fixture missing resolutions: {missing_text}"
        )


def test_taxation_lines_carry_the_gain_without_a_resource_delta_duplicate(
    resolution_guard_sample,
) -> None:
    reached, missing = resolution_guard_sample
    if "taxation" not in reached:
        pytest.skip(f"fixture cannot reach resolution: taxation; missing set: {', '.join(missing)}")

    spoken = [unescape(render_play_view.say(line)) for line in reached["taxation"]]
    assert any("took" in line.lower() and "taxation" in line.lower() for line in spoken), spoken
    assert not any(
        re.search(r"\b(stone|silver|wheat)\s+[+-]\\d", line.lower()) for line in spoken
    ), spoken


def test_piety_lines_drop_track_vp_debug_wording(resolution_guard_sample) -> None:
    reached, missing = resolution_guard_sample
    if "clerical_devotion" not in reached:
        pytest.skip(
            f"fixture cannot reach resolution: clerical_devotion; missing set: {', '.join(missing)}"
        )

    spoken = [unescape(render_play_view.say(line)) for line in reached["clerical_devotion"]]
    piety_lines = [line for line in spoken if "piety" in line.lower()]
    assert piety_lines, spoken
    assert not any("track vp" in line.lower() for line in piety_lines), piety_lines


@needs_node
def test_a_taxation_turn_is_playable_and_takes_the_stock_that_was_pressed(
    tmp_path: Path,
) -> None:
    """Played once per stock from the same board, and the stock pressed is the one that grows.

    Comparing the runs against each other rather than against a written-down expectation: taxation
    can pay a second time from its majority tiles, so what a turn is worth is the engine's business
    and only the DIFFERENCE the choice makes is this page's.
    """
    grown: dict[str, dict] = {}
    for index in range(3):
        server = _reference_server()
        asked = _asked(server, "taxation", "resource")
        assert asked, "no taxation turn on this board, so nothing was exercised"
        offered = _siblings(asked, asked[0], "resource")
        assert len(offered) == 3, "the Taxation tile did not offer all three stocks"
        candidate = offered[index]
        picked = _answer(candidate, "resource")
        seat = server.payload["state"]["active_player"]
        before = _stocks(server, seat)

        _played_from_the_page(server, candidate, tmp_path)
        after = _stocks(server, seat)
        grown[picked] = {stock: after[stock] - before[stock] for stock in before}

    for picked, deltas in grown.items():
        assert deltas[picked] > 0, f"pressing {picked} did not take any {picked}"
        for other, others in grown.items():
            if other != picked:
                assert deltas[picked] > others[picked], "the stock taken did not follow the press"


def _pair(value: str) -> tuple[int, ...]:
    """A combination key read back as the amounts it stands for."""
    return tuple(int(part.split("=")[1]) for part in value.split(","))


def _alms_group(server) -> list[dict]:
    """One set of alms candidates alike in everything but what they pay, with a real choice in it.

    Not simply the first: where only one split is legal there is nothing to ask, and the page is
    right to take it rather than offer it. A group with something to decide is what exercises this.
    """
    asked = _asked(server, "give_alms_paid", "combination")
    assert asked, "no paid alms on this board, so nothing was exercised"
    for candidate in asked:
        siblings = _siblings(asked, candidate, "combination")
        if len(siblings) > 1:
            return siblings
    raise AssertionError("every alms on this board had only one legal split, so none was offered")


def _offered_pairs(server) -> tuple[set, set]:
    """What the page offers to pay, and what the engine says may be paid, in the same shape.

    The engine's side is derived from `legal_actions` rather than written down, so the check is
    against the rules as they are today and not against a list somebody kept up to date.
    """
    siblings = _alms_group(server)
    wanted = _values_except(siblings[0]["steps"], "combination")
    actions = list(legal_actions(server.state, server.config))
    (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    ) = _offer_flags_by_action_id(
        actions,
        state=server.state,
        config=server.config,
    )

    offered = {_pair(_answer(candidate, "combination")) for candidate in siblings}
    legal = {
        tuple(getattr(action, name) for name in ALMS_PAIR)
        for action in actions
        if _values_except(
            _engine_steps(
                action,
                config=server.config,
                offer_hire=offer_hire_by_action_id[action_id(action)],
                hire_payment_buildings=hire_payment_buildings_by_action_id[action_id(action)],
            ),
            "combination",
        )
        == wanted
    }
    return offered, legal


def _the_payments_offered_are_the_legal_pairs(server) -> set:
    offered, legal = _offered_pairs(server)
    assert offered == legal, "the payments offered are not the pairs the engine allows"
    assert len(offered) > 1, "a payment was 'chosen' from a single option"
    return offered


@needs_node
def test_the_alms_payments_offered_are_the_legal_pairs_and_the_one_pressed_is_paid(
    tmp_path: Path,
) -> None:
    """A payment is a pair, so pairs are what is offered -- never one number and then the other.

    Setting the amounts one at a time would walk through splits the engine never offered, and
    deciding which second amount goes with a given first is the engine's rule. Offering the whole
    combinations means the page never has to know.
    """
    server = _reference_server()
    _the_payments_offered_are_the_legal_pairs(server)

    candidate = _alms_group(server)[0]
    silver, wheat = _pair(_answer(candidate, "combination"))
    seat = server.payload["state"]["active_player"]
    before = _stocks(server, seat)

    _played_from_the_page(server, candidate, tmp_path)
    after = _stocks(server, seat)

    assert after["silver"] == before["silver"] - silver
    assert after["wheat"] == before["wheat"] - wheat


def _clicks_before_the_stock(server, candidate: dict) -> list[dict]:
    """The clicks that get as far as being asked which stock, and stop there."""
    decisions = _engine_decisions(server)
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])
    kinds = [click["kind"] for click in clicks]
    assert "resource" in kinds, "this candidate never asked for a stock"
    return clicks[: kinds.index("resource")]


def _only_the_active_seat_is_asked(transcript: dict, seat: int) -> None:
    """The stock being picked is this seat's, and nobody may reach across the table for it."""
    assert transcript["askedSeats"][-1] == [str(seat)], "the wrong seat's board was asked"
    assert list(transcript["offeredBySeat"][-1]) == [str(seat)], "another seat had a key to press"
    assert transcript["offeredBySeat"][-1][str(seat)], "the seat being asked had no key"


@needs_node
def test_a_counter_that_pays_one_thing_still_asks_for_its_stock(tmp_path: Path) -> None:
    """A tithe with one named stock lights that stock's board before it can be confirmed."""
    server = _reference_server()
    asked = _asked(server, "tithe", "resource")
    forced = [c for c in asked if len(_siblings(asked, c, "resource")) == 1]
    assert forced, "every tithe on this board was a Cornucopia, so nothing was exercised"

    candidate = forced[0]
    decisions = _engine_decisions(server)
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])

    assert any(click["kind"] == "resource" for click in clicks), "the settled stock was not pressed"
    seat = SEATED_PLAYERS.index(server.payload["state"]["active_player"]) + 1
    before_stock = _run_script(server, _clicks_before_the_stock(server, candidate), tmp_path)
    assert before_stock["askedSeats"][-1] == [str(seat)], "the settled stock never lit its board"
    transcript = _run_script(server, clicks, tmp_path, confirm=True)
    assert transcript["posted"]["action_id"] == candidate["action_id"]


@needs_node
def test_only_the_seat_being_asked_has_keys_on_its_board(tmp_path: Path) -> None:
    """Four boards carry the keys, drawn hidden. One of them is ever asked."""
    server = _reference_server()
    candidate = _asked(server, "tithe", "resource")[0]
    seat = SEATED_PLAYERS.index(server.payload["state"]["active_player"]) + 1

    transcript = _run_script(server, _clicks_before_the_stock(server, candidate), tmp_path)

    assert transcript["askedSeats"][0] == [], "a board was asked before anything had been decided"
    _only_the_active_seat_is_asked(transcript, seat)


# ---------------------------------------------------------------------------------------------
# The Taxation bonus, which is a whole mix of stocks and is offered whole
# ---------------------------------------------------------------------------------------------


def _counts(value: str) -> dict[str, int]:
    """A combination step's value read back as amounts, which is what it encodes."""
    return {noun: int(amount) for noun, amount in (part.split("=") for part in value.split(","))}


def _mix_groups(server) -> dict[tuple, set[str]]:
    """Every prefix reaching a Taxation bonus, and the mixes it goes on to offer.

    Keyed on everything decided EXCEPT the mix, so what comes back is the choice rather than the
    candidates carrying it. Only prefixes offering more than one are kept: a single mix is not a
    choice, and that it is never asked about is a separate test.
    """
    groups: dict[tuple, set[str]] = {}
    for candidate in server.payload["turn_candidates"]:
        if not _resolves(candidate, "taxation"):
            continue
        mix = [step["value"] for step in candidate["steps"] if step["kind"] == "combination"]
        if not mix:
            continue
        groups.setdefault(tuple(_values_except(candidate["steps"], "combination")), set()).add(
            mix[0]
        )
    return {prefix: seen for prefix, seen in groups.items() if len(seen) > 1}


def _played_until_a_bonus_offers_a_choice(server, limit: int = 30):
    """Play on until a Taxation turn offers more than one mix, so the test has its question."""
    for _turn in range(limit):
        if _mix_groups(server):
            return server
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)
    raise AssertionError("no Taxation bonus ever offered a choice, so nothing was tested")


def _mixes_the_engine_allows(server, prefix: tuple) -> set[str]:
    """Read off the actions themselves, not off the steps the page was handed."""
    actions = list(legal_actions(server.state, server.config))
    (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    ) = _offer_flags_by_action_id(
        actions,
        state=server.state,
        config=server.config,
    )
    allowed = set()
    for action in actions:
        steps = _engine_steps(
            action,
            config=server.config,
            offer_hire=offer_hire_by_action_id[action_id(action)],
            hire_payment_buildings=hire_payment_buildings_by_action_id[action_id(action)],
        )
        if getattr(action, "resolution", None) is None or action.resolution.value != "taxation":
            continue
        if tuple(_values_except(steps, "combination")) != prefix:
            continue
        allowed.add(next(s["value"] for s in steps if s["kind"] == "combination"))
    return allowed


@needs_node
@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_a_taxation_bonus_takes_the_mix_that_was_named_and_leaves_the_rest(
    index: int,
    tmp_path: Path,
) -> None:
    """Played once per mix, and what is checked FIRST is the stock the mix does not name.

    A bonus that took everything, or that ignored the answer and took some default, would move the
    two stocks the mix names correctly often enough to look right. The stock left alone is what
    tells those apart, so it is asserted before the ones that grow. Parametrised over four of the
    six mixes -- including both a doubled stock and two different ones -- so no single mix can pass
    by being whatever the engine would have done anyway.
    """
    server = _played_until_a_bonus_offers_a_choice(_reference_server())
    prefix, offered = sorted(_mix_groups(server).items())[0]
    assert len(offered) > index, "this board offered fewer mixes than the test asks for"

    wanted = sorted(offered)[index]
    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if tuple(_values_except(c["steps"], "combination")) == prefix
        and _answer(c, "combination") == wanted
    )
    bonus = _counts(wanted)
    # Step one takes its own stock, and it is not the thing under test -- so it is added to the
    # bonus rather than assumed to be zero, and the totals below are what the whole turn is worth.
    taken = dict(bonus)
    step_one = _answer(candidate, "resource")
    taken[step_one] = taken.get(step_one, 0) + 1

    seat = server.payload["state"]["active_player"]
    before = _stocks(server, seat)
    _played_from_the_page(server, candidate, tmp_path)
    after = _stocks(server, seat)

    untouched = [stock for stock in before if not taken.get(stock)]
    for stock in untouched:
        assert after[stock] == before[stock], f"{stock} moved and this mix does not name it"
    for stock, amount in taken.items():
        if amount:
            assert after[stock] - before[stock] == amount, f"{stock} did not move by {amount}"


@needs_node
def test_the_mixes_offered_are_the_ones_the_engine_allows(tmp_path: Path) -> None:
    """Derived from the survivors, never from a written-down list.

    This one is falsifiable on the board as it stands, which the seat and building choices were
    not. The mixes are `combinations_with_replacement(unlocked stocks, duty value)`, and both of
    those move: over the walk this board reaches six DIFFERENT mix sets, and only one of them is
    the six pairs of three stocks. Most Taxation groups offer exactly one mix. So a page that had
    the six written down would offer six where the engine allows one, and `_mixes_the_engine_allows`
    would catch it without anything being perturbed.
    """
    server = _played_until_a_bonus_offers_a_choice(_reference_server())
    prefix, offered = sorted(_mix_groups(server).items())[0]
    assert offered == _mixes_the_engine_allows(server, prefix)

    decisions = _engine_decisions(server)
    transcript = _run_script(server, _clicks_to(server, decisions, list(prefix)), tmp_path)
    eligible = {
        resource for value in offered for resource, amount in _counts(value).items() if amount > 0
    }
    assert set(transcript["offered"][-1]) & {"stone", "silver", "wheat"} == eligible
    assert not [value for value in transcript["offered"][-1] if "=" in value]
    prompts = {
        step["prompt"]
        for candidate in server.payload["turn_candidates"]
        if tuple(_values_except(candidate["steps"], "combination")) == prefix
        for step in candidate["steps"]
        if step["kind"] == "combination" and step.get("resource_total") == 2
    }
    assert len(prompts) == 1
    assert transcript["asking"][-1] == [prompts.pop()]


@needs_node
def test_a_taxation_bonus_with_one_mix_still_uses_the_resource_pills(tmp_path: Path) -> None:
    """A single non-empty mix is still answered through the Step II pill question."""
    server = _reference_server()
    while not any(
        _resolves(candidate, "taxation")
        and any(step["kind"] == "combination" for step in candidate["steps"])
        for candidate in server.payload["turn_candidates"]
    ):
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)

    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if _resolves(c, "taxation") and any(step["kind"] == "combination" for step in c["steps"])
    )
    forced = _answer(candidate, "combination")

    decisions = _engine_decisions(server)
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])
    transcript = _run_script(server, clicks, tmp_path, confirm=True)

    assert transcript["posted"]["action_id"] == candidate["action_id"]
    assert forced not in transcript["offered"][-1]


def test_a_mix_is_offered_in_english_and_never_as_a_tuple() -> None:
    """The label is what a player reads, so it has to be a sentence rather than a spelling.

    The engine states a mix as a run of names -- ("stone", "stone") is two stone -- and printing
    that at somebody would be showing them the data structure. One of something loses its number
    too, because "take stone and silver" is how it would be said out loud.
    """
    server = _played_until_a_bonus_offers_a_choice(_reference_server())
    labels = _the_mixes_read_as_english(server)
    assert "take two stone" in labels
    assert "take stone and silver" in labels


def test_taxation_step_two_prompt_hides_real_count_majorities() -> None:
    scenario = load_scenario("scenarios/tithe_counter_choice_001.json")
    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        actions=tuple(legal_actions(scenario.state, scenario.config)),
    )
    taxation_steps = [
        step
        for candidate in candidates
        for step in candidate["steps"]
        if step["kind"] == "combination" and step.get("resource_total") == 2
    ]

    assert taxation_steps
    assert {step["prompt"] for step in taxation_steps} == {
        "player_one: Taxation step 2. Choose two resources."
    }
    step_two = taxation_steps[0]
    assert step_two["resource_delta"] == {"stone": 2, "silver": 0, "wheat": 0}
    assert step_two["resource_unit_deltas"]["wheat"] == {
        "stone": 0,
        "silver": 0,
        "wheat": 1,
    }
    assert not hasattr(play_server, "COMBINATION_PROMPT")
    assert (
        play_server._combination_step(
            "pay", [("silver", 1), ("wheat", 1)], prompt=play_server.ALMS_PAYMENT_PROMPT
        )["prompt"]
        == "Choose payment."
    )


def test_taxation_step_two_without_a_majority_has_no_zero_resource_instruction() -> None:
    scenario = load_scenario("scenarios/taxation_no_other_majority_001.json")
    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        actions=tuple(legal_actions(scenario.state, scenario.config)),
    )
    prompts = {
        step["prompt"]
        for candidate in candidates
        for step in candidate["steps"]
        if step["kind"] == "combination" and step.get("resource_total") == 0
    }

    assert prompts == {"player_one: Taxation step 2. No other Duty tile is a majority."}


@pytest.mark.parametrize(
    ("scenario_path", "expected"),
    (
        (
            "scenarios/scriptorium_taxation_majority_other_tiles_001.json",
            "player_one: Taxation step 2. The Scriptorium makes south west and west majorities. "
            "Choose two resources.",
        ),
        (
            "scenarios/customs_house_active_taxation_majority_001.json",
            "player_one: Taxation step 2. The Customs House makes your occupied tiles majorities. "
            "Choose two resources.",
        ),
    ),
)
def test_taxation_step_two_prompt_explains_building_majorities(
    scenario_path: str,
    expected: str,
) -> None:
    scenario = load_scenario(scenario_path)
    candidates = play_server.turn_candidates(
        scenario.state,
        scenario.config,
        actions=tuple(legal_actions(scenario.state, scenario.config)),
    )
    prompts = {
        step["prompt"]
        for candidate in candidates
        for step in candidate["steps"]
        if step["kind"] == "combination" and step.get("resource_total") == 2
    }

    assert prompts == {expected}


def test_taxation_step_two_prompt_names_one_scriptorium_majority(monkeypatch) -> None:
    scenario = load_scenario("scenarios/playtest/cloisters_loop_2p.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TAXATION
        and len(candidate.taxation_step2_resources) == 2
    )
    north_east = scenario.config.board.positions.index("north_east")
    unlock = TaxationMajorityUnlock(
        duty_position=north_east,
        duty_category="give_alms",
        resources=("wheat",),
        majority_reason="scriptorium",
        player_acolytes=1,
        effective_player_acolytes=2,
        competing_acolytes=1,
    )
    monkeypatch.setattr(
        play_server,
        "taxation_majority_unlocks_for_action",
        lambda _state, _config, _action: (unlock,),
    )

    assert play_server._taxation_step_two_prompt(action, scenario.state, scenario.config) == (
        "Taxation step 2. The Scriptorium makes north east a majority. Choose two resources."
    )


def test_cornucopia_tithe_resource_step_carries_engine_delta() -> None:
    server = _reference_server()
    tithe_steps = [
        step
        for candidate in server.payload["turn_candidates"]
        if any(
            step["kind"] == "resolution" and step["value"] == "tithe" for step in candidate["steps"]
        )
        for step in candidate["steps"]
        if step["kind"] == "resource"
    ]
    assert {step["value"] for step in tithe_steps} >= {"stone", "silver", "wheat"}
    for step in tithe_steps:
        assert step["resource_delta"] == {
            resource: int(resource == step["value"]) for resource in ("stone", "silver", "wheat")
        }


def _candidate_action(scenario, candidate: dict):
    assert candidate["action_id"] is not None
    return next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action_id(action) == candidate["action_id"]
    )


def test_resource_preview_step_matches_engine_after_produce() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    candidate = next(
        candidate
        for candidate in candidates
        if any(
            step["kind"] == "resolution" and step["value"] == "produce_wheat"
            for step in candidate["steps"]
        )
    )
    action = _candidate_action(scenario, candidate)
    before = scenario.state.player_state(scenario.state.active_player).resources
    after = (
        apply_action(scenario.state, action, scenario.config)
        .state.player_state(scenario.state.active_player)
        .resources
    )
    step = next(step for step in candidate["steps"] if step["value"] == "produce_wheat")
    assert step["resource_delta"] == {
        resource: getattr(after, resource) - getattr(before, resource)
        for resource in ("stone", "silver", "wheat")
    }


def test_construction_preview_step_carries_engine_building_and_cost() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    candidate = next(
        candidate
        for candidate in candidates
        if any(
            step["kind"] == "building" and step["value"] == "well" for step in candidate["steps"]
        )
    )
    action = _candidate_action(scenario, candidate)
    before_player = scenario.state.player_state(scenario.state.active_player)
    after_player = apply_action(scenario.state, action, scenario.config).state.player_state(
        scenario.state.active_player
    )
    step = next(step for step in candidate["steps"] if step["kind"] == "building")
    assert step["building_constructed"] in after_player.player_board_slots.active_buildings
    assert step["resource_delta"] == {
        resource: getattr(after_player.resources, resource)
        - getattr(before_player.resources, resource)
        for resource in ("stone", "silver", "wheat")
    }


def test_devotion_preview_step_matches_engine_piety_destination() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_chapel_001.json")
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    candidate = next(
        candidate
        for candidate in candidates
        if any(step.get("piety_delta") is not None for step in candidate["steps"])
    )
    action = _candidate_action(scenario, candidate)
    result = apply_action(scenario.state, action, scenario.config)
    step = next(step for step in candidate["steps"] if step.get("piety_delta") is not None)
    event = next(event for event in result.events if event.event_type is EventType.PIETY_DELTA)

    assert step["piety_delta"] == dict(event.details)
    assert (
        step["piety_delta"]["new_piety_position"]
        == result.state.player_state(scenario.state.active_player).piety
    )


def test_devotion_preview_uses_the_engine_cap_at_twelve() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_chapel_001.json")
    active = scenario.state.player_state(scenario.state.active_player)
    state = replace(
        scenario.state,
        players=(replace(active, piety=11), *scenario.state.players[1:]),
    )
    candidates = play_server.turn_candidates(state, scenario.config)
    candidate = next(
        candidate
        for candidate in candidates
        if any(step.get("piety_delta") is not None for step in candidate["steps"])
    )
    action = next(
        action
        for action in legal_actions(state, scenario.config)
        if action_id(action) == candidate["action_id"]
    )
    after = apply_action(state, action, scenario.config).state.player_state(state.active_player)
    step = next(step for step in candidate["steps"] if step.get("piety_delta") is not None)

    assert step["piety_delta"]["new_piety_position"] == after.piety
    assert after.piety == scenario.config.piety.max_position


def test_building_donation_preview_step_matches_engine_slot_state() -> None:
    scenario = load_scenario("scenarios/give_alms_donate_building_001.json")
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    candidate = next(
        candidate
        for candidate in candidates
        if any(step.get("building_donation") is not None for step in candidate["steps"])
    )
    action = _candidate_action(scenario, candidate)
    before = scenario.state.player_state(scenario.state.active_player)
    after = apply_action(scenario.state, action, scenario.config).state.player_state(
        scenario.state.active_player
    )
    step = next(step for step in candidate["steps"] if step.get("building_donation") is not None)

    assert step["building_donation"] == action.donate_building_id
    assert step["building_donation"] in after.player_board_slots.donated_buildings
    assert step["building_donation"] in before.player_board_slots.active_buildings


def test_guild_is_a_committed_turn_step_not_a_candidate_question() -> None:
    scenario = load_scenario("scenarios/guild_active_move_merchant_001.json")
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    steps = play_server.turn_steps_payload(scenario.state, scenario.config)
    guild = next(
        step for step in steps if step["kind"] == "activation" and step["building_id"] == "guild"
    )
    assert guild["source"] == "own_active"
    assert guild["prompt"] == "Activate Guild: move the Merchant clockwise +1 Duty tile."
    assert not any(
        step["kind"] == "merchant_advance"
        for candidate in candidates
        for step in candidate["steps"]
    )


def test_building_ability_payload_carries_each_engine_source_field_and_refreshes() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    try:
        abilities = {
            ability["building_id"]: ability for ability in server.payload["building_abilities"]
        }
        assert set(abilities) == {building.id for building in server.config.buildings.catalogue}
        assert abilities["dormitory"] == {
            "building_id": "dormitory",
            "source_type": "own_active",
            "owner": "player_one",
            "hire_resource": None,
            "hire_resource_chosen": False,
            "hire_cost": 0,
            "payable_to": None,
            "usable": True,
            "reason": None,
            "greyed": False,
            "map_tile": False,
            "status_text": "Usable: no payment.",
        }
        assert abilities["kogge"]["owner"] == "player_two"
        assert abilities["kogge"]["payable_to"] == "player_two"
        assert abilities["kogge"]["status_text"] == "Usable: pay 1 silver to Yellow."
        assert abilities["mill"]["reason"] == "not_selected"

        server.state = _with_stock(server.state, stone=4, silver=0, wheat=4)
        server._refresh()
        refreshed = next(
            ability
            for ability in server.payload["building_abilities"]
            if ability["building_id"] == "kogge"
        )
        assert refreshed["reason"] == "insufficient_resource"
        assert (refreshed["greyed"], refreshed["status_text"]) == (
            True,
            "Cannot be hired: insufficient silver to pay 1 silver to Yellow.",
        )
    finally:
        server.server_close()


def test_route_family_ability_payload_uses_resolved_ownership_not_board_placement() -> None:
    def kogge_ability(scenario_path: str) -> dict:
        scenario = load_scenario(scenario_path)
        payload = play_server.route_family_payload(
            scenario.state,
            scenario.config,
        )
        return next(
            ability
            for ability in payload["building_abilities"]
            if ability["building_id"] == "kogge"
        )

    hired = kogge_ability(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    owned = kogge_ability("scenarios/kogge_active_city_to_east_001.json")
    donated = kogge_ability("scenarios/kogge_donated_no_extra_routes_001.json")

    assert {
        "hired": {
            field: hired[field]
            for field in (
                "source_type",
                "family_visibility",
                "toggle_waiting_text",
                "toggle_off_text",
                "toggle_on_text",
            )
        },
        "owned": {
            field: owned[field]
            for field in ("source_type", "family_visibility", "owned_status_text")
        },
        "donated": {
            field: donated.get(field)
            for field in ("source_type", "family_visibility", "status_text")
        },
    } == {
        "hired": {
            "source_type": "opponent_active_hire",
            "family_visibility": "toggle",
            "toggle_waiting_text": (
                "Pick up acolytes first, then show the routes it opens — "
                "1 silver to Yellow if you use one."
            ),
            "toggle_off_text": (
                "After choosing an origin, show the routes it opens — "
                "1 silver to Yellow if you use one."
            ),
            "toggle_on_text": (
                "Routes shown — click to hide and restart your sow. "
                "Nothing is paid until you use one."
            ),
        },
        "owned": {
            "source_type": "own_active",
            "family_visibility": "always",
            "owned_status_text": "Yours: in effect every turn.",
        },
        "donated": {
            "source_type": "unavailable",
            "family_visibility": None,
            "status_text": "Cannot be hired: this building was donated by Yellow.",
        },
    }


def test_merchant_without_a_hire_resource_greys_hires_but_not_own_buildings() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    no_hire_resource = replace(scenario.state, merchant_board_position=1)
    abilities = {
        ability["building_id"]: ability
        for ability in play_server.building_abilities_payload(no_hire_resource, scenario.config)
    }

    assert {
        building_id: (ability["reason"], ability["greyed"])
        for building_id, ability in abilities.items()
        if building_id in {"dormitory", "kogge"}
    } == {
        "dormitory": (None, False),
        "kogge": ("merchant_resource_none", True),
    }


def test_building_ability_payload_marks_only_an_already_used_dormitory() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    baseline = {
        ability["building_id"]: ability
        for ability in play_server.building_abilities_payload(scenario.state, scenario.config)
    }
    state = replace(
        scenario.state,
        turn_progress=replace(scenario.state.turn_progress, used_buildings=frozenset({"dormitory"})),
    )
    abilities = {
        ability["building_id"]: ability
        for ability in play_server.building_abilities_payload(state, scenario.config)
    }
    windows = play_server.building_ability_windows_payload(state, scenario.config)
    window_dormitory = {
        window: next(
            ability
            for ability in payload["abilities"]
            if ability["building_id"] == "dormitory"
        )
        for window, payload in windows.items()
    }

    assert {
        "dormitory": {
            "payload": tuple(
                abilities["dormitory"][field]
                for field in ("usable", "reason", "greyed", "status_text")
            ),
            "beginning": tuple(
                window_dormitory["beginning"][field]
                for field in ("usable", "reason", "greyed", "status_text")
            ),
            "sow": tuple(
                window_dormitory["sow"][field]
                for field in ("usable", "reason", "greyed", "status_text")
            ),
            "end": tuple(
                window_dormitory["end"][field]
                for field in ("usable", "reason", "greyed", "status_text")
            ),
        },
        "unchanged": {
            building_id: abilities[building_id] == baseline[building_id]
            for building_id in ("guild", "inquisition", "kogge")
        },
    } == {
        "dormitory": {
            "payload": (False, "already_used", True, "Cannot be used: already used this turn."),
            "beginning": (False, "already_used", True, "Cannot be used: already used this turn."),
            "sow": (False, "mid_sow", True, "Cannot be used: sowing is in progress."),
            "end": (False, "already_used", True, "Cannot be used: already used this turn."),
        },
        "unchanged": {"guild": True, "inquisition": True, "kogge": True},
    }


def test_building_window_tiles_only_supply_a_phase_reason_when_the_other_window_offers_it() -> None:
    """A phase reason means this is the building's other committed-step window."""
    checked_scenarios = 0
    paths = [*sorted(SCENARIOS.glob("*.json")), *sorted(PLAYTEST_SCENARIOS.glob("*.json"))]
    for scenario_path in paths:
        scenario = load_scenario(str(scenario_path))
        windows = play_server.building_ability_windows_payload(scenario.state, scenario.config)
        offered_by_window = {}
        for window, resolution_committed in (("beginning", False), ("end", True)):
            window_state = replace(
                scenario.state,
                turn_progress=replace(
                    scenario.state.turn_progress,
                    resolution_committed=resolution_committed,
                ),
            )
            offered_by_window[window] = {
                step.building_id for step in turn_steps(window_state, scenario.config)
            }

        for window, other_window in (("beginning", "end"), ("end", "beginning")):
            for ability in windows[window]["abilities"]:
                if ability["reason"] in {
                    BuildingAbilityReason.END_OF_TURN_NOT_REACHED,
                    BuildingAbilityReason.BEGINNING_OF_TURN_PASSED,
                }:
                    assert ability["building_id"] in offered_by_window[other_window], (
                        f"{scenario_path.name} {window} supplied a phase reason for "
                        f"{ability['building_id']} without an opposite-window step"
                    )
        checked_scenarios += 1

    assert checked_scenarios >= 320, f"only {checked_scenarios} scenarios checked"


def test_building_window_tiles_preserve_sources_without_a_committed_step_in_either_window() -> None:
    """Sow abilities and independently unavailable sources do not acquire phase reasons."""
    checked_scenarios = 0
    paths = [*sorted(SCENARIOS.glob("*.json")), *sorted(PLAYTEST_SCENARIOS.glob("*.json"))]
    for scenario_path in paths:
        scenario = load_scenario(str(scenario_path))
        actions = list(legal_actions(scenario.state, scenario.config))
        windows = play_server.building_ability_windows_payload(
            scenario.state,
            scenario.config,
            actions=actions,
        )
        offered_by_window = {}
        for window, resolution_committed in (("beginning", False), ("end", True)):
            window_state = replace(
                scenario.state,
                turn_progress=replace(
                    scenario.state.turn_progress,
                    resolution_committed=resolution_committed,
                ),
            )
            offered_by_window[window] = {
                step.building_id for step in turn_steps(window_state, scenario.config)
            }

        sources = {
            building.id: building_ability_source(
                scenario.state,
                scenario.config,
                acting_player=scenario.state.active_player,
                building_key=building.id,
            )
            for building in scenario.config.buildings.catalogue
        }
        absent_from_steps = set(sources) - (
            offered_by_window["beginning"] | offered_by_window["end"]
        )
        for window in ("beginning", "end"):
            abilities = {
                ability["building_id"]: ability for ability in windows[window]["abilities"]
            }
            for building_id in absent_from_steps:
                source = sources[building_id]
                if (
                    play_server._paid_bank_hire_source(source)
                    and not play_server._paid_bank_payment_on_offer(actions)
                ):
                    assert tuple(
                        abilities[building_id][field]
                        for field in ("usable", "reason", "greyed", "status_text")
                    ) == (
                        False,
                        None,
                        True,
                        "Cannot be used: no action this turn can use the Bank.",
                    ), f"{scenario_path.name} {window} {building_id}"
                    continue
                assert (
                    abilities[building_id]["usable"],
                    abilities[building_id]["reason"],
                ) == (source.usable, source.reason or None), (
                    f"{scenario_path.name} {window} {building_id}"
                )
        checked_scenarios += 1

    assert checked_scenarios >= 320, f"only {checked_scenarios} scenarios checked"


def test_window_tiles_keep_sow_sources_and_no_target_reasons() -> None:
    well_scenario = load_scenario(str(SCENARIOS / "building_hire_live_market_001.json"))
    well_windows = play_server.building_ability_windows_payload(
        well_scenario.state, well_scenario.config
    )
    assert next(
        ability
        for ability in well_windows["beginning"]["abilities"]
        if ability["building_id"] == "well"
    )["usable"] is True

    kogge_scenario = load_scenario(str(SCENARIOS / "kogge_active_city_to_east_001.json"))
    kogge_windows = play_server.building_ability_windows_payload(
        kogge_scenario.state, kogge_scenario.config
    )
    assert next(
        ability
        for ability in kogge_windows["beginning"]["abilities"]
        if ability["building_id"] == "kogge"
    )["usable"] is True

    dormitory_scenario = load_scenario(
        str(SCENARIOS / "dormitory_no_duty_acolyte_no_modifier_001.json")
    )
    dormitory_windows = play_server.building_ability_windows_payload(
        dormitory_scenario.state, dormitory_scenario.config
    )
    dormitory = next(
        ability
        for ability in dormitory_windows["beginning"]["abilities"]
        if ability["building_id"] == "dormitory"
    )
    assert dormitory["reason"] not in {
        BuildingAbilityReason.END_OF_TURN_NOT_REACHED,
        BuildingAbilityReason.BEGINNING_OF_TURN_PASSED,
    }


def test_movement_window_tiles_name_the_unavailable_turn_window() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    windows = play_server.building_ability_windows_payload(scenario.state, scenario.config)
    relevant = {
        window: {
            ability["building_id"]: (
                ability["usable"],
                ability["reason"],
                ability["greyed"],
                ability["status_text"],
            )
            for ability in payload["abilities"]
            if ability["building_id"] in {"dormitory", "inquisition", "library"}
        }
        for window, payload in windows.items()
        if window in {"beginning", "end"}
    }

    assert relevant == {
        "beginning": {
            "dormitory": (True, None, False, "Usable: no payment."),
            "inquisition": (True, None, False, "Usable: pay 1 silver to bank."),
            "library": (
                False,
                "end_of_turn_not_reached",
                True,
                "Cannot be used: End of Turn has not begun.",
            ),
        },
        "end": {
            "dormitory": (
                False,
                "beginning_of_turn_passed",
                True,
                "Cannot be used: Beginning of Turn has passed.",
            ),
            "inquisition": (
                False,
                "beginning_of_turn_passed",
                True,
                "Cannot be used: Beginning of Turn has passed.",
            ),
            "library": (True, None, False, "Usable: pay 1 silver to bank."),
        },
    }


def test_committed_conversion_marks_its_building_already_used_in_the_ability_payload() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS))
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.building_id == "grain_store"
    )
    after_step = apply_turn_step(scenario.state, scenario.config, step)
    grain_store = next(
        ability
        for ability in play_server.building_abilities_payload(after_step, scenario.config)
        if ability["building_id"] == "grain_store"
    )

    assert {
        "conversion": isinstance(step, BuildingConversionStep),
        "used": after_step.turn_progress.used_buildings,
        "payload": tuple(
            grain_store[field] for field in ("usable", "reason", "greyed", "status_text")
        ),
    } == {
        "conversion": True,
        "used": frozenset({"grain_store"}),
        "payload": (False, "already_used", True, "Cannot be used: already used this turn."),
    }


def test_hired_kogge_route_action_leaves_its_tile_showing_the_active_effect() -> None:
    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.sow_route_building_id == "kogge"
        and action.sow_route_building_source == "player_two"
    )
    after_action = apply_action(scenario.state, action, scenario.config).state
    kogge = next(
        ability
        for ability in play_server.building_abilities_payload(after_action, scenario.config)
        if ability["building_id"] == "kogge"
    )

    assert {
        "route_hire": (action.sow_route_building_source, action.hire_payments),
        "tile": tuple(kogge[field] for field in ("usable", "reason", "greyed", "status_text")),
    } == {
        "route_hire": ("player_two", (("kogge", "silver"),)),
        "tile": (
            False,
            "effect_applies_for_rest_of_turn",
            True,
            "In effect for the rest of this turn.",
        ),
    }


@pytest.mark.parametrize(
    ("scenario_path", "building_id", "expected_status"),
    (
        (
            "scenarios/kogge_active_city_to_east_001.json",
            "kogge",
            "In effect for the rest of this turn.",
        ),
        (
            "scenarios/cloisters_active_skip_duty_tile_001.json",
            "cloisters",
            "In effect for the rest of this turn.",
        ),
    ),
)
def test_owned_route_sow_event_leaves_its_tile_showing_the_active_effect(
    scenario_path: str, building_id: str, expected_status: str
) -> None:
    """Owned route effects persist in the committed sow event, not the turn-step-only set."""
    scenario = load_scenario(scenario_path)
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.sow_route_building_id == building_id
        and action.sow_route_building_source == "own_active"
    )
    after_action = apply_action(scenario.state, action, scenario.config).state
    tile = next(
        ability
        for ability in play_server.building_abilities_payload(after_action, scenario.config)
        if ability["building_id"] == building_id
    )

    assert building_id not in after_action.turn_progress.used_buildings
    assert any(
        event.event_type is EventType.BUILDING_BONUS
        and dict(event.details).get("building") == building_id
        and dict(event.details).get("action") == "sowing"
        for event in after_action.turn_progress.events
    )
    assert tuple(tile[field] for field in ("usable", "reason", "greyed", "status_text")) == (
        False,
        "effect_applies_for_rest_of_turn",
        True,
        expected_status,
    )


_PERMITTER_COMMITTED_STEP_CASES = (
    (
        "scenarios/kogge_hire_opponent_city_to_west_001.json",
        "kogge",
        "In effect for the rest of this turn.",
    ),
    (
        "scenarios/cloisters_hire_opponent_skip_city_001.json",
        "cloisters",
        "In effect for the rest of this turn.",
    ),
    (
        "scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json",
        "scriptorium",
        "In effect for the rest of this turn.",
    ),
    (
        "scenarios/customs_house_hire_opponent_taxation_majority_001.json",
        "customs_house",
        "In effect for the rest of this turn.",
    ),
    (
        "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json",
        "bank",
        "In effect for the rest of this turn.",
    ),
)


def _committed_activation_tile(scenario_path: str, building_id: str) -> dict[str, object]:
    scenario = load_scenario(scenario_path)
    if building_id in transition._ROUTE_BUILDING_IDS:
        action = next(
            action
            for action in legal_actions(scenario.state, scenario.config)
            if isinstance(action, FullTurnAction)
            and building_id
            in {action.sow_route_building_id, action.sow_route_secondary_building_id}
            and (
                action.sow_route_building_source not in {None, "own_active"}
                or action.sow_route_secondary_building_source not in {None, "own_active"}
            )
        )
        after_step = apply_action(scenario.state, action, scenario.config).state
    else:
        step = next(
            step for step in turn_steps(scenario.state, scenario.config) if step.building_id == building_id
        )
        assert isinstance(step, BuildingActivationStep)
        after_step = apply_turn_step(scenario.state, scenario.config, step)
    return next(
        ability
        for ability in play_server.building_abilities_payload(after_step, scenario.config)
        if ability["building_id"] == building_id
    )


def test_committed_permitter_tiles_state_that_the_effect_remains_available() -> None:
    rendered = {
        building_id: _committed_activation_tile(scenario_path, building_id)
        for scenario_path, building_id, _expected_status in _PERMITTER_COMMITTED_STEP_CASES
    }

    assert {
        building_id: tuple(tile[field] for field in ("reason", "greyed", "status_text"))
        for building_id, tile in rendered.items()
    } == {
        building_id: ("effect_applies_for_rest_of_turn", True, expected_status)
        for _scenario_path, building_id, expected_status in _PERMITTER_COMMITTED_STEP_CASES
    }


def test_permitter_ability_lines_do_not_repeat_catalogue_effect_words() -> None:
    """Descriptions say the effect; the permitter line is only the time-limited state."""
    catalogue = json.loads(Path("configs/buildings.json").read_text(encoding="utf-8"))["catalogue"]
    ordinary_connectives = frozenset(
        {
            "a",
            "an",
            "and",
            "at",
            "by",
            "for",
            "from",
            "in",
            "of",
            "on",
            "or",
            "the",
            "this",
            "to",
        }
    )
    # Scriptorium's description and the required shared state sentence both say "turn".
    allowed_shared_state_words = ordinary_connectives | {"turn"}

    for building in catalogue:
        building_id = str(building["id"])
        if building_id not in play_server._PERMITTER_BUILDING_IDS:
            continue
        ability_words = set(
            re.findall(
                r"[a-z]+",
                play_server._PERMITTER_STATUS_TEXT.lower(),
            )
        )
        description_words = set(re.findall(r"[a-z]+", str(building["description"]).lower()))
        repeated_effect_words = ability_words & description_words - allowed_shared_state_words

        assert not repeated_effect_words, (building_id, repeated_effect_words)


def test_map_building_payload_carries_its_construct_cost_but_not_after_construction() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    building_id = "well"
    building = next(
        building for building in scenario.config.buildings.catalogue if building.id == building_id
    )
    market_ability = next(
        ability
        for ability in play_server.building_abilities_payload(scenario.state, scenario.config)
        if ability["building_id"] == building_id
    )
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction) and action.construct_building_id == building_id
    )
    after_construction = apply_action(scenario.state, action, scenario.config).state
    board_ability = next(
        ability
        for ability in play_server.building_abilities_payload(after_construction, scenario.config)
        if ability["building_id"] == building_id
    )

    assert market_ability["construct_cost_text"] == f"Construct for {building.stone_cost} stone."
    assert "construct_cost_text" not in board_ability


@pytest.mark.parametrize(
    ("scenario_path", "building_id"),
    (
        ("scenarios/guild_active_move_merchant_001.json", "guild"),
        (
            "scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json",
            "wagon_yard",
        ),
    ),
)
def test_committed_spent_activation_tiles_keep_the_already_used_status(
    scenario_path: str, building_id: str
) -> None:
    tile = _committed_activation_tile(scenario_path, building_id)

    assert tuple(tile[field] for field in ("reason", "greyed", "status_text")) == (
        "already_used",
        True,
        "Cannot be used: already used this turn.",
    )


def test_permitter_reason_partitions_the_reviewed_engine_building_tuples() -> None:
    assert transition._ROUTE_BUILDING_IDS == ("kogge", "cloisters")
    assert transition._HIRED_MODIFIER_BUILDING_IDS == (
        "scriptorium",
        "customs_house",
        "bank",
        "wagon_yard",
    )

    scenario = load_scenario(str(PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT))
    tuple_buildings = set(transition._ROUTE_BUILDING_IDS) | set(
        transition._HIRED_MODIFIER_BUILDING_IDS
    )
    permitters = {
        building.id
        for building in scenario.config.buildings.catalogue
        if play_server._used_building_ability_reason(building.id)
        is BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN
    }

    assert permitters == tuple_buildings - {"wagon_yard"}
    non_tuple_buildings = {
        building.id for building in scenario.config.buildings.catalogue
    } - tuple_buildings
    assert not permitters & non_tuple_buildings


def test_every_engine_building_ability_reason_has_player_facing_text() -> None:
    statuses: dict[BuildingAbilityReason, str] = {}
    for reason in BUILDING_ABILITY_REASONS:
        statuses[reason] = play_server._building_ability_status_text(
            BuildingAbilitySource(
                building_key=(
                    "kogge"
                    if reason is BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN
                    else "test_building"
                ),
                source_type="unavailable",
                owner="player_two",
                hire_resource="silver",
                hire_cost=1,
                payable_to="player_two",
                usable=False,
                reason=reason,
            )
        )
        assert statuses[reason], reason
    assert statuses[BuildingAbilityReason.DONATED] == (
        "Cannot be hired: this building was donated by Yellow."
    )


def test_permitter_reason_requires_a_specific_player_facing_sentence() -> None:
    with pytest.raises(AssertionError, match="Permitter has no player-facing status"):
        play_server._building_ability_status_text(
            BuildingAbilitySource(
                building_key="unmapped_permitter",
                source_type="unavailable",
                usable=False,
                reason=BuildingAbilityReason.EFFECT_APPLIES_FOR_REST_OF_TURN,
            )
        )


def test_cornucopia_turn_step_payload_keeps_the_enumerated_payment_resource() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_CONVERSIONS)
    try:
        hired = [step for step in server.payload["turn_steps"] if step["hire_payment"] is not None]
        assert hired
        assert {step["ability"]["hire_resource"] for step in hired} == {
            step["hire_payment"] for step in hired
        }
        assert all(step["ability"]["hire_resource_chosen"] for step in hired)
        for step in hired:
            payee = step["ability"]["payable_to"]
            displayed_payee = SEAT_COLOURS.get(payee, payee)
            assert step["ability"]["status_text"] == (
                f"Usable: pay 1 {step['hire_payment']} to {displayed_payee}."
            )
    finally:
        server.server_close()


def test_committed_hire_adds_the_engine_event_line_to_the_player_log() -> None:
    server = PlayServer(("127.0.0.1", 0), PLAYTEST_SCENARIOS / PLAYTEST_MOVEMENT)
    try:
        kogge = next(
            action
            for action in legal_actions(server.state, server.config)
            if isinstance(action, FullTurnAction)
            and action.sow_route_building_id == "kogge"
            and action.sow_route_building_source == "player_two"
        )
        server.apply(action_id(kogge), server.payload["state_token"])
        assert "player_one hired Kogge from player_two and paid 1 silver." in server.payload[
            "log_blocks"
        ][-1]["lines"]
        assert "building_hired" in server.payload["log_blocks"][-1]["event_types"]
    finally:
        server.server_close()


@pytest.mark.parametrize(
    ("scenario_name", "payment_units"),
    [
        ("give_alms_threshold_rewards_two_crossings_001.json", 4),
        ("give_alms_threshold_reward_row_six_001.json", 3),
    ],
)
def test_paid_alms_preview_step_carries_engine_progress_and_threshold_events(
    scenario_name: str,
    payment_units: int,
) -> None:
    scenario = load_scenario(SCENARIOS / scenario_name)
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
        and action.alms_payment_silver == payment_units
        and action.alms_payment_wheat == 0
    )
    candidates = play_server.turn_candidates(scenario.state, scenario.config)
    candidate = next(
        candidate for candidate in candidates if candidate["action_id"] == action_id(action)
    )
    step = next(step for step in candidate["steps"] if step.get("resource_allocation_any_total"))
    result = apply_action(scenario.state, action, scenario.config)
    expected_progress = dict(
        next(
            event for event in result.events if event.event_type is EventType.ALMS_PROGRESS
        ).details
    )
    expected_rewards = [
        dict(event.details)
        for event in result.events
        if event.event_type is EventType.ALMS_THRESHOLD_REWARD
    ]

    assert step["resource_allocation"] is True
    assert step["resource_allocation_any_total"] is True
    assert step["resource_delta"] == {
        resource: getattr(
            result.state.player_state(scenario.state.active_player).resources, resource
        )
        - getattr(scenario.state.player_state(scenario.state.active_player).resources, resource)
        for resource in ("stone", "silver", "wheat")
    }
    assert step["alms_progress"] == expected_progress
    assert step["alms_threshold_reward"] == expected_rewards
    assert EventType.WORKFORCE_MOVE not in {event.event_type for event in result.events}


@needs_node
def test_six_taxation_multisets_are_reachable_by_pill_clicks(tmp_path: Path) -> None:
    server = PlayServer(("127.0.0.1", 0), SCENARIOS / "taxation_three_bonus_types_001.json")
    try:
        candidates = [
            candidate
            for candidate in server.payload["turn_candidates"]
            if _resolves(candidate, "taxation") and _answer(candidate, "resource") == "stone"
        ]
        assert len({_answer(candidate, "combination") for candidate in candidates}) == 6
        decisions = _engine_decisions(server)
        outcomes = {}
        for candidate in candidates:
            clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])
            transcript = _run_script(server, clicks, tmp_path, confirm=True)
            assert transcript["posted"]["action_id"] == candidate["action_id"]
            action = next(
                action
                for action in legal_actions(server.state, server.config)
                if action_id(action) == candidate["action_id"]
            )
            result = apply_action(server.state, action, server.config)
            before = server.state.player_state(server.state.active_player).resources
            after = result.state.player_state(server.state.active_player).resources
            outcomes[_answer(candidate, "combination")] = (
                after.stone - before.stone,
                after.silver - before.silver,
                after.wheat - before.wheat,
            )
        assert len(outcomes) == 6
        assert len(set(outcomes.values())) == 6
    finally:
        server.server_close()


# ---------------------------------------------------------------------------------------------
# Constructing, which is answered by pressing a building where it stands on the round track
# ---------------------------------------------------------------------------------------------


def _played_until_a_construct_offers_a_choice(server, limit: int = 30):
    """Play on until a turn asks which building, so the test has the question it is about.

    The reference board reaches one in round 4, when a second building has gone live and the seat
    can afford both. Round 3 has exactly one and is the subject of its own test.
    """
    for _turn in range(limit):
        if _building_choices(server):
            return server
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)
    raise AssertionError("no construct ever offered a choice, so nothing was tested")


def _building_choices(server) -> dict[tuple, set[str]]:
    """Every prefix that reaches a construct, and the buildings it goes on to offer.

    Grouped by everything a candidate decides EXCEPT the building, so what comes back is the choice
    itself rather than the candidates carrying it. Only prefixes offering more than one are kept: a
    prefix with a single building is not a choice and the point of it is that nothing asks.
    """
    choices: dict[tuple, set[str]] = {}
    for candidate in server.payload["turn_candidates"]:
        named = [step["value"] for step in candidate["steps"] if step["kind"] == "building"]
        if not named:
            continue
        choices.setdefault(tuple(_values_except(candidate["steps"], "building")), set()).add(
            named[0]
        )
    return {prefix: seen for prefix, seen in choices.items() if len(seen) > 1}


def _buildings_the_engine_would_construct(server, prefix: tuple) -> list[str]:
    """Read off the actions themselves, not off the steps the page was handed."""
    actions = list(legal_actions(server.state, server.config))
    (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    ) = _offer_flags_by_action_id(
        actions,
        state=server.state,
        config=server.config,
    )
    return sorted(
        {
            action.construct_building_id
            for action in actions
            if getattr(action, "construct_building_id", None) is not None
            and tuple(
                _values_except(
                    _engine_steps(
                        action,
                        config=server.config,
                        offer_hire=offer_hire_by_action_id[action_id(action)],
                        hire_payment_buildings=hire_payment_buildings_by_action_id[
                            action_id(action)
                        ],
                    ),
                    "building",
                )
            )
            == prefix
        }
    )


@needs_node
def test_a_construct_turn_is_playable_and_the_building_named_is_the_one_constructed(
    tmp_path: Path,
) -> None:
    """End to end, and checked in the state rather than in the log.

    A log line saying a Chapter House was constructed is written by the same turn that would write
    it if the wrong building moved, so it cannot be the evidence. What is checked is the market
    losing exactly that building and the seat's board gaining exactly it.
    """
    server = _played_until_a_construct_offers_a_choice(_reference_server())
    prefix, offered = sorted(_building_choices(server).items())[0]
    wanted = sorted(offered)[0]
    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if tuple(_values_except(c["steps"], "building")) == prefix
        and _answer(c, "building") == wanted
    )
    seat = server.payload["state"]["active_player"]
    market_before = list(server.payload["state"]["building_market"])
    held_before = _buildings_held(server, seat)

    _played_from_the_page(server, candidate, tmp_path)

    assert wanted in market_before
    assert wanted not in server.payload["state"]["building_market"]
    assert _buildings_held(server, seat) == [*held_before, wanted]
    # And the one that was not pressed stayed exactly where it was.
    for other in offered - {wanted}:
        assert other in server.payload["state"]["building_market"]


def _buildings_held(server, player_id: str) -> list[str]:
    from tools.ui_debug.play_view_adapter import player_record

    return list(player_record(server.payload, player_id)["player_board_slots"]["active_buildings"])


@needs_node
def test_the_buildings_offered_are_the_ones_the_engine_would_construct(tmp_path: Path) -> None:
    """The lit hexes are the distinct values among the survivors, and nothing wider.

    Twelve buildings stand on the track and each carries a key, so "every building drawn" is a
    reading this page could have taken and it is not the one it takes. What the offered set is
    checked against is the engine's own actions, read off the field they carry.
    """
    server = _played_until_a_construct_offers_a_choice(_reference_server())
    prefix, offered = sorted(_building_choices(server).items())[0]
    accepted = _buildings_the_engine_would_construct(server, prefix)
    assert sorted(offered) == accepted

    on_the_track = _buildings_on_the_track(server)
    assert len(on_the_track) > len(accepted), (
        "every building was constructible, so nothing is shown"
    )

    decisions = _engine_decisions(server)
    transcript = _run_script(server, _clicks_to(server, decisions, list(prefix)), tmp_path)
    assert sorted(v for v in transcript["offered"][-1] if v in on_the_track) == accepted


@needs_node
def test_a_construct_with_one_building_to_go_is_still_put_as_a_question(tmp_path: Path) -> None:
    """A one-building construct remains visible, even though the engine has only one answer.

    Round 3 of the reference board has a single building live, so the construct turns there carry a
    building step whose value nobody has a choice about.  The player still presses its hex: the
    act belongs in the turn record even when no branch follows from it.
    """
    server = _reference_server()
    while not any(
        step["kind"] == "building"
        for candidate in server.payload["turn_candidates"]
        for step in candidate["steps"]
    ):
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        _apply_settled_turn_and_pass(server, settled)

    assert _building_choices(server) == {}, "this position had a choice, so it tests nothing"
    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if any(step["kind"] == "building" for step in c["steps"])
    )
    forced = _answer(candidate, "building")

    decisions = _engine_decisions(server)
    prefix = _values_except(candidate["steps"], "building")
    before_building = _run_script(server, _clicks_to(server, decisions, prefix), tmp_path)
    transcript = _run_script(
        server, _clicks_to(server, decisions, _values(candidate["steps"])), tmp_path, confirm=True
    )

    assert forced in before_building["offered"][-1], "the only building on offer was not asked for"
    assert transcript["posted"]["action_id"] == candidate["action_id"]


# ---------------------------------------------------------------------------------------------
# Naming a player, which is answered by pressing a whole board
# ---------------------------------------------------------------------------------------------


def _opening(tmp_path: Path, players: int = 4):
    """A generated game at the moment it opens, which is this decision and nothing else."""
    from pilgrim.cli import main as cli_main

    path = tmp_path / "opening.json"
    cli_main(["generate-setup", "--players", str(players), "--seed", "99", "--output", str(path)])
    server = PlayServer(("127.0.0.1", 0), path)
    assert server.payload["state"]["phase"] == "start_player_selection"
    return server


def _players_the_engine_would_accept(server) -> list[str]:
    """Read off the actions themselves rather than off `decision_steps`.

    Comparing the page against the same function that fed it would only show it copied faithfully.
    """
    return sorted(
        {
            action.chosen_start_player.name.lower()
            for action in legal_actions(server.state, server.config)
            if isinstance(action, StartPlayerSelectionAction)
        }
    )


def test_at_game_open_the_header_is_one_round_progress_line(tmp_path: Path) -> None:
    server = _opening(tmp_path)
    assert server.state.start_player is None

    page = render_play_view_from_payload(server.payload)
    assert _header_of(page) == [("Status", "Round 1 - 0 of 4 turns played")]


def test_after_the_opening_choice_the_header_stays_a_round_progress_line(tmp_path: Path) -> None:
    server = _opening(tmp_path)
    server.apply("start_player_selection:player_four", server.payload["state_token"])

    assert server.state.start_player is PlayerId.PLAYER_FOUR
    page = render_play_view_from_payload(server.payload)
    assert ("Status", "Setup - 0 of 4 sown") in _header_of(page)


def test_setup_status_counts_sows_and_then_hands_off_to_round_progress(tmp_path: Path) -> None:
    server = _served(tmp_path)
    seen = []
    while server.payload["state"]["phase"] == "setup_sow":
        page = render_play_view_from_payload(server.payload)
        seen.append(dict(_header_of(page))["Status"])
        server.apply(
            server.payload["turn_candidates"][0]["action_id"], server.payload["state_token"]
        )

    after_setup = render_play_view_from_payload(server.payload)
    assert seen == [
        "Setup - 0 of 4 sown",
        "Setup - 1 of 4 sown",
        "Setup - 2 of 4 sown",
        "Setup - 3 of 4 sown",
    ]
    assert dict(_header_of(after_setup))["Status"] == (
        "Setup - 4 of 4 sown. Round 1 - 0 of 4 turns played"
    )


@needs_node
@pytest.mark.parametrize("players", [2, 3, 4])
def test_the_boards_offered_are_the_players_the_engine_would_accept(
    tmp_path: Path,
    players: int,
) -> None:
    """The choosable set falls out of the surviving candidates, as every other set here does.

    Not the row of chairs. The page draws four of those whatever the count and hides the empty
    ones, so a script reaching for "every board" lights seats nobody is sitting in -- and at four
    players that reads identically to the right answer, which is why this is run short as well.
    Two players is the sharpest: the pair on the table are the two ENDS of the row.

    Checked against the engine's own actions, read off the field they carry rather than off the
    steps the page was handed, since comparing the page with what fed it shows only that it copied.
    """
    server = _opening(tmp_path, players)
    transcript = _run_script(server, [], tmp_path)

    accepted = _players_the_engine_would_accept(server)
    assert len(accepted) == players
    assert sorted(transcript["offeredBoards"][0]) == accepted
    assert transcript["shownPanel"][0] == -1, "a board was committed before anyone pressed one"


@needs_node
def test_the_first_thing_a_new_game_asks_is_which_board_begins(tmp_path: Path) -> None:
    """A game opens on this and reaches the sows through it, rather than the other way round."""
    server = _opening(tmp_path)
    assert {step["kind"] for c in server.payload["turn_candidates"] for step in c["steps"]} == {
        "seat"
    }

    transcript = _run_script(server, [_name("player_three")], tmp_path, confirm=True)
    assert transcript["posted"]["action_id"] == "start_player_selection:player_three"

    server.apply(transcript["posted"]["action_id"], server.payload["state_token"])
    assert server.payload["state"]["phase"] == "setup_sow"
    assert server.payload["state"]["start_player_id"] == "player_three"


@needs_node
def test_reset_undoes_a_first_player_choice_before_confirmation(tmp_path: Path) -> None:
    """Naming a first player is an answer the page can discard before it posts the turn."""
    server = _opening(tmp_path)
    choices = _players_the_engine_would_accept(server)
    first, second = choices[:2]

    transcript = _run_script(
        server,
        [_name(first), _press("reset"), _name(second)],
        tmp_path,
        confirm=True,
    )

    assert transcript["resetShown"] == [False, True, False, True]
    assert sorted(transcript["offeredBoards"][2]) == choices
    assert transcript["posted"]["action_id"] == f"start_player_selection:{second}"

    server.apply(transcript["posted"]["action_id"], server.payload["state_token"])
    assert server.payload["state"]["phase"] == "setup_sow"
    assert server.payload["state"]["start_player_id"] == second


@needs_node
def test_start_player_selection_prompt_says_this_round(tmp_path: Path) -> None:
    server = _opening(tmp_path)
    transcript = _run_script(server, [], tmp_path)
    active = server.payload["state"]["active_player"]

    assert transcript["asking"][0] == [f"{active}: Choose first player for this round."]


@needs_node
def test_the_holder_can_name_themselves_by_pressing_their_own_board(tmp_path: Path) -> None:
    """Their own board is one of the ones lit, and pressing it is not a different path."""
    server = _opening(tmp_path)
    holder = server.payload["state"]["active_player"]

    transcript = _run_script(server, [_name(holder)], tmp_path, confirm=True)

    assert holder in transcript["offeredBoards"][0]
    assert transcript["posted"]["action_id"] == f"start_player_selection:{holder}"
    server.apply(transcript["posted"]["action_id"], server.payload["state_token"])
    assert server.payload["state"]["start_player_id"] == holder


@needs_node
def test_most_of_the_lit_boards_belong_to_players_who_are_not_acting(tmp_path: Path) -> None:
    """Which is what makes this a different mark from the one that says whose turn it is.

    Every previous question on this page lit the acting seat's own board, so "lit" and "acting"
    were never told apart. Here three of the four lit boards belong to players who are not acting
    at all, and if the page said this the way it says whose turn it is, it would be claiming four
    active players. The wash stays where it was and the boards carry a second, separate mark.
    """
    server = _opening(tmp_path)
    acting = server.payload["state"]["active_player"]
    transcript = _run_script(server, [], tmp_path)

    lit = transcript["offeredBoards"][0]
    assert len(lit) == 4
    assert acting in lit
    assert [player for player in lit if player != acting] != []
    # The stock question, which IS asked of one seat only, is not being asked here at all: the two
    # sets are kept apart rather than one being made to stand in for the other.
    assert transcript["askedSeats"][0] == []


def test_the_wash_and_the_seal_end_up_on_different_boards(tmp_path: Path) -> None:
    """THE PAYOFF, played rather than posed. Two boards lit, for two reasons, in a real position.

    The holder presses somebody else's board. From the next frame the marker is still theirs and
    the round is not, so the seal and the wash are on different seats -- the first position in this
    whole game where those two ever disagree, and the one thing a screenshot can show about what
    the First Player marker is for.
    """
    server = _opening(tmp_path)
    holder = server.payload["state"]["active_player"]
    given_to = next(
        player for player in _players_the_engine_would_accept(server) if player != holder
    )

    server.apply(f"start_player_selection:{given_to}", server.payload["state_token"])

    assert server.payload["state"]["first_player_marker"] == holder
    assert server.payload["state"]["active_player"] == given_to

    page = render_play_view_from_payload(server.payload)
    sealed = re.search(r'<g data-first-player-seal="true" data-player="(\w+)"', page)
    washed = re.findall(r'data-player="(\w+)"[^>]*data-active-seat="true"', page)
    assert sealed is not None and sealed.group(1) == holder
    assert washed == [given_to]
    assert sealed.group(1) != washed[0]


# ---------------------------------------------------------------------------------------------
# Two deliberate bugs, and the checks that catch them
# ---------------------------------------------------------------------------------------------


@needs_node
def test_asking_every_seat_for_the_stock_is_caught(tmp_path: Path) -> None:
    """MUTATION. Let any board answer, and the seat check has to notice.

    The bug is a plausible one: the script already has all four boards in hand, and dropping the
    comparison that picks out the active one leaves a page where any seat can spend another's
    turn choosing what another seat gets.
    """
    server = _reference_server()
    candidate = _asked(server, "tithe", "resource")[0]
    seat = SEATED_PLAYERS.index(server.payload["state"]["active_player"]) + 1

    every_seat = _run_script(
        server,
        _clicks_before_the_stock(server, candidate),
        tmp_path,
        mutate=lambda code: code.replace(
            "seat.getAttribute('data-active-seat') === 'true'", "seat !== null"
        ),
    )

    with pytest.raises(AssertionError, match="the wrong seat's board was asked"):
        _only_the_active_seat_is_asked(every_seat, seat)


def test_offering_the_mix_one_stock_at_a_time_is_caught(monkeypatch) -> None:
    """MUTATION. Filter the run name by name, and the canonical order becomes a fake rule.

    The tempting bug, and it looks like it should work: the pills already answer "which stock", the
    route is a tuple the filter walks element by element, so two clicks. What it misses is that the
    engine writes these runs canonically -- stone before silver before wheat -- so a player who
    presses silver first can no longer reach stone-and-silver, though it is one of the six. The
    spelling would become a constraint nobody wrote.

    Checked by walking to exactly that dead end and asking the engine whether the mix it excludes
    is legal. It is, which is the bug.
    """
    from tools import play_server

    whole = play_server._presented

    def one_at_a_time(action):
        """Each name in the run its own question, in the order the engine happens to write them."""
        steps = [(step, fields) for step, fields in whole(action) if step["kind"] != "combination"]
        for resolution, _verb, name in play_server.COUNTED_COMBINATION_STEPS:
            if action.resolution.value != resolution:
                continue
            for taken in tuple(getattr(action, name, ()) or ()):
                steps.append(({"kind": "resource", "value": taken}, (name,)))
        return steps

    server = _played_until_a_bonus_offers_a_choice(_reference_server())
    prefix, offered = sorted(_mix_groups(server).items())[0]
    both = next(
        mix for mix in offered if _counts(mix)["stone"] == 1 and _counts(mix)["silver"] == 1
    )
    assert both in _mixes_the_engine_allows(server, prefix), "stone and silver is not legal here"

    monkeypatch.setattr(play_server, "_presented", one_at_a_time)
    monkeypatch.setitem(
        play_server.UNRESOLVED_FIELD_TEXT,
        "alms_payment_silver",
        "how much silver to give as alms",
    )
    monkeypatch.setitem(
        play_server.UNRESOLVED_FIELD_TEXT,
        "alms_payment_wheat",
        "how much wheat to give as alms",
    )
    server._refresh()

    # Every split turn that starts its bonus by taking silver, and what it may take second.
    after_silver = {
        tuple(step["value"] for step in candidate["steps"])[len(prefix) + 1]
        for candidate in server.payload["turn_candidates"]
        if tuple(step["value"] for step in candidate["steps"])[: len(prefix)] == prefix
        and tuple(step["value"] for step in candidate["steps"])[len(prefix)] == "silver"
        and len(candidate["steps"]) > len(prefix) + 1
    }
    assert "stone" not in after_silver, (
        "pressing silver first still reached stone, so the split proves nothing"
    )


def _the_mixes_read_as_english(server) -> set[str]:
    """Every mix label on offer, checked for being a sentence rather than a spelling."""
    labels = {
        step["label"]
        for candidate in server.payload["turn_candidates"]
        for step in candidate["steps"]
        if step["kind"] == "combination" and step["label"].startswith("take")
    }
    assert labels, "no mix carried a label"
    for label in labels:
        assert not any(mark in label for mark in "()'\"=,"), f"{label!r} shows its spelling"
        assert "1 " not in label, f"{label!r} counts to one out loud"
    return labels


def test_naming_the_mix_by_its_spelling_instead_of_its_amounts_is_caught(monkeypatch) -> None:
    """MUTATION. Join the names instead of counting them, and the label becomes the data structure.

    ("stone", "silver") and ("silver", "stone") are the same bonus and the engine only ever writes
    the first, so joining looks safe enough. What it costs is the sentence: there is no way to say
    "take two stone" from a run of names without counting them first, so the button ends up reading
    "take stone, stone" -- which is the tuple, printed at a player, with the brackets taken off.
    """
    from tools import play_server

    whole = play_server._presented

    def as_written(action):
        steps = []
        for step, fields in whole(action):
            if step["kind"] == "combination" and step["label"].startswith("take"):
                taken = tuple(action.taxation_step2_resources or ())
                step = {
                    "kind": "combination",
                    "value": ",".join(taken),
                    "label": f"take {', '.join(taken)}" if taken else "take nothing",
                }
            steps.append((step, fields))
        return steps

    server = _played_until_a_bonus_offers_a_choice(_reference_server())
    _the_mixes_read_as_english(server)

    monkeypatch.setattr(play_server, "_presented", as_written)
    server._refresh()

    with pytest.raises(AssertionError, match="shows its spelling"):
        _the_mixes_read_as_english(server)


@needs_node
def test_lighting_the_whole_round_track_is_caught(tmp_path: Path) -> None:
    """MUTATION. Light every building while one is being asked for, and the offered set must notice.

    The tempting bug, and the one this affordance invites: the keys are already on the map and all
    twelve are within reach, so revealing them together is one line shorter than revealing the two
    that may actually be built. It would look like a map that had woken up rather than like a
    question, and every hex it lit but two would refuse the click it invited.
    """
    server = _played_until_a_construct_offers_a_choice(_reference_server())
    prefix, offered = sorted(_building_choices(server).items())[0]
    decisions = _engine_decisions(server)
    on_the_track = _buildings_on_the_track(server)

    every_one = _run_script(
        server,
        _clicks_to(server, decisions, list(prefix)),
        tmp_path,
        mutate=lambda code: code.replace(
            "mark(buildings, 'data-building-choice-key', offeredByKind(offered, 'building'));",
            "Array.prototype.forEach.call(buildings, function (key) {"
            " key.setAttribute('data-turn-offered',"
            " offeredByKind(offered, 'building').length ? 'true' : 'false'); });",
        ),
    )

    lit = sorted(value for value in every_one["offered"][-1] if value in on_the_track)
    assert lit != sorted(offered), "the mutation changed nothing, so it proves nothing"
    assert len(lit) == len(on_the_track)


@needs_node
def test_lighting_the_live_market_instead_of_the_answers_is_caught(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """MUTATION, on the engine, because that is the only place these two readings part.

    "The buildings the engine offers" and "the buildings live in the market" name the same set in
    every position the reference board reaches -- the engine's filter is liveness, ownership, an
    empty board slot and enough stone, and on this board the last three never bite while a building
    is live. So a page computing liveness for itself would pass every test above, and it would be
    computing a rule in the browser, which is the thing none of this is allowed to do.

    Narrowing what the engine will construct separates them. A page reading the survivors lights
    the one required building; a page reading the market goes on lighting both and offers a turn
    that does not exist.
    """
    from pilgrim.rules import transition

    server = _played_until_a_construct_offers_a_choice(_reference_server())
    _prefix, both = sorted(_building_choices(server).items())[0]
    assert len(both) == 2
    only_one = (sorted(both)[0],)

    monkeypatch.setattr(transition, "_constructible_building_ids", lambda **_kwargs: only_one)
    narrowed = PlayServer(("127.0.0.1", 0), REFERENCE)
    narrowed.state = server.state
    narrowed._refresh()

    assert _building_choices(narrowed) == {}, "the engine still offers a choice here"
    still_live = [
        building for building in narrowed.payload["state"]["building_market"] if building in both
    ]
    assert sorted(still_live) == sorted(both), "the market no longer holds the pair that separates"

    decisions = _engine_decisions(narrowed)
    prefix = next(
        _values_except(c["steps"], "building")
        for c in narrowed.payload["turn_candidates"]
        if any(step["kind"] == "building" for step in c["steps"])
    )
    transcript = _run_script(narrowed, _clicks_to(narrowed, decisions, prefix), tmp_path)
    on_the_track = _buildings_on_the_track(narrowed)
    assert [value for value in transcript["offered"][-1] if value in on_the_track] == list(only_one)


@needs_node
def test_lighting_the_chairs_instead_of_the_answers_is_caught(tmp_path: Path, monkeypatch) -> None:
    """MUTATION, on the engine rather than the page, because that is where the two readings part.

    "Every player the engine would accept" and "every occupied chair" name the same four names in
    every position this game can currently reach, so no board and no player count tells them apart:
    a page that lit the chairs would pass every test above. What tells them apart is changing the
    engine's answer and seeing whether the page changes with it.

    So the choosable set is narrowed to two, which is a rule this game does not have and does not
    need to have -- what is being checked is only that the lit boards came FROM there. A page
    reading the row of chairs goes on lighting four.
    """
    from pilgrim.rules import transition

    all_four = _players_the_engine_would_accept(_opening(tmp_path))
    assert len(all_four) == 4

    only_two = (PlayerId.PLAYER_ONE, PlayerId.PLAYER_THREE)
    monkeypatch.setattr(transition, "choosable_start_players", lambda state: only_two)
    narrowed = _opening(tmp_path)

    accepted = _players_the_engine_would_accept(narrowed)
    assert accepted == ["player_one", "player_three"]

    transcript = _run_script(narrowed, [], tmp_path)
    assert sorted(transcript["offeredBoards"][0]) == accepted


def test_setting_the_two_alms_amounts_one_at_a_time_is_caught(monkeypatch) -> None:
    """MUTATION. Offer the amounts separately, and the pairs check has to notice.

    The bug is the tempting one: two fields, so two questions. It reads as a smaller change than
    a whole new kind of step, and it quietly hands the page a rule to enforce -- which second
    amount may follow a given first -- along with every pairing the engine never offered.
    """
    from tools import play_server

    def independently(action):
        """Each amount its own question, as if they did not have to go together.

        Everything else is left alone -- same kind of step, same encoding, still answered beside
        the confirm summary. Only the going-together is taken out, so what catches it is the check
        against the engine's pairs rather than the shape of the page changing under it.
        """
        return [
            ({"kind": "combination", "value": f"{noun}={getattr(action, name)}"}, (name,))
            for resolution, _verb, fields in play_server.COMBINATION_STEPS
            if action.resolution.value == resolution
            for name, noun in fields
        ]

    monkeypatch.setattr(play_server, "_presented", independently)
    monkeypatch.setitem(
        play_server.UNRESOLVED_FIELD_TEXT,
        "tithe_resource",
        "which resource to tithe",
    )
    monkeypatch.setitem(
        play_server.UNRESOLVED_FIELD_TEXT,
        "taxation_step1_resource",
        "which resource to collect from Taxation",
    )
    server = _reference_server()

    with pytest.raises(AssertionError, match="not the pairs the engine allows"):
        _the_payments_offered_are_the_legal_pairs(server)


# ---------------------------------------------------------------------------------------------
# What the page will not do
# ---------------------------------------------------------------------------------------------


def test_a_turn_the_page_cannot_finish_is_refused_with_the_open_fields_named(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answering everything the page asks can still leave several actions standing.

    `FullTurnAction` carries some forty optional fields and this page presents a handful. When the
    rest disagree, the honest answer is to say which -- picking one, or the first, or the simplest,
    would be the page quietly making a decision the rules give to the player. The named fields are
    the backlog, worked out from the position rather than remembered.
    """
    with _one_field_gone_unasked(monkeypatch):
        server = _played_until_the_page_must_refuse(_played_through_setup(_served(tmp_path)))
        open_ended = [c for c in server.payload["turn_candidates"] if c["unresolved"]]
        assert open_ended, "no ambiguous turn on this board, so nothing was exercised"

    for candidate in open_ended:
        assert candidate["action_id"] is None, "an undecided turn was given something to submit"
        assert candidate["summary"] is None, "an undecided turn was described as if it were one"
        assert candidate["variants"] > 1
        assert all(isinstance(name, str) and name for name in candidate["unresolved"])
        assert candidate["unresolved_text"] == [
            play_server.UNRESOLVED_FIELD_TEXT[name] for name in candidate["unresolved"]
        ]

    # The fields named are really the ones the survivors differ on, checked against the actions.
    candidate = open_ended[0]
    wanted = [step["value"] for step in candidate["steps"]]
    actions = list(legal_actions(server.state, server.config))
    (
        offer_hire_by_action_id,
        hire_payment_buildings_by_action_id,
    ) = _offer_flags_by_action_id(
        actions,
        state=server.state,
        config=server.config,
    )
    members = [
        action
        for action in actions
        if _values(
            _engine_steps(
                action,
                config=server.config,
                offer_hire=offer_hire_by_action_id[action_id(action)],
                hire_payment_buildings=hire_payment_buildings_by_action_id[action_id(action)],
            )
        )
        == wanted
    ]
    assert len(members) == candidate["variants"]
    for name in candidate["unresolved"]:
        assert len({getattr(member, name) for member in members}) > 1
    # A field the page does present cannot come back as unresolved: answering it is what put this
    # candidate in its own group, so the refusal is always about something genuinely unbuilt.
    presented = {"taxation_step1_resource", *ALMS_PAIR}
    assert presented.isdisjoint(candidate["unresolved"])
    # And the field taken off the page is the one that came back, which is the refusal doing its
    # job rather than naming whatever happened to be handy.
    assert UNPRESENTED in candidate["unresolved"]


@needs_node
def test_an_undecided_turn_offers_no_way_to_commit_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal has to be structural: there is no button on that panel to press."""
    with _one_field_gone_unasked(monkeypatch):
        server = _played_until_the_page_must_refuse(_played_through_setup(_served(tmp_path)))
        candidates = server.payload["turn_candidates"]
        index = next(i for i, c in enumerate(candidates) if c["unresolved"])
        target = [step["value"] for step in candidates[index]["steps"]]
        clicks = _clicks_to(server, _engine_decisions(server), target)
        transcript = _run_script(server, clicks, tmp_path, confirm=True)
    assert transcript["shownPanel"][-1] == index, "the undecided turn's panel was not the one shown"
    assert transcript["confirmable"] is False, "an undecided turn had a commit button"
    assert transcript["posted"] is None


def _cubes_at(page: str, position_index: int, player_id: str) -> int:
    """How many of one seat's cubes are standing on one space of the drawn board."""
    wheel = page[page.index('<div class="panel p-action">') :]
    start = wheel.index(f'data-board-position-index="{position_index}"')
    space = wheel[start : wheel.index("<g data-duty=", start + 1)]
    return len(re.findall(rf'data-player="{player_id}"(?![^>]*opacity="0")', space))


def test_a_stale_state_token_is_refused_and_changes_nothing(tmp_path: Path) -> None:
    """A submission decided against a board that has since moved is refused, not reinterpreted."""
    server = _served(tmp_path)
    with _running(server) as base:
        candidate = server.payload["turn_candidates"][0]
        stale = server.payload["state_token"]
        assert _post(base, candidate["action_id"], stale)[0] == 200

        before = _get_json(base, "/state.json")
        status, body = _post(base, server.payload["turn_candidates"][0]["action_id"], stale)
        after = _get_json(base, "/state.json")

    assert status == 409
    assert json.loads(body)["applied"] is False
    assert after == before


def test_an_action_id_that_is_not_legal_here_is_refused(tmp_path: Path) -> None:
    """Looked up in the legal set, never rebuilt from what arrived."""
    server = _served(tmp_path)
    with _running(server) as base:
        before = _get_json(base, "/state.json")
        status, body = _post(base, "setup_sow:sow:0:8->7->6->5->4", server.payload["state_token"])
        after = _get_json(base, "/state.json")

    assert status == 422
    assert json.loads(body)["applied"] is False
    assert after == before


def _script_carried_by(page: str) -> str:
    """The turn script as the page actually carries it, opening and closing tags and all."""
    found = re.search(r"<script>.*?</script>", page, re.S)
    assert found is not None, "the page carried no turn script"
    return found.group(0)


def _the_script_is_the_template_with_only_its_values_filled_in(page: str, payload: dict) -> None:
    """What lets the greps below read the template instead of the page.

    They grep `_TURN_SCRIPT`, which is the code as written, with no data in it at all -- so nothing
    has to be subtracted before searching and nothing can be over-subtracted by accident. That is
    only sound while the template IS the whole of the code, and this is what says so: the script on
    the page has to be the template with its data placeholders filled in and nothing else done to
    it. Anything injected by a second route breaks this equality, and the guard reports that its
    own coverage has stopped being what it claims rather than quietly checking less. The template
    carries the action candidates, committed turn steps, resolved building abilities, used-building
    set, resolution-window flag, and server-decided phase-column scope as separate data.
    """
    _owned_reversals, family_arrow_templates = render_play_view._route_family_arrow_templates(
        payload.get("turn_candidates") or [],
        payload.get("building_abilities") or [],
        render_play_view.load_duty_wheel_layout(),
    )
    expected = (
        render_play_view._TURN_SCRIPT.replace(
            "__CANDIDATE_WIRE__",
            json.dumps(
                render_play_view._compact_turn_candidates_for_page(
                    payload.get("turn_candidates") or []
                )
            ),
        )
        .replace("__FAMILIES__", json.dumps(payload.get("families") or []))
        .replace("__AUTO_FAMILY_INDEXES__", json.dumps(payload.get("auto_family_indexes") or []))
        .replace("__TURN_STEPS__", json.dumps(payload.get("turn_steps") or []))
        .replace("__BUILDING_ABILITIES__", json.dumps(payload.get("building_abilities") or []))
        .replace("__FAMILY_ARROW_TEMPLATES__", json.dumps(family_arrow_templates))
        .replace(
            "__BUILDING_ABILITY_WINDOWS__",
            json.dumps(payload.get("building_ability_windows") or {}),
        )
        .replace(
            "__BUILDING_ABILITY_WINDOW__",
            json.dumps(
                "end"
                if payload.get("state", {}).get("turn_progress", {}).get("resolution_committed")
                else "beginning"
            ),
        )
        .replace(
            "__USED_BUILDINGS__",
            json.dumps(payload.get("state", {}).get("turn_progress", {}).get("used_buildings", [])),
        )
        .replace(
            "__RESOLUTION_COMMITTED__",
            json.dumps(
                payload.get("state", {}).get("turn_progress", {}).get("resolution_committed", False)
            ),
        )
        .replace(
            "__PHASE_COLUMN_SCOPE__",
            json.dumps(payload.get("phase_column", {}).get("scope", "inactive")),
        )
        .replace("__TOKEN__", json.dumps(payload.get("state_token", "")))
        .replace(
            "__ALMS_POSITION_TARGETS__",
            json.dumps(
                render_play_view.disc_targets(
                    render_play_view.load_alms_table_layout(),
                    render_play_view.alms_rules(render_play_view.load_alms_config()),
                    payload["state"]["active_player"],
                )
            ),
        )
    )
    assert _script_carried_by(page) == expected, (
        "the page's script is not the template with its data placeholders filled in, so grepping "
        "the template no longer covers everything that reaches the browser"
    )


def test_the_page_says_a_seat_by_colour_and_never_by_the_engines_name(tmp_path: Path) -> None:
    """Ids remain in attributes, but visible seat names stay colour words.

    The rule names colours. Player ids are mapping, and this mapping has already changed once, so a
    page that says ids out loud would be saying implementation detail where table language belongs.

    The check is on text nodes only. The ids are all over this page in attributes and have to be,
    which is asserted first: a guard that could be satisfied by removing them from everywhere would
    be a guard against keeping the seam.
    """
    server = _played_through_setup(_served(tmp_path))
    page = render_play_view_from_payload(server.payload)

    for engine_id in SEAT_COLOURS:
        assert engine_id in page, f"{engine_id} has left the page entirely, attributes and all"

    said = _out_loud(page)
    offenders = [
        (where, text, engine_id)
        for where, text in said
        for engine_id in SEAT_COLOURS
        if engine_id in text
    ]
    assert not offenders, "the page said the engine's name for a seat out loud: " + "; ".join(
        f"{engine_id!r} in {where} -- {text!r}" for where, text, engine_id in offenders[:4]
    )

    # And it is saying something: a page that had stopped naming seats at all would pass the check
    # above by being silent.
    spoken = " ".join(text for _, text in said)
    assert any(colour in spoken for colour in SEAT_COLOURS.values())


def test_the_seat_a_page_names_is_the_one_the_player_is_looking_at(tmp_path: Path) -> None:
    """The colour is a lookup on the id, so the third board is Blue wherever it is mentioned.

    Named against the board's own markup rather than against a list written here, so the page and
    the page's words cannot drift: the seat that carries `data-player="player_three"` is the one the
    sentence has to call Blue.
    """
    # Before the opening decision rather than after it, because that decision is the one place a
    # seat is named four times over -- once per board a player may point at.
    server = PlayServer(("127.0.0.1", 0), _generated(tmp_path))
    page = render_play_view_from_payload(server.payload)

    third = re.search(r'data-player-seat="3" data-player="(\w+)"', page)
    assert third, "no third board on the page"
    assert third.group(1) == "player_three", "the third chair is not who it was"
    assert SEAT_COLOURS[third.group(1)] == "Blue"

    summaries = re.findall(r'<div class="turn-summary">([^<]*)</div>', page)
    assert "Red chose Blue to begin this round." in summaries
    assert not any("player_" in summary for summary in summaries)

    # Choosing that board, the transcript names both seats by colour and the header follows.
    blue = next(
        candidate
        for candidate in server.payload["turn_candidates"]
        if any(step["value"] == "player_three" for step in candidate["steps"])
    )
    server.apply(blue["action_id"], server.payload["state_token"])
    after = render_play_view_from_payload(server.payload)
    events = re.findall(r'<div class="log-event">([^<]*)</div>', after)
    assert any("chose Blue" in line for line in events), events
    assert ("Status", "Setup - 0 of 4 sown") in _header_of(after)


def _header_of(page: str) -> list[tuple[str, str]]:
    """The one status sentence in the box header."""
    return [("Status", text) for text in re.findall(r'data-status-line="([^"]+)"', page)]


def test_a_box_hired_from_another_seat_names_that_seat_by_colour() -> None:
    """The one offer that names a player, put to the page directly.

    `_played_until_a_box_is_offered` reaches a position offering your own box and the market's, and
    never one belonging to a neighbour, so the walk cannot exercise the case that actually carries
    a seat. Handing the page the step it would build is what makes this checkable at all -- and it
    is the case that matters, since a box hired from a neighbour is paid to that neighbour.
    """
    offer = {
        "kind": "combination",
        "value": "player_four",
        "label": "hire the Confession Box from player_four",
        "prompt": "Choose one of these.",
    }
    payload = {
        "turn_candidates": [{"steps": [offer], "action_id": "x", "summary": "s", "variants": 1}]
    }
    page = render_play_view.render_turn_panel(payload)

    assert ">hire the Confession Box from White<" in page
    # The value it is answered by is untouched: the script routes on the engine's name.
    assert 'data-combination-key="player_four"' in page


def test_saying_the_engines_name_for_a_seat_is_caught(tmp_path: Path, monkeypatch) -> None:
    """MUTATION. Put the ids back and the guard has to notice, and say where it found one."""
    monkeypatch.setattr(render_play_view, "say", lambda value: escape(str(value)))
    server = _played_through_setup(_served(tmp_path))
    page = render_play_view_from_payload(server.payload)

    offenders = [
        (where, text)
        for where, text in _out_loud(page)
        for engine_id in SEAT_COLOURS
        if engine_id in text
    ]
    assert offenders, "the guard would not have noticed the ids coming back"
    assert any("log-value" in where or "log-event" in where for where, _ in offenders), offenders


def test_the_script_may_filter_and_reveal_and_nothing_else(tmp_path: Path) -> None:
    """No rule may be computed in the browser, so there is nowhere for a second one to live.

    Adjacency, route length and legality are the engine's, and every turn the page can express came
    from it whole. This greps for a second implementation rather than trusting the intent.

    Read off the TEMPLATE rather than the rendered page. Only code can implement a rule, and the
    template is exactly the code: the candidates are the engine's own list arriving as data, and
    they carry summaries and prompts written to be read by a player. One of those prompts says the
    word "route", because that is what the space being asked for is part of -- a page forbidden to
    name the thing it is asking about could not ask. Subtracting the data from the rendered page
    would work, but it fails open: whatever such a rule over-strips goes silently unchecked.
    """
    server = _played_through_setup(_served(tmp_path))
    page = render_play_view_from_payload(server.payload)

    # The template is the whole of the code, and these assertions are what make that a fact
    # rather than an assumption the greps rest on.
    assert render_play_view._TURN_SCRIPT.count("__CANDIDATE_WIRE__") == 1
    assert render_play_view._TURN_SCRIPT.count("__FAMILIES__") == 1
    assert render_play_view._TURN_SCRIPT.count("__AUTO_FAMILY_INDEXES__") == 1
    assert render_play_view._TURN_SCRIPT.count("__TURN_STEPS__") == 1
    assert render_play_view._TURN_SCRIPT.count("__BUILDING_ABILITIES__") == 1
    assert render_play_view._TURN_SCRIPT.count("__FAMILY_ARROW_TEMPLATES__") == 1
    assert render_play_view._TURN_SCRIPT.count("__USED_BUILDINGS__") == 1
    assert render_play_view._TURN_SCRIPT.count("__RESOLUTION_COMMITTED__") == 1
    assert render_play_view._TURN_SCRIPT.count("__PHASE_COLUMN_SCOPE__") == 1
    assert render_play_view._TURN_SCRIPT.count("__TOKEN__") == 1
    assert render_play_view._TURN_SCRIPT.count("__ALMS_POSITION_TARGETS__") == 1
    _the_script_is_the_template_with_only_its_values_filled_in(page, server.payload)

    # Comments are stripped: prose about what the code does not do is not the code doing it, and a
    # grep that cannot tell them apart would be satisfied by deleting the explanation.
    code = re.sub(r"/\*.*?\*/", "", render_play_view._TURN_SCRIPT, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)

    for forbidden in ("adjacen", "neighbour", "neighbor", "legal", "sqrt", "route"):
        assert forbidden not in code, f"the script looks like it computes {forbidden!r}"
    # Arithmetic is now expected for arrangement deltas on the board, and only there.
    # No colour and no geometry either, which is the rule the seal established.
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", code)
    assert not re.search(r"\b(stroke|fill|translate)\s*[=:]", code)
    # It may say only these things about the board and the panel.
    assert "setAttribute('data-turn-start-candidate'" in code
    assert "setAttribute('data-turn-skip-candidate'" in code
    assert "setAttribute('data-turn-duty-candidate'" in code
    assert "setAttribute('data-turn-shown'" in code
    assert "setAttribute('data-turn-stage-state'" in code
    assert "setAttribute('data-turn-stage-current'" in code
    # And it may not know what any step is ABOUT. A step says how it is answered and the script
    # routes on that; the day it can tell a tithe's stock from a taxation's by name is the day the
    # next field needs the script taught about it rather than merely published to it. The whole
    # page is searched, candidates and all, because a field name reaching the browser as data is a
    # field name the browser can start to depend on.
    for field in (
        "tithe_resource",
        "taxation_step1_resource",
        "chosen_start_player",
        "construct_building_id",
        "sow_route_omitted_location",
        "allocation_moves",
        "ordination_steps",
        *ALMS_PAIR,
    ):
        assert field not in page, f"the page was told about the field {field!r}"


def test_a_rule_computed_in_the_script_is_caught(tmp_path: Path, monkeypatch) -> None:
    """MUTATION. Work out what lies next to what, and the greps have to find it.

    Patched into the template, so the page carries it too and the equality above still holds. That
    is the point: this is a rule genuinely reaching the browser through the ordinary route, and the
    greps are what catch it rather than the coverage check.
    """
    monkeypatch.setattr(
        render_play_view,
        "_TURN_SCRIPT",
        render_play_view._TURN_SCRIPT.replace(
            "  var chosen = [];",
            "  var chosen = [];\n  var adjacent = { 0: [1, 8], 1: [0, 2] };",
        ),
    )

    with pytest.raises(AssertionError, match="looks like it computes"):
        test_the_script_may_filter_and_reveal_and_nothing_else(tmp_path)


def test_a_second_thing_injected_into_the_script_is_caught(tmp_path: Path, monkeypatch) -> None:
    """MUTATION. Write into the script from somewhere else, and the coverage claim must break.

    This is the failure the whole arrangement guards against: greps that read the template prove
    nothing about a page whose script is not only the template. Here the render puts one more line
    in, the template knows nothing about it, and the greps would sail past it -- so the equality
    has to be what notices, and it has to notice even though the smuggled line is innocent.
    """
    whole_page = render_play_view.render_play_view_html

    def with_something_smuggled_in(*args, **kwargs):
        page = whole_page(*args, **kwargs)
        return page.replace("  var chosen = [];", '  var chosen = [];\n  var SEAT = "player_one";')

    monkeypatch.setattr(render_play_view, "render_play_view_html", with_something_smuggled_in)

    server = _played_through_setup(_served(tmp_path))
    page = render_play_view.render_play_view_from_payload(server.payload)
    assert 'var SEAT = "player_one";' in page, "the mutation reached nothing, so nothing is tested"

    with pytest.raises(AssertionError, match="no longer covers everything that reaches"):
        _the_script_is_the_template_with_only_its_values_filled_in(page, server.payload)


# ---------------------------------------------------------------------------------------------
# What the script reaches for, a player can hit
# ---------------------------------------------------------------------------------------------

# SVG paints; HTML does not. Only a painted shape is hit tested, and only over the area it paints,
# so these are the tags the rule below has anything to say about. A container paints nothing itself
# and is reached through whatever it holds.
_SVG_SHAPES = frozenset(
    {"rect", "circle", "ellipse", "line", "path", "polygon", "polyline", "text", "image"}
)
_SVG_CONTAINERS = frozenset({"svg", "g", "a", "use"})


class _Spoken(HTMLParser):
    """Every run of text the page shows a reader, with the element it sits in.

    Scoped to text nodes, and that scope is the point rather than a convenience. The page is full
    of engine player ids in ATTRIBUTES -- `data-player`, `data-seat-choice-key`, the candidates the
    script routes on -- and they have to stay there, because the script routes on them and the seam
    is defined in the engine's names. A guard that searched the whole page could only be satisfied
    by pulling the seam apart, so it would be a guard against the wrong thing.

    `script` and `style` are skipped for the same reason: their contents are data and rules, not
    words. The title is not skipped -- a tab is somewhere a reader looks.
    """

    QUIET = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.spoken: list[tuple[str, str]] = []
        self._quiet = 0
        self._where = "#document"

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.QUIET:
            self._quiet += 1
        found = dict(attrs)
        marks = " ".join(f"{k}={v!r}" for k, v in found.items() if k in ("class", "id"))
        self._where = f"<{tag} {marks}>" if marks else f"<{tag}>"

    def handle_endtag(self, tag: str) -> None:
        if tag in self.QUIET and self._quiet:
            self._quiet -= 1

    def handle_data(self, data: str) -> None:
        if self._quiet or not data.strip():
            return
        self.spoken.append((self._where, data.strip()))


def _out_loud(page: str) -> list[tuple[str, str]]:
    parser = _Spoken()
    parser.feed(page)
    return parser.spoken


class _Markup(HTMLParser):
    """The page as a tree, because hit testing is a question about ancestry.

    A `<g>` is reached through its children, so an element cannot be judged on its own attributes
    alone and a flat scan of tags would have to guess.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict = {"tag": "#document", "attrs": {}, "children": []}
        self._open = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self._open[-1]["children"].append(node)
        self._open.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._open[-1]["children"].append({"tag": tag, "attrs": dict(attrs), "children": []})

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._open) - 1, 0, -1):
            if self._open[index]["tag"] == tag:
                del self._open[index:]
                return


def _every_element(node: dict):
    yield node
    for child in node["children"]:
        yield from _every_element(child)


def _class_fills(page: str) -> dict[str, str]:
    """What fill, if any, this page's own stylesheets give each class.

    Read off the page rather than assumed, because the wheel's spaces are filled from a rule and
    not from an attribute -- and a check that only looked at attributes would call the one
    affordance that has always worked a failure.
    """
    fills: dict[str, str] = {}
    for sheet in re.findall(r"<style[^>]*>(.*?)</style>", page, re.S):
        for selector, body in re.findall(r"([^{}]*)\{([^{}]*)\}", sheet):
            declared = re.search(r"(?<![-\w])fill\s*:\s*([^;}]+)", body)
            if declared is None:
                continue
            for name in re.findall(r"\.([A-Za-z0-9_-]+)", selector):
                fills[name] = declared.group(1).strip()
    return fills


def _paints(node: dict, fills: dict[str, str]) -> bool:
    """Whether a shape is hit anywhere inside it, rather than only along its outline."""
    if node["attrs"].get("pointer-events") == "all":
        return True
    fill = node["attrs"].get("fill")
    if fill is not None and fill != "none":
        return True
    return any(
        fills.get(name, "none") != "none" for name in (node["attrs"].get("class") or "").split()
    )


def _is_hit_testable(node: dict, fills: dict[str, str]) -> bool:
    if node["tag"] in _SVG_SHAPES:
        return _paints(node, fills)
    if node["tag"] in _SVG_CONTAINERS:
        return any(_is_hit_testable(child, fills) for child in node["children"])
    return True


def _queried_attributes() -> list[str]:
    """Every attribute the script goes looking for, read off the script itself.

    Off the script rather than out of a list kept here, because a list kept here is one somebody
    has to remember to add to -- and the affordance that gets forgotten is exactly the one that
    ships unclickable. A new `querySelectorAll` is covered the moment it is written.
    """
    found = sorted(
        set(re.findall(r"querySelector(?:All)?\(.\[([a-z-]+)", render_play_view._TURN_SCRIPT))
    )
    assert found, "no attributes were read out of the script, so this test checks nothing"
    return found


def test_everything_the_script_reaches_for_can_be_hit_where_it_looks_solid() -> None:
    """An affordance a player cannot click in the middle is not an affordance.

    A shape painted `fill="none"` is hit tested ON ITS STROKE and nowhere else. It still draws as a
    box, still lights up, still says "press me" -- and a click a few pixels inside the line goes
    straight through it to whatever is behind. That is what the seat key did: every board on the
    page looked selectable and only its 6px border was.

    WHAT THIS CANNOT SEE. Draw order and overlap. An element that paints its whole area is still
    unreachable if something opaque is drawn on top of it, and nothing here knows what covers what
    -- that needs a real browser and a real click. Hidden-choice-key pointer gates are asserted
    separately below; what still needs eyes is one visible key covering another visible target.
    """
    server = _reference_server()
    page = render_play_view_from_payload(server.payload)
    tree = _Markup()
    tree.feed(page)
    fills = _class_fills(page)

    unreachable = []
    for attribute in _queried_attributes():
        if (
            attribute in {"data-turn-step-direction", "data-turn-step-amount"}
            or attribute.startswith("data-piety-choice-")
            or attribute.startswith("data-turn-step-hire-")
        ) and not server.payload.get("turn_steps"):
            continue
        if attribute in {
            "data-ordination-action",
            "data-ordination-unavailable-reason",
        } and not any(
            step["kind"] == "ordination"
            for candidate in server.payload["turn_candidates"]
            for step in candidate["steps"]
        ):
            continue
        carrying = [node for node in _every_element(tree.root) if attribute in node["attrs"]]
        # Every one of them has to be ON the page as well as reachable. An attribute the script
        # asks for and the renderer never draws would otherwise pass this test by being absent,
        # which is the same silence the seat key hid in.
        assert carrying, f"the script looks for [{attribute}] and the page draws none"
        unreachable += [
            f'[{attribute}="{node["attrs"][attribute]}"] is a <{node["tag"]}> hit only on its edge'
            for node in carrying
            if not _is_hit_testable(node, fills)
        ]

    assert not unreachable, (
        "affordances a click in the middle falls straight through:\n"
        + "\n".join(f"  {line}" for line in unreachable)
    )


def _hidden_choice_key_rules_drop_pointer_events(page: str) -> None:
    """Any rule hiding a whole-board/map choice key must also make it non-interactive."""
    selectors = (
        '[data-seat-choice-key][data-turn-offered="false"]',
        '[data-building-choice-key][data-turn-offered="false"]',
    )
    for selector in selectors:
        match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", page, re.S)
        assert match is not None, f"no hide rule for {selector}"
        body = " ".join(match.group(1).split())
        assert "visibility: hidden" in body, f"{selector} hide rule stopped hiding"
        assert "pointer-events: none" in body, f"{selector} hide rule still takes clicks"


def test_each_hidden_choice_key_rule_also_disables_pointer_events() -> None:
    server = _reference_server()
    page = render_play_view_from_payload(server.payload)
    _hidden_choice_key_rules_drop_pointer_events(page)


def _opened(tmp_path: Path):
    """A generated game at the moment it opens, before anything has been answered."""
    server = PlayServer(("127.0.0.1", 0), _generated(tmp_path))
    assert server.payload["state"]["phase"] == "start_player_selection"
    return server


def _visible_cubes(snapshot: dict, position: str, player_id: str) -> int:
    return sum(
        1 for cube in snapshot[position] if cube["player"] == player_id and cube["opacity"] != "0"
    )


def _exactly_one_prompt_is_visible(transcript) -> None:
    for point in transcript["asking"]:
        assert len(point) <= 1, f"two questions were put at once: {point}"


def _reset_waits_for_a_followed_arrow(transcript) -> None:
    assert transcript["resetShown"][0] is False, "reset lit before any arrow was followed"
    assert transcript["resetShown"][-1] is True, "reset stayed dark after an arrow was followed"


def _snapshot_at(transcript: dict, index: int) -> dict:
    return {
        "offered": transcript["offered"][index],
        "chosen": transcript["chosen"][index],
        "shown": transcript["shownPanel"][index],
        "asking": transcript["asking"][index],
        "startCandidates": transcript["startCandidates"][index],
        "startRelocationCandidates": transcript["startRelocationCandidates"][index],
        "skipCandidates": transcript["skipCandidates"][index],
        "dutyCandidates": transcript["dutyCandidates"][index],
        "reset": transcript["resetShown"][index],
        "counter": transcript["counterShown"][index],
        "controls": transcript["controls"][index],
        "controlActive": transcript["controlActive"][index],
        "cubes": transcript["cubes"][index],
        "arrangements": transcript["arrangements"][index],
        "overflow": transcript["overflow"][index],
    }


def _previewed_destinations(before: dict, after: dict, player_id: str) -> Counter:
    """Where preview put cubes down, as the positive column deltas for one seat."""
    shown: Counter = Counter()
    for position in before:
        gained = _visible_cubes(after, position, player_id) - _visible_cubes(
            before, position, player_id
        )
        if gained > 0:
            shown[position] = gained
    return shown


def _destinations_named_by(route_edges: list[str]) -> Counter:
    """Where the chosen route says cubes were placed, read straight off the edge answers."""
    return Counter(edge.split("->", 1)[1] for edge in route_edges)


def _assert_preview_matches_route(
    before: dict, after: dict, player_id: str, route_edges: list[str]
) -> None:
    expected = _destinations_named_by(route_edges)
    shown = _previewed_destinations(before, after, player_id)
    if shown == expected:
        return
    unexpected = sorted(
        position for position in shown if shown[position] > expected.get(position, 0)
    )
    missing = sorted(
        position for position in expected if expected[position] > shown.get(position, 0)
    )
    note = []
    if unexpected:
        note.append(f"unexpected cube at {', '.join(unexpected)}")
    if missing:
        note.append(f"missing cube at {', '.join(missing)}")
    assert shown == expected, (
        "preview diverged from the route the answers named: "
        + "; ".join(note)
        + f"; expected {dict(expected)}, got {dict(shown)}"
    )


SETUP_SWEEP_SEEDS = (7, 99)


@needs_node
def test_setup_sow_is_asked_with_arrows_and_a_counter(tmp_path: Path) -> None:
    server = _served(tmp_path)
    assert server.payload["state"]["phase"] == "setup_sow"
    transcript = _run_script(server, [], tmp_path)

    _exactly_one_prompt_is_visible(transcript)
    assert transcript["asking"][0] == [
        f"{server.payload['state']['active_player']}: Choose a space to lift acolytes from."
    ], "setup sow did not name the pickup question it was asking"
    assert transcript["offered"][0] == [0], "setup sow did not offer the City pickup"
    assert transcript["counterShown"][0] == [], "the route counter appeared before pickup"
    assert transcript["resetShown"][0] is False, "reset lit before any acolytes were picked up"

    after_pickup = _run_script(server, [_at(0)], tmp_path)
    assert after_pickup["asking"][-1] == [
        f"{server.payload['state']['active_player']}: Follow an arrow."
    ], "setup sow did not name the route question after pickup"
    assert after_pickup["offered"][-1] == ["city->north", "city->south"], (
        f"setup sow offered {transcript['offered'][0]} instead of the two City arrows"
    )
    assert after_pickup["counterShown"][-1] == ["5"], "the counter did not open on five in hand"
    assert after_pickup["resetShown"][-1] is True, "reset stayed dark after pickup"
    assert after_pickup["controls"][-1]["confirm"] == "false", "confirm lit before a turn was settled"
    assert after_pickup["controls"][-1]["action"] == "false"
    assert after_pickup["controls"][-1]["tithe"] == "false"
    assert after_pickup["shownPanel"][-1] == -1, "nothing was settled, so no summary was up"


@needs_node
def test_reset_lights_only_after_following_an_arrow(tmp_path: Path) -> None:
    server = _served(tmp_path)
    transcript = _run_script(server, [_at(0), _follow("city->north")], tmp_path)
    _reset_waits_for_a_followed_arrow(transcript)


@needs_node
def test_one_question_is_asked_at_a_time_and_it_is_the_one_still_open(tmp_path: Path) -> None:
    """When the panel does ask, it asks one open panel question at a time."""
    server = _played_through_setup(_served(tmp_path))
    decisions = _engine_decisions(server)
    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if any(
            step["kind"] == "resolution" and step["value"].startswith("produce_")
            for step in c["steps"]
        )
    )
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])
    transcript = _run_script(server, clicks, tmp_path)

    asked = [point for point in transcript["asking"] if point]
    assert asked, "the panel never asked anything during a whole turn"
    _exactly_one_prompt_is_visible(transcript)
    # And a settled turn has a summary to read instead, so the asking stops rather than leaving a
    # question standing over a decision that has been made.
    for asking, shown in zip(transcript["asking"], transcript["shownPanel"], strict=True):
        if shown != -1:
            assert asking == [], f"a settled turn was still asking {asking}"


def test_turn_prompt_lines_name_the_acting_seat_by_colour(tmp_path: Path) -> None:
    """Prompt text says the acting seat by colour, never by engine id."""
    server = _played_through_setup(_served(tmp_path))
    page = render_play_view_from_payload(server.payload)
    spoken = re.findall(r'<div class="turn-prompt"[^>]*>([^<]*)</div>', page)
    active = server.payload["state"]["active_player"]
    expected = f"{SEAT_COLOURS[active]}:"

    assert spoken, "no turn prompt lines were drawn"
    assert all(line.startswith(expected) for line in spoken), spoken
    assert not any("player_" in line for line in spoken), spoken


@needs_node
def test_reset_restores_every_cube_to_its_opening_opacity(tmp_path: Path) -> None:
    """Reset returns to the same opening setup-sow snapshot the page started from."""
    server = _served(tmp_path)
    transcript = _run_script(server, [_at(0), _follow("city->north")], tmp_path, reset=True)
    opening = _snapshot_at(transcript, 0)

    assert transcript["afterReset"] == opening, (
        "reset did not return to the opening setup-sow snapshot"
    )


@needs_node
def test_preview_cubes_follow_the_non_first_branch_back_through_the_city(
    tmp_path: Path,
) -> None:
    """The preview lands cubes where the chosen arrows point, including the City."""
    server = _served(tmp_path)
    active = server.payload["state"]["active_player"]
    route = [
        "city->north",
        "north->north_east",
        "north_east->east",
        "east->city",
        "city->south",
    ]
    clicks = [
        _at(0),
        _follow("city->north"),
        _follow("north->north_east"),
        _follow("north_east->east"),
        _follow("east->city"),
        _follow("city->south"),
    ]
    transcript = _run_script(server, clicks, tmp_path)
    before = transcript["cubes"][1]
    after = transcript["cubes"][-1]

    assert transcript["offered"][5] == ["city->north", "city->south"]
    assert clicks[-1]["value"] == transcript["offered"][5][1], (
        "the branch taken was not the non-first one"
    )
    _assert_preview_matches_route(before, after, active, route)
    assert _visible_cubes(after, "north", active) == 1
    assert _visible_cubes(after, "north_east", active) == 1
    assert _visible_cubes(after, "east", active) == 1
    assert _visible_cubes(after, "city", active) == 1
    assert _visible_cubes(after, "south", active) == 1
    assert _visible_cubes(after, "south_east", active) == 0


@needs_node
@pytest.mark.parametrize("seed", SETUP_SWEEP_SEEDS)
def test_after_any_setup_answers_preview_matches_the_route_those_answers_name(
    tmp_path: Path,
    seed: int,
) -> None:
    """For every setup route in the sweep, placements match the chosen route's destinations."""
    server = _served(tmp_path, seed=seed)
    active = server.payload["state"]["active_player"]
    decisions = _engine_decisions(server)

    assert decisions, f"seed {seed} had no setup-sow routes to check"
    for route in decisions:
        route_edges = [step["value"] for step in route if step["kind"] == "edge"]
        clicks = _clicks_to(server, decisions, _values(route))
        transcript = _run_script(server, clicks, tmp_path)
        _assert_preview_matches_route(
            transcript["cubes"][1], transcript["cubes"][-1], active, route_edges
        )


@needs_node
def test_after_normal_turn_route_answers_preview_matches_the_named_route(tmp_path: Path) -> None:
    """The same route guard in a normal turn, where cubes are already out on the wheel."""
    server = _played_through_setup(_served(tmp_path))
    active = server.payload["state"]["active_player"]
    decisions = _engine_decisions(server)
    route = next(steps for steps in decisions if any(step["kind"] == "edge" for step in steps))
    route_answers = [step["value"] for step in route if step["kind"] in {"origin", "edge"}]
    route_edges = [step["value"] for step in route if step["kind"] == "edge"]
    transcript = _run_script(server, _clicks_to(server, decisions, route_answers), tmp_path)

    _assert_preview_matches_route(
        transcript["cubes"][0], transcript["cubes"][-1], active, route_edges
    )


@needs_node
def test_taken_origin_clears_its_ring_and_duty_candidates_match_the_engine_offer(
    tmp_path: Path,
) -> None:
    """After lifting, the origin is unmarked and duty candidates come straight from candidates."""
    server = _played_through_setup(_served(tmp_path))
    decisions = _engine_decisions(server)
    opening = _run_script(server, [], tmp_path)
    assert opening["startCandidates"][-1], "no origin spaces were marked at turn start"

    route_prefix = next(
        _values(steps)[:index]
        for steps in decisions
        for index, step in enumerate(steps)
        if step["kind"] == "duty"
    )
    after_route = _run_script(server, _clicks_to(server, decisions, route_prefix), tmp_path)
    chosen_origin = route_prefix[0]
    expected = sorted(step["value"] for step in _next_steps(decisions, route_prefix))
    assert expected, "the engine offered no duties at this point"
    assert chosen_origin not in after_route["startCandidates"][-1]
    assert chosen_origin not in after_route["dutyCandidates"][-1]
    assert sorted(after_route["dutyCandidates"][-1]) == expected


@needs_node
def test_action_on_produce_keeps_resolution_open_and_offers_remaining_keys(tmp_path: Path) -> None:
    """Action narrows to non-tithe survivors and does not pick among them for the player."""
    server = _played_through_setup(_served(tmp_path))
    decisions = _engine_decisions(server)
    produce = next(
        steps
        for steps in decisions
        if any(
            step["kind"] == "resolution" and step["value"].startswith("produce_") for step in steps
        )
    )
    prefix = []
    for step in produce:
        if step["kind"] == "resolution":
            break
        prefix.append(step["value"])
    to_duty = _clicks_to(server, decisions, prefix)
    selected = _run_script(server, to_duty, tmp_path)
    after_action = _run_script(server, [*to_duty, _press("action")], tmp_path)

    assert selected["controls"][-1]["action"] == "true"
    assert after_action["shownPanel"][-1] == -1, "Action quietly settled a still-open resolution"
    assert after_action["controls"][-1]["confirm"] == "false"
    assert after_action["controls"][-1]["tithe"] == "false"
    assert after_action["controlActive"][-1]["action"] == "true"
    assert sorted(
        value for value in after_action["offered"][-1] if value.startswith("produce_")
    ) == [
        "produce_stone",
        "produce_wheat",
    ]


@needs_node
def test_tithe_is_dark_when_the_selected_duty_offers_no_tithe(tmp_path: Path) -> None:
    """Driven with Taxation rather than asserted as a rule."""
    server = _played_through_setup(_served(tmp_path))
    decisions = _engine_decisions(server)
    taxation = next(
        steps
        for steps in decisions
        if any(step["kind"] == "resolution" and step["value"] == "taxation" for step in steps)
    )
    prefix = []
    for step in taxation:
        if step["kind"] == "resolution":
            break
        prefix.append(step["value"])
    transcript = _run_script(server, _clicks_to(server, decisions, prefix), tmp_path)

    assert transcript["controls"][-1]["action"] == "true"
    assert transcript["controls"][-1]["tithe"] == "false"


@needs_node
def test_restoring_first_survivor_destination_lookup_is_caught(tmp_path: Path) -> None:
    """MUTATION. Re-deriving the destination from `live[0]` must fail on branch choice."""
    server = _served(tmp_path)
    active = server.payload["state"]["active_player"]
    route = [
        "city->north",
        "north->north_east",
        "north_east->east",
        "east->city",
        "city->south",
    ]
    clicks = [
        _at(0),
        _follow("city->north"),
        _follow("north->north_east"),
        _follow("north_east->east"),
        _follow("east->city"),
        _follow("city->south"),
    ]
    regressed = _run_script(
        server,
        clicks,
        tmp_path,
        mutate=lambda code: code.replace(
            (
                "var stepIndex = prefix.length;\n"
                "      var step = null;\n"
                "      live.forEach(function (candidate) {\n"
                "        var offered = candidate.steps[stepIndex];\n"
                "        if (step || !offered) { return; }\n"
                "        if (offered.value === answer) {\n"
                "          step = offered;\n"
                "        }\n"
                "      });"
            ),
            "var stepIndex = prefix.length;\n      var step = live[0].steps[stepIndex];",
        ).replace(
            "var ends = String(answer).split('->');",
            "var ends = String(step.value).split('->');",
        ),
    )

    with pytest.raises(AssertionError, match="south_east"):
        _assert_preview_matches_route(regressed["cubes"][1], regressed["cubes"][-1], active, route)


@needs_node
def test_a_preview_overflow_is_recorded_and_stops_further_preview(tmp_path: Path) -> None:
    """MUTATION. If one placement fails, previewing stops and the overflow is observable."""
    server = _served(tmp_path)
    active = server.payload["state"]["active_player"]
    overflowed = _run_script(
        server,
        [_at(0), _follow("city->north")],
        tmp_path,
        mutate=lambda code: code.replace(
            "if (!slot) { return null; }",
            "if (name === 'north') { return null; }\n    if (!slot) { return null; }",
        ),
    )

    assert overflowed["overflow"][-1] is True, "overflow was not recorded"
    assert overflowed["counterShown"][-1] == ["5"], "preview kept counting after overflow"
    assert _visible_cubes(overflowed["cubes"][-1], "north", active) == 0


@needs_node
@pytest.mark.parametrize("seed", SETUP_SWEEP_SEEDS)
def test_every_setup_route_on_the_sweep_seeds_avoids_preview_overflow(
    tmp_path: Path,
    seed: int,
) -> None:
    """Tripwire: every setup route we sweep stays within the board's drawn cube capacity."""
    server = _served(tmp_path, seed=seed)
    decisions = _engine_decisions(server)

    assert decisions, f"seed {seed} had no setup-sow routes to check"
    for route in decisions:
        clicks = _clicks_to(server, decisions, _values(route))
        transcript = _run_script(server, clicks, tmp_path)
        assert not any(transcript["overflow"]), (
            f"seed {seed} overflowed on route {_values(route)!r}"
        )


def test_the_buttons_do_not_describe_a_turn_they_may_not_be_part_of(tmp_path: Path) -> None:
    """A start-player selection is an action, and none of it is a turn.

    The words were borrowed from the turn flow, where they were true. The opening decision of a
    generated game is now the first thing anybody clicks, and "start this turn again" is not a
    description of it. The summary directly above says what is being agreed to, so the button does
    not have to -- and a label that named the action would be a second description to keep in step.
    """
    page = render_play_view_from_payload(_opened(tmp_path).payload)

    assert 'data-turn-confirm="' not in page, "the panel still carries its own confirm button"
    assert "data-turn-reset" not in page, "the panel still carries its own reset button"
    for control in ("action", "tithe", "reset", "confirm"):
        assert f'data-turn-control="{control}"' in page, f"the {control} control is missing"
    for borrowed in ("Confirm this turn", "Start this turn again"):
        assert borrowed not in page, f"the panel still calls this a turn: {borrowed!r}"


def test_the_wheel_corners_keep_only_the_counter_and_box_holds_the_controls(tmp_path: Path) -> None:
    page = render_play_view_from_payload(_served(tmp_path).payload)
    action = page[
        page.index('<div class="panel p-action">') : page.index('<div class="panel p-map">')
    ]
    box = page[page.index('data-component="play-turn"') : page.index('class="log-transcript"')]

    assert 'data-turn-counter="' in action
    assert 'data-turn-control="' not in action
    for control in ("action", "tithe", "reset", "confirm"):
        assert f'data-turn-control="{control}"' in box
    controls_start = box.index('<div class="turn-controls" data-component="turn-controls">')
    assert controls_start > box.rindex('data-turn-prompt="'), (
        "the restored control grid no longer follows the prompt lines"
    )
    assert '<div class="turn-control-row turn-control-row-top">' in box
    assert '<div class="turn-control-row turn-control-row-bottom">' in box
    assert 'data-turn-control="sow"' not in page


def test_end_turn_phase_is_painted_in_server_html_before_the_script_runs() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    committed = replace(
        scenario.state,
        turn_progress=replace(scenario.state.turn_progress, resolution_committed=True),
    )
    state_payload = view_payload(committed, scenario.config)
    candidates = play_server.turn_candidates(committed, scenario.config)
    turn_step_payload = play_server.turn_steps_payload(committed, scenario.config)
    payload = dict(
        state_payload,
        state_token=state_token(state_payload),
        turn_candidates=candidates,
        turn_steps=turn_step_payload,
        log=[],
        log_blocks=[],
        phase_column=play_server.phase_column_payload(
            committed,
            [],
            available_turn_steps=turn_step_payload,
            turn_candidates=candidates,
        ),
    )

    page = render_play_view_from_payload(payload)

    assert payload["phase_column"]["prompts"] == {}
    assert page.count('data-turn-phase="') == 3
    assert 'data-turn-phase-prompt=' not in page
    assert not re.findall(r'<div class="phase-row"[^>]*data-phase-current="true"', page)
    assert page.count('data-turn-stage="') == 7
    current_stage_rows = re.findall(
        r'<div class="turn-stage-row"[^>]*data-turn-stage-current="true"', page
    )
    assert len(current_stage_rows) == 1
    assert (
        'data-turn-stage="end_turn" data-turn-stage-state="open" '
        'data-turn-stage-highlight="true" data-turn-stage-current="true">End the turn</div>'
        in page
    )


def test_the_opening_decision_is_put_on_every_board_and_can_be_hit(tmp_path: Path) -> None:
    """THE SYMPTOM, in the position a new game actually opens in.

    Four candidates, one per seat, every board offered as an answer -- and every one of those keys
    reachable by a click in the middle of the board rather than only along its border.
    """
    server = _opened(tmp_path)
    candidates = server.payload["turn_candidates"]
    offered = {step["value"] for c in candidates for step in c["steps"] if step["kind"] == "seat"}

    assert len(candidates) == 4, f"a four-player opening offered {len(candidates)} choices"
    assert offered == _seated(server), "the choosable boards are not the seated players"

    page = render_play_view_from_payload(server.payload)
    keys = re.findall(r"<rect data-seat-choice-key=\"([^\"]*)\"[^>]*>", page)
    assert len(keys) == 4, f"the page drew {len(keys)} seat keys"
    for key in re.findall(r"<rect data-seat-choice-key=[^>]*>", page):
        assert 'pointer-events="all"' in key, f"a seat key is hit only on its edge: {key}"


@needs_node
def test_removing_one_data_arrow_attribute_is_caught(tmp_path: Path, monkeypatch) -> None:
    """MUTATION. One offered edge with no drawn arrow must fail the setup-sow guard."""
    from tools.ui_debug import render_duty_wheel

    original = render_duty_wheel._arrow_ends_markup

    def without_city_north(origin: str, destination: str, board: dict) -> str:
        markup = original(origin, destination, board)
        if origin == "city" and destination == "north":
            return markup.replace(f' data-arrow="{origin}->{destination}"', "", 1)
        return markup

    monkeypatch.setattr(render_duty_wheel, "_arrow_ends_markup", without_city_north)

    with pytest.raises(AssertionError, match="setup sow offered"):
        test_setup_sow_is_asked_with_arrows_and_a_counter(tmp_path)


@needs_node
def test_dimming_reset_after_origin_is_taken_is_caught(tmp_path: Path) -> None:
    """MUTATION. If reset never lights after following an arrow, the guard has to say so."""
    server = _served(tmp_path)
    counted = _run_script(
        server,
        [_at(0), _follow("city->north")],
        tmp_path,
        mutate=lambda code: code.replace(
            "setControl('reset', preview.resettable, false);",
            "setControl('reset', false);",
        ),
    )
    with pytest.raises(AssertionError, match="reset stayed dark after an arrow was followed"):
        _reset_waits_for_a_followed_arrow(counted)


@needs_node
def test_showing_more_than_one_prompt_line_at_once_is_caught(tmp_path: Path) -> None:
    """MUTATION. If prompts are no longer one-at-a-time, the guard has to say so."""
    server = _served(tmp_path)
    active = server.payload["state"]["active_player"]
    server.payload = dict(
        server.payload,
        turn_candidates=[
            {
                "steps": [
                    {
                        "kind": "origin",
                        "value": 1,
                        "prompt": f"{active}: Choose a space to lift acolytes from.",
                        "counter": 1,
                    }
                ],
                "counter_start": 1,
                "action_id": None,
                "summary": None,
                "unresolved": [],
                "unresolved_text": [],
                "variants": 1,
            },
            {
                "steps": [
                    {
                        "kind": "origin",
                        "value": 2,
                        "prompt": f"{active}: Choose a duty to take.",
                        "counter": 1,
                    }
                ],
                "counter_start": 1,
                "action_id": None,
                "summary": None,
                "unresolved": [],
                "unresolved_text": [],
                "variants": 1,
            },
        ],
    )
    widened = _run_script(
        server,
        [],
        tmp_path,
        mutate=lambda code: code.replace(
            "return step === null ? [] : [step.prompt];",
            (
                "return offered.filter(function (step) { return step.prompt; }).map(function"
                " (step) { return step.prompt; });"
            ),
        ),
    )
    with pytest.raises(AssertionError, match="two questions were put at once"):
        _exactly_one_prompt_is_visible(widened)


def test_an_outline_key_that_forgets_pointer_events_is_caught(monkeypatch) -> None:
    """MUTATION. Draw the seat key the way it was drawn, and the guard above must say so.

    This is the shipped bug, reinstated. It is worth pinning permanently because the mistake is
    invisible in the markup -- `fill="none"` is exactly right for an outline, and nothing about it
    looks like it also turns the click off.
    """
    from tools.ui_debug import render_player_boards_v2

    outline_only = render_player_boards_v2._render_seat_choice_key

    def without_pointer_events(geometry, player):
        return outline_only(geometry, player).replace(' pointer-events="all"', "")

    monkeypatch.setattr(render_player_boards_v2, "_render_seat_choice_key", without_pointer_events)

    with pytest.raises(AssertionError, match="data-seat-choice-key"):
        test_everything_the_script_reaches_for_can_be_hit_where_it_looks_solid()


def test_removing_hidden_choice_key_pointer_gate_is_caught(monkeypatch) -> None:
    """MUTATION. A hidden whole-board/map key must not keep swallowing clicks."""
    from tools.ui_debug import render_play_view

    with_gate = render_play_view.turn_styles

    def without_first_gate(route_color: str) -> str:
        return with_gate(route_color).replace(
            "visibility: hidden; pointer-events: none;",
            "visibility: hidden;",
            1,
        )

    monkeypatch.setattr(render_play_view, "turn_styles", without_first_gate)
    page = render_play_view_from_payload(_reference_server().payload)

    with pytest.raises(AssertionError, match="still takes clicks"):
        _hidden_choice_key_rules_drop_pointer_events(page)


# ---------------------------------------------------------------------------------------------
# The committed page is reproducible
# ---------------------------------------------------------------------------------------------


def test_the_play_view_is_drawn_from_a_scenario_the_repository_holds(tmp_path: Path) -> None:
    """The page has to be rebuildable, or comparing it against a copy proves nothing.

    It used to be written by handing `render_play_view.py` a payload from someone's /tmp, and that
    payload was not kept. Nothing regenerated the page, so a sweep that rebuilt every view and
    diffed it against a before-copy skipped this one in silence: it matched because it had not been
    touched, not because it still rendered the same, and it would have gone on matching through any
    change to the adapter, the renderers or the view payload.
    """
    from tools.generate_play_view import default_scenario_path, generate_play_view_from_scenario

    assert default_scenario_path().is_file(), "the reference scenario is not in the repository"
    load_scenario(str(default_scenario_path()))  # it must still load, not merely exist

    first = generate_play_view_from_scenario(output_path=tmp_path / "one.html")
    second = generate_play_view_from_scenario(output_path=tmp_path / "two.html")
    assert first.read_bytes() == second.read_bytes(), "the page is not reproducible"


def test_the_page_written_to_a_file_stays_read_only(tmp_path: Path) -> None:
    """A file has no server to submit to, so it must not draw anything that looks pressable."""
    from tools.generate_play_view import generate_play_view_from_scenario

    page = generate_play_view_from_scenario(output_path=tmp_path / "play_view.html").read_text(
        encoding="utf-8"
    )
    page_without_tooltip_behavior = page.replace(building_tooltip_script(), "")
    for affordance in ("<script>", "data-sow-abandon", "data-sow-candidate", "data-sow-on-route"):
        assert affordance not in page_without_tooltip_behavior, (
            f"the static page offers {affordance}"
        )


def test_the_reference_scenario_is_the_position_the_play_view_is_for() -> None:
    """Four seats and an unplayed setup sow, which is what makes it worth drawing.

    Pinned because the choice is the whole point of the fix: a two-player scenario would leave the
    fourth seat and the four-handed piety variant undrawn, and a scenario past setup would show a
    board this page cannot yet be used to reach.
    """
    from tools.generate_play_view import default_scenario_path

    scenario = load_scenario(str(default_scenario_path()))
    assert len(scenario.state.players) == 4
    assert scenario.state.setup_sow_required
    assert not scenario.state.setup_sow_complete
    # And it is genuinely dealt, rather than a fixture with the board left blank.
    assert legal_actions(scenario.state, scenario.config)


def test_one_command_rebuilds_every_page_including_the_one_across_the_seam(
    tmp_path: Path,
) -> None:
    """Rebuilding must not be something anyone has to remember two halves of.

    The play view is built on the engine's side of the seam and the overview generator cannot reach
    it, so for a while a full rebuild was two commands and the second was skippable. Skipping it is
    invisible: the page then compares byte-identical against its before-copy through any change to
    anything it is drawn from, which is the state it was already found in once.
    """
    from tools.rebuild_generated_pages import rebuild_generated_pages, unrebuilt_pages

    written = rebuild_generated_pages(tmp_path)

    assert {path.name for path in written} == {path.name for path in tmp_path.glob("*.html")}
    assert "play_view.html" in {path.name for path in written}
    assert all(path.parent == tmp_path for path in written), "a page was written outside the run"
    assert unrebuilt_pages(written, tmp_path) == []


def test_a_page_nothing_rebuilds_is_reported_rather_than_passed_over(tmp_path: Path) -> None:
    """The check that makes copy-and-diff mean something, rather than only being cheap to run."""
    from tools.rebuild_generated_pages import main, rebuild_generated_pages, unrebuilt_pages

    written = rebuild_generated_pages(tmp_path)
    fossil = tmp_path / "built_by_nothing.html"
    fossil.write_text("<html></html>", encoding="utf-8")

    assert unrebuilt_pages(written, tmp_path) == [fossil]
    assert main(["--output-dir", str(tmp_path)]) == 1
    fossil.unlink()
    assert main(["--output-dir", str(tmp_path)]) == 0


# ---------------------------------------------------------------------------------------------
# The Confession Box, which each player answers for themselves
# ---------------------------------------------------------------------------------------------


def _played_until_a_box_is_offered(server, limit: int = 80):
    """Play settled turns until a round end stops to ask somebody about a Confession Box."""
    for _turn in range(limit):
        if server.payload["state"]["phase"] == "start_player_confession":
            return server
        settled = next((c for c in server.payload["turn_candidates"] if c["action_id"]), None)
        if settled is None:
            break
        _apply_settled_turn_and_pass(server, settled)
    raise AssertionError(f"no round end in {limit} moves asked about a box")


def test_a_confession_box_is_asked_of_one_player_and_answered_from_the_page(
    tmp_path: Path,
) -> None:
    """One player, one question, both answers offered, and the answer taken is the one applied."""
    server = _played_until_a_box_is_offered(_played_through_setup(_served(tmp_path)))
    asked = server.payload["state"]["active_player"]
    candidates = server.payload["turn_candidates"]

    assert len(candidates) == 2, "a box decision must be a real choice, not a formality"
    assert all(len(c["steps"]) == 1 for c in candidates), "one question, so one step"
    assert all(c["steps"][0]["kind"] == "combination" for c in candidates)
    assert not any(c["unresolved"] for c in candidates)

    using = next(c for c in candidates if c["steps"][0]["value"] != "decline")
    server.apply(using["action_id"], server.payload["state_token"])

    assert server.payload["state"]["phase"] != "start_player_confession" or (
        server.payload["state"]["active_player"] != asked
    ), "the same player was asked twice"


def test_a_box_offer_reads_as_a_sentence_and_names_where_it_comes_from(tmp_path: Path) -> None:
    """The three sources cost different things and are owed to different people."""
    server = _played_until_a_box_is_offered(_played_through_setup(_served(tmp_path)))
    labels = [c["steps"][0]["label"] for c in server.payload["turn_candidates"]]

    assert "decline the Confession Box" in labels
    using = next(label for label in labels if label != "decline the Confession Box")
    assert using.startswith(("use your own", "hire the Confession Box from"))

    # Checked on the page rather than on the label, because that is now where the sentence is
    # finished. `own_active` and `market` are turned into English here, since they are not seats
    # and the page has no lookup for them; a seat is left in the engine's name and said as a
    # colour by the page's one door. So the label alone is no longer the thing a player reads.
    page = render_play_view_from_payload(server.payload)
    offered = re.findall(r'<button[^>]*data-combination-key="[^"]*"[^>]*>([^<]*)</button>', page)
    assert offered, "the offers never reached the page"
    for text in offered:
        assert "_" not in text, f"a value leaked into what a player reads: {text}"


def test_the_boxes_are_answered_one_seat_at_a_time_and_the_marker_waits(tmp_path: Path) -> None:
    """The page never puts two players' questions up at once, and the round does not move on."""
    server = _played_until_a_box_is_offered(_played_through_setup(_served(tmp_path)))
    asked: list[str] = []
    while server.payload["state"]["phase"] == "start_player_confession":
        asked.append(server.payload["state"]["active_player"])
        assert len(server.payload["turn_candidates"]) == 2
        declining = next(
            c for c in server.payload["turn_candidates"] if c["steps"][0]["value"] == "decline"
        )
        server.apply(declining["action_id"], server.payload["state_token"])

    assert len(asked) == len(set(asked)), "a seat was asked twice"
    assert server.payload["state"]["phase"] == "start_player_selection", (
        "the marker was not awarded once the last seat had answered"
    )
