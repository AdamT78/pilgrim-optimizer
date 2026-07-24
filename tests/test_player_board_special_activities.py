from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.special_activities import SpecialActivities
from pilgrim.rules.special_activities import (
    produce_stone_mason_bonus,
    produce_wheat_fields_bonus,
    road_engineer_duty_value_bonus_hook,
)
from pilgrim.rules.transition import apply_action, legal_actions


def test_player_board_full_setup_has_default_serfs_and_abbey_acolytes() -> None:
    scenario = load_scenario("scenarios/player_board_full_setup_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)

    assert player_one.workforce.village == 8
    assert player_two.workforce.village == 8
    assert player_one.workforce.abbey == 3
    assert player_two.workforce.abbey == 3
    assert player_one.special_activities.count == 0
    assert player_two.special_activities.count == 0


def test_existing_reduced_sandbox_scenarios_remain_valid() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    assert player_one.workforce.village == 0
    assert player_two.workforce.village == 0
    assert player_one.workforce.abbey == 0
    assert player_two.workforce.abbey == 0


def test_allocation_abbey_to_special_activity_occupies_target_and_conserves_acolytes() -> None:
    scenario = load_scenario("scenarios/allocation_abbey_to_special_activity_001.json")
    first_action = legal_actions(scenario.state, scenario.config)[0]

    before_total = scenario.state.total_acolytes(PlayerId.PLAYER_ONE)
    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, first_action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)
    after_total = result.state.total_acolytes(PlayerId.PLAYER_ONE)

    assert first_action.resolution is TurnResolutionType.ALLOCATION
    assert after.workforce.abbey == before.workforce.abbey - 1
    assert after.special_activities.count_for("fields") == 1
    assert before.special_activities.count_for("fields") == 0
    assert before_total == after_total
    assert any(event.event_type is EventType.ALLOCATION for event in result.events)


def test_allocation_special_activity_to_abbey_clears_source() -> None:
    scenario = load_scenario("scenarios/allocation_special_activity_to_abbey_001.json")
    first_action = legal_actions(scenario.state, scenario.config)[0]
    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, first_action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert first_action.resolution is TurnResolutionType.ALLOCATION
    assert before.special_activities.count_for("fields") == 1
    assert after.special_activities.count_for("fields") == 0
    assert after.workforce.abbey == before.workforce.abbey + 1


def test_allocation_special_activity_to_special_activity_moves_between_slots() -> None:
    scenario = load_scenario("scenarios/allocation_special_activity_to_special_activity_001.json")
    first_action = legal_actions(scenario.state, scenario.config)[0]
    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, first_action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert first_action.resolution is TurnResolutionType.ALLOCATION
    assert before.special_activities.count_for("fields") == 1
    assert before.special_activities.count_for("engraver") == 0
    assert after.special_activities.count_for("fields") == 0
    assert after.special_activities.count_for("engraver") == 1
    assert after.workforce.abbey == before.workforce.abbey


def test_engraver_bonus_adds_silver_to_clerical_silversmith() -> None:
    scenario = load_scenario("scenarios/special_activity_clerical_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.CLERICAL_SILVERSMITH
    )
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.silver == 2
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "engraver"
        for event in result.events
    )


def test_vestry_bonus_adds_piety_to_clerical_devotion() -> None:
    scenario = load_scenario("scenarios/special_activity_clerical_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.CLERICAL_DEVOTION
    )
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.piety == 2
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "vestry"
        for event in result.events
    )


def test_alms_house_bonus_actions_require_extra_payment() -> None:
    scenario = load_scenario("scenarios/special_activity_alms_house_001.json")
    give_alms_actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS
    ]

    assert give_alms_actions
    assert any(
        action.alms_house_extra_silver == 1 or action.alms_house_extra_wheat == 1
        for action in give_alms_actions
    )


def test_alms_house_bonus_applies_and_emits_event() -> None:
    scenario = load_scenario("scenarios/special_activity_alms_house_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    assert action.resolution is TurnResolutionType.GIVE_ALMS
    assert action.alms_house_extra_silver == 1 or action.alms_house_extra_wheat == 1

    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.alms_position >= before.alms_position + 2
    assert after.resources.silver == (
        before.resources.silver - action.alms_payment_silver - action.alms_house_extra_silver
    )
    assert after.resources.wheat == (
        before.resources.wheat - action.alms_payment_wheat - action.alms_house_extra_wheat
    )
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "alms_house"
        for event in result.events
    )


def test_alms_house_not_used_without_extra_resource() -> None:
    scenario = load_scenario("scenarios/special_activity_alms_house_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    reduced_resources_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, resources=Resources(stone=0, silver=1, wheat=0)),
    )

    give_alms_actions = [
        action
        for action in legal_actions(reduced_resources_state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS
    ]
    assert give_alms_actions
    assert all(
        action.alms_house_extra_silver == 0 and action.alms_house_extra_wheat == 0
        for action in give_alms_actions
    )


def test_special_activity_hooks_exist() -> None:
    scenario = load_scenario("scenarios/special_activity_clerical_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    assert produce_wheat_fields_bonus(player_one) == 0
    assert produce_stone_mason_bonus(player_one) == 0
    assert road_engineer_duty_value_bonus_hook(player_one, action_key="build_roads") == 0


def test_road_engineer_hook_applies_to_build_roads_only() -> None:
    scenario = load_scenario("scenarios/special_activity_clerical_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_with_road_engineer = replace(
        player_one,
        special_activities=player_one.special_activities.with_activity("road_engineer", True),
    )
    assert road_engineer_duty_value_bonus_hook(
        player_with_road_engineer, action_key="build_roads"
    ) == 1
    assert road_engineer_duty_value_bonus_hook(
        player_with_road_engineer, action_key="construct"
    ) == 0
    assert road_engineer_duty_value_bonus_hook(
        player_with_road_engineer, action_key="produce"
    ) == 0


def test_special_activity_model_rejects_non_boolean_flags() -> None:
    with pytest.raises(ValueError):
        SpecialActivities(fields=3)


def test_special_activity_model_allows_count_based_occupancy() -> None:
    activities = SpecialActivities(fields=2, vestry=1)
    assert activities.count_for("fields") == 2
    assert activities.count_for("vestry") == 1
    assert activities.count == 3


def test_fields_is_valid_special_activity_id() -> None:
    activities = SpecialActivities().with_activity("fields", True)
    assert activities.count_for("fields") == 1
