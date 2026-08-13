"""The engine side of the seam: what is serialized, what joins it, and what the server answers.

Nothing here applies an action. This PR's server is read-only by design, and the tests hold it to
that as much as they hold it to the shapes.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

import pytest

from pilgrim.io.logs import state_to_record
from pilgrim.io.scenarios import load_scenario
from pilgrim.io.view import duty_tiles_record, view_payload
from pilgrim.model.enums import CANONICAL_POSITION_NAMES
from pilgrim.rules.transition import legal_actions
from tools.play_server import PlayServer, actions_document, state_token

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


@pytest.fixture(scope="module")
def scenario():
    return load_scenario(str(SCENARIOS / "alms_sandbox_001.json"))


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


def test_a_fresh_scenario_offers_setup_sows_and_nothing_else(tmp_path: Path) -> None:
    from pilgrim.cli import main as cli_main

    path = tmp_path / "fresh.json"
    cli_main(["generate-setup", "--players", "4", "--seed", "99", "--output", str(path)])
    scenario = load_scenario(str(path))
    payload = view_payload(scenario.state, scenario.config)
    document = actions_document(scenario.state, scenario.config, payload)
    assert document["count"] > 0
    assert {entry["action_type"] for entry in document["actions"]} == {"SetupSowAction"}
    assert all(entry["action_id"].startswith("setup_sow:") for entry in document["actions"])


def test_the_three_routes_answer_and_none_of_them_change_anything(tmp_path: Path) -> None:
    """The whole surface of this PR's server, exercised over a real socket."""
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
    assert "<button" not in page
    assert state == server.payload
    assert actions["count"] == len(actions["actions"]) > 0
    assert actions["state_token"] == state_token(server.payload)
    # Nothing was applied: the position the server holds is the one it was handed.
    assert server.state is before


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
