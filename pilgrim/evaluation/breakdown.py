"""Canonical sandbox evaluation model and helpers."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.alms import score_alms_table
from pilgrim.rules.piety import score_piety

SANDBOX_EVALUATION_FORMULA = (
    "victory_points + piety_track_vp + alms_table_vp + resource_total"
)


@dataclass(frozen=True, slots=True)
class EvaluationBreakdown:
    """Explicit sandbox-only score decomposition for one player."""

    player_id: int
    player_name: str | None
    victory_points: int
    piety_position: int
    piety_track_vp: int
    alms_position: int
    alms_table_acolytes: int
    alms_table_vp: int
    stone: int
    silver: int
    wheat: int
    resource_total: int
    total: int


def evaluate_player_state(
    player_state: PlayerState,
    config: GameConfig,
    *,
    player_id: int = -1,
    player_name: str | None = None,
) -> EvaluationBreakdown:
    """Evaluate one player's state under current sandbox approximation."""
    piety_position = player_state.piety
    piety_track_vp = score_piety(piety_position, config.piety)
    alms_position = player_state.alms_position
    alms_table_acolytes = player_state.workforce.committed.alms_table
    alms_table_vp = score_alms_table(alms_table_acolytes, config.alms)
    stone = player_state.resources.stone
    silver = player_state.resources.silver
    wheat = player_state.resources.wheat
    resource_total = stone + silver + wheat
    total = player_state.victory_points + piety_track_vp + alms_table_vp + resource_total

    return EvaluationBreakdown(
        player_id=player_id,
        player_name=player_name,
        victory_points=player_state.victory_points,
        piety_position=piety_position,
        piety_track_vp=piety_track_vp,
        alms_position=alms_position,
        alms_table_acolytes=alms_table_acolytes,
        alms_table_vp=alms_table_vp,
        stone=stone,
        silver=silver,
        wheat=wheat,
        resource_total=resource_total,
        total=total,
    )


def evaluate_player(
    state: GameState,
    player_id: PlayerId | int,
    config: GameConfig,
) -> EvaluationBreakdown:
    """Evaluate a state from one player's perspective."""
    normalized_player = PlayerId(int(player_id))
    return evaluate_player_state(
        state.player_state(normalized_player),
        config,
        player_id=int(normalized_player),
        player_name=normalized_player.name.lower(),
    )


def evaluate_root_player(
    state: GameState,
    *,
    root_player_id: PlayerId | int,
    config: GameConfig,
) -> EvaluationBreakdown:
    """Evaluate a state from the configured root-player perspective."""
    return evaluate_player(state, root_player_id, config)


def evaluate_state(
    state: GameState,
    perspective: PlayerId | int,
    config: GameConfig,
) -> EvaluationBreakdown:
    """Backward-compatible alias for evaluating one perspective."""
    return evaluate_player(state, perspective, config)


def format_evaluation_breakdown_lines(breakdown: EvaluationBreakdown) -> tuple[str, ...]:
    """Return stable CLI-friendly formatting lines for a breakdown."""
    player_line = (
        f"Player: {breakdown.player_name}"
        if breakdown.player_name is not None
        else f"Player ID: {breakdown.player_id}"
    )
    return (
        player_line,
        f"Victory points: {breakdown.victory_points}",
        f"Piety position: {breakdown.piety_position}",
        f"Piety track VP: {breakdown.piety_track_vp}",
        f"Alms position: {breakdown.alms_position}",
        f"Alms table acolytes: {breakdown.alms_table_acolytes}",
        f"Alms table VP: {breakdown.alms_table_vp}",
        (
            "Resources: "
            f"stone={breakdown.stone}, "
            f"silver={breakdown.silver}, "
            f"wheat={breakdown.wheat}"
        ),
        f"Resource total: {breakdown.resource_total}",
        f"Total sandbox evaluation: {breakdown.total}",
    )


def format_evaluation_breakdown(breakdown: EvaluationBreakdown) -> str:
    """Return a printable multi-line evaluation summary."""
    return "\n".join(format_evaluation_breakdown_lines(breakdown))
