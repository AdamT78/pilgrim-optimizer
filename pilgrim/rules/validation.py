"""Validation helpers and transition invariants."""

from __future__ import annotations

from pilgrim.model.enums import PlayerId, TurnPhase
from pilgrim.model.state import GameState
from pilgrim.model.workforce import MANCALA_POSITION_COUNT


class TransitionValidationError(ValueError):
    """Raised when an action violates deterministic rules or invariants."""


def ensure_phase(state: GameState, *, expected: TurnPhase, action_name: str) -> None:
    if state.phase is not expected:
        message = (
            f"{action_name} is only legal during phase={expected.value}, "
            f"got phase={state.phase.value}."
        )
        raise TransitionValidationError(message)


def ensure_selected_duty_has_acolyte(
    state: GameState,
    *,
    player: PlayerId,
    duty_position: int,
) -> None:
    if duty_position == 0:
        raise TransitionValidationError("City is not a duty position.")
    if state.player_vector(player)[duty_position] <= 0:
        raise TransitionValidationError(
            "Selected duty must contain at least one active-player acolyte."
        )


def ensure_route_length_matches(*, picked_up: int, route_length: int) -> None:
    if route_length != picked_up:
        raise TransitionValidationError(
            f"Route length ({route_length}) must match picked-up acolytes ({picked_up})."
        )


def ensure_affordable_minority(*, available_silver: int, silver_cost: int) -> None:
    if silver_cost > available_silver:
        raise TransitionValidationError(
            f"Minority action requires {silver_cost} silver, available {available_silver}."
        )


def ensure_non_negative_resources(state: GameState) -> None:
    for player in state.players:
        if player.resources.stone < 0 or player.resources.silver < 0 or player.resources.wheat < 0:
            raise TransitionValidationError("Resources cannot be negative.")
        if player.piety < 0 or player.alms_position < 0 or player.victory_points < 0:
            raise TransitionValidationError(
                "Piety, Alms position, and victory points cannot be negative."
            )


def ensure_valid_workforce(state: GameState) -> None:
    for player_id in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        workforce = state.player_state(player_id).workforce
        if len(workforce.mancala) != MANCALA_POSITION_COUNT:
            raise TransitionValidationError(
                f"{player_id.name} mancala workforce must contain "
                f"{MANCALA_POSITION_COUNT} positions."
            )
        if any(count < 0 for count in workforce.mancala):
            raise TransitionValidationError(
                f"{player_id.name} mancala workforce cannot contain negative counts."
            )
        if workforce.village < 0:
            raise TransitionValidationError(
                f"{player_id.name} village workforce cannot be negative."
            )
        if workforce.abbey < 0:
            raise TransitionValidationError(
                f"{player_id.name} abbey workforce cannot be negative."
            )
        committed = workforce.committed
        if committed.roads < 0:
            raise TransitionValidationError(
                f"{player_id.name} committed roads workforce cannot be negative."
            )
        if committed.shrines < 0:
            raise TransitionValidationError(
                f"{player_id.name} committed shrines workforce cannot be negative."
            )
        if committed.market_ports < 0:
            raise TransitionValidationError(
                f"{player_id.name} committed market ports workforce cannot be negative."
            )
        if committed.pilgrimage_sites < 0:
            raise TransitionValidationError(
                f"{player_id.name} committed pilgrimage sites workforce cannot be negative."
            )
        if committed.alms_table < 0:
            raise TransitionValidationError(
                f"{player_id.name} committed alms table workforce cannot be negative."
            )


def ensure_acolyte_conservation(before: GameState, after: GameState) -> None:
    for player_id in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        if before.total_acolytes(player_id) != after.total_acolytes(player_id):
            raise TransitionValidationError(
                f"Acolyte count changed for {player_id.name}: "
                f"{before.total_acolytes(player_id)} -> {after.total_acolytes(player_id)}."
            )


def validate_state_invariants(state: GameState) -> None:
    """Basic state-level checks used by CLI validation."""
    ensure_non_negative_resources(state)
    ensure_valid_workforce(state)
