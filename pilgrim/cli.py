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
from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import GameAction, SetupSowAction, action_summary, readable_route
from pilgrim.model.config import GameConfig
from pilgrim.model.dummy import format_dummy_acolytes
from pilgrim.model.duties import DUTY_POSITIONS
from pilgrim.model.enums import EventType, PlayerId, position_name
from pilgrim.model.events import GameEvent
from pilgrim.model.state import GameState
from pilgrim.rules.buildings import (
    available_player_board_slots,
    building_names_for_ids,
    used_player_board_slots,
)
from pilgrim.rules.merchant import current_merchant_duty, current_merchant_resource
from pilgrim.rules.special_activities import format_special_activities
from pilgrim.rules.transition import apply_action, legal_actions
from pilgrim.rules.validation import validate_state_invariants
from pilgrim.search.exact import solve_exact
from pilgrim.setup.generator import generate_setup_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilgrim")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a JSON scenario.")
    validate_parser.add_argument("scenario", help="Path to scenario JSON file.")

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
            if transition_result.state.game_over:
                print("Next active player: none (game over)")
            else:
                print(f"Next active player: {transition_result.state.active_player.name.lower()}")
            print(f"Game over: {str(transition_result.state.game_over).lower()}")
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

        best_action_heading = "Best first full turn:"
        events_heading = "Events for best first full turn:"
        state_heading = "State after best first full turn:"
        evaluation_heading = "Root-player evaluation after best first full turn:"
        if isinstance(result.best_action, SetupSowAction):
            best_action_heading = "Best first setup sow:"
            events_heading = "Events for best first setup sow:"
            state_heading = "State after best first setup sow:"
            evaluation_heading = "Root-player evaluation after best first setup sow:"

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
                events_heading=events_heading,
                state_heading=state_heading,
                evaluation_heading=evaluation_heading,
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

    if event.event_type is EventType.SETUP_SOWING:
        source = int(details.get("source", -1))
        picked_up = details.get("picked_up", "?")
        route_names = str(details.get("route_names", "")).strip()
        if not route_names:
            route_text = str(details.get("route", ""))
            route = _parse_route(route_text)
            route_names = readable_route(source, route, positions=positions)
        return (
            f"{event_name}: {actor_name} picked up {picked_up} from "
            f"{position_name(source, positions)}; route {route_names}"
        )

    if event.event_type is EventType.SETUP_SOW_COMPLETE:
        player_name = str(details.get("player", actor_name))
        return f"{event_name}: {player_name} completed setup sow"

    if event.event_type is EventType.SETUP_PLAYER_ADVANCE:
        from_player = str(details.get("from_player", actor_name))
        to_player = str(details.get("to_player", "unknown"))
        return f"{event_name}: {from_player} -> {to_player}"

    if event.event_type is EventType.SETUP_COMPLETE:
        start_player = str(details.get("start_player", "unknown"))
        return (
            f"{event_name}: all players completed setup sow; "
            f"normal play begins with {start_player}"
        )

    if event.event_type is EventType.DUTY_RESOLUTION:
        duty_position = details.get("duty_position")
        duty_label = (
            position_name(int(duty_position), positions)
            if isinstance(duty_position, int)
            else "unknown"
        )
        duty_category = str(details.get("duty_category", "")).strip()
        duty_with_category = (
            f"{duty_label} ({duty_category})" if duty_category else duty_label
        )
        if details.get("mode") == "tithe":
            return f"{event_name}: selected {duty_with_category}; mode tithe"
        fragments = [f"selected {duty_with_category}"]
        if "strength" in details:
            fragments.append(f"relation {details['strength']}")
        if "duty_value" in details:
            fragments.append(f"duty value {details['duty_value']}")
        if "effective_duty_value" in details:
            effective_duty_value = int(details["effective_duty_value"])
            base_duty_value = int(details.get("duty_value", effective_duty_value))
            if effective_duty_value != base_duty_value:
                fragments.append(f"effective duty value {effective_duty_value}")
        if "silver_cost" in details:
            fragments.append(f"silver cost {details['silver_cost']}")
        if "effect" in details:
            fragments.append(f"action {details['effect']}")
        return f"{event_name}: {'; '.join(fragments)}"

    if event.event_type is EventType.DUTY_DEFERRED:
        scaffold = str(details.get("scaffold", "")).strip()
        effective_duty_value = details.get("effective_duty_value")
        spent = details.get("spent")
        if scaffold:
            if isinstance(effective_duty_value, int) and spent is False:
                return (
                    f"{event_name}: {scaffold}; effective duty value "
                    f"{effective_duty_value} not spent in this scaffold"
                )
            return f"{event_name}: {scaffold}"
        return f"{event_name}: {details}"

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
                conserved_label = (
                    "serfs/acolytes conserved"
                    if details.get("serfs_non_negative") is True
                    else "acolytes conserved"
                )
                return (
                    f"{event_name}: passed for all players "
                    f"({conserved_label}; total workforce by player: "
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

    if event.event_type is EventType.BUILDING_DONATION:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        donated_label = building_name if building_name else building_id
        donation_vp = int(details.get("donation_vp", 0))
        return f"{event_name}: {actor_name} donated {donated_label}; donation_vp={donation_vp}"

    if event.event_type is EventType.BUILDING_CONSTRUCTED:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        built_label = building_name if building_name else building_id
        source = str(details.get("source", "market"))
        level = int(details.get("level", 0))
        stone_cost = int(details.get("stone_cost", 0))
        active_count = int(details.get("active_buildings_count", 0))
        used_slots = int(details.get("used_slots", 0))
        slot_limit = int(details.get("slot_limit", 0))
        text = (
            f"{event_name}: {actor_name} constructed {built_label} from {source}; "
            f"level {level}; cost stone {stone_cost}; active buildings now {active_count}"
        )
        if slot_limit > 0:
            text += f"; used slots {used_slots}/{slot_limit}"
        else:
            text += f"; used slots {used_slots}"
        return text

    if event.event_type is EventType.ORDINATION:
        step = str(details.get("step", "")).strip()
        amount = int(details.get("amount", 1))
        from_pool = str(details.get("from_pool", "unknown"))
        to_pool = str(details.get("to_pool", "unknown"))
        wheat_paid = int(details.get("wheat_paid", 1))
        if step == "ordain":
            return (
                f"{event_name}: {actor_name} ordained {amount} serf {from_pool} -> {to_pool}; "
                f"paid wheat={wheat_paid}"
            )
        if step == "mission":
            return (
                f"{event_name}: {actor_name} sent {amount} acolyte {from_pool} -> {to_pool}; "
                f"paid wheat={wheat_paid}"
            )
        return (
            f"{event_name}: {actor_name} step={step} moved {amount} {from_pool} -> {to_pool}; "
            f"paid wheat={wheat_paid}"
        )

    if event.event_type is EventType.TAXATION:
        step = str(details.get("step", "")).strip()
        if step == "step_1":
            resource = str(details.get("resource", "unknown"))
            return f"{event_name}: {actor_name} took step 1 resource {resource}"
        if step == "step_2":
            no_bonus = bool(details.get("no_bonus", False))
            resources_csv = str(details.get("resources", "")).strip()
            if no_bonus or not resources_csv:
                return (
                    f"{event_name}: {actor_name} had no other majority duty tiles; no bonus resources"
                )
            resources_text = ", ".join(
                resource for resource in resources_csv.split(",") if resource
            )
            return (
                f"{event_name}: {actor_name} took bonus resources {resources_text} "
                "from other majority duty tiles"
            )
        return f"{event_name}: {actor_name} {details}"

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

    if event.event_type is EventType.ALLOCATION:
        from_pool = str(details.get("from_pool", "unknown"))
        to_pool = str(details.get("to_pool", "unknown"))
        amount = int(details.get("amount", 0))
        return f"{event_name}: {actor_name} moved {amount} acolyte {from_pool} -> {to_pool}"

    if event.event_type is EventType.BUILDING_BONUS:
        building = str(details.get("building", "unknown"))
        action_name = str(details.get("action", "unknown"))
        bonuses: list[str] = []
        if "wheat_bonus" in details:
            bonuses.append(f"wheat +{int(details['wheat_bonus'])}")
        if "stone_bonus" in details:
            bonuses.append(f"stone +{int(details['stone_bonus'])}")
        if "silver_bonus" in details:
            bonuses.append(f"silver +{int(details['silver_bonus'])}")
        if "piety_bonus" in details:
            bonuses.append(f"piety +{int(details['piety_bonus'])}")
        if bonuses:
            return f"{event_name}: {building} added {', '.join(bonuses)} to {action_name}"
        return f"{event_name}: {building} applied to {action_name}"

    if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS:
        activity = str(details.get("activity", "unknown"))
        action_name = str(details.get("action", "unknown"))
        if activity == "alms_house" and "duty_value_bonus" in details:
            text = f"{event_name}: {activity} applied to {action_name}"
            text += f"; duty value +{int(details['duty_value_bonus'])}"
            if "extra_silver" in details or "extra_wheat" in details:
                text += (
                    "; paid extra "
                    f"silver={int(details.get('extra_silver', 0))}, "
                    f"wheat={int(details.get('extra_wheat', 0))}"
                )
            return text
        if activity == "road_engineer" and details.get("construct_extra_road") is True:
            return (
                f"{event_name}: road_engineer allowed one additional road for construct "
                "because a road was included in the plan"
            )
        bonuses: list[str] = []
        if "wheat_bonus" in details:
            bonuses.append(f"wheat +{int(details['wheat_bonus'])}")
        if "stone_bonus" in details:
            bonuses.append(f"stone +{int(details['stone_bonus'])}")
        if "silver_bonus" in details:
            bonuses.append(f"silver +{int(details['silver_bonus'])}")
        if "piety_bonus" in details:
            bonuses.append(f"piety +{int(details['piety_bonus'])}")
        if "duty_value_bonus" in details:
            bonuses.append(f"duty value +{int(details['duty_value_bonus'])}")
        if bonuses:
            text = f"{event_name}: {activity} added {', '.join(bonuses)} to {action_name}"
        else:
            text = f"{event_name}: {activity} applied to {action_name}"
        if "extra_silver" in details or "extra_wheat" in details:
            text += (
                "; paid extra "
                f"silver={int(details.get('extra_silver', 0))}, "
                f"wheat={int(details.get('extra_wheat', 0))}"
            )
        return text

    if event.event_type is EventType.EXCESS_CHECK:
        if details.get("no_excess") is True:
            return f"{event_name}: no excess resources"
        return f"{event_name}: {details}"

    if event.event_type is EventType.EXCESS_DISCARD:
        player = str(details.get("player", "unknown"))
        resource = str(details.get("resource", "unknown"))
        before = int(details.get("before", 0))
        after = int(details.get("after", 0))
        returned = int(details.get("returned", max(before - after, 0)))
        return (
            f"{event_name}: {player} {resource} {before} -> {after}; "
            f"returned {returned} to supply"
        )

    if event.event_type is EventType.SHIP_ADVANCE:
        from_position = int(details.get("from_position", -1))
        to_position = int(details.get("to_position", -1))
        pilgrimage = bool(details.get("at_pilgrimage_site", False))
        nw_site = bool(details.get("at_nw_pilgrimage_site", False))
        return (
            f"{event_name}: {from_position} -> {to_position}; "
            f"pilgrimage_site={str(pilgrimage).lower()}; "
            f"nw_site={str(nw_site).lower()}"
        )

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

    if event.event_type is EventType.TRADE_ROUTE_INCOME_SKIPPED:
        return f"{event_name}: trade routes not implemented"

    if event.event_type is EventType.START_PLAYER_TIE_BREAK:
        tied_players = str(details.get("tied_players", ""))
        current_start = str(details.get("current_start_player", "unknown"))
        deciding_player = str(details.get("deciding_player", "unknown"))
        tied_labels = ", ".join(tied_players.split(",")) if tied_players else "none"
        return (
            f"{event_name}: tied players [{tied_labels}]; "
            f"current start player {current_start}; deciding player {deciding_player}"
        )

    if event.event_type is EventType.START_PLAYER_SELECTION:
        deciding_player = str(details.get("deciding_player", "unknown"))
        selected_player = str(details.get("selected_start_player", "unknown"))
        return (
            f"{event_name}: {deciding_player} selected {selected_player} "
            f"as next start player"
        )

    if event.event_type is EventType.GAME_END:
        reason = str(details.get("reason", "")).strip()
        if reason:
            return f"{event_name}: {reason}"
        return f"{event_name}: game over"

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
    next_name = (
        "none (game over)"
        if state.game_over
        else next_active_player.name.lower()
    )
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

    lines: list[str] = [
        f"Acted player: {acted_name}",
        f"Next active player: {next_name}",
        "Timing:",
        f"  Absolute turn: {state.timing.absolute_turn}",
        f"  Round: {state.timing.round_number}",
        f"  Season: {state.timing.season_number}",
        f"  Turn in round: {state.timing.turn_in_round}",
        f"  Start player: {state.start_player.name.lower()}",
        f"  Game over: {str(state.game_over).lower()}",
        *setup_lines,
        "Ship:",
        f"  Position: {state.ship_position}",
        (
            "  At pilgrimage site: "
            f"{str(config.ship.is_pilgrimage_site(state.ship_position)).lower()}"
        ),
        (
            "  At NW pilgrimage site: "
            f"{str(config.ship.is_nw_site(state.ship_position)).lower()}"
        ),
        "Merchant:",
        f"  Position: {current_merchant_duty(state, config.merchant)}",
        (
            "  Resource: "
            f"{current_merchant_resource(state, config.merchant) or 'none'}"
        ),
        "Duty tiles:",
        *_format_duty_tiles_layout(config),
        "Building market:",
        f"  Level 1: {_market_building_names_for_level(state, config, 1)}",
        f"  Level 2: {_market_building_names_for_level(state, config, 2)}",
        f"  Level 3: {_market_building_names_for_level(state, config, 3)}",
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


def _format_duty_tiles_layout(config: GameConfig) -> tuple[str, ...]:
    duty_tiles = config.duty_tiles_mapping()
    return tuple(
        f"  {position_name}: {duty_tiles[position_name]}"
        for position_name in DUTY_POSITIONS
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
        generated[field_name] = Path(
            os.path.relpath(absolute_path, output_dir)
        ).as_posix()


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
        position
        for position, category in duty_tiles.items()
        if category == "taxation"
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
    return (
        f"Generated setup scenario: {output_path.as_posix()}",
        f"Players: {player_count}",
        f"Seed: {seed}",
        f"Duty tiles: {duty_layout}",
        f"Taxation tile: {taxation_tile}",
        f"Tithe counters: {len(tithe_counters)} counters; taxation has none",
        f"Building market: {len(building_market)} buildings",
        f"Dummy acolytes: {player_count}-player setup",
        f"Setup sow required: {setup_sow_required}",
    )


if __name__ == "__main__":
    raise SystemExit(main())
