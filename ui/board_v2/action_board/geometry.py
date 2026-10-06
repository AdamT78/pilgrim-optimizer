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
TILE_GAP = GAP
# HOW MANY TILES, as a name rather than as an 8 and a 7 in the same expression. DUTIES is the real
# owner of this count and is declared far below -- it has to be, it carries the wording -- so the
# number lived here as a literal, which was tolerable while only this line used it. The controls
# column is placed off the LAST tile, so a second expression now depends on it. check() holds the
# two together.
TILES = 8
TILE_W = (WORK_W - (TILES - 1) * TILE_GAP) // TILES           # 154
TILE_PITCH = TILE_W + TILE_GAP
TILE_NAME_SIZE = 13


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
SEAL = 72
SEAL_INSET = INSET

# THE FRAME ROUND A MARK, which lived as a `2` in the template's CSS until the controls column
# needed it. It was harmless there while it only drew an edge; the moment another object's SIZE is
# measured from it, it is a number two files depend on and only one of them could see. The page
# reads it from here now and sets --seal-border off it.
#
# WHAT IT COSTS A MARK: the marks are border-box, so a 72 mark with a 2 frame shows 68 of artwork,
# and two of them 6 apart have 10 of clear air between the pictures. Both of those are what the
# controls column is matched to, below.
SEAL_BORDER = 2

# THE RIBBON IS AS TALL AS WHAT IT HOLDS, rather than a number somebody typed. One inset does
# every job in the tile -- under the name, between the two marks, and under the lower one -- so
# the column hangs at a single rhythm and the tile stops at the same distance below the last mark
# as the marks keep between themselves. It was 242 with a mark of 100; at 72 it is this.
RIBBON_H = 2 * BORDER + TILE_NAME_BOTTOM + 3 * SEAL_INSET + 2 * SEAL     # 186

# MOVED DOWN WITH IT. The tile's inner box is measured off RIBBON_H, and RIBBON_H is no longer a
# number typed near the top -- it is derived from the marks it has to hold, which are declared
# below the name. So this follows them rather than preceding them.
TILE_INNER_W, TILE_INNER_H = inner(TILE_W, RIBBON_H)      # 152 x 184

# THE ROAD. A strip the full width of the working area, between the ribbon and the action cards,
# reserved for the Merchant -- which rides the eight duty tiles and advances one clockwise at each
# round end, so it travels along the row rather than around anything. Nothing is drawn in it yet.
#
# ITS HEIGHT IS WHAT THE SHORTER RIBBON FREED, and that is the point: ART_Y stays exactly where it
# was, so the cards, the confirm row and the wheel do not move and the wheel pays nothing. 40 is
# what falls out of 242 - 186 less the two gaps that now sit either side of the strip.
# 104: the 40 the shorter ribbon freed, PLUS the 64 the confirm row gave back when it stopped
# being a row. The cards drop by that 64 so their foot lands where the confirm's did, which is
# why WHEEL_Y does not move -- the wheel neither gains nor pays for any of this.
ROAD_H = 104
ROAD_Y = RIBBON_Y + RIBBON_H + GAP
ROAD_X = X0
ROAD_W = WORK_W
ROAD = {"x": ROAD_X, "y": ROAD_Y, "width": ROAD_W, "height": ROAD_H}

# THE BACKDROP IS THE RIBBON AND THE ROAD TOGETHER, and it is derived from both rather than given
# a height of its own. It runs from the top of the tiles to the foot of the strip -- a valley the
# eight tiles stand in front of and the Merchant's road runs along the bottom of.
#
# IT IS THE ONE RECT ON THIS BOARD THAT IS MEANT TO BE COVERED. Everything else here is placed so
# that nothing overlaps it; this is placed BEHIND two things that do, which is why its height is
# the distance between two other objects and can never be typed. Shorten the ribbon or widen the
# strip and the picture follows without anybody remembering to resize it.
#
# THE ARTWORK'S OWN ROAD USED TO HAVE TO LAND ON THE TOP OF THE STRIP, and that rule has gone --
# not relaxed because it was inconvenient, but because the strip stopped being a surface. It is
# where the Merchant is TOLD to walk; the picture behind him is scenery. The arithmetic says the
# same: the strip is 104 tall now rather than 64, so it wants 34% of the rect below the horizon
# and the master has 8.8% of its height below its own. No crop of that file can satisfy the old
# rule, and stretching one to fit distorted the whole valley by 26% to do it. The horizon falls
# INSIDE the strip instead, 64px down its 104.
BACKDROP_Y = RIBBON_Y
BACKDROP_H = (ROAD_Y + ROAD_H) - BACKDROP_Y      # 306
BACKDROP = {"x": X0, "y": BACKDROP_Y, "width": WORK_W, "height": BACKDROP_H}

# WHERE THE PAINTED GROUND STARTS, as a fraction of the picture's height. Measured off the file,
# not chosen: it is what the crop came out at. Published so the page and the records agree about
# it, and so a replacement picture has a number to be compared with by eye rather than nothing.
BACKDROP_GROUND = 0.871   # recorded, no longer enforced


def configure(seal: int) -> None:
    """Set the mark size at launch and recompute the two numbers that hang off it.

    THE ONLY SUPPORTED OVERRIDE, and it exists so a size can be tried without editing this file
    and remembering to put it back. Everything else here stays typed where it is: this is not a
    settings system, it is one lever with one caller.

    TOKEN and TOKEN_SPREAD are reassigned because they are DERIVED FROM SEAL, and a flag that
    moved the tile marks while leaving the Tithe's three at 100 would be the exact bug the
    comment above TOKEN exists to prevent -- a seal and a coin are meant to be interchangeable
    at one size. Everything else reads SEAL through seal_slots(), token_slots() and as_dict(),
    which look it up when they are called, so they need nothing done to them.

    WHAT THIS DOES NOT DO IS MOVE THE RIBBON. RIBBON_H is 242 because a column of two at 100 asks
    for it; a larger mark does not grow the tile to fit, it overflows it. That is deliberate --
    the ribbon's height is paid for by the wheel, and pricing it is
    icon_lab/generate_tile_column.py's job, not a flag's. check() is what refuses the overflow,
    so call it after this and believe what it says.
    """
    global SEAL, TOKEN, TOKEN_SPREAD
    if seal < 1:
        raise SystemExit("a mark of %d px is not a size" % seal)
    SEAL = seal
    TOKEN = token_cap(SEAL)
    TOKEN_SPREAD = TOKEN + INSET

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
ART_Y = ROAD_Y + ROAD_H + GAP                    # 313, unchanged: the road took the slack

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

# Show Map, Hire Building and the City stay one tile wide, under Allocation. THEY NO LONGER LINE
# UP WITH THE TITHE, and that is the cost of centring the row: the Tithe moved with the cards to
# TITHE_X and this column stayed on the board's right margin, so the two are 93 apart. It is the
# one visible seam in this arrangement and it is deliberate -- a row aligned to the ribbon and a
# column aligned to the margin cannot both be had.
SIDE_W = TILE_W
SIDE_X = X0 + WORK_W - SIDE_W

ART_GAP = GAP

# THE CARD ROW IS CENTRED ON THE RIBBON'S TILES, not aligned to their edges. It begins at the
# middle of the first tile and ends at the middle of the last, so the row reads as hung beneath
# the eight rather than butted against them, and the ribbon's own rhythm sets where it starts.
ROW_X = X0 + TILE_W // 2                         # 105, Clerical's centre

# AND THE ROW NOW ENDS WITH A MARK, not with the Tithe. The three standing controls -- Show Map,
# Hire Building and the commit -- are a column of marks, and the row reads cards, Tithe, controls.
# The Tithe takes what is left of it.
#
# WHERE THE COLUMN ENDS IS WHERE THE ROW ENDS, and the column is placed by the eighth tile rather
# than by the board's margin -- see MARKS_X below for why. So this cannot be stated until the
# column has been, and ROW_END is published down there with it.
# MOVED UP FROM BELOW THE ROW. It used to sit with the rest of the tile's drawing, which was
# fine while nothing outside the tile asked where a mark goes. The controls column is placed
# off Allocation's mark, and a module-level expression cannot call a function declared after
# it -- so the choice was to inline the centring here and let two expressions drift, or to put
# the one that owns it in front. This is the one that owns it.
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


# ---- the controls column ----------------------------------------------------------------------
# THREE MARKS AT THE END OF THE ACTION ROW: Show Map, Hire Building, and the commit.
#
# THE COLUMN IS THE EIGHTH TILE'S MARK, CARRIED DOWN. Not "near" it and not centred under it by a
# number worked out here -- the same box, to the pixel: Allocation's artwork sits at 1261..1329
# inside its frame, and so do these. That single fact gives the column its x, its width and the
# row's right edge, and it is why there is no margin arithmetic in this section at all.
#
# IT USED TO BE FLUSH WITH THE WORKING EDGE, 41px to the right of this, and the two right edges
# lining up made it look deliberate from a distance while no two emblems on the board shared an
# axis. Nothing else here is justified to the margin -- the cards hang off tile centres -- so the
# column was the one object relating to the page rather than to the board.
#
# WHAT IT COSTS: 43px at the right of the action row with nothing in it, and the Tithe down to 120
# from 159, since the Tithe is what the row has left after the cards and this. Both are real and
# neither is hidden: the strip has no owner until something lands in it.
MARKS_ORDER = ("map", "hire", "commit")

# A MARK HERE IS A TILE'S MARK WITHOUT ITS FRAME, which is the whole of the sizing rule. A mark on
# a tile is SEAL with a SEAL_BORDER frame inside it, so it shows SEAL - 2*SEAL_BORDER of artwork;
# these carry no frame, because they are pressed rather than chosen, so they ARE that artwork size.
# The same emblem is now the same size in both places, which it was not at SEAL.
MARK = SEAL - 2 * SEAL_BORDER                    # 68
# AND THE AIR BETWEEN THEM IS THE AIR A TILE KEEPS, measured between the pictures rather than
# between the boxes. A tile's two marks are SEAL_INSET apart as boxes and 10 apart as artwork,
# because each box spends SEAL_BORDER on its frame. Matching the 6 -- which the column did at
# first -- matches the arithmetic and not the eye.
MARK_AIR = SEAL_INSET + 2 * SEAL_BORDER          # 10
MARKS_W = MARK
MARKS_H = len(MARKS_ORDER) * MARK + (len(MARKS_ORDER) - 1) * MARK_AIR        # 224

# ALLOCATION'S ARTWORK BOX, asked of the tile rather than retyped. seal_slots() places a mark
# inside its tile and the tile is placed on the pitch, so this is the one expression that survives
# the ribbon changing width, the seal changing size, or a ninth duty arriving.
MARKS_X = (X0 + (TILES - 1) * TILE_PITCH         # the eighth tile's left edge
           + BORDER + seal_slots(1)[0]["x"]      # its mark, inside the border
           + SEAL_BORDER)                        # and inside the mark's frame
ROW_END = MARKS_X + MARKS_W                      # 1329
ROW_W = ROW_END - ROW_X                          # 1224

# TITHE_W STOPPED BEING TILE_PITCH, which it was while the row ended at Allocation's centre and
# held nothing but cards and the Tithe. That was the happy number that made the centred row free;
# it is spent twice over now -- once on the column, once on pulling the column back off the margin.
TITHE_W = ROW_W - 2 * ART_W - 2 * ART_GAP - GAP - MARKS_W    # 120
TITHE_X = ROW_X + 2 * ART_W + 2 * ART_GAP        # 1125
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
# THE CONFIRM ROW IS GONE. Three buttons, one of which showed at a time, reserving a band 48 tall
# plus a gap across the whole board for whichever one it was. It is one mark now, at the foot of
# the controls column, and the 64 px it held went to the road above the cards.
#
# CONFIRM_Y, CONFIRM_H, CONFIRM_SIZE and CONFIRM_PAD_X are gone with it, and confirm_for() with
# them. A button that is a mark has no type size and no padding: it has SEAL, like every other
# mark on this board.

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
def token_cap(seal: int) -> int:
    """The biggest a Tithe token can be, which is not always the mark's size.

    THE COLUMN'S HEIGHT BINDS IT NOW. While the Tithe was two tiles wide with the three tokens
    side by side, the question was how many fit across. One tile wide with them in a column it is
    how many fit DOWN, and that height is ART_H -- a number chosen for the artwork. The width term
    alone reports 67 and would let a column of three overflow its box by 11.

    WRITTEN ONCE BECAUSE IT IS ASKED TWICE: here, and again in configure() when --icons moves the
    mark size. Two copies would answer the same question differently the first time either was
    tuned, which is the shape of fault this file exists to prevent.

    THE WIDTH TERM WAS STILL DIVIDING BY TWO, and this is where that was caught. It dates from the
    side-by-side arrangement -- two tokens across, so each gets half the room -- and it was never
    updated when they went into a column, because it did not BIND: at a Tithe of 159 it reported
    69 against a height term of 66, so the wrong expression and the right one happened to agree
    about the answer. Narrowing the Tithe to 120 for the controls column made it bind, and the
    tokens silently went from 66 to 50 -- a third of their area, for a reason nobody chose.
    One token across now, with an inset either side of it.
    """
    room = (ART_H - 2 * BORDER) - (TITHE_LABEL_TOP + TITHE_LABEL_H + INSET) - INSET
    return min(seal,
               TITHE_INNER_W_PRE - 2 * INSET,
               (room - 2 * INSET) // 3)


TOKEN = token_cap(SEAL)
TOKEN_SPREAD = TOKEN + INSET
TOKEN_ORDER = ("wheat", "stone", "silver")

# THE GAP IS WHAT IS LEFT, which is the only honest way round. Three seals of 78 and a label do
# not leave room for GAP between them -- 3*78 + 2*16 + the label's band comes to 298 in a box of
# 295 -- so the column is laid out from its fixed parts and the gap takes the remainder. Written
# the other way, picking a gap and hoping, is how the label gets quietly pushed out of the box.
TITHE_INNER_W, TITHE_INNER_H = inner(TITHE_W, ART_H)         # 322 x 245
# TOKEN_X, TOKEN_Y, TOKEN_GAP, TOKEN_TOP and TOKEN_COLUMN_H ARE GONE. Every one of them described
# a vertical stack -- a first row, a gap repeated twice, a column height to centre in -- and they
# were deleted when the three resources went onto a triangle. The three are back IN a column now,
# and these do not come back with them: the point was never the arrangement, it was that five
# constants cannot be rearranged. token_slots() below says where the three are, and TOKEN_SPREAD
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
# STANDING_H, STANDING_SIZE and STANDING_PAD_X are gone. Show Map and Hire Building were text
# buttons 48 tall in this column; they are marks now, in the controls column at the end of the
# action row, and a mark has SEAL and nothing else to say about its size.

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
WHEEL_Y = ART_Y + ART_H + GAP                    # 640, exactly where it was
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
# The two standing buttons that used to stack above the City have left for the controls column.
# The City keeps its place on the wheel's baseline and its derived height; the 160 px they held
# is empty for now, and is the room the City will need when the wheel's centre stops holding
# acolytes and this box starts showing them -- which is what the note above CITY_H already says.

CITY = {"x": SIDE_X, "y": CITY_Y, "width": SIDE_W, "height": CITY_H}

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


def mark_slots() -> dict:
    """Where the three controls sit: bottom-aligned with the action row, one MARK_AIR up from it.

    THE FOOT IS WHAT IS ALIGNED, not the head. The commit is the mark the eye ends on, so it sits
    at the bottom of the row where the cards finish, held off the edge by the same air the column
    keeps internally -- the tile does exactly this under its lower mark.

    THE SLACK IS ALL AT THE TOP, and there is 13 of it: three marks and their air come to 234 in a
    row of 247. There is no box around this column, so that 13 is not a margin of anything and has
    nothing to be unequal with. Spreading it to make the column fill the row would mean a different
    rhythm from the tiles', which is the thing being matched.
    """
    bottom = ART_Y + ART_H - MARK_AIR
    top = bottom - MARKS_H
    return {name: {"x": MARKS_X, "y": top + i * (MARK + MARK_AIR),
                   "width": MARK, "height": MARK}
            for i, name in enumerate(MARKS_ORDER)}


def art_slots() -> dict:
    """The two picture boxes. The confirm under each is derived, not stored -- one less thing
    to drag out of register, and one less number for a saved file to disagree about."""
    return {"actionA": {"x": ROW_X, "y": ART_Y, "width": ART_W, "height": ART_H},
            "actionB": {"x": ROW_X + ART_W + ART_GAP, "y": ART_Y,
                        "width": ART_W, "height": ART_H}}


def as_dict() -> dict:
    """Everything the page needs, as one JSON-able object.

    The template reads this and nothing else, so there is no number typed twice between here and
    the drawing. A value missing from here cannot be used there.
    """
    return {
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "gap": GAP, "gapWide": GAP_WIDE, "x0": X0, "workW": WORK_W,
        "status": dict(STATUS, size=STATUS_SIZE),
        "road": dict(ROAD),
        "backdrop": dict(BACKDROP, ground=BACKDROP_GROUND),
        "ribbon": {"y": RIBBON_Y, "height": RIBBON_H, "tileW": TILE_W, "tileGap": TILE_GAP,
                   "pitch": TILE_PITCH, "nameSize": TILE_NAME_SIZE,
                   "nameTop": TILE_NAME_TOP, "nameLh": TILE_NAME_LH,
                   "innerW": TILE_INNER_W, "innerH": TILE_INNER_H,
                   "seal": SEAL, "sealInset": SEAL_INSET, "sealBorder": SEAL_BORDER,
                   # So an empty slot is honest about the size of the seal that will fill it.
                   "solidFraction": SOLID_FRACTION,
                   # The page does not work the diagonal out; it is handed both arrangements.
                   "sealSlots": {"1": seal_slots(1), "2": seal_slots(2)}},
        "tiles": tiles(),
        "art": {"y": ART_Y, "width": ART_W, "height": ART_H, "gap": ART_GAP,
                "ratio": ART_RATIO, "capSize": CAP_SIZE, "capPadX": CAP_PAD_X,
                "capPadY": CAP_PAD_Y, "capLh": CAP_LH, "capH": CAP_H},
        "slots": art_slots(),
        # NO `size` HERE. It was published beside the rects and read by nobody -- the rects each
        # carry their own width and height, which is what a drawing needs, so the extra key was a
        # second statement of the same number waiting to disagree with it. That is the fault this
        # tree already has an open note about elsewhere (`--frame`, set by the icon picker and read
        # by no rule), and it is cheaper to not start a second one.
        "marks": dict(mark_slots(), order=list(MARKS_ORDER)),
        "side": {"x": SIDE_X, "width": SIDE_W},
        "tithe": dict(TITHE, labelSize=TITHE_LABEL_SIZE, labelH=TITHE_LABEL_H,
                      labelTop=TITHE_LABEL_TOP, lh=CAP_LH, token=TOKEN,
                      order=list(TOKEN_ORDER), spread=TOKEN_SPREAD,
                      slots=token_slots()),
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
        "ribbon -> road": ROAD_Y - (RIBBON_Y + RIBBON_H),
        "road -> art": ART_Y - (ROAD_Y + ROAD_H),
        "wheel -> canvas foot": CANVAS_H - (WHEEL_Y + WHEEL_H),
        # MEASURED FROM THE ROW, NOT THE MARGIN. These two read 93 the moment the row moved
        # off X0 and onto the first tile's centre -- the gaps had not changed at all, the
        # thing they were measured from had.
        "card A -> card B": art_slots()["actionB"]["x"] - (ROW_X + ART_W),
        # THE BOX BESIDE THE CARDS IS THE TITHE, NOT THE COLUMN BELOW IT. Measured to SIDE_X
        # this read 186 -- the distance to a box three rows further down, which is not a gap
        # anybody can see.
        "cards -> tithe": TITHE_X - (ROW_X + ART_W + ART_GAP + ART_W),
        "cards -> wheel": WHEEL_Y - (ART_Y + ART_H),
        "tithe -> the controls": MARKS_X - (TITHE_X + TITHE_W),
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
    # between boxes can still have two wax discs touching. In a column the NEAREST pair is
    # TOKEN_SPREAD apart and the outer two are twice that, so testing the nearest answers for all
    # three -- as it did on the triangle, where every pair was TOKEN_SPREAD. The sentence changed
    # and the test did not, which is the property TOKEN_SPREAD was named for.
    touch = SOLID_FRACTION * TOKEN
    if TOKEN_SPREAD < touch + DISC_CLEARANCE:
        bad.append("three Tithe seals of %d stand %d apart and their discs meet at %.1f, so they "
                   "clear each other by %.1f" % (TOKEN, TOKEN_SPREAD, touch, TOKEN_SPREAD - touch))
    if TOKEN > TITHE_W - 2 * INSET:
        bad.append("a Tithe seal of %d does not fit a box %d wide" % (TOKEN, TITHE_W))
    # AND THE CAP AGREES WITH THE ARRANGEMENT. The width term in token_cap() went on dividing by
    # two after the tokens left their row, and nothing failed for as long as the height term was
    # the smaller of the two -- a wrong expression hidden behind a right answer. This asks the
    # question the other way round: whatever the cap says, a token has to be the largest that the
    # column it actually sits in will take. One across, an inset either side, three down.
    slots = token_slots()
    if len({t["x"] for t in slots}) != 1:
        bad.append("the Tithe's tokens are no longer one across, so token_cap()'s width term is "
                   "measuring an arrangement the board does not have")
    elif TOKEN < min(SEAL, TITHE_INNER_W - 2 * INSET,
                     ((ART_H - 2 * BORDER) - (TITHE_LABEL_TOP + TITHE_LABEL_H + INSET)
                      - INSET - 2 * INSET) // 3):
        bad.append("a Tithe token is %d and the box would take a larger one -- the cap is "
                   "stricter than the column it is capping" % TOKEN)
    # THE ROW STANDS ON THE RIBBON'S CENTRES, which is the claim this layout makes and the one
    # thing no other guard here would notice going wrong. It used to stand on their EDGES, and
    # these two lines are the whole difference between the old arrangement and this one.
    t = tiles()
    half = TILE_W // 2
    if ROW_X != t["clerical"]["x"] + half:
        bad.append("the row's left edge is at %d and the first tile's centre at %d"
                   % (ROW_X, t["clerical"]["x"] + half))
    # AND THE RIGHT-HAND END IS ALLOCATION'S MARK, by the same rule as the left is Clerical's
    # centre. The row briefly ended at the working edge, while the controls column was pinned
    # there; both ends hang off the ribbon again now, which is what makes the row read as belonging
    # to the eight tiles rather than to the page it is printed on.
    if ROW_END != MARKS_X + MARKS_W:
        bad.append("the row ends at %d and the controls column at %d"
                   % (ROW_END, MARKS_X + MARKS_W))

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
    # THE CONTROLS COLUMN STAYS INSIDE THE ACTION ROW, which replaces the old guard that Show Map
    # cleared the confirm row -- both of those objects have gone. Three marks and their air come to
    # 234 in a row of 247, and the thing that would break it is somebody raising SEAL.
    if len(DUTIES) != TILES:
        bad.append("the ribbon is built for %d tiles and there are %d duties"
                   % (TILES, len(DUTIES)))
    m = mark_slots()
    first, last = m[MARKS_ORDER[0]], m[MARKS_ORDER[-1]]
    if first["y"] < ART_Y or last["y"] + MARK > ART_Y + ART_H:
        bad.append("the controls column spans %d..%d and the action row is %d..%d"
                   % (first["y"], last["y"] + MARK, ART_Y, ART_Y + ART_H))
    # AND IT STANDS ON ALLOCATION'S MARK, which is the claim the whole section is built on and the
    # one a later edit is most likely to break while everything still renders. Asked of the tile
    # here, exactly as MARKS_X asks it, so the two cannot drift: if this ever fails, the column has
    # stopped being the eighth tile's artwork carried down and is merely near it.
    art_x = X0 + (TILES - 1) * TILE_PITCH + BORDER + seal_slots(1)[0]["x"] + SEAL_BORDER
    if MARKS_X != art_x or MARKS_W != SEAL - 2 * SEAL_BORDER:
        bad.append("the controls column is %d..%d and Allocation's artwork is %d..%d"
                   % (MARKS_X, MARKS_X + MARKS_W, art_x, art_x + SEAL - 2 * SEAL_BORDER))
    # THE STRIP IT LEAVES AT THE RIGHT IS DECLARED, not discovered. Pulling the column off the
    # margin left 43px of board with nothing in it, and a guard that said nothing would let that
    # grow unremarked. It is not an arbitrary 43, though, which is the point worth holding: it is
    # exactly the margin Allocation's own mark leaves to the right INSIDE its tile -- the tile's
    # border, the space beside the mark, and the mark's own frame -- carried straight down. The
    # column is the tile's artwork and the strip is the tile's margin; one fact, stated twice.
    strip = (X0 + WORK_W) - ROW_END
    want = BORDER + (TILE_INNER_W - SEAL - (TILE_INNER_W - SEAL) // 2) + SEAL_BORDER
    if strip != want:
        bad.append("the strip right of the controls column is %d and the tile's own right margin "
                   "round its mark is %d" % (strip, want))
    if WHEEL_X < X0 or WHEEL_X + WHEEL_W > SIDE_X:
        bad.append("the wheel spans %d..%d and the play column is %d..%d"
                   % (WHEEL_X, WHEEL_X + WHEEL_W, X0, SIDE_X))

    # THE BACKDROP COVERS THE RIBBON AND THE STRIP EXACTLY, which is the one thing about it that
    # can go wrong silently: it sits behind two objects, so a backdrop an inch too short shows as
    # a seam under the last tile rather than as anything that fails.
    if BACKDROP["y"] != RIBBON_Y or BACKDROP["y"] + BACKDROP["height"] != ROAD_Y + ROAD_H:
        bad.append("the backdrop spans %d..%d and the ribbon and road span %d..%d"
                   % (BACKDROP["y"], BACKDROP["y"] + BACKDROP["height"],
                      RIBBON_Y, ROAD_Y + ROAD_H))
    # THE PAINTED ROAD NO LONGER HAS TO LAND ON THE STRIP, and the guard that held it there has
    # gone with the rule. The strip is where the Merchant is TOLD to walk and the picture is
    # scenery behind him -- that was the choice, and holding a painted horizon to a reserved band
    # was the other one. What is still worth asserting is that the picture reaches both ends of
    # what it stands behind, which the guard above does.

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

    # AND THE LAST MARK LEAVES WHAT THE PAIR KEEP BETWEEN THEM, which is the rule RIBBON_H is now
    # DERIVED from -- so without this line the derivation is a comment rather than something the
    # board is held to. The box test above does not reach it: a mark of 73 stays well inside the
    # tile and merely sits two pixels nearer the edge than the pair sit from each other, which is
    # the whole of what the shorter ribbon was asked for. 76 is where it starts to overflow, and
    # by then the tile has been wrong for three sizes without complaint.
    last = seal_slots(2)[-1]
    under = TILE_INNER_H - (last["y"] + SEAL)
    if under != SEAL_INSET:
        bad.append("the lower seal leaves %d under it inside a tile while the pair keep %d "
                   "between them, so the ribbon is no longer the height of what it holds"
                   % (under, SEAL_INSET))

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


def token_slots() -> list:
    """The three Tithe resources in a COLUMN, centred, TOKEN_SPREAD apart.

    A ROW, A TRIANGLE, A ROW, AND NOW A COLUMN -- and every change was the box changing shape
    rather than anybody's taste. Side by side wants width and the box had it at two tiles wide;
    on a triangle the width binds and no card height can touch it; in a column the HEIGHT binds,
    and that height is ART_H, chosen for the artwork. One tile wide, a column is the only
    arrangement that reads, and token_cap() is what keeps three of them inside the box.

    TOKEN_SPREAD IS STILL CENTRE TO CENTRE, as it was for the row and for the triangle's side, so
    check()'s touch test goes on measuring one number whatever the arrangement.
    """
    cx = TITHE_INNER_W / 2.0
    top = TITHE_LABEL_TOP + TITHE_LABEL_H + INSET
    bottom = TITHE_INNER_H - INSET
    span = 2 * TOKEN_SPREAD + TOKEN
    y0 = top + (bottom - top - span) / 2.0 + TOKEN / 2.0
    centres = [(cx, y0), (cx, y0 + TOKEN_SPREAD), (cx, y0 + 2 * TOKEN_SPREAD)]
    return [{"x": int(round(x - TOKEN / 2.0)), "y": int(round(y - TOKEN / 2.0)), "size": TOKEN}
            for x, y in centres]


if __name__ == "__main__":                                   # pragma: no cover - a hand check
    for k, v in gaps().items():
        print("  %-24s %d" % (k, v))
    print()
    for line in check() or ["sound"]:
        print(" ", line)
