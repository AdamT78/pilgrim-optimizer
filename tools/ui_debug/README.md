# Pilgrim UI Debug Prototypes

These files are visual prototypes/baselines only.

They are not connected to `GameState`, do not implement rules, and are not the final UI.
They should be used as visual reference before future renderer extraction.

Future work can extract structured geometry/layout data one prototype at a time while preserving visual parity.

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
