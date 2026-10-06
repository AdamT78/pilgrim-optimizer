#!/usr/bin/env python3
"""Take the painted black field off a duty icon, leaving the emblem on transparency.

    python3 tools/duty_art/knockout_icons.py            # report what it would do
    python3 tools/duty_art/knockout_icons.py --write    # write the cutouts

WHY THIS EXISTS. The icons were drawn light-on-black and filed that way, and on a duty tile that
was right: the tile's frame sat around the square and the black never showed as black, it showed
as the tile. Drawn on open landscape with no frame, each icon's own painted field becomes the
shape you see -- and the fourteen fields are all different, a shield here, a jagged burst there,
a pennant on Taxation. The row ends up with no common silhouette, which reads as fourteen
accidents rather than one set.

WHAT IT DOES, AND WHY IT IS A THRESHOLD AND NOT A JUDGEMENT. Measured across the tree, the field
sits at luminance 10-13 and the emblem at 235-250, with almost nothing in between: the two
populations are 220 apart. So the alpha is a straight ramp between LO and HI, and nothing is being
decided by taste.

THE COLOUR IS SET FLAT, which is the part that is easy to get wrong. Keeping each pixel's own RGB
and only changing its alpha leaves every soft edge carrying the dark it was blended against, so
the emblem comes out with a grey fringe that shows against anything lighter than the field it came
from. The emblem is one cream throughout -- CREAM below, measured off the artwork -- so painting
that flat and varying only alpha gives a clean edge at any size, over anything.

NOT WIRED TO THE BOARD. These are written to `cutouts/` beside `icons/`, and attribution.json's
`markFolders` lists `seals` and `icons` only -- so the board goes on drawing what it draws until
`cutouts` is added to that list, last, which is what the ordering in markFolders is for. Running
this changes no pixel the board shows.
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
ART_DIR = BOARD / "duty_actions"
ATTRIB_FILE = BOARD / "attribution.json"

SRC_DIR = "icons"
OUT_DIR = "cutouts"
SUFFIX = ".webp"

# LOSSLESS, WHICH IS NOT THE TREE'S USUAL CHOICE AND IS THE RIGHT ONE HERE. The shipped prints are
# WebP at quality 90 because they are photographs and paintings, where the eye cannot find the
# difference and the saving is large. A cutout is neither: it is ONE flat colour with a varying
# alpha, which is the exact shape lossy coding is worst at and lossless coding is best at.
#
# MEASURED BOTH WAYS before choosing. Lossy shifted the flat cream by one -- 236 came back 235 --
# so the one property these files have, that every visible pixel is the same colour, was not
# actually true of what was written. And it was BIGGER: 54 KB against 53, 60 against 57, 40
# against 37. There was nothing to trade.
LOSSLESS = True

# THE EMBLEM'S OWN CREAM, averaged over the bright pixels of the tree's icons. One colour for all
# fourteen because they were drawn as one set and measurably are: the spread between them is
# smaller than the spread inside any one of them.
CREAM = (248, 236, 201)

# WHERE THE FIELD ENDS AND THE EMBLEM BEGINS. Wide apart on purpose -- the gap between the two
# populations is 220, so anywhere in the middle gives the same answer, and a ramp rather than a
# hard cut is what keeps the antialiasing the artist drew.
LO, HI = 30.0, 180.0


def newest_icons() -> dict:
    """The icon cut the board would draw for each duty and slot, by the board's own rule.

    HIGHEST VERSION WINS INSIDE ONE LINEAGE, which is the only comparison that means anything --
    attribution.json's markFoldersNote says why a seal's v02 and an icon's v01 are unrelated
    counters. This looks in `icons` alone, so the question does not arise.
    """
    out: dict = {}
    for f in sorted(ART_DIR.glob("*/%s/*%s" % (SRC_DIR, SUFFIX))):
        m = re.match(r"([a-z_]+)_(action[AB])_icon_v(\d+)$", f.stem)
        if not m:
            continue
        key = (m.group(1), m.group(2))
        v = int(m.group(3))
        if key not in out or v > out[key][0]:
            out[key] = (v, f)
    return {k: v[1] for k, v in out.items()}


def knockout(path: pathlib.Path):
    """One icon, with its field taken off. Same pixel dimensions as the cut it came from."""
    from PIL import Image
    import numpy as np

    a = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    alpha = np.clip((lum - LO) / (HI - LO), 0, 1) * (a[:, :, 3] / 255.0)
    out = np.zeros_like(a, dtype=np.uint8)
    out[:, :, 0], out[:, :, 1], out[:, :, 2] = CREAM
    out[:, :, 3] = (alpha * 255).round().astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write the files; otherwise report only")
    a = ap.parse_args()

    if not ART_DIR.is_dir():
        raise SystemExit("there is no %s" % ART_DIR)
    found = newest_icons()
    if not found:
        raise SystemExit("no icon cuts under %s/*/%s" % (ART_DIR, SRC_DIR))

    import numpy as np

    rec = {}
    if ATTRIB_FILE.is_file():
        rec = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})

    for (duty, slot), src in sorted(found.items()):
        # THE RECORD GATES THIS TOO. A cut nobody wrote down is not a thing to derive from: the
        # cutout would inherit a provenance that does not exist.
        srel = "duty_actions/%s" % src.relative_to(ART_DIR).as_posix()
        if srel not in rec:
            print("  %-34s no attribution entry, skipped" % src.name)
            continue
        out = ART_DIR / duty / OUT_DIR / ("%s_%s_cutout_v01%s" % (duty, slot, SUFFIX))
        im = knockout(src)
        kept = (np.asarray(im)[:, :, 3] > 8).mean()
        if a.write:
            out.parent.mkdir(parents=True, exist_ok=True)
            im.save(out, "WEBP", lossless=LOSSLESS, quality=100, method=6, exact=True)
        print("  %-34s -> %-36s %4d square, emblem keeps %4.1f%%%s"
              % (src.name, out.name, im.width, 100 * kept, "" if a.write else "   (dry run)"))

    if not a.write:
        print("\nnothing written; pass --write to file them")
    else:
        print("\nfiled under */%s/. The board does not read that folder: attribution.json's"
              "\nmarkFolders is the list, and adding %r to the END of it is what would switch"
              "\nthe board over." % (OUT_DIR, OUT_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
