# Pilgrim UI Debug Prototypes

These files are visual prototypes/baselines only.

They are not connected to `GameState`, do not implement rules, and are not the final UI.
They should be used as visual reference before future renderer extraction.

Future work can extract structured geometry/layout data one prototype at a time while preserving visual parity.

## Source of truth

Each kind of file here has one job, and mixing them up is how this layer starts to drift:

- **Prototype HTML** (`prototypes/*.html`) are visual baselines. Once a prototype lands it is
  not edited; renderers are judged against it.
- **Layout/catalog JSON** (`*_layout.json`, `*_catalog.json`) are structured renderer inputs.
  They describe what to draw, reverse-engineered from the baseline.
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

## Baseline-only prototypes

These prototypes are visual baselines with no renderer extraction yet:

- `prototypes/donated_building_tiles.html`: flipped/donated building tile markers with star VP
  values, one hex per building colour.
- `prototypes/ship_marker.html`: ship marker / ship-on-tile visual examples, one per building
  colour.

For both of them there is currently:

- no renderer extraction
- no generated output
- no `GameState` integration
- no rules logic

`index.html` links to them as baselines only. Renderer extraction for these should happen in
separate PRs, following the component extraction checklist above.

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
tools/ui_debug/generated/debug_overview.html
```

Notes:

- `generated/*.html` files are ignored by git; they are local debug artifacts only.
- The generated links in `index.html` are dead until a generator has been run.
- Generated map rendering is visual/debug only.
- There is still no `GameState` integration.
- No gameplay or rules logic belongs in the UI debug layer.
