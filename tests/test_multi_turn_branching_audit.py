from __future__ import annotations

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import legal_actions, turn_steps
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
    assert "Overall summary:" in report


def test_classification_helpers_flag_expected_action_features() -> None:
    combined_scenario = load_scenario("scenarios/kogge_cloisters_hire_both_market_001.json")
    combined_action = _find_action(
        legal_actions(combined_scenario.state, combined_scenario.config),
        lambda action: (
            isinstance(action, FullTurnAction)
            and action.sow_route_building_id == "kogge"
            and action.sow_route_secondary_building_id == "cloisters"
            and action.sow_route_building_source == "market"
            and action.sow_route_secondary_building_source == "market"
        ),
    )
    assert audit.action_has_route_modifier(combined_action) is True
    assert audit.action_has_kogge(combined_action) is True
    assert audit.action_has_cloisters(combined_action) is True
    assert audit.action_has_combined_kogge_cloisters(combined_action) is True
    assert audit.action_hired_building_count(combined_action) >= 2
    assert audit.action_has_hire(combined_action) is True

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
    first = audit.collect_trace_results(trace_names=("basic_2p_round_flow",))
    second = audit.collect_trace_results(trace_names=("basic_2p_round_flow",))

    assert first == second
    rows = first[0].rows
    assert rows
    assert all(row.legal_action_count > 0 for row in rows)
    assert all(row.duplicate_action_id_count == 0 for row in rows)
    assert all(row.unique_action_id_count == row.legal_action_count for row in rows)
    assert all(row.full_turn_actions > 0 for row in rows)
    assert all(row.distinct_routes > 0 for row in rows)
    assert all(row.distinct_selected_duties > 0 for row in rows)
    assert all(row.max_picked_up_acolytes > 0 for row in rows)


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


def _find_action(actions, predicate):
    return next(action for action in actions if predicate(action))
