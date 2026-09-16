"""Guards for the duty wheel's 3x3 grid, one per failure that actually happened.

Nothing here is hypothetical. Every check below is a bug that shipped into a render during the
grid's build-out and was caught by eye rather than by anything automatic:

    numbering       Taxation was filed as `07`. It is index 7, so it is `08`, and the picker maps
                    NN-1 to a cell -- so Taxation drew itself in Produce's square and two rounds
                    of A/B comparison were made on a board with the wrong tile in it. Nothing
                    errored; the grid just quietly meant something else.

    resolution      Ordination B arrived at 887 px instead of 1254 and sat in the tree for a day.
                    It is 71% linear resolution, visibly softer beside its neighbours, and the
                    only signal was its file size.

    the join        The gradient that splits a two-action tile was placed from a "steepest central
                    step" heuristic, which finds the strongest vertical EDGE -- a pillar, a
                    scaffold post, a standing figure. It was wrong on all four tiles where the
                    source pair was available to check against, always by 15-17% and always to the
                    left. The joins are the midline; this holds them there.

    the slot        The component must carry no width or height, because the slot sizes it. An
                    earlier shape pass also overshot its cell and bled two columns past the grid
                    box, which is invisible until something clips.

These run in the `ui` lane, which is the lane a design-only pull request actually triggers -- AND
in the lane that runs the whole suite, which is not the same environment. The ui lane installs
pillow and numpy; the full-suite lane installs neither. This file must therefore pass with both
absent, and anything here that genuinely needs pixels says so with `pytest.importorskip` rather
than assuming.

That sentence used to name only the ui lane. Two guards were added on the strength of it, verified
where numpy exists, and failed on the lane nobody had mentioned -- a comment that was true about
where these run and silent about where else they run.
"""

from __future__ import annotations

import contextlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RENDER = REPO / "ui" / "render"
TILES = REPO / "ui" / "assets-gothic" / "duty-tiles"
SHAPES = REPO / "ui" / "assets-gothic" / "metadata" / "duty_grid_shapes.json"
TILE_PX = 1254          # the image tool's square maximum; see ui/docs/duty-wheel/
# Any single version letter, matching gen_duty_grid.find_tiles. Spelled `[AB]` this guard read a
# version C tile as a malformed FILENAME and said its number and its name disagreed, which is a
# different and much more alarming fault than the one it had found. A pattern listing the versions
# that exist has to be changed in step with the tree in every copy of it, and there were five.
NAME = re.compile(r"^(\d{2})_([a-z_]+)_([A-Z])\.(png|webp)$")


def grid():
    if not (RENDER / "gen_duty_grid.py").is_file():
        pytest.skip("gen_duty_grid.py is not in this checkout")
    import sys
    sys.path.insert(0, str(RENDER))
    import gen_duty_grid
    return gen_duty_grid


def tile_files():
    if not TILES.is_dir():
        pytest.skip("the duty tiles are not in this checkout")
    # sources/ holds the two panels each merge was made from; they are inputs, not tiles.
    return [p for p in sorted(TILES.rglob("*.*"))
            if p.suffix.lower() in {".png", ".webp"} and "sources" not in p.parts]


def test_the_picker_draws_with_the_boards_own_filters():
    """The picker's claim is that it shows what the board will show. This is that claim.

    It held three verbatim copies of the wheel's constants -- the dim filter, the lit filter, and
    the city's index -- and they agreed with the originals only because someone had typed them out
    twice. The day `DIM_SATURATE` moved from 0.40 to 1.00 the board changed and the picker did not.
    Nothing raised, nothing looked broken: the picker simply went on rendering a version of the
    board that no longer existed, which is the worst way for a comparison tool to fail, because
    every judgement made from it is confidently wrong.

    Identity, not equality. Two equal strings would pass while still being two strings, which is
    the state this is here to forbid.
    """
    g = grid()
    if not (RENDER / "gen_picker_grid.py").is_file():
        pytest.skip("gen_picker_grid.py is not in this checkout")
    import gen_picker_grid as pk
    for name in ("DIM", "LIT", "CITY"):
        assert getattr(pk, name) is getattr(g, name), (
            "gen_picker_grid.%s is not gen_duty_grid.%s -- it is a copy. The picker exists to show "
            "what the board will show, so it has to draw with the board's own filters rather than "
            "with its own equal-for-now duplicates of them. Import it." % (name, name))


def test_the_offsets_tool_lays_the_tiles_out_where_the_board_does():
    """The tool and the board must start from the same nine shapes, or the offsets mean nothing.

    They did not. gen_tile_offsets.py scaled the raw traced shapes itself and skipped `place`,
    which re-lays the nine as an even 3x3 and spreads them apart -- up to 25.6 screen px per tile,
    measured at the MARGIN of the day, 14.
    So the tool showed a tighter arrangement than the board builds, offsets dragged in it were
    judged against tiles that were never where the board would put them, and when applied they
    moved every tile by exactly the saved number and the result still looked wrong.

    That is the shape of fault worth a guard: nothing raises, nothing is measurably broken in
    either file, and the two simply disagree about the question. Compared as STRINGS rather than as
    centres, because a tile can share a centre with a different outline.
    """
    g = grid()
    if not (RENDER / "gen_tile_offsets.py").is_file():
        pytest.skip("gen_tile_offsets.py is not in this checkout")
    import re

    import gen_tile_offsets as tool
    # pop_set: the offsets are per acolyte set, so "where the board draws them" is a question
    # that now needs to name a set. The tool's own is the one to ask with -- comparing it against
    # the default would fail for a tool that is working perfectly on another set.
    # shift=False for the same reason the tool asks for it: the page translates the whole block
    # itself, so it starts from an arrangement that does not already carry the shift. This guard
    # asked WITH the shift and passed for weeks -- because the set it was asking about had a
    # saved shift of zero, and at zero the two are the same nine strings. It went red the first
    # time a real shift was saved, which is the only time it could have.
    assert tool.scaled_shapes() == g.laid_shapes(offsets=False, pop_set=tool.POP_SET,
                                                 shift=False), (
        "gen_tile_offsets.py is not drawing the tiles where gen_duty_grid.py draws them, so an "
        "offset dragged in the tool will not put a tile where you put it. The tool must ask "
        "gen_duty_grid.laid_shapes() rather than working the layout out again.")

    # And what the COMPONENT emits, because the fault that actually shipped was there rather than
    # here: the tool handed already-laid shapes back to duty_grid_svg, which laid them out and
    # offset them a second time, and the page's own script applied the file a third. The tool then
    # opened 27.1 px per tile away from the board while every function above was correct.
    clips = lambda svg: re.findall(r'<clipPath id="dg-c\d"><path d="([^"]+)"/></clipPath>', svg)
    for want_offsets in (True, False):
        drawn = clips(g.duty_grid_svg(tiles_dir=None, palettes=(), offsets=want_offsets))
        assert drawn == g.laid_shapes(offsets=want_offsets), (
            "duty_grid_svg(offsets=%r) is not drawing laid_shapes(offsets=%r). If the offsets are "
            "applied twice every saved nudge lands at double its value, and nothing raises: the "
            "tiles simply are not where the tool said they would be."
            % (want_offsets, want_offsets))


def test_every_tile_is_filed_under_the_index_its_name_claims():
    """`NN_slug_V.png` -- NN is the one-based position in DUTY_NAMES, and slug is that name.

    This is the Taxation bug. A tile whose number and slug disagree draws itself in a neighbour's
    square, silently, and every judgement made on that render is about the wrong board.
    """
    g = grid()
    slug_of = [n.lower().replace("the ", "").replace(" ", "_") for n in g.DUTY_NAMES]
    wrong = []
    for p in tile_files():
        m = NAME.match(p.name)
        if not m:
            wrong.append("%s does not match NN_slug_V.png" % p.name)
            continue
        i = int(m.group(1)) - 1
        if not 0 <= i < 9:
            wrong.append("%s has index %d, outside the nine" % (p.name, i))
        elif m.group(2) != slug_of[i]:
            wrong.append("%s is numbered %02d, which is %s (%r), not %r"
                         % (p.name, i + 1, g.DUTY_NAMES[i], slug_of[i], m.group(2)))
    assert not wrong, (
        "a duty tile's number and its name disagree. The number decides which square it is drawn "
        "in, so this does not fail loudly -- it just puts the art somewhere else:\n  "
        + "\n  ".join(wrong))


def test_no_two_tiles_of_one_version_claim_the_same_square():
    by_version: dict[str, dict[int, str]] = {}
    clash = []
    for p in tile_files():
        m = NAME.match(p.name)
        if not m:
            continue
        seen = by_version.setdefault(m.group(3).upper(), {})
        i = int(m.group(1)) - 1
        if i in seen:
            clash.append("version %s index %d: %s and %s" % (m.group(3), i, seen[i], p.name))
        seen[i] = p.name
    assert not clash, "two tiles would be drawn in one square:\n  " + "\n  ".join(clash)


def test_every_tile_is_square_and_full_resolution():
    """The Ordination B bug: 887 px in a set of 1254s, caught only by its file size."""
    Image = pytest.importorskip("PIL.Image", reason="measuring pixels needs Pillow")
    small = []
    for p in tile_files():
        w, h = Image.open(p).size
        if w != h:
            small.append("%s is %dx%d, not square" % (p.name, w, h))
        elif w != TILE_PX:
            small.append("%s is %d px, not %d (%.0f%% linear resolution)"
                         % (p.name, w, TILE_PX, w / TILE_PX * 100))
    assert not small, (
        "a duty tile is not at the size the rest of the set is drawn from. It will be visibly "
        "softer beside its neighbours and nothing else will say so:\n  " + "\n  ".join(small))


def test_the_joins_are_the_midline():
    """Measured, not assumed: all seven source pairs split at 0.4993-0.5035, and every merge
    checked against its pair kept that. A number that has drifted off 0.5 is the old
    steepest-edge heuristic creeping back in, and it puts the gold on the wrong scene."""
    path = TILES / "joins.json"
    if not path.is_file():
        pytest.skip("joins.json is not in this checkout")
    g = grid()
    data = json.loads(path.read_text())
    off = []
    for version, byindex in data.items():
        if version.startswith("_"):           # the note explaining why these are all 0.5
            continue
        for key, value in byindex.items():
            if int(key) not in g.TWO_ACTION:
                off.append("version %s records a join for index %s, which has one action"
                           % (version, key))
            elif abs(value - 0.5) > 0.02:
                off.append("version %s index %s is %.4f" % (version, key, value))
    assert not off, (
        "a join has moved off the midline:\n  " + "\n  ".join(off) + "\n"
        "The merge is two equal halves, so the join is 0.5. If a tile genuinely needs a different "
        "split, verify it against that tile's source pair first -- the edge heuristic that "
        "produced the old numbers was wrong every time it could be checked.")


def test_the_component_lets_its_slot_size_it():
    """No width or height on the root <svg>: the wheel slot decides, exactly as the circular
    wheel did. Also nine tile groups, because a missing one renders as a hole rather than an
    error and would otherwise go unnoticed."""
    g = grid()
    svg = g.duty_grid_svg(labels=g.DUTY_NAMES, tiles_dir=None)
    root = ET.fromstring(svg)
    assert "width" not in root.attrib and "height" not in root.attrib, (
        "the duty grid carries its own width/height. The slot sizes this component; a fixed size "
        "here is what made the first renders ignore the layout.")
    assert root.get("viewBox"), "the grid needs a viewBox to be sized by its slot"
    groups = root.findall('.//{http://www.w3.org/2000/svg}g[@data-duty-tile]')
    assert len(groups) == 9, "expected nine tile groups, found %d" % len(groups)


def test_the_shapes_stay_inside_the_grid_box():
    """The smoothing pass that produced these outlines is a spline, and a spline overshoots its
    control points. An earlier one bled the outer columns past the box, which shows up only when
    something clips."""
    if not SHAPES.is_file():
        pytest.skip("duty_grid_shapes.json is not in this checkout")
    g = grid()
    meta = json.loads(SHAPES.read_text())
    box = meta["box"]
    out = []
    for i, d in enumerate(meta["shapes"]):
        x0, y0, x1, y1 = g.bbox(d)
        if min(x0, y0) < 0 or max(x1, y1) > box:
            out.append("shape %d spans x %.1f..%.1f, y %.1f..%.1f in a %d box"
                       % (i, x0, x1, y0, y1, box))
    assert not out, "a tile outline leaves the grid box:\n  " + "\n  ".join(out)
    assert len(meta["shapes"]) == 9, "expected nine outlines, found %d" % len(meta["shapes"])


def test_the_chosen_version_has_artwork_for_every_square_it_claims():
    """gen_duty_grid.VERSION is what the layout tool and the board draw. A tile it cannot find
    is a flat colour in the finished wheel, which is fine while the set is being built and is not
    fine once it ships -- so this reports what is missing rather than asserting completeness."""
    g = grid()
    found = g.find_tiles(TILES, g.VERSION)
    missing = [g.DUTY_NAMES[i] for i in range(9) if i not in found]
    if missing:
        pytest.skip("version %s is still being generated; missing: %s"
                    % (g.VERSION, ", ".join(missing)))
    assert len(found) == 9


def test_a_shuffled_arrangement_is_drawn_and_a_broken_one_is_refused():
    """Duty tiles are shuffled at setup, so the component must take the arrangement rather than
    own one. The order it draws by default is a fixture and no more canonical than the two other
    arrangements in this repo (tools/ui_debug/duty_wheel_layout.json and the engine's
    _DEFAULT_DUTY_TILES, which disagree with it and with each other). What must hold is that a
    real arrangement reaches the drawing, and that one which would put two duties in a square --
    or leave one empty -- fails instead of quietly drawing a board that means something else."""
    g = grid()
    plain = g.duty_grid_svg(tiles_dir=None)
    assert plain == g.duty_grid_svg(tiles_dir=None, cells=g.DEFAULT_CELLS)
    assert plain != g.duty_grid_svg(tiles_dir=None, cells=[2, 5, 3, 8, 4, 6, 1, 7, 0]), (
        "a different arrangement drew the same picture: `cells` is not reaching the shapes")
    for bad in ([0, 1, 2, 3, 4, 5, 6, 7, 7], [0, 1, 2], list(range(9)) + [0]):
        with pytest.raises(ValueError):
            g.duty_grid_svg(tiles_dir=None, cells=bad)


def test_two_grids_on_one_page_do_not_share_ids():
    """Every id the component emits must be namespaced to its instance.

    SVG ids are document-global. Two grids in one page with the same id names means every
    `url(#...)` resolves to whichever came first, so the second grid clips its artwork to the
    FIRST one's shapes and most of its pictures land outside their tiles and disappear. Measured
    when this was real: a board that draws 55% artwork on its own drew 27% as the second on a
    page, with no error and nothing in the console. Two side-by-side grids is an ordinary thing
    to want -- comparing arrangements, showing a route in two states -- and the symptom points at
    the artwork rather than at the cause.

    Classes are deliberately NOT namespaced: they carry styling, not references, and the CSS is
    written against them.
    """
    import re
    g = grid()
    ids = lambda svg: set(re.findall(r'id="([^"]+)"', svg))
    a = ids(g.duty_grid_svg(tiles_dir=None, uid="wheelA"))
    b = ids(g.duty_grid_svg(tiles_dir=None, uid="wheelB"))
    assert a and b, "no ids emitted at all -- the check would pass vacuously"
    assert not (a & b), (
        "two grids share these ids: %s. The second one on a page will resolve them to the "
        "first's elements." % sorted(a & b)[:8])
    # and every reference must point at an id the same grid defines
    svg = g.duty_grid_svg(tiles_dir=None, uid="solo")
    refs = set(re.findall(r'url\(#([^)]+)\)', svg))
    assert refs <= ids(svg), (
        "these are referenced but never defined here: %s" % sorted(refs - ids(svg)))


def test_the_offsets_tool_watches_every_generator_it_builds_from():
    """Whatever `--serve` rebuilds a page from, it must also notice has changed on disk.

    The tool's server rebuilds the whole page on every request, and its docstring said that made a
    stale checkout impossible. It did not. Rebuilding re-opens the JSON files, because `build` and
    `dg.load` read them each call -- but `import gen_duty_grid` runs ONCE, at process start, and
    every later rebuild calls into that same module object. So a server left running across an edit
    kept serving pre-edit geometry, under a page that looked freshly built, through any number of
    hard refreshes.

    That cost three separate rounds of "the duty tiles are not where I saved them" -- the last one
    after the bug it was blamed on had already been fixed and measured at 0.001 px, which is the
    expensive part: a stale server makes a correct fix look like a failed one, so the next thing
    edited is code that was right.

    `serve` now stamps its sources and checks them per request. This guards the half of that which
    rots silently: the LIST. Importing another generator here and forgetting to watch it restores
    the original bug in a new place, and nothing else would say so.
    """
    import ast

    tool_path = RENDER / "gen_tile_offsets.py"
    if not tool_path.is_file():
        pytest.skip("gen_tile_offsets.py is not in this checkout")
    grid()                     # puts ui/render on sys.path; without it this test needs a neighbour
                               # to have run first, and passes or errors depending on -k

    import gen_tile_offsets as tool
    watched = {Path(p).resolve() for p in tool._sources()}
    assert watched, "_sources() is empty, so the staleness check cannot fail"
    for p in watched:
        assert p.is_file(), "_sources() names %s, which does not exist" % p

    # every module this file imports that lives beside it in ui/render
    imported = set()
    for node in ast.walk(ast.parse(tool_path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)
    local = {(RENDER / (n.split(".")[0] + ".py")).resolve() for n in imported}
    local = {p for p in local if p.is_file()}
    local.add(tool_path.resolve())

    missed = local - watched
    assert not missed, (
        "gen_tile_offsets.py builds its page from %s but does not watch %s for changes. A --serve "
        "session left running across an edit to it will keep serving the old layout, look freshly "
        "rebuilt while doing it, and send you looking for the bug in code that is already correct."
        % (sorted(p.name for p in local), sorted(p.name for p in missed)))


SHUFFLE = [2, 5, 3, 8, 4, 6, 1, 7, 0]      # a real arrangement: no duty on its own numbered square


@contextlib.contextmanager
def drawn_without_the_artwork(g):
    """Emit the acolyte rows without building their four duotone PNGs.

    `acolyte_tints` needs numpy and Pillow. The ui lane installs both. The lane that runs the whole
    suite installs neither, and the two guards below went in green here and red there -- they had
    only ever been run where numpy exists, which is not a thing either of them is about.

    `pytest.importorskip` was the other option and is worse. What these check is which SHAPE each
    row is derived from, and which tiles carry hit areas; the image bytes have no part in either.
    Skipping would retire a guard against a Taxation-class bug in the lane that runs everything,
    and leave it running only where somebody remembered to install a plotting library. Stubbing the
    artwork keeps the geometry and the markup exactly what production emits, and keeps the guard
    running in both lanes.

    The stub is an empty href, so the <image> elements are still there and still positioned. If a
    future check needs the real pixels it should ask for them explicitly with importorskip, not
    quietly acquire a dependency for everything else in the file.
    """
    real = g.acolyte_tints
    g.acolyte_tints = lambda: {seat: "" for seat in g.SEAT_ORDER}
    try:
        yield
    finally:
        g.acolyte_tints = real


@contextlib.contextmanager
def built_without_the_palette(g):
    """Emit a wheel without measuring the tile art for its palette matrices.

    `drawn_without_the_artwork` above stubs the acolyte tints, which is not enough for anything
    that builds a whole page: `duty_grid_svg` imports Pillow itself, to measure the reference tile
    and match the other eight to it. That is a SECOND pixel dependency in the same call and it
    cannot be reached from outside.

    It can be switched off, though, without touching production: the matrices are only computed
    when the reference tile is among the ones loaded. Pointed at a tile index that does not exist,
    the loop does not run and nothing else changes -- the matrices are `<filter>` defs and no
    coordinate in the svg comes from them. Every clip path, transform and row is byte-identical
    with and without, which is asserted where this is used.
    """
    real = g.PALETTE_REF
    g.PALETTE_REF = -1
    try:
        yield
    finally:
        g.PALETTE_REF = real

def _piles(svg):
    """Every acolyte pile in the emitted markup, as (seat, [(x, y), ...]) in document order.

    The count is the LENGTH of that list and is never read from an attribute. `dg-ac` carries
    `data-seat` and deliberately does not carry the count: a count in the markup would be a second
    statement of the same thing, free to drift from the number of figures actually drawn, and a
    guard reading it would pass while the board showed something else. This file has been bitten
    by duplicated statements of one fact often enough to spell that out.
    """
    import re
    body = svg[svg.index('<g class="dg-acolytes'):]
    out = []
    for seat, inner in re.findall(r'<g class="dg-ac" data-seat="(\w+)">(.*?)</g>', body):
        out.append((seat, [(float(x), float(y)) for x, y in
                           re.findall(r'<image href="[^"]*" x="([\d.\-]+)" y="([\d.\-]+)"', inner)]))
    return out


def test_a_seats_count_is_drawn_under_the_tile_it_belongs_to():
    """Counts are keyed by DUTY; the nine acolyte rows are keyed by SQUARE. Not the same index.

    This shipped wrong. The rows were placed with `frozen[duty]` where `frozen` is the grid's nine
    positions, which is only correct while `cells` is the identity -- and the identity is the
    default, so every render anyone had looked at was right. Pass a real arrangement and seven of
    the nine counts were drawn under the square that merely SHARES THEIR NUMBER: a player's
    acolytes sitting under somebody else's duty, with nothing raised and nothing to notice unless
    you already knew which duty had been dealt where.

    It is the Taxation bug a second time, and the comment in gen_game_view.py warning against
    exactly this fault was already in the file when the fault was introduced two functions away.
    Knowing the shape of a bug does not prevent writing it; a guard does.

    The two duties that happened to land on their own number are why this checks all nine and
    the ROW rectangle rather than the column -- an earlier version of this check compared x only,
    so anything in the same column passed and it reported a working fix as still broken.

    The marker used to be the numeral 7. There are no numerals now, so it is a pile of seven
    figures, located by the one figure standing ON the row's line -- the rest of the pile is above
    it and would otherwise reach into the band this is trying to identify.
    """
    g = grid()
    if not (RENDER / "gen_tile_offsets.py").is_file():
        pytest.skip("the acolyte row geometry lives in gen_tile_offsets.py")
    grid_mod = __import__("gen_tile_offsets")
    rows = grid_mod.acolyte_grid(g.laid_shapes(offsets=False))

    wrong = []
    for duty in range(9):
        counts = [[0, 0, 0, 0] for _ in range(9)]
        counts[duty] = [7, 0, 0, 0]                      # one seat, one duty, an unmistakable value
        with drawn_without_the_artwork(g):
            svg = g.duty_grid_svg(tiles_dir=None, cells=SHUFFLE, acolytes=counts)
        marks = [max(f, key=lambda p: p[1]) for seat, f in _piles(svg) if len(f) == 7]
        assert len(marks) == 1, "expected exactly one pile of seven, found %d" % len(marks)
        x, y = marks[0]
        # the same slack as `_row_under`, and for the same reason: the markup is written to one
        # decimal, so a figure exactly on the slot can land 0.05 units outside an exact bound.
        landed = [i for i, r in enumerate(rows)
                  if r["sx"] - 1.0 <= x <= r["sx"] + 4 * r["fw"] + 3 * r["gap"] + 1.0
                  and r["sy"] - 0.1 <= y <= r["sy"] + r["fh"] * 1.05]
        if landed != [SHUFFLE[duty]]:
            wrong.append("duty %d was dealt to square %d but its count is drawn under %s"
                         % (duty, SHUFFLE[duty], landed or "no row at all"))
    assert not wrong, (
        "an acolyte count is drawn under the wrong tile:\n  " + "\n  ".join(wrong) + "\n"
        "The row belongs under cells[duty], the square that duty was dealt to -- not under the "
        "square with the same number.")


def test_a_duty_the_active_seat_cannot_reach_still_answers_but_never_lights():
    """Closed tiles must stay READABLE and stop being OFFERED. Those are different things.

    The first version of this removed the hit areas from closed tiles, reasoning that a control
    which responds but cannot be used is a lie. It conflated responding with inviting. The game
    view binds its duty description panel to `.dg-hit`, so dropping them took away the text saying
    what the duty does -- from exactly the tiles a player most needs to read while deciding where
    to put acolytes next turn. Nothing sets a pointer cursor; the gold edge is the only thing that
    says "yours to take".

    So: every tile keeps its hit areas, and every rule that LIGHTS something is gated on
    `:not([data-eligible="0"])` as part of the positive selector rather than layered over it as an
    override, so there is no specificity contest to lose later.
    """
    import re
    g = grid()

    # EVERY rule that turns an affordance on must depend on a hit area AND on eligibility, and it
    # has to be checked rule by rule. Asking whether the strings appear anywhere in the stylesheet
    # is a different question and cannot fail: `.dg-hit` is mentioned by `.dg-hit{fill:transparent}`
    # too, so a gold rule rewritten to `.dgt:hover` would leave that substring intact and gold back
    # on unreachable tiles. That was this check's first form, and breaking the link on purpose did
    # not disturb it.
    reveals = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", g.HOVER_CSS):
        if "opacity:1" in body or "stroke:#" in body:
            reveals.append(sel.strip())
    assert reveals, "no rule in HOVER_CSS reveals anything; this check would pass vacuously"
    ungated = [s for s in reveals if ".dg-hit" not in s]
    assert not ungated, (
        "these light something without depending on a hit area: %s" % ungated)
    unchecked = [s for s in reveals if 'not([data-eligible="0"])' not in s]
    assert not unchecked, (
        "these light something without checking eligibility: %s\n"
        "A closed duty would take the gold edge or the lit overlay and read as available."
        % unchecked)

    counts = [[2, 1, 0, 3], [1, 0, 0, 0], [0, 2, 1, 0], [3, 0, 2, 1], [0, 0, 0, 0],
              [1, 1, 1, 1], [2, 0, 0, 0], [0, 1, 0, 2], [1, 0, 3, 0]]
    groups = lambda svg: {int(m.group(1)): m.group(0) for m in re.finditer(
        r'<g data-duty-tile="(\d+)".*?(?=<g data-duty-tile="|<g class="dg-acolytes|</svg>)',
        svg, re.S)}

    for seat in g.SEAT_ORDER:
        with drawn_without_the_artwork(g):
            svg = g.duty_grid_svg(tiles_dir=None, acolytes=counts, active=seat)
        live = g.eligible_tiles(counts, seat)
        assert live, "seat %s reaches nothing in this fixture; the check would be vacuous" % seat
        assert len(live) < 9, "every duty is reachable for %s; nothing is being excluded" % seat
        for i, body in groups(svg).items():
            assert "dg-hit" in body, (
                "duty %d has no hit area, so the game view cannot bind its description panel to "
                "it and the tile goes silent instead of merely closed" % i)
            assert ('data-eligible="%d"' % (1 if i in live else 0)) in body, (
                "duty %d is not marked with whether the %s seat can use it, so a click handler "
                "has nothing to refuse on" % (i, seat))

    # and with no seat active nothing claims anything, so every tile lights as it always did
    with drawn_without_the_artwork(g):
        svg = g.duty_grid_svg(tiles_dir=None, acolytes=counts)
    bodies = groups(svg)
    assert all("dg-hit" in b for b in bodies.values())
    # the TILES, not the whole document: the stylesheet names the attribute in every render,
    # because the gating lives in the selector. Checking the svg as a whole matched the CSS and
    # failed on a board that was behaving correctly.
    marked = [i for i, b in bodies.items() if "data-eligible" in b]
    assert not marked, (
        "a board with no turn in progress is claiming something about eligibility on %s" % marked)


def test_an_active_seat_without_counts_is_refused_rather_than_assumed():
    """The dangerous default is 'everything is available', so it must not be reachable.

    A board that lets a player act on all nine duties is a legal-LOOKING board: nothing downstream
    can tell it from a real one, and the mistake surfaces as a rules bug much later. Both ways of
    getting there -- no counts at all, and a seat name that matches no column -- raise.
    """
    g = grid()
    counts = [[1, 0, 0, 0]] * 9
    with pytest.raises(ValueError):
        g.duty_grid_svg(tiles_dir=None, active="sage")                 # counts missing
    with pytest.raises(ValueError):
        g.duty_grid_svg(tiles_dir=None, acolytes=counts, active="green")   # not a seat
    with pytest.raises(ValueError):
        g.eligible_tiles([[1, 0, 0]] * 9, "sage")                      # short row
    assert g.eligible_tiles(counts, "sage") == set(range(9))
    assert g.eligible_tiles(counts, "bone") == set()


def test_each_half_of_a_two_action_tile_is_named_the_same_in_both_files():
    """`TWO_ACTION` and gen_board's `DUTY_TEXT` describe the same two halves, twice.

    The grid names each half in TWO_ACTION -- that is what decides which half of the picture a
    pointer is on -- and gen_board writes the caption for it under "<duty>|<half>". Two files, one
    fact, and nothing between them.

    They drifted the moment the Give Alms artwork was redrawn with the donation on the left: the
    art said donate-then-alms and both files still said alms-then-donate, so every pointer on the
    left half of that tile described the wrong action. Nothing raised, the picture looked entirely
    normal, and the only way to notice was to read the tile and the caption at the same time.

    A third place said it too -- the old circular wheel puts the crossed-out building on whichever
    wedge it draws second -- and that is why this matters more than tidiness: the two drawings
    share ONE key space, so reordering either alone silently mislabels the other.

    The short name in TWO_ACTION has to appear in the caption's title. That holds for all five
    pairs and is checked to hold, because a substring rule that matched nothing would pass while
    guarding nothing.
    """
    import re
    g = grid()
    board = RENDER / "gen_board.py"
    if not board.is_file():
        pytest.skip("gen_board.py is not in this checkout")
    # read rather than import: gen_board writes a page as a side effect of being executed
    src = board.read_text(encoding="utf-8")
    block = src[src.index("DUTY_TEXT = {"):]
    titles = dict(re.findall(r'"([^"]+\|\d)":\s*\(\s*\n\s*"([^"]+)"', block))
    assert titles, "no DUTY_TEXT entries were parsed; this check would pass guarding nothing"

    wrong, checked = [], 0
    for i, pair in sorted(g.TWO_ACTION.items()):
        name = g.DUTY_NAMES[i]
        for half, short in enumerate(pair):
            key = "%s|%d" % (name, half)
            assert key in titles, "gen_board has no caption for %s" % key
            checked += 1
            if short.lower() not in titles[key].lower():
                wrong.append("%s is %r in the grid but %r in gen_board"
                             % (key, short, titles[key]))
    assert checked == 2 * len(g.TWO_ACTION), (
        "expected %d halves, checked %d" % (2 * len(g.TWO_ACTION), checked))
    assert not wrong, (
        "a tile's two halves are named in different orders in the two files:\n  "
        + "\n  ".join(wrong) + "\n"
        "Whichever is wrong, the effect is the same: the pointer lands on one action and the "
        "panel describes the other, on a tile that looks completely normal.")


def test_the_arrangement_shift_moves_the_acolyte_rows_with_the_tiles():
    """The whole block moves; nothing inside it moves relative to anything else.

    Two kinds of number live in duty_tile_offsets.json and they are not interchangeable. A
    per-tile offset says where ONE tile sits against its own acolyte row -- the rows are frozen,
    so nudging a tile changes that relationship, which is the entire point of the drag tool. The
    arrangement shift says where all nine sit inside the box, and it must change no relationship
    at all.

    The trap is that both are applied in the same function. `placed()` drops the per-tile offsets
    when called with offsets=False, and that call is exactly what the acolyte rows are derived
    from. Dropping the shift alongside them would leave every row behind while the tiles moved --
    a bug that needs the file to be non-zero to appear at all, so it would sit dormant until
    someone actually used the setting.
    """
    g = grid()
    if not (RENDER / "gen_tile_offsets.py").is_file():
        pytest.skip("the acolyte row geometry lives in gen_tile_offsets.py")
    import gen_tile_offsets as tool

    box = g.load()["box"]

    def depths(shift):
        """Each tile's bottom against its own row, under a given shift."""
        laid = g.placed(g.place(g.load()["shapes"], box, g.MARGIN), box, offsets=True)
        rows = tool.acolyte_grid(
            g.placed(g.place(g.load()["shapes"], box, g.MARGIN), box, offsets=False))
        out = []
        for i, d in enumerate(laid):
            out.append(max(q[1] for q in tool._pts(d)) - rows[i]["sy"])
        return out, laid, rows

    import json
    path = g.OFFSETS
    original = path.read_text(encoding="utf-8") if path.is_file() else None
    try:
        data = json.loads(original) if original else {}
        # INTO THE SET, not the top level. The file keys its numbers by acolyte set now, so a
        # top-level `arrangement_shift` is read by nothing and this guard silently patched a key
        # the loader had stopped looking at -- it failed loudly, which is the good version.
        block = data.setdefault("sets", {}).setdefault(g.pop.DEFAULT, {})
        block["arrangement_shift"] = {"dx": 0.0, "dy": 0.0}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        base, laid0, rows0 = depths(0)

        block["arrangement_shift"] = {"dx": -17.0, "dy": -23.0}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        moved, laid1, rows1 = depths(1)

        # `placed()` writes coordinates as %.2f, so every point carries up to 0.005 units of
        # rounding and a depth -- a difference of two of them, one of which the row geometry is
        # derived from -- carries a little more. 0.02 units is 0.018 px on screen. The tolerance
        # is the quantisation, not slack: what it must not hide is a LEAK, and a leak would grow
        # with the shift while rounding does not, which is what the second shift below tests.
        drift = [abs(a - b) for a, b in zip(base, moved)]
        assert max(drift) < 0.02, (
            "a tile's depth over its acolyte row changed by up to %.3f units when only the whole "
            "arrangement moved. The rows are being left behind: `placed()` is dropping the shift "
            "along with the per-tile offsets when called with offsets=False." % max(drift))

        block["arrangement_shift"] = {"dx": -68.0, "dy": -92.0}     # four times as far
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        far, _, _ = depths(2)
        far_drift = max(abs(a - b) for a, b in zip(base, far))
        assert far_drift < 0.02, (
            "the drift grew to %.3f units at four times the shift, so it is not rounding: some "
            "part of the arrangement is being left behind in proportion to how far it moves."
            % far_drift)

        # and it really did move, or the check above passed on two identical boards
        k = box / tool.WHEEL_PX
        dx = min(q[0] for q in tool._pts(laid1[0])) - min(q[0] for q in tool._pts(laid0[0]))
        dy = min(q[1] for q in tool._pts(laid1[0])) - min(q[1] for q in tool._pts(laid0[0]))
        # same 0.02-unit quantum as above -- these are read back out of %.2f path strings too
        assert abs(dx - (-17.0 * k)) < 0.02 and abs(dy - (-23.0 * k)) < 0.02, (
            "the shift did not reach the tiles at all (moved %.3f, %.3f units, wanted %.3f, "
            "%.3f); this test would have passed while guarding nothing"
            % (dx, dy, -17.0 * k, -23.0 * k))
        assert abs((rows1[0]["sy"] - rows0[0]["sy"]) - (-23.0 * k)) < 0.02, (
            "the shift did not reach the acolyte rows")
    finally:
        if original is not None:
            path.write_text(original, encoding="utf-8")


def test_the_offsets_page_draws_the_block_where_the_board_draws_it():
    """Compose the page the way the page composes itself, and land on the board's own tiles.

    The guard above proves the shift moves the rows with the tiles. This one asks a different
    question that had the opposite answer for as long as the setting existed: is the block in the
    right PLACE? The tool builds its base wheel with `offsets=False` because its JS moves tiles
    itself -- and `offsets=False` deliberately keeps the arrangement shift, so the rows are not
    left behind. Then `apply()` adds the shift again, to every tile group and to `#acol`. The
    block was drawn at twice the saved number.

    Nothing inside the arrangement looks wrong when that happens, which is why it survived: the
    rows double with the tiles, so every relationship the drag tool exists to set is intact. Only
    the block's position in the box is wrong -- and the panel reported it correctly, because its
    margins are BASE + shift and BASE had the shift taken back out. Picture and read-out
    disagreed, and an arrangement is judged by the picture.

    So: the page's OWN emitted numbers, its OWN drawn shapes, and the grid's own answer for where
    the board puts the tiles. Nothing here recomputes a layout, which is what stops this becoming
    another check that moves with the thing it is checking.
    """
    g = grid()
    if not (RENDER / "gen_tile_offsets.py").is_file():
        pytest.skip("the page lives in gen_tile_offsets.py")
    import gen_tile_offsets as tool
    import json
    import re

    def centre(d):
        P = tool._pts(d)
        return sum(q[0] for q in P) / len(P), sum(q[1] for q in P) / len(P)

    path = g.OFFSETS
    original = path.read_text(encoding="utf-8") if path.is_file() else None
    try:
        data = json.loads(original) if original else {}
        block = data.setdefault("sets", {}).setdefault(tool.POP_SET, {})
        # DELIBERATELY non-zero, and not a round multiple of anything: the fault is invisible at
        # zero, and the set this tool opens on may well have zero saved.
        block["arrangement_shift"] = {"dx": 37.0, "dy": -29.0}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        # FOURTH time this dependency has escaped into the lane that has no numpy, and this is
        # the first guard to build a whole PAGE, so it walks into both halves of it: the gothic
        # acolytes are four duotoned PNGs, and `duty_grid_svg` measures the tile art for its
        # palette matrices. The page's GEOMETRY is what is under test and no coordinate comes
        # from either, so both are stubbed rather than the guard skipped.
        with drawn_without_the_artwork(g), built_without_the_palette(g):
            page = tool.build(False)
        # BOTH, and this gate is the reason this guard went red in CI after passing here.
        # `shrink` needs Pillow and `palette_stats` needs numpy, and the lane that runs the whole
        # suite installs the first and not the second -- so a gate asking only about Pillow said
        # yes and then built a page that could not be built. The simulation used locally blocked
        # numpy and Pillow TOGETHER, which is the one combination that hides this.
        try:
            import numpy                                              # noqa: F401
            import PIL.Image                                          # noqa: F401
            unstubbed = True
        except ImportError:
            unstubbed = False
        if unstubbed:
            # the stubs do not move anything. Asserted here rather than asserted by the comment.
            full = tool.build(False)
            assert (re.findall(r'<clipPath id="dg-c\d"><path d="M[^"]+"', full)
                    == re.findall(r'<clipPath id="dg-c\d"><path d="M[^"]+"', page)), (
                "stubbing the artwork or the palette changed where the tiles are, so this guard "
                "is no longer measuring the page the tool actually serves.")
        # what the page tells its own JavaScript -- read back out of the page, not recomputed
        sh = json.loads(re.search(r"var shift = (\{.*?\});", page).group(1))
        pg_off = json.loads(re.search(r"var off = (\{.*?\});", page).group(1))
        K = float(re.search(r"K = ([0-9.]+);", page).group(1))
        assert (sh["dx"], sh["dy"]) == (37.0, -29.0), (
            "the page did not pick up the shift under test (%r); this guard would be checking a "
            "board that never moved" % (sh,))

        clips = dict(re.findall(r'<clipPath id="dg-c(\d)"><path d="(M[^"]+)"', page))
        assert len(clips) == 9, "expected nine tile clip paths in the page, found %d" % len(clips)

        board = [centre(d) for d in g.laid_shapes(offsets=True, pop_set=tool.POP_SET)]
        worst = (0.0, -1)
        for i in range(9):
            bx, by = centre(clips[str(i)])
            o = pg_off.get(str(i)) or {"dx": 0.0, "dy": 0.0}
            # exactly what apply() does: screen px -> grid units, offset and shift together
            px = bx + (o["dx"] + sh["dx"]) / K
            py = by + (o["dy"] + sh["dy"]) / K
            d = max(abs(px - board[i][0]), abs(py - board[i][1]))
            if d > worst[0]:
                worst = (d, i)
        # the %.2f the paths are written at, doubled because two of them are differenced
        assert worst[0] < 0.02, (
            "tile %d lands %.2f grid units (%.1f screen px) from where the board draws it once "
            "the page's own transform is applied. The shift is being counted twice: the base svg "
            "is built with it AND apply() adds it. A shift of (%.0f, %.0f) px was under test."
            % (worst[1], worst[0], worst[0] * K, sh["dx"], sh["dy"]))

        # and the panel agrees with the picture it is beside, which is the half that was right
        base = json.loads(re.search(r"var BASE = (\{.*?\});", page).group(1))
        xs, ys = [], []
        for d in g.laid_shapes(offsets=True, pop_set=tool.POP_SET):
            for q in tool._pts(d):
                xs.append(q[0])
                ys.append(q[1])
        box = g.load()["box"]
        assert abs((base["l"] + sh["dx"]) - min(xs) * K) < 0.05, (
            "the panel reports a left margin of %.2f px where the board's is %.2f"
            % (base["l"] + sh["dx"], min(xs) * K))
        assert abs((base["t"] + sh["dy"]) - min(ys) * K) < 0.05, (
            "the panel reports a top margin of %.2f px where the board's is %.2f"
            % (base["t"] + sh["dy"], min(ys) * K))
        assert abs((base["r"] - sh["dx"]) - (box - max(xs)) * K) < 0.05, (
            "the panel's right margin does not match the board's")
    finally:
        if original is not None:
            path.write_text(original, encoding="utf-8")


def test_the_tools_pixel_basis_is_the_board_the_offsets_will_be_drawn_on():
    """WHEEL_PX must be the size the wheel is actually drawn at, or everything downstream lies.

    Three things ride on this number and none of them would complain. The nine offsets are stored
    as "screen px at wheel width 877.8" and converted back through it, so a stale value scales
    every one of them. The arrangement shift is the same. And the red reference box the tool draws
    is asserted to be the wheel's real box on the board -- the banner sits on its top edge and the
    column meets it left and right -- which is only true while these agree.

    The board's wheel is not a constant there either: `geometry()` fits it to whichever of the
    column's width or height runs out first, so a change to the frame, the banner or a column gap
    moves it. That is the realistic way this breaks -- nobody edits WHEEL_PX, somebody widens a
    gap -- and the failure is a board that looks fine with every tile a percent or two out.
    """
    if not (RENDER / "gen_tile_offsets.py").is_file():
        pytest.skip("gen_tile_offsets.py is not in this checkout")
    if not (RENDER / "gen_game_view.py").is_file():
        pytest.skip("gen_game_view.py is not in this checkout")
    grid()                                  # puts ui/render on sys.path
    import gen_game_view as gv
    import gen_tile_offsets as tool

    drawn = gv.geometry(gv.layout())["wheel"]
    assert drawn > 0, "the game view reports a zero-width wheel; this check would be vacuous"
    assert abs(drawn - tool.WHEEL_PX) < 0.05, (
        "the board draws its wheel %.1f px square, but gen_tile_offsets.WHEEL_PX is %.1f. Every "
        "saved offset is stored in screen px at that width and converted back through it, so all "
        "nine are out by %.1f%%, and the red reference box in the tool is no longer the box the "
        "banner and the column actually meet."
        % (drawn, tool.WHEEL_PX, abs(drawn - tool.WHEEL_PX) / tool.WHEEL_PX * 100))

    # and the file agrees with the tool, or offsets saved earlier are read back at the wrong scale
    import json
    if tool.OFFSETS_PATH.is_file():
        recorded = json.loads(tool.OFFSETS_PATH.read_text(encoding="utf-8")).get("wheel_px")
        assert recorded is None or abs(float(recorded) - tool.WHEEL_PX) < 0.05, (
            "duty_tile_offsets.json records wheel_px %s but the tool is at %.1f; the numbers in "
            "it were judged on a different board" % (recorded, tool.WHEEL_PX))


def test_the_action_box_ends_on_the_acolytes_feet():
    """The action box is sized from the wheel's visible foot, and that foot is not its box.

    The figures hang below the last row of tiles, so the line the eye reads as the bottom of the
    component sits above the box's own bottom edge -- 42.3 px above it, as the board stands. The
    action box is aligned to that line rather than to the row it lives in.

    Two ways this rots, and neither shows up as an error. The number could be frozen into the
    stylesheet, in which case the next drag or arrangement shift moves the acolytes and the box
    stays put. Or the wheel could stop being the thing it is measured against -- `geometry()` fits
    the wheel to whichever of the column's width or height runs out first, so it moves when a gap
    or the banner does. Both give a board that looks deliberate and is a few px out.
    """
    g = grid()
    if not (RENDER / "gen_game_view.py").is_file():
        pytest.skip("gen_game_view.py is not in this checkout")
    import gen_game_view as gv

    G = gv.geometry(gv.layout())
    box = g.load()["box"]
    # The set the PAGE draws, not the default: the foot is the lowest acolyte ink and the
    # offsets are per set, so the two answers differ by the whole arrangement shift between them.
    import gen_game_view as _gv
    foot = G["banner_h"] + G["wheel"] * (g.acolyte_foot(pop_set=_gv.POP_SET) / box)
    assert abs(G["act_h"] - foot) < 0.1, (
        "the action box is %.1f px tall but the acolytes' feet are at %.1f px from the top of "
        "that column. It is meant to end on that line." % (G["act_h"], foot))
    assert G["act_h"] < G["main_h"], (
        "the action box fills its whole row, so it is not being cut to the acolyte line at all "
        "and this check is comparing two numbers that happen to match")

    # and the foot must actually track the tiles, or the alignment is a coincidence
    import json
    path = g.OFFSETS
    original = path.read_text(encoding="utf-8") if path.is_file() else None
    try:
        data = json.loads(original) if original else {}
        # RELATIVE to whatever is already saved, not from zero. The board currently carries a
        # shift, so setting an absolute -60 moves the foot by the difference, and asserting it
        # moved the full 60 failed on correct code -- a test wrong about the starting point looks
        # exactly like the bug it was written to catch.
        #
        # And INTO THE SET the page draws, for the same reason: the file keys its numbers by
        # acolyte set now, so a top-level shift is read by nothing. Patching one moved the foot by
        # exactly zero, which this falsification reported as the bug it exists to catch -- the
        # good failure, but only because the number it prints is unmistakable.
        block = data.setdefault("sets", {}).setdefault(_gv.POP_SET, {})
        was = float((block.get("arrangement_shift") or {}).get("dy", 0.0))
        before = g.acolyte_foot(pop_set=_gv.POP_SET)
        block["arrangement_shift"] = {"dx": 0.0, "dy": was - 60.0}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        after = g.acolyte_foot(pop_set=_gv.POP_SET)
        G2 = gv.geometry(gv.layout())
        moved = (before - after) * (G2["wheel"] / box)
        assert abs(moved - 60.0) < 0.1, (
            "moving the whole arrangement 60 px up moved the acolyte foot %.1f px, so the foot "
            "is not tracking the tiles at all." % moved)
        # THE BOX ITSELF, not just the foot. Asserting only that the foot moved leaves a frozen
        # constant passing: `act_h = 923.5` is correct for the offsets saved today and wrong the
        # moment anyone drags, and the first check above cannot see the difference because it
        # never asks what the box did. Writing this guard without the line below produced exactly
        # that -- the deliberate regression passed.
        assert abs((G["act_h"] - G2["act_h"]) - 60.0) < 0.15, (
            "the acolytes' feet moved 60 px but the action box moved %.1f px. It is not being "
            "derived from them -- most likely the height is a literal that happens to be right "
            "for the offsets currently saved." % (G["act_h"] - G2["act_h"]))
    finally:
        if original is not None:
            path.write_text(original, encoding="utf-8")


def _row_under(g, svg, shape, seats):
    """The piles drawn under ONE tile, as (x, count), found by that tile's own row rectangle.

    By the RECTANGLE, not the column. Squares 0, 3 and 6 share an x range, so a filter on x alone
    picks up three rows and reads as one -- which has now produced a wrong answer twice in this
    file's history, once reporting a working fix as broken.

    A pile is identified by the figure standing ON the line, at `sy`, and the count is how many
    figures that pile contains. Matching any figure in the band would be wrong twice over: a pile
    reaches upward by as much as 158 px, and its upper figures are leaned sideways, so both the
    y band and the x band would have to be widened until they stopped identifying one row.
    """
    b = g.acolyte_box(shape, seats)
    # widened by a lean at both ends: this is a finder, and it must not depend on the very thing
    # `test_every_pile_stands_on_its_own_slot` exists to check. An earlier version bounded it at
    # sx exactly and silently dropped the first seat's pile the moment its bottom figure leaned.
    slack = b["fw"] * g.STACK_LEAN + 1.0
    lo, hi = b["sx"] - slack, b["sx"] + len(seats) * (b["fw"] + b["gap"]) + slack
    top, bot = b["sy"] - 0.1, b["sy"] + b["fh"] * 1.05
    out = []
    for _seat, figs in _piles(svg):
        base = max(figs, key=lambda p: p[1])
        if lo <= base[0] <= hi and top <= base[1] <= bot:
            out.append((base[0], len(figs)))
    return out


def test_the_row_is_drawn_for_the_seats_actually_playing():
    """Pilgrim seats two to four, and a two-player board must not show four players.

    What has to survive a change of player count is the per-tile offsets, and they survive for a
    reason worth stating rather than hoping: `sx + span/2` is the tile's own centre whatever the
    span is, so a row of two sits exactly where a row of four sat. The offsets in
    duty_tile_offsets.json were judged at four seats and are not re-judged at two.

    The figure does not grow when there are fewer of them either. A figure is a figure.
    """
    g = grid()
    for k in (2, 3, 4):
        seats = g.SEAT_ORDER[:k]
        with drawn_without_the_artwork(g):
            svg = g.duty_grid_svg(tiles_dir=None, acolytes=[[1] * k] * 9, seats=seats)
        shapes = g.laid_shapes(offsets=False)
        for i, d in enumerate(shapes):
            row = _row_under(g, svg, d, seats)
            assert len(row) == k, (
                "tile %d drew %d figures for %d seats" % (i, len(row), k))
        b = g.acolyte_box(shapes[0], seats)
        span = k * b["fw"] + (k - 1) * b["gap"]
        pts = [float(v) for v in
               shapes[0].replace("M", " ").replace("Z", " ").replace("L", " ").split()]
        centre = (min(pts[0::2]) + max(pts[0::2])) / 2
        assert abs((b["sx"] + span / 2) - centre) < 1e-6, (
            "at %d seats the row's centre is %.3f but the tile's is %.3f. The row has stopped "
            "being centred, so every saved offset now means something different at this player "
            "count than at the one it was judged at."
            % (k, b["sx"] + span / 2, centre))
        assert abs(b["fw"] - g.acolyte_box(shapes[0], g.SEAT_ORDER)["fw"]) < 1e-9, (
            "the figure changed size with the seat count")


def test_the_acolyte_foot_does_not_move_with_the_game():
    """The action box is cut to this line, so it must not depend on who is playing or on counts.

    If it did, the board's layout would shift when a player joined, left, or simply moved an
    acolyte -- furniture moving in response to game state, which is the opposite of what furniture
    is for. It holds because `sy + fh` has neither a seat term nor a count term in it, and that is
    worth a guard because both would be easy to introduce while making the row cleverer.
    """
    g = grid()
    base = g.acolyte_foot()
    for k in (1, 2, 3, 4):
        shapes = g.laid_shapes(offsets=False)
        foot = max(g.acolyte_box(d, g.SEAT_ORDER[:k])["sy"]
                   + g.acolyte_box(d, g.SEAT_ORDER[:k])["fh"] for d in shapes)
        assert abs(foot - base) < 1e-9, (
            "the acolytes' feet move from %.4f to %.4f between 4 seats and %d. The action box "
            "height is derived from that line." % (base, foot, k))


def test_a_seat_with_no_acolytes_on_a_tile_is_drawn_as_nothing():
    """An absence should look like an absence, and the others must not close up around it.

    A row of figures each labelled 0 was the same picture as a row with one player present until
    four small numbers were read. So a zero draws nothing.

    With the numerals gone this matters MORE, not less. An empty slot is now the only thing on the
    board that distinguishes "this player has none here" from "this player is not in the game" --
    there is no 0 left to read as a fallback, so the absence has to carry it alone.

    The rest keep their slots. That is the half worth guarding: reflowing to close the gap would
    make the second pile mean a different player on every tile, and a row is only readable at a
    glance across nine tiles because position means seat.
    """
    g = grid()
    shapes = g.laid_shapes(offsets=False)
    with drawn_without_the_artwork(g):
        full = g.duty_grid_svg(tiles_dir=None, acolytes=[[2, 1, 3, 1]] * 9)
        holed = g.duty_grid_svg(tiles_dir=None, acolytes=[[2, 0, 3, 0]] * 9)
        empty = g.duty_grid_svg(tiles_dir=None, acolytes=[[0, 0, 0, 0]] * 9)
    for i, d in enumerate(shapes):
        a = _row_under(g, full, d, g.SEAT_ORDER)
        b = _row_under(g, holed, d, g.SEAT_ORDER)
        c = _row_under(g, empty, d, g.SEAT_ORDER)
        assert len(a) == 4, "tile %d: expected four figures, got %d" % (i, len(a))
        assert len(b) == 2, (
            "tile %d drew %d figures for counts [2,0,3,0]; the two zeros should draw nothing"
            % (i, len(b)))
        assert not c, "tile %d drew %d figures for a row of zeros" % (i, len(c))
        assert [x for x, _ in b] == [a[0][0], a[2][0]], (
            "tile %d: the surviving figures are at %s but their slots are %s. Something reflowed "
            "to close the gap, so the second figure is no longer the second seat."
            % (i, [x for x, _ in b], [a[0][0], a[2][0]]))
        assert [v for _, v in b] == [2, 3], "tile %d kept the wrong counts: %s" % (i, b)


def test_a_count_is_that_many_figures_and_there_is_no_numeral_anywhere():
    """The picture IS the count. Nothing on the board states it a second time.

    This is the whole change, so it is worth saying what would break it quietly. A numeral kept
    "as a fallback above some threshold" is the obvious next edit and the wrong one: it would make
    the tall piles -- the ones a player is squinting at to compare -- the only ones that have to be
    read, which is exactly backwards. And any numeral at all is a second statement of the count,
    free to disagree with the number of figures drawn, with nothing to say which is right.

    Counts run past what a game reaches on purpose. A pile is not capped and nothing here truncates
    one, so nine must draw nine.
    """
    g = grid()
    shapes = g.laid_shapes(offsets=False)
    for n in range(1, 10):
        with drawn_without_the_artwork(g):
            svg = g.duty_grid_svg(tiles_dir=None, acolytes=[[n, 0, n, 0]] * 9)
        body = svg[svg.index('<g class="dg-acolytes'):]
        assert "<text" not in body, (
            "a numeral is being drawn in the acolyte rows at count %d. The pile is the count; a "
            "number beside it can disagree with the figures and nothing says which is right." % n)
        for i, d in enumerate(shapes):
            row = _row_under(g, svg, d, g.SEAT_ORDER)
            assert [c for _, c in row] == [n, n], (
                "tile %d drew piles of %s for counts [%d, 0, %d, 0]"
                % (i, [c for _, c in row], n, n))


def test_a_lone_acolyte_stands_exactly_where_it_always_did():
    """One acolyte is the commonest count on the board, and it must not have moved at all.

    It holds because the bottom figure of a pile does not lean -- only the ones resting on it do.
    The first version leaned every figure and re-centred the pile afterwards, which is correct
    about the pile and wrong about the foot: it moved the bottom figure by half a lean whenever the
    count changed, so a lone acolyte sat 5 px off its slot in a uniform direction. That reads as a
    botched drag rather than as a bug, and it would have been chased in the offsets file.

    `test_every_pile_stands_on_its_own_slot` below is the general form of this. Both are kept: this
    one names the count that is commonest on the board and the one a reader will check by eye.
    """
    g = grid()
    for k in (2, 3, 4):
        seats = g.SEAT_ORDER[:k]
        for i, d in enumerate(g.laid_shapes(offsets=False)):
            b = g.acolyte_box(d, seats)
            for j in range(k):
                counts = [0] * k
                counts[j] = 1
                with drawn_without_the_artwork(g):
                    svg = ('<g class="dg-acolytes">'
                           + g.acolyte_row(d, counts, seats) + '</g>')
                (_seat, figs), = _piles(svg)
                (x, y), = figs
                want = (b["sx"] + j * (b["fw"] + b["gap"]), b["sy"])
                # the markup writes %.1f, so 0.05 units is the floor. Anything real here is a lean,
                # which is 0.10 of a figure -- 6.1 units, two orders of magnitude away.
                assert abs(x - want[0]) < 0.06 and abs(y - want[1]) < 0.06, (
                    "at %d seats, tile %d, slot %d: a single acolyte is drawn at (%.2f, %.2f) but "
                    "its slot is (%.2f, %.2f). A lone figure has to stand where it stood before "
                    "the pile existed." % (k, i, j, x, y, *want))


def test_every_pile_stands_on_its_own_slot():
    """The bottom figure of every pile sits exactly on its seat's slot, at every count.

    The row of feet is what the eye measures pile heights against, so it has to be a row: if the
    bottom figure moved with the count, four seats with four different counts would stand on four
    slightly different lines and the comparison the pile exists to make gets harder to read, not
    easier. It also keeps a count change from nudging anything sideways.
    """
    g = grid()
    for k in (2, 3, 4):
        seats = g.SEAT_ORDER[:k]
        for i, d in enumerate(g.laid_shapes(offsets=False)):
            b = g.acolyte_box(d, seats)
            for n in range(1, 10):
                with drawn_without_the_artwork(g):
                    svg = ('<g class="dg-acolytes">'
                           + g.acolyte_row(d, [n] * k, seats) + '</g>')
                for j, (seat, figs) in enumerate(_piles(svg)):
                    base = max(figs, key=lambda p: p[1])
                    want = b["sx"] + j * (b["fw"] + b["gap"])
                    assert abs(base[0] - want) < 0.06, (
                        "tile %d, %d seats, count %d: %s's bottom figure is at %.2f, not on its "
                        "slot at %.2f." % (i, k, n, seat, base[0], want))


def test_the_pile_grows_upward_so_the_foot_never_moves_with_a_count():
    """The action box is cut to the acolytes' foot, so a count must not be able to move it.

    `test_the_acolyte_foot_does_not_move_with_the_game` says the same thing about the SEAT count
    and checks it through `acolyte_box`, which has no count term to begin with. This checks the
    drawing instead, because the foot is now a property of which end of the pile is anchored: draw
    it downward, or centre it, and `acolyte_box` still reports the same foot while the figures sit
    somewhere else entirely and the box no longer ends where they do.
    """
    g = grid()
    for k in (2, 3, 4):
        seats = g.SEAT_ORDER[:k]
        for i, d in enumerate(g.laid_shapes(offsets=False)):
            b = g.acolyte_box(d, seats)
            for n in range(1, 10):
                with drawn_without_the_artwork(g):
                    svg = ('<g class="dg-acolytes">'
                           + g.acolyte_row(d, [n] * k, seats) + '</g>')
                for seat, figs in _piles(svg):
                    low = max(y for _, y in figs)
                    assert abs(low - b["sy"]) < 0.06, (
                        "tile %d, %d seats, count %d: %s's lowest figure is at %.2f but the row's "
                        "line is %.2f. The pile has to grow upward from that line -- the action "
                        "box ends on it." % (i, k, n, seat, low, b["sy"]))
                    top = min(y for _, y in figs)
                    assert abs((b["sy"] - top) - (n - 1) * b["fh"] * g.STACK_STEP) < 0.06, (
                        "tile %d, count %d: the pile is %.2f tall, not %.2f. Something is not "
                        "stepping by STACK_STEP." % (i, n, b["sy"] - top,
                                                     (n - 1) * b["fh"] * g.STACK_STEP))


def test_neighbouring_piles_never_touch():
    """The lean widens a pile into the gap between seats, and the gap is not large.

    A pile is 2 * STACK_LEAN wider than one figure, into a gap of 0.24 of a figure. That leaves
    0.04 of a figure -- under 2 px at the drawn size -- between BOUNDING BOXES, which is close
    enough that raising the lean even slightly would run two seats together, and the failure would
    look like a rendering artefact rather than a constant being wrong.

    So this measures INK, from the asset's own alpha, rather than boxes. The ink clears by far
    more than the boxes do, because the leaning figures are the upper ones and the acolyte is 9%
    of its width at the crown -- but that is a fact about this artwork, and it stops being true if
    the figure is ever redrawn straighter. This is the guard that would notice.
    """
    g = grid()
    np = pytest.importorskip("numpy")
    Image = pytest.importorskip("PIL.Image", reason="the ink profile comes from the asset")
    if not g.ACOLYTE.is_file():
        pytest.skip("the acolyte asset is not in this tree")
    al = np.asarray(Image.open(g.ACOLYTE).convert("RGBA")).astype(int)[..., 3] > 24
    H, W = al.shape
    ext = []
    for r in range(H):
        c = np.where(al[r])[0]
        ext.append((c[0] / W, (c[-1] + 1) / W) if len(c) else None)

    worst, where = 1e9, None
    for k in (2, 3, 4):
        seats = g.SEAT_ORDER[:k]
        for i, d in enumerate(g.laid_shapes(offsets=False)):
            b = g.acolyte_box(d, seats)
            step, lean = b["fh"] * g.STACK_STEP, b["fw"] * g.STACK_LEAN
            band = b["fh"] / H
            for n in range(1, 10):
                spans = []
                for j in range(k):
                    x = b["sx"] + j * (b["fw"] + b["gap"])
                    side = [(lean if (n - 1 - m) % 2 else -lean) for m in range(n)]
                    mid = (min(side) + max(side)) / 2
                    one = []
                    for m in range(n):
                        fx, fy = x + side[m] - mid, b["sy"] - (n - 1 - m) * step
                        one += [(fy + b["fh"] * r / H, fx + b["fw"] * e[0], fx + b["fw"] * e[1])
                                for r, e in enumerate(ext) if e]
                    spans.append(one)
                for A, B in zip(spans, spans[1:]):
                    for ya, _, ra in A:
                        for yb, lb, _ in B:
                            if abs(ya - yb) <= band and lb - ra < worst:
                                worst, where = lb - ra, (k, i, n)
    assert worst > 2.0, (
        "two neighbouring seats' acolytes come within %.2f units of each other (%d seats, tile "
        "%d, count %d). They are separate players' pieces and must read as separate piles."
        % (worst, *where))


def test_a_row_of_counts_must_match_the_seats_at_the_table():
    """A row of the wrong length puts one player's acolytes under another player's figure."""
    g = grid()
    with pytest.raises(ValueError):
        g.duty_grid_svg(tiles_dir=None, acolytes=[[1, 1, 1, 1]] * 9, seats=("sage", "pewter"))
    with pytest.raises(ValueError):
        g.duty_grid_svg(tiles_dir=None, acolytes=[[1, 1]] * 9, seats=g.SEAT_ORDER)
    with pytest.raises(ValueError):
        g.duty_grid_svg(tiles_dir=None, acolytes=[[1, 1]] * 9, seats=("sage", "sage"))
    with pytest.raises(ValueError):
        g.duty_grid_svg(tiles_dir=None, acolytes=[[1, 1]] * 9, seats=("sage", "crimson"))
    with pytest.raises(ValueError):       # active must be at the table, not merely a seat colour
        g.duty_grid_svg(tiles_dir=None, acolytes=[[1, 1]] * 9,
                        seats=("sage", "pewter"), active="bone")
    assert g.eligible_tiles([[0, 1]] * 9, "pewter", ("sage", "pewter")) == set(range(9))
    assert g.eligible_tiles([[0, 1]] * 9, "sage", ("sage", "pewter")) == set()


# ---------------------------------------------------------------------------------------------
# THE BORDER STUDIO, which draws the wheel's outlines and must not draw its own.
#
# gen_border_studio lays candidate markings over the tile edge so a choice made in it is a choice
# about the board. That only holds while the edge it draws IS the board's edge -- same nine shapes,
# same stroke weight, same ink, same gold under the hover. A studio that drifted would still look
# entirely convincing; it would just be answering a question about a different board.
#
# Two scripts in this project already died of that, and one of them kept captioning its baseline
# with a design that had been replaced weeks earlier. The guards below are the cheap version of
# never doing it a third time.


def studio():
    import importlib.util
    path = REPO / "ui" / "render" / "gen_border_studio.py"
    if not path.is_file():
        pytest.skip("gen_border_studio.py is not in this checkout")
    spec = importlib.util.spec_from_file_location("_studio", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_studio_draws_the_wheels_own_edge():
    """Nine shapes, the board's stroke weight, the board's ink, the board's gold.

    All four are read from gen_duty_grid at build time rather than written into the studio, so this
    guard is really asserting that they still CAN be: it fails the moment one of those names moves
    and the studio starts carrying a copy instead.
    """
    st = studio()
    dg = st.grid()
    page = st.build(dg)
    import json
    box = json.loads(dg.SHAPES.read_text())["box"]
    # `.dgt` and not a class of the studio's own: MARK_CSS is scoped to the wheel's contract, so a
    # studio using different names would need its own copy of every rule -- which is the drift.
    assert page.count('class="dgt"') == 9, (
        "the studio drew %d tiles, not nine." % page.count('class="dgt"'))
    assert page.count('class="dg-mark"') == 9, (
        "the studio drew %d marking groups; it is meant to use gen_duty_grid.mark_paths for every "
        "tile rather than building lookalikes." % page.count('class="dg-mark"'))
    assert ('stroke-width:%.2f' % (box * dg.EDGE_STROKE)) in page, (
        "the studio's baseline edge is not %.2f, the board's own stroke weight. A comparison "
        "against a heavier or lighter edge than the board draws is a comparison against nothing."
        % (box * dg.EDGE_STROKE))
    assert dg.INK in page, "the studio's edge is not the board's ink %s." % dg.INK
    # `--gold:` and not merely "the string appears somewhere". It appears in the studio's own
    # prose as well, so the loose version of this assertion passed while the declaration carried a
    # completely different colour -- and the only reason that was found is that falsifying it
    # reported NO. A guard that cannot fail is worth nothing, and this one could not.
    assert ("--gold:%s" % dg.EDGE_HOVER) in page, (
        "the studio's --gold is not the board's %s. That colour is the one thing on the board "
        "already meaning 'yours to take', and the studio's whole argument for proposing a "
        "different hue is that it can see the one that is taken." % dg.EDGE_HOVER)


def test_the_portal_dashes_divide_the_path_evenly():
    """No seam, on any of the nine, and that is arithmetic rather than taste.

    The effect this came from sums to 478 against a circumference of 754, so its pattern restarts
    part-way round the ring. On a smooth circle that is invisible; on nine torn outlines with
    different perimeters it would be nine visible seams in nine different places, and it would read
    as the artwork being wrong rather than the dash pattern.
    """
    dg = studio().grid()
    total = sum(float(v) for v in dg.mark_dash().split())
    assert abs(total - dg.MARK_PERIOD) < 0.05, (
        "the rescaled dash pattern sums to %.2f, not the %.2f it is meant to."
        % (total, dg.MARK_PERIOD))
    reps = dg.MARK_PATH_LENGTH / dg.MARK_PERIOD
    assert abs(reps - round(reps)) < 1e-9, (
        "the pattern repeats %.3f times in a pathLength of %d. It has to be a whole number or the "
        "last dash meets the first mid-stride and every tile shows a seam."
        % (reps, dg.MARK_PATH_LENGTH))


def test_the_studio_marks_no_duty_it_was_not_told_to():
    """Its eligibility is a fixture, and it has to stay one.

    Which duties are open after a Sow is a rules question, and three arrangements in this repo
    still disagree about which duty is mancala position n. A studio that started deriving its own
    answer would be quietly asserting one of them.
    """
    st = studio()
    assert set(st.DEMO_ELIGIBLE) <= set(range(9)), "a demo index outside the nine tiles"
    assert len(st.DEMO_COUNTS) == 9, "the demo acolyte counts are not nine numbers"
    src = (REPO / "ui" / "render" / "gen_border_studio.py").read_text()
    assert "GameState" not in src and "sow_vector" not in src, (
        "gen_border_studio has started reaching into the engine. It draws candidate markings; "
        "what is actually eligible is not its question.")


# ---------------------------------------------------------------------------------------------
# ONE MARKING, TWO PAGES. The studio's entire claim is that a choice made in it is a choice about
# the board, and that holds only while both draw the same rings from the same rules. So the rules
# live in gen_duty_grid and both pages borrow them whole; these guards are what stops a copy.


def game_view():
    import importlib.util
    path = REPO / "ui" / "render" / "gen_game_view.py"
    if not path.is_file():
        pytest.skip("gen_game_view.py is not in this checkout")
    spec = importlib.util.spec_from_file_location("_gv_mark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_marking_is_inert_until_a_page_asks():
    """A component embedded in a page that has no script must not start animating by itself.

    Every rule in MARK_CSS needs `data-mark="1"` on a tile and `data-mark-effect` on the svg, and
    this module sets neither -- the layout tool slots this wheel into a simulated screen and the
    picker shows two at once, and a wheel with an opinion about its own page would be wrong in both.
    """
    dg = studio().grid()
    rules = [r for r in dg.MARK_CSS.split("}") if r.strip().startswith("svg[data-mark-effect")]
    assert rules, "no effect rules found in MARK_CSS at all"
    for r in rules:
        assert 'data-mark="1"' in r, (
            "a MARK_CSS rule fires without a tile being marked: %r. Every effect has to require "
            "BOTH attributes, or embedding this wheel starts an animation nobody asked for." % r)


def test_the_studio_and_the_board_carry_the_same_marking():
    """Byte-for-byte, both directions, because a near-copy is the thing that drifts.

    Not "both mention emerald" or "both have six effects" -- the exact text. The moment either page
    is edited to hold its own version of a rule, this fails, which is the only way the studio's
    claim about predicting the board stays true.
    """
    st = studio()
    dg = st.grid()
    page = st.build(dg)
    assert dg.MARK_CSS in page, "the studio no longer emits gen_duty_grid.MARK_CSS verbatim"
    assert dg.MARK_JS in page, "the studio no longer emits gen_duty_grid.MARK_JS verbatim"
    for value, label in dg.MARK_EFFECTS:
        assert label in page, "the studio is missing the %r effect" % (label,)


def test_the_game_view_offers_every_effect_and_marks_what_the_board_computed():
    """The dropdown's options come from MARK_EFFECTS, and what it marks is not a fixture.

    `data-eligible="1"` is set by eligible_tiles() on every tile where the active seat has one or
    more acolytes -- the lift state, from the real counts. A driver that marked a hard-coded set
    would look identical on this board and be wrong on every other.
    """
    dg = studio().grid()
    gv = game_view()
    for value, label in dg.MARK_EFFECTS:
        assert ('<option value="%s">%s</option>' % (value, label)) in gv.MARK_SELECT, (
            "the game view's control is missing %r; its options are meant to be MARK_EFFECTS."
            % (label,))
    # The CODE, not the comments above it. Both of these names appear in the note explaining the
    # driver, so the whole-string version of each assertion passed while the driver had stopped
    # doing the thing -- found by falsifying, which is the only way it shows.
    code = "\n".join(ln.split("//")[0] for ln in gv.MARK_DRIVER.splitlines())
    assert "data-eligible" in code, (
        "the game view's marking driver no longer reads data-eligible, so whatever it marks is "
        "not what the board computed -- and a hard-coded set would look identical on this board.")
    assert "dgMark(" in code, (
        "the driver never calls dgMark, so the segment loop is neither started nor -- worse -- "
        "stopped, and its inline dash array would survive into the next effect chosen.")


def test_the_marking_never_takes_the_pointer():
    """A decoration that can be hovered is a decoration that breaks hovering.

    The acolyte row carries `pointer-events="none"` for this, and the mark needs it more: it
    straddles the outline, so half its width lies OUTSIDE the tile where the hit rect's clip ends,
    and the portal's dots orbit out there under a glow filter, MOVING. Without this a pointer near
    the edge lands on the mark instead of the tile, and on `portal` it does so intermittently as a
    dot passes beneath the cursor -- a fault that appears only on marked tiles, only near an edge,
    and only sometimes.

    This was not hypothetical. Probing a point on the outline in the built game view resolved to
    `.dg-mring` before the attribute was added.
    """
    dg = studio().grid()
    group = dg.mark_paths("M 0 0 L 10 0 L 10 10 Z")
    assert group.startswith('<g class="dg-mark" pointer-events="none"'), (
        "the marking group no longer disclaims pointer events: %r" % group[:90])




# ---------------------------------------------------------------------------------------------
# THE POPULATION SETS. Two ways of drawing an acolyte, and the numbers that place each of them.
# What is at risk is not that a set draws -- that is visible -- but the three things that are not:
# that a caller who asks for nothing still gets the board it always got, that the two sets agree
# about where the FEET are (the action box is cut to that line), and that a page drawing the hood
# defines the ids its rows point at, because an unresolved <use> draws nothing and says nothing.


def _pop():
    grid()                      # puts ui/render on sys.path
    import population_sets
    return population_sets


TILE_KEYS = {"kind", "aspect", "frac", "overlap", "gap", "step", "lean"}


def test_every_figure_set_names_every_metric_a_row_reads():
    """A set is a table entry, so a missing key is a KeyError at draw time on one page only.

    Asserted as a SET COMPARISON rather than key by key: a set that grows a metric the row does not
    read is as wrong as one missing a metric it does -- the first is a number nobody applies, which
    is how a dial comes to look like it does something.
    """
    pop = _pop()
    for name, s in pop.SETS.items():
        assert set(s["tile"]) == TILE_KEYS, (
            "figure set %r has tile metrics %s; a row reads exactly %s"
            % (name, sorted(s["tile"]), sorted(TILE_KEYS)))
        assert s["tile"]["kind"] in ("image", "hood"), (
            "figure set %r draws %r, which acolyte_row has no branch for" % (name, s["tile"]["kind"]))
        assert isinstance(s.get("label"), str) and s["label"], (
            "figure set %r has no label, so a chooser would show its key" % name)


def test_the_default_set_still_draws_the_numbers_the_board_shipped_with():
    """The gothic figure's own metrics, pinned to LITERALS here.

    This is the one guard in this group that holds its own copy of the numbers, deliberately: every
    other way of writing it compares the module against the table it is now derived from, which
    cannot fail. `FIG_FRAC == pop.tile("gothic")["frac"]` is an identity, not a check.
    """
    g = grid()
    assert (g.FIG_FRAC, g.FIG_OVERLAP, g.STACK_STEP, g.STACK_LEAN) == (0.205, 0.60, 0.30, 0.10), (
        "the default set's metrics moved: %s" % [g.FIG_FRAC, g.FIG_OVERLAP, g.STACK_STEP, g.STACK_LEAN])
    assert abs(g.ACOLYTE_ASPECT - 228 / 210.0) < 1e-12, "the gothic figure's aspect moved"


def test_asking_for_nothing_draws_the_gothic_figure():
    """The default is a contract, not a convenience: the pickers, the layout tool and every guard
    written before sets existed pass no set at all."""
    g = grid()
    counts = {0: [1, 0, 3, 0], 5: [2, 1, 0, 0]}
    # Stubbed, for the reason `drawn_without_the_artwork` gives at length: the duotone PNGs need
    # numpy and Pillow, this guard is about which BRANCH the row takes, and skipping would retire
    # it in the lane that runs everything. THIRD TIME this dependency has escaped into that lane.
    with drawn_without_the_artwork(g):
        plain = g.duty_grid_svg(tiles_dir=None, acolytes=counts, active="sage")
        assert plain == g.duty_grid_svg(tiles_dir=None, acolytes=counts, active="sage",
                                        pop_set="gothic")
    assert "<image href=" in plain, "the default set stopped drawing the figure asset"
    assert "-hood-" not in plain, "the default set is drawing the hooded mark"


def test_the_two_sets_put_their_feet_on_the_same_line():
    """The game view cuts the action box to `acolyte_foot`, so the sets disagreeing about a
    figure's HEIGHT silently moves the box away from the feet it is cut to.

    The hood is sized to the gothic figure's height on purpose -- it is the taller shape, so
    matching the height is what costs it width -- and that choice is one number in the table.
    Falsified in the same test with a deliberately mis-sized third set, because an equality that
    would hold whatever the numbers were is not a check.
    """
    g, pop = grid(), _pop()
    # AGAINST ONE SHAPE, which is the change this guard needed when the tile offsets became per
    # set: `acolyte_foot` walks the laid-out board, and the two sets are now laid out differently
    # on purpose, so comparing it between them measures the arrangement rather than the figure.
    # What must hold is the figure's own height, and that is per shape.
    shape = g.laid_shapes(offsets=False, pop_set="gothic")[0]
    foot = lambda n: (g.acolyte_box(shape, pop_set=n)["sy"]
                      + g.acolyte_box(shape, pop_set=n)["fh"])
    assert abs(foot("hood") - foot("gothic")) < 1e-9, (
        "on one tile the two sets put the figure's foot on different lines: %.4f against %.4f"
        % (foot("hood"), foot("gothic")))
    import copy as _copy
    pop.SETS["_taller"] = _copy.deepcopy(pop.SETS["hood"])
    pop.SETS["_taller"]["tile"]["frac"] *= 1.30
    try:
        assert abs(foot("_taller") - foot("gothic")) > 1.0, (
            "a set 30% taller than the default moved the foot by less than a unit, so the "
            "assertion above would hold for a set of any size and guards nothing")
    finally:
        del pop.SETS["_taller"]


def test_a_page_drawing_the_hood_defines_every_id_its_rows_point_at():
    """An unresolved <use> renders NOTHING and raises nothing.

    A wheel with no acolytes is a board somebody will believe, so this is the failure mode worth
    a guard: the rows and the defs come from two different calls, and only one of them is obvious.
    """
    import re
    g = grid()
    svg = g.duty_grid_svg(tiles_dir=None, acolytes={0: [2, 1, 0, 0], 8: [1, 0, 3, 0]},
                          active="sage", pop_set="hood")
    used = set(re.findall(r'href="#([^"]+)"', svg))
    defined = set(re.findall(r' id="([^"]+)"', svg))
    assert used, "the hood set drew no <use> at all"
    assert used <= defined, "used but never defined here: %s" % sorted(used - defined)
    assert g.pop_defs("dg", "gothic") == "", "the image set emitted defs it does not need"


def test_an_unknown_set_is_refused_rather_than_quietly_replaced():
    """A fallback here draws the other set and looks entirely correct."""
    pop = _pop()
    with pytest.raises(ValueError):
        pop.tile("no_such_set")
    with pytest.raises(ValueError):
        pop.board("gothic")      # a FIGURE set is not a card-row preset


def test_the_wheel_and_the_offsets_tool_name_one_set_between_them():
    """Read out of the SOURCE, not by comparing two imported values.

    Both modules read `population_sets.WHEEL`, so comparing `gen_game_view.POP_SET` to
    `gen_tile_offsets.POP_SET` is comparing a name to itself and holds however either is written.
    What can actually rot is one of them being edited to a literal -- at which point the tool keeps
    judging tile nudges against a row the board has stopped drawing, which is the exact fault that
    file carries two fixed instances of.
    """
    import re
    # The layout tool joined the list when the offsets became per set: it simulates "what will the
    # board look like at this size", and the two sets are up to 52 units apart, so a tool drawing
    # the default while the board draws another is judging screens against the wrong arrangement.
    for name in ("gen_game_view.py", "gen_tile_offsets.py", "gen_layout_tool.py"):
        src = (RENDER / name).read_text(encoding="utf-8")
        line = [ln for ln in src.splitlines() if re.match(r"POP_SET\s*=", ln)]
        assert len(line) == 1, "%s sets POP_SET %d times" % (name, len(line))
        assert "WHEEL" in line[0], (
            "%s names its own set (%s) instead of reading population_sets.WHEEL"
            % (name, line[0].strip()))


# ---------------------------------------------------------------------------------------------
# OFFSETS PER ACOLYTE SET. A tile nudge places a tile against its acolyte ROW, so a row of a
# different shape wants different nudges. The failure worth guarding is not that they can be saved
# separately -- that is visible in the file -- but that the BOARD reads the set it DRAWS. A tool
# that saves nudges nothing applies is a tool you can drag in for an hour.


def test_the_board_reads_the_offsets_of_the_set_it_draws(tmp_path):
    """Written against a file with two DELIBERATELY different sets, because with one set saved
    every set inherits it and any wiring at all looks correct."""
    import json
    g = grid()
    path = tmp_path / "offsets.json"
    path.write_text(json.dumps({
        "wheel_px": 1000, "tile_scale": 1.0,
        "sets": {
            "gothic": {"offsets": {"0": {"dx": 10, "dy": 0}}, "arrangement_shift": {"dx": 0, "dy": 0}},
            "hood": {"offsets": {"0": {"dx": -40, "dy": 25}}, "arrangement_shift": {"dx": 5, "dy": 5}},
        }}), encoding="utf-8")

    a = g.tile_placement(path=path, pop_set="gothic")
    b = g.tile_placement(path=path, pop_set="hood")
    assert a[1][0] == (10.0, 0.0) and b[1][0] == (-40.0, 25.0), (
        "tile_placement gave %s and %s" % (a[1][0], b[1][0]))
    assert a[2] != b[2], "the arrangement shift is not per set"

    # and the shapes the board actually draws move with it
    real = g.OFFSETS
    try:
        g.OFFSETS = path
        shapes = {name: g.laid_shapes(pop_set=name) for name in ("gothic", "hood")}
    finally:
        g.OFFSETS = real
    assert shapes["gothic"] != shapes["hood"], (
        "both sets drew the same nine shapes, so the set never reaches `placed`")


def test_a_set_with_nothing_saved_inherits_and_says_so():
    """Inheriting is deliberate -- zero would throw a real arrangement away the first time a second
    set existed -- but a caller has to be able to tell inherited numbers from its own."""
    g = grid()
    data = {"sets": {"gothic": {"offsets": {"1": {"dx": 3, "dy": 4}}}}}
    block, src = g.offset_block(data, "hood")
    assert src == "gothic" and block["offsets"] == {"1": {"dx": 3, "dy": 4}}, (
        "an unsaved set reported %r" % src)
    block, src = g.offset_block(data, "gothic")
    assert src == "gothic"
    # the pre-set file shape, which is the gothic answer from before sets existed
    legacy = {"offsets": {"2": {"dx": 1, "dy": 1}}, "arrangement_shift": {"dx": 0, "dy": 2}}
    block, src = g.offset_block(legacy, "hood")
    assert src == "legacy" and block is legacy
    assert g.offset_block({}, "hood") == ({}, "none")


def test_saving_one_set_cannot_touch_another(tmp_path):
    """The whole ask. Also checks the one-time migration, because the file predates sets and its
    top-level numbers ARE the gothic answer -- lifted into `sets`, not left in two places."""
    import json
    import importlib
    tool = importlib.import_module("gen_tile_offsets")
    path = tmp_path / "offsets.json"
    legacy = {
        "prose": "what these numbers turned out to be",
        "wheel_px": 877.8, "tile_scale": 0.92,
        "offsets": {"0": {"dx": 2.4, "dy": 20.8}, "5": {"dx": -7.4, "dy": 7.7}},
        "arrangement_shift": {"dx": 0.0, "dy": -21.0},
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")

    real_path, real_set = tool.OFFSETS_PATH, tool.POP_SET
    try:
        tool.OFFSETS_PATH = path
        tool.POP_SET = "hood"
        tool.save_offsets({i: {"dx": float(i), "dy": -1.0} for i in range(9)},
                          shift=(1.0, 2.0), pop_set="hood")
    finally:
        tool.OFFSETS_PATH, tool.POP_SET = real_path, real_set

    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["sets"]["gothic"]["offsets"] == legacy["offsets"], (
        "the pre-set numbers did not survive as the gothic set: %s"
        % after["sets"]["gothic"]["offsets"])
    assert after["sets"]["gothic"]["arrangement_shift"] == legacy["arrangement_shift"]
    assert after["sets"]["hood"]["offsets"]["3"] == {"dx": 3.0, "dy": -1.0}
    assert "offsets" not in after and "arrangement_shift" not in after, (
        "the top-level copies were left behind, so the file now answers twice")
    assert after["prose"] == legacy["prose"], "a save dropped a key it does not own"


def test_the_offsets_tool_draws_its_tiles_where_it_draws_its_acolyte_grid():
    """Both halves of that page must carry the SAME arrangement shift.

    `offsets=False` drops the per-tile nudges and keeps the shift -- that is what holds the rows
    still against the tiles while the block moves -- and the shift is per set now. The tool's base
    wheel was asking for the default set while its frozen acolyte grid asked for the one being
    edited, which put the rows 23.9 units from the tiles they are dragged against. Nothing about
    that page looks wrong; the numbers just come out different.

    BOTH HALVES ALSO HAVE TO AGREE ABOUT THE SHIFT, which is the same question one level up. The
    page applies the shift itself, so both halves start without it; this guard asked for the base
    WITH it and held anyway for as long as the set under test had zero saved, which is the state
    a new set starts in. The first real shift is what made it mean anything.
    """
    grid()
    import gen_tile_offsets as tool
    import gen_duty_grid as g
    base = g.duty_grid_svg(tiles_dir=None, klass="wheel", offsets=False, pop_set=tool.POP_SET,
                           shift=False)
    for d in tool.scaled_shapes():
        assert d in base, (
            "the tool measures its acolyte grid off a shape its own wheel does not draw; the two "
            "are asking for different sets")
