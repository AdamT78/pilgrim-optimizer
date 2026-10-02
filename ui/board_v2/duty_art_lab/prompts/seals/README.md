# The seal briefs

One file per seal, **word for word as it was sent**, each marked `<!-- archival: -->` — which is
the mechanism `generate_duty_art_board.py` already has for exactly this: "somebody's text as they
wrote it, kept because it produced a particular picture… it gets a button and no substitution".

`<!-- produces: -->` names the file each one made. That is what `attribution.json`'s
`reproducibleBy` points at, and what the duty art board matches a seal to.

## There is no shared brief here, and that is a finding rather than an omission

The action-card briefs in `../` are one text with `{{LEFT_SUBJECT}}` and friends substituted in,
because they genuinely are one brief run against eight duties. The seal briefs look like they
work the same way — the same section headings, the same vocabulary — so the obvious move was to
pull the common part out into a template.

Measured, they do not. Splitting the four on their `======` rules and comparing word by word:

| section | compared | words the same |
| --- | --- | --- |
| VERY THIN OUTER EDGE | red wheat vs grey wheat | 67% |
| CAMERA / PRESENTATION | red wheat vs grey wheat | 60% |
| LIGHTING | red wheat vs grey wheat | 59% |
| REAL …CONSTRUCTION | red wheat vs red stone | 46% |
| REAL SEAL CONSTRUCTION | grey wheat vs grey stone | 41% |
| COLOR / MATERIAL | grey wheat vs grey stone | 33% |
| SURFACE / AGE | grey wheat vs grey stone | 31% |
| SMALL-SIZE READABILITY | grey stone vs red stone | 31% |
| FINAL GOAL | grey wheat vs grey stone | 24% |
| STONE MOTIF | grey stone vs red stone | 13% |

Nothing is near-verbatim. These are four separately written prompts that share a **vocabulary**,
not one brief with holes in it. A template built from them would be a document that never existed
and never produced anything, and every record pointing at it would be approximately true — which
is the one thing a provenance record must not be.

## What the vocabulary actually is

Worth knowing when writing the next one, because the phrasing is not equally good everywhere and
the later files are not the better ones. Reading the diffs rather than the similarity scores:

- The differences between the red and grey versions of EDGE, LIGHTING and CAMERA are almost all
  **drift**, not intent: `centred`/`centered`, `focal length`/`focal-length`, `No coloured
  reflections`/`No colored light`, a line moved. Nothing there distinguishes a red seal from a
  grey one.
- Two differences are not drift, and both are **losses in the grey wheat version**. It dropped
  the lip figure — "approximately 4–6% of the seal radius" became "a narrow irregular outer lip",
  so the one quantity in that section went missing — and it dropped `No black background` from
  the exclusions. The grey stone brief later restored the lip figure; the grey wheat one never
  did.
- The red wheat brief has the most specific LIGHTING of the four ("small specular highlights on
  polished wax; deep but soft shadows inside the impressed recesses"). The grey wheat one replaced
  it with a vaguer list.

So the best phrasing for a new seal is mostly the **red wheat** brief, with the grey stone brief's
COLOR / MATERIAL section when the seal is a resource.

## Two things in here are stale and stay stale

**"approximately 55–70 px wide."** True when the Tithe tokens were 64 and the duty seals 46. The
board has drawn both at 78 since the seals went diagonal, so these briefs ask for readability at a
size nothing uses. Left as written.

**The edge proportion is not the figure the repository enforces.** These ask for an impressed face
of 88–92% of the diameter plus a 4–6% lip, which is about where the wax ends on the *seal*.
`SOLID_FRACTION` in `../../action_board/geometry.py` is 0.906 and measures something else — how
much of the *square PNG* the drawing fills — and the generator does not hit any stated target
reliably: the nineteen filed so far came back between 0.914 and 0.998 of their squares. That is
why `tools/duty_art/file_seals.py` corrects every one of them about its own centre, and why the
master is kept. Do not try to fix this by rewording a brief.

## The reference chain

Three of the four were built from the one before it, which is why they are numbered in generation
order rather than by duty. `<!-- reference: -->` records it per file:

```
red PRODUCE wheat  →  grey TAKE TITHE wheat  →  grey TAKE TITHE stone  →  red PRODUCE stone
                                  └──────────────────┴──→  grey TAKE TITHE silver
```

Silver branches rather than continuing the line: it was told to match the grey wheat AND stone
together, so it is the first one written against a family rather than against a single picture.
Every brief names its own reference in its opening sentence, so the header is a reading of the
text rather than a note kept beside it.

Note that the download order of the images disagrees with this: the grey pair reached Downloads
before the red pair. The chain above is what the briefs themselves say, and the pictures agree
with the briefs — the red wheat seal has the three stalks its brief asks for and the grey one the
single stalk it was told to reduce to.

## The standing ground reference is one named file

`duty_actions/build_roads/seals/build_roads_actionA_seal_v03.webp` — **the road, not the shrine.**

Any brief that asks for a lighter wax ground attaches that file and no other. It is named here by
filename, as a fixed point, because the alternative was tried and it drifted.

Each ground brief was handed the previous seal as its reference, and the flat wax field climbed
every time it was asked to:

```
shrine v02   13   (where the complaint started)
road   v03   35   brief 13, floor and no ceiling
alloc  v03   43   brief 15, floor and no ceiling, reference = road v03   target 35, +8
shrine v03   46   brief 14, floor AND A CEILING, reference = road v03    target 35, +11
tax    v04   42   brief 17, floor and no ceiling, reference = road v03   target 35, +7
wheat  v03   46   brief 18, floor and no ceiling, reference = road v03   target 35, +11  (predicted 42-46)
stone  v03   48   brief 19, reference = WHEAT v03 (46)                   target 46, +2
```

The last row was a **prediction written before the image existed**, because a bias only ever
noticed afterwards is indistinguishable from a story. It was 42–46 and the result was 46. Produce
wheat started at 27, the smallest deficit any of these briefs has been written against, and still
overshot by eleven — so the bias is a roughly fixed offset, not a proportion of the gap being
closed.

Four briefs have now aimed at the road's 35 and landed at 43, 46, 42 and 46: **+8, +11, +7, +11**,
mean +9, spread of four. That is tight enough to act on.

### What those four briefs do and do not show

Line them up by where they started rather than by what they landed on:

```
            started    landed
allocation     20   ->   43
shrine         24   ->   46
taxation       13   ->   42
wheat          27   ->   46
```

The starting points span fourteen and the landings span four. **The result is set by something
other than the seal being fixed** — these briefs do not nudge a ground upward, they replace it
with a particular one.

What that something is cannot be told from these four, because all four held the reference image
(the road, 35) and the brief's wording constant together. Reference and wording are perfectly
confounded. "The generator lands nine above whatever it is shown" fits the data exactly as well as
"this wording produces a ground in the mid-forties whatever is attached", and the two give opposite
advice.

**An earlier version of this section asserted the first of those and told you to attach a darker
seal — Give Alms at 26 — to land on 35. Treat that as withdrawn.** It was an untested
extrapolation from a single reference value, and applying it to produce stone, which starts at 36,
would have pointed a brief at an image darker than the seal it was meant to lighten. The arithmetic
ran backwards the moment it met a case that was not far too dark.

### Brief 19 settled it, against both accounts

It attached wheat at 46 instead of the road at 35. A landing near 55 would have meant the offset
follows the reference; near 44 would have meant the wording decides alone. It landed at **48**,
missing those by seven and by four.

```
reference attached   landings              mean
        35           43, 46, 42, 46        44.25
        46           48                    48.00
```

Eleven points of reference bought under four points of result. **About a third of a change in the
reference reaches the output; the wording sets the rest and anchors it in the mid-forties.** That
is why starting points between 13 and 27 all landed within four of each other: these briefs do not
move a ground by an amount, they install one.

Two cautions on that number. It rests on a single sample at the second reference value, so the
third is an estimate from two points. And the wording was not held constant either — brief 19
dropped the "large, clear lift" rhetoric because a gap of ten did not justify it — so some of the
four points may be wording rather than picture.

### What follows for the next brief

**You cannot steer the ground precisely by choosing a reference.** To land a seal somewhere other
than the mid-forties the wording has to change, and the one wording experiment on record — brief
14's ceiling — made the result worse rather than better. Until someone tries another, treat "this
family of briefs produces a ground in the mid-forties" as the fact, and choose the reference for
honesty rather than for aim: attach the seal the result genuinely has to sit beside, so the brief
says something true whatever the number does.

A seal already in the forties should not be sent through this wording at all. It has nowhere to
go.

Three things in that table are worth keeping.

**A ceiling made it worse, not better.** Brief 14 was the only one to name an upper bound, and it
is the one that missed by most — eleven above the road it was told to match, where the two briefs
with a floor and no ceiling landed eight above theirs. Do not reach for an upper bound expecting
it to help; brief 14's own header says the same thing at the point of use.

**The overshoot is consistent, and that is still not a correction.** Eight, eleven, seven, every
one above the reference, is a bias rather than noise. It is tempting to start aiming low by eight —
do not. A brief that asks for a darker ground than it wants is a brief nobody can read straight, it
stops being archival the moment someone edits it back, and the bias is measured against one
reference file at one size of lift. Aim at the reference and expect to land roughly ten above it.

**The size of the lift did not change the overshoot.** Brief 17 asked the face to move 29 points
where the others moved single figures, and it still landed seven over. So the overshoot behaves like
a fixed offset rather than a percentage, which is the more forgiving of the two: a seal already
close to the reference will not be thrown far past it.

## The ground statistic is not trustworthy and is withdrawn

Everything above this line that quotes a "flat wax field" number rests on one statistic: the MODE
of the luminance of the seal's opaque face. Filing ordination's pair broke it, and the break is not
a near miss.

Mission's source image measures **61**. The same seal, filed, measures **4**. Nothing about the wax
changed — `file_seals.py` scales the image by 0.97 about its centre and re-encodes it. What changed
is which of two peaks in the histogram happened to be taller. A mode is a winner-take-all statistic,
and a seal with a large dark region (here, a deep hood and heavy robe shadow) has two peaks that
can trade places under a resample.

Five variants were tried on the full set of fourteen and each breaks on a different subset:

| variant | how it fails |
| --- | --- |
| mode of the whole opaque face | flips to the dark peak on seals with a large dark motif |
| mode inside radius 0.62 | lands on motif shadow where the design fills the centre |
| flat wax in the ring 0.66–0.78 | lands on the motif where the design reaches outward |
| median of the band outside the rim | confounded with band width; a wider band samples more shadow |
| flat pixels connected to the rim's inner edge | collapses to a sliver on seals whose motif touches the rim |

The rim-edge detector underneath the last three is itself unstable: it reports produce stone's rim
at 66% of radius, which is deep inside the face, and shifts by five points on other seals when its
bin range changes.

**So no further ground numbers should be quoted from this folder until the measure is rebuilt and
its mask is rendered and checked over all fourteen seals.** The overlay check is not optional —
every one of the five looked plausible until its mask was drawn on the picture.

### What this does and does not invalidate

The ordination pair was judged by eye at board size instead, where the two read as a matched pair
with calm borders. That is the judgement that mattered and it needed no metric.

The earlier conclusions in this file — that these briefs install a ground rather than shifting one,
that roughly a third of a change in the reference reaches the output — were drawn on seals where
the whole-face mode was checked against the ring mask and agreed within three (road, shrine, wheat,
taxation). They are probably sound. But "probably sound, on the cases I happened to check" is a
weaker claim than those sections make, and they should be re-derived once there is a measure that
survives all fourteen. Treat the numbers in the drift table as provisional.

The silhouette measures are unaffected and remain reliable, because they use only the alpha
channel and need no segmentation of the wax at all: **wobble** (standard deviation of the outer
radius over its mean) and **lobe count** (dominant angular frequency of the same profile). The
border work was settled on those.

### Which measure

`flat wax field` = the **modal luminance of the opaque face**, Rec.709, measured on the shipped
`.webp` at full resolution, over pixels with alpha > 250 — **the shipped print, not the master and
not the file in Downloads.** `file_seals.py` scales every seal about its own centre to
`SOLID_FRACTION`, and that resample moves the mode: taxation v04 reads 44 as downloaded and 42 as
shipped. Two points is enough to misjudge an overshoot. Composite before comparing anything
across a background; raw RGBA where alpha is zero is undefined and every encoder writes something
different there.

**Do not measure the face as "everything inside radius 0.62".** That looks like the obvious way to
exclude the rim and it fails on exactly the seals that matter: where the motif fills the centre,
the mode lands on motif shadow instead of on wax. It reports produce wheat as 13 when its ground
is 27, and build roads' shrine as 6 when its ground is 46. Both would have been written into a
brief as a far bigger deficit than really existed.

The check that settles it is **the flat wax in the ring just inside the rim** — mask `0.66 < r <
0.78`, keep the flattest half by local standard deviation, take the mode. Overlaying that mask on
the seal shows it landing on true unimpressed ground for every seal in the set, including the two
above, and it agrees with the whole-opaque-face mode within three everywhere it has been tried
(wheat 24/27, road 34/35, shrine 46/46). So the simple measure defined here is sound; it is the
clever-looking radius crop that is not. If a ground figure ever looks surprising, run the ring
mask and look at the overlay before believing it.

**The mode is the right statistic for the face and the wrong one for the rim.** The face is mostly
one flat tone, so its histogram has a single tall peak and the mode sits on it. A thick lobed
border does not: it is highlight, flank and shadow in roughly equal measure, the histogram is broad
and multi-peaked, and the mode lands wherever the widest of those happens to be. Measuring
taxation's rim by mode said it went 21 → 20 and had not moved at all; by median it went 31.8 → 37.2
and had. Use the median for the rim, and do not report a rim mode as though it meant the same thing
as a face mode.

Whole-face **mean** luminance does not track this and should not be used: when Build Roads was
first called too dark beside Give Alms, the two means differed by 3–8%, which is nothing. The
modal field is the measure that moved.

Earlier work in this project quoted 25.9 / 29.9 / 37.9 / 45.8 / 49.8 for these same files. Those
came from a variant that could not afterwards be reproduced from either the prints or the masters.
The ranking and every gap are the same; the absolute numbers here are the ones on the measure
defined above, and mixing the two sets is how a target gets missed by four.

## A brief is not the whole provenance when the generator has a memory

`16-taxation-red-five.md` is four lines, attaches nothing, and says not one word about a border.
What came back has the thick uneven lobed rim that `12-taxation-red.md` asked for, because both
were sent in the same ChatGPT conversation and the earlier instruction was still in scope.

So for the seals generated in that chat, the brief in this folder is **necessary and not
sufficient**: re-sending the same text into a fresh conversation will not reproduce the file. The
`<!-- reference: -->` header on 16 says so. When a brief's result shows a feature the brief never
asked for, that feature came from the conversation, and the next brief should state it outright —
which is what `17-taxation-red-ground.md` does for the border it needs kept.

## Wobble is the one luminance-free measure, and it is the one that works

While the ground statistic was collapsing, the border work settled cleanly, because the measure it
rests on never touches the wax at all. **Wobble** is the standard deviation of the seal's outer
radius over its mean, taken from the alpha channel: it describes the silhouette and needs no
segmentation, no threshold and no assumption about where the motif is.

```
                              wobble
clerical Devotion v01          4.04%   <- most lobed on the board
clerical Silversmith v01       3.22%
ordination pair, before        2.8%
ordination pair, after         1.7%    <- brief 22/23 asked for "roughly half"
build roads road v03           1.52%
```

"Reduce the depth of the undulations by roughly half" produced almost exactly half. That is the
only instruction in this folder so far that has landed on its target rather than near it, and the
difference is probably that it names a ratio of a thing the generator can see in the reference,
rather than an absolute it has to infer.

Briefs 24 and 25 asked the clerical pair for **one third**, because 4.04% was further out than
anything yet attempted. It stalled:

```
                 before   asked   got     ratio delivered
devotion          4.04%   1.35%   1.89%      2.14x
silversmith       3.22%   1.07%   2.03%      1.59x
```

Two seals that started 0.8 apart finished 0.14 apart, neither near its target.

I read that as a floor on how round these outlines would go, and predicted the construct pair would
stall in the same place. **That was wrong, and the way it was wrong is the most useful thing in
this file.**

```
                  start    instruction                     landed
clerical pair     4.04%    "reduce to one third"            1.89%
                  3.22%    "reduce to one third"            2.03%
construct pair    2.58%    describe the finished outline    1.37%   <- roundest on the board
                  2.33%    describe the finished outline    1.79%
build roads road    --     --                               1.52%
```

The construct pair started CLOSER to round and finished ROUNDER, one of them below the road itself.
There is no floor. What separates the two rounds is the wording.

### Describe the finished state. Do not name an amount of change.

A ratio asks the generator to do arithmetic against a baseline it was never given — it cannot see
"4.04%", so "one third of it" is not an instruction, it is a gesture. A description is something it
can match:

> irregular and organic but close to round: an outline that reads as a hand-made disc with gentle,
> shallow swells, not as a ring of distinct bulging lobes. A viewer should notice it is not a
> perfect circle only on looking twice.

That is the whole of the change between briefs 24/25 and 26/27, and it moved the result further
while asking for less. The same shape explains the border instruction that kept half-failing:
"lift it in step with the face" names a motion, "land at least as light as the face" names a state.

### What this does to the "installs a value" claim

That claim was made on the ground numbers — starts of 13–27 landing at 42–48 — and then extended to
wobble on the strength of the clerical pair alone. **The extension does not survive construct.**
Wobble is not installed at a fixed value; it responds to how the instruction is phrased. The ground
result stands on its own evidence and is untouched, but read it as a fact about the ground rather
than a law about these briefs. One extra measure agreeing was never enough to generalise from, and
it only looked like enough because that measure was being read wrong.

Lobe COUNT behaved differently again: construct's road went 14 → 4, matching build roads, while its
building stayed at 13 with the amplitude nearly halved. At low wobble the dominant frequency is
reading noise rather than structure, so treat lobe count as meaningful only above about 2%.

## A tile is a pair, and a brief that moves one moves half a picture

Produce had to be done twice — wheat to 46, which left stone at 36, then stone to 48 — because the
first brief treated one seal as the unit of work. The unit is the TILE. Two seals are drawn a few
pixels apart and are seen together or not at all; a ten-point difference between them is more
visible than a twenty-point difference between seals in different tiles.

Current within-tile gaps:

```
build_roads   35 / 46   gap 11
produce       46 / 48   gap  2
clerical      17 / 21   gap  4
construct     16 / 21   gap  5
give_alms     26 / 26   gap  0
ordination    17 / 17   gap  0   <- both dark, both still v01
```

Ordination is the instructive one. Both its seals sit at 17, so the tile is *consistent* while
being the darkest on the board. Putting one of them through this family of briefs would land it in
the mid-forties and open a gap of twenty-eight — twice the worst gap that exists today, and
created by an improvement. Briefs 20 and 21 are written as a pair for that reason, and below the
motif section they are word for word the same text.

**Before writing a ground brief, look at the other seal in the tile.** If it is within a few
points, write both or write neither.

## "The border looks thick" was not about the border's width

Brief 20 lifted Mission's ground from 17 to 50 and the result was rejected for a heavy-looking
border. Three measurements, in the order they were tried:

```
                        band outside the ring      lobes    wobble
mission v01                      21.0%               11      2.64%
MISSION from brief 20            21.8%               11      2.63%
build roads road v03             23.9%               15      1.52%
taxation v04                     33.2%               13      2.31%
```

**The border did not get wider and it did not get more lobed.** Both measures are within rounding
of the version it came from, and its width is mid-pack — taxation's is half again as heavy and
nobody has complained about it.

What changed was the border's tone *relative to the face*:

```
                     ground   border   border - ground
mission v01            17      30.4         +13.4
MISSION brief 20       50      46.3          -3.7
every other seal     26-48       —      +2.6 to -1.1
```

The ground rose 33 points and the border only 16, so a border that had been thirteen shades
LIGHTER than its face ended up four shades DARKER — the only seal on the board where that is true
by more than one. A dark frame around a lit disc reads as a thick frame whatever its width.

So an impression about shape turned out to be about tone, and the fix is not to narrow anything.
Narrowing it would have made the seal unlike its own family while leaving the cause untouched.

### The instruction that keeps half-failing

Both brief 17 and brief 20 asked for the border to be lifted "in step with the face". Taxation's
rim moved 5 while its face moved 29; Mission's moved 16 while its face moved 33. **Twice is a
wording problem, not luck.** "In step with" describes a direction of travel and can be satisfied
by any movement at all.

Briefs 22 and 23 state it as a floor against a measurable thing instead: *the border must land at
least as light as the face, and never below it.* If a relationship matters, write the relationship,
not the motion.

## What produced the v01 seals is not recorded

Fourteen duty seals and two resource seals were filed before any brief was kept. Their
`reproducibleBy` says so in as many words rather than guessing, and the duty art board shows them
without a brief. If the texts turn up, they go here with the same headers.
