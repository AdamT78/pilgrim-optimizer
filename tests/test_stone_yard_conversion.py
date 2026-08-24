from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingConversionStep, EndTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.buildings import building_ability_source
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


def test_stone_yard_steps_offer_each_amount_and_hired_source() -> None:
    _scenario, steps = _scenario_steps("scenarios/stone_yard_active_sell_stone_001.json")
    assert {step.amount for step in steps if step.direction == "sell_stone"} == {1, 2, 3}
    assert all(step.source == "own_active" for step in steps)

    _scenario, buy_steps = _scenario_steps("scenarios/stone_yard_hire_market_buy_stone_001.json")
    assert any(step.source == "market" and step.direction == "buy_stone" and step.amount == 1
               for step in buy_steps)
    _scenario, opponent_steps = _scenario_steps("scenarios/stone_yard_hire_opponent_buy_stone_001.json")
    assert any(step.source == "player_two" and step.direction == "buy_stone" and step.amount == 2
               for step in opponent_steps)


def test_own_active_stone_yard_generates_sell_variants_for_each_stone_amount() -> None:
    _scenario, steps = _scenario_steps("scenarios/stone_yard_active_sell_stone_001.json")
    assert {step.amount for step in steps if step.direction == "sell_stone"} == {1, 2, 3}
    assert all(step.source == "own_active" for step in steps)


def test_own_active_stone_yard_generates_buy_variants_for_each_silver_amount() -> None:
    _scenario, steps = _scenario_steps("scenarios/stone_yard_active_buy_stone_001.json")
    assert {step.amount for step in steps if step.direction == "buy_stone"} == {1, 2}
    assert all(step.source == "own_active" for step in steps)


def test_hired_market_stone_yard_generates_sell_variants_when_payable() -> None:
    _scenario, steps = _scenario_steps("scenarios/stone_yard_hire_market_sell_stone_001.json")
    assert {step.amount for step in steps if step.direction == "sell_stone"} == {1, 2, 3}
    assert all(step.source == "market" for step in steps)


def test_hired_opponent_stone_yard_generates_buy_variants_when_payable() -> None:
    _scenario, steps = _scenario_steps("scenarios/stone_yard_hire_opponent_buy_stone_001.json")
    assert {step.amount for step in steps if step.direction == "buy_stone"} == {1, 2}
    assert all(step.source == "player_two" for step in steps)


def test_stone_yard_step_is_blocked_when_unavailable_and_used_once() -> None:
    scenario, steps = _scenario_steps("scenarios/stone_yard_active_sell_stone_001.json")
    state = apply_turn_step(scenario.state, scenario.config, steps[0])
    assert all(step.building_id != "stone_yard" for step in turn_steps(state, scenario.config))
    for path in (
        "scenarios/stone_yard_merchant_none_no_hire_001.json",
        "scenarios/stone_yard_insufficient_after_hire_001.json",
        "scenarios/stone_yard_donated_no_conversion_001.json",
        "scenarios/stone_yard_not_live_no_conversion_001.json",
    ):
        blocked = load_scenario(path)
        assert turn_steps(blocked.state, blocked.config) == ()


def test_stone_yard_step_applies_before_sowing_and_round_end_caps_afterwards() -> None:
    scenario, steps = _scenario_steps("scenarios/stone_yard_active_sell_stone_001.json")
    step = _step(steps, direction="sell_stone", amount=2)
    state = apply_turn_step(scenario.state, scenario.config, step)
    north_east = scenario.config.board.index_for_name("north_east")
    action = next(action for action in legal_actions(state, scenario.config)
                  if action.selected_duty == north_east and action.resolution is TurnResolutionType.TITHE)
    result = apply_action(state, action, scenario.config)
    assert dict(_events(result.events, EventType.RESOURCE_DELTA)[0].details) == {
        "stone": -2, "silver": 2, "wheat": 0
    }

    cap_scenario, cap_steps = _scenario_steps("scenarios/stone_yard_buy_above_six_then_round_end_cap_001.json")
    cap_step = _step(cap_steps, direction="buy_stone", amount=1)
    cap_state = apply_turn_step(cap_scenario.state, cap_scenario.config, cap_step)
    assert cap_state.player_state(PlayerId.PLAYER_TWO).resources.stone == 7


def test_apply_own_active_sell_two_stone_emits_bonus_then_delta_before_sowing() -> None:
    scenario, steps = _scenario_steps("scenarios/stone_yard_active_sell_stone_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, direction="sell_stone", amount=2))
    north_east = scenario.config.board.index_for_name("north_east")
    action = next(
        action for action in legal_actions(state, scenario.config)
        if action.selected_duty == north_east and action.resolution is TurnResolutionType.TITHE
    )
    result = apply_action(state, action, scenario.config)
    bonus = next(event for event in _events(result.events, EventType.BUILDING_BONUS)
                 if dict(event.details).get("building") == "stone_yard")
    delta = _events(result.events, EventType.RESOURCE_DELTA)[0]
    sowing = _events(result.events, EventType.SOWING)[0]
    assert dict(delta.details) == {"stone": -2, "silver": 2, "wheat": 0}
    assert result.events.index(bonus) < result.events.index(delta) < result.events.index(sowing)


def test_apply_own_active_buy_one_stone_converts_resources() -> None:
    scenario, steps = _scenario_steps("scenarios/stone_yard_active_buy_stone_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, direction="buy_stone", amount=1))
    delta = _events(state.events, EventType.RESOURCE_DELTA)[0]
    assert dict(delta.details) == {"stone": 1, "silver": -1, "wheat": 0}
    assert state.player_state(PlayerId.PLAYER_ONE).resources.stone == 1


def test_buying_stone_can_exceed_six_then_round_end_caps_back_to_six() -> None:
    scenario, steps = _scenario_steps("scenarios/stone_yard_buy_above_six_then_round_end_cap_001.json")
    state = apply_turn_step(
        scenario.state,
        scenario.config,
        _step(steps, direction="buy_stone", amount=1),
    )
    action = next(
        action for action in legal_actions(state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    )
    resolution = apply_action(state, action, scenario.config)
    assert resolution.state.turn_progress.resolution_committed
    result = apply_action(resolution.state, EndTurnAction(), scenario.config)
    cap = next(event for event in _events(result.events, EventType.EXCESS_RESOURCE_CAP)
               if dict(event.details).get("player") == "player_two")
    assert dict(cap.details)["stone_before"] == 7
    assert dict(cap.details)["stone_after"] == 6


def test_stone_yard_can_follow_a_kogge_route() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=player.resources.add(silver=2), player_board_slots=replace(
            player.player_board_slots, active_buildings=(*player.player_board_slots.active_buildings, "stone_yard")
        )),
    )
    step = _step(turn_steps(state, scenario.config), direction="buy_stone", amount=1)
    state = apply_turn_step(state, scenario.config, step)
    assert any(action.sow_route_building_id == "kogge" for action in legal_actions(state, scenario.config))


def test_own_active_stone_yard_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/stone_yard_hire_market_sell_stone_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player,
            player_board_slots=replace(
                player.player_board_slots,
                active_buildings=("stone_yard",),
            ),
        ),
    )
    steps = turn_steps(state, scenario.config)
    assert steps
    assert all(step.source == "own_active" for step in steps)


def test_merchant_none_insufficient_donated_and_not_live_block_hired_stone_yard() -> None:
    for path in (
        "scenarios/stone_yard_merchant_none_no_hire_001.json",
        "scenarios/stone_yard_insufficient_after_hire_001.json",
        "scenarios/stone_yard_donated_no_conversion_001.json",
        "scenarios/stone_yard_not_live_no_conversion_001.json",
    ):
        scenario = load_scenario(path)
        assert turn_steps(scenario.state, scenario.config) == ()


def test_sell_variants_not_generated_at_stone_zero() -> None:
    scenario = load_scenario("scenarios/stone_yard_active_buy_stone_001.json")
    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.direction == "sell_stone"]


def test_buy_variants_not_generated_at_silver_zero() -> None:
    scenario = load_scenario("scenarios/stone_yard_active_sell_stone_001.json")
    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.direction == "buy_stone"]


def test_hired_market_stone_yard_pays_bank_before_conversion() -> None:
    scenario = load_scenario("scenarios/stone_yard_hire_market_sell_stone_001.json")
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.direction == "sell_stone" and step.amount == 2
    )
    result = apply_turn_step(scenario.state, scenario.config, step)
    hired = next(event for event in result.events if event.event_type is EventType.BUILDING_HIRED)
    bonus = next(event for event in result.events if event.event_type is EventType.BUILDING_BONUS)
    delta = next(event for event in result.events if event.event_type is EventType.RESOURCE_DELTA)
    assert dict(hired.details)["payee"] == "bank"
    assert result.events.index(hired) < result.events.index(bonus) < result.events.index(delta)


def test_hired_opponent_stone_yard_pays_owner_before_conversion() -> None:
    scenario = load_scenario("scenarios/stone_yard_hire_opponent_buy_stone_001.json")
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.direction == "buy_stone" and step.amount == 2
    )
    result = apply_turn_step(scenario.state, scenario.config, step)
    hired = next(event for event in result.events if event.event_type is EventType.BUILDING_HIRED)
    assert dict(hired.details)["payee"] == "player_two"
    assert result.player_state(PlayerId.PLAYER_ONE).resources.stone == 2
    assert result.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_buy_conversion_that_cannot_pay_after_hire() -> None:
    scenario = load_scenario("scenarios/stone_yard_insufficient_after_hire_001.json")
    source = building_ability_source(
        scenario.state,
        scenario.config,
        acting_player=scenario.state.active_player,
        building_key="stone_yard",
    )
    assert source.hire_resource == "silver"
    with pytest.raises(
        TransitionValidationError,
        match="Stone Yard buy conversion requires enough silver after hire payment",
    ):
        apply_turn_step(
            scenario.state,
            scenario.config,
            BuildingConversionStep("stone_yard", "market", "buy_stone", 1, "silver"),
        )


def test_apply_rejects_sell_conversion_below_zero_stone() -> None:
    scenario = load_scenario("scenarios/stone_yard_active_buy_stone_001.json")
    with pytest.raises(
        TransitionValidationError,
        match="Stone Yard sell conversion requires enough stone after hire payment",
    ):
        apply_turn_step(
            scenario.state,
            scenario.config,
            BuildingConversionStep("stone_yard", "own_active", "sell_stone", 1),
        )


def test_converted_stone_can_enable_construct_building_acquisition() -> None:
    scenario = load_scenario("scenarios/stone_yard_buy_then_construct_001.json")
    step = next(
        step for step in turn_steps(scenario.state, scenario.config)
        if step.direction == "buy_stone" and step.amount == 1
    )
    state = apply_turn_step(scenario.state, scenario.config, step)
    action = next(
        action
        for action in legal_actions(state, scenario.config)
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_building_id == "brewery"
    )
    result = apply_action(state, action, scenario.config)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 0
    assert "brewery" in result.state.player_state(PlayerId.PLAYER_ONE).player_board_slots.active_buildings


def test_action_summary_includes_stone_yard_conversion_and_hire_suffix() -> None:
    own_scenario = load_scenario("scenarios/stone_yard_active_sell_stone_001.json")
    own = next(
        step
        for step in turn_steps(own_scenario.state, own_scenario.config)
        if step.direction == "sell_stone" and step.amount == 2
    )
    assert "use building: stone_yard to sell 2 stone for 2 silver" in action_summary(
        own, own_scenario.config
    )

    hired_scenario = load_scenario("scenarios/stone_yard_hire_market_buy_stone_001.json")
    hired = next(
        step
        for step in turn_steps(hired_scenario.state, hired_scenario.config)
        if step.direction == "buy_stone" and step.amount == 1
    )
    summary = action_summary(hired, hired_scenario.config)
    assert "use building: stone_yard to buy 1 stone for 1 silver" in summary
    assert "hire building: stone_yard from market" in summary
