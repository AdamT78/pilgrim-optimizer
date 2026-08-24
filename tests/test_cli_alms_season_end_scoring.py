from __future__ import annotations

from pilgrim.cli import main


def test_cli_verbose_unique_leader_stops_at_end_turn_before_season_scoring(capsys) -> None:
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
    assert "Round: 9" in output
    assert "Season: 1" in output
    for deferred in (
        "ALMS_SEASON_END:",
        "ALMS_SEASON_REWARD:",
        "ALMS_RESET:",
        "MERCHANT_ADVANCE:",
        "CONFESSION_BOX_PHASE:",
        "TURN_ADVANCE:",
    ):
        assert deferred not in output


def test_cli_verbose_forfeit_case_waits_for_end_turn_before_scoring(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/alms_season_end_no_abbey_forfeit_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DUTY_RESOLUTION:" in output
    assert "ALMS_SEASON_END:" not in output
    assert "ALMS_SEASON_REWARD:" not in output
    assert "ALMS_RESET:" not in output


def test_cli_verbose_fourth_season_game_end_waits_for_end_turn(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/alms_season_end_fourth_season_game_end_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "DUTY_RESOLUTION:" in output
    for deferred in (
        "ALMS_SEASON_END:",
        "ALMS_SEASON_REWARD:",
        "ALMS_RESET:",
        "GAME_END:",
        "MERCHANT_ADVANCE:",
        "START_PLAYER_MARKER:",
        "TURN_ADVANCE:",
    ):
        assert deferred not in output
    assert "Round: 22" in output
    assert "Season: 3" in output
    assert "Game over: false" in output
