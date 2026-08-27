from __future__ import annotations

from dataclasses import fields, replace

import pytest

from pilgrim.io.event_text import format_event_for_players
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, FullTurnAction
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.merchant import CORNUCOPIA_COUNTER, taxation_board_position
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _pulpit_steps(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    steps = [
        step
        for step in turn_steps(scenario.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "pulpit"
    ]
    return scenario, actions, steps


def _first(items, predicate):
    return next(item for item in items if predicate(item))


def _commit_and_resolve(scenario, step, resolution: TurnResolutionType):
    state = apply_turn_step(scenario.state, scenario.config, step)
    action = _first(
        legal_actions(state, scenario.config),
        lambda candidate: candidate.resolution is resolution,
    )
    return state, apply_action(state, action, scenario.config)


def test_own_active_pulpit_generates_one_free_beginning_of_turn_step() -> None:
    _scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_active_move_serf_001.json")

    assert steps == [BuildingActivationStep("pulpit", "own_active")]


def test_own_active_pulpit_generates_no_step_when_village_has_no_serfs() -> None:
    _scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_no_village_serf_no_modifier_001.json")

    assert steps == []


def test_own_active_pulpit_works_when_merchant_resource_is_none() -> None:
    scenario = load_scenario("scenarios/pulpit_active_move_serf_001.json")
    taxation_state = replace(
        scenario.state,
        # Taxation is a looked-up tile now, not index 0 of the retired six-step path.
        merchant_board_position=taxation_board_position(scenario.config),
    )
    steps = [
        step for step in turn_steps(taxation_state, scenario.config) if step.building_id == "pulpit"
    ]

    assert steps == [BuildingActivationStep("pulpit", "own_active")]


def test_own_active_pulpit_source_priority_blocks_hired_steps() -> None:
    scenario = load_scenario("scenarios/pulpit_hire_market_move_serf_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_pulpit = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("pulpit",),
            ),
        ),
    )
    steps = [
        step
        for step in turn_steps(state_with_own_pulpit, scenario.config)
        if step.building_id == "pulpit"
    ]

    assert steps == [BuildingActivationStep("pulpit", "own_active")]


def test_hired_market_and_opponent_pulpit_steps_carry_settled_payment() -> None:
    _market_scenario, _market_actions, market_steps = _pulpit_steps(
        "scenarios/pulpit_hire_market_move_serf_001.json"
    )
    _opponent_scenario, _opponent_actions, opponent_steps = _pulpit_steps(
        "scenarios/pulpit_hire_opponent_move_serf_001.json"
    )

    assert market_steps == [BuildingActivationStep("pulpit", "market", "wheat")]
    assert opponent_steps == [BuildingActivationStep("pulpit", "player_two", "silver")]


def test_pulpit_keeps_every_cornucopia_payment_pick_on_its_committed_step() -> None:
    scenario = load_scenario("scenarios/deep_round_eighteen_seed_seven_two_player_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=replace(player.resources, wheat=1, stone=1, silver=1)),
    )
    state = replace(state, timing=replace(state.timing, round_number=22))
    assert (
        scenario.config.tithe_counters.resource_for_board_index(state.merchant_board_position)
        == CORNUCOPIA_COUNTER
    )
    steps = [step for step in turn_steps(state, scenario.config) if step.building_id == "pulpit"]

    assert [step.hire_payment for step in steps] == ["wheat", "stone", "silver"]
    after = apply_turn_step(state, scenario.config, steps[1])
    hired = _events_of_type(after.turn_progress.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["resource"] == "stone"


def test_merchant_none_insufficient_donated_not_live_and_no_village_block_pulpit() -> None:
    blocked_paths = (
        "scenarios/pulpit_merchant_none_no_hire_001.json",
        "scenarios/pulpit_insufficient_hire_resource_001.json",
        "scenarios/pulpit_donated_no_modifier_001.json",
        "scenarios/pulpit_not_live_no_modifier_001.json",
        "scenarios/pulpit_no_village_serf_no_modifier_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, steps = _pulpit_steps(path)
        assert steps == []
        assert actions


def test_apply_own_active_pulpit_moves_exactly_one_serf_before_sowing_without_wheat_cost() -> None:
    scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_active_move_serf_001.json")
    before_player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    step_state, result = _commit_and_resolve(scenario, steps[0], TurnResolutionType.TITHE)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    bonus_event = _first(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "pulpit",
    )
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    workforce_details = dict(workforce_event.details)

    assert _events_of_type(step_state.turn_progress.events, EventType.BUILDING_HIRED) == []
    assert before_player.resources.wheat == after_player.resources.wheat
    assert after_player.workforce.village == before_player.workforce.village - 1
    assert after_player.workforce.abbey == before_player.workforce.abbey + 1
    assert workforce_details == {
        "amount": 1,
        "building": "pulpit",
        "from_pool": "village",
        "to_pool": "abbey",
        "unit": "serf",
        "wheat_paid": 0,
        "player_line_suppressed": True,
    }
    assert result.events.index(bonus_event) < result.events.index(workforce_event) < result.events.index(
        sowing_event
    )
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_pulpit_bonus_owns_the_only_player_line_for_its_workforce_move() -> None:
    scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_active_move_serf_001.json")
    _step_state, result = _commit_and_resolve(scenario, steps[0], TurnResolutionType.TITHE)
    bonus_event = _first(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "pulpit",
    )
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    player_lines = [
        line
        for event in (bonus_event, workforce_event)
        if (line := format_event_for_players(event, scenario.config)) is not None
    ]

    assert player_lines == [
        "player_one used the Pulpit to move a serf from the Village to the Abbey."
    ]


def test_hired_market_pulpit_pays_bank_before_free_move() -> None:
    scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_hire_market_move_serf_001.json")
    _step_state, result = _commit_and_resolve(scenario, steps[0], TurnResolutionType.TITHE)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "pulpit",
    )
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "pulpit"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert result.events.index(hired_event) < result.events.index(bonus_event) < result.events.index(
        workforce_event
    ) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_hired_opponent_pulpit_pays_owner_before_free_move() -> None:
    scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_hire_opponent_move_serf_001.json")
    _step_state, result = _commit_and_resolve(scenario, steps[0], TurnResolutionType.TITHE)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "silver"
    # The hire's silver goes to player two and the tithe's silver counter replaces it.
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_apply_rejects_hired_pulpit_when_hire_payment_is_unaffordable() -> None:
    scenario = load_scenario("scenarios/pulpit_insufficient_hire_resource_001.json")
    invalid_step = BuildingActivationStep("pulpit", "market", "wheat")

    with pytest.raises(TransitionValidationError, match="Pulpit is unavailable in current state"):
        apply_turn_step(scenario.state, scenario.config, invalid_step)


def test_full_turn_actions_carry_no_pulpit_modifier_fields() -> None:
    _scenario, actions, _steps = _pulpit_steps("scenarios/pulpit_active_move_serf_001.json")
    field_names = {field.name for field in fields(FullTurnAction)}

    assert {"workforce_move_building_id", "workforce_move_building_source"}.isdisjoint(field_names)
    assert actions


def test_pulpit_and_infirmary_do_not_stack_free_village_to_abbey_move() -> None:
    scenario, _actions, steps = _pulpit_steps(
        "scenarios/pulpit_infirmary_does_not_double_free_move_001.json"
    )
    step_state = apply_turn_step(scenario.state, scenario.config, steps[0])
    ordination_actions = [
        action
        for action in legal_actions(step_state, scenario.config)
        if action.resolution is TurnResolutionType.ORDINATION
    ]
    action = _first(ordination_actions, lambda candidate: len(candidate.ordination_steps) == 2)
    result = apply_action(step_state, action, scenario.config)
    workforce_events = _events_of_type(result.events, EventType.WORKFORCE_MOVE)
    ordination_events = _events_of_type(result.events, EventType.ORDINATION)
    duty_details = dict(_events_of_type(result.events, EventType.DUTY_RESOLUTION)[0].details)

    assert all(len(action.ordination_steps) <= 2 for action in ordination_actions)
    assert len(workforce_events) == 1
    assert dict(workforce_events[0].details)["wheat_paid"] == 0
    assert len(ordination_events) == 2
    assert all(dict(event.details)["wheat_paid"] == 1 for event in ordination_events)
    assert duty_details["duty_value"] == 1
    assert duty_details["effective_duty_value"] == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.events.index(workforce_events[0]) < result.events.index(
        _events_of_type(result.events, EventType.SOWING)[0]
    )


def test_pulpit_does_not_make_ordination_steps_free() -> None:
    scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_plus_ordination_paid_step_001.json")
    step_state = apply_turn_step(scenario.state, scenario.config, steps[0])
    ordain_action = _first(
        legal_actions(step_state, scenario.config),
        lambda candidate: (
            candidate.resolution is TurnResolutionType.ORDINATION
            and candidate.ordination_steps == ("ordain",)
        ),
    )
    result = apply_action(step_state, ordain_action, scenario.config)
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]
    ordination_event = _events_of_type(result.events, EventType.ORDINATION)[0]
    duty_event = _events_of_type(result.events, EventType.DUTY_RESOLUTION)[0]

    assert dict(workforce_event.details)["wheat_paid"] == 0
    assert dict(ordination_event.details)["wheat_paid"] == 1
    assert dict(duty_event.details)["effective_duty_value"] == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_pulpit_is_not_offered_in_the_end_of_turn_window() -> None:
    scenario, _actions, steps = _pulpit_steps("scenarios/pulpit_active_move_serf_001.json")
    result = apply_action(
        scenario.state,
        _first(
            legal_actions(scenario.state, scenario.config),
            lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
        ),
        scenario.config,
    )

    assert result.state.turn_progress.resolution_committed
    assert not any(step.building_id == "pulpit" for step in turn_steps(result.state, scenario.config))
    with pytest.raises(TransitionValidationError, match="only available before resolution"):
        apply_turn_step(result.state, scenario.config, steps[0])
