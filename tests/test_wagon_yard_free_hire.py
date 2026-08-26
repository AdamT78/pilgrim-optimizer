from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, FullTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import (
    TransitionValidationError,
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_steps,
)


def _events(events, event_type):
    return [event for event in events if event.event_type is event_type]


def _wagon_actions(path: str, target: str):
    scenario = load_scenario(path)
    actions = tuple(legal_actions(scenario.state, scenario.config))
    return scenario, tuple(
        action for action in actions
        if isinstance(action, FullTurnAction)
        and action.free_hire_enabler_building_id == "wagon_yard"
        and action.free_hire_target_building_id == target
    )


def _wagon_free_activation(path: str, target: str):
    scenario = load_scenario(path)
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == target
    )
    assert step.hire_payment is None
    return scenario, apply_turn_step(scenario.state, scenario.config, step)


def _first(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_wagon_yard_generates_market_and_opponent_free_hire_variants() -> None:
    _scenario, market = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    opponent_scenario, opponent_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_opponent_customs_house_001.json",
        "customs_house",
    )
    assert market
    assert {action.free_hire_target_building_source for action in market} == {"market"}
    hired = _events(opponent_state.turn_progress.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["source"] == "player_two"
    assert dict(hired.details)["amount"] == 0
    assert any(
        action.taxation_majority_building_id == "customs_house"
        for action in legal_actions(opponent_state, opponent_scenario.config)
        if isinstance(action, FullTurnAction)
    )


def test_wagon_yard_supports_minimum_target_building_set() -> None:
    _scenario, guild_actions = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    assert guild_actions
    _scenario, pulpit_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_market_pulpit_001.json", "pulpit"
    )
    assert "pulpit" in pulpit_state.turn_progress.used_buildings
    for path, target in (
        ("scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json", "bank"),
        ("scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json", "scriptorium"),
        ("scenarios/wagon_yard_active_free_hire_market_customs_house_001.json", "customs_house"),
    ):
        _scenario, state = _wagon_free_activation(path, target)
        assert target in state.turn_progress.used_buildings


def test_wagon_yard_works_when_merchant_is_on_taxation_or_has_no_hire_resource() -> None:
    for path, target in (
        ("scenarios/wagon_yard_active_free_hire_market_customs_house_001.json", "customs_house"),
        ("scenarios/wagon_yard_active_free_hire_opponent_scriptorium_001.json", "scriptorium"),
    ):
        _scenario, state = _wagon_free_activation(path, target)
        hired = _events(state.turn_progress.events, EventType.BUILDING_HIRED)[0]
        assert dict(hired.details)["amount"] == 0


def test_wagon_yard_free_hire_does_not_require_paid_hire_affordability() -> None:
    scenario, actions = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    assert actions
    assert all(action.hired_building_id is None for action in actions)
    assert scenario.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0


def test_wagon_yard_preserves_normal_paid_hire_variants_when_affordable() -> None:
    scenario = load_scenario("scenarios/wagon_yard_active_free_hire_market_guild_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    paid_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=player.resources.add(silver=2, wheat=1)),
    )
    actions = tuple(legal_actions(paid_state, scenario.config))
    paid = [
        step
        for step in turn_steps(paid_state, scenario.config)
        if isinstance(step, BuildingActivationStep)
        and step.building_id == "guild"
        and step.source == "market"
    ]
    free = [
        action for action in actions
        if isinstance(action, FullTurnAction)
        and action.free_hire_enabler_building_id == "wagon_yard"
        and action.free_hire_target_building_id == "guild"
    ]
    assert paid
    assert free


def test_wagon_yard_action_summary_includes_free_hire_and_target_effect() -> None:
    scenario, actions = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    summary = action_summary(actions[0], scenario.config)
    assert "use building: wagon_yard to hire guild from market for free" in summary
    assert "use building: guild to move merchant +1" not in summary


def test_wagon_yard_opponent_free_activation_labels_opponent_source() -> None:
    scenario = load_scenario("scenarios/wagon_yard_active_free_hire_opponent_customs_house_001.json")
    step = next(
        step
        for step in turn_steps(scenario.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "customs_house"
    )

    assert step.source == "player_two"
    assert step.hire_payment is None


def test_wagon_yard_market_free_hire_cost_is_zero_and_effect_applies() -> None:
    scenario, actions = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    action = _first(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    result = apply_action(scenario.state, action, scenario.config)
    hired = _events(result.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["amount"] == 0
    assert dict(hired.details)["payee"] == "none"
    assert result.state.merchant_board_position == scenario.state.merchant_board_position


def test_wagon_yard_opponent_free_hire_does_not_pay_owner() -> None:
    _scenario, state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_opponent_customs_house_001.json",
        "customs_house",
    )
    hired = _events(state.turn_progress.events, EventType.BUILDING_HIRED)[0]
    assert dict(hired.details)["payee"] == "none"
    assert dict(hired.details)["amount"] == 0


def test_wagon_yard_hire_cost_remains_zero_even_when_merchant_resource_exists() -> None:
    scenario = load_scenario("scenarios/wagon_yard_active_free_hire_market_guild_001.json")
    player = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player, resources=player.resources.add(wheat=1)),
    )
    action = _first(
        [candidate for candidate in legal_actions(state, scenario.config) if isinstance(candidate, FullTurnAction)],
        lambda candidate: candidate.free_hire_enabler_building_id == "wagon_yard"
        and candidate.free_hire_target_building_id == "guild",
    )
    result = apply_action(state, action, scenario.config)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == player.resources.wheat + 1


def test_wagon_yard_keeps_non_conversion_target_effects() -> None:
    _scenario, guild_actions = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    assert guild_actions
    _scenario, pulpit_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_market_pulpit_001.json", "pulpit"
    )
    assert "pulpit" in pulpit_state.turn_progress.used_buildings
    for path, target in (
        ("scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json", "scriptorium"),
        ("scenarios/wagon_yard_active_free_hire_market_customs_house_001.json", "customs_house"),
    ):
        _scenario, state = _wagon_free_activation(path, target)
        assert target in state.turn_progress.used_buildings


def test_wagon_yard_hiring_guild_does_not_activate_it_inside_the_full_turn() -> None:
    scenario, actions = _wagon_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"
    )
    action = next(action for action in actions if action.resolution is TurnResolutionType.TITHE)
    result = apply_action(scenario.state, action, scenario.config)
    hired = dict(_events(result.events, EventType.BUILDING_HIRED)[0].details)
    assert hired["building_id"] == "guild"
    assert hired["amount"] == 0
    assert result.state.merchant_board_position == scenario.state.merchant_board_position
    assert not any(
        dict(event.details).get("building") == "guild"
        for event in _events(result.events, EventType.BUILDING_BONUS)
    )
    guild_step = next(
        step
        for step in turn_steps(result.state, scenario.config)
        if isinstance(step, BuildingActivationStep) and step.building_id == "guild"
    )
    activated = apply_turn_step(result.state, scenario.config, guild_step)
    assert activated.merchant_board_position != result.state.merchant_board_position


def test_wagon_yard_pulpit_and_customs_house_effects_resolve() -> None:
    _scenario, pulpit_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_market_pulpit_001.json", "pulpit"
    )
    pulpit_hire = _events(pulpit_state.turn_progress.events, EventType.BUILDING_HIRED)[0]
    assert _events(pulpit_state.turn_progress.events, EventType.WORKFORCE_MOVE)
    assert dict(pulpit_hire.details)["amount"] == 0
    assert dict(pulpit_hire.details)["payee"] == "none"

    scenario, customs_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_market_customs_house_001.json", "customs_house"
    )
    action = next(
        action
        for action in legal_actions(customs_state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.resolution is TurnResolutionType.TAXATION
        and action.taxation_majority_building_id == "customs_house"
    )
    result = apply_action(customs_state, action, scenario.config)
    assert dict(_events(result.events, EventType.DUTY_RESOLUTION)[0].details)["strength"] == "majority"


def test_wagon_yard_scriptorium_and_customs_house_effects_resolve() -> None:
    scriptorium, scriptorium_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json", "scriptorium"
    )
    scriptorium_action = next(
        action
        for action in legal_actions(scriptorium_state, scriptorium.config)
        if isinstance(action, FullTurnAction) and action.effective_acolyte_building_id == "scriptorium"
    )
    scriptorium_result = apply_action(scriptorium_state, scriptorium_action, scriptorium.config)
    assert any(
        dict(event.details).get("building") == "scriptorium"
        for event in _events(scriptorium_result.events, EventType.BUILDING_BONUS)
    )

    customs, customs_state = _wagon_free_activation(
        "scenarios/wagon_yard_active_free_hire_market_customs_house_001.json", "customs_house"
    )
    customs_action = _first(
        [
            action
            for action in legal_actions(customs_state, customs.config)
            if isinstance(action, FullTurnAction)
        ],
        lambda action: action.resolution is TurnResolutionType.TAXATION
        and action.taxation_majority_building_id == "customs_house",
    )
    customs_result = apply_action(customs_state, customs_action, customs.config)
    assert any(
        dict(event.details).get("building") == "customs_house"
        for event in _events(customs_result.events, EventType.BUILDING_BONUS)
    )


def test_blocked_wagon_sources_produce_no_wagon_actions() -> None:
    for path in (
        "scenarios/wagon_yard_market_not_hireable_001.json",
        "scenarios/wagon_yard_opponent_not_hireable_001.json",
        "scenarios/wagon_yard_donated_no_modifier_001.json",
        "scenarios/wagon_yard_not_live_no_modifier_001.json",
        "scenarios/wagon_yard_no_live_target_no_modifier_001.json",
        "scenarios/wagon_yard_cannot_target_self_001.json",
    ):
        scenario = load_scenario(path)
        assert not any(
            isinstance(action, FullTurnAction)
            and action.free_hire_enabler_building_id == "wagon_yard"
            for action in legal_actions(scenario.state, scenario.config)
        )


def test_invalid_wagon_yard_target_is_rejected_without_conversion_fields() -> None:
    scenario = load_scenario("scenarios/wagon_yard_market_not_hireable_001.json")
    action = next(action for action in legal_actions(scenario.state, scenario.config)
                  if isinstance(action, FullTurnAction) and action.resolution is TurnResolutionType.TITHE)
    invalid = replace(
        action,
        free_hire_enabler_building_id="wagon_yard",
        free_hire_target_building_id="wagon_yard",
        free_hire_target_building_source="market",
    )
    with pytest.raises(TransitionValidationError):
        apply_action(scenario.state, invalid, scenario.config)


def test_apply_rejects_unavailable_free_hire_target_and_own_source() -> None:
    scenario = load_scenario("scenarios/wagon_yard_no_live_target_no_modifier_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction) and action.resolution is TurnResolutionType.TITHE
    )
    unavailable = replace(
        action,
        free_hire_enabler_building_id="wagon_yard",
        free_hire_target_building_id="brewery",
        free_hire_target_building_source="market",
    )
    own_source = replace(unavailable, free_hire_target_building_source="player_one")
    with pytest.raises(
        TransitionValidationError,
        match="Wagon Yard free-hire target source is unavailable in current state",
    ):
        apply_action(scenario.state, unavailable, scenario.config)
    with pytest.raises(
        TransitionValidationError,
        match="Wagon Yard free-hire target source cannot be own active building",
    ):
        apply_action(scenario.state, own_source, scenario.config)
