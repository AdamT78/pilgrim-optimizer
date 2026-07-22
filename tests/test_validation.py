import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.transition import apply_action
from pilgrim.rules.validation import TransitionValidationError, validate_state_invariants


def test_route_length_must_match_picked_up_acolytes() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    with pytest.raises(TransitionValidationError):
        apply_action(
            scenario.state,
            FullTurnAction(
                origin=0,
                route=(1, 2),
                selected_duty=2,
                resolution=TurnResolutionType.CLERICAL_DEVOTION,
            ),
            scenario.config,
        )


def test_selected_duty_must_contain_active_player_acolyte() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(resources=Resources(stone=0, silver=2, wheat=0)),
            PlayerState(resources=Resources(stone=0, silver=0, wheat=0)),
        ),
        acolytes=(
            (3, 0, 0, 0, 0, 0, 0, 0, 0),
            (0, 1, 0, 0, 0, 0, 0, 0, 0),
        ),
        turn=1,
    )
    with pytest.raises(TransitionValidationError):
        apply_action(
            state,
            FullTurnAction(
                origin=0,
                route=(1, 2, 3),
                selected_duty=8,
                resolution=TurnResolutionType.PRODUCE,
            ),
            scenario.config,
        )


def test_validate_scenario_state_invariants() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    validate_state_invariants(scenario.state)
