import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import DutyStrength, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import Workforce
from pilgrim.rules.duties import duty_strength, duty_value_and_silver_cost
from pilgrim.rules.transition import apply_action
from pilgrim.rules.validation import TransitionValidationError


def test_majority_parity_minority_value_calculation() -> None:
    majority = duty_strength(2, (1,))
    parity = duty_strength(1, (1,))
    minority = duty_strength(0, (1,))

    assert majority is DutyStrength.MAJORITY
    assert duty_value_and_silver_cost(majority) == (2, 0)

    assert parity is DutyStrength.PARITY
    assert duty_value_and_silver_cost(parity) == (1, 0)

    assert minority is DutyStrength.MINORITY
    assert duty_value_and_silver_cost(minority) == (1, 1)


def test_dummy_competition_can_cause_parity_minority_and_majority() -> None:
    # player=1, (real_opponent=0, dummy=1) => parity
    assert duty_strength(1, (0, 1)) is DutyStrength.PARITY
    # player=1, (real_opponent=0, dummy=2) => minority
    assert duty_strength(1, (0, 2)) is DutyStrength.MINORITY
    # player=2, (real_opponent=0, dummy=1) => majority
    assert duty_strength(2, (0, 1)) is DutyStrength.MAJORITY


def test_highest_competing_count_is_used_across_real_and_dummy() -> None:
    # highest competing count is 2 (dummy), not 1 (real opponent)
    assert duty_strength(1, (1, 2)) is DutyStrength.MINORITY


def test_minority_action_fails_when_silver_insufficient() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 2, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(1,),
        selected_duty=1,
        resolution=TurnResolutionType.PRODUCE,
    )
    with pytest.raises(TransitionValidationError):
        apply_action(state, action, scenario.config)
