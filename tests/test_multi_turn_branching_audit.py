from __future__ import annotations

import pytest

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingConversionStep, FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import apply_turn_step, legal_actions, turn_steps
from tools.audits import multi_turn_branching_audit as audit


def test_audit_report_contains_expected_headings() -> None:
    report = audit.generate_report(trace_names=("basic_2p_round_flow",))

    assert "Multi-Turn Branching Audit" in report
    assert "Trace: basic_2p_round_flow" in report
    assert "Branching totals:" in report
    assert "Base sow/action breakdown:" in report
    assert "Selected actions:" in report
    assert "Summary:" in report
    assert "Base branching summary:" in report
    assert "Committed turn steps:" in report
    assert "Steps  StepSeq  States  Act×Seq  Act×State" in report
    assert "Overall summary:" in report


def test_classification_helpers_flag_expected_action_features() -> None:
    combined_scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")
    state = combined_scenario.state
    for building_id in ("kogge", "cloisters"):
        step = next(
            step
            for step in turn_steps(state, combined_scenario.config)
            if step.building_id == building_id
        )
        state = apply_turn_step(
            state,
            combined_scenario.config,
            step,
        )
    combined_action = _find_action(
        legal_actions(state, combined_scenario.config),
        lambda action: (
            isinstance(action, FullTurnAction)
            and action.sow_route_building_id == "kogge"
            and action.sow_route_secondary_building_id == "cloisters"
            and action.sow_route_building_source is None
            and action.sow_route_secondary_building_source is None
        ),
    )
    assert audit.action_has_route_modifier(combined_action) is True
    assert audit.action_has_kogge(combined_action) is True
    assert audit.action_has_cloisters(combined_action) is True
    assert audit.action_has_combined_kogge_cloisters(combined_action) is True
    assert audit.action_hired_building_count(combined_action) == 0
    assert audit.action_has_hire(combined_action) is False

    grain_scenario = load_scenario("scenarios/grain_store_hire_market_sell_wheat_001.json")
    grain_steps = turn_steps(grain_scenario.state, grain_scenario.config)
    assert any(
        step.building_id == "grain_store"
        and step.source == "market"
        for step in grain_steps
    )

    plain_scenario = load_scenario("scenarios/alms_sandbox_001.json")
    plain_action = _find_action(
        legal_actions(plain_scenario.state, plain_scenario.config),
        lambda action: (
            isinstance(action, FullTurnAction)
            and action.resolution is TurnResolutionType.TITHE
        ),
    )
    assert audit.action_has_route_modifier(plain_action) is False
    assert audit.action_has_building_conversion(plain_action) is False
    assert audit.action_hired_building_count(plain_action) == 0
    assert audit.action_has_hire(plain_action) is False


def test_trace_rows_are_deterministic_and_have_no_duplicate_action_ids() -> None:
    trace_names = ("basic_2p_round_flow", "grain_store_2p")
    first = audit.collect_trace_results(trace_names=trace_names)
    second = audit.collect_trace_results(trace_names=trace_names)

    assert first == second
    rows = tuple(row for result in first for row in result.rows)
    assert rows
    assert all(row.legal_action_count > 0 for row in rows)
    assert all(row.reachable_step_sequences > 0 for row in rows)
    assert all(row.distinct_reachable_states > 0 for row in rows)
    assert all(row.action_step_sequence_product >= row.legal_action_count for row in rows)
    assert all(row.action_distinct_state_product >= row.legal_action_count for row in rows)
    assert all(row.duplicate_action_id_count == 0 for row in rows)
    assert all(row.unique_action_id_count == row.legal_action_count for row in rows)
    assert all(row.full_turn_actions > 0 for row in rows)
    assert all(row.distinct_routes > 0 for row in rows)
    assert all(row.distinct_selected_duties > 0 for row in rows)
    assert all(row.max_picked_up_acolytes > 0 for row in rows)

    grain_store_rows = first[1].rows
    assert grain_store_rows[0].grain_store_conversion_turn_steps == 3
    assert grain_store_rows[0].reachable_step_sequences == 4
    assert grain_store_rows[0].distinct_reachable_states == 4
    assert grain_store_rows[0].action_step_sequence_product == 12
    assert grain_store_rows[0].action_distinct_state_product == 12
    assert grain_store_rows[0].pre_action_step_commits
    assert all(
        "building_conversion:grain_store" in commit.selected_step_id
        for commit in grain_store_rows[0].pre_action_step_commits
    )
    assert audit._likely_branching_driver(grain_store_rows[0]) == "committed turn-step branching"


def test_pulpit_trace_records_hired_step_branching_before_sowing() -> None:
    result = audit.collect_trace_results(trace_names=("pulpit_hire_2p",))[0]
    first_row = result.rows[0]

    assert first_row.legal_action_count == 3
    assert first_row.turn_step_count == 1
    assert first_row.reachable_step_sequences == 2
    assert first_row.hired_turn_steps == 1
    assert first_row.pre_action_step_commits
    assert "building_activation:pulpit:from:market:pay:wheat" in (
        first_row.pre_action_step_commits[0].selected_step_id
    )


def test_generated_setup_three_and_four_player_traces_run() -> None:
    results = audit.collect_trace_results(
        trace_names=("generated_setup_3p", "generated_setup_4p"),
    )

    assert tuple(result.definition.name for result in results) == (
        "generated_setup_3p",
        "generated_setup_4p",
    )
    assert all(result.rows for result in results)
    assert all(row.legal_action_count > 0 for result in results for row in result.rows)
    assert all(row.duplicate_action_id_count == 0 for result in results for row in result.rows)
    assert all(row.full_turn_actions > 0 for result in results for row in result.rows)
    assert all(row.distinct_routes > 0 for result in results for row in result.rows)
    assert all(row.distinct_selected_duties > 0 for result in results for row in result.rows)
    assert all(row.max_picked_up_acolytes > 0 for result in results for row in result.rows)

    three_players = {row.active_player for row in results[0].rows}
    four_players = {row.active_player for row in results[1].rows}
    assert "player_three" in three_players
    assert "player_four" in four_players


def test_post_resolution_turn_steps_are_recorded_before_end_turn() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")

    rows = audit._run_trace_rows(
        trace_name="library_window",
        state=scenario.state,
        config=scenario.config,
        steps=1,
        selector=lambda actions, _config, _step: next(
            action
            for action in actions
            if isinstance(action, FullTurnAction)
            and action.resolution is TurnResolutionType.PRODUCE_WHEAT
        ),
        turn_step_selector=audit._select_lowest_turn_step,
    )

    assert rows[0].post_resolution_step_commits
    commit = rows[0].post_resolution_step_commits[0]
    assert commit.window == "post-resolution"
    assert any("building_relocation:library" in step_id for step_id in commit.offered_step_ids)
    assert "building_relocation:library" in commit.selected_step_id


def test_grain_store_step_selector_fails_loudly_without_a_grain_store_step() -> None:
    with pytest.raises(ValueError, match="offered no Grain Store conversion step"):
        audit._select_grain_store_action(
            (BuildingConversionStep("brewery", "own_active", "sell_wheat_for_silver", 1),),
            None,  # type: ignore[arg-type]
            1,
            "pre-action",
        )


def _find_action(actions, predicate):
    return next(action for action in actions if predicate(action))
