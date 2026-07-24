"""Building catalogue, market, and player-board slot helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from pilgrim.model.buildings import (
    BUILDING_LEVELS,
    BuildingDefinition,
    BuildingsConfig,
    PlayerBoardSlots,
    buildings_config_from_dict,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.resources import Resources
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.merchant import current_merchant_resource
from pilgrim.rules.validation import TransitionValidationError

_EXPECTED_DONATION_VP_BY_LEVEL: dict[int, int] = {
    1: 2,
    2: 4,
    3: 6,
}
MIN_BUILDING_LIVE_ROUND = 2
MAX_BUILDING_LIVE_ROUND = 26
DEFAULT_BUILDING_LIVE_ROUND = MIN_BUILDING_LIVE_ROUND
_HIRE_COST = 1


@dataclass(frozen=True, slots=True)
class BuildingAbilitySource:
    """Resolved source for one building ability lookup."""

    building_key: str
    source_type: str
    owner: str | None = None
    hire_resource: str | None = None
    hire_cost: int = 0
    payable_to: str | None = None
    usable: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class BuildingHirePayment:
    """Concrete payment route for one building hire source."""

    building_key: str
    payer: str
    payee: str
    resource: str | None
    amount: int


@dataclass(frozen=True, slots=True)
class BuildingHireTurnContext:
    """Per-turn hired-building tracker (same building at most once per turn)."""

    hired_buildings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(normalize_hire_building_key(key) for key in self.hired_buildings)
        if len(set(normalized)) != len(normalized):
            raise ValueError("hired_buildings cannot contain duplicates in one turn.")
        if normalized != self.hired_buildings:
            object.__setattr__(self, "hired_buildings", normalized)


def load_building_config(raw: Mapping[str, Any]) -> BuildingsConfig:
    """Parse and validate building catalogue config from raw JSON data."""
    config = buildings_config_from_dict(raw)
    validate_building_catalogue(config)
    return config


def building_by_id(config: BuildingsConfig, building_id: str) -> BuildingDefinition:
    """Return one building definition by stable id."""
    return config.definition_by_id(building_id)


def buildings_by_level(config: BuildingsConfig, level: int) -> tuple[BuildingDefinition, ...]:
    """Return all catalogue entries matching one level."""
    return config.definitions_by_level(level)


def validate_building_catalogue(config: BuildingsConfig) -> None:
    """Validate catalogue size, level distribution, costs, VP, and identifiers."""
    setup = config.setup
    catalogue = config.catalogue
    if setup.buildings_per_game != 12:
        raise TransitionValidationError("Building setup must specify buildings_per_game=12.")

    expected_draw_per_level = {1: 4, 2: 4, 3: 4}
    expected_pool_per_level = {1: 8, 2: 8, 3: 8}

    if len(catalogue) != 24:
        raise TransitionValidationError("Building catalogue must contain exactly 24 entries.")

    ids = [building.id for building in catalogue]
    names = [building.name for building in catalogue]
    if len(set(ids)) != len(ids):
        raise TransitionValidationError("Building catalogue contains duplicate ids.")
    if len(set(names)) != len(names):
        raise TransitionValidationError("Building catalogue contains duplicate names.")

    for level in BUILDING_LEVELS:
        draw_count = setup.draw_count(level)
        pool_size = setup.pool_size(level)
        if draw_count != expected_draw_per_level[level]:
            raise TransitionValidationError(
                f"Building setup draw_per_level[{level}] must be {expected_draw_per_level[level]}."
            )
        if pool_size != expected_pool_per_level[level]:
            raise TransitionValidationError(
                "Building setup pool_size_per_level["
                f"{level}] must be {expected_pool_per_level[level]}."
            )
        definitions = buildings_by_level(config, level)
        if len(definitions) != pool_size:
            raise TransitionValidationError(
                f"Building catalogue must contain exactly {pool_size} buildings at level {level}."
            )

    if config.player_board.building_and_cardinal_slot_limit != 6:
        raise TransitionValidationError(
            "Building player_board building_and_cardinal_slot_limit must be 6."
        )

    for building in catalogue:
        if building.level not in BUILDING_LEVELS:
            raise TransitionValidationError(
                f"Building {building.id} has invalid level {building.level}."
            )
        if building_stone_cost(building) != building.level:
            raise TransitionValidationError(
                f"Building {building.id} stone_cost must equal level ({building.level})."
            )
        expected_vp = _EXPECTED_DONATION_VP_BY_LEVEL[building.level]
        if building_donation_vp(building) != expected_vp:
            raise TransitionValidationError(
                f"Building {building.id} donation_vp must be {expected_vp}."
            )
        if building.effect_status != "deferred":
            raise TransitionValidationError(
                f"Building {building.id} effect_status must be 'deferred'."
            )


def default_building_market(config: BuildingsConfig) -> tuple[str, ...]:
    """Return deterministic fallback market: first draw_count ids per level."""
    market: list[str] = []
    for level in BUILDING_LEVELS:
        level_buildings = buildings_by_level(config, level)
        market.extend(
            building.id
            for building in level_buildings[: config.setup.draw_count(level)]
        )
    validate_building_market(tuple(market), config)
    return tuple(market)


def validate_building_market(market: tuple[str, ...], config: BuildingsConfig) -> None:
    """Validate runtime building market composition."""
    if len(market) > config.setup.buildings_per_game:
        raise TransitionValidationError(
            f"Building market cannot exceed {config.setup.buildings_per_game} buildings."
        )
    if len(set(market)) != len(market):
        raise TransitionValidationError("Building market cannot contain duplicate building ids.")

    level_counts: Counter[int] = Counter()
    for building_id in market:
        definition = building_by_id(config, building_id)
        level_counts[definition.level] += 1

    for level in BUILDING_LEVELS:
        expected = config.setup.draw_count(level)
        actual = level_counts[level]
        if actual > expected:
            raise TransitionValidationError(
                f"Building market may contain at most {expected} level-{level} buildings."
            )


def building_stone_cost(building: BuildingDefinition) -> int:
    """Return stone cost for one building definition."""
    return building.stone_cost


def building_donation_vp(building: BuildingDefinition) -> int:
    """Return donation VP for one building definition."""
    return building.donation_vp


def donate_active_building(
    player_state: PlayerState,
    *,
    building_id: str,
    config: GameConfig,
) -> tuple[PlayerState, BuildingDefinition]:
    """Move one active building to donated and add its donation VP."""
    slots = player_state.player_board_slots
    if building_id in slots.donated_buildings:
        raise ValueError(f"Building '{building_id}' is already donated.")
    if building_id not in slots.active_buildings:
        raise ValueError(f"Building '{building_id}' is not in active_buildings.")

    definition = building_by_id(config.buildings, building_id)
    remaining_active = tuple(
        current_building_id
        for current_building_id in slots.active_buildings
        if current_building_id != building_id
    )
    if len(remaining_active) != len(slots.active_buildings) - 1:
        raise ValueError(f"Building '{building_id}' must appear exactly once in active_buildings.")

    updated_slots = PlayerBoardSlots(
        active_buildings=remaining_active,
        donated_buildings=(*slots.donated_buildings, building_id),
        cardinal_favor_tiles=slots.cardinal_favor_tiles,
    )
    updated_player_state = replace(
        player_state,
        victory_points=player_state.victory_points + definition.donation_vp,
        player_board_slots=updated_slots,
    )
    return updated_player_state, definition


def construct_building_from_market(
    player_state: PlayerState,
    *,
    building_id: str,
    building_market: tuple[str, ...],
    config: GameConfig,
) -> tuple[PlayerState, tuple[str, ...], BuildingDefinition]:
    """Construct one market building and move it to active_buildings."""
    if building_id not in building_market:
        raise ValueError(f"Building '{building_id}' is not available in building_market.")
    if building_id in player_state.player_board_slots.active_buildings:
        raise ValueError(f"Building '{building_id}' is already active on this player board.")
    if building_id in player_state.player_board_slots.donated_buildings:
        raise ValueError(f"Building '{building_id}' is already donated on this player board.")
    if not has_available_player_board_slot(player_state, config):
        raise ValueError("No available player-board slot for constructing a building.")

    definition = building_by_id(config.buildings, building_id)
    stone_cost = building_stone_cost(definition)
    resources_after_cost = player_state.resources.add(stone=-stone_cost)
    if resources_after_cost.stone < 0:
        raise ValueError(
            f"Insufficient stone to construct '{building_id}': need {stone_cost}."
        )

    updated_slots = PlayerBoardSlots(
        active_buildings=(*player_state.player_board_slots.active_buildings, building_id),
        donated_buildings=player_state.player_board_slots.donated_buildings,
        cardinal_favor_tiles=player_state.player_board_slots.cardinal_favor_tiles,
    )
    updated_player_state = replace(
        player_state,
        resources=resources_after_cost,
        player_board_slots=updated_slots,
    )
    updated_market = _remove_first_occurrence(building_market, building_id)
    return updated_player_state, updated_market, definition


def player_has_active_building(player_state: PlayerState, building_id: str) -> bool:
    """Return True when one building is currently active on the player board."""
    return building_id in player_state.player_board_slots.active_buildings


def produce_wheat_well_bonus(player_state: PlayerState) -> int:
    """Well adds +1 wheat to produce_wheat when active."""
    return 1 if player_has_active_building(player_state, "well") else 0


def produce_stone_quarry_bonus(player_state: PlayerState) -> int:
    """Quarry adds +1 stone to produce_stone when active."""
    return 1 if player_has_active_building(player_state, "quarry") else 0


def clerical_silversmith_mint_bonus(player_state: PlayerState) -> int:
    """Mint adds +1 silver to clerical_silversmith when active."""
    return 1 if player_has_active_building(player_state, "mint") else 0


def clerical_devotion_chapel_bonus(player_state: PlayerState) -> int:
    """Chapel adds +1 piety to clerical_devotion when active."""
    return 1 if player_has_active_building(player_state, "chapel") else 0


def allocation_infirmary_duty_value_bonus(player_state: PlayerState) -> int:
    """Infirmary adds +1 effective duty value to allocation when active."""
    return 1 if player_has_active_building(player_state, "infirmary") else 0


def player_has_active_chapter_house(player_state: PlayerState) -> bool:
    """Return True when Chapter House is currently active on this player board."""
    return player_has_active_building(player_state, "chapter_house")


def ordination_infirmary_duty_value_bonus(
    player_state: PlayerState,
    *,
    extra_step_wheat_paid: bool,
) -> int:
    """Infirmary adds +1 effective duty value to ordination when an extra paid step is used."""
    if not extra_step_wheat_paid:
        return 0
    return 1 if player_has_active_building(player_state, "infirmary") else 0


def mill_wheat_waiver(required_wheat: int) -> int:
    """Return Mill wheat waiver amount for one action wheat requirement."""
    if required_wheat < 0:
        raise ValueError("required_wheat cannot be negative.")
    return min(2, required_wheat)


def mill_actual_wheat_cost(required_wheat: int) -> int:
    """Return wheat actually spent after applying Mill waiver."""
    if required_wheat < 0:
        raise ValueError("required_wheat cannot be negative.")
    return max(0, required_wheat - 2)


def used_player_board_slots(player_state: PlayerState) -> int:
    """Return number of occupied shared board slots."""
    slots = player_state.player_board_slots
    return (
        len(slots.active_buildings)
        + len(slots.donated_buildings)
        + slots.cardinal_favor_tiles
    )


def available_player_board_slots(player_state: PlayerState, config: GameConfig) -> int:
    """Return remaining shared board slots."""
    limit = config.buildings.player_board.building_and_cardinal_slot_limit
    return limit - used_player_board_slots(player_state)


def has_available_player_board_slot(player_state: PlayerState, config: GameConfig) -> bool:
    """Return True when one or more board slots remain."""
    return available_player_board_slots(player_state, config) > 0


def validate_player_board_slots(
    slots: PlayerBoardSlots,
    config: BuildingsConfig,
) -> None:
    """Validate one player's board slot occupancy against catalogue and capacity."""
    if slots.cardinal_favor_tiles < 0:
        raise TransitionValidationError("cardinal_favor_tiles cannot be negative.")

    _ensure_unique_ids(slots.active_buildings, label="active_buildings")
    _ensure_unique_ids(slots.donated_buildings, label="donated_buildings")

    overlap = set(slots.active_buildings).intersection(slots.donated_buildings)
    if overlap:
        raise TransitionValidationError(
            "Building id cannot be both active and donated on same player board: "
            f"{sorted(overlap)}."
        )

    for building_id in (*slots.active_buildings, *slots.donated_buildings):
        building_by_id(config, building_id)

    used_slots = (
        len(slots.active_buildings)
        + len(slots.donated_buildings)
        + slots.cardinal_favor_tiles
    )
    limit = config.player_board.building_and_cardinal_slot_limit
    if used_slots > limit:
        raise TransitionValidationError(
            f"Player board slots exceed limit {limit}: used {used_slots}."
        )


def validate_building_state(state: GameState, config: GameConfig) -> None:
    """Validate market + per-player slot occupancy against building config."""
    validate_building_catalogue(config.buildings)
    validate_building_market(state.building_market, config.buildings)
    validate_building_availability(state, config)
    for player_id in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        validate_player_board_slots(
            state.player_state(player_id).player_board_slots,
            config.buildings,
        )


def validate_building_availability(state: GameState, config: GameConfig) -> None:
    """Validate live-round timeline metadata for selected buildings."""
    availability_keys = [building_id for building_id, _round_number in state.building_availability]
    if len(set(availability_keys)) != len(availability_keys):
        raise TransitionValidationError(
            "building_availability cannot contain duplicate building ids."
        )

    selected_building_ids = set(state.building_market)
    for player_id in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        slots = state.player_state(player_id).player_board_slots
        selected_building_ids.update(slots.active_buildings)
        selected_building_ids.update(slots.donated_buildings)

    availability_map = _building_availability_map(state)
    for building_id, live_round in state.building_availability:
        try:
            building_by_id(config.buildings, building_id)
        except ValueError as exc:
            raise TransitionValidationError(str(exc)) from exc
        if not isinstance(live_round, int) or isinstance(live_round, bool):
            raise TransitionValidationError(
                "building_availability live rounds must be integer values."
            )
        if live_round < MIN_BUILDING_LIVE_ROUND or live_round > MAX_BUILDING_LIVE_ROUND:
            raise TransitionValidationError(
                "building_availability live rounds must be between "
                f"{MIN_BUILDING_LIVE_ROUND} and {MAX_BUILDING_LIVE_ROUND}."
            )
        if building_id not in selected_building_ids:
            raise TransitionValidationError(
                "building_availability key must reference a selected building in game state: "
                f"{building_id}."
            )

    for building_id in state.building_market:
        if building_id not in availability_map:
            raise TransitionValidationError(
                "building_market entry missing building_availability round: "
                f"{building_id}."
            )


def building_ability_source(
    state: GameState,
    config: GameConfig,
    *,
    acting_player: PlayerId,
    building_key: str,
) -> BuildingAbilitySource:
    """Resolve how one player may access one building ability right now."""
    donated_owner = _donated_owner(state, building_key)
    if donated_owner is not None:
        return BuildingAbilitySource(
            building_key=building_key,
            source_type="unavailable",
            owner=donated_owner,
            usable=False,
            reason="donated",
        )

    player_state = state.player_state(acting_player)
    if building_key in player_state.player_board_slots.active_buildings:
        return BuildingAbilitySource(
            building_key=building_key,
            source_type="own_active",
            owner=_player_label(acting_player),
            hire_resource=None,
            hire_cost=0,
            payable_to=None,
            usable=True,
        )

    opponent_owner = _opponent_active_owner(
        state,
        acting_player=acting_player,
        building_key=building_key,
    )
    if opponent_owner is not None:
        return _hired_source(
            state,
            config,
            acting_player=acting_player,
            building_key=building_key,
            source_type="opponent_active_hire",
            owner=opponent_owner,
            payable_to=opponent_owner,
        )

    if building_key in state.building_market:
        if not is_building_live(state, building_key):
            return BuildingAbilitySource(
                building_key=building_key,
                source_type="unavailable",
                hire_cost=_HIRE_COST,
                payable_to="bank",
                usable=False,
                reason="not_live",
            )
        return _hired_source(
            state,
            config,
            acting_player=acting_player,
            building_key=building_key,
            source_type="live_market_hire",
            owner=None,
            payable_to="bank",
        )

    return BuildingAbilitySource(
        building_key=building_key,
        source_type="unavailable",
        usable=False,
        reason="not_selected",
    )


def available_building_ability_sources(
    state: GameState,
    config: GameConfig,
    *,
    acting_player: PlayerId,
    building_key: str,
) -> tuple[BuildingAbilitySource, ...]:
    """Return usable ability sources only for one building lookup."""
    source = building_ability_source(
        state,
        config,
        acting_player=acting_player,
        building_key=building_key,
    )
    if source.usable:
        return (source,)
    return ()


def can_use_building_ability(
    state: GameState,
    config: GameConfig,
    *,
    acting_player: PlayerId,
    building_key: str,
) -> bool:
    """Return True when building ability is usable under current source/cost rules."""
    source = building_ability_source(
        state,
        config,
        acting_player=acting_player,
        building_key=building_key,
    )
    return source.usable


def building_hire_cost(
    state: GameState,
    config: GameConfig,
    *,
    acting_player: PlayerId,
    building_key: str,
) -> tuple[str | None, int]:
    """Return (resource, cost) for one current ability-source resolution."""
    source = building_ability_source(
        state,
        config,
        acting_player=acting_player,
        building_key=building_key,
    )
    return source.hire_resource, source.hire_cost


def normalize_hire_building_key(building_key: str) -> str:
    """Normalize building ids used by turn-hire tracking helpers."""
    normalized = "_".join(
        building_key.strip().lower().replace("-", " ").replace("_", " ").split()
    )
    if not normalized:
        raise ValueError("Building key cannot be empty for hire tracking.")
    return normalized


def can_hire_building_this_turn(
    context: BuildingHireTurnContext,
    *,
    building_key: str,
) -> bool:
    """Return True when this building has not yet been hired during the same turn."""
    normalized = normalize_hire_building_key(building_key)
    return normalized not in context.hired_buildings


def record_hired_building_this_turn(
    context: BuildingHireTurnContext,
    *,
    building_key: str,
) -> BuildingHireTurnContext:
    """Return updated immutable hire context after recording one building hire."""
    normalized = normalize_hire_building_key(building_key)
    if normalized in context.hired_buildings:
        raise ValueError(f"Building already hired this turn: {normalized}.")
    return BuildingHireTurnContext(
        hired_buildings=(*context.hired_buildings, normalized),
    )


def validate_hire_sequence_for_turn(building_keys: Sequence[str]) -> bool:
    """Return False when any normalized building appears more than once in a turn."""
    context = BuildingHireTurnContext()
    for building_key in building_keys:
        if not can_hire_building_this_turn(context, building_key=building_key):
            return False
        context = record_hired_building_this_turn(context, building_key=building_key)
    return True


def building_hire_payment(
    state: GameState,
    *,
    acting_player: PlayerId,
    source: BuildingAbilitySource,
) -> BuildingHirePayment:
    """Describe payment route for a resolved building-ability source."""
    # Validate player id against current state for deterministic callers.
    state.player_state(acting_player)
    payer = _player_label(acting_player)
    if source.source_type == "own_active":
        return BuildingHirePayment(
            building_key=source.building_key,
            payer=payer,
            payee="none",
            resource=None,
            amount=0,
        )
    if source.source_type not in ("live_market_hire", "opponent_active_hire"):
        raise ValueError("Building ability source cannot be hired.")
    if not source.usable:
        raise ValueError(
            f"Building ability source is not usable for hire payment: {source.reason or 'unavailable'}."
        )
    if source.hire_resource is None or source.hire_cost <= 0:
        raise ValueError("Building hire source is missing cost/resource details.")
    payee = source.payable_to or "bank"
    return BuildingHirePayment(
        building_key=source.building_key,
        payer=payer,
        payee=payee,
        resource=source.hire_resource,
        amount=source.hire_cost,
    )


def apply_building_hire_payment(
    state: GameState,
    *,
    acting_player: PlayerId,
    source: BuildingAbilitySource,
) -> tuple[GameState, BuildingHirePayment]:
    """Apply one hire payment transfer to state and return payment details."""
    payment = building_hire_payment(
        state,
        acting_player=acting_player,
        source=source,
    )
    if payment.amount <= 0 or payment.resource is None:
        return state, payment

    payer_state = state.player_state(acting_player)
    payer_resources = _apply_resource_delta(
        payer_state.resources,
        resource=payment.resource,
        delta=-payment.amount,
    )
    if _resource_amount(payer_resources, payment.resource) < 0:
        raise ValueError(
            f"Insufficient {payment.resource} for building hire payment by {payment.payer}."
        )
    next_state = state.with_player_state(
        acting_player,
        replace(payer_state, resources=payer_resources),
    )

    recipient_player_id = _player_id_from_label(payment.payee)
    if recipient_player_id is not None:
        recipient_state = next_state.player_state(recipient_player_id)
        recipient_resources = _apply_resource_delta(
            recipient_state.resources,
            resource=payment.resource,
            delta=payment.amount,
        )
        next_state = next_state.with_player_state(
            recipient_player_id,
            replace(recipient_state, resources=recipient_resources),
        )

    return next_state, payment


def building_live_round(state: GameState, building_key: str) -> int | None:
    """Return the configured live round for one building, if known."""
    return _building_availability_map(state).get(building_key)


def is_building_live(
    state: GameState,
    building_key: str,
    *,
    round_number: int | None = None,
) -> bool:
    """Return True when current/effective round is at or beyond building live round."""
    effective_round = state.round_number if round_number is None else round_number
    live_round = building_live_round(state, building_key)
    if live_round is None:
        return False
    return effective_round >= live_round


def live_buildings(state: GameState) -> tuple[str, ...]:
    """Return currently live building ids across the tracked availability map."""
    effective_round = state.round_number
    return tuple(
        sorted(
            building_id
            for building_id, live_round in _building_availability_map(state).items()
            if effective_round >= live_round
        )
    )


def future_buildings(state: GameState) -> tuple[tuple[str, int], ...]:
    """Return not-yet-live building ids with their configured live rounds."""
    effective_round = state.round_number
    entries = [
        (building_id, live_round)
        for building_id, live_round in _building_availability_map(state).items()
        if effective_round < live_round
    ]
    return tuple(sorted(entries, key=lambda item: (item[1], item[0])))


def building_names_for_ids(
    building_ids: Sequence[str],
    config: BuildingsConfig,
) -> tuple[str, ...]:
    """Map stable building ids to display names."""
    return tuple(building_by_id(config, building_id).name for building_id in building_ids)


def _ensure_unique_ids(values: tuple[str, ...], *, label: str) -> None:
    if len(set(values)) != len(values):
        raise TransitionValidationError(f"{label} cannot contain duplicate building ids.")


def _hired_source(
    state: GameState,
    config: GameConfig,
    *,
    acting_player: PlayerId,
    building_key: str,
    source_type: str,
    owner: str | None,
    payable_to: str,
) -> BuildingAbilitySource:
    hire_resource = current_merchant_resource(state, config.merchant)
    if hire_resource is None:
        return BuildingAbilitySource(
            building_key=building_key,
            source_type="unavailable",
            owner=owner,
            hire_resource=None,
            hire_cost=_HIRE_COST,
            payable_to=payable_to,
            usable=False,
            reason="merchant_resource_none",
        )

    acting_resources = state.player_state(acting_player).resources
    if _resource_amount(acting_resources, hire_resource) < _HIRE_COST:
        return BuildingAbilitySource(
            building_key=building_key,
            source_type="unavailable",
            owner=owner,
            hire_resource=hire_resource,
            hire_cost=_HIRE_COST,
            payable_to=payable_to,
            usable=False,
            reason="insufficient_resource",
        )

    return BuildingAbilitySource(
        building_key=building_key,
        source_type=source_type,
        owner=owner,
        hire_resource=hire_resource,
        hire_cost=_HIRE_COST,
        payable_to=payable_to,
        usable=True,
    )


def _opponent_active_owner(
    state: GameState,
    *,
    acting_player: PlayerId,
    building_key: str,
) -> str | None:
    for candidate in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        if candidate is acting_player:
            continue
        candidate_slots = state.player_state(candidate).player_board_slots
        if building_key in candidate_slots.active_buildings:
            return _player_label(candidate)
    return None


def _donated_owner(state: GameState, building_key: str) -> str | None:
    for candidate in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        candidate_slots = state.player_state(candidate).player_board_slots
        if building_key in candidate_slots.donated_buildings:
            return _player_label(candidate)
    return None


def _player_label(player_id: PlayerId) -> str:
    return player_id.name.lower()


def _player_id_from_label(label: str) -> PlayerId | None:
    if label == "player_one":
        return PlayerId.PLAYER_ONE
    if label == "player_two":
        return PlayerId.PLAYER_TWO
    return None


def _resource_amount(resources: Resources, resource: str) -> int:
    if resource == "stone":
        return resources.stone
    if resource == "silver":
        return resources.silver
    if resource == "wheat":
        return resources.wheat
    raise ValueError(f"Unknown resource type for building hire: {resource}.")


def _apply_resource_delta(resources: Resources, *, resource: str, delta: int) -> Resources:
    if resource == "stone":
        return resources.add(stone=delta)
    if resource == "silver":
        return resources.add(silver=delta)
    if resource == "wheat":
        return resources.add(wheat=delta)
    raise ValueError(f"Unknown resource type for building hire: {resource}.")


def _building_availability_map(state: GameState) -> dict[str, int]:
    return {building_id: live_round for building_id, live_round in state.building_availability}


def _remove_first_occurrence(values: tuple[str, ...], target: str) -> tuple[str, ...]:
    removed = False
    kept: list[str] = []
    for value in values:
        if value == target and not removed:
            removed = True
            continue
        kept.append(value)
    if not removed:
        raise ValueError(f"Cannot remove '{target}': value not found.")
    return tuple(kept)
