from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _scriptorium_action_index(
    scenario_path: str,
    *,
    source: str,
    resolution: TurnResolutionType,
    taxation_step1_resource: str | None = None,
    taxation_step2_resources: tuple[str, ...] | None = None,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.effective_acolyte_building_id != "scriptorium":
            continue
        if action.effective_acolyte_building_source != source:
            continue
        if action.resolution is not resolution:
            continue
        if (
            taxation_step1_resource is not None
            and action.taxation_step1_resource != taxation_step1_resource
        ):
            continue
        if (
            taxation_step2_resources is not None
            and action.taxation_step2_resources != taxation_step2_resources
        ):
            continue
        return index
    raise AssertionError(f"No matching Scriptorium action found in {scenario_path}.")


def test_cli_apply_own_active_scriptorium_shows_bonus_before_sowing(capsys) -> None:
    action_index = _scriptorium_action_index(
        "scenarios/scriptorium_active_majority_selected_duty_001.json",
        source="own_active",
        resolution=TurnResolutionType.CLERICAL_DEVOTION,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/scriptorium_active_majority_selected_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert (
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
        in output
    )
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert (
        "DUTY_RESOLUTION: selected north_east (clerical); relation majority; duty value 2; "
        "silver cost 0; action clerical_devotion"
    ) in output
    assert output.index(
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
    ) < output.index("SOWING: picked up 1 from north; route north -> north_east")


def test_cli_apply_market_hired_scriptorium_shows_hire_then_bonus(capsys) -> None:
    action_index = _scriptorium_action_index(
        "scenarios/scriptorium_hire_market_majority_selected_duty_001.json",
        source="market",
        resolution=TurnResolutionType.CLERICAL_DEVOTION,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/scriptorium_hire_market_majority_selected_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Scriptorium from market; paid wheat 1 to bank"
        in output
    )
    assert (
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
        in output
    )
    assert output.index(
        "BUILDING_HIRED: player_one hired Scriptorium from market; paid wheat 1 to bank"
    ) < output.index(
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
    )


def test_cli_apply_opponent_hired_scriptorium_shows_owner_payment(capsys) -> None:
    action_index = _scriptorium_action_index(
        "scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json",
        source="player_two",
        resolution=TurnResolutionType.CLERICAL_DEVOTION,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Scriptorium from player_two; paid silver 1 to player_two"
        in output
    )
    assert (
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
        in output
    )


def test_cli_apply_scriptorium_taxation_shows_majority_and_step2_bonus(capsys) -> None:
    action_index = _scriptorium_action_index(
        "scenarios/scriptorium_taxation_majority_other_tiles_001.json",
        source="own_active",
        resolution=TurnResolutionType.TAXATION,
        taxation_step1_resource="wheat",
        taxation_step2_resources=("stone", "silver"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/scriptorium_taxation_majority_other_tiles_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_BONUS: scriptorium added +1 effective acolyte on occupied Duty tiles this turn"
        in output
    )
    assert (
        "DUTY_RESOLUTION: selected north (taxation); relation majority; duty value 2; "
        "silver cost 0; action taxation"
    ) in output
    assert "TAXATION: player_one took bonus resources stone, silver from other majority duty tiles" in output

