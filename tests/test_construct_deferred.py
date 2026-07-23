from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _construct_plans_for_scenario(path: str) -> tuple[str, ...]:
    scenario = load_scenario(path)
    return tuple(
        action.construct_plan or ""
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.CONSTRUCT_DEFERRED
    )


def test_construct_legal_actions_duty_value_one_include_building_and_road() -> None:
    scenario = load_scenario("scenarios/construct_deferred_building_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    construct_plans = {
        action.construct_plan
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_DEFERRED
    }

    assert construct_plans == {"building", "road"}
    assert any(action.resolution is TurnResolutionType.TITHE for action in actions)
    assert "building + building" not in construct_plans
    assert "road + road" not in construct_plans


def test_construct_legal_actions_duty_value_two_include_building_plus_road() -> None:
    scenario = load_scenario("scenarios/construct_deferred_building_and_road_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    construct_actions = [
        action
        for action in actions
        if action.resolution is TurnResolutionType.CONSTRUCT_DEFERRED
    ]
    construct_plans = {action.construct_plan for action in construct_actions}

    assert construct_plans == {"building + road", "building", "road"}
    assert construct_actions[0].construct_plan == "building + road"
    assert "building + building" not in construct_plans
    assert "road + road" not in construct_plans


def test_construct_road_engineer_extra_road_requires_road_in_plan() -> None:
    construct_plans = set(_construct_plans_for_scenario("scenarios/construct_road_engineer_extra_road_001.json"))

    assert "road + road_engineer_extra_road" in construct_plans
    assert "building + road_engineer_extra_road" not in construct_plans
    assert "building + building" not in construct_plans
    assert "road + road" not in construct_plans
    assert any("road_engineer_extra_road" not in plan for plan in construct_plans)


def test_construct_road_engineer_duty_value_two_includes_extra_road_variants() -> None:
    scenario = load_scenario("scenarios/construct_deferred_building_and_road_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_road_engineer = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=player_one.special_activities.with_activity("road_engineer", True),
        ),
    )
    construct_plans = {
        action.construct_plan
        for action in legal_actions(state_with_road_engineer, scenario.config)
        if action.resolution is TurnResolutionType.CONSTRUCT_DEFERRED
    }

    assert "road + road_engineer_extra_road" in construct_plans
    assert "building + road + road_engineer_extra_road" in construct_plans
    assert "building + road_engineer_extra_road" not in construct_plans


def test_apply_construct_building_scaffold_emits_deferred_and_preserves_building_state() -> None:
    scenario = load_scenario("scenarios/construct_deferred_building_001.json")
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    before_slots = before_player.player_board_slots
    action = legal_actions(scenario.state, scenario.config)[0]

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    event_types = {event.event_type for event in result.events}
    assert EventType.DUTY_RESOLUTION in event_types
    assert EventType.DUTY_DEFERRED in event_types
    assert EventType.ACOLYTE_RECALL in event_types
    assert EventType.SPECIAL_ACTIVITY_BONUS not in event_types

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["duty_category"] == "construct"
    assert duty_details["effect"] == "construct_deferred"
    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 1

    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )
    assert "requested plan: building" in str(dict(deferred_event.details).get("scaffold"))

    assert after_player.resources == before_player.resources
    assert after_player.player_board_slots == before_slots
    assert result.state.building_market == scenario.state.building_market
    assert after_player.workforce.committed == before_player.workforce.committed


def test_apply_construct_building_and_road_scaffold_preserves_slot_state() -> None:
    scenario = load_scenario("scenarios/construct_deferred_building_and_road_001.json")
    before_slots = scenario.state.player_state(PlayerId.PLAYER_ONE).player_board_slots
    action = legal_actions(scenario.state, scenario.config)[0]

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )
    assert "requested plan: building + road" in str(dict(deferred_event.details).get("scaffold"))
    assert after_player.player_board_slots == before_slots
    assert after_player.workforce.committed == scenario.state.player_state(
        PlayerId.PLAYER_ONE
    ).workforce.committed


def test_apply_construct_road_engineer_extra_road_emits_bonus_without_duty_value_raise() -> None:
    scenario = load_scenario("scenarios/construct_road_engineer_extra_road_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]

    result = apply_action(scenario.state, action, scenario.config)

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["duty_value"] == duty_details["effective_duty_value"]

    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "road_engineer"
    )
    bonus_details = dict(bonus_event.details)
    assert bonus_details["action"] == "construct_deferred"
    assert bonus_details["construct_extra_road"] is True

    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )
    assert "road + road_engineer_extra_road" in str(dict(deferred_event.details)["scaffold"])


def test_apply_construct_minority_cost_applies_silver_delta() -> None:
    scenario = load_scenario("scenarios/construct_minority_cost_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]

    result = apply_action(scenario.state, action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["strength"] == "minority"
    assert duty_details["silver_cost"] == 1

    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )
    resource_details = dict(resource_event.details)
    assert resource_details["silver"] == -1
    assert any(event.event_type is EventType.DUTY_DEFERRED for event in result.events)
