from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import (
    TransitionValidationError,
    _costs_with_bank_substitution,
    apply_action,
    legal_actions,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def _bank_actions(path: str):
    scenario = load_scenario(path)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    ]
    bank_actions = [action for action in actions if action.bank_payment_building_id == "bank"]
    return scenario, actions, bank_actions


def test_own_active_bank_generates_partial_and_full_ordination_substitution_variants() -> None:
    _scenario, actions, bank_actions = _bank_actions(
        "scenarios/bank_active_ordination_substitution_001.json"
    )
    two_step_bank_variants = [
        action
        for action in bank_actions
        if action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
    ]

    assert two_step_bank_variants
    assert {
        action.bank_payment_silver_amount for action in two_step_bank_variants
    } == {1}
    assert all(action.bank_payment_replaced_resource == "wheat" for action in two_step_bank_variants)
    assert all(action.bank_payment_building_source == "own_active" for action in two_step_bank_variants)
    assert not any(
        action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
        and action.bank_payment_building_id is None
        for action in actions
    )

    _scenario_full, actions_full, bank_actions_full = _bank_actions(
        "scenarios/bank_active_ordination_full_substitution_001.json"
    )
    full_two_step_variants = [
        action
        for action in bank_actions_full
        if action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
    ]
    assert {action.bank_payment_silver_amount for action in full_two_step_variants} == {2}
    assert not any(
        action.resolution is TurnResolutionType.ORDINATION
        and action.ordination_steps == ("ordain", "ordain")
        and action.bank_payment_building_id is None
        for action in actions_full
    )


def test_apply_own_active_bank_partial_substitution_deducts_silver_and_remaining_wheat() -> None:
    scenario, _actions, bank_actions = _bank_actions("scenarios/bank_active_ordination_substitution_001.json")
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 1
        ),
    )
    summary = action_summary(action, scenario.config)
    assert "use building: bank to replace 1 wheat with 1 silver for this transaction" in summary
    assert "hire building: bank" not in summary

    result = apply_action(scenario.state, action, scenario.config)
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "bank",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    sow_event = _events_of_type(result.events, EventType.SOWING)[0]
    bonus_details = dict(bonus_event.details)
    delta_details = dict(delta_event.details)

    assert bonus_details["replaced_resource"] == "wheat"
    assert bonus_details["silver_amount"] == 1
    assert delta_details == {"stone": 0, "silver": -1, "wheat": -1}
    assert result.events.index(bonus_event) < result.events.index(sow_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_apply_own_active_bank_full_substitution_can_resolve_without_wheat() -> None:
    scenario, _actions, bank_actions = _bank_actions(
        "scenarios/bank_active_ordination_full_substitution_001.json"
    )
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 2
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert delta_details["silver"] == -2
    assert delta_details["wheat"] == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_bank_construct_substitution_spends_silver_and_not_stone() -> None:
    scenario, actions, bank_actions = _bank_actions(
        "scenarios/bank_active_construct_minority_substitution_001.json"
    )
    construct_bank_actions = [
        action
        for action in bank_actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_building_id == "well"
    ]
    assert construct_bank_actions
    assert {action.bank_payment_replaced_resource for action in construct_bank_actions} == {"stone"}
    assert {action.bank_payment_silver_amount for action in construct_bank_actions} == {1}
    assert not any(
        action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_building_id == "well"
        and action.bank_payment_building_id is None
        for action in actions
    )

    action = construct_bank_actions[0]
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)
    assert delta_details == {"stone": 0, "silver": -2, "wheat": 0}
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert "well" in result.state.player_state(PlayerId.PLAYER_ONE).player_board_slots.active_buildings


def test_bank_helper_supports_one_resource_type_substitution_including_piety() -> None:
    wheat_sub = _costs_with_bank_substitution(
        required_stone=1,
        required_wheat=2,
        replaced_resource="wheat",
        silver_amount=2,
    )
    stone_sub = _costs_with_bank_substitution(
        required_stone=1,
        required_wheat=2,
        replaced_resource="stone",
        silver_amount=1,
    )
    piety_sub = _costs_with_bank_substitution(
        required_piety=2,
        replaced_resource="piety",
        silver_amount=1,
    )
    assert wheat_sub == (1, 2, 0, 0)
    assert stone_sub == (0, 1, 2, 0)
    assert piety_sub == (0, 1, 0, 1)
    with pytest.raises(ValueError, match="exceeds required stone"):
        _costs_with_bank_substitution(
            required_stone=1,
            replaced_resource="stone",
            silver_amount=2,
        )


def test_bank_variants_only_exist_for_supported_payment_resolutions() -> None:
    scenario, actions, _bank_actions_all = _bank_actions(
        "scenarios/bank_active_construct_minority_substitution_001.json"
    )
    legal_bank_resolutions = {
        TurnResolutionType.ORDINATION,
        TurnResolutionType.CONSTRUCT_BUILDING,
        TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
    }
    for action in actions:
        if action.bank_payment_building_id is None:
            continue
        assert action.resolution in legal_bank_resolutions
        assert action.bank_payment_replaced_resource in {"wheat", "stone", "piety"}
        assert action.bank_payment_replaced_resource != "silver"
        assert (action.bank_payment_silver_amount or 0) >= 1
    assert scenario is not None


def test_hired_market_bank_pays_hire_before_substitution_and_cannot_use_merchant_none() -> None:
    scenario, _actions, bank_actions = _bank_actions("scenarios/bank_hire_market_ordination_001.json")
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_building_source == "market"
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 1
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "bank",
    )
    sow_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)
    assert hired_details["building_id"] == "bank"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sow_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0

    merchant_none_state = scenario.state.with_merchant_position(0)
    actions_when_none = [
        action
        for action in legal_actions(merchant_none_state, scenario.config)
        if isinstance(action, FullTurnAction)
    ]
    assert not any(
        action.bank_payment_building_id == "bank"
        and action.bank_payment_building_source == "market"
        for action in actions_when_none
    )


def test_hired_opponent_bank_pays_owner_before_substitution() -> None:
    scenario, _actions, bank_actions = _bank_actions("scenarios/bank_hire_opponent_ordination_001.json")
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_building_source == "player_two"
            and candidate.bank_payment_replaced_resource == "wheat"
            and candidate.bank_payment_silver_amount == 1
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)
    assert hired_details["building_id"] == "bank"
    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_wagon_yard_can_free_hire_bank_and_apply_substitution() -> None:
    scenario, _actions, bank_actions = _bank_actions(
        "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json"
    )
    action = _first_action(
        bank_actions,
        lambda candidate: (
            candidate.free_hire_enabler_building_id == "wagon_yard"
            and candidate.free_hire_target_building_id == "bank"
            and candidate.free_hire_target_building_source == "market"
            and candidate.bank_payment_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain", "ordain")
            and candidate.bank_payment_silver_amount == 2
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    hired_details = dict(hired_event.details)
    assert hired_details["building_id"] == "bank"
    assert hired_details["source"] == "market"
    assert hired_details["resource"] == "none"
    assert hired_details["amount"] == 0
    assert hired_details["payee"] == "none"
    assert hired_details["free_with_wagon_yard"] is True
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_apply_rejects_bank_fields_on_unsupported_resolution() -> None:
    scenario = load_scenario("scenarios/bank_active_ordination_substitution_001.json")
    base_action = _first_action(
        [
            action
            for action in legal_actions(scenario.state, scenario.config)
            if isinstance(action, FullTurnAction)
        ],
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    invalid_action = replace(
        base_action,
        bank_payment_building_id="bank",
        bank_payment_building_source="own_active",
        bank_payment_replaced_resource="wheat",
        bank_payment_silver_amount=1,
    )
    with pytest.raises(
        TransitionValidationError,
        match="Bank payment substitution is only supported for Ordination and Construct building actions",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)
