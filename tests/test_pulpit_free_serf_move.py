from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _pulpit_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    pulpit_actions = [
        action for action in actions if action.workforce_move_building_id == "pulpit"
    ]
    return scenario, actions, pulpit_actions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_pulpit_generates_workforce_move_variants() -> None:
    _scenario, actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_active_move_serf_001.json"
    )

    assert pulpit_actions
    assert all(
        action.workforce_move_building_source == "own_active" for action in pulpit_actions
    )
    assert all(action.workforce_move_building_id == "pulpit" for action in pulpit_actions)
    assert any(action.workforce_move_building_id is None for action in actions)


def test_own_active_pulpit_generates_no_variants_when_village_has_no_serfs() -> None:
    _scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_no_village_serf_no_modifier_001.json"
    )
    assert pulpit_actions == []


def test_own_active_pulpit_works_when_merchant_resource_is_none() -> None:
    scenario = load_scenario("scenarios/pulpit_active_move_serf_001.json")
    taxation_state = replace(scenario.state, merchant_position=0)
    actions = legal_actions(taxation_state, scenario.config)
    pulpit_actions = [
        action for action in actions if action.workforce_move_building_id == "pulpit"
    ]

    assert pulpit_actions
    assert all(
        action.workforce_move_building_source == "own_active" for action in pulpit_actions
    )


def test_own_active_pulpit_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/pulpit_hire_market_move_serf_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_pulpit = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("pulpit",),
            ),
        ),
    )
    actions = legal_actions(state_with_own_pulpit, scenario.config)
    pulpit_actions = [
        action for action in actions if action.workforce_move_building_id == "pulpit"
    ]

    assert pulpit_actions
    assert all(
        action.workforce_move_building_source == "own_active" for action in pulpit_actions
    )


def test_hired_market_pulpit_generates_variants_when_payable() -> None:
    _scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_hire_market_move_serf_001.json"
    )

    assert pulpit_actions
    assert all(
        action.workforce_move_building_source == "market" for action in pulpit_actions
    )


def test_hired_opponent_pulpit_generates_variants_when_payable() -> None:
    _scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_hire_opponent_move_serf_001.json"
    )

    assert pulpit_actions
    assert all(
        action.workforce_move_building_source == "player_two" for action in pulpit_actions
    )


def test_merchant_none_insufficient_donated_not_live_and_no_village_block_pulpit() -> None:
    blocked_paths = (
        "scenarios/pulpit_merchant_none_no_hire_001.json",
        "scenarios/pulpit_insufficient_hire_resource_001.json",
        "scenarios/pulpit_donated_no_modifier_001.json",
        "scenarios/pulpit_not_live_no_modifier_001.json",
        "scenarios/pulpit_no_village_serf_no_modifier_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, pulpit_actions = _pulpit_actions(path)
        assert pulpit_actions == []
        assert any(action.workforce_move_building_id is None for action in actions)


def test_apply_own_active_pulpit_moves_exactly_one_serf_before_sowing_without_wheat_cost() -> None:
    scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_active_move_serf_001.json"
    )
    action = _first_action(
        pulpit_actions,
        lambda candidate: (
            candidate.workforce_move_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "pulpit",
    )
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    workforce_details = dict(workforce_event.details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert before_player.resources.wheat == after_player.resources.wheat
    assert after_player.workforce.village == before_player.workforce.village - 1
    assert after_player.workforce.abbey == before_player.workforce.abbey + 1
    assert workforce_details["amount"] == 1
    assert workforce_details["from_pool"] == "village"
    assert workforce_details["to_pool"] == "abbey"
    assert workforce_details["wheat_paid"] == 0
    assert result.events.index(bonus_event) < result.events.index(workforce_event)
    assert result.events.index(workforce_event) < result.events.index(sowing_event)
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_hired_market_pulpit_pays_bank_before_free_move() -> None:
    scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_hire_market_move_serf_001.json"
    )
    action = _first_action(
        pulpit_actions,
        lambda candidate: (
            candidate.workforce_move_building_source == "market"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "pulpit",
    )
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "pulpit"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(workforce_event)
    assert result.events.index(workforce_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_hired_opponent_pulpit_pays_owner_before_free_move() -> None:
    scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_hire_opponent_move_serf_001.json"
    )
    action = _first_action(
        pulpit_actions,
        lambda candidate: (
            candidate.workforce_move_building_source == "player_two"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "silver"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_hired_pulpit_when_hire_payment_is_unaffordable() -> None:
    scenario = load_scenario("scenarios/pulpit_insufficient_hire_resource_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(
        actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE
    )
    invalid_action = replace(
        base_action,
        workforce_move_building_id="pulpit",
        workforce_move_building_source="market",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Pulpit is unavailable in current state",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_action_summary_includes_pulpit_modifier_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_active_move_serf_001.json"
    )
    own_action = _first_action(
        own_pulpit_actions,
        lambda candidate: (
            candidate.workforce_move_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert "use building: pulpit to move 1 serf village -> abbey for free" in own_summary
    assert "hire building: pulpit" not in own_summary

    hired_scenario, _hired_actions, hired_pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_hire_market_move_serf_001.json"
    )
    hired_action = _first_action(
        hired_pulpit_actions,
        lambda candidate: (
            candidate.workforce_move_building_source == "market"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert "use building: pulpit to move 1 serf village -> abbey for free" in hired_summary
    assert "hire building: pulpit from market" in hired_summary


def test_pulpit_and_infirmary_do_not_stack_free_village_to_abbey_move() -> None:
    scenario, actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_infirmary_does_not_double_free_move_001.json"
    )
    ordination_actions = [
        action
        for action in pulpit_actions
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    assert ordination_actions
    assert all(len(action.ordination_steps) <= 2 for action in ordination_actions)
    assert not any(len(action.ordination_steps) > 2 for action in ordination_actions)
    assert any(len(action.ordination_steps) == 2 for action in ordination_actions)

    action = _first_action(ordination_actions, lambda candidate: len(candidate.ordination_steps) == 2)
    result = apply_action(scenario.state, action, scenario.config)
    workforce_events = _events_of_type(result.events, EventType.WORKFORCE_MOVE)
    ordination_events = _events_of_type(result.events, EventType.ORDINATION)
    duty_event = _events_of_type(result.events, EventType.DUTY_RESOLUTION)[0]
    duty_details = dict(duty_event.details)

    assert len(workforce_events) == 1
    workforce_details = dict(workforce_events[0].details)
    assert workforce_details["amount"] == 1
    assert workforce_details["from_pool"] == "village"
    assert workforce_details["to_pool"] == "abbey"
    assert workforce_details["wheat_paid"] == 0
    assert len(ordination_events) == 2
    assert all(dict(event.details)["wheat_paid"] == 1 for event in ordination_events)
    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    assert result.events.index(workforce_events[0]) < result.events.index(sowing_event)

    non_pulpit_ordination_actions = [
        action
        for action in actions
        if action.workforce_move_building_id is None
        and action.resolution is TurnResolutionType.ORDINATION
    ]
    assert non_pulpit_ordination_actions


def test_pulpit_does_not_make_ordination_steps_free() -> None:
    scenario, _actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_plus_ordination_paid_step_001.json"
    )
    ordain_action = _first_action(
        pulpit_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain",)
        ),
    )
    result = apply_action(scenario.state, ordain_action, scenario.config)
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    ordination_event = _events_of_type(result.events, EventType.ORDINATION)[0]
    duty_event = _events_of_type(result.events, EventType.DUTY_RESOLUTION)[0]

    assert dict(workforce_event.details)["wheat_paid"] == 0
    assert dict(ordination_event.details)["wheat_paid"] == 1
    assert dict(duty_event.details)["effective_duty_value"] == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_when_pulpit_is_unavailable_legal_actions_remain_non_pulpit() -> None:
    _scenario, actions, pulpit_actions = _pulpit_actions(
        "scenarios/pulpit_not_live_no_modifier_001.json"
    )
    assert pulpit_actions == []
    assert actions
