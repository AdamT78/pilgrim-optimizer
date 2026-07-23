from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def test_build_roads_legal_actions_include_scaffold_and_tithe_only() -> None:
    scenario = load_scenario("scenarios/build_roads_deferred_001.json")

    actions = legal_actions(scenario.state, scenario.config)

    assert [action.resolution for action in actions] == [
        TurnResolutionType.BUILD_ROADS_DEFERRED,
        TurnResolutionType.TITHE,
    ]
    assert scenario.config.duty_category_for_position(actions[0].selected_duty) == "build_roads"


def test_apply_build_roads_scaffold_emits_deferred_event_and_recalls() -> None:
    scenario = load_scenario("scenarios/build_roads_deferred_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    event_types = [event.event_type for event in result.events]
    assert EventType.DUTY_RESOLUTION in event_types
    assert EventType.DUTY_DEFERRED in event_types
    assert EventType.ACOLYTE_RECALL in event_types

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["duty_category"] == "build_roads"
    assert duty_details["effect"] == "build_roads_deferred"

    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )
    deferred_details = dict(deferred_event.details)
    assert "build road/bridge/ford/shrine" in str(deferred_details["scaffold"])

    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 1
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[3] == 0
    assert after_player.resources == before_player.resources
    assert after_player.workforce.committed == before_player.workforce.committed
    assert result.state.building_market == scenario.state.building_market


def test_build_roads_road_engineer_adds_effective_duty_value_bonus() -> None:
    scenario = load_scenario("scenarios/build_roads_road_engineer_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]

    result = apply_action(scenario.state, action, scenario.config)

    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["duty_value"] == 2
    assert duty_details["effective_duty_value"] == 3
    assert duty_details["effect"] == "build_roads_deferred"

    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "road_engineer"
    )
    bonus_details = dict(bonus_event.details)
    assert bonus_details["action"] == "build_roads_deferred"
    assert bonus_details["duty_value_bonus"] == 1

    deferred_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_DEFERRED
    )
    deferred_details = dict(deferred_event.details)
    assert deferred_details["effective_duty_value"] == 3


def test_build_roads_minority_applies_silver_cost_and_still_defers() -> None:
    scenario = load_scenario("scenarios/build_roads_minority_cost_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]

    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

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
    assert resource_details["stone"] == 0
    assert resource_details["silver"] == -1
    assert resource_details["wheat"] == 0
    assert after_player.resources.silver == 0
    assert any(event.event_type is EventType.DUTY_DEFERRED for event in result.events)


def test_road_engineer_does_not_boost_unrelated_duties() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_engineer = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=player_one.special_activities.with_activity("road_engineer", True),
        ),
    )
    produce_action = next(
        action
        for action in legal_actions(state_with_engineer, scenario.config)
        if action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )

    result = apply_action(state_with_engineer, produce_action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)
    assert duty_details["duty_value"] == duty_details["effective_duty_value"]
    assert not any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "road_engineer"
        for event in result.events
    )
