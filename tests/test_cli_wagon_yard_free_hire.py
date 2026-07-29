from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _wagon_action_index(
    scenario_path: str,
    *,
    target_building: str,
    target_source: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if not isinstance(action, FullTurnAction):
            continue
        if action.free_hire_enabler_building_id != "wagon_yard":
            continue
        if action.free_hire_target_building_id != target_building:
            continue
        if action.free_hire_target_building_source != target_source:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching Wagon Yard action found in {scenario_path}.")


def test_cli_legal_actions_show_wagon_yard_and_target_effect_for_market_and_opponent(capsys) -> None:
    market_exit = main(["legal-actions", "scenarios/wagon_yard_active_free_hire_market_brewery_001.json"])
    market_output = capsys.readouterr().out
    opponent_exit = main(
        ["legal-actions", "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json"]
    )
    opponent_output = capsys.readouterr().out

    assert market_exit == 0
    assert opponent_exit == 0
    assert "use building: wagon_yard to hire brewery from market for free" in market_output
    assert "use building: brewery to sell 1 wheat for 2 silver" in market_output
    assert "use building: wagon_yard to hire brewery from player_two for free" in opponent_output
    assert "use building: brewery to sell 1 wheat for 2 silver" in opponent_output


def test_cli_apply_market_free_hire_shows_free_event_and_order(capsys) -> None:
    action_index = _wagon_action_index(
        "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
        target_building="brewery",
        target_source="market",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/wagon_yard_active_free_hire_market_brewery_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Brewery from market for free with Wagon Yard" in output
    assert "BUILDING_BONUS: brewery sold 1 wheat for 2 silver" in output
    assert "RESOURCE_DELTA: player_one silver +2; wheat -1" in output
    assert "paid wheat 1 to bank" not in output
    assert output.index(
        "BUILDING_HIRED: player_one hired Brewery from market for free with Wagon Yard"
    ) < output.index("BUILDING_BONUS: brewery sold 1 wheat for 2 silver")
    assert output.index("BUILDING_BONUS: brewery sold 1 wheat for 2 silver") < output.index("SOWING:")


def test_cli_apply_opponent_free_hire_shows_no_owner_payment(capsys) -> None:
    action_index = _wagon_action_index(
        "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json",
        target_building="brewery",
        target_source="player_two",
        resolution=TurnResolutionType.TITHE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/wagon_yard_active_free_hire_opponent_brewery_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Brewery from player_two for free with Wagon Yard" in output
    assert "to player_two" not in output


def test_cli_wagon_yard_merchant_taxation_override_shows_legal_actions_and_apply(capsys) -> None:
    legal_exit = main(
        ["legal-actions", "scenarios/wagon_yard_active_free_hire_market_taxation_merchant_001.json"]
    )
    legal_output = capsys.readouterr().out
    action_index = _wagon_action_index(
        "scenarios/wagon_yard_active_free_hire_market_taxation_merchant_001.json",
        target_building="brewery",
        target_source="market",
        resolution=TurnResolutionType.TITHE,
    )
    apply_exit = main(
        [
            "apply",
            "scenarios/wagon_yard_active_free_hire_market_taxation_merchant_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    apply_output = capsys.readouterr().out

    assert legal_exit == 0
    assert apply_exit == 0
    assert "use building: wagon_yard to hire brewery from market for free" in legal_output
    assert "BUILDING_HIRED: player_one hired Brewery from market for free with Wagon Yard" in apply_output


def test_cli_blocked_wagon_sources_do_not_print_wagon_modifier_lines(capsys) -> None:
    blocked_paths = (
        "scenarios/wagon_yard_market_not_hireable_001.json",
        "scenarios/wagon_yard_opponent_not_hireable_001.json",
        "scenarios/wagon_yard_donated_no_modifier_001.json",
        "scenarios/wagon_yard_not_live_no_modifier_001.json",
        "scenarios/wagon_yard_no_live_target_no_modifier_001.json",
        "scenarios/wagon_yard_cannot_target_self_001.json",
    )
    for path in blocked_paths:
        exit_code = main(["legal-actions", path])
        output = capsys.readouterr().out

        assert exit_code == 0
        assert "use building: wagon_yard to hire" not in output
