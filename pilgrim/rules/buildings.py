"""Building catalogue, market, and player-board slot helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
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
from pilgrim.model.state import GameState, PlayerState
from pilgrim.rules.validation import TransitionValidationError

_EXPECTED_DONATION_VP_BY_LEVEL: dict[int, int] = {
    1: 2,
    2: 4,
    3: 6,
}


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
    """Validate scenario building market composition."""
    if len(market) != config.setup.buildings_per_game:
        raise TransitionValidationError(
            f"Building market must contain exactly {config.setup.buildings_per_game} buildings."
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
        if actual != expected:
            raise TransitionValidationError(
                f"Building market must contain exactly {expected} level-{level} buildings."
            )


def building_stone_cost(building: BuildingDefinition) -> int:
    """Return stone cost for one building definition."""
    return building.stone_cost


def building_donation_vp(building: BuildingDefinition) -> int:
    """Return donation VP for one building definition."""
    return building.donation_vp


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
    market = (
        state.building_market
        if state.building_market
        else default_building_market(config.buildings)
    )
    validate_building_market(market, config.buildings)
    for player_id in (PlayerId.PLAYER_ONE, PlayerId.PLAYER_TWO):
        validate_player_board_slots(
            state.player_state(player_id).player_board_slots,
            config.buildings,
        )


def building_names_for_ids(
    building_ids: Sequence[str],
    config: BuildingsConfig,
) -> tuple[str, ...]:
    """Map stable building ids to display names."""
    return tuple(building_by_id(config, building_id).name for building_id in building_ids)


def _ensure_unique_ids(values: tuple[str, ...], *, label: str) -> None:
    if len(set(values)) != len(values):
        raise TransitionValidationError(f"{label} cannot contain duplicate building ids.")
