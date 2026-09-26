"""Every tray piece for wheel_space_check_v2, at every size, from the full-resolution original.

    python3 tools/ui_debug/make_tray_figures.py

Writes generated/figure_<subject>_<px>.png, which is git-ignored debug art the page inlines.

WHICH ART

--kind picks what a player row is drawn from. `unpainted` is the default: the filed sculpts in
ui/assets-gothic/sculpts/, three seats and three poses, the same poses as the painted set and
the art the painted set was made from. `--kind painted` renders their painted counterparts.
`--kind figure` reads the old concept art and still works if you want to compare.

THE LABEL IS STILL `plastic` AND THE KIND IS NOT. `unpainted` replaced a kind called
`sculpt_plastic`, which rendered ui/concept/player_N/sculpt_plastic.png -- four seats, one pose,
each a single flat colour. The label stayed because `210_plastic` is what duty_placement.json
was tuned at, what its `sizes` list names and what the sow's buttons say; renaming it would have
orphaned all of that to relabel the same slot. The kind changed because the name said where the
art came from and no longer would. The concept file of that name still exists and is still read,
directly rather than through this table, by ui/concept/build_browser.py and by
generate_asset_check.reference_band().

WHAT THE SWAP COST, measured 2026-09-26, AND WHAT WAS DONE ABOUT IT. The concept plastics carried
a hue per seat -- 115, 213 and 312 degrees at a mean saturation around 0.55, every pixel coloured.
The filed unpainted sculpts are one warm grey: hue 26 to 28, saturation 0.10 to 0.15, and under a
third of their pixels carry any colour at all. So the three seats stopped being told apart by
colour on every page that draws this set, which was a real loss on the arrangements view where the
captions name seats.

THE FIX IS A PER-SEAT TINT AT RENDER TIME HERE, rather than three more files or a colour-carrying
set. See `seat_tint` below for what it does and `SEAT_TINT` for how hard. It is baked into the
PNGs rather than applied by whichever page happens to draw them, so every consumer gets it: the
placement sheet, the sow, the board check, and generate_wheel_space_check_v2.py, which reads these
files straight off disk. A tint applied in a page would have coloured that one page, and only
while its art was inlined -- a CSS mask needs a same-origin source, so the same trick from a
file:// URL fails silently and renders the figure grey with no error at all.

`generated/` IS GIT-IGNORED, so pulling the change does not colour anything. Re-run this.

TWO RULES, AND THEY PULL AGAINST EACH OTHER

1. A piece is a PLINTH standing on a tile. The player sculpts do not share a scale -- their
   plinths measure 573 to 620 px in the committed art -- so they are levelled on the plinth
   first, targeting the NARROWEST so nothing is ever upscaled. That is the rule
   ui/concept/build_browser.py already uses for this very kind, and it is what keeps the bases
   equal where they sit side by side.
2. The nominal size is a HEIGHT. Once the plinths agree the heights cannot also be made to agree
   without breaking rule 1. So the set is scaled until the TALLEST lands exactly on the nominal
   and the rest come in under it: nothing overshoots the size on its label, and the relative
   heights stay honest rather than being flattened.

With the filed sculpts the two rules barely fight; the run prints the levelled spread so you can
see how hard they are pulling on whatever art you gave it. With --kind figure the spread is
wider, which is that art's own height variation showing through and a thing to fix at the source
if it matters.

ALL FOUR COME FROM THE SAME PLACE

Every row reads ui/concept/player_N/, so a checkout is all it takes to rebuild the tray. The
fourth row used to be cut out of a variant sheet sitting in ~/Downloads -- one row of the tray
was unreproducible on any other machine, and would have gone quietly missing the day that file
was tidied away. It was also a different artwork family with its own base, which kept it out of
the levelling and left it standing on a wider plinth than the three beside it. Both problems had
the same fix: use player 4's own sculpt, like everyone else's.

Nothing is ever upscaled to reach a size: every version is rendered DOWN from the original, with
alpha premultiplied before resampling so the cutout picks up no dark fringe from the transparent
pixels around it, and a size taller than its own source is refused rather than invented.
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated"

# The measuring and the alpha-safe downscale live in one place, shared with check_sculpt.py --
# both of them care about exactly the same properties of exactly the same artwork, and the third
# copy of these functions was the one that made that obvious.
sys.path.insert(0, str(HERE))
import sculpt_metrics as sm                                          # noqa: E402

bbox, plinth, resize, down, fringe = (
    sm.bbox, sm.plinth_width, sm.resize, sm.down, sm.fringe)

SIZES = (90, 120, 150, 180, 210)
CONCEPT = ROOT / "ui" / "concept"
SCULPTS = ROOT / "ui" / "assets-gothic" / "sculpts"
PAINTED = SCULPTS / "painted"

# THE SEAT COLOURS, READ RATHER THAN COPIED. ui/render/population_sets.py owns them and says why:
# a set "carries no colours", because a seat's colour is a property of the PLAYER rather than of
# how their people are drawn, and two surfaces drawing seat-coloured figures have to agree about
# plum. This is now a third surface, so it reads the one table.
sys.path.insert(0, str(ROOT / "ui" / "render"))
import population_sets as pop                                         # noqa: E402

# HOW MUCH OF THE SCULPT'S OWN GREY THE SEAT'S COLOUR REPLACES, 0 to 1.
#
# 0.60 because the job is telling three seats apart at 90 px, the smallest size below, where the
# robe is a sliver of a figure the height of a line of text -- not because it looks best on the
# 210. Measured 2026-09-26: at 0.60 the tinted figures' mean saturation lands inside the painted
# set's own 0.34-0.44 band, and at 0.45 it sits below it.
#
# One constant rather than a flag or a settings file, and that is a decision rather than an
# omission. A flag lets two people render the tray differently and leaves no record of which; a
# settings file nothing else reads is a decision nobody can check. Changing this is a one-line
# diff that says what changed and can be reverted.
SEAT_TINT = 0.60

# A KIND IS A SET OF ART, AND IT DECIDES FOUR THINGS AT ONCE: where the art comes from, which
# seats it covers, how many poses each seat has, and whether it is tinted. They are kept together
# here because they only make sense together -- `painted` has three poses and no seat 4,
# `sculpt_plastic` has one pose and four seats, and pairing the wrong source with the wrong shape
# is how a tray ends up silently one row short.
#
# `tint` IS IN THE TABLE AND NOT A FLAG, for the same reason the other three are. The painted
# sculpts already carry their seat's colour in paint -- seats 2 and 3 measure hue 213-217 and
# 315-325 -- so tinting them would be painting over paint, and a flag would let that happen by
# typing. Here it cannot: the kind decides, and the kind is what the run is.
#
# `label` is what the size becomes on the page: 210 rendered from `painted` is `210_painted`.
# It is derived here rather than passed in, so a run cannot label itself as a set it did not draw.
#
# ONE KIND PER LABEL, and that is load-bearing rather than tidy. Two kinds writing `plastic`
# would write the same filenames from different art: seats 1 to 3 pose 1 overwritten by
# whichever ran last, and any seat or pose only the other one had left behind as a file the
# pages still discover. `sculpt_plastic` was therefore removed rather than kept alongside
# `unpainted`. Asking for it now fails at argparse with the choices listed, which is the loud
# failure; keeping it would have been the quiet one.
KINDS = {
    "unpainted":      {"label": "plastic", "seats": (1, 2, 3),    "poses": 3, "tint": True},
    "figure":         {"label": "figure",  "seats": (1, 2, 3, 4), "poses": 1, "tint": False},
    "painted":        {"label": "painted", "seats": (1, 2, 3),    "poses": 3, "tint": False},
}

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--kind", default="unpainted", choices=tuple(KINDS),
                help="which art a player row is drawn from (default: %(default)s)")
ap.add_argument("--out", default=None, help="where to write (default: %s)" % OUT.relative_to(ROOT))
args = ap.parse_args()
OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.mkdir(parents=True, exist_ok=True)
KIND = KINDS[args.kind]


# ---- the seat tint -------------------------------------------------------------------------
#
# WHAT IT REPLACES AND WHAT IT KEEPS: the seat's hue and saturation, the sculpt's own lightness.
# That is the CSS `color` blend, and it is the right one here because the filed unpainted sculpts
# are one warm grey -- hue 26 to 28, saturation 0.10 to 0.15, under a third of their pixels
# carrying any colour at all. There is nothing there for a hue rotation to rotate, and a duotone
# of the kind generate_asset_check.seat_tint draws maps lightness onto a two-point ramp, which
# suits the flat concept pawns it was written for and would flatten the modelling that makes
# these sculpts rather than pawns.
#
# IT IS THE SPEC OPERATION, NOT AN APPROXIMATION -- SetLum and ClipColor from Compositing and
# Blending Level 1, with that spec's 0.30/0.59/0.11 luminosity weighting and NOT the Rec.709
# weighting sculpt_metrics uses for rim luminance. Getting that constant wrong is a plausible
# near-miss that looks right, so it was checked against a browser rendering the same blend on the
# same figure: mean difference 0.5 and worst channel 2.5 of 255 over the opaque pixels, which is
# sRGB rounding.
#
# HERE RATHER THAN IN sculpt_metrics: that module is for what more than one tool needs, and its
# own note says the third copy of those functions is what made that obvious. This has one caller.
LUM = np.array([0.30, 0.59, 0.11])


def _lum(c):
    return c @ LUM


def _clip_colour(c):
    """Pull an out-of-gamut colour back toward its own luminosity rather than clamping channels.

    Clamping each channel on its own would shift the hue of whatever went out of range, which is
    the one thing this operation exists not to do.
    """
    l = _lum(c)[..., None]
    lo, hi = c.min(-1)[..., None], c.max(-1)[..., None]
    c = np.where(lo < 0, l + (c - l) * l / np.maximum(l - lo, 1e-9), c)
    return np.where(hi > 1, l + (c - l) * (1 - l) / np.maximum(hi - l, 1e-9), c)


def seat_tint(im: Image.Image, hexcol: str, amount: float = SEAT_TINT) -> Image.Image:
    """`im` recoloured toward `hexcol`, keeping its own lightness. Alpha is untouched.

    ALPHA IS UNTOUCHED AND THAT MATTERS BEYOND TIDINESS: the run ends by asserting that no
    part-transparent rim comes out lighter than the body, which is how it catches a resize
    inventing light pixels. Because the blend preserves lightness exactly, that number does not
    move -- measured across all nine figures it shifts by at most 0.2, staying between -12 and
    -31 against an assertion that trips at +6.
    """
    a = np.asarray(im.convert("RGBA")).astype(np.float64) / 255.0
    rgb, alpha = a[..., :3], a[..., 3:]
    seat = np.broadcast_to(
        np.array([int(hexcol[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]), rgb.shape)
    blended = _clip_colour(seat + (_lum(rgb) - _lum(seat))[..., None])
    out = np.concatenate([np.clip(rgb + (blended - rgb) * amount, 0, 1), alpha], axis=-1)
    return Image.fromarray((out * 255).round().astype(np.uint8), "RGBA")


def seat_colour(seat: int) -> str:
    """Seat 1 is the first name in SEAT_ORDER. Wraps, so a set with more seats than the table has
    colours repeats rather than failing -- which is what generate_asset_check already does when it
    deals five sculpts four colours."""
    order = [s for s in pop.SEAT_ORDER if s in pop.SEAT_SWATCH]
    return pop.SEAT_SWATCH[order[(seat - 1) % len(order)]]


def source_path(seat: int, pose: int) -> pathlib.Path:
    """Where one seat's one pose lives, which differs per kind rather than per seat.

    `unpainted` and `painted` are the two halves of the filed set and differ only in which
    folder they read -- same nine names, three poses a seat, named for the pose rather than for
    what the figure is doing (see docs/architecture/painted_miniatures.md for why seat 1 moved
    onto that convention). The concept kind is one file per seat and ignores the pose.
    """
    if args.kind == "unpainted":
        return SCULPTS / ("player_%d_v%d.png" % (seat, pose))
    if args.kind == "painted":
        return PAINTED / ("player_%d_v%d.png" % (seat, pose))
    return CONCEPT / ("player_%d" % seat) / ("%s.png" % args.kind)


made = []

# Keyed by (seat, pose) so the levelling below sees every piece at once. That matters more for
# `painted` than it ever did for the concept art: nine figures drawn in separate sessions do not
# share a plinth, and levelling a subset would leave the columns standing at different scales.
src = {}
for seat in KIND["seats"]:
    for pose in range(1, KIND["poses"] + 1):
        p = source_path(seat, pose)
        if not p.is_file():
            raise SystemExit("%s is missing -- %s art for seat %d pose %d"
                             % (p, args.kind, seat, pose))
        im = Image.open(p).convert("RGBA")
        im = im.crop(bbox(im))
        # TINTED ONCE, ON THE CROPPED SOURCE, so all five sizes are rendered down from the same
        # coloured pixels: nine blends rather than forty-five, and no chance of two sizes of the
        # same figure disagreeing about its colour.
        if KIND["tint"]:
            im = seat_tint(im, seat_colour(seat))
        src[(seat, pose)] = im
print("%d pieces from %s (%d seats x %d pose%s)%s"
      % (len(src), args.kind, len(KIND["seats"]), KIND["poses"],
         "" if KIND["poses"] == 1 else "s",
         (", tinted %d%% toward %s" % (round(100 * SEAT_TINT),
          ", ".join("%s %s" % (s, pop.SEAT_SWATCH[s])
                    for s in pop.SEAT_ORDER[:len(KIND["seats"])])))
         if KIND["tint"] else ""))

target = min(plinth(src[n]) for n in src)
lev = {n: target / plinth(src[n]) for n in src}
assert all(v <= 1.0 + 1e-9 for v in lev.values()), \
    "levelling would UPSCALE one of them, which the narrowest-target rule exists to prevent: %s" % lev
tallest = max(src[n].height * lev[n] for n in src)
print("plinth target %d px (the narrowest)  ·  tallest levelled figure %.0f px" % (target, tallest))

for px in SIZES:
    k = px / tallest                                               # one k for the whole set
    for (seat, pose) in sorted(src):
        f = lev[(seat, pose)] * k
        im = src[(seat, pose)]
        made.append((("player_%d_p%d_%d_%s" % (seat, pose, px, KIND["label"])),
                     down(im, round(im.width * f), round(im.height * f),
                          "player_%d pose %d at %d" % (seat, pose, px)), px))

print()
print("%-34s %-10s %-8s %-11s %s"
      % ("file", "w × h", "plinth", "of nominal", "rim vs body"))
worst = None
for name, im, px in made:
    f = OUT / ("figure_%s.png" % name)
    im.save(f)
    g = fringe(im)
    worst = g if worst is None else max(worst, g)
    print("%-34s %-10s %-8d %-11s %+.1f" % (f.name, "%d × %d" % im.size, plinth(im),
                                            "%d%%" % round(100 * im.height / px), g))

# A light rim is invisible against a pale tile and glaring against a dark one, so it cannot be
# left to the eye on whichever tile colour happens to be selected. The art's own edges are
# shaded and come out around -20; anything positive is the pipeline inventing light pixels.
print()
print("worst rim %+.1f luminance against the body (the source art runs about -20)"
      % (0.0 if worst is None else worst))
assert worst is not None and worst < 6.0, (
    "a part-transparent rim %+.1f lighter than the body means light pixels are being invented "
    "somewhere in the resize -- do not ship these, and do not paper over it by recolouring the "
    "edge to suit one tile, which only hides it on that tile." % worst)
print("wrote %d files to %s" % (len(made), OUT))
