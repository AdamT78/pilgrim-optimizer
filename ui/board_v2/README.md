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

## Duty action art workflow

Each duty's two actions are **one drawing, cropped twice**. A single wide master holds the whole
scene and the two production images are overlapping windows onto it. For Clerical the left window
is *Gain Piety* and the right is *Gain Coins*.

The overlap is the point. Two separately generated illustrations of "a priest at prayer" and "a
priest receiving coins" look like two pictures of two places; two windows onto one continuous
environment look like one place seen twice, and the shared middle ground is what the eye uses to
tie them together.

    generate → save master → crop → save action A/B → load the pair in the studio
    → judge at real game size → iterate

The master is archived permanently, and that is not housekeeping. A crop is reversible while the
master exists; a regeneration is not, because the same prompt does not produce the same picture
twice. When the slot dimensions change later, the master is re-cropped rather than the art
re-made. Masters and crops live under `duty_actions/<duty>/`, and the recipe, the naming
convention and the real crop geometry are in `../../tools/duty_art/README.md`.

**The art belongs to the ACTIONS, not to the left and right display slots.** It is stored as
`S.duties.clerical.actionA.scenic`, never as `duty.leftImage`. The two large boxes on the stage
own geometry -- position, size, fit -- and borrow whichever duty is previewed or reached. Moving a
box does not move an artwork's identity, and pointing both boxes at the same action is a display
choice rather than a change of ownership.

## Duty tile marks, and the icon lab

A duty's tile carries one small mark per action, and there are two kinds of them. They are filed
apart because they are not the same thing, and a tree that called them both seals would be saying
something that is not true.

`duty_actions/<duty>/seals/` holds the red wax discs. Nothing about one has to be decided: it is
drawn to fill its own square and `../../tools/duty_art/file_seals.py` scales every one to the
discs' 0.906 of it on the way in.

`duty_actions/<duty>/icons/` holds the cut-out emblems, which arrive as a 1254 square with the
mark somewhere inside it and a wide transparent margin. How much of that square the board draws,
and which part, is a judgement nobody can make from the file alone. It is made in `icon_lab/` and
written down in `icon_lab/framing.json`.

    python3 ui/board_v2/icon_lab/generate_icon_sizer.py --open

WHERE THE ICONS COME FROM. Every one of them was generated with ChatGPT, and that is on the record
rather than in a sentence somewhere: each file's entry in `attribution.json` carries
`creator: "Generated with ChatGPT (OpenAI)"` and `licence: "openai-generated"`, and the licence
itself is spelled out in that file's `licences` block with a link to the terms the rights come
from. The same is true of the wax seals and of every duty action card. So the question "may we
ship this, and who do we credit" has one machine-readable answer for the whole tree, which is what
that file is for -- and a guard in `tests/layout_lab/test_board_v2_attribution.py` makes a missing
entry impossible rather than merely unlikely.

`--open` builds and opens in one go, spelled the same way the action board's generator spells it;
without it the page is written and left at `icon_lab/generated/icon_sizer.html`.

**Three pages, three decisions.** The sizer above decides a mark's CROP -- how much of its
master the mark is. `generate_size_check.py --open` decides how big that mark is DRAWN, by
showing every one of them at a size you choose and at the scale your own window would give them.

    python3 ui/board_v2/icon_lab/generate_size_check.py --open

ITS OUTPUT IS A NUMBER, NOT A FILE, and that is a decision rather than an omission. What you take
away from it is a figure for `geometry.py`'s `SEAL`, which is the one place the board's sizes
live. It deliberately exports nothing: baking the drawn size into a file would take it away from
geometry.py, so changing one number would stop restyling the marks and start needing every one
re-cut; baking the ground would take it from the record's `ground` field and the single CSS rule
that owns that colour; baking a border would make a style into art; and a file at exactly its
drawn size is soft on a retina screen, which is why the board inlines every mark at `SEAL * 2`
instead. A guard in `tests/icon_lab/` holds it to being a viewer.

**The third decides WHERE a duty's two marks sit.**

    python3 ui/board_v2/icon_lab/generate_tile_column.py --open

The board put them on the diagonal, overlapping: that was designed for round wax discs, where one
resting on another reads as depth. The marks have corners now, and a corner cutting into a
neighbour reads as a mistake. THIS PAGE IS WHERE THE COLUMN WAS DECIDED, and the board has since
taken it, so the arrangement here is the one that ships; the levers are for asking what a
different gap or tile height would cost. Every number is `geometry.py`'s,
the mark's size included, so what is on screen is the board as it would be rather than a sketch of
one -- which is what lets the page answer the question worth asking: at the size the board really
draws, does a column of two fit the ribbon at all, and what would it cost if it does not.

AND IT SAYS WHO PAYS. Nothing below the ribbon shrinks when the ribbon grows -- it moves. `ART_Y`
is `RIBBON_Y + RIBBON_H + GAP` and the rest of the board follows down from there, so the action
cards and the confirm row keep their sizes and change their places. The wheel is the one elastic
thing on the board, because `WHEEL_H` is whatever the canvas has left over; it pays every pixel the
ribbon gains, and it keeps its asset's aspect, so it narrows by about twice what it loses in
height. The readout prices a height in the wheel's own width and height rather than as a count of
pixels, and so does the build, on every run.

The two levers are the gap and the tile's height. THE GAP DOES TWO JOBS: it is the space under the
duty's name as well as the space between the two marks, so the column hangs from the name at the
rhythm it keeps inside itself rather than floating in what is left over. That also puts the first
mark on the same line on all eight tiles, including Taxation and Allocation, which have a single
action each -- centring theirs in the leftover space sat it half a mark below its neighbours',
which read as a mistake on the two tiles that are different rather than as the difference itself.

THE HEIGHT IS A PROPOSAL, NOT `RIBBON_H`. The page opens at `START_H`, because the board as it
stands does not fit a column and opening on the board would mean opening on the problem every time
and dragging to the answer before you could look at anything. Nothing here moves the board:
`RIBBON_H` is untouched, and the readout prints it beside the proposed height so the two cannot be
confused. A guard holds `START_H` to a height the column actually fits at, since a proposal that
does not fit is worse than no proposal.

**The build step is not optional.** `generated/` is ignored (see `../.gitignore`), so a fresh
clone has the framing but not the page; running the generator is how one becomes the other. It
needs nothing but the standard library, and it seeds from the masters rather than the shipped
cuts, so a framing can be revisited any number of times and is still one trim away from the
generator's own pixels.

**A framing changes this page and nothing else.** `framing.json` decides what the cards show and
what the `cut` button hands back; the board draws the file sitting in `duty_actions/<duty>/icons/`,
which was cut under whatever framing was in force when somebody cut it. A framing that has been
saved but never cut and filed is a change you can see here and nowhere else, and each build prints
which ones those are.

The page also remembers your framing in the browser, so reopening it without rebuilding shows what
you last did. Those two can disagree, and the page does not choose quietly: the newer one wins,
the line under the buttons says which it is showing and how old the other is, and a button takes
the other instead. To make your framing the one the repository knows, press **save settings**,
move the downloaded `framing.json` into `icon_lab/` over the one already there, and build again.
Chrome will not overwrite a download -- a second save arrives as `framing (1).json` -- so check
`savedAt` at the top of the file if which is newest is ever in doubt.

## What is here

- `action_board/` -- the page the action-selection board is drawn on, and the generator that
  builds it from `geometry.py`, `duty_text.json` and the art in `duty_actions/`.
- `icon_lab/` -- the three pages that decide how a mark is presented: its crop, with
  `framing.json` holding the answer; how big it is drawn; and where a duty's two sit. See the
  section above.
- `duty_art_lab/` -- the viewfinder for cropping a duty's wide master into its two action
  cards, and `prompts/`, which is now the larger half of it: the briefs that produced the
  art, each kept word for word as it was sent. `prompts/` itself holds the templated
  two-panel briefs the viewfinder runs; `prompts/seals/` one file per wax seal;
  `prompts/panels/` one file per duty action card; and `prompts/icons/` the single brief
  that made every icon. `attribution.json` points at them by name. The cropping half is now
  history on both sides: every card was generated whole, and `crop_duty_master.py` itself has
  been removed. The viewfinder page still builds and still serves the briefs.
- `duty_actions/` -- the art itself, by duty: the action cards, the tile marks under `seals/`
  and `icons/`, and the untouched originals under each `masters/`.
- `tokens/` -- the three Tithe resources, in both the wax and the coin treatment.
- `attribution.json` -- provenance for every asset in this tree, and the shared facts the tools
  would otherwise each keep their own copy of: which folders hold marks, which are not actions,
  which file extensions to look for.
- `duty_text.json` -- every word the board prints.
- `docs/duty_wheel_spec.md` -- the design direction for the module.
- `docs/layout_lab_brief.md` -- the brief the layout lab was built from, kept because it
  records what was asked for and what was left to judgement.
- `layout_lab/` -- an interactive tool for deciding the module's geometry, currently at build
  4.2.1. See its own README.
- `docs/layout_lab_v2_brief.md` -- the V2 brief, kept for the same reason as the first.
- `docs/layout_lab_v3_brief.md` -- the V3 brief, which changed the layout concept.
- `docs/layout_lab_v4_1_brief.md` -- the V4.1 brief, four corrective fixes before the first
  commit. The V4, V4.2 and V4.2.1 briefs are not here: they were given in conversations whose
  history was compacted before they could be filed. What was decided in each is recorded under
  *Development history* in `layout_lab/README.md`, which states the intent and the invariants
  rather than reproducing prompts that no longer exist.
- `docs/webp_inlining_note.md` -- a measurement, not a change: what inlining the board's
  pictures as WebP instead of JPEG and PNG would cost and save, and the one trap in doing it
  (Pillow's WebP lossless is not exact by default). Nothing in the tree does this yet.

## What is not decided yet

The full-board canvas. The spec names 2039x1200 and 2283x1200 and deliberately leaves out
the 1600x1200 the game ships at today. With the module now 1400 wide the point is sharper
still: a 1400 module inside 1600 would leave 200px for everything else, less than two
reference cards. That implies the shipped canvas is being retired, which is a decision this tree
assumes rather than makes. The module leaves 639px beside it on 2039x1200 and 883px on
2283x1200.
