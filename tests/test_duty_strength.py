import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import ResolveDutyAction
from pilgrim.model.enums import DutyStrength, PlayerId, TurnPhase
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
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


def test_minority_action_fails_when_silver_insufficient() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.DUTY,
        players=(
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0)),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0)),
        ),
        acolytes=(
            (0, 1, 0, 0, 0, 0, 0, 0, 0),
            (0, 2, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=0,
    )
    action = ResolveDutyAction(duty_position=1)
    with pytest.raises(TransitionValidationError):
        apply_action(state, action, scenario.config)
