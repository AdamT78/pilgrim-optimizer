from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingConversionStep, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _scenario_steps(path: str):
    scenario = load_scenario(path)
    return scenario, tuple(turn_steps(scenario.state, scenario.config))


def _step(steps, **values):
    return next(step for step in steps if all(getattr(step, key) == value for key, value in values.items()))


def _events(events, event_type):
    return [event for event in events if event.event_type is event_type]


def test_brewery_offers_exactly_one_wheat_for_silver_step() -> None:
    _scenario, steps = _scenario_steps("scenarios/brewery_active_sell_wheat_001.json")
    assert steps
    assert all((step.source, step.direction, step.amount) ==
               ("own_active", "sell_wheat_for_silver", 1) for step in steps)
    _scenario, many_wheat = _scenario_steps("scenarios/brewery_exactly_one_wheat_only_001.json")
    assert {step.amount for step in many_wheat} == {1}


def test_own_active_brewery_generates_no_variants_when_wheat_zero() -> None:
    scenario = load_scenario("scenarios/brewery_active_sell_wheat_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=replace(player.resources, wheat=0)),
    )
    assert turn_steps(state, scenario.config) == ()


def test_brewery_hired_sources_are_offered_and_unavailable_states_are_empty() -> None:
    _scenario, market_steps = _scenario_steps("scenarios/brewery_hire_market_sell_wheat_001.json")
    assert any(step.source == "market" for step in market_steps)
    _scenario, opponent_steps = _scenario_steps("scenarios/brewery_hire_opponent_sell_wheat_001.json")
    assert any(step.source == "player_two" for step in opponent_steps)
    for path in (
        "scenarios/brewery_merchant_none_no_hire_001.json",
        "scenarios/brewery_insufficient_after_hire_001.json",
        "scenarios/brewery_hire_with_wheat_requires_two_wheat_001.json",
        "scenarios/brewery_donated_no_conversion_001.json",
        "scenarios/brewery_not_live_no_conversion_001.json",
    ):
        scenario = load_scenario(path)
        assert turn_steps(scenario.state, scenario.config) == ()


def test_hired_market_brewery_generates_variants_when_payable_and_wheat_remains() -> None:
    _scenario, steps = _scenario_steps("scenarios/brewery_hire_market_sell_wheat_001.json")
    assert {step.amount for step in steps} == {1}
    assert all(step.source == "market" and step.direction == "sell_wheat_for_silver" for step in steps)


def test_hired_opponent_brewery_generates_variants_when_payable_and_wheat_remains() -> None:
    _scenario, steps = _scenario_steps("scenarios/brewery_hire_opponent_sell_wheat_001.json")
    assert {step.amount for step in steps} == {1}
    assert all(step.source == "player_two" and step.direction == "sell_wheat_for_silver" for step in steps)


def test_own_active_brewery_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/brewery_hire_market_sell_wheat_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player,
            player_board_slots=replace(
                player.player_board_slots,
                active_buildings=("brewery",),
            ),
        ),
    )
    steps = turn_steps(state, scenario.config)
    assert steps
    assert all(step.source == "own_active" for step in steps)


def test_brewery_step_events_precede_sowing() -> None:
    scenario, steps = _scenario_steps("scenarios/brewery_active_sell_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, amount=1))
    north_east = scenario.config.board.index_for_name("north_east")
    action = next(action for action in legal_actions(state, scenario.config)
                  if action.selected_duty == north_east and action.resolution is TurnResolutionType.TITHE)
    result = apply_action(state, action, scenario.config)
    bonus = _events(result.events, EventType.BUILDING_BONUS)[0]
    delta = _events(result.events, EventType.RESOURCE_DELTA)[0]
    sowing = _events(result.events, EventType.SOWING)[0]
    assert dict(delta.details) == {"stone": 0, "silver": 2, "wheat": -1}
    assert result.events.index(bonus) < result.events.index(delta) < result.events.index(sowing)


def test_hired_market_brewery_pays_bank_before_conversion() -> None:
    scenario, steps = _scenario_steps("scenarios/brewery_hire_market_sell_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, steps[0])
    hired = _events(state.events, EventType.BUILDING_HIRED)[0]
    bonus = _events(state.events, EventType.BUILDING_BONUS)[0]
    delta = _events(state.events, EventType.RESOURCE_DELTA)[0]
    assert dict(hired.details)["payee"] == "bank"
    assert state.events.index(hired) < state.events.index(bonus) < state.events.index(delta)
    assert state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_hired_opponent_brewery_pays_owner_before_conversion() -> None:
    scenario, steps = _scenario_steps("scenarios/brewery_hire_opponent_sell_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, steps[0])
    hired = _events(state.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["payee"] == "player_two"
    assert state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_brewery_step_rejects_invalid_amount_and_direction() -> None:
    scenario = load_scenario("scenarios/brewery_active_sell_wheat_001.json")
    for step, message in (
        (BuildingConversionStep("brewery", "own_active", "sell_wheat_for_silver", 2), "amount"),
        (BuildingConversionStep("brewery", "own_active", "buy_wheat", 1), "direction"),
    ):
        with pytest.raises(TransitionValidationError, match=message):
            apply_turn_step(scenario.state, scenario.config, step)


def test_apply_rejects_conversion_that_cannot_keep_wheat_after_hire() -> None:
    scenario = load_scenario("scenarios/brewery_insufficient_after_hire_001.json")
    with pytest.raises(
        TransitionValidationError,
        match="Brewery conversion requires at least 1 wheat after hire payment",
    ):
        apply_turn_step(
            scenario.state,
            scenario.config,
            BuildingConversionStep("brewery", "market", "sell_wheat_for_silver", 1, "wheat"),
        )


def test_brewery_step_can_enable_later_paid_alms() -> None:
    scenario, steps = _scenario_steps("scenarios/brewery_sell_then_give_alms_paid_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, amount=1))
    action = next(action for action in legal_actions(state, scenario.config)
                  if action.resolution is TurnResolutionType.GIVE_ALMS_PAID
                  and action.alms_payment_silver + action.alms_payment_wheat == 2)
    result = apply_action(state, action, scenario.config)
    assert len(_events(result.events, EventType.RESOURCE_DELTA)) >= 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).alms_position == 2


def test_action_summary_includes_brewery_conversion_and_hire_suffix() -> None:
    own_scenario, own_steps = _scenario_steps("scenarios/brewery_active_sell_wheat_001.json")
    own = own_steps[0]
    assert "use building: brewery to sell 1 wheat for 2 silver" in action_summary(
        own, own_scenario.config
    )
    hired_scenario, hired_steps = _scenario_steps("scenarios/brewery_hire_market_sell_wheat_001.json")
    summary = action_summary(hired_steps[0], hired_scenario.config)
    assert "hire building: brewery from market" in summary


def test_brewery_can_follow_a_kogge_route() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=player.resources.add(wheat=1), player_board_slots=replace(
            player.player_board_slots, active_buildings=(*player.player_board_slots.active_buildings, "brewery")
        )),
    )
    state = apply_turn_step(state, scenario.config, _step(turn_steps(state, scenario.config), amount=1))
    assert any(action.sow_route_building_id == "kogge" for action in legal_actions(state, scenario.config))
