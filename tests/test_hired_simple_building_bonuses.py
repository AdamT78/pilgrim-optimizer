from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _action_for_resolution(actions, resolution: TurnResolutionType):
    return next(action for action in actions if action.resolution is resolution)


def _events_of_type(events, event_type: EventType):
    return [event for event in events if event.event_type is event_type]


def test_market_well_hire_variant_exists_for_produce_wheat() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_market_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    produce_wheat_actions = [
        action for action in actions if action.resolution is TurnResolutionType.PRODUCE_WHEAT
    ]

    assert len(produce_wheat_actions) == 1
    assert produce_wheat_actions[0].hired_building_id == "well"
    assert produce_wheat_actions[0].hired_building_source == "market"
    assert (
        "hire building: well from market"
        in action_summary(produce_wheat_actions[0], scenario.config)
    )


def test_market_well_hire_pays_bank_and_adds_bonus() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_market_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, action, scenario.config)

    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    hired_details = dict(hired_event.details)
    bonus_event = _events_of_type(result.events, EventType.BUILDING_BONUS)[0]
    bonus_details = dict(bonus_event.details)
    delta_event = _events_of_type(result.events, EventType.RESOURCE_DELTA)[0]
    delta_details = dict(delta_event.details)

    assert hired_details["building_id"] == "well"
    assert hired_details["source"] == "market"
    assert hired_details["payee"] == "bank"
    assert hired_details["resource"] == "wheat"
    assert hired_details["amount"] == 1
    assert bonus_details["building"] == "well"
    assert bonus_details["wheat_bonus"] == 1
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert delta_details["wheat"] == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 3


def test_opponent_well_hire_pays_owner_and_adds_bonus() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_opponent_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)

    assert hired_details["source"] == "player_two"
    assert hired_details["payee"] == "player_two"
    assert hired_details["resource"] == "wheat"
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 3
    assert result.state.player_state(PlayerId.PLAYER_TWO).resources.wheat == 1


def test_own_active_well_remains_free_and_has_no_hired_event() -> None:
    scenario = load_scenario("scenarios/produce_wheat_well_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert action.hired_building_id is None
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert delta_details["wheat"] == 3
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 3


def test_merchant_none_prevents_market_well_hire_variant() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_merchant_none_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert action.hired_building_id is None
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert not any(
        dict(event.details).get("building") == "well"
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
    )
    assert delta_details["wheat"] == 2


def test_insufficient_resource_prevents_market_well_hire_variant() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_insufficient_resource_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, action, scenario.config)

    assert action.hired_building_id is None
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 2


def test_donated_well_is_unavailable_for_hire_source() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_market_001.json")
    player_two = scenario.state.player_state(PlayerId.PLAYER_TWO)
    donated_state = scenario.state.with_building_market(()).with_player_state(
        PlayerId.PLAYER_TWO,
        replace(
            player_two,
            player_board_slots=replace(
                player_two.player_board_slots,
                active_buildings=(),
                donated_buildings=("well",),
            ),
        ),
    )
    action = _action_for_resolution(
        legal_actions(donated_state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )

    assert action.hired_building_id is None


def test_not_live_well_is_unavailable_for_hire_source() -> None:
    scenario = load_scenario("scenarios/produce_wheat_hire_well_market_001.json")
    not_live_state = scenario.state.with_building_availability((("well", 7),))
    action = _action_for_resolution(
        legal_actions(not_live_state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(not_live_state, action, scenario.config)

    assert action.hired_building_id is None
    assert _events_of_type(result.events, EventType.BUILDING_HIRED) == []


def test_fields_stacks_with_hired_well() -> None:
    scenario = load_scenario("scenarios/produce_wheat_fields_hire_well_market_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_WHEAT,
    )
    result = apply_action(scenario.state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert action.hired_building_id == "well"
    assert delta_details["wheat"] == 3
    assert any(
        dict(event.details).get("activity") == "fields"
        for event in _events_of_type(result.events, EventType.SPECIAL_ACTIVITY_BONUS)
    )


def test_market_quarry_hire_adds_stone_and_applies_payment() -> None:
    scenario = load_scenario("scenarios/produce_stone_hire_quarry_market_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.PRODUCE_STONE,
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_details = dict(_events_of_type(result.events, EventType.BUILDING_HIRED)[0].details)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert action.hired_building_id == "quarry"
    assert hired_details["resource"] == "wheat"
    assert delta_details["stone"] == 3
    assert delta_details["wheat"] == -1


def test_market_mint_hire_adds_silver_and_engraver_stacks() -> None:
    scenario = load_scenario("scenarios/clerical_silversmith_hire_mint_market_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    engraver_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=player_one.special_activities.with_activity("engraver", True),
        ),
    )
    action = _action_for_resolution(
        legal_actions(engraver_state, scenario.config),
        TurnResolutionType.CLERICAL_SILVERSMITH,
    )
    result = apply_action(engraver_state, action, scenario.config)
    delta_details = dict(_events_of_type(result.events, EventType.RESOURCE_DELTA)[0].details)

    assert action.hired_building_id == "mint"
    assert delta_details["silver"] == 4
    assert delta_details["wheat"] == -1


def test_market_chapel_hire_adds_piety_and_vestry_stacks() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_vestry_hire_chapel_market_001.json")
    action = _action_for_resolution(
        legal_actions(scenario.state, scenario.config),
        TurnResolutionType.CLERICAL_DEVOTION,
    )
    result = apply_action(scenario.state, action, scenario.config)
    hired_event = _events_of_type(result.events, EventType.BUILDING_HIRED)[0]
    bonus_event = next(
        event
        for event in _events_of_type(result.events, EventType.BUILDING_BONUS)
        if dict(event.details).get("building") == "chapel"
    )
    piety_details = dict(_events_of_type(result.events, EventType.PIETY_DELTA)[0].details)

    assert action.hired_building_id == "chapel"
    assert result.events.index(hired_event) < result.events.index(bonus_event)
    assert piety_details["new_piety_position"] == 4
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 0

