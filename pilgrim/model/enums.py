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

    SETUP_SOW = "setup_sow"
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
    ALLOCATION = "allocation"


class TurnResolutionType(Enum):
    """Simplified full-turn action choices for the sandbox."""

    PRODUCE_WHEAT = "produce_wheat"
    PRODUCE_STONE = "produce_stone"
    BUILD_ROADS_DEFERRED = "build_roads_deferred"
    CONSTRUCT_BUILDING = "construct_building"
    CONSTRUCT_BUILDING_AND_ROAD_DEFERRED = "construct_building_and_road_deferred"
    CONSTRUCT_ROAD_DEFERRED = "construct_road_deferred"
    CLERICAL_DEVOTION = "clerical_devotion"
    CLERICAL_SILVERSMITH = "clerical_silversmith"
    GIVE_ALMS_PAID = "give_alms_paid"
    GIVE_ALMS_DONATE_BUILDING = "give_alms_donate_building"
    ORDINATION = "ordination"
    TAXATION = "taxation"
    ALLOCATION = "allocation"
    TITHE = "tithe"

    # Backward-compatible aliases for prior canonical names.
    CONSTRUCT_DEFERRED = "construct_road_deferred"
    GIVE_ALMS = "give_alms_paid"
    DONATE_BUILDING = "give_alms_donate_building"

    @classmethod
    def _missing_(cls, value: object) -> TurnResolutionType | None:
        """Support loading legacy action-name strings from older fixtures/logs."""
        if not isinstance(value, str):
            return None
        legacy_map = {
            "construct_deferred": cls.CONSTRUCT_ROAD_DEFERRED.value,
            "give_alms": cls.GIVE_ALMS_PAID.value,
            "donate_building": cls.GIVE_ALMS_DONATE_BUILDING.value,
        }
        mapped = legacy_map.get(value)
        if mapped is None:
            return None
        return cls(mapped)


class ActionType(Enum):
    """Action categories used for stable action IDs and logging."""

    SETUP_SOW = "setup_sow"
    FULL_TURN = "full_turn"
    SOW = "sow"
    RESOLVE_DUTY = "resolve_duty"
    TITHE = "tithe"


class EventType(Enum):
    """Structured transition event categories."""

    SETUP_SOWING = "setup_sowing"
    SETUP_SOW_COMPLETE = "setup_sow_complete"
    SETUP_PLAYER_ADVANCE = "setup_player_advance"
    SETUP_COMPLETE = "setup_complete"
    SOWING = "sowing"
    DUTY_RESOLUTION = "duty_resolution"
    DUTY_DEFERRED = "duty_deferred"
    RESOURCE_DELTA = "resource_delta"
    PIETY_DELTA = "piety_delta"
    ACOLYTE_RECALL = "acolyte_recall"
    ORDINATION = "ordination"
    TAXATION = "taxation"
    ALMS_PAYMENT = "alms_payment"
    BUILDING_DONATION = "building_donation"
    BUILDING_CONSTRUCTED = "building_constructed"
    BUILDING_HIRED = "building_hired"
    BUILDING_BONUS = "building_bonus"
    ALMS_PROGRESS = "alms_progress"
    ALMS_THRESHOLD_REWARD = "alms_threshold_reward"
    ALMS_SEASON_REWARD = "alms_season_reward"
    ALMS_RESET = "alms_reset"
    ALLOCATION = "allocation"
    SPECIAL_ACTIVITY_BONUS = "special_activity_bonus"
    DUMMY_ACOLYTE_MOVE = "dummy_acolyte_move"
    MERCHANT_ADVANCE = "merchant_advance"
    EXCESS_CHECK = "excess_check"
    EXCESS_DISCARD = "excess_discard"
    SHIP_ADVANCE = "ship_advance"
    TRADE_ROUTE_INCOME_SKIPPED = "trade_route_income_skipped"
    START_PLAYER_TIE_BREAK = "start_player_tie_break"
    START_PLAYER_SELECTION = "start_player_selection"
    GAME_END = "game_end"
    TURN_ADVANCE = "turn_advance"
    ROUND_END = "round_end"
    ROUND_ADVANCE = "round_advance"
    SEASON_END = "season_end"
    SEASON_ADVANCE = "season_advance"
    INVARIANT_CHECK = "invariant_check"
