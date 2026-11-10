#!/usr/bin/env python3
"""The action board with the duty wheel replaced by nine rectangles, and three sliders to shape them.

    python3 ui/board_v2/action_board/generate_action_board_v2.py --open
    python3 ui/board_v2/action_board/generate_action_board_v2.py --serve --open

WHAT THIS IS, AND WHY IT IS A SEPARATE FILE

v1's docstring says the board has no sliders, no drag handles, no inspector and no zoom, and that
this is not an omission to be filled in later: "a board whose geometry can be nudged is a board
nobody can write a game against, and every reasonable request to `just add a control for` is how
the lab reached 3,840 lines." That is still right, and it is exactly why this is a FORK rather
than two flags on v1. v1 keeps its promise. This page breaks it on purpose, for one question.

THE QUESTION: can the duty wheel be eight rectangles and a middle?

The wheel is a drawing with eight compass faces, and the eight duties stand on them. Here they
stand on eight 2:1 rectangles in a ring instead, with a ninth in the centre. Three sliders are
the only numbers the arrangement has -- the gap between rectangles, how far the four edge
rectangles push outward, and the size of a rectangle as a percentage of what fits.

WHAT IS DIFFERENT, AND NOTHING ELSE IS

  * the wheel is not drawn, and its 59 KB of borrowed SVG is not inlined
  * the whole top band is gone -- the backdrop picture, the eight ribbon tiles and the road
    under them -- and the backdrop is not bundled either, so the page carries no copy of it
  * each duty's icons sit in the top right of its own rectangle, in a row, on a plate that is
    the ribbon tile's own ground; on the ribbon they stacked, because a 74-wide tile had no
    room to do anything else
  * the card row, the Take Tithe box and the three control marks are LIFTED to just under the
    title, into the room the band left, and the title is white because it is no longer sitting
    on a pale valley
  * the control marks keep the board's own margin on the right, which they did not before
  * the City panel is not drawn (geometry.py still publishes it -- see the template's note)
  * the bar grows three sliders and a checkbox, OUTSIDE the 1400 x 1200 canvas
  * the acolytes stand inside their duty's rectangle rather than ringing a circle, and are
    sized to the room the icon plate leaves them

THE GRID IS NOT PINNED TO ANY PUBLISHED RECT, INCLUDING GEO.wheel, WHICH IT NO LONGER READS.
It is centred at draw time in the room the lifted card row leaves -- bounded by the board's own
margin on all four sides, that margin read off the cards rather than typed. Today that is
1344 x 842 against the wheel's 1174 x 622. Change the margin, the card row or the canvas and the
grid follows; there is no 1174, 622, 28 or 1400 anywhere in the template.

EVERYTHING THAT FEEDS THE PAGE IS v1'S, IMPORTED RATHER THAN COPIED

The art walk, the attribution gate that refuses to ship a picture with no record, the seals, the
cues, the beds, the controls, the duty text and the server all come from generate_action_board by
import. Those are not design and they are not meant to diverge: a v2 that quietly stopped gating
art on the record would be a bug wearing a version number. What IS forked is the template,
because that is the design, and the design is the whole point.

WHAT THIS FORK DOES NOT HAVE: tests. tests/action_board names generate_action_board and
action_board.html.tmpl explicitly, 4,400 lines of them, and none of it reaches this file.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import generate_action_board as v1          # noqa: E402  (after the path insert, deliberately)
import hood                                 # noqa: E402  board_v2's own copy of the figure
import geometry as G                        # noqa: E402

TMPL = HERE / "action_board_v2.html.tmpl"
OUT = HERE / "generated" / "action_board_v2.html"
# NO BANNER CONSTANTS. The nine parchments and the face that lettered them are off this
# board: a rectangle carries no name at all now. THE FILES STAY WHERE THEY ARE --
# duty_actions/banners/*.webp and fonts/PirataOne-Regular.ttf, still recorded in
# attribution.json and still held by tests/action_board/test_action_board_v2_banners.py --
# because they may come back, and a resource that is deleted and re-fetched comes back as a
# different file with a different provenance. Nothing in this build reads them.

# WHERE THE SLIDERS START, AND THE ONLY PLACE THEY ARE WRITTEN DOWN. The template reads them out
# of __GRID__ rather than carrying them in the markup, so changing a default is changing this
# dict and nothing else. They are in BOARD pixels, like every other number this tool passes.
# `height` OPENS JUST OFF 100. 100 is the 2:1 rectangle this fork exists to look at and the
# slider only goes up from there; it grows the boxes UPWARD, so the line the acolytes stand on
# does not move when it is dragged.
# `bare` OPENS ON. It hides three edges of every rectangle and their ground, leaving the bottom
# line the acolytes stand on. It opened OFF while it was a way of LOOKING at a framed board;
# the frameless arrangement is now the one being judged, so that is what the page opens on and
# the frame is what you switch back to.
# NO `centre`. The City was a ninth rectangle you could switch off while it stood for nothing;
# it is where the City panel went and it holds people, so it is part of the wheel now and there
# is nothing to switch.
GRID_DEFAULTS = {"gap": 115, "disp": 60, "size": 90, "height": 130, "bare": True}


def build() -> tuple[str, list]:
    """v1's build(), with the wheel's drawing swapped for the grid's two numbers.

    The duty dict is assembled exactly as v1 assembles it -- by calling v1's own helpers -- so
    the two pages cannot disagree about what a duty is. If v1 learns a new field, this gets it.
    """
    if not TMPL.is_file():
        raise SystemExit("the v2 template is not at %s" % TMPL)

    art, by_duty, notes = v1.bundled_art()
    seals, seal_by_duty, snotes = v1.bundled_seals()
    sfx, xnotes = v1.bundled_sfx()
    beds, dnotes = v1.bundled_beds()
    controls, cnotes = v1.bundled_controls()
    notes += snotes + xnotes + dnotes + cnotes

    # THE BACKDROP IS NOT BUNDLED, because v2 does not draw it. It was the valley the ribbon of
    # eight tiles stood on, and the ribbon is gone. Carrying the picture anyway would leave 22 KB
    # of data URI in the page for an element that no longer exists, and would make "the image is
    # removed" true only of the drawing. bundled_backdrop() is not called at all, so a missing
    # or unrecorded backdrop cannot fail this build -- which is right here and would not be in v1.

    text = v1.duty_text()
    duties = {}
    for slug, name, deg in G.DUTIES:
        said = text[slug]
        entry = {"name": name, "clock": deg,
                 "actions": 1 if said.get("actionB") is None else 2}
        for slot in G.ACTIONS:
            s = said.get(slot) or {"name": None, "shortLabel": ""}
            a = by_duty.get(slug, {}).get(slot)
            w = seal_by_duty.get(slug, {}).get(slot)
            entry[slot] = {"name": s["name"], "shortLabel": s["shortLabel"],
                           "byStrength": s.get("byStrength"),
                           "art": a[0] if a else None, "artFile": a[1] if a else None,
                           "seal": w[0] if w else None, "sealFile": w[1] if w else None,
                           "sealGround": w[2] if w else None}
        duties[slug] = entry

    page = TMPL.read_text(encoding="utf-8")
    fill = {
        "__GEOMETRY__": json.dumps(G.as_dict()),
        "__DUTIES__": json.dumps(duties),
        "__CONTROLS__": json.dumps(v1.control_text()),
        "__IMAGES__": json.dumps({**art, **seals, **controls}),
        "__SFX__": json.dumps(sfx),
        "__BEDS__": json.dumps(beds),
        # NO __WHEEL_SVG__. The drawing is not inlined and geometry.WHEEL_ASSET is not read, so
        # the asset could go missing without this build noticing -- which is correct here and
        # would not be in v1.
        "__GRID__": json.dumps(GRID_DEFAULTS),
        "__HOOD__": json.dumps(hood.as_dict()),
        "__SAVEKEYS__": json.dumps(v1.SAVE_KEYS),
        "__BUILD__": json.dumps({"version": v1.BUILD_VERSION + "+v2", "notes": notes}),
    }
    for token, value in fill.items():
        page = page.replace(token, value)

    # A TOKEN LEFT IN THE PAGE IS A HOLE NOBODY WOULD SEE -- v1's rule, and it earns its keep
    # twice over on a fork, where the template and the fill are edited apart from each other.
    left = sorted(set(re.findall(r"__[A-Z_]+__", page)))
    if left:
        raise SystemExit("the v2 template still has %s in it, so the build is incomplete"
                         % ", ".join(left))
    return page, notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--open", action="store_true", help="open the page when it is built")
    ap.add_argument("--serve", nargs="?", type=int, const=8778, default=None, metavar="PORT",
                    help="serve the page on localhost so its save button can write into the "
                         "repository (default port %(const)s, one above v1's, so both can be up "
                         "at once); without this the button can only download")
    ap.add_argument("--gap", type=int, metavar="PX",
                    help="the gap the sliders open at instead of %d" % GRID_DEFAULTS["gap"])
    ap.add_argument("--disp", type=int, metavar="PX",
                    help="the edge displacement the sliders open at instead of %d"
                         % GRID_DEFAULTS["disp"])
    ap.add_argument("--size", type=int, metavar="PCT",
                    help="the rectangle size the sliders open at, as a percentage of what fits, "
                         "instead of %d" % GRID_DEFAULTS["size"])
    a = ap.parse_args()

    # SET BEFORE build() READS THEM. These are openings, not geometry: the page can be dragged to
    # any value either way, and nothing downstream is measured against them.
    if a.gap is not None:
        GRID_DEFAULTS["gap"] = a.gap
    if a.disp is not None:
        GRID_DEFAULTS["disp"] = a.disp
    if a.size is not None:
        GRID_DEFAULTS["size"] = a.size

    page, notes = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print("  wrote %s  (%d KB)" % (OUT, len(page.encode("utf-8")) // 1024))
    # WHAT THE PAGE WILL ACTUALLY DO, worked out the same way the template works it out. The
    # grid is no longer laid into GEO.wheel: v2 centres it in the room the lifted card row
    # leaves, spanning the two ACTION CARDS end to end rather than margin to margin. Printing
    # the wheel's rect here would be printing a number the page does not use.
    #
    # THIS IS A SECOND COPY OF gridArea() AND IT HAS ALREADY DRIFTED ONCE. The template's version
    # is the one that draws; this one only prints. When the span stopped being margin-to-margin
    # the template was changed and this was not, so the build cheerfully announced 1344 while the
    # page drew 1174 -- a wrong number in the one place somebody checks instead of measuring.
    # `test_the_build_summary_agrees_with_the_page` now runs both and compares them.
    d = G.as_dict()
    card, far = d["slots"]["actionA"], d["slots"]["actionB"]
    m = card["x"]
    lift = d["art"]["y"] - (d["status"]["y"] + d["status"]["height"] + 16)
    top = (card["y"] - lift) + card["height"] + m
    print("  the duty grid is centred in %d x %d at (%d, %d), margin %d, read at draw time"
          % ((far["x"] + far["width"]) - card["x"], d["canvas"]["height"] - top - m,
             card["x"], top, m))
    print("  sliders open at gap %d, edge %d, size %d%%, height %d%%, bare %s"
          % (GRID_DEFAULTS["gap"], GRID_DEFAULTS["disp"], GRID_DEFAULTS["size"],
             GRID_DEFAULTS["height"], "on" if GRID_DEFAULTS["bare"] else "off"))
    for n in notes:
        print("  note: %s" % n)

    if a.serve is not None:
        v1.serve(OUT, a.serve, a.open)
    else:
        print("  NOT SERVED -- the save button can only download. Add --serve to write "
              "into the repository.")
        if a.open:
            webbrowser.open(OUT.as_uri())


if __name__ == "__main__":
    main()
