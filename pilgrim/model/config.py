"""Config models loaded from JSON files."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pilgrim.model.enums import DutyEffect


@dataclass(frozen=True, slots=True)
class BoardConfig:
    """Mancala position names and directed movement graph."""

    positions: tuple[str, ...]
    edges: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        if len(self.positions) != len(self.edges):
            raise ValueError("Board edges must match position count.")

    def index_for_name(self, position_name: str) -> int:
        try:
            return self.positions.index(position_name)
        except ValueError as exc:
            raise ValueError(f"Unknown position name: {position_name}") from exc

    def neighbors(self, position: int) -> tuple[int, ...]:
        return self.edges[position]


@dataclass(frozen=True, slots=True)
class DutyDefinition:
    """Config-driven duty behavior placeholder."""

    key: str
    position: int
    effect: DutyEffect


@dataclass(frozen=True, slots=True)
class PietyConfig:
    """Piety track bounds and VP scoring lookup."""

    max_position: int
    score_by_position: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.max_position < 0:
            raise ValueError("Piety max_position cannot be negative.")
        if len(self.score_by_position) != self.max_position + 1:
            raise ValueError(
                "Piety score_by_position length must equal max_position + 1."
            )

    def clamp(self, position: int) -> int:
        if position < 0:
            return 0
        if position > self.max_position:
            return self.max_position
        return position

    def score(self, position: int) -> int:
        return self.score_by_position[self.clamp(position)]


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Ruleset configuration bundle for scenario execution."""

    board: BoardConfig
    duties: tuple[DutyDefinition, ...]
    piety: PietyConfig

    def duty_for_position(self, position: int) -> DutyDefinition | None:
        for duty in self.duties:
            if duty.position == position:
                return duty
        return None

    def duty_positions(self) -> tuple[int, ...]:
        return tuple(duty.position for duty in self.duties)


def board_from_dict(raw: Mapping[str, Any]) -> BoardConfig:
    positions = tuple(str(name) for name in raw["positions"])
    edges_by_name = raw["edges"]
    if not isinstance(edges_by_name, Mapping):
        raise ValueError("Board 'edges' must be an object.")

    index_lookup = {name: idx for idx, name in enumerate(positions)}
    edges: list[tuple[int, ...]] = []
    for name in positions:
        raw_neighbors = edges_by_name.get(name, [])
        if not isinstance(raw_neighbors, list):
            raise ValueError(f"Neighbors for {name} must be a list.")
        neighbors = tuple(index_lookup[str(neighbor)] for neighbor in raw_neighbors)
        edges.append(neighbors)
    return BoardConfig(positions=positions, edges=tuple(edges))


def duties_from_dict(raw: Mapping[str, Any], board: BoardConfig) -> tuple[DutyDefinition, ...]:
    raw_duties = raw["duties"]
    if not isinstance(raw_duties, list):
        raise ValueError("Duty config must contain a 'duties' list.")

    duties: list[DutyDefinition] = []
    for raw_duty in raw_duties:
        position_name = str(raw_duty["position"])
        duties.append(
            DutyDefinition(
                key=str(raw_duty["key"]),
                position=board.index_for_name(position_name),
                effect=DutyEffect(str(raw_duty["effect"])),
            )
        )
    duties.sort(key=lambda duty: duty.position)
    return tuple(duties)


def piety_from_dict(raw: Mapping[str, Any]) -> PietyConfig:
    max_position = int(raw["max_position"])
    score_map = raw["score_by_position"]
    if not isinstance(score_map, Mapping):
        raise ValueError("Piety score_by_position must be an object.")

    score_by_position = tuple(int(score_map[str(index)]) for index in range(max_position + 1))
    return PietyConfig(max_position=max_position, score_by_position=score_by_position)


def game_config_from_dict(
    *,
    board_raw: Mapping[str, Any],
    duties_raw: Mapping[str, Any],
    piety_raw: Mapping[str, Any],
) -> GameConfig:
    board = board_from_dict(board_raw)
    duties = duties_from_dict(duties_raw, board)
    piety = piety_from_dict(piety_raw)
    return GameConfig(board=board, duties=duties, piety=piety)
