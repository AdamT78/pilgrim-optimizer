from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _indulgences_action_index(
    scenario_path: str,
    *,
    source: str,
    direction: str,
    amount: int,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.building_conversion_id != "indulgences":
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
    raise AssertionError(f"No matching Indulgences action found in {scenario_path}.")


def test_cli_apply_own_active_indulgences_sell_shows_bonus_and_delta_before_sowing(capsys) -> None:
    action_index = _indulgences_action_index(
        "scenarios/indulgences_active_sell_piety_001.json",
        source="own_active",
        direction="sell_piety",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/indulgences_active_sell_piety_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: indulgences sold 2 piety for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; piety -2" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: indulgences sold 2 piety for 2 silver") < output.index(
        "RESOURCE_DELTA: player_one silver +2; piety -2"
    )
    assert output.index("RESOURCE_DELTA: player_one silver +2; piety -2") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_market_hired_indulgences_buy_shows_hire_then_bonus_then_delta(capsys) -> None:
    action_index = _indulgences_action_index(
        "scenarios/indulgences_hire_market_buy_piety_001.json",
        source="market",
        direction="buy_piety",
        amount=1,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/indulgences_hire_market_buy_piety_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Indulgences from market; paid silver 1 to bank"
        in output
    )
    assert "BUILDING_BONUS: indulgences bought 1 piety for 1 silver" in output
    assert "RESOURCE_DELTA: player_one silver -1; piety +1" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Indulgences from market; paid silver 1 to bank"
    ) < output.index("BUILDING_BONUS: indulgences bought 1 piety for 1 silver")
    assert output.index("BUILDING_BONUS: indulgences bought 1 piety for 1 silver") < output.index(
        "RESOURCE_DELTA: player_one silver -1; piety +1"
    )
    assert output.index("RESOURCE_DELTA: player_one silver -1; piety +1") < output.index(
        "SOWING: picked up 1 from north; route north -> north_east"
    )


def test_cli_apply_opponent_hired_indulgences_buy_shows_owner_payment(capsys) -> None:
    action_index = _indulgences_action_index(
        "scenarios/indulgences_hire_opponent_buy_piety_001.json",
        source="player_two",
        direction="buy_piety",
        amount=2,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/indulgences_hire_opponent_buy_piety_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Indulgences from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: indulgences bought 2 piety for 2 silver" in output


def test_cli_apply_indulgences_buy_then_round_end_shows_start_player_selection(capsys) -> None:
    action_index = _indulgences_action_index(
        "scenarios/indulgences_buy_then_round_end_start_player_001.json",
        source="own_active",
        direction="buy_piety",
        amount=1,
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/indulgences_buy_then_round_end_start_player_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_BONUS: indulgences bought 1 piety for 1 silver" in output
    assert "RESOURCE_DELTA: player_two silver -1; piety +1" in output
    assert "START_PLAYER_SELECTION: player_two selected player_two as next start player" in output
