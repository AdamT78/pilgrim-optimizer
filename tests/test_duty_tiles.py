from __future__ import annotations

import pytest

from pilgrim.cli import main
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary
from pilgrim.model.duties import default_duty_tiles, validate_duty_tiles
from pilgrim.model.enums import EventType, PlayerId, TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.search.exact import solve_exact


def test_validate_duty_tiles_accepts_complete_valid_layout() -> None:
    validate_duty_tiles(default_duty_tiles())


def test_validate_duty_tiles_rejects_missing_position() -> None:
    invalid = default_duty_tiles()
    invalid.pop("north")
    with pytest.raises(ValueError):
        validate_duty_tiles(invalid)


def test_validate_duty_tiles_rejects_city_key() -> None:
    invalid = default_duty_tiles()
    invalid.pop("north_west")
    invalid["city"] = "taxation"
    with pytest.raises(ValueError):
        validate_duty_tiles(invalid)


def test_validate_duty_tiles_rejects_unknown_position() -> None:
    invalid = default_duty_tiles()
    invalid.pop("north_west")
    invalid["foo"] = "taxation"
    with pytest.raises(ValueError):
        validate_duty_tiles(invalid)


def test_validate_duty_tiles_rejects_duplicate_category() -> None:
    invalid = default_duty_tiles()
    invalid["north_west"] = "produce"
    with pytest.raises(ValueError):
        validate_duty_tiles(invalid)


def test_validate_duty_tiles_rejects_unknown_category() -> None:
    invalid = default_duty_tiles()
    invalid["north_west"] = "unknown_duty"
    with pytest.raises(ValueError):
        validate_duty_tiles(invalid)


def test_validate_duty_tiles_rejects_missing_category() -> None:
    invalid = default_duty_tiles()
    invalid["north_west"] = "produce"
    with pytest.raises(ValueError):
        validate_duty_tiles(invalid)


def test_scenario_without_duty_tiles_uses_deterministic_fallback() -> None:
    scenario = load_scenario("scenarios/duty_tiles_default_001.json")
    assert scenario.config.duty_tiles_mapping() == default_duty_tiles()
    assert len(set(scenario.config.duty_tiles_mapping().values())) == 8


def test_custom_layout_allows_give_alms_on_north_and_allocation_on_south() -> None:
    scenario = load_scenario("scenarios/duty_tiles_custom_give_alms_north_001.json")
    north = scenario.config.board.index_for_name("north")
    south = scenario.config.board.index_for_name("south")
    actions = legal_actions(scenario.state, scenario.config)

    assert any(
        action.selected_duty == north and action.resolution is TurnResolutionType.GIVE_ALMS
        for action in actions
    )
    assert any(
        action.selected_duty == south and action.resolution is TurnResolutionType.ALLOCATION
        for action in actions
    )
    assert not any(
        action.selected_duty == south and action.resolution is TurnResolutionType.GIVE_ALMS
        for action in actions
    )

    give_alms_action = next(
        action
        for action in actions
        if action.selected_duty == north and action.resolution is TurnResolutionType.GIVE_ALMS
    )
    summary = action_summary(give_alms_action, scenario.config)
    assert "selected duty: north (give_alms)" in summary


def test_apply_custom_give_alms_north_reports_category_in_event() -> None:
    scenario = load_scenario("scenarios/duty_tiles_custom_give_alms_north_001.json")
    first_action = legal_actions(scenario.state, scenario.config)[0]
    result = apply_action(scenario.state, first_action, scenario.config)
    duty_event = next(
        event for event in result.events if event.event_type is EventType.DUTY_RESOLUTION
    )
    duty_details = dict(duty_event.details)

    assert duty_details["duty_category"] == "give_alms"
    assert duty_details["duty_position"] == scenario.config.board.index_for_name("north")


def test_custom_south_allocation_applies_without_position_hardcoding() -> None:
    scenario = load_scenario("scenarios/duty_tiles_custom_allocation_south_001.json")
    first_action = legal_actions(scenario.state, scenario.config)[0]
    before = scenario.state.player_state(PlayerId.PLAYER_ONE)
    result = apply_action(scenario.state, first_action, scenario.config)
    after = result.state.player_state(PlayerId.PLAYER_ONE)

    assert first_action.resolution is TurnResolutionType.ALLOCATION
    assert first_action.selected_duty == scenario.config.board.index_for_name("south")
    assert after.workforce.abbey == before.workforce.abbey - 1
    assert after.workforce.mancala[0] == before.workforce.mancala[0] + 2


def test_default_layout_still_offers_implemented_categories() -> None:
    scenario = load_scenario("scenarios/duty_tiles_default_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    resolutions = {action.resolution for action in actions}
    assert TurnResolutionType.PRODUCE in resolutions
    assert TurnResolutionType.CLERICAL_DEVOTION in resolutions
    assert TurnResolutionType.CLERICAL_SILVERSMITH in resolutions
    assert TurnResolutionType.GIVE_ALMS in resolutions
    assert TurnResolutionType.ALLOCATION in resolutions


def test_deferred_categories_validate_and_do_not_emit_non_tithe_actions() -> None:
    scenario = load_scenario("scenarios/duty_tiles_deferred_categories_001.json")
    actions = legal_actions(scenario.state, scenario.config)
    deferred_categories = {"build_roads", "construct", "ordination", "taxation"}
    for action in actions:
        category = scenario.config.duty_category_for_position(action.selected_duty)
        if category in deferred_categories:
            assert action.resolution is TurnResolutionType.TITHE


def test_deferred_categories_do_not_crash_search() -> None:
    scenario = load_scenario("scenarios/duty_tiles_deferred_categories_001.json")
    result = solve_exact(scenario.state, scenario.config, depth=2)
    assert isinstance(result.best_score, int)


def test_cli_verbose_output_includes_duty_tile_layout_and_category_labels(capsys) -> None:
    exit_code = main(
        [
            "solve",
            "scenarios/duty_tiles_default_001.json",
            "--depth",
            "2",
            "--verbose",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Duty tiles:" in output
    assert "north: produce" in output
    assert "north_east: clerical" in output
    assert "DUTY_RESOLUTION: selected" in output
    assert "(produce)" in output or "(clerical)" in output
