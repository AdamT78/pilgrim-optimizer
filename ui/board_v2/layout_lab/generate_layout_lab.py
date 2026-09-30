#!/usr/bin/env python3
"""Generate the Duty Wheel Layout Lab -- a standalone page for deciding the module's geometry.

WHAT THIS IS FOR. The Duty Wheel module is a fixed 1400x1200 composition that will be dropped
unchanged into a wider full-board canvas. Everything about it -- how big the wheel is, what the
player reads while deciding, where the scenic action artwork goes, where the City goes, whether
four realistically sized acolytes still read on one duty -- is a visual decision that cannot be
made from numbers. So this page exists to make those decisions by moving things, and then to
hand back the exact coordinates.

WHY A GENERATOR RATHER THAN A HAND-WRITTEN PAGE. The duty list, the design envelope and the
starting geometry are facts that belong in one place. Written straight into HTML they would be
facts in a file nothing else can read; here they are module constants that the tests import and
assert against, and the page is built from them.

WHAT CHANGED IN V4 -- the composition, again, and this time it is the arrangement rather than
the canvas. The canvas has not moved: still 1400x1200.

  THE WHEEL TAKES THE BOTTOM AND ALMOST ALL THE WIDTH. 1372 wide at y=438, finishing at 1165
  with 35px of margin under it. V3 left a wide empty strip down there and spent width on margins
  either side of a 950 wheel; V4 spends the height instead. The wheel is now the dominant object
  by a long way, which is what it is on the table.

  SO EVERY PIECE OF INTERFACE MOVES ABOVE IT, into three bands:

      y  10.. 65   one line of instruction, and nothing else
      y  78..228   eight duty reference cards in ONE row, north then clockwise
      y 240..424   the two scenic action artworks, then Tithe, then the City

  THREE STATES, not two. READY/CITY is new: the turn before anything has been picked up. The
  duty cards are reference material in all three -- clicking one PREVIEWS its two actions
  without choosing anything -- and only in ACTION SELECTION does the artwork become a choice and
  Tithe appear at all.

  THE WHEEL'S CENTRE IS DELIBERATELY EMPTY. V3.1 put the in-hand pool and then Tithe there. Both
  have left: Tithe is a card in the band, and the acolytes in hand take over the City's region
  while sowing, which is where the eye already is.

  NOTHING IDENTIFIES A DUTY SPACE ON THE WHEEL. No labels, no plaques, no icons, no landmarks --
  that question is open and is not this file's to answer. The ribbon of cards carries the names.

  A V1, V2 or V3 file still opens: see MIGRATION in the template.

NOTHING HERE TOUCHES THE FIRST BOARD DESIGN. No file under tools/ui_debug is read or written,
and no metadata under ui/assets-gothic is either. See ui/board_v2/README.md.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE / "duty_wheel_layout_lab.html.tmpl"
OUT = HERE / "generated" / "duty_wheel_layout_lab.html"

# =============================================================================================
# THE BUILT-IN WHEEL.
#
# A COPY, NOT AN IMPORT. The drawing is the v2 duty wheel AT AN ASPECT OF 1.887, built by
# tools/ui_debug/build_duty_wheel_v2.py, and this file deliberately does not import, exec or
# reach into that tree: this module is read by a test suite and by people who only care about the
# layout, and a path into the other tool would make its argparse, its numpy dependency and its
# open questions all things that have to be true for a page to be generated here.
#
# 1.887 IS A DIFFERENT DRAWING, not the 1.778 one squashed. The faces are built from the ellipse
# and the spokes, and the hub is held as a proportion of the rim, so changing the aspect rebuilds
# the geometry. The 1.778 baseline in `tools/ui_debug/prototypes/` is untouched and still belongs
# to that tool. To refresh this copy:
#
#     python3 tools/ui_debug/build_duty_wheel_v2.py --aspect 1.887 \
#         --out duty_wheel_v2_1887_layout.json
#     python3 - <<'EOF'
#     import pathlib, sys; sys.path.insert(0, ".")
#     from tools.ui_debug.render_duty_wheel_v2 import (
#         load_duty_wheel_v2_layout, render_duty_wheel_v2_svg)
#     lay = load_duty_wheel_v2_layout(
#         pathlib.Path("tools/ui_debug/duty_wheel_v2_1887_layout.json"))
#     pathlib.Path("ui/board_v2/layout_lab/assets/duty_wheel_v2.svg").write_text(
#         render_duty_wheel_v2_svg(lay, standalone=True), encoding="utf-8")
#     EOF
#
# THE COPY IS THE BUILDER'S OWN COLOURS and the recolour happens here, at build time -- see
# WHEEL_PALETTE. Hand-editing a generated file is how a file stops being regenerable, and this
# tree's rule is that a layout nothing can regenerate quietly becomes wrong.
#
# The copy is checked in rather than generated, so the lab's page is reproducible from this tree
# alone. Nothing downstream of it re-projects it -- see WHEEL_RATIO below.
# =============================================================================================
WHEEL_ASSET = HERE / "assets" / "duty_wheel_v2.svg"

# THE GREYS ARE THE ONES THE PLACEHOLDER WORE. The drawing is built in parchment -- cream faces
# on dark board -- which is the first board design's palette, not this one's. The lab composes
# against pure black with scenic art that fades into it, and the stand-in this wheel replaced was
# slate: a mid-grey face, a darker hub, a darker base again. Keeping those three keeps every
# judgement made against the placeholder -- acolyte contrast, the reached-duty mark, how much the
# artwork above can carry -- still worth something.
#
# EVERY ENTRY MUST MATCH SOMETHING. A palette that silently stopped applying would leave a cream
# wheel on a black field and no error, so recolour() counts the substitutions and fails loudly
# rather than shipping the wrong colours.
WHEEL_PALETTE = {
    "#efe3c8": "#3a3d45",   # face   -> the placeholder's segment slate
    "#e8dcc0": "#23262b",   # centre -> its darker hub
    "#17130d": "#2b2e34",   # ground -> its base ellipse (hidden by default; see wheel.ground)
}


def recolour(text: str, palette: dict = None) -> str:
    """Swap the builder's parchment for the lab's slate, and refuse to do it quietly.

    Case-insensitive because an SVG writer is free to emit #EFE3C8, and every key has to be
    found: a palette that matched nothing would leave a cream wheel on a black field with no
    error anywhere, which is precisely the failure this function exists to prevent.
    """
    palette = WHEEL_PALETTE if palette is None else palette
    for old, new in palette.items():
        pattern = re.compile(re.escape(old), re.IGNORECASE)
        text, n = pattern.subn(new, text)
        if not n:
            raise SystemExit("the built-in wheel has no %s in it, so the lab's palette no longer "
                             "describes the drawing it is colouring" % old)
    return text


def wheel_svg(text: str = None) -> str:
    """The asset, stripped of its XML declaration and recoloured, ready to inline.

    Taking the argument makes the parsing testable without the file, which is the half of this
    that can be wrong in a way nobody would see: an `<?xml ... ?>` left in the middle of a page
    is not an error, it is a processing instruction the browser ignores, and the wheel would
    still draw.
    """
    if text is None:
        text = WHEEL_ASSET.read_text(encoding="utf-8")
    return recolour(re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", text).strip())


def viewbox_of(text: str) -> tuple:
    """The asset's own `viewBox`, which is the authority on its shape.

    NOT its width/height attributes and not what a browser would report for it: a drawing
    exported for a board is typically responsive, and a browser asked for the natural size of one
    of those answers 300x150 -- a ratio of 0.5, close enough to a real foreshortening to look
    plausible while being wrong. The page applies the same rule to an SVG somebody loads.
    """
    m = re.search(r'\bviewBox\s*=\s*"\s*([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s*"',
                  text)
    if not m:
        raise SystemExit("the built-in wheel has no viewBox, so its shape is not knowable")
    w, h = float(m.group(3)), float(m.group(4))
    if not (w > 0 and h > 0):
        raise SystemExit("the built-in wheel's viewBox is %s x %s" % (w, h))
    return w, h

# The schema version. V1 had one artwork per duty; V2 split it into two with a box each; V3 took
# the boxes away and gave the assets to two shared slots. V4 rearranges the composition and adds
# a third state, which is a real change of shape -- the summaries become a ribbon, the two
# wheel-centre medallions retire, the status line loses its context field -- so the version moves
# with it and older files are migrated rather than reinterpreted.
STATE_VERSION = 4
BUILD_VERSION = "4.5"

# ---- the design envelope -------------------------------------------------------------------
CANVAS_W, CANVAS_H = 1400, 1200

# The full-board canvases this module is meant to sit inside. 1600x1200 is deliberately absent:
# a 1400-wide module inside it leaves 200px for everything else.
FULL_BOARD_CANVASES = (2039, 2283)

# ---- the eight duties ----------------------------------------------------------------------
# The engine's own vocabulary, from DUTY_CATEGORIES in pilgrim/model/duties.py, so a layout
# exported here names duties the same way the game does. THE CITY IS NOT HERE: merchant.py sets
# CITY_POSITION = 0 and the valid duty range is 1..8.
#
# THE ORDER IS THE WHEEL'S OWN, north then clockwise, and the ribbon is built in this order --
# so a card's place in the row is its duty's place on the wheel, which is the only association
# the player gets now that nothing on the wheel is labelled.
#
# THE ACTION NAMES ARE STARTING TEXT and every one stays editable. Taxation's two are left as
# THE ACTION WORDING IS NOT HERE ANY MORE. It moved to ../duty_text.json, which the UI edits
# constantly and which also records the engine action each box answers to; leaving a copy in this
# tuple would have meant two files disagreeing about what a card says the first time one of them
# was edited alone. What stays is what this file is actually for: the slug, the duty's own name,
# and the angle its space sits at on the wheel.
DUTIES = (
    ("clerical",    "Clerical",    0),
    ("taxation",    "Taxation",    45),
    ("produce",     "Produce",     90),
    ("build_roads", "Build Roads", 135),
    ("construct",   "Construct",   180),
    ("give_alms",   "Give Alms",   225),
    ("ordination",  "Ordination",  270),
    ("allocation",  "Allocation",  315),
)

DUTY_TEXT_ASSET = HERE.parent / "duty_text.json"


def duty_text() -> dict:
    """What each action box says, read rather than retyped.

    LOUD ON ANYTHING MISSING. A duty with no entry, or a slot with no `shortLabel`, is a card that
    would draw with a blank caption and look finished -- so the build stops instead. `name` may be
    null, because the duty action names are still being decided and a box without one simply does
    not draw its top line; `shortLabel` may not, because that is the caption the card has always
    had.
    """
    import json
    if not DUTY_TEXT_ASSET.is_file():
        raise SystemExit("ui/board_v2/duty_text.json is missing; it owns what the action boxes "
                         "say and nothing here has a copy")
    data = json.loads(DUTY_TEXT_ASSET.read_text(encoding="utf-8")).get("duties", {})
    out = {}
    for slug, _name, _angle in DUTIES:
        entry = data.get(slug)
        if not entry:
            raise SystemExit("duty_text.json has no entry for %r" % slug)
        slots = {}
        for key, _ in ACTIONS:
            slot = entry.get(key, "missing")
            # A NULL actionB IS A DUTY WITH ONE ACTION, not an oversight -- Taxation and
            # Allocation have one each. It is spelled null rather than left out so that a typo in
            # the key still fails loudly; `entry.get(key)` alone could not tell the two apart.
            if slot is None:
                if key == ACTIONS[0][0]:
                    raise SystemExit("duty_text.json: %s has no first action, which no duty "
                                     "can be missing" % slug)
                slots[key] = None
                continue
            if not isinstance(slot, dict):
                raise SystemExit("duty_text.json: %s has no %s" % (slug, key))
            label = slot.get("shortLabel")
            if not isinstance(label, str) or not label.strip():
                raise SystemExit("duty_text.json: %s/%s has no shortLabel, so its card would "
                                 "draw an empty caption" % (slug, key))
            name = slot.get("name")
            if name is not None and (not isinstance(name, str) or not name.strip()):
                raise SystemExit("duty_text.json: %s/%s has a blank name. Use null for 'not "
                                 "decided'; a blank string is indistinguishable from a mistake"
                                 % (slug, key))
            slots[key] = {"name": name, "shortLabel": label}
        out[slug] = slots
    return out

ACTIONS = (("actionA", "Action A"), ("actionB", "Action B"))

# ---- the wheel -----------------------------------------------------------------------------
# THE SHAPE IS THE ASSET'S AND THE SIZE FOLLOWS FROM IT. The built-in wheel is 1000 x 562.4 in
# its own viewBox -- an aspect of 1.778 -- so the ratio is read from the drawing rather than
# derived from an elevation this file picked. The implied elevation is asin(0.5624) = 34.2
# degrees, which is reported and never used as an input; setting it the other way round would be
# this module having an opinion about a drawing it did not make.
#
# WHICHEVER BOUND BINDS. The module is a fixed 1400 x 1200 with the action band ending at 424, so
# the wheel has two ceilings: the width less a margin each side, and the height left under the
# band. Which one bites depends entirely on the drawing's aspect, and that is not this file's to
# choose -- so both are computed and the smaller wins.
#
# At 1.887 (ratio 0.5299) the WIDTH runs out first: 1372 wide is 727 high and finishes at 1165,
# leaving 35px of module under it that nothing is reserved for. At 1.778 (0.5624) it was the
# other way round -- a full-width wheel would have been 772 high and hung 10px off the bottom --
# and the wheel came out 1354 x 761 with wider margins. Both are correct for their drawing, which
# is the point of deriving it rather than writing the numbers down.
WHEEL_VIEW_W, WHEEL_VIEW_H = viewbox_of(wheel_svg())
WHEEL_RATIO = WHEEL_VIEW_H / WHEEL_VIEW_W
WHEEL_ASPECT = WHEEL_VIEW_W / WHEEL_VIEW_H
WHEEL_ELEVATION_DEG = round(math.degrees(math.asin(WHEEL_RATIO)), 1)

WHEEL_Y = 438
# The smallest side margin worth keeping: enough that the wheel does not touch the module's edge,
# and no more, because there is nothing to put there.
WHEEL_MARGIN_MIN = 14
_fits_width = CANVAS_W - 2 * WHEEL_MARGIN_MIN
_fits_height = int((CANVAS_H - WHEEL_Y) / WHEEL_RATIO)
# Even, so the two side margins are the same whole number of pixels.
WHEEL_W = min(_fits_width, _fits_height) // 2 * 2
WHEEL_H = round(WHEEL_W * WHEEL_RATIO)
WHEEL_X = (CANVAS_W - WHEEL_W) // 2
WHEEL_CX, WHEEL_CY = WHEEL_X + WHEEL_W / 2, WHEEL_Y + WHEEL_H / 2
WHEEL_BOUND = "width" if _fits_width <= _fits_height else "height"
# 32 DEGREES IS A DESIGN INVARIANT and the rest of the composition is built on it, so the
# drawing is CHECKED against it rather than merely followed. Re-rendering the built-in wheel at
# another aspect is a decision about the whole module, and it fails here rather than silently
# moving the wheel's lower edge and every acolyte with it.
#
# A function rather than a bare assert so the refusal itself can be tested: an invariant whose
# only expression is a line that happens to be true today is not being checked, it is being
# hoped for.
DESIGN_RATIO = 0.5299
RATIO_TOLERANCE = 0.0005


def check_design_ratio(ratio: float) -> float:
    if abs(ratio - DESIGN_RATIO) > RATIO_TOLERANCE:
        raise SystemExit(
            "the built-in wheel is %.4f, not the %.4f the layout is designed around. That is a "
            "decision about the whole module -- the wheel's lower edge, the acolyte ring and the "
            "action band all follow from it -- so it is refused here rather than applied quietly."
            % (ratio, DESIGN_RATIO))
    return ratio


check_design_ratio(WHEEL_RATIO)
assert WHEEL_Y + WHEEL_H <= CANVAS_H, "the wheel runs off the bottom of the module"
assert WHEEL_X >= WHEEL_MARGIN_MIN - 1, "the wheel runs off the side of the module"

# ---- band 1: the instruction ------------------------------------------------------------------
# ONE LINE AND NOTHING ELSE. V3 carried a small context field above it -- SOW, CLERICAL -- which
# said what the rest of the screen was already saying. Centred light text on the dark field: no
# parchment, no frame, nothing that competes with the wheel.
STATUS = {"x": 28, "y": 10, "width": 1344, "height": 55}
STATUS_SIZE = 30

# ---- band 2: the duty reference ribbon ----------------------------------------------------------
# Eight cards in one row, in wheel order. They are REFERENCE, not controls: clicking one previews
# its two scenic actions and chooses nothing, in every state.
#
# 150 TALL BECAUSE THE SEALS ARE 34. V3's summaries were short enough that an action seal had to
# be about 18px, which is too small to ever hold a readable pictorial icon. The height was bought
# from the empty strip that used to sit under the wheel.
RIBBON = {"x": 28, "y": 78, "width": 1344, "height": 150}
CARD_GAP = 10
CARD_W = (RIBBON["width"] - (len(DUTIES) - 1) * CARD_GAP) // len(DUTIES)
CARD_X0 = RIBBON["x"] + (RIBBON["width"] - (len(DUTIES) * CARD_W
                                            + (len(DUTIES) - 1) * CARD_GAP)) // 2
SEAL_SIZE = 34

# ---- band 3: artwork, Tithe, City ----------------------------------------------------------------
# The row runs left to right in the order the player reads it: the two actions that belong
# together, then the alternative to them, then the reserve that is not a choice at all.
BAND = {"x": 28, "y": 240, "width": 1344, "height": 184}

# The first artwork's left edge lines up with the first duty card's, so a duty's card and its
# artwork share a vertical.
ART_W, ART_GAP = 375, 15
ART_LEFT = {"x": BAND["x"], "y": BAND["y"], "width": ART_W, "height": BAND["height"]}
ART_RIGHT = {"x": BAND["x"] + ART_W + ART_GAP, "y": BAND["y"],
             "width": ART_W, "height": BAND["height"]}

# Immediately right of the second artwork, and visibly a different kind of thing: Tithe is the
# alternative to taking a duty action, not a third action. No "OR" anywhere -- the card being a
# separate card is the separation.
TITHE = {"x": ART_RIGHT["x"] + ART_W + 10, "y": BAND["y"], "width": 178,
         "height": BAND["height"]}

# The remaining width on the right. Subordinate to the artwork on purpose.
CITY = {"x": TITHE["x"] + TITHE["width"] + 12, "y": BAND["y"],
        "width": BAND["x"] + BAND["width"] - (TITHE["x"] + TITHE["width"] + 12),
        "height": BAND["height"]}

# The three resources a tithe can pay, as a pyramid: one over two. The letters are placeholders
# for icons and are deliberately not the words -- spelling out Wheat, Stone and Silver would be
# designing around the icons not existing yet.
TITHE_RESOURCES = (("W", "Wheat"), ("S", "Stone"), ("Ag", "Silver"))

# THE TOKEN DEFAULTS ARE THE CURRENT RENDERING, NOT ROUND NUMBERS. The placeholder disc is 38px
# and the two rows sit 7px apart with 9px between the lower pair, so opening this build with no
# icons loaded has to reproduce exactly that rather than quietly enlarging the card. The brief
# suggested 50 and 8-10; those would have grown the pyramid on first open, which its own section
# 6 rules out ("preserve the current overall Tithe composition rather than enlarge the card").
#
# ONE GAP, and it cannot match both axes. 9 is the horizontal value and the more visible one, so
# the vertical spacing moves 7 -> 9: two pixels inside a fixed card, nothing outside it moves.
TOKEN_SIZE_DEFAULT = 38
# THE SIDE OF AN EQUILATERAL TRIANGLE whose VERTICES the three token centres sit on: apex above,
# two below. Centres, not edges -- which is the whole reason for it. Edge-to-edge spacing couples
# the two decisions, because growing a token then pushes its neighbours apart as well; pinning
# the centres to a triangle makes size and spacing genuinely independent, so one slider changes
# how big the tokens are and the other changes how far apart they sit, and neither disturbs the
# other. 47 reproduces the old 38px discs at a 9px gap.
TOKEN_SPREAD_DEFAULT = 47
# NO PER-TOKEN SCALE. The three tokens are one size, full stop. The reason that is safe is that
# the ARTWORK was corrected instead: the source motifs filled their squares unequally -- the
# solid disc was 90.6% of the square for stone, 84.7% for wheat and 80.2% for silver, so silver
# read about a ninth small -- and the production PNGs are re-exported so all three now measure
# 0.906. The untouched originals are kept beside them in tokens/masters/. Correcting the picture
# is better than carrying a correction factor in the layout forever.

SAFE_MARGIN = 50

# ---- the layout helpers' control ranges --------------------------------------------------------
# STUDIO ONLY. These bound the sliders in the LAYOUT HELPERS panel and never reach the game
# layout: they say what is worth trying while composing, not what the module is. They are here
# rather than in the template so a test can read them, and so the one place that knows the
# module's dimensions is the one place that bounds controls against them.
#
# The wheel's upper bound is the canvas itself -- a wheel that touches both edges is a
# composition somebody may want to look at, and the auto-centre makes it symmetrical rather than
# off-centre. The artwork's lower bound is the smallest box worth judging a scenic illustration
# in, and FIT ACTION ROW refuses rather than going under it.
HELPER_RANGES = {
    "wheelW": [600, CANVAS_W],
    "cardH": [80, 300],
    "artW": [150, 600],
    "artH": [80, 400],
    # THE TOP OF THESE RANGES IS PAST WHAT THE CARD HOLDS, deliberately. The Tithe box is
    # 178 x 184 and never follows the tokens, so a size of 160 crowds and then clips -- which is
    # the trade-off the fixed region exists to show. A slider that stopped at the comfortable
    # size would be deciding the composition instead of reporting it.
    "tokenSize": [28, 160],
    "tokenSpread": [0, 200],

    "gap": [0, 80],
    # What FIT ACTION ROW leaves at the right-hand end: the band's own right margin, so a fitted
    # row ends where the ribbon above it does.
    "rowRight": CANVAS_W - (BAND["x"] + BAND["width"]),
}

# The figure anchors ring the wheel's own face, as a fraction of the wheel so they scale with it.
#
# MEASURED AGAINST THE REAL FACES, not chosen. Since the built-in drawing is inlined in the page,
# every anchor can be mapped into its viewBox and handed to isPointInFill, so "is this row
# standing on its own face" is a question with an answer rather than something to squint at.
# At 0.385/0.34 every anchor and both ends of every row land on that duty's own face, with 62 to
# 82 asset units of clearance to the nearest edge -- the best of the fractions tried.
#
# 0.34 RATHER THAN 0.40 VERTICALLY is the other half, and it is a finding too: at 0.40 a 120px
# acolyte standing at 12 o'clock reaches up past the wheel's top edge and into the action band,
# where it draws over the artwork. On the taller 1.778 wheel that clearance is 16px; it was 10px
# on the sin(32) one, so the asset change bought a little room rather than costing it.
FIG_RX, FIG_RY = round(WHEEL_W * 0.385), round(WHEEL_H * 0.34)

# ---- acolytes -------------------------------------------------------------------------------
ACOLYTE_MIN, ACOLYTE_MAX, ACOLYTE_DEFAULT = 90, 210, 120
ACOLYTE_ASPECT = 0.42

# The City's representative figures and the in-hand one stand for a pool rather than for a piece
# on the board, and they now live in a 184-tall band rather than beside the wheel -- so they are
# a good deal smaller than a duty's acolytes, not merely a little.
ACOLYTE_RATIOS = {"duty": 100, "city": 85, "inHand": 95}

PLAYERS = (
    {"id": "p1", "label": "Player 1", "colour": "#8fae6a"},
    {"id": "p2", "label": "Player 2", "colour": "#7fa7c8"},
    {"id": "p3", "label": "Player 3", "colour": "#c88fb8"},
    {"id": "p4", "label": "Player 4", "colour": "#d6a45c"},
)

# ---- the crowded starting state -------------------------------------------------------------
START_OCCUPANCY = {"clerical": 4, "allocation": 3, "build_roads": 2, "ordination": 1,
                   "give_alms": 4, "produce": 2, "taxation": 3, "construct": 1}
START_SEATS = {"clerical": ["p1", "p1", "p2", "p3"]}
START_CITY_COUNTS = {"p1": 7, "p2": 4, "p3": 2, "p4": 5}

# ---- the three states -----------------------------------------------------------------------
# READY is the turn before anything is picked up; SOW is placing them; ACTION is what the one you
# placed does. The wheel and the City are identical in all three -- that is the whole reason the
# three are comparable rather than merely similar.
VIEW_STATES = (
    ("ready",  "READY / CITY",      "Pick up Acolytes or Hire Buildings"),
    ("sow",    "SOWING",            "Choose the next Duty — {n} Acolytes remaining"),
    ("action", "ACTION SELECTION",  "Select a Duty Action or take Tithe"),
)

BACKGROUNDS = (("black", "Black", "#000000"),
               ("gamedark", "Game Dark", "#100e0b"))
ZOOM_STEPS = (50, 75, 100, 125, 150)


def _on_ellipse(deg: float, rx: float, ry: float) -> tuple[float, float]:
    """A point on the ring, measured clockwise from 12 o'clock."""
    t = math.radians(deg)
    return WHEEL_CX + rx * math.sin(t), WHEEL_CY - ry * math.cos(t)


def _norm(x: float, y: float) -> tuple[float, float]:
    """An absolute design point as a fraction of the wheel's box."""
    return (x - WHEEL_X) / WHEEL_W, (y - WHEEL_Y) / WHEEL_H


def _r4(v: float) -> float:
    return round(v, 4)


def card_slots() -> dict:
    """Where each duty's reference card opens: one row, in wheel order.

    Returned as a mapping so the arrangement is one fact the tests can read, and so that the
    ribbon's order is visibly the wheel's order rather than a coincidence of iteration.
    """
    return {slug: {"x": CARD_X0 + i * (CARD_W + CARD_GAP), "y": RIBBON["y"],
                   "width": CARD_W, "height": RIBBON["height"]}
            for i, (slug, _n, _d) in enumerate(DUTIES)}


def default_state() -> dict:
    """THE ONE PLACE THE STARTING LAYOUT IS DECIDED.

    The page's own reset, its first run, and the tests all read this. It is emitted into the page
    as JSON rather than rebuilt in JavaScript, which would be the same decision written twice.

    IMAGES ARE NOT IN HERE. An asset field carries a KEY and a filename; the bytes live in a pool
    beside the state, which is what lets the autosave stay small, the undo history stay cheap and
    a lost asset say which file to reload.
    """
    slots = card_slots()
    TEXT = duty_text()
    duties = {}
    for slug, name, deg in DUTIES:
        fx, fy = _on_ellipse(deg, FIG_RX, FIG_RY)
        fu, fv = _norm(fx, fy)
        d = {"name": name, "clock": deg}
        # DERIVED FROM THE TEXT FILE, not a second switch to keep in step. A duty either has
        # a second action or it does not, and duty_text.json is where that is said.
        d["actions"] = 1 if TEXT[slug][ACTIONS[1][0]] is None else 2
        for slot, _ in ACTIONS:
            # ASSETS ONLY -- no geometry. The two shared slots in `display` own the box.
            # `name` and `shortLabel` are two different things now and no longer shadow each
            # other: the name is the duty action's own (DEVOTION), the shortLabel is what it does
            # (GAIN PIETY). They were the same string in every duty until the wording moved into
            # duty_text.json, which is why one caption could stand in for both.
            # The second slot still EXISTS on a one-action duty: the schema is fixed, an
            # older session merges against it, and the export keeps one shape for all eight. It
            # simply carries nothing and is never drawn.
            said = TEXT[slug][slot] or {"name": None, "shortLabel": ""}
            d[slot] = {"name": said["name"], "shortLabel": said["shortLabel"],
                       "seal": None, "sealName": None,
                       "scenic": None, "scenicName": None}
        seats = START_SEATS.get(slug) or [PLAYERS[0]["id"]] * 4
        d["card"] = dict(slots[slug], visible=True, locked=False)
        d["figures"] = {"x": round(fx), "y": round(fy),
                        "u": _r4(fu), "v": _r4(fv),
                        "count": START_OCCUPANCY.get(slug, 0),
                        "spacing": 74, "arrangement": "row",
                        "seats": list(seats)[:4], "attached": True}
        duties[slug] = d

    return {
        "version": STATE_VERSION,
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "background": BACKGROUNDS[0][0],
        "attachToWheel": True,
        "view": VIEW_STATES[0][0],
        "selectedDuty": "clerical",       # the duty the sow reached, for ACTION SELECTION
        "previewDuty": None,              # the card being previewed, in READY and SOW
        "showGhosts": False,
        "status": dict(STATUS, size=STATUS_SIZE, align="center", opacity=1.0,
                       byView={k: {"main": m} for k, _l, m in VIEW_STATES},
                       locked=False, visible=True),
        # THE ASSET'S RATIO, NOT THE BOX'S. WHEEL_H is that ratio rounded to a whole pixel, so
        # storing height/width instead would bake the rounding error in and let it compound
        # every time the wheel is rescaled.
        "wheel": {"x": WHEEL_X, "y": WHEEL_Y, "width": WHEEL_W, "height": WHEEL_H,
                  "naturalRatio": WHEEL_RATIO,
                  "ratioSource": "builtin",
                  # WHAT A LOADED FILE'S OWN SHAPE IS, recorded so it can be reported. It is
                  # information about the asset and never an input to the layout -- see the
                  # wheel file input in the template.
                  "assetRatio": None, "assetRatioSource": None,
                  # The built-in drawing's own ground rectangle. Off, because it describes the
                  # board's colour inside the wheel's bounding box and nowhere else, which is
                  # not a shape the real board has. The stage background is the honest control.
                  "ground": False,
                  "opacity": 1.0, "locked": False, "image": None, "imageName": None},
        "duties": duties,
        "display": {
            # ONE SWITCH FOR BOTH BOXES, and it sits on `display` rather than beside the
            # sizes, because it is not the same kind of decision. How big a caption is belongs
            # to the box it is in; whether the effect line shouts is a convention for the whole
            # composition, and having it twice would only raise the question of what a board
            # with one box shouting and one not is supposed to mean.
            #
            # TRUE is the default because that is how the card has always drawn. Turning it off
            # shows what duty_text.json actually stores -- "Gain X piety" rather than
            # "GAIN X PIETY" -- which is the form the wording is written and reused in.
            "effectUpper": True,
            # TWO SIZES PER BOX. `labelSize` is the effect line at the foot and keeps its
            # name, so an older session opens at the size it was saved with; `nameSize` is the
            # action name at the head and is new. They start equal and are set separately,
            # because the two lines are different lengths -- seven of the fourteen effect lines
            # wrap to two at 17px while every name fits one.
            "artLeft": dict(ART_LEFT, slot="actionA", fit="cover", opacity=1.0,
                            locked=False, visible=True, labelVisible=True,
                            labelSize=17, nameSize=17),
            "artRight": dict(ART_RIGHT, slot="actionB", fit="cover", opacity=1.0,
                             locked=False, visible=True, labelVisible=True,
                             labelSize=17, nameSize=17),
            # A lightweight overlay at the reached duty's own anchor. Never a change to the
            # imported wheel asset: the SVG may not expose its segments, and recolouring
            # somebody's artwork from a layout tool is not this page's business.
            "highlight": {"width": 300, "height": 120, "dy": 12, "style": "glow",
                          # A WARM GLOW, because the wheel is dark again. This travelled: pale
                          # gold reads well on slate, went to 1.06 against the drawing's cream
                          # parchment, became deep oxblood for it, and came back when the lab's
                          # palette turned the faces slate. The number to watch is the contrast
                          # against WHEEL_PALETTE's face colour, and the acceptance run measures
                          # it rather than taking the colour on trust.
                          "visible": True, "opacity": 0.5, "colour": "#e8c877"},
        },
        "tithe": dict(TITHE, label="TAKE TITHE", visible=True, locked=False,
                      image=None, imageName=None,
                      tokenSize=TOKEN_SIZE_DEFAULT, tokenSpread=TOKEN_SPREAD_DEFAULT,
                      resources=[{"key": k, "name": n, "icon": None, "iconName": None}
                                 for k, n in TITHE_RESOURCES]),
        "acolytes": {
            "height": ACOLYTE_DEFAULT,
            "style": "colored",
            "ratios": dict(ACOLYTE_RATIOS),
            "painted": {p["id"]: None for p in PLAYERS},
            "paintedNames": {p["id"]: None for p in PLAYERS},
            "colored": {p["id"]: None for p in PLAYERS},
            "coloredNames": {p["id"]: None for p in PLAYERS},
        },
        "players": [dict(p) for p in PLAYERS],
        "city": dict(CITY, locked=False, visible=True,
                     label="THE CITY",
                     counts=dict(START_CITY_COUNTS),
                     shown={p["id"]: True for p in PLAYERS}),
        # NOT A BOX ANY MORE. The acolytes in hand are drawn in the City's region while sowing,
        # so the only thing left to remember is how many there are and whose they are.
        "inHand": {"count": 4, "seat": "p1", "label": "ACOLYTES IN HAND"},
        "guides": {"bounds": True, "centreH": True, "centreV": True,
                   "grid": False, "safe": True, "wheelCentre": True, "warnings": True},
        "zoom": "fit",
        "mode": "edit",
    }


# SUBSTITUTED IN THIS ORDER, and __WHEEL_SVG__ is deliberately last: it is 60KB of path data,
# and putting it in first would mean every remaining replace scanning it.
_TOKENS = ("__BUILD_VERSION__", "__DEFAULT_STATE__", "__CANVAS_W__", "__CANVAS_H__",
           "__DUTY_ORDER__", "__DUTY_ACTIONS__", "__FULL_BOARDS__", "__SAFE_MARGIN__",
           "__WHEEL_RATIO__", "__WHEEL_VIEWBOX__", "__ELEVATION__", "__HELPER_RANGES__",
           "__STATE_VERSION__", "__ACOLYTE_RANGE__", "__ACOLYTE_ASPECT__",
           "__BACKGROUNDS__", "__ZOOM_STEPS__", "__PLAYER_IDS__", "__VIEW_STATES__",
           "__SEAL_SIZE__", "__WHEEL_SVG__")


def build() -> str:
    tmpl = TEMPLATE.read_text(encoding="utf-8")
    values = {
        "__DEFAULT_STATE__": json.dumps(default_state(), indent=1),
        "__CANVAS_W__": json.dumps(CANVAS_W),
        "__CANVAS_H__": json.dumps(CANVAS_H),
        "__DUTY_ORDER__": json.dumps([d[0] for d in DUTIES]),
        "__DUTY_ACTIONS__": json.dumps([{"key": k, "label": v} for k, v in ACTIONS]),
        "__FULL_BOARDS__": json.dumps(list(FULL_BOARD_CANVASES)),
        "__SAFE_MARGIN__": json.dumps(SAFE_MARGIN),
        "__WHEEL_RATIO__": json.dumps(WHEEL_RATIO),
        "__WHEEL_VIEWBOX__": json.dumps("%g x %g" % (WHEEL_VIEW_W, WHEEL_VIEW_H)),
        "__ELEVATION__": json.dumps(WHEEL_ELEVATION_DEG),
        "__HELPER_RANGES__": json.dumps(HELPER_RANGES),
        # THE ASSET GOES IN LAST AND RAW. It is 60KB of path data with no tokens in it, so
        # substituting it before the others would mean scanning it for every remaining token --
        # and, worse, a coordinate that happened to spell one would be replaced.
        # JSON-ENCODED, not pasted between quotes: the markup contains both newlines and
        # double quotes, and a JavaScript string literal tolerates neither.
        "__WHEEL_SVG__": json.dumps(wheel_svg()),
        "__STATE_VERSION__": json.dumps(STATE_VERSION),
        "__BUILD_VERSION__": json.dumps(BUILD_VERSION),
        "__ACOLYTE_RANGE__": json.dumps([ACOLYTE_MIN, ACOLYTE_MAX]),
        "__ACOLYTE_ASPECT__": json.dumps(ACOLYTE_ASPECT),
        "__BACKGROUNDS__": json.dumps([{"key": k, "label": lbl, "css": c}
                                       for k, lbl, c in BACKGROUNDS]),
        "__ZOOM_STEPS__": json.dumps(list(ZOOM_STEPS)),
        "__PLAYER_IDS__": json.dumps([p["id"] for p in PLAYERS]),
        "__VIEW_STATES__": json.dumps([{"key": k, "label": lbl}
                                       for k, lbl, _m in VIEW_STATES]),
        "__SEAL_SIZE__": json.dumps(SEAL_SIZE),
    }
    assert set(values) == set(_TOKENS), "the token list and the values have drifted apart"
    for token in _TOKENS:
        if token not in tmpl:
            raise SystemExit("the template no longer has %s in it -- generator and template "
                             "have drifted apart" % token)
        tmpl = tmpl.replace(token, values[token])
    left = [t for t in _TOKENS if t in tmpl]
    assert not left, "placeholders left unsubstituted: %s" % left
    return tmpl


def main(argv=None, opener=webbrowser.open) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", type=pathlib.Path, default=OUT,
                    help="where to write the page (default: %s)" % OUT)
    ap.add_argument("--open", action="store_true",
                    help="open the page in the default browser once it is written")
    args = ap.parse_args(argv)
    html = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (args.out, len(html) / 1024))

    if not args.open:
        print("  open it by double-clicking, or pass --open; it needs no server and no network")
        return 0

    # AS A file:// URI, not a bare path. as_uri() resolves and percent-encodes, so a checkout
    # under a directory with a space in it still opens.
    url = args.out.resolve().as_uri()
    # webbrowser.open returns False when it cannot find a browser, and on a headless box it can
    # return True having done nothing -- so the URL is printed either way.
    ok = opener(url)
    print("  %s %s" % ("opened" if ok else "could not open a browser for", url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
