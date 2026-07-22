"""CLI entrypoint for scenario validation, action listing, apply, and exact search."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from pilgrim.evaluation import (
    EvaluationBreakdown,
    evaluate_player,
    evaluate_root_player,
    format_evaluation_breakdown_lines,
)
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import GameAction, action_summary, readable_route
from pilgrim.model.config import GameConfig
from pilgrim.model.dummy import format_dummy_acolytes
from pilgrim.model.enums import EventType, PlayerId, position_name
from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState
from pilgrim.rules.merchant import current_merchant_duty, current_merchant_resource
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants
from pilgrim.search.exact import solve_exact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilgrim")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a JSON scenario.")
    validate_parser.add_argument("scenario", help="Path to scenario JSON file.")

    legal_parser = subparsers.add_parser("legal-actions", help="List readable full-turn actions.")
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
        "--verbose",
        action="store_true",
        help="Print first-action events and resulting state summary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    scenario = load_scenario(args.scenario)
    if args.command == "validate":
        validate_state_invariants(scenario.state)
        print(f"Scenario '{scenario.scenario_id}' is valid.")
        return 0

    if args.command == "legal-actions":
        actions = legal_actions(scenario.state, scenario.config)
        print(f"Legal actions for scenario '{scenario.scenario_id}':")
        print()
        if not actions:
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
                f"Invalid action index {selected_index}. "
                f"Scenario has {action_count} legal actions."
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
            print(f"Next active player: {transition_result.state.active_player.name.lower()}")
        return 0

    if args.command == "solve":
        result = solve_exact(
            scenario.state,
            scenario.config,
            args.depth,
            root_player_id=scenario.root_player_id,
            opponent_model_type=scenario.opponent_model.type,
        )
        root_player_name = scenario.root_player_id.name.lower()
        print(f"Solve result for scenario '{scenario.scenario_id}'")
        print(f"Root player: {root_player_name}")
        print("Objective: maximize root player sandbox evaluation")
        print(f"Opponent model: {scenario.opponent_model.type.value}")
        print(f"Depth: {args.depth}")
        print(f"Best score: {result.best_score}")
        print(f"Nodes expanded: {result.nodes_expanded}")
        print()

        print("Best first full turn:")
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
                    f"{index}. {player_id.name.lower()}: "
                    f"{action_summary(action, scenario.config)}"
                )
            print()
            print("Best-line final evaluation:")
            for line in _format_evaluation_breakdown(result.best_line_final_breakdown):
                print(line)

        if args.verbose and result.best_action is not None:
            transition_result = apply_action(scenario.state, result.best_action, scenario.config)
            print()
            _print_transition_report(
                initial_state=scenario.state,
                next_state=transition_result.state,
                events=transition_result.events,
                config=scenario.config,
                root_player_id=scenario.root_player_id,
                events_heading="Events for best first full turn:",
                state_heading="State after best first full turn:",
                evaluation_heading="Root-player evaluation after best first full turn:",
            )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _format_event(event: GameEvent, config: GameConfig) -> str | None:
    details = dict(event.details)
    positions = config.board.positions
    event_name = event.event_type.value.upper()
    actor_name = event.actor.name.lower()

    if event.event_type is EventType.SOWING:
        source = int(details.get("source", -1))
        picked_up = details.get("picked_up", "?")
        route_text = str(details.get("route", ""))
        route = _parse_route(route_text)
        return (
            f"{event_name}: picked up {picked_up} from {position_name(source, positions)}; "
            f"route {readable_route(source, route, positions=positions)}"
        )

    if event.event_type is EventType.DUTY_RESOLUTION:
        duty_position = details.get("duty_position")
        duty_label = (
            position_name(int(duty_position), positions)
            if isinstance(duty_position, int)
            else "unknown"
        )
        if details.get("mode") == "tithe":
            return f"{event_name}: selected {duty_label}; mode tithe"
        fragments = [f"selected {duty_label}"]
        if "strength" in details:
            fragments.append(f"relation {details['strength']}")
        if "duty_value" in details:
            fragments.append(f"duty value {details['duty_value']}")
        if "silver_cost" in details:
            fragments.append(f"silver cost {details['silver_cost']}")
        if "effect" in details:
            fragments.append(f"action {details['effect']}")
        return f"{event_name}: {'; '.join(fragments)}"

    if event.event_type is EventType.RESOURCE_DELTA:
        stone = int(details.get("stone", 0))
        silver = int(details.get("silver", 0))
        wheat = int(details.get("wheat", 0))
        fragments: list[str] = []
        if stone != 0:
            fragments.append(f"stone {stone:+d}")
        if silver != 0:
            fragments.append(f"silver {silver:+d}")
        if wheat != 0:
            fragments.append(f"wheat {wheat:+d}")
        if not fragments:
            return None
        return f"{event_name}: {actor_name} {'; '.join(fragments)}"

    if event.event_type is EventType.PIETY_DELTA:
        if "old_piety_position" in details and "new_piety_position" in details:
            old_position = int(details["old_piety_position"])
            new_position = int(details["new_piety_position"])
            if old_position == new_position:
                return None
            old_vp = int(details.get("old_piety_vp", 0))
            new_vp = int(details.get("new_piety_vp", 0))
            return (
                f"{event_name}: {actor_name} piety {old_position} -> {new_position}; "
                f"track VP {old_vp} -> {new_vp}"
            )
        amount = int(details.get("piety", 0))
        if amount == 0:
            return None
        return f"{event_name}: {actor_name} {amount:+d} piety"

    if event.event_type is EventType.ACOLYTE_RECALL:
        duty_position = int(details.get("duty_position", -1))
        recalled = int(details.get("recalled", 0))
        duty_label = position_name(duty_position, positions)
        return f"{event_name}: recalled {recalled} from {duty_label} to city"

    if event.event_type is EventType.INVARIANT_CHECK:
        if details.get("acolytes_conserved") is True:
            total_workforce_p1 = details.get("total_workforce_player_one")
            total_workforce_p2 = details.get("total_workforce_player_two")
            if isinstance(total_workforce_p1, int) and isinstance(total_workforce_p2, int):
                return (
                    f"{event_name}: passed for all players "
                    f"(acolytes conserved; total workforce by player: "
                    f"player_one={total_workforce_p1}, player_two={total_workforce_p2})"
                )
            total_workforce = details.get("total_workforce")
            if isinstance(total_workforce, int):
                return (
                    f"{event_name}: passed "
                    f"(acolytes conserved; total workforce={total_workforce})"
                )
            return f"{event_name}: passed (acolytes conserved)"
        return f"{event_name}: {details}"

    if event.event_type is EventType.ALMS_PAYMENT:
        silver = int(details.get("silver", 0))
        wheat = int(details.get("wheat", 0))
        text = f"{event_name}: {actor_name} paid silver={silver}, wheat={wheat}"
        minority_silver_cost = int(details.get("minority_silver_cost", 0))
        if minority_silver_cost > 0:
            text += f" (plus minority silver cost {minority_silver_cost})"
        return text

    if event.event_type is EventType.ALMS_PROGRESS:
        old_row = int(details.get("old_row", 0))
        new_row = int(details.get("new_row", 0))
        return f"{event_name}: {actor_name} row {old_row} -> {new_row}"

    if event.event_type is EventType.ALMS_THRESHOLD_REWARD:
        description = str(details.get("description", "")).strip()
        if description:
            return f"{event_name}: {description}"
        threshold = int(details.get("threshold", -1))
        reward = str(details.get("reward", "unknown"))
        moved = bool(details.get("moved", False))
        return f"{event_name}: crossed row {threshold}; reward={reward}; moved={moved}"

    if event.event_type is EventType.ALMS_SEASON_REWARD:
        winner = details.get("winner")
        moved = bool(details.get("moved", False))
        if moved:
            return f"{event_name}: {winner} moved 1 acolyte abbey -> alms_table"
        return f"{event_name}: {winner} had no abbey acolyte to move"

    if event.event_type is EventType.ALMS_RESET:
        return f"{event_name}: all players reset to row 0"

    if event.event_type is EventType.DUMMY_ACOLYTE_MOVE:
        group = str(details.get("group", "unknown"))
        from_position = int(details.get("from_position", -1))
        to_position = int(details.get("to_position", -1))
        from_label = position_name(from_position, positions)
        to_label = position_name(to_position, positions)
        before_positions = str(details.get("before_positions", "")).strip()
        after_positions = str(details.get("after_positions", "")).strip()
        if before_positions and after_positions:
            return (
                f"{event_name}: {group} before [{before_positions}]; "
                f"moved {from_label} -> {to_label}; "
                f"after [{after_positions}]"
            )
        return f"{event_name}: {group} moved {from_label} -> {to_label}"

    if event.event_type is EventType.MERCHANT_ADVANCE:
        from_duty = str(details.get("from_duty", "unknown"))
        to_duty = str(details.get("to_duty", "unknown"))
        current_resource = str(details.get("current_resource", "none"))
        return (
            f"{event_name}: {from_duty} -> {to_duty}; "
            f"current resource={current_resource}"
        )

    if event.event_type is EventType.TURN_ADVANCE:
        from_player = str(details.get("from_player", "unknown"))
        to_player = str(details.get("to_player", "unknown"))
        return f"{event_name}: {from_player} -> {to_player}"

    if event.event_type is EventType.ROUND_END:
        round_number = int(details.get("round", 0))
        return f"{event_name}: round {round_number} complete"

    if event.event_type is EventType.ROUND_ADVANCE:
        from_round = int(details.get("from_round", 0))
        to_round = int(details.get("to_round", 0))
        return f"{event_name}: round {from_round} -> {to_round}"

    if event.event_type is EventType.SEASON_END:
        season_number = int(details.get("season", 0))
        return f"{event_name}: season {season_number} complete"

    if event.event_type is EventType.SEASON_ADVANCE:
        from_season = int(details.get("from_season", 0))
        to_season = int(details.get("to_season", 0))
        return f"{event_name}: season {from_season} -> {to_season}"

    return f"{event_name}: {details}"


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
) -> None:
    print(events_heading)
    for event in events:
        formatted = _format_event(event, config)
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

    breakdown = evaluate_root_player(
        next_state,
        root_player_id=root_player_id,
        config=config,
    )
    print()
    print(evaluation_heading)
    for line in _format_evaluation_breakdown(breakdown):
        print(line)


def _format_state_summary(
    state: GameState,
    config: GameConfig,
    *,
    acted_player: PlayerId,
) -> tuple[str, ...]:
    next_active_player = state.active_player
    acted_name = acted_player.name.lower()
    next_name = next_active_player.name.lower()

    lines: list[str] = [
        f"Acted player: {acted_name}",
        f"Next active player: {next_name}",
        "Timing:",
        f"  Absolute turn: {state.timing.absolute_turn}",
        f"  Round: {state.timing.round_number}",
        f"  Season: {state.timing.season_number}",
        f"  Turn in round: {state.timing.turn_in_round}",
        "Merchant:",
        f"  Position: {current_merchant_duty(state, config.merchant)}",
        (
            "  Resource: "
            f"{current_merchant_resource(state, config.merchant) or 'none'}"
        ),
        "Dummy acolytes:",
        (
            "  north_group: "
            f"{format_dummy_acolytes(state.dummy_acolytes.north_group, positions=config.board.positions)}"
        ),
        (
            "  south_group: "
            f"{format_dummy_acolytes(state.dummy_acolytes.south_group, positions=config.board.positions)}"
        ),
        (
            "  total: "
            f"{format_dummy_acolytes(state.dummy_acolytes.total_vector, positions=config.board.positions)}"
        ),
        "",
        "Acted player state:",
        *_format_player_state(state, acted_player, config),
    ]

    if next_active_player is not acted_player:
        lines.extend(
            [
                "",
                "Next active player state:",
                *_format_player_state(state, next_active_player, config),
            ]
        )

    return tuple(lines)


def _format_player_state(
    state: GameState,
    player: PlayerId,
    config: GameConfig,
) -> tuple[str, ...]:
    positions = config.board.positions
    breakdown = evaluate_player(state, player, config)
    player_state = state.player_state(player)
    player_vector = state.player_vector(player)
    mancala = ", ".join(
        f"{position_name(position_id, positions)}={count}"
        for position_id, count in enumerate(player_vector)
    )
    return (
        (
            "Resources: "
            f"stone={breakdown.stone}, "
            f"silver={breakdown.silver}, "
            f"wheat={breakdown.wheat}"
        ),
        f"Piety position: {breakdown.piety_position}",
        f"Piety track VP: {breakdown.piety_track_vp}",
        f"Alms position: {breakdown.alms_position}",
        f"Alms table acolytes: {breakdown.alms_table_acolytes}",
        f"Alms table VP: {breakdown.alms_table_vp}",
        "Workforce:",
        f"  Mancala total: {player_state.workforce.mancala_total}",
        f"  Village: {player_state.workforce.village}",
        f"  Abbey: {player_state.workforce.abbey}",
        (
            "  Committed: "
            f"roads={player_state.workforce.committed.roads}, "
            f"shrines={player_state.workforce.committed.shrines}, "
            f"market_ports={player_state.workforce.committed.market_ports}, "
            f"pilgrimage_sites={player_state.workforce.committed.pilgrimage_sites}, "
            f"alms_table={player_state.workforce.committed.alms_table}"
        ),
        f"  Total: {player_state.workforce.total}",
        f"Mancala: {mancala}",
    )


def _format_evaluation_breakdown(breakdown: EvaluationBreakdown) -> tuple[str, ...]:
    return format_evaluation_breakdown_lines(breakdown)


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
    return tuple(annotated)


def _parse_route(route_text: str) -> tuple[int, ...]:
    if not route_text:
        return ()
    return tuple(int(piece) for piece in route_text.split("->"))


if __name__ == "__main__":
    raise SystemExit(main())
