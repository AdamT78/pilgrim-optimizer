from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules import transition as transition_module
from pilgrim.rules.sow_routes import (
    cloisters_actual_placements_after_omission,
    combined_kogge_cloisters_route_variants,
    is_legal_route_with_kogge_and_cloisters_skip,
    kogge_cloisters_candidate_placements,
    route_requires_kogge,
    valid_cloisters_omissions,
)
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"
EXPECTED_MOVED_ACTION_DELTAS = {
    "kogge_and_cloisters_2p.json": 140,
    "kogge_cloisters_own_own_skip_city_001.json": 39,
    "kogge_cloisters_own_own_skip_duty_001.json": 39,
    "kogge_cloisters_hire_kogge_own_cloisters_001.json": 37,
    "kogge_cloisters_own_kogge_hire_cloisters_001.json": 37,
    "kogge_cloisters_hire_both_market_001.json": 35,
    "kogge_cloisters_hire_both_opponent_001.json": 35,
}


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


def _combined_candidate_walk_for_action(action, board) -> tuple[int, ...]:
    """The unique candidate walk (before Cloisters omission) represented by this combined action."""
    assert action.sow_route_omitted_location is not None
    matches: set[tuple[int, ...]] = set()
    for candidate_route in kogge_cloisters_candidate_placements(
        origin=action.origin,
        picked_up=len(action.route),
        board=board,
    ):
        for omitted_index, candidate_location in valid_cloisters_omissions(
            origin=action.origin,
            candidate_placements=candidate_route,
            board=board,
        ):
            if candidate_location != action.sow_route_omitted_location:
                continue
            if (
                cloisters_actual_placements_after_omission(
                    candidate_route,
                    omitted_index=omitted_index,
                )
                == tuple(action.route)
            ):
                matches.add(candidate_route)
    assert len(matches) == 1, (
        "combined action should map to one candidate walk "
        f"(origin={action.origin}, route={action.route}, omitted={action.sow_route_omitted_location})"
    )
    return next(iter(matches))


def _legacy_combined_kogge_cloisters_route_options_without_kogge_requirement(
    state,
    config,
    *,
    origin: int,
    picked_up: int,
):
    if picked_up <= 0:
        return ()
    kogge_source = transition_module.building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=transition_module._ROUTE_BUILDING_KOGGE,
    )
    if not kogge_source.usable or (
        kogge_source.source_type != "own_active" and not transition_module._is_hired_source(kogge_source)
    ):
        return ()

    cloisters_source = transition_module.building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=transition_module._ROUTE_BUILDING_CLOISTERS,
    )
    if not cloisters_source.usable or (
        cloisters_source.source_type != "own_active"
        and not transition_module._is_hired_source(cloisters_source)
    ):
        return ()

    return tuple(
        transition_module._SowRouteOption(
            route=variant.route,
            building_id=transition_module._ROUTE_BUILDING_KOGGE,
            source=kogge_hire,
            secondary_building_id=transition_module._ROUTE_BUILDING_CLOISTERS,
            secondary_source=cloisters_hire,
            omitted_location=variant.omitted_location,
        )
        for kogge_hire in transition_module._hire_payment_source_variants(
            kogge_source, state.player_state(state.active_player)
        )
        for cloisters_hire in transition_module._hire_payment_source_variants(
            cloisters_source, state.player_state(state.active_player)
        )
        for variant in combined_kogge_cloisters_route_variants(
            origin=origin,
            picked_up=picked_up,
            board=config.board,
        )
    )


@contextmanager
def _legacy_combined_mode():
    original = transition_module._legal_combined_kogge_cloisters_route_options
    transition_module._legal_combined_kogge_cloisters_route_options = (
        _legacy_combined_kogge_cloisters_route_options_without_kogge_requirement
    )
    try:
        yield
    finally:
        transition_module._legal_combined_kogge_cloisters_route_options = original


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


def test_kogge_and_cloisters_construct_skip_clerical_allocation_tithe_has_one_action() -> None:
    scenario = load_scenario("scenarios/playtest/kogge_and_cloisters_2p.json")
    board = scenario.config.board
    construct = board.index_for_name("south_east")
    build_roads = board.index_for_name("south")
    clerical = board.index_for_name("south_west")
    allocation = board.index_for_name("west")
    matching = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.origin == construct
        and tuple(action.route) == (build_roads, allocation)
        and action.sow_route_omitted_location == clerical
        and action.selected_duty == allocation
        and action.resolution is TurnResolutionType.TITHE
    ]

    assert len(matching) == 1
    action = matching[0]
    assert action.sow_route_building_id == "cloisters"
    assert action.sow_route_secondary_building_id is None
    assert action.sow_route_building_source == "own_active"


def test_combined_kogge_cloisters_actions_require_kogge_candidate_walk_across_corpus_and_playtests() -> None:
    checked = 0
    offenders: list[tuple[str, tuple[int, ...], tuple[int, ...], int]] = []
    scenario_paths = sorted(SCENARIOS.glob("*.json")) + sorted((SCENARIOS / "playtest").glob("*.json"))
    for scenario_path in scenario_paths:
        scenario = load_scenario(str(scenario_path))
        board = scenario.config.board
        for action in legal_actions(scenario.state, scenario.config):
            if not isinstance(action, FullTurnAction):
                continue
            if not (
                action.sow_route_building_id == "kogge"
                and action.sow_route_secondary_building_id == "cloisters"
            ):
                continue
            checked += 1
            candidate_walk = _combined_candidate_walk_for_action(action, board)
            if not route_requires_kogge(
                origin=action.origin,
                route=candidate_walk,
                board=board,
            ):
                offenders.append(
                    (
                        scenario_path.name,
                        tuple(action.route),
                        candidate_walk,
                        action.sow_route_omitted_location,
                    )
                )

    assert checked > 0
    assert not offenders, f"combined Kogge+Cloisters actions with non-Kogge walks: {offenders[:10]}"


def test_only_known_scenarios_move_with_expected_action_deltas() -> None:
    scenario_paths = sorted(SCENARIOS.glob("*.json")) + sorted((SCENARIOS / "playtest").glob("*.json"))

    current_counts: dict[str, int] = {}
    for scenario_path in scenario_paths:
        scenario = load_scenario(str(scenario_path))
        current_counts[scenario_path.name] = len(list(legal_actions(scenario.state, scenario.config)))

    with _legacy_combined_mode():
        legacy_counts: dict[str, int] = {}
        for scenario_path in scenario_paths:
            scenario = load_scenario(str(scenario_path))
            legacy_counts[scenario_path.name] = len(list(legal_actions(scenario.state, scenario.config)))

    moved = {
        name: legacy_counts[name] - current_counts[name]
        for name in current_counts
        if legacy_counts[name] != current_counts[name]
    }
    assert moved == EXPECTED_MOVED_ACTION_DELTAS
    assert sum(legacy_counts.values()) == 93510
    assert sum(current_counts.values()) == 93148


def test_kogge_and_cloisters_playtest_keeps_spoke_using_kogge_route_counts() -> None:
    scenario = load_scenario("scenarios/playtest/kogge_and_cloisters_2p.json")
    board = scenario.config.board
    actions = list(legal_actions(scenario.state, scenario.config))
    kogge_only = [
        action
        for action in actions
        if action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id is None
    ]
    combined = [
        action
        for action in actions
        if action.sow_route_building_id == "kogge"
        and action.sow_route_secondary_building_id == "cloisters"
    ]

    assert len(kogge_only) == 80
    assert len(combined) == 769
    assert all(
        route_requires_kogge(
            origin=action.origin,
            route=_combined_candidate_walk_for_action(action, board),
            board=board,
        )
        for action in combined
    )


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
