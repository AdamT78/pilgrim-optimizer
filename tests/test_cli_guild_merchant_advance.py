from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _guild_action_index(
    scenario_path: str,
    *,
    source: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.merchant_advance_building_id != "guild":
            continue
        if action.merchant_advance_building_source != source:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching Guild action found in {scenario_path}.")


def test_cli_apply_own_active_guild_shows_bonus_then_merchant_advance_before_sowing(capsys) -> None:
    action_index = _guild_action_index(
        "scenarios/guild_active_move_merchant_001.json",
        source="own_active",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/guild_active_move_merchant_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: guild moved Merchant clockwise +1" in output
    assert "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver; cause=guild" in output
    assert "SOWING: picked up 1 from north; route north -> north_east" in output
    assert output.index("BUILDING_BONUS: guild moved Merchant clockwise +1") < output.index(
        "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver; cause=guild"
    )
    assert output.index(
        "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver; cause=guild"
    ) < output.index("SOWING: picked up 1 from north; route north -> north_east")


def test_cli_apply_market_hired_guild_shows_hire_then_bonus_then_merchant_advance(capsys) -> None:
    action_index = _guild_action_index(
        "scenarios/guild_hire_market_move_merchant_001.json",
        source="market",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/guild_hire_market_move_merchant_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Guild from market; paid wheat 1 to bank"
        in output
    )
    assert "BUILDING_BONUS: guild moved Merchant clockwise +1" in output
    assert "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver; cause=guild" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Guild from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: guild moved Merchant clockwise +1")
    assert output.index("BUILDING_BONUS: guild moved Merchant clockwise +1") < output.index(
        "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver; cause=guild"
    )


def test_cli_apply_opponent_hired_guild_shows_owner_payment(capsys) -> None:
    action_index = _guild_action_index(
        "scenarios/guild_hire_opponent_move_merchant_001.json",
        source="player_two",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/guild_hire_opponent_move_merchant_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Guild from player_two; paid silver 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: guild moved Merchant clockwise +1" in output
    # "alms" was a name in the retired path, not a duty category. The tile clockwise of clerical
    # is build_roads, and the resource is the tithe counter standing on it rather than a property
    # of the duty, so the line now names the position a player would look at.
    assert (
        "MERCHANT_ADVANCE: clerical -> build_roads (east); current resource=stone; cause=guild"
        in output
    )


def test_cli_apply_round_ending_guild_turn_shows_two_merchant_advances(capsys) -> None:
    action_index = _guild_action_index(
        "scenarios/guild_round_end_moves_merchant_twice_001.json",
        source="own_active",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/guild_round_end_moves_merchant_twice_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.count("MERCHANT_ADVANCE:") == 2
    assert "MERCHANT_ADVANCE: taxation -> produce (north); current resource=wheat; cause=guild" in output
    assert "MERCHANT_ADVANCE: produce -> clerical (north_east); current resource=silver" in output
