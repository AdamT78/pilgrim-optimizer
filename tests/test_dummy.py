import json
from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.dummy import DummyAcolyteGroups
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.dummy import move_dummy_acolytes_end_of_season, seed_dummy_groups
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants


def test_seed_dummy_groups_two_player_setup() -> None:
    groups = seed_dummy_groups(2)
    assert groups.north_group == (0, 1, 1, 1, 0, 0, 0, 0, 0)
    assert groups.south_group == (0, 0, 0, 0, 0, 1, 1, 1, 0)
    assert groups.total_count == 6
    assert groups.total_vector[0] == 0


def test_seed_dummy_groups_three_player_setup() -> None:
    groups = seed_dummy_groups(3)
    assert groups.north_group == (0, 1, 1, 0, 0, 0, 0, 0, 0)
    assert groups.south_group == (0, 0, 0, 0, 0, 1, 1, 0, 0)
    assert groups.total_count == 4
    assert groups.total_vector[0] == 0


def test_seed_dummy_groups_four_player_setup_is_empty() -> None:
    groups = seed_dummy_groups(4)
    assert groups.north_group == (0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert groups.south_group == (0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert groups.total_count == 0


def test_dummy_defaults_from_player_count_for_scenarios() -> None:
    scenario_2p = load_scenario("scenarios/dummy_2p_setup_001.json")
    assert scenario_2p.state.table_player_count == 2
    assert scenario_2p.state.dummy_acolytes.north_total == 3
    assert scenario_2p.state.dummy_acolytes.south_total == 3

    scenario_3p = load_scenario("scenarios/dummy_3p_setup_001.json")
    assert scenario_3p.state.table_player_count == 3
    assert scenario_3p.state.dummy_acolytes.north_total == 2
    assert scenario_3p.state.dummy_acolytes.south_total == 2


def test_dummy_defaults_to_empty_for_four_player_count(tmp_path: Path) -> None:
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    initial_state = json.loads(json.dumps(setup_raw["initial_state"]))
    initial_state.pop("dummy_acolytes", None)
    scenario_path = tmp_path / "dummy_4p.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "dummy_4p",
                "board_file": str(Path("configs/board.json").resolve()),
                "duties_file": str(Path("configs/duties.json").resolve()),
                "piety_file": str(Path("configs/piety.json").resolve()),
                "alms_file": str(Path("configs/alms.json").resolve()),
                "timing_file": str(Path("configs/timing.json").resolve()),
                "merchant_file": str(Path("configs/merchant.json").resolve()),
                "ship_file": str(Path("configs/ship.json").resolve()),
                "player_count": 4,
                "initial_state": initial_state,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_scenario(scenario_path)
    assert loaded.state.dummy_total == 0


def test_explicit_dummy_groups_can_be_loaded_from_scenario(tmp_path: Path) -> None:
    setup_raw = json.loads(Path("configs/setups/basic_mancala_sandbox.json").read_text())
    initial_state = json.loads(json.dumps(setup_raw["initial_state"]))
    initial_state["dummy_acolytes"] = {
        "north_group": [0, 1, 1, 1, 0, 0, 0, 0, 0],
        "south_group": [0, 0, 0, 0, 0, 1, 1, 1, 0],
    }

    scenario_path = tmp_path / "dummy_explicit.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "dummy_explicit",
                "board_file": str(Path("configs/board.json").resolve()),
                "duties_file": str(Path("configs/duties.json").resolve()),
                "piety_file": str(Path("configs/piety.json").resolve()),
                "alms_file": str(Path("configs/alms.json").resolve()),
                "timing_file": str(Path("configs/timing.json").resolve()),
                "merchant_file": str(Path("configs/merchant.json").resolve()),
                "ship_file": str(Path("configs/ship.json").resolve()),
                "player_count": 2,
                "initial_state": initial_state,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_scenario(scenario_path)
    assert loaded.state.dummy_acolytes.north_group == (0, 1, 1, 1, 0, 0, 0, 0, 0)
    assert loaded.state.dummy_acolytes.south_group == (0, 0, 0, 0, 0, 1, 1, 1, 0)


def test_dummy_affects_duty_strength_in_transition() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    give_alms_action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.GIVE_ALMS
    )
    result = apply_action(scenario.state, give_alms_action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    details = dict(duty_event.details)
    assert details["strength"] == "parity"
    assert details["duty_value"] == 1


def test_end_of_season_dummy_move_for_two_player_setup() -> None:
    scenario = load_scenario("scenarios/dummy_2p_setup_001.json")
    moved_state, events = move_dummy_acolytes_end_of_season(
        scenario.state,
        actor=PlayerId.PLAYER_ONE,
        action_id="dummy:test",
    )
    assert moved_state.dummy_acolytes.north_group == (0, 0, 1, 1, 1, 0, 0, 0, 0)
    assert moved_state.dummy_acolytes.south_group == (0, 0, 0, 0, 0, 0, 1, 1, 1)
    moves = {
        (
            str(dict(event.details)["group"]),
            int(dict(event.details)["from_position"]),
            int(dict(event.details)["to_position"]),
        )
        for event in events
    }
    assert ("north_group", 1, 4) in moves
    assert ("south_group", 5, 8) in moves


def test_end_of_season_dummy_move_for_three_player_setup() -> None:
    scenario = load_scenario("scenarios/dummy_3p_setup_001.json")
    moved_state, events = move_dummy_acolytes_end_of_season(
        scenario.state,
        actor=PlayerId.PLAYER_ONE,
        action_id="dummy:test",
    )
    assert moved_state.dummy_acolytes.north_group == (0, 0, 1, 1, 0, 0, 0, 0, 0)
    assert moved_state.dummy_acolytes.south_group == (0, 0, 0, 0, 0, 0, 1, 1, 0)
    assert len(events) == 2


def test_dummy_season_movement_wraps_clockwise() -> None:
    scenario = load_scenario("scenarios/dummy_2p_setup_001.json")
    wrapped_state = scenario.state.with_dummy_acolytes(
        DummyAcolyteGroups(
            north_group=(0, 1, 0, 0, 0, 0, 0, 1, 1),
            south_group=scenario.state.dummy_acolytes.south_group,
        )
    )
    moved_state, _ = move_dummy_acolytes_end_of_season(
        wrapped_state,
        actor=PlayerId.PLAYER_ONE,
        action_id="dummy:test",
    )
    assert moved_state.dummy_acolytes.north_group == (0, 0, 1, 0, 0, 0, 0, 1, 1)


def test_season_end_transition_emits_dummy_moves_and_conserves_totals() -> None:
    scenario = load_scenario("scenarios/dummy_season_move_001.json")
    before = scenario.state
    action = legal_actions(before, scenario.config)[0]
    result = apply_action(before, action, scenario.config)

    event_types = [event.event_type for event in result.events]
    assert EventType.SEASON_END in event_types
    assert EventType.DUMMY_ACOLYTE_MOVE in event_types
    assert event_types.count(EventType.DUMMY_ACOLYTE_MOVE) == 2
    assert result.state.dummy_acolytes.north_group == (0, 0, 1, 1, 1, 0, 0, 0, 0)
    assert result.state.dummy_acolytes.south_group == (0, 0, 0, 0, 0, 0, 1, 1, 1)
    assert result.state.dummy_total == before.dummy_total


def test_dummy_movement_does_not_happen_on_non_season_turn() -> None:
    scenario = load_scenario("scenarios/alms_sandbox_001.json")
    action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, action, scenario.config)
    assert not any(
        event.event_type is EventType.DUMMY_ACOLYTE_MOVE for event in result.events
    )


def test_dummy_scenarios_validate() -> None:
    for path in (
        "scenarios/dummy_2p_setup_001.json",
        "scenarios/dummy_3p_setup_001.json",
        "scenarios/dummy_season_move_001.json",
    ):
        scenario = load_scenario(path)
        validate_state_invariants(scenario.state)
