"""The Sow, played by hand on the duty wheel, at true size.

    python3 tools/ui_debug/generate_duty_sow.py --open

WHAT THIS IS FOR

A sow is a physical act before it is a rule: you pick a tile up, you hold a fistful of acolytes,
and you put them down one at a time along a route. Everything else in this toolchain draws an
arrangement that already exists. This page is the only one where sculpts MOVE, which is the only
way to find out whether the arrangement reads while your hand is in the way.

WHAT IS LIT, AND WHY ONLY THAT

Lit means legal NOW. The board graph runs one way and only three positions branch -- `east` and
`west` each offer the ring or a spoke to the City, and the City offers north or south -- so the
next step is one tile most of the time and two at those three. Both choices are lit identically;
the page has no business implying one of them is the real one.

An earlier version also ghosted the tiles further along a forced run. It was dropped rather than
fixed. It answered "where will this end up", which is not the question in front of the player --
the question is where THIS acolyte goes -- and the count in the hand already says how much is
left. The forced runs are short anyway: never longer than three, averaging 1.3.

THERE ARE NO SLIDERS HERE

Spread, set-back, rank gap, seating order, the marking and the whole depth cue come from
`ui/assets-gothic/metadata/duty_placement.json`, which is tuned next door in the placement sheet
and saved from it. A control here would be a second place to set the same numbers, and the two
would disagree the first time one was nudged. The only controls are which seat you are playing
and which sculpt SET is on screen -- and the sets on offer are the ones the file names. A set
is a label (`210_plastic`, `210_painted`) rather than a pixel height, because two sets can be
210 tall; the height is a fact about the label rather than the name of it.

NOTHING IS COPIED FROM ITS NEIGHBOURS

`placement()`, `figures()` and `banners()` are imported from generate_duty_board_check.py, which
owns them, and the formation, seat order and depth cue are inlined from duty_sculpt_rules.js.
The board graph is read from configs/board.json and the duty at each position from the
committed sandbox scenario. Everything this page knows, something else is responsible for.
"""

import argparse
import importlib.util
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "duty_sow.html"

BOARD_JSON = ROOT / "configs" / "board.json"
RULES_JS = HERE / "duty_sculpt_rules.js"
MARK_JS = HERE / "duty_mark_rules.js"
# What the engine offers during a turn, recorded by record_sow_offers.py. The page draws
# from this rather than working out what is legal; see the long note at the top of that
# script for why, and for the two places the rule it replaced was measurably wrong.
OFFERS = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_sow_offers.json"
# The set dropdown, shared with the placement sheet so the two group the sets the same way.
PICKER_JS = HERE / "duty_set_picker.js"
TEMPLATE = HERE / "duty_sow.html.tmpl"



def _by_path(name, path, extra_sys_path=None):
    """Import a neighbouring SCRIPT by path.

    The generators are scripts rather than package modules, so they are loaded this way rather
    than by name, and without depending on the caller's working directory. This is boilerplate
    rather than a rule, and the placement sheet has its own copy on purpose: a wrong copy of an
    importer fails loudly on the next run, which is not the kind of duplication that has ever
    hurt this toolchain.
    """
    if extra_sys_path:
        sys.path.insert(0, str(extra_sys_path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # REGISTERED BEFORE IT RUNS. @dataclass and a few other decorators look their own class up
    # through sys.modules while the module is still executing, and die with an AttributeError
    # about NoneType if it is not there yet -- an error that names dataclasses.py and says
    # nothing about this line. None of the scripts loaded here holds one today.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_BOARD = None


def _board_module():
    """The board checker, which owns the placement rules, the art and the nine tiles.

    Cached: it is asked for several times a run, and re-executing a module to read a constant
    off it is the kind of waste that turns into a puzzling slowdown rather than an error.
    """
    global _BOARD
    if _BOARD is None:
        _BOARD = _by_path("generate_duty_board_check", HERE / "generate_duty_board_check.py",
                          ROOT / "ui" / "render")
    return _BOARD


def board_grid():
    return _board_module().GRID


def graph():
    """The board's directed edges, read rather than restated.

    A page that invented its own ring would be a drawing of a board rather than of THIS board,
    and would keep looking right while the real topology moved underneath it.
    """
    if not BOARD_JSON.is_file():
        raise SystemExit("%s is missing -- the sow has no board to walk"
                         % BOARD_JSON.relative_to(ROOT))
    data = json.loads(BOARD_JSON.read_text(encoding="utf-8"))
    edges = data.get("edges") or {}
    missing = [p for p in board_grid() if p not in edges]
    if missing:
        raise SystemExit("%s has no edges for %s -- the compass and the graph have drifted apart"
                         % (BOARD_JSON.relative_to(ROOT), ", ".join(missing)))
    return edges


def offered(place, figs, notes):
    """Which sculpt sets the page can show, and which of them the file calls the played ones.

    Returns (every set that has art, the subset `sizes` names). BOTH, because `sizes` stopped
    being a filter on 2026-09-25 and became a grouping.

    IT WAS A FILTER AND IT HID REAL WORK. The file named two sets, the tray had rendered ten,
    and a set tuned in the placement sheet -- 150_painted, with its own spread, set-back, rank
    and frame, and its own lift for the plates -- simply did not appear here, with nothing on
    the page to say it existed. A control that silently omits the thing you just tuned is worse
    than a long list. So everything rendered is reachable, and `sizes` says which ones are the
    played sizes rather than which ones you are allowed to look at.

    A set the file names but the tray has never rendered is still dropped with a note: there is
    no art to draw, and an entry that produces an empty board is worse than one that is absent.
    """
    board = _board_module()
    have = sorted(figs, key=board.set_sort)
    declared = place.get("sizes") or [place.get("tuned_at")]
    played = []
    for label in declared:
        if label in figs:
            played.append(label)
        else:
            notes.append("%s is named by the placement file but has no art -- left out of the "
                         "played group (run tools/ui_debug/make_tray_figures.py)" % label)
    return have, sorted(played, key=board.set_sort)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--figures", default=None, help="folder holding the rendered sculpts")
    ap.add_argument("--open", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--no-open", dest="open", action="store_false",
                    help="write the page without opening it")
    ap.add_argument("--offers", default=None, metavar="FILE",
                    help="a recording other than the committed one, for building two deals "
                         "side by side (see tools/ui_debug/record_sow_offers.py)")
    args = ap.parse_args()

    board = _board_module()
    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    fig_dir = pathlib.Path(args.figures).expanduser() if args.figures else board.FIGURE_DIR

    notes = []
    place = board.placement(notes)
    figs = board.figures(fig_dir, notes)
    if not figs:
        raise SystemExit("no sculpt art -- run tools/ui_debug/make_tray_figures.py first; "
                         "this page is acolytes being moved and nothing else")
    if not TEMPLATE.is_file():
        raise SystemExit("%s is missing" % board._short(TEMPLATE))
    if not RULES_JS.is_file():
        raise SystemExit("%s is missing -- it is where the drawing rules live"
                         % board._short(RULES_JS))
    if not PICKER_JS.is_file():
        raise SystemExit("%s is missing -- it is where the set dropdown lives"
                         % board._short(PICKER_JS))

    sizes, played = offered(place, figs, notes)
    if not sizes:
        raise SystemExit("the tray has rendered no sculpt set -- nothing to draw "
                         "(run tools/ui_debug/make_tray_figures.py)")

    edges = graph()
    offers_path = pathlib.Path(args.offers).expanduser() if args.offers else OFFERS
    if not offers_path.is_file():
        raise SystemExit(
            "%s is missing -- the page has no engine answers to draw and will not guess at "
            "them. Record it with: python3 tools/ui_debug/record_sow_offers.py"
            % board._short(offers_path))
    offers = json.loads(offers_path.read_text(encoding="utf-8"))

    # THE LAYOUT COMES FROM THE RECORDING, not from the sandbox setup the other pages use.
    # The offers were taken against a particular deal, and banners drawn from a different one
    # put real duties on the wrong tiles while every lit set still checks out -- which is how
    # this went unnoticed for a day.
    layout = {t["position_name"]: t["duty"] for t in (offers.get("duty_tiles") or [])}
    if not layout:
        raise SystemExit("%s carries no duty_tiles -- re-record it; the page will not pair its "
                         "offers with a layout from somewhere else"
                         % board._short(offers_path))
    cells, font_uri = board.tiles(notes, layout=layout)
    # The same two files the placement sheet writes. The sheet tunes; this page plays on what
    # the sheet saved -- if it read its own copy of any of this, the two would drift the first
    # time a slider moved.
    plan = board.ground_plan(notes)
    effects = board.effects_plan(notes)
    plates = board.ground_art(notes)

    # Only the seats the page can actually draw: the sculpt rows are p1..p3 and so is the sow.
    # A seat is a LIST OF POSES -- one for the plastic set, three for the painted one -- and the
    # page picks with dutyPose(), so the two stay interchangeable with no branch on which loaded.
    art = {label: [[{"uri": f["uri"], "w": f["w"], "h": f["h"]} for f in row]
                   for row in figs[label]]
           for label in sizes}

    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in (
            # RAW, not JSON-quoted: this one lands inside a CSS url(). With no font it becomes an
            # empty url(), an invalid @font-face src -- which is the right failure, because the
            # face simply never loads and the titles fall back instead of the page breaking.
            ("__FONTURI_CSS__", font_uri),
            ("__GROUND__", board.GROUND),
            ("__CELLS__", json.dumps(cells)),
            ("__EDGES__", json.dumps(edges)),
            ("__FIGS__", json.dumps(art)),
            ("__SIZES__", json.dumps(sizes)),
            # WHICH OF THEM THE FILE CALLS THE PLAYED ONES. The dropdown groups by this rather
            # than filtering by it; see offered() for the set that went missing when it filtered.
            ("__PLAYED__", json.dumps(played)),
            ("__BASESET__", json.dumps(place.get("tuned_at"))),
            ("__OWNSETS__", json.dumps(sorted(
                set(place.get("per_set") or {}) | set(plan.get("per_set") or {}),
                key=board.set_sort))),
            ("__OPENING__", json.dumps(place.get("tuned_at", sizes[-1]))),
            ("__PLACEMENT__", json.dumps(place)),
            # EVERY OFFERED SET'S NUMBERS AND PLATES, resolved here. This page switches sets
            # with a button, so it needs an answer per set rather than the base and the rule
            # for merging it -- and one resolver means it cannot disagree with the sheet that
            # tuned them.
            ("__RULES__", json.dumps({label: board.settings_for(place, label)
                                      for label in sizes})),
            ("__GPLANS__", json.dumps({label: board.ground_settings_for(plan, label)
                                       for label in sizes})),
            ("__TRANSPARENCY__", json.dumps(plan.get("transparency", 0))),
            ("__PLATES__", json.dumps(plates)),
            ("__GROUNDPLAN__", json.dumps(plan)),
            ("__BANNERTOP__", json.dumps(board.BANNER_TOP)),
            ("__BANNERFS__", json.dumps(board.BANNER_FS)),
            ("__BANNERTRACK__", json.dumps(board.BANNER_TRACK)),
            ("__BANNERINK__", json.dumps(board.BANNER_INK)),
            ("__FORMATION__", RULES_JS.read_text(encoding="utf-8")),
            ("__MARKRULES__", MARK_JS.read_text(encoding="utf-8")),
            ("__OFFERS__", json.dumps(offers)),
            # What the page SHOWS, which is shorter than what the recording carries.
            ("__DRAWABLE__", json.dumps(list(board.DRAWABLE_DECISIONS))),
            # THE CATALOGUE, WHOLE. The page reads the entry `mark` names rather than being told
            # which one to draw, so an effect added to the file reaches this page without a line
            # changing here -- which is the claim the catalogue is for.
            ("__EFFECTS__", json.dumps(effects.get("effects") or {})),
            ("__SETPICKER__", PICKER_JS.read_text(encoding="utf-8"))):
        page = page.replace(key, value)
    left = re.findall(r"__[A-Z_]+__", page)
    assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    branch = sorted(p for p in board_grid() if len(edges.get(p, [])) > 1)
    print("  board from %s: %d positions, %d of them a choice (%s)"
          % (BOARD_JSON.name, len(board_grid()), len(branch), ", ".join(branch)))
    own = set(place.get("per_set") or {}) | set(plan.get("per_set") or {})
    print("  %d sculpt set(s) on the dropdown, %s of them played at per %s"
          % (len(sizes), len(played) or "none", board.PLACEMENT.name))
    for label in sizes:
        print("    %-13s %d pose%s%s%s%s"
              % (label, len(figs[label][0]), "" if len(figs[label][0]) == 1 else "s",
                 "  played" if label in played else "",
                 "  base" if label == place.get("tuned_at") else "",
                 "  own numbers" if label in own else ""))
    frame = place.get("frame") or {}
    if frame:
        print("  frame %d x %d real px, base %d below the floor"
              % (frame["w"], frame["h"], frame.get("drop", 0)))
    in_use = board.ground_check(plan, plates, notes)
    print("  %d ground plate(s) in %s, %d duties assigned by %s, standing on: %s"
          % (len(plates), board.GROUNDS_DIR.name, len(plan.get("by_duty") or {}),
             board.GROUND_PLAN.name, ", ".join(in_use) or "bare floor only"))
    print("  ground lifted %d px above the floor line on every tile" % plan.get("lift", 0))
    # SAID BESIDE THE LIFT because it is the other number that is true of every tile AND
    # every set. Printed even at 0: a summary that only mentions transparency when the
    # plates are faded reads as though solid plates were the absence of a setting.
    print("  ground drawn at %d%% transparency on every tile and every sculpt set"
          % plan.get("transparency", 0))
    print("  spread %d, set-back %d, rank gap %d  ·  order %s  ·  depth %s %d%%"
          % (place["spread"], place["back"], place["rank"], place["order"],
             place["depth"]["mode"], place["depth"]["amount"]))
    print("  marks  %s" % board._marks_sentence(place))
    # WHERE THE LIT TILES COME FROM, said every build. The recording is a snapshot of what the
    # engine offered when it was taken, and nothing in the page build can tell that the engine
    # has moved on -- so the run says which scenario it is and how old it is, rather than
    # letting a stale recording pass as a current answer.
    print("  offers recorded from scenario %s  ·  %d nodes  ·  p%d to move"
          % (offers.get("scenario", "?"), len(offers.get("nodes") or {}),
             offers.get("seat", 0) + 1))
    # WHAT THE PAGE IS NOT SHOWING, every build. The recording is the plain sow; turns that
    # hire Kogge or Cloisters reach further and are left out, because hiring is a decision
    # about a building and no page here can ask it. Said out loud so the omission cannot
    # quietly become "the engine only ever offered one step".
    left_out = offers.get("turns_left_out_hiring_a_route_building")
    if left_out:
        print("  plain sow only: %d turns drawn, %d left out for hiring a route building"
              % (offers.get("turns_recorded", 0), left_out))
    for note in notes:
        print("  %s" % note)
    board.show(out, args.open)


if __name__ == "__main__":
    main()
