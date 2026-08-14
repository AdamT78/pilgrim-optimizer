from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, GameAction, SetupSowAction, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState
from pilgrim.rules.transition import TransitionResult, legal_actions
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


def test_two_player_round_ends_after_two_turns() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    first = _apply_with_selector(scenario.state, scenario.config, _select_tithe_action)
    second = _apply_with_selector(first.state, scenario.config, _select_tithe_action)

    first_event_types = _event_types(first.events)
    second_event_types = _event_types(second.events)

    assert first.state.timing.round_number == scenario.state.timing.round_number
    assert first.state.timing.turn_in_round == 1
    assert first.state.active_player is PlayerId.PLAYER_TWO
    assert EventType.ROUND_ADVANCE not in first_event_types
    assert EventType.MERCHANT_ADVANCE not in first_event_types
    assert EventType.START_PLAYER_MARKER not in first_event_types

    assert second.state.timing.round_number == scenario.state.timing.round_number + 1
    assert second.state.timing.turn_in_round == 0
    assert EventType.ROUND_ADVANCE in second_event_types
    assert EventType.MERCHANT_ADVANCE in second_event_types
    assert EventType.START_PLAYER_MARKER in second_event_types
    # Stopped on the marker holder, waiting to be told who begins. The start player is
    # still the seat this round was played from, because nobody has chosen one yet.
    assert second.state.phase is TurnPhase.START_PLAYER_SELECTION
    assert second.state.start_player is scenario.state.start_player


def test_three_player_round_ends_after_three_turns(tmp_path: Path) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=3, seed=3, normal_sow=True)
    first = _apply_with_selector(scenario.state, scenario.config, _select_tithe_action)
    second = _apply_with_selector(first.state, scenario.config, _select_tithe_action)
    third = _apply_with_selector(second.state, scenario.config, _select_tithe_action)

    assert first.state.active_player is PlayerId.PLAYER_TWO
    assert first.state.timing.round_number == scenario.state.timing.round_number
    assert EventType.ROUND_ADVANCE not in _event_types(first.events)

    assert second.state.active_player is PlayerId.PLAYER_THREE
    assert second.state.timing.round_number == scenario.state.timing.round_number
    assert EventType.ROUND_ADVANCE not in _event_types(second.events)

    third_events = _event_types(third.events)
    assert EventType.ROUND_ADVANCE in third_events
    assert EventType.MERCHANT_ADVANCE in third_events
    assert EventType.START_PLAYER_MARKER in third_events
    assert third.state.timing.round_number == scenario.state.timing.round_number + 1
    assert third.state.timing.turn_in_round == 0
    # Stopped on the marker holder, waiting to be told who begins. The start player is
    # still the seat this round was played from, because nobody has chosen one yet.
    assert third.state.phase is TurnPhase.START_PLAYER_SELECTION
    assert third.state.start_player is scenario.state.start_player


def test_four_player_round_ends_after_four_turns(tmp_path: Path) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=4, seed=4, normal_sow=True)
    first = _apply_with_selector(scenario.state, scenario.config, _select_tithe_action)
    second = _apply_with_selector(first.state, scenario.config, _select_tithe_action)
    third = _apply_with_selector(second.state, scenario.config, _select_tithe_action)
    fourth = _apply_with_selector(third.state, scenario.config, _select_tithe_action)

    assert first.state.active_player is PlayerId.PLAYER_TWO
    assert second.state.active_player is PlayerId.PLAYER_THREE
    assert third.state.active_player is PlayerId.PLAYER_FOUR

    assert EventType.ROUND_ADVANCE not in _event_types(first.events)
    assert EventType.ROUND_ADVANCE not in _event_types(second.events)
    assert EventType.ROUND_ADVANCE not in _event_types(third.events)

    fourth_events = _event_types(fourth.events)
    assert EventType.ROUND_ADVANCE in fourth_events
    assert EventType.MERCHANT_ADVANCE in fourth_events
    assert EventType.START_PLAYER_MARKER in fourth_events
    assert fourth.state.timing.round_number == scenario.state.timing.round_number + 1
    assert fourth.state.timing.turn_in_round == 0
    # Stopped on the marker holder, waiting to be told who begins. The start player is
    # still the seat this round was played from, because nobody has chosen one yet.
    assert fourth.state.phase is TurnPhase.START_PLAYER_SELECTION
    assert fourth.state.start_player is scenario.state.start_player


def test_three_player_start_player_tie_break_is_clockwise_from_current_marker(
    tmp_path: Path,
) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=3, seed=13, normal_sow=True)
    state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_THREE,
        start_player=PlayerId.PLAYER_TWO,
        timing=replace(
            scenario.state.timing,
            turn_in_round=2,
        ),
        pilgrimage_rounds=(),
    )
    state = _with_piety(state, PlayerId.PLAYER_ONE, 3)
    state = _with_piety(state, PlayerId.PLAYER_TWO, 3)
    state = _with_piety(state, PlayerId.PLAYER_THREE, 3)

    result = _apply_with_selector(state, scenario.config, _select_tithe_action)
    tie_break_event = _event_of_type(result.events, EventType.START_PLAYER_TIE_BREAK)
    tie_break_details = dict(tie_break_event.details)

    assert tie_break_details["deciding_player"] == "player_three"
    assert result.state.active_player is PlayerId.PLAYER_THREE
    assert result.state.active_player is PlayerId.PLAYER_THREE


def test_four_player_start_player_tie_break_is_clockwise_from_current_marker(
    tmp_path: Path,
) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=4, seed=14, normal_sow=True)
    state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_FOUR,
        start_player=PlayerId.PLAYER_THREE,
        timing=replace(
            scenario.state.timing,
            turn_in_round=3,
        ),
        pilgrimage_rounds=(),
    )
    state = _with_piety(state, PlayerId.PLAYER_ONE, 5)
    state = _with_piety(state, PlayerId.PLAYER_TWO, 1)
    state = _with_piety(state, PlayerId.PLAYER_THREE, 2)
    state = _with_piety(state, PlayerId.PLAYER_FOUR, 5)

    result = _apply_with_selector(state, scenario.config, _select_tithe_action)
    tie_break_event = _event_of_type(result.events, EventType.START_PLAYER_TIE_BREAK)
    tie_break_details = dict(tie_break_event.details)

    assert tie_break_details["deciding_player"] == "player_four"
    assert result.state.active_player is PlayerId.PLAYER_FOUR
    assert result.state.active_player is PlayerId.PLAYER_FOUR


def test_three_player_alms_turn_order_tie_break_uses_current_start_player_order(
    tmp_path: Path,
) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=3, seed=23, normal_sow=True)
    state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_THREE,
        start_player=PlayerId.PLAYER_TWO,
        ship_position=8,
        completed_rounds=8,
        timing=replace(
            scenario.state.timing,
            absolute_turn=26,
            round_number=9,
            season_number=1,
            turn_in_round=2,
        ),
        pilgrimage_rounds=(1, 10, 15, 23),
    )
    state = _with_alms_and_piety(state, PlayerId.PLAYER_ONE, alms=4, piety=2)
    state = _with_alms_and_piety(state, PlayerId.PLAYER_TWO, alms=1, piety=1)
    state = _with_alms_and_piety(state, PlayerId.PLAYER_THREE, alms=4, piety=2)

    result = _apply_with_selector(state, scenario.config, _select_tithe_action)
    season_end_event = _event_of_type(result.events, EventType.ALMS_SEASON_END)
    season_details = dict(season_end_event.details)

    assert season_details["tie_break"] == "turn_order"
    assert season_details["winner"] == "player_three"


def test_four_player_alms_turn_order_tie_break_uses_current_start_player_order(
    tmp_path: Path,
) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=4, seed=24, normal_sow=True)
    state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_FOUR,
        start_player=PlayerId.PLAYER_THREE,
        ship_position=8,
        completed_rounds=8,
        timing=replace(
            scenario.state.timing,
            absolute_turn=39,
            round_number=9,
            season_number=1,
            turn_in_round=3,
        ),
        pilgrimage_rounds=(1, 10, 15, 23),
    )
    state = _with_alms_and_piety(state, PlayerId.PLAYER_ONE, alms=4, piety=3)
    state = _with_alms_and_piety(state, PlayerId.PLAYER_TWO, alms=1, piety=1)
    state = _with_alms_and_piety(state, PlayerId.PLAYER_THREE, alms=2, piety=2)
    state = _with_alms_and_piety(state, PlayerId.PLAYER_FOUR, alms=4, piety=3)

    result = _apply_with_selector(state, scenario.config, _select_tithe_action)
    season_end_event = _event_of_type(result.events, EventType.ALMS_SEASON_END)
    season_details = dict(season_end_event.details)

    assert season_details["tie_break"] == "turn_order"
    assert season_details["winner"] == "player_four"


def test_round_length_uses_real_player_count_not_fixed_timing_config(tmp_path: Path) -> None:
    scenario = _load_generated_setup(tmp_path, player_count=3, seed=31, normal_sow=True)
    assert scenario.config.timing.players_per_round == 2

    first = _apply_with_selector(scenario.state, scenario.config, _select_tithe_action)
    second = _apply_with_selector(first.state, scenario.config, _select_tithe_action)

    assert first.state.timing.round_number == scenario.state.timing.round_number
    assert second.state.timing.round_number == scenario.state.timing.round_number
    assert EventType.ROUND_ADVANCE not in _event_types(first.events)
    assert EventType.ROUND_ADVANCE not in _event_types(second.events)


@pytest.mark.parametrize(
    ("player_count", "scenario_path", "seed"),
    (
        (3, "scenarios/setup_sow_3p_001.json", 3),
        (4, None, 44),
    ),
)
def test_setup_sow_for_three_and_four_players_does_not_trigger_round_end(
    tmp_path: Path,
    player_count: int,
    scenario_path: str | None,
    seed: int,
) -> None:
    if scenario_path is not None:
        scenario = load_scenario(scenario_path)
    else:
        scenario = _load_generated_setup(
            tmp_path, player_count=player_count, seed=seed, normal_sow=False
        )
    state = scenario.state
    if state.phase is TurnPhase.START_PLAYER_SELECTION:
        # A generated game opens by asking who begins. Answered here rather than avoided, because
        # this test is about the sows that follow and the order they run in.
        state = _apply_with_selector(state, scenario.config, lambda actions: actions[0]).state
    assert state.phase is TurnPhase.SETUP_SOW

    for step_index in range(player_count):
        result = _apply_with_selector(state, scenario.config, _select_setup_sow_action)
        events = _event_types(result.events)
        assert EventType.ROUND_ADVANCE not in events
        assert EventType.MERCHANT_ADVANCE not in events
        assert EventType.START_PLAYER_MARKER not in events
        if step_index < player_count - 1:
            assert result.state.phase is TurnPhase.SETUP_SOW
        state = result.state

    assert state.setup_sow_complete is True
    assert state.phase is TurnPhase.SOW
    assert state.active_player is state.start_player
    assert len(state.setup_sow_completed_by) == player_count


@pytest.mark.parametrize(("player_count", "seed"), ((3, 53), (4, 54)))
def test_generated_setup_round_length_matches_real_players(
    tmp_path: Path,
    player_count: int,
    seed: int,
) -> None:
    scenario = _load_generated_setup(
        tmp_path, player_count=player_count, seed=seed, normal_sow=True
    )
    start_round = scenario.state.timing.round_number
    state = scenario.state

    for _ in range(player_count - 1):
        result = _apply_with_selector(state, scenario.config, _select_tithe_action)
        assert EventType.ROUND_ADVANCE not in _event_types(result.events)
        assert result.state.timing.round_number == start_round
        state = result.state

    final = _apply_with_selector(state, scenario.config, _select_tithe_action)
    assert EventType.ROUND_ADVANCE in _event_types(final.events)
    assert final.state.timing.round_number == start_round + 1


def _load_generated_setup(
    tmp_path: Path,
    *,
    player_count: int,
    seed: int,
    normal_sow: bool,
):
    generated = generate_setup_scenario(player_count=player_count, seed=seed)
    repo_root = Path.cwd().resolve()
    for field in _CONFIG_PATH_FIELDS:
        generated[field] = str((repo_root / str(generated[field])).resolve())  # type: ignore[index]

    initial_state = generated["initial_state"]  # type: ignore[index]
    if normal_sow:
        initial_state["phase"] = "sow"
        initial_state["setup"] = {
            "setup_sow_required": False,
            "setup_sow_complete": True,
            "setup_sow_completed_by": [],
        }
        # Fast-forwarding the opening also means fast-forwarding the choice it opens on, so the
        # round has to begin where that choice would have left it: on the start player. A generated
        # game hands `active_player` to the MARKER HOLDER, who is red rather than the start player,
        # and carrying that through would open the round one seat along from the seat it counts
        # turn order out from.
        initial_state["active_player"] = initial_state["start_player_id"]

    scenario_path = tmp_path / f"generated_{player_count}p_seed_{seed}.json"
    scenario_path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")
    return load_scenario(scenario_path)


def _apply_with_selector(
    state: GameState,
    config,
    selector: Callable[[tuple[GameAction, ...]], GameAction],
) -> TransitionResult:
    actions = legal_actions(state, config)
    action = selector(actions)
    return apply_declining_confession(state, action, config)


def _select_tithe_action(actions: tuple[GameAction, ...]) -> GameAction:
    return _find_action(
        actions,
        lambda action: (
            isinstance(action, FullTurnAction) and action.resolution is TurnResolutionType.TITHE
        ),
        "tithe action",
    )


def _select_setup_sow_action(actions: tuple[GameAction, ...]) -> GameAction:
    return _find_action(
        actions,
        lambda action: isinstance(action, SetupSowAction),
        "setup sow action",
    )


def _find_action(
    actions: Iterable[GameAction],
    predicate: Callable[[GameAction], bool],
    label: str,
) -> GameAction:
    matches = [action for action in actions if predicate(action)]
    if not matches:
        raise AssertionError(f"Could not find {label}.")
    return min(matches, key=action_id)


def _event_types(events: tuple[GameEvent, ...]) -> tuple[EventType, ...]:
    return tuple(event.event_type for event in events)


def _event_of_type(events: tuple[GameEvent, ...], event_type: EventType) -> GameEvent:
    for event in events:
        if event.event_type is event_type:
            return event
    raise AssertionError(f"Missing event type {event_type.value}.")


def _with_piety(state: GameState, player_id: PlayerId, piety: int) -> GameState:
    player_state = state.player_state(player_id)
    return state.with_player_state(player_id, replace(player_state, piety=piety))


def _with_alms_and_piety(
    state: GameState,
    player_id: PlayerId,
    *,
    alms: int,
    piety: int,
) -> GameState:
    player_state = state.player_state(player_id)
    return state.with_player_state(
        player_id,
        replace(
            player_state,
            alms_position=alms,
            piety=piety,
        ),
    )
