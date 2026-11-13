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

# WHAT AN OPEN DUTY TILE WEARS, AND WHEN EACH ONE STARTS WEARING IT.
#
# A twelve-second loop of warm smoke rising off the line the Acolytes stand on, drawn on black so
# the page can screen it over the rectangle. One file; the eight tiles play it from eight
# different places so the wheel does not pulse in unison.
#
# THE STAGGER IS A RULE, NOT A TABLE. Starting at zero and alternating +1 and +2 seconds round
# the ring gives 0, 1, 3, 4, 6, 7, 9, 10 -- and the eighth step lands back on twelve, so the
# arrangement closes the loop exactly and repeats forever without two tiles ever coinciding.
# Written out as eight numbers that would be a coincidence nobody could check; written as the
# rule, `check_open_loop` below can fail the build when the clip and the stagger disagree.
OPEN_DIR = v1.BOARD / "effects"
OPEN_STEPS = (1, 2)

# ONE FILM PER PHASE, OVER THE SAME SET OF TILES. The tiles a seat's Acolytes stand on are
# marked in Action Selection and in Sowing both, because the two phases ask different things of
# one set: there it is where you may ACT, here it is where your people are STANDING before you
# move them. The set is `standsOn` either way and the FILM is what says which question is being
# asked, so the clips differ on purpose -- the Sowing one is a smoulder against the other's
# billow, measurably rather than by eye, and the record for each says by how much.
#
# KEYED BY THE PHASE KEY geometry.py PUBLISHES, so a phase with no film here simply has none and
# the page draws nothing; `ready` is in that position today.
#
# `duty_open_smoke` IS NOT A TYPO FOR `duty_action_smoke`. It was named when there was one clip
# and no phase to key it by, and renaming a file in this tree orphans its sha256 and its record.
# The map is the right place to absorb that rather than a rename that costs provenance.
FILM_STEMS = {"action": "duty_open_smoke", "sow": "duty_sow_smoke"}

# WHERE THE THREE RESOURCE CUTS LIVE, and the three keys the board asks for them by.
TITHE_DIR = v1.BOARD / "tokens" / "resources" / "icons"
# THE CORNUCOPIA IS IN THIS LIST AND IS NOT A RESOURCE. It is the WILDCARD -- the tile where the
# tithing player chooses which resource they take, as ui/concept/build_browser.py and
# tools/ui_debug/duty_wheel_layout.json's `Cornucopia (wild resource)` both have it. It is listed
# here because this list answers "which pictures does the board inline", and the board inlines
# four; it is NOT a claim that a duty handing you the choice is the same kind of offer as a duty
# handing you stone. The day that distinction has to be drawn, it is drawn in the drawing.
# THE WILDCARD, NAMED ONCE. It is in TITHE_KEYS because the board inlines its picture like the
# others, and it is named separately because the page has to know which of the four is the one
# that unions the rest in rather than being chosen itself.
TITHE_WILD = "cornucopia"
TITHE_KEYS = ("wheat", "stone", "silver", TITHE_WILD)

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
V2_TITHE = ("wheat", None, "silver", "stone", "cornucopia", "wheat", "silver", "stone")

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


# WHERE A RESOURCE'S NAME COMES FROM, which is a file and not this one.
#
# THE BOARD'S OWN RULE, stated where the controls are drawn: the wording comes from data, like
# every other string the board prints -- a labels object typed into the tool is one file
# restating another. tools/ui_debug/duty_wheel_layout.json already names all four, and
# ui/render/gen_board.py already reads that file, so this is a second reader of an existing
# source rather than a new dependency.
#
# AND IT IS NOT FATAL. A missing file or a missing key falls back to the key with a capital on
# it and SAYS SO in the build notes -- the same bargain every other missing thing on this board
# strikes. A build that refused over a caption would be refusing the wrong thing.
WHEEL_LAYOUT = v1.ROOT / "tools" / "ui_debug" / "duty_wheel_layout.json"


def tithe_names() -> tuple[dict, list]:
    """What to call each resource on screen, read from the wheel layout."""
    notes: list = []
    out = {k: k.capitalize() for k in TITHE_KEYS}
    try:
        said = json.loads(WHEEL_LAYOUT.read_text(encoding="utf-8")).get("tithe_icons", {})
    except Exception as why:
        return out, ["%s is unreadable (%s), so the resources are named after their keys"
                     % (WHEEL_LAYOUT.name, why)]
    missing = []
    for key in TITHE_KEYS:
        label = (said.get(key) or {}).get("label")
        if label:
            out[key] = label
        else:
            missing.append(key)
    if missing:
        notes.append("no label in %s for %s, so %s named after the key"
                     % (WHEEL_LAYOUT.name, ", ".join(missing),
                        "it is" if len(missing) == 1 else "they are"))
    return out, notes


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


def open_offsets() -> dict:
    """Where in the loop each duty starts, clockwise from north.

    The rule and its arithmetic in four lines: alternate the two steps round the ring. The total
    is what makes it a ring rather than a list -- see check_open_loop.
    """
    out, t = {}, 0
    for i, (slug, _name, _deg) in enumerate(G.DUTIES):
        out[slug] = t
        t += OPEN_STEPS[i % len(OPEN_STEPS)]
    return out


def open_span() -> int:
    """What the eight steps add up to, which has to be the length of the clip."""
    return sum(OPEN_STEPS[i % len(OPEN_STEPS)] for i in range(len(G.DUTIES)))


def _mp4_seconds(path: pathlib.Path) -> float | None:
    """The duration an .mp4 declares, read out of its own header.

    WHY THIS IS HERE AND NOT TAKEN ON TRUST. The stagger divides a twelve-second loop, and a clip
    that is not twelve seconds turns that from an arrangement into a collision -- two tiles on the
    same frame, which is the one thing the stagger exists to prevent. The file is the only place
    that fact lives, so this asks it rather than believing a constant.

    `mvhd` inside `moov`, which is the one box every mp4 has and the only one needed: a 32-bit
    timescale and a duration in those units (64-bit in version 1). No decoder, no dependency, and
    a file this cannot parse returns None rather than guessing -- the caller says so out loud.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None

    def walk(buf: bytes, want: bytes):
        i = 0
        while i + 8 <= len(buf):
            size = int.from_bytes(buf[i:i + 4], "big")
            kind = buf[i + 4:i + 8]
            if size == 1:                      # 64-bit extended size
                size = int.from_bytes(buf[i + 8:i + 16], "big")
                body = buf[i + 16:i + size]
            else:
                body = buf[i + 8:i + size]
            if size < 8:
                return None
            if kind == want:
                return body
            if kind in (b"moov", b"trak", b"mdia"):
                got = walk(body, want)
                if got is not None:
                    return got
            i += size
        return None

    mvhd = walk(data, b"mvhd")
    if not mvhd or len(mvhd) < 4:
        return None
    version = mvhd[0]
    try:
        if version == 1:
            scale = int.from_bytes(mvhd[20:24], "big")
            dur = int.from_bytes(mvhd[24:32], "big")
        else:
            scale = int.from_bytes(mvhd[12:16], "big")
            dur = int.from_bytes(mvhd[16:20], "big")
    except (IndexError, ValueError):
        return None
    return dur / scale if scale else None


def bundled_films() -> tuple[dict, list]:
    """One clip per phase, with the stagger they all share.

    WAS bundled_open() AND BUNDLED ONE. It became a map the moment Sowing got a film of its own,
    and the shape changed rather than a second near-copy being written: two bundlers would be two
    places to forget the record gate, the length check or the no-re-encode rule, and all three
    are the point of this function rather than decoration on it.

    THE RECORD GATES EACH ONE, exactly as it gates every picture on this board: a clip with no
    attribution entry is left out and NAMED rather than shipped. A phase whose clip is refused
    simply has none, and the page draws nothing for it -- which is the same state `ready` is in
    by having no entry here at all.

    NEWEST VERSION WINS -- `<stem>_vNN.mp4`, highest NN -- so replacing an effect is adding a
    file beside the old one rather than overwriting it and orphaning its sha256.

    INLINED RATHER THAN SERVED, which is bundled_sfx's decision and for its reasons: the page is
    opened off disk and saved with a button, and an effect living in generated/ would be a second
    file to carry. The two together cost about 250 KB of a 3 MB page.

    AND NOTHING IS RE-ENCODED ON THE WAY IN. These are each file's own bytes, base64 and no more:
    the loops were authored at 48 fps and re-encoding is the one thing that would quietly cost it.
    """
    notes: list = []
    span = open_span()
    out = {"loop": float(span), "offsets": open_offsets(), "byPhase": {}}

    if not OPEN_DIR.is_dir():
        return out, ["no effects/ at %s, so no tile is lit in any phase" % OPEN_DIR]

    rec = {}
    if v1.ATTRIB_FILE.is_file():
        rec = json.loads(v1.ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})

    for phase, stem in FILM_STEMS.items():
        found = sorted(f for f in OPEN_DIR.glob("%s_v*.mp4" % stem) if f.is_file())
        if not found:
            notes.append("no %s_vNN.mp4 in effects/, so nothing is lit in %s" % (stem, phase))
            continue
        f = found[-1]
        rel = "effects/%s" % f.name
        if rel not in rec:
            notes.append("%s: no attribution entry, left out" % rel)
            continue

        seconds = _mp4_seconds(f)
        if seconds is None:
            notes.append("%s: no duration in its header, so the %d s stagger is unchecked"
                         % (rel, span))
        elif abs(seconds - span) > 0.05:
            # NOT A WARNING. The stagger would put two tiles on the same frame, which is the
            # whole thing it exists to avoid, and a board that says so in a build note nobody
            # reads is a board that ships it. Every film is held to the same loop, because they
            # share one set of offsets and one clock: a clip of some other length would be in
            # step with the others for one cycle and adrift from then on.
            raise SystemExit(
                "%s is %.3f s and the stagger closes a %d s loop, so two duties would run in "
                "step. Either the clip or OPEN_STEPS is wrong." % (rel, seconds, span))
        else:
            # THE STAGGER IS PRINTED BY THE SUMMARY, not here. This says what each clip IS, which
            # the summary cannot: that a file was found, that its own header agrees with the loop
            # the stagger closes, and what it costs the page.
            notes.append("%s: %s, %.3f s, %d KB, inlined"
                         % (phase, rel, seconds, len(f.read_bytes()) // 1024))
        out["byPhase"][phase] = ("data:video/mp4;base64,"
                                 + base64.b64encode(f.read_bytes()).decode("ascii"))
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
    names, nnotes = tithe_names()
    films, fnotes = bundled_films()
    notes += snotes + xnotes + dnotes + cnotes + tnotes + nnotes + fnotes

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
        # WHICH RESOURCES THERE ARE AND WHICH IS WILD. The page lists a player's pool in this
        # ORDER so the box reads the same way every time, and unions the whole order in when a
        # figure stands on the wild one. Both are facts about the tree, which is what this tool
        # walks -- restated in the template they would be a second list to keep in step.
        "__TITHE__": json.dumps({"order": [k for k in TITHE_KEYS if k != TITHE_WILD],
                                 "wild": TITHE_WILD, "names": names}),
        # WHAT A MARKED TILE WEARS IN EACH PHASE, the length of the loop they share, and one
        # start offset per duty. The offsets are arithmetic here rather than a list in the
        # template for the reason every other fact on this board travels as data: a second copy
        # is a second thing to keep in step, and this one would be eight numbers that look
        # arbitrary wherever they are read.
        "__FILMS__": json.dumps(films),
        "__HOOD__": json.dumps(hood.as_dict()),
        "__SAVEKEYS__": json.dumps(v1.SAVE_KEYS),
        "__BUILD__": json.dumps({"version": v1.BUILD_VERSION + "+v2", "notes": notes}),
    }
    # AND A TOKEN WRITTEN TWICE IS THE SAME HOLE FROM THE OTHER SIDE. The check below catches a
    # token left IN the page; this catches one substituted somewhere nobody meant it to be, which
    # is not hypothetical: a comment in the stylesheet named the film bundle's own token while
    # explaining what had replaced the gradient, and the replace below duly wrote 130 KB of base64
    # video into a CSS comment. The page still worked, which is what makes it worth failing on -- it cost a
    # quarter of a megabyte and showed up as nothing but a bigger number in the build line.
    twice = sorted(t for t in fill if page.count(t) > 1)
    if twice:
        raise SystemExit(
            "the v2 template names %s more than once, so the fill would write the value into "
            "every one of them. A token in prose is still a token; say it another way."
            % ", ".join(twice))
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
    # AND THE STAGGER, IN THE SAME FORM AND FOR THE SAME REASON. Eight start times round a ring
    # are easy to get wrong by one step and impossible to see wrong in a page that is playing
    # them, so the build says what it dealt with the compass face beside each.
    off = open_offsets()
    print("  effects: %d s loop, %s, starting %s"
          % (open_span(),
             "/".join(sorted(FILM_STEMS)) or "none",
             ", ".join("%s %ds" % (G.face_of(deg), off[slug]) for slug, _, deg in G.DUTIES)))
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
