"""How much of a turn the play view can put to a player, and how much of the game was looked at.

The page presents a fixed set of steps and refuses any candidate whose surviving actions still
disagree about something it never asked. That refusal is deliberate, but the size of it is the
backlog, and a backlog nobody measures is a backlog nobody works off. This counts it.

WHY THERE ARE TWO NUMBERS AND NOT ONE. A count of refusals on its own cannot be read. Zero refused
means either "there is nothing left to present" or "this walk never went anywhere that would have
asked", and those are opposite conclusions from the same figure. The reference board reported zero
while a generated board reported 616 refusals across five fields that had never once been offered
to it -- and nothing in the output said so, so the zero was believed.

So every run reports COVERAGE beside residue: for each field, each resolution and each duty
category, whether it was ever put to the page at all. A run that ends "0 refused, 23 fields never
offered" is honest. A run that ends "0 refused" is the thing that misled us.

FOUR STATES PER FIELD, and the middle two are the point:

    refused          it came up and the page could not answer it            -- the backlog
    asked            the page has an affordance and used it                 -- genuinely covered
    never a question it came up, the page has no affordance, and no group   -- covered by luck
                     ever needed it decided
    never offered    no visited position ever put a value on it             -- not evidence

"Never a question" is not folded into "asked", though both look clean from the outside. A field
with no affordance that happens never to split a group is one board away from being a refusal, and
calling that covered would be the same conflation this tool exists to undo.

WHAT "OFFERED" MEANS, exactly: a field is offered once some visited position's legal actions carry
a value for it other than the one its dataclass declares as the default. The one thing this misses
is a field whose only live value IS its default -- an alms payment of zero silver, say -- which
reads as never offered. Named here rather than worked around, because the alternative readings all
cost more than they buy.

TWO AXES, NOT ONE. Which fields a walk meets depends on the board AND on the line of play through
it: all eight duties exist on every board, and what differs is which ones a line selects. Seeds
sample the first axis only. `--policy coverage` samples the second, by preferring at each turn a
resolution it has taken least often.

    python3 tools/measure_turn_residue.py                       # the reference board, first turn
    python3 tools/measure_turn_residue.py --turns 40
    python3 tools/measure_turn_residue.py --turns 40 --policy coverage
    python3 tools/measure_turn_residue.py --sweep               # several boards, union reported
    python3 tools/measure_turn_residue.py --sweep --full        # the long one; see --sweep output
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO))

from pilgrim.io.scenarios import load_scenario  # noqa: E402
from pilgrim.model.actions import EndTurnAction, FullTurnAction, action_id  # noqa: E402
from pilgrim.model.duties import DUTY_CATEGORIES, duty_category_at_position  # noqa: E402
from pilgrim.model.enums import TurnResolutionType  # noqa: E402
from pilgrim.rules.transition import apply_action, legal_actions  # noqa: E402
from pilgrim.setup.generator import generate_setup_scenario  # noqa: E402
from tools.play_server import (  # noqa: E402
    DECIDED_FIELDS,
    _covered_fields,
    _hire_contexts,
    _resolution_context_key,
    turn_candidates,
)

REFERENCE = "scenarios/play_view_reference_4p_001.json"

CONFIG_PATH_FIELDS: tuple[str, ...] = (
    "board_file",
    "duties_file",
    "piety_file",
    "alms_file",
    "timing_file",
    "merchant_file",
    "ship_file",
    "buildings_file",
)

# Not chosen for interest. The first is the board every other measurement in this repo quotes, and
# the rest are the smallest spread that touches each supported table size more than once, so a
# field reached on one and not another shows up as a difference rather than as an absence.
SWEEP_SEEDS: tuple[int, ...] = (7, 99)
FULL_SWEEP_SEEDS: tuple[int, ...] = (7, 42, 99, 2024, 31337)
PLAYER_COUNTS: tuple[int, ...] = (2, 3, 4)

# WHY A FIELD IS STILL NEVER OFFERED, which is the backlog and is more use than any count here.
#
# Read this against how buildings reach a game at all. The catalogue holds 24; a setup deals 12,
# four of the eight at each level, so any one building is on any one board with probability a half.
# Being dealt is not enough either: a market building is only hireable from its live round, which
# is gated behind the matching pilgrimage site, and several abilities are refused to a hirer and
# offered only to a seat that CONSTRUCTED the thing. So a walk misses these for one of two reasons,
# and it is worth knowing which: the board never held the building, or it held it and the line of
# play never paid for it. More seeds fix the first. Only a policy that reasons about what to build
# would fix the second, and this tool does not have one.
#
# None of it is dead code. Every field below has a live branch in the enumerator; each is quoted
# with the condition that would open it.
WHY_NOT_REACHED: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "sow_route_building_id",
            "sow_route_building_source",
            "sow_route_secondary_building_id",
            "sow_route_secondary_building_source",
            "sow_route_omitted_location",
        ),
        "kogge or cloisters in reach; kogge also needs the sow to set out from the city, and the"
        " secondary fields need both at once",
    ),
    (
        (
            "bank_payment_building_id",
            "bank_payment_building_source",
            "bank_payment_replaced_resource",
            "bank_payment_silver_amount",
        ),
        "bank in reach, on a construct or ordination whose stone, wheat or piety cost silver can"
        " stand in for, and no other modifier on the same turn",
    ),
    (
        ("effective_acolyte_building_id", "effective_acolyte_building_source"),
        "scriptorium in reach, on any resolution other than a tithe or a building donation",
    ),
    (
        ("taxation_majority_building_id", "taxation_majority_building_source"),
        "customs_house in reach, on a taxation resolution specifically",
    ),
    (
        (
            "free_hire_enabler_building_id",
            "free_hire_target_building_id",
            "free_hire_target_building_source",
        ),
        "wagon_yard CONSTRUCTED onto your own board -- hiring it does not open the ability -- and a"
        " second building to take for free",
    ),
    (
        ("workforce_move_building_id", "workforce_move_building_source"),
        "pulpit in reach and a village worker to send to the abbey",
    ),
    (
        (
        ),
        "library in reach, and an acolyte still in the city once the turn has resolved",
    ),
    (
        ("donate_building_id",),
        "a building already constructed onto your own board, then a give_alms duty to give it away",
    ),
    (
        ("construct_plan",),
        "a construct duty worth two or more, or a road_engineer to split the plan into variants;"
        " below that there is one plan and nothing to decide",
    ),
)

REFUSED = "refused"
ASKED = "asked"
NEVER_A_QUESTION = "never a question"
NEVER_OFFERED = "never offered"

# Worst first. A field is reported at the worst state it ever reached, because one position that
# could not be played is the fact worth carrying -- a field refused on one board and asked on
# another is not covered, it is a coin toss.
STATE_ORDER: tuple[str, ...] = (REFUSED, ASKED, NEVER_A_QUESTION, NEVER_OFFERED)

TURN_FIELDS: tuple[str, ...] = tuple(
    field.name for field in dataclasses.fields(FullTurnAction) if field.name != "action_type"
)
FIELD_DEFAULTS: dict[str, Any] = {
    field.name: (
        field.default
        if field.default is not dataclasses.MISSING
        else (field.default_factory() if field.default_factory is not dataclasses.MISSING else None)
    )
    for field in dataclasses.fields(FullTurnAction)
}


def played_through_setup(state, config):
    """Fast-forward to the first normal turn.

    The reference board is a generated setup, where no duty is resolved and so no residue exists.
    Measuring it as loaded would report a clean sheet for a page that has not been asked anything
    yet. Which setup sow is taken does not matter to the measurement, so the first is taken.
    """
    while True:
        actions = legal_actions(state, config)
        if not actions or any(getattr(a, "resolution", None) is not None for a in actions):
            return state
        state = apply_action(state, actions[0], config).state


def _resolution_of(candidate: dict) -> str | None:
    """Which resolution a candidate answers, read off its steps rather than off an action."""
    for step in candidate["steps"]:
        if step["kind"] == "resolution":
            return str(step["value"])
    return None


def _pick(candidate_pairs: list[tuple[dict, str]], policy: str, taken: Counter[str]) -> dict:
    """Which settled candidate the walk takes next.

    `first` takes the first settled candidate, which is what this tool always did. It is not a
    neutral choice -- it follows whatever line `legal_actions` happens to enumerate first, and that
    line is why the reference board never met an ordination in forty turns.

    `coverage` prefers a candidate whose resolution has been taken least often, so the walk spreads
    across the eight duties rather than falling down one of them. It is not a search: it does not
    look ahead, and it cannot construct an asset a field is gated behind.

    THE TIE-BREAK IS THE ACTION ID, lexicographically, and never anything random. A measurement
    whose numbers move between two runs of the same command cannot be used to say a change made
    things better, which is the only thing anyone would want it for. The id is used rather than the
    candidate's position in the list because position depends on enumeration order, and the point
    of the tie-break is to survive that changing.
    """
    if policy == "first":
        return candidate_pairs[0][0]
    return min(
        candidate_pairs,
        key=lambda pair: (taken[_resolution_of(pair[0]) or ""], pair[1]),
    )[0]


def measure(scenario_path: str, turns: int = 1, policy: str = "first") -> dict:
    """Walk `turns` positions, counting what was refused and recording what was ever offered."""
    scenario = load_scenario(scenario_path)
    state = played_through_setup(scenario.state, scenario.config)
    config = scenario.config

    groups = resolving = 0
    by_fields: Counter[tuple[str, ...]] = Counter()
    field_state: dict[str, str] = {name: NEVER_OFFERED for name in TURN_FIELDS}
    resolutions_seen: Counter[str] = Counter()
    duties_seen: Counter[str] = Counter()
    taken: Counter[str] = Counter()
    played = 0
    stopped = "the walk ran to the length asked for"

    def worsen(name: str, worse: str) -> None:
        # Fields belonging to the other action types go by. A start-player selection carries
        # `chosen_start_player` and a Confession Box answer carries `use` -- both presented, both
        # real, and neither of them a field of the turn this table is about.
        if name not in field_state:
            return
        if STATE_ORDER.index(worse) < STATE_ORDER.index(field_state[name]):
            field_state[name] = worse

    for _turn in range(turns):
        candidates = turn_candidates(state, config, include_preview_effects=False)
        if not candidates:
            stopped = "the game ended"
            break
        played += 1
        groups += len(candidates)

        actions = legal_actions(state, config)
        by_id = {action_id(action): action for action in actions}
        hire_contexts = _hire_contexts(list(actions), config)
        offer_hire_by_action_id = {
            action_id(action): (
                isinstance(action, FullTurnAction)
                and _resolution_context_key(action, config) in hire_contexts
            )
            for action in actions
        }
        for action in actions:
            if not isinstance(action, FullTurnAction):
                continue
            resolutions_seen[action.resolution.value] += 1
            duties_seen[duty_category_at_position(config, action.selected_duty)] += 1
            for name in TURN_FIELDS:
                if getattr(action, name) != FIELD_DEFAULTS[name]:
                    worsen(name, NEVER_A_QUESTION)

        for candidate in candidates:
            if candidate["unresolved"]:
                by_fields[tuple(candidate["unresolved"])] += 1
                for name in candidate["unresolved"]:
                    worsen(name, REFUSED)
            else:
                resolving += 1
            # Read off the steps that were really emitted, so a field the page could ask about in
            # principle but did not ask about here is not credited with having been asked.
            answered = candidate["action_id"]
            if answered is not None:
                for name in _covered_fields(
                    by_id[answered],
                    state,
                    config,
                    offer_hire=offer_hire_by_action_id[answered],
                    include_preview_effects=False,
                ):
                    worsen(name, ASKED)
            # The four the page opens with -- origin, route, duty, resolution -- are asked of every
            # turn there is, which is why they are excluded from the residue and so from
            # `_covered_fields`. Left out of this table they would read as never asked, which is
            # the opposite of true and would be its own small version of the lie above.
            for name in DECIDED_FIELDS:
                worsen(name, ASKED)

        settled = [
            (candidate, candidate["action_id"])
            for candidate in candidates
            if candidate["action_id"] is not None
        ]
        if not settled:
            # Not the game ending. Every move in the position needs something the page cannot ask,
            # so it cannot play on -- a far sharper statement of the backlog than a count.
            blocking = ", ".join(sorted({f for c in candidates for f in c["unresolved"]}))
            stopped = f"nothing in the position was playable; every move needed {blocking}"
            break
        chosen_candidate = _pick(settled, policy, taken)
        resolution = _resolution_of(chosen_candidate)
        if resolution is not None:
            taken[resolution] += 1
        resolution = apply_action(state, by_id[chosen_candidate["action_id"]], config)
        state = resolution.state
        if state.turn_progress.resolution_committed:
            state = apply_action(state, EndTurnAction(), config).state

    return {
        "scenario": scenario_path,
        "policy": policy,
        "turns": played,
        "groups": groups,
        "resolving": resolving,
        "ambiguous": groups - resolving,
        "fields": by_fields,
        "field_state": field_state,
        "resolutions_seen": resolutions_seen,
        "duties_seen": duties_seen,
        "stopped": stopped,
    }


def generated_board(player_count: int, seed: int, into: Path) -> str:
    """One generated board, written where a scenario can be loaded from it."""
    generated = generate_setup_scenario(player_count=player_count, seed=seed)
    for field in CONFIG_PATH_FIELDS:
        generated[field] = str((REPO / str(generated[field])).resolve())
    path = into / f"generated_{player_count}p_seed{seed}.json"
    path.write_text(json.dumps(generated))
    return str(path)


def sweep(turns: int, policy: str, seeds: tuple[int, ...]) -> dict:
    """Every board in the sweep, measured separately and then unioned.

    The union is taken at the WORST state each field reached anywhere. A field asked on one board
    and refused on another is refused: the page cannot play the game, it can play that board.
    """
    with tempfile.TemporaryDirectory() as workspace:
        into = Path(workspace)
        boards = [(REFERENCE, "reference 4p")]
        boards += [
            (generated_board(players, seed, into), f"generated {players}p seed {seed}")
            for players in PLAYER_COUNTS
            for seed in seeds
        ]
        started = time.monotonic()
        results = [(label, measure(path, turns, policy)) for path, label in boards]
        elapsed = time.monotonic() - started

    union_fields: dict[str, str] = {name: NEVER_OFFERED for name in TURN_FIELDS}
    union_by_fields: Counter[tuple[str, ...]] = Counter()
    union_resolutions: Counter[str] = Counter()
    union_duties: Counter[str] = Counter()
    for _label, result in results:
        for name, state in result["field_state"].items():
            if STATE_ORDER.index(state) < STATE_ORDER.index(union_fields[name]):
                union_fields[name] = state
        union_by_fields.update(result["fields"])
        union_resolutions.update(result["resolutions_seen"])
        union_duties.update(result["duties_seen"])

    return {
        "policy": policy,
        "turns": turns,
        "seeds": seeds,
        "boards": results,
        "groups": sum(result["groups"] for _label, result in results),
        "resolving": sum(result["resolving"] for _label, result in results),
        "ambiguous": sum(result["ambiguous"] for _label, result in results),
        "fields": union_by_fields,
        "field_state": union_fields,
        "resolutions_seen": union_resolutions,
        "duties_seen": union_duties,
        "seconds": elapsed,
    }


def _coverage_table(field_state: dict[str, str]) -> None:
    """Every field on the action, not only the ones that happened to turn up."""
    print("  per-field coverage (every field on FullTurnAction):")
    for state in STATE_ORDER:
        named = [name for name in TURN_FIELDS if field_state[name] == state]
        print(f"    {state:16} {len(named):>3}  {', '.join(named) if named else '--'}")


def _backlog(field_state: dict[str, str]) -> None:
    """What was never offered, grouped by what would have to happen for it to be.

    Printed here rather than left for a reader to work out, because "26 fields never offered" is a
    number and "the board never held a bank" is a thing somebody can go and do something about.
    """
    unreached = {name for name in TURN_FIELDS if field_state[name] == NEVER_OFFERED}
    if not unreached:
        print("  nothing went unoffered")
        return
    print("  what would have to happen for the unoffered ones:")
    for names, reason in WHY_NOT_REACHED:
        wanting = [name for name in names if name in unreached]
        if wanting:
            print(f"    {', '.join(wanting)}\n      needs {reason}")
    unexplained = unreached - {name for names, _ in WHY_NOT_REACHED for name in names}
    if unexplained:
        print(
            f"    {', '.join(sorted(unexplained))}\n      needs an explanation nobody has written"
        )


def _seen_table(label: str, seen: Counter[str], everything: tuple[str, ...]) -> None:
    missing = [name for name in everything if name not in seen]
    print(f"  {label}: {len(seen)}/{len(everything)} offered")
    if missing:
        print(f"    never offered:  {', '.join(missing)}")


def report(result: dict) -> None:
    print(f"board: {result['scenario']}")
    print(f"  walk policy:       {result['policy']}")
    print(f"  turns measured:    {result['turns']}")
    print(f"  groups total:      {result['groups']}")
    print(f"  resolving cleanly: {result['resolving']}")
    print(f"  ambiguous:         {result['ambiguous']}")
    if result["fields"]:
        print("  refused about:")
        for fields, count in sorted(result["fields"].items(), key=lambda pair: -pair[1]):
            print(f"    {', '.join(fields):58} {count} group(s)")
    else:
        print("  refused about:     nothing")
    _coverage_table(result["field_state"])
    _seen_table(
        "resolutions",
        result["resolutions_seen"],
        tuple(member.value for member in TurnResolutionType),
    )
    _seen_table("duty categories", result["duties_seen"], DUTY_CATEGORIES)
    _backlog(result["field_state"])
    print(f"  stopped because:   {result['stopped']}")


def report_sweep(result: dict) -> None:
    print(f"sweep: {len(result['boards'])} boards, {result['turns']} turns each")
    print(f"  walk policy:       {result['policy']}")
    print(f"  seeds:             {', '.join(str(seed) for seed in result['seeds'])}")
    print(f"  ran in:            {result['seconds']:.1f}s")
    print()
    print(f"  {'board':32} {'groups':>8} {'clean':>8} {'refused':>8}")
    for label, board in result["boards"]:
        print(f"  {label:32} {board['groups']:>8} {board['resolving']:>8} {board['ambiguous']:>8}")
    print(f"  {'UNION':32} {result['groups']:>8} {result['resolving']:>8} {result['ambiguous']:>8}")
    print()
    if result["fields"]:
        print("  refused about, across the sweep:")
        for fields, count in sorted(result["fields"].items(), key=lambda pair: -pair[1]):
            print(f"    {', '.join(fields):58} {count} group(s)")
    else:
        print("  refused about:     nothing")
    _coverage_table(result["field_state"])
    _seen_table(
        "resolutions",
        result["resolutions_seen"],
        tuple(member.value for member in TurnResolutionType),
    )
    _seen_table("duty categories", result["duties_seen"], DUTY_CATEGORIES)
    _backlog(result["field_state"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default=REFERENCE)
    parser.add_argument("--turns", type=int, default=1, help="how many positions to walk")
    parser.add_argument(
        "--policy",
        choices=("first", "coverage"),
        default="first",
        help="which settled candidate the walk takes; see _pick",
    )
    parser.add_argument("--sweep", action="store_true", help="walk several boards and union them")
    parser.add_argument(
        "--full",
        action="store_true",
        help=f"sweep {len(FULL_SWEEP_SEEDS)} seeds instead of {len(SWEEP_SEEDS)}",
    )
    parsed = parser.parse_args(argv)
    if parsed.sweep:
        turns = parsed.turns if parsed.turns > 1 else 40
        report_sweep(sweep(turns, parsed.policy, FULL_SWEEP_SEEDS if parsed.full else SWEEP_SEEDS))
    else:
        report(measure(parsed.scenario, parsed.turns, parsed.policy))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
