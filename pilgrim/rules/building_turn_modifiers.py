"""Metadata-only registry for deferred building turn/movement modifiers.

This module is intentionally declarative. Existing transition logic remains the source of truth
for runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BuildingTurnModifierCategory = Literal[
    "sow_route_modifier",
    "start_turn_relocation",
    "end_turn_relocation",
]
BuildingTurnModifierPhase = Literal["during_sow", "start_of_turn", "end_of_turn"]
BuildingTurnModifierStatus = Literal["scaffolded", "implemented", "deferred_spatial"]


@dataclass(frozen=True, slots=True)
class BuildingTurnModifier:
    """One building turn/movement-layer modifier mapping."""

    building_key: str
    category: BuildingTurnModifierCategory
    phase: BuildingTurnModifierPhase
    effect: str
    status: BuildingTurnModifierStatus
    notes: str = ""


_BUILDING_TURN_MODIFIERS: tuple[BuildingTurnModifier, ...] = (
    BuildingTurnModifier(
        building_key="kogge",
        category="sow_route_modifier",
        phase="during_sow",
        effect="adds city -> east and city -> west sow options",
        status="implemented",
        notes="implemented in transition sow-route generation and apply validation/events.",
    ),
    BuildingTurnModifier(
        building_key="cloisters",
        category="sow_route_modifier",
        phase="during_sow",
        effect="may skip one Duty tile or the city when moving acolytes to Duty actions",
        status="scaffolded",
        notes="skip-route logic deferred",
    ),
    BuildingTurnModifier(
        building_key="dormitory",
        category="start_turn_relocation",
        phase="start_of_turn",
        effect="may return 1 acolyte from any Duty action to City",
        status="implemented",
        notes="implemented as optional pre-sow start-turn relocation action prefix.",
    ),
    BuildingTurnModifier(
        building_key="inquisition",
        category="start_turn_relocation",
        phase="start_of_turn",
        effect="may move 1 acolyte from City to any Duty",
        status="implemented",
        notes="implemented as optional pre-sow start-turn relocation action prefix.",
    ),
    BuildingTurnModifier(
        building_key="library",
        category="end_turn_relocation",
        phase="end_of_turn",
        effect="may move 1 acolyte from City directly to a Duty action or back to Abbey",
        status="scaffolded",
        notes="optional post-turn action composition deferred",
    ),
)


def all_building_turn_modifiers() -> tuple[BuildingTurnModifier, ...]:
    """Return the full immutable turn-modifier registry."""
    return _BUILDING_TURN_MODIFIERS


def turn_modifiers_for_building(building_key: str) -> tuple[BuildingTurnModifier, ...]:
    """Return modifiers registered for one building key."""
    normalized = _normalize_building_key(building_key)
    return tuple(
        entry for entry in _BUILDING_TURN_MODIFIERS if entry.building_key == normalized
    )


def turn_modifiers_for_phase(phase: str) -> tuple[BuildingTurnModifier, ...]:
    """Return modifiers affecting one turn phase."""
    normalized = phase.strip().lower()
    return tuple(entry for entry in _BUILDING_TURN_MODIFIERS if entry.phase == normalized)


def turn_modifiers_for_category(category: str) -> tuple[BuildingTurnModifier, ...]:
    """Return modifiers affecting one movement/turn category."""
    normalized = category.strip().lower()
    return tuple(entry for entry in _BUILDING_TURN_MODIFIERS if entry.category == normalized)


def scaffolded_turn_modifiers() -> tuple[BuildingTurnModifier, ...]:
    """Return turn modifiers with scaffold-only status."""
    return tuple(entry for entry in _BUILDING_TURN_MODIFIERS if entry.status == "scaffolded")


def implemented_turn_modifiers() -> tuple[BuildingTurnModifier, ...]:
    """Return turn modifiers with implemented runtime behavior."""
    return tuple(entry for entry in _BUILDING_TURN_MODIFIERS if entry.status == "implemented")


def _normalize_building_key(building_key: str) -> str:
    normalized = (
        building_key.strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )
    normalized = "_".join(normalized.split())
    if not normalized:
        raise ValueError("building_key cannot be empty.")
    return normalized


def _validate_unique_entries() -> None:
    keys = [
        (
            entry.building_key,
            entry.category,
            entry.phase,
            entry.effect,
            entry.status,
            entry.notes,
        )
        for entry in _BUILDING_TURN_MODIFIERS
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("Building turn modifier registry contains duplicate entries.")


_validate_unique_entries()


__all__ = [
    "BuildingTurnModifier",
    "BuildingTurnModifierCategory",
    "BuildingTurnModifierPhase",
    "BuildingTurnModifierStatus",
    "all_building_turn_modifiers",
    "turn_modifiers_for_building",
    "turn_modifiers_for_phase",
    "turn_modifiers_for_category",
    "scaffolded_turn_modifiers",
    "implemented_turn_modifiers",
]
