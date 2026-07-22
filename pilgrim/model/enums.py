"""Enum types shared across engine modules."""

from __future__ import annotations

from enum import Enum, IntEnum

CANONICAL_POSITION_NAMES: tuple[str, ...] = (
    "city",
    "north",
    "north_east",
    "east",
    "south_east",
    "south",
    "south_west",
    "west",
    "north_west",
)


def position_name(position_id: int, positions: tuple[str, ...] | None = None) -> str:
    """Return the canonical readable name for a position index."""
    if positions is not None and 0 <= position_id < len(positions):
        return positions[position_id]
    if 0 <= position_id < len(CANONICAL_POSITION_NAMES):
        return CANONICAL_POSITION_NAMES[position_id]
    return f"position_{position_id}"


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
    GIVE_ALMS = "give_alms"


class TurnResolutionType(Enum):
    """Simplified full-turn action choices for the sandbox."""

    PRODUCE = "produce"
    CLERICAL_DEVOTION = "clerical_devotion"
    CLERICAL_SILVERSMITH = "clerical_silversmith"
    GIVE_ALMS = "give_alms"
    TITHE = "tithe"


class ActionType(Enum):
    """Action categories used for stable action IDs and logging."""

    FULL_TURN = "full_turn"
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
    ALMS_PAYMENT = "alms_payment"
    ALMS_PROGRESS = "alms_progress"
    ALMS_THRESHOLD_REWARD = "alms_threshold_reward"
    ALMS_SEASON_REWARD = "alms_season_reward"
    ALMS_RESET = "alms_reset"
    MERCHANT_ADVANCE = "merchant_advance"
    TURN_ADVANCE = "turn_advance"
    ROUND_END = "round_end"
    ROUND_ADVANCE = "round_advance"
    SEASON_END = "season_end"
    SEASON_ADVANCE = "season_advance"
    INVARIANT_CHECK = "invariant_check"
