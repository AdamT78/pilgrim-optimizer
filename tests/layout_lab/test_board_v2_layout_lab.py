"""Guards for the Duty Wheel layout lab.

The lab is a tool rather than a renderer, so what is worth holding here is not how it looks but
the handful of facts it would be quietly wrong about: which duties exist, that the City is not
one of them, that the wheel's proportions are the asset's and not the layout's, and that a
layout file it refuses to read is refused for a reason it can state.

WHY THE JAVASCRIPT IS TESTED IN NODE. The page's validation and merge rules decide whether a
saved layout loads or is thrown away, and they are written once, in the template. Reimplementing
them in Python to assert against would be a second copy that agrees on the day it is written --
which is the failure this file exists to prevent, not to commit.
"""

import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

# tests/layout_lab/ -> tests/ -> the repo root. This file sits beside the browser suites
# it shares a subject with, which is also what keeps every layout lab path inside one
# design-only directory for CI to route on.
ROOT = pathlib.Path(__file__).resolve().parents[2]
LAB = ROOT / "ui" / "board_v2" / "layout_lab"
GEN = LAB / "generate_layout_lab.py"
TMPL = LAB / "duty_wheel_layout_lab.html.tmpl"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def lab():
    spec = importlib.util.spec_from_file_location("generate_layout_lab", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def page(lab):
    return lab.build()


@pytest.fixture(scope="module")
def duties_model():
    """pilgrim/model/duties.py, which is where the engine says what a duty is."""
    spec = importlib.util.spec_from_file_location("pilgrim_duties",
                                                  ROOT / "pilgrim" / "model" / "duties.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pilgrim_duties"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- the model


def test_the_lab_knows_the_eight_duties_the_engine_knows(lab, duties_model):
    """The one fact this whole module is built on, checked against the engine rather than a list.

    The first board drew nine duties because its 3x3 grid made the City the middle cell. The
    engine never agreed: merchant.py sets CITY_POSITION = 0 and says the valid range is 1..8.
    So a layout exported here has to name duties the way the game does, or the coordinates it
    produces land on keys the game cannot look up.

    Asked of the engine's own enum, so renaming a duty there fails here rather than silently
    leaving the lab exporting a name nothing reads.
    """
    slugs = {d[0] for d in lab.DUTIES}
    assert len(slugs) == 8, "the lab does not have eight duties: %s" % sorted(slugs)
    assert "city" not in slugs, (
        "the City is in the duty list. It has no duty action, no tithe and no merchant, and the "
        "engine puts it at position 0 outside the 1..8 range -- it is a reserve, not a duty")

    # THE SAME EIGHT, not merely eight of the engine's names. DUTY_CATEGORIES is the engine's
    # own list and it is exactly eight long, so equality is the honest assertion -- a lab that
    # renamed one, dropped one or invented one would export coordinates keyed on something the
    # game cannot look up.
    assert slugs == set(duties_model.DUTY_CATEGORIES), (
        "the lab and the engine do not name the same eight duties.\n  lab:    %s\n  engine: %s"
        % (sorted(slugs), sorted(duties_model.DUTY_CATEGORIES)))

    # And the engine's ring has eight positions with no city among them, which is the structural
    # half of the same claim.
    assert len(duties_model.DUTY_POSITIONS) == 8
    assert "city" not in duties_model.DUTY_POSITIONS


def test_the_wheels_shape_is_the_assets_and_not_this_files_opinion(lab):
    """Where the wheel's proportions come from, which is the thing that must not drift.

    The drawing is the v2 duty wheel built at an aspect of **1.887**: 1000 x 529.9 in its own
    viewBox. The ratio is READ from that, and the elevation it implies is reported rather than
    used as an input. Deriving the shape from a number chosen here would be this module having an
    opinion about a drawing it did not make.

    1.887 happens to work out at 32.0 degrees, which is the elevation the old placeholder was
    drawn at -- so the numbers agree, and that agreement is a coincidence worth stating rather
    than relying on. The assertion below is about the DIRECTION of the derivation: ratio first,
    elevation after. A check that the two match would pass just as well with the arrow reversed.

    Falsified by setting the ratio from an elevation, or by hard-coding it.
    """
    import math
    text = lab.WHEEL_ASSET.read_text(encoding="utf-8")
    vw, vh = lab.viewbox_of(text)
    assert (vw, vh) == (lab.WHEEL_VIEW_W, lab.WHEEL_VIEW_H)
    assert (vw, vh) == (1000.0, 529.9), (
        "the built-in wheel is not the 1.887 build: %s x %s" % (vw, vh))
    assert abs(lab.WHEEL_RATIO - vh / vw) < 1e-12, "the ratio is not the asset's own"
    assert abs(lab.WHEEL_ASPECT - 1.887) < 0.001, (
        "the built-in wheel's aspect is %.4f, not the 1.887 it is built at" % lab.WHEEL_ASPECT)

    # RATIO FIRST, ELEVATION AFTER. Asserted at the source, because the two agreeing numerically
    # says nothing about which one was computed from which.
    source = GEN.read_text(encoding="utf-8")
    assert "WHEEL_RATIO = WHEEL_VIEW_H / WHEEL_VIEW_W" in source
    assert "math.asin(WHEEL_RATIO)" in source, (
        "the elevation is not derived from the ratio")
    assert "math.sin(math.radians(" not in source, (
        "an elevation is being turned back into a ratio somewhere, which is the arrow pointing "
        "the wrong way")
    assert abs(math.sin(math.radians(lab.WHEEL_ELEVATION_DEG)) - lab.WHEEL_RATIO) < 0.002

    d = lab.default_state()
    w = d["wheel"]
    # THE STORED RATIO IS THE ASSET'S, not the rounded box's -- otherwise the rounding error is
    # baked in and compounds every time the wheel is rescaled.
    assert w["naturalRatio"] == lab.WHEEL_RATIO, (
        "the default state stores %r rather than the asset's %r"
        % (w["naturalRatio"], lab.WHEEL_RATIO))
    assert w["ratioSource"] == "builtin", w["ratioSource"]
    assert abs(w["height"] / w["width"] - lab.WHEEL_RATIO) < 0.001, (
        "the opening box is %dx%d, a ratio of %.4f against the asset's %.4f"
        % (w["width"], w["height"], w["height"] / w["width"], lab.WHEEL_RATIO))


def test_the_drawing_is_recoloured_into_the_labs_slate(lab):
    """The wheel is built in parchment and the lab wears slate, so something has to convert.

    The builder draws for the first board design: cream faces on dark board. This lab composes
    against pure black with scenic art that fades into it, and the stand-in this drawing replaced
    was slate -- so keeping those greys keeps every judgement made against the placeholder still
    worth something.

    THE CONVERSION HAPPENS AT BUILD TIME AND THE CHECKED-IN FILE IS LEFT ALONE. Hand-editing a
    generated file is how a file stops being regenerable, which is the one rule the builder's own
    header insists on.

    AND EVERY ENTRY MUST MATCH. A palette that silently stopped applying would leave a cream wheel
    on a black field with no error anywhere, so a missing colour is fatal rather than skipped.

    Falsified by a palette that no longer describes the drawing, or by one that fails quietly.
    """
    raw = lab.WHEEL_ASSET.read_text(encoding="utf-8")
    out = lab.wheel_svg()

    for cream in lab.WHEEL_PALETTE:
        assert cream.lower() in raw.lower(), (
            "the checked-in drawing has no %s, so the palette does not describe it" % cream)
        assert cream.lower() not in out.lower(), (
            "%s survived the recolour" % cream)
    for slate in lab.WHEEL_PALETTE.values():
        assert slate.lower() in out.lower(), "%s never reached the page" % slate

    # The three greys are the placeholder's own: face, hub, base.
    assert lab.WHEEL_PALETTE["#efe3c8"] == "#3a3d45", "the faces are not the placeholder's slate"
    assert lab.WHEEL_PALETTE["#e8dcc0"] == "#23262b", "the hub is not the placeholder's darker one"
    assert lab.WHEEL_PALETTE["#17130d"] == "#2b2e34", "the ground is not the placeholder's base"

    # Eight faces plus a hub, all converted, none missed.
    assert out.lower().count("#3a3d45") == 8, (
        "%d faces came out slate rather than eight" % out.lower().count("#3a3d45"))
    assert out.lower().count("#23262b") == 1

    # A COLOUR THAT IS NOT THERE IS FATAL, not ignored.
    with pytest.raises(SystemExit):
        lab.recolour("<svg/>", {"#123456": "#654321"})
    # And the match is case-insensitive, because an SVG writer may emit either.
    assert lab.recolour('fill="#EFE3C8"', {"#efe3c8": "#3a3d45"}) == 'fill="#3a3d45"'
    assert lab.recolour('fill="#efe3c8"', {"#EFE3C8": "#3a3d45"}) == 'fill="#3a3d45"'



def test_the_build_label_moved_and_the_schema_did_not(lab):
    """V4.1 corrects four things and changes no shapes, so only one of the two numbers moves.

    Bumping STATE_VERSION would send every existing V4 session through the V3 -> V4 migration,
    which drops geometry on purpose -- so a correction that changes no shapes would throw away
    somebody's composition to fix a hover rule. The build label carries the change instead, and
    the wheel's ratio is normalised on import rather than migrated.

    Falsified by moving STATE_VERSION for a corrective release.
    """
    assert lab.STATE_VERSION == 4, lab.STATE_VERSION
    assert lab.BUILD_VERSION != "4.0", "the build label did not move with the corrections"
    assert lab.BUILD_VERSION.startswith("4."), lab.BUILD_VERSION
    d = lab.default_state()
    assert d["version"] == 4


def test_a_loaded_asset_is_art_in_the_box_and_never_the_layouts_shape(lab):
    """The instruction that made 32 degrees an invariant, held at the source.

    Loading a picture used to be a layout edit: the file's ratio became the wheel's, the height
    was recomputed, the lower edge could leave the module and every attached acolyte moved. The
    behaviour is now the other way round -- the box is the authority and the file is art placed
    into it -- and this asserts the absence of the old code path by name, because that is the
    kind that gets added back for one convenient case.

    Falsified by writing naturalRatio, height or the anchors from a loaded asset again.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    handler = tmpl[tmpl.index('if (fw) fw.onchange'):tmpl.index('// HOW CLOSE COUNTS AS MATCHING')]
    for banned in ("o.naturalRatio =", "o.ratioSource =", "o.height =", "syncAttached()"):
        assert banned not in handler, (
            "loading a wheel file still does %r, which makes loading a picture a layout edit"
            % banned)
    assert "o.assetRatio =" in handler, "the asset's own ratio is not recorded at all"
    assert "ratioMatches(" in handler, "nothing reports whether the asset matches"

    # THE NORMALISATION IS UNCONDITIONAL. A guarded version -- only when the stored ratio is
    # missing or absurd -- leaves an older V4 session at whatever projection it was saved with.
    apply = tmpl[tmpl.index("function applyState("):tmpl.index("function stripDataUrls(")]
    assert "S.wheel.naturalRatio = WHEEL_RATIO;" in apply
    assert "S.wheel.height = Math.round(S.wheel.width * WHEEL_RATIO);" in apply
    assert "if (!(S.wheel.naturalRatio > 0))" not in apply, (
        "the ratio is only normalised when it is missing, so a session saved at somebody else's "
        "projection keeps it")

    # A MISMATCHED PICTURE IS CONTAINED, NOT STRETCHED -- which is how a person sees it is wrong.
    css = tmpl[tmpl.index("<style>"):tmpl.index("</style>")]
    assert "#wheelObj img{" in css and "object-fit:contain" in css, (
        "a loaded asset is not contained inside the wheel box")
    assert "object-fit:fill" not in css

    # AND THE GENERATOR REFUSES a drawing that is not at the design elevation. Exercised rather
    # than looked for in the source: an invariant whose only expression is a line that happens to
    # be true today is being hoped for, not checked.
    assert lab.check_design_ratio(0.5299) == 0.5299
    assert lab.check_design_ratio(lab.WHEEL_RATIO) == lab.WHEEL_RATIO
    for wrong in (0.5624, 0.5, 0.75, 1.0):
        with pytest.raises(SystemExit):
            lab.check_design_ratio(wrong)
    assert lab.DESIGN_RATIO == 0.5299
    d = lab.default_state()
    assert d["wheel"]["assetRatio"] is None and d["wheel"]["assetRatioSource"] is None, (
        "the default state opens claiming an asset ratio it does not have")


def test_only_an_empty_stage_click_dismisses_a_preview(lab):
    """A preview is something you are reading, so touching it is not a request to put it away.

    The handler used to close on "anything that is not a card", which meant the preview artwork
    dismissed itself the moment you clicked it -- and so did the wheel, the City and the
    acolytes. Three outcomes now: a card toggles, empty stage closes, everything else is left
    alone.

    Falsified by widening the dismissal back out.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    clean = tmpl[tmpl.index('if (document.body.classList.contains("clean")){'):]
    clean = clean[:clean.index("if (!node){ select(null); return; }")]
    assert 'else if (!node){' in clean, (
        "the empty-stage branch is not a plain 'no object was clicked'")
    assert 'node.dataset.kind !== "card"' not in clean, (
        "the handler still dismisses on anything that is not a card")


def test_the_cards_only_advertise_a_click_where_one_does_something(lab):
    """A card that brightens under the cursor and then ignores the click is a false promise.

    Cards preview in READY and SOWING and are inert in ACTION SELECTION, so the affordance is
    conditional on the view and the class carrying it is set in the same render that decides the
    rest of the card's treatment -- which is what stops the two disagreeing.

    Falsified by styling .card:hover unconditionally, or by setting the class in every state.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    css = tmpl[tmpl.index("<style>"):tmpl.index("</style>")]
    hovers = [line for line in css.splitlines() if ".card" in line and ":hover" in line]
    assert hovers, "the cards have no hover treatment at all"
    for line in hovers:
        assert "previewable" in line, (
            "a card hover rule is not scoped to previewable cards: %s" % line.strip())

    render = tmpl[tmpl.index("---- 7. the duty reference cards"):tmpl.index("---- 8.")]
    assert 'if (S.view !== "action") cls += " previewable";' in render, (
        "the previewable class is not set from the view state")
    # And it is a separate thing from the reached treatment, which is about the game.
    assert 'cls += " reached"' in render



def test_the_layout_helpers_read_the_geometry_rather_than_remembering_it(lab):
    """The one rule that decides whether this panel is useful or a liar.

    A `groupHeight` or a `rowGap` kept in the state is a second opinion about geometry that is
    already there, and the moment somebody drags one card by hand it is wrong. So the panel asks
    the eight cards what height they are, and measures the three gaps between the four objects in
    the action row, every time it paints.

    That is also what lets it report MIXED honestly. A panel that showed 159 x 150 while three
    cards were 184 would be worse than no panel, because it would be believed.

    Falsified by storing either value in the state, or by reporting one card as if it spoke for
    eight.
    """
    d = lab.default_state()
    flat = json.dumps(d)
    for banned in ("groupHeight", "rowGap", "cardHeight", "linked", "helperState"):
        assert banned not in flat, (
            "the starting layout stores %r, which is a remembered copy of geometry that is "
            "already in the objects" % banned)

    tmpl = TMPL.read_text(encoding="utf-8")
    # The readings are functions of S, not fields on it.
    for fn in ("function cardGroup()", "function rowGaps()", "function rowGapCommon()",
               "function rowGapSuggested()", "function cardsToRowGap()"):
        assert fn in tmpl, "the derived reading %s is missing" % fn
    for banned in ("S.rowGap", "S.groupHeight", "S.helpers"):
        assert banned not in tmpl, "the panel keeps %r in the state" % banned

    # And the readout distinguishes uniform from mixed rather than always showing one number.
    paint = tmpl[tmpl.index("function paintMetrics()"):tmpl.index("function statusText()")]
    assert "mixed" in paint and "spreadText(" in paint, (
        "the readout has no mixed case, so eight different cards would be shown as one")
    assert "uniform" in tmpl[tmpl.index("function spread("):tmpl.index("function cardGroup()")]


def test_the_helper_ranges_are_studio_only_and_bounded_by_the_module(lab):
    """What the sliders may try, and the fact that none of it is the layout.

    These bound the controls, not the module: they say what is worth experimenting with while
    composing. They live in the generator so a test can read them and so the one place that knows
    the module's dimensions is the one place that bounds controls against it.

    Falsified by exporting a helper setting, or by a range that lets a slider leave the module.
    """
    r = lab.HELPER_RANGES
    assert set(r) == {"wheelW", "cardH", "artW", "artH", "gap", "rowRight",
                      "tokenSize", "tokenSpread"}, sorted(r)
    for key in ("wheelW", "cardH", "artW", "artH", "gap", "tokenSize", "tokenSpread"):
        lo, hi = r[key]
        assert lo < hi, "%s is not a range: %s" % (key, r[key])

    # TWO NUMBERS, AND THEY DO NOT INTERACT. The tokens stand on the vertices of an invisible
    # equilateral triangle: `tokenSpread` is its side, measured centre to centre, and `tokenSize`
    # is how big the three are. Neither is expressed in terms of the other, which is what the two
    # controls the triangle replaced could not manage -- a GAP is the space BETWEEN two boxes, so
    # it could not be set without also deciding what "bigger" would mean.
    assert "tokenGap" not in r, (
        "the gap between token boxes is the flex pyramid's measurement, not the triangle's")
    # NOR A PER-RESOURCE SCALE. Silver read about a ninth smaller than the other two because its
    # PNG carried more transparent margin; that was corrected by re-exporting the three masters
    # to the same disc fraction, not by a slider in the studio that production would then have
    # had to reproduce.
    assert "tokenScale" not in r, (
        "optical correction belongs in the artwork, not in a control")

    # THE TOP IS PAST WHAT THE CARD HOLDS, on purpose -- the Tithe box never follows the tokens,
    # so the slider has to be able to reach the crowding rather than stop short of it.
    assert r["tokenSize"][1] > 100, r["tokenSize"]
    assert r["tokenSize"][0] >= 20 and r["tokenSize"][1] <= 400, r["tokenSize"]
    # A SPREAD OF ZERO IS AN ARRANGEMENT, not an error: three tokens concentric on one point.
    assert r["tokenSpread"][0] == 0, (
        "a spread of zero has to be reachable: %s" % (r["tokenSpread"],))
    # And the top has to clear the widest token, or at the top of the size range the three could
    # never be pulled far enough apart to stop overlapping.
    assert r["tokenSpread"][1] >= r["tokenSize"][1], (
        "the tokens cannot be separated at their largest: %s vs %s"
        % (r["tokenSpread"], r["tokenSize"]))
    # The starting layout sits inside every token range, or the panel opens out of bounds.
    d0 = lab.default_state()["tithe"]
    assert r["tokenSize"][0] <= d0["tokenSize"] <= r["tokenSize"][1], d0["tokenSize"]
    assert r["tokenSpread"][0] <= d0["tokenSpread"] <= r["tokenSpread"][1], d0["tokenSpread"]
    assert not any("scale" in res for res in d0["resources"]), d0["resources"]

    # The wheel may fill the module but never exceed it, and at full width it still fits under
    # the action band -- otherwise the top of the range would produce a layout off the bottom.
    assert r["wheelW"][1] == lab.CANVAS_W, r["wheelW"]
    assert lab.WHEEL_Y + round(r["wheelW"][1] * lab.WHEEL_RATIO) <= lab.CANVAS_H, (
        "a full-width wheel would run off the bottom of the module")
    assert r["wheelW"][0] >= 200

    # FIT ACTION ROW leaves the band's own right margin, so a fitted row ends where the ribbon
    # above it does rather than at some number picked separately.
    assert r["rowRight"] == lab.CANVAS_W - (lab.BAND["x"] + lab.BAND["width"]), r["rowRight"]

    # The starting layout sits inside every range, or the panel would open out of bounds.
    d = lab.default_state()
    assert r["wheelW"][0] <= d["wheel"]["width"] <= r["wheelW"][1]
    for D in d["duties"].values():
        assert r["cardH"][0] <= D["card"]["height"] <= r["cardH"][1]
    for side in ("artLeft", "artRight"):
        e = d["display"][side]
        assert r["artW"][0] <= e["width"] <= r["artW"][1]
        assert r["artH"][0] <= e["height"] <= r["artH"][1]

    # NOT GAME STATE. The production export is built field by field, so the check is that these
    # names appear nowhere in it.
    tmpl = TMPL.read_text(encoding="utf-8")
    game = tmpl[tmpl.index("function gameLayout()"):tmpl.index("function validate(")]
    for banned in ("HELPERS", "rowGapSuggested", "cardGroup"):
        assert banned not in game, (
            "the game layout export reaches for the studio helper %r" % banned)


def test_no_helper_pushes_a_band_it_was_not_asked_about(lab):
    """The absence that makes the panel worth having, asserted at the source.

    Taller duty cards must not shove the action row down, and taller artwork must not move the
    wheel. The module is a fixed 1400 x 1200 and the point of the exercise is to watch these
    bands compete for it -- automatic reflow would hide the trade-off the designer is trying to
    judge. Only the explicit buttons move more than one thing.

    Falsified by any cascade, which is the tempting thing to add the first time two objects
    overlap.
    """
    tmpl = TMPL.read_text(encoding="utf-8")

    def body(name):
        """A function's LIVE lines, with its commentary stripped.

        The comments in these functions say exactly which objects they deliberately leave alone,
        so scanning the raw text finds the words it is looking for in the sentences explaining
        why they are absent.
        """
        start = tmpl.index("function %s(" % name)
        text = tmpl[start:tmpl.index("\nfunction ", start + 1)]
        return "\n".join(line for line in text.splitlines()
                          if not line.lstrip().startswith("//"))

    cards = body("setCardHeights")
    for banned in ("artLeft", "artRight", "artOf", "S.tithe", "S.city", "S.wheel"):
        assert banned not in cards, (
            "the card height control touches %s -- taller cards are meant to overlap the row "
            "visibly, not push it out of the way" % banned)

    art_h = body("setArtHeight")
    for banned in ("S.tithe", "S.city", "S.wheel", "card"):
        assert banned not in art_h, (
            "the linked artwork height touches %s; Tithe and the City keep their own" % banned)

    wheel = body("setWheelWidth")
    for banned in ("card", "S.tithe", "S.city", "artOf"):
        assert banned not in wheel, "the wheel control touches %s" % banned
    # It does move the acolytes, and it must: they are wheel-relative and would be left behind.
    assert "syncAttached()" in wheel

    # The row's left edge is the anchor and nothing rebuilds it.
    row = body("layoutActionRow")
    assert "L.x =" not in row, (
        "layoutActionRow writes the left anchor, so every gap change would walk the row sideways")
    assert "R.x =" in row and "T.x =" in row and "C.x =" in row

    # The centre button is the narrowest operation in the panel: it WRITES one field. It has to
    # read the width to know where the middle is, so the ban is on assignment rather than on the
    # word -- a check that forbade reading it would forbid the arithmetic.
    centre = body("centreWheelX")
    assert "S.wheel.x =" in centre, "centre wheel x does not set x"
    for banned in ("width =", "height =", ".y =", "clone("):
        assert banned not in centre, (
            "centre wheel x writes %s as well as x, so it is a reset rather than a repair"
            % banned)


# The nine operations the Layout Helpers panel offers, each with the set of objects it is about.
# "About" is not the same as "writes": ALIGN CARD TOPS never assigns Clerical's y, because
# Clerical's y is the value the other seven are levelled to -- and yet a locked Clerical must
# still refuse, because levelling seven cards to an eighth you were told not to touch is not an
# alignment. The same reasoning keeps the left artwork OUT of the row-gap set: the row is spaced
# from that anchor without writing it, so locking it does not stand in the way.
HELPER_OPERATIONS = {
    "setWheelWidth":   ("resize the wheel", "[WHEEL_O()]"),
    "centreWheelX":    ("centre the wheel", "[WHEEL_O()]"),
    "setCardHeights":  ("resize the duty cards", "ALL_CARDS()"),
    "alignCardTops":   ("align the duty cards", "ALL_CARDS()"),
    "setArtWidth":     ("resize the action artwork", "[ART_L(), ART_R(), TITHE_O(), CITY_O()]"),
    "setArtHeight":    ("resize the action artwork", "[ART_L(), ART_R()]"),
    "setRowGap":       ("re-space the action row", "[ART_R(), TITHE_O(), CITY_O()]"),
    "alignRowTop":     ("align the action row", "[ART_R(), TITHE_O(), CITY_O()]"),
    "fitActionRow":    ("fit the action row", "[ART_L(), ART_R(), TITHE_O(), CITY_O()]"),
}


def _helper_body(tmpl, name):
    """A helper function's live lines, with its commentary stripped."""
    start = tmpl.index("function %s(" % name)
    text = tmpl[start:tmpl.index("\nfunction ", start + 1)]
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("//"))


def test_every_helper_refuses_as_a_whole_or_not_at_all(lab):
    """A helper either does the whole operation or does none of it, and says which.

    The failure this forbids is the plausible one: check the locks as you go, move the six
    objects that are free, skip the two that are not. That leaves a layout nobody asked for and
    an undo entry recording it, and the designer's next act is to hunt for what moved.

    So the guard is one function, consulted once, before anything is written -- which is also
    what makes the refusal cheap to prove: no geometry changed and no history entry exists,
    because the operation never began.

    The message has to carry the VERB as well as the object. "Ordination's card is locked" does
    not say which of the two card helpers was pressed, and the build where the verb read off the
    wrong array said "cannot undefined" to every refusal while every browser test still passed,
    because they were all checking for the word "lock" and the object's name.

    Falsified by a per-object skip, by a refusal that still records, or by a message assembled
    from anything but the operation's own set.
    """
    tmpl = TMPL.read_text(encoding="utf-8")

    guard = _helper_body(tmpl, "requireUnlocked")
    # THE VERB COMES OFF THE SET THAT WAS PASSED IN. `stuck` is built inside the guard out of the
    # labels and carries no verb, so reading it there is the exact bug this line pins down.
    assert "needed.verb" in guard, "the refusal does not name the operation it refused"
    assert "stuck.verb" not in guard, (
        "the verb is read off the array the guard builds, which has none -- every refusal would "
        "read 'cannot undefined'")
    for banned in ("commit(", "record(", "recordSoon("):
        assert banned not in guard, (
            "a refusal calls %s, so being told no leaves an undo entry behind" % banned)

    for name, (verb, objects) in HELPER_OPERATIONS.items():
        text = _helper_body(tmpl, name)
        # THE WHOLE CALL, closing brackets included. Matching the set as a fragment lets
        # `ALL_CARDS().slice(1)` -- seven of the eight cards, which is the partial alignment this
        # test exists to forbid -- satisfy a check for `ALL_CARDS()`.
        call = 'requireUnlocked(needs("%s", %s))' % (verb, " ".join(objects.split()))
        assert call in " ".join(text.split()), (
            "%s does not open with the shared guard over exactly the set it is about; "
            "expected %s" % (name, call))
        # The guard is the FIRST thing, so nothing is half-done when it refuses.
        first = [ln for ln in text.splitlines()[1:] if ln.strip()][0]
        assert "requireUnlocked" in first, (
            "%s does work before checking the locks: %r" % (name, first.strip()))
        # And no helper consults a lock on its own; that is what makes the behaviour uniform.
        assert "lockedOf(" not in text, (
            "%s checks a lock itself rather than through the guard, so its refusal can drift "
            "out of step with the other eight" % name)

    # Direct manipulation is deliberately NOT routed through this: dragging a locked object and
    # arrow-keying one simply do nothing, because a mouse that announces a refusal on every
    # movement is noise rather than information.
    for name in ("onDown", "onKey"):
        if "function %s(" % name in tmpl:
            assert "lockedOf(" in _helper_body(tmpl, name), (
                "%s no longer checks locks at all" % name)


def test_the_helper_controls_are_refreshed_from_render_and_never_rebuilt(lab):
    """Why the controls cannot go stale, and why refreshing them does not fight the typist.

    Every path that changes geometry ends in a render -- drag, resize, inspector, arrow key,
    helper, undo, redo, reset, import -- so hanging the refresh off that one place makes "the
    controls always show the truth" true by construction instead of by remembering to call it
    from nine buttons.

    Two things it must not do. It must not REBUILD the panel: replacing the markup under a
    half-typed number throws the caret out and drops the field's focus, so the refresh has to
    write `.value` into the controls that are already there. And it must skip whichever control
    has the caret, or a typed "1500" never survives its own first digit.

    Falsified by a refresh that rebuilds, one that overwrites a focused field, or a control that
    echoes what was typed instead of reading back what the geometry actually became.
    """
    tmpl = TMPL.read_text(encoding="utf-8")

    render = tmpl[tmpl.index("function render()"):]
    render = render[:render.index("\nfunction ")]
    assert "syncHelperInputs()" in render, (
        "render does not refresh the helper controls, so an undo or a drag leaves them stale")
    assert render.index("paintMetrics()") < render.index("syncHelperInputs()"), (
        "the controls are synced before the metrics, so the two readings can disagree")

    sync = _helper_body(tmpl, "syncHelperInputs")
    assert "document.activeElement" in sync, (
        "the refresh writes over whichever box has the caret")
    for banned in ("innerHTML", "panels()", "createElement", "appendChild"):
        assert banned not in sync, (
            "the refresh reaches for %s -- it rebuilds the panel rather than updating the "
            "controls in place, which takes the caret with it" % banned)
    # It reads the geometry, not some remembered copy.
    for reading in ("S.wheel.width", "cardGroup()", "helperGap()"):
        assert reading in sync, "the refresh does not read %s from the objects" % reading
    # The GROUP value, not one end of a mixed range: the number shown is the one the control
    # would apply to all eight if it were touched.
    assert "cg.h.lo" in sync and "cg.h.hi" not in sync, (
        "the card control shows one end of a mixed range rather than the group value")
    # And the control is clamped into its own range, or the number box displays something the
    # slider beside it cannot reach. The METRICS are the place a negative gap is reported.
    helper_gap = _helper_body(tmpl, "helperGap")
    assert "clamp(" in helper_gap and "HELPERS.gap" in helper_gap, (
        "the gap control is not bounded by its own range")

    pair = tmpl[tmpl.index("function pair(numId"):]
    pair = pair[:pair.index("\n  pair(")]
    assert "var actual = read();" in pair, (
        "the control echoes the typed number instead of reading the geometry back, so a clamped "
        "or refused value leaves it armed to jump there on the next touch")
    assert "document.activeElement !== n" in pair, (
        "the number box is rewritten while it has the caret")


def test_only_the_repair_button_normalises_the_gap(lab):
    """The one place a gap may be changed behind the designer's back, and the one place it may not.

    FIT ACTION ROW is restorative. Hand-dragging can leave gaps of -20 / -10 / 12, whose median
    is negative, and rebuilding the row at that median would be a repair that carefully preserved
    the overlap it was pressed to remove. So the fit clamps into the control's range and says so.

    The ordinary linked resize must NOT do this. Someone mid-composition with a deliberate
    overlap types a new width and gets their overlap quietly corrected -- a slider that edits
    more than the thing it is labelled with.

    Falsified by an unclamped fit, or by the clamp spreading to the resize.
    """
    tmpl = TMPL.read_text(encoding="utf-8")

    fit = _helper_body(tmpl, "fitActionRow")
    assert "clamp(raw, HELPERS.gap[0], HELPERS.gap[1])" in fit, (
        "the fit rebuilds the row at whatever gap it measured, overlap included")
    assert "normalised from" in fit, (
        "the fit changes a number it was not asked to change without saying so")
    assert 'raw !== gap ? " · normalised from "' in fit, (
        "the fit claims to have normalised the gap even when it did not")

    resize = _helper_body(tmpl, "setArtWidth")
    assert "HELPERS.gap" not in resize, (
        "the ordinary resize clamps the gap, so it repairs a composition in progress")
    # AND IT MEASURES BEFORE IT MOVES. Reading the gap after the widths change measures the hole
    # the change just opened, which made shrinking scatter the row and widening pack it negative.
    assert resize.index("var gap = rowGapSuggested();") < resize.index('artOf("left").width ='), (
        "the gap is measured after the widths move, so it measures the change rather than the "
        "spacing the row had")


def test_the_vendored_drawing_matches_the_layout_it_was_built_from(lab):
    """A copy's whole failure mode is going quietly out of step with its source.

    There is no byte-for-byte original to diff against any more: the lab's wheel is a 1.887 build
    and `tools/ui_debug/prototypes/` holds the 1.778 baseline, which belongs to that tool and is
    deliberately untouched. What there IS is the layout the drawing was rendered from, which is
    plain JSON -- so the check reads it directly rather than importing anything, and asks the two
    things that would actually go out of step: the shape and the palette.

    When that file is not in the checkout the check stands down rather than failing for the wrong
    reason.

    A STALENESS GUARD HAS ALREADY EARNED ITS KEEP HERE. An earlier copy arrived 7,774 bytes larger
    than its source because a file-transfer path had injected a C2PA content-credentials manifest
    into it. Nothing failed: the page generated, the suite passed, and the only symptom was a page
    8KB bigger than the one that had been tested.

    Falsified by rebuilding the layout at a different aspect and not re-rendering the SVG.
    """
    layout = ROOT / "tools" / "ui_debug" / "duty_wheel_v2_1887_layout.json"
    if not layout.is_file():
        pytest.skip("tools/ui_debug/duty_wheel_v2_1887_layout.json is not in this checkout")
    d = json.loads(layout.read_text(encoding="utf-8"))

    assert abs(d["aspect"] - 1.887) < 1e-9, (
        "the layout was rebuilt at aspect %s; the lab's drawing is still 1.887" % d["aspect"])
    assert (d["box"], d["box_h"]) == (lab.WHEEL_VIEW_W, lab.WHEEL_VIEW_H), (
        "the layout is %s x %s and the vendored drawing is %s x %s -- one was regenerated without "
        "the other. Re-render it; the recipe is in the generator's header"
        % (d["box"], d["box_h"], lab.WHEEL_VIEW_W, lab.WHEEL_VIEW_H))

    # The checked-in copy is the builder's own colours; the lab converts at build time.
    raw = lab.WHEEL_ASSET.read_text(encoding="utf-8")
    for key in ("ground", "face", "centre"):
        assert d["palette"][key].lower() in raw.lower(), (
            "the layout's %s colour %s is not in the vendored drawing, so the copy was edited "
            "rather than re-rendered" % (key, d["palette"][key]))
        assert d["palette"][key].lower() in {k.lower() for k in lab.WHEEL_PALETTE}, (
            "the builder now uses %s for the %s and the lab's palette does not mention it"
            % (d["palette"][key], key))



def test_the_built_in_wheel_is_vendored_rather_than_imported(lab):
    """The instruction was to use that wheel and to depend on nothing that makes it.

    `tools/ui_debug/build_duty_wheel_v2.py` parses argv at import time, needs numpy, and says in
    its own header that the aspect is not settled. None of that should have to be true for this
    page to generate, and a test suite that imports this module should not be importing that one.

    So the drawing is a checked-in copy read as bytes. This asserts the absence of the coupling
    by name, because the coupling is the kind that gets added back for one convenient constant.

    Falsified by importing anything from tools/, or by reading the SVG from its original path.
    """
    source = GEN.read_text(encoding="utf-8")
    for banned in ("tools.ui_debug", "tools/ui_debug/generated", "build_duty_wheel_v2",
                   "render_duty_wheel_v2", "generate_duty_wheel_v2", "sys.path.insert",
                   "parents[2]", "importlib"):
        # The refresh recipe in the header names the scripts on purpose, so only live code counts.
        live = "\n".join(line for line in source.splitlines()
                          if not line.lstrip().startswith("#") and '"""' not in line)
        assert banned not in live, (
            "the generator reaches for %r. The wheel is vendored precisely so it does not" % banned)

    assert lab.WHEEL_ASSET.is_file(), "the vendored wheel is missing"
    assert lab.WHEEL_ASSET.parent.name == "assets"
    assert lab.WHEEL_ASSET.parent.parent == LAB, (
        "the asset lives outside the lab's own folder: %s" % lab.WHEEL_ASSET)


def test_the_built_in_wheel_names_no_duty_and_carries_nothing_live(lab):
    """What is inside the drawing, checked rather than trusted.

    Two separate claims. The first is V4's: nothing on the wheel says which duty a space is, and
    that has to hold for the asset as much as for anything the page draws over it -- the wheel's
    own faces are named by POSITION (north_west, north, centre), which is the same reason the
    builder gives, since duty tiles are shuffled at setup.

    The second is that inlining 60KB of somebody else's markup into a page does not bring
    anything with it. No script, no external reference, no remote font: the page's promise is
    that it needs no network, and an asset with an href in it would quietly break that.

    Falsified by an asset that labels its faces, or that pulls anything in.
    """
    text = lab.WHEEL_ASSET.read_text(encoding="utf-8")
    assert "<text" not in text and "<tspan" not in text, (
        "the built-in wheel carries text. Whatever it says, a duty name on the wheel is the one "
        "thing V4 keeps out of this tool")
    for slug, name, *_ in lab.DUTIES:
        assert name.lower() not in text.lower(), "the asset mentions %r" % name
        assert slug not in text, "the asset mentions %r" % slug

    for banned in ("<script", "<image", "href", "@import", "url(", "<foreignObject", "<use"):
        assert banned not in text, (
            "the built-in wheel contains %r, which either runs or fetches something" % banned)

    # Named by where they are, which is what makes the drawing reusable whatever is shuffled.
    for position in ("north_west", "north", "west", "centre"):
        assert 'id="%s"' % position in text, "the asset has no %r face" % position



def test_the_vendored_wheel_carries_no_metadata_of_its_own(lab):
    """What a file picks up on its way somewhere, which is not always nothing.

    The drawing is vector geometry this repo builds, so a content-credentials manifest, an XMP
    packet or an editor's leftovers are all claims about it that are either untrue or noise --
    and every byte of them is inlined into the generated page, where the sensible expectation is
    that 60KB of asset is 60KB of path data.

    Separate from the byte-identity check above on purpose: this one still holds in a checkout
    that has no `tools/` to compare against.

    Falsified by an asset that arrives stamped.
    """
    text = lab.WHEEL_ASSET.read_text(encoding="utf-8")
    for junk in ("c2pa", "<metadata", "xmpmeta", "rdf:RDF", "sodipodi", "inkscape",
                 "Adobe", "<!-- Generator"):
        assert junk.lower() not in text.lower(), (
            "the vendored wheel carries %r. It is geometry this repo generates; anything else in "
            "it is inlined into every page for no reason" % junk)
    # And the page is the size the geometry accounts for, give or take.
    assert 50_000 < len(text) < 70_000, (
        "the vendored wheel is %d bytes, which is not the size the nine faces come to" % len(text))


def test_the_viewbox_is_the_authority_on_the_assets_shape(lab):
    """The parsing, exercised on the shapes that make it wrong rather than on the real file.

    A drawing exported for a board is typically `width="100%%" height="100%%"`, and a browser
    asked for the natural size of one of those answers 300 x 150 -- a ratio of 0.5, close enough
    to a real foreshortening to look plausible while being wrong. The page already applies this
    rule to an SVG somebody loads; the built-in one gets the same treatment.

    Falsified by reading width/height instead, or by accepting a file with no viewBox.
    """
    responsive = '<svg width="100%" height="100%" viewBox="0 0 1000 529.9"><g/></svg>'
    assert lab.viewbox_of(responsive) == (1000.0, 529.9), (
        "the width/height attributes won over the viewBox, which is the exact trap")
    assert lab.viewbox_of('<svg viewBox = " 0 0 800 450 " >') == (800.0, 450.0), (
        "a viewBox with the whitespace an exporter leaves in was not read")

    for bad in ('<svg width="1000" height="530">', '<svg viewBox="0 0 0 529.9">',
                '<svg viewBox="0 0 1000">'):
        with pytest.raises(SystemExit):
            lab.viewbox_of(bad)

    # And the XML declaration is stripped, because an <?xml ?> inside an HTML document is not an
    # error -- it is a processing instruction the browser ignores, so the wheel would still draw
    # and nothing would say the page was malformed. Fed through the palette's colours, since
    # wheel_svg() recolours on the way out and refuses a drawing it cannot colour.
    swatch = " ".join(lab.WHEEL_PALETTE)
    assert lab.wheel_svg('<?xml version="1.0" encoding="UTF-8"?>\n<svg>%s</svg>' % swatch) \
        .startswith("<svg>")
    assert lab.wheel_svg("<svg>%s</svg>\n" % swatch).endswith("</svg>")
    assert not lab.wheel_svg().startswith("<?xml"), "the real asset kept its XML declaration"
    assert lab.wheel_svg().startswith("<svg")



def test_the_module_is_1400_by_1200_and_the_wheel_takes_whatever_fits(lab):
    """The canvas is unchanged; how big the wheel gets is derived, not written down.

    V3 spent the two hundred pixels over 1200 on margins, because four compact duty summaries
    stood in each one. V4 has no side columns, so the space went to the wheel -- and the wheel has
    two ceilings: the module's width less a margin each side, and the height left under the action
    band. WHICH ONE BITES DEPENDS ENTIRELY ON THE DRAWING, so both are computed and the smaller
    wins.

    At 1.887 the width runs out first: 1372 wide is 727 high, finishing at 1165. At 1.778 it was
    the other way round -- a full-width wheel would have hung 10px off the bottom -- and the wheel
    came out 1354 x 761 with wider margins. Both are right for their drawing, which is the point
    of deriving it.

    Falsified by fixing either dimension, or by only ever checking one of the two ceilings.
    """
    d = lab.default_state()
    assert d["canvas"] == {"width": 1400, "height": 1200}
    assert (lab.CANVAS_W, lab.CANVAS_H) == (1400, 1200)

    w = d["wheel"]
    left_margin = w["x"]
    right_margin = lab.CANVAS_W - (w["x"] + w["width"])
    assert left_margin == right_margin, (
        "the wheel is not centred: %d px of margin on the left, %d on the right"
        % (left_margin, right_margin))
    assert left_margin >= lab.WHEEL_MARGIN_MIN - 1, (
        "the wheel is %d px from the module's edge" % left_margin)

    # BOTH CEILINGS HOLD.
    assert w["y"] + w["height"] <= lab.CANVAS_H, (
        "the wheel runs %d px off the bottom of the module"
        % (w["y"] + w["height"] - lab.CANVAS_H))

    # AND ONE OF THEM IS TIGHT: two more pixels of width must break the floor or the margin.
    wider = w["width"] + 2
    breaks_floor = w["y"] + round(wider * lab.WHEEL_RATIO) > lab.CANVAS_H
    breaks_margin = (lab.CANVAS_W - wider) / 2 < lab.WHEEL_MARGIN_MIN
    assert breaks_floor or breaks_margin, (
        "the wheel is %d wide and %d would still fit inside both ceilings, so it is not as large "
        "as the module allows" % (w["width"], wider))
    assert lab.WHEEL_BOUND == ("width" if breaks_margin else "height"), (
        "the module reports it is %s-bound and the arithmetic says otherwise" % lab.WHEEL_BOUND)

    assert w["width"] >= lab.CANVAS_W * 0.95, (
        "the wheel opens %d px wide in a %d px module, which is a V3 wheel in a V4 layout"
        % (w["width"], lab.CANVAS_W))
    assert (w["width"] * w["height"]) / (lab.CANVAS_W * lab.CANVAS_H) > 0.55, (
        "the wheel covers only %.0f%% of the module; V4 is a wheel-dominant layout"
        % ((w["width"] * w["height"]) / (lab.CANVAS_W * lab.CANVAS_H) * 100))

    for board in lab.FULL_BOARD_CANVASES:
        assert board > lab.CANVAS_W, "%d is not wider than the module" % board
    assert 1600 not in lab.FULL_BOARD_CANVASES, (
        "1600 is back on the list. A 1400 module leaves it 200px for everything else")
    assert [b - lab.CANVAS_W for b in lab.FULL_BOARD_CANVASES] == [639, 883]



def test_nothing_on_the_wheel_identifies_which_duty_a_space_is(lab):
    """V4's deliberate absence, which is easier to reintroduce than to notice.

    How the eight physical spaces get identified -- engraved names, landmarks, emblems, plaques --
    is a question the brief explicitly removes from this tool's scope and keeps for later. So the
    wheel carries the acolytes standing on it and nothing else, and the duty's name lives in the
    ribbon card instead.

    V3 had a hideable parchment label object per duty for exactly this job. It is gone rather
    than hidden: a hidden object is one checkbox away from being back, and a default that could
    be flipped is not an absence.

    Falsified by putting a label object back on a duty, or by drawing any duty's name inside the
    wheel element.
    """
    d = lab.default_state()
    for slug, D in d["duties"].items():
        # `actions` is 1 or 2 -- Taxation and Allocation have one. Derived from
        # duty_text.json at build time rather than being a second switch to keep in step, and it
        # says nothing about WHERE a duty is, which is all this guard is about.
        assert set(D) == {"name", "clock", "actionA", "actionB", "actions", "card",
                          "figures"}, (
            "%s carries %s -- V4 duties hold wording, how many actions the duty has, a ribbon "
            "card and an acolyte anchor, and nothing that would mark out a space on the wheel"
            % (slug, sorted(D)))
        assert "label" not in D and "summary" not in D and "titheLabel" not in D

    # The template must not draw one either. A blocklist of names to look for is the weak way to
    # ask this -- it catches the spellings somebody thought of -- so the assertion is the exact
    # contents instead: the wheel element gets an editing name tag and the wheel art, full stop.
    tmpl = TMPL.read_text(encoding="utf-8")
    wheel_block = tmpl[tmpl.index("---- 1. the wheel"):tmpl.index("---- 2.")]
    assert "'<span class=nm>wheel</span>' + wheelInner, WHEEL_Z);" in wheel_block, (
        "the wheel element is drawn with something other than its name tag and its art. Anything "
        "else inside it identifies a duty space, which V4 keeps for a later decision:\n%s"
        % wheel_block)
    assert wheel_block.count("make(") == 1, "the wheel block draws a second object"
    assert "wheelInner = haveImage(w.image)" in wheel_block

    # And the acolyte anchors, which DO ride the wheel, are anchors and not labels.
    for slug, D in d["duties"].items():
        f = D["figures"]
        assert {"x", "y", "u", "v", "count", "seats"} <= set(f), sorted(f)
        assert "text" not in f and "label" not in f, (
            "%s's anchor grew a text field, which is a duty name on the wheel by another route"
            % slug)



def test_the_action_band_is_four_regions_that_do_not_touch(lab):
    """The one row where V4 puts everything that is not the wheel or the ribbon.

    Two artwork slots, Tithe and the City stand side by side in a single band between the ribbon
    and the wheel's top edge. They are the objects most likely to be resized while composing, so
    the thing worth pinning is that they open laid out rather than overlapping -- a default that
    starts with Tithe under an artwork teaches that the band is smaller than it is.

    The City is checked hardest because it is the one that has to hold four seats in a row and is
    the last thing before the module's right edge.

    Falsified by widening any of the four, or by moving Tithe back under the wheel.
    """
    d = lab.default_state()
    band = [("artLeft", d["display"]["artLeft"]), ("artRight", d["display"]["artRight"]),
            ("tithe", d["tithe"]), ("city", d["city"])]
    band.sort(key=lambda kv: kv[1]["x"])
    assert [k for k, _ in band] == ["artLeft", "artRight", "tithe", "city"], (
        "the band is not in the order the brief describes: %s" % [k for k, _ in band])

    # strict=False on purpose: pairing a list with its own tail is one shorter by design.
    for (an, a), (bn, b) in zip(band, band[1:], strict=False):
        assert a["x"] + a["width"] <= b["x"], (
            "%s ends at %d and %s starts at %d -- they overlap"
            % (an, a["x"] + a["width"], bn, b["x"]))
    for name, o in band:
        assert o["y"] == d["display"]["artLeft"]["y"], "%s is not on the band's row" % name
        assert o["height"] == d["display"]["artLeft"]["height"], (
            "%s is not the band's height" % name)
    assert band[0][1]["x"] >= 0
    assert band[-1][1]["x"] + band[-1][1]["width"] <= lab.CANVAS_W, (
        "the band runs off the right edge of the module")

    # Between the ribbon and the wheel, touching neither.
    ribbon_bottom = max(D["card"]["y"] + D["card"]["height"] for D in d["duties"].values())
    assert band[0][1]["y"] >= ribbon_bottom, "the band overlaps the ribbon"
    assert band[0][1]["y"] + band[0][1]["height"] <= d["wheel"]["y"], (
        "the band reaches into the wheel, which is the one thing it must leave alone")



def test_the_wheels_centre_is_left_empty(lab):
    """V3.1 put Tithe and the in-hand pool in the middle of the wheel. V4 empties it again.

    Both objects left for the action band, where they sit beside the artwork a player is choosing
    between -- which is where the decision is being made. What is gained is a quiet centre: the
    wheel now reads as a board rather than as a frame around a medallion, and a wheel asset with
    art of its own in the middle is no longer competing with the layout.

    So the assertion is an absence, expressed as distance: nothing the layout owns opens inside
    the wheel's middle third.

    Falsified by putting either medallion back in the centre.
    """
    d = lab.default_state()
    w = d["wheel"]
    cx, cy = w["x"] + w["width"] / 2, w["y"] + w["height"] / 2
    inner = {"x": cx - w["width"] / 6, "y": cy - w["height"] / 6,
             "width": w["width"] / 3, "height": w["height"] / 3}

    def overlaps(a, b):
        return (min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]) > 0
                and min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]) > 0)

    boxes = {"tithe": d["tithe"], "city": d["city"], "status": d["status"],
             "artLeft": d["display"]["artLeft"], "artRight": d["display"]["artRight"]}
    boxes.update({"%s card" % s: D["card"] for s, D in d["duties"].items()})
    for name, o in boxes.items():
        assert not overlaps(o, inner), "%s opens in the wheel's middle third" % name

    # The in-hand pool is no longer a box at all -- it borrows the City's region while sowing --
    # so it cannot be anywhere, which is a stronger statement than being elsewhere.
    assert set(d["inHand"]) == {"count", "seat", "label"}, (
        "the in-hand pool still carries geometry: %s. In V4 it is drawn inside the City's "
        "region, so a box of its own is a second opinion about where it is" % sorted(d["inHand"]))



def test_the_acolyte_anchors_are_the_only_wheel_relative_objects(lab):
    """What u/v is for once the medallions have left the wheel.

    An object is wheel-relative when its meaning is a place ON the wheel, and after V4 exactly
    one kind of object still means that: the eight acolyte anchors. Everything else -- the cards,
    the artwork, Tithe, the City, the instruction -- is placed against the module, so giving any
    of them u/v would tie it to a wheel it has no relationship with and move it every time the
    wheel is nudged.

    V3.1's uvAnchor field went with the medallions. It existed because "in the centre of the
    wheel" is a claim about the centre of the object too; nothing in V4 makes that claim, so a
    field that only the medallions used is a field with no users.

    Falsified by giving u/v to anything but an anchor, or by bringing uvAnchor back.
    """
    d = lab.default_state()
    w = d["wheel"]
    for slug, D in d["duties"].items():
        f = D["figures"]
        assert "u" in f and "v" in f, "%s's anchor is not wheel-relative" % slug
        assert f["attached"] is True
        # The stored pair really does resolve to the cached x/y against this wheel, so attaching
        # and detaching is a no-op rather than a small move.
        assert abs((w["x"] + f["u"] * w["width"]) - f["x"]) <= 1, (
            "%s's u does not resolve to its own x" % slug)
        assert abs((w["y"] + f["v"] * w["height"]) - f["y"]) <= 1, (
            "%s's v does not resolve to its own y" % slug)
        assert f.get("uvAnchor") is None, "uvAnchor came back on %s" % slug

    others = {"tithe": d["tithe"], "city": d["city"], "status": d["status"],
              "artLeft": d["display"]["artLeft"], "artRight": d["display"]["artRight"]}
    others.update({"%s card" % s: D["card"] for s, D in d["duties"].items()})
    for name, o in others.items():
        assert "u" not in o and "v" not in o, (
            "%s carries u/v. It is placed against the module, so tying it to the wheel would "
            "move it every time the wheel is nudged" % name)

    # The ring itself: eight anchors around the wheel's centre, none of them on top of another.
    pts = [(D["figures"]["x"], D["figures"]["y"]) for D in d["duties"].values()]
    assert len(set(pts)) == 8, "two duties share an acolyte anchor"



def test_every_placeholder_the_template_asks_for_is_filled(page):
    """A page shipped with __SOMETHING__ still in it is a page whose script does not run.

    The generator already raises on a token it cannot find; this is the other direction -- a
    token the template gained that the generator does not know about.
    """
    left = re.findall(r"__[A-Z_]+__", page)
    assert not left, "unsubstituted placeholders in the generated page: %s" % sorted(set(left))


def test_the_page_closes_its_script_and_needs_nothing_from_the_network(page):
    """Two failures that both look like a page that simply does nothing.

    An unterminated <script> is parsed and then never executed by Chrome, so the page renders
    its empty chrome and no error -- which is exactly what happened the first time this was
    generated, and took a DOM inspection rather than a console to find.

    And the brief's flat requirement: no CDN, no network. A page that quietly needed one would
    work on the machine that built it and nowhere else.
    """
    assert page.rstrip().endswith("</script>"), (
        "the page does not close its script tag, so the browser parses the script and never "
        "runs it")
    assert page.count("<script>") == page.count("</script>") == 1

    urls = re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)""", page)
    remote = [u for u in urls if re.match(r"(https?:)?//", u)]
    assert not remote, "the page fetches from the network: %s" % remote
    assert "cdn" not in page.lower().split("</style>")[0], "a CDN is referenced in the styles"


def test_the_default_state_in_the_page_is_the_generators_own(page, lab):
    """One definition of the starting layout, not two.

    The page's reset button, its first run and these tests all have to mean the same thing by
    "default". Rebuilt in JavaScript it would be the same decision written twice, and the two
    would part company the first time one moved.
    """
    m = re.search(r"var DEFAULT_STATE = (\{.*?\});\n\nvar STORE_KEY", page, re.S)
    assert m, "the page no longer carries a DEFAULT_STATE object"
    assert json.loads(m.group(1)) == lab.default_state()


def test_open_hands_the_browser_a_file_uri_for_the_page_it_just_wrote(lab, tmp_path):
    """--open is a convenience, so the two ways it can quietly do nothing are what is checked.

    A bare filesystem path handed to a browser fails the moment the checkout sits under a
    directory with a space in it -- and it works perfectly on the machine it was written on,
    which is how that bug survives. `as_uri()` resolves and percent-encodes, so this asserts the
    URI and not the path.

    The other failure is silence: webbrowser.open returns False when it cannot find a browser,
    and on a headless machine it can return True having done nothing at all. So the URL is
    printed either way and the return code stays 0 -- the page is written regardless, and a
    convenience that swallows its own failure is worse than no convenience.

    Falsified by handing the opener str(path) instead of the URI: the space case then fails.
    """
    out = tmp_path / "a folder with spaces" / "lab.html"
    seen = []

    assert lab.main(["--out", str(out)], opener=lambda u: seen.append(u) or True) == 0
    assert out.is_file(), "the page was not written"
    assert seen == [], "--open was not passed, but the browser was called anyway"

    assert lab.main(["--out", str(out), "--open"],
                    opener=lambda u: seen.append(u) or True) == 0
    assert len(seen) == 1, "--open did not reach the browser"
    assert seen[0] == out.resolve().as_uri(), (
        "the browser was handed %r rather than the file's URI %r"
        % (seen[0], out.resolve().as_uri()))
    assert seen[0].startswith("file://") and "%20" in seen[0], (
        "the space in the path was not encoded: %s" % seen[0])

    # A browser that cannot be found is reported, not swallowed, and the page still exists.
    assert lab.main(["--out", str(out), "--open"], opener=lambda u: False) == 0
    assert out.is_file()


# ---------------------------------------------------------------- the page's own rules, in node


def lab_defaults() -> dict:
    """This build's starting layout, for tests that otherwise only talk to node."""
    spec = importlib.util.spec_from_file_location("generate_layout_lab_d", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.default_state()


def _in_node(body: str) -> dict:
    """Run the page's script in node with just enough DOM for it to define its functions.

    The script bootstraps against a real document at the end, which node has none of -- so the
    stub lets every definition happen, the bootstrap is allowed to fail, and the pure functions
    are then exercised. Testing them any other way would mean copying them.

    THE SCRIPT COMES FROM THE GENERATED PAGE, not from the template with hand-written stand-ins
    for the tokens. The first version of this harness substituted its own values for __CANVAS__
    and friends, which meant every token V2 added broke it with a ReferenceError -- and, worse,
    that these tests ran against a DEFAULT_STATE of `null` while the shipped page ran against
    the real one. Building it properly costs nothing and makes the real starting layout
    available to every test below.
    """
    spec = importlib.util.spec_from_file_location("generate_layout_lab_h", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = mod.build()
    src = src[src.index("<script>") + len("<script>"):src.rindex("</script>")]
    # THE BOOTSTRAP IS CUT OFF, not caught. Wrapping the script in a try block was the first
    # attempt and it scopes every function declaration to that block -- in strict mode they
    # simply are not there afterwards. So the script is sliced at its own START marker instead,
    # which also keeps the test honest: if that marker moves, this fails loudly rather than
    # testing a shorter file.
    marker = "// START"
    assert src.count(marker) == 1, "the page's START marker moved; this harness cuts there"
    src = src[:src.index(marker)]

    harness = """
const stub = new Proxy(function(){}, {
  get: (t, k) => (k === 'style' || k === 'dataset' || k === 'classList') ? stub
       : (k === 'length') ? 0 : (k === Symbol.toPrimitive) ? (() => '') : stub,
  apply: () => stub, set: () => true,
});
globalThis.document = new Proxy({}, {get: () => stub});
// LISTENERS KEEPS WHAT THE SCRIPT SUBSCRIBED TO rather than dropping it. A handler the page
// registers is the page's behaviour just as much as a function it exports, and the only way to
// exercise one without a browser is to hold on to it and call it.
globalThis.LISTENERS = {};
globalThis.addEventListener = (k, fn) => { (LISTENERS[k] = LISTENERS[k] || []).push(fn); };
globalThis.localStorage = {getItem: () => null, setItem: () => {}};
%s
""" % src
    script = harness + "\n" + body
    # THROUGH A FILE, NOT `node -e`. The generated page is well over a hundred kilobytes now and
    # an argument that size is past what execve will take -- which surfaces as OSError 7,
    # "Argument list too long", and looks nothing like a test failure.
    with tempfile.TemporaryDirectory() as tmp:
        f = pathlib.Path(tmp) / "harness.mjs"
        f.write_text(script, encoding="utf-8")
        done = subprocess.run(["node", str(f)], capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError("node failed:\n%s" % done.stderr[-1500:])
    return json.loads(done.stdout)


@needs_node
def test_the_page_refuses_a_layout_it_cannot_honestly_draw():
    """What import does with a file that is not this module's layout.

    The lab writes JSON that a person will hand-edit and that older builds will have written, so
    the question is not whether a good file loads but what a bad one does. Accepted quietly, a
    layout for a nine-duty board would come up missing a duty with nothing on screen to say so.

    A 1200-wide canvas is deliberately NOT among the refusals: that is a V2 file, and migrate()
    widens it before validate() ever sees it. Refusing one would throw away real work over a
    number the importer is able to fix -- so the case here is a canvas that is neither.

    Falsified by removing the duty check from validate(): the first three cases then pass.
    """
    cases = {
        "seven duties": {"canvas": {"width": 1400, "height": 1200},
                         "duties": {s: {} for s in
                                    ["clerical", "taxation", "produce", "build_roads",
                                     "construct", "give_alms", "ordination"]}},
        "a city among the duties": {"canvas": {"width": 1400, "height": 1200},
                                    "duties": {s: {} for s in
                                               ["clerical", "taxation", "produce", "build_roads",
                                                "construct", "give_alms", "ordination",
                                                "allocation", "city"]}},
        "the wrong canvas": {"canvas": {"width": 900, "height": 1200},
                             "duties": {s: {} for s in
                                        ["clerical", "taxation", "produce", "build_roads",
                                         "construct", "give_alms", "ordination", "allocation"]}},
        "not an object": "a layout",
    }
    good = {"canvas": {"width": 1400, "height": 1200},
            "duties": {s: {} for s in ["clerical", "taxation", "produce", "build_roads",
                                       "construct", "give_alms", "ordination", "allocation"]}}
    body = """
DUTY_ORDER = ["clerical","taxation","produce","build_roads","construct","give_alms",
              "ordination","allocation"];
const cases = %s, good = %s, out = {};
for (const [name, d] of Object.entries(cases)){
  try { validate(d); out[name] = null; } catch (e) { out[name] = e.message; }
}
try { validate(good); out._good = null; } catch (e) { out._good = e.message; }
process.stdout.write(JSON.stringify(out));
""" % (json.dumps(cases), json.dumps(good))
    got = _in_node(body)
    assert got["_good"] is None, "a well-formed layout was refused: %s" % got["_good"]
    for name in cases:
        assert got[name], "%r was accepted" % name
    assert "taxation" in got["seven duties"] or "allocation" in got["seven duties"]
    assert "city" in got["a city among the duties"]
    assert "1400" in got["the wrong canvas"]


@needs_node
def test_an_older_layout_file_loads_with_the_new_defaults_filled_in():
    """A file written before a control existed must still open.

    The lab's own JSON is the record of a layout worth keeping, so a field added later cannot
    invalidate every file written before it. Defaults win where the file is silent and the file
    wins where it speaks -- and arrays are replaced whole, because a four-player list merged
    element-wise is a way to end up with a fifth player nobody added.

    Falsified by making deepMerge return the override wholesale: the untouched default is then
    lost and `kept` comes back undefined.
    """
    body = """
const base = {a: 1, kept: "default", nest: {x: 1, y: 2}, list: [1, 2, 3]};
const over = {a: 9, nest: {y: 7}, list: [4]};
const merged = deepMerge(base, over);
process.stdout.write(JSON.stringify({
  merged: merged,
  clampLow: clamp(-5, 0, 10), clampHigh: clamp(99, 0, 10), clampNaN: clamp("abc", 0, 10),
}));
"""
    got = _in_node(body)
    m = got["merged"]
    assert m["a"] == 9, "the file did not win where it spoke"
    assert m["kept"] == "default", "a field the file was silent about was lost"
    assert m["nest"] == {"x": 1, "y": 7}, "nested merge: %s" % m["nest"]
    assert m["list"] == [4], "arrays must be replaced, not merged: %s" % m["list"]
    assert (got["clampLow"], got["clampHigh"], got["clampNaN"]) == (0, 10, 0)


@needs_node
def test_full_screen_follows_the_browser_rather_than_the_keypress():
    """F on a lab that is mostly chrome, and the three ways that goes wrong.

    ESCAPE IS THE WHOLE REASON THIS IS WRITTEN THE WAY IT IS. The browser leaves full screen on
    Escape without the page hearing a keypress, so a page that toggled its own class on F would
    be left sitting with its toolbar and inspector hidden and the stage on a black field, and
    nothing but pressing F twice would bring them back. The class is therefore hung off
    `fullscreenchange`, which is the only thing that knows the truth, and F only ever asks.

    The second case is a refusal -- an iframe without the permission, a policy. Real full screen
    is then unavailable but the useful half is not: the chrome can still be hidden and the stage
    given the window, and the page says so rather than appearing to have ignored the key.

    The third is the caret. Every other single-key shortcut in this page is already guarded, and
    F is the one a person is most likely to type into the x/y fields by accident.

    Driven through the page's own keydown handler and its own fullscreenchange handler, against
    a Fullscreen API that behaves like a browser's -- headless Chromium will not really go full
    screen, so a screenshot cannot answer this.

    Falsified three ways: removing the fullscreenchange listener leaves the class off after F;
    neutering the catch leaves the refusal case unhandled; dropping the typing guard lets F
    fire from inside a field.
    """
    body = """
process.on("unhandledRejection", () => {});
// The bootstrap is cut off, so the live state has to be stood up here: setFull calls relayout,
// and relayout reads the current zoom off it.
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
const base = globalThis.document;
const FS = {element: null, reqs: 0, exits: 0, refuse: false, classes: new Set()};
const bodyEl = {classList: {
  toggle: (c, on) => { if (on) FS.classes.add(c); else FS.classes.delete(c); },
  contains: (c) => FS.classes.has(c),
}};
const fire = () => (LISTENERS.fullscreenchange || []).forEach(f => f());
const docEl = {requestFullscreen: () => {
  FS.reqs++;
  if (FS.refuse) return Promise.reject(new Error("denied by policy"));
  FS.element = docEl;
  return Promise.resolve().then(fire);          // as a browser does: the event, not the call
}};
globalThis.document = new Proxy({}, {get: (t, k) =>
  k === "body" ? bodyEl :
  k === "documentElement" ? docEl :
  k === "fullscreenElement" ? FS.element :
  k === "exitFullscreen" ? (() => { FS.exits++; FS.element = null;
                                    return Promise.resolve().then(fire); }) :
  base[k]});

const keydown = (LISTENERS.keydown || [])[0];
if (!keydown) { process.stdout.write(JSON.stringify({error: "no keydown handler"})); }
const settle = () => new Promise(r => setTimeout(r, 0));
let prevented = false;
const press = (key, tagName) => keydown({key: key, target: {tagName: tagName || "BODY"},
                                         shiftKey: false,
                                         preventDefault: () => { prevented = true; }});
const snap = () => ({full: FS.classes.has("full"), reqs: FS.reqs, exits: FS.exits});
const out = {listeners: Object.keys(LISTENERS)};
out.start = snap();
prevented = false; press("f");  await settle(); out.enter = snap(); out.prevented = prevented;
press("F");                     await settle(); out.exit = snap();       // capital F too
press("f");                     await settle(); out.reenter = snap();
FS.element = null; fire();                      out.escape = snap();     // the browser's doing
press("f", "INPUT");            await settle(); out.typing = snap();
press("f", "TEXTAREA");         await settle(); out.textarea = snap();
FS.refuse = true; press("f");   await settle(); await settle();
out.refused = snap();
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)
    assert "error" not in got, got.get("error")
    assert "fullscreenchange" in got["listeners"], (
        "the page does not listen for fullscreenchange, so Escape would strand it with its "
        "chrome hidden")

    assert got["start"] == {"full": False, "reqs": 0, "exits": 0}
    assert got["enter"] == {"full": True, "reqs": 1, "exits": 0}, (
        "F did not put the page in full screen: %s" % got["enter"])
    assert got["prevented"], "F did not preventDefault, so the browser's own find-bar may open"
    assert got["exit"] == {"full": False, "reqs": 1, "exits": 1}, (
        "a second F did not leave full screen and restore the chrome: %s" % got["exit"])
    assert got["reenter"]["full"] is True

    # THE ONE THAT MATTERS: no keypress at all, just the browser saying it left.
    assert got["escape"] == {"full": False, "reqs": 2, "exits": 1}, (
        "the browser left full screen and the page kept its chrome hidden -- the class is "
        "being toggled by the keypress rather than by fullscreenchange: %s" % got["escape"])

    assert got["typing"]["reqs"] == 2 and got["typing"]["full"] is False, (
        "F fired while an input had the caret: %s" % got["typing"])
    assert got["textarea"]["reqs"] == 2, "F fired while a textarea had the caret"

    assert got["refused"]["full"] is True, (
        "the browser refused full screen and the page did nothing at all; it should still hide "
        "the chrome and say so: %s" % got["refused"])


def test_the_full_screen_class_is_one_the_styles_actually_act_on(page):
    """A class nothing styles is a shortcut that appears to do nothing.

    The node test above proves `body.full` goes on and comes off at the right moments, which is
    exactly the sort of proof that can be completely true about a page where F changes nothing
    visible. So the other half is asserted here, in the stylesheet: under that class the toolbar
    and the inspector are gone and the stage is on a plain field.

    Falsified by deleting the `body.full` rules: the node test still passes.
    """
    styles = page.split("</style>")[0]
    for sel in ("body.full #bar", "body.full #side"):
        m = re.search(re.escape(sel) + r"[^{}]*\{([^}]*)\}", styles)
        assert m, "%s is not styled, so the full screen class hides nothing" % sel
        assert "display:none" in m.group(1).replace(" ", ""), (
            "%s is styled but not hidden: %s" % (sel, m.group(1)))

    assert re.search(r"body\.full\s+#app\s*\{[^}]*grid-template-columns\s*:\s*1fr", styles), (
        "the stage does not take the whole grid in full screen, so hiding the panels would "
        "leave their empty columns behind")

    # And the key is advertised, because an unlabelled shortcut is one nobody finds.
    assert re.search(r"full screen", page), "the toolbar does not mention the full screen key"


# ---------------------------------------------------------------- V2: two actions per duty


def test_an_action_owns_its_assets_and_the_two_shared_slots_own_the_geometry(lab):
    """V3's split, carried into V4 unchanged, with the slots renamed to what they now are.

    Sixteen artworks exist and two are ever on screen, so sixteen geometries have no reason to
    exist. An action carries its wording and its pictures; the two shared slots carry the only
    large-artwork boxes there are, and which action each slot shows is a field on the slot.

    Falsified by putting a box back on an action, or a picture into a slot.
    """
    d = lab.default_state()
    for slug, D in d["duties"].items():
        for slot in ("actionA", "actionB"):
            a = D[slot]
            assert set(a) == {"name", "shortLabel", "seal", "sealName", "scenic", "scenicName"}, (
                "%s/%s carries %s -- an action owns assets, not geometry"
                % (slug, slot, sorted(a)))
            for banned in ("x", "y", "width", "height", "u", "v"):
                assert banned not in a

    assert sorted(d["display"]) == ["artLeft", "artRight", "effectUpper", "highlight"], sorted(d["display"])
    for side in ("artLeft", "artRight"):
        e = d["display"][side]
        assert {"x", "y", "width", "height", "slot"} <= set(e), sorted(e)
        assert e["slot"] in ("actionA", "actionB")
        for banned in ("scenic", "image", "seal"):
            assert banned not in e, "%s stores a picture of its own" % side
    assert d["display"]["artLeft"]["slot"] != d["display"]["artRight"]["slot"], (
        "both slots show the same action, so one duty's two actions cannot be compared")



def test_the_two_artwork_slots_sit_above_the_wheel_and_never_on_it(lab):
    """Where the large artwork goes in V4, which is the opposite of where V3 put it.

    V3 tucked the two expanded slots into the side margins and deliberately let them overlap the
    wheel's rim, because the margins were narrow and the rim was the only space left. V4 has no
    margins: the wheel takes the width, and the artwork stands in the band above it, clear of the
    wheel entirely.

    Overlapping is not merely unnecessary now, it is wrong -- an image over the rim would cover
    the acolytes standing on the top of the wheel, which is the part of the board a player is
    reading while they choose.

    Falsified by moving either slot down onto the wheel.
    """
    d = lab.default_state()
    w = d["wheel"]
    for side in ("artLeft", "artRight"):
        e = d["display"][side]
        assert e["y"] + e["height"] <= w["y"], (
            "%s reaches %d px onto the wheel" % (side, e["y"] + e["height"] - w["y"]))
        assert e["x"] >= 0 and e["x"] + e["width"] <= lab.CANVAS_W, (
            "%s is not inside the module" % side)

    L, R = d["display"]["artLeft"], d["display"]["artRight"]
    assert L["width"] == R["width"] and L["height"] == R["height"], (
        "the two slots are different sizes, so the two actions are not offered evenly: "
        "%sx%s vs %sx%s" % (L["width"], L["height"], R["width"], R["height"]))
    assert L["y"] == R["y"], "the two slots are not on the same line"
    assert L["x"] + L["width"] <= R["x"], "the two slots overlap each other"
    assert L["width"] > d["tithe"]["width"], (
        "an artwork slot is no wider than Tithe, which is the alternative to it rather than a "
        "third equal option")



def test_the_eight_reference_cards_open_as_one_row_in_wheel_order(lab):
    """V3's two columns of four became one row of eight, and the order is the wheel's.

    A card is a reference, not a choice, so it is on screen in every state; eight of them across
    the top is what freed the side margins for the wheel to grow into. They are pitched evenly
    and ordered by the duty's position on the wheel, so a player reading left to right is reading
    round the ring rather than down an arbitrary list.

    Nothing in the page may depend on which half of the row a duty is in -- V3 had SUMMARY_LEFT
    and SUMMARY_RIGHT tuples and that split is precisely what V4 removed.

    Falsified by sorting the cards any other way, or by letting the row leave the module.
    """
    d = lab.default_state()
    assert not hasattr(lab, "SUMMARY_LEFT") and not hasattr(lab, "SUMMARY_RIGHT"), (
        "the two-column split is back; V4 has one row and no side to be on")

    order = [slug for slug, *_ in lab.DUTIES]
    cards = [(slug, d["duties"][slug]["card"]) for slug in order]
    xs = [c["x"] for _, c in cards]
    assert xs == sorted(xs), (
        "the cards are not left-to-right in wheel order: %s"
        % [(s, c["x"]) for s, c in cards])
    ys = {c["y"] for _, c in cards}
    assert len(ys) == 1, "the cards are not one row: %s" % sorted(ys)
    widths = {c["width"] for _, c in cards}
    assert len(widths) == 1, "the cards are not the same width: %s" % sorted(widths)

    pitches = {b["x"] - a["x"] for (_, a), (_, b) in zip(cards, cards[1:], strict=False)}
    assert len(pitches) == 1, "the cards are not evenly pitched: %s" % sorted(pitches)
    pitch = pitches.pop()
    assert pitch >= cards[0][1]["width"], "the cards overlap each other"

    first, last = cards[0][1], cards[-1][1]
    assert first["x"] >= lab.RIBBON["x"] - 1, "the row starts left of the ribbon"
    assert last["x"] + last["width"] <= lab.CANVAS_W, "the row runs off the module"
    assert last["x"] + last["width"] <= lab.RIBBON["x"] + lab.RIBBON["width"] + 1, (
        "the row is wider than the ribbon it is meant to fill")

    # Above the wheel and above the band, because a reference is read before a decision.
    assert first["y"] + first["height"] <= d["display"]["artLeft"]["y"], (
        "the ribbon overlaps the action band")
    assert first["y"] >= d["status"]["y"] + d["status"]["height"], (
        "the ribbon overlaps the instruction")



def test_every_duty_opens_with_the_wording_its_file_gives_it(lab):
    """Starting wording, and how many actions each duty offers.

    This used to assert a list of labels typed here and that Taxation was still an obvious
    placeholder. Both premises are gone: the wording moved into ui/board_v2/duty_text.json, and
    Taxation was given real wording along with the news that it has only ONE action. A list
    retyped here would now be a third copy of something that already has an owner, so this checks
    the relationship instead -- every duty opens at whatever that file says.

    Falsified by the generator inventing wording, or by a duty's action count disagreeing with
    the file.
    """
    d = lab.default_state()
    said = lab.duty_text()

    for slug, slots in said.items():
        first = slots[lab.ACTIONS[0][0]]
        assert d["duties"][slug]["actionA"]["shortLabel"] == first["shortLabel"], slug
        assert d["duties"][slug]["actionA"]["name"] == first["name"], slug

    # ONE ACTION OR TWO, and the state must agree with the file rather than carry its own idea.
    single = [s for s, v in said.items() if v[lab.ACTIONS[1][0]] is None]
    assert sorted(single) == ["allocation", "taxation"], (
        "the one-action duties are %s; Taxation and Allocation are the two that have one action "
        "each, so a change here is a change to the game" % sorted(single))
    for slug, D in d["duties"].items():
        want = 1 if said[slug][lab.ACTIONS[1][0]] is None else 2
        assert D["actions"] == want, (
            "%s says it has %d actions and its file says %d" % (slug, D["actions"], want))

    # The summary row needs something to print for every action a duty actually has.
    for slug, D in d["duties"].items():
        for i, (slot, _) in enumerate(lab.ACTIONS):
            if i >= D["actions"]:
                continue
            assert D[slot]["shortLabel"], "%s/%s has no short label for its summary" % (slug, slot)


def test_the_crowded_default_is_actually_crowded(lab):
    """The starting state is a busy board on purpose, so "busy" is what is checked.

    The question the lab exists to answer is whether this composition survives a heavy game
    state. A default with one acolyte on two duties would let it pass by being empty.

    Falsified by zeroing START_OCCUPANCY.
    """
    d = lab.default_state()
    counts = {s: D["figures"]["count"] for s, D in d["duties"].items()}
    assert sum(counts.values()) >= 18, "only %d acolytes on the board: %s" % (
        sum(counts.values()), counts)
    assert sorted(counts.values())[-1] == 4, "no duty opens full"
    assert min(counts.values()) >= 1, "a duty opens empty: %s" % counts

    mixed = [s for s, D in d["duties"].items()
             if len(set(D["figures"]["seats"][:D["figures"]["count"]])) > 1]
    assert mixed, (
        "no duty opens with more than one player on it. Majority readability is a different "
        "question from crowding and only a mixed stack asks it")

    assert sum(d["city"]["counts"].values()) >= 15, "the City opens nearly empty"
    # The in-hand pool has no visibility flag in V4 -- it is drawn whenever the view is SOWING --
    # so what is left to check is that it opens with something to count.
    assert d["inHand"]["count"] > 0, "the in-hand pool opens with nothing in it"
    assert d["inHand"]["seat"] in {p["id"] for p in d["players"]}, (
        "the in-hand pool is held by a seat that does not exist: %s" % d["inHand"]["seat"])



def test_the_acolyte_range_is_the_one_the_brief_asked_for(lab):
    """90-210 px, defaulting to 120, and a default that sits inside its own range.

    V1's figures were about 14px tall, which answers "is there an anchor here" and not "can four
    of these stand on one duty". The range is the feature, so it is pinned.
    """
    assert (lab.ACOLYTE_MIN, lab.ACOLYTE_MAX) == (90, 210)
    assert lab.ACOLYTE_MIN <= lab.ACOLYTE_DEFAULT <= lab.ACOLYTE_MAX
    assert lab.ACOLYTE_DEFAULT == 120
    d = lab.default_state()
    assert d["acolytes"]["height"] == lab.ACOLYTE_DEFAULT
    assert d["acolytes"]["style"] in ("colored", "painted")
    # A miniature is much taller than it is wide; a ratio near 1 would be a token, not a figure.
    assert 0.25 < lab.ACOLYTE_ASPECT < 0.6, lab.ACOLYTE_ASPECT


def test_the_city_opens_wide_enough_for_four_seats_in_one_row(lab):
    """The City aggregates, so its whole content is four figures and four counts side by side.

    Found by looking at the rendered page rather than by reasoning: at the default acolyte
    height the fourth player wrapped onto a second row and was clipped by the box. The arithmetic
    is reproduced here so a later change to the acolyte default or the City size cannot quietly
    reintroduce it.

    Falsified by putting the City back to 290 wide.
    """
    d = lab.default_state()
    fig_h = lab.ACOLYTE_DEFAULT * lab.ACOLYTE_RATIOS["city"] / 100
    fig_w = fig_h * lab.ACOLYTE_ASPECT
    count_w = 20                      # "x7" at the 15px monospace the rows use
    gap, inset = 16, 8
    needed = 4 * (fig_w + 4 + count_w) + 3 * gap + 2 * inset
    assert d["city"]["width"] >= needed, (
        "the City opens %d px wide but four seats need about %d, so the fourth wraps and is "
        "clipped" % (d["city"]["width"], needed))
    assert d["city"]["height"] >= fig_h + 2 * inset, (
        "the City is shorter than the figure it has to hold")


# ---------------------------------------------------------------- V2: the page's rules, in node


@needs_node
def test_a_v1_layout_survives_every_migration_to_the_v4_shape():
    """What migration does with a file composed before a duty had two actions, and before the
    action artwork lost its box.

    A V1 file goes through every step: its single artwork becomes Action A, Action A's box is
    dropped while its picture becomes the action's scenic asset, and then V4 rearranges what is
    left. Three hops in one function on purpose -- an importer that only knew about the most
    recent change would open a V1 file into a shape that has been wrong for three versions.

    A V1 file is a real layout somebody spent time on. Refusing it would throw that away for no
    gain, and accepting it silently in the wrong slot would be worse -- so the single artwork
    becomes Action A, keeping its own position, size, z and image, and Action B starts from this
    build's defaults beside it.

    The rest of the V1 shape moves too: anchorX/anchorY became x/y, the compact flag became one
    of three named arrangements, and the city's one list of players split into global identity
    and per-city counts.

    IMAGES ARE HOISTED OUT OF THE STATE. V1 inlined data URLs into the layout; V2 keeps a key
    and puts the bytes in a pool beside it, which is what makes the autosave small and the undo
    history cheap. A migrated file must come through with the bytes in the pool and a key -- not
    a data URL -- left in the state.

    Falsified by deleting the `D.art && !D.actionA` branch: actionA then comes back as the
    default rather than as the V1 artwork, and the image never reaches the pool.
    """
    v1 = {
        "version": 1,
        "canvas": {"width": 1200, "height": 1200},
        "wheel": {"x": 210, "y": 333, "width": 780, "height": 413, "naturalRatio": 0.5299,
                  "opacity": 1, "locked": False, "image": None, "imageName": None},
        "duties": {},
        "city": {"x": 470, "y": 1000, "width": 260, "height": 150, "locked": False,
                 "visible": True,
                 "players": [{"id": "p1", "label": "Anne", "colour": "#112233", "count": 9,
                              "visible": True},
                             {"id": "p2", "label": "Bo", "colour": "#445566", "count": 2,
                              "visible": False}],
                 "label": {"x": 545, "y": 970, "width": 110, "visible": True}},
        "inHand": {"x": 525, "y": 465, "width": 150, "height": 150, "locked": False,
                   "visible": False, "count": 3, "textMode": "left", "colour": "#112233"},
        "guides": {}, "mode": "edit",
    }
    order = ["clerical", "taxation", "produce", "build_roads", "construct", "give_alms",
             "ordination", "allocation"]
    for i, s in enumerate(order):
        v1["duties"][s] = {
            "name": s.title(), "clock": i * 45,
            "art": {"x": 111 + i, "y": 222 + i, "width": 333, "height": 180, "opacity": 0.5,
                    "fit": "cover", "z": 7, "locked": True, "visible": True,
                    "image": ("data:image/png;base64,AAAA" if s == "clerical" else None),
                    "imageName": ("old.png" if s == "clerical" else None)},
            "label": {"x": 10 + i, "y": 20 + i, "width": 110, "visible": True},
            "figures": {"anchorX": 400 + i, "anchorY": 500 + i, "count": 3, "spacing": 34,
                        "compact": True},
        }
    body = """
const v1 = %s;
const out = {};
applyState(v1);
const C = S.duties.clerical;
out.actionA = {keys: Object.keys(C.actionA).sort(),
               scenic: C.actionA.scenic, scenicName: C.actionA.scenicName,
               name: C.actionA.name, shortLabel: C.actionA.shortLabel};
out.actionB = {scenic: C.actionB.scenic, name: C.actionB.name};
out.stillHasArt = ("art" in C) || ("art" in C.actionA);
out.figures = {x: C.figures.x, y: C.figures.y, arrangement: C.figures.arrangement,
               anchorX: C.figures.anchorX === undefined ? null : C.figures.anchorX,
               seats: C.figures.seats};
out.players = S.players.map(p => [p.id, p.label, p.colour]);
out.cityCounts = S.city.counts;
out.cityShown = S.city.shown;
out.cityHasPlayers = ("players" in S.city);
out.inHandSeat = S.inHand.seat;
out.version = S.version;
out.pool = Object.keys(IMAGES).map(k => IMAGES[k]);
out.stateHasDataUrl = JSON.stringify(S).indexOf("data:") >= 0;
process.stdout.write(JSON.stringify(out));
""" % json.dumps(v1)
    got = _in_node(body)

    a = got["actionA"]
    assert a["keys"] == ["name", "scenic", "scenicName", "seal", "sealName", "shortLabel"], (
        "the migrated Action A is not a V3 asset object: %s" % a["keys"])
    assert not got["stillHasArt"], "an `art` object survived the migration"
    # A V1 file has no action objects at all -- it carried a single `art` -- so the migration
    # has to synthesise them, and what it synthesises is this build's default wording. Both
    # fields, because they stopped being the same string in V4.5.
    assert a["shortLabel"] == "Gain X piety", (
        "Action A did not take this build's default wording: %r" % a["shortLabel"])
    assert a["name"] == "Devotion", (
        "Action A did not take this build's default action name: %r" % a["name"])

    b = got["actionB"]
    assert b["scenic"] is None, "Action B came up holding an image nothing loaded"

    # The image: bytes in the pool, a key in the state, and no data URL anywhere in the state.
    # Through TWO migrations -- the V1 artwork became Action A's art, and that art's picture then
    # became Action A's scenic asset when the boxes went away.
    assert got["pool"] == ["data:image/png;base64,AAAA"], (
        "the V1 image did not reach the pool: %s" % got["pool"])
    assert a["scenic"] and not str(a["scenic"]).startswith("data:"), (
        "the state still holds a data URL rather than a pool key: %r" % a["scenic"])
    assert a["scenicName"] == "old.png", "the filename was lost, so a lost asset cannot say which"
    assert not got["stateHasDataUrl"], "a data URL survived somewhere in the migrated state"

    f = got["figures"]
    # anchorX/anchorY became x/y -- and then V4 REPLACED the coordinate, because a V1 anchor
    # rings a 780px wheel and V4's is 1372px, so carrying the number across would put the ring
    # inside the hub. The conversion still has to happen: the old key must not survive as a key
    # the page would later read, and what is left has to be this build's own ring.
    assert f["anchorX"] is None, "the old anchorX key survived"
    want = lab_defaults()["duties"]["clerical"]["figures"]
    assert (f["x"], f["y"]) == (want["x"], want["y"]), (
        "the migrated anchor is not on this build's ring: %s" % f)
    assert f["arrangement"] == "compact", (
        "the V1 compact flag did not become the compact arrangement: %s" % f)
    assert len(f["seats"]) == 4, "the migrated figures have no seat list"

    assert got["players"][0] == ["p1", "Anne", "#112233"], (
        "player identity did not come out of the city list: %s" % got["players"])
    assert len(got["players"]) == 4, "the two-player V1 file did not fill out to four"
    assert got["cityCounts"]["p1"] == 9 and got["cityCounts"]["p2"] == 2, got["cityCounts"]
    assert got["cityShown"]["p1"] is True and got["cityShown"]["p2"] is False, got["cityShown"]
    assert not got["cityHasPlayers"], "the V1 city player list survived the split"
    assert got["inHandSeat"] == "p1", "the in-hand pool kept a raw colour instead of a seat"
    assert got["version"] == 4, "a migrated file did not come out at the current version"


@needs_node
def test_an_attached_object_holds_its_place_on_the_wheel_through_a_move_and_a_scale():
    """The wheel-relative conversion, in both directions and through the wheel changing.

    An anchor stored at an absolute stage position is in the wrong place the moment the wheel is
    resized, and the wheel's size is the single thing most likely to change while composing. So
    the attached objects store a fraction of the wheel's box instead, and the absolute value is
    a cache that is re-derived rather than trusted.

    Both directions are checked because both exist and they are not the same operation:
    syncAttached re-derives x/y from u/v after the wheel moves, and reanchorAll re-derives u/v
    from x/y when the global switch goes on, so that attaching records where things are now
    rather than teleporting them to where they were.

    Falsified by making syncAttached a no-op (the anchor stops following), by making it ignore
    the global switch (a detached anchor follows the wheel anyway), or by calling syncAttached
    in place of reanchorAll on the switch (attaching then moves everything).
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
const F = S.duties.clerical.figures;
out.startsAttached = !!F.attached && S.attachToWheel === true;
out.u0 = F.u; out.v0 = F.v;
// From the same derivation the comparison will use. u/v is stored to four places, so the
// absolute cache can sit a pixel from the generator's own rounding of the same point -- a
// fixed offset, not a drift, since x/y is always re-derived from u/v and never from itself.
syncAttached();
const before = {x: F.x, y: F.y};

// 1. the wheel moves: the anchor moves with it, by the same amount, and u/v does not budge.
S.wheel.x += 70; S.wheel.y -= 25;
syncAttached();
out.afterMove = {dx: F.x - before.x, dy: F.y - before.y, u: F.u, v: F.v};

// 2. the wheel scales: the anchor lands where u/v says it should, not where it was.
S.wheel.width = Math.round(S.wheel.width * 1.5);
S.wheel.height = Math.round(S.wheel.height * 1.5);
syncAttached();
out.afterScale = {x: F.x, y: F.y, u: F.u,
                  want: Math.round(S.wheel.x + F.u * S.wheel.width)};

// 3. the round trip: a point converted out and back is the point it started as.
const uv = toUV(612, 431), back = fromUV(uv.u, uv.v);
out.roundTrip = {x: Math.round(back.x * 1000) / 1000, y: Math.round(back.y * 1000) / 1000};

// 4. the global switch off: the wheel may move without dragging anything along.
S.attachToWheel = false;
const held = {x: F.x, y: F.y};
S.wheel.x += 200; syncAttached();
out.whileFree = {dx: F.x - held.x, dy: F.y - held.y};

// 5. the switch back on: u/v is re-derived from where things are, so nothing moves.
S.attachToWheel = true;
reanchorAll();
out.onAttach = {dx: F.x - held.x, uChanged: F.u !== out.u0};
syncAttached();
out.afterReattach = {dx: F.x - held.x};

// 6. the art is never attachable, whatever the switch says.
out.artAttachable = attachable("art");
out.cityAttachable = attachable("city");
out.figsAttachable = attachable("figs");
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)
    assert got["startsAttached"], "the default does not open attached"

    m = got["afterMove"]
    assert (m["dx"], m["dy"]) == (70, -25), "the anchor did not follow the wheel: %s" % m
    assert m["u"] == got["u0"] and m["v"] == got["v0"], (
        "moving the wheel changed the normalized coordinates: %s" % m)

    s = got["afterScale"]
    assert s["u"] == got["u0"], "scaling the wheel changed u"
    assert abs(s["x"] - s["want"]) <= 1, (
        "after a 1.5x scale the anchor is at %s but u/v puts it at %s" % (s["x"], s["want"]))

    assert abs(got["roundTrip"]["x"] - 612) < 0.01 and abs(got["roundTrip"]["y"] - 431) < 0.01, (
        "design -> u/v -> design is not the identity: %s" % got["roundTrip"])

    assert got["whileFree"] == {"dx": 0, "dy": 0}, (
        "the wheel moved while attachment was off and dragged the anchor with it: %s"
        % got["whileFree"])
    assert got["onAttach"]["dx"] == 0 and got["onAttach"]["uChanged"], (
        "turning attachment on moved the anchor instead of recording where it already was: %s"
        % got["onAttach"])
    assert got["afterReattach"]["dx"] == 0, "the re-derived u/v does not reproduce the position"

    # THE CALL SITE, pinned separately. The two passes above are proven to do opposite things,
    # but which one the global switch calls is a line in a DOM event handler that this harness
    # cannot reach -- and swapping them there is a real mistake that leaves both functions
    # correct and the button wrong. The browser run exercises the button itself; this keeps the
    # repo suite from missing the swap.
    src = TMPL.read_text(encoding="utf-8")
    handler = re.search(r"el\(\"attAll\"\)\.onclick[\s\S]{0,600}?\n  \};", src)
    assert handler, "the global attachment toggle's handler could not be found"
    assert "reanchorAll()" in handler.group(0), (
        "the attachment toggle does not call reanchorAll. Turning attachment ON must record "
        "where things are now; syncAttached there would move them to where they used to be")
    assert "syncAttached()" not in handler.group(0), (
        "the attachment toggle calls syncAttached, which moves everything to the stored u/v "
        "instead of recording the present composition")

    assert got["figsAttachable"] is True
    assert got["artAttachable"] is False, (
        "the scenic art can be attached to the wheel. How far it overlaps the wheel is the "
        "question this lab exists to ask, so binding it would answer that by fiat")
    assert got["cityAttachable"] is False, "the City is a reserve outside the wheel"


@needs_node
def test_the_autosave_carries_no_image_bytes_but_still_knows_the_filenames():
    """The requirement that the browser store holds geometry and settings, never assets.

    A handful of full-resolution scenic images as data URLs is tens of megabytes and
    localStorage gives a page about five, so an autosave that embedded them would start throwing
    QuotaExceededError at exactly the point the layout got interesting -- and the failure would
    look like "my work stopped saving" rather than like an image problem.

    The pool makes this structural: there are no image bytes in the state to save. The strip
    pass is the belt to that's braces, so a future field holding a data URL cannot quietly
    reintroduce it, and it is what this asserts on.

    The three assets are a duty's scenic art, Tithe's face and the wheel -- V4's City has no
    background image of its own, since it is now a compact region in the action band rather than
    a scenic panel, so a session that collected one would be collecting a field nothing draws.

    THE FILENAME SURVIVES, which is the other half. An asset lost to a refresh has to be able to
    say which file to reload rather than rendering an empty box.

    Falsified by making stripDataUrls the identity function.
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
// As if three assets had been loaded: keys in the state, bytes in the pool.
const k1 = putImage("data:image/png;base64,AAAA");
const k2 = putImage("data:image/webp;base64,BBBB");
const k3 = putImage("data:image/svg+xml,%3Csvg/%3E");
S.duties.clerical.actionA.scenic = k1;
S.duties.clerical.actionA.scenicName = "clerical_piety.png";
S.tithe.image = k2; S.tithe.imageName = "tithe_seal.png";
S.wheel.image = k3; S.wheel.imageName = "wheel.svg";
S.acolytes.painted.p1 = k1; S.acolytes.paintedNames.p1 = "acolyte.png";

const saved = JSON.stringify(stripDataUrls(S));
out.hasData = saved.indexOf("data:") >= 0;
out.keepsKey = saved.indexOf(k1) >= 0;
out.keepsNames = ["clerical_piety.png", "tithe_seal.png", "wheel.svg", "acolyte.png"]
                   .every(n => saved.indexOf(n) >= 0);
out.keepsGeometry = JSON.parse(saved).duties.clerical.card.x
                    === S.duties.clerical.card.x;
out.bytes = saved.length;

// And the other direction: a state that somehow acquired a raw data URL is scrubbed anyway.
S.somethingNew = {sneaky: "data:image/png;base64,CCCC", fine: 12};
const saved2 = JSON.stringify(stripDataUrls(S));
out.scrubbed = saved2.indexOf("CCCC") < 0 && saved2.indexOf('"fine":12') >= 0;

// A lab session, on the other hand, may carry the bytes -- and only the ones in use.
out.sessionWith = Object.keys(labSession(true).images).length;
out.sessionWithout = Object.keys(labSession(false).images).length;
S.duties.clerical.actionA.scenic = null;
S.acolytes.painted.p1 = null;
out.sessionAfterClear = Object.keys(labSession(true).images).length;
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)
    assert not got["hasData"], "the autosave payload contains an image data URL"
    assert got["keepsKey"], (
        "the autosave dropped the image key, so a reload cannot say what is missing")
    assert got["keepsNames"], "the autosave dropped the filenames"
    assert got["keepsGeometry"], "the strip pass damaged the geometry"
    assert got["bytes"] < 60000, "the autosave payload is %d bytes" % got["bytes"]
    assert got["scrubbed"], "a data URL in a field the strip pass did not know about survived"

    assert got["sessionWith"] == 3, (
        "a Lab Session with images should carry the three distinct assets in use, not %d"
        % got["sessionWith"])
    assert got["sessionWithout"] == 0, "a geometry-only Lab Session carried image bytes"
    assert got["sessionAfterClear"] == 2, (
        "clearing an image did not drop its bytes from the next export: %d left"
        % got["sessionAfterClear"])


@needs_node
def test_the_game_layout_export_is_the_v4_schema_and_carries_no_editor_state():
    """The production export, and where the line between design and session actually falls.

    It is not "geometry in, everything else out". A box alone was too little: the real UI could
    place the instruction and then not know what it says, how big it is or whether it is centred,
    and could place the two artwork slots without knowing whether they cover or contain. Those
    were decided in this tool and are part of the design.

    What stays out is what somebody happened to be DOING while composing -- which object is
    selected, which duty is reached or previewed, the mode, the zoom, the guides, the ghosts, the
    history, the locks, the image pool -- and the occupancy counts and seats, which are the
    crowding test this session is running rather than a fact about the layout. The layout says
    where the pieces go, not which pieces are on the board today.

    Falsified by returning a clone of S with a few keys deleted: the guide flags, the locks, the
    seats and the current selection all come straight back.
    """
    body = """
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
const g = gameLayout();
process.stdout.write(JSON.stringify({layout: g, text: JSON.stringify(g)}));
"""
    got = _in_node(body)
    g, text = got["layout"], got["text"]

    # ---- what it must carry
    assert g["version"] == 4
    assert g["canvas"] == {"width": 1400, "height": 1200}
    for key in ("status", "wheel", "duties", "artwork", "highlight", "tithe", "city", "acolytes"):
        assert key in g, "the game layout is missing %r" % key

    # THE INSTRUCTION: where it sits AND what it says in each state.
    assert set(g["status"]) == {"x", "y", "width", "height", "size", "align", "opacity",
                                "visible", "byView"}, sorted(g["status"])
    assert sorted(g["status"]["byView"]) == ["action", "ready", "sow"]
    for v, entry in g["status"]["byView"].items():
        assert set(entry) == {"main"} and entry["main"], (v, entry)

    # THE WHEEL CARRIES ITS RATIO, because 32 degrees is a design invariant rather than a
    # consequence of the box: the production UI has to know it is a circle at that elevation.
    assert set(g["wheel"]) == {"x", "y", "width", "height", "ratio", "ground", "opacity"}, \
        sorted(g["wheel"])
    assert abs(g["wheel"]["ratio"] - 0.5299) < 0.0005, g["wheel"]["ratio"]
    assert g["wheel"]["height"] == round(g["wheel"]["width"] * g["wheel"]["ratio"])

    assert len(g["duties"]) == 8
    for slug, d in g["duties"].items():
        # `actions` travels because the real UI cannot infer it: a one-action duty still
        # carries both wording slots, the second simply saying nothing.
        assert set(d) == {"name", "actions", "card", "actionA", "actionB",
                          "figures"}, sorted(d)
        assert set(d["card"]) == {"x", "y", "width", "height", "visible"}, sorted(d["card"])
        for slot in ("actionA", "actionB"):
            assert set(d[slot]) == {"name", "shortLabel"}, (
                "%s/%s exports %s -- an action carries wording, not a box" % (slug, slot,
                                                                             sorted(d[slot])))
        # WHERE the acolytes stand, not WHO is standing there.
        assert set(d["figures"]) == {"x", "y", "u", "v", "spacing", "arrangement", "attached"}, \
            sorted(d["figures"])
        assert "label" not in d, "%s exports a duty label, which V4 removed" % slug
        assert "summary" not in d, "%s exports a V3 summary box" % slug
    # BOTH fields travel, and they are two different things: the action's name and what it
    # does. They were the same string until V4.5, so an export carrying only one of them would
    # have looked complete.
    assert g["duties"]["clerical"]["actionA"]["shortLabel"] == "Gain X piety"
    assert g["duties"]["clerical"]["actionA"]["name"] == "Devotion"

    for side in ("left", "right"):
        e = g["artwork"][side]
        assert set(e) == {"x", "y", "width", "height", "slot", "fit", "opacity", "visible",
                          "labelVisible", "labelSize", "nameSize"}, sorted(e)
        assert e["slot"] in ("actionA", "actionB")
    assert g["artwork"]["left"]["slot"] != g["artwork"]["right"]["slot"]

    assert set(g["highlight"]) == {"width", "height", "dy", "style", "visible", "opacity",
                                   "colour"}, sorted(g["highlight"])
    # THE TOKEN SIZING TRAVELS, THE POOL KEY DOES NOT. How big the tokens are and how far apart
    # they sit were decided here and the real UI cannot recompute them; which slot in this
    # session's image pool happens to hold the bytes is not a fact about the layout at all.
    # `iconName` is the handle production resolves against, exactly as the action artwork is
    # identified by filename rather than by bytes.
    assert set(g["tithe"]) == {"x", "y", "width", "height", "visible", "label", "labelSize",
                               "resources", "tokenSize", "tokenSpread"}, sorted(g["tithe"])
    # HOW BIG A LINE OF TYPE IS TRAVELS, on the same footing as status.size: it was decided here
    # and the real UI cannot recover it from anything else in the file.
    assert isinstance(g["tithe"]["labelSize"], int) and g["tithe"]["labelSize"] > 0
    assert isinstance(g["tithe"]["tokenSize"], int) and g["tithe"]["tokenSize"] > 0
    assert isinstance(g["tithe"]["tokenSpread"], int) and g["tithe"]["tokenSpread"] >= 0
    assert "tokenGap" not in g["tithe"], (
        "the flex pyramid's gap exported beside the triangle's spread")
    assert [r["key"] for r in g["tithe"]["resources"]] == ["W", "S", "Ag"]
    assert all(set(r) == {"key", "name", "iconName"}
               for r in g["tithe"]["resources"]), g["tithe"]["resources"]
    assert all(r["iconName"] is None for r in g["tithe"]["resources"]), (
        "the default state names an icon it has not got")
    assert '"icon"' not in text.replace('"iconName"', ""), (
        "the production export carries an image-pool key for a tithe token")
    assert set(g["city"]) == {"x", "y", "width", "height", "visible", "label",
                              "labelSize"}, sorted(g["city"])
    assert isinstance(g["city"]["labelSize"], int) and g["city"]["labelSize"] > 0
    assert "counts" not in g["city"] and "shown" not in g["city"], (
        "the City exports this session's occupancy as production layout")

    assert "inHand" not in g, (
        "the in-hand pool is exported as a box. It is drawn inside the City's region in V4, so a "
        "box of its own would be a second opinion about where it is")
    assert "expandedActions" not in g, "the V3 slot name survived in the export"
    assert set(g["acolytes"]) == {"height", "ratios"}, sorted(g["acolytes"])

    # ---- what it must not
    for key in ("guides", "mode", "zoom", "view", "selectedDuty", "previewDuty", "display",
                "showGhosts", "attachToWheel", "background", "players", "summaryDim",
                "connectors", "inHandOverride", "titheInSummary"):
        assert key not in g, "the game layout carries the editor's %r" % key
    for field in ('"locked"', '"image"', '"imageName"', '"seal"', '"scenic"', '"seats"',
                  '"clock"', '"naturalRatio"', '"ratioSource"', '"assetRatio"', '"count"',
                  '"preset"', "data:", "base64"):
        assert field not in text, (
            "the game layout carries %s, which is editor or session state" % field)



@needs_node
def test_the_wheels_aspect_ratio_is_judged_from_the_viewbox_and_refuses_everything_else():
    """An SVG's viewBox is the authority on its shape; the browser's naturalWidth is not.

    The wheel arrives already projected, and adopting its shape rather than imposing one is the
    single promise this page makes about it. A responsive SVG -- width="100%" height="100%" --
    is exactly what a drawing exported for a game board looks like, and a browser asked for its
    naturalWidth reports the default 300x150, i.e. a ratio of 0.5, which is close enough to
    sin(32) = 0.5299 that the wrong answer would look entirely plausible on screen.

    WHAT IS CHECKED HERE is the decoding and the judging -- svgTextOf and ratioFromViewBox --
    which is where the refusals live and which is ordinary string work. The middle step, pulling
    the attribute out of a parsed document, needs a DOMParser that node does not have; that leg
    is covered end to end by the browser run, which loads a real responsive SVG and asserts the
    page ends up at ratio 0.6 from source "viewBox".

    Every refusal returns 0 rather than a guess, because 0 is what makes the caller fall back to
    the browser's measurement instead of silently re-shaping the asset.

    Falsified by letting ratioFromViewBox accept a three-number viewBox or a zero width: the
    malformed cases then come back as numbers.
    """
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
           'viewBox="0 0 1000 600"><ellipse cx="500" cy="300" rx="495" ry="295"/></svg>')
    body = """
const svg = %s;
const plain = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
const b64 = "data:image/svg+xml;base64," + Buffer.from(svg).toString("base64");
globalThis.atob = s => Buffer.from(s, "base64").toString("binary");
process.stdout.write(JSON.stringify({
  decodePlain: svgTextOf(plain) === svg,
  decodeB64: svgTextOf(b64) === svg,
  decodeNotSvg: svgTextOf("data:image/png;base64,AAAA"),
  decodeNothing: svgTextOf(null),
  ratio: ratioFromViewBox("0 0 1000 600"),
  ratioCommas: ratioFromViewBox("0,0,1000,600"),
  ratioSpaced: ratioFromViewBox("  0 0 1000 600  "),
  ratioOffset: ratioFromViewBox("-50 -30 1000 600"),
  threeNumbers: ratioFromViewBox("0 0 1000"),
  fiveNumbers: ratioFromViewBox("0 0 1000 600 7"),
  zeroWidth: ratioFromViewBox("0 0 0 600"),
  negative: ratioFromViewBox("0 0 -1000 600"),
  words: ratioFromViewBox("a b c d"),
  empty: ratioFromViewBox(""),
  missing: ratioFromViewBox(null),
  // and the whole path, which returns 0 here for want of a DOMParser rather than a wrong number
  wholePathWithoutADom: svgViewBoxRatio(plain),
}));
""" % json.dumps(svg)
    got = _in_node(body)

    assert got["decodePlain"], "a percent-encoded SVG data URL did not decode"
    assert got["decodeB64"], "a base64 SVG data URL did not decode"
    assert got["decodeNotSvg"] == "" and got["decodeNothing"] == "", (
        "svgTextOf returned something for a non-SVG input")

    for name in ("ratio", "ratioCommas", "ratioSpaced", "ratioOffset"):
        assert abs(got[name] - 0.6) < 1e-9, "%s came back as %r, not 0.6" % (name, got[name])

    for name in ("threeNumbers", "fiveNumbers", "zeroWidth", "negative", "words", "empty",
                 "missing"):
        assert got[name] == 0, (
            "%s returned %r instead of refusing -- a caller would adopt it as the wheel's shape"
            % (name, got[name]))

    assert got["wholePathWithoutADom"] == 0, (
        "without a DOMParser the whole path must refuse rather than throw or guess")


@needs_node
def test_undo_restores_the_layout_without_dragging_the_view_back_with_it():
    """What belongs in history and what does not.

    The brief lists moves, sizes, images, counts and the background as undoable. It also says
    not to record editor-only transient state. Edit/Clean mode, the zoom level and -- since V3 --
    which of the three view states is on screen are all how the layout is being LOOKED at rather
    than part of it; they are among the fields the Game Layout export leaves out for the same
    reason. So they are saved but never recorded, and an undo carries the current view forward
    rather than restoring an old one. Flipping between SOW and ACTION twenty times to compare
    them must not cost twenty presses of undo. V4 adds which duty is being PREVIEWED
    to the same list, for the same reason: opening a card to read it is looking, not composing.

    Without that, toggling Clean Preview twice to check something would cost two presses of undo
    before the move you actually wanted to reverse, and undoing a move while zoomed in would
    throw the page back to whatever zoom it was at three edits ago.

    Falsified by dropping the view carry-over in stepHistory: `zoomAfterUndo` comes back as the
    old zoom rather than the current one.
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
histReset();
const x0 = S.duties.clerical.card.x;

S.duties.clerical.card.x = x0 + 100; record();
S.duties.clerical.card.x = x0 + 200; record();
out.depth = HIST.length;

// The view changes after the edits, and then we undo.
S.zoom = 125; S.mode = "clean"; S.view = "action";
stepHistory(-1);
out.afterUndo = {x: S.duties.clerical.card.x, zoom: S.zoom,
                 mode: S.mode, view: S.view};
stepHistory(-1);
out.afterTwo = S.duties.clerical.card.x;
stepHistory(1);
out.afterRedo = S.duties.clerical.card.x;

// A gesture records once, however many times the model is written during it. Measured from a
// fresh stack: the undo/redo above left HPOS mid-stack, and the next record legitimately drops
// the entries in front of it, which would make the arithmetic here about truncation instead.
histReset();
const base = HIST.length;
gesture = true;
for (let i = 0; i < 25; i++){ S.duties.clerical.card.y += 1; record(); }
gesture = false; record();
out.gestureEntries = HIST.length - base;

// Recording an unchanged state is not an entry.
record(); record();
out.noopEntries = HIST.length - base;

// The stack is capped and drops from the old end.
for (let i = 0; i < HIST_MAX + 20; i++){ S.duties.clerical.card.y += 1; record(); }
out.capped = HIST.length;
out.max = HIST_MAX;
out.newestKept = JSON.parse(HIST[HIST.length - 1]).duties.clerical.card.y
                 === S.duties.clerical.card.y;
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)
    assert got["depth"] == 3, "two edits after the reset should be three entries: %s" % got["depth"]
    assert got["afterUndo"]["x"] is not None
    assert (got["afterUndo"]["zoom"] == 125 and got["afterUndo"]["mode"] == "clean"
            and got["afterUndo"]["view"] == "action"), (
        "undo restored the view state along with the layout: %s" % got["afterUndo"])
    assert got["afterRedo"] > got["afterTwo"], "redo did not step forward"

    assert got["gestureEntries"] == 1, (
        "25 writes inside one gesture became %d history entries" % got["gestureEntries"])
    assert got["noopEntries"] == 1, "recording an unchanged state added an entry"

    assert 30 <= got["max"] <= 50, "the history cap is %d, outside the brief's 30-50" % got["max"]
    assert got["capped"] == got["max"], (
        "the stack grew to %d past a cap of %d" % (got["capped"], got["max"]))
    assert got["newestKept"], "the cap dropped the newest entry instead of the oldest"


# ---------------------------------------------------------------- V3: the two view states


@needs_node
def test_the_wheel_is_identical_in_all_three_view_states():
    """The invariant the whole comparison rests on.

    The point of several states is to judge their compositions against each other, and that only
    works if the thing they share does not move. The brief says so twice and lists it separately
    in the acceptance test, which is a fair signal about how easy it would be to break: a state
    switch that nudged the wheel by a few pixels would make every other difference untrustworthy
    without ever looking wrong.

    V4 raises the stakes, because the wheel is now most of the module and the three states differ
    only in the band above it. If the wheel moved there would be almost nothing left that did not.

    So this flips through all three repeatedly and asserts on the geometry, and then asserts the
    stronger version -- that the state is not merely restored but never written at all, by
    checking a changed wheel survives the flips rather than being reset to any state's idea of it.

    Falsified by giving setView any wheel geometry to write.
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
const snap = () => JSON.stringify(S.wheel);
const states = ["ready", "sow", "action"];
out.each = {};
states.forEach(v => { setView(v); out.each[v] = snap(); });
states.forEach(v => { setView(v); });
states.slice().reverse().forEach(v => { setView(v); });
out.afterFlips = snap();

// The stronger claim: a wheel the person has moved and resized stays exactly where they put it
// across every flip. A state switch that "restored" the wheel would pass the first check and
// fail this one.
S.wheel.x = 300; S.wheel.y = 400; S.wheel.width = 812;
S.wheel.height = Math.round(812 * S.wheel.naturalRatio);
out.moved = snap();
out.movedEach = {};
states.forEach(v => { setView(v); out.movedEach[v] = snap(); });

// The City, the ribbon and the acolyte anchors are required to be identical too -- everything
// except the band's contents, which is what the three states are FOR.
out.cityEach = {}; out.cardEach = {}; out.figEach = {};
states.forEach(v => {
  setView(v);
  out.cityEach[v] = JSON.stringify(S.city);
  out.cardEach[v] = JSON.stringify(DUTY_ORDER.map(s => S.duties[s].card));
  out.figEach[v]  = JSON.stringify(DUTY_ORDER.map(s => [S.duties[s].figures.x,
                                                        S.duties[s].figures.y]));
});
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)
    assert len(set(got["each"].values())) == 1, (
        "the wheel's geometry changed across a view switch: %s" % got["each"])
    assert got["afterFlips"] == got["each"]["ready"], (
        "the wheel drifted over repeated flips: %s" % got["afterFlips"])

    assert set(got["movedEach"].values()) == {got["moved"]}, (
        "a wheel the person moved was rewritten by a view switch:\n  set to %s\n  became %s"
        % (got["moved"], got["movedEach"]))

    for name in ("cityEach", "cardEach", "figEach"):
        assert len(set(got[name].values())) == 1, (
            "%s changed across a view switch: %s" % (name[:-4], got[name]))


def test_an_acolyte_at_the_top_of_the_wheel_stays_off_the_action_band(lab):
    """The overhang that only showed up in a screenshot, pinned as arithmetic.

    An acolyte stands ON its anchor: the anchor is its feet, and the figure reaches upwards by
    its full height. The anchor ring is an ellipse inside the wheel, so the 12 o'clock duty's
    figures are the ones closest to the top edge -- and at a vertical radius of 0.40 a 120 px
    acolyte reached past that edge and drew over the artwork in the band above.

    Narrowing the ring vertically to 0.34 is not a cosmetic change: the ring is what the imported
    wheel asset's own duty spaces will be matched against, so it has to be a ring the figures fit
    inside. The margin is small on purpose -- the acolytes should stand near the rim -- which is
    exactly why it is worth holding a number to.

    Falsified by widening FIG_RY, or by raising the acolyte height past what the gap allows.
    """
    d = lab.default_state()
    w = d["wheel"]
    top_anchor = min(D["figures"]["y"] for D in d["duties"].values())
    height = d["acolytes"]["height"] * d["acolytes"]["ratios"]["duty"] / 100
    head = top_anchor - height

    band = d["display"]["artLeft"]
    band_bottom = band["y"] + band["height"]
    assert head >= band_bottom, (
        "a %d px acolyte standing at 12 o'clock reaches y=%d, which is %d px into the action "
        "band above the wheel" % (height, head, band_bottom - head))
    assert head >= w["y"] - 10, (
        "the 12 o'clock acolytes stand %d px above the wheel's own top edge" % (w["y"] - head))

    # And the ring really is inside the wheel, not merely clear of the band.
    for slug, D in d["duties"].items():
        f = D["figures"]
        assert w["x"] <= f["x"] <= w["x"] + w["width"], "%s's anchor is off the wheel" % slug
        assert w["y"] <= f["y"] <= w["y"] + w["height"], "%s's anchor is off the wheel" % slug
    assert lab.FIG_RY / lab.WHEEL_H < 0.38, (
        "the anchor ring is %.2f of the wheel's height; at 0.40 the top figures overhang it"
        % (lab.FIG_RY / lab.WHEEL_H))


def test_the_reached_duty_highlight_is_drawn_above_the_wheel_and_below_the_acolytes():
    """A highlight the wheel covers is a highlight nobody sees.

    The first V4 build gave it z-index 19 against a wheel at 20, so it was composed correctly,
    positioned correctly, and invisible -- the kind of defect that no assertion about state would
    have caught and that only showed up in a screenshot.

    It also must not go above the acolytes: it marks the space they are standing on, and a glow
    drawn over the figures would hide the thing it is pointing at.

    Falsified by moving the highlight to either side of that sandwich.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    css = tmpl[tmpl.index("<style>"):tmpl.index("</style>")]

    def z(pattern):
        m = re.search(pattern, css)
        assert m, "no z-index found for %s" % pattern
        return int(m.group(1))

    hl = z(r"\.hl\{[^}]*z-index:(\d+)")

    # The wheel and the acolytes take theirs from WHEEL_Z in the render, not from the stylesheet.
    render = tmpl[tmpl.index("function render()"):tmpl.index("function statusText()")]
    assert "wheelInner, WHEEL_Z)" in render, "the wheel no longer draws at WHEEL_Z"
    m = re.search(r"'<span class=anchor></span>', WHEEL_Z \+ (\d+)\)", render)
    assert m, "the acolyte layer no longer draws at a WHEEL_Z offset"
    figs_offset = int(m.group(1))
    base = re.search(r"var WHEEL_Z\s*=\s*(\d+)", tmpl)
    assert base, "WHEEL_Z is not defined in the page"
    wheel_z = int(base.group(1))

    assert hl > wheel_z, (
        "the highlight is at z %d and the wheel at %d, so the wheel covers it -- which is exactly "
        "how it shipped invisible the first time" % (hl, wheel_z))
    assert hl < wheel_z + figs_offset, (
        "the highlight is at z %d and the acolytes at %d, so the glow covers the figures it is "
        "meant to be pointing at" % (hl, wheel_z + figs_offset))

    # And it is drawn only in ACTION SELECTION, at the reached duty's own anchor.
    assert 'if (S.view === "action" && H.visible){' in render, (
        "the highlight is not restricted to ACTION SELECTION")
    assert 'rectOf("figs", reachedDuty())' in render, (
        "the highlight is not positioned from the reached duty's own anchor")



@needs_node
def test_each_view_state_contains_exactly_what_it_is_for():
    """Which objects belong to which state, asserted through the page's own table.

    The redesign is a claim about what is on screen when. V4 has three states and the wheel, the
    eight cards, the acolytes, the instruction and the City are in every one of them -- that is
    what makes the three comparable, and it is why the composition has so few moving parts.

    Only two things move. Tithe is ACTION-only, because it is the alternative to taking what a
    duty offers rather than something a duty offers. The artwork is the conditional one: it
    answers through shownDuty() rather than through a fixed list, so it is on screen whenever a
    duty is being shown -- always in ACTION, and before that only when somebody opened a card.

    statesOf() is the single table the render, the ghosting and Clean Preview all read, so
    testing it tests all three at once -- which is why it exists as a table rather than as three
    conditions in three places.

    Falsified by moving any object to another state, or by making the artwork unconditional.
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
const kinds = ["wheel","status","card","figs","art","tithe","city"];

const activeIn = (v) => { S.view = v; return kinds.filter(activeHere); };
S.previewDuty = null;
out.ready  = activeIn("ready");
out.sow    = activeIn("sow");
out.action = activeIn("action");

// The same three states again, with a card open.
S.previewDuty = "produce";
out.readyPreview = activeIn("ready");
out.sowPreview   = activeIn("sow");
S.previewDuty = null;

out.artStates   = { closed: (S.view = "ready", statesOf("art")) };
S.previewDuty = "produce";
out.artStates.open = statesOf("art");
S.previewDuty = null;
out.titheStates = statesOf("tithe");
out.cardStates  = statesOf("card");
out.wheelStates = statesOf("wheel");

out.attachable = kinds.filter(attachable);
out.shown = {};
S.view = "ready";  S.previewDuty = null;      out.shown.readyClosed = shownDuty();
S.view = "ready";  S.previewDuty = "produce"; out.shown.readyOpen = shownDuty();
S.view = "action"; S.previewDuty = "produce"; out.shown.action = shownDuty();
out.previewing = {};
S.view = "ready";  S.previewDuty = "produce"; out.previewing.ready = previewing();
S.view = "action";                            out.previewing.action = previewing();
// A preview pointed at a duty that does not exist is not a preview.
S.view = "ready"; S.previewDuty = "nonesuch"; out.shown.bogus = shownDuty();
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)

    always = {"wheel", "status", "card", "figs", "city"}
    for state in ("ready", "sow", "action"):
        assert always <= set(got[state]), (
            "something permanent is missing from %s: %s" % (state.upper(), got[state]))

    assert "tithe" not in got["ready"] and "tithe" not in got["sow"], (
        "Tithe is on screen before anything has been reached")
    assert "tithe" in got["action"], "Tithe is missing from ACTION SELECTION"
    assert got["titheStates"] == ["action"], got["titheStates"]

    assert "art" not in got["ready"] and "art" not in got["sow"], (
        "scenic artwork is on screen before anybody asked for a duty: %s / %s"
        % (got["ready"], got["sow"]))
    assert "art" in got["action"], "ACTION SELECTION has no artwork to select between"
    assert "art" in got["readyPreview"] and "art" in got["sowPreview"], (
        "opening a card does not bring its artwork on screen: %s / %s"
        % (got["readyPreview"], got["sowPreview"]))
    assert "tithe" not in got["readyPreview"] and "tithe" not in got["sowPreview"], (
        "Tithe appears in a preview. Reading about a duty is not being offered the alternative "
        "to one: %s / %s" % (got["readyPreview"], got["sowPreview"]))

    assert got["artStates"]["closed"] == [], got["artStates"]
    assert set(got["artStates"]["open"]) == {"ready", "sow", "action"}, got["artStates"]
    assert set(got["cardStates"]) == {"ready", "sow", "action"}, (
        "the reference cards are not in every state: %s" % got["cardStates"])
    assert set(got["wheelStates"]) == {"ready", "sow", "action"}

    assert got["shown"]["readyClosed"] is None
    assert got["shown"]["readyOpen"] == "produce"
    assert got["shown"]["action"] == "clerical", (
        "ACTION SELECTION showed the previewed duty rather than the one the sow reached: %r"
        % got["shown"]["action"])
    assert got["shown"]["bogus"] is None, (
        "a preview pointing at a duty that does not exist was treated as a preview")
    assert got["previewing"]["ready"] is True and got["previewing"]["action"] is False, (
        "a choice and a preview are not told apart: %s" % got["previewing"])

    # AND ONLY THE ANCHORS RIDE THE WHEEL. V3.1 had four kinds on this list; V4 has one, because
    # the labels and both medallions left. The artwork must never be on it -- it stands in the
    # band above the wheel and binding it to the wheel would move it every time the wheel is.
    assert set(got["attachable"]) == {"figs"}, (
        "the set of wheel-relative objects changed: %s" % got["attachable"])



@needs_node
def test_the_two_slots_show_whichever_duty_is_being_shown():
    """The other half of the asset/geometry split: the slots resolve, they do not store.

    An artwork slot holds a box and the name of an action SLOT ("actionA"), not a picture. What
    it draws is looked up from whichever duty is being shown at the time. That is what makes two
    boxes enough for sixteen pictures, and it means showing a different duty is a read, not a
    copy -- nothing is written into the slot and nothing about the previous duty is disturbed.

    V4 changes only where the question comes from. In ACTION SELECTION it is the duty the sow
    reached; before that it is whichever card was opened, or nothing at all.

    Falsified by copying the asset into the slot: the second duty's picture then appears under
    the first duty's name, or the first duty's asset is found to have moved.
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));
IMAGES.k_piety = "data:image/png;base64,PIETY";
IMAGES.k_coins = "data:image/png;base64,COINS";
IMAGES.k_wheat = "data:image/png;base64,WHEAT";
S.duties.clerical.actionA.scenic = "k_piety";
S.duties.clerical.actionB.scenic = "k_coins";
S.duties.produce.actionA.scenic = "k_wheat";

const read = () => ({
  duty: shownDuty(),
  leftLabel: artLabel("left"), rightLabel: artLabel("right"),
  leftAsset: (actionOf(shownDuty(), artOf("left").slot) || {}).scenic || null,
  rightAsset: (actionOf(shownDuty(), artOf("right").slot) || {}).scenic || null,
  leftBox: JSON.stringify([artOf("left").x, artOf("left").y,
                           artOf("left").width, artOf("left").height]),
});
S.view = "ready";
S.previewDuty = "clerical"; out.clerical = read();
S.previewDuty = "produce";  out.produce = read();
S.previewDuty = "taxation"; out.taxation = read();
S.previewDuty = "clerical"; out.backAgain = read();
S.previewDuty = null;       out.closed = read();

// In ACTION the question is answered by the sow, not by a click.
S.view = "action"; S.selectedDuty = "produce"; S.previewDuty = "clerical";
out.reached = read();

// The slots hold no picture of their own, before or after.
out.slotKeys = Object.keys(artOf("left")).sort();
// And swapping which action a slot shows is a change to the slot, not to any duty.
S.view = "ready"; S.previewDuty = "clerical";
artOf("left").slot = "actionB";
out.swapped = {label: artLabel("left"),
               asset: (actionOf("clerical", artOf("left").slot) || {}).scenic || null,
               dutyUntouched: S.duties.clerical.actionA.scenic};
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)

    assert got["clerical"]["leftAsset"] == "k_piety", got["clerical"]
    assert got["clerical"]["rightAsset"] == "k_coins", got["clerical"]
    assert got["clerical"]["leftLabel"] == "Gain X piety", got["clerical"]

    assert got["produce"]["leftAsset"] == "k_wheat", (
        "opening Produce did not change what the left slot resolves to: %s" % got["produce"])
    assert got["produce"]["leftLabel"] == "Gain X wheat", got["produce"]

    # A duty with no artwork loaded resolves to nothing rather than to the last one's picture.
    assert got["taxation"]["leftAsset"] is None, (
        "opening a duty with no artwork left the previous duty's picture in the slot: %s"
        % got["taxation"])
    # Taxation has real wording now, and only ONE action -- so the left box carries its caption
    # and the right box is not drawn at all. `rightLabel` here is whatever artLabel() would say
    # if it were asked, which is why it is not what this checks; the drawn-or-not claim belongs
    # with the acceptance suite that can see the DOM.
    assert got["taxation"]["leftLabel"] == "Gain X resources", got["taxation"]

    assert got["backAgain"] == got["clerical"], (
        "coming back to Clerical did not restore what it showed: %s vs %s"
        % (got["backAgain"], got["clerical"]))

    # Closed, the slots resolve to nothing at all rather than to the last duty opened.
    assert got["closed"]["duty"] is None and got["closed"]["leftAsset"] is None, got["closed"]
    assert got["closed"]["leftLabel"] == "", (
        "a closed slot still carries the last duty's caption: %r" % got["closed"]["leftLabel"])

    assert got["reached"]["duty"] == "produce" and got["reached"]["leftAsset"] == "k_wheat", (
        "ACTION SELECTION resolved to the previewed duty rather than the reached one: %s"
        % got["reached"])

    # The box never moved while the content changed six times.
    boxes = {got[k]["leftBox"]
             for k in ("clerical", "produce", "taxation", "backAgain", "closed", "reached")}
    assert len(boxes) == 1, "the slot's geometry changed with the duty it shows: %s" % boxes

    assert "scenic" not in got["slotKeys"] and "image" not in got["slotKeys"], (
        "an artwork slot stores a picture of its own: %s" % got["slotKeys"])
    assert got["swapped"]["label"] == "Gain X silver", got["swapped"]
    assert got["swapped"]["dutyUntouched"] == "k_piety", (
        "swapping which action the slot shows wrote through to the duty: %s" % got["swapped"])



@needs_node
@needs_node
def test_a_session_saved_before_the_wording_changed_takes_the_new_wording(lab):
    """The symptom this exists to prevent: the generator is re-run, duty_text.json has been
    edited, and the lab still shows the old words.

    The lab keeps the whole state in localStorage and merges it over the defaults, so the saved
    copy wins -- for ever, silently, and looking exactly like the build not having happened. The
    stamped wording fingerprint is what makes the two cases separable: a session saved against
    different words gives them up, one saved against these keeps whatever was typed into the
    ACTION panel.

    Falsified by dropping the fingerprint check, which would discard typed wording on every
    load, or by removing the refresh, which brings the original bug back.
    """
    body = """
const out = {};
// A session from an earlier build: old wording, no fingerprint, and some real work of its own.
const old = JSON.parse(JSON.stringify(DEFAULT_STATE));
old.duties.clerical.actionA.name = "Gain Piety";
old.duties.clerical.actionA.shortLabel = "Gain Piety";
old.duties.taxation.actionA.shortLabel = "Action A";
delete old.duties.taxation.actions;
delete old.textVersion;
old.wheel.width = 1000;
applyState(old);
out.stale = [S.duties.clerical.actionA.name, S.duties.clerical.actionA.shortLabel,
             S.duties.taxation.actionA.shortLabel, S.duties.taxation.actions];
out.staleKeptWork = S.wheel.width;

// A session saved against THIS wording, carrying something somebody typed.
const mine = JSON.parse(JSON.stringify(DEFAULT_STATE));
mine.textVersion = TEXT_VERSION;
mine.duties.clerical.actionA.shortLabel = "My own wording";
applyState(mine);
out.typed = S.duties.clerical.actionA.shortLabel;
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)
    d = lab.default_state()
    want = [d["duties"]["clerical"]["actionA"]["name"],
            d["duties"]["clerical"]["actionA"]["shortLabel"],
            d["duties"]["taxation"]["actionA"]["shortLabel"],
            d["duties"]["taxation"]["actions"]]
    assert got["stale"] == want, (
        "a session saved before the wording changed kept the old words: %s" % (got["stale"],))
    assert got["staleKeptWork"] == 1000, (
        "refreshing the wording threw away the rest of the session")
    assert got["typed"] == "My own wording", (
        "wording typed into the panel was discarded; the fingerprint matched, so it is work")


def test_an_older_layout_keeps_its_work_and_loses_only_its_coordinates():
    """What V4 carries across the boundary, and the one thing it deliberately does not.

    V3 widened the module and shifted a V2 file's coordinates sideways to keep the composition
    centred, which was right then: the bands had not moved, only the frame around them.

    V4 moved every band. The summary columns became a ribbon, the artwork left the margins, the
    medallions left the wheel's centre and the wheel itself went from 950 px to 1372. A position
    in that layout is a position in a layout that no longer exists, so shifting it would place
    eight cards precisely where the old columns were -- off the ribbon and over the wheel. The
    coordinates are therefore dropped and the defaults supplied.

    Everything that is not a coordinate is kept, because that is the part somebody spent time on:
    the wording, the assets, the counts, the seats, the player colours, the guides and the
    acolyte settings.

    Falsified by carrying the old geometry across, or by resetting the wording with it.
    """
    body = """
const out = {};
const v3 = JSON.parse(JSON.stringify(DEFAULT_STATE));
v3.version = 3;
v3.canvas = {width: 1400, height: 1200};
// A V3 file, as V3 actually shaped it.
v3.wheel = {x: 225, y: 355, width: 950, height: 503, opacity: 1, locked: false,
            image: null, imageName: null, naturalRatio: 0.5299};
v3.status = {x: 20, y: 24, width: 1360, height: 96, size: 34, align: "center", opacity: 1,
             context: "SOW", preset: "sow", contextVisible: true, contextSize: 18,
             byView: {sow:    {context: "SOW",      main: "MY OWN SOW LINE"},
                      action: {context: "CLERICAL", main: "MY OWN ACTION LINE"}},
             locked: false, visible: true};
v3.tithe = {x: 600, y: 900, width: 200, height: 200, u: 0.39, v: 0.5, attached: true,
            uvAnchor: "centre", label: "TITHE", resourceText: "W / S / Ag", visible: true,
            locked: false, image: null, imageName: null,
            resources: [{key: "W", name: "Wheat"}]};
v3.city = {x: 470, y: 1010, width: 460, height: 170, locked: false, visible: true,
           label: {x: 1, y: 2, width: 3, visible: true}, fit: "cover", opacity: 0.8,
           image: null, imageName: null,
           counts: {p1: 9, p2: 8, p3: 7, p4: 6}, shown: {p1: true, p2: true, p3: true, p4: false}};
v3.inHand = {x: 525, y: 465, width: 150, height: 150, u: 0.5, v: 0.5, uvAnchor: "centre",
             attached: true, count: 2, seat: "p3", label: "IN HAND", visible: true};
v3.summaryDim = "30"; v3.connectors = true; v3.titheInSummary = false; v3.inHandOverride = true;
v3.display = {expandedLeft: {x: 20, y: 345, width: 190, height: 420, slot: "actionA"},
              expandedRight: {x: 1190, y: 345, width: 190, height: 420, slot: "actionB"}};
v3.acolytes.height = 171;
v3.guides.warnings = false;
v3.players[0].colour = "#ff00ff"; v3.players[0].label = "Aelfric";
Object.keys(v3.duties).forEach(function(s){
  const D = v3.duties[s];
  D.summary = {x: 20, y: 120, width: 190, height: 110, visible: true, locked: false};
  D.label = {x: 5, y: 6, width: 110, visible: false, u: 0.1, v: 0.2, attached: true};
  D.titheLabel = "tithe";
  D.figures.u = 0.5; D.figures.v = 0.1;
  D.figures.x = 700; D.figures.y = 412;
});
v3.duties.clerical.actionA.name = "MY OWN WORDING";
v3.duties.clerical.actionA.scenicName = "clerical_piety.png";
v3.duties.taxation.figures.count = 4;
v3.duties.taxation.figures.seats = ["p4","p4","p4","p4"];

applyState(v3);
const fresh = JSON.parse(JSON.stringify(DEFAULT_STATE));
out.version = S.version;
out.wheel = [S.wheel.x, S.wheel.y, S.wheel.width, S.wheel.height];
out.freshWheel = [fresh.wheel.x, fresh.wheel.y, fresh.wheel.width, fresh.wheel.height];
out.card = [S.duties.clerical.card.x, S.duties.clerical.card.y,
            S.duties.clerical.card.width, S.duties.clerical.card.height];
out.freshCard = [fresh.duties.clerical.card.x, fresh.duties.clerical.card.y,
                 fresh.duties.clerical.card.width, fresh.duties.clerical.card.height];
out.band = [S.display.artLeft.x, S.display.artLeft.y, S.tithe.x, S.city.x, S.status.x, S.status.y];
out.freshBand = [fresh.display.artLeft.x, fresh.display.artLeft.y, fresh.tithe.x, fresh.city.x,
                 fresh.status.x, fresh.status.y];
out.anchor = [S.duties.clerical.figures.x, S.duties.clerical.figures.y];
out.freshAnchor = [fresh.duties.clerical.figures.x, fresh.duties.clerical.figures.y];
out.dutyKeys = Object.keys(S.duties.clerical).sort();
out.displayKeys = Object.keys(S.display).sort();
out.inHandKeys = Object.keys(S.inHand).sort();
out.statusKeys = Object.keys(S.status).sort();
out.retired = ["summaryDim","connectors","titheInSummary","inHandOverride"].filter(k => k in S);
out.titheRetired = ["u","v","attached","uvAnchor","resourceText"].filter(k => k in S.tithe);
// ---- and what must survive
out.wording = S.duties.clerical.actionA.name;
out.assetName = S.duties.clerical.actionA.scenicName;
out.statusSow = (S.status.byView.sow || {}).main;
out.statusAction = (S.status.byView.action || {}).main;
out.statusReady = (S.status.byView.ready || {}).main;
out.counts = S.city.counts;
out.shown = S.city.shown;
out.seats = S.duties.taxation.figures.seats;
out.count = S.duties.taxation.figures.count;
out.colour = S.players[0].colour;
out.label = S.players[0].label;
out.acoHeight = S.acolytes.height;
out.warnings = S.guides.warnings;
out.inHandCount = S.inHand.count;
out.inHandSeat = S.inHand.seat;
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)

    # ---- the coordinates are this build's, not the file's
    assert got["version"] == 4
    assert got["wheel"] == got["freshWheel"], (
        "the V3 wheel came through: %s rather than %s" % (got["wheel"], got["freshWheel"]))
    assert got["card"] == got["freshCard"], (
        "the summary's old box became the card's: %s rather than %s"
        % (got["card"], got["freshCard"]))
    assert got["band"] == got["freshBand"], (
        "a V3 band position survived: %s rather than %s" % (got["band"], got["freshBand"]))
    assert got["anchor"] == got["freshAnchor"], (
        "the acolyte ring kept its 950px-wheel coordinates: %s" % (got["anchor"],))

    # ---- and the shape is V4's
    assert got["dutyKeys"] == ["actionA", "actionB", "actions", "card", "clock",
                               "figures", "name"], (
        "the migrated duty is not a V4 duty: %s" % got["dutyKeys"])
    assert got["displayKeys"] == ["artLeft", "artRight", "effectUpper", "highlight"], got["displayKeys"]
    assert got["inHandKeys"] == ["count", "label", "seat"], got["inHandKeys"]
    assert got["retired"] == [], "retired V3 switches survived: %s" % got["retired"]
    assert got["titheRetired"] == [], (
        "Tithe kept the fields it had while it lived on the wheel: %s" % got["titheRetired"])
    for dead in ("context", "preset", "contextVisible", "contextSize"):
        assert dead not in got["statusKeys"], (
            "the status band kept its V3 %r field" % dead)

    # ---- the work survives
    assert got["wording"] == "MY OWN WORDING", (
        "the migration reset wording somebody typed: %r" % got["wording"])
    assert got["assetName"] == "clerical_piety.png", "a lost asset can no longer name its file"
    assert got["statusSow"] == "MY OWN SOW LINE", got["statusSow"]
    assert got["statusAction"] == "MY OWN ACTION LINE", got["statusAction"]
    assert got["statusReady"], (
        "the state V4 added came through with no message at all: %r" % got["statusReady"])
    assert got["counts"] == {"p1": 9, "p2": 8, "p3": 7, "p4": 6}, got["counts"]
    assert got["shown"]["p4"] is False, "a hidden seat came back visible"
    assert got["seats"] == ["p4", "p4", "p4", "p4"] and got["count"] == 4, (
        "who is standing on Taxation was lost: %s x%s" % (got["seats"], got["count"]))
    assert got["colour"] == "#ff00ff" and got["label"] == "Aelfric", "a player's identity was lost"
    assert got["acoHeight"] == 171, "the acolyte height was reset"
    assert got["warnings"] is False, "a guide setting was reset"
    assert got["inHandCount"] == 2 and got["inHandSeat"] == "p3", (
        "the in-hand pool lost its count or its seat when it lost its box")



def test_the_status_band_has_one_message_per_view_state(lab):
    """One line, three states, and no second line saying what the screen already says.

    V3 carried a context field above the message -- a small "SOW" or "CLERICAL" strap. V3.1 kept
    it; V4 removes it, because the instruction is already unambiguous and the strap was a second
    place where the same fact could be stated and go stale.

    What is left is one message per state, stored per state rather than rewritten on the way in,
    so composing the wording for one does not touch the other two.

    Falsified by collapsing byView to a single string, or by putting the context line back.
    """
    d = lab.default_state()
    t = d["status"]

    keys = [v[0] for v in lab.VIEW_STATES]
    assert keys == ["ready", "sow", "action"], keys
    assert sorted(t["byView"]) == sorted(keys), (
        "the status band does not have one entry per view state: %s" % sorted(t["byView"]))
    for k in keys:
        assert set(t["byView"][k]) == {"main"}, (
            "%s's message carries %s -- V4 stores one line and nothing else"
            % (k, sorted(t["byView"][k])))
        assert t["byView"][k]["main"].strip(), "%s opens with an empty instruction" % k
    mains = [t["byView"][k]["main"] for k in keys]
    assert len(set(mains)) == 3, "two states share an instruction: %s" % mains

    for dead in ("context", "preset", "contextVisible", "contextSize", "mainSize", "autoContext",
                 "accent", "accentColour", "main"):
        assert dead not in t, "the status band kept its V3 %r field" % dead

    # The sow line counts down, and it does so through a token rather than through typed digits,
    # so the instruction and the figure in the City's region cannot disagree.
    assert "{n}" in t["byView"]["sow"]["main"], (
        "the sow instruction does not carry {n}: %r" % t["byView"]["sow"]["main"])
    assert "{n}" not in t["byView"]["ready"]["main"]
    assert "{n}" not in t["byView"]["action"]["main"]



def test_the_instruction_is_the_top_line_and_nothing_scenic_is_above_the_wheel(lab):
    """The vertical order of the module, which is the composition's whole argument.

    Read down: what to do, the eight duties, what this duty offers, the board. Nothing scenic may
    appear above the instruction and nothing at all below the wheel -- the wheel's bottom edge is
    the module's bottom edge, which is what makes it a board rather than a panel.

    Falsified by moving the instruction under the ribbon, or by putting anything below the wheel.
    """
    d = lab.default_state()
    t, w = d["status"], d["wheel"]

    ribbon_top = min(D["card"]["y"] for D in d["duties"].values())
    band_top = d["display"]["artLeft"]["y"]

    assert t["y"] + t["height"] <= ribbon_top, "the instruction overlaps the ribbon"
    assert ribbon_top < band_top < w["y"], (
        "the bands are not in order: ribbon %d, action band %d, wheel %d"
        % (ribbon_top, band_top, w["y"]))
    assert t["y"] >= 0 and t["x"] >= 0

    # Nothing else is above the instruction.
    boxes = {"artLeft": d["display"]["artLeft"], "artRight": d["display"]["artRight"],
             "tithe": d["tithe"], "city": d["city"]}
    boxes.update({"%s card" % s: D["card"] for s, D in d["duties"].items()})
    for name, o in boxes.items():
        assert o["y"] >= t["y"], "%s opens above the instruction" % name

    # AND NOTHING BELOW THE WHEEL. V3 had the City down there; V4 brought it up into the band, so
    # the wheel runs to the bottom of the module with nothing under it.
    bottom = w["y"] + w["height"]
    for name, o in boxes.items():
        assert o["y"] < bottom, "%s opens below the wheel" % name
    assert bottom <= lab.CANVAS_H
    assert lab.CANVAS_H - bottom < 60, (
        "%d px of empty module below the wheel -- V4 puts nothing there, so it is width the "
        "wheel should have had" % (lab.CANVAS_H - bottom))



@needs_node
def test_each_view_state_keeps_its_own_status_message():
    """Reading, writing and resetting the instruction, which is where V3.1's bug lived.

    The V3.1 bug was a read: the panel drew from the wrong local, so both text fields came up
    empty and editing either wrote the other. V4 makes the class of mistake unavailable by
    looping over VIEW_STATES rather than naming each state's field, but the behaviour is still
    worth pinning from the outside -- what matters is that three messages stay three messages
    through a read, a write, an undo and a reset.

    Falsified by sharing one string between the states, or by a reset that keeps dead keys.
    """
    body = """
const out = {};
S = JSON.parse(JSON.stringify(DEFAULT_STATE));

out.opening = {};
["ready","sow","action"].forEach(v => { S.view = v; out.opening[v] = statusText(); });

// {n} is substituted from the pool, not typed.
S.view = "sow"; S.inHand.count = 7; out.counted = statusText();
S.inHand.count = 0; out.countedZero = statusText();
S.inHand.count = 4;

// Writing one state's message leaves the others alone.
S.status.byView.action.main = "ONLY THE ACTION LINE";
out.afterWrite = {};
["ready","sow","action"].forEach(v => { S.view = v; out.afterWrite[v] = statusText(); });

// A reset puts the BOX back and keeps the WORDS, and leaves nothing dead behind.
S.status.x = 4; S.status.y = 5; S.status.size = 71; S.status.align = "left";
resetOne("status", null);
out.afterReset = {};
["ready","sow","action"].forEach(v => { S.view = v; out.afterReset[v] = statusText(); });
out.resetBox = [S.status.x, S.status.y, S.status.size, S.status.align];
out.defaultBox = [DEFAULT_STATE.status.x, DEFAULT_STATE.status.y,
                  DEFAULT_STATE.status.size, DEFAULT_STATE.status.align];
out.resetKeys = Object.keys(S.status).sort();
out.resetByView = Object.keys(S.status.byView).sort();
out.resetEntryKeys = Object.keys(S.status.byView.sow).sort();

// A state the file has never heard of reads as empty rather than throwing.
S.view = "nonesuch"; out.unknown = statusText();
process.stdout.write(JSON.stringify(out));
"""
    got = _in_node(body)

    assert len(set(got["opening"].values())) == 3, (
        "the three states do not open with three different instructions: %s" % got["opening"])
    for v, text in got["opening"].items():
        assert text.strip(), "%s opens with an empty instruction" % v
        assert "{n}" not in text, "%s shows the token rather than the count: %r" % (v, text)

    assert " 7 " in got["counted"], "the sow line did not count 7: %r" % got["counted"]
    assert " 0 " in got["countedZero"], (
        "the sow line does not count down to nothing: %r" % got["countedZero"])

    assert got["afterWrite"]["action"] == "ONLY THE ACTION LINE"
    assert got["afterWrite"]["sow"] == got["opening"]["sow"], (
        "writing the action line changed the sow line: %r" % got["afterWrite"]["sow"])
    assert got["afterWrite"]["ready"] == got["opening"]["ready"], (
        "writing the action line changed the ready line: %r" % got["afterWrite"]["ready"])

    # A RESET IS ABOUT THE BOX, NOT THE WORDS -- the same rule Tithe's label and the City's
    # counts follow. Retyping three instructions is not what anyone means by putting a band back
    # where it started, so the wording survives and the geometry snaps back.
    assert got["resetBox"] == got["defaultBox"], (
        "a reset did not put the band back where it started: %s vs %s"
        % (got["resetBox"], got["defaultBox"]))
    assert got["afterReset"]["action"] == "ONLY THE ACTION LINE", (
        "a reset retyped an instruction somebody had written: %r"
        % got["afterReset"]["action"])
    assert got["afterReset"]["sow"] == got["opening"]["sow"], got["afterReset"]
    assert got["afterReset"]["ready"] == got["opening"]["ready"], got["afterReset"]
    assert got["resetByView"] == ["action", "ready", "sow"], got["resetByView"]
    assert got["resetEntryKeys"] == ["main"], (
        "the reset left dead keys on a message: %s" % got["resetEntryKeys"])
    for dead in ("context", "preset", "contextVisible", "contextSize", "main"):
        assert dead not in got["resetKeys"], (
            "the reset put back the retired %r field" % dead)

    assert got["unknown"] == "", (
        "an unknown view state produced %r rather than nothing" % got["unknown"])



def _strip_js_comments(src):
    """Drop // and /* */ comments, leaving string literals alone.

    Deliberately small and deliberately not a JavaScript parser. It tracks quotes so that a `//`
    inside a string -- a URL, say -- is not mistaken for the start of a comment, and it tracks
    nothing else, because the only thing asking is a name search.
    """
    out = []
    i, n = 0, len(src)
    quote = None
    while i < n:
        c = src[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'`":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def test_the_comment_stripper_leaves_code_and_strings_alone():
    """Because the guard above is only as good as this, and it is easy to get subtly wrong."""
    assert _strip_js_comments("var a = 1; // titheLabel\nvar b = 2;") == "var a = 1; \nvar b = 2;"
    assert _strip_js_comments("/* titheLabel */ var a = 1;") == " var a = 1;"
    # A RETIRED NAME INSIDE A STRING IS STILL A READ as far as this guard is concerned -- it is
    # how bracket access is written -- so the stripper must not swallow string literals.
    assert "titheLabel" in _strip_js_comments('var a = d["titheLabel"];')
    # A // inside a string is not a comment.
    assert _strip_js_comments('var u = "http://x/y"; var b = 2;') == 'var u = "http://x/y"; var b = 2;'
    assert _strip_js_comments("var s = 'a // b'; // gone") == "var s = 'a // b'; "


def test_no_live_code_reaches_for_the_retired_status_fields(lab):
    """The fields V4 retired, checked for by name, because a stale read is silent.

    V3's status band had a context strap and a preset; V3's duties had a label and a summary; the
    wheel's centre had two medallions. All of them are gone. A line that still reads one of those
    names does not fail -- it reads undefined and renders nothing -- so the only way to notice is
    to look for the names.

    THE MIGRATION IS EXEMPT AND MUST BE. It is the one place that legitimately knows the old
    shape: it reads V3's byView entries to keep somebody's wording, and deletes the rest by name.
    Excluding it by slicing the file at migrate() would also excuse anything defined after it, so
    the exemption is per-function instead.

    COMMENTS ARE NOT CODE, and this used to scan them. It went red on a comment that merely
    NAMED a retired field while explaining why a new helper was called something else -- a false
    positive that pushes the next person towards a worse name or towards deleting the guard. A
    check for stale READS has no business reading prose, so the comments come out first. This
    does not weaken it: the falsification below puts a real read back and it still fails.

    Falsified by leaving a live read of any retired name outside the migration.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    start = tmpl.index("function migrate(")
    end = tmpl.index("function deepMerge(")
    live = _strip_js_comments(tmpl[:start] + tmpl[end:])

    retired = ["status.context", "status.preset", "contextVisible", "contextSize",
               "autoContext", "accentColour", "summaryDim", "titheInSummary", "inHandOverride",
               "expandedLeft", "expandedRight", "uvAnchor", "titheLabel", ".summary",
               "connectors"]
    for name in retired:
        assert name not in live, (
            "live code still reads %r, which V4 retired. It will read undefined and draw nothing "
            "rather than failing" % name)

    # The migration, on the other hand, MUST still know them -- otherwise an older file loses
    # what somebody typed instead of having it carried across.
    migration = tmpl[start:end]
    for name in ("byView", "summary", "label", "titheLabel", "uvAnchor", "summaryDim",
                 "expandedLeft"):
        assert name in migration, (
            "the migration no longer mentions %r, so an older file would silently lose it" % name)

    # And the generator has stopped producing them.
    d = lab.default_state()
    assert "context" not in d["status"] and "preset" not in d["status"]
    assert "summaryDim" not in d and "connectors" not in d and "inHandOverride" not in d
    for D in d["duties"].values():
        assert "label" not in D and "summary" not in D and "titheLabel" not in D



def test_the_artwork_slots_are_the_size_a_scenic_illustration_wants(lab):
    """V3.1 made the side slots taller; V4 made them landscape, because they moved.

    In the margins a slot was a tall column 190 px wide, and the refinement was to grow its
    height. In the band above the wheel there is width and there is not much height, so the same
    object is now a wide, shallow panel -- which is the shape a scenic illustration of a place
    actually wants, and the reason the artwork moved out of the margins at all.

    Falsified by giving a slot a portrait aspect again, or by letting the pair outgrow the band.
    """
    d = lab.default_state()
    L, R = d["display"]["artLeft"], d["display"]["artRight"]
    for name, e in (("artLeft", L), ("artRight", R)):
        assert e["width"] > e["height"], (
            "%s is %dx%d, which is a column. The band is wide and shallow"
            % (name, e["width"], e["height"]))
        assert 1.6 <= e["width"] / e["height"] <= 2.6, (
            "%s is %.2f:1; a scenic panel wants roughly 2:1" % (name, e["width"] / e["height"]))
        assert e["width"] >= 300, "%s is only %d px wide" % (name, e["width"])

    # The two together take rather more of the band than Tithe and the City, because choosing
    # between them is the decision the state exists for.
    art = L["width"] + R["width"]
    rest = d["tithe"]["width"] + d["city"]["width"]
    assert art > rest, (
        "the two artworks take %d px and Tithe plus the City take %d -- the choice is not the "
        "largest thing in the band" % (art, rest))
    assert art + rest <= lab.BAND["width"] + 40, "the band's contents do not fit the band"



def test_clean_preview_tells_a_preview_apart_from_a_choice():
    """What Clean Preview has to make visually different, now that the cards never dim.

    V3.1's refinement was about dimming: the compact summaries were a card treatment that had to
    lighten in Clean Preview so the state read honestly. V4's cards are reference furniture in
    every state, so there is no dim to get right.

    What replaced it is a harder distinction. The same two artwork boxes are used for reading
    about a duty and for choosing one of its actions, and those must not look alike -- so a
    preview is badged and a choice is not, and the choice treatment is a class the preview does
    not get.

    Falsified by dropping the badge, or by giving a preview the choice treatment.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    art = tmpl[tmpl.index("---- 4. the two scenic artworks"):tmpl.index("---- 5. Tithe")]

    assert 'isPreview ? "" : " choice"' in art, (
        "the choice treatment is not withheld from a preview, so reading about a duty looks like "
        "taking it")
    assert 'pv.textContent = "PREVIEW"' in art, "the PREVIEW badge is gone"
    assert "if (isPreview){" in art, "the badge is not conditional on previewing"

    # Both the badge and the treatment answer the same function, so they cannot disagree.
    assert "previewing()" in tmpl
    assert "var shown = shownDuty(), isPreview = previewing();" in art, (
        "the artwork block computes the two facts separately rather than reading them once")

    # The styles act on both classes, or the distinction is only in the DOM.
    css = tmpl[tmpl.index("<style>"):tmpl.index("</style>")]
    assert ".art.choice" in css, "Clean Preview has no rule for a choice, so it reads as a preview"
    assert ".pv{" in css or ".pv {" in css, "the badge has no styling"

    # And Clean Preview never shows editing chrome, which is the part V3.1 got right.
    assert 'if (activeHere(kind)) return "yes";' in tmpl
    assert 'return (editing && S.showGhosts) ? "ghost" : "no";' in tmpl, (
        "a ghost could survive into Clean Preview, which exists to show one state honestly")




def test_the_status_panel_offers_one_field_per_state_and_writes_only_that_one(lab):
    """The editing side of the instruction, which is where V3.1's bug actually was.

    V3.1 named two locals for the band and the message and read the wrong one, so both text
    fields came up blank and typing in either wrote the other. The fix then was to name them
    apart and pin the names. V4 does something better: the panel LOOPS over VIEW_STATES, so the
    field and the handler are generated from the same key and cannot disagree -- there is no
    second name to get wrong.

    So the guard moves from "these two locals are named apart" to "there is one field per state,
    each prefilled from its own entry, each writing only its own". That survives a fourth state
    being added, which the old one would not have.

    Falsified by hard-coding the states, or by writing through a captured key.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    panel = tmpl[tmpl.index('el("statusCtl").innerHTML') - 2500:
                 tmpl.index('el("stSize").oninput')]

    assert "VIEW_STATES.forEach" in panel, (
        "the status panel no longer generates its fields from VIEW_STATES. Hard-coding one field "
        "per state is what made V3.1 able to read the wrong one")
    assert 'data-st="' in panel, "the fields do not carry the state they belong to"
    assert "T.byView[vs.key]" in panel, (
        "a field is not prefilled from its own state's entry, which is the V3.1 bug exactly")
    assert "T.byView[inp.dataset.st]" in panel, (
        "the handler does not write through the field's own key, so typing in one state's box "
        "could land in another's")
    # The read and the write use the same key expression, which is the whole point.
    assert panel.count("byView") >= 3

    for dead in ("statusText()", ".context", ".preset"):
        assert dead not in panel, (
            "the status panel still mentions %s. The rendered line belongs to render(); the "
            "panel edits the stored text" % dead)

    # One field per state, whatever the states are.
    assert len(lab.VIEW_STATES) == 3
    d = lab.default_state()
    assert sorted(d["status"]["byView"]) == sorted(v[0] for v in lab.VIEW_STATES)




# =================================================================================================
# THE TWO CAPTIONS THAT ARE NOT ON ARTWORK.
#
# TAKE TITHE and THE CITY were the last text on the board whose size was fixed in the stylesheet.
# Making them adjustable is easy; making them adjustable WITHOUT MOVING ANYTHING is the part
# worth guarding, and that is what most of these are about.
# =================================================================================================

def test_the_caption_controls_open_at_the_size_the_stylesheet_already_drew(lab):
    """A new control must start where the design is, or shipping it silently restyles the board.

    The two numbers exist in two places -- the generator's default and the stylesheet's fallback
    -- and they have to agree. The fallback is not decoration: it is what a browser draws if the
    custom property is ever missing, so a fallback that disagreed with the default would make a
    failure mode look like a design.

    Falsified by changing either number on its own.
    """
    S = lab.default_state()
    assert S["tithe"]["labelSize"] == lab.TITHE_LABEL_SIZE == 17
    assert S["city"]["labelSize"] == lab.CITY_LABEL_SIZE == 13

    tmpl = TMPL.read_text(encoding="utf-8")
    tl = re.search(r"#titheObj \.tl\{[^}]*?font:600 var\(--cap,(\d+)px\)", tmpl, re.S)
    cl = re.search(r"#cityObj \.cl\{font:600 var\(--cap,(\d+)px\)", tmpl)
    assert tl and int(tl.group(1)) == S["tithe"]["labelSize"], (
        "the Tithe caption's CSS fallback is not the default size, so a page whose property "
        "never arrived would draw a different board rather than the same one")
    assert cl and int(cl.group(1)) == S["city"]["labelSize"], (
        "the City caption's CSS fallback is not the default size")


def test_the_two_captions_are_not_one_number(lab):
    """They label different kinds of thing and are deliberately different sizes.

    TAKE TITHE is a choice offered alongside the two actions and matches their caption; THE CITY
    heads a reserve nobody picks. A single shared constant would assert those are the same job.

    Falsified by collapsing them to one constant.
    """
    assert lab.TITHE_LABEL_SIZE != lab.CITY_LABEL_SIZE


def test_the_tithe_card_reserves_what_the_caption_measured_not_what_it_guessed(lab):
    """The reserve is derived, and derived from the RENDER rather than from the font size.

    A reserve computed as one line-height is wrong as soon as the caption wraps, which TAKE
    TITHE does at 34px in a 178px card -- the second line then sits on the tokens. So the height
    is read back off the drawn element. Three things have to stay true:

      * it is read AFTER the stage has the node, because everything is built into a fragment and
        a detached node measures 0 -- which is exactly the bug this went through;
      * it is read BEFORE paintMetrics(), because the overflow figure painted there is measured
        against the reserve;
      * the cached measurement is cleared when the card is not drawn, so a stale height from an
        earlier state cannot be quoted at you.

    Falsified by moving the call above the insertion, below paintMetrics(), or by dropping the
    reset.
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    insert = tmpl.index("st.appendChild(frag);")
    fit = tmpl.index("fitBandCaptions();", insert)
    metrics = tmpl.index("paintMetrics();", insert)
    assert insert < fit < metrics, (
        "fitBandCaptions() must run after the stage has the nodes and before the metrics that "
        "are measured against what it sets")
    body = tmpl[tmpl.index("function fitBandCaptions("):]
    body = body[:body.index("\n}\n") + 3]
    assert "offsetHeight" in body, "fitBandCaptions() no longer measures the caption"
    # THE OFFSET IS SET BEFORE THE HEIGHT IS READ. A caption moved after it was measured is a
    # caption whose reserve was worked out against where it used to be.
    assert body.index("tl.style.bottom") < body.index("offsetHeight"), (
        "the Tithe caption's height is read before it has been put on its line")
    # `card.style.paddingBottom`, not the first paddingBottom in the function -- that one is the
    # artwork's effect caption being dropped onto the bottom line, which is a different thing
    # and comes earlier.
    assert body.index("offsetHeight") < body.index("card.style.paddingBottom"), (
        "the reserve is set before the height it is supposed to reserve has been read")
    assert re.search(r"TITHE_CAP_H = null;\s*\n\s*if \(titheMode", tmpl), (
        "the measurement is no longer forgotten when the Tithe card is not drawn, so the "
        "overflow reading can quote a caption height from some earlier state")


def test_nothing_still_reserves_a_fixed_thirty_six(lab):
    """The old constant is gone, and the derived one agrees with it at the default.

    36px of bottom padding was right for exactly one caption size. The number surviving anywhere
    -- in the stylesheet, or as the old TITHE_CHROME -- would mean something is still sizing
    itself for a 17px caption while the control says otherwise.

    Falsified by leaving TITHE_CHROME in place, or by putting padding-bottom:36px back.
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    assert "TITHE_CHROME" not in tmpl, (
        "TITHE_CHROME is back, and it cannot know how tall the caption turned out to be")
    assert "titheChrome()" in tmpl
    # The derived figure at the default must be the number that was there before: 10px off the
    # bottom, a 17px caption at 1.2 line-heights, and 6px of air.
    derived = 10 + round(1.2 * lab.TITHE_LABEL_SIZE) + 6
    assert derived == 36, derived
    # THE STYLESHEET KEEPS ITS 36, and that is not a leftover -- it is the same bargain as the
    # `var(--cap,17px)` fallback beside it. render() overwrites it on every pass, so the CSS
    # value is only ever seen if the property never arrived, and it should then show the design
    # rather than some other number. What it must not do is disagree with the derived default.
    css = re.search(r"#titheObj\{[^}]*?padding-bottom:(\d+)px\}", tmpl, re.S)
    assert css, "the Tithe card no longer carries a bottom reserve in the stylesheet at all"
    assert int(css.group(1)) == derived, (
        "the stylesheet's fallback reserve is %s but the derived default is %d, so a page that "
        "never got the inline value would draw a card nobody designed"
        % (css.group(1), derived))


def test_one_size_covers_the_city_in_both_of_its_phases(lab):
    """The same line of the same box, saying what is in it -- so one control, not two.

    The region is THE CITY until sowing and ACOLYTES IN HAND during it. Both are drawn into the
    same `.cl` element and both read cityCapSize(). Two controls would let the box change its
    type size halfway through a turn for no reason a player could see.

    Falsified by giving either branch its own size.
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    branches = re.findall(r"body = '<div class=cl style=\"--cap:' \+ (\w+)\(\)", tmpl)
    assert len(branches) == 2, ("expected the City's two phases to be drawn by two branches, "
                                "found %d" % len(branches))
    assert branches[0] == branches[1] == "cityCapSize", branches


def test_every_caption_on_the_board_is_bounded_by_the_same_two_numbers(lab):
    """8 and 60, written once.

    There were four copies before the Tithe and the City wanted them too. Six copies that agree
    only by coincidence is how a bound drifts: somebody widens one and the inspector starts
    accepting a size that normalisation then silently takes back on the next load.

    Falsified by writing the bound out again anywhere.
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    assert tmpl.count("CAP_MIN = 8, CAP_MAX = 60") == 1
    assert "8, 60" not in tmpl, (
        "the caption bound is written out longhand somewhere as well as being named")
    # Every caption size goes through it -- the artwork's two and the two new ones.
    for fn in ("clampCap(v)", "clampCap(e.labelSize)", "clampCap(e.nameSize)",
               "clampCap(S.tithe.labelSize)", "clampCap(S.city.labelSize)"):
        assert fn in tmpl, "%s no longer shares the common bound" % fn


def test_a_caption_size_that_is_missing_and_one_that_is_absurd_are_different_problems(lab):
    """Absent goes to the default; out of range is pulled into range and kept.

    A session saved before these controls existed has no value and must open at the design. A
    session carrying 900 was composed by somebody who meant "as big as it goes", and opening it
    at 17 would throw away a decision rather than bound it.

    Falsified by writing either case as `+v || default`, which conflates them.
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    body = tmpl[tmpl.index("function capFor("):][:400]
    assert "undefined" in body and "null" in body and "isNaN" in body, (
        "capFor no longer distinguishes a missing value from an unreadable one")
    # The `||`s above are the guard, and are fine. What is banned is falling back THROUGH one --
    # `+v || dflt` quietly turns a legitimate 0 into the default, and 0 is how a hand-edited
    # file says "smallest". The bound takes it to 8; `||` would take it to 17.
    assert not re.search(r"\+?v\s*\|\|\s*\w*[Dd]flt", body), (
        "capFor falls back with `||`, which cannot tell a missing size from a zero one")
    assert body.index("isNaN") < body.index("?"), (
        "the unreadable case is no longer decided before the value is used")
    for key in ("S.tithe.labelSize = capFor(", "S.city.labelSize = capFor("):
        assert key in tmpl, "%s is not normalised on load" % key


# =================================================================================================
# ONE LINE ACROSS THE ACTION BAND.
#
# The four captions on the band print on two baselines: the artwork's action names and THE CITY
# along the top, the artwork's effect lines and TAKE TITHE along the bottom. What these guard is
# that it stays true at any combination of the four sizes -- it was true before only by accident,
# and the accident did not survive the first turn of a size control.
#
# WHETHER THE BASELINES ACTUALLY COINCIDE IS A QUESTION FOR A BROWSER, not for a source file, and
# tests/layout_lab/accept45.mjs is what asks it: it probes the rendered captions across a matrix
# of sizes and reports the worst spread on either line. These are the shape of the arithmetic
# that makes the answer come out, which is the part that can rot without anything looking wrong.
# =================================================================================================

def test_the_band_line_is_set_by_the_tallest_caption_on_it(lab):
    """Not by the artwork, and this is the whole design.

    Lining the other two up on the artwork was tried first and is impossible in general: a 26px
    City heading carries its baseline 24px below its own box top, a 17px artwork name carries
    its 15.8px below the same top, and no padding reconciles those without pushing a caption out
    of its card. Doing it anyway means a silent clamp -- which is what the first version did, and
    what it looked like was a control that stopped working past a certain number.

    So the tallest caption on each edge sets that edge's line and everything else is dropped onto
    it. At the default sizes the tallest IS the artwork, so the artwork does not move.

    Falsified by taking the max over anything narrower, or by measuring from the artwork alone.
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    for fn, edge in (("bandTopInset", "topCapSizes"), ("bandBottomInset", "bottomCapSizes")):
        body = tmpl[tmpl.index("function %s(" % fn):][:200]
        assert "maxOf(%s()" % edge in body, (
            "%s no longer takes the tallest caption on its edge, so a caption bigger than the "
            "artwork's is either clipped or silently left off the line" % fn)
        assert "CAP_PAD" in body, "%s no longer leaves the artwork's own padding" % fn


def test_both_artwork_slots_count_towards_the_line_even_when_one_is_hidden(lab):
    """A one-action duty hides the right slot, and the band must not jump when it does.

    Taxation and Allocation draw one artwork; the others draw two. If the hidden slot's size were
    dropped from the reckoning, stepping the wheel from Clerical to Taxation could move both
    baselines -- the whole band shifting as a side effect of which duty is reached.

    Falsified by filtering the sizes by artUsed().
    """
    tmpl = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    for fn in ("topCapSizes", "bottomCapSizes"):
        body = tmpl[tmpl.index("function %s(" % fn):][:280]
        assert '"left"' in body and '"right"' in body, (
            "%s no longer counts both artwork slots" % fn)
        assert "artUsed" not in body and "visible" not in body, (
            "%s skips a slot that is not on screen, so the band moves when a one-action duty "
            "is reached" % fn)
    assert "cityCapSize()" in tmpl[tmpl.index("function topCapSizes("):][:280]
    assert "titheCapSize()" in tmpl[tmpl.index("function bottomCapSizes("):][:280]


def test_the_baseline_is_measured_at_each_size_because_it_does_not_scale(lab):
    """A baseline is rounded to a whole pixel, so the fraction is not one number.

    Read off the same face at line-height 1.2 it comes out 0.875 at 8px, 0.882 at 17 and 0.930 at
    100. A single constant is around three pixels out at the top of the range, on the one thing
    this code exists to line up. So the probe is set to each size in use and read.

    The probe must also be REAL: off screen rather than display:none, which has no layout and
    nothing to measure, and set exactly as the captions are or it answers about another face.

    Falsified by caching one fraction and scaling it, or by hiding the probe properly.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    assert "#capProbe" in tmpl and 'id=capProbe' in tmpl
    css = re.search(r"#capProbe\{([^}]*)\}", tmpl).group(1)
    assert "display:none" not in css, (
        "the probe is display:none, which gives it no layout and no baseline to read")
    assert "visibility:hidden" in css and "left:-9999px" in css
    assert "/1.2 Georgia,serif" in css, "the probe is not set as the captions are"

    code = _strip_js_comments(tmpl)
    body = code[code.index("function capBase("):][:700]
    assert "CAP_BASE[F]" in body and "getBoundingClientRect" in body, (
        "capBase no longer measures, or no longer caches what it measured")
    assert "probe.style.fontSize" in body, (
        "capBase no longer asks about the size it was given, so it is back to one fraction "
        "scaled -- which is what the rounding makes wrong")
    # A cache that outlives a late-arriving font is a wrong number for the whole session.
    assert "CAP_BASE = {};" in code[code.index("document.fonts.ready"):][:200], (
        "the measurements are not dropped when fonts finish loading")


def test_a_caption_that_cannot_be_measured_falls_back_rather_than_collapsing(lab):
    """No probe, or a figure that cannot be a baseline, must not put a caption at zero.

    capBase returning 0 would drop every caption onto its box edge and, worse, would look
    deliberate. The guards are a missing probe and a reading outside the line box.

    Falsified by removing either fallback.
    """
    code = _strip_js_comments(TMPL.read_text(encoding="utf-8"))
    body = code[code.index("function capBase("):][:700]
    assert "if (!bl) return" in body, "a missing probe no longer has a fallback"
    assert re.search(r"if \(!\(v > 0 && v < F \* CAP_LH\)\)", body), (
        "a reading that cannot be a baseline is used anyway")


def test_the_stylesheet_fallbacks_are_what_the_derivation_gives_at_the_defaults(lab):
    """Every caption's position is overwritten each render, so the CSS is only ever seen if the
    inline value never arrived -- and it should then show the design rather than some other
    number.

    The Tithe caption's `bottom` and the City card's `padding-top` are the two that changed:
    5px and 8.53px, against the artwork's plain 6px, because those two cards carry a 1px border
    the artwork does not and the City's 13px type needs more room above it than the artwork's 17.

    Falsified by changing a default size without the fallback following.
    """
    tmpl = TMPL.read_text(encoding="utf-8")
    tl = re.search(r"#titheObj \.tl\{[^}]*?bottom:(\d+)px", tmpl, re.S)
    assert tl and int(tl.group(1)) == 6 - 1, (
        "at equal sizes the Tithe caption wants the artwork's 6px less its own 1px border")
    city = re.search(r"#cityObj\{[^}]*?padding-top:([\d.]+)px\}", tmpl, re.S)
    assert city, "the City card no longer carries a fallback padding-top"
    assert 7.5 < float(city.group(1)) < 9.5, city.group(1)
    # All four captions share one line-height, or there are two baseline fractions to keep right.
    for sel in (r"\.art \.cap\{", r"\.art \.anm\{", r"#titheObj \.tl\{", r"#cityObj \.cl\{"):
        block = re.search(sel + r"[^}]*\}", tmpl, re.S).group(0)
        assert "/1.2 Georgia,serif" in block, (
            "%s is not at the band's line-height any more" % sel)
