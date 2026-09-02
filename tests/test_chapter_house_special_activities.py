from __future__ import annotations

from dataclasses import replace

import pytest

import pilgrim.rules.transition as transition
from pilgrim.io import scenarios as scenario_loader
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import AllocationMove, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.model.special_activities import SpecialActivities
from pilgrim.rules.special_activities import (
    allocation_outcome,
    apply_allocation_move_with_capacity,
    legal_allocation_moves,
)
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants


def _actions_for_resolution(path: str, resolution: TurnResolutionType):
    scenario = load_scenario(path)
    actions = [
        action for action in legal_actions(scenario.state, scenario.config) if action.resolution is resolution
    ]
    return scenario, actions


def _allocation_move_sequences_without_second_placement_limit(
    player_state,
    *,
    max_moves: int,
    special_activity_capacity: int,
    min_moves: int = 1,
    requires_second_acolyte_placement: bool = False,
) -> tuple[tuple, ...]:
    """Allocation generator before the one-second-placement cap."""
    if max_moves <= 0:
        return ()
    by_outcome_and_depth = {}
    frontier = [(player_state, ())]

    for depth in range(1, max_moves + 1):
        next_frontier = []
        for current_player_state, current_path in frontier:
            for move in legal_allocation_moves(
                current_player_state,
                capacity=special_activity_capacity,
            ):
                try:
                    next_state = apply_allocation_move_with_capacity(
                        current_player_state,
                        move,
                        capacity=special_activity_capacity,
                    )
                except ValueError:
                    continue
                next_path = (*current_path, move)
                key = (allocation_outcome(next_path), depth)
                if key in by_outcome_and_depth:
                    continue
                by_outcome_and_depth[key] = next_path
                next_frontier.append((next_state, next_path))
        frontier = next_frontier

    shortest_by_outcome = {}
    for (outcome, depth), path in by_outcome_and_depth.items():
        if depth < min_moves or outcome in shortest_by_outcome:
            continue
        shortest_by_outcome[outcome] = path
    return tuple(sorted(shortest_by_outcome.values(), key=len, reverse=True))


def test_loader_supports_legacy_and_count_special_activity_forms() -> None:
    from_bool = scenario_loader._special_activities_from_dict({"vestry": True})
    from_list = scenario_loader._special_activities_from_dict(["vestry"])
    from_count = scenario_loader._special_activities_from_dict({"vestry": 2})

    assert from_bool.count_for("vestry") == 1
    assert from_list.count_for("vestry") == 1
    assert from_count.count_for("vestry") == 2


def test_loader_rejects_count_above_two() -> None:
    with pytest.raises(ValueError, match="range 0..2"):
        scenario_loader._special_activities_from_dict({"vestry": 3})


def test_allocation_active_chapter_house_allows_second_acolyte_from_abbey() -> None:
    scenario, allocation_actions = _actions_for_resolution(
        "scenarios/allocation_chapter_house_second_acolyte_001.json",
        TurnResolutionType.ALLOCATION,
    )
    action = next(
        candidate
        for candidate in allocation_actions
        if len(candidate.allocation_moves) == 1
        and candidate.allocation_moves[0].source == "abbey"
        and candidate.allocation_moves[0].destination == "vestry"
    )

    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert before_player.special_activities.count_for("vestry") == 1
    assert after_player.special_activities.count_for("vestry") == 2
    assert after_player.workforce.abbey == before_player.workforce.abbey - 1
    chapter_house_event = next(
        event
        for event in result.events
        if event.event_type is EventType.BUILDING_BONUS
        and dict(event.details).get("building") == "chapter_house"
    )
    details = dict(chapter_house_event.details)
    assert details["action"] == "allocation"
    assert details["activity"] == "vestry"
    assert details["second_acolyte"] is True


def test_allocation_chapter_house_move_between_special_activities_updates_counts() -> None:
    scenario, allocation_actions = _actions_for_resolution(
        "scenarios/allocation_chapter_house_move_between_special_activities_001.json",
        TurnResolutionType.ALLOCATION,
    )
    action = next(
        candidate
        for candidate in allocation_actions
        if len(candidate.allocation_moves) == 1
        and candidate.allocation_moves[0].source == "engraver"
        and candidate.allocation_moves[0].destination == "vestry"
    )

    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert before_player.special_activities.count_for("engraver") == 1
    assert before_player.special_activities.count_for("vestry") == 1
    assert after_player.special_activities.count_for("engraver") == 0
    assert after_player.special_activities.count_for("vestry") == 2


def test_allocation_moving_from_count_two_decrements_source_by_one() -> None:
    scenario, _allocation_actions = _actions_for_resolution(
        "scenarios/allocation_chapter_house_move_between_special_activities_001.json",
        TurnResolutionType.ALLOCATION,
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_count_two_source = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=SpecialActivities(engraver=2, vestry=0),
        ),
    )
    allocation_actions = [
        action
        for action in legal_actions(state_with_count_two_source, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]
    action = next(
        candidate
        for candidate in allocation_actions
        if len(candidate.allocation_moves) == 1
        and candidate.allocation_moves[0].source == "engraver"
        and candidate.allocation_moves[0].destination == "vestry"
    )

    result = apply_action(state_with_count_two_source, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    assert after_player.special_activities.count_for("engraver") == 1
    assert after_player.special_activities.count_for("vestry") == 1


def test_allocation_destination_at_count_two_is_not_legal_even_with_chapter_house() -> None:
    scenario, _allocation_actions = _actions_for_resolution(
        "scenarios/allocation_chapter_house_second_acolyte_001.json",
        TurnResolutionType.ALLOCATION,
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_full_vestry = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=SpecialActivities(vestry=2),
        ),
    )
    allocation_actions = [
        action
        for action in legal_actions(state_with_full_vestry, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]

    assert not any(
        move.destination == "vestry"
        for action in allocation_actions
        for move in action.allocation_moves
    )


def test_allocation_donated_chapter_house_does_not_increase_capacity() -> None:
    scenario, allocation_actions = _actions_for_resolution(
        "scenarios/allocation_chapter_house_donated_001.json",
        TurnResolutionType.ALLOCATION,
    )
    assert not any(
        move.source == "abbey" and move.destination == "vestry"
        for action in allocation_actions
        for move in action.allocation_moves
    )

    result = apply_action(scenario.state, allocation_actions[0], scenario.config)
    assert not any(
        event.event_type is EventType.BUILDING_BONUS
        and dict(event.details).get("building") == "chapter_house"
        for event in result.events
    )


@pytest.mark.parametrize(
    ("scenario_name", "activity_id"),
    [
        ("clerical_vestry_chapter_house_two_acolytes_001", "vestry"),
        ("give_alms_chapter_house_two_alms_house_001", "alms_house"),
        ("produce_fields_chapter_house_two_acolytes_001", "fields"),
    ],
)
def test_donating_chapter_house_keeps_standing_pairs_on_special_activities(
    scenario_name: str,
    activity_id: str,
) -> None:
    """Capacity limits placements, not whether a standing pair may continue to stand."""
    scenario = load_scenario(f"scenarios/{scenario_name}.json")
    donate_action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
        and action.donate_building_id == "chapter_house"
    )
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)

    result = apply_action(scenario.state, donate_action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert before_player.special_activities.count_for(activity_id) == 2
    assert after_player.special_activities.count_for(activity_id) == 2
    assert after_player.player_board_slots.active_buildings == ()
    assert after_player.player_board_slots.donated_buildings == ("chapter_house",)


def test_allocation_second_placement_limit_removes_exactly_one_action_on_guard_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only abbey->fields, abbey->stone_mason is removed; every other allocation action survives."""
    scenario = load_scenario("scenarios/allocation_chapter_house_two_second_targets_001.json")

    with monkeypatch.context() as patched:
        patched.setattr(
            transition,
            "_allocation_move_sequences",
            _allocation_move_sequences_without_second_placement_limit,
        )
        before = [
            action
            for action in legal_actions(scenario.state, scenario.config)
            if action.resolution is TurnResolutionType.ALLOCATION
        ]
    after = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.ALLOCATION
    ]

    before_by_id = {action_id(action): action for action in before}
    before_ids = set(before_by_id)
    after_ids = {action_id(action) for action in after}
    removed = before_ids - after_ids
    added = after_ids - before_ids

    assert len(before) == 81
    assert len(after) == 80
    assert not added, f"unexpected new allocation actions appeared: {sorted(added)}"
    assert len(removed) == 1
    removed_action = before_by_id[next(iter(removed))]
    assert tuple((move.source, move.destination) for move in removed_action.allocation_moves) == (
        ("abbey", "fields"),
        ("abbey", "stone_mason"),
    )
    assert allocation_outcome(removed_action.allocation_moves) == (
        ("abbey", -2),
        ("fields", 1),
        ("stone_mason", 1),
    )


def test_order_dependent_allocation_outcome_stays_legal_when_one_ordering_works() -> None:
    """Legality is existential: keep an outcome when one legal ordering stays under the cap."""
    scenario = load_scenario("scenarios/allocation_chapter_house_two_second_targets_001.json")
    player_state = replace(
        scenario.state.player_state(PlayerId.PLAYER_ONE),
        special_activities=SpecialActivities(fields=1, vestry=1),
    )
    sequences = transition._allocation_move_sequences(
        player_state,
        max_moves=2,
        special_activity_capacity=2,
        min_moves=2,
    )
    wanted = (("abbey", -1), ("vestry", 1))
    assert any(allocation_outcome(sequence) == wanted for sequence in sequences)

    # This concrete ordering is the one-placement route to that outcome.
    first = apply_allocation_move_with_capacity(
        player_state,
        AllocationMove(source="fields", destination="vestry"),
        capacity=2,
    )
    second = apply_allocation_move_with_capacity(
        first,
        AllocationMove(source="abbey", destination="fields"),
        capacity=2,
    )
    assert second.special_activities.count_for("fields") == 1
    assert second.special_activities.count_for("vestry") == 2


def test_produce_fields_two_acolytes_scales_bonus_to_plus_two() -> None:
    scenario, produce_actions = _actions_for_resolution(
        "scenarios/produce_fields_chapter_house_two_acolytes_001.json",
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, produce_actions[0], scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "fields"
    )
    bonus_details = dict(bonus_event.details)

    assert duty_details["duty_value"] == 2
    assert duty_details["effective_duty_value"] == 2
    assert bonus_details["wheat_bonus"] == 2
    assert after_player.resources.wheat == 4


def test_clerical_vestry_two_acolytes_scales_bonus_to_plus_two() -> None:
    scenario, clerical_actions = _actions_for_resolution(
        "scenarios/clerical_vestry_chapter_house_two_acolytes_001.json",
        TurnResolutionType.CLERICAL_DEVOTION,
    )
    result = apply_action(scenario.state, clerical_actions[0], scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "vestry"
    )
    bonus_details = dict(bonus_event.details)

    assert duty_details["duty_value"] == 2
    assert duty_details["effective_duty_value"] == 2
    assert bonus_details["piety_bonus"] == 2
    assert after_player.piety == 4


def test_build_roads_two_road_engineers_scales_duty_value_bonus_to_plus_two() -> None:
    scenario, build_roads_actions = _actions_for_resolution(
        "scenarios/build_roads_chapter_house_two_road_engineers_001.json",
        TurnResolutionType.BUILD_ROADS_DEFERRED,
    )
    result = apply_action(scenario.state, build_roads_actions[0], scenario.config)

    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "road_engineer"
    )
    bonus_details = dict(bonus_event.details)

    assert duty_details["duty_value"] == 2
    assert duty_details["effective_duty_value"] == 4
    assert bonus_details["duty_value_bonus"] == 2


def test_give_alms_two_alms_house_supports_plus_two_payment_ceiling_for_free() -> None:
    scenario, give_alms_actions = _actions_for_resolution(
        "scenarios/give_alms_chapter_house_two_alms_house_001.json",
        TurnResolutionType.GIVE_ALMS_PAID,
    )
    assert any(
        action.alms_payment_silver + action.alms_payment_wheat == 4
        for action in give_alms_actions
    )
    action = next(
        action
        for action in give_alms_actions
        if action.alms_payment_silver + action.alms_payment_wheat == 4
    )
    result = apply_action(scenario.state, action, scenario.config)

    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "alms_house"
    )
    bonus_details = dict(bonus_event.details)

    assert duty_details["duty_value"] == 2
    assert duty_details["effective_duty_value"] == 4
    assert bonus_details["duty_value_bonus"] == 2


def test_alms_house_count_two_does_not_apply_to_donate_building() -> None:
    scenario = load_scenario("scenarios/give_alms_chapter_house_two_alms_house_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    donate_ready_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("chapter_house", "confession_box"),
                donated_buildings=(),
            ),
        ),
    )
    donate_action = next(
        action
        for action in legal_actions(donate_ready_state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
        and action.donate_building_id == "confession_box"
    )
    result = apply_action(donate_ready_state, donate_action, scenario.config)

    assert not any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "alms_house"
        for event in result.events
    )


def test_construct_two_road_engineers_supports_double_extra_road_scaffold() -> None:
    scenario, construct_actions = _actions_for_resolution(
        "scenarios/construct_chapter_house_two_road_engineers_001.json",
        TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
    )
    construct_plans = {action.construct_plan for action in construct_actions}
    assert "road" in construct_plans
    assert "road + road_engineer_extra_road" in construct_plans
    assert "road + road_engineer_extra_road + road_engineer_extra_road" in construct_plans

    action = next(
        action
        for action in construct_actions
        if action.construct_plan == "road + road_engineer_extra_road + road_engineer_extra_road"
    )
    result = apply_action(scenario.state, action, scenario.config)

    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    bonus_event = next(
        event
        for event in result.events
        if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "road_engineer"
    )
    bonus_details = dict(bonus_event.details)
    deferred_event = next(event for event in result.events if event.event_type is EventType.DUTY_DEFERRED)

    assert duty_details["duty_value"] == duty_details["effective_duty_value"]
    assert bonus_details["construct_extra_roads"] == 2
    assert "road + road_engineer_extra_road + road_engineer_extra_road" in str(
        dict(deferred_event.details)["scaffold"]
    )


def test_special_activity_count_two_without_chapter_house_passes_validation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    valid_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=SpecialActivities(fields=2),
        ),
    )
    validate_state_invariants(valid_state)


def test_special_activity_count_two_with_active_chapter_house_passes_validation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    valid_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=SpecialActivities(fields=2),
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("chapter_house",),
                donated_buildings=(),
            ),
        ),
    )
    validate_state_invariants(valid_state)
    assert (
        valid_state.total_acolytes(PlayerId.PLAYER_ONE)
        == scenario.state.total_acolytes(PlayerId.PLAYER_ONE) + 2
    )
