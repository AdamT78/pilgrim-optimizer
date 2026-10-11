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
# A SLICE IS NOT A TILE, AND THEY USED TO BE THE SAME NUMBER. The ribbon divides the working width
# into eight columns -- that division is derived, not chosen: eight columns and seven gaps have to
# fill WORK_W exactly, so a column is whatever is left, (1344 - 7*16) / 8 = 154. (The layout lab's
# 159 came from a 10px gap, which is the one place the board had a third spacing in it.)
#
# FOR A LONG TIME THE TILE FILLED ITS COLUMN and one name, TILE_W, answered for both facts. The
# tile is now a small box hugging its two marks, 74 wide, and the column it stands in is still
# 154 -- so the two have come apart and each needs its own name. Everything that spaces the eight
# reads SLICE_W; everything that draws one tile reads TILE_W.
RIBBON_Y = STATUS["y"] + STATUS["height"] + GAP   # 55, derived so the rule cannot drift
TILE_GAP = GAP
# HOW MANY TILES, as a name rather than as an 8 and a 7 in the same expression. DUTIES is the real
# owner of this count and is declared far below -- it has to be, it carries the wording -- so the
# number lived here as a literal, which was tolerable while only this line used it. The controls
# column is placed off the LAST tile, so a second expression now depends on it. check() holds the
# two together.
TILES = 8
SLICE_W = (WORK_W - (TILES - 1) * TILE_GAP) // TILES          # 154, one duty's column
TILE_PITCH = SLICE_W + TILE_GAP                               # 170

# ONE LINE FOR EVERY SMALL-CAPS LABEL ON THE BOARD, AND IT IS SET RATHER THAN GUESSED. This was
# the tile name's own number, TILE_NAME_SIZE * 1.25, against a CSS rule that named no line-height
# at all -- so the browser used Georgia's own and drew a 15px line where the arithmetic said 16. A
# number this file states and the page does not obey is worse than no number: everything measured
# from it is quietly out.
#
# THE TILE NAME HAS GONE AND THIS HAS NOT. The duty names are off the board -- the tile is the two
# marks and the box round them -- so TILE_NAME_SIZE, TILE_NAME_TOP and TILE_NAME_BOTTOM are
# deleted. The LINE is still read by the City's label and by the action caption, which is why it
# outlives the thing it was named for and is renamed for what it actually is.
LABEL_LH = 1.2

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
SEAL = 50
SEAL_INSET = INSET

# NO FRAME ROUND A MARK ANY MORE, and SEAL_BORDER has gone with it. It was a 2 in the stylesheet,
# then a constant here once the controls column was sized off it; now the marks are cut-outs drawn
# straight on the tile and nothing measures an edge that is not drawn. A control and a tile mark
# are therefore the same number again -- see MARK below, which is SEAL rather than SEAL less a
# frame it no longer has.

# ---- the tile itself ---------------------------------------------------------------------------
# THE TILE IS NOW EXACTLY ITS TWO MARKS AND THE AIR ROUND THEM. It used to be the whole column --
# 154 x 186, a duty name across the top and the pair floating under it in a good deal of space.
# The name is off the board and the box has closed up round what is left, which is the one thing
# a tile has ever actually been for: saying which two marks belong together.
#
# THE MARKS DO NOT MOVE. That is the constraint this is built to satisfy, and it is why the box is
# derived from the mark rather than the mark re-placed inside a box: every emblem on the ribbon
# stands on the same board pixel it stood on before, and the only visible change is the frame
# drawn round it. check() asserts it against the slice.
#
# THE PAD IS 12, measured off the example rather than chosen: the card in it is 150 wide round an
# icon square of about 99, which is a margin of 25.5, and 25.5/99 of a 50px mark is 12.9. 12 is
# that, in the board's own units -- twice the inset the two marks keep between themselves.
TILE_PAD = 2 * SEAL_INSET                                     # 12
TILE_W = SEAL + 2 * TILE_PAD                                  # 74
TILE_H = 2 * SEAL + SEAL_INSET + 2 * TILE_PAD                 # 130
TILE_INNER_W, TILE_INNER_H = inner(TILE_W, TILE_H)            # 72 x 128

# THE CORNERS ARE ROUNDED HARDER THAN THE OLD TILE'S, AND IN PROPORTION. The old box used a flat
# 4px at 154 wide, which is 0.026 of it -- barely a softening, right for a panel. The example is
# 18px on a card 150 wide, 0.12, which is a different shape of object: a chip, not a panel. Held
# as the fraction so the corner follows the box if the box ever changes.
TILE_RADIUS_FRAC = 0.12
TILE_RADIUS = round(TILE_W * TILE_RADIUS_FRAC)                # 9

# THE RIBBON IS NOT AS TALL AS THE TILE IT HOLDS, and that is a deliberate loosening of a rule
# this file otherwise keeps. The height used to be derived so the tile was exactly snug round its
# two marks at one inset everywhere; a mark of 50 makes that derivation 142, which would take 44
# off the band and move the whole board up. The marks were asked to get smaller, not the board.
#
# SO THE HEIGHT IS DECLARED AND THE TILE FLOATS IN IT, and with the tile down to 130 there are now
# 56 of band it does not use -- which is the landscape behind it, showing. The cost is that two
# numbers have to be kept agreeing by hand where one used to answer for both, and check() is what
# does the keeping: it refuses a tile that does not fit the band, and reports the air left over so
# that a height nobody intended cannot sit here unnoticed.
#
# AND THE AIR BELOW THE TILE IS THE AIR BESIDE IT, which is what sets this number. A tile is
# centred in its 154-wide column, so it keeps TILE_IN_SLICE -- 40 -- clear on each side, and the
# first tile therefore stands 40 in from where the picture starts. The band gives it the same 40
# under its foot, so the margin you see at the left end of the ribbon is the margin you see below
# it. The band is TILE_H + TILE_IN_SLICE.
#
# IT WAS THE AIR ABOVE INSTEAD, briefly: 55 under the tiles to match the 55 above them, which
# made the picture 240 and the tiles exactly centred in it. The side margin is the better match
# because it is the one a player sees against the same object -- the gap at the first tile's left
# shoulder and the gap under its foot are both the tile's own clearance, where the distance to
# the top of the picture is the status bar's business.
#
# STILL DECLARED, NOT DERIVED, AND THAT IS THE WHOLE POINT. Writing it as TILE_H + TILE_IN_SLICE
# is the obvious move and it is wrong: both of those come from the MARK, so the band would too,
# and then so would the road, the picture, the cards, the wheel and the City -- the --icons flag
# would stop being a lever on the marks and become one on the whole board. The reason the height
# is declared has never been that nobody worked out the expression; it is that the ribbon must
# not grow to fit a bigger mark, it must overflow and be refused. check() holds this to
# TILE_H + TILE_IN_SLICE, so the two cannot drift apart silently -- they are just not wired.
RIBBON_H = 170                                   # 55 above the tile, 130 of tile, 40 below

# THE TILE SITS AT THE TOP OF THE BAND, which is one small margin under the status line and is
# not a number of its own. RIBBON_Y is already "one gap below the status bar's foot" -- derived,
# so the rule cannot drift -- and the margin asked for is that gap. Hanging the tile anywhere
# else would be inventing a second distance up here.
#
# IT HUNG 39 LOWER UNTIL NOW, and that 39 was held rather than chosen: it was what kept every
# mark on the board pixel it had occupied before the frame shrank round it, so that putting a box
# round the marks did not also move them. The marks have now been asked to move up, which retires
# the number and the reason together.
#
# WHICH LEAVES THE AIR AT THE FOOT, all 56 of it, and that is not a margin of anything: the band
# has no drawn bottom edge, because the backdrop runs from the top of the canvas straight down
# through the road. The only edge the eye has up here is the status line above the tiles.
TILE_Y = RIBBON_Y

# THE ROAD. A strip the full width of the working area, between the ribbon and the action cards,
# reserved for the Merchant -- which rides the eight duty tiles and advances one clockwise at each
# round end, so it travels along the row rather than around anything. Nothing is drawn in it yet.
#
# IT IS INSIDE THE BAND NOW, NOT A ROW OF ITS OWN BELOW IT. The strip used to sit between the
# ribbon and the cards with a gap either side, 104 tall, and the picture had to stretch over both
# to put painted ground under the Merchant. The picture now ends one tile-air below the tiles, so
# there is no room under the band for a strip -- and no need for one: the band's own lower half
# IS the ground he walks on. The road is the part of the valley below the tiles.
#
# WHICH TAKES A ROW OUT OF THE BOARD'S VERTICAL STACK. It was ribbon, gap, road, gap, cards; it
# is ribbon, gap, cards. The 120 that frees goes to the wheel.
ROAD_Y = TILE_Y + TILE_H                         # 185, the tiles' own foot
ROAD_H = (RIBBON_Y + RIBBON_H) - ROAD_Y          # 55, down to the foot of the band
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
# and the old master had 8.8% of its height below its own. No crop of that file could satisfy the
# old rule, and stretching one to fit distorted the whole valley by 26% to do it.
#
# IT STARTS AT THE TOP OF THE CANVAS NOW, NOT AT THE TOP OF THE TILES. The picture used to begin
# where the ribbon begins, which left 55px of black above it with the status line floating in the
# middle of that -- a caption on a black strip above a picture, rather than a caption on the
# picture. Reaching y = 0 makes the valley the board's own ground rather than a panel inside it.
#
# WHICH PUTS THE STATUS LINE OVER THE SKY, and that is the one thing this costs. The band it sits
# in is a flat mist at luminance 144 and the type is cream: 2.2:1, against the 4.5 ordinary text
# wants. The page answers it with a shadow on the glyphs rather than a plate behind them -- a
# plate would be the black strip again, in the one place the picture was extended to remove it.
# AND IT ENDS AT THE FOOT OF THE BAND, which is one tile-air below the tiles. It used to run on
# past them to the foot of the road strip, 361 deep, because the strip was a separate row with
# painted ground to stand on. The strip is inside the band now, so the picture is the band: the
# tiles with equal valley above and below them, and nothing else.
BACKDROP_Y = 0
BACKDROP_H = RIBBON_Y + RIBBON_H - BACKDROP_Y    # 240
BACKDROP = {"x": X0, "y": BACKDROP_Y, "width": WORK_W, "height": BACKDROP_H}

# HOW MUCH OF THE PICTURE IS GROUND, as the fraction of its height at which it goes dark and
# stays dark. Measured off the file, not chosen. Published so the page and the records agree
# about it, and so a replacement has a number to be read against by eye rather than nothing.
#
# THE RULE CHANGED WITH THE PICTURE, AND THE OLD ONE WAS MEASURING NOISE. It was "the sharpest
# darkening in the lower half", which works on a frame with a HORIZON -- the old valley had one
# and the rule found it at 0.871. This picture has none: it is a continuous fall from mist at 146
# to mud at 43, with no edge anywhere, so the sharpest darkening in its lower half is a fifteen-
# row band of wet earth at 0.958 and the number would have said the ground begins almost at the
# bottom of a frame that is ground for most of its height.
#
# SO BOTH ARE MEASURED THE SAME WAY and the three can be compared: the first row from which the
# picture is within a tenth of its own foreground darkness and never returns above it. v02 gives
# 0.921, v03 0.554, and this one 0.656. The README asked a replacement for "a third of the height
# below the horizon" and everything since v02 has had it.
BACKDROP_GROUND = 0.548   # recorded, no longer enforced


def configure(seal: int) -> None:
    """Set the mark size at launch and recompute the two numbers that hang off it.

    THE ONLY SUPPORTED OVERRIDE, and it exists so a size can be tried without editing this file
    and remembering to put it back. Everything else here stays typed where it is: this is not a
    settings system, it is one lever with one caller.

    EVERYTHING ON THE MARK'S OWN CHAIN IS REASSIGNED, and the chain is longer than it looks.
    Everything that reads SEAL through seal_slots() or as_dict() looks it up when it is called and
    needs nothing done to it; everything that is a module-level EXPRESSION over SEAL is frozen at
    import and has to be asked again here. A test parses this file for that second set and
    requires every one of them to appear below, because a typed list of what a lever moves is a
    list of what somebody remembered.

    WHAT THIS DOES NOT DO IS MOVE THE RIBBON. RIBBON_H is declared, not derived; a larger mark
    does not grow the band to fit, it overflows it. That is deliberate -- the ribbon's height is
    paid for by the wheel, and pricing it is icon_lab/generate_tile_column.py's job, not a flag's.
    check() is what refuses the overflow, so call it after this and believe what it says.

    IT DOES MOVE THE TILE, which is new, and it is the same fault twice over. The controls column
    is Allocation's mark carried down, so a flag that changed SEAL and left MARKS_X alone left the
    column standing where the OLD mark had been -- check()'s strip guard then said the strip was
    52 where the tile's margin was 41, and the right answer looked like a broken board. The tile
    is now derived from the mark too (it is the mark plus TILE_PAD), so the same thing would have
    happened to all eight boxes.
    """
    global SEAL
    global TILE_W, TILE_H, TILE_INNER_W, TILE_INNER_H, TILE_RADIUS, TILE_IN_SLICE
    global MARK, MARK_AIR, MARKS_W, MARKS_X, ROW_END, ROW_W, CONTROL_BOX
    global ROAD_Y, ROAD_H, ROAD
    if seal < 1:
        raise SystemExit("a mark of %d px is not a size" % seal)
    SEAL = seal
    TILE_W = SEAL + 2 * TILE_PAD
    TILE_H = 2 * SEAL + SEAL_INSET + 2 * TILE_PAD
    TILE_INNER_W, TILE_INNER_H = inner(TILE_W, TILE_H)
    TILE_RADIUS = round(TILE_W * TILE_RADIUS_FRAC)
    TILE_IN_SLICE = (SLICE_W - TILE_W) // 2
    MARK = SEAL
    MARK_AIR = SEAL_INSET
    MARKS_W = MARK
    # AND THE BOX ROUND IT, which the typed list did not have and the AST-derived guard found on
    # its first run after the box was added -- a bigger mark would have grown the three emblems
    # and left their grounds at 62, which renders as artwork overflowing its own panel.
    CONTROL_BOX = MARK + 2 * CONTROL_PAD
    MARKS_X = tile_x(TILES - 1) + BORDER + seal_slots(1)[0]["x"]
    ROW_END = MARKS_X + MARKS_W
    ROW_W = ROW_END - ROW_X
    # AND THE ROAD, WHICH IS NEW AND IS THE BAND'S DOING. The strip is the part of the valley
    # below the tiles, so a taller tile eats into it; at a mark big enough it goes to nothing and
    # then negative, and check()'s band guard is what refuses that rather than this.
    ROAD_Y = TILE_Y + TILE_H
    ROAD_H = (RIBBON_Y + RIBBON_H) - ROAD_Y
    ROAD = {"x": ROAD_X, "y": ROAD_Y, "width": ROAD_W, "height": ROAD_H}

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
# ONE GAP UNDER THE PICTURE, which is what it has always been -- but the picture is shorter, so
# the row comes up 121 with it. It used to be measured off the road strip, which was the lowest
# thing above it; the strip is inside the band now and the picture's own foot is the edge the
# cards stand clear of.
ART_Y = BACKDROP_Y + BACKDROP_H + GAP            # 256

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
ART_W = 3 * SLICE_W + 2 * TILE_GAP               # 494, three of the ribbon's columns
# AND 2:1 IS BACK, which is the whole reason to prefer this width. The masters are generated at
# 2:1, so at 494 x 247 `fit: cover` crops nothing -- what the generator drew is what the card
# shows, end to end. The earlier 579 x 205 was 2.82:1 and threw away 30% of every illustration.
ART_H = ART_W // 2                               # 247, exactly half

# Show Map, Hire Building and the City stay one tile wide, under Allocation. THEY NO LONGER LINE
# UP WITH THE TITHE, and that is the cost of centring the row: the Tithe moved with the cards to
# TITHE_X and this column stayed on the board's right margin, so the two are 93 apart. It is the
# one visible seam in this arrangement and it is deliberate -- a row aligned to the ribbon and a
# column aligned to the margin cannot both be had.
SIDE_W = SLICE_W
SIDE_X = X0 + WORK_W - SIDE_W

ART_GAP = GAP

# THE CARD ROW STARTS ON THE FIRST TILE'S LEFT EDGE. It began at that tile's CENTRE for a while,
# so the row read as hung beneath the eight rather than butted against them -- and the price was
# that nothing on the board shared a vertical line with anything else. The cards line up with the
# ribbon now: Clerical's left edge and Devotion's left edge are the same x, which is the one
# alignment a player's eye can actually use.
#
# THE CONTROLS DO NOT COME WITH IT. They sit on Allocation's mark, because that is what they are
# made of; so pulling the row 77 to the left opens a gap between the Tithe and the column rather
# than dragging the column off the tile it belongs to.
ROW_X = X0                                       # 28, Clerical's left edge

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

    THE PAIR IS CENTRED IN THE TILE, which has been three different claims as the tile changed
    shape. It hung from the duty's name at one inset while the tile was exactly as tall as the
    pair asked for: one inset everywhere, nothing left over, nothing to centre. Then the mark
    shrank and the tile kept its height, leaving 56 spare, and hanging would have put all 56 below
    the lower mark -- a pair sitting high in a box that looks nudged. So it was centred in the
    room UNDER THE NAME.

    THERE IS NO NAME NOW AND NO ROOM UNDER IT: the tile is the two marks and TILE_PAD, so the
    room is the whole inner box and the centring comes out at exactly TILE_PAD on every side. The
    rule did not change, its input did -- which is the point of having written it as a centring
    rather than as an inset.
    """
    room = TILE_INNER_H
    pair = 2 * SEAL + SEAL_INSET
    top = (room - pair) // 2
    x = (TILE_INNER_W - SEAL) // 2
    # EVERY FIRST MARK ON THE SAME LINE, WHATEVER THE TILE HOLDS. A single mark used to be centred
    # in the space it had, which put Taxation's and Allocation's half a mark lower than the top
    # mark of every tile beside them -- and on a ribbon of eight that reads as two tiles done
    # wrong rather than as two tiles that are different. One mark goes where the FIRST of two
    # goes, so where a mark sits stops depending on how many the tile has.
    #
    # WHICH LEAVES TAXATION AND ALLOCATION BOTTOM-HEAVY, and that is now visible in a way it was
    # not: their box is drawn round a pair that is half empty, so the frame hugs nothing at the
    # foot. It is still the right trade -- eight boxes of one height with their first marks on one
    # line beats two boxes that are shorter than the rest -- but it is a trade, not a free lunch.
    if n == 1:
        return [{"x": x, "y": top, "size": SEAL}]
    if n == 2:
        return [{"x": x, "y": top, "size": SEAL},
                {"x": x, "y": top + SEAL + SEAL_INSET, "size": SEAL}]
    raise SystemExit("a duty with %d actions has no seal arrangement here" % n)


# HOISTED FOR THE SAME REASON seal_slots() IS, and it is the other half of the same answer. The
# controls column is placed off Allocation's MARK, and a mark's board position is now two steps
# from the pitch rather than one: the slice, then the tile centred in the slice, then the mark
# centred in the tile. tiles() wants this and so does MARKS_X, which is declared above tiles() --
# so either the expression is written twice and allowed to drift, or the thing that owns it goes
# in front of both. This is the thing that owns it.
TILE_IN_SLICE = (SLICE_W - TILE_W) // 2          # 40, the air each side of a tile in its column


def tile_x(i: int) -> int:
    """Where the i-th duty's tile opens, in board coordinates.

    CENTRED IN ITS COLUMN, which is what keeps every mark on the pixel it already occupied. The
    mark was centred in a tile that filled the column; the tile is 74 now and centred in that
    same column, and the mark is centred in the tile -- so two centrings compose to the one the
    board had before, and nothing on the ribbon moves sideways. check() asserts it rather than
    leaving it to this comment.
    """
    return X0 + i * TILE_PITCH + TILE_IN_SLICE


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

# A MARK HERE IS A TILE'S MARK, FULL STOP. It was SEAL less the frame, back when a tile's mark
# wore one and a control did not, so that the same emblem came out the same size in both places.
# Neither wears a frame now, so the correction has nothing to correct and the two are one number.
MARK = SEAL                                      # 50
# AND THE AIR BETWEEN THEM IS THE TILE'S INSET, for the same reason. It was SEAL_INSET plus two
# frames, because that was the CLEAR space between two framed pictures; with no frames the clear
# space and the box gap are the same 6.
MARK_AIR = SEAL_INSET                            # 6
MARKS_W = MARK

# ---- and the box round each one ---------------------------------------------------------------
# THE THREE USED TO STAND ON NOTHING. Every other object in the action row has a ground -- the
# cards are pictures, the Tithe is a .panel -- and the controls were bare artwork on the canvas,
# which is black here because the backdrop ends at the foot of the ribbon, well above this row.
#
# IT IS THE TITHE'S PANEL AND NOT THE DUTY TILE'S PLATE, which was the other candidate and is
# wrong twice over. A tile is GLASS, 55% of --plate over the picture behind it; there is no
# picture behind this row, so the same treatment carried down is 55% of a dark colour over black
# and very nearly invisible. And a tile means "selectable, takes the gold rim when chosen" --
# Show Map and Hire Building are never chosen, so it would promise a state they cannot enter.
#
# THE PAD IS THE BOARD'S INSET, and it is what forced this into geometry rather than leaving it
# a CSS flourish. Two 6s round two marks is 12 of box where the column has 6 of air, so boxes
# drawn around the marks WHERE THEY STOOD would have overlapped by 6. The fix is to say what the
# column is a column of: it is three BOXES, MARK_AIR apart, each holding a mark. The marks move
# apart to suit the boxes rather than the boxes being squeezed to suit the marks.
CONTROL_PAD = INSET                              # 6
CONTROL_BOX = MARK + 2 * CONTROL_PAD             # 62
# NO MARKS_H. It was len(MARKS_ORDER) marks plus their air -- the height of one even stack -- and
# the column is not one stack any more. Keeping it would have left a constant that reads like the
# column's height and is not, which is the kind of fact that survives a refactor by being nearly
# right. mark_slots() knows where the three marks are; nothing else needs a total.

# ALLOCATION'S MARK, asked of the tile rather than retyped. seal_slots() places a mark inside its
# tile and the tile is placed on the pitch, so this is the one expression that survives the ribbon
# changing width, the seal changing size, or a ninth duty arriving.
MARKS_X = (tile_x(TILES - 1)                     # the eighth tile's left edge
           + BORDER + seal_slots(1)[0]["x"])     # its mark, inside the border
ROW_END = MARKS_X + MARKS_W                      # 1320
ROW_W = ROW_END - ROW_X                          # 1292

# THE TITHE IS DECLARED NOW, NOT WHAT THE ROW HAS LEFT. It was the remainder for as long as the
# row was packed edge to edge -- cards, gap, cards, gap, Tithe, gap, controls -- so its width was
# whatever the others did not want. The row is not packed any more: it starts at the first tile's
# LEFT EDGE rather than its centre, which pulls the cards and the Tithe 77 to the left, while the
# controls stay on Allocation's mark because that is what they are. The slack lands between the
# Tithe and the controls, where it is visible and intended, instead of silently resizing the
# Tithe. check() reports it rather than deriving it away.
#
# AND IT IS ONE DUTY'S COLUMN WIDE, which is where 154 comes from and why it is SLICE_W rather
# than a number. It was 120 while it held three resource discs in a stack and 120 was what the
# packed row had left; the discs are gone, so the only thing still asking for a width is the
# eye. One column of the ribbon is the width every other object on this board is built out of --
# the cards are three of them, the tile used to be one -- so the Tithe is one of them too.
TITHE_W = SLICE_W                                # 154
TITHE_X = ROW_X + 2 * ART_W + 2 * ART_GAP        # 1048
ART_RATIO = ART_W / ART_H                        # 2.0 exactly

# The action NAME is printed on the picture, top left. The effect line is NOT: it moved off the
# artwork into the top box, which halved the scrim count and gave the bottom of every picture
# back -- the corner the briefs now reserve for the close dark foreground element.
CAP_SIZE = 14
CAP_PAD_X, CAP_PAD_Y = 10, INSET
CAP_LH = 1.2
CAP_TEXT_H = round(CAP_SIZE * CAP_LH)             # 17, one line of caption
CAP_H = round(CAP_PAD_Y * 2 + CAP_SIZE * CAP_LH)  # 29, the band the line sits in

# WHERE THE TITLES' FEET FALL, AS A BOARD POSITION. Named because something outside this row now
# hangs off it -- the two standing controls line up on it -- and the alternative was that other
# object re-deriving ART_Y + BORDER + CAP_PAD_Y + CAP_TEXT_H for itself, which is the same
# arithmetic in two places and the usual way two things stop agreeing.
#
# THE TEXT'S FOOT, NOT THE BAND'S. CAP_H's 29 includes the padding under the line, so the band
# ends at 270 while the lettering stops at 265. The thing the eye lines up on is the lettering.
CAP_TEXT_FOOT = ART_Y + BORDER + CAP_PAD_Y + CAP_TEXT_H   # 265

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
TITHE_LABEL_SIZE = CAP_SIZE
# ONE PIXEL HIGHER THAN THE CAPTION'S INSET, and that pixel is the panel's border. The action card
# has no border, so its caption at a 6 starts 6 below the top of the card; the Tithe is a bordered
# panel, so a child at a 6 starts 7 below the top of the box. Measured on the rendered page: the
# two titles came out 283.4 and 284.4. This is the fault test_a_bordered_box_measures_its_children
# _inside_its_border already names, met once more.
TITHE_LABEL_TOP = CAP_PAD_Y - BORDER
TITHE_LABEL_H = CAP_TEXT_H                               # 17, the caption's own line

# THE THREE RESOURCES ARE OFF THE BOARD, AND SO IS EVERYTHING THAT PLACED THEM. TOKEN,
# TOKEN_SPREAD, TOKEN_ORDER, token_cap() and token_slots() are all deleted, with their guards.
# The Tithe is a labelled box now and what goes in it is an open question.
#
# WHAT WENT WITH THEM IS WORTH NAMING, because it was the hardest-won arithmetic in this file and
# somebody will want it back if the discs return. token_cap() answered "how big may a Tithe
# resource be", and the answer was NOT simply the mark's size: three of them in a column had to
# fit the box's HEIGHT, which is ART_H, a number chosen for the artwork rather than for them. Its
# width term spent a long time dividing by two -- left over from a side-by-side arrangement -- and
# agreed with the right answer by luck until the Tithe narrowed to 120, at which point the discs
# silently went from 66 to 50. That is the shape of fault that argues for deriving a size instead
# of typing one, and git has the function if it is ever needed again.
#
# TITHE_INNER_W_PRE WENT TOO. It existed only because token_cap() needed the box's inner width
# before TITHE_INNER_W could be stated, which is a cycle the discs created and nothing else wants.

# THE GAP IS WHAT IS LEFT, which is the only honest way round. It was the rule that kept a column
# of three discs and a label inside a box that could not hold both at their stated sizes: lay the
# fixed parts out and let the gap take the remainder, rather than picking a gap and hoping, which
# is how the label gets quietly pushed out of the box. Nothing is laid out in here any more, so
# the box's inner size is all that is left of it.
TITHE_INNER_W, TITHE_INNER_H = inner(TITHE_W, ART_H)         # 152 x 245

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
CITY_LABEL_H = round(CITY_LABEL_SIZE * LABEL_LH)

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

# THE WHEEL IS WIDTH-BOUND NOW, AND THAT IS A CHANGE OF WHICH CONSTRAINT BINDS. It used to take
# whatever vertical space the board had left -- height first, width from the asset's ratio -- and
# it came out 1027 in a column 1174 wide, 147 short of filling it. Taking a whole row out of the
# stack handed it another 121 of height, which it cannot use: at 665 tall it would be 1255 wide
# against a column of 1174, and check()'s play-column guard would refuse it.
#
# SO THE COLUMN SETS THE SIZE AND THE FOOT SETS THE POSITION. The wheel fills its column exactly,
# takes its height from the asset's own ratio, and stands one GAP off the canvas's foot like
# everything else on this board.
WHEEL_W = PLAY_W                                 # 1174, the column, filled
WHEEL_H = round(WHEEL_W * WHEEL_RATIO)           # 622
WHEEL_X = X0 + (PLAY_W - WHEEL_W) // 2           # 28, which is X0 now that it fills the column
WHEEL_Y = CANVAS_H - GAP - WHEEL_H               # 562

# AND THE SLACK FALLS ABOVE IT, between the cards and the wheel. The wheel can no longer absorb
# every pixel the layout frees, so what it cannot use lands here -- which is the one place on
# this part of the board where air reads as deliberate rather than as a mistake, since the cards
# and the wheel are different kinds of thing. gaps() leaves it out of the 16-or-32 rule for the
# same reason the Tithe-to-controls slack is left out, and check() holds it to GAP_WIDE or more.

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
    """Where each duty's tile opens, in wheel order, so the ribbon's order IS the wheel's.

    IT IS NO LONGER THE COLUMN. The tile used to BE the slice -- full width, full band height --
    so this was the pitch and nothing else. It is a 74 x 130 box now, centred in its column and
    hanging 39 below the top of the band, and the column it stands in is not drawn at all.
    """
    return {slug: {"x": tile_x(i), "y": TILE_Y, "width": TILE_W, "height": TILE_H}
            for i, (slug, _n, _d) in enumerate(DUTIES)}


def mark_slots() -> dict:
    """The controls, which are TWO groups in one column and used to be one stack of three.

    THEY ARE NOT THREE OF A KIND, and spacing them as though they were said they are. Show Map and
    Hire Building are always on the board; the commit appears only once an action has been chosen.
    Evenly stacked, the commit arriving read as a third item joining a list -- the eye had no
    reason to treat the new thing as different from the two that had been there all along. The
    whole value of that mark is that its appearance is news.

    SO THE STANDING PAIR GOES TO THE TOP OF THE ROW AND THE COMMIT STAYS AT THE FOOT, and the
    space between them is what makes the arrival legible. It is not a gap in the board's sense --
    see check(), which holds it to GAP_WIDE or more and reports it, the same treatment the
    Tithe-to-controls strip gets.

    THE PAIR LINES UP ON THE TITLES, not on the top of the row. CAP_TEXT_FOOT is where "Construct
    Building", "Construct Road" and "Take Tithe" stop, and the pair hangs one MARK_AIR above it,
    so the column's own internal air is also the air between the titles' line and the first mark.
    That is the only number in this function that is a choice, and it is the column's own.

    THE BOX IS WHAT IS PLACED NOW, AND THE MARK SITS IN IT. Every y here is a box top; the mark
    is CONTROL_PAD inside. That is the change the ground brought with it -- a box round a mark
    where it stood would have overlapped its neighbour, since two pads is 12 and the column's
    air is 6 -- and it is also the more honest statement of what the column is.

    WHICH MOVED TWO MARKS AND NOT THE THIRD. The commit's box foot is the row's foot, so its
    mark lands at exactly the 432 it already had; the two standing marks come down by the pad.
    """
    standing = MARKS_ORDER[:-1]
    pitch = CONTROL_BOX + MARK_AIR
    # THE FIRST BOX ON THE TITLES' LINE, which is what CAP_TEXT_FOOT is named for. It is the BOX
    # that lines up with the lettering now rather than the mark, because the box is the object
    # the eye sees -- a mark aligned inside a box that is not would look like neither.
    top = CAP_TEXT_FOOT - MARK_AIR
    boxes = {name: top + i * pitch for i, name in enumerate(standing)}
    # AND THE LAST BOX'S FOOT IS THE ROW'S FOOT, which is a sharper rule than the mark's old one
    # and a visible alignment rather than an arithmetic one: the commit's lower edge now lands on
    # the same line as the bottom of both action cards and the Tithe panel. The old rule held the
    # MARK a MARK_AIR above that line, which was the tile's habit borrowed into a row that has no
    # tiles in it.
    boxes[MARKS_ORDER[-1]] = ART_Y + ART_H - CONTROL_BOX
    return {name: {"x": MARKS_X, "y": boxes[name] + CONTROL_PAD,
                   "width": MARK, "height": MARK,
                   "box": {"x": MARKS_X - CONTROL_PAD, "y": boxes[name],
                           "width": CONTROL_BOX, "height": CONTROL_BOX}}
            for name in MARKS_ORDER}


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
        # NO nameSize, nameTop OR nameLh. The duty names are off the board, and a size published
        # for text nobody prints is the kind of leftover that gets read by something later and
        # believed. The TILE'S OWN HEIGHT is published now, which the band's height used to
        # answer for; so is the corner, so the stylesheet has no radius of its own to disagree.
        "ribbon": {"y": RIBBON_Y, "height": RIBBON_H, "tileW": TILE_W, "tileH": TILE_H,
                   "tileY": TILE_Y, "tileGap": TILE_GAP, "sliceW": SLICE_W,
                   "pitch": TILE_PITCH, "radius": TILE_RADIUS, "pad": TILE_PAD,
                   # THE FRACTION AS WELL AS THE PIXEL, because the icon lab draws tiles at
                   # sizes this board does not: a 9 copied onto a tile of 120 is the corner
                   # of a different box. The board uses the pixel, the lab the fraction.
                   "radiusFrac": TILE_RADIUS_FRAC,
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
        # NO `size` HERE. It was published beside the rects and read by nobody -- the rects each
        # carry their own width and height, which is what a drawing needs, so the extra key was a
        # second statement of the same number waiting to disagree with it. That is the fault this
        # tree already has an open note about elsewhere (`--frame`, set by the icon picker and read
        # by no rule), and it is cheaper to not start a second one.
        "marks": dict(mark_slots(), order=list(MARKS_ORDER), pad=CONTROL_PAD),
        "side": {"x": SIDE_X, "width": SIDE_W},
        # THE TITHE IS A LABEL AND A BOX. `token`, `order`, `spread` and `slots` are gone with the
        # three resource discs: a page handed the positions of things that are not drawn is a page
        # one line away from drawing them again.
        "tithe": dict(TITHE, labelSize=TITHE_LABEL_SIZE, labelH=TITHE_LABEL_H,
                      labelTop=TITHE_LABEL_TOP, lh=CAP_LH),
        "city": dict(CITY, labelSize=CITY_LABEL_SIZE, labelH=CITY_LABEL_H, labelTop=INSET,
                     lh=LABEL_LH, figures=city_figures()),
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
    # THE COLUMNS, ASKED OF THE PITCH RATHER THAN OF THE TILES. This read the tiles' own x, which
    # was the same thing while a tile filled its column and is not any more -- see the loop below.
    order = [X0 + i * TILE_PITCH for i in range(len(DUTIES))]
    # The board's outer MARGIN is X0 and is not a gap -- check() asserts the column lands on it.
    g = {
        "status -> ribbon": RIBBON_Y - (STATUS["y"] + STATUS["height"]),
        # NO "ribbon -> road". The strip is INSIDE the band now -- it is the part of the valley
        # below the tiles -- so the distance between them is not a gap, it is zero by
        # construction, and measuring it reported -55 the moment the road moved up.
        "picture -> art": ART_Y - (BACKDROP["y"] + BACKDROP["height"]),
        "wheel -> canvas foot": CANVAS_H - (WHEEL_Y + WHEEL_H),
        # MEASURED FROM THE ROW, NOT THE MARGIN. These two read 93 the moment the row moved
        # off X0 and onto the first tile's centre -- the gaps had not changed at all, the
        # thing they were measured from had.
        "card A -> card B": art_slots()["actionB"]["x"] - (ROW_X + ART_W),
        # THE BOX BESIDE THE CARDS IS THE TITHE, NOT THE COLUMN BELOW IT. Measured to SIDE_X
        # this read 186 -- the distance to a box three rows further down, which is not a gap
        # anybody can see.
        "cards -> tithe": TITHE_X - (ROW_X + ART_W + ART_GAP + ART_W),
        # NO "cards -> wheel" EITHER, and that one is a loss rather than a tidy-up. It was 16 for
        # as long as the wheel took whatever height the board had left; the wheel fills its
        # COLUMN now and cannot grow past it, so what the layout frees and the wheel cannot use
        # falls in that space. check() holds it to GAP_WIDE or more and reports it, which is
        # exactly how the Tithe-to-controls slack is handled.


        # No "seal -> seal" here any more. The two seals OVERLAP by design, so the distance
        # between them is not a gap and holding it to GAP would have forced them back into a row
        # they do not fit in. check() asserts the overlap is a corner instead.
    }
    # THE COLUMNS, NOT THE DRAWN TILES, AND THE DIFFERENCE IS NEW. These were the same measurement
    # while a tile filled its column. The tile is 74 in a column of 154, so the air between two
    # drawn boxes is 96 -- and 96 is not a gap this board has, nor should it be: it is what is
    # left over from a box being smaller than its column, which is a consequence rather than a
    # spacing decision. What IS a spacing decision is the column, and the columns are 16 apart.
    #
    # REPORTING THE 96 INSTEAD would put a third distance in a board that has two, and the honest
    # fix would then be to call 96 a gap -- which would mean the eight boxes could be any width at
    # all and still satisfy the rule, since the leftover would simply be whatever it was. The
    # claim worth keeping is that the eight COLUMNS are evenly spaced at the board's own gap, and
    # check() separately asserts the box is centred in its column.
    for i in range(1, len(order)):
        g["column %d -> %d" % (i, i + 1)] = order[i] - (order[i - 1] + SLICE_W)
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
    if SLICE_W * TILES + TILE_GAP * (TILES - 1) != WORK_W:
        bad.append("eight tiles and seven gaps come to %d, not the working width %d"
                   % (SLICE_W * TILES + TILE_GAP * (TILES - 1), WORK_W))
    if SIDE_X + SIDE_W != CANVAS_W - X0:
        bad.append("the column ends at %d and the status bar at %d"
                   % (SIDE_X + SIDE_W, CANVAS_W - X0))
    if CITY_Y + CITY_H != WHEEL_Y + WHEEL_H:
        bad.append("the City ends at %d and the wheel at %d, so they are not on one baseline"
                   % (CITY_Y + CITY_H, WHEEL_Y + WHEEL_H))
    # THE TITHE'S THREE RESOURCES HAD FOUR GUARDS HERE and all four are gone with them: the discs
    # centred in their box, the label clear of the first, the last clear of the foot, and the
    # discs clearing each other at SOLID_FRACTION. They were about an arrangement, and there is no
    # arrangement -- the box holds a label. The one thing still worth asserting about it is that
    # the label fits, which is below with the rest of the Tithe.
    #
    # THE LABEL IS ALL THAT IS IN THE BOX, so the only way it can be wrong is by not fitting the
    # width it has. It never could before -- the box was built round discs that were wider than
    # any word in it -- and at 154 it still cannot; but the box is now sized by the ribbon's
    # column rather than by its contents, so nothing except this would notice it narrowing.
    if TITHE_LABEL_H > TITHE_INNER_H:
        bad.append("the Take Tithe label is %d tall in a box %d deep"
                   % (TITHE_LABEL_H, TITHE_INNER_H))
    # THE ROW STANDS ON THE RIBBON'S FIRST COLUMN, which is the claim this layout makes and the
    # one thing no other guard here would notice going wrong. It stood on the tiles' CENTRES for
    # a while, and this line is the whole difference between that arrangement and this one.
    #
    # ON THE COLUMN, NOT ON THE DRAWN TILE, AND THAT IS A REAL CHANGE. They were the same x while
    # the tile filled its column. The tile is 74 now and centred, so its left edge is 40 to the
    # right of this and the card no longer lines up with anything you can see -- it lines up with
    # where the ribbon begins, which is also where the backdrop begins and what the cards' own
    # width is three of. Aligning to the drawn box instead would push the row 40 right and leave
    # 28 before the controls, under GAP_WIDE, which the slack guard below would refuse.
    if ROW_X != X0:
        bad.append("the row's left edge is at %d and the ribbon's first column opens at %d"
                   % (ROW_X, X0))
    # AND EVERY TILE IS CENTRED IN ITS COLUMN, which is what keeps the marks where they were. Two
    # centrings compose -- tile in column, mark in tile -- and if either drifts the eight emblems
    # slide sideways while every box still looks correctly placed.
    t = tiles()
    for i, (slug, _n, _d) in enumerate(DUTIES):
        left = t[slug]["x"] - (X0 + i * TILE_PITCH)
        right = SLICE_W - TILE_W - left
        if abs(left - right) > 1:
            bad.append("%s's tile sits %d from one side of its column and %d from the other"
                       % (slug, left, right))
            break
    # AND THE TILE FITS THE BAND IT HANGS IN. The band's height is declared and the tile's is
    # derived, so the two can part company in either direction: a bigger mark overflows the band,
    # and a smaller one leaves air that nobody chose. The air is reported either way.
    below = RIBBON_H - (TILE_Y - RIBBON_Y) - TILE_H
    if below < 0:
        bad.append("the tile hangs %d into the band and is %d tall, which is %d past the band's "
                   "%d" % (TILE_Y - RIBBON_Y, TILE_H, -below, RIBBON_H))
    # AND IT HANGS ONE GAP UNDER THE STATUS LINE, not at a distance of its own. The margin above
    # the ribbon is the one edge visible up here now that the picture reaches the canvas top, so
    # it is the one distance on this part of the board that can look wrong.
    if TILE_Y - (STATUS["y"] + STATUS["height"]) != GAP:
        bad.append("the tiles sit %d under the status line and the board's gap is %d"
                   % (TILE_Y - (STATUS["y"] + STATUS["height"]), GAP))
    # AND THE SLACK IS WHERE IT WAS PUT. Pulling the row onto the tile's edge moved the cards and
    # the Tithe 77 left while the controls stayed on Allocation's mark, so the room they used to
    # share falls between the Tithe and the column. That is the intent; what would not be is the
    # gap drifting, or the Tithe growing back into it, so it is held to what it was accepted at.
    #
    # ASSERTED AS A FLOOR, NOT AS A NUMBER. It comes to 102 today, and writing 102 here would be a
    # guard that restates its own input: the slack IS the remainder, so an expression reproducing
    # it could only be the same arithmetic again and would agree with anything the row happened to
    # do. What can go wrong is the two colliding, or the space shrinking back to a gap and losing
    # the separation it was opened for. That is what this holds.
    slack = MARKS_X - (TITHE_X + TITHE_W)
    if slack < GAP_WIDE:
        bad.append("the Tithe leaves %d before the controls column, which is less than the %d "
                   "that makes them read as separate things rather than a row"
                   % (slack, GAP_WIDE))
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
    # cleared the confirm row -- both of those objects have gone. The thing that would break it is
    # somebody raising SEAL.
    if len(DUTIES) != TILES:
        bad.append("the ribbon is built for %d tiles and there are %d duties"
                   % (TILES, len(DUTIES)))
    m = mark_slots()
    first, last = m[MARKS_ORDER[0]], m[MARKS_ORDER[-1]]
    if first["box"]["y"] < ART_Y or last["box"]["y"] + CONTROL_BOX > ART_Y + ART_H:
        bad.append("the controls column spans %d..%d and the action row is %d..%d"
                   % (first["box"]["y"], last["box"]["y"] + CONTROL_BOX, ART_Y, ART_Y + ART_H))
    # THE STANDING PAIR HANGS OFF THE TITLES' LINE. This is the whole reason CAP_TEXT_FOOT has a
    # name, and the fault it guards against is the quiet one: both numbers are plausible on their
    # own, so a caption that changed size would slide the lettering out from under the marks with
    # nothing rendering wrong.
    if first["box"]["y"] != CAP_TEXT_FOOT - MARK_AIR:
        bad.append("the standing controls' first box starts at %d and the titles' feet less the "
                   "column's own air is %d" % (first["box"]["y"], CAP_TEXT_FOOT - MARK_AIR))
    # AND THE MARK IS CENTRED IN ITS BOX. Derived, so check() can only agree -- which is the
    # point: the complaint exists for the edit that types a y over the derivation.
    for n, slot in m.items():
        b = slot["box"]
        if (slot["x"] - b["x"], slot["y"] - b["y"]) != (CONTROL_PAD, CONTROL_PAD):
            bad.append("the %s mark sits %d,%d inside its box and the pad is %d"
                       % (n, slot["x"] - b["x"], slot["y"] - b["y"], CONTROL_PAD))
        if (b["width"], b["height"]) != (CONTROL_BOX, CONTROL_BOX):
            bad.append("the %s box is %d x %d and a control box is %d square"
                       % (n, b["width"], b["height"], CONTROL_BOX))
    # AND THE PAIR IS EVENLY SPACED AND UNBROKEN, so "the standing controls" stays one object as
    # more of them arrive. Written as a loop rather than as hire-minus-map, which would stop
    # checking anything the moment a third standing control was added.
    standing = [m[n] for n in MARKS_ORDER[:-1]]
    for a, b in zip(standing, standing[1:]):
        apart_ = b["box"]["y"] - (a["box"]["y"] + CONTROL_BOX)
        if apart_ != MARK_AIR:
            bad.append("two standing control boxes are %d apart and the column's air is %d"
                       % (apart_, MARK_AIR))
    # THE COMMIT IS STILL AT THE FOOT, unmoved by any of this. It is the one mark a reader may
    # already have a position for, and the pair going up was explicitly not a reason to move it.
    if last["box"]["y"] + CONTROL_BOX != ART_Y + ART_H:
        bad.append("the commit's box ends at %d and the action row ends at %d"
                   % (last["box"]["y"] + CONTROL_BOX, ART_Y + ART_H))
    # THE SPACE BETWEEN THE TWO GROUPS IS DECLARED, NOT DISCOVERED -- the same shape of exception
    # as the Tithe-to-controls strip and the cards-to-wheel slack, and held the same way. It is
    # what makes the commit's arrival read as news rather than as a third item joining a list, so
    # what would break it is the space closing up, not its exact size. A floor, not a number: the
    # gap IS the remainder of the row, so writing today's 67 here would be a guard restating its
    # own arithmetic.
    apart = last["box"]["y"] - (standing[-1]["box"]["y"] + CONTROL_BOX)
    if apart < GAP_WIDE:
        bad.append("the commit sits %d under the standing controls, which is less than the %d "
                   "that keeps it from reading as a third item in their list" % (apart, GAP_WIDE))
    # AND IT STANDS ON ALLOCATION'S MARK, which is the claim the whole section is built on and the
    # one a later edit is most likely to break while everything still renders. Asked of the tile
    # here, exactly as MARKS_X asks it, so the two cannot drift: if this ever fails, the column has
    # stopped being the eighth tile's artwork carried down and is merely near it.
    art_x = tile_x(TILES - 1) + BORDER + seal_slots(1)[0]["x"]
    if MARKS_X != art_x or MARKS_W != SEAL:
        bad.append("the controls column is %d..%d and Allocation's mark is %d..%d"
                   % (MARKS_X, MARKS_X + MARKS_W, art_x, art_x + SEAL))
    # THE STRIP IT LEAVES AT THE RIGHT IS DECLARED, not discovered. Pulling the column off the
    # margin left 52px of board with nothing in it, and a guard that said nothing would let that
    # grow unremarked. It is not an arbitrary 52, though, which is the point worth holding: it is
    # exactly the margin Allocation's mark leaves to the right of itself inside its COLUMN, carried
    # straight down. The column of controls is the eighth tile's artwork and the strip is that
    # tile's own right margin; one fact, stated twice.
    #
    # MEASURED TO THE COLUMN'S EDGE, NOT THE TILE'S, WHICH IS WHERE THE TILE SHRINKING SHOWED UP.
    # These were the same number while a tile filled its column; now the mark leaves 12 inside its
    # 74px box and 52 inside the 154px column it stands in, and 52 is what the strip is. Reading
    # the box would have called a correct board broken by 40 pixels.
    # BOTH REMAINDERS, WHICH ODD SIZES MADE VISIBLE. There are two floor divisions between the
    # column's right edge and the mark's -- the tile centred in the column, the mark centred in
    # the tile -- and each can drop a pixel on the right. Re-deriving the margin with its own
    # halving agreed at a mark of 50, where both divide evenly, and was one out at 59. So the
    # right margin is measured as what is actually left rather than worked out a second time.
    strip = (X0 + WORK_W) - ROW_END
    want = ((SLICE_W - TILE_W - TILE_IN_SLICE)       # right of the tile, inside the column
            + BORDER                                  # the tile's own edge
            + (TILE_INNER_W - SEAL - seal_slots(1)[0]["x"]))   # right of the mark, inside the tile
    if strip != want:
        bad.append("the strip right of the controls column is %d and the tile's own right margin "
                   "round its mark is %d" % (strip, want))
    if WHEEL_X < X0 or WHEEL_X + WHEEL_W > SIDE_X:
        bad.append("the wheel spans %d..%d and the play column is %d..%d"
                   % (WHEEL_X, WHEEL_X + WHEEL_W, X0, SIDE_X))
    # THE WHEEL FILLS ITS COLUMN, which is the claim that replaced "it takes what height is
    # left". It is the binding constraint now: a wheel narrower than its column means the board
    # freed height the wheel could have used and did not, and the line above would not notice.
    if WHEEL_W != PLAY_W:
        bad.append("the wheel is %d wide in a column of %d, so it is not taking the room it has"
                   % (WHEEL_W, PLAY_W))
    if WHEEL_H != round(WHEEL_W * WHEEL_RATIO):
        bad.append("the wheel is %d x %d against the asset's own %.4f, so it is distorted"
                   % (WHEEL_W, WHEEL_H, WHEEL_RATIO))
    # AND THE SLACK ABOVE IT IS DELIBERATE AND AT LEAST A WIDE GAP. This is the space the wheel
    # cannot use, and it is the one distance on the lower board that is not 16 or 32 -- the same
    # shape of exception as the Tithe-to-controls strip, and reported for the same reason.
    slack = WHEEL_Y - (ART_Y + ART_H)
    if slack < GAP_WIDE:
        bad.append("the wheel stands %d under the cards and the widest gap this board has is %d"
                   % (slack, GAP_WIDE))

    # THE BACKDROP REACHES THE TOP OF THE CANVAS AND THE FOOT OF THE STRIP, which is the one thing
    # about it that can go wrong silently: it sits behind everything up here, so a backdrop a few
    # pixels short shows as a seam rather than as anything that fails.
    #
    # ZERO AT THE TOP, NOT RIBBON_Y. It used to start where the tiles start, and the two ends were
    # the ribbon and the road; the top end is now the canvas itself, so the status line has the
    # picture behind it rather than a black strip. A 0 typed into an assertion is usually a smell,
    # and here it is the claim: there is nothing above this.
    #
    # AND THE BAND'S FOOT AT THE BOTTOM, not the road's. They were different edges while the road
    # was a row of its own below the ribbon; the road is inside the band now, so the picture ends
    # where the band ends -- one tile-air below the tiles.
    if BACKDROP["y"] != 0 or BACKDROP["y"] + BACKDROP["height"] != RIBBON_Y + RIBBON_H:
        bad.append("the backdrop spans %d..%d and the canvas top to the band's foot is 0..%d"
                   % (BACKDROP["y"], BACKDROP["y"] + BACKDROP["height"], RIBBON_Y + RIBBON_H))
    # THE AIR UNDER THE TILES IS THE AIR BESIDE THEM, which is what sets the band's height and is
    # the whole of why the picture is 225 rather than 361. The first tile stands TILE_IN_SLICE in
    # from the picture's left edge because it is centred in its column; the picture ends the same
    # distance below its foot, so the tile's clearance reads the same at the shoulder and at the
    # foot. Stated here because RIBBON_H is declared and this is the claim it was written for.
    below = (BACKDROP["y"] + BACKDROP["height"]) - (TILE_Y + TILE_H)
    beside = tiles()["clerical"]["x"] - BACKDROP["x"]
    if below != beside:
        bad.append("the picture leaves %d under the tiles and the first tile stands %d in from "
                   "its left edge" % (below, beside))
    # WHICH IS THE SAME CLAIM AS THIS ONE, stated against the band rather than the picture. A
    # mark size that grows the tile past what the band holds has to be refused rather than
    # quietly accommodated, so the two numbers are kept agreeing by a guard, not an expression.
    if RIBBON_H != TILE_H + TILE_IN_SLICE:
        bad.append("the band is %d and the tile with its own side clearance under it is %d"
                   % (RIBBON_H, TILE_H + TILE_IN_SLICE))
    # AND IT STILL COVERS BOTH THINGS THAT STAND ON IT, asserted separately because the line
    # above would be satisfied by a picture that reached the canvas top and stopped short of the
    # ribbon -- the two ends it was originally written for.
    if BACKDROP["y"] > RIBBON_Y or BACKDROP["y"] + BACKDROP["height"] < RIBBON_Y + RIBBON_H:
        bad.append("the backdrop spans %d..%d and the ribbon it stands behind is %d..%d"
                   % (BACKDROP["y"], BACKDROP["y"] + BACKDROP["height"],
                      RIBBON_Y, RIBBON_Y + RIBBON_H))
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
            if s["y"] < SEAL_INSET:
                bad.append("a seal of a %d-action duty leaves %d above it and %d below it "
                           "inside a tile"
                           % (n, s["y"], TILE_INNER_H - s["y"] - SEAL))

    # TWO FAULTS, AND THEY ARE REPORTED SEPARATELY BECAUSE THEY ARE DIFFERENT FAULTS. The pair has
    # to sit centred in the tile, and it has to keep at least the tile's own inset at both ends.
    # One condition covered both while the two were the same rule -- hanging from the duty's name
    # at one inset left nothing over, so centred and inset-everywhere described the same
    # placement. They came apart when the tile kept its height and the mark shrank.
    #
    # THE MESSAGE WAS SAYING THE WRONG THING, which is how this was found: at a mark of 73 the pair
    # is centred to the pixel and merely too TIGHT, and the one complaint announced that it was
    # "not centred in the room the tile gives it". A guard that misnames what is wrong sends the
    # next reader to the wrong number.
    #
    # BOTH ARE NOW TRUE BY CONSTRUCTION AND BOTH ARE STILL ASSERTED. The tile is derived from the
    # mark, so the air comes out at TILE_PAD whatever the mark is -- which is exactly the state in
    # which a guard looks redundant and is not: it is the only thing standing between the tile's
    # derivation and seal_slots(), two expressions that have to agree and have no other reason to.
    last = seal_slots(2)[-1]
    under = TILE_INNER_H - (last["y"] + SEAL)
    above = seal_slots(1)[0]["y"]
    if abs(above - under) > 1:
        bad.append("the pair sits %d above and %d below inside a tile, so it is not centred in "
                   "the room the tile gives it" % (above, under))
    if min(above, under) < SEAL_INSET:
        bad.append("the pair leaves %d above and %d below inside a tile, tighter "
                   "than the %d the marks keep between themselves"
                   % (above, under, SEAL_INSET))

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
