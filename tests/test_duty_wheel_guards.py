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
    assert tool.scaled_shapes() == g.laid_shapes(offsets=False), (
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


def test_the_arrows_do_not_depend_on_the_arrangement():
    """Which squares are adjacent is a property of the grid, not of which duty was dealt where,
    so shuffling the tiles must not move a single arrow.

    `arrows=True` is passed EXPLICITLY. The default became False when the arrows were taken off the
    board, and this guard then failed -- correctly, and usefully: it asserts `a and a == b`, so an
    empty `a` fails rather than passing vacuously, which is the difference between noticing a
    changed default and silently testing nothing. What it guards is how the arrows behave when
    drawn, not whether they are drawn, so it asks for them.
    """
    g = grid()
    import re
    arrows = lambda svg: re.findall(r'<g transform="translate\([^"]+\) rotate\([^"]+\)"', svg)
    a = arrows(g.duty_grid_svg(tiles_dir=None, arrows=True))
    b = arrows(g.duty_grid_svg(tiles_dir=None, arrows=True, cells=[2, 5, 3, 8, 4, 6, 1, 7, 0]))
    assert a and a == b, "the arrows moved when the arrangement changed"


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


def test_every_arrow_clears_its_destination_and_reaches_under_its_source():
    """The arrow geometry, which is four constants that have to agree with the torn outlines.

    Each arrow is one length, anchored at the tile it points AT and masked by the tile it leaves.
    Two things must hold for all twelve, and neither is visible in the markup:

        the head stops short of the destination outline, or the arrow crosses into the next duty
        the tail ends inside the source outline, or it floats in the channel with a visible butt

    They pull against each other -- a shorter arrow clears more easily but stops reaching under --
    and the margin between them is thin: the channels vary, and the widest source gap is 75.5
    units against ARROW_LEN 90. Changing ARROW_LEN, ARROW_GAP, ARROW_W, ARROW_STROKE or MARGIN
    can break either end, and the render still looks plausible at a glance.
    """
    g = grid()
    meta = g.load()
    laid = g.place(meta["shapes"], meta["box"], g.MARGIN)
    bad = []
    for a, b in g.RING + g.CITY_ROUTES:
        x, y, ang = g._channel(laid[a], laid[b])
        dest = g._ray_hit(laid[b], x, y, ang)
        head = dest - g._inset(g.ARROW_W, meta["box"])
        tail = head - g.ARROW_LEN
        src = -g._ray_hit(laid[a], x, y, (ang + 180) % 360)
        if head >= dest:
            bad.append("%d->%d head reaches %.1f, destination outline at %.1f" % (a, b, head, dest))
        if tail >= src:
            bad.append("%d->%d tail ends at %.1f, source outline at %.1f -- it would float"
                       % (a, b, tail, src))
    assert not bad, "arrow geometry no longer fits the tiles:\n  " + "\n  ".join(bad)


def test_the_arrow_gap_is_the_gap_that_is_drawn():
    """ARROW_GAP must be the clear ground you SEE, not the distance between two path tips.

    Both shapes are stroked and strokes sit centred on their paths, so an inset that ignores them
    is consumed by ink: this is how ARROW_INSET = 2.0 came to leave the arrow and tile outlines
    OVERLAPPING by 2.3 units while claiming a 2-unit gap.

    The stroke is read back out of the EMITTED markup rather than from the constant `_inset`
    reads, because otherwise the two sides of this check are the same number and it cannot fail.
    What it is really guarding is that `arrow()` and `_inset()` still agree about how much ink
    there is -- which is exactly what stops being true when one of them is edited to a literal.
    """
    import re
    g = grid()
    box = g.load()["box"]
    svg = g.duty_grid_svg(tiles_dir=None, arrows=True)
    widths = {float(w) for w in re.findall(r'stroke-width="([\d.]+)" stroke-linejoin', svg)}
    drawn = [w for w in widths if abs(w - g.ARROW_W * g.ARROW_STROKE) < 0.01]
    assert drawn, ("no arrow stroke of the expected weight is in the markup; `arrow()` and "
                   "ARROW_STROKE have parted company (found %s)" % sorted(widths))
    ink = drawn[0] / 2 + box * 0.0035 / 2          # half the arrow's ink, half the tile's
    assert g._inset(g.ARROW_W, box) - ink == pytest.approx(g.ARROW_GAP, abs=0.02), (
        "_inset does not allow for the ink actually drawn: the gap on screen is %.2f units, not "
        "the %.2f that ARROW_GAP promises"
        % (g._inset(g.ARROW_W, box) - ink, g.ARROW_GAP))
    assert g.ARROW_GAP > 0, "a zero or negative gap puts the arrow head against the tile"


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


def _numerals(svg):
    """Every acolyte numeral in the emitted markup, as (x, y, value)."""
    import re
    body = svg[svg.index('<g class="dg-acolytes'):]
    return [(float(x), float(y), int(v)) for x, y, v in
            re.findall(r'<text x="([\d.\-]+)" y="([\d.\-]+)"[^>]*>(\d+)</text>', body)]


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
        marks = [(x, y) for x, y, v in _numerals(svg) if v == 7]
        assert len(marks) == 1, "expected exactly one 7, found %d" % len(marks)
        x, y = marks[0]
        landed = [i for i, r in enumerate(rows)
                  if r["sx"] <= x <= r["sx"] + 4 * r["fw"] + 3 * r["gap"]
                  and r["sy"] <= y <= r["sy"] + r["fh"] * 1.05]
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
        data["arrangement_shift"] = {"dx": 0.0, "dy": 0.0}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        base, laid0, rows0 = depths(0)

        data["arrangement_shift"] = {"dx": -17.0, "dy": -23.0}
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

        data["arrangement_shift"] = {"dx": -68.0, "dy": -92.0}      # four times as far
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
    foot = G["banner_h"] + G["wheel"] * (g.acolyte_foot() / box)
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
        was = float((data.get("arrangement_shift") or {}).get("dy", 0.0))
        before = g.acolyte_foot()
        data["arrangement_shift"] = {"dx": 0.0, "dy": was - 60.0}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        after = g.acolyte_foot()
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
    """The figures drawn under ONE tile, as (x, count), found by that tile's own row rectangle.

    By the RECTANGLE, not the column. Squares 0, 3 and 6 share an x range, so a filter on x alone
    picks up three rows and reads as one -- which has now produced a wrong answer twice in this
    file's history, once reporting a working fix as broken.
    """
    import re
    b = g.acolyte_box(shape, seats)
    lo, hi = b["sx"] - 1.0, b["sx"] + len(seats) * (b["fw"] + b["gap"]) + 1.0
    top, bot = b["sy"] - 1.0, b["sy"] + b["fh"] * 1.05
    body = svg[svg.index('<g class="dg-acolytes'):]
    out = []
    for x, y, v in re.findall(
            r'<image href="[^"]*" x="([\d.\-]+)" y="([\d.\-]+)"[^>]*/><text[^>]*>(\d+)</text>',
            body):
        if lo <= float(x) <= hi and top <= float(y) <= bot:
            out.append((float(x), int(v)))
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

    A row of figures each labelled 0 is the same picture as a row with one player present until
    four small numbers are read. So a zero draws nothing.

    The rest keep their slots. That is the half worth guarding: reflowing to close the gap would
    make the second figure mean a different player on every tile, and a row is only readable at a
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
