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
from pilgrim.rules.alms import AlmsPayment, resolve_alms_season_end, resolve_give_alms
from pilgrim.rules.buildings import validate_building_state
from pilgrim.rules.dummy import move_dummy_acolytes_end_of_season
from pilgrim.rules.duties import apply_duty_effect, duty_strength, duty_value_and_silver_cost
from pilgrim.rules.mancala import generate_routes, occupied_positions, sow_vector
from pilgrim.rules.merchant import (
    advance_merchant_position,
    current_merchant_duty,
    current_merchant_resource,
)
from pilgrim.rules.piety import score_piety
from pilgrim.rules.round_end import (
    apply_excess_resource_caps,
    resolve_trade_route_income,
    select_next_start_player,
)
from pilgrim.rules.ship import advance_ship_position, is_nw_pilgrimage_site, is_pilgrimage_site
from pilgrim.rules.timing import advance_timing, resolve_round_end, resolve_season_end
from pilgrim.rules.validation import (
    TransitionValidationError,
    ensure_acolyte_conservation,
    ensure_affordable_minority,
    ensure_dummy_acolyte_conservation,
    ensure_non_negative_resources,
    ensure_phase,
    ensure_route_length_matches,
    ensure_selected_duty_has_acolyte,
    ensure_valid_dummy_state,
    ensure_valid_timing,
)


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Transition output containing next state and event records."""

    state: GameState
    events: tuple[GameEvent, ...]


def legal_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    """Generate deterministic full-turn actions for current phase."""
    if state.game_over:
        return ()
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
                    opponent_counts = _competing_counts(
                        state,
                        player=state.active_player,
                        duty_position=duty_position,
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
    if state.game_over:
        raise TransitionValidationError("Cannot apply action: game is already over.")
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

    transition_action_id = action_id(action)
    events: list[GameEvent] = [
        GameEvent(
            event_type=EventType.SOWING,
            actor=player,
            action_id=transition_action_id,
            details=make_event_details(
                source=action.origin,
                picked_up=picked_up,
                route="->".join(str(position) for position in action.route),
            ),
        ),
    ]

    if action.resolution is TurnResolutionType.TITHE:
        updated_state = state_after_sow
        events.append(
            GameEvent(
                event_type=EventType.DUTY_RESOLUTION,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    duty_position=action.selected_duty,
                    mode="tithe",
                    recall=False,
                ),
            )
        )
    else:
        duty = config.duty_for_position(action.selected_duty)
        if duty is None:
            raise TransitionValidationError(
                f"No duty configured at position {action.selected_duty}."
            )

        expected_resolution = resolution_from_effect(duty.effect)
        if action.resolution is not expected_resolution:
            message = (
                f"Selected action {action.resolution.value} does not match "
                f"duty effect {duty.effect.value}."
            )
            raise TransitionValidationError(message)

        player_count = sowed_vector[action.selected_duty]
        opponent_counts = _competing_counts(
            state,
            player=player,
            duty_position=action.selected_duty,
        )
        strength = duty_strength(player_count, opponent_counts)
        duty_value, silver_cost = duty_value_and_silver_cost(strength)
        available_silver = state_after_sow.player_state(player).resources.silver
        ensure_affordable_minority(available_silver=available_silver, silver_cost=silver_cost)

        if (
            action.resolution is not TurnResolutionType.GIVE_ALMS
            and (action.alms_payment_silver != 0 or action.alms_payment_wheat != 0)
        ):
            raise TransitionValidationError(
                "Only Give Alms actions may include Alms payment fields."
            )

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

        piety_position_delta = new_piety_position - old_piety_position
        old_piety_vp = score_piety(old_piety_position, config.piety)
        new_piety_vp = score_piety(new_piety_position, config.piety)
        piety_vp_delta = new_piety_vp - old_piety_vp

        events.append(
            GameEvent(
                event_type=EventType.DUTY_RESOLUTION,
                actor=player,
                action_id=transition_action_id,
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
                action_id=transition_action_id,
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
                    action_id=transition_action_id,
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
                    action_id=transition_action_id,
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
                        action_id=transition_action_id,
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
                    action_id=transition_action_id,
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

        events.append(
            GameEvent(
                event_type=EventType.ACOLYTE_RECALL,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    duty_position=action.selected_duty,
                    recalled=recalled,
                ),
            )
        )

    try:
        timing_result = advance_timing(
            updated_state,
            config.timing,
            action_id=transition_action_id,
        )
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc

    next_state = timing_result.state
    events.extend(timing_result.events)
    if timing_result.round_ended:
        completed_round_number = timing_result.completed_round_number
        if completed_round_number is None:
            completed_round_number = next_state.timing.round_number
        next_state, round_end_events = _resolve_round_end_phases(
            next_state,
            config,
            actor=player,
            action_id=transition_action_id,
            completed_round_number=completed_round_number,
        )
        events.extend(round_end_events)

    ensure_non_negative_resources(next_state)
    validate_building_state(next_state, config)
    ensure_valid_timing(next_state)
    ensure_valid_dummy_state(next_state)
    ensure_acolyte_conservation(state, next_state)
    ensure_dummy_acolyte_conservation(state, next_state)
    events.append(
        GameEvent(
            event_type=EventType.INVARIANT_CHECK,
            actor=player,
            action_id=transition_action_id,
            details=make_event_details(
                name="post_turn",
                acolytes_conserved=True,
                invariant_scope="all_players",
                total_workforce_player_one=next_state.total_acolytes(PlayerId.PLAYER_ONE),
                total_workforce_player_two=next_state.total_acolytes(PlayerId.PLAYER_TWO),
                total_workforce_all_players=(
                    next_state.total_acolytes(PlayerId.PLAYER_ONE)
                    + next_state.total_acolytes(PlayerId.PLAYER_TWO)
                ),
                dummy_north_group_total=next_state.dummy_acolytes.north_total,
                dummy_south_group_total=next_state.dummy_acolytes.south_total,
                dummy_total=next_state.dummy_total,
            ),
        )
    )
    return TransitionResult(state=next_state, events=tuple(events))


def _resolve_round_end_phases(
    state: GameState,
    config: GameConfig,
    *,
    actor: PlayerId,
    action_id: str,
    completed_round_number: int,
) -> tuple[GameState, tuple[GameEvent, ...]]:
    events: list[GameEvent] = []
    next_state = state

    # 1) Excess cap
    next_state, excess_events = apply_excess_resource_caps(
        next_state,
        actor=actor,
        action_id=action_id,
    )
    events.extend(excess_events)

    # 2) Ship advance
    from_ship = next_state.ship_position
    to_ship = advance_ship_position(from_ship, config.ship)
    next_state = next_state.with_ship_position(to_ship)
    next_state = next_state.with_completed_rounds(next_state.completed_rounds + 1)
    ship_at_pilgrimage = is_pilgrimage_site(to_ship, config.ship)
    ship_at_nw = is_nw_pilgrimage_site(to_ship, config.ship)
    events.append(
        GameEvent(
            event_type=EventType.SHIP_ADVANCE,
            actor=actor,
            action_id=action_id,
            details=make_event_details(
                from_position=from_ship,
                to_position=to_ship,
                at_pilgrimage_site=ship_at_pilgrimage,
                at_nw_pilgrimage_site=ship_at_nw,
                completed_rounds=next_state.completed_rounds,
            ),
        )
    )

    # 3) Season end from ship marker
    season_ended = ship_at_pilgrimage
    if season_ended:
        completed_season_number = next_state.timing.season_number
        events.append(
            GameEvent(
                event_type=EventType.SEASON_END,
                actor=actor,
                action_id=action_id,
                details=make_event_details(season=completed_season_number),
            )
        )
        alms_result = resolve_alms_season_end(next_state, config.alms)
        next_state = alms_result.state
        events.extend(alms_result.events)

    # Final NW pilgrimage-site return after full 26-round loop ends the game.
    game_over = (
        season_ended
        and ship_at_nw
        and next_state.completed_rounds >= config.ship.path_length
    )
    if game_over:
        next_state = next_state.with_game_over(True)
        events.append(
            GameEvent(
                event_type=EventType.GAME_END,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    reason=(
                        "ship returned to NW Pilgrimage Site after final Alms Table assessment"
                    )
                ),
            )
        )
        return next_state, tuple(events)

    # Dummy acolytes move on normal season ends only, not on final game-ending NW return.
    if season_ended:
        next_state, dummy_move_events = move_dummy_acolytes_end_of_season(
            next_state,
            actor=actor,
            action_id=action_id,
        )
        events.extend(dummy_move_events)

    # 4) Merchant advances once at round end.
    if config.merchant.advance_at_round_end:
        from_duty = current_merchant_duty(next_state, config.merchant)
        next_merchant_position = advance_merchant_position(
            next_state.merchant_position,
            config.merchant,
        )
        next_state = next_state.with_merchant_position(next_merchant_position)
        to_duty = current_merchant_duty(next_state, config.merchant)
        current_resource = current_merchant_resource(next_state, config.merchant)
        events.append(
            GameEvent(
                event_type=EventType.MERCHANT_ADVANCE,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    from_duty=from_duty,
                    to_duty=to_duty,
                    current_resource=current_resource if current_resource is not None else "none",
                ),
            )
        )

    # 5) Trade-route placeholder hook.
    next_state, trade_route_events = resolve_trade_route_income(
        next_state,
        actor=actor,
        action_id=action_id,
    )
    events.extend(trade_route_events)

    # 6) Start-player placeholder policy.
    next_state, start_player_events, _ = select_next_start_player(
        next_state,
        actor=actor,
        action_id=action_id,
    )
    events.extend(start_player_events)

    # 7) Round advance and potential season advance.
    next_state = resolve_round_end(next_state, config.timing)
    events.append(
        GameEvent(
            event_type=EventType.ROUND_ADVANCE,
            actor=actor,
            action_id=action_id,
            details=make_event_details(
                from_round=completed_round_number,
                to_round=next_state.timing.round_number,
            ),
        )
    )
    if season_ended:
        completed_season_number = next_state.timing.season_number
        next_state = resolve_season_end(next_state, config.timing)
        events.append(
            GameEvent(
                event_type=EventType.SEASON_ADVANCE,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    from_season=completed_season_number,
                    to_season=next_state.timing.season_number,
                ),
            )
        )
    return next_state, tuple(events)


def _opponents(player: PlayerId) -> tuple[PlayerId, ...]:
    if player is PlayerId.PLAYER_ONE:
        return (PlayerId.PLAYER_TWO,)
    return (PlayerId.PLAYER_ONE,)


def _competing_counts(
    state: GameState,
    *,
    player: PlayerId,
    duty_position: int,
) -> tuple[int, ...]:
    opponent_counts = [
        state.player_vector(opponent_id)[duty_position] for opponent_id in _opponents(player)
    ]
    opponent_counts.append(state.dummy_at_position(duty_position))
    return tuple(opponent_counts)


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
