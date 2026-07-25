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

_STATUS_IMPLEMENTED = "implemented"
_STATUS_PARTIAL = "partial"
_STATUS_DEFERRED = "deferred"
_STATUS_BLOCKED_SPATIAL = "blocked_by_roads_spatial"
_STATUS_BLOCKED_SCORING = "blocked_by_final_scoring"
_STATUS_NEEDS_CONFIRMATION = "needs_rule_confirmation"
_STATUS_UNKNOWN = "unknown"

_STATUS_DISPLAY_ORDER: tuple[str, ...] = (
    _STATUS_IMPLEMENTED,
    _STATUS_PARTIAL,
    _STATUS_DEFERRED,
    _STATUS_BLOCKED_SPATIAL,
    _STATUS_BLOCKED_SCORING,
    _STATUS_NEEDS_CONFIRMATION,
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
    total_actions: int
    normal_actions: int
    movement_modifier_actions: int
    grain_store_conversion_actions: int
    hired_building_actions: int
    combined_route_modifier_actions: int
    flag: str


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
    turn_modifier_buildings = {
        entry.building_key for entry in implemented_turn_modifiers()
    }
    duty_enhancement_buildings = {
        entry.source_key
        for entry in implemented_enhancements()
        if entry.source_type == "building"
    }
    catalogue_marked_implemented = {
        str(entry.get("id", ""))
        for entry in load_building_catalogue(root=root)
        if str(entry.get("effect_status", "")).strip().lower() == _STATUS_IMPLEMENTED
    }
    return (
        turn_modifier_buildings
        | duty_enhancement_buildings
        | catalogue_marked_implemented
    )


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


def _is_hired_source_label(source_label: str | None) -> bool:
    return source_label is not None and source_label != "own_active"


def _action_has_hired_component(action: FullTurnAction) -> bool:
    return (
        action.hired_building_id is not None
        or _is_hired_source_label(action.start_turn_building_source)
        or _is_hired_source_label(action.end_turn_building_source)
        or _is_hired_source_label(action.sow_route_building_source)
        or _is_hired_source_label(action.sow_route_secondary_building_source)
        or _is_hired_source_label(action.building_conversion_source)
    )


def _action_is_movement_modifier(action: FullTurnAction) -> bool:
    return (
        action.start_turn_building_id is not None
        or action.sow_route_building_id is not None
        or action.end_turn_building_id is not None
    )


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

        movement_modifier_actions = 0
        conversion_actions = 0
        hired_actions = 0
        combined_route_actions = 0
        normal_actions = 0

        for action in full_turn_actions:
            has_movement_modifier = _action_is_movement_modifier(action)
            has_conversion = action.building_conversion_id == "grain_store"
            has_hired_component = _action_has_hired_component(action)
            has_combined_route = (
                action.sow_route_building_id == "kogge"
                and action.sow_route_secondary_building_id == "cloisters"
            )

            if has_movement_modifier:
                movement_modifier_actions += 1
            if has_conversion:
                conversion_actions += 1
            if has_hired_component:
                hired_actions += 1
            if has_combined_route:
                combined_route_actions += 1
            if not (has_movement_modifier or has_conversion or has_hired_component):
                normal_actions += 1

        rows.append(
            BranchingAuditRow(
                scenario_path=scenario_path,
                total_actions=len(actions),
                normal_actions=normal_actions,
                movement_modifier_actions=movement_modifier_actions,
                grain_store_conversion_actions=conversion_actions,
                hired_building_actions=hired_actions,
                combined_route_modifier_actions=combined_route_actions,
                flag=_branching_flag(len(actions)),
            )
        )

    return tuple(rows)


def _format_building_status_section(rows: tuple[BuildingStatusRow, ...]) -> str:
    lines: list[str] = []
    lines.append("=== Building Status Audit ===")
    lines.append(
        "Metadata note: catalogue effect_status is currently coarse; runtime-derived status is used where available."
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


def _format_recommendations_section() -> str:
    lines = [
        "=== Safe Next Candidates ===",
        "- Buildings that modify already-implemented duty flows (produce, clerical, give_alms, ordination, allocation, construct-building acquisition).",
        "- Buildings that are pure resource/track modifiers and do not require new board-spatial systems.",
        "",
        "Likely Deferred / Higher-Risk Areas",
        "- Effects requiring roads/bridges/shrines/trail spatial runtime.",
        "- Effects requiring final scoring runtime.",
        "- Effects whose canonical rule text still needs confirmation.",
        "",
        "Classification limitation: this audit does not infer blocked-by-spatial or blocked-by-final-scoring per building from machine-readable metadata because those tags are not yet encoded in the catalogue.",
    ]
    return "\n".join(lines)


def _format_branching_section(rows: tuple[BranchingAuditRow, ...]) -> str:
    header = (
        "Scenario                                      Total  Flag      Normal  Movement  GrainStore  Hired  CombinedRoute"
    )
    divider = (
        "---------------------------------------------------------------------------------------------------------------"
    )
    lines = ["=== Branching Count Audit ===", header, divider]
    for row in rows:
        scenario_label = row.scenario_path.split("/")[-1]
        lines.append(
            f"{scenario_label:<44} "
            f"{row.total_actions:>5}  "
            f"{row.flag:<8}  "
            f"{row.normal_actions:>6}  "
            f"{row.movement_modifier_actions:>8}  "
            f"{row.grain_store_conversion_actions:>10}  "
            f"{row.hired_building_actions:>5}  "
            f"{row.combined_route_modifier_actions:>13}"
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
        _format_recommendations_section(),
        _format_branching_section(branching_rows),
    )
    return "\n\n".join(sections).rstrip() + "\n"


def main() -> None:
    print(generate_report(), end="")


if __name__ == "__main__":
    main()
