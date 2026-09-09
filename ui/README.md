# ui/

The Pilgrim UI redesign: generators that draw the board, an asset library, and the studies that
settled each decision. Nothing here is wired to the engine, and nothing in the game reads it — this
is where the next play view is designed before it is migrated.

**This is not `tools/ui_debug/`.** That directory holds the renderers the *current* game view is
actually drawn by, and it is the destination: moving a decision from here to there is what shipping
it means. The one live connection today is `render/gen_board_kit.py`, which imports the resource
pill's constants from `tools/ui_debug/render_player_boards_v2.py` so that a study's pill cannot
drift from the game's.

## Running it

    python3 ui/render/gen_board.py --open       # the assembled board
    python3 ui/render/gen_picker.py --open      # swap icons, portraits and frames on one card
    python3 ui/rebuild_ui_pages.py              # rebuild every generated page
    python3 ui/rebuild_ui_pages.py --check      # rebuild and report anything that moved

Both generators print the finished page as a `file://` URL; `--open` opens it. Run them from
anywhere — they locate the repository by looking for the renderer, not by counting directories up.

## Layout

    ui/
      render/       the generators. gen_board.py and gen_picker.py are the two entry points;
                    the rest are modules they import
      assets/       source material a generator cannot produce — icons, portraits, frames — with
                    its own README, licence record and checks
      inputs/       pre-rendered stages of the pipeline that gen_board.py composes
      generated/    the rebuilt pages. GIT-IGNORED
      studies/      frozen decision records, grouped by component. Never regenerated
      docs/         hybrid-svg-png.md, the rendering contract the assets are built to
      scratch/      upstream generators rescued from a temp directory, not yet portable

The split that matters is `generated/` against `studies/`. Both are HTML and they behave in
opposite ways: a generated page is rebuilt from its generator every run and is worthless the
moment it disagrees with it, while a study is a snapshot of a decision that will never be drawn
again. It is the same distinction `tools/ui_debug/` already draws between `generated/` and
`prototypes/`, and it uses the same words on purpose.

Because `generated/` is ignored, **`git diff` inside it reports nothing however much changed**.
That is the trade: no more committed outputs quietly going stale, but git no longer tells you when
one moves. `rebuild_ui_pages.py --check` is what replaces that signal, and it also fails on any
page in `generated/` that no generator writes — a page nothing rebuilds compares identical forever.

## Studies

Grouped by component: `alms/` (6), `market/` (10), `duty/` (5), `player-board/` (3), `misc/` (17).
They are read for intent, not edited. The sections below record what each one settled.

## desktop-fit.html

The target window is **1440 × 760** CSS px — a 13″ MacBook maximised in Chrome with a bookmarks
bar, and close enough to a Windows laptop at 1920/125 %. Bigger windows grow from there.

Board sizes are the viewBox of each renderer's current generated page. Height is the scarce
dimension, and the two boards that eat it are the duty wheel (1104 × 1425) and the map
(1014 × 1149) — both taller than wide. At the floor size, the player column (346), the wheel
(558 × 720) and a right column (456) holding the alms table over the market come to exactly
1440 with 20 px padding and gutters, and **the map does not fit as a column** — it needs 353 px
even at 400 tall, and 83 are left. So the map is the piece that yields: an overlay that comes
forward when acolytes move.

Reclaiming the piety track's 637 × 213 buys the alms table room; it does not by itself change
this.

**Superseded in one respect by `game-board.html`:** those wheel figures are the *old*
`render_duty_wheel` page, 1104 × 1425. The rail prototype the v2.0 table actually uses is
**square, 544 × 544**, which is far cheaper in the scarce dimension and is why the real layout
comes out better than this study predicted. The map conclusion still holds.

Open question recorded here rather than solved: a cube on the old duty wheel comes out **6.6 px**
at the floor size and 7.8 px at 1728 wide. That is a dot, not a cube — either the tally stops being
drawn as cubes at this scale, or the wheel needs more of the window than this layout gives it.

## player-board.html

Card 320×112. Portrait radius 44 at (26, 46), collar at 51, columns 118 / 196 / 274,
rows at y=45 and y=100, seal radius 21 at (57.7, 76.6).

Three things the card has to say, each said once and in one place:

- **whose seat** — the colour bar down the left, swelling into the collar that carries the
  portrait, so the seat colour is one continuous form from top to bottom;
- **whose turn** — the portrait disc fills with that seat's colour. No card carries a
  coloured border, and nothing else is outlined;
- **first player** — the gold wax seal on the portrait's lower-right rim, on exactly one
  board at a time.

The card and the collar are stroked as a *single* silhouette: the card's line stops where
the collar begins and the collar's line stops where the card begins. That is what stops the
portrait reading as a disc laid on top of the board.

Weak cases to watch: White active (a white disc on parchment is a soft mark and leans on the
dark silhouette), and Yellow holding the seal (gold against yellow is the least separation
in the set, though the seal sits on parchment rather than on the spine).

Values on the boards are hand-placed.

## market.html

Two real generated games — `generate_setup_scenario(2, seed)` with seeds 118 and 1086 —
whose draws share no building, so between them all 24 appear exactly once. The seeds were
found by searching 2,599 generated setups for a disjoint pair. The draw, the level split and
every live round are the generator's own; names, rule text, stone costs and donation VP are
verbatim from `configs/buildings.json`. Only *who owns what* is placed by hand, so that all
four seat washes appear.

Ownership is a top-band gradient of the seat colour; no wash means the building is still on
the map. The round number is boxed, green once the building has woken up and grey while it
is still coming.

## duty-wheel.html

The rail: each duty tile carries its own actions as clickable symbols, with the cube tally
still in the middle. Some tiles have one action, some two, and Construct has three. Two
variants differ in where the Tithe counter goes relative to the action rail.

Duty positions are shuffled per game by `_generate_duty_tiles`, so a tile cannot be
identified by its compass point — the prototype shows one dealt arrangement, not a fixed
layout.

## gen_portraits_svg.py

Four placeholder faces (`elder`, `tonsured`, `lank`, `ascetic`) drawn from scratch as
parametric paths, about 2 KB each. `portrait_svg(cx, cy, r, kind, ring=..., ground=...)`
returns a group clipped to a circle; `ground` is what takes the seat colour on the active
board. No third-party artwork is involved and nothing here is traced from any, so this is
free to ship. A real portrait replaces one by swapping the call — the board code does not
change.


## game-board.html

The whole table in one page, sized to the window: four player boards down the left, the duty
wheel in the middle, the market above the alms table on the right. Open it and resize — the
readout in the bottom-right corner reports the viewport, the wheel's drawn size, the market's
scale and the right column's width, which is what makes it worth opening on two screens.

Columns, left to right: the **alms panel above the four player boards**, the **turn panel**
(phase spine, the prompt with its buttons), the duty wheel, then the market with the **log in a
box beneath it**. The old alms table is gone.

The log moved out of the turn panel because the leftover space under the market measured
560 × 292 — an aspect of 1.9, which is log-shaped and not map-shaped. In the box it is about 2.5×
the area it had and nearly twice as wide, so entries stop wrapping. The panel keeps a single
**Last** line at its foot, so the acknowledgement of a click still appears next to the button that
caused it; the transcript lives where there is room for it. The panel also narrowed from 340 to
290, and those 50 px went straight to the duty wheel — 1185 → 1251 px drawn on a 3440 × 1318
screen.

Sizing, all in the page's own script. There is **one zoom for the whole table**:
`zoom = clamp(0.5, min(height / 760, width / 1900), 2)`. The design height stays 760 and the
design width is whatever the window gives back once zoomed, so extra width reaches the layout
instead of becoming letterbox. 1900 is what the five columns want (352 seats + 340 panel +
544 wheel + 560 right column + gutters, now 1850 with the narrower panel); below it the zoom drops under 1 and the whole table
shrinks together rather than one panel being starved — the market's small print is what pays.

Inside that design box the wheel takes `max(360, min(760, height − 40, width − 1352))`, the last
term keeping the right column at 560 or more; the market and alms table are set to one shared
width so their edges line up, capped by the height the two of them share, with the market's own
height measured at runtime rather than assumed.

Measured: 1440 × 760 → zoom 0.76, wheel 415 px drawn, market 90 %. 1920 × 1080 → zoom 1.01,
wheel 554, market 90 %. 3440 × 1318 → zoom 1.67, design 2062 × 790, wheel 1185, market 90 %. The
seats column (alms panel 144 + four boards 560 + gaps) comes to 732 of the 750 available.

**The turn panel moved the floor.** Before it, the table fitted a 1440 × 760 laptop at 1:1. With
it, the five columns want 1900, and at 1440 everything renders at 76 % — legible for the boards,
marginal for the market's rule text. The fix, when it matters, is the one already named for the
map: at narrow widths the market becomes a drawer rather than a column.

Panel content is written by hand — real phase and stage names from `_TURN_PHASE_ROWS` and
`_TURN_STAGE_ROWS` in `play_server.py`, but the prompt, the buttons and the log entries are
plausible sample text, not engine output. The hire question sits in its own banded lane below the
duty buttons, which is the placement discussed earlier: hiring always asked in the same place,
visually separate from the duty action it might pay for.

Three things were changed while composing, none of them in the source prototypes:

- **one palette.** The duty wheel prototype drew its own seat colours (#b23a2d, #d7b24a,
  #2f5e8e); they are mapped to the board palette (#B7382E, #D9B33B, #3B6EA5) so the same red
  means the same seat everywhere. Worth fixing at source.
- **the alms backdrop is dropped.** `render_alms_table` paints a black page backdrop that
  overhangs its panel by 18 units; on a green table that was a black rectangle, so the viewBox is
  cropped to the panel frame.
- **the seat SVG was cropped too tightly.** The collar reaches x = −25 and y = −5 but the box
  started at −22, −4, so the left of every portrait was shaved. The box is now
  `-30 -8 352 140`.
- **the market is re-skinned to parchment.** It was designed on a black page and read as a hole
  in the table. The `dark market` button switches back to the original for comparison — that is a
  real design choice, not a bug, so it is left switchable.

The `wheel B` button swaps the two rail variants; A is shown by default and nothing depends on
that choice yet.

Still open, visible in the page rather than argued about here: the alms table is the only grey
panel on a parchment-and-green table; the right column has roughly 280 design px of unused width
on an ultrawide; and the empty green under the seats and under the wheel is where the map will
have to go.


## alms-on-player-board.html

Can the alms table stop being a panel? Two facts have to survive: each player's position on the
0–6 track, which resets after each of the first three seasons, and how many acolytes they already
have on the alms table. From `configs/alms.json` the track pays at **2, 4 and 6** (serf to abbey,
acolyte to city, serf to city) and acolytes on the table score **0 / 5 / 11 / 18 / 26** — the
fourth is worth 8 by itself, so the count is not linear and is worth showing exactly.

- **V1 footer rail** — card 320 × 136. The whole track drawn along the bottom, gold at 2/4/6,
  the seat's disc on the current cell; wins as filled and empty cubes under the portrait with
  the VP they are currently worth. Most legible, and the only one that answers "how far to the
  next reward" without arithmetic. Costs 24 px of height per card — the column goes from 584 to
  680, against 720 available, so **it fits as things stand**.
- **V2 fourth column** — card 394 × 112. Two more pills in the card's own grammar: a glyph and a
  number. The alms glyph is a seven-rung ladder with the seat's bar on the current rung; the wins
  glyph is a 2 × 2 tray. Costs 74 px of width, which comes straight off the duty wheel.
- **V3 collar track** — card unchanged. The collar widens to 18 and becomes the track: seven
  notches on the portrait's north-west arc, gold at 2/4/6, position ridden by a numbered disc,
  wins as gold stars on the south-west arc. Free, and the least legible of the three — the notches
  read as ornament and at position 0 the marker floats off the card's left edge.

Shown with Red at 5 with 2 wins, Yellow at 0 with none, Blue at 3 with 1, White at 6 with 3.


## alms-rail-variants.html

The footer rail from `alms-on-player-board.html`, iterated. Wins and the "season" note are gone
for now — this is the track alone. Seven cells **24 px wide at 4 px gaps, spanning 100 → 292**,
which is exactly the width of the three resource pills above them, so the rail is a fourth row of
the same column rather than a strip floating under it. Card 320 × 150; the seats column comes to
712 against 720 available, so it still fits.

- **A the cell fills** — the box you stand on is filled with the seat colour and its number
  reverses out. Adds no new shape at all. On a gold step the gold survives as a thin inner rule.
  Weakest on White, where the fill is close to the parchment and only the heavier outline carries.
- **B the cell is ringed** — every box keeps its face; the current one gets a 3 px seat-coloured
  ring with a hairline outside it. Nothing is covered, so position and reward step read together.
  White rings in its darker tone, since a white line on parchment is not a line.
- **C filled to here** — every passed cell carries a 38 % wash and the current one is solid, so
  the rail reads as a bar: how far along, not just where. It answers whether 2 and 4 have already
  been passed this season, which neither of the others does. White's wash is nearly invisible.

Positions shown: Red 5, Yellow 0, Blue 3, White 6 — both ends and a gold step.


## alms-wins-tray.html

Rail **A** (the cell you stand on is filled with the seat colour) with the wins restored as four
places in one row of four, cubes at **18 px** — the same size as the serf and acolyte cubes above.

The tray needs its own row and the card cannot grow: four cards at 172 px already come to 712 of
the column's 720. So the two pill rows move up — row one from y 45 to 42, row two from 100 to 88 —
which buys a tray row at 140–158 inside the same 150 px card. That row shift is the one real cost
of putting the wins back.

Four placements: left-aligned under the track (tray, track and wheat pill share one vertical); the
same tray in a recessed slot; under the portrait, keeping the whole right side for the track; and
spread to span the track's full width.

Known weakness in all four: on White a filled cube and an empty place differ only by a dashed line
and a thin stroke, because the seat colour is nearly the parchment. The slot helps a little; a
darker stroke on White's cube would help more.


## alms-panel-board-width.html

The alms table stays a separate panel, narrowed to the player board's own width and set in the
same coordinate frame so the two share a left and a right edge. The player boards revert to
320 × 112 — no rail, no tray.

Panel is **320 × 132**. Eight columns across 296: seven for the 0–6 track and one for the
first-player disc, with the reward marker under 2, 4 and 6, the title and ornament rule as the
current renderer draws them, and the season-winners block replaced by **four win places in the
top-right corner** — cubes at 18 px, the size the boards already use. Shown in the renderer's grey
and in parchment for comparison.

**Resolved:** the panel is now at the *top* of the seats column in `game-board.html`, and the
zoom's design height moved from 760 to 790 to pay for it — about 4 % of scale on a screen whose
height is the binding constraint.


## alms-panel-speciality.html

The parchment panel, with three ways to say that **2 and 4 are spaces where something happens**
without saying what. Each is shown large, then in the column under the four boards at real size.

- **shaded ground** — the two columns are floored in a darker parchment for their whole height,
  with a short gold rule under the number. Nothing is added; the space is simply made of something
  else. Sits behind everything, so a seat disc standing on 2 does not hide the mark.
- **gold rosette** — a filled gold trefoil at the foot of the column, the same three-circle
  ornament the panel's own title rule carries, with the number in gold-dark. Most explicit, and
  borrows a shape the board already owns. It occupies the bottom of the column, which is where a
  fourth disc sits when all four seats stand on one space.
- **a niche** — the column is drawn as its own recessed panel with an inset hairline, the same
  idiom as the duty tiles. Reads as built rather than painted; heaviest of the three.

Resolved in `alms-panel-shaded.html`: all three reward rows — 2, 4 and 6 — carry the mark.


## alms-panel-shaded.html

The chosen mark. Shading only — no rule under the numbers — running exactly the height of the
column dividers (62 to 116), so a speciality space is the same shape as every other space and
differs only in what it is floored with. **2, 4 and 6** are shaded, matching all three reward rows
in `configs/alms.json`. It sits behind the discs, so a seat standing on 2 does
not hide it.

Two versions: numbers uniform, and 2 and 4 set a point larger. The numbers sit above the shading
on plain parchment, so with uniform numbers the mark lives entirely in the band.


### The Dune: Imperium comparison

What that game actually does, checked rather than assumed: its published system requirements
state **no resolution at all**; its window opens at **1200 × 800** (3:2), which is what players
report and try to change; and it **does not support ultrawide** — on 3440 × 1440 and 5120 × 1440
it draws black bars down both sides, with Dire Wolf saying only that they are "looking at
solutions". So the model is a fixed canvas, uniformly scaled, pillarboxed on anything wider.

`game-board.html` has a `fixed 3:2` button that switches to exactly that, using a 1900 × 1267
canvas — the width our five columns need, at Dune's aspect. Measured on 3440 × 1318:

| | zoom | wheel drawn | side bars |
| --- | --- | --- | --- |
| fit to window (current) | 1.67× | 1185 px | none |
| fixed 3:2 (Dune's model) | 1.04× | 570 px | ~625 px each side |

The fixed canvas costs 38 % of scale on that screen, because 3:2 is much taller than 3440 × 1318
(2.61:1) and the height runs out long before the width does. Kept as a toggle rather than adopted.

On that taller canvas the two flexible boxes stretched to fill it — the turn panel reached 1227
and the log box 769, both mostly empty parchment. They are now capped at **820** and **560**, which
never bites in fit-to-window mode (where they measure 750 and 284 on a 3440 × 1318 screen) and
stops them running the height of a canvas their content does not need.


### Why the duty wheel cannot get much bigger

Measured on 3440 × 1318: the wheel is drawn at **1278 px in a 1318 px window** — 97 % of the
screen's height. It is bound by `availH`, not by width, so freeing width by moving or hiding
another column does nothing for it. The one lever that helped was chrome: the stage's padding went
20 → 12, which is worth +27 px of wheel and nothing else.

Moving the market under the player boards does not fit: alms 144 + four boards 584 + market 488 =
**1216** against the 766 the column has. It would fit only if the market were re-laid with its
three shelves side by side rather than stacked — roughly 1870 × 180, a short wide strip along the
bottom of the stage. That is a change to the market prototype, not to this layout.

Letting the market run at its natural 624 instead of 91 % costs the wheel about 63 drawn px, since
the two compete for the same width once the wheel is at its cap.

`hide log` in the HUD toggles the log box, for comparing with and without.


### Two shared horizontals

The table now hangs on two lines rather than on the stage padding. The **top line** is the alms
panel's own top edge; the **bottom line** is the bottom edge of the last player board. An
`align()` pass after every layout puts three things on them:

- the duty wheel is nudged up so its **top duty tile** meets the top line — its SVG carries empty
  margin above that tile, so the wheel's own box starts above the stage and only the margin is
  lost;
- the turn panel's top meets the top line and its bottom meets the bottom line, so the panel spans
  exactly the height of the seats column's contents;
- the measurement is taken from the DOM each time rather than hardcoded, so it survives the wheel
  A/B switch, a different zoom, and any change to the card or panel geometry.

Verified at 3440 × 1318 (all three at y 33, bottoms at 1248) and 1920 × 1080 (y 21, bottoms 776).


### Market under the boards (now the default)

The seats column carries the whole left side: alms panel, the four player boards as a **2 × 2
block**, and the market beneath them. Measured on 3440 × 1318 (design 2062 × 790, 766 usable):

| | design | drawn |
| --- | --- | --- |
| alms panel | 362 × 148 | — |
| player board | 177 × 70 each | 296 px wide |
| market | 569 wide, 91 % | text 15.9 px |
| turn panel | 290 × 758, y 20 → 778 | — |

The boards had to halve — 352 → 177 — because the column's height is the constraint: alms 148 +
boards 149 + market 445 + gaps = 766 exactly. The market's width is now derived from whatever
height the boards leave it, so it can never push past the bottom of the canvas.

Two consequences worth knowing. **The log is hidden in this mode** — there is no room for a fourth
column once the market leaves the right side, and the `hide log` button still toggles it back if
you want to see the overflow. And **the wheel did not change**: 1278 px either way, because it is
bound by the stage height, not by the width the market freed.

`market right` in the HUD restores the previous arrangement.


## board-3-2.html

Designed for the fixed 3:2 view only, and solved from the type outwards rather than by nudging
sizes afterwards.

**The canvas is 1600 × 1067**, not 1900 × 1267. That is the whole trick: with a fixed canvas the
zoom is `min(w/1600, h/1067)`, so a smaller canvas renders everything larger. On 3440 × 1318 it
gives **1.235×** against the old canvas's 1.04× — a 19 % lift before a single font size changed.

Everything then falls out of one target: **body text ≈ 16 px rendered**.

| | design | rendered |
| --- | --- | --- |
| prompt, buttons | 13.5 | 16.7 |
| phase rows | 13 | 16.1 |
| phase headers | 12 | 14.8 |
| market tile name | 13.5 | 16.7 |
| market rule text | 12 | 14.8 |
| log entries | 13 | 16.1 |

The player boards are **scaled, not restyled**, so their resource figures land in the same band:
variant A draws them 314 wide for a **15.4 px** number, variant B 420 wide for **20.6 px**. Nothing
inside a board was retyped.

### A — everything on the table

Three columns: alms + four boards at 420 wide, the action box at 300, and a centre column of 816
carrying **the wheel with the market beneath it**.

The market lost its three "Level n" rows. What they carried that matters — build cost and donation
vp — is now one line in the title row (`L1 1 stone / 2 vp · L2 2 / 4 · L3 3 / 6`), and each tile
carries a small `L1`/`L2`/`L3` chip beside its round number. The twelve tiles are a single **6 × 2
grid** instead of three shelves of four, which is what makes the block short and wide enough to sit
under a square wheel. Tile names moved onto their own line so the narrower tiles do not truncate
them.

Wheel 610 design, **759 px drawn** — the market's 340 of column height is what it costs.

### B — the wheel leads

Boards at 420 wide in a single stack, alms to match, action box 300, and the wheel at 816 design —
**1008 px drawn**, a third larger than A. The market and the log become sheets that open over the
table from tabs in the top-right corner, at 100 % with no scaling at all. This is the arrangement
that treats the wheel as the board and the market as a catalogue you consult.

`variant B` / `variant A` in the HUD switches, `wheel B` swaps the rail variants, and `1:1` pins
the scale at 1.00 so every element is drawn at its true CSS pixel size — the honest way to judge
type, at the cost of the board no longer filling the screen.


## board-3-2-step1.html

A rebuild from nothing, one piece at a time. Step 1 is the alms table, the four player boards
under it, and the action box to their right — nothing else.

Everything is sized from a single decision: **the action box's body text is 13.5 canvas units.**
The two SVG components are then *scaled* so their own numerals come out the same size, rather than
restyled:

    component width = 352 × 13.5 / 14 = 339.4

because a player board draws its figures at 14 of its own units inside a 352-wide frame. The alms
panel's column numbers were raised from 13 to 14 so the same arithmetic covers it. Measured on
3440 × 1318 (zoom 1.24): **action text 16.7 px, board figure 16.7 px, alms figure 16.7 px.**

The alms panel and the four boards share one width, so their left and right edges line up exactly
(419 px drawn, both). The action box runs from the alms panel's top edge to the last board's
bottom edge — measured at run time, both at y 27 and y 895.

`1:1` in the corner pins the scale at 1.00 to check true pixel sizes.


### The action box's copy: stocks as glyphs, and what the log says

**Stocks are drawn, not named.** Wheat, stone, silver and piety appear in the action box's
prose as the same small drawings the player boards and duty tiles use, set in a 16-unit box on
the line of the body type. Naming a stock in words while drawing it a few units away in the same
panel taught the player two vocabularies for one thing. A glyph that follows a figure is set on a
hair space rather than a word space — "3 wheat" is one quantity, and a full space made it read as
two things standing side by side. Action *names* keep their words: "Produce wheat" is a title.

**The log names the duty tile and then the result — never the action.** A duty's actions have
names in the engine (`give_alms_paid`, `give_alms_donate_building`, `produce_wheat`) and none of
them belong in the log, because the outcome already says which was taken:

- `Blue took Produce and gained 3 🌾`
- `Blue took Give Alms and donated the Chapel`
- `Blue took Give Alms and moved 2 spaces on the Alms table`

So the shape is **actor · took · duty tile · and · what happened**. This keeps one sentence
pattern across all eight duties and stops the log carrying internal action ids in a player's
reading.

**Label and message are two columns.** Both `Duty` and `Last` set the label in its own column with
the message hanging beside it, so a second line starts under the message's first word rather than
under the label. The Duty slot is a fixed 132 units — sized for the longest of the thirteen
tooltips, Taxation — so nothing below it moves as the pointer crosses the wheel.

## The map as the wheel's other face

`desktop-fit.html` concluded that the map is the piece that yields — "an overlay that comes
forward when acolytes move". That conclusion is **superseded**: the map now *swaps* with the
duty wheel in the wheel's own slot, and there is no overlay.

The reason the overlay looked necessary was that the study asked the map to fit *beside*
everything else. It does not have to. The map's viewBox is 1013.8 × 1149.3 — an aspect of
**0.882**, taller than wide — so it is **height-bound**, and the wheel's slot is already as tall
as the row. Widening the slot buys the map nothing: at the action box's height it wants 0.882 of
that in width, and the wheel's square more than holds it. Concretely, at the 1600 × 1067 canvas
the map comes out **759 × 860** in a slot 848 wide, and at the 1440 × 760 floor **540 × 613**.
A hex is 92 units across, so it draws at **69 px** on the canvas and **49 px** at the floor —
against the 353 px at 400 tall that the overlay study was rationing.

So nothing else on the table moves when the view changes. The alms table, the market, the four
player boards, the Special Activities panel and the action box are all untouched; only the middle
column changes face. The action box in particular stays readable, which is the argument against a
real second page: the turn spine, the prompt and any half-made choice have to survive a look at
the map. Here they do, because nothing is torn down — the swap is one class on `.stage`
(`.mapview`), and `fit()` measures on the wheel's face and derives the map's box from it, so a
resize while the map is showing sizes correctly and comes back correctly.

The control is a **button in the bottom-right corner**, on the table rather than in the debug
hud, so it scales with the board and lives in the empty green under the wheel. It names the view
you would get, the way a door is labelled with the room behind it: it reads **Map** on the board
and **Duty Wheel** on the map. A hidden copy of the longer of the two names holds the width open,
so the button stays one size -- 135 x 39 -- and does not resize under the cursor when the view
changes; the live label is right-aligned in that box, so "Map" sits against the right edge.
`M` does the same thing from the keyboard. The map's own black backing
rect is dropped so it sits on the same green table the wheel does.

Still open: the map is `render_map`'s debug page, which is not connected to `GameState`, so
nothing on it moves yet; and whether the swap should happen *by itself* when the turn reaches a
step that needs the map — the old note's "comes forward when acolytes move" — which as a swap
would have to be returnable rather than modal.

### Building tiles at the swapped map's size

The map is populated from the **real** setup generator, not the setup page's example schedule:
`pilgrim.setup.generator.generate_setup_scenario(4, seed=20260730)` draws the four buildings per
level and the four pilgrimage sites and the rounds they go live on. Only the round-to-hex mapping
is borrowed from `generate_game_setup.py`, because the edge path *is* the round track and is not
the generator's business. Sixteen of the twenty-six edge hexes are occupied: sites on rounds 1, 8,
13 and 16, buildings on 3-6 (Infirmary, Mint, Guild, Chapel), 10-12 and 15 (Library, Indulgences,
Brewery, Reliquary) and 18-21 (Bank, Inquisition, Mill, Pulpit), with start roll 1 putting round 1
on E1. Buildings recolour their hex rather than lying on top of it, which is the setup page's rule.

**They fit, and the worst case is already on the board.** A building name draws at 13.4 map units,
which is **10.0 px** on the 1600 x 1067 canvas and **7.1 px** at the 1440 x 760 floor. The label
sits 13 units below the hex's centre, where the hex is 77.0 units wide rather than its full 92.
`Indulgences` measures **72.2** units -- 94 per cent of that, clearing by 2.4 units a side -- and
eleven characters is the catalogue's ceiling (`Scriptorium` and `Inquisition` tie on length and are
narrower), so no name in the game overflows at this size. `Confession Box` is the only two-line
tile and has the height for it.

Open, and visible in the picture: the map's own **hex coordinate labels** (`D10`, `E11`, ...) draw
at 7.9 px on the canvas and 5.6 px at the floor. They are 18xx-style debug furniture from the
prototype, they sit in the same corner the eye goes to for the building name, and at the floor they
are illegible smudges rather than information. They should come off the played map.

### Hex coordinates off, and the two views on one axis

The 18xx-style hex coordinates are gone from the played map. They are **tagged, not deleted** --
each of the 84 gets `class="hexref"` and the page hides them with one rule -- so they are still in
the file to switch back on whenever a hex has to be named while the map is being built.

On alignment, the answer to "is the wheel centred?" turned out to be **horizontally yes, already,
and on exactly the same axis**: the wheel's visible ink runs 786-1538 and the map's box 783-1541,
both centred on x = 1162, which is the slot's own centre. Nothing to change there.

Vertically they did not match, and the reason is worth recording. `fit()` intends the wheel's top
and bottom tiles to meet the action box's top and bottom edges -- but the wheel cannot always
reach that, because it is **width**-limited: it needs all 848 px of the slot, and the action box is
860 tall, so the tiles come up 108 px short. That leftover has to go somewhere, and top-aligning
put all 108 of it in one wedge of green under Produce. It is now split, 54 above and 54 below,
which is what the map does. Both views now centre on **(1162, 623)**, so swapping no longer shifts
the picture's centre of gravity. When the wheel is tall enough to span the box the change is a
no-op, because the leftover is zero.

**It costs nothing in measurement.** Every icon, cube and glyph on the wheel is sized from `side`,
which `fit()` computes by measuring the rendered tiles; a margin does not enter that calculation.
The readout confirms it -- wheel 848, action box 860, action text 13.5 px, board figure 13.5 px,
before and after. `wheel-map-alignment.png` is the before/after.

## The market, rebuilt as the map's own hex tiles

The twelve building cards are gone. In their place are the twelve building **hex tiles** and the
four **pilgrimage sites**, sixteen of them in round order, drawn from the same seeded setup the map
is drawn from -- so a name in the market is that name on the map's edge, on that round. The old
strip's names never matched the map's at all; that is fixed by construction rather than by hand.

Four things the shape settled, each of them a measurement or a rule rather than a preference.

**Chronological, not by level.** `build_abstract_setup_timeline` gates each level behind a
pilgrimage site and its cursor only moves forward, so levels always run 1, 2, 3 along the track --
but a site can land *inside* a level's run (here the round-13 end falls between Brewery on 12 and
Reliquary on 15). Grouping by level and telling the truth about time are incompatible, so the
strip tells the truth about time. The four seasons are the blocks, broken after each end.

**Site 1 sits at round 26, not round 1.** `pilgrimage_rounds_from_rolls` normalises against the NW
roll, so site 1 lands on round 1 every seed. That is where the *ship starts*, not a season ending.
The lap closing is the fourth season end, so the marker is drawn at 26 and the ribbon has an
ending. A site tile keeps only its colour and the words **Season End** -- which of the three site
variants it is does not change what the round means, and the market says *when*.

**Level colour is gone; ownership took the field.** Level 1 blue, level 2 red and level 3 green
collide with three of the four seat colours, and the seat mark is the one that loses: a red wash on
a pink tile stops reading as red. Since the order carries the level anyway, the fills went. The
outline went black. Ownership is a **foot bar** -- a short seat-coloured rule at the tile's foot,
black-keyed so white reads on parchment. It sits there and not in the border because the border
costs interior width: at the name's depth a bare hex offers **86.4** units, `Indulgences` wants
**82.1**, and an inward band of any useful weight takes more than the 2.2 a side that leaves.

**Used and donated are one gesture at two weights.** `TurnProgress.used_buildings` is cleared by
`advance_turn` on every turn boundary and is keyed by building rather than player, so "used" means
*spent this turn, by whoever spent it* -- the owner using it free and another player hiring it are
the same fact to the tile. `donated_buildings` never clears. So donated takes the **dark** grey and
used the **light** one, and the difference in weight is the difference in duration. Every letter on
the strip is black: the field carries the state, so the ink does not have to. The round box never
takes the state -- a building woke on the round it woke on -- and is filled green on the round the
board is actually on.

Built by `scratch/mkmarketsvg.py` against the panel's content box (1182 x 116, which is the strip's
1193 x 127 less its border and padding), so it drops into `.mkt` at 1:1.

## The log, and what it costs to open it

The log takes the foot of the player column -- the job Special Activities used to do before it went
to the head of the board -- so the three columns end on one line again. Its voice is *actor · tile ·
result*: a seat disc, the duty tile in bold, then what the tile actually handed over. Action names
never appear as words where a glyph exists, and stocks are the action box's own icons, so a line
reads `● Taxation, gained 1 ▣ and 1 ◎ in majority.` Seats are **discs, not coloured names** --
measured on parchment, yellow contrasts at 1.42 and white at 1.23, both far under any legible floor,
so the colour has to be a shape with an outline rather than ink on a word.

The verb went the same way. Every entry in the log is a duty being taken, so `took` was the same
word on every line and the tile is what the eye is hunting for; it is gone, and an entry now opens
on the bold tile name. The tithe is always one of its own stock, so the figure says nothing the
icon does not: `● Construct and took Tithe gaining ◎.`

**Why there is an expand and not a hide.** A toggle earns its keep when two things want one slot,
which is exactly what the Duty Wheel / Map button is for. Nothing else wants the log's space -- hide
it and the green table shows through -- so hiding buys nothing. The real complaint is size: at four
players the body is **162 px** against **915** of content, about two-thirds of a round. Growing is
the answer, and the numbers say how far. A line is 19.575, so an entry costs 23.1 single and 42.7
wrapped, and a round divider costs 26 (9 + 12 + 5). The three complete rounds in the reference
transcript measured **175.0, 177.9 and 221.2**; allow all four Confession Box lines and one wrapped
duty entry and the same round is ~241. The opening block is **304**, because setup emits four
two-line *sowed five acolytes* entries.

**The expanded panel stops at the top of the action box row (y 197.7), not at the seat ring.**
Player 1's board offers three edges within 14 px of each other -- outer ring 191.0, inner ring 197.7,
card frame 205.4 -- and the ring is the ornament that deliberately overhangs its card. Aligning to it
would put the log 6.7 px above the action box standing right beside it, which reads as a slip rather
than a decision. At 197.7 the two readings coincide: level with the action box, and the top of the
inner ring. Measured open: **y 197.7, height 855.3, body 807** -- four rounds at the sizes above.

**The bottom is pinned and the panel grows upward.** The log opens at its foot, so the invariant to
hold across the resize is the distance from the foot of the list, not `scrollTop`. Hold that and the
newest entry stays on the same pixel while history opens above it; hold `scrollTop` and it slides out
from under the eye. Measured: the last entry sits at y 1015.9 closed and 1016.3 open, the 0.4 being
integer `scrollTop`.

Expanding covers only the player cards. The action box is a different column and is untouched, so
the live context -- whose turn, what they are doing -- stays on screen the whole time the history is
open, which is why the panel does not need to stop short to preserve a board.

**Player boards stay in seat order.** Sorting them by turn order was considered and dropped. Vertical
position is the strongest encoding on that column and it is currently spent on identity, which never
changes: players learn *I am second from the top* and then navigate by position, checking the ring
only to confirm. Turn order is volatile -- the First Player marker changed hands in two of the three
complete rounds in the transcript -- so reordering would fire most rounds, break that spatial memory
every time, and make comparison across rounds harder. Turn order already lives in the First Player
marker, the alms table's `1st` slot, and the log's own line.

Built by `scratch/mklog.py` (engine transcript to log voice) and `scratch/mkmarketsvg.py`'s sibling
`scratch/mklogsheet.py` for the standalone study in `log-panel.html`. The translation layer belongs in
`pilgrim/io/event_text.py` and does not live there yet.

The action box's **Last** line is one line of the log and now obeys the same rules: the seat is a
disc built from the board's own `SEAT` palette rather than a coloured word, `took` is gone, the duty
tile carries the weight, and the result follows a comma — `● Produce, gained 3 ▣.` The disc rule is
shared (`.log .disc,.last .disc`) so the two marks cannot drift apart.

### The medallion came inside the card

Expanding the log used to leave four coloured crescents down its left edge: the portrait collar
overhangs the card, so covering the card did not cover the collar. Two overhangs had to go.

*Left, 18.3 px.* The collar sits at `PX - COLLAR`, and at `PX=26, COLLAR=45` that is -19 units --
19 units left of the card's own edge, which is also the log's edge. Moving the portrait to `PX=46`
puts the collar's left edge one unit inside the card. That cost the pill row 20 units on its left,
and the right margin is fixed (the silver pill keeps the card's own 16), so the row absorbed it by
closing up: pitch **58 -> 51.33**, gap between pills **22 -> 15.33 units (21.2 -> 14.8 px)**. The
first pill still stands 19 units off the collar, the gap it always kept.

*Top, 6.7 px.* This one was not in the card at all -- it was in `fit()`, which pinned **the portrait
circle's top** to the action box's top edge. The collar is 7 units larger, so the outer ring always
stood 7 units proud of the line the log stops at. Pinning the collar instead (`ptop = (PY-COLLAR)+8-1`,
the -1 for a unit of clearance) fixes it, and the outer ink is the thing that should meet that edge
anyway. With `PY=54` the two changes cancel exactly: the card frame stays at **y 205.4** where it
was, the boards do not move, and the collapsed log keeps its **162 px**.

Measured after: every collar is **1.00 px inside the log's left edge and 1.01 px below its top**, on
all four cards, so nothing of the portrait survives the expansion.

The cost is the badge. The medallion no longer breaks the card's left edge -- it is tangent to it,
and only the 7-unit top overhang still reads as breaking out. The seat spine follows the portrait's
centre line (it was a literal `26` from when the portrait sat at 26, now `PX`), so the medallion
still straddles the spine's edge and the shape holds together. Whether the card is better for it is
a judgement, not a measurement: the old card had a portrait hung off its corner, the new one has a
portrait set into it.

The alms table's four win places are pinned at **both** ends now, not by one place and a chosen
pitch: the rightmost sits over the first-player column, the third from the right over the **6** on
the track, and `WIN_PITCH = (first_x - anchor) / 2` is whatever halves the span between them, so the
remaining two land on it without a figure of their own. Measured: rightmost 0.01 px off the `1st`
centre, third-from-right 0.16 off the `6` (glyph bearing, not placement), pitch 19.3 across all
three gaps. `panel()` takes `win_seats` — seats filling from the left, fourth-from-right first — so
a place carries its holder's colour instead of always red; `wins` still works and still takes red.

### The building tile, settled

One skeleton for every tile in the strip, Season End included: the round in the crown, the name on
the map's own line below the middle, growing downward for a second row. A Season End tile is told
apart by its colour and its words rather than by a different layout -- giving it its own skeleton
as well made the strip read as two kinds of object instead of one board.

*Ownership moved from the foot to the crown.* It is a seat-coloured band **clipped to the hex**, so
it meets the tile's edge and takes its slope; a rectangle laid over the tile squares the corners and
reads as a sticker stuck on rather than part of it. The band runs from the top edge down to
`-APO/2`, half the way from the middle to the crown. It carries a **keyline on its lower boundary**,
because white contrasts 1.23 against parchment -- the same measurement that made the log's seats
into discs -- and colour alone is not a signal the white seat can use.

*The round box sits over the band,* at the same 9.5 from the top edge it always had, so it straddles
the band's lower boundary and the keyline runs out either side. One width for every box, sized for
two digits, so a 3 and a 16 are the same object; the rounds only reach 26. None is filled -- the
tile's own state shows through, which is what keeps a donated tile's number legible -- except green
on the round the board is on. The cost is that the box takes the widest part of the band and the
seat colour survives as two shoulders; red, blue and yellow read at a glance, white leans on its
keyline.

*The name is the map's, to the unit.* The map draws its label at y 11.5 on a hex of radius 46 -- a
quarter of the radius -- and a quarter of this tile's 52 is 13.0, the offset the tile started with.
The font follows: 12.4/46 and 14/52 are the same ratio. Measured across every name at that line,
nothing overflows and the binding case is **Indulgences at 81.6 in 89** -- under 4 units a side.
Scriptorium (78.4) and Confession (76.6) come next. A second line lands on 28 with 71.6 available,
which none of the six two-line buildings approaches. That 4 units is the headroom any future change
to this line has to respect.

*Gone:* the foot bar, and the word "Donated" -- the dark grey field says it, and a tile carrying
both said it twice.

`market-owner-band.html` carries two strips: the sixteen tiles this seed brings into play, and the
remaining twelve, which between them hold all six two-line names. The second strip is the layout's
real test and the reason to keep it. The band's clip ids are `mkband*` and not `hc*`, because
`mkR.py` names the player cards' hole-clips `hc1, hc2...` and the two SVGs share one document on the
board, where a duplicate id silently wins.

### The duty tile, rebuilt in bands

Everything used to queue down the right rail -- act, act, resource, wagon -- so the tile had one
busy edge and a large empty middle. It reads as four horizontal bands now:

    title + acts   the acts on the title's own line, filling from the RIGHT so the last one
                   always lands on _CX = 124, the wagon's axis
    tally          cube columns, cap 3, rule at y 107
    foot           resource at 26, wagon at 124, both on y 129

Pinning the last act to the wagon's axis gives the right side a spine -- act, cube column, wagon on
one vertical -- which is what the old layout had by accident and this one has on purpose.

**Two numbers were nearly fatal and are worth keeping.** The first is the title-to-icon clearance.
With `_GAP` 3 the first of two acts starts at x 75.85, and the titles end at: Clerical 55.0,
Produce 55.9, Construct 64.5, Give Alms 69.6, Ordination 70.5. Every two-act tile clears, the
tightest being **Ordination at 5.5** and Give Alms at 6.4. Build Roads is the longest title of all
at 78.2 but carries a single act, which sits on 124 and clears by 30. (An earlier pass declared
three of these impossible -- that was screen px read as tile units, and there are 1.163 of them to
the unit. Measure in the tile's own frame.)

The second is the pitch. With the acts up on the title's line they now stand *over* the cube
columns, ending at y 38.6. At pitch 13 a full stack plus its `+N` reached 36.1 and collided, so the
duty tiles took **`TILE_PITCH` 11** -- the pitch the wheel drew before -- and the city kept 13.
The cap then came down from 5 to **4**, which makes the tally band 56.9 deep, and the rule rose
from 112 to **106**: the acts end at 38.6 and the foot starts at 116, leaving 77.4 for a 56.9 band
and 20.5 of slack, so 106 is the line that splits it evenly -- about 10 above the tally and 10
below. Measured across all nine tiles the tightest is now **8.6** (Construct and Produce, the two
that carry both an overflowing column and two acts), up from 3.6 at the old cap.

Worth knowing: at a cap of 4 the original pitch of 13 would fit again, at 4.5 of clearance instead
of 8.6. Going back to it would match the city's spacing at the price of that margin.

The tally is centred twice over. Within the group, the cube columns are centred on the rule --
`XCOL` spans -33..31, a centre of -1 against a rule centred on 0, so the block sat a unit light to
the left, and `TCOL` fixes that for the tiles while the city keeps `XCOL`. And the group itself
moved from x 55 to `TALLY_X` **75**, the tile's own centre: on a 150-wide tile it had been standing
20 left of centre, which was invisible while the right rail was full of icons and obvious the
moment they left. 75 is also exactly halfway between the two marks on the foot, the resource at 26
and the wagon at 124.

The resource left the rail for the foot's left corner and grew **1.35**, which is what stops it
being read as one more cube now that it stands near the tally's ground. The overflow stays `+N`
rather than a total: at a cap of 4 the cubes are still countable and the figure is a footnote to
them. At the cap of 3 the study tried, that reverses -- the drawn cubes stop being the number -- and
the figure should become the total instead.


### Scaling the tiles, and where the act row finally landed

Ordination and Give Alms read as cramped, and the first instinct -- scale the tiles up -- does not
fix it: the title and the icons grow with the tile, so the gap keeps its proportion. Measured,
going from `scale(.74)` to `.80` moved Ordination's title-to-icon gap from 5.5 tile units to 5.7,
about 6.4 px to 7.2. Bigger, and just as tight. **Scaling changes the size of a crowding problem,
not the crowding.**

The tiles did grow anyway, to **0.80**: each goes 174.5 -> 188.7 px, roughly 8%, and the ring pays
for it -- the gap between neighbouring tiles falls from 32.2 to 18.1, and the arrows live in those
gaps. **0.86 was tried and rejected**: neighbours close to 3.9 and the arrows are crushed between
Allocation and Clerical. Treat 0.80 as the ceiling.

What actually opened the gap was moving the act row **below the title's baseline** (y 22) instead
of straddling it. The title then owns the tile's full width and the row reads as what the title
introduces. The box opens 3 under the baseline, at `_ROW_TOP` 25.

The title also came down to **11.4** from 12.5, and the reason changed underneath it. It was bought
to make horizontal room beside the icons; once the acts dropped to their own row that problem was
gone, but the type still earns its keep against the row's panel, which starts at x 72.8 -- at 11.4
Ordination ends at 65.5 and clears by 7.4, at 12.5 it ends at 70.5 and clears by 2.3, near enough
to read as touching the corner. `duty-scale-A.html` is the same board at 12.5 if you want to judge
that for yourself.

The cap came down to **3**, which makes the tally band 45.9 deep; with the acts now ending at 52.6
and the foot starting at 116, `TALLY_Y` **107** splits the 17.5 of slack evenly. Tightest
act-to-tally clearance across all nine tiles is **6.6**, no overlaps. The city takes `TILE_PITCH`
too, so there is one cube spacing on the board rather than two.

Both knobs are environment variables on `mkR.py` -- `TILE_S` and `TITLE_SZ` -- so a variant board is
one run, not an edit.

### The population band

The serf and acolyte marks are three things per population, left to right: a **figure**, its
**square**, its **count**. Both groups are pinned to the resource pills below them, so the band and
the pill row read on the same columns — the serf figure over **piety**, its square between piety and
wheat; the acolyte figure over **stone**, its square between stone and silver. A divider splits the
air between the two groups, which is not the midpoint of the squares: each group runs from its
figure's left edge to the right of its count, so the divider is derived from those extents.

Two numbers came out of the band rather than out of taste. The row sits on `TOP + BAND_H/2` = **36**,
the band's own centre; it had been at 28.5, which centred the squares in the band's *upper half*
rather than in the band. And the figure is **30 units, 2.51x the square** — centred on 36 in a band
running 16..56 that clears the card's frame top by 5 and the band's foot by 5, which is the size the
band allows rather than one chosen by eye. At the old row position it would not have fitted.

The figures share the squares' centre line instead of standing on a baseline beside them. At two and
a half times the square a baseline alignment leaves the figure towering next to it; a shared centre
makes each group read as one row.

It lives in **`gen_population_marks.py`**, not in the generator, so it survives the session that
built it — `defs()` returns the symbol markup and each figure's aspect, `band()` draws one card's
row. `defs()` takes a choice of asset paths, which is the hook the icon picker will use. Its markup
goes in the **page body, never inside `.boards`**: `fit()` aligns the player column from
`.boards svg[0]`, so a zero-size defs element there becomes the thing it measures.
