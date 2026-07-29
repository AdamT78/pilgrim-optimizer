from __future__ import annotations

import pytest

from pilgrim.cli import main


def test_cli_solve_accepts_explicit_sandbox_objective(capsys) -> None:
    exit_code = main(
        [
            "solve",
            "scenarios/mancala_sandbox_search_smoke_001.json",
            "--depth",
            "1",
            "--objective",
            "sandbox",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Objective: maximize root player sandbox evaluation" in output
    assert "Best-line final evaluation:" in output


def test_cli_solve_accepts_implemented_official_score_objective(capsys) -> None:
    exit_code = main(
        [
            "solve",
            "scenarios/mancala_sandbox_search_smoke_001.json",
            "--depth",
            "1",
            "--objective",
            "implemented-official-score",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Objective: maximize root player implemented official score" in output
    assert "Best-line final implemented official score:" in output
    assert "Total implemented score:" in output
    assert "Total sandbox evaluation:" not in output


def test_cli_solve_invalid_objective_returns_clear_parser_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "solve",
                "scenarios/mancala_sandbox_search_smoke_001.json",
                "--depth",
                "1",
                "--objective",
                "nonsense",
            ]
        )
    captured = capsys.readouterr()

    assert exc_info.value.code == 2
    assert "invalid choice" in captured.err
    assert "nonsense" in captured.err
