from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules.transition import apply_action, legal_actions


def test_start_player_unique_highest_piety_selects_that_player() -> None:
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    state = scenario.state.with_start_player(PlayerId.PLAYER_TWO)
    action = legal_actions(state, scenario.config)[0]
    result = apply_action(state, action, scenario.config)

    assert result.state.start_player is PlayerId.PLAYER_ONE
    assert result.state.active_player is PlayerId.PLAYER_ONE
    assert result.state.timing.turn_in_round == 0

    selection_event = next(
        event
        for event in result.events
        if event.event_type is EventType.START_PLAYER_SELECTION
    )
    details = dict(selection_event.details)
    assert details["deciding_player"] == "player_one"
    assert details["selected_start_player"] == "player_one"


def test_start_player_tie_break_moves_clockwise_away_from_current_holder() -> None:
    scenario = load_scenario("scenarios/start_player_selection_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)

    assert result.state.start_player is PlayerId.PLAYER_TWO
    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert result.state.timing.turn_in_round == 0

    tie_break_event = next(
        event
        for event in result.events
        if event.event_type is EventType.START_PLAYER_TIE_BREAK
    )
    tie_break_details = dict(tie_break_event.details)
    assert tie_break_details["current_start_player"] == "player_one"
    assert tie_break_details["deciding_player"] == "player_two"
