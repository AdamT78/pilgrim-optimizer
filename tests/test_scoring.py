from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId, TurnResolutionType
from pilgrim.model.resources import Resources
from pilgrim.rules.scoring import (
    DEFERRED_SCORING_CATEGORIES,
    score_all_players,
    score_breakdown,
)
from pilgrim.rules.transition import apply_action, legal_actions


def test_acolytes_score_only_abbey_city_and_duty_tiles() -> None:
    scenario = load_scenario("scenarios/scoring_acolyte_locations_001.json")
    breakdown = score_breakdown(scenario.state, PlayerId.PLAYER_ONE, scenario.config)

    assert breakdown.acolytes_vp == 7
    assert breakdown.alms_vp == 11


def test_piety_score_uses_real_track_value_not_temporary_confession_bonus() -> None:
    scenario = load_scenario("scenarios/confession_box_owned_temp_piety_above_12_001.json")
    round_ending_tithe_actions = [
        action
        for action in legal_actions(scenario.state, scenario.config)
        if action.resolution is TurnResolutionType.TITHE
    ]
    confession_box_action = next(
        action
        for action in round_ending_tithe_actions
        if action.start_player_confession_box_uses
    )

    result = apply_action(scenario.state, confession_box_action, scenario.config)
    breakdown = score_breakdown(result.state, PlayerId.PLAYER_ONE, scenario.config)

    assert result.state.player_state(PlayerId.PLAYER_ONE).piety == 12
    assert breakdown.piety_vp == 9


@pytest.mark.parametrize(
    ("acolytes_on_table", "expected_vp"),
    [
        (0, 0),
        (1, 5),
        (2, 11),
        (3, 18),
        (4, 26),
    ],
)
def test_alms_table_scoring_bands(acolytes_on_table: int, expected_vp: int) -> None:
    scenario = load_scenario("scenarios/scoring_resources_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    committed = replace(player_one.workforce.committed, alms_table=acolytes_on_table)
    updated_player = replace(
        player_one,
        workforce=replace(player_one.workforce, committed=committed),
    )
    state = scenario.state.with_player_state(PlayerId.PLAYER_ONE, updated_player)

    breakdown = score_breakdown(state, PlayerId.PLAYER_ONE, scenario.config)
    assert breakdown.alms_vp == expected_vp


def test_donated_buildings_scoring_uses_donated_buildings_only() -> None:
    scenario = load_scenario("scenarios/scoring_donated_buildings_001.json")
    breakdown = score_breakdown(scenario.state, PlayerId.PLAYER_ONE, scenario.config)

    assert breakdown.donated_buildings_vp == 12


@pytest.mark.parametrize(
    ("resources", "expected_vp"),
    [
        (Resources(stone=0, silver=0, wheat=2), 0),
        (Resources(stone=1, silver=1, wheat=1), 1),
        (Resources(stone=2, silver=2, wheat=1), 1),
        (Resources(stone=1, silver=2, wheat=3), 2),
    ],
)
def test_resource_scoring_rounds_down(resources: Resources, expected_vp: int) -> None:
    scenario = load_scenario("scenarios/scoring_resources_001.json")
    player_one = scenario.state.player_state(PlayerId.PLAYER_ONE)
    state = scenario.state.with_player_state(
        PlayerId.PLAYER_ONE,
        replace(player_one, resources=resources),
    )

    breakdown = score_breakdown(state, PlayerId.PLAYER_ONE, scenario.config)
    assert breakdown.resources_vp == expected_vp


def test_mixed_score_breakdown_total_includes_implemented_categories_only() -> None:
    scenario = load_scenario("scenarios/scoring_basic_breakdown_001.json")
    breakdown = score_breakdown(scenario.state, PlayerId.PLAYER_ONE, scenario.config)

    assert breakdown.acolytes_vp == 5
    assert breakdown.piety_vp == 9
    assert breakdown.alms_vp == 11
    assert breakdown.donated_buildings_vp == 6
    assert breakdown.resources_vp == 2
    assert breakdown.implemented_total == 33
    assert breakdown.deferred_categories == DEFERRED_SCORING_CATEGORIES


def test_score_all_players_uses_real_player_count() -> None:
    scenario = load_scenario("scenarios/confession_box_multiple_players_player_order_001.json")
    all_scores = score_all_players(scenario.state, scenario.config)

    assert tuple(all_scores) == (
        PlayerId.PLAYER_ONE,
        PlayerId.PLAYER_TWO,
        PlayerId.PLAYER_THREE,
    )
