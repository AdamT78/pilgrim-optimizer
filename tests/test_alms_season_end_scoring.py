from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.alms import score_alms_table
from pilgrim.rules.transition import legal_actions
from tests.round_end_helpers import apply_declining_confession


def test_unique_leader_reward_and_reset_continue_for_non_final_season() -> None:
    scenario = load_scenario("scenarios/alms_season_end_unique_leader_001.json")
    result = apply_declining_confession(scenario.state, _tithe_action(scenario), scenario.config)

    player_one = result.state.player_state(PlayerId.PLAYER_ONE)
    player_two = result.state.player_state(PlayerId.PLAYER_TWO)
    assert result.state.timing.round_number == 10
    assert result.state.timing.season_number == 2
    assert player_one.workforce.abbey == 0
    assert player_one.workforce.committed.alms_table == 1
    assert player_two.workforce.committed.alms_table == 0
    assert player_one.alms_position == 0
    assert player_two.alms_position == 0

    event_types = {event.event_type for event in result.events}
    assert EventType.ALMS_SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.START_PLAYER_MARKER in event_types
    assert EventType.TURN_ADVANCE in event_types
    assert EventType.GAME_END not in event_types

    reward_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_SEASON_REWARD
    )
    reward_details = dict(reward_event.details)
    assert reward_details["alms_table_acolytes"] == 1
    assert reward_details["end_game_vp"] == 5


def test_no_abbey_forfeits_reward_but_still_resets_markers() -> None:
    scenario = load_scenario("scenarios/alms_season_end_no_abbey_forfeit_001.json")
    result = apply_declining_confession(scenario.state, _tithe_action(scenario), scenario.config)

    player_one = result.state.player_state(PlayerId.PLAYER_ONE)
    assert player_one.workforce.committed.alms_table == 0
    assert player_one.workforce.abbey == 0
    assert player_one.alms_position == 0
    assert result.state.player_state(PlayerId.PLAYER_TWO).alms_position == 0

    reward_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_SEASON_REWARD
    )
    reward_details = dict(reward_event.details)
    assert reward_details["winner"] == "player_one"
    assert reward_details["moved"] is False
    assert reward_details["forfeited"] is True


def test_alms_table_vp_scoring_lookup_matches_rule_table() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    config = scenario.config.alms
    assert score_alms_table(1, config) == 5
    assert score_alms_table(2, config) == 11
    assert score_alms_table(3, config) == 18
    assert score_alms_table(4, config) == 26


def test_tie_break_by_higher_piety() -> None:
    scenario = load_scenario("scenarios/alms_season_end_tie_piety_break_001.json")
    result = apply_declining_confession(scenario.state, _tithe_action(scenario), scenario.config)

    season_end_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_SEASON_END
    )
    details = dict(season_end_event.details)
    assert details["winner"] == "player_two"
    assert details["tie_break"] == "higher_piety"


def test_tie_break_by_turn_order_from_current_start_player() -> None:
    scenario = load_scenario("scenarios/alms_season_end_tie_turn_order_break_001.json")
    result = apply_declining_confession(scenario.state, _tithe_action(scenario), scenario.config)

    season_end_event = next(
        event for event in result.events if event.event_type is EventType.ALMS_SEASON_END
    )
    details = dict(season_end_event.details)
    assert details["winner"] == "player_one"
    assert details["tie_break"] == "turn_order"


def test_no_trigger_without_pilgrimage_round_metadata() -> None:
    scenario = load_scenario("scenarios/alms_season_end_no_metadata_no_trigger_001.json")
    result = apply_declining_confession(scenario.state, _tithe_action(scenario), scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.ALMS_SEASON_END not in event_types
    assert EventType.ALMS_SEASON_REWARD not in event_types
    assert EventType.ALMS_RESET not in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.START_PLAYER_MARKER in event_types


def test_fourth_season_scores_then_ends_game_without_continuation_steps() -> None:
    scenario = load_scenario("scenarios/alms_season_end_fourth_season_game_end_001.json")
    result = apply_declining_confession(scenario.state, _tithe_action(scenario), scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.ROUND_ADVANCE in event_types
    assert EventType.ALMS_SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.GAME_END in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.START_PLAYER_MARKER not in event_types
    assert EventType.TURN_ADVANCE not in event_types
    assert result.state.game_over is True
    assert result.state.timing.season_number == 4


def test_event_order_for_non_final_and_final_season_end_paths() -> None:
    normal = load_scenario("scenarios/alms_season_end_unique_leader_001.json")
    normal_result = apply_declining_confession(normal.state, _tithe_action(normal), normal.config)
    assert (
        _event_index(normal_result.events, EventType.ROUND_ADVANCE)
        < _event_index(normal_result.events, EventType.ALMS_SEASON_END)
        < _event_index(normal_result.events, EventType.ALMS_SEASON_REWARD)
        < _event_index(normal_result.events, EventType.ALMS_RESET)
        < _event_index(normal_result.events, EventType.MERCHANT_ADVANCE)
        < _event_index(normal_result.events, EventType.TURN_ADVANCE)
        < _event_index(normal_result.events, EventType.START_PLAYER_MARKER)
    )

    final = load_scenario("scenarios/alms_season_end_fourth_season_game_end_001.json")
    final_result = apply_declining_confession(final.state, _tithe_action(final), final.config)
    assert (
        _event_index(final_result.events, EventType.ROUND_ADVANCE)
        < _event_index(final_result.events, EventType.ALMS_SEASON_END)
        < _event_index(final_result.events, EventType.ALMS_SEASON_REWARD)
        < _event_index(final_result.events, EventType.ALMS_RESET)
        < _event_index(final_result.events, EventType.GAME_END)
    )


def _tithe_action(scenario):
    return next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    )


def _event_index(events, event_type: EventType) -> int:
    for index, event in enumerate(events):
        if event.event_type is event_type:
            return index
    raise AssertionError(f"Missing event type: {event_type}")
