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

WHAT THE SWAP COSTS, measured 2026-09-26. The concept plastics carried a hue per seat -- 115,
213 and 312 degrees at a mean saturation around 0.55, every pixel coloured. The filed unpainted
sculpts are one warm grey: hue 26 to 28, saturation 0.10 to 0.15, and under a third of their
pixels carry any colour at all. So the three seats are no longer told apart by colour on any
page that draws this set, which is a real loss on the arrangements view where the captions name
seats. It is what the art is; the fix, if it is wanted, is a per-seat tint at render time here
rather than three more files.

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

# A KIND IS A SET OF ART, AND IT DECIDES THREE THINGS AT ONCE: where the art comes from, which
# seats it covers, and how many poses each seat has. They are kept together here because they
# only make sense together -- `painted` has three poses and no seat 4, `sculpt_plastic` has one
# pose and four seats, and pairing the wrong source with the wrong shape is how a tray ends up
# silently one row short.
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
    "unpainted":      {"label": "plastic", "seats": (1, 2, 3),    "poses": 3},
    "figure":         {"label": "figure",  "seats": (1, 2, 3, 4), "poses": 1},
    "painted":        {"label": "painted", "seats": (1, 2, 3),    "poses": 3},
}

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--kind", default="unpainted", choices=tuple(KINDS),
                help="which art a player row is drawn from (default: %(default)s)")
ap.add_argument("--out", default=None, help="where to write (default: %s)" % OUT.relative_to(ROOT))
args = ap.parse_args()
OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.mkdir(parents=True, exist_ok=True)
KIND = KINDS[args.kind]


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
