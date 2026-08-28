from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_id
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _cloisters_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    return scenario, [action for action in actions if action.sow_route_building_id == "cloisters"]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_cloisters_generates_skip_duty_and_skip_city_variants() -> None:
    duty_scenario, duty_actions = _cloisters_actions(
        "scenarios/cloisters_active_skip_duty_tile_001.json"
    )
    north_east = duty_scenario.config.board.index_for_name("north_east")

    assert duty_actions
    assert all(action.sow_route_building_source == "own_active" for action in duty_actions)
    assert any(action.sow_route_omitted_location == north_east for action in duty_actions)

    city_scenario, city_actions = _cloisters_actions(
        "scenarios/cloisters_active_skip_city_001.json"
    )
    city = city_scenario.config.board.index_for_name("city")
    assert city_actions
    assert any(action.sow_route_omitted_location == city for action in city_actions)


def test_cloisters_market_hire_generates_only_skip_route_variants() -> None:
    _scenario, actions = _cloisters_actions(
        "scenarios/cloisters_hire_market_skip_duty_tile_001.json"
    )

    assert actions
    assert all(action.sow_route_building_source == "market" for action in actions)
    assert all(action.hire_payments == (("cloisters", "wheat"),) for action in actions)


def test_cloisters_opponent_hire_pays_owner_and_skips_city_before_sowing() -> None:
    scenario = load_scenario("scenarios/cloisters_hire_opponent_skip_city_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "cloisters"
    ]
    city = scenario.config.board.index_for_name("city")
    east = scenario.config.board.index_for_name("east")
    north = scenario.config.board.index_for_name("north")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_building_source == "player_two"
            and candidate.sow_route_omitted_location == city
            and candidate.origin == east
            and candidate.selected_duty == north
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "cloisters",
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)
    sowing_details = dict(sowing_event.details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert sowing_details["skipped"] == city
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sowing_event)
    # The hire spends the last wheat and the tithe on north puts one straight back: north carries a
    # wheat counter, and the tithe these building tests ride on now pays what it stands on.
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_cloisters_hire_market_pays_bank() -> None:
    scenario = load_scenario("scenarios/cloisters_hire_market_skip_duty_tile_001.json")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "cloisters"
    ]
    north_east = scenario.config.board.index_for_name("north_east")
    east = scenario.config.board.index_for_name("east")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_building_source == "market"
            and candidate.sow_route_omitted_location == north_east
            and candidate.selected_duty == east
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1


def test_cloisters_hire_blocked_for_merchant_none_insufficient_donated_and_not_live() -> None:
    for path in (
        "scenarios/cloisters_merchant_none_no_hire_001.json",
        "scenarios/cloisters_insufficient_resource_no_hire_001.json",
        "scenarios/cloisters_donated_no_modifier_001.json",
        "scenarios/cloisters_not_live_no_modifier_001.json",
    ):
        scenario = load_scenario(path)
        assert not _cloisters_actions(path)[1]


def test_cloisters_apply_omitted_duty_receives_no_acolyte_and_counts_match_pickup() -> None:
    scenario, actions = _cloisters_actions("scenarios/cloisters_active_skip_duty_tile_001.json")
    north_east = scenario.config.board.index_for_name("north_east")
    east = scenario.config.board.index_for_name("east")
    south_east = scenario.config.board.index_for_name("south_east")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_omitted_location == north_east
            and candidate.selected_duty == south_east
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    sowing_details = dict(_events_of_type(result.events, EventType.SOWING)[0].details)
    player_vector = result.state.player_vector(PlayerId.PLAYER_ONE)

    assert sowing_details["picked_up"] == 2
    assert sowing_details["skipped"] == north_east
    assert len(str(sowing_details["route"]).split("->")) == 2
    assert player_vector[north_east] == 0
    assert player_vector[east] == 1
    assert player_vector[south_east] == 1


def test_apply_rejects_cloisters_selected_duty_that_was_omitted() -> None:
    scenario, actions = _cloisters_actions("scenarios/cloisters_active_skip_duty_tile_001.json")
    north_east = scenario.config.board.index_for_name("north_east")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_omitted_location == north_east
            and candidate.selected_duty != north_east
        ),
    )
    invalid_action = replace(action, selected_duty=north_east)

    with pytest.raises(TransitionValidationError, match="Selected duty must contain"):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_accepts_cloisters_omitting_a_revisited_origin() -> None:
    scenario, actions = _cloisters_actions("scenarios/playtest/cloisters_loop_2p.json")
    city = scenario.config.board.index_for_name("city")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.origin == city
            and candidate.sow_route_omitted_location == city
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    sowing_details = dict(_events_of_type(result.events, EventType.SOWING)[0].details)
    assert sowing_details["skipped"] == city


def test_cloisters_event_order_and_bonus_for_own_active() -> None:
    scenario, actions = _cloisters_actions("scenarios/cloisters_active_skip_duty_tile_001.json")
    north_east = scenario.config.board.index_for_name("north_east")
    east = scenario.config.board.index_for_name("east")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.sow_route_omitted_location == north_east
            and candidate.selected_duty == east
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "cloisters",
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert result.events.index(bonus_event) < result.events.index(sowing_event)


def test_cloisters_events_not_emitted_when_modifier_not_used() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _first_action(actions, lambda candidate: candidate.sow_route_building_id is None)
    result = apply_action(scenario.state, action, scenario.config)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert not any(
        dict(event.details).get("building") == "cloisters"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )


def test_normal_non_cloisters_actions_remain_legal_and_cloisters_actions_dedupe() -> None:
    scenario = load_scenario("scenarios/cloisters_active_skip_duty_tile_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    cloisters_actions = [
        action for action in actions if action.sow_route_building_id == "cloisters"
    ]

    assert any(action.sow_route_building_id is None for action in actions)
    assert cloisters_actions
    assert len(cloisters_actions) == len({action_id(action) for action in cloisters_actions})


def test_cloisters_can_combine_with_start_turn_prefix_when_both_are_active() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    combined_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(
                    *player_state.player_board_slots.active_buildings,
                    "cloisters",
                ),
            ),
        ),
    )

    dormitory_step = next(
        step
        for step in turn_steps(combined_state, scenario.config)
        if step.building_id == "dormitory"
    )
    actions = legal_actions(
        apply_turn_step(combined_state, scenario.config, dormitory_step), scenario.config
    )
    assert any(action.sow_route_building_id == "cloisters" for action in actions)
