from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _action_index(
    scenario_path: str,
    *,
    building_id: str,
    source: str,
    relocation_from: str,
    relocation_to: str,
    origin: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    board = scenario.config.board
    from_position = board.index_for_name(relocation_from)
    to_position = board.index_for_name(relocation_to)
    origin_position = board.index_for_name(origin)
    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.resolution is not resolution:
            continue
        if action.origin != origin_position:
            continue
        if action.start_turn_building_id != building_id:
            continue
        if action.start_turn_building_source != source:
            continue
        if action.start_turn_relocation_from != from_position:
            continue
        if action.start_turn_relocation_to != to_position:
            continue
        return index
    raise AssertionError(f"No matching start-turn action found in {scenario_path}.")


def test_cli_apply_own_active_dormitory_shows_bonus_then_relocation_then_sowing(capsys) -> None:
    action_index = _action_index(
        "scenarios/dormitory_active_return_duty_to_city_001.json",
        building_id="dormitory",
        source="own_active",
        relocation_from="east",
        relocation_to="city",
        origin="city",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/dormitory_active_return_duty_to_city_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "BUILDING_BONUS: dormitory returned 1 acolyte from east to city" in output
    assert (
        "START_TURN_RELOCATION: player_one moved 1 acolyte east -> city using Dormitory"
        in output
    )
    assert output.index("BUILDING_BONUS: dormitory returned 1 acolyte from east to city") < output.index(
        "START_TURN_RELOCATION: player_one moved 1 acolyte east -> city using Dormitory"
    )
    assert output.index(
        "START_TURN_RELOCATION: player_one moved 1 acolyte east -> city using Dormitory"
    ) < output.index("SOWING: picked up 2 from city; route city ->")


def test_cli_apply_market_hired_dormitory_shows_hire_bonus_relocation_order(capsys) -> None:
    action_index = _action_index(
        "scenarios/dormitory_hire_market_return_duty_to_city_001.json",
        building_id="dormitory",
        source="market",
        relocation_from="east",
        relocation_to="city",
        origin="city",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/dormitory_hire_market_return_duty_to_city_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Dormitory from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: dormitory returned 1 acolyte from east to city" in output
    assert (
        "START_TURN_RELOCATION: player_one moved 1 acolyte east -> city using Dormitory"
        in output
    )
    assert output.index(
        "BUILDING_HIRED: player_one hired Dormitory from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: dormitory returned 1 acolyte from east to city")
    assert output.index("BUILDING_BONUS: dormitory returned 1 acolyte from east to city") < output.index(
        "START_TURN_RELOCATION: player_one moved 1 acolyte east -> city using Dormitory"
    )


def test_cli_apply_market_hired_inquisition_shows_hire_bonus_relocation_order(capsys) -> None:
    action_index = _action_index(
        "scenarios/inquisition_hire_market_city_to_duty_001.json",
        building_id="inquisition",
        source="market",
        relocation_from="city",
        relocation_to="west",
        origin="city",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/inquisition_hire_market_city_to_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Inquisition from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: inquisition moved 1 acolyte from city to west" in output
    assert (
        "START_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Inquisition"
        in output
    )
    assert output.index(
        "BUILDING_HIRED: player_one hired Inquisition from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: inquisition moved 1 acolyte from city to west")
    assert output.index("BUILDING_BONUS: inquisition moved 1 acolyte from city to west") < output.index(
        "START_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Inquisition"
    )
