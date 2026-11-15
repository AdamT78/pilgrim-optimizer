#!/usr/bin/env python3
"""Split the drawn acolyte into the parts that take a player's colour and the part that does not.

    python3 tools/duty_art/split_acolyte.py            # report what it would do
    python3 tools/duty_art/split_acolyte.py --write    # write the layers

WHY THIS EXISTS. An acolyte is drawn in its player's colour -- that is how you read whose figures
stand where -- and the figure the board grew up with manages it by being one flat shape with one
fill. A drawing does not have that luxury. This one has a brown ink and a tan for face and hands,
which are the drawing's own, and TONES OF THE ROBE, which are the player's: lit, in shadow, and --
in a master that draws one -- darker still for a cord at the waist. Tint only the lit one and a
plum acolyte gets green shadows, which is worse than no shading at all.

THE CORD IS A ROLE THAT COMES AND GOES. v01 drew it in the tan, v03 made it a third tone of the
robe, and v04 -- what the board draws today -- has no cord at all. That is why it is optional
below rather than required: the splitter reports it as not in this drawing and writes three
layers instead of four, which is a fact about the master and not a fault in it.

SO THE SHADOW IS DERIVED, NOT STORED. It is the robe with the light taken out of it, and the
amount is measured off the drawing -- in HLS the dark green sits at a fixed fraction of the lit
green's lightness, and that one ratio carries to any seat colour. The alternative is a second
swatch per player chosen by eye, which is four more numbers to keep in step with four that
already exist.

AND IT HIDES WHERE YOU WOULD NOT LOOK FOR IT. The dark green is as DARK as the brown outline --
both sit near luminance 44 against the lit robe's 104 -- so splitting the picture by brightness
puts them in one bin and loses the shadow entirely. Hue is what separates them, and finding that
cost a first pass which reported the shadow as half a percent of a figure it is a tenth of.

WHAT COMES OUT. Three files: two masks carrying only alpha, which the board fills with the seat's
colour and the seat's colour darkened, and an overlay carrying the drawing's own colours and
whatever alpha the masks did not take. Laid one over the other they are the drawing again, which
the round trip below checks rather than assumes. One set serves every seat, so a palette change
costs nothing on disk.
"""
import argparse
import colorsys
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "ui" / "board_v2"
ACOLYTES = BOARD / "tokens" / "acolytes"
ATTRIB_FILE = BOARD / "attribution.json"
SUFFIX = ".webp"

# LOSSLESS, FOR THE REASON THE CUT-OUTS ARE. A mask is one flat colour with a varying alpha and
# the overlay is four flat colours; that is the shape lossy coding handles worst, and on this
# kind of picture lossless is the smaller file as well.
LOSSLESS = True

# THE FOUR ROLES, FOUND BY RULE RATHER THAN TYPED IN, so a redrawn acolyte in different colours
# still splits and a drawing that is NOT in this shape says so instead of coming out wrong. The
# rules are about where each role sits, not what colour it happens to be: the ink is dark and not
# green, the shadow is dark and green, the robe is mid and green, the tan is bright and warm.
def classify(rgb, alpha):
    import numpy as np
    from PIL import Image
    hsv = np.asarray(Image.fromarray(rgb.astype("uint8"), "RGB").convert("HSV")).astype(float)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    op = alpha > 200 / 255.0
    robe_hue = (H > 40) & (H < 95)
    return {
        "ink": op & (V < 90) & ~robe_hue,
        "shade": op & (V >= 40) & (V < 90) & robe_hue,
        "robe": op & (V >= 90) & (V < 170) & robe_hue,
        "tan": op & (V >= 150) & (S >= 60) & (H > 10) & (H < 45),
        # THE CORD IS A THIRD ROBE TONE, darker than the shadow, and it is the player's like the
        # other two. Drawn in the shadow's own colour it disappears: it is a thin band sitting
        # among the fold shadows, the same colour as them, and where it crosses the robe's dark
        # centre panel there is nothing left of it at all. Darker is the only direction with any
        # room, so it goes past the ink's lightness and reads as a dark line on every seat.
        #
        # SEPARATED FROM THE SHADOW BY VALUE, NOT HUE, because both are the same green. The
        # shadow sits at luminance 46 and this at 24, so 40 divides them with room either side;
        # the ink is darker still at 44 but is not green, which is what the hue test above is
        # for.
        "cord": op & (V < 40) & robe_hue,
    }, op


# WHAT EACH ROLE SHOULD BE A SHARE OF THE FIGURE, as wide bands rather than numbers. They are
# here to catch a drawing this script cannot split -- one with no shadow, or with the hood drawn
# in the tan -- not to insist on a particular acolyte. Measured on the first one: 26% ink, 10%
# shadow, 56% robe, 8% tan.
SHARES = {"ink": (0.10, 0.45), "shade": (0.02, 0.30), "robe": (0.30, 0.75),
          "tan": (0.02, 0.20), "cord": (0.005, 0.10)}
# A ROLE A DRAWING DOES NOT USE IS NOT A FAULT IN THE DRAWING. The first acolyte drew its cord
# in the same tan as the hands and has no separate brown at all, so demanding one would refuse
# the tree's own filed artwork -- which this did for one run, reporting the 0.1% of edge pixels
# that fall in the cord's band as a cord that was too small. An optional role found below its
# share is DROPPED for that drawing rather than failing it, and dropping it matters: an endpoint
# taken from a tenth of a percent of antialiasing is not a colour the picture is made of, and
# every blend in the unmix would then be measured partly against noise.
OPTIONAL = ("cord",)
TINTED = ("robe", "shade", "cord")
MAX_UNCLASSIFIED = 0.02

# HOW CLOSE THE LAYERS MUST COME BACK TO THE DRAWING. The remainder is solved for rather than
# assembled, so the only error left is where a pixel is ENTIRELY one of the tinted roles and has
# no remainder to carry the drawing's own variation -- it comes out that role's flat colour,
# which is what a tint should be.
#
# JUDGED ON HOW MANY PIXELS ARE WRONG, NOT ON THE WORST ONE, and that is a correction. A gate on
# the maximum alone refused the third acolyte over ONE pixel in 896,800 -- the single darkest in
# the drawing, darker than the ink itself, which the cord's role claims whole and which therefore
# has no remainder at all. Meanwhile a genuinely broken split, the kind this exists to catch, was
# wrong by 24 and more across 867 pixels. The count is what tells those apart; the maximum is
# just the tail. Measured: v01 has nothing over 8, v03 has four pixels, a broken unmix had 867.
WORST_OK, MEAN_OK = 20.0, 0.5
LOUD, LOUD_SHARE = 8.0, 0.0001      # at most a hundredth of a percent may be off by this much


def roles_of(path):
    """The four flat colours and their shares, measured off one drawing."""
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    alpha = a[:, :, 3] / 255.0
    rgb = a[:, :, :3]
    masks, op = classify(rgb, alpha)
    named = np.zeros(op.shape, bool)
    out = {}
    for name, m in masks.items():
        share = m.sum() / op.sum()
        if name in OPTIONAL and share < SHARES[name][0]:
            continue                       # a colour this drawing does not use
        named |= m
        if not m.any():
            raise SystemExit("%s: nothing is %s -- this is not an acolyte this can split"
                             % (path.name, name))
        px = rgb[m].reshape(-1, 3).astype(int)
        cols, counts = np.unique(px, axis=0, return_counts=True)
        # THE MODE, NOT THE MEAN. The art is flat, so the mode IS the flat value; a mean is
        # pulled about by whatever the edges between roles are doing.
        out[name] = (tuple(int(v) for v in cols[counts.argmax()]), share)
    loose = (op & ~named).sum() / op.sum()
    return out, loose, alpha, rgb


def shade_ratio(roles):
    """How much light the shadow has lost, in HLS, so it can be taken out of any seat colour."""
    lr, ll, ls = colorsys.rgb_to_hls(*[c / 255 for c in roles["robe"][0]])
    dr, dl, ds = colorsys.rgb_to_hls(*[c / 255 for c in roles["shade"][0]])
    return {"l": dl / ll, "s": (ds / ls) if ls > 1e-6 else 1.0}


def split(rgb, alpha, roles):
    """Per-pixel share of each role, by reading every pixel as a blend of its nearest two.

    EVERY PAIR, NOT ONLY THE PAIRS CONTAINING A TINTED ROLE. A pixel on the edge between the ink
    and a hand is a blend of two roles neither of which is the robe, and a model offered only
    robe-to-ink and robe-to-tan has to call that three-quarters robe. Offered ink-to-tan as well
    it calls it what it is.

    AND IT PROJECTS RATHER THAN COMPARING DISTANCES. A pixel BEYOND a role -- darker than the
    flat ink, brighter than the flat tan -- is not between anything; clamping to the end of the
    segment puts it where it belongs instead of giving it a share of a robe it is no part of.
    """
    import numpy as np

    names = list(roles)
    cols = [np.array(roles[n][0], dtype=float) for n in names]
    best = np.full(rgb.shape[:2], np.inf)
    share = {n: np.zeros(rgb.shape[:2]) for n in names}
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            A, B = cols[i], cols[j]
            seg = B - A
            t = np.clip(((rgb - A) * seg).sum(axis=2) / float((seg * seg).sum()), 0.0, 1.0)
            resid = np.linalg.norm(rgb - (A + t[..., None] * seg), axis=2)
            take = resid < best
            best = np.where(take, resid, best)
            for n in names:
                w = (1.0 - t) if n == names[i] else (t if n == names[j] else 0.0)
                share[n] = np.where(take, w, share[n])
    for n in names:
        share[n] = np.clip(share[n], 0.0, 1.0) * (alpha > 0)
    return share


def layers(share, alpha, rgb, roles):
    """The two masks and the overlay, the overlay carrying EXACTLY what the masks do not.

    THE REMAINDER IS SOLVED FOR, NOT ASSEMBLED. Rebuilding it out of the flat ink and tan would
    flatten the drawing's own variation into the role colours; subtracting the tinted shares from
    the real pixel keeps whatever is actually there, so the three add back up to the picture
    rather than to an idealised version of it.
    """
    import numpy as np

    # ONLY THE TINTED ROLES THIS DRAWING ACTUALLY HAS. One of them is optional -- the first
    # acolyte has no cord tone at all -- and iterating the full list regardless is how a tool
    # that handles a missing role everywhere else still falls over on it here.
    tint = [n for n in TINTED if n in roles]
    taken = sum(share[n][..., None] * np.array(roles[n][0], dtype=float) for n in tint)
    rest_w = np.clip(1.0 - sum(share[n] for n in tint), 0.0, 1.0)
    rest_rgb = np.where(rest_w[..., None] > 1e-3,
                        (rgb - taken) / np.maximum(rest_w, 1e-3)[..., None],
                        np.array(roles["ink"][0], dtype=float))
    return rest_w, np.clip(rest_rgb, 0, 255), taken


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write the layers; otherwise report")
    a = ap.parse_args()

    import numpy as np
    from PIL import Image

    masters = sorted((ACOLYTES / "masters").glob("acolyte_*_master_v*.png"))
    if not masters:
        raise SystemExit("no acolyte master under %s/masters/" % ACOLYTES)
    rec = {}
    if ATTRIB_FILE.is_file():
        rec = json.loads(ATTRIB_FILE.read_text(encoding="utf-8")).get("files", {})

    for src in masters:
        stem = src.stem.replace("_master", "").rsplit("_v", 1)[0]       # acolyte_friar
        ver = src.stem.rsplit("_v", 1)[1]
        srel = "tokens/acolytes/masters/%s" % src.name
        if srel not in rec:
            print("  %-40s no attribution entry, skipped" % src.name)
            continue

        roles, loose, alpha, rgb = roles_of(src)
        bad = [n for n, (_, sh) in roles.items()
               if not (SHARES[n][0] <= sh <= SHARES[n][1])]
        bad += [n for n in SHARES if n not in roles and n not in OPTIONAL]
        print("  %s" % src.name)
        for n in SHARES:
            if n not in roles:
                print("      %-6s %18s" % (n, "not in this drawing"))
                continue
            col, sh = roles[n]
            print("      %-6s #%02x%02x%02x  %5.1f%%%s"
                  % (n, *col, 100 * sh, "   OUT OF RANGE" if n in bad else ""))
        print("      %-6s %18.1f%%" % ("edges", 100 * loose))
        if bad or loose > MAX_UNCLASSIFIED:
            print("      this drawing is not in the shape this splits -- skipped")
            continue

        share = split(rgb, alpha, roles)
        rest_w, rest_rgb, taken = layers(share, alpha, rgb, roles)
        back = taken + rest_w[..., None] * rest_rgb
        inside = alpha > 0.5
        err = np.abs(back - rgb).max(axis=2)[inside]
        loud = (err > LOUD).mean()
        print("      round trip: worst %.2f of 255, mean %.3f, over 2 %.3f%%, over %g %.5f%%"
              % (err.max(), err.mean(), 100 * (err > 2).mean(), LOUD, 100 * loud))
        if err.max() > WORST_OK or err.mean() > MEAN_OK or loud > LOUD_SHARE:
            print("      the split does not reproduce the drawing -- skipped")
            continue

        op = alpha > 0.004
        ys, xs = np.where(op)
        box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        print("      trimmed to %d x %d, aspect %.4f"
              % (box[2] - box[0], box[3] - box[1],
                 (box[3] - box[1]) / (box[2] - box[0])))

        def mask(w):
            m = (np.clip(w * alpha, 0, 1) * 255).round().astype(np.uint8)
            return Image.fromarray(np.dstack([np.full_like(m, 255)] * 3 + [m]),
                                   "RGBA").crop(box)

        wrote = []
        for n in [n for n in TINTED if n in roles]:
            out = ACOLYTES / ("%s_%s_v%s%s" % (stem, n, ver, SUFFIX))
            if a.write:
                mask(share[n]).save(out, "WEBP", lossless=LOSSLESS, quality=100, method=6,
                                    exact=True)
            wrote.append(out.name)
        over = np.dstack([rest_rgb.round().astype(np.uint8),
                          (np.clip(rest_w * alpha, 0, 1) * 255).round().astype(np.uint8)])
        out = ACOLYTES / ("%s_over_v%s%s" % (stem, ver, SUFFIX))
        if a.write:
            Image.fromarray(over, "RGBA").crop(box).save(out, "WEBP", lossless=LOSSLESS,
                                                         quality=100, method=6, exact=True)
        wrote.append(out.name)
        print("      -> %s%s" % (", ".join(wrote), "" if a.write else "   (dry run)"))
        print("      shadow is the robe at %.3f of its lightness and %.3f of its saturation"
              % (shade_ratio(roles)["l"], shade_ratio(roles)["s"]))

    if not a.write:
        print("\nnothing written; pass --write to file them")
    else:
        print("\nRECORD EVERY FILE WRITTEN ABOVE IN attribution.json, and note that the board "
              "\nreads the figure's numbers from action_board/friar.py -- the ratio printed "
              "\nabove lives there, and a redrawn acolyte whose shadow sits differently needs it "
              "\nmoved by hand, because nothing downstream re-measures the master.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
