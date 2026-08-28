from __future__ import annotations

import json

import pytest

from tools.audits import route_modifier_hire_manifest as manifest


def test_manifest_matches_the_committed_scope_snapshot() -> None:
    assert manifest.output_path().read_text(encoding="utf-8") == manifest.generate_manifest()


def test_manifest_covers_the_full_corpus_and_reviewed_initial_hire_boundary() -> None:
    rows = manifest.collect_capture_snapshot_rows()
    target_rows = tuple(row for row in rows if row.offered_building_ids)

    assert len(rows) == 320
    assert tuple(row.scenario_path for row in target_rows) == manifest.SCOPED_SCENARIO_PATHS
    assert len(target_rows) == 27
    assert target_rows[-1].scenario_path == "scenarios/wagon_yard_opponent_not_hireable_001.json"
    assert target_rows[0].legal_actions_count == 2
    assert target_rows[0].turn_steps_count == 1


def test_manifest_walk_finds_no_additional_target_hire_window_on_current_main() -> None:
    payload = json.loads(manifest.output_path().read_text(encoding="utf-8"))
    rows = payload["scenarios"]

    assert len(rows) == 320
    assert any(row["reachable_committed_step_scan"]["states_examined"] > 1 for row in rows)
    assert all(
        not row["reachable_committed_step_scan"]["additional_target_hire_windows"] for row in rows
    )


def test_manifest_records_capture_coverage_and_limitations() -> None:
    payload = json.loads(manifest.output_path().read_text(encoding="utf-8"))
    movement = next(
        row
        for row in payload["scenarios"]
        if row["scenario"] == "scenarios/playtest/movement_2p.json"
    )

    assert payload["corpus_scenario_count"] == 320
    assert payload["capture_scenario_counts"] == {"legal_actions": 314, "turn_steps": 320}
    assert movement["capture_files"] == {"legal_actions": None, "turn_steps": "movement_2p.txt"}
    assert any("initial position only" in limitation for limitation in payload["limitations"])
    assert any("exact changed IDs" in limitation for limitation in payload["limitations"])


@pytest.mark.parametrize("capture", manifest.CAPTURE_NAMES)
def test_capture_file_change_helper_accepts_exact_manifest_set(capture: str) -> None:
    manifest.assert_capture_file_changes_match_manifest(
        manifest.expected_capture_files()[capture],
        capture=capture,
    )


def test_capture_file_change_helper_rejects_a_file_outside_manifest() -> None:
    changed = set(manifest.expected_capture_files()[manifest.LEGAL_ACTIONS_CAPTURE])
    changed.add("produce_wheat_001.txt")

    with pytest.raises(AssertionError, match="Unexpected changed files: produce_wheat_001.txt"):
        manifest.assert_capture_file_changes_match_manifest(
            changed,
            capture=manifest.LEGAL_ACTIONS_CAPTURE,
        )


def test_capture_file_change_helper_rejects_a_missing_manifest_file() -> None:
    changed = set(manifest.expected_capture_files()[manifest.TURN_STEPS_CAPTURE])
    changed.remove("bank_hire_market_ordination_001.txt")

    with pytest.raises(
        AssertionError,
        match="Expected files without a change: bank_hire_market_ordination_001.txt",
    ):
        manifest.assert_capture_file_changes_match_manifest(
            changed,
            capture=manifest.TURN_STEPS_CAPTURE,
        )


def test_sow_carried_hire_group_matches_the_reviewed_initial_action_boundary() -> None:
    rows = manifest.collect_sow_carried_hire_snapshot_rows()
    action_counts = {
        building_id: sum(
            option.action_count
            for row in rows
            for option in row.options
            if option.building_id == building_id
        )
        for building_id in manifest.SOW_CARRIED_HIRE_BUILDING_IDS
    }

    assert tuple(row.scenario_path for row in rows) == manifest.SOW_CARRIED_HIRE_SCENARIO_PATHS
    assert len(rows) == 20
    assert action_counts == {
        "infirmary": 90,
        "mill": 20,
        "well": 17,
        "chapel": 2,
        "mint": 1,
        "quarry": 1,
    }


def test_sow_carried_hire_group_records_candidate_index_and_player_labels() -> None:
    rows = manifest.collect_sow_carried_hire_snapshot_rows()
    infirmary = next(
        row
        for row in rows
        if row.scenario_path == "scenarios/allocation_hire_infirmary_market_001.json"
    )
    well = next(
        row for row in rows if row.scenario_path == "scenarios/building_hire_live_market_001.json"
    )

    assert infirmary.options[0].candidate_hire_step_indices == (4,)
    assert infirmary.options[0].hire_option_labels == (
        "Hire Infirmary from market for 1 wheat",
    )
    assert well.options[0].candidate_hire_step_indices == (6,)
    assert well.options[0].hire_option_labels == ("Hire Well from market for 1 wheat",)


def test_sow_carried_hire_group_records_every_frontier_and_its_complete_options() -> None:
    rows = manifest.collect_sow_carried_hire_snapshot_rows()
    infirmary = next(
        row
        for row in rows
        if row.scenario_path == "scenarios/allocation_hire_infirmary_market_001.json"
    )
    well = next(
        row for row in rows if row.scenario_path == "scenarios/building_hire_live_market_001.json"
    )
    deep = next(
        row
        for row in rows
        if row.scenario_path == "scenarios/deep_round_eighteen_seed_seven_two_player_001.json"
    )

    assert infirmary.hire_frontiers[0].hire_kind == "improving"
    assert infirmary.hire_frontiers[0].offers_opt_out
    assert infirmary.hire_frontiers[0].complete_option_labels == (
        "Don't hire",
        "Hire Infirmary from market for 1 wheat",
    )
    assert well.hire_frontiers[0].hire_kind == "enabling"
    assert not well.hire_frontiers[0].offers_opt_out
    assert well.hire_frontiers[0].complete_option_labels == (
        "Hire Well from market for 1 wheat",
    )
    assert len(deep.hire_frontiers) == 7
    assert sum(frontier.hire_kind == "enabling" for frontier in deep.hire_frontiers) == 6
    assert sum(frontier.hire_kind == "improving" for frontier in deep.hire_frontiers) == 1


def test_every_sow_carried_hire_scenario_has_a_complete_turn_without_a_hire() -> None:
    rows = manifest.collect_sow_carried_hire_snapshot_rows()
    scenarios_without_a_non_hire_turn = [
        row.scenario_path for row in rows if row.complete_turn_without_hire_count == 0
    ]

    assert not scenarios_without_a_non_hire_turn, (
        "Sow-carried hire scenarios without a complete turn that hires nothing: "
        f"{scenarios_without_a_non_hire_turn}"
    )


def test_sow_carried_hire_manifest_records_overlap_and_later_reachable_windows() -> None:
    payload = json.loads(manifest.output_path().read_text(encoding="utf-8"))
    group = payload["sow_carried_hire_group"]
    later = {
        row["scenario"]: row["first_later_hire_window"]
        for row in group["later_reachable_scenarios"]
    }
    deep = next(
        row for row in payload["scenarios"] if row["scenario"].startswith("scenarios/deep_")
    )

    assert group["current_initial_affected_scenario_count"] == 20
    assert group["current_initial_action_counts_by_building"] == {
        "chapel": 2,
        "infirmary": 90,
        "mill": 20,
        "mint": 1,
        "quarry": 1,
        "well": 17,
    }
    assert group["current_initial_hire_frontier_counts_by_kind"] == {
        "enabling": 15,
        "improving": 11,
    }
    assert group["current_initial_scenario_counts_by_hire_kind"] == {
        "enabling": 10,
        "improving": 11,
    }
    assert len(group["overlap_with_target_hire_step_group"]) == 3
    assert group["union_with_target_hire_step_group_scenario_count"] == 44
    assert set(later) == {
        "scenarios/deep_round_eighteen_seed_seven_two_player_001.json",
        "scenarios/kogge_donated_no_extra_routes_001.json",
        "scenarios/kogge_hire_opponent_city_to_west_001.json",
        "scenarios/stone_yard_buy_then_construct_001.json",
    }
    assert later["scenarios/stone_yard_buy_then_construct_001.json"][
        "new_since_initial_building_ids"
    ] == ["well", "quarry"]
    assert deep["capture_file_groups"] == {
        "legal_actions": ["target_hire_steps", "sow_carried_hires"],
        "turn_steps": ["target_hire_steps", "sow_carried_hires"],
    }


@pytest.mark.parametrize(
    ("group", "capture", "expected_count"),
    (
        (manifest.SOW_CARRIED_HIRE_GROUP, manifest.LEGAL_ACTIONS_CAPTURE, 20),
        (manifest.SOW_CARRIED_HIRE_GROUP, manifest.TURN_STEPS_CAPTURE, 20),
        (manifest.UNION_HIRE_GROUP, manifest.LEGAL_ACTIONS_CAPTURE, 43),
        (manifest.UNION_HIRE_GROUP, manifest.TURN_STEPS_CAPTURE, 44),
    ),
)
def test_capture_file_change_helper_accepts_each_sow_scope_group(
    group: str,
    capture: str,
    expected_count: int,
) -> None:
    changed = manifest.expected_capture_files(group)[capture]

    assert len(changed) == expected_count
    manifest.assert_capture_file_changes_match_manifest(changed, capture=capture, group=group)


def test_capture_file_change_helper_rejects_target_only_diff_for_the_union_group() -> None:
    target_only = manifest.expected_capture_files(manifest.TARGET_HIRE_STEP_GROUP)[
        manifest.LEGAL_ACTIONS_CAPTURE
    ]

    with pytest.raises(AssertionError, match="Expected files without a change"):
        manifest.assert_capture_file_changes_match_manifest(
            target_only,
            capture=manifest.LEGAL_ACTIONS_CAPTURE,
            group=manifest.UNION_HIRE_GROUP,
        )
