from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _brewery_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    conversions = [
        action
        for action in actions
        if action.building_conversion_id == "brewery"
    ]
    return scenario, actions, conversions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_brewery_generates_sell_variants_when_wheat_available() -> None:
    _scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_active_sell_wheat_001.json"
    )

    assert conversions
    assert all(action.building_conversion_source == "own_active" for action in conversions)
    assert all(action.building_conversion_direction == "sell_wheat_for_silver" for action in conversions)
    assert {action.building_conversion_amount for action in conversions} == {1}


def test_own_active_brewery_generates_exactly_one_conversion_amount_even_with_many_wheat() -> None:
    _scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_exactly_one_wheat_only_001.json"
    )

    assert conversions
    assert {action.building_conversion_amount for action in conversions} == {1}
    assert not any(
        action.building_conversion_amount in (0, 2)
        for action in conversions
    )
    assert not any(
        action.building_conversion_direction.startswith("buy_")
        for action in conversions
        if action.building_conversion_direction is not None
    )


def test_own_active_brewery_generates_no_variants_when_wheat_zero() -> None:
    scenario = load_scenario("scenarios/brewery_active_sell_wheat_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_without_wheat = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=player_one.resources.add(wheat=-player_one.resources.wheat),
        ),
    )

    actions = legal_actions(state_without_wheat, scenario.config)
    conversions = [action for action in actions if action.building_conversion_id == "brewery"]
    assert conversions == []


def test_hired_market_brewery_generates_variants_when_payable_and_wheat_remains() -> None:
    _scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_hire_market_sell_wheat_001.json"
    )

    assert conversions
    assert all(action.building_conversion_source == "market" for action in conversions)
    assert all(action.building_conversion_direction == "sell_wheat_for_silver" for action in conversions)
    assert {action.building_conversion_amount for action in conversions} == {1}


def test_hired_opponent_brewery_generates_variants_when_payable_and_wheat_remains() -> None:
    _scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_hire_opponent_sell_wheat_001.json"
    )

    assert conversions
    assert all(action.building_conversion_source == "player_two" for action in conversions)
    assert all(action.building_conversion_direction == "sell_wheat_for_silver" for action in conversions)
    assert {action.building_conversion_amount for action in conversions} == {1}


def test_own_active_brewery_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/brewery_hire_market_sell_wheat_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_brewery = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("brewery",),
            ),
        ),
    )
    actions = legal_actions(state_with_own_brewery, scenario.config)
    conversions = [
        action
        for action in actions
        if action.building_conversion_id == "brewery"
    ]

    assert conversions
    assert all(action.building_conversion_source == "own_active" for action in conversions)


def test_merchant_none_insufficient_donated_and_not_live_block_hired_brewery() -> None:
    blocked_paths = (
        "scenarios/brewery_merchant_none_no_hire_001.json",
        "scenarios/brewery_insufficient_after_hire_001.json",
        "scenarios/brewery_hire_with_wheat_requires_two_wheat_001.json",
        "scenarios/brewery_donated_no_conversion_001.json",
        "scenarios/brewery_not_live_no_conversion_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, conversions = _brewery_actions(path)
        assert conversions == []
        assert any(action.building_conversion_id is None for action in actions)


def test_apply_own_active_brewery_sell_one_emits_bonus_then_delta_before_sowing() -> None:
    scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_active_sell_wheat_001.json"
    )
    north_east = scenario.config.board.index_for_name("north_east")
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.selected_duty == north_east
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "brewery",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    delta_details = dict(delta_event.details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert delta_details["stone"] == 0
    assert delta_details["silver"] == 2
    assert delta_details["wheat"] == -1
    assert result.events.index(bonus_event) < result.events.index(delta_event)
    assert result.events.index(delta_event) < result.events.index(sowing_event)
    # Two silver from the conversion and a third from the tithe this conversion rides on. Tithe was
    # the inert resolution to hang a building test off until it started paying its counter out.
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 3
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 2
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_hired_market_brewery_pays_bank_before_conversion() -> None:
    scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_hire_market_sell_wheat_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_source == "market"
            and candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "brewery",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "brewery"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(delta_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 3


def test_hired_opponent_brewery_pays_owner_before_conversion() -> None:
    scenario, _actions, conversions = _brewery_actions(
        "scenarios/brewery_hire_opponent_sell_wheat_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_source == "player_two"
            and candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 3
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_conversion_that_cannot_keep_wheat_after_hire() -> None:
    scenario = load_scenario("scenarios/brewery_insufficient_after_hire_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="brewery",
        building_conversion_source="market",
        building_conversion_direction="sell_wheat_for_silver",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Brewery conversion requires at least 1 wheat after hire payment",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_invalid_brewery_amount_two() -> None:
    scenario = load_scenario("scenarios/brewery_active_sell_wheat_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="brewery",
        building_conversion_source="own_active",
        building_conversion_direction="sell_wheat_for_silver",
        building_conversion_amount=2,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Brewery conversion amount must be exactly 1",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_invalid_brewery_buy_direction() -> None:
    scenario = load_scenario("scenarios/brewery_active_sell_wheat_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="brewery",
        building_conversion_source="own_active",
        building_conversion_direction="buy_wheat",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Brewery conversion direction must be sell_wheat_for_silver",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_converted_silver_can_enable_later_give_alms_paid_costs() -> None:
    scenario, actions, conversions = _brewery_actions(
        "scenarios/brewery_sell_then_give_alms_paid_001.json"
    )
    paid_alms_with_conversion = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.GIVE_ALMS_PAID
        ),
    )

    assert not any(
        action.resolution is TurnResolutionType.GIVE_ALMS_PAID
        and action.building_conversion_id is None
        for action in actions
    )

    result = apply_action(scenario.state, paid_alms_with_conversion, scenario.config)
    resource_delta_events = _events_of_type(result.events, EventType.RESOURCE_DELTA)
    assert len(resource_delta_events) == 2
    conversion_delta = dict(resource_delta_events[0].details)
    alms_delta = dict(resource_delta_events[1].details)
    assert conversion_delta == {"stone": 0, "silver": 2, "wheat": -1}
    assert int(alms_delta["silver"]) < 0 or int(alms_delta["wheat"]) < 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).alms_position == 2


def test_action_summary_includes_brewery_conversion_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_conversions = _brewery_actions(
        "scenarios/brewery_active_sell_wheat_001.json"
    )
    own_action = _first_action(
        own_conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert "use building: brewery to sell 1 wheat for 2 silver" in own_summary
    assert "hire building: brewery" not in own_summary

    hired_scenario, _hired_actions, hired_conversions = _brewery_actions(
        "scenarios/brewery_hire_market_sell_wheat_001.json"
    )
    hired_action = _first_action(
        hired_conversions,
        lambda candidate: (
            candidate.building_conversion_source == "market"
            and candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert "use building: brewery to sell 1 wheat for 2 silver" in hired_summary
    assert "hire building: brewery from market" in hired_summary


def test_brewery_can_compose_with_kogge_route_modifier_when_both_are_active() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    composed_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=player_one.resources.add(wheat=1),
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=(
                    *player_one.player_board_slots.active_buildings,
                    "brewery",
                ),
            ),
        ),
    )
    actions = legal_actions(composed_state, scenario.config)
    combined_action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_building_id == "kogge"
            and candidate.building_conversion_id == "brewery"
            and candidate.building_conversion_direction == "sell_wheat_for_silver"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    summary = action_summary(combined_action, scenario.config)

    assert "use building: kogge" in summary
    assert "use building: brewery to sell 1 wheat for 2 silver" in summary
