"""Opponent-model placeholders for search orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pilgrim.model.enums import PlayerId


class OpponentModelType(Enum):
    """Available opponent model identifiers."""

    SANDBOX_ACTIVE_PLAYER_MAX = "sandbox_active_player_max"
    FIXED_SCHEDULE = "fixed_schedule"
    HEURISTIC = "heuristic"
    ADVERSARIAL = "adversarial"
    STOCHASTIC = "stochastic"


@dataclass(frozen=True, slots=True)
class OpponentModel:
    """Parsed opponent model configuration for a scenario."""

    type: OpponentModelType = OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX


def opponent_model_from_dict(raw: Mapping[str, Any] | None) -> OpponentModel:
    """Parse scenario opponent model config with safe defaults."""
    if raw is None:
        return OpponentModel()
    model_type = raw.get("type", OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX.value)
    return OpponentModel(type=OpponentModelType(str(model_type)))


def decision_player_for_node(
    *,
    active_player: PlayerId,
    root_player: PlayerId,
    opponent_model: OpponentModelType,
) -> PlayerId:
    """
    Return which player's local objective selects actions at this node.

    Current behavior:
    - `sandbox_active_player_max`: each active player picks actions maximizing
      their own sandbox evaluation.
    """
    if opponent_model is OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX:
        return active_player
    return root_player
