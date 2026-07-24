from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _action_index(
    path: str,
    *,
    resolution: TurnResolutionType,
    building_id: str | None = None,
    plan: str | None = None,
) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.resolution is not resolution:
            continue
        if building_id is not None and action.construct_building_id != building_id:
            continue
        if plan is not None and action.construct_plan != plan:
            continue
        return index
    raise AssertionError(f"Action not found for {path}: {resolution.value}")


def test_cli_apply_construct_road_only_verbose_shows_scaffold_plan(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_deferred_building_001.json",
        resolution=TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
        plan="road",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/construct_deferred_building_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_road_deferred | plan: road" in output
    assert (
        "DUTY_DEFERRED: construct road part requires spatial road system; requested plan: road"
        in output
    )
    assert "BUILDING_CONSTRUCTED" not in output


def test_cli_apply_construct_building_verbose_shows_constructed_event(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_building_level1_001.json",
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/construct_building_level1_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_building | building: well" in output
    assert "RESOURCE_DELTA: player_one stone -1" in output
    assert "BUILDING_CONSTRUCTED: player_one constructed Well from market; level 1" in output
    assert "BUILDING_BONUS" not in output


def test_cli_apply_construct_building_and_road_verbose_shows_combined_plan(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_building_and_road_deferred_001.json",
        resolution=TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
        building_id="well",
        plan="road",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/construct_building_and_road_deferred_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "action: construct_building_and_road_deferred | building: well | deferred plan: road"
        in output
    )
    assert "BUILDING_CONSTRUCTED: player_one constructed Well from market; level 1" in output
    assert (
        "DUTY_DEFERRED: construct road part requires spatial road system; requested plan: road"
        in output
    )


def test_cli_apply_construct_road_engineer_building_plus_road_shows_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_building_road_engineer_extra_road_001.json",
        resolution=TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
        building_id="well",
        plan="road + road_engineer_extra_road",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/construct_building_road_engineer_extra_road_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "SPECIAL_ACTIVITY_BONUS: road_engineer allowed one additional road for construct "
        "because a road was included in the plan"
    ) in output
    assert "requested plan: road + road_engineer_extra_road" in output
    assert "effective duty value" not in output


def test_cli_apply_construct_building_minority_shows_stone_and_silver_costs(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_building_minority_cost_001.json",
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/construct_building_minority_cost_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "relation minority" in output
    assert "silver cost 1" in output
    assert "RESOURCE_DELTA: player_one stone -1; silver -1" in output
