from __future__ import annotations

from pilgrim.cli import main


def test_cli_round_end_verbose_shows_excess_then_merchant_then_start_player(capsys) -> None:
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
    assert "EXCESS_RESOURCE_CAP:" in output
    assert "EXCESS_RESOURCE_CAP: player_one stone 8 -> 6; wheat 7 -> 6" in output
    assert "EXCESS_RESOURCE_CAP: player_two wheat 10 -> 6" in output

    merchant_index = output.index("MERCHANT_ADVANCE:")
    start_player_index = output.index("CONFESSION_BOX_PHASE:")
    turn_advance_index = output.index("TURN_ADVANCE:")
    assert merchant_index < start_player_index < turn_advance_index
    assert "ALMS_SEASON_END:" not in output
    assert "ALMS_SEASON_REWARD:" not in output
    assert "ALMS_RESET:" not in output


def test_cli_round_end_verbose_shows_season_end_scoring_between_round_and_merchant(capsys) -> None:
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
    assert "ALMS_SEASON_REWARD:" in output
    assert "ALMS_RESET:" in output
    round_advance_index = output.index("ROUND_ADVANCE:")
    season_end_index = output.index("ALMS_SEASON_END:")
    season_reward_index = output.index("ALMS_SEASON_REWARD:")
    season_reset_index = output.index("ALMS_RESET:")
    merchant_index = output.index("MERCHANT_ADVANCE:")
    assert (
        round_advance_index
        < season_end_index
        < season_reward_index
        < season_reset_index
        < merchant_index
    )
