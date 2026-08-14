"""Ordination duty step rules and sequence generation helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from pilgrim.model.state import PlayerState

ORDINATION_ORDAIN = "ordain"
ORDINATION_MISSION = "mission"
ORDINATION_STEP_TYPES: tuple[str, str] = (ORDINATION_ORDAIN, ORDINATION_MISSION)

OrdinationOutcome = tuple[tuple[str, int], ...]


def ordination_outcome(steps: tuple[str, ...]) -> OrdinationOutcome:
    """What a step sequence does, with the order it was written in discarded.

    Order gates legality -- you cannot mission out of an empty Abbey -- but it never gates the
    result. Each ordain moves a serf from village to Abbey, each mission moves an acolyte from
    Abbey to the City, and each of either costs one wheat, so what a sequence leaves behind is
    settled by HOW MANY of each it contains and not by the order they were written in. The count
    also fixes the length, which matters because length is read separately for the wheat cost and
    for the Infirmary bonus.

    So `('ordain', 'mission')` and `('mission', 'ordain')` project to the same thing, and only one
    of them needs offering.
    """
    return tuple(sorted(Counter(steps).items()))


def legal_ordination_steps(player_state: PlayerState) -> tuple[str, ...]:
    """Return legal single-step ordination options from one player state."""
    if player_state.resources.wheat <= 0:
        return ()
    legal_steps: list[str] = []
    if player_state.workforce.village > 0:
        legal_steps.append(ORDINATION_ORDAIN)
    if player_state.workforce.abbey > 0:
        legal_steps.append(ORDINATION_MISSION)
    return tuple(legal_steps)


def apply_ordination_step(player_state: PlayerState, step: str) -> PlayerState:
    """Apply one ordination step with wheat payment and workforce movement."""
    if step not in ORDINATION_STEP_TYPES:
        raise ValueError(f"Unknown ordination step: {step}")
    if player_state.resources.wheat <= 0:
        raise ValueError("Ordination step requires 1 wheat.")

    workforce = player_state.workforce
    if step == ORDINATION_ORDAIN:
        if workforce.village <= 0:
            raise ValueError("Ordain requires at least 1 village serf.")
        workforce = replace(
            workforce,
            village=workforce.village - 1,
            abbey=workforce.abbey + 1,
        )
    elif step == ORDINATION_MISSION:
        if workforce.abbey <= 0:
            raise ValueError("Mission requires at least 1 abbey acolyte.")
        city_mancala = list(workforce.mancala)
        city_mancala[0] += 1
        workforce = replace(
            workforce,
            mancala=tuple(city_mancala),
            abbey=workforce.abbey - 1,
        )

    new_resources = player_state.resources.add(wheat=-1)
    if new_resources.wheat < 0:
        raise ValueError("Ordination step cannot overdraw wheat.")
    return replace(
        player_state,
        resources=new_resources,
        workforce=workforce,
    )


def legal_ordination_step_sequences(
    player_state: PlayerState,
    *,
    max_steps: int,
) -> tuple[tuple[str, ...], ...]:
    """Generate one legal ordination step sequence per distinct outcome, up to max_steps.

    This used to walk depth first and emit every legal SPELLING, so a player was offered both
    `('ordain', 'mission')` and `('mission', 'ordain')` as separate moves although they leave the
    game in exactly the same place. That is a real cost to the search and an incoherent thing to
    put in front of a player, who would be asked to pick between two descriptions of one move.

    So the walk is breadth first and remembers outcomes rather than paths. Reaching an outcome a
    second time adds nothing -- the position after it is the same position, so everything reachable
    onward from it has already been queued -- and the branch is dropped where it is found rather
    than generated and collapsed afterwards.

    Breadth first is what makes the surviving spelling the SHORTEST one, since an outcome is
    recorded the first time it is reached and no later arrival can be shorter. Where several
    spellings of one outcome share that shortest length, the surviving one is whichever the walk
    reached first: parents in the order the previous level recorded them, and within a parent the
    order `legal_ordination_steps` returns. Nothing is constructed -- every sequence handed back is
    one this function walked and found legal step by step.
    """
    if max_steps <= 0:
        return ()

    shortest_by_outcome: dict[OrdinationOutcome, tuple[str, ...]] = {}
    frontier: list[tuple[PlayerState, tuple[str, ...]]] = [(player_state, ())]

    for _depth in range(max_steps):
        next_frontier: list[tuple[PlayerState, tuple[str, ...]]] = []
        for current_player_state, current_path in frontier:
            for step in legal_ordination_steps(current_player_state):
                try:
                    next_state = apply_ordination_step(current_player_state, step)
                except ValueError:
                    continue
                next_path = (*current_path, step)
                outcome = ordination_outcome(next_path)
                if outcome in shortest_by_outcome:
                    continue
                shortest_by_outcome[outcome] = next_path
                next_frontier.append((next_state, next_path))
        frontier = next_frontier

    # Longest first, as this has always emitted them. The sort is stable, so sequences of one
    # length keep the order the walk found them in.
    sequences = sorted(shortest_by_outcome.values(), key=len, reverse=True)
    return tuple(sequences)
