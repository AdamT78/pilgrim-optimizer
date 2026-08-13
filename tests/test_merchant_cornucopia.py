"""What happens when the Merchant stands on the cornucopia tile.

WHY THIS FILE EXISTS AS ITS OWN THING

Hiring a building crashed on a cornucopia -- `_resource_amount` raises on it -- and the whole
suite passed over that crash. It passed because the fallback tithe counters that hand-written
scenarios inherit deal 2 wheat, 3 silver and 2 stone and NO cornucopia, so no scenario in the
repository can put the Merchant on one. The generator deals a cornucopia on every seed; the
fixtures cannot. That gap is not a tidiness problem, it is the reason a reachable crash was
invisible, and these tests exist to reach the state the fixtures cannot.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.buildings import building_ability_source
from pilgrim.rules.merchant import current_merchant_resource
from pilgrim.rules.transition import legal_actions

HIRE_SCENARIO = "scenarios/building_hire_opponent_owned_001.json"


def _with_cornucopia_under_the_merchant(scenario):
    """Put a cornucopia on the tile the Merchant occupies, leaving everything else alone."""
    position_name = scenario.config.board.positions[scenario.state.merchant_board_position]
    counters = scenario.config.tithe_counters
    moved = tuple(
        (name, "cornucopia" if name == position_name else resource)
        for name, resource in counters.counters_by_position
    )
    config = replace(scenario.config, tithe_counters=replace(counters, counters_by_position=moved))
    return scenario.state, config


def test_no_scenario_in_the_repository_can_put_the_merchant_on_a_cornucopia() -> None:
    """Pins the blind spot itself, so it fails if someone assumes fixtures cover this.

    If a fixture ever does deal a cornucopia the Merchant can reach, this test should be deleted
    and the coverage it stands in for taken from the fixture instead.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    assert "cornucopia" not in set(scenario.config.tithe_counters.mapping().values())


def test_a_merchant_on_the_cornucopia_offers_the_wildcard_rather_than_a_resource() -> None:
    scenario = load_scenario(HIRE_SCENARIO)
    state, config = _with_cornucopia_under_the_merchant(scenario)
    assert current_merchant_resource(state, config) == "cornucopia"


def test_hiring_on_a_cornucopia_is_refused_and_does_not_raise() -> None:
    """The crash this replaced: `_resource_amount` had no branch for the wildcard.

    Refusing is deliberately not the finished rule. The hiring player is meant to choose which of
    wheat, stone or silver to pay in, which needs one action variant per affordable resource. Until
    that exists, refusing spends nothing; guessing a resource would quietly spend the wrong stock.
    """
    scenario = load_scenario(HIRE_SCENARIO)
    state, config = _with_cornucopia_under_the_merchant(scenario)

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="well",
    )
    assert source.usable is False
    assert source.reason == "cornucopia_choice_not_implemented"


def test_legal_actions_still_answers_when_the_merchant_sits_on_the_cornucopia() -> None:
    """Whole-pipeline guard: the raise happened during enumeration, not only at the source."""
    scenario = load_scenario(HIRE_SCENARIO)
    state, config = _with_cornucopia_under_the_merchant(scenario)
    actions = legal_actions(state, config)
    assert actions
    assert all(action.hired_building_id is None for action in actions)


def test_a_generated_scenario_deals_a_cornucopia_the_merchant_will_reach() -> None:
    """The counterpart to the blind spot: real games do reach this, every seed.

    The Merchant laps all eight tiles, so a cornucopia dealt anywhere is a tile it stands on
    within eight rounds.
    """
    from pilgrim.setup.generator import generate_setup_scenario

    for seed in (1, 2, 3):
        generated = generate_setup_scenario(player_count=2, seed=seed)
        counters = generated["tithe_counters"]
        assert "cornucopia" in set(counters.values()), seed


@pytest.mark.parametrize("resource", ["wheat", "stone", "silver"])
def test_the_ordinary_counters_are_unaffected_by_the_wildcard_branch(resource: str) -> None:
    """The refusal must be about the wildcard alone and must not catch real resources."""
    scenario = load_scenario(HIRE_SCENARIO)
    position_name = scenario.config.board.positions[scenario.state.merchant_board_position]
    counters = scenario.config.tithe_counters
    moved = tuple(
        (name, resource if name == position_name else value)
        for name, value in counters.counters_by_position
    )
    config = replace(scenario.config, tithe_counters=replace(counters, counters_by_position=moved))
    assert current_merchant_resource(scenario.state, config) == resource
    source = building_ability_source(
        scenario.state,
        config,
        acting_player=scenario.state.active_player,
        building_key="well",
    )
    assert source.reason != "cornucopia_choice_not_implemented"
