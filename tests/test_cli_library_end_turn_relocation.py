from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _action_index(
    scenario_path: str,
    *,
    source: str,
    to_target: str,
    origin: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    board = scenario.config.board
    city_position = board.index_for_name("city")
    target = to_target if to_target == "abbey" else board.index_for_name(to_target)
    origin_position = board.index_for_name(origin)

    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.end_turn_building_id != "library":
            continue
        if action.end_turn_building_source != source:
            continue
        if action.end_turn_relocation_from != city_position:
            continue
        if action.end_turn_relocation_to != target:
            continue
        if action.origin != origin_position:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching Library end-turn action found in {scenario_path}.")


def test_cli_apply_own_active_library_shows_recall_bonus_relocation_before_turn_advance(capsys) -> None:
    action_index = _action_index(
        "scenarios/library_active_city_to_duty_001.json",
        source="own_active",
        to_target="west",
        origin="city",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/library_active_city_to_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED" not in output
    assert "ACOLYTE_RECALL: recalled 1 from north to city" in output
    assert "BUILDING_BONUS: library moved 1 acolyte from city to west" in output
    assert "END_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Library" in output
    assert output.index("ACOLYTE_RECALL: recalled 1 from north to city") < output.index(
        "BUILDING_BONUS: library moved 1 acolyte from city to west"
    )
    assert output.index(
        "BUILDING_BONUS: library moved 1 acolyte from city to west"
    ) < output.index(
        "END_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Library"
    )


def test_cli_apply_market_hired_library_city_to_abbey_shows_hire_bonus_and_relocation(capsys) -> None:
    action_index = _action_index(
        "scenarios/library_hire_market_city_to_abbey_001.json",
        source="market",
        to_target="abbey",
        origin="city",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/library_hire_market_city_to_abbey_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "ACOLYTE_RECALL: recalled 1 from north to city" in output
    assert "BUILDING_HIRED: player_one hired Library from market; paid wheat 1 to bank" in output
    assert "BUILDING_BONUS: library moved 1 acolyte from city to abbey" in output
    assert "END_TURN_RELOCATION: player_one moved 1 acolyte city -> abbey using Library" in output
    assert output.index("ACOLYTE_RECALL: recalled 1 from north to city") < output.index(
        "BUILDING_HIRED: player_one hired Library from market; paid wheat 1 to bank"
    )
    assert output.index(
        "BUILDING_HIRED: player_one hired Library from market; paid wheat 1 to bank"
    ) < output.index("BUILDING_BONUS: library moved 1 acolyte from city to abbey")
    assert output.index(
        "BUILDING_BONUS: library moved 1 acolyte from city to abbey"
    ) < output.index("END_TURN_RELOCATION: player_one moved 1 acolyte city -> abbey using Library")


def test_cli_apply_opponent_hired_library_shows_owner_payment(capsys) -> None:
    action_index = _action_index(
        "scenarios/library_hire_opponent_city_to_duty_001.json",
        source="player_two",
        to_target="west",
        origin="city",
        resolution=TurnResolutionType.PRODUCE_WHEAT,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/library_hire_opponent_city_to_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "BUILDING_HIRED: player_one hired Library from player_two; paid wheat 1 to player_two" in output
    assert "BUILDING_BONUS: library moved 1 acolyte from city to west" in output
    assert "END_TURN_RELOCATION: player_one moved 1 acolyte city -> west using Library" in output
