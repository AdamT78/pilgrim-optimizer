from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import EventType, PlayerId
from pilgrim.rules.timing import advance_timing, is_round_end
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants


def _event_types(path: str) -> tuple[set[EventType], object]:
    scenario = load_scenario(path)
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    return {event.event_type for event in result.events}, result


def test_advance_timing_non_round_end_increments_turn_and_active_player() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")
    result = advance_timing(scenario.state, scenario.config.timing, action_id="timing:normal")
    assert result.state.timing.absolute_turn == scenario.state.timing.absolute_turn + 1
    assert result.state.timing.turn_in_round == 1
    assert result.state.active_player is PlayerId.PLAYER_TWO
    assert result.round_ended is False
    assert [event.event_type for event in result.events] == [EventType.TURN_ADVANCE]


def test_advance_timing_round_end_emits_round_end_without_round_advance() -> None:
    scenario = load_scenario("scenarios/round_end_excess_001.json")
    assert is_round_end(scenario.state.timing, scenario.config.timing) is True
    result = advance_timing(scenario.state, scenario.config.timing, action_id="timing:round_end")
    assert result.round_ended is True
    event_types = {event.event_type for event in result.events}
    assert EventType.TURN_ADVANCE in event_types
    assert EventType.ROUND_END in event_types
    assert EventType.ROUND_ADVANCE not in event_types
    assert result.state.timing.round_number == scenario.state.timing.round_number


def test_non_round_ending_turn_does_not_advance_merchant_or_ship() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}
    assert EventType.TURN_ADVANCE in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.SHIP_ADVANCE not in event_types
    assert result.state.merchant_position == scenario.state.merchant_position
    assert result.state.ship_position == scenario.state.ship_position


def test_round_end_emits_excess_ship_merchant_start_player_and_round_advance() -> None:
    event_types, result = _event_types("scenarios/round_end_excess_001.json")
    assert EventType.ROUND_END in event_types
    assert EventType.EXCESS_DISCARD in event_types
    assert EventType.SHIP_ADVANCE in event_types
    assert EventType.MERCHANT_ADVANCE in event_types
    assert EventType.START_PLAYER_SELECTION in event_types
    assert EventType.ROUND_ADVANCE in event_types
    assert EventType.SEASON_END not in event_types
    assert EventType.DUMMY_ACOLYTE_MOVE not in event_types
    assert result.state.ship_position == 2
    assert result.state.merchant_position == 1
    assert result.state.start_player is PlayerId.PLAYER_TWO
    assert result.state.timing.round_number == 3


def test_round_end_excess_caps_stone_and_wheat_only() -> None:
    scenario = load_scenario("scenarios/round_end_excess_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    player_one = result.state.player_state(PlayerId.PLAYER_ONE)
    player_two = result.state.player_state(PlayerId.PLAYER_TWO)
    assert player_one.resources.stone == 6
    assert player_one.resources.wheat == 6
    assert player_one.resources.silver == 5
    assert player_two.resources.stone == 6
    assert player_two.resources.wheat == 4


def test_season_end_is_triggered_by_ship_and_runs_alms_and_dummy_phases() -> None:
    event_types, result = _event_types("scenarios/season_end_alms_001.json")
    assert EventType.SHIP_ADVANCE in event_types
    assert EventType.SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.DUMMY_ACOLYTE_MOVE in event_types
    assert EventType.SEASON_ADVANCE in event_types
    assert result.state.ship_position == 4
    assert result.state.game_over is False
    assert result.state.timing.season_number == 2
    assert result.state.player_state(PlayerId.PLAYER_ONE).workforce.committed.alms_table == 1


def test_game_end_triggers_on_final_nw_return_and_blocks_future_actions() -> None:
    scenario = load_scenario("scenarios/game_end_nw_site_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}
    assert EventType.SHIP_ADVANCE in event_types
    assert EventType.SEASON_END in event_types
    assert EventType.ALMS_SEASON_REWARD in event_types
    assert EventType.ALMS_RESET in event_types
    assert EventType.DUMMY_ACOLYTE_MOVE not in event_types
    assert EventType.GAME_END in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert result.state.ship_position == 0
    assert result.state.game_over is True
    assert legal_actions(result.state, scenario.config) == ()


def test_start_player_tie_break_chooses_clockwise_away_from_current_holder() -> None:
    scenario = load_scenario("scenarios/start_player_selection_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    event_types = {event.event_type for event in result.events}
    assert EventType.START_PLAYER_TIE_BREAK in event_types
    assert EventType.START_PLAYER_SELECTION in event_types
    assert result.state.start_player is PlayerId.PLAYER_TWO
    assert result.state.active_player is PlayerId.PLAYER_TWO


def test_scenarios_validate_with_round_end_state_fields() -> None:
    for path in (
        "scenarios/mancala_sandbox_001.json",
        "scenarios/alms_sandbox_001.json",
        "scenarios/season_end_alms_001.json",
        "scenarios/round_end_excess_001.json",
        "scenarios/game_end_nw_site_001.json",
        "scenarios/start_player_selection_001.json",
    ):
        scenario = load_scenario(path)
        validate_state_invariants(scenario.state)
