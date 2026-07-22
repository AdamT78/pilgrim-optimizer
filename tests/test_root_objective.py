import json
from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import Workforce
from pilgrim.opponents import OpponentModelType
from pilgrim.search.evaluation import evaluate_state
from pilgrim.search.exact import solve_exact


def test_scenario_loads_root_player_and_opponent_model() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    assert scenario.root_player_id is PlayerId.PLAYER_ONE
    assert scenario.opponent_model.type is OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX


def test_missing_root_player_defaults_to_active_player(tmp_path: Path) -> None:
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    scenario_path = tmp_path / "scenario_without_root.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "tmp_default_root",
                "board_file": str(Path("configs/board.json").resolve()),
                "duties_file": str(Path("configs/duties.json").resolve()),
                "piety_file": str(Path("configs/piety.json").resolve()),
                "initial_state": setup_raw["initial_state"],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_scenario(scenario_path)
    assert loaded.root_player_id is loaded.state.active_player
    assert loaded.opponent_model.type is OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX


def test_evaluation_can_be_calculated_for_both_players() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=3, wheat=0),
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
                piety=12,
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
                piety=0,
            ),
        ),
        turn=0,
    )
    p1_breakdown = evaluate_state(state, PlayerId.PLAYER_ONE, scenario.config)
    p2_breakdown = evaluate_state(state, PlayerId.PLAYER_TWO, scenario.config)

    assert p1_breakdown.total == 12
    assert p2_breakdown.total == -5


def test_search_score_uses_root_player_perspective() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    root_one = solve_exact(
        scenario.state,
        scenario.config,
        depth=0,
        root_player_id=PlayerId.PLAYER_ONE,
        opponent_model_type=OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX,
    )
    root_two = solve_exact(
        scenario.state,
        scenario.config,
        depth=0,
        root_player_id=PlayerId.PLAYER_TWO,
        opponent_model_type=OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX,
    )

    assert root_one.best_score == -4
    assert root_two.best_score == -5


def test_search_still_returns_full_turn_principal_variation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = solve_exact(
        scenario.state,
        scenario.config,
        depth=2,
        root_player_id=PlayerId.PLAYER_TWO,
        opponent_model_type=OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX,
    )
    assert len(result.principal_variation) == 2
