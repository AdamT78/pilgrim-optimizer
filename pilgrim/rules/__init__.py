"""Deterministic rules engine modules."""

from pilgrim.rules.alms import (
    apply_alms_threshold_reward,
    clamp_alms_position,
    crossed_alms_thresholds,
    move_alms_position,
    resolve_alms_season_end,
    resolve_give_alms,
    score_alms_table,
)
from pilgrim.rules.piety import clamp_piety, move_piety, score_piety
from pilgrim.rules.timing import (
    advance_active_player,
    advance_timing,
    is_round_end,
    is_season_end,
    resolve_round_end,
    resolve_season_end,
)
from pilgrim.rules.transition import TransitionResult, apply_action, legal_actions
from pilgrim.rules.validation import TransitionValidationError, validate_state_invariants

__all__ = [
    "apply_alms_threshold_reward",
    "clamp_alms_position",
    "crossed_alms_thresholds",
    "move_alms_position",
    "resolve_alms_season_end",
    "resolve_give_alms",
    "score_alms_table",
    "advance_active_player",
    "advance_timing",
    "clamp_piety",
    "is_round_end",
    "is_season_end",
    "move_piety",
    "resolve_round_end",
    "resolve_season_end",
    "score_piety",
    "TransitionResult",
    "TransitionValidationError",
    "apply_action",
    "legal_actions",
    "validate_state_invariants",
]
