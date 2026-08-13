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
from pilgrim.model.actions import action_id
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

HARNESS = Path(__file__).resolve().parent / "sow_script_harness.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _served(tmp_path: Path, players: int = 4, seed: int = 99):
    from pilgrim.cli import main as cli_main

    path = tmp_path / "scenario.json"
    cli_main(
        ["generate-setup", "--players", str(players), "--seed", str(seed), "--output", str(path)]
    )
    return PlayServer(("127.0.0.1", 0), path)


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


def _run_script(page: str, clicks: list[int], tmp_path: Path, abandon_at: int | None = None):
    """Execute the page's own sow script against a stub board, and report what it did."""
    script = re.search(r"<script>\n(.*?)\n</script>", page, re.S)
    assert script is not None, "the page carried no sow script"
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps({"script": script.group(1), "clicks": clicks, "abandonAt": abandon_at}),
        encoding="utf-8",
    )
    finished = subprocess.run(
        ["node", str(HARNESS), str(job)], capture_output=True, text=True, check=True
    )
    return json.loads(finished.stdout)


def _distinct_next_steps(paths: list[list[int]], prefix: list[int]) -> list[int]:
    """What legal_actions itself says may come next, given the steps taken so far.

    Derived from the actions rather than from a written-down list of routes, so a board whose
    exits changed would move this expectation with it instead of failing it.
    """
    live = [path for path in paths if path[: len(prefix)] == prefix]
    seen = []
    for path in live:
        if len(path) > len(prefix) and path[len(prefix)] not in seen:
            seen.append(path[len(prefix)])
    return seen


def _paths_from_engine(server) -> list[list[int]]:
    return [[action.origin, *action.route] for action in legal_actions(server.state, server.config)]


@needs_node
def test_what_is_offered_is_what_the_engine_says_may_come_next(tmp_path: Path) -> None:
    """The options at each step are the distinct next steps of the surviving actions, and no more.

    Held against `legal_actions` rather than against a route anybody typed out. The page is allowed
    to narrow the engine's list; it is not allowed to arrive at a different one.
    """
    server = _served(tmp_path)
    paths = _paths_from_engine(server)
    page = render_play_view_from_payload(server.payload)

    clicks = [1, 4]
    transcript = _run_script(page, clicks, tmp_path)

    prefix: list[int] = []
    for step, offered in enumerate(transcript["offered"][: len(clicks)]):
        # Forced steps are taken by the page, so the engine's own prefix has to skip them too.
        while len(_distinct_next_steps(paths, prefix)) == 1:
            prefix.append(_distinct_next_steps(paths, prefix)[0])
        assert sorted(offered) == sorted(_distinct_next_steps(paths, prefix)), f"at step {step}"
        prefix.append(clicks[step])


@needs_node
def test_a_forced_step_is_never_offered_and_five_steps_are_asked_about_twice(
    tmp_path: Path,
) -> None:
    """A step every survivor agrees on is not a choice, and is not presented as one.

    On a freshly dealt board the route out of the City is five steps: two ways out, then three
    steps nobody has any say in, then whether to duck back into the City. Two questions, not five.
    """
    server = _served(tmp_path)
    page = render_play_view_from_payload(server.payload)
    transcript = _run_script(page, [1, 4], tmp_path)

    asked = [offered for offered in transcript["offered"] if offered]
    assert all(len(offered) > 1 for offered in asked), "a single option was presented as a choice"
    assert transcript["posted"]["action_id"] in {
        action_id(action) for action in legal_actions(server.state, server.config)
    }
    # Two clicks settled a five-step route, and the City it started from is marked as travelled.
    assert len(transcript["posted"]["action_id"].split(":")[-1].split("->")) == 5
    assert 0 in transcript["onRoute"][1]


@needs_node
def test_abandoning_a_half_built_route_sends_nothing_and_moves_nothing(tmp_path: Path) -> None:
    """Nothing is sent until one candidate is left, so giving up is local and must stay local."""
    server = _served(tmp_path)
    with _running(server) as base:
        before = _get_json(base, "/state.json")
        page = render_play_view_from_payload(server.payload)
        transcript = _run_script(page, [1], tmp_path, abandon_at=True)
        after = _get_json(base, "/state.json")

    assert transcript["posted"] is None, "a half-built route was submitted"
    assert transcript["abandonedTo"]["onRoute"] == [0], "abandoning kept steps that were clicked"
    assert after == before


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
            candidate = server.payload["sow_candidates"][0]
            status, page = _post(base, candidate["action_id"], server.payload["state_token"])
            assert status == 200
            pages.append(page)
        final = _get_json(base, "/state.json")

    sown = [position for position in candidate["path"] if position != 0]
    assert _cubes_at(page_before, sown[0], first) == 0
    assert _cubes_at(pages[0], sown[0], first) > 0
    assert final["state"]["acolytes"][0][0] < city_before

    # Setup is over: the phase has turned and the seat on is the one the round starts with.
    assert final["state"]["phase"] == "sow"
    assert final["state"]["active_player"] == final["state"]["start_player_id"]
    assert not server.payload["sow_candidates"]
    log = server.payload["log"]
    assert any("SETUP_COMPLETE" in line for line in log)
    assert any(final["state"]["start_player_id"] in line for line in log)


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
        candidate = server.payload["sow_candidates"][0]
        stale = server.payload["state_token"]
        assert _post(base, candidate["action_id"], stale)[0] == 200

        before = _get_json(base, "/state.json")
        status, body = _post(base, server.payload["sow_candidates"][0]["action_id"], stale)
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

    Adjacency, route length and legality are the engine's, and every route the page can express
    came from it whole. This greps for a second implementation rather than trusting the intent.
    """
    server = _served(tmp_path)
    page = render_play_view_from_payload(server.payload)
    script = re.search(r"<script>\n(.*?)\n</script>", page, re.S).group(1)
    # Comments are stripped first: prose about what the code does not do is not the code doing it,
    # and a grep that cannot tell them apart would be satisfied by deleting the explanation.
    code = re.sub(r"/\*.*?\*/", "", script, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)

    for forbidden in ("adjacen", "neighbour", "neighbor", "legal", "Math.", "sqrt", ".length -"):
        assert forbidden not in code, f"the script looks like it computes {forbidden!r}"
    # No colour and no geometry either, which is the rule the seal established.
    assert not re.search(r"#[0-9A-Fa-f]{3,6}\b", code)
    assert not re.search(r"\b(cx|cy|stroke|fill|translate)\s*[=:]", code)
    # It may say only these things about the board.
    assert "setAttribute('data-sow-candidate'" in script
    assert "setAttribute('data-sow-on-route'" in script


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
