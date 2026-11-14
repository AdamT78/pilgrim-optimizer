#!/usr/bin/env python3
"""Take the painted black field off a duty icon or a tithe resource, leaving only the emblem.

    python3 tools/duty_art/knockout_icons.py            # report what it would do
    python3 tools/duty_art/knockout_icons.py --write    # write the cutouts

WHY THIS EXISTS. The icons were drawn light-on-black and filed that way, and on a duty tile that
was right: the tile's frame sat around the square and the black never showed as black, it showed
as the tile. Drawn on open landscape with no frame, each icon's own painted field becomes the
shape you see -- and the fourteen fields are all different, a shield here, a jagged burst there,
a pennant on Taxation. The row ends up with no common silhouette, which reads as fourteen
accidents rather than one set.

WHAT IT DOES, AND WHY IT IS A THRESHOLD AND NOT A JUDGEMENT. Measured across the tree the field
sits at luminance 10-13 and the emblem at 220-250, so the alpha is a straight ramp between LO and
HI and nothing is decided by taste.

THERE ARE THREE POPULATIONS, NOT TWO, AND THE FIRST RAMP ONLY KNEW ABOUT TWO. Painted ON the
black field is a scratch texture -- the diagonal strokes -- and it sits at luminance 90-130, in
what the original note called "almost nothing in between". At a ramp of 30 to 180 those strokes
came through at roughly half alpha, and half-alpha cream over a dark plate is a grey streak lying
beside the emblem. ON A DARK BOARD THAT LOOKS LIKE A BACKGROUND THAT WAS NEVER REMOVED, which is
how it was read and reported; over white, where nothing can hide, the field was plainly gone and
only the strokes were left. The ramp now starts ABOVE the strokes.

AND NOT ON COLOUR, WHICH IS THE OBVIOUS THING TO TRY. "Keep only the yellowish pixels" was tested
against this and is worse: inside a near-black field the hue is numerically meaningless, so
selecting on saturation brings the whole field back as speckle. The strokes are not a different
colour from the emblem. They are a different brightness.

THE COLOUR IS SET FLAT, which is the part that is easy to get wrong. Keeping each pixel's own RGB
and only changing its alpha leaves every soft edge carrying the dark it was blended against, so
the emblem comes out with a grey fringe that shows against anything lighter than the field it came
from. The emblem is one cream throughout -- CREAM below, measured off the artwork -- so painting
that flat and varying only alpha gives a clean edge at any size, over anything.

THE THREE TREES REACH THE BOARD DIFFERENTLY, and the difference matters before you run it.

The fourteen DUTY cutouts ARE wired now, and were not when this was first written. They are
written to `cutouts/` beside `icons/`, and the board draws a mark from the LAST folder in
attribution.json's `markFolders` that has one -- which was `icons` and is now `cutouts`, added to
the end of that list in 4553e63. So this half used to change no pixel the board shows and now
changes fourteen of them: a run with --write is live for the duties too, once the board is
rebuilt.

The three CONTROL cutouts ARE wired, immediately. A control is chosen by version rather than by
folder -- bundled_controls() takes the highest vNN -- so there is nowhere to put one where the
board is not already looking, and filing it IS the switch. Run this with --write and the next
build draws the new cuts.

THE FOUR TITHE RESOURCES GO THE CONTROLS' WAY, not the duties'. A resource is chosen by version
-- bundled_tithe() takes the highest `resource_<key>_icon_v*` -- so there is no folder to add to
any list and filing the cut IS the switch, exactly as for a control. What it does still need is
an attribution entry: bundled_tithe() skips a file it has no record of, with a note and not an
error, so an unrecorded cut shows up as a tithe frame drawing empty rather than as a failure.

AND IT WILL NOT CUT A CUT, THOUGH NOT BY REFUSING TO LOOK AT ONE. A version-picked tree always
cuts from its DRAWN version -- the newest one that still has a painted field -- and files the
result above whatever is newest, so a ramp change reaches every tree. What stops it climbing is
that the result is compared with the bytes already filed: identical means this ramp has already
been applied to this drawing, and nothing is written.

THAT IS A CORRECTION, AND IT COST THREE ICONS TO FIND. The rule used to be "cut the newest, skip
it if it has no field left", which is right arithmetic for the climb and wrong for everything
else: a tree cut once could never be cut again. When LO and HI moved, the fourteen duty cut-outs
followed -- they are rewritten from `icons/` every run -- and the three controls did not, because
their newest version WAS the old cut-out. They stayed on the board beside the new ones, still
carrying the strokes the new ramp exists to remove, and nothing reported it, because skipping
them was the rule working exactly as written.
"""
import argparse
import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
ART_DIR = BOARD / "duty_actions"
CONTROL_DIR = BOARD / "controls" / "icons"
RESOURCE_DIR = BOARD / "tokens" / "resources" / "icons"
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

# WHERE THE SCRATCH TEXTURE ENDS AND THE EMBLEM BEGINS. LO is the number doing the work: it sits
# above the strokes' 90-130 and below the emblem's 220-250, and the field at 10-13 was never the
# difficulty. A ramp rather than a hard cut is what keeps the antialiasing the artist drew, and
# HI stays 65 above LO so it is still a ramp.
#
# WHERE TO STOP IS MEASURED, NOT EYEBALLED. Walk LO up and the share of part-transparent pixels
# falls from 6.6% to 2.6% between 30 and 120 and then does not move again however far it goes --
# because what is still part-transparent past that point is the emblem's OWN edge, which is the
# one thing that has to survive. 150 sits inside that plateau with room either side rather than
# balanced on its lip; by 175 the emblem starts to thin, which is visible on a wheat stalk and on
# Silver's ring.
#
# THE SAME PAIR FITS BOTH TREES because both were drawn by the same hand: measured separately,
# the four resources carry 55-83% field, a 4-5% stroke band and an emblem whose 5th percentile is
# 220-232, against the duty icons' 62-69%, 4% and 229-231.
LO, HI = 150.0, 215.0

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


def all_controls() -> dict:
    """Every version of each control: control_<key>_icon_vNN -> {key: [(nn, path), ...]}.

    EVERY VERSION, NOT JUST THE NEWEST, which is the correction that let a ramp change reach
    these at all. See cut_by_version for why the newest is the wrong thing to cut FROM.

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
        out.setdefault(m.group(1), []).append((int(m.group(2)), f))
    return {k: sorted(v) for k, v in out.items()}


def all_resources() -> dict:
    """Every version of each tithe resource: resource_<key>_icon_vNN -> {key: [(nn, path), ..]}.

    THE SAME FIELD AND THE SAME ANSWER AS THE CONTROLS. These were drawn by the same hand as the
    fourteen duty icons -- light on a painted black field, scratch texture over it -- and measure
    55-83% near-opaque dark against a cutout's 0%. They were simply not in the tree this walked.

    AND LIKE A CONTROL, THERE IS NOWHERE ELSE TO PUT ONE. bundled_tithe() globs this folder and
    takes the highest version, so a `cutouts/` folder here would be a folder nothing reads. The
    knocked-out cut is the next version and v01 stays beside it, unorphaned.
    """
    out: dict = {}
    if not RESOURCE_DIR.is_dir():
        return out
    for f in sorted(RESOURCE_DIR.glob("resource_*_icon_v*%s" % SUFFIX)):
        m = re.match(r"resource_([a-z]+)_icon_v(\d+)$", f.stem)
        if not m:
            continue
        out.setdefault(m.group(1), []).append((int(m.group(2)), f))
    return {k: sorted(v) for k, v in out.items()}


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


def encoded(im) -> bytes:
    """The exact bytes this script would file, so "is it already current" can be ASKED."""
    buf = io.BytesIO()
    im.save(buf, "WEBP", lossless=LOSSLESS, quality=100, method=6, exact=True)
    return buf.getvalue()


def cut_by_version(found: dict, folder: pathlib.Path, name_fmt: str, rel_fmt: str,
                   rec: dict, write: bool, np) -> None:
    """Cut each drawn source to the next version beside it, for the trees picked by version.

    IT CUTS FROM THE DRAWN ORIGINAL, NOT FROM THE NEWEST, and that distinction is the whole of
    this function. The board reads the highest version, so the first draft of this cut the
    highest version and refused when that turned out to have no field left -- which is correct
    arithmetic for "do not derive v03 from v02 forever" and wrong for everything else. It meant a
    tree that had been cut ONCE could never be cut again: when LO and HI moved, the fourteen duty
    cut-outs followed, because those are rewritten from `icons/` every run, and the three
    controls did not, because their newest version WAS the old cut-out. They sat on the board
    beside the new ones still carrying the scratch strokes the new ramp exists to remove, and
    nothing reported it, because skipping them was the rule working as written.

    SO THE SOURCE IS THE NEWEST VERSION THAT STILL HAS A PAINTED FIELD -- the drawing -- and the
    destination is the newest version of anything plus one. A ramp change now reaches every tree.

    AND THE CLIMB IS STOPPED BY ASKING RATHER THAN BY REFUSING. The cut is encoded and compared
    with the bytes already filed as newest: identical means this ramp has already been applied to
    this drawing and there is nothing to add, so a second run files nothing. That is the property
    the old rule was reaching for -- it just tested a proxy for it, and the proxy was false
    whenever the constants moved.
    """
    if not found:
        print("  %-34s nothing matched under %s -- no such tree, or the naming has moved"
              % ("(none)", folder))
        return
    for key, versions in sorted(found.items()):
        newest_ver, newest_path = versions[-1]
        drawn = [(v, f) for v, f in versions if field_fraction(f) >= HAS_A_FIELD]
        if not drawn:
            print("  %-34s no drawn version left to cut from, skipped" % newest_path.name)
            continue
        _, src = drawn[-1]
        # A CUT NOBODY WROTE DOWN IS NOT A THING TO DERIVE FROM: the cutout would inherit a
        # provenance that does not exist.
        srel = rel_fmt % src.name
        if srel not in rec:
            print("  %-34s no attribution entry, skipped" % src.name)
            continue
        im = knockout(src)
        kept = (np.asarray(im)[:, :, 3] > 8).mean()
        if kept > 0.60:
            print("  %-34s keeps %.0f%% -- that is a field, not an emblem, SKIPPED"
                  % (src.name, 100 * kept))
            continue
        blob = encoded(im)
        if newest_path != src and newest_path.read_bytes() == blob:
            print("  %-34s %s is already this exact cut, nothing to add"
                  % (src.name, newest_path.name))
            continue
        out = folder / ((name_fmt % (key, newest_ver + 1)) + SUFFIX)
        if out.exists():
            print("  %-34s %s already exists, skipped" % (src.name, out.name))
            continue
        if write:
            out.write_bytes(blob)
        print("  %-34s -> %-36s %4d square, emblem keeps %4.1f%%%s"
              % (src.name, out.name, im.width, 100 * kept, "" if write else "   (dry run)"))


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

    # THE TREES CHOSEN BY VERSION RATHER THAN BY FOLDER. The duties above write into a cutouts/
    # folder of their own; these write the NEXT VERSION of a file the board already reads, so
    # this part of the run is live the moment it is filed.
    #
    # ONE LOOP FOR BOTH, because they differ in a folder and a filename and in nothing else. Two
    # copies of these six guards is how the second one quietly stops matching the first.
    cut_by_version(all_controls(), CONTROL_DIR, "control_%s_icon_v%02d",
                   "controls/icons/%s", rec, a.write, np)
    cut_by_version(all_resources(), RESOURCE_DIR, "resource_%s_icon_v%02d",
                   "tokens/resources/icons/%s", rec, a.write, np)

    if not a.write:
        print("\nnothing written; pass --write to file them")
    else:
        print("\nEVERYTHING ABOVE IS LIVE once the board is rebuilt. %r is the last entry in"
              "\nattribution.json's markFolders, so a duty's cutout now outranks its icon; a"
              "\ncontrol and a resource are chosen by highest version, so filing one was the"
              "\nswitch."
              "\n\nRECORD EVERY FILE WRITTEN ABOVE IN attribution.json -- its sha256, and for a"
              "\nnew cut its own entry. bundled_tithe() SKIPS a resource it has no record of,"
              "\nwith a note rather than an error, so the cost of forgetting is a tithe frame"
              "\nthat draws empty and a build that says it succeeded." % OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
