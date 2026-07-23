"""Duty-tile category identity and layout helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

DUTY_POSITIONS: tuple[str, ...] = (
    "north",
    "north_east",
    "east",
    "south_east",
    "south",
    "south_west",
    "west",
    "north_west",
)

DUTY_CATEGORIES: tuple[str, ...] = (
    "produce",
    "clerical",
    "give_alms",
    "allocation",
    "build_roads",
    "construct",
    "ordination",
    "taxation",
)

_DEFAULT_DUTY_TILES: tuple[tuple[str, str], ...] = (
    ("north", "produce"),
    ("north_east", "clerical"),
    ("east", "build_roads"),
    ("south_east", "construct"),
    ("south", "give_alms"),
    ("south_west", "ordination"),
    ("west", "allocation"),
    ("north_west", "taxation"),
)


@dataclass(frozen=True, slots=True)
class DutyTilesLayout:
    """Resolved duty-tile layout for one scenario configuration."""

    ordered_tiles: tuple[tuple[str, str], ...]
    board_indices_by_position: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.ordered_tiles) != len(DUTY_POSITIONS):
            raise ValueError("Duty tile layout must define all 8 duty positions.")
        if len(self.board_indices_by_position) != len(DUTY_POSITIONS):
            raise ValueError("Duty tile board index vector must match duty positions length.")

    def category_for_position_name(self, position_name: str) -> str:
        for name, category in self.ordered_tiles:
            if name == position_name:
                return category
        raise ValueError(f"Unknown duty position name: {position_name}")

    def category_for_board_index(self, board_position: int) -> str:
        try:
            index = self.board_indices_by_position.index(board_position)
        except ValueError as exc:
            raise ValueError(f"Board position {board_position} is not a duty tile.") from exc
        return self.ordered_tiles[index][1]

    def board_index_for_category(self, duty_category: str) -> int:
        validate_duty_category_name(duty_category)
        for (_position_name, category), board_index in zip(
            self.ordered_tiles,
            self.board_indices_by_position,
            strict=True,
        ):
            if category == duty_category:
                return board_index
        raise ValueError(
            f"Duty category {duty_category} missing from duty tile layout (invalid state)."
        )

    def position_name_for_category(self, duty_category: str) -> str:
        validate_duty_category_name(duty_category)
        for position_name, category in self.ordered_tiles:
            if category == duty_category:
                return position_name
        raise ValueError(
            f"Duty category {duty_category} missing from duty tile layout (invalid state)."
        )

    def mapping(self) -> dict[str, str]:
        return dict(self.ordered_tiles)

    def categories_in_order(self) -> tuple[str, ...]:
        return tuple(category for _, category in self.ordered_tiles)

    def board_duty_positions(self) -> tuple[int, ...]:
        return self.board_indices_by_position


def default_duty_tiles() -> dict[str, str]:
    """Return the deterministic fallback duty layout."""
    return dict(_DEFAULT_DUTY_TILES)


def validate_duty_category_name(duty_category: str) -> None:
    if duty_category not in DUTY_CATEGORIES:
        allowed = ", ".join(DUTY_CATEGORIES)
        raise ValueError(f"Unknown duty category '{duty_category}'. Allowed: {allowed}.")


def validate_duty_tiles(duty_tiles: Mapping[str, str]) -> None:
    """Validate one complete duty layout mapping."""
    keys = set(duty_tiles.keys())
    expected_positions = set(DUTY_POSITIONS)
    if keys != expected_positions:
        missing = sorted(expected_positions - keys)
        extra = sorted(keys - expected_positions)
        fragments: list[str] = []
        if missing:
            fragments.append(f"missing positions: {', '.join(missing)}")
        if extra:
            fragments.append(f"unknown positions: {', '.join(extra)}")
        raise ValueError("Invalid duty tile keys (" + "; ".join(fragments) + ").")

    if "city" in keys:
        raise ValueError("City cannot be used as a duty tile position.")

    categories = list(duty_tiles.values())
    unknown_categories = sorted(
        category for category in categories if category not in DUTY_CATEGORIES
    )
    if unknown_categories:
        raise ValueError(
            "Unknown duty categories in layout: " + ", ".join(sorted(set(unknown_categories))) + "."
        )

    category_counts: dict[str, int] = {}
    for category in categories:
        category_counts[category] = category_counts.get(category, 0) + 1

    duplicates = sorted(category for category, count in category_counts.items() if count > 1)
    if duplicates:
        raise ValueError("Duplicate duty categories in layout: " + ", ".join(duplicates) + ".")

    missing_categories = sorted(set(DUTY_CATEGORIES) - set(categories))
    if missing_categories:
        raise ValueError(
            "Missing duty categories in layout: " + ", ".join(missing_categories) + "."
        )

    if len(categories) != len(DUTY_CATEGORIES):
        raise ValueError("Duty layout must contain exactly 8 categories.")


def duty_tiles_layout_from_mapping(
    duty_tiles: Mapping[str, str],
    *,
    board_positions: tuple[str, ...],
) -> DutyTilesLayout:
    """
    Parse validated duty tiles into ordered category + board-index layout.

    Board positions are required to map position names to runtime indices.
    """
    validate_duty_tiles(duty_tiles)
    ordered_tiles = tuple((position, duty_tiles[position]) for position in DUTY_POSITIONS)
    indices: list[int] = []
    for position_name, _ in ordered_tiles:
        try:
            indices.append(board_positions.index(position_name))
        except ValueError as exc:
            raise ValueError(
                f"Duty position '{position_name}' missing from board positions."
            ) from exc
    return DutyTilesLayout(
        ordered_tiles=ordered_tiles,
        board_indices_by_position=tuple(indices),
    )


def duty_category_at_position(state_or_config: Any, position: int) -> str:
    """Return duty category at a board position from a config/layout-like object."""
    if isinstance(state_or_config, DutyTilesLayout):
        return state_or_config.category_for_board_index(position)
    if hasattr(state_or_config, "duty_category_for_position"):
        return str(state_or_config.duty_category_for_position(position))
    if hasattr(state_or_config, "duty_tiles"):
        return duty_category_at_position(state_or_config.duty_tiles, position)
    raise TypeError("Object does not expose duty tile layout access.")


def position_for_duty_category(state_or_config: Any, duty_category: str) -> str:
    """Return position name for a duty category from a config/layout-like object."""
    validate_duty_category_name(duty_category)
    if isinstance(state_or_config, DutyTilesLayout):
        return state_or_config.position_name_for_category(duty_category)
    if hasattr(state_or_config, "position_name_for_duty_category"):
        return str(state_or_config.position_name_for_duty_category(duty_category))
    if hasattr(state_or_config, "duty_tiles"):
        return position_for_duty_category(state_or_config.duty_tiles, duty_category)
    raise TypeError("Object does not expose duty tile layout access.")
