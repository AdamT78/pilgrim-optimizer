from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_id
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules import sow_routes as sow_routes_module
from pilgrim.rules import transition as transition_module
from pilgrim.rules.building_turn_modifiers import (
    implemented_turn_modifiers,
    scaffolded_turn_modifiers,
)
from pilgrim.rules.sow_routes import SowRouteVariant, cloisters_actual_placements_after_omission
from pilgrim.rules.transition import apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _legacy_kogge_city_start_routes(*, origin: int, picked_up: int, board):
    if picked_up <= 0:
        return ()
    city = board.index_for_name("city")
    if origin != city:
        return ()
    east = board.index_for_name("east")
    west = board.index_for_name("west")
    routes = []
    for first_step in (east, west):
        for suffix in transition_module.generate_routes(first_step, picked_up - 1, board):
            routes.append((first_step, *suffix))
    return tuple(routes)


def _legacy_route_requires_kogge(*, origin: int, route: tuple[int, ...], board) -> bool:
    if not route:
        return False
    city = board.index_for_name("city")
    if origin != city:
        return False
    first_step = route[0]
    east = board.index_for_name("east")
    west = board.index_for_name("west")
    if first_step in board.neighbors(city):
        return False
    return first_step in (east, west)


def _legacy_combined_kogge_cloisters_route_variants(*, origin: int, picked_up: int, board):
    if picked_up <= 0:
        return ()
    allowed = sow_routes_module._allowed_cloisters_omission_locations(board)
    variants: list[SowRouteVariant] = []
    for candidate_route in _legacy_kogge_city_start_routes(
        origin=origin,
        picked_up=picked_up + 1,
        board=board,
    ):
        for omitted_index, omitted_location in enumerate(candidate_route):
            if omitted_location not in allowed:
                continue
            variants.append(
                SowRouteVariant(
                    route=cloisters_actual_placements_after_omission(
                        candidate_route,
                        omitted_index=omitted_index,
                    ),
                    omitted_location=omitted_location,
                )
            )
    return sow_routes_module.dedupe_sow_route_variants(tuple(variants))


def _legacy_legal_actions(state, config, monkeypatch) -> list:
    with monkeypatch.context() as patched:
        patched.setattr(transition_module, "kogge_sow_routes", _legacy_kogge_city_start_routes)
        patched.setattr(
            transition_module,
            "combined_kogge_cloisters_route_variants",
            _legacy_combined_kogge_cloisters_route_variants,
        )
        patched.setattr(
            transition_module,
            "_route_requires_kogge_for_origin_route",
            _legacy_route_requires_kogge,
        )
        return list(legal_actions(state, config))


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
    scenario = load_scenario("scenarios/kogge_hire_market_city_to_east_001.json")
    city = scenario.config.board.index_for_name("city")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.origin == city and action.route
    ]
    east_action = next(
        action
        for action in actions
        if _first_step_name(action, scenario) == "east"
        and action.sow_route_building_source == "market"
    )
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
    scenario = load_scenario("scenarios/kogge_hire_opponent_city_to_west_001.json")
    city = scenario.config.board.index_for_name("city")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.origin == city and action.route
    ]
    west_action = next(
        action
        for action in actions
        if _first_step_name(action, scenario) == "west"
        and action.sow_route_building_source == "player_two"
    )
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
    assert all(action.sow_route_building_id != "kogge" for action in actions)


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


def test_kogge_can_modify_non_city_sow_origins_when_route_uses_reversed_city_spokes() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    city = board.index_for_name("city")
    west = board.index_for_name("west")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    shifted_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            workforce=replace(
                player_state.workforce,
                mancala=(0, 2, 0, 0, 0, 0, 0, 0, 0),
            ),
        ),
    )
    actions = legal_actions(shifted_state, scenario.config)

    assert actions
    against_flow = [
        action
        for action in actions
        if action.origin == north and len(action.route) == 2 and action.route == (city, west)
    ]
    assert against_flow
    assert all(action.sow_route_building_id == "kogge" for action in against_flow)


def test_turn_modifier_registry_marks_all_turn_modifiers_as_implemented() -> None:
    assert {entry.building_key for entry in implemented_turn_modifiers()} == {
        "kogge",
        "cloisters",
        "dormitory",
        "inquisition",
        "library",
    }
    assert scaffolded_turn_modifiers() == ()


def test_kogge_widening_only_moves_corpus_scenarios_where_kogge_is_reachable(
    monkeypatch, corpus_actions
) -> None:
    # The Bank+Mill carrier is part of the direct scenario corpus; this Kogge audit must keep
    # traversing it even though it cannot move under the legacy Kogge implementation.
    assert len(corpus_actions) == 317

    moved_without_kogge_reach: list[str] = []
    checked_without_kogge_reach = 0
    for path, scenario, current_actions in corpus_actions:
        legacy_actions = _legacy_legal_actions(scenario.state, scenario.config, monkeypatch)

        current_ids = {action_id(action) for action in current_actions}
        legacy_ids = {action_id(action) for action in legacy_actions}
        if current_ids == legacy_ids:
            continue

        current_has_kogge = any(
            getattr(action, "sow_route_building_id", None) == "kogge"
            or getattr(action, "sow_route_secondary_building_id", None) == "kogge"
            for action in current_actions
        )
        legacy_has_kogge = any(
            getattr(action, "sow_route_building_id", None) == "kogge"
            or getattr(action, "sow_route_secondary_building_id", None) == "kogge"
            for action in legacy_actions
        )
        if not (current_has_kogge or legacy_has_kogge):
            moved_without_kogge_reach.append(path.name)
        else:
            checked_without_kogge_reach += 1

    assert not moved_without_kogge_reach, (
        "scenarios changed without any Kogge-reachable legal action: "
        f"{moved_without_kogge_reach[:10]}"
    )
    assert checked_without_kogge_reach > 0
