from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _event_index(events, event_type: EventType) -> int:
    for index, event in enumerate(events):
        if event.event_type is event_type:
            return index
    raise AssertionError(f"Missing event type: {event_type}")


def _round_ending_tithe_action(path: str):
    scenario = load_scenario(path)
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TITHE
    )
    return scenario, action


def test_trade_routes_count_defaults_to_zero_for_legacy_scenarios() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    assert scenario.state.player_state(PlayerId.PLAYER_ONE).trade_routes_count == 0
    assert scenario.state.player_state(PlayerId.PLAYER_TWO).trade_routes_count == 0


def test_round_end_trade_route_income_basic_gain_and_order() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_basic_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)

    income_events = _events_of_type(result.events, EventType.TRADE_ROUTE_INCOME)
    assert len(income_events) == 1
    income_details = dict(income_events[0].details)
    assert income_details["player"] == "player_one"
    assert income_details["resource"] == "wheat"
    assert income_details["amount"] == 1
    assert income_details["trade_routes"] == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 1

    merchant_index = _event_index(result.events, EventType.MERCHANT_ADVANCE)
    income_index = _event_index(result.events, EventType.TRADE_ROUTE_INCOME)
    start_player_index = _event_index(result.events, EventType.START_PLAYER_SELECTION)
    assert merchant_index < income_index < start_player_index


def test_round_end_trade_route_income_multiple_routes_gains_scaled_amount() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_multiple_routes_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    income_details = dict(_events_of_type(result.events, EventType.TRADE_ROUTE_INCOME)[0].details)

    assert income_details["amount"] == 3
    assert income_details["trade_routes"] == 3
    assert income_details["resource"] == "wheat"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 3


def test_round_end_trade_route_income_multiple_players_emits_in_player_order() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_multiple_players_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    income_events = _events_of_type(result.events, EventType.TRADE_ROUTE_INCOME)

    assert len(income_events) == 2
    first_details = dict(income_events[0].details)
    second_details = dict(income_events[1].details)
    assert first_details["player"] == "player_one"
    assert first_details["amount"] == 2
    assert second_details["player"] == "player_two"
    assert second_details["amount"] == 1
    assert first_details["resource"] == "silver"
    assert second_details["resource"] == "silver"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 2
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.silver == 1


def test_round_end_trade_route_income_zero_routes_emits_no_income_event() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_basic_001.json"
    )
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    zero_routes_state = (
        scenario.state.with_player_state(
            PlayerId.PLAYER_ONE,
            replace(player_one, trade_routes_count=0),
        ).with_player_state(
            PlayerId.PLAYER_TWO,
            replace(player_two, trade_routes_count=0),
        )
    )

    result = apply_action(zero_routes_state, action, scenario.config)
    assert _events_of_type(result.events, EventType.TRADE_ROUTE_INCOME) == []


def test_round_end_trade_route_income_resource_cap_applies_before_income() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_resource_cap_order_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    cap_event = _events_of_type(result.events, EventType.EXCESS_RESOURCE_CAP)[0]
    income_event = _events_of_type(result.events, EventType.TRADE_ROUTE_INCOME)[0]

    assert dict(cap_event.details)["wheat_before"] == 7
    assert dict(cap_event.details)["wheat_after"] == 6
    assert dict(income_event.details)["resource"] == "wheat"
    assert dict(income_event.details)["amount"] == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 7
    assert result.events.index(cap_event) < result.events.index(income_event)


def test_round_end_trade_route_income_skips_when_merchant_resource_none() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_basic_001.json"
    )
    state_with_taxation_after_advance = scenario.state.with_merchant_position(5)
    result = apply_action(state_with_taxation_after_advance, action, scenario.config)

    assert _events_of_type(result.events, EventType.MERCHANT_ADVANCE)
    assert _events_of_type(result.events, EventType.TRADE_ROUTE_INCOME) == []
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0


def test_round_end_trade_route_income_not_emitted_when_game_end_stops_pipeline() -> None:
    scenario = load_scenario("scenarios/game_end_nw_site_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    state_with_routes = (
        scenario.state.with_player_state(
            PlayerId.PLAYER_ONE,
            replace(player_one, trade_routes_count=3),
        ).with_player_state(
            PlayerId.PLAYER_TWO,
            replace(player_two, trade_routes_count=2),
        )
    )
    result = apply_action(state_with_routes, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert result.state.game_over is True
    assert EventType.GAME_END in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.TRADE_ROUTE_INCOME not in event_types


def test_trade_route_income_uses_merchant_position_after_two_prior_guild_moves_and_round_end_advance() -> None:
    # This scenario starts after both players have already used Guild this round.
    # The test verifies round-end Merchant advance and trade-route income from that resulting state.
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_after_two_guild_moves_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    merchant_event = _events_of_type(result.events, EventType.MERCHANT_ADVANCE)[0]
    income_events = _events_of_type(result.events, EventType.TRADE_ROUTE_INCOME)

    assert dict(merchant_event.details)["from_duty"] == "clerical"
    assert dict(merchant_event.details)["to_duty"] == "alms"
    assert dict(merchant_event.details)["current_resource"] == "wheat"
    assert len(income_events) == 2
    assert dict(income_events[0].details)["player"] == "player_one"
    assert dict(income_events[0].details)["resource"] == "wheat"
    assert dict(income_events[0].details)["amount"] == 2
    assert dict(income_events[1].details)["player"] == "player_two"
    assert dict(income_events[1].details)["resource"] == "wheat"
    assert dict(income_events[1].details)["amount"] == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.silver == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1

    merchant_index = _event_index(result.events, EventType.MERCHANT_ADVANCE)
    income_index = _event_index(result.events, EventType.TRADE_ROUTE_INCOME)
    start_player_index = _event_index(result.events, EventType.START_PLAYER_SELECTION)
    assert merchant_index < income_index < start_player_index
