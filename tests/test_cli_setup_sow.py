from pilgrim.cli import main


def test_cli_apply_setup_sow_verbose_shows_setup_events_and_state(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/setup_sow_2p_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Selected action 1:" in output
    assert "Setup sow: sow city ->" in output
    assert "SETUP_SOWING:" in output
    assert "SETUP_SOW_COMPLETE:" in output
    assert "SETUP_PLAYER_ADVANCE:" in output
    assert "SETUP_COMPLETE:" not in output
    assert "DUTY_RESOLUTION:" not in output
    assert "ACOLYTE_RECALL:" not in output
    assert "Setup:" in output
    assert "Setup sow required: true" in output
    assert "Setup sow complete: false" in output
    assert "Completed by: player_one" in output
    assert "Absolute turn: 0" in output
    assert "Round: 1" in output
    assert "Season: 1" in output
    assert "Turn in round: 0" in output


def test_cli_apply_final_setup_sow_verbose_shows_setup_complete(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/setup_sow_complete_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Selected action 1:" in output
    assert "Setup sow: sow city ->" in output
    assert "SETUP_SOW_COMPLETE:" in output
    assert "SETUP_COMPLETE:" in output
    assert "normal play begins with player_one" in output
    assert "Setup sow complete: true" in output
    assert "Completed by: player_one, player_two" in output
    assert "Absolute turn: 0" in output
    assert "Turn in round: 0" in output
