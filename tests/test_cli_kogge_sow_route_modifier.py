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


def test_cli_does_not_offer_an_uncommitted_market_kogge_hire(capsys) -> None:
    scenario_path = "scenarios/kogge_hire_market_city_to_east_001.json"
    scenario = load_scenario(scenario_path)
    exit_code = main(["legal-actions", scenario_path])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "hire building: kogge from market" not in output
    assert not [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "kogge"
    ]


def test_cli_does_not_offer_an_uncommitted_opponent_kogge_hire(capsys) -> None:
    scenario_path = "scenarios/kogge_hire_opponent_city_to_west_001.json"
    scenario = load_scenario(scenario_path)
    exit_code = main(["legal-actions", scenario_path])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "hire building: kogge from player_two" not in output
    assert not [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.sow_route_building_id == "kogge"
    ]
