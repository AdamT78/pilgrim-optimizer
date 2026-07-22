"""Pure helpers for piety track movement and scoring."""

from __future__ import annotations

from pilgrim.model.config import PietyConfig


def clamp_piety(position: int, piety_config: PietyConfig) -> int:
    """Clamp a piety position to the configured track bounds."""
    return piety_config.clamp(position)


def move_piety(position: int, amount: int, piety_config: PietyConfig) -> int:
    """Move piety position forward by amount with cap at max_position."""
    return clamp_piety(position + amount, piety_config)


def score_piety(position: int, piety_config: PietyConfig) -> int:
    """Return piety track VP for a position using config lookup."""
    return piety_config.score(position)
