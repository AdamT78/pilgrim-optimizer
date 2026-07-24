from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _action_index(
    path: str,
    resolution: TurnResolutionType,
    *,
    steps=None,
    moves=None,
    hired_building_id: str | None = None,
) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.resolution is not resolution:
            continue
        if steps is not None and action.ordination_steps != steps:
            continue
        if moves is not None and len(action.allocation_moves) != moves:
            continue
        if hired_building_id is not None and action.hired_building_id != hired_building_id:
            continue
        return index
    raise AssertionError(f"No matching action found in {path}")


def test_cli_apply_allocation_infirmary_shows_effective_duty_value_and_building_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/allocation_infirmary_001.json",
        TurnResolutionType.ALLOCATION,
        moves=2,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/allocation_infirmary_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "DUTY_RESOLUTION: selected north_west (allocation); relation parity; duty value 1; "
        "effective duty value 2; silver cost 0; action allocation"
    ) in output
    assert "BUILDING_BONUS: infirmary added duty value +1 to allocation" in output
    assert (
        output.index("BUILDING_BONUS: infirmary added duty value +1 to allocation")
        < output.index("ALLOCATION: player_one moved 1 acolyte abbey -> fields")
    )


def test_cli_apply_ordination_infirmary_extra_step_shows_bonus_and_effective_duty_value(capsys) -> None:
    action_index = _action_index(
        "scenarios/ordination_infirmary_extra_step_001.json",
        TurnResolutionType.ORDINATION,
        steps=("ordain", "mission"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/ordination_infirmary_extra_step_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "DUTY_RESOLUTION: selected south_west (ordination); relation parity; duty value 1; "
        "effective duty value 2; silver cost 0; action ordination"
    ) in output
    assert (
        "BUILDING_BONUS: infirmary added duty value +1 to ordination; extra wheat cost paid"
    ) in output
    assert "ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1" in output
    assert "ORDINATION: player_one sent 1 acolyte abbey -> city; paid wheat=1" in output
    assert (
        output.index("BUILDING_BONUS: infirmary added duty value +1 to ordination; extra wheat cost paid")
        < output.index("ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1")
    )


def test_cli_apply_ordination_infirmary_base_step_without_extra_has_no_infirmary_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/ordination_infirmary_insufficient_wheat_001.json",
        TurnResolutionType.ORDINATION,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/ordination_infirmary_insufficient_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "DUTY_RESOLUTION: selected south_west (ordination); relation parity; duty value 1; "
        "silver cost 0; action ordination"
    ) in output
    assert "effective duty value 2" not in output
    assert "infirmary added duty value +1 to ordination" not in output


def test_cli_apply_allocation_hired_infirmary_shows_hired_then_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/allocation_hire_infirmary_market_001.json",
        TurnResolutionType.ALLOCATION,
        moves=2,
        hired_building_id="infirmary",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/allocation_hire_infirmary_market_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Infirmary from market; paid wheat 1 to bank"
    ) in output
    assert "BUILDING_BONUS: infirmary added duty value +1 to allocation" in output
    assert (
        output.index("BUILDING_HIRED: player_one hired Infirmary from market; paid wheat 1 to bank")
        < output.index("BUILDING_BONUS: infirmary added duty value +1 to allocation")
    )


def test_cli_apply_ordination_hired_infirmary_shows_hired_then_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/ordination_hire_infirmary_market_extra_step_001.json",
        TurnResolutionType.ORDINATION,
        steps=("ordain", "mission"),
        hired_building_id="infirmary",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/ordination_hire_infirmary_market_extra_step_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Infirmary from market; paid wheat 1 to bank"
    ) in output
    assert (
        "BUILDING_BONUS: infirmary added duty value +1 to ordination; extra wheat cost paid"
    ) in output
    assert (
        output.index("BUILDING_HIRED: player_one hired Infirmary from market; paid wheat 1 to bank")
        < output.index(
            "BUILDING_BONUS: infirmary added duty value +1 to ordination; extra wheat cost paid"
        )
    )
