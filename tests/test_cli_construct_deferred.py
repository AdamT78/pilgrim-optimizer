from pilgrim.cli import main


def test_cli_apply_construct_building_verbose_shows_scaffold_plan(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/construct_deferred_building_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_deferred | plan: building" in output
    assert "DUTY_RESOLUTION: selected south_east (construct);" in output
    assert "DUTY_DEFERRED: construct requires building/spatial road system; requested plan: building" in output


def test_cli_apply_construct_building_and_road_verbose_shows_combined_plan(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/construct_deferred_building_and_road_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_deferred | plan: building + road" in output
    assert (
        "DUTY_DEFERRED: construct requires building/spatial road system; "
        "requested plan: building + road"
    ) in output


def test_cli_apply_construct_road_engineer_plan_shows_bonus_message(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/construct_road_engineer_extra_road_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_deferred | plan: road + road_engineer_extra_road" in output
    assert (
        "SPECIAL_ACTIVITY_BONUS: road_engineer allowed one additional road for construct "
        "because a road was included in the plan"
    ) in output
    assert "effective duty value" not in output


def test_cli_apply_construct_minority_plan_shows_silver_cost(capsys) -> None:
    exit_code = main(
        [
            "apply",
            "scenarios/construct_minority_cost_001.json",
            "--action-index",
            "1",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_deferred | plan: building" in output
    assert "relation minority" in output
    assert "silver cost 1" in output
    assert "RESOURCE_DELTA: player_one silver -1" in output
