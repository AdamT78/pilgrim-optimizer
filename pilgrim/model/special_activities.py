"""Special-activity occupancy model for one player board."""

from __future__ import annotations

from dataclasses import dataclass

SPECIAL_ACTIVITY_IDS: tuple[str, ...] = (
    "fields",
    "road_engineer",
    "stone_mason",
    "alms_house",
    "engraver",
    "vestry",
)


@dataclass(frozen=True, slots=True)
class SpecialActivities:
    """Per-player special-activity occupancy (one acolyte max per space)."""

    fields: bool = False
    road_engineer: bool = False
    stone_mason: bool = False
    alms_house: bool = False
    engraver: bool = False
    vestry: bool = False

    def __post_init__(self) -> None:
        for activity_id in SPECIAL_ACTIVITY_IDS:
            value = getattr(self, activity_id)
            if not isinstance(value, bool):
                raise ValueError(f"Special activity {activity_id} must be boolean.")

    @property
    def count(self) -> int:
        return sum(1 for activity_id in SPECIAL_ACTIVITY_IDS if getattr(self, activity_id))

    def has(self, activity_id: str) -> bool:
        _validate_activity_id(activity_id)
        return bool(getattr(self, activity_id))

    def with_activity(self, activity_id: str, occupied: bool) -> SpecialActivities:
        _validate_activity_id(activity_id)
        if occupied == self.has(activity_id):
            return self
        return SpecialActivities(
            fields=self.fields if activity_id != "fields" else occupied,
            road_engineer=(
                self.road_engineer
                if activity_id != "road_engineer"
                else occupied
            ),
            stone_mason=self.stone_mason if activity_id != "stone_mason" else occupied,
            alms_house=self.alms_house if activity_id != "alms_house" else occupied,
            engraver=self.engraver if activity_id != "engraver" else occupied,
            vestry=self.vestry if activity_id != "vestry" else occupied,
        )

    @property
    def grain(self) -> bool:
        """Deprecated alias for backwards compatibility with older tests/scenarios."""
        return self.fields

    def occupied(self) -> tuple[str, ...]:
        return tuple(
            activity_id
            for activity_id in SPECIAL_ACTIVITY_IDS
            if getattr(self, activity_id)
        )

    def available(self) -> tuple[str, ...]:
        return tuple(
            activity_id
            for activity_id in SPECIAL_ACTIVITY_IDS
            if not getattr(self, activity_id)
        )


def _validate_activity_id(activity_id: str) -> None:
    if activity_id not in SPECIAL_ACTIVITY_IDS:
        raise ValueError(f"Unknown special activity id: {activity_id}")
