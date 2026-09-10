"""Regenerate everything a seat colour decides, from the red originals.

    python3 ui/render/recolor_seat_layers.py            # write the sixteen derived files
    python3 ui/render/recolor_seat_layers.py --check    # verify the committed files match

WHY THIS IS A SCRIPT AND NOT SIXTEEN OPAQUE FILES

Sixteen recoloured files in a directory tell you what the palette *is* and nothing about how it was
arrived at, so the first person who wants a fifth seat colour -- or who wants plum a shade cooler --
has to reverse-engineer it out of the pixels. The tables below are the actual definition; the files
are their output, committed because the build should not need Pillow.

HOW THE RECOLOUR WORKS

Hue is *set*, not rotated. The originals are pure red (hue 0), so a rotation and an assignment agree
on them, but assignment is the honest description: every ink pixel comes out on the named hue.
Saturation and value are scaled, which is what keeps the artwork alive -- the drape's folds and the
gemstones' specular highlights both live in V, and V is only ever multiplied, so every crease and
every glint survives at the same relative strength it had in red.

LIT AND DIM

Each seat's drape exists twice. `cloth_<colour>.png` is the lit state, worn by the player whose turn
it is; `cloth_<colour>_dim.png` is every other seat. Both are the same hue, so the drape never stops
saying which seat it belongs to -- the turn is carried by lightness alone, underneath the identity
rather than instead of it.

The dim table is not a single multiplier, and the reason is worth keeping. The four lit drapes do
not sit at one lightness: bone is near-white at L 51 while plum and pewter sit at L 27. Dim
everything by the same factor and dim bone lands at L 34 -- *lighter than lit plum*. The column then
has a board that looks lit while a darker seat is actually to play, which is precisely the misread
the whole scheme exists to prevent. So sage, pewter and plum take the common factor and bone takes a
deeper one, chosen so that the brightest dim drape (bone, L 25) still falls below the darkest lit
drape (plum, L 27). Two bands that do not overlap; you can scan the column and be right.

The gemstones and the acolyte cube do not have a dim state. They are the other signal -- active player, first-player
marker -- and dimming both at once would leave the two indistinguishable.
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
FRAMES = HERE.parent / "assets-gothic" / "frames"

# The Cloister palette, lit. (hue in degrees, saturation multiplier, value multiplier)
#
# Chosen against two constraints: the four must separate from each other, and none may collide with
# the frame's gold. Measured pairwise CIE Lab dE between the four lit drapes is 28, comfortably past
# the point where two colours read as different rather than as two dye lots of one.
CLOTH = {
    "sage":   ( 95, 0.52, 1.05),   # verdigris / herb garden
    "pewter": (208, 0.55, 0.88),   # cold slate blue
    "plum":   (298, 0.55, 0.95),   # bishop's purple
    "bone":   ( 33, 0.16, 1.45),   # undyed wool -- see the note below about hue 33 and the gold
}

# The same four, dimmed for a seat that is not to play. sage/pewter/plum are CLOTH scaled by
# s x1.25, v x0.60; bone is scaled by v x0.45 instead, for the banding reason in the docstring.
# Pairwise dE among these is 19 at its tightest, so a dim seat is still plainly its own colour.
CLOTH_DIM = {
    "sage":   ( 95, 0.650, 0.630),
    "pewter": (208, 0.688, 0.528),
    "plum":   (298, 0.688, 0.570),
    "bone":   ( 33, 0.208, 0.653),
}

GEM = {
    "sage":   ( 95, 0.88, 1.00),
    "pewter": (208, 0.92, 1.02),
    "plum":   (298, 0.90, 1.00),
    "bone":   ( 33, 0.14, 1.30),   # pearl, not a coloured stone
}

SOURCES = [("cloth_red.png", "cloth_%s.png", CLOTH),
           ("cloth_red.png", "cloth_%s_dim.png", CLOTH_DIM),
           ("stones_red.png", "stones_%s.png", GEM)]

# The acolyte cube. It is a player's own marker, so it wears the seat colour too, and it takes the
# GEM treatment rather than the drape's: the drape is dyed wool and reads best desaturated, while
# this is a 70 px painted block that has to be unmistakable beside the grey serf cube a hand's width
# to its left. Bone is the case to watch -- at pearl saturation it would sit near that grey, so the
# GEM table's warm hue 33 carries it to a cream at dE 41 from the serf's #85888b instead.
#
# The source file is called cube_acolyte_yellow.svg and is not yellow; it has been red for as long
# as the gothic set has existed. Renaming it is a separate job from this one.
CUBE_SOURCE = "cube_acolyte_yellow.svg"
CUBE_FACES = ("#b52d2a", "#7f1a18", "#d4453f")   # top, left, right


def recolour_cube(text, hue, sat_scale, val_scale):
    """The same hue/S/V move as the drapes, applied to three fill colours in SVG markup."""
    import colorsys
    for face in CUBE_FACES:
        r, g, b = (int(face[i:i + 2], 16) / 255 for i in (1, 3, 5))
        _, s, v = colorsys.rgb_to_hsv(r, g, b)
        r, g, b = colorsys.hsv_to_rgb(hue / 360.0, min(s * sat_scale, 1.0), min(v * val_scale, 1.0))
        text = text.replace(face, "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255)))
    return text


def shift(src, hue, sat_scale, val_scale):
    """Recolour every non-transparent pixel to `hue`, scaling S and V.

    Transparent pixels are zeroed rather than left alone: a fully transparent pixel still carries
    RGB, and PIL's HSV round-trip will happily invent a colour for it that shows up the moment
    anything downstream premultiplies or resamples.
    """
    a = np.array(Image.open(src).convert("RGBA"))
    ink = a[:, :, 3] > 0
    hsv = np.array(Image.fromarray(a[:, :, :3], "RGB").convert("HSV")).astype(float)
    hsv[:, :, 0][ink] = hue * 256 / 360.0
    hsv[:, :, 1][ink] = np.clip(hsv[:, :, 1][ink] * sat_scale, 0, 255)
    hsv[:, :, 2][ink] = np.clip(hsv[:, :, 2][ink] * val_scale, 0, 255)
    out = a.copy()
    out[:, :, :3] = np.array(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))
    out[~ink] = 0
    return Image.fromarray(out, "RGBA")


def lightness(image):
    """Mean CIE L* over the ink, which is the number the lit/dim banding is chosen against."""
    a = np.array(image)
    rgb = a[a[:, :, 3] > 0][:, :3] / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array([0.2126, 0.7152, 0.0722])
    f = np.where(y > 0.008856, np.cbrt(y), 7.787 * y + 16 / 116)
    return float((116 * f - 16).mean())


def check_bands(frames):
    """The lit and dim bands must not overlap, or the column can be misread."""
    lit = {c: lightness(shift(frames / "cloth_red.png", *p)) for c, p in CLOTH.items()}
    dim = {c: lightness(shift(frames / "cloth_red.png", *p)) for c, p in CLOTH_DIM.items()}
    hi, lo = max(dim.values()), min(lit.values())
    print("\nlit  L: " + "  ".join("%s %.0f" % (c, lit[c]) for c in CLOTH))
    print("dim  L: " + "  ".join("%s %.0f" % (c, dim[c]) for c in CLOTH_DIM))
    ok = hi < lo
    print("brightest dim L %.0f %s darkest lit L %.0f  -- %s"
          % (hi, "<" if ok else ">=", lo,
             "the two bands do not overlap" if ok else
             "BANDS OVERLAP: a dim seat outshines a lit one, so the column can be misread"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frames-dir", default=str(FRAMES))
    ap.add_argument("--check", action="store_true",
                    help="compare against the committed files instead of overwriting them")
    args = ap.parse_args()
    frames = pathlib.Path(args.frames_dir).expanduser().resolve()

    problems = 0
    for source, pattern, palette in SOURCES:
        src = frames / source
        if not src.is_file():
            raise SystemExit("missing source layer %s" % src)
        for name, (hue, ss, vs) in palette.items():
            got = shift(src, hue, ss, vs)
            dest = frames / (pattern % name)
            if args.check:
                if not dest.is_file():
                    print("MISSING  %s" % dest.name)
                    problems += 1
                    continue
                have = np.array(Image.open(dest).convert("RGBA")).astype(int)
                diff = int(np.abs(have - np.array(got).astype(int)).max())
                print("%-24s %s" % (dest.name,
                                    "identical" if diff == 0 else "DIFFERS by %d" % diff))
                problems += diff != 0
            else:
                got.save(dest, "PNG", optimize=True)
                a = np.array(got)
                mean = a[a[:, :, 3] > 0][:, :3].mean(axis=0)
                print("%-24s hue %3d  s x%.3f  v x%.3f  ->  #%02x%02x%02x   L %.0f"
                      % (dest.name, hue, ss, vs, *mean.astype(int), lightness(got)))

    cubes = frames.parent / "ui"
    source = cubes / CUBE_SOURCE
    if not source.is_file():
        raise SystemExit("missing cube source %s" % source)
    for name, (hue, ss, vs) in GEM.items():
        got = recolour_cube(source.read_text(encoding="utf-8"), hue, ss, vs)
        dest = cubes / ("cube_acolyte_%s.svg" % name)
        if args.check:
            have = dest.read_text(encoding="utf-8") if dest.is_file() else None
            print("%-24s %s" % (dest.name, "identical" if have == got else
                                "MISSING" if have is None else "DIFFERS"))
            problems += have != got
        else:
            dest.write_text(got, encoding="utf-8")
            print("%-24s hue %3d  s x%.3f  v x%.3f" % (dest.name, hue, ss, vs))

    problems += check_bands(frames)

    if args.check:
        print("\n%s" % ("the committed layers match the palette" if not problems
                        else "PROBLEMS -- see above"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
