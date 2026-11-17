"""Guards for the nine rectangles on ui/board_v2/action_board's v2 board.

WHY THESE. The things this board can get wrong all fail the same way: a duty in the wrong
rectangle, a plate that is clipped or quietly refused, and a row of acolytes that draws nobody
are all states the page reaches without an exception, without a console line, and without looking
obviously broken.

THE BANNERS HAVE GONE OFF THIS BOARD and the rectangles carry no name at all. The art and the
face are still in the tree -- recorded, and guarded by test_action_board_v2_banners.py -- because
they may come back; nothing on the page reads them, and
`test_no_rectangle_carries_a_name_any_more` holds both halves of that.

WHAT IS COVERED ELSEWHERE AND IS NOT REPEATED HERE. geometry.py checks itself -- the canvas, the
card row, the Tithe's slack, the controls column -- and `tests/action_board/test_action_board.py`
holds the v1 board. v2 imports v1 for every piece of data bundling, so the art walk, the
attribution gate, the seals, the cues and the beds are all guarded over there and a v2-specific
copy would be a second statement of the same rule. What v2 forked is the TEMPLATE, and what it
invented inside the template is the grid. That is what this file covers.

THE ARITHMETIC IS RUN, NOT RESTATED. `gridArea`, `gridCells` and the per-cell plate block are
sliced out of the shipped template and evaluated in node -- the idiom
`tests/test_ui_debug_duty_board.py` already uses against that page's rules file. A Python
reimplementation to assert against was the alternative and it is the worse one twice over: it
would agree with the template on the day it was written and drift silently after, and it would
reproduce any error the template already has. Slicing means the test reads the real text, so a
refactor that moves the anchors fails loudly here rather than leaving a guard that passes against
nothing.

ONE NODE RUN FOR THE WHOLE SWEEP. The three sliders crossed with the two action counts is 250
arrangements and 2000 rectangles; a process per cell would be ten thousand of them. The `sweep`
fixture runs the lot in one `node -e` and every test below reads its output.

Each test names the failure it exists to catch and how to falsify it.
"""
import base64
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
TOOL = BOARD / "action_board"
TMPL = TOOL / "action_board_v2.html.tmpl"
UPSTREAM_HOOD = ROOT / "ui" / "render" / "population_sets.py"
# Kept in the tree, drawn by nothing. See test_no_rectangle_carries_a_name_any_more.
BANNERS_DIR = BOARD / "duty_actions" / "banners"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

def _grid_defaults() -> dict:
    """The sliders' opening values, read out of the generator rather than restated here.

    Read as TEXT rather than imported: importing the generator pulls in v1 and everything v1
    imports, for one dict. A regex over the literal is the cheaper and more honest read.

    IT NO LONGER INSISTS ON ONE LINE. It did, and the dict outgrew it the day a sixth slider was
    added -- which failed here with a message about formatting, three tests away from anything
    to do with sliders. The literal is matched across lines instead; what is actually being
    relied on is that it IS a literal, not that it fits in eighty columns.
    """
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    m = re.search(r"^GRID_DEFAULTS\s*=\s*(\{.*?\})\s*$", src, re.M | re.S)
    assert m, "the generator no longer declares GRID_DEFAULTS as a literal"
    out = {}
    for k, v in re.findall(r"\"(\w+)\":\s*(True|False|-?\d+)", m.group(1)):
        out[k] = {"True": True, "False": False}.get(v, v)
        if isinstance(out[k], str):
            out[k] = int(out[k])
    return out


_D = _grid_defaults()

# THE SLIDERS' FULL TRAVEL, AND BOTH ENDS OF IT. Every overflow this file exists to catch was
# found at an END rather than in the middle: the plate hung out of the box at size 40, and
# Ordination landed at x -12 at the opening default of edge 40. The rest are the opening
# defaults and two odd numbers, because an arrangement that only works on multiples of ten works
# by luck. `test_the_sweep_covers_the_sliders_the_page_actually_offers` holds these against the
# <input> elements, so widening a slider cannot quietly leave half of it unswept.
#
# THE DEFAULTS ARE READ RATHER THAN TYPED, and they were typed until the day all six moved at
# once. Two guards here assert things about the board AT ITS DEFAULTS -- the state anybody
# opening the page sees -- and they find that row by matching the four numbers; typed in, they
# went stale the moment the defaults changed and both failed with "the sweep does not cover the
# opening defaults", which is a true sentence that says nothing about what had actually been
# done. Derived, a default can move without this file knowing.
GAPS = tuple(sorted({0, 1, 73, 150, _D["gap"]}))
DISPS = tuple(sorted({0, 1, 97, 150, _D["disp"]}))
SIZES = tuple(sorted({40, 62, 100, 160, _D["size"]}))
# The height slider only goes UP from the 2:1 rectangle, so 100 is its floor and
# every claim about 2:1 is a claim about that one value.
HEIGHTS = tuple(sorted({100, 175, 250, _D["height"]}))
# THE COLUMN PULL, AT ITS ENDS, AT REST, AND WHERE IT OPENS. It moves rectangles, so it cannot be
# excused from the sweep the way the two figure sliders are -- but it is a plain horizontal shift
# applied after everything is sized, so those four are the only interesting values. Four rather
# than five of each, because every value here multiplies nine thousand rectangles.
#
# ZERO IS IN THE LIST WHATEVER THE DEFAULT IS, and it is not there because it used to be the
# default. It is the RESTING position: three guards measure the pull by comparing an arrangement
# against the same arrangement with the pull off, and two more make claims about the gap and the
# fit that are only true with it off. The day the board opened on -30 instead of 0, a list of
# "the ends and the default" quietly dropped the one value all five of them need.
COLS = tuple(sorted({-150, 0, 150, _D["cols"]}))
# THE DIVIDER SLIDER, AND IT COSTS THE SWEEP NOTHING. `divide` moves one line and touches neither
# the grid nor the frame nor the marks, so it is not a sixth dimension multiplying 9,000
# rectangles by five -- every rectangle is simply asked for its divider at each of these, inside
# the row it already produced. Both ends are covered, because both ends are where this board's
# overflows have always been.
NACTS = (1, 2)


def _v2_tithe() -> tuple:
    """The ring of resources the generator deals, read out of it as text.

    Read the way _grid_defaults is and for the same reason: importing the generator pulls v1 and
    everything v1 imports in behind it, for one tuple. `None` is kept as None rather than turned
    into a string, because the whole of what this constant says about Taxation is that its entry
    is not a key.
    """
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    m = re.search(r"^V2_TITHE\s*=\s*\((.*?)\)\s*$", src, re.M | re.S)
    assert m, "the generator no longer declares V2_TITHE on one line"
    out = []
    for part in m.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        out.append(None if part == "None" else part.strip('"'))
    return tuple(out)


def _tithe_keys() -> tuple:
    """The four resource keys the board can inline.

    ONE OF THEM IS A NAME, NOT A STRING. TITHE_KEYS reads
    `("wheat", "stone", "silver", TITHE_WILD)`, so stripping quotes off each entry yields the
    identifier `TITHE_WILD` where the key should be -- and every guard comparing against it then
    compares against a word that is not a resource. Resolved here rather than worked around at
    each call site.
    """
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    m = re.search(r"^TITHE_KEYS\s*=\s*\((.*?)\)\s*$", src, re.M)
    assert m, "the generator no longer declares TITHE_KEYS on one line"
    w = re.search(r'^TITHE_WILD = "(\w+)"', src, re.M)
    assert w, "the generator no longer names the wildcard"
    out = []
    for part in m.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        out.append(w.group(1) if part == "TITHE_WILD" else part.strip('"'))
    return tuple(out)


def _load(name: str, where: pathlib.Path = TOOL):
    spec = importlib.util.spec_from_file_location("_abv2g_" + name, where / (name + ".py"))
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import %s" % name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    sys.path.insert(0, str(where))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(where))
    return mod


@pytest.fixture(scope="module")
def geo():
    return _load("geometry")


@pytest.fixture(scope="module")
def hood():
    return _load("hood")


@pytest.fixture(scope="module")
def tmpl():
    return TMPL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gen():
    """The v2 generator as a MODULE, not as text.

    Most guards here read this file as a string, because what they are checking is how it is
    written. The open-effect rules are different: the stagger and the clip's length are
    arithmetic, and arithmetic is checked by running it. Reading `OPEN_STEPS` out of the source
    and adding the numbers up here would be this file doing the generator's sum and agreeing
    with itself.
    """
    return _load("generate_action_board_v2")


# ---------------------------------------------------------------- reading the template


def _decl(text: str, name: str) -> str:
    """The right-hand side of a top-level `var NAME = ...;` in the template.

    Anchored on the declaration rather than on a line number, and it raises rather than returning
    a default: a guard that silently found nothing to check is the thing these tests are for.
    """
    m = re.search(r"^var %s\s*=\s*(.*?);\s*$" % re.escape(name), text, re.M | re.S)
    assert m, "the template has no top-level `var %s =` to read" % name
    return m.group(1).strip()


def _function(text: str, name: str) -> str:
    """One whole `function NAME(...){...}` from the template, by matching its braces."""
    head = "function %s(" % name
    assert text.count(head) == 1, "%s is declared %d times" % (name, text.count(head))
    i = text.index(head)
    j = text.index("{", i)
    depth = 0
    while True:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[i:j + 1]


def _code(text: str) -> str:
    """The same JavaScript with its whole-line `//` comments dropped.

    THIS FILE HAS TRIPPED ON ITS OWN PROSE FOUR TIMES. The comments on this board name variables,
    selectors and settings freely -- the plate block explains itself by talking about "the bare
    cell" -- so any guard that asks whether a word appears in a function has to ask about the
    CODE. Searching for a code form such as `GRID.bare` rather than a bare word is the other half
    of the same discipline, and both are used together below.
    """
    return "\n".join(ln for ln in text.split("\n") if not ln.strip().startswith("//"))


def _node(prelude: str, expression: str):
    """One expression, against a prelude of the template's own code, in node."""
    script = "%s\nprocess.stdout.write(JSON.stringify(%s));\n" % (prelude, expression)
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)




@pytest.fixture(scope="module")
def sweep(tmpl, geo):
    """Every arrangement, worked out by the template's own arithmetic, in one node run.

    Returns a list of dicts, one per (gap, edge, size, actions, cell): the cell `gridCells()`
    produced, and -- for the eight non-centre cells -- the plate and figure-row numbers the
    shipped block derives from it.
    """
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = "\n".join([
        "var GEO = %s;" % json.dumps(geo.as_dict()),
        # Read off the template rather than typed, so a board that re-lifts its card row is
        # measured the way it actually draws instead of the way this file remembers.
        "var TOP_GAP = %s;" % _decl(tmpl, "TOP_GAP"),
        "var LIFT = %s;" % _decl(tmpl, "LIFT"),
        "var CELL_BORDER = %s;" % _decl(tmpl, "CELL_BORDER"),
        "var PLATE_DROP = %s;" % _decl(tmpl, "PLATE_DROP"),
        # `merch` AT ITS DEFAULT THROUGH THE WHOLE SWEEP. It scales the marker and nothing
        # else, which is one short guard of its own below; running it as a sixth dimension would
        # multiply 18,000 rectangles by however many sizes were tried, to re-answer a question
        # that does not interact with any of the five.
        "var GRID = {gap: 0, disp: 0, size: 100, height: 100, cols: 0, merch: %d};"
        % _grid_defaults()["merch"],
        "var PLATES_DROPPED = 0;",
        "var PLATE_H = 0;",
        _function(tmpl, "gridArea"),
        _function(tmpl, "gridCells"),
        # The plate block, verbatim, wrapped so it can be called per rectangle.
        "var PLATE_BORDER = %s;" % _decl(tmpl, "PLATE_BORDER"),
        "var DUTIES = %s;" % json.dumps({"a": {"actions": 1}, "b": {"actions": 2}}),
        _function(tmpl, "mostActions"),
        _function(tmpl, "plateHeight"),
        _function(tmpl, "plateFor"),
        "var LINE_MIN_GAP = %s;" % _decl(tmpl, "LINE_MIN_GAP"),
        _function(tmpl, "slotsFor"),
        _function(tmpl, "inkAt"),
        _function(tmpl, "plateHang"),
        _function(tmpl, "cellRect"),
        _function(tmpl, "plateInset"),
        _function(tmpl, "markAt"),
        _function(tmpl, "titheMarkAt"),
        # THE PICTURE IS STUBBED AND ITS SHAPE IS NOT. Only the aspect reaches the arithmetic,
        # and it reaches it twice -- the marker is sized to stand a mark TALL, and the height it
        # ends up with is read back off the same number -- so a stub carries everything the
        # placement depends on. 1.5 rather than 1 on purpose: an aspect of 1 would make both
        # "the height follows the drawing" and "a mark tall is this wide" true by accident, and
        # the guards that ask them would pass against a page that had dropped the term. It is
        # near the drawing's own 1.4547 so the sweep binds on the same cap the board does, and
        # deliberately not equal to it, because it is a stub and not a second copy of a measured
        # fact.
        "var MERCHANT = {h: 1.5, src: \"\"};",
        "var MERCHANT_FLOOR = %s;" % _decl(tmpl, "MERCHANT_FLOOR"),
        _function(tmpl, "merchantAt"),
        _function(tmpl, "placeFor"),
        # Flattened, so the tests below read one dict per rectangle rather than a nest.
        #
        # BOTH ANSWERS TO THE TITHE QUESTION, FROM ONE ROW. placeFor is asked twice -- once as a
        # duty that takes a resource and once as Taxation, which does not -- so the guards can
        # hold the geometry of the frame and the fact that Taxation never gets one without the
        # sweep growing a sixth dimension and doubling to 18,000 rectangles.
        "function placed(r, nAct){",
        "  var L = placeFor(r, nAct, true), P = L.p;",
        "  var N = placeFor(r, nAct, false);",
        "  return {sz: P.sz, rowW: P.rowW, plateX: L.x, plateY: L.y,",
        # `plateW` is what is DRAWN and `rowBox` is what the marks NEED -- two questions since the
        # frame started spanning its rectangle, and the tests below are careful about which one
        # they are asking.
        "          plateW: L.has ? L.width : 0, plateH: L.has ? P.height : 0,",
        "          fullH: P.height, fullW: L.width, hasPlate: L.has,",
        "          rowBox: P.rowBox, fullRow: P.fullRow,",
        "          igap: P.igap, ip: P.ip, mg: P.mg, g: P.g, most: P.most,",
        "          widths: P.line.w, at: P.line.at, band: P.line.band, box: P.line.box,",
        "          seats: L.seats,",
        "          marks: (function(){ var a = []; for (var k = 0; k < nAct; k++)",
        "                              a.push(markAt(P, k)); return a; })(),",
        "          hasTithe: L.hasTithe, titheWhenNoneIsDealt: N.hasTithe,",
        "          titheMark: L.titheMark,",
        # BOTH MERCHANTS FROM THE SAME ROW, for the reason both tithe answers come from it: the
        # one that stands between a frame and a resource, and the one Taxation puts on the other
        # side of its frame because it has no resource to stand beside.
        "          merchant: L.merchant, merchantAsTaxation: N.merchant,",
        "          innerW: P.innerW, innerH: P.innerH, hang: plateHang(),",
        "          figLeft: L.figLeft, figRight: L.figRight};",
        "}",
        "var GAPS = %s, DISPS = %s, SIZES = %s, HEIGHTS = %s, COLS = %s, NACTS = %s;" % (
            json.dumps(list(GAPS)), json.dumps(list(DISPS)), json.dumps(list(SIZES)),
            json.dumps(list(HEIGHTS)), json.dumps(list(COLS)), json.dumps(list(NACTS))),
        "var out = [];",
        "GAPS.forEach(function(gap){ DISPS.forEach(function(disp){",
        "  SIZES.forEach(function(size){ HEIGHTS.forEach(function(height){",
        "  COLS.forEach(function(cols){",
        "    GRID = {gap: gap, disp: disp, size: size, height: height, cols: cols,",
        "            merch: %d};" % _grid_defaults()["merch"],
        "    var area = gridArea(), cells = gridCells();",
        "    NACTS.forEach(function(n){",
        "      cells.forEach(function(c){",
        "        var row = {gap: gap, disp: disp, size: size, height: height, cols: cols,",
        "                   nAct: n, area: area, cell: c, centre: c.centre};",
        # The rounding is the template's own: drawGrid() rounds the rectangle before anything
        # inside it is measured, so the plate is worked out against the integers the page uses.
        "        if (!c.centre){",
        "          var r = cellRect(c);",
        "          row.r = r; row.plate = placed(r, n);",
        "        }",
        "        out.push(row);",
        "      });",
        "    });",
        "  });",
        "  }); });",
        "}); });",
        "process.stdout.write(JSON.stringify(out));",
    ])
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert done.returncode == 0, (
        "the template's own grid arithmetic would not run:\n%s" % done.stderr[-3000:])
    rows = json.loads(done.stdout)
    assert len(rows) == (len(GAPS) * len(DISPS) * len(SIZES) * len(HEIGHTS) * len(COLS)
                         * len(NACTS) * 9), (
        "the sweep produced %d rectangles" % len(rows))
    return rows


# THE BOARD'S OWN HEIGHT, which two guards now measure the wheel against because the wheel is
# pinned to its bottom edge rather than centred in the area above it.
def _canvas_height() -> float:
    import importlib.util as _il

    spec = _il.spec_from_file_location("_abv2geo", TOOL / "geometry.py")
    mod = _il.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return float(mod.as_dict()["canvas"]["height"])


GEO_CANVAS_H = _canvas_height()


def PLATE_DROP_OF(text: str) -> float:
    """How far the icon plate hangs below the bottom line, read off the page rather than typed."""
    return float(_decl(text, "PLATE_DROP"))


def _tag(row):
    at = "cell (col %d, row %d)" % (row["cell"]["col"], row["cell"]["row"])
    return "gap %d, edge %d, size %d, height %d, cols %d, %d action(s), %s" % (
        row["gap"], row["disp"], row["size"], row["height"], row["cols"], row["nAct"], at)


def _arrangements(rows):
    """One entry per (gap, edge, size, height, cols): its area and nine cells, actions collapsed.

    The cells do not depend on the action count, so the tests about the GRID walk this and the
    tests about the plate walk the rows.

    THE COLUMN PULL IS PART OF THE KEY and was left out of it for one run. Without it the three
    pulls collapsed into one entry carrying twenty-seven cells, and every test that looks up an
    arrangement and expects nine got a jumble of three different ones -- which showed up as
    rectangles 150px apart at a gap of zero, a true statement about cells that were never in the
    same arrangement.
    """
    seen = {}
    for row in rows:
        if row["nAct"] != NACTS[0]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"], row["cols"])
        e = seen.setdefault(key, {"area": row["area"], "cells": [],
                                  "hang": row["cell"]["hang"]})
        e["cells"].append(row["cell"])
    return seen


# ---------------------------------------------------------------- which duty lands where


def test_the_ring_names_the_eight_faces_geometry_names(tmpl, geo):
    """A renamed face would put every duty in the wrong rectangle, or in none at all.

    `drawGrid` finds a duty by `byFace[RING_FACES[ring]]` and SILENTLY RETURNS when the lookup
    misses -- which is correct for the centre and catastrophic for anything else: rename `east` to
    `East` in geometry and this board draws seven rectangles, with no error anywhere. The names
    are a copy of geometry's COMPASS, so the copy is held against the original.

    Falsify: reorder or rename one entry of RING_FACES in the template.
    """
    faces = json.loads(_decl(tmpl, "RING_FACES").replace("'", '"'))
    assert faces == list(geo.COMPASS), (
        "the template's ring faces are %s and geometry's COMPASS is %s"
        % (faces, list(geo.COMPASS)))


def test_every_face_in_the_ring_is_a_face_some_duty_stands_on(tmpl, geo):
    """The lookup that misses is the one that draws nothing, so no slot may go unclaimed.

    This is the other half of the test above: agreeing with COMPASS is not enough on its own,
    because COMPASS could gain a ninth name and the ring would still agree with it while one
    rectangle went empty. Eight faces, eight duties, eight distinct cells, one each.

    Falsify: drop a duty from geometry's DUTIES, or name the same cell twice in RING_ORDER.
    """
    faces = json.loads(_decl(tmpl, "RING_FACES").replace("'", '"'))
    order = json.loads(_decl(tmpl, "RING_ORDER"))
    assert len(faces) == len(order) == 8, (
        "the ring is %d faces against %d cells" % (len(faces), len(order)))
    standing = {geo.face_of(clock) for _slug, _name, clock in geo.DUTIES}
    assert standing == set(faces), (
        "the duties stand on %s and the ring draws %s" % (sorted(standing), sorted(faces)))
    assert len({tuple(c) for c in order}) == 8, "two ring slots name the same cell: %s" % order


def test_each_duty_lands_in_the_cell_its_clock_angle_points_at(tmpl, geo):
    """CLERICAL AT 0 DEGREES BELONGS AT THE TOP, and nothing but this says so.

    The ring is a literal pair of lists while the duties are placed by clock angle, so the two can
    disagree completely and the board still draws nine tidy rectangles with eight names on them.
    Give Alms and Ordination swapped is a correct-LOOKING board that is wrong, and the only way to
    notice is to remember which way round the wheel used to go.

    So the expected cell is DERIVED from the angle rather than restated: a compass bearing is a
    direction, and on a 3x3 grid the cell in that direction is the one the unit vector rounds to.
    0 degrees is north is up is row 0; 90 is east is right is col 2. A restatement of RING_ORDER
    would agree with a swapped RING_ORDER for the same reason it was wrong.

    Falsify: swap any two entries of RING_ORDER in the template.
    """
    faces = json.loads(_decl(tmpl, "RING_FACES").replace("'", '"'))
    order = json.loads(_decl(tmpl, "RING_ORDER"))
    where = dict(zip(faces, [tuple(c) for c in order]))

    for _slug, name, clock in geo.DUTIES:
        th = math.radians(clock)
        want = (1 + round(math.sin(th)), 1 - round(math.cos(th)))
        got = where[geo.face_of(clock)]
        assert got == want, (
            "%s stands at %d degrees, which points at cell (col %d, row %d), but the ring puts it "
            "at (col %d, row %d)" % (name, clock, want[0], want[1], got[0], got[1]))


def test_the_centre_is_not_in_the_ring(tmpl):
    """The City is the ninth rectangle and it is not a duty, so the ring must not claim it.

    If (1,1) appeared in RING_ORDER a duty would be looked up for the centre cell. `drawGrid`
    returns before the ring lookup for the centre, so the entry would sit there unused and shift
    nothing -- until someone moved that early return, and then eight duties would become seven
    with one of them drawn on top of the City's title.

    Falsify: add [1,1] to RING_ORDER.
    """
    order = [tuple(c) for c in json.loads(_decl(tmpl, "RING_ORDER"))]
    assert (1, 1) not in order, "the ring claims the centre cell, which is the City's"


# ---------------------------------------------------------------- the grid itself


@needs_node
def test_the_nine_rectangles_are_always_two_to_one(sweep):
    """The aspect IS the design question this fork was made to answer, at every OTHER slider
    setting. The height slider exists to depart from it deliberately, so 2:1 is a claim about
    height 100 -- which is where the board opens and where the other three sliders are judged.

    A rectangle that is 2.03:1 at one end of the size slider looks like nothing at all and means
    the inscribe is wrong -- which would be read off the page as a design finding rather than as a
    bug in the page.

    Falsify: change `var rh = rw / 2` to `rw / 2.05`.
    """
    for row in sweep:
        c = row["cell"]
        assert c["width"] > 0 and c["height"] > 0, (
            "%s: the rectangle came out %g x %g" % (_tag(row), c["width"], c["height"]))
        if row["height"] != 100:
            continue                       # the height slider's business; see below
        assert abs(c["width"] / c["height"] - 2.0) < 1e-9, (
            "%s: the rectangle is %g x %g, which is %.4f:1"
            % (_tag(row), c["width"], c["height"], c["width"] / c["height"]))


def test_the_sweep_covers_the_sliders_the_page_actually_offers(tmpl):
    """A sweep that stops short of a slider's end is a guard with a blind spot at the one place
    every overflow in this board has turned up.

    So the ends are read off the <input> elements and held against the lists above. Widening a
    slider without widening the sweep fails here, with the number to change.

    Falsify: change any slider's `max` in the template.
    """
    swept = {"rGap": GAPS, "rDisp": DISPS, "rSize": SIZES, "rHeight": HEIGHTS, "rCols": COLS}
    # A SLIDER THE SWEEP DOES NOT NEED, AND WHY. The sweep measures RECTANGLES -- where they
    # land and how big they are -- and this one does not move any: it scales the acolytes
    # standing in them and the grid is identical at either end of it. Named here rather than
    # left out, so a slider that joins the page has to be accounted for in one place or the
    # other instead of quietly falling outside both.
    not_swept = {"rFig": "scales the acolytes; no rectangle moves",
                 "rMerch": "scales the merchant on the duty line; no rectangle moves, and "
                           "nothing else on the line is placed from it"}
    offered = set(re.findall(r"<input type=range id=(\w+)", tmpl))
    unaccounted = sorted(offered - set(swept) - set(not_swept))
    assert not unaccounted, (
        "the page offers %s and this guard has never heard of %s. Add it to the sweep, or to "
        "not_swept with the reason it does not belong there -- a slider in neither is the blind "
        "spot this test exists to stop."
        % (", ".join(unaccounted), "it" if len(unaccounted) == 1 else "them"))
    for ident, values in swept.items():
        m = re.search(r"<input type=range id=%s min=(-?\d+) max=(-?\d+)" % ident, tmpl)
        assert m, "the template has no `<input type=range id=%s min=.. max=..>`" % ident
        lo, hi = int(m.group(1)), int(m.group(2))
        assert min(values) == lo and max(values) == hi, (
            "%s runs %d to %d and the sweep covers %d to %d"
            % (ident, lo, hi, min(values), max(values)))


def test_every_slider_on_the_page_is_actually_listened_to(tmpl):
    """A slider nobody subscribed moves and the board does nothing.

    THIS IS NOT HYPOTHETICAL. The acolyte slider was added with its markup, its default, its
    readout and its arithmetic all correct, and without the one line that subscribes it -- so it
    dragged smoothly from end to end and changed nothing at all. There is no error, no console
    line and no visual clue; the control simply does not work, which is indistinguishable from a
    control whose effect you have not understood yet.

    IT FOLLOWS THE VARIABLE RATHER THAN THE ID, because wireGrid looks each one up into a short
    local -- `rf` for `rFig` -- and it is that local the listener is attached to. Checking for
    the id in an addEventListener call would pass for a slider that is looked up and dropped.

    Falsify: delete any `rX.addEventListener("input", apply)` from wireGrid.
    """
    wire = _code(_function(tmpl, "wireGrid"))
    looked_up = dict(re.findall(r'var\s+(\w+)\s*=\s*document\.getElementById\("(\w+)"\)',
                                wire))
    for ident in sorted(re.findall(r"<input type=range id=(\w+)", tmpl)):
        local = [v for v, i in looked_up.items() if i == ident]
        assert local, ("wireGrid never looks %s up, so nothing can be listening to it" % ident)
        assert len(local) == 1, "%s is read into %s" % (ident, ", ".join(local))
        call = '%s.addEventListener("input", apply)' % local[0]
        assert call in wire, (
            "%s is read into `%s` and `%s` is never subscribed. The slider will drag and the "
            "board will not move." % (ident, local[0], call))


@needs_node
def test_nothing_is_displaced_out_of_the_grid_area(sweep):
    """ORDINATION LANDED AT X -12 AND CONSTRUCT RAN 17PX PAST THE BOTTOM, cut by overflow:hidden.

    This is the bug the standalone lab did not have, because the lab had margin around its stage
    to draw the overflow in. The board does not: #board is overflow:hidden, so a displaced
    rectangle is quietly cropped and reads as a rectangle of a different size -- and it happened
    at the OPENING DEFAULTS, which is how it shipped for one round.

    Up to size 100 the whole arrangement, displacement included, must sit inside the grid area.
    Above 100 it is deliberately allowed past the margins, which is the next test's business.

    Falsify: inset by the displacement after sizing instead of before, i.e. use `w.width` and
    `w.height` in place of `avW` and `avH`.
    """
    for row in sweep:
        if row["size"] > 100:
            continue
        # AND THE COLUMN PULL IS ALLOWED OUT, ONE WAY. Pulled IN -- the direction it exists for --
        # the outer columns move towards the middle and the arrangement can only get narrower, so
        # the claim still has to hold and is still checked. Pushed OUT it is the size slider's
        # bargain over again: asking for wider and silently being refused is worse than asking
        # and seeing it, and the readout reports the overflow. Unlike the EDGE slider, this one
        # is applied AFTER the rectangles are sized, which is the whole reason it does not shrink
        # them -- and the price of that is exactly this.
        if row["cols"] > 0:
            continue
        box, c = row["area"], row["cell"]
        assert c["x"] >= box["x"] - 1e-9, (
            "%s: starts at x %g, left of %g" % (_tag(row), c["x"], box["x"]))
        # THE TOP IS A CLAIM AT HEIGHT 100 ONLY. The height slider grows the rectangles upward
        # on purpose and is allowed to take them past the area -- that is the trade it makes to
        # keep every bottom edge where it was, and the readout reports it in amber. Everything
        # else about the box still has to stay inside.

        assert c["x"] + c["width"] <= box["x"] + box["width"] + 1e-9, (
            "%s: reaches x %g, past %g"
            % (_tag(row), c["x"] + c["width"], box["x"] + box["width"]))
        # AND DOWN, THE AREA IS NO LONGER THE TEST. The wheel is pinned to the bottom margin
        # now, not centred in the area, so where its top lands is whatever the arrangement's own
        # height makes it -- and the top row is allowed above the area, which is what pinning
        # the other end means. What must still hold is the pin itself, and that is the next
        # guard's business.
        assert c["y"] + c["height"] <= GEO_CANVAS_H + 1e-9, (
            "%s: reaches y %g, past the bottom of the board"
            % (_tag(row), c["y"] + c["height"]))


@needs_node
@pytest.mark.xfail(strict=True, reason="the size slider runs off the canvas above 104; see below")
def test_the_block_stays_on_the_canvas_at_every_setting(sweep, geo):
    """KNOWN FAILURE, RECORDED RATHER THAN EXCLUDED. The size slider's top half is off the board.

    Above 100 the block is deliberately allowed past the MARGINS, and the argument for that is
    that asking for bigger and silently being refused is worse than asking for bigger and seeing
    it. That argument only holds while you can see it. Past the CANVAS there is nothing to see:
    #board is overflow:hidden, so the rectangles are cropped and what the slider does from there
    on is shave the left and right columns.

    Measured on the shipped page, at the moment this was written:

        gap   0, edge   0   leaves the canvas at size 105; 174px off at 130, 375px at 160
        gap   0, edge  40   leaves the canvas at size 105; 162px off at 130, 351px at 160
        gap  20, edge  40   leaves the canvas at size 105; 156px off at 130, 339px at 160
        gap 150, edge 150   leaves the canvas at size 124;   8px off at 130,  45px at 160

    The slider's own range is `min=40 max=160`, so at the common settings 56 of its 120 steps do
    something nobody can look at. The range was chosen when the slider was added and the number
    was not derived from anything -- which is the bug. WHAT TO DO ABOUT IT IS A DESIGN DECISION
    and is left open: capping the slider near 104 keeps every step meaningful but takes away the
    "ask for bigger and see it" affordance that the overflow above 100 exists to give; letting it
    run and showing the crop keeps the affordance and keeps the waste.

    `strict=True` ON PURPOSE. When the slider is capped or the arrangement clamped, this test
    starts PASSING and the strict marker turns that into a failure that says so -- so the fix
    cannot land while the note above still claims the bug is open.

    Falsify, once it is fixed: widen the slider's `max` again.
    """
    for row in sweep:
        c = row["cell"]
        assert c["x"] >= -1e-9, (
            "%s: starts at x %g, off the left of the canvas" % (_tag(row), c["x"]))
        assert c["y"] >= -1e-9, (
            "%s: starts at y %g, off the top of the canvas" % (_tag(row), c["y"]))
        assert c["x"] + c["width"] <= geo.CANVAS_W + 1e-9, (
            "%s: reaches x %g on a canvas %d wide"
            % (_tag(row), c["x"] + c["width"], geo.CANVAS_W))
        assert c["y"] + c["height"] <= geo.CANVAS_H + 1e-9, (
            "%s: reaches y %g on a canvas %d tall"
            % (_tag(row), c["y"] + c["height"], geo.CANVAS_H))


@needs_node
def test_the_wheel_stands_on_the_bottom_margin_and_is_centred_across(sweep, tmpl):
    """Across it is centred; down it is pinned, to the one gap this board already repeats.

    IT WAS CENTRED BOTH WAYS and the vertical half never held still: the slack moved with every
    slider, so the lowest plate finished a different distance off the bottom edge on every
    setting -- and the plates hang below the rectangles, so centring the OUTLINES put visibly
    more air above the drawing than below it. The wheel now sits so the lowest plate keeps
    exactly the drop a plate keeps from its own rectangle. The board ends on the spacing it is
    built from, and the number stops depending on where the sliders are.

    MEASURED TO THE LOWEST PLATE, not the lowest rectangle: the bottom row's middle cell is
    pushed down by the displacement and its plate hangs below that.

    ACROSS, NOTHING CHANGED. A plate is centred under its own rectangle and never wider than it,
    so the arrangement's left and right edges are the rectangles' -- and the slack is split.

    Falsify: centre the block vertically again, drop the displacement from the pin, or measure
    it to the rectangles instead of the plates.
    """
    drop = PLATE_DROP_OF(tmpl)
    by_arrangement = {}
    for row in sweep:
        key = (row["gap"], row["disp"], row["size"], row["height"], row["cols"])
        by_arrangement.setdefault(key, []).append(row)
    for key, rows in by_arrangement.items():
        area = rows[0]["area"]
        cells = [r["cell"] for r in rows]
        left = min(c["x"] for c in cells)
        right = max(c["x"] + c["width"] for c in cells)
        tag = "gap %d, edge %d, size %d, height %d, cols %d" % key
        if key[4] <= 0:
            assert abs((left - area["x"]) - (area["x"] + area["width"] - right)) < 1e-6, (
                "%s: %g of slack on the left and %g on the right"
                % (tag, left - area["x"], area["x"] + area["width"] - right))
        # THE PIN, measured the way the page draws it: the lowest rectangle's bottom, the drop
        # below it, the plate's own height, and then the same drop again to the board's edge.
        plated = [r for r in rows if r.get("plate") and r["plate"]["hasPlate"]]
        if not plated:
            continue
        low = max(r["plate"]["plateY"] + r["plate"]["fullH"] for r in plated)
        assert abs((GEO_CANVAS_H - low) - drop) < 1e-6, (
            "%s: the lowest plate ends %g above the board's bottom edge, against the %g a plate "
            "keeps from its own rectangle" % (tag, GEO_CANVAS_H - low, drop))


@needs_node
def test_the_plate_reaches_exactly_what_the_arrangement_expects_of_it(sweep, tmpl):
    """What hangs below a rectangle is one expression, and the pin is built on it.

    THE RESERVE IS GONE AND THE AGREEMENT IS NOT. `gridCells` used to hold back `plateHang()`
    below the bottom row before centring the block on it, which meant the reserve and the drawn
    plate had to be the same number or the whole wheel sat a few pixels off with nothing to
    compare it against. Pinning the bottom replaced the reserve with the same arithmetic used
    the other way round -- the offset is worked out FROM the plate's drop and height -- so the
    two expressions still have to agree, and this is still where that is held.

    Falsify: drop PLATE_DROP from either end of the pin, or reserve for a plate of a different
    height than the one drawn.
    """
    drop = PLATE_DROP_OF(tmpl)
    checked = 0
    for row in sweep:
        p, r = row.get("plate"), row.get("r")
        if not p or not p["hasPlate"]:
            continue
        drawn_to = (p["plateY"] + p["fullH"]) - (r["y"] + r["height"])
        assert abs((drop + p["fullH"]) - drawn_to) < 1e-9, (
            "%s: a plate is built to hang %g below its rectangle and reaches %g"
            % (_tag(row), drop + p["fullH"], drawn_to))
        checked += 1
    assert checked > 500, "only %d plates were measured" % checked


@needs_node
def test_the_two_outer_columns_move_by_the_same_amount_and_the_middle_does_not(sweep):
    """One number, both ways, and the wheel stays centred on its middle column.

    THE BRIEF WAS "BY THE SAME AMOUNT" and that is the half a sign error destroys. Give both
    columns the same sign and the whole wheel slides sideways instead of closing up; move one
    and leave the other and the middle column stops being the middle. Neither raises, and at a
    small setting both look like a layout that was always slightly off rather than like a
    slider doing the wrong thing -- which is why they are worth a test and not a reading.

    IT IS MEASURED AGAINST THE SAME ARRANGEMENT AT REST, not against the slider in the abstract.
    The pull is applied after the rectangles are sized, so nothing else about the arrangement
    may move with it: same widths, same heights, same vertical positions, and the only
    difference in x is the pull itself, taken off column 0 and added to column 2.

    Falsify: flip either sign, drop either line, scale one by anything but one, or move the
    middle column with them.
    """
    at = {}
    for row in sweep:
        if row["nAct"] != NACTS[0]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"])
        c = row["cell"]
        at.setdefault(key, {}).setdefault(row["cols"], {})[(c["col"], c["row"])] = c
    assert 0 in COLS, "the sweep has no arrangement with the pull at rest to measure against"
    checked = 0
    for key, pulls in at.items():
        rest = pulls[0]
        for cols, cells in pulls.items():
            if cols == 0:
                continue
            for (col, rw), c in cells.items():
                r = rest[(col, rw)]
                want = {0: -cols, 1: 0, 2: cols}[col]
                moved = c["x"] - r["x"]
                assert abs(moved - want) < 1e-9, (
                    "gap %d, edge %d, size %d, height %d: at a pull of %+d, column %d moved by "
                    "%+g where it should have moved %+g. The outer columns take the pull off "
                    "and add it on, by the SAME amount, and the middle column does not move at "
                    "all -- that is what keeps the wheel centred on the City."
                    % (key + (cols, col, moved, want)))
                for same in ("y", "width", "height", "bottom"):
                    assert abs(c[same] - r[same]) < 1e-9, (
                        "gap %d, edge %d, size %d, height %d: at a pull of %+d, column %d row "
                        "%d changed its %s from %g to %g. The pull is applied after the "
                        "rectangles are sized, so it may move them and nothing else -- if it "
                        "resizes anything it has become a second gap slider."
                        % (key + (cols, col, rw, same, r[same], c[same])))
                checked += 1
    assert checked, "no arrangement was compared against its own resting pull"

@needs_node
def test_the_four_edge_rectangles_move_the_way_the_slider_says(sweep):
    """Top up, bottom down, left left, right right -- by the SAME amount, which is the brief.

    Four `if`s with a hand-written sign each: one flipped is a grid that leans instead of
    expanding, and at the opening default of 40 a lean looks like a layout decision rather than a
    mistake.

    The movement is measured against the UNDISPLACED corners of the same row or column, not
    against the slider directly, because the sizing changes when the displacement does. That is
    the one question which survives the resize: is each edge rectangle exactly as far out of line
    as the slider says.

    Falsify: change any of the four signs, or any of the four `d`s to `d / 2`.
    """
    for key, a in _arrangements(sweep).items():
        gap, disp, size, _height, _cols = key
        if disp == 0:
            continue                    # nothing to measure, and the test above covers it
        at = {(c["col"], c["row"]): c for c in a["cells"]}
        tag = "gap %d, edge %d, size %d, height %d, cols %d" % key
        moved = {
            "top rectangle rose":
                at[(1, 1)]["y"] - at[(1, 0)]["y"] - (at[(0, 1)]["y"] - at[(0, 0)]["y"]),
            "bottom rectangle fell":
                at[(1, 2)]["y"] - at[(1, 1)]["y"] - (at[(0, 2)]["y"] - at[(0, 1)]["y"]),
            "left rectangle moved":
                at[(1, 1)]["x"] - at[(0, 1)]["x"] - (at[(1, 0)]["x"] - at[(0, 0)]["x"]),
            "right rectangle moved":
                at[(2, 1)]["x"] - at[(1, 1)]["x"] - (at[(2, 0)]["x"] - at[(1, 0)]["x"]),
        }
        for what, by in moved.items():
            assert abs(by - disp) < 1e-6, "%s: the %s %g, not %g" % (tag, what, by, disp)


@needs_node
def test_at_the_sliders_zero_the_rectangles_touch(sweep):
    """GAP 0 AND EDGE 0 MEANS NO GAP ANYWHERE, which was a correction asked for by name.

    The first lab drew the three columns flush and left a seam between the ROWS, because the
    vertical spacing came from the 2:1 height rather than from the gap. One number serving both
    directions is the fix, and a seam of one pixel at zero is the symptom of it coming apart.

    Falsify: use a different term for `y`'s step than for `x`'s, e.g. `row * (rh + g + 1)`.
    """
    # AT REST ON THE PULL, because this is a claim about the GAP: it says that at gap 0
    # the rectangles touch, and the column pull exists precisely to move two of the three
    # columns away from where the gap put them.
    a = _arrangements(sweep)[(0, 0, 100, 100, 0)]
    at = {(c["col"], c["row"]): c for c in a["cells"]}
    for row in range(3):
        for col in range(3):
            c = at[(col, row)]
            if col < 2:
                nxt = at[(col + 1, row)]
                assert abs(nxt["x"] - (c["x"] + c["width"])) < 1e-9, (
                    "at gap 0 there is %g between the rectangles in columns %d and %d of row %d"
                    % (nxt["x"] - (c["x"] + c["width"]), col, col + 1, row))
            if row < 2:
                nxt = at[(col, row + 1)]
                assert abs(nxt["y"] - (c["y"] + c["height"])) < 1e-9, (
                    "at gap 0 there is %g between the rectangles in rows %d and %d of column %d"
                    % (nxt["y"] - (c["y"] + c["height"]), row, row + 1, col))


@needs_node
def test_the_grid_area_is_read_off_the_row_above_it_and_not_typed(tmpl, geo):
    """THE GRID LINES UP WITH THE ROW ABOVE, END TO END, and every number comes from that row.

    It used to run margin to margin -- the card's left edge to the same distance off the right of
    the canvas -- which lined it up with the BOARD rather than with the things on the board. Then
    it ran card to card, on the argument that the wheel answers to the two pictures it is a
    choice between and not to a box that is not a duty; that left it ending 170 short of the
    rightmost thing above it, which reads as a wheel that missed rather than as a wheel making a
    point.

    BOTH ENDS ARE OBJECTS: the first card's left edge and the TAKE TITHE box's right edge. A
    constant that happened to equal today's 1174 would pass any check OF today's numbers, so
    this moves the objects and demands the area follow them.

    Falsify: type either end, or read the second card's right edge again.
    """
    def area(g):
        return _node("\n".join([
            "var GEO = %s;" % json.dumps(g),
            "var TOP_GAP = %s;" % _decl(tmpl, "TOP_GAP"),
            "var LIFT = %s;" % _decl(tmpl, "LIFT"),
            _function(tmpl, "gridArea"),
        ]), "gridArea()")

    base = area(geo.as_dict())
    want = geo.as_dict()
    assert base["x"] == want["slots"]["actionA"]["x"], (
        "the area starts at %g and the leftmost card at %g"
        % (base["x"], want["slots"]["actionA"]["x"]))
    far = want["tithe"]
    assert base["x"] + base["width"] == far["x"] + far["width"], (
        "the area ends at %g and the Take Tithe box at %g"
        % (base["x"] + base["width"], far["x"] + far["width"]))

    # move the left end
    g = geo.as_dict()
    g["slots"]["actionA"]["x"] += 17
    g["slots"]["actionA"]["y"] += 9
    moved = area(g)
    assert moved["x"] == base["x"] + 17, (
        "the card moved 17 right and the area's left edge went from %g to %g"
        % (base["x"], moved["x"]))
    assert moved["width"] == base["width"] - 17, (
        "the first card moved 17 right, the second did not, and the width went from %g to %g"
        % (base["width"], moved["width"]))
    assert moved["y"] == base["y"] + 9 + 17, (
        "the card moved 9 down and the margin grew 17, and the top went from %g to %g"
        % (base["y"], moved["y"]))

    # and the right end, on its own
    g = geo.as_dict()
    g["tithe"]["x"] -= 40
    shrunk = area(g)
    assert shrunk["x"] == base["x"], "moving the Tithe box moved the area's LEFT edge"
    assert shrunk["width"] == base["width"] - 40, (
        "the Tithe box moved 40 left and the width went from %g to %g"
        % (base["width"], shrunk["width"]))

    # and the second card is no longer one of its ends
    g = geo.as_dict()
    g["slots"]["actionB"]["x"] += 55
    assert area(g)["width"] == base["width"], (
        "moving the second action card changed the grid's width, so it is still one of the ends")


@needs_node
def test_the_build_summary_says_what_the_page_will_draw(tmpl, geo):
    """A SECOND COPY OF gridArea() LIVES IN THE GENERATOR, AND IT HAS ALREADY DRIFTED ONCE.

    The template's version is the one that draws; the generator's only prints, in the build
    summary -- which is the one place somebody checks the number instead of measuring it. When
    the span stopped being margin-to-margin the template was changed and the summary was not, so
    the build announced 1344 while the page drew 1174.

    The two cannot share code across the language boundary, so they are held against each other
    here: the summary's own arithmetic, run, against gridArea() in node.

    Falsify: change either side's expression without the other.
    """
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    m = re.search(r"print\(\"  the duty grid is fitted to %d x %d at \(%d, %d\)[^\n]*\n"
                  r"\s*% \((.*?)\)\)", src, re.S)
    assert m, "the build summary no longer prints the grid's area"
    d = geo.as_dict()
    # THE SAME TWO OBJECTS THE SUMMARY NAMES, bound here so the printed expression can be run.
    # They are the first action card and the Take Tithe box -- the ends of the row above the
    # wheel -- and if the summary ever names something else this evaluates to nothing and says
    # so, which is the point of running it rather than reading it.
    card, far = d["slots"]["actionA"], d["tithe"]
    lift = d["art"]["y"] - (d["status"]["y"] + d["status"]["height"] + 16)
    m_ = card["x"]
    top = (card["y"] - lift) + card["height"] + m_
    # One line, because the printed expression is wrapped across several in the source and
    # `eval` will not take the indentation.
    expr = " ".join(line.strip() for line in m.group(1).splitlines())
    printed = eval(expr, {"__builtins__": {}},                              # noqa: S307
                   {"far": far, "card": card, "d": d, "top": top, "m": m_})
    said = _node("\n".join([
        "var GEO = %s;" % json.dumps(d),
        "var TOP_GAP = %s;" % _decl(tmpl, "TOP_GAP"),
        "var LIFT = %s;" % _decl(tmpl, "LIFT"),
        _function(tmpl, "gridArea"),
    ]), "gridArea()")
    assert printed[:4] == (said["width"], said["height"], said["x"], said["y"]), (
        "the build says the grid is %d x %d at (%d, %d) and the page draws it %g x %g at (%g, %g)"
        % (printed[0], printed[1], printed[2], printed[3],
           said["width"], said["height"], said["x"], said["y"]))


@needs_node
def test_the_height_slider_grows_the_boxes_upward_from_a_fixed_bottom(sweep):
    """THE LOWER EDGE DOES NOT MOVE, which is the whole of what was asked for.

    Three things hang off a rectangle's bottom edge and none of them may shift when this slider
    is dragged: the line the acolytes stand on, the icon plate PLATE_DROP under it, and the
    vertical balance of the wheel, which is centred on the un-extended block plus that plate.
    So the extension is applied AFTER the arrangement is laid out and centred -- `y` goes up and
    `height` grows by the same amount, leaving `y + height` untouched.

    AND THE WIDTH DOES NOT MOVE EITHER. Re-inscribing the taller shape would have kept the whole
    thing inside the area, by making the rectangles narrower -- which pays for the height out of
    the width and shifts every bottom edge to do it. The width is left alone and the top is
    allowed to leave the area instead, which the readout reports.

    Falsify: grow the box downward, or feed the extra height back into `fit`.
    """
    by = {}
    for row in sweep:
        if row["nAct"] != NACTS[0]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["cols"],
               row["cell"]["col"], row["cell"]["row"])
        by.setdefault(key, {})[row["height"]] = row["cell"]
    compared = 0
    for key, at in by.items():
        base = at.get(100)
        assert base is not None, "height 100 is not in the sweep for %s" % (key,)
        for h, c in sorted(at.items()):
            tag = ("gap %d, edge %d, size %d, cols %d, cell (col %d, row %d) at height %d"
                   % (key + (h,)))
            assert abs((c["y"] + c["height"]) - (base["y"] + base["height"])) < 1e-9, (
                "%s: the bottom edge moved from %g to %g"
                % (tag, base["y"] + base["height"], c["y"] + c["height"]))
            assert abs(c["width"] - base["width"]) < 1e-9, (
                "%s: the width changed from %g to %g" % (tag, base["width"], c["width"]))
            want = base["height"] * h / 100.0
            assert abs(c["height"] - want) < 1e-6, (
                "%s: the box is %g tall where %d%% of %g is %g"
                % (tag, c["height"], h, base["height"], want))
            if h > 100:
                assert c["y"] < base["y"] - 1e-9, (
                    "%s: the box got taller without its top rising" % tag)
                compared += 1
    assert compared, "the sweep never raised the height slider off 100"


@needs_node
def test_the_plates_and_the_figure_line_ignore_the_height_slider(sweep):
    """The plate hangs off the bottom edge and the acolytes stand on it, so neither may notice.

    This is the other half of the test above, said about the objects rather than the rectangle:
    if the extension leaked into `placeFor` the plates would walk up the board as the slider was
    dragged, which looks like the slider moving the wrong thing.

    Falsify: measure the plate from `r.y` instead of `r.y + r.height`.
    """
    by = {}
    for row in sweep:
        if row["centre"]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["nAct"],
               row["cell"]["col"], row["cell"]["row"])
        by.setdefault(key, {})[row["height"]] = row["plate"]
    for key, at in by.items():
        base = at.get(100)
        for h, p in at.items():
            for field in ("plateY", "figLeft", "figRight", "plateX", "plateW", "plateH"):
                assert abs(p[field] - base[field]) < 1e-9, (
                    "gap %d, edge %d, size %d, %d action(s), cell (col %d, row %d): %s went from "
                    "%g to %g when the height slider moved to %d"
                    % (key + (field, base[field], p[field], h)))


def test_the_city_is_always_drawn(tmpl):
    """IT WAS A CHECKBOX WHILE THE CENTRE STOOD FOR NOTHING, and it stands for something now.

    The City is where the bottom-right panel went; it holds people like any duty does and it is
    the fullest rectangle on the board. A switch that removes it leaves a hole in the middle of
    the wheel and a figure pass sized against a board that is no longer the board -- the City is
    what sets the tallest pile.

    Falsify: put `cCentre` or a `GRID.centre` test back.
    """
    assert "cCentre" not in tmpl, "the centre checkbox is back in the toolbar"
    assert "GRID.centre" not in tmpl, "something still asks whether the City should be drawn"
    body = _code(_function(tmpl, "drawGrid"))
    assert "if (c.centre){" in body, (
        "drawGrid no longer has a branch for the centre rectangle, so the City is drawn as a "
        "duty or not at all")
    assert "return;" in body.split("if (c.centre){")[1][:900], (
        "the City's branch no longer returns early, so it would fall through into the ring "
        "lookup and be drawn as a ninth duty")


# ---------------------------------------------------------------- taking the frame off


def _rule(text: str, selector: str) -> dict:
    """One CSS rule's declarations, as {property: value}.

    Comments are stripped first, because the prose around these rules names properties and
    selectors freely and a guard that reads a comment as a declaration is a guard that fails on
    an explanation. That has happened three times on this board.

    STRIPPED AS COMMENTS, NOT AS LINES THAT LOOK LIKE ONE. This dropped every line beginning `/*`,
    `*` or `*/`, which is most of a comment and not all of it: the continuation lines in this
    file's comments begin with ordinary words, so a comment sitting BETWEEN two declarations left
    its middle behind, and that text ran on into the declaration below it. The next declaration
    then came back under a key made of a paragraph of prose. Nothing failed -- the property was
    simply absent, and a guard asking whether it was there said no. `--plate-edge` was added
    between two comments and was invisible to this for exactly that reason.
    """
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    m = re.search(r"%s\s*\{([^}]*)\}" % re.escape(selector), body)
    assert m, "the template has no `%s` rule" % selector
    out = {}
    for d in m.group(1).split(";"):
        if ":" in d:
            k, v = d.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def test_taking_the_frame_off_changes_colour_and_nothing_else(tmpl):
    """THE ONE THING THIS CHECKBOX MUST NOT DO IS MOVE THE ARRANGEMENT IT WAS ADDED TO LOOK AT.

    `border:none` or a zero width would give each cell back 4px of width and 4px of height, and
    everything inside is placed against the PADDING box -- so the plate, the parchment and the
    whole figure row would shift two pixels. The board would still look right, because every
    rectangle would shift by the same two pixels, and the comparison the checkbox exists for
    would be against a board that is no longer the board.

    So the rule is held to colour: a background and three border COLOURS, nothing else.

    Falsify: add `border:none`, `border-width:0` or any padding to the `.dcell.bare` rule.
    """
    d = _rule(tmpl, ".dcell.bare")
    allowed = {"background", "background-color",
               "border-top-color", "border-left-color", "border-right-color"}
    extra = sorted(set(d) - allowed)
    assert not extra, (
        "`.dcell.bare` sets %s, and anything but a colour moves what is inside the cell"
        % ", ".join(extra))
    assert "border-bottom-color" not in d, (
        "`.dcell.bare` hides the bottom edge too, and the acolytes stand on it -- their feet are "
        "6px above it, so that line is the floor of the drawing and not part of the frame")
    for k in ("border-top-color", "border-left-color", "border-right-color"):
        assert k in d, "`.dcell.bare` does not hide the %s" % k.replace("-", " ")


def test_the_bare_rule_comes_after_the_states_it_has_to_beat(tmpl):
    """IT WOULD WORK ON SEVEN RECTANGLES AND NOT ON THE OTHER TWO, which is the worst way to fail.

    `.dcell.lit`, `.dcell.sel` and `.dcell.centre` all set `border-color` as a SHORTHAND, so they
    write all four edges. `.dcell.bare` has the same specificity as each of them -- two classes --
    so the later rule wins and nothing but source order decides it. Move `bare` above them and the
    frame comes off every resting rectangle and stays on the hovered one, the selected one and the
    City: a board that looks like a hover bug rather than a rule in the wrong place.

    Being last is also what makes the bottom edge carry the state: `bare` overrides three of the
    four edges and leaves `.lit`/`.sel` holding the fourth.

    Falsify: move the `.dcell.bare` rule above `.dcell.lit`.
    """
    where = {}
    for sel in (".dcell.lit", ".dcell.sel", ".dcell.centre", ".dcell.bare"):
        i = tmpl.find(sel + "{")
        assert i > 0, "the template has no `%s{` rule" % sel
        where[sel] = i
    for sel in (".dcell.lit", ".dcell.sel", ".dcell.centre"):
        assert where[".dcell.bare"] > where[sel], (
            "`.dcell.bare` is declared before `%s`, which has the same specificity -- so %s wins "
            "and the frame stays on those cells" % (sel, sel))


@needs_node
def test_the_frame_is_not_in_any_of_the_arithmetic(tmpl):
    """A WAY OF LOOKING AT THE BOARD, NOT A STATE OF IT.

    `bare` must reach exactly one place: the class on the cell. If it ever reaches the sizing --
    a cell that sizes itself differently with the frame off, say, to use the 4px back -- then the
    two states stop being the same arrangement and the checkbox stops answering the question it
    was added to answer, silently, because both states would still look tidy.

    Falsify: read `GRID.bare` anywhere in gridArea, gridCells or the plate block.
    """
    for name in ("gridArea", "gridCells", "cellRect",
                 "plateHeight", "plateFor", "plateHang", "placeFor"):
        body = _code(_function(tmpl, name))
        assert "GRID.bare" not in body, (
            "%s reads the frame setting, so the arrangement is no longer the same with the frame "
            "on and off:\n%s" % (name, body))
    assert tmpl.count('classList.add("bare")') == 1, (
        "the bare class is added in %d places; one is the cell, and a second would be a state "
        "this file cannot follow" % tmpl.count('classList.add("bare")'))


def test_the_frame_checkbox_is_wired_to_a_redraw(tmpl):
    """A checkbox that sets a flag nothing re-reads is a checkbox that does nothing until the next
    time a slider moves -- which looks like a checkbox that works, as long as you touch a slider
    first.

    The class is added in `drawGrid`, so the box has to cause a `drawGrid`. It shares `apply()`
    with the three sliders and the centre box, which is the only path that redraws.

    Falsify: drop the `cb.addEventListener("change", apply)` line.
    """
    body = _function(tmpl, "wireGrid")
    assert 'document.getElementById("cBare")' in body, "wireGrid never looks the checkbox up"
    assert re.search(r"GRID\.bare\s*=\s*\w+\.checked", body), (
        "wireGrid does not read the checkbox into GRID.bare:\n%s" % body)
    assert re.search(r"\w+\.addEventListener\(\"change\", apply\)", body), (
        "nothing redraws when the checkbox changes")
    changes = re.findall(r"(\w+)\.addEventListener\(\"change\", apply\)", body)
    assert len(changes) == 1, (
        "%d change listeners on apply(); the frame box is the only checkbox left -- the City's "
        "went when it stopped being optional -- and a second one here is a control this guard "
        "does not know about" % len(changes))
    assert '<input type=checkbox id=cBare' in tmpl, "the toolbar has no `bare` checkbox"


def test_the_generator_publishes_every_setting_the_page_reads(tmpl):
    """`GRID.bare` with no default is `undefined`, which is falsy, so the page opens framed and
    the checkbox works from the first click. Nothing breaks -- it just stops being true that the
    generator decides what the board opens on, and the `--gap`/`--edge`/`--size` flags and the
    build summary go on describing a dict the page is only half reading.

    So the two are held against each other both ways: every default must be read, and every
    setting the page reads must have a default.

    Falsify: drop `bare` from GRID_DEFAULTS, or read a new `GRID.x` in the template.
    """
    published = set(_grid_defaults())
    read = set(re.findall(r"GRID\.([A-Za-z_][A-Za-z0-9_]*)", tmpl))
    assert not read - published, (
        "the template reads GRID.%s and the generator has no default for %s"
        % (", GRID.".join(sorted(read - published)),
           "it" if len(read - published) == 1 else "them"))
    assert not published - read, (
        "the generator publishes %s and the page never reads %s"
        % (", ".join(sorted(published - read)),
           "it" if len(published - read) == 1 else "them"))


# ---------------------------------------------------------------- what the readout says


@needs_node
def test_the_wheel_measurement_is_the_rectangles_own_extent(tmpl, sweep):
    """REPORTING THE AREA INSTEAD WOULD BE RIGHT ON THE NUMBER ANYBODY CHECKS FIRST.

    `gridArea()` is the room the nine are centred in; the readout is meant to say what was PUT in
    it -- the arrangement's own width and height, displacement and all. At the opening defaults
    the room is 1344 x 842 and the arrangement is 1344 x 732: the SAME width, because width is the
    binding dimension and the block fills it exactly. So a tag that printed `a.width` would agree
    with this one on the width at the defaults and be 110 out on the height, which reads as a
    number you have misremembered rather than as the wrong number.

    The test holds both halves: the readout is built from the extent, and the extent and the area
    really are confusable -- identical on one axis and not the other -- so this is worth holding.

    Falsify: build the wheel term from `a.width` and `a.height`.
    """
    body = _function(tmpl, "wireGrid")
    m = re.search(r'"\s*·\s*wheel "\s*\+\s*Math\.round\((\w+) - (\w+)\)'
                  r'\s*\+\s*" × "\s*\+\s*Math\.round\((\w+) - (\w+)\)', body)
    assert m, (
        "the readout no longer reports the wheel as one extent minus another:\n%s" % body)
    assert (m.group(1), m.group(2)) == ("r", "l"), (
        "the wheel's width is %s - %s, and the rectangles' own span is r - l"
        % (m.group(1), m.group(2)))
    assert (m.group(3), m.group(4)) == ("bt", "tp"), (
        "the wheel's height is %s - %s, and the rectangles' own span is bt - tp"
        % (m.group(3), m.group(4)))

    # AND THERE IS A SETTING WHERE THEY ARE INDISTINGUISHABLE, which is what makes naming the
    # right one worth a guard. At size 100 the block fills the area exactly across -- width is
    # the binding dimension -- so a readout printing the AREA would agree with this one on the
    # number anybody checks first and be short only on the height. At the board's own defaults
    # the two are far apart, so the mistake would be obvious there; it is the size-100 case that
    # would hide it.
    d = _grid_defaults()
    a = _arrangements(sweep)
    # AT REST ON THE PULL for the same reason as the gap test above: "the block fills the area
    # exactly across" is a fact about the fit, and the pull moves two columns off it on purpose.
    fills = (d["gap"], d["disp"], 100, 100, 0)
    for key, why in ((fills, "where the block fills the area"),
                     ((d["gap"], d["disp"], d["size"], d["height"], d["cols"]),
                      "at the opening defaults")):
        assert key in a, (
            "the sweep does not cover gap %d, edge %d, size %d, height %d, cols %d -- add it to "
            "GAPS, DISPS, SIZES, HEIGHTS and COLS" % key)
    cells, area = a[fills]["cells"], a[fills]["area"]
    w = max(c["x"] + c["width"] for c in cells) - min(c["x"] for c in cells)
    h = max(c["y"] + c["height"] for c in cells) - min(c["y"] for c in cells)
    assert abs(w - area["width"]) < 1e-6, (
        "at size 100 the arrangement is %g wide and the area %g -- they were the same, which is "
        "the case where reporting the area instead of the extent would look right"
        % (w, area["width"]))
    assert h < area["height"] - 1, (
        "at size 100 the arrangement is %g tall and the area %g; if those agreed too then the "
        "readout could not be wrong and this guard would be checking nothing"
        % (h, area["height"]))


@needs_node
def test_the_readout_still_says_the_size_of_one_rectangle(tmpl, sweep):
    """The per-rectangle size is the number to watch while dragging, and it is the one the board
    itself cannot show -- both sliders shrink the rectangles, so the thing you are setting is not
    the thing you are reading.

    Adding the wheel's total beside it must not have replaced it.

    Falsify: drop the `c.width × c.height` term from the tag.
    """
    body = _function(tmpl, "wireGrid")
    assert re.search(r"Math\.round\(c\.width\)\s*\+\s*\" × \"\s*\+\s*Math\.round\(c\.height\)",
                     body), ("the readout no longer leads with the size of one rectangle:\n%s"
                             % body)
    assert "var cs = gridCells(), a = gridArea(), c = cs[0];" in body, (
        "the readout's three numbers no longer come off one call each")


def test_choosing_an_action_makes_the_sound_whichever_route_you_took(tmpl):
    """TWO WAYS TO MAKE THE SAME CHOICE, AND ONE OF THEM WAS SILENT.

    An action is chosen either by its duty-action ICON, which goes through `pickAction`, or by
    clicking the PICTURE of it, which goes through `select` -- and the cue lived in the first
    only. Clicking the picture chose the action and said nothing, which reads as the sound being
    broken rather than as a route that skips it; and it is the quieter kind of bug, because the
    board plainly did the right thing on screen.

    The Tithe comes through `select` too and gets the cue for the same reason: it is a choice of
    what to do this turn, like the other two.

    NOT A THIRD COPY OF THE CUE. `pickAction` does not call `select` -- it sets the duty and the
    slot together to avoid rendering twice -- so the two routes each say it once and neither
    double-plays.

    Falsify: take `sfx("select")` out of `select`, or add a call to it inside `pickAction`.
    """
    sel = _code(_function(tmpl, "select"))
    assert 'sfx("select")' in sel, (
        "choosing an action by its picture is silent again:\n%s" % sel)
    assert "sfxWake()" in sel, (
        "the cue is played without waking the audio context first, so the first click of a "
        "session makes no sound:\n%s" % sel)
    act = _code(_function(tmpl, "pickAction"))
    assert 'sfx("select")' in act, "choosing an action by its icon has gone silent"
    assert "select(" not in act, (
        "pickAction now calls select(), so the cue is played twice for one choice:\n%s" % act)


def test_both_action_pictures_are_click_targets_for_their_own_action(tmpl):
    """The picture is the one-click route to an action and is what the cards are for.

    Each card carries its own slot and hands that slot to the click, so the two cannot end up
    both selecting the same one -- which is the failure a shared handler reading `S.slot` would
    produce, and it would look like the second card being ignored.

    Falsify: drop the click listener, or close over one slot for both cards.
    """
    body = _code(_function(tmpl, "drawArt"))
    assert '["actionA","actionB"].forEach(function(slot){' in body, (
        "the two cards are no longer drawn from one list of slots:\n%s" % body)
    assert re.search(r'art\.addEventListener\("click", function\(\)\{ slotOrSelect\(slot\); \}\);',
                     body), (
        "an action card is no longer wired to choose its own slot:\n%s" % body)
    route = _code(_function(tmpl, "slotOrSelect"))
    assert "select(slot)" in route, (
        "the card's click no longer reaches select():\n%s" % route)
    assert "pickFile" in route, (
        "the card's click no longer opens the picker while images are being replaced, so edit "
        "mode has lost its way in:\n%s" % route)


def test_one_click_on_a_mark_chooses_its_action_whatever_duty_you_were_on(tmpl, geo):
    """IT WORKED ON TWO DUTIES OF EIGHT, AND THE TWO WERE THE ONES WITH A SINGLE ACTION.

    `slotClick` used to ask where you already were: on a duty you were not standing on, the
    click chose the DUTY and left the action unanswered, so reaching an action took two clicks.
    But `pickDuty` answers the slot itself when a duty has only ONE action -- so Allocation and
    Taxation lit their picture on the first click and the other six did not. The same gesture
    did two different things depending on a property of the duty you cannot see from the mark
    you are clicking, which is the hardest kind of inconsistency to attribute.

    THE TRADE IT CAME FROM IS GONE WITH THE RIBBON. Two marks used to cover 52% of a tile --
    39x39 each inside 57x101 -- so aiming at a tile and hitting an action was the usual case.
    The marks sit on a plate BELOW the rectangle now, outside the element entirely, and the
    rectangle is its own target. The two questions have two places to be asked.

    Falsify: put the `d.duty !== S.duty` branch back in slotClick.
    """
    body = _code(_function(tmpl, "slotClick"))
    assert "pickAction(d.duty, d.slot)" in body, (
        "a mark no longer chooses its own action:\n%s" % body)
    # THE COMPARISON, NOT THE NAME. `S.duty` legitimately appears on the edit-mode line, where
    # it is the duty a dropped picture belongs to; what must not come back is slotClick asking
    # whether you are ALREADY on the duty it belongs to.
    for cmp_ in ("!== S.duty", "=== S.duty", "!= S.duty", "== S.duty"):
        assert cmp_ not in body, (
            "slotClick asks where you already are again (`%s`), so a mark means one thing on "
            "the duty you are on and another everywhere else:\n%s" % (cmp_, body))
    assert "pickDuty" not in body, (
        "a mark routes through pickDuty again, which leaves the action unanswered on the six "
        "duties that have two of them:\n%s" % body)

    # AND THE RECTANGLE STILL ASKS THE OTHER QUESTION, which is what makes one click on a mark
    # safe: the tile is where "which duty" is asked, and it answers the action only when there
    # is no choice to make.
    grid = _code(_function(tmpl, "drawGrid"))
    assert "pickDuty(slug)" in grid, (
        "clicking a rectangle no longer chooses its duty, so the two targets have collapsed "
        "into one question")
    only = _code(_function(tmpl, "onlySlot"))
    assert "actions === 1" in only, (
        "onlySlot no longer answers the slot for a one-action duty, which is what lets the "
        "rectangle choose a duty AND its action when there is only one:\n%s" % only)
    counts = {slug: None for slug, _n, _d in geo.DUTIES}
    assert len(counts) == 8, "expected eight duties, found %d" % len(counts)


# ---------------------------------------------------------------- the icon plate


@needs_node
def test_the_plate_hangs_below_the_line_and_is_flush_with_its_left_edge(sweep, tmpl):
    """FLUSH LEFT AND SIX BELOW, which is the whole of what was asked for.

    The plate used to sit in the rectangle's top right corner and was bounded by it. Then it hung
    under the bottom line, CENTRED, which this test held for several rounds -- and it is centred no
    longer: there are two frames under the line now and they are pushed to opposite edges, so the
    claim that replaces centring is that the plate's left edge IS the rectangle's inner left edge,
    exactly, with no term between them.

    EXACT, NOT WITHIN HALF A PIXEL. The centring claim had to be held to a tolerance because it
    went through a `/ 2` and a `Math.round`; flush does not, and a tolerance on an equality that
    can be exact is a tolerance that hides a one-pixel bug of the kind this file has already had
    three of.

    Falsify: put the centring term back, pay CELL_BORDER twice, or replace PLATE_DROP with a
    literal.
    """
    drew = 0
    border = float(_decl(tmpl, "CELL_BORDER"))
    drop = float(_decl(tmpl, "PLATE_DROP"))
    for row in sweep:
        if row["centre"]:
            continue
        p, r = row["plate"], row["r"]
        if not p["hasPlate"]:
            assert p["plateW"] == 0 and p["plateH"] == 0, (
                "%s: no plate, but it still has a size of %g x %g"
                % (_tag(row), p["plateW"], p["plateH"]))
            continue
        drew += 1
        assert p["plateX"] == r["x"] + border, (
            "%s: the rectangle's inner left edge is at %g and the plate starts at %g"
            % (_tag(row), r["x"] + border, p["plateX"]))
        assert p["plateY"] == r["y"] + r["height"] + drop, (
            "%s: the line's outer edge is at %g and the plate starts at %g, which is %g below "
            "instead of %g" % (_tag(row), r["y"] + r["height"], p["plateY"],
                               p["plateY"] - (r["y"] + r["height"]), drop))
    assert drew, "no arrangement in the sweep drew a plate at all, so nothing was checked"


# ---------------------------------------------------------------- the tithe resource


@needs_node
def test_the_frame_is_built_to_the_marks_and_the_resource_is_outside_it(sweep, tmpl):
    """THE FRAME IS THE SIGNAL, which is what it was reshaped to be.

    It has been three things. A frame of its own beside the resource's; then one frame spanning
    the rectangle with the resource at its right-hand end; and now a frame built to the row of
    marks, with the resource standing outside it on bare ground. The first two both made the two
    objects look alike -- same ground, same border, or no border and the same ground -- and they
    are not alike. An action is CHOSEN; a resource says what the tile provides, to anyone,
    standing there or not. Inside a frame you can choose it; outside, it is telling you something.

    READABLE AT REST, which is the whole point. The distinction used to live entirely in what
    happened on hover, so a still board said nothing about which of the three objects on that line
    could be pressed.

    AND ONE WIDTH ON EVERY TILE, at every slider setting: `rowBox` is the widest row any duty
    needs plus its margin, and it does not depend on the rectangle at all. So Taxation's frame is
    the same object as everyone else's with nothing beside it.

    Falsify: span the rectangle again, inset the frame from the left edge, or size it from the
    duty's own marks.
    """
    border = float(_decl(tmpl, "CELL_BORDER"))
    widths, drew = set(), 0
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        p_, r = row["plate"], row["r"]
        drew += 1
        widths.add(p_["plateW"])
        assert p_["plateX"] == r["x"] + border, (
            "%s: the rectangle's inner left edge is at %g and the frame starts at %g"
            % (_tag(row), r["x"] + border, p_["plateX"]))
        assert p_["plateW"] == p_["rowBox"], (
            "%s: the frame is %g wide and the row it holds needs %g"
            % (_tag(row), p_["plateW"], p_["rowBox"]))
        assert p_["plateX"] + p_["plateW"] < r["x"] + r["width"] - border, (
            "%s: the frame still reaches the rectangle's far edge" % _tag(row))
    assert drew, "no arrangement in the sweep drew a frame, so nothing was checked"
    # ONE WIDTH PER ARRANGEMENT, WHICH IS THE CLAIM THAT SURVIVED THE LINE BEING JUSTIFIED. The
    # frame used to be one number for the whole board at every setting -- the widest row any duty
    # needs plus its margin -- because the spacing inside it was fixed at `igap`. The spacing is
    # now whatever the line's leftover divides into, so the frame grows and shrinks with the
    # rectangles. What must still hold is that every duty's frame is the same object: at one
    # slider setting, all eight are identical, however many marks they hold.
    by_arrangement = {}
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"], row["cols"])
        by_arrangement.setdefault(key, set()).add(round(row["plate"]["plateW"], 6))
    bad = {k: sorted(v) for k, v in by_arrangement.items() if len(v) > 1}
    assert not bad, (
        "within one arrangement the frames come in more than one width, so a duty is being "
        "framed to what IT holds rather than to the widest row: %s" % sorted(bad.items())[:3])
    assert len(widths) > 1, (
        "the frame is one width at every setting, so it is no longer built to the line's own "
        "spacing and this guard is watching a constant")


def test_the_resource_did_not_move_when_the_frame_left_it(sweep, tmpl, geo):
    """THE FRAME MOVED AWAY FROM THE RESOURCE; THE RESOURCE DID NOT MOVE.

    It keeps `GEO.marks.pad` from the RECTANGLE's inner right edge -- the margin it kept from the
    frame's right edge while the frame ended there -- so nothing on the board shifted when the
    frame shrank and the only visible change is that there is no edge around it. A resource that
    had also jumped sideways would have made the change look bigger than it is, and made it hard
    to judge the one thing being judged.

    AND IT IS LEVEL WITH THE MARKS BESIDE IT. `P.ip` does both jobs: the margin from the
    rectangle's edge, and the inset that centres a 50px mark on a 62px line. The same number,
    because the line IS the mark plus that margin at each end -- so a resource that drifted
    vertically would mean the two had come apart.

    Falsify: measure from the frame's edge instead of the rectangle's, or centre it on the line
    with its own arithmetic.
    """
    pad = geo.as_dict()["marks"]["pad"]
    border = float(_decl(tmpl, "CELL_BORDER"))
    drew = 0
    for row in sweep:
        if row["centre"] or not row["plate"]["hasTithe"]:
            continue
        p_, r = row["plate"], row["r"]
        drew += 1
        right = p_["titheMark"]["x"] + p_["titheMark"]["w"]
        assert abs(right - (r["x"] + r["width"] - border - pad)) < 1e-9, (
            "%s: the resource ends %g from the rectangle's inner right edge, not %g"
            % (_tag(row), (r["x"] + r["width"] - border) - right, pad))
        # AND IT IS THE SAME HEIGHT AS EVERYTHING ELSE ON THE LINE. The drawings are not the
        # same shape, so sizing them by a box makes them look like different sizes: what they
        # share is the band, and the width each one takes follows its own drawing.
        assert abs(p_["titheMark"]["h"] - p_["band"]) < 1e-9, (
            "%s: the resource is %g tall and the line's band is %g"
            % (_tag(row), p_["titheMark"]["h"], p_["band"]))
        # LEVEL WITH THE MARKS, measured rather than argued. The marks are placed against the
        # frame's PADDING box, one PLATE_BORDER inside its top; the resource is placed against the
        # board. Comparing them without that border is off by one -- which is the size of error
        # this guard exists to catch and would therefore have hidden.
        pb = float(_decl(tmpl, "PLATE_BORDER"))
        assert p_["titheMark"]["y"] - p_["plateY"] == pb + p_["marks"][0]["top"], (
            "%s: the resource sits %g below the frame's top and the marks sit %g"
            % (_tag(row), p_["titheMark"]["y"] - p_["plateY"], pb + p_["marks"][0]["top"]))
    assert drew, "no arrangement in the sweep drew a resource, so nothing was checked"


def test_every_gap_on_the_duty_line_is_the_same(sweep):
    """FOUR OBJECTS, THREE SPACES, ONE NUMBER -- which is the whole of what was asked for.

    The line was 6, 13 and 17.6 at the opening settings: the frame padded its own marks, the
    merchant stood in what was left over, and the resource was pinned to the rectangle's far
    edge. Three different gaps on one line read as three unrelated pairs rather than as a row,
    and no amount of saying "the frame is the signal" fixes that -- the eye measures the spaces.

    SO THE ROW IS JUSTIFIED BETWEEN TWO FIXED ENDS and everything between is spaced by one
    number. That number also decides the frame's width, because the gap INSIDE the frame is the
    same gap as the ones outside it.

    MEASURED MARK TO MARK, NOT FROM THE FRAME'S EDGE. The frame carries `ip` of ground past its
    last mark; that ground belongs to the mark it surrounds, not to the space after it, so a
    guard measuring from the frame's outer edge would be asking for `g + ip` between two of the
    four pairs and `g` between the others -- the very unevenness this replaced.

    Falsify: pad the frame into the gap, pin the merchant to the frame's edge, or give the
    resource a margin of its own.
    """
    drew = 0
    for row in sweep:
        if row["centre"]:
            continue
        p = row["plate"]
        if not (p["hasPlate"] and p["hasTithe"] and p["merchant"]):
            continue
        drew += 1
        g, at, w = p["g"], p["at"], p["widths"]
        assert g >= p["igap"] - 1e-9, (
            "%s: the line is spaced %g apart, under the %g a mark keeps from a mark"
            % (_tag(row), g, p["igap"]))
        # EVERY PAIR IN THE LINE, FROM THE SLOTS THEMSELVES. There is no arithmetic here that
        # repeats the layout's -- the slots say where each drawing starts and how wide it came
        # out, and the only claim is that the space between any two of them is the same number.
        assert len(at) == len(w) == p["most"] + 2, (
            "%s: the line has %d slots and %d widths" % (_tag(row), len(at), len(w)))
        for k in range(1, len(at)):
            assert abs((at[k] - (at[k - 1] + w[k - 1])) - g) < 1e-9, (
                "%s: slot %d starts %g after slot %d ends, against a spacing of %g"
                % (_tag(row), k + 1, at[k] - (at[k - 1] + w[k - 1]), k, g))
        # AND THE TWO ENDS ARE WHERE THE RECTANGLE PUT THEM.
        assert abs(at[0] - p["ip"]) < 1e-9, (
            "%s: the line starts %g inside the rectangle, not %g" % (_tag(row), at[0], p["ip"]))
        assert abs((at[-1] + w[-1]) - (p["innerW"] - p["ip"])) < 1e-9, (
            "%s: the line ends %g from the rectangle's far edge, not %g"
            % (_tag(row), p["innerW"] - (at[-1] + w[-1]), p["ip"]))
        # AND THE FRAME STILL ENDS BEFORE WHAT COMES NEXT. Its padding eats into the gap by `ip`,
        # so at the tightest settings its edge comes close -- but never past.
        assert p["plateX"] + p["plateW"] <= p["plateX"] + at[p["most"]] + 1e-9, (
            "%s: the frame's edge has reached into the merchant's slot" % _tag(row))
    assert drew > 500, "only %d arrangements drew the whole line" % drew


@needs_node
def test_the_line_is_drawn_whole_or_not_at_all(sweep):
    """A frame with no resource beside it was a state; it is not one any more.

    THE LINE USED TO BE GIVEN UP A PIECE AT A TIME -- the merchant first, then the resource, then
    the frame -- because each was fitted into what the one before it had left. Justifying the row
    took that apart: every piece is sized from the same band and the same leftover, so when the
    leftover closes it closes for all of them at once. There is nothing left to order.

    WHICH IS WORTH A GUARD BECAUSE IT IS EASY TO BREAK QUIETLY. A refusal written against one
    piece -- a floor on the merchant, a clearance on the resource -- would bring back a line that
    is drawn in parts, and a tile missing only its resource looks exactly like Taxation.

    Falsify: refuse any one piece on a rectangle that drew the rest.
    """
    checked = 0
    for row in sweep:
        if row["centre"]:
            continue
        p = row["plate"]
        if not p["hasPlate"]:
            assert not p["hasTithe"] and not p["merchant"], (
                "%s: a rectangle with no frame drew the rest of its line" % _tag(row))
            continue
        assert p["hasTithe"], (
            "%s: the frame is drawn and its resource is not, which is the one state Taxation's "
            "empty end is supposed to mean" % _tag(row))
        assert p["merchant"], (
            "%s: the frame and the resource are drawn and the merchant between them is not"
            % _tag(row))
        checked += 1
    assert checked > 500, "only %d rectangles drew a line" % checked


@needs_node
def test_a_duty_dealt_no_resource_gets_no_resource_at_any_setting(sweep):
    """TAXATION'S EMPTY RIGHT-HAND END IS CORRECT, and it has to stay distinguishable from the
    two other ways that end can be empty: a resource whose cut is missing from the tree, which
    draws an empty dashed slot, and a rectangle too narrow for one, which draws nothing and is
    counted.

    IT READS DIFFERENTLY SINCE THE FRAMES MERGED, and that is worth saying out loud rather than
    discovering on the board. Taxation used to have no right-hand frame at all; it now has the
    same full-width frame as every other duty with nothing at that end of it. The frame is the
    same width everywhere on purpose -- that was the point of giving a one-mark duty the same
    ground as a two-mark one -- so the empty end is Taxation saying "none belongs here" in the
    same object the others say "here is yours" in.

    The first is what `tkey === null` is for and the second is what `hasTithe` is for, and this
    holds the first across every rectangle the sliders can make -- including the wide ones, where
    there is plenty of room and nothing but the deal to stop a frame appearing.

    Falsify: make placeFor ignore its third argument, or test it for truthiness somewhere that a
    missing argument reads as "yes".
    """
    for row in sweep:
        if row["centre"]:
            continue
        assert row["plate"]["titheWhenNoneIsDealt"] is False, (
            "%s: a duty dealt no resource was given one anyway" % _tag(row))


# ---------------------------------------------------------------- the tithe pool


def _v2_seats() -> dict:
    """The demo occupancy the page opens on, read out of the template as JSON-ish text."""
    src = TMPL.read_text(encoding="utf-8")
    m = re.search(r"^var V2_SEATS = (\{.*?\n\};)", src, re.M | re.S)
    assert m, "the template no longer declares V2_SEATS"
    body = m.group(1).rstrip(";")
    body = re.sub(r"(\w+):", r'"\1":', body)
    return json.loads(body)


def _lift(geo) -> int:
    """The template's own LIFT, worked out from geometry the way the page works it out."""
    d = geo.as_dict()
    return d["art"]["y"] - (d["status"]["y"] + d["status"]["height"] + 16)


def _wild_duty(geo, ring) -> str:
    """The slug the wildcard is dealt to, found rather than typed -- it has moved once already."""
    wild = _tithe_token()["wild"]
    for (slug, _, _), key in zip(geo.DUTIES, ring):
        if key == wild:
            return slug
    raise AssertionError("no duty is dealt the wildcard, so its rule cannot be isolated")


def _single_duty(geo, ring) -> str:
    """A duty offering exactly one ordinary resource, for the pool-of-one case."""
    wild = _tithe_token()["wild"]
    for (slug, _, _), key in zip(geo.DUTIES, ring):
        if key is not None and key != wild:
            return slug
    raise AssertionError("no duty offers a plain resource")


@pytest.fixture(scope="module")
def pool(tmpl, geo):
    """Every seat's tithe pool, worked out by the template's own functions in node.

    Driven against the REAL demo occupancy and the REAL ring rather than a fixture of this
    file's own, because what is being checked is partly the deal: that the cornucopia on
    Construct reaches p3, and that Taxation's seats bring nothing. A stub here would check the
    arithmetic and miss the thing the arithmetic is for.
    """
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    ring = _v2_tithe()
    duties = [{"slug": s, "face": geo.face_of(d)} for s, _, d in geo.DUTIES]
    dmap = {s: {"tithe": k} for (s, _, _), k in zip(geo.DUTIES, ring)}
    seats = _v2_seats()
    occ = {slug: seats.get(slug, []) for slug in dmap}
    players = [p["id"] for p in geo.as_dict()["players"]]
    script = "\n".join([
        "var GEO = %s;" % json.dumps({
            "duties": duties, "tithe": geo.as_dict()["tithe"],
            "marks": {"pad": geo.as_dict()["marks"]["pad"]},
            "canvas": geo.as_dict()["canvas"], "slots": geo.as_dict()["slots"],
            # THE PHASE COMES FROM GEOMETRY HERE TOO, so a guard on the gate cannot pass by
            # agreeing with a string this file typed. eligible() reads S.phase against this.
            "livePhase": geo.LIVE_PHASE}),
        "var PANEL_BORDER = %s;" % _decl(tmpl, "PANEL_BORDER"),
        "var LIFT = %d;" % _lift(geo),
        "var DUTIES = %s;" % json.dumps(dmap),
        "var TITHE = %s;" % json.dumps(_tithe_token()),
        "var S = {occupancy: %s, seat: null, slot: null, tithe: null, phase: GEO.livePhase};"
        % json.dumps(occ),
        "function dutyOf(slug){ return DUTIES[slug]; }",
        # THE STANDING RULE THE POOL IS NOW BUILT ON, and the eligibility that reads it beside
        # it. Both are driven here rather than restated, for the reason the pool already is:
        # these two answers have to come from ONE walk of the occupancy or the box and the tiles
        # can disagree on screen, and a test that asked them separately would not notice.
        _function(tmpl, "standsOn"),
        _function(tmpl, "actionPhase"),
        _function(tmpl, "eligible"),
        _function(tmpl, "tithePool"),
        _function(tmpl, "onlyTithe"),
        _function(tmpl, "titheLayout"),
        _function(tmpl, "titheSlotLeft"),
        _function(tmpl, "lifted"),
        _function(tmpl, "controlBox"),
        "var out = {pools: {}, only: {}, layout: {}, iso: {}, isoOnly: {},",
        "           can: {}, canIso: {}, canIsoOff: {}, canOff: {}};",
        "function _can(){ return GEO.duties.filter(function(d){ return eligible(d.slug); })",
        "                     .map(function(d){ return d.slug; }); }",
        "%s.forEach(function(p){ S.seat = p;" % json.dumps(players),
        "  out.pools[p] = tithePool(p); out.only[p] = onlyTithe();",
        "  out.can[p] = _can();",
        # AND THE SAME SEATS WITH THE PHASE TURNED OFF. The gate is the one part of this rule
        # whose failure LOOKS like success -- every duty open reads as a board with no rule --
        # so the off state is measured rather than assumed from the on state.
        "  S.phase = 'not-' + GEO.livePhase; out.canOff[p] = _can(); S.phase = GEO.livePhase; });",
        "[1,2,3].forEach(function(n){ out.layout[n] = titheLayout(n); });",
        # BOTH COLUMNS' ROWS IN BOARD COORDINATES, worked out by the page's own functions. The
        # column used to share the box's rect, so "same y, same height" was proof enough; it is
        # hung off the box's first row now, so the rows themselves are what has to be compared.
        "var _C = controlBox(), _L = titheLayout(TITHE.order.length);",
        "var _bt = lifted(GEO.tithe);",
        "out.cols = {box: {y: _bt.y, height: _bt.height, rows: []},",
        "            col: {y: _C.y, height: _C.height, width: _C.width, start: _C.start,",
        "                  size: _C.size, left: _C.left, x: _C.x, rows: []},",
        "            block: _L.block};",
        "for (var i = 0; i < TITHE.order.length; i++){",
        "  out.cols.box.rows.push(_bt.y + PANEL_BORDER + _L.start + i * _L.pitch);",
        "  out.cols.col.rows.push(_C.y + PANEL_BORDER + _C.start + i * _C.pitch); }",
        # THE DEMO OCCUPANCY PROVES LESS THAN IT LOOKS, which three mutations found at once. Every
        # seat that stands on the cornucopia ALSO stands on a silver tile, so removing the union
        # changes nothing; every seat on Taxation already holds wheat, so counting Taxation
        # changes nothing; and no seat has a pool of exactly one, so the branch that answers a
        # single resource was never taken. A guard driven only by the real state agreed with all
        # three mistakes. These stand one figure on one tile so each rule is the only thing that
        # could produce the answer.
        "var REAL = S.occupancy;",
        "var ISO = {wildOnly: %s, taxOnly: %s, oneOnly: %s, nowhere: {}};" % (
            json.dumps({_wild_duty(geo, ring): ["z"]}),
            json.dumps({"taxation": ["z"]}),
            json.dumps({_single_duty(geo, ring): ["z"]})),
        "for (var k in ISO){ S.occupancy = ISO[k]; S.seat = 'z';",
        "  out.iso[k] = tithePool('z'); out.isoOnly[k] = onlyTithe(); out.canIso[k] = _can();",
        # AND THE SAME ONE FIGURE WITH THE PHASE TURNED OFF, which is the only place left where
        # the gate's difference can be SEEN. Every seat in the demo deal now stands on every
        # tile, so "what this seat may act on" and "every duty" are the same list for all four
        # of them, live or not -- a gate that had stopped working would agree with that.
        "  S.phase = 'not-' + GEO.livePhase; out.canIsoOff[k] = _can();",
        "  S.phase = GEO.livePhase; }",
        "S.occupancy = REAL;",
        "process.stdout.write(JSON.stringify(out));",
    ])
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert done.returncode == 0, (
        "the template's own tithe arithmetic would not run:\n%s" % done.stderr[-3000:])
    return json.loads(done.stdout)


def _tithe_token() -> dict:
    """What the generator hands the page as __TITHE__ -- the order and the wildcard."""
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    m = re.search(r'^TITHE_WILD = "(\w+)"', src, re.M)
    assert m, "the generator no longer names the wildcard"
    wild = m.group(1)
    keys = _tithe_keys()
    return {"order": [k for k in keys if k != wild], "wild": wild}


@needs_node
def test_the_pool_is_what_this_seats_figures_are_standing_on(pool, geo):
    """THE BOX IS NOT A PROPERTY OF THE SELECTED DUTY, which is what it looked like.

    Taking a tithe moves nobody, so it does not matter which duty is selected when you take one.
    What matters is where your figures already are: the pool is the resources offered by every
    tile this seat stands on. Checked against the page's REAL demo occupancy and the REAL ring,
    because half of what is being held is the deal rather than the arithmetic.

    Falsify: read the selected duty's resource instead, or drop the occupancy test.
    """
    # WORKED OUT FROM THE DEAL RATHER THAN TYPED. It used to be ["wheat", "stone"], which was
    # p1's three tiles in the old demo occupancy -- and every seat stands on every duty now, so
    # a typed answer would be a sentence about a board that no longer exists. What the guard is
    # for survives: the pool is what THIS seat's figures are standing on, whatever that is.
    want = []
    for (slug, _n, _d), key in zip(geo.DUTIES, _v2_tithe()):
        if key and key != _tithe_token()["wild"] and "p1" in _v2_seats()[slug] and key not in want:
            want.append(key)
    assert sorted(pool["pools"]["p1"]) == sorted(want), (
        "p1 stands on tiles offering %s and got %%s" % want
        % pool["pools"]["p1"])
    assert pool["pools"]["p2"] == ["wheat", "stone", "silver"], pool["pools"]["p2"]


@needs_node
def test_the_pool_is_a_set_in_the_generators_own_order(pool):
    """FIGURES ON TWO STONE TILES GIVE YOU STONE, NOT STONE TWICE.

    You take ONE resource, so a second tile offering the same thing changes nothing you could
    choose -- and a box listing stone twice would be offering a choice between a thing and
    itself. p1 stands on two wheat tiles and gets one wheat.

    AND IN A FIXED ORDER, which is the generator's. Walking the duties and appending as they come
    would list a pool in whatever order the ring happens to run, so the same two resources would
    swap places between seats and the box would never settle.

    Falsify: build the pool by appending per duty, or sort it some other way.
    """
    for seat, got in pool["pools"].items():
        assert len(got) == len(set(got)), "%s's pool repeats: %s" % (seat, got)
    order = _tithe_token()["order"]
    for seat, got in pool["pools"].items():
        assert got == [k for k in order if k in got], (
            "%s's pool is %s, which is not %s order" % (seat, got, order))


@needs_node
def test_the_cornucopia_unions_every_resource_in_and_taxation_adds_none(pool):
    """THE WILDCARD'S WHOLE RULE IN ONE LINE, and the one duty that offers nothing.

    A figure on the cornucopia tile lets you take any resource, so rather than appearing in the
    box as a fourth thing to choose it puts the other three in. p3 stands on Construct and on
    nothing else that offers silver -- Produce is p2 and p3 both, so take care -- and still has
    the full three.

    TAXATION ADDS NOTHING, which is the other end of the same test: it is the one duty with no
    resource, and a pool that counted it would be offering something that does not exist.

    Falsify: let the wildcard into the pool as itself, or give Taxation a resource.
    """
    order = _tithe_token()["order"]
    wild = _tithe_token()["wild"]

    # ONE FIGURE ON THE CORNUCOPIA AND NOWHERE ELSE, which is the only way to see the rule at
    # all. Every seat in the demo state that stands on Construct also stands on a silver tile, so
    # a pool built WITHOUT the union comes out identical for all of them -- this guard passed on
    # a page that had dropped the rule entirely until a mutation said so.
    assert pool["iso"]["wildOnly"] == order, (
        "a figure on the cornucopia alone should hold every resource, not %s"
        % pool["iso"]["wildOnly"])
    for where, got in list(pool["pools"].items()) + list(pool["iso"].items()):
        assert wild not in got, (
            "%s's pool offers the wildcard itself, which cannot be taken: %s" % (where, got))

    # AND ONE FIGURE ON TAXATION, for the same reason: both seats standing there already hold
    # wheat, so giving Taxation a resource changed nothing anybody could measure.
    assert pool["iso"]["taxOnly"] == [], (
        "a figure on Taxation alone should hold nothing, not %s" % pool["iso"]["taxOnly"])

    # AND A SEAT STANDING NOWHERE HAS NOTHING. The empty box is the case easiest to forget and
    # the one that lets a confirm be offered for a move nobody can make.
    #
    # DRIVEN BY A SEAT OF THIS FILE'S OWN, NOT BY THE DEAL. It used to be p4, which stood on no
    # duty in the demo occupancy -- and the demo is a bench: every seat now has a figure on every
    # tile so the four acolytes can be checked against the four slots they stand over. A deal
    # arranged for looking at is the wrong place to keep a degenerate case; `nowhere` is a seat
    # standing on nothing, which is the case itself rather than a board that happens to contain
    # it.
    assert pool["iso"]["nowhere"] == [], pool["iso"]["nowhere"]
    assert all(pool["pools"][p] for p in pool["pools"]), (
        "a seat in the demo deal holds nothing, so the board opens with a box the bench cannot "
        "show: %s" % pool["pools"])


@needs_node
def test_one_resource_answers_itself_the_way_a_one_action_duty_does(pool):
    """WHERE THERE IS NOTHING TO CHOOSE, CHOOSING THE THING CHOOSES IT.

    `onlySlot` settled this shape for a duty holding one action; a pool holding one resource is
    the same question. Without it the board sits with the Take Tithe box lit, the confirm
    withheld, and exactly one place to click to proceed -- a second click with one possible
    target, which reads as the board not having noticed the first.

    Falsify: always return null, or return the first of any pool.
    """
    # NO SEAT IN THE DEMO STATE HAS A POOL OF ONE, so driven against it alone this guard took
    # the `len == 1` branch exactly never and agreed with a function that returned null always.
    # `oneOnly` stands one figure on one ordinary duty, which is the whole case.
    assert len(pool["iso"]["oneOnly"]) == 1, pool["iso"]["oneOnly"]
    assert pool["isoOnly"]["oneOnly"] == pool["iso"]["oneOnly"][0], (
        "a pool of one does not answer itself: %r" % pool["isoOnly"]["oneOnly"])
    assert pool["isoOnly"]["nowhere"] is None, "an empty pool answered with something"

    for seat, got in pool["pools"].items():
        want = got[0] if len(got) == 1 else None
        assert pool["only"][seat] == want, (
            "%s has a pool of %d (%s) and answers %r" % (seat, len(got), got, pool["only"][seat]))
    assert any(len(g) > 1 for g in pool["pools"].values()), (
        "no seat has more than one resource, so the null case is never shown")


@needs_node
def test_every_resource_in_the_box_is_drawn_the_same_size(pool, geo, tmpl):
    """THE SAME OBJECT AT TWO SIZES, FOR A REASON THAT HAS NOTHING TO DO WITH IT.

    The column used to be divided by however many resources the pool held, so one was drawn at
    the box's full width and three at a third of it. Switch seat and the wheat changed size while
    nothing about wheat changed -- the size was carrying how many OTHER resources you happened to
    hold, which is not a fact about wheat. The duty marks settled this for the board already: an
    icon that changes size with the arrangement is one you cannot compare, so the size is fixed
    and the room is what gives.

    AND THE SIZE IS THE FULL SET'S, taken from TITHE.order rather than from a 3. The box is built
    for every resource there is, so a fourth would rescale every pool together instead of the box
    quietly meaning something different depending on who is looking at it.

    Falsify: divide the column by the pool again, or write the full count as a literal.
    """
    # READ, NOT MERELY CORRECT. Typing the right number passes every measurement below -- a
    # mutation replacing the computed height with the 213 it happens to equal went unnoticed --
    # so the source is asked whether it is deriving the column or restating it.
    src = _code(_function(tmpl, "titheLayout"))
    assert "GEO.tithe" in src and "GEO.marks.pad" in src, (
        "the box's layout no longer comes from geometry:\n%s" % src)
    assert "TITHE.order.length" in src, (
        "the box is no longer built for every resource there is:\n%s" % src)
    assert not re.search(r"[^.\w]\d{2,}", src), (
        "the box's layout has a number typed into it:\n%s" % src)

    t = geo.as_dict()["tithe"]
    pad = geo.as_dict()["marks"]["pad"]
    full = len(_tithe_token()["order"])
    sizes = {n: pool["layout"][str(n)]["size"] for n in (1, 2, 3)}
    assert len(set(sizes.values())) == 1, (
        "a resource is drawn at %s depending on how many others there are" % sorted(set(sizes.values())))

    L = pool["layout"]["3"]
    top = t["labelTop"] + t["labelH"] + pad
    h = t["height"] - top - pad
    w = t["width"] - 2 * pad
    assert L["size"] == min(h / full - pad, w), (
        "the resources are %g where the full set of %d gives %g"
        % (L["size"], full, min(h / full - pad, w)))
    assert 0 < L["size"] <= w


@needs_node
def test_the_block_of_resources_is_centred_with_one_spacing(pool, geo):
    """FEWER RESOURCES CLOSE UP AND SIT IN THE MIDDLE, with the air between them unchanged.

    A resource you do not have is not a slot standing empty -- there is nothing to say about it --
    so two resources are two marks in the middle of the column with the same gap between them
    that three would have. The gap is the board's own margin, so the pair reads as the same
    object spaced the same way rather than as a short version of a longer list.

    THE CENTRING IS THE CLAIM, and it is checked as equal air at both ends rather than by
    recomputing the start, because a test that re-derives the position agrees with a mistake in
    it for the same reason the mistake happened.

    Falsify: pin the block to the top, or let the spacing follow the pool.
    """
    t = geo.as_dict()["tithe"]
    pad = geo.as_dict()["marks"]["pad"]
    top = t["labelTop"] + t["labelH"] + pad
    bottom = top + (t["height"] - top - pad)

    pitches = set()
    for n in (1, 2, 3):
        L = pool["layout"][str(n)]
        pitches.add(L["pitch"])
        assert L["pitch"] == L["size"] + pad, (
            "n=%d: the gap between resources is %g, not the board's own %g"
            % (n, L["pitch"] - L["size"], pad))
        assert L["block"] == n * L["size"] + (n - 1) * pad, (
            "n=%d: %d resources and %d gaps do not come to %g" % (n, n, n - 1, L["block"]))
        above = L["start"] - top
        below = bottom - (L["start"] + L["block"])
        assert abs(above - below) < 1e-9, (
            "n=%d: %g of air above the resources and %g below" % (n, above, below))
        assert above >= 0, "n=%d: the block starts %g above the column" % (n, -above)
    assert len(pitches) == 1, (
        "the spacing changes with the pool: %s" % sorted(pitches))


def test_choosing_an_action_puts_the_resource_down(tmpl):
    """S.slot AND S.tithe ARE TWO HALVES OF ONE ANSWER, so one cannot outlive the other.

    "I am taking a tithe, and it is stone" is one sentence. Choose an action afterwards and the
    resource has to go with it, or the board keeps a resource chosen underneath an action and the
    confirm gate reads a stale yes.

    ALL THREE ROUTES, which is the half that was missed. The line went into `select()` -- the
    route the action PICTURES take -- and not into `pickAction`, the route the action MARKS take,
    so clicking a mark left the resource set while clicking the picture cleared it. Two ways to
    make one choice, disagreeing. Found by driving the page rather than by reading it.

    Falsify: drop `S.tithe = null` from any of select, pickAction or pickDuty.
    """
    for fn in ("select", "pickAction", "pickDuty"):
        body = _code(_function(tmpl, fn))
        assert re.search(r"S\.tithe = null;", body), (
            "%s does not put the resource down, so it can outlive the action:\n%s" % (fn, body))


@needs_node
def test_the_board_never_claims_a_duty_and_a_tithe_at_once(tmpl):
    """TAKING A TITHE CHOOSES NO DUTY, so no duty may wear the chosen rim while one is taken.

    Nobody moves when you take a tithe, so it does not matter which duty was selected -- and the
    board sat with the gold rim on whichever tile you were last looking at while the Take Tithe
    box was also lit, which is two answers to a question that has one. The cards above stay up,
    because they are what you are BROWSING; the rim is what says CHOSEN.

    THIS GUARD USED TO READ render()'s TEXT AND THAT IS WHY IT MISSED THE SEQUEL. It asked that
    `var chosen = ...` mentioned the tithe, which was true of render() for as long as render()
    was the only place the rim was drawn -- and drawGrid()'s post-rebuild sweep was drawing it
    too, from `d.slug === S.duty` alone. The rule now has one name and this asks what it ANSWERS;
    test_both_places_that_draw_the_rim_ask_the_one_rule holds that both sites ask it.

    THE CASE IN THE MIDDLE IS NOT A MISTAKE. A duty with no action chosen yet still wears the
    rim -- pickDuty puts the duty down and clears the slot -- so a null slot is chosen and only
    the tithe is not. A guard that demanded a slot as well would forbid the state the board is in
    for the whole moment between picking a duty and picking its action.

    Falsify: drop the `S.slot !== TITHE_SLOT` half of dutyChosen and the third case lights.
    """
    prelude = "\n".join([
        "var TITHE_SLOT = %s;" % _decl(tmpl, "TITHE_SLOT"),
        "var S = {duty: null, slot: null};",
        _function(tmpl, "dutyChosen"),
        "function at(duty, slot){ S.duty = duty; S.slot = slot; return dutyChosen('clerical'); }",
    ])
    got = _node(prelude, "[at('clerical', 'actionA'), at('clerical', null),"
                         " at('clerical', TITHE_SLOT), at('produce', 'actionA'),"
                         " at('produce', TITHE_SLOT)]")
    assert got == [True, True, False, False, False], (
        "dutyChosen answered %s for: clerical+action, clerical+nothing, clerical+tithe, "
        "another duty+action, another duty+tithe" % got)


def test_the_confirm_waits_for_the_resource(tmpl):
    """A TITHE IS TWO HALVES AND THE CONFIRM MAY NOT APPEAR ON THE FIRST.

    `S.slot` alone used to be the whole question, because every answer it could hold was
    complete. A tithe is not: offering the confirm the moment the box is pressed lets you commit
    a choice you have not made. A pool of one answers itself, so this is never in the way of the
    common case.

    Falsify: gate the confirm on S.slot alone again.
    """
    body = _code(_function(tmpl, "render"))
    m = re.search(r"var ready = (.*?);", body)
    assert m, "render no longer works out whether there is something to commit:\n%s" % body[-900:]
    cond = m.group(1)
    assert "S.slot" in cond and "S.tithe" in cond and "TITHE_SLOT" in cond, (
        "the confirm no longer waits for a resource when a tithe is being taken: %s" % cond)
    assert re.search(r'toggle\("off", !ready\)', body), (
        "the confirm is not drawn from that answer")


def test_a_change_of_seat_reconciles_a_tithe_already_chosen(tmpl):
    """THE POOL BELONGS TO THE SEAT, so changing seat can take the chosen resource away.

    Left alone the board sat with the Take Tithe box lit and NOTHING IN IT, offering a confirm
    for a move the new seat cannot make. A resource no longer in the pool falls back to whatever
    the pool answers by itself; an empty pool puts the whole choice down.

    AND IT IS NOT DONE IN render(). render is called from everywhere, and a render that quietly
    rewrites the state is one nobody can reason about -- so the reconciliation happens where the
    seat changes, which is the only place it can be needed.

    Falsify: drop the call from the seat handler, or move it inside render.
    """
    body = _code(_function(tmpl, "reconcileTithe"))
    assert "tithePool(S.seat)" in body, "the reconciliation no longer asks the new seat's pool"
    assert "S.slot = null" in body, "an empty pool no longer puts the choice down:\n%s" % body
    assert "onlyTithe()" in body, "a shrunken pool no longer re-answers itself:\n%s" % body
    # THROUGH reconcile(), WHICH IS THE PAIR. The seat picker called reconcileTithe alone while
    # the tithe was the only half there was; the duty half arrived with eligibility and was
    # forgotten at exactly this call site in the first draft. So what is pinned is that the seat
    # change reconciles BOTH, by whatever name the pair goes under -- parsed, not matched, so the
    # guard keeps meaning this when the pair grows a third member.
    wire = _code(_function(tmpl, "wireGrid"))
    assert re.search(r"S\.seat = seat\.value;\s*reconcile\(\);", wire), (
        "the seat picker does not reconcile:\n%s" % wire[-400:])
    pair = _code(_function(tmpl, "reconcile"))
    assert "reconcileTithe()" in pair and "reconcileDuty()" in pair, (
        "reconcile() no longer does both halves: %s" % pair)
    assert "reconcileTithe" not in _code(_function(tmpl, "render")), (
        "render rewrites the state, so what it draws depends on how often it has run")


@needs_node
def test_a_seat_may_act_exactly_where_its_figures_stand(pool):
    """BOTH MOVES IN ACTION SELECTION NEED AN ACOLYTE ON A DUTY TILE, so this is the rule.

    Driven against the real demo occupancy and against four isolated cases, because the demo
    state is generous: p3 stands on seven of the eight duties, so a rule that answered "all" and
    a rule that answered correctly look nearly identical from p3's seat alone.

    Falsify: return every duty, or read S.duty instead of the occupancy.
    """
    seats = _v2_seats()
    for seat, got in pool["can"].items():
        want = sorted(s for s, on in seats.items() if seat in on)
        assert sorted(got) == want, (
            "%s stands on %s and the board offers %s" % (seat, want, sorted(got)))

    # A SEAT STANDING NOWHERE MAY ACT NOWHERE, which is the state the engine cannot produce --
    # sowing guarantees a figure on at least one tile. Kept because it is the cheapest way to
    # find a rule that quietly divides by the number of your own figures, and driven by a seat
    # standing on nothing rather than by whichever seat the demo deal happens to leave out.
    assert pool["canIso"]["nowhere"] == [], pool["canIso"]["nowhere"]
    assert pool["canIso"]["taxOnly"] == ["taxation"], pool["canIso"]["taxOnly"]


@needs_node
def test_being_able_to_act_is_wider_than_feeding_the_box(pool):
    """TAXATION IS THE WHOLE OF THIS TEST, and it is why eligibility is not the pool.

    It is the one duty with no resource, so figures there make its actions available and add
    nothing to the Take Tithe box. "You may act here" is a SUPERSET of "this feeds the box" -- so
    a board that built the pool first and reused it as eligibility would have quietly made
    Taxation unplayable, which is the kind of mistake that reads as a missing feature rather than
    as a bug.

    Falsify: define eligibility as `tithePool(seat).indexOf(...) >= 0`, or give Taxation a key.
    """
    assert pool["canIso"]["taxOnly"] == ["taxation"] and pool["iso"]["taxOnly"] == [], (
        "a figure on Taxation alone: may act on %s, offers %s"
        % (pool["canIso"]["taxOnly"], pool["iso"]["taxOnly"]))
    for seat, can in pool["can"].items():
        got = pool["pools"][seat]
        assert not got or can, "%s has a pool %s with nowhere to act" % (seat, got)


@needs_node
def test_nothing_is_refused_outside_action_selection(pool):
    """ELIGIBILITY BELONGS TO ONE PHASE, and the other two are labels with nothing behind them.

    In Sowing these same tiles mean "where may I walk", which is a different question with a
    different answer -- marking them by where you ALREADY stand would answer the wrong one. So
    outside Action Selection every duty is open, which is the board's behaviour up to now.

    AND THE OFF STATE IS MEASURED. A broken gate -- everything open, always -- looks exactly like
    a board that has no rule, so reading only the on state would agree with it.

    Falsify: drop the phase test from eligible(), or compare against a typed "action".
    """
    want = sorted(d for d in _v2_seats())
    for seat, got in pool["canOff"].items():
        assert sorted(got) == want, (
            "outside Action Selection %s is refused %s"
            % (seat, sorted(set(want) - set(got))))
    # AND THE DIFFERENCE IS SHOWN WITH ONE FIGURE, because the demo deal can no longer show it:
    # every seat stands on every tile now, so "what this seat may act on" is the whole ring
    # whether the phase is live or not, and a gate that had stopped working would produce
    # exactly that. A seat standing on Taxation alone may act on Taxation while the phase is
    # live and on everything outside it -- which only the gate can account for.
    assert pool["canIso"]["taxOnly"] == ["taxation"], pool["canIso"]["taxOnly"]
    assert sorted(pool["canIsoOff"]["taxOnly"]) == want, (
        "outside Action Selection a seat standing on one tile is refused %s"
        % sorted(set(want) - set(pool["canIsoOff"]["taxOnly"])))
    assert not pool["canIso"]["nowhere"] and sorted(pool["canIsoOff"]["nowhere"]) == want, (
        "the gate makes no difference to a seat standing nowhere, so it is not a gate")


def test_the_pool_and_the_tiles_ask_one_question(tmpl):
    """ONE WALK OF THE OCCUPANCY, TWO READERS, because the disagreement would be ON SCREEN.

    Written twice, the box could offer a resource from a tile the board had just refused to let
    you act on. Both go through standsOn, and neither re-implements it.

    Falsify: inline `S.occupancy[...].indexOf(seat) >= 0` back into either one.
    """
    for name in ("tithePool", "eligible", "lightTithe"):
        body = _code(_function(tmpl, name))
        assert "standsOn(" in body, "%s no longer asks the standing rule:\n%s" % (name, body)
        assert "indexOf(seat)" not in body and "indexOf(S.seat)" not in body, (
            "%s walks the occupancy itself, so there are two answers again:\n%s" % (name, body))
    rule = _code(_function(tmpl, "standsOn"))
    assert "S.occupancy[slug]" in rule and "indexOf(seat)" in rule, (
        "the standing rule no longer reads the occupancy: %s" % rule)


def test_a_refused_press_changes_nothing_and_makes_no_sound(tmpl):
    """A PRESS YOU CANNOT MAKE MUST NOT COST YOU THE ONE YOU HAD.

    Three routes reach a choice -- the rectangle, the mark, and the card above -- and each
    refuses BEFORE it touches the state or the sound. A refusal that also cleared the selection
    would be the worst of both: you learn you cannot do this, and you have to redo the thing you
    could. A refusal that played `select` would sound exactly like being accepted.

    THE CARD ASKS A DIFFERENT QUESTION, and that is deliberate. pickDuty and pickAction ask about
    the duty in the press; select() has no duty in the press at all, so it asks about S.duty --
    which a change of SEAT can make ineligible with nothing clicked.

    Falsify: move any guard below its sfx call, or give select() the others' test.
    """
    for name, asked in (("pickDuty", "slug"), ("pickAction", "duty"), ("select", "S.duty")):
        body = _code(_function(tmpl, name))
        m = re.search(r"if \(!eligible\((%s)\)\) return explain\(" % re.escape(asked), body)
        assert m, "%s does not refuse an ineligible %s:\n%s" % (name, asked, body)
        sound = body.find("sfx(")
        assert sound < 0 or m.start() < sound, (
            "%s refuses after it has already sounded like a choice:\n%s" % (name, body))

    told = _code(_function(tmpl, "explain"))
    assert "S." not in told.replace("setStatus", ""), (
        "a refusal writes to the state, so it costs you something:\n%s" % told)
    assert "sfx" not in told, "a refusal makes a sound:\n%s" % told


def test_the_refusal_says_what_the_duty_does_as_well_as_why(tmpl):
    """TWO QUESTIONS AT ONCE: what is this, and why can I not press it.

    The first is the one that makes a tile worth reading on a turn you cannot take it -- you are
    looking at Ordination BECAUSE you are deciding where to walk next -- so the reason is JOINED
    onto the labels rather than put in their place.

    AND THE WORDING IS NOT IN THE PAGE. It comes from geometry with the phase lines, which is
    where the status line's own sentences live; typed here it would be the fault duty_text.json
    was created to end.

    Falsify: return the reason instead of appending it, or type the clause into the template.
    """
    body = _code(_function(tmpl, "lineFor"))
    assert body.count("say(") == 2, (
        "both the tile line and the mark line no longer carry the reason:\n%s" % body)
    assert "reasonFor(" in body, "the reason is no longer asked for:\n%s" % body

    why = _code(_function(tmpl, "reasonFor"))
    assert "GEO.lines.noAcolytes" in why, "the clause is not read from geometry: %s" % why
    assert "eligible(" in why, "the clause is not gated on eligibility: %s" % why

    join = _code(_function(tmpl, "say"))
    assert "body +" in join, "the reason replaces the labels instead of joining them: %s" % join

    page = _code(_rule_free(tmpl))
    assert "no Acolytes present" not in page and "no Tithe to take" not in page, (
        "the refusal wording is typed into the page as well as published by geometry")


def test_the_refusal_wording_is_published_by_geometry(geo):
    """THE STATUS LINE'S OWN SENTENCES LIVE WITH THE PHASES, and reach the page as data.

    duty_text.json holds what the game's things are CALLED and is read by both boards and the
    icon lab; these are the board's chrome, which no card carries. PHASES has held exactly that
    kind of string in geometry since there were phases, so one clause does not start a second
    home -- but it does have to be EXPORTED, or the page falls back to an empty string and the
    refusal is silent.

    Falsify: drop `lines` from as_dict(), or empty a clause.
    """
    lines = geo.as_dict().get("lines")
    assert lines, "geometry publishes no status lines, so the page cannot say why"
    # EVERY LINE IN THE TABLE, not a list of the ones that existed when this was written. A new
    # sentence added to LINES and left out of here is a sentence nothing checks, which is the
    # same shape of hole as a walk that names its file types.
    assert set(lines) >= {"noAcolytes", "noTithe", "titheResource"}, sorted(lines)
    for key, text in sorted(lines.items()):
        assert text, "`%s` is missing or empty: %s" % (key, lines)
        assert text == text.strip(), "`%s` is padded: %r" % (key, text)
    assert lines == geo.LINES, "the export is not the table"

    # AND THE PHASE NAMES THE CONDITION. The line a player reads while deciding has to say what
    # makes a duty choosable, or seven unpressable tiles have nothing explaining them.
    action = [p for p in geo.as_dict()["phases"] if p["key"] == geo.LIVE_PHASE]
    assert len(action) == 1, geo.as_dict()["phases"]
    assert "Acolytes" in action[0]["line"], (
        "the live phase's line does not say what makes a duty choosable: %r" % action[0]["line"])


def test_the_city_is_lit_in_sowing_and_in_no_other_phase(gen, tmpl):
    """THE TWO FILMS ARE NOT ASKING THE SAME QUESTION OF THE SAME PLACES.

    It looked at first as though one set wore two clips. It does not. Action Selection marks the
    tiles whose ACTIONS you may take, and the City has none -- it is not a duty, takes no pointer
    and carries no icons. Sowing marks where your people ARE, and the City is the fullest place
    on the board and the one Acolytes walk out of. So the rule is "where this seat stands" in
    both, and what differs is WHERE that question is asked.

    THE CITY GETS NO ELEMENT IT COULD NOT SHOW. filmPhases hands it only the phases that name
    it, and buildFilms builds from that -- so there is no Action Selection video sitting paused
    in the middle of the board forever, which is the kind of thing that is invisible until
    somebody counts decoders.

    AND IT CANNOT RUN IN STEP WITH A DUTY. The City is not on the ring, so it has no clock angle
    and no place in the alternating walk that gives the eight their offsets. It takes the
    smallest second the ring leaves free -- derived, so changing the steps moves the City with
    them instead of silently landing it on top of a duty. It is the largest rectangle with the
    most figures in it, so a coincidence there would be the most visible one available.

    Falsify: light the City in Action Selection, build it a film it cannot wear, or give it a
    start time a duty already has.
    """
    assert gen.FILM_CITY, "no phase lights the City, so it is dark in all of them"
    assert set(gen.FILM_CITY) <= set(gen.FILM_STEMS), (
        "the City is named for a phase that has no film: %s"
        % (set(gen.FILM_CITY) - set(gen.FILM_STEMS)))
    assert "action" not in gen.FILM_CITY, (
        "the City is lit in Action Selection, where it has no action to take")

    ring = gen.open_offsets()
    city = gen.city_offset()
    assert city not in set(ring.values()), (
        "the City starts at %ds, which is already %s's" % (city, [k for k, v in ring.items()
                                                                 if v == city]))
    assert 0 <= city < gen.open_span(), "the City starts outside the loop: %s" % city
    assert city == min(set(range(gen.open_span())) - set(ring.values())), (
        "the City's start is not the first second the ring leaves free, so it is chosen rather "
        "than derived: %s" % city)

    out, _notes = gen.bundled_films()
    assert out["offsets"][gen.CITY_SLUG] == city, "the City's start is not published"
    assert out["city"] == [p for p in gen.FILM_CITY if p in gen.FILM_STEMS], out["city"]

    # AND THE PAGE ASKS, RATHER THAN KNOWING. A list of phases typed into the template would be
    # a second copy of FILM_CITY, and the two would part company the first time one was edited.
    body = _code(_function(tmpl, "filmPhases"))
    assert "FILMS.city" in body, (
        "the page decides for itself which phases light the City:\n%s" % body)
    assert "CITY_SLOT" in body, "the City is not what the exception is about:\n%s" % body


def test_a_resource_names_itself_wherever_it_is_drawn(tmpl):
    """THE SAME QUESTION IN TWO PLACES GETS THE SAME ANSWER.

    The four resources are drawn twice over -- as a label beside each duty's icons, and as a slot
    in the Take Tithe box -- and a player pointing at either is asking the same thing. So both
    carry `hoverTithe` and both reach one line; two routes answering separately is how a board
    ends up knowing a name in one place and not the other.

    THE LINE IS HALF CHROME AND HALF DATA, deliberately. `titheResource` is the board's own label
    and lives with the phase lines in geometry; the NAME is the icon lab's own, by way of the
    generator -- which is why it reads "Silver coin" rather than "silver", and why renaming a
    resource in the lab renames it here with nobody remembering to.

    AND A LABEL IS ASKED BEFORE THE DUTY IT SITS ON. A tile's label carries both: the resource it
    names and the duty it belongs to. Asked the other way round it would announce the duty's two
    actions -- true of the tile, and not of the thing under the pointer. The duty travels anyway,
    so the face still lights.

    Falsify: type the label into the page, drop either route, or read the duty first.
    """
    for where, block in (("the tile's label", _tithe_block(tmpl)),
                         ("the box's slot", _code(_function(tmpl, "drawTithe")))):
        assert "hoverTithe" in block, "%s does not name itself on hover:\n%s" % (where, block)

    line = _code(_function(tmpl, "titheLine"))
    assert "GEO.lines.titheResource" in line, (
        "the label is not read from geometry, so it is typed into the page: %s" % line)
    assert "titheName(key)" in line, (
        "the resource's own name is not used, so the line cannot follow a rename: %s" % line)

    says = _code(_function(tmpl, "setStatus"))
    assert "titheLine(hovered.tithe)" in says, (
        "the status line has no branch for a hovered resource:\n%s" % says)

    seen = _code(_function(tmpl, "hoverDataOf"))
    assert "d.hoverTithe" in seen, (
        "the delegation cannot see a resource, so neither route ever fires:\n%s" % seen)

    body = _code(tmpl)
    i, j = body.index("if (d.hoverTithe)"), body.index("hover(d.hoverDuty || S.duty")
    assert i < j, "the duty is asked before the resource, so a label announces the tile instead"
    assert "hoverTithe(d.hoverTithe, d.hoverDuty)" in body, (
        "the duty does not travel with the resource, so the face goes dark under the pointer")


def test_a_chosen_action_does_not_survive_losing_the_right_to_it(tmpl):
    """TWO THINGS CHANGE UNDERNEATH YOU, and both can take away the action you had chosen.

    Picking another seat and moving to Action Selection are the same hole one object apart: the
    board kept the commit up over a move the new state refuses. That is exactly what
    reconcileTithe was written for, so the duty half is done the same way and the two are called
    together by one name.

    THE DUTY STAYS; ONLY THE CHOICE GOES. S.duty is what you are LOOKING at and the two cards
    above belong to it, so clearing it would empty the board's largest objects to say something
    about a small one.

    Falsify: clear S.duty as well, choose some other duty in its place, or call the pair from one
    of its two sites only.
    """
    body = _code(_function(tmpl, "reconcileDuty"))
    assert "eligible(S.duty)" in body, "the reconciliation does not ask the new state: %s" % body
    assert "S.slot = null" in body, "the chosen action is not put down: %s" % body
    assert "S.duty =" not in body, "the duty being looked at is cleared as well: %s" % body
    assert "TITHE_SLOT" in body, (
        "a tithe is reconciled as though it were an action: %s" % body)

    phases = _code(_function(tmpl, "drawPhases"))
    assert "reconcile()" in phases, "a change of phase does not reconcile:\n%s" % phases
    assert "render()" in phases, "a change of phase does not redraw, so the cue is stale"


def test_the_open_tile_is_lit_and_nothing_is_dimmed(tmpl):
    """ADDITIVE, AND ON THE LARGEST THING A DUTY HAS.

    The open set is the MINORITY -- your figures are on one or two tiles of eight -- so dimming
    would change six or seven objects to say something about two, on a palette with no room below
    the one the board is already at, and would take the board away from the three players who are
    not taking this turn.

    ON THE RECTANGLE, WHICH IS THE SECOND PLACE THIS LIVED. It was the icon frame's 1px edge
    first: a real step in colour over about forty pixels of a 1400-wide board, which measured
    fine and could not be seen. A cue that has to be found at a glance across eight tiles needs
    AREA. That is the finding worth keeping, and it is why this guard pins the carrier.

    Falsify: move the cue back onto the frame, or dim the shut tiles instead.
    """
    film = _rule(tmpl, ".smoke")
    assert film.get("object-fit") == "cover", (
        "the clip is not scaled to fill the rectangle: %s" % film)
    assert film.get("object-position") == "bottom", (
        "the plume is not anchored to the line the Acolytes stand on, so a short tile crops the "
        "wrong end of it: %s" % film)
    assert film.get("display") == "none" and film.get("pointer-events") == "none", (
        "the clip shows on every tile, or takes clicks meant for one: %s" % film)
    assert _rule(tmpl, ".smoke.on").get("display") == "block", (
        "a chosen film is never shown")

    # NOT FOUR NAMED SELECTORS, BUT EVERY RULE THAT REACHES A RECTANGLE. Written as a list of
    # selectors this guard slept through `.dcell:not(.eligible){opacity:.6}` -- a dimming rule
    # that is obviously the thing being forbidden and is not any of the four names it was
    # looking under. A mutation found it; the fix is to ask the question of the whole stylesheet.
    body = _rule_free(tmpl)
    sheet = body.split("</style>")[0]
    dim = sorted(sel.strip() for sel, decls in re.findall(r"([^{}]+)\{([^}]*)\}", sheet)
                 if re.search(r"\bdcell\b|\bsmoke\b", sel)
                 and re.search(r"(^|;)\s*(opacity|filter)\s*:", decls))
    assert not dim, (
        "a rectangle is dimmed by %s, so a shut tile wears a disabled look" % ", ".join(dim))
    assert ".iplate.eligible" not in body, (
        "the frame carries the cue as well, so the board says one thing in two places")
    assert "--open-wash" not in _code(body).replace("NO --open-wash", ""), (
        "the gold wash is still declared beside the film, so there are two cues")


def test_the_clip_is_lightened_and_nothing_above_it_isolates(tmpl):
    """THE CLIP HAS NO ALPHA AND NEEDS NONE, AND THE BLEND IS WHAT STANDS IN FOR ONE.

    `screen` WAS WRONG AND LOOKED RIGHT, which is why this is pinned. Screening black is a no-op
    for TRUE black; the clip is drawn on rgb(4, 6, 8), so screen left four levels standing and
    every open tile wore a cool dark rectangle. Matching the board to the clip's own ground made
    it WORSE -- screen combines, so (4,6,8) over (4,6,8) is (8,12,16), the same gap again.

    `lighten` takes the greater of the two, so a clip pixel at or below the board's ground is
    exactly the board's ground and only what is brighter shows. It works only in company with
    --film-black; the two together are the mechanism and neither half does anything alone, which
    is why the guard on that colour and this one both exist.

    AND NOTHING ABOVE IT MAY ISOLATE. Inside an isolated group the backdrop is transparent,
    `lighten` returns the source unchanged, and the clip's ground paints a solid rectangle over
    the board -- the cue becomes a hole. `.dcell` must stay a non-stacking context, which means
    no isolation and no z-index on the way down to it.

    Falsify: go back to screen, or isolate `.dcell` or `.smoke`.
    """
    film = _rule(tmpl, ".smoke")
    assert film.get("mix-blend-mode") == "lighten", (
        "the clip's ground is not hidden by the blend, so it draws a rectangle: %s" % film)
    for sel in (".dcell", ".smoke"):
        rule = _rule(tmpl, sel)
        assert "isolation" not in rule, (
            "%s isolates, so screen returns the clip unchanged and its black becomes a hole" % sel)
        assert "z-index" not in rule, (
            "%s takes a z-index, which makes it a stacking context and isolates the blend" % sel)


def test_the_board_is_the_same_black_the_clip_is_drawn_on(tmpl):
    """`screen` ONLY MAKES TRUE BLACK DISAPPEAR, AND THE CLIP'S BLACK IS NOT TRUE BLACK.

    It renders at rgb(4, 6, 8) -- measured off the page, steady to within one level across the
    loop -- so screened over a pure black board that pedestal survived untouched and every open
    tile wore a cool dark rectangle. Not the border, which is transparent in the view the board
    opens in: the clip's own ground, showing wherever the board's was darker.

    THE BOARD MOVED TO MEET THE FILM. Crushing four levels out of the clip instead would be a
    filter running on every frame of eight videos, and it would take the smoke's own darkest
    values with it; the canvas is one declaration and costs nothing.

    AND THE TWO ARE HELD TOGETHER, which is the point of this guard rather than the colour. The
    pedestal is a fact about a FILE: a clip drawn on a different black needs this declaration to
    move with it. So the number lives in the clip's own attribution record and the stylesheet is
    checked against it -- neither is the other's copy, and a new clip that forgets this fails
    here rather than looking slightly wrong to somebody eventually.

    Falsify: put the board back to #000, or change one of the two without the other.
    """
    root = _rule(tmpl, ":root")
    named = (root.get("--film-black") or "").strip().lstrip("#")
    assert len(named) == 6, "the clip's black is not a name: %r" % root.get("--film-black")
    css = tuple(int(named[i:i + 2], 16) for i in (0, 2, 4))

    board = _rule(tmpl, "#board")
    assert board.get("background") == "var(--film-black)", (
        "the canvas is not the clip's black, so a lit tile draws a rectangle: %s" % board)

    # EVERY CLIP, NOT THE CLIP. There is more than one film now and they share one canvas, so
    # they have to share one ground: a clip drawn on a different black cannot be absorbed by the
    # same --film-black and would wear a rectangle in its own phase only, which is the kind of
    # fault that gets noticed late because the board looks right in whichever phase you are in.
    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))["files"]
    clips = sorted(k for k in rec if k.startswith("effects/") and k.endswith(".mp4"))
    assert clips, "no clip is recorded, so nothing says what black the canvas is matching"
    for clip in clips:
        m = re.search(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", rec[clip]["measured"])
        assert m, "%s does not say what black it is drawn on" % clip
        assert css == tuple(int(g) for g in m.groups()), (
            "the canvas is %s and %s is recorded as being drawn on %s"
            % (css, clip, m.groups()))


def test_the_clip_is_an_element_so_bare_cannot_clear_it(tmpl):
    """THE CUE STOPPED BEING A BACKGROUND, AND TWO TRAPS WENT WITH IT.

    The gold wash this replaces had to be declared after `.dcell.bare`, because bare sets
    `background` and is the view the board opens in; and it had to carry `no-repeat`, because a
    background's origin is the padding box while its clip is the border box, so the strip above
    the padding box repeated the image and drew its strong end as a hard line along every open
    tile's top edge. A child element has neither problem, and this guard exists so that nobody
    re-introduces them by moving the cue back into `background`.

    Falsify: light an open tile with a background again.
    """
    body = _rule_free(tmpl)
    assert ".dcell.eligible{" not in body and ".dcell.yours{" not in body, (
        "a marked tile is lit by a rule on the cell itself again, which `bare` can clear")
    shown = _rule(tmpl, ".smoke.on")
    assert set(shown) == {"display"}, (
        "the shown state says more than which element to show: %s" % shown)
    assert "background" not in _code(_function(tmpl, "markStanding")), (
        "the cue is being painted from script, where the stylesheet cannot be read")


def test_the_box_says_it_in_words_and_the_tiles_say_it_in_light(tmpl):
    """ONE STATEMENT PER OBJECT, IN WHATEVER LANGUAGE THAT OBJECT HAS.

    The Take Tithe box wore the same wash for a round and it was taken back out. A box with
    nothing in it already writes "no tithe available" across its own middle, so the light was the
    board saying one thing twice on one object. The rectangles keep it because they have nowhere
    to write a sentence: a duty tile is figures and icons and no room.

    AND THE REFUSAL IS NOT WHAT WENT. A press on an empty box still answers out loud; what was
    removed is the resting cue, not the reply.

    Falsify: light the box again, leave the empty box with nothing written in it, or make the
    press silent.
    """
    body = _rule_free(tmpl)
    assert ".panel.eligible" not in body, (
        "the box is lit again, so it says in light what it already says in words")
    assert "NO .panel.eligible RULE" in tmpl, (
        "the reason the box is not lit is no longer written down, so it will come back")
    sweep = _code(_function(tmpl, "markStanding"))
    assert '"tithe"' not in sweep and "tbox" not in sweep, (
        "the box is still given a class nothing draws, which is a write with no reader:\n%s"
        % sweep)

    empty = _code(_function(tmpl, "drawTithe"))
    assert "no tithe available" in empty, (
        "the empty box no longer writes what is wrong with it:\n%s" % empty[-700:])

    assert _rule(tmpl, ".art.sel, .panel.sel").get("outline-color") == "var(--line)", (
        "the chosen box no longer takes the gold from --line. The outline itself is declared on "
        "the base rules now, because the row wears three states rather than one; see "
        "test_the_action_row_wears_the_wheels_three_states.")

    take = _code(_function(tmpl, "takeTithe"))
    assert "explainWhy(GEO.lines.noTithe)" in take, (
        "a press on an empty box is silent again:\n%s" % take)
    assert re.search(r"if \(!tithePool\(S\.seat\)\.length\) return explainWhy", take), (
        "the box is refused somewhere other than on the pool being empty:\n%s" % take)


def test_the_phase_picks_the_film_and_the_occupancy_picks_the_tiles(tmpl):
    """TWO QUESTIONS, AND THEY MUST NOT BE ANSWERED BY ONE RULE.

    WHICH TILES are marked is where this seat's Acolytes stand -- the same set in Action
    Selection and in Sowing, because that set is what both films are about. WHICH FILM they wear
    is the phase.

    IT MUST NOT ASK eligible(). That is the REFUSAL rule, and it answers `true` for every duty
    outside Action Selection so that nothing is refused in a phase with no rules behind it -- so
    a sweep built on it would light all eight tiles during Sowing. The two questions shared a
    name until Sowing got a film, and this guard is what stops them sharing one again.

    A PHASE WITH NO FILM MARKS NOTHING, which is the gate: `ready` has no entry in FILMS.byPhase
    and needs no list of its own saying so.

    ONE SWEEP, TWO CALLERS. render() sets it because it is state; drawGrid() sets it because the
    sliders throw these nine elements away and build them again, and a rebuild that left it to
    the next render would drop the cue under the pointer on every slider move.

    Falsify: mark from eligible(), light a tile in the wrong phase, or set the class in only one
    of the two callers.
    """
    body = _code(_function(tmpl, "markStanding"))
    assert "standsOn(S.seat, slug)" in body, (
        "the marked places are not the ones this seat stands on:\n%s" % body)
    # AND THE CITY IS ONE OF THE PLACES WALKED. It is not a duty, so GEO.duties alone leaves it
    # out -- which is correct in Action Selection, where it has no actions to take, and wrong in
    # Sowing, where it is the fullest place on the board and the one Acolytes walk out of.
    assert "CITY_SLOT" in body, (
        "the City is not among the places the sweep walks, so it can never be marked:\n%s"
        % body)
    assert "filmPhases(slug)" in body, (
        "the sweep does not ask which films a place may wear, so the City would be handed one "
        "it cannot show:\n%s" % body)
    assert "eligible(" not in body, (
        "the sweep asks the refusal rule, which is true of every duty outside Action Selection "
        "and would light all eight during Sowing:\n%s" % body)
    assert re.search(r"phase === S\.phase", body), (
        "the film is not chosen by the phase:\n%s" % body)
    assert re.search(r'toggle\("on",\s*on\)', body), (
        "the chosen film is not shown from that answer:\n%s" % body)
    # THE BUNDLE IS READ ONE FUNCTION DOWN, which is where the question moved when the City
    # arrived: the sweep asks filmPhases, and filmPhases is what consults FILMS. Pinned where it
    # lives rather than where it used to, so this keeps meaning "no typed list of phases".
    phases = _code(_function(tmpl, "filmPhases"))
    assert "FILMS.byPhase" in phases, (
        "the phases are not taken from the bundle, so a phase with no film is not simply a "
        "phase with no film:\n%s" % phases)

    for caller in ("render", "drawGrid"):
        assert "markStanding()" in _code(_function(tmpl, caller)), (
            "%s does not set the cue, so it is stale after %s runs"
            % (caller, "a state change" if caller == "render" else "a rebuild"))


def test_every_phase_with_a_film_has_one_that_is_recorded_and_its_own(gen):
    """A FILM PER PHASE, EACH A DIFFERENT FILM, EACH THE SAME LENGTH.

    THE SAME LENGTH because they share one set of offsets and one clock: a clip of some other
    length would be in step for one cycle and adrift from then on. THE SAME GROUND because they
    share one canvas -- see the guard on --film-black. A DIFFERENT FILM because the phase is what
    the clip is there to say, and two that looked alike would leave the phase carried by nothing
    but the word in the bar.

    Falsify: point two phases at one clip, or add a phase to the map with no file behind it.
    """
    geo = _load("geometry")
    keys = {p["key"] for p in geo.as_dict()["phases"]}
    assert set(gen.FILM_STEMS) <= keys, (
        "a film is keyed by something that is not a phase: %s"
        % (set(gen.FILM_STEMS) - keys))
    assert len(set(gen.FILM_STEMS.values())) == len(gen.FILM_STEMS), (
        "two phases are pointed at one clip: %s" % gen.FILM_STEMS)

    out, _notes = gen.bundled_films()
    assert set(out["byPhase"]) == set(gen.FILM_STEMS), (
        "a phase in the map shipped no clip: %s" % sorted(
            set(gen.FILM_STEMS) - set(out["byPhase"])))
    assert len(set(out["byPhase"].values())) == len(out["byPhase"]), (
        "two phases shipped the same bytes, so the films cannot tell them apart")

    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))["files"]
    for phase, stem in gen.FILM_STEMS.items():
        clip = sorted(gen.OPEN_DIR.glob("%s_v*.mp4" % stem))[-1]
        rel = "effects/%s" % clip.name
        assert rel in rec, "%s ships the unrecorded %s" % (phase, rel)
        assert hashlib.sha256(clip.read_bytes()).hexdigest() == rec[rel]["sha256"], (
            "%s is not the file that was recorded" % rel)
        assert abs(gen._mp4_seconds(clip) - gen.open_span()) < 0.05, (
            "%s does not close the loop the stagger divides" % rel)


def test_the_stagger_is_the_sequence_that_was_asked_for(gen):
    """EIGHT START TIMES ROUND THE RING: 0, 1, 3, 4, 6, 7, 9, 10 SECONDS, CLOCKWISE FROM NORTH.

    The generator derives them by alternating +1 and +2 rather than listing them, because eight
    numbers that look arbitrary are exactly what gets copied wrong -- but a derivation can drift
    from the intent silently, which a list cannot. So the rule is in the code and the sequence it
    has to produce is here, and neither is the other's copy.

    Falsify: change the steps, their order, or where the ring starts.
    """
    geo = _load("geometry")
    off = gen.open_offsets()
    assert [off[slug] for slug, _n, _d in geo.DUTIES] == [0, 1, 3, 4, 6, 7, 9, 10], (
        "the stagger is not the sequence asked for: %s" % off)
    assert off[geo.DUTIES[0][0]] == 0, "north does not start at the beginning of the clip"
    assert len(set(off.values())) == len(geo.DUTIES), (
        "two duties share a start time, which is the one thing the stagger exists to prevent")


def test_the_stagger_closes_the_loop_and_the_build_refuses_when_it_cannot(gen):
    """EIGHT STEPS THAT ADD UP TO THE LENGTH OF THE CLIP, which is what makes it a ring.

    The arrangement repeats exactly and no two tiles ever coincide ONLY while the steps sum to
    the loop. A clip of some other length turns the stagger into a collision, so the build reads
    the duration out of the file's own header and refuses rather than noting it -- a board that
    reports this in a line nobody reads is a board that ships it.

    AND THE DURATION IS READ, NOT ASSUMED. _mp4_seconds walks to `mvhd` and divides; this checks
    it against the clip on disk and against what attribution.json measured, which are three
    independent statements of one fact.

    Falsify: drop the length check, or let the steps sum to something else.
    """
    span = gen.open_span()
    assert span == sum(gen.OPEN_STEPS) * 4, "the ring no longer walks the steps evenly"

    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))["files"]
    for stem in sorted(set(gen.FILM_STEMS.values())):
        found = sorted(gen.OPEN_DIR.glob("%s_v*.mp4" % stem))
        assert found, "there is no %s clip in %s" % (stem, gen.OPEN_DIR)
        clip = found[-1]
        seconds = gen._mp4_seconds(clip)
        assert seconds is not None, "%s: no duration in its header, so nothing is checked" % stem
        assert abs(seconds - span) < 0.05, (
            "%s is %.3f s and the stagger closes a %d s loop" % (clip.name, seconds, span))
        entry = rec["effects/%s" % clip.name]
        assert "%.3f s" % seconds in entry["measured"], (
            "%s measures something other than what the file says: %s"
            % (clip.name, entry["measured"]))

    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    body = src.split("def bundled_films")[1].split("\ndef ")[0]
    assert "raise SystemExit" in body, (
        "a clip of the wrong length is noted rather than refused, so it ships")


def test_the_clip_ships_as_its_own_bytes_and_is_gated_on_the_record(gen):
    """TWO RULES THIS TREE ALREADY HAS, APPLIED TO THE FIRST ASSET THAT IS NOT A PICTURE.

    AN UNRECORDED ASSET IS LEFT OUT AND NAMED. Every picture on this board is gated on
    attribution.json, and a board that quietly inlined an unrecorded clip would be that rule
    broken by the newest kind of file -- which is how the interface sounds went uncredited for
    months, invisible to a walk that knew only about pictures.

    AND NOTHING IS RE-ENCODED ON THE WAY IN. The loop was authored at 48 fps; re-encoding is the
    one thing that would quietly cost that and make the wrap stop being seamless. What the page
    carries is base64 of the file, byte for byte, which this checks against the recorded sha256
    rather than against a promise in a comment.

    Falsify: drop the record check, or pass the clip through any encoder.
    """
    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))
    out, notes = gen.bundled_films()
    assert out["loop"] == gen.open_span()
    # THE RING'S OFFSETS ARE IN THE TABLE UNCHANGED, and the City is added to it rather than
    # replacing it: the page asks for a start time by slug and does not care which kind of
    # place it is holding.
    for slug, when in gen.open_offsets().items():
        assert out["offsets"][slug] == when, "%s moved in the published table" % slug

    for phase, stem in sorted(gen.FILM_STEMS.items()):
        clip = sorted(gen.OPEN_DIR.glob("%s_v*.mp4" % stem))[-1]
        rel = "effects/%s" % clip.name
        assert rel in rec["files"], "%s is shipped with no attribution entry" % rel
        assert hashlib.sha256(clip.read_bytes()).hexdigest() == rec["files"][rel]["sha256"], (
            "%s is not the file that was recorded" % rel)
        uri = out["byPhase"][phase]
        assert uri.startswith("data:video/mp4;base64,"), uri[:40]
        assert base64.b64decode(uri.split(",", 1)[1]) == clip.read_bytes(), (
            "%s carries something other than the clip's own bytes, so the 48 fps is a claim"
            % phase)

    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    body = src.split("def bundled_films")[1].split("\ndef ")[0]
    assert "no attribution entry, left out" in body, (
        "an unrecorded clip is no longer refused, so it can ship uncredited")

    # AND effects/ IS WALKED AT ALL. A folder missing from assetDirs is a folder the verifier
    # never opens, which is the other half of how the sounds stayed invisible.
    assert "effects" in rec["assetDirs"], "effects/ is not a directory the asset walk opens"


def test_the_clip_is_built_for_every_tile_and_played_by_the_state(tmpl):
    """EIGHT ELEMENTS, BUILT ONCE; PLAYED, PAUSED AND SOUGHT FROM THE STATE.

    HIDDEN IS NOT PAUSED. `display:none` stops a video being drawn and does not stop it being
    decoded, so seven invisible films would run for the whole of a turn on a board where one or
    two tiles are open.

    SOUGHT ONLY ON THE WAY IN. render() runs on every click, hover cue and slider nudge, and
    setting currentTime on a playing video is a seek -- done every render it would hold the clip
    on one frame forever.

    MUTED AS AN ATTRIBUTE AS WELL AS A PROPERTY, because that is what a browser reads when it
    decides whether a video may autoplay without a gesture. Set only as a property, the play()
    is refused on a page nobody has clicked yet, which is every page on first paint.

    Falsify: build the elements on demand, leave a shut tile playing, seek on every render, or
    drop the muted attribute.
    """
    build = _code(_function(tmpl, "buildFilms"))
    assert 'el("video", "smoke"' in build, "the films are not built as elements"
    assert 'sm.setAttribute("muted"' in build and "sm.muted = true" in build, (
        "muted is not set both ways, so autoplay is refused before the first gesture")
    for want in ("sm.loop = true", "playsinline", 'sm.id = "smoke-" + phase'):
        assert want in build, "the films are missing %s" % want
    assert "filmPhases(slug)" in build, (
        "the elements are not built from the phases that place may actually wear, so the City "
        "carries a film it can never show")

    # ONE BUILDER FOR THE RING AND THE CITY. Written at both ends they would be two answers the
    # first time one was edited, and the City's copy is the one nobody would remember to edit.
    grid = _code(_function(tmpl, "drawGrid"))
    assert grid.count("buildFilms(cell,") == 2, (
        "the ring and the City do not both go through one builder:\n%s" % grid[-900:])
    assert 'el("video"' not in grid, (
        "drawGrid builds a video of its own again, beside the builder")

    mark = _code(_function(tmpl, "markStanding"))
    assert re.search(r"if \(!on\)\{ if \(!sm\.paused\) sm\.pause\(\); return; \}", mark), (
        "a film that is not showing is hidden without being paused:\n%s" % mark)
    assert re.search(r"if \(!sm\.paused\) return;\s*\n\s*try \{ sm\.currentTime", mark), (
        "a clip is sought on every render, which holds it on one frame:\n%s" % mark)
    assert "filmAt(slug)" in mark, "a clip does not join at its own place in the loop"


def test_a_tile_that_opens_later_joins_the_others_in_step(tmpl):
    """THE STAGGER IS A RELATIONSHIP, AND IT HAS TO SURVIVE THE SEAT PICKER.

    The open set changes several times a turn -- a different seat, a different phase -- so a tile
    starting its own clock when it happens to light up is the normal case, not an edge one. Eight
    clips each begun at a different wall-clock moment are eight unrelated films; what makes this
    one arrangement is that every tile's position is read off ONE clock that started with the
    page.

    Falsify: seek to the bare offset, or restart the clock when a tile opens.
    """
    body = _code(_function(tmpl, "filmAt"))
    assert "FILM_T0" in body, "the position is not measured from the page's own clock"
    assert re.search(r"%\s*span", body), (
        "the position is not wrapped into the loop, so it runs past the end of the clip")
    assert "FILMS.offsets" in body, "the position ignores the duty's own start time"
    assert "Date.now" in _decl(tmpl, "FILM_T0"), (
        "the clock is not started when the page is: %s" % _decl(tmpl, "FILM_T0"))
    assert "FILM_T0 =" not in _code(_function(tmpl, "markStanding")), (
        "the clock is restarted where tiles are marked, so the eight drift apart")
    # AND ONE CLOCK FOR BOTH FILMS. Changing phase swaps which clip a tile shows; a second clock
    # would restart the ring at that moment, which is the one thing the stagger is for.
    assert _code(tmpl).count("FILM_T0 =") == 1, (
        "there is more than one clock, so the films cannot stay in step with each other")


def test_a_token_named_twice_fails_the_build(gen):
    """A TOKEN IN PROSE IS STILL A TOKEN.

    The build already refuses a token left IN the page. This is the same hole from the other
    side, and it is not hypothetical: a comment in the stylesheet mentioned the open bundle's
    token by name while explaining what had replaced the gradient, and the fill duly wrote 130 KB
    of base64 video into a CSS comment. The page still worked. It cost a quarter of a megabyte
    and showed up as nothing but a bigger number in the build line, which is exactly the kind of
    fault that survives for months.

    Falsify: drop the count check from build().
    """
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    body = src.split("def build")[1].split("\ndef ")[0]
    assert re.search(r"page\.count\(t\) > 1", body), (
        "the build no longer notices a token written twice")
    assert "raise SystemExit" in body.split("page.count(t) > 1")[1][:400], (
        "a token written twice is noted rather than refused")

    # AND THE TEMPLATE IS CLEAN TODAY, which is the thing the check is for.
    page = (TOOL / "action_board_v2.html.tmpl").read_text(encoding="utf-8")
    twice = sorted(set(t for t in re.findall(r"__[A-Z_]+__", page) if page.count(t) > 1))
    assert not twice, "the template names %s more than once" % ", ".join(twice)


def _rule_free(text: str) -> str:
    """The template with its CSS comments stripped as well as its JS ones.

    A guard asking whether a string is TYPED into the page reads the prose too, and this file's
    prose quotes the strings it is about -- which is how an earlier guard found "Show Map" in an
    explanation of where "Show Map" comes from and passed on a page that had lost it.
    """
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_a_tiles_resource_is_a_label_and_takes_no_clicks(tmpl):
    """IT WAS CLICKABLE FOR A ROUND AND THE MECHANIC TOOK THAT BACK.

    You do not get Build Roads' stone by clicking Build Roads' stone. You get stone because one
    of YOUR figures stands on a tile that offers it -- and the tile draws its resource whether
    you stand there or not, so a click here would offer something you may have no claim to, and
    would put one decision in two places. The choosing happens in the box, against the pool.

    AND IT IS NOT GREYED, for the reason the controls column already gives about Map and Hire: a
    disabled look promises a state the thing can enter later, and these never become clickable.
    They are drawn at the same rest weight as the duty marks beside them.

    IT DOES ANSWER THE POINTER NOW, AND THAT IS NOT THE SAME AS BEING CHOOSABLE. This guard read
    `pointer-events: none` for a round, on the reasoning that a thing you cannot choose should
    not answer the pointer at all -- and that went one step too far. With no pointer events the
    element receives no mouseover either, so the one question a player has about it, WHICH
    RESOURCE IS THAT, had nowhere to be answered. Pointing at something to find out what it is
    is not choosing it, and the line it puts in the status bar is all it gained.

    Falsify: wire a click to it, let it brighten on hover, or take the pointer away again and
    leave it mute.
    """
    block = _tithe_block(tmpl)
    for bad in ("addEventListener", "dataset.slot", '"seal"', "wireDrop", "pickFile"):
        assert bad not in block, (
            "the tile's resource carries %s, so it is a control again:\n%s" % (bad, block))
    assert "tm.dataset.duty = d.slug" in block, (
        "the label no longer knows its duty, so the box cannot light the tiles feeding a resource")
    rule = _rule(tmpl, ".tmark")
    assert rule.get("pointer-events") == "auto", (
        "the tile's resource takes no pointer events, so it receives no mouseover and cannot "
        "say what it is: %s" % rule)
    assert "cursor" not in rule, (
        "the label sets a cursor, which is how an inert thing starts looking pressable: %s" % rule)
    # COMMENTS STRIPPED BEFORE THE SQUASH. Written against the raw template this fired on the
    # stylesheet's own comment explaining that there is no `.tmark.filled:hover` rule -- a guard
    # failing on the prose that describes the thing it forbids, which is the fourth time this
    # board has managed that. The squash is what makes it easy: it turns a sentence into
    # something that contains every selector it mentions.
    lit = re.sub(r"\s+", "", _code(_rule_free(tmpl)))
    assert ".tmark.filled:hover" not in lit, (
        "a label brightens under the pointer, which is a button that does nothing when pressed")
    assert ".tmark.filled.on" not in lit, "a label can be chosen"
    # IT STILL LIGHTS WHEN THE BOX POINTS AT IT, which is the job it kept.
    assert ".tmark.filled.feeds{filter" in lit, (
        "hovering a resource in the box no longer lights the tiles feeding it")


def test_the_seat_is_demo_state_and_says_so(tmpl):
    """THE FIRST PRIVATE THING ON THIS BOARD, and it has no engine behind it.

    Everything else v2 draws is public -- where every seat stands, what each duty offers, which
    action is being looked at. The pool belongs to ONE player, and v2 has no turn order, so the
    seat is picked in the bar. That is a placeholder and has to be labelled as one, the way
    V2_SEATS already is, or it becomes a fact nobody remembers inventing.

    Falsify: hard-code a seat, or read it from somewhere that is not the picker.
    """
    assert re.search(r'^var V2_SEAT = "p\d";$', tmpl, re.M), (
        "the template no longer opens on a named demo seat")
    i = tmpl.index("var V2_SEAT")
    preamble = tmpl[max(0, i - 1200):i]
    assert "DEMO STATE" in preamble.upper(), (
        "the demo seat is not flagged as demo state, so it reads as a decision")
    assert re.search(r'<select id=rSeat', tmpl), "there is no seat picker in the bar"
    wire = _code(_function(tmpl, "wireGrid"))
    assert "S.seat = seat.value" in wire, "the picker does not set the seat"
    # AND THE POOL READS IT RATHER THAN A PLAYER INDEX.
    assert "tithePool(S.seat)" in _code(tmpl), "nothing asks the pool for the chosen seat"


def test_the_top_line_answers_for_the_tithe_once_it_is_being_taken(tmpl):
    """THE PHASE LINE IS WRITTEN FOR THE COMMON CASE, and the tithe stops being it.

    "Select a Duty Action or take Tithe" is the right line while you are deciding WHICH of those
    to do. The moment you have decided on the tithe it is describing a choice already made and
    saying nothing about the one still open -- which resource.

    TWO STATES, NOT THREE. A line for the empty pool was written and driving the page found it
    unreachable: takeTithe refuses an empty pool, a box with nothing in it has no slots to click,
    and reconcileTithe puts the whole choice down when a change of seat empties it. So the slot
    cannot be the tithe with nothing to take, and a seat with no tithe keeps the phase line
    because it has chosen nothing. This file has carried three conditions that could not fail.

    Falsify: drop the tithe branch, or put the unreachable third state back.
    """
    body = _code(_function(tmpl, "phaseLine"))
    assert "S.slot === TITHE_SLOT" in body, (
        "the top line no longer answers for the tithe:\n%s" % body)
    assert "S.tithe" in body and "titheName(" in body, (
        "the chosen line does not name the resource, so it and the lit mark can disagree:\n%s"
        % body)
    assert "tithePool(" not in body, (
        "the top line asks the pool a question it cannot answer -- the slot cannot be the tithe "
        "with an empty pool:\n%s" % body)
    assert "GEO.phases" in body, "the phase line has stopped being the fallback"


def test_hovering_a_control_puts_its_name_in_the_status_line(tmpl):
    """EVERY OTHER HOVER ON THIS BOARD SPEAKS IN ONE PLACE, and these three did not.

    A duty tile, a mark and an action card all put a line at the top when the pointer crosses
    them. Show Map, Hire a building and Confirm had only a tooltip -- a different register
    altogether: it arrives late, it sits where the pointer is rather than where the board's
    sentence is, and it was the only thing here that worked that way.

    A CONTROL IS NOT A DUTY AND HAS NO SLOT, so it cannot go through the duty route. Passing it
    `S.duty` would announce whichever duty happened to be selected -- the board saying something
    true about the wrong object -- so the mark carries its own name and `hoverMark` is its own
    small state.

    AND IT CLEARS THE WHEEL. The pointer has left the tiles; a tile still lit while the line
    talks about Show Map is two objects claiming the pointer at once.

    THE NAME ALONE UP THERE, though the tooltip keeps `shortLabel` after an em dash. A tooltip is
    a second look and can afford the sentence; the status line is one line in a fixed place.
    Both read duty_text.json, so they cannot disagree about what the mark is called.

    Falsify: route a control through hover(), drop the lightFace(null), or read the name from
    anywhere but the shared wording.
    """
    draw = _code(_function(tmpl, "drawMarks"))
    assert "e.dataset.hoverMark = name;" in draw, (
        "a control no longer carries its own name for the hover:\n%s" % draw)
    assert "CONTROLS[name]" in draw, (
        "the controls' names are no longer read from the shared wording:\n%s" % draw)

    picked = _code(_function(tmpl, "hoverDataOf"))
    assert "hoverMark" in picked, (
        "the hover walk does not stop on a control, so nothing reaches the status line:\n%s"
        % picked)

    code = _code(tmpl)
    assert re.search(r"if \(d\.hoverMark\) return hoverMark\(d\.hoverMark\);", code), (
        "a control does not take its own route out of the delegation, so it would be announced "
        "as whatever duty is selected")

    on = _code(_function(tmpl, "hoverMark"))
    assert "hovered = {mark: name}" in on, "hovering a control sets no state:\n%s" % on
    assert "lightFace(null)" in on, (
        "hovering a control leaves a duty tile lit, so two objects claim the pointer:\n%s" % on)

    status = _code(_function(tmpl, "setStatus"))
    assert "hovered.mark" in status and "controlLine(" in status, (
        "the status line does not answer for a control:\n%s" % status)
    assert "phaseLine()" in status and "lineFor(" in status, (
        "the status line has lost one of its other two answers:\n%s" % status)

    line = _code(_function(tmpl, "controlLine"))
    assert "CONTROLS[" in line, "the line is not read from the shared wording:\n%s" % line
    assert "shortLabel" not in line, (
        "the status line is carrying the tooltip's sentence:\n%s" % line)

    # AND THE WORDING IS NOT TYPED HERE. Asked of the code: the prose on this board names these
    # marks freely -- the control column's own rule explains itself by saying Show Map and Hire a
    # building are never chosen -- so both comment kinds come off first.
    bare = _code(re.sub(r"/\*.*?\*/", "", tmpl, flags=re.S))
    said = json.loads((BOARD / "duty_text.json").read_text(encoding="utf-8"))["controls"]
    for entry in said.values():
        assert '"%s"' % entry["name"] not in bare, (
            "%r is typed into the template, so it can differ from duty_text.json"
            % entry["name"])
    assert [said[k]["name"] for k in ("map", "hire", "commit")] == [
        "Show Map", "Hire a building", "Confirm"], (
        "the shipped control wording changed: %s" % [said[k]["name"] for k in said])


def test_a_resources_name_comes_from_the_tree_and_not_from_a_capital_letter(tmpl):
    """THE BOARD'S OWN RULE, stated where the controls are drawn: the wording comes from data.

    A labels object typed into the tool is one file restating another, which is what the controls
    column already learned -- so the four resource names are read from
    tools/ui_debug/duty_wheel_layout.json, which names all four and which ui/render/gen_board.py
    already reads. That is a second reader of an existing source, not a new dependency. It also
    means "Silver coin" rather than "Silver", which no amount of capitalising a key would give.

    AND A MISSING LABEL IS NOT FATAL. It falls back to the key with a capital on it and says so
    in the build notes, the same bargain every other missing thing on this board strikes. A build
    that refused over a caption would be refusing the wrong thing.

    Falsify: capitalise the key in the template, or make a missing label fatal.
    """
    body = _code(_function(tmpl, "titheName"))
    assert "TITHE.names" in body, (
        "the page is no longer taking resource names from the generator:\n%s" % body)
    assert "capitalize" not in _code(tmpl) and "toUpperCase" not in body, (
        "the page is inventing a display name from the key")

    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    assert "duty_wheel_layout.json" in src, (
        "the generator no longer reads the file that names the resources")
    assert '"names": names' in src, "the names never reach the page"
    fn = src[src.index("def tithe_names("):src.index("def bundled_tithe(")]
    assert "raise" not in fn, "a missing caption stops the build"

    # RUN, NOT READ. Asking whether `notes.append` APPEARS in the source is satisfied by a branch
    # that can never be taken -- a mutation turning `if missing:` into `if False:` passed this
    # guard untouched. The function is sliced out and executed against a tree of this test's own
    # making instead, which is the trick the JS side of this file has used all along.
    keys = _tithe_keys()
    ns = {"json": json, "TITHE_KEYS": keys}
    with tempfile.TemporaryDirectory() as tmp:
        layout = pathlib.Path(tmp) / "duty_wheel_layout.json"
        ns["WHEEL_LAYOUT"] = layout
        exec(compile(fn, "<tithe_names>", "exec"), ns)          # noqa: S102 - this file's own text
        tithe_names = ns["tithe_names"]

        # EVERY LABEL PRESENT: taken as given, nothing said.
        layout.write_text(json.dumps(
            {"tithe_icons": {k: {"label": k.upper()} for k in keys}}), encoding="utf-8")
        out, notes = tithe_names()
        assert out == {k: k.upper() for k in keys}, out
        assert not notes, "a complete tree still reports something: %s" % notes

        # ONE MISSING: named after its key, AND SAID.
        short = {k: {"label": k.upper()} for k in keys[1:]}
        layout.write_text(json.dumps({"tithe_icons": short}), encoding="utf-8")
        out, notes = tithe_names()
        assert out[keys[0]] == keys[0].capitalize(), (
            "a resource with no label is not named after its key: %r" % out[keys[0]])
        assert notes and keys[0] in notes[0], (
            "a missing label is not reported, so the board would quietly name a resource after "
            "its key: %s" % notes)

        # NO FILE AT ALL: all four fall back, and that is said too.
        layout.unlink()
        out, notes = tithe_names()
        assert out == {k: k.capitalize() for k in keys}, out
        assert notes, "an unreadable layout file is not reported"


def test_the_resource_order_and_the_wildcard_come_from_the_generator(tmpl):
    """TWO FACTS ABOUT THE TREE, AND THE TREE IS WHAT THE GENERATOR WALKS.

    The page needs the ORDER to list a pool the same way every time and the WILD one to know what
    unions the rest in. Written out in the template they would be a second list to keep in step
    with TITHE_KEYS -- and the failure would be silent: a page whose order had drifted would
    simply list resources in a different sequence from the one the build reports.

    Falsify: write the three names or the wildcard into the template.
    """
    assert re.search(r"^var TITHE = __TITHE__;$", tmpl, re.M), (
        "the page no longer takes the resources from the generator")
    body = _code(_function(tmpl, "tithePool"))
    assert "TITHE.order" in body and "TITHE.wild" in body, (
        "the pool no longer reads the generator's answer:\n%s" % body)
    for key in _tithe_keys():
        assert '"%s"' % key not in _code(tmpl), (
            "the template writes the resource name %r out instead of reading TITHE" % key)


def test_the_tithe_ring_reads_clockwise_from_north(geo):
    """THE DEAL, WRITTEN DOWN IN THE ONE FORM THE MISTAKE WOULD BE VISIBLE IN.

    V2_TITHE is a bare tuple with no slugs in it, zipped against geometry's DUTIES -- which is the
    right way to write it, because repeating the slugs would be a second list to keep in step. The
    cost is that it is one step away from being silently wrong: reorder DUTIES, or drop an entry,
    and every duty quietly takes its neighbour's resource. Nothing would raise and the board would
    look finished.

    So the deal is held here BY COMPASS FACE rather than by position, with the face derived from
    each duty's clock angle the way geometry derives it -- 0 degrees north, 45 clockwise per step.
    A reorder moves a resource to a different face and this fails; a reorder that somehow kept
    every face's resource would not be a mistake.

    THE CORNUCOPIA IS DEALT TO SOUTH, WHICH IS CONSTRUCT, and it is the WILDCARD rather than a
    fourth resource -- the tile where the tithing player chooses what they take. It sits in the
    ring like the other three because that is the arrangement being looked at; this guard holds
    where it is, not what it means.

    Falsify: rotate V2_TITHE by one, swap two entries, or reorder geometry's DUTIES.
    """
    want = {"north": "wheat", "north_east": None, "east": "silver", "south_east": "stone",
            "south": "cornucopia", "south_west": "wheat", "west": "silver",
            "north_west": "stone"}
    ring = _v2_tithe()
    assert len(ring) == len(geo.DUTIES), (
        "V2_TITHE names %d resources and geometry publishes %d duties" % (len(ring),
                                                                          len(geo.DUTIES)))
    got = {geo.face_of(deg): key for (_, _, deg), key in zip(geo.DUTIES, ring)}
    assert got == want, (
        "the ring reads %s"
        % ", ".join("%s %s" % (f, got.get(f, "missing") or "none") for f in geo.COMPASS))


def test_only_taxation_is_dealt_no_resource(geo):
    """THE ONE EXCEPTION, NAMED RATHER THAN COUNTED.

    "Every duty but Taxation takes a resource" is the rule, and the two halves of it fail
    differently: a second None is a duty quietly missing its resource, and a None that has MOVED is
    two duties wrong at once with the count still right. Asserting there is exactly one None would
    catch the first and miss the second, so this asks which duty it belongs to.

    Falsify: deal Taxation a resource, or deal any other duty None.
    """
    ring = _v2_tithe()
    none_at = [slug for (slug, _, _), key in zip(geo.DUTIES, ring) if key is None]
    assert none_at == ["taxation"], (
        "the duties dealt no resource are %s" % (", ".join(none_at) or "none"))


def test_every_resource_the_ring_deals_is_one_the_tree_can_draw(geo):
    """A KEY WITH NO CUT BEHIND IT DRAWS AN EMPTY FRAME, SILENTLY, which is the failure this
    catches before it reaches the board.

    The page looks a resource up in IMAGES by `tithe:<key>` and falls back to an empty frame, which
    is the right behaviour at draw time -- a visible hole beats a crash -- and is exactly why a
    typo in V2_TITHE would survive a build and a look at the page. So the three names are held
    against TITHE_KEYS, and TITHE_KEYS against what is actually on disk AND recorded, which is the
    pair of conditions the bundler gates on.

    Falsify: add a fourth name to V2_TITHE, or rename a cut without renaming the key.
    """
    keys = _tithe_keys()
    dealt = {k for k in _v2_tithe() if k is not None}
    assert dealt <= set(keys), (
        "the ring deals %s, which TITHE_KEYS does not name" % ", ".join(sorted(dealt - set(keys))))

    folder = BOARD / "tokens" / "resources" / "icons"
    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))["files"]
    for key in sorted(dealt):
        cuts = sorted(f for f in folder.glob("resource_%s_icon_v*" % key)
                      if f.is_file() and f.suffix.lower() in (".png", ".webp"))
        assert cuts, "no cut on disk for the %s resource, so its frame would draw empty" % key
        rel = "tokens/resources/icons/%s" % cuts[-1].name
        assert rel in rec, (
            "%s is the newest %s cut and has no attribution entry, so the bundler leaves it out "
            "and the frame draws empty" % (rel, key))


def _tithe_block(tmpl: str) -> str:
    """drawGrid's `if (L.hasTithe){...}` alone, by its own braces.

    By braces rather than by a prose anchor, because _code() strips whole-line comments -- slicing
    to one reads to the end of drawGrid, which includes every seal the duty plate makes, and a
    guard asking "does this block mention `seal`" then passes on anything.
    """
    grid = _code(_function(tmpl, "drawGrid"))
    head = "if (L.hasTithe){"
    assert head in grid, "drawGrid no longer has a tithe block"
    i = grid.index(head)
    j, depth = grid.index("{", i), 0
    while True:
        if grid[j] == "{":
            depth += 1
        elif grid[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return grid[i:j + 1]


def test_the_tithe_box_and_the_chosen_resource_are_lit_from_the_state(tmpl):
    """EVERY ROUTE TO ONE FACT AGREES BECAUSE NONE OF THEM SETS THE CUE.

    The Take Tithe box is reached two ways -- pressing the box, which answers a pool of one by
    itself, and clicking a resource inside it -- and the chosen resource has to light the way a
    chosen action mark does. Both are set from the state, which is render()'s own stated rule for
    exactly this reason: a class set where it is CLICKED is right on one route and stale on the
    other.

    THE BOX SAID NOTHING AT ALL BEFORE THIS. It had been clickable since it was drawn and the
    only sign it had been pressed was the commit mark appearing in the column -- survivable while
    pressing it was the only way in, and much louder now that it is where the choosing happens.
    So `.panel.sel` joins `.art.sel`'s own declaration rather than getting a matching outline.

    AND THE RESOURCES IN IT ARE LIT BY THE SEAL'S OWN RULE: same 50px artwork, chosen the same
    way, so a different fraction of brightness would claim there are two kinds of choosable mark.
    The tile's copy of the same picture is NOT in that rule, because it is a label.

    Falsify: light either one in a click handler, give `.panel.sel` its own outline, or put the
    tile's label back in the brightening rule.
    """
    render = _code(_function(tmpl, "render"))
    assert re.search(r'tbox\.classList\.toggle\("sel", S\.slot === TITHE_SLOT\)', render), (
        "the Take Tithe box is not lit from S.slot in render()")

    draw = _code(_function(tmpl, "drawTithe"))
    assert re.search(r'classList\.toggle\("on",\s*S\.slot === TITHE_SLOT && S\.tithe === key\)',
                     draw), (
        "the chosen resource is not lit from the state:\n%s" % draw)

    for fn in ("titheClick", "takeTithe", "select", "pickAction"):
        body = _code(_function(tmpl, fn))
        assert "classList" not in body, (
            "%s sets a cue where the click happens rather than leaving it to the draw:\n%s"
            % (fn, body))

    sel = _rule(tmpl, ".art.sel, .panel.sel")
    assert sel.get("outline-color") == "var(--line)", (
        "the Tithe box no longer shares the action cards' own chosen outline: %s. The shared "
        "declaration moved to the base rules when the row gained three states; what matters "
        "here is still that ONE rule answers for both." % sel)
    lit = _rule(tmpl, ".seal.filled, .tmark.filled, .tslot.filled")
    assert lit.get("filter"), (
        "the board's marks no longer share one rest weight: %s" % lit)
    flat = re.sub(r"\s+", "", tmpl)
    assert ".tslot.filled.on{filter" in flat or ".tslot.filled.on," in flat, (
        "the chosen resource is not lit by the rule that lights a chosen action mark")


@needs_node
def test_the_controls_sit_on_the_take_tithe_boxs_own_lines(pool, geo, tmpl):
    """TWO COLUMNS, THREE ROWS, AND A MARK LEVEL WITH THE RESOURCE BESIDE IT.

    geometry puts the three controls on y values of its own -- 265, 333 and 432, unevenly spaced
    because the commit was given extra air -- which belong to no line anything else on this board
    uses. They are laid out against the Take Tithe box instead: same size as a resource, same
    three rows.

    THE SAME TOP AND THE SAME HEIGHT AS THE BOX is what makes that true without restating the
    box's internals. Both are panels, both place their children against their own padding box,
    and both lay them out with `titheLayout` -- so identical offsets land on identical rows, and
    no arithmetic here has to know about the box's label or its border. Any other height would
    need both restated, which is the drift this file keeps undoing.

    THE FULL SET'S LINES, not the pool's. A pool of two centres its block and stops matching; the
    controls are always three and always on the three-resource rows, which is the arrangement
    the alignment was asked for.

    Falsify: give the column its own y, its own height, or its own idea of how big a mark is.
    """
    src = _code(_function(tmpl, "controlBox"))
    assert "lifted(GEO.tithe)" in src, (
        "the control column no longer takes its position from the Take Tithe box:\n%s" % src)
    assert "titheLayout(TITHE.order.length)" in src, (
        "the column is not laid out on the full set's lines:\n%s" % src)
    assert "GEO.marks." not in src.replace("GEO.marks.pad", ""), (
        "the column is reading geometry's own control rects again:\n%s" % src)

    # THE ROWS THEMSELVES, run rather than argued. This used to assert that the column shared the
    # box's y and height, which was proof while it did -- a column that closes up does not, so the
    # proxy had to go and the thing it stood for is measured instead. Both lists come from the
    # page's own functions in node, so a mistake in either moves what is compared.
    C = pool["cols"]
    assert C["box"]["rows"] == C["col"]["rows"], (
        "the two columns are on different rows: box %s, controls %s"
        % (C["box"]["rows"], C["col"]["rows"]))
    assert len(C["col"]["rows"]) == len(_tithe_token()["order"]), (
        "the column does not have a row for every resource: %s" % C["col"]["rows"])


    draw = _code(_function(tmpl, "drawMarks"))
    assert re.search(r"top:\s*px\(C\.start \+ i \* C\.pitch\)", draw), (
        "the marks are not placed on the box's rows:\n%s" % draw)
    assert re.search(r"width:\s*px\(C\.size\)", draw), (
        "the marks are not drawn at the box's own size:\n%s" % draw)
    assert "box(marked(" not in draw, "the old geometry-driven placement is still here"

    # AND THE SIZE IS THE RESOURCE'S. Measured off the same layout the box uses.
    full = len(_tithe_token()["order"])
    assert pool["layout"][str(full)]["size"] == pool["layout"]["1"]["size"], (
        "the resources are not one size, so 'the same size as a resource' names nothing")

    # BOTH COLUMNS CENTRE THEIR MARKS IN THEIR OWN PADDING BOX, which is the panel less its own
    # border at each end. Centring in the margin-to-margin width instead is a pixel out, because
    # the margins are measured from the panel's OUTER edge and an absolutely positioned child is
    # placed from its inner one -- the box's resources sat 44.5 from one side and 42.5 from the
    # other until this was fixed. The same border-box trap took the duty marks once already.
    left = _code(_function(tmpl, "titheSlotLeft"))
    assert "PANEL_BORDER" in left, (
        "the box centres its resources without paying for the panel's border:\n%s" % left)
    assert "panelW" in left, (
        "the box centres against the margins rather than the panel:\n%s" % left)
    # THE SAME EXPRESSION, NOT A MATCHING ONE. Asking whether PANEL_BORDER appears in controlBox
    # proved nothing: it is in the panel's width too, so a `left` that had dropped it entirely
    # still passed. The column calls the box's own centring function now, and that is what is
    # asserted.
    assert "titheSlotLeft(" in src, (
        "the control column centres its marks with arithmetic of its own:\n%s" % src)
    assert re.search(r'^var PANEL_BORDER = \d+;$', tmpl, re.M), (
        "the panel's own border is not named, so the two columns can pay different amounts")


@needs_node
def test_the_control_column_closes_up_instead_of_matching_the_boxs_height(pool, tmpl):
    """THE BOX IS 247 TALL BECAUSE IT CARRIES A LABEL, and this column carries none.

    Sharing the box's rect made the rows line up with no arithmetic at all, which was worth
    something -- but it also gave a column with no heading 31px of nothing at the top, holding
    the place of a word it does not have. So the panel closes up: the air the box leaves BELOW
    its last resource is the air this leaves above its first AND below its last.

    THE BOX'S TOP MARGIN IS NOT A MARGIN and is deliberately not borrowed. It is the room the
    label sits in, so copying it would reproduce a gap that exists for a reason this column does
    not have -- which is the whole of what was wrong with matching the height.

    WHICH MEANS THE TWO PANELS END ON THE SAME LINE rather than starting on it, and that is the
    visible consequence worth having asserted somewhere.

    Falsify: match the box's height again, or borrow its top margin for the top.
    """
    C = pool["cols"]
    border = float(_decl(tmpl, "PANEL_BORDER"))
    block = C["block"]
    above = C["col"]["start"]
    below = (C["col"]["height"] - 2 * border) - (C["col"]["start"] + block)
    assert above == below, (
        "the column leaves %g above its marks and %g below" % (above, below))
    assert C["col"]["height"] == block + 2 * above + 2 * border, (
        "the column is %g tall for a block of %g with %g of air at each end"
        % (C["col"]["height"], block, above))
    assert C["col"]["height"] < C["box"]["height"], (
        "the column is still as tall as the box (%g), so it is holding room for a label it does "
        "not have" % C["col"]["height"])
    # THE BOX'S OWN BOTTOM MARGIN IS THE ONE BORROWED, not an invented number.
    box_below = (C["box"]["height"] - 2 * border) - (C["box"]["rows"][-1] - C["box"]["y"]
                                                     - border + 0)
    assert abs(below - (box_below - C["col"]["size"])) < 1e-9, (
        "the column's margin is %g where the box leaves %g below its last resource"
        % (below, box_below - C["col"]["size"]))
    # AND THE TWO END TOGETHER.
    assert C["col"]["y"] + C["col"]["height"] == C["box"]["y"] + C["box"]["height"], (
        "the panels do not end on the same line: column %g, box %g"
        % (C["col"]["y"] + C["col"]["height"], C["box"]["y"] + C["box"]["height"]))


def test_the_controls_stand_on_the_duty_frames_ground_in_one_rectangle(tmpl):
    """ONE GROUND, ONE TOKEN, AND ONLY THE GROUND.

    LOST ONCE ALREADY, which is worth recording here rather than in a commit nobody re-reads.
    This guard was written when each control carried its own ground, and it was deleted by a
    slice-and-replace whose two anchors sat either side of it -- the third time this file has
    lost a test that way. The count is the only thing that catches it, and printing the count is
    not the same as comparing it with what you expected.

    The three controls wore `.panel`'s own #0e0d0b while the duty frames wore 55% of --plate.
    Both sit on #board's black, so the two were the same darkness in different hues -- rgb(14,
    13, 11) warm against rgb(12, 16, 20) cool -- which reads as two kinds of object holding the
    same artwork. They share one ground now, through a `--plate-ground` token that `.iplate` and
    `.cbox` both read, so `--tile-alpha` still reaches both.

    ONE RECTANGLE, NOT THREE, and that is geometry rather than taste: a mark is drawn at the Take
    Tithe box's own size now, and a ground of `pad` either side of it is taller than the line
    pitch, so three separate grounds would overlap. One panel holding three marks is also what
    the box beside it is.

    WHAT IS NOT SHARED IS THE POINT OF THE TOKEN. A duty frame also means "selectable, takes the
    gold rim when chosen" and the controls are never chosen -- so they take `--plate-ground` and
    not `.iplate`: same background, their own border, their own radius, no selected state.

    Falsify: write either background out as a literal, give the column the frame's border, or
    bring back a per-mark ground.
    """
    root = _rule(tmpl, ":root")
    ground = root.get("--plate-ground")
    assert ground, "there is no --plate-ground token for the two to share"
    assert "var(--tile-alpha)" in ground and "var(--plate)" in ground, (
        "the shared ground no longer goes through the numbers somebody would tune: %s" % ground)

    frame = _rule(tmpl, ".iplate")
    column = _rule(tmpl, ".cbox")
    assert frame.get("background") == "var(--plate-ground)", (
        "the duty frame no longer reads the shared ground: %s" % frame)
    assert column.get("background") == "var(--plate-ground)", (
        "the control column no longer stands on the duty frame's ground: %s" % column)
    # THE MIX IS WRITTEN ONCE, WHICH IS NOT THE SAME AS BEING THE ONLY MIX ON THE PAGE. This read
    # "no color-mix survives outside the token", which was true while this was the only thing on
    # the board mixed from anything -- and it failed the moment an UNRELATED mix arrived (the gold
    # wash that lights an open tile) without a copy of this one existing anywhere. A guard that
    # fires on a stranger is a guard that gets edited under pressure, so it now says what it
    # means: this ground appears once, and nothing else is mixed from --plate.
    body = _code(tmpl)
    assert body.count(ground) == 1, (
        "the shared ground is written out %d times instead of read from the token"
        % body.count(ground))
    strangers = re.findall(r"color-mix\([^;)]*(?:\([^)]*\))?[^;)]*\)", body.replace(ground, ""))
    assert not [m for m in strangers if "--plate" in m], (
        "a second mix of the plate has appeared outside the token: %s" % strangers)

    assert "var(--plate-edge)" not in column.get("border", ""), (
        "the control column has taken the duty frame's own edge: %s" % column)
    assert column.get("border") and column.get("border-radius"), (
        "the control column has lost its own border or radius: %s" % column)

    # ONE RECTANGLE: no per-mark ground survives anywhere.
    assert "::before" not in re.sub(r"/\*.*?\*/", "", tmpl, flags=re.S).split("</style>")[0], (
        "a control is drawing a ground of its own again, which cannot fit the line pitch")

    # The Take Tithe box is NOT one of the three and keeps the ground it had.
    panel = _rule(tmpl, ".panel")
    assert panel.get("background", "").startswith("#"), (
        "the Take Tithe box's own ground moved with the controls', which was not asked for: %s"
        % panel)


def test_the_word_tithe_is_written_once_in_the_selection(tmpl):
    """FIVE PLACES NEEDED THE SAME STRING AND A MISSPELLING IN ANY ONE IS A SILENT DEAD CLICK.

    `S.slot` has held `"tithe"` since the box was first wired, as a bare literal. There were two
    such places and it was survivable. A clickable resource makes five -- the panel's handler, the
    mark's dataset, the picker, render()'s loop and render()'s box -- and they do not check each
    other: a typo in one gives a resource that selects nothing while the box still works, or a box
    that lights for everything except the resource. Nothing throws and nothing fails a build.

    Falsify: write `"tithe"` into any of the five.
    """
    assert re.search(r'^var TITHE_SLOT = "tithe";$', tmpl, re.M), (
        "the template no longer names the tithe slot in one place")

    # THE BOX'S ELEMENT ID IS NOT THE SLOT'S VALUE, and they are the same word, which is exactly
    # the sort of coincidence a guard like this mistakes for a duplicate. One is a DOM identifier
    # shared with the `#tithe` CSS rule -- which cannot read a JavaScript variable, so it could
    # not be folded into the constant even if it meant the same thing -- and the other is what
    # `S.slot` holds. Renaming either leaves the other correct. So the two id uses are set aside
    # by name and what is left has to come from the constant.
    assert re.search(r"#tithe\s", tmpl), "the Take Tithe box's own CSS rule has gone"
    id_uses = ('p.id = "tithe"', 'getElementById("tithe")')
    for fn in ("drawSide", "render", "titheClick"):
        body = _code(_function(tmpl, fn))
        for use in id_uses:
            body = body.replace(use, "")
        assert '"tithe"' not in body, (
            "%s writes the slot name out instead of reading TITHE_SLOT:\n%s" % (fn, body))
    block = _tithe_block(tmpl)
    assert '"tithe"' not in block, (
        "the resource's dataset writes the slot name out instead of reading TITHE_SLOT:\n%s"
        % block)


def test_a_frame_that_would_not_fit_is_counted_apart_from_the_plates(tmpl):
    """TWO COUNTERS BECAUSE THEY ARE TWO LOSSES, AND THEY HAPPEN AT DIFFERENT SETTINGS.

    The frame is refused when the rectangle has no width left BESIDE the plate, which comes first:
    at the opening gap and edge the marks are all drawn from size 56 up and the resources only from
    85. A single counter would print "8 without room for icons" on a board whose icons are all
    drawn -- a readout that is wrong in the direction of looking broken.

    AND IT IS RESET WHERE THE OTHER IS. A counter incremented in drawGrid and zeroed nowhere grows
    on every slider event, so the readout would be right once and absurd by the tenth drag.

    Falsify: fold the two counters into one, drop the reset, or stop the readout mentioning it.
    """
    grid = _code(_function(tmpl, "drawGrid"))
    assert "TITHES_DROPPED = 0;" in grid, (
        "drawGrid no longer zeroes the resource counter, so it grows on every slider event")
    assert "TITHES_DROPPED++" in grid, "nothing counts a refused resource frame"
    assert "PLATES_DROPPED++" in grid, "nothing counts a refused plate any more"
    wire = _code(_function(tmpl, "wireGrid"))
    assert "TITHES_DROPPED" in wire, "the readout never mentions a refused resource"
    assert "PLATES_DROPPED" in wire, "the readout never mentions a refused plate"
    # The two are reported as different things, not summed into one phrase.
    assert "PLATES_DROPPED + TITHES_DROPPED" not in wire, (
        "the two losses are added together, so the readout cannot say which one happened")


@needs_node
def test_the_resource_is_right_aligned_and_not_centred_like_a_short_row(sweep, tmpl):
    """THE ONE PLACE THE TWO FRAMES MUST NOT SHARE ARITHMETIC, and it looks like the place they
    should.

    `P.inset` centres a SHORT row of marks inside the widest row any duty needs -- it is what puts
    Allocation's single mark in the middle of the span a two-mark duty fills. The resource is not
    in that row and is not centred in anything: it is pinned to the frame's right-hand end. Borrow
    `inset` for it and it would move right by half the difference between one mark and two, 28px,
    and only on the duties that hold a single action -- so Allocation's and Taxation's resources
    would sit somewhere no other duty's does, which looks like two of the eight being drawn wrong
    rather than like one expression being shared where it should not be.

    WHICH GIVES THE CLAIM ITS SHARPEST FORM: the resource sits in the same place whether its duty
    holds one action or two. Nothing about how many marks a duty has may reach it.

    Falsify: call markAt(P, 0) for the resource, or add P.inset to titheMarkAt.
    """
    src = _code(_function(tmpl, "titheMarkAt"))
    assert "P.ip" in src, (
        "the resource's margin is no longer the board's own:\n%s" % src)
    assert "inset" not in src, (
        "the resource has picked up the short-row centring term:\n%s" % src)

    by_cell = {}
    for row in sweep:
        if row["centre"] or not row["plate"]["hasTithe"]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"],
               row["cell"]["col"], row["cell"]["row"])
        by_cell.setdefault(key, {})[row["nAct"]] = row["plate"]["titheMark"]["x"]
    compared = 0
    for key, lefts in by_cell.items():
        if len(lefts) < 2:
            continue
        compared += 1
        assert len(set(lefts.values())) == 1, (
            "gap %d, edge %d, size %d, height %d, cell (col %d, row %d): the resource sits at %g "
            "for a duty holding one action and %g for one holding two"
            % (key + (lefts[min(lefts)], lefts[max(lefts)])))
    assert compared, (
        "no rectangle drew a resource at both action counts, so the one thing this guard is "
        "about was never compared")
    # AND THE RESOURCE IS WHERE THE LINE ENDS, which is what makes the equality above worth
    # asserting rather than merely true: it is one of the two fixed points the rest of the row is
    # justified between, so if anything about a duty's own marks could reach it, the whole line
    # would move on two tiles out of eight.
    assert any(row["plate"]["g"] > row["plate"]["igap"] for row in sweep if not row["centre"]), (
        "every rectangle in the sweep was spaced at the minimum, so the justification never "
        "actually divided anything")


@needs_node
def test_the_acolytes_stand_on_the_line_and_the_plate_hangs_below_it(tmpl):
    """TWO DIFFERENT CLAIMS ABOUT THE SAME LINE, and they used to be one.

    The feet kept a 6px clearance and the plate kept the same below, read off a single constant
    so the two could not drift into different numbers that only measuring would find. The feet
    are flush to the inner bottom edge now and the plate still drops -- so the symmetry is gone
    on purpose and the constant belongs to the plate alone, which is why it stopped being called
    FOOT_GAP.

    THE FEET HAVE NO TERM AT ALL, not a zero. A zero is a number somebody can tune, and there is
    nothing here to tune: the line is where they stand.

    Falsify: give `foot` a clearance again, or write the plate's drop as a literal.
    """
    drop = float(_decl(tmpl, "PLATE_DROP"))
    assert drop > 0, "PLATE_DROP is not a positive number"

    figures = _code(_function(tmpl, "drawFigures"))
    m = re.search(r"var foot = r\.y \+ r\.height - CELL_BORDER;", figures)
    assert m, (
        "the acolytes no longer stand on the rectangle's own inner bottom edge:\n%s"
        % "\n".join(ln for ln in figures.split("\n") if "foot" in ln))
    assert not re.search(r"var foot =[^;]*(PLATE_DROP|- \d)", figures), (
        "something has put a clearance back under the acolytes' feet")

    place = _code(_function(tmpl, "placeFor"))
    assert re.search(r"var y = r\.y \+ r\.height \+ PLATE_DROP;", place), (
        "the plate no longer hangs PLATE_DROP below the line:\n%s" % place)
    hang = _code(_function(tmpl, "plateHang"))
    assert "PLATE_DROP + plateHeight()" in hang, (
        "the room reserved for the plates below the bottom row no longer includes the same drop "
        "the plate is actually drawn with:\n%s" % hang)


@needs_node
def test_the_pile_has_the_whole_inner_height_to_grow_into(tmpl):
    """It used to lose a clearance at each end -- the gap under the feet, and the same again at
    the top for symmetry -- and with the bottom gap gone there is nothing left to subtract.

    A cap that still took 12px off would size every figure on the board against a rectangle
    12px shorter than the one it stands in, which is invisible until you measure it against the
    plate the figures are supposed to match.

    Falsify: put a clearance back into the cap.
    """
    body = _code(_function(tmpl, "drawFigures"))
    assert re.search(r"var cap = \(r\.height - 2 \* CELL_BORDER\)", body), (
        "the pile's height cap is no longer the rectangle's whole inner height:\n%s"
        % "\n".join(ln for ln in body.split("\n") if "cap" in ln))


@needs_node
def test_the_plate_is_refused_rather_than_cropped(sweep, geo):
    """IT IS OUTSIDE THE CELL NOW, SO THE CELL NO LONGER PROTECTS IT -- and #board is
    `overflow:hidden` as well.

    A plate under the bottom row hangs into the margin below it, and at a tall arrangement it
    runs off the board. Cropped, it reads as a plate of a different shape; refused, the duty
    simply has no icons, which is wrong in a way somebody can see and ask about. Refusing is the
    choice, and `PLATES_DROPPED` is what stops it being silent.

    Falsify: drop the `plateY + plateH <= GEO.canvas.height` term from `hasPlate`.
    """
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        p = row["plate"]
        assert p["plateY"] + p["plateH"] <= geo.CANVAS_H, (
            "%s: the plate reaches %g down a board %d tall, so overflow:hidden takes the rest"
            % (_tag(row), p["plateY"] + p["plateH"], geo.CANVAS_H))



@needs_node
def test_the_icons_are_never_drawn_smaller_than_geometry_draws_them(sweep, geo, tmpl):
    """AN ICON THAT CHANGES SIZE WITH A LAYOUT SLIDER IS AN ICON YOU CANNOT COMPARE.

    The size used to be the smallest of geometry's 50, what the row could take across the
    rectangle and what the rectangle's height allowed -- so a duty's marks came out at 32px at
    the settings this board opens on, against the 50 the same mark is drawn at everywhere else
    in the game. These are the one object on a rectangle that carries meaning rather than
    arrangement, so the size is fixed and the ROOM is what gives.

    Falsify: put any `Math.min` back around the icon size.
    """
    seal = geo.as_dict()["ribbon"]["seal"]
    assert seal > 0
    body = _code(_function(tmpl, "plateFor"))
    assert re.search(r"var sz = GEO\.ribbon\.seal;", body), (
        "the icon size is no longer geometry's own number, plainly:\n%s" % body)
    assert "Math.min" not in body and "Math.floor" not in body, (
        "something is capping or rounding the icon size again:\n%s" % body)
    for row in sweep:
        if row["centre"]:
            continue
        assert row["plate"]["sz"] == seal, (
            "%s: the icon came out %g where geometry draws it at %g"
            % (_tag(row), row["plate"]["sz"], seal))
        # The frame is the emblem plus its margin, border included -- which is how a control
        # mark's ground is drawn, and the point of matching it.
        assert row["plate"]["fullH"] == seal + 2 * row["plate"]["ip"], (
            "%s: the plate is %g tall around a %g icon with %g of margin"
            % (_tag(row), row["plate"]["fullH"], seal, row["plate"]["ip"]))


@needs_node
def test_a_plate_too_wide_for_its_rectangle_is_refused(sweep):
    """THE WIDTH TEST WAS DEAD CODE UNTIL THE ICON STOPPED SHRINKING, and now it does the work.

    It was in `hasPlate` for a round, a mutation proved no slider setting could fail it -- the
    icon shrank to fit first -- and it was removed as dead. With the size fixed, a two-action
    plate is 130 wide whatever rectangle it belongs to, and the sliders make rectangles smaller
    than that. A plate wider than the thing it captions reaches under its neighbours and stops
    saying which duty it belongs to, so it is refused.

    Measured across the whole slider space: 52% of settings draw all eight plates, and at the
    opening gap and edge all eight hold from size 50 upward -- twelve steps below the default.

    IT IS THE ROW THAT CAN FAIL TO FIT, NOT THE FRAME, and that distinction arrived with the
    tithe resource. The frame now spans its rectangle, so asking whether the frame fits would be
    asking whether `innerW <= innerW` -- the third dead condition this file would have carried.
    What the sliders can make too narrow is the ROW BOX: the widest row any duty needs plus its
    margin either side.

    Falsify: drop the `P.rowBox <= P.innerW` term from placeFor's `has`, or test `P.innerW`
    against itself.
    """
    drew = refused = 0
    for row in sweep:
        if row["centre"]:
            continue
        p = row["plate"]
        if p["hasPlate"]:
            drew += 1
            assert p["rowBox"] <= p["innerW"] + 1e-9, (
                "%s: a row needing %g was drawn in a %g-wide rectangle"
                % (_tag(row), p["rowBox"], p["innerW"]))
        else:
            refused += 1
    assert drew, "no plate was drawn anywhere in the sweep"
    assert refused, (
        "no plate was refused anywhere in the sweep, so the width test cannot be doing anything "
        "-- which is what it was removed for last time")


def test_a_plate_that_would_not_fit_is_counted_and_said(tmpl):
    """THREE DUTIES QUIETLY WITHOUT ICONS LOOKS LIKE THREE DUTIES THAT HAVE NONE.

    The refusal above is right and it is still a loss. The readout already says when the grid
    passes the margin; this is the same kind of fact about the same drag, so it is said in the
    same place. Without it the only way to notice is to count the plates.

    Falsify: stop incrementing PLATES_DROPPED, or drop the term from the readout.
    """
    grid = _code(_function(tmpl, "drawGrid"))
    assert "PLATES_DROPPED++" in grid, (
        "nothing counts a refused plate, so the readout cannot report one")
    assert "PLATES_DROPPED = 0" in grid, (
        "drawGrid does not reset the count, so it climbs on every slider event")
    wire = _code(_function(tmpl, "wireGrid"))
    assert "PLATES_DROPPED" in wire, "the readout never mentions the refused plates"
    # THE CONDITION IS PARSED, NOT MATCHED WHOLE. This used to pin the expression verbatim --
    # `(over > 0.5 || PLATES_DROPPED)` -- and that broke the day the tithe frames got a loss of
    # their own to report, which is a guard failing because the page learned something rather than
    # because it forgot something. What it is really asserting is that losing a plate is one of
    # the things that colours the tag, so that is what it asks, and a new disjunct is allowed to
    # join without this needing an edit.
    m = re.search(r"tag\.style\.color = \((.*?)\)\s*\?", wire)
    assert m, "the readout no longer colours itself at all"
    terms = [t.strip() for t in m.group(1).split("||")]
    assert "PLATES_DROPPED" in terms, (
        "the readout does not colour itself when a duty has lost its icons, so the number is "
        "printed in the same grey as the numbers that are fine: %s" % terms)
    assert "over > 0.5" in terms, (
        "the readout no longer colours itself when the arrangement passes the margin: %s" % terms)


@needs_node
def test_the_icons_sit_inside_the_plate_that_was_sized_for_them(sweep, tmpl):
    """THE PLATE'S SIZE AND THE ICONS' PLACEMENT ARE TWO EXPRESSIONS, and they must agree.

    `plateW` comes out of the sliced block; the icons are placed by a separate line further down
    -- `left: px(ip + k * (sz + igap))` -- so the row can be sized against one arithmetic and
    drawn by another. The plate is the icon's own ground, so a row that overruns it puts a disc
    half on the plate and half on the board.

    Falsify: change the icons' `left` to `ip + k * sz`, or drop the `(nAct - 1) * igap` from the
    plate's own width.
    """
    # THE PAGE'S OWN PLACEMENT, not a second copy of it. These numbers come from `markAt`,
    # which drawGrid also calls, so the mutation that moves a mark moves what is checked here.
    assert re.search(r"var at = markAt\(P, k\);", tmpl), (
        "drawGrid no longer places its marks with markAt, so the sweep and the page are working "
        "out two different positions")
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        p, n = row["plate"], row["nAct"]
        border = float(_decl(tmpl, "PLATE_BORDER"))
        # THE ROW BOX, NOT THE FRAME. The frame spans the whole rectangle now, so bounding the
        # marks by it would pass on a row three times too wide -- the frame has room to spare and
        # the point of this guard is that the row and the space reserved for it agree.
        inner_w = p["rowBox"] - 2 * border
        inner_h = p["plateH"] - 2 * border
        assert len(p["marks"]) == n, (
            "%s: %d mark(s) placed for a duty with %d" % (_tag(row), len(p["marks"]), n))
        first, last = p["marks"][0], p["marks"][-1]
        assert first["left"] >= 0, (
            "%s: the first mark starts at %g, outside its own frame"
            % (_tag(row), first["left"]))
        assert last["left"] + last["w"] <= inner_w + 1e-9, (
            "%s: the last of %d mark(s) reaches %g inside a frame %g wide"
            % (_tag(row), n, last["left"] + last["w"], inner_w))
        # AND THE SAME GAP TOP AND BOTTOM, which is what the frame's height is for.
        assert abs(first["top"] - (inner_h - (first["top"] + first["h"]))) < 1e-9, (
            "%s: a mark sits %g from the top of its frame and %g from the bottom"
            % (_tag(row), first["top"], inner_h - (first["top"] + first["size"])))


def test_the_plate_lives_on_the_board_and_is_swept_with_the_grid(tmpl):
    """`.dcell` IS overflow:hidden, SO A PLATE INSIDE IT WOULD BE CLIPPED TO NOTHING.

    That is the failure this arrangement invites: the plate hangs below the cell's own bottom
    edge, so as a child of the cell it would simply not be drawn -- no error, no warning, and a
    board whose icons had all vanished. It is a child of #board instead, which costs one thing:
    removing the cells no longer removes the plates, so drawGrid has to sweep them itself or
    nine orphans accumulate on every slider event.

    Falsify: append the plate to `cell`, or sweep only `.dcell` in drawGrid.
    """
    body = _code(_function(tmpl, "drawGrid"))
    m = re.search(r'el\("div", "iplate", \{[^}]*\}\)', body)
    assert m, (
        "the plate is no longer created with `el(\"div\", \"iplate\", {...})` and no parent -- a "
        "fourth argument here would put it back inside the cell, where overflow:hidden is:\n%s"
        % body)
    # PARSED, NOT PINNED. This held the selector verbatim and broke the day the resources left
    # the plate and had to join the sweep -- a guard failing because the page learned something
    # rather than because it forgot something. What it is really asserting is that everything
    # drawGrid makes outside the cells is swept by it, so that is what it asks.
    m = re.search(r'querySelectorAll\("([^"]+)"\)', body)
    assert m, "drawGrid no longer sweeps anything before rebuilding"
    swept = {s.strip() for s in m.group(1).split(",")}
    for need in (".dcell", ".iplate", ".tmark", ".mmark"):
        assert need in swept, (
            "drawGrid does not sweep %s, which is not a child of the cells it does sweep -- so "
            "every slider event leaves one behind per duty: %s" % (need, sorted(swept)))


@needs_node
def test_every_duty_gets_the_same_frame_whatever_it_holds(sweep, tmpl):
    """TWO SIZES OF THE SAME OBJECT IN ONE ROW READS AS TWO KINDS OF THING.

    Allocation and Taxation hold a single mark each and used to get a plate 74 wide against the
    other six's 130. The frame is now the widest row ANY duty needs, and a short row is centred
    in it -- so what differs between duties is the marks, not the ground they sit on.

    THE WIDTH IS COUNTED, NOT TYPED. `mostActions()` walks the duties, so a duty gaining a third
    action widens every plate to match without anything else changing. A literal 2 here would
    leave the new mark hanging off the edge of seven frames.

    ASKED PER ARRANGEMENT NOW, NOT ACROSS THE WHOLE SWEEP. This used to collect every frame width
    in the sweep and demand there be exactly one, which worked while the frame was built to its
    contents and was therefore the same 118 at every slider setting. The frame spans its rectangle
    now, so its width changes with the sliders by design -- and a test still demanding one width
    everywhere would be failing on the feature rather than on a fault. What the claim was always
    about is two duties SIDE BY SIDE: at one setting, in one rectangle, a duty holding one mark
    gets the same frame as a duty holding two.

    Falsify: size the plate from `rowW` again, or write the full row as `2 * sz + igap`.
    """
    by_cell = {}
    for row in sweep:
        if row["centre"]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"],
               row["cell"]["col"], row["cell"]["row"])
        by_cell.setdefault(key, {})[row["nAct"]] = row["plate"]["fullW"]
    assert by_cell, "the sweep produced no rectangles to compare"
    for key, widths in by_cell.items():
        assert len(set(widths.values())) == 1, (
            "gap %d, edge %d, size %d, height %d, cell (col %d, row %d): a duty holding one mark "
            "gets a %g-wide frame and one holding two gets %g"
            % (key + (widths[min(widths)], widths[max(widths)])))
    assert any(len(w) > 1 for w in by_cell.values()), (
        "no rectangle was measured at more than one action count, so nothing was compared")
    body = _code(_function(tmpl, "plateFor"))
    assert "mostActions()" in body, (
        "the frame is no longer built to the widest row any duty needs:\n%s" % body)
    assert not re.search(r"(?<!most)\b2 \* sz", body), (
        "the full row is written as a literal two marks, so a third action would hang off the "
        "edge of every frame:\n%s" % body)


@needs_node
def test_a_short_row_leaves_its_slot_empty_rather_than_closing_up(sweep, tmpl):
    """ONE MARK IN A FRAME BUILT FOR TWO SITS IN THE FIRST SLOT, and that is a reversal.

    It used to be centred: an inset of half the difference put Allocation's single mark in the
    middle of the span a two-mark duty fills, so the frame read as one object holding what it
    had. That was right while the frame was the only thing on the line -- and is wrong now that
    four acolytes stand over four slots. Centred, Allocation's mark would sit BETWEEN the first
    and second acolyte, with a person over each side of it.

    SO A SLOT IS A PLACE AND NOT A THING THAT HAPPENS TO BE FILLED. A duty with fewer marks
    leaves the slot empty; the frame is the same width on every tile, and every tile's people
    line up with the same four positions.

    Falsify: put the inset back, or build the frame to the marks the duty actually holds.
    """
    assert "inset" not in _code(_function(tmpl, "markAt")), (
        "the short-row centring term is back in markAt, which moves a single mark off its slot")
    seen, border = set(), float(_decl(tmpl, "PLATE_BORDER"))
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        p, n = row["plate"], row["nAct"]
        seen.add(n)
        # THE FIRST MARK IS ALWAYS IN THE SAME PLACE, whatever the duty holds: one padding in
        # from the frame's outer edge, which is `ip` less the border the padding box already
        # paid for.
        assert abs(p["marks"][0]["left"] - (p["ip"] - border)) < 1e-9, (
            "%s: the first of %d mark(s) sits %g from the frame's padding box, against %g"
            % (_tag(row), n, p["marks"][0]["left"], p["ip"] - border))
        # AND EVERY MARK AFTER IT IS ONE SLOT ON.
        for k in range(1, n):
            assert abs(p["marks"][k]["left"]
                       - (p["marks"][0]["left"] + k * (p["sz"] + p["g"]))) < 1e-9, (
                "%s: mark %d is not one slot past the one before it" % (_tag(row), k))
    assert seen == {1, 2}, (
        "the sweep did not cover both a short row and a full one: %s" % sorted(seen))


def test_no_rectangle_carries_a_name_any_more(tmpl):
    """THE PARCHMENTS WENT AND THE WORDS WENT WITH THEM, which was the decision, not an accident.

    `banner()` had a fallback that drew the duty's name as text whenever the art was missing --
    which is exactly what a half-finished removal would leave behind: delete the images, keep the
    function, and the board quietly grows nine serif captions nobody asked for. Both are gone,
    and this is what says so.

    THE FILES ARE NOT GONE and must not be: duty_actions/banners/ and fonts/ stay in the tree,
    recorded and guarded by tests/action_board/test_action_board_v2_banners.py, because they may
    come back and a resource deleted and re-fetched comes back as a different file.

    Falsify: put the `.dn` rule, the `banner()` function or the `__BANNERS__` token back.
    """
    # EVERY ONE OF THESE IS A CODE FORM, not a word. The template EXPLAINS the removal in a
    # comment that says "no @font-face here any more", and a guard asking for the bare word would
    # fail on the sentence describing the thing it is checking for. That has happened five times
    # on this board; `{` and `(` are what tell a rule or a function from a mention of one.
    for gone in ("__BANNERS__", "__BANNERMETA__", "__BANNERFONT__", "@font-face{",
                 "function banner(", ".ban{", ".dcell .dn{"):
        assert gone not in tmpl, (
            "the page still carries %r, so a rectangle can still end up wearing a name" % gone)
    assert BANNERS_DIR.is_dir(), (
        "the banner art has been deleted from the tree; it is meant to stay, unused and recorded")
    assert any(BANNERS_DIR.glob("*.webp")), "duty_actions/banners/ has no art left in it"


@needs_node
def test_a_duty_plate_keeps_the_same_margin_as_a_control_mark(sweep, tmpl, geo):
    """TWO FRAMES ROUND THE SAME 50px EMBLEMS SHOULD NOT KEEP TWO DIFFERENT MARGINS.

    The plate used the ribbon's `pad` -- 12, what a tile kept around its marks when the marks
    were on tiles -- against the 6 the Map and Hire controls keep. The duty plates read as a
    looser kind of object than the controls rather than as the same kind in another place.

    THE NUMBER IS READ FROM THE CONTROLS, NOT COPIED. `GEO.marks.pad` is what `.mark::before`
    is inset by, so the two cannot be tuned apart -- and a control column that retightens takes
    the duty plates with it.

    THE HEIGHT FOLLOWS FROM IT, which is the other half of what was asked: emblem plus margin
    either side is 62, the same as a control's frame, and geometry publishes that box so the two
    are held against each other here rather than against a number typed in this file.

    Falsify: put `GEO.ribbon.pad` back in plateFor.
    """
    g = geo.as_dict()
    pad = g["marks"]["pad"]
    seal = g["ribbon"]["seal"]
    box = g["marks"][g["marks"]["order"][0]]["box"]
    assert box["height"] == seal + 2 * pad, (
        "a control's own published box is %g tall round a %g emblem with %g of margin, so this "
        "test's idea of 'the same' is wrong before it starts"
        % (box["height"], seal, pad))

    body = _code(_function(tmpl, "plateFor"))
    assert "GEO.marks.pad" in body, (
        "the plate's margin is no longer the controls' own number:\n%s" % body)
    assert "GEO.ribbon.pad" not in body, (
        "the plate is back on the ribbon's padding, which is twice the controls':\n%s" % body)

    for row in sweep:
        if row["centre"]:
            continue
        p = row["plate"]
        assert p["ip"] == pad, (
            "%s: the plate keeps %g of margin and a control mark keeps %g"
            % (_tag(row), p["ip"], pad))
        assert p["fullH"] == box["height"], (
            "%s: the plate is %g tall and a control's frame is %g"
            % (_tag(row), p["fullH"], box["height"]))


# ---------------------------------------------------------------- where the acolytes stand


@needs_node
def test_the_figures_row_always_has_somewhere_to_stand(sweep):
    """A NEGATIVE SPAN DRAWS NOBODY, SILENTLY, and a board with four empty duties looks exactly
    like a board with no acolytes on it.

    `drawFigures` divides `figRight - figLeft` into slots and returns early when a figure comes
    out under three pixels. That early return is right -- a hood of two pixels is a smudge -- and
    it is also the one place where a geometry error turns into an ABSENCE rather than a mess.
    Nothing downstream can tell the two apart, so the span is checked where it is set, which is
    here.

    Falsify: swap `figLeft` and `figRight`, or drop the `CELL_BORDER` from either.
    """
    for row in sweep:
        if row["centre"]:
            continue
        p, r = row["plate"], row["r"]
        assert p["figRight"] > p["figLeft"], (
            "%s: the row runs from %g to %g, which is backwards or nothing"
            % (_tag(row), p["figLeft"], p["figRight"]))
        assert p["figLeft"] >= r["x"], (
            "%s: the row starts at %g, left of the rectangle's own %g"
            % (_tag(row), p["figLeft"], r["x"]))
        assert p["figRight"] <= r["x"] + r["width"], (
            "%s: the row ends at %g and the rectangle ends at %g"
            % (_tag(row), p["figRight"], r["x"] + r["width"]))


@needs_node
def test_the_row_is_the_whole_rectangle_and_is_margined_evenly(sweep, tmpl):
    """THE ROW IS THE ROOM NOW, because there is nothing left in the rectangle to share it with.

    It ran from the banner's left edge to the plate's while both were in there -- half the width,
    and the alignment was the brief. Both have gone, so the row takes the whole rectangle less one
    margin at each end. The failure to guard against is asymmetry: a row that keeps the old
    right-hand expression would end where a plate that is no longer there used to start, which
    leaves the acolytes bunched to the left in a rectangle with space to spare on the right. That
    looks like a design decision.

    The row is placed against the cell's PADDING box, which is why the border is in both terms and
    is the one that is easy to lose on one side only.

    Falsify: drop the `mg` from `r.figLeft`, or the `- mg` from `r.figRight`.
    """
    border = float(_decl(tmpl, "CELL_BORDER"))
    for row in sweep:
        if row["centre"]:
            continue
        p, r = row["plate"], row["r"]
        want_l = r["x"] + border + p["mg"]
        want_r = r["x"] + border + p["innerW"] - p["mg"]
        assert abs(p["figLeft"] - want_l) < 1e-9, (
            "%s: the row starts at %g and one margin inside the rectangle is %g"
            % (_tag(row), p["figLeft"], want_l))
        assert abs(p["figRight"] - want_r) < 1e-9, (
            "%s: the row ends at %g and one margin inside the far edge is %g"
            % (_tag(row), p["figRight"], want_r))
        left = p["figLeft"] - (r["x"] + border)
        right = (r["x"] + border + p["innerW"]) - p["figRight"]
        assert abs(left - right) < 1e-9, (
            "%s: the row keeps %g at one end and %g at the other" % (_tag(row), left, right))


def test_the_row_is_divided_into_as_many_slots_as_there_are_players(tmpl, geo, hood):
    """FOUR IS WRITTEN INTO THE DIVISOR, so a fifth player would be drawn off the end of the row.

    `drawFigures` sizes a figure as span / (4 + 3 * HOOD.gap) and then puts seat j at
    `figLeft + j * (fw + gap)`. Both 4s are literals and neither counts anything. Seat the board
    for five and the fifth pile is drawn past the plate's left edge, over the icons, with nothing
    raised -- and the loop walks `HOOD.order` while the counts come from geometry's PLAYERS, so
    all three numbers have to be the same one.

    Falsify: add a fifth player to geometry's PLAYERS, or a fifth seat to hood's SEAT_ORDER.
    """
    m = re.search(r"\(r\.figRight - r\.figLeft\)\s*/\s*\((\d+)\s*\+\s*(\d+)\s*\*\s*HOOD\.gap\)",
                  tmpl)
    assert m, "the figure width is no longer span / (n + (n - 1) * HOOD.gap)"
    slots, gaps = int(m.group(1)), int(m.group(2))
    assert gaps == slots - 1, "the row divides into %d slots but allows %d gaps" % (slots, gaps)
    assert slots == len(hood.SEAT_ORDER), (
        "the row has %d slots and the hood table has %d seats (%s)"
        % (slots, len(hood.SEAT_ORDER), ", ".join(hood.SEAT_ORDER)))
    assert slots == len(geo.PLAYERS), (
        "the row has %d slots and the board has %d players" % (slots, len(geo.PLAYERS)))


def test_the_piles_are_keyed_by_the_boards_players_and_not_the_hoods_names(tmpl):
    """KEYING THEM BY THE HOOD'S NAMES FOUND NOTHING AND DREW NOBODY, which is the bug this is for.

    S.occupancy holds player ids -- p1..p4 -- and the figure's own table is keyed
    sage/pewter/plum/bone. `countsFor` has to go through GEO.players to get from one to the other.
    When it did not, it returned four zeros for every rectangle and the board drew an empty grid,
    with no error and nothing in the console: a board with four empty duties is a legal board.

    The drawing pass needs a DOM, so what is held here is the mapping itself -- that it still goes
    through GEO.players, BY INDEX, and that the placement loop still indexes the hood's own order
    so that the count at j and the colour at j are the same seat.

    Falsify: change `GEO.players.map` in countsFor to `HOOD.order.map`.
    """
    body = _function(tmpl, "countsFor")
    assert "S.occupancy" in body, "countsFor no longer reads the board's occupancy"
    assert "GEO.players.map" in body, (
        "countsFor no longer walks GEO.players, so the piles are keyed by something that is not a "
        "player id:\n%s" % body)
    assert "HOOD." not in body, (
        "countsFor reads the hood table, which is keyed by colour and not by player:\n%s" % body)
    assert "HOOD.order.forEach(function(seat, j)" in tmpl, (
        "the placement loop no longer indexes the hood's own order, so the count at index j and "
        "the colour at index j may be different seats")


def test_all_nine_rectangles_are_in_the_sizing_pass(tmpl):
    """THE CITY IS THE FULLEST, AND LEAVING IT OUT WOULD SIZE EVERY FIGURE AGAINST A SHORTER PILE.

    One figure size serves the whole board, so that the row of piles the eye compares stays
    comparable -- that is the entire point of the drawing. The size comes from the tallest pile
    anywhere, and the City opens with seven of somebody where a duty has at most four. Size the
    board on the duties alone and the City's pile runs off the top of its rectangle, which
    overflow:hidden crops into a row of headless people.

    Falsify: delete the `if (GRIDPOS.city) CELLS.push("city")` line, or move it below the sizing.
    """
    body = _function(tmpl, "drawFigures")
    assert 'CELLS.push("city")' in body, (
        "the City is not in drawFigures' list of rectangles, so it is neither sized nor drawn")
    assert body.index('CELLS.push("city")') < body.index("tallest = Math.max"), (
        "the City is added to the list after the sizing pass has already run, so it is drawn at a "
        "size chosen without it")


def test_the_city_keeps_a_figure_row_of_its_own(tmpl):
    """THE CITY HOLDS PEOPLE LIKE ANY DUTY DOES; it simply has no icon plate.

    `drawFigures` walks GRIDPOS and reads `figLeft`/`figRight` off whatever it finds, so the City
    is drawn only because its own branch registers those two numbers before returning. That branch
    returns EARLY -- before the plate arithmetic every other rectangle runs -- so if it stopped
    setting them the City's figures would be placed at `undefined`, which is NaN, which is a
    figure that is simply not on the page. No error, and eight rectangles still full.

    Falsify: delete `GRIDPOS.city = r` or either of the City's own figLeft/figRight lines.
    """
    body = _function(tmpl, "drawGrid")
    i = body.index("if (c.centre){")
    j = body.index("var ring = -1;")
    centre = body[i:j]
    for want in ("r.figLeft", "r.figRight", "GRIDPOS.city = r"):
        assert want in centre, (
            "the City's branch no longer sets %s, so it is registered without everything "
            "drawFigures reads off it" % want)
    assert "iplate" not in centre, (
        "the City's branch now draws a plate; it has no actions to put on one, and the missing "
        "plate is part of what separates it from its eight neighbours")


@needs_node
def test_an_acolyte_is_as_tall_as_the_plate_below_his_rectangle(tmpl):
    """ONE HEIGHT FOR THE TWO OBJECTS A DUTY IS READ BY, which is what was asked for.

    The plates are sized in drawGrid and the figures in drawFigures, two passes with nothing
    between them, so the height has to travel. Re-deriving it in the second pass would be the
    same arithmetic written twice -- and the failure that produces is a figure ALMOST the height
    of the plate beside it, which nobody finds by looking.

    IT IS THE HEIGHT THE PLATE WOULD HAVE, captured before a plate that will not fit is zeroed.
    A board whose bottom row lost its icons must not draw its people to match a plate of nothing.

    Falsify: read PLATE_H after the `if (!hasPlate)` line, or set `fw` from the row again.
    """
    plate = _code(_function(tmpl, "drawGrid"))
    take = plate.index("PLATE_H = Math.max(PLATE_H, plateH)")
    zero = plate.index("if (!hasPlate)")
    assert take < zero, (
        "PLATE_H is taken after a refused plate has been zeroed, so a board that lost its icons "
        "would size its acolytes against nothing")
    figures = _code(_function(tmpl, "drawFigures"))
    assert re.search(r"var fw = PLATE_H / HOOD\.h", figures), (
        "drawFigures no longer asks for the plate's height:\n%s" % figures)
    assert "fw = Math.min(fw, w, cap)" in figures, (
        "the plate's height is no longer held against the two caps, so a narrow rectangle can "
        "no longer shrink its people")
    grid = _code(_function(tmpl, "drawGrid"))
    assert "PLATE_H = 0" in grid, (
        "drawGrid does not reset PLATE_H, so the tallest plate of any earlier arrangement keeps "
        "sizing the figures after the sliders have moved")


def test_the_figure_row_is_centred_in_its_rectangle(tmpl):
    """THE SLACK IS SPLIT, because sized by the plate the row no longer fills the room.

    While the figures were sized BY the row they filled it exactly and there was nothing to
    centre. Sized by the plate they come out narrower -- 291 of 380 at the opening settings --
    and left anchored the group would read as people pushed against an edge, with the icon plate
    centred underneath disagreeing with them.

    THE SLACK MUST BE MEASURED AGAINST THE ROW BEING DRAWN. This used to be put as "the row's
    width and the width that would fill the row are one expression" -- `(4 + 3 * HOOD.gap)`
    appearing in the cap and again in the slack -- and that held while the cap was the only
    thing deciding either. It stopped holding when two sliders arrived that move the drawn row
    without moving the cap: `folk` scales the figures past what fits, and `apart` opens the gaps.
    Measured against the cap's width the row would now be centred against a width it does not
    have, which looks like a small, consistent lean that gets worse as either is dragged.

    SO THE TWO THINGS THAT HAVE TO AGREE ARE THE SLACK AND THE STEP. Placement walks j from 0 to
    3 by `fw + gap`, so the row really occupies four figures and three gaps; the slack has to
    subtract exactly that, out of the same two variables.

    Falsify: drop the `/ 2`, subtract the cap's width instead of the drawn one, or step by
    something other than what the slack was measured with.
    """
    body = _code(_function(tmpl, "drawFigures"))
    assert re.search(r"var slack = \(r\.figRight - r\.figLeft\) - \(fw \* 4 \+ gap \* 3\);",
                     body), \
        "the row's slack is no longer the span less four figures and three gaps:\n%s" % body
    # THE FALLBACK, WHICH IS NOW THE CITY'S. The eight duties stand their people over the slots
    # on the line below them; the City has no line, so it keeps the even spread -- and the spread
    # is still centred, for the reason this whole guard exists.
    assert re.search(r"x = r\.figLeft \+ slack / 2 \+ j \* \(fw \+ gap\);", body), (
        "the row is no longer placed at half the slack, so it is not centred:\n%s" % body)
    assert re.search(r"if \(r\.seats && r\.seats\[j\] != null\)", body), (
        "the figures no longer stand over the duty line's slots, so the spread below is the "
        "only rule left and nothing lines up with anything:\n%s" % body)
    assert "fw * (4 + 3 * HOOD.gap)" not in body, (
        "the slack is measured against the width that would FIT rather than the width being "
        "DRAWN. Those are the same number only while no slider has moved the figures.")


@needs_node
def test_the_plate_height_is_a_ceiling_the_figures_never_pass(sweep, geo, hood):
    """A TARGET, NOT A GUARANTEE -- and at the board's own defaults it is not reached.

    The plate's height is what the figures ask for; the row's width and the deepest pile are
    still what makes a figure impossible, and on a narrow rectangle the row wins and the
    acolytes come out SHORTER than the plate. That is correct, and at the opening settings it is
    what happens: gap 120, edge 60, size 62 gives a 168 x 84 rectangle whose plate is 56 tall,
    while the row allows a figure only 29.7 wide against the 46.7 the plate asks for. The plate
    does not start setting the size until size 118 at that gap and edge; at gap 20, edge 40 it
    takes over at 91, and at gap 0, edge 0 at 82.

    So what holds everywhere is the one-directional claim: a figure is never TALLER than the
    plate below its rectangle. Dropping the plate from `Math.min(fw, w, cap)` breaks it at the
    wide settings, where the row would otherwise allow more.

    Falsify: drop the `fw` term from `Math.min(fw, w, cap)` in drawFigures.
    """
    h = hood.as_dict()["h"]
    slots = 4 + 3 * hood.as_dict()["gap"]
    d = _grid_defaults()
    defaults = (d["gap"], d["disp"], d["size"], d["height"], d["cols"])

    def wants_vs_allows(row):
        """What the plate asks of a figure's width, and what the row leaves for one."""
        p = row["plate"]
        return p["fullH"] / h, (p["figRight"] - p["figLeft"]) / slots

    # AT THE BOARD'S OWN DEFAULTS THE TWO AGREE, which is what replaced a claim that has now
    # flipped twice in a day. It used to be that the row was the tighter of the two and the
    # acolytes came out shorter than their plate; widening the wheel to the Take Tithe box made
    # the plate the tighter one; opening the size slider at 100 instead of 110 brought the row
    # back to within a fifth of a pixel of it. Which of them wins at the opening settings is not
    # a property of this board -- it is where three sliders happen to sit -- so what is pinned is
    # that they agree, and that a figure is the smaller of the two whichever that is.
    at_default = [r for r in sweep if not r["centre"] and r["plate"]["hasPlate"]
                  and (r["gap"], r["disp"], r["size"], r["height"],
                       r["cols"]) == defaults]
    assert at_default, "the sweep does not cover the opening defaults"
    for row in at_default:
        wants, allows = wants_vs_allows(row)
        assert abs(allows - wants) < 1.0, (
            "%s: the plate asks for a %g-wide figure and the row allows %g. They are a pixel "
            "apart at the settings the board opens on, and were tuned to be; if that is no "
            "longer wanted this guard is the place to say so."
            % (_tag(row), wants, allows))

    # AND IT IS REACHED SOMEWHERE, or asking for it is decoration.
    reached = [r for r in sweep if not r["centre"] and r["plate"]["hasPlate"]
               and wants_vs_allows(r)[0] <= wants_vs_allows(r)[1]]
    assert reached, (
        "the row is narrower than the plate at every setting in the sweep, so the acolytes are "
        "never the plate's height and the term in `Math.min(fw, w, cap)` does nothing")


# ---------------------------------------------------------------- the copied figure


def test_the_hood_has_not_drifted_from_the_tree_it_was_copied_from(hood):
    """A COPY WITH NOTHING WATCHING IT IS THE PRICE OF NOT READING ACROSS AT BUILD TIME.

    board_v2 copies the hood rather than importing it, deliberately and for the same reason the
    banners are copied: this board must read nothing out of ui/render/, so that a change over there
    cannot alter it and neither tree's guards reach the other. The cost is that the two can
    disagree, and a figure that disagrees by one coordinate, or by one hex digit of plum, is not
    something anybody would see.

    Skipped rather than failed if the original is gone: this board does not depend on it, and a
    guard that fails because an unrelated tree was retired is a guard that gets deleted.

    Falsify: change any coordinate in HOOD_PATH, or plum's hex, or a number in TILE.
    """
    if not UPSTREAM_HOOD.exists():
        pytest.skip("ui/render/population_sets.py is gone; the copy is now the only one")
    up = _load("population_sets", UPSTREAM_HOOD.parent)

    assert hood.HOOD_PATH == up.hood_path(), (
        "the outline has drifted from population_sets.hood_path()")
    for name in ("HOOD_H", "HOOD_FACE", "HOOD_INK", "HOOD_STROKE", "SEAT_SWATCH"):
        assert getattr(hood, name) == getattr(up, name), (
            "%s is %r here and %r in population_sets"
            % (name, getattr(hood, name), getattr(up, name)))
    assert tuple(hood.SEAT_ORDER) == tuple(up.SEAT_ORDER), (
        "the seat order is %r here and %r there" % (hood.SEAT_ORDER, up.SEAT_ORDER))

    theirs = up.SETS["hood"]["tile"]
    for k in ("overlap", "gap", "step", "lean"):
        assert hood.TILE[k] == theirs[k], (
            "the pile's %s is %r here and %r in population_sets' hood set"
            % (k, hood.TILE[k], theirs[k]))


def test_the_page_is_handed_every_number_the_figure_needs(tmpl, hood):
    """The template holds NO copy of any of this, so a key the page reads and no figure publishes
    is `undefined` arithmetic -- which in JavaScript is NaN, and a NaN position is a figure that
    is not on the page rather than a figure in the wrong place.

    THERE ARE TWO FIGURES NOW AND THE SCOPE HAD TO FOLLOW. This read hood.as_dict() alone, and
    fired the day the template learned to draw the drawn acolyte -- correctly, because `over`
    and `shadeOf` really are read and really are not the hood's. Widening it to the union of the
    two would have been the lazy fix and a worse guard: it would then pass for a key published
    only by the friar and read where EITHER figure is drawn, which is the same NaN as before.
    So the template is split instead. There are exactly TWO places that know which figure is
    being drawn -- hoodSvg, past the line that sends the drawn acolyte elsewhere, and
    friarLayers -- and inside those a key need only be that figure's. Everywhere else, which is
    everything that MEASURES a figure rather than draws one, it has to be BOTH.

    Falsify: remove any key from either as_dict(), or read a new `HOOD.x` outside those two
    functions that only one figure publishes.
    """
    friar = _load("friar")
    draws = [_function(tmpl, "hoodSvg"), _function(tmpl, "friarLayers")]
    everywhere = tmpl
    for d in draws:
        everywhere = everywhere.replace(d, "")

    hood_keys, friar_keys = set(hood.as_dict()), set(friar.as_dict(""))
    both = hood_keys & friar_keys

    def reads(text):
        return set(re.findall(r"HOOD\.([A-Za-z_][A-Za-z0-9_]*)", text))

    missing = sorted(reads(everywhere) - both)
    assert not missing, (
        "the template reads HOOD.%s where either figure may be drawn, and %s not published by "
        "BOTH of them. "
        "Everything drawn for either acolyte has to be answerable by either, or the board draws "
        "one of them out of undefined."
        % (", HOOD.".join(missing), "it is" if len(missing) == 1 else "they are"))
    for fn, keys, who in ((draws[0], hood_keys | {"kind"}, "hoodSvg"),
                          (draws[1], friar_keys, "friarLayers")):
        missing = sorted(reads(fn) - keys)
        assert not missing, (
            "%s reads HOOD.%s, which the figure it draws does not publish"
            % (who, ", HOOD.".join(missing)))
    for k in ("path", "h", "face", "ink", "stroke", "swatch", "order", "step", "lean", "gap"):
        assert k in hood_keys, "hood.as_dict() no longer publishes %r" % k
    for k in ("kind", "h", "over", "shadeOf", "swatch", "order", "step", "lean", "gap"):
        assert k in friar_keys, "friar.as_dict() no longer publishes %r" % k


# =================================================================================================
# THE MERCHANT, WHICH IS THE THIRD THING ON A LINE BUILT FOR TWO.
#
# EVERYTHING BELOW IS ABOUT ROOM. The frame is built to the marks and the resource is pinned to
# the rectangle's right edge; the merchant gets what is left between them, and on Taxation -- the
# one duty that takes no tithe -- it is mirrored to the other side of the frame, where what it has
# to clear is the neighbouring rectangle rather than anything on its own line. All four ways this
# goes wrong are invisible on a still board at the opening settings: a marker touching the frame,
# a marker a different size from the other seven, a marker drawn where no room was checked for it,
# and a marker that followed the SLIDERS down to a smudge instead of going away.


@needs_node
def test_the_merchant_clears_what_it_stands_between(sweep):
    """It touches neither the frame nor the resource, at any setting of any slider.

    THE GAP IT KEEPS IS THE MARKS' OWN. Inside a single line the only thing separating three
    objects is distance, and the distance that says "these are not one row" is already named:
    `igap`, the space between a duty's own two marks. Let the merchant come closer than that to
    either side and the line reads as four icons in a row, which is exactly the misreading the
    resource was moved out of the frame to avoid.

    Falsify: drop the `2 * P.igap` from the width, or add the clearance to one side only.
    """
    # ASKED OF THE SLOTS, NOT OF THE DRAWING. The trade slider scales the merchant and the line
    # re-justifies around it, so the merchant's own box is whatever the person dragging it asked
    # for -- what has to hold is that its SLOT keeps the line's spacing from the slot on each
    # side of it, and that the drawing sits in the slot it was given.
    checked = 0
    for row in sweep:
        pl = row.get("plate")
        if not pl or not pl["hasPlate"] or not pl["hasTithe"] or not pl["merchant"]:
            continue
        m = pl["merchant"]
        frame_end = pl["plateX"] + pl["rowBox"]
        at, w, k = pl["at"], pl["widths"], pl["most"]
        assert abs((at[k] - (at[k - 1] + w[k - 1])) - pl["g"]) < 1e-9, (
            "%s: the merchant's slot starts %.2f after the slot before it, against the %.2f the "
            "line is spaced by" % (_tag(row), at[k] - (at[k - 1] + w[k - 1]), pl["g"]))
        assert abs((at[k + 1] - (at[k] + w[k])) - pl["g"]) < 1e-9, (
            "%s: the resource starts %.2f after the merchant, against %.2f"
            % (_tag(row), at[k + 1] - (at[k] + w[k]), pl["g"]))
        # CENTRED IN ITS SLOT, NOT FLUSH WITH IT. The slots are all one width and the drawings
        # in them are not, so what has to line up is the middles.
        assert abs((m["x"] + m["w"] / 2) - (pl["plateX"] + at[k] + pl["box"] / 2)) < 1e-9, (
            "%s: the merchant's middle is at %.2f and its slot's at %.2f"
            % (_tag(row), m["x"] + m["w"] / 2, pl["plateX"] + at[k] + pl["box"] / 2))
        assert frame_end <= pl["plateX"] + at[k] + 1e-9, (
            "%s: the frame's edge has reached into the merchant's slot" % _tag(row))
        checked += 1
    assert checked > 500, "only %d arrangements drew a merchant to check" % checked


@needs_node
def test_the_merchant_stands_a_mark_tall_on_every_board(sweep):
    """Height is what the eye compares it by, so height is what its slot is built to.

    IT USED TO BE FITTED INTO WHAT WAS LEFT OVER, capped at a mark and cut down by the gap
    whenever the gap was tighter than that -- which meant the figure beside a row of 50-pixel
    emblems was a different size on a board whose rectangles had moved. The line is justified
    around its slot now: the slot is a mark tall at every setting, and what changes with the
    sliders is the SPACE between the slots, which is the thing that is supposed to change.

    AND BELOW HALF A MARK THE LINE IS NOT SPACED, IT IS PACKED, so the marker is refused rather
    than drawn as dirt on every tile.
    """
    # THE CAPS ARE ON THE SIZE THE LINE OFFERS, NOT ON THE SIZE THAT IS DRAWN, which is the
    # whole point of the trade slider sitting outside them: it opens at 90 today and could open
    # anywhere, and a guard that measured the drawn figure would start failing the day somebody
    # moved it -- as this one did. So the drawn width is divided back out by the setting the
    # sweep ran at, and what is asserted is what the arithmetic decided before the slider.
    scale = _grid_defaults()["merch"] / 100.0
    sizes, dropped, by_height = set(), 0, 0
    for row in sweep:
        pl = row.get("plate")
        if not pl or not pl["hasPlate"] or not pl["hasTithe"]:
            continue
        m = pl["merchant"]
        if m is None:
            dropped += 1
            continue
        offered_w, offered_h = m["w"] / scale, m["h"] / scale
        assert offered_h <= pl["sz"] + 1e-9, (
            "%s: the merchant is offered %.2f of height against a %s mark"
            % (_tag(row), offered_h, pl["sz"]))
        assert offered_w <= pl["titheMark"]["x"] - (pl["plateX"] + pl["rowBox"]) + 1e-9, (
            "%s: the merchant is offered more width than the gap it stands in" % _tag(row))
        assert offered_w >= pl["sz"] * 0.5 - 1e-9, (
            "%s: the merchant was offered %.2f of width, under half a mark -- it should have "
            "been refused" % (_tag(row), offered_w))
        assert abs(offered_h - pl["sz"]) < 1e-6, (
            "%s: the merchant is offered %.2f of height against a %s mark -- its slot is a mark "
            "tall at every setting now, because the line is justified around it rather than it "
            "being fitted into what the line had left" % (_tag(row), offered_h, pl["sz"]))
        by_height += 1
        sizes.add(round(m["w"], 3))
    # AND THE FLOOR IS NOT REACHED HERE, WHICH IS SAID RATHER THAN HIDDEN. The sweep drives the
    # line at a mark's band -- that is placeFor's default and what every guard above is written
    # against -- and the merchant is refused by the BAND falling under half a mark, which only
    # the page's own board-wide sizing can produce. The trade slider's guard covers the other
    # half: a size somebody asked for is never a reason to refuse the figure.
    assert not dropped, (
        "%d arrangements refused a merchant at a full band, which the floor should not do"
        % dropped)
    assert by_height, "no arrangement drew a merchant at all"
    assert len(sizes) == 1, (
        "the merchant comes in %d widths; a mark tall is one width on every board, and the only "
        "thing that may change it is the trade slider" % len(sizes))


@needs_node
def test_the_merchant_stands_on_the_same_line_as_the_duty_s_own_icons(sweep, tmpl):
    """Its feet and the bottom of the marks are the same line, at every setting and every size.

    THE EYE LINES THINGS UP BY THEIR BOTTOMS, NOT BY THEIR BOXES. The marker is smaller than a
    mark and a different shape, so centring it in the row -- which is what it did first -- left
    it floating a few pixels above icons that sit on a line: nothing anybody can name, and
    everybody sees. Anchoring the bottom also makes the size slider grow it UPWARD, which is the
    only direction that keeps the line still while the figure changes.

    AND THE HEIGHT COMES FROM THE DRAWING'S OWN SHAPE. The marker is placed by width -- what the
    gap can spare -- so without the aspect it would be square, which at this aspect is a 7%
    stretch: a slightly different drawing rather than a visible fault.

    Falsify: centre it in the row, hang it from the top, or drop the aspect from the height.
    """
    for row in sweep:
        pl = row.get("plate")
        if not pl or not pl["merchant"]:
            continue
        m = pl["merchant"]
        assert abs(m["h"] - m["w"] * 1.5) < 1e-6, (
            "%s: the merchant is %.2f x %.2f, which is not the shape the drawing was made in"
            % (_tag(row), m["w"], m["h"]))
        feet = m["y"] + m["h"]
        marks = pl["marks"][0]
        # ONE BORDER, WHICH IS THE WHOLE OF THE DIFFERENCE BETWEEN THESE TWO. A mark is placed
        # against the frame's PADDING box and the merchant against the board, so comparing the
        # two without it is off by exactly the size of error this guard exists to catch.
        pb = float(_decl(tmpl, "PLATE_BORDER"))
        assert abs(feet - (pl["plateY"] + pb + marks["top"] + marks["h"])) < 1e-6, (
            "%s: the merchant's feet are at %.2f and the duty's drawings stand on %.2f"
            % (_tag(row), feet, pl["plateY"] + marks["top"] + marks["h"]))


@needs_node
def test_taxation_s_merchant_stands_where_every_other_duty_s_does(sweep):
    """The duty that takes no tithe gets the same marker in the same place.

    ITS RECTANGLE IS THE ODD ONE OUT AND ITS LINE IS NOT. Taxation has nothing on its right by
    design, so a marker placed by what is actually beside it would be sized and set differently
    from the other seven -- which is what the first version of this did, mirroring it to the
    left of the frame entirely. The gap it stands in is measured to where a resource WOULD go,
    and every rectangle has that whether it fills it or not.

    Falsify: measure the gap to the resource rather than to its place, or special-case the duty
    that has none.
    """
    seen = 0
    for row in sweep:
        pl = row.get("plate")
        if not pl or not pl["hasPlate"]:
            continue
        m, t = pl["merchant"], pl["merchantAsTaxation"]
        assert (m is None) == (t is None), (
            "%s: one of the two is drawn and the other is not" % _tag(row))
        if m is None:
            continue
        for k in ("x", "y", "w", "h"):
            assert abs(m[k] - t[k]) < 1e-9, (
                "%s: Taxation's merchant differs in %s -- %.3f against %.3f"
                % (_tag(row), k, t[k], m[k]))
        seen += 1
    assert seen > 500, "only %d arrangements compared the two" % seen


@needs_node
def test_the_board_as_it_opens_draws_a_merchant_on_every_duty(sweep):
    """Eight markers at the settings the board actually opens at, not merely "when there is room".

    EVERY OTHER GUARD HERE IS AN INVARIANT, and an invariant is satisfied by drawing nothing at
    all. A rule that refused the merchant more often than it had to -- a room measured against
    cells on rows this one does not share, say -- would break none of them and would show up as
    markers missing from a board nobody had touched the sliders on. This is the promise the rest
    of the file cannot make: at the opening settings there are eight.

    Falsify: widen anything that decides the room, or lower MERCHANT_FLOOR's effect, and tiles
    start opening without their marker.
    """
    want = _grid_defaults()
    opening = [r for r in sweep
               if not r.get("centre")
               and all(r[k] == want[k] for k in ("gap", "disp", "size", "height", "cols"))]
    assert opening, "the sweep does not cover the settings the board opens at"
    for r in opening:
        pl = r["plate"]
        assert pl["hasPlate"] and pl["hasTithe"], (
            "%s: the board does not open with a full line on every duty" % _tag(r))
        assert pl["merchant"], (
            "%s: a duty opens without its merchant, though the frame and the resource both fit"
            % _tag(r))
        assert pl["merchantAsTaxation"], (
            "%s: Taxation would open without its merchant, on a line with room for one" % _tag(r))


def test_the_merchant_is_drawn_only_where_one_was_placed(tmpl):
    """drawGrid is the one function these guards cannot call, so its source is asked instead.

    THE ARITHMETIC IS TESTED AND THE DRAWING IS NOT. Everything above runs placeFor in node and
    never builds a single element, which is what makes this file fast and what leaves exactly one
    hole: a marker drawn from a placement that came back null would read `.x` off nothing and
    take the whole board down with it -- no plates, no figures, no tiles -- at whichever slider
    setting first refuses a merchant. Nothing in a headless arithmetic sweep can see that.

    Falsify: draw the marker on `MERCHANT.src` alone, or hoist it out of the test entirely.
    """
    body = _code(_function(tmpl, "drawGrid"))
    i = body.find('el("div", "mmark"')
    assert i > 0, "drawGrid no longer draws a merchant at all"
    assert body.count("if (L.merchant && MERCHANT.src)", 0, i) == 1, (
        "the merchant is drawn without first asking BOTH questions. placeFor answers null "
        "whenever the line has no room for one -- and `null.x` is a TypeError that stops "
        "drawGrid mid-rebuild, taking the plates, the figures and the tiles with it -- while a "
        "tree with no marker filed leaves MERCHANT.src empty, which would put an <img src=\"\"> "
        "on all eight duties:\n%s" % body[max(0, i - 300):i + 120])


@needs_node
def test_the_trade_slider_scales_the_merchant_and_moves_nothing_else(tmpl, geo):
    """One rectangle, one setting, the slider swept across its whole range.

    KEPT OUT OF THE SWEEP ON PURPOSE and therefore asked here. The five sliders in the sweep all
    move rectangles; this one moves nothing, and running it as a sixth dimension would multiply
    eighteen thousand arrangements to re-answer a question none of them interact with. What it
    has to be held to is exactly this: the marker scales with it, in proportion, about the place
    it stood -- and the frame, the marks and the resource do not budge.

    AND IT IS ALLOWED PAST THE EDGES. Over 100 the merchant grows into the frame and the
    resource, which is what the slider is for: the size is being chosen by eye and a marker that
    refused to be looked at would teach nothing. So this does not assert a clearance -- the
    guard above holds that at the size the board opens at.

    Falsify: scale the height and not the width, grow it from its left edge, or let the marker's
    size leak into the frame or the resource.
    """
    body = _node("\n".join([
        "var GEO = %s;" % json.dumps(geo.as_dict()),
        "var CELL_BORDER = %s;" % _decl(tmpl, "CELL_BORDER"),
        "var PLATE_DROP = %s;" % _decl(tmpl, "PLATE_DROP"),
        "var PLATE_BORDER = %s;" % _decl(tmpl, "PLATE_BORDER"),
        "var MERCHANT = {h: 1.5, src: \"\"};",      # a stub, as in the sweep above
        "var MERCHANT_FLOOR = %s;" % _decl(tmpl, "MERCHANT_FLOOR"),
        "var DUTIES = %s;" % json.dumps({"a": {"actions": 1}, "b": {"actions": 2}}),
        "var GRID = {merch: 100};",
        _function(tmpl, "mostActions"),
        _function(tmpl, "plateHeight"),
        _function(tmpl, "plateFor"),
        "var LINE_MIN_GAP = %s;" % _decl(tmpl, "LINE_MIN_GAP"),
        _function(tmpl, "slotsFor"),
        _function(tmpl, "inkAt"),
        _function(tmpl, "plateInset"),
        _function(tmpl, "markAt"),
        _function(tmpl, "titheMarkAt"),
        _function(tmpl, "merchantAt"),
        _function(tmpl, "placeFor"),
        "var r = {x: 100, y: 200, width: 236, height: 165};",
        # A BAND THE WHOLE RANGE FITS IN. On the page the band is worked out across the eight
        # duties AT THE SLIDER'S CURRENT SETTING -- drag the merchant to twice its size and every
        # drawing on the board comes down to make room -- which is a board-wide pass this test
        # has no business reproducing. Fixing the band instead isolates what is being asked:
        # what the slider does to the merchant and to the spaces around it.
        "var BAND = 30;",
    ]), "(function(){ var out = []; "
        "[40, 70, 100, 150, 200].forEach(function(v){ GRID.merch = v; "
        "  var L = placeFor(r, 2, true, null, BAND); "
        "  out.push({v: v, m: L.merchant, plateX: L.x, rowBox: L.p.rowBox, "
        "            at: L.p.line.at, widths: L.p.line.w, g: L.p.line.g, "
        "            mark: markAt(L.p, 0), tithe: L.titheMark}); }); return out; })()")
    rows = {row["v"]: row for row in body}
    base = rows[100]
    assert base["m"], "the merchant is not drawn at the setting the board opens at"
    for v, row in rows.items():
        m = row["m"]
        assert m, "the merchant vanished at %d%% -- the slider is not a reason to refuse it" % v
        assert abs(m["w"] - base["m"]["w"] * v / 100) < 1e-6, (
            "at %d%% the merchant is %.3f wide against %.3f at 100%%"
            % (v, m["w"], base["m"]["w"]))
        assert abs(m["h"] - m["w"] * 1.5) < 1e-6, (
            "at %d%% the merchant is %.3f x %.3f, so the slider is stretching it rather than "
            "scaling it" % (v, m["w"], m["h"]))
        assert abs((m["y"] + m["h"]) - (base["m"]["y"] + base["m"]["h"])) < 1e-6, (
            "at %d%% the merchant's feet have left the line they stand on" % v)
        # AND THE LINE IS STILL EVENLY SPACED, which is what it means for the slider to belong
        # to the line rather than to sit on top of it. A smaller merchant in a slot kept at full
        # width would put more air around it than around anything else -- the unevenness this
        # whole arrangement was rebuilt to remove -- so the row re-justifies and everything
        # moves a little. What must not change is that the spaces are all one number.
        at, w, g = row["at"], row["widths"], row["g"]
        for k in range(1, len(at)):
            assert abs((at[k] - (at[k - 1] + w[k - 1])) - g) < 1e-9, (
                "at %d%% slot %d is %g past the one before it, against a spacing of %g"
                % (v, k + 1, at[k] - (at[k - 1] + w[k - 1]), g))
        assert abs(at[0] - base["at"][0]) < 1e-9, "at %d%% the line no longer starts where it did" % v
        assert abs((at[-1] + w[-1]) - (base["at"][-1] + base["widths"][-1])) < 1e-9, (
            "at %d%% the line no longer ends where it did" % v)
        assert row["mark"]["w"] == base["mark"]["w"], (
            "at %d%% a duty mark changed size when the merchant was scaled" % v)


@needs_node
def test_every_acolyte_has_a_place_on_the_line_below_it(sweep):
    """Seat one over the first mark, seat two over the second, seat three over the merchant,
    seat four over the resource -- on every tile, at every setting.

    THIS IS WHY THE SLOTS ARE FIXED. A player's figures and the thing those figures can take are
    the same question asked twice, and the answer should be readable by looking straight down
    rather than by counting across. Spread evenly instead -- which is what they did -- four
    people sit over four places that have nothing to do with the four objects beneath them, and
    the board quietly stops saying who may do what.

    AND A SLOT THAT IS EMPTY STILL HAS A MIDDLE. Taxation takes no tithe and Allocation holds one
    mark; their people stand in the same four places as everyone else's, because a slot is a
    position on the line rather than a thing that happens to be drawn in it. A line that closed
    up would move two tiles' people out of step with the other six.

    Falsify: publish three seats, order them differently, anchor them to a slot's left edge
    instead of its middle, or let a missing resource close the line up.
    """
    checked = 0
    for row in sweep:
        if row["centre"]:
            continue
        pl = row["plate"]
        if not pl["hasPlate"]:
            assert pl["seats"] is None, (
                "%s: a rectangle with no line published places to stand over it" % _tag(row))
            continue
        seats = pl["seats"]
        assert seats and len(seats) == pl["most"] + 2, (
            "%s: the line publishes %s places against %d slots"
            % (_tag(row), seats and len(seats), pl["most"] + 2))
        at, w = pl["at"], pl["widths"]
        for k in range(len(at)):
            want = pl["plateX"] + at[k] + w[k] / 2
            assert abs(seats[k] - want) < 1e-9, (
                "%s: seat %d stands at %g and slot %d is centred at %g"
                % (_tag(row), k + 1, seats[k], k + 1, want))
        # AND THE LAST OF THEM IS OVER THE RESOURCE ITSELF, which is the one slot whose drawing
        # is placed by the board rather than by the line's own arithmetic.
        assert abs(seats[-1] - (pl["titheMark"]["x"] + pl["titheMark"]["w"] / 2)) < 1e-9, (
            "%s: the last seat is not over the resource" % _tag(row))
        if pl["merchant"]:
            assert abs(seats[pl["most"]]
                       - (pl["merchant"]["x"] + pl["merchant"]["w"] / 2)) < 1e-9, (
                "%s: the third seat is not over the merchant" % _tag(row))
        checked += 1
    assert checked > 500, "only %d lines published places to stand" % checked


@needs_node
def test_the_places_are_the_same_whether_a_duty_fills_its_slots_or_not(sweep):
    """Allocation holds one mark and Taxation takes no tithe; their people stand where everyone
    else's do.

    THE TWO TILES THE WHOLE ARRANGEMENT TURNS ON. Every other duty fills all four slots, so any
    rule at all lines their people up; these two are where a line that closed up would show
    itself, and they are the pair the board has got wrong before -- the frame used to centre
    Allocation's single mark, which put it between two acolytes rather than under one.

    Falsify: size the line from the marks a duty actually holds, or skip the empty slot.
    """
    by_cell = {}
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"], row["cols"],
               row["cell"]["col"], row["cell"]["row"])
        by_cell.setdefault(key, {})[row["nAct"]] = row["plate"]["seats"]
    compared = 0
    for key, seats in by_cell.items():
        if len(seats) < 2:
            continue
        compared += 1
        one, two = seats[min(seats)], seats[max(seats)]
        assert one == two, (
            "a duty holding one action stands its people at %s and one holding two at %s"
            % (one, two))
    assert compared > 100, "only %d rectangles were asked at both action counts" % compared


def test_a_figure_stands_centred_on_its_slot_rather_than_beside_it(tmpl):
    """The slot's middle, less half a figure -- and the half is the whole guard.

    EVERYTHING ELSE ABOUT THIS IS CHECKED IN placeFor, which publishes the four slot middles and
    is run by the sweep above. What no sweep can see is what drawFigures does with them: it
    places a figure by its LEFT edge, so a line that forgot to take half the figure off would
    put every acolyte half a body to the right of the thing it stands over -- about 25 pixels,
    on all nine rectangles, with the arithmetic behind it still perfectly correct.

    AND THE FALLBACK HAS TO STAY A FALLBACK. Reading the spread's expression where the slots
    exist is the other half of the same mistake: the people would be evenly spaced and line up
    with nothing, which is exactly what the board did before.

    Falsify: drop the `- fw / 2`, or place from `r.figLeft` where `r.seats` is set.
    """
    body = _code(_function(tmpl, "drawFigures"))
    assert re.search(r"x = r\.seats\[j\] - fw / 2;", body), (
        "a figure is no longer centred on the slot it stands over:\n%s" % body)
    # THE TWO BRANCHES ARE IN THE RIGHT ORDER, which a regex for each cannot tell on its own.
    i, k = body.index("r.seats[j] - fw / 2"), body.index("r.figLeft + slack / 2")
    assert i < k, "the even spread is being taken before the slots are looked at"


def test_every_seat_stands_on_every_duty_in_the_demo_deal(geo):
    """Four acolytes, four slots, on all eight tiles -- which is what makes the alignment
    checkable by looking.

    THE BOARD IS A BENCH BEFORE IT IS A GAME. A duty's line has four places on it and a player's
    figures stand over them one each; on a tile where the fourth seat has nobody, the fourth
    column is empty and "seat four stands over the resource" is a claim rather than something
    anybody can see. The deal used to leave p4 off the board entirely, so the one alignment
    hardest to get right was the one never on screen.

    AND THE DEGENERATE CASE DID NOT GO WITH IT. A seat standing nowhere is still driven, by a
    seat of the tests' own -- see `nowhere` in the pool fixture -- rather than by whichever seat
    the demo happens to leave out. A deal arranged for looking at is the wrong place to keep it.

    Falsify: drop a seat from any duty in V2_SEATS.
    """
    seats = _v2_seats()
    players = [p["id"] for p in geo.as_dict()["players"]]
    duties = [slug for slug, _name, _deg in geo.DUTIES]
    assert sorted(seats) == sorted(duties), (
        "the deal covers %s and the ring has %s" % (sorted(seats), sorted(duties)))
    for slug in duties:
        missing = [p for p in players if p not in seats[slug]]
        assert not missing, (
            "%s has nobody from %s standing on it, so %s of the four slots below it cannot be "
            "checked against anybody" % (slug, ", ".join(missing), len(missing)))


@needs_node
def test_the_acolytes_stand_at_one_pitch(sweep):
    """Evenly spaced, because the slots they stand over are.

    THIS IS THE WHOLE REASON THE BOXES ARE EVEN. The line was laid out the other way for an
    afternoon -- slots as wide as the drawings they hold, with the space between the pictures
    shared equally -- and the people above it inherited slot middles that were not evenly
    spaced: a figure beside a narrow drawing came within a pixel of its neighbour while the one
    beside the wheat stalk had a hand's width of air. Four figures of one width cannot be evenly
    spaced over unevenly spaced slots; the drawings gave way instead.

    Falsify: size a slot from the drawing it holds.
    """
    checked = 0
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        seats = row["plate"]["seats"]
        if not seats or len(seats) < 3:
            continue
        pitch = seats[1] - seats[0]
        for k in range(2, len(seats)):
            assert abs((seats[k] - seats[k - 1]) - pitch) < 1e-9, (
                "%s: seat %d stands %g past the one before it and seat 2 stands %g past seat 1"
                % (_tag(row), k + 1, seats[k] - seats[k - 1], pitch))
        checked += 1
    assert checked > 500, "only %d lines were measured" % checked


@needs_node
def test_a_drawing_is_one_height_and_centred_in_its_slot(tmpl, geo):
    """Driven with shapes nothing like each other, because squares prove nothing here.

    THE SWEEP RUNS ON SQUARES. placeFor's own default is a square drawing in every slot, which is
    what every guard above is written against -- and in a line of squares, "centred in its slot"
    and "flush with its slot" are the same arithmetic. The two drawings this board actually has
    trouble with are a stone block at 1.30 and a wheat stalk at 0.29, so they are what this runs.

    ONE HEIGHT IS THE CLAIM THAT MAKES THEM A SET. Fit each drawing to its box instead and the
    wide ones come out short and the narrow ones tall, which is what the board looked like before
    any of this: four pictures in four identical boxes, all apparently different sizes.

    Falsify: fit the drawings to their boxes, or anchor them to a slot's left edge.
    """
    shapes = [1.30, 0.29, 0.687, 1.00]
    body = _node("\n".join([
        "var GEO = %s;" % json.dumps(geo.as_dict()),
        "var CELL_BORDER = %s;" % _decl(tmpl, "CELL_BORDER"),
        "var PLATE_DROP = %s;" % _decl(tmpl, "PLATE_DROP"),
        "var PLATE_BORDER = %s;" % _decl(tmpl, "PLATE_BORDER"),
        "var LINE_MIN_GAP = %s;" % _decl(tmpl, "LINE_MIN_GAP"),
        "var MERCHANT = {h: 1.4547, src: \"\"};",
        "var MERCHANT_FLOOR = %s;" % _decl(tmpl, "MERCHANT_FLOOR"),
        "var DUTIES = %s;" % json.dumps({"a": {"actions": 1}, "b": {"actions": 2}}),
        "var GRID = {merch: 100};",
        _function(tmpl, "mostActions"),
        _function(tmpl, "plateHeight"),
        _function(tmpl, "plateFor"),
        _function(tmpl, "slotsFor"),
        _function(tmpl, "inkAt"),
        _function(tmpl, "plateInset"),
        _function(tmpl, "markAt"),
        _function(tmpl, "titheMarkAt"),
        _function(tmpl, "merchantAt"),
        _function(tmpl, "placeFor"),
        "var r = {x: 100, y: 200, width: 236, height: 165};",
        "var SHAPES_IN = %s;" % json.dumps(shapes),
    ]), "(function(){ var L = placeFor(r, 2, true, SHAPES_IN, {band: 36, box: 47}); "
        "  return {marks: [markAt(L.p, 0), markAt(L.p, 1)], tithe: L.titheMark, "
        "          merchant: L.merchant, seats: L.seats, at: L.p.line.at, box: L.p.line.box, "
        "          band: L.p.line.band, x: L.x, plateY: L.y}; })()")

    band, box = body["band"], body["box"]
    drawn = [(body["marks"][0], shapes[0]), (body["marks"][1], shapes[1])]
    for mark, aspect in drawn:
        assert abs(mark["h"] - band) < 1e-9, (
            "a mark of aspect %.2f is %g tall and the band is %g" % (aspect, mark["h"], band))
        assert abs(mark["w"] - band * aspect) < 1e-9, (
            "a mark of aspect %.2f is %g wide, which is not that shape at %g tall"
            % (aspect, mark["w"], band))
    # CENTRED, which is only visible when the drawing is narrower than its slot. A mark is
    # placed against the frame's PADDING box, one border inside its outer edge, so that border
    # is paid before the two middles are compared -- the omission this file has been bitten by
    # three times.
    pb = float(_decl(tmpl, "PLATE_BORDER"))
    for k, (mark, aspect) in enumerate(drawn):
        drawn_mid = body["x"] + pb + mark["left"] + mark["w"] / 2
        slot_mid = body["x"] + body["at"][k] + box / 2
        assert abs(drawn_mid - slot_mid) < 1e-9, (
            "the mark of aspect %.2f is centred at %g and its slot at %g"
            % (aspect, drawn_mid, slot_mid))
    assert abs(body["tithe"]["h"] - band) < 1e-9, "the resource is not the band's height"
    assert abs(body["merchant"]["h"] - band) < 1e-9, "the merchant is not the band's height"
    # AND THE SEATS ARE THE SLOT MIDDLES, whatever is drawn in them.
    for k in range(len(body["seats"])):
        assert abs(body["seats"][k] - (body["x"] + body["at"][k] + box / 2)) < 1e-9, (
            "seat %d does not stand over the middle of slot %d" % (k + 1, k + 1))


@needs_node
def test_four_figures_fit_between_the_slots_they_stand_over(sweep):
    """The pitch is wider than the row allows a figure to be, so nobody overlaps anybody.

    DRAWN FIGURES ARE SIZED BY THE ROW AND PLACED BY THE SLOTS, and those are two different
    numbers. While the slots were as wide as the drawings they held, the gap between two of them
    could close to nothing and the people above them walked into each other -- which is what the
    even boxes fixed. This is the claim that replaced the cap drawFigures briefly grew: a quarter
    of the figure row is never wider than the distance between two slot middles.

    Falsify: narrow a slot to its drawing, or widen the figure row past the rectangle.
    """
    checked = 0
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        pl = row["plate"]
        seats = pl["seats"]
        if not seats or len(seats) < 2:
            continue
        pitch = seats[1] - seats[0]
        room = (pl["figRight"] - pl["figLeft"]) / 4
        assert room <= pitch + 1e-9, (
            "%s: the row allows a figure %g wide and the slots are %g apart, so two of them "
            "overlap" % (_tag(row), room, pitch))
        checked += 1
    assert checked > 500, "only %d lines were measured" % checked


@needs_node
def test_the_widest_drawing_on_the_board_still_fits_its_slot(tmpl, geo):
    """The box is sized FROM the widest drawing, which is the only order that works.

    ONE HEIGHT AND EVEN BOXES ARE TWO CLAIMS AND THEY CONSTRAIN EACH OTHER. Pick the box first
    and the broadest drawing -- a block of stone at 1.30 against a wheat stalk at 0.29 -- has to
    shrink to fit it, and shrinking takes its height with it: the set stops being one size, which
    was the whole point. So the height is whatever makes the widest drawing exactly fill a box,
    and every narrower one keeps air at its sides.

    THE SWEEP CANNOT SEE THIS. It drives placeFor with square drawings and a band handed to it,
    which is the arithmetic below the decision; bandFor is where the decision is, it reads the
    whole board to make it, and nothing else in this file runs it.

    Falsify: drop the divide by the widest aspect, or measure the merchant at the trade slider's
    size, which would shrink every icon on the board as it was dragged.
    """
    shapes = {"seal:a:actionA": 1.30, "seal:a:actionB": 0.29,
              "seal:b:actionA": 1.00, "seal:b:actionB": 0.90, "tithe:x": 1.21}
    duties = {"a": {"actions": 2, "tithe": "x", "actionA": {"seal": "seal:a:actionA"},
                    "actionB": {"seal": "seal:a:actionB"}},
              "b": {"actions": 2, "tithe": None, "actionA": {"seal": "seal:b:actionA"},
                    "actionB": {"seal": "seal:b:actionB"}}}
    merch_h = 1.4547
    body = _node("\n".join([
        "var GEO = %s;" % json.dumps({"duties": [{"slug": "a"}, {"slug": "b"}],
                                      "canvas": geo.as_dict()["canvas"],
                                      "ribbon": geo.as_dict()["ribbon"],
                                      "marks": geo.as_dict()["marks"]}),
        "var CELL_BORDER = %s;" % _decl(tmpl, "CELL_BORDER"),
        "var LINE_MIN_GAP = %s;" % _decl(tmpl, "LINE_MIN_GAP"),
        "var MERCHANT = {h: %s, src: \"\"};" % merch_h,
        "var SHAPES = %s;" % json.dumps(shapes),
        "var DUTIES = %s;" % json.dumps(duties),
        "var GRID = {merch: 200};",
        "function dutyOf(slug){ return DUTIES[slug]; }",
        _function(tmpl, "mostActions"),
        _function(tmpl, "plateHeight"),
        _function(tmpl, "plateFor"),
        _function(tmpl, "lineShapes"),
        _function(tmpl, "bandFor"),
    ]), "(function(){ var P = plateFor(236, 165, 2); var L = bandFor(P); "
        "  return {band: L.band, box: L.box, span: P.span, gaps: P.gaps, most: P.most, "
        "          sz: P.sz}; })()")

    widest = max(list(shapes.values()) + [1 / merch_h])
    assert body["band"] * widest <= body["box"] + 1e-9, (
        "the widest drawing is %g wide at a band of %g and its box is %g, so it is drawn outside "
        "its own slot" % (body["band"] * widest, body["band"], body["box"]))
    assert body["band"] <= body["sz"] + 1e-9, (
        "the drawings are %g tall against a %g mark" % (body["band"], body["sz"]))
    n = body["most"] + 2
    g = (body["span"] - n * body["box"]) / body["gaps"]
    assert g >= float(_decl(tmpl, "LINE_MIN_GAP")) - 1e-9, (
        "the line comes out spaced %g apart, under its own minimum" % g)
    # AND THE TRADE SLIDER IS NOT ALLOWED TO DECIDE IT. This runs at 200%, where a merchant
    # measured at its drawn size would be the widest thing on the board by a distance.
    assert abs(body["band"] - min(body["sz"], body["box"] / widest)) < 1e-9, (
        "the band moved with the trade slider: %g" % body["band"])


@needs_node
def test_the_city_stands_its_people_at_the_same_pitch_as_a_duty(sweep):
    """The ninth rectangle has no line, and it spaces its four columns like the eight that do.

    IT HAD A SPREAD OF ITS OWN -- four figures and three gaps shared across the rectangle --
    which was the right answer while the duties had one too. The day the duties started standing
    their people over the slots on their own lines, the City became the one tile where the
    distance between two acolytes meant something different, and on a board whose whole job is
    comparing nine piles that is the worst place for an exception.

    SO IT BORROWS THE PITCH. Every cell in the wheel is the same size, so the line the City does
    not draw would have the same slots as the one next door; its four columns are centred on its
    middle at that spacing.

    Falsify: give the City its own spread again, or centre it on anything but the rectangle.
    """
    # THE SWEEP DOES NOT PLACE THE CITY -- it has no plate and no line -- so what is held here is
    # the number it borrows: a duty's seats are exactly one slot plus one gap apart, which is
    # what drawGrid centres four City columns on. The guard below holds that it reads it from
    # placeFor rather than working it out a second time.
    checked = 0
    for row in sweep:
        if row["centre"] or not row.get("plate") or not row["plate"]["hasPlate"]:
            continue
        pl = row["plate"]
        pitch = pl["box"] + pl["g"]
        seats = pl["seats"]
        if not seats:
            continue
        assert abs((seats[1] - seats[0]) - pitch) < 1e-9, (
            "%s: a duty's seats are %g apart and its slots are %g"
            % (_tag(row), seats[1] - seats[0], pitch))
        checked += 1
    assert checked > 500, "only %d lines were measured" % checked


def test_the_city_reads_its_pitch_off_a_line_rather_than_inventing_one(tmpl):
    """drawGrid is the one function the guards cannot call, so its source is asked instead.

    THE CITY'S FOUR COLUMNS ARE PLACED IN drawGrid, in the branch that returns before any line
    is drawn -- there is no plate, no marks and no resource on that rectangle. The pitch
    therefore has to come from placeFor, run against the City's own rectangle, or it is a second
    copy of the line's arithmetic living where nothing can compare it.

    Falsify: type a pitch into the City's branch, or spread its people across the rectangle.
    """
    body = _code(_function(tmpl, "drawGrid"))
    city = body[:body.index("GRIDPOS.city")]
    assert "placeFor(r, 1, false, null, LINE)" in city, (
        "the City no longer asks placeFor for the line it would have had:\n%s" % city[-600:])
    assert re.search(r"r\.seats\.push\(cmid \+ \(cs - 1\.5\) \* cpitch\)", city), (
        "the City's four columns are no longer centred on its middle at the line's own pitch")


def test_both_places_that_draw_the_rim_ask_the_one_rule(tmpl):
    """render() and drawGrid()'s post-rebuild sweep go through dutyChosen, not through a copy.

    THIS IS THE GUARD FOR A DRIFT THAT ALREADY HAPPENED. render() held the rule in full and the
    sweep held `d.slug === S.duty` alone, so with a tithe taken one slider drag put the gold back
    on the grid cell while its own tile stayed clear -- the two halves of a single answer visibly
    disagreeing until the next render(). Only the sliders call drawGrid() without a render()
    behind it, which is why no player met it and a tuning session did.

    THE TAKE TITHE BOX IS LEFT OUT ON PURPOSE. It asks `S.slot === TITHE_SLOT` directly, which is
    not this rule and not a copy of it: it is the other side of the same choice, and the box has
    no duty to be chosen for.

    Falsify: inline the comparison at either site, or let the sweep ask about S.duty alone.
    """
    rend = _code(_function(tmpl, "render"))
    grid = _code(_function(tmpl, "drawGrid"))
    assert re.search(r"var chosen = dutyChosen\(d\.slug\);", rend), (
        "render() no longer takes the rule from dutyChosen()")
    assert rend.count('classList.toggle("sel", chosen)') == 2, (
        "render() lights the tile and its grid cell from one word; it now lights %d that way"
        % rend.count('classList.toggle("sel", chosen)'))
    assert 'classList.toggle("sel", dutyChosen(d.slug))' in grid, (
        "drawGrid()'s post-rebuild sweep no longer asks dutyChosen()")
    for name, body in (("render", rend), ("drawGrid", grid)):
        assert not re.search(r'toggle\("sel",[^)]*S\.duty', body), (
            "%s compares S.duty where it draws the rim instead of asking dutyChosen()" % name)


def test_the_action_row_wears_the_wheels_three_states(tmpl):
    """The cards and the Tithe box say rest, hover and chosen in the rectangles' own colours.

    THE TWO HALVES OF THE BOARD USED TO DISAGREE ABOUT WHAT AN EDGE MEANS. The nine rectangles
    have had three states since they replaced the wheel; the action row had one -- a card at rest
    carried no frame at all and hover was said entirely by the picture lifting -- so the only
    edge-state the row could show was the gold, and an edge meant "chosen" above the fold and
    "this is a thing" below it.

    AND IT IS ONE TOKEN, NOT TWO MATCHING NUMBERS. --edge and --edge-lit exist because four rules
    read them; --line already named the third. A guard that allowed the literals back would allow
    the row and the wheel to drift a shade apart, which is the failure that cannot be seen in a
    screenshot of either one alone.

    OUTLINE ON THE ROW, BORDER ON THE RECTANGLES, AND THAT ASYMMETRY IS LOAD-BEARING. `.art` is
    overflow:hidden round an image at width:100% and `.panel`'s contents are absolutely positioned
    against its padding box, so a border on either would move pixels geometry.py owns. The colours
    are shared; the property carrying them cannot be.

    Falsify: type a literal back into any of the six declarations, or give the row a border.
    """
    root = _rule(tmpl, ":root")
    assert root.get("--edge") and root.get("--edge-lit"), (
        "the rest and hover edges are no longer names, so nothing holds the row and the wheel "
        "to one pair of colours: %s" % {k: v for k, v in root.items() if "edge" in k})

    for name, rule, prop in (
            (".dcell", _rule(tmpl, ".dcell"), "border"),
            (".art", _rule(tmpl, ".art"), "outline"),
            (".panel", _rule(tmpl, ".panel"), "outline")):
        assert rule.get(prop) == "2px solid var(--edge)", (
            "%s no longer draws its rest edge from --edge: %s" % (name, rule.get(prop)))

    assert _rule(tmpl, ".dcell.lit").get("border-color") == "var(--edge-lit)", (
        "the rectangles' hover no longer comes from --edge-lit")
    assert _rule(tmpl, ".art:hover, .panel:hover").get("outline-color") == "var(--edge-lit)", (
        "the row's hover no longer comes from --edge-lit")

    assert _rule(tmpl, ".dcell.sel").get("border-color") == "var(--line)", (
        "the rectangles' chosen edge no longer comes from --line")
    assert _rule(tmpl, ".art.sel, .panel.sel").get("outline-color") == "var(--line)", (
        "the row's chosen edge no longer comes from --line")

    # AND THE ROW KEEPS ITS LAYOUT OUT OF IT. A border here would rescale fourteen pictures and
    # walk the Tithe's label and three slots a pixel; the transparent border on .panel is what
    # holds that box's shape now that its edge is painted rather than laid out.
    assert "transparent" in _rule(tmpl, ".panel").get("border", ""), (
        "the Tithe box's border is carrying colour again, so its contents move with it")
    for name in (".art", ".panel"):
        assert "px solid var(--edge)" not in _rule(tmpl, name).get("border", ""), (
            "%s draws its rest edge with a border, which changes the box" % name)


def test_the_card_crossfades_between_its_two_pictures(tmpl):
    """Rest is the cold picture, hover is 65% of the colour one, chosen is all of it.

    ONE DRAWING, TWO FILES, AND NO THIRD STATE TO PAINT. The cold layer is a luminance-to-palette
    grade of the colour one -- nothing resized or regenerated -- so the two sit pixel over pixel
    and an opacity between them reads as colour arriving rather than as two pictures dissolving.
    tests/layout_lab/test_board_v2_attribution.py holds that claim by re-running the transform.

    65% IS NOT A SATURATION OF 65% and the two cannot be swapped. This is 65% of the colour
    picture over 35% of the cold one; a saturation filter moves each pixel along its own hue axis
    and cannot reach this palette at all, which is the whole reason there are two files to ship.

    ORDER CARRIES THE PRECEDENCE, because all four rules weigh the same. Hover before chosen, so
    a chosen card under the pointer stays in full colour; both before `nocold`, so an action
    whose cold layer is missing shows its colour picture outright instead of fading to nothing.

    Falsify: reorder the three rules, or let the pictures lay out in flow instead of on top of
    each other.
    """
    base = _rule(tmpl, ".art img")
    assert base.get("position") == "absolute" and base.get("inset") == "0", (
        "the two pictures no longer share one rectangle, so they stack in flow: %s" % base)
    assert _rule(tmpl, ".art img.hot").get("opacity") == "0", "the card does not open cold"
    assert _rule(tmpl, ".art:hover img.hot").get("opacity") == ".65", "hover is not 65% colour"
    assert _rule(tmpl, ".art.sel img.hot").get("opacity") == "1", "chosen is not full colour"
    assert _rule(tmpl, ".art.nocold img.hot").get("opacity") == "1", (
        "an action with no cold twin no longer shows its colour picture, so it draws as blank")

    css = _rule_free(tmpl)
    hover, sel, nocold = (css.index(".art:hover img.hot"), css.index(".art.sel img.hot"),
                          css.index(".art.nocold img.hot"))
    assert hover < sel < nocold, (
        "the crossfade rules are out of order, so hover beats chosen or a missing twin fades: "
        "hover@%d sel@%d nocold@%d" % (hover, sel, nocold))

    draw = _code(_function(tmpl, "render"))
    assert 'a.art.replace("art:", "cold:")' in draw, (
        "the cold twin is no longer found from the colour key, so an action that gains a layer "
        "has to be taught about somewhere else as well")
    assert 'classList.toggle("nocold", !cold)' in draw, (
        "nothing tells the card whether it has a cold twin")
    assert draw.index('classList.toggle("nocold"') < draw.index("if (has){"), (
        "`nocold` is set inside the branch that has a picture, so a card that loses its twin "
        "keeps the old answer -- innerHTML clears children, not classes")
    assert draw.index('ci.className = "cold"') < draw.index('im.className = "hot"'), (
        "the colour picture is appended first, so the cold one covers it and nothing fades")
