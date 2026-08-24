from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import EndTurnAction, action_id
from pilgrim.model.enums import EventType, TurnPhase, TurnResolutionType
from pilgrim.rules.transition import (
    apply_action,
    apply_turn_step,
    full_turn_actions,
    legal_actions,
    turn_steps,
)


def _devotion_action(state, config):
    return next(
        action
        for action in legal_actions(state, config)
        if action.resolution is TurnResolutionType.CLERICAL_DEVOTION
    )


def test_devotion_keeps_the_turn_open_for_a_conversion_then_end_turn_passes() -> None:
    scenario = load_scenario("scenarios/indulgences_active_sell_piety_001.json")
    before = replace(
        scenario.state,
        turn_progress=replace(
            scenario.state.turn_progress,
            used_buildings=frozenset({"grain_store"}),
        ),
    )
    action = _devotion_action(before, scenario.config)

    resolution = apply_action(before, action, scenario.config)
    committed = resolution.state

    assert committed.active_player is before.active_player
    assert committed.phase is TurnPhase.SOW
    assert committed.turn == before.turn
    assert committed.turn_progress.resolution_committed is True
    assert committed.turn_progress.used_buildings == frozenset({"grain_store"})
    assert turn_steps(committed, scenario.config)
    assert legal_actions(committed, scenario.config) == (EndTurnAction(),)
    assert tuple(full_turn_actions(committed, scenario.config)) == (EndTurnAction(),)

    sell_gained_piety = next(
        step
        for step in turn_steps(committed, scenario.config)
        if step.direction == "sell_piety" and step.amount == 1
    )
    after_conversion = apply_turn_step(committed, scenario.config, sell_gained_piety)
    player_after_conversion = after_conversion.player_state(before.active_player)
    player_before = before.player_state(before.active_player)
    assert player_after_conversion.piety == player_before.piety
    assert player_after_conversion.resources.silver == player_before.resources.silver + 1

    ended = apply_action(after_conversion, EndTurnAction(), scenario.config)
    assert ended.state.active_player is not before.active_player
    assert ended.state.turn == before.turn + 1
    assert ended.state.turn_progress.resolution_committed is False
    assert ended.state.phase is TurnPhase.SOW
    assert legal_actions(ended.state, scenario.config) != (EndTurnAction(),)


@pytest.mark.parametrize(
    "scenario_path",
    [
        "scenarios/produce_wheat_001.json",
        "scenarios/clerical_devotion_chapel_001.json",
        "scenarios/indulgences_not_live_no_conversion_001.json",
    ],
)
def test_resolution_without_a_conversion_defers_the_old_immediate_pass(
    scenario_path: str,
) -> None:
    scenario = load_scenario(scenario_path)
    before = scenario.state
    action = legal_actions(before, scenario.config)[0]

    resolution = apply_action(before, action, scenario.config)

    assert resolution.state.turn == before.turn
    assert resolution.state.active_player is before.active_player
    assert resolution.state.phase is TurnPhase.SOW
    assert resolution.state.turn_progress.resolution_committed is True
    assert not turn_steps(resolution.state, scenario.config)
    assert legal_actions(resolution.state, scenario.config) == (EndTurnAction(),)
    assert EventType.TURN_ADVANCE not in {event.event_type for event in resolution.events}

    expected_turn = resolution.state.next_player_turn()
    passed = apply_action(resolution.state, EndTurnAction(), scenario.config)

    assert passed.state == expected_turn
    assert EventType.TURN_ADVANCE in {event.event_type for event in passed.events}


def test_round_end_effects_wait_for_end_turn_and_award_the_marker_at_the_pass() -> None:
    scenario = load_scenario("scenarios/indulgences_active_sell_piety_001.json")
    round_ending_state = replace(
        scenario.state,
        timing=replace(scenario.state.timing, turn_in_round=1),
    )
    resolution = apply_action(
        round_ending_state,
        _devotion_action(round_ending_state, scenario.config),
        scenario.config,
    )

    resolution_event_types = [event.event_type for event in resolution.events]
    assert resolution.state.first_player_marker is None
    assert EventType.ROUND_ADVANCE not in resolution_event_types
    assert EventType.START_PLAYER_MARKER not in resolution_event_types
    assert EventType.TURN_ADVANCE not in resolution_event_types
    assert all(event.action_id != action_id(EndTurnAction()) for event in resolution.events)

    passed = apply_action(resolution.state, EndTurnAction(), scenario.config)
    passed_event_types = [event.event_type for event in passed.events]
    assert EventType.ROUND_ADVANCE in passed_event_types
    assert EventType.START_PLAYER_MARKER in passed_event_types
    assert passed.state.first_player_marker is not None
    assert all(event.action_id == action_id(EndTurnAction()) for event in passed.events)
    assert passed_event_types.index(EventType.START_PLAYER_MARKER) < passed_event_types.index(
        EventType.TURN_ADVANCE
    )


def test_game_ending_round_end_opens_window_then_pass_ends_game() -> None:
    scenario = load_scenario("scenarios/game_end_nw_site_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]

    resolution = apply_action(scenario.state, action, scenario.config)

    assert resolution.state.game_over is False
    assert resolution.state.turn_progress.resolution_committed is True
    assert legal_actions(resolution.state, scenario.config) == (EndTurnAction(),)

    passed = apply_action(resolution.state, EndTurnAction(), scenario.config)

    assert passed.state.game_over is True
    assert legal_actions(passed.state, scenario.config) == ()


def test_final_game_ending_window_keeps_conversion_usable_before_pass() -> None:
    scenario = load_scenario("scenarios/game_end_nw_site_001.json")
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    state = scenario.state.with_player_state(
        player,
        replace(
            player_state,
            # Give Alms donates Library; Indulgences must remain active in the final window.
            player_board_slots=replace(
                player_state.player_board_slots,
                active_buildings=("library", "indulgences"),
            ),
        ),
    )
    action = next(
        candidate
        for candidate in legal_actions(state, scenario.config)
        if candidate.donate_building_id == "library"
    )

    resolution = apply_action(state, action, scenario.config)
    sell_one_piety = next(
        step
        for step in turn_steps(resolution.state, scenario.config)
        if step.building_id == "indulgences" and step.direction == "sell_piety" and step.amount == 1
    )

    with_conversion = apply_action(
        apply_turn_step(resolution.state, scenario.config, sell_one_piety),
        EndTurnAction(),
        scenario.config,
    )
    without_conversion = apply_action(resolution.state, EndTurnAction(), scenario.config)

    converted_player = with_conversion.state.player_state(player)
    passed_player = without_conversion.state.player_state(player)
    assert with_conversion.state.game_over is True
    assert without_conversion.state.game_over is True
    assert converted_player.resources != passed_player.resources
    assert converted_player.resources.silver == passed_player.resources.silver + 1
    assert converted_player.piety == passed_player.piety - 1
