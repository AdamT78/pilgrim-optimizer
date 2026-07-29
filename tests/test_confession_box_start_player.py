from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import StartPlayerConfessionBoxUse, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.piety import score_piety
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _round_ending_tithe_actions(path: str):
    scenario = load_scenario(path)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    ]
    return scenario, actions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_temporary_piety_bonus_can_exceed_twelve_and_does_not_persist() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_owned_temp_piety_above_12_001.json"
    )
    action = _first_action(
        actions,
        lambda candidate: candidate.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_ONE,
                source="own_active",
            ),
        ),
    )
    before_vp = score_piety(
        scenario.state.player_state(PlayerId.PLAYER_ONE).piety,
        scenario.config.piety,
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _events_of_type(result.events, EventType.CONFESSION_BOX_BONUS)[0]
    selection_event = _events_of_type(result.events, EventType.START_PLAYER_SELECTION)[0]
    bonus_details = dict(bonus_event.details)
    selection_details = dict(selection_event.details)
    after_piety = result.state.player_state(PlayerId.PLAYER_ONE).piety
    after_vp = score_piety(after_piety, scenario.config.piety)

    assert bonus_details["player"] == "player_one"
    assert bonus_details["base_piety"] == 12
    assert bonus_details["temporary_bonus"] == 2
    assert bonus_details["effective_piety"] == 14
    assert selection_details["highest_effective_piety"] == 14
    assert selection_details["selected_start_player"] == "player_one"
    assert after_piety == 12
    assert before_vp == after_vp
    assert EventType.PIETY_DELTA not in {event.event_type for event in result.events}
    assert not hasattr(result.state.player_state(PlayerId.PLAYER_ONE), "temporary_piety")


def test_owned_confession_box_works_for_free_even_when_merchant_resource_is_none() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_owned_start_player_001.json"
    )
    action = _first_action(
        actions,
        lambda candidate: candidate.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_ONE,
                source="own_active",
            ),
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.BUILDING_HIRED not in event_types
    assert EventType.CONFESSION_BOX_BONUS in event_types
    assert dict(_events_of_type(result.events, EventType.START_PLAYER_SELECTION)[0].details)[
        "selected_start_player"
    ] == "player_one"


def test_market_hired_confession_box_pays_bank_then_applies_bonus() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_hire_market_start_player_001.json"
    )
    action = _first_action(
        actions,
        lambda candidate: candidate.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_TWO,
                source="market",
            ),
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.CONFESSION_BOX_BONUS)[0]
    selection_event = _events_of_type(result.events, EventType.START_PLAYER_SELECTION)[0]
    hired_details = dict(hired_event.details)
    bonus_details = dict(bonus_event.details)

    assert hired_details["building_id"] == "confession_box"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert bonus_details["player"] == "player_two"
    assert bonus_details["base_piety"] == 9
    assert bonus_details["effective_piety"] == 11
    assert dict(selection_event.details)["selected_start_player"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 0
    assert result.events.index(hired_event) < result.events.index(bonus_event)


def test_opponent_hired_confession_box_pays_owner_then_applies_bonus() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_hire_opponent_start_player_001.json"
    )
    action = _first_action(
        actions,
        lambda candidate: candidate.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_TWO,
                source="player_one",
            ),
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.CONFESSION_BOX_BONUS)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["source"] == "player_one"
    assert hired_details["payee"] == "player_one"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert dict(bonus_event.details)["effective_piety"] == 11
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1
    assert result.events.index(hired_event) < result.events.index(bonus_event)


def test_multiple_players_confession_box_resolves_in_start_player_order() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_multiple_players_player_order_001.json"
    )
    action = _first_action(
        actions,
        lambda candidate: candidate.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_TWO,
                source="player_one",
            ),
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_ONE,
                source="own_active",
            ),
        ),
    )
    summary = action_summary(action, scenario.config)
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_events = _events_of_type(result.events, EventType.CONFESSION_BOX_BONUS)

    assert (
        "start-player Confession Box: player_two hires Confession Box from player_one; "
        "player_one uses own active Confession Box"
    ) in summary
    assert len(bonus_events) == 2
    assert dict(bonus_events[0].details)["player"] == "player_two"
    assert dict(bonus_events[1].details)["player"] == "player_one"
    assert result.events.index(hired_event) < result.events.index(bonus_events[0])
    assert result.events.index(bonus_events[0]) < result.events.index(bonus_events[1])
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 0


def test_tie_break_uses_effective_piety_after_confession_box_bonus() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_effective_piety_tie_break_001.json"
    )
    action = _first_action(
        actions,
        lambda candidate: candidate.start_player_confession_box_uses
        == (
            StartPlayerConfessionBoxUse(
                player=PlayerId.PLAYER_ONE,
                source="own_active",
            ),
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    tie_break_event = _events_of_type(result.events, EventType.START_PLAYER_TIE_BREAK)[0]
    tie_break_details = dict(tie_break_event.details)

    assert tie_break_details["current_start_player"] == "player_two"
    assert tie_break_details["deciding_player"] == "player_one"
    assert result.state.start_player is PlayerId.PLAYER_ONE
    assert result.state.active_player is PlayerId.PLAYER_ONE


def test_hired_confession_box_choices_block_when_merchant_resource_is_none() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_hire_blocked_merchant_none_001.json"
    )

    assert all(not action.start_player_confession_box_uses for action in actions)
    result = apply_action(scenario.state, actions[0], scenario.config)
    assert _events_of_type(result.events, EventType.CONFESSION_BOX_BONUS) == []
    assert [
        event
        for event in _events_of_type(result.events, EventType.BUILDING_HIRED)
        if dict(event.details).get("building_id") == "confession_box"
    ] == []


def test_game_end_before_start_player_selection_skips_confession_box_variants_and_events() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_game_end_no_start_player_phase_001.json"
    )

    assert all(not action.start_player_confession_box_uses for action in actions)
    result = apply_action(scenario.state, actions[0], scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.GAME_END in event_types
    assert EventType.START_PLAYER_SELECTION not in event_types
    assert EventType.CONFESSION_BOX_BONUS not in event_types
    assert EventType.BUILDING_HIRED not in event_types


def test_apply_rejects_confession_box_directive_on_non_round_ending_action() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    invalid_action = replace(
        action,
        start_player_confession_box_uses=(
            StartPlayerConfessionBoxUse(player=PlayerId.PLAYER_ONE, source="own_active"),
        ),
    )
    with pytest.raises(
        TransitionValidationError,
        match="only valid on round-ending actions",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_confession_box_directive_when_game_ends_before_start_player_selection() -> None:
    scenario, actions = _round_ending_tithe_actions(
        "scenarios/confession_box_game_end_no_start_player_phase_001.json"
    )
    invalid_action = replace(
        actions[0],
        start_player_confession_box_uses=(
            StartPlayerConfessionBoxUse(player=PlayerId.PLAYER_ONE, source="market"),
        ),
    )
    with pytest.raises(
        TransitionValidationError,
        match="invalid when game ends before start-player selection",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)
