import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.dummy import DummyAcolyteGroups
from pilgrim.model.enums import PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import CommittedAcolytes, Workforce
from pilgrim.rules.transition import apply_action, legal_actions
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
            PlayerState(
                resources=Resources(stone=0, silver=2, wheat=0),
                workforce=Workforce(mancala=(3, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 1, 0, 0, 0, 0, 0, 0, 0)),
            ),
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


def test_negative_village_fails_validation() -> None:
    with pytest.raises(ValueError):
        Workforce(
            mancala=(3, 0, 0, 0, 0, 0, 0, 0, 0),
            village=-1,
        )


def test_negative_committed_count_fails_validation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    with pytest.raises(ValueError):
        GameState(
            active_player=PlayerId.PLAYER_ONE,
            phase=TurnPhase.SOW,
            players=(
                PlayerState(
                    resources=Resources(stone=0, silver=1, wheat=0),
                    workforce=Workforce(
                        mancala=(3, 0, 0, 0, 0, 0, 0, 0, 0),
                        committed=CommittedAcolytes(roads=-1),
                    ),
                ),
                scenario.state.player_state(PlayerId.PLAYER_TWO),
            ),
            turn=0,
        )


def test_mancala_vector_length_must_be_nine() -> None:
    with pytest.raises(ValueError):
        Workforce(mancala=(1, 2, 3))


def test_dummy_city_position_must_be_zero() -> None:
    with pytest.raises(ValueError):
        DummyAcolyteGroups(
            north_group=(1, 0, 0, 0, 0, 0, 0, 0, 0),
            south_group=(0, 0, 0, 0, 0, 0, 0, 0, 0),
        )


def test_dummy_totals_must_match_player_count_expectation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    invalid_state = scenario.state.with_dummy_acolytes(
        DummyAcolyteGroups(
            north_group=(0, 1, 1, 0, 0, 0, 0, 0, 0),
            south_group=(0, 0, 0, 0, 0, 1, 1, 1, 0),
        )
    )
    with pytest.raises(TransitionValidationError, match="north_group total"):
        validate_state_invariants(invalid_state)


def test_game_over_blocks_legal_actions() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    over_state = scenario.state.with_game_over(True)
    assert legal_actions(over_state, scenario.config) == ()


def test_ship_position_cannot_be_negative() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    with pytest.raises(ValueError):
        scenario.state.with_ship_position(-1)
