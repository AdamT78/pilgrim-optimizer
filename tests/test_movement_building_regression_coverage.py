from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import EndTurnAction, action_id
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def _event_index(events, event_type: EventType, predicate=None) -> int:
    if predicate is None:
        predicate = lambda _event: True
    for index, event in enumerate(events):
        if event.event_type is event_type and predicate(event):
            return index
    raise AssertionError(f"Missing event type {event_type.value}.")


def _assert_event_type_before(events, first: EventType, second: EventType) -> None:
    assert _event_index(events, first) < _event_index(events, second)


@pytest.mark.parametrize(
    "scenario_path",
    (
        "scenarios/kogge_active_city_to_east_001.json",
        "scenarios/cloisters_active_skip_duty_tile_001.json",
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
    ),
)
def test_action_ids_are_unique_within_representative_movement_scenarios(
    scenario_path: str,
) -> None:
    scenario = load_scenario(scenario_path)
    actions = legal_actions(scenario.state, scenario.config)
    ids = [action_id(action) for action in actions]

    assert len(ids) == len(set(ids))


def test_kogge_normal_and_modified_routes_have_distinct_action_ids() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    actions = legal_actions(scenario.state, scenario.config)
    normal_action = _first_action(
        actions,
        lambda candidate: (
            candidate.origin == city
            and candidate.route
            and board.positions[candidate.route[0]] in {"north", "south"}
            and candidate.sow_route_building_id is None
        ),
    )
    modified_action = _first_action(
        actions,
        lambda candidate: (
            candidate.origin == city
            and candidate.route
            and board.positions[candidate.route[0]] in {"east", "west"}
            and candidate.sow_route_building_id == "kogge"
        ),
    )

    assert action_id(normal_action) != action_id(modified_action)


def test_cloisters_different_omissions_produce_distinct_action_ids() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "cloisters"
    ]
    first_action = actions[0]
    second_action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_omitted_location != first_action.sow_route_omitted_location
        ),
    )
    assert first_action.sow_route_omitted_location is not None
    assert second_action.sow_route_omitted_location is not None

    first_id = action_id(first_action)
    second_id = action_id(second_action)

    assert first_id != second_id
    assert f":skip:{first_action.sow_route_omitted_location}" in first_id
    assert f":skip:{second_action.sow_route_omitted_location}" in second_id


def test_combined_kogge_cloisters_action_id_has_no_hire_source() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")
    after_kogge = apply_turn_step(
        scenario.state,
        scenario.config,
        _first_action(turn_steps(scenario.state, scenario.config), lambda step: step.building_id == "kogge"),
    )
    after_both = apply_turn_step(
        after_kogge,
        scenario.config,
        _first_action(turn_steps(after_kogge, scenario.config), lambda step: step.building_id == "cloisters"),
    )
    combined_action = _first_action(
        legal_actions(after_both, scenario.config),
        lambda candidate: (
            candidate.sow_route_building_id == "kogge"
            and candidate.sow_route_building_source is None
            and candidate.sow_route_secondary_building_id == "cloisters"
            and candidate.sow_route_secondary_building_source is None
        ),
    )
    combined_id = action_id(combined_action)

    assert ":sow_route_building:kogge" in combined_id
    assert ":secondary_building:cloisters" in combined_id
    assert ":from:market" not in combined_id
    assert ":secondary_from:market" not in combined_id
    assert combined_action.sow_route_omitted_location is not None
    assert f":skip:{combined_action.sow_route_omitted_location}" in combined_id
    assert action_id(combined_action) == combined_id


def test_apply_rejects_forced_kogge_fields_from_non_city_origin() -> None:
    scenario = load_scenario("scenarios/kogge_active_city_to_east_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
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
    base_action = _first_action(
        legal_actions(shifted_state, scenario.config),
        lambda candidate: candidate.origin != city and candidate.sow_route_building_id is None,
    )
    invalid_action = replace(
        base_action,
        sow_route_building_id="kogge",
        sow_route_building_source="own_active",
    )

    with pytest.raises(
        TransitionValidationError,
        match="only legal when route uses Kogge-reversed City spokes",
    ):
        apply_action(shifted_state, invalid_action, scenario.config)


def test_apply_rejects_cloisters_omission_not_in_candidate_placements() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    cloisters_action = _first_action(
        legal_actions(scenario.state, scenario.config),
        lambda candidate: candidate.sow_route_building_id == "cloisters",
    )
    invalid_action = replace(cloisters_action, sow_route_omitted_location=999)

    with pytest.raises(TransitionValidationError, match="legal candidate route"):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_rejects_forced_combined_fields_from_non_city_origin() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_duty_001.json")
    board = scenario.config.board
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
    base_action = _first_action(
        legal_actions(shifted_state, scenario.config),
        lambda candidate: candidate.origin != board.index_for_name("city"),
    )
    invalid_action = replace(
        base_action,
        sow_route_building_id="kogge",
        sow_route_building_source="own_active",
        sow_route_secondary_building_id="cloisters",
        sow_route_secondary_building_source="own_active",
        sow_route_omitted_location=base_action.route[0],
    )

    with pytest.raises(TransitionValidationError, match="legal Kogge candidate route"):
        apply_action(shifted_state, invalid_action, scenario.config)


def test_apply_rejects_forced_combined_fields_on_non_kogge_city_route() -> None:
    scenario = load_scenario("scenarios/kogge_cloisters_own_own_skip_duty_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    base_action = _first_action(
        legal_actions(scenario.state, scenario.config),
        lambda candidate: (
            candidate.origin == city
            and candidate.route
            and board.positions[candidate.route[0]] in {"north", "south"}
            and candidate.sow_route_building_id is None
        ),
    )
    invalid_action = replace(
        base_action,
        sow_route_building_id="kogge",
        sow_route_building_source="own_active",
        sow_route_secondary_building_id="cloisters",
        sow_route_secondary_building_source="own_active",
        sow_route_omitted_location=base_action.route[0],
    )

    with pytest.raises(TransitionValidationError, match="legal Kogge candidate route"):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_hired_cloisters_step_is_absent_when_hire_source_is_unavailable() -> None:
    merchant_none_scenario = load_scenario("scenarios/cloisters_merchant_none_no_hire_001.json")
    assert not [
        step
        for step in turn_steps(merchant_none_scenario.state, merchant_none_scenario.config)
        if step.building_id == "cloisters"
    ]

    insufficient_scenario = load_scenario(
        "scenarios/cloisters_insufficient_resource_no_hire_001.json"
    )
    assert not [
        step
        for step in turn_steps(insufficient_scenario.state, insufficient_scenario.config)
        if step.building_id == "cloisters"
    ]


def test_own_active_source_suppresses_hired_cloisters_variants() -> None:
    scenario = load_scenario("scenarios/cloisters_hire_market_skip_duty_tile_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    own_active_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=("cloisters",),
            ),
        ),
    )
    cloisters_actions = [
        action
        for action in legal_actions(own_active_state, scenario.config)
        if action.sow_route_building_id == "cloisters"
    ]

    assert cloisters_actions
    assert all(action.sow_route_building_source == "own_active" for action in cloisters_actions)


def test_dormitory_plus_kogge_uses_post_relocation_city_pickup() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    east = board.index_for_name("east")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    composed_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(
                    *player_state.player_board_slots.active_buildings,
                    "kogge",
                ),
            ),
        ),
    )
    step = _first_action(
        turn_steps(composed_state, scenario.config),
        lambda candidate: (
            candidate.building_id == "dormitory" and candidate.selected_position == east
        ),
    )
    after_step = apply_turn_step(composed_state, scenario.config, step)
    action = _first_action(
        legal_actions(after_step, scenario.config),
        lambda candidate: candidate.origin == city and candidate.sow_route_building_id == "kogge",
    )
    result = apply_action(after_step, action, scenario.config)
    sowing_details = dict(_events_of_type(result.events, EventType.SOWING)[0].details)

    _assert_event_type_before(result.events, EventType.START_TURN_RELOCATION, EventType.SOWING)
    assert sowing_details["picked_up"] == 2


def test_inquisition_plus_kogge_uses_post_relocation_city_pickup() -> None:
    scenario = load_scenario("scenarios/inquisition_active_city_to_duty_001.json")
    board = scenario.config.board
    city = board.index_for_name("city")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    composed_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(
                    *player_state.player_board_slots.active_buildings,
                    "kogge",
                ),
            ),
        ),
    )
    step = _first_action(
        turn_steps(composed_state, scenario.config),
        lambda candidate: candidate.building_id == "inquisition",
    )
    after_step = apply_turn_step(composed_state, scenario.config, step)
    action = _first_action(
        legal_actions(after_step, scenario.config),
        lambda candidate: candidate.origin == city and candidate.sow_route_building_id == "kogge",
    )
    result = apply_action(after_step, action, scenario.config)
    sowing_details = dict(_events_of_type(result.events, EventType.SOWING)[0].details)

    _assert_event_type_before(result.events, EventType.START_TURN_RELOCATION, EventType.SOWING)
    assert sowing_details["picked_up"] == 1


def test_kogge_plus_library_preserves_route_and_end_turn_event_boundaries() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    composed_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(
                    *player_state.player_board_slots.active_buildings,
                    "kogge",
                ),
            ),
        ),
    )
    action = _first_action(
        legal_actions(composed_state, scenario.config),
        lambda candidate: candidate.sow_route_building_id == "kogge",
    )
    resolution = apply_action(composed_state, action, scenario.config)
    assert resolution.state.turn_progress.resolution_committed
    library_step = _first_action(
        turn_steps(resolution.state, scenario.config),
        lambda candidate: candidate.building_id == "library" and candidate.selected_position == "abbey",
    )
    after_step = apply_turn_step(resolution.state, scenario.config, library_step)
    passed = apply_action(after_step, EndTurnAction(), scenario.config)
    events = (*resolution.events, *after_step.turn_progress.events, *passed.events)

    kogge_bonus_index = _event_index(
        events,
        EventType.BUILDING_BONUS,
        lambda event: dict(event.details).get("building") == "kogge",
    )
    sowing_index = _event_index(events, EventType.SOWING)
    duty_index = _event_index(events, EventType.DUTY_RESOLUTION)
    recall_index = _event_index(events, EventType.ACOLYTE_RECALL)
    library_bonus_index = _event_index(
        events,
        EventType.BUILDING_BONUS,
        lambda event: dict(event.details).get("building") == "library",
    )
    end_turn_index = _event_index(events, EventType.END_TURN_RELOCATION)
    turn_advance_index = _event_index(events, EventType.TURN_ADVANCE)

    assert (
        kogge_bonus_index
        < sowing_index
        < duty_index
        < recall_index
        < library_bonus_index
        < end_turn_index
        < turn_advance_index
    )
    assert passed.state.player_state(PlayerId.PLAYER_ONE).workforce.abbey == 4
