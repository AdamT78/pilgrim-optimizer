"""Deterministic reporting audit for building status and legal-action branching.

This script is intentionally reporting-only. It does not change game behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import FullTurnAction
from pilgrim.rules.building_turn_modifiers import implemented_turn_modifiers
from pilgrim.rules.duty_enhancements import implemented_enhancements
from pilgrim.rules.transition import legal_actions

if __package__:
    from .audit_helpers import _format_bounded_count, project_root
    from .turn_step_metrics import collect_turn_step_metrics
else:
    from audit_helpers import _format_bounded_count, project_root
    from turn_step_metrics import collect_turn_step_metrics

_STATUS_IMPLEMENTED = "implemented"
_STATUS_PARTIAL = "partial"
_STATUS_DEFERRED = "deferred"
_STATUS_UNKNOWN = "unknown"

_STATUS_DISPLAY_ORDER: tuple[str, ...] = (
    _STATUS_IMPLEMENTED,
    _STATUS_PARTIAL,
    _STATUS_DEFERRED,
    _STATUS_UNKNOWN,
)

_HIGH_BRANCHING_THRESHOLD = 100
_VERY_HIGH_BRANCHING_THRESHOLD = 250

_SCENARIO_LIST: tuple[str, ...] = (
    "scenarios/produce_wheat_001.json",
    "scenarios/kogge_active_city_to_east_001.json",
    "scenarios/cloisters_active_skip_duty_tile_001.json",
    "scenarios/cloisters_active_skip_city_001.json",
    "scenarios/kogge_cloisters_own_own_skip_duty_001.json",
    "scenarios/dormitory_active_return_duty_to_city_001.json",
    "scenarios/inquisition_hire_market_city_to_duty_001.json",
    "scenarios/library_active_city_to_duty_001.json",
    "scenarios/grain_store_active_sell_wheat_001.json",
    "scenarios/grain_store_active_buy_wheat_001.json",
    "scenarios/grain_store_buy_then_ordination_001.json",
    "scenarios/playtest/cloisters_loop_2p.json",
    "scenarios/playtest/cloisters_reach_2p.json",
    "scenarios/playtest/conversions_2p.json",
    "scenarios/playtest/kogge_and_cloisters_2p.json",
    "scenarios/playtest/movement_2p.json",
    "scenarios/deep_round_eighteen_seed_seven_two_player_001.json",
)


@dataclass(frozen=True, slots=True)
class BuildingStatusRow:
    building_id: str
    building_name: str
    status: str
    reason: str


@dataclass(frozen=True, slots=True)
class BranchingAuditRow:
    scenario_path: str
    legal_action_count: int
    turn_step_count: int
    reachable_step_sequences: int
    distinct_reachable_states: int
    action_step_sequence_product: int
    action_distinct_state_product: int
    post_resolution_window_measured: bool
    sequence_walk_truncated: bool
    dropped_step_sequence_prefixes: tuple[tuple[str, ...], ...]
    additional_dropped_step_sequence_prefix_count: int
    hired_turn_steps: int
    conversion_turn_steps: int
    grain_store_conversion_turn_steps: int
    relocation_turn_steps: int
    movement_modifier_actions: int
    combined_route_modifier_actions: int
    flag: str


def configured_scenarios() -> tuple[str, ...]:
    return _SCENARIO_LIST


def load_building_catalogue(root: Path | None = None) -> tuple[dict[str, object], ...]:
    base = project_root() if root is None else root
    payload = json.loads((base / "configs" / "buildings.json").read_text(encoding="utf-8"))
    catalogue = payload.get("catalogue")
    if not isinstance(catalogue, list):
        raise ValueError("configs/buildings.json is missing a valid catalogue list.")
    return tuple(catalogue)


def implemented_building_ids(root: Path | None = None) -> set[str]:
    turn_modifier_buildings = {entry.building_key for entry in implemented_turn_modifiers()}
    duty_enhancement_buildings = {
        entry.source_key for entry in implemented_enhancements() if entry.source_type == "building"
    }
    catalogue_marked_implemented = {
        str(entry.get("id", ""))
        for entry in load_building_catalogue(root=root)
        if str(entry.get("effect_status", "")).strip().lower() == _STATUS_IMPLEMENTED
    }
    return turn_modifier_buildings | duty_enhancement_buildings | catalogue_marked_implemented


def partial_building_ids() -> set[str]:
    # Chapter House runtime currently applies own-active allocation-capacity behavior only.
    return {"chapter_house"}


def collect_building_status_rows(root: Path | None = None) -> tuple[BuildingStatusRow, ...]:
    catalogue = load_building_catalogue(root=root)
    implemented = implemented_building_ids(root=root)
    partial = partial_building_ids()
    rows: list[BuildingStatusRow] = []

    for entry in catalogue:
        building_id = str(entry.get("id", "")).strip()
        if not building_id:
            continue
        building_name = str(entry.get("name", building_id)).strip() or building_id
        effect_status = str(entry.get("effect_status", "deferred")).strip().lower()

        if building_id in partial:
            status = _STATUS_PARTIAL
            reason = (
                "runtime supports own-active behavior; hire-source and full parity wiring "
                "remain deferred"
            )
        elif building_id in implemented:
            status = _STATUS_IMPLEMENTED
            reason = "runtime effect wiring detected via movement/duty enhancement registries"
        elif effect_status == "deferred":
            status = _STATUS_DEFERRED
            reason = "catalogue metadata still deferred and no runtime effect wiring detected"
        elif effect_status == _STATUS_IMPLEMENTED:
            status = _STATUS_IMPLEMENTED
            reason = "catalogue marks implemented"
        else:
            status = _STATUS_UNKNOWN
            reason = f"catalogue has unrecognized effect_status={effect_status!r}"

        rows.append(
            BuildingStatusRow(
                building_id=building_id,
                building_name=building_name,
                status=status,
                reason=reason,
            )
        )

    return tuple(rows)


def _action_is_movement_modifier(action: FullTurnAction) -> bool:
    return action.sow_route_building_id is not None


def _branching_flag(action_count: int) -> str:
    if action_count >= _VERY_HIGH_BRANCHING_THRESHOLD:
        return "VERY HIGH"
    if action_count >= _HIGH_BRANCHING_THRESHOLD:
        return "HIGH"
    return ""


def collect_branching_rows(
    *,
    scenario_paths: tuple[str, ...] | None = None,
    root: Path | None = None,
) -> tuple[BranchingAuditRow, ...]:
    selected_paths = _SCENARIO_LIST if scenario_paths is None else scenario_paths
    base = project_root() if root is None else root
    rows: list[BranchingAuditRow] = []

    for scenario_path in selected_paths:
        scenario_file = base / scenario_path
        if not scenario_file.exists():
            raise FileNotFoundError(f"Missing scenario for branching audit: {scenario_path}")
        scenario = load_scenario(str(scenario_file))
        actions = legal_actions(scenario.state, scenario.config)
        full_turn_actions = [action for action in actions if isinstance(action, FullTurnAction)]
        step_metrics = collect_turn_step_metrics(
            scenario.state,
            scenario.config,
            legal_action_count=len(actions),
        )

        movement_modifier_actions = 0
        combined_route_actions = 0

        for action in full_turn_actions:
            has_movement_modifier = _action_is_movement_modifier(action)
            has_combined_route = (
                action.sow_route_building_id == "kogge"
                and action.sow_route_secondary_building_id == "cloisters"
            )

            if has_movement_modifier:
                movement_modifier_actions += 1
            if has_combined_route:
                combined_route_actions += 1

        rows.append(
            BranchingAuditRow(
                scenario_path=scenario_path,
                legal_action_count=len(actions),
                turn_step_count=step_metrics.total_turn_steps,
                reachable_step_sequences=step_metrics.reachable_step_sequences,
                distinct_reachable_states=step_metrics.distinct_reachable_states,
                action_step_sequence_product=step_metrics.action_step_sequence_product,
                action_distinct_state_product=step_metrics.action_distinct_state_product,
                post_resolution_window_measured=scenario.state.turn_progress.resolution_committed,
                sequence_walk_truncated=step_metrics.sequence_walk_truncated,
                dropped_step_sequence_prefixes=step_metrics.dropped_step_sequence_prefixes,
                additional_dropped_step_sequence_prefix_count=(
                    step_metrics.additional_dropped_step_sequence_prefix_count
                ),
                hired_turn_steps=step_metrics.hired_turn_steps,
                conversion_turn_steps=step_metrics.conversion_turn_steps,
                grain_store_conversion_turn_steps=step_metrics.grain_store_conversion_turn_steps,
                relocation_turn_steps=step_metrics.relocation_turn_steps,
                movement_modifier_actions=movement_modifier_actions,
                combined_route_modifier_actions=combined_route_actions,
                flag=_branching_flag(step_metrics.action_step_sequence_product),
            )
        )

    return tuple(rows)


def _format_building_status_section(rows: tuple[BuildingStatusRow, ...]) -> str:
    lines: list[str] = []
    lines.append("=== Building Status Audit ===")
    lines.append(
        "Metadata note: catalogue effect_status is currently coarse; "
        "runtime-derived status is used where available."
    )
    lines.append("")

    for status in _STATUS_DISPLAY_ORDER:
        group = sorted(
            (row for row in rows if row.status == status),
            key=lambda row: row.building_name.lower(),
        )
        lines.append(f"[{status}] ({len(group)})")
        if not group:
            lines.append("- none")
        else:
            for row in group:
                lines.append(f"- {row.building_name} ({row.building_id}): {row.reason}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_unimplemented_buildings_section(rows: tuple[BuildingStatusRow, ...]) -> str:
    unimplemented = sorted(
        (row for row in rows if row.status == _STATUS_DEFERRED),
        key=lambda row: row.building_name.lower(),
    )
    if not unimplemented:
        return ""
    return "\n".join(
        [
            "=== Unimplemented Buildings ===",
            *(f"- {row.building_name}: {row.reason}" for row in unimplemented),
        ]
    )


def _format_branching_section(rows: tuple[BranchingAuditRow, ...]) -> str:
    scenario_width = max(44, *(len(row.scenario_path.split("/")[-1]) for row in rows))
    header = (
        f"{'Scenario':<{scenario_width}}  Actions  Steps  StepSeq  States  Act×Seq  "
        "Act×State  "
        "PostWindow  Flag      HiredSteps  Conversions  GrainStore  Relocations  "
        "Movement  CombinedRoute"
    )
    divider = "-" * len(header)
    lines = ["=== Branching Count Audit ===", header, divider]
    for row in rows:
        scenario_label = row.scenario_path.split("/")[-1]
        sequence_count = _format_bounded_count(
            row.reachable_step_sequences,
            truncated=row.sequence_walk_truncated,
        )
        state_count = _format_bounded_count(
            row.distinct_reachable_states,
            truncated=row.sequence_walk_truncated,
        )
        action_step_product = _format_bounded_count(
            row.action_step_sequence_product,
            truncated=row.sequence_walk_truncated,
        )
        action_state_product = _format_bounded_count(
            row.action_distinct_state_product,
            truncated=row.sequence_walk_truncated,
        )
        post_window = "MEASURED" if row.post_resolution_window_measured else "UNMEASURED"
        lines.append(
            f"{scenario_label:<{scenario_width}}  "
            f"{row.legal_action_count:>7}  "
            f"{row.turn_step_count:>5}  "
            f"{sequence_count:>7}  "
            f"{state_count:>6}  "
            f"{action_step_product:>7}  "
            f"{action_state_product:>9}  "
            f"{post_window:<10}  "
            f"{row.flag:<8}  "
            f"{row.hired_turn_steps:>10}  "
            f"{row.conversion_turn_steps:>11}  "
            f"{row.grain_store_conversion_turn_steps:>10}  "
            f"{row.relocation_turn_steps:>11}  "
            f"{row.movement_modifier_actions:>8}  "
            f"{row.combined_route_modifier_actions:>13}"
        )
    truncated_rows = [row for row in rows if row.sequence_walk_truncated]
    if truncated_rows:
        lines.extend(
            ["", "Step-sequence/state walk truncations (reported counts are lower bounds):"]
        )
        for row in truncated_rows:
            shown_count = len(row.dropped_step_sequence_prefixes)
            lines.append(
                f"- {row.scenario_path.split('/')[-1]} retained {shown_count} dropped "
                "sequence prefixes:"
            )
            lines.extend(
                f"  - {' -> '.join(prefix)}" for prefix in row.dropped_step_sequence_prefixes
            )
            lines.append(
                "  - additional dropped prefixes not shown: "
                f"{row.additional_dropped_step_sequence_prefix_count}"
            )
    return "\n".join(lines)


def generate_report(
    *,
    root: Path | None = None,
    scenario_paths: tuple[str, ...] | None = None,
) -> str:
    base = project_root() if root is None else root
    building_rows = collect_building_status_rows(root=base)
    branching_rows = collect_branching_rows(
        scenario_paths=scenario_paths,
        root=base,
    )
    sections = (
        _format_building_status_section(building_rows),
        _format_unimplemented_buildings_section(building_rows),
        _format_branching_section(branching_rows),
    )
    return "\n\n".join(section for section in sections if section).rstrip() + "\n"


def main() -> None:
    print(generate_report(), end="")


if __name__ == "__main__":
    main()
