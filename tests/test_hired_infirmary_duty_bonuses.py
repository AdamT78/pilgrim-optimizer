from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _actions_for_resolution(path: str, resolution: TurnResolutionType):
    scenario = load_scenario(path)
    actions = [
        action for action in legal_actions(scenario.state, scenario.config) if action.resolution is resolution
    ]
    return scenario, actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def test_allocation_market_hired_infirmary_enables_extra_move_and_pays_bank() -> None:
    scenario, actions = _actions_for_resolution(
        "scenarios/allocation_hire_infirmary_market_001.json",
        TurnResolutionType.ALLOCATION,
    )
    hired_actions = [action for action in actions if action.hired_building_id == "infirmary"]

    assert any(len(action.allocation_moves) == 2 for action in hired_actions)
    assert not any(len(action.allocation_moves) == 1 for action in hired_actions)
    action = next(action for action in hired_actions if len(action.allocation_moves) == 2)
    result = apply_action(scenario.state, action, scenario.config)

    duty_event = _events_of_type(result.events, EventType.DUTY_RESOLUTION)[0]
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    allocation_events = _events_of_type(result.events, EventType.ALLOCATION)
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]

    duty_details = dict(duty_event.details)
    hired_details = dict(hired_event.details)
    bonus_details = dict(bonus_event.details)
    delta_details = dict(delta_event.details)

    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 2
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert bonus_details["building"] == "infirmary"
    assert bonus_details["duty_value_bonus"] == 1
    assert delta_details["wheat"] == -1
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(allocation_events[0])
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_allocation_opponent_hired_infirmary_pays_owner() -> None:
    scenario, actions = _actions_for_resolution(
        "scenarios/allocation_hire_infirmary_opponent_001.json",
        TurnResolutionType.ALLOCATION,
    )
    action = next(action for action in actions if action.hired_building_id == "infirmary")
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_allocation_own_active_infirmary_remains_free() -> None:
    scenario, actions = _actions_for_resolution(
        "scenarios/allocation_infirmary_001.json",
        TurnResolutionType.ALLOCATION,
    )
    action = next(action for action in actions if len(action.allocation_moves) == 2)
    result = apply_action(scenario.state, action, scenario.config)

    assert action.hired_building_id is None
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert _events_of_type(result.events, EventType.BUILDING_BONUS)


def test_allocation_hired_infirmary_blocked_by_merchant_none() -> None:
    _scenario, actions = _actions_for_resolution(
        "scenarios/allocation_hire_infirmary_merchant_none_001.json",
        TurnResolutionType.ALLOCATION,
    )

    assert all(action.hired_building_id is None for action in actions)
    assert all(len(action.allocation_moves) == 1 for action in actions)


def test_allocation_hired_infirmary_blocked_by_insufficient_resource() -> None:
    _scenario, actions = _actions_for_resolution(
        "scenarios/allocation_hire_infirmary_insufficient_resource_001.json",
        TurnResolutionType.ALLOCATION,
    )

    assert all(action.hired_building_id is None for action in actions)
    assert all(len(action.allocation_moves) == 1 for action in actions)


def test_allocation_donated_or_not_live_infirmary_is_unavailable() -> None:
    scenario = load_scenario("scenarios/allocation_hire_infirmary_market_001.json")
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    donated_state = scenario.state.with_building_market(()).with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            player_board_slots=replace(
                player_two.player_board_slots,
                donated_buildings=("infirmary",),
            ),
        ),
    )
    donated_actions = [
        action
        for action in legal_actions(donated_state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]
    assert all(action.hired_building_id is None for action in donated_actions)

    not_live_state = scenario.state.with_building_availability((("infirmary", 7),))
    not_live_actions = [
        action
        for action in legal_actions(not_live_state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]
    assert all(action.hired_building_id is None for action in not_live_actions)


def test_ordination_market_hired_infirmary_enables_extra_paid_step() -> None:
    scenario, actions = _actions_for_resolution(
        "scenarios/ordination_hire_infirmary_market_extra_step_001.json",
        TurnResolutionType.ORDINATION,
    )
    hired_actions = [action for action in actions if action.hired_building_id == "infirmary"]

    assert any(len(action.ordination_steps) == 2 for action in hired_actions)
    assert not any(len(action.ordination_steps) == 1 for action in hired_actions)
    action = next(action for action in hired_actions if len(action.ordination_steps) == 2)
    result = apply_action(scenario.state, action, scenario.config)

    duty_event = _events_of_type(result.events, EventType.DUTY_RESOLUTION)[0]
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    ordination_events = _events_of_type(result.events, EventType.ORDINATION)
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]

    duty_details = dict(duty_event.details)
    bonus_details = dict(bonus_event.details)
    hired_details = dict(hired_event.details)
    delta_details = dict(delta_event.details)

    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 2
    assert hired_details["source"] == "market"
    assert hired_details["resource"] == "wheat"
    assert bonus_details["building"] == "infirmary"
    assert bonus_details["extra_wheat_cost_paid"] is True
    assert delta_details["wheat"] == -3
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(ordination_events[0])
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_ordination_opponent_hired_infirmary_pays_owner() -> None:
    scenario, actions = _actions_for_resolution(
        "scenarios/ordination_hire_infirmary_opponent_extra_step_001.json",
        TurnResolutionType.ORDINATION,
    )
    action = next(
        action
        for action in actions
        if action.hired_building_id == "infirmary" and len(action.ordination_steps) == 2
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_ordination_hired_infirmary_blocked_when_wheat_insufficient() -> None:
    _scenario, actions = _actions_for_resolution(
        "scenarios/ordination_hire_infirmary_insufficient_wheat_001.json",
        TurnResolutionType.ORDINATION,
    )

    assert all(action.hired_building_id is None for action in actions)
    assert all(len(action.ordination_steps) == 1 for action in actions)


def test_ordination_hired_infirmary_blocked_by_merchant_none() -> None:
    _scenario, actions = _actions_for_resolution(
        "scenarios/ordination_hire_infirmary_merchant_none_001.json",
        TurnResolutionType.ORDINATION,
    )

    assert all(action.hired_building_id is None for action in actions)
    assert all(len(action.ordination_steps) == 1 for action in actions)


def test_ordination_own_active_infirmary_behavior_is_unchanged() -> None:
    scenario, actions = _actions_for_resolution(
        "scenarios/ordination_infirmary_extra_step_001.json",
        TurnResolutionType.ORDINATION,
    )
    action = next(action for action in actions if action.ordination_steps == ("ordain", "mission"))
    result = apply_action(scenario.state, action, scenario.config)

    assert action.hired_building_id is None
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert _events_of_type(result.events, EventType.BUILDING_BONUS)

