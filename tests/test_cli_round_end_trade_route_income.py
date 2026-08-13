from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _tithe_action_index(path: str) -> int:
    scenario = load_scenario(path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if not isinstance(action, FullTurnAction):
            continue
        if action.resolution is TurnResolutionType.TITHE:
            return index
    raise AssertionError(f"No tithe full-turn action found for scenario: {path}")


def test_cli_round_end_trade_route_income_basic_order_and_wording(capsys) -> None:
    action_index = _tithe_action_index("scenarios/round_end_trade_route_income_basic_001.json")
    exit_code = main(
        [
            "apply",
            "scenarios/round_end_trade_route_income_basic_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "MERCHANT_ADVANCE:" in output
    assert "TRADE_ROUTE_INCOME: player_one gained wheat +1 from 1 trade route" in output
    assert "START_PLAYER_SELECTION:" in output
    assert output.index("MERCHANT_ADVANCE:") < output.index("TRADE_ROUTE_INCOME:")
    assert output.index("TRADE_ROUTE_INCOME:") < output.index("START_PLAYER_SELECTION:")


def test_cli_round_end_trade_route_income_plural_wording(capsys) -> None:
    action_index = _tithe_action_index(
        "scenarios/round_end_trade_route_income_multiple_routes_001.json"
    )
    exit_code = main(
        [
            "apply",
            "scenarios/round_end_trade_route_income_multiple_routes_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "TRADE_ROUTE_INCOME: player_one gained wheat +3 from 3 trade routes" in output


def test_cli_round_end_trade_route_income_after_two_guild_moves_regression(capsys) -> None:
    action_index = _tithe_action_index(
        "scenarios/round_end_trade_route_income_after_two_guild_moves_001.json"
    )
    exit_code = main(
        [
            "apply",
            "scenarios/round_end_trade_route_income_after_two_guild_moves_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "MERCHANT_ADVANCE: clerical -> build_roads (east); current resource=stone" in output
    assert "TRADE_ROUTE_INCOME: player_one gained stone +2 from 2 trade routes" in output
    assert "TRADE_ROUTE_INCOME: player_two gained stone +1 from 1 trade route" in output
    assert output.index("MERCHANT_ADVANCE:") < output.index(
        "TRADE_ROUTE_INCOME: player_one gained stone +2 from 2 trade routes"
    )
    assert output.index(
        "TRADE_ROUTE_INCOME: player_two gained stone +1 from 1 trade route"
    ) < output.index("START_PLAYER_SELECTION:")
