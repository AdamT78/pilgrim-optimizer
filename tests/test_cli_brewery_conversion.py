from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _brewery_action_index(
    scenario_path: str,
    *,
    source: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.building_conversion_id != "brewery":
            continue
        if action.building_conversion_source != source:
            continue
        if action.building_conversion_direction != "sell_wheat_for_silver":
            continue
        if action.building_conversion_amount != 1:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching Brewery action found in {scenario_path}.")


def test_cli_apply_own_active_brewery_sell_shows_bonus_and_delta_before_sowing(capsys) -> None:
    action_index = _brewery_action_index(
        "scenarios/brewery_active_sell_wheat_001.json",
        source="own_active",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/brewery_active_sell_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: brewery sold 1 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -1" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: brewery sold 1 wheat for 2 silver") < output.index(
        "RESOURCE_DELTA: player_one silver +2; wheat -1"
    )
    assert output.index("RESOURCE_DELTA: player_one silver +2; wheat -1") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_market_hired_brewery_sell_shows_hire_then_bonus_then_delta(capsys) -> None:
    action_index = _brewery_action_index(
        "scenarios/brewery_hire_market_sell_wheat_001.json",
        source="market",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/brewery_hire_market_sell_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Brewery from market; paid wheat 1 to bank"
        in output
    )
    assert "BUILDING_BONUS: brewery sold 1 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -1" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Brewery from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: brewery sold 1 wheat for 2 silver")
    assert output.index("BUILDING_BONUS: brewery sold 1 wheat for 2 silver") < output.index(
        "RESOURCE_DELTA: player_one silver +2; wheat -1"
    )
    assert output.index("RESOURCE_DELTA: player_one silver +2; wheat -1") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_opponent_hired_brewery_sell_shows_owner_payment(capsys) -> None:
    action_index = _brewery_action_index(
        "scenarios/brewery_hire_opponent_sell_wheat_001.json",
        source="player_two",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/brewery_hire_opponent_sell_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Brewery from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: brewery sold 1 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -1" in output
