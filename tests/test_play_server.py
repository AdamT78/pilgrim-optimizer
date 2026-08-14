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
from pilgrim.model.actions import (
    SetupSowAction,
    StartPlayerSelectionAction,
    action_id,
    action_summary,
)
from pilgrim.model.enums import CANONICAL_POSITION_NAMES, PlayerId
from pilgrim.rules.transition import apply_action, legal_actions
from tools.play_server import PlayServer, actions_document, state_token
from tools.ui_debug.render_play_view import render_play_view_from_payload
from tools.ui_debug.render_table_layout import SEATED_PLAYERS

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
    """A server on a fresh game, already past the decision that opens one.

    A generated game opens by asking who begins, and these tests are about the setup sows and the
    turns that follow it. That opening is the subject of its own test, which is where it is asserted
    rather than being incidentally rehearsed by every test that needs a board.
    """
    from pilgrim.cli import main as cli_main

    path = tmp_path / "scenario.json"
    cli_main(
        ["generate-setup", "--players", str(players), "--seed", str(seed), "--output", str(path)]
    )
    return _past_the_start_player_decision(PlayServer(("127.0.0.1", 0), path))


def _played_until_the_page_must_refuse(server, limit: int = 40):
    """Play on, a settled turn at a time, until the page meets a turn it cannot finish.

    Not a pinned seed and turn number. Which fields are still unpresented changes every time one
    of them gets an affordance, so a position hard-coded as ambiguous would go stale silently and
    take the refusal out of the suite with it. This looks for one instead, and says so if the game
    runs out without ever needing to refuse anything.
    """
    for _turn in range(limit):
        if any(candidate["unresolved"] for candidate in server.payload["turn_candidates"]):
            return server
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"])
        server.apply(settled["action_id"], server.payload["state_token"])
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


def _run_script(
    server,
    clicks,
    tmp_path: Path,
    *,
    reset: bool = False,
    confirm: bool = False,
    mutate=None,
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
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps(
            {
                "script": source,
                "resolutions": _key_values(candidates, "resolution"),
                "combinations": _key_values(candidates, "combination"),
                # Every building on the track, not only the constructible ones, because the page
                # draws a key for every one of them. A stub holding only the right answers cannot
                # show a script reaching past them.
                "buildings": _buildings_on_the_track(server),
                # Every seat, with the page's own word for which one is on, so the script has four
                # boards to choose wrongly between rather than one it cannot help but get right.
                # Always four, however many are playing, because the page always draws four and
                # hides the empty ones. A stub with only the occupied chairs in it would take the
                # empty ones out of reach of anything that wrongly lit them.
                "seats": [
                    {
                        "seat": seat,
                        "player": player_id,
                        "taken": player_id in _seated(server),
                        "active": player_id == server.payload["state"]["active_player"],
                    }
                    for seat, player_id in enumerate(SEATED_PLAYERS, start=1)
                ],
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


def _buildings_on_the_track(server) -> list[str]:
    """Read off the page, which is where the keys really are, rather than off the state."""
    page = render_play_view_from_payload(server.payload)
    return re.findall(r'data-building-choice-key="([a-z_]+)"', page)


def _seated(server) -> set[str]:
    """The engine's player ids that have a chair, which at two players is not the first two."""
    count = len(server.payload["state"]["players"])
    return {f"player_{word}" for word in ("one", "two", "three", "four")[:count]}


def _key_values(candidates: list[dict], kind: str) -> list[str]:
    """Every distinct value of one kind of step, which is one key each on the page."""
    return sorted(
        {step["value"] for c in candidates for step in c["steps"] if step["kind"] == kind}
    )


def _at(value):
    return {"kind": "position", "value": value}


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


def _click_for(server, step: dict) -> dict:
    """The click that answers one step, chosen by the step's kind and never by what it is about."""
    if step["kind"] == "position":
        return _at(step["value"])
    if step["kind"] == "resource":
        return _take(step["value"], _active_seat(server))
    if step["kind"] == "combination":
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


def _engine_steps(action) -> list[dict]:
    """One legal action as the sequence of decisions that reaches it, spelled out here by hand.

    Deliberately not `decision_steps`: comparing the page against the same function that fed it
    would only show the page copied it faithfully. Every field is read off the action itself, so
    what the offers are checked against is the engine's own answer about what is legal.
    """
    steps = [{"kind": "position", "value": position} for position in (action.origin, *action.route)]
    if isinstance(action, SetupSowAction):
        return steps
    steps.append({"kind": "position", "value": action.selected_duty})
    steps.append({"kind": "resolution", "value": action.resolution.value})
    for name in ("tithe_resource", "taxation_step1_resource"):
        if getattr(action, name) is not None:
            steps.append({"kind": "resource", "value": getattr(action, name)})
    if action.construct_building_id is not None:
        steps.append({"kind": "building", "value": action.construct_building_id})
    if action.resolution.value == "give_alms_paid":
        silver, wheat = (getattr(action, name) for name in ALMS_PAIR)
        steps.append({"kind": "combination", "value": f"silver={silver},wheat={wheat}"})
    if action.resolution.value == "taxation":
        taken = tuple(action.taxation_step2_resources or ())
        counted = ",".join(f"{noun}={taken.count(noun)}" for noun in ("stone", "silver", "wheat"))
        steps.append({"kind": "combination", "value": counted})
    return steps


def _engine_decisions(server) -> list[list[dict]]:
    """Every legal move as its sequence of decisions, with no two the same."""
    decisions: list[list[dict]] = []
    for action in legal_actions(server.state, server.config):
        steps = _engine_steps(action)
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


def _forced_prefix(decisions: list[list[dict]], prefix: list) -> list:
    """Advance past every step the survivors agree on, as the page does."""
    prefix = list(prefix)
    while len(_next_values(decisions, prefix)) == 1:
        prefix.append(_next_values(decisions, prefix)[0])
    return prefix


def _clicks_to(server, decisions: list[list[dict]], target: list) -> list[dict]:
    """The clicks that reach one particular move, skipping every step the page takes by itself.

    Handing over all of a move's steps would not work and should not: the page advances past the
    forced ones on its own, so a caller supplying them too would answer the wrong questions.

    Which affordance each click uses comes from the engine's own step kind, so a test never has to
    know that a tithe's stock is pressed on a board and an alms payment beside it.
    """
    clicks: list[dict] = []
    prefix: list = []
    while True:
        prefix = _forced_prefix(decisions, prefix)
        if len(prefix) >= len(target):
            return clicks
        value = target[len(prefix)]
        step = next(s for s in _next_steps(decisions, prefix) if s["value"] == value)
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
        prefix = _forced_prefix(decisions, prefix)
        expected = _next_values(decisions, prefix)
        if len(expected) <= 1:
            break
        transcript = _run_script(server, list(clicks), tmp_path)
        assert sorted(map(str, transcript["offered"][-1])) == sorted(map(str, expected))
        step = next(s for s in _next_steps(decisions, prefix) if s["value"] == expected[0])
        prefix.append(expected[0])
        clicks.append(_click_for(server, step))
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
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])

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
# The questions a resolution goes on to ask
# ---------------------------------------------------------------------------------------------


def _reference_server():
    """The committed reference board, played through setup to the first normal turn.

    The reference board rather than a generated one because it is the position the play view is
    drawn for, and it happens to reach a Cornucopia, the Taxation tile and a paid alms in the same
    turn -- which is all three of the questions this PR gives the page a way to ask.
    """
    return _played_through_setup(PlayServer(("127.0.0.1", 0), REFERENCE))


def _stocks(server, player_id: str) -> dict:
    """One seat's three stocks, off the payload the page is drawn from."""
    from tools.ui_debug.play_view_adapter import player_record

    return dict(player_record(server.payload, player_id)["resources"])


def _asked(server, resolution: str, kind: str) -> list[dict]:
    """Candidates for one resolution that go on to ask a further question of the given kind."""
    return [
        candidate
        for candidate in server.payload["turn_candidates"]
        if {"kind": "resolution", "value": resolution} in candidate["steps"]
        and any(step["kind"] == kind for step in candidate["steps"])
    ]


def _siblings(candidates: list[dict], candidate: dict, kind: str) -> list[dict]:
    """The candidates alike in everything but their answer to one kind of question."""
    wanted = _values_except(candidate["steps"], kind)
    return [other for other in candidates if _values_except(other["steps"], kind) == wanted]


def _answer(candidate: dict, kind: str):
    return next(step["value"] for step in candidate["steps"] if step["kind"] == kind)


def _played_from_the_page(server, candidate: dict, tmp_path: Path):
    """Walk the page to one candidate, agree to it, and apply exactly what it sent."""
    decisions = _engine_decisions(server)
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])
    transcript = _run_script(server, clicks, tmp_path, confirm=True)
    assert transcript["posted"] is not None, "the page found nothing to submit"
    assert transcript["posted"]["action_id"] == candidate["action_id"]
    server.apply(transcript["posted"]["action_id"], transcript["posted"]["state_token"])
    return transcript


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

    offered = {_pair(_answer(candidate, "combination")) for candidate in siblings}
    legal = {
        tuple(getattr(action, name) for name in ALMS_PAIR)
        for action in legal_actions(server.state, server.config)
        if _values_except(_engine_steps(action), "combination") == wanted
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
def test_a_counter_that_pays_one_thing_is_never_put_as_a_choice(tmp_path: Path) -> None:
    """Most tithe counters name their stock, so there is nothing to ask and no board lights.

    The same rule the route steps have always followed, now that a stock is a step too: a question
    with one answer is taken rather than asked. Worth its own check because this is the kind where
    not asking is the common case and asking is the exception.
    """
    server = _reference_server()
    asked = _asked(server, "tithe", "resource")
    forced = [c for c in asked if len(_siblings(asked, c, "resource")) == 1]
    assert forced, "every tithe on this board was a Cornucopia, so nothing was exercised"

    candidate = forced[0]
    decisions = _engine_decisions(server)
    clicks = _clicks_to(server, decisions, [step["value"] for step in candidate["steps"]])

    assert all(click["kind"] != "resource" for click in clicks), "a settled stock was pressed"
    transcript = _run_script(server, clicks, tmp_path, confirm=True)
    assert transcript["askedSeats"] == [[]] * len(transcript["askedSeats"]), "a board was asked"
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
        if {"kind": "resolution", "value": "taxation"} not in candidate["steps"]:
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
        server.apply(settled["action_id"], server.payload["state_token"])
    raise AssertionError("no Taxation bonus ever offered a choice, so nothing was tested")


def _mixes_the_engine_allows(server, prefix: tuple) -> set[str]:
    """Read off the actions themselves, not off the steps the page was handed."""
    allowed = set()
    for action in legal_actions(server.state, server.config):
        steps = _engine_steps(action)
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
    assert sorted(value for value in transcript["offered"][-1] if "=" in value) == sorted(offered)


@needs_node
def test_a_taxation_bonus_with_one_mix_never_puts_the_question(tmp_path: Path) -> None:
    """Most Taxation turns here have a single legal mix, and none of them may ask about it.

    Including the empty one. A seat holding no majority anywhere takes no bonus at all, which is
    still a mix -- "take nothing" -- and is still not a choice.
    """
    server = _reference_server()
    while not any(
        {"kind": "resolution", "value": "taxation"} in candidate["steps"]
        and any(step["kind"] == "combination" for step in candidate["steps"])
        for candidate in server.payload["turn_candidates"]
    ):
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        server.apply(settled["action_id"], server.payload["state_token"])

    assert _mix_groups(server) == {}, "this position had a choice of mix, so it tests nothing"
    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if {"kind": "resolution", "value": "taxation"} in c["steps"]
        and any(step["kind"] == "combination" for step in c["steps"])
    )
    forced = _answer(candidate, "combination")

    decisions = _engine_decisions(server)
    prefix = _values_except(candidate["steps"], "combination")
    transcript = _run_script(server, _clicks_to(server, decisions, prefix), tmp_path, confirm=True)

    assert forced not in transcript["offered"][-1], "the only legal mix was still asked for"
    assert transcript["posted"]["action_id"] == candidate["action_id"]


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
        server.apply(settled["action_id"], server.payload["state_token"])
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
    return sorted(
        {
            action.construct_building_id
            for action in legal_actions(server.state, server.config)
            if getattr(action, "construct_building_id", None) is not None
            and tuple(_values_except(_engine_steps(action), "building")) == prefix
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
def test_a_construct_with_one_building_to_go_at_never_puts_the_question(tmp_path: Path) -> None:
    """A step every survivor agrees on is taken, not asked, and this is one of those.

    Round 3 of the reference board has a single building live, so the construct turns there carry a
    building step whose value nobody has a choice about. It has to behave like every other forced
    step -- swallowed on the way past -- rather than becoming a hex the player must press to
    confirm something that was never in doubt.
    """
    server = _reference_server()
    while not any(
        step["kind"] == "building"
        for candidate in server.payload["turn_candidates"]
        for step in candidate["steps"]
    ):
        settled = next(c for c in server.payload["turn_candidates"] if c["action_id"] is not None)
        server.apply(settled["action_id"], server.payload["state_token"])

    assert _building_choices(server) == {}, "this position had a choice, so it tests nothing"
    candidate = next(
        c
        for c in server.payload["turn_candidates"]
        if any(step["kind"] == "building" for step in c["steps"])
    )
    forced = _answer(candidate, "building")

    decisions = _engine_decisions(server)
    prefix = _values_except(candidate["steps"], "building")
    transcript = _run_script(server, _clicks_to(server, decisions, prefix), tmp_path, confirm=True)

    assert forced not in transcript["offered"][-1], "the only building on offer was still asked for"
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

    Narrowing what the engine will construct separates them. A page reading the survivors asks
    nothing here, because one building is not a choice; a page reading the market goes on lighting
    both and offers a turn that does not exist.
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
    assert [value for value in transcript["offered"][-1] if value in on_the_track] == []


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
    server = _reference_server()

    with pytest.raises(AssertionError, match="not the pairs the engine allows"):
        _the_payments_offered_are_the_legal_pairs(server)


# ---------------------------------------------------------------------------------------------
# What the page will not do
# ---------------------------------------------------------------------------------------------


def test_a_turn_the_page_cannot_finish_is_refused_with_the_open_fields_named(
    tmp_path: Path,
) -> None:
    """Answering everything the page asks can still leave several actions standing.

    `FullTurnAction` carries some forty optional fields and this page presents a handful. When the
    rest disagree, the honest answer is to say which -- picking one, or the first, or the simplest,
    would be the page quietly making a decision the rules give to the player. The named fields are
    the backlog, worked out from the position rather than remembered.
    """
    server = _played_until_the_page_must_refuse(_played_through_setup(_served(tmp_path)))
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
        if _values(_engine_steps(action)) == wanted
    ]
    assert len(members) == candidate["variants"]
    for name in candidate["unresolved"]:
        assert len({getattr(member, name) for member in members}) > 1
    # A field the page does present cannot come back as unresolved: answering it is what put this
    # candidate in its own group, so the refusal is always about something genuinely unbuilt.
    presented = {"tithe_resource", "taxation_step1_resource", *ALMS_PAIR}
    assert presented.isdisjoint(candidate["unresolved"])


@needs_node
def test_an_undecided_turn_offers_no_way_to_commit_it(tmp_path: Path) -> None:
    """The refusal has to be structural: there is no button on that panel to press."""
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
        *ALMS_PAIR,
    ):
        assert field not in page, f"the page was told about the field {field!r}"


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
