# The ring ratio: how a camera angle is measured

![The ring ratio explained](ring-ratio.png)

Redraw the picture with `python3 tools/ui_debug/generate_ring_ratio_explainer.py`. It reads
the constants and the art at run time rather than having numbers painted into it, so if the
set of plates moves, the picture moves with it.

## The one sentence

A circle lying flat on the ground, seen from an angle θ above the horizon, projects as an
ellipse whose height is `sin(θ)` times its width. That fraction — height divided by width —
is the **ring ratio**, and it is the only thing in this project that measures a camera.

Everything else follows. 0.500 is 30°, 0.523 is 31.545°, 0.530 is 32°, 1.000 is straight
down. Nothing about the subject changes the arithmetic: a figurine's plinth, a paved floor
and a drawn guide ring are all circles on the same ground, so all three give the same answer
when the camera is the same. That is the whole reason the number is worth having — it is
what lets a ground plate and a sculpt be compared at all, when the two were generated
separately, months apart, and have no other property in common.

## Why measure it

A duty tile is figures standing on a plate. If the plate was drawn from a camera 8° higher
than the figures were, the figures do not look like they are standing on it — they look
pasted onto it, and nobody can say why. The failure is real and hard to name by eye, which
is exactly the kind of thing worth turning into a number.

So both halves are measured the same way and held to a window. `TARGET_DEGREES` (32.0,
tolerance 2.5) governs sculpts; `GROUND_TARGET_DEGREES` (31.545, tolerance 0.48) governs
plates. Both live in `tools/ui_debug/generate_asset_check.py` and both are shown on the
asset-check page, where they are editable boxes rather than constants so a judgement can be
re-run against a different window without editing code.

The two numbers are four tenths of a degree apart. That gap is not slack — it is the
agreement, measured rather than asserted, and a test fails if it opens past a degree.

## Where the plate numbers come from

The window is **locked**: target 31.545°, tolerance 0.48°, so 31.065 to 32.025. They are
constants, not a formula over the folder, and a plate outside them fails rather than
widening them.

They were derived once, on 2026-09-23, from the six plates then on file — every one of which
had been looked at under figures and kept, so the set was the best description available of
what "right" meant:

| plate | degrees | from the mean | |
|---|---|---|---|
| `slate_irregular` | 31.07 | −0.475 | |
| `planks_rough` | 31.14 | −0.405 | recorded from its ring; its outline reads 30.66 |
| `flagstones_grey` | 31.52 | −0.025 | |
| `cobbles_oval` | 31.63 | +0.085 | |
| `limestone_irregular` | 31.89 | +0.345 | |
| `flagstones_slab` | 32.02 | +0.475 | |

Mean 31.545, largest deviation 0.475 — as ratios, 0.5160 to 0.5303. The tolerance is that
deviation **rounded up**, to 0.48.

**Corrected 2026-09-24, and the correction is the useful part.** The target was 31.55 and
this table read −0.47 for slate and +0.48 for slab, which has the two transposed: the mean is
31.545 exactly and the two extreme plates sit 0.475 either side of it, equidistant. Rounding
the target to two decimals moved it five thousandths toward slab, which put `slate_irregular`
at exactly 0.48 from target against a tolerance of exactly 0.48. Equal decimals are not equal
in binary — `abs(31.55 - 31.07)` evaluates to 0.48000000000000043 against a literal 0.48 of
0.47999999999999998 — so the plate carrying the `construct` duty was judged `check` on the
asset-check page and failed `test_a_plate_is_held_tighter_than_a_sculpt`, entirely on
representation error. Note what the fix is *not*: setting the tolerance to the exact largest
deviation of 0.475 would put **both** extreme plates on the boundary instead of one. Rounding
the tolerance up is what buys margin, and there is now five thousandths of a degree of it.

That replaced a target of 32.0 with a tolerance of 1.0, both of which had been picked rather
than measured, and which the set never centred on: five of its six sat below 32. The window
is about half as wide, deliberately. Against the batch of five that produced the current
cobbles plate it admits exactly the one that was chosen by eye: 31.6 passes, and 32.2, 32.9,
34.4 and 35.9 do not. One usable plate in five is what this work has actually cost all along.

### Why the rule that produced the numbers is not the rule that keeps them

For a few hours the window *was* the formula — recomputed from the folder, with a test
asserting the constants matched. That makes the specification a function of the thing it
judges, and it has no fixed point. Every plate accepted rewrites the bar that judges the next.

Simulated before locking it. File eight plates each landing exactly on the current ceiling —
the worst thing that still passes, every step legitimate, every suite green — and the target
moves +0.54° while the ceiling moves +1.09°.

The realistic path is worse, because it is invisible. We do not file edge cases; we file the
best of each batch. Simulating that over twelve plates, the target slides **down** from 31.55
to 31.43 while the ceiling stays pinned at 32.02. The reason is an asymmetry nobody would
predict: `flagstones_slab` at 32.02 is the highest plate on file and anchors the top of the
window, so everything new lands below the mean, drags the mean down, and widens the tolerance
downward. The set drifts away from the sculpts one plate at a time, and every individual step
looks like tightening the standard.

The tolerance was also decided by exactly one plate — whichever sat furthest out, `slab`
today, `slate` before the plank correction. A statistic one member controls is fragile in both
directions: add a plate 0.48° past the ceiling and it jumps 72%, where two standard deviations
would move 31%. And redrawing the current extreme closer in silently tightens the bar on
everything else.

So the numbers stay where the measurement put them. `test_the_plate_window_is_locked_and_every_plate_is_inside_it`
asserts both literals and then checks every filed plate is inside the window. Changing the
window is now a deliberate edit that shows up in review; filing a plate outside it fails, which
is the moment to decide whether the plate is wrong or the family has genuinely moved.

It keeps one check in the other direction: if every plate ends up huddled in a corner of its
own window, the window has stopped describing the set and is no longer measuring anything.

Since 2026-09-26 a plate can also be **corrected** into the window rather than generated inside
it — scaled vertically from the camera it arrived at to the target. That makes the check above
load-bearing rather than hypothetical, because a corrected plate satisfies the window by
construction and says nothing about where the generator puts a camera. A corrected plate
therefore declares itself in `duty_grounds.json` and its derivation is asserted, and the same
test refuses to let corrections become a majority of the set. See
[`correcting-a-ground-plate.md`](correcting-a-ground-plate.md).

## The measuring ring

Most ground plates are round with a rim, and a round plate's own outline is an ellipse you
can measure directly. A **ragged** plate is not: a patch of cobbles that simply stops in
packed earth has no ellipse to fit, and fitting one anyway returns a number that looks
plausible and means nothing.

So the briefs ask the generator to draw a guide: a single closed ellipse around the whole
tile, in flat spring green, representing a perfect circle lying on the same ground. It is a
jig, not artwork. `sculpt_metrics.py` measures it, then removes it, and what is filed is the
tile alone.

Four details of the implementation are not obvious and each cost a round to learn.

**Spring green, RGB 0 255 128, because it has to sit outside the palette.** Magenta was the
obvious choice and it is wrong: measured across all committed PNGs in `ui/assets-gothic/`,
magenta comes within 34 of `stones_plum.png`, plum being a purple. Spring green's closest
approach is 182, in `stones_sage.png`. A key that lives inside the palette eats the art.

**The ring is fitted, not bounded — and getting this wrong cost more than the whole
tolerance.** `ground_ellipse` looks for the widest row, so a hollow ellipse handed over
as-is measures 10° when it was drawn at 32. The first fix was to fill the hole and bound the
result, and that is subtly wrong: filling an annulus recovers its **outer** edge, and an
outer edge is a fatter ellipse than the centreline it was drawn around, because adding
half-stroke `t` to both semi-axes gives `(b+t)/(a+t)`, which exceeds `b/a` whenever `b < a`.
Every reading was therefore biased toward a steeper camera, by an amount that grows with the
stroke — and the briefs ask for a stroke of about 2% of the tile's width.

Measured against rings whose centreline is known exactly, the bounding method erred by +0.27
to +0.48° at a 9 px half-stroke and by **+0.70°** at 18 px. A plate is held to 0.48°, so the
instrument's bias was larger than the thing it was measuring. `ring_ellipse` now fits a conic
to the ring's pixels by least squares — plain numpy SVD, since OpenCV is not a dependency —
which is exact to 0.01° anywhere in the 28–34° band this board works in. It degrades to 0.22°
only at 40° with a fat stroke, where a constant-width band is least like an ellipse, and no
plate will ever sit there.

The fill is still used, for what it is actually good at: deciding whether the loop is closed.

**The ring is filed now, not discarded — for a plate that records a camera.** The ring is a
jig, and for a plate whose own outline is an ellipse there is nothing to keep once it has been
measured. That reasoning was applied to `planks_rough` too, and it was wrong there: its
recorded 31.14 *is* the ring's reading, so discarding the ring discarded the measurement and
left a number nothing in the repository could check. It was recovered on 2026-09-24 from the
session that generated it, three weeks later and after the file had been cleared from disk, and
is filed at `grounds/candidates/planks_rough_ringed.png` — in `candidates/` because the ground
panel globs `grounds/*.png` and would otherwise report a ring-bearing image as a seventh plate.

The identity is proven rather than asserted: strip that file's ring, crop to ink, and the
result is byte-for-byte identical to the committed `grounds/planks_rough.png`. Nine other
images from the same batch were checked as controls — one matched on size and differed in
content, fitting 33.49 rather than 31.14, which is exactly the near-miss the check exists for.

So a `camera` block now carries a `ring_source`, and
`test_a_recorded_camera_keeps_the_ring_it_was_read_from` asserts four things that can each rot
separately: the block names a source, the source is on file, the ring still fits the recorded
angle to 0.01°, and the stripped art still is the filed plate.

**Why the suite did not catch it.** The fixture drew its ring with PIL's `ellipse` outline,
which strokes *inward* from the bounding box — so filling it recovered the box exactly and the
round trip was perfect. The fixture was not representative of the thing being measured. It now
draws the band between two ellipses, so the centreline is known, and
`test_the_ring_is_fitted_and_not_merely_bounded` asserts the old method fails on it, or the
fixture would not be exercising the bias at all.

**A broken ring refuses rather than reporting.** The ring's height is `2 × radius × sin(θ)`,
so at a shallow camera a ring that looks generous side to side is still shorter than the
tile it encircles, and the tile sits on top of it. At 1.04 times the tile's height a 32° ring
read 6.0; at 1.20 it read 31.9. The briefs ask for a clear gap all the way round for this
reason, and `ring_ellipse` returns `None` on an open loop rather than reporting the number
that occlusion produces.

**Removing the ring means removing its soft edge too.** A pixel halfway along the ring's
antialiased edge is a blend of green and transparent background: low alpha, and an RGB pulled
far enough off the key to survive a colour test. The first version of `without_ring` left
those behind, and what survived was a faint ghost of the ring exactly where the ring had
been. On the cobbles candidate of 2026-09-23 the ring was 1382 px wide and the stripped
image's `alpha>8` box was still 1382, while the solid plate was 1159. It never moved a
measured angle — `ground_ellipse` fits the shape rather than taking a bounding box, and the
ghost was 0.8% of the ink — but every preview that crops came out 16% too wide. The stripper
now dilates the keyed mask and drops whatever is not near-opaque inside that band.

## What can carry a camera, and what cannot

**A circle can.** Its plan shape is known, so its foreshortening is the only thing that can
have changed it.

**A rectangle cannot.** Its height-over-width confounds foreshortening with plan proportions
and there is no way to separate them from the picture alone. The timber reference at
`ui/assets-gothic/grounds/candidates/planks_rough_c01.png` is the worked example: its ink is
1181 × 855, h/w 0.724, which is 46.4° if that patch is square in plan, 32.9° if it is 3:4 and
74.9° if it is 4:3. Three answers from one image, and nothing in the image says which.
`ground_ellipse` returns 21.8° on it, which is meaningless — 14% of its rows are within 2% of
the widest, so it is not an ellipse at all.

This matters when writing a brief. A reference image is handed the camera by the first
sentence of most of our briefs, and handing it to something that has no camera to give is how
two cobbles batches went astray. `prompts/planks_rough.md` therefore attaches two images and
says which job each one has.

## What the ring ratio is *not*

It is **not the anchor**. The two are unrelated quantities that both happen to sit near 0.5
in this project, which makes them easy to confuse.

The ratio is a *shape* — how squashed the ellipse is — and it is decided entirely by the
camera. The anchor is a *position*: how far down a piece of art its widest row falls, which
is where figures' feet belong on that particular picture. It is 48% on the rimmed plates and
58% on `cobbles_oval`, and the difference is the rim, not the camera: a rim is most of what
sits below the equator, so a plate without one has less ink under its widest row.

Drawing the same disc at five cameras makes the independence plain:

| camera | ratio | anchor |
|---|---|---|
| 25° | 0.421 | 47.5% |
| 30° | 0.496 | 47.5% |
| 32° | 0.527 | 47.4% |
| 40° | 0.640 | 47.6% |
| 50° | 0.762 | 47.5% |

The ratio sweeps its whole useful range; the anchor does not move. It cannot: the widest row
of an ellipse is at its vertical midpoint whatever angle you view it from.

The practical consequence is that moving a brief's target changes the camera and does not
change where figures stand — and if figures need to stand differently on a plate, that is the
`anchor` in `duty_grounds.json`, and editing the brief would be the wrong lever entirely.

## Two ways this measurement has fooled us

Both are worth keeping because both looked like findings at the time.

**The jig measured itself.** The first ringed cobbles batch, 2026-09-23, produced five clean
closed rings all inside a one-degree window — and four of the five tiles inside them were at
a different angle from their own ring, by up to 6.6°. The ring was honest about its own
geometry and said nothing about the tile. The fix is a cross-check rather than a single
number: report both the ring and the tile's outline, and require them to agree. On the plate
that was filed they agree to 0.1°.

**The ring measures, it does not steer.** Across three batches the rings' own angles averaged
32.0, 29.0 and 32.6, with within-batch standard deviations of 0.49, 0.68 and 1.4 — tight
inside a batch, three degrees apart between them, on briefs asking for the same number. The
generator appears to choose a camera per session and hold it. So the ring tells you whether a
batch is usable; it does not make it so, and more than one batch should be expected.

**The instrument was biased and its own test said otherwise.** This is the third, and the
worst, because unlike the other two it was invisible: a synthetic ring round-tripped
perfectly, so the suite reported the measurement as exact while it was out by up to 0.7° on
real rings. It surfaced only when someone measured one of our images independently, got 31.15
where our tooling said 31.57, and said so. The lesson is not about ellipses — it is that a
fixture built the same way as the code under test will agree with it for the wrong reason.

## Where things live

| | |
|---|---|
| the measurement | `tools/ui_debug/sculpt_metrics.py` — `ground_ellipse`, `ring_ellipse`, `without_ring` |
| the window | `tools/ui_debug/generate_asset_check.py` — `GROUND_TARGET_DEGREES`, `GROUND_TOLERANCE_DEGREES` |
| the judgement | the ground-tiles tab of `tools/ui_debug/generated/asset_check.html` |
| the briefs that ask for a ring | `tools/ui_debug/prompts/*.md` |
| this picture | `tools/ui_debug/generate_ring_ratio_explainer.py` |
| correcting a plate to the target | [`correcting-a-ground-plate.md`](correcting-a-ground-plate.md) — `tools/ui_debug/ground_tile_angle.py` |
| the camera decision itself | [`duty_tile_art_plan.md`](duty_tile_art_plan.md) |
