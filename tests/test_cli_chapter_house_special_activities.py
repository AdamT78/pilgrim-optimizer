from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _action_index(
    path: str,
    *,
    resolution: TurnResolutionType,
    first_move: tuple[str, str] | None = None,
    plan: str | None = None,
    alms_house_bonus: int | None = None,
) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.resolution is not resolution:
            continue
        if first_move is not None:
            if not action.allocation_moves:
                continue
            move = action.allocation_moves[0]
            if (move.source, move.destination) != first_move:
                continue
        if plan is not None and action.construct_plan != plan:
            continue
        if alms_house_bonus is not None:
            if action.alms_house_extra_silver + action.alms_house_extra_wheat != alms_house_bonus:
                continue
        return index
    raise AssertionError(f"Action not found for {path}: {resolution.value}")


def test_cli_apply_allocation_chapter_house_shows_capacity_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/allocation_chapter_house_second_acolyte_001.json",
        resolution=TurnResolutionType.ALLOCATION,
        first_move=("abbey", "vestry"),
    )
    exit_code = main(
        [
            "apply",
            "scenarios/allocation_chapter_house_second_acolyte_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: allocation | moves: abbey -> vestry" in output
    assert (
        "BUILDING_BONUS: chapter_house allowed second acolyte on vestry (capacity 2)"
        in output
    )
    assert "Special Activities: vestry x2" in output


def test_cli_apply_produce_fields_two_acolytes_shows_plus_two_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/produce_fields_chapter_house_two_acolytes_001.json",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/produce_fields_chapter_house_two_acolytes_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SPECIAL_ACTIVITY_BONUS: fields added wheat +2 to produce_wheat" in output
    assert "RESOURCE_DELTA: player_one wheat +4" in output
    assert "effective duty value 4" not in output


def test_cli_apply_clerical_vestry_two_acolytes_shows_plus_two_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/clerical_vestry_chapter_house_two_acolytes_001.json",
        resolution=TurnResolutionType.CLERICAL_DEVOTION,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/clerical_vestry_chapter_house_two_acolytes_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "SPECIAL_ACTIVITY_BONUS: vestry added piety +2 to clerical_devotion" in output
    assert "PIETY_DELTA: player_one piety 0 -> 4" in output
    assert "effective duty value 4" not in output


def test_cli_apply_build_roads_two_road_engineers_shows_effective_plus_two(capsys) -> None:
    action_index = _action_index(
        "scenarios/build_roads_chapter_house_two_road_engineers_001.json",
        resolution=TurnResolutionType.BUILD_ROADS_DEFERRED,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/build_roads_chapter_house_two_road_engineers_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "effective duty value 4" in output
    assert "SPECIAL_ACTIVITY_BONUS: road_engineer added duty value +2 to build_roads_deferred" in output


def test_cli_apply_give_alms_two_alms_house_shows_plus_two_bonus(capsys) -> None:
    action_index = _action_index(
        "scenarios/give_alms_chapter_house_two_alms_house_001.json",
        resolution=TurnResolutionType.GIVE_ALMS_PAID,
        alms_house_bonus=2,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/give_alms_chapter_house_two_alms_house_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "effective duty value 4" in output
    assert "SPECIAL_ACTIVITY_BONUS: alms_house applied to give_alms_paid; duty value +2" in output


def test_cli_apply_construct_two_road_engineers_shows_double_extra_plan(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_chapter_house_two_road_engineers_001.json",
        resolution=TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
        plan="road + road_engineer_extra_road + road_engineer_extra_road",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/construct_chapter_house_two_road_engineers_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "action: construct_road_deferred | plan: road + road_engineer_extra_road + road_engineer_extra_road" in output
    assert (
        "SPECIAL_ACTIVITY_BONUS: road_engineer allowed 2 additional roads for construct "
        "because a road was included in the plan"
    ) in output
