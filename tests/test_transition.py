from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.search.exact import solve_exact


def test_apply_action_applies_sowing_and_duty_in_one_call() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
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
    action = FullTurnAction(
        origin=0,
        route=(1,),
        selected_duty=1,
        resolution=TurnResolutionType.PRODUCE,
    )
    result = apply_action(state, action, scenario.config)
    assert result.state.player_state(PlayerId.PLAYER_ONE).resources.wheat == 2
    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert result.state.phase is TurnPhase.SOW


def test_full_turn_duty_recall_returns_acolytes_to_city() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
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
    action = FullTurnAction(
        origin=0,
        route=(1,),
        selected_duty=1,
        resolution=TurnResolutionType.PRODUCE,
    )
    result = apply_action(state, action, scenario.config)
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 3
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[1] == 0


def test_full_turn_tithe_does_not_recall() -> None:
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
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
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    action = FullTurnAction(
        origin=0,
        route=(1,),
        selected_duty=1,
        resolution=TurnResolutionType.TITHE,
    )
    result = apply_action(state, action, scenario.config)
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 0
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[1] == 3


def test_acolyte_conservation_after_full_turn_transition() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    before = scenario.state
    action = FullTurnAction(
        origin=0,
        route=(1, 2, 3),
        selected_duty=3,
        resolution=TurnResolutionType.CLERICAL_SILVERSMITH,
    )
    after = apply_action(before, action, scenario.config).state
    assert sum(before.player_vector(PlayerId.PLAYER_ONE)) == sum(
        after.player_vector(PlayerId.PLAYER_ONE)
    )
    assert sum(before.player_vector(PlayerId.PLAYER_TWO)) == sum(
        after.player_vector(PlayerId.PLAYER_TWO)
    )


def test_exact_search_depth_corresponds_to_full_turns() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = solve_exact(scenario.state, scenario.config, depth=3)
    assert isinstance(result.best_score, int)
    assert result.nodes_expanded > 0
    assert len(result.principal_variation) == 3


def test_legal_actions_return_full_turn_actions() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    assert len(actions) > 2
    first = actions[0]
    assert isinstance(first, FullTurnAction)
