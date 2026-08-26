"""Deterministic reporting audit for branching over scripted multi-turn traces.

This script is reporting-only and does not modify gameplay behavior.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from pilgrim.io.scenarios import LoadedScenario, load_scenario
from pilgrim.model.actions import (
    BuildingActivationStep,
    BuildingConversionStep,
    BuildingRelocationStep,
    EndTurnAction,
    FullTurnAction,
    GameAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    TurnStep,
    action_id,
    action_summary,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.state import GameState
from pilgrim.rules.transition import (
    apply_action,
    apply_turn_step,
    legal_actions,
    turn_step_id,
    turn_steps,
)
from pilgrim.setup.generator import generate_setup_scenario

if __package__:
    from .audit_helpers import _format_bounded_count, project_root
    from .turn_step_metrics import collect_turn_step_metrics
else:
    from audit_helpers import _format_bounded_count, project_root
    from turn_step_metrics import collect_turn_step_metrics

_TRACE_ORDER: tuple[str, ...] = (
    "basic_2p_round_flow",
    "movement_hotspot_2p",
    "grain_store_2p",
    "generated_setup_3p",
    "generated_setup_4p",
)
_CONFIG_PATH_FIELDS: tuple[str, ...] = (
    "board_file",
    "duties_file",
    "piety_file",
    "alms_file",
    "timing_file",
    "merchant_file",
    "ship_file",
    "buildings_file",
)

ActionSelector = Callable[[tuple[GameAction, ...], GameConfig, int], GameAction]
TurnStepSelector = Callable[[tuple[TurnStep, ...], GameConfig, int, str], TurnStep]
TraceLoader = Callable[[Path], LoadedScenario]


@dataclass(frozen=True, slots=True)
class TraceDefinition:
    name: str
    description: str
    steps: int
    loader: TraceLoader
    selector: ActionSelector
    turn_step_selector: TurnStepSelector


@dataclass(frozen=True, slots=True)
class TraceTurnStepCommit:
    """One deterministic trace commit and the complete stable offer set before it."""

    window: str
    offered_step_ids: tuple[str, ...]
    selected_step_id: str
    selected_step_summary: str


@dataclass(frozen=True, slots=True)
class TraceStepRow:
    trace_name: str
    step: int
    absolute_turn: int
    round_number: int
    season_number: int
    turn_in_round: int
    active_player: str
    legal_action_count: int
    turn_step_count: int
    reachable_step_sequences: int
    distinct_reachable_states: int
    action_step_sequence_product: int
    action_distinct_state_product: int
    sequence_walk_truncated: bool
    dropped_step_sequence_prefixes: tuple[tuple[str, ...], ...]
    additional_dropped_step_sequence_prefix_count: int
    unique_action_id_count: int
    duplicate_action_id_count: int
    hired_turn_steps: int
    conversion_turn_steps: int
    grain_store_conversion_turn_steps: int
    relocation_turn_steps: int
    setup_sow_actions: int
    full_turn_actions: int
    distinct_sow_origins: int
    distinct_routes: int
    distinct_actual_routes: int
    distinct_selected_duties: int
    distinct_duty_actions: int
    max_picked_up_acolytes: int
    avg_picked_up_acolytes: float
    max_route_length: int
    avg_route_length: float
    actions_with_route_modifier: int
    actions_with_kogge: int
    actions_with_cloisters: int
    actions_with_kogge_cloisters_combined: int
    pre_action_step_commits: tuple[TraceTurnStepCommit, ...]
    post_resolution_step_commits: tuple[TraceTurnStepCommit, ...]
    selected_action_id: str
    selected_action_summary: str


@dataclass(frozen=True, slots=True)
class TraceResult:
    definition: TraceDefinition
    rows: tuple[TraceStepRow, ...]


def configured_trace_names() -> tuple[str, ...]:
    return _TRACE_ORDER


def action_hired_building_count(action: FullTurnAction) -> int:
    count = 0
    if action.hired_building_id is not None:
        count += 1
    if _is_hired_source(action.sow_route_building_source):
        count += 1
    if _is_hired_source(action.sow_route_secondary_building_source):
        count += 1
    if _is_hired_source(action.building_conversion_source):
        count += 1
    return count


def action_has_hire(action: FullTurnAction) -> bool:
    return action_hired_building_count(action) > 0


def action_has_route_modifier(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id is not None
        or action.sow_route_secondary_building_id is not None
        or action.sow_route_omitted_location is not None
    )


def action_has_kogge(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id == "kogge" or action.sow_route_secondary_building_id == "kogge"
    )


def action_has_cloisters(action: FullTurnAction) -> bool:
    return (
        action.sow_route_building_id == "cloisters"
        or action.sow_route_secondary_building_id == "cloisters"
    )


def action_has_combined_kogge_cloisters(action: FullTurnAction) -> bool:
    present = {
        building_id
        for building_id in (
            action.sow_route_building_id,
            action.sow_route_secondary_building_id,
        )
        if building_id is not None
    }
    return present == {"kogge", "cloisters"}


def action_has_start_turn_modifier(action: FullTurnAction) -> bool:
    return False


def action_has_end_turn_modifier(action: FullTurnAction) -> bool:
    return False


def action_has_grain_store_conversion(action: FullTurnAction) -> bool:
    return action.building_conversion_id == "grain_store"


def action_has_building_conversion(action: FullTurnAction) -> bool:
    return action.building_conversion_id is not None


def trace_definitions() -> tuple[TraceDefinition, ...]:
    return (
        TraceDefinition(
            name="basic_2p_round_flow",
            description="Baseline 2p round flow over six turns.",
            steps=6,
            loader=_load_basic_2p_round_flow,
            selector=_select_preferred_safe_action,
            turn_step_selector=_select_lowest_turn_step,
        ),
        TraceDefinition(
            name="movement_hotspot_2p",
            description="2p branching hotspot with Kogge+Cloisters route modifiers.",
            steps=6,
            loader=_load_movement_hotspot_2p,
            selector=_select_movement_hotspot_action,
            turn_step_selector=_select_lowest_turn_step,
        ),
        TraceDefinition(
            name="grain_store_2p",
            description=(
                "2p Grain Store conversion branching over six turns; the first pre-action "
                "commit requires a Grain Store step."
            ),
            steps=6,
            loader=_load_grain_store_2p,
            selector=_select_preferred_safe_action,
            turn_step_selector=_select_grain_store_action,
        ),
        TraceDefinition(
            name="generated_setup_3p",
            description="Generated setup probe for 3-player turn-order/branching.",
            steps=4,
            loader=lambda root: _load_generated_setup(root, player_count=3, seed=3),
            selector=_select_preferred_safe_action,
            turn_step_selector=_select_lowest_turn_step,
        ),
        TraceDefinition(
            name="generated_setup_4p",
            description="Generated setup probe for 4-player turn-order/branching.",
            steps=5,
            loader=lambda root: _load_generated_setup(root, player_count=4, seed=4),
            selector=_select_preferred_safe_action,
            turn_step_selector=_select_lowest_turn_step,
        ),
    )


def collect_trace_results(
    *,
    root: Path | None = None,
    trace_names: tuple[str, ...] | None = None,
) -> tuple[TraceResult, ...]:
    base = project_root() if root is None else root
    definitions_by_name = {definition.name: definition for definition in trace_definitions()}
    selected_names = _TRACE_ORDER if trace_names is None else trace_names
    results: list[TraceResult] = []

    for name in selected_names:
        definition = definitions_by_name.get(name)
        if definition is None:
            known = ", ".join(sorted(definitions_by_name))
            raise ValueError(f"Unknown trace name: {name}. Known traces: {known}.")
        loaded = definition.loader(base)
        rows = _run_trace_rows(
            trace_name=definition.name,
            state=loaded.state,
            config=loaded.config,
            steps=definition.steps,
            selector=definition.selector,
            turn_step_selector=definition.turn_step_selector,
        )
        results.append(TraceResult(definition=definition, rows=rows))

    return tuple(results)


def generate_report(
    *,
    root: Path | None = None,
    trace_names: tuple[str, ...] | None = None,
) -> str:
    results = collect_trace_results(root=root, trace_names=trace_names)
    lines: list[str] = ["Multi-Turn Branching Audit", ""]
    for result in results:
        lines.extend(_format_trace_result(result))
        lines.append("")
    lines.extend(_format_overall_summary(results))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    print(generate_report(), end="")


def _run_trace_rows(
    *,
    trace_name: str,
    state: GameState,
    config: GameConfig,
    steps: int,
    selector: ActionSelector,
    turn_step_selector: TurnStepSelector,
) -> tuple[TraceStepRow, ...]:
    rows: list[TraceStepRow] = []
    current_state = state
    pending_post_resolution_step_commits: tuple[TraceTurnStepCommit, ...] = ()
    for step in range(1, steps + 1):
        # A game opens, and every round ends, by stopping on whoever holds the First Player marker.
        # Answered and stepped over rather than measured: a row counts how a TURN branches --
        # routes, duties, what to do with them -- and a position whose only question is who begins
        # has none of that. The holder keeps it, so the trace walks a fixed seating rather than a
        # wandering one. Confession Box questions are stepped over with the answer that changes
        # nothing for the same reason.
        #
        # End Turn remains a separate timing checkpoint rather than a trace row, but it is not
        # assumed to be branch-free: post-resolution steps are committed and recorded before the
        # trace passes it. This keeps the audit honest about Library and conversions that remain
        # available after resolution.
        while True:
            if current_state.turn_progress.resolution_committed:
                current_state, initial_window_commits = _commit_available_turn_steps(
                    current_state,
                    config,
                    trace_step=step,
                    selector=turn_step_selector,
                    window="post-resolution",
                )
                pending_post_resolution_step_commits = (
                    *pending_post_resolution_step_commits,
                    *initial_window_commits,
                )
                window_actions = legal_actions(current_state, config)
                end_turn_action = next(
                    (action for action in window_actions if isinstance(action, EndTurnAction)),
                    None,
                )
                if end_turn_action is None:
                    raise ValueError(
                        "End-turn window offered no EndTurnAction at "
                        f"trace={trace_name} step={step}: {window_actions!r}"
                    )
                current_state = apply_action(current_state, end_turn_action, config).state
                continue
            if current_state.phase not in (
                TurnPhase.START_PLAYER_CONFESSION,
                TurnPhase.START_PLAYER_SELECTION,
            ):
                break
            answer: GameAction = (
                StartPlayerConfessionBoxAction(use=False)
                if current_state.phase is TurnPhase.START_PLAYER_CONFESSION
                else StartPlayerSelectionAction(chosen_start_player=current_state.active_player)
            )
            current_state = apply_action(current_state, answer, config).state
        actions_before_steps = legal_actions(current_state, config)
        if not actions_before_steps:
            break
        step_metrics = collect_turn_step_metrics(
            current_state,
            config,
            legal_action_count=len(actions_before_steps),
        )
        pre_action_state = current_state
        current_state, pre_action_step_commits = _commit_available_turn_steps(
            current_state,
            config,
            trace_step=step,
            selector=turn_step_selector,
            window="pre-action",
        )
        actions = legal_actions(current_state, config)
        if not actions:
            raise ValueError(f"No legal action after turn steps at trace={trace_name} step={step}.")
        action_ids = tuple(action_id(action) for action in actions_before_steps)
        selected_action = selector(actions, config, step)
        selected_id = action_id(selected_action)
        selectable_ids = {action_id(action) for action in actions}
        if selected_id not in selectable_ids:
            raise ValueError(
                "Selector returned non-legal action at "
                f"trace={trace_name} step={step}: {selected_id}"
            )

        setup_sow_actions = [
            action for action in actions_before_steps if isinstance(action, SetupSowAction)
        ]
        full_turn_actions = [
            action for action in actions_before_steps if isinstance(action, FullTurnAction)
        ]
        route_lengths = [len(action.route) for action in full_turn_actions]
        picked_up_counts = list(route_lengths)
        distinct_routes = {action.route for action in full_turn_actions}
        distinct_actual_routes = {
            _actual_route_for_branching_metrics(action) for action in full_turn_actions
        }
        action_result = apply_action(current_state, selected_action, config)
        current_state = action_result.state
        post_resolution_step_commits: tuple[TraceTurnStepCommit, ...] = (
            pending_post_resolution_step_commits
        )
        pending_post_resolution_step_commits = ()
        if current_state.turn_progress.resolution_committed:
            current_state, current_window_commits = _commit_available_turn_steps(
                current_state,
                config,
                trace_step=step,
                selector=turn_step_selector,
                window="post-resolution",
            )
            post_resolution_step_commits = (
                *post_resolution_step_commits,
                *current_window_commits,
            )
            window_actions = legal_actions(current_state, config)
            end_turn_action = next(
                (action for action in window_actions if isinstance(action, EndTurnAction)),
                None,
            )
            if end_turn_action is None:
                raise ValueError(
                    "End-turn window offered no EndTurnAction at "
                    f"trace={trace_name} step={step}: {window_actions!r}"
                )
            current_state = apply_action(current_state, end_turn_action, config).state

        row = TraceStepRow(
            trace_name=trace_name,
            step=step,
            absolute_turn=pre_action_state.timing.absolute_turn,
            round_number=pre_action_state.timing.round_number,
            season_number=pre_action_state.timing.season_number,
            turn_in_round=pre_action_state.timing.turn_in_round,
            active_player=pre_action_state.active_player.name.lower(),
            legal_action_count=len(actions_before_steps),
            turn_step_count=step_metrics.total_turn_steps,
            reachable_step_sequences=step_metrics.reachable_step_sequences,
            distinct_reachable_states=step_metrics.distinct_reachable_states,
            action_step_sequence_product=step_metrics.action_step_sequence_product,
            action_distinct_state_product=step_metrics.action_distinct_state_product,
            sequence_walk_truncated=step_metrics.sequence_walk_truncated,
            dropped_step_sequence_prefixes=step_metrics.dropped_step_sequence_prefixes,
            additional_dropped_step_sequence_prefix_count=(
                step_metrics.additional_dropped_step_sequence_prefix_count
            ),
            unique_action_id_count=len(set(action_ids)),
            duplicate_action_id_count=len(action_ids) - len(set(action_ids)),
            hired_turn_steps=step_metrics.hired_turn_steps,
            conversion_turn_steps=step_metrics.conversion_turn_steps,
            grain_store_conversion_turn_steps=step_metrics.grain_store_conversion_turn_steps,
            relocation_turn_steps=step_metrics.relocation_turn_steps,
            setup_sow_actions=len(setup_sow_actions),
            full_turn_actions=len(full_turn_actions),
            distinct_sow_origins=len({action.origin for action in full_turn_actions}),
            distinct_routes=len(distinct_routes),
            distinct_actual_routes=len(distinct_actual_routes),
            distinct_selected_duties=len({action.selected_duty for action in full_turn_actions}),
            distinct_duty_actions=len({action.resolution.value for action in full_turn_actions}),
            max_picked_up_acolytes=max(picked_up_counts) if picked_up_counts else 0,
            avg_picked_up_acolytes=(
                sum(picked_up_counts) / len(picked_up_counts) if picked_up_counts else 0.0
            ),
            max_route_length=max(route_lengths) if route_lengths else 0,
            avg_route_length=(sum(route_lengths) / len(route_lengths) if route_lengths else 0.0),
            actions_with_route_modifier=_count_matching(
                full_turn_actions, action_has_route_modifier
            ),
            actions_with_kogge=_count_matching(full_turn_actions, action_has_kogge),
            actions_with_cloisters=_count_matching(full_turn_actions, action_has_cloisters),
            actions_with_kogge_cloisters_combined=_count_matching(
                full_turn_actions,
                action_has_combined_kogge_cloisters,
            ),
            pre_action_step_commits=pre_action_step_commits,
            post_resolution_step_commits=post_resolution_step_commits,
            selected_action_id=selected_id,
            selected_action_summary=action_summary(selected_action, config),
        )
        rows.append(row)
    return tuple(rows)


def _commit_available_turn_steps(
    state: GameState,
    config: GameConfig,
    *,
    trace_step: int,
    selector: TurnStepSelector,
    window: str,
) -> tuple[GameState, tuple[TraceTurnStepCommit, ...]]:
    """Commit one deterministic choice at every offered step decision in a trace window."""
    commits: list[TraceTurnStepCommit] = []
    current_state = state
    while offered_steps := tuple(sorted(turn_steps(current_state, config), key=turn_step_id)):
        selected_step = selector(offered_steps, config, trace_step, window)
        offered_ids = tuple(turn_step_id(candidate) for candidate in offered_steps)
        selected_step_id = turn_step_id(selected_step)
        if selected_step_id not in set(offered_ids):
            raise ValueError(
                "Turn-step selector returned a non-offered step at "
                f"step={trace_step} window={window}: {selected_step_id}"
            )
        commits.append(
            TraceTurnStepCommit(
                window=window,
                offered_step_ids=offered_ids,
                selected_step_id=selected_step_id,
                selected_step_summary=_turn_step_summary(selected_step, config),
            )
        )
        current_state = apply_turn_step(current_state, config, selected_step)
    return current_state, tuple(commits)


def _turn_step_summary(step: TurnStep, config: GameConfig) -> str:
    if isinstance(step, BuildingConversionStep):
        return action_summary(step, config)
    if isinstance(step, BuildingActivationStep):
        summary = f"use building: {step.building_id}"
    elif isinstance(step, BuildingRelocationStep):
        summary = (
            f"use building: {step.building_id} to relocate one acolyte "
            f"to {step.selected_position}"
        )
    else:
        raise TypeError(f"Unsupported turn step type: {type(step)!r}")
    if step.source != "own_active":
        summary += f" | hire building: {step.building_id} from {step.source}"
    return summary


def _count_matching(
    actions: Iterable[FullTurnAction],
    predicate: Callable[[FullTurnAction], bool],
) -> int:
    return sum(1 for action in actions if predicate(action))


def _actual_route_for_branching_metrics(action: FullTurnAction) -> tuple[int, ...]:
    """
    Return actual route approximation used for base-branching metrics.

    Current action model stores one route tuple on `FullTurnAction`. There is no separate
    candidate-vs-actual route field, so this helper returns that tuple directly.
    """
    return action.route


def _format_trace_result(result: TraceResult) -> list[str]:
    lines = [
        f"Trace: {result.definition.name}",
        f"Description: {result.definition.description}",
        "Branching totals:",
        (
            "Step  AbsTurn  Round  Season  TIR  Player       Legal  Steps  StepSeq  States  "
            "Act×Seq  "
            "Act×State  "
            "Unique  Dups  HireSt  ConvSt  GrainSt  RelocSt  RouteMod  Kogge  Cloisters  K+C"
        ),
        (
            "----  -------  -----  ------  ---  -----------  -----  -----  -------  ------  "
            "-------  "
            "---------  "
            "------  ----  ------  ------  -------  -------  --------  -----  ---------  ---"
        ),
    ]
    for row in result.rows:
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
        lines.append(
            f"{row.step:>4}  "
            f"{row.absolute_turn:>7}  "
            f"{row.round_number:>5}  "
            f"{row.season_number:>6}  "
            f"{row.turn_in_round:>3}  "
            f"{row.active_player:<11}  "
            f"{row.legal_action_count:>5}  "
            f"{row.turn_step_count:>5}  "
            f"{sequence_count:>7}  "
            f"{state_count:>6}  "
            f"{action_step_product:>7}  "
            f"{action_state_product:>9}  "
            f"{row.unique_action_id_count:>6}  "
            f"{row.duplicate_action_id_count:>4}  "
            f"{row.hired_turn_steps:>6}  "
            f"{row.conversion_turn_steps:>6}  "
            f"{row.grain_store_conversion_turn_steps:>7}  "
            f"{row.relocation_turn_steps:>7}  "
            f"{row.actions_with_route_modifier:>8}  "
            f"{row.actions_with_kogge:>5}  "
            f"{row.actions_with_cloisters:>9}  "
            f"{row.actions_with_kogge_cloisters_combined:>3}"
        )
    lines.extend(
        [
            "Base sow/action breakdown:",
            (
                "Step  SetupSow  FullTurn  Origins  Routes  ActualRoutes  Duties  DutyActions  "
                "MaxPickup  AvgPickup  MaxRoute  AvgRoute"
            ),
            (
                "----  --------  --------  -------  ------  ------------  ------  -----------  "
                "---------  ---------  --------  --------"
            ),
        ]
    )
    for row in result.rows:
        lines.append(
            f"{row.step:>4}  "
            f"{row.setup_sow_actions:>8}  "
            f"{row.full_turn_actions:>8}  "
            f"{row.distinct_sow_origins:>7}  "
            f"{row.distinct_routes:>6}  "
            f"{row.distinct_actual_routes:>12}  "
            f"{row.distinct_selected_duties:>6}  "
            f"{row.distinct_duty_actions:>11}  "
            f"{row.max_picked_up_acolytes:>9}  "
            f"{row.avg_picked_up_acolytes:>9.2f}  "
            f"{row.max_route_length:>8}  "
            f"{row.avg_route_length:>8.2f}"
        )
    lines.append("Selected actions:")
    for row in result.rows:
        lines.append(f"- step {row.step}: {row.selected_action_id}")
        lines.append(f"  {row.selected_action_summary}")
    lines.extend(_format_turn_step_commits(result.rows))
    lines.extend(_format_step_sequence_truncations(result.rows))
    lines.extend(_format_trace_summary(result.rows))
    return lines


def _format_turn_step_commits(rows: tuple[TraceStepRow, ...]) -> list[str]:
    commits = [
        (row, commit)
        for row in rows
        for commit in (*row.pre_action_step_commits, *row.post_resolution_step_commits)
    ]
    if not commits:
        return ["Committed turn steps:", "- none"]

    lines = ["Committed turn steps:"]
    for row, commit in commits:
        lines.append(f"- step {row.step} ({commit.window}):")
        lines.append(f"  offered: {', '.join(commit.offered_step_ids)}")
        lines.append(f"  selected: {commit.selected_step_id}")
        lines.append(f"  {commit.selected_step_summary}")
    return lines


def _format_step_sequence_truncations(rows: tuple[TraceStepRow, ...]) -> list[str]:
    truncated_rows = [row for row in rows if row.sequence_walk_truncated]
    if not truncated_rows:
        return []

    lines = ["Step-sequence/state walk truncations (reported counts are lower bounds):"]
    for row in truncated_rows:
        shown_count = len(row.dropped_step_sequence_prefixes)
        lines.append(f"- step {row.step} retained {shown_count} dropped sequence prefixes:")
        lines.extend(
            f"  - {' -> '.join(prefix)}" for prefix in row.dropped_step_sequence_prefixes
        )
        lines.append(
            "  - additional dropped prefixes not shown: "
            f"{row.additional_dropped_step_sequence_prefix_count}"
        )
    return lines


def _format_trace_summary(rows: tuple[TraceStepRow, ...]) -> list[str]:
    if not rows:
        return ["Summary:", "- no steps executed"]
    max_legal = max(rows, key=lambda row: row.legal_action_count)
    max_turn_steps = max(rows, key=lambda row: row.turn_step_count)
    max_step_sequences = max(rows, key=lambda row: row.reachable_step_sequences)
    max_distinct_states = max(rows, key=lambda row: row.distinct_reachable_states)
    max_action_step_product = max(rows, key=lambda row: row.action_step_sequence_product)
    max_action_state_product = max(rows, key=lambda row: row.action_distinct_state_product)
    max_dups = max(rows, key=lambda row: row.duplicate_action_id_count)
    max_hired = max(rows, key=lambda row: row.hired_turn_steps)
    max_combined = max(rows, key=lambda row: row.actions_with_kogge_cloisters_combined)
    max_grain_store = max(rows, key=lambda row: row.grain_store_conversion_turn_steps)
    max_routes = max(rows, key=lambda row: row.distinct_routes)
    max_duties = max(rows, key=lambda row: row.distinct_selected_duties)
    max_pickup = max(rows, key=lambda row: row.max_picked_up_acolytes)
    max_sequence_count = _format_bounded_count(
        max_step_sequences.reachable_step_sequences,
        truncated=max_step_sequences.sequence_walk_truncated,
    )
    max_action_step_count = _format_bounded_count(
        max_action_step_product.action_step_sequence_product,
        truncated=max_action_step_product.sequence_walk_truncated,
    )
    max_distinct_state_count = _format_bounded_count(
        max_distinct_states.distinct_reachable_states,
        truncated=max_distinct_states.sequence_walk_truncated,
    )
    max_action_state_count = _format_bounded_count(
        max_action_state_product.action_distinct_state_product,
        truncated=max_action_state_product.sequence_walk_truncated,
    )
    likely_driver = _likely_branching_driver(max_action_step_product)
    return [
        "Summary:",
        f"- max legal actions: {max_legal.legal_action_count} at step {max_legal.step}",
        f"- max offered turn steps: {max_turn_steps.turn_step_count} at step {max_turn_steps.step}",
        (
            "- max reachable step sequences: "
            f"{max_sequence_count} "
            f"at step {max_step_sequences.step}"
        ),
        (
            "- max action×step-sequence branches: "
            f"{max_action_step_count} "
            f"at step {max_action_step_product.step}"
        ),
        (
            "- max distinct reachable states: "
            f"{max_distinct_state_count} "
            f"at step {max_distinct_states.step}"
        ),
        (
            "- max action×distinct-state branches: "
            f"{max_action_state_count} "
            f"at step {max_action_state_product.step}"
        ),
        f"- max duplicate action IDs: {max_dups.duplicate_action_id_count} at step {max_dups.step}",
        f"- max hired turn steps: {max_hired.hired_turn_steps} at step {max_hired.step}",
        (
            "- max combined Kogge+Cloisters actions: "
            f"{max_combined.actions_with_kogge_cloisters_combined} at step {max_combined.step}"
        ),
        (
            "- max Grain Store conversion turn steps: "
            f"{max_grain_store.grain_store_conversion_turn_steps} at step {max_grain_store.step}"
        ),
        "Base branching summary:",
        f"- max distinct routes: {max_routes.distinct_routes} at step {max_routes.step}",
        (
            "- max distinct selected duties: "
            f"{max_duties.distinct_selected_duties} at step {max_duties.step}"
        ),
        (
            "- max picked-up acolytes: "
            f"{max_pickup.max_picked_up_acolytes} at step {max_pickup.step}"
        ),
        (
            "- likely driver at max action×step-sequence step "
            f"{max_action_step_product.step}: {likely_driver}"
        ),
    ]


def _likely_branching_driver(row: TraceStepRow) -> str:
    if row.action_step_sequence_product > row.legal_action_count:
        return "committed turn-step branching"
    if row.actions_with_kogge_cloisters_combined > 0:
        return "combined route modifiers"
    if (
        row.legal_action_count >= 100
        and row.actions_with_route_modifier == 0
    ):
        return "base sow/duty expansion"
    if row.actions_with_route_modifier > 0:
        return "route modifiers"
    return "mixed / low"


def _format_overall_summary(results: tuple[TraceResult, ...]) -> list[str]:
    all_rows = [row for result in results for row in result.rows]
    if not all_rows:
        return ["Overall summary:", "- no traces executed"]
    duplicate_total = sum(row.duplicate_action_id_count for row in all_rows)
    committed_steps = sum(
        len(row.pre_action_step_commits) + len(row.post_resolution_step_commits)
        for row in all_rows
    )
    return [
        "Overall summary:",
        f"- traces executed: {len(results)}",
        f"- total steps executed: {len(all_rows)}",
        f"- total deterministic turn steps committed: {committed_steps}",
        f"- total duplicate action IDs observed: {duplicate_total}",
    ]

def _select_preferred_safe_action(
    actions: tuple[GameAction, ...],
    _config: GameConfig,
    _step: int,
) -> GameAction:
    full_turn_actions = [action for action in actions if isinstance(action, FullTurnAction)]
    tithe_actions = [
        action for action in full_turn_actions if action.resolution is TurnResolutionType.TITHE
    ]
    if tithe_actions:
        return min(tithe_actions, key=action_id)

    for resolution in (
        TurnResolutionType.PRODUCE_WHEAT,
        TurnResolutionType.PRODUCE_STONE,
        TurnResolutionType.ALLOCATION,
    ):
        by_resolution = [action for action in full_turn_actions if action.resolution is resolution]
        if by_resolution:
            return min(by_resolution, key=action_id)

    return min(actions, key=action_id)


def _select_movement_hotspot_action(
    actions: tuple[GameAction, ...],
    config: GameConfig,
    step: int,
) -> GameAction:
    full_turn_actions = [action for action in actions if isinstance(action, FullTurnAction)]
    if step == 1:
        route_actions = [
            action for action in full_turn_actions if action_has_route_modifier(action)
        ]
        if route_actions:
            return min(route_actions, key=action_id)
    return _select_preferred_safe_action(actions, config, step)


def _select_grain_store_action(
    steps: tuple[TurnStep, ...],
    _config: GameConfig,
    step: int,
    window: str,
) -> TurnStep:
    """Require the Grain Store probe to commit a Grain Store step before its first action."""
    if step == 1 and window == "pre-action":
        grain_store_steps = [
            candidate
            for candidate in steps
            if isinstance(candidate, BuildingConversionStep)
            and candidate.building_id == "grain_store"
        ]
        if not grain_store_steps:
            raise ValueError(
                "Grain Store trace offered no Grain Store conversion step before its first action."
            )
        return min(grain_store_steps, key=turn_step_id)
    return _select_lowest_turn_step(steps, _config, step, window)


def _select_lowest_turn_step(
    steps: tuple[TurnStep, ...],
    _config: GameConfig,
    _step: int,
    _window: str,
) -> TurnStep:
    return min(steps, key=turn_step_id)


def _load_basic_2p_round_flow(root: Path) -> LoadedScenario:
    return load_scenario(root / "scenarios" / "alms_sandbox_001.json")


def _load_movement_hotspot_2p(root: Path) -> LoadedScenario:
    scenario = load_scenario(root / "scenarios" / "kogge_cloisters_own_own_skip_duty_001.json")
    adjusted_state = _state_with_city_acolyte(
        scenario.state,
        player_id=PlayerId.PLAYER_TWO,
    )
    return replace(scenario, state=adjusted_state)


def _load_grain_store_2p(root: Path) -> LoadedScenario:
    scenario = load_scenario(root / "scenarios" / "grain_store_active_sell_wheat_001.json")
    adjusted_state = _state_with_city_acolyte(
        scenario.state,
        player_id=PlayerId.PLAYER_TWO,
    )
    return replace(scenario, state=adjusted_state)


def _load_generated_setup(root: Path, *, player_count: int, seed: int) -> LoadedScenario:
    generated = generate_setup_scenario(player_count=player_count, seed=seed)
    for field in _CONFIG_PATH_FIELDS:
        generated[field] = str((root / str(generated[field])).resolve())  # type: ignore[index]
    initial_state = generated["initial_state"]  # type: ignore[index]
    chosen_start_player = "player_one"
    initial_state["phase"] = "sow"
    initial_state["setup"] = {
        "setup_sow_required": False,
        "setup_sow_complete": True,
        "setup_sow_completed_by": [],
    }
    initial_state["start_player_id"] = chosen_start_player
    initial_state["active_player"] = chosen_start_player
    output_path = Path("/tmp") / f"pilgrim_multi_turn_branching_{player_count}p_seed_{seed}.json"
    output_path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")
    return load_scenario(output_path)


def _state_with_city_acolyte(state: GameState, *, player_id: PlayerId) -> GameState:
    player_state = state.player_state(player_id)
    workforce = player_state.workforce
    if workforce.mancala[0] > 0:
        return state
    updated_vector = (1, *workforce.mancala[1:])
    updated_workforce = replace(workforce, mancala=updated_vector)
    if workforce.village > 0:
        updated_workforce = replace(updated_workforce, village=workforce.village - 1)
    return state.with_player_state(
        player_id,
        replace(player_state, workforce=updated_workforce),
    )


def _is_hired_source(source_label: str | None) -> bool:
    return source_label is not None and source_label != "own_active"


if __name__ == "__main__":
    main()
