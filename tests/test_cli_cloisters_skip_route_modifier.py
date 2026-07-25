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


def test_cli_apply_market_hired_cloisters_shows_hire_bonus_then_sowing(capsys) -> None:
    action_index = _cloisters_action_index(
        "scenarios/cloisters_hire_market_skip_duty_tile_001.json",
        source="market",
        origin="north",
        omitted="north_east",
        selected_duty="east",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/cloisters_hire_market_skip_duty_tile_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Cloisters from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: cloisters skipped north_east during sow route" in output
    assert "SOWING: picked up 2 from north; route " in output
    assert "skipped north_east with Cloisters" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Cloisters from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: cloisters skipped north_east during sow route")
    assert output.index(
        "BUILDING_BONUS: cloisters skipped north_east during sow route"
    ) < output.index("SOWING: picked up 2 from north; route ")


def test_cli_apply_opponent_hired_cloisters_shows_owner_payment(capsys) -> None:
    action_index = _cloisters_action_index(
        "scenarios/cloisters_hire_opponent_skip_city_001.json",
        source="player_two",
        origin="east",
        omitted="city",
        selected_duty="north",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/cloisters_hire_opponent_skip_city_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Cloisters from player_two; paid wheat 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: cloisters skipped city during sow route" in output
    assert "skipped city with Cloisters" in output
