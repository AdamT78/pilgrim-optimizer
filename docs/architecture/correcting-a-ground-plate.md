# Correcting a ground plate

This is the companion to [`ring-ratio.md`](ring-ratio.md), which explains how a camera angle is
*measured*. This one is about what to do when the measurement comes back wrong.

## The one sentence

A flat plate seen from θ above the horizon projects sin(θ) tall, so moving a flat plate from
one camera to another is a vertical scale and nothing else. `tools/ui_debug/ground_tile_angle.py`
does that scale.

## Why this exists

Until 2026-09-26 the only answer to a plate at the wrong camera was another batch. The generator
picks a camera per session and holds it — within a batch the readings are tight, between batches
they move three degrees on briefs asking for the same number — so getting a usable plate has
cost about one in five generations all along.

Scaling one is not a shortcut past that. It is the right operation for a plate whose *art* is
what you wanted and whose *camera* is not, which is a case the batch-again loop handles badly:
you throw away art you liked to buy a number you could have computed.

## What it will not do

**It is exact only for geometry lying on the ground plane.** Anything with height — a plinth, a
kerb stone seen from the side, a wall — has a visible face whose height does not foreshorten the
same way. Squash the plate and those faces end up wrong while the outline reads right, and the
number will not tell you. `mosaic_compass` took a 7% squash with no visible damage; there is no
measured figure for where that stops being true, so the rule is to look at the check image
rather than trust a threshold nobody has established.

**It cannot recover a camera from a ragged outline.** Every instrument here assumes the plate's
un-foreshortened shape is a circle, which is the same limitation `ring-ratio.md` sets out under
*What can carry a camera, and what cannot*. On `mosaic_compass` the three readings were:

| instrument | reading |
|---|---|
| ink bounding box | 32.45° |
| `ground_ellipse` (the `repo` reading) | 34.13° |
| `cv2.fitEllipse` over the silhouette | 34.06° |

A 1.60° spread against a window 0.96° wide. That is not three bugs; it is three answers to a
question the picture does not contain. The tool prints all of them and the spread, because the
number it then uses is a **choice** and ought to look like one.

## Why `repo` is the default

Not because it is true — because it is repeatable, and a set measured the same way agrees with
itself even where no single absolute reading can be defended. Across the six plates on file:

| instrument | spread across the set |
|---|---|
| `ground_ellipse` | 1.36° |
| ink bounding box | 3.55° |

The fit is 2.6× the more consistent instrument on real art, and it is what every filed plate was
already measured with. Switching instruments between plates is the one thing that would undo the
consistency the default is bought with, so `--method` exists for diagnosis rather than for taste.

`--method contour` is diagnostic only and refuses outright when the fitted ellipse sits more than
2° off level. Not because a tilt spoils the *ratio* — it does not; on a true ellipse rendered at
34° the axis ratio returns 33.92° at every tilt from 0 to 10, while the vertical-extent reading
that looks more physical drifts to 35.19° at 10°. A tilt spoils the *correction*: a vertical
scale is the right projection only for a level ellipse, and a plate rotated in the image plane
needs straightening rather than squashing.

## The one piece of evidence that is not circular

Everything above measures a plate against an instrument and then scales the plate until the
instrument is satisfied. That cannot fail, which means it cannot confirm anything either.

The painted sculpts' base discs can. They are clean circles, so `ground_ellipse` reads them
*exactly* rather than approximately, and they come from art that shares nothing with these
plates:

| sculpt | base disc |
|---|---|
| `player_1_book_and_palm_a` | 31.26° |
| `player_2_v2_a` | 31.44° |
| `player_2_v1_a` | 31.47° |
| `player_1_quarterstaff_a` | 31.56° |
| `player_2_v3_a` | 31.73° |
| `player_1_reading_a` | 31.80° |

They sit on the ground target, arrived at separately. Correcting `mosaic_compass` moved it from
2.26° of disagreement with the figure that stands on it to **0.006°**. That is the only
corroboration in this area that was not arranged, and it is the reason to believe the default.

It also settled the instrument choice after the fact. The bounding box would have called the
plate 32.45° and left a 0.9° disagreement with the figures; the ring that arrived on the tile
would have left 2.76°.

## A corrected plate is not evidence

This is the thing to hold on to, and `ring-ratio.md` predicted it before there was a tool:

> if every plate ends up huddled in a corner of its own window, the window has stopped
> describing the set and is no longer measuring anything.

A plate that arrived inside the window tells you something about where the generator puts a
camera. A plate that was scaled until it was inside tells you only that somebody scaled it. Once
filed the two are indistinguishable, and the window's own numbers were derived from plates that
arrived where they arrived.

So a corrected plate carries a `correction` block in `duty_grounds.json` — where it came from,
what scale was applied, which instrument said so, and why — and
`test_a_corrected_plate_can_be_re_derived_from_its_source` asserts four things that can each rot
separately: the block names a source, the source is on file, correcting that source reproduces
the filed plate **byte for byte**, and the filed plate reads what the block says.

The byte-for-byte step is the one that earns its keep. Anything looser lets a plate be retouched
by hand afterwards and still claim to be a pure vertical scale of its source, which is exactly
what `attribution.json` says it is.

The same test also refuses to let corrected plates become a majority of the set. That is not a
style rule — past that point the window describes the scaling rather than the generator, and the
right response is to decide whether the generator has moved or the target has.

## Four things that cost a measurement to learn

**Crop after correcting, never before.** Cropping first shifts the resampler's sub-pixel phase,
and `ground_ellipse` reading a ragged outline is sensitive to it: the same plate came out 0.10°
different. Correct on the generation's own canvas, then crop — which is why
`mosaic_compass_c01.png` is filed uncropped.

**The instrument has a floor.** An identity resample — scaling by exactly ×1.000, which changes
nothing — re-reads 0.026° from where it started. Nothing here is repeatable past that, which is
well inside the 0.48° tolerance but worth knowing before chasing a third decimal.

**The canvas has to grow.** Scaling into the same one silently cuts the art off whenever the
scale exceeds 1. Tested with the ink pushed against the top edge, a ×1.41 stretch kept 1031 rows
where 1207 were wanted and lost the difference with nothing said. Four rows of margin rather than
two, so the outermost row does not land on the edge where a later crop has to guess about it.

**The check ring is drawn as an annulus, not a stroke.** PIL's `ellipse(..., width=w)` strokes
*inward* from the box, so the drawn centreline comes out `w` smaller on both axes — and
subtracting the same `w` from a major and a minor lowers the ratio. The first version asked for
31.545° and drew 31.294°: 0.251° low, over half the tolerance, in the one thing here meant to be
trustworthy. This is the same bias `ring_ellipse` exists to avoid on the measuring side, made
again on the drawing side. It now draws 31.531°, the residual being one rounded pixel on a 672 px
axis.

## The ring that was rejected

`mosaic_compass` arrived with a measuring ring on it. The ring fits 37.19° where the tile's own
outline reads 34.13° — three degrees apart, against a tolerance of 0.48 — and it was not used.

The reason is measurable rather than a preference. Correcting by the ring leaves the plate
reading 28.80°, which is 2.76° from the sculpt bases; correcting by the outline leaves it 0.006°
away. The ring was honest about its own geometry and wrong about the tile it encircled, which is
the failure already on record from the first ringed cobbles batch, where five clean closed rings
sat inside a one-degree window while four of the five tiles inside them were up to 6.6° from
their own ring.

The ringed original is filed at `grounds/candidates/mosaic_compass_ringed.png` anyway — so the
claim can be re-checked rather than taken on trust, and because `without_ring()` on it yields
`mosaic_compass_c01.png`, which makes the whole chain re-derivable from the generation itself.

One incidental finding from that comparison, worth recording because it cuts the other way from
what you would expect: an outside script that erased the ring's full geometric annulus rather
than keying its colour destroyed 3,814 pixels of real mosaic at the left and right extremes,
where the ring passes closest to the tile. `sculpt_metrics.without_ring()` keeps them and leaves
exactly as little keyed green behind — zero, in both cases.

## Running it

```
python3 tools/ui_debug/ground_tile_angle.py <tile.png> --check
python3 tools/ui_debug/ground_tile_angle.py <tile.png> --crop -o grounds/<name>.png --check
python3 tools/ui_debug/ground_tile_angle.py <tile.png> --method bbox
python3 tools/ui_debug/ground_tile_angle.py <tile.png> --angle 34.13    # assert it yourself
```

`--check` writes the result with the target ellipse over it. **Look at it.** Re-measuring the
result proves nothing — scale by target ÷ current and the reading comes back as the target
whatever `current` was, including badly wrong. Whether the plate's front rim sits on that line
is a different question, and the only one here the arithmetic cannot answer for itself.

`readings()` and `correct_to_target()` are importable and touch no files, if you want the
measurement or the scale without the shell around them.

## Where things live

| | |
|---|---|
| the correction | `tools/ui_debug/ground_tile_angle.py` |
| the measurement it uses | `tools/ui_debug/sculpt_metrics.py` — `ground_ellipse` |
| the target | `tools/ui_debug/generate_asset_check.py` — `GROUND_TARGET_DEGREES`, read at run time rather than restated |
| what a corrected plate must declare | `duty_grounds.json` — `grounds.<name>.correction` |
| the guard | `test_a_corrected_plate_can_be_re_derived_from_its_source` |
| the worked example | `mosaic_compass`, and its two files in `grounds/candidates/` |
| how a camera is measured at all | [`ring-ratio.md`](ring-ratio.md) |
