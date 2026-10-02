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

NOTHING HERE IS TYPED. The slot size and the gap come from ui/board_v2/action_board/geometry.py,
the way ui/board_v2/canvas_check does it. The one number this file must not invent is the shape
of the box its output goes into.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GEOMETRY = ROOT / "ui" / "board_v2" / "action_board" / "geometry.py"


def band() -> dict:
    """The span the two action slots occupy on the board, gap included.

    FROM geometry.py, WHICH OWNS IT. The numbers used to come from the layout lab's saved state,
    which was right while the lab was where the composition was decided. The action board is what
    ships now, and a cut made to a draggable state is a cut made to whatever somebody last dragged.

    LOUD ON FAILURE. Every number below is a consequence of this one, and a hard-coded fallback
    would let the script go on cutting confidently for a board that had moved underneath it.
    """
    if not GEOMETRY.is_file():
        raise SystemExit("the board's geometry is not at %s -- it owns the shape this cuts "
                         "to and there is nothing to cut to without it" % GEOMETRY)
    spec = importlib.util.spec_from_file_location("_crop_geometry", GEOMETRY)
    if spec is None or spec.loader is None:        # pragma: no cover - unreachable in practice
        raise SystemExit("could not load %s" % GEOMETRY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_crop_geometry"] = mod
    spec.loader.exec_module(mod)

    # ASKED OF THE PUBLISHED RECTS, not of ART_W and ART_H. Those two constants cannot disagree
    # with each other, so checking them against each other would assert nothing. The slots as the
    # board publishes them can differ, and that is the failure worth catching.
    slots = mod.as_dict()["slots"]
    L, R = slots["actionA"], slots["actionB"]
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


# =================================================================================================
# TINT MATCHING. Optional, and off unless it is asked for.
#
# WORDING CANNOT HIT A COLOUR TARGET. Eleven masters across four briefs came back between 0.15 and
# 0.27 median saturation, and the scatter INSIDE a single brief -- as much as 0.055 -- is wider
# than the whole distance from the greyest of them to the warmest. Each rewrite moved the average
# and none of them set the value. A board whose duties agree cannot be had by asking for it.
#
# So it is done here, where it is arithmetic instead. The mean and spread of the two CHROMA
# channels in CIELAB are matched to a reference and L* IS LEFT ALONE. That restraint is the whole
# point: L* carries the engraving -- the hatching, the contrast, how far the darks go -- and none
# of it moves. Only the colour the ink is dyed with changes. Measured on the Ordination pair
# against Clerical v03: median saturation 0.176 -> 0.243 against the reference's 0.239, while L
# mean stayed at 65.2 and its spread went 37.6 -> 37.5.
#
# TWO THINGS THIS DELIBERATELY IS NOT. It is a colour transform and moves no pixel, so nothing
# about registration is touched. And it never writes to a master: only crops are matched, the
# master keeps whatever came out of the generator, and a crop can always be cut again -- with a
# different reference, a different strength, or none.

_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                 [0.2126729, 0.7151522, 0.0721750],
                 [0.0193339, 0.1191920, 0.9503041]])
_XYZ_INV = np.linalg.inv(_XYZ)
_WHITE = np.array([0.95047, 1.0, 1.08883])          # D65, the sRGB white point
_EPS, _KAPPA = 216 / 24389, 24389 / 27

# Fitted on mid-tones only. Near-black pixels carry no reliable chroma -- the hue of a shadow is
# mostly rounding -- and letting them into the mean drags the fit towards whatever the darks
# happen to be. The transform is FITTED on this range and then applied to every pixel.
_FIT_LO, _FIT_HI = 12.0, 92.0


def rgb_to_lab(rgb) -> np.ndarray:
    """sRGB (0-255) to CIELAB, in numpy alone. Agrees with scikit-image to 0.005 LAB units."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _XYZ.T / _WHITE
    f = np.where(xyz > _EPS, np.cbrt(np.maximum(xyz, 0)), (_KAPPA * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_rgb(lab) -> np.ndarray:
    """CIELAB back to sRGB (0-255, float). Round-trips rgb_to_lab exactly."""
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16) / 116
    fx, fz = fy + lab[..., 1] / 500, fy - lab[..., 2] / 200
    x = np.where(fx ** 3 > _EPS, fx ** 3, (116 * fx - 16) / _KAPPA)
    y = np.where(fy ** 3 > _EPS, fy ** 3, lab[..., 0] / _KAPPA)
    z = np.where(fz ** 3 > _EPS, fz ** 3, (116 * fz - 16) / _KAPPA)
    lin = np.stack([x, y, z], axis=-1) * _WHITE @ _XYZ_INV.T
    srgb = np.where(lin <= 0.0031308, lin * 12.92,
                    1.055 * np.maximum(lin, 0) ** (1 / 2.4) - 0.055)
    return np.clip(srgb, 0.0, 1.0) * 255.0


def chroma_stats(band) -> list:
    """(mean, sd) of a* and b* over the mid-tones of one band."""
    lab = rgb_to_lab(band)
    m = (lab[..., 0] > _FIT_LO) & (lab[..., 0] < _FIT_HI)
    if m.sum() < 1000:
        raise SystemExit("the reference has almost no mid-tones in it (%d pixels between L* %g "
                         "and %g), so there is nothing to fit a tint to. Pass a picture, not a "
                         "swatch or a silhouette." % (m.sum(), _FIT_LO, _FIT_HI))
    return [(float(lab[..., c][m].mean()), float(lab[..., c][m].std())) for c in (1, 2)]


def apply_tint(rgb, src_stats, ref_stats, strength: float = 1.0) -> np.ndarray:
    """Move rgb's chroma from src_stats onto ref_stats. L* is returned untouched.

    src_stats is measured on the WHOLE source band, not on one crop, so the two cards get the
    same mapping and cannot drift apart from each other.
    """
    lab = rgb_to_lab(rgb)
    out = lab.copy()
    for i, c in enumerate((1, 2)):
        (sm, ssd), (rm, rsd) = src_stats[i], ref_stats[i]
        moved = (lab[..., c] - sm) * (rsd / max(ssd, 1e-6)) + rm
        out[..., c] = lab[..., c] + strength * (moved - lab[..., c])
    return lab_to_rgb(out).round().astype(np.uint8)


def crop_duty_master(input_path: pathlib.Path, out_dir: pathlib.Path,
                     left_name: str | None = None, right_name: str | None = None,
                     y: int | None = None, quiet: bool = False,
                     match: pathlib.Path | None = None,
                     match_strength: float = 1.0) -> tuple[pathlib.Path, pathlib.Path]:
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
    left_img, right_img = img.crop(g["left"]), img.crop(g["right"])
    fit = None
    if match is not None:
        if not 0.0 <= match_strength <= 1.0:
            raise SystemExit("--match-strength is a fraction from 0 to 1, not %g" % match_strength)
        ref = Image.open(match).convert("RGB")
        # THE REFERENCE IS ITS BAND, not the whole file. The band is the part that ships, and it
        # is what the source is being compared against; the overscan a master carries above and
        # below is thrown away on both sides and has no business in the fit.
        rg = boxes(ref.width, ref.height, b, None)
        ref_band = np.asarray(ref.crop((0, rg["top"], ref.width, rg["top"] + rg["band_h"])))
        src_band = np.asarray(img.crop((0, g["top"], img.width, g["top"] + g["band_h"])))
        src_stats, ref_stats = chroma_stats(src_band), chroma_stats(ref_band)
        fit = (src_stats, ref_stats)
        left_img = Image.fromarray(apply_tint(np.asarray(left_img), src_stats, ref_stats,
                                              match_strength))
        right_img = Image.fromarray(apply_tint(np.asarray(right_img), src_stats, ref_stats,
                                               match_strength))
    left_img.save(left_path)
    right_img.save(right_path)

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
        if fit is None:
            print("tint        left as generated")
        else:
            (sa, sb), (ra, rb) = fit[0], fit[1]
            print("tint        matched to %s at %.2f" % (match.name, match_strength))
            print("            a* %+.2f/%.2f -> %+.2f/%.2f   b* %+.2f/%.2f -> %+.2f/%.2f  "
                  "(mean/sd; L* untouched)"
                  % (sa[0], sa[1], ra[0], ra[1], sb[0], sb[1], rb[0], rb[1]))
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
    ap.add_argument("--match", type=pathlib.Path, default=None,
                    help="another master whose TINT the crops should take. Matches the mean and "
                         "spread of the two CIELAB chroma channels and leaves L* alone, so the "
                         "engraving is untouched and only the colour moves. Use it to keep the "
                         "duties on one board agreeing with each other, which asking a generator "
                         "for a palette does not achieve.")
    ap.add_argument("--match-strength", type=float, default=1.0,
                    help="how far to go, 0 to 1 (default 1.0 = all the way to the reference)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    crop_duty_master(a.input, a.out_dir, a.left_name, a.right_name, a.y, a.quiet,
                     a.match, a.match_strength)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
