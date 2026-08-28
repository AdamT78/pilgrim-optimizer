from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _cloisters_action_index(
    scenario_path: str,
    *,
    source: str,
    origin: str,
    omitted: str,
    selected_duty: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    board = scenario.config.board
    origin_position = board.index_for_name(origin)
    omitted_position = board.index_for_name(omitted)
    selected_duty_position = board.index_for_name(selected_duty)

    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.sow_route_building_id != "cloisters":
            continue
        if action.sow_route_building_source != source:
            continue
        if action.origin != origin_position:
            continue
        if action.sow_route_omitted_location != omitted_position:
            continue
        if action.selected_duty != selected_duty_position:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching Cloisters action found in {scenario_path}.")


def test_cli_apply_own_active_cloisters_shows_bonus_before_sowing(capsys) -> None:
    action_index = _cloisters_action_index(
        "scenarios/cloisters_active_skip_duty_tile_001.json",
        source="own_active",
        origin="north",
        omitted="north_east",
        selected_duty="east",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/cloisters_active_skip_duty_tile_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: cloisters skipped north_east during sow route" in output
    assert "SOWING: picked up 2 from north; route " in output
    assert "skipped north_east with Cloisters" in output
    assert output.index("BUILDING_BONUS: cloisters skipped north_east during sow route") < output.index(
        "SOWING: picked up 2 from north; route "
    )


def test_cli_offers_market_cloisters_hires_only_on_routes_that_skip(capsys) -> None:
    scenario_path = "scenarios/cloisters_hire_market_skip_duty_tile_001.json"
    scenario = load_scenario(scenario_path)
    exit_code = main(["legal-actions", scenario_path])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "hire building: cloisters from market" in output
    assert [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "cloisters"
        and action.sow_route_building_source == "market"
    ]


def test_cli_offers_opponent_cloisters_hires_only_on_routes_that_skip(capsys) -> None:
    scenario_path = "scenarios/cloisters_hire_opponent_skip_city_001.json"
    scenario = load_scenario(scenario_path)
    exit_code = main(["legal-actions", scenario_path])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "hire building: cloisters from player_two" in output
    assert [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "cloisters"
        and action.sow_route_building_source == "player_two"
    ]
