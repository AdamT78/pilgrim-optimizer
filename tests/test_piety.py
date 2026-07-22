from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.piety import move_piety, score_piety
from pilgrim.rules.transition import apply_action
from pilgrim.search.evaluation import evaluate_state


def test_piety_scoring_lookup() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    piety_config = scenario.config.piety
    assert score_piety(0, piety_config) == -5
    assert score_piety(5, piety_config) == 0
    assert score_piety(10, piety_config) == 5
    assert score_piety(11, piety_config) == 7
    assert score_piety(12, piety_config) == 9


def test_piety_capped_movement() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    piety_config = scenario.config.piety
    assert move_piety(10, 2, piety_config) == 12
    assert move_piety(11, 2, piety_config) == 12
    assert move_piety(12, 1, piety_config) == 12


def test_devotion_increases_piety_and_emits_delta_when_changed() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(resources=Resources(stone=0, silver=1, wheat=0), piety=10),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0), piety=0),
        ),
        acolytes=(
            (2, 0, 0, 0, 0, 0, 0, 0, 0),
            (0, 0, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(1, 2),
        selected_duty=2,
        resolution=TurnResolutionType.CLERICAL_DEVOTION,
    )
    result = apply_action(state, action, scenario.config)

    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 12
    piety_events = [event for event in result.events if event.event_type is EventType.PIETY_DELTA]
    assert len(piety_events) == 1
    details = dict(piety_events[0].details)
    assert details["old_piety_position"] == 10
    assert details["new_piety_position"] == 12


def test_devotion_event_not_emitted_when_piety_already_capped() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(resources=Resources(stone=0, silver=1, wheat=0), piety=12),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0), piety=0),
        ),
        acolytes=(
            (2, 0, 0, 0, 0, 0, 0, 0, 0),
            (0, 0, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(1, 2),
        selected_duty=2,
        resolution=TurnResolutionType.CLERICAL_DEVOTION,
    )
    result = apply_action(state, action, scenario.config)

    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 12
    assert not any(event.event_type is EventType.PIETY_DELTA for event in result.events)


def test_evaluation_uses_piety_track_vp_instead_of_raw_position() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    low_piety_state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0), piety=0),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0), piety=0),
        ),
        acolytes=(
            (1, 0, 0, 0, 0, 0, 0, 0, 0),
            (1, 0, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=0,
    )
    high_piety_state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0), piety=12),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0), piety=0),
        ),
        acolytes=(
            (1, 0, 0, 0, 0, 0, 0, 0, 0),
            (1, 0, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=0,
    )

    low_breakdown = evaluate_state(low_piety_state, PlayerId.PLAYER_ONE, scenario.config)
    high_breakdown = evaluate_state(high_piety_state, PlayerId.PLAYER_ONE, scenario.config)

    assert low_breakdown.piety_track_vp == -5
    assert high_breakdown.piety_track_vp == 9
    assert low_breakdown.total == -5
    assert high_breakdown.total == 9
