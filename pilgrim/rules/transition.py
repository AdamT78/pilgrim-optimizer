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
from pilgrim.model.enums import DutyEffect, EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.state import GameState
from pilgrim.rules.alms import AlmsPayment, resolve_give_alms
from pilgrim.rules.duties import apply_duty_effect, duty_strength, duty_value_and_silver_cost
from pilgrim.rules.mancala import generate_routes, occupied_positions, sow_vector
from pilgrim.rules.piety import score_piety
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
    player_resources = state.player_state(state.active_player).resources
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
                if duty.effect is DutyEffect.GIVE_ALMS:
                    player_count = sowed_vector[duty_position]
                    opponent_counts = tuple(
                        state.player_vector(opponent_id)[duty_position]
                        for opponent_id in _opponents(state.active_player)
                    )
                    strength = duty_strength(player_count, opponent_counts)
                    duty_value, silver_cost = duty_value_and_silver_cost(strength)
                    available_silver = player_resources.silver - silver_cost
                    if available_silver >= 0:
                        for payment in _alms_payment_options(
                            duty_value=duty_value,
                            available_silver=available_silver,
                            available_wheat=player_resources.wheat,
                        ):
                            actions.append(
                                FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.GIVE_ALMS,
                                    alms_payment_silver=payment.silver,
                                    alms_payment_wheat=payment.wheat,
                                )
                            )
                else:
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
                    details=make_event_details(
                        name="post_turn",
                        acolytes_conserved=True,
                        total_workforce=next_state.total_acolytes(player),
                    ),
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
        raise TransitionValidationError(message)

    player_count = sowed_vector[action.selected_duty]
    opponent_counts = tuple(
        state.player_vector(opponent_id)[action.selected_duty] for opponent_id in _opponents(player)
    )
    strength = duty_strength(player_count, opponent_counts)
    duty_value, silver_cost = duty_value_and_silver_cost(strength)
    available_silver = state_after_sow.player_state(player).resources.silver
    ensure_affordable_minority(available_silver=available_silver, silver_cost=silver_cost)

    if (
        action.resolution is not TurnResolutionType.GIVE_ALMS
        and (action.alms_payment_silver != 0 or action.alms_payment_wheat != 0)
    ):
        raise TransitionValidationError("Only Give Alms actions may include Alms payment fields.")

    if action.resolution is TurnResolutionType.GIVE_ALMS:
        try:
            alms_resolution = resolve_give_alms(
                state_after_sow.player_state(player),
                duty_value=duty_value,
                payment=AlmsPayment(
                    silver=action.alms_payment_silver,
                    wheat=action.alms_payment_wheat,
                ),
                minority_silver_cost=silver_cost,
                config=config.alms,
            )
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc
        new_player_state = alms_resolution.player_state
        resource_delta = alms_resolution.resource_delta
        old_piety_position = state_after_sow.player_state(player).piety
        new_piety_position = state_after_sow.player_state(player).piety
    else:
        try:
            (
                new_player_state,
                resource_delta,
                old_piety_position,
                new_piety_position,
            ) = apply_duty_effect(
                state_after_sow.player_state(player),
                effect=duty.effect,
                duty_value=duty_value,
                silver_cost=silver_cost,
                piety_config=config.piety,
            )
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc

    post_effect_vector = new_player_state.workforce.mancala
    recalled = post_effect_vector[action.selected_duty]
    recalled_vector = list(post_effect_vector)
    recalled_vector[0] += recalled
    recalled_vector[action.selected_duty] = 0

    updated_state = state_after_sow.with_player_state(player, new_player_state)
    updated_state = updated_state.with_player_vector(player, tuple(recalled_vector))
    next_state = updated_state.next_player_turn()

    ensure_non_negative_resources(next_state)
    ensure_acolyte_conservation(state, next_state)

    piety_position_delta = new_piety_position - old_piety_position
    old_piety_vp = score_piety(old_piety_position, config.piety)
    new_piety_vp = score_piety(new_piety_position, config.piety)
    piety_vp_delta = new_piety_vp - old_piety_vp

    events.append(
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
        )
    )
    events.append(
        GameEvent(
            event_type=EventType.RESOURCE_DELTA,
            actor=player,
            action_id=action_id(action),
            details=make_event_details(
                stone=resource_delta[0],
                silver=resource_delta[1],
                wheat=resource_delta[2],
            ),
        )
    )

    if action.resolution is TurnResolutionType.GIVE_ALMS:
        events.append(
            GameEvent(
                event_type=EventType.ALMS_PAYMENT,
                actor=player,
                action_id=action_id(action),
                details=make_event_details(
                    silver=action.alms_payment_silver,
                    wheat=action.alms_payment_wheat,
                    minority_silver_cost=silver_cost,
                ),
            )
        )
        events.append(
            GameEvent(
                event_type=EventType.ALMS_PROGRESS,
                actor=player,
                action_id=action_id(action),
                details=make_event_details(
                    old_row=alms_resolution.old_position,
                    new_row=alms_resolution.new_position,
                ),
            )
        )
        for outcome in alms_resolution.threshold_outcomes:
            events.append(
                GameEvent(
                    event_type=EventType.ALMS_THRESHOLD_REWARD,
                    actor=player,
                    action_id=action_id(action),
                    details=make_event_details(
                        threshold=outcome.threshold,
                        reward=outcome.reward_key,
                        moved=outcome.moved,
                        description=outcome.description,
                    ),
                )
            )
    elif piety_position_delta != 0:
        events.append(
            GameEvent(
                event_type=EventType.PIETY_DELTA,
                actor=player,
                action_id=action_id(action),
                details=make_event_details(
                    amount_gained=piety_position_delta,
                    old_piety_position=old_piety_position,
                    new_piety_position=new_piety_position,
                    old_piety_vp=old_piety_vp,
                    new_piety_vp=new_piety_vp,
                    piety_vp_delta=piety_vp_delta,
                ),
            )
        )

    events.extend(
        [
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
                details=make_event_details(
                    name="post_turn",
                    acolytes_conserved=True,
                    total_workforce=next_state.total_acolytes(player),
                ),
            ),
        ]
    )
    return TransitionResult(state=next_state, events=tuple(events))


def _opponents(player: PlayerId) -> tuple[PlayerId, ...]:
    if player is PlayerId.PLAYER_ONE:
        return (PlayerId.PLAYER_TWO,)
    return (PlayerId.PLAYER_ONE,)


def _alms_payment_options(
    *,
    duty_value: int,
    available_silver: int,
    available_wheat: int,
) -> tuple[AlmsPayment, ...]:
    if duty_value <= 0:
        return ()
    options: list[AlmsPayment] = []
    for silver in range(duty_value, -1, -1):
        wheat = duty_value - silver
        if silver <= available_silver and wheat <= available_wheat:
            options.append(AlmsPayment(silver=silver, wheat=wheat))
    return tuple(options)
