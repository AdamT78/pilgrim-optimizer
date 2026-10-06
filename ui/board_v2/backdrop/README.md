# The ribbon's backdrop

One picture, drawn behind the eight duty tiles and the road strip together: a valley the tiles
stand in front of, with the road the Merchant travels running along the foot of it. The tiles are
glass over it — `--tile-alpha`, 55% — and the selected tile is not, which is how it reads as solid
against seven panes.

`ribbon_backdrop_v02.webp` · 2172 × 495 · 87 KB · CC-free, see `../attribution.json`

## The number that used to matter, and what replaced it

**The painted ground begins 87.1% down the picture. The road strip begins 66.0% down the rect.**
They no longer meet, and that is a decision rather than a defect.

The first cut was anchored to make them meet to within a third of a pixel, and `check()` held them
to each other. Then the confirm row came off the board and the road strip took its height: 64 tall
became 104, and `BACKDROP` went from 1344 × 242 to 1344 × 306. A rect with a 104-tall strip at its
foot wants **34% of the picture below the horizon**. The master has **8.8%** — 64 rows under its
own ground line, out of 724.

So no crop of this master can satisfy the old rule. What a crop *can* do is satisfy it by being
stretched, and that is what the board did for one build: the aspect-true crop is 4.39:1 against the
rect's 4.39, and forcing the old 5.55:1 crop into the new rect scaled the whole valley vertically
by 26%. Taller chapel, taller tower, taller everybody.

The rule went instead. **The strip is a place, not a surface** — it is where the Merchant is told to
walk, and the picture behind him is scenery. The horizon now falls *inside* the strip, 64 px down
its 104, so he walks across the painted ground rather than along its top edge. `check()` no longer
compares the two; `BACKDROP_GROUND` is still published so a replacement has a number to be read
against by eye.

## How this one was cut

The master is **2172 × 724** at 3:1. The board's `BACKDROP` rect is **1344 × 306** at 4.392:1.

```
crop box     (0, 229) to (2172, 724)   ->   2172 x 495   (4.3879:1)
anchored     to the BOTTOM edge
dropped      the upper sky, which was the emptiest part of the frame
kept         the hills, the chapel, the scaffolded tower, the bridge, the spire, the lanterns
ground line  master row 660 -> 87.1% down the crop
```

Bottom-anchored because the foreground is the scarce thing: every row dropped from the top is sky,
and every row that would be dropped from the bottom is the only ground there is. Aspect-true to
within 0.1%, so the board's `background-size:100% 100%` resamples it by a tenth of a pixel and
distorts nothing. The ground line was found by row brightness rather than by eye — the sharpest
darkening in the lower half of the frame.

Re-encoded WebP q86 method 6: the PNG was 1.7 MB and this is 87 KB. The board inlines every
picture as a `data:` URI, so that saving is how quickly the page opens.

## Replacing it

Add `ribbon_backdrop_v03.webp` beside this one rather than overwriting — the generator takes the
highest version, so the old one stays available and the change is a file rather than a loss.

**The suffix has to be one the generator reads.** `imageSuffixes` in `../attribution.json` declares
`.png` and `.webp` only, and the provenance walk is by suffix too. A `.jpg` dropped in here is
skipped by both, silently, and the build's own notes are the only place it shows.

Three things a replacement should get right:

**The ratio is 4.392:1** (1344 × 306, or 2688 × 612 at 2×). Image models will not generate that
directly — most stop around 21:9 — so expect to crop a wider-than-tall frame, which is what
happened here.

**A third of the height should be below the horizon.** That is what this master could not give, and
it is the one thing worth asking the generator for explicitly: a low horizon with real foreground
under it, rather than a skyline. Get it and the strip can go back to being a surface.

**The top 242 px sits behind the tiles** and the bottom 104 px is the strip. The 16 px between them
is the only band seen unobstructed. Detail in the top half is seen through glass, so it should read
as atmosphere; detail at the foot is seen plainly.

## Density

2172 px of picture covers a 1344 px slot: 1.6×, which is crisp on a normal display and slightly
soft on a retina one, where 2688 would be ideal. Upscaling the file gains nothing real, so it is
left at its native width. On a misty valley seen through glass the softness is close to invisible,
and a regenerated master at a wider size would fix it properly — and is the same regeneration the
horizon wants.
