"""The engine's most basic contract: everything legal_actions offers, apply_action accepts.

A searchable branch has to appear in `legal_actions` and a replayable one has to be expressed in
`apply_action`, so an action the first produces and the second refuses is neither. A bot that picks
it crashes, and nothing shallower than picking it finds out.

Nothing checked this until now, and the cost of not checking it was 3,374 unappliable actions at
the round-eighteen fixture -- one move in five. They all came of the same thing: the cornucopia
lets the payer choose which resource a hire is paid in, and a turn may hire several buildings. The
engine now records one payment per hired building so application can replay exactly what
enumeration chose.

So this walks every committed position, applies every action offered there, and requires none to
raise. It is not a fast test. The round-eighteen fixture alone is thirty thousand actions and about
fourteen seconds of it; the other three hundred and eight positions are four thousand actions and
one second. The fixture is in nonetheless, because every one of those 3,374 was found there and
nowhere else -- it is the only committed position deep enough to have several buildings live at
once, which is what it takes to hire more than one in a turn.
"""

from __future__ import annotations

from collections import Counter

from pilgrim.model.actions import FullTurnAction, action_id
from pilgrim.rules.merchant import CORNUCOPIA_COUNTER, current_merchant_resource
from pilgrim.rules.transition import apply_action

DEEP_FIXTURE = "deep_round_eighteen_seed_seven_two_player_001"


def test_every_legal_action_applies(deep_actions, corpus_actions) -> None:
    """The contract itself, over every committed position including the deep one."""
    deep_scenario, deep_legal_actions = deep_actions
    unexpected: list[tuple[str, str, str]] = []
    total = 0

    for path, loaded_scenario, loaded_actions in corpus_actions:
        if path.stem == DEEP_FIXTURE:
            scenario = deep_scenario
            actions = deep_legal_actions
        else:
            scenario = loaded_scenario
            actions = loaded_actions
        total += len(actions)
        for action in actions:
            try:
                apply_action(scenario.state, action, scenario.config)
            except Exception as exc:
                unexpected.append((path.stem, action_id(action), str(exc)))

    # Dormitory and Inquisition now commit separately, so their old action-prefix multiplication
    # deliberately leaves this full-turn population. Keep a floor so a later accidental collapse
    # still cannot make the corpus walk vacuous.
    assert total > 14_000, f"only {total} actions walked; the corpus has shrunk"
    assert not unexpected, "legal actions that apply_action refuses:\n" + "\n".join(
        f"  {name}: {reason}\n    {ident}" for name, ident, reason in unexpected[:20]
    )


def test_the_deep_fixture_is_where_this_would_be_found(deep_actions) -> None:
    """Without this position the guard above would pass on a corpus that never hires twice."""
    scenario, actions = deep_actions
    assert current_merchant_resource(scenario.state, scenario.config) == CORNUCOPIA_COUNTER, (
        "this fixture is here because the Merchant offers the wildcard on it"
    )
    # Committed start-turn relocation no longer multiplies complete-action variants here.
    assert len(actions) > 9_500, f"the deep fixture now offers only {len(actions)} actions"

    multi_hire = sum(1 for action in actions if _hired_sources(action) > 1)
    assert multi_hire > 1_000, (
        f"only {multi_hire} actions hire more than once; the case that broke is not covered"
    )


def _hired_sources(action) -> int:
    """How many separately-hired buildings one action pays for."""
    if not isinstance(action, FullTurnAction):
        return 0
    labels = (
        (action.hired_building_id, action.hired_building_source),
        (action.sow_route_building_id, action.sow_route_building_source),
        (action.sow_route_secondary_building_id, action.sow_route_secondary_building_source),
        (action.end_turn_building_id, action.end_turn_building_source),
        (action.effective_acolyte_building_id, action.effective_acolyte_building_source),
        (action.taxation_majority_building_id, action.taxation_majority_building_source),
        (action.workforce_move_building_id, action.workforce_move_building_source),
        (action.bank_payment_building_id, action.bank_payment_building_source),
    )
    return sum(
        1
        for building_id, source_label in labels
        if building_id is not None and source_label is not None and source_label != "own_active"
    )


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
        if _hired_sources(action) > 0 and len(action.hire_payments) != _hired_sources(action)
    ]
    assert not silent, (
        f"{len(silent)} actions hire without recording one payment per hired building, "
        f"e.g. {action_id(silent[0])}"
    )


def test_the_wildcard_is_a_choice_and_the_payer_can_afford_what_it_offers(deep_actions) -> None:
    """Both halves of the wildcard, which pull against each other and are easy to get wrong.

    It has to be a real choice, or generation has quietly collapsed it and the guard above would be
    passing on a wildcard nobody exercises. And every resource offered has to be one the payer can
    settle, which is what stops the choice from being three actions of which two fail.

    This fixture reaches hires after optional pre-sow effects that can change stock, so affordability
    is observed through "everything offered applies" above rather than by comparing only to opening
    resources.
    """
    _scenario, actions = deep_actions
    offered = Counter(
        resource
        for action in actions
        if _hired_sources(action) > 0
        for _building, resource in action.hire_payments
    )
    assert set(offered) <= {"wheat", "stone", "silver"}, (
        f"offered an unknown hire payment resource: {dict(offered)}"
    )
    assert len(offered) > 1, (
        f"the wildcard offered only {set(offered)}; it is not being presented as a choice"
    )

    mixed_multi = [
        action
        for action in actions
        if _hired_sources(action) > 1
        and len({resource for _building, resource in action.hire_payments}) > 1
    ]
    assert mixed_multi, (
        "turns hiring more than once never mix hire payment resources; "
        "per-hire payment choices are not being expressed"
    )
