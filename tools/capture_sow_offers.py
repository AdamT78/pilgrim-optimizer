#!/usr/bin/env python3
"""Capture what the engine OFFERS during one turn's sow, so a page can draw it without deciding it.

ON THIS SIDE OF THE SEAM ON PURPOSE. It lived under tools/ui_debug until CI caught it:
`test_no_page_of_the_ui_reaches_for_the_engines_state_or_rules` forbids anything there from
importing the engine, and this imports `pilgrim.rules.transition` itself. The rule is right
and the file was on the wrong side of it -- the whole point of a dict crossing the seam is
that only one side knows the engine, and this IS that side: it is the thing that writes the
dict. It sits in tools/ beside capture_legal_actions.py and the rest, and what it writes is
all the drawing side ever sees.

WHY THIS EXISTS. generate_duty_sow.py used to work out for itself which tiles a player
could sow onto. THE RULE IT REPLACED WAS NOT WRONG, AND THE FIRST VERSION OF THIS NOTE SAID IT WAS.
`legal()` answered "a neighbour of where I am, with space", composed from the real board graph,
and measured against the PLAIN sow it agreed everywhere testable -- city offers north and south,
south_east offers south, west offers city and north_west, on both scenarios, and the tiles you
may lift from matched too. The claim that the engine offered nine from the city came from this
recorder unioning across turns that HIRE Kogge or Cloisters, which reach further. That was a
fault in the projection, not in the page.

It was replaced for the reason that survives the correction: it was a second implementation of
the rules living in a page, and it knew nothing about route buildings at all -- so it agreed
with the engine by luck on the cases it could express, and had no way to be right about the
rest.

WHAT IS RECORDED. legal_actions() returns complete turns: a FullTurnAction carries `origin`,
the whole `route`, the `selected_duty` and the `resolution` at once. So "which tiles may I
touch right now" is not a question the engine answers directly -- it is a PROJECTION of the
actions still reachable given what has been decided, and taking that projection needs no
knowledge of the game at all:

    decided so far  ->  keep the actions that match  ->  the distinct next values they offer

That is the whole recorder. It knows the names of four fields and nothing else: not what a duty
is, not what a route means, not which tiles are adjacent. Every set of lit tiles below is
something the engine said.

The tree is small because a turn is small, and smaller still for the plain sow:
kogge_and_cloisters_2p records 12 nodes from its 55 plain turns, having left out 989 that hire
a route building. It fits in a file.

WHAT IS NOT RECORDED. Where the sculpts stand as you move them. The engine has no state for
"halfway through sowing" -- it applies a whole turn -- so there is nothing to record and the
page animates that itself from the choices you made. The split is deliberate and is the line
worth holding: WHAT IS LEGAL comes from here, WHAT IT LOOKS LIKE while you decide is the
page's. If a future question needs an intermediate engine state, it needs the engine, not a
better guess.

Run it with the engine importable (Python 3.12+; the ui_debug tools themselves run on 3.10):

    python3 tools/capture_sow_offers.py --scenario movement_2p
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# `HERE.parent`, not `HERE.parents[1]`: this file moved up out of tools/ui_debug on 2026-09-26
# and the old depth silently pointed sys.path at the repo's PARENT, so `import pilgrim` failed
# with ModuleNotFoundError rather than anything that named the cause.
ROOT = HERE.parent
OUT = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_sow_offers.json"
SCENARIOS = ROOT / "scenarios" / "playtest"

# The engine's own order of decision. Named here because the projection walks them in it, and
# because a field added to the engine should make this file stop rather than quietly record a
# turn with a decision missing from it.
DECIDED = ("origin", "route", "selected_duty")


def _engine():
    """Import the engine, or say plainly why it could not be."""
    sys.path.insert(0, str(ROOT))
    try:
        from pilgrim.io.scenarios import load_scenario
        from pilgrim.io.view import view_payload
        from pilgrim.model.actions import FullTurnAction
        from pilgrim.rules.transition import legal_actions
    except SyntaxError as bad:                       # the engine needs 3.12+; these tools do not
        raise SystemExit(
            "the engine will not import under Python %d.%d -- it needs 3.12 or newer. This "
            "recorder is the only thing here that needs it, which is why it is a separate "
            "script run when the offers change rather than part of the page build: %s"
            % (sys.version_info[0], sys.version_info[1], bad)
        ) from bad
    return load_scenario, view_payload, FullTurnAction, legal_actions


def offers(state, config, load, view, FullTurnAction, legal_actions, seat=None):
    """The offer tree for the active player's turn, as nodes a page can walk.

    A node id is the decisions taken to reach it: "" is before anything is chosen, "4" after
    picking up at position 4, "4/5" after the first acolyte lands on 5. The page holds an id and
    nothing else; it never works out what is legal, it reads `lit`.
    """
    every = [a for a in legal_actions(state, config) if isinstance(a, FullTurnAction)]
    if not every:
        raise SystemExit("this scenario offers no whole turns -- nothing to record")

    # THE PLAIN SOW ONLY: turns that hire no route building.
    #
    # legal_actions returns WHOLE TURNS, and a whole turn may include hiring Kogge or Cloisters,
    # which extend how far the acolytes reach. Projecting the next position without separating
    # those unions three different offers into one lit set: from Construct in
    # kogge_and_cloisters_2p the plain sow reaches `south`, cloisters also reaches `south_west`,
    # and kogge+cloisters reaches `city` -- and the page lit all three as though they were
    # equally free, two tiles further than the acolytes can actually walk.
    #
    # Hiring is a decision about a BUILDING, not about a tile, and this page has no way to ask
    # it. So the recording is of the sow as it stands with nothing hired, and how many turns
    # that leaves out is counted and written down rather than quietly dropped -- otherwise in a
    # year the file reads as though the engine only ever offered one step.
    actions = [a for a in every
               if a.sow_route_building_id is None
               and a.sow_route_secondary_building_id is None]
    if not actions:
        raise SystemExit("every legal turn here hires a route building -- there is no plain "
                         "sow to record, and this page cannot ask which building to hire")
    hired = len(every) - len(actions)

    nodes: dict[str, dict] = {}

    def node_id(origin, prefix):
        return "/".join(str(v) for v in (origin,) + prefix) if origin is not None else ""

    def walk(origin, prefix):
        here = node_id(origin, prefix)
        if here in nodes:
            return
        if origin is None:
            # NOTHING DECIDED. The tiles on offer are the distinct origins -- which happens to
            # be every tile the player has an acolyte on, but that is the engine's conclusion
            # and not a rule written here.
            lit = sorted({a.origin for a in actions})
            nodes[here] = {"decision": "origin", "lit": lit,
                           "next": {str(v): node_id(v, ()) for v in lit}}
            for v in lit:
                walk(v, ())
            return
        live = [a for a in actions
                if a.origin == origin and a.route[: len(prefix)] == prefix]
        ahead = sorted({a.route[len(prefix)] for a in live if len(a.route) > len(prefix)})
        if ahead:
            nodes[here] = {"decision": "route", "lit": ahead,
                           "next": {str(v): node_id(origin, prefix + (v,)) for v in ahead}}
            for v in ahead:
                walk(origin, prefix + (v,))
            return
        # THE ROUTE IS DONE, so the question becomes which duty tile is acted on. A node with no
        # `next` is the end of what this recording covers: `resolution` -- duty action or tithe
        # -- is a decision about an already-chosen tile and no page draws it yet.
        nodes[here] = {"decision": "selected_duty",
                       "lit": sorted({a.selected_duty for a in live}),
                       "next": {}}

    walk(None, ())

    payload = view(state, config)
    return {
        "note": "Captured from the engine by tools/capture_sow_offers.py. Every `lit` "
                "list is a projection of legal_actions given the decisions in the node's id -- "
                "no rule about the board is written anywhere in this file or in the page that "
                "reads it. Re-record when the engine's offers change; the page cannot tell that "
                "they have.",
        "positions": payload["board_positions"],
        "seat": state.active_player if seat is None else seat,
        "acolytes": [list(row) for row in payload["state"]["acolytes"]],
        # THE DUMMY GROUPS COUNT AS OCCUPANTS. They are not a player's and cannot be lifted, but
        # they fill slots, and a page drawing the board without them shows tiles emptier than
        # they are -- which is the one thing the sculpt layout is judged on.
        "dummies": list((payload["state"].get("dummy_acolytes") or {}).get("total") or []),
        "duty_tiles": payload["duty_tiles"],
        "root": "",
        "nodes": nodes,
        # WHAT THIS RECORDING IS NOT. Turns that hire Kogge or Cloisters reach further and are
        # left out, because hiring is a building decision and no page here can ask it.
        "plain_sow_only": True,
        "turns_recorded": len(actions),
        "turns_left_out_hiring_a_route_building": hired,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # NO DEFAULT. It was `movement_2p` while the committed recording was made from
    # kogge_and_cloisters_2p, so running this with no arguments silently replaced one deal's
    # offers with another's -- and since both are valid nothing would have complained. Which
    # scenario a recording is of is the most important thing about it; it gets said out loud.
    ap.add_argument("--scenario", required=True,
                    help="a file in scenarios/playtest, without the .json")
    ap.add_argument("--out", default=None, help="where to write (default %s)" % OUT.name)
    args = ap.parse_args()

    load, view, FullTurnAction, legal_actions = _engine()
    path = SCENARIOS / ("%s.json" % args.scenario)
    if not path.is_file():
        raise SystemExit("%s is not a scenario -- have %s"
                         % (path, ", ".join(sorted(p.stem for p in SCENARIOS.glob("*.json")))))
    loaded = load(str(path))
    rec = offers(loaded.state, loaded.config, load, view, FullTurnAction, legal_actions)
    rec["scenario"] = args.scenario

    out = pathlib.Path(args.out) if args.out else OUT
    out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")

    by = {}
    for n in rec["nodes"].values():
        by[n["decision"]] = by.get(n["decision"], 0) + 1
    print("recorded %s -> %s" % (args.scenario, out))
    print("  seat %d  ·  %d nodes  ·  %s"
          % (rec["seat"], len(rec["nodes"]),
             ", ".join("%d asking %s" % (v, k) for k, v in sorted(by.items()))))
    print("  origins offered: %s"
          % [rec["positions"][i] for i in rec["nodes"][rec["root"]]["lit"]])
    print("  plain sow only: %d turns recorded, %d left out for hiring a route building"
          % (rec["turns_recorded"], rec["turns_left_out_hiring_a_route_building"]))


if __name__ == "__main__":
    main()
