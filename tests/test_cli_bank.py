from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _bank_action_index(
    scenario_path: str,
    *,
    source: str,
    replaced_resource: str,
    silver_amount: int,
    resolution: TurnResolutionType,
    ordination_steps: tuple[str, ...] | None = None,
    free_hire_target: str | None = None,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if not isinstance(action, FullTurnAction):
            continue
        if action.bank_payment_building_id != "bank":
            continue
        if action.bank_payment_building_source != source:
            continue
        if action.bank_payment_replaced_resource != replaced_resource:
            continue
        if action.bank_payment_silver_amount != silver_amount:
            continue
        if action.resolution is not resolution:
            continue
        if ordination_steps is not None and action.ordination_steps != ordination_steps:
            continue
        if free_hire_target is not None and action.free_hire_target_building_id != free_hire_target:
            continue
        return index
    raise AssertionError(f"No matching Bank action found in {scenario_path}.")


def test_cli_legal_actions_show_bank_substitution_for_own_and_hired_sources(capsys) -> None:
    own_exit = main(["legal-actions", "scenarios/bank_active_ordination_substitution_001.json"])
    own_output = capsys.readouterr().out
    market_exit = main(["legal-actions", "scenarios/bank_hire_market_ordination_001.json"])
    market_output = capsys.readouterr().out

    assert own_exit == 0
    assert market_exit == 0
    assert "use building: bank to replace 1 wheat with 1 silver for this transaction" in own_output
    assert "use building: bank to replace 1 wheat with 1 silver for this transaction" in market_output
    assert "hire building: bank from market" in market_output


def test_cli_apply_market_hired_bank_shows_hire_bonus_and_delta_before_sowing(capsys) -> None:
    action_index = _bank_action_index(
        "scenarios/bank_hire_market_ordination_001.json",
        source="market",
        replaced_resource="wheat",
        silver_amount=1,
        resolution=TurnResolutionType.ORDINATION,
        ordination_steps=("ordain", "ordain"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/bank_hire_market_ordination_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Bank from market; paid silver 1 to bank" in output
    assert "BUILDING_BONUS: bank replaced 1 wheat with 1 silver for this transaction" in output
    assert "RESOURCE_DELTA: player_one silver -2; wheat -1" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Bank from market; paid silver 1 to bank"
    ) < output.index("BUILDING_BONUS: bank replaced 1 wheat with 1 silver for this transaction")
    assert output.index("BUILDING_BONUS: bank replaced 1 wheat with 1 silver for this transaction") < output.index(
        "SOWING:"
    )


def test_cli_apply_wagon_yard_free_hire_bank_has_no_paid_hire(capsys) -> None:
    action_index = _bank_action_index(
        "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json",
        source="own_active",
        replaced_resource="wheat",
        silver_amount=2,
        resolution=TurnResolutionType.ORDINATION,
        ordination_steps=("ordain", "ordain"),
        free_hire_target="bank",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Bank from market for free with Wagon Yard" in output
    assert "BUILDING_BONUS: bank replaced 2 wheat with 2 silver for this transaction" in output
    assert "paid silver 1 to bank" not in output
