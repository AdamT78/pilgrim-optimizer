from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.buildings import mill_actual_wheat_cost, mill_wheat_waiver
from pilgrim.rules.merchant import current_merchant_resource
from pilgrim.rules.transition import apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


@pytest.mark.parametrize(
    ("required_wheat", "waiver", "actual"),
    [
        (0, 0, 0),
        (1, 1, 0),
        (2, 2, 0),
        (3, 2, 1),
        (4, 2, 2),
        (5, 2, 3),
    ],
)
def test_mill_wheat_formula(required_wheat: int, waiver: int, actual: int) -> None:
    assert mill_wheat_waiver(required_wheat) == waiver
    assert mill_actual_wheat_cost(required_wheat) == actual


def test_mill_wheat_helpers_reject_negative_input() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        mill_wheat_waiver(-1)
    with pytest.raises(ValueError, match="cannot be negative"):
        mill_actual_wheat_cost(-1)


def test_ordination_active_mill_two_steps_costs_zero_wheat() -> None:
    scenario = load_scenario("scenarios/ordination_mill_active_two_steps_free_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    action = next(action for action in actions if action.ordination_steps == ("ordain", "mission"))
    result = apply_action(scenario.state, action, scenario.config)

    duty_details = dict(_events_of_type(result.events, EventType.DUTY_RESOLUTION)[0].details)
    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "mill"
    )
    bonus_details = dict(bonus_event.details)
    ordination_events = _events_of_type(result.events, EventType.ORDINATION)

    assert duty_details["duty_value"] == 2
    assert duty_details["effective_duty_value"] == 2
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert bonus_details["wheat_waived"] == 2
    assert bonus_details["actual_wheat_spent"] == 0
    assert "duty_value_bonus" not in bonus_details
    assert [dict(event.details)["wheat_paid"] for event in ordination_events] == [0, 0]
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_ordination_active_mill_three_steps_spends_one_wheat() -> None:
    scenario = load_scenario("scenarios/ordination_mill_active_three_steps_one_wheat_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    action = next(action for action in actions if len(action.ordination_steps) == 3)
    result = apply_action(scenario.state, action, scenario.config)
    bonus_details = dict(
        next(
            event
            for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
            if dict(event.details).get("building") == "mill"
        ).details
    )
    ordination_events = _events_of_type(result.events, EventType.ORDINATION)

    assert bonus_details["wheat_waived"] == 2
    assert bonus_details["actual_wheat_spent"] == 1
    assert sum(int(dict(event.details)["wheat_paid"]) for event in ordination_events) == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_ordination_hired_mill_market_pays_hire_and_waives_two() -> None:
    scenario = load_scenario("scenarios/ordination_hire_mill_market_three_steps_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    action = next(
        action for action in actions if action.hired_building_id == "mill" and len(action.ordination_steps) == 3
    )
    assert "mill wheat spent=1" in action_summary(action, scenario.config)

    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "mill"
    )
    hired_details = dict(hired_event.details)
    bonus_details = dict(bonus_event.details)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)
    first_ordination_event = _events_of_type(result.events, EventType.ORDINATION)[0]

    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert bonus_details["wheat_waived"] == 2
    assert bonus_details["actual_wheat_spent"] == 1
    assert delta_details["wheat"] == -2
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(first_ordination_event)


def test_ordination_hired_mill_opponent_pays_owner() -> None:
    scenario = load_scenario("scenarios/ordination_hire_mill_opponent_three_steps_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
        and action.hired_building_id == "mill"
        and len(action.ordination_steps) == 3
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_ordination_hired_mill_blocked_by_merchant_none_or_insufficient_hire_resource() -> None:
    merchant_none_scenario = load_scenario("scenarios/ordination_hire_mill_merchant_none_001.json")
    merchant_none_actions = [
        action
        for action in legal_actions(merchant_none_scenario.state, merchant_none_scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    assert all(action.hired_building_id is None for action in merchant_none_actions)

    insufficient_scenario = load_scenario("scenarios/ordination_hire_mill_insufficient_resource_001.json")
    insufficient_actions = [
        action
        for action in legal_actions(insufficient_scenario.state, insufficient_scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    assert all(action.hired_building_id is None for action in insufficient_actions)


def test_ordination_own_active_mill_works_when_merchant_resource_none() -> None:
    scenario = load_scenario("scenarios/ordination_mill_active_two_steps_free_001.json")
    assert current_merchant_resource(scenario.state, scenario.config.merchant) is None
    ordination_actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    assert any(action.ordination_steps == ("ordain", "mission") for action in ordination_actions)


def test_give_alms_active_mill_wheat3_spends_one_and_advances_three_rows() -> None:
    scenario = load_scenario("scenarios/give_alms_mill_active_wheat3_spend1_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
        and action.alms_payment_silver == 0
        and action.alms_payment_wheat == 3
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "mill"
    )
    bonus_details = dict(bonus_event.details)
    alms_payment_details = dict(_events_of_type(result.events, EventType.ALMS_PAYMENT)[0].details)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)
    alms_progress = dict(_events_of_type(result.events, EventType.ALMS_PROGRESS)[0].details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert bonus_details["wheat_waived"] == 2
    assert bonus_details["actual_wheat_spent"] == 1
    assert alms_payment_details["credited_silver"] == 0
    assert alms_payment_details["credited_wheat"] == 3
    assert alms_payment_details["actual_paid_silver"] == 0
    assert alms_payment_details["actual_paid_wheat"] == 1
    assert alms_progress["old_row"] == 0
    assert alms_progress["new_row"] == 3
    assert delta_details["wheat"] == -1


def test_give_alms_hired_mill_market_pays_hire_separately() -> None:
    scenario = load_scenario("scenarios/give_alms_hire_mill_market_wheat3_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
        and action.hired_building_id == "mill"
        and action.alms_payment_wheat == 3
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "mill"
    )
    hired_details = dict(hired_event.details)
    alms_payment_details = dict(_events_of_type(result.events, EventType.ALMS_PAYMENT)[0].details)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert alms_payment_details["credited_silver"] == 0
    assert alms_payment_details["credited_wheat"] == 3
    assert alms_payment_details["actual_paid_silver"] == 0
    assert alms_payment_details["actual_paid_wheat"] == 1
    assert delta_details["wheat"] == -2
    assert result.events.index(hired_event) < result.events.index(bonus_event)


def test_give_alms_hired_mill_opponent_transfers_hire_resource_to_owner() -> None:
    scenario = load_scenario("scenarios/give_alms_hire_mill_opponent_wheat3_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
        and action.hired_building_id == "mill"
        and action.alms_payment_wheat == 3
    )
    assert "mill wheat spent=1" in action_summary(action, scenario.config)

    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "silver"
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_give_alms_hired_mill_blocked_when_merchant_resource_is_none() -> None:
    scenario = load_scenario("scenarios/give_alms_hire_mill_merchant_none_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
    ]
    assert actions
    assert all(action.hired_building_id is None for action in actions)


def test_give_alms_all_silver_payment_does_not_emit_mill_bonus() -> None:
    scenario = load_scenario("scenarios/give_alms_paid_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_mill = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("mill",),
                donated_buildings=(),
            ),
        ),
    )
    action = next(
        action
        for action in legal_actions(state_with_mill, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID and action.alms_payment_wheat == 0
    )
    result = apply_action(state_with_mill, action, scenario.config)
    alms_payment_details = dict(_events_of_type(result.events, EventType.ALMS_PAYMENT)[0].details)

    assert not any(
        dict(event.details).get("building") == "mill"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )
    assert "credited_wheat" not in alms_payment_details
    assert "actual_paid_wheat" not in alms_payment_details


def test_give_alms_donate_building_is_not_modified_by_mill() -> None:
    scenario = load_scenario("scenarios/give_alms_mill_donate_building_no_effect_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
    )
    result = apply_action(scenario.state, action, scenario.config)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert not any(
        dict(event.details).get("building") == "mill"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )
    progress_details = dict(_events_of_type(result.events, EventType.ALMS_PROGRESS)[0].details)
    assert progress_details["old_row"] == 0
    assert progress_details["new_row"] == 1


def test_give_alms_alms_house_extra_wheat_counts_toward_mill_waiver() -> None:
    scenario = load_scenario("scenarios/give_alms_mill_active_wheat3_spend1_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
        and action.alms_house_extra_wheat == 1
        and action.alms_payment_wheat == 2
    )
    result = apply_action(scenario.state, action, scenario.config)
    bonus_details = dict(
        next(
            event
            for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
            if dict(event.details).get("building") == "mill"
        ).details
    )

    assert bonus_details["required_wheat"] == 3
    assert bonus_details["wheat_waived"] == 2
    assert bonus_details["actual_wheat_spent"] == 1
