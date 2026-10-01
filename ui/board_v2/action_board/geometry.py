"""Every number the action board is drawn from, in one place, so the game can import them later.

THIS MODULE IS THE REASON THE TOOL IS NOT A LAB. The layout lab exists to find these numbers and
it has a control for each one; this file is what the search settled on. Nothing here is
adjustable at run time, and that is the feature -- a board whose geometry can be nudged is a
board nobody can write a game against.

IT IS A MODULE RATHER THAN CONSTANTS IN THE TEMPLATE, and that is the whole point of its
existing. When the playable board is built it needs the same 590 x 295, the same 16, the same
177. Numbers that live only inside an HTML template get retyped, and a retyped number is a
number that will differ. One module, imported by the tool now and by whatever draws the real
board later.

ONE SPACING, AND ONE EXCEPTION THAT MEANS SOMETHING. Everything on this board is GAP apart.
GAP_WIDE -- exactly twice it -- is used in one place only: between the controls on the right
that belong to this turn and the ones that are always available. The distance is carrying the
meaning, so a third value would make it carry nothing. `check()` enforces that there are only
two, and tests/action_board/test_action_board.py runs it. That rule erodes one box at a time if
nothing is watching.

THE GEOMETRY IS OURS; THE WHEEL'S SHAPE IS NOT. WHEEL_RATIO comes from the asset's own viewBox,
read at import, because the asset is the authority on its own foreshortening and a number copied
out of it here would silently stop matching the day it is re-exported.
"""
from __future__ import annotations

import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE.parent

# THE WHEEL DRAWING IS BORROWED BY PATH, not copied and not imported. See the fork note in
# generate_action_board.py: the wheel is being redesigned, so this tool owns its own copy of the
# logic -- but the 59 KB of SVG is an asset, and an asset read from a path couples nothing. When
# the redesign lands, this path changes and nothing else does.
WHEEL_ASSET = BOARD / "layout_lab" / "assets" / "duty_wheel_v2.svg"

CANVAS_W, CANVAS_H = 1400, 1200

# The one spacing, and the one deliberate exception.
GAP = 16
GAP_WIDE = 2 * GAP

# The board's working column: the status bar's own edges, which everything else aligns to.
X0 = 28
WORK_W = CANVAS_W - 2 * X0                      # 1344

# ---- the upper text box ----------------------------------------------------------------------
# It holds the phase's line now and the hovered action's wording later. At 16 the type needs 19px
# of line (15 ascent, 4 descent) inside 29, so it is centred with 5 clear above and below and
# nothing can be clipped -- which is what it was doing at the size this replaced.
STATUS = {"x": X0, "y": 10, "width": WORK_W, "height": 29}
STATUS_SIZE = 16

# ---- the eight duty tiles ---------------------------------------------------------------------
# TILE_W IS DERIVED, NOT CHOSEN. Eight tiles and seven gaps have to fill WORK_W exactly, so the
# width is whatever is left: (1344 - 7*16) / 8 = 154. The layout lab's 159 came from a 10px gap,
# which is the one place the board had a third spacing in it.
RIBBON_Y = STATUS["y"] + STATUS["height"] + GAP   # 55, derived so the rule cannot drift
RIBBON_H = 110
TILE_GAP = GAP
TILE_W = (WORK_W - 7 * TILE_GAP) // 8           # 154
TILE_PITCH = TILE_W + TILE_GAP
TILE_NAME_SIZE = 13

# One seal per action, centred as a group in the tile. A one-action duty gets one seal in the
# middle rather than an empty second slot: the slot would be a hole nobody can fill.
SEAL = 46
SEAL_GAP = GAP
SEAL_Y = RIBBON_Y + 44

# ---- the two action cards ----------------------------------------------------------------------
# 590 x 295 IS EXACTLY 2:1, and that is worth more than the nineteen pixels it costs against a
# taller box. The masters are generated at 2:1, so `fit: cover` crops nothing at all -- what the
# generator drew is what the card shows, end to end. Every earlier shape clipped something: the
# 375 x 184 slot took 1.9% of the height, and a 600 x 320 box took 6.25% of the width.
ART_Y = RIBBON_Y + RIBBON_H + GAP                # 177
ART_W, ART_H = 590, 295
ART_GAP = GAP
ART_RATIO = ART_W / ART_H                        # 2.0 exactly

# The action NAME is printed on the picture, top left. The effect line is NOT: it moved off the
# artwork into the top box, which halved the scrim count and gave the bottom of every picture
# back -- the corner the briefs now reserve for the close dark foreground element.
CAP_SIZE = 14
CAP_PAD_X, CAP_PAD_Y = 10, 6
CAP_LH = 1.2
CAP_H = round(CAP_PAD_Y * 2 + CAP_SIZE * CAP_LH)  # 29

# ---- the confirm row -----------------------------------------------------------------------------
# No box under the cards -- the button alone, right-aligned to the card it confirms, on the same
# line as the right-hand column's controls so the three choices read as one row.
CONFIRM_Y = ART_Y + ART_H + GAP                  # 488
CONFIRM_H = 48
CONFIRM_SIZE = 14

# ---- the right-hand column -------------------------------------------------------------------
SIDE_X = X0 + ART_W + ART_GAP + ART_W + GAP      # 1240
SIDE_W = CANVAS_W - X0 - SIDE_X                  # 132, flush with the status bar's right edge

TITHE = {"x": SIDE_X, "y": ART_Y, "width": SIDE_W, "height": ART_H}
TITHE_LABEL_SIZE = 12
TOKEN = 64                                       # 3 * 64 + 2 * 16 = 224, and the box gives 230
TOKEN_GAP = GAP
TOKEN_ORDER = ("wheat", "stone", "silver")

# The City sits on the wheel's baseline; the two standing options stack above it, GAP_WIDE apart,
# because they are a different kind of thing from the move being made this turn.
CITY_H = 300
STANDING_H = 48

# ---- the wheel ----------------------------------------------------------------------------------
WHEEL_Y = CONFIRM_Y + CONFIRM_H + GAP            # 552
PLAY_W = ART_W * 2 + ART_GAP                     # 1196, the left column's full width


def _viewbox_ratio(text: str) -> float:
    """The asset's own height/width, from its viewBox.

    NOT its width/height attributes and not what a browser reports: a drawing exported for a
    board is typically responsive, and a browser asked for one of those answers 300 x 150 -- a
    ratio of 0.5, close enough to a real foreshortening to look right while being wrong.
    """
    m = re.search(r'\bviewBox\s*=\s*"\s*([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s*"',
                  text)
    if not m:
        raise SystemExit("the wheel asset has no viewBox, so its shape is not knowable")
    w, h = float(m.group(3)), float(m.group(4))
    if not (w > 0 and h > 0):
        raise SystemExit("the wheel asset's viewBox is %s x %s" % (w, h))
    return h / w


WHEEL_RATIO = _viewbox_ratio(WHEEL_ASSET.read_text(encoding="utf-8")) if WHEEL_ASSET.is_file() \
    else 529.9 / 1000.0

# THE WHEEL IS HEIGHT-BOUND HERE, which is a change from the lab. The lab fits the widest wheel
# the canvas allows and lets the bottom margin fall where it may; this board wants GAP at the
# bottom like everywhere else, so the height is fixed first and the width follows from the
# asset's ratio. It comes out 4px narrower than the play column, so it is centred in it.
WHEEL_H = CANVAS_H - WHEEL_Y - GAP               # 632
WHEEL_W = round(WHEEL_H / WHEEL_RATIO)
WHEEL_X = X0 + (PLAY_W - WHEEL_W) // 2

CITY_Y = WHEEL_Y + WHEEL_H - CITY_H              # bottom-aligned with the wheel
HIRE_Y = CITY_Y - GAP_WIDE - STANDING_H
MAP_Y = HIRE_Y - GAP_WIDE - STANDING_H

CITY = {"x": SIDE_X, "y": CITY_Y, "width": SIDE_W, "height": CITY_H}
HIRE = {"x": SIDE_X, "y": HIRE_Y, "width": SIDE_W, "height": STANDING_H}
SHOW_MAP = {"x": SIDE_X, "y": MAP_Y, "width": SIDE_W, "height": STANDING_H}

# ---- the acolytes on the wheel ------------------------------------------------------------------
# Re-implemented rather than imported, deliberately -- see the fork note in the generator. These
# are the lab's numbers as they stand today, and they are expected to diverge: the centre will
# stop holding acolytes, the City box will show them instead, and placement will become a
# function of how many figures occupy a space.
ACOLYTE_H = 120
ACOLYTE_ASPECT = 0.42
FIG_RX_FRAC, FIG_RY_FRAC = 0.385, 0.34

PLAYERS = (
    {"id": "p1", "label": "Player 1", "colour": "#8fae6a"},
    {"id": "p2", "label": "Player 2", "colour": "#7fa7c8"},
    {"id": "p3", "label": "Player 3", "colour": "#c88fb8"},
    {"id": "p4", "label": "Player 4", "colour": "#d6a45c"},
)
START_OCCUPANCY = {"clerical": 4, "allocation": 3, "build_roads": 2, "ordination": 1,
                   "give_alms": 4, "produce": 2, "taxation": 3, "construct": 1}
START_SEATS = {"clerical": ["p1", "p1", "p2", "p3"]}
START_CITY_COUNTS = {"p1": 7, "p2": 4, "p3": 2, "p4": 5}

DUTIES = (
    ("clerical",    "Clerical",    0),
    ("taxation",    "Taxation",    45),
    ("produce",     "Produce",     90),
    ("build_roads", "Build Roads", 135),
    ("construct",   "Construct",   180),
    ("give_alms",   "Give Alms",   225),
    ("ordination",  "Ordination",  270),
    ("allocation",  "Allocation",  315),
)
ACTIONS = ("actionA", "actionB")

# WHICH PATH IN THE DRAWING IS WHICH DUTY. The asset names its eight faces by compass point and
# the duties are placed by clock angle, so the mapping is arithmetic rather than a list to keep
# in step: 0 degrees is north and every 45 degrees clockwise is the next name.
COMPASS = ("north", "north_east", "east", "south_east",
           "south", "south_west", "west", "north_west")


def face_of(clock: int) -> str:
    """The id of the face a duty stands on, from its clock angle."""
    if clock % 45:
        raise SystemExit("a duty at %d degrees does not land on one of the eight faces" % clock)
    return COMPASS[(clock // 45) % 8]

PHASES = (
    ("ready",  "Ready / City",      "Pick up Acolytes or Hire Buildings"),
    ("sow",    "Sowing",            "Choose the next Duty"),
    ("action", "Action Selection",  "Select a Duty Action or take Tithe"),
)
LIVE_PHASE = "action"          # the other two are placeholders and the page says so


def tiles() -> dict:
    """Where each duty's tile opens, in wheel order, so the ribbon's order IS the wheel's."""
    return {slug: {"x": X0 + i * TILE_PITCH, "y": RIBBON_Y,
                   "width": TILE_W, "height": RIBBON_H}
            for i, (slug, _n, _d) in enumerate(DUTIES)}


def art_slots() -> dict:
    """The two picture boxes. The confirm under each is derived, not stored -- one less thing
    to drag out of register, and one less number for a saved file to disagree about."""
    return {"actionA": {"x": X0, "y": ART_Y, "width": ART_W, "height": ART_H},
            "actionB": {"x": X0 + ART_W + ART_GAP, "y": ART_Y,
                        "width": ART_W, "height": ART_H}}


def confirm_for(slot: str) -> dict:
    a = art_slots()[slot]
    return {"x": a["x"], "y": CONFIRM_Y, "width": a["width"], "height": CONFIRM_H}


def as_dict() -> dict:
    """Everything the page needs, as one JSON-able object.

    The template reads this and nothing else, so there is no number typed twice between here and
    the drawing. A value missing from here cannot be used there.
    """
    return {
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "gap": GAP, "gapWide": GAP_WIDE, "x0": X0, "workW": WORK_W,
        "status": dict(STATUS, size=STATUS_SIZE),
        "ribbon": {"y": RIBBON_Y, "height": RIBBON_H, "tileW": TILE_W, "tileGap": TILE_GAP,
                   "pitch": TILE_PITCH, "nameSize": TILE_NAME_SIZE,
                   "seal": SEAL, "sealGap": SEAL_GAP, "sealY": SEAL_Y},
        "tiles": tiles(),
        "art": {"y": ART_Y, "width": ART_W, "height": ART_H, "gap": ART_GAP,
                "ratio": ART_RATIO, "capSize": CAP_SIZE, "capPadX": CAP_PAD_X,
                "capPadY": CAP_PAD_Y, "capLh": CAP_LH, "capH": CAP_H},
        "slots": art_slots(),
        "confirm": {"y": CONFIRM_Y, "height": CONFIRM_H, "size": CONFIRM_SIZE,
                    "actionA": confirm_for("actionA"), "actionB": confirm_for("actionB"),
                    "tithe": {"x": SIDE_X, "y": CONFIRM_Y,
                              "width": SIDE_W, "height": CONFIRM_H}},
        "side": {"x": SIDE_X, "width": SIDE_W},
        "tithe": dict(TITHE, labelSize=TITHE_LABEL_SIZE, token=TOKEN, tokenGap=TOKEN_GAP,
                      order=list(TOKEN_ORDER)),
        "showMap": SHOW_MAP, "hire": HIRE, "city": CITY,
        "wheel": {"x": WHEEL_X, "y": WHEEL_Y, "width": WHEEL_W, "height": WHEEL_H,
                  "ratio": WHEEL_RATIO,
                  "figRx": round(WHEEL_W * FIG_RX_FRAC), "figRy": round(WHEEL_H * FIG_RY_FRAC)},
        "acolytes": {"height": ACOLYTE_H, "aspect": ACOLYTE_ASPECT},
        "players": [dict(p) for p in PLAYERS],
        "start": {"occupancy": dict(START_OCCUPANCY), "seats": dict(START_SEATS),
                  "city": dict(START_CITY_COUNTS)},
        "duties": [{"slug": s, "name": n, "clock": d, "face": face_of(d)}
                   for s, n, d in DUTIES],
        "phases": [{"key": k, "label": lbl, "line": line} for k, lbl, line in PHASES],
        "livePhase": LIVE_PHASE,
    }


def gaps() -> dict:
    """Every gap on the board, named, so a test can look at all of them at once.

    NAMED RATHER THAN COUNTED. A test that only checked "the set of gaps is {16, 32}" would pass
    on a board where two things overlapped by -16, and would not say which gap went wrong.
    """
    t = tiles()
    order = [t[s]["x"] for s, _n, _d in DUTIES]
    # The board's outer MARGIN is X0 and is not a gap -- check() asserts the column lands on it.
    g = {
        "status -> ribbon": RIBBON_Y - (STATUS["y"] + STATUS["height"]),
        "ribbon -> art": ART_Y - (RIBBON_Y + RIBBON_H),
        "art -> confirm": CONFIRM_Y - (ART_Y + ART_H),
        "confirm -> wheel": WHEEL_Y - (CONFIRM_Y + CONFIRM_H),
        "wheel -> canvas foot": CANVAS_H - (WHEEL_Y + WHEEL_H),
        "card A -> card B": art_slots()["actionB"]["x"] - (X0 + ART_W),
        "cards -> column": SIDE_X - (X0 + ART_W + ART_GAP + ART_W),
        "tithe -> its confirm": CONFIRM_Y - (TITHE["y"] + TITHE["height"]),
        "show map -> hire": HIRE_Y - (MAP_Y + STANDING_H),
        "hire -> city": CITY_Y - (HIRE_Y + STANDING_H),
        "seal -> seal": SEAL_GAP,
    }
    for i in range(1, len(order)):
        g["tile %d -> %d" % (i, i + 1)] = order[i] - (order[i - 1] + TILE_W)
    return g


def check() -> list:
    """Everything this file asserts about itself. Returns the complaints; empty means sound."""
    bad = []
    for name, v in gaps().items():
        if v not in (GAP, GAP_WIDE):
            bad.append("%s is %d, and this board has only %d and %d in it"
                       % (name, v, GAP, GAP_WIDE))
    if abs(ART_RATIO - 2.0) > 1e-9:
        bad.append("the card is %.5f : 1, so a 2:1 master no longer lands in it uncropped"
                   % ART_RATIO)
    if TILE_W * 8 + TILE_GAP * 7 != WORK_W:
        bad.append("eight tiles and seven gaps come to %d, not the working width %d"
                   % (TILE_W * 8 + TILE_GAP * 7, WORK_W))
    if SIDE_X + SIDE_W != CANVAS_W - X0:
        bad.append("the column ends at %d and the status bar at %d"
                   % (SIDE_X + SIDE_W, CANVAS_W - X0))
    if CITY_Y + CITY_H != WHEEL_Y + WHEEL_H:
        bad.append("the City ends at %d and the wheel at %d, so they are not on one baseline"
                   % (CITY_Y + CITY_H, WHEEL_Y + WHEEL_H))
    if MAP_Y <= CONFIRM_Y + CONFIRM_H:
        bad.append("Show Map at %d runs into the confirm row ending at %d"
                   % (MAP_Y, CONFIRM_Y + CONFIRM_H))
    if WHEEL_X < X0 or WHEEL_X + WHEEL_W > SIDE_X:
        bad.append("the wheel spans %d..%d and the play column is %d..%d"
                   % (WHEEL_X, WHEEL_X + WHEEL_W, X0, SIDE_X))
    return bad


if __name__ == "__main__":                                   # pragma: no cover - a hand check
    for k, v in gaps().items():
        print("  %-24s %d" % (k, v))
    print()
    for line in check() or ["sound"]:
        print(" ", line)
