from __future__ import annotations

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


def test_cli_apply_building_availability_shows_live_and_future_market(capsys) -> None:
    action_index = _action_index(
        "scenarios/building_availability_future_001.json",
        resolution=TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
        plan="road",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/building_availability_future_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Building availability:" in output
    assert "Live market: Well" in output
    assert "Future market: Chapel (round 4)" in output
    assert "Owned/live: none" in output


def test_cli_apply_building_availability_shows_owned_live_after_construct(capsys) -> None:
    action_index = _action_index(
        "scenarios/building_availability_round2_001.json",
        resolution=TurnResolutionType.CONSTRUCT_BUILDING,
        building_id="well",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/building_availability_round2_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Building availability:" in output
    assert "Live market: none" in output
    assert "Owned/live: Well (player_one)" in output


def test_cli_apply_building_availability_none_future_when_all_live(capsys) -> None:
    action_index = _action_index(
        "scenarios/construct_building_level1_001.json",
        resolution=TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
        plan="road",
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
    assert "Building availability:" in output
    assert "Future market: none" in output
