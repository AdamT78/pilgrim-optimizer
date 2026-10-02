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
WHEEL_ASSET = BOARD / "assets" / "duty_wheel_v2.svg"

CANVAS_W, CANVAS_H = 1400, 1200

# The one spacing, and the one deliberate exception.
GAP = 16
GAP_WIDE = 2 * GAP

# The board's working column: the status bar's own edges, which everything else aligns to.
X0 = 28
WORK_W = CANVAS_W - 2 * X0                      # 1344

# ONE INSET, THE WAY THERE IS ONE GAP. GAP is the distance BETWEEN two boxes; this is the distance
# from a box's own edge to what is printed or placed inside it, and X0 is a third thing again --
# the board's outer margin. `gaps()` lists none of these, because none of them is a gap.
#
# It exists because two labels of the same kind had drifted: the duty's name sat 14 from the top of
# its tile and the action's name 6 from the top of its card, and nothing anywhere said they were
# meant to agree. One value, used by both, so the question cannot come back.
INSET = 6

# EVERY BORDERED BOX ON THIS BOARD IS A BORDER-BOX WITH A ONE-PIXEL RULE, so its stated width and
# height are its OUTER size while a child positioned at `left: 6px` sits 6px from the border's
# INNER edge. Measuring a child against the outer size is a two-pixel lean, and it had happened in
# three separate places -- the duty tile, the City's grid and the Tithe's column -- each found by
# measuring the rendered page rather than by reading the code, because the arithmetic looks
# symmetrical either way. `inner()` is the one way to ask, so there is nothing left to get wrong.
BORDER = 1


def inner(width: int, height: int) -> tuple:
    """A bordered box's usable size: what its children are actually positioned within."""
    return width - 2 * BORDER, height - 2 * BORDER

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
RIBBON_H = 152
TILE_GAP = GAP
TILE_W = (WORK_W - 7 * TILE_GAP) // 8           # 154
TILE_PITCH = TILE_W + TILE_GAP
TILE_NAME_SIZE = 13

TILE_INNER_W, TILE_INNER_H = inner(TILE_W, RIBBON_H)      # 152 x 150

# THE LINE HEIGHT IS SET RATHER THAN GUESSED. This was TILE_NAME_SIZE * 1.25 against a CSS rule
# that named no line-height at all, so the browser used Georgia's own and drew a 15px line where
# the arithmetic said 16. A number this file states and the page does not obey is worse than no
# number: everything measured from it is quietly out. The template is handed this and uses it.
TILE_NAME_LH = 1.2                              # the same line the action's own name is set on
TILE_NAME_TOP = INSET                           # the same inset the card's own name is printed at
TILE_NAME_BOTTOM = TILE_NAME_TOP + round(TILE_NAME_SIZE * TILE_NAME_LH)   # 22

# ---- the seals in the tile ---------------------------------------------------------------------
# THE SEALS SIT DIAGONALLY, AND THAT IS WHAT MAKES 78 POSSIBLE. Side by side, two seals and a gap
# need 2*78 + 16 = 172 inside a tile 154 wide; there is no arrangement in a row that fits. On the
# diagonal -- first under the name at the top left, second at the bottom right -- the pair overlaps
# only at one corner and both discs stay whole and readable.
#
# WHAT ACTUALLY HAS TO CLEAR IS THE DISCS, NOT THE BOXES. Each seal fills SOLID_FRACTION of its
# square, so two boxes overlapping at a corner can still leave the drawn discs apart -- and at the
# first arrangement they did not, quite: their centres were 70.0 apart against a sum of radii of
# 70.7, so the two wax discs were touching by seven tenths of a pixel. The box arithmetic said
# "corner overlap 18 x 42" and looked comfortable; the thing on screen was not.
#
# Two changes open it up, and neither costs the wheel anything. The name moved to INSET, which
# lifts the first seal with it; and the seals took the same INSET as everything else instead of
# half the gap. Centres are 78.8 apart now and the discs clear each other by 8.1px.
#
# THE RIBBON'S HEIGHT IS STILL WHAT BUYS VERTICAL SEPARATION -- dy is RIBBON_H - INSET - SEAL -
# TILE_NAME_BOTTOM, so every pixel of ribbon goes straight into it -- but dx comes from the tile's
# width alone and only the inset can move it. check() asserts the discs clear.
SEAL = 78
SEAL_INSET = INSET

# EVERY DISC ON THIS BOARD FILLS THIS MUCH OF ITS OWN SQUARE, and the number lives here rather
# than in a README because it has now been got wrong three times: the three coins, then the three
# grey resource seals, then the two red action seals, each set arriving with its discs at a
# different fraction and each one reading as a layout fault rather than a difference in the
# drawings. A seal and a coin are meant to be interchangeable in one slot at one size, and nothing
# in the drawings enforces that -- so it is asserted, by tests/action_board, against the files.
SOLID_FRACTION = 0.906
SOLID_TOLERANCE = 0.004

# THE FLOOR, NOT THE VERDICT. A seal's bounding disc is the widest its art ever gets, and these
# seals are not circles -- the wax is scalloped and lopsided, so the widest point of one is not
# the point facing the other. Measured against the real alpha masks at the real placement, the
# rims clear each other by 4.85px where this conservative figure says 2.1. So it is held at zero:
# it catches the fault that actually happened, which was the two bounding discs INTERSECTING at
# -0.7 while the box arithmetic read "corner overlap 18 x 42" and sounded roomy. How much daylight
# looks right is not a thing this file can know, and a threshold invented here would be a metric
# posing as a judge.
DISC_CLEARANCE = 0

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
CAP_PAD_X, CAP_PAD_Y = 10, INSET
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
TITHE_LABEL_H = round(TITHE_LABEL_SIZE * TILE_NAME_LH)   # 14, on the board's one line height

# A SEAL IS A SEAL, AND THEY ARE ALL ONE SIZE. The three resources in the Tithe column were drawn
# at 64 beside duty action seals of 78, which made the third choice on this row look like a lesser
# kind of thing than the two beside it. It is not: taking the tithe is the same sort of move. The
# token takes the seal's size, and nothing here is free to disagree with it.
TOKEN = SEAL
TOKEN_ORDER = ("wheat", "stone", "silver")

# THE GAP IS WHAT IS LEFT, which is the only honest way round. Three seals of 78 and a label do
# not leave room for GAP between them -- 3*78 + 2*16 + the label's band comes to 298 in a box of
# 295 -- so the column is laid out from its fixed parts and the gap takes the remainder. Written
# the other way, picking a gap and hoping, is how the label gets quietly pushed out of the box.
TITHE_INNER_W, TITHE_INNER_H = inner(SIDE_W, ART_H)          # 130 x 293
TOKEN_X = (TITHE_INNER_W - TOKEN) // 2                       # centred in the box, not beside it
TOKEN_COLUMN_H = TITHE_INNER_H - 2 * INSET - TITHE_LABEL_H - INSET   # 261, the room above
TOKEN_GAP = (TOKEN_COLUMN_H - 3 * TOKEN) // 2                # 13
TOKEN_Y = INSET + (TOKEN_COLUMN_H - (3 * TOKEN + 2 * TOKEN_GAP)) // 2

# The City sits on the wheel's baseline; the two standing options stack above it, GAP_WIDE apart,
# because they are a different kind of thing from the move being made this turn.
CITY_H = 300
STANDING_H = 48
STANDING_SIZE = 13
STANDING_PAD_X = 8

# ---- the figures in the City ---------------------------------------------------------------------
# PLACEHOLDER NUMBERS, LIKE THE ACOLYTES BELOW, and in here for the same reason. Four pawns in a
# 2 x 2 grid is not how this box will end up working: the wheel's centre will stop holding
# acolytes, the City will show them instead, and where a figure stands will become a function of
# how many are standing there. These are today's numbers, they are expected to go, and they are
# written here rather than in the page so that when they go there is one place to change.
#
# WHAT THEY REPLACE WAS MEASURABLY WRONG, which is why this moved now rather than later. The grid
# was `(width - 24) / 2` with 8px margins typed into the template, and 132 is the OUTER width of a
# bordered box -- so the panel drew with a 9px margin on the left and 7px on the right, a two-pixel
# lean nothing was watching. Vertically it was four unrelated figures: 12 above the label, 9 under
# it, 10 between the rows and 23 at the foot, not one of them the board's own INSET or GAP. The
# City's label was 12px set 12 from the top while the Tithe's is 12px set 6 from the bottom: two
# panels of the same kind, side by side, disagreeing about their own margins.
CITY_LABEL_SIZE = TITHE_LABEL_SIZE               # the same label on the same kind of box
CITY_LABEL_H = TITHE_LABEL_H
CITY_COLS, CITY_ROWS = 2, 2
CITY_INNER_W, CITY_INNER_H = inner(SIDE_W, CITY_H)       # 130 x 298
# ONE INSET HERE TOO -- between the figures, around them, and under the label. There is nothing
# about this box that wants a second spacing in it, and the four it had were how it went wrong.
CITY_FIG_W = (CITY_INNER_W - (CITY_COLS + 1) * INSET) // CITY_COLS
CITY_FIG_TOP = INSET + CITY_LABEL_H + INSET      # under the label, at the one inset
CITY_FIG_H = (CITY_INNER_H - CITY_FIG_TOP - CITY_ROWS * INSET) // CITY_ROWS


def city_figures() -> list:
    """Where the four pawns stand INSIDE the City panel, in player order.

    Inside its border, like everything else placed in a bordered box on this board -- which is the
    bug this replaced. Derived, so the row that was 23 from the foot and 9 from the label is now
    the same distance from both, and the two columns are the same distance from their own edges.
    """
    out = []
    for i in range(CITY_COLS * CITY_ROWS):
        col, row = i % CITY_COLS, i // CITY_COLS
        out.append({"x": INSET + col * (CITY_FIG_W + INSET),
                    "y": CITY_FIG_TOP + row * (CITY_FIG_H + INSET),
                    "width": CITY_FIG_W, "height": CITY_FIG_H})
    return out

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


def seal_slots(n: int) -> list:
    """Where a duty's seals sit INSIDE its tile, for a duty with n actions.

    RELATIVE TO THE TILE, not the board, because the tile is what moves. Eight tiles have eight
    different x, and a seal position written in board coordinates would be eight facts where one
    will do.

    A one-action duty gets ONE seal, centred -- not the first of two with an empty slot beside it.
    An empty slot is a hole nobody can fill, and Taxation and Allocation genuinely have one action
    each; `duty_text.json` is what says so.

    THE TOP SEAL IS INSET FROM THE NAME EXACTLY AS THE BOTTOM ONE IS FROM THE EDGE. It used to
    begin at TILE_NAME_BOTTOM, flush against the line of type with nothing between them, while
    the other had a margin under it -- so the pair sat high and lopsided in a tile that looked
    like it had been nudged. One inset, measured from whatever is above each seal.
    """
    top = TILE_NAME_BOTTOM + SEAL_INSET
    bottom = TILE_INNER_H - SEAL_INSET - SEAL
    if n == 1:
        return [{"x": (TILE_INNER_W - SEAL) // 2, "y": top + (bottom - top) // 2, "size": SEAL}]
    if n == 2:
        return [{"x": SEAL_INSET, "y": top, "size": SEAL},
                {"x": TILE_INNER_W - SEAL_INSET - SEAL, "y": bottom, "size": SEAL}]
    raise SystemExit("a duty with %d actions has no seal arrangement here" % n)


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
                   "nameTop": TILE_NAME_TOP, "nameLh": TILE_NAME_LH,
                   "innerW": TILE_INNER_W, "innerH": TILE_INNER_H,
                   "seal": SEAL, "sealInset": SEAL_INSET,
                   # So an empty slot is honest about the size of the seal that will fill it.
                   "solidFraction": SOLID_FRACTION,
                   # The page does not work the diagonal out; it is handed both arrangements.
                   "sealSlots": {"1": seal_slots(1), "2": seal_slots(2)}},
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
        "tithe": dict(TITHE, labelSize=TITHE_LABEL_SIZE, labelH=TITHE_LABEL_H,
                      labelBottom=INSET, lh=TILE_NAME_LH, token=TOKEN, tokenGap=TOKEN_GAP,
                      tokenX=TOKEN_X, tokenY=TOKEN_Y, order=list(TOKEN_ORDER)),
        "showMap": SHOW_MAP, "hire": HIRE,
        "standing": {"size": STANDING_SIZE, "padX": STANDING_PAD_X},
        "city": dict(CITY, labelSize=CITY_LABEL_SIZE, labelH=CITY_LABEL_H, labelTop=INSET,
                     lh=TILE_NAME_LH, figures=city_figures()),
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
        # No "seal -> seal" here any more. The two seals OVERLAP by design, so the distance
        # between them is not a gap and holding it to GAP would have forced them back into a row
        # they do not fit in. check() asserts the overlap is a corner instead.
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
    # The Tithe column: three seals, then a label, inside one box.
    tokens_end = TOKEN_Y + 3 * TOKEN + 2 * TOKEN_GAP
    label_top = TITHE_INNER_H - INSET - TITHE_LABEL_H
    if TOKEN_X != TITHE_INNER_W - TOKEN_X - TOKEN:
        bad.append("a Tithe seal sits %d from one side of its column and %d from the other"
                   % (TOKEN_X, TITHE_INNER_W - TOKEN_X - TOKEN))
    if tokens_end > label_top:
        bad.append("the three Tithe seals end at %d and the Take Tithe label starts at %d, so "
                   "they overlap by %d" % (tokens_end, label_top, tokens_end - label_top))
    if TOKEN_GAP < 1:
        bad.append("three Tithe seals of %d leave %d between them, which is not a column"
                   % (TOKEN, TOKEN_GAP))
    if TOKEN > SIDE_W - 2 * INSET:
        bad.append("a Tithe seal of %d does not fit a column %d wide" % (TOKEN, SIDE_W))

    # The City: four figures in a grid, inside the panel's border, evenly margined.
    figs = city_figures()
    if len(figs) != CITY_COLS * CITY_ROWS or len(figs) != len(PLAYERS):
        bad.append("the City draws %d figures for %d players" % (len(figs), len(PLAYERS)))
    left = figs[0]["x"]
    right = CITY_INNER_W - (figs[CITY_COLS - 1]["x"] + CITY_FIG_W)
    foot = CITY_INNER_H - (figs[-1]["y"] + CITY_FIG_H)
    for name, v in (("left of the City grid", left), ("right of it", right),
                    ("under it", foot)):
        if v != INSET:
            bad.append("%s is %d and the board's inset is %d" % (name, v, INSET))
    if figs[0]["y"] - (INSET + CITY_LABEL_H) != INSET:
        bad.append("the City's figures start %d under its label, not %d"
                   % (figs[0]["y"] - (INSET + CITY_LABEL_H), INSET))
    if CITY_FIG_W < 1 or CITY_FIG_H < 1:
        bad.append("a City figure comes out %d x %d" % (CITY_FIG_W, CITY_FIG_H))
    if MAP_Y <= CONFIRM_Y + CONFIRM_H:
        bad.append("Show Map at %d runs into the confirm row ending at %d"
                   % (MAP_Y, CONFIRM_Y + CONFIRM_H))
    if WHEEL_X < X0 or WHEEL_X + WHEEL_W > SIDE_X:
        bad.append("the wheel spans %d..%d and the play column is %d..%d"
                   % (WHEEL_X, WHEEL_X + WHEEL_W, X0, SIDE_X))

    # ---- the seals in the tile -----------------------------------------------------------------
    for n in (1, 2):
        for s in seal_slots(n):
            # INSIDE THE BORDER, not inside the outer box -- that is where a child is placed.
            if s["x"] < 0 or s["x"] + SEAL > TILE_INNER_W or s["y"] + SEAL > TILE_INNER_H:
                bad.append("a seal of a %d-action duty spans %d..%d x %d..%d inside a tile "
                           "%d x %d" % (n, s["x"], s["x"] + SEAL, s["y"], s["y"] + SEAL,
                                        TILE_INNER_W, TILE_INNER_H))
            if s["y"] - TILE_NAME_BOTTOM < SEAL_INSET:
                bad.append("a seal of a %d-action duty leaves %d under the duty's name and %d "
                           "above the tile's lower edge"
                           % (n, s["y"] - TILE_NAME_BOTTOM, TILE_INNER_H - s["y"] - SEAL))

    # THE DISCS HAVE TO CLEAR, NOT THE BOXES. Two boxes can overlap at a corner and still leave
    # the drawn discs apart, because each disc is only SOLID_FRACTION of its square -- so the box
    # arithmetic is not the thing to assert. The first arrangement passed every box test above
    # with its two wax discs touching.
    a, b = seal_slots(2)
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    if dx <= 0 or dy <= 0:
        bad.append("the second seal is offset by %d, %d, which is not a diagonal" % (dx, dy))
    else:
        centres = (dx * dx + dy * dy) ** 0.5
        touch = SOLID_FRACTION * SEAL            # two radii
        if centres < touch + DISC_CLEARANCE:
            bad.append("the seals' centres are %.1f apart and their discs meet at %.1f, so the "
                       "two wax discs clear each other by %.1f and %d is the least this board "
                       "accepts" % (centres, touch, centres - touch, DISC_CLEARANCE))
    return bad


if __name__ == "__main__":                                   # pragma: no cover - a hand check
    for k, v in gaps().items():
        print("  %-24s %d" % (k, v))
    print()
    for line in check() or ["sound"]:
        print(" ", line)
