from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _customs_house_action_index(
    scenario_path: str,
    *,
    source: str,
    resolution: TurnResolutionType,
    taxation_step1_resource: str | None = None,
    taxation_step2_resources: tuple[str, ...] | None = None,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.taxation_majority_building_id != "customs_house":
            continue
        if action.taxation_majority_building_source != source:
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
    raise AssertionError(f"No matching Customs House action found in {scenario_path}.")


def test_cli_apply_own_active_customs_house_shows_bonus_before_sowing(capsys) -> None:
    action_index = _customs_house_action_index(
        "scenarios/customs_house_active_taxation_majority_001.json",
        source="own_active",
        resolution=TurnResolutionType.TAXATION,
        taxation_step1_resource="wheat",
        taxation_step2_resources=("stone", "silver"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/customs_house_active_taxation_majority_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert (
        "BUILDING_BONUS: customs_house claimed Taxation majority on occupied Duty tiles this turn"
        in output
    )
    assert "SOWING: picked up 1 from city; route city -> north" in output
    assert (
        "DUTY_RESOLUTION: selected north (taxation); relation majority; duty value 2; "
        "silver cost 0; action taxation"
    ) in output
    assert output.index(
        "BUILDING_BONUS: customs_house claimed Taxation majority on occupied Duty tiles this turn"
    ) < output.index("SOWING: picked up 1 from city; route city -> north")


def test_cli_legal_actions_do_not_fold_market_customs_house_hire_into_an_action(capsys) -> None:
    exit_code = main(["legal-actions", "scenarios/customs_house_hire_market_taxation_majority_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "use building: customs_house for Taxation majority on occupied Duty tiles" not in output
    assert "hire building: customs_house from market" not in output


def test_cli_legal_actions_do_not_fold_opponent_customs_house_hire_into_an_action(capsys) -> None:
    exit_code = main(["legal-actions", "scenarios/customs_house_hire_opponent_taxation_majority_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "use building: customs_house for Taxation majority on occupied Duty tiles" not in output
    assert "hire building: customs_house from player_two" not in output


def test_cli_apply_customs_house_beats_larger_stack_for_selected_taxation(capsys) -> None:
    action_index = _customs_house_action_index(
        "scenarios/customs_house_active_taxation_beats_larger_stack_001.json",
        source="own_active",
        resolution=TurnResolutionType.TAXATION,
        taxation_step1_resource="wheat",
        taxation_step2_resources=("stone", "silver"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/customs_house_active_taxation_beats_larger_stack_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "DUTY_RESOLUTION: selected north (taxation); relation majority; duty value 2; "
        "silver cost 0; action taxation"
    ) in output
    assert "TAXATION: player_one took bonus resources stone, silver from other majority duty tiles" in output


def test_cli_legal_actions_customs_house_not_generated_for_non_taxation_turn(capsys) -> None:
    exit_code = main(["legal-actions", "scenarios/customs_house_no_taxation_no_modifier_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "use building: customs_house for Taxation majority on occupied Duty tiles" not in output
