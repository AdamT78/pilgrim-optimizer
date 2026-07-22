import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_summary
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.model.workforce import CommittedAcolytes, Workforce
from pilgrim.rules.alms import (
    apply_alms_threshold_reward,
    crossed_alms_thresholds,
    move_alms_position,
    resolve_alms_season_end,
    score_alms_table,
)
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import TransitionValidationError
from pilgrim.search.evaluation import evaluate_state


def test_alms_table_scoring_lookup() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    alms_config = scenario.config.alms
    assert score_alms_table(0, alms_config) == 0
    assert score_alms_table(1, alms_config) == 5
    assert score_alms_table(2, alms_config) == 11
    assert score_alms_table(3, alms_config) == 18
    assert score_alms_table(4, alms_config) == 26


def test_alms_position_movement_caps_at_six() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    alms_config = scenario.config.alms
    assert move_alms_position(5, 1, alms_config) == 6
    assert move_alms_position(5, 2, alms_config) == 6
    assert move_alms_position(6, 1, alms_config) == 6


@pytest.mark.parametrize(
    ("old_position", "new_position", "expected"),
    [
        (1, 2, (2,)),
        (1, 3, (2,)),
        (3, 5, (4,)),
        (5, 6, (6,)),
        (0, 6, (2, 4, 6)),
    ],
)
def test_crossed_threshold_rows(
    old_position: int,
    new_position: int,
    expected: tuple[int, ...],
) -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    crossed = crossed_alms_thresholds(old_position, new_position, scenario.config.alms)
    assert crossed == expected


def test_threshold_row_two_moves_village_to_abbey_when_available() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player = PlayerState(
        workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0), village=1, abbey=0),
    )
    updated, outcome = apply_alms_threshold_reward(player, 2, scenario.config.alms)
    assert updated.workforce.village == 0
    assert updated.workforce.abbey == 1
    assert updated.workforce.total == player.workforce.total
    assert outcome.moved is True


def test_threshold_row_four_moves_abbey_to_city_when_available() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player = PlayerState(
        workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0), village=0, abbey=1),
    )
    updated, outcome = apply_alms_threshold_reward(player, 4, scenario.config.alms)
    assert updated.workforce.abbey == 0
    assert updated.workforce.mancala[0] == 1
    assert updated.workforce.total == player.workforce.total
    assert outcome.moved is True


def test_threshold_row_six_moves_village_to_city_when_available() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player = PlayerState(
        workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0), village=1, abbey=0),
    )
    updated, outcome = apply_alms_threshold_reward(player, 6, scenario.config.alms)
    assert updated.workforce.village == 0
    assert updated.workforce.mancala[0] == 1
    assert updated.workforce.total == player.workforce.total
    assert outcome.moved is True


def test_threshold_reward_no_source_pool_keeps_workforce_non_negative() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    player = PlayerState(
        workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0), village=0, abbey=0),
    )
    updated, outcome = apply_alms_threshold_reward(player, 2, scenario.config.alms)
    assert updated == player
    assert updated.workforce.total == player.workforce.total
    assert outcome.moved is False
    assert "no village acolyte available" in outcome.description


def test_give_alms_transition_pays_advances_rewards_and_recalls() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    before = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=2, wheat=1),
                workforce=Workforce(
                    mancala=(3, 0, 0, 0, 0, 0, 0, 0, 0),
                    village=1,
                    abbey=0,
                ),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(5, 6, 7),
        selected_duty=5,
        resolution=TurnResolutionType.GIVE_ALMS,
        alms_payment_silver=1,
        alms_payment_wheat=1,
    )
    result = apply_action(before, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)

    assert after_player.resources.silver == 1
    assert after_player.resources.wheat == 0
    assert after_player.alms_position == 2
    assert after_player.workforce.village == 0
    assert after_player.workforce.abbey == 1
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[5] == 0
    assert result.state.player_vector(PlayerId.PLAYER_ONE)[0] == 1
    assert before.total_acolytes(PlayerId.PLAYER_ONE) == result.state.total_acolytes(
        PlayerId.PLAYER_ONE
    )
    event_types = {event.event_type for event in result.events}
    assert EventType.ALMS_PAYMENT in event_types
    assert EventType.ALMS_PROGRESS in event_types
    assert EventType.ALMS_THRESHOLD_REWARD in event_types
    assert EventType.ACOLYTE_RECALL in event_types
    assert EventType.PIETY_DELTA not in event_types


def test_give_alms_transition_fails_when_payment_is_insufficient() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=1, wheat=0),
                workforce=Workforce(mancala=(3, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(5, 6, 7),
        selected_duty=5,
        resolution=TurnResolutionType.GIVE_ALMS,
        alms_payment_silver=2,
        alms_payment_wheat=0,
    )
    with pytest.raises(TransitionValidationError, match="Insufficient silver"):
        apply_action(state, action, scenario.config)


def test_give_alms_transition_fails_when_payment_does_not_match_duty_value() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=2, wheat=1),
                workforce=Workforce(mancala=(3, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(5, 6, 7),
        selected_duty=5,
        resolution=TurnResolutionType.GIVE_ALMS,
        alms_payment_silver=1,
        alms_payment_wheat=0,
    )
    with pytest.raises(TransitionValidationError, match="must equal duty value"):
        apply_action(state, action, scenario.config)


def test_give_alms_applies_minority_silver_cost_in_addition_to_payment() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=1, wheat=1),
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 0, 0, 0, 0, 2, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    action = FullTurnAction(
        origin=0,
        route=(5,),
        selected_duty=5,
        resolution=TurnResolutionType.GIVE_ALMS,
        alms_payment_silver=0,
        alms_payment_wheat=1,
    )
    result = apply_action(state, action, scenario.config)
    after_player = result.state.player_state(PlayerId.PLAYER_ONE)
    assert after_player.resources.silver == 0
    assert after_player.resources.wheat == 0
    alms_payment_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_PAYMENT
    )
    details = dict(alms_payment_event.details)
    assert details["minority_silver_cost"] == 1


def test_season_end_highest_alms_wins_and_resets_track() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    before = GameState(
        active_player=PlayerId.PLAYER_TWO,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                piety=3,
                alms_position=4,
                workforce=Workforce(
                    mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0),
                    village=0,
                    abbey=1,
                    committed=CommittedAcolytes(alms_table=0),
                ),
            ),
            PlayerState(
                piety=5,
                alms_position=3,
                workforce=Workforce(
                    mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0),
                    village=0,
                    abbey=1,
                    committed=CommittedAcolytes(alms_table=0),
                ),
            ),
        ),
        turn=0,
    )
    result = resolve_alms_season_end(before, scenario.config.alms)
    assert result.winner is PlayerId.PLAYER_ONE
    assert result.moved_to_alms_table is True
    assert result.state.player_state(PlayerId.PLAYER_ONE).workforce.abbey == 0
    assert result.state.player_state(PlayerId.PLAYER_ONE).workforce.committed.alms_table == 1
    assert result.state.player_state(PlayerId.PLAYER_ONE).alms_position == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).alms_position == 0
    assert before.total_acolytes(PlayerId.PLAYER_ONE) == result.state.total_acolytes(
        PlayerId.PLAYER_ONE
    )
    assert before.total_acolytes(PlayerId.PLAYER_TWO) == result.state.total_acolytes(
        PlayerId.PLAYER_TWO
    )
    assert {event.event_type for event in result.events} == {
        EventType.ALMS_SEASON_REWARD,
        EventType.ALMS_RESET,
    }


def test_season_end_uses_piety_then_turn_order_for_tie_breaks() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    tie_by_alms_state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(alms_position=2, piety=4, workforce=Workforce(mancala=(0,) * 9, abbey=1)),
            PlayerState(alms_position=2, piety=5, workforce=Workforce(mancala=(0,) * 9, abbey=1)),
        ),
        turn=0,
    )
    piety_tie_winner = resolve_alms_season_end(tie_by_alms_state, scenario.config.alms).winner
    assert piety_tie_winner is PlayerId.PLAYER_TWO

    full_tie_state = GameState(
        active_player=PlayerId.PLAYER_TWO,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(alms_position=3, piety=5, workforce=Workforce(mancala=(0,) * 9, abbey=1)),
            PlayerState(alms_position=3, piety=5, workforce=Workforce(mancala=(0,) * 9, abbey=1)),
        ),
        turn=0,
    )
    turn_order_winner = resolve_alms_season_end(full_tie_state, scenario.config.alms).winner
    assert turn_order_winner is PlayerId.PLAYER_TWO


def test_season_end_no_abbey_acolyte_does_not_add_alms_table_acolyte() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    before = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(alms_position=5, piety=1, workforce=Workforce(mancala=(0,) * 9, abbey=0)),
            PlayerState(alms_position=2, piety=1, workforce=Workforce(mancala=(0,) * 9, abbey=1)),
        ),
        turn=0,
    )
    result = resolve_alms_season_end(before, scenario.config.alms)
    assert result.winner is PlayerId.PLAYER_ONE
    assert result.moved_to_alms_table is False
    assert result.state.player_state(PlayerId.PLAYER_ONE).workforce.committed.alms_table == 0
    details = dict(result.events[0].details)
    assert details["moved"] is False


def test_evaluation_includes_alms_table_vp() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=1, silver=2, wheat=0),
                piety=5,
                alms_position=4,
                victory_points=3,
                workforce=Workforce(
                    mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0),
                    committed=CommittedAcolytes(alms_table=2),
                ),
            ),
            PlayerState(workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0))),
        ),
        turn=0,
    )
    breakdown = evaluate_state(state, PlayerId.PLAYER_ONE, scenario.config)
    assert breakdown.alms_position == 4
    assert breakdown.alms_table_acolytes == 2
    assert breakdown.alms_table_vp == 11
    assert breakdown.total == 17


def test_legal_actions_include_give_alms_payment_when_available() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    give_alms_actions = [
        action for action in actions if action.resolution is TurnResolutionType.GIVE_ALMS
    ]
    assert give_alms_actions
    summary = action_summary(give_alms_actions[0], scenario.config)
    assert "action: give_alms" in summary
    assert "pay silver=" in summary
    assert "wheat=" in summary


def test_give_alms_payment_options_for_duty_value_one() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=1, wheat=1),
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 0, 0, 0, 0, 1, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    options = [
        (action.alms_payment_silver, action.alms_payment_wheat)
        for action in legal_actions(state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS
    ]
    assert (1, 0) in options
    assert (0, 1) in options


def test_give_alms_payment_options_for_duty_value_two() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    state = GameState(
        active_player=PlayerId.PLAYER_ONE,
        phase=TurnPhase.SOW,
        players=(
            PlayerState(
                resources=Resources(stone=0, silver=2, wheat=2),
                workforce=Workforce(mancala=(1, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
            PlayerState(
                resources=Resources(stone=0, silver=0, wheat=0),
                workforce=Workforce(mancala=(0, 0, 0, 0, 0, 0, 0, 0, 0)),
            ),
        ),
        turn=0,
    )
    options = {
        (action.alms_payment_silver, action.alms_payment_wheat)
        for action in legal_actions(state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS
    }
    assert options == {(2, 0), (1, 1), (0, 2)}
