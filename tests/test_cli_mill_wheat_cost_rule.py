from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _action_index(
    path: str,
    resolution: TurnResolutionType,
    *,
    hired_building_id: str | None = None,
    ordination_steps: tuple[str, ...] | None = None,
    alms_payment_wheat: int | None = None,
) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.resolution is not resolution:
            continue
        if hired_building_id is not None and action.hired_building_id != hired_building_id:
            continue
        if ordination_steps is not None and action.ordination_steps != ordination_steps:
            continue
        if alms_payment_wheat is not None and action.alms_payment_wheat != alms_payment_wheat:
            continue
        return index
    raise AssertionError(f"No matching action found in {path}")


def test_cli_apply_ordination_hired_mill_shows_hire_then_mill_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/ordination_hire_mill_market_three_steps_001.json",
        TurnResolutionType.ORDINATION,
        hired_building_id="mill",
        ordination_steps=("ordain", "ordain", "mission"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/ordination_hire_mill_market_three_steps_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Mill from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: mill waived wheat cost 2 for ordination" in output
    assert (
        output.index("BUILDING_HIRED: player_one hired Mill from market; paid wheat 1 to bank")
        < output.index("BUILDING_BONUS: mill waived wheat cost 2 for ordination")
    )


def test_cli_apply_give_alms_active_mill_shows_waiver_and_net_wheat_delta(capsys) -> None:
    action_index = _action_index(
        "scenarios/give_alms_mill_active_wheat3_spend1_001.json",
        TurnResolutionType.GIVE_ALMS_PAID,
        alms_payment_wheat=3,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/give_alms_mill_active_wheat3_spend1_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_BONUS: mill waived wheat cost 2 for give_alms_paid" in output
    assert "RESOURCE_DELTA: player_one silver -1; wheat -1" in output
    assert (
        "ALMS_PAYMENT: player_one credited silver=0, wheat=3 toward Give Alms; "
        "actual paid silver=0, wheat=1"
    ) in output


def test_cli_apply_give_alms_hired_mill_shows_credited_vs_actual_payment(capsys) -> None:
    action_index = _action_index(
        "scenarios/give_alms_hire_mill_market_wheat3_001.json",
        TurnResolutionType.GIVE_ALMS_PAID,
        hired_building_id="mill",
        alms_payment_wheat=3,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/give_alms_hire_mill_market_wheat3_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Mill from market; paid wheat 1 to bank" in output
    assert "RESOURCE_DELTA: player_one silver -1; wheat -2" in output
    assert (
        "ALMS_PAYMENT: player_one credited silver=0, wheat=3 toward Give Alms; "
        "actual paid silver=0, wheat=1"
    ) in output


def test_cli_apply_give_alms_without_mill_keeps_paid_wording(capsys) -> None:
    action_index = _action_index(
        "scenarios/give_alms_paid_001.json",
        TurnResolutionType.GIVE_ALMS_PAID,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/give_alms_paid_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ALMS_PAYMENT: player_one paid silver=" in output
    assert "credited silver=" not in output
