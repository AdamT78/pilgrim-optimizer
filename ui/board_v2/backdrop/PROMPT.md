# Backdrop prompt — the vertical restriction, and the prompt that honours it

The board puts eight translucent duty tiles and a line of black type over the top of this picture.
Everything the eye is meant to read has to sit **below** them.

## Where the line falls

The shipped picture is a crop of a 10:3 master, so the percentage the generator must be given is
the percentage of the **master**, not of the crop — the crop drops 59/420 of the master's height
off the top, and every line moves when it does.

| line, measured up from the base | % of the cut file | **% of the 10:3 master** |
|---|---|---|
| road strip top | 28.8% | 24.8% |
| **tiles' lower edge — the limit** | **48.8%** | **41.9%** |
| tiles' top edge | 84.8% | 72.9% |
| black status text, foot | 89.2% | 76.7% |
| black status text, top | 97.2% | 83.6% |

**In the master: the bottom 40% carries the motif, the top 60% is sky.** Ask for 40 rather than
41.9 so there is a little slack.

Three things that follow and are easy to miss:

**The tiles are glass, not boards.** 55% opaque, so anything in the 42–73% band is seen *through*
a cream emblem rather than hidden by it. That band has to be mist, not faint buildings.

**And the sky has to be two different tones, which is the part that caught us out.** The two
objects printed over this picture want opposite things:

| band (up from the base) | what sits there | wants | measured |
|---|---|---|---|
| 77–84% | the black status line | **light**, 115 at the very least | v03 145 · Misty 209 |
| 42–73% | the eight glass tiles | **dark**, around 110–140 | v03 81 · Misty 187 |

A single flat mist cannot serve both. `Misty Monastic Pilgrimage` was pale all the way down — 187
behind the tiles — and the cream emblems fell to **4.21:1** against their own tile, under the 4.5
they need; v03's valley sat at 81 there and gave 4.72:1. So the sky is asked for as a **strong
vertical gradient**: palest at the very top edge where the type goes, deepening to a dark
featureless fog mass by the horizon where the tiles go.

Dark fog, **not** dark shapes. A hillside or treeline would darken the band and put readable
forms behind the emblems, which is the fault the whole restriction exists to avoid. What is
wanted is depth with nothing in it.

**Percentages are the weakest instruction in the prompt.** The generation of 11 Oct obeyed every
one of them except the almshouse, whose roof came out at 53% up against a 40% limit — because a
building with a roof has a ridge, and the model will put the ridge where the building needs it.
The fix was never a louder percentage, it was **not asking for a tall object**.

Which left the left end with nothing to say. A doorway in a bare wall obeyed the rule and read as
nothing in particular, so the almshouse was given depth instead of height: a flagstone courtyard,
a broad flight of steps going down, and a footing wall turning a corner into the fog. Ruins at
knee height say "a building stood here" as plainly as a roof does, and cost nothing above the
line.

**And then "cellar" bought the height straight back, in a shape nobody asked for.** Ask a model
for an entrance that goes underground and it reaches for the barrow: a vaulted tunnel mouth with
an earth mound heaped over it, which is a roof made of grass and sits exactly where a roof sits.
Flattening the ground and reducing the whole thing to a free-standing gate did not help either.

**Four tries, and the diagnosis was the scene, not the wording.** Roof, bare wall, cellar, gate:
every one of them was an attempt to draw an ENTRANCE, and an entrance is a hole in a building, so
the model kept supplying the building the hole needs. Meanwhile the centre and right scenes have
never once broken the rule — because they are **people and small objects on open ground**, and
nothing in them wants to be tall.

The open-air dole that finally worked proved the point: a trestle, a cauldron, a queue, and the
rule held first time. **So the triptych was retired altogether.** If the only panel that never
caused trouble was the pilgrim trail, and the fix for the other two was to make them more like
it, then the honest version of that is one motif across the whole width — pilgrims on a road,
with shrines along it. v04 shipped as the last of the three-scene backdrops; the prompt below is
the single-motif one.

## Generate at

**Any ratio wider than about 3:1; the crop is mechanical and works it out.** 2800 × 840 gives 2×
density, which is what a retina display wants. Anything around 2200 wide gives about 1.6×, which
is what the last three have been. 1400 × 420 is 1.0× and visibly soft.

The rect wants **1344 : 225 = 5.973 : 1**, which is wider than any image model will generate, so
something always has to come off. Which edge depends on the master:

```
R = 1344 / 225

if W / H >= R:        # master is wider than the rect: keep the height, trim the sides evenly
    cw, ch = round(H * R), H
else:                 # master is taller than the rect: keep the width, drop the TOP
    cw, ch = W, round(W / R)

side, top = (W - cw) // 2, H - ch
crop (side, top) to (side + cw, H)
```

Worked, for the masters this has actually been given:

```
2800 x 840  (10:3)  ->  crop (0, 119) to (2800, 840)  =  2800 x 752   (2.08x)
2290 x 687  (10:3)  ->  crop (0,  72) to (2290, 687)  =  2290 x 615   (1.70x)
2171 x 724  ( 3:1)  ->  crop (0, 141) to (2171, 724)  =  2171 x 583   (1.62x)
1400 x 420  (10:3)  ->  crop (0,  44) to (1400, 420)  =  1400 x 376   (1.04x)
```

**THE EARLIER RULE HERE WAS WRONG AND IT IS WORTH SAYING HOW.** It took 28/1400 of the width off
each side and whatever was left off the top — fine, because the first master arrived at exactly
1400 wide, the canvas's own width, so those 28s were the board's own margins and the picture
landed as if laid across the whole canvas. That coincidence was then written down as the rule. A
3:1 master breaks it immediately: the side crop leaves a frame that needs **2357** px of width
from a master that has 2171, so `side` comes out negative and the per-tile check reads an empty
slice and reports `nan`. A wrong answer would have been better than that one was lucky to be.

The side crop was never doing any work. Nothing requires the picture to correspond to the canvas
— it has to fill 1344 × 225 and nothing more. So the sides are only trimmed when the master is
genuinely too wide, and the top is what goes otherwise, which is what every master so far has
needed anyway.

**A taller master pays for it in sky.** The crop drops the top until the ratio is right, and the
top is the palest part of the gradient — the 3:1 master lost 141 rows and its text band came out
at 148 where the same picture at 10:3 would have kept more light. Generate wide.

## The prompt

**No motif at all, which changes the job completely.** Six backdrops were pictures, and each one
was a negotiation between what the generator wanted to draw and what the board needs behind it.
The board needs two things that pull against each other: the status line is BLACK type and wants
a light band, and the duty tiles are 55% glass over cream emblems and want a dark one. A painting
has one sky. With nothing to compose, every band can simply be put where it belongs.

**And it frees the crop.** A landscape has to be cut at one particular window or the composition
breaks; mist has no composition, so any horizontal slice of the master will do. Generate a tall
fog gradient and I will search it for the 383-row window whose bands land closest to the targets
below, instead of taking the bottom and hoping. That removes the thing that has sunk the last two
cuts — the shorter the band gets, the more of the pale top a bottom-anchored crop throws away,
which is why the shipped picture's status line is down at 3.27:1.

So: generate **as tall as you like at any wide ratio**, 3:1 is fine, and aim the tones at these
fractions of the FINAL band rather than of your frame:

| | fraction of the band | wants |
|---|---|---|
| status line, black type | 4.4% – 17.3% down | **pale and even, around 195** |
| the eight duty tiles | 24.4% – 82.2% down | **deep, around 95–115** |
| the road strip | 82.2% – 100% down | **darkest, around 70** |

---

Ultra-wide atmospheric fog study, 3:1 aspect ratio or wider, landscape orientation, no text.
**A field of cold mist and nothing else — this is a texture, not a scene. There are no objects in
this image of any kind: no landscape, no horizon line, no ground, no figures, no structures, no
silhouettes, no sun, no moon. Only air.**

The fog is a **strong, smooth vertical gradient**: at the top it is pale, almost white, a clean
even haze with very little variation across it. From there it deepens steadily and continuously
downward, through soft greys, to a deep, heavy, near-black fog at the bottom edge. The fall is
gradual and unbroken — no band, no edge, no line anywhere where the tone changes step.

Within that gradient the mist lies in **broad horizontal sheets and strata**, as fog does when it
settles in still air: long, soft, wide drifts many times wider than they are tall, overlapping
and dissolving into each other, some a little lighter and some a little darker than the gradient
they sit in. The drifts are **soft-edged everywhere** — nothing in this picture has an outline.
Fine film grain throughout.

**The palette is near monochrome ash grey with the faintest warm cast** — a trace of sepia in the
light, cooler in the depths, no blue anywhere. Desaturated, low-key, painted engraving quality,
the feel of a wet winter dusk with no light source in frame.

## Negative prompt

text, title, letters, logo, watermark, signature, border, frame, vignette, objects, any object,
landscape, horizon, horizon line, ground, land, hills, mountains, trees, treeline, forest,
silhouettes, shapes, figures, people, animals, buildings, structures, shrines, stones, water,
sea, lake, reflections, sun, sunlight, moon, stars, light source, sunbeams, god rays, crepuscular
rays, clouds, cloud puffs, cumulus, billowing smoke, swirls, vortex, spirals, turbulence, visible
edges, hard edges, outlines, banding, posterisation, stepped gradient, flat even sky, uniform
tone with no gradient, bright white blowout, pure black crush, blue tones, cyan, teal, saturated
colours, high contrast, dramatic lighting, cartoon, anime, digital glitch, noise artefacts

## Checking one before it is cut

```
python3 - <<'EOF'
from PIL import Image
import numpy as np
im = Image.open("YOUR_MASTER.png").convert("L")
W, H = im.size
R = 1344 / 225

# CUT IT FIRST, THEN SCORE THE CUT. Every band below is a fraction of the CROP, which means the
# same thing whatever ratio the master arrived at. Scoring the master instead needs a different
# set of fractions for every ratio -- the version of this that did was quietly measuring a
# different part of the picture the first time a 3:1 master turned up.
cw, ch = (round(H * R), H) if W / H >= R else (W, round(W / R))
side, top = (W - cw) // 2, H - ch
a = np.asarray(im).astype(float)[top:H, side:side + cw]
h, w = a.shape
print("crop (%d, %d) -> %d x %d   density %.2fx" % (side, top, w, h, w / 1344))

# A STRUCTURE IS DARKER THAN THE FOG AT ITS OWN HEIGHT. The sky is a vertical gradient, so one
# reference level for the whole band calls the lower fog a silhouette. The row's own median IS
# the local sky.
dark = a < (np.median(a, axis=1, keepdims=True) - 28)
line = h * 0.822                           # the tiles' lower edge, 82.2% of the crop down
rows = dark.mean(axis=1)
first = int(np.argmax(rows > 0.02))
print("top quarter        %5.2f%% painted" % (100 * dark[:round(h*0.25)].mean()))
print("above the line     %5.2f%% painted" % (100 * dark[:int(line)].mean()))
print("first row over 2%%: %d  -> %d px above the line" % (first, line - first))

# AND PER TILE, which is the question that actually matters: a shrine in a gap between two tiles
# costs nothing, the same shrine behind one costs the emblem its clean field.
k = w / 1344.0
for i, n in enumerate("Clerical Taxation Produce BuildRoads Construct GiveAlms Ordination "
                      "Allocation".split()):
    x0 = (40 + i*170) * k
    print("  %-12s %5.2f%%" % (n, 100 * dark[int(line - 130*k):int(line), int(x0):int(x0+74*k)].mean()))

# THE TWO BANDS WANT OPPOSITE THINGS, so both are reported. A flat sky passes every test above
# and still fails here.
def rel(u):
    u = u / 255.0
    return u / 12.92 if u <= 0.03928 else ((u + 0.055) / 1.055) ** 2.4
text  = a[round(h*0.044):round(h*0.173)]     # the black status line is printed on this
tiles = a[round(h*0.244):round(h*0.822)]     # the eight glass tiles stand on this
print("text band  %3.0f  black type reads at %.2f:1  (wants 4.5, so >= 115)"
      % (text.mean(), min((rel(r.mean()) + 0.05) / 0.05 for r in text)))
print("tile band  %3.0f  (wants 110-140; pale fog here costs the emblems their field)"
      % tiles.mean())
print("gradient   top %3.0f -> horizon %3.0f  (wants a fall of 60 or more)"
      % (a[:round(h*0.06)].mean(), a[int(line)-20:int(line)+10].mean()))
EOF
```

**Pass looks like**, for a mist with no motif: nothing registering as painted matter anywhere,
the text band over 4.5:1 and ideally near 11:1, and the tile band down around 95–115. The
per-tile numbers are a leftover from the motif backdrops and should all read 0.00% — if any of
them does not, the generator has put something in the fog.

Where the candidates landed, all scored on the crop:

| | worst tile | text band | tile band | emblem on tile |
|---|---|---|---|---|
| v03 (two versions ago) | — | 145 | 81 | 7.58:1 |
| Misty Monastic | 1.4% | 209 | 187 | 4.23:1 |
| **v04 (shipped)** | 5.6% | 183 | 124 | 6.67:1 |
| Fogbound Pilgrims (3:1) | 10.4% | 148 | 89 | **8.14:1** |

The emblem figures are measured on the rendered `.tile` element at 4×, not sampled out of a
screenshot by eye — an earlier method did the latter and read three points low across the board.
