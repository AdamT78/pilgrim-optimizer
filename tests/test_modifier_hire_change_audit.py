from __future__ import annotations

import json

from tools.audits import modifier_hire_change_audit as audit


def test_manifest_matches_the_committed_modifier_hire_measurement() -> None:
    assert audit.output_path().read_text(encoding="utf-8") == audit.generate_manifest()


def test_manifest_records_the_reviewed_modifier_hire_scope() -> None:
    payload = json.loads(audit.output_path().read_text(encoding="utf-8"))
    buildings = {building["building_id"]: building for building in payload["buildings"]}
    capture_impact = payload["predicted_capture_impact_if_inline_hire_and_use_replaces_the_step"]
    actual = {
        "corpus_scenario_count": payload["corpus_scenario_count"],
        "capture_scenario_counts": payload["capture_scenario_counts"],
        "buildings": {
            building_id: {
                "standalone_step_scenarios": building["standalone_hire_step"]["scenario_count"],
                "after_commit": building["after_committing_totals"],
                "inline_hire_and_use_exists": building["inline_hire_and_use"]["exists"],
                "removal_safe": building["standalone_step_removal_safety"][
                    "safe_without_first_adding_inline_actions"
                ],
                "only_through_effect_actions": building["standalone_step_removal_safety"][
                    "only_through_step_effect_action_count"
                ],
                "frontiers": building["same_frontier_opt_out"],
            }
            for building_id, building in buildings.items()
        },
        "capture_impact": {
            "legal_actions": capture_impact["legal_actions"]["predicted_changed_file_count"],
            "turn_steps": capture_impact["turn_steps"]["predicted_changed_file_count"],
            "removed_steps": capture_impact["turn_steps"][
                "removed_standalone_activation_step_count"
            ],
        },
    }

    assert actual == {
        "corpus_scenario_count": 320,
        "capture_scenario_counts": {"legal_actions": 314, "turn_steps": 320},
        "buildings": {
            "bank": {
                "standalone_step_scenarios": 6,
                "after_commit": {
                    "full_turn_action_count": 34,
                    "uses_effect_count": 9,
                    "does_not_use_effect_count": 25,
                },
                "inline_hire_and_use_exists": False,
                "removal_safe": False,
                "only_through_effect_actions": 9,
                "frontiers": {
                    "classification": "improving",
                    "frontier_count": 6,
                    "opt_out_frontier_count": 6,
                    "no_opt_out_frontier_count": 0,
                    "declining_full_turn_action_count": 71,
                },
            },
            "scriptorium": {
                "standalone_step_scenarios": 5,
                "after_commit": {
                    "full_turn_action_count": 25,
                    "uses_effect_count": 10,
                    "does_not_use_effect_count": 15,
                },
                "inline_hire_and_use_exists": False,
                "removal_safe": False,
                "only_through_effect_actions": 10,
                "frontiers": {
                    "classification": "improving",
                    "frontier_count": 5,
                    "opt_out_frontier_count": 5,
                    "no_opt_out_frontier_count": 0,
                    "declining_full_turn_action_count": 15,
                },
            },
            "customs_house": {
                "standalone_step_scenarios": 7,
                "after_commit": {
                    "full_turn_action_count": 114,
                    "uses_effect_count": 36,
                    "does_not_use_effect_count": 78,
                },
                "inline_hire_and_use_exists": False,
                "removal_safe": False,
                "only_through_effect_actions": 36,
                "frontiers": {
                    "classification": "improving",
                    "frontier_count": 7,
                    "opt_out_frontier_count": 7,
                    "no_opt_out_frontier_count": 0,
                    "declining_full_turn_action_count": 126,
                },
            },
        },
        "capture_impact": {"legal_actions": 12, "turn_steps": 15, "removed_steps": 18},
    }
