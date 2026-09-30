#!/usr/bin/env python3
"""Cut one wide duty master into the two action images the board draws.

    python3 tools/duty_art/crop_duty_master.py MASTER.png --out-dir crops

THE CARDS ARE ADJACENT, NOT OVERLAPPING. This replaces a model where the two windows were
anchored flush to the master's left and right edges and shared whatever strip was left in the
middle. The shared strip was there to make the two cards read as one place -- and it never
really did, because it meant the middle of the drawing appeared twice and each card's own
composition had to survive being half a duplicate.

What the board actually shows is two boxes with a gap between them. So the master is cropped
ONCE to the shape of that whole span, gap included, and then split where the gap falls. The gap
hides a sliver of the picture instead of the two cards sharing one. The pillar carries across,
the floor line runs through, and the gap reads as depth rather than as a join between two
unrelated pictures.

Two consequences worth stating, because they are the reason this is simpler than what it
replaces:

  * THERE IS NOTHING TO CHOOSE. The old model had an overlap, an inset and a crop size, none of
    which the board had an opinion about, so all three were argued about per image. Here the
    only free parameter is how far down the master to take the band.

  * THE RATIO IS EXACT BY CONSTRUCTION. A card is `span x slot_width/span` wide and
    `span x slot_height/span` tall, so its ratio is the slot's ratio however wide the master is,
    give or take a pixel of integer rounding. The old model cut 1120 x 560 into a 375 x 184 box
    -- 2.000 against 2.038 -- and the board quietly threw away 1.9% of every image's height
    with `fit: cover`, about five pixels off the top and five off the bottom, forever.

NOTHING HERE IS TYPED. The slot size and the gap come from the layout lab's own default_state(),
the way ui/board_v2/canvas_check does it. The one number this file must not invent is the shape
of the box its output goes into.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAB = ROOT / "ui" / "board_v2" / "layout_lab" / "generate_layout_lab.py"


def band() -> dict:
    """The span the two action slots occupy on the board, gap included.

    LOUD ON FAILURE. Every number below is a consequence of this one, and a hard-coded fallback
    would let the script go on cutting confidently for a board that had moved underneath it.
    """
    if not LAB.is_file():
        raise SystemExit("the layout lab generator is not at %s -- it owns the shape this cuts "
                         "to and there is nothing to cut to without it" % LAB)
    spec = importlib.util.spec_from_file_location("_crop_lab", LAB)
    if spec is None or spec.loader is None:        # pragma: no cover - unreachable in practice
        raise SystemExit("could not load %s" % LAB)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_crop_lab"] = mod
    spec.loader.exec_module(mod)

    S = mod.default_state()
    L, R = S["display"]["artLeft"], S["display"]["artRight"]
    if (L["width"], L["height"]) != (R["width"], R["height"]):
        raise SystemExit(
            "the two action slots are no longer the same shape (%dx%d and %dx%d). This cut "
            "assumes one card shape serves both and needs rethinking rather than patching."
            % (L["width"], L["height"], R["width"], R["height"]))
    gap = R["x"] - (L["x"] + L["width"])
    if gap < 0:
        raise SystemExit("the two action slots overlap on the board by %d px; there is no gap "
                         "for this cut to hide picture in" % -gap)
    return {"card_w": L["width"], "card_h": L["height"], "gap": gap,
            "span": L["width"] * 2 + gap}


def boxes(master_w: int, master_h: int, b: dict, y: int | None = None) -> dict:
    """The two rectangles, and the band they are taken from.

    The band is as wide as the master and as tall as the span's own proportion makes it, so the
    full width of the drawing is always used and only height is ever discarded -- which is the
    axis a generator gives you spare, since the board's band is wider than anything ChatGPT will
    draw.
    """
    band_h = round(master_w * b["card_h"] / b["span"])
    if band_h > master_h:
        raise SystemExit(
            "this master is %d x %d, and at its width the band wants to be %d tall -- %d more "
            "than it has. It is too TALL for its width, not too small: crop or regenerate it "
            "nearer %.2f:1." % (master_w, master_h, band_h, band_h - master_h,
                                b["span"] / b["card_h"]))
    # THE TWO CARDS ARE THE SAME WIDTH, AND THE GAP TAKES THE ROUNDING. Working out the gap
    # independently gave cards of 1065 and 1064 on a 2172px master -- a pixel apart, which the
    # board would then scale by slightly different amounts. The gap is the one part of this that
    # nobody ever sees, so it is where the odd pixel belongs.
    left_w = round(master_w * b["card_w"] / b["span"])
    gap_w = master_w - 2 * left_w
    if gap_w < 0:
        raise SystemExit("two cards do not fit across this master, which cannot happen for a "
                         "gap of %d -- the slot geometry has changed shape" % b["gap"])
    # CENTRED UNLESS TOLD OTHERWISE. The band is shorter than the master, so something has to
    # decide what to drop; centring is a default, not a recommendation, and --y overrides it.
    top = (master_h - band_h) // 2 if y is None else y
    if not 0 <= top <= master_h - band_h:
        raise SystemExit("--y %d puts the band outside the master; it must be 0..%d"
                         % (top, master_h - band_h))
    return {
        "band_h": band_h, "top": top, "gap_w": gap_w,
        "left": (0, top, left_w, top + band_h),
        "right": (master_w - left_w, top, master_w, top + band_h),
    }


def crop_duty_master(input_path: pathlib.Path, out_dir: pathlib.Path,
                     left_name: str | None = None, right_name: str | None = None,
                     y: int | None = None, quiet: bool = False) -> tuple[pathlib.Path, pathlib.Path]:
    img = Image.open(input_path)
    # RGB, not RGBA. These are opaque scenes dropped into an opaque box, and an alpha channel
    # that is 255 everywhere is a third of the file for nothing.
    img = img.convert("RGB")
    b = band()
    g = boxes(img.width, img.height, b, y)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    left_path = out_dir / (left_name or "%s_left.png" % stem)
    right_path = out_dir / (right_name or "%s_right.png" % stem)
    lw = g["left"][2] - g["left"][0]
    rw = g["right"][2] - g["right"][0]
    if lw != rw:
        raise SystemExit("the two cards came out %d and %d px wide; they must match or the "
                         "board scales them differently" % (lw, rw))
    img.crop(g["left"]).save(left_path)
    img.crop(g["right"]).save(right_path)

    if not quiet:
        cw = g["left"][2] - g["left"][0]
        print("master      %d x %d" % (img.width, img.height))
        print("band        %d x %d at y %d   (the %d x %d span, gap included)"
              % (img.width, g["band_h"], g["top"], b["span"], b["card_h"]))
        print("LEFT        %s" % (g["left"],))
        print("RIGHT       %s" % (g["right"],))
        print("the gap hides %d px of picture between them" % g["gap_w"])
        print("card        %d x %d   ratio %.5f   (the slot is %.5f)"
              % (cw, g["band_h"], cw / g["band_h"], b["card_w"] / b["card_h"]))
        print("scale       %.2fx the %d x %d slot" % (cw / b["card_w"], b["card_w"], b["card_h"]))
        print("wrote       %s" % left_path)
        print("            %s" % right_path)
    return left_path, right_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=pathlib.Path, help="the wide master image")
    ap.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("crops"))
    ap.add_argument("--left-name", default=None)
    ap.add_argument("--right-name", default=None)
    ap.add_argument("--y", type=int, default=None,
                    help="top of the band in master pixels (default: centred). The only thing "
                         "here anybody has to decide.")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    crop_duty_master(a.input, a.out_dir, a.left_name, a.right_name, a.y, a.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
