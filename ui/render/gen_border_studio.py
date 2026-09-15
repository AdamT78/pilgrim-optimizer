"""Candidate markings for the two states a duty tile can be in, on the tile's own outline.

WHAT THIS IS FOR

Two states are not built yet and both want the same channel -- the tile's edge:

    take    after a Sow, which duties the active seat may take
    lift    which tiles hold one or more of that seat's acolytes, so can be lifted from

This page puts candidate animations on the REAL traced outlines at the board's own stroke weight,
over the ink edge the board already draws, so a choice made here is a choice about the board rather
than about a mock-up. It writes a page and nothing else; picking an effect means writing it into
gen_duty_grid, which this file deliberately cannot do.

WHY IT READS EVERYTHING FROM gen_duty_grid

Nothing here is retyped. The nine shapes, the names, which tiles carry two actions, the ink colour,
the edge's stroke weight and the gold the hover already uses all come from that module. A studio
that drew a 4.0 edge against the board's 3.5, or a different gold, would be a comparison against
something that does not exist -- and it would look completely right. Two throwaway scripts in this
project already died of exactly that, one of them captioning its baseline with a design that had
been replaced weeks earlier.

    python3 ui/render/gen_border_studio.py
    python3 ui/render/gen_border_studio.py --open

WHAT THE PAGE CANNOT TELL YOU

CSS animation is a browser thing. The PNG path goes through CairoSVG, which renders the static
state, so whatever is chosen has to be legible at frame zero as well as in motion.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent
OUT = UI / "generated" / "duty-border-studio.html"

# The portal ring's dash pattern, as proportions. RESCALED at build time so the pattern divides
# `pathLength` exactly -- see dash_pattern() for why that matters more here than on a circle.
PORTAL_DASH = (44, 28, 20, 62, 34, 36, 16, 74, 24, 54, 18, 68)
PORTAL_PERIOD = 200.0       # of 1000, so the pattern repeats five times with no seam
PATH_LENGTH = 1000          # every marked path is normalised to this, so a dash means one thing

# The "dynamic segments" variants build their dash array every frame from layered sine waves and
# then scale the whole thing to fit PATH_LENGTH exactly, so there is never a seam and never a reset
# -- the pattern simply keeps evolving. The waves live in the page, because they are presentation.
# THE SEGMENT COUNT IS THE ONLY THING THAT DIFFERS between the two, and it is the only number worth
# having out here, because normalising to PATH_LENGTH means the count is what sets the LENGTH: at n
# segments each lit run is about 1/n of the outline, whatever the waves are doing.
#
# v2 exists to sit near `ants`, whose lit dash is 14 of 1000. Sampling the waves over 4000 frames:
#
#     n = 9    mean lit 57.98   4.14x the ants dash
#     n = 14   mean lit 37.26   2.66x
#     n = 18   mean lit 28.99   2.07x     <- v2
#     n = 22   mean lit 23.71   1.69x
#
# So "twice ants, and more of them" is 18, derived rather than dialled in by eye.
SEGMENTS = 9
SEGMENTS_V2 = 18
ANTS_DASH = 14              # what `ants` draws, for the comparison above to mean anything

# The two states, and the colour each is proposed in. `take` is the emerald already designed for it
# -- hue 146 deg, chosen to read as a different KIND of signal from the gold hover rather than as a
# different shade of it. `lift` is offered twice, because which is right is the open question: the
# seat's own colour says "yours", one fixed hue says "liftable" and is steadier to read.
STATES = {
    "take": ("Take a duty (after Sow)", "#4BA672",
             "Emerald #4BA672, hue 146° — the positive marking already designed for this "
             "and not yet built. It has to read as a different KIND of thing from the gold hover."),
    "lift": ("Lift acolytes (1 or more present)", "#7d9b52",
             "The active seat's own colour, because what this marks is where YOUR pieces are. Sage "
             "shown. Check bone — #A8A296 against the ink edge is the weakest of the four."),
    "cool": ("Lift — fixed cool white", "#cfe3ea",
             "One hue for “lift” whoever is playing. Steadier to read, but says nothing "
             "about whose acolytes they are."),
}
EFFECTS = (("portal", "portal ring + four dots"),
           ("segments", "portal ring, dynamic segments"),
           ("segmentsv2", "portal ring, dynamic segments v2"),
           ("steady", "steady"), ("pulse", "pulse"), ("ants", "marching ants"))

# A fixture, and named as one. Which duties are open after a Sow is a rules question this file has
# no business answering; these are here so the page has something to mark.
DEMO_ELIGIBLE = (1, 2, 5, 7)
DEMO_COUNTS = (3, 0, 1, 0, 5, 0, 2, 0, 1)


def grid():
    """gen_duty_grid's namespace. Loaded by path because that is how this tree loads siblings."""
    path = HERE / "gen_duty_grid.py"
    if not path.is_file():
        raise SystemExit("%s is not in this checkout; there are no shapes to draw." % path)
    spec = importlib.util.spec_from_file_location("_studio_dg", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dash_pattern(raw=PORTAL_DASH, period=PORTAL_PERIOD) -> str:
    """The portal's dashes, rescaled so the pattern divides `pathLength` a whole number of times.

    The effect this came from sums to 478 against a circumference of 754, so its pattern restarts
    part-way round and leaves a seam where the last dash meets the first. On a smooth ring that is
    invisible. On a torn outline with nine different perimeters it would be nine visible seams in
    nine different places, and it would read as the artwork being wrong rather than the dashes.

    Scaled to 200 of 1000 the pattern repeats exactly five times on every tile, one dash is the
    same length everywhere, and the offset animates by exactly one period.
    """
    k = period / sum(raw)
    return " ".join("%.2f" % (v * k) for v in raw)


def bounds(d: str):
    n = [float(t) for t in d.replace("M", " ").replace("L", " ").replace("Z", " ").split()]
    return min(n[0::2]), min(n[1::2]), max(n[0::2]), max(n[1::2])


def tiles(dg):
    shapes = json.loads(dg.SHAPES.read_text())["shapes"]
    out = []
    for i, d in enumerate(shapes):
        x0, y0, x1, y1 = bounds(d)
        out.append({"i": i, "d": d, "name": dg.DUTY_NAMES[i], "two": dg.TWO_ACTION.get(i),
                    "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return out


def svg_body(dg, rows) -> str:
    """Nine tiles. Each carries its own path as a custom property so the dots can ride it.

    `offset-path` is the only honest way to send a dot round one of these: the effect this came
    from rotates each dot about a centre at a fixed radius, which is a description of a circle and
    of nothing else. The cost is that `offset-path` does not honour `pathLength`, so the dots take
    the same time round perimeters that differ by about 9% and drift apart. The dashes do not.
    """
    out = []
    for t in rows:
        i, d = t["i"], t["d"]
        out.append('<g class="tile" data-i="%d" style="--p:path(\'%s\')">' % (i, d))
        out.append('<path class="fillp" d="%s"/>' % d)
        out.append('<path class="edge" d="%s"/>' % d)
        out.append('<g class="markwrap">')
        for cls in ("mark", "pring-soft", "pring"):
            out.append('<path class="%s" d="%s" pathLength="%d"/>' % (cls, d, PATH_LENGTH))
        for k in range(1, 5):
            out.append('<circle class="dot d%d" cx="0" cy="0" r="7"/>' % k)
        out.append("</g>")
        cx, cy = (t["x0"] + t["x1"]) / 2, (t["y0"] + t["y1"]) / 2
        out.append('<text class="tname" x="%.1f" y="%.1f">%s</text>' % (cx, cy - 4, t["name"]))
        if t["two"]:
            out.append('<text class="tsub" x="%.1f" y="%.1f">%s &#183; %s</text>'
                       % (cx, cy + 26, t["two"][0], t["two"][1]))
        out.append('<text class="cnt" x="%.1f" y="%.1f"></text>' % (t["x0"] + 26, t["y1"] - 18))
        out.append("</g>")
    return "".join(out)


def build(dg) -> str:
    rows = tiles(dg)
    box = json.loads(dg.SHAPES.read_text())["box"]
    subs = {
        "box": box,
        "ink": dg.INK,
        "gold": dg.EDGE_HOVER,
        "sw": "%.2f" % (box * dg.EDGE_STROKE),
        "dash": dash_pattern(),
        "plen": PATH_LENGTH,
        "half": PORTAL_PERIOD,
        "segments": SEGMENTS,
        "segments2": SEGMENTS_V2,
        "ants": ANTS_DASH,
        "body": svg_body(dg, rows),
        "states": json.dumps({k: {"label": v[0], "colour": v[1], "note": v[2]}
                              for k, v in STATES.items()}),
        "effects": json.dumps(list(EFFECTS)),
        "eligible": json.dumps(list(DEMO_ELIGIBLE)),
        "counts": json.dumps(list(DEMO_COUNTS)),
        "twocount": sum(1 for t in rows if t["two"]),
    }
    return (HERE / "border_studio.html.tmpl").read_text(encoding="utf-8") % subs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", type=pathlib.Path, default=OUT)
    ap.add_argument("--open", action="store_true")
    z = ap.parse_args()

    dg = grid()
    page = build(dg)
    z.output.parent.mkdir(parents=True, exist_ok=True)
    z.output.write_text(page, encoding="utf-8")
    print("written %s  (%.1f KB)" % (z.output, z.output.stat().st_size / 1024))
    print("  9 outlines at stroke %.2f, ink %s, hover gold %s -- all read from gen_duty_grid"
          % (json.loads(dg.SHAPES.read_text())["box"] * dg.EDGE_STROKE, dg.INK, dg.EDGE_HOVER))
    print("  %d effects, %d states, portal dashes %s" % (len(EFFECTS), len(STATES), dash_pattern()))
    print("  dynamic segments: %d and %d, rebuilt per frame, normalised to pathLength %d"
          % (SEGMENTS, SEGMENTS_V2, PATH_LENGTH))
    url = z.output.resolve().as_uri()
    print("\n%s" % url)
    if z.open:
        import webbrowser
        webbrowser.open(url)


if __name__ == "__main__":
    main()
