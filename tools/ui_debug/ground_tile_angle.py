#!/usr/bin/env python3
"""Measure a flat ground plate's camera and scale it to the ground target.

WHAT THIS IS FOR. A generated plate rarely lands on the target: the generator picks a camera
per session and holds it, so a batch comes back tight among itself and two or three degrees
from where it was asked to be. Until now the answer was to run another batch. This scales the
plate instead -- a circle on the ground seen from theta projects as an ellipse sin(theta) tall,
so moving a flat plate from one camera to another is a vertical scale and nothing else.

WHAT IT IS NOT FOR. It is exact only for geometry lying ON the ground plane. Anything with
height -- a plinth, a wall, a standing stone, a chunky rubble kerb seen from the side -- has a
visible face whose height does not foreshorten the same way, so a large correction makes those
faces wrong while the outline reads right. Measured on mosaic_compass, a 6% correction is
invisible. There is no measured figure for where it stops being invisible, so the rule is to
look at the check image rather than to trust a threshold that has not been established.

AND IT CANNOT RECOVER A CAMERA FROM A RAGGED OUTLINE. Every reading below assumes the plate's
un-foreshortened shape is a circle; a patch of rubble that simply stops is not one, and the
instruments disagree accordingly. On mosaic_compass they spanned 1.60 degrees against a window
0.96 wide. That is not three bugs, it is three answers to a question the picture does not
contain. The tool prints all of them and the spread, because the number it then uses is a
CHOICE and should look like one.

SO WHY IS THE DEFAULT DEFENSIBLE. Not because `repo` is true -- because it is repeatable, and
a set measured the same way agrees with itself. Across the six plates on file the repo fit
spans 1.36 degrees and the ink bounding box spans 3.55, so the fit is 2.6x the more consistent
instrument on real art. Switching instruments between plates is the one thing that would undo
that, which is why the default is not a parameter anyone should be tempted to vary per tile.

Measured 2026-09-26 and the reason to believe any of it: the painted sculpts' own base discs
are CLEAN circles, so ground_ellipse reads them exactly -- 31.26 to 31.80 across the set,
sitting on the ground target arrived at from entirely separate art. Correcting mosaic_compass
by the repo fit took it from 2.26 degrees of disagreement with the figure it stands under to
0.01. That is the only corroboration in this whole area that is not circular, because the
sculpt base is the one ellipse here that is genuinely an ellipse.

Used from the shell:

    python3 tools/ui_debug/ground_tile_angle.py <tile.png> --check
    python3 tools/ui_debug/ground_tile_angle.py <tile.png> --method bbox
    python3 tools/ui_debug/ground_tile_angle.py <tile.png> --angle 33.82   # assert it yourself

or imported -- `readings()` and `correct_to_target()` are the whole of it, and neither touches
the filesystem.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

# ONE PLACE. GROUND_TARGET_DEGREES in generate_asset_check.py is the same number and is the
# window's own copy; this reads it from there rather than restating it, so the two cannot drift
# apart the way a second literal always eventually does.
HERE = pathlib.Path(__file__).resolve().parent
ALPHA = 8                    # a pixel is ink above this. 0 counts the invisible fringe a ring
                             # strip leaves behind, which inflates a bbox by 7% with no warning
MAX_TILT_DEG = 2.0           # above this a vertical scale is the wrong correction -- see below


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def target_degrees():
    """The window's target, read from the module that owns it."""
    return _load(HERE / "generate_asset_check.py", "generate_asset_check").GROUND_TARGET_DEGREES


def deg(ratio):
    return math.degrees(math.asin(min(1.0, max(0.0, ratio))))


def ink_box(im):
    a = np.array(im)[..., 3]
    ys, xs = np.nonzero(a > ALPHA)
    if not len(xs):
        raise ValueError("the image is entirely transparent")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


# ---- the instruments -------------------------------------------------------------------------

def read_bbox(im):
    """The ink's bounding box. The crudest reading and the only one that cannot fail."""
    x0, y0, x1, y1 = ink_box(im)
    w, h = x1 - x0, y1 - y0
    return {"ratio": h / w, "major": float(w), "minor": float(h),
            "cx": (x0 + x1) / 2.0, "cy": (y0 + y1) / 2.0}


def read_repo(im, metrics_path=None):
    """The repo's own ground_ellipse -- THE DEFAULT, and the instrument every filed plate was
    measured with.

    Imported rather than reimplemented. A second copy would agree today and drift the first time
    a threshold moved, and both halves would look correct alone.

    A READER RAISES, IT DOES NOT EXIT. An earlier version raised SystemExit here, which derives
    from BaseException rather than Exception and so slid straight past the `except Exception`
    that wraps the reader loop -- the whole tool died outside the repo even when the chosen
    method did not need this file at all. Deciding to stop is main()'s job.
    """
    p = pathlib.Path(metrics_path or (HERE / "sculpt_metrics.py"))
    if not p.is_file():
        raise FileNotFoundError("no sculpt_metrics.py at %s (pass --metrics)" % p)
    sm = _load(p, "sculpt_metrics")
    g = sm.ground_ellipse(im, base_band=False)
    if not g:
        raise RuntimeError("ground_ellipse could not read this plate")
    ox, oy = sm.bbox(im)[:2]
    # ground_ellipse measures a CROPPED copy and reports in crop coordinates. A caller drawing
    # the result on the full canvas gets it wrong by however wide the transparent margin was --
    # and on a roughly centred plate it lands ALMOST right, which is the kind of wrong that
    # survives a look.
    return {"ratio": g["sin_theta"], "major": float(g["width"]), "minor": float(g["minor"]),
            "cx": ox + (g["left"] + g["right"]) / 2.0,
            "cy": oy + g["bottom_centre"] - g["minor"] / 2.0}


def read_contour(im):
    """cv2.fitEllipse over the silhouette. DIAGNOSTIC, and refused for correction when tilted.

    THE TILT DOES NOT SPOIL THE RATIO -- IT SPOILS THE CORRECTION, and it took a measurement to
    get that the right way round. minor/major is the ratio of the ellipse's own axes and is
    invariant to how it sits: on a true ellipse rendered at 34 degrees it returns 33.92 at every
    tilt from 0 to 10. The "vertical extent over width" reading that looks like the more physical
    quantity is the one that drifts, to 34.24 at 5 degrees and 35.19 at 10 (measured 2026-09-26).

    What a tilt breaks is the fix. Everything here scales VERTICALLY, which is the right
    projection only for a level ellipse; a plate rotated in the image plane needs straightening
    first, and scaling it vertically shears the art instead. On a silhouette that is not an
    ellipse at all the tilt is the fit wobbling, which is its own reason not to steer by it.
    """
    import cv2
    a = np.array(im)[..., 3]
    cnts, _ = cv2.findContours(((a > ALPHA) * 255).astype(np.uint8),
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        raise RuntimeError("no silhouette to fit")
    (cx, cy), (a1, a2), rot = cv2.fitEllipse(max(cnts, key=cv2.contourArea))
    major, minor = max(a1, a2), min(a1, a2)
    off = abs(rot - 90.0)
    if off > 90:
        off = abs(off - 180.0)
    return {"ratio": minor / major, "major": major, "minor": minor,
            "cx": cx, "cy": cy, "tilt_deg": off}


READERS = {"repo": read_repo, "bbox": read_bbox, "contour": read_contour}
DEFAULT_METHOD = "repo"


def readings(im, metrics_path=None):
    """Every instrument that can read this plate, keyed by name. One that cannot is left out
    rather than raising, so a caller gets what is available and decides for itself."""
    out = {}
    for name in sorted(READERS):
        try:
            out[name] = (read_repo(im, metrics_path) if name == "repo" else READERS[name](im))
        except Exception:                                             # noqa: BLE001, S110
            pass
    return out


# ---- the correction --------------------------------------------------------------------------

def correct_to_target(im, current_ratio, target_ratio):
    """The plate scaled vertically from `current_ratio` to `target_ratio`. The whole method.

    THE CANVAS GROWS. Scaling into the same one silently cuts the art off whenever the scale is
    above 1, and the loss is invisible until you go looking for it -- tested with the ink pushed
    against the top edge, a x1.41 stretch kept 1031 rows where 1207 were wanted and lost the
    difference off the top with nothing said. Four rows of margin, not two: at full stretch the
    grown canvas is exactly the size of its content, so the outermost row lands ON the edge and
    a later crop has to guess about it.

    ALPHA IS PREMULTIPLIED before resampling and divided out after. Interpolating colour and
    alpha separately mixes the colour of fully transparent pixels into the edge, which is a dark
    halo you cannot see until the plate is over something pale.
    """
    scale = target_ratio / current_ratio
    a = np.array(im.convert("RGBA"), dtype=np.float32) / 255.0
    h = a.shape[0]
    alpha = a[:, :, 3:4]
    pm = a[:, :, :3] * alpha
    grown = max(h, int(math.ceil(h * scale)) + 4)
    ys = (np.arange(grown, dtype=np.float32) - (grown - 1) / 2.0) / scale + (h - 1) / 2.0

    def rows(plane):
        y0 = np.floor(ys).astype(np.int32)
        frac = (ys - y0).astype(np.float32)[:, None, None]
        lo = np.clip(y0, 0, h - 1)
        hi = np.clip(y0 + 1, 0, h - 1)
        inside = ((ys >= -1.0) & (ys <= h))[:, None, None]
        return np.where(inside, plane[lo] * (1.0 - frac) + plane[hi] * frac, 0.0)

    out_a = np.clip(rows(alpha), 0.0, 1.0)
    rgb = np.where(out_a > 1e-6, rows(pm) / np.maximum(out_a, 1e-6), 0.0)
    out = np.clip(np.dstack([rgb, out_a]), 0.0, 1.0)
    return Image.fromarray(np.round(out * 255).astype(np.uint8), "RGBA")


def crop_to_ink(im):
    """What gets filed. Every plate in grounds/ is cropped to its own ink."""
    return im.crop(ink_box(im))


def with_target_ring(im, target_ratio, supersample=4):
    """The plate with the target ellipse drawn over it. THIS IS THE ONLY CHECK THAT CAN FAIL.

    Re-measuring the result proves nothing: scale by target/current and the reading comes back
    as the target whatever `current` was, including badly wrong. Looking at whether the plate's
    front rim sits on this line asks a different question, and one the arithmetic cannot answer
    for itself.

    A SYMMETRIC ANNULUS, NOT A STROKED ELLIPSE. PIL's `ellipse(..., width=w)` strokes INWARD
    from the box, so the drawn centreline comes out w smaller on both axes -- and subtracting
    the same w from a major and a minor lowers the ratio. The first version of this asked for
    31.545 and drew 31.294, measured 2026-09-26: 0.251 degrees low, over half the tolerance, in
    the one thing here that is meant to be trustworthy. Two filled ellipses around a known
    centreline cannot drift that way; this now draws 31.531, the residual being one rounded
    pixel on a 672 px axis.

    THE MASK IS SUPERSAMPLED, NOT THE RGBA. Downsampling colour-with-alpha mixes the colour of
    fully transparent pixels into the edge -- the same halo premultiplication exists to avoid.
    A single-channel coverage mask has no colour to contaminate.
    """
    x0, y0, x1, y1 = ink_box(im)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    major = float(x1 - x0)
    minor = major * target_ratio
    lw = max(3.0, major * 0.008)
    s = supersample
    mask = Image.new("L", (im.width * s, im.height * s), 0)
    d = ImageDraw.Draw(mask)
    for sign, fill in ((+1.0, 255), (-1.0, 0)):
        mj, mn = (major + sign * lw) * s, (minor + sign * lw) * s
        d.ellipse([cx * s - mj / 2, cy * s - mn / 2, cx * s + mj / 2, cy * s + mn / 2], fill=fill)
    layer = Image.new("RGBA", im.size, (0, 255, 128, 0))
    layer.putalpha(mask.resize(im.size, Image.LANCZOS))
    return Image.alpha_composite(im.convert("RGBA"), layer)


# ---- the shell -------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Scale a flat ground plate to the ground target.")
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--check", action="store_true",
                    help="also write <output>_check.png with the target ellipse over it")
    ap.add_argument("--method", choices=sorted(READERS), default=DEFAULT_METHOD)
    ap.add_argument("--angle", type=float,
                    help="skip measurement and assert the plate is at this angle")
    ap.add_argument("--target", type=float, default=None)
    ap.add_argument("--crop", action="store_true",
                    help="crop the result to its ink, the way a filed plate is stored")
    ap.add_argument("--metrics", default=None)
    args = ap.parse_args(argv)

    im = Image.open(args.input).convert("RGBA")
    want_deg = args.target if args.target is not None else target_degrees()
    target = math.sin(math.radians(want_deg))

    print("readings for %s" % args.input)
    got = {}
    for name in sorted(READERS):
        try:
            got[name] = (read_repo(im, args.metrics) if name == "repo" else READERS[name](im))
        except Exception as exc:                                      # noqa: BLE001
            # Fatal ONLY if this is the reader being used. A diagnostic that cannot run must
            # not be able to stop a run that does not need it.
            if args.angle is None and name == args.method:
                raise SystemExit("the chosen method %r failed: %s" % (name, exc)) from None
            print("  %-8s unavailable (%s)" % (name, exc))
    for name, r in got.items():
        mark = " <- used" if (name == args.method and args.angle is None) else ""
        tilt = ("  [fit sits %.2f deg off level]" % r["tilt_deg"]) if "tilt_deg" in r else ""
        print("  %-8s %7.1f x %6.1f  ratio %.6f  %6.2f deg%s%s"
              % (name, r["major"], r["minor"], r["ratio"], deg(r["ratio"]), mark, tilt))
    if got:
        seen = [deg(r["ratio"]) for r in got.values()]
        spread = max(seen) - min(seen)
        print("  spread %.2f deg%s"
              % (spread, "   <-- not an ellipse; the number below is a choice"
                 if spread > 1.0 else ""))

    if args.angle is not None:
        current = math.sin(math.radians(args.angle))
        print("  asserted %.3f deg (measurement ignored)" % args.angle)
    else:
        chosen = got[args.method]
        tilt = chosen.get("tilt_deg")
        if tilt is not None and tilt > MAX_TILT_DEG:
            raise SystemExit(
                "the %s fit sits %.2f deg off level (limit %.1f), so a vertical scale is the "
                "wrong correction for it -- straighten the plate, choose another method, or "
                "assert the angle with --angle" % (args.method, tilt, MAX_TILT_DEG))
        if tilt is not None and tilt > 0.5:
            print("  note: the %s fit sits %.2f deg off level" % (args.method, tilt))
        current = chosen["ratio"]

    out = correct_to_target(im, current, target)
    if args.crop:
        out = crop_to_ink(out)
    print("  target %.3f deg -> vertical scale x%.6f" % (want_deg, target / current))

    path = pathlib.Path(args.output or
                        (pathlib.Path(args.input).stem + "_at%.3f.png" % want_deg))
    out.save(path)
    print("  wrote %s  (%d x %d)" % (path, out.width, out.height))
    if args.check:
        chk = path.with_name(path.stem + "_check.png")
        with_target_ring(out, target).save(chk)
        print("  wrote %s -- LOOK AT IT: the front rim should sit on the green line" % chk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
