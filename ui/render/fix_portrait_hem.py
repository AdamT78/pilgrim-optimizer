"""Close the hem of a portrait that fades out inside the board's oval.

    python3 ui/render/fix_portrait_hem.py --check      # report, write nothing
    python3 ui/render/fix_portrait_hem.py              # fix every portrait that needs it

WHAT GOES WRONG

Two of the portraits -- both hooded ones -- end in an alpha ramp rather than an edge: their bottom
sixth fades to nothing. On a white page that is invisible, which is presumably where they were
judged. On a player board the oval behind the head is the SEAT'S COLOUR, so the fade does not end in
white, it ends in sage, or pewter, or ash. What you see is a pale crescent creeping up into the
robe from the bottom of the oval, and it reads as a rendering fault rather than as artwork.

    leader_male_hooded     opaque pixels per row collapse from 309 to 2 between rows 543 and 575
    leader_female_hooded   the same, from 333 to 22

WHY THE FIX IS TO THE ASSET AND NOT TO THE BOARD

The obvious repair -- move the image down, or scale it up, so the ramp falls outside the oval -- is
the one thing this repository does not do: the portrait's placement is registration, shared by every
portrait, and nudging it for one file breaks the other four. So the board's numbers are read, not
written. This fills the hem INSIDE the portrait, and any portrait that already has a solid hem comes
out byte-identical.

HOW

The fade still carries colour; only the alpha is ramped away. So the robe does not have to be
invented, only continued: each column takes the median of its last forty opaque rows, that colour is
carried down, darkened as it descends the way a hem in shadow would be, and the original portrait is
composited back on top so every fold and highlight it still has survives. The fill's own alpha ramps
in from zero well above the damage, so nothing in the picture gains an edge that was not there.

The fill is shaped to the oval, grown past it, because the board clips to the oval anyway: a fill
that stopped exactly on the boundary would be eroded by its own feathering and leave the rim
translucent, which is the original bug in miniature.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets-gothic"
TEMPLATE = ASSETS / "template" / "player_board_template.svg"
PORTRAITS = ASSETS / "portraits"

# Where the fill starts to appear and where it is solid, as a fraction of the portrait's height.
# Both sit above the earliest damage in either file and below anything either of them draws, so one
# pair of numbers serves every portrait rather than becoming a table keyed by filename.
RAMP_TOP, SOLID_FROM = 0.711, 0.820
DARKEN = 0.28          # how much the carried-down robe loses by the bottom of the frame
GROW = 26.0            # board px the fill extends past the oval, so its feather clears the rim
FEATHER = 8            # px of blur on the fill's alpha


def board_geometry():
    """The portrait's placement and clip, read off the template.

    Read rather than repeated: these four numbers are registration shared by every portrait, and a
    second copy of them here is a second thing to update when the board moves.
    """
    svg = TEMPLATE.read_text(encoding="utf-8")
    clip = re.search(r'<clipPath id="portraitClip"><ellipse\s+cx="([\d.]+)"\s+cy="([\d.]+)"'
                     r'\s+rx="([\d.]+)"\s+ry="([\d.]+)"', svg)
    image = re.search(r'<image data-asset-role="portrait"[^>]*?\sx="([\d.]+)"\s+y="([\d.]+)"'
                      r'\s+width="([\d.]+)"', svg)
    if not clip or not image:
        raise SystemExit(
            "could not find the portrait's clip ellipse and <image> placement in %s.\n"
            "This script reads the board's own numbers rather than keeping a copy; if the template "
            "was reshaped, update the two patterns here to match." % TEMPLATE)
    cx, cy, rx, ry = (float(v) for v in clip.groups())
    x, y, w = (float(v) for v in image.groups())
    return dict(cx=cx, cy=cy, rx=rx, ry=ry, x=x, y=y, w=w)


def oval_alpha(size, geo, grow=0.0):
    """The clip oval, in the portrait's own pixels."""
    scale = size / geo["w"]                       # source px per board px
    ys, xs = np.mgrid[0:size, 0:size]
    bx = geo["x"] + xs / scale
    by = geo["y"] + ys / scale
    inside = ((bx - geo["cx"]) / (geo["rx"] + grow)) ** 2 \
        + ((by - geo["cy"]) / (geo["ry"] + grow)) ** 2
    return inside <= 1.0


def damage(alpha, oval, size):
    """Thin pixels in the BOTTOM BAND of the oval, which is what a fade looks like and nothing else.

    Getting this band right is the difference between a check and a nuisance. Measuring the whole
    lower oval also catches portraits that are perfectly solid but simply do not reach the oval's
    left and right rim -- leader_male_shaven has 1,214 such pixels, all of them behind the gold ring
    and none of them a fault. Measured in the bottom band instead, the two portraits that fade score
    38%% and 52%% and the three that do not score zero, with nothing in between to draw a line
    through.

    The TOP of the oval is never measured. That is the ground behind the head, it is meant to show
    the seat's colour, and counting it would report every portrait as broken.
    """
    rows = np.mgrid[0:size, 0:size][0]
    band = oval & (rows >= int(size * SOLID_FROM))
    lower = oval & (rows >= int(size * RAMP_TOP))
    return (int((band & (alpha < 250)).sum()),
            int(alpha[band].min()) if band.any() else 255,
            int((lower & (alpha < 250)).sum()))


def fill_hem(path: pathlib.Path, geo) -> tuple[np.ndarray, int, int]:
    a = np.array(Image.open(path).convert("RGBA")).astype(float)
    size = a.shape[0]
    if a.shape[0] != a.shape[1]:
        raise SystemExit("%s is %dx%d; the portraits are square." % (path.name, *a.shape[:2]))
    rgb, alpha = a[:, :, :3], a[:, :, 3]
    oval = oval_alpha(size, geo)
    before = damage(alpha, oval, size)

    solid_row = int(size * SOLID_FROM)
    opaque = alpha >= 250
    base = np.zeros((size, 3))
    have = np.zeros(size, bool)
    for x in range(size):
        rows = np.where(opaque[:solid_row, x])[0]
        if len(rows) >= 8:
            base[x] = np.median(rgb[rows[-40:], x], axis=0)
            have[x] = True
    known = np.where(have)[0]
    if not len(known):
        raise SystemExit("%s has no opaque rows to continue; it is not a portrait this can fix."
                         % path.name)
    for x in np.where(~have)[0]:                  # a column with nothing borrows its nearest neighbour
        base[x] = base[known[np.argmin(np.abs(known - x))]]

    ramp_row = int(size * RAMP_TOP)
    depth = np.clip((np.arange(size) - ramp_row) / max(size - ramp_row, 1), 0, 1)[:, None, None]
    backdrop = np.repeat(base[None, :, :], size, axis=0) * (1 - DARKEN * depth)

    ramp = np.clip((np.arange(size) - ramp_row) / max(solid_row - ramp_row, 1), 0, 1)[:, None] * 255
    back_a = np.repeat(ramp, size, axis=1) * oval_alpha(size, geo, grow=GROW)
    back_a = np.array(Image.fromarray(back_a.astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(FEATHER)), float)
    # The blur reads zeros from beyond the bottom of the image, so near the oval's lowest point it
    # pulls the fill back below opaque -- which left a rim the fix had not fixed, and made a second
    # run find work to do. Inside the band the fill is asserted rather than feathered; the feather
    # is only there to hide the fill's upper edge, and there is no upper edge down here.
    band = oval_alpha(size, geo) & (np.mgrid[0:size, 0:size][0] >= solid_row)
    back_a = np.maximum(back_a, band * 255.0)

    # Source-over: the portrait as it is, onto the continued robe.
    ta = alpha[:, :, None] / 255
    ba = back_a[:, :, None] / 255
    out_a = ta + ba * (1 - ta)
    out_rgb = np.where(out_a > 0, (rgb * ta + backdrop * ba * (1 - ta)) / np.maximum(out_a, 1e-6), 0)
    out = np.dstack([out_rgb, out_a * 255]).clip(0, 255).astype(np.uint8)
    after = damage(out[:, :, 3].astype(float), oval, size)
    return out, before, after


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report and write nothing")
    ap.add_argument("portraits", nargs="*", help="default: every portrait in the assets tree")
    args = ap.parse_args()

    geo = board_geometry()
    paths = [pathlib.Path(p) for p in args.portraits] or sorted(PORTRAITS.glob("*.png"))
    if not paths:
        raise SystemExit("no portraits found in %s" % PORTRAITS)

    print("oval cx %(cx)s cy %(cy)s rx %(rx)s ry %(ry)s, image at x %(x)s y %(y)s w %(w)s"
          % geo)
    changed = 0
    for path in paths:
        out, before, after = fill_hem(path, geo)
        band_before, min_before, lower_before = before
        band_after, min_after, lower_after = after
        if band_before == 0:
            print("  %-32s hem solid (%d thin px higher up, all behind the ring)"
                  % (path.name, lower_before))
            continue
        changed += 1
        print("  %-32s hem %5d thin px (min alpha %3d) -> %4d (min alpha %3d);"
              "  lower oval %5d -> %5d%s"
              % (path.name, band_before, min_before, band_after, min_after,
                 lower_before, lower_after, "" if args.check else "   written"))
        if not args.check:
            Image.fromarray(out, "RGBA").save(path)
    if args.check:
        print("\n%d portrait(s) would be changed. Run without --check to write them." % changed)
        return 1 if changed else 0
    print("\n%d portrait(s) written." % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
