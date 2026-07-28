from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _pulpit_action_index(
    scenario_path: str,
    *,
    source: str,
    resolution: TurnResolutionType,
    ordination_steps: tuple[str, ...] | None = None,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.workforce_move_building_id != "pulpit":
            continue
        if action.workforce_move_building_source != source:
            continue
        if action.resolution is not resolution:
            continue
        if ordination_steps is not None and action.ordination_steps != ordination_steps:
            continue
        return index
    raise AssertionError(f"No matching Pulpit action found in {scenario_path}.")


def test_cli_apply_own_active_pulpit_shows_bonus_and_workforce_move_before_sowing(capsys) -> None:
    action_index = _pulpit_action_index(
        "scenarios/pulpit_active_move_serf_001.json",
        source="own_active",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/pulpit_active_move_serf_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free") < output.index(
        "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit"
    )
    assert output.index(
        "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit"
    ) < output.index("SOWING: picked up 1 from north; route north -> north_east")


def test_cli_apply_market_hired_pulpit_shows_hire_then_bonus_then_move(capsys) -> None:
    action_index = _pulpit_action_index(
        "scenarios/pulpit_hire_market_move_serf_001.json",
        source="market",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/pulpit_hire_market_move_serf_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Pulpit from market; paid wheat 1 to bank"
        in output
    )
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Pulpit from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free")
    assert output.index("BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free") < output.index(
        "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit"
    )


def test_cli_apply_opponent_hired_pulpit_shows_owner_payment(capsys) -> None:
    action_index = _pulpit_action_index(
        "scenarios/pulpit_hire_opponent_move_serf_001.json",
        source="player_two",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/pulpit_hire_opponent_move_serf_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Pulpit from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output


def test_cli_apply_pulpit_with_infirmary_still_shows_paid_ordination_steps(capsys) -> None:
    action_index = _pulpit_action_index(
        "scenarios/pulpit_infirmary_does_not_double_free_move_001.json",
        source="own_active",
        resolution=TurnResolutionType.ORDINATION,
        ordination_steps=("ordain", "mission"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/pulpit_infirmary_does_not_double_free_move_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_BONUS: pulpit moved 1 serf village -> abbey for free" in output
    assert "WORKFORCE_MOVE: player_one moved 1 serf village -> abbey for free with Pulpit" in output
    assert "ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1" in output
    assert "ORDINATION: player_one sent 1 acolyte abbey -> city; paid wheat=1" in output
