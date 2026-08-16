"""Count legal actions with the Merchant on the cornucopia, to see what the choice costs.

The cornucopia is the first thing that can multiply the branch factor rather than add to it, so
the number matters to search before the rule does. Run it on the same scenario before and after
the choice exists; the difference is what the choice costs.
"""

from __future__ import annotations

from dataclasses import replace

from pilgrim.io.scenarios import load_scenario
from pilgrim.rules.transition import legal_actions

SCENARIO = "scenarios/building_hire_opponent_owned_001.json"


def _with_counter_under_merchant(scenario, value: str):
    name = scenario.config.board.positions[scenario.state.merchant_board_position]
    counters = scenario.config.tithe_counters
    moved = tuple(
        (position, value if position == name else resource)
        for position, resource in counters.counters_by_position
    )
    return replace(
        scenario.config,
        tithe_counters=replace(counters, counters_by_position=moved),
    )


def _with_stock(scenario, *, stone: int, silver: int, wheat: int):
    player = scenario.state.active_player
    player_state = scenario.state.player_state(player)
    resources = replace(player_state.resources, stone=stone, silver=silver, wheat=wheat)
    return scenario.state.with_player_state(player, replace(player_state, resources=resources))


def main() -> int:
    scenario = load_scenario(SCENARIO)
    cases = {
        "all three affordable": dict(stone=5, silver=5, wheat=5),
        "one affordable (wheat only)": dict(stone=0, silver=0, wheat=5),
        "none affordable": dict(stone=0, silver=0, wheat=0),
    }
    for label, stock in cases.items():
        state = _with_stock(scenario, **stock)
        config = _with_counter_under_merchant(scenario, "cornucopia")
        actions = legal_actions(state, config)
        hires = [a for a in actions if getattr(a, "hired_building_id", None) is not None]
        paid_in = sorted(
            {
                resource
                for a in actions
                for _building, resource in a.hire_payments
            }
        )
        print(
            f"{label:30s} total={len(actions):5d}  hire actions={len(hires):4d}  "
            f"paid_in={paid_in or '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
