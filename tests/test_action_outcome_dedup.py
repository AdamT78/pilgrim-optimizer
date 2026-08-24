"""Guards on generating one move per outcome rather than one per spelling.

Ordination steps and allocation moves are ordered sequences, and generation used to emit every
legal ORDER of them. Order gates legality -- you cannot mission out of an empty Abbey, or move an
acolyte out of a slot nothing stands in -- but it never gates the result, so most of what was
emitted was a second way of writing a move already on offer. At the round-eighteen fixture that was
twenty-four thousand of forty thousand moves.

Generation now keeps one sequence per outcome. That is a deduplication on a PROJECTION of the
action, and the risk that comes with it is specific: if the projection leaves out something the
rules read, two genuinely different moves collapse into one and a reachable position quietly stops
being reachable. No amount of thinking about it settles that -- the projection has to be checked
against what the engine actually does with the actions.

So the expensive check lives here rather than at runtime. These tests reconstruct generation as it
was, exhaustively, and then:

  - apply every pair of spellings that share an outcome and require the resulting GameState to be
    equal IN FULL, not in some chosen handful of fields
  - count the distinct positions reachable per decision before and after, and require them equal

The second is the one that catches a projection that is too coarse in the other direction, where
the merge loses a move rather than a synonym.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

import pilgrim.rules.transition as transition
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import EndTurnAction, FullTurnAction
from pilgrim.rules.ordination import (
    apply_ordination_step,
    legal_ordination_steps,
    ordination_outcome,
)
from pilgrim.rules.special_activities import (
    allocation_outcome,
    apply_allocation_move_with_capacity,
    legal_allocation_moves,
)
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.search.exact import solve_exact

REPO = Path(__file__).resolve().parents[1]

DEEP_FIXTURE = "deep_round_eighteen_seed_seven_two_player_001"

# The corpus is every committed position that offers one of these sequences, found rather than
# listed so that a scenario added later is covered without anyone remembering to add it here. The
# round-eighteen fixture is left out only of the exhaustive tests: reconstructing it spelling by
# spelling means applying thirty-six thousand actions. It is covered instead by the generator-level
# completeness test below, which asks the narrower question and can afford to ask it of everything.
EXCLUDED_FROM_EXHAUSTIVE = frozenset({DEEP_FIXTURE})


def every_allocation_spelling(
    player_state,
    *,
    max_moves: int,
    special_activity_capacity: int,
    min_moves: int = 1,
):
    """Allocation generation as it was: every legal spelling, longest first.

    Kept here rather than in the engine because it is the thing being compared against. The old
    caller filtered by length after the fact; passing `min_moves` through does the same job, so
    this reproduces what generation used to hand back.

    The Chapter House now also limits one allocation to at most one second-acolyte placement.
    Exhaustive generation here mirrors that legality too, so these tests still compare two legal
    generators rather than one legal and one intentionally over-permissive.
    """
    if max_moves <= 0:
        return ()
    found: list[tuple] = []

    def walk(state, path, used_second_placements):
        if len(path) >= max_moves:
            return
        for move in legal_allocation_moves(state, capacity=special_activity_capacity):
            next_second_placements = used_second_placements + int(
                move.destination != "abbey" and state.special_activities.count_for(move.destination) == 1
            )
            if next_second_placements > 1:
                continue
            try:
                next_state = apply_allocation_move_with_capacity(
                    state, move, capacity=special_activity_capacity
                )
            except ValueError:
                continue
            found.append((*path, move))
            walk(next_state, (*path, move), next_second_placements)

    walk(player_state, (), 0)
    keep = [sequence for sequence in found if len(sequence) >= min_moves]
    return tuple(sorted(keep, key=len, reverse=True))


def every_ordination_spelling(player_state, *, max_steps: int):
    """Ordination generation as it was: every legal spelling, longest first."""
    if max_steps <= 0:
        return ()
    found: list[tuple] = []

    def walk(state, path):
        if len(path) >= max_steps:
            return
        for step in legal_ordination_steps(state):
            try:
                next_state = apply_ordination_step(state, step)
            except ValueError:
                continue
            found.append((*path, step))
            walk(next_state, (*path, step))

    walk(player_state, ())
    return tuple(sorted(found, key=len, reverse=True))


def outcome_of(action) -> tuple:
    """The projection generation deduplicates on, for whichever field this action carries."""
    if action.allocation_moves:
        return ("allocation", allocation_outcome(action.allocation_moves))
    return ("ordination", ordination_outcome(action.ordination_steps))


def sequenced(action) -> bool:
    return isinstance(action, FullTurnAction) and bool(
        action.allocation_moves or action.ordination_steps
    )


def skeleton(action) -> FullTurnAction:
    """The decision an action belongs to: everything about it except how the sequence is spelled."""
    return replace(action, allocation_moves=(), ordination_steps=())


def landing(state, action, config):
    """Where a completed turn leaves the game, or the refusal it earns.

    Full turns now pause at the deterministic End Turn window. This audit compares action outcomes,
    not the action-id-bearing event trail held inside that temporary window, so it passes the only
    legal EndTurnAction before comparing final states.
    """
    try:
        landed = apply_action(state, action, config).state
        if landed.turn_progress.resolution_committed:
            landed = apply_action(landed, EndTurnAction(), config).state
        return ("state", landed)
    except Exception as exc:  # a refusal is a result too, and must match for equivalent spellings
        return ("refused", type(exc).__name__, str(exc))


@pytest.fixture(scope="module")
def generations(corpus_actions):
    """Every corpus position generated twice: exhaustively, and as the engine now does it."""
    monkeypatch = pytest.MonkeyPatch()
    built = []
    for path, scenario, after in corpus_actions:
        if path.stem in EXCLUDED_FROM_EXHAUSTIVE:
            continue
        if not any(sequenced(action) for action in after):
            continue
        with monkeypatch.context() as patched:
            patched.setattr(transition, "_allocation_move_sequences", every_allocation_spelling)
            patched.setattr(
                transition, "legal_ordination_step_sequences", every_ordination_spelling
            )
            before = legal_actions(scenario.state, scenario.config)
        built.append((path.stem, scenario, before, after))
    return built


def test_the_corpus_actually_exercises_what_it_claims_to(generations) -> None:
    """A corpus that stopped producing sequences would make every test below vacuous."""
    allocation = ordination = collapsed = 0
    for _name, _scenario, before, after in generations:
        allocation += sum(1 for a in before if sequenced(a) and a.allocation_moves)
        ordination += sum(1 for a in before if sequenced(a) and a.ordination_steps)
        collapsed += sum(1 for a in before if sequenced(a)) - sum(1 for a in after if sequenced(a))
    assert allocation > 200, "corpus no longer exercises allocation"
    assert ordination > 10, "corpus no longer exercises ordination"
    assert collapsed > 100, "nothing is being deduplicated; these tests would prove nothing"


def test_equal_outcome_means_an_equal_game_state_in_full(generations) -> None:
    """The projection's whole premise, checked by applying rather than by reasoning.

    Every pair of spellings sharing a decision and an outcome is applied, and the two resulting
    GameState objects must be equal -- the whole object, so a difference in a field nobody thought
    to look at still fails. GameState is a frozen dataclass of scalars, enums and tuples, so its
    generated equality already compares everything and nothing needed substituting for it.
    """
    pairs = 0
    for _name, scenario, before, _after in generations:
        groups = defaultdict(list)
        for action in before:
            if sequenced(action):
                groups[(skeleton(action), outcome_of(action))].append(action)

        for spellings in groups.values():
            if len(spellings) < 2:
                continue
            first = landing(scenario.state, spellings[0], scenario.config)
            for other in spellings[1:]:
                pairs += 1
                assert landing(scenario.state, other, scenario.config) == first, (
                    "two spellings of one outcome left the game in different places"
                )
    assert pairs > 400, f"only {pairs} pairs compared; this is meant to be the expensive check"


def test_no_position_stops_being_reachable(generations) -> None:
    """The other direction: a projection can also be too coarse and swallow a real move.

    Counting distinct landings per decision is what catches that. If deduplicating removed only
    synonyms the counts are identical; if it removed a move, the count drops, and it drops here
    whether or not the projection looked reasonable.
    """
    for name, scenario, before, after in generations:
        reachable_before = defaultdict(set)
        reachable_after = defaultdict(set)
        for action in before:
            if sequenced(action):
                reachable_before[skeleton(action)].add(
                    landing(scenario.state, action, scenario.config)
                )
        for action in after:
            if sequenced(action):
                reachable_after[skeleton(action)].add(
                    landing(scenario.state, action, scenario.config)
                )

        assert set(reachable_after) == set(reachable_before), f"{name}: a decision disappeared"
        for decision, landings in reachable_before.items():
            assert reachable_after[decision] == landings, (
                f"{name}: a decision no longer reaches every position it used to"
            )


def test_nothing_survives_twice(generations) -> None:
    """The deduplication has to be complete as well as sound: no two survivors may agree."""
    for name, _scenario, _before, after in generations:
        groups = defaultdict(list)
        for action in after:
            if sequenced(action):
                groups[(skeleton(action), outcome_of(action))].append(action)
        for key, spellings in groups.items():
            assert len(spellings) == 1, f"{name}: {len(spellings)} spellings survived for {key[1]}"


def test_the_surviving_spelling_is_the_shortest_one(generations) -> None:
    """Shortest is the point: a detour reaches the same place while reading as extra work done."""
    for name, _scenario, before, after in generations:
        shortest: dict[tuple, int] = {}
        for action in before:
            if not sequenced(action):
                continue
            key = (skeleton(action), outcome_of(action))
            length = len(action.allocation_moves or action.ordination_steps)
            shortest[key] = min(shortest.get(key, length), length)

        for action in after:
            if not sequenced(action):
                continue
            key = (skeleton(action), outcome_of(action))
            length = len(action.allocation_moves or action.ordination_steps)
            assert length == shortest[key], (
                f"{name}: kept a {length}-step spelling where {shortest[key]} was available"
            )


def test_a_kept_spelling_is_one_the_walk_found_and_not_one_we_wrote(generations) -> None:
    """Nothing is constructed: every emitted sequence is one the exhaustive walk also produced.

    A shorter route between two slots can look obviously legal and not be, so the enumerator gets
    to decide what exists. This checks we only ever selected from what it offered.
    """
    for name, _scenario, before, after in generations:
        walked = {
            (skeleton(a), a.allocation_moves, a.ordination_steps) for a in before if sequenced(a)
        }
        for action in after:
            if not sequenced(action):
                continue
            key = (skeleton(action), action.allocation_moves, action.ordination_steps)
            assert key in walked, f"{name}: emitted a sequence the walk never found legal"


def test_the_shortest_spelling_also_gives_the_shortest_log(generations) -> None:
    """What a player reads afterwards, which is decided by which spelling survives.

    Each move in a sequence writes its own line, so a detour is not merely redundant in the state
    it reaches -- it narrates work that undoes itself. Keeping the shortest spelling therefore also
    keeps the plainest account of the move, rather than that being a happy accident.
    """
    checked = 0
    for _name, scenario, before, after in generations:
        kept = {(skeleton(a), outcome_of(a)): a for a in after if sequenced(a)}
        groups = defaultdict(list)
        for action in before:
            if sequenced(action):
                groups[(skeleton(action), outcome_of(action))].append(action)

        for key, spellings in groups.items():
            if len(spellings) < 2 or key not in kept:
                continue
            survivor = kept[key]
            try:
                survivor_events = len(
                    apply_action(scenario.state, survivor, scenario.config).events
                )
            except Exception:
                continue
            for other in spellings:
                try:
                    other_events = len(apply_action(scenario.state, other, scenario.config).events)
                except Exception:
                    continue
                checked += 1
                assert survivor_events <= other_events, (
                    "a dropped spelling would have written a shorter log than the kept one"
                )
    assert checked > 100, f"only {checked} logs compared"


@pytest.mark.slow
@pytest.mark.parametrize(
    "scenario_name",
    [
        "allocation_all_special_occupied_001",
        "allocation_multi_move_001",
        "allocation_hire_infirmary_market_001",
        "allocation_chapter_house_second_acolyte_001",
        "kogge_cloisters_hire_both_market_001",
        "ordination_hire_mill_market_three_steps_001",
        DEEP_FIXTURE,
    ],
)
def test_the_walk_reaches_every_outcome_the_exhaustive_walk_reaches(scenario_name) -> None:
    """Completeness at the generator, where it can be asked of the big fixture too.

    The tests above reconstruct whole positions, which the round-eighteen fixture is too large for.
    This asks the narrower question directly of the walk, so the one position where the redundancy
    actually hurts is still covered.
    """
    scenario = load_scenario(REPO / "scenarios" / f"{scenario_name}.json")
    player_state = scenario.state.player_state(scenario.state.active_player)

    for capacity in (1, 2):
        for max_moves in (1, 2, 3):
            exhaustive = every_allocation_spelling(
                player_state, max_moves=max_moves, special_activity_capacity=capacity
            )
            walked = transition._allocation_move_sequences(
                player_state, max_moves=max_moves, special_activity_capacity=capacity
            )
            assert {allocation_outcome(s) for s in walked} == {
                allocation_outcome(s) for s in exhaustive
            }, f"allocation outcomes differ at capacity={capacity} max_moves={max_moves}"

    for max_steps in (1, 2, 3):
        exhaustive = every_ordination_spelling(player_state, max_steps=max_steps)
        walked = transition.legal_ordination_step_sequences(player_state, max_steps=max_steps)
        assert {ordination_outcome(s) for s in walked} == {
            ordination_outcome(s) for s in exhaustive
        }, f"ordination outcomes differ at max_steps={max_steps}"


def test_the_root_reaches_the_same_positions(generations) -> None:
    """Removing a synonym must not remove a position, asked of whole turns rather than sequences.

    This is what stops the search test below from being vacuous. Every legal move at the root is
    applied and the resulting positions collected; the two sets must match. A projection that
    merged two genuinely different moves loses a position here, whatever the search then does with
    it.
    """
    for name, scenario, before, after in generations:
        reached_before = set()
        reached_after = set()
        for actions, reached in ((before, reached_before), (after, reached_after)):
            for action in actions:
                landed = landing(scenario.state, action, scenario.config)
                if landed[0] == "state":
                    reached.add(landed[1])
        assert reached_after == reached_before, (
            f"{name}: the positions reachable in one move changed"
        )


def test_the_search_lands_on_the_same_line(generations) -> None:
    """Equivalent branches removed must not move the optimum.

    Worth knowing about the shape of this evidence: on the committed corpus the best line never
    contains an allocation or ordination move, so the principal variation alone could not tell
    these two generations apart. What makes the comparison mean something is the test above --
    the same positions are reachable -- and the node counts here, which come out equal because the
    search already collapsed the synonyms into one another through its transposition table.
    """
    monkeypatch = pytest.MonkeyPatch()
    for name, scenario, _before, _after in generations:
        after = solve_exact(scenario.state, scenario.config, 2)
        with monkeypatch.context() as patched:
            patched.setattr(transition, "_allocation_move_sequences", every_allocation_spelling)
            patched.setattr(
                transition, "legal_ordination_step_sequences", every_ordination_spelling
            )
            before = solve_exact(scenario.state, scenario.config, 2)

        assert before.best_score == after.best_score, f"{name}: the score moved"
        assert before.best_action_id == after.best_action_id, f"{name}: the chosen move changed"
        assert before.principal_variation_ids == after.principal_variation_ids, (
            f"{name}: the line changed"
        )
        assert before.nodes_expanded == after.nodes_expanded, (
            f"{name}: the search saw a different number of distinct positions"
        )


@pytest.fixture(scope="module")
def deep_generation():
    """The round-eighteen fixture, generated both ways.

    Worth the cost on its own: every committed scenario but this one offers under two hundred
    moves, and the whole committed corpus yields four hundred pairs to compare. This one position
    yields more than all of them together, and it is the only one whose decisions are dense enough
    for the redundancy to look like what it does in a real late game.
    """
    monkeypatch = pytest.MonkeyPatch()
    scenario = load_scenario(REPO / "scenarios" / f"{DEEP_FIXTURE}.json")
    with monkeypatch.context() as patched:
        patched.setattr(transition, "_allocation_move_sequences", every_allocation_spelling)
        patched.setattr(transition, "legal_ordination_step_sequences", every_ordination_spelling)
        before = legal_actions(scenario.state, scenario.config)
    return scenario, before


@pytest.mark.slow
def test_equal_outcome_survives_a_late_position_too(deep_generation) -> None:
    """The same equality check where the decisions are dense, over a bounded sample.

    Applying all thirty-six thousand spellings would be minutes of test time for evidence that
    stops improving long before that, so this walks the decisions in a fixed order and stops at a
    budget. Fixed order and fixed budget, so it examines the same actions every run.
    """
    scenario, before = deep_generation
    groups = defaultdict(list)
    for action in before:
        if sequenced(action):
            groups[(skeleton(action), outcome_of(action))].append(action)

    budget = 4000
    pairs = 0
    for _key, spellings in sorted(groups.items(), key=lambda item: repr(item[0])):
        if len(spellings) < 2 or pairs >= budget:
            continue
        first = landing(scenario.state, spellings[0], scenario.config)
        for other in spellings[1:]:
            pairs += 1
            assert landing(scenario.state, other, scenario.config) == first, (
                "two spellings of one outcome left the game in different places"
            )
    assert pairs >= budget, f"only {pairs} pairs compared at the deep fixture"


def test_the_late_position_still_reaches_everything_it_used_to(
    deep_generation, deep_actions
) -> None:
    """Completeness at the deep fixture, counted rather than sampled.

    Comparing outcomes per decision needs no application, so this one can afford to look at all six
    hundred allocation decisions rather than a sample of them.
    """
    scenario, before = deep_generation
    _shared_scenario, after = deep_actions

    reachable_before = defaultdict(set)
    reachable_after = defaultdict(set)
    for action in before:
        if sequenced(action):
            reachable_before[skeleton(action)].add(outcome_of(action))
    for action in after:
        if sequenced(action):
            reachable_after[skeleton(action)].add(outcome_of(action))

    assert set(reachable_after) == set(reachable_before)
    assert reachable_after == reachable_before
    assert sum(len(v) for v in reachable_after.values()) > 10_000, (
        "this fixture is here to be dense; something has shrunk it"
    )


def test_the_walk_keeps_every_length_an_outcome_is_reachable_at() -> None:
    """Hiring the Infirmary buys a move, and only a longer sequence proves it was spent.

    An outcome reachable in two moves must still be offered as a three-move sequence to the caller
    that hires, or hiring to reach it stops being a move at all. This is the one place where length
    is read as well as outcome, and it is why the memo carries the depth.
    """
    scenario = load_scenario(REPO / "scenarios" / "allocation_all_special_occupied_001.json")
    player_state = scenario.state.player_state(scenario.state.active_player)

    reachable_in_two = {
        allocation_outcome(s)
        for s in transition._allocation_move_sequences(
            player_state, max_moves=2, special_activity_capacity=1
        )
    }
    only_longer = transition._allocation_move_sequences(
        player_state, max_moves=3, special_activity_capacity=1, min_moves=3
    )
    lengths = {len(s) for s in only_longer}

    assert lengths == {3}, f"asked for three-move sequences and got lengths {lengths}"
    also_short = reachable_in_two & {allocation_outcome(s) for s in only_longer}
    assert also_short, (
        "no outcome reachable in two moves is offered as a three-move sequence, so hiring the "
        "Infirmary to reach one would no longer be a legal move"
    )
