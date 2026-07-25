from __future__ import annotations

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions


def _combined_action_index(
    scenario_path: str,
    *,
    primary_source: str,
    secondary_source: str,
    omitted: str,
    selected_duty: str,
    resolution: TurnResolutionType,
) -> int:
    scenario = load_scenario(scenario_path)
    board = scenario.config.board
    omitted_position = board.index_for_name(omitted)
    selected_duty_position = board.index_for_name(selected_duty)

    for index, action in enumerate(legal_actions(scenario.state, scenario.config), start=1):
        if action.sow_route_building_id != "kogge":
            continue
        if action.sow_route_building_source != primary_source:
            continue
        if action.sow_route_secondary_building_id != "cloisters":
            continue
        if action.sow_route_secondary_building_source != secondary_source:
            continue
        if action.sow_route_omitted_location != omitted_position:
            continue
        if action.selected_duty != selected_duty_position:
            continue
        if action.resolution is not resolution:
            continue
        return index
    raise AssertionError(f"No matching combined Kogge+Cloisters action found in {scenario_path}.")


def test_cli_apply_combined_summary_shows_both_modifiers_and_skip(capsys) -> None:
    action_index = _combined_action_index(
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
        primary_source="own_active",
        secondary_source="own_active",
        omitted="north_west",
        selected_duty="north",
        resolution=TurnResolutionType.PRODUCE_STONE,
    )
    exit_code = main(
        [
            "apply",
            "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
            "--action-index",
            str(action_index),
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert (
        "Turn: sow city -> west -> north | use building: kogge | use building: cloisters "
        "to skip north_west | selected duty: north (produce) | action: produce_stone"
    ) in output
    assert "SOWING: picked up 2 from city; route city -> west -> north; skipped north_west with Cloisters" in output
