"""Depth-limited exact search placeholder for Ruleset A.

This module intentionally uses a temporary objective:
`victory_points + piety_track_vp + stone + silver + wheat`
and should be replaced once full scoring is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilgrim.model.actions import GameAction, action_id
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.state import GameState
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.search.evaluation import evaluate_state


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result container for exact search runs."""

    best_score: int
    best_action: GameAction | None
    best_action_id: str | None
    principal_variation: tuple[GameAction, ...]
    principal_variation_ids: tuple[str, ...]
    nodes_expanded: int


def solve_exact(initial_state: GameState, config: GameConfig, depth: int) -> SearchResult:
    """Run deterministic depth-limited minimax over full-turn actions."""
    if depth < 0:
        raise ValueError("Depth must be non-negative.")

    root_player = initial_state.active_player
    memo: dict[tuple[GameState, int, PlayerId], tuple[int, tuple[GameAction, ...]]] = {}
    nodes_expanded = 0

    def search(state: GameState, remaining_depth: int) -> tuple[int, tuple[GameAction, ...]]:
        nonlocal nodes_expanded
        memo_key = (state, remaining_depth, root_player)
        if memo_key in memo:
            return memo[memo_key]

        nodes_expanded += 1
        actions = legal_actions(state, config)
        if remaining_depth == 0 or not actions:
            result = (_evaluate_state(state, root_player, config), ())
            memo[memo_key] = result
            return result

        maximizing = state.active_player is root_player
        best_score = float("-inf") if maximizing else float("inf")
        best_line: tuple[GameAction, ...] = ()
        for action in actions:
            child_state = apply_action(state, action, config).state
            child_score, child_line = search(child_state, remaining_depth - 1)
            candidate_line = (action, *child_line)
            if maximizing and child_score > best_score:
                best_score = child_score
                best_line = candidate_line
            if not maximizing and child_score < best_score:
                best_score = child_score
                best_line = candidate_line

        result = (int(best_score), best_line)
        memo[memo_key] = result
        return result

    best_score, principal_variation = search(initial_state, depth)
    best_action = principal_variation[0] if principal_variation else None
    principal_variation_ids = tuple(action_id(action) for action in principal_variation)
    return SearchResult(
        best_score=best_score,
        best_action=best_action,
        best_action_id=action_id(best_action) if best_action else None,
        principal_variation=principal_variation,
        principal_variation_ids=principal_variation_ids,
        nodes_expanded=nodes_expanded,
    )


def _evaluate_state(state: GameState, perspective: PlayerId, config: GameConfig) -> int:
    """Temporary objective for early experimentation."""
    return evaluate_state(state, perspective, config).total
