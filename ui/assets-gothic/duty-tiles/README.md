# Duty tile art

```
V/                 the finished square tiles of version V   NN_slug_V.webp
sources/V/         what they were made from, suffixed       NN_slug_V_pair.webp
                                                            NN_slug_V_left.webp / _right.webp
joins.json         where each tile's two scenes meet, written by check_tile.py
```

`V` is a single letter and nothing enumerates the letters that exist: the patterns take `[A-Z]`,
the picker discovers versions by looking, and `gen_duty_grid.VERSION` says which one the board
draws — **C** today, after A engraved and B grim dark. A new set needs a folder and a name, not a
code change. That was not true until recently, and the cost of it not being true was invisible
rather than loud: a set the patterns did not recognise rendered as nine flat colours saying "no
art", which is exactly what an unstarted set looks like.

The picker matches `NN_slug_V.ext` exactly and searches recursively, so anything with a suffix —
`_pair`, `_left`, `_right` — is skipped automatically. There is no include list to keep in step:
the name decides. A tile with no file draws its flat region colour and says "no art".

Finished tiles are stored WebP lossless and the source pairs at q92. The tile is what gets drawn
and the component re-encodes it down to 448 px anyway; the pair is kept only so a merge can one
day be compared against what it was merged from, which does not need to be lossless.

## After generating a tile

```
python3 ui/render/check_tile.py ui/assets-gothic/duty-tiles/C/*.webp \
        --version C --joins-out ui/assets-gothic/duty-tiles/joins.json
python3 ui/render/gen_picker_grid.py --tiles ui/assets-gothic/duty-tiles --open
python3 ui/render/gen_game_view.py --duty-version C --open
```

The picker reads `joins.json` from this directory without being told, and opens on whichever
version the board is drawing. `--joins-out` writes the measured constant 0.5 for every two-action
tile: the pair is generated as two equal halves and the merge keeps them, so there is nothing to
detect. It used to write a detector's output instead, and the detector was wrong on every tile
where ground truth existed — see `join_fraction`'s docstring, which is kept for that record.

Keep the sources. They cost nothing and one matched set — two `_left`/`_right` images plus the
`_pair` or merged tile made from them — would settle whether a seam can be found by comparing a
merge against its source, which is still open.
