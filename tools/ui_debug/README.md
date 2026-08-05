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
v1 draws, and the first-player marker sits on the first/white board.
`prototype_sources/player_boards_v2.py.txt` is the reference-only copy of the script that drew it,
read for intent while reverse-engineering the layout, never imported or run.

`player_boards_v2_layout.json` and `render_player_boards_v2.py` are the structured renderer
extraction. The split between them is worth knowing: the JSON says what a board carries (the four
players and their colours, the palette, the Village/Abbey banners and how many starting workers
each shows, the six worker roles, the three resource readouts, which roles already hold workers),
and the module says where it all goes. The geometry stays in the module because it is derived
rather than chosen: one zigzag chain of six hexes, spread apart horizontally, gives the x-centres
that the banners, worker circles, and building slots all share, and the panel sizes itself around
the result. The four generated SVGs are byte-identical to the baseline's, which is what the parity
test pins.

Generate the output page with:

```bash
python3 tools/ui_debug/generate_player_boards_v2.py
```

The generated overview below also produces it. Both write `generated/player_boards_v2.html`, which
is not committed.

The first-player marker is renderer-driven, not `GameState`-driven:
`render_player_boards_v2_html(layout, first_player="player_two")` moves the card to the red board.
Nothing here decides who the first player actually is, and there are no start-player rules.

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
pitch, disc sizes and colours, and the star geometry are untouched, and the discs are deliberately
identical to the Alms Table's, which is why a step reads the same on both boards.

`piety_track_v2_layout.json` and `render_piety_track_v2.py` are the structured extraction, and they
follow v1's shape closely: the layout describes the panel once and lists the two variants,
`3_4_player` with two disc rows and `2_player` with one, and dropping a row still shortens the
panel by exactly that row. What v2 adds to the layout is the panel around the strip — side padding,
title band, corner radius — and the ornament geometry, so the hairline offset and the trefoil's
lobes and rule gap are all named values rather than constants buried in the drawing code.

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

Both variants render byte-for-byte identical to their SVG baselines once the `data-` hooks are
stripped, and a test holds them there. Those hooks — `data-component="piety-track-v2"`,
`data-piety-variant`, `data-piety-position`, `data-player`, `data-player-disc` — are the only
difference between the generated SVG and the baseline, and they exist for future UI/debug
interaction. The baselines carry none of them.

v2 does not replace the current piety track: `piety_track_layout.json`, `render_piety_track.py`,
and the generated `piety_tracks.html` are untouched and stay the live view, so the two are
generated side by side for now. There are no movement controls, no `game_setup.html` integration,
no `GameState` integration, and no gameplay rules here.

## Pilgrimage site renderer extraction

`prototypes/pilgrimage_sites.html` is the untouched visual baseline for the Pilgrimage Site tiles:
five orange tiles in one row, each with a piety-track star in its lower half and a P value and an S
value beside it. `prototype_sources/pilgrimage_sites.py.txt` is the reference-only copy of the
script that drew it. That script is read for intent; it is never imported or executed.

`pilgrimage_sites.json` and `render_pilgrimage_sites.py` are the structured renderer extraction.
The JSON holds only what the tiles print — the VP value on the star and the two values beside it —
while the geometry lives in the renderer, the same split the building tiles use. Nothing is
redrawn from scratch: the hex comes from `render_buildings.py` at the same 52 unit radius, so the
sites read as the same kind of piece, and the star comes from `render_donated_buildings.py`. The
rendered SVG is byte-identical to the baseline, and a test keeps it that way.

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
tally columns each duty shows: 4p is the view the prototype drew and the one the page opens on,
3p drops blue, and 2p drops yellow as well. The columns left standing stay centred on the duty, so
a shorter table narrows the tally around the middle of the space instead of leaving a gap on the
right, and the baseline under them shrinks to match. All of it is visual/debug only: the controls
move tokens, rewrite the eight titles, and swap tallies, and they do not mutate `GameState` or
implement any gameplay rule.

The controls work by ring position rather than tile identity, which is debug-only shorthand and
fine while Taxation is the one tile that never moves. The renderer draws every slot they can
switch on — a Merchant token on each position, every Tithe token on each position that has a
capsule, and a tally per player count on every duty — hidden until wanted, so a click flips
opacity instead of redrawing the board. Ask for the board without `interactive` and none of that
is emitted, leaving the four-player tally the prototype shows. `players_for_count()` says who is
at the table and `tally_columns()` says where their columns stand. The sample setups come from
`duty_setups()`: the first is the board the layout describes, the rest turn the movable tiles
around the ring, and a tile keeps its own Tithe token wherever it lands — which is why Taxation
stays put, being the one tile with no Tithe token and so the one position drawn without a capsule.
`next_merchant_position()` is the walk itself, one step clockwise along `clockwise_order`.

The cube counts on each duty come from `sample_cubes` in the layout, keyed by seat — the players
are `player_one` to `player_four`, each naming its cube colour, the same way
`player_boards_v2_layout.json` names them. They are sample debug state, not `GameState`, in the
same spirit as the v1 player board's mock state. Nothing here says what
any of it means: there is no Tithe token logic, no Taxation rule, no sowing or acolyte placement,
and no sow animation. Those belong in later PRs.

`render_duty_wheel_panel()` returns the controls and the board as one fragment, which is how the
generated setup view shows the wheel without copying any of this: it pairs that fragment with
`DUTY_WHEEL_CONTROL_STYLES` and `render_duty_wheel_controls_script()` and brings its own wrapper
and heading. Every hook the panel owns is prefixed — `duty-wheel-randomize`,
`duty-wheel-move-merchant`, `duty-wheel-readout`, `.duty-wheel-controls`, `.duty-wheel-counts` —
because the setup page already has a `.controls` row and `.readout` spans of its own, and the
script is one IIFE that reaches for those hooks and nothing else on the host page.

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
the mancala board's cube, which is why the Alms Table reads as part of the same set.

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
3-4 player piety track, generated building tiles, and generated pilgrimage sites on one page and
adds a little client-side interaction.

It uses the `three_four_player` variant only, because the page has controls for four players. The
2-player track is intentionally not shown here; `generate_piety_track.py` still produces both
variants for the standalone piety tracks page.

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
  tile's own wrapped label into it; it does not lay a second hex on top of the board. The fill goes
  in through `render_map_svg(layout, tile_overlay=...)`, which drops a fragment onto the tile fills
  before the map draws its rivers, hex edges, and labels, so a placed building keeps every line and
  label the map would have drawn there. `render_buildings.py` and the standalone building tiles
  page are untouched and still draw full tiles. An empty slot draws nothing. Which round a slot
  belongs to is not written on the map.
- A pilgrimage site slot is filled the same way: its hex takes the site orange and carries the
  site's star, VP value, and `P`/`S` values, scaled from `render_pilgrimage_sites.py` down to the
  map hex. The four site slots always take the first four sites in `pilgrimage_sites.json`, in
  file order. That is deterministic debug behaviour only; drawing sites at random is not
  implemented yet, and the fifth site is unused.
- Each player has one disc on the piety track. `+1 piety` and `-1 piety` move it one position and
  clamp at the ends of the track.
- The four discs are the movable copy of the track's own starting tokens, so their colours come
  from `piety_track_layout.json` (white, red, yellow, blue) rather than being restated here.

The generated setup view now includes a right-side Player Board v2 panel. The panel is local
UI/debug state only: it can move the first-player marker, move serfs from Village to Abbey, and
move acolytes between Abbey and role circles. This does not mutate `GameState` and does not
implement gameplay legality.

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
its own — and the slot's dashed outline is drawn last, so it stays the only boundary a slot has. `building_ownership_state`, `buy_building`, and
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
tools/ui_debug/generated/game_setup.html
tools/ui_debug/generated/debug_overview.html
```

Notes:

- `generated/*.html` files are ignored by git; they are local debug artifacts only.
- The generated links in `index.html` are dead until a generator has been run.
- Generated map rendering is visual/debug only.
- There is still no `GameState` integration.
- No gameplay or rules logic belongs in the UI debug layer.
