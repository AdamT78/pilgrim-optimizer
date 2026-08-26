"""Shared deterministic metrics for committed turn-step branching audits."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.actions import (
    BuildingConversionStep,
    BuildingRelocationStep,
    TurnStep,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.state import GameState
from pilgrim.rules.transition import apply_turn_step, turn_step_id, turn_steps

_STEP_SEQUENCE_WALK_CAP = 10_000
_DROPPED_SEQUENCE_PREFIX_LIMIT = 8


@dataclass(frozen=True, slots=True)
class TurnStepMetrics:
    """Counts the offered steps and their reachable optional-commit prefixes.

    A sequence includes the empty prefix: a player may stop committing buildings and choose a
    full-turn action immediately. The reported action-step product is consequently meaningful
    even when no building step is available.
    """

    total_turn_steps: int
    hired_turn_steps: int
    conversion_turn_steps: int
    grain_store_conversion_turn_steps: int
    relocation_turn_steps: int
    reachable_step_sequences: int
    action_step_sequence_product: int
    sequence_walk_truncated: bool
    dropped_step_sequence_prefixes: tuple[tuple[str, ...], ...]
    additional_dropped_step_sequence_prefix_count: int


def step_is_hired(step: TurnStep) -> bool:
    return step.source != "own_active"


def step_is_conversion(step: TurnStep) -> bool:
    return isinstance(step, BuildingConversionStep)


def step_is_grain_store_conversion(step: TurnStep) -> bool:
    return step_is_conversion(step) and step.building_id == "grain_store"


def step_is_relocation(step: TurnStep) -> bool:
    return isinstance(step, BuildingRelocationStep)


def collect_turn_step_metrics(
    state: GameState,
    config: GameConfig,
    *,
    legal_action_count: int,
    sequence_cap: int = _STEP_SEQUENCE_WALK_CAP,
) -> TurnStepMetrics:
    """Return bounded committed-step branching metrics for one engine position.

    The walk counts every reachable sequence prefix once. It intentionally has no state
    canonicalization: distinct commit orders are player choices and therefore distinct search
    branches even if a future engine optimization might merge their outcomes. At the cap, the
    report retains the first few omitted sequence prefixes in stable step-ID order and counts any
    additional omitted prefixes rather than presenting the bounded count as complete.
    """
    if sequence_cap < 1:
        raise ValueError("sequence_cap must be at least 1.")

    offered_steps = tuple(turn_steps(state, config))
    sequence_count = 0
    truncated = False
    dropped_prefixes: list[tuple[str, ...]] = []
    additional_dropped_prefix_count = 0

    def walk(current_state: GameState, prefix: tuple[str, ...]) -> None:
        nonlocal additional_dropped_prefix_count, sequence_count, truncated
        if sequence_count >= sequence_cap:
            truncated = True
            if len(dropped_prefixes) < _DROPPED_SEQUENCE_PREFIX_LIMIT:
                dropped_prefixes.append(prefix)
            else:
                additional_dropped_prefix_count += 1
            return

        # Every prefix is a choice point because the player may stop committing steps here.
        sequence_count += 1
        for step in sorted(turn_steps(current_state, config), key=turn_step_id):
            walk(
                apply_turn_step(current_state, config, step),
                (*prefix, turn_step_id(step)),
            )

    walk(state, ())
    return TurnStepMetrics(
        total_turn_steps=len(offered_steps),
        hired_turn_steps=sum(step_is_hired(step) for step in offered_steps),
        conversion_turn_steps=sum(step_is_conversion(step) for step in offered_steps),
        grain_store_conversion_turn_steps=sum(
            step_is_grain_store_conversion(step) for step in offered_steps
        ),
        relocation_turn_steps=sum(step_is_relocation(step) for step in offered_steps),
        reachable_step_sequences=sequence_count,
        action_step_sequence_product=legal_action_count * sequence_count,
        sequence_walk_truncated=truncated,
        dropped_step_sequence_prefixes=tuple(dropped_prefixes),
        additional_dropped_step_sequence_prefix_count=additional_dropped_prefix_count,
    )
