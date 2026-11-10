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
import importlib.util
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
TOOL = BOARD / "action_board"
TMPL = TOOL / "action_board_v2.html.tmpl"
UPSTREAM_HOOD = ROOT / "ui" / "render" / "population_sets.py"
# Kept in the tree, drawn by nothing. See test_no_rectangle_carries_a_name_any_more.
BANNERS_DIR = BOARD / "duty_actions" / "banners"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

# THE SLIDERS' FULL TRAVEL, AND BOTH ENDS OF IT. Every overflow this file exists to catch was
# found at an END rather than in the middle: the plate hung out of the box at size 40, and
# Ordination landed at x -12 at the opening default of edge 40. The middle values are the
# defaults and two odd numbers, because an arrangement that only works on multiples of ten works
# by luck. `test_the_sweep_covers_the_sliders_the_page_actually_offers` holds these against the
# <input> elements, so widening a slider cannot quietly leave half of it unswept.
GAPS = (0, 1, 73, 115, 150)
DISPS = (0, 1, 60, 97, 150)
SIZES = (40, 62, 90, 100, 160)
# The height slider only goes UP from the 2:1 rectangle, so 100 is its floor and
# every claim about 2:1 is a claim about that one value.
HEIGHTS = (100, 130, 175, 250)
NACTS = (1, 2)


def _grid_defaults() -> dict:
    """The sliders' opening values, read out of the generator rather than restated here.

    Read as TEXT rather than imported: importing the generator pulls in v1 and everything v1
    imports, for one dict. A regex over one literal line is the cheaper and more honest read.
    """
    src = (TOOL / "generate_action_board_v2.py").read_text(encoding="utf-8")
    m = re.search(r"^GRID_DEFAULTS\s*=\s*(\{.*?\})\s*$", src, re.M)
    assert m, "the generator no longer declares GRID_DEFAULTS on one line"
    out = {}
    for k, v in re.findall(r"\"(\w+)\":\s*(True|False|-?\d+)", m.group(1)):
        out[k] = {"True": True, "False": False}.get(v, v)
        if isinstance(out[k], str):
            out[k] = int(out[k])
    return out


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
        "var GRID = {gap: 0, disp: 0, size: 100, height: 100};",
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
        _function(tmpl, "plateHang"),
        _function(tmpl, "cellRect"),
        _function(tmpl, "placeFor"),
        # Flattened, so the tests below read one dict per rectangle rather than a nest.
        "function placed(r, nAct){",
        "  var L = placeFor(r, nAct), P = L.p;",
        "  return {sz: P.sz, rowW: P.rowW, plateX: L.x, plateY: L.y,",
        "          plateW: L.has ? P.width : 0, plateH: L.has ? P.height : 0,",
        "          fullH: P.height, fullW: P.width, hasPlate: L.has,",
        "          igap: P.igap, ip: P.ip, mg: P.mg, inset: P.inset,",
        "          innerW: P.innerW, innerH: P.innerH, hang: plateHang(),",
        "          figLeft: L.figLeft, figRight: L.figRight};",
        "}",
        "var GAPS = %s, DISPS = %s, SIZES = %s, HEIGHTS = %s, NACTS = %s;" % (
            json.dumps(list(GAPS)), json.dumps(list(DISPS)), json.dumps(list(SIZES)),
            json.dumps(list(HEIGHTS)), json.dumps(list(NACTS))),
        "var out = [];",
        "GAPS.forEach(function(gap){ DISPS.forEach(function(disp){",
        "  SIZES.forEach(function(size){ HEIGHTS.forEach(function(height){",
        "    GRID = {gap: gap, disp: disp, size: size, height: height};",
        "    var area = gridArea(), cells = gridCells();",
        "    NACTS.forEach(function(n){",
        "      cells.forEach(function(c){",
        "        var row = {gap: gap, disp: disp, size: size, height: height, nAct: n,",
        "                   area: area, cell: c, centre: c.centre};",
        # The rounding is the template's own: drawGrid() rounds the rectangle before anything
        # inside it is measured, so the plate is worked out against the integers the page uses.
        "        if (!c.centre){",
        "          var r = cellRect(c);",
        "          row.r = r; row.plate = placed(r, n);",
        "        }",
        "        out.push(row);",
        "      });",
        "    });",
        "  }); });",
        "}); });",
        "process.stdout.write(JSON.stringify(out));",
    ])
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert done.returncode == 0, (
        "the template's own grid arithmetic would not run:\n%s" % done.stderr[-3000:])
    rows = json.loads(done.stdout)
    assert len(rows) == (len(GAPS) * len(DISPS) * len(SIZES) * len(HEIGHTS)
                         * len(NACTS) * 9), (
        "the sweep produced %d rectangles" % len(rows))
    return rows


def PLATE_DROP_OF(text: str) -> float:
    """How far the icon plate hangs below the bottom line, read off the page rather than typed."""
    return float(_decl(text, "PLATE_DROP"))


def _tag(row):
    at = "cell (col %d, row %d)" % (row["cell"]["col"], row["cell"]["row"])
    return "gap %d, edge %d, size %d, height %d, %d action(s), %s" % (
        row["gap"], row["disp"], row["size"], row["height"], row["nAct"], at)


def _arrangements(rows):
    """One entry per (gap, edge, size): its area and its nine cells, with actions collapsed.

    The cells do not depend on the action count, so the tests about the GRID walk this and the
    tests about the plate walk the rows.
    """
    seen = {}
    for row in rows:
        if row["nAct"] != NACTS[0]:
            continue
        key = (row["gap"], row["disp"], row["size"], row["height"])
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
    for ident, values in (("rGap", GAPS), ("rDisp", DISPS), ("rSize", SIZES),
                          ("rHeight", HEIGHTS)):
        m = re.search(r"<input type=range id=%s min=(-?\d+) max=(-?\d+)" % ident, tmpl)
        assert m, "the template has no `<input type=range id=%s min=.. max=..>`" % ident
        lo, hi = int(m.group(1)), int(m.group(2))
        assert min(values) == lo and max(values) == hi, (
            "%s runs %d to %d and the sweep covers %d to %d"
            % (ident, lo, hi, min(values), max(values)))


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
        box, c = row["area"], row["cell"]
        assert c["x"] >= box["x"] - 1e-9, (
            "%s: starts at x %g, left of %g" % (_tag(row), c["x"], box["x"]))
        # THE TOP IS A CLAIM AT HEIGHT 100 ONLY. The height slider grows the rectangles upward
        # on purpose and is allowed to take them past the area -- that is the trade it makes to
        # keep every bottom edge where it was, and the readout reports it in amber. Everything
        # else about the box still has to stay inside.
        if row["height"] == 100:
            assert c["y"] >= box["y"] - 1e-9, (
                "%s: starts at y %g, above %g" % (_tag(row), c["y"], box["y"]))
        assert c["x"] + c["width"] <= box["x"] + box["width"] + 1e-9, (
            "%s: reaches x %g, past %g"
            % (_tag(row), c["x"] + c["width"], box["x"] + box["width"]))
        assert c["y"] + c["height"] <= box["y"] + box["height"] + 1e-9, (
            "%s: reaches y %g, past %g"
            % (_tag(row), c["y"] + c["height"], box["y"] + box["height"]))


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
def test_everything_drawn_is_centred_in_the_area_at_every_setting(sweep):
    """Centred was asked for by name, and off-centre by a few pixels is invisible one slider at a
    time and obvious across the three.

    TWO CLAIMS, NOT ONE, BECAUSE THE DRAWING IS NO LONGER THE RECTANGLES. Across, the arrangement
    IS the nine outlines: a plate is centred under its own rectangle and never wider than it, so
    the left and right edges are the rectangles'. Down, the plates hang below the bottom row and
    reach 62px past it at the opening settings -- so centring the outlines alone put equal slack
    above and below the OUTLINES and visibly more above than below the DRAWING.

    The horizontal claim is about the cells at every setting; the vertical one is about the
    cells plus the hang, and only at height 100 -- the height slider grows the rectangles upward
    deliberately and is allowed to take their tops past the area, which is what keeps every
    bottom edge where it was. That is also why the centring adds the displacement back --
    `(width - (bw + 2*d))/2 + d` -- which is exactly the term a simplification would drop,
    because on the face of it the `+ d` looks like it cancels.

    Falsify: drop the `+ d` from either `ox` or `oy`, or drop `hang` from `oy`.
    """
    for key, a in _arrangements(sweep).items():
        area, cells = a["area"], a["cells"]
        left = min(c["x"] for c in cells)
        right = max(c["x"] + c["width"] for c in cells)
        top = min(c["y"] for c in cells)
        bot = max(c["y"] + c["height"] for c in cells)
        tag = "gap %d, edge %d, size %d, height %d" % key
        assert abs((left - area["x"]) - (area["x"] + area["width"] - right)) < 1e-6, (
            "%s: %g of slack on the left and %g on the right"
            % (tag, left - area["x"], area["x"] + area["width"] - right))
        # The reserve the arrangement was centred on, which is capped by the room available --
        # so on a tall arrangement it is less than a plate's full hang, and the plates that then
        # run off the board are refused and counted rather than drawn.
        hang = a["hang"]
        if key[3] != 100:
            continue                # the height slider raises the tops on purpose; see below
        assert abs((top - area["y"])
                   - (area["y"] + area["height"] - (bot + hang))) < 1e-6, (
            "%s: %g of slack above the rectangles and %g below the plates that hang under them "
            "(the hang is %g)"
            % (tag, top - area["y"], area["y"] + area["height"] - (bot + hang), hang))


@needs_node
def test_the_room_reserved_for_the_plates_is_the_room_they_take(sweep, tmpl):
    """THE RESERVE AND THE DRAWING ARE TWO EXPRESSIONS AND MUST AGREE.

    `gridCells` reserves `plateHang()` below the bottom row before it centres anything;
    `drawGrid` then places each plate at `r.y + r.height + PLATE_DROP`. If the reserve were
    computed from a different plate -- a different action count, say -- the arrangement would be
    centred on a hang that is not the one drawn, and the whole wheel would sit a few pixels off
    with nothing to compare it against.

    THE RESERVE IS CAPPED BY THE ROOM LEFT, so it is allowed to be SHORT of what a plate takes:
    the rectangles are sized before the hang is known -- `fit` cannot account for it without
    solving for its own output -- and an arrangement that already fills the area vertically has
    nothing left to hold back. Taking it anyway pushed the top row 24px above the area and within
    4px of the card row. So the claim is one-directional, except at the opening defaults, where
    the room has to be there.

    Falsify: drop the PLATE_DROP from plateHang, or remove the cap so the reserve exceeds
    what is drawn.
    """
    d = _grid_defaults()
    defaults = (d["gap"], d["disp"], d["size"], d["height"])
    for row in sweep:
        if row["centre"]:
            continue
        p, r = row["plate"], row["r"]
        reserved = row["cell"]["hang"]
        want = PLATE_DROP_OF(tmpl) + p["fullH"]
        assert reserved <= want + 1e-9, (
            "%s: %g is reserved below the rectangle and a plate only ever takes %g"
            % (_tag(row), reserved, want))
        if (row["gap"], row["disp"], row["size"], row["height"]) == defaults:
            # AND AT THE SETTINGS THE BOARD OPENS ON, THE CAP MUST NOT BITE. Everywhere else the
            # reserve is allowed to be short -- the rectangles are sized before the hang is known
            # -- but a board whose own defaults cannot hold their plates is a board that opens
            # unbalanced, which is the thing this reserve was added for.
            assert abs(reserved - want) < 1e-6, (
                "%s: the board opens on these settings and reserves %g where a plate takes %g"
                % (_tag(row), reserved, want))
        if p["hasPlate"]:
            drawn_to = (p["plateY"] + p["fullH"]) - (r["y"] + r["height"])
            assert abs(want - drawn_to) < 1e-9, (
                "%s: the reserve is built for %g below the rectangle and the plate reaches %g"
                % (_tag(row), want, drawn_to))


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
        gap, disp, size, _height = key
        if disp == 0:
            continue                    # nothing to measure, and the test above covers it
        at = {(c["col"], c["row"]): c for c in a["cells"]}
        tag = "gap %d, edge %d, size %d, height %d" % key
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
    a = _arrangements(sweep)[(0, 0, 100, 100)]
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
    the canvas -- which lined it up with the BOARD rather than with the things on the board. The
    card row stops at the Tithe's right edge, 198 short of that mirror margin, so the grid was
    wider than every object above it by most of a Tithe box.

    Now both ends are the ACTION CARDS: the leftmost card's left edge and the second card's
    right edge -- the two pictures the nine rectangles are a choice between. It reached the
    Tithe's right edge for a round, which lined the wheel up with a box that is not a duty. A
    constant that happened to equal today's 1004 would pass any check OF today's numbers, so
    this moves each end in turn and insists the area follows.

    Falsify: write 28, 1004 or GEO.canvas.width - 2 * m into gridArea.
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
    far = want["slots"]["actionB"]
    assert base["x"] + base["width"] == far["x"] + far["width"], (
        "the area ends at %g and the second action card at %g"
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
    g["slots"]["actionB"]["x"] -= 40
    shrunk = area(g)
    assert shrunk["x"] == base["x"], "moving the second card moved the area's LEFT edge"
    assert shrunk["width"] == base["width"] - 40, (
        "the second card moved 40 left and the width went from %g to %g"
        % (base["width"], shrunk["width"]))

    # and the Tithe is no longer one of its ends
    g = geo.as_dict()
    g["tithe"]["x"] += 55
    assert area(g)["width"] == base["width"], (
        "moving the Tithe changed the grid's width, so it is still one of the ends")


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
    m = re.search(r"print\(\"  the duty grid is centred in %d x %d at \(%d, %d\)[^\n]*\n"
                  r"\s*% \((.*?)\)\)", src, re.S)
    assert m, "the build summary no longer prints the grid's area"
    d = geo.as_dict()
    card, far = d["slots"]["actionA"], d["slots"]["actionB"]
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
        key = (row["gap"], row["disp"], row["size"], row["cell"]["col"], row["cell"]["row"])
        by.setdefault(key, {})[row["height"]] = row["cell"]
    compared = 0
    for key, at in by.items():
        base = at.get(100)
        assert base is not None, "height 100 is not in the sweep for %s" % (key,)
        for h, c in sorted(at.items()):
            tag = "gap %d, edge %d, size %d, cell (col %d, row %d) at height %d" % (key + (h,))
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

    Comment lines are stripped first, because the prose around these rules names properties and
    selectors freely and a guard that reads a comment as a declaration is a guard that fails on
    an explanation. That has happened three times on this board.
    """
    body = "\n".join(ln for ln in text.split("\n") if not ln.strip().startswith(("/*", "*", "*/")))
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
    for key, why in (((d["gap"], d["disp"], 100, 100), "where the block fills the area"),
                     ((d["gap"], d["disp"], d["size"], d["height"]), "at the opening defaults")):
        assert key in a, (
            "the sweep does not cover gap %d, edge %d, size %d, height %d -- add it to GAPS, "
            "DISPS, SIZES and HEIGHTS" % key)
    cells, area = a[(d["gap"], d["disp"], 100, 100)]["cells"], a[(d["gap"], d["disp"], 100, 100)]["area"]
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
def test_the_plate_hangs_below_the_line_and_is_centred_under_it(sweep, tmpl):
    """CENTRED AND SIX BELOW, which is the whole of what was asked for.

    The plate used to sit in the rectangle's top right corner and was bounded by it. It hangs
    under the bottom line now, which takes away every bound the cell used to give it -- so the
    two claims that replace them are held here: its middle is the rectangle's middle, and its top
    is PLATE_DROP under the line.

    Falsify: drop the `/ 2` from the centring, or replace PLATE_DROP with a literal.
    """
    drew = 0
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
        border = float(_decl(tmpl, "CELL_BORDER"))
        drop = float(_decl(tmpl, "PLATE_DROP"))
        mid_cell = r["x"] + border + (r["width"] - 2 * border) / 2.0
        mid_plate = p["plateX"] + p["plateW"] / 2.0
        assert abs(mid_cell - mid_plate) <= 0.5, (
            "%s: the rectangle's middle is %g and the plate's is %g"
            % (_tag(row), mid_cell, mid_plate))
        assert p["plateY"] == r["y"] + r["height"] + drop, (
            "%s: the line's outer edge is at %g and the plate starts at %g, which is %g below "
            "instead of %g" % (_tag(row), r["y"] + r["height"], p["plateY"],
                               p["plateY"] - (r["y"] + r["height"]), drop))
    assert drew, "no arrangement in the sweep drew a plate at all, so nothing was checked"


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
        # The plate's own border is in the declared size, because box-sizing is border-box --
        # so the ground around the mark is `ip` on every side rather than `ip` on two of them.
        border = float(_decl(tmpl, "PLATE_BORDER"))
        assert row["plate"]["fullH"] == seal + 2 * row["plate"]["ip"] + 2 * border, (
            "%s: the plate is %g tall around a %g icon with %g of padding and a %g border"
            % (_tag(row), row["plate"]["fullH"], seal, row["plate"]["ip"], border))


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

    Falsify: drop the `P.width <= P.innerW` term from placeFor's `has`.
    """
    drew = refused = 0
    for row in sweep:
        if row["centre"]:
            continue
        p = row["plate"]
        if p["hasPlate"]:
            drew += 1
            assert p["plateW"] <= p["innerW"] + 1e-9, (
                "%s: a %g-wide plate was drawn under a %g-wide rectangle"
                % (_tag(row), p["plateW"], p["innerW"]))
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
    assert re.search(r"tag\.style\.color = \(over > 0\.5 \|\| PLATES_DROPPED\)", wire), (
        "the readout does not colour itself when a duty has lost its icons, so the number is "
        "printed in the same grey as the numbers that are fine")


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
    place = re.search(r"left:\s*px\(ip \+ P\.inset \+ k \* \(sz \+ igap\)\)", tmpl)
    assert place, (
        "the icons are no longer placed at `ip + P.inset + k * (sz + igap)`, so this guard is "
        "checking an expression the page has stopped using")
    for row in sweep:
        if row["centre"] or not row["plate"]["hasPlate"]:
            continue
        p, n = row["plate"], row["nAct"]
        last = p["ip"] + p["inset"] + (n - 1) * (p["sz"] + p["igap"]) + p["sz"]
        assert last <= p["plateW"] - p["ip"] + 1e-9, (
            "%s: the last of %d icon(s) reaches %g inside a plate %g wide with %g of padding"
            % (_tag(row), n, last, p["plateW"], p["ip"]))
        assert p["sz"] + 2 * p["ip"] <= p["plateH"] + 1e-9, (
            "%s: a %g icon with %g of padding does not fit a plate %g tall"
            % (_tag(row), p["sz"], p["ip"], p["plateH"]))


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
    assert 'querySelectorAll(".dcell, .iplate")' in body, (
        "drawGrid does not sweep the plates, which are no longer children of the cells it does "
        "sweep -- so every slider event leaves nine behind")


@needs_node
def test_every_duty_gets_the_same_frame_whatever_it_holds(sweep, tmpl):
    """TWO SIZES OF THE SAME OBJECT IN ONE ROW READS AS TWO KINDS OF THING.

    Allocation and Taxation hold a single mark each and used to get a plate 74 wide against the
    other six's 130. The frame is now the widest row ANY duty needs, and a short row is centred
    in it -- so what differs between duties is the marks, not the ground they sit on.

    THE WIDTH IS COUNTED, NOT TYPED. `mostActions()` walks the duties, so a duty gaining a third
    action widens every plate to match without anything else changing. A literal 2 here would
    leave the new mark hanging off the edge of seven frames.

    Falsify: size the plate from `rowW` again, or write the full row as `2 * sz + igap`.
    """
    widths = {row["plate"]["fullW"] for row in sweep if not row["centre"]}
    assert len(widths) == 1, (
        "the plates come in %d widths (%s); one duty's frame is a different size from another's"
        % (len(widths), sorted(widths)))
    body = _code(_function(tmpl, "plateFor"))
    assert "mostActions()" in body, (
        "the frame is no longer built to the widest row any duty needs:\n%s" % body)
    assert not re.search(r"(?<!most)\b2 \* sz", body), (
        "the full row is written as a literal two marks, so a third action would hang off the "
        "edge of every frame:\n%s" % body)


@needs_node
def test_a_short_row_of_marks_is_centred_in_the_frame(sweep, tmpl):
    """ONE MARK IN A FRAME BUILT FOR TWO HAS TO SIT IN THE MIDDLE OF IT.

    The inset is the only thing that puts it there, and it is zero for a duty holding the full
    row -- so the two cases are one expression and a duty with every mark cannot be pushed off
    centre by the arithmetic that centres a duty with fewer.

    THE PLATE'S OWN BORDER IS IN THE WIDTH, which is what makes "centred" true rather than
    nearly true. `*{box-sizing:border-box}` means a plate declared 130 wide has a 128 padding
    box, and the marks are placed against that -- so a row set at `pad` from the left had `pad`
    on one side and `pad - 2` on the other. Two pixels, invisible on a pair and exactly what
    stops a single centred mark from being centred.

    Falsify: drop PLATE_BORDER from the width, or the `/ 2` from the inset.
    """
    border = float(_decl(tmpl, "PLATE_BORDER"))
    assert border > 0, "PLATE_BORDER is not positive"
    seen = set()
    for row in sweep:
        if row["centre"]:
            continue
        p, n = row["plate"], row["nAct"]
        inner = p["fullW"] - 2 * border          # the padding box the marks are placed against
        left = p["ip"] + p["inset"]
        right = inner - (left + p["rowW"])
        seen.add(n)
        assert abs(left - right) < 1e-9, (
            "%s: %d mark(s) sit %g from one end of the frame and %g from the other"
            % (_tag(row), n, left, right))
        if n == 1:
            assert p["inset"] > 0, (
                "%s: a single mark is not inset at all, so it is not centred in a frame built "
                "for more" % _tag(row))
    assert seen == set(NACTS), "the sweep did not cover every action count: %s" % sorted(seen)


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

    THE ROW'S WIDTH AND THE WIDTH THAT WOULD FILL IT ARE ONE EXPRESSION. `(4 + 3 * HOOD.gap)`
    appears in the cap and again in the slack, and if those two ever disagree the row is centred
    against a width it does not have -- which looks like a small, consistent lean.

    Falsify: drop the `/ 2`, or write the slack with a literal 4.72.
    """
    body = _code(_function(tmpl, "drawFigures"))
    m = re.search(r"var slack = \(r\.figRight - r\.figLeft\) - fw \* \(4 \+ 3 \* HOOD\.gap\);",
                  body)
    assert m, "the row's slack is no longer the span less four slots:\n%s" % body
    assert re.search(r"var x = r\.figLeft \+ slack / 2 \+ j \* \(fw \+ gap\);", body), (
        "the row is no longer placed at half the slack, so it is not centred:\n%s" % body)
    assert body.count("(4 + 3 * HOOD.gap)") == 2, (
        "`(4 + 3 * HOOD.gap)` appears %d times; it is the row's width and the width that would "
        "fill the row, and the two have to be the same expression"
        % body.count("(4 + 3 * HOOD.gap)"))


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
    defaults = (d["gap"], d["disp"], d["size"], d["height"])

    def wants_vs_allows(row):
        """What the plate asks of a figure's width, and what the row leaves for one."""
        p = row["plate"]
        return p["fullH"] / h, (p["figRight"] - p["figLeft"]) / slots

    # AT THE BOARD'S OWN DEFAULTS THE CEILING IS NOT REACHED, and that is the fact worth
    # pinning: it is the state anybody opening the page sees. If this starts failing the
    # defaults have moved into the range where the plate sets the size, and the note above --
    # and what the board looks like on opening -- both need re-reading.
    at_default = [r for r in sweep if not r["centre"] and r["plate"]["hasPlate"]
                  and (r["gap"], r["disp"], r["size"], r["height"]) == defaults]
    assert at_default, "the sweep does not cover the opening defaults"
    for row in at_default:
        wants, allows = wants_vs_allows(row)
        assert allows < wants, (
            "%s: the row now allows a %g-wide figure against the %g the plate asks for, so the "
            "acolytes ARE the plate's height at the settings the board opens on -- which they "
            "were not when this was written" % (_tag(row), allows, wants))

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
    """The template holds NO copy of any of this, so a key the page reads and `as_dict` does not
    publish is `undefined` arithmetic -- which in JavaScript is NaN, and a NaN position is a
    figure that is not on the page rather than a figure in the wrong place.

    Falsify: remove any key from hood.as_dict(), or read a new `HOOD.x` in the template.
    """
    published = set(hood.as_dict())
    read = set(re.findall(r"HOOD\.([A-Za-z_][A-Za-z0-9_]*)", tmpl))
    missing = sorted(read - published)
    assert not missing, (
        "the template reads HOOD.%s and hood.as_dict() does not publish %s"
        % (", HOOD.".join(missing), "it" if len(missing) == 1 else "them"))
    for k in ("path", "h", "face", "ink", "stroke", "swatch", "order", "step", "lean", "gap"):
        assert k in published, "hood.as_dict() no longer publishes %r" % k
