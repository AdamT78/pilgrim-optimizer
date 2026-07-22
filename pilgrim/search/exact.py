"""Depth-limited exact search placeholder for Ruleset A.

This module intentionally uses a temporary objective:
`victory_points + piety + stone + silver + wheat`
and should be replaced once full scoring is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.actions import GameAction, action_id
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.state import GameState
from pilgrim.rules.transition import apply_action, legal_actions


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result container for exact search runs."""

    best_score: int
    best_action: GameAction | None
    best_action_id: str | None
    nodes_expanded: int


def solve_exact(initial_state: GameState, config: GameConfig, depth: int) -> SearchResult:
    """Run deterministic depth-limited minimax with memoization."""
    if depth < 0:
        raise ValueError("Depth must be non-negative.")

    root_player = initial_state.active_player
    memo: dict[tuple[GameState, int, PlayerId], tuple[int, GameAction | None]] = {}
    nodes_expanded = 0

    def search(state: GameState, remaining_depth: int) -> tuple[int, GameAction | None]:
        nonlocal nodes_expanded
        memo_key = (state, remaining_depth, root_player)
        if memo_key in memo:
            return memo[memo_key]

        nodes_expanded += 1
        actions = legal_actions(state, config)
        if remaining_depth == 0 or not actions:
            result = (_evaluate_state(state, root_player), None)
            memo[memo_key] = result
            return result

        maximizing = state.active_player is root_player
        best_score = float("-inf") if maximizing else float("inf")
        best_action: GameAction | None = None
        for action in actions:
            child_state = apply_action(state, action, config).state
            child_score, _ = search(child_state, remaining_depth - 1)
            if maximizing and child_score > best_score:
                best_score = child_score
                best_action = action
            if not maximizing and child_score < best_score:
                best_score = child_score
                best_action = action

        result = (int(best_score), best_action)
        memo[memo_key] = result
        return result

    best_score, best_action = search(initial_state, depth)
    return SearchResult(
        best_score=best_score,
        best_action=best_action,
        best_action_id=action_id(best_action) if best_action else None,
        nodes_expanded=nodes_expanded,
    )


def _evaluate_state(state: GameState, perspective: PlayerId) -> int:
    """Temporary objective for early experimentation."""
    return state.player_state(perspective).value_score()
