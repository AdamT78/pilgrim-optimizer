"""The First Player marker as a thing a player HOLDS, rather than a phase they are briefly in.

The marker is won at a round end on effective piety and then sits with that player for the whole
round that follows. The state used to know that only while the holder was being asked who begins --
they were `active_player`, and the moment they answered, the fact was gone. So the marker could not
be drawn, and the one occasion it means anything, when a holder hands the round to somebody else,
was the exact occasion nothing recorded it.

Two facts that are allowed to disagree therefore need two fields, and the tests that matter most
here are the ones that would pass if they were secretly one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pilgrim.io.logs import state_to_record
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, StartPlayerSelectionAction
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.rules.transition import legal_actions
from pilgrim.setup.generator import generate_setup_scenario
from tests.round_end_helpers import apply_declining_confession

_CONFIG_PATH_FIELDS: tuple[str, ...] = (
    "board_file",
    "duties_file",
    "piety_file",
    "alms_file",
    "timing_file",
    "merchant_file",
    "ship_file",
    "buildings_file",
)


def _waiting_on_the_holder(scenario, *, start_player: PlayerId):
    """Play the turn that closes the round, stopping where the holder is asked to choose."""
    state = scenario.state.with_start_player(start_player)
    return apply_declining_confession(
        state, legal_actions(state, scenario.config)[0], scenario.config
    ).state


def _one_turn(state, config):
    action = next(
        action for action in legal_actions(state, config) if isinstance(action, FullTurnAction)
    )
    return apply_declining_confession(state, action, config).state


def _generated(tmp_path: Path, player_count: int):
    generated = generate_setup_scenario(player_count=player_count, seed=11)
    repo_root = Path.cwd().resolve()
    for field in _CONFIG_PATH_FIELDS:
        generated[field] = str((repo_root / str(generated[field])).resolve())  # type: ignore[index]
    path = tmp_path / f"generated_{player_count}p.json"
    path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")
    return load_scenario(path)


def test_a_holder_who_gives_the_round_away_keeps_the_marker() -> None:
    """THE PAYOFF. Two values that finally say different things, in the one position where they can.

    Everything before this could have been one field wearing two names, because the holder and the
    start player agreed in every state anybody looked at. Here the holder names somebody else and
    the two come apart: the marker stays, the round goes. Any line that "kept them in step" -- a
    tidy-looking `first_player_marker=chosen_start_player` in the selection -- would make this the
    only failing test in the suite, which is what it is for.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    waiting = _waiting_on_the_holder(scenario, start_player=PlayerId.PLAYER_TWO)
    holder = waiting.active_player
    assert waiting.first_player_marker is holder

    given_away = apply_declining_confession(
        waiting,
        StartPlayerSelectionAction(chosen_start_player=PlayerId.PLAYER_TWO),
        scenario.config,
    ).state

    assert given_away.first_player_marker is holder
    assert given_away.start_player is PlayerId.PLAYER_TWO
    assert given_away.active_player is PlayerId.PLAYER_TWO
    assert given_away.first_player_marker is not given_away.start_player


def test_a_holder_who_keeps_the_round_is_not_a_different_code_path() -> None:
    """The marker is not moved TO them either, because nothing moves it here at all."""
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    waiting = _waiting_on_the_holder(scenario, start_player=PlayerId.PLAYER_TWO)
    holder = waiting.active_player

    kept = apply_declining_confession(
        waiting,
        StartPlayerSelectionAction(chosen_start_player=holder),
        scenario.config,
    ).state

    assert kept.first_player_marker is holder
    assert kept.start_player is holder


def test_the_marker_sits_still_through_the_round_and_moves_only_at_the_end_of_it() -> None:
    """Durable, not momentary. It outlives the phase in which it was handed over.

    Walked turn by turn rather than checked at the two ends, because a field written at a round end
    and read at the next one would pass that. What is being asserted is that nothing in between --
    no sow, no turn advance, no selection -- so much as touches it.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    waiting = _waiting_on_the_holder(scenario, start_player=PlayerId.PLAYER_TWO)
    holder = waiting.active_player

    state = apply_declining_confession(
        waiting,
        StartPlayerSelectionAction(chosen_start_player=PlayerId.PLAYER_TWO),
        scenario.config,
    ).state

    turns = 0
    while state.phase is not TurnPhase.START_PLAYER_SELECTION:
        assert state.first_player_marker is holder, "the marker moved in the middle of a round"
        state = _one_turn(state, scenario.config)
        turns += 1
        assert turns < 10, "the round never ended, so nothing was really checked"

    assert turns == state.player_count, "the walk did not cover a whole round"
    # And at the round end it is settled again, from the piety as it stands now.
    assert state.first_player_marker is state.active_player


def test_a_scenario_written_before_the_marker_existed_does_not_acquire_one() -> None:
    """Absent means unknown, and unknown is kept.

    Every other optional field in a scenario has a defensible default. This one has none: the
    holder was won at a round end from piety that has since moved, so anything computed on load
    would be who would win it now, standing in for who won it then. A fixture that never had a
    holder is a position nobody can answer that question about, and saying so is the answer.
    """
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    assert scenario.state.first_player_marker is None

    piety = {
        player: scenario.state.player_state(player).piety
        for player in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO)
    }
    assert len(set(piety.values())) > 1, "this fixture cannot show a holder being guessed at"


def test_the_committed_scenarios_all_load_and_none_of_them_invent_a_holder() -> None:
    """Three hundred files, opened rather than argued about."""
    paths = sorted(Path("scenarios").glob("*.json"))
    assert len(paths) > 100, "the scenario directory is not where this test thinks it is"

    with_a_holder = [
        path for path in paths if json.loads(path.read_text()).get("first_player_marker")
    ]
    assert with_a_holder == []

    sampled = [load_scenario(path) for path in paths[:20]]
    assert all(scenario.state.first_player_marker is None for scenario in sampled)


@pytest.mark.parametrize("player_count", [2, 3, 4])
def test_a_generated_game_always_knows_who_holds_the_marker(
    tmp_path: Path,
    player_count: int,
) -> None:
    """New games are never in the unknown case, so the seal is drawn from the first frame."""
    scenario = _generated(tmp_path, player_count)

    assert scenario.state.first_player_marker is PlayerId.PLAYER_TWO
    assert scenario.state.phase is TurnPhase.START_PLAYER_SELECTION
    assert scenario.state.first_player_marker is not scenario.state.start_player


def test_the_record_says_who_holds_the_marker_and_says_so_when_it_does_not_know() -> None:
    """Serialized as null rather than left out, because null is a fact and absence is ambiguous."""
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    unknown = state_to_record(scenario.state)
    assert "first_player_marker" in unknown
    assert unknown["first_player_marker"] is None

    waiting = _waiting_on_the_holder(scenario, start_player=PlayerId.PLAYER_TWO)
    known = state_to_record(waiting)
    assert known["first_player_marker"] == waiting.active_player.name.lower()
    assert known["start_player_id"] == "player_two"
    assert known["first_player_marker"] != known["start_player_id"]
