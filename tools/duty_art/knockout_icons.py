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

THE TWO HALVES REACH THE BOARD DIFFERENTLY, and the difference matters before you run it.

The fourteen DUTY cutouts are NOT WIRED. They are written to `cutouts/` beside `icons/`, and
attribution.json's `markFolders` lists `seals` and `icons` only -- so the board goes on drawing
what it draws until `cutouts` is added to that list, last, which is what the ordering in
markFolders is for. That half changes no pixel the board shows.

The three CONTROL cutouts ARE wired, immediately. A control is chosen by version rather than by
folder -- bundled_controls() takes the highest vNN -- so there is nowhere to put one where the
board is not already looking, and filing it IS the switch. Run this with --write and the next
build draws the new cuts.

AND IT WILL NOT CUT A CUT. Because the controls' newest version becomes the cutout, a second run
would otherwise derive v03 from v02 and keep climbing. Each source is measured first and skipped
when it has no painted field left to remove, which is the property that actually matters rather
than a filename convention -- see HAS_A_FIELD below.
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
ART_DIR = BOARD / "duty_actions"
CONTROL_DIR = BOARD / "controls" / "icons"
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

# WHAT "STILL HAS A FIELD" MEANS, measured rather than named. A drawn icon is 51-61% near-opaque
# dark; a cutout is 0.0%, because every visible pixel of one is the flat cream and everything else
# is clear. There is no middle, so any small number separates them and 2% is slack, not a judgement.
#
# WHY NOT TEST THE FILENAME. A control's cutout is `control_map_icon_v02`, which is spelt exactly
# like a second drawn cut -- the version is the only thing that moves, deliberately, because that
# is how the board picks one. So the name cannot answer this and the pixels can.
HAS_A_FIELD = 0.02


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


def newest_controls() -> dict:
    """The three controls, by the board's own rule: control_<key>_icon_vNN, highest NN wins.

    THE SAME FIELD, THE SAME PROBLEM, A DIFFERENT FOLDER. The three controls were drawn by the
    same hand and in the same way as the fourteen duty icons -- light on a painted black field --
    and measured, they carry 51-61% near-opaque dark against the cutouts' 0%. So they had exactly
    the fault this script exists for and were simply not in the tree it walked.

    AND THEY NEED NO cutouts/ FOLDER, which is the one real difference. A duty mark is chosen by
    attribution.json's markFolders list, so a cutout had to go somewhere the board was not yet
    looking and be switched on by adding a folder name to the end of that list. A control is
    chosen by VERSION -- bundled_controls() takes the highest vNN -- so the knocked-out cut is
    just the next version, and filing it IS the switch. v01 stays beside it, unorphaned.
    """
    out: dict = {}
    if not CONTROL_DIR.is_dir():
        return out
    for f in sorted(CONTROL_DIR.glob("control_*_icon_v*%s" % SUFFIX)):
        m = re.match(r"control_([a-z]+)_icon_v(\d+)$", f.stem)
        if not m:
            continue
        key, v = m.group(1), int(m.group(2))
        if key not in out or v > out[key][0]:
            out[key] = (v, f)
    return {k: v for k, v in out.items()}


def field_fraction(path: pathlib.Path) -> float:
    """How much of this square is painted field: near-opaque, and not the emblem's cream."""
    from PIL import Image
    import numpy as np

    a = np.asarray(Image.open(path).convert("RGBA")).astype(int)
    alpha, rgb = a[:, :, 3], a[:, :, :3]
    return float(((alpha > 200) & (rgb.mean(axis=2) <= 140)).mean())


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

    # THE CONTROLS, BY VERSION RATHER THAN BY FOLDER. Everything above this line writes into a
    # cutouts/ folder the board does not read until it is told to; these write the next version
    # of a file the board already reads, so this half of the run is live the moment it is filed.
    for key, (ver, src) in sorted(newest_controls().items()):
        srel = "controls/icons/%s" % src.name
        if srel not in rec:
            print("  %-34s no attribution entry, skipped" % src.name)
            continue
        field = field_fraction(src)
        if field < HAS_A_FIELD:
            print("  %-34s already a cutout (%.1f%% field), nothing to take off"
                  % (src.name, 100 * field))
            continue
        im = knockout(src)
        kept = (np.asarray(im)[:, :, 3] > 8).mean()
        if kept > 0.60:
            print("  %-34s keeps %.0f%% -- that is a field, not an emblem, SKIPPED"
                  % (src.name, 100 * kept))
            continue
        out = CONTROL_DIR / ("control_%s_icon_v%02d%s" % (key, ver + 1, SUFFIX))
        if out.exists():
            print("  %-34s %s already exists, skipped" % (src.name, out.name))
            continue
        if a.write:
            im.save(out, "WEBP", lossless=LOSSLESS, quality=100, method=6, exact=True)
        print("  %-34s -> %-36s %4d square, emblem keeps %4.1f%%%s"
              % (src.name, out.name, im.width, 100 * kept, "" if a.write else "   (dry run)"))

    if not a.write:
        print("\nnothing written; pass --write to file them")
    else:
        print("\nduty cutouts filed under */%s/, which the board does NOT read:"
              "\nattribution.json's markFolders is the list, and adding %r to the END of it is"
              "\nwhat would switch the board over."
              "\n\nany control cutout above is LIVE -- a control is chosen by highest version, so"
              "\nfiling it was the switch. Record its sha256 in attribution.json and rebuild."
              % (OUT_DIR, OUT_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
