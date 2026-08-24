"""CLI entrypoint for scenario validation, action listing, apply, and exact search."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from pilgrim.evaluation import (
    EvaluationBreakdown,
    evaluate_player,
    evaluate_root_player,
    format_evaluation_breakdown_lines,
)
from pilgrim.io.event_text import format_event
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import (
    EndTurnAction,
    GameAction,
    SetupSowAction,
    StartPlayerConfessionBoxAction,
    StartPlayerSelectionAction,
    action_summary,
)
from pilgrim.model.config import GameConfig
from pilgrim.model.dummy import format_dummy_acolytes
from pilgrim.model.duties import DUTY_POSITIONS
from pilgrim.model.enums import PlayerId, position_name
from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState
from pilgrim.rules.buildings import (
    available_player_board_slots,
    building_names_for_ids,
    future_buildings,
    live_buildings,
    used_player_board_slots,
)
from pilgrim.rules.merchant import current_merchant_duty, current_merchant_resource
from pilgrim.rules.scoring import (
    DEFERRED_SCORING_CATEGORIES,
    ScoreBreakdown,
    score_all_players,
    score_breakdown,
)
from pilgrim.rules.special_activities import format_special_activities
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants
from pilgrim.search.exact import SearchResult, solve_exact
from pilgrim.search.objectives import (
    SearchObjective,
    objective_cli_choices,
    objective_description,
    objective_from_cli_name,
)
from pilgrim.setup.generator import generate_setup_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilgrim")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a JSON scenario.")
    validate_parser.add_argument("scenario", help="Path to scenario JSON file.")

    score_parser = subparsers.add_parser(
        "score",
        help="Print official implemented score breakdown.",
    )
    score_parser.add_argument("scenario", help="Path to scenario JSON file.")

    legal_parser = subparsers.add_parser("legal-actions", help="List readable legal actions.")
    legal_parser.add_argument("scenario", help="Path to scenario JSON file.")

    apply_parser = subparsers.add_parser("apply", help="Apply one legal action by index.")
    apply_parser.add_argument("scenario", help="Path to scenario JSON file.")
    apply_parser.add_argument(
        "--action-index",
        type=int,
        required=True,
        help="1-based index from legal-actions output.",
    )
    apply_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print action events and resulting state details.",
    )

    solve_parser = subparsers.add_parser("solve", help="Run placeholder exact search.")
    solve_parser.add_argument("scenario", help="Path to scenario JSON file.")
    solve_parser.add_argument("--depth", type=int, default=3, help="Search depth (default: 3).")
    solve_parser.add_argument(
        "--objective",
        default="sandbox",
        choices=objective_cli_choices(),
        help=(
            "Search objective: sandbox, implemented-official-score, "
            "or sandbox-with-official-terminal (default: sandbox)."
        ),
    )
    solve_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print first-action events and resulting state summary.",
    )

    generate_parser = subparsers.add_parser(
        "generate-setup",
        help="Generate deterministic seeded setup scenario JSON.",
    )
    generate_parser.add_argument(
        "--players",
        type=int,
        required=True,
        help="Table player count (2, 3, or 4).",
    )
    generate_parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Seed value for deterministic setup generation.",
    )
    generate_parser.add_argument(
        "--output",
        required=True,
        help="Path to write generated scenario JSON.",
    )
    generate_parser.add_argument(
        "--name",
        default=None,
        help="Optional scenario_id override.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate-setup":
        return _generate_setup_command(
            players=args.players,
            seed=args.seed,
            output=args.output,
            scenario_name=args.name,
        )

    scenario = load_scenario(args.scenario)
    if args.command == "validate":
        validate_state_invariants(scenario.state)
        print(f"Scenario '{scenario.scenario_id}' is valid.")
        return 0

    if args.command == "score":
        _print_score_sheet(scenario.state, scenario.config, scenario.scenario_id)
        return 0

    if args.command == "legal-actions":
        actions = legal_actions(scenario.state, scenario.config)
        print(f"Legal actions for scenario '{scenario.scenario_id}':")
        print()
        if not actions:
            if scenario.state.game_over:
                print("No legal actions available (game over).")
            else:
                print("No legal actions available.")
        for index, action in enumerate(actions, start=1):
            print(f"{index}. {action_summary(action, scenario.config)}")
        print()
        print(f"Total legal actions: {len(actions)}")
        return 0

    if args.command == "apply":
        actions = legal_actions(scenario.state, scenario.config)
        action_count = len(actions)
        selected_index = args.action_index
        if selected_index < 1 or selected_index > action_count:
            message = (
                f"Invalid action index {selected_index}. Scenario has {action_count} legal actions."
            )
            print(
                message,
                file=sys.stderr,
            )
            return 2

        selected_action = actions[selected_index - 1]
        transition_result = apply_action(scenario.state, selected_action, scenario.config)

        print(f"Apply result for scenario '{scenario.scenario_id}'")
        print(f"Selected action {selected_index}:")
        print(action_summary(selected_action, scenario.config))
        print()

        if args.verbose:
            _print_transition_report(
                initial_state=scenario.state,
                next_state=transition_result.state,
                events=transition_result.events,
                config=scenario.config,
                root_player_id=scenario.root_player_id,
                events_heading="Events:",
                state_heading="State after action:",
                evaluation_heading="Root-player evaluation after action:",
            )
        else:
            print("State updated successfully.")
            if transition_result.state.game_over:
                print("Next active player: none (game over)")
            else:
                print(f"Next active player: {transition_result.state.active_player.name.lower()}")
            print(f"Game over: {str(transition_result.state.game_over).lower()}")
        return 0

    if args.command == "solve":
        search_objective = objective_from_cli_name(args.objective)
        result = solve_exact(
            scenario.state,
            scenario.config,
            args.depth,
            root_player_id=scenario.root_player_id,
            opponent_model_type=scenario.opponent_model.type,
            objective=search_objective,
        )
        root_player_name = scenario.root_player_id.name.lower()
        print(f"Solve result for scenario '{scenario.scenario_id}'")
        print(f"Root player: {root_player_name}")
        print(f"Objective: {objective_description(search_objective)}")
        print(f"Opponent model: {scenario.opponent_model.type.value}")
        print(f"Depth: {args.depth}")
        print(f"Best score: {result.best_score}")
        print(f"Nodes expanded: {result.nodes_expanded}")
        print()

        best_action_heading = "Best first full turn:"
        events_heading = "Events for best first full turn:"
        state_heading = "State after best first full turn:"
        evaluation_heading = _solve_transition_report_heading(
            search_objective,
            is_setup_sow=False,
        )
        if isinstance(result.best_action, SetupSowAction):
            best_action_heading = "Best first setup sow:"
            events_heading = "Events for best first setup sow:"
            state_heading = "State after best first setup sow:"
            evaluation_heading = _solve_transition_report_heading(
                search_objective,
                is_setup_sow=True,
            )
        elif isinstance(result.best_action, StartPlayerConfessionBoxAction):
            best_action_heading = "Best Confession Box decision:"
            events_heading = "Events for best Confession Box decision:"
            state_heading = "State after best Confession Box decision:"
        elif isinstance(result.best_action, StartPlayerSelectionAction):
            best_action_heading = "Best start player choice:"
            events_heading = "Events for best start player choice:"
            state_heading = "State after best start player choice:"

        print(best_action_heading)
        if result.best_action is None:
            print("None")
        else:
            print(action_summary(result.best_action, scenario.config))

        if result.principal_variation:
            print()
            print("Best line:")
            annotated = _annotate_actions_with_active_players(
                scenario.state,
                result.principal_variation,
                scenario.config,
            )
            for index, (player_id, action) in enumerate(annotated, start=1):
                print(
                    f"{index}. {player_id.name.lower()}: {action_summary(action, scenario.config)}"
                )
            print()
            print(_solve_best_line_final_heading(search_objective))
            for line in _format_solve_best_line_breakdown(
                result,
                objective=search_objective,
            ):
                print(line)

        if args.verbose and result.best_action is not None:
            transition_result = apply_action(scenario.state, result.best_action, scenario.config)
            transition_events = list(transition_result.events)
            while transition_result.state.turn_progress.resolution_committed:
                transition_result = apply_action(
                    transition_result.state,
                    EndTurnAction(),
                    scenario.config,
                )
                transition_events.extend(transition_result.events)
            print()
            _print_transition_report(
                initial_state=scenario.state,
                next_state=transition_result.state,
                events=tuple(transition_events),
                config=scenario.config,
                root_player_id=scenario.root_player_id,
                events_heading=events_heading,
                state_heading=state_heading,
                evaluation_heading=evaluation_heading,
                objective=search_objective,
            )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _print_transition_report(
    *,
    initial_state: GameState,
    next_state: GameState,
    events: tuple[GameEvent, ...],
    config: GameConfig,
    root_player_id: PlayerId,
    events_heading: str,
    state_heading: str,
    evaluation_heading: str,
    objective: SearchObjective = SearchObjective.SANDBOX,
) -> None:
    print(events_heading)
    for event in events:
        formatted = format_event(event, config)
        if formatted is not None:
            print(f"* {formatted}")

    print()
    print(state_heading)
    for line in _format_state_summary(
        next_state,
        config,
        acted_player=initial_state.active_player,
    ):
        print(line)

    score_breakdown_for_root = score_breakdown(next_state, root_player_id, config)
    print()
    print(evaluation_heading)
    for line in _format_transition_breakdown_for_objective(
        objective,
        sandbox_breakdown=evaluate_root_player(
            next_state,
            root_player_id=root_player_id,
            config=config,
        ),
        implemented_breakdown=score_breakdown_for_root,
        state_is_terminal=next_state.game_over,
    ):
        print(line)


def _format_state_summary(
    state: GameState,
    config: GameConfig,
    *,
    acted_player: PlayerId,
) -> tuple[str, ...]:
    next_active_player = state.active_player
    acted_name = acted_player.name.lower()
    next_name = "none (game over)" if state.game_over else next_active_player.name.lower()
    north_group_text = format_dummy_acolytes(
        state.dummy_acolytes.north_group,
        positions=config.board.positions,
    )
    south_group_text = format_dummy_acolytes(
        state.dummy_acolytes.south_group,
        positions=config.board.positions,
    )
    total_group_text = format_dummy_acolytes(
        state.dummy_acolytes.total_vector,
        positions=config.board.positions,
    )
    setup_lines = _format_setup_summary(state)
    start_player_name = (
        state.start_player.name.lower() if state.start_player is not None else "not chosen yet"
    )

    lines: list[str] = [
        f"Acted player: {acted_name}",
        f"Next active player: {next_name}",
        "Timing:",
        f"  Absolute turn: {state.timing.absolute_turn}",
        f"  Round: {state.timing.round_number}",
        f"  Season: {state.timing.season_number}",
        f"  Turn in round: {state.timing.turn_in_round}",
        f"  Start player: {start_player_name}",
        f"  Game over: {str(state.game_over).lower()}",
        *setup_lines,
        "Ship:",
        f"  Position: {state.ship_position}",
        (
            "  At pilgrimage site: "
            f"{str(config.ship.is_pilgrimage_site(state.ship_position)).lower()}"
        ),
        (f"  At NW pilgrimage site: {str(config.ship.is_nw_site(state.ship_position)).lower()}"),
        "Merchant:",
        f"  Position: {current_merchant_duty(state, config)}",
        (f"  Resource: {current_merchant_resource(state, config) or 'none'}"),
        "Duty tiles:",
        *_format_duty_tiles_layout(config),
        "Building market:",
        f"  Level 1: {_market_building_names_for_level(state, config, 1)}",
        f"  Level 2: {_market_building_names_for_level(state, config, 2)}",
        f"  Level 3: {_market_building_names_for_level(state, config, 3)}",
        "Building availability:",
        *_format_building_availability_summary(state, config),
        "Dummy acolytes:",
        f"  north_group: {north_group_text}",
        f"  south_group: {south_group_text}",
        f"  total: {total_group_text}",
        "",
        "Acted player state:",
        *_format_player_state(state, acted_player, config),
    ]

    if not state.game_over and next_active_player is not acted_player:
        lines.extend(
            [
                "",
                "Next active player state:",
                *_format_player_state(state, next_active_player, config),
            ]
        )

    return tuple(lines)


def _format_setup_summary(state: GameState) -> tuple[str, ...]:
    if not state.setup_sow_required:
        return ("Setup: not required",)

    completed_by = tuple(player_id.name.lower() for player_id in state.setup_sow_completed_by)
    if state.setup_sow_complete:
        if completed_by:
            completed_text = ", ".join(completed_by)
        else:
            completed_text = "unavailable (legacy state)"
        return (
            "Setup:",
            "  Setup sow: complete",
            f"  Completed by: {completed_text}",
        )

    all_players = tuple(PlayerId(index) for index in range(state.player_count))
    completed_set = set(state.setup_sow_completed_by)
    remaining = tuple(
        player_id.name.lower() for player_id in all_players if player_id not in completed_set
    )
    completed_text = ", ".join(completed_by) if completed_by else "none"
    remaining_text = ", ".join(remaining) if remaining else "none (legacy state)"
    return (
        "Setup:",
        "  Setup sow: in progress",
        f"  Completed by: {completed_text}",
        f"  Remaining: {remaining_text}",
    )


def _format_player_state(
    state: GameState,
    player: PlayerId,
    config: GameConfig,
) -> tuple[str, ...]:
    positions = config.board.positions
    breakdown = evaluate_player(state, player, config)
    player_state = state.player_state(player)
    player_vector = state.player_vector(player)
    slots = player_state.player_board_slots
    active_building_names = building_names_for_ids(slots.active_buildings, config.buildings)
    donated_building_names = building_names_for_ids(slots.donated_buildings, config.buildings)
    used_slots = used_player_board_slots(player_state)
    total_slots = config.buildings.player_board.building_and_cardinal_slot_limit
    available_slots = available_player_board_slots(player_state, config)
    special_activity_acolytes = player_state.special_activities.count
    workforce_total = player_state.workforce.total + special_activity_acolytes
    special_activities = format_special_activities(player_state)
    mancala = ", ".join(
        f"{position_name(position_id, positions)}={count}"
        for position_id, count in enumerate(player_vector)
    )
    return (
        (f"Resources: stone={breakdown.stone}, silver={breakdown.silver}, wheat={breakdown.wheat}"),
        f"Piety position: {breakdown.piety_position}",
        f"Piety track VP: {breakdown.piety_track_vp}",
        f"Alms position: {breakdown.alms_position}",
        f"Alms table acolytes: {breakdown.alms_table_acolytes}",
        f"Alms table VP: {breakdown.alms_table_vp}",
        "Workforce:",
        f"  Mancala total: {player_state.workforce.mancala_total}",
        f"  Village: {player_state.workforce.village}",
        f"  Abbey: {player_state.workforce.abbey}",
        f"  Special Activities: {special_activity_acolytes}",
        (
            "  Committed: "
            f"roads={player_state.workforce.committed.roads}, "
            f"shrines={player_state.workforce.committed.shrines}, "
            f"market_ports={player_state.workforce.committed.market_ports}, "
            f"pilgrimage_sites={player_state.workforce.committed.pilgrimage_sites}, "
            f"alms_table={player_state.workforce.committed.alms_table}"
        ),
        f"  Total: {workforce_total}",
        "Village:",
        f"  Serfs: {player_state.workforce.village}",
        "Abbey:",
        f"  Acolytes: {player_state.workforce.abbey}",
        f"Special Activities: {special_activities}",
        "Player board slots:",
        (
            "  Active buildings: "
            f"{', '.join(active_building_names) if active_building_names else 'none'}"
        ),
        (
            "  Donated buildings: "
            f"{', '.join(donated_building_names) if donated_building_names else 'none'}"
        ),
        f"  Cardinal favor tiles: {slots.cardinal_favor_tiles}",
        f"  Used slots: {used_slots}/{total_slots}",
        f"  Available slots: {available_slots}",
        f"Mancala: {mancala}",
    )


def _format_evaluation_breakdown(breakdown: EvaluationBreakdown) -> tuple[str, ...]:
    return format_evaluation_breakdown_lines(breakdown)


def _solve_transition_report_heading(
    objective: SearchObjective,
    *,
    is_setup_sow: bool,
) -> str:
    transition_target = "setup sow" if is_setup_sow else "full turn"
    if objective is SearchObjective.SANDBOX:
        return f"Root-player evaluation after best first {transition_target}:"
    if objective is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE:
        return f"Root-player implemented official score after best first {transition_target}:"
    return (
        "Root-player objective score after best first "
        f"{transition_target} (sandbox unless game over):"
    )


def _solve_best_line_final_heading(objective: SearchObjective) -> str:
    if objective is SearchObjective.SANDBOX:
        return "Best-line final evaluation:"
    if objective is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE:
        return "Best-line final implemented official score:"
    return "Best-line final objective score (sandbox unless game over):"


def _format_solve_best_line_breakdown(
    result: SearchResult,
    *,
    objective: SearchObjective,
) -> tuple[str, ...]:
    if objective is SearchObjective.SANDBOX:
        return _format_evaluation_breakdown(result.best_line_final_breakdown)
    if objective is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE:
        return _format_score_breakdown_with_player(result.best_line_final_score_breakdown)

    # Hybrid objective: only terminal states switch to official score.
    if not result.best_line_final_state_game_over:
        return (
            "Scoring mode: sandbox",
            *_format_evaluation_breakdown(result.best_line_final_breakdown),
        )
    player_name = (
        result.best_line_final_breakdown.player_name
        if result.best_line_final_breakdown.player_name is not None
        else result.root_player_id.name.lower()
    )
    return (
        "Scoring mode: implemented official score (terminal)",
        f"Player: {player_name}",
        f"Objective score: {result.best_score}",
        *_format_score_breakdown_lines(result.best_line_final_score_breakdown),
    )


def _format_transition_breakdown_for_objective(
    objective: SearchObjective,
    *,
    sandbox_breakdown: EvaluationBreakdown,
    implemented_breakdown: ScoreBreakdown,
    state_is_terminal: bool,
) -> tuple[str, ...]:
    if objective is SearchObjective.SANDBOX:
        return _format_evaluation_breakdown(sandbox_breakdown)
    if objective is SearchObjective.IMPLEMENTED_OFFICIAL_SCORE:
        return _format_score_breakdown_with_player(implemented_breakdown)
    if state_is_terminal:
        return (
            "Scoring mode: implemented official score (terminal)",
            *_format_score_breakdown_with_player(implemented_breakdown),
        )
    return (
        "Scoring mode: sandbox",
        *_format_evaluation_breakdown(sandbox_breakdown),
    )


def _print_score_sheet(state: GameState, config: GameConfig, scenario_id: str) -> None:
    score_by_player = score_all_players(state, config)
    print(f"Score sheet for scenario '{scenario_id}'")
    print()
    for player_index, (player_id, breakdown) in enumerate(score_by_player.items()):
        print(player_id.name.lower())
        for line in _format_score_breakdown_lines(breakdown):
            print(line)
        if player_index < len(score_by_player) - 1:
            print()
    print()
    print("Deferred / not yet implemented:")
    deferred = (
        next(iter(score_by_player.values())).deferred_categories
        if score_by_player
        else DEFERRED_SCORING_CATEGORIES
    )
    for category in deferred:
        print(f"  {category}")


def _format_score_breakdown_lines(breakdown: ScoreBreakdown) -> tuple[str, ...]:
    return (
        f"  Acolytes in Abbey / City / Duty tiles: {breakdown.acolytes_vp} VP",
        f"  Piety track: {breakdown.piety_vp} VP",
        f"  Alms table: {breakdown.alms_vp} VP",
        f"  Donated buildings: {breakdown.donated_buildings_vp} VP",
        f"  Resources: {breakdown.resources_vp} VP",
        f"  Total implemented score: {breakdown.implemented_total} VP",
    )


def _format_score_breakdown_with_player(breakdown: ScoreBreakdown) -> tuple[str, ...]:
    return (
        f"Player: {breakdown.player.name.lower()}",
        *_format_score_breakdown_lines(breakdown),
    )


def _annotate_actions_with_active_players(
    initial_state: GameState,
    actions: tuple[GameAction, ...],
    config: GameConfig,
) -> tuple[tuple[PlayerId, GameAction], ...]:
    state = initial_state
    annotated: list[tuple[PlayerId, GameAction]] = []
    for action in actions:
        annotated.append((state.active_player, action))
        state = apply_action(state, action, config).state
        # Exact-search lines contain full-turn decisions. The End Turn window is still an engine
        # state, but its pass is deterministic and is not one of the line's chosen actions.
        while state.turn_progress.resolution_committed:
            state = apply_action(state, EndTurnAction(), config).state
    return tuple(annotated)


def _market_building_names_for_level(
    state: GameState,
    config: GameConfig,
    level: int,
) -> str:
    level_ids = tuple(
        building_id
        for building_id in state.building_market
        if config.buildings.definition_by_id(building_id).level == level
    )
    level_names = building_names_for_ids(level_ids, config.buildings)
    if not level_names:
        return "none"
    return ", ".join(level_names)


def _format_building_availability_summary(
    state: GameState,
    config: GameConfig,
) -> tuple[str, ...]:
    live_set = set(live_buildings(state))
    availability_map = {
        building_id: live_round for building_id, live_round in state.building_availability
    }
    market_set = set(state.building_market)
    market_live_ids = tuple(
        building_id for building_id in state.building_market if building_id in live_set
    )
    market_future_entries = tuple(
        (building_id, live_round)
        for building_id, live_round in future_buildings(state)
        if building_id in market_set
    )

    market_live_names = building_names_for_ids(market_live_ids, config.buildings)
    live_market_text = ", ".join(market_live_names) if market_live_names else "none"

    market_future_text_parts: list[str] = []
    for building_id, live_round in market_future_entries:
        building_name = config.buildings.name_for_id(building_id)
        market_future_text_parts.append(f"{building_name} (round {live_round})")
    future_market_text = ", ".join(market_future_text_parts) if market_future_text_parts else "none"

    owned_live_parts: list[str] = []
    for player_id in (PlayerId(index) for index in range(state.player_count)):
        player_label = player_id.name.lower()
        slots = state.player_state(player_id).player_board_slots
        owned_ids = (*slots.active_buildings, *slots.donated_buildings)
        for building_id in owned_ids:
            if building_id in market_set:
                continue
            # Legacy scenarios may omit live-round entries for owned-only buildings.
            # Treat those as currently live for this summary to match board ownership display.
            if building_id not in live_set and building_id in availability_map:
                continue
            building_name = config.buildings.name_for_id(building_id)
            owned_live_parts.append(f"{building_name} ({player_label})")
    owned_live_text = ", ".join(owned_live_parts) if owned_live_parts else "none"

    return (
        f"  Live market: {live_market_text}",
        f"  Future market: {future_market_text}",
        f"  Owned/live: {owned_live_text}",
    )


def _format_duty_tiles_layout(config: GameConfig) -> tuple[str, ...]:
    duty_tiles = config.duty_tiles_mapping()
    return tuple(
        f"  {position_name}: {duty_tiles[position_name]}" for position_name in DUTY_POSITIONS
    )


def _generate_setup_command(
    *,
    players: int,
    seed: int,
    output: str,
    scenario_name: str | None,
) -> int:
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        generated = generate_setup_scenario(
            player_count=players,
            seed=seed,
            scenario_name=scenario_name,
        )
        _rewrite_generated_config_paths_for_output(generated, output_path=output_path)
        _validate_generated_scenario_payload(generated, output_path=output_path)
    except Exception as exc:
        print(f"Generated scenario failed validation: {exc}", file=sys.stderr)
        return 2

    output_path.write_text(
        json.dumps(generated, indent=2) + "\n",
        encoding="utf-8",
    )
    for line in _format_generated_setup_summary(
        generated,
        output_path=output_path,
    ):
        print(line)
    return 0


def _rewrite_generated_config_paths_for_output(
    generated: dict[str, object],
    *,
    output_path: Path,
) -> None:
    output_dir = output_path.parent
    repo_root = Path(__file__).resolve().parents[1]
    path_fields = (
        "board_file",
        "duties_file",
        "piety_file",
        "alms_file",
        "timing_file",
        "merchant_file",
        "ship_file",
        "buildings_file",
    )
    for field_name in path_fields:
        raw_path = generated.get(field_name)
        if not isinstance(raw_path, str):
            raise ValueError(f"Generated scenario field '{field_name}' must be a string path.")
        absolute_path = (
            Path(raw_path).resolve()
            if Path(raw_path).is_absolute()
            else (repo_root / raw_path).resolve()
        )
        generated[field_name] = Path(os.path.relpath(absolute_path, output_dir)).as_posix()


def _validate_generated_scenario_payload(
    generated: dict[str, object],
    *,
    output_path: Path,
) -> None:
    temp_path = output_path.parent / f".{output_path.stem}.validate.tmp.json"
    temp_path.write_text(json.dumps(generated, indent=2) + "\n", encoding="utf-8")
    try:
        loaded = load_scenario(temp_path)
        validate_state_invariants(loaded.state)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _format_generated_setup_summary(
    generated: dict[str, object],
    *,
    output_path: Path,
) -> tuple[str, ...]:
    player_count = int(generated.get("player_count", 0))
    metadata = generated.get("setup_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Generated scenario missing setup_metadata object.")
    seed = metadata.get("seed")
    setup_sow_required = str(bool(metadata.get("setup_sow_required", False))).lower()
    duty_tiles = generated.get("duty_tiles")
    if not isinstance(duty_tiles, dict):
        raise ValueError("Generated scenario missing duty_tiles object.")
    taxation_tile = next(
        position for position, category in duty_tiles.items() if category == "taxation"
    )
    duty_layout = ", ".join(f"{position}={category}" for position, category in duty_tiles.items())
    tithe_counters = generated.get("tithe_counters")
    if not isinstance(tithe_counters, dict):
        raise ValueError("Generated scenario missing tithe_counters object.")
    initial_state = generated.get("initial_state")
    if not isinstance(initial_state, dict):
        raise ValueError("Generated scenario missing initial_state object.")
    building_market = initial_state.get("building_market")
    if not isinstance(building_market, list):
        raise ValueError("Generated scenario missing initial_state.building_market list.")
    building_availability = initial_state.get("building_availability")
    if not isinstance(building_availability, dict):
        raise ValueError("Generated scenario missing initial_state.building_availability object.")
    setup_timeline_lines = _format_generated_setup_timeline_summary(metadata)
    return (
        f"Generated setup scenario: {output_path.as_posix()}",
        f"Players: {player_count}",
        f"Seed: {seed}",
        f"Duty tiles: {duty_layout}",
        f"Taxation tile: {taxation_tile}",
        f"Tithe counters: {len(tithe_counters)} counters; taxation has none",
        f"Building market: {len(building_market)} buildings",
        f"Building availability: {len(building_availability)} entries",
        *setup_timeline_lines,
        f"Dummy acolytes: {player_count}-player setup",
        f"Setup sow required: {setup_sow_required}",
    )


def _format_generated_setup_timeline_summary(metadata: dict[str, object]) -> tuple[str, ...]:
    setup_timeline = metadata.get("setup_timeline")
    if not isinstance(setup_timeline, dict):
        return ()

    pilgrimage_rolls = setup_timeline.get("pilgrimage_rolls")
    if not isinstance(pilgrimage_rolls, dict):
        raise ValueError("Generated scenario missing setup_timeline.pilgrimage_rolls object.")
    pilgrimage_rounds = setup_timeline.get("pilgrimage_rounds")
    if not isinstance(pilgrimage_rounds, dict):
        raise ValueError("Generated scenario missing setup_timeline.pilgrimage_rounds object.")
    building_live_rounds = setup_timeline.get("building_live_rounds")
    if not isinstance(building_live_rounds, dict):
        raise ValueError("Generated scenario missing setup_timeline.building_live_rounds object.")

    nw = int(pilgrimage_rolls["nw"])
    ne = int(pilgrimage_rolls["ne"])
    se = int(pilgrimage_rolls["se"])
    sw = int(pilgrimage_rolls["sw"])
    site_1_round = int(pilgrimage_rounds["site_1"])
    site_2_round = int(pilgrimage_rounds["site_2"])
    site_3_round = int(pilgrimage_rounds["site_3"])
    site_4_round = int(pilgrimage_rounds["site_4"])

    level_lines: list[str] = []
    for key, label in (("level_1", "Level 1"), ("level_2", "Level 2"), ("level_3", "Level 3")):
        level_mapping = building_live_rounds.get(key)
        if not isinstance(level_mapping, dict):
            raise ValueError(
                "Generated scenario setup_timeline.building_live_rounds is missing "
                f"{key!r} mapping."
            )
        if not level_mapping:
            level_lines.append(f"  {label}: none")
            continue
        formatted = ", ".join(
            f"{building_id}=round {int(live_round)}"
            for building_id, live_round in level_mapping.items()
        )
        level_lines.append(f"  {label}: {formatted}")

    return (
        "Pilgrimage d6 rolls:",
        f"  NW={nw}, NE={ne}, SE={se}, SW={sw}",
        "Pilgrimage rounds:",
        f"  Site 1: round {site_1_round}",
        f"  Site 2: round {site_2_round}",
        f"  Site 3: round {site_3_round}",
        f"  Site 4: round {site_4_round}",
        "Building live rounds:",
        *level_lines,
    )


if __name__ == "__main__":
    raise SystemExit(main())
