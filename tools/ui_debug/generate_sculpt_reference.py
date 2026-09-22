"""The card handed to the image model when a new acolyte sculpt is generated.

    python3 tools/ui_debug/generate_sculpt_reference.py

WHY A PICTURE AND NOT A SENTENCE

A figurine's camera cannot be steered by text. Every photograph of a miniature ever taken is at
eye level, and asking for anything else loses to that prior: sculpts came back at 9 degrees
however the brief was worded. What works is attaching a diagram of the BASE alone, drawn at the
wanted ellipse ratio, with the instruction to keep it exactly as it is. The base pins the camera
and the figure follows the base.

Only the base is drawn. Three attempts at including a schematic FIGURE produced two traffic cones
and a lampshade, any of which an image model might have copied, so the card carries the base, the
empty room above it, and nothing else.

WHY 27 DEGREES WHEN THE TARGET IS 32 -- DO NOT "CORRECT" THIS

The number on this card is deliberately BELOW the target in
`tools/ui_debug/generate_asset_check.py`, and it is not a mistake left behind by a target that
moved. It was set to 27 while the target was 29, to correct a measured +3.1 degree bias. What
then happened is more useful than the arithmetic: the ask turned out not to steer the result at
all. Two batches of ten, with cards drawn to match, landed at 32.1 from a card of 30 and 31.9
from a card of 27 -- three degrees of instruction bought two tenths of a degree. This generator
has an attractor near 32 for a hooded figurine and will not be argued out of it, which is why the
target moved to 32 rather than the card moving to 32.

So: every sculpt in ui/assets-gothic/sculpts/ was generated from a card reading 27, and each one
measures within 2.5 degrees of 32. Redrawing this card at 32 has been measured to change nothing
about the output, while breaking the one property that matters -- that the committed sculpts and
the committed card agree about how they were made.

THE OTHER TWO NUMBERS

The scale line sits at 2.4 x the base width, above the 2.2 actually wanted, because the model
undershoots the scale it is given: a card marked 2.2 produced figures at 2.01. Aiming past a
known undershoot is the correction for it, and the same change fixes a base drawn too wide, since
a wide base IS a low proportion.

The base is drawn dark because the prompt says to keep it exactly as it is, so its tone is
inherited without needing an instruction of its own. Pale bases were the loudest thing on a duty
tile -- four of them merged into a single bright mass with the figures seeming to float above it.
It is dark enough to sit under a pale robe and light enough to read against the card's own
background, which near-black was not.
"""
import argparse
import math
import pathlib

from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "ui" / "assets-gothic" / "references" / "base_scale_reference_27.png"

BG = (17, 16, 14)
INK = (216, 208, 192)
FAINT = (112, 106, 96)
GOLD = (220, 188, 122)
STONE = (104, 99, 90)       # dark enough to sit under a pale robe, light enough to read
SIDE = (64, 61, 55)
THETA = 27.0
PROPORTION = 2.4


def card(theta=THETA, proportion=PROPORTION):
    W, H = 900, 1450
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")
    s = math.sin(math.radians(theta))
    cx, R, wall = W*0.52, 180.0, 24.0
    base_w = 2*R
    top = 300.0
    cy = top + proportion*base_w

    d.ellipse([cx-R, cy-R*s+wall, cx+R, cy+R*s+wall], fill=SIDE)
    d.rectangle([cx-R, cy, cx+R, cy+wall], fill=SIDE)
    d.ellipse([cx-R, cy-R*s, cx+R, cy+R*s], fill=STONE, outline=(140, 134, 124), width=3)
    d.line([(cx-R, cy), (cx-R, cy+wall)], fill=(140, 134, 124), width=3)
    d.line([(cx+R, cy), (cx+R, cy+wall)], fill=(140, 134, 124), width=3)

    xg = cx - R - 86
    d.line([(xg, top), (xg, cy)], fill=GOLD, width=3)
    for y in (top, cy):
        d.line([(xg-13, y), (xg+13, y)], fill=GOLD, width=3)
    d.line([(cx-R, top), (cx+R, top)], fill=GOLD + (110,), width=2)
    d.text((xg-78, (top+cy)/2 - 26), "%.1f x W" % proportion, fill=GOLD)
    d.text((cx-R+8, top+10), "top of the hood reaches this line", fill=GOLD)

    yb = cy + R*s + wall + 40
    d.line([(cx-R, yb), (cx+R, yb)], fill=GOLD, width=3)
    for x in (cx-R, cx+R):
        d.line([(x, yb-11), (x, yb+11)], fill=GOLD, width=3)
    d.text((cx-42, yb+13), "width  W", fill=GOLD)
    xr = cx + R + 70
    d.line([(xr, cy-R*s), (xr, cy+R*s)], fill=GOLD, width=3)
    for y in (cy-R*s, cy+R*s):
        d.line([(xr-11, y), (xr+11, y)], fill=GOLD, width=3)
    d.text((xr+16, cy-9), "%.3f x W" % s, fill=GOLD)

    d.text((46, 40), "BASE AND SCALE  -  CAMERA %d DEGREES ABOVE THE HORIZON" % round(theta),
           fill=INK)
    for i, t in enumerate([
            "The base of the figurine, and the room the figure must fill. The figure itself is",
            "deliberately not drawn -- sculpt it fully, in your own detail.",
            "",
            "Copy three things from this image, and nothing else:",
            "1.  The base's SHAPE. A circle lying flat, seen from %d degrees above, so it draws"
            % round(theta),
            "    an ellipse whose height is %.3f of its width, its whole top face open." % s,
            "2.  The base's TONE. It is dark stone -- darker than the figure standing on it.",
            "3.  The SCALE. The figure's head reaches the marked line: %.1f times the base's"
            % proportion,
            "    width. Do not draw it squatter than that, and do not widen the base.",
    ]):
        d.text((46, 80 + i*23), t, fill=FAINT if i else INK)
    d.text((46, H-40), "If the base reads as a thin sliver, the camera is too low.", fill=GOLD)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="where to write (default: %s)"
                    % OUT.relative_to(ROOT))
    args = ap.parse_args()
    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    card().save(out)
    print("wrote %s" % out)
    print("  camera %.0f deg, ellipse ratio %.3f, scale line %.1f x W"
          % (THETA, math.sin(math.radians(THETA)), PROPORTION))
    print("  27 is deliberate and below the 32 target: see this file's docstring before changing")


if __name__ == "__main__":
    raise SystemExit(main())
