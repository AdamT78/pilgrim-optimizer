from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _scriptorium_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    scriptorium_actions = [
        action
        for action in actions
        if action.effective_acolyte_building_id == "scriptorium"
    ]
    return scenario, actions, scriptorium_actions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_scriptorium_generates_effective_acolyte_variants() -> None:
    _scenario, actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_active_majority_selected_duty_001.json"
    )

    assert scriptorium_actions
    assert all(
        action.effective_acolyte_building_source == "own_active"
        for action in scriptorium_actions
    )
    assert all(
        action.effective_acolyte_building_id == "scriptorium"
        for action in scriptorium_actions
    )
    assert any(action.effective_acolyte_building_id is None for action in actions)


def test_own_active_scriptorium_works_when_merchant_resource_is_none() -> None:
    scenario = load_scenario("scenarios/scriptorium_active_majority_selected_duty_001.json")
    taxation_state = replace(scenario.state, merchant_position=0)
    actions = legal_actions(taxation_state, scenario.config)
    scriptorium_actions = [
        action
        for action in actions
        if action.effective_acolyte_building_id == "scriptorium"
    ]

    assert scriptorium_actions
    assert all(
        action.effective_acolyte_building_source == "own_active"
        for action in scriptorium_actions
    )


def test_own_active_scriptorium_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/scriptorium_hire_market_majority_selected_duty_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_scriptorium = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("scriptorium",),
            ),
        ),
    )
    actions = legal_actions(state_with_own_scriptorium, scenario.config)
    scriptorium_actions = [
        action
        for action in actions
        if action.effective_acolyte_building_id == "scriptorium"
    ]

    assert scriptorium_actions
    assert all(
        action.effective_acolyte_building_source == "own_active"
        for action in scriptorium_actions
    )


def test_hired_market_scriptorium_generates_variants_when_payable() -> None:
    _scenario, _actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_hire_market_majority_selected_duty_001.json"
    )

    assert scriptorium_actions
    assert all(
        action.effective_acolyte_building_source == "market"
        for action in scriptorium_actions
    )


def test_hired_opponent_scriptorium_generates_variants_when_payable() -> None:
    _scenario, _actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json"
    )

    assert scriptorium_actions
    assert all(
        action.effective_acolyte_building_source == "player_two"
        for action in scriptorium_actions
    )


def test_merchant_none_insufficient_donated_not_live_and_no_occupancy_block_scriptorium() -> None:
    blocked_paths = (
        "scenarios/scriptorium_merchant_none_no_hire_001.json",
        "scenarios/scriptorium_insufficient_hire_resource_001.json",
        "scenarios/scriptorium_donated_no_modifier_001.json",
        "scenarios/scriptorium_not_live_no_modifier_001.json",
        "scenarios/scriptorium_no_occupied_duty_no_modifier_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, scriptorium_actions = _scriptorium_actions(path)
        assert scriptorium_actions == []
        assert all(action.effective_acolyte_building_id is None for action in actions)


def test_scriptorium_turn_changes_selected_duty_relation_without_physical_acolyte_changes() -> None:
    scenario, actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_active_majority_selected_duty_001.json"
    )
    base_action = _first_action(
        actions,
        lambda candidate: (
            candidate.effective_acolyte_building_id is None
            and candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION
        ),
    )
    boosted_action = _first_action(
        scriptorium_actions,
        lambda candidate: candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION,
    )

    base_result = apply_action(scenario.state, base_action, scenario.config)
    boosted_result = apply_action(scenario.state, boosted_action, scenario.config)
    base_duty = _events_of_type(base_result.events, EventType.DUTY_RESOLUTION)[0]
    boosted_duty = _events_of_type(boosted_result.events, EventType.DUTY_RESOLUTION)[0]
    base_duty_details = dict(base_duty.details)
    boosted_duty_details = dict(boosted_duty.details)

    assert base_duty_details["strength"] == "parity"
    assert base_duty_details["duty_value"] == 1
    assert boosted_duty_details["strength"] == "majority"
    assert boosted_duty_details["duty_value"] == 2
    assert boosted_result.state.player_state(PlayerId.PLAYER_ONE).piety == 2
    assert base_result.state.player_state(PlayerId.PLAYER_ONE).piety == 1
    assert boosted_result.state.player_vector(PlayerId.PLAYER_ONE) == base_result.state.player_vector(
        PlayerId.PLAYER_ONE
    )


def test_hired_market_scriptorium_pays_bank_before_sowing() -> None:
    scenario, _actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_hire_market_majority_selected_duty_001.json"
    )
    action = _first_action(
        scriptorium_actions,
        lambda candidate: (
            candidate.effective_acolyte_building_source == "market"
            and candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "scriptorium",
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "scriptorium"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_hired_opponent_scriptorium_pays_owner_before_sowing() -> None:
    scenario, _actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json"
    )
    action = _first_action(
        scriptorium_actions,
        lambda candidate: (
            candidate.effective_acolyte_building_source == "player_two"
            and candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "silver"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_unavailable_scriptorium_source() -> None:
    scenario = load_scenario("scenarios/scriptorium_insufficient_hire_resource_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(
        actions,
        lambda candidate: candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION,
    )
    invalid_action = replace(
        base_action,
        effective_acolyte_building_id="scriptorium",
        effective_acolyte_building_source="market",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Scriptorium is unavailable in current state",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_action_summary_includes_scriptorium_modifier_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_active_majority_selected_duty_001.json"
    )
    own_action = _first_action(
        own_scriptorium_actions,
        lambda candidate: candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION,
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert (
        "use building: scriptorium for +1 effective acolyte on occupied Duty tiles"
        in own_summary
    )
    assert "hire building: scriptorium" not in own_summary

    hired_scenario, _hired_actions, hired_scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_hire_market_majority_selected_duty_001.json"
    )
    hired_action = _first_action(
        hired_scriptorium_actions,
        lambda candidate: (
            candidate.effective_acolyte_building_source == "market"
            and candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert (
        "use building: scriptorium for +1 effective acolyte on occupied Duty tiles"
        in hired_summary
    )
    assert "hire building: scriptorium from market" in hired_summary


def test_scriptorium_taxation_majority_applies_to_selected_and_other_occupied_duties() -> None:
    scenario, actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_taxation_majority_other_tiles_001.json"
    )

    plain_taxation_actions = [
        action
        for action in actions
        if action.effective_acolyte_building_id is None
        and action.resolution is TurnResolutionType.TAXATION
    ]
    boosted_taxation_actions = [
        action
        for action in scriptorium_actions
        if action.resolution is TurnResolutionType.TAXATION
    ]

    assert plain_taxation_actions
    assert boosted_taxation_actions
    assert all(action.taxation_step2_resources == () for action in plain_taxation_actions)
    boosted_step2_choices = {
        action.taxation_step2_resources
        for action in boosted_taxation_actions
        if action.taxation_step1_resource == "wheat"
    }
    assert boosted_step2_choices == {
        ("stone", "stone"),
        ("stone", "silver"),
        ("silver", "silver"),
    }

    plain_action = _first_action(
        plain_taxation_actions,
        lambda candidate: candidate.taxation_step1_resource == "wheat"
        and candidate.taxation_step2_resources == (),
    )
    boosted_action = _first_action(
        boosted_taxation_actions,
        lambda candidate: candidate.taxation_step1_resource == "wheat"
        and candidate.taxation_step2_resources == ("stone", "silver"),
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


def test_scriptorium_prunes_tithe_and_give_alms_donate_building_no_op_variants() -> None:
    _scenario, actions, scriptorium_actions = _scriptorium_actions(
        "scenarios/scriptorium_taxation_majority_other_tiles_001.json"
    )

    assert any(
        action.effective_acolyte_building_id is None
        and action.resolution is TurnResolutionType.TITHE
        for action in actions
    )
    assert any(
        action.effective_acolyte_building_id is None
        and action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
        for action in actions
    )
    assert all(
        action.resolution is not TurnResolutionType.TITHE for action in scriptorium_actions
    )
    assert all(
        action.resolution is not TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
        for action in scriptorium_actions
    )


def test_taxation_without_scriptorium_stays_parity_and_has_no_step2_bonus() -> None:
    scenario = load_scenario("scenarios/scriptorium_taxation_without_modifier_remains_parity_001.json")
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
