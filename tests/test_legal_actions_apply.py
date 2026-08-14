"""The engine's most basic contract: everything legal_actions offers, apply_action accepts.

A searchable branch has to appear in `legal_actions` and a replayable one has to be expressed in
`apply_action`, so an action the first produces and the second refuses is neither. A bot that picks
it crashes, and nothing shallower than picking it finds out.

Nothing checked this until now, and the cost of not checking it was 3,374 unappliable actions at
the round-eighteen fixture -- one move in five. They all came of the same thing: the cornucopia
lets the payer choose which resource a hire is paid in, a turn may hire several buildings, and an
action has ONE field to record that choice in. Each hire was enumerated as though it chose
independently. Where nothing wrote the choice down at all, applying looked the source up again,
found the wildcard and failed; where two hires wrote down different choices, applying spent one
resource on both and overdrew.

So this walks every committed position, applies every action offered there, and requires none to
raise. It is not a fast test. The round-eighteen fixture alone is thirty thousand actions and about
fourteen seconds of it; the other three hundred and seven positions are four thousand actions and
one second. The fixture is in nonetheless, because every one of those 3,374 was found there and
nowhere else -- it is the only committed position deep enough to have several buildings live at
once, which is what it takes to hire more than one in a turn.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction, action_id
from pilgrim.rules.merchant import CORNUCOPIA_COUNTER, current_merchant_resource
from pilgrim.rules.transition import apply_action, legal_actions

REPO = Path(__file__).resolve().parents[1]
DEEP_FIXTURE = "deep_round_eighteen_seed_seven_two_player_001"

# Three actions still refuse to apply, and they are a DIFFERENT bug from the one this file was
# written for: a Chapter House raises a Special Activity's capacity to two, and donating a building
# into an activity that is already full is offered anyway. They are pinned by count so that the
# guard below is a real guard rather than one exception away from being switched off, and so that
# this bug cannot quietly grow. Fixing it is its own job; nothing here should be read as saying it
# is acceptable.
KNOWN_UNAPPLIABLE = {
    "clerical_vestry_chapter_house_two_acolytes_001": 1,
    "give_alms_chapter_house_two_alms_house_001": 1,
    "produce_fields_chapter_house_two_acolytes_001": 1,
}


def scenario_paths():
    return sorted(REPO.joinpath("scenarios").glob("*.json"))


@pytest.fixture(scope="module")
def deep_actions():
    scenario = load_scenario(REPO / "scenarios" / f"{DEEP_FIXTURE}.json")
    return scenario, legal_actions(scenario.state, scenario.config)


def test_every_legal_action_applies() -> None:
    """The contract itself, over every committed position including the deep one."""
    unexpected: list[tuple[str, str, str]] = []
    counted: Counter[str] = Counter()
    total = 0

    for path in scenario_paths():
        scenario = load_scenario(path)
        actions = legal_actions(scenario.state, scenario.config)
        total += len(actions)
        for action in actions:
            try:
                apply_action(scenario.state, action, scenario.config)
            except Exception as exc:
                counted[path.stem] += 1
                if counted[path.stem] > KNOWN_UNAPPLIABLE.get(path.stem, 0):
                    unexpected.append((path.stem, action_id(action), str(exc)))

    assert total > 30_000, f"only {total} actions walked; the corpus has shrunk"
    assert not unexpected, "legal actions that apply_action refuses:\n" + "\n".join(
        f"  {name}: {reason}\n    {ident}" for name, ident, reason in unexpected[:20]
    )
    assert dict(counted) == KNOWN_UNAPPLIABLE, (
        f"the known-unappliable list is out of date: found {dict(counted)}"
    )


def test_the_deep_fixture_is_where_this_would_be_found(deep_actions) -> None:
    """Without this position the guard above would pass on a corpus that never hires twice."""
    scenario, actions = deep_actions
    assert current_merchant_resource(scenario.state, scenario.config) == CORNUCOPIA_COUNTER, (
        "this fixture is here because the Merchant offers the wildcard on it"
    )
    assert len(actions) > 25_000, f"the deep fixture now offers only {len(actions)} actions"

    multi_hire = sum(1 for action in actions if _hired_sources(action) > 1)
    assert multi_hire > 1_000, (
        f"only {multi_hire} actions hire more than once; the case that broke is not covered"
    )


def _hired_sources(action) -> int:
    """How many separately-hired buildings one action pays for."""
    if not isinstance(action, FullTurnAction):
        return 0
    labels = (
        action.hired_building_source,
        action.building_conversion_source,
        action.sow_route_building_source,
        action.sow_route_secondary_building_source,
        action.start_turn_building_source,
    )
    return sum(1 for label in labels if label is not None and label != "own_active")


def test_a_hire_on_the_wildcard_says_what_it_pays_with(deep_actions) -> None:
    """Enumeration settles the choice, so the action has to carry it.

    Looking the source up again during application finds the cornucopia, not the pick. An action
    that hires on the wildcard without recording a resource is therefore one that cannot be
    applied, whatever else is true of it.
    """
    _scenario, actions = deep_actions
    silent = [
        action
        for action in actions
        if _hired_sources(action) > 0 and action.hire_payment_resource is None
    ]
    assert not silent, (
        f"{len(silent)} actions hire on the wildcard without naming a resource, "
        f"e.g. {action_id(silent[0])}"
    )


def test_the_wildcard_is_a_choice_and_the_payer_can_afford_what_it_offers(deep_actions) -> None:
    """Both halves of the wildcard, which pull against each other and are easy to get wrong.

    It has to be a real choice, or generation has quietly collapsed it and the guard above would be
    passing on a wildcard nobody exercises. And every resource offered has to be one the payer can
    settle, which is what stops the choice from being three actions of which two fail.

    On this fixture the payer holds six stone, one silver and no wheat, so both halves are visible
    at once: a single hire may be paid in stone or in silver, never in wheat, and a turn hiring
    twice can only be paid in stone because one silver does not stretch to two hires. That is not a
    fact to hard-code -- it is read off the payer's stock, so it stays true if the fixture moves.
    """
    scenario, actions = deep_actions
    stock = scenario.state.player_state(scenario.state.active_player).resources
    affordable = {name for name in ("wheat", "stone", "silver") if getattr(stock, name) > 0}

    offered = Counter(
        action.hire_payment_resource
        for action in actions
        if _hired_sources(action) > 0 and action.hire_payment_resource is not None
    )
    assert set(offered) <= affordable, (
        f"offered a hire paid in something the payer has none of: {dict(offered)} against {stock}"
    )
    assert len(offered) > 1, (
        f"the wildcard offered only {set(offered)}; it is not being presented as a choice"
    )

    richest = max(affordable, key=lambda name: getattr(stock, name))
    multi = {action.hire_payment_resource for action in actions if _hired_sources(action) > 1}
    assert multi == {richest}, (
        f"turns hiring more than once were paid in {multi}, but only {richest} stretches that far"
    )
