from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId
from pilgrim.rules.mancala import generate_routes
from pilgrim.rules.sow_routes import (
    SowRouteVariant,
    cloisters_actual_placements_after_omission,
    cloisters_candidate_omissions,
    cloisters_candidate_placements,
    cloisters_route_variants,
    dedupe_sow_route_variants,
    is_legal_route_with_cloisters_skip,
    is_legal_route_with_optional_city_kogge,
    kogge_city_start_routes,
    normal_sow_routes,
    route_requires_kogge,
    selected_duty_is_actual_placement,
    sow_vector_from_route,
)


def test_normal_city_routes_remain_north_and_south() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    routes = normal_sow_routes(origin=city, picked_up=1, board=board)

    assert {board.positions[route[0]] for route in routes} == {"north", "south"}


def test_normal_non_city_route_generation_matches_current_graph_behavior() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    routes = normal_sow_routes(origin=north, picked_up=2, board=board)

    assert routes == tuple(generate_routes(north, 2, board))


def test_normal_route_placement_count_matches_picked_up_acolytes() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    vector = scenario.state.player_vector(PlayerId.PLAYER_ONE)
    routes = normal_sow_routes(origin=north, picked_up=2, board=board)

    assert routes
    for route in routes:
        updated = sow_vector_from_route(vector, origin=north, route=route)
        assert updated[north] == 0
        assert sum(updated) == sum(vector)


def test_kogge_helpers_add_city_east_and_west_without_duplicates() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    north = board.index_for_name("north")
    kogge_routes = kogge_city_start_routes(origin=city, picked_up=1, board=board)
    normal_routes = normal_sow_routes(origin=city, picked_up=1, board=board)

    assert {board.positions[route[0]] for route in kogge_routes} == {"east", "west"}
    assert kogge_city_start_routes(origin=north, picked_up=1, board=board) == ()
    assert set(kogge_routes).isdisjoint(set(normal_routes))


def test_kogge_route_validation_helper_preserves_behavior() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    east = board.index_for_name("east")

    assert is_legal_route_with_optional_city_kogge(
        city,
        (east,),
        board=board,
        allows_kogge_city_step=True,
    )
    assert not is_legal_route_with_optional_city_kogge(
        city,
        (east,),
        board=board,
        allows_kogge_city_step=False,
    )
    assert route_requires_kogge(origin=city, route=(east,), board=board)


def test_cloisters_candidate_n_plus_one_and_actual_n_after_omission() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    candidates = cloisters_candidate_placements(origin=north, picked_up=2, board=board)

    assert candidates
    assert all(len(candidate) == 3 for candidate in candidates)

    candidate = candidates[0]
    omitted_index, _omitted_location = cloisters_candidate_omissions(
        origin=north,
        candidate_placements=candidate,
    )[0]
    actual = cloisters_actual_placements_after_omission(
        candidate,
        omitted_index=omitted_index,
    )
    assert len(actual) == 2


def test_cloisters_omitted_duty_and_city_receive_no_acolyte() -> None:
    duty_scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    duty_board = duty_scenario.config.board
    north = duty_board.index_for_name("north")
    north_east = duty_board.index_for_name("north_east")
    east = duty_board.index_for_name("east")
    south_east = duty_board.index_for_name("south_east")
    duty_vector = duty_scenario.state.player_vector(PlayerId.PLAYER_ONE)
    duty_variant = next(
        variant
        for variant in cloisters_route_variants(
            origin=north,
            picked_up=2,
            board=duty_board,
        )
        if variant.omitted_location == north_east and variant.route == (east, south_east)
    )
    duty_updated = sow_vector_from_route(duty_vector, origin=north, route=duty_variant.route)
    assert duty_updated[north_east] == 0

    city_scenario = load_scenario("scenarios/cloisters_active_skip_city_001.json")
    city_board = city_scenario.config.board
    city = city_board.index_for_name("city")
    origin_east = city_board.index_for_name("east")
    city_vector = city_scenario.state.player_vector(PlayerId.PLAYER_ONE)
    city_variant = next(
        variant
        for variant in cloisters_route_variants(
            origin=origin_east,
            picked_up=1,
            board=city_board,
        )
        if variant.omitted_location == city
    )
    city_updated = sow_vector_from_route(city_vector, origin=origin_east, route=city_variant.route)
    assert city_updated[city] == 0


def test_cloisters_selected_duty_membership_rules_are_explicit() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    north_east = board.index_for_name("north_east")
    east = board.index_for_name("east")
    south_east = board.index_for_name("south_east")
    variant = next(
        route_variant
        for route_variant in cloisters_route_variants(
            origin=north,
            picked_up=2,
            board=board,
        )
        if route_variant.omitted_location == north_east
        and route_variant.route == (east, south_east)
    )
    assert not selected_duty_is_actual_placement(variant.route, selected_duty=north_east)

    candidates = cloisters_candidate_placements(origin=north, picked_up=4, board=board)
    city = board.index_for_name("city")
    repeated_candidate = next(
        candidate
        for candidate in candidates
        if any(
            position != city and candidate.count(position) >= 2
            for position in candidate
        )
    )
    repeated_duty = next(
        position
        for position in repeated_candidate
        if position != city and repeated_candidate.count(position) >= 2
    )
    first_repeat_index = repeated_candidate.index(repeated_duty)
    actual = cloisters_actual_placements_after_omission(
        repeated_candidate,
        omitted_index=first_repeat_index,
    )
    assert selected_duty_is_actual_placement(actual, selected_duty=repeated_duty)


def test_cloisters_origin_cannot_be_omitted_and_invalid_omission_is_rejected() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    board = scenario.config.board
    north = board.index_for_name("north")
    east = board.index_for_name("east")
    south_east = board.index_for_name("south_east")

    candidates = cloisters_candidate_placements(origin=north, picked_up=2, board=board)
    omissions = cloisters_candidate_omissions(
        origin=north,
        candidate_placements=candidates[0],
    )
    assert all(location != north for _index, location in omissions)

    assert not is_legal_route_with_cloisters_skip(
        origin=north,
        route=(east, south_east),
        board=board,
        omitted_location=north,
    )
    assert not is_legal_route_with_cloisters_skip(
        origin=north,
        route=(east, south_east),
        board=board,
        omitted_location=999,
    )


def test_dedupe_sow_route_variants_collapses_equivalent_entries() -> None:
    duplicate_a = SowRouteVariant(route=(1, 2), omitted_location=3)
    duplicate_b = SowRouteVariant(route=(1, 2), omitted_location=3)
    distinct = SowRouteVariant(route=(1, 2), omitted_location=4)

    deduped = dedupe_sow_route_variants((duplicate_a, duplicate_b, distinct))

    assert deduped == (duplicate_a, distinct)
