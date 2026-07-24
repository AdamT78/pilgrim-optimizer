from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions


def _action_for_resolution(state, config, resolution: TurnResolutionType):
    return next(
        action for action in legal_actions(state, config) if action.resolution is resolution
    )


def _with_player_one_buildings(
    state,
    *,
    active_buildings: tuple[str, ...],
    donated_buildings: tuple[str, ...],
):
    player_one = state.player_state(PlayerId.PLAYER_ONE)
    updated_slots = replace(
        player_one.player_board_slots,
        active_buildings=active_buildings,
        donated_buildings=donated_buildings,
    )
    return state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, player_board_slots=updated_slots),
    )


def _with_player_one_special_activity(state, activity_id: str):
    player_one = state.player_state(PlayerId.PLAYER_ONE)
    return state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            special_activities=player_one.special_activities.with_activity(activity_id, True),
        ),
    )


def _building_bonus_events(events):
    return [event for event in events if event.event_type is EventType.BUILDING_BONUS]


def test_well_adds_plus_one_wheat_to_produce_wheat() -> None:
    scenario = load_scenario("scenarios/produce_wheat_well_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.PRODUCE_WHEAT)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.wheat == 3
    bonus_event = next(event for event in _building_bonus_events(result.events))
    bonus_details = dict(bonus_event.details)
    assert bonus_details["building"] == "well"
    assert bonus_details["action"] == "produce_wheat"
    assert bonus_details["wheat_bonus"] == 1


def test_quarry_adds_plus_one_stone_to_produce_stone() -> None:
    scenario = load_scenario("scenarios/produce_stone_quarry_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.PRODUCE_STONE)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.stone == 3
    bonus_event = next(event for event in _building_bonus_events(result.events))
    bonus_details = dict(bonus_event.details)
    assert bonus_details["building"] == "quarry"
    assert bonus_details["action"] == "produce_stone"
    assert bonus_details["stone_bonus"] == 1


def test_well_does_not_affect_produce_stone() -> None:
    scenario = load_scenario("scenarios/produce_wheat_well_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.PRODUCE_STONE)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.stone == 2
    assert not _building_bonus_events(result.events)


def test_quarry_does_not_affect_produce_wheat() -> None:
    scenario = load_scenario("scenarios/produce_stone_quarry_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.PRODUCE_WHEAT)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.wheat == 2
    assert not _building_bonus_events(result.events)


def test_donated_well_does_not_apply() -> None:
    scenario = load_scenario("scenarios/produce_wheat_well_001.json")
    donated_state = _with_player_one_buildings(
        scenario.state,
        active_buildings=(),
        donated_buildings=("well",),
    )
    action = _action_for_resolution(donated_state, scenario.config, TurnResolutionType.PRODUCE_WHEAT)
    result = apply_action(donated_state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.wheat == 2
    assert not _building_bonus_events(result.events)


def test_donated_quarry_does_not_apply() -> None:
    scenario = load_scenario("scenarios/produce_stone_quarry_001.json")
    donated_state = _with_player_one_buildings(
        scenario.state,
        active_buildings=(),
        donated_buildings=("quarry",),
    )
    action = _action_for_resolution(donated_state, scenario.config, TurnResolutionType.PRODUCE_STONE)
    result = apply_action(donated_state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.stone == 2
    assert not _building_bonus_events(result.events)


def test_well_stacks_with_fields() -> None:
    scenario = load_scenario("scenarios/produce_wheat_fields_and_well_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.PRODUCE_WHEAT)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.wheat == 4
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "fields"
        for event in result.events
    )
    assert any(dict(event.details).get("building") == "well" for event in _building_bonus_events(result.events))
    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    assert duty_details["duty_value"] == duty_details["effective_duty_value"] == 2


def test_quarry_stacks_with_stone_mason() -> None:
    scenario = load_scenario("scenarios/produce_stone_quarry_001.json")
    state_with_stone_mason = _with_player_one_special_activity(scenario.state, "stone_mason")
    action = _action_for_resolution(
        state_with_stone_mason,
        scenario.config,
        TurnResolutionType.PRODUCE_STONE,
    )
    result = apply_action(state_with_stone_mason, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.stone == 4
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "stone_mason"
        for event in result.events
    )
    assert any(
        dict(event.details).get("building") == "quarry" for event in _building_bonus_events(result.events)
    )


def test_mint_adds_plus_one_silver_to_clerical_silversmith() -> None:
    scenario = load_scenario("scenarios/clerical_silversmith_mint_001.json")
    action = _action_for_resolution(
        scenario.state,
        scenario.config,
        TurnResolutionType.CLERICAL_SILVERSMITH,
    )
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.silver == 3
    bonus_event = next(event for event in _building_bonus_events(result.events))
    bonus_details = dict(bonus_event.details)
    assert bonus_details["building"] == "mint"
    assert bonus_details["action"] == "clerical_silversmith"
    assert bonus_details["silver_bonus"] == 1


def test_chapel_adds_plus_one_piety_to_clerical_devotion() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_chapel_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.CLERICAL_DEVOTION)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.piety == 3
    bonus_event = next(event for event in _building_bonus_events(result.events))
    bonus_details = dict(bonus_event.details)
    assert bonus_details["building"] == "chapel"
    assert bonus_details["action"] == "clerical_devotion"
    assert bonus_details["piety_bonus"] == 1


def test_mint_does_not_affect_clerical_devotion() -> None:
    scenario = load_scenario("scenarios/clerical_silversmith_mint_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.CLERICAL_DEVOTION)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.piety == 2
    assert not _building_bonus_events(result.events)


def test_chapel_does_not_affect_clerical_silversmith() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_chapel_001.json")
    action = _action_for_resolution(
        scenario.state,
        scenario.config,
        TurnResolutionType.CLERICAL_SILVERSMITH,
    )
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.silver == 2
    assert not _building_bonus_events(result.events)


def test_donated_mint_does_not_apply() -> None:
    scenario = load_scenario("scenarios/clerical_silversmith_mint_001.json")
    donated_state = _with_player_one_buildings(
        scenario.state,
        active_buildings=(),
        donated_buildings=("mint",),
    )
    action = _action_for_resolution(
        donated_state,
        scenario.config,
        TurnResolutionType.CLERICAL_SILVERSMITH,
    )
    result = apply_action(donated_state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.silver == 2
    assert not _building_bonus_events(result.events)


def test_donated_chapel_does_not_apply() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_chapel_001.json")
    donated_state = _with_player_one_buildings(
        scenario.state,
        active_buildings=(),
        donated_buildings=("chapel",),
    )
    action = _action_for_resolution(
        donated_state,
        scenario.config,
        TurnResolutionType.CLERICAL_DEVOTION,
    )
    result = apply_action(donated_state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.piety == 2
    assert not _building_bonus_events(result.events)


def test_mint_stacks_with_engraver() -> None:
    scenario = load_scenario("scenarios/clerical_silversmith_mint_001.json")
    state_with_engraver = _with_player_one_special_activity(scenario.state, "engraver")
    action = _action_for_resolution(
        state_with_engraver,
        scenario.config,
        TurnResolutionType.CLERICAL_SILVERSMITH,
    )
    result = apply_action(state_with_engraver, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.resources.silver == 4
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "engraver"
        for event in result.events
    )
    assert any(dict(event.details).get("building") == "mint" for event in _building_bonus_events(result.events))
    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    assert duty_details["duty_value"] == duty_details["effective_duty_value"] == 2


def test_chapel_stacks_with_vestry() -> None:
    scenario = load_scenario("scenarios/clerical_devotion_vestry_and_chapel_001.json")
    action = _action_for_resolution(scenario.state, scenario.config, TurnResolutionType.CLERICAL_DEVOTION)
    result = apply_action(scenario.state, action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after.piety == 4
    assert any(
        event.event_type is EventType.SPECIAL_ACTIVITY_BONUS
        and dict(event.details).get("activity") == "vestry"
        for event in result.events
    )
    assert any(
        dict(event.details).get("building") == "chapel" for event in _building_bonus_events(result.events)
    )
    duty_event = next(event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION)
    duty_details = dict(duty_event.details)
    assert duty_details["duty_value"] == duty_details["effective_duty_value"] == 2
