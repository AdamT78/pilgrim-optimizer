from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import Workforce
from pilgrim.rules.transition import apply_action, legal_actions


def test_ordination_legal_actions_include_ordain_when_village_and_wheat_available() -> None:
    scenario = load_scenario("scenarios/ordination_ordain_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    ordination_actions = [
        action for action in actions if action.resolution is TurnResolutionType.ORDINATION
    ]

    assert len(ordination_actions) == 1
    assert ordination_actions[0].ordination_steps == ("ordain",)
    assert any(action.resolution is TurnResolutionType.TITHE for action in actions)


def test_ordination_legal_actions_include_mission_when_abbey_and_wheat_available() -> None:
    scenario = load_scenario("scenarios/ordination_mission_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    ordination_actions = [
        action for action in actions if action.resolution is TurnResolutionType.ORDINATION
    ]

    assert len(ordination_actions) == 1
    assert ordination_actions[0].ordination_steps == ("mission",)


def test_ordination_legal_actions_allow_ordain_then_mission_with_duty_value_two() -> None:
    scenario = load_scenario("scenarios/ordination_ordain_then_mission_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    ordination_actions = [
        action for action in actions if action.resolution is TurnResolutionType.ORDINATION
    ]
    step_sequences = {action.ordination_steps for action in ordination_actions}

    assert ordination_actions
    assert ordination_actions[0].ordination_steps == ("ordain", "mission")
    assert ("ordain",) in step_sequences
    assert ("ordain", "mission") in step_sequences
    assert ("mission",) not in step_sequences
    assert all(len(action.ordination_steps) <= 2 for action in ordination_actions)


def test_ordination_two_step_actions_require_two_wheat() -> None:
    scenario = load_scenario("scenarios/ordination_ordain_then_mission_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    reduced_wheat_state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(
            player_one,
            resources=Resources(
                stone=player_one.resources.stone,
                silver=player_one.resources.silver,
                wheat=1,
            ),
        ),
    )
    actions = legal_actions(reduced_wheat_state, scenario.config)
    ordination_actions = [
        action for action in actions if action.resolution is TurnResolutionType.ORDINATION
    ]

    assert ordination_actions
    assert all(len(action.ordination_steps) == 1 for action in ordination_actions)
    assert all(action.ordination_steps != ("ordain", "mission") for action in ordination_actions)


def test_ordination_legal_actions_generate_none_when_wheat_is_zero() -> None:
    scenario = load_scenario("scenarios/ordination_insufficient_wheat_001.json")
    actions = legal_actions(scenario.state, scenario.config)

    assert not any(action.resolution is TurnResolutionType.ORDINATION for action in actions)
    assert any(action.resolution is TurnResolutionType.TITHE for action in actions)


def test_apply_ordination_ordain_updates_village_abbey_wheat_and_recall() -> None:
    scenario = load_scenario("scenarios/ordination_ordain_001.json")
    before_total = scenario.state.total_acolytes(PlayerId.PLAYER_ONE)
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    ordination_events = [event for event in result.events if event.event_type is EventType.ORDINATION]

    assert action.resolution is TurnResolutionType.ORDINATION
    assert action.ordination_steps == ("ordain",)
    assert after_player.workforce.village == 0
    assert after_player.workforce.abbey == 1
    assert after_player.resources.wheat == 0
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[6] == 0
    assert after_player.workforce.mancala[0] == 1
    assert len(ordination_events) == 1
    assert dict(ordination_events[0].details)["step"] == "ordain"
    assert before_total == result.state.total_acolytes(PlayerId.PLAYER_ONE)


def test_apply_ordination_mission_updates_abbey_city_wheat_and_recall() -> None:
    scenario = load_scenario("scenarios/ordination_mission_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    ordination_events = [event for event in result.events if event.event_type is EventType.ORDINATION]

    assert action.resolution is TurnResolutionType.ORDINATION
    assert action.ordination_steps == ("mission",)
    assert after_player.workforce.abbey == 0
    assert after_player.resources.wheat == 0
    assert after_player.workforce.mancala[0] == 2
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[6] == 0
    assert len(ordination_events) == 1
    assert dict(ordination_events[0].details)["step"] == "mission"


def test_apply_ordination_ordain_then_mission_chains_newly_ordained_acolyte() -> None:
    scenario = load_scenario("scenarios/ordination_ordain_then_mission_001.json")
    before_total = scenario.state.total_acolytes(PlayerId.PLAYER_ONE)
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    ordination_steps = [
        dict(event.details)["step"]
        for event in result.events
        if event.event_type is EventType.ORDINATION
    ]

    assert action.resolution is TurnResolutionType.ORDINATION
    assert action.ordination_steps == ("ordain", "mission")
    assert ordination_steps == ["ordain", "mission"]
    assert after_player.workforce.village == 0
    assert after_player.workforce.abbey == 0
    assert after_player.resources.wheat == 0
    assert after_player.workforce.mancala[0] == 2
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[6] == 0
    assert before_total == result.state.total_acolytes(PlayerId.PLAYER_ONE)


def test_apply_ordination_two_ordains_converts_two_serfs_to_abbey_acolytes() -> None:
    scenario = load_scenario("scenarios/ordination_two_ordains_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    ordination_steps = [
        dict(event.details)["step"]
        for event in result.events
        if event.event_type is EventType.ORDINATION
    ]

    assert action.resolution is TurnResolutionType.ORDINATION
    assert action.ordination_steps == ("ordain", "ordain")
    assert ordination_steps == ["ordain", "ordain"]
    assert after_player.workforce.village == 0
    assert after_player.workforce.abbey == 2
    assert after_player.resources.wheat == 0
    assert after_player.workforce.mancala[0] == 1


def test_apply_ordination_minority_applies_silver_cost() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=1, wheat=1),
                workforce=Workforce(
                    mancala=(0, 0, 0, 0, 0, 1, 0, 0, 0),
                    village=1,
                    abbey=0,
                ),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(
                    mancala=(0, 0, 0, 0, 0, 0, 2, 0, 0),
                    village=0,
                    abbey=0,
                ),
            ),
        ),
        table_player_count=4,
        turn=0,
    )
    action = next(
        candidate
        for candidate in legal_actions(state, scenario.config)
        if candidate.resolution is TurnResolutionType.ORDINATION
    )

    result = apply_action(state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    resource_event = next(
        event for event in result.events if event.event_type is EventType.RESOURCE_DELTA
    )

    assert action.ordination_steps == ("ordain",)
    assert after_player.resources.silver == 0
    assert after_player.resources.wheat == 0
    assert dict(duty_event.details)["strength"] == "minority"
    assert dict(duty_event.details)["silver_cost"] == 1
    assert dict(resource_event.details)["silver"] == -1
    assert dict(resource_event.details)["wheat"] == -1
