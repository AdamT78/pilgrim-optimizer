from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingRelocationStep, EndTurnAction, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)
from pilgrim.search.exact import solve_exact


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _resolved_state(path: str):
    scenario = load_scenario(path)
    city = scenario.config.board.index_for_name("city")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.origin == city and action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    result = apply_action(scenario.state, action, scenario.config)
    assert result.state.turn_progress.resolution_committed
    return scenario, result


def _library_steps(state, config):
    return [step for step in turn_steps(state, config) if step.building_id == "library"]


def test_relocation_steps_are_offered_in_their_respective_windows() -> None:
    library_scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    assert _library_steps(library_scenario.state, library_scenario.config) == []
    assert not {
        step.building_id
        for step in turn_steps(library_scenario.state, library_scenario.config)
        if step.building_id in {"dormitory", "inquisition"}
    }

    _scenario, resolution = _resolved_state("scenarios/library_active_city_to_duty_001.json")
    assert _library_steps(resolution.state, library_scenario.config)
    assert not {
        step.building_id
        for step in turn_steps(resolution.state, library_scenario.config)
        if step.building_id in {"dormitory", "inquisition"}
    }

    for path, building_id in (
        ("scenarios/dormitory_active_return_duty_to_city_001.json", "dormitory"),
        ("scenarios/inquisition_active_city_to_duty_001.json", "inquisition"),
    ):
        scenario = load_scenario(path)
        assert building_id in {step.building_id for step in turn_steps(scenario.state, scenario.config)}
        result = apply_action(
            scenario.state,
            next(iter(legal_actions(scenario.state, scenario.config))),
            scenario.config,
        )
        assert result.state.turn_progress.resolution_committed
        assert building_id not in {
            step.building_id for step in turn_steps(result.state, scenario.config)
        }


def test_library_targets_every_duty_and_abbey_after_resolution() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    _scenario, resolution = _resolved_state("scenarios/library_active_city_to_duty_001.json")
    steps = _library_steps(resolution.state, scenario.config)
    city = scenario.config.board.index_for_name("city")

    assert all(step.source == "own_active" and step.hire_payment is None for step in steps)
    assert {step.selected_position for step in steps} == {
        *set(scenario.config.duty_positions()) - {city},
        "abbey",
    }
    assert legal_actions(resolution.state, scenario.config) == (EndTurnAction(),)


def test_library_market_and_opponent_hires_are_steps_paid_after_turn_earnings() -> None:
    market_scenario = load_scenario("scenarios/library_hire_market_city_to_abbey_001.json")
    market_player = market_scenario.state.active_player
    market_player_state = market_scenario.state.player_state(market_player)
    market_start = market_scenario.state.with_player_state(
        market_player,
        replace(
            market_player_state,
            resources=replace(market_player_state.resources, wheat=0),
        ),
    )
    market_action = next(
        action
        for action in legal_actions(market_start, market_scenario.config)
        if action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    market_resolution = apply_action(market_start, market_action, market_scenario.config)
    assert market_start.player_state(market_player).resources.wheat == 0
    assert market_resolution.state.player_state(market_player).resources.wheat == 1
    market_step = next(
        step for step in _library_steps(market_resolution.state, market_scenario.config)
        if step.selected_position == "abbey"
    )
    assert market_step.source == "market"
    market_state = apply_turn_step(market_resolution.state, market_scenario.config, market_step)
    market_events = market_state.turn_progress.events
    assert dict(_events_of_type(market_events, EventType.BUILDING_HIRED)[0].details)["payee"] == "bank"
    assert market_state.player_state(market_player).resources.wheat == 0

    opponent_scenario, opponent_resolution = _resolved_state(
        "scenarios/library_hire_opponent_city_to_duty_001.json"
    )
    west = opponent_scenario.config.board.index_for_name("west")
    opponent_step = next(
        step for step in _library_steps(opponent_resolution.state, opponent_scenario.config)
        if step.selected_position == west
    )
    assert opponent_step.source == "player_two"
    opponent_state = apply_turn_step(opponent_resolution.state, opponent_scenario.config, opponent_step)
    hired = _events_of_type(opponent_state.turn_progress.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["payee"] == "player_two"
    assert opponent_state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


@pytest.mark.parametrize(
    "path",
    (
        "scenarios/library_merchant_none_no_hire_001.json",
        "scenarios/library_insufficient_resource_no_hire_001.json",
        "scenarios/library_donated_no_modifier_001.json",
        "scenarios/library_not_live_no_modifier_001.json",
        "scenarios/library_no_city_acolyte_after_turn_no_modifier_001.json",
    ),
)
def test_library_is_not_offered_when_its_source_or_city_acolyte_is_unavailable(path: str) -> None:
    scenario = load_scenario(path)
    resolution = apply_action(
        scenario.state,
        next(iter(legal_actions(scenario.state, scenario.config))),
        scenario.config,
    )
    assert resolution.state.turn_progress.resolution_committed
    assert _library_steps(resolution.state, scenario.config) == [], path


def test_library_step_moves_after_recall_and_before_turn_advance() -> None:
    scenario, resolution = _resolved_state("scenarios/library_active_city_to_duty_001.json")
    west = scenario.config.board.index_for_name("west")
    step = next(
        step for step in _library_steps(resolution.state, scenario.config) if step.selected_position == west
    )
    after_step = apply_turn_step(resolution.state, scenario.config, step)
    passed = apply_action(after_step, EndTurnAction(), scenario.config)
    events = (*resolution.events, *after_step.turn_progress.events, *passed.events)

    recall = _events_of_type(events, EventType.ACOLYTE_RECALL)[0]
    bonus = _events_of_type(events, EventType.BUILDING_BONUS)[0]
    relocation = _events_of_type(events, EventType.END_TURN_RELOCATION)[0]
    advance = _events_of_type(events, EventType.TURN_ADVANCE)[0]
    assert events.index(recall) < events.index(bonus) < events.index(relocation) < events.index(advance)


def test_library_rejects_pre_resolution_and_invalid_target() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    pre_resolution = BuildingRelocationStep("library", "own_active", "abbey")
    with pytest.raises(TransitionValidationError, match="only available after resolution"):
        apply_turn_step(scenario.state, scenario.config, pre_resolution)

    _scenario, resolution = _resolved_state("scenarios/library_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    invalid = BuildingRelocationStep("library", "own_active", city)
    with pytest.raises(TransitionValidationError, match="Abbey or a non-city Duty"):
        apply_turn_step(resolution.state, scenario.config, invalid)


def test_library_rejects_a_step_whose_source_does_not_match_the_opening() -> None:
    scenario, resolution = _resolved_state("scenarios/library_active_city_to_duty_001.json")
    invalid = BuildingRelocationStep("library", "market", "abbey", "wheat")
    with pytest.raises(TransitionValidationError, match="source does not match"):
        apply_turn_step(resolution.state, scenario.config, invalid)


def test_full_turn_actions_have_no_library_relocation_fields_or_id_suffix() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    action = next(iter(legal_actions(scenario.state, scenario.config)))

    for field in (
        "end_turn_building_id",
        "end_turn_building_source",
        "end_turn_relocation_from",
        "end_turn_relocation_to",
    ):
        assert not hasattr(action, field), f"FullTurnAction still exposes {field}"
    assert "end_turn" not in action_id(action), "action_id still serializes an end-turn suffix"


def test_exact_search_refuses_library_in_the_end_of_turn_window() -> None:
    scenario, resolution = _resolved_state("scenarios/library_active_city_to_duty_001.json")

    with pytest.raises(RuntimeError, match="cannot enumerate committed turn steps") as raised:
        solve_exact(resolution.state, scenario.config, depth=0)

    assert "BuildingRelocationStep(building_id='library'" in str(raised.value)


def test_library_can_follow_a_committed_start_turn_relocation() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(*player_state.player_board_slots.active_buildings, "library"),
            ),
        ),
    )
    dormitory_step = next(
        step for step in turn_steps(state, scenario.config) if step.building_id == "dormitory"
    )
    after_dormitory = apply_turn_step(state, scenario.config, dormitory_step)
    action = next(iter(legal_actions(after_dormitory, scenario.config)))
    resolution = apply_action(after_dormitory, action, scenario.config)
    assert _library_steps(resolution.state, scenario.config)


def test_library_can_follow_a_committed_pulpit_step() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(*player_state.player_board_slots.active_buildings, "pulpit"),
            ),
        ),
    )
    pulpit_step = next(
        step for step in turn_steps(state, scenario.config) if step.building_id == "pulpit"
    )
    after_pulpit = apply_turn_step(state, scenario.config, pulpit_step)
    action = next(
        action
        for action in legal_actions(after_pulpit, scenario.config)
        if action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    resolution = apply_action(after_pulpit, action, scenario.config)
    assert _library_steps(resolution.state, scenario.config), (
        "Library must remain available after Pulpit's committed turn step"
    )
