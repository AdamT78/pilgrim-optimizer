"""Round/season timing helpers for post-turn progression."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pilgrim.model.config import TimingConfig
from pilgrim.model.enums import EventType, PlayerId, TurnPhase
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.state import GameState
from pilgrim.model.timing import TimingState


@dataclass(frozen=True, slots=True)
class TimingAdvanceResult:
    """Result of advancing timing after one full player turn."""

    state: GameState
    events: tuple[GameEvent, ...]
    round_ended: bool
    season_ended: bool
    completed_round_number: int | None
    completed_season_number: int | None


def advance_active_player(state: GameState, config: TimingConfig) -> PlayerId:
    """Advance to the next player in deterministic player order."""
    _ensure_timing_config_compatible(state, config)
    next_index = (int(state.active_player) + 1) % state.player_count
    return PlayerId(next_index)


def is_round_end(timing: TimingState, config: TimingConfig) -> bool:
    """Return true when the current turn will complete the round."""
    return timing.turn_in_round + 1 >= config.players_per_round


def is_season_end(timing: TimingState, config: TimingConfig) -> bool:
    """Return true when the current turn will complete the season."""
    if not is_round_end(timing, config):
        return False
    return timing.round_number % config.rounds_per_season == 0


def resolve_round_end(state: GameState, config: TimingConfig) -> GameState:
    """Advance to the next round and reset turn index within round."""
    _ensure_timing_config_compatible(state, config)
    return replace(
        state,
        timing=replace(
            state.timing,
            round_number=state.timing.round_number + 1,
            turn_in_round=0,
        ),
    )


def resolve_season_end(state: GameState, config: TimingConfig) -> GameState:
    """Advance to the next season after season-end effects resolve."""
    _ensure_timing_config_compatible(state, config)
    return replace(
        state,
        timing=replace(state.timing, season_number=state.timing.season_number + 1),
    )


def advance_timing(
    state: GameState,
    config: TimingConfig,
    *,
    action_id: str,
) -> TimingAdvanceResult:
    """
    Advance active player and timing after one full player turn.

    Event order emitted here:
    - TURN_ADVANCE (always)
    - ROUND_END / ROUND_ADVANCE (when round closes)
    - SEASON_END (when season boundary reached)
    """
    _ensure_timing_config_compatible(state, config)
    actor = state.active_player
    next_player = advance_active_player(state, config)
    round_ended = is_round_end(state.timing, config)
    season_ended = is_season_end(state.timing, config)
    completed_round_number: int | None = None
    completed_season_number: int | None = None

    base_timing = replace(
        state.timing,
        absolute_turn=state.timing.absolute_turn + 1,
    )
    if base_timing.absolute_turn > config.max_absolute_turns:
        raise ValueError(
            f"Absolute turn exceeds max_absolute_turns={config.max_absolute_turns}."
        )

    updated_state = replace(
        state,
        active_player=next_player,
        phase=TurnPhase.SOW,
        timing=base_timing,
    )
    if round_ended:
        completed_round_number = state.timing.round_number
        updated_state = resolve_round_end(updated_state, config)
    else:
        updated_state = replace(
            updated_state,
            timing=replace(
                updated_state.timing,
                turn_in_round=state.timing.turn_in_round + 1,
            ),
        )

    events: list[GameEvent] = [
        GameEvent(
            event_type=EventType.TURN_ADVANCE,
            actor=actor,
            action_id=action_id,
            details=make_event_details(
                from_player=actor.name.lower(),
                to_player=next_player.name.lower(),
            ),
        )
    ]
    if round_ended and completed_round_number is not None:
        events.append(
            GameEvent(
                event_type=EventType.ROUND_END,
                actor=actor,
                action_id=action_id,
                details=make_event_details(round=completed_round_number),
            )
        )
        events.append(
            GameEvent(
                event_type=EventType.ROUND_ADVANCE,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    from_round=completed_round_number,
                    to_round=updated_state.timing.round_number,
                ),
            )
        )
    if season_ended:
        completed_season_number = state.timing.season_number
        events.append(
            GameEvent(
                event_type=EventType.SEASON_END,
                actor=actor,
                action_id=action_id,
                details=make_event_details(season=completed_season_number),
            )
        )

    return TimingAdvanceResult(
        state=updated_state,
        events=tuple(events),
        round_ended=round_ended,
        season_ended=season_ended,
        completed_round_number=completed_round_number,
        completed_season_number=completed_season_number,
    )


def _ensure_timing_config_compatible(state: GameState, config: TimingConfig) -> None:
    if state.player_count != config.players_per_round:
        raise ValueError(
            "Timing config players_per_round does not match state player count: "
            f"{config.players_per_round} vs {state.player_count}."
        )
