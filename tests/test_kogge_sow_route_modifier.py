from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules.building_turn_modifiers import (
    implemented_turn_modifiers,
    scaffolded_turn_modifiers,
)
from pilgrim.rules.transition import apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _city_route_actions(path: str):
    scenario = load_scenario(path)
    city = scenario.config.board.index_for_name("city")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.origin == city and action.route
    ]
    return scenario, actions


def _first_step_name(action, scenario) -> str:
    return scenario.config.board.positions[action.route[0]]


def test_without_kogge_city_east_and_west_routes_are_not_legal() -> None:
    scenario, actions = _city_route_actions("scenarios/produce_wheat_001.json")
    first_steps = {_first_step_name(action, scenario) for action in actions}

    assert "east" not in first_steps
    assert "west" not in first_steps
    assert {"north", "south"}.issubset(first_steps)


def test_own_active_kogge_adds_city_east_and_west_routes() -> None:
    scenario, actions = _city_route_actions("scenarios/kogge_active_city_to_east_001.json")
    east_west_actions = [
        action for action in actions if _first_step_name(action, scenario) in {"east", "west"}
    ]

    assert east_west_actions
    assert all(action.sow_route_building_id == "kogge" for action in east_west_actions)
    assert all(
        action.sow_route_building_source == "own_active" for action in east_west_actions
    )


def test_market_hired_kogge_route_emits_hired_then_bonus_then_sowing() -> None:
    scenario, actions = _city_route_actions("scenarios/kogge_hire_market_city_to_east_001.json")
    east_action = next(action for action in actions if _first_step_name(action, scenario) == "east")
    result = apply_action(scenario.state, east_action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "kogge"
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)
    bonus_details = dict(bonus_event.details)

    assert east_action.sow_route_building_id == "kogge"
    assert east_action.sow_route_building_source == "market"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert bonus_details["enabled_route"] == "city -> east"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_opponent_hired_kogge_route_pays_owner() -> None:
    scenario, actions = _city_route_actions("scenarios/kogge_hire_opponent_city_to_west_001.json")
    west_action = next(action for action in actions if _first_step_name(action, scenario) == "west")
    result = apply_action(scenario.state, west_action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert west_action.sow_route_building_id == "kogge"
    assert west_action.sow_route_building_source == "player_two"
    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


@pytest.mark.parametrize(
    "scenario_path",
    [
        "scenarios/kogge_merchant_none_no_extra_routes_001.json",
        "scenarios/kogge_insufficient_resource_no_extra_routes_001.json",
        "scenarios/kogge_donated_no_extra_routes_001.json",
        "scenarios/kogge_not_live_no_extra_routes_001.json",
    ],
)
def test_unusable_kogge_does_not_add_city_east_or_west_routes(scenario_path: str) -> None:
    scenario, actions = _city_route_actions(scenario_path)
    first_steps = {_first_step_name(action, scenario) for action in actions}

    assert "east" not in first_steps
    assert "west" not in first_steps
    assert {"north", "south"}.issubset(first_steps)
    assert all(action.sow_route_building_id is None for action in actions)


def test_own_active_kogge_bonus_emits_before_sowing_without_hired_event() -> None:
    scenario, actions = _city_route_actions("scenarios/kogge_active_city_to_west_001.json")
    west_action = next(action for action in actions if _first_step_name(action, scenario) == "west")
    result = apply_action(scenario.state, west_action, scenario.config)

    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "kogge"
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[0]

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert dict(bonus_event.details)["enabled_route"] == "city -> west"
    assert result.events.index(bonus_event) < result.events.index(sowing_event)
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_kogge_available_but_unused_route_emits_no_kogge_events() -> None:
    scenario, actions = _city_route_actions("scenarios/kogge_active_city_to_east_001.json")
    north_action = next(action for action in actions if _first_step_name(action, scenario) == "north")
    result = apply_action(scenario.state, north_action, scenario.config)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert not any(
        dict(event.details).get("building") == "kogge"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )


def test_kogge_does_not_modify_non_city_sow_origins() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    shifted_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            workforce=replace(
                player_state.workforce,
                mancala=(0, 1, 0, 0, 0, 0, 0, 0, 0),
            ),
        ),
    )
    actions = legal_actions(shifted_state, scenario.config)

    assert actions
    assert all(action.origin != scenario.config.board.index_for_name("city") for action in actions)
    assert all(action.sow_route_building_id is None for action in actions)


def test_turn_modifier_registry_marks_library_as_implemented() -> None:
    assert {entry.building_key for entry in implemented_turn_modifiers()} == {
        "kogge",
        "dormitory",
        "inquisition",
        "library",
    }
    assert {
        entry.building_key for entry in scaffolded_turn_modifiers()
    } == {"cloisters"}
