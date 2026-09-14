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

These run in the `ui` lane, which is the lane a design-only pull request actually triggers.
"""

from __future__ import annotations

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
    so shuffling the tiles must not move a single arrow."""
    g = grid()
    import re
    arrows = lambda svg: re.findall(r'<g transform="translate\([^"]+\) rotate\([^"]+\)"', svg)
    a = arrows(g.duty_grid_svg(tiles_dir=None))
    b = arrows(g.duty_grid_svg(tiles_dir=None, cells=[2, 5, 3, 8, 4, 6, 1, 7, 0]))
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
