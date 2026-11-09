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
import base64
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
BANNER_DIR = HERE.parent / "duty_actions" / "banners"
# THE FONT IS NOT IN duty_actions/ AND THE TESTS ARE WHY, which is worth writing down because
# the obvious place to put it was beside the banners it letters. Two guards refuse that. A .ttf
# is not in `imageSuffixes`, so the asset walk cannot see it and a record for it reads as a
# record naming a file that is not in the tree; and `test_the_stated_default_is_written_down`
# holds that EVERY recorded entry under duty_actions/ and tokens/ carries `openai-generated`,
# which an OFL face from Google Fonts plainly does not. Between them they say duty_actions/ is
# for this project's generated artwork, so a third-party font lives next door and carries its
# licence text with it, which is what the OFL asks.
BANNER_FONT = HERE.parent / "fonts" / "PirataOne-Regular.ttf"

# HOW A TITLE SITS ON ITS PARCHMENT. Carried over whole from
# tools/ui_debug/generate_duty_board_check.py, which is where the sow page gets them and where
# they were found by looking: the blanks are BLANK, so every one of these four numbers is about
# where the lettering goes rather than about the art.
BANNER_TOP = 0.502           # of the banner's own height: where the parchment's middle sits
BANNER_FS = 29.0 / 64.0      # font size as a fraction of banner height
BANNER_TRACK = 0.025         # letter-spacing, em
BANNER_INK = "#201b17"

# WHERE THE SLIDERS START, AND THE ONLY PLACE THEY ARE WRITTEN DOWN. The template reads them out
# of __GRID__ rather than carrying them in the markup, so changing a default is changing this
# dict and nothing else. They are in BOARD pixels, like every other number this tool passes.
GRID_DEFAULTS = {"gap": 20, "disp": 40, "size": 100, "centre": True}


def bundled_banners() -> tuple[dict, str, list]:
    """The nine parchments and the face that letters them, inlined, from board_v2's own copies.

    NOT READ OUT OF ui/assets-gothic/, WHICH IS THE POINT OF THE COPY. The sow page reads the
    2172 px PNGs and the font straight from the older trees; this build reads neither, so a
    change there cannot alter this board and the guards on each tree stay on their own side of
    the fence. What each file came from is in attribution.json, which is where provenance goes.

    THE RECORD GATES THESE TOO, by the rule every other picture on this board follows: a file
    with no entry is left out and NAMED rather than inlined. The art is already at its shipped
    size, so unlike bundled_art() there is nothing to resample here -- it is base64 and nothing
    else.

    A MISSING FONT IS A NOTE, NOT A FAILURE. The sow page returns empty and says which, because
    a page with no banners is still worth looking at; the same choice here, and the titles fall
    back to the serif the stylesheet names after `PB`.
    """
    notes: list = []
    out: dict = {}
    if not BANNER_DIR.is_dir():
        return out, "", ["no duty_actions/banners/, so the rectangles carry no titles"]

    recorded = set()
    if v1.ATTRIB_FILE.is_file():
        rec = json.loads(v1.ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})
        recorded = {k for k, e in rec.items() if e.get("state", "present") == "present"}

    for slug, _name, _deg in G.DUTIES:
        out[slug] = None
    out["city"] = None
    for slug in list(out):
        f = BANNER_DIR / ("%s_banner_v01.webp" % slug)
        key = "duty_actions/banners/%s_banner_v01.webp" % slug
        if not f.is_file():
            notes.append("no banner for %s, so its rectangle keeps a plain title" % slug)
            continue
        if key not in recorded:
            notes.append("%s has no attribution entry, so it is left out" % key)
            continue
        out[slug] = "data:image/webp;base64," + base64.b64encode(f.read_bytes()).decode("ascii")

    # THE FONT IS NOT GATED ON THE RECORD, unlike every picture here, because it cannot be in
    # the record -- see BANNER_FONT above. Its provenance is ui/board_v2/fonts/OFL.txt beside it
    # and the full entry in ui/assets/attribution.json, which names the same sha256.
    font = ""
    if BANNER_FONT.is_file():
        font = ("data:font/ttf;base64,"
                + base64.b64encode(BANNER_FONT.read_bytes()).decode("ascii"))
    else:
        notes.append("%s is missing, so banner titles fall back to a serif" % BANNER_FONT.name)
    return out, font, notes


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
    banners, banner_font, bnotes = bundled_banners()
    notes += snotes + xnotes + dnotes + cnotes + bnotes

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
        "__BANNERS__": json.dumps(banners),
        "__HOOD__": json.dumps(hood.as_dict()),
        "__BANNERFONT__": json.dumps(banner_font),
        "__BANNERMETA__": json.dumps({"top": BANNER_TOP, "fs": BANNER_FS,
                                      "track": BANNER_TRACK, "ink": BANNER_INK}),
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
    # grid is no longer laid into GEO.wheel: v2 centres it in the room left once the card row
    # is lifted, bounded by the board's own margin on all four sides. Printing the wheel's rect
    # here would be printing a number the page does not use.
    d = G.as_dict()
    m = d["slots"]["actionA"]["x"]
    lift = d["art"]["y"] - (d["status"]["y"] + d["status"]["height"] + 16)
    top = (d["slots"]["actionA"]["y"] - lift) + d["slots"]["actionA"]["height"] + m
    print("  the duty grid is centred in %d x %d at (%d, %d), margin %d, read at draw time"
          % (d["canvas"]["width"] - 2 * m, d["canvas"]["height"] - top - m, m, top, m))
    print("  sliders open at gap %d, edge %d, size %d%%, centre %s"
          % (GRID_DEFAULTS["gap"], GRID_DEFAULTS["disp"], GRID_DEFAULTS["size"],
             "on" if GRID_DEFAULTS["centre"] else "off"))
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
