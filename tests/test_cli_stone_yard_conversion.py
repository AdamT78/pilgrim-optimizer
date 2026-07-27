from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _stone_yard_action_index(
    scenario_path: str,
    *,
    source: str,
    direction: str,
    amount: int,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.building_conversion_id != "stone_yard":
            continue
        if action.building_conversion_source != source:
            continue
        if action.building_conversion_direction != direction:
            continue
        if action.building_conversion_amount != amount:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching Stone Yard action found in {scenario_path}.")


def test_cli_apply_own_active_stone_yard_sell_shows_bonus_and_delta_before_sowing(capsys) -> None:
    action_index = _stone_yard_action_index(
        "scenarios/stone_yard_active_sell_stone_001.json",
        source="own_active",
        direction="sell_stone",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/stone_yard_active_sell_stone_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: stone_yard sold 2 stone for 2 silver" in output
    assert "RESOURCE_DELTA: player_one stone -2; silver +2" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: stone_yard sold 2 stone for 2 silver") < output.index(
        "RESOURCE_DELTA: player_one stone -2; silver +2"
    )
    assert output.index("RESOURCE_DELTA: player_one stone -2; silver +2") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_market_hired_stone_yard_buy_shows_hire_then_bonus_then_delta(capsys) -> None:
    action_index = _stone_yard_action_index(
        "scenarios/stone_yard_hire_market_buy_stone_001.json",
        source="market",
        direction="buy_stone",
        amount=1,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/stone_yard_hire_market_buy_stone_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Stone Yard from market; paid silver 1 to bank"
        in output
    )
    assert "BUILDING_BONUS: stone_yard bought 1 stone for 1 silver" in output
    assert "RESOURCE_DELTA: player_one stone +1; silver -1" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Stone Yard from market; paid silver 1 to bank"
    ) < output.index("BUILDING_BONUS: stone_yard bought 1 stone for 1 silver")
    assert output.index("BUILDING_BONUS: stone_yard bought 1 stone for 1 silver") < output.index(
        "RESOURCE_DELTA: player_one stone +1; silver -1"
    )
    assert output.index("RESOURCE_DELTA: player_one stone +1; silver -1") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_opponent_hired_stone_yard_buy_shows_owner_payment(capsys) -> None:
    action_index = _stone_yard_action_index(
        "scenarios/stone_yard_hire_opponent_buy_stone_001.json",
        source="player_two",
        direction="buy_stone",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/stone_yard_hire_opponent_buy_stone_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Stone Yard from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: stone_yard bought 2 stone for 2 silver" in output


def test_cli_apply_stone_yard_buy_above_six_round_end_cap_shows_cap_event(capsys) -> None:
    action_index = _stone_yard_action_index(
        "scenarios/stone_yard_buy_above_six_then_round_end_cap_001.json",
        source="own_active",
        direction="buy_stone",
        amount=1,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/stone_yard_buy_above_six_then_round_end_cap_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_BONUS: stone_yard bought 1 stone for 1 silver" in output
    assert "RESOURCE_DELTA: player_two stone +1; silver -1" in output
    assert "EXCESS_RESOURCE_CAP: player_two stone 7 -> 6" in output
