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
    FullTurnAction,
    GameAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_id,
    action_summary,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import PlayerId, TurnPhase, TurnResolutionType
from pilgrim.model.state import GameState
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.setup.generator import generate_setup_scenario

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
TraceLoader = Callable[[Path], LoadedScenario]


@dataclass(frozen=True, slots=True)
class TraceDefinition:
    name: str
    description: str
    steps: int
    loader: TraceLoader
    selector: ActionSelector


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
    unique_action_id_count: int
    duplicate_action_id_count: int
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
    actions_with_hired_building: int
    actions_with_two_or_more_hired_buildings: int
    actions_with_route_modifier: int
    actions_with_kogge: int
    actions_with_cloisters: int
    actions_with_kogge_cloisters_combined: int
    actions_with_start_turn_modifier: int
    actions_with_end_turn_modifier: int
    actions_with_grain_store_conversion: int
    actions_with_building_conversion: int
    selected_action_id: str
    selected_action_summary: str


@dataclass(frozen=True, slots=True)
class TraceResult:
    definition: TraceDefinition
    rows: tuple[TraceStepRow, ...]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def configured_trace_names() -> tuple[str, ...]:
    return _TRACE_ORDER


def action_hired_building_count(action: FullTurnAction) -> int:
    count = 0
    if action.hired_building_id is not None:
        count += 1
    if _is_hired_source(action.start_turn_building_source):
        count += 1
    if _is_hired_source(action.end_turn_building_source):
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
    return action.start_turn_building_id is not None


def action_has_end_turn_modifier(action: FullTurnAction) -> bool:
    return action.end_turn_building_id is not None


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
        ),
        TraceDefinition(
            name="movement_hotspot_2p",
            description="2p branching hotspot with Kogge+Cloisters route modifiers.",
            steps=6,
            loader=_load_movement_hotspot_2p,
            selector=_select_movement_hotspot_action,
        ),
        TraceDefinition(
            name="grain_store_2p",
            description="2p Grain Store conversion branching over six turns.",
            steps=6,
            loader=_load_grain_store_2p,
            selector=_select_grain_store_action,
        ),
        TraceDefinition(
            name="generated_setup_3p",
            description="Generated setup probe for 3-player turn-order/branching.",
            steps=4,
            loader=lambda root: _load_generated_setup(root, player_count=3, seed=3),
            selector=_select_preferred_safe_action,
        ),
        TraceDefinition(
            name="generated_setup_4p",
            description="Generated setup probe for 4-player turn-order/branching.",
            steps=5,
            loader=lambda root: _load_generated_setup(root, player_count=4, seed=4),
            selector=_select_preferred_safe_action,
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
) -> tuple[TraceStepRow, ...]:
    rows: list[TraceStepRow] = []
    current_state = state
    for step in range(1, steps + 1):
        # A game opens, and every round ends, by stopping on whoever holds the First Player marker.
        # Answered and stepped over rather than measured: a row counts how a TURN branches --
        # routes, duties, what to do with them -- and a position whose only question is who begins
        # has none of that. Its branching is one per seat, and is not what this audit looks at.
        # The holder keeps it, so the trace walks a fixed seating rather than a wandering one.
        # The Confession Box questions are stepped over on the same grounds and with the answer
        # that changes nothing. A seat deciding whether to buy two piety for the marker is not
        # branching a turn either, and declining leaves the walk where it was.
        while current_state.phase in (
            TurnPhase.START_PLAYER_CONFESSION,
            TurnPhase.START_PLAYER_SELECTION,
        ):
            answer: GameAction = (
                StartPlayerConfessionBoxAction(use=False)
                if current_state.phase is TurnPhase.START_PLAYER_CONFESSION
                else StartPlayerSelectionAction(chosen_start_player=current_state.active_player)
            )
            current_state = apply_action(current_state, answer, config).state
        actions = legal_actions(current_state, config)
        if not actions:
            break
        action_ids = tuple(action_id(action) for action in actions)
        selected_action = selector(actions, config, step)
        selected_id = action_id(selected_action)
        if selected_id not in set(action_ids):
            raise ValueError(
                f"Selector returned non-legal action at trace={trace_name} step={step}: {selected_id}"
            )

        setup_sow_actions = [action for action in actions if isinstance(action, SetupSowAction)]
        full_turn_actions = [action for action in actions if isinstance(action, FullTurnAction)]
        route_lengths = [len(action.route) for action in full_turn_actions]
        picked_up_counts = list(route_lengths)
        distinct_routes = {action.route for action in full_turn_actions}
        distinct_actual_routes = {
            _actual_route_for_branching_metrics(action) for action in full_turn_actions
        }
        row = TraceStepRow(
            trace_name=trace_name,
            step=step,
            absolute_turn=current_state.timing.absolute_turn,
            round_number=current_state.timing.round_number,
            season_number=current_state.timing.season_number,
            turn_in_round=current_state.timing.turn_in_round,
            active_player=current_state.active_player.name.lower(),
            legal_action_count=len(actions),
            unique_action_id_count=len(set(action_ids)),
            duplicate_action_id_count=len(action_ids) - len(set(action_ids)),
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
            actions_with_hired_building=_count_matching(full_turn_actions, action_has_hire),
            actions_with_two_or_more_hired_buildings=_count_matching(
                full_turn_actions,
                lambda action: action_hired_building_count(action) >= 2,
            ),
            actions_with_route_modifier=_count_matching(
                full_turn_actions, action_has_route_modifier
            ),
            actions_with_kogge=_count_matching(full_turn_actions, action_has_kogge),
            actions_with_cloisters=_count_matching(full_turn_actions, action_has_cloisters),
            actions_with_kogge_cloisters_combined=_count_matching(
                full_turn_actions,
                action_has_combined_kogge_cloisters,
            ),
            actions_with_start_turn_modifier=_count_matching(
                full_turn_actions,
                action_has_start_turn_modifier,
            ),
            actions_with_end_turn_modifier=_count_matching(
                full_turn_actions, action_has_end_turn_modifier
            ),
            actions_with_grain_store_conversion=_count_matching(
                full_turn_actions,
                action_has_grain_store_conversion,
            ),
            actions_with_building_conversion=_count_matching(
                full_turn_actions,
                action_has_building_conversion,
            ),
            selected_action_id=selected_id,
            selected_action_summary=action_summary(selected_action, config),
        )
        rows.append(row)
        current_state = apply_action(current_state, selected_action, config).state
    return tuple(rows)


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
            "Step  AbsTurn  Round  Season  TIR  Player       Legal  Unique  Dups  "
            "Hired  2+Hired  RouteMod  Kogge  Cloisters  K+C  StartMod  EndMod  Conv  GrainStore"
        ),
        (
            "----  -------  -----  ------  ---  -----------  -----  ------  ----  "
            "-----  -------  --------  -----  ---------  ---  --------  ------  ----  ----------"
        ),
    ]
    for row in result.rows:
        lines.append(
            f"{row.step:>4}  "
            f"{row.absolute_turn:>7}  "
            f"{row.round_number:>5}  "
            f"{row.season_number:>6}  "
            f"{row.turn_in_round:>3}  "
            f"{row.active_player:<11}  "
            f"{row.legal_action_count:>5}  "
            f"{row.unique_action_id_count:>6}  "
            f"{row.duplicate_action_id_count:>4}  "
            f"{row.actions_with_hired_building:>5}  "
            f"{row.actions_with_two_or_more_hired_buildings:>7}  "
            f"{row.actions_with_route_modifier:>8}  "
            f"{row.actions_with_kogge:>5}  "
            f"{row.actions_with_cloisters:>9}  "
            f"{row.actions_with_kogge_cloisters_combined:>3}  "
            f"{row.actions_with_start_turn_modifier:>8}  "
            f"{row.actions_with_end_turn_modifier:>6}  "
            f"{row.actions_with_building_conversion:>4}  "
            f"{row.actions_with_grain_store_conversion:>10}"
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
    lines.extend(_format_trace_summary(result.rows))
    return lines


def _format_trace_summary(rows: tuple[TraceStepRow, ...]) -> list[str]:
    if not rows:
        return ["Summary:", "- no steps executed"]
    max_legal = max(rows, key=lambda row: row.legal_action_count)
    max_dups = max(rows, key=lambda row: row.duplicate_action_id_count)
    max_hired = max(rows, key=lambda row: row.actions_with_hired_building)
    max_combined = max(rows, key=lambda row: row.actions_with_kogge_cloisters_combined)
    max_grain_store = max(rows, key=lambda row: row.actions_with_grain_store_conversion)
    max_routes = max(rows, key=lambda row: row.distinct_routes)
    max_duties = max(rows, key=lambda row: row.distinct_selected_duties)
    max_pickup = max(rows, key=lambda row: row.max_picked_up_acolytes)
    likely_driver = _likely_branching_driver(max_legal)
    return [
        "Summary:",
        f"- max legal actions: {max_legal.legal_action_count} at step {max_legal.step}",
        f"- max duplicate action IDs: {max_dups.duplicate_action_id_count} at step {max_dups.step}",
        f"- max hired-building actions: {max_hired.actions_with_hired_building} at step {max_hired.step}",
        (
            "- max combined Kogge+Cloisters actions: "
            f"{max_combined.actions_with_kogge_cloisters_combined} at step {max_combined.step}"
        ),
        (
            "- max Grain Store conversion actions: "
            f"{max_grain_store.actions_with_grain_store_conversion} at step {max_grain_store.step}"
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
        (f"- likely driver at max-branching step {max_legal.step}: {likely_driver}"),
    ]


def _likely_branching_driver(row: TraceStepRow) -> str:
    if (
        row.legal_action_count >= 100
        and row.actions_with_hired_building == 0
        and row.actions_with_route_modifier == 0
        and row.actions_with_grain_store_conversion == 0
    ):
        return "base sow/duty expansion"
    if row.actions_with_kogge_cloisters_combined > 0:
        return "combined route modifiers"
    if row.actions_with_grain_store_conversion > 0:
        return "building conversion quantities"
    if row.actions_with_route_modifier > 0:
        return "route/start/end modifiers"
    if row.actions_with_hired_building > 0:
        return "hired-building variants"
    return "mixed / low"


def _format_overall_summary(results: tuple[TraceResult, ...]) -> list[str]:
    all_rows = [row for result in results for row in result.rows]
    if not all_rows:
        return ["Overall summary:", "- no traces executed"]
    duplicate_total = sum(row.duplicate_action_id_count for row in all_rows)
    return [
        "Overall summary:",
        f"- traces executed: {len(results)}",
        f"- total steps executed: {len(all_rows)}",
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
    actions: tuple[GameAction, ...],
    config: GameConfig,
    step: int,
) -> GameAction:
    full_turn_actions = [action for action in actions if isinstance(action, FullTurnAction)]
    if step == 1:
        conversion_actions = [
            action for action in full_turn_actions if action_has_grain_store_conversion(action)
        ]
        if conversion_actions:
            return min(conversion_actions, key=action_id)
    return _select_preferred_safe_action(actions, config, step)


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
