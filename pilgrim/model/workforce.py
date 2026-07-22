"""Workforce pool models and helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace

MANCALA_POSITION_COUNT = 9


@dataclass(frozen=True, slots=True)
class CommittedAcolytes:
    """Committed workforce pools reserved for future systems."""

    roads: int = 0
    shrines: int = 0
    market_ports: int = 0
    pilgrimage_sites: int = 0
    alms_table: int = 0

    def __post_init__(self) -> None:
        if self.roads < 0:
            raise ValueError("Committed roads acolytes cannot be negative.")
        if self.shrines < 0:
            raise ValueError("Committed shrines acolytes cannot be negative.")
        if self.market_ports < 0:
            raise ValueError("Committed market port acolytes cannot be negative.")
        if self.pilgrimage_sites < 0:
            raise ValueError("Committed pilgrimage site acolytes cannot be negative.")
        if self.alms_table < 0:
            raise ValueError("Committed alms table acolytes cannot be negative.")

    @property
    def total(self) -> int:
        return (
            self.roads
            + self.shrines
            + self.market_ports
            + self.pilgrimage_sites
            + self.alms_table
        )


@dataclass(frozen=True, slots=True)
class Workforce:
    """All workforce locations for one player."""

    mancala: tuple[int, ...]
    village: int = 0
    abbey: int = 0
    committed: CommittedAcolytes = CommittedAcolytes()

    def __post_init__(self) -> None:
        if len(self.mancala) != MANCALA_POSITION_COUNT:
            raise ValueError(
                f"Mancala workforce must contain {MANCALA_POSITION_COUNT} positions."
            )
        if any(count < 0 for count in self.mancala):
            raise ValueError("Mancala workforce counts cannot be negative.")
        if self.village < 0:
            raise ValueError("Village acolytes cannot be negative.")
        if self.abbey < 0:
            raise ValueError("Abbey acolytes cannot be negative.")

    @property
    def mancala_total(self) -> int:
        return sum(self.mancala)

    @property
    def committed_total(self) -> int:
        return self.committed.total

    @property
    def total(self) -> int:
        return self.mancala_total + self.village + self.abbey + self.committed_total


def mancala_total(workforce: Workforce) -> int:
    """Return total acolytes currently on mancala positions."""
    return workforce.mancala_total


def committed_total(workforce: Workforce) -> int:
    """Return total committed acolytes."""
    return workforce.committed_total


def total_acolytes(workforce: Workforce) -> int:
    """Return total workforce across all currently tracked pools."""
    return workforce.total


def replace_mancala(workforce: Workforce, new_mancala: tuple[int, ...]) -> Workforce:
    """Return a new workforce with replaced mancala counts."""
    return replace(workforce, mancala=new_mancala)
