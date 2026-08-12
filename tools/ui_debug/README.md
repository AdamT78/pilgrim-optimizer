# Pilgrim UI Debug Prototypes

These files are visual prototypes/baselines only.

They are not connected to `GameState`, do not implement rules, and are not the final UI.
They should be used as visual reference before future renderer extraction.

Future work can extract structured geometry/layout data one prototype at a time while preserving visual parity.

## Source of truth

Each kind of file here has one job, and mixing them up is how this layer starts to drift:

- **Prototype HTML** (`prototypes/*.html`) are visual baselines. Once a prototype lands it is
  not edited; renderers are judged against it.
- **Prototype sources** (`prototype_sources/*.py.txt`) are reference copies of the throwaway
  scripts that drew a baseline. They are kept as `.txt` on purpose: they are read for intent when
  reverse-engineering, never imported, run, or refactored.
- **Layout/catalog JSON** (`*_layout.json`, `*_catalog.json`) are structured renderer inputs.
  They describe what to draw, reverse-engineered from the baseline. They hold geometry, not
  gameplay numbers.
- **Game config** (`configs/*.json`) stays the source of truth for any real game value a view
  happens to print, such as the piety VP table. Copying those numbers into layout JSON is how the
  UI starts lying about the game.
- **Generated HTML** (`generated/*.html`) are local debug artifacts. They are git-ignored,
  rebuilt on demand, and never hand-edited or committed.
- **`GameState`** remains the source of truth for gameplay once integration begins.
- **UI debug renderers are derived views only.** They read data and draw it. They never decide
  anything about the game.

## Component extraction checklist

The building tiles, player board, and map extractions all worked the same way: reverse-engineer
the baseline, then reproduce it. None of them redesigned anything. Follow the same steps when
adding a new component:

1. Add the untouched prototype HTML under `tools/ui_debug/prototypes/`.
2. Do not alter existing prototype baselines.
3. Add structured layout/catalog data only after the prototype baseline exists.
4. Add a deterministic renderer that targets visual parity with the prototype.
5. Add a generator script that writes to `tools/ui_debug/generated/`.
6. Keep generated HTML ignored by git.
7. Update `tools/ui_debug/index.html` with separate baseline and generated links.
8. Update `tools/ui_debug/generate_debug_overview.py` only after the generated view exists.
9. Add lightweight tests for file existence, key labels, expected IDs, and generation.
10. Do not snapshot full generated HTML unless explicitly required.
11. Do not add `GameState` integration unless explicitly requested.
12. Do not put gameplay/rules logic in the UI debug layer.

For upcoming boards such as the piety track and the alms board, prefer splitting the work
across PRs in this order:

1. Add the prototype baseline first.
2. Verify it opens and looks correct.
3. Extract the renderer in a separate PR.
4. Wire it into the generated overview only after renderer parity is acceptable.

Every prototype currently in `prototypes/` has been through this checklist, so there are no
baseline-only prototypes left. New prototypes start at step 1 again.

## Building tiles renderer extraction

`prototypes/building_tiles.html` is the untouched visual baseline for the building tiles.

`building_catalog.json` and `render_buildings.py` are the first structured renderer extraction:
the 24 building tiles are described as data, and the renderer draws them with geometry taken
from the baseline prototype.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_buildings.py
```

This writes `generated/building_tiles.html`. Generated output is not committed; the catalog and
the renderer are.

Building tile labels omit the Roman numeral level row. Level is communicated by tile color, while
the building name is rendered larger, near the hex center, breaking only between words: a name of
two words takes two lines, and no word is ever cut or hyphenated. Setting a word to a line is what
buys the size, because the longest word rather than the longest name is what has to fit.
`Indulgences` is the widest of them, and it caps `TILE_NAME_FONT_SIZE` at 14: on the first line,
at `TILE_NAME_CENTER_Y_OFFSET`, it fills all but about 7 units of the hex's width. That first line
starts just below the middle of the hex, which is as far down as the ship marker's hull reaches,
so a tile carrying both still reads. The label the tiles used to wrap under a level numeral
survives on the ship marker page, which still heads each example tile with its level.

Like the prototypes, this still does not connect to `GameState` and still does not implement
game rules.

## Player board renderer extraction

`prototypes/player_board.html` is the untouched visual baseline for the player board.

`player_board_layout.json` and `render_player_board.py` are the structured renderer extraction:
the banners, worker slots, resource counters, special-activity hex snake, and empty building
slots are described as data with coordinates reverse-engineered from the baseline prototype.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_player_board.py
```

This writes `generated/player_board.html`, which is not committed.

The renderer draws a mock player state (see `default_player_state()`), so it still does not
connect to `GameState` and still does not implement game rules.

## Player boards v2 renderer extraction

`prototypes/player_boards_v2.html` is the untouched visual baseline for player board v2. It holds
all four player boards on one page — white, red, yellow, and blue — instead of the single board
v1 draws. `prototype_sources/player_boards_v2.py.txt` is the reference-only copy of the script that drew it,
read for intent while reverse-engineering the layout, never imported or run.

`player_boards_v2_layout.json` and `render_player_boards_v2.py` are the structured renderer
extraction. The split between them is worth knowing: the JSON says what a board carries (the four
players and their colours, the palette, the Village/Abbey banners and how many starting workers
each shows, the six worker roles, the three resource readouts, which roles already hold workers),
and the module says where it all goes. The geometry stays in the module because it is derived
rather than chosen: the board is built on six columns, and the banners, the worker circles and the
resource readouts all line up on them. The columns were the building slots' width, back when a slot
stood in one; `COLUMN_HALF_WIDTH` is that width, kept where it was after the slots outgrew it.

### The board is wider than the baseline, and taller

The board is wider in its own geometry than `prototypes/player_boards_v2.html` draws it, and then
taller, both for the same reason: its bottom building slots are the size of a map hex. The
prototype's slots were about two thirds of one, which is why the bottom row looked cramped — a
building tile dropped into a slot was a different size there than the same tile on the map.

Matching them is not arithmetic the board can do on its own. A slot and a map hex are both flat-top
hexagons measured from the centre out to a corner, so they come out the same size when they render
at the same width — but the composed game table draws the map at the full table cube and a seat at
the shortfall the duty wheel is fitted into, so equal figures do not render equally.
`BUILDING_SLOT_HEX_SIZE` is therefore measured off the real solve rather than derived, and a game
table test holds it against a map hex; that test is what to re-run if either board's scale moves.
It used to be derived, as a map hex counted in `MARKER_CUBE`s, and rendered a fifth short.

A slot that size is wider than one of the board's columns, so six will not fit across in a row. The
slots left the columns and interlock instead, every other one offset by an apothem — the way two
flat-top hexagons pack against each other — which fits all six across a board that has not grown at
all, and costs a band half again as deep. The columns above them did not move: the banners, the
worker circles and the readouts are all where they were, to the unit, and the worker circles are the
size they always were. The board is 22% taller for the band, and the game table does not scale a
seat to compensate; it inherits the component's geometry and the shared table scale, and gives the
seats' row the room. A Village cube still matches a duty tile's cube exactly, because a seat is
sized from the wheel's rendered cube rather than stretched to fit a height.

### Type and readouts are sized against the duty wheel

On a board that much wider, type set for the narrow one reads small, so three things were drawn
bigger afterwards: the Village and Abbey banners, the worker role labels, and the three resource
readouts. The board did not change size again to fit them — `board_geometry` returns the same panel
it did before, to the unit — and none of it is scaled; these are the native constants.

Two of the three are matched to the duty wheel, by the argument the building slots settled. Boards
drawn at different scales are the same size on screen when they are the same size in cubes, so
`BANNER_FONT_SIZE` is the wheel's `LABEL_FONT_SIZE` converted into this board's units: 15.5 against
a 13.0-unit cube becomes 16.7 against a 14.0-unit one. The resource icons are sized the same way,
against the wheel's drawings of the same three things.

The wheat has its own size and the stone and coin share one, which is not tidiness for its own
sake. A single size for all three, picked to suit the stone and the coin, puts the wheat about 8%
over the wheel's, and that is the one difference here the eye picks up: it is the big shape of the
three, so it is the one you notice. Sized on its own it lands within about a percent of the wheel's
wheat in both height and width. The other two are left a few percent under the wheel's rather than
exactly on it, which is where they read right next to everything else on this board.

Because the three no longer share a size, and because none of them is drawn around the middle of its
own shape, each one centres itself in the band they share: `ICON_RISE_RATIO` and `ICON_FOOT_RATIO`
are how far each reaches above and below the point it is drawn from, and `resource_icon_center_y` is
the offset that puts the middle of the drawing on the middle of the band. The wheat is the one that
needs it, fanning upwards and reaching barely half as far below. Resizing any one icon therefore
cannot leave the three standing at three different heights.

That buys a match in cubes, not a match in pixels. On the table the two panels do not render at the
same pixels-per-cube: the player board runs somewhere between 2% and 9% larger than the duty wheel
depending on the window, so "Village" reads a few percent bigger than "Produce" and how much
depends on the window size. That gap belongs to the table's panel scaling rather than to either
component, and no fixed number a renderer could carry would close it at more than one window size.

The role labels are the third, and are simply set larger than the prototype had them — 10 to 14 —
while staying below the banners naming the two halves of the board. `LINE_HEIGHT_RATIO` and
`ASCENT_RATIO` are why that is a one-line change: a line height and an ascent are properties of the
type rather than free choices, so every point of type on the board derives them from its own size.
Set a size and the spacing that depends on it follows, and no change can leave two-line labels like
"Road Engineer" overlapping or drop a row of them onto the circles below.

### Resources stand in the top-right corner

Player Board v2 now keeps resources in a compact top-right block and no longer renders the
first-player marker on the board. They used to be three large circles strung across the middle of
the board; they are a row of icon over amount in the corner, with a thin rule between one readout
and the next.

Across the board they stand on the same six columns as everything else. The banners take two
columns each, which leaves two, and the readouts split those three ways — `RESOURCE_BAND_COLUMNS`
over `RESOURCE_READOUT_COUNT` — so one centres in each third and a rule falls on each seam. That
lands the block's left-hand end exactly on the Abbey banner's right-hand end, which is a
consequence of the derivation rather than a number anyone picked. The two ends of the row are left
open: a rule out there would read as a frame drawn around the block rather than a division inside
it.

Two things want this corner, and they divide it between them. The colour tag runs down the board's
right-hand edge as far as its own size, and the rules pick up from exactly where it stops, so the
boundary between them is one line rather than a judged gap. That is what puts the readouts below
the banners rather than level with them: the tag is the deeper of the two. Under the rules' start
comes a band deep enough for the tallest of the three icons, then `RESOURCE_VALUE_GAP`, then the
amounts, all on one baseline so a two-digit amount cannot shift its neighbours.

The first-player card went with the move: it would have sat on top of the block, and it was never
anything but layout state to look at. The buttons on the setup page that moved it went too.

### The board is shorter now

Player Board v2 was shortened after moving resources to the top-right by tightening vertical spacing
between the cube area, special activity labels, and role circles. Piece sizes and font sizes remain
unchanged: the board went from 401.56 units tall to 339.98, and nothing on it was scaled to do it.

The readouts had left a third of the board empty. The role labels used to hang a flat 130 units
below the cube grid — a distance chosen when the readouts stood in that space — so they are hung off
whatever is above them instead. That is the readouts rather than the cubes: the block and its rules
reach lower than the Village and Abbey grids do, and the labels run the whole width of the board, so
`ROLE_LABEL_TOP_GAP` is measured from the deeper of the two. Below it the band is exactly as deep as
a label can be, `ROLE_LABEL_MAX_LINES` of them, and then the circles. Everything under the circles
came up with them, and the board's bottom margin is the banners' top margin again.

This could not move until the composed game table was taught to size a seat from the duty wheel's
cube. The table used to stretch two boards to the wheel's height, which made a board's shape decide
the scale it was drawn at there: taking a sixth off the height drew a cube in a Village a fifth
larger than the same cube on a duty tile. See "One shared scale" below for what changed.

### Cubes are the duty wheel's cubes

Player Board v2 cube size and cube spacing intentionally match the Duty Wheel cube styling so player
pieces read consistently across the composed game table. A player's cube is the same piece whether
it is waiting in the Village, standing on a role circle or sitting on a duty tile, and it should not
change size on the way. So `TOKEN_RADIUS` is half the wheel's `CUBE_SIZE`, imported rather than
copied, and the grids are spaced off the wheel's two pitches: the wheel writes `CUBE_COLUMN_WIDTH`
and `CUBE_CELL_HEIGHT`, and the air between two of its cubes is a pitch less the cube. It spaces
them wider side to side than it stacks them, so `TOKEN_GAP` and `TOKEN_ROW_GAP` are two numbers here
rather than one.

The wheel is the reference rather than the other way round because its cube is what the rest of the
table is calibrated against; see the duty wheel section below.

Matching the number here is not on its own what makes the two equal on screen — that depends on the
scale each board is drawn at, which is the composed table's business rather than either renderer's.
The table pins a seat to the wheel's own rendered cube, so the match is now exact; the old 14.0-unit
cube was about 10% over. A game table test measures both against the real solve rather than trusting
either renderer.

`MARKER_CUBE` stays at 14.0 through all of this. It is no longer the size of a drawn cube but it is
still the unit the board's geometry is written in — the banner type is a multiple of it — and
matching the cubes to the wheel was never a reason to reset the type. The building slots were
multiples of it too, and should not have been: a slot stands for a map hex, so it has to be measured
against what a map hex renders at rather than against a unit that had stopped being this board's
cube. The grids keep the band they had at the old cube size, `TOKEN_BAND_HEIGHT`, with the shorter
grid centred in it, so nothing below them moved: the role circles, the readouts and the top of the
slot band are all where they were to the unit.
The Alms Table draws the same cube too, taken from the seats the way the seats take theirs from the
wheel, so the three boards are one chain from the wheel's `CUBE_SIZE` down.

The generated SVGs are therefore no longer byte-identical to the baseline's. The test that used to
pin that parity now pins the divergence instead, and only that: a board wider and taller, with the
type bigger and the cubes smaller, the readouts moved out of their circles and into the corner with
the first-player card gone, and the worker circles and the count of every piece — cubes included —
exactly as the prototype left them. The baseline itself is untouched.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_player_boards_v2.py
```

The generated overview below also produces it. Both write `generated/player_boards_v2.html`, which
is not committed.

This does not replace the v1 player board. `player_board_layout.json`, `render_player_board.py`,
`generate_player_board.py`, and `prototypes/player_board.html` are untouched, and both views are
generated and linked side by side until v2 takes over. Like every other view here, it does not
connect to `GameState` and implements no gameplay rules.

## Map renderer extraction

`prototypes/map.html` is the untouched visual baseline for the map.

`map_layout.json` and `render_map.py` are the structured renderer extraction: the hex grid,
its 18xx-style coordinate labels, the hidden centre cluster, and the river/track features are
described as data with coordinates reverse-engineered from the baseline prototype.

The label function is the part most likely to drift, so it is pinned by tests: the top hex is
`B6`, the bottom hex is `L6`, and the middle row runs `G1`..`G11`.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_map.py
```

The generated overview below also produces it. Like the other renderers, this still does not
connect to `GameState` and still does not implement game rules.

## Donated building tiles renderer extraction

`prototypes/donated_building_tiles.html` is the untouched visual baseline for the
donated/flipped building tiles.

`donated_building_tiles.json` and `render_donated_buildings.py` are the structured renderer
extraction. These tiles are the VP markers shown when a building is donated (flipped), one per
building level/colour:

```text
level I  (light blue)  = 2 VP
level II (light red)   = 4 VP
level III (light green) = 6 VP
```

The tile colours are imported from `render_buildings.py` rather than repeated, so the donated
tiles cannot drift away from the regular building tiles.

Donated building VP stars match the Pilgrimage Site VP star sizing while remaining centered in the
donated hex. Neither tile is ever seen at its own size — a donated tile is drawn into a player
board's building slot and a site into a map hex — so `STAR_OUTER_RADIUS` here is a site star's share
of the hex it is drawn onto, applied to this tile's hex. That is the whole of it now that a building
slot renders at a map hex's size; it took a larger figure while the slot came out short, and
`test_ui_debug_game_table.py` still measures the two against each other on the real solve. The VP
inside the star is set at the piety track's star-to-label proportion, the same one the site uses.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_donated_buildings.py
```

The generated overview below also produces it. Like the other renderers, this still does not
connect to `GameState` and still does not implement game rules.

## Ship marker renderer extraction

`prototypes/ship_marker.html` is the untouched visual baseline for the ship marker examples: the
first building tile of each colour with a ship silhouette in the upper part of the hex.

`ship_marker_examples.json` and `render_ship_marker.py` are the structured renderer extraction.
The three example tiles are described as data, and the tile colours, hex radius, and label layout
are imported from `render_buildings.py` so they cannot drift away from the regular building tiles.

The ship itself is deliberately a reusable SVG primitive rather than part of the tile:

```python
render_ship_icon(cx, cy, scale=0.85, color="#000000")
```

It returns a self-contained fragment (hull, bowsprit, three masts, sails, pennant) anchored at the
middle of the hull at the waterline, so a later map-edge or round-track view can drop the same
ship in without pulling tile geometry along. The ship is a marker drawn on a tile, not a rule
about the tile.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_ship_marker.py
```

The generated overview below also produces it. Like the other renderers, this still does not
connect to `GameState` and still does not implement game rules.

## Piety track renderer extraction

`prototypes/piety_tracks.html` is the untouched visual baseline for the piety tracks, and
`prototype_sources/piety_tracks.py.txt` is the reference-only copy of the script that drew it.
That script is read for intent; it is never imported or executed.

`piety_track_layout.json` and `render_piety_track.py` are the structured renderer extraction. The
page shows the same strip twice, so the layout describes the geometry once and lists the two
variants: `three_four_player` with two token rows and `two_player` with one. Dropping a row
shortens the strip by exactly that row, which is why the two tracks have different heights.

The VP numbers on the stars are **not** in the layout JSON. They are read from
`configs/piety.json`, parsed with the game's own `piety_from_dict`, so the drawn track cannot
disagree with the scoring the engine uses. The renderer fails loudly if the config stops matching
the number of positions the layout draws. The yellow star itself is imported from
`render_donated_buildings.py` rather than reimplemented.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_piety_track.py
```

The generated overview below also produces it. Reading the piety table is not `GameState`
integration: this is still a static view, and it still does not implement game rules.

## Piety track v2 renderer extraction

`prototypes/piety_tracks_v2.html` is the untouched visual baseline for Piety Track v2, the piety
track redrawn in the house ornament so it sits alongside the mancala board and the Alms Table. Like
the v1 page it holds both tracks: the 3–4 player one on top, the 2 player one beneath.
`prototypes/piety_track_v2.svg` and `prototypes/piety_track_2p_v2.svg` are those two tracks as
standalone SVG baselines, and `prototype_sources/piety_tracks_v2.py.txt` preserves the Python that
drew them, reference-only — read for intent, never imported or executed.

What v2 changes is structural rather than decorative. The two ornament devices the house style kept
are an inset hairline just inside the panel edge and a trefoil header beside the title, and the v1
strip has nowhere to put either: its boxes butt against the panel edge, so a hairline would run
through the numbers and clip the end stars. So the strip becomes a panel that contains the boxes,
the way the Alms Table already is, gaining side padding, a title band, and a little more bottom
margin — and with it, the board's name in the artwork instead of only in the HTML heading. Box
pitch, disc sizes and colours are untouched, and the discs are deliberately identical to the Alms
Table's, which is why a step reads the same on both boards.

`piety_track_v2_layout.json` and `render_piety_track_v2.py` are the structured extraction, and they
follow v1's shape closely: the layout describes the panel once and lists the two variants,
`3_4_player` with two disc rows and `2_player` with one, and dropping a row still shortens the
panel by exactly that row. What v2 adds to the layout is the panel around the strip — side padding,
corner radius — and where the ornament sits on it.

### Set the way the Alms Table is set

The two boards are the same thing twice: a numbered row of spaces with a player disc standing on
one and a score printed under each. In the composed game table they are drawn at the same scale —
that is what makes the disc they share come out the same size on both, and
`test_the_alms_table_and_the_piety_track_share_a_scale` holds it against the real solve. A unit
being a unit on both is what lets this board be set from the Alms Table's own constants and have
each thing land at the same size on screen.

So it is. The numbers `0`–`12` are `STEP_NUMBER_FONT_SIZE` in `INK_FONT` at `LABEL_FONT_WEIGHT`,
the same three the Alms Table numbers its steps with; a hairline at `STEP_RULE_STROKE_OPACITY`
divides each position from the next, as one divides each step there; the title is `TITLE_FONT` at
`TITLE_FONT_SIZE`; and each score sits in a `STAR_OUTER_RADIUS` star with the VP set inside it at
`STAR_LABEL_FONT_SIZE`, plain rather than bold, `STAR_LABEL_OFFSET` under the centre. None of those
are copies of the Alms Table's values — they are imported from `render_alms_table.py`, so the two
boards cannot be restyled apart by accident. Four of them were moved out of `alms_table_layout.json`
into that module to make the sharing possible: how a thing is drawn is the house's business, where
it sits is the board's.

The row of stars is then placed rather than merely sized. The composed table stands this panel's
top level with the Alms Table's and draws both at one scale, so the same y in panel coordinates is
the same y on the table, and `discs_to_stars` is set to land this row on the row the `11` star
sits in over there — a score reads across the table at one height.
`test_the_stars_stand_level_with_the_second_row_of_the_alms_tables_key` measures it against the
Alms Table's own key rather than against the number, and the game table's own test holds the
premise: the two panels are cropped to the same height above their panels. It is bought in the gap
over the stars rather than by pinning them to a y, so the strip is still a stack — the 2 player
variant is a disc row shorter and its stars come up with the rest of it.

Two more things follow from all this rather than being asked for directly. The rules run from
above the numbers to the Alms Table's own distance below the disc grid, which takes them down past
the top of the stars — what keeps them off the pieces is width, not height, since a disc pair and
a star are both narrower than the space they stand in. And the drop from the title to the numbers
is the Alms Table's, which is 14 units more than v2 was drawn with, so the panel is taller than
the baseline by that, the two the star grew, and the six the stars moved down. The title band the
layout used to carry is gone: what it described is now the drop itself, which is the thing worth
naming.

The header rule is the one place the two part company. The lobes, the air held either side of
them and the stroke are the Alms Table's, but the rule they break runs from clear of the title to
the panel's far padding, which is a wider header than the Alms Table's — so the arms are longer.
They stay equal to each other and centred on the lobes, and the tests hold the left one clear of a
measured `TITLE_RIGHT_EDGE`, as the Alms Table's tests do.

The VP numbers on the stars are **not** in the layout JSON, exactly as in v1. They are read from
`configs/piety.json`, parsed with the game's own `piety_from_dict`, so the drawn track cannot
disagree with the scoring the engine uses, and the renderer fails loudly if the config stops
matching the number of positions the layout draws. The viewBox and display size are not stored
either: they follow from the panel and the padding, and a stored copy could only ever go stale. The
star is imported from `render_donated_buildings.py` rather than reimplemented.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_piety_track_v2.py
```

The generated overview below also produces it, and the index links it as `Generated piety tracks
v2`.

The board no longer renders byte-for-byte against its SVG baselines: the styling above moved it
away from them, and the baselines are left untouched as the record of what was drawn first. Two
tests stand in place of that parity. One says what the restyling was not allowed to touch — the
panel is the same width, the positions fall on the same centres, and the discs are the same discs
on the same position — checked against the baseline's own numbers rather than against this layout,
so the two cannot drift together. The other says what did move and which way: the numbers and the
scores grew from 9, the star from 16, rules arrived where the baseline had none, and the panel
grew taller for the drop under the title.

The `data-` hooks — `data-component="piety-track-v2"`, `data-piety-variant`, `data-piety-position`,
`data-player`, `data-player-disc` — are still the only thing the extraction adds that is not
drawing, and they exist for future UI/debug interaction. The baselines carry none of them.

v2 does not replace the current piety track: `piety_track_layout.json`, `render_piety_track.py`,
and the generated `piety_tracks.html` are untouched, so the two are generated side by side. The
setup view below is the one place that has moved over to v2; the old generated page remains
available as a standalone debug view. There is no `GameState` integration and no gameplay rules
here.

## Pilgrimage site renderer extraction

`prototypes/pilgrimage_sites.html` is the untouched visual baseline for the Pilgrimage Site tiles:
five orange tiles in one row, each with a piety-track star and a P value and an S value beside it. `prototype_sources/pilgrimage_sites.py.txt` is the reference-only copy of the
script that drew it. That script is read for intent; it is never imported or executed.

`pilgrimage_sites.json` and `render_pilgrimage_sites.py` are the structured renderer extraction.
The JSON holds only what the tiles print — the VP value on the star and the two values beside it —
while the geometry lives in the renderer, the same split the building tiles use. Nothing is
redrawn from scratch: the hex comes from `render_buildings.py` at the same 52 unit radius, so the
sites read as the same kind of piece, and the star comes from `render_donated_buildings.py`.

Pilgrimage Site VP stars are enlarged to match the Piety Track star, and the P and S values beside
them are set the size a building tile sets its name. `STAR_OUTER_RADIUS` is the track's own star
written in the
tile's units: the site tile is drawn into a map hex, so its star crosses the tile's units into the
map's and the map's into the table's before it stands next to the track, and the figure is that
round trip solved for. `VP_TEXT_FONT_SIZE` takes the Alms Table's star-to-label proportion of it,
so the VP sits in the star the way the piety track's does. A test in
`test_ui_debug_game_table.py` measures the two stars against each other across the boards' scales;
it is what holds the figure honest, and what to re-measure from if a board's scale ever moves.

Matching the track makes the star large enough to run into the ship marker, so `STAR_CENTER_Y`
hangs it below the ship instead: a map hex carrying both shows them one under the other. What it
clears is `SHIP_BOTTOM_Y`, the keel's own depth taken off the hull the ship renderer draws, plus
`STAR_SHIP_CLEARANCE` for daylight. The ship is scaled onto a map hex by the same tile-to-map ratio
as the site's contents, so the keel sits at the same height in either board's units and the drop
reads the same on the tile page and on the map.

The P and S values take `TILE_NAME_FONT_SIZE` and `TILE_NAME_LINE_HEIGHT` from the building tiles,
so a site tile and a building tile are lettered alike. The pair straddles the hex's mid line — the
number standing above it, its letter hanging below — rather than sitting under it, and
`LABEL_COLUMN_X` is measured out from the star's widest points so the two stay clear of each other
whatever size the star is set to.

Because the star and the values grew, the page is no longer byte-identical to the baseline. In its
place the tests assert the divergence: the hexes are still the baseline's element for element, and
the tiles print exactly what they printed, while nothing about how the contents are set matches.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_pilgrimage_sites.py
```

The generated overview below also produces it.

This is still a picture of five tiles. It does not connect to `GameState`, does not draw
pilgrimage sites at random, is not wired into setup generation, and implements no game rules. The
game setup view below reuses the tile contents for its four site slots, always taking the first
four sites in file order.

## Duty wheel renderer extraction

`prototypes/duty_wheel.html` is the untouched visual baseline for the Duty Wheel / Duty Board,
which holds the duty tiles and their action spaces away from the map so the map stays readable.
`prototypes/duty_wheel.svg` is the same board as a standalone SVG, for looking at or embedding
without the page around it. Both still carry the titles the source gave them
(`PILGRIM — Flat-top Circle Grid`, `PILGRIM — 3x3 Circle Grid`).
`prototype_sources/duty_wheel_build.py.txt` preserves the Python that drew the prototype and
`prototype_sources/duty_wheel_render.py.txt` preserves the optional helper that rasterises it to a
PNG through headless Chromium. Both are reference-only: read for intent, never imported or run.

`duty_wheel_layout.json` and `render_duty_wheel.py` are the structured renderer extraction. Every
space is placed from a single anchor, the centre of its own arc, and everything else on it — the
flat-top outline, the title, the cube tally, the Tithe capsule, the ornament — is a fixed offset
from that anchor, which is why the JSON only has to name nine points. The JSON says what a space
carries and where its anchor sits; the module says how the pieces around it are drawn. Three
traced shapes live in the JSON as raw path data because nobody derives them: the two arrow
silhouettes and the cornucopia horn.

Two things in the picture are named so a later renderer does not have to guess:

- The purple disc is the **Merchant token**, drawn wherever `merchant_token.starts_on` points
  (Taxation, on the generated page).
- The resource icons in the capsules are **Tithe tokens**.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_duty_wheel.py
```

The generated overview below also produces it. Both write `generated/duty_wheel.html`, which is
not committed.

The generated Duty Wheel carries three local UI/debug controls. **Randomize Duty tiles** cycles
through sample Duty tile / Tithe token setups, and **Move Merchant** walks the Merchant token
clockwise around the duty ring. The Merchant starts on Taxation in this debug view, and repeated
clicks carry him through all eight duty tiles, Taxation included; the City is not part of his
path. **2p / 3p / 4p** picks how many players the board is drawn for, which decides how many cube
tally columns each space shows. 2p is the view the page opens on: red and blue at the table, and a
black neutral column beside them on each duty tile, so a duty tile shows three columns and the City
two. 3p seats white as well and 4p seats yellow too, and a full table plays against no neutrals, so
its tally is seats alone. The columns stay centred on the space, so a shorter table narrows the
tally around the middle of it instead of leaving a gap on the right, and the baseline under them
shrinks to match. All of it is visual/debug only: the controls
move tokens, rewrite the eight titles, and swap tallies, and they do not mutate `GameState` or
implement any gameplay rule.

The controls work by ring position rather than tile identity, which is debug-only shorthand and
fine while Taxation is the one tile that never moves. The renderer draws every slot they can
switch on — a Merchant token on each position, every Tithe token on each position that has a
capsule, and a tally per player count on every space — hidden until wanted, so a click flips
opacity instead of redrawing the board. Ask for the board without `interactive` and none of that
is emitted, leaving the two-player tally the page opens on. `players_for_count()` says who is at
the table, `tally_pieces()` adds the neutrals beside them, and `tally_columns()` says where the
columns stand. The sample setups come from
`duty_setups()`: the first is the board the layout describes, the rest turn the movable tiles
around the ring, and a tile keeps its own Tithe token wherever it lands — which is why Taxation
stays put, being the one tile with no Tithe token and so the one position drawn without a capsule.
`next_merchant_position()` is the walk itself, one step clockwise along `clockwise_order`.

The cube counts on each duty come from `sample_cubes` in the layout, keyed by seat — the players
are `player_one` to `player_four`, each naming its cube colour, the same way
`player_boards_v2_layout.json` names them. Which of those four sit down at a two- or three-player
table is `seats_by_player_count`, the layout's to say rather than simply the first few in the list:
a two-player table takes red and blue, the pair that carries against parchment.

The black column beside them is `dummy_acolytes`, the neutral pieces a reduced table plays against.
They are not a seat — they take no turn and hold nothing — so they are not in the players' state
and read their own seeding out of the layout, one group of three clockwise from the top and one
from the bottom at two players, two and two at three. That mirrors `docs/rules/DummyAcolytes.md`,
which is also why the City has no neutral column: dummy acolytes are seeded and moved on the duty
ring, and the City is not on that ring. The City's own columns have room for six cubes a seat —
`CITY_STACK_HEIGHT`, a seat's whole holding rather than a duty tile's handful — and stand lower in
the space so the taller stacks share the room under the title evenly. They open holding
`city_sample_cubes_per_seat`, which is two, leaving four spaces free for a page with buttons to fill.
Drawn `interactive`, a column draws every slot it has room for and hides the empty ones, the way
every other board here draws the slots a cube can stand in — six in the City, `TILE_STACK_HEIGHT` on
a duty tile, which is the three that fit between the baseline and the title, and none at all in the
neutral column, since no seat plays those cubes. Drawn plain, a column is the cubes standing in it
and no more. Cube size and pitch are the wheel's throughout: what makes room for six is where the
City's column stands, not how big the cubes in it are.

All of it is sample debug state, not `GameState`, in the same spirit as the v1 player board's mock
state. Nothing here says what any of it means: there is no Tithe token logic, no Taxation rule, no
sowing or acolyte placement, and no sow animation. Those belong in later PRs.

The cube itself keeps the size it has always had, and this is the board that sets it. It is the
reference the rest of the composed table is calibrated against — a seat is sized from this cube as
it renders, which is also what fixes the scale a seat's building slots have to be measured against —
so what a cube here is worth in another board's units is not this renderer's to restate. When the seats' cubes read larger than these on the composed pages, it was the seats that
were brought to this size rather than this number that moved.

`render_duty_wheel_panel()` returns the controls and the board as one fragment, which is how the
generated setup view shows the wheel without copying any of this: it pairs that fragment with
`DUTY_WHEEL_CONTROL_STYLES` and `render_duty_wheel_controls_script()` and brings its own wrapper
and heading. Every hook the panel owns is prefixed — `duty-wheel-randomize`,
`duty-wheel-move-merchant`, `duty-wheel-readout`, `.duty-wheel-controls`, `.duty-wheel-counts` —
because the setup page already has a `.controls` row and `.readout` spans of its own, and the
script is one IIFE that reaches for those hooks and nothing else on the host page.

Asked for `turn_controls`, the wheel also draws a visual-only shell of the turn flow to come, as
four plaques in the black corners the green hexagon leaves: `Sow` at the top left, a cubes-in-hand
counter at the top right, `Reset` and `Confirm` at the bottom left, and `Action` and `Tithe` at the
bottom right. The renderer draws a picture and nothing else — nothing here is clickable, nothing is
counted, no GameState is touched, and only `Sow` is drawn as reachable, the rest dimmed to
`TURN_CONTROL_DISABLED_OPACITY`. `data-component="duty-wheel-turn-controls"`, `data-turn-state`,
`data-turn-control` and `data-turn-counter` are the handles a page takes hold of to drive it, and
the game table is the page that does.

Movement on this wheel is keyed to **board positions**, not to the names printed on the tiles. A
board position is where a space stands — `city`, `north`, `north_east` and the rest — and the
renderer reads both the names and the directed edges between them out of the engine's own
`configs/board.json` rather than keeping a copy. A **duty category** is the tile lying on a
position, and turning the tiles moves categories around while moving no position at all. So every
space carries three names: `data-duty`, the prototype's stable id for the space and no use for
saying where a cube may go; `data-board-position` with `data-board-position-index`, which is what
movement means; and `data-duty-category`, the tile there now, which is the one a roll rewrites.
The wheel's own ids are the prototype's default arrangement, so `clerical` is the space Clerical
happened to start on — the east one — and reading it as a duty is exactly the mistake this split
exists to prevent.

Every arrow carries the pair of positions it runs between, as `data-from-position` and
`data-to-position`, each with its board index beside it. The middle four are named in the layout;
the ring's eight are one shape turned around the board, so which pair each stands between is worked
out from how far it has been turned — `ring_arrow_ends()` — and then said in the engine's terms.
One question answers both families, which is how a page finds the ways out of a position without
counting elements or trusting their order, and a test holds the drawn edge set to `board.json` edge
for edge. The City, east and west turn out to be the only three positions with more than one arrow
leaving them, and nothing had to be written down to say so. Kogge, which adds a first step from the
City to east or west, and Cloisters, which drops one placement from a route, are graph modifiers
the engine applies on top of these edges; neither is drawn here.

Two things decide where the plaques stand. They are drawn inside the SVG rather than beside it,
because the composed table sizes the wheel by its SVG and a control outside it would neither scale
with the board nor stay anchored to it; and they are drawn outside the group the renderer scales
the board in, in the canvas's own units, because that is the space the corners are measured in.
The corners themselves are the one part of the canvas nothing else uses, and they sit inside the
box the game table crops the wheel to — the hexagon's own bounding box — so the shell is carried
onto the table rather than being cut off the side of it. `turn_controls` in
`duty_wheel_layout.json` gives the four anchors, each the corner of its own group nearest the
corner of the board it hangs in, so a row grows inward from the corner it belongs to. Tests pin
both halves of that: no plaque corner falls on the green, and every plaque survives the table's
crop with a cube's clearance to spare.

The shell is off unless a page asks for it, so a page that was not designed around it does not
quietly grow one: the generated duty wheel page and the game table both pass `turn_controls=True`,
and `game_setup.html`, which hosts the same panel, is unchanged and shows no plaques.

Asked for the board the prototype drew — static, with the Merchant on
`merchant_token.baseline_position` — every drawing element the renderer emits matches the
baseline's numerically, bar one: the Allocation title sits 0.1px lower, because the baseline's own
title is that far off the offset the other eight share. The generated markup also carries
`data-duty`, `data-token`, and `data-tithe-token` attributes the baseline has no need for, so the
two files are not byte identical.

## Alms Table renderer extraction

`prototypes/alms_table.html` is the untouched visual baseline for the Alms Table, and
`prototypes/alms_table.svg` is the same board as a standalone SVG, for looking at or embedding
without the page around it. `prototype_sources/alms_table.py.txt` preserves the Python that drew
them, reference-only as always: read for intent, never imported or run.

The board is one grey strip split by a rule into the two things it tracks. Left of the rule is the
race, steps `0` to `6` with a 2x2 of player discs on each and a pocket for the first disc to reach
`6`, and the three threshold rewards printed underneath against the steps that pay them. Right of
the rule is the record, which is what survives the round reset: four sockets, one per round, and
beneath them the season-end key from cubes owned to VP.

Two things about the copy are worth knowing before anyone goes looking. The files arrived named
`construction_track.*` and the page still titles itself `Pilgrim — Construction Track` with an
`<h1>` of `Construction track`; the drawing's own caption reads `Alms Table`, as does `TITLE` in
the source, and the content is the Alms Table throughout. The baseline is kept exactly as it
arrived rather than retitled, the same way the other baselines keep the titles their sources gave
them.

`alms_table_layout.json` and `render_alms_table.py` are the structured renderer extraction. The
JSON says where each anchor sits — the step centres, the pocket, the first reward badge and the
pitch below it, the first placeholder slot and the first key row — and the module says how the
pieces around them are drawn, the same split the duty wheel uses. None of the pieces are new: the
disc is the piety-track disc at a larger radius, the star is the piety-track star, and the cube is
Player Board v2's cube, which is why the Alms Table reads as part of the same set.

### Widened to the seat it stands above

In the game table the Alms Table heads the column the player boards start under, and it was widened
to the seat below it. That width is native geometry — `panel_width` and the viewBox around it grew,
and nothing is scaled — but how much of it to buy is a question about the composed table, because
the two boards are not drawn at the same scale. The Alms Table is pinned to the piety track, for the
player disc the two share, and the piety track's units are the smaller of the two: one unit here
renders 1.48688 of the pixels one player board unit does. `UNITS_PER_PLAYER_UNIT` in
`render_alms_table.py` is that ratio, and `PLAYER_UNIT` its reciprocal — one player board unit
measured in this board's units. The ratio belongs to the composed table rather than to either board,
so it is re-solved each time the table is recomposed, and the game table's tests check it against
the real solve rather than trusting the number written here. A seat's 692.8 units came to 536 at the
ratio that held when the width was chosen, which is what the board is; at the ratio that holds now
they come to 466, so the board stands proud of the seat until its width is re-fitted.

The extra width all went right of the zone divider, which has not moved: the race track, the
reward lines and the title are where they were, and the record zone got both a wider span and a
wider right margin. The ratio is exact at the one viewport the table is solved for and drifts a
few percent either side of it, because both panels carry fixed chrome that does not scale with the
cube. Pinning the width exactly at every window size would mean giving up the disc match with the
piety track, which is the older and more visible of the two.

The same conversion is what sizes the pieces. The dashed placeholders and the season-end cubes are a
seat's cube in `PLAYER_UNIT`s with a seat's `TOKEN_GAP` between them, so a cube won here is the cube
it came off a player board as, spaced as it was in a Village grid — and because the board used to
draw a 13-unit cube at a scale where that came out 20% oversized, the cubes got smaller as the
board got wider. Both are imported rather than written down, and a seat takes them from the duty
wheel in turn, so the three boards draw one piece at one size and none of them can drift from the
others by standing still. Only the side-to-side gap crosses over: no cubes sit above or below each
other here, and the scoring key's rows are a star apart rather than a cube apart — `row_height` is
the star's own diameter. `cube_rect` is the one helper that draws the box for all of them, socket,
placed cube and printed key alike, so a placed cube covers the dashed outline it fills exactly
rather than nearly. `Season end winners` and the `2`/`4`/`6` the rewards are filed under are
`ROLE_FONT_SIZE` the same way, so they read as `Fields` and `Stone Mason` do on a seat.

Matching the cube moved two things around it. The socket row is no longer given a starting x by the
layout: where it starts depends on the cube and the air beside it, both of which belong to the
seats, so a number here is one that goes stale the next time they resize — as it had. It now falls
out of the record zone's own centre, and a test holds it there. The scoring key's ladder did keep an
x, because where it sits is a judgment about margins rather than a derivation, and it moved four
units left so its widest row keeps the air it had between the fourth cube and the star it pays.

The header ornament came along with the cube without being touched. Its lobes and rule are written
in cubes — `0.354` and `1.154` of one — precisely so they match the wheel's, so correcting the cube
corrected the motif with it; it was rendering about 8% over the wheel's and now sits where the rest
of the table does.

The scoring key's stars grew with the rest of the zone. The VP inside one is now
`STEP_NUMBER_FONT_SIZE`, the size the track numbers its steps, so a score on this board reads at
one size wherever it is printed; `STAR_LABEL_OFFSET` follows from that size rather than sitting
beside it, which is what keeps the digits centred on the star as it changes. It is the one number
on the board set plain rather than bold, since the star around it already stands the score out.
The star itself went
to 18 units so a two-digit VP still sits inside its waist rather than across its points. What caps
it is the four rows: a five-pointed star stands its radius above its centre and sin(54) of that
below, so at this row height anything past 19.9 would have the rows touching, and
`test_a_star_holds_its_vp_at_the_size_the_track_numbers_its_steps` holds the size against both
bounds rather than only pinning it where it landed.

Two smaller things went with it. The `1st` pocket is centred in the lane between the track's last
rule and the zone divider — measured by `bonus_pocket_center_x` rather than written down, since
that lane is wider than a step and the pocket used to sit on the track's pitch inside it, off to
the left. And the header ornament's trefoil is the duty wheel's: that board draws its lobes at 4.6
units against a 13.0-unit cube and holds the rule 15.0 clear of them, and carrying those over in
cubes puts the two marks at the same size on screen. They used to be this board's own 4.6 units,
which at this board's scale read a fifth larger than the same mark over every duty on the wheel.

The rule the lobes sit on is this header's rather than the wheel's, because this board has a header
to span and a duty space does not. `ornament_rule_arm` runs the right arm out to
`ORNAMENT_RULE_CLEARANCE` short of the zone divider and gives the left one the same length rather
than a reach of its own, so the mark stays symmetrical about the lobes. The left arm is then the
only thing on the board that could run into the title, and it ends 11 units clear of it.
`test_the_ornament_rule_spans_the_header_symmetrically_and_touches_neither_end` holds it to all
three: symmetry, the gap off the divider, and the gap off the title. That last one is checked
against a measured `TITLE_RIGHT_EDGE`, since there is no font metric here to compute it from.

The numbers the board prints about the game are not in the layout JSON. `configs/alms.json` is the
source of truth for how far the track runs, which steps pay which reward, and the season-end VP
per cube, and the renderer parses it with the game's own `alms_from_dict`, exactly as the piety
track reads `configs/piety.json` for its stars. So the row of steps is as long as `max_position`
says, there is a reward line per configured threshold, and the key has a row per scoring entry
above zero — change the config and this view follows without anyone editing the UI layer. The
four dashed sockets are counted from the same key, which is the board's own logic: four rounds,
four cubes, four sockets, so an impossible fifth has nowhere to go. What the layout does own is
the prose beside each reward, which is display copy the config has no opinion about, and a layout
that draws a different number of steps from the one the config defines is rejected rather than
drawn.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_alms_table.py
```

The generated overview below also produces it. Both write `generated/alms_table.html`, which is
not committed.

One thing is drawn differently on purpose. The baseline puts a full 2x2 of discs on every step,
as a diagram of where discs go; the generated page draws player state instead, so there are four
discs and they all stand on step `0`, where a round starts them. Each takes its own corner of the
2x2, so four on one step stay legible. `render_alms_table_svg(..., positions=...)` takes a seat to
position mapping, which is all a later PR needs to walk them rightward along the track the way the
Piety track moves its own discs — no new geometry, and no controls in this PR.

Everything is labelled: `data-component="alms-table"` on the board, `data-alms-position` on each
step and on each disc, `data-player` and `data-player-disc` on the discs themselves,
`data-alms-threshold` on the reward lines, `data-placeholder-slot` on the four dashed squares at
the top right, `data-season-end-winner-slot` on the cubes that fill them, and
`data-season-end-rank` on the key rows. The baselines carry none of these attributes, which is the
only reason the generated SVG and the baseline SVG are not byte identical — with the hooks
stripped and the diagram discs set aside, every drawing element matches the baseline's exactly,
and a test keeps it that way.

The generated Alms Table carries local UI/debug controls. **Move Player 1 up** and **Move Player 1
down** walk the white disc along the track, and the button at the end of its travel is disabled
rather than silently doing nothing. Only Player 1 moves; the other three stay on step `0`, where
they keep their own corners of the 2x2 so the white disc leaving does not disturb them. The four
**Add _colour_ cube to Season end winner** buttons drop a cube into the first free socket, and
once all four are filled the buttons switch off. A readout beside them says where Player 1 stands
and how many cubes are down. All of it is visual/debug state only: nothing here mutates
`GameState`, decides whether a player really won a round, or scores anything.

Player 1 has one space past the end of the track: the `1st` pocket, `RANK_FIRST`, which the board
already draws for the first disc to reach the top. `mover_path` is the whole of the movement rule
— `[0, 1, 2, 3, 4, 5, 6, "rank_1st"]` — and `next_mover_position`, `previous_mover_position`, and
the page's own buttons all just step along it, which is why neither end can be walked off. The
pocket holds one disc, so a disc there takes the pocket's centre rather than its seat corner in
the 2x2; `alms_position_target` decides which. Note that the pocket is a space on the race track,
left of the divider, and has nothing to do with the record's cube sockets at the top right: the
disc races into one, the cubes are recorded in the other, and a test pins the two apart.

Like the duty wheel, the renderer draws everything the controls can switch on and hides it, so a
click flips opacity rather than building SVG in the browser: all sixteen winner cubes, one per
socket per player, are already there at `opacity="0"`. The disc is the exception — it slides, so
the page sets its `cx` and `cy` from `disc_targets`, the same coordinates the renderer used, and
updates its `data-alms-position` so the markup stays honest about where it is. That is also why a
disc that can move is lifted out of its step group into its own layer when `interactive` is on:
sliding it must not leave it parented to the step it started on. That layer is drawn after the
`1st` pocket, since the pocket is painted solid and would otherwise hide the disc that lands in
it. Ask for the board without `interactive` and none of that is emitted, leaving exactly the
picture the baseline draws.

The winner cubes take the Player Board v2 cube colours rather than the track's disc colours,
because they are the player's own cube moved onto this board, while the discs are the piety-track
disc. A test pins them to `player_boards_v2_layout.json` so the two cannot drift apart. A cube is
exactly the size of the socket it fills, and the script hides the socket underneath it as well, so
a filled socket shows no dashed edge rather than a dash peeking out from behind a stroke.

Every square on this board is the same cube — the empty socket, the winner's cube that fills it,
and the printed key cube counting toward a score — so all three read from one `record.cube` and
are drawn at one size and one stroke weight, `1.2`, which is what Player Board v2 draws a cube at.
The baseline gave each kind its own weight (`1.4` for a socket, `1.5` for a key cube), so this is
the one place the generated board deliberately departs from it: the parity test restrokes the
baseline's fourteen cubes before comparing, and still holds every other element to the letter.

The hooks are namespaced — `alms-move-up`, `alms-move-down`, `alms-readout`,
`.alms-table-controls` — and the script is one IIFE, so the panel can later join a page that
already has controls of its own without either side reaching into the other.

The generated page is titled `Alms Table` rather than the baseline's leftover `Construction
track`, since nothing is preserving fidelity to a wrong title once the renderer owns the markup.

The controls move pieces and nothing else. The board is not in the setup view, it does not connect
to `GameState`, and it implements no gameplay rule: no Alms legality, no season-end resolution, no
scoring, and no `apply_action` integration. Those belong in later PRs.

## Game setup debug view

`generated/game_setup.html` is the first composed view: it has no prototype baseline of its own
and no renderer module of its own. `generate_game_setup.py` puts the generated map, the generated
3-4 player piety track v2, generated building tiles, and generated pilgrimage sites on one page and
adds a little client-side interaction.

The generated setup view now uses the 3-4 player Piety Track v2 renderer above the map, so the
track arrives ornamented, titled, and with its four discs already tagged with whose they are. The
setup piety buttons still move local UI/debug discs only; this does not mutate `GameState` or
implement gameplay rules.

It uses the `3_4_player` variant only, because the page has controls for four players. The 2-player
track is intentionally not shown here; `generate_piety_track_v2.py` still produces both v2 variants
on the standalone v2 page, and the older `generate_piety_track.py` remains available as its own
standalone generated view.

What moves, and what it means:

- `EDGE_HEX_PATH` lists the eligible edge hexes clockwise from `J3` by map label. It hops over the
  four special corner hexes `F1`, `B6`, `G11`, and `L6`, which leaves 26 hexes — the engine's round
  track length. Both the setup slots and the ship ride that path, and the labels are resolved
  through the map's own label table, so neither can drift away from the board.
- The ship sits in the upper part of a hex the way the ship marker tiles draw it, and starts on the
  hex that carries setup slot 1. When the ship actually moves is still a rules question this page
  does not answer.
- `Start roll` 1-6 picks the hex setup slot 1 sits on (`E1`, `D1`, `D2`, `C3`, `C4`, `B5`), and the
  rest of the slots follow it clockwise. Changing the roll re-places every slot and sends the ship
  back to the new first hex.
- The slots themselves are `SETUP_SLOTS`, one hard-coded example schedule of 26 rounds. This page
  deliberately does not call `pilgrim.setup.generator`, so the layout can be looked at without a
  seed or a scenario. A building slot recolours its map hex in the catalog palette and writes the
  tile's own name into it, a word to a line; it does not lay a second hex on top of the board. The
  fill goes in through `render_map_svg(layout, tile_overlay=...)`, which drops a fragment onto the
  tile fills before the map draws its rivers, hex edges, and labels, so a placed building keeps
  every line and label the map would have drawn there. `render_buildings.py` and the building tiles
  page are untouched and still draw full tiles. An empty slot draws nothing. Which round a slot
  belongs to is not written on the map.
- A pilgrimage site slot is filled the same way: its hex takes the site orange and carries the
  site's star, VP value, and `P`/`S` values, scaled from `render_pilgrimage_sites.py` down to the
  map hex. The four site slots always take the first four sites in `pilgrimage_sites.json`, in
  file order. That is deterministic debug behaviour only; drawing sites at random is not
  implemented yet, and the fifth site is unused.
- Each player has one disc on the piety track. `+1 piety` and `-1 piety` move it one position and
  clamp at the ends of the track.
- The page moves the discs the v2 track itself drew rather than laying its own set of circles over
  them, so their colours, seats, and start position all come from `piety_track_v2_layout.json`.
  The script finds each one by `data-player` inside `data-component="piety-track-v2"`, never by
  its order in the SVG, and `data-player` is scoped that way because the player boards and the
  buttons carry the same attribute.

The generated setup view now includes a right-side Player Board v2 panel. The panel is local
UI/debug state only: it can move serfs from Village to Abbey and move acolytes between Abbey and
role circles. This does not mutate `GameState` and does not implement gameplay legality.

The setup view now includes local UI/debug controls for buying buildings from the setup map and
donating/flipping bought buildings on Player Board v2 slots. Buying removes the building from the
map visually and places it into the first empty player-board building slot. Donating flips a
bought building in slot 1-6 to its donated side using the existing 2/4/6 VP level mapping. This
does not mutate `GameState` and does not implement purchase/donation legality.

A building standing on the map is available, one in a player-board slot is bought, and a bought
one that has been flipped is donated. Only `"building"` setup slots are for sale — empty slots
hold nothing and site slots hold a pilgrimage site — and a building is keyed by its setup slot
rather than by the hex it currently sits on, so changing the start roll afterwards moves the
unbought buildings around the map without giving a bought one back. Each slot's content is drawn
once into a `defs` block, as the building's own tile colour and label for the bought side and as
the donated tile's star and VP value from `render_donated_buildings.py` for the flipped side; a
slot shows one by pointing its `use` element at it. Both sides recolour the slot the way a setup
slot recolours a map hex — a fill on the slot's own hex path, `stroke="none"`, no tile border of
its own — and the slot's dashed outline is drawn last, over the content, so it stays the only
boundary a slot has whether it holds a building or not. `building_ownership_state`, `buy_building`,
and
`donate_building` are the same two moves in Python, so the rules the buttons follow — first empty
slot, one flip per building — can be tested without a browser.

The four boards come from `render_player_boards_v2.py`, drawn with `interactive=True`: that draws
every slot a cube can stand in — all eight Village and Abbey slots, and for each role circle both
the centred slot and the side-by-side pair — and hides the ones the state does not need, so the
buttons only flip opacity. A cube is a serf while it is in the Village and an acolyte once it
reaches the Abbey or a role circle, and the acolyte controls therefore never mention the Village:
the only way out of it is `Move serf to Abbey`. A role circle holds at most two acolytes and the
Abbey holds the eight its slots give it, so a button that would break either is disabled. Every
board starts from `default_player_board_v2_state`, the board the prototype draws.

The generated setup view now includes the Duty Wheel panel. It reuses the Duty Wheel renderer and
includes local controls for sample Duty tile/Tithe setup cycling, Merchant movement, and 2p/3p/4p
cube-column views. This is UI/debug state only and does not mutate `GameState` or implement
gameplay legality. The wheel sits in its own full-width panel below the setup area and the player
boards, so the map keeps the width it had, and it draws at its own size rather than filling that
panel. Sow animation is still not implemented.

All of it is visual only. The buttons change SVG attributes; they do not touch `GameState`, call
`apply_action`, pick legal actions, or write scenario state. The view exists to check layout and
to confirm markers can move before any of that is wired up.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_game_setup.py
```

The generated overview below also produces it. Until one of the two has been run, the
`generated/game_setup.html` link in `index.html` is dead like the other generated links.

## Game table layout

`generated/game_table.html` composes the existing UI/debug renderers into a full four-player table
view, laid out as two rows. The top row is three panels across: the Alms Table, then Piety Track v2
above the Duty Wheel, then the map board. Under it stands one unscaled horizontal row of all four
Player Board v2 boards, red first, starting under the Alms Table column. The composition page owns
shared scale and placement; individual renderers continue to own visual geometry. This is
visual/debug layout only: it does not mutate `GameState`, and it implements no gameplay rules.

The stage is left-aligned rather than centred, which is what lines the two rows up: both start on
the same vertical, so the leading board sits under the leading panel of the row above.

That division of ownership is why widening Player Board v2 needed nothing here. A seat's width is
solved from the board's own shape, so a wider board is simply a wider seat; the table has no
separate width to adjust and must not scale the boards down to win the room back.

`game_setup.html` remains the control-heavy debug sandbox. The table page has no buttons and no
script at all, and no text either — no heading, no description, nothing above the boards. It opens
straight into the table, because what is being judged is the arrangement rather than a page about
the arrangement. The tab keeps a name, which is the one piece of text a window needs.

### One shared scale

Each renderer draws in its own units, so handing every panel a width by eye makes the same wooden
cube come out a different size on each board — a cube is 13 units on the duty wheel but inside a
group the wheel scales, 10.83 on the alms table, and 14 on a player board, against viewBoxes of
1104, 572 and 706.8.

So the page stops choosing panel widths. One physical reference is measured in each board's own
units, and every display width falls out of it:

```text
display width = --cube * (cropped viewBox width / cube size in that board's units)
```

A single `--cube` therefore drives the whole table, and every board stays in proportion when it
changes. Two boards draw no cube at all, so each is anchored on a piece it does share:

- the Piety Track on the player disc it shares with the Alms Table — both draw it 18 units across,
  so matching their units-per-pixel matches the discs on screen. This is why `--w-alms` is a
  multiple of `--w-piety` rather than of `--cube` directly, and why the Alms Table is not simply
  handed the seats' width: it buys that width in its own units instead, as above.
- the map on the board hexagon the Duty Wheel's was derived from, so the two greens come out the
  same width.

The Duty Wheel is the one panel not sized this way: it fills whatever height the row has left once
the Piety Track and the chrome are out of it, which comes to rather less than its own width would
give it. So the cube it draws is not `--cube`, and anything meant to match a wheel cube has to be
sized against the wheel rather than against the cube.

That is what a seat is. The seats used to be fitted the other way about — stacked to exactly the
Duty Wheel's panel height — which made a board's *shape* decide the scale it was drawn at, and left
the cubes matching only because the board happened to be the height it was. Shortening the board
took that match from 2% out to 20%. A seat is now as many cubes wide as its crop measures, times
the wheel's own shortfall against `--cube`, so a Village cube and a duty tile cube are the same size
exactly, at any board height. The two are mutually dependent — the seat row is part of the height
the cube is solved against — so they settle together in the solve below rather than one being solved
before the other.

One consequence worth knowing about, not new to this arrangement so much as uncovered by it:

- The Alms Table no longer comes out a seat's width. It is 536 of its own units because that was a
  seat's width at the ratio which held when it was widened; a seat is narrower now, and this board
  is pinned to the Piety Track rather than to the seats, which is what keeps the two boards' player
  discs the same size. It therefore stands about a seventh proud of the board below it until its
  own width is re-fitted. `UNITS_PER_PLAYER_UNIT` is re-solved whenever the table is recomposed —
  growing the building slots to a map hex's size moved it last, by a third of a percent — so pieces
  and type written in a seat's units, its cubes and its labels, do still come out a seat's size.

A third was there for a long time and is now closed: a building slot used to be a map hex counted in
`MARKER_CUBE`s, the unit a player board writes its geometry in, which stopped being the board's cube
when the cubes were resized to the wheel's — so slots rendered a fifth short of the map hex they
stood for. `BUILDING_SLOT_HEX_SIZE` is measured off this solve now rather than derived, and the
slots interlock rather than sit one to a column, which is how they grew to a map hex's size without
taking the board wider with them. `test_ui_debug_game_table.py` holds the two together.

### Cropping, and the one place a drawing is touched

Each of these SVGs was authored as a standalone page, so its viewBox includes a heading, a subtitle
and a backdrop. The Duty Wheel is the worst: its playable hexagon is 717x848 inside a 1104x1425
viewBox, so nearly half the panel is page furniture, which would be paid for in the middle of a
table. Each fragment's viewBox is therefore pointed at its own panel instead. Nothing is deleted —
the extra elements are simply outside the view — and no renderer changes.

The crops are measured off the frame each renderer draws rather than off everything it draws,
because those page backdrops overhang the panel by 18 units on the Alms Table and 20 on the Piety
Track against 1 on a player board, and cropping to them would bury the two ornamented panels in far
more black than a board carries. The two hexagon boards are cropped off their hexagon instead, since
they are meant to read as the same physical board.

The one place the composition touches what a renderer drew is the Duty Wheel's hexagon, which was
drawn by hand about 2.5% taller than a regular hexagon of the same width, so at equal widths it and
the map did not read as the same shape. `duty_hexagon()` replaces it with a true regular hexagon of
the same width and centre; only how far the empty top and bottom points reach changes, and no tile
on the board moves. It is done in the composition so the standalone Duty Wheel page keeps the
hexagon it has always had, and it fails loudly rather than silently mis-cropping if the renderer
stops drawing the path it was measured against.

### The converged solve

Every board is cropped to its own content plus a margin, and that margin has to come out the same
number of pixels on all of them — which is whatever a player board's 6 units happen to render as.
But that figure depends on how big everything is, the sizes depend on the crops, and the crops
depend on the margins. Rather than pretend that chain has a first link, `solve_table_scale()`
iterates the whole thing to a fixed point.

Everything it measures is read from the layout files rather than hardcoded, so the crops follow the
renderers: the panel frames from the alms and piety layouts and `board_geometry`, the map's hexagon
from `edge_hex_radius`, and the wheel's from its own `ground_path`, `center` and `scale`.

### Heights, and why the gaps come out even

The top row's height is whichever of the map or the Alms Table needs more of it — in practice the
map, now that the seats no longer stand under the Alms Table — and neither depends on the Duty
Wheel, so it can be read before the wheel is sized. The wheel is then handed what is left once the
Piety Track, both panels' chrome and one gap come out of it. Because the stacked column has the
same shape as the row is measured against, two panels and one gap, the space above the wheel comes
out to exactly `var(--gap)`: the same distance used between the player boards, and the wheel's
bottom edge lands on the map's.

The two rows then compete differently. Each asks for the window's width on its own — neither is
inside the other any more, so neither bounds the other — while for height they take the window one
after the other. With four seats in the stack the height is what binds at the reference window, and
the shared cube comes out about 6% under what the two-seat table reached; give the page the 1142px
the two rows want and the width takes over instead, at a cube a fifth larger than that table ever
reached. Nothing is scaled to fit: there is one cube and every panel is a fixed multiple of it, so
this shows up as a smaller cube for the whole table rather than as any board drawn at a size of its
own.

That is computed in CSS from `--cube` rather than baked in as a scale factor, so it holds at any
window size rather than only at the one the constants were solved against. It is the reason the Duty
Wheel is the one panel sized by height (`--h-action`) while every other panel is sized by width.

Below 1080px there is no row height to fill, so the row wraps and the wheel goes back to being sized
by width like everything else.

Nothing is redrawn here. The alms table, the piety track, the map with its setup overlay, the duty
wheel, and the boards all arrive through the same functions their standalone pages call —
`render_setup_map_svg` in `generate_game_setup.py` for the three-layer map, and
`render_player_board_v2_svg` for one board at a time.

Every seat the layout describes is drawn, in the layout's own order read from the red board rather
than from the first one — red, yellow, blue, white — so the run is the seating order the layout
already gives and red simply leads it. The generated game table now has compact controls under the
Alms Table: player count plus setup-roll buttons, Alms/Piety disc movement controls, and Player
Board v2 acolyte movement controls. `S->A` on that last row moves one cube from the selected
player's Village to their Abbey, which is a serf becoming an acolyte — the game setup page's
serf helper, as one button rather than four, because the row already names the player it acts on. It
stops for the two reasons that page stops: an empty Village has nobody to send, and a full Abbey has
nowhere to put him. `A->C` and `V->C` sit beside it and send one cube on to the City in the middle
of the Duty Wheel, from the Abbey or straight out of the Village; each stops when there is nothing
to take or no room to stand, and the City column holds six. The game table also includes compact
resource controls for the
selected player and Alms Table season-end winner controls: `AT+` moves one cube from the selected
player's Abbey into the first empty Season End Winners socket, and `ATr` returns every placed cube
to the Abbey of the player whose colour it carries. The same row buys and donates buildings: `Buy`
takes the chosen building off the setup map into the selected player's first empty slot, and
`Donate` flips the chosen slot to its donated side (level 1 is 2 VP, level 2 is 4 VP, level 3 is
6 VP). A bought building does not come back when a setup roll moves the map around. The compact
controls now include Duty Wheel randomize and Merchant advance buttons: `R` cycles the wheel's own
sample Duty tile arrangements and `M+` walks the Merchant clockwise around the eight duty tiles,
Taxation included and the City excluded. Player-count controls also update Duty Wheel starting cube
columns locally: 2P uses two player columns plus black, 3P uses three player columns plus black, and
4P uses four player columns without black. The City takes no neutral column, so it simply drops the
seats that are not playing: 2P leaves red and yellow standing there, 3P adds blue, 4P adds white.
Cubes walked into the City stay where they were put when the count changes, since the count only
picks which of the wheel's tallies shows and a column is redrawn in all three. The wheel here also
carries its turn-control shell — `Sow`, the cubes-in-hand counter, `Reset`/`Confirm` and
`Action`/`Tithe`, in the four black corners of the hexagon's box — which is drawn inside the wheel's
SVG and so is scaled and cropped along with it.

All five of those plaques are wired here, as the shape of a turn drawn on the board. `Sow` arms the
nine spaces: each is outlined in cream and takes a click, the eight duty tiles and the City alike.
Clicking one lifts the active seat's cubes there into the counter in the corner — `■ × N` — outlines
the space in the colour of the seat the turn belongs to, and sets the hand walking: one cube goes
down at each position it comes to, and the counter falls as they do. It stops only at a fork, where
it turns the ways out green and waits for one to be clicked; clicking one puts a cube down at the far
end, records which way was asked for in `data-last-route-choice`, and walks on. When the hand is
empty the turn is `sow_complete`, and every tile the seat has a cube standing on is outlined in cream
to be picked from: clicking one takes it as the turn's duty, rings it in the seat's colour, colours
in the three lobes of its trefoil, and lights `Action` and `Tithe`. Pressing either sends every one
of that seat's cubes home from that tile to its City column — the ones that were standing there
before the turn as much as the ones it has just sown — and stays lit to say which was pressed. `Reset` hands the
board straight back. The phases are `idle`, `sow_armed`, `sowing`, `branch_choice`, `sow_complete`,
`duty_selected` and `resolution_selected`, carried on `data-turn-state` beside
`data-turn-current-position`, the `data-turn-route` walked so far, `data-turn-duty` and
`data-turn-resolution`, and the styling all hangs off attributes — `data-turn-start-candidate`,
`data-turn-start-selected`, `data-turn-branch-choice`, `data-turn-duty-candidate`,
`data-turn-duty-selected`, `data-turn-control-enabled` and `data-turn-control-active` — so a click
sets a word and the stylesheet does the rest.

All of it moves in board positions. A click hands on `data-board-position`, the cubes to pick up
are the ones showing inside that space, and the ways out are the arrows whose `data-from-position`
is that position, gathered once into `outgoingEdgesByPosition`. Nothing lists the forks: one way out
is not a choice, so the walk never asks about it, and the City, east and west are simply the three
positions with more than one. A route choice is recorded as `city:north`, not as the tiles that
happen to be at either end. So `R` can turn the duty tiles as often as it likes — rewriting each
space's title, Tithe token and `data-duty-category` — and the board still branches in the same three
places, because a roll moves duties between positions and never moves a position. The Kogge and
Cloisters modifiers that would add and drop these edges are still to come.

A hand picks up its own cubes and nothing else. The turn belongs to a seat — seat 1, red, named in
its own colour on the stage as `data-active-player-seat` and `data-active-player-color`, and on its
board as `data-active-seat` — and the player that seat is is asked of the board itself rather than
worked out, since seat order and player ids are not the same list: the first seat is red, and red is
`player_two`. So clicking a space takes only the cubes there whose `data-player` is the active
seat's. The other seats' cubes stay standing, the neutral column's black ones are nobody's to take,
and the City slots nobody is standing in are hidden and so never counted. A space showing none of
that seat's cubes is nothing to start from: the click is spent, the board stays armed, and the next
one still works. Turn order and turn advancement are still to come, so the active seat only ever
moves when a count change leaves it with no board to sit at.

The board whose turn it is says so itself, rather than being ringed. Every Player Board v2 is drawn
holding a wash of its own colour rising off its bottom edge — `data-active-player-glow`, laid
straight onto the parchment under everything else and left at `opacity="0"` — and the game table's
one rule turns up the wash on the board wearing `data-active-seat="true"`. A ring drawn round the
outside of a panel is a browser's idea of a selected thing; a board on a table lights up instead.
Because the layer is drawn with the board and only shown from the page, the table writes no size and
restyles nothing, so a change of seat cannot move a row. The rect covers the whole panel and takes
the panel's corner radius, and the shaping is the fade's: strongest along the bottom edge at
`ACTIVE_GLOW_OPACITY`, gone by the top of the building band, which it reads back off the panel
height it was one of the terms in. So it passes behind the dashed slots and never reaches the role
circles, the readouts or the banners, and nothing about the geometry, the cubes or the type changes.
The wash is a colour of its own in the layout beside `fill` and `stroke`, because white had a
problem the other three do not: white on parchment is barely a change, and turned up until it is one
it reads as a glow round the board. So white's wash is `#8B7B4E`, the warm brown its own cubes are
outlined in — the colour already on that board for making white legible against this parchment,
which is the same problem twice. The boards' own page never turns any of it up, so
`player_boards_v2.html` looks exactly as it did.

Picking a cube up and putting one down are the same trick run in opposite directions. The wheel
draws every slot a seat's column has room for and hides the empty ones, so a cube is lifted by
hiding the rect it stands in and sown by showing an empty one: nothing is ever drawn into the wheel
or cut out of it, and a turn is a set of opacities to put back. Sending cubes home at the end of the
turn is the same trick a third time: they are hidden on the tile and empty slots are shown in the
City column. So `Reset` undoes the turn in the order it was done, last thing first — what came home,
then what was sown, then what was picked up — since a cube can be sown into the very slot it was
lifted out of and recalled out of that same slot again, and each layer has to hand the board back to
the one beneath it before that one has its say.

Which tiles are on offer at the end is read off the board rather than off the way the hand walked:
`occupiedDutyPositions` is every tile the seat has a cube standing on, less the City, since the City
is not a duty. A seat has acolytes out on the wheel before its turn begins and those are as much its
own as the ones it has just sown, so asking where the walk went would offer it the tiles it happened
to pass and hide the rest of its own — including, often, most of them, since a short walk touches
two or three of eight. It also asks the same helper the hand picks up by,
`visibleActivePlayerCubesForPosition`, which is what leaves the other three kinds of cube out of the
choice without any of them being named: another seat's, the neutral column's, and the slots nobody
is standing in — drawn but hidden, so not visible — are none of them this seat's standing cubes. The
tile the turn started from usually drops off the offer for the same reason it is read off the board
at all: the hand took everything of the seat's that was standing there. The City is found as
the one space with no place in the ring of arrows — the eight tiles each carry a
`data-duty-ring-index` and it does not — rather than by its name. The trefoils are drawn as one layer
over the whole board rather than inside the nine spaces, so each carries a `data-ornament-position`
saying which space it stands over; without it the only way to the right trefoil would be counting
groups in the order they were drawn.

A column can fill up. A tile shows a seat three cubes — what fits between the baseline and the
title — while the rules cap nothing, so a hand can reach a position with nowhere to put the next
cube. It stops there and keeps what it is still holding, the counter goes on showing it, and `Reset`
is the way out; this is a limit of what the wheel can draw, not a rule. The City column can fill the
same way, six to a seat, so a cube sent home that finds no slot waiting is left standing on its tile;
nothing is lost either way, since a cube is only ever hidden in one place and shown in another.

`Setup`, the button after `R` on the first row, deals the game before the game. Every seat starts
with five acolytes in the City and sows them out onto the wheel, one seat after another, and only
when the last has finished does the first turn begin. Pressing it clears the seats' cubes off the
eight duty tiles — the neutral column's black ones are seeded onto the ring and no seat plays them,
so they stay where they are — stands five in each playing seat's City column, and hands the wheel to
the first seat.

A setup sow starts itself. There is one place it can begin from, so asking which would be a click
for nothing: the seat's five come up into the hand the moment the wheel reaches it and the walk
begins, which — starting where it starts — means it stops at the City's fork straight away with
`city -> north` and `city -> south` lit. So `Sow` has nothing to ask and stays dark for the whole of
a setup, no space is ever armed to be clicked, and the first thing to do is take a road. Nor is the
City ringed in the seat's colour the way a space a turn started from is: the ring is the answer to
which space to start from, and a setup seat was never asked, so on the one space it could ever
appear it would be colouring in an answer to nothing. The two green roads out are the whole of what
a setup is waiting on. `beginSowFrom` is asked for that with `{ ring: false }`, which is the only
difference between a setup's start and any other; leave it out and the ring goes on as it always
did. From there it is the sowing already described, unchanged. What is different is the end of it: a
setup sow
chooses no duty, so nothing is offered to pick from and `Action` and `Tithe` stay dark. `Confirm`
lights instead, and pressing it accepts where that seat put its acolytes and hands the wheel to the
next seat, which is then holding its own five with the City's roads lit, again with nothing to
press first.

Confirming moves not one cube. Where a seat put its acolytes is where they stay, so what a reset
would need in order to take them back is dropped rather than played back, and all that comes off is
what the sow wrote about itself: the counter, the lit roads, the ring round the space it started
from, the route. That is why putting a turn down is written as its two halves — the cubes back where
the turn found them, and the marks off the board — with confirming taking only the second. The last
seat to confirm is no different from the others in this; the only thing different about it is what
comes after, which is that there is no seat to hand the wheel to, so the table goes back to the
first to begin and setup lets go of the board exactly as the four of them left it.

`Reset` deals the seat its five back and sets it going again the same way, and the seats that have
already confirmed keep what they placed — what a reset would need in order to take their acolytes
back was dropped when they confirmed, so there is nothing of theirs left to undo. It stays lit all
through a setup even with no sow standing to be put down, since with `Sow` dark it is the only way
back to the start of one: a compact row that redraws a City column mid-setup puts the flow down, and
`Reset` is what picks it back up. When the last seat confirms, the wheel is set, the table goes back
to the first seat, and `Setup` comes back up; the stage says which of the three it is on
`data-setup-mode` — `inactive`, `active`, `complete` — beside the seats that have finished on
`data-setup-completed-seats`. Five is what the engine's own setup deals, and the shape of the phase
is the engine's too, but nothing here is read from it: this is a board dealt to be clicked on, not a
position in a game.

A deal is the one thing on this page that a turn is not: it means to stick. So it sits with the
compact rows rather than with the turn flow, and it writes the City count those rows keep — the same
one `A->C` and `V->C` read and redraw from — instead of leaving the board saying one thing and the
rows another. It is made on the tally the table is playing and nowhere else: the wheel drew a tally
for every count and shows one at a time, and redrawing a City column writes a seat's column in all
of them at once, which would leave the other three saying a seat is in the City while their own duty
tiles still hold the cubes it sowed out of it. So a deal stands the columns it is dealing and writes
the count, and leaves the redrawing to the rows that own it. A change of table size deals again for
the same reason the count change puts a turn down: the tally now on the table is a different one,
drawn as the wheel opens rather than as a setup left it, and the seats it holds are a different
list.

The flow reads the tally the table is currently
playing and touches nothing the compact rows keep, which is why a count change simply puts a turn
down first — `applyPlayerCount` calls `resetTurnFlow` before anything else, as do `A->C` and
`V->C`, since both redraw a City column a turn may be holding cubes out of. `Action` and `Tithe` do
the one same thing — sending the cubes home is all either knows how to do — and `Confirm` knows only
how to hand a setup sow on. Resolving an action, taking a tithe, spending or collecting anything,
passing an ordinary turn on, and anything at all to do with `GameState` are still to come; this page
knows no rules. The wheel is seated in this page's own order — red,
yellow, blue, white — rather than the red-and-blue pair its standalone page seats, so every board
here agrees about who is playing; the standalone wheel is unchanged. These are local
debug UI controls only and do not change GameState or rules behavior. In 2P, the remaining red and yellow discs stay stacked (red over
yellow) but centred horizontally inside each track value; 3P/4P restore the 2x2. No board says who
starts.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_game_table.py
```

The generated overview below also produces it, and the index links it as `Generated game table
layout`.

## Generated overview

To build every generated view at once, plus an overview page linking them together:

```bash
python3 tools/ui_debug/generate_debug_overview.py
```

This writes:

```text
tools/ui_debug/generated/map.html
tools/ui_debug/generated/building_tiles.html
tools/ui_debug/generated/player_board.html
tools/ui_debug/generated/player_boards_v2.html
tools/ui_debug/generated/donated_building_tiles.html
tools/ui_debug/generated/ship_marker.html
tools/ui_debug/generated/piety_tracks.html
tools/ui_debug/generated/piety_tracks_v2.html
tools/ui_debug/generated/pilgrimage_sites.html
tools/ui_debug/generated/duty_wheel.html
tools/ui_debug/generated/alms_table.html
tools/ui_debug/generated/game_setup.html
tools/ui_debug/generated/game_table.html
tools/ui_debug/generated/debug_overview.html
```

Notes:

- `generated/*.html` files are ignored by git; they are local debug artifacts only.
- The generated links in `index.html` are dead until a generator has been run.
- Generated map rendering is visual/debug only.
- There is still no `GameState` integration.
- No gameplay or rules logic belongs in the UI debug layer.
