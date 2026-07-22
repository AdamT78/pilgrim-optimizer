"""Dummy acolyte setup and season-end movement helpers."""

from __future__ import annotations

from pilgrim.model.dummy import DUMMY_VECTOR_LENGTH, DummyAcolyteGroups
from pilgrim.model.enums import EventType, PlayerId, position_name
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.state import GameState

NORTH_DUTY_POSITION = 1
SOUTH_DUTY_POSITION = 5


def clockwise_duty_positions() -> tuple[int, ...]:
    """Return canonical clockwise duty order (city excluded)."""
    return (1, 2, 3, 4, 5, 6, 7, 8)


def seed_from_anchor(anchor_position: int, count: int) -> tuple[int, ...]:
    """Seed one dummy group clockwise from anchor, including anchor tile."""
    if count < 0:
        raise ValueError("Dummy seed count cannot be negative.")
    order = _clockwise_from_anchor(anchor_position)
    if count > len(order):
        raise ValueError("Dummy seed count cannot exceed number of duty positions.")
    vector = [0] * DUMMY_VECTOR_LENGTH
    for position in order[:count]:
        vector[position] = 1
    return tuple(vector)


def seed_dummy_groups(player_count: int) -> DummyAcolyteGroups:
    """Seed both dummy groups for table player-count."""
    if player_count == 2:
        per_group = 3
    elif player_count == 3:
        per_group = 2
    elif player_count == 4:
        per_group = 0
    else:
        raise ValueError(f"Unsupported player_count for dummy setup: {player_count}.")

    return DummyAcolyteGroups(
        north_group=seed_from_anchor(NORTH_DUTY_POSITION, per_group),
        south_group=seed_from_anchor(SOUTH_DUTY_POSITION, per_group),
    )


def seed_dummy_acolytes(player_count: int) -> tuple[int, ...]:
    """Return total dummy occupancy vector for setup/debug convenience."""
    groups = seed_dummy_groups(player_count)
    return groups.total_vector


def move_dummy_acolytes_end_of_season(
    state: GameState,
    *,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Move the rearmost acolyte in each dummy group at season end."""
    dummy_before = state.dummy_acolytes
    (
        north_after,
        north_from,
        north_to,
        north_before_positions,
        north_after_positions,
    ) = _move_group_rearmost(
        dummy_before.north_group,
        anchor_position=NORTH_DUTY_POSITION,
    )
    (
        south_after,
        south_from,
        south_to,
        south_before_positions,
        south_after_positions,
    ) = _move_group_rearmost(
        dummy_before.south_group,
        anchor_position=SOUTH_DUTY_POSITION,
    )

    dummy_after = DummyAcolyteGroups(north_group=north_after, south_group=south_after)
    next_state = state.with_dummy_acolytes(dummy_after)

    events: list[GameEvent] = []
    if north_from is not None and north_to is not None and north_from != north_to:
        events.append(
            GameEvent(
                event_type=EventType.DUMMY_ACOLYTE_MOVE,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    group="north_group",
                    from_position=north_from,
                    to_position=north_to,
                    before_positions=_format_group_positions(north_before_positions),
                    after_positions=_format_group_positions(north_after_positions),
                ),
            )
        )
    if south_from is not None and south_to is not None and south_from != south_to:
        events.append(
            GameEvent(
                event_type=EventType.DUMMY_ACOLYTE_MOVE,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    group="south_group",
                    from_position=south_from,
                    to_position=south_to,
                    before_positions=_format_group_positions(south_before_positions),
                    after_positions=_format_group_positions(south_after_positions),
                ),
            )
        )
    return next_state, tuple(events)


def _move_group_rearmost(
    group_vector: tuple[int, ...],
    *,
    anchor_position: int,
) -> tuple[tuple[int, ...], int | None, int | None, tuple[int, ...], tuple[int, ...]]:
    ordered = _clockwise_from_anchor(anchor_position)
    occupied = tuple(position for position in ordered if group_vector[position] > 0)
    if not occupied:
        return group_vector, None, None, (), ()

    rearmost = occupied[0]
    foremost = occupied[-1]
    destination = _next_unoccupied_after(group_vector, position=foremost)

    updated = list(group_vector)
    updated[rearmost] -= 1
    updated[destination] += 1
    updated_tuple = tuple(updated)
    occupied_after = tuple(position for position in ordered if updated_tuple[position] > 0)
    return updated_tuple, rearmost, destination, occupied, occupied_after


def _clockwise_from_anchor(anchor_position: int) -> tuple[int, ...]:
    order = clockwise_duty_positions()
    try:
        anchor_index = order.index(anchor_position)
    except ValueError as exc:
        raise ValueError(f"Anchor is not a duty position: {anchor_position}.") from exc
    return order[anchor_index:] + order[:anchor_index]


def _next_unoccupied_after(group_vector: tuple[int, ...], *, position: int) -> int:
    order = clockwise_duty_positions()
    start_index = order.index(position)
    for offset in range(1, len(order) + 1):
        candidate = order[(start_index + offset) % len(order)]
        if group_vector[candidate] == 0:
            return candidate
    raise ValueError("No unoccupied duty tile available for dummy movement.")


def _format_group_positions(positions: tuple[int, ...]) -> str:
    if not positions:
        return ""
    return ", ".join(position_name(position) for position in positions)
