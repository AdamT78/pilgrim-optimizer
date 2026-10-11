# The ribbon's backdrop

The ground the eight duty tiles and the status line stand on. The tiles are glass over it —
`--tile-alpha`, 55% — and the selected tile is not, which is how it reads as solid against seven
panes.

`ribbon_backdrop_v07.webp` · 2170 × 363 · 17 KB · **shipped**, see `../attribution.json`  
`ribbon_backdrop_v06.webp` · 2290 × 383 · 158 KB · superseded, kept  
`ribbon_backdrop_v05.webp` · 2290 × 409 · 156 KB · superseded, kept  
`ribbon_backdrop_v04.webp` · 2197 × 590 · 145 KB · superseded, kept  
`ribbon_backdrop_v03.webp` · 1344 × 361 · 99 KB · superseded, kept  
`ribbon_backdrop_v02.webp` · 2172 × 495 · 87 KB · superseded, kept

**The prompt, the band targets and the script that scores a generation before it is cut now live
in `PROMPT.md` beside this file.** What is below is the history of how the rect got its shape;
what is in there is how to fill it.

## v07: no motif, which is why it finally fits

Six backdrops were pictures, and every one was a negotiation between what the generator wanted to
compose and what the board needs behind it. The board needs two things that pull against each
other — the status line is black type and wants a light band, the tiles are 55% glass over cream
emblems and want a dark one — and **a painting has one sky**. v07 is a field of mist and nothing
else: no horizon, no ground, no objects, a smooth vertical gradient. With nothing to compose,
every band can simply be put where it belongs.

Measured on the crop, it is the first backdrop to read **0.00% painted matter** both above the
tiles' line and behind each of the eight tiles, and the first to clear 4.5:1 on both overlaid
objects at once:

| | worst tile | status line | tile band | emblem on tile |
|---|---|---|---|---|
| v03 | — | 145 → 6.4:1 | 81 | 7.58:1 |
| Misty Monastic (rejected) | 1.4% | 209 | 187 | **4.23:1** ✗ |
| v04 | 5.6% | 183 | 124 | 6.67:1 |
| v06 (shipped, non-conforming) | 36.0% | **3.27:1** ✗ | — | — |
| **v07** | **0.00%** | **6.69:1** | **105** | **5.57:1** worst, 7.13 mean |

**And the crop was searched rather than taken from the bottom.** A landscape has to be cut at one
window or its composition breaks; mist has no composition, so all 363 candidate windows of this
master were scored against the band targets and the best chosen. That matters more than it
sounds: a bottom-anchored cut of this same file gives a text band of 107 and a tile band of 76,
too dark at both ends — and bottom-anchoring is exactly how v05 and v06 went wrong, because the
shorter the band gets, the more of the pale top a bottom crop throws away.

It is also a tenth the weight of what it replaces, 17 KB against 158, because flat fog compresses
in a way a painted valley does not. The board inlines every picture as a `data:` URI, so that is
page-open time.

**What it gives up is the valley.** There is no road, no pilgrims and no shrines behind the
tiles any more — the motif history below is the record of four attempts to keep one and the
diagnosis of why they kept failing. If the picture is wanted back, that is the reading, not a
fresh start.

## v04: generated to the constraints rather than cropped to fit

The first four backdrops were pictures that existed and were then made to fit. v04 is the first
one generated against the board's own numbers, and it took four tries to get a prompt that
holds — the history is in `PROMPT.md`, because every failure taught something reusable.

Two findings worth having here as well:

**The two things printed over this picture want opposite tones.** The black status line needs a
light band (≥115) and the translucent tiles need a dark one (110–140). A flat mist cannot serve
both: one candidate was pale all the way down at 187 behind the tiles and put the cream emblems
at 4.21:1 against their own tile, under the 4.5 they need. So the sky is a deliberate vertical
gradient — v04 runs 226 at the top to 90 at the horizon, reading 183 in the text band and 124 in
the tile band.

**Asking for an entrance is asking for a building.** The left scene broke the height rule four
times running — roof, bare wall, cellar barrow, gate — because every version was a hole in a
building and the model kept supplying the building. It only settled when the scene stopped being
architecture at all and became an open-air dole: a trestle, a cauldron, a queue. The centre and
right scenes never broke the rule once, for the same reason.

**Density is 1.63×**, back up from v03's 1.00×.

## v03: the picture reaches the top of the canvas

The rect changed shape before the picture did. `BACKDROP` used to start at `RIBBON_Y` — the top of
the duty tiles — which left 55 px of black above it with the status line floating in the middle of
that: a caption on a black strip above a picture, rather than a caption on the picture. It starts
at **y = 0** now, so the valley is the board's own ground rather than a panel inside it, and the
rect went from 1344 × 306 to **1344 × 361**.

Two things followed from that, and both are the kind that would have shipped looking like
something else.

**The status line was painted over.** Everything on this board is `#board > *` with no z-index, so
append order is stack order — and `draw()` called `drawStatus()` before `drawBackdrop()`. That was
invisible for as long as the two rects did not overlap. The moment the picture reached y 0 the
caption simply was not there, with nothing in the console to say why. The valley is drawn first
now, and the guard says *first* rather than "before the tiles", which is what it used to say and
what the status line satisfied by standing in front of it.

**The line sits on sky at 2.2:1.** Cream type at luminance 232 on a flat mist at 144, against the
4.5 ordinary text is held to. It is answered with a **shadow on the glyphs, not a plate behind
them** — a plate is a dark strip across the top of the picture, which is the thing extending the
picture removed, put back in the one place it was removed from.

## How v03 was cut

The master is **1400 × 420**, supplied at the canvas's own width.

```
crop box     (28, 59) to (1372, 420)   ->   1344 x 361   (exactly the rect)
dropped      28 each side and 59 off the TOP, which was sky
anchored     to the bottom edge, as v02 was, and for the same reason
```

The 28 taken off each side is precisely the board's left and right margin, so the picture lands
where it would if the whole 1400 were laid across the canvas and clipped to the working area.
Nothing is resampled and nothing is stretched: the crop is 1:1 with the rect, where v02 was
aspect-true to 0.1%.

**Density is 1.0×, down from v02's 1.6×.** 1344 px of picture in a 1344 px slot is exact on a
normal display and soft on a retina one, where 2688 would be ideal. That is the one thing v03 is
worse at, and it is fixed by regenerating the master at 2800 × 840 and cutting it the same way.

## The number that used to matter, and what replaced it

**The painted ground begins 55.4% down the picture. The road strip begins 71.2% down the rect.**
They no longer meet, and that is a decision rather than a defect.

### And the rule for finding it changed, because the old one was measuring noise

It was *the sharpest darkening in the lower half of the frame*, which works on a frame that has a
**horizon**. v02 had one and the rule found it at 0.871. v03 has none: it falls continuously from
mist at luminance 146 to mud at 43 with no edge anywhere, so the sharpest darkening in its lower
half is a fifteen-row band of wet earth at **0.958** — a number saying the ground begins almost at
the bottom of a frame that is ground for most of its height.

Both are measured the same way now: **the first row from which the picture is within a tenth of
its own foreground darkness and never returns above it.** v02 gives 0.921, v03 gives **0.554** —
so v03 is the first backdrop with the third of its height below the horizon that this file has
been asking a replacement for.

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
