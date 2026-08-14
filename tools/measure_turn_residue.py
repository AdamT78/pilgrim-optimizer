"""How much of a turn the play view can actually put to a player, on a given board.

The page presents a fixed set of steps and refuses any candidate whose surviving actions still
disagree about something it never asked. That refusal is deliberate, but the size of it is the
backlog, and a backlog nobody measures is a backlog nobody works off. This counts it: how many
candidate turns resolve to one action, how many are refused, and which fields the refusals are
about.

Read the field list off the output rather than off anyone's memory of what is unbuilt. A field
appears here the moment a board makes two actions differ in it, so a scenario that never reaches
the alms tile will not list alms payments and that is the honest answer for that board.

One position or a whole game. A single position answers "can this board be played through the
page", which is the question a PR closing a gap has to answer. Walking on answers "what is left
anywhere", which is the backlog: fields that never come up in the opening turns turn up later, and
a backlog written from the first position would quietly stop at what that position happened to ask.

    python3 tools/measure_turn_residue.py                       # the reference board, first turn
    python3 tools/measure_turn_residue.py scenarios/other.json
    python3 tools/measure_turn_residue.py --turns 30            # play on, and total it up
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO))

from pilgrim.io.scenarios import load_scenario  # noqa: E402
from pilgrim.model.actions import action_id  # noqa: E402
from pilgrim.rules.transition import apply_action, legal_actions  # noqa: E402
from tools.play_server import turn_candidates  # noqa: E402

REFERENCE = "scenarios/play_view_reference_4p_001.json"


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


def measure(scenario_path: str, turns: int = 1) -> dict:
    """Count the candidates over `turns` positions, taking the first settled move between them.

    Which move is taken does not matter to what is being counted, so the first is taken. It has to
    be a SETTLED one: an ambiguous candidate has no action to submit, which is the whole point.
    """
    scenario = load_scenario(scenario_path)
    state = played_through_setup(scenario.state, scenario.config)
    config = scenario.config

    groups = resolving = 0
    by_fields: Counter[tuple[str, ...]] = Counter()
    played = 0
    stopped = "the walk ran to the length asked for"
    for _turn in range(turns):
        candidates = turn_candidates(state, config)
        if not candidates:
            stopped = "the game ended"
            break
        played += 1
        groups += len(candidates)
        for candidate in candidates:
            if candidate["unresolved"]:
                by_fields[tuple(candidate["unresolved"])] += 1
            else:
                resolving += 1
        settled = next((c for c in candidates if c["action_id"] is not None), None)
        if settled is None:
            # A round boundary used to land here: it asks who begins the next round, the page had
            # no way to ask that, and this walked past it by answering on the table's behalf so a
            # backlog would not stop at the first round boundary and report a fifth of the game as
            # the total. The page asks it now, so the boundary is a settled candidate like any
            # other and there is nothing to carry.
            #
            # Not the game ending either. Every move in the position needs something the page
            # cannot ask, so it cannot play on -- a far sharper statement of the backlog than a
            # count.
            blocking = ", ".join(sorted({f for c in candidates for f in c["unresolved"]}))
            stopped = f"nothing in the position was playable; every move needed {blocking}"
            break
        chosen = next(
            a for a in legal_actions(state, config) if action_id(a) == settled["action_id"]
        )
        state = apply_action(state, chosen, config).state

    return {
        "scenario": scenario_path,
        "turns": played,
        "groups": groups,
        "resolving": resolving,
        "ambiguous": groups - resolving,
        "fields": by_fields,
        "stopped": stopped,
    }


def report(result: dict) -> None:
    print(f"board: {result['scenario']}")
    print(f"  turns measured:    {result['turns']}")
    print(f"  groups total:      {result['groups']}")
    print(f"  resolving cleanly: {result['resolving']}")
    print(f"  ambiguous:         {result['ambiguous']}")
    if result["fields"]:
        print("  fields remaining:")
        for fields, count in sorted(result["fields"].items(), key=lambda pair: -pair[1]):
            print(f"    {', '.join(fields):58} {count} group(s)")
    else:
        print("  fields remaining:  none")
    print(f"  stopped because:   {result['stopped']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default=REFERENCE)
    parser.add_argument("--turns", type=int, default=1, help="how many positions to walk")
    parsed = parser.parse_args(argv)
    report(measure(parsed.scenario, parsed.turns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
