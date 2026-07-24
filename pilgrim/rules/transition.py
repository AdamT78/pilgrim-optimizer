"""State transitions and legal action generation for Ruleset A."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations_with_replacement

from pilgrim.model.actions import (
    AllocationMove,
    FullTurnAction,
    GameAction,
    SetupSowAction,
    action_id,
    readable_route,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import DutyStrength, EventType, PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.events import GameEvent, make_event_details
from pilgrim.model.special_activities import SPECIAL_ACTIVITY_IDS
from pilgrim.model.state import GameState
from pilgrim.rules.alms import (
    AlmsPayment,
    resolve_alms_season_end,
    resolve_donate_building_alms,
    resolve_give_alms,
)
from pilgrim.rules.buildings import (
    BuildingAbilitySource,
    BuildingHirePayment,
    BuildingHireTurnContext,
    apply_building_hire_payment,
    building_ability_source,
    can_hire_building_this_turn,
    building_live_round,
    construct_building_from_market,
    donate_active_building,
    has_available_player_board_slot,
    is_building_live,
    mill_actual_wheat_cost,
    mill_wheat_waiver,
    player_has_active_chapter_house,
    record_hired_building_this_turn,
    used_player_board_slots,
    validate_hire_sequence_for_turn,
    validate_building_state,
)
from pilgrim.rules.dummy import move_dummy_acolytes_end_of_season
from pilgrim.rules.duties import (
    action_options_for_duty_category,
    apply_duty_effect,
    apply_produce_resolution,
    duty_strength,
    duty_value_and_silver_cost,
    effect_for_resolution,
)
from pilgrim.rules.mancala import generate_routes, occupied_positions, sow_vector
from pilgrim.rules.merchant import (
    advance_merchant_position,
    current_merchant_duty,
    current_merchant_resource,
)
from pilgrim.rules.ordination import (
    ORDINATION_MISSION,
    ORDINATION_ORDAIN,
    apply_ordination_step,
    legal_ordination_step_sequences,
)
from pilgrim.rules.piety import score_piety
from pilgrim.rules.round_end import (
    apply_excess_resource_caps,
    resolve_trade_route_income,
    select_next_start_player,
)
from pilgrim.rules.ship import advance_ship_position, is_nw_pilgrimage_site, is_pilgrimage_site
from pilgrim.rules.special_activities import (
    alms_house_duty_value_bonus_capacity,
    alms_house_extra_payment_options,
    apply_allocation_move_with_capacity,
    can_use_alms_house_bonus,
    clerical_devotion_bonus,
    clerical_silversmith_bonus,
    legal_allocation_moves,
    produce_stone_mason_bonus,
    produce_wheat_fields_bonus,
    road_engineer_construct_extra_roads_bonus,
    road_engineer_duty_value_bonus_hook,
    special_activity_capacity,
    special_activity_count,
)
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
    ensure_valid_special_activities_state,
    ensure_valid_setup_state,
    ensure_valid_timing,
)


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Transition output containing next state and event records."""

    state: GameState
    events: tuple[GameEvent, ...]


_TAXATION_RESOURCE_TYPES: tuple[str, ...] = ("stone", "silver", "wheat")
_CONSTRUCT_PLAN_ROAD = "road"
_CONSTRUCT_PLAN_EXTRA_ROAD = "road_engineer_extra_road"
_CONSTRUCT_ROAD_SCAFFOLD_TEXT = "construct road part requires spatial road system"
_SIMPLE_BONUS_BUILDING_BY_ACTION: dict[TurnResolutionType, str] = {
    TurnResolutionType.PRODUCE_WHEAT: "well",
    TurnResolutionType.PRODUCE_STONE: "quarry",
    TurnResolutionType.CLERICAL_SILVERSMITH: "mint",
    TurnResolutionType.CLERICAL_DEVOTION: "chapel",
}
_HIRED_BUILDINGS_BY_ACTION: dict[TurnResolutionType, frozenset[str]] = {
    TurnResolutionType.PRODUCE_WHEAT: frozenset({"well"}),
    TurnResolutionType.PRODUCE_STONE: frozenset({"quarry"}),
    TurnResolutionType.CLERICAL_SILVERSMITH: frozenset({"mint"}),
    TurnResolutionType.CLERICAL_DEVOTION: frozenset({"chapel"}),
    TurnResolutionType.ALLOCATION: frozenset({"infirmary"}),
    TurnResolutionType.GIVE_ALMS_PAID: frozenset({"mill"}),
    TurnResolutionType.ORDINATION: frozenset({"infirmary", "mill"}),
}


def legal_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    """Generate deterministic full-turn actions for current phase."""
    if state.game_over:
        return ()
    if state.phase is TurnPhase.SETUP_SOW:
        return _legal_setup_sow_actions(state, config)
    if state.phase is not TurnPhase.SOW:
        return ()
    return _legal_full_turn_actions(state, config)


def apply_action(state: GameState, action: GameAction, config: GameConfig) -> TransitionResult:
    """Apply one full-turn action with invariant checks."""
    if isinstance(action, SetupSowAction):
        return _apply_setup_sow_action(state, action, config)
    if isinstance(action, FullTurnAction):
        return _apply_full_turn_action(state, action, config)
    raise TypeError(f"Unsupported action type: {type(action)!r}")


def _legal_setup_sow_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    if not state.setup_sow_required or state.setup_sow_complete:
        return ()
    city_position = 0
    player_vector = state.player_vector(state.active_player)
    picked_up = player_vector[city_position]
    if picked_up <= 0:
        return ()
    return tuple(
        SetupSowAction(origin=city_position, route=route)
        for route in generate_routes(city_position, picked_up, config.board)
    )


def _legal_full_turn_actions(state: GameState, config: GameConfig) -> tuple[GameAction, ...]:
    player_vector = state.player_vector(state.active_player)
    player_state = state.player_state(state.active_player)
    player_resources = player_state.resources
    chapter_house_active = player_has_active_chapter_house(player_state)
    activity_capacity = special_activity_capacity(chapter_house_active=chapter_house_active)
    actions: list[GameAction] = []
    for origin in occupied_positions(player_vector):
        picked_up = player_vector[origin]
        for route in generate_routes(origin, picked_up, config.board):
            sowed_vector = sow_vector(player_vector, origin, route, config.board)
            for duty_position in config.duty_positions():
                if sowed_vector[duty_position] <= 0:
                    continue
                duty_category = config.duty_category_for_position(duty_position)
                category_actions = action_options_for_duty_category(duty_category)
                if TurnResolutionType.GIVE_ALMS_PAID in category_actions:
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
                        mill_source = building_ability_source(
                            state,
                            config,
                            acting_player=state.active_player,
                            building_key="mill",
                        )
                        extra_payment_options: list[tuple[int, int]] = []
                        if can_use_alms_house_bonus(player_state):
                            alms_house_bonus_cap = alms_house_duty_value_bonus_capacity(
                                player_state
                            )
                            extra_payment_options.extend(
                                _all_alms_house_extra_payment_options(
                                    max_bonus=alms_house_bonus_cap
                                )
                            )
                        extra_payment_options.append((0, 0))

                        for extra_silver, extra_wheat in extra_payment_options:
                            alms_house_bonus = extra_silver + extra_wheat
                            effective_alms_value = duty_value + alms_house_bonus
                            for payment in _alms_payment_options(
                                duty_value=effective_alms_value,
                                available_silver=effective_alms_value,
                                available_wheat=effective_alms_value,
                            ):
                                required_silver = silver_cost + extra_silver + payment.silver
                                required_wheat = extra_wheat + payment.wheat
                                base_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.GIVE_ALMS_PAID,
                                    alms_payment_silver=payment.silver,
                                    alms_payment_wheat=payment.wheat,
                                    alms_house_extra_silver=extra_silver,
                                    alms_house_extra_wheat=extra_wheat,
                                )

                                if _can_afford_resolution_costs(
                                    player_state,
                                    required_silver=required_silver,
                                    required_wheat=required_wheat,
                                ) and base_action not in actions:
                                    actions.append(base_action)

                                if required_wheat <= 0:
                                    continue

                                mill_wheat_spent = mill_actual_wheat_cost(required_wheat)
                                if mill_source.source_type == "own_active" and mill_source.usable:
                                    if _can_afford_resolution_costs(
                                        player_state,
                                        required_silver=required_silver,
                                        required_wheat=mill_wheat_spent,
                                    ) and base_action not in actions:
                                        actions.append(base_action)
                                elif _is_hired_source(mill_source) and mill_source.usable:
                                    if not _can_afford_resolution_costs(
                                        player_state,
                                        required_silver=required_silver,
                                        required_wheat=mill_wheat_spent,
                                        hired_source=mill_source,
                                    ):
                                        continue
                                    hired_action = FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=TurnResolutionType.GIVE_ALMS_PAID,
                                        alms_payment_silver=payment.silver,
                                        alms_payment_wheat=payment.wheat,
                                        alms_house_extra_silver=extra_silver,
                                        alms_house_extra_wheat=extra_wheat,
                                        hired_building_id="mill",
                                        hired_building_source=_hired_building_source_label(
                                            mill_source
                                        ),
                                    )
                                    if hired_action not in actions:
                                        actions.append(hired_action)
                        if TurnResolutionType.GIVE_ALMS_DONATE_BUILDING in category_actions:
                            for building_id in _legal_give_alms_donation_buildings(
                                player_state,
                                config,
                            ):
                                actions.append(
                                    FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=TurnResolutionType.GIVE_ALMS_DONATE_BUILDING,
                                        donate_building_id=building_id,
                                    )
                                )
                elif TurnResolutionType.ALLOCATION in category_actions:
                    player_count = sowed_vector[duty_position]
                    opponent_counts = _competing_counts(
                        state,
                        player=state.active_player,
                        duty_position=duty_position,
                    )
                    strength = duty_strength(player_count, opponent_counts)
                    duty_value, silver_cost = duty_value_and_silver_cost(strength)
                    base_move_sequences = _allocation_move_sequences(
                        player_state,
                        max_moves=duty_value,
                        special_activity_capacity=activity_capacity,
                    )
                    infirmary_source = building_ability_source(
                        state,
                        config,
                        acting_player=state.active_player,
                        building_key="infirmary",
                    )

                    if infirmary_source.source_type == "own_active" and infirmary_source.usable:
                        for move_sequence in _allocation_move_sequences(
                            player_state,
                            max_moves=duty_value + 1,
                            special_activity_capacity=activity_capacity,
                        ):
                            actions.append(
                                FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.ALLOCATION,
                                    allocation_moves=move_sequence,
                                )
                            )
                    else:
                        for move_sequence in base_move_sequences:
                            actions.append(
                                FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.ALLOCATION,
                                    allocation_moves=move_sequence,
                                )
                            )
                        if (
                            _is_hired_source(infirmary_source)
                            and infirmary_source.usable
                            and _can_afford_resolution_costs(
                                player_state,
                                required_silver=silver_cost,
                                hired_source=infirmary_source,
                            )
                        ):
                            for move_sequence in _allocation_move_sequences(
                                player_state,
                                max_moves=duty_value + 1,
                                special_activity_capacity=activity_capacity,
                            ):
                                if len(move_sequence) <= duty_value:
                                    continue
                                actions.append(
                                    FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=TurnResolutionType.ALLOCATION,
                                        allocation_moves=move_sequence,
                                        hired_building_id="infirmary",
                                        hired_building_source=_hired_building_source_label(
                                            infirmary_source
                                        ),
                                    )
                                )
                elif TurnResolutionType.CONSTRUCT_ROAD_DEFERRED in category_actions:
                    player_count = sowed_vector[duty_position]
                    opponent_counts = _competing_counts(
                        state,
                        player=state.active_player,
                        duty_position=duty_position,
                    )
                    strength = duty_strength(player_count, opponent_counts)
                    duty_value, silver_cost = duty_value_and_silver_cost(strength)
                    road_engineer_extra_roads = road_engineer_construct_extra_roads_bonus(
                        player_state
                    )
                    if player_resources.silver >= silver_cost:
                        constructible_building_ids = _constructible_building_ids(
                            state=state,
                            player_state=player_state,
                            config=config,
                            building_market=state.building_market,
                        )
                        for building_id in constructible_building_ids:
                            actions.append(
                                FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.CONSTRUCT_BUILDING,
                                    construct_building_id=building_id,
                                )
                            )
                        for construct_plan in _construct_road_only_plans(
                            duty_value=duty_value,
                            road_engineer_extra_roads=road_engineer_extra_roads,
                        ):
                            actions.append(
                                FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
                                    construct_plan=construct_plan,
                                )
                            )
                        for construct_plan in _construct_building_plus_road_plans(
                            duty_value=duty_value,
                            road_engineer_extra_roads=road_engineer_extra_roads,
                        ):
                            for building_id in constructible_building_ids:
                                actions.append(
                                    FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=(
                                            TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
                                        ),
                                        construct_plan=construct_plan,
                                        construct_building_id=building_id,
                                    )
                                )
                elif TurnResolutionType.ORDINATION in category_actions:
                    player_count = sowed_vector[duty_position]
                    opponent_counts = _competing_counts(
                        state,
                        player=state.active_player,
                        duty_position=duty_position,
                    )
                    strength = duty_strength(player_count, opponent_counts)
                    duty_value, silver_cost = duty_value_and_silver_cost(strength)
                    available_silver = player_resources.silver - silver_cost
                    if available_silver < 0:
                        continue

                    infirmary_source = building_ability_source(
                        state,
                        config,
                        acting_player=state.active_player,
                        building_key="infirmary",
                    )
                    mill_source = building_ability_source(
                        state,
                        config,
                        acting_player=state.active_player,
                        building_key="mill",
                    )

                    owns_active_infirmary = (
                        infirmary_source.source_type == "own_active" and infirmary_source.usable
                    )
                    owns_active_mill = mill_source.source_type == "own_active" and mill_source.usable
                    no_hire_mill_active = owns_active_mill
                    no_hire_player_state = _player_state_with_wheat_delta(
                        player_state,
                        wheat_delta=2 if no_hire_mill_active else 0,
                    )
                    if no_hire_player_state is not None:
                        base_sequences = legal_ordination_step_sequences(
                            no_hire_player_state,
                            max_steps=duty_value,
                        )
                        for step_sequence in base_sequences:
                            required_wheat = _ordination_wheat_cost(
                                len(step_sequence),
                                mill_active=no_hire_mill_active,
                            )
                            if not _can_afford_resolution_costs(
                                player_state,
                                required_silver=silver_cost,
                                required_wheat=required_wheat,
                            ):
                                continue
                            base_action = FullTurnAction(
                                origin=origin,
                                route=route,
                                selected_duty=duty_position,
                                resolution=TurnResolutionType.ORDINATION,
                                ordination_steps=step_sequence,
                            )
                            if base_action not in actions:
                                actions.append(base_action)

                        if owns_active_infirmary:
                            bonus_sequences = legal_ordination_step_sequences(
                                no_hire_player_state,
                                max_steps=duty_value + 1,
                            )
                            for step_sequence in bonus_sequences:
                                if len(step_sequence) <= duty_value:
                                    continue
                                required_wheat = _ordination_wheat_cost(
                                    len(step_sequence),
                                    mill_active=no_hire_mill_active,
                                )
                                if not _can_afford_resolution_costs(
                                    player_state,
                                    required_silver=silver_cost,
                                    required_wheat=required_wheat,
                                ):
                                    continue
                                bonus_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.ORDINATION,
                                    ordination_steps=step_sequence,
                                )
                                if bonus_action not in actions:
                                    actions.append(bonus_action)

                    if _is_hired_source(infirmary_source) and infirmary_source.usable:
                        hired_infirmary_player_state = _player_state_with_wheat_delta(
                            player_state,
                            wheat_delta=(2 if owns_active_mill else 0)
                            - _hire_wheat_cost(infirmary_source),
                        )
                        if hired_infirmary_player_state is not None:
                            bonus_sequences = legal_ordination_step_sequences(
                                hired_infirmary_player_state,
                                max_steps=duty_value + 1,
                            )
                            for step_sequence in bonus_sequences:
                                if len(step_sequence) <= duty_value:
                                    continue
                                required_wheat = _ordination_wheat_cost(
                                    len(step_sequence),
                                    mill_active=owns_active_mill,
                                )
                                if not _can_afford_resolution_costs(
                                    player_state,
                                    required_silver=silver_cost,
                                    required_wheat=required_wheat,
                                    hired_source=infirmary_source,
                                ):
                                    continue
                                hired_infirmary_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.ORDINATION,
                                    ordination_steps=step_sequence,
                                    hired_building_id="infirmary",
                                    hired_building_source=_hired_building_source_label(
                                        infirmary_source
                                    ),
                                )
                                if hired_infirmary_action not in actions:
                                    actions.append(hired_infirmary_action)

                    if _is_hired_source(mill_source) and mill_source.usable:
                        hired_mill_player_state = _player_state_with_wheat_delta(
                            player_state,
                            wheat_delta=2 - _hire_wheat_cost(mill_source),
                        )
                        if hired_mill_player_state is not None:
                            base_sequences = legal_ordination_step_sequences(
                                hired_mill_player_state,
                                max_steps=duty_value,
                            )
                            for step_sequence in base_sequences:
                                required_wheat = _ordination_wheat_cost(
                                    len(step_sequence),
                                    mill_active=True,
                                )
                                if not _can_afford_resolution_costs(
                                    player_state,
                                    required_silver=silver_cost,
                                    required_wheat=required_wheat,
                                    hired_source=mill_source,
                                ):
                                    continue
                                hired_mill_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.ORDINATION,
                                    ordination_steps=step_sequence,
                                    hired_building_id="mill",
                                    hired_building_source=_hired_building_source_label(
                                        mill_source
                                    ),
                                )
                                if hired_mill_action not in actions:
                                    actions.append(hired_mill_action)

                            if owns_active_infirmary:
                                bonus_sequences = legal_ordination_step_sequences(
                                    hired_mill_player_state,
                                    max_steps=duty_value + 1,
                                )
                                for step_sequence in bonus_sequences:
                                    if len(step_sequence) <= duty_value:
                                        continue
                                    required_wheat = _ordination_wheat_cost(
                                        len(step_sequence),
                                        mill_active=True,
                                    )
                                    if not _can_afford_resolution_costs(
                                        player_state,
                                        required_silver=silver_cost,
                                        required_wheat=required_wheat,
                                        hired_source=mill_source,
                                    ):
                                        continue
                                    hired_mill_bonus_action = FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=TurnResolutionType.ORDINATION,
                                        ordination_steps=step_sequence,
                                        hired_building_id="mill",
                                        hired_building_source=_hired_building_source_label(
                                            mill_source
                                        ),
                                    )
                                    if hired_mill_bonus_action not in actions:
                                        actions.append(hired_mill_bonus_action)
                elif TurnResolutionType.TAXATION in category_actions:
                    player_count = sowed_vector[duty_position]
                    opponent_counts = _competing_counts(
                        state,
                        player=state.active_player,
                        duty_position=duty_position,
                    )
                    strength = duty_strength(player_count, opponent_counts)
                    duty_value, silver_cost = duty_value_and_silver_cost(strength)
                    available_silver = player_resources.silver - silver_cost
                    if available_silver < 0:
                        continue
                    bonus_resource_types = _taxation_bonus_resource_types(
                        state,
                        config,
                        player=state.active_player,
                        sowed_vector=sowed_vector,
                        selected_duty=duty_position,
                    )
                    for step_1_resource in _TAXATION_RESOURCE_TYPES:
                        for step_2_resources in _taxation_bonus_resource_choices(
                            bonus_resource_types,
                            duty_value=duty_value,
                        ):
                            actions.append(
                                FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.TAXATION,
                                    taxation_step1_resource=step_1_resource,
                                    taxation_step2_resources=step_2_resources,
                                )
                            )
                else:
                    for category_action in category_actions:
                        actions.extend(
                            _legal_action_variants_for_resolution(
                                state=state,
                                config=config,
                                origin=origin,
                                route=route,
                                selected_duty=duty_position,
                                resolution=category_action,
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


def _apply_setup_sow_action(
    state: GameState,
    action: SetupSowAction,
    config: GameConfig,
) -> TransitionResult:
    if state.game_over:
        raise TransitionValidationError("Cannot apply action: game is already over.")
    ensure_phase(state, expected=TurnPhase.SETUP_SOW, action_name="Setup sow action")
    if not state.setup_sow_required or state.setup_sow_complete:
        raise TransitionValidationError("Setup sow action is not legal in current setup state.")
    if action.origin != 0:
        raise TransitionValidationError("Setup sow origin must be city.")

    player = state.active_player
    if player in set(state.setup_sow_completed_by):
        raise TransitionValidationError("Active player already completed setup sow.")

    player_vector = state.player_vector(player)
    picked_up = player_vector[action.origin]
    if picked_up <= 0:
        raise TransitionValidationError("Setup sow requires at least one city acolyte.")
    ensure_route_length_matches(picked_up=picked_up, route_length=len(action.route))

    try:
        sowed_vector = sow_vector(player_vector, action.origin, action.route, config.board)
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc

    transition_action_id = action_id(action)
    route_numbers = "->".join(str(position) for position in action.route)
    route_names = readable_route(action.origin, action.route, positions=config.board.positions)
    events: list[GameEvent] = [
        GameEvent(
            event_type=EventType.SETUP_SOWING,
            actor=player,
            action_id=transition_action_id,
            details=make_event_details(
                source=action.origin,
                picked_up=picked_up,
                route=route_numbers,
                route_names=route_names,
            ),
        )
    ]

    state_after_sow = state.with_player_vector(player, sowed_vector)
    completed_by = (*state.setup_sow_completed_by, player)
    events.append(
        GameEvent(
            event_type=EventType.SETUP_SOW_COMPLETE,
            actor=player,
            action_id=transition_action_id,
            details=make_event_details(player=_player_label(player)),
        )
    )

    next_player = _next_incomplete_setup_player(
        state_after_sow,
        current_player=player,
        completed_by=completed_by,
    )
    if next_player is None:
        next_state = replace(
            state_after_sow,
            setup_sow_complete=True,
            setup_sow_completed_by=tuple(completed_by),
            phase=TurnPhase.SOW,
            active_player=state.start_player,
        )
        events.append(
            GameEvent(
                event_type=EventType.SETUP_COMPLETE,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    start_player=_player_label(state.start_player),
                ),
            )
        )
    else:
        next_state = replace(
            state_after_sow,
            setup_sow_complete=False,
            setup_sow_completed_by=tuple(completed_by),
            phase=TurnPhase.SETUP_SOW,
            active_player=next_player,
        )
        events.append(
            GameEvent(
                event_type=EventType.SETUP_PLAYER_ADVANCE,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    from_player=_player_label(player),
                    to_player=_player_label(next_player),
                ),
            )
        )

    ensure_non_negative_resources(next_state)
    validate_building_state(next_state, config)
    ensure_valid_timing(next_state)
    ensure_valid_dummy_state(next_state)
    ensure_valid_special_activities_state(next_state)
    ensure_valid_setup_state(next_state)
    ensure_acolyte_conservation(state, next_state)
    ensure_dummy_acolyte_conservation(state, next_state)
    events.append(
        GameEvent(
            event_type=EventType.INVARIANT_CHECK,
            actor=player,
            action_id=transition_action_id,
            details=make_event_details(
                name="post_setup_sow",
                acolytes_conserved=True,
                serfs_non_negative=True,
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
        duty_category = config.duty_category_for_position(action.selected_duty)
        events.append(
            GameEvent(
                event_type=EventType.DUTY_RESOLUTION,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    duty_position=action.selected_duty,
                    duty_category=duty_category,
                    mode="tithe",
                    recall=False,
                ),
            )
        )
    else:
        duty_category = config.duty_category_for_position(action.selected_duty)
        allowed_resolutions = action_options_for_duty_category(duty_category)
        if action.resolution not in allowed_resolutions:
            message = (
                f"Selected action {action.resolution.value} does not match "
                f"duty category {duty_category}."
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
        special_bonus_events: list[GameEvent] = []
        building_bonus_events: list[GameEvent] = []
        building_hired_events: list[GameEvent] = []
        construct_events: list[GameEvent] = []
        effective_duty_value = duty_value
        give_alms_resolution = None
        donate_building_alms_resolution = None
        alms_payment_actual_silver: int | None = None
        alms_payment_actual_wheat: int | None = None
        duty_deferred_event: GameEvent | None = None
        updated_building_market = state_after_sow.building_market
        state_after_resolution: GameState | None = None

        if (
            action.resolution is not TurnResolutionType.GIVE_ALMS_PAID
            and (
                action.alms_payment_silver != 0
                or action.alms_payment_wheat != 0
                or action.alms_house_extra_silver != 0
                or action.alms_house_extra_wheat != 0
            )
        ):
            raise TransitionValidationError(
                "Only Give Alms actions may include Alms payment fields."
            )
        if (
            action.resolution is not TurnResolutionType.GIVE_ALMS_DONATE_BUILDING
            and action.donate_building_id is not None
        ):
            raise TransitionValidationError(
                "Only give_alms_donate_building actions may include donate_building_id."
            )
        if action.resolution is not TurnResolutionType.ORDINATION and action.ordination_steps:
            raise TransitionValidationError(
                "Only ordination actions may include ordination_steps."
            )
        if (
            action.resolution is not TurnResolutionType.TAXATION
            and (
                action.taxation_step1_resource is not None
                or action.taxation_step2_resources
            )
        ):
            raise TransitionValidationError(
                "Only taxation actions may include taxation_step1_resource/taxation_step2_resources."
            )
        if action.resolution is not TurnResolutionType.ALLOCATION and action.allocation_moves:
            raise TransitionValidationError("Only Allocation actions may set allocation_moves.")
        if (
            action.resolution
            not in (
                TurnResolutionType.CONSTRUCT_ROAD_DEFERRED,
                TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
            )
            and action.construct_plan is not None
        ):
            raise TransitionValidationError(
                "Only Construct road-plan actions may include construct_plan."
            )
        if (
            action.resolution
            not in (
                TurnResolutionType.CONSTRUCT_BUILDING,
                TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
            )
            and action.construct_building_id is not None
        ):
            raise TransitionValidationError(
                "Only Construct building actions may include construct_building_id."
            )
        if (action.hired_building_id is None) != (action.hired_building_source is None):
            raise TransitionValidationError(
                "hired_building_id and hired_building_source must be set together."
            )
        if action.hired_building_id is not None:
            allowed_hire_buildings = _HIRED_BUILDINGS_BY_ACTION.get(action.resolution)
            if allowed_hire_buildings is None:
                raise TransitionValidationError(
                    "This action cannot include hired building fields."
                )
            if action.hired_building_id not in allowed_hire_buildings:
                expected_buildings = ", ".join(sorted(allowed_hire_buildings))
                raise TransitionValidationError(
                    "hired_building_id does not match action resolution expected building(s): "
                    f"{expected_buildings}."
                )
            hire_context = BuildingHireTurnContext()
            if not can_hire_building_this_turn(
                hire_context,
                building_key=action.hired_building_id,
            ):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=action.hired_building_id,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            if not validate_hire_sequence_for_turn(hire_context.hired_buildings):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )

        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID:
            required_mill_wheat = action.alms_payment_wheat + action.alms_house_extra_wheat
            mill_source = _resolved_mill_source_for_action(
                state=state_after_sow,
                config=config,
                player=player,
                action=action,
                required_wheat=required_mill_wheat,
                silver_cost=silver_cost,
                additional_silver_cost=action.alms_payment_silver + action.alms_house_extra_silver,
            )
            mill_waiver = mill_wheat_waiver(required_mill_wheat) if mill_source is not None else 0
            mill_actual_wheat_spent = (
                mill_actual_wheat_cost(required_mill_wheat)
                if mill_source is not None
                else required_mill_wheat
            )
            alms_payment_actual_silver = action.alms_payment_silver
            alms_payment_actual_wheat = action.alms_payment_wheat
            if mill_waiver:
                credited_wheat_waiver = min(action.alms_payment_wheat, mill_waiver)
                alms_payment_actual_wheat = action.alms_payment_wheat - credited_wheat_waiver
            state_for_give_alms = state_after_sow
            if mill_source is not None and _is_hired_source(mill_source):
                try:
                    state_for_give_alms, hire_payment = apply_building_hire_payment(
                        state_for_give_alms,
                        acting_player=player,
                        source=mill_source,
                    )
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                building_hired_events.append(
                    _building_hired_event(
                        source=mill_source,
                        payment=hire_payment,
                        actor=player,
                        action_id=transition_action_id,
                        config=config,
                    )
                )
            alms_house_bonus = action.alms_house_extra_silver + action.alms_house_extra_wheat
            use_alms_house = (
                action.alms_house_extra_silver != 0 or action.alms_house_extra_wheat != 0
            )
            if use_alms_house:
                if not can_use_alms_house_bonus(state_after_sow.player_state(player)):
                    raise TransitionValidationError("Alms House is not occupied for this player.")
                alms_house_bonus_cap = alms_house_duty_value_bonus_capacity(
                    state_after_sow.player_state(player)
                )
                if alms_house_bonus <= 0 or alms_house_bonus > alms_house_bonus_cap:
                    raise TransitionValidationError(
                        "Alms House extra payment exceeds occupied Alms House capacity."
                    )
                current_resources = state_for_give_alms.player_state(player).resources
                resources_for_extra_validation = current_resources
                if mill_waiver:
                    resources_for_extra_validation = resources_for_extra_validation.add(
                        wheat=mill_waiver
                    )
                valid_extra_options = alms_house_extra_payment_options(
                    resources_for_extra_validation,
                    max_bonus=alms_house_bonus_cap,
                )
                if (action.alms_house_extra_silver, action.alms_house_extra_wheat) not in (
                    valid_extra_options
                ):
                    raise TransitionValidationError(
                        "Alms House extra payment does not match a legal payment combination."
                    )
                effective_duty_value += alms_house_bonus
                if (
                    current_resources.silver
                    < silver_cost + action.alms_payment_silver + action.alms_house_extra_silver
                ):
                    raise TransitionValidationError(
                        "Insufficient silver for minority/alms payment plus Alms House cost."
                    )
                if (
                    current_resources.wheat + mill_waiver
                    < action.alms_payment_wheat + action.alms_house_extra_wheat
                ):
                    raise TransitionValidationError(
                        "Insufficient wheat for alms payment plus Alms House cost."
                    )
            give_alms_player_state = state_for_give_alms.player_state(player)
            if mill_waiver:
                give_alms_player_state = replace(
                    give_alms_player_state,
                    resources=give_alms_player_state.resources.add(wheat=mill_waiver),
                )
            try:
                give_alms_resolution = resolve_give_alms(
                    give_alms_player_state,
                    duty_value=effective_duty_value,
                    payment=AlmsPayment(
                        silver=action.alms_payment_silver,
                        wheat=action.alms_payment_wheat,
                    ),
                    minority_silver_cost=silver_cost,
                    config=config.alms,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            new_player_state = give_alms_resolution.player_state
            if use_alms_house:
                new_resources = new_player_state.resources.add(
                    silver=-action.alms_house_extra_silver,
                    wheat=-action.alms_house_extra_wheat,
                )
                if new_resources.silver < 0 or new_resources.wheat < 0:
                    raise TransitionValidationError(
                        "Alms House extra payment would overdraw resources."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            activity="alms_house",
                            action=action.resolution.value,
                            duty_value_bonus=alms_house_bonus,
                            extra_silver=action.alms_house_extra_silver,
                            extra_wheat=action.alms_house_extra_wheat,
                        ),
                    )
                )
            if mill_waiver:
                building_bonus_events.append(
                    GameEvent(
                        event_type=EventType.BUILDING_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            building="mill",
                            action=action.resolution.value,
                            wheat_waived=mill_waiver,
                            required_wheat=required_mill_wheat,
                            actual_wheat_spent=mill_actual_wheat_spent,
                        ),
                    )
                )
            state_after_resolution = state_for_give_alms.with_player_state(player, new_player_state)
            resource_delta = _resource_delta_between(
                state_after_sow.player_state(player).resources,
                new_player_state.resources,
            )
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
        elif action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING:
            if not action.donate_building_id:
                raise TransitionValidationError(
                    "give_alms_donate_building action requires donate_building_id."
                )

            try:
                donated_player_state, donated_building = donate_active_building(
                    state_after_sow.player_state(player),
                    building_id=action.donate_building_id,
                    config=config,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc

            if silver_cost:
                resources_after_silver_cost = donated_player_state.resources.add(
                    silver=-silver_cost
                )
                if resources_after_silver_cost.silver < 0:
                    raise TransitionValidationError(
                        "Donate building minority silver cost would overdraw silver."
                    )
                donated_player_state = replace(
                    donated_player_state,
                    resources=resources_after_silver_cost,
                )

            try:
                donate_building_alms_resolution = resolve_donate_building_alms(
                    donated_player_state,
                    config=config.alms,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc

            new_player_state = donate_building_alms_resolution.player_state
            resource_delta = (0, -silver_cost, 0)
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
            special_bonus_events.append(
                GameEvent(
                    event_type=EventType.BUILDING_DONATION,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(
                        building_id=donated_building.id,
                        building_name=donated_building.name,
                        donation_vp=donated_building.donation_vp,
                    ),
                )
            )
        elif action.resolution is TurnResolutionType.BUILD_ROADS_DEFERRED:
            road_engineer_bonus = road_engineer_duty_value_bonus_hook(
                state_after_sow.player_state(player),
                action_key="build_roads",
            )
            effective_duty_value += road_engineer_bonus
            if road_engineer_bonus:
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            activity="road_engineer",
                            action=action.resolution.value,
                            duty_value_bonus=road_engineer_bonus,
                        ),
                    )
                )

            new_player_state = state_after_sow.player_state(player)
            if silver_cost:
                new_resources = new_player_state.resources.add(silver=-silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Build Roads minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            resource_delta = (0, -silver_cost, 0)
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
            duty_deferred_event = GameEvent(
                event_type=EventType.DUTY_DEFERRED,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    duty_category="build_roads",
                    scaffold=(
                        "build_roads requires spatial road/shrine system; options are "
                        "build road/bridge/ford/shrine, upgrade road/bridge, "
                        "demolish road/bridge"
                    ),
                    effective_duty_value=effective_duty_value,
                    spent=False,
                ),
            )
        elif action.resolution is TurnResolutionType.CONSTRUCT_ROAD_DEFERRED:
            if not action.construct_plan:
                raise TransitionValidationError("Construct action requires construct_plan.")
            road_engineer_extra_roads = road_engineer_construct_extra_roads_bonus(
                state_after_sow.player_state(player),
            )
            allowed_construct_plans = _construct_road_only_plans(
                duty_value=duty_value,
                road_engineer_extra_roads=road_engineer_extra_roads,
            )
            if action.construct_plan not in allowed_construct_plans:
                raise TransitionValidationError(
                    "Illegal construct road plan for current duty value/special-activity state."
                )

            new_player_state = state_after_sow.player_state(player)
            if silver_cost:
                new_resources = new_player_state.resources.add(silver=-silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Construct minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            construct_extra_roads = _construct_plan_extra_road_count(action.construct_plan)
            if construct_extra_roads:
                bonus_details = {
                    "activity": "road_engineer",
                    "action": action.resolution.value,
                    "construct_extra_roads": construct_extra_roads,
                    "reason": "road included in plan",
                }
                if construct_extra_roads == 1:
                    bonus_details["construct_extra_road"] = True
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(**bonus_details),
                    )
                )

            resource_delta = (0, -silver_cost, 0)
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
            duty_deferred_event = GameEvent(
                event_type=EventType.DUTY_DEFERRED,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    duty_category="construct",
                    scaffold=(
                        f"{_CONSTRUCT_ROAD_SCAFFOLD_TEXT}; "
                        f"requested plan: {action.construct_plan}"
                    ),
                ),
            )
        elif action.resolution is TurnResolutionType.CONSTRUCT_BUILDING:
            if not action.construct_building_id:
                raise TransitionValidationError(
                    "construct_building action requires construct_building_id."
                )
            if not is_building_live(state_after_sow, action.construct_building_id):
                live_round = building_live_round(state_after_sow, action.construct_building_id)
                raise TransitionValidationError(
                    "construct_building action requires a live market building: "
                    f"{action.construct_building_id} "
                    f"(round {state_after_sow.round_number}; live round {live_round})."
                )

            new_player_state = state_after_sow.player_state(player)
            if silver_cost:
                new_resources = new_player_state.resources.add(silver=-silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Construct minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            try:
                (
                    new_player_state,
                    updated_building_market,
                    constructed_building,
                ) = construct_building_from_market(
                    new_player_state,
                    building_id=action.construct_building_id,
                    building_market=updated_building_market,
                    config=config,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc

            stone_cost = constructed_building.stone_cost
            resource_delta = (-stone_cost, -silver_cost, 0)
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
            construct_events.append(
                GameEvent(
                    event_type=EventType.BUILDING_CONSTRUCTED,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(
                        building_id=constructed_building.id,
                        building_name=constructed_building.name,
                        level=constructed_building.level,
                        stone_cost=stone_cost,
                        source="market",
                        active_buildings_count=len(
                            new_player_state.player_board_slots.active_buildings
                        ),
                        used_slots=used_player_board_slots(new_player_state),
                        slot_limit=config.buildings.player_board.building_and_cardinal_slot_limit,
                    ),
                )
            )
        elif action.resolution is TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED:
            if not action.construct_building_id:
                raise TransitionValidationError(
                    "construct_building_and_road_deferred requires construct_building_id."
                )
            if not is_building_live(state_after_sow, action.construct_building_id):
                live_round = building_live_round(state_after_sow, action.construct_building_id)
                raise TransitionValidationError(
                    "construct_building_and_road_deferred requires a live market building: "
                    f"{action.construct_building_id} "
                    f"(round {state_after_sow.round_number}; live round {live_round})."
                )
            if not action.construct_plan:
                raise TransitionValidationError(
                    "construct_building_and_road_deferred requires construct_plan."
                )
            if duty_value < 2:
                raise TransitionValidationError(
                    "construct_building_and_road_deferred requires duty value >= 2."
                )

            road_engineer_extra_roads = road_engineer_construct_extra_roads_bonus(
                state_after_sow.player_state(player),
            )
            allowed_construct_plans = _construct_building_plus_road_plans(
                duty_value=duty_value,
                road_engineer_extra_roads=road_engineer_extra_roads,
            )
            if action.construct_plan not in allowed_construct_plans:
                raise TransitionValidationError(
                    "Illegal construct road plan for building+road action."
                )

            new_player_state = state_after_sow.player_state(player)
            if silver_cost:
                new_resources = new_player_state.resources.add(silver=-silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Construct minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            try:
                (
                    new_player_state,
                    updated_building_market,
                    constructed_building,
                ) = construct_building_from_market(
                    new_player_state,
                    building_id=action.construct_building_id,
                    building_market=updated_building_market,
                    config=config,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc

            stone_cost = constructed_building.stone_cost
            construct_extra_roads = _construct_plan_extra_road_count(action.construct_plan)
            if construct_extra_roads:
                bonus_details = {
                    "activity": "road_engineer",
                    "action": action.resolution.value,
                    "construct_extra_roads": construct_extra_roads,
                    "reason": "road included in plan",
                }
                if construct_extra_roads == 1:
                    bonus_details["construct_extra_road"] = True
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(**bonus_details),
                    )
                )

            resource_delta = (-stone_cost, -silver_cost, 0)
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
            construct_events.append(
                GameEvent(
                    event_type=EventType.BUILDING_CONSTRUCTED,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(
                        building_id=constructed_building.id,
                        building_name=constructed_building.name,
                        level=constructed_building.level,
                        stone_cost=stone_cost,
                        source="market",
                        active_buildings_count=len(
                            new_player_state.player_board_slots.active_buildings
                        ),
                        used_slots=used_player_board_slots(new_player_state),
                        slot_limit=config.buildings.player_board.building_and_cardinal_slot_limit,
                    ),
                )
            )
            duty_deferred_event = GameEvent(
                event_type=EventType.DUTY_DEFERRED,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    duty_category="construct",
                    scaffold=(
                        f"{_CONSTRUCT_ROAD_SCAFFOLD_TEXT}; "
                        f"requested plan: {action.construct_plan}"
                    ),
                ),
            )
        elif action.resolution is TurnResolutionType.ORDINATION:
            if not action.ordination_steps:
                raise TransitionValidationError(
                    "Ordination action must include at least 1 ordination step."
                )
            required_mill_wheat = len(action.ordination_steps)
            mill_source = _resolved_mill_source_for_action(
                state=state_after_sow,
                config=config,
                player=player,
                action=action,
                required_wheat=required_mill_wheat,
                silver_cost=silver_cost,
            )
            mill_waiver = mill_wheat_waiver(required_mill_wheat) if mill_source is not None else 0
            mill_actual_wheat_spent = (
                mill_actual_wheat_cost(required_mill_wheat)
                if mill_source is not None
                else required_mill_wheat
            )
            ordination_source = _resolved_infirmary_source_for_action(
                state=state_after_sow,
                config=config,
                player=player,
                action=action,
                duty_value=duty_value,
                silver_cost=silver_cost,
                ordination_wheat_cost=mill_actual_wheat_spent,
                mode="ordination",
            )
            ordination_cap_bonus = 1 if ordination_source is not None else 0
            max_ordination_steps = duty_value + ordination_cap_bonus
            if len(action.ordination_steps) > max_ordination_steps:
                raise TransitionValidationError(
                    "Ordination action includes more steps than effective duty value allows."
                )
            ordination_bonus = 1 if len(action.ordination_steps) > duty_value else 0
            if ordination_bonus:
                effective_duty_value += ordination_bonus
                building_bonus_events.append(
                    GameEvent(
                        event_type=EventType.BUILDING_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            building="infirmary",
                            action=action.resolution.value,
                            duty_value_bonus=ordination_bonus,
                            extra_wheat_cost_paid=True,
                        ),
                    )
                )
            if mill_waiver:
                building_bonus_events.append(
                    GameEvent(
                        event_type=EventType.BUILDING_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            building="mill",
                            action=action.resolution.value,
                            wheat_waived=mill_waiver,
                            required_wheat=required_mill_wheat,
                            actual_wheat_spent=mill_actual_wheat_spent,
                        ),
                    )
                )

            state_for_ordination = state_after_sow
            new_player_state = state_for_ordination.player_state(player)
            hired_ordination_source = None
            if ordination_source is not None and _is_hired_source(ordination_source):
                hired_ordination_source = ordination_source
            elif mill_source is not None and _is_hired_source(mill_source):
                hired_ordination_source = mill_source
            if hired_ordination_source is not None:
                try:
                    state_for_ordination, hire_payment = apply_building_hire_payment(
                        state_for_ordination,
                        acting_player=player,
                        source=hired_ordination_source,
                    )
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                new_player_state = state_for_ordination.player_state(player)
                building_hired_events.append(
                    _building_hired_event(
                        source=hired_ordination_source,
                        payment=hire_payment,
                        actor=player,
                        action_id=transition_action_id,
                        config=config,
                    )
                )
            if mill_waiver:
                new_player_state = replace(
                    new_player_state,
                    resources=new_player_state.resources.add(wheat=mill_waiver),
                )
            remaining_mill_waiver = mill_waiver
            for step in action.ordination_steps:
                wheat_paid = 0 if remaining_mill_waiver > 0 else 1
                try:
                    new_player_state = apply_ordination_step(new_player_state, step)
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                if remaining_mill_waiver > 0:
                    remaining_mill_waiver -= 1
                if step == ORDINATION_ORDAIN:
                    special_bonus_events.append(
                        GameEvent(
                            event_type=EventType.ORDINATION,
                            actor=player,
                            action_id=transition_action_id,
                            details=make_event_details(
                                step=ORDINATION_ORDAIN,
                                from_pool="village",
                                to_pool="abbey",
                                unit="serf",
                                amount=1,
                                wheat_paid=wheat_paid,
                            ),
                        )
                    )
                elif step == ORDINATION_MISSION:
                    special_bonus_events.append(
                        GameEvent(
                            event_type=EventType.ORDINATION,
                            actor=player,
                            action_id=transition_action_id,
                            details=make_event_details(
                                step=ORDINATION_MISSION,
                                from_pool="abbey",
                                to_pool="city",
                                unit="acolyte",
                                amount=1,
                                wheat_paid=wheat_paid,
                            ),
                        )
                    )
                else:
                    raise TransitionValidationError(f"Unknown ordination step: {step}")

            if silver_cost:
                new_resources = new_player_state.resources.add(silver=-silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Ordination minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            state_after_resolution = state_for_ordination.with_player_state(player, new_player_state)
            resource_delta = _resource_delta_between(
                state_after_sow.player_state(player).resources,
                new_player_state.resources,
            )
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
        elif action.resolution is TurnResolutionType.TAXATION:
            step_1_resource = action.taxation_step1_resource
            if step_1_resource not in _TAXATION_RESOURCE_TYPES:
                raise TransitionValidationError(
                    "Taxation action requires taxation_step1_resource in: "
                    + ", ".join(_TAXATION_RESOURCE_TYPES)
                    + "."
                )

            bonus_resource_types = _taxation_bonus_resource_types(
                state,
                config,
                player=player,
                sowed_vector=sowed_vector,
                selected_duty=action.selected_duty,
            )
            legal_step_2_choices = _taxation_bonus_resource_choices(
                bonus_resource_types,
                duty_value=effective_duty_value,
            )
            step_2_resources = tuple(action.taxation_step2_resources)
            if step_2_resources not in legal_step_2_choices:
                raise TransitionValidationError(
                    "Illegal taxation_step2_resources for current majority tiles and duty value."
                )

            stone_delta = 0
            silver_delta = -silver_cost
            wheat_delta = 0

            for resource in (step_1_resource, *step_2_resources):
                if resource == "stone":
                    stone_delta += 1
                elif resource == "silver":
                    silver_delta += 1
                elif resource == "wheat":
                    wheat_delta += 1
                else:
                    raise TransitionValidationError(f"Unknown taxation resource: {resource}")

            new_player_state = state_after_sow.player_state(player)
            new_resources = new_player_state.resources.add(
                stone=stone_delta,
                silver=silver_delta,
                wheat=wheat_delta,
            )
            if (
                new_resources.stone < 0
                or new_resources.silver < 0
                or new_resources.wheat < 0
            ):
                raise TransitionValidationError("Taxation resource update cannot overdraw resources.")
            new_player_state = replace(new_player_state, resources=new_resources)

            special_bonus_events.append(
                GameEvent(
                    event_type=EventType.TAXATION,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(
                        step="step_1",
                        resource=step_1_resource,
                    ),
                )
            )
            if step_2_resources:
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.TAXATION,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            step="step_2",
                            resources=",".join(step_2_resources),
                            no_bonus=False,
                        ),
                    )
                )
            else:
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.TAXATION,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            step="step_2",
                            resources="",
                            no_bonus=True,
                        ),
                    )
                )

            resource_delta = (stone_delta, silver_delta, wheat_delta)
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
        elif action.resolution is TurnResolutionType.ALLOCATION:
            chapter_house_active = player_has_active_chapter_house(
                state_after_sow.player_state(player)
            )
            allocation_special_activity_capacity = special_activity_capacity(
                chapter_house_active=chapter_house_active
            )
            allocation_source = _resolved_infirmary_source_for_action(
                state=state_after_sow,
                config=config,
                player=player,
                action=action,
                duty_value=duty_value,
                silver_cost=silver_cost,
                mode="allocation",
            )
            allocation_bonus = 1 if allocation_source is not None else 0
            if allocation_bonus:
                effective_duty_value += allocation_bonus
                building_bonus_events.append(
                    GameEvent(
                        event_type=EventType.BUILDING_BONUS,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            building="infirmary",
                            action=action.resolution.value,
                            duty_value_bonus=allocation_bonus,
                        ),
                    )
                )
            if not action.allocation_moves:
                raise TransitionValidationError(
                    "Allocation action must include at least 1 allocation move."
                )
            if len(action.allocation_moves) > effective_duty_value:
                raise TransitionValidationError(
                    "Allocation action includes more moves than effective duty value allows."
                )

            state_for_allocation = state_after_sow
            new_player_state = state_for_allocation.player_state(player)
            if allocation_source is not None and _is_hired_source(allocation_source):
                try:
                    state_for_allocation, hire_payment = apply_building_hire_payment(
                        state_for_allocation,
                        acting_player=player,
                        source=allocation_source,
                    )
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                new_player_state = state_for_allocation.player_state(player)
                building_hired_events.append(
                    _building_hired_event(
                        source=allocation_source,
                        payment=hire_payment,
                        actor=player,
                        action_id=transition_action_id,
                        config=config,
                    )
                )
            for move in action.allocation_moves:
                destination_activity: str | None = None
                destination_count_before = 0
                if move.destination in SPECIAL_ACTIVITY_IDS:
                    destination_activity = move.destination
                    destination_count_before = special_activity_count(
                        new_player_state,
                        destination_activity,
                    )
                try:
                    new_player_state = apply_allocation_move_with_capacity(
                        new_player_state,
                        move,
                        capacity=allocation_special_activity_capacity,
                    )
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                if (
                    chapter_house_active
                    and destination_activity is not None
                    and destination_count_before >= 1
                    and special_activity_count(new_player_state, destination_activity) >= 2
                ):
                    building_bonus_events.append(
                        GameEvent(
                            event_type=EventType.BUILDING_BONUS,
                            actor=player,
                            action_id=transition_action_id,
                            details=make_event_details(
                                building="chapter_house",
                                action=action.resolution.value,
                                activity=destination_activity,
                                capacity=allocation_special_activity_capacity,
                                second_acolyte=True,
                            ),
                        )
                    )
                special_bonus_events.append(
                    GameEvent(
                        event_type=EventType.ALLOCATION,
                        actor=player,
                        action_id=transition_action_id,
                        details=make_event_details(
                            from_pool=move.source,
                            to_pool=move.destination,
                            amount=1,
                        ),
                    )
                )

            if silver_cost:
                new_resources = new_player_state.resources.add(silver=-silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Allocation minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            state_after_resolution = state_for_allocation.with_player_state(player, new_player_state)
            resource_delta = _resource_delta_between(
                state_after_sow.player_state(player).resources,
                new_player_state.resources,
            )
            old_piety_position = state_after_sow.player_state(player).piety
            new_piety_position = state_after_sow.player_state(player).piety
        else:
            if action.resolution in (
                TurnResolutionType.PRODUCE_WHEAT,
                TurnResolutionType.PRODUCE_STONE,
            ):
                produce_resource_bonus = 0
                selected_simple_source: BuildingAbilitySource | None = None
                if action.resolution is TurnResolutionType.PRODUCE_WHEAT:
                    wheat_bonus = produce_wheat_fields_bonus(state_after_sow.player_state(player))
                    produce_resource_bonus += wheat_bonus
                    if wheat_bonus:
                        special_bonus_events.append(
                            GameEvent(
                                event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    activity="fields",
                                    action=action.resolution.value,
                                    wheat_bonus=wheat_bonus,
                                ),
                            )
                        )
                    selected_simple_source = _resolved_simple_bonus_source_for_action(
                        state=state_after_sow,
                        config=config,
                        player=player,
                        action=action,
                        building_key="well",
                    )
                    if selected_simple_source is not None:
                        produce_resource_bonus += 1
                        building_bonus_events.append(
                            GameEvent(
                                event_type=EventType.BUILDING_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    building="well",
                                    action=action.resolution.value,
                                    wheat_bonus=1,
                                ),
                            )
                        )
                else:
                    stone_bonus = produce_stone_mason_bonus(
                        state_after_sow.player_state(player)
                    )
                    produce_resource_bonus += stone_bonus
                    if stone_bonus:
                        special_bonus_events.append(
                            GameEvent(
                                event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    activity="stone_mason",
                                    action=action.resolution.value,
                                    stone_bonus=stone_bonus,
                                ),
                            )
                        )
                    selected_simple_source = _resolved_simple_bonus_source_for_action(
                        state=state_after_sow,
                        config=config,
                        player=player,
                        action=action,
                        building_key="quarry",
                    )
                    if selected_simple_source is not None:
                        produce_resource_bonus += 1
                        building_bonus_events.append(
                            GameEvent(
                                event_type=EventType.BUILDING_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    building="quarry",
                                    action=action.resolution.value,
                                    stone_bonus=1,
                                ),
                            )
                        )
                try:
                    new_player_state, _produce_resource_delta = apply_produce_resolution(
                        state_after_sow.player_state(player),
                        resolution=action.resolution,
                        duty_value=duty_value + produce_resource_bonus,
                        silver_cost=silver_cost,
                    )
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                old_piety_position = state_after_sow.player_state(player).piety
                new_piety_position = state_after_sow.player_state(player).piety
                state_after_resolution = state_after_sow.with_player_state(player, new_player_state)
                if selected_simple_source is not None and _is_hired_source(selected_simple_source):
                    try:
                        state_after_resolution, hire_payment = apply_building_hire_payment(
                            state_after_resolution,
                            acting_player=player,
                            source=selected_simple_source,
                        )
                    except ValueError as exc:
                        raise TransitionValidationError(str(exc)) from exc
                    new_player_state = state_after_resolution.player_state(player)
                    building_hired_events.append(
                        _building_hired_event(
                            source=selected_simple_source,
                            payment=hire_payment,
                            actor=player,
                            action_id=transition_action_id,
                            config=config,
                        )
                    )
                resource_delta = _resource_delta_between(
                    state_after_sow.player_state(player).resources,
                    new_player_state.resources,
                )
            else:
                clerical_output_bonus = 0
                selected_simple_source = None
                if action.resolution is TurnResolutionType.CLERICAL_SILVERSMITH:
                    bonus = clerical_silversmith_bonus(state_after_sow.player_state(player))
                    clerical_output_bonus += bonus
                    if bonus:
                        special_bonus_events.append(
                            GameEvent(
                                event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    activity="engraver",
                                    action=action.resolution.value,
                                    silver_bonus=bonus,
                                ),
                            )
                        )
                    selected_simple_source = _resolved_simple_bonus_source_for_action(
                        state=state_after_sow,
                        config=config,
                        player=player,
                        action=action,
                        building_key="mint",
                    )
                    if selected_simple_source is not None:
                        clerical_output_bonus += 1
                        building_bonus_events.append(
                            GameEvent(
                                event_type=EventType.BUILDING_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    building="mint",
                                    action=action.resolution.value,
                                    silver_bonus=1,
                                ),
                            )
                        )
                elif action.resolution is TurnResolutionType.CLERICAL_DEVOTION:
                    bonus = clerical_devotion_bonus(state_after_sow.player_state(player))
                    clerical_output_bonus += bonus
                    if bonus:
                        special_bonus_events.append(
                            GameEvent(
                                event_type=EventType.SPECIAL_ACTIVITY_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    activity="vestry",
                                    action=action.resolution.value,
                                    piety_bonus=bonus,
                                ),
                            )
                        )
                    selected_simple_source = _resolved_simple_bonus_source_for_action(
                        state=state_after_sow,
                        config=config,
                        player=player,
                        action=action,
                        building_key="chapel",
                    )
                    if selected_simple_source is not None:
                        clerical_output_bonus += 1
                        building_bonus_events.append(
                            GameEvent(
                                event_type=EventType.BUILDING_BONUS,
                                actor=player,
                                action_id=transition_action_id,
                                details=make_event_details(
                                    building="chapel",
                                    action=action.resolution.value,
                                    piety_bonus=1,
                                ),
                            )
                        )
                try:
                    (
                        new_player_state,
                        resource_delta,
                        old_piety_position,
                        new_piety_position,
                    ) = apply_duty_effect(
                        state_after_sow.player_state(player),
                        effect=effect_for_resolution(action.resolution),
                        duty_value=duty_value + clerical_output_bonus,
                        silver_cost=silver_cost,
                        piety_config=config.piety,
                    )
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                state_after_resolution = state_after_sow.with_player_state(player, new_player_state)
                if selected_simple_source is not None and _is_hired_source(selected_simple_source):
                    try:
                        state_after_resolution, hire_payment = apply_building_hire_payment(
                            state_after_resolution,
                            acting_player=player,
                            source=selected_simple_source,
                        )
                    except ValueError as exc:
                        raise TransitionValidationError(str(exc)) from exc
                    new_player_state = state_after_resolution.player_state(player)
                    building_hired_events.append(
                        _building_hired_event(
                            source=selected_simple_source,
                            payment=hire_payment,
                            actor=player,
                            action_id=transition_action_id,
                            config=config,
                        )
                    )
                resource_delta = _resource_delta_between(
                    state_after_sow.player_state(player).resources,
                    new_player_state.resources,
                )

        if state_after_resolution is None:
            state_after_resolution = state_after_sow.with_player_state(player, new_player_state)
        new_player_state = state_after_resolution.player_state(player)
        post_effect_vector = new_player_state.workforce.mancala
        recalled = post_effect_vector[action.selected_duty]
        recalled_vector = list(post_effect_vector)
        recalled_vector[0] += recalled
        recalled_vector[action.selected_duty] = 0

        updated_state = state_after_resolution
        updated_state = updated_state.with_player_vector(player, tuple(recalled_vector))
        updated_state = updated_state.with_building_market(updated_building_market)

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
                    duty_category=duty_category,
                    strength=strength.value,
                    duty_value=duty_value,
                    effective_duty_value=effective_duty_value,
                    silver_cost=silver_cost,
                    effect=action.resolution.value,
                ),
            )
        )
        duty_value_building_bonus_events = [
            event for event in building_bonus_events if _is_duty_value_building_bonus_event(event)
        ]
        allocation_capacity_building_bonus_events = [
            event
            for event in building_bonus_events
            if _is_allocation_capacity_building_bonus_event(event)
        ]
        output_building_bonus_events = [
            event
            for event in building_bonus_events
            if (
                not _is_duty_value_building_bonus_event(event)
                and not _is_allocation_capacity_building_bonus_event(event)
            )
        ]
        events.extend(building_hired_events)
        events.extend(duty_value_building_bonus_events)
        events.extend(allocation_capacity_building_bonus_events)
        events.extend(output_building_bonus_events)
        events.extend(special_bonus_events)
        if duty_deferred_event is not None and not construct_events:
            events.append(duty_deferred_event)
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
        events.extend(construct_events)
        if duty_deferred_event is not None and construct_events:
            events.append(duty_deferred_event)

        if action.resolution is TurnResolutionType.GIVE_ALMS_PAID:
            if give_alms_resolution is None:
                raise TransitionValidationError("Missing Give Alms resolution payload.")
            alms_payment_details = {
                "silver": action.alms_payment_silver,
                "wheat": action.alms_payment_wheat,
                "minority_silver_cost": silver_cost,
            }
            if (
                alms_payment_actual_silver is not None
                and alms_payment_actual_wheat is not None
                and (
                    alms_payment_actual_silver != action.alms_payment_silver
                    or alms_payment_actual_wheat != action.alms_payment_wheat
                )
            ):
                alms_payment_details.update(
                    {
                        "credited_silver": action.alms_payment_silver,
                        "credited_wheat": action.alms_payment_wheat,
                        "actual_paid_silver": alms_payment_actual_silver,
                        "actual_paid_wheat": alms_payment_actual_wheat,
                    }
                )
            events.append(
                GameEvent(
                    event_type=EventType.ALMS_PAYMENT,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(**alms_payment_details),
                )
            )
            events.append(
                GameEvent(
                    event_type=EventType.ALMS_PROGRESS,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(
                        old_row=give_alms_resolution.old_position,
                        new_row=give_alms_resolution.new_position,
                    ),
                )
            )
            for outcome in give_alms_resolution.threshold_outcomes:
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
        elif action.resolution is TurnResolutionType.GIVE_ALMS_DONATE_BUILDING:
            if donate_building_alms_resolution is None:
                raise TransitionValidationError(
                    "Missing give_alms_donate_building Alms resolution payload."
                )
            events.append(
                GameEvent(
                    event_type=EventType.ALMS_PROGRESS,
                    actor=player,
                    action_id=transition_action_id,
                    details=make_event_details(
                        old_row=donate_building_alms_resolution.old_position,
                        new_row=donate_building_alms_resolution.new_position,
                    ),
                )
            )
            for outcome in donate_building_alms_resolution.threshold_outcomes:
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
    ensure_valid_special_activities_state(next_state)
    ensure_valid_setup_state(next_state)
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
                serfs_non_negative=True,
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


def _player_label(player: PlayerId) -> str:
    if player is PlayerId.PLAYER_ONE:
        return "player_one"
    return "player_two"


def _next_incomplete_setup_player(
    state: GameState,
    *,
    current_player: PlayerId,
    completed_by: tuple[PlayerId, ...],
) -> PlayerId | None:
    turn_order = tuple(PlayerId(index) for index in range(state.player_count))
    completed_set = set(completed_by)
    if set(turn_order).issubset(completed_set):
        return None
    current_index = turn_order.index(current_player)
    for offset in range(1, len(turn_order) + 1):
        candidate = turn_order[(current_index + offset) % len(turn_order)]
        if candidate not in completed_set:
            return candidate
    return None


def _legal_action_variants_for_resolution(
    *,
    state: GameState,
    config: GameConfig,
    origin: int,
    route: tuple[int, ...],
    selected_duty: int,
    resolution: TurnResolutionType,
) -> tuple[FullTurnAction, ...]:
    """Return deterministic action variants for one duty-resolution option."""
    building_key = _SIMPLE_BONUS_BUILDING_BY_ACTION.get(resolution)
    if building_key is None:
        return (
            FullTurnAction(
                origin=origin,
                route=route,
                selected_duty=selected_duty,
                resolution=resolution,
            ),
        )

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=building_key,
    )
    if source.source_type in ("live_market_hire", "opponent_active_hire") and source.usable:
        hire_context = BuildingHireTurnContext()
        if not can_hire_building_this_turn(hire_context, building_key=building_key):
            return (
                FullTurnAction(
                    origin=origin,
                    route=route,
                    selected_duty=selected_duty,
                    resolution=resolution,
                ),
            )
        hire_context = record_hired_building_this_turn(
            hire_context,
            building_key=building_key,
        )
        if not validate_hire_sequence_for_turn(hire_context.hired_buildings):
            return (
                FullTurnAction(
                    origin=origin,
                    route=route,
                    selected_duty=selected_duty,
                    resolution=resolution,
                ),
            )
        return (
            FullTurnAction(
                origin=origin,
                route=route,
                selected_duty=selected_duty,
                resolution=resolution,
                hired_building_id=hire_context.hired_buildings[0],
                hired_building_source=_hired_building_source_label(source),
            ),
        )

    # own_active uses the free source without a dedicated hire suffix.
    return (
        FullTurnAction(
            origin=origin,
            route=route,
            selected_duty=selected_duty,
            resolution=resolution,
        ),
    )


def _resolved_simple_bonus_source_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
    building_key: str,
) -> BuildingAbilitySource | None:
    """Resolve and validate simple building-bonus source against action hire fields."""
    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=building_key,
    )
    action_has_hire_fields = action.hired_building_id is not None

    if source.source_type == "own_active" and source.usable:
        if action_has_hire_fields:
            raise TransitionValidationError(
                f"{building_key} is own-active; action must not include hired building fields."
            )
        return source

    if source.source_type in ("live_market_hire", "opponent_active_hire") and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if not action_has_hire_fields:
            raise TransitionValidationError(
                f"{building_key} is hire-usable; action must include hired building fields."
            )
        if action.hired_building_id != building_key:
            raise TransitionValidationError(
                f"Action hired_building_id must be {building_key} for this resolution."
            )
        if action.hired_building_source != expected_source_label:
            raise TransitionValidationError(
                "Action hired_building_source does not match resolved source: "
                f"expected {expected_source_label}."
            )
        return source

    if action_has_hire_fields:
        raise TransitionValidationError(
            f"{building_key} is not hire-usable in current state."
        )
    return None


def _resolved_infirmary_source_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
    duty_value: int,
    silver_cost: int,
    ordination_wheat_cost: int = 0,
    mode: str,
) -> BuildingAbilitySource | None:
    """Resolve/validate Infirmary source for allocation or ordination actions."""
    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key="infirmary",
    )
    action_hires_infirmary = action.hired_building_id == "infirmary"
    uses_infirmary_bonus = False
    if mode == "allocation":
        uses_infirmary_bonus = True
        if action_hires_infirmary:
            uses_infirmary_bonus = len(action.allocation_moves) > duty_value
    elif mode == "ordination":
        uses_infirmary_bonus = len(action.ordination_steps) > duty_value
    else:
        raise TransitionValidationError(f"Unknown infirmary action mode: {mode}.")

    if source.source_type == "own_active" and source.usable:
        if action_hires_infirmary:
            raise TransitionValidationError(
                "Infirmary is own-active; action must not include hired building fields."
            )
        return source if uses_infirmary_bonus else None

    if _is_hired_source(source) and source.usable:
        if not action_hires_infirmary:
            return None
        expected_source_label = _hired_building_source_label(source)
        if action.hired_building_id != "infirmary":
            raise TransitionValidationError(
                "Action hired_building_id must be infirmary for this resolution."
            )
        if action.hired_building_source != expected_source_label:
            raise TransitionValidationError(
                "Action hired_building_source does not match resolved source: "
                f"expected {expected_source_label}."
            )
        if not uses_infirmary_bonus:
            raise TransitionValidationError(
                "Infirmary hire fields are only legal when action uses the extra Infirmary bonus."
            )
        required_wheat = ordination_wheat_cost if mode == "ordination" else 0
        if not _can_afford_resolution_costs(
            state.player_state(player),
            required_silver=silver_cost,
            required_wheat=required_wheat,
            hired_source=source,
        ):
            raise TransitionValidationError(
                "Infirmary hire plus duty costs are not affordable for this action."
            )
        return source

    if action_hires_infirmary:
        raise TransitionValidationError("Infirmary is not hire-usable in current state.")
    return None


def _hired_building_source_label(source: BuildingAbilitySource) -> str:
    if source.source_type == "live_market_hire":
        return "market"
    if source.source_type == "opponent_active_hire":
        return source.owner or "unknown"
    return source.source_type


def _is_hired_source(source: BuildingAbilitySource) -> bool:
    return source.source_type in ("live_market_hire", "opponent_active_hire")


def _resolved_mill_source_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
    required_wheat: int,
    silver_cost: int,
    additional_silver_cost: int = 0,
    additional_wheat_cost: int = 0,
) -> BuildingAbilitySource | None:
    """Resolve/validate Mill source for Give Alms paid or Ordination actions."""
    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key="mill",
    )
    action_hires_mill = action.hired_building_id == "mill"
    if required_wheat < 0:
        raise TransitionValidationError("Mill required wheat cannot be negative.")
    uses_mill_bonus = required_wheat > 0
    mill_wheat_cost = mill_actual_wheat_cost(required_wheat)

    if source.source_type == "own_active" and source.usable:
        if action_hires_mill:
            raise TransitionValidationError(
                "Mill is own-active; action must not include hired Mill fields."
            )
        return source if uses_mill_bonus else None

    if _is_hired_source(source) and source.usable:
        if not action_hires_mill:
            return None
        expected_source_label = _hired_building_source_label(source)
        if action.hired_building_source != expected_source_label:
            raise TransitionValidationError(
                "Action hired_building_source does not match resolved Mill source: "
                f"expected {expected_source_label}."
            )
        if not uses_mill_bonus:
            raise TransitionValidationError(
                "Mill hire fields are only legal when wheat cost is present."
            )
        if not _can_afford_resolution_costs(
            state.player_state(player),
            required_silver=silver_cost + additional_silver_cost,
            required_wheat=mill_wheat_cost + additional_wheat_cost,
            hired_source=source,
        ):
            raise TransitionValidationError(
                "Mill hire plus duty costs are not affordable for this action."
            )
        return source

    if action_hires_mill:
        raise TransitionValidationError("Mill is not hire-usable in current state.")
    return None


def _can_afford_resolution_costs(
    player_state,
    *,
    required_stone: int = 0,
    required_silver: int = 0,
    required_wheat: int = 0,
    hired_source: BuildingAbilitySource | None = None,
) -> bool:
    """Return True when total resolution costs are jointly affordable."""
    required_stone = max(0, required_stone)
    required_silver = max(0, required_silver)
    required_wheat = max(0, required_wheat)

    if hired_source is not None and _is_hired_source(hired_source):
        if not hired_source.usable:
            return False
        if hired_source.hire_resource is None or hired_source.hire_cost <= 0:
            return False
        if hired_source.hire_resource == "stone":
            required_stone += hired_source.hire_cost
        elif hired_source.hire_resource == "silver":
            required_silver += hired_source.hire_cost
        elif hired_source.hire_resource == "wheat":
            required_wheat += hired_source.hire_cost
        else:
            return False

    resources = player_state.resources
    return (
        resources.stone >= required_stone
        and resources.silver >= required_silver
        and resources.wheat >= required_wheat
    )


def _building_hired_event(
    *,
    source: BuildingAbilitySource,
    payment: BuildingHirePayment,
    actor: PlayerId,
    action_id: str,
    config: GameConfig,
) -> GameEvent:
    building_name = config.buildings.name_for_id(source.building_key)
    return GameEvent(
        event_type=EventType.BUILDING_HIRED,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building_id=source.building_key,
            building_name=building_name,
            source=_hired_building_source_label(source),
            payee=payment.payee,
            resource=payment.resource or "none",
            amount=payment.amount,
        ),
    )


def _resource_delta_between(before, after) -> tuple[int, int, int]:
    return (
        after.stone - before.stone,
        after.silver - before.silver,
        after.wheat - before.wheat,
    )


def _all_alms_house_extra_payment_options(*, max_bonus: int) -> tuple[tuple[int, int], ...]:
    options: list[tuple[int, int]] = []
    if max_bonus <= 0:
        return ()
    for duty_value_bonus in range(max_bonus, 0, -1):
        for extra_silver in range(duty_value_bonus, -1, -1):
            extra_wheat = duty_value_bonus - extra_silver
            options.append((extra_silver, extra_wheat))
    return tuple(options)


def _ordination_wheat_cost(step_count: int, *, mill_active: bool) -> int:
    if step_count < 0:
        raise ValueError("step_count cannot be negative.")
    if not mill_active:
        return step_count
    return mill_actual_wheat_cost(step_count)


def _hire_wheat_cost(source: BuildingAbilitySource) -> int:
    if not _is_hired_source(source):
        return 0
    if source.hire_resource == "wheat":
        return source.hire_cost
    return 0


def _player_state_with_wheat_delta(player_state, *, wheat_delta: int):
    resources = player_state.resources.add(wheat=wheat_delta)
    if resources.wheat < 0:
        return None
    return replace(player_state, resources=resources)


def _construct_road_only_plans(
    *,
    duty_value: int,
    road_engineer_extra_roads: int,
) -> tuple[str, ...]:
    if duty_value <= 0:
        return ()

    max_extra_roads = max(0, road_engineer_extra_roads)
    return _construct_road_plans(max_extra_roads=max_extra_roads)


def _construct_building_plus_road_plans(
    *,
    duty_value: int,
    road_engineer_extra_roads: int,
) -> tuple[str, ...]:
    if duty_value < 2:
        return ()

    max_extra_roads = max(0, road_engineer_extra_roads)
    return _construct_road_plans(max_extra_roads=max_extra_roads)


def _construct_road_plans(*, max_extra_roads: int) -> tuple[str, ...]:
    plans: list[str] = []
    for extra_roads in range(max_extra_roads, -1, -1):
        plans.append(_construct_plan_with_extra_roads(extra_roads))
    return tuple(plans)


def _construct_plan_with_extra_roads(extra_roads: int) -> str:
    if extra_roads < 0:
        raise ValueError("extra_roads cannot be negative.")
    parts = [_CONSTRUCT_PLAN_ROAD]
    parts.extend(_CONSTRUCT_PLAN_EXTRA_ROAD for _ in range(extra_roads))
    return " + ".join(parts)


def _construct_plan_extra_road_count(plan: str) -> int:
    return sum(
        1
        for part in (piece.strip() for piece in plan.split("+"))
        if part == _CONSTRUCT_PLAN_EXTRA_ROAD
    )


def _is_duty_value_building_bonus_event(event: GameEvent) -> bool:
    if event.event_type is not EventType.BUILDING_BONUS:
        return False
    return "duty_value_bonus" in dict(event.details)


def _is_allocation_capacity_building_bonus_event(event: GameEvent) -> bool:
    if event.event_type is not EventType.BUILDING_BONUS:
        return False
    details = dict(event.details)
    return (
        details.get("building") == "chapter_house"
        and details.get("action") == TurnResolutionType.ALLOCATION.value
        and details.get("second_acolyte") is True
    )


def _constructible_building_ids(
    *,
    state: GameState,
    player_state,
    config: GameConfig,
    building_market: tuple[str, ...],
) -> tuple[str, ...]:
    if not has_available_player_board_slot(player_state, config):
        return ()

    owned_buildings = set(player_state.player_board_slots.active_buildings).union(
        player_state.player_board_slots.donated_buildings
    )
    affordable_buildings: list[str] = []
    for building_id in building_market:
        if building_id in owned_buildings:
            continue
        try:
            definition = config.buildings.definition_by_id(building_id)
        except ValueError:
            continue
        if not is_building_live(state, building_id):
            continue
        if player_state.resources.stone >= definition.stone_cost:
            affordable_buildings.append(building_id)
    return tuple(affordable_buildings)


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


def _legal_give_alms_donation_buildings(
    player_state,
    config: GameConfig,
) -> tuple[str, ...]:
    legal_buildings: list[str] = []
    donated_buildings = set(player_state.player_board_slots.donated_buildings)
    for building_id in player_state.player_board_slots.active_buildings:
        if building_id in donated_buildings:
            continue
        try:
            config.buildings.definition_by_id(building_id)
        except ValueError:
            continue
        legal_buildings.append(building_id)
    return tuple(legal_buildings)


def _taxation_bonus_resource_types(
    state: GameState,
    config: GameConfig,
    *,
    player: PlayerId,
    sowed_vector: tuple[int, ...],
    selected_duty: int,
) -> tuple[str, ...]:
    unlocked_resources: set[str] = set()
    for duty_position in config.duty_positions():
        if duty_position == selected_duty:
            continue
        if config.duty_category_for_position(duty_position) == "taxation":
            continue
        strength = duty_strength(
            sowed_vector[duty_position],
            _competing_counts(state, player=player, duty_position=duty_position),
        )
        if strength is not DutyStrength.MAJORITY:
            continue
        resource = config.tithe_counters.resource_for_board_index(duty_position)
        if resource == "cornucopia":
            unlocked_resources.update(_TAXATION_RESOURCE_TYPES)
        elif resource in _TAXATION_RESOURCE_TYPES:
            unlocked_resources.add(resource)
    return tuple(resource for resource in _TAXATION_RESOURCE_TYPES if resource in unlocked_resources)


def _taxation_bonus_resource_choices(
    bonus_resource_types: tuple[str, ...],
    *,
    duty_value: int,
) -> tuple[tuple[str, ...], ...]:
    if duty_value <= 0:
        return ()
    if not bonus_resource_types:
        return ((),)
    return tuple(
        tuple(choice)
        for choice in combinations_with_replacement(bonus_resource_types, duty_value)
    )


def _allocation_move_sequences(
    player_state,
    *,
    max_moves: int,
    special_activity_capacity: int,
) -> tuple[tuple[AllocationMove, ...], ...]:
    if max_moves <= 0:
        return ()

    discovered_sequences: list[tuple[AllocationMove, ...]] = []

    def _walk(
        current_player_state,
        current_path: tuple[AllocationMove, ...],
    ) -> None:
        if len(current_path) >= max_moves:
            return
        for move in legal_allocation_moves(
            current_player_state,
            capacity=special_activity_capacity,
        ):
            try:
                next_state = apply_allocation_move_with_capacity(
                    current_player_state,
                    move,
                    capacity=special_activity_capacity,
                )
            except ValueError:
                continue
            next_path = (*current_path, move)
            discovered_sequences.append(next_path)
            _walk(next_state, next_path)

    _walk(player_state, ())

    ordered_sequences: list[tuple[AllocationMove, ...]] = []
    for length in range(max_moves, 0, -1):
        for sequence in discovered_sequences:
            if len(sequence) == length:
                ordered_sequences.append(sequence)

    seen: set[tuple[tuple[str, str], ...]] = set()
    unique_sequences: list[tuple[AllocationMove, ...]] = []
    for sequence in ordered_sequences:
        key = tuple((move.source, move.destination) for move in sequence)
        if key in seen:
            continue
        seen.add(key)
        unique_sequences.append(sequence)
    return tuple(unique_sequences)
