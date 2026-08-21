from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingConversionStep, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.buildings import building_ability_source
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _steps(path: str):
    scenario = load_scenario(path)
    return scenario, tuple(turn_steps(scenario.state, scenario.config))


def _step(steps, **values):
    return next(step for step in steps if all(getattr(step, key) == value for key, value in values.items()))


def _events(events, event_type):
    return [event for event in events if event.event_type is event_type]


def _tithe_after_step(scenario, step):
    state = apply_turn_step(scenario.state, scenario.config, step)
    north_east = scenario.config.board.index_for_name("north_east")
    action = next(
        action
        for action in legal_actions(state, scenario.config)
        if action.selected_duty == north_east and action.resolution is TurnResolutionType.TITHE
    )
    return state, apply_action(state, action, scenario.config)


def test_grain_store_steps_offer_each_sell_and_buy_amount() -> None:
    scenario, steps = _steps("scenarios/grain_store_active_sell_wheat_001.json")
    assert {
        step.amount for step in steps if step.direction == "sell_wheat"
    } == {1, 2, 3}
    assert all(step.source == "own_active" for step in steps)

    buy_scenario, buy_steps = _steps("scenarios/grain_store_active_buy_wheat_001.json")
    assert {step.amount for step in buy_steps if step.direction == "buy_wheat"} == {1, 2}
    assert all(step.building_id == "grain_store" for step in buy_steps)
    assert scenario.state == scenario.state
    assert buy_scenario.state == buy_scenario.state


def test_own_active_grain_store_generates_buy_variants_for_each_silver_amount() -> None:
    _scenario, steps = _steps("scenarios/grain_store_active_buy_wheat_001.json")
    assert {step.amount for step in steps if step.direction == "buy_wheat"} == {1, 2}
    assert all(step.source == "own_active" for step in steps)


def test_hired_market_grain_store_generates_sell_variants_when_payable() -> None:
    _scenario, steps = _steps("scenarios/grain_store_hire_market_sell_wheat_001.json")
    assert {step.amount for step in steps if step.direction == "sell_wheat"} == {1, 2}
    assert all(step.source == "market" for step in steps)


def test_hired_opponent_grain_store_generates_buy_variants_when_payable() -> None:
    _scenario, steps = _steps("scenarios/grain_store_hire_opponent_buy_wheat_001.json")
    assert {step.amount for step in steps if step.direction == "buy_wheat"} == {1, 2}
    assert all(step.source == "player_two" for step in steps)


def test_own_active_grain_store_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/grain_store_hire_market_sell_wheat_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player,
            player_board_slots=replace(
                player.player_board_slots,
                active_buildings=("grain_store",),
            ),
        ),
    )
    steps = turn_steps(state, scenario.config)
    assert steps
    assert all(step.source == "own_active" for step in steps)


def test_grain_store_hired_sources_are_derived_and_paid() -> None:
    scenario, steps = _steps("scenarios/grain_store_hire_market_sell_wheat_001.json")
    market_step = _step(steps, source="market", direction="sell_wheat", amount=2)
    _state, result = _tithe_after_step(scenario, market_step)
    hired = _events(result.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["payee"] == "bank"
    assert dict(_events(result.events, EventType.RESOURCE_DELTA)[0].details) == {
        "stone": 0,
        "silver": 2,
        "wheat": -2,
    }

    opponent, opponent_steps = _steps("scenarios/grain_store_hire_opponent_buy_wheat_001.json")
    opponent_step = _step(opponent_steps, source="player_two", direction="buy_wheat", amount=2)
    _state, result = _tithe_after_step(opponent, opponent_step)
    assert dict(_events(result.events, EventType.BUILDING_HIRED)[0].details)["payee"] == "player_two"


def test_grain_store_is_used_once_and_blocked_when_unavailable() -> None:
    scenario, steps = _steps("scenarios/grain_store_active_sell_wheat_001.json")
    after = apply_turn_step(scenario.state, scenario.config, steps[0])
    assert "grain_store" in after.turn_progress.used_buildings
    assert all(step.building_id != "grain_store" for step in turn_steps(after, scenario.config))

    for path in (
        "scenarios/grain_store_merchant_none_no_hire_001.json",
        "scenarios/grain_store_insufficient_after_hire_001.json",
        "scenarios/grain_store_donated_no_conversion_001.json",
        "scenarios/grain_store_not_live_no_conversion_001.json",
    ):
        blocked, blocked_steps = _steps(path)
        assert blocked_steps == ()
        assert not any(step.building_id == "grain_store" for step in turn_steps(blocked.state, blocked.config))


def test_grain_store_step_events_precede_sowing_and_summary_stays_on_turn_action() -> None:
    scenario, steps = _steps("scenarios/grain_store_active_sell_wheat_001.json")
    step = _step(steps, direction="sell_wheat", amount=2)
    state, result = _tithe_after_step(scenario, step)
    bonus = next(event for event in _events(result.events, EventType.BUILDING_BONUS)
                 if dict(event.details).get("building") == "grain_store")
    delta = _events(result.events, EventType.RESOURCE_DELTA)[0]
    sowing = _events(result.events, EventType.SOWING)[0]
    assert result.events.index(bonus) < result.events.index(delta) < result.events.index(sowing)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1
    assert "grain_store" not in action_summary(next(action for action in legal_actions(
        state, scenario.config) if action.resolution is TurnResolutionType.TITHE), scenario.config)


def test_apply_own_active_buy_one_wheat_converts_resources() -> None:
    scenario, steps = _steps("scenarios/grain_store_active_buy_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, direction="buy_wheat", amount=1))
    delta = _events(state.events, EventType.RESOURCE_DELTA)[0]
    assert dict(delta.details) == {"stone": 0, "silver": -1, "wheat": 1}
    resources = state.player_state(PlayerId.PLAYER_ONE).resources
    assert (resources.silver, resources.wheat) == (1, 1)


def test_hired_market_grain_store_pays_bank_before_conversion() -> None:
    scenario, steps = _steps("scenarios/grain_store_hire_market_sell_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, source="market", amount=2))
    hired = _events(state.events, EventType.BUILDING_HIRED)[0]
    bonus = _events(state.events, EventType.BUILDING_BONUS)[0]
    delta = _events(state.events, EventType.RESOURCE_DELTA)[0]
    assert dict(hired.details)["payee"] == "bank"
    assert state.events.index(hired) < state.events.index(bonus) < state.events.index(delta)


def test_hired_opponent_grain_store_pays_owner_before_conversion() -> None:
    scenario, steps = _steps("scenarios/grain_store_hire_opponent_buy_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, source="player_two", amount=2))
    hired = _events(state.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["payee"] == "player_two"
    assert state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 2
    assert state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_grain_store_step_can_enable_later_ordination() -> None:
    scenario, steps = _steps("scenarios/grain_store_buy_then_ordination_001.json")
    step = _step(steps, direction="buy_wheat", amount=1)
    state = apply_turn_step(scenario.state, scenario.config, step)
    action = next(
        action for action in legal_actions(state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION and action.ordination_steps == ("ordain",)
    )
    result = apply_action(state, action, scenario.config)
    resource_delta_events = _events(result.events, EventType.RESOURCE_DELTA)
    assert len(resource_delta_events) == 2
    assert dict(resource_delta_events[0].details) == {"stone": 0, "silver": -1, "wheat": 1}
    assert dict(resource_delta_events[1].details) == {"stone": 0, "silver": 0, "wheat": -1}
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_action_summary_includes_grain_store_conversion_and_hire_suffix() -> None:
    own_scenario, own_steps = _steps("scenarios/grain_store_active_sell_wheat_001.json")
    own = _step(own_steps, direction="sell_wheat", amount=2)
    assert "use building: grain_store to sell 2 wheat for 2 silver" in action_summary(
        own, own_scenario.config
    )
    hired_scenario, hired_steps = _steps("scenarios/grain_store_hire_market_buy_wheat_001.json")
    hired = _step(hired_steps, source="market", direction="buy_wheat", amount=1)
    summary = action_summary(hired, hired_scenario.config)
    assert "use building: grain_store to buy 1 wheat for 1 silver" in summary
    assert "hire building: grain_store from market" in summary


def test_grain_store_step_rejects_amount_unaffordable_after_hire() -> None:
    scenario = load_scenario("scenarios/grain_store_insufficient_after_hire_001.json")
    source = building_ability_source(
        scenario.state, scenario.config, acting_player=scenario.state.active_player, building_key="grain_store"
    )
    assert source.hire_resource == "silver"
    step = BuildingConversionStep("grain_store", "market", "buy_wheat", 1)
    with pytest.raises(TransitionValidationError, match="Grain Store buy conversion requires enough silver after hire payment"):
        apply_turn_step(scenario.state, scenario.config, step)


def test_grain_store_step_can_be_composed_after_a_kogge_route_choice() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=player.resources.add(wheat=2), player_board_slots=replace(
            player.player_board_slots, active_buildings=(*player.player_board_slots.active_buildings, "grain_store")
        )),
    )
    step = _step(turn_steps(state, scenario.config), direction="sell_wheat", amount=1)
    state = apply_turn_step(state, scenario.config, step)
    assert any(action.sow_route_building_id == "kogge" for action in legal_actions(state, scenario.config))
