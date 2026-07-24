from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.rules.transition import apply_action, legal_actions


def _actions_for_resolution(path: str, resolution: TurnResolutionType):
    scenario = load_scenario(path)
    actions = [
        action for action in legal_actions(scenario.state, scenario.config) if action.resolution is resolution
    ]
    return scenario, actions


def _building_bonus_event(events):
    return next(event for event in events if event.event_type is EventType.BUILDING_BONUS)


def test_allocation_active_infirmary_increases_effective_duty_value_and_enables_extra_move() -> None:
    scenario, allocation_actions = _actions_for_resolution(
        "scenarios/allocation_infirmary_001.json",
        TurnResolutionType.ALLOCATION,
    )

    assert any(len(action.allocation_moves) == 2 for action in allocation_actions)
    assert all(len(action.allocation_moves) <= 2 for action in allocation_actions)

    action = next(action for action in allocation_actions if len(action.allocation_moves) == 2)
    result = apply_action(scenario.state, action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    bonus_event = _building_bonus_event(result.events)
    bonus_details = dict(bonus_event.details)
    allocation_events = [event for event in result.events if event.event_type is EventType.ALLOCATION]
    duty_index = result.events.index(duty_event)
    bonus_index = result.events.index(bonus_event)
    first_allocation_index = min(result.events.index(event) for event in allocation_events)

    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 2
    assert bonus_details["building"] == "infirmary"
    assert bonus_details["action"] == "allocation"
    assert bonus_details["duty_value_bonus"] == 1
    assert len(allocation_events) == 2
    assert duty_index < bonus_index < first_allocation_index


def test_allocation_donated_infirmary_does_not_apply() -> None:
    scenario, allocation_actions = _actions_for_resolution(
        "scenarios/allocation_infirmary_donated_001.json",
        TurnResolutionType.ALLOCATION,
    )

    assert allocation_actions
    assert all(len(action.allocation_moves) == 1 for action in allocation_actions)
    action = allocation_actions[0]
    result = apply_action(scenario.state, action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)

    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 1
    assert not any(event.event_type is EventType.BUILDING_BONUS for event in result.events)


def test_allocation_infirmary_in_market_does_not_apply() -> None:
    scenario = load_scenario("scenarios/allocation_abbey_to_special_activity_001.json")
    market = list(scenario.state.building_market)
    market[0] = "infirmary"
    state_with_market_infirmary = scenario.state.with_building_market(tuple(market))
    allocation_actions = [
        action
        for action in legal_actions(state_with_market_infirmary, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]

    assert allocation_actions
    assert all(len(action.allocation_moves) == 1 for action in allocation_actions)


def test_ordination_active_infirmary_enables_extra_paid_step() -> None:
    scenario, ordination_actions = _actions_for_resolution(
        "scenarios/ordination_infirmary_extra_step_001.json",
        TurnResolutionType.ORDINATION,
    )
    step_sequences = {action.ordination_steps for action in ordination_actions}

    assert ("ordain", "mission") in step_sequences
    assert all(len(action.ordination_steps) <= 2 for action in ordination_actions)

    action = next(action for action in ordination_actions if action.ordination_steps == ("ordain", "mission"))
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    bonus_event = _building_bonus_event(result.events)
    bonus_details = dict(bonus_event.details)
    ordination_events = [event for event in result.events if event.event_type is EventType.ORDINATION]
    duty_index = result.events.index(duty_event)
    bonus_index = result.events.index(bonus_event)
    first_ordination_index = min(result.events.index(event) for event in ordination_events)

    assert after_player.resources.wheat == 0
    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 2
    assert bonus_details["building"] == "infirmary"
    assert bonus_details["action"] == "ordination"
    assert bonus_details["duty_value_bonus"] == 1
    assert bonus_details["extra_wheat_cost_paid"] is True
    assert duty_index < bonus_index < first_ordination_index


def test_ordination_infirmary_insufficient_wheat_blocks_extra_step_and_no_bonus_event() -> None:
    scenario, ordination_actions = _actions_for_resolution(
        "scenarios/ordination_infirmary_insufficient_wheat_001.json",
        TurnResolutionType.ORDINATION,
    )

    assert ordination_actions
    assert all(len(action.ordination_steps) == 1 for action in ordination_actions)
    action = ordination_actions[0]
    result = apply_action(scenario.state, action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)

    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 1
    assert not any(event.event_type is EventType.BUILDING_BONUS for event in result.events)


def test_ordination_donated_infirmary_does_not_apply() -> None:
    _scenario, ordination_actions = _actions_for_resolution(
        "scenarios/ordination_infirmary_donated_001.json",
        TurnResolutionType.ORDINATION,
    )
    step_sequences = {action.ordination_steps for action in ordination_actions}

    assert step_sequences == {("ordain",)}


def test_ordination_infirmary_in_market_does_not_apply() -> None:
    scenario = load_scenario("scenarios/ordination_ordain_then_mission_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    boosted_player_one = replace(
        player_one,
        resources=Resources(
            stone=player_one.resources.stone,
            silver=player_one.resources.silver,
            wheat=3,
        ),
        workforce=replace(player_one.workforce, village=2),
    )
    market = list(scenario.state.building_market)
    market[0] = "infirmary"
    state_with_market_infirmary = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        boosted_player_one,
    ).with_building_market(tuple(market))

    ordination_actions = [
        action
        for action in legal_actions(state_with_market_infirmary, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]

    assert ordination_actions
    assert all(len(action.ordination_steps) <= 2 for action in ordination_actions)
    assert not any(len(action.ordination_steps) == 3 for action in ordination_actions)
