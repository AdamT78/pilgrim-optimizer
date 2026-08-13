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
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from pilgrim.io.logs import state_to_record
from pilgrim.io.scenarios import load_scenario
from pilgrim.io.view import duty_tiles_record, view_payload
from pilgrim.model.actions import SetupSowAction, action_id, action_summary
from pilgrim.model.enums import CANONICAL_POSITION_NAMES
from pilgrim.rules.transition import legal_actions
from tools.play_server import PlayServer, actions_document, state_token
from tools.ui_debug.render_play_view import render_play_view_from_payload

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


# ---------------------------------------------------------------------------------------------
# Playing a setup sow
# ---------------------------------------------------------------------------------------------

HARNESS = Path(__file__).resolve().parent / "turn_script_harness.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
REFERENCE = Path(__file__).resolve().parents[1] / "scenarios" / "play_view_reference_4p_001.json"


def _served(tmp_path: Path, players: int = 4, seed: int = 99):
    from pilgrim.cli import main as cli_main

    path = tmp_path / "scenario.json"
    cli_main(
        ["generate-setup", "--players", str(players), "--seed", str(seed), "--output", str(path)]
    )
    return PlayServer(("127.0.0.1", 0), path)


def _played_through_setup(server):
    """Take the four setup sows so the position is one where a normal turn is legal."""
    while server.payload["state"]["phase"] == "setup_sow":
        server.apply(
            server.payload["turn_candidates"][0]["action_id"], server.payload["state_token"]
        )
    return server


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


def _get_json(base: str, route: str):
    with urllib.request.urlopen(f"{base}{route}", timeout=10) as response:
        return json.loads(response.read())


def _run_script(server, clicks, tmp_path: Path, *, reset: bool = False, confirm: bool = False):
    """Execute the page's own turn script against a stub board, and report what it did."""
    page = render_play_view_from_payload(server.payload)
    script = re.search(r"<script>\n(.*?)\n</script>", page, re.S)
    assert script is not None, "the page carried no turn script"

    candidates = server.payload["turn_candidates"]
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps(
            {
                "script": script.group(1),
                "resolutions": sorted(
                    {
                        step["value"]
                        for candidate in candidates
                        for step in candidate["steps"]
                        if step["kind"] == "resolution"
                    }
                ),
                "panels": [candidate["action_id"] for candidate in candidates],
                "clicks": clicks,
                "reset": reset,
                "confirm": confirm,
            }
        ),
        encoding="utf-8",
    )
    finished = subprocess.run(
        ["node", str(HARNESS), str(job)], capture_output=True, text=True, check=True
    )
    return json.loads(finished.stdout)


def _at(value):
    return {"kind": "position", "value": value}


def _do(name):
    return {"kind": "resolution", "value": name}


# ---------------------------------------------------------------------------------------------
# What the engine says may come next
# ---------------------------------------------------------------------------------------------


def _engine_decisions(server) -> list[list]:
    """Every legal move as the sequence of decisions that reaches it, derived here from scratch.

    Deliberately not `turn_candidates`: comparing the page against the same function that fed it
    would only show the page copied it faithfully. This walks `legal_actions` itself, so what the
    offers are checked against is the engine's own answer about what is legal.
    """
    decisions = []
    for action in legal_actions(server.state, server.config):
        steps = [action.origin, *action.route]
        if not isinstance(action, SetupSowAction):
            steps += [action.selected_duty, action.resolution.value]
        if steps not in decisions:
            decisions.append(steps)
    return decisions


def _next_values(decisions: list[list], prefix: list) -> list:
    live = [steps for steps in decisions if steps[: len(prefix)] == prefix]
    seen = []
    for steps in live:
        if len(steps) > len(prefix) and steps[len(prefix)] not in seen:
            seen.append(steps[len(prefix)])
    return seen


def _forced_prefix(decisions: list[list], prefix: list) -> list:
    """Advance past every step the survivors agree on, as the page does."""
    prefix = list(prefix)
    while len(_next_values(decisions, prefix)) == 1:
        prefix.append(_next_values(decisions, prefix)[0])
    return prefix


def _clicks_to(decisions: list[list], target: list) -> list[dict]:
    """The clicks that reach one particular move, skipping every step the page takes by itself.

    Handing over all of a move's steps would not work and should not: the page advances past the
    forced ones on its own, so a caller supplying them too would answer the wrong questions.
    """
    clicks: list[dict] = []
    prefix: list = []
    while True:
        prefix = _forced_prefix(decisions, prefix)
        if len(prefix) >= len(target):
            return clicks
        step = target[len(prefix)]
        prefix.append(step)
        clicks.append(_do(step) if isinstance(step, str) else _at(step))


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
        prefix = _forced_prefix(decisions, prefix)
        expected = _next_values(decisions, prefix)
        if len(expected) <= 1:
            break
        transcript = _run_script(server, list(clicks), tmp_path)
        assert sorted(map(str, transcript["offered"][-1])) == sorted(map(str, expected))
        prefix.append(expected[0])
        clicks.append(_do(expected[0]) if isinstance(expected[0], str) else _at(expected[0]))
    assert clicks, "the position asked nothing, so nothing was checked"


@needs_node
@pytest.mark.parametrize("phase", ["setup_sow", "sow"])
def test_a_step_the_survivors_agree_on_is_never_put_as_a_question(phase, tmp_path: Path) -> None:
    """Forced steps are taken, not asked about, at whatever length the decisions happen to run."""
    server = _served(tmp_path)
    if phase == "sow":
        _played_through_setup(server)
    decisions = _engine_decisions(server)
    opening = _next_values(decisions, _forced_prefix(decisions, []))

    transcript = _run_script(server, [_at(opening[0])], tmp_path)
    for offered in transcript["offered"]:
        assert len(offered) != 1, f"a single option was presented as a choice: {offered}"


def test_the_two_phases_run_to_different_lengths_and_take_the_same_walk(tmp_path: Path) -> None:
    """Nothing may assume how many decisions a move takes, so the two phases must not agree.

    A setup sow decides six things here and a normal turn four, and the same script walks either.
    A route is as long as the number of acolytes lifted; the day that varies within one position
    too, this still holds, because no number is written down anywhere to have to be updated.
    """
    server = _served(tmp_path)
    setup_lengths = {len(steps) for steps in _engine_decisions(server)}
    _played_through_setup(server)
    turn_lengths = {len(steps) for steps in _engine_decisions(server)}

    assert setup_lengths.isdisjoint(turn_lengths), "the two phases happen to run the same length"


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

    sown = [step["value"] for step in candidate["steps"] if step["value"] != 0]
    assert _cubes_at(page_before, sown[0], first) == 0
    assert _cubes_at(pages[0], sown[0], first) > 0
    assert final["state"]["acolytes"][0][0] < city_before

    # Setup is over: the phase has turned and the seat on is the one the round starts with.
    assert final["state"]["phase"] == "sow"
    assert final["state"]["active_player"] == final["state"]["start_player_id"]
    log = server.payload["log"]
    assert any("SETUP_COMPLETE" in line for line in log)
    assert any(final["state"]["start_player_id"] in line for line in log)


def test_a_normal_turn_moves_the_cubes_pays_for_itself_and_passes_the_seat(
    tmp_path: Path,
) -> None:
    """A whole turn, played the way the page plays it, and the board comes back changed."""
    server = _played_through_setup(_served(tmp_path))
    with _running(server) as base:
        before = _get_json(base, "/state.json")
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"])
        status, _page = _post(base, settled["action_id"], server.payload["state_token"])
        after = _get_json(base, "/state.json")

    assert status == 200
    assert after["state"]["acolytes"] != before["state"]["acolytes"], "no cube moved"
    assert after["state"]["players"] != before["state"]["players"], "nothing was gained or spent"
    assert after["state"]["active_player"] != before["state"]["active_player"]


@needs_node
def test_a_turn_is_shown_in_words_before_it_is_sent_and_needs_a_press(tmp_path: Path) -> None:
    """Nothing is committed by running out of questions. The last click is agreeing to it.

    The words are the CLI's, taken from `action_summary` rather than written again here, so the
    sentence somebody confirms is the sentence the tool prints for that same action.
    """
    server = _played_through_setup(_served(tmp_path))
    decisions = _engine_decisions(server)
    candidates = server.payload["turn_candidates"]
    index = next(i for i, c in enumerate(candidates) if c["action_id"])
    candidate = candidates[index]
    clicks = _clicks_to(decisions, [step["value"] for step in candidate["steps"]])

    answered = _run_script(server, clicks, tmp_path)
    assert answered["shownPanel"][-1] == index, "the decided turn was not the one shown"
    assert answered["posted"] is None, "the turn went without anybody agreeing to it"

    chosen = next(
        action
        for action in legal_actions(server.state, server.config)
        if action_id(action) == candidate["action_id"]
    )
    assert candidate["summary"] == action_summary(chosen, server.config)

    confirmed = _run_script(server, clicks, tmp_path, confirm=True)
    assert confirmed["posted"]["action_id"] == candidate["action_id"]
    assert confirmed["posted"]["state_token"] == server.payload["state_token"]


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
# What the page will not do
# ---------------------------------------------------------------------------------------------


def test_a_turn_the_page_cannot_finish_is_refused_with_the_open_fields_named(
    tmp_path: Path,
) -> None:
    """Answering everything the page asks can still leave several actions standing.

    `FullTurnAction` carries some forty optional fields and four of them are presented. When the
    rest disagree, the honest answer is to say which -- picking one, or the first, or the simplest,
    would be the page quietly making a decision the rules give to the player. The named fields are
    the backlog, worked out from the position rather than remembered.
    """
    server = _played_through_setup(_served(tmp_path))
    open_ended = [c for c in server.payload["turn_candidates"] if c["unresolved"]]
    assert open_ended, "no ambiguous turn on this board, so nothing was exercised"

    for candidate in open_ended:
        assert candidate["action_id"] is None, "an undecided turn was given something to submit"
        assert candidate["summary"] is None, "an undecided turn was described as if it were one"
        assert candidate["variants"] > 1
        assert all(isinstance(name, str) and name for name in candidate["unresolved"])

    # The fields named are really the ones the survivors differ on, checked against the actions.
    candidate = open_ended[0]
    wanted = [step["value"] for step in candidate["steps"]]
    members = [
        action
        for action in legal_actions(server.state, server.config)
        if [action.origin, *action.route, action.selected_duty, action.resolution.value] == wanted
    ]
    assert len(members) == candidate["variants"]
    for name in candidate["unresolved"]:
        assert len({getattr(member, name) for member in members}) > 1


@needs_node
def test_an_undecided_turn_offers_no_way_to_commit_it(tmp_path: Path) -> None:
    """The refusal has to be structural: there is no button on that panel to press."""
    server = _played_through_setup(_served(tmp_path))
    candidates = server.payload["turn_candidates"]
    index = next(i for i, c in enumerate(candidates) if c["unresolved"])
    target = [step["value"] for step in candidates[index]["steps"]]
    clicks = _clicks_to(_engine_decisions(server), target)

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


def test_the_script_may_filter_and_reveal_and_nothing_else(tmp_path: Path) -> None:
    """No rule may be computed in the browser, so there is nowhere for a second one to live.

    Adjacency, route length and legality are the engine's, and every turn the page can express came
    from it whole. This greps for a second implementation rather than trusting the intent.
    """
    server = _played_through_setup(_served(tmp_path))
    page = render_play_view_from_payload(server.payload)
    script = re.search(r"<script>\n(.*?)\n</script>", page, re.S).group(1)
    # Comments are stripped first: prose about what the code does not do is not the code doing it,
    # and a grep that cannot tell them apart would be satisfied by deleting the explanation.
    code = re.sub(r"/\*.*?\*/", "", script, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)

    for forbidden in ("adjacen", "neighbour", "neighbor", "legal", "Math.", "sqrt", "route"):
        assert forbidden not in code, f"the script looks like it computes {forbidden!r}"
    # No arithmetic on the decisions, so it cannot be counting steps or measuring a route.
    assert not re.search(r"[-+*/%]=|[^-+]\+\+|--[^-]|\b\w+\s*[-+*/%]\s*\d", code)
    # No colour and no geometry either, which is the rule the seal established.
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", code)
    assert not re.search(r"\b(cx|cy|stroke|fill|translate)\s*[=:]", code)
    # It may say only these things about the board and the panel.
    assert "setAttribute('data-play-offered'" in code
    assert "setAttribute('data-turn-shown'" in code


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
    for affordance in ("<script>", "data-sow-abandon", "data-sow-candidate", "data-sow-on-route"):
        assert affordance not in page, f"the static page offers {affordance}"


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
