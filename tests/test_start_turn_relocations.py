from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules.transition import TransitionValidationError, apply_action, legal_actions


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def _start_turn_actions(path: str):
    scenario = load_scenario(path)
    actions = legal_actions(scenario.state, scenario.config)
    return scenario, [action for action in actions if action.start_turn_building_id is not None]


def _first_action(actions, predicate):
    return next(action for action in actions if predicate(action))


def test_dormitory_active_generates_duty_to_city_variants() -> None:
    scenario, actions = _start_turn_actions("scenarios/dormitory_active_return_duty_to_city_001.json")
    city = scenario.config.board.index_for_name("city")
    duty_positions = set(scenario.config.duty_positions())

    assert actions
    dormitory_actions = [action for action in actions if action.start_turn_building_id == "dormitory"]
    assert dormitory_actions
    assert all(action.start_turn_building_source == "own_active" for action in dormitory_actions)
    assert all(action.start_turn_relocation_to == city for action in dormitory_actions)
    assert all(action.start_turn_relocation_from in duty_positions for action in dormitory_actions)


def test_dormitory_market_hire_generates_variants_when_payable() -> None:
    _scenario, actions = _start_turn_actions(
        "scenarios/dormitory_hire_market_return_duty_to_city_001.json"
    )

    assert actions
    assert all(action.start_turn_building_id == "dormitory" for action in actions)
    assert all(action.start_turn_building_source == "market" for action in actions)


def test_dormitory_opponent_hire_pays_owner_and_relocates_before_sowing() -> None:
    scenario, actions = _start_turn_actions(
        "scenarios/dormitory_hire_opponent_return_duty_to_city_001.json"
    )
    city = scenario.config.board.index_for_name("city")
    east = scenario.config.board.index_for_name("east")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.start_turn_building_id == "dormitory"
            and candidate.start_turn_building_source == "player_two"
            and candidate.start_turn_relocation_from == east
            and candidate.origin == city
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    relocation_event = _events_of_type(result.events, EventType.START_TURN_RELOCATION)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)
    relocation_details = dict(relocation_event.details)
    sowing_details = dict(sowing_event.details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert relocation_details["from_position"] == east
    assert relocation_details["to_position"] == city
    assert sowing_details["picked_up"] == 2
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(relocation_event)
    assert result.events.index(relocation_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_dormitory_hire_blocked_by_merchant_none_or_insufficient_resource() -> None:
    _scenario, merchant_none_actions = _start_turn_actions(
        "scenarios/dormitory_merchant_none_no_hire_001.json"
    )
    assert merchant_none_actions == []

    scenario = load_scenario("scenarios/dormitory_hire_market_return_duty_to_city_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    insufficient_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=replace(player_one.resources, wheat=0),
        ),
    )
    insufficient_actions = [
        action
        for action in legal_actions(insufficient_state, scenario.config)
        if action.start_turn_building_id is not None
    ]
    assert insufficient_actions == []


def test_dormitory_donated_or_not_live_is_unavailable() -> None:
    _scenario, donated_actions = _start_turn_actions("scenarios/dormitory_donated_no_modifier_001.json")
    assert donated_actions == []

    scenario = load_scenario("scenarios/dormitory_hire_market_return_duty_to_city_001.json")
    not_live_state = scenario.state.with_building_availability((("dormitory", 7),))
    not_live_actions = [
        action
        for action in legal_actions(not_live_state, scenario.config)
        if action.start_turn_building_id is not None
    ]
    assert not_live_actions == []


def test_dormitory_no_duty_acolyte_generates_no_modifier_variants() -> None:
    _scenario, actions = _start_turn_actions("scenarios/dormitory_no_duty_acolyte_no_modifier_001.json")
    assert actions == []


def test_inquisition_active_generates_city_to_duty_variants() -> None:
    scenario, actions = _start_turn_actions("scenarios/inquisition_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    duty_positions = set(scenario.config.duty_positions())

    assert actions
    inquisition_actions = [
        action for action in actions if action.start_turn_building_id == "inquisition"
    ]
    assert inquisition_actions
    assert all(action.start_turn_building_source == "own_active" for action in inquisition_actions)
    assert all(action.start_turn_relocation_from == city for action in inquisition_actions)
    assert all(action.start_turn_relocation_to in duty_positions for action in inquisition_actions)


def test_inquisition_market_hire_generates_variants_when_payable() -> None:
    _scenario, actions = _start_turn_actions("scenarios/inquisition_hire_market_city_to_duty_001.json")

    assert actions
    assert all(action.start_turn_building_id == "inquisition" for action in actions)
    assert all(action.start_turn_building_source == "market" for action in actions)


def test_inquisition_opponent_hire_pays_owner_and_relocates_before_sowing() -> None:
    scenario, actions = _start_turn_actions("scenarios/inquisition_hire_opponent_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    west = scenario.config.board.index_for_name("west")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.start_turn_building_id == "inquisition"
            and candidate.start_turn_building_source == "player_two"
            and candidate.start_turn_relocation_to == west
            and candidate.origin == city
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    relocation_event = _events_of_type(result.events, EventType.START_TURN_RELOCATION)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    hired_details = dict(hired_event.details)
    sowing_details = dict(sowing_event.details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert sowing_details["picked_up"] == 1
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert result.events.index(bonus_event) < result.events.index(relocation_event)
    assert result.events.index(relocation_event) < result.events.index(sowing_event)
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_inquisition_hire_blocked_by_merchant_none_or_insufficient_resource() -> None:
    _scenario, merchant_none_actions = _start_turn_actions("scenarios/inquisition_merchant_none_no_hire_001.json")
    assert merchant_none_actions == []

    scenario = load_scenario("scenarios/inquisition_hire_market_city_to_duty_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    insufficient_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=replace(player_one.resources, wheat=0),
        ),
    )
    insufficient_actions = [
        action
        for action in legal_actions(insufficient_state, scenario.config)
        if action.start_turn_building_id is not None
    ]
    assert insufficient_actions == []


def test_inquisition_donated_or_not_live_is_unavailable() -> None:
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
    donated_actions = [
        action
        for action in legal_actions(donated_state, scenario.config)
        if action.start_turn_building_id is not None
    ]
    assert donated_actions == []

    _scenario, not_live_actions = _start_turn_actions("scenarios/inquisition_not_live_no_modifier_001.json")
    assert not_live_actions == []


def test_inquisition_no_city_acolyte_generates_no_modifier_variants() -> None:
    _scenario, actions = _start_turn_actions("scenarios/inquisition_no_city_acolyte_no_modifier_001.json")
    assert actions == []


def test_start_turn_events_not_emitted_when_modifier_not_used() -> None:
    scenario = load_scenario("scenarios/dormitory_active_return_duty_to_city_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    action = _first_action(actions, lambda candidate: candidate.start_turn_building_id is None)
    result = apply_action(scenario.state, action, scenario.config)

    assert _events_of_type(result.events, EventType.START_TURN_RELOCATION) == []
    assert not any(
        dict(event.details).get("building") in {"dormitory", "inquisition"}
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )


def test_own_active_start_turn_events_order_before_sowing_and_invariant_passes() -> None:
    scenario, actions = _start_turn_actions("scenarios/inquisition_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    north = scenario.config.board.index_for_name("north")
    action = _first_action(
        actions,
        lambda candidate: (
            candidate.start_turn_building_id == "inquisition"
            and candidate.start_turn_relocation_to == north
            and candidate.origin == city
        ),
    )
    result = apply_action(scenario.state, action, scenario.config)

    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    relocation_event = _events_of_type(result.events, EventType.START_TURN_RELOCATION)[0]
    sowing_event = _events_of_type(result.events, EventType.SOWING)[0]
    invariant_event = _events_of_type(result.events, EventType.INVARIANT_CHECK)[0]

    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert result.events.index(bonus_event) < result.events.index(relocation_event)
    assert result.events.index(relocation_event) < result.events.index(sowing_event)
    assert dict(invariant_event.details)["acolytes_conserved"] is True


def test_dormitory_apply_rejects_invalid_non_duty_source_position() -> None:
    scenario, actions = _start_turn_actions("scenarios/dormitory_active_return_duty_to_city_001.json")
    city = scenario.config.board.index_for_name("city")
    action = _first_action(actions, lambda candidate: candidate.start_turn_building_id == "dormitory")
    invalid_action = replace(action, start_turn_relocation_from=city)

    with pytest.raises(TransitionValidationError, match="Dormitory relocation source"):
        apply_action(scenario.state, invalid_action, scenario.config)


def test_inquisition_apply_rejects_invalid_city_target() -> None:
    scenario, actions = _start_turn_actions("scenarios/inquisition_active_city_to_duty_001.json")
    city = scenario.config.board.index_for_name("city")
    action = _first_action(actions, lambda candidate: candidate.start_turn_building_id == "inquisition")
    invalid_action = replace(action, start_turn_relocation_to=city)

    with pytest.raises(TransitionValidationError, match="Inquisition relocation target"):
        apply_action(scenario.state, invalid_action, scenario.config)
