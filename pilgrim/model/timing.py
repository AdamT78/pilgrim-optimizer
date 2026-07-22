"""Timing state models for turn/round/season progression."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimingState:
    """Current timing position in the simplified sandbox timeline."""

    absolute_turn: int = 0
    round_number: int = 1
    season_number: int = 1
    turn_in_round: int = 0

    def __post_init__(self) -> None:
        if self.absolute_turn < 0:
            raise ValueError("absolute_turn cannot be negative.")
        if self.round_number < 1:
            raise ValueError("round_number must start at 1 or higher.")
        if self.season_number < 1:
            raise ValueError("season_number must start at 1 or higher.")
        if self.turn_in_round < 0:
            raise ValueError("turn_in_round cannot be negative.")
