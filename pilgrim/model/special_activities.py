"""Special-activity occupancy model for one player board."""

from __future__ import annotations

from dataclasses import dataclass, replace

SPECIAL_ACTIVITY_IDS: tuple[str, ...] = (
    "fields",
    "road_engineer",
    "stone_mason",
    "alms_house",
    "engraver",
    "vestry",
)
MAX_SPECIAL_ACTIVITY_ACOLYTES = 2


@dataclass(frozen=True, slots=True)
class SpecialActivities:
    """Per-player special-activity occupancy counts (0..2 acolytes per space)."""

    fields: int = 0
    road_engineer: int = 0
    stone_mason: int = 0
    alms_house: int = 0
    engraver: int = 0
    vestry: int = 0

    def __post_init__(self) -> None:
        for activity_id in SPECIAL_ACTIVITY_IDS:
            value = getattr(self, activity_id)
            # Backward-compatible bool inputs are normalized to integer counts.
            if isinstance(value, bool):
                value = int(value)
                object.__setattr__(self, activity_id, value)
            if not isinstance(value, int):
                raise ValueError(f"Special activity {activity_id} count must be integer.")
            if value < 0 or value > MAX_SPECIAL_ACTIVITY_ACOLYTES:
                raise ValueError(
                    f"Special activity {activity_id} count must be in range "
                    f"0..{MAX_SPECIAL_ACTIVITY_ACOLYTES}."
                )

    @property
    def count(self) -> int:
        return sum(self.count_for(activity_id) for activity_id in SPECIAL_ACTIVITY_IDS)

    def count_for(self, activity_id: str) -> int:
        _validate_activity_id(activity_id)
        return int(getattr(self, activity_id))

    def has(self, activity_id: str) -> bool:
        return self.count_for(activity_id) > 0

    def with_count(self, activity_id: str, count: int) -> SpecialActivities:
        _validate_activity_id(activity_id)
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError(f"Special activity {activity_id} count must be integer.")
        if count < 0 or count > MAX_SPECIAL_ACTIVITY_ACOLYTES:
            raise ValueError(
                f"Special activity {activity_id} count must be in range "
                f"0..{MAX_SPECIAL_ACTIVITY_ACOLYTES}."
            )
        if count == self.count_for(activity_id):
            return self
        return replace(self, **{activity_id: count})

    def with_activity(self, activity_id: str, occupied: bool | int) -> SpecialActivities:
        """
        Backward-compatible setter for one activity.

        - bool -> 0/1 occupancy
        - int  -> explicit count
        """
        if isinstance(occupied, bool):
            count = 1 if occupied else 0
        elif isinstance(occupied, int):
            count = occupied
        else:
            raise ValueError(f"Special activity {activity_id} occupancy must be bool or int.")
        return self.with_count(activity_id, count)

    def increment(
        self,
        activity_id: str,
        *,
        amount: int = 1,
        capacity: int = MAX_SPECIAL_ACTIVITY_ACOLYTES,
    ) -> SpecialActivities:
        _validate_activity_id(activity_id)
        if amount <= 0:
            raise ValueError("Increment amount must be positive.")
        if capacity < 0 or capacity > MAX_SPECIAL_ACTIVITY_ACOLYTES:
            raise ValueError(
                f"Special activity capacity must be in range 0..{MAX_SPECIAL_ACTIVITY_ACOLYTES}."
            )
        new_count = self.count_for(activity_id) + amount
        if new_count > capacity:
            raise ValueError(
                f"Special activity {activity_id} cannot exceed capacity {capacity}."
            )
        return self.with_count(activity_id, new_count)

    def decrement(self, activity_id: str, *, amount: int = 1) -> SpecialActivities:
        _validate_activity_id(activity_id)
        if amount <= 0:
            raise ValueError("Decrement amount must be positive.")
        new_count = self.count_for(activity_id) - amount
        if new_count < 0:
            raise ValueError(f"Special activity {activity_id} cannot drop below zero.")
        return self.with_count(activity_id, new_count)

    @property
    def grain(self) -> bool:
        """Deprecated alias for backwards compatibility with older tests/scenarios."""
        return self.fields > 0

    def occupied(self) -> tuple[str, ...]:
        return tuple(
            activity_id
            for activity_id in SPECIAL_ACTIVITY_IDS
            if self.count_for(activity_id) > 0
        )

    def available(self, *, capacity: int = 1) -> tuple[str, ...]:
        if capacity < 0 or capacity > MAX_SPECIAL_ACTIVITY_ACOLYTES:
            raise ValueError(
                f"Special activity capacity must be in range 0..{MAX_SPECIAL_ACTIVITY_ACOLYTES}."
            )
        return tuple(
            activity_id
            for activity_id in SPECIAL_ACTIVITY_IDS
            if self.count_for(activity_id) < capacity
        )

    def as_dict(self) -> dict[str, int]:
        return {
            activity_id: self.count_for(activity_id)
            for activity_id in SPECIAL_ACTIVITY_IDS
        }


def _validate_activity_id(activity_id: str) -> None:
    if activity_id not in SPECIAL_ACTIVITY_IDS:
        raise ValueError(f"Unknown special activity id: {activity_id}")
