from __future__ import annotations

from pilgrim.cli import main


def test_cli_verbose_unique_leader_shows_season_end_reward_and_reset(capsys) -> None:
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
    assert "ALMS_SEASON_END:" in output
    assert "leader player_one by highest Alms position" in output
    assert "ALMS_SEASON_REWARD: player_one moved 1 acolyte abbey -> alms_table" in output
    assert "ALMS_RESET: all players reset to row 0" in output
    assert "MERCHANT_ADVANCE:" in output
    assert "START_PLAYER_MARKER:" in output


def test_cli_verbose_forfeit_case_is_clear(capsys) -> None:
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
    assert "ALMS_SEASON_END:" in output
    assert (
        "ALMS_SEASON_REWARD: player_one won Alms season end but had no Abbey acolyte; "
        "reward forfeited"
    ) in output
    assert "ALMS_RESET:" in output


def test_cli_verbose_fourth_season_game_end_skips_continuation_steps(capsys) -> None:
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
    assert "ALMS_SEASON_END:" in output
    assert "ALMS_SEASON_REWARD:" in output
    assert "ALMS_RESET:" in output
    assert "GAME_END: fourth season ended after pilgrimage site 4" in output
    assert "Season: 4" in output
    assert "Game over: true" in output
    assert "MERCHANT_ADVANCE:" not in output
    assert "START_PLAYER_MARKER:" not in output
    assert "TURN_ADVANCE:" not in output
