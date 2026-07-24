from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.transition import legal_actions


def _action_index_for_first_step(
    scenario_path: str,
    *,
    first_step: str,
    sow_route_building_source: str | None = None,
) -> int:
    scenario = load_scenario(scenario_path)
    board = scenario.config.board
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.origin != board.index_for_name("city") or not action.route:
            continue
        if board.positions[action.route[0]] != first_step:
            continue
        if sow_route_building_source is not None:
            if action.sow_route_building_source != sow_route_building_source:
                continue
        return index
    raise AssertionError(f"No city route action found for {scenario_path} -> {first_step}")


def test_cli_apply_own_active_kogge_route_shows_bonus_before_sowing(capsys) -> None:
    action_index = _action_index_for_first_step(
        "scenarios/kogge_active_city_to_east_001.json",
        first_step="east",
        sow_route_building_source="own_active",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/kogge_active_city_to_east_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: kogge enabled city -> east sow route" in output
    assert "SOWING: picked up 1 from city; route city -> east" in output
    assert output.index("BUILDING_BONUS: kogge enabled city -> east sow route") < output.index(
        "SOWING: picked up 1 from city; route city -> east"
    )


def test_cli_apply_market_hired_kogge_shows_hire_bonus_then_sowing(capsys) -> None:
    action_index = _action_index_for_first_step(
        "scenarios/kogge_hire_market_city_to_east_001.json",
        first_step="east",
        sow_route_building_source="market",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/kogge_hire_market_city_to_east_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Kogge from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: kogge enabled city -> east sow route" in output
    assert "SOWING: picked up 1 from city; route city -> east" in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Kogge from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: kogge enabled city -> east sow route")
    assert output.index("BUILDING_BONUS: kogge enabled city -> east sow route") < output.index(
        "SOWING: picked up 1 from city; route city -> east"
    )


def test_cli_apply_opponent_hired_kogge_pays_owner(capsys) -> None:
    action_index = _action_index_for_first_step(
        "scenarios/kogge_hire_opponent_city_to_west_001.json",
        first_step="west",
        sow_route_building_source="player_two",
    )
    exit_code = main(
        [
            "apply",
            "scenarios/kogge_hire_opponent_city_to_west_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "BUILDING_HIRED: player_one hired Kogge from player_two; paid wheat 1 to player_two"
        in output
    )
    assert "BUILDING_BONUS: kogge enabled city -> west sow route" in output
