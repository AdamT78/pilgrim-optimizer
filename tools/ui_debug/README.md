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

## Game setup debug view

`generated/game_setup.html` is the first composed view: it has no prototype baseline of its own
and no renderer module of its own. `generate_game_setup.py` puts the generated map and the
generated 3-4 player piety track on one page and adds a little client-side interaction.

It uses the `three_four_player` variant only, because the page has controls for four players. The
2-player track is intentionally not shown here; `generate_piety_track.py` still produces both
variants for the standalone piety tracks page.

What moves, and what it means:

- The ship rides the edge hexes clockwise from `J3`, sitting in the upper part of a tile the way
  the ship marker tiles draw it. It hops over the four special corner hexes `F1`, `B6`, `G11`, and
  `L6`, which leaves 26 stops — the engine's round track length. `SHIP_HEX_PATH` lists those stops
  by map label and they are resolved through the map's own label table, so the route cannot drift
  away from the board. When the ship actually moves is still a rules question this page does not
  answer.
- Each player has one disc on the piety track. `+1 piety` and `-1 piety` move it one position and
  clamp at the ends of the track.
- The four discs are the movable copy of the track's own starting tokens, so their colours come
  from `piety_track_layout.json` (white, red, yellow, blue) rather than being restated here.

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
