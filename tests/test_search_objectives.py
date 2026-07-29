from __future__ import annotations

import pytest

from pilgrim.evaluation import evaluate_player
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.enums import PlayerId
from pilgrim.rules.scoring import score_breakdown
from pilgrim.rules.transition import apply_action
from pilgrim.search.exact import solve_exact
from pilgrim.search.objectives import (
    SearchObjective,
    evaluate_search_leaf,
    objective_from_value,
)


def test_sandbox_objective_matches_current_evaluation() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_search_smoke_001.json")
    expected = evaluate_player(scenario.state, PlayerId.PLAYER_ONE, scenario.config).total
    actual = evaluate_search_leaf(
        scenario.state,
        PlayerId.PLAYER_ONE,
        scenario.config,
        SearchObjective.SANDBOX,
    )
    assert actual == expected


def test_implemented_official_objective_matches_score_sheet_total() -> None:
    scenario = load_scenario("scenarios/scoring_basic_breakdown_001.json")
    expected = score_breakdown(
        scenario.state,
        PlayerId.PLAYER_ONE,
        scenario.config,
    ).implemented_total
    actual = evaluate_search_leaf(
        scenario.state,
        PlayerId.PLAYER_ONE,
        scenario.config,
        SearchObjective.IMPLEMENTED_OFFICIAL_SCORE,
    )
    assert actual == expected


def test_sandbox_with_official_terminal_uses_official_only_at_game_over() -> None:
    in_progress = load_scenario("scenarios/mancala_sandbox_search_smoke_001.json")
    terminal = load_scenario("scenarios/scoring_basic_breakdown_001.json")

    in_progress_value = evaluate_search_leaf(
        in_progress.state,
        PlayerId.PLAYER_ONE,
        in_progress.config,
        SearchObjective.SANDBOX_WITH_OFFICIAL_TERMINAL,
    )
    in_progress_sandbox = evaluate_player(
        in_progress.state,
        PlayerId.PLAYER_ONE,
        in_progress.config,
    ).total
    assert in_progress_value == in_progress_sandbox

    terminal_value = evaluate_search_leaf(
        terminal.state,
        PlayerId.PLAYER_ONE,
        terminal.config,
        SearchObjective.SANDBOX_WITH_OFFICIAL_TERMINAL,
    )
    terminal_official = score_breakdown(
        terminal.state,
        PlayerId.PLAYER_ONE,
        terminal.config,
    ).implemented_total
    assert terminal_value == terminal_official


def test_unknown_objective_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown search objective"):
        objective_from_value("nonsense")


def test_solve_exact_default_matches_explicit_sandbox() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_search_smoke_001.json")
    default_result = solve_exact(scenario.state, scenario.config, depth=2)
    explicit_result = solve_exact(
        scenario.state,
        scenario.config,
        depth=2,
        objective=SearchObjective.SANDBOX,
    )

    assert default_result.objective is SearchObjective.SANDBOX
    assert default_result.best_score == explicit_result.best_score
    assert default_result.best_action_id == explicit_result.best_action_id
    assert default_result.principal_variation_ids == explicit_result.principal_variation_ids


def test_solve_exact_official_objective_scores_leaf_with_implemented_total() -> None:
    scenario = load_scenario("scenarios/mancala_sandbox_search_smoke_001.json")
    result = solve_exact(
        scenario.state,
        scenario.config,
        depth=1,
        objective=SearchObjective.IMPLEMENTED_OFFICIAL_SCORE,
    )

    assert result.objective is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE
    assert result.best_action is not None
    assert len(result.principal_variation) == 1

    final_state = apply_action(scenario.state, result.best_action, scenario.config).state
    expected = score_breakdown(
        final_state,
        scenario.root_player_id,
        scenario.config,
    ).implemented_total
    assert result.best_score == expected
    assert result.best_line_final_score_breakdown.implemented_total == expected
