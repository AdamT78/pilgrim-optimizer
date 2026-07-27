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
    start_player_index = output.index("START_PLAYER_SELECTION:")
    turn_advance_index = output.index("TURN_ADVANCE:")
    assert merchant_index < start_player_index < turn_advance_index
    assert "ALMS_SEASON_REWARD:" not in output
    assert "ALMS_RESET:" not in output


def test_cli_round_end_verbose_shows_season_end_deferred_between_round_and_merchant(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/round_end_pilgrimage_deferred_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "SEASON_END_DEFERRED: round 10 reached pilgrimage site; "
        "Alms leader assessment deferred"
    ) in output
    round_advance_index = output.index("ROUND_ADVANCE:")
    season_deferred_index = output.index("SEASON_END_DEFERRED:")
    merchant_index = output.index("MERCHANT_ADVANCE:")
    assert round_advance_index < season_deferred_index < merchant_index
