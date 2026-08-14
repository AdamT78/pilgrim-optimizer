from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.merchant import advance_merchant_position
from pilgrim.rules.transition import legal_actions
from tests.round_end_helpers import apply_declining_confession


def test_non_round_ending_turn_does_not_run_round_end_phases() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_declining_confession(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert result.state.timing.round_number == scenario.state.timing.round_number
    assert result.state.merchant_board_position == scenario.state.merchant_board_position
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.START_PLAYER_MARKER not in event_types
    assert EventType.EXCESS_RESOURCE_CAP not in event_types
    assert EventType.ROUND_ADVANCE not in event_types
    assert EventType.ALMS_SEASON_END not in event_types


def test_round_ending_turn_runs_expected_sequence_and_state_updates() -> None:
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_declining_confession(scenario.state, action, scenario.config)

    recall_index = _event_index(result.events, EventType.ACOLYTE_RECALL)
    excess_index = _event_index(result.events, EventType.EXCESS_RESOURCE_CAP)
    round_advance_index = _event_index(result.events, EventType.ROUND_ADVANCE)
    merchant_index = _event_index(result.events, EventType.MERCHANT_ADVANCE)
    confession_index = _event_index(result.events, EventType.CONFESSION_BOX_PHASE)
    start_player_index = _event_index(result.events, EventType.START_PLAYER_MARKER)
    turn_advance_index = _event_index(result.events, EventType.TURN_ADVANCE)
    invariant_index = _event_index(result.events, EventType.INVARIANT_CHECK)

    assert recall_index < excess_index
    assert excess_index < round_advance_index
    assert round_advance_index < merchant_index
    assert merchant_index < confession_index
    # The marker now falls on the far side of the turn advance rather than before it, because the
    # turn genuinely advances at that point: the round-ending action stops, having handed the table
    # to the first player owed a Confession Box question, and the marker is awarded by the action
    # that answers the last of them. What is still asserted is the ORDER, which is what this test
    # is about -- the boxes before the marker, since what they buy is the marker.
    assert confession_index < turn_advance_index
    assert turn_advance_index < invariant_index
    assert invariant_index < start_player_index

    assert result.state.timing.round_number == scenario.state.timing.round_number + 1
    assert result.state.timing.turn_in_round == 0
    assert result.state.active_player is result.state.start_player


def test_round_end_excess_caps_stone_and_wheat_with_silver_unchanged() -> None:
    scenario = load_scenario("scenarios/round_end_excess_caps_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution.value == "tithe"
    )
    result = apply_declining_confession(scenario.state, action, scenario.config)

    player_one = result.state.player_state(PlayerId.PLAYER_ONE)
    player_two = result.state.player_state(PlayerId.PLAYER_TWO)
    assert player_one.resources.stone == 6
    assert player_one.resources.wheat == 6
    assert player_one.resources.silver == 9
    assert player_two.resources.stone == 6
    assert player_two.resources.wheat == 6
    assert player_two.resources.silver == 3

    cap_events = [
        event for event in result.events if event.event_type is EventType.EXCESS_RESOURCE_CAP
    ]
    assert len(cap_events) == 2
    details_by_player = {dict(event.details)["player"]: dict(event.details) for event in cap_events}
    assert details_by_player["player_one"]["stone_before"] == 8
    assert details_by_player["player_one"]["stone_after"] == 6
    assert details_by_player["player_one"]["wheat_before"] == 7
    assert details_by_player["player_one"]["wheat_after"] == 6
    assert "stone_before" not in details_by_player["player_two"]
    # Ten held plus the one the tithe took. The cap is what this test is about and it still lands
    # on six, but the figure it caps from now includes the turn's own gain.
    assert details_by_player["player_two"]["wheat_before"] == 11
    assert details_by_player["player_two"]["wheat_after"] == 6


def test_merchant_moves_once_at_round_end_only() -> None:
    non_round_scenario = load_scenario("scenarios/alms_sandbox_001.json")
    non_round_action = legal_actions(non_round_scenario.state, non_round_scenario.config)[0]
    non_round_result = apply_declining_confession(
        non_round_scenario.state,
        non_round_action,
        non_round_scenario.config,
    )
    assert (
        non_round_result.state.merchant_board_position
        == non_round_scenario.state.merchant_board_position
    )
    assert not any(
        event.event_type is EventType.MERCHANT_ADVANCE for event in non_round_result.events
    )

    round_end_scenario = load_scenario("scenarios/round_end_excess_001.json")
    round_end_action = legal_actions(round_end_scenario.state, round_end_scenario.config)[0]
    round_end_result = apply_declining_confession(
        round_end_scenario.state, round_end_action, round_end_scenario.config
    )
    merchant_events = [
        event for event in round_end_result.events if event.event_type is EventType.MERCHANT_ADVANCE
    ]
    assert len(merchant_events) == 1
    # `+ 1` held while the Merchant walked a six-step list and wrapped with modulo. It rides the
    # board ring now, so the step after north_west is north, not a ninth position: ask the ring.
    assert round_end_result.state.merchant_board_position == advance_merchant_position(
        round_end_scenario.state.merchant_board_position, round_end_scenario.config
    )


def test_season_end_scoring_uses_incremented_round_and_orders_events_before_merchant() -> None:
    scenario = load_scenario("scenarios/alms_season_end_unique_leader_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TITHE
    )
    result = apply_declining_confession(scenario.state, action, scenario.config)

    assert result.state.timing.round_number == 10
    round_advance_index = _event_index(result.events, EventType.ROUND_ADVANCE)
    season_end_index = _event_index(result.events, EventType.ALMS_SEASON_END)
    season_reward_index = _event_index(result.events, EventType.ALMS_SEASON_REWARD)
    season_reset_index = _event_index(result.events, EventType.ALMS_RESET)
    merchant_index = _event_index(result.events, EventType.MERCHANT_ADVANCE)
    assert (
        round_advance_index
        < season_end_index
        < season_reward_index
        < season_reset_index
        < merchant_index
    )

    event_types = {event.event_type for event in result.events}
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types


def test_no_season_end_when_round_has_no_pilgrimage_metadata() -> None:
    scenario = load_scenario("scenarios/alms_season_end_no_metadata_no_trigger_001.json")
    action = next(
        candidate
        for candidate in legal_actions(scenario.state, scenario.config)
        if candidate.resolution is TurnResolutionType.TITHE
    )
    result = apply_declining_confession(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.ALMS_SEASON_END not in event_types
    assert EventType.ALMS_SEASON_REWARD not in event_types
    assert EventType.ALMS_RESET not in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.START_PLAYER_MARKER in event_types


def test_setup_sow_turn_does_not_trigger_round_end_phases() -> None:
    scenario = load_scenario("scenarios/setup_sow_2p_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_declining_confession(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert EventType.EXCESS_RESOURCE_CAP not in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.START_PLAYER_MARKER not in event_types
    assert EventType.ROUND_ADVANCE not in event_types


def test_final_game_end_path_does_not_advance_merchant() -> None:
    scenario = load_scenario("scenarios/game_end_nw_site_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_declining_confession(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}

    assert result.state.game_over is True
    assert EventType.GAME_END in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types


def _event_index(events, event_type: EventType) -> int:
    for index, event in enumerate(events):
        if event.event_type is event_type:
            return index
    raise AssertionError(f"Missing event type: {event_type}")
