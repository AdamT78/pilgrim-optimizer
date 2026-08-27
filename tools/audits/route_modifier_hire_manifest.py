"""Freeze the capture-file scope for moving route and modifier hires onto sow actions.

The next refactor changes where a paid use is represented.  Its capture diffs are expected, but
only for the scenarios named here.  This audit records the current engine facts and keeps the
review boundary independently checkable.
"""

from __future__ import annotations

import json
import sys
from collections import deque
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import BuildingActivationStep, FullTurnAction
from pilgrim.rules.transition import apply_turn_step, legal_actions, turn_step_id, turn_steps
from tools.play_server import turn_candidates

if __package__:
    from .audit_helpers import project_root
else:
    from audit_helpers import project_root


OUTPUT_PATH = Path("docs/audits/route_modifier_hire_manifest.json")
LEGAL_ACTIONS_CAPTURE = "legal_actions"
TURN_STEPS_CAPTURE = "turn_steps"
CAPTURE_NAMES = (LEGAL_ACTIONS_CAPTURE, TURN_STEPS_CAPTURE)
TARGET_HIRE_STEP_GROUP = "target_hire_steps"
SOW_CARRIED_HIRE_GROUP = "sow_carried_hires"
UNION_HIRE_GROUP = "target_and_sow_carried_hires"
CHANGE_GROUPS = (TARGET_HIRE_STEP_GROUP, SOW_CARRIED_HIRE_GROUP, UNION_HIRE_GROUP)
TARGET_BUILDING_IDS = (
    "kogge",
    "cloisters",
    "bank",
    "scriptorium",
    "customs_house",
    "wagon_yard",
)
SOW_CARRIED_HIRE_BUILDING_IDS = (
    "infirmary",
    "mill",
    "well",
    "chapel",
    "mint",
    "quarry",
)

# This is a deliberately fixed pre-refactor boundary, not a fresh prediction from the changed
# engine.  The next branch must compare its capture diff to this reviewed baseline before it
# updates the current-state portion of the generated manifest.
SCOPED_SCENARIO_PATHS = (
    "scenarios/bank_hire_market_ordination_001.json",
    "scenarios/bank_hire_opponent_ordination_001.json",
    "scenarios/cloisters_hire_market_skip_duty_tile_001.json",
    "scenarios/cloisters_hire_opponent_skip_city_001.json",
    "scenarios/customs_house_hire_market_taxation_majority_001.json",
    "scenarios/customs_house_hire_opponent_taxation_majority_001.json",
    "scenarios/deep_round_eighteen_seed_seven_two_player_001.json",
    "scenarios/kogge_cloisters_hire_both_market_001.json",
    "scenarios/kogge_cloisters_hire_both_opponent_001.json",
    "scenarios/kogge_cloisters_hire_kogge_own_cloisters_001.json",
    "scenarios/kogge_cloisters_insufficient_for_two_hires_001.json",
    "scenarios/kogge_cloisters_own_kogge_hire_cloisters_001.json",
    "scenarios/kogge_donated_no_extra_routes_001.json",
    "scenarios/kogge_hire_market_city_to_east_001.json",
    "scenarios/kogge_hire_opponent_city_to_west_001.json",
    "scenarios/playtest/movement_2p.json",
    "scenarios/scriptorium_hire_market_majority_selected_duty_001.json",
    "scenarios/scriptorium_hire_opponent_majority_selected_duty_001.json",
    "scenarios/stone_yard_buy_then_construct_001.json",
    "scenarios/wagon_yard_active_free_hire_market_bank_ordination_001.json",
    "scenarios/wagon_yard_active_free_hire_market_customs_house_001.json",
    "scenarios/wagon_yard_active_free_hire_market_scriptorium_001.json",
    "scenarios/wagon_yard_active_free_hire_opponent_customs_house_001.json",
    "scenarios/wagon_yard_active_free_hire_opponent_scriptorium_001.json",
    "scenarios/wagon_yard_hire_opponent_free_hire_market_scriptorium_001.json",
    "scenarios/wagon_yard_market_not_hireable_001.json",
    "scenarios/wagon_yard_opponent_not_hireable_001.json",
)

# Like the target scope, this is a reviewed pre-refactor boundary.  It remains fixed while the
# current-state measurements below change, so a sow-hire refactor can compare its captures to the
# scope it was meant to reach.
SOW_CARRIED_HIRE_SCENARIO_PATHS = (
    "scenarios/allocation_hire_infirmary_market_001.json",
    "scenarios/allocation_hire_infirmary_opponent_001.json",
    "scenarios/building_hire_live_market_001.json",
    "scenarios/building_hire_opponent_owned_001.json",
    "scenarios/clerical_devotion_hire_chapel_market_001.json",
    "scenarios/clerical_devotion_vestry_hire_chapel_market_001.json",
    "scenarios/clerical_silversmith_hire_mint_market_001.json",
    "scenarios/deep_round_eighteen_seed_seven_two_player_001.json",
    "scenarios/give_alms_hire_mill_market_wheat3_001.json",
    "scenarios/give_alms_hire_mill_opponent_wheat3_001.json",
    "scenarios/kogge_donated_no_extra_routes_001.json",
    "scenarios/kogge_hire_opponent_city_to_west_001.json",
    "scenarios/ordination_hire_infirmary_market_extra_step_001.json",
    "scenarios/ordination_hire_infirmary_opponent_extra_step_001.json",
    "scenarios/ordination_hire_mill_market_three_steps_001.json",
    "scenarios/ordination_hire_mill_opponent_three_steps_001.json",
    "scenarios/produce_stone_hire_quarry_market_001.json",
    "scenarios/produce_wheat_fields_hire_well_market_001.json",
    "scenarios/produce_wheat_hire_well_market_001.json",
    "scenarios/produce_wheat_hire_well_opponent_001.json",
)


@dataclass(frozen=True, slots=True)
class CaptureSnapshotRow:
    """The one initial position that the two capture tools write for a scenario."""

    scenario_path: str
    captured_by: tuple[str, ...]
    offered_building_ids: tuple[str, ...]
    offered_hire_step_count: int
    legal_actions_count: int
    turn_steps_count: int


@dataclass(frozen=True, slots=True)
class ReachableHireWindow:
    """A target building first offered after a sequence of committed steps."""

    step_ids: tuple[str, ...]
    offered_building_ids: tuple[str, ...]
    offered_hire_step_count: int
    legal_actions_count: int
    turn_steps_count: int


@dataclass(frozen=True, slots=True)
class ReachabilityRow:
    """The exhaustive pre-resolution committed-step traversal for one scenario."""

    scenario_path: str
    states_examined: int
    additional_hire_windows: tuple[ReachableHireWindow, ...]


@dataclass(frozen=True, slots=True)
class SowCarriedHireOption:
    """One building's action-carried hire variants and their player-facing question."""

    building_id: str
    action_count: int
    candidate_hire_step_indices: tuple[int, ...]
    hire_option_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SowCarriedHireFrontier:
    """One player-visible hire question, including whether that question can be declined."""

    candidate_hire_step_index: int
    candidate_step_prefix: tuple[str, ...]
    hired_building_ids: tuple[str, ...]
    hire_option_labels: tuple[str, ...]
    complete_option_labels: tuple[str, ...]
    offers_opt_out: bool

    @property
    def hire_kind(self) -> str:
        """Name the current question shape without claiming a rule beyond the offered choices."""
        return "improving" if self.offers_opt_out else "enabling"


@dataclass(frozen=True, slots=True)
class SowCarriedHireSnapshotRow:
    """The action-carried hires present in one initial capture position."""

    scenario_path: str
    captured_by: tuple[str, ...]
    legal_actions_count: int
    turn_steps_count: int
    complete_turn_action_count: int
    complete_turn_without_hire_count: int
    options: tuple[SowCarriedHireOption, ...]
    hire_frontiers: tuple[SowCarriedHireFrontier, ...]

    @property
    def action_count(self) -> int:
        return sum(option.action_count for option in self.options)


@dataclass(frozen=True, slots=True)
class SowCarriedHireWindow:
    """The first later committed-step state that offers an action-carried hire."""

    step_ids: tuple[str, ...]
    new_building_ids: tuple[str, ...]
    legal_actions_count: int
    turn_steps_count: int
    options: tuple[SowCarriedHireOption, ...]
    hire_frontiers: tuple[SowCarriedHireFrontier, ...]


@dataclass(frozen=True, slots=True)
class SowCarriedReachabilityRow:
    """Whether action-carried hires survive or appear after committed steps."""

    scenario_path: str
    states_examined: int
    first_later_hire_window: SowCarriedHireWindow | None


def corpus_scenario_paths(root: Path | None = None) -> tuple[Path, ...]:
    """Return the complete checked-in corpus, including playtest positions."""
    base = project_root() if root is None else root
    return tuple(sorted((base / "scenarios").rglob("*.json")))


def capture_scenario_paths(capture: str, root: Path | None = None) -> tuple[Path, ...]:
    """Mirror exactly the scenario paths written by one current capture script."""
    base = project_root() if root is None else root
    scenarios = base / "scenarios"
    if capture == LEGAL_ACTIONS_CAPTURE:
        return tuple(sorted(scenarios.glob("*.json")))
    if capture == TURN_STEPS_CAPTURE:
        return tuple(sorted((*scenarios.glob("*.json"), *(scenarios / "playtest").glob("*.json"))))
    raise ValueError(f"Unknown capture name: {capture!r}")


def _scenario_name(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _target_hire_steps(state: object, config: object) -> tuple[BuildingActivationStep, ...]:
    return tuple(
        step
        for step in turn_steps(state, config)
        if isinstance(step, BuildingActivationStep) and step.building_id in TARGET_BUILDING_IDS
    )


def _target_building_ids(steps: Collection[BuildingActivationStep]) -> tuple[str, ...]:
    offered = {step.building_id for step in steps}
    return tuple(building_id for building_id in TARGET_BUILDING_IDS if building_id in offered)


def _sow_carried_hire_actions(
    state: object,
    config: object,
    *,
    actions: Collection[object] | None = None,
) -> tuple[FullTurnAction, ...]:
    current_actions = legal_actions(state, config) if actions is None else actions
    return tuple(
        action
        for action in current_actions
        if isinstance(action, FullTurnAction)
        and action.hired_building_id in SOW_CARRIED_HIRE_BUILDING_IDS
    )


def _candidate_step_prefix(steps: list[dict[str, object]]) -> tuple[str, ...]:
    """Give each repeated hire question a stable, readable identity in the manifest."""
    return tuple(
        f"{step['kind']}={json.dumps(step['value'], sort_keys=True)}" for step in steps
    )


def _sow_carried_hire_details(
    state: object,
    config: object,
    actions: Collection[object],
) -> tuple[tuple[SowCarriedHireOption, ...], tuple[SowCarriedHireFrontier, ...]]:
    """Read action-carried hire questions and all answers at each visible frontier."""
    hired_actions = _sow_carried_hire_actions(state, config, actions=actions)
    values_to_buildings = {
        f"{action.hired_building_id}:{action.hired_building_source or 'unknown'}": (
            action.hired_building_id
        )
        for action in hired_actions
        if action.hired_building_id is not None
    }
    counts = {
        building_id: sum(action.hired_building_id == building_id for action in hired_actions)
        for building_id in SOW_CARRIED_HIRE_BUILDING_IDS
    }
    indices_by_building: dict[str, set[int]] = {}
    labels_by_building: dict[str, set[str]] = {}
    frontier_options: dict[tuple[int, tuple[str, ...]], dict[str, str]] = {}

    for candidate in turn_candidates(
        state,
        config,
        actions=list(actions),
        include_preview_effects=False,
    ):
        for index, step in enumerate(candidate["steps"]):
            if step["kind"] != "hire":
                continue
            label = step.get("label")
            if not isinstance(label, str):
                raise AssertionError(f"Sow-carried hire candidate lacks a label: {step!r}")
            key = (index, _candidate_step_prefix(candidate["steps"][:index]))
            frontier_options.setdefault(key, {})[str(step["value"])] = label

    hire_frontiers: list[SowCarriedHireFrontier] = []
    for (index, prefix), options in sorted(frontier_options.items()):
        building_ids = tuple(
            building_id
            for building_id in SOW_CARRIED_HIRE_BUILDING_IDS
            if building_id in {values_to_buildings.get(value) for value in options}
        )
        if not building_ids:
            continue
        hire_labels = tuple(
            sorted(label for value, label in options.items() if value in values_to_buildings)
        )
        for building_id in building_ids:
            indices_by_building.setdefault(building_id, set()).add(index)
            labels_by_building.setdefault(building_id, set()).update(hire_labels)
        hire_frontiers.append(
            SowCarriedHireFrontier(
                candidate_hire_step_index=index,
                candidate_step_prefix=prefix,
                hired_building_ids=building_ids,
                hire_option_labels=hire_labels,
                complete_option_labels=tuple(sorted(options.values())),
                offers_opt_out="none" in options,
            )
        )

    offered_buildings = {action.hired_building_id for action in hired_actions}
    if offered_buildings != set(indices_by_building):
        raise AssertionError(
            "Every action-carried hire must have a matching candidate hire step: "
            f"actions={sorted(offered_buildings)}, candidates={sorted(indices_by_building)}."
        )
    hire_options = tuple(
        SowCarriedHireOption(
            building_id=building_id,
            action_count=counts[building_id],
            candidate_hire_step_indices=tuple(sorted(indices_by_building[building_id])),
            hire_option_labels=tuple(sorted(labels_by_building[building_id])),
        )
        for building_id in SOW_CARRIED_HIRE_BUILDING_IDS
        if building_id in offered_buildings
    )
    return hire_options, tuple(hire_frontiers)


def collect_capture_snapshot_rows(root: Path | None = None) -> tuple[CaptureSnapshotRow, ...]:
    """Measure each initial capture position, rather than inferring availability from JSON."""
    base = project_root() if root is None else root
    captured_paths = {
        capture: set(capture_scenario_paths(capture, root=base)) for capture in CAPTURE_NAMES
    }
    rows: list[CaptureSnapshotRow] = []

    for path in corpus_scenario_paths(root=base):
        scenario = load_scenario(path)
        offered_steps = _target_hire_steps(scenario.state, scenario.config)
        rows.append(
            CaptureSnapshotRow(
                scenario_path=_scenario_name(path, base),
                captured_by=tuple(
                    capture for capture in CAPTURE_NAMES if path in captured_paths[capture]
                ),
                offered_building_ids=_target_building_ids(offered_steps),
                offered_hire_step_count=len(offered_steps),
                legal_actions_count=len(legal_actions(scenario.state, scenario.config)),
                turn_steps_count=len(turn_steps(scenario.state, scenario.config)),
            )
        )
    return tuple(rows)


def collect_sow_carried_hire_snapshot_rows(
    root: Path | None = None,
) -> tuple[SowCarriedHireSnapshotRow, ...]:
    """Measure every initial position whose legal action carries one of the six hires."""
    base = project_root() if root is None else root
    captured_paths = {
        capture: set(capture_scenario_paths(capture, root=base)) for capture in CAPTURE_NAMES
    }
    rows: list[SowCarriedHireSnapshotRow] = []

    for path in corpus_scenario_paths(root=base):
        scenario = load_scenario(path)
        actions = legal_actions(scenario.state, scenario.config)
        hired_actions = _sow_carried_hire_actions(
            scenario.state,
            scenario.config,
            actions=actions,
        )
        if not hired_actions:
            continue
        options, hire_frontiers = _sow_carried_hire_details(
            scenario.state,
            scenario.config,
            actions,
        )
        complete_turn_actions = tuple(
            action for action in actions if isinstance(action, FullTurnAction)
        )
        rows.append(
            SowCarriedHireSnapshotRow(
                scenario_path=_scenario_name(path, base),
                captured_by=tuple(
                    capture for capture in CAPTURE_NAMES if path in captured_paths[capture]
                ),
                legal_actions_count=len(actions),
                turn_steps_count=len(turn_steps(scenario.state, scenario.config)),
                complete_turn_action_count=len(complete_turn_actions),
                complete_turn_without_hire_count=sum(
                    action.hired_building_id is None for action in complete_turn_actions
                ),
                options=options,
                hire_frontiers=hire_frontiers,
            )
        )
    return tuple(rows)


def _walk_committed_turn_step_states(
    state: object,
    config: object,
) -> Iterator[tuple[object, tuple[str, ...]]]:
    """Visit every distinct state reachable before choosing a full-turn action.

    The walk is deliberately uncapped.  A cap would turn an undiscovered hire window into an
    undocumented hole in the next branch's capture-diff assertion.
    """
    pending: deque[tuple[object, tuple[str, ...]]] = deque(((state, ()),))
    visited: set[object] = set()

    while pending:
        current, step_ids = pending.popleft()
        if current in visited:
            continue
        visited.add(current)
        yield current, step_ids
        for step in turn_steps(current, config):
            next_state = apply_turn_step(current, config, step)
            if next_state not in visited:
                pending.append((next_state, (*step_ids, turn_step_id(step))))


def collect_reachability_rows(root: Path | None = None) -> tuple[ReachabilityRow, ...]:
    """Find target hire buildings that become legal only after another committed step."""
    base = project_root() if root is None else root
    rows: list[ReachabilityRow] = []

    for path in corpus_scenario_paths(root=base):
        scenario = load_scenario(path)
        initial_steps = _target_hire_steps(scenario.state, scenario.config)
        initial_buildings = set(_target_building_ids(initial_steps))
        states_examined = 0
        windows_by_buildings: dict[tuple[str, ...], ReachableHireWindow] = {}

        for state, step_ids in _walk_committed_turn_step_states(scenario.state, scenario.config):
            states_examined += 1
            if not step_ids:
                continue
            offered_steps = _target_hire_steps(state, scenario.config)
            new_buildings = tuple(
                building_id
                for building_id in _target_building_ids(offered_steps)
                if building_id not in initial_buildings
            )
            if not new_buildings or new_buildings in windows_by_buildings:
                continue
            windows_by_buildings[new_buildings] = ReachableHireWindow(
                step_ids=step_ids,
                offered_building_ids=new_buildings,
                offered_hire_step_count=sum(
                    step.building_id in new_buildings for step in offered_steps
                ),
                legal_actions_count=len(legal_actions(state, scenario.config)),
                turn_steps_count=len(turn_steps(state, scenario.config)),
            )

        rows.append(
            ReachabilityRow(
                scenario_path=_scenario_name(path, base),
                states_examined=states_examined,
                additional_hire_windows=tuple(windows_by_buildings.values()),
            )
        )
    return tuple(rows)


def collect_sow_carried_hire_reachability_rows(
    root: Path | None = None,
) -> tuple[SowCarriedReachabilityRow, ...]:
    """Find action-carried hires that remain or emerge after committed steps."""
    base = project_root() if root is None else root
    rows: list[SowCarriedReachabilityRow] = []

    for path in corpus_scenario_paths(root=base):
        scenario = load_scenario(path)
        initial_actions = _sow_carried_hire_actions(scenario.state, scenario.config)
        initial_buildings = {action.hired_building_id for action in initial_actions}
        states_examined = 0
        first_later_hire_window: SowCarriedHireWindow | None = None

        for state, step_ids in _walk_committed_turn_step_states(scenario.state, scenario.config):
            states_examined += 1
            if not step_ids or first_later_hire_window is not None:
                continue
            actions = legal_actions(state, scenario.config)
            hired_actions = _sow_carried_hire_actions(state, scenario.config, actions=actions)
            if not hired_actions:
                continue
            options, hire_frontiers = _sow_carried_hire_details(state, scenario.config, actions)
            offered_buildings = {option.building_id for option in options}
            first_later_hire_window = SowCarriedHireWindow(
                step_ids=step_ids,
                new_building_ids=tuple(
                    building_id
                    for building_id in SOW_CARRIED_HIRE_BUILDING_IDS
                    if building_id in offered_buildings and building_id not in initial_buildings
                ),
                legal_actions_count=len(actions),
                turn_steps_count=len(turn_steps(state, scenario.config)),
                options=options,
                hire_frontiers=hire_frontiers,
            )

        rows.append(
            SowCarriedReachabilityRow(
                scenario_path=_scenario_name(path, base),
                states_examined=states_examined,
                first_later_hire_window=first_later_hire_window,
            )
        )
    return tuple(rows)


def scoped_scenario_paths(group: str) -> tuple[str, ...]:
    """Return one reviewed pre-refactor scope, or the union a broader change must reach."""
    if group == TARGET_HIRE_STEP_GROUP:
        return SCOPED_SCENARIO_PATHS
    if group == SOW_CARRIED_HIRE_GROUP:
        return SOW_CARRIED_HIRE_SCENARIO_PATHS
    if group == UNION_HIRE_GROUP:
        return tuple(sorted({*SCOPED_SCENARIO_PATHS, *SOW_CARRIED_HIRE_SCENARIO_PATHS}))
    raise ValueError(f"Unknown capture change group: {group!r}")


def expected_capture_files(
    group: str = TARGET_HIRE_STEP_GROUP,
) -> dict[str, frozenset[str]]:
    """The reviewed capture-file boundary that one next behavior branch must hit exactly."""
    files = {
        capture: frozenset(
            f"{Path(scenario_path).stem}.txt"
            for scenario_path in scoped_scenario_paths(group)
            if capture != LEGAL_ACTIONS_CAPTURE or Path(scenario_path).parent.name != "playtest"
        )
        for capture in CAPTURE_NAMES
    }
    return files


def _capture_file_groups(scenario_path: str, captured_by: Collection[str]) -> dict[str, list[str]]:
    groups = tuple(
        group
        for group in (TARGET_HIRE_STEP_GROUP, SOW_CARRIED_HIRE_GROUP)
        if scenario_path in scoped_scenario_paths(group)
    )
    return {
        capture: list(groups) if capture in captured_by else [] for capture in CAPTURE_NAMES
    }


def _row_payload(row: CaptureSnapshotRow, reachability: ReachabilityRow) -> dict[str, object]:
    return {
        "scenario": row.scenario_path,
        "capture_files": {
            capture: f"{Path(row.scenario_path).stem}.txt" if capture in row.captured_by else None
            for capture in CAPTURE_NAMES
        },
        "capture_file_groups": _capture_file_groups(row.scenario_path, row.captured_by),
        "capture_snapshot": {
            "offers_target_hire_step": bool(row.offered_building_ids),
            "target_hire_step_building_ids": list(row.offered_building_ids),
            "target_hire_step_count": row.offered_hire_step_count,
            "legal_actions_count": row.legal_actions_count,
            "turn_steps_count": row.turn_steps_count,
        },
        "reachable_committed_step_scan": {
            "states_examined": reachability.states_examined,
            "additional_target_hire_windows": [
                {
                    "after_turn_step_ids": list(window.step_ids),
                    "target_hire_step_building_ids": list(window.offered_building_ids),
                    "target_hire_step_count": window.offered_hire_step_count,
                    "legal_actions_count": window.legal_actions_count,
                    "turn_steps_count": window.turn_steps_count,
                }
                for window in reachability.additional_hire_windows
            ],
        },
    }


def _sow_option_payload(option: SowCarriedHireOption) -> dict[str, object]:
    return {
        "building_id": option.building_id,
        "action_count": option.action_count,
        "candidate_hire_step_indices": list(option.candidate_hire_step_indices),
        "hire_option_labels": list(option.hire_option_labels),
    }


def _sow_hire_frontier_payload(frontier: SowCarriedHireFrontier) -> dict[str, object]:
    return {
        "candidate_hire_step_index": frontier.candidate_hire_step_index,
        "candidate_step_prefix": list(frontier.candidate_step_prefix),
        "hire_kind": frontier.hire_kind,
        "hired_building_ids": list(frontier.hired_building_ids),
        "hire_option_labels": list(frontier.hire_option_labels),
        "complete_option_labels": list(frontier.complete_option_labels),
        "offers_opt_out": frontier.offers_opt_out,
    }


def _sow_window_payload(window: SowCarriedHireWindow) -> dict[str, object]:
    return {
        "after_turn_step_ids": list(window.step_ids),
        "new_since_initial_building_ids": list(window.new_building_ids),
        "legal_actions_count": window.legal_actions_count,
        "turn_steps_count": window.turn_steps_count,
        "options": [_sow_option_payload(option) for option in window.options],
        "hire_frontiers": [
            _sow_hire_frontier_payload(frontier) for frontier in window.hire_frontiers
        ],
    }


def _sow_snapshot_payload(
    row: SowCarriedHireSnapshotRow,
    reachability: SowCarriedReachabilityRow,
) -> dict[str, object]:
    return {
        "scenario": row.scenario_path,
        "capture_files": {
            capture: f"{Path(row.scenario_path).stem}.txt" if capture in row.captured_by else None
            for capture in CAPTURE_NAMES
        },
        "capture_file_groups": _capture_file_groups(row.scenario_path, row.captured_by),
        "capture_snapshot": {
            "sow_carried_hire_action_count": row.action_count,
            "sow_carried_hire_building_ids": [option.building_id for option in row.options],
            "legal_actions_count": row.legal_actions_count,
            "turn_steps_count": row.turn_steps_count,
            "complete_turn_action_count": row.complete_turn_action_count,
            "complete_turn_without_hire_count": row.complete_turn_without_hire_count,
            # Python sequence indices are zero-based: the ordinary fifth question is index four.
            "candidate_hire_step_index_basis": "zero-based",
            "options": [_sow_option_payload(option) for option in row.options],
            "hire_frontiers": [
                _sow_hire_frontier_payload(frontier) for frontier in row.hire_frontiers
            ],
            "distinct_hire_option_labels": sorted(
                {label for option in row.options for label in option.hire_option_labels}
            ),
            "distinct_hire_frontier_option_labels": sorted(
                {
                    label
                    for frontier in row.hire_frontiers
                    for label in frontier.complete_option_labels
                }
            ),
        },
        "reachable_committed_step_scan": {
            "states_examined": reachability.states_examined,
            "first_later_hire_window": (
                _sow_window_payload(reachability.first_later_hire_window)
                if reachability.first_later_hire_window is not None
                else None
            ),
        },
    }


def generate_manifest(root: Path | None = None) -> str:
    """Render the committed, reviewable scope boundary as deterministic JSON."""
    base = project_root() if root is None else root
    snapshots = collect_capture_snapshot_rows(root=base)
    reachability_rows = collect_reachability_rows(root=base)
    reachability_by_path = {row.scenario_path: row for row in reachability_rows}
    sow_snapshots = collect_sow_carried_hire_snapshot_rows(root=base)
    sow_reachability_rows = collect_sow_carried_hire_reachability_rows(root=base)
    sow_reachability_by_path = {row.scenario_path: row for row in sow_reachability_rows}
    scoped_snapshot_paths = {
        row.scenario_path for row in snapshots if row.offered_building_ids
    }
    sow_scoped_snapshot_paths = {row.scenario_path for row in sow_snapshots}
    sow_action_counts = {
        building_id: sum(
            option.action_count
            for row in sow_snapshots
            for option in row.options
            if option.building_id == building_id
        )
        for building_id in SOW_CARRIED_HIRE_BUILDING_IDS
    }
    sow_hire_frontiers = tuple(
        frontier for row in sow_snapshots for frontier in row.hire_frontiers
    )
    sow_hire_frontier_counts = {
        hire_kind: sum(frontier.hire_kind == hire_kind for frontier in sow_hire_frontiers)
        for hire_kind in ("enabling", "improving")
    }
    sow_hire_scenario_counts = {
        hire_kind: sum(
            any(frontier.hire_kind == hire_kind for frontier in row.hire_frontiers)
            for row in sow_snapshots
        )
        for hire_kind in ("enabling", "improving")
    }
    overlapping_scenarios = tuple(
        sorted(set(SCOPED_SCENARIO_PATHS) & set(SOW_CARRIED_HIRE_SCENARIO_PATHS))
    )
    later_sow_rows = tuple(
        row for row in sow_reachability_rows if row.first_later_hire_window is not None
    )
    payload = {
        "generated_by": "python3 tools/audits/route_modifier_hire_manifest.py",
        "target_building_ids": list(TARGET_BUILDING_IDS),
        "corpus_scenario_count": len(snapshots),
        "capture_scenario_counts": {
            capture: len(capture_scenario_paths(capture, root=base)) for capture in CAPTURE_NAMES
        },
        "scope": {
            "baseline_affected_scenario_count": len(SCOPED_SCENARIO_PATHS),
            "current_capture_snapshot_affected_scenario_count": len(scoped_snapshot_paths),
            "current_capture_snapshot_matches_reviewed_baseline": (
                scoped_snapshot_paths == set(SCOPED_SCENARIO_PATHS)
            ),
            "expected_changed_capture_files": {
                capture: sorted(expected_capture_files(TARGET_HIRE_STEP_GROUP)[capture])
                for capture in CAPTURE_NAMES
            },
        },
        "sow_carried_hire_group": {
            "building_ids": list(SOW_CARRIED_HIRE_BUILDING_IDS),
            "candidate_hire_step_index_basis": "zero-based",
            "hire_frontier_kind_basis": (
                "enabling has no same-frontier opt-out; improving offers one"
            ),
            "baseline_initial_affected_scenario_count": len(SOW_CARRIED_HIRE_SCENARIO_PATHS),
            "current_initial_affected_scenario_count": len(sow_scoped_snapshot_paths),
            "current_initial_snapshot_matches_reviewed_baseline": (
                sow_scoped_snapshot_paths == set(SOW_CARRIED_HIRE_SCENARIO_PATHS)
            ),
            "current_initial_action_counts_by_building": sow_action_counts,
            "current_initial_hire_frontier_counts_by_kind": sow_hire_frontier_counts,
            "current_initial_scenario_counts_by_hire_kind": sow_hire_scenario_counts,
            "overlap_with_target_hire_step_group": list(overlapping_scenarios),
            "union_with_target_hire_step_group_scenario_count": len(
                set(SCOPED_SCENARIO_PATHS) | set(SOW_CARRIED_HIRE_SCENARIO_PATHS)
            ),
            "expected_changed_capture_files": {
                capture: sorted(expected_capture_files(SOW_CARRIED_HIRE_GROUP)[capture])
                for capture in CAPTURE_NAMES
            },
            "expected_changed_capture_files_for_union": {
                capture: sorted(expected_capture_files(UNION_HIRE_GROUP)[capture])
                for capture in CAPTURE_NAMES
            },
            "initial_capture_scenarios": [
                _sow_snapshot_payload(row, sow_reachability_by_path[row.scenario_path])
                for row in sow_snapshots
            ],
            "later_reachable_scenarios": [
                {
                    "scenario": row.scenario_path,
                    "states_examined": row.states_examined,
                    "first_later_hire_window": _sow_window_payload(
                        row.first_later_hire_window
                    ),
                }
                for row in later_sow_rows
                if row.first_later_hire_window is not None
            ],
        },
        "limitations": [
            "tools/capture_legal_actions.py writes only top-level scenarios, while "
            "tools/capture_turn_steps.py also writes scenarios/playtest. Both write each "
            "scenario's initial position only; their output does not include later states.",
            "This audit exhaustively walks currently legal committed turn steps before a full "
            "action. It does not walk action results or later turns. Today those results have a "
            "committed resolution and cannot offer these pre-resolution hires; revisit this "
            "boundary if their timing changes.",
            "expected_changed_capture_files checks file membership only. It does not assert the "
            "exact changed IDs, their order, or the size of either diff; the capture diffs remain "
            "the evidence for those properties.",
            "Reachability merges equal game states and records the first path for a newly "
            "offered building set. It does not claim that all step orderings are equivalent.",
            "The sow-carried group records each player-visible hire frontier's current prefix, "
            "complete labels, and same-frontier opt-out shape. Its capture-file assertion still "
            "checks membership only, not an exact candidate sequence or label diff.",
        ],
        "scenarios": [
            _row_payload(row, reachability_by_path[row.scenario_path]) for row in snapshots
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def output_path(root: Path | None = None) -> Path:
    base = project_root() if root is None else root
    return base / OUTPUT_PATH


def load_committed_manifest(root: Path | None = None) -> dict[str, object]:
    """Read the checked-in baseline rather than recomputing it after a behavior change."""
    payload = json.loads(output_path(root=root).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Route/modifier hire manifest must be a JSON object.")
    return payload


def manifest_expected_capture_files(
    capture: str,
    *,
    group: str = TARGET_HIRE_STEP_GROUP,
    root: Path | None = None,
) -> frozenset[str]:
    """Return one frozen expected file set from the committed scope manifest."""
    if capture not in CAPTURE_NAMES:
        raise ValueError(f"Unknown capture name: {capture!r}")
    if group not in CHANGE_GROUPS:
        raise ValueError(f"Unknown capture change group: {group!r}")
    payload = load_committed_manifest(root=root)
    try:
        if group == TARGET_HIRE_STEP_GROUP:
            scope = payload["scope"]
            assert isinstance(scope, dict)
            changed_files = scope["expected_changed_capture_files"]
        else:
            sow_group = payload["sow_carried_hire_group"]
            assert isinstance(sow_group, dict)
            key = (
                "expected_changed_capture_files"
                if group == SOW_CARRIED_HIRE_GROUP
                else "expected_changed_capture_files_for_union"
            )
            changed_files = sow_group[key]
        assert isinstance(changed_files, dict)
        files = changed_files[capture]
    except (AssertionError, KeyError) as exc:
        raise ValueError("Route/modifier hire manifest is missing expected capture files.") from exc
    if not isinstance(files, list) or not all(isinstance(file, str) for file in files):
        raise ValueError("Route/modifier hire manifest has invalid expected capture files.")
    return frozenset(files)


def assert_capture_file_changes_match_manifest(
    changed_files: Collection[str | Path],
    *,
    capture: str,
    group: str = TARGET_HIRE_STEP_GROUP,
    root: Path | None = None,
) -> None:
    """Fail if a capture diff misses or exceeds one named scope group or their union."""
    actual = frozenset(Path(file).name for file in changed_files)
    expected = manifest_expected_capture_files(capture, group=group, root=root)
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unexpected or missing:
        details: list[str] = [
            f"{capture} capture files did not match the reviewed {group} manifest group."
        ]
        if unexpected:
            details.append(f"Unexpected changed files: {', '.join(unexpected)}.")
        if missing:
            details.append(f"Expected files without a change: {', '.join(missing)}.")
        raise AssertionError(" ".join(details))


def main() -> None:
    output_path().write_text(generate_manifest(), encoding="utf-8")


if __name__ == "__main__":
    main()
