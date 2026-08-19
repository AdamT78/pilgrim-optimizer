from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.sow_routes import (
    combined_kogge_cloisters_route_variants,
    is_legal_route_with_kogge_and_cloisters_skip,
)
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _combined_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    combined = [
        action
        for action in actions
        if action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id == "cloisters"
    ]
    return scenario, actions, combined


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_combined_helper_routes_include_kogge_augmented_city_spokes_and_are_deduped() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_duty_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    east = board.index_for_name("east")
    west = board.index_for_name("west")

    variants = combined_kogge_cloisters_route_variants(
        origin=city,
        picked_up=2,
        board=board,
    )

    assert variants
    first_steps = {variant.route[0] for variant in variants}
    assert east in first_steps
    assert west in first_steps
    assert len(variants) == len({(variant.route, variant.omitted_location) for variant in variants})


def test_combined_helper_allows_city_omission_when_city_is_in_candidate() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_city_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")

    variants = combined_kogge_cloisters_route_variants(
        origin=city,
        picked_up=2,
        board=board,
    )

    assert any(variant.omitted_location == city for variant in variants)


def test_non_city_origin_can_generate_kogge_cloisters_combined_variants() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_duty_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    city = board.index_for_name("city")

    variants = combined_kogge_cloisters_route_variants(
        origin=north,
        picked_up=2,
        board=board,
    )
    assert variants
    assert any(variant.route and variant.route[0] == city for variant in variants)


def test_combined_helper_validates_kogge_and_cloisters_legality() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_duty_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    east = board.index_for_name("east")
    south = board.index_for_name("south")
    south_east = board.index_for_name("south_east")

    assert is_legal_route_with_kogge_and_cloisters_skip(
        origin=city,
        route=(east, south),
        board=board,
        omitted_location=south_east,
    )
    assert not is_legal_route_with_kogge_and_cloisters_skip(
        origin=city,
        route=(east, south),
        board=board,
        omitted_location=999,
    )


def test_legal_generation_own_own_includes_combined_plus_single_modifiers() -> None:
    scenario, actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json"
    )

    assert combined_actions
    assert all(action.origin == scenario.config.board.index_for_name("city") for action in combined_actions)
    assert any(
        action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id is None
        for action in actions
    )
    assert any(action.sow_route_building_id == "cloisters" for action in actions)
    assert any(action.sow_route_building_id is None for action in actions)


def test_combined_summary_own_active_shows_parallel_modifier_wording() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json"
    )
    board = scenario.config.board
    north_west = board.index_for_name("north_west")
    north = board.index_for_name("north")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_omitted_location == north_west
            and candidate.selected_duty == north
            and candidate.resolution is TurnResolutionType.PRODUCE_STONE
        ),
    )

    summary = action_summary(action, scenario.config)
    assert (
        summary
        == "Turn: sow city -> west -> north | use building: kogge | use building: cloisters to skip north_west | selected duty: north (produce) | action: produce_stone"
    )


def test_combined_summary_hired_keeps_hire_details_at_end() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_hire_both_market_001.json"
    )
    board = scenario.config.board
    city = board.index_for_name("city")
    west = board.index_for_name("west")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_building_source == "market"
            and candidate.sow_route_secondary_building_source == "market"
            and candidate.sow_route_omitted_location == city
            and candidate.selected_duty == west
            and candidate.resolution is TurnResolutionType.ALLOCATION
            and any(move.destination == "stone_mason" for move in candidate.allocation_moves)
        ),
    )

    summary = action_summary(action, scenario.config)
    assert summary.startswith("Turn: sow city -> ")
    assert " | use building: kogge | use building: cloisters to skip city | " in summary
    assert "selected duty: west (allocation) | action: allocation | moves: abbey -> stone_mason" in summary
    assert summary.endswith(
        "hire building: kogge from market | hire building: cloisters from market"
    )


def test_apply_own_own_combined_skip_duty_orders_kogge_then_cloisters_bonus_before_sowing() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json"
    )
    board = scenario.config.board
    south_east = board.index_for_name("south_east")
    south = board.index_for_name("south")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_building_source == "own_active"
            and candidate.sow_route_secondary_building_source == "own_active"
            and candidate.sow_route_omitted_location == south_east
            and candidate.selected_duty == south
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_events = _events_of_type(result.events, EventType.BUILDING_BONUS)
    kogge_bonus = _first_action(bonus_events, lambda event: dict(event.details).get("building") == "kogge")
    cloisters_bonus = _first_action(
        bonus_events,
        lambda event: dict(event.details).get("building") == "cloisters",
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    sowing_details = dict(sowing_event.details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert sowing_details["skipped"] == south_east
    assert result.events.index(kogge_bonus) < result.events.index(cloisters_bonus)
    assert result.events.index(cloisters_bonus) < result.events.index(sowing_event)


def test_apply_own_own_combined_can_skip_city_when_candidate_contains_city() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_own_own_skip_city_001.json"
    )
    board = scenario.config.board
    city = board.index_for_name("city")
    north = board.index_for_name("north")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_omitted_location == city
            and candidate.selected_duty == north
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    sowing_details = dict(_events_of_type(result.events, EventType.SOWING)[0].details)

    assert sowing_details["skipped"] == city


def test_hired_kogge_own_cloisters_combined_generates_and_pays_once() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_hire_kogge_own_cloisters_001.json"
    )
    south_east = scenario.config.board.index_for_name("south_east")
    south = scenario.config.board.index_for_name("south")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_building_source == "market"
            and candidate.sow_route_secondary_building_source == "own_active"
            and candidate.sow_route_omitted_location == south_east
            and candidate.selected_duty == south
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "kogge"
    assert hired_details["source"] == "market"
    # The hires spend the wheat and the tithe on south hands one back: south carries a wheat
    # counter, and these route-modifier turns all resolve as tithes.
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1


def test_own_kogge_hired_cloisters_combined_generates_and_pays_once() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_own_kogge_hire_cloisters_001.json"
    )
    south_east = scenario.config.board.index_for_name("south_east")
    south = scenario.config.board.index_for_name("south")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_building_source == "own_active"
            and candidate.sow_route_secondary_building_source == "market"
            and candidate.sow_route_omitted_location == south_east
            and candidate.selected_duty == south
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "cloisters"
    assert hired_details["source"] == "market"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1


def test_hired_both_market_combined_emits_two_hires_before_bonuses_and_sowing() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_hire_both_market_001.json"
    )
    south_east = scenario.config.board.index_for_name("south_east")
    south = scenario.config.board.index_for_name("south")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_building_source == "market"
            and candidate.sow_route_secondary_building_source == "market"
            and candidate.sow_route_omitted_location == south_east
            and candidate.selected_duty == south
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_events = _events_of_type(result.events, EventType.BUILDING_HIRED)
    bonus_events = _events_of_type(result.events, EventType.BUILDING_BONUS)
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    kogge_bonus = _first_action(bonus_events, lambda event: dict(event.details).get("building") == "kogge")
    cloisters_bonus = _first_action(
        bonus_events,
        lambda event: dict(event.details).get("building") == "cloisters",
    )

    assert len(hired_events) == 2
    assert [dict(event.details)["building_id"] for event in hired_events] == ["kogge", "cloisters"]
    assert result.events.index(hired_events[0]) < result.events.index(hired_events[1])
    assert result.events.index(hired_events[1]) < result.events.index(kogge_bonus)
    assert result.events.index(kogge_bonus) < result.events.index(cloisters_bonus)
    assert result.events.index(cloisters_bonus) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1


def test_hired_both_opponent_combined_pays_owner_twice() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_hire_both_opponent_001.json"
    )
    south_east = scenario.config.board.index_for_name("south_east")
    south = scenario.config.board.index_for_name("south")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_building_source == "player_two"
            and candidate.sow_route_secondary_building_source == "player_two"
            and candidate.sow_route_omitted_location == south_east
            and candidate.selected_duty == south
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_events = _events_of_type(result.events, EventType.BUILDING_HIRED)

    assert len(hired_events) == 2
    assert all(dict(event.details)["payee"] == "player_two" for event in hired_events)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 2


def test_insufficient_resources_blocks_two_hire_combined_but_single_hire_variants_remain() -> None:
    _scenario, actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_insufficient_for_two_hires_001.json"
    )

    assert combined_actions == []
    assert any(
        action.sow_route_building_id == "kogge"
        and action.sow_route_building_source == "market"
        and action.sow_route_secondary_building_id is None
        for action in actions
    )
    assert any(
        action.sow_route_building_id == "cloisters"
        and action.sow_route_building_source == "market"
        for action in actions
    )


def test_merchant_none_blocks_hired_combined_and_hired_single_variants() -> None:
    _scenario, actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_merchant_none_blocks_hired_combo_001.json"
    )

    assert combined_actions == []
    assert not any(action.sow_route_building_id == "kogge" for action in actions)
    assert not any(action.sow_route_building_id == "cloisters" for action in actions)
    assert any(action.sow_route_building_id is None for action in actions)


def test_apply_rejects_combined_selected_duty_equal_to_omitted_without_remaining_placement() -> None:
    scenario, _actions, combined_actions = _combined_actions(
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json"
    )
    south_east = scenario.config.board.index_for_name("south_east")
    action = _first_action(
        combined_actions,
        lambda candidate: (
            candidate.sow_route_omitted_location == south_east
            and candidate.selected_duty != south_east
        ),
    )
    invalid_action = replace(action, selected_duty=south_east)

    with pytest.raises(TransitionValidationError, match="Selected duty must contain"):
        apply_action(scenario.state, invalid_action, scenario.config)
