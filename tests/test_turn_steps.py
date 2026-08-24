from __future__ import annotations

import inspect
import json
from dataclasses import replace

from pilgrim.io.logs import state_to_record
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingConversionStep, EndTurnAction
from pilgrim.model.enums import PlayerId
from pilgrim.rules.transition import (
    apply_action,
    apply_turn_step,
    full_turn_actions,
    legal_actions,
    turn_steps,
)


def _scenario(path: str):
    return load_scenario(path)


def test_apply_turn_step_is_pure_and_leaves_a_hashable_state() -> None:
    scenario = _scenario("scenarios/grain_store_active_sell_wheat_001.json")
    before = scenario.state
    step = turn_steps(before, scenario.config)[0]
    after = apply_turn_step(before, scenario.config, step)

    assert before == scenario.state
    assert before.turn_progress.used_buildings == frozenset()
    assert after.turn_progress.used_buildings == frozenset({"grain_store"})
    assert hash(before) == hash(scenario.state)
    assert isinstance(hash(after), int)


def test_turn_progress_is_serialised_and_end_of_turn_resets_it() -> None:
    scenario = _scenario("scenarios/grain_store_active_sell_wheat_001.json")
    state = apply_turn_step(scenario.state, scenario.config, turn_steps(scenario.state, scenario.config)[0])
    record = state_to_record(state)
    assert record["turn_progress"]["used_buildings"] == ["grain_store"]
    json.dumps(record)

    action = next(iter(legal_actions(state, scenario.config)))
    resolution = apply_action(state, action, scenario.config)
    assert resolution.state.turn_progress.used_buildings == frozenset({"grain_store"})
    result = apply_action(resolution.state, EndTurnAction(), scenario.config)
    assert result.state.turn_progress.used_buildings == frozenset()
    assert result.state.turn_progress.events == ()


def test_two_independent_conversions_transpose() -> None:
    scenario = _scenario("scenarios/grain_store_active_sell_wheat_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player,
            resources=player.resources.add(stone=1, wheat=1),
            player_board_slots=replace(
                player.player_board_slots,
                active_buildings=("grain_store", "stone_yard"),
            ),
        ),
    )
    steps = turn_steps(state, scenario.config)
    grain = next(step for step in steps if step.building_id == "grain_store" and step.direction == "sell_wheat")
    stone = next(step for step in steps if step.building_id == "stone_yard" and step.direction == "sell_stone")
    first = apply_turn_step(apply_turn_step(state, scenario.config, grain), scenario.config, stone)
    second = apply_turn_step(apply_turn_step(state, scenario.config, stone), scenario.config, grain)
    assert first == second
    assert first.turn_progress.used_buildings == frozenset({"grain_store", "stone_yard"})
    before = state.player_state(PlayerId.PLAYER_ONE).resources
    after = first.player_state(PlayerId.PLAYER_ONE).resources
    assert (
        after.stone - before.stone,
        after.silver - before.silver,
        after.wheat - before.wheat,
    ) == (-1, 2, -1)


def test_full_turn_actions_collapses_conversion_order_transpositions() -> None:
    scenario = _scenario("scenarios/brewery_active_sell_wheat_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player,
            piety=1,
            player_board_slots=replace(
                player.player_board_slots,
                active_buildings=("brewery", "indulgences"),
            ),
        ),
    )
    piety = replace(
        scenario.config.piety,
        max_position=1,
        score_by_position=scenario.config.piety.score_by_position[:2],
    )
    config = replace(scenario.config, piety=piety)
    actions = tuple(full_turn_actions(state, config))
    assert len(actions) == len(set(actions))


def test_two_active_conversion_buildings_remain_independently_available() -> None:
    scenario = _scenario("scenarios/two_active_conversions_001.json")
    initial_steps = turn_steps(scenario.state, scenario.config)
    assert {step.building_id for step in initial_steps} == {"grain_store", "stone_yard"}

    grain = next(step for step in initial_steps if step.building_id == "grain_store")
    stone = next(step for step in initial_steps if step.building_id == "stone_yard")
    after_grain = apply_turn_step(scenario.state, scenario.config, grain)
    after_stone = apply_turn_step(scenario.state, scenario.config, stone)
    assert "stone_yard" in {step.building_id for step in turn_steps(after_grain, scenario.config)}
    assert "grain_store" in {step.building_id for step in turn_steps(after_stone, scenario.config)}

    after_both = apply_turn_step(after_grain, scenario.config, stone)
    assert after_both.turn_progress.used_buildings == frozenset({"grain_store", "stone_yard"})
    assert all(
        step.building_id not in after_both.turn_progress.used_buildings
        for step in turn_steps(after_both, scenario.config)
    )


def test_full_turn_actions_is_a_lazy_generator() -> None:
    scenario = _scenario("scenarios/grain_store_active_sell_wheat_001.json")
    composed = full_turn_actions(scenario.state, scenario.config)
    assert inspect.isgenerator(composed)
    assert next(composed)


def test_hired_conversion_step_records_the_payment_resource() -> None:
    scenario = _scenario("scenarios/grain_store_hire_market_sell_wheat_001.json")
    steps = turn_steps(scenario.state, scenario.config)
    assert {step.hire_payment for step in steps} == {"wheat"}
