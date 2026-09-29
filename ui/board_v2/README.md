# board_v2

A second design for the game board, starting with the Duty Wheel, built apart from the
first so neither disturbs the other.

## Why it is separate

`tools/ui_debug/` holds the tooling for the board the game currently ships: a 3x3 grid of
duty tiles on a 1600x1200 canvas, tuned through `generate_placement_sheet.py` and played
through `generate_duty_sow.py`, with its numbers in `ui/assets-gothic/metadata/`.

This tree does not read or write any of that. Nothing here changes `duty_placement.json`,
`duty_grounds.json`, or any generated page under `tools/ui_debug/generated/`, and nothing
there reads anything here. The two designs can be worked on in the same checkout without
either becoming a constraint on the other.

## What is different about it

**Eight duties, and the City is not one of them.** The 3x3 board made the City the middle
cell, which put it in the ring as a ninth duty. The engine has never agreed: `merchant.py`
sets `CITY_POSITION = 0` and says the valid duty range is 1..8, and `pilgrim/io/view.py`
treats index 0 separately. So this is not a departure from the model -- it is the UI
catching up with it.

**A fixed module rather than a board-wide layout.** The wheel and everything around it is
composed inside a fixed area, which is then placed unchanged into whichever full-board
canvas is used. That makes the module's layout one decision instead of one per canvas
width. It started 1200x1200 and is now **1400x1200**. V3 spent the extra width on margins
either side of the wheel; V4 gave it to the wheel, which now opens 1372x727 and covers
about 59% of the module. The information that used to stand in those margins is a thin
band above it: eight reference cards, then the two action artworks, Tithe and the City.

**A finished wheel asset.** The layout lab draws the real v2 duty wheel -- the vector
geometry `tools/ui_debug/build_duty_wheel_v2.py` builds, at an aspect of 1.887 -- rather
than a stand-in. That is a rebuild rather than a squash: the faces come from the ellipse
and the spokes, so changing the aspect changes the geometry. The 1.778 baseline that tool
keeps is untouched, and the 1.887 layout sits beside it, regenerable the same way. Nothing downstream re-projects it; the layout only moves and uniformly
scales it, and the module's own geometry follows from the drawing's shape rather than the
other way round. Its own `viewBox` is the authority on that shape -- a drawing exported
for a board is typically `width="100%" height="100%"`, and a browser asked for the natural
size of one of those answers 300x150, a ratio of 0.5, which is close enough to a real
foreshortening to look plausible while being wrong.

The lab holds a checked-in COPY of the drawing rather than importing the builder: that
script parses argv at import time, needs numpy, and says in its own header that the aspect
is not settled, none of which should have to be true for a layout page to generate. The
refresh recipe lives in both files.

The copy keeps the builder's parchment colours and the lab recolours it into slate at
build time, because the drawing belongs to the first board design's palette and this one
composes against pure black. Hand-editing a generated file is how it stops being
regenerable, so the conversion lives where it can be seen and tested instead.

**Two actions per duty.** Each duty offers two action options and so owns two sets of
assets: a name, a short planning label, a wax seal and a scenic image each. The lab does
not model what the actions do; that is the engine's business.

**Three presentation states rather than one screen.** Ready, sowing and action selection.
The wheel, the eight reference cards, the acolytes, the instruction and the City are
identical in all three -- only the band above the wheel changes -- which is what makes the
three compositions comparable. While sowing, the City's region becomes the pool in hand.
During action selection the band holds exactly two large scenic images, supplied by the
duty the sow reached, with Tithe beside them as the alternative to both.

**Reading about a duty is not choosing one.** A reference card can be opened before any
choice is made, which shows that duty's two artworks badged as a preview, without Tithe and
without the treatment a real choice gets.

**An action owns assets, not geometry.** Sixteen large illustrations are never on screen
at once, so sixteen large geometries have no reason to exist. Two shared display slots own
the box and whichever duty is being shown lends them its pictures.

**Nothing on the wheel says which duty a space is.** How the eight physical spaces get
marked out -- engraved names, landmarks, emblems -- is a decision kept for later, so the
wheel carries the acolytes standing on it and nothing else.

## What is here

- `docs/duty_wheel_spec.md` -- the design direction for the module.
- `docs/layout_lab_brief.md` -- the brief the layout lab was built from, kept because it
  records what was asked for and what was left to judgement.
- `layout_lab/` -- an interactive tool for deciding the module's geometry, currently at V4.
  See its own README.
- `docs/layout_lab_v2_brief.md` -- the V2 brief, kept for the same reason as the first.
- `docs/layout_lab_v3_brief.md` -- the V3 brief, which changed the layout concept.
- `docs/layout_lab_v4_1_brief.md` -- the V4.1 brief, four corrective fixes before the first
  commit. The V4 brief itself is NOT here: it was given in a conversation whose history was
  compacted before it could be filed, and rebuilding it from the implementation would produce a
  document that agrees with the code by construction, which is the one thing a brief must not
  do. V4's design as built is described in `layout_lab/README.md`.

## What is not decided yet

The full-board canvas. The spec names 2039x1200 and 2283x1200 and deliberately leaves out
the 1600x1200 the game ships at today. With the module now 1400 wide the point is sharper
still: a 1400 module inside 1600 would leave 200px for everything else, less than two
reference cards. That implies the shipped canvas is being retired, which is a decision this tree
assumes rather than makes. The module leaves 639px beside it on 2039x1200 and 883px on
2283x1200.
