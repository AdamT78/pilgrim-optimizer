"""State transitions and legal action generation for Ruleset A."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pilgrim.model.actions import (
    GameAction,
    ResolveDutyAction,
    SowingAction,
    TitheAction,
    action_id,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import EventType, PlayerId, TurnPhase
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.state import GameState
from pilgrim.rules.duties import apply_duty_effect, duty_strength, duty_value_and_silver_cost
from pilgrim.rules.mancala import generate_routes, occupied_positions, sow_vector
from pilgrim.rules.validation import (
    TransitionValidationError,
    ensure_acolyte_conservation,
    ensure_affordable_minority,
    ensure_non_negative_resources,
    ensure_phase,
    ensure_route_length_matches,
    ensure_selected_duty_has_acolyte,
)


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Transition output containing next state and event records."""

    state: GameState
    events: tuple[GameEvent, ...]


def legal_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    """Generate deterministic legal actions for current phase."""
    if state.phase is TurnPhase.SOW:
        return _legal_sowing_actions(state, config)
    if state.phase is TurnPhase.DUTY:
        return _legal_duty_actions(state, config)
    return ()


def apply_action(state: GameState, action: GameAction, config: GameConfig) -> TransitionResult:
    """Apply one legal action with invariant checks."""
    if isinstance(action, SowingAction):
        return _apply_sowing_action(state, action, config)
    if isinstance(action, ResolveDutyAction):
        return _apply_resolve_duty_action(state, action, config)
    if isinstance(action, TitheAction):
        return _apply_tithe_action(state, action)
    raise TypeError(f"Unsupported action type: {type(action)!r}")


def _legal_sowing_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    player_vector = state.player_vector(state.active_player)
    actions: list[GameAction] = []
    for source in occupied_positions(player_vector):
        picked_up = player_vector[source]
        for route in generate_routes(source, picked_up, config.board):
            actions.append(SowingAction(source=source, route=route))
    return tuple(actions)


def _legal_duty_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    player_vector = state.player_vector(state.active_player)
    actions: list[GameAction] = []
    for duty_position in config.duty_positions():
        if player_vector[duty_position] <= 0:
            continue
        actions.append(ResolveDutyAction(duty_position=duty_position))
        actions.append(TitheAction(duty_position=duty_position))
    return tuple(actions)


def _apply_sowing_action(
    state: GameState,
    action: SowingAction,
    config: GameConfig,
) -> TransitionResult:
    ensure_phase(state, expected=TurnPhase.SOW, action_name="Sowing action")

    player = state.active_player
    player_vector = state.player_vector(player)
    picked_up = player_vector[action.source]
    if picked_up <= 0:
        raise TransitionValidationError("Sowing source must be occupied.")
    ensure_route_length_matches(picked_up=picked_up, route_length=len(action.route))

    try:
        new_vector = sow_vector(player_vector, action.source, action.route, config.board)
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc

    updated_state = state.with_player_vector(player, new_vector)
    next_state = replace(updated_state, phase=TurnPhase.DUTY)
    ensure_non_negative_resources(next_state)
    ensure_acolyte_conservation(state, next_state)

    events = (
        GameEvent(
            event_type=EventType.SOWING,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(
                source=action.source,
                picked_up=picked_up,
                route="->".join(str(position) for position in action.route),
            ),
        ),
        GameEvent(
            event_type=EventType.INVARIANT_CHECK,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(name="post_sow", acolytes_conserved=True),
        ),
    )
    return TransitionResult(state=next_state, events=events)


def _apply_resolve_duty_action(
    state: GameState, action: ResolveDutyAction, config: GameConfig
) -> TransitionResult:
    ensure_phase(state, expected=TurnPhase.DUTY, action_name="Duty resolution")

    player = state.active_player
    ensure_selected_duty_has_acolyte(state, player=player, duty_position=action.duty_position)
    duty = config.duty_for_position(action.duty_position)
    if duty is None:
        raise TransitionValidationError(f"No duty configured at position {action.duty_position}.")

    player_vector = state.player_vector(player)
    player_count = player_vector[action.duty_position]
    opponent_counts = tuple(
        state.player_vector(opponent_id)[action.duty_position] for opponent_id in _opponents(player)
    )

    strength = duty_strength(player_count, opponent_counts)
    duty_value, silver_cost = duty_value_and_silver_cost(strength)
    available_silver = state.player_state(player).resources.silver
    ensure_affordable_minority(available_silver=available_silver, silver_cost=silver_cost)

    try:
        new_player_state, resource_delta, piety_delta = apply_duty_effect(
            state.player_state(player),
            effect=duty.effect,
            duty_value=duty_value,
            silver_cost=silver_cost,
        )
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc

    recalled = player_vector[action.duty_position]
    recalled_vector = list(player_vector)
    recalled_vector[0] += recalled
    recalled_vector[action.duty_position] = 0

    updated_state = state.with_player_state(player, new_player_state)
    updated_state = updated_state.with_player_vector(player, tuple(recalled_vector))
    next_state = updated_state.next_player_turn()

    ensure_non_negative_resources(next_state)
    ensure_acolyte_conservation(state, next_state)

    events = (
        GameEvent(
            event_type=EventType.DUTY_RESOLUTION,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(
                duty_position=action.duty_position,
                duty_key=duty.key,
                strength=strength.value,
                duty_value=duty_value,
                silver_cost=silver_cost,
                effect=duty.effect.value,
            ),
        ),
        GameEvent(
            event_type=EventType.RESOURCE_DELTA,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(
                stone=resource_delta[0],
                silver=resource_delta[1],
                wheat=resource_delta[2],
            ),
        ),
        GameEvent(
            event_type=EventType.PIETY_DELTA,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(piety=piety_delta),
        ),
        GameEvent(
            event_type=EventType.ACOLYTE_RECALL,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(duty_position=action.duty_position, recalled=recalled),
        ),
        GameEvent(
            event_type=EventType.INVARIANT_CHECK,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(name="post_duty", acolytes_conserved=True),
        ),
    )
    return TransitionResult(state=next_state, events=events)


def _apply_tithe_action(state: GameState, action: TitheAction) -> TransitionResult:
    ensure_phase(state, expected=TurnPhase.DUTY, action_name="Tithe")
    player = state.active_player
    ensure_selected_duty_has_acolyte(state, player=player, duty_position=action.duty_position)

    next_state = state.next_player_turn()
    ensure_non_negative_resources(next_state)
    ensure_acolyte_conservation(state, next_state)

    events = (
        GameEvent(
            event_type=EventType.DUTY_RESOLUTION,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(
                duty_position=action.duty_position,
                mode="tithe",
                recall=False,
            ),
        ),
        GameEvent(
            event_type=EventType.INVARIANT_CHECK,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(name="post_tithe", acolytes_conserved=True),
        ),
    )
    return TransitionResult(state=next_state, events=events)


def _opponents(player: PlayerId) -> tuple[PlayerId, ...]:
    if player is PlayerId.PLAYER_ONE:
        return (PlayerId.PLAYER_TWO,)
    return (PlayerId.PLAYER_ONE,)
