from __future__ import annotations

from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.model.enums import TurnResolutionType
from pilgrim.rules.transition import apply_action, legal_actions
from tools.audits import building_status_branching_audit as audit
from tools.audits.turn_step_metrics import collect_turn_step_metrics


def test_audit_module_import_and_report_sections() -> None:
    report = audit.generate_report(
        scenario_paths=(
            "scenarios/produce_wheat_001.json",
            "scenarios/kogge_active_city_to_east_001.json",
        )
    )

    assert "=== Building Status Audit ===" in report
    assert "=== Safe Next Candidates ===" in report
    assert "=== Branching Count Audit ===" in report
    assert "Actions  Steps  StepSeq  Act×Seq" in report
    assert "PostWindow" in report
    assert "HiredSteps  Conversions  GrainStore  Relocations" in report


def test_building_status_includes_known_implemented_and_partial() -> None:
    rows = audit.collect_building_status_rows()
    status_by_id = {row.building_id: row.status for row in rows}

    assert status_by_id["well"] == "implemented"
    assert status_by_id["quarry"] == "implemented"
    assert status_by_id["mint"] == "implemented"
    assert status_by_id["chapel"] == "implemented"
    assert status_by_id["infirmary"] == "implemented"
    assert status_by_id["kogge"] == "implemented"
    assert status_by_id["cloisters"] == "implemented"
    assert status_by_id["dormitory"] == "implemented"
    assert status_by_id["inquisition"] == "implemented"
    assert status_by_id["library"] == "implemented"
    assert status_by_id["mill"] == "implemented"
    assert status_by_id["grain_store"] == "implemented"
    assert status_by_id["indulgences"] == "implemented"
    assert status_by_id["stone_yard"] == "implemented"
    assert status_by_id["brewery"] == "implemented"
    assert status_by_id["guild"] == "implemented"
    assert status_by_id["pulpit"] == "implemented"
    assert status_by_id["customs_house"] == "implemented"
    assert status_by_id["wagon_yard"] == "implemented"
    assert status_by_id["scriptorium"] == "implemented"
    assert status_by_id["chapter_house"] == "partial"
    assert status_by_id["confession_box"] == "implemented"
    assert status_by_id["bank"] == "implemented"
    assert status_by_id["reliquary"] == "deferred"


def test_branching_rows_are_deterministic_for_representative_subset() -> None:
    subset = (
        "scenarios/produce_wheat_001.json",
        "scenarios/kogge_active_city_to_east_001.json",
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
        "scenarios/dormitory_active_return_duty_to_city_001.json",
        "scenarios/inquisition_hire_market_city_to_duty_001.json",
        "scenarios/grain_store_active_sell_wheat_001.json",
    )
    first = audit.collect_branching_rows(scenario_paths=subset)
    second = audit.collect_branching_rows(scenario_paths=subset)

    assert first == second
    assert tuple(row.scenario_path for row in first) == subset
    assert all(row.legal_action_count > 0 for row in first)
    assert all(row.reachable_step_sequences > 0 for row in first)
    assert first[0].legal_action_count == 5
    assert first[0].turn_step_count == 0
    assert first[0].reachable_step_sequences == 1
    assert first[0].action_step_sequence_product == 5
    assert first[0].flag == ""
    assert first[2].legal_action_count >= 100
    assert first[2].flag in {"HIGH", "VERY HIGH"}

    dormitory, inquisition, grain_store = first[3:]
    assert dormitory.turn_step_count == 1
    assert dormitory.relocation_turn_steps == 1
    assert dormitory.reachable_step_sequences == 2
    assert dormitory.action_step_sequence_product == 24
    assert inquisition.hired_turn_steps == 8
    assert inquisition.relocation_turn_steps == 8
    assert inquisition.reachable_step_sequences == 9
    assert inquisition.action_step_sequence_product == 108
    assert grain_store.conversion_turn_steps == 3
    assert grain_store.grain_store_conversion_turn_steps == 3
    assert grain_store.reachable_step_sequences == 4
    assert grain_store.action_step_sequence_product == 12


def test_step_sequence_cap_reports_dropped_prefixes() -> None:
    scenario = load_scenario("scenarios/grain_store_active_sell_wheat_001.json")
    metrics = collect_turn_step_metrics(
        scenario.state,
        scenario.config,
        legal_action_count=len(legal_actions(scenario.state, scenario.config)),
        sequence_cap=1,
    )

    assert metrics.sequence_walk_truncated is True
    assert metrics.reachable_step_sequences == 1
    assert metrics.action_step_sequence_product == 3
    assert metrics.additional_dropped_step_sequence_prefix_count == 0
    assert metrics.dropped_step_sequence_prefixes == (
        ("turn_step:building_conversion:grain_store:from:own_active:direction:sell_wheat:amount:1",),
        ("turn_step:building_conversion:grain_store:from:own_active:direction:sell_wheat:amount:2",),
        ("turn_step:building_conversion:grain_store:from:own_active:direction:sell_wheat:amount:3",),
    )


def test_library_row_marks_its_post_resolution_window_unmeasured() -> None:
    rows = audit.collect_branching_rows(
        scenario_paths=("scenarios/library_active_city_to_duty_001.json",)
    )

    library = rows[0]
    assert library.turn_step_count == 0
    assert library.post_resolution_window_measured is False


def test_step_sequence_cap_counts_additional_omitted_prefixes() -> None:
    scenario = load_scenario("scenarios/library_active_city_to_duty_001.json")
    action = next(
        action
        for action in legal_actions(scenario.state, scenario.config)
        if isinstance(action, FullTurnAction)
        and action.resolution is TurnResolutionType.PRODUCE_WHEAT
    )
    post_resolution_state = apply_action(scenario.state, action, scenario.config).state
    metrics = collect_turn_step_metrics(
        post_resolution_state,
        scenario.config,
        legal_action_count=len(legal_actions(post_resolution_state, scenario.config)),
        sequence_cap=1,
    )

    assert metrics.sequence_walk_truncated is True
    assert len(metrics.dropped_step_sequence_prefixes) == 8
    assert metrics.additional_dropped_step_sequence_prefix_count == 1


def test_project_root_points_to_repository_root() -> None:
    root = audit.project_root()
    assert (root / "pyproject.toml").exists()
    assert (root / "configs" / "buildings.json").exists()
    assert root == Path(__file__).resolve().parents[1]
