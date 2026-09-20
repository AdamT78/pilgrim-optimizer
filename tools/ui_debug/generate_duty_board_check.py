"""Nine duty tiles carrying MIXED stacks of sculpts, to settle how a crowded tile should read.

WHAT THIS ASKS THAT THE OTHER PAGES DO NOT

v1 asks how much room the wheel GETS. v3 asks how big the wheel NEEDS to be. Both draw at most
one piece per tile, dropped by hand. This page asks the question that only turns up once several
acolytes share a position: given that a duty tile holds a VECTOR -- p1's acolytes there, p2's,
p3's -- where does each sculpt stand, and can a player still read the tile?

That is four decisions, and they are independent, which is why they are four controls rather
than one mode:

    the SHAPE     how the total splits across seats            per tile, click its banner
    the FORMATION where n sculpts stand                        spread / set-back / rank sliders
    the SEATING   which seat takes which slot                  grouped or arrival order
    the DEPTH CUE how a figure set back is drawn               haze, darken or off

Nothing in that chain needs to know about the rest, so they compose. A board is one choice from
each.

    python3 tools/ui_debug/generate_duty_board_check.py --open

FIFTEEN SHAPES, NOT FIFTY-FIVE

Across three seats a total of one to five splits 55 ways if you care which seat holds which
count. You do not: 2+1+1 looks the same whoever owns the pair, because the seating rule decides
the colours afterwards. Collapsing by that symmetry leaves fifteen distinct pictures -- and only
EIGHT of them can tell the two seating rules apart, because the seven single-seat and one-each
shapes have nothing to group or interleave. The `sweep` deal puts a different shape on every
tile so the set can be walked rather than imagined.

The enumeration and both seat queues are built HERE and handed to the page as data, so the page
displays rather than derives, and so `tests/test_ui_debug_duty_board.py` can hold them to it.
The formation stays in the page because it is geometry driven by live sliders, and the depth cue
with it.

A TYPICAL DEAL IS NOT A UNIFORM ONE

Dealing evenly across the fifteen would show a board no game produces. Counted across the
engine's own scenario fixtures, an occupied duty position holds one acolyte in 86% of cases, two
in 13% and three in under 2%; a little over a quarter of positions are empty. `typical` carries
those weights.

Which makes `typical` deliberately dull, and that is the point. On a board dealt this way most
tiles hold nothing or one sculpt, where the seating rule and the depth cue make NO difference at
all -- so anyone about to spend a week on the difference between grouped and arrival order
should look at this deal first and see how rarely it is visible. `crowded` and `sweep` are for
judging the rules; `typical` is for judging whether they matter.

Read the weights as the right SHAPE rather than as measured frequencies: those fixtures were
chosen to exercise rules, not to be representative, and the repository carries no replays to
check them against.

The deal is seeded and the seed is on the page, so two screenshots can be compared.

DEPTH IS SHADED BY DEPTH, NOT BY RANK

A figure's shading is proportional to how far back it actually stands, so the middle of three
(set back a little) gets a little and a back rank gets the full amount. One rule instead of a
special case for "the back row", which also means the sliders cannot produce a board where the
cue and the geometry disagree.

Two modes, because they are different claims. `darken` goes toward black with some desaturation
-- brightness alone leaves the seat colour at full chroma and reads as different plastic rather
than as distance. `haze` blends toward the tile colour, which is what distance actually does: a
far object loses contrast against its background rather than simply going dark.

The haze filters carry `color-interpolation-filters="sRGB"` and that is load-bearing. SVG
filters default to linearRGB; measured against the default, a full-strength haze landed less
than half as dark as its flood-opacity asked for and the bottom third of the slider did nothing
visible at all.

WHETHER THE CUE EATS THE SEAT COLOUR

It is the obvious objection and it was measured rather than assumed. Sampling the rendered
sculpts through a mask fixed from the UNSHADED render -- a brightness threshold instead drops
pixels as the figure darkens and reports the cue as weaker than it is -- a back-rank p1 at haze
60% moves about dE 12 from its own front rank while a different seat sits about dE 50 away. The
margin narrows as the amount rises and `darken` is the tighter of the two, because it pulls
every seat toward a neutral they share. If a strong cue is wanted, haze is the safer way to get
one.

WHAT IS EMBEDDED AND WHAT CAN GO MISSING

Banners, icons and the title face are committed, so they are always there and are inlined. The
sculpts come from `generated/figure_player_<seat>_<px>.png`, which `make_tray_figures.py` renders
DOWN from the full-resolution originals -- git-ignored debug input, so a fresh clone has none of
it and a missing size costs that size rather than the page.

The action icons are this project's own primitives, not a third-party set, so nothing here adds
an attribution obligation. THE CITY HAS NO ACTION ICON and that is a fact about the duty rather
than a missing file; the page says so on the tile.

THREE SEATS ON PURPOSE

The sculpt work is being judged for a three-player game on a laptop, which is where the vertical
budget actually binds. Adding a fourth seat here would change what the page is for without
answering the question it was built to ask.
"""

import argparse
import base64
import io
import json
import pathlib
import re
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "duty_board_check.html"

sys.path.insert(0, str(ROOT / "ui" / "render"))
import gen_duty_grid as dg                                          # noqa: E402

try:
    from PIL import Image as _Img
except ModuleNotFoundError:                                         # pragma: no cover
    _Img = None

GROUND = "#17130d"

# The nine duties in artwork order, straight from the module that owns the identity. Read rather
# than copied: renaming a duty there must not leave this page captioning the old name.
NAMES = list(getattr(dg, "DUTY_NAMES", []))

# Which banner art wears which duty name. The same mapping the concept browser uses -- the
# titles are NOT in the art, so this is a pairing of parchment to name and nothing more.
BANNER_ORDER = (1, 5, 8, 3, 9, 4, 7, 6, 2)
BANNER_DIR = ROOT / "ui" / "assets-gothic" / "banners"
BANNER_FONT = ROOT / "ui" / "assets" / "fonts" / "PirataOne-Regular.ttf"
BANNER_RASTER = 420          # the art is 2172 px and draws near 300; embedding it whole is waste
BANNER_TOP = 0.502           # of the banner's own height: where the parchment's middle sits
BANNER_FS = 29.0 / 64.0      # font size as a fraction of banner height
BANNER_TRACK = 0.025         # letter-spacing, em
BANNER_INK = "#201b17"

ICON_DIR = ROOT / "ui" / "assets" / "icons" / "actions"
# Slugs in DUTY_NAMES order, so ICONS[i] belongs to NAMES[i]. `city` is here and expected to
# match nothing: The City has no action of its own.
SLUGS = ("allocation", "clerical", "construct", "build_roads", "city",
         "ordination", "produce", "taxation", "give_alms")

FIGURE_DIR = HERE / "generated"
FIGURE_SIZES = (90, 120, 150)
FIGURE_SEATS = (1, 2, 3)

# Formation defaults, in real device pixels. Starting points for the sliders rather than
# answers -- what they should be is the question the page exists to ask.
DEFAULTS = {"spread": 44, "back": 12, "rank": 30, "shade": 45, "size": 120}


def shapes():
    """Every distinct split of a total of 1..5 across three seats, ascending by total.

    Distinct means up to WHICH seat holds which count: the seating rule assigns colours later,
    so 2+1+1 is one picture, not three. Returned sorted descending within a shape, which is also
    the order `grouped` will lay them out in.
    """
    out = []
    for total in range(1, 6):
        seen = set()
        for a in range(total + 1):
            for b in range(total - a + 1):
                c = total - a - b
                part = tuple(sorted((a, b, c), reverse=True))
                if part in seen:
                    continue
                seen.add(part)
                out.append([v for v in part if v > 0])
    return out


def queues(shape):
    """The two seating rules, as the order seats take slots from left to right.

    Slots always fill left to right in both, so the ONLY thing that differs is the order of
    seats in the queue -- anything the page shows differing between the two is the rule's doing
    and not the geometry's.

        grouped  a player's sculpts are consecutive        p1 p1 p2 p3
        arrival  seats take turns as they place            p1 p2 p3 p1
    """
    grouped = []
    for seat, count in enumerate(shape):
        grouped.extend([seat] * count)
    arrival, left = [], list(shape)
    while len(arrival) < sum(shape):
        for seat, count in enumerate(left):
            if count > 0:
                arrival.append(seat)
                left[seat] -= 1
    return {"grouped": grouped, "arrival": arrival}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--figures", default=None,
                    help="folder holding figure_player_<seat>_<px>.png (default: %s)"
                         % FIGURE_DIR.relative_to(ROOT))
    ap.add_argument("--open", action="store_true", help="open the page when it is written")
    args = ap.parse_args()

    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    fig_dir = pathlib.Path(args.figures).expanduser() if args.figures else FIGURE_DIR
    notes = []

    assert len(NAMES) == 9, "expected nine duty names from gen_duty_grid, got %d" % len(NAMES)
    assert len(SLUGS) == len(NAMES), "slug table and duty names have drifted apart"

    # ---- the shape table, built here so the page displays rather than derives ----------------
    SHAPES = [{"parts": s, "total": sum(s), "queues": queues(s)} for s in shapes()]
    assert len(SHAPES) == 15, "expected 15 distinct shapes, got %d" % len(SHAPES)

    # ---- banners -----------------------------------------------------------------------------
    banners, font_uri = [], ""
    if not BANNER_FONT.is_file():
        notes.append("%s is missing, so titles would fall back to a serif -- banners left out"
                     % BANNER_FONT.name)
    elif _Img is None:
        notes.append("Pillow is not installed, so the banner art cannot be downscaled for "
                     "embedding -- banners left out (pip3 install --user Pillow)")
    else:
        font_uri = "data:font/ttf;base64," + base64.b64encode(
            BANNER_FONT.read_bytes()).decode("ascii")
        for n in BANNER_ORDER:
            path = BANNER_DIR / ("duty_banner_%02d.png" % n)
            if not path.is_file():
                notes.append("%s is missing -- banners left out" % path.name)
                banners = []
                break
            im = _Img.open(path).convert("RGBA")
            # Already premultiplied-clean, so a straight resize is safe here and the alpha rides
            # along; the separate-channel path is for art that is not.
            k = BANNER_RASTER / im.width
            small = im.resize((BANNER_RASTER, max(1, round(im.height * k))), _Img.LANCZOS)
            buf = io.BytesIO()
            small.save(buf, "WEBP", quality=86, method=6)
            banners.append("data:image/webp;base64,"
                           + base64.b64encode(buf.getvalue()).decode("ascii"))

    # ---- action icons --------------------------------------------------------------------
    icons = []
    for slug in SLUGS:
        found = sorted(ICON_DIR.glob("%s_*.svg" % slug))
        icons.append([p.read_text(encoding="utf-8").strip() for p in found])
    if not any(icons):
        notes.append("no action icons found under %s" % ICON_DIR.relative_to(ROOT))

    # ---- sculpts -----------------------------------------------------------------------------
    figs = {}
    # THE CAUSE IS CHECKED BEFORE THE SYMPTOM. Inside the loop, a missing Pillow looked exactly
    # like missing art -- every file present, no per-size note, and a summary telling you to run
    # make_tray_figures.py, which would not have helped. An error naming the wrong cause has
    # already cost this project a CI run.
    if _Img is None:
        notes.append("Pillow is not installed, so the sculpts cannot be re-encoded for "
                     "embedding -- no sculpts on the page (pip3 install --user Pillow)")
    else:
        for px in FIGURE_SIZES:
            row = []
            for seat in FIGURE_SEATS:
                path = fig_dir / ("figure_player_%d_%d.png" % (seat, px))
                if not path.is_file():
                    notes.append("%3d px  missing %s, size left out" % (px, path.name))
                    row = []
                    break
                im = _Img.open(path).convert("RGBA")
                buf = io.BytesIO()
                # LOSSLESS. These are the true-size reference the whole page is built to judge;
                # a lossy re-encode would put its artefacts on the thing being looked at. The
                # art is small enough that it costs little. (`quality` is ignored when lossless,
                # so it is not passed -- carrying one would only suggest it did something.)
                im.save(buf, "WEBP", method=6, lossless=True)
                row.append({"uri": "data:image/webp;base64,"
                                   + base64.b64encode(buf.getvalue()).decode("ascii"),
                            "w": im.width, "h": im.height})
            if row:
                figs[str(px)] = row
        if not figs:
            notes.append("no sculpts embedded -- run tools/ui_debug/make_tray_figures.py "
                         "first; the page still builds and shows the tiles empty")

    # ---- assemble ----------------------------------------------------------------------------
    page = ((HERE / "duty_board_check.html.tmpl").read_text(encoding="utf-8")
            .replace("__GROUND__", GROUND)
            # RAW, not JSON-quoted: this one lands inside a CSS url(), not in a script. With no
            # font it becomes an empty url() -- an invalid @font-face src, which is exactly the
            # right failure: the face never loads and the titles fall back rather than the page
            # breaking.
            .replace("__FONTURI_CSS__", font_uri)
            .replace("__BANNERS__", json.dumps(banners))
            .replace("__NAMES__", json.dumps(NAMES))
            .replace("__ICONS__", json.dumps(icons))
            .replace("__FIGS__", json.dumps(figs))
            .replace("__SHAPES__", json.dumps(SHAPES))
            .replace("__SIZES__", json.dumps(list(FIGURE_SIZES)))
            .replace("__BANNERTOP__", json.dumps(BANNER_TOP))
            .replace("__BANNERFS__", json.dumps(BANNER_FS))
            .replace("__BANNERTRACK__", json.dumps(BANNER_TRACK))
            .replace("__BANNERINK__", json.dumps(BANNER_INK))
            .replace("__DEFAULTS__", json.dumps(DEFAULTS)))
    left = re.findall(r"__[A-Z_]+__", page)
    assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    print("  %d shapes, %d of them telling the seating rules apart"
          % (len(SHAPES), sum(1 for s in SHAPES
                              if s["queues"]["grouped"] != s["queues"]["arrival"])))
    print("  sculpts %s  ·  banners %d  ·  icons %d across %d duties"
          % (", ".join(sorted(figs, key=int)) or "none", len(banners),
             sum(len(i) for i in icons), sum(1 for i in icons if i)))
    for note in notes:
        print("  %s" % note)
    if args.open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
