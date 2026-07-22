"""Dummy acolyte group models and formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.enums import CANONICAL_POSITION_NAMES, position_name

DUMMY_VECTOR_LENGTH = 9
EMPTY_DUMMY_VECTOR: tuple[int, ...] = (0,) * DUMMY_VECTOR_LENGTH


@dataclass(frozen=True, slots=True)
class DummyAcolyteGroups:
    """
    Dummy acolytes tracked as two internal groups.

    Both vectors must be length 9 and keep city position (index 0) empty.
    """

    north_group: tuple[int, ...] = EMPTY_DUMMY_VECTOR
    south_group: tuple[int, ...] = EMPTY_DUMMY_VECTOR

    def __post_init__(self) -> None:
        _validate_group_vector(self.north_group, group_name="north_group")
        _validate_group_vector(self.south_group, group_name="south_group")

    @property
    def north_total(self) -> int:
        return sum(self.north_group)

    @property
    def south_total(self) -> int:
        return sum(self.south_group)

    @property
    def total_count(self) -> int:
        return self.north_total + self.south_total

    @property
    def total_vector(self) -> tuple[int, ...]:
        return tuple(
            self.north_group[index] + self.south_group[index]
            for index in range(DUMMY_VECTOR_LENGTH)
        )

    def dummy_at_position(self, position: int) -> int:
        return self.total_vector[position]


def dummy_total(dummy: DummyAcolyteGroups) -> int:
    """Return total count across north and south dummy groups."""
    return dummy.total_count


def dummy_at_position(dummy: DummyAcolyteGroups, position: int) -> int:
    """Return total dummy acolytes at one board position."""
    return dummy.dummy_at_position(position)


def validate_dummy_acolytes(dummy: DummyAcolyteGroups, *, player_count: int) -> None:
    """
    Validate dummy groups against table player-count expectations.

    - 2 players: 3 dummies per group
    - 3 players: 2 dummies per group
    - 4 players: 0 dummies
    """
    if player_count not in (2, 3, 4):
        raise ValueError(f"Unsupported player_count for dummy setup: {player_count}.")

    expected_per_group = {2: 3, 3: 2, 4: 0}[player_count]
    if dummy.north_total != expected_per_group:
        raise ValueError(
            "Dummy north_group total does not match player_count expectation: "
            f"{dummy.north_total} vs expected {expected_per_group}."
        )
    if dummy.south_total != expected_per_group:
        raise ValueError(
            "Dummy south_group total does not match player_count expectation: "
            f"{dummy.south_total} vs expected {expected_per_group}."
        )


def format_dummy_acolytes(
    vector: tuple[int, ...],
    *,
    positions: tuple[str, ...] = CANONICAL_POSITION_NAMES,
) -> str:
    """
    Format non-zero duty entries as "name=count".

    City (index 0) and zero-count duty positions are omitted.
    """
    if len(vector) != DUMMY_VECTOR_LENGTH:
        raise ValueError(
            f"Dummy vector must have {DUMMY_VECTOR_LENGTH} positions, got {len(vector)}."
        )
    parts = [
        f"{position_name(index, positions)}={count}"
        for index, count in enumerate(vector)
        if index != 0 and count > 0
    ]
    return ", ".join(parts) if parts else "none"


def _validate_group_vector(vector: tuple[int, ...], *, group_name: str) -> None:
    if len(vector) != DUMMY_VECTOR_LENGTH:
        raise ValueError(
            f"Dummy {group_name} must have {DUMMY_VECTOR_LENGTH} positions, got {len(vector)}."
        )
    if vector[0] != 0:
        raise ValueError(f"Dummy {group_name} city position must remain empty (index 0).")
    if any(count < 0 for count in vector):
        raise ValueError(f"Dummy {group_name} cannot contain negative counts.")
    if any(count > 1 for count in vector[1:]):
        raise ValueError(
            f"Dummy {group_name} cannot place more than one acolyte on one Duty tile."
        )
