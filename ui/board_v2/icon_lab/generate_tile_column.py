#!/usr/bin/env python3
"""Build a page showing the eight duty tiles with their marks stacked in a column.

    python3 ui/board_v2/icon_lab/generate_tile_column.py --open

The board places a duty's two marks on the DIAGONAL, overlapping. That was designed for round wax
discs, where one resting on another reads as depth; the marks are squares with corners now, and a
corner cutting into a neighbour reads as a mistake. This page asks what the obvious alternative
looks like.

EVERY NUMBER STARTS AS GEOMETRY.PY'S. The page opens on the board's own `SEAL`, `GAP` and a tile
height worth looking at, so what you see first is the board as it would be rather than a sketch of
a board that might be. Three sliders move from there: the gap, the tile's height -- which is
RIBBON_H -- and the mark's size.

THE SIZE IS A LEVER BECAUSE THE BOARD NOW TAKES ONE. It used to be fixed here on the argument that
SEAL had been decided, which was true while the only way to draw a different size was to edit
geometry.py. `generate_action_board.py --icons N` made it a real choice, so the number needs a
place to be chosen, and this is the page that can show you it against the tile it has to fit.
Nothing here writes it down: the readout names geometry.py's SEAL beside the slider's whenever the
two differ, and what you decide goes to --icons or into geometry.py by hand.

ONE GAP, TWO JOBS. The gap is the space under the duty's name as well as the space between its two
marks, so the column hangs from the name at the rhythm it keeps inside itself instead of floating
in whatever is left over. That also puts the first mark on the same line on all eight tiles:
Taxation and Allocation have a single action each, and centring theirs in the leftover space sat
it half a mark below its neighbours', which read as a mistake on the two tiles that are different
rather than as the difference itself.

AND IT SAYS WHO PAYS. A page that let you drag RIBBON_H to 244 and said nothing else would be
offering a free lunch. Nothing below the ribbon shrinks, it moves: ART_Y is RIBBON_Y + RIBBON_H +
GAP and the rest of the board follows down from there. The wheel is the one elastic thing, because
WHEEL_H is whatever the canvas has left, so the wheel pays every pixel -- and it keeps its asset's
aspect, so it narrows by about twice what it loses in height. The readout says that in the wheel's
own width and height, and so does this script on every build.

It sits beside the icon lab's other two pages because all three are about how a mark is presented:
one decides its crop, one how big it is drawn, this one where the two of them sit.
"""
import argparse
import base64
import importlib.util
import json
import pathlib
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent
TMPL = HERE / "tile_column.html.tmpl"
OUT = HERE / "generated" / "tile_column.html"

spec = importlib.util.spec_from_file_location("geometry", BOARD / "action_board" / "geometry.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
# THE RIBBON'S OWN NUMBERS, PLUS THE THREE THE PAGE NEEDS THAT ARE NOT IN IT. The border is the
# board's and belongs to every box; the wheel is here because it is the thing that pays for a
# taller ribbon, and the page cannot say what a height costs without knowing the size it comes off.
GEO = dict(G.as_dict()["ribbon"], border=G.BORDER,
           wheelW=G.WHEEL_W, wheelH=G.WHEEL_H, wheelRatio=G.WHEEL_RATIO)

# THE GAP THE PAGE OPENS ON, OWNED ONCE. It is the slider's starting value and it is the number
# the fit arithmetic below uses, and those have to be the same number or the build reports on a
# page nobody is looking at. It does one more job than its name suggests: it is the space between
# the two marks AND, at twice itself, the air the tile keeps round them -- so the box hugs the
# pair at the rhythm the pair keeps inside itself.
#
# IT IS THE BOARD'S OWN NUMBER NOW, NOT 15. It was 15 while the page's job was to propose a tile
# the board did not have, and the second job was the space under the duty's NAME. There is no
# name, the board's tile is derived from exactly this arithmetic, and a page that opened on a
# gap the board does not use would be drawing a tile the board does not draw.
GAP = G.SEAL_INSET

# AND THE BAND HEIGHT THE PAGE OPENS ON, WHICH IS RIBBON_H AGAIN. It was 265 -- not the board's
# ribbon, deliberately: the board of the day did not fit a column at all, so opening there meant
# opening on the problem every time and dragging to the answer before you could look at anything.
# The band holds the tile with room over now, so the board you have IS a thing worth looking at,
# and starting anywhere else would make the page disagree with it for no reason.
# NOTHING HERE MOVES THE BOARD. RIBBON_H in geometry.py is untouched and the readout still names
# it beside this one, so the page cannot be mistaken for the board it is proposing.
START_H = G.RIBBON_H

# AND THE MARK SIZE THE PAGE OPENS ON, WHICH IS THE BOARD'S. Unlike the two above it this one is
# not a number chosen for the page -- it is read straight from geometry.py, so the page opens on
# the board you have and the slider is what proposes something else. It is also what the fit
# arithmetic below reports on, for the same reason the gap is: a build that printed a verdict on a
# size the page does not open at would be reporting on a page nobody is looking at.
START_SEAL = G.SEAL

TEXT = json.loads((BOARD / "duty_text.json").read_text(encoding="utf-8"))["duties"]
REC = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))["files"]
ART = BOARD / "duty_actions"
SIDE = {"left": "actionA", "right": "actionB"}


def version_of(name):
    import re
    m = re.search(r"_v(\d+)\.", name)
    return int(m.group(1)) if m else -1


def marks():
    """The mark the board actually draws for each slot, by the same rule the board uses."""
    order = {n: i for i, n in enumerate(
        json.loads((BOARD / "attribution.json").read_text(encoding="utf-8")).get("markFolders")
        or ("seals",))}
    best = {}
    for path, e in REC.items():
        if not path.startswith("duty_actions/"):
            continue
        parts = path[len("duty_actions/"):].split("/")
        if len(parts) < 3 or parts[1] not in order or "masters" in parts:
            continue
        slot = SIDE.get(e.get("slot"))
        if slot is None:
            continue
        key = (parts[0], slot)
        rank = (order[parts[1]], version_of(parts[-1]))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, path, e)
    return best


def main():
    best = marks()
    duties = []
    for slug, name, _deg in G.DUTIES:
        said = TEXT[slug]
        slots = []
        for slot in ("actionA", "actionB"):
            if not said.get(slot):
                continue
            got = best.get((slug, slot))
            if not got:
                print("  %s %s has no mark on the record, left out" % (slug, slot))
                continue
            _rank, path, e = got
            f = BOARD / path
            mime = "image/webp" if f.suffix == ".webp" else "image/png"
            slots.append({
                "name": said[slot]["name"],
                "ground": e.get("ground") == "board",
                "src": "data:%s;base64,%s" % (mime, base64.b64encode(f.read_bytes()).decode()),
            })
        duties.append({"slug": slug, "name": name, "slots": slots})

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    a = ap.parse_args()

    if not TMPL.is_file():
        raise SystemExit("the template is not at %s" % TMPL)
    page = TMPL.read_text(encoding="utf-8")
    fill = {"__GEO__": json.dumps(GEO), "__DUTIES__": json.dumps(duties),
            "__START_H__": str(START_H), "__GAP__": str(GAP),
            "__START_SEAL__": str(START_SEAL)}
    for token, value in fill.items():
        if token not in page:
            raise SystemExit("the template has no %s in it, so the build would be dropped on "
                             "the floor" % token)
        page = page.replace(token, value)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode("utf-8")) // 1024))
    print("  %d tiles, %d marks, opening at %d px (geometry.py's SEAL)"
          % (len(duties), sum(len(d["slots"]) for d in duties), START_SEAL))

    # WHAT THE COLUMN ASKS FOR, SAID ON EVERY BUILD. It used to be said only when the marks
    # overflowed the tile, which meant the one line that states this build's whole purpose --
    # pricing a ribbon against a mark size -- printed nothing at all for every size that fits. A
    # build that reports only on failure is a build you cannot read while it is working.
    #
    # AND THAT IS WHERE THE PRICE STOPPED BEING TESTABLE. The mark went to 50, two of them fit the
    # tile with 36 to spare, and the guard that holds the slider and this arithmetic to the same
    # gap had nothing to read. Hiding a number behind a condition hides its guard with it.
    # THE TILE IS DERIVED FROM THE MARK, which is what this arithmetic became. It used to add a
    # name band, a gap, two marks and an inset and ask whether that fitted a tile of a given
    # height; the tile has no name band and is not given a height -- it is the pair plus the air,
    # and the question is whether the BAND holds it.
    pad = 2 * GAP
    avail = GEO["height"]
    want = 2 * START_SEAL + GAP + 2 * pad
    grew = want - G.RIBBON_H
    print("  a column wants RIBBON_H of about %d against today's %d" % (want, G.RIBBON_H))
    if want > avail:
        print("  a tile round two marks of %d is %d tall and the band is %d"
              % (START_SEAL, want, avail))
    if grew > 0:
        # WHAT IT WOULD COST, because the number above on its own reads as free. Nothing below the
        # ribbon shrinks, it moves; the wheel takes whatever the canvas has left, so the wheel is
        # what pays, and it narrows by its aspect as it loses height.
        tall = G.WHEEL_H - grew
        print("  which the wheel would pay for: %d x %d becomes %d x %d"
              % (G.WHEEL_W, G.WHEEL_H, round(tall / G.WHEEL_RATIO), tall))
    else:
        # OR WHAT IT GIVES BACK. The ribbon is held at its height on purpose, so this is spare
        # rather than a saving anybody has taken -- and saying so is what keeps the choice visible
        # instead of letting it look like nobody noticed.
        print("  %d px of the ribbon's height is spare at this mark size; RIBBON_H is held at %d"
              % (-grew, G.RIBBON_H))

    if a.open:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
