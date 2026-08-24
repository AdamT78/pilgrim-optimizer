from __future__ import annotations

import dataclasses
from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, EndTurnAction, FullTurnAction, action_id
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.merchant import (
    advance_merchant_position,
    current_merchant_resource,
    taxation_board_position,
)
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _guild_step(path: str) -> tuple[object, BuildingActivationStep]:
    scenario = load_scenario(path)
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "guild"
    )
    return scenario, step


def _tithe_action(state, config):
    return next(
        action
        for action in legal_actions(state, config)
        if isinstance(action, FullTurnAction) and action.resolution is TurnResolutionType.TITHE
    )


def test_activating_own_guild_moves_merchant_and_marks_it_used() -> None:
    scenario, step = _guild_step("scenarios/guild_active_move_merchant_001.json")

    updated = apply_turn_step(scenario.state, scenario.config, step)
    merchant_events = _events_of_type(updated.turn_progress.events, EventType.MERCHANT_ADVANCE)

    assert updated.merchant_board_position == advance_merchant_position(
        scenario.state.merchant_board_position, scenario.config
    )
    assert updated.turn_progress.used_buildings == frozenset({"guild"})
    assert len(merchant_events) == 1
    assert dict(merchant_events[0].details)["cause"] == "guild"


def test_guild_cannot_be_activated_twice_in_one_turn() -> None:
    scenario, step = _guild_step("scenarios/guild_active_move_merchant_001.json")
    updated = apply_turn_step(scenario.state, scenario.config, step)

    with pytest.raises(TransitionValidationError, match="already used"):
        apply_turn_step(updated, scenario.config, step)


def test_hiring_guild_from_market_uses_the_pre_move_merchant_counter() -> None:
    scenario, step = _guild_step("scenarios/guild_hire_market_move_merchant_001.json")
    before = scenario.state.player_state(PlayerId.PLAYER_ONE).resources

    updated = apply_turn_step(scenario.state, scenario.config, step)
    hired_event = _events_of_type(updated.turn_progress.events, EventType.BUILDING_HIRED)[0]
    hired = dict(hired_event.details)

    assert step.source == "market"
    assert step.hire_payment == "wheat"
    assert hired["building_id"] == "guild"
    assert hired["source"] == "market"
    assert hired["resource"] == "wheat"
    assert updated.player_state(PlayerId.PLAYER_ONE).resources.wheat == before.wheat - 1
    assert updated.merchant_board_position == advance_merchant_position(
        scenario.state.merchant_board_position, scenario.config
    )


def test_own_active_guild_source_priority_blocks_hired_variants() -> None:
    scenario = load_scenario("scenarios/guild_hire_market_move_merchant_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state_with_own_guild = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            player_board_slots=replace(
                player_one.player_board_slots,
                active_buildings=("guild",),
            ),
        ),
    )
    guild_steps = [
        step
        for step in turn_steps(state_with_own_guild, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "guild"
    ]

    assert [(step.source, step.hire_payment) for step in guild_steps] == [("own_active", None)]


def test_hired_opponent_guild_pays_owner_before_merchant_move() -> None:
    scenario, step = _guild_step("scenarios/guild_hire_opponent_move_merchant_001.json")
    before_owner = scenario.state.player_state(PlayerId.PLAYER_TWO).resources

    updated = apply_turn_step(scenario.state, scenario.config, step)
    hired_event = _events_of_type(updated.turn_progress.events, EventType.BUILDING_HIRED)[0]
    merchant_event = _events_of_type(updated.turn_progress.events, EventType.MERCHANT_ADVANCE)[0]
    hired = dict(hired_event.details)

    assert step.source == "player_two"
    assert step.hire_payment == current_merchant_resource(scenario.state, scenario.config)
    assert hired["payee"] == "player_two"
    assert hired["resource"] == "silver"
    assert updated.player_state(PlayerId.PLAYER_TWO).resources.silver == before_owner.silver + 1
    assert updated.turn_progress.events.index(hired_event) < updated.turn_progress.events.index(
        merchant_event
    )
    assert dict(merchant_event.details)["current_resource"] == "stone"


def test_apply_rejects_hired_guild_when_hire_payment_is_unaffordable() -> None:
    scenario = load_scenario("scenarios/guild_insufficient_hire_resource_001.json")
    unavailable = BuildingActivationStep(
        building_id="guild",
        source="market",
        hire_payment=current_merchant_resource(scenario.state, scenario.config),
    )

    assert not [
        step
        for step in turn_steps(scenario.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "guild"
    ]
    with pytest.raises(TransitionValidationError, match="Guild is unavailable"):
        apply_turn_step(scenario.state, scenario.config, unavailable)


def test_own_active_guild_works_when_merchant_resource_is_none() -> None:
    scenario = load_scenario("scenarios/guild_active_move_merchant_001.json")
    taxation_state = replace(
        scenario.state,
        merchant_board_position=taxation_board_position(scenario.config),
    )
    guild_steps = [
        step
        for step in turn_steps(taxation_state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "guild"
    ]

    assert current_merchant_resource(taxation_state, scenario.config) is None
    assert [(candidate.source, candidate.hire_payment) for candidate in guild_steps] == [
        ("own_active", None)
    ]
    updated = apply_turn_step(taxation_state, scenario.config, guild_steps[0])
    assert _events_of_type(updated.turn_progress.events, EventType.BUILDING_HIRED) == []
    assert updated.merchant_board_position == advance_merchant_position(
        taxation_state.merchant_board_position, scenario.config
    )


def test_non_round_ending_turn_with_guild_emits_one_merchant_advance_only() -> None:
    scenario, step = _guild_step("scenarios/guild_active_move_merchant_001.json")
    after_guild = apply_turn_step(scenario.state, scenario.config, step)
    resolution = apply_action(
        after_guild,
        _tithe_action(after_guild, scenario.config),
        scenario.config,
    )
    merchant_events = _events_of_type(resolution.events, EventType.MERCHANT_ADVANCE)

    assert len(merchant_events) == 1
    assert dict(merchant_events[0].details)["cause"] == "guild"
    assert _events_of_type(resolution.events, EventType.ROUND_ADVANCE) == []


def test_guild_is_available_in_the_end_of_turn_window() -> None:
    scenario, beginning_step = _guild_step("scenarios/guild_active_move_merchant_001.json")
    resolution = apply_action(
        scenario.state,
        _tithe_action(scenario.state, scenario.config),
        scenario.config,
    )

    end_step = next(
        step
        for step in turn_steps(resolution.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "guild"
    )

    assert resolution.state.turn_progress.resolution_committed is True
    assert end_step == beginning_step
    assert legal_actions(resolution.state, scenario.config) == (EndTurnAction(),)


def test_full_turn_actions_do_not_carry_guild_merchant_advance_fields() -> None:
    scenario = load_scenario("scenarios/guild_active_move_merchant_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    field_names = {field.name for field in dataclasses.fields(FullTurnAction)}

    assert "merchant_advance_building_id" not in field_names
    assert "merchant_advance_building_source" not in field_names
    assert all("merchant_advance" not in action_id(action) for action in actions)


def test_round_ending_turn_with_committed_guild_moves_merchant_twice() -> None:
    scenario, step = _guild_step("scenarios/guild_round_end_moves_merchant_twice_001.json")
    after_guild = apply_turn_step(scenario.state, scenario.config, step)
    resolution = apply_action(
        after_guild,
        _tithe_action(after_guild, scenario.config),
        scenario.config,
    )
    passed = apply_action(resolution.state, EndTurnAction(), scenario.config)
    merchant_events = _events_of_type(
        (*resolution.events, *passed.events),
        EventType.MERCHANT_ADVANCE,
    )

    assert len(merchant_events) == 2
    assert [dict(event.details).get("cause") for event in merchant_events] == ["guild", None]
    assert passed.state.merchant_board_position == 2
