from __future__ import annotations

from pilgrim.cli import main


def test_cli_round_end_verbose_defers_the_pipeline_until_end_turn(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/round_end_excess_caps_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DUTY_RESOLUTION:" in output
    assert "EXCESS_RESOURCE_CAP:" not in output
    assert "MERCHANT_ADVANCE:" not in output
    assert "CONFESSION_BOX_PHASE:" not in output
    assert "TURN_ADVANCE:" not in output
    assert "ALMS_SEASON_END:" not in output
    assert "ALMS_SEASON_REWARD:" not in output
    assert "ALMS_RESET:" not in output


def test_cli_round_end_verbose_defers_season_end_scoring_until_end_turn(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/alms_season_end_unique_leader_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DUTY_RESOLUTION:" in output
    assert "ROUND_ADVANCE:" not in output
    assert "ALMS_SEASON_END:" not in output
    assert "ALMS_SEASON_REWARD:" not in output
    assert "ALMS_RESET:" not in output
    assert "MERCHANT_ADVANCE:" not in output
