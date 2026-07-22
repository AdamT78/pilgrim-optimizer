"""Resource model with immutable update helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Resources:
    """Simple immutable resource pool for the sandbox."""

    stone: int = 0
    silver: int = 0
    wheat: int = 0

    def __post_init__(self) -> None:
        if self.stone < 0 or self.silver < 0 or self.wheat < 0:
            raise ValueError("Resources cannot be negative.")

    def add(self, *, stone: int = 0, silver: int = 0, wheat: int = 0) -> Resources:
        """Return a new resource pool with deterministic deltas."""
        return Resources(
            stone=self.stone + stone,
            silver=self.silver + silver,
            wheat=self.wheat + wheat,
        )

    def score(self) -> int:
        """Temporary search score contribution."""
        return self.stone + self.silver + self.wheat
