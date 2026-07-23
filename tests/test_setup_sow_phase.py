from __future__ import annotations

import json
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, SetupSowAction
from pilgrim.model.enums import EventType, PlayerId, TurnPhase
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import TransitionValidationError, validate_state_invariants
from pilgrim.setup.generator import generate_setup_scenario


def test_setup_sow_phase_generates_only_setup_sow_actions() -> None:
    scenario = load_scenario("scenarios/setup_sow_2p_001.json")

    actions = legal_actions(scenario.state, scenario.config)

    assert actions
    assert all(isinstance(action, SetupSowAction) for action in actions)
    assert all(action.origin == 0 for action in actions)
    assert all(len(action.route) == 5 for action in actions)
    assert all(not isinstance(action, FullTurnAction) for action in actions)


def test_setup_sow_apply_advances_without_full_turn_side_effects() -> None:
    scenario = load_scenario("scenarios/setup_sow_2p_001.json")
    before = scenario.state
    action = legal_actions(before, scenario.config)[0]

    result = apply_action(before, action, scenario.config)
    after = result.state

    assert after.phase is TurnPhase.SETUP_SOW
    assert after.active_player is PlayerId.PLAYER_TWO
    assert after.setup_sow_required is True
    assert after.setup_sow_complete is False
    assert after.setup_sow_completed_by == (PlayerId.PLAYER_ONE,)
    assert after.timing == before.timing
    assert after.turn == before.turn
    assert after.player_vector(PlayerId.PLAYER_ONE)[0] < before.player_vector(PlayerId.PLAYER_ONE)[0]

    event_types = {event.event_type for event in result.events}
    assert EventType.SETUP_SOWING in event_types
    assert EventType.SETUP_SOW_COMPLETE in event_types
    assert EventType.SETUP_PLAYER_ADVANCE in event_types
    assert EventType.INVARIANT_CHECK in event_types
    assert EventType.DUTY_RESOLUTION not in event_types
    assert EventType.ACOLYTE_RECALL not in event_types
    assert EventType.TURN_ADVANCE not in event_types
    assert EventType.ROUND_END not in event_types
    assert EventType.MERCHANT_ADVANCE not in event_types
    assert EventType.SHIP_ADVANCE not in event_types


def test_final_setup_sow_marks_complete_and_restores_normal_phase() -> None:
    scenario = load_scenario("scenarios/setup_sow_complete_001.json")
    before = scenario.state
    action = legal_actions(before, scenario.config)[0]

    result = apply_action(before, action, scenario.config)
    after = result.state

    assert after.setup_sow_required is True
    assert after.setup_sow_complete is True
    assert after.setup_sow_completed_by == (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO)
    assert after.phase is TurnPhase.SOW
    assert after.active_player is PlayerId.PLAYER_ONE
    assert after.active_player is after.start_player
    assert after.timing == before.timing
    assert EventType.SETUP_COMPLETE in {event.event_type for event in result.events}
    assert EventType.SETUP_PLAYER_ADVANCE not in {
        event.event_type for event in result.events
    }

    next_actions = legal_actions(after, scenario.config)
    assert next_actions
    assert isinstance(next_actions[0], FullTurnAction)


def test_setup_sow_generated_like_fixture_validates_and_exposes_setup_actions() -> None:
    scenario = load_scenario("scenarios/setup_sow_generated_like_001.json")

    validate_state_invariants(scenario.state)
    actions = legal_actions(scenario.state, scenario.config)

    assert actions
    assert isinstance(actions[0], SetupSowAction)


def test_setup_sow_3p_fixture_validates_and_exposes_setup_actions() -> None:
    scenario = load_scenario("scenarios/setup_sow_3p_001.json")

    validate_state_invariants(scenario.state)
    actions = legal_actions(scenario.state, scenario.config)

    assert actions
    assert isinstance(actions[0], SetupSowAction)


def test_generated_metadata_fallback_enters_setup_sow_without_explicit_setup_state(
    tmp_path: Path,
) -> None:
    generated = generate_setup_scenario(player_count=2, seed=123)
    repo_root = Path.cwd().resolve()
    for field in (
        "board_file",
        "duties_file",
        "piety_file",
        "alms_file",
        "timing_file",
        "merchant_file",
        "ship_file",
        "buildings_file",
    ):
        generated[field] = str((repo_root / str(generated[field])).resolve())  # type: ignore[index]
    initial_state = generated["initial_state"]  # type: ignore[index]
    initial_state.pop("setup", None)
    initial_state["phase"] = "sow"
    scenario_path = tmp_path / "generated_metadata_fallback.json"
    scenario_path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")

    loaded = load_scenario(scenario_path)

    assert loaded.state.setup_sow_required is True
    assert loaded.state.setup_sow_complete is False
    assert loaded.state.setup_sow_completed_by == ()
    assert loaded.state.phase is TurnPhase.SETUP_SOW


def test_legacy_non_setup_scenario_defaults_to_normal_play() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_001.json")

    assert scenario.state.setup_sow_required is False
    assert scenario.state.setup_sow_complete is True
    assert scenario.state.setup_sow_completed_by == ()
    assert scenario.state.phase is TurnPhase.SOW


def test_setup_validation_fails_when_incomplete_player_has_no_city_acolytes() -> None:
    scenario = load_scenario("scenarios/setup_sow_2p_001.json")
    invalid_state = scenario.state.with_player_vector(
        PlayerId.PLAYER_ONE,
        (0, 0, 0, 0, 0, 0, 0, 0, 0),
    )

    with pytest.raises(
        TransitionValidationError,
        match="must have at least 1 city acolyte",
    ):
        validate_state_invariants(invalid_state)
