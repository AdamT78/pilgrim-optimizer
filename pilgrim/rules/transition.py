"""State transitions and legal action generation for Ruleset A."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations_with_replacement

from pilgrim.model.actions import (
    AllocationMove,
    FullTurnAction,
    GameAction,
    SetupSowAction,
    StartPlayerConfessionBoxUse,
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
    merchant_position_name,
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
from pilgrim.rules.sow_routes import (
    cloisters_route_variants,
    combined_kogge_cloisters_route_variants,
    is_legal_route_with_cloisters_skip as _is_legal_route_with_cloisters_skip,
    is_legal_route_with_kogge_and_cloisters_skip as _is_legal_route_with_kogge_and_cloisters_skip,
    kogge_city_start_routes,
    normal_sow_routes,
    route_requires_kogge as _route_requires_kogge_for_origin_route,
    sow_vector_with_optional_city_kogge as _sow_vector_with_optional_city_kogge,
)
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
from pilgrim.rules.timing import (
    advance_timing,
    is_round_end_for_state,
    resolve_round_end,
    resolve_season_end,
)
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


@dataclass(frozen=True, slots=True)
class _StartTurnRelocationOption:
    """Pre-sow state plus relocation metadata for one start-turn modifier use."""

    state: GameState
    building_id: str
    source: BuildingAbilitySource
    from_position: int
    to_position: int


@dataclass(frozen=True, slots=True)
class _ResolvedStartTurnRelocation:
    """Validated start-turn relocation directive from one action."""

    building_id: str
    source: BuildingAbilitySource
    from_position: int
    to_position: int


@dataclass(frozen=True, slots=True)
class _SowRouteOption:
    """One legal sow-route option with optional route-modifier metadata."""

    route: tuple[int, ...]
    building_id: str | None = None
    source: BuildingAbilitySource | None = None
    secondary_building_id: str | None = None
    secondary_source: BuildingAbilitySource | None = None
    omitted_location: int | None = None


@dataclass(frozen=True, slots=True)
class _ResolvedCloistersRoute:
    """Validated Cloisters sow-route modifier directive from one action."""

    source: BuildingAbilitySource
    omitted_location: int


@dataclass(frozen=True, slots=True)
class _BuildingConversionOption:
    """Pre-sow conversion variant for one legal building conversion use."""

    state: GameState
    building_id: str
    source: BuildingAbilitySource
    direction: str
    amount: int


@dataclass(frozen=True, slots=True)
class _ResolvedGrainStoreConversion:
    """Validated pre-sow building conversion directive from one action."""

    building_id: str
    source: BuildingAbilitySource
    direction: str
    amount: int


@dataclass(frozen=True, slots=True)
class _BankPaymentOption:
    """Pre-sow state plus payment-substitution metadata for one Bank use."""

    state: GameState
    building_id: str
    source: BuildingAbilitySource
    replaced_resource: str
    silver_amount: int


@dataclass(frozen=True, slots=True)
class _ResolvedBankPayment:
    """Validated Bank payment substitution directive from one action."""

    building_id: str
    source: BuildingAbilitySource
    replaced_resource: str
    silver_amount: int


@dataclass(frozen=True, slots=True)
class _GuildMerchantAdvanceOption:
    """Pre-sow merchant-advance variant for one legal Guild use."""

    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _ResolvedGuildMerchantAdvance:
    """Validated pre-sow Guild merchant-advance directive from one action."""

    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _ScriptoriumEffectiveAcolyteOption:
    """Pre-sow state plus relation-context metadata for one Scriptorium use."""

    state: GameState
    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _ResolvedScriptoriumEffectiveAcolyte:
    """Validated pre-sow Scriptorium effective-acolyte modifier directive."""

    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _CustomsHouseTaxationOption:
    """Pre-sow state plus Taxation-majority context for one Customs House use."""

    state: GameState
    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _ResolvedCustomsHouseTaxation:
    """Validated pre-sow Customs House Taxation-majority override directive."""

    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _WagonYardFreeHireOption:
    """One Wagon Yard free-hire target option with temporary active target state."""

    state: GameState
    target_building_id: str
    target_source: str


@dataclass(frozen=True, slots=True)
class _ResolvedWagonYardFreeHire:
    """Validated Wagon Yard free-hire directive for one target building/source."""

    enabler_building_id: str
    target_building_id: str
    target_source: str
    target_was_temporary_added: bool


@dataclass(frozen=True, slots=True)
class _PulpitWorkforceMoveOption:
    """Pre-sow workforce-move variant for one legal Pulpit use."""

    state: GameState
    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _ResolvedPulpitWorkforceMove:
    """Validated pre-sow Pulpit workforce-move directive from one action."""

    building_id: str
    source: BuildingAbilitySource


@dataclass(frozen=True, slots=True)
class _ResolvedEndTurnRelocation:
    """Validated end-turn relocation directive from one action."""

    building_id: str
    source: BuildingAbilitySource
    from_position: int
    to_position: int | None
    to_pool: str


@dataclass(frozen=True, slots=True)
class _DutyRelationModifierContext:
    """Per-action context for virtual duty-relation count modifiers."""

    acting_player: PlayerId
    uses_scriptorium: bool = False
    uses_customs_house: bool = False


_TAXATION_RESOURCE_TYPES: tuple[str, ...] = ("stone", "silver", "wheat")
_CONSTRUCT_PLAN_ROAD = "road"
_CONSTRUCT_PLAN_EXTRA_ROAD = "road_engineer_extra_road"
_CONSTRUCT_ROAD_SCAFFOLD_TEXT = "construct road part requires spatial road system"
_LIBRARY_ABBEY_TARGET = "abbey"
_ROUTE_BUILDING_KOGGE = "kogge"
_ROUTE_BUILDING_CLOISTERS = "cloisters"
_BUILDING_GRAIN_STORE = "grain_store"
_GRAIN_STORE_BUY_WHEAT = "buy_wheat"
_GRAIN_STORE_SELL_WHEAT = "sell_wheat"
_BUILDING_INDULGENCES = "indulgences"
_INDULGENCES_BUY_PIETY = "buy_piety"
_INDULGENCES_SELL_PIETY = "sell_piety"
_BUILDING_STONE_YARD = "stone_yard"
_STONE_YARD_BUY_STONE = "buy_stone"
_STONE_YARD_SELL_STONE = "sell_stone"
_BUILDING_BREWERY = "brewery"
_BREWERY_SELL_WHEAT_FOR_SILVER = "sell_wheat_for_silver"
_BUILDING_BANK = "bank"
_BANK_REPLACED_RESOURCES: tuple[str, ...] = ("wheat", "stone", "piety")
_BUILDING_SCRIPTORIUM = "scriptorium"
_BUILDING_CUSTOMS_HOUSE = "customs_house"
_BUILDING_GUILD = "guild"
_BUILDING_PULPIT = "pulpit"
_BUILDING_WAGON_YARD = "wagon_yard"
_BUILDING_CONFESSION_BOX = "confession_box"
_CONFESSION_BOX_TEMPORARY_PIETY_BONUS = 2
_WAGON_YARD_SUPPORTED_TARGET_BUILDINGS: frozenset[str] = frozenset(
    {
        _BUILDING_GRAIN_STORE,
        _BUILDING_INDULGENCES,
        _BUILDING_STONE_YARD,
        _BUILDING_BREWERY,
        _BUILDING_BANK,
        _BUILDING_GUILD,
        _BUILDING_PULPIT,
        _BUILDING_SCRIPTORIUM,
        _BUILDING_CUSTOMS_HOUSE,
    }
)
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
    actions: list[GameAction] = []
    for start_turn_option in _legal_start_turn_relocation_options(state, config):
        start_turn_state = state if start_turn_option is None else start_turn_option.state
        library_source = _resolved_library_source_for_state(start_turn_state, config)
        variant_actions = _legal_full_turn_actions_for_state(
            start_turn_state,
            config,
            allow_guild_modifier=start_turn_option is None,
            allow_pulpit_modifier=start_turn_option is None,
            allow_scriptorium_modifier=start_turn_option is None,
            allow_customs_house_modifier=start_turn_option is None,
            allow_wagon_yard_modifier=start_turn_option is None,
            allow_bank_modifier=start_turn_option is None,
            uses_scriptorium_effective_counts=False,
            uses_customs_house_taxation_override=False,
        )
        for variant_action in variant_actions:
            if not isinstance(variant_action, FullTurnAction):
                if variant_action not in actions:
                    actions.append(variant_action)
                continue
            action = variant_action
            if start_turn_option is not None:
                action = _with_start_turn_relocation_fields(
                    action,
                    option=start_turn_option,
                )
            if action not in actions:
                actions.append(action)
            if library_source is None:
                continue
            if action.merchant_advance_building_id == _BUILDING_GUILD:
                # Defer mixed Guild+Library hire-order interactions for this milestone.
                continue
            if action.workforce_move_building_id == _BUILDING_PULPIT:
                # Defer mixed Pulpit+Library hire-order interactions for this milestone.
                continue
            if action.effective_acolyte_building_id == _BUILDING_SCRIPTORIUM:
                # Defer mixed Scriptorium+Library hire-order interactions for this milestone.
                continue
            if action.taxation_majority_building_id == _BUILDING_CUSTOMS_HOUSE:
                # Defer mixed Customs House+Library hire-order interactions for this milestone.
                continue
            if action.free_hire_enabler_building_id == _BUILDING_WAGON_YARD:
                # Defer mixed Wagon Yard+Library hire-order interactions for this milestone.
                continue
            for library_action in _library_suffix_variants_for_action(
                original_state=state,
                state_for_turn=start_turn_state,
                config=config,
                action=action,
                source=library_source,
            ):
                if library_action not in actions:
                    actions.append(library_action)
    if not is_round_end_for_state(state, config.timing):
        return tuple(actions)

    if not _confession_box_is_selected_in_state(state):
        return tuple(actions)

    expanded_actions: list[GameAction] = []
    for candidate in actions:
        if not isinstance(candidate, FullTurnAction):
            if candidate not in expanded_actions:
                expanded_actions.append(candidate)
            continue
        for variant in _start_player_confession_box_variants_for_action(
            state=state,
            config=config,
            action=candidate,
        ):
            if variant not in expanded_actions:
                expanded_actions.append(variant)
    return tuple(expanded_actions)


def _legal_full_turn_actions_for_state(
    state: GameState,
    config: GameConfig,
    *,
    allow_guild_modifier: bool,
    allow_pulpit_modifier: bool,
    allow_scriptorium_modifier: bool,
    allow_customs_house_modifier: bool,
    allow_wagon_yard_modifier: bool,
    allow_bank_modifier: bool,
    uses_scriptorium_effective_counts: bool,
    uses_customs_house_taxation_override: bool,
) -> tuple[GameAction, ...]:
    player_vector = state.player_vector(state.active_player)
    base_player_state = state.player_state(state.active_player)
    chapter_house_active = player_has_active_chapter_house(base_player_state)
    activity_capacity = special_activity_capacity(chapter_house_active=chapter_house_active)
    duty_relation_context = _DutyRelationModifierContext(
        acting_player=state.active_player,
        uses_scriptorium=uses_scriptorium_effective_counts,
        uses_customs_house=uses_customs_house_taxation_override,
    )
    actions: list[GameAction] = []

    def _append_bank_payment_variants_for_action(
        *,
        action: FullTurnAction,
        state_for_action: GameState,
        required_stone: int = 0,
        required_silver: int = 0,
        required_wheat: int = 0,
        required_piety: int = 0,
        hired_source: BuildingAbilitySource | None = None,
    ) -> None:
        if not allow_bank_modifier:
            return
        if not _is_bank_modifier_eligible_action(action):
            return
        bank_options = _legal_bank_payment_options_for_action(
            state=state_for_action,
            config=config,
            required_stone=required_stone,
            required_silver=required_silver,
            required_wheat=required_wheat,
            required_piety=required_piety,
            hired_source=hired_source,
        )
        for bank_option in bank_options:
            bank_action = _with_bank_payment_fields(action, option=bank_option)
            if bank_action not in actions:
                actions.append(bank_action)

    for origin in occupied_positions(player_vector):
        picked_up = player_vector[origin]
        for route_option in _legal_sow_routes_for_origin(
            state,
            config,
            origin=origin,
            picked_up=picked_up,
        ):
            route = route_option.route
            route_state = state
            route_sources_to_pay: list[BuildingAbilitySource] = []
            if route_option.source is not None and _is_hired_source(route_option.source):
                route_sources_to_pay.append(route_option.source)
            if route_option.secondary_source is not None and _is_hired_source(
                route_option.secondary_source
            ):
                route_sources_to_pay.append(route_option.secondary_source)
            route_payment_invalid = False
            for route_source in route_sources_to_pay:
                try:
                    route_state, _ = apply_building_hire_payment(
                        route_state,
                        acting_player=state.active_player,
                        source=route_source,
                    )
                except ValueError:
                    route_payment_invalid = True
                    break
            if route_payment_invalid:
                continue

            uses_kogge = (
                route_option.building_id == _ROUTE_BUILDING_KOGGE
                or route_option.secondary_building_id == _ROUTE_BUILDING_KOGGE
            )
            uses_cloisters = (
                route_option.building_id == _ROUTE_BUILDING_CLOISTERS
                or route_option.secondary_building_id == _ROUTE_BUILDING_CLOISTERS
            )
            sowed_vector = _sow_vector_with_optional_city_kogge(
                player_vector,
                origin=origin,
                route=route,
                board=config.board,
                allows_kogge_city_step=uses_kogge,
                cloisters_omitted_location=(
                    route_option.omitted_location if uses_cloisters else None
                ),
                cloisters_with_kogge=uses_kogge and uses_cloisters,
            )
            conversion_options: tuple[_BuildingConversionOption | None, ...] = (
                None,
                *_legal_grain_store_conversion_options(route_state, config),
                *_legal_indulgences_conversion_options(route_state, config),
                *_legal_stone_yard_conversion_options(route_state, config),
                *_legal_brewery_conversion_options(route_state, config),
            )
            for conversion_option in conversion_options:
                state_for_turn = (
                    route_state if conversion_option is None else conversion_option.state
                )
                player_state = state_for_turn.player_state(state.active_player)
                player_resources = player_state.resources
                bank_modifier_allowed_for_turn = (
                    route_option.building_id is None and conversion_option is None
                )

                for duty_position in config.duty_positions():
                    if sowed_vector[duty_position] <= 0:
                        continue
                    actions_before_duty = len(actions)
                    duty_category = config.duty_category_for_position(duty_position)
                    strength = _duty_strength_for_position(
                        state,
                        config,
                        player=state.active_player,
                        duty_position=duty_position,
                        sowed_vector=sowed_vector,
                        relation_context=duty_relation_context,
                    )
                    if duty_category == "taxation":
                        strength = _taxation_duty_strength_for_position(
                            state,
                            config,
                            player=state.active_player,
                            duty_position=duty_position,
                            sowed_vector=sowed_vector,
                            relation_context=duty_relation_context,
                        )
                    _duty_value, silver_cost = duty_value_and_silver_cost(strength)
                    if player_resources.silver < silver_cost:
                        continue
                    category_actions = action_options_for_duty_category(duty_category)
                    if TurnResolutionType.GIVE_ALMS_PAID in category_actions:
                        strength = _duty_strength_for_position(
                            state,
                            config,
                            player=state.active_player,
                            duty_position=duty_position,
                            sowed_vector=sowed_vector,
                            relation_context=duty_relation_context,
                        )
                        duty_value, silver_cost = duty_value_and_silver_cost(strength)
                        available_silver = player_resources.silver - silver_cost
                        if available_silver >= 0:
                            mill_source = building_ability_source(
                                state_for_turn,
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
                                    if (
                                        mill_source.source_type == "own_active"
                                        and mill_source.usable
                                    ):
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
                        strength = _duty_strength_for_position(
                            state,
                            config,
                            player=state.active_player,
                            duty_position=duty_position,
                            sowed_vector=sowed_vector,
                            relation_context=duty_relation_context,
                        )
                        duty_value, silver_cost = duty_value_and_silver_cost(strength)
                        base_move_sequences = _allocation_move_sequences(
                            player_state,
                            max_moves=duty_value,
                            special_activity_capacity=activity_capacity,
                        )
                        infirmary_source = building_ability_source(
                            state_for_turn,
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
                        strength = _duty_strength_for_position(
                            state,
                            config,
                            player=state.active_player,
                            duty_position=duty_position,
                            sowed_vector=sowed_vector,
                            relation_context=duty_relation_context,
                        )
                        duty_value, silver_cost = duty_value_and_silver_cost(strength)
                        road_engineer_extra_roads = road_engineer_construct_extra_roads_bonus(
                            player_state
                        )
                        if player_resources.silver >= silver_cost:
                            constructible_building_ids = _constructible_building_ids(
                                state=state_for_turn,
                                player_state=player_state,
                                config=config,
                                building_market=state_for_turn.building_market,
                            )
                            construct_candidate_ids = _construct_market_candidate_building_ids(
                                state=state_for_turn,
                                player_state=player_state,
                                config=config,
                                building_market=state_for_turn.building_market,
                            )
                            for building_id in constructible_building_ids:
                                construct_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.CONSTRUCT_BUILDING,
                                    construct_building_id=building_id,
                                )
                                actions.append(construct_action)
                            for building_id in construct_candidate_ids:
                                stone_cost = config.buildings.definition_by_id(building_id).stone_cost
                                construct_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.CONSTRUCT_BUILDING,
                                    construct_building_id=building_id,
                                )
                                if bank_modifier_allowed_for_turn:
                                    _append_bank_payment_variants_for_action(
                                        action=construct_action,
                                        state_for_action=state_for_turn,
                                        required_silver=silver_cost,
                                        required_stone=stone_cost,
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
                                    construct_building_and_road_action = FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=(
                                            TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
                                        ),
                                        construct_plan=construct_plan,
                                        construct_building_id=building_id,
                                    )
                                    actions.append(construct_building_and_road_action)
                                for building_id in construct_candidate_ids:
                                    stone_cost = config.buildings.definition_by_id(
                                        building_id
                                    ).stone_cost
                                    construct_building_and_road_action = FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=(
                                            TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED
                                        ),
                                        construct_plan=construct_plan,
                                        construct_building_id=building_id,
                                    )
                                    if bank_modifier_allowed_for_turn:
                                        _append_bank_payment_variants_for_action(
                                            action=construct_building_and_road_action,
                                            state_for_action=state_for_turn,
                                            required_silver=silver_cost,
                                            required_stone=stone_cost,
                                        )
                    elif TurnResolutionType.ORDINATION in category_actions:
                        strength = _duty_strength_for_position(
                            state,
                            config,
                            player=state.active_player,
                            duty_position=duty_position,
                            sowed_vector=sowed_vector,
                            relation_context=duty_relation_context,
                        )
                        duty_value, silver_cost = duty_value_and_silver_cost(strength)
                        available_silver = player_resources.silver - silver_cost
                        if available_silver < 0:
                            continue

                        infirmary_source = building_ability_source(
                            state_for_turn,
                            config,
                            acting_player=state.active_player,
                            building_key="infirmary",
                        )
                        mill_source = building_ability_source(
                            state_for_turn,
                            config,
                            acting_player=state.active_player,
                            building_key="mill",
                        )

                        owns_active_infirmary = (
                            infirmary_source.source_type == "own_active" and infirmary_source.usable
                        )
                        owns_active_mill = (
                            mill_source.source_type == "own_active" and mill_source.usable
                        )
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
                                if bank_modifier_allowed_for_turn:
                                    _append_bank_payment_variants_for_action(
                                        action=base_action,
                                        state_for_action=state_for_turn,
                                        required_silver=silver_cost,
                                        required_wheat=required_wheat,
                                    )

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
                                    if bank_modifier_allowed_for_turn:
                                        _append_bank_payment_variants_for_action(
                                            action=bonus_action,
                                            state_for_action=state_for_turn,
                                            required_silver=silver_cost,
                                            required_wheat=required_wheat,
                                        )

                        # Bank can make otherwise-unaffordable Ordination wheat costs legal.
                        bank_sequence_seed = _player_state_with_wheat_delta(
                            player_state,
                            wheat_delta=(
                                (2 if no_hire_mill_active else 0) + player_resources.silver
                            ),
                        )
                        if (
                            bank_modifier_allowed_for_turn
                            and bank_sequence_seed is not None
                            and player_resources.silver > 0
                        ):
                            bank_base_sequences = legal_ordination_step_sequences(
                                bank_sequence_seed,
                                max_steps=duty_value,
                            )
                            for step_sequence in bank_base_sequences:
                                required_wheat = _ordination_wheat_cost(
                                    len(step_sequence),
                                    mill_active=no_hire_mill_active,
                                )
                                base_action = FullTurnAction(
                                    origin=origin,
                                    route=route,
                                    selected_duty=duty_position,
                                    resolution=TurnResolutionType.ORDINATION,
                                    ordination_steps=step_sequence,
                                )
                                _append_bank_payment_variants_for_action(
                                    action=base_action,
                                    state_for_action=state_for_turn,
                                    required_silver=silver_cost,
                                    required_wheat=required_wheat,
                                )
                            if owns_active_infirmary:
                                bank_bonus_sequences = legal_ordination_step_sequences(
                                    bank_sequence_seed,
                                    max_steps=duty_value + 1,
                                )
                                for step_sequence in bank_bonus_sequences:
                                    if len(step_sequence) <= duty_value:
                                        continue
                                    required_wheat = _ordination_wheat_cost(
                                        len(step_sequence),
                                        mill_active=no_hire_mill_active,
                                    )
                                    bonus_action = FullTurnAction(
                                        origin=origin,
                                        route=route,
                                        selected_duty=duty_position,
                                        resolution=TurnResolutionType.ORDINATION,
                                        ordination_steps=step_sequence,
                                    )
                                    _append_bank_payment_variants_for_action(
                                        action=bonus_action,
                                        state_for_action=state_for_turn,
                                        required_silver=silver_cost,
                                        required_wheat=required_wheat,
                                    )

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
                        strength = _taxation_duty_strength_for_position(
                            state,
                            config,
                            player=state.active_player,
                            duty_position=duty_position,
                            sowed_vector=sowed_vector,
                            relation_context=duty_relation_context,
                        )
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
                            relation_context=duty_relation_context,
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
                                    state=state_for_turn,
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
                    if (
                        route_option.building_id is not None
                        or conversion_option is not None
                    ):
                        for index in range(actions_before_duty, len(actions)):
                            action = actions[index]
                            if not isinstance(action, FullTurnAction):
                                continue
                            if route_option.building_id is not None:
                                action = _with_route_option_fields(
                                    action,
                                    option=route_option,
                                )
                            if conversion_option is not None:
                                action = _with_grain_store_conversion_fields(
                                    action,
                                    option=conversion_option,
                                )
                            actions[index] = action
    if allow_scriptorium_modifier:
        scriptorium_options = _legal_scriptorium_effective_acolyte_options(state, config)
        if scriptorium_options:
            scriptorium_option = scriptorium_options[0]
            for action in _legal_full_turn_actions_for_state(
                scriptorium_option.state,
                config,
                allow_guild_modifier=False,
                allow_pulpit_modifier=False,
                allow_scriptorium_modifier=False,
                allow_customs_house_modifier=False,
                allow_wagon_yard_modifier=False,
                allow_bank_modifier=False,
                uses_scriptorium_effective_counts=True,
                uses_customs_house_taxation_override=False,
            ):
                if not isinstance(action, FullTurnAction):
                    continue
                if not _is_scriptorium_modifier_eligible_action(action):
                    continue
                if not _scriptorium_can_affect_action(action):
                    continue
                scriptorium_action = _with_scriptorium_effective_acolyte_fields(
                    action,
                    option=scriptorium_option,
                )
                if scriptorium_action not in actions:
                    actions.append(scriptorium_action)
    if allow_pulpit_modifier:
        pulpit_options = _legal_pulpit_workforce_move_options(state, config)
        if pulpit_options:
            pulpit_option = pulpit_options[0]
            for action in _legal_full_turn_actions_for_state(
                pulpit_option.state,
                config,
                allow_guild_modifier=False,
                allow_pulpit_modifier=False,
                allow_scriptorium_modifier=False,
                allow_customs_house_modifier=False,
                allow_wagon_yard_modifier=False,
                allow_bank_modifier=False,
                uses_scriptorium_effective_counts=False,
                uses_customs_house_taxation_override=False,
            ):
                if not isinstance(action, FullTurnAction):
                    continue
                if not _is_pulpit_modifier_eligible_action(action):
                    continue
                pulpit_action = _with_pulpit_workforce_move_fields(
                    action,
                    option=pulpit_option,
                )
                if pulpit_action not in actions:
                    actions.append(pulpit_action)
    if allow_customs_house_modifier:
        customs_house_options = _legal_customs_house_taxation_options(state, config)
        if customs_house_options:
            customs_house_option = customs_house_options[0]
            for action in _legal_full_turn_actions_for_state(
                customs_house_option.state,
                config,
                allow_guild_modifier=False,
                allow_pulpit_modifier=False,
                allow_scriptorium_modifier=False,
                allow_customs_house_modifier=False,
                allow_wagon_yard_modifier=False,
                allow_bank_modifier=False,
                uses_scriptorium_effective_counts=False,
                uses_customs_house_taxation_override=True,
            ):
                if not isinstance(action, FullTurnAction):
                    continue
                if not _is_customs_house_modifier_eligible_action(action):
                    continue
                if not _customs_house_can_affect_action(action):
                    continue
                customs_house_action = _with_customs_house_taxation_fields(
                    action,
                    option=customs_house_option,
                )
                if customs_house_action not in actions:
                    actions.append(customs_house_action)
    if allow_wagon_yard_modifier:
        wagon_yard_options = _legal_wagon_yard_free_hire_options(state, config)
        for wagon_yard_option in wagon_yard_options:
            for action in _legal_full_turn_actions_for_state(
                wagon_yard_option.state,
                config,
                allow_guild_modifier=(
                    wagon_yard_option.target_building_id == _BUILDING_GUILD
                ),
                allow_pulpit_modifier=(
                    wagon_yard_option.target_building_id == _BUILDING_PULPIT
                ),
                allow_scriptorium_modifier=(
                    wagon_yard_option.target_building_id == _BUILDING_SCRIPTORIUM
                ),
                allow_customs_house_modifier=(
                    wagon_yard_option.target_building_id == _BUILDING_CUSTOMS_HOUSE
                ),
                allow_wagon_yard_modifier=False,
                allow_bank_modifier=(
                    wagon_yard_option.target_building_id == _BUILDING_BANK
                ),
                uses_scriptorium_effective_counts=False,
                uses_customs_house_taxation_override=False,
            ):
                if not isinstance(action, FullTurnAction):
                    continue
                if not _wagon_yard_action_uses_target_building(
                    action,
                    target_building_id=wagon_yard_option.target_building_id,
                ):
                    continue
                if not _wagon_yard_action_is_supported_composition(
                    action,
                    target_building_id=wagon_yard_option.target_building_id,
                ):
                    continue
                wagon_yard_action = _with_wagon_yard_free_hire_fields(
                    action,
                    option=wagon_yard_option,
                )
                if wagon_yard_action not in actions:
                    actions.append(wagon_yard_action)
    if allow_guild_modifier:
        guild_options = _legal_guild_merchant_advance_options(state, config)
        if guild_options:
            guild_option = guild_options[0]
            state_after_guild = _state_after_guild_merchant_advance_for_legal_generation(
                state,
                option=guild_option,
                config=config,
            )
            for action in _legal_full_turn_actions_for_state(
                state_after_guild,
                config,
                allow_guild_modifier=False,
                allow_pulpit_modifier=False,
                allow_scriptorium_modifier=False,
                allow_customs_house_modifier=False,
                allow_wagon_yard_modifier=False,
                allow_bank_modifier=False,
                uses_scriptorium_effective_counts=False,
                uses_customs_house_taxation_override=False,
            ):
                if not isinstance(action, FullTurnAction):
                    continue
                if not _is_guild_modifier_eligible_action(action):
                    continue
                guild_action = _with_guild_merchant_advance_fields(
                    action,
                    option=guild_option,
                )
                if guild_action not in actions:
                    actions.append(guild_action)
    return tuple(actions)


def _confession_box_is_selected_in_state(state: GameState) -> bool:
    if _BUILDING_CONFESSION_BOX in state.building_market:
        return True
    for player_id in (PlayerId(index) for index in range(state.player_count)):
        slots = state.player_state(player_id).player_board_slots
        if _BUILDING_CONFESSION_BOX in slots.active_buildings:
            return True
        if _BUILDING_CONFESSION_BOX in slots.donated_buildings:
            return True
    return False


def _start_player_confession_box_variants_for_action(
    *,
    state: GameState,
    config: GameConfig,
    action: FullTurnAction,
) -> tuple[FullTurnAction, ...]:
    base_action = _with_start_player_confession_box_uses(action, ())
    preview_result = _apply_full_turn_action(state, base_action, config)
    if preview_result.state.game_over:
        return (base_action,)
    if not any(
        event.event_type is EventType.START_PLAYER_SELECTION for event in preview_result.events
    ):
        return (base_action,)

    ordered_players = _start_player_turn_order(
        start_player=state.start_player,
        player_count=state.player_count,
    )
    use_combinations = _legal_start_player_confession_box_use_combinations(
        state=preview_result.state,
        config=config,
        ordered_players=ordered_players,
    )
    state_before_start_player_selection = replace(
        preview_result.state,
        start_player=state.start_player,
        active_player=state.start_player,
    )
    baseline_next_start_player = _resolved_next_start_player_for_confession_uses(
        state=state_before_start_player_selection,
        uses=(),
    )
    kept_use_combinations: list[tuple[StartPlayerConfessionBoxUse, ...]] = [()]
    for use_combination in use_combinations:
        if not use_combination:
            continue
        candidate_next_start_player = _resolved_next_start_player_for_confession_uses(
            state=state_before_start_player_selection,
            uses=use_combination,
        )
        if candidate_next_start_player != baseline_next_start_player:
            kept_use_combinations.append(use_combination)
    return tuple(
        _with_start_player_confession_box_uses(base_action, use_combination)
        for use_combination in kept_use_combinations
    )


def _start_player_turn_order(
    *,
    start_player: PlayerId,
    player_count: int,
) -> tuple[PlayerId, ...]:
    return tuple(
        PlayerId((int(start_player) + offset) % player_count)
        for offset in range(player_count)
    )


def _legal_start_player_confession_box_use_combinations(
    *,
    state: GameState,
    config: GameConfig,
    ordered_players: tuple[PlayerId, ...],
) -> tuple[tuple[StartPlayerConfessionBoxUse, ...], ...]:
    combinations: list[tuple[StartPlayerConfessionBoxUse, ...]] = []

    def _recurse(
        index: int,
        state_after_payments: GameState,
        selected: tuple[StartPlayerConfessionBoxUse, ...],
    ) -> None:
        if index >= len(ordered_players):
            combinations.append(selected)
            return
        player_id = ordered_players[index]
        _recurse(index + 1, state_after_payments, selected)
        source = building_ability_source(
            state_after_payments,
            config,
            acting_player=player_id,
            building_key=_BUILDING_CONFESSION_BOX,
        )
        if not source.usable:
            return
        if not _confession_box_source_is_live_for_start_player_phase(
            state_after_payments,
            source,
        ):
            return
        source_label = _confession_box_source_label_for_ability_source(source)
        use = StartPlayerConfessionBoxUse(player=player_id, source=source_label)
        if source.source_type == "own_active":
            _recurse(index + 1, state_after_payments, (*selected, use))
            return
        if source.source_type not in ("live_market_hire", "opponent_active_hire"):
            return
        try:
            paid_state, _payment = apply_building_hire_payment(
                state_after_payments,
                acting_player=player_id,
                source=source,
            )
        except ValueError:
            return
        _recurse(index + 1, paid_state, (*selected, use))

    _recurse(0, state, ())
    return tuple(combinations)


def _with_start_player_confession_box_uses(
    action: FullTurnAction,
    uses: tuple[StartPlayerConfessionBoxUse, ...],
) -> FullTurnAction:
    return replace(action, start_player_confession_box_uses=uses)


def _confession_box_source_label_for_ability_source(source: BuildingAbilitySource) -> str:
    if source.source_type == "own_active":
        return "own_active"
    if source.source_type == "live_market_hire":
        return "market"
    if source.source_type == "opponent_active_hire":
        if source.owner is None:
            raise TransitionValidationError(
                "Confession Box opponent-hire source is missing owner label."
            )
        return source.owner
    raise TransitionValidationError(
        f"Confession Box source cannot be used from {source.source_type}."
    )


def _confession_box_source_is_live_for_start_player_phase(
    state: GameState,
    source: BuildingAbilitySource,
) -> bool:
    if source.source_type not in {"own_active", "opponent_active_hire"}:
        return True
    live_round = building_live_round(state, _BUILDING_CONFESSION_BOX)
    if live_round is None:
        return True
    return is_building_live(state, _BUILDING_CONFESSION_BOX)


def _resolved_next_start_player_for_confession_uses(
    *,
    state: GameState,
    uses: tuple[StartPlayerConfessionBoxUse, ...],
) -> PlayerId:
    temporary_bonus_players = {use.player for use in uses}
    players = tuple(PlayerId(index) for index in range(state.player_count))
    highest_effective_piety = max(
        state.player_state(player_id).piety
        + (
            _CONFESSION_BOX_TEMPORARY_PIETY_BONUS
            if player_id in temporary_bonus_players
            else 0
        )
        for player_id in players
    )
    tied_players = tuple(
        player_id
        for player_id in players
        if state.player_state(player_id).piety
        + (
            _CONFESSION_BOX_TEMPORARY_PIETY_BONUS
            if player_id in temporary_bonus_players
            else 0
        )
        == highest_effective_piety
    )
    if len(tied_players) == 1:
        return tied_players[0]
    return _clockwise_start_player_tie_break(
        tied_players=tied_players,
        current_start=state.start_player,
        player_count=state.player_count,
    )


def _clockwise_start_player_tie_break(
    *,
    tied_players: tuple[PlayerId, ...],
    current_start: PlayerId,
    player_count: int,
) -> PlayerId:
    for offset in range(1, player_count + 1):
        candidate = PlayerId((int(current_start) + offset) % player_count)
        if candidate in tied_players:
            return candidate
    raise TransitionValidationError("No tied player found during Confession Box pruning.")


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
                **_invariant_workforce_details(next_state),
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
    if action.start_player_confession_box_uses and not is_round_end_for_state(
        state, config.timing
    ):
        raise TransitionValidationError(
            "Confession Box start-player directives are only valid on round-ending actions."
        )

    player = state.active_player
    turn_start_resources = state.player_state(player).resources
    resolution_resource_delta_baseline = turn_start_resources
    transition_action_id = action_id(action)
    start_turn_relocation = _resolved_start_turn_relocation_for_action(
        state=state,
        config=config,
        player=player,
        action=action,
    )
    state_for_sow = state
    duty_relation_context = _DutyRelationModifierContext(acting_player=player)
    pre_sowing_events: list[GameEvent] = []
    if start_turn_relocation is not None:
        if _is_hired_source(start_turn_relocation.source):
            try:
                state_for_sow, start_turn_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=start_turn_relocation.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=start_turn_relocation.source,
                    payment=start_turn_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        pre_sowing_events.append(
            _start_turn_building_bonus_event(
                actor=player,
                action_id=transition_action_id,
                relocation=start_turn_relocation,
                config=config,
            )
        )
        try:
            relocated_vector = _relocate_one_acolyte_in_mancala_vector(
                state_for_sow.player_vector(player),
                from_position=start_turn_relocation.from_position,
                to_position=start_turn_relocation.to_position,
            )
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc
        state_for_sow = state_for_sow.with_player_vector(player, relocated_vector)
        pre_sowing_events.append(
            _start_turn_relocation_event(
                actor=player,
                action_id=transition_action_id,
                relocation=start_turn_relocation,
                config=config,
            )
        )

    wagon_yard_free_hire = _resolved_wagon_yard_free_hire_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if wagon_yard_free_hire is not None:
        state_for_sow, _ = _state_with_temporary_active_building(
            state_for_sow,
            player=player,
            building_id=wagon_yard_free_hire.target_building_id,
        )
        pre_sowing_events.append(
            _wagon_yard_free_hire_event(
                actor=player,
                action_id=transition_action_id,
                target_building_id=wagon_yard_free_hire.target_building_id,
                target_source=wagon_yard_free_hire.target_source,
                config=config,
            )
        )

    cloisters_route = _resolved_cloisters_route_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    kogge_source = _resolved_kogge_source_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if kogge_source is not None:
        if _is_hired_source(kogge_source):
            try:
                state_for_sow, kogge_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=kogge_source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=kogge_source,
                    payment=kogge_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
    if cloisters_route is not None and _is_hired_source(cloisters_route.source):
        try:
            state_for_sow, cloisters_hire_payment = apply_building_hire_payment(
                state_for_sow,
                acting_player=player,
                source=cloisters_route.source,
            )
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc
        pre_sowing_events.append(
            _building_hired_event(
                source=cloisters_route.source,
                payment=cloisters_hire_payment,
                actor=player,
                action_id=transition_action_id,
                config=config,
            )
        )
    if kogge_source is not None:
        pre_sowing_events.append(
            _kogge_route_bonus_event(
                actor=player,
                action_id=transition_action_id,
                route=action.route,
                config=config,
            )
        )
    if cloisters_route is not None:
        pre_sowing_events.append(
            _cloisters_route_bonus_event(
                actor=player,
                action_id=transition_action_id,
                omitted_location=cloisters_route.omitted_location,
                config=config,
            )
        )
    grain_store_conversion = _resolved_grain_store_conversion_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if grain_store_conversion is not None:
        if _is_hired_source(grain_store_conversion.source):
            try:
                state_for_sow, grain_store_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=grain_store_conversion.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=grain_store_conversion.source,
                    payment=grain_store_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        try:
            state_for_sow, conversion_delta = _apply_grain_store_conversion_to_state(
                state_for_sow,
                player=player,
                config=config,
                conversion=grain_store_conversion,
            )
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc
        pre_sowing_events.append(
            _grain_store_conversion_bonus_event(
                actor=player,
                action_id=transition_action_id,
                conversion=grain_store_conversion,
            )
        )
        pre_sowing_events.append(
            GameEvent(
                event_type=EventType.RESOURCE_DELTA,
                actor=player,
                action_id=transition_action_id,
                details=make_event_details(
                    **(
                        {
                            "stone": conversion_delta[0],
                            "silver": conversion_delta[1],
                            "wheat": conversion_delta[2],
                        }
                        | (
                            {"piety": conversion_delta[3]}
                            if conversion_delta[3] != 0
                            else {}
                        )
                    )
                ),
            )
        )
        resolution_resource_delta_baseline = state_for_sow.player_state(player).resources

    guild_merchant_advance = _resolved_guild_merchant_advance_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if guild_merchant_advance is not None:
        if _is_hired_source(guild_merchant_advance.source):
            try:
                state_for_sow, guild_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=guild_merchant_advance.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=guild_merchant_advance.source,
                    payment=guild_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        pre_sowing_events.append(
            _guild_merchant_bonus_event(
                actor=player,
                action_id=transition_action_id,
            )
        )
        state_for_sow, merchant_advance_event = _apply_guild_merchant_advance_to_state(
            state_for_sow,
            actor=player,
            action_id=transition_action_id,
            config=config,
        )
        pre_sowing_events.append(merchant_advance_event)

    pulpit_workforce_move = _resolved_pulpit_workforce_move_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if pulpit_workforce_move is not None:
        if _is_hired_source(pulpit_workforce_move.source):
            try:
                state_for_sow, pulpit_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=pulpit_workforce_move.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=pulpit_workforce_move.source,
                    payment=pulpit_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        try:
            state_for_sow, pulpit_workforce_event = _apply_pulpit_workforce_move_to_state(
                state_for_sow,
                actor=player,
                action_id=transition_action_id,
            )
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc
        pre_sowing_events.append(
            _pulpit_workforce_bonus_event(
                actor=player,
                action_id=transition_action_id,
            )
        )
        pre_sowing_events.append(pulpit_workforce_event)

    scriptorium_effective_acolyte = _resolved_scriptorium_effective_acolyte_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if scriptorium_effective_acolyte is not None:
        if _is_hired_source(scriptorium_effective_acolyte.source):
            try:
                state_for_sow, scriptorium_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=scriptorium_effective_acolyte.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=scriptorium_effective_acolyte.source,
                    payment=scriptorium_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        pre_sowing_events.append(
            _scriptorium_effective_acolyte_bonus_event(
                actor=player,
                action_id=transition_action_id,
            )
        )
        duty_relation_context = replace(
            duty_relation_context,
            uses_scriptorium=True,
        )

    customs_house_taxation = _resolved_customs_house_taxation_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if customs_house_taxation is not None:
        if _is_hired_source(customs_house_taxation.source):
            try:
                state_for_sow, customs_house_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=customs_house_taxation.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=customs_house_taxation.source,
                    payment=customs_house_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        pre_sowing_events.append(
            _customs_house_taxation_bonus_event(
                actor=player,
                action_id=transition_action_id,
            )
        )
        duty_relation_context = replace(
            duty_relation_context,
            uses_customs_house=True,
        )

    bank_payment = _resolved_bank_payment_for_action(
        state=state_for_sow,
        config=config,
        player=player,
        action=action,
    )
    if bank_payment is not None:
        if _is_hired_source(bank_payment.source):
            try:
                state_for_sow, bank_hire_payment = apply_building_hire_payment(
                    state_for_sow,
                    acting_player=player,
                    source=bank_payment.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            pre_sowing_events.append(
                _building_hired_event(
                    source=bank_payment.source,
                    payment=bank_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        pre_sowing_events.append(
            _bank_payment_bonus_event(
                actor=player,
                action_id=transition_action_id,
                replaced_resource=bank_payment.replaced_resource,
                silver_amount=bank_payment.silver_amount,
            )
        )

    if wagon_yard_free_hire is not None and wagon_yard_free_hire.target_was_temporary_added:
        state_for_sow = _state_without_temporary_active_building(
            state_for_sow,
            player=player,
            building_id=wagon_yard_free_hire.target_building_id,
        )

    player_vector = state_for_sow.player_vector(player)
    picked_up = player_vector[action.origin]
    if picked_up <= 0:
        raise TransitionValidationError("Sowing source must be occupied.")
    ensure_route_length_matches(picked_up=picked_up, route_length=len(action.route))

    try:
        sowed_vector = _sow_vector_with_optional_city_kogge(
            player_vector,
            origin=action.origin,
            route=action.route,
            board=config.board,
            allows_kogge_city_step=kogge_source is not None and kogge_source.usable,
            cloisters_omitted_location=(
                cloisters_route.omitted_location if cloisters_route is not None else None
            ),
            cloisters_with_kogge=(
                kogge_source is not None and cloisters_route is not None
            ),
        )
    except ValueError as exc:
        raise TransitionValidationError(str(exc)) from exc

    state_after_sow = state_for_sow.with_player_vector(player, sowed_vector)
    ensure_selected_duty_has_acolyte(
        state_after_sow,
        player=player,
        duty_position=action.selected_duty,
    )

    sowing_details = {
        "source": action.origin,
        "picked_up": picked_up,
        "route": "->".join(str(position) for position in action.route),
    }
    if cloisters_route is not None:
        sowing_details["skipped"] = cloisters_route.omitted_location
        sowing_details["route_modifier"] = _ROUTE_BUILDING_CLOISTERS

    events: list[GameEvent] = [
        *pre_sowing_events,
        GameEvent(
            event_type=EventType.SOWING,
            actor=player,
            action_id=transition_action_id,
            details=make_event_details(**sowing_details),
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

        if action.resolution is TurnResolutionType.TAXATION:
            strength = _taxation_duty_strength_for_position(
                state,
                config,
                player=player,
                duty_position=action.selected_duty,
                sowed_vector=sowed_vector,
                relation_context=duty_relation_context,
            )
        else:
            strength = _duty_strength_for_position(
                state,
                config,
                player=player,
                duty_position=action.selected_duty,
                sowed_vector=sowed_vector,
                relation_context=duty_relation_context,
            )
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

        def _resolution_costs_with_bank(
            *,
            required_stone: int = 0,
            required_silver: int = 0,
            required_wheat: int = 0,
            required_piety: int = 0,
        ) -> tuple[int, int, int, int]:
            if bank_payment is None:
                return (
                    max(0, required_stone),
                    max(0, required_silver),
                    max(0, required_wheat),
                    max(0, required_piety),
                )
            try:
                return _costs_with_bank_substitution(
                    required_stone=required_stone,
                    required_silver=required_silver,
                    required_wheat=required_wheat,
                    required_piety=required_piety,
                    replaced_resource=bank_payment.replaced_resource,
                    silver_amount=bank_payment.silver_amount,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc

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
        has_route_building_id = action.sow_route_building_id is not None
        has_route_building_source = action.sow_route_building_source is not None
        has_secondary_route_building_id = action.sow_route_secondary_building_id is not None
        has_secondary_route_building_source = (
            action.sow_route_secondary_building_source is not None
        )
        if has_route_building_id != has_route_building_source:
            raise TransitionValidationError(
                "sow_route_building_id and sow_route_building_source must be set together."
            )
        if has_secondary_route_building_id != has_secondary_route_building_source:
            raise TransitionValidationError(
                "sow_route_secondary_building_id/source must be set together."
            )
        if has_secondary_route_building_id and not has_route_building_id:
            raise TransitionValidationError(
                "Secondary sow-route fields require primary sow-route building fields."
            )
        if (
            action.sow_route_building_id is not None
            and action.sow_route_building_id
            not in (_ROUTE_BUILDING_KOGGE, _ROUTE_BUILDING_CLOISTERS)
        ):
            raise TransitionValidationError(
                "Only Kogge and Cloisters are supported for sow_route_building fields."
            )
        if (
            action.sow_route_secondary_building_id is not None
            and action.sow_route_secondary_building_id
            not in (_ROUTE_BUILDING_KOGGE, _ROUTE_BUILDING_CLOISTERS)
        ):
            raise TransitionValidationError(
                "Only Kogge and Cloisters are supported for secondary sow-route fields."
            )
        if (
            action.sow_route_building_id is not None
            and action.sow_route_secondary_building_id == action.sow_route_building_id
        ):
            raise TransitionValidationError(
                "sow-route primary and secondary building ids cannot be the same."
            )
        has_cloisters_route_modifier = (
            action.sow_route_building_id == _ROUTE_BUILDING_CLOISTERS
            or action.sow_route_secondary_building_id == _ROUTE_BUILDING_CLOISTERS
        )
        if not has_cloisters_route_modifier and action.sow_route_omitted_location is not None:
            raise TransitionValidationError(
                "sow_route_omitted_location requires a Cloisters sow-route modifier."
            )
        if has_cloisters_route_modifier and action.sow_route_omitted_location is None:
            raise TransitionValidationError(
                "Cloisters sow-route actions must set sow_route_omitted_location."
            )
        if (
            action.sow_route_secondary_building_id is not None
            and not (
                action.sow_route_building_id == _ROUTE_BUILDING_KOGGE
                and action.sow_route_secondary_building_id == _ROUTE_BUILDING_CLOISTERS
            )
        ):
            raise TransitionValidationError(
                "Combined sow-route actions must use primary Kogge and secondary Cloisters fields."
            )
        if (
            action.sow_route_building_id == _ROUTE_BUILDING_KOGGE
            and action.sow_route_omitted_location is not None
            and action.sow_route_secondary_building_id != _ROUTE_BUILDING_CLOISTERS
        ):
            raise TransitionValidationError(
                "Kogge actions may not set sow_route_omitted_location."
            )
        conversion_fields = (
            action.building_conversion_id,
            action.building_conversion_source,
            action.building_conversion_direction,
            action.building_conversion_amount,
        )
        conversion_field_count = sum(field is not None for field in conversion_fields)
        if conversion_field_count not in (0, len(conversion_fields)):
            raise TransitionValidationError(
                "building_conversion fields must be set together."
            )
        if conversion_field_count == len(conversion_fields):
            conversion_building_id = action.building_conversion_id
            if conversion_building_id not in (
                _BUILDING_GRAIN_STORE,
                _BUILDING_INDULGENCES,
                _BUILDING_STONE_YARD,
                _BUILDING_BREWERY,
            ):
                raise TransitionValidationError(
                    "Only Grain Store, Indulgences, Stone Yard, and Brewery are supported for building_conversion fields."
                )
            conversion_direction = action.building_conversion_direction
            if conversion_building_id == _BUILDING_GRAIN_STORE:
                if conversion_direction not in (
                    _GRAIN_STORE_BUY_WHEAT,
                    _GRAIN_STORE_SELL_WHEAT,
                ):
                    raise TransitionValidationError(
                        "Grain Store conversion direction must be buy_wheat or sell_wheat."
                    )
            elif conversion_building_id == _BUILDING_INDULGENCES and conversion_direction not in (
                _INDULGENCES_BUY_PIETY,
                _INDULGENCES_SELL_PIETY,
            ):
                raise TransitionValidationError(
                    "Indulgences conversion direction must be buy_piety or sell_piety."
                )
            elif conversion_building_id == _BUILDING_STONE_YARD and conversion_direction not in (
                _STONE_YARD_BUY_STONE,
                _STONE_YARD_SELL_STONE,
            ):
                raise TransitionValidationError(
                    "Stone Yard conversion direction must be buy_stone or sell_stone."
                )
            elif conversion_building_id == _BUILDING_BREWERY and conversion_direction != (
                _BREWERY_SELL_WHEAT_FOR_SILVER
            ):
                raise TransitionValidationError(
                    "Brewery conversion direction must be sell_wheat_for_silver."
                )
            amount = action.building_conversion_amount
            if amount is None or amount <= 0:
                if conversion_building_id == _BUILDING_GRAIN_STORE:
                    raise TransitionValidationError(
                        "Grain Store conversion amount must be at least 1."
                    )
                if conversion_building_id == _BUILDING_INDULGENCES:
                    raise TransitionValidationError(
                        "Indulgences conversion amount must be at least 1."
                    )
                if conversion_building_id == _BUILDING_BREWERY:
                    raise TransitionValidationError(
                        "Brewery conversion amount must be exactly 1."
                    )
                raise TransitionValidationError(
                    "Stone Yard conversion amount must be at least 1."
                )
            if conversion_building_id == _BUILDING_BREWERY and amount != 1:
                raise TransitionValidationError(
                    "Brewery conversion amount must be exactly 1."
                )
        bank_payment_fields = (
            action.bank_payment_building_id,
            action.bank_payment_building_source,
            action.bank_payment_replaced_resource,
            action.bank_payment_silver_amount,
        )
        bank_payment_field_count = sum(field is not None for field in bank_payment_fields)
        if bank_payment_field_count not in (0, len(bank_payment_fields)):
            raise TransitionValidationError(
                "bank_payment_building_id/source and bank_payment_replaced_resource/silver_amount must be set together."
            )
        has_bank_payment_modifier = bank_payment_field_count == len(bank_payment_fields)
        if has_bank_payment_modifier:
            if action.bank_payment_building_id != _BUILDING_BANK:
                raise TransitionValidationError(
                    "Only Bank is supported for bank_payment_building fields."
                )
            if action.bank_payment_replaced_resource not in _BANK_REPLACED_RESOURCES:
                replaced_text = ", ".join(_BANK_REPLACED_RESOURCES)
                raise TransitionValidationError(
                    "Bank replaced resource must be one of: "
                    f"{replaced_text}."
                )
            amount = action.bank_payment_silver_amount
            if amount is None or amount <= 0:
                raise TransitionValidationError(
                    "Bank silver substitution amount must be at least 1."
                )
            if action.resolution not in (
                TurnResolutionType.ORDINATION,
                TurnResolutionType.CONSTRUCT_BUILDING,
                TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
            ):
                raise TransitionValidationError(
                    "Bank payment substitution is only supported for Ordination and Construct building actions."
                )
            if conversion_field_count == len(conversion_fields):
                raise TransitionValidationError(
                    "Combining Bank payment substitution with building conversion modifiers is deferred."
                )
            if has_route_building_id or has_secondary_route_building_id:
                raise TransitionValidationError(
                    "Combining Bank payment substitution with sow-route modifiers is deferred."
                )
            if start_turn_relocation is not None:
                raise TransitionValidationError(
                    "Combining Bank payment substitution with start-turn relocation modifiers is deferred."
                )
        merchant_advance_fields = (
            action.merchant_advance_building_id,
            action.merchant_advance_building_source,
        )
        merchant_advance_field_count = sum(
            field is not None for field in merchant_advance_fields
        )
        if merchant_advance_field_count not in (0, len(merchant_advance_fields)):
            raise TransitionValidationError(
                "merchant_advance_building_id and merchant_advance_building_source must be set together."
            )
        has_guild_merchant_modifier = merchant_advance_field_count == len(
            merchant_advance_fields
        )
        if has_guild_merchant_modifier:
            if action.merchant_advance_building_id != _BUILDING_GUILD:
                raise TransitionValidationError(
                    "Only Guild is supported for merchant_advance_building fields."
                )
            if conversion_field_count == len(conversion_fields):
                raise TransitionValidationError(
                    "Combining Guild Merchant movement with building conversion modifiers is deferred."
                )
            if has_route_building_id or has_secondary_route_building_id:
                raise TransitionValidationError(
                    "Combining Guild Merchant movement with sow-route modifiers is deferred."
                )
            if start_turn_relocation is not None:
                raise TransitionValidationError(
                    "Combining Guild Merchant movement with start-turn relocation modifiers is deferred."
                )
        if has_guild_merchant_modifier and has_bank_payment_modifier:
            raise TransitionValidationError(
                "Combining Guild and Bank pre-sow building modifiers in one action is deferred."
            )
        effective_acolyte_fields = (
            action.effective_acolyte_building_id,
            action.effective_acolyte_building_source,
        )
        effective_acolyte_field_count = sum(
            field is not None for field in effective_acolyte_fields
        )
        if effective_acolyte_field_count not in (0, len(effective_acolyte_fields)):
            raise TransitionValidationError(
                "effective_acolyte_building_id and effective_acolyte_building_source must be set together."
            )
        has_scriptorium_effective_modifier = effective_acolyte_field_count == len(
            effective_acolyte_fields
        )
        if has_scriptorium_effective_modifier:
            if action.effective_acolyte_building_id != _BUILDING_SCRIPTORIUM:
                raise TransitionValidationError(
                    "Only Scriptorium is supported for effective_acolyte_building fields."
                )
            if conversion_field_count == len(conversion_fields):
                raise TransitionValidationError(
                    "Combining Scriptorium effective-acolyte modifier with building conversion modifiers is deferred."
                )
            if has_route_building_id or has_secondary_route_building_id:
                raise TransitionValidationError(
                    "Combining Scriptorium effective-acolyte modifier with sow-route modifiers is deferred."
                )
            if start_turn_relocation is not None:
                raise TransitionValidationError(
                    "Combining Scriptorium effective-acolyte modifier with start-turn relocation modifiers is deferred."
                )
            if has_guild_merchant_modifier:
                raise TransitionValidationError(
                    "Combining Guild and Scriptorium pre-sow building modifiers in one action is deferred."
                )
            if has_bank_payment_modifier:
                raise TransitionValidationError(
                    "Combining Bank and Scriptorium pre-sow building modifiers in one action is deferred."
                )
        taxation_majority_fields = (
            action.taxation_majority_building_id,
            action.taxation_majority_building_source,
        )
        taxation_majority_field_count = sum(
            field is not None for field in taxation_majority_fields
        )
        if taxation_majority_field_count not in (0, len(taxation_majority_fields)):
            raise TransitionValidationError(
                "taxation_majority_building_id and taxation_majority_building_source must be set together."
            )
        has_customs_house_taxation_modifier = taxation_majority_field_count == len(
            taxation_majority_fields
        )
        if has_customs_house_taxation_modifier:
            if action.taxation_majority_building_id != _BUILDING_CUSTOMS_HOUSE:
                raise TransitionValidationError(
                    "Only Customs House is supported for taxation_majority_building fields."
                )
            if action.resolution is not TurnResolutionType.TAXATION:
                raise TransitionValidationError(
                    "Customs House Taxation modifier can only be used with taxation actions."
                )
            if conversion_field_count == len(conversion_fields):
                raise TransitionValidationError(
                    "Combining Customs House Taxation modifier with building conversion modifiers is deferred."
                )
            if has_route_building_id or has_secondary_route_building_id:
                raise TransitionValidationError(
                    "Combining Customs House Taxation modifier with sow-route modifiers is deferred."
                )
            if start_turn_relocation is not None:
                raise TransitionValidationError(
                    "Combining Customs House Taxation modifier with start-turn relocation modifiers is deferred."
                )
            if has_guild_merchant_modifier:
                raise TransitionValidationError(
                    "Combining Guild and Customs House pre-sow building modifiers in one action is deferred."
                )
            if has_scriptorium_effective_modifier:
                raise TransitionValidationError(
                    "Combining Scriptorium and Customs House pre-sow building modifiers in one action is deferred."
                )
            if has_bank_payment_modifier:
                raise TransitionValidationError(
                    "Combining Bank and Customs House pre-sow building modifiers in one action is deferred."
                )
        free_hire_fields = (
            action.free_hire_enabler_building_id,
            action.free_hire_target_building_id,
            action.free_hire_target_building_source,
        )
        free_hire_field_count = sum(field is not None for field in free_hire_fields)
        if free_hire_field_count not in (0, len(free_hire_fields)):
            raise TransitionValidationError(
                "free_hire_enabler_building_id, free_hire_target_building_id, and free_hire_target_building_source must be set together."
            )
        has_wagon_yard_free_hire_modifier = free_hire_field_count == len(free_hire_fields)
        if has_wagon_yard_free_hire_modifier:
            if action.free_hire_enabler_building_id != _BUILDING_WAGON_YARD:
                raise TransitionValidationError(
                    "Only Wagon Yard is supported for free_hire_enabler_building_id."
                )
            target_building_id = action.free_hire_target_building_id
            target_source = action.free_hire_target_building_source
            assert target_building_id is not None
            assert target_source is not None
            if (
                target_building_id not in _WAGON_YARD_SUPPORTED_TARGET_BUILDINGS
                or target_building_id == _BUILDING_WAGON_YARD
            ):
                raise TransitionValidationError(
                    "Wagon Yard free-hire target building is unsupported."
                )
            if target_source in ("own_active", _player_label(player)):
                raise TransitionValidationError(
                    "Wagon Yard free-hire target source cannot be own active building."
                )
            opponent_labels = {_player_label(opponent) for opponent in _opponents(state, player)}
            if target_source != "market" and target_source not in opponent_labels:
                raise TransitionValidationError(
                    "Wagon Yard free-hire target source must be market or an opponent id."
                )
            if not _wagon_yard_own_active_is_usable(state, config):
                raise TransitionValidationError("Wagon Yard is unavailable in current state.")
            legal_target_sources = set(
                _wagon_yard_target_sources_for_building(
                    state,
                    config,
                    target_building_id=target_building_id,
                )
            )
            if target_source not in legal_target_sources:
                raise TransitionValidationError(
                    "Wagon Yard free-hire target source is unavailable in current state."
                )
            if not _wagon_yard_action_uses_target_building(
                action,
                target_building_id=target_building_id,
            ):
                raise TransitionValidationError(
                    "Wagon Yard free-hire action must use the selected target building effect."
                )
            if not _wagon_yard_action_is_supported_composition(
                action,
                target_building_id=target_building_id,
            ):
                raise TransitionValidationError(
                    "Combining Wagon Yard free-hire with additional hired/modifier effects is deferred."
                )
            if has_bank_payment_modifier and target_building_id != _BUILDING_BANK:
                raise TransitionValidationError(
                    "Bank payment substitution with Wagon Yard is only supported when Wagon Yard targets Bank."
                )
        workforce_move_fields = (
            action.workforce_move_building_id,
            action.workforce_move_building_source,
        )
        workforce_move_field_count = sum(
            field is not None for field in workforce_move_fields
        )
        if workforce_move_field_count not in (0, len(workforce_move_fields)):
            raise TransitionValidationError(
                "workforce_move_building_id and workforce_move_building_source must be set together."
            )
        has_pulpit_workforce_modifier = workforce_move_field_count == len(
            workforce_move_fields
        )
        if has_pulpit_workforce_modifier:
            if action.workforce_move_building_id != _BUILDING_PULPIT:
                raise TransitionValidationError(
                    "Only Pulpit is supported for workforce_move_building fields."
                )
            if conversion_field_count == len(conversion_fields):
                raise TransitionValidationError(
                    "Combining Pulpit free serf movement with building conversion modifiers is deferred."
                )
            if has_route_building_id or has_secondary_route_building_id:
                raise TransitionValidationError(
                    "Combining Pulpit free serf movement with sow-route modifiers is deferred."
                )
            if start_turn_relocation is not None:
                raise TransitionValidationError(
                    "Combining Pulpit free serf movement with start-turn relocation modifiers is deferred."
                )
            if has_bank_payment_modifier:
                raise TransitionValidationError(
                    "Combining Bank and Pulpit pre-sow building modifiers in one action is deferred."
                )
        if has_guild_merchant_modifier and has_pulpit_workforce_modifier:
            raise TransitionValidationError(
                "Combining Guild and Pulpit pre-sow building modifiers in one action is deferred."
            )
        if has_scriptorium_effective_modifier and has_pulpit_workforce_modifier:
            raise TransitionValidationError(
                "Combining Pulpit and Scriptorium pre-sow building modifiers in one action is deferred."
            )
        if has_customs_house_taxation_modifier and has_pulpit_workforce_modifier:
            raise TransitionValidationError(
                "Combining Pulpit and Customs House pre-sow building modifiers in one action is deferred."
            )
        if has_bank_payment_modifier and has_pulpit_workforce_modifier:
            raise TransitionValidationError(
                "Combining Bank and Pulpit pre-sow building modifiers in one action is deferred."
            )
        end_turn_fields = (
            action.end_turn_building_id,
            action.end_turn_building_source,
            action.end_turn_relocation_from,
            action.end_turn_relocation_to,
        )
        end_turn_field_count = sum(field is not None for field in end_turn_fields)
        if end_turn_field_count not in (0, len(end_turn_fields)):
            raise TransitionValidationError(
                "end_turn_building_id/source and end_turn_relocation_from/to must be set together."
            )
        if (
            end_turn_field_count == len(end_turn_fields)
            and action.end_turn_building_id != "library"
        ):
            raise TransitionValidationError(
                "Only Library is supported for end-turn relocation fields."
            )
        if has_guild_merchant_modifier and end_turn_field_count == len(end_turn_fields):
            raise TransitionValidationError(
                "Combining Guild Merchant movement with end-turn relocation modifiers is deferred."
            )
        if has_scriptorium_effective_modifier and end_turn_field_count == len(end_turn_fields):
            raise TransitionValidationError(
                "Combining Scriptorium effective-acolyte modifier with end-turn relocation modifiers is deferred."
            )
        if has_pulpit_workforce_modifier and end_turn_field_count == len(end_turn_fields):
            raise TransitionValidationError(
                "Combining Pulpit free serf movement with end-turn relocation modifiers is deferred."
            )
        if has_customs_house_taxation_modifier and end_turn_field_count == len(end_turn_fields):
            raise TransitionValidationError(
                "Combining Customs House Taxation modifier with end-turn relocation modifiers is deferred."
            )
        if has_bank_payment_modifier and end_turn_field_count == len(end_turn_fields):
            raise TransitionValidationError(
                "Combining Bank payment substitution with end-turn relocation modifiers is deferred."
            )

        hire_context = BuildingHireTurnContext()
        if (action.hired_building_id is None) != (action.hired_building_source is None):
            raise TransitionValidationError(
                "hired_building_id and hired_building_source must be set together."
            )
        if action.hired_building_id is not None:
            if has_guild_merchant_modifier:
                raise TransitionValidationError(
                    "Combining Guild Merchant movement with resolution-level hired building fields is deferred."
                )
            if has_bank_payment_modifier:
                raise TransitionValidationError(
                    "Combining Bank payment substitution with resolution-level hired building fields is deferred."
                )
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
        if (
            has_guild_merchant_modifier
            and action.merchant_advance_building_source is not None
            and action.merchant_advance_building_source != "own_active"
        ):
            if not can_hire_building_this_turn(hire_context, building_key=_BUILDING_GUILD):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=_BUILDING_GUILD,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            has_scriptorium_effective_modifier
            and action.effective_acolyte_building_source is not None
            and action.effective_acolyte_building_source != "own_active"
        ):
            if not can_hire_building_this_turn(
                hire_context, building_key=_BUILDING_SCRIPTORIUM
            ):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=_BUILDING_SCRIPTORIUM,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            has_customs_house_taxation_modifier
            and action.taxation_majority_building_source is not None
            and action.taxation_majority_building_source != "own_active"
        ):
            if not can_hire_building_this_turn(
                hire_context, building_key=_BUILDING_CUSTOMS_HOUSE
            ):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=_BUILDING_CUSTOMS_HOUSE,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            has_pulpit_workforce_modifier
            and action.workforce_move_building_source is not None
            and action.workforce_move_building_source != "own_active"
        ):
            if not can_hire_building_this_turn(hire_context, building_key=_BUILDING_PULPIT):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=_BUILDING_PULPIT,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            has_bank_payment_modifier
            and action.bank_payment_building_source is not None
            and action.bank_payment_building_source != "own_active"
        ):
            if not can_hire_building_this_turn(hire_context, building_key=_BUILDING_BANK):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=_BUILDING_BANK,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        route_hire_entries: list[tuple[str, str]] = []
        if action.sow_route_building_id is not None and action.sow_route_building_source is not None:
            route_hire_entries.append(
                (
                    action.sow_route_building_id,
                    action.sow_route_building_source,
                )
            )
        if (
            action.sow_route_secondary_building_id is not None
            and action.sow_route_secondary_building_source is not None
        ):
            route_hire_entries.append(
                (
                    action.sow_route_secondary_building_id,
                    action.sow_route_secondary_building_source,
                )
            )
        for building_key, source_label in route_hire_entries:
            if source_label == "own_active":
                continue
            if not can_hire_building_this_turn(hire_context, building_key=building_key):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=building_key,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            action.building_conversion_id in (
                _BUILDING_GRAIN_STORE,
                _BUILDING_INDULGENCES,
                _BUILDING_STONE_YARD,
                _BUILDING_BREWERY,
            )
            and action.building_conversion_source is not None
            and action.building_conversion_source != "own_active"
        ):
            assert action.building_conversion_id is not None
            if not can_hire_building_this_turn(
                hire_context,
                building_key=action.building_conversion_id,
            ):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=action.building_conversion_id,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            start_turn_relocation is not None
            and start_turn_relocation.source.source_type != "own_active"
        ):
            if not can_hire_building_this_turn(
                hire_context,
                building_key=start_turn_relocation.building_id,
            ):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key=start_turn_relocation.building_id,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
        if (
            action.end_turn_building_id == "library"
            and action.end_turn_building_source != "own_active"
        ):
            if not can_hire_building_this_turn(hire_context, building_key="library"):
                raise TransitionValidationError(
                    "Same building cannot be hired more than once in one turn."
                )
            try:
                hire_context = record_hired_building_this_turn(
                    hire_context,
                    building_key="library",
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
                resolution_resource_delta_baseline,
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
            try:
                construct_definition = config.buildings.definition_by_id(
                    action.construct_building_id
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            stone_cost = construct_definition.stone_cost
            (
                adjusted_stone_cost,
                adjusted_silver_cost,
                _adjusted_wheat_cost,
                _adjusted_piety_cost,
            ) = _resolution_costs_with_bank(
                required_stone=stone_cost,
                required_silver=silver_cost,
            )

            new_player_state = state_after_sow.player_state(player)
            if not _can_afford_resolution_costs(
                new_player_state,
                required_stone=adjusted_stone_cost,
                required_silver=adjusted_silver_cost,
            ):
                raise TransitionValidationError(
                    "Construct costs are not affordable for this action."
                )
            bank_stone_substitution = stone_cost - adjusted_stone_cost
            if bank_stone_substitution:
                new_player_state = replace(
                    new_player_state,
                    resources=new_player_state.resources.add(stone=bank_stone_substitution),
                )
            if adjusted_silver_cost:
                new_resources = new_player_state.resources.add(silver=-adjusted_silver_cost)
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

            resource_delta = (-adjusted_stone_cost, -adjusted_silver_cost, 0)
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
            try:
                construct_definition = config.buildings.definition_by_id(
                    action.construct_building_id
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            stone_cost = construct_definition.stone_cost
            (
                adjusted_stone_cost,
                adjusted_silver_cost,
                _adjusted_wheat_cost,
                _adjusted_piety_cost,
            ) = _resolution_costs_with_bank(
                required_stone=stone_cost,
                required_silver=silver_cost,
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
            if not _can_afford_resolution_costs(
                new_player_state,
                required_stone=adjusted_stone_cost,
                required_silver=adjusted_silver_cost,
            ):
                raise TransitionValidationError(
                    "Construct costs are not affordable for this action."
                )
            bank_stone_substitution = stone_cost - adjusted_stone_cost
            if bank_stone_substitution:
                new_player_state = replace(
                    new_player_state,
                    resources=new_player_state.resources.add(stone=bank_stone_substitution),
                )
            if adjusted_silver_cost:
                new_resources = new_player_state.resources.add(silver=-adjusted_silver_cost)
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

            resource_delta = (-adjusted_stone_cost, -adjusted_silver_cost, 0)
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
            (
                _adjusted_stone_cost,
                adjusted_silver_cost,
                adjusted_wheat_cost,
                _adjusted_piety_cost,
            ) = _resolution_costs_with_bank(
                required_silver=silver_cost,
                required_wheat=mill_actual_wheat_spent,
            )
            bank_wheat_credit = mill_actual_wheat_spent - adjusted_wheat_cost
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
            if not _can_afford_resolution_costs(
                new_player_state,
                required_silver=adjusted_silver_cost,
                required_wheat=adjusted_wheat_cost,
            ):
                raise TransitionValidationError(
                    "Ordination costs are not affordable for this action."
                )
            if mill_waiver or bank_wheat_credit:
                new_player_state = replace(
                    new_player_state,
                    resources=new_player_state.resources.add(
                        wheat=(mill_waiver + bank_wheat_credit)
                    ),
                )
            remaining_no_wheat_steps = mill_waiver + bank_wheat_credit
            remaining_bank_paid_steps = bank_wheat_credit
            for step in action.ordination_steps:
                wheat_paid = 0 if remaining_no_wheat_steps > 0 else 1
                bank_silver_paid = 0
                if wheat_paid == 0 and remaining_bank_paid_steps > 0:
                    bank_silver_paid = 1
                try:
                    new_player_state = apply_ordination_step(new_player_state, step)
                except ValueError as exc:
                    raise TransitionValidationError(str(exc)) from exc
                if remaining_no_wheat_steps > 0:
                    remaining_no_wheat_steps -= 1
                if bank_silver_paid:
                    remaining_bank_paid_steps -= 1
                if step == ORDINATION_ORDAIN:
                    ordain_details = {
                        "step": ORDINATION_ORDAIN,
                        "from_pool": "village",
                        "to_pool": "abbey",
                        "unit": "serf",
                        "amount": 1,
                        "wheat_paid": wheat_paid,
                    }
                    if bank_silver_paid:
                        ordain_details["bank_silver_paid"] = bank_silver_paid
                    special_bonus_events.append(
                        GameEvent(
                            event_type=EventType.ORDINATION,
                            actor=player,
                            action_id=transition_action_id,
                            details=make_event_details(**ordain_details),
                        )
                    )
                elif step == ORDINATION_MISSION:
                    mission_details = {
                        "step": ORDINATION_MISSION,
                        "from_pool": "abbey",
                        "to_pool": "city",
                        "unit": "acolyte",
                        "amount": 1,
                        "wheat_paid": wheat_paid,
                    }
                    if bank_silver_paid:
                        mission_details["bank_silver_paid"] = bank_silver_paid
                    special_bonus_events.append(
                        GameEvent(
                            event_type=EventType.ORDINATION,
                            actor=player,
                            action_id=transition_action_id,
                            details=make_event_details(**mission_details),
                        )
                    )
                else:
                    raise TransitionValidationError(f"Unknown ordination step: {step}")

            if adjusted_silver_cost:
                new_resources = new_player_state.resources.add(silver=-adjusted_silver_cost)
                if new_resources.silver < 0:
                    raise TransitionValidationError(
                        "Ordination minority silver cost would overdraw silver."
                    )
                new_player_state = replace(new_player_state, resources=new_resources)

            state_after_resolution = state_for_ordination.with_player_state(player, new_player_state)
            resource_delta = _resource_delta_between(
                resolution_resource_delta_baseline,
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
                relation_context=duty_relation_context,
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
                resolution_resource_delta_baseline,
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
                    resolution_resource_delta_baseline,
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
                    resolution_resource_delta_baseline,
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

    end_turn_relocation = _resolved_end_turn_relocation_for_action(
        state=updated_state,
        config=config,
        player=player,
        action=action,
    )
    if end_turn_relocation is not None:
        if _is_hired_source(end_turn_relocation.source):
            try:
                updated_state, end_turn_hire_payment = apply_building_hire_payment(
                    updated_state,
                    acting_player=player,
                    source=end_turn_relocation.source,
                )
            except ValueError as exc:
                raise TransitionValidationError(str(exc)) from exc
            _refresh_resource_delta_event(
                events,
                actor=player,
                action_id=transition_action_id,
                before_resources=resolution_resource_delta_baseline,
                after_resources=updated_state.player_state(player).resources,
            )
            events.append(
                _building_hired_event(
                    source=end_turn_relocation.source,
                    payment=end_turn_hire_payment,
                    actor=player,
                    action_id=transition_action_id,
                    config=config,
                )
            )
        events.append(
            _end_turn_building_bonus_event(
                actor=player,
                action_id=transition_action_id,
                relocation=end_turn_relocation,
            )
        )
        updated_state = _apply_end_turn_relocation_to_state(
            updated_state,
            player=player,
            relocation=end_turn_relocation,
        )
        events.append(
            _end_turn_relocation_event(
                actor=player,
                action_id=transition_action_id,
                relocation=end_turn_relocation,
                config=config,
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
            action=action,
        )
        events.extend(round_end_events)
        if not next_state.game_over:
            events.append(
                _turn_advance_event(
                    actor=player,
                    action_id=transition_action_id,
                    from_player=player,
                    to_player=next_state.active_player,
                )
            )
    else:
        events.extend(timing_result.events)

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
                **_invariant_workforce_details(next_state),
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
    action: FullTurnAction,
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

    # 2) Ship (round-marker) advance and completed-rounds tracking.
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

    full_loop_nw_return = ship_at_nw and next_state.completed_rounds >= config.ship.path_length
    projected_round_after_advance = completed_round_number + 1
    projected_pilgrimage_site_index = _pilgrimage_site_index_for_round_number(
        next_state,
        projected_round_after_advance,
    )

    # Legacy full-loop game end still applies, but if the next round is a configured
    # pilgrimage round then that season-end block must resolve before GAME_END.
    if full_loop_nw_return and projected_pilgrimage_site_index is None:
        _ensure_no_start_player_confession_box_uses_before_game_end(action)
        next_state = next_state.with_game_over(True)
        events.append(
            GameEvent(
                event_type=EventType.GAME_END,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    reason=(
                        "ship returned to NW Pilgrimage Site after full 26-round loop"
                    )
                ),
            )
        )
        return next_state, tuple(events)

    # 3) Round advance.
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

    # 4) Season-end Alms scoring from metadata pilgrimage rounds.
    season_site_index = _pilgrimage_site_index_for_round(next_state)
    if season_site_index is not None:
        alms_result = resolve_alms_season_end(
            next_state,
            config.alms,
            actor=actor,
            action_id=action_id,
            round_number=next_state.timing.round_number,
            season_site_index=season_site_index,
        )
        next_state = alms_result.state
        events.extend(alms_result.events)
        next_state = resolve_season_end(next_state, config.timing)
        if _is_final_season_site(next_state, season_site_index=season_site_index):
            _ensure_no_start_player_confession_box_uses_before_game_end(action)
            next_state = next_state.with_game_over(True)
            events.append(
                GameEvent(
                    event_type=EventType.GAME_END,
                    actor=actor,
                    action_id=action_id,
                    details=make_event_details(
                        reason=(
                            "fourth season ended after pilgrimage site 4"
                        )
                    ),
                )
            )
            return next_state, tuple(events)

    if full_loop_nw_return:
        _ensure_no_start_player_confession_box_uses_before_game_end(action)
        next_state = next_state.with_game_over(True)
        events.append(
            GameEvent(
                event_type=EventType.GAME_END,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    reason=(
                        "ship returned to NW Pilgrimage Site after full 26-round loop"
                    )
                ),
            )
        )
        return next_state, tuple(events)

    # 5) Merchant advances once at round end.
    if config.merchant.advance_at_round_end:
        from_duty = current_merchant_duty(next_state, config)
        next_merchant_position = advance_merchant_position(
        next_state.merchant_board_position,
        config,
    )
        next_state = next_state.with_merchant_board_position(next_merchant_position)
        to_duty = current_merchant_duty(next_state, config)
        current_resource = current_merchant_resource(next_state, config)
        events.append(
            _merchant_advance_event(
                actor=actor,
                action_id=action_id,
                from_duty=from_duty,
                to_duty=to_duty,
                to_position=merchant_position_name(next_merchant_position, config),
                current_resource=current_resource,
            )
        )

    # 6) Trade-route income from Merchant's current resource.
    next_state, trade_route_income_events = resolve_trade_route_income(
        next_state,
        config=config,
        actor=actor,
        action_id=action_id,
    )
    events.extend(trade_route_income_events)

    # 7) Start-player placeholder policy.
    next_state, start_player_events, _ = select_next_start_player(
        next_state,
        config=config,
        actor=actor,
        action_id=action_id,
        confession_box_uses=action.start_player_confession_box_uses,
    )
    events.extend(start_player_events)
    return next_state, tuple(events)


def _pilgrimage_site_index_for_round(state: GameState) -> int | None:
    return _pilgrimage_site_index_for_round_number(state, state.timing.round_number)


def _ensure_no_start_player_confession_box_uses_before_game_end(
    action: FullTurnAction,
) -> None:
    if not action.start_player_confession_box_uses:
        return
    raise TransitionValidationError(
        "Confession Box start-player directives are invalid when game ends before start-player selection."
    )


def _pilgrimage_site_index_for_round_number(state: GameState, round_number: int) -> int | None:
    if not state.pilgrimage_rounds:
        return None
    for index, pilgrimage_round in enumerate(state.pilgrimage_rounds, start=1):
        if round_number == pilgrimage_round:
            return index
    return None


def _is_final_season_site(state: GameState, *, season_site_index: int) -> bool:
    if not state.pilgrimage_rounds:
        return False
    return season_site_index >= 4


def _turn_advance_event(
    *,
    actor: PlayerId,
    action_id: str,
    from_player: PlayerId,
    to_player: PlayerId,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.TURN_ADVANCE,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            from_player=from_player.name.lower(),
            to_player=to_player.name.lower(),
        ),
    )


def _player_label(player: PlayerId) -> str:
    return player.name.lower()


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


def _legal_start_turn_relocation_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_StartTurnRelocationOption | None, ...]:
    options: list[_StartTurnRelocationOption | None] = [None]
    options.extend(_legal_dormitory_relocation_options(state, config))
    options.extend(_legal_inquisition_relocation_options(state, config))
    return tuple(options)


def _legal_dormitory_relocation_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_StartTurnRelocationOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="dormitory",
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = _state_after_optional_start_turn_hire_payment(
        state,
        player=state.active_player,
        source=source,
    )
    if state_after_hire is None:
        return ()

    city_position = config.board.index_for_name("city")
    player_vector = state_after_hire.player_vector(state.active_player)
    options: list[_StartTurnRelocationOption] = []
    for duty_position in config.duty_positions():
        if player_vector[duty_position] <= 0:
            continue
        relocated_vector = _relocate_one_acolyte_in_mancala_vector(
            player_vector,
            from_position=duty_position,
            to_position=city_position,
        )
        options.append(
            _StartTurnRelocationOption(
                state=state_after_hire.with_player_vector(state.active_player, relocated_vector),
                building_id="dormitory",
                source=source,
                from_position=duty_position,
                to_position=city_position,
            )
        )
    return tuple(options)


def _legal_inquisition_relocation_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_StartTurnRelocationOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="inquisition",
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = _state_after_optional_start_turn_hire_payment(
        state,
        player=state.active_player,
        source=source,
    )
    if state_after_hire is None:
        return ()

    city_position = config.board.index_for_name("city")
    player_vector = state_after_hire.player_vector(state.active_player)
    if player_vector[city_position] <= 0:
        return ()

    options: list[_StartTurnRelocationOption] = []
    for duty_position in config.duty_positions():
        relocated_vector = _relocate_one_acolyte_in_mancala_vector(
            player_vector,
            from_position=city_position,
            to_position=duty_position,
        )
        options.append(
            _StartTurnRelocationOption(
                state=state_after_hire.with_player_vector(state.active_player, relocated_vector),
                building_id="inquisition",
                source=source,
                from_position=city_position,
                to_position=duty_position,
            )
        )
    return tuple(options)


def _state_after_optional_start_turn_hire_payment(
    state: GameState,
    *,
    player: PlayerId,
    source: BuildingAbilitySource,
) -> GameState | None:
    if not _is_hired_source(source):
        return state
    try:
        paid_state, _payment = apply_building_hire_payment(
            state,
            acting_player=player,
            source=source,
        )
    except ValueError:
        return None
    return paid_state


def _with_start_turn_relocation_fields(
    action: FullTurnAction,
    *,
    option: _StartTurnRelocationOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        start_turn_building_id=option.building_id,
        start_turn_building_source=source_label,
        start_turn_relocation_from=option.from_position,
        start_turn_relocation_to=option.to_position,
    )


def _resolved_library_source_for_state(
    state: GameState,
    config: GameConfig,
) -> BuildingAbilitySource | None:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="library",
    )
    if not source.usable:
        return None
    if source.source_type == "own_active" or _is_hired_source(source):
        return source
    return None


def _library_suffix_variants_for_action(
    *,
    original_state: GameState,
    state_for_turn: GameState,
    config: GameConfig,
    action: FullTurnAction,
    source: BuildingAbilitySource,
) -> tuple[FullTurnAction, ...]:
    if source.building_key != "library":
        return ()
    city_position = config.board.index_for_name("city")
    city_acolytes = _city_acolytes_after_action_for_end_turn(
        state_for_turn,
        config,
        action=action,
    )
    if city_acolytes <= 0:
        return ()

    variants: list[FullTurnAction] = []
    for target in _library_end_turn_targets(config):
        candidate = _with_end_turn_library_relocation_fields(
            action,
            source=source,
            from_position=city_position,
            to_target=target,
        )
        if not _is_action_apply_legal(
            original_state,
            candidate,
            config,
        ):
            continue
        variants.append(candidate)
    return tuple(variants)


def _library_end_turn_targets(config: GameConfig) -> tuple[int | str, ...]:
    return (*config.duty_positions(), _LIBRARY_ABBEY_TARGET)


def _city_acolytes_after_action_for_end_turn(
    state: GameState,
    config: GameConfig,
    *,
    action: FullTurnAction,
) -> int:
    player = state.active_player
    player_vector = state.player_vector(player)
    picked_up = player_vector[action.origin]
    if picked_up <= 0 or len(action.route) != picked_up:
        return 0

    try:
        cloisters_route = _resolved_cloisters_route_for_action(
            state=state,
            config=config,
            player=player,
            action=action,
        )
    except TransitionValidationError:
        return 0
    try:
        kogge_source = _resolved_kogge_source_for_action(
            state=state,
            config=config,
            player=player,
            action=action,
        )
    except TransitionValidationError:
        return 0
    try:
        sowed_vector = _sow_vector_with_optional_city_kogge(
            player_vector,
            origin=action.origin,
            route=action.route,
            board=config.board,
            allows_kogge_city_step=kogge_source is not None and kogge_source.usable,
            cloisters_omitted_location=(
                cloisters_route.omitted_location if cloisters_route is not None else None
            ),
            cloisters_with_kogge=(
                kogge_source is not None and cloisters_route is not None
            ),
        )
    except ValueError:
        return 0

    city_position = config.board.index_for_name("city")
    city_count = sowed_vector[city_position]
    if action.resolution is TurnResolutionType.TITHE:
        return city_count

    city_count += sowed_vector[action.selected_duty]
    if action.resolution is TurnResolutionType.ORDINATION:
        city_count += sum(1 for step in action.ordination_steps if step == ORDINATION_MISSION)
    return city_count


def _with_end_turn_library_relocation_fields(
    action: FullTurnAction,
    *,
    source: BuildingAbilitySource,
    from_position: int,
    to_target: int | str,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if source.source_type == "own_active"
        else _hired_building_source_label(source)
    )
    return replace(
        action,
        end_turn_building_id="library",
        end_turn_building_source=source_label,
        end_turn_relocation_from=from_position,
        end_turn_relocation_to=to_target,
    )


def _is_action_apply_legal(
    state: GameState,
    action: FullTurnAction,
    config: GameConfig,
) -> bool:
    try:
        apply_action(state, action, config)
    except TransitionValidationError:
        return False
    return True


def _relocate_one_acolyte_in_mancala_vector(
    vector: tuple[int, ...],
    *,
    from_position: int,
    to_position: int,
) -> tuple[int, ...]:
    if from_position < 0 or from_position >= len(vector):
        raise ValueError(f"Invalid from_position: {from_position}")
    if to_position < 0 or to_position >= len(vector):
        raise ValueError(f"Invalid to_position: {to_position}")
    if vector[from_position] <= 0:
        raise ValueError("Cannot relocate acolyte from an empty mancala position.")

    updated = list(vector)
    updated[from_position] -= 1
    updated[to_position] += 1
    return tuple(updated)


def _legal_sow_routes_for_origin(
    state: GameState,
    config: GameConfig,
    *,
    origin: int,
    picked_up: int,
) -> tuple[_SowRouteOption, ...]:
    routes: list[_SowRouteOption] = []
    if picked_up <= 0:
        return ()

    kogge_source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key="kogge",
    )
    if origin == config.board.index_for_name("city") and kogge_source.usable and (
        kogge_source.source_type == "own_active" or _is_hired_source(kogge_source)
    ):
        routes.extend(
            _SowRouteOption(
                route=route,
                building_id=_ROUTE_BUILDING_KOGGE,
                source=kogge_source,
            )
            for route in kogge_city_start_routes(
                origin=origin,
                picked_up=picked_up,
                board=config.board,
            )
        )

    routes.extend(
        _SowRouteOption(route=route)
        for route in normal_sow_routes(
            origin=origin,
            picked_up=picked_up,
            board=config.board,
        )
    )
    routes.extend(
        _legal_cloisters_route_options(
            state,
            config,
            origin=origin,
            picked_up=picked_up,
        )
    )
    routes.extend(
        _legal_combined_kogge_cloisters_route_options(
            state,
            config,
            origin=origin,
            picked_up=picked_up,
        )
    )
    return tuple(routes)


def _legal_cloisters_route_options(
    state: GameState,
    config: GameConfig,
    *,
    origin: int,
    picked_up: int,
) -> tuple[_SowRouteOption, ...]:
    if picked_up <= 0:
        return ()

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_ROUTE_BUILDING_CLOISTERS,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    return tuple(
        _SowRouteOption(
            route=variant.route,
            building_id=_ROUTE_BUILDING_CLOISTERS,
            source=source,
            omitted_location=variant.omitted_location,
        )
        for variant in cloisters_route_variants(
            origin=origin,
            picked_up=picked_up,
            board=config.board,
        )
    )


def _legal_combined_kogge_cloisters_route_options(
    state: GameState,
    config: GameConfig,
    *,
    origin: int,
    picked_up: int,
) -> tuple[_SowRouteOption, ...]:
    if picked_up <= 0:
        return ()

    kogge_source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_ROUTE_BUILDING_KOGGE,
    )
    if not kogge_source.usable or (
        kogge_source.source_type != "own_active" and not _is_hired_source(kogge_source)
    ):
        return ()

    cloisters_source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_ROUTE_BUILDING_CLOISTERS,
    )
    if not cloisters_source.usable or (
        cloisters_source.source_type != "own_active" and not _is_hired_source(cloisters_source)
    ):
        return ()

    return tuple(
        _SowRouteOption(
            route=variant.route,
            building_id=_ROUTE_BUILDING_KOGGE,
            source=kogge_source,
            secondary_building_id=_ROUTE_BUILDING_CLOISTERS,
            secondary_source=cloisters_source,
            omitted_location=variant.omitted_location,
        )
        for variant in combined_kogge_cloisters_route_variants(
            origin=origin,
            picked_up=picked_up,
            board=config.board,
        )
    )


def _with_kogge_route_fields(
    action: FullTurnAction,
    *,
    source: BuildingAbilitySource,
) -> FullTurnAction:
    if source.source_type == "own_active":
        return replace(
            action,
            sow_route_building_id="kogge",
            sow_route_building_source="own_active",
        )
    if _is_hired_source(source):
        return replace(
            action,
            sow_route_building_id="kogge",
            sow_route_building_source=_hired_building_source_label(source),
        )
    raise ValueError("Kogge route source must be own-active or hired.")


def _with_cloisters_route_fields(
    action: FullTurnAction,
    *,
    source: BuildingAbilitySource,
    omitted_location: int,
) -> FullTurnAction:
    if source.source_type == "own_active":
        return replace(
            action,
            sow_route_building_id=_ROUTE_BUILDING_CLOISTERS,
            sow_route_building_source="own_active",
            sow_route_omitted_location=omitted_location,
        )
    if _is_hired_source(source):
        return replace(
            action,
            sow_route_building_id=_ROUTE_BUILDING_CLOISTERS,
            sow_route_building_source=_hired_building_source_label(source),
            sow_route_omitted_location=omitted_location,
        )
    raise ValueError("Cloisters route source must be own-active or hired.")


def _with_secondary_cloisters_route_fields(
    action: FullTurnAction,
    *,
    source: BuildingAbilitySource,
    omitted_location: int,
) -> FullTurnAction:
    if source.source_type == "own_active":
        return replace(
            action,
            sow_route_secondary_building_id=_ROUTE_BUILDING_CLOISTERS,
            sow_route_secondary_building_source="own_active",
            sow_route_omitted_location=omitted_location,
        )
    if _is_hired_source(source):
        return replace(
            action,
            sow_route_secondary_building_id=_ROUTE_BUILDING_CLOISTERS,
            sow_route_secondary_building_source=_hired_building_source_label(source),
            sow_route_omitted_location=omitted_location,
        )
    raise ValueError("Cloisters secondary route source must be own-active or hired.")


def _with_route_option_fields(
    action: FullTurnAction,
    *,
    option: _SowRouteOption,
) -> FullTurnAction:
    updated = action
    if option.building_id == _ROUTE_BUILDING_KOGGE:
        if option.source is None:
            raise ValueError("Kogge route option missing source.")
        updated = _with_kogge_route_fields(
            updated,
            source=option.source,
        )
    elif option.building_id == _ROUTE_BUILDING_CLOISTERS:
        if option.source is None:
            raise ValueError("Cloisters route option missing source.")
        omitted_location = option.omitted_location
        if omitted_location is None:
            raise ValueError("Cloisters route option missing omitted location.")
        updated = _with_cloisters_route_fields(
            updated,
            source=option.source,
            omitted_location=omitted_location,
        )

    if option.secondary_building_id is None:
        return updated

    if option.secondary_building_id != _ROUTE_BUILDING_CLOISTERS:
        raise ValueError(
            "Only Cloisters is supported as secondary sow-route modifier in this milestone."
        )
    if option.secondary_source is None:
        raise ValueError("Secondary Cloisters route option missing source.")
    omitted_location = option.omitted_location
    if omitted_location is None:
        raise ValueError("Secondary Cloisters route option missing omitted location.")
    return _with_secondary_cloisters_route_fields(
        updated,
        source=option.secondary_source,
        omitted_location=omitted_location,
    )


def _legal_grain_store_conversion_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_BuildingConversionOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_GRAIN_STORE,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _hire_payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    player_state = state_after_hire.player_state(state.active_player)
    resources = player_state.resources
    options: list[_BuildingConversionOption] = []

    for amount in range(1, resources.wheat + 1):
        converted_state = state_after_hire.with_player_state(
            state.active_player,
            replace(
                player_state,
                resources=resources.add(wheat=-amount, silver=amount),
            ),
        )
        options.append(
            _BuildingConversionOption(
                state=converted_state,
                building_id=_BUILDING_GRAIN_STORE,
                source=source,
                direction=_GRAIN_STORE_SELL_WHEAT,
                amount=amount,
            )
        )

    for amount in range(1, resources.silver + 1):
        converted_state = state_after_hire.with_player_state(
            state.active_player,
            replace(
                player_state,
                resources=resources.add(silver=-amount, wheat=amount),
            ),
        )
        options.append(
            _BuildingConversionOption(
                state=converted_state,
                building_id=_BUILDING_GRAIN_STORE,
                source=source,
                direction=_GRAIN_STORE_BUY_WHEAT,
                amount=amount,
            )
        )

    return tuple(options)


def _legal_indulgences_conversion_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_BuildingConversionOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_INDULGENCES,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _hire_payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    player_state = state_after_hire.player_state(state.active_player)
    resources = player_state.resources
    piety_position = player_state.piety
    piety_space = max(0, config.piety.max_position - piety_position)
    options: list[_BuildingConversionOption] = []

    for amount in range(1, piety_position + 1):
        converted_state = state_after_hire.with_player_state(
            state.active_player,
            replace(
                player_state,
                piety=piety_position - amount,
                resources=resources.add(silver=amount),
            ),
        )
        options.append(
            _BuildingConversionOption(
                state=converted_state,
                building_id=_BUILDING_INDULGENCES,
                source=source,
                direction=_INDULGENCES_SELL_PIETY,
                amount=amount,
            )
        )

    max_buy_amount = min(resources.silver, piety_space)
    for amount in range(1, max_buy_amount + 1):
        converted_state = state_after_hire.with_player_state(
            state.active_player,
            replace(
                player_state,
                piety=piety_position + amount,
                resources=resources.add(silver=-amount),
            ),
        )
        options.append(
            _BuildingConversionOption(
                state=converted_state,
                building_id=_BUILDING_INDULGENCES,
                source=source,
                direction=_INDULGENCES_BUY_PIETY,
                amount=amount,
            )
        )

    return tuple(options)


def _legal_stone_yard_conversion_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_BuildingConversionOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_STONE_YARD,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _hire_payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    player_state = state_after_hire.player_state(state.active_player)
    resources = player_state.resources
    options: list[_BuildingConversionOption] = []

    for amount in range(1, resources.stone + 1):
        converted_state = state_after_hire.with_player_state(
            state.active_player,
            replace(
                player_state,
                resources=resources.add(stone=-amount, silver=amount),
            ),
        )
        options.append(
            _BuildingConversionOption(
                state=converted_state,
                building_id=_BUILDING_STONE_YARD,
                source=source,
                direction=_STONE_YARD_SELL_STONE,
                amount=amount,
            )
        )

    for amount in range(1, resources.silver + 1):
        converted_state = state_after_hire.with_player_state(
            state.active_player,
            replace(
                player_state,
                resources=resources.add(silver=-amount, stone=amount),
            ),
        )
        options.append(
            _BuildingConversionOption(
                state=converted_state,
                building_id=_BUILDING_STONE_YARD,
                source=source,
                direction=_STONE_YARD_BUY_STONE,
                amount=amount,
            )
        )

    return tuple(options)


def _legal_brewery_conversion_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_BuildingConversionOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_BREWERY,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _hire_payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    player_state = state_after_hire.player_state(state.active_player)
    resources = player_state.resources
    if resources.wheat < 1:
        return ()

    converted_state = state_after_hire.with_player_state(
        state.active_player,
        replace(
            player_state,
            resources=resources.add(wheat=-1, silver=2),
        ),
    )
    return (
        _BuildingConversionOption(
            state=converted_state,
            building_id=_BUILDING_BREWERY,
            source=source,
            direction=_BREWERY_SELL_WHEAT_FOR_SILVER,
            amount=1,
        ),
    )


def _costs_with_bank_substitution(
    *,
    required_stone: int = 0,
    required_silver: int = 0,
    required_wheat: int = 0,
    required_piety: int = 0,
    replaced_resource: str | None = None,
    silver_amount: int = 0,
) -> tuple[int, int, int, int]:
    adjusted_stone = max(0, required_stone)
    adjusted_silver = max(0, required_silver)
    adjusted_wheat = max(0, required_wheat)
    adjusted_piety = max(0, required_piety)

    if replaced_resource is None:
        if silver_amount != 0:
            raise ValueError("Bank silver_amount requires a replaced_resource.")
        return adjusted_stone, adjusted_silver, adjusted_wheat, adjusted_piety

    if replaced_resource not in _BANK_REPLACED_RESOURCES:
        raise ValueError(f"Unsupported Bank replaced resource: {replaced_resource}.")
    if silver_amount <= 0:
        raise ValueError("Bank substitution amount must be at least 1.")

    if replaced_resource == "stone":
        if silver_amount > adjusted_stone:
            raise ValueError("Bank substitution exceeds required stone.")
        adjusted_stone -= silver_amount
    elif replaced_resource == "wheat":
        if silver_amount > adjusted_wheat:
            raise ValueError("Bank substitution exceeds required wheat.")
        adjusted_wheat -= silver_amount
    elif replaced_resource == "piety":
        if silver_amount > adjusted_piety:
            raise ValueError("Bank substitution exceeds required piety.")
        adjusted_piety -= silver_amount

    adjusted_silver += silver_amount
    return adjusted_stone, adjusted_silver, adjusted_wheat, adjusted_piety


def _legal_bank_payment_options_for_action(
    *,
    state: GameState,
    config: GameConfig,
    required_stone: int = 0,
    required_silver: int = 0,
    required_wheat: int = 0,
    required_piety: int = 0,
    hired_source: BuildingAbilitySource | None = None,
) -> tuple[_BankPaymentOption, ...]:
    if max(required_stone, required_wheat, required_piety) <= 0:
        return ()

    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_BANK,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    player_state = state_after_hire.player_state(state.active_player)
    substitutions: list[_BankPaymentOption] = []
    required_amounts = {
        "stone": max(0, required_stone),
        "wheat": max(0, required_wheat),
        "piety": max(0, required_piety),
    }
    for replaced_resource, required_amount in required_amounts.items():
        if required_amount <= 0:
            continue
        max_substitution = min(required_amount, player_state.resources.silver)
        for silver_amount in range(1, max_substitution + 1):
            (
                adjusted_stone,
                adjusted_silver,
                adjusted_wheat,
                adjusted_piety,
            ) = _costs_with_bank_substitution(
                required_stone=required_stone,
                required_silver=required_silver,
                required_wheat=required_wheat,
                required_piety=required_piety,
                replaced_resource=replaced_resource,
                silver_amount=silver_amount,
            )
            if not _can_afford_resolution_costs(
                player_state,
                required_stone=adjusted_stone,
                required_silver=adjusted_silver,
                required_wheat=adjusted_wheat,
                required_piety=adjusted_piety,
                hired_source=hired_source,
            ):
                continue
            substitutions.append(
                _BankPaymentOption(
                    state=state_after_hire,
                    building_id=_BUILDING_BANK,
                    source=source,
                    replaced_resource=replaced_resource,
                    silver_amount=silver_amount,
                )
            )
    return tuple(substitutions)


def _legal_guild_merchant_advance_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_GuildMerchantAdvanceOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_GUILD,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()
    if _is_hired_source(source):
        try:
            _paid_state, _payment = apply_building_hire_payment(
                state,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()
    return (
        _GuildMerchantAdvanceOption(
            building_id=_BUILDING_GUILD,
            source=source,
        ),
    )


def _legal_scriptorium_effective_acolyte_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_ScriptoriumEffectiveAcolyteOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_SCRIPTORIUM,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    return (
        _ScriptoriumEffectiveAcolyteOption(
            state=state_after_hire,
            building_id=_BUILDING_SCRIPTORIUM,
            source=source,
        ),
    )


def _legal_customs_house_taxation_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_CustomsHouseTaxationOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_CUSTOMS_HOUSE,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    return (
        _CustomsHouseTaxationOption(
            state=state_after_hire,
            building_id=_BUILDING_CUSTOMS_HOUSE,
            source=source,
        ),
    )


def _legal_wagon_yard_free_hire_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_WagonYardFreeHireOption, ...]:
    if not _wagon_yard_own_active_is_usable(state, config):
        return ()

    options: list[_WagonYardFreeHireOption] = []
    for target_building_id in sorted(_WAGON_YARD_SUPPORTED_TARGET_BUILDINGS):
        if target_building_id == _BUILDING_WAGON_YARD:
            continue
        for target_source in _wagon_yard_target_sources_for_building(
            state,
            config,
            target_building_id=target_building_id,
        ):
            borrowed_state, _temporarily_added = _state_with_temporary_active_building(
                state,
                player=state.active_player,
                building_id=target_building_id,
            )
            options.append(
                _WagonYardFreeHireOption(
                    state=borrowed_state,
                    target_building_id=target_building_id,
                    target_source=target_source,
                )
            )
    return tuple(options)


def _legal_pulpit_workforce_move_options(
    state: GameState,
    config: GameConfig,
) -> tuple[_PulpitWorkforceMoveOption, ...]:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_PULPIT,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        return ()

    state_after_hire = state
    if _is_hired_source(source):
        try:
            state_after_hire, _payment = apply_building_hire_payment(
                state_after_hire,
                acting_player=state.active_player,
                source=source,
            )
        except ValueError:
            return ()

    player_state = state_after_hire.player_state(state.active_player)
    if player_state.workforce.village < 1:
        return ()
    moved_workforce = replace(
        player_state.workforce,
        village=player_state.workforce.village - 1,
        abbey=player_state.workforce.abbey + 1,
    )
    moved_state = state_after_hire.with_player_state(
        state.active_player,
        replace(player_state, workforce=moved_workforce),
    )
    return (
        _PulpitWorkforceMoveOption(
            state=moved_state,
            building_id=_BUILDING_PULPIT,
            source=source,
        ),
    )


def _state_after_guild_merchant_advance_for_legal_generation(
    state: GameState,
    *,
    option: _GuildMerchantAdvanceOption,
    config: GameConfig,
) -> GameState:
    state_after_hire = state
    if _is_hired_source(option.source):
        state_after_hire, _payment = apply_building_hire_payment(
            state_after_hire,
            acting_player=state.active_player,
            source=option.source,
        )
    next_merchant_position = advance_merchant_position(
        state_after_hire.merchant_board_position,
        config,
    )
    return state_after_hire.with_merchant_board_position(next_merchant_position)


def _wagon_yard_own_active_is_usable(
    state: GameState,
    config: GameConfig,
) -> bool:
    source = building_ability_source(
        state,
        config,
        acting_player=state.active_player,
        building_key=_BUILDING_WAGON_YARD,
    )
    if source.source_type != "own_active" or not source.usable:
        return False
    if (
        building_live_round(state, _BUILDING_WAGON_YARD) is not None
        and not is_building_live(state, _BUILDING_WAGON_YARD)
    ):
        return False
    return True


def _wagon_yard_target_sources_for_building(
    state: GameState,
    config: GameConfig,
    *,
    target_building_id: str,
) -> tuple[str, ...]:
    if target_building_id not in _WAGON_YARD_SUPPORTED_TARGET_BUILDINGS:
        return ()
    if target_building_id == _BUILDING_WAGON_YARD:
        return ()

    player_slots = state.player_state(state.active_player).player_board_slots
    if (
        target_building_id in player_slots.active_buildings
        or target_building_id in player_slots.donated_buildings
    ):
        return ()
    if any(
        target_building_id in state.player_state(candidate).player_board_slots.donated_buildings
        for candidate in (PlayerId(index) for index in range(state.player_count))
    ):
        return ()

    sources: list[str] = []
    if (
        target_building_id in state.building_market
        and is_building_live(state, target_building_id)
    ):
        sources.append("market")

    for opponent in _opponents(state, state.active_player):
        opponent_slots = state.player_state(opponent).player_board_slots
        if target_building_id not in opponent_slots.active_buildings:
            continue
        if (
            building_live_round(state, target_building_id) is not None
            and not is_building_live(state, target_building_id)
        ):
            continue
        sources.append(_player_label(opponent))
    return tuple(sources)


def _state_with_temporary_active_building(
    state: GameState,
    *,
    player: PlayerId,
    building_id: str,
) -> tuple[GameState, bool]:
    player_state = state.player_state(player)
    if building_id in player_state.player_board_slots.active_buildings:
        return state, False
    updated_slots = replace(
        player_state.player_board_slots,
        active_buildings=(*player_state.player_board_slots.active_buildings, building_id),
    )
    return (
        state.with_player_state(
            player,
            replace(player_state, player_board_slots=updated_slots),
        ),
        True,
    )


def _state_without_temporary_active_building(
    state: GameState,
    *,
    player: PlayerId,
    building_id: str,
) -> GameState:
    player_state = state.player_state(player)
    if building_id not in player_state.player_board_slots.active_buildings:
        return state
    updated_slots = replace(
        player_state.player_board_slots,
        active_buildings=tuple(
            current_building
            for current_building in player_state.player_board_slots.active_buildings
            if current_building != building_id
        ),
    )
    return state.with_player_state(
        player,
        replace(player_state, player_board_slots=updated_slots),
    )


def _is_guild_modifier_eligible_action(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id is None
        and action.sow_route_secondary_building_id is None
        and action.sow_route_omitted_location is None
        and action.building_conversion_id is None
        and action.hired_building_id is None
        and action.start_turn_building_id is None
        and action.end_turn_building_id is None
        and action.merchant_advance_building_id is None
        and action.merchant_advance_building_source is None
        and action.workforce_move_building_id is None
        and action.workforce_move_building_source is None
        and action.effective_acolyte_building_id is None
        and action.effective_acolyte_building_source is None
        and action.taxation_majority_building_id is None
        and action.taxation_majority_building_source is None
        and action.bank_payment_building_id is None
        and action.bank_payment_building_source is None
        and action.bank_payment_replaced_resource is None
        and action.bank_payment_silver_amount is None
        and action.free_hire_enabler_building_id is None
        and action.free_hire_target_building_id is None
        and action.free_hire_target_building_source is None
    )


def _is_pulpit_modifier_eligible_action(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id is None
        and action.sow_route_secondary_building_id is None
        and action.sow_route_omitted_location is None
        and action.building_conversion_id is None
        and action.start_turn_building_id is None
        and action.end_turn_building_id is None
        and action.merchant_advance_building_id is None
        and action.merchant_advance_building_source is None
        and action.workforce_move_building_id is None
        and action.workforce_move_building_source is None
        and action.effective_acolyte_building_id is None
        and action.effective_acolyte_building_source is None
        and action.taxation_majority_building_id is None
        and action.taxation_majority_building_source is None
        and action.bank_payment_building_id is None
        and action.bank_payment_building_source is None
        and action.bank_payment_replaced_resource is None
        and action.bank_payment_silver_amount is None
        and action.free_hire_enabler_building_id is None
        and action.free_hire_target_building_id is None
        and action.free_hire_target_building_source is None
    )


def _is_scriptorium_modifier_eligible_action(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id is None
        and action.sow_route_secondary_building_id is None
        and action.sow_route_omitted_location is None
        and action.building_conversion_id is None
        and action.start_turn_building_id is None
        and action.end_turn_building_id is None
        and action.merchant_advance_building_id is None
        and action.merchant_advance_building_source is None
        and action.workforce_move_building_id is None
        and action.workforce_move_building_source is None
        and action.effective_acolyte_building_id is None
        and action.effective_acolyte_building_source is None
        and action.taxation_majority_building_id is None
        and action.taxation_majority_building_source is None
        and action.bank_payment_building_id is None
        and action.bank_payment_building_source is None
        and action.bank_payment_replaced_resource is None
        and action.bank_payment_silver_amount is None
        and action.free_hire_enabler_building_id is None
        and action.free_hire_target_building_id is None
        and action.free_hire_target_building_source is None
    )


def _is_customs_house_modifier_eligible_action(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id is None
        and action.sow_route_secondary_building_id is None
        and action.sow_route_omitted_location is None
        and action.building_conversion_id is None
        and action.start_turn_building_id is None
        and action.end_turn_building_id is None
        and action.merchant_advance_building_id is None
        and action.merchant_advance_building_source is None
        and action.workforce_move_building_id is None
        and action.workforce_move_building_source is None
        and action.effective_acolyte_building_id is None
        and action.effective_acolyte_building_source is None
        and action.taxation_majority_building_id is None
        and action.taxation_majority_building_source is None
        and action.bank_payment_building_id is None
        and action.bank_payment_building_source is None
        and action.bank_payment_replaced_resource is None
        and action.bank_payment_silver_amount is None
        and action.free_hire_enabler_building_id is None
        and action.free_hire_target_building_id is None
        and action.free_hire_target_building_source is None
    )


def _is_bank_modifier_eligible_action(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id is None
        and action.sow_route_secondary_building_id is None
        and action.sow_route_omitted_location is None
        and action.building_conversion_id is None
        and action.start_turn_building_id is None
        and action.end_turn_building_id is None
        and action.hired_building_id is None
        and action.hired_building_source is None
        and action.merchant_advance_building_id is None
        and action.merchant_advance_building_source is None
        and action.workforce_move_building_id is None
        and action.workforce_move_building_source is None
        and action.effective_acolyte_building_id is None
        and action.effective_acolyte_building_source is None
        and action.taxation_majority_building_id is None
        and action.taxation_majority_building_source is None
        and action.bank_payment_building_id is None
        and action.bank_payment_building_source is None
        and action.bank_payment_replaced_resource is None
        and action.bank_payment_silver_amount is None
        and action.free_hire_enabler_building_id is None
        and action.free_hire_target_building_id is None
        and action.free_hire_target_building_source is None
    )


def _scriptorium_can_affect_action(action: FullTurnAction) -> bool:
    """Return True when Scriptorium can change this action's outcome."""
    return action.resolution not in (
        TurnResolutionType.TITHE,
        TurnResolutionType.GIVE_ALMS_DONATE_BUILDING,
    )


def _customs_house_can_affect_action(action: FullTurnAction) -> bool:
    """Return True when Customs House can change this action's outcome."""
    return action.resolution is TurnResolutionType.TAXATION


def _wagon_yard_action_uses_target_building(
    action: FullTurnAction,
    *,
    target_building_id: str,
) -> bool:
    if target_building_id in (
        _BUILDING_GRAIN_STORE,
        _BUILDING_INDULGENCES,
        _BUILDING_STONE_YARD,
        _BUILDING_BREWERY,
    ):
        return (
            action.building_conversion_id == target_building_id
            and action.building_conversion_source == "own_active"
        )
    if target_building_id == _BUILDING_GUILD:
        return (
            action.merchant_advance_building_id == _BUILDING_GUILD
            and action.merchant_advance_building_source == "own_active"
        )
    if target_building_id == _BUILDING_PULPIT:
        return (
            action.workforce_move_building_id == _BUILDING_PULPIT
            and action.workforce_move_building_source == "own_active"
        )
    if target_building_id == _BUILDING_SCRIPTORIUM:
        return (
            action.effective_acolyte_building_id == _BUILDING_SCRIPTORIUM
            and action.effective_acolyte_building_source == "own_active"
        )
    if target_building_id == _BUILDING_CUSTOMS_HOUSE:
        return (
            action.taxation_majority_building_id == _BUILDING_CUSTOMS_HOUSE
            and action.taxation_majority_building_source == "own_active"
        )
    if target_building_id == _BUILDING_BANK:
        return (
            action.bank_payment_building_id == _BUILDING_BANK
            and action.bank_payment_building_source == "own_active"
        )
    return False


def _wagon_yard_action_is_supported_composition(
    action: FullTurnAction,
    *,
    target_building_id: str,
) -> bool:
    if action.start_turn_building_id is not None or action.end_turn_building_id is not None:
        return False
    if action.sow_route_building_id is not None or action.sow_route_secondary_building_id is not None:
        return False
    if action.hired_building_id is not None or action.hired_building_source is not None:
        return False

    if target_building_id != _BUILDING_GUILD and action.merchant_advance_building_id is not None:
        return False
    if target_building_id != _BUILDING_PULPIT and action.workforce_move_building_id is not None:
        return False
    if target_building_id != _BUILDING_SCRIPTORIUM and action.effective_acolyte_building_id is not None:
        return False
    if target_building_id != _BUILDING_CUSTOMS_HOUSE and action.taxation_majority_building_id is not None:
        return False
    if target_building_id != _BUILDING_BANK and action.bank_payment_building_id is not None:
        return False
    if (
        target_building_id
        not in (
            _BUILDING_GRAIN_STORE,
            _BUILDING_INDULGENCES,
            _BUILDING_STONE_YARD,
            _BUILDING_BREWERY,
        )
        and action.building_conversion_id is not None
    ):
        return False
    if target_building_id == _BUILDING_BANK and action.building_conversion_id is not None:
        return False
    if (
        target_building_id == _BUILDING_BANK
        and action.bank_payment_replaced_resource not in _BANK_REPLACED_RESOURCES
    ):
        return False
    if target_building_id == _BUILDING_BANK and (
        action.bank_payment_silver_amount is None or action.bank_payment_silver_amount <= 0
    ):
        return False
    return True


def _with_guild_merchant_advance_fields(
    action: FullTurnAction,
    *,
    option: _GuildMerchantAdvanceOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        merchant_advance_building_id=option.building_id,
        merchant_advance_building_source=source_label,
    )


def _with_scriptorium_effective_acolyte_fields(
    action: FullTurnAction,
    *,
    option: _ScriptoriumEffectiveAcolyteOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        effective_acolyte_building_id=option.building_id,
        effective_acolyte_building_source=source_label,
    )


def _with_customs_house_taxation_fields(
    action: FullTurnAction,
    *,
    option: _CustomsHouseTaxationOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        taxation_majority_building_id=option.building_id,
        taxation_majority_building_source=source_label,
    )


def _with_wagon_yard_free_hire_fields(
    action: FullTurnAction,
    *,
    option: _WagonYardFreeHireOption,
) -> FullTurnAction:
    return replace(
        action,
        free_hire_enabler_building_id=_BUILDING_WAGON_YARD,
        free_hire_target_building_id=option.target_building_id,
        free_hire_target_building_source=option.target_source,
    )


def _with_pulpit_workforce_move_fields(
    action: FullTurnAction,
    *,
    option: _PulpitWorkforceMoveOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        workforce_move_building_id=option.building_id,
        workforce_move_building_source=source_label,
    )


def _with_grain_store_conversion_fields(
    action: FullTurnAction,
    *,
    option: _BuildingConversionOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        building_conversion_id=option.building_id,
        building_conversion_source=source_label,
        building_conversion_direction=option.direction,
        building_conversion_amount=option.amount,
    )


def _with_bank_payment_fields(
    action: FullTurnAction,
    *,
    option: _BankPaymentOption,
) -> FullTurnAction:
    source_label = (
        "own_active"
        if option.source.source_type == "own_active"
        else _hired_building_source_label(option.source)
    )
    return replace(
        action,
        bank_payment_building_id=option.building_id,
        bank_payment_building_source=source_label,
        bank_payment_replaced_resource=option.replaced_resource,
        bank_payment_silver_amount=option.silver_amount,
    )


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


def _resolved_start_turn_relocation_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedStartTurnRelocation | None:
    fields = (
        action.start_turn_building_id,
        action.start_turn_building_source,
        action.start_turn_relocation_from,
        action.start_turn_relocation_to,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "start_turn_building_id/source and start_turn_relocation_from/to must be set together."
        )

    building_id = action.start_turn_building_id
    source_label = action.start_turn_building_source
    from_position = action.start_turn_relocation_from
    to_position = action.start_turn_relocation_to
    assert building_id is not None
    assert source_label is not None
    assert from_position is not None
    assert to_position is not None

    if building_id not in ("dormitory", "inquisition"):
        raise TransitionValidationError(
            "Only Dormitory and Inquisition are supported for start-turn relocation fields."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=building_id,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                f"{building_id} is own-active; start_turn_building_source must be own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "start_turn_building_source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError(
            f"{building_id} is not usable for start-turn relocation in current state."
        )

    city_position = config.board.index_for_name("city")
    duty_positions = set(config.duty_positions())
    player_vector = state.player_vector(player)

    if building_id == "dormitory":
        if from_position not in duty_positions or from_position == city_position:
            raise TransitionValidationError(
                "Dormitory relocation source must be a non-city Duty tile."
            )
        if to_position != city_position:
            raise TransitionValidationError("Dormitory relocation target must be City.")
        if player_vector[from_position] <= 0:
            raise TransitionValidationError(
                "Dormitory relocation source must contain at least one acting-player acolyte."
            )
    else:
        if from_position != city_position:
            raise TransitionValidationError("Inquisition relocation source must be City.")
        if to_position not in duty_positions or to_position == city_position:
            raise TransitionValidationError(
                "Inquisition relocation target must be a non-city Duty tile."
            )
        if player_vector[city_position] <= 0:
            raise TransitionValidationError(
                "Inquisition relocation requires at least one acting-player acolyte in City."
            )

    return _ResolvedStartTurnRelocation(
        building_id=building_id,
        source=source,
        from_position=from_position,
        to_position=to_position,
    )


def _resolved_end_turn_relocation_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedEndTurnRelocation | None:
    fields = (
        action.end_turn_building_id,
        action.end_turn_building_source,
        action.end_turn_relocation_from,
        action.end_turn_relocation_to,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "end_turn_building_id/source and end_turn_relocation_from/to must be set together."
        )

    building_id = action.end_turn_building_id
    source_label = action.end_turn_building_source
    from_position = action.end_turn_relocation_from
    to_target = action.end_turn_relocation_to
    assert building_id is not None
    assert source_label is not None
    assert from_position is not None
    assert to_target is not None

    if building_id != "library":
        raise TransitionValidationError(
            "Only Library is supported for end-turn relocation fields."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=building_id,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                "Library is own-active; end_turn_building_source must be own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "end_turn_building_source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError(
            "Library is not usable for end-turn relocation in current state."
        )

    city_position = config.board.index_for_name("city")
    if from_position != city_position:
        raise TransitionValidationError("Library relocation source must be City.")

    duty_positions = set(config.duty_positions())
    to_pool: str
    to_position: int | None
    if isinstance(to_target, str):
        normalized_target = (
            to_target.strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if normalized_target != _LIBRARY_ABBEY_TARGET:
            raise TransitionValidationError(
                "Library relocation target must be Abbey or a non-city Duty tile."
            )
        to_pool = _LIBRARY_ABBEY_TARGET
        to_position = None
    elif isinstance(to_target, int) and not isinstance(to_target, bool):
        if to_target not in duty_positions or to_target == city_position:
            raise TransitionValidationError(
                "Library relocation target must be Abbey or a non-city Duty tile."
            )
        to_pool = config.board.positions[to_target]
        to_position = to_target
    else:
        raise TransitionValidationError(
            "Library relocation target must be Abbey or a non-city Duty tile."
        )

    player_vector = state.player_vector(player)
    if player_vector[city_position] <= 0:
        raise TransitionValidationError(
            "Library relocation requires at least one acting-player acolyte in City."
        )

    return _ResolvedEndTurnRelocation(
        building_id=building_id,
        source=source,
        from_position=city_position,
        to_position=to_position,
        to_pool=to_pool,
    )


def _apply_end_turn_relocation_to_state(
    state: GameState,
    *,
    player: PlayerId,
    relocation: _ResolvedEndTurnRelocation,
) -> GameState:
    player_state = state.player_state(player)
    player_vector = player_state.workforce.mancala
    if player_vector[relocation.from_position] <= 0:
        raise TransitionValidationError(
            "Library relocation requires at least one acting-player acolyte in City."
        )

    if relocation.to_pool == _LIBRARY_ABBEY_TARGET:
        updated_vector = list(player_vector)
        updated_vector[relocation.from_position] -= 1
        updated_workforce = replace(
            player_state.workforce,
            mancala=tuple(updated_vector),
            abbey=player_state.workforce.abbey + 1,
        )
        updated_player_state = replace(player_state, workforce=updated_workforce)
        return state.with_player_state(player, updated_player_state)

    to_position = relocation.to_position
    if to_position is None:
        raise TransitionValidationError("Library Duty target position is missing.")
    relocated_vector = _relocate_one_acolyte_in_mancala_vector(
        player_vector,
        from_position=relocation.from_position,
        to_position=to_position,
    )
    return state.with_player_vector(player, relocated_vector)


def _route_requires_kogge(action: FullTurnAction, config: GameConfig) -> bool:
    return _route_requires_kogge_for_origin_route(
        origin=action.origin,
        route=action.route,
        board=config.board,
    )


def _action_has_route_building(action: FullTurnAction, building_id: str) -> bool:
    return (
        action.sow_route_building_id == building_id
        or action.sow_route_secondary_building_id == building_id
    )


def _action_route_building_source_label(
    action: FullTurnAction,
    *,
    building_id: str,
) -> str | None:
    if action.sow_route_building_id == building_id:
        return action.sow_route_building_source
    if action.sow_route_secondary_building_id == building_id:
        return action.sow_route_secondary_building_source
    return None


def _resolved_guild_merchant_advance_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedGuildMerchantAdvance | None:
    fields = (
        action.merchant_advance_building_id,
        action.merchant_advance_building_source,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "merchant_advance_building_id and merchant_advance_building_source must be set together."
        )

    building_id = action.merchant_advance_building_id
    source_label = action.merchant_advance_building_source
    assert building_id is not None
    assert source_label is not None

    if building_id != _BUILDING_GUILD:
        raise TransitionValidationError(
            "Only Guild is supported for merchant_advance_building fields."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_BUILDING_GUILD,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                "Own-active Guild merchant movement must set source=own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "Guild merchant movement source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError("Guild is unavailable in current state.")

    return _ResolvedGuildMerchantAdvance(
        building_id=_BUILDING_GUILD,
        source=source,
    )


def _resolved_scriptorium_effective_acolyte_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedScriptoriumEffectiveAcolyte | None:
    fields = (
        action.effective_acolyte_building_id,
        action.effective_acolyte_building_source,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "effective_acolyte_building_id and effective_acolyte_building_source must be set together."
        )

    building_id = action.effective_acolyte_building_id
    source_label = action.effective_acolyte_building_source
    assert building_id is not None
    assert source_label is not None

    if building_id != _BUILDING_SCRIPTORIUM:
        raise TransitionValidationError(
            "Only Scriptorium is supported for effective_acolyte_building fields."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_BUILDING_SCRIPTORIUM,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                "Own-active Scriptorium modifier must set source=own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "Scriptorium modifier source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError("Scriptorium is unavailable in current state.")

    return _ResolvedScriptoriumEffectiveAcolyte(
        building_id=_BUILDING_SCRIPTORIUM,
        source=source,
    )


def _resolved_customs_house_taxation_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedCustomsHouseTaxation | None:
    fields = (
        action.taxation_majority_building_id,
        action.taxation_majority_building_source,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "taxation_majority_building_id and taxation_majority_building_source must be set together."
        )

    building_id = action.taxation_majority_building_id
    source_label = action.taxation_majority_building_source
    assert building_id is not None
    assert source_label is not None

    if action.resolution is not TurnResolutionType.TAXATION:
        raise TransitionValidationError(
            "Customs House Taxation modifier can only be used with taxation actions."
        )

    if building_id != _BUILDING_CUSTOMS_HOUSE:
        raise TransitionValidationError(
            "Only Customs House is supported for taxation_majority_building fields."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_BUILDING_CUSTOMS_HOUSE,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                "Own-active Customs House Taxation modifier must set source=own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "Customs House Taxation modifier source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError("Customs House is unavailable in current state.")

    return _ResolvedCustomsHouseTaxation(
        building_id=_BUILDING_CUSTOMS_HOUSE,
        source=source,
    )


def _resolved_bank_payment_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedBankPayment | None:
    fields = (
        action.bank_payment_building_id,
        action.bank_payment_building_source,
        action.bank_payment_replaced_resource,
        action.bank_payment_silver_amount,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "bank_payment_building_id/source and bank_payment_replaced_resource/silver_amount must be set together."
        )

    building_id = action.bank_payment_building_id
    source_label = action.bank_payment_building_source
    replaced_resource = action.bank_payment_replaced_resource
    silver_amount = action.bank_payment_silver_amount
    assert building_id is not None
    assert source_label is not None
    assert replaced_resource is not None
    assert silver_amount is not None

    if building_id != _BUILDING_BANK:
        raise TransitionValidationError(
            "Only Bank is supported for bank_payment_building fields."
        )
    if replaced_resource not in _BANK_REPLACED_RESOURCES:
        replaced_text = ", ".join(_BANK_REPLACED_RESOURCES)
        raise TransitionValidationError(
            "Bank replaced resource must be one of: "
            f"{replaced_text}."
        )
    if silver_amount <= 0:
        raise TransitionValidationError("Bank silver substitution amount must be at least 1.")
    if action.resolution not in (
        TurnResolutionType.ORDINATION,
        TurnResolutionType.CONSTRUCT_BUILDING,
        TurnResolutionType.CONSTRUCT_BUILDING_AND_ROAD_DEFERRED,
    ):
        raise TransitionValidationError(
            "Bank payment substitution is only supported for Ordination and Construct building actions."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_BUILDING_BANK,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                "Own-active Bank payment substitution must set source=own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "Bank payment substitution source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError("Bank is unavailable in current state.")

    return _ResolvedBankPayment(
        building_id=_BUILDING_BANK,
        source=source,
        replaced_resource=replaced_resource,
        silver_amount=silver_amount,
    )


def _resolved_wagon_yard_free_hire_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedWagonYardFreeHire | None:
    fields = (
        action.free_hire_enabler_building_id,
        action.free_hire_target_building_id,
        action.free_hire_target_building_source,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "free_hire_enabler_building_id, free_hire_target_building_id, and free_hire_target_building_source must be set together."
        )

    enabler_building_id = action.free_hire_enabler_building_id
    target_building_id = action.free_hire_target_building_id
    target_source = action.free_hire_target_building_source
    assert enabler_building_id is not None
    assert target_building_id is not None
    assert target_source is not None

    if enabler_building_id != _BUILDING_WAGON_YARD:
        raise TransitionValidationError(
            "Only Wagon Yard is supported for free_hire_enabler_building_id."
        )
    if (
        target_building_id not in _WAGON_YARD_SUPPORTED_TARGET_BUILDINGS
        or target_building_id == _BUILDING_WAGON_YARD
    ):
        raise TransitionValidationError("Wagon Yard free-hire target building is unsupported.")
    if target_source in ("own_active", _player_label(player)):
        raise TransitionValidationError(
            "Wagon Yard free-hire target source cannot be own active building."
        )
    if not _wagon_yard_own_active_is_usable(state, config):
        raise TransitionValidationError("Wagon Yard is unavailable in current state.")

    legal_sources = set(
        _wagon_yard_target_sources_for_building(
            state,
            config,
            target_building_id=target_building_id,
        )
    )
    if target_source not in legal_sources:
        raise TransitionValidationError(
            "Wagon Yard free-hire target source is unavailable in current state."
        )
    if not _wagon_yard_action_uses_target_building(
        action,
        target_building_id=target_building_id,
    ):
        raise TransitionValidationError(
            "Wagon Yard free-hire action must use the selected target building effect."
        )
    if not _wagon_yard_action_is_supported_composition(
        action,
        target_building_id=target_building_id,
    ):
        raise TransitionValidationError(
            "Combining Wagon Yard free-hire with additional hired/modifier effects is deferred."
        )

    target_was_temporary_added = (
        target_building_id
        not in state.player_state(player).player_board_slots.active_buildings
    )
    return _ResolvedWagonYardFreeHire(
        enabler_building_id=_BUILDING_WAGON_YARD,
        target_building_id=target_building_id,
        target_source=target_source,
        target_was_temporary_added=target_was_temporary_added,
    )


def _resolved_pulpit_workforce_move_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedPulpitWorkforceMove | None:
    fields = (
        action.workforce_move_building_id,
        action.workforce_move_building_source,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "workforce_move_building_id and workforce_move_building_source must be set together."
        )

    building_id = action.workforce_move_building_id
    source_label = action.workforce_move_building_source
    assert building_id is not None
    assert source_label is not None

    if building_id != _BUILDING_PULPIT:
        raise TransitionValidationError(
            "Only Pulpit is supported for workforce_move_building fields."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_BUILDING_PULPIT,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                "Own-active Pulpit free move must set source=own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "Pulpit free move source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError("Pulpit is unavailable in current state.")

    return _ResolvedPulpitWorkforceMove(
        building_id=_BUILDING_PULPIT,
        source=source,
    )


def _resolved_grain_store_conversion_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedGrainStoreConversion | None:
    fields = (
        action.building_conversion_id,
        action.building_conversion_source,
        action.building_conversion_direction,
        action.building_conversion_amount,
    )
    field_count = sum(field is not None for field in fields)
    if field_count == 0:
        return None
    if field_count != len(fields):
        raise TransitionValidationError(
            "building_conversion fields must be set together."
        )

    building_id = action.building_conversion_id
    source_label = action.building_conversion_source
    direction = action.building_conversion_direction
    amount = action.building_conversion_amount
    assert building_id is not None
    assert source_label is not None
    assert direction is not None
    assert amount is not None

    building_name: str
    valid_directions: tuple[str, ...]
    if building_id == _BUILDING_GRAIN_STORE:
        building_name = "Grain Store"
        valid_directions = (_GRAIN_STORE_BUY_WHEAT, _GRAIN_STORE_SELL_WHEAT)
    elif building_id == _BUILDING_INDULGENCES:
        building_name = "Indulgences"
        valid_directions = (_INDULGENCES_BUY_PIETY, _INDULGENCES_SELL_PIETY)
    elif building_id == _BUILDING_STONE_YARD:
        building_name = "Stone Yard"
        valid_directions = (_STONE_YARD_BUY_STONE, _STONE_YARD_SELL_STONE)
    elif building_id == _BUILDING_BREWERY:
        building_name = "Brewery"
        valid_directions = (_BREWERY_SELL_WHEAT_FOR_SILVER,)
    else:
        raise TransitionValidationError(
            "Only Grain Store, Indulgences, Stone Yard, and Brewery are supported for building_conversion fields."
        )
    if direction not in valid_directions:
        if building_id == _BUILDING_GRAIN_STORE:
            raise TransitionValidationError(
                "Grain Store conversion direction must be buy_wheat or sell_wheat."
            )
        if building_id == _BUILDING_INDULGENCES:
            raise TransitionValidationError(
                "Indulgences conversion direction must be buy_piety or sell_piety."
            )
        if building_id == _BUILDING_BREWERY:
            raise TransitionValidationError(
                "Brewery conversion direction must be sell_wheat_for_silver."
            )
        raise TransitionValidationError(
            "Stone Yard conversion direction must be buy_stone or sell_stone."
        )
    if building_id == _BUILDING_BREWERY and amount != 1:
        raise TransitionValidationError("Brewery conversion amount must be exactly 1.")
    if amount <= 0:
        if building_id == _BUILDING_GRAIN_STORE:
            raise TransitionValidationError(
                "Grain Store conversion amount must be at least 1."
            )
        if building_id == _BUILDING_INDULGENCES:
            raise TransitionValidationError(
                "Indulgences conversion amount must be at least 1."
            )
        if building_id == _BUILDING_BREWERY:
            raise TransitionValidationError("Brewery conversion amount must be exactly 1.")
        raise TransitionValidationError(
            "Stone Yard conversion amount must be at least 1."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=building_id,
    )
    if source.source_type == "own_active" and source.usable:
        if source_label != "own_active":
            raise TransitionValidationError(
                f"Own-active {building_name} conversion must set source=own_active."
            )
    elif _is_hired_source(source) and source.usable:
        expected_source_label = _hired_building_source_label(source)
        if source_label != expected_source_label:
            raise TransitionValidationError(
                f"{building_name} conversion source does not match resolved source: "
                f"expected {expected_source_label}."
            )
    else:
        raise TransitionValidationError(f"{building_name} is unavailable in current state.")

    return _ResolvedGrainStoreConversion(
        building_id=building_id,
        source=source,
        direction=direction,
        amount=amount,
    )


def _resolved_cloisters_route_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> _ResolvedCloistersRoute | None:
    has_cloisters_building = _action_has_route_building(action, _ROUTE_BUILDING_CLOISTERS)
    has_omitted_location = action.sow_route_omitted_location is not None
    if not has_cloisters_building:
        if has_omitted_location:
            raise TransitionValidationError(
                "sow_route_omitted_location requires a Cloisters sow-route modifier."
            )
        return None

    source_label = _action_route_building_source_label(
        action,
        building_id=_ROUTE_BUILDING_CLOISTERS,
    )
    if source_label is None:
        raise TransitionValidationError(
            "Cloisters actions must set sow_route_building_source."
        )
    omitted_location = action.sow_route_omitted_location
    if omitted_location is None:
        raise TransitionValidationError(
            "Cloisters actions must set sow_route_omitted_location."
        )

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key=_ROUTE_BUILDING_CLOISTERS,
    )
    if not source.usable or (
        source.source_type != "own_active" and not _is_hired_source(source)
    ):
        raise TransitionValidationError("Cloisters is unavailable in current state.")

    expected_source_label = (
        "own_active"
        if source.source_type == "own_active"
        else _hired_building_source_label(source)
    )
    if source_label != expected_source_label:
        raise TransitionValidationError(
            "sow_route_building_source does not match resolved Cloisters source: "
            f"expected {expected_source_label}."
        )

    action_uses_kogge = _action_has_route_building(action, _ROUTE_BUILDING_KOGGE)
    if omitted_location == action.origin and not action_uses_kogge:
        raise TransitionValidationError("Cloisters omitted placement cannot be the sow origin.")
    if action_uses_kogge:
        if not _is_legal_route_with_kogge_and_cloisters_skip(
            origin=action.origin,
            route=action.route,
            board=config.board,
            omitted_location=omitted_location,
        ):
            raise TransitionValidationError(
                "Cloisters action route/skip fields do not form a legal Kogge candidate route."
            )
    elif not _is_legal_route_with_cloisters_skip(
        origin=action.origin,
        route=action.route,
        board=config.board,
        omitted_location=omitted_location,
    ):
        raise TransitionValidationError(
            "Cloisters action route/skip fields do not form a legal candidate route."
        )

    return _ResolvedCloistersRoute(
        source=source,
        omitted_location=omitted_location,
    )


def _resolved_kogge_source_for_action(
    *,
    state: GameState,
    config: GameConfig,
    player: PlayerId,
    action: FullTurnAction,
) -> BuildingAbilitySource | None:
    action_has_kogge_fields = _action_has_route_building(action, _ROUTE_BUILDING_KOGGE)
    route_uses_kogge = _route_requires_kogge(action, config)
    if (
        not route_uses_kogge
        and action_has_kogge_fields
        and _action_has_route_building(action, _ROUTE_BUILDING_CLOISTERS)
        and action.sow_route_omitted_location is not None
    ):
        route_uses_kogge = _is_legal_route_with_kogge_and_cloisters_skip(
            origin=action.origin,
            route=action.route,
            board=config.board,
            omitted_location=action.sow_route_omitted_location,
        )
    if not route_uses_kogge:
        if action_has_kogge_fields:
            raise TransitionValidationError(
                "Kogge sow-route fields are only legal when route uses city -> east/west."
            )
        return None

    source = building_ability_source(
        state,
        config,
        acting_player=player,
        building_key="kogge",
    )
    expected_source_label = (
        "own_active"
        if source.source_type == "own_active"
        else _hired_building_source_label(source)
    )
    if source.source_type == "own_active" and source.usable:
        if action_has_kogge_fields:
            source_label = _action_route_building_source_label(
                action,
                building_id=_ROUTE_BUILDING_KOGGE,
            )
            if source_label != "own_active":
                raise TransitionValidationError(
                    "Own-active Kogge route must set sow_route_building_source=own_active."
                )
        return source

    if _is_hired_source(source) and source.usable:
        if not action_has_kogge_fields:
            raise TransitionValidationError(
                "Hired Kogge route must include sow-route building fields."
            )
        source_label = _action_route_building_source_label(
            action,
            building_id=_ROUTE_BUILDING_KOGGE,
        )
        if source_label != expected_source_label:
            raise TransitionValidationError(
                "sow_route_building_source does not match resolved Kogge source: "
                f"expected {expected_source_label}."
            )
        return source

    raise TransitionValidationError(
        "Route requires Kogge (city -> east/west), but Kogge is unavailable."
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
    required_piety: int = 0,
    hired_source: BuildingAbilitySource | None = None,
) -> bool:
    """Return True when total resolution costs are jointly affordable."""
    required_stone = max(0, required_stone)
    required_silver = max(0, required_silver)
    required_wheat = max(0, required_wheat)
    required_piety = max(0, required_piety)

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
        elif hired_source.hire_resource == "piety":
            required_piety += hired_source.hire_cost
        else:
            return False

    resources = player_state.resources
    return (
        resources.stone >= required_stone
        and resources.silver >= required_silver
        and resources.wheat >= required_wheat
        and player_state.piety >= required_piety
    )


def _merchant_advance_event(
    *,
    actor: PlayerId,
    action_id: str,
    from_duty: str,
    to_duty: str,
    to_position: str,
    current_resource: str | None,
    cause: str | None = None,
) -> GameEvent:
    # The duty names alone do not tell a player where to look or what a hire will now cost, so
    # the tile it moved to and the counter standing on it travel with the event.
    details: dict[str, str] = {
        "from_duty": from_duty,
        "to_duty": to_duty,
        "to_position": to_position,
        "current_resource": current_resource if current_resource is not None else "none",
    }
    if cause is not None:
        details["cause"] = cause
    return GameEvent(
        event_type=EventType.MERCHANT_ADVANCE,
        actor=actor,
        action_id=action_id,
        details=make_event_details(**details),
    )


def _apply_guild_merchant_advance_to_state(
    state: GameState,
    *,
    actor: PlayerId,
    action_id: str,
    config: GameConfig,
) -> tuple[GameState, GameEvent]:
    from_duty = current_merchant_duty(state, config)
    next_merchant_position = advance_merchant_position(
        state.merchant_board_position,
        config,
    )
    next_state = state.with_merchant_board_position(next_merchant_position)
    to_duty = current_merchant_duty(next_state, config)
    current_resource = current_merchant_resource(next_state, config)
    event = _merchant_advance_event(
        actor=actor,
        action_id=action_id,
        from_duty=from_duty,
        to_duty=to_duty,
        to_position=merchant_position_name(next_merchant_position, config),
        current_resource=current_resource,
        cause="guild",
    )
    return next_state, event


def _apply_pulpit_workforce_move_to_state(
    state: GameState,
    *,
    actor: PlayerId,
    action_id: str,
) -> tuple[GameState, GameEvent]:
    player_state = state.player_state(actor)
    workforce = player_state.workforce
    if workforce.village < 1:
        raise ValueError(
            "Pulpit free move requires at least 1 serf in Village after hire payment."
        )
    moved_workforce = replace(
        workforce,
        village=workforce.village - 1,
        abbey=workforce.abbey + 1,
    )
    next_state = state.with_player_state(
        actor,
        replace(player_state, workforce=moved_workforce),
    )
    workforce_event = GameEvent(
        event_type=EventType.WORKFORCE_MOVE,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            amount=1,
            unit="serf",
            from_pool="village",
            to_pool="abbey",
            wheat_paid=0,
            building=_BUILDING_PULPIT,
        ),
    )
    return next_state, workforce_event


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


def _wagon_yard_free_hire_event(
    *,
    actor: PlayerId,
    action_id: str,
    target_building_id: str,
    target_source: str,
    config: GameConfig,
) -> GameEvent:
    building_name = config.buildings.name_for_id(target_building_id)
    return GameEvent(
        event_type=EventType.BUILDING_HIRED,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building_id=target_building_id,
            building_name=building_name,
            source=target_source,
            payee="none",
            resource="none",
            amount=0,
            free_with_wagon_yard=True,
            enabler_building=_BUILDING_WAGON_YARD,
        ),
    )


def _kogge_route_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
    route: tuple[int, ...],
    config: GameConfig,
) -> GameEvent:
    city_position = config.board.index_for_name("city")
    if not route:
        raise ValueError("Kogge route bonus event requires a non-empty route.")
    route_label = readable_route(city_position, (route[0],), positions=config.board.positions)
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building="kogge",
            action="sowing",
            enabled_route=route_label,
        ),
    )


def _cloisters_route_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
    omitted_location: int,
    config: GameConfig,
) -> GameEvent:
    omitted_name = config.board.positions[omitted_location]
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=_ROUTE_BUILDING_CLOISTERS,
            action="sowing",
            skipped_location=omitted_name,
        ),
    )


def _apply_grain_store_conversion_to_state(
    state: GameState,
    *,
    player: PlayerId,
    config: GameConfig,
    conversion: _ResolvedGrainStoreConversion,
) -> tuple[GameState, tuple[int, int, int, int]]:
    player_state = state.player_state(player)
    resources = player_state.resources
    piety_position = player_state.piety
    amount = conversion.amount
    if conversion.building_id == _BUILDING_BREWERY and amount != 1:
        raise ValueError("Brewery conversion amount must be exactly 1.")
    if amount <= 0:
        if conversion.building_id == _BUILDING_GRAIN_STORE:
            raise ValueError("Grain Store conversion amount must be at least 1.")
        if conversion.building_id == _BUILDING_INDULGENCES:
            raise ValueError("Indulgences conversion amount must be at least 1.")
        if conversion.building_id == _BUILDING_BREWERY:
            raise ValueError("Brewery conversion amount must be exactly 1.")
        raise ValueError("Stone Yard conversion amount must be at least 1.")

    if conversion.building_id == _BUILDING_GRAIN_STORE:
        if conversion.direction == _GRAIN_STORE_SELL_WHEAT:
            if resources.wheat < amount:
                raise ValueError(
                    "Grain Store sell conversion requires enough wheat after hire payment."
                )
            next_player_state = replace(
                player_state,
                resources=resources.add(wheat=-amount, silver=amount),
            )
            delta = (0, amount, -amount, 0)
        elif conversion.direction == _GRAIN_STORE_BUY_WHEAT:
            if resources.silver < amount:
                raise ValueError(
                    "Grain Store buy conversion requires enough silver after hire payment."
                )
            next_player_state = replace(
                player_state,
                resources=resources.add(silver=-amount, wheat=amount),
            )
            delta = (0, -amount, amount, 0)
        else:
            raise ValueError("Grain Store conversion direction must be buy_wheat or sell_wheat.")
    elif conversion.building_id == _BUILDING_INDULGENCES:
        if conversion.direction == _INDULGENCES_SELL_PIETY:
            if piety_position < amount:
                raise ValueError(
                    "Indulgences sell conversion requires enough piety after hire payment."
                )
            next_player_state = replace(
                player_state,
                piety=piety_position - amount,
                resources=resources.add(silver=amount),
            )
            delta = (0, amount, 0, -amount)
        elif conversion.direction == _INDULGENCES_BUY_PIETY:
            if resources.silver < amount:
                raise ValueError(
                    "Indulgences buy conversion requires enough silver after hire payment."
                )
            if piety_position + amount > config.piety.max_position:
                raise ValueError("Indulgences buy conversion exceeds piety track maximum.")
            next_player_state = replace(
                player_state,
                piety=piety_position + amount,
                resources=resources.add(silver=-amount),
            )
            delta = (0, -amount, 0, amount)
        else:
            raise ValueError("Indulgences conversion direction must be buy_piety or sell_piety.")
    elif conversion.building_id == _BUILDING_STONE_YARD:
        if conversion.direction == _STONE_YARD_SELL_STONE:
            if resources.stone < amount:
                raise ValueError(
                    "Stone Yard sell conversion requires enough stone after hire payment."
                )
            next_player_state = replace(
                player_state,
                resources=resources.add(stone=-amount, silver=amount),
            )
            delta = (-amount, amount, 0, 0)
        elif conversion.direction == _STONE_YARD_BUY_STONE:
            if resources.silver < amount:
                raise ValueError(
                    "Stone Yard buy conversion requires enough silver after hire payment."
                )
            next_player_state = replace(
                player_state,
                resources=resources.add(silver=-amount, stone=amount),
            )
            delta = (amount, -amount, 0, 0)
        else:
            raise ValueError("Stone Yard conversion direction must be buy_stone or sell_stone.")
    elif conversion.building_id == _BUILDING_BREWERY:
        if conversion.direction != _BREWERY_SELL_WHEAT_FOR_SILVER:
            raise ValueError("Brewery conversion direction must be sell_wheat_for_silver.")
        if resources.wheat < 1:
            raise ValueError(
                "Brewery conversion requires at least 1 wheat after hire payment."
            )
        next_player_state = replace(
            player_state,
            resources=resources.add(wheat=-1, silver=2),
        )
        delta = (0, 2, -1, 0)
    else:
        raise ValueError(
            "Only Grain Store, Indulgences, Stone Yard, and Brewery are supported for building conversions."
        )

    next_state = state.with_player_state(
        player,
        next_player_state,
    )
    return next_state, delta


def _grain_store_conversion_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
    conversion: _ResolvedGrainStoreConversion,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=conversion.building_id,
            action="conversion",
            conversion_direction=conversion.direction,
            amount=conversion.amount,
        ),
    )


def _bank_payment_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
    replaced_resource: str,
    silver_amount: int,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=_BUILDING_BANK,
            action="payment_substitution",
            replaced_resource=replaced_resource,
            silver_amount=silver_amount,
        ),
    )


def _guild_merchant_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=_BUILDING_GUILD,
            action="merchant_advance",
            steps=1,
            direction="clockwise",
        ),
    )


def _scriptorium_effective_acolyte_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=_BUILDING_SCRIPTORIUM,
            action="effective_acolyte_bonus",
            duty_relation_bonus=1,
            virtual_only=True,
        ),
    )


def _customs_house_taxation_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=_BUILDING_CUSTOMS_HOUSE,
            action="taxation_majority_override",
            duty_scope="occupied_duty_tiles",
            virtual_only=True,
        ),
    )


def _pulpit_workforce_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=_BUILDING_PULPIT,
            action="workforce_move",
            amount=1,
            from_pool="village",
            to_pool="abbey",
            wheat_paid=0,
        ),
    )


def _start_turn_building_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
    relocation: _ResolvedStartTurnRelocation,
    config: GameConfig,
) -> GameEvent:
    from_name = config.board.positions[relocation.from_position]
    to_name = config.board.positions[relocation.to_position]
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=relocation.building_id,
            action="start_turn_relocation",
            start_turn_from=from_name,
            start_turn_to=to_name,
        ),
    )


def _start_turn_relocation_event(
    *,
    actor: PlayerId,
    action_id: str,
    relocation: _ResolvedStartTurnRelocation,
    config: GameConfig,
) -> GameEvent:
    building_name = config.buildings.name_for_id(relocation.building_id)
    return GameEvent(
        event_type=EventType.START_TURN_RELOCATION,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=relocation.building_id,
            building_name=building_name,
            from_position=relocation.from_position,
            to_position=relocation.to_position,
            amount=1,
        ),
    )


def _end_turn_building_bonus_event(
    *,
    actor: PlayerId,
    action_id: str,
    relocation: _ResolvedEndTurnRelocation,
) -> GameEvent:
    return GameEvent(
        event_type=EventType.BUILDING_BONUS,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=relocation.building_id,
            action="end_turn_relocation",
            end_turn_from="city",
            end_turn_to=relocation.to_pool,
        ),
    )


def _end_turn_relocation_event(
    *,
    actor: PlayerId,
    action_id: str,
    relocation: _ResolvedEndTurnRelocation,
    config: GameConfig,
) -> GameEvent:
    building_name = config.buildings.name_for_id(relocation.building_id)
    return GameEvent(
        event_type=EventType.END_TURN_RELOCATION,
        actor=actor,
        action_id=action_id,
        details=make_event_details(
            building=relocation.building_id,
            building_name=building_name,
            from_pool="city",
            to_pool=relocation.to_pool,
            amount=1,
        ),
    )


def _refresh_resource_delta_event(
    events: list[GameEvent],
    *,
    actor: PlayerId,
    action_id: str,
    before_resources,
    after_resources,
) -> None:
    for index in range(len(events) - 1, -1, -1):
        event = events[index]
        if (
            event.event_type is EventType.RESOURCE_DELTA
            and event.actor is actor
            and event.action_id == action_id
        ):
            delta = _resource_delta_between(before_resources, after_resources)
            events[index] = GameEvent(
                event_type=EventType.RESOURCE_DELTA,
                actor=actor,
                action_id=action_id,
                details=make_event_details(
                    stone=delta[0],
                    silver=delta[1],
                    wheat=delta[2],
                ),
            )
            return


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


def _construct_market_candidate_building_ids(
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
    candidate_buildings: list[str] = []
    for building_id in building_market:
        if building_id in owned_buildings:
            continue
        try:
            _definition = config.buildings.definition_by_id(building_id)
        except ValueError:
            continue
        if not is_building_live(state, building_id):
            continue
        candidate_buildings.append(building_id)
    return tuple(candidate_buildings)


def _opponents(state: GameState, player: PlayerId) -> tuple[PlayerId, ...]:
    return tuple(
        candidate
        for candidate in (PlayerId(index) for index in range(state.player_count))
        if candidate != player
    )


def _competing_counts(
    state: GameState,
    *,
    player: PlayerId,
    duty_position: int,
) -> tuple[int, ...]:
    opponent_counts = [
        state.player_vector(opponent_id)[duty_position]
        for opponent_id in _opponents(state, player)
    ]
    opponent_counts.append(state.dummy_at_position(duty_position))
    return tuple(opponent_counts)


def _effective_player_acolytes_for_duty_position(
    *,
    base_count: int,
    duty_position: int,
    relation_context: _DutyRelationModifierContext,
    config: GameConfig,
) -> int:
    if not relation_context.uses_scriptorium:
        return base_count
    if base_count <= 0:
        return base_count
    if duty_position not in config.duty_positions():
        return base_count
    return base_count + 1


def _duty_strength_for_position(
    state: GameState,
    config: GameConfig,
    *,
    player: PlayerId,
    duty_position: int,
    sowed_vector: tuple[int, ...],
    relation_context: _DutyRelationModifierContext,
) -> DutyStrength:
    player_count = _effective_player_acolytes_for_duty_position(
        base_count=sowed_vector[duty_position],
        duty_position=duty_position,
        relation_context=relation_context,
        config=config,
    )
    opponent_counts = _competing_counts(
        state,
        player=player,
        duty_position=duty_position,
    )
    return duty_strength(player_count, opponent_counts)


def _has_customs_house_taxation_majority(
    *,
    player: PlayerId,
    duty_position: int,
    sowed_vector: tuple[int, ...],
    relation_context: _DutyRelationModifierContext,
    config: GameConfig,
) -> bool:
    if not relation_context.uses_customs_house:
        return False
    if player != relation_context.acting_player:
        return False
    if duty_position not in config.duty_positions():
        return False
    return sowed_vector[duty_position] > 0


def _taxation_duty_strength_for_position(
    state: GameState,
    config: GameConfig,
    *,
    player: PlayerId,
    duty_position: int,
    sowed_vector: tuple[int, ...],
    relation_context: _DutyRelationModifierContext,
) -> DutyStrength:
    if _has_customs_house_taxation_majority(
        player=player,
        duty_position=duty_position,
        sowed_vector=sowed_vector,
        relation_context=relation_context,
        config=config,
    ):
        return DutyStrength.MAJORITY
    return _duty_strength_for_position(
        state,
        config,
        player=player,
        duty_position=duty_position,
        sowed_vector=sowed_vector,
        relation_context=relation_context,
    )


def _invariant_workforce_details(state: GameState) -> dict[str, int]:
    details: dict[str, int] = {}
    total = 0
    for player_id in (PlayerId(index) for index in range(state.player_count)):
        workforce_total = state.total_acolytes(player_id)
        details[f"total_workforce_{_player_label(player_id)}"] = workforce_total
        total += workforce_total
    details["total_workforce_all_players"] = total
    return details


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
    relation_context: _DutyRelationModifierContext,
) -> tuple[str, ...]:
    unlocked_resources: set[str] = set()
    for duty_position in config.duty_positions():
        if duty_position == selected_duty:
            continue
        if config.duty_category_for_position(duty_position) == "taxation":
            continue
        strength = _taxation_duty_strength_for_position(
            state,
            config,
            player=player,
            duty_position=duty_position,
            sowed_vector=sowed_vector,
            relation_context=relation_context,
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
