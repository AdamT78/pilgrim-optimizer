"""Judge a freshly generated sculpt before it is filed, and show the working.

    python3 tools/ui_debug/check_sculpt.py ~/Downloads/player_2_new.png

Prints what the base measures, compares it with the set already in ui/concept/, and writes an
overlay PNG with the measured lines drawn on the art so the numbers can be checked rather than
believed. --sizes also renders the piece down to the sizes the board uses, with the edge check
that catches a pale rim.

WHY THE OVERLAY IS NOT OPTIONAL

Measuring the wall took three wrong methods before a right one, and two of the wrong ones
produced confident numbers. A measurement of a picture is only worth the picture that shows
where it landed, so every run writes one. Look at it.

WHAT IS COMPARED AGAINST WHAT

By default the reference is the committed set, ui/concept/player_*/sculpt_plastic.png, so the
bar moves as the set improves rather than being a number frozen in this file. Its spread is
printed alongside the candidate; a property outside the reference range is flagged, and so is
one outside --tol of the reference median. Pass --target-wall / --target-rise to check against a
spec you are converging on instead of against where the set happens to be.

Ratios, never raw pixels: everything is divided by the base's own width, so a figure that came
back larger or smaller than its siblings still compares directly.
"""
import argparse
import glob
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import sculpt_metrics as sm                                          # noqa: E402

REFERENCE = "ui/concept/player_*/sculpt_plastic.png"
BOARD_SIZES = (90, 120, 150)
TOL = 0.10                      # fraction of the reference median a property may stray
RIM_LIMIT = 6.0                 # luminance; above this the rim is being invented, not drawn

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("images", nargs="+", help="the candidate PNG(s)")
ap.add_argument("--reference", default=REFERENCE,
                help="glob for the set to compare against (default: %(default)s)")
ap.add_argument("--sizes", default="",
                help="also render down to these heights, e.g. 90,120,150 (default: none)")
ap.add_argument("--out", default=None,
                help="where to write overlays and renders (default: beside each image)")
ap.add_argument("--target-wall", type=float, default=None, help="wall / base width to aim at")
ap.add_argument("--target-rise", type=float, default=None, help="rise / base width to aim at")
ap.add_argument("--tol", type=float, default=TOL, help="allowed stray, as a fraction")
ap.add_argument("--strict", action="store_true", help="exit non-zero if anything is flagged")
args = ap.parse_args()


def load(p):
    return sm.crop_to_art(Image.open(p).convert("RGBA"))


refs = []
for p in sorted(glob.glob(str(ROOT / args.reference))):
    try:
        refs.append((pathlib.Path(p).parent.name, sm.measure(load(p))))
    except Exception as e:                                            # noqa: BLE001
        print("  skipped reference %s: %s" % (p, e))

if refs:
    print("reference set (%s)" % args.reference)
    print("  %-12s %-8s %-7s %-7s %-9s %-9s %s"
          % ("", "plinth", "wall", "rise", "wall/w", "rise/w", "h/plinth"))
    for name, m in refs:
        print("  %-12s %-8d %-7d %-7d %-9.3f %-9.3f %.3f"
              % (name, m["plinth"], m["wall"], m["rise"], m["wall_ratio"], m["rise_ratio"],
                 m["h_plinth"]))
else:
    print("no reference images matched %s -- candidates will be reported without comparison"
          % args.reference)


def band(key):
    vals = [m[key] for _, m in refs]
    return (min(vals), float(np.median(vals)), max(vals)) if vals else (None, None, None)


WALL_LO, WALL_MID, WALL_HI = band("wall_ratio")
RISE_LO, RISE_MID, RISE_HI = band("rise_ratio")
if args.target_wall is not None:
    WALL_MID = args.target_wall
if args.target_rise is not None:
    RISE_MID = args.target_rise
if refs:
    print("  %-12s %-8s wall/w %.3f-%.3f (median %.3f)   rise/w %.3f-%.3f (median %.3f)"
          % ("range", "", WALL_LO, WALL_HI, WALL_MID, RISE_LO, RISE_HI, RISE_MID))
print()


def verdict(value, lo, hi, mid, label, is_target):
    """Two separate questions: is it inside the set, and is it near the middle of it.
    Returns the line and whether anything is wrong, so the caller counts once rather than
    re-deriving it from the text."""
    if mid is None:
        return "  %-11s %.3f" % (label, value), False
    off = (value - mid) / mid
    marks = []
    if lo is not None and not (lo <= value <= hi):
        marks.append("outside the set's %.3f-%.3f" % (lo, hi))
    if abs(off) > args.tol:
        marks.append("%+.0f%% off the %s %.3f"
                     % (100 * off, "target" if is_target else "median", mid))
    return ("  %-11s %.3f%s" % (label, value, "  <-- " + "; ".join(marks) if marks else "  ok"),
            bool(marks))


flagged = 0
for path in args.images:
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        print("%s: not found" % p)
        flagged += 1
        continue
    full = Image.open(p).convert("RGBA")
    art = sm.crop_to_art(full)
    m = sm.measure(art)
    out_dir = pathlib.Path(args.out).expanduser() if args.out else p.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    l, t, r, b = sm.bbox(full)
    print("%s" % p.name)
    print("  canvas %d x %d   art %d x %d   gaps L%d T%d R%d B%d"
          % (full.width, full.height, m["art_w"], m["art_h"],
             l, t, full.width - r, full.height - b))
    print("  plinth %d px   wall %d px   rise %d px   h/plinth %.3f   ripple %.2f"
          % (m["plinth"], m["wall"], m["rise"], m["h_plinth"], m["ripple"]))
    line, bad = verdict(m["wall_ratio"], WALL_LO, WALL_HI, WALL_MID, "wall / w",
                        args.target_wall is not None)
    print(line)
    flagged += bad
    line, bad = verdict(m["rise_ratio"], RISE_LO, RISE_HI, RISE_MID, "rise / w",
                        args.target_rise is not None)
    print(line)
    flagged += bad
    # Measured on the FULL canvas, not the cropped art: a background is a property of what is
    # around the figure, and cropping to the figure is exactly what throws that away.
    fa = np.array(full)[..., 3]
    corners = [int(fa[2, 2]), int(fa[2, -3]), int(fa[-3, 2]), int(fa[-3, -3])]
    clear = 100.0 * float((fa == 0).mean())
    if max(corners) > sm.ALPHA:
        print("  <-- corners are not transparent (alpha %s): this still has a background"
              % corners)
        flagged += 1
    elif clear < 5.0:
        print("  <-- corners are clear but only %.0f%% of the canvas is: check for a partial "
              "backdrop" % clear)
        flagged += 1
    else:
        print("  background   clean, %.0f%% of the canvas is fully transparent" % clear)

    # the overlay: red = top of wall, blue = widest row, green = the target wall if one is set
    ov = Image.new("RGB", (art.width, min(art.height, 260)), (0x2b, 0x2f, 0x38))
    ov.paste(art.crop((0, art.height - ov.height, art.width, art.height)), (0, 0),
             art.crop((0, art.height - ov.height, art.width, art.height)))
    d = ImageDraw.Draw(ov)
    d.line([(0, ov.height - 1 - m["wall"]), (ov.width, ov.height - 1 - m["wall"])],
           fill=(0xff, 0x40, 0x30), width=2)
    d.line([(0, ov.height - 1 - m["rise"]), (ov.width, ov.height - 1 - m["rise"])],
           fill=(0x50, 0xa0, 0xff), width=1)
    if WALL_MID:
        y = ov.height - 1 - round(WALL_MID * m["plinth"])
        d.line([(0, y), (ov.width, y)], fill=(0x40, 0xff, 0x90), width=1)
    ovp = out_dir / (p.stem + "_measured.png")
    ov.save(ovp)
    print("  overlay      %s   (red top of wall, blue widest row, green where the wall should be)"
          % ovp)

    sizes = [int(s) for s in args.sizes.replace(",", " ").split()] if args.sizes else []
    for px in sizes:
        small = sm.down(art, round(art.width * px / art.height), px, "%s at %d" % (p.name, px))
        g = sm.fringe(small)
        f = out_dir / ("%s_%d.png" % (p.stem, px))
        small.save(f)
        note = "  <-- pale rim, %+.1f" % g if g > RIM_LIMIT else ""
        print("  %3d px       %d x %d, rim %+.1f%s   %s"
              % (px, small.width, small.height, g, note, f.name))
        if g > RIM_LIMIT:
            flagged += 1
    print()

print("%d thing(s) flagged. Look at the overlay before trusting any of this." % flagged
      if flagged else "nothing flagged. Look at the overlay anyway.")
if flagged and args.strict:
    raise SystemExit(1)
