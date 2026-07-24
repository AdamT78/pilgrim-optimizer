from pathlib import Path
import json

from pilgrim.cli import main


def test_cli_generate_setup_writes_file_and_prints_summary(capsys, tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "setup_2p_seed_123.json"
    exit_code = main(
        [
            "generate-setup",
            "--players",
            "2",
            "--seed",
            "123",
            "--output",
            str(output_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output_path.exists()
    assert f"Generated setup scenario: {output_path.as_posix()}" in output
    assert "Players: 2" in output
    assert "Seed: 123" in output
    assert "Taxation tile:" in output
    assert "Building availability: 12 entries" in output
    assert "Setup sow required: true" in output
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    assert generated["root_player_id"] == "player_one"
    assert generated["setup_metadata"]["setup_sow_implemented"] is True
    assert generated["initial_state"]["setup"] == {
        "setup_sow_required": True,
        "setup_sow_complete": False,
        "setup_sow_completed_by": [],
    }

    validate_exit = main(["validate", str(output_path)])
    validate_output = capsys.readouterr().out
    assert validate_exit == 0
    assert "is valid." in validate_output


def test_cli_generate_setup_supports_name_override(capsys, tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "named_setup.json"
    exit_code = main(
        [
            "generate-setup",
            "--players",
            "2",
            "--seed",
            "321",
            "--output",
            str(output_path),
            "--name",
            "my_seeded_setup",
        ]
    )
    assert exit_code == 0
    scenario_output = capsys.readouterr().out
    assert "Generated setup scenario:" in scenario_output

    validate_exit = main(["validate", str(output_path)])
    assert validate_exit == 0
    _ = capsys.readouterr()


def test_cli_generate_setup_works_for_2p_3p_4p(capsys, tmp_path: Path) -> None:
    for player_count in (2, 3, 4):
        output_path = tmp_path / "generated" / f"setup_{player_count}p_seed_123.json"
        exit_code = main(
            [
                "generate-setup",
                "--players",
                str(player_count),
                "--seed",
                "123",
                "--output",
                str(output_path),
            ]
        )
        assert exit_code == 0
        _ = capsys.readouterr()

        validate_exit = main(["validate", str(output_path)])
        assert validate_exit == 0
        _ = capsys.readouterr()


def test_cli_generate_setup_generated_2p_scenario_can_solve_depth_one(
    capsys,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "generated" / "setup_2p_seed_123.json"
    generate_exit = main(
        [
            "generate-setup",
            "--players",
            "2",
            "--seed",
            "123",
            "--output",
            str(output_path),
        ]
    )
    assert generate_exit == 0
    _ = capsys.readouterr()

    solve_exit = main(["solve", str(output_path), "--depth", "1", "--verbose"])
    solve_output = capsys.readouterr().out
    assert solve_exit == 0
    assert "Solve result for scenario" in solve_output
    assert "Root player: player_one" in solve_output
    assert "Setup sow: sow city ->" in solve_output


def test_cli_generate_setup_rejects_invalid_player_count(capsys, tmp_path: Path) -> None:
    output_path = tmp_path / "generated" / "invalid_players.json"
    exit_code = main(
        [
            "generate-setup",
            "--players",
            "5",
            "--seed",
            "123",
            "--output",
            str(output_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Generated scenario failed validation:" in captured.err
    assert "Unsupported player count" in captured.err
    assert not output_path.exists()
