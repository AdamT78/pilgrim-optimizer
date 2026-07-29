from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _customs_house_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    customs_house_actions = [
        action
        for action in actions
        if action.taxation_majority_building_id == "customs_house"
    ]
    return scenario, actions, customs_house_actions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_customs_house_generates_taxation_variants() -> None:
    _scenario, actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_majority_001.json"
    )

    assert customs_house_actions
    assert all(
        action.taxation_majority_building_source == "own_active"
        for action in customs_house_actions
    )
    assert all(
        action.taxation_majority_building_id == "customs_house"
        for action in customs_house_actions
    )
    assert any(action.taxation_majority_building_id is None for action in actions)


def test_own_active_customs_house_works_when_merchant_resource_is_none() -> None:
    _scenario, _actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_majority_001.json"
    )

    assert customs_house_actions
    assert all(
        action.taxation_majority_building_source == "own_active"
        for action in customs_house_actions
    )


def test_own_active_customs_house_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/customs_house_hire_market_taxation_majority_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_customs_house = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("customs_house",),
            ),
        ),
    )
    actions = legal_actions(state_with_own_customs_house, scenario.config)
    customs_house_actions = [
        action
        for action in actions
        if action.taxation_majority_building_id == "customs_house"
    ]

    assert customs_house_actions
    assert all(
        action.taxation_majority_building_source == "own_active"
        for action in customs_house_actions
    )


def test_hired_market_customs_house_generates_variants_when_payable() -> None:
    _scenario, _actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_hire_market_taxation_majority_001.json"
    )

    assert customs_house_actions
    assert all(
        action.taxation_majority_building_source == "market"
        for action in customs_house_actions
    )


def test_hired_opponent_customs_house_generates_variants_when_payable() -> None:
    _scenario, _actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_hire_opponent_taxation_majority_001.json"
    )

    assert customs_house_actions
    assert all(
        action.taxation_majority_building_source == "player_two"
        for action in customs_house_actions
    )


def test_merchant_none_insufficient_donated_and_not_live_block_hired_customs_house() -> None:
    blocked_paths = (
        "scenarios/customs_house_merchant_none_no_hire_001.json",
        "scenarios/customs_house_insufficient_hire_resource_001.json",
        "scenarios/customs_house_donated_no_modifier_001.json",
        "scenarios/customs_house_not_live_no_modifier_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, customs_house_actions = _customs_house_actions(path)
        assert customs_house_actions == []
        assert any(action.taxation_majority_building_id is None for action in actions)


def test_customs_house_is_not_generated_when_no_taxation_action_exists() -> None:
    _scenario, actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_no_taxation_no_modifier_001.json"
    )
    assert customs_house_actions == []
    assert all(
        action.resolution is not TurnResolutionType.TAXATION
        for action in actions
    )


def test_customs_house_prunes_non_taxation_variants() -> None:
    _scenario, actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_majority_001.json"
    )

    assert any(
        action.taxation_majority_building_id is None
        and action.resolution is TurnResolutionType.TITHE
        for action in actions
    )
    assert all(
        action.resolution is TurnResolutionType.TAXATION
        for action in customs_house_actions
    )


def test_non_customs_house_taxation_actions_remain_legal() -> None:
    _scenario, actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_majority_001.json"
    )

    plain_taxation_actions = [
        action
        for action in actions
        if action.taxation_majority_building_id is None
        and action.resolution is TurnResolutionType.TAXATION
    ]
    assert plain_taxation_actions
    assert customs_house_actions


def test_customs_house_taxation_claims_majority_and_unlocks_bonus_tiles() -> None:
    scenario, actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_majority_001.json"
    )
    plain_action = _first_action(
        actions,
        lambda candidate: (
            candidate.taxation_majority_building_id is None
            and candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
            and candidate.taxation_step2_resources == ()
        ),
    )
    boosted_action = _first_action(
        customs_house_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
            and candidate.taxation_step2_resources == ("stone", "silver")
        ),
    )

    plain_result = apply_action(scenario.state, plain_action, scenario.config)
    boosted_result = apply_action(scenario.state, boosted_action, scenario.config)
    plain_duty = _events_of_type(plain_result.events, EventType.DUTY_RESOLUTION)[0]
    boosted_duty = _events_of_type(boosted_result.events, EventType.DUTY_RESOLUTION)[0]
    plain_tax_step2 = _first_action(
        _events_of_type(plain_result.events, EventType.TAXATION),
        lambda event: dict(event.details).get("step") == "step_2",
    )
    boosted_tax_step2 = _first_action(
        _events_of_type(boosted_result.events, EventType.TAXATION),
        lambda event: dict(event.details).get("step") == "step_2",
    )
    plain_resource = _events_of_type(plain_result.events, EventType.RESOURCE_DELTA)[0]
    boosted_resource = _events_of_type(boosted_result.events, EventType.RESOURCE_DELTA)[0]

    assert dict(plain_duty.details)["strength"] == "parity"
    assert dict(plain_duty.details)["duty_value"] == 1
    assert dict(boosted_duty.details)["strength"] == "majority"
    assert dict(boosted_duty.details)["duty_value"] == 2
    assert dict(plain_tax_step2.details)["no_bonus"] is True
    assert dict(boosted_tax_step2.details)["resources"] == "stone,silver"
    assert dict(plain_resource.details)["stone"] == 0
    assert dict(plain_resource.details)["silver"] == 0
    assert dict(plain_resource.details)["wheat"] == 1
    assert dict(boosted_resource.details)["stone"] == 1
    assert dict(boosted_resource.details)["silver"] == 1
    assert dict(boosted_resource.details)["wheat"] == 1
    assert boosted_result.state.player_vector(PlayerId.PLAYER_ONE) == plain_result.state.player_vector(
        PlayerId.PLAYER_ONE
    )
    invariant_event = _events_of_type(boosted_result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_customs_house_selected_taxation_beats_larger_opponent_stack() -> None:
    scenario, actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_beats_larger_stack_001.json"
    )
    plain_action = _first_action(
        actions,
        lambda candidate: (
            candidate.taxation_majority_building_id is None
            and candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
            and candidate.taxation_step2_resources == ()
        ),
    )
    boosted_action = _first_action(
        customs_house_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
            and candidate.taxation_step2_resources == ("stone", "silver")
        ),
    )

    plain_result = apply_action(scenario.state, plain_action, scenario.config)
    boosted_result = apply_action(scenario.state, boosted_action, scenario.config)
    plain_duty = _events_of_type(plain_result.events, EventType.DUTY_RESOLUTION)[0]
    boosted_duty = _events_of_type(boosted_result.events, EventType.DUTY_RESOLUTION)[0]

    assert dict(plain_duty.details)["strength"] == "minority"
    assert dict(plain_duty.details)["duty_value"] == 1
    assert dict(plain_duty.details)["silver_cost"] == 1
    assert dict(boosted_duty.details)["strength"] == "majority"
    assert dict(boosted_duty.details)["duty_value"] == 2
    assert dict(boosted_duty.details)["silver_cost"] == 0


def test_taxation_without_customs_house_remains_non_majority() -> None:
    scenario = load_scenario(
        "scenarios/customs_house_taxation_without_modifier_remains_non_majority_001.json"
    )
    actions = legal_actions(scenario.state, scenario.config)
    taxation_actions = [
        action for action in actions if action.resolution is TurnResolutionType.TAXATION
    ]

    assert taxation_actions
    assert all(action.taxation_step2_resources == () for action in taxation_actions)
    action = _first_action(
        taxation_actions,
        lambda candidate: candidate.taxation_step1_resource == "wheat",
    )
    result = apply_action(scenario.state, action, scenario.config)
    duty_event = _events_of_type(result.events, EventType.DUTY_RESOLUTION)[0]
    tax_step2_event = _first_action(
        _events_of_type(result.events, EventType.TAXATION),
        lambda event: dict(event.details).get("step") == "step_2",
    )

    assert dict(duty_event.details)["strength"] == "parity"
    assert dict(duty_event.details)["duty_value"] == 1
    assert dict(tax_step2_event.details)["no_bonus"] is True


def test_hired_market_customs_house_pays_bank_before_sowing() -> None:
    scenario, _actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_hire_market_taxation_majority_001.json"
    )
    action = _first_action(
        customs_house_actions,
        lambda candidate: (
            candidate.taxation_majority_building_source == "market"
            and candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "customs_house",
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "customs_house"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1


def test_hired_opponent_customs_house_pays_owner_before_sowing() -> None:
    scenario, _actions, customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_hire_opponent_taxation_majority_001.json"
    )
    action = _first_action(
        customs_house_actions,
        lambda candidate: (
            candidate.taxation_majority_building_source == "player_two"
            and candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "silver"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_unavailable_customs_house_source() -> None:
    scenario = load_scenario("scenarios/customs_house_insufficient_hire_resource_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(
        actions, lambda candidate: candidate.resolution is TurnResolutionType.TAXATION
    )
    invalid_action = replace(
        base_action,
        taxation_majority_building_id="customs_house",
        taxation_majority_building_source="market",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Customs House is unavailable in current state",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_invalid_customs_house_field_values() -> None:
    scenario = load_scenario("scenarios/customs_house_active_taxation_majority_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(
        actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_majority_building_id is None
        ),
    )
    invalid_building = replace(
        base_action,
        taxation_majority_building_id="scriptorium",
        taxation_majority_building_source="own_active",
    )
    invalid_source = replace(
        base_action,
        taxation_majority_building_id="customs_house",
        taxation_majority_building_source="market",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Only Customs House is supported for taxation_majority_building fields",
    ):
        apply_action(scenario.state, invalid_building, scenario.config)
    with pytest.raises(
        TransitionValidationError,
        match="Own-active Customs House Taxation modifier must set source=own_active",
    ):
        apply_action(scenario.state, invalid_source, scenario.config)


def test_apply_rejects_customs_house_on_non_taxation_action() -> None:
    scenario = load_scenario("scenarios/customs_house_no_taxation_no_modifier_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(
        actions, lambda candidate: candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION
    )
    invalid_action = replace(
        base_action,
        taxation_majority_building_id="customs_house",
        taxation_majority_building_source="own_active",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Customs House Taxation modifier can only be used with taxation actions",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_action_summary_includes_customs_house_modifier_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_active_taxation_majority_001.json"
    )
    own_action = _first_action(
        own_customs_house_actions,
        lambda candidate: (
            candidate.taxation_majority_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
        ),
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert "use building: customs_house for Taxation majority on occupied Duty tiles" in own_summary
    assert "| selected duty: north (taxation) | action: taxation" in own_summary
    assert "|action: taxation" not in own_summary
    assert "hire building: customs_house" not in own_summary

    hired_scenario, _hired_actions, hired_customs_house_actions = _customs_house_actions(
        "scenarios/customs_house_hire_market_taxation_majority_001.json"
    )
    hired_action = _first_action(
        hired_customs_house_actions,
        lambda candidate: (
            candidate.taxation_majority_building_source == "market"
            and candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert "use building: customs_house for Taxation majority on occupied Duty tiles" in hired_summary
    assert "| selected duty: north (taxation) | action: taxation" in hired_summary
    assert "|action: taxation" not in hired_summary
    assert "hire building: customs_house from market" in hired_summary
