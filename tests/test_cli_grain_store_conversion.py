from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _grain_store_action_index(
    scenario_path: str,
    *,
    source: str,
    direction: str,
    amount: int,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.building_conversion_id != "grain_store":
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
    raise AssertionError(f"No matching Grain Store action found in {scenario_path}.")


def test_cli_apply_own_active_grain_store_sell_shows_bonus_and_delta_before_sowing(capsys) -> None:
    action_index = _grain_store_action_index(
        "scenarios/grain_store_active_sell_wheat_001.json",
        source="own_active",
        direction="sell_wheat",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/grain_store_active_sell_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: grain_store sold 2 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -2" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: grain_store sold 2 wheat for 2 silver") < output.index(
        "RESOURCE_DELTA: player_one silver +2; wheat -2"
    )
    assert output.index("RESOURCE_DELTA: player_one silver +2; wheat -2") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_market_hired_grain_store_buy_shows_hire_then_bonus_then_delta(capsys) -> None:
    action_index = _grain_store_action_index(
        "scenarios/grain_store_hire_market_buy_wheat_001.json",
        source="market",
        direction="buy_wheat",
        amount=1,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/grain_store_hire_market_buy_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Grain Store from market; paid silver 1 to bank"
        in output
    )
    assert "BUILDING_BONUS: grain_store bought 1 wheat for 1 silver" in output
    assert "RESOURCE_DELTA: player_one silver -1; wheat +1" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Grain Store from market; paid silver 1 to bank"
    ) < output.index("BUILDING_BONUS: grain_store bought 1 wheat for 1 silver")
    assert output.index("BUILDING_BONUS: grain_store bought 1 wheat for 1 silver") < output.index(
        "RESOURCE_DELTA: player_one silver -1; wheat +1"
    )
    assert output.index("RESOURCE_DELTA: player_one silver -1; wheat +1") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_opponent_hired_grain_store_buy_shows_owner_payment(capsys) -> None:
    action_index = _grain_store_action_index(
        "scenarios/grain_store_hire_opponent_buy_wheat_001.json",
        source="player_two",
        direction="buy_wheat",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/grain_store_hire_opponent_buy_wheat_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Grain Store from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: grain_store bought 2 wheat for 2 silver" in output


def test_cli_apply_grain_store_buy_then_ordination_shows_ordination_wheat_delta(capsys) -> None:
    action_index = _grain_store_action_index(
        "scenarios/grain_store_buy_then_ordination_001.json",
        source="own_active",
        direction="buy_wheat",
        amount=1,
        resolution=TurnResolutionType.ORDINATION,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/grain_store_buy_then_ordination_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_BONUS: grain_store bought 1 wheat for 1 silver" in output
    assert "RESOURCE_DELTA: player_one silver -1; wheat +1" in output
    assert "ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1" in output
    assert "RESOURCE_DELTA: player_one wheat -1" in output
    assert output.index("RESOURCE_DELTA: player_one silver -1; wheat +1") < output.index(
        "SOWING: picked up 1 from south; route south -> south_west"
    )
    assert output.index(
        "ORDINATION: player_one ordained 1 serf village -> abbey; paid wheat=1"
    ) < output.index("RESOURCE_DELTA: player_one wheat -1")
