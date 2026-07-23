"""Building catalogue and player-board slot state models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

BUILDING_LEVELS: tuple[int, ...] = (1, 2, 3)


@dataclass(frozen=True, slots=True)
class BuildingDefinition:
    """One building definition from the static catalogue."""

    id: str
    name: str
    level: int
    stone_cost: int
    donation_vp: int
    effect_status: str = "deferred"

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Building id cannot be empty.")
        if not self.name:
            raise ValueError("Building name cannot be empty.")
        if self.level not in BUILDING_LEVELS:
            raise ValueError(f"Building level must be in {BUILDING_LEVELS}.")


@dataclass(frozen=True, slots=True)
class BuildingSetupConfig:
    """Per-game market setup metadata for building draws."""

    buildings_per_game: int
    draw_per_level: tuple[tuple[int, int], ...]
    pool_size_per_level: tuple[tuple[int, int], ...]

    def draw_count(self, level: int) -> int:
        return _value_for_level(self.draw_per_level, level)

    def pool_size(self, level: int) -> int:
        return _value_for_level(self.pool_size_per_level, level)


@dataclass(frozen=True, slots=True)
class PlayerBoardConfig:
    """Player-board shared slot capacity metadata."""

    building_and_cardinal_slot_limit: int


@dataclass(frozen=True, slots=True)
class BuildingsConfig:
    """Static building catalogue + setup metadata bundle."""

    setup: BuildingSetupConfig
    player_board: PlayerBoardConfig
    catalogue: tuple[BuildingDefinition, ...]

    def definition_by_id(self, building_id: str) -> BuildingDefinition:
        for building in self.catalogue:
            if building.id == building_id:
                return building
        raise ValueError(f"Unknown building id: {building_id}")

    def definitions_by_level(self, level: int) -> tuple[BuildingDefinition, ...]:
        return tuple(building for building in self.catalogue if building.level == level)

    def name_for_id(self, building_id: str) -> str:
        return self.definition_by_id(building_id).name


@dataclass(frozen=True, slots=True)
class PlayerBoardSlots:
    """State for building/cardinal slot occupancy on one player board."""

    active_buildings: tuple[str, ...] = ()
    donated_buildings: tuple[str, ...] = ()
    cardinal_favor_tiles: int = 0

    def __post_init__(self) -> None:
        if self.cardinal_favor_tiles < 0:
            raise ValueError("cardinal_favor_tiles cannot be negative.")
        if any(not building_id for building_id in self.active_buildings):
            raise ValueError("active_buildings cannot contain empty ids.")
        if any(not building_id for building_id in self.donated_buildings):
            raise ValueError("donated_buildings cannot contain empty ids.")


def buildings_config_from_dict(raw: Mapping[str, Any]) -> BuildingsConfig:
    """Parse static building catalogue config from JSON."""
    setup_raw = raw["setup"]
    if not isinstance(setup_raw, Mapping):
        raise ValueError("Building setup must be an object.")

    player_board_raw = raw["player_board"]
    if not isinstance(player_board_raw, Mapping):
        raise ValueError("Building player_board must be an object.")

    catalogue_raw = raw["catalogue"]
    if not isinstance(catalogue_raw, list):
        raise ValueError("Building catalogue must be a list.")

    setup = BuildingSetupConfig(
        buildings_per_game=int(setup_raw["buildings_per_game"]),
        draw_per_level=_parse_level_mapping(setup_raw["draw_per_level"]),
        pool_size_per_level=_parse_level_mapping(setup_raw["pool_size_per_level"]),
    )
    player_board = PlayerBoardConfig(
        building_and_cardinal_slot_limit=int(
            player_board_raw["building_and_cardinal_slot_limit"]
        )
    )
    catalogue = tuple(
        BuildingDefinition(
            id=str(entry["id"]),
            name=str(entry["name"]),
            level=int(entry["level"]),
            stone_cost=int(entry["stone_cost"]),
            donation_vp=int(entry["donation_vp"]),
            effect_status=str(entry.get("effect_status", "deferred")),
        )
        for entry in catalogue_raw
    )
    return BuildingsConfig(setup=setup, player_board=player_board, catalogue=catalogue)


def _parse_level_mapping(raw: Any) -> tuple[tuple[int, int], ...]:
    if not isinstance(raw, Mapping):
        raise ValueError("Level mapping must be an object.")
    parsed = tuple(sorted((int(level), int(value)) for level, value in raw.items()))
    return parsed


def _value_for_level(mapping: tuple[tuple[int, int], ...], level: int) -> int:
    for candidate_level, value in mapping:
        if candidate_level == level:
            return value
    raise ValueError(f"Missing mapping for level {level}.")
