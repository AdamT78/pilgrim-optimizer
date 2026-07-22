from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import ResolveDutyAction, SowingAction, TitheAction
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.transition import apply_action
from pilgrim.search.exact import solve_exact


def test_duty_recall_returns_acolytes_to_city() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.DUTY,
        players=(
            PlayerState(resources=Resources(stone=0, silver=1, wheat=0)),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0)),
        ),
        acolytes=(
            (1, 2, 0, 0, 0, 0, 0, 0, 0),
            (0, 0, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=1,
    )
    result = apply_action(state, ResolveDutyAction(duty_position=1), scenario.config)
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 3
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[1] == 0
    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert result.state.phase is TurnPhase.SOW


def test_tithe_does_not_recall_acolytes() -> None:
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.DUTY,
        players=(
            PlayerState(resources=Resources(stone=0, silver=1, wheat=0)),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0)),
        ),
        acolytes=(
            (0, 2, 0, 0, 0, 0, 0, 0, 0),
            (0, 0, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=1,
    )
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = apply_action(state, TitheAction(duty_position=1), scenario.config)
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 0
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[1] == 2


def test_acolyte_conservation_after_transition() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    before = scenario.state
    sow_action = SowingAction(source=0, route=(1, 2, 3))
    after = apply_action(before, sow_action, scenario.config).state
    assert sum(before.player_vector(PlayerId.PLAYER_ONE)) == sum(
        after.player_vector(PlayerId.PLAYER_ONE)
    )
    assert sum(before.player_vector(PlayerId.PLAYER_TWO)) == sum(
        after.player_vector(PlayerId.PLAYER_TWO)
    )


def test_exact_search_returns_result_without_crashing() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = solve_exact(scenario.state, scenario.config, depth=3)
    assert isinstance(result.best_score, int)
    assert result.nodes_expanded > 0
