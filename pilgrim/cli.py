"""CLI entrypoint for scenario validation, action listing, and exact search."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_summary, readable_route
from pilgrim.model.config import GameConfig
from pilgrim.model.enums import EventType, PlayerId, position_name
from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState
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

    if args.command == "solve":
        result = solve_exact(scenario.state, scenario.config, args.depth)
        print(f"Solve result for scenario '{scenario.scenario_id}'")
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
            for index, action in enumerate(result.principal_variation, start=1):
                print(f"{index}. {action_summary(action, scenario.config)}")

        if args.verbose and result.best_action is not None:
            acted_player = scenario.state.active_player
            transition_result = apply_action(scenario.state, result.best_action, scenario.config)
            print()
            print("Events for best first full turn:")
            for event in transition_result.events:
                formatted = _format_event(event, scenario.config)
                if formatted is not None:
                    print(f"* {formatted}")
            print()
            print("State after best first full turn:")
            for line in _format_state_summary(
                transition_result.state,
                scenario.config,
                acted_player=acted_player,
            ):
                print(line)
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
        piety = int(details.get("piety", 0))
        if piety == 0:
            return None
        return f"{event_name}: {actor_name} {piety:+d} piety"

    if event.event_type is EventType.ACOLYTE_RECALL:
        duty_position = int(details.get("duty_position", -1))
        recalled = int(details.get("recalled", 0))
        duty_label = position_name(duty_position, positions)
        return f"{event_name}: recalled {recalled} from {duty_label} to city"

    if event.event_type is EventType.INVARIANT_CHECK:
        if details.get("acolytes_conserved") is True:
            return f"{event_name}: passed (acolytes conserved)"
        return f"{event_name}: {details}"

    return f"{event_name}: {details}"


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
        f"Turn: {state.turn}",
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
    player_state = state.player_state(player)
    player_vector = state.player_vector(player)
    mancala = ", ".join(
        f"{position_name(position_id, positions)}={count}"
        for position_id, count in enumerate(player_vector)
    )
    return (
        (
            "Resources: "
            f"stone={player_state.resources.stone}, "
            f"silver={player_state.resources.silver}, "
            f"wheat={player_state.resources.wheat}"
        ),
        f"Piety: {player_state.piety}",
        f"Mancala: {mancala}",
    )


def _parse_route(route_text: str) -> tuple[int, ...]:
    if not route_text:
        return ()
    return tuple(int(piece) for piece in route_text.split("->"))


if __name__ == "__main__":
    raise SystemExit(main())
