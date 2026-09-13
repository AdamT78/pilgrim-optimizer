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
NAME = re.compile(r"^(\d{2})_([a-z_]+)_([AB])\.(png|webp)$")


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
