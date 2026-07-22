"""Sandbox evaluation helpers with score breakdown."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.piety import score_piety


@dataclass(frozen=True, slots=True)
class EvaluationBreakdown:
    """Temporary objective breakdown for explainable search output."""

    victory_points: int
    piety_position: int
    piety_track_vp: int
    stone: int
    silver: int
    wheat: int
    resource_total: int
    total: int


def evaluate_player_state(player_state: PlayerState, config: GameConfig) -> EvaluationBreakdown:
    """Evaluate one player's state under current sandbox approximation."""
    piety_position = player_state.piety
    piety_track_vp = score_piety(piety_position, config.piety)
    stone = player_state.resources.stone
    silver = player_state.resources.silver
    wheat = player_state.resources.wheat
    resource_total = stone + silver + wheat
    total = player_state.victory_points + piety_track_vp + resource_total
    return EvaluationBreakdown(
        victory_points=player_state.victory_points,
        piety_position=piety_position,
        piety_track_vp=piety_track_vp,
        stone=stone,
        silver=silver,
        wheat=wheat,
        resource_total=resource_total,
        total=total,
    )


def evaluate_state(
    state: GameState,
    perspective: PlayerId,
    config: GameConfig,
) -> EvaluationBreakdown:
    """Evaluate state from one player's perspective."""
    return evaluate_player_state(state.player_state(perspective), config)
