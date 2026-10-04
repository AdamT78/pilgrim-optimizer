#!/usr/bin/env python3
"""Build a page showing the eight duty tiles with their marks stacked in a column.

    python3 ui/board_v2/icon_lab/generate_tile_column.py --open

The board places a duty's two marks on the DIAGONAL, overlapping. That was designed for round wax
discs, where one resting on another reads as depth; the marks are squares with corners now, and a
corner cutting into a neighbour reads as a mistake. This page asks what the obvious alternative
looks like.

EVERY NUMBER IS GEOMETRY.PY'S, INCLUDING THE MARK'S SIZE. The size is `SEAL`, read from the
board, so what you are looking at is the board as it would be rather than a sketch of a board that
might be. What the page lets you move is the gap and the tile's height, which is RIBBON_H -- and
those are the only two levers there are, because at SEAL = 100 a column of two does not fit the
ribbon as it stands.

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
# page nobody is looking at. It does one more job than its name suggests: it is the space under
# the duty's name as well as the space between the two marks, so the column hangs from the name at
# the same rhythm it keeps inside itself.
GAP = 15

# AND THE HEIGHT THE PAGE OPENS ON, WHICH IS NOT RIBBON_H. It used to start at the board's own
# ribbon, so the first thing on screen was the board you have. The board you have does not fit a
# column -- that is the finding -- so starting there means opening on the problem every time and
# dragging to the answer before you can look at anything. 265 is a height worth looking at: at the
# gap above it leaves five pixels spare.
# NOTHING HERE MOVES THE BOARD. RIBBON_H in geometry.py is untouched and the readout still names
# it beside this one, so the page cannot be mistaken for the board it is proposing.
START_H = 265

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
            "__START_H__": str(START_H), "__GAP__": str(GAP)}
    for token, value in fill.items():
        if token not in page:
            raise SystemExit("the template has no %s in it, so the build would be dropped on "
                             "the floor" % token)
        page = page.replace(token, value)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode("utf-8")) // 1024))
    print("  %d tiles, %d marks, drawn at SEAL = %d"
          % (len(duties), sum(len(d["slots"]) for d in duties), G.SEAL))

    # WHETHER IT FITS, SAID ON EVERY BUILD. The page shows it, but a build that printed nothing
    # while the marks overflowed their tile would be a build that looked fine.
    name_h = round(GEO["nameSize"] * GEO["nameLh"])
    top = GEO["nameTop"] + name_h + GAP
    avail = GEO["innerH"] - top - GEO["sealInset"]
    if 2 * G.SEAL > avail:
        print("  two marks of %d need %d px and the tile has %d under its name"
              % (G.SEAL, 2 * G.SEAL, avail))
        want = top + 2 * G.SEAL + GAP + GEO["sealInset"] + 2 * G.BORDER
        grew = want - G.RIBBON_H
        tall = G.WHEEL_H - grew
        print("  a column wants RIBBON_H of about %d against today's %d" % (want, G.RIBBON_H))
        # AND WHAT THAT WOULD COST, because the number above on its own reads as free. Nothing
        # below the ribbon shrinks, it moves; the wheel takes whatever the canvas has left, so the
        # wheel is what pays, and it narrows by its aspect as it loses height.
        print("  which the wheel would pay for: %d x %d becomes %d x %d"
              % (G.WHEEL_W, G.WHEEL_H, round(tall / G.WHEEL_RATIO), tall))

    if a.open:
        webbrowser.open(OUT.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
