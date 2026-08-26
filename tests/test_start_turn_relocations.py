from __future__ import annotations

from dataclasses import fields, replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingRelocationStep, FullTurnAction, action_id
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


def _relocation_steps(path: str, building_id: str):
    scenario = load_scenario(path)
    steps = [
        step
        for step in turn_steps(scenario.state, scenario.config)
        if step.building_id == building_id
    ]
    return scenario, steps


def _first(items, predicate):
    return next(item for item in items if predicate(item))


def _with_active_building(scenario, building_id: str):
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    return scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(*player_state.player_board_slots.active_buildings, building_id),
            ),
        ),
    )


def test_dormitory_active_offers_exactly_occupied_duties_and_marks_it_used() -> None:
    scenario, steps = _relocation_steps(
        "scenarios/dormitory_active_return_duty_to_city_001.json", "dormitory"
    )
    city = scenario.config.board.index_for_name("city")
    occupied_duties = {
        position
        for position in scenario.config.duty_positions()
        if scenario.state.player_vector(scenario.state.active_player)[position] > 0
    }

    assert {step.selected_position for step in steps} == occupied_duties
    step = steps[0]
    after = apply_turn_step(scenario.state, scenario.config, step)

    assert after.player_vector(after.active_player)[city] == (
        scenario.state.player_vector(scenario.state.active_player)[city] + 1
    )
    assert after.player_vector(after.active_player)[step.selected_position] == (
        scenario.state.player_vector(scenario.state.active_player)[step.selected_position] - 1
    )
    assert "dormitory" in after.turn_progress.used_buildings


def test_dormitory_market_hire_generates_payable_steps() -> None:
    _scenario, steps = _relocation_steps(
        "scenarios/dormitory_hire_market_return_duty_to_city_001.json", "dormitory"
    )

    assert steps
    assert all(step.source == "market" for step in steps)
    assert all(step.hire_payment == "wheat" for step in steps)


def test_dormitory_opponent_hire_pays_owner_and_relocates() -> None:
    scenario, steps = _relocation_steps(
        "scenarios/dormitory_hire_opponent_return_duty_to_city_001.json", "dormitory"
    )
    east = scenario.config.board.index_for_name("east")
    step = _first(
        steps,
        lambda candidate: candidate.source == "player_two" and candidate.selected_position == east,
    )

    after = apply_turn_step(scenario.state, scenario.config, step)
    hired_event = _events_of_type(after.turn_progress.events, EventType.BUILDING_HIRED)[0]
    relocation_event = _events_of_type(after.turn_progress.events, EventType.START_TURN_RELOCATION)[
        0
    ]
    hired_details = dict(hired_event.details)
    relocation_details = dict(relocation_event.details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert relocation_details["from_position"] == east
    assert scenario.config.board.index_for_name("city") == relocation_details["to_position"]
    assert after.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_dormitory_hire_is_unavailable_without_a_payable_source() -> None:
    _scenario, merchant_none_steps = _relocation_steps(
        "scenarios/dormitory_merchant_none_no_hire_001.json", "dormitory"
    )
    scenario = load_scenario("scenarios/dormitory_hire_market_return_duty_to_city_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    insufficient_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=replace(player.resources, wheat=0)),
    )
    insufficient_steps = [
        step
        for step in turn_steps(insufficient_state, scenario.config)
        if step.building_id == "dormitory"
    ]

    assert merchant_none_steps == []
    assert insufficient_steps == []


def test_dormitory_donated_not_live_or_without_a_duty_acolyte_is_unavailable() -> None:
    _scenario, donated_steps = _relocation_steps(
        "scenarios/dormitory_donated_no_modifier_001.json", "dormitory"
    )
    _scenario, no_duty_steps = _relocation_steps(
        "scenarios/dormitory_no_duty_acolyte_no_modifier_001.json", "dormitory"
    )
    scenario = load_scenario("scenarios/dormitory_hire_market_return_duty_to_city_001.json")
    not_live_state = scenario.state.with_building_availability((("dormitory", 7),))
    not_live_steps = [
        step
        for step in turn_steps(not_live_state, scenario.config)
        if step.building_id == "dormitory"
    ]

    assert donated_steps == []
    assert no_duty_steps == []
    assert not_live_steps == []


def test_inquisition_active_offers_every_reachable_duty_and_marks_it_used() -> None:
    scenario, steps = _relocation_steps(
        "scenarios/inquisition_active_city_to_duty_001.json", "inquisition"
    )
    city = scenario.config.board.index_for_name("city")

    assert {step.selected_position for step in steps} == set(scenario.config.duty_positions())
    step = steps[0]
    after = apply_turn_step(scenario.state, scenario.config, step)

    assert after.player_vector(after.active_player)[city] == (
        scenario.state.player_vector(scenario.state.active_player)[city] - 1
    )
    assert after.player_vector(after.active_player)[step.selected_position] == (
        scenario.state.player_vector(scenario.state.active_player)[step.selected_position] + 1
    )
    assert "inquisition" in after.turn_progress.used_buildings


def test_inquisition_market_hire_generates_payable_steps() -> None:
    _scenario, steps = _relocation_steps(
        "scenarios/inquisition_hire_market_city_to_duty_001.json", "inquisition"
    )

    assert steps
    assert all(step.source == "market" for step in steps)
    assert all(step.hire_payment == "wheat" for step in steps)


def test_inquisition_opponent_hire_pays_owner_and_relocates() -> None:
    scenario, steps = _relocation_steps(
        "scenarios/inquisition_hire_opponent_city_to_duty_001.json", "inquisition"
    )
    west = scenario.config.board.index_for_name("west")
    step = _first(
        steps,
        lambda candidate: candidate.source == "player_two" and candidate.selected_position == west,
    )

    after = apply_turn_step(scenario.state, scenario.config, step)
    hired_event = _events_of_type(after.turn_progress.events, EventType.BUILDING_HIRED)[0]
    relocation_event = _events_of_type(after.turn_progress.events, EventType.START_TURN_RELOCATION)[
        0
    ]
    hired_details = dict(hired_event.details)
    relocation_details = dict(relocation_event.details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert relocation_details["from_position"] == scenario.config.board.index_for_name("city")
    assert relocation_details["to_position"] == west
    assert after.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_inquisition_hire_is_unavailable_without_a_payable_source() -> None:
    _scenario, merchant_none_steps = _relocation_steps(
        "scenarios/inquisition_merchant_none_no_hire_001.json", "inquisition"
    )
    scenario = load_scenario("scenarios/inquisition_hire_market_city_to_duty_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    insufficient_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=replace(player.resources, wheat=0)),
    )
    insufficient_steps = [
        step
        for step in turn_steps(insufficient_state, scenario.config)
        if step.building_id == "inquisition"
    ]

    assert merchant_none_steps == []
    assert insufficient_steps == []


def test_inquisition_donated_not_live_or_without_a_city_acolyte_is_unavailable() -> None:
    scenario = load_scenario("scenarios/inquisition_hire_market_city_to_duty_001.json")
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    donated_state = scenario.state.with_building_market(()).with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            player_board_slots=replace(
                player_two.player_board_slots,
                donated_buildings=("inquisition",),
            ),
        ),
    )
    donated_steps = [
        step
        for step in turn_steps(donated_state, scenario.config)
        if step.building_id == "inquisition"
    ]
    _scenario, not_live_steps = _relocation_steps(
        "scenarios/inquisition_not_live_no_modifier_001.json", "inquisition"
    )
    _scenario, no_city_steps = _relocation_steps(
        "scenarios/inquisition_no_city_acolyte_no_modifier_001.json", "inquisition"
    )

    assert donated_steps == []
    assert not_live_steps == []
    assert no_city_steps == []


def test_start_turn_relocation_steps_close_after_resolution_but_guild_stays_open() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    state = _with_active_building(scenario, "guild")
    resolution = apply_action(state, legal_actions(state, scenario.config)[0], scenario.config)
    remaining = turn_steps(resolution.state, scenario.config)

    assert resolution.state.turn_progress.resolution_committed
    assert not any(step.building_id in {"dormitory", "inquisition"} for step in remaining)
    assert any(step.building_id == "guild" for step in remaining)


def test_start_turn_relocation_events_are_only_emitted_by_a_committed_step() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    result = apply_action(
        scenario.state, legal_actions(scenario.state, scenario.config)[0], scenario.config
    )

    assert _events_of_type(result.events, EventType.START_TURN_RELOCATION) == []
    assert not any(
        dict(event.details).get("building") in {"dormitory", "inquisition"}
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )


def test_committed_relocation_events_precede_the_following_sowing_and_preserve_invariants() -> None:
    scenario, steps = _relocation_steps(
        "scenarios/inquisition_active_city_to_duty_001.json", "inquisition"
    )
    north = scenario.config.board.index_for_name("north")
    stepped = apply_turn_step(
        scenario.state,
        scenario.config,
        _first(steps, lambda step: step.selected_position == north),
    )
    action = _first(
        legal_actions(stepped, scenario.config), lambda candidate: candidate.origin == 0
    )
    result = apply_action(stepped, action, scenario.config)
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    relocation_event = _events_of_type(result.events, EventType.START_TURN_RELOCATION)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[0]

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert result.events.index(bonus_event) < result.events.index(relocation_event)
    assert result.events.index(relocation_event) < result.events.index(sowing_event)
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_relocation_steps_reject_non_duty_positions_and_post_resolution_use() -> None:
    scenario, steps = _relocation_steps(
        "scenarios/dormitory_active_return_duty_to_city_001.json", "dormitory"
    )
    invalid = replace(steps[0], selected_position=scenario.config.board.index_for_name("city"))
    resolved = apply_action(
        scenario.state,
        legal_actions(scenario.state, scenario.config)[0],
        scenario.config,
    ).state

    with pytest.raises(TransitionValidationError, match="Duty position"):
        apply_turn_step(scenario.state, scenario.config, invalid)
    with pytest.raises(TransitionValidationError, match="only available before resolution"):
        apply_turn_step(resolved, scenario.config, steps[0])


def test_full_turn_actions_and_ids_carry_no_start_turn_relocation_fields() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    field_names = {field.name for field in fields(FullTurnAction)}

    assert {"start_turn_building_id", "start_turn_building_source"}.isdisjoint(field_names)
    assert {"start_turn_relocation_from", "start_turn_relocation_to"}.isdisjoint(field_names)
    assert "start_turn" not in action_id(action)
    assert isinstance(turn_steps(scenario.state, scenario.config)[0], BuildingRelocationStep)


@pytest.mark.parametrize(
    ("scenario_path", "building_id", "field_name"),
    (
        (
            "scenarios/scriptorium_active_majority_selected_duty_001.json",
            "scriptorium",
            "effective_acolyte_building_id",
        ),
        (
            "scenarios/customs_house_active_taxation_majority_001.json",
            "customs_house",
            "taxation_majority_building_id",
        ),
    ),
)
def test_dormitory_step_can_combine_with_each_remaining_full_turn_modifier(
    scenario_path: str,
    building_id: str,
    field_name: str,
) -> None:
    scenario = load_scenario(scenario_path)
    state = _with_active_building(scenario, "dormitory")
    step = _first(
        turn_steps(state, scenario.config), lambda candidate: candidate.building_id == "dormitory"
    )
    after_step = apply_turn_step(state, scenario.config, step)

    assert any(
        getattr(action, field_name) == building_id
        for action in legal_actions(after_step, scenario.config)
    )


def test_dormitory_step_can_combine_with_wagon_yards_free_pulpit_step() -> None:
    scenario = load_scenario("scenarios/wagon_yard_active_free_hire_market_pulpit_001.json")
    state = _with_active_building(scenario, "dormitory")
    dormitory_step = _first(
        turn_steps(state, scenario.config), lambda candidate: candidate.building_id == "dormitory"
    )
    after_dormitory = apply_turn_step(state, scenario.config, dormitory_step)
    pulpit_step = _first(
        turn_steps(after_dormitory, scenario.config), lambda candidate: candidate.building_id == "pulpit"
    )

    assert pulpit_step.hire_payment is None


def test_inquisition_step_can_combine_with_bank() -> None:
    scenario = load_scenario("scenarios/bank_active_ordination_substitution_001.json")
    player = scenario.state.active_player
    source_position = next(
        position
        for position in scenario.config.duty_positions()
        if scenario.state.player_vector(player)[position] > 0
    )
    city = scenario.config.board.index_for_name("city")
    vector = list(scenario.state.player_vector(player))
    vector[source_position] -= 1
    vector[city] += 1
    state = scenario.state.with_player_vector(player, tuple(vector))
    state = _with_active_building(replace(scenario, state=state), "inquisition")
    step = _first(
        turn_steps(state, scenario.config),
        lambda candidate: (
            candidate.building_id == "inquisition"
            and candidate.selected_position == source_position
        ),
    )
    after_step = apply_turn_step(state, scenario.config, step)

    assert any(
        action.bank_payment_building_id == "bank"
        for action in legal_actions(after_step, scenario.config)
    )
