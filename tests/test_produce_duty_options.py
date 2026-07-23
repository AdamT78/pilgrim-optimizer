from __future__ import annotations

from dataclasses import replace

from pilgrim.io import scenarios as scenario_loader
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _select_action_for_resolution(
    scenario_path: str,
    resolution: TurnResolutionType,
):
    scenario = load_scenario(scenario_path)
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is resolution
    )
    return scenario, action


def test_produce_duty_offers_exact_wheat_and_stone_actions() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    north = scenario.config.board.index_for_name("north")
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.selected_duty == north
    ]
    resolutions = {action.resolution for action in actions}
    resolution_names = {action.resolution.value for action in actions}

    assert TurnResolutionType.PRODUCE_WHEAT in resolutions
    assert TurnResolutionType.PRODUCE_STONE in resolutions
    assert "produce" not in resolution_names
    assert "produce_grain" not in resolution_names


def test_produce_wheat_grants_wheat_equal_to_duty_value() -> None:
    scenario, action = _select_action_for_resolution(
        "scenarios/produce_wheat_001.json",
        TurnResolutionType.PRODUCE_WHEAT,
    )
    before = scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE).resources
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )

    assert after.wheat == before.wheat + 2
    assert after.stone == before.stone
    assert after.silver == before.silver
    assert dict(duty_event.details)["effect"] == "produce_wheat"


def test_produce_stone_grants_stone_equal_to_duty_value() -> None:
    scenario, action = _select_action_for_resolution(
        "scenarios/produce_stone_001.json",
        TurnResolutionType.PRODUCE_STONE,
    )
    before = scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE).resources
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )

    assert after.stone == before.stone + 2
    assert after.wheat == before.wheat
    assert after.silver == before.silver
    assert dict(duty_event.details)["effect"] == "produce_stone"


def test_produce_duty_value_is_not_split_between_wheat_and_stone() -> None:
    wheat_scenario, wheat_action = _select_action_for_resolution(
        "scenarios/produce_wheat_001.json",
        TurnResolutionType.PRODUCE_WHEAT,
    )
    wheat_before = wheat_scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    wheat_after = apply_action(
        wheat_scenario.state,
        wheat_action,
        wheat_scenario.config,
    ).state.player_state(PlayerId.PLAYER_ONE).resources

    stone_scenario, stone_action = _select_action_for_resolution(
        "scenarios/produce_stone_001.json",
        TurnResolutionType.PRODUCE_STONE,
    )
    stone_before = stone_scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    stone_after = apply_action(
        stone_scenario.state,
        stone_action,
        stone_scenario.config,
    ).state.player_state(PlayerId.PLAYER_ONE).resources

    assert wheat_after.wheat == wheat_before.wheat + 2
    assert wheat_after.stone == wheat_before.stone
    assert stone_after.stone == stone_before.stone + 2
    assert stone_after.wheat == stone_before.wheat


def test_fields_bonus_applies_only_to_produce_wheat() -> None:
    wheat_scenario, wheat_action = _select_action_for_resolution(
        "scenarios/produce_special_activity_fields_001.json",
        TurnResolutionType.PRODUCE_WHEAT,
    )
    wheat_before = wheat_scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    wheat_result = apply_action(wheat_scenario.state, wheat_action, wheat_scenario.config)
    wheat_after = wheat_result.state.player_state(PlayerId.PLAYER_ONE).resources
    fields_bonus_event = next(
        event
        for event in wheat_result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "fields"
    )

    stone_scenario, stone_action = _select_action_for_resolution(
        "scenarios/produce_special_activity_fields_001.json",
        TurnResolutionType.PRODUCE_STONE,
    )
    stone_before = stone_scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    stone_result = apply_action(stone_scenario.state, stone_action, stone_scenario.config)
    stone_after = stone_result.state.player_state(PlayerId.PLAYER_ONE).resources

    assert wheat_after.wheat == wheat_before.wheat + 3
    assert dict(fields_bonus_event.details).get("action") == "produce_wheat"
    assert dict(fields_bonus_event.details).get("wheat_bonus") == 1

    assert stone_after.stone == stone_before.stone + 2
    assert not any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "fields"
        for event in stone_result.events
    )


def test_stone_mason_bonus_applies_only_to_produce_stone() -> None:
    stone_scenario, stone_action = _select_action_for_resolution(
        "scenarios/produce_special_activity_stone_mason_001.json",
        TurnResolutionType.PRODUCE_STONE,
    )
    stone_before = stone_scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    stone_result = apply_action(stone_scenario.state, stone_action, stone_scenario.config)
    stone_after = stone_result.state.player_state(PlayerId.PLAYER_ONE).resources
    stone_bonus_event = next(
        event
        for event in stone_result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "stone_mason"
    )

    wheat_scenario, wheat_action = _select_action_for_resolution(
        "scenarios/produce_special_activity_stone_mason_001.json",
        TurnResolutionType.PRODUCE_WHEAT,
    )
    wheat_before = wheat_scenario.state.player_state(PlayerId.PLAYER_ONE).resources
    wheat_result = apply_action(wheat_scenario.state, wheat_action, wheat_scenario.config)
    wheat_after = wheat_result.state.player_state(PlayerId.PLAYER_ONE).resources

    assert stone_after.stone == stone_before.stone + 3
    assert dict(stone_bonus_event.details).get("action") == "produce_stone"
    assert dict(stone_bonus_event.details).get("stone_bonus") == 1

    assert wheat_after.wheat == wheat_before.wheat + 2
    assert not any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "stone_mason"
        for event in wheat_result.events
    )


def test_minority_silver_cost_applies_to_produce_wheat_and_produce_stone() -> None:
    scenario = load_scenario("scenarios/produce_wheat_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    minority_state = scenario.state.with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            workforce=replace(player_two.workforce, mancala=(0, 2, 0, 0, 0, 0, 0, 0, 0)),
        ),
    )

    wheat_action = next(
        action
        for action in legal_actions(minority_state, scenario.config)
        if action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    wheat_result = apply_action(minority_state, wheat_action, scenario.config)
    wheat_after = wheat_result.state.player_state(PlayerId.PLAYER_ONE).resources

    stone_action = next(
        action
        for action in legal_actions(minority_state, scenario.config)
        if action.resolution is TurnResolutionType.PRODUCE_STONE
    )
    stone_result = apply_action(minority_state, stone_action, scenario.config)
    stone_after = stone_result.state.player_state(PlayerId.PLAYER_ONE).resources

    assert wheat_after.silver == player_one.resources.silver - 1
    assert wheat_after.wheat == player_one.resources.wheat + 1
    assert stone_after.silver == player_one.resources.silver - 1
    assert stone_after.stone == player_one.resources.stone + 1


def test_legacy_grain_alias_normalizes_to_fields() -> None:
    activities = scenario_loader._special_activities_from_dict({"grain": True})

    assert activities.fields is True
