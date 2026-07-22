from pilgrim.evaluation import (
    SANDBOX_EVALUATION_FORMULA,
    evaluate_player,
    evaluate_root_player,
)
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import CommittedAcolytes, Workforce
from pilgrim.opponents import OpponentModelType
from pilgrim.search.exact import solve_exact


def test_evaluation_piety_track_vp_values() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                piety=0,
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                piety=12,
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
    )
    p1 = evaluate_player(state, PlayerId.PLAYER_ONE, scenario.config)
    p2 = evaluate_player(state, PlayerId.PLAYER_TWO, scenario.config)
    assert p1.piety_track_vp == -5
    assert p2.piety_track_vp == 9


def test_evaluation_alms_table_vp_values() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                workforce=Workforce(
                    mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0),
                    committed=CommittedAcolytes(alms_table=0),
                )
            ),
            PlayerState(
                workforce=Workforce(
                    mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0),
                    committed=CommittedAcolytes(alms_table=1),
                )
            ),
        ),
    )
    p1 = evaluate_player(state, PlayerId.PLAYER_ONE, scenario.config)
    p2 = evaluate_player(state, PlayerId.PLAYER_TWO, scenario.config)
    assert p1.alms_table_vp == 0
    assert p2.alms_table_vp == 5


def test_evaluation_resource_total_and_total_formula() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=2, silver=3, wheat=4),
                piety=12,
                victory_points=6,
                workforce=Workforce(
                    mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0),
                    committed=CommittedAcolytes(alms_table=1),
                ),
            ),
            PlayerState(workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0))),
        ),
    )
    breakdown = evaluate_player(state, PlayerId.PLAYER_ONE, scenario.config)
    assert breakdown.resource_total == 9
    assert breakdown.total == (
        breakdown.victory_points
        + breakdown.piety_track_vp
        + breakdown.alms_table_vp
        + breakdown.resource_total
    )
    assert SANDBOX_EVALUATION_FORMULA == (
        "victory_points + piety_track_vp + alms_table_vp + resource_total"
    )


def test_root_player_evaluation_can_differ_by_player() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=3, wheat=0),
                piety=12,
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                piety=0,
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
    )
    root_one = evaluate_root_player(
        state,
        root_player_id=PlayerId.PLAYER_ONE,
        config=scenario.config,
    )
    root_two = evaluate_root_player(
        state,
        root_player_id=PlayerId.PLAYER_TWO,
        config=scenario.config,
    )
    assert root_one.total == 12
    assert root_two.total == -5


def test_search_score_uses_root_player_evaluation_total() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    root_player_id = PlayerId.PLAYER_ONE
    search_result = solve_exact(
        scenario.state,
        scenario.config,
        depth=0,
        root_player_id=root_player_id,
        opponent_model_type=OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX,
    )
    expected = evaluate_root_player(
        scenario.state,
        root_player_id=root_player_id,
        config=scenario.config,
    )
    assert search_result.best_score == expected.total
    assert search_result.best_line_final_breakdown.total == expected.total
