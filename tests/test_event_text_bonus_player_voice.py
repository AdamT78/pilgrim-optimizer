"""Player-voice lines for number-changing bonus events and ordination steps."""

from __future__ import annotations

import pytest

from pilgrim.io.event_text import format_event_for_players
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.rules.transition import apply_action, legal_actions


@pytest.fixture(scope="module")
def config():
    return load_scenario("scenarios/play_view_reference_4p_001.json").config


def _event(event_type: EventType, **details) -> GameEvent:
    return GameEvent(
        event_type=event_type,
        actor=PlayerId.PLAYER_ONE,
        action_id="test",
        details=make_event_details(**details),
    )


def _player_lines(events, config) -> list[str]:
    return [
        line
        for event in events
        if (line := format_event_for_players(event, config)) is not None
    ]


def test_ordination_mill_cost_line_uses_payment_wording_on_real_action() -> None:
    scenario = load_scenario("scenarios/ordination_mill_active_three_steps_one_wheat_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.ORDINATION
        and candidate.ordination_steps == ("ordain", "mission")
    )
    result = apply_action(scenario.state, action, scenario.config)
    lines = _player_lines(result.events, scenario.config)
    assert "player_one paid 0 wheat for Ordination — 2 due, 2 waived by the Mill." in lines


def test_produce_fields_and_well_share_one_player_line_on_real_action() -> None:
    scenario = load_scenario("scenarios/produce_wheat_fields_and_well_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    result = apply_action(scenario.state, action, scenario.config)
    lines = _player_lines(result.events, scenario.config)
    expected = "player_one gained 4 wheat at Produce — 2 for the duty, 1 from the Fields, 1 from the Well."
    assert lines.count(expected) == 1
    assert all("BUILDING_BONUS:" not in line for line in lines)


def test_ordination_step_lines_follow_the_current_player_wording_on_real_action() -> None:
    scenario = load_scenario("scenarios/ordination_mill_active_three_steps_one_wheat_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.ORDINATION
        and candidate.ordination_steps == ("ordain", "mission")
    )
    result = apply_action(scenario.state, action, scenario.config)
    lines = _player_lines(result.events, scenario.config)
    assert "player_one ordained 1 serf into the Abbey." in lines
    assert "player_one sent 1 acolyte on mission to the City." in lines


def test_zero_delta_bonus_event_produces_no_player_clause(config) -> None:
    fields_zero = _event(
        EventType.SPECIAL_ACTIVITY_BONUS,
        activity="fields",
        action="produce_wheat",
        wheat_bonus=0,
        base_amount=2,
        total_amount=2,
    )
    mill_zero = _event(
        EventType.BUILDING_BONUS,
        building="mill",
        action="ordination",
        required_wheat=2,
        wheat_waived=0,
        actual_wheat_spent=2,
    )
    assert format_event_for_players(fields_zero, config) is None
    assert format_event_for_players(mill_zero, config) == "player_one paid 2 wheat for Ordination."
