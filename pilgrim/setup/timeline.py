"""Abstract 26-round setup timeline helpers for seeded setup generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

TOTAL_BORDER_ROUNDS = 26
PILGRIMAGE_SITE_ORDER: tuple[str, ...] = ("site_1", "site_2", "site_3", "site_4")
PILGRIMAGE_ROLL_KEYS: tuple[str, ...] = ("nw", "ne", "se", "sw")
PILGRIMAGE_ROLL_MIN = 1
PILGRIMAGE_ROLL_MAX = 6
_PILGRIMAGE_OFFSETS: dict[str, int] = {
    "nw": 0,
    "ne": 6,
    "se": 13,
    "sw": 19,
}
_SLOT_BUILDING_BLOCKED_KINDS: frozenset[str] = frozenset(
    {
        "pilgrimage_site",
        "empty_after_pilgrimage",
        "empty_after_building_level",
    }
)

SetupTimelineSlotKind = Literal[
    "pilgrimage_site",
    "empty_after_pilgrimage",
    "empty_after_building_level",
    "building",
    "empty",
]


@dataclass(frozen=True, slots=True)
class SetupTimelineSlot:
    """One abstract timeline slot for a single round."""

    round_number: int
    kind: SetupTimelineSlotKind
    site: str | None = None
    building_id: str | None = None
    building_level: int | None = None


def generate_pilgrimage_rolls(rng) -> dict[str, int]:
    """Return deterministic d6 pilgrimage rolls for NW/NE/SE/SW."""
    return {
        key: int(rng.randint(PILGRIMAGE_ROLL_MIN, PILGRIMAGE_ROLL_MAX))
        for key in PILGRIMAGE_ROLL_KEYS
    }


def pilgrimage_rounds_from_rolls(rolls: Mapping[str, int]) -> dict[str, int]:
    """Map NW/NE/SE/SW d6 rolls to pilgrimage-site rounds."""
    normalized = _normalized_rolls(rolls)
    nw = normalized["nw"]
    absolute_positions = {
        "site_1": _PILGRIMAGE_OFFSETS["nw"] + normalized["nw"],
        "site_2": _PILGRIMAGE_OFFSETS["ne"] + normalized["ne"],
        "site_3": _PILGRIMAGE_OFFSETS["se"] + normalized["se"],
        "site_4": _PILGRIMAGE_OFFSETS["sw"] + normalized["sw"],
    }
    rounds = {
        site: 1 + (absolute_position - nw)
        for site, absolute_position in absolute_positions.items()
    }
    _validate_pilgrimage_rounds(rounds)
    return rounds


def build_abstract_setup_timeline(
    *,
    pilgrimage_rounds: Mapping[str, int],
    building_market: Sequence[str],
    building_levels: Mapping[str, int],
    total_rounds: int = TOTAL_BORDER_ROUNDS,
) -> tuple[SetupTimelineSlot, ...]:
    """Build abstract round slots from pilgrimage rounds and selected buildings."""
    if total_rounds <= 0:
        raise ValueError("total_rounds must be positive.")

    _validate_pilgrimage_rounds(pilgrimage_rounds)
    normalized_rounds = _normalized_pilgrimage_rounds(pilgrimage_rounds)
    if any(round_number > total_rounds for round_number in normalized_rounds.values()):
        raise ValueError(
            "total_rounds is smaller than one or more pilgrimage rounds."
        )
    site_round_to_site = {round_number: site for site, round_number in normalized_rounds.items()}
    timeline: dict[int, SetupTimelineSlot] = {
        round_number: SetupTimelineSlot(round_number=round_number, kind="empty")
        for round_number in range(1, total_rounds + 1)
    }

    for site, round_number in normalized_rounds.items():
        timeline[round_number] = SetupTimelineSlot(
            round_number=round_number,
            kind="pilgrimage_site",
            site=site,
        )

    for site, round_number in normalized_rounds.items():
        gap_round = round_number + 1
        if gap_round > total_rounds or gap_round in site_round_to_site:
            continue
        timeline[gap_round] = SetupTimelineSlot(
            round_number=gap_round,
            kind="empty_after_pilgrimage",
            site=site,
        )

    grouped = _group_market_buildings_by_level(
        building_market=building_market,
        building_levels=building_levels,
    )
    level_site_gate = {
        1: "site_1",
        2: "site_2",
        3: "site_3",
    }
    cursor = 1
    for level in (1, 2, 3):
        cursor = max(
            cursor,
            _first_round_after_site_gap(
                site_round=normalized_rounds[level_site_gate[level]],
                site_round_to_site=site_round_to_site,
                total_rounds=total_rounds,
            ),
        )
        for building_id in grouped[level]:
            cursor = _advance_to_placeable_building_round(
                cursor=cursor,
                timeline=timeline,
                total_rounds=total_rounds,
            )
            if cursor > total_rounds:
                raise ValueError("Unable to place all buildings inside the abstract timeline.")
            timeline[cursor] = SetupTimelineSlot(
                round_number=cursor,
                kind="building",
                building_id=building_id,
                building_level=level,
            )
            cursor += 1

        if level < 3 and grouped[level]:
            cursor = _reserve_post_level_gap(
                cursor=cursor,
                timeline=timeline,
                total_rounds=total_rounds,
            )

    return tuple(timeline[round_number] for round_number in range(1, total_rounds + 1))


def assign_building_live_rounds(
    *,
    timeline: Sequence[SetupTimelineSlot],
    building_market: Sequence[str],
) -> dict[str, int]:
    """Return building live rounds extracted from timeline building slots."""
    discovered: dict[str, int] = {}
    for slot in timeline:
        if slot.kind != "building":
            continue
        if slot.building_id is None:
            raise ValueError("Building slot missing building_id.")
        if slot.building_id in discovered:
            raise ValueError(f"Duplicate building placement in timeline: {slot.building_id}.")
        discovered[slot.building_id] = slot.round_number

    market_set = set(building_market)
    missing = [building_id for building_id in building_market if building_id not in discovered]
    extras = [building_id for building_id in discovered if building_id not in market_set]
    if missing:
        raise ValueError(f"Timeline missing placements for selected building(s): {missing}.")
    if extras:
        raise ValueError(f"Timeline contains unselected building(s): {extras}.")

    return {building_id: discovered[building_id] for building_id in building_market}


def grouped_live_rounds_by_level(
    *,
    building_market: Sequence[str],
    building_levels: Mapping[str, int],
    building_live_rounds: Mapping[str, int],
) -> dict[str, dict[str, int]]:
    """Group market live rounds by level while preserving market order."""
    grouped = {"level_1": {}, "level_2": {}, "level_3": {}}
    for building_id in building_market:
        if building_id not in building_live_rounds:
            raise ValueError(f"building_live_rounds missing selected building: {building_id}.")
        level = int(building_levels[building_id])
        if level not in (1, 2, 3):
            raise ValueError(f"Unsupported building level: {level}.")
        grouped[f"level_{level}"][building_id] = int(building_live_rounds[building_id])
    return grouped


def _normalized_rolls(rolls: Mapping[str, int]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    missing = [key for key in PILGRIMAGE_ROLL_KEYS if key not in rolls]
    if missing:
        raise ValueError(f"Missing pilgrimage roll key(s): {missing}.")

    for key in PILGRIMAGE_ROLL_KEYS:
        value = rolls[key]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Pilgrimage roll {key!r} must be an integer.")
        if value < PILGRIMAGE_ROLL_MIN or value > PILGRIMAGE_ROLL_MAX:
            raise ValueError(
                f"Pilgrimage roll {key!r} must be in "
                f"[{PILGRIMAGE_ROLL_MIN}, {PILGRIMAGE_ROLL_MAX}]."
            )
        normalized[key] = value
    return normalized


def _validate_pilgrimage_rounds(rounds: Mapping[str, int]) -> None:
    normalized = _normalized_pilgrimage_rounds(rounds)
    ordered_rounds = tuple(normalized[site] for site in PILGRIMAGE_SITE_ORDER)
    if tuple(sorted(ordered_rounds)) != ordered_rounds:
        raise ValueError("Pilgrimage rounds must be non-decreasing in site order.")
    if len(set(ordered_rounds)) != len(ordered_rounds):
        # Adjacent overlap is disallowed by the site-position math itself.
        raise ValueError("Pilgrimage rounds must be unique.")
    for round_number in ordered_rounds:
        if round_number < 1 or round_number > TOTAL_BORDER_ROUNDS:
            raise ValueError(
                f"Pilgrimage rounds must be within [1, {TOTAL_BORDER_ROUNDS}], "
                f"got {round_number}."
            )


def _normalized_pilgrimage_rounds(rounds: Mapping[str, int]) -> dict[str, int]:
    missing = [site for site in PILGRIMAGE_SITE_ORDER if site not in rounds]
    if missing:
        raise ValueError(f"Missing pilgrimage round key(s): {missing}.")
    normalized: dict[str, int] = {}
    for site in PILGRIMAGE_SITE_ORDER:
        value = rounds[site]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Pilgrimage round {site!r} must be an integer.")
        normalized[site] = value
    return normalized


def _group_market_buildings_by_level(
    *,
    building_market: Sequence[str],
    building_levels: Mapping[str, int],
) -> dict[int, tuple[str, ...]]:
    grouped: dict[int, list[str]] = {1: [], 2: [], 3: []}
    for building_id in building_market:
        if building_id not in building_levels:
            raise ValueError(f"Missing level metadata for selected building: {building_id}.")
        level = int(building_levels[building_id])
        if level not in grouped:
            raise ValueError(f"Unsupported building level for timeline placement: {level}.")
        grouped[level].append(building_id)
    return {level: tuple(values) for level, values in grouped.items()}


def _first_round_after_site_gap(
    *,
    site_round: int,
    site_round_to_site: Mapping[int, str],
    total_rounds: int,
) -> int:
    candidate = site_round + 1
    while candidate <= total_rounds and candidate in site_round_to_site:
        candidate += 1
    if candidate > total_rounds:
        return total_rounds + 1
    return candidate + 1


def _advance_to_placeable_building_round(
    *,
    cursor: int,
    timeline: Mapping[int, SetupTimelineSlot],
    total_rounds: int,
) -> int:
    while cursor <= total_rounds:
        slot = timeline[cursor]
        if slot.kind in _SLOT_BUILDING_BLOCKED_KINDS:
            cursor += 1
            continue
        if slot.kind == "building":
            raise ValueError("Timeline already contains a building at this round.")
        return cursor
    return cursor


def _reserve_post_level_gap(
    *,
    cursor: int,
    timeline: dict[int, SetupTimelineSlot],
    total_rounds: int,
) -> int:
    while cursor <= total_rounds and timeline[cursor].kind == "pilgrimage_site":
        cursor += 1
    if cursor > total_rounds:
        raise ValueError("Unable to reserve required post-level empty position.")

    slot = timeline[cursor]
    if slot.kind == "empty_after_pilgrimage":
        return cursor + 1
    if slot.kind == "empty":
        timeline[cursor] = SetupTimelineSlot(
            round_number=cursor,
            kind="empty_after_building_level",
        )
        return cursor + 1
    if slot.kind == "empty_after_building_level":
        return cursor + 1
    raise ValueError(f"Cannot reserve post-level gap on slot kind {slot.kind!r}.")


__all__ = [
    "PILGRIMAGE_ROLL_KEYS",
    "PILGRIMAGE_ROLL_MAX",
    "PILGRIMAGE_ROLL_MIN",
    "PILGRIMAGE_SITE_ORDER",
    "TOTAL_BORDER_ROUNDS",
    "SetupTimelineSlot",
    "SetupTimelineSlotKind",
    "assign_building_live_rounds",
    "build_abstract_setup_timeline",
    "generate_pilgrimage_rolls",
    "grouped_live_rounds_by_level",
    "pilgrimage_rounds_from_rolls",
]
