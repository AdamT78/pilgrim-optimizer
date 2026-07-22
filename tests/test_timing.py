from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.timing import TimingState
from pilgrim.model.workforce import Workforce
from pilgrim.rules.timing import (
    advance_timing,
    is_round_end,
    is_season_end,
    resolve_season_end,
)
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants


def test_advance_timing_increments_turn_and_active_player() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = advance_timing(
        scenario.state,
        scenario.config.timing,
        action_id="test:timing",
    )
    assert result.state.timing.absolute_turn == 1
    assert result.state.timing.turn_in_round == 1
    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert result.round_ended is False
    assert result.season_ended is False
    assert [event.event_type for event in result.events] == [EventType.TURN_ADVANCE]


def test_round_end_advances_round_and_resets_turn_in_round() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_TWO,
        timing=TimingState(
            absolute_turn=1,
            round_number=1,
            season_number=1,
            turn_in_round=1,
        ),
    )
    result = advance_timing(state, scenario.config.timing, action_id="test:round_end")
    assert result.round_ended is True
    assert result.state.timing.absolute_turn == 2
    assert result.state.timing.round_number == 2
    assert result.state.timing.turn_in_round == 0
    assert result.completed_round_number == 1
    event_types = {event.event_type for event in result.events}
    assert EventType.ROUND_END in event_types
    assert EventType.ROUND_ADVANCE in event_types


def test_season_end_detected_on_configured_round_boundary() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = replace(
        scenario.state,
        active_player=PlayerId.PLAYER_TWO,
        timing=TimingState(
            absolute_turn=5,
            round_number=3,
            season_number=1,
            turn_in_round=1,
        ),
    )
    assert is_round_end(state.timing, scenario.config.timing) is True
    assert is_season_end(state.timing, scenario.config.timing) is True
    result = advance_timing(state, scenario.config.timing, action_id="test:season_end")
    assert result.season_ended is True
    assert result.completed_season_number == 1
    event_types = {event.event_type for event in result.events}
    assert EventType.SEASON_END in event_types


def test_resolve_season_end_increments_season_number() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    updated = resolve_season_end(scenario.state, scenario.config.timing)
    assert updated.timing.season_number == scenario.state.timing.season_number + 1


def test_transition_emits_turn_advance_and_updates_timing_for_normal_turn() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    merchant_event = next(
        event for event in result.events if event.event_type is EventType.MERCHANT_ADVANCE
    )
    merchant_details = dict(merchant_event.details)
    event_types = {event.event_type for event in result.events}
    turn_advance_index = next(
        index
        for index, event in enumerate(result.events)
        if event.event_type is EventType.TURN_ADVANCE
    )
    merchant_advance_index = next(
        index
        for index, event in enumerate(result.events)
        if event.event_type is EventType.MERCHANT_ADVANCE
    )
    assert EventType.TURN_ADVANCE in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert merchant_advance_index == turn_advance_index + 1
    assert result.state.timing.absolute_turn == 1
    assert result.state.timing.round_number == 1
    assert result.state.timing.season_number == 1
    assert result.state.timing.turn_in_round == 1
    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert EventType.DUMMY_ACOLYTE_MOVE not in event_types
    assert result.state.merchant_position == 1
    assert merchant_details["from_duty"] == "taxation"
    assert merchant_details["to_duty"] == "produce"
    assert merchant_details["current_resource"] == "wheat"


def test_transition_round_end_emits_round_events() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_TWO,
        phase=TurnPhase.SOW,
        timing=TimingState(
            absolute_turn=3,
            round_number=2,
            season_number=1,
            turn_in_round=1,
        ),
        players=(
            PlayerState(workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0))),
            PlayerState(workforce=Workforce(mancala=(0, 0, 0, 0, 1, 0, 0, 0, 0))),
        ),
    )
    action = FullTurnAction(
        origin=4,
        route=(5,),
        selected_duty=5,
        resolution=TurnResolutionType.TITHE,
    )
    result = apply_action(state, action, scenario.config)
    event_types = {event.event_type for event in result.events}
    assert EventType.TURN_ADVANCE in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.ROUND_END in event_types
    assert EventType.ROUND_ADVANCE in event_types
    assert EventType.SEASON_END not in event_types
    assert result.state.timing.round_number == 3
    assert result.state.timing.turn_in_round == 0
    assert result.state.merchant_position == 1


def test_transition_season_end_triggers_alms_reward_and_reset() -> None:
    scenario = load_scenario("scenarios/season_end_alms_001.json")
    before = scenario.state
    action = legal_actions(before, scenario.config)[0]
    result = apply_action(before, action, scenario.config)
    after = result.state

    event_types = {event.event_type for event in result.events}
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.DUMMY_ACOLYTE_MOVE in event_types
    assert EventType.SEASON_ADVANCE in event_types

    assert after.timing.season_number == 2
    assert after.timing.round_number == 4
    assert after.merchant_position == 1
    assert after.player_state(PlayerId.PLAYER_ONE).workforce.committed.alms_table == 1
    assert after.player_state(PlayerId.PLAYER_ONE).alms_position == 0
    assert after.player_state(PlayerId.PLAYER_TWO).alms_position == 0
    assert before.total_acolytes(PlayerId.PLAYER_ONE) == after.total_acolytes(PlayerId.PLAYER_ONE)
    assert before.total_acolytes(PlayerId.PLAYER_TWO) == after.total_acolytes(PlayerId.PLAYER_TWO)


def test_transition_season_end_skips_alms_table_gain_without_abbey_acolyte() -> None:
    scenario = load_scenario("scenarios/season_end_alms_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            workforce=replace(player_one.workforce, abbey=0),
        ),
    )
    action = legal_actions(state, scenario.config)[0]
    result = apply_action(state, action, scenario.config)
    after_player_one = result.state.player_state(PlayerId.PLAYER_ONE)
    assert after_player_one.workforce.committed.alms_table == 0
    season_reward_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_SEASON_REWARD
    )
    assert dict(season_reward_event.details)["moved"] is False


def test_scenarios_validate_with_timing_fields() -> None:
    for path in (
        "scenarios/mancala_sandbox_001.json",
        "scenarios/alms_sandbox_001.json",
        "scenarios/season_end_alms_001.json",
    ):
        scenario = load_scenario(path)
        validate_state_invariants(scenario.state)
