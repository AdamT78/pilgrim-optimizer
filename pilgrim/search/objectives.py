"""Selectable leaf-scoring objectives for exact search."""

from __future__ import annotations

from enum import Enum

from pilgrim.evaluation.breakdown import evaluate_player
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId
from pilgrim.model.state import GameState
from pilgrim.rules.scoring import score_breakdown


class SearchObjective(Enum):
    """Supported leaf-scoring objectives for exact search."""

    SANDBOX = "sandbox"
    IMPLEMENTED_OFFICIAL_SCORE = "implemented_official_score"
    SANDBOX_WITH_OFFICIAL_TERMINAL = "sandbox_with_official_terminal"


_OBJECTIVE_BY_KEY: dict[str, SearchObjective] = {
    "sandbox": SearchObjective.SANDBOX,
    "implemented_official_score": SearchObjective.IMPLEMENTED_OFFICIAL_SCORE,
    "sandbox_with_official_terminal": SearchObjective.SANDBOX_WITH_OFFICIAL_TERMINAL,
}


def objective_from_value(objective: SearchObjective | str) -> SearchObjective:
    """Parse objective enum/string values, accepting hyphen/underscore spellings."""
    if isinstance(objective, SearchObjective):
        return objective

    key = str(objective).strip().lower().replace("-", "_")
    try:
        return _OBJECTIVE_BY_KEY[key]
    except KeyError as exc:
        allowed = ", ".join(sorted(_OBJECTIVE_BY_KEY))
        raise ValueError(f"Unknown search objective '{objective}'. Allowed: {allowed}.") from exc


def evaluate_search_leaf(
    state: GameState,
    player: PlayerId,
    config: GameConfig,
    objective: SearchObjective | str,
) -> int:
    """Return a player score for one leaf state under the selected objective."""
    resolved = objective_from_value(objective)

    if resolved is SearchObjective.SANDBOX:
        return evaluate_player(state, player, config).total

    if resolved is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE:
        return score_breakdown(state, player, config).implemented_total

    # Hybrid objective: use sandbox unless terminal state is reached.
    if state.game_over:
        return score_breakdown(state, player, config).implemented_total
    return evaluate_player(state, player, config).total


def objective_cli_name(objective: SearchObjective) -> str:
    """Return kebab-case CLI spelling for a search objective."""
    return objective.value.replace("_", "-")


def objective_cli_choices() -> tuple[str, ...]:
    """Return stable CLI spelling choices in display order."""
    return tuple(
        objective_cli_name(objective)
        for objective in (
            SearchObjective.SANDBOX,
            SearchObjective.IMPLEMENTED_OFFICIAL_SCORE,
            SearchObjective.SANDBOX_WITH_OFFICIAL_TERMINAL,
        )
    )


def objective_from_cli_name(name: str) -> SearchObjective:
    """Parse kebab-case CLI objective names."""
    return objective_from_value(name)


def objective_description(objective: SearchObjective | str) -> str:
    """Return human-readable objective text for CLI output."""
    resolved = objective_from_value(objective)
    if resolved is SearchObjective.SANDBOX:
        return "maximize root player sandbox evaluation"
    if resolved is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE:
        return "maximize root player implemented official score"
    return "maximize root player sandbox evaluation (official score at terminal states)"
