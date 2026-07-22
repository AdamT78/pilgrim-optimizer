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
from pilgrim.opponents import OpponentModelType, decision_player_for_node
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.search.evaluation import evaluate_state


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result container for exact search runs."""

    root_player_id: PlayerId
    opponent_model_type: OpponentModelType
    best_score: int
    best_action: GameAction | None
    best_action_id: str | None
    principal_variation: tuple[GameAction, ...]
    principal_variation_ids: tuple[str, ...]
    nodes_expanded: int


def solve_exact(
    initial_state: GameState,
    config: GameConfig,
    depth: int,
    *,
    root_player_id: PlayerId | int | None = None,
    opponent_model_type: OpponentModelType = OpponentModelType.SANDBOX_ACTIVE_PLAYER_MAX,
) -> SearchResult:
    """
    Run deterministic depth-limited search over full-turn actions.

    For `sandbox_active_player_max`, each active player selects actions maximizing
    their own sandbox evaluation, while terminal/cutoff scoring is still taken from
    the root player's perspective.
    """
    if depth < 0:
        raise ValueError("Depth must be non-negative.")

    root_player = (
        initial_state.active_player if root_player_id is None else PlayerId(int(root_player_id))
    )
    memo: dict[
        tuple[GameState, int, PlayerId, OpponentModelType],
        tuple[int, tuple[int, int], tuple[GameAction, ...]],
    ] = {}
    nodes_expanded = 0

    def search(
        state: GameState, remaining_depth: int
    ) -> tuple[int, tuple[int, int], tuple[GameAction, ...]]:
        nonlocal nodes_expanded
        memo_key = (state, remaining_depth, root_player, opponent_model_type)
        if memo_key in memo:
            return memo[memo_key]

        nodes_expanded += 1
        actions = legal_actions(state, config)
        if remaining_depth == 0 or not actions:
            scores = (
                _evaluate_state(state, PlayerId.PLAYER_ONE, config),
                _evaluate_state(state, PlayerId.PLAYER_TWO, config),
            )
            result = (scores[int(root_player)], scores, ())
            memo[memo_key] = result
            return result

        decision_player = decision_player_for_node(
            active_player=state.active_player,
            root_player=root_player,
            opponent_model=opponent_model_type,
        )
        best_actor_score = float("-inf")
        best_root_score = float("-inf")
        best_scores = (0, 0)
        best_line: tuple[GameAction, ...] = ()
        for action in actions:
            child_state = apply_action(state, action, config).state
            child_root_score, child_scores, child_line = search(child_state, remaining_depth - 1)
            actor_score = child_scores[int(decision_player)]
            candidate_line = (action, *child_line)
            if actor_score > best_actor_score:
                best_actor_score = actor_score
                best_root_score = child_root_score
                best_scores = child_scores
                best_line = candidate_line
            elif actor_score == best_actor_score and child_root_score > best_root_score:
                best_root_score = child_root_score
                best_scores = child_scores
                best_line = candidate_line

        result = (int(best_root_score), best_scores, best_line)
        memo[memo_key] = result
        return result

    best_score, _, principal_variation = search(initial_state, depth)
    best_action = principal_variation[0] if principal_variation else None
    principal_variation_ids = tuple(action_id(action) for action in principal_variation)
    return SearchResult(
        root_player_id=root_player,
        opponent_model_type=opponent_model_type,
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
