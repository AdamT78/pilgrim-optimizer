#!/usr/bin/env python3
"""Trace a generated cell sheet into the outlines the board draws.

    python3 ui/render/trace_grid_sheet.py sheet.png --out /tmp/shapes.json
    python3 ui/render/trace_grid_sheet.py sheet.png --out ... --write   # over the real file

WHAT THIS REPLACES

`duty_grid_shapes.json` says `source: "Duty_wheel_base_v1.png, contours traced and smoothed"`,
and that tracing was done outside the tree. So the one step that turns a generated picture into
the geometry the whole board rests on has never been repeatable, and the record of how the shapes
were derived is a sentence rather than a program. This is that program.

SIX SHAPES, NINE CELLS

The sheet carries SIX cells and the board needs nine. Three of the six are emitted twice, once as
drawn and once mirrored about their own centre, which is not a saving so much as a correction:
asked for nine, the image tool mirrors the left and right columns by itself -- measured at 0.982,
0.995 and 0.996 overlap after a horizontal flip on the first sheet it produced. Doing it here
instead makes those pairs 1.000, and a pair that is nearly identical is worse than one that either
matches or does not: the acolyte row and the duty value have to be the same on every tile, because
they are the two things a player reads ACROSS tiles, and "nearly the same width" is a difference
that looks intentional and is not.

Only horizontal mirroring is available. A vertical flip would put the flat base at the top, and
the base is where the acolytes stand.

WHY THE TRACE IS RADIAL, AND WHY THAT IS CHECKED RATHER THAN ASSUMED

Each outline is sampled as one radius per angle from the cell's centroid, which gives an evenly
spaced polygon of the same shape the existing file already holds -- `M x y L x y ... Z`, no
curves -- and needs nothing but numpy and Pillow. The repo declares no dependencies at all, and a
contour tracer is not the place to acquire the first two.

A radial trace is exact for a star-shaped region and silently WRONG for anything with an
undercut: it cuts the concavity off and returns a plausible, smaller shape. So the area of the
polygon is compared against the area of the region it came from, and a cell that differs by more
than a per cent is refused by name rather than quietly simplified.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_duty_grid as dg          # noqa: E402  (needs the path line above)

MARGIN_FOR_SCALE = dg.MARGIN        # the board's own outer margin, so the two agree by reading

REPO = pathlib.Path(__file__).resolve().parents[2]
SHAPES = REPO / "ui" / "assets-gothic" / "metadata" / "duty_grid_shapes.json"

BOX = 1000.0          # the coordinate space the board's shapes live in
RAYS = 128            # points per outline; the committed set carries about 125
SMOOTH = 5            # circular moving average over the radii, in samples
INK = 128             # below this is a line, above it is parchment
MIN_AREA = 5000       # px; anything smaller is speckle, not a cell
AREA_TOL = 0.01       # how far the radial polygon may fall short of its own region

# HOW MUCH CHANNEL THERE IS BETWEEN NEIGHBOURS, as a fraction of a cell's width -- and the reason
# it is here rather than inherited from the sheet. `place()` already says the tiles' positions on
# a generated sheet "are an accident while their shapes are not"; the SPACING is the same accident
# one step on, and taking the scale from `box / sheet_width` quietly inherits it. Two sheets from
# the same prompt came back at 5.5% and 13.4% between neighbours, which is a visibly different
# board from the same shapes.
#
# 5.5% is the tighter of the two and the one that reads as a wheel rather than as six things on a
# page. Cells are scaled so that three of them, two channels and two margins fill the box exactly,
# which also makes the traced size independent of how many cells the sheet happened to carry.
CHANNEL = 0.055

# WHICH OF THE SIX GOES WHERE, and which of the nine are mirrors. Positions are the board's own
# reading order, so index 4 is the centre -- `DUTY_NAMES[4]` is The City, which is why the sheet
# asks for one cell without a lobe and why that one is checked for below rather than trusted.
#
# The three mirrored pairs are the two corner pairs and the side pair; top-centre and
# bottom-centre have no horizontal partner and are drawn separately. That is six shapes for nine
# cells and it is the floor, not a compromise.
PLAN = (
    (0, 0, False), (1, 3, False), (2, 0, True),      # top row:    s0, s3, s0 mirrored
    (3, 1, False), (4, 4, False), (5, 1, True),      # middle row: s1, hub, s1 mirrored
    (6, 2, False), (7, 5, False), (8, 2, True),      # bottom row: s2, s5, s2 mirrored
)
HUB_CELL = 4          # which traced cell is the one without a lobe


def cells_in(path: pathlib.Path) -> tuple[list[np.ndarray], tuple[int, int], list[int]]:
    """Every closed region of parchment enclosed by ink, in reading order.

    The sheet's own field is found first and discarded: it is the one pale region that reaches
    the border. What is left is the cells, and they are separated by flood fill rather than by a
    labelling library -- Pillow's is in C and the alternative is a dependency.
    """
    from PIL import ImageDraw
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im)
    grey = np.asarray(im.convert("L")).astype(np.int16)
    h, w = grey.shape

    # FIELD = 64, INK = 0, everything still 255 is enclosed parchment. The field is taken first
    # and kept, because its colour is what the board's `parchment` value has always been -- the
    # sheet's own, sampled, rather than a colour anybody chose.
    # `.copy()` IS LOad-BEARING. An Image built straight from a numpy array wraps that array's
    # buffer read-only on Pillow 12, and floodfill writes through `load()` -- so the fill silently
    # does nothing and the array comes back untouched. Measured: 0 pixels filled without it, 200
    # of 200 with it. The guard below is what turned that into a message instead of an empty trace.
    img = Image.fromarray(np.where(grey < INK, 0, 255).astype(np.uint8), "L").copy()
    ImageDraw.floodfill(img, (0, 0), 64)
    a = np.array(img)
    field = a == 64
    if not field.any():
        raise SystemExit(
            "%s: flooding from the top-left corner filled nothing, so the corner is not bare "
            "parchment. Either the sheet has a border or it is not a cell sheet." % path.name)
    if not (a == 255).any():
        raise SystemExit(
            "%s has no enclosed parchment: every pale pixel reached the border, so at least one "
            "outline is broken." % path.name)
    parch = [int(v) for v in rgb[field].mean(axis=0).round()]

    masks, tops = [], []
    while (a == 255).any():
        ys, xs = np.nonzero(a == 255)
        img = Image.fromarray(a, "L").copy()          # see the note above
        ImageDraw.floodfill(img, (int(xs[0]), int(ys[0])), 1)
        a = np.array(img)
        m = a == 1
        if m.sum() >= MIN_AREA:
            ys2, xs2 = np.nonzero(m)
            masks.append(m)
            tops.append((int(ys2.min()), int(xs2.min())))
        a[m] = 64                       # consumed, whether it was a cell or speckle

    # reading order: banded into rows by a third of the sheet's height, then left to right
    order = sorted(range(len(masks)), key=lambda i: (tops[i][0] * 3 // h, tops[i][1]))
    return [masks[i] for i in order], (w, h), parch


def outline(mask: np.ndarray) -> tuple[list[tuple[float, float]], float]:
    """One cell as an evenly angled polygon, with the fraction of its area the polygon keeps."""
    ys, xs = np.nonzero(mask)
    cx, cy = xs.mean(), ys.mean()
    reach = math.hypot(mask.shape[1], mask.shape[0])
    # one ray per angle: the furthest filled sample along it
    rad = []
    for k in range(RAYS):
        t = 2 * math.pi * k / RAYS
        dx, dy = math.cos(t), math.sin(t)
        steps = np.arange(0, reach, 0.5)
        px = np.clip((cx + dx * steps).astype(int), 0, mask.shape[1] - 1)
        py = np.clip((cy + dy * steps).astype(int), 0, mask.shape[0] - 1)
        hit = mask[py, px]
        last = np.nonzero(hit)[0]
        rad.append(float(steps[last.max()]) if last.size else 0.0)
    r = np.array(rad)
    if SMOOTH > 1:
        k = np.ones(SMOOTH) / SMOOTH
        r = np.convolve(np.concatenate([r[-SMOOTH:], r, r[:SMOOTH]]), k, "same")[SMOOTH:-SMOOTH]
    pts = [(cx + r[k] * math.cos(2 * math.pi * k / RAYS),
            cy + r[k] * math.sin(2 * math.pi * k / RAYS)) for k in range(RAYS)]
    poly = 0.5 * abs(sum(pts[k][0] * pts[(k + 1) % RAYS][1] - pts[(k + 1) % RAYS][0] * pts[k][1]
                         for k in range(RAYS)))
    return pts, poly / mask.sum()


def crop(mask: np.ndarray) -> np.ndarray:
    """A cell on its own. The masks are sheet-sized, and every measurement below is about the
    CELL -- its width, its own bottom edge -- so measuring against the sheet would report the
    sheet's geometry under the cell's name."""
    ys, xs = np.nonzero(mask)
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def base_flatness(mask: np.ndarray) -> int:
    """How far the bottom edge wanders across the central two thirds, in pixels. Ruled is 0-3."""
    mask = crop(mask)
    w = mask.shape[1]
    low = [np.nonzero(mask[:, x])[0].max() for x in range(w // 6, w - w // 6)]
    return int(max(low) - min(low))


def lobe_depth(mask: np.ndarray) -> float:
    """How far the top outline departs from its own smoothed self, as a fraction of height."""
    mask = crop(mask)
    w, h = mask.shape[1], mask.shape[0]
    high = np.array([np.nonzero(mask[:, x])[0].min() for x in range(w // 6, w - w // 6)],
                    dtype=float)
    n = max(9, w // 6)
    sm = np.convolve(np.pad(high, n, mode="edge"), np.ones(n) / n, "same")[n:-n]
    return float(np.abs(high - sm).max()) / h


def path_of(pts) -> str:
    return "M " + " L ".join("%.1f %.1f" % (x, y) for x, y in pts) + " Z"


def mirrored(pts) -> list[tuple[float, float]]:
    """About the shape's own centre, so it stays where it was and only turns over."""
    cx = (min(x for x, _ in pts) + max(x for x, _ in pts)) / 2
    return [(2 * cx - x, y) for x, y in pts][::-1]


def trace(path: pathlib.Path, box: float = BOX) -> tuple[dict, list]:
    masks, (w, h), parch = cells_in(path)
    if len(masks) != 6:
        raise SystemExit(
            "%s holds %d cells, not 6. The plan that turns six shapes into nine names each one "
            "by position, so a sheet with a different count cannot be placed without saying what "
            "the new cells are for." % (path.name, len(masks)))

    # SCALE TO THE ARRANGEMENT, not to the sheet. See CHANNEL above.
    widths = [float(crop(m).shape[1]) for m in masks]
    want = (box - 2 * MARGIN_FOR_SCALE) / (3 + 2 * CHANNEL)
    scale = want / (sum(widths) / len(widths))
    traced, report = [], []
    for i, m in enumerate(masks):
        pts, keep = outline(m)
        if keep < 1 - AREA_TOL:
            raise SystemExit(
                "cell %d loses %.1f%% of its area to the radial trace, which means its outline "
                "turns back on itself somewhere -- an undercut, or a lobe deep enough to hide "
                "part of the edge behind it. The trace would return a plausible smaller shape "
                "and say nothing, so it stops here instead." % (i, (1 - keep) * 100))
        ys, xs = np.nonzero(m)
        # the masks are full-sheet sized, so the points are already in the sheet's own space and
        # only need the one scale into the board's box
        traced.append([(x * scale, y * scale) for x, y in pts])
        report.append(dict(i=i, w=int(xs.max() - xs.min() + 1), h=int(ys.max() - ys.min() + 1),
                           flat=base_flatness(m), lobe=lobe_depth(m), keep=keep))

    quiet = min(report, key=lambda r: r["lobe"])["i"]
    if quiet != HUB_CELL:
        print("  NOTE the cell with the shallowest lobe is %d, not the %d the plan calls the hub "
              "-- the sheet put the plain cell somewhere else, so check the placement."
              % (quiet, HUB_CELL), file=sys.stderr)

    shapes, origin = [], []
    for pos, cell, flip in PLAN:
        pts = mirrored(traced[cell]) if flip else traced[cell]
        shapes.append(path_of(pts))
        origin.append({"cell": cell, "mirrored": flip})
    return {
        "box": box,
        "cell_width": round(sum(widths) / len(widths) * scale, 1),
        "channel": CHANNEL,
        "parchment": parch,
        "source": "%s, contours traced and smoothed by trace_grid_sheet.py" % path.name,
        "cells": len(masks),
        "from": origin,
        "shapes": shapes,
    }, report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, help="where to write; default beside the sheet")
    ap.add_argument("--box", type=float, default=BOX)
    ap.add_argument("--write", action="store_true",
                    help="write over %s itself" % SHAPES.relative_to(REPO))
    args = ap.parse_args()

    data, report = trace(args.sheet, args.box)
    out = SHAPES if args.write else (args.out or args.sheet.with_suffix(".shapes.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1), encoding="utf-8")

    print("traced %s -> %s" % (args.sheet.name, out))
    print("  parchment %s, box %.0f, %d cells -> %d shapes"
          % (data["parchment"], data["box"], data["cells"], len(data["shapes"])))
    print("  scaled to a %.1f%% channel between neighbours: cells come out %.1f units wide, "
          "against the committed set's 305" % (CHANNEL * 100, data["cell_width"]))
    ws = [r["w"] for r in report]
    print("  widths %d..%d px, spread %.1f%% (the committed set holds 5%%)"
          % (min(ws), max(ws), (max(ws) / min(ws) - 1) * 100))
    for r in report:
        print("    cell %d  %4d x %4d  base wanders %d px  lobe %.1f%% of height  trace keeps "
              "%.2f%% of the area" % (r["i"], r["w"], r["h"], r["flat"], r["lobe"] * 100,
                                      r["keep"] * 100))
    pairs = [(p, c["cell"]) for p, c in enumerate(data["from"]) if c["mirrored"]]
    print("  mirrored into place: %s"
          % ", ".join("position %d from cell %d" % (p, c) for p, c in pairs))


if __name__ == "__main__":
    main()
