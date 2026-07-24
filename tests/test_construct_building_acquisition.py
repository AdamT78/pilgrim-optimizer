from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.buildings import (
    available_player_board_slots,
    produce_wheat_well_bonus,
    used_player_board_slots,
)
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import TransitionValidationError


def _action_for_construct(
    actions,
    *,
    resolution: TurnResolutionType,
    building_id: str | None = None,
    plan: str | None = None,
):
    return next(
        action
        for action in actions
        if action.resolution is resolution
        and (building_id is None or action.construct_building_id == building_id)
        and (plan is None or action.construct_plan == plan)
    )


def test_construct_legal_actions_generate_affordable_building_actions_at_duty_value_one() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    building_ids = [
        action.construct_building_id
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
    ]

    assert building_ids == ["well", "chapel", "mint", "quarry"]
    assert all(building_id is not None for building_id in building_ids)
    assert any(
        action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED
        and action.construct_plan == "road"
        for action in actions
    )
    assert not any(
        action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
        for action in actions
    )


def test_construct_legal_actions_duty_value_two_include_building_plus_road_actions() -> None:
    scenario = load_scenario("scenarios/construct_building_and_road_deferred_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    combined_pairs = {
        (action.construct_building_id, action.construct_plan)
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
    }
    combined_buildings = {
        building_id for building_id, plan in combined_pairs if plan == "road"
    }

    assert combined_buildings == {"well", "chapel", "mint", "quarry"}
    assert ("well", "road + road_engineer_extra_road") not in combined_pairs
    assert any(
        action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED
        and action.construct_plan == "road"
        for action in actions
    )


def test_construct_road_engineer_extra_road_variants_require_road_included() -> None:
    scenario = load_scenario("scenarios/construct_building_road_engineer_extra_road_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    deferred_plans = {
        action.construct_plan
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED
    }
    combined_pairs = {
        (action.construct_building_id, action.construct_plan)
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
    }

    assert deferred_plans == {"road", "road + road_engineer_extra_road"}
    assert ("well", "road + road_engineer_extra_road") in combined_pairs
    assert ("well", "road") in combined_pairs
    assert not any(
        action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
        and action.construct_plan is not None
        for action in actions
    )


def test_construct_no_slot_prevents_building_actions_but_keeps_road_scaffold() -> None:
    scenario = load_scenario("scenarios/construct_building_no_slot_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    resolutions = {action.resolution for action in actions}

    assert TurnResolutionType.CONSTRUCT_BUILDING not in resolutions
    assert TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED not in resolutions
    assert any(action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED for action in actions)


def test_construct_insufficient_stone_filters_unaffordable_buildings() -> None:
    scenario = load_scenario("scenarios/construct_building_insufficient_stone_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    building_ids = {
        action.construct_building_id
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING
    }
    combined_ids = {
        action.construct_building_id
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
    }

    assert "brewery" not in building_ids
    assert "cloisters" not in building_ids
    assert "bank" not in building_ids
    assert building_ids == {"well", "chapel", "mint", "quarry"}
    assert combined_ids == {"well", "chapel", "mint", "quarry"}


def test_apply_construct_building_level1_updates_market_slots_and_events() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    before_market = scenario.state.building_market
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after_player.resources.stone == before_player.resources.stone - 1
    assert "well" not in result.state.building_market
    assert len(result.state.building_market) == len(before_market) - 1
    assert "well" in after_player.player_board_slots.active_buildings
    assert used_player_board_slots(after_player) == used_player_board_slots(before_player) + 1
    assert available_player_board_slots(after_player, scenario.config) == (
        available_player_board_slots(before_player, scenario.config) - 1
    )

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["effect"] == "construct_building"

    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )
    resource_details = dict(resource_event.details)
    assert resource_details["stone"] == -1
    assert resource_details["silver"] == 0

    constructed_event = next(
        event for event in result.events if event.event_type is EventType.BUILDING_CONSTRUCTED
    )
    constructed_details = dict(constructed_event.details)
    assert constructed_details["building_id"] == "well"
    assert constructed_details["level"] == 1
    assert constructed_details["stone_cost"] == 1
    assert not any(event.event_type is EventType.BUILDING_BONUS for event in result.events)


def test_apply_construct_building_level2_pays_two_stone() -> None:
    scenario = load_scenario("scenarios/construct_building_level2_001.json")
    before_stone = scenario.state.player_state(PlayerId.PLAYER_ONE).resources.stone
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="brewery",
    )

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    constructed_event = next(
        event for event in result.events if event.event_type is EventType.BUILDING_CONSTRUCTED
    )
    constructed_details = dict(constructed_event.details)

    assert after_player.resources.stone == before_stone - 2
    assert constructed_details["building_id"] == "brewery"
    assert constructed_details["level"] == 2
    assert constructed_details["stone_cost"] == 2


def test_apply_construct_building_level3_pays_three_stone() -> None:
    scenario = load_scenario("scenarios/construct_building_level2_001.json")
    level3_first_market = (
        "bank",
        "well",
        "chapel",
        "mint",
        "quarry",
        "brewery",
        "cloisters",
        "dormitory",
        "grain_store",
        "customs_house",
        "inquisition",
        "kogge",
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_level3 = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, resources=replace(player_one.resources, stone=3)),
    ).with_building_market(level3_first_market)
    actions = legal_actions(state_with_level3, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="bank",
    )

    result = apply_action(state_with_level3, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    constructed_event = next(
        event for event in result.events if event.event_type is EventType.BUILDING_CONSTRUCTED
    )
    constructed_details = dict(constructed_event.details)

    assert after_player.resources.stone == 0
    assert constructed_details["building_id"] == "bank"
    assert constructed_details["level"] == 3
    assert constructed_details["stone_cost"] == 3


def test_apply_construct_building_and_road_deferred_constructs_building_and_keeps_road_deferred() -> None:
    scenario = load_scenario("scenarios/construct_building_and_road_deferred_001.json")
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
        building_id="well",
        plan="road",
    )

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    event_types = {event.event_type for event in result.events}

    assert EventType.BUILDING_CONSTRUCTED in event_types
    assert EventType.DUTY_DEFERRED in event_types
    assert EventType.BUILDING_BONUS not in event_types
    assert "well" in after_player.player_board_slots.active_buildings
    assert after_player.resources.stone == before_player.resources.stone - 1
    assert after_player.workforce.committed == before_player.workforce.committed

    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )
    assert "requested plan: road" in str(dict(deferred_event.details).get("scaffold"))


def test_apply_construct_building_and_road_with_road_engineer_emits_extra_road_bonus() -> None:
    scenario = load_scenario("scenarios/construct_building_road_engineer_extra_road_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
        building_id="well",
        plan="road + road_engineer_extra_road",
    )

    result = apply_action(scenario.state, action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "road_engineer"
    )
    bonus_details = dict(bonus_event.details)
    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )

    assert duty_details["duty_value"] == duty_details["effective_duty_value"]
    assert bonus_details["construct_extra_road"] is True
    assert "road + road_engineer_extra_road" in str(dict(deferred_event.details)["scaffold"])


def test_apply_construct_building_minority_cost_stacks_silver_and_stone() -> None:
    scenario = load_scenario("scenarios/construct_building_minority_cost_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )
    resource_details = dict(resource_event.details)

    assert duty_details["strength"] == "minority"
    assert duty_details["silver_cost"] == 1
    assert resource_details["stone"] == -1
    assert resource_details["silver"] == -1
    assert after_player.resources.stone == 0
    assert after_player.resources.silver == 0


def test_constructed_well_is_immediately_active_for_produce_bonus_hook() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert "well" in after_player.player_board_slots.active_buildings
    assert produce_wheat_well_bonus(after_player) == 1


def test_apply_construct_building_rejects_non_market_building() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )
    invalid_action = replace(action, construct_building_id="not_in_market")

    with pytest.raises(TransitionValidationError, match="building_market"):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_apply_construct_building_and_road_requires_duty_value_two() -> None:
    scenario = load_scenario("scenarios/construct_building_level1_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _action_for_construct(
        actions,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )
    invalid_action = replace(
        action,
        resolution=TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
        construct_plan="road",
    )

    with pytest.raises(TransitionValidationError, match="duty value >= 2"):
        apply_action(scenario.state, invalid_action, scenario.config)
