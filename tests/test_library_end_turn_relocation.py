from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _library_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    return scenario, [action for action in actions if action.end_turn_building_id == "library"]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_library_active_generates_city_to_duty_and_city_to_abbey_variants() -> None:
    scenario, actions = _library_actions("scenarios/library_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    duty_positions = set(scenario.config.duty_positions())

    assert actions
    assert all(action.end_turn_building_source == "own_active" for action in actions)
    assert all(action.end_turn_relocation_from == city for action in actions)
    assert any(action.end_turn_relocation_to == "abbey" for action in actions)
    assert any(action.end_turn_relocation_to in duty_positions for action in actions)


def test_library_market_hire_generates_variants_when_payable() -> None:
    _scenario, actions = _library_actions("scenarios/library_hire_market_city_to_duty_001.json")

    assert actions
    assert all(action.end_turn_building_source == "market" for action in actions)
    assert all(action.end_turn_building_id == "library" for action in actions)


def test_library_opponent_hire_pays_owner_and_moves_after_recall_before_turn_advance() -> None:
    scenario, actions = _library_actions("scenarios/library_hire_opponent_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    west = scenario.config.board.index_for_name("west")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.end_turn_building_source == "player_two"
            and candidate.end_turn_relocation_to == west
            and candidate.origin == city
            and candidate.resolution is TurnResolutionType.PRODUCE_WHEAT
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    recall_event = _events_of_type(result.events, EventType.ACOLYTE_RECALL)[0]
    relocation_event = _events_of_type(result.events, EventType.END_TURN_RELOCATION)[0]
    turn_advance_event = _events_of_type(result.events, EventType.TURN_ADVANCE)[0]
    hired_details = dict(hired_event.details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert result.events.index(recall_event) < result.events.index(hired_event)
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(relocation_event)
    assert result.events.index(relocation_event) < result.events.index(turn_advance_event)
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_library_hire_market_city_to_abbey_moves_acolyte_to_abbey() -> None:
    scenario, actions = _library_actions("scenarios/library_hire_market_city_to_abbey_001.json")
    city = scenario.config.board.index_for_name("city")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.end_turn_building_source == "market"
            and candidate.end_turn_relocation_to == "abbey"
            and candidate.origin == city
            and candidate.resolution is TurnResolutionType.PRODUCE_WHEAT
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)
    player = result.state.player_state(PlayerId.PLAYER_ONE)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    relocation_event = _events_of_type(result.events, EventType.END_TURN_RELOCATION)[0]
    hired_details = dict(hired_event.details)
    relocation_details = dict(relocation_event.details)

    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert relocation_details["from_pool"] == "city"
    assert relocation_details["to_pool"] == "abbey"
    assert player.workforce.abbey == 4
    assert player.workforce.mancala[city] == 0


def test_library_hire_blocked_for_merchant_none_insufficient_donated_and_not_live() -> None:
    _scenario, merchant_none_actions = _library_actions("scenarios/library_merchant_none_no_hire_001.json")
    assert merchant_none_actions == []

    _scenario, insufficient_actions = _library_actions("scenarios/library_insufficient_resource_no_hire_001.json")
    assert insufficient_actions == []

    _scenario, donated_actions = _library_actions("scenarios/library_donated_no_modifier_001.json")
    assert donated_actions == []

    _scenario, not_live_actions = _library_actions("scenarios/library_not_live_no_modifier_001.json")
    assert not_live_actions == []


def test_library_no_city_acolyte_after_turn_generates_no_suffix_variants() -> None:
    _scenario, actions = _library_actions("scenarios/library_no_city_acolyte_after_turn_no_modifier_001.json")
    assert actions == []


def test_normal_full_turn_actions_without_library_suffix_remain_legal() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    assert any(action.end_turn_building_id is None for action in actions)
    assert any(action.end_turn_building_id == "library" for action in actions)


def test_library_events_not_emitted_when_suffix_not_used() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _first_action(actions, lambda candidate: candidate.end_turn_building_id is None)
    result = apply_action(scenario.state, action, scenario.config)

    assert _events_of_type(result.events, EventType.END_TURN_RELOCATION) == []
    assert not any(
        dict(event.details).get("building") == "library"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )


def test_own_active_library_event_order_is_recall_bonus_relocation_turn_advance() -> None:
    scenario, actions = _library_actions("scenarios/library_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    west = scenario.config.board.index_for_name("west")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.end_turn_building_source == "own_active"
            and candidate.end_turn_relocation_to == west
            and candidate.origin == city
            and candidate.resolution is TurnResolutionType.PRODUCE_WHEAT
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    recall_event = _events_of_type(result.events, EventType.ACOLYTE_RECALL)[0]
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    relocation_event = _events_of_type(result.events, EventType.END_TURN_RELOCATION)[0]
    turn_advance_event = _events_of_type(result.events, EventType.TURN_ADVANCE)[0]

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert result.events.index(recall_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(relocation_event)
    assert result.events.index(relocation_event) < result.events.index(turn_advance_event)


def test_apply_rejects_invalid_library_source_or_target_fields() -> None:
    scenario, actions = _library_actions("scenarios/library_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    action = _first_action(actions, lambda candidate: candidate.end_turn_relocation_to == "abbey")

    invalid_source = replace(action, end_turn_relocation_from=city + 1)
    with pytest.raises(TransitionValidationError, match="Library relocation source must be City"):
        apply_action(scenario.state, invalid_source, scenario.config)

    invalid_target = replace(action, end_turn_relocation_to=city)
    with pytest.raises(TransitionValidationError, match="Library relocation target must be Abbey"):
        apply_action(scenario.state, invalid_target, scenario.config)


def test_library_can_combine_with_start_turn_relocation() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    combined_state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=(
                    *player_state.player_board_slots.active_buildings,
                    "library",
                ),
            ),
        ),
    )

    actions = legal_actions(combined_state, scenario.config)
    assert any(
        action.start_turn_building_id in {"dormitory", "inquisition"}
        and action.end_turn_building_id == "library"
        for action in actions
    )
