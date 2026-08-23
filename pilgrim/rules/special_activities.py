"""Helpers for special-activity occupancy and activity-specific bonuses."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from pilgrim.model.actions import AllocationMove
from pilgrim.model.special_activities import MAX_SPECIAL_ACTIVITY_ACOLYTES, SPECIAL_ACTIVITY_IDS
from pilgrim.model.state import PlayerState

AllocationOutcome = tuple[tuple[str, int], ...]


def allocation_outcome(moves: tuple[AllocationMove, ...]) -> AllocationOutcome:
    """Where a sequence of allocation moves leaves the acolytes, net of how it got there.

    An allocation move carries one acolyte from one slot to another and costs nothing, so a
    sequence is fully described by how many acolytes each slot ends up gaining or losing. Order
    gates legality -- you cannot move out of an empty slot -- but never the result.

    Two things fall out of that, and the second is why this is worth having. Sequences that differ
    only in the order of their moves land on the same vector. So do sequences of DIFFERENT lengths
    whenever the longer one contains a detour: Abbey to Fields and back again returns every acolyte
    where it started, and cancels out of the vector entirely. Both are offered today as separate
    moves, which is how one decision came to offer eight hundred and fifty-eight ways of doing
    sixty-four things.

    Slots that end level are dropped rather than recorded as zero, so a sequence that puts
    everything back where it found it projects to the empty tuple -- which is honest, because that
    is precisely what such a sequence does.
    """
    net: Counter[str] = Counter()
    for move in moves:
        net[move.destination] += 1
        net[move.source] -= 1
    return tuple(sorted((slot, delta) for slot, delta in net.items() if delta))


def occupied_special_activities(player_state: PlayerState) -> tuple[str, ...]:
    """Return occupied special-activity ids for one player."""
    return player_state.special_activities.occupied()


def special_activity_count(player_state: PlayerState, activity_id: str | None = None) -> int:
    """
    Return special-activity occupancy count.

    - no activity_id: total acolytes across all special activities
    - with activity_id: count for that one activity
    """
    if activity_id is None:
        return player_state.special_activities.count
    return player_state.special_activities.count_for(activity_id)


def has_special_activity(player_state: PlayerState, activity_id: str) -> bool:
    """Return True when one activity is occupied."""
    return special_activity_count(player_state, activity_id) > 0


def special_activity_capacity(*, chapter_house_active: bool) -> int:
    """Return Special Activity occupancy capacity for one space."""
    return 2 if chapter_house_active else 1


def available_special_activities(
    player_state: PlayerState,
    *,
    capacity: int = 1,
) -> tuple[str, ...]:
    """Return special-activity ids whose occupancy is below capacity."""
    return player_state.special_activities.available(capacity=capacity)


def allocate_abbey_to_special_activity(
    player_state: PlayerState,
    activity_id: str,
    *,
    capacity: int = 1,
) -> PlayerState:
    """Move one abbey acolyte into one not-full special-activity space."""
    if player_state.workforce.abbey < 1:
        raise ValueError("Allocation requires at least 1 abbey acolyte.")
    if special_activity_count(player_state, activity_id) >= capacity:
        raise ValueError(f"Special activity is full: {activity_id}")
    return replace(
        player_state,
        workforce=replace(
            player_state.workforce,
            abbey=player_state.workforce.abbey - 1,
        ),
        special_activities=player_state.special_activities.increment(
            activity_id,
            capacity=capacity,
        ),
    )


def allocate_special_activity_to_abbey(
    player_state: PlayerState,
    activity_id: str,
) -> PlayerState:
    """Move one occupied special-activity acolyte back to abbey."""
    if not has_special_activity(player_state, activity_id):
        raise ValueError(f"Special activity is not occupied: {activity_id}")
    return replace(
        player_state,
        workforce=replace(
            player_state.workforce,
            abbey=player_state.workforce.abbey + 1,
        ),
        special_activities=player_state.special_activities.decrement(activity_id),
    )


def allocate_special_activity_to_special_activity(
    player_state: PlayerState,
    *,
    source_activity_id: str,
    destination_activity_id: str,
    capacity: int = 1,
) -> PlayerState:
    """Move one acolyte from occupied source special-activity to not-full destination."""
    if source_activity_id == destination_activity_id:
        raise ValueError("Allocation source and destination special activity must differ.")
    if not has_special_activity(player_state, source_activity_id):
        raise ValueError(f"Special activity is not occupied: {source_activity_id}")
    if special_activity_count(player_state, destination_activity_id) >= capacity:
        raise ValueError(f"Special activity is full: {destination_activity_id}")
    after_source_decrement = player_state.special_activities.decrement(source_activity_id)
    return replace(
        player_state,
        special_activities=after_source_decrement.increment(
            destination_activity_id,
            capacity=capacity,
        ),
    )


def legal_allocation_moves(
    player_state: PlayerState,
    *,
    capacity: int = 1,
) -> tuple[AllocationMove, ...]:
    """Return legal one-step allocation moves in deterministic order."""
    if capacity < 1 or capacity > MAX_SPECIAL_ACTIVITY_ACOLYTES:
        raise ValueError(
            f"Special activity capacity must be in range 1..{MAX_SPECIAL_ACTIVITY_ACOLYTES}."
        )
    occupied = occupied_special_activities(player_state)
    available_targets = available_special_activities(player_state, capacity=capacity)
    moves: list[AllocationMove] = []

    if player_state.workforce.abbey > 0:
        for activity_id in available_targets:
            moves.append(AllocationMove(source="abbey", destination=activity_id))

    for source_activity_id in occupied:
        for destination_activity_id in available_targets:
            if source_activity_id != destination_activity_id:
                moves.append(
                    AllocationMove(
                        source=source_activity_id,
                        destination=destination_activity_id,
                    )
                )

    for activity_id in occupied:
        moves.append(AllocationMove(source=activity_id, destination="abbey"))

    return tuple(moves)


def apply_allocation_move(player_state: PlayerState, move: AllocationMove) -> PlayerState:
    """Apply one allocation move with validation."""
    return apply_allocation_move_with_capacity(player_state, move, capacity=1)


def apply_allocation_move_with_capacity(
    player_state: PlayerState,
    move: AllocationMove,
    *,
    capacity: int = 1,
) -> PlayerState:
    """Apply one allocation move with one explicit Special Activity capacity."""
    if move.source == "abbey":
        if move.destination == "abbey":
            raise ValueError("Allocation move abbey -> abbey is not legal.")
        return allocate_abbey_to_special_activity(
            player_state,
            move.destination,
            capacity=capacity,
        )

    if move.destination == "abbey":
        return allocate_special_activity_to_abbey(player_state, move.source)

    return allocate_special_activity_to_special_activity(
        player_state,
        source_activity_id=move.source,
        destination_activity_id=move.destination,
        capacity=capacity,
    )


def clerical_silversmith_bonus(player_state: PlayerState) -> int:
    """Engraver adds +1 silver per acolyte to clerical_silversmith."""
    return special_activity_count(player_state, "engraver")


def clerical_devotion_bonus(player_state: PlayerState) -> int:
    """Vestry adds +1 piety per acolyte to clerical_devotion."""
    return special_activity_count(player_state, "vestry")


def produce_wheat_fields_bonus(player_state: PlayerState) -> int:
    """Fields adds +1 wheat per acolyte to produce_wheat."""
    return special_activity_count(player_state, "fields")


def produce_stone_mason_bonus(player_state: PlayerState) -> int:
    """Stone Mason adds +1 stone per acolyte to produce_stone."""
    return special_activity_count(player_state, "stone_mason")


def road_engineer_duty_value_bonus_hook(player_state: PlayerState, *, action_key: str) -> int:
    """
    Placeholder hook for Road Engineer.

    Road-building / construct systems are not yet implemented in the sandbox runtime.
    """
    if action_key == "build_roads":
        return special_activity_count(player_state, "road_engineer")
    return 0


def alms_house_duty_value_bonus_capacity(player_state: PlayerState) -> int:
    """Return maximum +duty-value bonus available from Alms House occupancy."""
    return special_activity_count(player_state, "alms_house")


def road_engineer_construct_extra_roads_bonus(player_state: PlayerState) -> int:
    """Return max additional deferred construct roads from Road Engineer occupancy."""
    return special_activity_count(player_state, "road_engineer")


def all_special_activity_ids() -> tuple[str, ...]:
    """Return canonical special-activity identifiers."""
    return SPECIAL_ACTIVITY_IDS


def format_special_activities(player_state: PlayerState) -> str:
    """Compact string for verbose CLI summary."""
    parts: list[str] = []
    for activity_id in all_special_activity_ids():
        count = special_activity_count(player_state, activity_id)
        if count <= 0:
            continue
        if count == 1:
            parts.append(activity_id)
        else:
            parts.append(f"{activity_id} x{count}")
    if not parts:
        return "none"
    return ", ".join(parts)
