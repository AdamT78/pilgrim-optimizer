from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def _wagon_actions(path: str):
    scenario = load_scenario(path)
    actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
    ]
    wagon_actions = [
        action for action in actions if action.free_hire_enabler_building_id == "wagon_yard"
    ]
    return scenario, actions, wagon_actions


def _wagon_target_actions(path: str, *, target_building_id: str, target_source: str):
    scenario, actions, wagon_actions = _wagon_actions(path)
    target_actions = [
        action
        for action in wagon_actions
        if action.free_hire_target_building_id == target_building_id
        and action.free_hire_target_building_source == target_source
    ]
    return scenario, actions, wagon_actions, target_actions


def test_own_active_wagon_yard_generates_market_and_opponent_free_hire_variants() -> None:
    _scenario, _actions, _wagon_actions_all, market_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        target_building_id="brewery",
        target_source="market",
    )
    _scenario2, _actions2, _wagon_actions_all2, opponent_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json",
        target_building_id="brewery",
        target_source="player_two",
    )

    assert market_actions
    assert opponent_actions


def test_wagon_yard_supports_minimum_target_building_set() -> None:
    scenarios = (
        ("scenarios/wagon_yard_active_free_hire_market_grain_store_001.json", "grain_store"),
        ("scenarios/wagon_yard_active_free_hire_market_indulgences_001.json", "indulgences"),
        ("scenarios/wagon_yard_active_free_hire_market_stone_yard_001.json", "stone_yard"),
        ("scenarios/wagon_yard_active_free_hire_market_brewery_001.json", "brewery"),
        ("scenarios/wagon_yard_active_free_hire_market_guild_001.json", "guild"),
        ("scenarios/wagon_yard_active_free_hire_market_pulpit_001.json", "pulpit"),
        ("scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json", "scriptorium"),
        ("scenarios/wagon_yard_active_free_hire_market_customs_house_001.json", "customs_house"),
    )
    for path, target in scenarios:
        _scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
            path,
            target_building_id=target,
            target_source="market",
        )
        assert target_actions


def test_wagon_yard_works_when_merchant_is_on_taxation_or_has_no_hire_resource() -> None:
    for path, source in (
        (
            "scenarios/wagon_yard_active_free_hire_market_taxation_merchant_001.json",
            "market",
        ),
        (
            "scenarios/wagon_yard_active_free_hire_opponent_taxation_merchant_001.json",
            "player_two",
        ),
    ):
        _scenario, actions, _wagon_actions_all, target_actions = _wagon_target_actions(
            path,
            target_building_id="brewery",
            target_source=source,
        )
        paid_hires = [
            action
            for action in actions
            if action.building_conversion_id == "brewery"
            and action.building_conversion_source in {"market", "player_two"}
        ]

        assert target_actions
        assert paid_hires == []


def test_wagon_yard_free_hire_does_not_require_paid_hire_affordability() -> None:
    _scenario, actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        target_building_id="brewery",
        target_source="market",
    )
    paid_hires = [
        action
        for action in actions
        if action.building_conversion_id == "brewery"
        and action.building_conversion_source == "market"
    ]

    assert target_actions
    assert paid_hires == []


def test_market_opponent_donated_not_live_and_no_live_target_prune_wagon_modifier() -> None:
    blocked_paths = (
        "scenarios/wagon_yard_market_not_hireable_001.json",
        "scenarios/wagon_yard_opponent_not_hireable_001.json",
        "scenarios/wagon_yard_donated_no_modifier_001.json",
        "scenarios/wagon_yard_not_live_no_modifier_001.json",
        "scenarios/wagon_yard_no_live_target_no_modifier_001.json",
        "scenarios/wagon_yard_cannot_target_self_001.json",
    )
    for path in blocked_paths:
        _scenario, _actions, wagon_actions = _wagon_actions(path)
        assert wagon_actions == []


def test_wagon_yard_preserves_normal_paid_hire_variants_when_affordable() -> None:
    scenario = load_scenario("scenarios/wagon_yard_active_free_hire_market_brewery_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    paid_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=player_one.resources.add(silver=1),
        ),
    )

    actions = [
        action
        for action in legal_actions(paid_state, scenario.config)
        if isinstance(action, FullTurnAction)
    ]
    paid_variants = [
        action
        for action in actions
        if action.building_conversion_id == "brewery"
        and action.building_conversion_source == "market"
    ]
    free_variants = [
        action
        for action in actions
        if action.free_hire_enabler_building_id == "wagon_yard"
        and action.free_hire_target_building_id == "brewery"
        and action.free_hire_target_building_source == "market"
    ]

    assert paid_variants
    assert free_variants


def test_wagon_yard_action_summary_includes_free_hire_and_target_effect() -> None:
    scenario, _actions, _wagon_actions_all, market_target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        target_building_id="brewery",
        target_source="market",
    )
    market_action = _first_action(
        market_target_actions,
        lambda candidate: candidate.building_conversion_id == "brewery",
    )
    summary = action_summary(market_action, scenario.config)

    assert "use building: wagon_yard to hire brewery from market for free" in summary
    assert "use building: brewery to sell 1 wheat for 2 silver" in summary


def test_wagon_yard_opponent_summary_labels_opponent_source() -> None:
    scenario, _actions, _wagon_actions_all, opponent_target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json",
        target_building_id="brewery",
        target_source="player_two",
    )
    action = _first_action(
        opponent_target_actions,
        lambda candidate: candidate.building_conversion_id == "brewery",
    )
    summary = action_summary(action, scenario.config)

    assert "use building: wagon_yard to hire brewery from player_two for free" in summary
    assert "use building: brewery to sell 1 wheat for 2 silver" in summary


def test_wagon_yard_market_brewery_hire_cost_is_zero_and_effect_applies() -> None:
    scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        target_building_id="brewery",
        target_source="market",
    )
    action = _first_action(
        target_actions,
        lambda candidate: candidate.building_conversion_id == "brewery",
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "brewery",
    )
    sow_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "brewery"
    assert hired_details["source"] == "market"
    assert hired_details["resource"] == "none"
    assert hired_details["amount"] == 0
    assert hired_details["payee"] == "none"
    assert hired_details["free_with_wagon_yard"] is True
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(sow_event)


def test_wagon_yard_opponent_brewery_does_not_pay_owner() -> None:
    scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json",
        target_building_id="brewery",
        target_source="player_two",
    )
    action = _first_action(
        target_actions,
        lambda candidate: candidate.building_conversion_id == "brewery",
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "none"
    assert hired_details["resource"] == "none"
    assert hired_details["amount"] == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 0


def test_wagon_yard_stone_yard_and_conversion_parameters_are_preserved() -> None:
    scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_stone_yard_001.json",
        target_building_id="stone_yard",
        target_source="market",
    )
    action = _first_action(
        target_actions,
        lambda candidate: (
            candidate.building_conversion_direction == "sell_stone" and candidate.building_conversion_amount == 1
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.stone == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1


def test_wagon_yard_guild_moves_merchant_and_pays_no_hire_fee() -> None:
    scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_guild_001.json",
        target_building_id="guild",
        target_source="market",
    )
    action = _first_action(
        target_actions,
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["building_id"] == "guild"
    assert hired_details["amount"] == 0
    assert result.state.merchant_position == 3
    assert any(
        dict(event.details).get("building") == "guild"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )


def test_wagon_yard_pulpit_moves_serf_and_pays_no_hire_fee() -> None:
    scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_pulpit_001.json",
        target_building_id="pulpit",
        target_source="market",
    )
    action = _first_action(
        target_actions,
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)
    workforce_event = _events_of_type(result.events, EventType.WORKFORCE_MOVE)[0]

    assert hired_details["building_id"] == "pulpit"
    assert hired_details["amount"] == 0
    assert dict(workforce_event.details)["wheat_paid"] == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).workforce.village == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).workforce.abbey == 1


def test_wagon_yard_scriptorium_and_customs_house_effects_resolve() -> None:
    scriptorium_scenario, _actions, _wagon_actions_all, scriptorium_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json",
        target_building_id="scriptorium",
        target_source="market",
    )
    scriptorium_action = scriptorium_actions[0]
    scriptorium_result = apply_action(
        scriptorium_scenario.state,
        scriptorium_action,
        scriptorium_scenario.config,
    )

    customs_scenario, _actions2, _wagon_actions_all2, customs_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_customs_house_001.json",
        target_building_id="customs_house",
        target_source="market",
    )
    customs_action = _first_action(
        customs_actions,
        lambda candidate: (
            candidate.resolution is TurnResolutionType.TAXATION
            and candidate.taxation_step1_resource == "wheat"
            and candidate.taxation_step2_resources == ("stone", "silver")
        ),
    )
    customs_result = apply_action(
        customs_scenario.state,
        customs_action,
        customs_scenario.config,
    )
    customs_duty = _events_of_type(customs_result.events, EventType.DUTY_RESOLUTION)[0]

    assert any(
        dict(event.details).get("building") == "scriptorium"
        for event in _events_of_type(scriptorium_result.events, EventType.BUILDING_BONUS)
    )
    assert any(
        dict(event.details).get("building") == "customs_house"
        for event in _events_of_type(customs_result.events, EventType.BUILDING_BONUS)
    )
    assert dict(customs_duty.details)["strength"] == "majority"


def test_apply_rejects_invalid_wagon_yard_sources_and_targets() -> None:
    scenario, actions, _wagon_actions_all = _wagon_actions(
        "scenarios/wagon_yard_market_not_hireable_001.json"
    )
    base_action = _first_action(
        actions,
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    missing_wagon = replace(
        base_action,
        free_hire_enabler_building_id="wagon_yard",
        free_hire_target_building_id="brewery",
        free_hire_target_building_source="market",
        building_conversion_id="brewery",
        building_conversion_source="own_active",
        building_conversion_direction="sell_wheat_for_silver",
        building_conversion_amount=1,
    )
    self_target = replace(
        missing_wagon,
        free_hire_target_building_id="wagon_yard",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Wagon Yard is unavailable in current state",
    ):
        apply_action(scenario.state, missing_wagon, scenario.config)
    with pytest.raises(
        TransitionValidationError,
        match="Wagon Yard free-hire target building is unsupported",
    ):
        apply_action(scenario.state, self_target, scenario.config)


def test_apply_rejects_unavailable_free_hire_target_and_own_source() -> None:
    scenario, actions, _wagon_actions_all = _wagon_actions(
        "scenarios/wagon_yard_no_live_target_no_modifier_001.json"
    )
    base_action = _first_action(
        actions,
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    unavailable_target = replace(
        base_action,
        free_hire_enabler_building_id="wagon_yard",
        free_hire_target_building_id="brewery",
        free_hire_target_building_source="market",
        building_conversion_id="brewery",
        building_conversion_source="own_active",
        building_conversion_direction="sell_wheat_for_silver",
        building_conversion_amount=1,
    )
    own_source = replace(
        unavailable_target,
        free_hire_target_building_source="player_one",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Wagon Yard free-hire target source is unavailable in current state",
    ):
        apply_action(scenario.state, unavailable_target, scenario.config)
    with pytest.raises(
        TransitionValidationError,
        match="Wagon Yard free-hire target source cannot be own active building",
    ):
        apply_action(scenario.state, own_source, scenario.config)


def test_wagon_yard_hire_cost_remains_zero_even_when_merchant_resource_exists() -> None:
    scenario, _actions, _wagon_actions_all, target_actions = _wagon_target_actions(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        target_building_id="brewery",
        target_source="market",
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    resource_rich_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, resources=player_one.resources.add(silver=1)),
    )
    action = _first_action(
        [
            candidate
            for candidate in legal_actions(resource_rich_state, scenario.config)
            if isinstance(candidate, FullTurnAction)
        ],
        lambda candidate: (
            candidate.free_hire_enabler_building_id == "wagon_yard"
            and candidate.free_hire_target_building_id == "brewery"
            and candidate.building_conversion_id == "brewery"
        ),
    )
    result = apply_action(resource_rich_state, action, scenario.config)

    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 3
