from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingConversionStep, EndTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, apply_turn_step, legal_actions, turn_steps


def _scenario_steps(path: str):
    scenario = load_scenario(path)
    return scenario, tuple(turn_steps(scenario.state, scenario.config))


def _step(steps, **values):
    return next(step for step in steps if all(getattr(step, key) == value for key, value in values.items()))


def _events(events, event_type):
    return [event for event in events if event.event_type is event_type]


def test_indulgences_steps_offer_sell_and_buy_amounts() -> None:
    _scenario, sell_steps = _scenario_steps("scenarios/indulgences_active_sell_piety_001.json")
    assert {step.amount for step in sell_steps if step.direction == "sell_piety"} == {1, 2, 3}
    assert all(step.source == "own_active" for step in sell_steps)

    _scenario, buy_steps = _scenario_steps("scenarios/indulgences_active_buy_piety_001.json")
    assert {step.amount for step in buy_steps if step.direction == "buy_piety"} == {1, 2}
    assert all(step.building_id == "indulgences" for step in buy_steps)


def test_own_active_indulgences_generates_buy_variants_for_each_amount() -> None:
    _scenario, steps = _scenario_steps("scenarios/indulgences_active_buy_piety_001.json")
    assert {step.amount for step in steps if step.direction == "buy_piety"} == {1, 2}
    assert all(step.source == "own_active" for step in steps)


def test_hired_market_indulgences_generates_sell_variants_when_payable() -> None:
    _scenario, steps = _scenario_steps("scenarios/indulgences_hire_market_sell_piety_001.json")
    assert {step.amount for step in steps if step.direction == "sell_piety"} == {1, 2}
    assert all(step.source == "market" for step in steps)


def test_hired_opponent_indulgences_generates_buy_variants_when_payable() -> None:
    _scenario, steps = _scenario_steps("scenarios/indulgences_hire_opponent_buy_piety_001.json")
    assert {step.amount for step in steps if step.direction == "buy_piety"} == {1, 2, 3}
    assert all(step.source == "player_two" for step in steps)


def test_indulgences_hired_sources_are_offered() -> None:
    _scenario, market_steps = _scenario_steps("scenarios/indulgences_hire_market_sell_piety_001.json")
    assert any(step.source == "market" and step.direction == "sell_piety" for step in market_steps)
    _scenario, opponent_steps = _scenario_steps("scenarios/indulgences_hire_opponent_buy_piety_001.json")
    assert any(step.source == "player_two" and step.direction == "buy_piety" for step in opponent_steps)


def test_indulgences_respect_piety_bounds_and_source_priority() -> None:
    _scenario, steps = _scenario_steps("scenarios/indulgences_active_buy_piety_001.json")
    assert all(step.direction != "sell_piety" for step in steps)

    scenario = load_scenario("scenarios/indulgences_hire_market_sell_piety_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, player_board_slots=replace(player.player_board_slots, active_buildings=("indulgences",))),
    )
    assert turn_steps(state, scenario.config)
    assert all(step.source == "own_active" for step in turn_steps(state, scenario.config))

    for path in (
        "scenarios/indulgences_merchant_none_no_hire_001.json",
        "scenarios/indulgences_insufficient_after_hire_001.json",
        "scenarios/indulgences_donated_no_conversion_001.json",
        "scenarios/indulgences_not_live_no_conversion_001.json",
    ):
        blocked = load_scenario(path)
        assert turn_steps(blocked.state, blocked.config) == ()


def test_sell_variants_not_generated_at_piety_zero() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    assert not [step for step in turn_steps(scenario.state, scenario.config) if step.direction == "sell_piety"]


def test_buy_variants_not_generated_at_piety_cap() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, piety=scenario.config.piety.max_position),
    )
    assert not [step for step in turn_steps(state, scenario.config) if step.direction == "buy_piety"]


def test_indulgences_step_events_and_resources_flow_into_the_full_turn() -> None:
    scenario, steps = _scenario_steps("scenarios/indulgences_active_sell_piety_001.json")
    step = _step(steps, direction="sell_piety", amount=2)
    state = apply_turn_step(scenario.state, scenario.config, step)
    north_east = scenario.config.board.index_for_name("north_east")
    action = next(action for action in legal_actions(state, scenario.config)
                  if action.selected_duty == north_east and action.resolution is TurnResolutionType.TITHE)
    result = apply_action(state, action, scenario.config)
    delta = _events(result.events, EventType.RESOURCE_DELTA)[0]
    assert dict(delta.details) == {"stone": 0, "silver": 2, "wheat": 0, "piety": -2}
    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 1


def test_apply_own_active_buy_one_piety_converts_resources() -> None:
    scenario, steps = _scenario_steps("scenarios/indulgences_active_buy_piety_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, direction="buy_piety", amount=1))
    delta = _events(state.events, EventType.RESOURCE_DELTA)[0]
    assert dict(delta.details) == {"stone": 0, "silver": -1, "wheat": 0, "piety": 1}
    assert state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1
    assert state.player_state(PlayerId.PLAYER_ONE).piety == 1


def test_hired_market_indulgences_pays_bank_before_conversion() -> None:
    scenario, steps = _scenario_steps("scenarios/indulgences_hire_market_sell_piety_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, source="market", amount=2))
    hired = _events(state.events, EventType.BUILDING_HIRED)[0]
    bonus = _events(state.events, EventType.BUILDING_BONUS)[0]
    delta = _events(state.events, EventType.RESOURCE_DELTA)[0]
    assert dict(hired.details)["payee"] == "bank"
    assert state.events.index(hired) < state.events.index(bonus) < state.events.index(delta)


def test_hired_opponent_indulgences_pays_owner_before_conversion() -> None:
    scenario, steps = _scenario_steps("scenarios/indulgences_hire_opponent_buy_piety_001.json")
    state = apply_turn_step(scenario.state, scenario.config, _step(steps, source="player_two", amount=2))
    hired = _events(state.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["payee"] == "player_two"
    assert state.player_state(PlayerId.PLAYER_ONE).piety == 2
    assert state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_buy_conversion_that_cannot_pay_after_hire() -> None:
    scenario = load_scenario("scenarios/indulgences_insufficient_after_hire_001.json")
    with pytest.raises(
        TransitionValidationError,
        match="Indulgences buy conversion requires enough silver after hire payment",
    ):
        apply_turn_step(
            scenario.state,
            scenario.config,
            BuildingConversionStep("indulgences", "market", "buy_piety", 1, "silver"),
        )


def test_apply_rejects_sell_conversion_below_zero_piety() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    with pytest.raises(
        TransitionValidationError,
        match="Indulgences sell conversion requires enough piety after hire payment",
    ):
        apply_turn_step(
            scenario.state,
            scenario.config,
            BuildingConversionStep("indulgences", "own_active", "sell_piety", 1),
        )


def test_apply_rejects_buy_conversion_above_piety_cap() -> None:
    scenario = load_scenario("scenarios/indulgences_active_buy_piety_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, piety=scenario.config.piety.max_position, resources=player.resources.add(silver=1)),
    )
    with pytest.raises(
        TransitionValidationError,
        match="Indulgences buy conversion exceeds piety track maximum",
    ):
        apply_turn_step(
            state,
            scenario.config,
            BuildingConversionStep("indulgences", "own_active", "buy_piety", 1),
        )


def test_converted_piety_can_change_who_takes_the_first_player_marker() -> None:
    scenario, steps = _scenario_steps("scenarios/indulgences_buy_then_round_end_start_player_001.json")
    conversion_state = apply_turn_step(
        scenario.state,
        scenario.config,
        _step(steps, direction="buy_piety", amount=1),
    )
    with_conversion_action = next(
        action for action in legal_actions(conversion_state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    )
    without_conversion_action = next(
        action for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    )
    with_resolution = apply_action(conversion_state, with_conversion_action, scenario.config)
    assert with_resolution.state.turn_progress.resolution_committed
    with_conversion = apply_action(
        with_resolution.state,
        EndTurnAction(),
        scenario.config,
    )
    with_conversion_events = (*with_resolution.events, *with_conversion.events)
    without_conversion = apply_action(scenario.state, without_conversion_action, scenario.config)
    assert without_conversion.state.turn_progress.resolution_committed
    without_conversion = apply_action(
        without_conversion.state,
        EndTurnAction(),
        scenario.config,
    )
    assert with_conversion.state.active_player is PlayerId.PLAYER_TWO
    assert without_conversion.state.active_player is PlayerId.PLAYER_ONE
    marker = _events(with_conversion_events, EventType.START_PLAYER_MARKER)[0]
    assert dict(marker.details)["deciding_player"] == "player_two"


def test_indulgences_used_set_blocks_a_second_step() -> None:
    scenario, steps = _scenario_steps("scenarios/indulgences_active_sell_piety_001.json")
    state = apply_turn_step(scenario.state, scenario.config, steps[0])
    assert all(step.building_id != "indulgences" for step in turn_steps(state, scenario.config))


def test_action_summary_includes_indulgences_conversion_and_hire_suffix() -> None:
    own_scenario, own_steps = _scenario_steps("scenarios/indulgences_active_sell_piety_001.json")
    own = _step(own_steps, direction="sell_piety", amount=2)
    assert "use building: indulgences to sell 2 piety for 2 silver" in action_summary(
        own, own_scenario.config
    )
    hired_scenario, hired_steps = _scenario_steps("scenarios/indulgences_hire_market_buy_piety_001.json")
    hired = _step(hired_steps, source="market", direction="buy_piety", amount=1)
    summary = action_summary(hired, hired_scenario.config)
    assert "hire building: indulgences from market" in summary
