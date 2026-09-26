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
sculpts come from `generated/figure_player_<seat>_p<pose>_<px>_<label>.png`, which
`make_tray_figures.py` renders DOWN from the full-resolution originals -- git-ignored debug
input, so a fresh clone has none of it and a missing set costs that set rather than the page.

A SET IS NAMED, NOT MEASURED. `210_plastic` and `210_painted` are both 210 px tall and are not
the same art, so the pixel height stopped being enough to say which sculpts are on screen. What
the pages switch between is a LABEL -- `<px>_<kind>` -- and the pixel height is a fact about the
label rather than the identity of it. The sets are discovered from the folder rather than
declared here: a second copy of make_tray_figures.py's kind table is how the two drift apart.

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
import copy
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
FIGURE_SEATS = (1, 2, 3)

# figure_player_<seat>_p<pose>_<px>_<label>.png, written by make_tray_figures.py. The set label a
# page shows is the last two fields joined -- `210_painted` -- so the px stays readable off the
# front of it without a second table saying which labels exist.
FIGURE_NAME = re.compile(r"^figure_player_(\d+)_p(\d+)_(\d+)_([a-z][a-z0-9_]*)\.png$")


def set_px(label):
    """The pixel height behind a set label. `210_painted` -> 210."""
    return int(str(label).split("_", 1)[0])


def set_sort(label):
    """Sets in a settled order: by height, then by name. Used wherever buttons are laid out."""
    text = str(label)
    head, _, tail = text.partition("_")
    return (int(head) if head.isdigit() else 0, tail, text)

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

# How a marked tile is lit: the catalogue of effects a `mark` may name, beside the floor styles
# the sow draws in geometry. Its own file rather than a section of duty_placement.json because an
# effect is not a fact about how sculpts stand -- it may yet mark a seat or a whole tile rather
# than a plate -- and not a section of duty_grounds.json because it is not a fact about a piece
# of art either. What it IS a fact about is how the board reads, which is a third thing.
EFFECTS = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_effects.json"

# The drawing rules -- formation, seat order and the depth cue -- inlined into the page.
# One copy, shared with the placement sheet.
RULES_JS = HERE / "duty_sculpt_rules.js"

# The marking technique -- the blend group, the pulse, the plate markup itself -- inlined into
# every page that draws a marked tile. One copy, for the same reason RULES_JS is one copy.
MARK_JS = HERE / "duty_mark_rules.js"

# Only if the file is missing. A page built from these instead of from the file would look right
# and be wrong, so it says so in the run output rather than quietly standing in.
FALLBACK = {"tuned_at": "210_plastic", "spread": 77, "back": 21, "rank": 52, "order": "grouped",
            "width_across_ranks": False,
            "frame": {"w": 320, "h": 390, "drop": 40},
            "marks": {"route": "floor"},
            "depth": {"mode": "haze", "amount": 60, "full_at": 52}}


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


def duty_at(layout=None):
    """Position to duty slug. One deal, not the deal -- so a caller showing a REAL deal says so.

    `layout` is a position-name to duty-slug map from whoever knows which deal is on screen.
    The sow passes the one recorded beside its engine offers, because a page whose lit tiles
    come from one deal and whose banners come from another is wrong in a way that looks fine:
    every tile carries a real duty and a real plate, just not the ones belonging to the
    position it is standing on.

    THAT IS NOT HYPOTHETICAL. Measured 2026-09-26: the sandbox layout and the recorded
    kogge_and_cloisters_2p layout differ at six of eight positions, and the page had been
    drawing one over the other since the offers were recorded. The lit sets were right, which
    is exactly why nobody noticed.

    With no layout given, the sandbox setup stands in -- the right answer for the board check
    and the placement sheet, which show no game state at all.
    """
    if layout:
        tiles = dict(layout)
        tiles["city"] = "city"
        return tiles
    if not SETUP.is_file():
        raise SystemExit("%s is missing -- there is no duty to put on a tile" % _short(SETUP))
    tiles = dict((json.loads(SETUP.read_text(encoding="utf-8")) or {}).get("duty_tiles") or {})
    if not tiles:
        raise SystemExit("%s carries no duty_tiles" % _short(SETUP))
    tiles["city"] = "city"
    return tiles


def tiles(notes, layout=None):
    """The nine tiles in compass order, each with its parchment and its title.

    Parchment and title are looked up by the duty's SLUG, so a page cannot pair a name with
    somebody else's banner even if the compass or the layout changes. The ground plates are
    keyed by slug too -- `by_duty` in duty_grounds.json -- so a duty that moves takes its
    plate with it and nothing has to be re-tuned when the deal changes.
    """
    art, font_uri = banners(notes)
    at = duty_at(layout)
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


# WHICH NUMBERS A SET MAY CARRY ITS OWN OF. These are the sliders; `order` and `mark` are
# switches and stay global, because grouped-versus-arrival and which floor mark is drawn are
# conventions about reading a tile rather than facts about how big the sculpts are.
PER_SET_KEYS = ("spread", "back", "rank", "frame", "depth", "width_across_ranks")


def _check_geometry(data, where, required):
    """Validate the arrangement numbers, whether they are the base or one set's override.

    ONE FUNCTION FOR BOTH, which is the point: an override reaching a page unchecked would be a
    typo that draws rather than a typo that stops, and a second copy of these rules would agree
    on the day it was written. `required` is the only difference -- the base must name every
    number, an override names only what it changes.

    An override carries WHOLE VALUES. A `frame` with only `w` in it, or a `depth` with only
    `full_at`, is refused rather than half-merged: a half-frame has no meaning, and guessing
    which half was meant is how a file ends up with a shape nobody wrote.
    """
    for key in ("spread", "back", "rank"):
        if key not in data:
            if required:
                raise SystemExit("%s has no %s -- the arrangement cannot be drawn without it"
                                 % (where, key))
            continue
        if not isinstance(data[key], int) or isinstance(data[key], bool) or data[key] < 0:
            raise SystemExit("%s: %s is %r -- want a non-negative whole number of real device "
                             "pixels" % (where, key, data[key]))
    # THE FRAME IS NOT DERIVED FROM THE FORMATION, and that is the decision rather than an
    # oversight: art is drawn to a fixed rectangle. `drop` may be negative, because a frame
    # whose base sits ABOVE the floor line is a legitimate thing to want to try.
    frame = data.get("frame")
    if frame is not None:
        if not isinstance(frame, dict):
            raise SystemExit("%s: frame is %r, want an object with w, h and drop"
                             % (where, frame))
        for key in ("w", "h"):
            value = frame.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SystemExit("%s: frame.%s is %r, want a positive whole number of real "
                                 "device pixels" % (where, key, value))
        drop = frame.get("drop", 0)
        if isinstance(drop, bool) or not isinstance(drop, int):
            raise SystemExit("%s: frame.drop is %r, want a whole number of real device pixels "
                             "(negative lifts the frame off the floor)" % (where, drop))
    # WHAT `spread` MEASURES once there are two ranks. A look rather than a correctness
    # question, and one that depends on the ground plate under the figures -- a wide plate can
    # carry the spaced-out version, a narrow one puts the outer acolytes over its edge.
    wide = data.get("width_across_ranks")
    if wide is not None and not isinstance(wide, bool):
        raise SystemExit("%s: width_across_ranks is %r, want true or false -- it is the "
                         "placement sheet's checkbox, not a number" % (where, wide))
    depth = data.get("depth")
    if depth is None and not required:
        return
    depth = depth or {}
    if depth.get("mode") not in ("haze", "dark", "off"):
        raise SystemExit("%s: depth.mode is %r, want haze, dark or off"
                         % (where, depth.get("mode")))
    if not isinstance(depth.get("amount"), int) or not 0 <= depth["amount"] <= 100:
        raise SystemExit("%s: depth.amount is %r, want a whole number 0-100"
                         % (where, depth.get("amount")))
    # full_at is the e-fold distance of the cue. Zero would divide the depth by nothing and send
    # every figure straight to full haze, so it has to be a real distance.
    if not isinstance(depth.get("full_at"), int) or depth["full_at"] <= 0:
        raise SystemExit("%s: depth.full_at is %r, want a positive whole number of real device "
                         "pixels" % (where, depth.get("full_at")))


def settings_for(place, label):
    """The numbers one sculpt set is drawn with: the base, with that set's override laid over it.

    ONE RESOLVER, IN PYTHON, and the pages are handed the answer rather than the rule. They
    switch sets live, so each of them would otherwise need its own copy of this merge -- three
    copies of a two-line rule is still three places for it to stop agreeing, and the last time
    this project let a two-line rule live in three files the copies had already drifted.

    Whole values, not deep-merged: an override's `frame` replaces the base's frame entire. See
    _check_geometry for why half of one is refused rather than filled in.
    """
    out = {k: copy.deepcopy(place[k]) for k in PER_SET_KEYS if k in place}
    own = (place.get("per_set") or {}).get(label) or {}
    for key in PER_SET_KEYS:
        if key in own:
            out[key] = copy.deepcopy(own[key])
    return out


def placement(notes):
    """The arrangement rules, checked hard enough that a typo cannot reach a page silently."""
    if not PLACEMENT.is_file():
        notes.append("%s is missing -- built from the fallback, which may not be what you tuned"
                     % _short(PLACEMENT))
        return dict(FALLBACK)
    data = json.loads(PLACEMENT.read_text(encoding="utf-8"))
    _check_geometry(data, _short(PLACEMENT), required=True)
    # WHICH SETS ARE ON OFFER, not which sets have their own numbers -- those are `per_set`
    # below. This list only says which sculpt sets a page should put a button on.
    #
    # A LABEL, NOT A NUMBER, since `210_plastic` and `210_painted` are both 210. The pattern is
    # checked rather than the membership: which labels exist is a fact about the tray folder,
    # and a name this file cannot parse is the one mistake worth stopping for.
    if "sizes" in data:
        sizes = data["sizes"]
        if not isinstance(sizes, list) or not sizes:
            raise SystemExit("%s: sizes is %r, want a non-empty list of sculpt set labels"
                             % (_short(PLACEMENT), sizes))
        for label in sizes:
            if not isinstance(label, str) or not re.match(r"^\d+_[a-z][a-z0-9_]*$", label):
                raise SystemExit("%s: sizes holds %r, want labels like '210_painted' -- a pixel "
                                 "height, an underscore and the set's name"
                                 % (_short(PLACEMENT), label))
        if len(set(sizes)) != len(sizes):
            raise SystemExit("%s: sizes repeats a value (%r) -- one button each"
                             % (_short(PLACEMENT), sizes))
    # `tuned_at` names which set opens, so it is a label too. The numbers below it are still
    # tuned against 210 real px, which every set named so far happens to share.
    tuned = data.get("tuned_at")
    if tuned is not None and not (isinstance(tuned, str)
                                  and re.match(r"^\d+_[a-z][a-z0-9_]*$", tuned)):
        raise SystemExit("%s: tuned_at is %r, want a set label like '210_plastic'"
                         % (_short(PLACEMENT), tuned))
    if data.get("order") not in ("grouped", "arrival"):
        raise SystemExit("%s: order is %r, want 'grouped' or 'arrival'"
                         % (_short(PLACEMENT), data.get("order")))
    # A MARKING PER DECISION THE PLAYER IS BEING ASKED TO MAKE. This was one `mark` while the
    # only marked moment was the sow destination. It is a block rather than three sibling keys
    # because the keys are not free-form: they are the engine's own decision fields, so the
    # block can be checked against DECISION_FIELDS and a fourth marking is a row rather than
    # another top-level key.
    #
    # An absent field is not an error -- it means that decision is drawn unmarked, which is the
    # honest state for a decision no page can draw yet.
    marks = data.get("marks")
    if marks is None:
        marks = {}
    if not isinstance(marks, dict):
        raise SystemExit("%s: marks is %r, want an object keyed by decision"
                         % (_short(PLACEMENT), marks))
    stray = sorted(set(marks) - set(DECISION_FIELDS))
    if stray:
        raise SystemExit("%s: marks carries %s, which is not a decision the engine makes -- "
                         "a marking hangs on one of %s"
                         % (_short(PLACEMENT), ", ".join(stray), ", ".join(DECISION_FIELDS)))
    undrawable = sorted(set(marks) - set(DRAWABLE_DECISIONS))
    if undrawable:
        raise SystemExit("%s: marks carries %s, which the engine decides but no page can draw "
                         "yet -- storing a marking for it would be a setting nothing reads. Add "
                         "it to DRAWABLE_DECISIONS when there is a phase to show it on."
                         % (_short(PLACEMENT), ", ".join(undrawable)))
    effects = effects_plan([])
    for field in DECISION_FIELDS:
        if field in marks:
            check_mark(marks[field], effects, "%s: marks.%s" % (_short(PLACEMENT), field))
    data["marks"] = marks
    # `mark` WAS THIS KEY, singular, and meant the sow destination. Refused rather than migrated
    # quietly: a file still carrying it would load with that marking silently dropped.
    if "mark" in data:
        raise SystemExit("%s still carries `mark`, which became marks.route on 2026-09-26 when "
                         "there was more than one marked moment -- move its value there"
                         % _short(PLACEMENT))
    # ---- and each set that carries numbers of its own ------------------------------------
    per_set = data.get("per_set")
    if per_set is not None:
        if not isinstance(per_set, dict):
            raise SystemExit("%s: per_set is %r, want an object keyed by set label"
                             % (_short(PLACEMENT), per_set))
        for label, own in sorted(per_set.items()):
            where = "%s: per_set[%s]" % (_short(PLACEMENT), label)
            if not re.match(r"^\d+_[a-z][a-z0-9_]*$", str(label)):
                raise SystemExit("%s is not a set label like '210_painted'" % where)
            if not isinstance(own, dict):
                raise SystemExit("%s is %r, want an object of the numbers this set changes"
                                 % (where, own))
            # NAMED, NOT IGNORED. A key here that nothing reads is a number someone moved and
            # believes is in effect, which is worse than a number they know they cannot set.
            stray = sorted(set(own) - set(PER_SET_KEYS))
            if stray:
                raise SystemExit("%s carries %s, which a set cannot have its own of -- a set "
                                 "may name %s, and nothing else"
                                 % (where, ", ".join(stray), ", ".join(PER_SET_KEYS)))
            if not own:
                raise SystemExit("%s is empty -- a set with nothing of its own should not be "
                                 "listed at all, because an empty row reads as 'tuned to the "
                                 "base' when it means 'never tuned'" % where)
            _check_geometry(own, where, required=False)
    return data


DEFAULTS = {"size": "210_plastic"}


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


# ---- how a marked tile is lit -----------------------------------------------------------------
# THE DECISIONS A TURN IS MADE OF, in the order the engine settles them, and the only names a
# marking may be hung on. This mirrors DECIDED_FIELDS in tools/play_server.py, which in turn
# names fields of the engine's FullTurnAction -- so a marking is attached to a QUESTION THE
# ENGINE ASKS rather than to a phase somebody named in a stylesheet.
#
# Copied rather than imported on purpose: these tools run wherever the sculpts are rendered,
# which is Python 3.10 here, and the engine needs 3.12+. A test pins this tuple against the
# server's by reading it, so the copy cannot drift in silence.
DECISION_FIELDS = ("origin", "route", "selected_duty", "resolution")

# OF THOSE, THE ONES A PAGE CAN ACTUALLY DRAW. Two are out, for different reasons.
#
# `resolution` -- duty action or tithe -- is a decision about an already-chosen tile. Its values
# are not positions at all (14 names: allocation, taxation, tithe, produce_stone...), so there is
# nothing for a ground-tile marking to appear on, and a fourteenth colour on one tile would not
# be readable if there were.
#
# `selected_duty` IS a position and could be drawn, and briefly was. It is out because the sow
# page's job ends when the sow ends: choosing which duty to act on is the next phase, and a page
# that lights tiles for it is claiming to show a phase it does not run. The rule behind it, from
# the engine on 2026-09-26, is worth writing down where the next person looks --
# `ensure_selected_duty_has_acolyte(state_after_sow, ...)`: the city is not a duty position, and
# the tile must hold at least one of your acolytes ONCE THE SOW IS DONE. Not "where you just
# landed": measured over every legal turn, 190/190 and 1044/1044 satisfy the after-sow rule while
# only 76 and 470 are anywhere in the route.
#
# Both stay out of the sheet's rows and are refused in the file, for the reason the seven empty
# per_set blocks were dropped: a setting nothing reads is a decision nobody can check.
#
# WHAT IS RECORDED AND WHAT IS DRAWN ARE DIFFERENT QUESTIONS. The recording still carries every
# decision the engine offers, because that is a fact about the engine; this tuple says what THIS
# set of pages puts on screen. Moving a name in here is the whole job of turning a marking on.
DRAWABLE_DECISIONS = ("origin", "route")
# The four the sow draws in geometry. Anything else `mark` names has to be an effect in the
# catalogue, which is what lets an effect be added without touching this list.
FLOOR_MARKS = ("floor", "foot", "box", "gild")

# An effect's name. No colon, because the colon is the pulse modifier -- `amber:pulse` is the
# amber breathing, not a second effect, and a name containing one could not be told apart.
EFFECT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

# hsl() plus how far the colour is laid over the plate. Hue wraps at 360 rather than 100.
EFFECT_RANGES = (("hue", 0, 360), ("saturation", 0, 100),
                 ("lightness", 0, 100), ("strength", 0, 100))

# The breath. `speed` is milliseconds and has a floor: under about a tenth of a second a pulse
# stops reading as breathing and starts reading as a fault in the screen.
PULSE_RANGES = (("lo", 0, 100), ("hi", 0, 100), ("speed", 100, 20000))


def effects_plan(notes):
    """The catalogue of markings, checked the way the other two plans are.

    A typo here lights a tile in a colour nobody chose, or in none at all, which looks like a
    bug in the board rather than a bad key -- so it stops the load and says which entry.
    """
    if not EFFECTS.is_file():
        notes.append("%s is missing -- only the floor marks are on offer" % _short(EFFECTS))
        return {"effects": {}}
    data = json.loads(EFFECTS.read_text(encoding="utf-8"))
    fx = data.get("effects")
    if fx is None:
        fx = {}
    if not isinstance(fx, dict):
        raise SystemExit("%s: effects is %r, want an object keyed by effect name"
                         % (_short(EFFECTS), fx))
    for name, e in sorted(fx.items()):
        where = "%s: effects[%s]" % (_short(EFFECTS), name)
        if not EFFECT_NAME.match(str(name)):
            raise SystemExit("%s is not an effect name -- lowercase, digits and underscores, "
                             "and no colon: the colon is the pulse modifier" % where)
        # AN EFFECT MAY NOT TAKE A FLOOR MARK'S NAME. `mark` holds one string and is read as a
        # floor mark first, so an effect called `floor` could never be selected and the file
        # would look as though it were being ignored.
        if name in FLOOR_MARKS:
            raise SystemExit("%s takes the name of a floor mark, which `mark` reads first -- "
                             "this effect could never be chosen" % where)
        if not isinstance(e, dict):
            raise SystemExit("%s is %r, want an object of the effect's numbers" % (where, e))
        for key, lo, hi in EFFECT_RANGES:
            v = e.get(key)
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                raise SystemExit("%s.%s is %r, want a whole number %d-%d"
                                 % (where, key, v, lo, hi))
        stray = sorted(set(e) - {k for k, _, _ in EFFECT_RANGES} - {"pulse"})
        if stray:
            raise SystemExit("%s carries %s, which an effect has no use for -- an effect may "
                             "name %s and an optional pulse"
                             % (where, ", ".join(stray),
                                ", ".join(k for k, _, _ in EFFECT_RANGES)))
        pulse = e.get("pulse")
        if pulse is not None:
            if not isinstance(pulse, dict):
                raise SystemExit("%s.pulse is %r, want an object of lo, hi and speed"
                                 % (where, pulse))
            for key, lo, hi in PULSE_RANGES:
                v = pulse.get(key)
                if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                    raise SystemExit("%s.pulse.%s is %r, want a whole number %d-%d"
                                     % (where, key, v, lo, hi))
            stray = sorted(set(pulse) - {k for k, _, _ in PULSE_RANGES})
            if stray:
                raise SystemExit("%s.pulse carries %s, which a pulse has no use for"
                                 % (where, ", ".join(stray)))
    data["effects"] = fx
    return data


def _marks_sentence(place):
    """The markings, as one phrase, saying which decisions are drawn and which are not.

    A decision with no marking is NAMED rather than left out. A setting nothing reads is a
    decision nobody can check, and a summary that simply omits it is how it stays that way.
    """
    marks = place.get("marks") or {}
    said = ["%s %s" % (f, marks[f]) for f in DECISION_FIELDS if f in marks]
    bare = [f for f in DECISION_FIELDS if f not in marks]
    if bare:
        said.append("unmarked: " + ", ".join(bare))
    return "  \u00b7  ".join(said) if said else "nothing marked"


def check_mark(mark, effects, where):
    """That `mark` names something that can actually be drawn.

    The same guard as `by_duty` naming a plate with no entry under `grounds`, and it matters for
    the same reason: the page would draw nothing and say nothing, which reads as missing art.
    """
    base, _, modifier = str(mark if mark is not None else "").partition(":")
    known = (effects or {}).get("effects") or {}
    if base not in FLOOR_MARKS and base not in known:
        raise SystemExit("%s: mark is %r, which is neither a floor mark (%s) nor an effect in "
                         "%s (%s)"
                         % (where, mark, ", ".join(FLOOR_MARKS), _short(EFFECTS),
                            ", ".join(sorted(known)) or "none on file"))
    if modifier and modifier != "pulse":
        raise SystemExit("%s: mark is %r -- the only modifier is ':pulse'" % (where, mark))
    if modifier and base in FLOOR_MARKS:
        raise SystemExit("%s: mark is %r, but %s is a floor mark drawn in geometry and has "
                         "nothing to breathe with -- ':pulse' is for effects"
                         % (where, mark, base))
    # NAMING THE BREATH AN EFFECT CANNOT TAKE. Without this the page falls back to the solid
    # marking, which is a real marking, so the mistake shows up as "why is it not pulsing"
    # rather than as an error -- and the answer is in a different file.
    if modifier == "pulse" and not (known.get(base) or {}).get("pulse"):
        raise SystemExit("%s: mark is %r, but %s has no pulse block to breathe with -- give it "
                         "lo, hi and speed in %s, or drop the ':pulse'"
                         % (where, mark, base, _short(EFFECTS)))
    return base, modifier == "pulse"


# WHAT A SET MAY RESTAND. `by_duty` is deliberately absent: which duty stands on which plate is
# a fact about the board, not about how tall the sculpts are, and letting it split per set would
# let the same duty stand on two different grounds depending on which sculpts were loaded.
GROUND_PER_SET_KEYS = ("lift", "grounds")

# `opacity` LEFT THIS LIST ON 2026-09-26 and became one top-level `transparency`. It was per
# plate, which meant it was also per SET the moment a set carried plate rows of its own -- and
# the two sets that had been tuned kept opacity 100 while every set inheriting the base went to
# 50, so the sow's dropdown showed two of its own played sets at different transparencies with
# nothing on screen to say why. How solid the ground is is a fact about the board, like `lift`.
PLATE_RANGES = (("anchor", 0, 100), ("scale", 1, 300),
                ("dim", 0, 100), ("saturate", 0, 100))


def _check_plate(g, where):
    """One plate's row, wherever it came from -- the base grounds or a set's override."""
    if not isinstance(g, dict):
        raise SystemExit("%s is %r, want an object of the plate's settings" % (where, g))
    for key, lo, hi in PLATE_RANGES:
        value = g.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            raise SystemExit("%s.%s is %r, want a whole number %d-%d" % (where, key, value, lo, hi))


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
        _check_plate(g, "%s: grounds.%s" % (_short(GROUND_PLAN), name))
    by_duty = data.get("by_duty") or {}
    for slug, name in by_duty.items():
        if slug not in SLUGS:
            raise SystemExit("%s: by_duty has %r, which is not a duty slug"
                             % (_short(GROUND_PLAN), slug))
        if name and name not in grounds:
            raise SystemExit("%s: %s is assigned %r, which has no entry under grounds"
                             % (_short(GROUND_PLAN), slug, name))
    # ONE LIFT FOR ALL NINE TILES, in real pixels, positive upward. Not per plate, and not the
    # same thing as a plate's `anchor`: anchor says where in the PICTURE the standing line falls,
    # which is a fact about that piece of art, while the lift says how far the whole ground sits
    # off the floor line on every tile at once -- which is a fact about the tile's layout, tuned
    # against the banner underneath it. Defaulted rather than required, so a plan written before
    # this existed still loads.
    lift = data.get("lift", 0)
    if isinstance(lift, bool) or not isinstance(lift, int) or not -300 <= lift <= 600:
        raise SystemExit("%s: lift is %r, want a whole number -300-600"
                         % (_short(GROUND_PLAN), lift))
    data["lift"] = lift
    # ONE TRANSPARENCY FOR EVERY PLATE ON EVERY SET, beside the lift and for the same reason:
    # both are facts about how the board is drawn rather than about one piece of art. Stored as
    # transparency rather than opacity because that is the way round it gets talked about, and
    # because a top-level `opacity` beside a per-plate `opacity` would be two keys of one name.
    transp = data.get("transparency", 0)
    if isinstance(transp, bool) or not isinstance(transp, int) or not 0 <= transp <= 100:
        raise SystemExit("%s: transparency is %r, want a whole number 0-100 (0 is solid)"
                         % (_short(GROUND_PLAN), transp))
    data["transparency"] = transp
    # ---- and each set that stands its plates differently -------------------------------------
    # A PLATE IS THE SAME ART WHATEVER SIZE THE SCULPTS ARE, but how it is STOOD is not: the lift
    # is a distance in real pixels between the floor line and the ground, and the scale sizes the
    # plate against figures that are 90 px tall in one set and 210 in another. So the picture
    # stays global and the standing of it splits, which is also why `by_duty` does not split --
    # which duty stands on which plate is not a question about how big anything is.
    per_set = data.get("per_set")
    if per_set is not None:
        if not isinstance(per_set, dict):
            raise SystemExit("%s: per_set is %r, want an object keyed by set label"
                             % (_short(GROUND_PLAN), per_set))
        for label, own in sorted(per_set.items()):
            where = "%s: per_set[%s]" % (_short(GROUND_PLAN), label)
            if not re.match(r"^\d+_[a-z][a-z0-9_]*$", str(label)):
                raise SystemExit("%s is not a set label like '210_painted'" % where)
            if not isinstance(own, dict):
                raise SystemExit("%s is %r, want an object of what this set changes" % (where, own))
            stray = sorted(set(own) - set(GROUND_PER_SET_KEYS))
            if stray:
                raise SystemExit("%s carries %s, which a set cannot have its own of -- a set "
                                 "may name %s. `by_duty` and `transparency` are deliberately "
                                 "not among them."
                                 % (where, ", ".join(stray), ", ".join(GROUND_PER_SET_KEYS)))
            if not own:
                raise SystemExit("%s is empty -- a set with nothing of its own should not be "
                                 "listed at all" % where)
            if "lift" in own:
                v = own["lift"]
                if isinstance(v, bool) or not isinstance(v, int) or not -300 <= v <= 600:
                    raise SystemExit("%s: lift is %r, want a whole number -300-600" % (where, v))
            own_grounds = own.get("grounds")
            if own_grounds is not None:
                if not isinstance(own_grounds, dict):
                    raise SystemExit("%s: grounds is %r, want an object keyed by plate name"
                                     % (where, own_grounds))
                for name, g in own_grounds.items():
                    # A PLATE THIS SET TUNES MUST BE A PLATE THAT EXISTS. Tuning a name the base
                    # has never heard of is a typo that would sit in the file drawing nothing.
                    if name not in grounds:
                        raise SystemExit("%s tunes %r, which has no entry under the base grounds"
                                         % (where, name))
                    _check_plate(g, "%s: grounds.%s" % (where, name))
    return data


def ground_settings_for(plan, label):
    """How one sculpt set stands its plates: the base, with that set's override laid over it.

    The companion to settings_for, and per plate rather than per file -- a set may restand one
    plate and leave the other five alone, so a plate's row is merged on its own. The row itself
    is whole-value like everywhere else: a set's `slate_irregular` replaces the base's entire.
    """
    out = {"by_duty": copy.deepcopy(plan.get("by_duty") or {}),
           "grounds": copy.deepcopy(plan.get("grounds") or {}),
           "lift": plan.get("lift", 0),
           # NOT per set, and it is handed over here anyway so a page has one place to read
           # every number it draws a plate with.
           "transparency": plan.get("transparency", 0)}
    own = (plan.get("per_set") or {}).get(label) or {}
    if "lift" in own:
        out["lift"] = own["lift"]
    for name, g in (own.get("grounds") or {}).items():
        out["grounds"][name] = copy.deepcopy(g)
    return out


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
    """Every sculpt SET that has art, inlined. Shared with generate_placement_sheet.py.

    Returns `figs[label][seat_index][pose_index]`, where `label` is `<px>_<kind>` and a seat's
    row is a LIST OF POSES -- length 1 for a one-pose set like `210_plastic`, length 3 for
    `210_painted`. One pose is a list of one rather than a special case, so a page can index
    `row[n % row.length]` and the two sets stay interchangeable without branching on which is
    loaded.

    DISCOVERED, NOT DECLARED. Which sets exist is a fact about what the tray has rendered, and
    this file listing them too would be a second copy of make_tray_figures.py's kind table --
    the copy that goes stale the first time a kind is added there and not here.

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
        return figs

    # label -> {seat: {pose: path}}, filled from whatever the folder holds.
    found = {}
    for path in sorted(fig_dir.glob("figure_player_*.png")) if fig_dir.is_dir() else []:
        m = FIGURE_NAME.match(path.name)
        if not m:
            continue            # an older naming, or art for something that is not the tray
        seat, pose, px, kind = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        if seat not in FIGURE_SEATS:
            continue            # seat 4 is rendered and this page seats three -- see above
        found.setdefault("%d_%s" % (px, kind), {}).setdefault(seat, {})[pose] = path

    for label in sorted(found, key=set_sort):
        seats = found[label]
        # A SET IS WHOLE OR IT IS NOT OFFERED. Half a set draws a board with a seat missing,
        # which reads as a rule about the arrangement rather than as art that never rendered.
        gap = [s for s in FIGURE_SEATS if s not in seats]
        if gap:
            notes.append("%-12s no art for seat%s %s, set left out"
                         % (label, "" if len(gap) == 1 else "s",
                            ", ".join(str(s) for s in gap)))
            continue
        # Poses must be 1..n for every seat and the SAME n, or `row[i % row.length]` would pick
        # a different pose per seat from the same index and the column rule would mean nothing.
        wanted = sorted(seats[FIGURE_SEATS[0]])
        if (wanted != list(range(1, len(wanted) + 1))
                or any(sorted(seats[s]) != wanted for s in FIGURE_SEATS)):
            notes.append("%-12s poses do not line up across the seats (%s), set left out"
                         % (label, "; ".join("seat %d: %s" % (s, sorted(seats[s]))
                                             for s in FIGURE_SEATS)))
            continue
        row = []
        for seat in FIGURE_SEATS:
            poses = []
            for pose in wanted:
                im = _Img.open(seats[seat][pose]).convert("RGBA")
                buf = io.BytesIO()
                # LOSSLESS. These are the true-size reference the whole page is built to judge;
                # a lossy re-encode would put its artefacts on the thing being looked at. The
                # art is small enough that it costs little. (`quality` is ignored when lossless,
                # so it is not passed -- carrying one would only suggest it did something.)
                im.save(buf, "WEBP", method=6, lossless=True)
                poses.append({"uri": "data:image/webp;base64,"
                                     + base64.b64encode(buf.getvalue()).decode("ascii"),
                              "w": im.width, "h": im.height})
            row.append(poses)
        figs[label] = row

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
                    help="folder holding figure_player_<seat>_p<pose>_<px>_<label>.png "
                         "(default: %s)" % FIGURE_DIR.relative_to(ROOT))
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
            # Every set the tray has rendered, not a declared list: this page is the one whose
            # job is comparing them, so it offers whatever is there.
            .replace("__SIZES__", json.dumps(sorted(figs, key=set_sort)))
            .replace("__BANNERTOP__", json.dumps(BANNER_TOP))
            .replace("__BANNERFS__", json.dumps(BANNER_FS))
            .replace("__BANNERTRACK__", json.dumps(BANNER_TRACK))
            .replace("__BANNERINK__", json.dumps(BANNER_INK))
            .replace("__DEFAULTS__", json.dumps(DEFAULTS))
            .replace("__PLACEMENT__", json.dumps(PLACE))
            # EVERY SET'S NUMBERS, RESOLVED HERE. The page switches sets live, so it needs an
            # answer per set rather than the base and the rule for merging it -- and the rule
            # living in one place means the sow and the sheet cannot disagree with this page
            # about what 210_painted's spread is.
            .replace("__RULES__", json.dumps(
                {label: settings_for(PLACE, label) for label in sorted(figs, key=set_sort)}))
            .replace("__FORMATION__", RULES_JS.read_text(encoding="utf-8")))
    left = re.findall(r"__[A-Z_]+__", page)
    assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    print("  %d shapes, %d of them telling the seating rules apart"
          % (len(SHAPES), sum(1 for s in SHAPES
                              if s["queues"]["grouped"] != s["queues"]["arrival"])))
    tuned = PLACE.get("tuned_at")
    own = sorted(PLACE.get("per_set") or {}, key=set_sort)
    print("  placement from %s: spread %d, set-back %d, rank gap %d  (the BASE, which belongs "
          "to %s at %s px)" % (PLACEMENT.name, PLACE["spread"], PLACE["back"], PLACE["rank"],
                               tuned or "?", set_px(tuned) if tuned else "?"))
    print("  %s" % ("sets with numbers of their own: %s"
                    % ", ".join("%s (%s)" % (k, ", ".join(sorted(PLACE["per_set"][k])))
                                for k in own)
                    if own else "no set carries numbers of its own -- every one takes the base"))
    print("  order %s  ·  mark %s  ·  depth %s %d%%"
          % (PLACE["order"], _marks_sentence(PLACE), PLACE["depth"]["mode"],
             PLACE["depth"]["amount"]))
    print("  sculpts %s  ·  banners %d  ·  icons %d across %d duties"
          % (", ".join("%s [%d pose%s]"
                        % (k, len(figs[k][0]), "" if len(figs[k][0]) == 1 else "s")
                        for k in sorted(figs, key=set_sort)) or "none", len(banner_art),
             sum(len(i) for i in icons), sum(1 for i in icons if i)))
    for note in notes:
        print("  %s" % note)
    show(out, args.open)


if __name__ == "__main__":
    main()
