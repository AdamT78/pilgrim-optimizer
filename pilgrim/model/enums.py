"""Enum types shared across engine modules."""

from __future__ import annotations

from enum import Enum, IntEnum


class PlayerId(IntEnum):
    """Stable player ordering for tuple-indexed state containers."""

    PLAYER_ONE = 0
    PLAYER_TWO = 1

    def opponent(self) -> PlayerId:
        """Return the opposing player in a two-player sandbox."""
        return PlayerId.PLAYER_TWO if self is PlayerId.PLAYER_ONE else PlayerId.PLAYER_ONE

    @classmethod
    def from_string(cls, value: str) -> PlayerId:
        mapping = {
            "player_one": cls.PLAYER_ONE,
            "player_two": cls.PLAYER_TWO,
            "1": cls.PLAYER_ONE,
            "2": cls.PLAYER_TWO,
        }
        try:
            return mapping[value]
        except KeyError as exc:
            raise ValueError(f"Unknown player identifier: {value}") from exc


class TurnPhase(Enum):
    """Top-level turn phase for the Mancala sandbox."""

    SOW = "sow"
    DUTY = "duty"

    @classmethod
    def from_string(cls, value: str) -> TurnPhase:
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unknown turn phase: {value}") from exc


class DutyStrength(Enum):
    """Relative control level at a duty position."""

    MAJORITY = "majority"
    PARITY = "parity"
    MINORITY = "minority"


class DutyEffect(Enum):
    """Placeholder duty effects implemented in Ruleset A."""

    PRODUCE = "produce"
    CLERICAL_DEVOTION = "clerical_devotion"
    CLERICAL_SILVERSMITH = "clerical_silversmith"


class ActionType(Enum):
    """Action categories used for stable action IDs and logging."""

    SOW = "sow"
    RESOLVE_DUTY = "resolve_duty"
    TITHE = "tithe"


class EventType(Enum):
    """Structured transition event categories."""

    SOWING = "sowing"
    DUTY_RESOLUTION = "duty_resolution"
    RESOURCE_DELTA = "resource_delta"
    PIETY_DELTA = "piety_delta"
    ACOLYTE_RECALL = "acolyte_recall"
    INVARIANT_CHECK = "invariant_check"
