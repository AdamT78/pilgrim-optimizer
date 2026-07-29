from __future__ import annotations

from pathlib import Path

from tools.audits import building_status_branching_audit as audit


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
    assert status_by_id["reliquary"] == "deferred"
    assert status_by_id["bank"] == "deferred"


def test_branching_rows_are_deterministic_for_representative_subset() -> None:
    subset = (
        "scenarios/produce_wheat_001.json",
        "scenarios/kogge_active_city_to_east_001.json",
        "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
    )
    first = audit.collect_branching_rows(scenario_paths=subset)
    second = audit.collect_branching_rows(scenario_paths=subset)

    assert first == second
    assert tuple(row.scenario_path for row in first) == subset
    assert all(row.total_actions > 0 for row in first)
    assert first[0].total_actions == 4
    assert first[0].flag == ""
    assert first[2].total_actions >= 100
    assert first[2].flag in {"HIGH", "VERY HIGH"}


def test_project_root_points_to_repository_root() -> None:
    root = audit.project_root()
    assert (root / "pyproject.toml").exists()
    assert (root / "configs" / "buildings.json").exists()
    assert root == Path(__file__).resolve().parents[1]
