from pilgrim.cli import main


def test_cli_apply_build_roads_deferred_verbose_shows_scaffold_events(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/build_roads_deferred_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Selected action 1:" in output
    assert "action: build_roads_deferred" in output
    assert "DUTY_RESOLUTION: selected east (build_roads)" in output
    assert "DUTY_DEFERRED: build_roads requires spatial road/shrine system" in output
    assert "build road/bridge/ford/shrine, upgrade road/bridge, demolish road/bridge" in output
    assert "ACOLYTE_RECALL: recalled 1 from east to city" in output
    assert "Setup: not required" in output
    assert "Setup sow required: false" not in output
    assert "Setup sow complete: true" not in output
    assert "Completed by: none" not in output


def test_cli_apply_build_roads_road_engineer_verbose_shows_bonus(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/build_roads_road_engineer_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: build_roads_deferred" in output
    assert "effective duty value 3" in output
    assert "SPECIAL_ACTIVITY_BONUS: road_engineer added duty value +1 to build_roads_deferred" in output
    assert "DUTY_DEFERRED:" in output


def test_cli_apply_build_roads_minority_verbose_shows_silver_cost(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/build_roads_minority_cost_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: build_roads_deferred" in output
    assert "relation minority" in output
    assert "silver cost 1" in output
    assert "RESOURCE_DELTA: player_one silver -1" in output
    assert "DUTY_DEFERRED:" in output
