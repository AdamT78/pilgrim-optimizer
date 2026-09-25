"""Every tray piece for wheel_space_check_v2, at every size, from the full-resolution original.

    python3 tools/ui_debug/make_tray_figures.py

Writes generated/figure_<subject>_<px>.png, which is git-ignored debug art the page inlines.

WHICH ART

--kind picks what a player row is drawn from. `sculpt_plastic` is the default and is what the
tray wants: the pieces then read as one family of miniatures, and they are a far tidier set than
the painted figures -- 5% apart in height and plinth where figure.png is 12% and 6%. The painted
figures are also dark-robed, and measured against the slate tile they lose half to two thirds of
their outline where the sculpts do not. `--kind figure` still works if you want to compare.

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

With the sculpts the two rules barely fight: the four come in within about 8% of each other on
identical bases. With --kind figure the spread is wider, which is that art's own height variation
showing through and a thing to fix at the source if it matters.

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
PAINTED = ROOT / "ui" / "assets-gothic" / "sculpts" / "painted"

# A KIND IS A SET OF ART, AND IT DECIDES THREE THINGS AT ONCE: where the art comes from, which
# seats it covers, and how many poses each seat has. They are kept together here because they
# only make sense together -- `painted` has three poses and no seat 4, `sculpt_plastic` has one
# pose and four seats, and pairing the wrong source with the wrong shape is how a tray ends up
# silently one row short.
#
# `label` is what the size becomes on the page: 210 rendered from `painted` is `210_painted`.
# It is derived here rather than passed in, so a run cannot label itself as a set it did not draw.
KINDS = {
    "sculpt_plastic": {"label": "plastic", "seats": (1, 2, 3, 4), "poses": 1},
    "figure":         {"label": "figure",  "seats": (1, 2, 3, 4), "poses": 1},
    "painted":        {"label": "painted", "seats": (1, 2, 3),    "poses": 3},
}

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--kind", default="sculpt_plastic", choices=tuple(KINDS),
                help="which art a player row is drawn from (default: %(default)s)")
ap.add_argument("--out", default=None, help="where to write (default: %s)" % OUT.relative_to(ROOT))
args = ap.parse_args()
OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.mkdir(parents=True, exist_ok=True)
KIND = KINDS[args.kind]


def source_path(seat: int, pose: int) -> pathlib.Path:
    """Where one seat's one pose lives, which differs per kind rather than per seat.

    The concept kinds are one file per seat and ignore the pose; `painted` is the filed set,
    three poses a seat, named for the pose rather than for what the figure is doing -- see
    docs/architecture/painted_miniatures.md for why seat 1 moved onto that convention.
    """
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
        src[(seat, pose)] = im.crop(bbox(im))
print("%d pieces from %s (%d seats x %d pose%s)"
      % (len(src), args.kind, len(KIND["seats"]), KIND["poses"],
         "" if KIND["poses"] == 1 else "s"))

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
