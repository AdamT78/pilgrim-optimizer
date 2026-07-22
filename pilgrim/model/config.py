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
class AlmsConfig:
    """Alms track bounds, threshold rewards, and Alms-table scoring."""

    max_position: int
    threshold_rewards: tuple[tuple[int, str], ...]
    alms_table_scoring: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.max_position < 0:
            raise ValueError("Alms max_position cannot be negative.")
        if not self.alms_table_scoring:
            raise ValueError("Alms table scoring cannot be empty.")
        rows = [row for row, _ in self.threshold_rewards]
        if rows != sorted(rows):
            raise ValueError("Alms threshold rows must be sorted ascending.")
        if len(set(rows)) != len(rows):
            raise ValueError("Alms threshold rows must be unique.")
        if any(row < 0 or row > self.max_position for row in rows):
            raise ValueError("Alms threshold rows must be within alms track bounds.")

    def clamp(self, position: int) -> int:
        if position < 0:
            return 0
        if position > self.max_position:
            return self.max_position
        return position

    def threshold_reward_for_row(self, row: int) -> str | None:
        for threshold_row, reward_key in self.threshold_rewards:
            if threshold_row == row:
                return reward_key
        return None

    def score(self, acolytes_on_table: int) -> int:
        if acolytes_on_table <= 0:
            return self.alms_table_scoring[0]
        max_index = len(self.alms_table_scoring) - 1
        return self.alms_table_scoring[min(acolytes_on_table, max_index)]


@dataclass(frozen=True, slots=True)
class TimingConfig:
    """Simplified timing cadence for rounds/seasons in sandbox mode."""

    players_per_round: int
    rounds_per_season: int
    max_rounds: int
    max_absolute_turns: int

    def __post_init__(self) -> None:
        if self.players_per_round < 1:
            raise ValueError("players_per_round must be at least 1.")
        if self.rounds_per_season < 1:
            raise ValueError("rounds_per_season must be at least 1.")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1.")
        if self.max_absolute_turns < 1:
            raise ValueError("max_absolute_turns must be at least 1.")


@dataclass(frozen=True, slots=True)
class MerchantConfig:
    """Sandbox Merchant path and duty->resource lookup."""

    path: tuple[str, ...]
    resource_by_duty: tuple[tuple[str, str | None], ...]
    advance_after_full_turn: bool

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("Merchant path cannot be empty.")
        if not self.resource_by_duty:
            raise ValueError("Merchant resource_by_duty cannot be empty.")

        duty_names = {name for name, _ in self.resource_by_duty}
        valid_resources = {"stone", "silver", "wheat"}
        for _, resource in self.resource_by_duty:
            if resource is not None and resource not in valid_resources:
                raise ValueError(f"Invalid Merchant resource mapping: {resource}.")
        for duty in self.path:
            if duty not in duty_names:
                raise ValueError(f"Merchant path duty missing resource mapping: {duty}.")

    def duty_at(self, position: int) -> str:
        return self.path[position % len(self.path)]

    def resource_for_duty(self, duty: str) -> str | None:
        for name, resource in self.resource_by_duty:
            if name == duty:
                return resource
        raise ValueError(f"Unknown Merchant duty: {duty}")

    def resource_at(self, position: int) -> str | None:
        return self.resource_for_duty(self.duty_at(position))


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Ruleset configuration bundle for scenario execution."""

    board: BoardConfig
    duties: tuple[DutyDefinition, ...]
    piety: PietyConfig
    alms: AlmsConfig
    timing: TimingConfig
    merchant: MerchantConfig

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


def alms_from_dict(raw: Mapping[str, Any]) -> AlmsConfig:
    max_position = int(raw["max_position"])

    threshold_rewards_raw = raw["threshold_rewards"]
    if not isinstance(threshold_rewards_raw, Mapping):
        raise ValueError("Alms threshold_rewards must be an object.")
    threshold_rewards = tuple(
        sorted(
            (int(row), str(reward_key))
            for row, reward_key in threshold_rewards_raw.items()
        )
    )

    alms_table_scoring_raw = raw["alms_table_scoring"]
    if not isinstance(alms_table_scoring_raw, Mapping):
        raise ValueError("Alms alms_table_scoring must be an object.")
    score_rows = sorted(int(key) for key in alms_table_scoring_raw)
    if not score_rows or score_rows[0] != 0:
        raise ValueError("Alms table scoring must include row 0.")
    max_score_row = score_rows[-1]
    alms_table_scoring = tuple(
        int(alms_table_scoring_raw[str(index)]) for index in range(max_score_row + 1)
    )

    return AlmsConfig(
        max_position=max_position,
        threshold_rewards=threshold_rewards,
        alms_table_scoring=alms_table_scoring,
    )


def game_config_from_dict(
    *,
    board_raw: Mapping[str, Any],
    duties_raw: Mapping[str, Any],
    piety_raw: Mapping[str, Any],
    alms_raw: Mapping[str, Any],
    timing_raw: Mapping[str, Any],
    merchant_raw: Mapping[str, Any],
) -> GameConfig:
    board = board_from_dict(board_raw)
    duties = duties_from_dict(duties_raw, board)
    piety = piety_from_dict(piety_raw)
    alms = alms_from_dict(alms_raw)
    timing = timing_from_dict(timing_raw)
    merchant = merchant_from_dict(merchant_raw)
    return GameConfig(
        board=board,
        duties=duties,
        piety=piety,
        alms=alms,
        timing=timing,
        merchant=merchant,
    )


def timing_from_dict(raw: Mapping[str, Any]) -> TimingConfig:
    """Parse sandbox timing configuration."""
    return TimingConfig(
        players_per_round=int(raw["players_per_round"]),
        rounds_per_season=int(raw["rounds_per_season"]),
        max_rounds=int(raw["max_rounds"]),
        max_absolute_turns=int(raw["max_absolute_turns"]),
    )


def merchant_from_dict(raw: Mapping[str, Any]) -> MerchantConfig:
    """Parse sandbox Merchant path and resource lookup config."""
    path_raw = raw["path"]
    if not isinstance(path_raw, list):
        raise ValueError("Merchant path must be a list.")
    path = tuple(str(entry) for entry in path_raw)

    resource_lookup_raw = raw["resource_by_duty"]
    if not isinstance(resource_lookup_raw, Mapping):
        raise ValueError("Merchant resource_by_duty must be an object.")
    resource_by_duty = tuple(
        sorted(
            (
                str(duty_name),
                str(resource_name) if resource_name is not None else None,
            )
            for duty_name, resource_name in resource_lookup_raw.items()
        )
    )

    return MerchantConfig(
        path=path,
        resource_by_duty=resource_by_duty,
        advance_after_full_turn=bool(raw.get("advance_after_full_turn", True)),
    )
