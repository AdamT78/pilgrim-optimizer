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
FIGURE_SIZES = (90, 120, 150, 180, 210)
FIGURE_SEATS = (1, 2, 3)

# THE ARRANGEMENT RULES LIVE IN A FILE, NOT HERE.
#
# ONE SET OF NUMBERS, USED AT EVERY SIZE. They were per size for a while, scaled so the
# arrangement held still as the sculpt grew -- but the working size is 210 and only 210, so a
# table of five was four rows of upkeep for sizes nobody tunes against. The consequence is worth
# naming rather than discovering: a spread of 77 is nearly twice a 90 px figure's own width, so
# the small sizes stand well apart. They are there to glance at, not to judge.
#
# Kept as data for the same reason configs/board.json is: a rule that outlives a session and is
# read by more than one thing has no business being a constant in one of them.
PLACEMENT = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_placement.json"

# The drawing rules -- formation, seat order and the depth cue -- inlined into the page.
# One copy, shared with the placement sheet.
RULES_JS = HERE / "duty_sculpt_rules.js"

# Only if the file is missing. A page built from these instead of from the file would look right
# and be wrong, so it says so in the run output rather than quietly standing in.
FALLBACK = {"tuned_at": 210, "spread": 77, "back": 21, "rank": 52, "order": "grouped",
            "frame": {"w": 320, "h": 390, "drop": 40},
            "mark": "floor", "depth": {"mode": "haze", "amount": 60, "full_at": 52}}


# The nine positions as a compass, so a wheel drawn from this reads as the ring on the board.
# The artwork order is an IDENTITY and not a position: laying a wheel out in it draws a ring
# that wanders.
GRID = ("north_west", "north", "north_east",
        "west", "city", "east",
        "south_west", "south", "south_east")

# Which duty sits where, taken from a committed scenario rather than from the model. Everything
# under tools/ui_debug is a derived view: it reads data and draws it, and a game config is the
# source of truth for any real game value a view shows.
SETUP = ROOT / "configs" / "setups" / "basic_mancala_sandbox.json"


def duty_at():
    """Position to duty slug, from the sandbox scenario. One deal, not the deal."""
    if not SETUP.is_file():
        raise SystemExit("%s is missing -- there is no duty to put on a tile" % _short(SETUP))
    tiles = dict((json.loads(SETUP.read_text(encoding="utf-8")) or {}).get("duty_tiles") or {})
    if not tiles:
        raise SystemExit("%s carries no duty_tiles" % _short(SETUP))
    tiles["city"] = "city"
    return tiles


def tiles(notes):
    """The nine tiles in compass order, each with its parchment and its title.

    Parchment and title are looked up by the duty's SLUG, so a page cannot pair a name with
    somebody else's banner even if the compass or the layout changes.
    """
    art, font_uri = banners(notes)
    at = duty_at()
    out = []
    for pos in GRID:
        slug = at.get(pos)
        if slug not in SLUGS:
            raise SystemExit("position %s carries duty %r, which is not in the slug table"
                             % (pos, slug))
        i = SLUGS.index(slug)
        out.append({"pos": pos, "slug": slug, "title": NAMES[i],
                    "ban": art[i] if art else ""})
    return out, font_uri


# THE GROUND PLATES. A layer, not a tile face: the duty-tiles tree holds the opaque face of the
# wheel, and a plate is a transparent cut-out drawn over it and under the figures.
#
# The plates are DISCOVERED rather than listed. What art exists is a fact about the folder, and a
# list would be a second place for it to be wrong; which duty gets which is a decision, and that
# is what the metadata file carries.
GROUNDS_DIR = ROOT / "ui" / "assets-gothic" / "grounds"
GROUND_PLAN = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_grounds.json"
GROUND_RASTER = 520      # drawn near 320 real px wide; this leaves room and costs little


def _short(path):
    """Repo-relative when it can be, absolute when it cannot.

    `relative_to` RAISES for a path outside the tree, so using it directly in an error message
    means the message itself blows up -- and the operator sees a ValueError about subpaths
    instead of the thing that was actually wrong with their file.
    """
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def placement(notes):
    """The arrangement rules, checked hard enough that a typo cannot reach a page silently."""
    if not PLACEMENT.is_file():
        notes.append("%s is missing -- built from the fallback, which may not be what you tuned"
                     % _short(PLACEMENT))
        return dict(FALLBACK)
    data = json.loads(PLACEMENT.read_text(encoding="utf-8"))
    for key in ("spread", "back", "rank"):
        if key not in data:
            raise SystemExit("%s has no %s -- the arrangement cannot be drawn without it"
                             % (_short(PLACEMENT), key))
        if not isinstance(data[key], int) or isinstance(data[key], bool) or data[key] < 0:
            raise SystemExit("%s: %s is %r -- want a non-negative whole number of real device "
                             "pixels" % (_short(PLACEMENT), key, data[key]))
    # WHICH SIZES ARE ON OFFER, not which sizes have their own numbers. There is still exactly
    # one spread, one set-back and one rank gap, used at every size -- this list only says which
    # sculpt sizes a page should put a button on. A per-size TABLE is the thing that was taken
    # out and is not coming back: it was four rows of upkeep for sizes nobody tunes against.
    if "sizes" in data:
        sizes = data["sizes"]
        if not isinstance(sizes, list) or not sizes:
            raise SystemExit("%s: sizes is %r, want a non-empty list of sculpt sizes"
                             % (_short(PLACEMENT), sizes))
        for px in sizes:
            if isinstance(px, bool) or not isinstance(px, int) or px <= 0:
                raise SystemExit("%s: sizes holds %r, want positive whole numbers of pixels"
                                 % (_short(PLACEMENT), px))
        if len(set(sizes)) != len(sizes):
            raise SystemExit("%s: sizes repeats a value (%r) -- one button each"
                             % (_short(PLACEMENT), sizes))
    if data.get("order") not in ("grouped", "arrival"):
        raise SystemExit("%s: order is %r, want 'grouped' or 'arrival'"
                         % (_short(PLACEMENT), data.get("order")))
    if data.get("mark") not in ("floor", "foot", "box", "gild"):
        raise SystemExit("%s: mark is %r, want floor, foot, box or gild"
                         % (_short(PLACEMENT), data.get("mark")))
    # THE FRAME IS NOT DERIVED FROM THE FORMATION, and that is the decision rather than an
    # oversight: art is drawn to a fixed rectangle. `drop` may be negative, because a frame
    # whose base sits ABOVE the floor line is a legitimate thing to want to try.
    frame = data.get("frame")
    if frame is not None:
        if not isinstance(frame, dict):
            raise SystemExit("%s: frame is %r, want an object with w, h and drop"
                             % (_short(PLACEMENT), frame))
        for key in ("w", "h"):
            value = frame.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SystemExit("%s: frame.%s is %r, want a positive whole number of real "
                                 "device pixels" % (_short(PLACEMENT), key, value))
        drop = frame.get("drop", 0)
        if isinstance(drop, bool) or not isinstance(drop, int):
            raise SystemExit("%s: frame.drop is %r, want a whole number of real device pixels "
                             "(negative lifts the frame off the floor)"
                             % (_short(PLACEMENT), drop))
    depth = data.get("depth") or {}
    if depth.get("mode") not in ("haze", "dark", "off"):
        raise SystemExit("%s: depth.mode is %r, want haze, dark or off"
                         % (_short(PLACEMENT), depth.get("mode")))
    if not isinstance(depth.get("amount"), int) or not 0 <= depth["amount"] <= 100:
        raise SystemExit("%s: depth.amount is %r, want a whole number 0-100"
                         % (_short(PLACEMENT), depth.get("amount")))
    # full_at is the e-fold distance of the cue. Zero would divide the depth by nothing and send
    # every figure straight to full haze, so it has to be a real distance.
    if not isinstance(depth.get("full_at"), int) or depth["full_at"] <= 0:
        raise SystemExit("%s: depth.full_at is %r, want a positive whole number of real device "
                         "pixels" % (_short(PLACEMENT), depth.get("full_at")))
    return data


DEFAULTS = {"size": 210}


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


def ground_plan(notes):
    """Which duty stands on which plate, and how each plate is toned down.

    Checked the same way the placement file is -- a typo here draws a tile with no ground and
    no explanation, which looks like missing art rather than a bad key.
    """
    if not GROUND_PLAN.is_file():
        notes.append("%s is missing -- no grounds will be drawn" % _short(GROUND_PLAN))
        return {"default": "", "by_duty": {}, "grounds": {}}
    data = json.loads(GROUND_PLAN.read_text(encoding="utf-8"))
    grounds = data.get("grounds") or {}
    if not isinstance(grounds, dict):
        raise SystemExit("%s: grounds is %r, want an object keyed by plate name"
                         % (_short(GROUND_PLAN), grounds))
    for name, g in grounds.items():
        for key, lo, hi in (("anchor", 0, 100), ("scale", 1, 300),
                            ("dim", 0, 100), ("saturate", 0, 100), ("opacity", 0, 100)):
            value = g.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise SystemExit("%s: grounds.%s.%s is %r, want a whole number %d-%d"
                                 % (_short(GROUND_PLAN), name, key, value, lo, hi))
    by_duty = data.get("by_duty") or {}
    for slug, name in by_duty.items():
        if slug not in SLUGS:
            raise SystemExit("%s: by_duty has %r, which is not a duty slug"
                             % (_short(GROUND_PLAN), slug))
        if name and name not in grounds:
            raise SystemExit("%s: %s is assigned %r, which has no entry under grounds"
                             % (_short(GROUND_PLAN), slug, name))
    return data


def ground_art(notes):
    """Every plate in the grounds folder, downscaled and inlined.

    Discovered, so dropping a PNG in the folder is all it takes to be able to pick it. A plate
    with no entry in the plan still appears -- it simply carries the defaults until you tune it,
    which is the difference between a new asset and a broken one.
    """
    art = {}
    if _Img is None:
        notes.append("Pillow is not installed, so the ground plates cannot be embedded")
        return art
    if not GROUNDS_DIR.is_dir():
        notes.append("%s does not exist -- no ground plates to offer" % _short(GROUNDS_DIR))
        return art
    for path in sorted(GROUNDS_DIR.glob("*.png")):
        im = _Img.open(path).convert("RGBA")
        box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if box is None:
            notes.append("%s is fully transparent -- skipped" % path.name)
            continue
        im = im.crop(box)
        k = min(1.0, GROUND_RASTER / im.width)
        small = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))),
                          _Img.LANCZOS)
        buf = io.BytesIO()
        small.save(buf, "WEBP", quality=88, method=6)
        # The widest row is where the plate is at its broadest, which is the best guess at its
        # standing line for a plate nobody has tuned yet.
        rows = [sum(1 for x in range(small.width) if small.getpixel((x, y))[3] > 8)
                for y in range(small.height)]
        widest = rows.index(max(rows)) if rows else 0
        art[path.stem] = {"uri": "data:image/webp;base64,"
                                 + base64.b64encode(buf.getvalue()).decode("ascii"),
                          "w": small.width, "h": small.height,
                          "widest": round(100 * widest / max(1, small.height))}
    if not art:
        notes.append("no ground plates found under %s" % _short(GROUNDS_DIR))
    return art


def ground_check(plan, plates, notes):
    """Cross the plan against the folder, and say which plates are actually in use.

    `ground_plan` checks the plan against ITSELF -- that every duty is assigned something the
    plan also tunes -- and `ground_art` discovers whatever PNGs happen to exist. Neither asks the
    question that bites: does the plate this duty is assigned have a PICTURE? A name with no art
    draws nothing and says nothing, which on screen is indistinguishable from a duty nobody has
    assigned yet.

    Returns the plate names in use, so every page that draws grounds prints the same line rather
    than each summarising the same two files its own way.
    """
    by_duty = plan.get("by_duty") or {}
    in_use, missing = [], []
    for slug in SLUGS:
        name = by_duty.get(slug, plan.get("default") or "")
        if not name:
            continue
        if name not in plates:
            missing.append((slug, name))
        elif name not in in_use:
            in_use.append(name)
    for slug, name in missing:
        notes.append("%s is assigned %r, which has no art in %s -- that tile draws a bare floor"
                     % (slug, name, _short(GROUNDS_DIR)))
    spare = sorted(n for n in plates if n not in in_use)
    if spare:
        notes.append("%d plate(s) in %s that no duty stands on: %s"
                     % (len(spare), GROUNDS_DIR.name, ", ".join(spare)))
    return sorted(in_use)


def figures(fig_dir, notes):
    """Every sculpt size that has art, inlined. Shared with generate_placement_sheet.py.

    Extracted rather than copied: this function is where "never upscale", "lossless because
    these are the true-size reference" and "name the cause, not the symptom" live, and a second
    copy is how those three quietly drift apart.
    """
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
    return figs


def banners(notes):
    """The nine parchments and the face that letters them, inlined. Shared with the sow page.

    Extracted for the same reason `figures()` was: the sow page needs the identical pairing of
    parchment to duty name, and a second copy would be a second place for BANNER_ORDER to be
    wrong in. Returns ([], "") rather than raising when the art or the font is absent -- a page
    with no banners is still worth looking at, and the note says which.
    """
    art, font_uri = [], ""
    if not BANNER_FONT.is_file():
        notes.append("%s is missing, so titles would fall back to a serif -- banners left out"
                     % BANNER_FONT.name)
        return art, font_uri
    if _Img is None:
        notes.append("Pillow is not installed, so the banner art cannot be downscaled for "
                     "embedding -- banners left out (pip3 install --user Pillow)")
        return art, font_uri
    font_uri = "data:font/ttf;base64," + base64.b64encode(
        BANNER_FONT.read_bytes()).decode("ascii")
    for n in BANNER_ORDER:
        path = BANNER_DIR / ("duty_banner_%02d.png" % n)
        if not path.is_file():
            notes.append("%s is missing -- banners left out" % path.name)
            return [], font_uri
        im = _Img.open(path).convert("RGBA")
        # Already premultiplied-clean, so a straight resize is safe here and the alpha rides
        # along; the separate-channel path is for art that is not.
        k = BANNER_RASTER / im.width
        small = im.resize((BANNER_RASTER, max(1, round(im.height * k))), _Img.LANCZOS)
        buf = io.BytesIO()
        small.save(buf, "WEBP", quality=86, method=6)
        art.append("data:image/webp;base64,"
                   + base64.b64encode(buf.getvalue()).decode("ascii"))
    return art, font_uri


def show(target, wanted):
    """Say where the page is, and open it unless told not to.

    THE URL IS PRINTED EVERY TIME, opened or not. A tool whose output you have to reconstruct
    from a relative path is a tool you stop using, and in a terminal the line below is clickable.

    `webbrowser.open` RETURNS FALSE when it cannot find a browser to launch, and every caller
    here used to throw that away -- so a machine with no browser looked exactly like a tool that
    had quietly decided not to open anything.
    """
    url = target if isinstance(target, str) else target.resolve().as_uri()
    print("  %s" % url)
    if not wanted:
        return
    if not webbrowser.open(url):
        print("  (nothing here could launch a browser -- open the line above yourself)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--figures", default=None,
                    help="folder holding figure_player_<seat>_<px>.png (default: %s)"
                         % FIGURE_DIR.relative_to(ROOT))
    # OPENING IS THE DEFAULT. These pages exist to be looked at; a run that writes one and says
    # nothing is a run you have to follow with a second command, and the flag was easy to forget.
    # `--open` is still accepted so it stays in anyone's fingers and in any note that mentions it.
    ap.add_argument("--open", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--no-open", dest="open", action="store_false",
                    help="write the page without opening it")
    args = ap.parse_args()

    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    fig_dir = pathlib.Path(args.figures).expanduser() if args.figures else FIGURE_DIR
    notes = []
    PLACE = placement(notes)

    assert len(NAMES) == 9, "expected nine duty names from gen_duty_grid, got %d" % len(NAMES)
    assert len(SLUGS) == len(NAMES), "slug table and duty names have drifted apart"

    # ---- the shape table, built here so the page displays rather than derives ----------------
    SHAPES = [{"parts": s, "total": sum(s), "queues": queues(s)} for s in shapes()]
    assert len(SHAPES) == 15, "expected 15 distinct shapes, got %d" % len(SHAPES)

    # ---- banners -----------------------------------------------------------------------------
    banner_art, font_uri = banners(notes)

    # ---- action icons --------------------------------------------------------------------
    icons = []
    for slug in SLUGS:
        found = sorted(ICON_DIR.glob("%s_*.svg" % slug))
        icons.append([p.read_text(encoding="utf-8").strip() for p in found])
    if not any(icons):
        notes.append("no action icons found under %s" % ICON_DIR.relative_to(ROOT))

    # ---- sculpts -----------------------------------------------------------------------------
    figs = figures(fig_dir, notes)

    # NAMED, NOT TRACEBACKED. Without this the run died on a bare FileNotFoundError from inside
    # the template substitution, which says where Python gave up rather than what is missing --
    # and this file is the one most likely to be absent, because it is the newest.
    if not RULES_JS.is_file():
        raise SystemExit("%s is missing -- it is where the drawing rules live"
                         % _short(RULES_JS))

    # ---- assemble ----------------------------------------------------------------------------
    page = ((HERE / "duty_board_check.html.tmpl").read_text(encoding="utf-8")
            .replace("__GROUND__", GROUND)
            # RAW, not JSON-quoted: this one lands inside a CSS url(), not in a script. With no
            # font it becomes an empty url() -- an invalid @font-face src, which is exactly the
            # right failure: the face never loads and the titles fall back rather than the page
            # breaking.
            .replace("__FONTURI_CSS__", font_uri)
            .replace("__BANNERS__", json.dumps(banner_art))
            .replace("__NAMES__", json.dumps(NAMES))
            .replace("__ICONS__", json.dumps(icons))
            .replace("__FIGS__", json.dumps(figs))
            .replace("__SHAPES__", json.dumps(SHAPES))
            .replace("__SIZES__", json.dumps(list(FIGURE_SIZES)))
            .replace("__BANNERTOP__", json.dumps(BANNER_TOP))
            .replace("__BANNERFS__", json.dumps(BANNER_FS))
            .replace("__BANNERTRACK__", json.dumps(BANNER_TRACK))
            .replace("__BANNERINK__", json.dumps(BANNER_INK))
            .replace("__DEFAULTS__", json.dumps(DEFAULTS))
            .replace("__PLACEMENT__", json.dumps(PLACE))
            .replace("__FORMATION__", RULES_JS.read_text(encoding="utf-8")))
    left = re.findall(r"__[A-Z_]+__", page)
    assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    print("  %d shapes, %d of them telling the seating rules apart"
          % (len(SHAPES), sum(1 for s in SHAPES
                              if s["queues"]["grouped"] != s["queues"]["arrival"])))
    print("  placement from %s: spread %d, set-back %d, rank gap %d  (tuned at %s px, used at "
          "every size)" % (PLACEMENT.name, PLACE["spread"], PLACE["back"], PLACE["rank"],
                           PLACE.get("tuned_at", "?")))
    print("  order %s  ·  mark %s  ·  depth %s %d%%"
          % (PLACE["order"], PLACE["mark"], PLACE["depth"]["mode"], PLACE["depth"]["amount"]))
    print("  sculpts %s  ·  banners %d  ·  icons %d across %d duties"
          % (", ".join(sorted(figs, key=int)) or "none", len(banner_art),
             sum(len(i) for i in icons), sum(1 for i in icons if i)))
    for note in notes:
        print("  %s" % note)
    show(out, args.open)


if __name__ == "__main__":
    main()
