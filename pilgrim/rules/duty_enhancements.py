"""Metadata-only registry for known Duty enhancements.

This module is intentionally declarative. Existing duty-specific rules hooks and transition
logic remain the source of truth for gameplay behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DutyEnhancementSourceType = Literal["special_activity", "building"]
DutyEnhancementStatus = Literal[
    "implemented",
    "implemented_scaffolded",
    "known_unimplemented",
    "deferred_spatial",
]


@dataclass(frozen=True, slots=True)
class DutyEnhancement:
    """One source->duty-action enhancement mapping."""

    duty: str
    action_key: str
    source_type: DutyEnhancementSourceType
    source_key: str
    effect: str
    status: DutyEnhancementStatus
    notes: str


_DUTY_ENHANCEMENTS: tuple[DutyEnhancement, ...] = (
    # Special Activities
    DutyEnhancement(
        duty="produce",
        action_key="produce_wheat",
        source_type="special_activity",
        source_key="fields",
        effect="+1 wheat",
        status="implemented",
        notes="Applied by produce_wheat_fields_bonus() hook.",
    ),
    DutyEnhancement(
        duty="produce",
        action_key="produce_stone",
        source_type="special_activity",
        source_key="stone_mason",
        effect="+1 stone",
        status="implemented",
        notes="Applied by produce_stone_mason_bonus() hook.",
    ),
    DutyEnhancement(
        duty="clerical",
        action_key="clerical_devotion",
        source_type="special_activity",
        source_key="vestry",
        effect="+1 piety",
        status="implemented",
        notes="Applied by clerical_devotion_bonus() hook.",
    ),
    DutyEnhancement(
        duty="clerical",
        action_key="clerical_silversmith",
        source_type="special_activity",
        source_key="engraver",
        effect="+1 silver",
        status="implemented",
        notes="Applied by clerical_silversmith_bonus() hook.",
    ),
    DutyEnhancement(
        duty="give_alms",
        action_key="give_alms",
        source_type="special_activity",
        source_key="alms_house",
        effect="optional +1 effective Duty Value with extra payment",
        status="implemented",
        notes="Bonus requires paying exactly 1 extra silver or wheat.",
    ),
    DutyEnhancement(
        duty="build_roads",
        action_key="build_roads_deferred",
        source_type="special_activity",
        source_key="road_engineer",
        effect="+1 effective Duty Value",
        status="implemented_scaffolded",
        notes="Current Build Roads runtime is deferred/scaffolded.",
    ),
    DutyEnhancement(
        duty="construct",
        action_key="construct_deferred",
        source_type="special_activity",
        source_key="road_engineer",
        effect="extra deferred road only if road already included",
        status="implemented_scaffolded",
        notes="Construct does not use generic duty-value +1 from Road Engineer.",
    ),
    # Buildings
    DutyEnhancement(
        duty="allocation",
        action_key="allocation",
        source_type="building",
        source_key="infirmary",
        effect="+1 effective Duty Value",
        status="implemented",
        notes="Applied in transition when Infirmary is active.",
    ),
    DutyEnhancement(
        duty="allocation",
        action_key="all_special_activity_spaces",
        source_type="building",
        source_key="chapter_house",
        effect="allows a second acolyte on each Special Activity via Allocation; bonuses scale by acolyte count, max 2",
        status="implemented",
        notes="Active Chapter House increases per-space Special Activity capacity from 1 to 2.",
    ),
    DutyEnhancement(
        duty="clerical",
        action_key="clerical_silversmith",
        source_type="building",
        source_key="mint",
        effect="+1 silver",
        status="implemented",
        notes="Applied in transition when Mint is active.",
    ),
    DutyEnhancement(
        duty="clerical",
        action_key="clerical_devotion",
        source_type="building",
        source_key="chapel",
        effect="+1 piety",
        status="implemented",
        notes="Applied in transition when Chapel is active.",
    ),
    DutyEnhancement(
        duty="give_alms",
        action_key="give_alms",
        source_type="building",
        source_key="mill",
        effect="deferred",
        status="known_unimplemented",
        notes="Give Alms building interaction is not implemented yet.",
    ),
    DutyEnhancement(
        duty="ordination",
        action_key="ordination",
        source_type="building",
        source_key="mill",
        effect="deferred",
        status="known_unimplemented",
        notes="Ordination building interaction is not implemented yet.",
    ),
    DutyEnhancement(
        duty="ordination",
        action_key="ordination",
        source_type="building",
        source_key="infirmary",
        effect="+1 effective Duty Value if wheat cost is paid",
        status="implemented",
        notes="Applied when active Infirmary is used for an extra paid ordination step.",
    ),
    DutyEnhancement(
        duty="produce",
        action_key="produce_wheat",
        source_type="building",
        source_key="well",
        effect="+1 wheat",
        status="implemented",
        notes="Applied in transition when Well is active.",
    ),
    DutyEnhancement(
        duty="produce",
        action_key="produce_stone",
        source_type="building",
        source_key="quarry",
        effect="+1 stone",
        status="implemented",
        notes="Applied in transition when Quarry is active.",
    ),
)

_IMPLEMENTED_STATUSES: frozenset[DutyEnhancementStatus] = frozenset(
    {"implemented", "implemented_scaffolded"}
)


def all_duty_enhancements() -> tuple[DutyEnhancement, ...]:
    """Return the full immutable registry in deterministic order."""
    return _DUTY_ENHANCEMENTS


def enhancements_for_duty(duty: str) -> tuple[DutyEnhancement, ...]:
    """Return enhancements that affect one duty category."""
    return tuple(entry for entry in _DUTY_ENHANCEMENTS if entry.duty == duty)


def enhancements_for_action(action_key: str) -> tuple[DutyEnhancement, ...]:
    """Return enhancements that affect one action key."""
    return tuple(entry for entry in _DUTY_ENHANCEMENTS if entry.action_key == action_key)


def enhancements_by_source(source_key: str) -> tuple[DutyEnhancement, ...]:
    """Return enhancements contributed by one source (special activity or building)."""
    return tuple(entry for entry in _DUTY_ENHANCEMENTS if entry.source_key == source_key)


def implemented_enhancements() -> tuple[DutyEnhancement, ...]:
    """Return entries whose behavior exists in current runtime (or scaffold runtime)."""
    return tuple(entry for entry in _DUTY_ENHANCEMENTS if entry.status in _IMPLEMENTED_STATUSES)


def unimplemented_enhancements() -> tuple[DutyEnhancement, ...]:
    """Return entries documented but not implemented in gameplay transitions."""
    return tuple(entry for entry in _DUTY_ENHANCEMENTS if entry.status not in _IMPLEMENTED_STATUSES)


def _validate_unique_entries() -> None:
    keys = [
        (
            entry.duty,
            entry.action_key,
            entry.source_type,
            entry.source_key,
            entry.effect,
            entry.status,
            entry.notes,
        )
        for entry in _DUTY_ENHANCEMENTS
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Duty enhancement registry contains duplicate entries.")


_validate_unique_entries()


__all__ = [
    "DutyEnhancement",
    "DutyEnhancementSourceType",
    "DutyEnhancementStatus",
    "all_duty_enhancements",
    "enhancements_for_duty",
    "enhancements_for_action",
    "enhancements_by_source",
    "implemented_enhancements",
    "unimplemented_enhancements",
]
