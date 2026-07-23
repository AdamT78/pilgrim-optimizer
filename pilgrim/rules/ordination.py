"""Ordination duty step rules and sequence generation helpers."""

from __future__ import annotations

from dataclasses import replace

from pilgrim.model.state import PlayerState

ORDINATION_ORDAIN = "ordain"
ORDINATION_MISSION = "mission"
ORDINATION_STEP_TYPES: tuple[str, str] = (ORDINATION_ORDAIN, ORDINATION_MISSION)


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
    """Generate deterministic legal ordination step sequences up to max_steps."""
    if max_steps <= 0:
        return ()

    discovered_sequences: list[tuple[str, ...]] = []

    def _walk(current_player_state: PlayerState, current_path: tuple[str, ...]) -> None:
        if len(current_path) >= max_steps:
            return
        for step in legal_ordination_steps(current_player_state):
            try:
                next_state = apply_ordination_step(current_player_state, step)
            except ValueError:
                continue
            next_path = (*current_path, step)
            discovered_sequences.append(next_path)
            _walk(next_state, next_path)

    _walk(player_state, ())

    ordered_sequences: list[tuple[str, ...]] = []
    for length in range(max_steps, 0, -1):
        for sequence in discovered_sequences:
            if len(sequence) == length:
                ordered_sequences.append(sequence)

    seen: set[tuple[str, ...]] = set()
    unique_sequences: list[tuple[str, ...]] = []
    for sequence in ordered_sequences:
        if sequence in seen:
            continue
        seen.add(sequence)
        unique_sequences.append(sequence)
    return tuple(unique_sequences)
