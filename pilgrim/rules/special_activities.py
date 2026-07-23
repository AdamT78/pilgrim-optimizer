"""Helpers for special-activity occupancy and activity-specific bonuses."""

from __future__ import annotations

from dataclasses import replace

from pilgrim.model.actions import AllocationMove
from pilgrim.model.resources import Resources
from pilgrim.model.special_activities import SPECIAL_ACTIVITY_IDS
from pilgrim.model.state import PlayerState


def occupied_special_activities(player_state: PlayerState) -> tuple[str, ...]:
    """Return occupied special-activity ids for one player."""
    return player_state.special_activities.occupied()


def special_activity_count(player_state: PlayerState) -> int:
    """Return occupied special-activity count for one player."""
    return player_state.special_activities.count


def has_special_activity(player_state: PlayerState, activity_id: str) -> bool:
    """Return True when one activity is occupied."""
    return player_state.special_activities.has(activity_id)


def available_special_activities(player_state: PlayerState) -> tuple[str, ...]:
    """Return empty special-activity ids for one player."""
    return player_state.special_activities.available()


def allocate_abbey_to_special_activity(
    player_state: PlayerState,
    activity_id: str,
) -> PlayerState:
    """Move one abbey acolyte into one empty special-activity space."""
    if player_state.workforce.abbey < 1:
        raise ValueError("Allocation requires at least 1 abbey acolyte.")
    if has_special_activity(player_state, activity_id):
        raise ValueError(f"Special activity already occupied: {activity_id}")
    return replace(
        player_state,
        workforce=replace(
            player_state.workforce,
            abbey=player_state.workforce.abbey - 1,
        ),
        special_activities=player_state.special_activities.with_activity(activity_id, True),
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
        special_activities=player_state.special_activities.with_activity(activity_id, False),
    )


def allocate_special_activity_to_special_activity(
    player_state: PlayerState,
    *,
    source_activity_id: str,
    destination_activity_id: str,
) -> PlayerState:
    """Move one acolyte from occupied source special-activity to empty destination."""
    if source_activity_id == destination_activity_id:
        raise ValueError("Allocation source and destination special activity must differ.")
    if not has_special_activity(player_state, source_activity_id):
        raise ValueError(f"Special activity is not occupied: {source_activity_id}")
    if has_special_activity(player_state, destination_activity_id):
        raise ValueError(f"Special activity already occupied: {destination_activity_id}")
    after_source_clear = player_state.special_activities.with_activity(source_activity_id, False)
    return replace(
        player_state,
        special_activities=after_source_clear.with_activity(destination_activity_id, True),
    )


def legal_allocation_moves(player_state: PlayerState) -> tuple[AllocationMove, ...]:
    """Return legal one-step allocation moves in deterministic order."""
    occupied = occupied_special_activities(player_state)
    empty = available_special_activities(player_state)
    moves: list[AllocationMove] = []

    if player_state.workforce.abbey > 0:
        for activity_id in empty:
            moves.append(AllocationMove(source="abbey", destination=activity_id))

    for source_activity_id in occupied:
        for destination_activity_id in empty:
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
    if move.source == "abbey":
        if move.destination == "abbey":
            raise ValueError("Allocation move abbey -> abbey is not legal.")
        return allocate_abbey_to_special_activity(player_state, move.destination)

    if move.destination == "abbey":
        return allocate_special_activity_to_abbey(player_state, move.source)

    return allocate_special_activity_to_special_activity(
        player_state,
        source_activity_id=move.source,
        destination_activity_id=move.destination,
    )


def clerical_silversmith_bonus(player_state: PlayerState) -> int:
    """Engraver adds +1 silver to clerical_silversmith."""
    return 1 if has_special_activity(player_state, "engraver") else 0


def clerical_devotion_bonus(player_state: PlayerState) -> int:
    """Vestry adds +1 piety to clerical_devotion."""
    return 1 if has_special_activity(player_state, "vestry") else 0


def produce_wheat_fields_bonus(player_state: PlayerState) -> int:
    """Fields special activity adds +1 wheat to produce_wheat."""
    return 1 if has_special_activity(player_state, "fields") else 0


def produce_stone_mason_bonus(player_state: PlayerState) -> int:
    """Stone Mason adds +1 stone to produce_stone."""
    return 1 if has_special_activity(player_state, "stone_mason") else 0


def road_engineer_duty_value_bonus_hook(player_state: PlayerState, *, action_key: str) -> int:
    """
    Placeholder hook for Road Engineer.

    Road-building / construct systems are not yet implemented in the sandbox runtime.
    """
    if action_key == "build_roads" and has_special_activity(player_state, "road_engineer"):
        return 1
    return 0


def can_use_alms_house_bonus(player_state: PlayerState) -> bool:
    """Return True when Alms House special activity is occupied."""
    return has_special_activity(player_state, "alms_house")


def alms_house_extra_payment_options(resources: Resources) -> tuple[tuple[int, int], ...]:
    """
    Return legal Alms House extra payment options as (extra_silver, extra_wheat).

    Exactly one of silver/wheat must be paid.
    """
    options: list[tuple[int, int]] = []
    if resources.silver >= 1:
        options.append((1, 0))
    if resources.wheat >= 1:
        options.append((0, 1))
    return tuple(options)


def all_special_activity_ids() -> tuple[str, ...]:
    """Return canonical special-activity identifiers."""
    return SPECIAL_ACTIVITY_IDS


def format_special_activities(player_state: PlayerState) -> str:
    """Compact string for verbose CLI summary."""
    occupied = occupied_special_activities(player_state)
    if not occupied:
        return "none"
    return ", ".join(occupied)
