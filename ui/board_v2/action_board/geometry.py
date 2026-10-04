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
RIBBON_H = 242
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
# THE TWO MARKS STACK IN A COLUMN, centred, each one inset from whatever is above it: the duty's
# name, the first mark, the second, the tile's lower edge, at SEAL_INSET every time. Where a mark
# sits does not depend on how many the tile holds, so Taxation and Allocation -- one action each --
# put their single mark where the first of two goes, and all eight first marks stand on one line.
#
# IT WAS A DIAGONAL, AND THAT IS WHAT MADE 78 THE CEILING. Side by side, two seals and a gap
# needed 2*78 + 16 = 172 inside a tile 154 wide, so a row did not fit; on the diagonal the pair
# overlapped at one corner and both discs stayed whole. At 100 it runs out: the centres come 43.1
# apart against discs meeting at 90.6, an overlap of 47.5, one mark lying across the other. A
# diagonal buys its separation out of the tile's WIDTH, and width is the one thing a taller ribbon
# cannot give you -- which is why the arrangement had to change rather than the number.
#
# WHAT HAS TO CLEAR IS THE DISCS, NOT THE BOXES, and that outlived the diagonal. Each mark fills
# SOLID_FRACTION of its square, so boxes that look comfortably apart can still have their drawn
# discs touching: the first arrangement had centres 70.0 apart against a sum of radii of 70.7 --
# seven tenths of a pixel of overlap -- while the box arithmetic reported "corner overlap 18 x 42"
# and looked fine. In a column the centres are SEAL + SEAL_INSET apart and check() asserts the
# same thing it always did, now of a different arrangement.
#
# THE RIBBON'S HEIGHT IS WHAT BUYS IT, and the wheel is what pays. A column of two at 100 wants
# RIBBON_H of 242 against the 152 it had; nothing below the ribbon shrinks, because ART_Y derives
# from RIBBON_H and the rest of the board follows down, so the wheel -- whose height is whatever
# the canvas has left -- gives up all 90 pixels and narrows by about twice that.
# icon_lab/generate_tile_column.py is the page that decided it and prices any other height.
SEAL = 100
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

# THE CARDS ARE MEASURED OFF THE RIBBON'S GRID, NOT TYPED. The right-hand column is ONE DUTY TILE
# wide and sits under Allocation, so everything in it -- Take Tithe, Show Map, Hire Building, the
# City -- is the width of the tile above it. The two cards then fill what is left, which is the
# first seven tiles split in two: card two's right edge lands on Ordination's right edge, and the
# gap it leaves before the column is the board's own GAP rather than a remainder.
#
# IT USED TO RUN THE OTHER WAY. ART_W was 590, typed, and SIDE_W was whatever the canvas had left
# over -- 132, which matched no tile and lined up with nothing. Every edge on this row now stands
# on a tile edge above it.
# EACH CARD IS THREE DUTY TILES WIDE, counted off the ribbon above it: three tiles and the two
# gaps between them. Card one then covers Clerical, Taxation and Produce and ends on Produce's
# right edge; card two covers Build Roads, Construct and Give Alms and starts on Build Roads'
# left edge. The ribbon is 3 + 3 + 2, and every vertical edge on this row stands on a tile edge.
ART_W = 3 * TILE_W + 2 * TILE_GAP                # 494
# AND 2:1 IS BACK, which is the whole reason to prefer this width. The masters are generated at
# 2:1, so at 494 x 247 `fit: cover` crops nothing -- what the generator drew is what the card
# shows, end to end. The earlier 579 x 205 was 2.82:1 and threw away 30% of every illustration.
ART_H = ART_W // 2                               # 247, exactly half

# THE TITHE SPANS THE LAST TWO TILES, Ordination and Allocation, starting where the second card
# stops leaving room. The three boxes BELOW it keep the single tile's width they already had, so
# this is the one box on the board whose width is not the column's.
TITHE_X = X0 + 6 * TILE_PITCH                    # 1048, Ordination's left edge
TITHE_W = 2 * TILE_W + TILE_GAP                  # 324, out to Allocation's right edge

# Show Map, Hire Building and the City stay one tile wide, under Allocation.
SIDE_W = TILE_W
SIDE_X = X0 + WORK_W - SIDE_W
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
# THE BUTTON IS AS WIDE AS ITS WORD, NOT AS WIDE AS ITS BOX. confirm_for() hands over the whole
# card's width because that is the span the button is aligned WITHIN -- it sits at the right-hand
# end of it, where the thing it acts on finishes. What it actually occupies is the word plus this
# padding each side. The number lived in the template, which is why the Tithe's button never got
# it: that one took its box at face value and came out the full width of the Tithe panel, a
# different button from the two beside it doing the same job.
CONFIRM_PAD_X = 22

# ---- the right-hand column -------------------------------------------------------------------
# SIDE_X and SIDE_W are set with the cards above, because the column is now what the cards are
# measured against rather than what is left after them.

TITHE = {"x": TITHE_X, "y": ART_Y, "width": TITHE_W, "height": ART_H}
# THE TITHE'S TITLE IS AN ACTION CAPTION, not a panel label. It sits at the top of its box on the
# same line as "Ordain" and "Silversmith", because taking the tithe is the third choice in that row
# and the three titles are one row of titles. Its size, its top inset and its line height are the
# art caption's and are not set here, so the row cannot fall out of line by somebody editing one of
# the three.
TITHE_INNER_W_PRE = inner(TITHE_W, ART_H)[0]
TITHE_LABEL_SIZE = CAP_SIZE
# ONE PIXEL HIGHER THAN THE CAPTION'S INSET, and that pixel is the panel's border. The action card
# has no border, so its caption at a 6 starts 6 below the top of the card; the Tithe is a bordered
# panel, so a child at a 6 starts 7 below the top of the box. Measured on the rendered page: the
# two titles came out 283.4 and 284.4. This is the fault test_a_bordered_box_measures_its_children
# _inside_its_border already names, met once more.
TITHE_LABEL_TOP = CAP_PAD_Y - BORDER
TITHE_LABEL_H = round(TITHE_LABEL_SIZE * CAP_LH)         # 17

# A SEAL IS A SEAL, AND THEY ARE ALL ONE SIZE. The three resources in the Tithe column were drawn
# at 64 beside duty action seals of 78, which made the third choice on this row look like a lesser
# kind of thing than the two beside it. It is not: taking the tithe is the same sort of move. The
# token takes the seal's size, and nothing here is free to disagree with it.
TOKEN = min(SEAL, (TITHE_INNER_W_PRE - 2 * INSET - INSET) // 2)
TOKEN_SPREAD = TOKEN + INSET
TOKEN_ORDER = ("wheat", "stone", "silver")

# THE GAP IS WHAT IS LEFT, which is the only honest way round. Three seals of 78 and a label do
# not leave room for GAP between them -- 3*78 + 2*16 + the label's band comes to 298 in a box of
# 295 -- so the column is laid out from its fixed parts and the gap takes the remainder. Written
# the other way, picking a gap and hoping, is how the label gets quietly pushed out of the box.
TITHE_INNER_W, TITHE_INNER_H = inner(TITHE_W, ART_H)         # 322 x 245
# TOKEN_X, TOKEN_Y, TOKEN_GAP, TOKEN_TOP and TOKEN_COLUMN_H ARE GONE. Every one of them described
# a vertical stack -- a first row, a gap repeated twice, a column height to centre in -- and the
# three resources sit on a triangle now. token_slots() below says where they are, and TOKEN_SPREAD
# is the only number it needs.

# ---- the acolyte -----------------------------------------------------------------------------
# ITS SIZE IS DECIDED HERE, ABOVE THE CITY, BECAUSE THE CITY IS MEASURED FROM IT. A pawn in the
# City box and a pawn on the duty wheel are the same figure in two places, so there is one size
# and the City takes it rather than keeping a second one of its own.
ACOLYTE_H = 120
ACOLYTE_ASPECT = 0.42
ACOLYTE_W = round(ACOLYTE_H * ACOLYTE_ASPECT)                # 50

# The City sits on the wheel's baseline; the two standing options stack above it, GAP_WIDE apart,
# because they are a different kind of thing from the move being made this turn.
#
# CITY_H is derived from the figures and the label, so it is set below, once both are known.
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
# City's label was 12px set 12 from the top while the Tithe's was 12px set 6 from the bottom: two
# panels of the same kind, side by side, disagreeing about their own margins.
#
# THE TITHE HAS SINCE LEFT. Its title moved to the top of its box to stand in the action captions'
# row and took their 14 with it, so this is no longer "the same label on the same kind of box" and
# no longer written as one: it is a panel label on a panel, and it keeps the 12 the two once shared.
CITY_LABEL_SIZE = 12
CITY_LABEL_H = round(CITY_LABEL_SIZE * TILE_NAME_LH)

# AND THE BOX FITS ITS FIGURES, rather than being a typed 300 they were cut down to meet. Reading
# down: the border, the label at its inset, the two rows with one inset between them, one at the
# foot. It is DERIVED and not typed, so a figure that changes size takes the box with it.
CITY_H = (2 * BORDER + INSET + CITY_LABEL_H + INSET
          + 2 * ACOLYTE_H + INSET + INSET)
CITY_COLS, CITY_ROWS = 2, 2
CITY_INNER_W, CITY_INNER_H = inner(SIDE_W, CITY_H)       # 130 x 298
# ONE INSET HERE TOO -- between the figures, around them, and under the label. There is nothing
# about this box that wants a second spacing in it, and the four it had were how it went wrong.
# THE FIGURE IS THE ACOLYTE, AT THE ACOLYTE'S SIZE. It used to be whatever was left after the box
# was divided up -- 67 x 130, an aspect of 0.515 against the pawn's own 0.417, so the same drawing
# that stands on the wheel at 50 x 120 was stretched 23% wider in the City. One figure in two
# places was two different shapes, and it is the box that should give, not the pawn.
CITY_FIG_W, CITY_FIG_H = ACOLYTE_W, ACOLYTE_H
CITY_FIG_TOP = INSET + CITY_LABEL_H + INSET      # under the label, at the one inset
# CENTRED, NOT INSET. Figures of a fixed size no longer fill the box's width, so the grid sits in
# the middle of what it has; an INSET on the left with all the slack on the right would lean.
CITY_GRID_X = (CITY_INNER_W - (CITY_COLS * CITY_FIG_W + (CITY_COLS - 1) * INSET)) // 2


def city_figures() -> list:
    """Where the four pawns stand INSIDE the City panel, in player order.

    Inside its border, like everything else placed in a bordered box on this board -- which is the
    bug this replaced. Derived, so the row that was 23 from the foot and 9 from the label is now
    the same distance from both, and the two columns are the same distance from their own edges.
    """
    out = []
    for i in range(CITY_COLS * CITY_ROWS):
        col, row = i % CITY_COLS, i // CITY_COLS
        out.append({"x": CITY_GRID_X + col * (CITY_FIG_W + INSET),
                    "y": CITY_FIG_TOP + row * (CITY_FIG_H + INSET),
                    "width": CITY_FIG_W, "height": CITY_FIG_H})
    return out

# ---- the wheel ----------------------------------------------------------------------------------
WHEEL_Y = CONFIRM_Y + CONFIRM_H + GAP            # 552
# THE WHEEL'S ROOM IS EVERYTHING LEFT OF THE RIGHT-HAND COLUMN, not the width of the cards. It
# was the cards' width, which was the same thing while they reached the column; at three tiles
# each they stop well short of it, and a wheel centred under them was pushed 12px past the board's
# own margin -- outside the canvas's left inset, which check() caught.
PLAY_W = SIDE_X - GAP - X0                       # 1174


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

    A one-action duty gets ONE seal where the FIRST of two would go -- not centred in the space,
    and not the first of two with an empty slot beside it.
    An empty slot is a hole nobody can fill, and Taxation and Allocation genuinely have one action
    each; `duty_text.json` is what says so.

    THE TOP SEAL IS INSET FROM THE NAME EXACTLY AS THE BOTTOM ONE IS FROM THE EDGE. It used to
    begin at TILE_NAME_BOTTOM, flush against the line of type with nothing between them, while
    the other had a margin under it -- so the pair sat high and lopsided in a tile that looked
    like it had been nudged. One inset, measured from whatever is above each seal.
    """
    top = TILE_NAME_BOTTOM + SEAL_INSET
    x = (TILE_INNER_W - SEAL) // 2
    # EVERY FIRST MARK ON THE SAME LINE, WHATEVER THE TILE HOLDS. A single mark used to be centred
    # in the space under the name, which put Taxation's and Allocation's half a mark lower than the
    # top mark of every tile beside them -- and on a ribbon of eight that reads as two tiles done
    # wrong rather than as two tiles that are different. The column hangs from the name instead,
    # so where a mark sits stops depending on how many the tile has.
    if n == 1:
        return [{"x": x, "y": top, "size": SEAL}]
    if n == 2:
        return [{"x": x, "y": top, "size": SEAL},
                {"x": x, "y": top + SEAL + SEAL_INSET, "size": SEAL}]
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
                    "padX": CONFIRM_PAD_X,
                    "actionA": confirm_for("actionA"), "actionB": confirm_for("actionB"),
                    "tithe": {"x": TITHE_X, "y": CONFIRM_Y,
                              "width": TITHE_W, "height": CONFIRM_H}},
        "side": {"x": SIDE_X, "width": SIDE_W},
        "tithe": dict(TITHE, labelSize=TITHE_LABEL_SIZE, labelH=TITHE_LABEL_H,
                      labelTop=TITHE_LABEL_TOP, lh=CAP_LH, token=TOKEN,
                      order=list(TOKEN_ORDER), spread=TOKEN_SPREAD,
                      slots=token_slots()),
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
        # THE BOX BESIDE THE CARDS IS THE TITHE, NOT THE COLUMN BELOW IT. Measured to SIDE_X
        # this read 186 -- the distance to a box three rows further down, which is not a gap
        # anybody can see.
        "cards -> tithe": TITHE_X - (X0 + ART_W + ART_GAP + ART_W),
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
    # THE TOKENS ARE ON A TRIANGLE, SO ASK THE TRIANGLE. These two guards were doing the
    # arithmetic of a vertical stack -- TOKEN_Y plus three tokens and two gaps -- and went on
    # reporting overlaps against an arrangement that no longer exists. Read the slots instead:
    # whatever the layout becomes, the first one's top and the last one's bottom are true of it.
    slots = token_slots()
    tokens_top = min(d["y"] for d in slots)
    tokens_end = max(d["y"] + d["size"] for d in slots)
    label_end = TITHE_LABEL_TOP + TITHE_LABEL_H
    left = min(d["x"] for d in slots)
    right = TITHE_INNER_W - max(d["x"] + d["size"] for d in slots)
    if abs(left - right) > 1:
        bad.append("the Tithe's seals sit %d from one side of their box and %d from the other"
                   % (left, right))
    if tokens_top < label_end:
        bad.append("the Take Tithe label ends at %d and the three seals start at %d, so they "
                   "overlap by %d" % (label_end, tokens_top, label_end - tokens_top))
    if tokens_end > TITHE_INNER_H - INSET:
        bad.append("the three Tithe seals end at %d and the column's inner edge is at %d"
                   % (tokens_end, TITHE_INNER_H - INSET))
    # THE TITHE'S DISCS HAVE TO CLEAR EACH OTHER TOO, by the same rule as the tile's marks and for
    # the same reason: the drawn disc is SOLID_FRACTION of its square, so a gap that looks safe
    # between boxes can still have two wax discs touching. On the triangle every pair of centres
    # is TOKEN_SPREAD apart, so one number answers for all three.
    touch = SOLID_FRACTION * TOKEN
    if TOKEN_SPREAD < touch + DISC_CLEARANCE:
        bad.append("three Tithe seals of %d stand %d apart and their discs meet at %.1f, so they "
                   "clear each other by %.1f" % (TOKEN, TOKEN_SPREAD, touch, TOKEN_SPREAD - touch))
    if TOKEN > TITHE_W - 2 * INSET:
        bad.append("a Tithe seal of %d does not fit a box %d wide" % (TOKEN, TITHE_W))
    # THE CARDS AND THE TITHE STAND ON THE RIBBON'S OWN EDGES, which is the claim this layout
    # makes and the one thing no other guard here would notice going wrong.
    t = tiles()
    for label, got, want in (("card one's right edge", X0 + ART_W, t["produce"]["x"] + TILE_W),
                             ("card two's right edge", X0 + ART_W + ART_GAP + ART_W,
                              t["give_alms"]["x"] + TILE_W),
                             ("the Tithe's left edge", TITHE_X, t["ordination"]["x"]),
                             ("the Tithe's right edge", TITHE_X + TITHE_W,
                              t["allocation"]["x"] + TILE_W)):
        if got != want:
            bad.append("%s is at %d and the tile above it at %d" % (label, got, want))

    # The City: four figures in a grid, inside the panel's border, evenly margined.
    figs = city_figures()
    if len(figs) != CITY_COLS * CITY_ROWS or len(figs) != len(PLAYERS):
        bad.append("the City draws %d figures for %d players" % (len(figs), len(PLAYERS)))
    left = figs[0]["x"]
    right = CITY_INNER_W - (figs[CITY_COLS - 1]["x"] + CITY_FIG_W)
    foot = CITY_INNER_H - (figs[-1]["y"] + CITY_FIG_H)
    # EVENLY MARGINED IS THE CLAIM, AND IT IS NOT THE SAME AS "AT THE INSET". The figures are the
    # acolyte's size now, so they do not fill the box's width and the side margins are whatever is
    # left -- but they still have to match each other, which is the lean this guard exists to
    # catch. The foot is a margin the box's own height controls, so that one is the inset exactly.
    if abs(left - right) > 1:
        bad.append("the City grid sits %d from one side and %d from the other" % (left, right))
    if foot != INSET:
        bad.append("under the City grid is %d and the board's inset is %d" % (foot, INSET))
    if (CITY_FIG_W, CITY_FIG_H) != (ACOLYTE_W, ACOLYTE_H):
        bad.append("a City figure is %d x %d and an acolyte on the wheel is %d x %d"
                   % (CITY_FIG_W, CITY_FIG_H, ACOLYTE_W, ACOLYTE_H))
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
    if dx != 0 or dy <= 0:
        bad.append("the second seal is offset by %d, %d, which is not a column" % (dx, dy))
    else:
        centres = float(dy)
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


def token_slots() -> list:
    """The three Tithe resources on an equilateral TRIANGLE, two below and one centred above.

    A COLUMN OF THREE IS SIZED BY ITS BOX'S HEIGHT; A TRIANGLE BY ITS WIDTH. That is the whole
    reason to change it. The Tithe box IS the action card's box -- its height is ART_H -- so a
    stack of three was hostage to a number chosen for the artwork: shorten the cards to make room
    for taller duty tiles and the Tithe resources had to shrink with them. On a triangle the
    binding constraint is the bottom pair against SIDE_W, which no card height can touch.

    TOKEN_SPREAD IS THE SIDE OF THE TRIANGLE THE THREE CENTRES STAND ON, which is the vocabulary
    tokens/README.md already uses for this arrangement.
    """
    half = TOKEN_SPREAD / 2.0
    rise = TOKEN_SPREAD * (3 ** 0.5) / 2.0
    cx = TITHE_INNER_W / 2.0
    cy_top = TITHE_LABEL_TOP + TITHE_LABEL_H + INSET + TOKEN / 2.0
    cy_bot = cy_top + rise
    centres = [(cx, cy_top), (cx - half, cy_bot), (cx + half, cy_bot)]
    return [{"x": int(round(x - TOKEN / 2.0)), "y": int(round(y - TOKEN / 2.0)), "size": TOKEN}
            for x, y in centres]
