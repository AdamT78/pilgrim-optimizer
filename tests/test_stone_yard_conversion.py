from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _stone_yard_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    conversions = [
        action
        for action in actions
        if action.building_conversion_id == "stone_yard"
    ]
    return scenario, actions, conversions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_stone_yard_generates_sell_variants_for_each_stone_amount() -> None:
    _scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_sell_stone_001.json"
    )

    sell_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "sell_stone"
    }
    assert sell_amounts == {1, 2, 3}
    assert all(action.building_conversion_source == "own_active" for action in conversions)
    assert all((action.building_conversion_amount or 0) >= 1 for action in conversions)


def test_own_active_stone_yard_generates_buy_variants_for_each_silver_amount() -> None:
    _scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_buy_stone_001.json"
    )

    buy_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "buy_stone"
    }
    assert buy_amounts == {1, 2}
    assert all(action.building_conversion_source == "own_active" for action in conversions)
    assert all((action.building_conversion_amount or 0) >= 1 for action in conversions)


def test_hired_market_stone_yard_generates_sell_variants_when_payable() -> None:
    _scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_hire_market_sell_stone_001.json"
    )

    sell_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "sell_stone"
    }
    assert sell_amounts == {1, 2, 3}
    assert all(action.building_conversion_source == "market" for action in conversions)


def test_hired_opponent_stone_yard_generates_buy_variants_when_payable() -> None:
    _scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_hire_opponent_buy_stone_001.json"
    )

    buy_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "buy_stone"
    }
    assert buy_amounts == {1, 2}
    assert all(action.building_conversion_source == "player_two" for action in conversions)


def test_own_active_stone_yard_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/stone_yard_hire_market_sell_stone_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_stone_yard = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("stone_yard",),
            ),
        ),
    )
    actions = legal_actions(state_with_own_stone_yard, scenario.config)
    conversions = [
        action
        for action in actions
        if action.building_conversion_id == "stone_yard"
    ]

    assert conversions
    assert all(action.building_conversion_source == "own_active" for action in conversions)


def test_merchant_none_insufficient_donated_and_not_live_block_hired_stone_yard() -> None:
    blocked_paths = (
        "scenarios/stone_yard_merchant_none_no_hire_001.json",
        "scenarios/stone_yard_insufficient_after_hire_001.json",
        "scenarios/stone_yard_donated_no_conversion_001.json",
        "scenarios/stone_yard_not_live_no_conversion_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, conversions = _stone_yard_actions(path)
        assert conversions == []
        assert any(action.building_conversion_id is None for action in actions)


def test_sell_variants_not_generated_at_stone_zero() -> None:
    _scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_buy_stone_001.json"
    )
    sell_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "sell_stone"
    }
    assert sell_amounts == set()


def test_buy_variants_not_generated_at_silver_zero() -> None:
    _scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_sell_stone_001.json"
    )
    buy_amounts = {
        action.building_conversion_amount
        for action in conversions
        if action.building_conversion_direction == "buy_stone"
    }
    assert buy_amounts == set()


def test_apply_own_active_sell_two_stone_emits_bonus_then_delta_before_sowing() -> None:
    scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_sell_stone_001.json"
    )
    north_east = scenario.config.board.index_for_name("north_east")
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_stone"
            and candidate.building_conversion_amount == 2
            and candidate.selected_duty == north_east
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "stone_yard",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    delta_details = dict(delta_event.details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert delta_details["stone"] == -2
    assert delta_details["silver"] == 2
    assert delta_details["wheat"] == 0
    assert result.events.index(bonus_event) < result.events.index(delta_event)
    assert result.events.index(delta_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_apply_own_active_buy_one_stone_converts_resources() -> None:
    scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_buy_stone_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_stone"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert delta_details["stone"] == 1
    assert delta_details["silver"] == -1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1


def test_hired_market_stone_yard_pays_bank_before_conversion() -> None:
    scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_hire_market_sell_stone_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_source == "market"
            and candidate.building_conversion_direction == "sell_stone"
            and candidate.building_conversion_amount == 2
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "stone_yard",
    )
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "stone_yard"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(delta_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2


def test_hired_opponent_stone_yard_pays_owner_before_conversion() -> None:
    scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_hire_opponent_buy_stone_001.json"
    )
    action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_source == "player_two"
            and candidate.building_conversion_direction == "buy_stone"
            and candidate.building_conversion_amount == 2
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 2
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_buy_conversion_that_cannot_pay_after_hire() -> None:
    scenario = load_scenario("scenarios/stone_yard_insufficient_after_hire_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="stone_yard",
        building_conversion_source="market",
        building_conversion_direction="buy_stone",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Stone Yard buy conversion requires enough silver after hire payment",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_sell_conversion_below_zero_stone() -> None:
    scenario = load_scenario("scenarios/stone_yard_active_buy_stone_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        building_conversion_id="stone_yard",
        building_conversion_source="own_active",
        building_conversion_direction="sell_stone",
        building_conversion_amount=1,
    )

    with pytest.raises(
        TransitionValidationError,
        match="Stone Yard sell conversion requires enough stone after hire payment",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_converted_stone_can_enable_construct_building_acquisition() -> None:
    scenario, actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_buy_then_construct_001.json"
    )
    construct_with_conversion = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_stone"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.CONSTRUCT_BUILDING
            and candidate.construct_building_id == "brewery"
        ),
    )

    assert not any(
        action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_building_id == "brewery"
        and action.building_conversion_id is None
        for action in actions
    )

    result = apply_action(scenario.state, construct_with_conversion, scenario.config)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 0
    assert "brewery" in result.state.player_state(PlayerId.PLAYER_ONE).player_board_slots.active_buildings


def test_buying_stone_can_exceed_six_then_round_end_caps_back_to_six() -> None:
    scenario, _actions, conversions = _stone_yard_actions(
        "scenarios/stone_yard_buy_above_six_then_round_end_cap_001.json"
    )
    buy_action = _first_action(
        conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_stone"
            and candidate.building_conversion_amount == 1
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )

    result = apply_action(scenario.state, buy_action, scenario.config)
    conversion_delta = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)
    cap_event = _first_action(
        _events_of_type(result.events, EventType.EXCESS_RESOURCE_CAP),
        lambda event: dict(event.details).get("player") == "player_two",
    )
    cap_details = dict(cap_event.details)

    assert conversion_delta == {"stone": 1, "silver": -1, "wheat": 0}
    assert cap_details["stone_before"] == 7
    assert cap_details["stone_after"] == 6
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.stone == 6


def test_action_summary_includes_stone_yard_conversion_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_conversions = _stone_yard_actions(
        "scenarios/stone_yard_active_sell_stone_001.json"
    )
    own_action = _first_action(
        own_conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_stone"
            and candidate.building_conversion_amount == 2
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert "use building: stone_yard to sell 2 stone for 2 silver" in own_summary
    assert "hire building: stone_yard" not in own_summary

    hired_scenario, _hired_actions, hired_conversions = _stone_yard_actions(
        "scenarios/stone_yard_hire_market_buy_stone_001.json"
    )
    hired_action = _first_action(
        hired_conversions,
        lambda candidate: (
            candidate.building_conversion_direction == "buy_stone"
            and candidate.building_conversion_amount == 1
            and candidate.building_conversion_source == "market"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert "use building: stone_yard to buy 1 stone for 1 silver" in hired_summary
    assert "hire building: stone_yard from market" in hired_summary


def test_stone_yard_can_compose_with_kogge_route_modifier_when_both_are_active() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    composed_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=player_one.resources.add(silver=2),
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=(
                    *player_one.player_board_slots.active_buildings,
                    "stone_yard",
                ),
            ),
        ),
    )
    actions = legal_actions(composed_state, scenario.config)
    combined_action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_building_id == "kogge"
            and candidate.building_conversion_id == "stone_yard"
            and candidate.building_conversion_direction == "buy_stone"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    summary = action_summary(combined_action, scenario.config)

    assert "use building: kogge" in summary
    assert "use building: stone_yard to buy 1 stone for 1 silver" in summary
