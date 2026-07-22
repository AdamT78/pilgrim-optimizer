"""State transitions and legal action generation for Ruleset A."""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.actions import (
    FullTurnAction,
    GameAction,
    action_id,
    resolution_from_effect,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import EventType, PlayerId, TurnPhase, TurnResolutionType
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
    """Generate deterministic full-turn actions for current phase."""
    if state.phase is not TurnPhase.SOW:
        return ()
    return _legal_full_turn_actions(state, config)


def apply_action(state: GameState, action: GameAction, config: GameConfig) -> TransitionResult:
    """Apply one full-turn action with invariant checks."""
    if not isinstance(action, FullTurnAction):
        raise TypeError(f"Unsupported action type: {type(action)!r}")
    return _apply_full_turn_action(state, action, config)


def _legal_full_turn_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    player_vector = state.player_vector(state.active_player)
    actions: list[GameAction] = []
    for origin in occupied_positions(player_vector):
        picked_up = player_vector[origin]
        for route in generate_routes(origin, picked_up, config.board):
            sowed_vector = sow_vector(player_vector, origin, route, config.board)
            for duty_position in config.duty_positions():
                if sowed_vector[duty_position] <= 0:
                    continue
                duty = config.duty_for_position(duty_position)
                if duty is None:
                    continue
                actions.append(
                    FullTurnAction(
                        origin=origin,
                        route=route,
                        selected_duty=duty_position,
                        resolution=resolution_from_effect(duty.effect),
                    )
                )
                actions.append(
                    FullTurnAction(
                        origin=origin,
                        route=route,
                        selected_duty=duty_position,
                        resolution=TurnResolutionType.TITHE,
                    )
                )
    return tuple(actions)


def _apply_full_turn_action(
    state: GameState,
    action: FullTurnAction,
    config: GameConfig,
) -> TransitionResult:
    ensure_phase(state, expected=TurnPhase.SOW, action_name="Full turn action")

    player = state.active_player
    player_vector = state.player_vector(player)
    picked_up = player_vector[action.origin]
    if picked_up <= 0:
        raise TransitionValidationError("Sowing source must be occupied.")
    ensure_route_length_matches(picked_up=picked_up, route_length=len(action.route))

    try:
        sowed_vector = sow_vector(player_vector, action.origin, action.route, config.board)
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc

    state_after_sow = state.with_player_vector(player, sowed_vector)
    ensure_selected_duty_has_acolyte(
        state_after_sow,
        player=player,
        duty_position=action.selected_duty,
    )

    events: list[GameEvent] = [
        GameEvent(
            event_type=EventType.SOWING,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(
                source=action.origin,
                picked_up=picked_up,
                route="->".join(str(position) for position in action.route),
            ),
        ),
    ]

    if action.resolution is TurnResolutionType.TITHE:
        next_state = state_after_sow.next_player_turn()
        ensure_non_negative_resources(next_state)
        ensure_acolyte_conservation(state, next_state)
        events.extend(
            [
                GameEvent(
                    event_type=EventType.DUTY_RESOLUTION,
                    actor=player,
                    action_id=action_id(action),
                    details=make_event_details(
                        duty_position=action.selected_duty,
                        mode="tithe",
                        recall=False,
                    ),
                ),
                GameEvent(
                    event_type=EventType.INVARIANT_CHECK,
                    actor=player,
                    action_id=action_id(action),
                    details=make_event_details(name="post_turn", acolytes_conserved=True),
                ),
            ]
        )
        return TransitionResult(state=next_state, events=tuple(events))

    duty = config.duty_for_position(action.selected_duty)
    if duty is None:
        raise TransitionValidationError(f"No duty configured at position {action.selected_duty}.")

    expected_resolution = resolution_from_effect(duty.effect)
    if action.resolution is not expected_resolution:
        message = (
            f"Selected action {action.resolution.value} does not match "
            f"duty effect {duty.effect.value}."
        )
        raise TransitionValidationError(
            message
        )

    player_count = sowed_vector[action.selected_duty]
    opponent_counts = tuple(
        state.player_vector(opponent_id)[action.selected_duty] for opponent_id in _opponents(player)
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

    recalled = sowed_vector[action.selected_duty]
    recalled_vector = list(sowed_vector)
    recalled_vector[0] += recalled
    recalled_vector[action.selected_duty] = 0

    updated_state = state_after_sow.with_player_state(player, new_player_state)
    updated_state = updated_state.with_player_vector(player, tuple(recalled_vector))
    next_state = updated_state.next_player_turn()

    ensure_non_negative_resources(next_state)
    ensure_acolyte_conservation(state, next_state)

    events.extend(
        [
            GameEvent(
                event_type=EventType.DUTY_RESOLUTION,
                actor=player,
                action_id=action_id(action),
                details=make_event_details(
                    duty_position=action.selected_duty,
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
                details=make_event_details(duty_position=action.selected_duty, recalled=recalled),
            ),
            GameEvent(
                event_type=EventType.INVARIANT_CHECK,
                actor=player,
                action_id=action_id(action),
                details=make_event_details(name="post_turn", acolytes_conserved=True),
            ),
        ]
    )
    return TransitionResult(state=next_state, events=tuple(events))


def _opponents(player: PlayerId) -> tuple[PlayerId, ...]:
    if player is PlayerId.PLAYER_ONE:
        return (PlayerId.PLAYER_TWO,)
    return (PlayerId.PLAYER_ONE,)
