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
and which sculpt size is on screen -- and the sizes on offer are the ones the file names.

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
SETUP = ROOT / "configs" / "setups" / "basic_mancala_sandbox.json"
RULES_JS = HERE / "duty_sculpt_rules.js"
TEMPLATE = HERE / "duty_sow.html.tmpl"

# The nine positions as a compass, so the ring on screen reads as the ring on the board. The
# artwork order is an IDENTITY and not a position, so laying the page out in it would draw a
# ring that wanders.
GRID = ("north_west", "north", "north_east",
        "west", "city", "east",
        "south_west", "south", "south_east")


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


def _board_module():
    return _by_path("generate_duty_board_check", HERE / "generate_duty_board_check.py",
                    ROOT / "ui" / "render")


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
    missing = [p for p in GRID if p not in edges]
    if missing:
        raise SystemExit("%s has no edges for %s -- the compass and the graph have drifted apart"
                         % (BOARD_JSON.relative_to(ROOT), ", ".join(missing)))
    return edges


def duty_at():
    """Which duty sits at which position, from a committed scenario.

    FROM THE CONFIG, NOT FROM THE ENGINE. The model can answer this too, but everything under
    tools/ui_debug is a derived view: it reads data and draws it, and a game config is the
    source of truth for any real game value a view happens to show. Reading the scenario also
    keeps this script free of the engine, which needs a newer interpreter than a tools run can
    count on.

    Duty tiles can be shuffled, so this is one deal rather than the deal -- which is the right
    shape for a page about sculpts.
    """
    if not SETUP.is_file():
        raise SystemExit("%s is missing -- there is no duty to put on a tile"
                         % SETUP.relative_to(ROOT))
    tiles = dict((json.loads(SETUP.read_text(encoding="utf-8")) or {}).get("duty_tiles") or {})
    if not tiles:
        raise SystemExit("%s carries no duty_tiles" % SETUP.relative_to(ROOT))
    tiles["city"] = "city"
    return tiles


def offered(place, figs, notes):
    """Which sculpt sizes get a button.

    The file names them. Today that is one size and the row is a label with a border round it,
    which is the honest way to draw a choice of one. When the file names another, the button
    appears here with no change to the page -- which is the whole reason the list is in the file
    rather than in this script.

    A size the file names but the tray has never rendered is dropped with a note rather than
    offered: a button that produces an empty board is worse than a button that is absent.
    """
    declared = place.get("sizes") or [place.get("tuned_at")]
    have = []
    for px in declared:
        if str(px) in figs:
            have.append(px)
        else:
            notes.append("%s px is named by the placement file but has no art -- left out "
                         "(run tools/ui_debug/make_tray_figures.py)" % px)
    return sorted(have)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--figures", default=None, help="folder holding the rendered sculpts")
    ap.add_argument("--open", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--no-open", dest="open", action="store_false",
                    help="write the page without opening it")
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

    sizes = offered(place, figs, notes)
    if not sizes:
        raise SystemExit("the placement file names no sculpt size that has art -- nothing to "
                         "draw (run tools/ui_debug/make_tray_figures.py)")

    edges = graph()
    at = duty_at()
    banner_art, font_uri = board.banners(notes)

    # Parchment and title are looked up by the duty's slug, so the page cannot pair a name with
    # someone else's banner even if the compass or the layout changes.
    cells = []
    for pos in GRID:
        slug = at.get(pos)
        if slug not in board.SLUGS:
            raise SystemExit("position %s carries duty %r, which is not in the slug table"
                             % (pos, slug))
        i = board.SLUGS.index(slug)
        cells.append({"pos": pos, "slug": slug, "title": board.NAMES[i],
                      "ban": banner_art[i] if banner_art else ""})

    # Only the seats the page can actually draw: the sculpt rows are p1..p3 and so is the sow.
    art = {str(px): [{"uri": f["uri"], "w": f["w"], "h": f["h"]} for f in figs[str(px)]]
           for px in sizes}

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
            ("__OPENING__", json.dumps(place.get("tuned_at", sizes[-1]))),
            ("__PLACEMENT__", json.dumps(place)),
            ("__BANNERTOP__", json.dumps(board.BANNER_TOP)),
            ("__BANNERFS__", json.dumps(board.BANNER_FS)),
            ("__BANNERTRACK__", json.dumps(board.BANNER_TRACK)),
            ("__BANNERINK__", json.dumps(board.BANNER_INK)),
            ("__FORMATION__", RULES_JS.read_text(encoding="utf-8"))):
        page = page.replace(key, value)
    left = re.findall(r"__[A-Z_]+__", page)
    assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    branch = sorted(p for p in GRID if len(edges.get(p, [])) > 1)
    print("  board from %s: %d positions, %d of them a choice (%s)"
          % (BOARD_JSON.name, len(GRID), len(branch), ", ".join(branch)))
    print("  sculpt sizes offered: %s  (named by %s)"
          % (", ".join(str(s) for s in sizes), board.PLACEMENT.name))
    print("  spread %d, set-back %d, rank gap %d  ·  order %s  ·  mark %s  ·  depth %s %d%%"
          % (place["spread"], place["back"], place["rank"], place["order"], place["mark"],
             place["depth"]["mode"], place["depth"]["amount"]))
    for note in notes:
        print("  %s" % note)
    board.show(out, args.open)


if __name__ == "__main__":
    main()
