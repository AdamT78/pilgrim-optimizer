# Duty tile art

```
A/                 the finished square tiles, version A   NN_slug_A.png
B/                 version B
sources/A|B/       what they were made from, suffixed     NN_slug_A_pair.png
                                                          NN_slug_A_left.png / _right.png
joins.json         where each tile's two scenes meet, written by check_tile.py
```

The picker matches `NN_slug_V.ext` exactly and searches recursively, so anything with a suffix —
`_pair`, `_left`, `_right` — is skipped automatically. There is no include list to keep in step:
the name decides. A tile with no file draws its flat region colour and says "no art".

## After generating a tile

```
python3 ui/render/check_tile.py ui/assets-gothic/duty-tiles/A/*.png \
        --version A --joins-out ui/assets-gothic/duty-tiles/joins.json
python3 ui/render/gen_picker_grid.py --tiles ui/assets-gothic/duty-tiles --open
```

`check_tile` measures the join; the picker reads `joins.json` from this directory without being
told. That is deliberate — the highlight gradient is centred on the measured join rather than the
midline, and a number copied by hand is a number that goes stale.

Keep the sources. They cost nothing and one matched set — two `_left`/`_right` images plus the
`_pair` or merged tile made from them — would settle whether a seam can be found by comparing a
merge against its source, which is still open.
