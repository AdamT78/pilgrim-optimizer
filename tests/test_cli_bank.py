from __future__ import annotations

from pilgrim.cli import main


def test_cli_legal_actions_show_bank_substitution_only_for_own_source(capsys) -> None:
    own_exit = main(["legal-actions", "scenarios/bank_active_ordination_substitution_001.json"])
    own_output = capsys.readouterr().out
    market_exit = main(["legal-actions", "scenarios/bank_hire_market_ordination_001.json"])
    market_output = capsys.readouterr().out

    assert own_exit == 0
    assert market_exit == 0
    assert "use building: bank to replace 1 wheat with 1 silver for this transaction" in own_output
    assert "use building: bank to replace 1 wheat with 1 silver for this transaction" not in market_output
    assert "hire building: bank from market" not in market_output


def test_cli_legal_actions_do_not_fold_market_bank_hire_into_an_action(capsys) -> None:
    exit_code = main(["legal-actions", "scenarios/bank_hire_market_ordination_001.json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "use building: bank to replace" not in output
    assert "hire building: bank from market" not in output


def test_cli_legal_actions_do_not_fold_wagon_yard_free_bank_hire_into_an_action(capsys) -> None:
    exit_code = main(
        ["legal-actions", "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json"]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "use building: wagon_yard to hire bank from market for free" not in output
    assert "use building: bank to replace" not in output
