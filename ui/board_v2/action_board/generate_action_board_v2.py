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
# `divide` IS HOW FAR IN FRONT OF THE TITHE RESOURCE THE DIVIDER STANDS, in board pixels, and it
# opens at half the clear ground a two-action duty has at these settings -- 24px between the last
# mark and the resource, so 12 puts the line in the middle of it. It is measured leftward from the
# resource because the resource is the thing on that frame that never moves.
GRID_DEFAULTS = {"gap": 115, "disp": 60, "size": 90, "height": 130, "divide": 12, "bare": True}

# WHERE THE THREE RESOURCE CUTS LIVE, and the three keys the board asks for them by.
TITHE_DIR = v1.BOARD / "tokens" / "resources" / "icons"
TITHE_KEYS = ("wheat", "stone", "silver")

# WHICH TITHE RESOURCE SITS BESIDE EACH DUTY'S ICONS, read CLOCKWISE FROM NORTH.
#
# DEMO STATE, FLAGGED LIKE V2_SEATS AND FOR THE SAME REASON. These are to be dealt at setup; until
# there is a setup to deal them the board needs eight answers to look at, and inventing them in the
# template would put game state in the drawing. The day setup deals them this constant is what gets
# deleted, and the template reads `d.tithe` either way.
#
# A TUPLE AGAINST G.DUTIES RATHER THAN A DICT OF SLUGS, which is the whole point of writing it this
# way. G.DUTIES is in clock order -- north at 0 degrees and 45 clockwise per step, which `face_of`
# derives rather than lists -- so this reads down the page in the order you would walk the ring, and
# zipping the two means a duty added, removed or reordered in geometry.py fails HERE instead of
# quietly pairing Produce's resource with Construct's tile. The zip is length-checked below for the
# same reason: zip() is happy to be handed seven.
V2_TITHE = ("wheat", None, "silver", "stone", "wheat", "wheat", "silver", "stone")

# TAXATION IS None AND THAT IS NOT "nothing" SPELLED DIFFERENTLY. A duty with no resource gets no
# FRAME either, which is a different drawing from an empty frame -- an empty frame says "a resource
# belongs here and is missing", and what is true of Taxation is that none belongs. `None` is the
# only value the template tests, so this is the one place the distinction is made.


def tithe_by_duty() -> dict:
    """Each duty's resource key, or None, paired off against geometry's own clock order."""
    if len(V2_TITHE) != len(G.DUTIES):
        raise SystemExit("V2_TITHE names %d resources and geometry publishes %d duties"
                         % (len(V2_TITHE), len(G.DUTIES)))
    bad = sorted({k for k in V2_TITHE if k is not None} - set(TITHE_KEYS))
    if bad:
        raise SystemExit("V2_TITHE names %s, which is not one of %s"
                         % (", ".join(bad), ", ".join(TITHE_KEYS)))
    return {slug: key for (slug, _, _), key in zip(G.DUTIES, V2_TITHE)}


def bundled_tithe() -> tuple[dict, list]:
    """The three resource cuts, inlined at twice the size the board draws them.

    v1's bundled_controls() ONE ROOT OVER, and it is a separate function rather than a call
    because v1 has no tithe frame to bundle for: adding the resources to v1's bundler would put
    22 KB of picture into a page that draws none of it. What IS shared is everything that makes
    the rule a rule -- `_inline`, `image_suffixes`, the record, the newest-version walk -- so the
    two cannot disagree about what gating an image means.

    THE RECORD GATES THESE TOO. A cut with no attribution entry is left out and NAMED rather than
    guessed into a frame, which is the rule every other picture on this board is held to.

    NEWEST VERSION WINS: `resource_<key>_icon_vNN.webp`, highest NN, so replacing a resource is
    adding a file rather than overwriting one and orphaning its sha256.

    A MISSING RESOURCE IS SAID OUT LOUD AND THE BOARD STILL DRAWS. The frame appears with nothing
    in it, which is visibly unfinished -- unlike a frame silently not drawn, which is
    indistinguishable from Taxation, the one duty whose empty right-hand side is correct.
    """
    notes: list = []
    out: dict = {}
    if not TITHE_DIR.is_dir():
        return out, ["no tokens/resources/icons/ at %s, so the tithe frames draw empty"
                     % TITHE_DIR]
    rec = {}
    if v1.ATTRIB_FILE.is_file():
        rec = json.loads(v1.ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})
    want = v1.image_suffixes()
    for key in TITHE_KEYS:
        found = sorted(f for f in TITHE_DIR.glob("resource_%s_icon_v*" % key)
                       if f.is_file() and f.suffix.lower() in want)
        if not found:
            notes.append("no cut for the %s resource, so its frame draws empty" % key)
            continue
        f = found[-1]
        rel = "tokens/resources/icons/%s" % f.name
        if rel not in rec:
            notes.append("%s: no attribution entry, left out" % rel)
            continue
        out["tithe:%s" % key] = v1._inline(f, (G.MARK * 2, G.MARK * 2), "PNG")
    return out, notes


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
    tithe, tnotes = bundled_tithe()
    notes += snotes + xnotes + dnotes + cnotes + tnotes

    # THE BACKDROP IS NOT BUNDLED, because v2 does not draw it. It was the valley the ribbon of
    # eight tiles stood on, and the ribbon is gone. Carrying the picture anyway would leave 22 KB
    # of data URI in the page for an element that no longer exists, and would make "the image is
    # removed" true only of the drawing. bundled_backdrop() is not called at all, so a missing
    # or unrecorded backdrop cannot fail this build -- which is right here and would not be in v1.

    text = v1.duty_text()
    byduty = tithe_by_duty()
    duties = {}
    for slug, name, deg in G.DUTIES:
        said = text[slug]
        entry = {"name": name, "clock": deg,
                 "actions": 1 if said.get("actionB") is None else 2,
                 # THE KEY, NOT THE PICTURE. The page looks the image up in IMAGES by
                 # `tithe:<key>` exactly as it does a seal, so a duty whose resource has no cut
                 # yet still knows it HAS one and draws the frame.
                 "tithe": byduty[slug]}
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
        "__IMAGES__": json.dumps({**art, **seals, **controls, **tithe}),
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
    # WHAT WAS DEALT, IN THE ORDER IT WILL BE WALKED. Eight placeholders are the kind of thing
    # that goes unlooked-at for weeks, and the ring is the one property of them that is easy to
    # get wrong by one step -- so the build reads it out with the compass face beside each, which
    # is the form the mistake would be visible in.
    ring = tithe_by_duty()
    print("  tithe ring: %s"
          % ", ".join("%s %s" % (G.face_of(deg), ring[slug] or "none")
                      for slug, _, deg in G.DUTIES))
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
