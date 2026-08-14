from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.merchant import advance_merchant_position, taxation_board_position
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _guild_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    guild_actions = [
        action
        for action in actions
        if action.merchant_advance_building_id == "guild"
    ]
    return scenario, actions, guild_actions


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_own_active_guild_generates_merchant_move_variants() -> None:
    _scenario, actions, guild_actions = _guild_actions(
        "scenarios/guild_active_move_merchant_001.json"
    )

    assert guild_actions
    assert all(action.merchant_advance_building_source == "own_active" for action in guild_actions)
    assert all(action.merchant_advance_building_id == "guild" for action in guild_actions)
    assert any(action.merchant_advance_building_id is None for action in actions)


def test_own_active_guild_works_when_merchant_resource_is_none() -> None:
    scenario = load_scenario("scenarios/guild_active_move_merchant_001.json")
    taxation_state = replace(
        scenario.state,
        # Taxation is a looked-up tile now, not index 0 of the retired six-step path.
        merchant_board_position=taxation_board_position(scenario.config),
    )
    actions = legal_actions(taxation_state, scenario.config)
    guild_actions = [
        action
        for action in actions
        if action.merchant_advance_building_id == "guild"
    ]

    assert guild_actions
    assert all(action.merchant_advance_building_source == "own_active" for action in guild_actions)


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
    actions = legal_actions(state_with_own_guild, scenario.config)
    guild_actions = [
        action
        for action in actions
        if action.merchant_advance_building_id == "guild"
    ]

    assert guild_actions
    assert all(action.merchant_advance_building_source == "own_active" for action in guild_actions)


def test_hired_market_guild_generates_variants_when_payable() -> None:
    _scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_hire_market_move_merchant_001.json"
    )

    assert guild_actions
    assert all(action.merchant_advance_building_source == "market" for action in guild_actions)


def test_hired_opponent_guild_generates_variants_when_payable() -> None:
    _scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_hire_opponent_move_merchant_001.json"
    )

    assert guild_actions
    assert all(action.merchant_advance_building_source == "player_two" for action in guild_actions)


def test_merchant_none_insufficient_donated_and_not_live_block_hired_guild() -> None:
    blocked_paths = (
        "scenarios/guild_merchant_none_no_hire_001.json",
        "scenarios/guild_insufficient_hire_resource_001.json",
        "scenarios/guild_donated_no_modifier_001.json",
        "scenarios/guild_not_live_no_modifier_001.json",
    )
    for path in blocked_paths:
        _scenario, actions, guild_actions = _guild_actions(path)
        assert guild_actions == []
        assert any(action.merchant_advance_building_id is None for action in actions)


def test_apply_own_active_guild_moves_merchant_exactly_one_clockwise_before_sowing() -> None:
    scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_active_move_merchant_001.json"
    )
    action = _first_action(
        guild_actions,
        lambda candidate: (
            candidate.merchant_advance_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    expected_merchant_position = advance_merchant_position(
        scenario.state.merchant_board_position,
        scenario.config,
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "guild",
    )
    merchant_event = _events_of_type(result.events, EventType.MERCHANT_ADVANCE)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    merchant_details = dict(merchant_event.details)

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert merchant_details["from_duty"] == "produce"
    assert merchant_details["to_duty"] == "clerical"
    assert merchant_details["current_resource"] == "silver"
    assert merchant_details["cause"] == "guild"
    assert result.events.index(bonus_event) < result.events.index(merchant_event)
    assert result.events.index(merchant_event) < result.events.index(sowing_event)
    assert result.state.merchant_board_position == expected_merchant_position
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[-1]
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_hired_market_guild_pays_bank_before_merchant_move() -> None:
    scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_hire_market_move_merchant_001.json"
    )
    action = _first_action(
        guild_actions,
        lambda candidate: (
            candidate.merchant_advance_building_source == "market"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _first_action(
        _events_of_type(result.events, EventType.BUILDING_BONUS),
        lambda event: dict(event.details).get("building") == "guild",
    )
    merchant_event = _events_of_type(result.events, EventType.MERCHANT_ADVANCE)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["building_id"] == "guild"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(merchant_event)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0
    assert result.state.merchant_board_position == 2


def test_hired_opponent_guild_pays_owner_before_merchant_move() -> None:
    scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_hire_opponent_move_merchant_001.json"
    )
    action = _first_action(
        guild_actions,
        lambda candidate: (
            candidate.merchant_advance_building_source == "player_two"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "silver"
    # The hire's silver goes to player two and the tithe's silver counter replaces it.
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 1
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1
    assert result.state.merchant_board_position == 3


def test_apply_rejects_hired_guild_when_hire_payment_is_unaffordable() -> None:
    scenario = load_scenario("scenarios/guild_insufficient_hire_resource_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    base_action = _first_action(actions, lambda candidate: candidate.resolution is TurnResolutionType.TITHE)
    invalid_action = replace(
        base_action,
        merchant_advance_building_id="guild",
        merchant_advance_building_source="market",
    )

    with pytest.raises(
        TransitionValidationError,
        match="Guild is unavailable in current state",
    ):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_action_summary_includes_guild_modifier_and_hire_suffix() -> None:
    own_scenario, _own_actions, own_guild_actions = _guild_actions(
        "scenarios/guild_active_move_merchant_001.json"
    )
    own_action = _first_action(
        own_guild_actions,
        lambda candidate: (
            candidate.merchant_advance_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    own_summary = action_summary(own_action, own_scenario.config)
    assert "use building: guild to move merchant +1" in own_summary
    assert "hire building: guild" not in own_summary

    hired_scenario, _hired_actions, hired_guild_actions = _guild_actions(
        "scenarios/guild_hire_market_move_merchant_001.json"
    )
    hired_action = _first_action(
        hired_guild_actions,
        lambda candidate: (
            candidate.merchant_advance_building_source == "market"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    hired_summary = action_summary(hired_action, hired_scenario.config)
    assert "use building: guild to move merchant +1" in hired_summary
    assert "hire building: guild from market" in hired_summary


def test_non_round_ending_turn_with_guild_emits_one_merchant_advance_only() -> None:
    scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_active_move_merchant_001.json"
    )
    action = _first_action(
        guild_actions,
        lambda candidate: candidate.resolution is TurnResolutionType.TITHE,
    )
    result = apply_action(scenario.state, action, scenario.config)
    merchant_events = _events_of_type(result.events, EventType.MERCHANT_ADVANCE)

    assert len(merchant_events) == 1
    assert dict(merchant_events[0].details)["cause"] == "guild"
    assert not _events_of_type(result.events, EventType.ROUND_ADVANCE)


def test_round_ending_turn_with_guild_moves_merchant_twice() -> None:
    scenario, _actions, guild_actions = _guild_actions(
        "scenarios/guild_round_end_moves_merchant_twice_001.json"
    )
    action = _first_action(
        guild_actions,
        lambda candidate: (
            candidate.merchant_advance_building_source == "own_active"
            and candidate.resolution is TurnResolutionType.TITHE
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    merchant_events = _events_of_type(result.events, EventType.MERCHANT_ADVANCE)
    assert len(merchant_events) == 2
    guild_event = _first_action(
        merchant_events,
        lambda event: dict(event.details).get("cause") == "guild",
    )
    round_end_event = _first_action(
        merchant_events,
        lambda event: dict(event.details).get("cause") is None,
    )
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    round_advance_event = _events_of_type(result.events, EventType.ROUND_ADVANCE)[0]

    assert result.events.index(guild_event) < result.events.index(sowing_event)
    assert result.events.index(round_advance_event) < result.events.index(round_end_event)
    assert result.state.merchant_board_position == 2
