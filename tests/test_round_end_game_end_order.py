from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _round_ending_tithe_action(path: str):
    scenario = load_scenario(path)
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TITHE
    )
    return scenario, action


def _event_index(events, event_type: EventType) -> int:
    for index, event in enumerate(events):
        if event.event_type is event_type:
            return index
    raise AssertionError(f"Missing event type: {event_type}")


def test_final_nw_pilgrimage_resolves_alms_before_game_end() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_final_pilgrimage_alms_before_game_end_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert result.state.game_over is True
    assert EventType.SHIP_ADVANCE in event_types
    assert EventType.ROUND_ADVANCE in event_types
    assert EventType.ALMS_SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.GAME_END in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.TRADE_ROUTE_INCOME not in event_types
    assert EventType.START_PLAYER_SELECTION not in event_types

    assert _event_index(result.events, EventType.SHIP_ADVANCE) < _event_index(
        result.events,
        EventType.ROUND_ADVANCE,
    ) < _event_index(result.events, EventType.ALMS_SEASON_END) < _event_index(
        result.events,
        EventType.ALMS_SEASON_REWARD,
    ) < _event_index(result.events, EventType.ALMS_RESET) < _event_index(
        result.events,
        EventType.GAME_END,
    )


def test_non_final_pilgrimage_continues_to_merchant_trade_route_and_start_player() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_non_final_pilgrimage_continues_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.GAME_END not in event_types
    assert EventType.ALMS_SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.TRADE_ROUTE_INCOME in event_types
    assert EventType.START_PLAYER_SELECTION in event_types

    assert _event_index(result.events, EventType.SHIP_ADVANCE) < _event_index(
        result.events,
        EventType.ROUND_ADVANCE,
    ) < _event_index(result.events, EventType.ALMS_SEASON_END) < _event_index(
        result.events,
        EventType.ALMS_SEASON_REWARD,
    ) < _event_index(result.events, EventType.ALMS_RESET) < _event_index(
        result.events,
        EventType.MERCHANT_ADVANCE,
    ) < _event_index(result.events, EventType.TRADE_ROUTE_INCOME) < _event_index(
        result.events,
        EventType.START_PLAYER_SELECTION,
    )


def test_non_pilgrimage_round_end_order_is_unchanged() -> None:
    scenario, action = _round_ending_tithe_action(
        "scenarios/round_end_trade_route_income_basic_001.json"
    )
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.ALMS_SEASON_END not in event_types
    assert EventType.GAME_END not in event_types
    assert _event_index(result.events, EventType.SHIP_ADVANCE) < _event_index(
        result.events,
        EventType.ROUND_ADVANCE,
    ) < _event_index(result.events, EventType.MERCHANT_ADVANCE) < _event_index(
        result.events,
        EventType.TRADE_ROUTE_INCOME,
    ) < _event_index(result.events, EventType.START_PLAYER_SELECTION)
