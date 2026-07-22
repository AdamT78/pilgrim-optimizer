"""Duty strength and placeholder duty-effect resolution."""

from __future__ import annotations

from pilgrim.model.config import PietyConfig
from pilgrim.model.enums import DutyEffect, DutyStrength
from pilgrim.model.state import PlayerState
from pilgrim.rules.piety import move_piety


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
        victory_points=player_state.victory_points,
    )
    return (
        new_player_state,
        (stone_delta, silver_delta, wheat_delta),
        old_piety_position,
        new_piety_position,
    )
