"""Validation helpers and transition invariants."""

from __future__ import annotations

from pilgrim.model.dummy import validate_dummy_acolytes
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


def ensure_dummy_acolyte_conservation(before: GameState, after: GameState) -> None:
    if before.dummy_acolytes.north_total != after.dummy_acolytes.north_total:
        raise TransitionValidationError(
            "Dummy north_group total changed across transition: "
            f"{before.dummy_acolytes.north_total} -> {after.dummy_acolytes.north_total}."
        )
    if before.dummy_acolytes.south_total != after.dummy_acolytes.south_total:
        raise TransitionValidationError(
            "Dummy south_group total changed across transition: "
            f"{before.dummy_acolytes.south_total} -> {after.dummy_acolytes.south_total}."
        )


def ensure_valid_timing(state: GameState) -> None:
    timing = state.timing
    if timing.absolute_turn < 0:
        raise TransitionValidationError("Timing absolute_turn cannot be negative.")
    if timing.round_number < 1:
        raise TransitionValidationError("Timing round_number must be at least 1.")
    if timing.season_number < 1:
        raise TransitionValidationError("Timing season_number must be at least 1.")
    if timing.turn_in_round < 0:
        raise TransitionValidationError("Timing turn_in_round cannot be negative.")
    if timing.turn_in_round >= state.player_count:
        raise TransitionValidationError(
            f"Timing turn_in_round must be less than player count ({state.player_count})."
        )


def ensure_valid_merchant_state(state: GameState) -> None:
    if state.merchant_position < 0:
        raise TransitionValidationError("Merchant position cannot be negative.")


def ensure_valid_round_end_state(state: GameState) -> None:
    if state.ship_position < 0:
        raise TransitionValidationError("Ship position cannot be negative.")
    if state.completed_rounds < 0:
        raise TransitionValidationError("completed_rounds cannot be negative.")
    if int(state.start_player) >= state.player_count:
        raise TransitionValidationError("start_player must be a valid real player.")
    if int(state.active_player) >= state.player_count:
        raise TransitionValidationError("active_player must be a valid real player.")
    if not isinstance(state.game_over, bool):
        raise TransitionValidationError("game_over must be boolean.")


def ensure_valid_dummy_state(state: GameState) -> None:
    try:
        validate_dummy_acolytes(
            state.dummy_acolytes,
            player_count=state.table_player_count,
        )
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc


def ensure_valid_player_board_slots_structure(state: GameState) -> None:
    for player_id in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        slots = state.player_state(player_id).player_board_slots
        if slots.cardinal_favor_tiles < 0:
            raise TransitionValidationError(
                f"{player_id.name} cardinal_favor_tiles cannot be negative."
            )
        if len(set(slots.active_buildings)) != len(slots.active_buildings):
            raise TransitionValidationError(
                f"{player_id.name} active_buildings cannot contain duplicates."
            )
        if len(set(slots.donated_buildings)) != len(slots.donated_buildings):
            raise TransitionValidationError(
                f"{player_id.name} donated_buildings cannot contain duplicates."
            )
        overlap = set(slots.active_buildings).intersection(slots.donated_buildings)
        if overlap:
            raise TransitionValidationError(
                f"{player_id.name} building cannot be both active and donated: "
                f"{sorted(overlap)}."
            )


def validate_state_invariants(state: GameState) -> None:
    """Basic state-level checks used by CLI validation."""
    ensure_non_negative_resources(state)
    ensure_valid_workforce(state)
    ensure_valid_timing(state)
    ensure_valid_merchant_state(state)
    ensure_valid_round_end_state(state)
    ensure_valid_dummy_state(state)
    ensure_valid_player_board_slots_structure(state)
