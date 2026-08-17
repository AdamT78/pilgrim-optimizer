"""Guards on how legal action generation de-duplicates.

Generation de-duped by scanning a list -- `if action not in actions` -- at seventeen sites. That
is O(n) a check and O(n^2) a position. Every committed scenario but one offers under two hundred
actions, where the cost is unmeasurable, so this survived a long time; the round-eighteen fixture
offers forty thousand and took a hundred and seventy seconds, which is what made it visible.

Three things need holding down, and only the first is about speed:

  - the substitution has to be sound, which means every action dataclass must hash consistently
    with its equality, or a lookup and a scan would answer differently
  - the cost has to stay linear, asserted by counting comparisons rather than by timing anything,
    because a stopwatch measures the machine as much as the code
  - the pattern must not come back, because a helper only helps if the eighteenth site uses it
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import (
    AllocationMove,
    FullTurnAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
)
from pilgrim.rules.transition import _ActionAccumulator, legal_actions

REPO = Path(__file__).resolve().parents[1]
TRANSITION = REPO / "pilgrim" / "rules" / "transition.py"
DEEP_FIXTURE = REPO / "scenarios" / "deep_round_eighteen_seed_seven_two_player_001.json"

# The accumulators de-dup is generated against. A membership test on either of these names is the
# quadratic pattern; a membership test on anything else is a legality check and is not.
ACCUMULATOR_NAMES = frozenset({"actions"})

# Membership tests in this module that are deliberately NOT in scope, named so the exclusion is a
# decision rather than an oversight. Each asks "is this submitted value one of the legal ones",
# against a small collection built for the question, inside apply_action rather than generation.
DELIBERATE_NON_ACCUMULATOR_MEMBERSHIP = {
    "legal_target_sources": "Wagon Yard free-hire target validation, already a set",
    "legal_step_2_choices": "Taxation step-two mix validation, a fixed handful of mixes",
    "legal_sources": "Wagon Yard free-hire source validation, already a set",
}

# Every dataclass that can be an action or sit inside one. A set index is only interchangeable
# with a linear scan if all of these hash consistently with how they compare.
ACTION_BEARING_DATACLASSES = (
    FullTurnAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    AllocationMove,
)


@pytest.fixture(scope="module")
def deep_position():
    """The one committed position deep enough for the quadratic term to be visible."""
    return load_scenario(DEEP_FIXTURE)


@pytest.fixture(scope="module")
def deep_generation(deep_position):
    """Generate the deep position once, counting comparisons while it happens.

    Generated once and shared because forty thousand actions is a few seconds even done properly,
    and counting while generating costs nothing measurable now that the count is small -- so there
    is no reason to pay for a second pass just to instrument it.
    """
    original_eq = FullTurnAction.__eq__
    calls = 0

    def counting_eq(self, other):
        nonlocal calls
        calls += 1
        return original_eq(self, other)

    FullTurnAction.__eq__ = counting_eq
    try:
        actions = legal_actions(deep_position.state, deep_position.config)
    finally:
        FullTurnAction.__eq__ = original_eq
    return actions, calls


@pytest.fixture(scope="module")
def deep_actions(deep_generation):
    """Just the actions, for the tests that do not care what generating them cost."""
    return deep_generation[0]


@pytest.mark.parametrize("dataclass_type", ACTION_BEARING_DATACLASSES, ids=lambda t: t.__name__)
def test_every_action_dataclass_hashes_the_way_it_compares(dataclass_type) -> None:
    """A set can only stand in for a scan where equal values hash equal."""
    params = dataclass_type.__dataclass_params__
    assert params.frozen, f"{dataclass_type.__name__} must be frozen to be hashable"
    assert params.eq, f"{dataclass_type.__name__} must generate __eq__"
    assert dataclass_type.__hash__ is not None, f"{dataclass_type.__name__} is unhashable"


@pytest.mark.slow
def test_the_deep_position_hashes_every_action_it_generates(deep_actions) -> None:
    """Hashability asserted on real actions, not on empty ones the fields never populate."""
    assert len(deep_actions) > 10_000, "this fixture is here to be big; something has shrunk it"
    by_hash: dict[int, list] = {}
    for action in deep_actions:
        by_hash.setdefault(hash(action), []).append(action)
    for colliding in by_hash.values():
        for other in colliding[1:]:
            if colliding[0] == other:
                raise AssertionError("equal actions must not both be emitted")


@pytest.mark.slow
def test_a_set_and_a_scan_agree_about_what_is_already_present(deep_actions) -> None:
    """The substitution's whole premise, checked against real actions rather than argued.

    Equality is what the old scan used and hashing is what the index uses. If they can disagree
    the de-dup would silently change, so this walks the real generated actions and checks that
    de-duping by hash keeps exactly the values de-duping by equality keeps.
    """
    sample = deep_actions[:2000]

    by_hash = []
    seen = set()
    for action in sample:
        if action not in seen:
            seen.add(action)
            by_hash.append(action)

    by_equality = []
    for action in sample:
        if action not in by_equality:
            by_equality.append(action)

    assert by_hash == by_equality


def test_the_accumulator_index_survives_a_rewrite_in_place() -> None:
    """Generation rewrites entries after adding them, which a plain set could not track.

    Route and conversion fields are folded into actions already in the list. A set index cannot
    tell whether the action written over was the last copy, so it would keep reporting a value the
    list no longer holds -- and then reject an action the old scan would have admitted.
    """
    first = SetupSowAction(origin=0, route=(1,))
    second = SetupSowAction(origin=0, route=(2,))
    rewritten = SetupSowAction(origin=0, route=(3,))

    # Written over when it was the only copy: the list no longer holds it, so a scan would admit
    # it again, and the index must agree.
    only_copy = _ActionAccumulator()
    only_copy.append(first)
    only_copy.append(second)
    only_copy[0] = rewritten
    only_copy.add_if_new(first)
    assert only_copy.as_tuple() == (rewritten, second, first), (
        "an action written over is no longer present and must be admissible again"
    )

    # Written over when a second copy remains. This is what separates counting occurrences from
    # remembering which values were seen: a set forgets `first` entirely on the rewrite, and would
    # then admit a duplicate of an action the list still holds.
    two_copies = _ActionAccumulator()
    two_copies.append(first)
    two_copies.append(first)
    two_copies[0] = rewritten
    two_copies.add_if_new(first)
    assert two_copies.as_tuple() == (rewritten, first), (
        "one copy was written over but another remains, so it must still be rejected"
    )


def test_a_site_that_never_de_duped_still_never_de_dups() -> None:
    """`append` is unconditional on purpose; making it de-dup would be a hidden rules change."""
    accumulator = _ActionAccumulator()
    action = SetupSowAction(origin=0, route=(1,))
    accumulator.append(action)
    accumulator.append(action)
    assert accumulator.as_tuple() == (action, action)


def _membership_tests_against_accumulators() -> list[tuple[int, str]]:
    """Every `x not in y` / `x in y` in transition.py whose container is an accumulator."""
    tree = ast.parse(TRANSITION.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            if not isinstance(operator, ast.In | ast.NotIn):
                continue
            if isinstance(comparator, ast.Name) and comparator.id in ACCUMULATOR_NAMES:
                found.append((node.lineno, comparator.id))
    return found


def test_no_list_backed_de_dup_returns() -> None:
    """The eighteenth site must use the helper, and this is what tells it so.

    Read as source rather than run, because the pattern's cost is not visible in any position a
    test can afford to generate -- the fixture that shows it takes a hundred and seventy seconds
    under the old code. A scan of the text catches it in the diff instead.
    """
    offenders = _membership_tests_against_accumulators()
    assert offenders == [], (
        "legal action generation must de-dup through _ActionAccumulator.add_if_new, not by "
        f"scanning the accumulator. Membership tests found at lines: {offenders}"
    )


def test_the_excluded_membership_tests_are_still_the_ones_we_excluded() -> None:
    """Pins the exclusions, so a new list-backed de-dup cannot hide behind a familiar name."""
    tree = ast.parse(TRANSITION.read_text(encoding="utf-8"))
    containers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            if not isinstance(operator, ast.In | ast.NotIn):
                continue
            if isinstance(comparator, ast.Name) and comparator.id.startswith("legal_"):
                containers.add(comparator.id)

    assert containers == set(DELIBERATE_NON_ACCUMULATOR_MEMBERSHIP), (
        "the membership tests deliberately left out of scope have changed; re-read them and "
        "decide, rather than updating this list"
    )


@pytest.mark.slow
def test_de_dup_stays_linear_in_the_number_of_actions(deep_generation) -> None:
    """The complexity assertion, counted rather than timed.

    A stopwatch here would measure the machine. Comparisons do not: the old scan made 1.44 billion
    of them at this position, roughly n^2/2 for forty thousand actions, where an indexed lookup
    makes a small constant number each. The bound is generous on purpose -- it is meant to catch a
    reintroduced linear scan, which overshoots it by four orders of magnitude, not to pin a number.
    """
    actions, calls = deep_generation
    generated = len(actions)
    assert calls <= 20 * generated, (
        f"{calls:,} equality comparisons for {generated:,} actions is {calls / generated:.0f} "
        "each, which is a linear scan rather than an indexed lookup"
    )


@pytest.mark.slow
def test_the_deep_fixture_is_the_position_it_says_it_is(deep_position, deep_actions) -> None:
    """Without this the fixture could drift shallow and every assertion above would still pass."""
    assert deep_position.state.round_number == 18
    assert deep_position.state.table_player_count == 2
    assert len(deep_actions) > 10_000
