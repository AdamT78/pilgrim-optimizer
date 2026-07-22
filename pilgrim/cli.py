"""CLI entrypoint for scenario validation, action listing, and exact search."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from pilgrim.io.scenarios import load_scenario
from pilgrim.model.actions import action_id
from pilgrim.rules.transition import legal_actions
from pilgrim.rules.validation import validate_state_invariants
from pilgrim.search.exact import solve_exact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilgrim")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a JSON scenario.")
    validate_parser.add_argument("scenario", help="Path to scenario JSON file.")

    legal_parser = subparsers.add_parser("legal-actions", help="List legal action IDs.")
    legal_parser.add_argument("scenario", help="Path to scenario JSON file.")

    solve_parser = subparsers.add_parser("solve", help="Run placeholder exact search.")
    solve_parser.add_argument("scenario", help="Path to scenario JSON file.")
    solve_parser.add_argument("--depth", type=int, default=3, help="Search depth (default: 3).")
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
        for action in actions:
            print(action_id(action))
        return 0

    if args.command == "solve":
        result = solve_exact(scenario.state, scenario.config, args.depth)
        print(f"best_score={result.best_score}")
        print(f"best_action={result.best_action_id or 'none'}")
        print(f"nodes_expanded={result.nodes_expanded}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
