"""Duty strength and placeholder duty-effect resolution."""

from __future__ import annotations

from collections.abc import Mapping

from pilgrim.model.config import PietyConfig
from pilgrim.model.duties import DUTY_CATEGORIES
from pilgrim.model.enums import DutyEffect, DutyStrength, TurnResolutionType
from pilgrim.model.state import PlayerState
from pilgrim.rules.piety import move_piety

_DUTY_CATEGORY_ACTIONS: Mapping[str, tuple[TurnResolutionType, ...]] = {
    "produce": (
        TurnResolutionType.PRODUCE_WHEAT,
        TurnResolutionType.PRODUCE_STONE,
    ),
    "clerical": (
        TurnResolutionType.CLERICAL_DEVOTION,
        TurnResolutionType.CLERICAL_SILVERSMITH,
    ),
    "give_alms": (
        TurnResolutionType.GIVE_ALMS,
        TurnResolutionType.DONATE_BUILDING,
    ),
    "allocation": (TurnResolutionType.ALLOCATION,),
    "build_roads": (),
    "construct": (),
    "ordination": (),
    "taxation": (),
}

_RESOLUTION_EFFECTS: Mapping[TurnResolutionType, DutyEffect] = {
    TurnResolutionType.CLERICAL_DEVOTION: DutyEffect.CLERICAL_DEVOTION,
    TurnResolutionType.CLERICAL_SILVERSMITH: DutyEffect.CLERICAL_SILVERSMITH,
}


def duty_strength(player_count: int, opponent_counts: tuple[int, ...]) -> DutyStrength:
    """Compute relative control of a duty against all opponents."""
    highest_opponent = max(opponent_counts, default=0)
    if player_count > highest_opponent:
        return DutyStrength.MAJORITY
    if player_count == highest_opponent:
        return DutyStrength.PARITY
    return DutyStrength.MINORITY


def duty_value_and_silver_cost(strength: DutyStrength) -> tuple[int, int]:
    """Return (duty_value, minority_silver_cost)."""
    if strength is DutyStrength.MAJORITY:
        return 2, 0
    if strength is DutyStrength.PARITY:
        return 1, 0
    return 1, 1


def action_options_for_duty_category(duty_category: str) -> tuple[TurnResolutionType, ...]:
    """Return currently available action options for one duty category."""
    if duty_category not in _DUTY_CATEGORY_ACTIONS:
        allowed = ", ".join(DUTY_CATEGORIES)
        raise ValueError(f"Unknown duty category '{duty_category}'. Allowed: {allowed}.")
    return _DUTY_CATEGORY_ACTIONS[duty_category]


def is_deferred_duty_category(duty_category: str) -> bool:
    """Return True when a duty category is valid but intentionally deferred."""
    return len(action_options_for_duty_category(duty_category)) == 0


def effect_for_resolution(resolution: TurnResolutionType) -> DutyEffect:
    """Map concrete duty action resolution to effect implementation helper."""
    try:
        return _RESOLUTION_EFFECTS[resolution]
    except KeyError as exc:
        raise ValueError(
            f"Resolution does not map to direct duty effect: {resolution.value}"
        ) from exc


def apply_produce_resolution(
    player_state: PlayerState,
    *,
    resolution: TurnResolutionType,
    duty_value: int,
    silver_cost: int,
) -> tuple[PlayerState, tuple[int, int, int]]:
    """Apply produce_wheat or produce_stone resolution with minority silver cost."""
    if resolution is TurnResolutionType.PRODUCE_WHEAT:
        stone_delta = 0
        wheat_delta = duty_value
    elif resolution is TurnResolutionType.PRODUCE_STONE:
        stone_delta = duty_value
        wheat_delta = 0
    else:
        raise ValueError(f"Unsupported produce resolution: {resolution.value}")

    silver_delta = -silver_cost
    new_resources = player_state.resources.add(
        stone=stone_delta,
        silver=silver_delta,
        wheat=wheat_delta,
    )
    new_player_state = PlayerState(
        resources=new_resources,
        workforce=player_state.workforce,
        piety=player_state.piety,
        alms_position=player_state.alms_position,
        victory_points=player_state.victory_points,
        special_activities=player_state.special_activities,
        player_board_slots=player_state.player_board_slots,
    )
    return new_player_state, (stone_delta, silver_delta, wheat_delta)


def apply_duty_effect(
    player_state: PlayerState,
    *,
    effect: DutyEffect,
    duty_value: int,
    silver_cost: int,
    piety_config: PietyConfig,
) -> tuple[PlayerState, tuple[int, int, int], int, int]:
    """
    Apply a placeholder duty effect.

    Returns:
        (
            new_player_state,
            (stone_delta, silver_delta, wheat_delta),
            old_piety_position,
            new_piety_position,
        )
    """
    stone_delta = 0
    silver_delta = -silver_cost
    wheat_delta = 0
    old_piety_position = player_state.piety
    new_piety_position = old_piety_position

    if effect is DutyEffect.PRODUCE:
        wheat_delta = duty_value
    elif effect is DutyEffect.CLERICAL_DEVOTION:
        new_piety_position = move_piety(old_piety_position, duty_value, piety_config)
    elif effect is DutyEffect.CLERICAL_SILVERSMITH:
        silver_delta += duty_value

    new_resources = player_state.resources.add(
        stone=stone_delta,
        silver=silver_delta,
        wheat=wheat_delta,
    )
    new_player_state = PlayerState(
        resources=new_resources,
        workforce=player_state.workforce,
        piety=new_piety_position,
        alms_position=player_state.alms_position,
        victory_points=player_state.victory_points,
        special_activities=player_state.special_activities,
        player_board_slots=player_state.player_board_slots,
    )
    return (
        new_player_state,
        (stone_delta, silver_delta, wheat_delta),
        old_piety_position,
        new_piety_position,
    )
