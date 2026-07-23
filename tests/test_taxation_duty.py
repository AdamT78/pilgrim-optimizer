from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.model.special_activities import SpecialActivities
from pilgrim.rules.transition import apply_action, legal_actions


def test_taxation_legal_actions_include_step1_choices_and_tithe() -> None:
    scenario = load_scenario("scenarios/taxation_no_other_majority_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    taxation_actions = [
        action for action in actions if action.resolution is TurnResolutionType.TAXATION
    ]

    assert taxation_actions
    assert len(taxation_actions) == 3
    assert {action.taxation_step1_resource for action in taxation_actions} == {
        "stone",
        "silver",
        "wheat",
    }
    assert all(action.taxation_step2_resources == () for action in taxation_actions)
    assert any(action.resolution is TurnResolutionType.TITHE for action in actions)


def test_taxation_majority_bonus_allows_repeated_or_mixed_step2_resources() -> None:
    scenario = load_scenario("scenarios/taxation_majority_bonus_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    taxation_actions = [
        action
        for action in actions
        if action.resolution is TurnResolutionType.TAXATION
        and action.taxation_step1_resource == "stone"
    ]
    step2_choices = {action.taxation_step2_resources for action in taxation_actions}

    assert step2_choices == {
        ("stone", "stone"),
        ("stone", "silver"),
        ("silver", "silver"),
    }
    assert all(len(action.taxation_step2_resources) == 2 for action in taxation_actions)
    assert all(1 + len(action.taxation_step2_resources) <= 3 for action in taxation_actions)


def test_taxation_single_bonus_type_generates_double_same_resource() -> None:
    scenario = load_scenario("scenarios/taxation_single_bonus_type_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    taxation_actions = [
        action for action in actions if action.resolution is TurnResolutionType.TAXATION
    ]

    assert len(taxation_actions) == 3
    assert all(action.taxation_step2_resources == ("stone", "stone") for action in taxation_actions)


def test_taxation_parity_on_other_tile_does_not_unlock_step2_resources() -> None:
    scenario = load_scenario("scenarios/taxation_parity_not_bonus_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    taxation_actions = [
        action for action in actions if action.resolution is TurnResolutionType.TAXATION
    ]

    assert taxation_actions
    assert all(action.taxation_step2_resources == () for action in taxation_actions)


def test_taxation_apply_no_other_majority_gains_step1_only_and_recalls_taxation_tile() -> None:
    scenario = load_scenario("scenarios/taxation_no_other_majority_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TAXATION
        and candidate.taxation_step1_resource == "wheat"
    )
    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    taxation_events = [event for event in result.events if event.event_type is EventType.TAXATION]
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )

    assert after.resources.wheat == before.resources.wheat + 1
    assert after.resources.stone == before.resources.stone
    assert after.resources.silver == before.resources.silver
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[8] == 0
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 1
    assert len(taxation_events) == 2
    assert dict(taxation_events[0].details)["step"] == "step_1"
    assert dict(taxation_events[1].details)["no_bonus"] is True
    assert dict(resource_event.details)["wheat"] == 1


def test_taxation_apply_majority_bonus_gains_step2_and_does_not_recall_other_majorities() -> None:
    scenario = load_scenario("scenarios/taxation_majority_bonus_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TAXATION
        and candidate.taxation_step1_resource == "wheat"
        and candidate.taxation_step2_resources == ("stone", "silver")
    )
    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    before_vector = scenario.state.player_vector(PlayerId.PLAYER_ONE)
    before_counters = scenario.config.tithe_counters_mapping()
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)
    after_vector = result.state.player_vector(PlayerId.PLAYER_ONE)
    west = scenario.config.board.index_for_name("west")
    south_west = scenario.config.board.index_for_name("south_west")

    taxation_event = next(
        event
        for event in result.events
        if event.event_type is EventType.TAXATION and dict(event.details)["step"] == "step_2"
    )
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )

    assert after.resources.wheat == before.resources.wheat + 1
    assert after.resources.stone == before.resources.stone + 1
    assert after.resources.silver == before.resources.silver + 1
    assert after_vector[action.selected_duty] == 0
    assert after_vector[west] == before_vector[west]
    assert after_vector[south_west] == before_vector[south_west]
    assert dict(taxation_event.details)["resources"] == "stone,silver"
    assert dict(resource_event.details)["stone"] == 1
    assert dict(resource_event.details)["silver"] == 1
    assert dict(resource_event.details)["wheat"] == 1
    assert after.piety == before.piety
    assert after.alms_position == before.alms_position
    assert scenario.config.tithe_counters_mapping() == before_counters


def test_taxation_apply_minority_pays_silver_cost_and_still_gains_resource() -> None:
    scenario = load_scenario("scenarios/taxation_minor_cost_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TAXATION
        and candidate.taxation_step1_resource == "stone"
    )
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )

    assert after.resources.stone == 1
    assert after.resources.silver == 0
    assert dict(duty_event.details)["strength"] == "minority"
    assert dict(duty_event.details)["silver_cost"] == 1
    assert dict(resource_event.details)["stone"] == 1
    assert dict(resource_event.details)["silver"] == -1


def test_taxation_not_modified_by_special_activities() -> None:
    scenario = load_scenario("scenarios/taxation_no_other_majority_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TAXATION
        and candidate.taxation_step1_resource == "stone"
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    boosted_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=SpecialActivities(
                fields=True,
                road_engineer=True,
                stone_mason=True,
                alms_house=True,
                engraver=True,
                vestry=True,
            ),
        ),
    )
    result = apply_action(boosted_state, action, scenario.config)
    bonus_events = [
        event for event in result.events if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
    ]
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )

    assert not bonus_events
    assert dict(resource_event.details)["stone"] == 1
    assert dict(resource_event.details)["silver"] == 0
    assert dict(resource_event.details)["wheat"] == 0


def test_tithe_counters_allow_missing_or_null_taxation_counter() -> None:
    missing_counter = load_scenario("scenarios/taxation_majority_bonus_001.json")
    explicit_null_counter = load_scenario("scenarios/taxation_tile_no_tithe_counter_001.json")

    missing_taxation_position = missing_counter.config.position_name_for_duty_category("taxation")
    explicit_null_taxation_position = explicit_null_counter.config.position_name_for_duty_category(
        "taxation"
    )

    assert (
        missing_counter.config.tithe_counters.resource_for_position_name(missing_taxation_position)
        is None
    )
    assert (
        explicit_null_counter.config.tithe_counters.resource_for_position_name(
            explicit_null_taxation_position
        )
        is None
    )


def test_fallback_tithe_counters_never_assign_counter_to_taxation_tile() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    taxation_position_name = scenario.config.position_name_for_duty_category("taxation")
    assert scenario.config.tithe_counters.resource_for_position_name(taxation_position_name) is None


def test_tithe_counters_reject_non_null_counter_on_taxation_tile(tmp_path: Path) -> None:
    scenario_raw = _absolute_base_scenario()
    scenario_raw["scenario_id"] = "tmp_invalid_taxation_counter"
    scenario_raw["tithe_counters"] = {"north_west": "cornucopia"}
    scenario_path = tmp_path / "tmp_invalid_taxation_counter.json"
    scenario_path.write_text(json.dumps(scenario_raw), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot have a non-null tithe counter"):
        load_scenario(scenario_path)


def test_tithe_counters_reject_city_key_and_invalid_resource(tmp_path: Path) -> None:
    city_raw = _absolute_base_scenario()
    city_raw["scenario_id"] = "tmp_invalid_city_counter"
    city_raw["tithe_counters"] = {"city": "stone"}
    city_path = tmp_path / "tmp_invalid_city_counter.json"
    city_path.write_text(json.dumps(city_raw), encoding="utf-8")

    with pytest.raises(ValueError, match="city cannot have a tithe counter"):
        load_scenario(city_path)

    resource_raw = _absolute_base_scenario()
    resource_raw["scenario_id"] = "tmp_invalid_counter_resource"
    resource_raw["tithe_counters"] = {"north": "gold"}
    resource_path = tmp_path / "tmp_invalid_counter_resource.json"
    resource_path.write_text(json.dumps(resource_raw), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid tithe counter resource"):
        load_scenario(resource_path)


def _absolute_base_scenario() -> dict[str, object]:
    raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text(encoding="utf-8"))
    root = Path.cwd().resolve()
    for key in (
        "board_file",
        "duties_file",
        "piety_file",
        "alms_file",
        "timing_file",
        "merchant_file",
        "ship_file",
        "buildings_file",
    ):
        raw[key] = str((root / str(raw[key])).resolve())
    return raw
