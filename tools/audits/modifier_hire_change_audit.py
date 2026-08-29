"""Measure what moving modifier hires into full-turn actions would need to preserve.

This is a characterization audit.  It deliberately reads the current engine but does not alter
rules or construct a hypothetical state: the replacement action shapes are an implementation
decision for the later refactor, not something this audit is permitted to guess into existence.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, FullTurnAction, action_id
from pilgrim.rules.transition import apply_turn_step, legal_actions, turn_step_id, turn_steps

OUTPUT_PATH = Path("docs/audits/modifier_hire_change_audit.json")
LEGAL_ACTIONS_CAPTURE = "legal_actions"
TURN_STEPS_CAPTURE = "turn_steps"
CAPTURE_NAMES = (LEGAL_ACTIONS_CAPTURE, TURN_STEPS_CAPTURE)


@dataclass(frozen=True, slots=True)
class ModifierBuilding:
    """The one FullTurnAction field pair that represents this building's effect."""

    building_id: str
    display_name: str
    effect_building_id_field: str
    effect_building_source_field: str
    keeps_free_standalone_hires: bool = False


MODIFIER_BUILDINGS = (
    ModifierBuilding(
        building_id="bank",
        display_name="Bank",
        effect_building_id_field="bank_payment_building_id",
        effect_building_source_field="bank_payment_building_source",
        keeps_free_standalone_hires=True,
    ),
    ModifierBuilding(
        building_id="scriptorium",
        display_name="Scriptorium",
        effect_building_id_field="effective_acolyte_building_id",
        effect_building_source_field="effective_acolyte_building_source",
    ),
    ModifierBuilding(
        building_id="customs_house",
        display_name="Customs House",
        effect_building_id_field="taxation_majority_building_id",
        effect_building_source_field="taxation_majority_building_source",
    ),
)


def project_root() -> Path:
    """Return the checkout root regardless of the command's working directory."""
    return Path(__file__).resolve().parents[2]


def corpus_scenario_paths(root: Path) -> tuple[Path, ...]:
    """Return every checked-in scenario, including playtest positions."""
    return tuple(sorted((root / "scenarios").rglob("*.json")))


def capture_scenario_paths(capture: str, root: Path) -> tuple[Path, ...]:
    """Mirror exactly the initial positions each current capture script writes."""
    scenarios = root / "scenarios"
    if capture == LEGAL_ACTIONS_CAPTURE:
        return tuple(sorted(scenarios.glob("*.json")))
    if capture == TURN_STEPS_CAPTURE:
        return tuple(sorted((*scenarios.glob("*.json"), *(scenarios / "playtest").glob("*.json"))))
    raise ValueError(f"Unknown capture name: {capture!r}")


def _scenario_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _full_turn_actions(state: object, config: object) -> tuple[FullTurnAction, ...]:
    return tuple(
        action
        for action in legal_actions(state, config)
        if isinstance(action, FullTurnAction)
    )


def _hire_steps(
    state: object,
    config: object,
    building: ModifierBuilding,
) -> tuple[BuildingActivationStep, ...]:
    return tuple(
        step
        for step in turn_steps(state, config)
        if isinstance(step, BuildingActivationStep) and step.building_id == building.building_id
    )


def _effect_actions(
    actions: Iterable[FullTurnAction],
    building: ModifierBuilding,
) -> tuple[FullTurnAction, ...]:
    return tuple(
        action
        for action in actions
        if getattr(action, building.effect_building_id_field) == building.building_id
    )


def _source_values(
    actions: Iterable[FullTurnAction],
    building: ModifierBuilding,
) -> list[str | None]:
    """Render all observed values, preserving ``None`` as the committed-step marker."""
    return sorted(
        {getattr(action, building.effect_building_source_field) for action in actions},
        key=lambda value: "" if value is None else str(value),
    )


def _inline_hire_and_use_actions(
    actions: Iterable[FullTurnAction],
    building: ModifierBuilding,
) -> tuple[FullTurnAction, ...]:
    """Find an effect action that names a paid source instead of a prior activation step."""
    return tuple(
        action
        for action in _effect_actions(actions, building)
        if getattr(action, building.effect_building_source_field) not in (None, "own_active")
    )


def _action_ids(actions: Iterable[FullTurnAction]) -> list[str]:
    return sorted(action_id(action) for action in actions)


def _scenario_measurement(
    path: Path,
    root: Path,
    building: ModifierBuilding,
) -> list[dict[str, object]]:
    """Measure every distinct standalone offer for one building in one initial state."""
    scenario = load_scenario(path)
    before_actions = _full_turn_actions(scenario.state, scenario.config)
    before_ids = set(_action_ids(before_actions))
    rows: list[dict[str, object]] = []

    for step in _hire_steps(scenario.state, scenario.config, building):
        after_state = apply_turn_step(scenario.state, scenario.config, step)
        after_actions = _full_turn_actions(after_state, scenario.config)
        effect_actions = _effect_actions(after_actions, building)
        unused_actions = tuple(action for action in after_actions if action not in effect_actions)
        after_ids = set(_action_ids(after_actions))
        only_through_step = after_ids - before_ids
        only_without_step = before_ids - after_ids
        shared = before_ids & after_ids
        effect_ids = set(_action_ids(effect_actions))
        unused_ids = set(_action_ids(unused_actions))
        same_frontier_opt_out_actions = tuple(
            action
            for action in before_actions
            if action not in _effect_actions((action,), building)
        )

        rows.append(
            {
                "scenario": _scenario_name(path, root),
                "standalone_hire_step": {
                    "step_id": turn_step_id(step),
                    "source": step.source,
                    "hire_payment": step.hire_payment,
                },
                "same_frontier_opt_out": {
                    "classification": (
                        "improving" if same_frontier_opt_out_actions else "enabling"
                    ),
                    "full_turn_action_count": len(before_actions),
                    "declining_full_turn_action_count": len(same_frontier_opt_out_actions),
                    "declining_full_turn_action_ids": _action_ids(same_frontier_opt_out_actions),
                },
                "after_committing_standalone_hire": {
                    "full_turn_action_count": len(after_actions),
                    "uses_effect_count": len(effect_actions),
                    "does_not_use_effect_count": len(unused_actions),
                    "effect_source_values": _source_values(effect_actions, building),
                    "uses_effect_action_ids": _action_ids(effect_actions),
                    "does_not_use_effect_action_ids": _action_ids(unused_actions),
                },
                "full_turn_action_outcome_comparison": {
                    "outcome_identity": "FullTurnAction action_id",
                    "without_step_action_count": len(before_ids),
                    "through_step_action_count": len(after_ids),
                    "shared_action_count": len(shared),
                    "only_through_step_action_count": len(only_through_step),
                    "only_without_step_action_count": len(only_without_step),
                    "without_step_action_ids": sorted(before_ids),
                    "through_step_action_ids": sorted(after_ids),
                    "shared_action_ids": sorted(shared),
                    "only_through_step_action_ids": sorted(only_through_step),
                    "only_without_step_action_ids": sorted(only_without_step),
                    "only_through_step_effect_action_ids": sorted(effect_ids & only_through_step),
                    "only_through_step_unused_action_ids": sorted(unused_ids & only_through_step),
                },
            }
        )
    return rows


def _inline_hire_and_use_rows(
    root: Path,
    building: ModifierBuilding,
) -> list[dict[str, object]]:
    """Find direct source-bearing modifier choices across every initial scenario state."""
    rows: list[dict[str, object]] = []
    for path in corpus_scenario_paths(root):
        scenario = load_scenario(path)
        for action in _inline_hire_and_use_actions(
            _full_turn_actions(scenario.state, scenario.config), building
        ):
            rows.append(
                {
                    "scenario": _scenario_name(path, root),
                    "action_id": action_id(action),
                    "effect_source": getattr(action, building.effect_building_source_field),
                    "hire_payment": dict(action.hire_payments).get(building.building_id),
                }
            )
    return rows


def _aggregate_building(
    root: Path,
    building: ModifierBuilding,
) -> tuple[dict[str, object], set[str], set[str], int]:
    """Return one building's manifest payload and its predicted capture-change memberships."""
    rows = [
        row
        for path in corpus_scenario_paths(root)
        for row in _scenario_measurement(path, root, building)
    ]
    inline_rows = _inline_hire_and_use_rows(root, building)
    action_capture_scenarios: set[str] = set()
    turn_step_capture_scenarios: set[str] = set()
    removed_step_count = 0

    for row in rows:
        scenario_name = str(row["scenario"])
        compared = row["full_turn_action_outcome_comparison"]
        after = row["after_committing_standalone_hire"]
        frontier = row["same_frontier_opt_out"]
        assert isinstance(compared, dict)
        assert isinstance(after, dict)
        assert isinstance(frontier, dict)
        retains_free_step = (
            building.keeps_free_standalone_hires
            and row["standalone_hire_step"]["hire_payment"] is None
        )
        if retains_free_step:
            continue
        removed_step_count += 1
        turn_step_capture_scenarios.add(scenario_name)
        if len(compared["only_through_step_effect_action_ids"]) > 0:
            action_capture_scenarios.add(scenario_name)

    classifications = {str(row["same_frontier_opt_out"]["classification"]) for row in rows}
    classification = classifications.pop() if len(classifications) == 1 else "mixed"

    def summed(section: str, key: str) -> int:
        return sum(int(row[section][key]) for row in rows)

    all_effect_actions_only_through_step = all(
        not row["full_turn_action_outcome_comparison"]["only_through_step_unused_action_ids"]
        and row["full_turn_action_outcome_comparison"]["only_through_step_effect_action_ids"]
        == row["full_turn_action_outcome_comparison"]["only_through_step_action_ids"]
        for row in rows
    )

    payload = {
        "building_id": building.building_id,
        "building_name": building.display_name,
        "effect_fields": {
            "building_id_field": building.effect_building_id_field,
            "source_field": building.effect_building_source_field,
            "post_step_source_meaning": (
                "null means the effect was enabled by the separately committed hire step"
            ),
        },
        "standalone_hire_step": {
            "scenario_count": len(rows),
            "step_count": removed_step_count,
            "scenarios": rows,
        },
        "after_committing_totals": {
            "full_turn_action_count": summed(
                "after_committing_standalone_hire", "full_turn_action_count"
            ),
            "uses_effect_count": summed("after_committing_standalone_hire", "uses_effect_count"),
            "does_not_use_effect_count": summed(
                "after_committing_standalone_hire", "does_not_use_effect_count"
            ),
        },
        "inline_hire_and_use": {
            "exists": bool(inline_rows),
            "action_count": len(inline_rows),
            "examples": inline_rows,
            "criterion": (
                "the effect building-id field names this building and its paired source field "
                "is neither null nor own_active in the initial scenario state"
            ),
        },
        "standalone_step_removal_safety": {
            "safe_without_first_adding_inline_actions": not any(
                row["full_turn_action_outcome_comparison"]["only_through_step_action_ids"]
                for row in rows
            ),
            "comparison_basis": "sum of per-scenario FullTurnAction action_id sets",
            "through_step_action_count": summed(
                "full_turn_action_outcome_comparison", "through_step_action_count"
            ),
            "without_step_action_count": summed(
                "full_turn_action_outcome_comparison", "without_step_action_count"
            ),
            "shared_action_count": summed(
                "full_turn_action_outcome_comparison", "shared_action_count"
            ),
            "only_through_step_action_count": summed(
                "full_turn_action_outcome_comparison", "only_through_step_action_count"
            ),
            "only_through_step_effect_action_count": sum(
                len(row["full_turn_action_outcome_comparison"]["only_through_step_effect_action_ids"])
                for row in rows
            ),
            "only_through_step_unused_action_count": sum(
                len(row["full_turn_action_outcome_comparison"]["only_through_step_unused_action_ids"])
                for row in rows
            ),
            "only_without_step_action_count": summed(
                "full_turn_action_outcome_comparison", "only_without_step_action_count"
            ),
            "all_only_through_step_actions_use_the_effect": all_effect_actions_only_through_step,
            "scenarios_with_only_through_step_actions": sorted(action_capture_scenarios),
        },
        "same_frontier_opt_out": {
            "classification": classification,
            "frontier_count": len(rows),
            "opt_out_frontier_count": sum(
                bool(row["same_frontier_opt_out"]["declining_full_turn_action_count"])
                for row in rows
            ),
            "no_opt_out_frontier_count": sum(
                not row["same_frontier_opt_out"]["declining_full_turn_action_count"]
                for row in rows
            ),
            "declining_full_turn_action_count": summed(
                "same_frontier_opt_out", "declining_full_turn_action_count"
            ),
        },
    }
    return payload, action_capture_scenarios, turn_step_capture_scenarios, removed_step_count


def generate_manifest(root: Path | None = None) -> str:
    """Render the deterministic audit manifest without changing game behaviour."""
    base = project_root() if root is None else root
    corpus_paths = corpus_scenario_paths(base)
    captured_paths = {
        capture: capture_scenario_paths(capture, base) for capture in CAPTURE_NAMES
    }
    if set(corpus_paths) != set(captured_paths[TURN_STEPS_CAPTURE]):
        raise AssertionError("The turn-step capture no longer covers the complete scenario corpus.")

    buildings: list[dict[str, object]] = []
    action_capture_scenarios: set[str] = set()
    turn_step_capture_scenarios: set[str] = set()
    removed_step_count = 0
    for building in MODIFIER_BUILDINGS:
        payload, action_members, step_members, building_step_count = _aggregate_building(
            base, building
        )
        buildings.append(payload)
        action_capture_scenarios.update(action_members)
        turn_step_capture_scenarios.update(step_members)
        removed_step_count += building_step_count

    legal_capture_names = {
        _scenario_name(path, base) for path in captured_paths[LEGAL_ACTIONS_CAPTURE]
    }
    turn_step_capture_names = {
        _scenario_name(path, base) for path in captured_paths[TURN_STEPS_CAPTURE]
    }
    if not action_capture_scenarios <= legal_capture_names:
        raise AssertionError("An action-capture impact scenario is not captured by legal_actions.")
    if not turn_step_capture_scenarios <= turn_step_capture_names:
        raise AssertionError("A turn-step impact scenario is not captured by turn_steps.")

    payload = {
        "generated_by": "python3 tools/audits/modifier_hire_change_audit.py",
        "corpus_scenario_count": len(corpus_paths),
        "capture_scenario_counts": {
            capture: len(captured_paths[capture]) for capture in CAPTURE_NAMES
        },
        "method": {
            "standalone_hire_definition": (
                "a currently legal BuildingActivationStep for Bank, Scriptorium, or Customs House"
            ),
            "effect_use_definition": (
                "a FullTurnAction whose named effect building-id field equals the target building; "
                "the paired source field is reported for every post-step use"
            ),
            "outcome_identity": (
                "the stable FullTurnAction action_id saved by tools/capture_legal_actions.py"
            ),
            "same_frontier_opt_out_definition": (
                "at the initial engine choice boundary that offers the standalone step, a direct "
                "FullTurnAction that does not use the target effect is a decline; a frontier with "
                "one is improving, otherwise enabling"
            ),
        },
        "buildings": buildings,
        "predicted_capture_impact_if_inline_hire_and_use_replaces_the_step": {
            "prediction_basis": (
                "current initial-state offers and the effect-use actions visible only after their "
                "standalone step; this is a computed scope, not an observed hypothetical diff"
            ),
            LEGAL_ACTIONS_CAPTURE: {
                "total_capture_file_count": len(legal_capture_names),
                "predicted_changed_file_count": len(action_capture_scenarios),
                "predicted_unchanged_file_count": len(
                    legal_capture_names - action_capture_scenarios
                ),
                "predicted_changed_scenarios": sorted(action_capture_scenarios),
                "rough_change": (
                    "add source-bearing modifier-use FullTurnAction variants for the currently "
                    "post-step-only effect choices; existing non-hire actions remain"
                ),
            },
            TURN_STEPS_CAPTURE: {
                "total_capture_file_count": len(turn_step_capture_names),
                "predicted_changed_file_count": len(turn_step_capture_scenarios),
                "predicted_unchanged_file_count": len(
                    turn_step_capture_names - turn_step_capture_scenarios
                ),
                "predicted_changed_scenarios": sorted(turn_step_capture_scenarios),
                "removed_standalone_activation_step_count": removed_step_count,
                "rough_change": (
                    "remove one paid target BuildingActivationStep per offer; Bank's free Wagon "
                    "Yard step stays"
                ),
            },
        },
        "limitations": [
            "The manifest measures each scenario's initial state, exactly as the two capture "
            "scripts do. It does not walk later turns or action results.",
            "The removal-safety comparison uses FullTurnAction action IDs, not final GameState "
            "equality. A paid standalone hire also leaves an event and resource-payment history, "
            "so its final states are deliberately distinct even where an action ID is shared.",
            "The capture-impact section is a scope prediction for a refactor that adds atomic "
            "hire-and-use variants while removing the steps. It does not claim exact future IDs, "
            "ordering, or line counts; capture diffs must prove those after implementation.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def output_path(root: Path | None = None) -> Path:
    """Return the checked-in manifest path."""
    base = project_root() if root is None else root
    return base / OUTPUT_PATH


def main() -> None:
    """Write the current deterministic measurement."""
    output_path().write_text(generate_manifest(), encoding="utf-8")


if __name__ == "__main__":
    main()
