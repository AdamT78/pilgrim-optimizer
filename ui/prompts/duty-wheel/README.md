# Prompt files

Every `.txt` here contains one prompt and nothing else — no headings, no notes, no filenames.
Safe to paste, or to attach as a file. **Do not send this index.**

## The route

One route is kept here: the two-send **pair then merge**, which is what every committed tile was
actually made with. Three others were written and tried — a single send for the whole nine-tile
wheel, a single send per tile, and a three-send version generating each action separately — and
none of them is what got used. They are in git history if you want them back.

```
NN_name/V_option3_step1_pair.txt   ->   NN_name/V_option3_step2_merge.txt
```

Send step 1. You get a landscape image of two panels side by side with a blank band between them.
Then send step 2 **with that image attached**; you get the square tile. The filenames keep their
`option3` prefix so they still match the route named in the `.md` reference files and in the
commit that removed the others.

The four single-action tiles — Allocation, Build Roads, Taxation and the City — have only
`V_whole_tile.txt`. They are one scene, so there is nothing to merge.

### A second route, added for Construct

```
NN_name/V_option3_step2_merge_cross.txt
```

A cross-merge: TWO pair images are attached and ONE panel is taken from each, rather than both
panels of a single pair. It exists because a pair can come back with one panel worth keeping and
one not, and regenerating the pair to fix the second half throws away the first.

The committed Construct C tile was not made this way. It was **composited by code** — the same two
panels, cropped a fifth of their width from the inner side, level-matched per channel and butted at
the centre through a 20 px cross-fade. That is worth knowing before you reach for either: a
composite keeps the artwork exactly as generated and puts the join at 0.5, where the board's
lit/dim mask already splits, but it cannot make anything FLOW across the join. It worked there only
because the two inner edges were 43 levels apart before cropping and 0.8 after — measure that
first, on the columns that would actually touch, not on the panels as wholes. The prompt route
redraws a band instead, so weather and ground carry across; the cost is a regeneration, and the
figures may not come back as they are.

`V` is `A` (engraved plate) or `B` (grim dark). **B is the chosen set**; A is kept as the record of
that comparison. Generating A again is only worth it if you are revisiting the decision.

## The background, which is not a tile

```
background/left.txt        background/right.txt          the night field
background/left_v2.txt     background/right_v2.txt       the mist field -- what the board draws
background/left_v3.txt     background/right_v3.txt       not generated yet
```

`_v2` is the same two scenes with the empty middle made PALE instead of dark, and it exists for a
measured reason rather than a taste. The wheel paints no ground of its own, so what shows between
the duty tiles is this picture; behind the wheel the night field sits at L\* 12.9 and the tile
edge ink is L\* 13.5, which is to say a tile's outline was the same value as what was behind it.
The v2 prompts hold the mist near `#464442` in a band, and both halves must name the SAME inner
edge value or the butt join needs an overlap.

The band is a target and the model overshot it: the committed halves came back at L\* 37 rather
than 29. That is worth knowing before regenerating, because the direction has a cost as well as a
benefit -- the wheel's acolyte marks sit on this field too, and pewter is the one a lighter ground
closes on. Measured as dE76 against the field behind the wheel, night gave edge 8.3 and pewter
37.7; mist gives edge 24.3 and pewter 24.6. Everything now separates by about the same margin,
which is the argument for it.

### Where a subject has to sit, which is not where v1 and v2 put it

**The board covers panorama 24.4% to 75.6% on every display, whatever its shape.** The stage is a
fixed 1600x1200 canvas that is zoom-to-fitted, and the panorama is `center/cover`, so both are
scaled by the same height and shrink together; changing the display changes only how much panorama
is VISIBLE either side of it. Worked from those two numbers alone:

| display | visible panorama | exposed left | exposed right |
| --- | --- | --- | --- |
| 2.606:1, as composed | 0 – 100% | 0 – 24.4% | 75.6 – 100% |
| 1.882:1 | 13.8 – 86.2% | 13.8 – 24.4% | 75.6 – 86.2% |
| 1.778:1 (16:9) | 15.8 – 84.2% | 15.8 – 24.4% | 75.6 – 84.2% |
| 1.600:1 (16:10) | 19.2 – 80.8% | 19.2 – 24.4% | 75.6 – 80.8% |

So the strip that is both uncovered AND visible on every screen is the **five points just outside
the board** — roughly 19–24% and 76–81%. Everything further out is seen only on wide displays.

v1 and v2 said "the outer quarter" and then pushed the subject to the OUTER edge of it: measured,
they centre their detail at 9.8% and 88.4%. That is the part a 16:10 display throws away first. On
a 1.882:1 screen the left shrine falls off entirely and the right one is cut at 86.2%, which leaves
a wide empty field beside the board and a clipped scene at the edge.

v3 inverts it. The focal point — statue, candles, kneeling figures — is anchored against the INNER
edge of the strip, and the scene thins OUTWARD from there rather than inward, so a wide display
gets more of it rather than a different picture. v3 also takes the outer scene back to the night
register, which v2 lifted along with the mist: dark at the edges, pale only where the board sits,
which is the arrangement the tiles actually need.

`background/` has no `NN_` prefix on purpose. `NN` is a one-based position in `DUTY_NAMES` and it
decides which square a tile is drawn in; the panorama behind the whole game view is not a duty and
has no square, so numbering it would be a claim about the wheel that is not true.

Two sends, one per half, **and they are not a pair-then-merge route**: neither half is a panel of
the other, and nothing is attached to the second send. Each is a complete landscape in its own
right at 1.30:1, and the two are butted together into 2.600:1 by
`python3 ui/render/gen_panorama.py`, which also carries the two corrections the join needs. Save the
results as `ui/assets-gothic/ui/sources/panorama_{left,right}.webp`, **lossless** — the join
measures the level step off their inner columns, so a lossy re-encode moves it.

What these two prompts are mostly about is the EMPTY part. The board covers 26%-73% of the screen,
so each half's inner side has to carry nothing a viewer would look at, and the paragraph that gets
that is the one saying so in the negative — no trunk, no ruin, no silhouette, "not a faint one, not
a distant one". Two earlier rounds asked for "no readable detail" and got *less* detail instead.
The foreground paragraph exists for the same reason: the fog was read as a horizontal band, so the
sky emptied and the ground filled with rubble edge to edge.

Two more things that are load-bearing rather than stylistic. Only the LEFT prompt may have a moon —
the right one says so explicitly, because a second one reads as two moons over one landscape. And
both ask for a flat `#1e1d1b` at the inner edge, which is what makes the butt join possible at all;
without it the halves need an overlap, and an overlap costs 2.6 px of height for every px of it.

## Using these with ChatGPT

**Start a new chat for every tile.** ChatGPT carries context between turns, and that is what
produced the A/B comparison images with its own captions baked along the bottom, and what put two
tiles in one picture. It is also how style drifts from tile to tile. One chat, one tile.

**Do not ask for two versions in one chat.** Generate Version A for a tile, then start a fresh
chat for Version B. Asking for both invites a comparison image.

**Say nothing else in the message.** No "can you also", no follow-up tweaks in the same chat — a
re-render is a new drawing, not an edit, so the second attempt loses whatever was good about the
first.

**The 1254 px ceiling is gpt-image-1, not a setting.** It renders about 1.57 Mpx and reshapes to
whatever aspect you ask for: 1536x1024 landscape, 1024x1536 portrait. Asking for 1536 square
returns 1254, because that is 1.57 Mpx made square.

## Then run the checker

```
python3 ui/render/check_tile.py 06_ordination_B.png --version B
```

Save results as `NN_name_V.png` — `NN` is the tile's **one-based position in `DUTY_NAMES`**, so
Produce is `07` and Taxation is `08`. That number decides which square the tile is drawn in, and
getting it wrong does not fail, it just puts the art somewhere else. Keep the two-panel source
under `duty-tiles/sources/V/NN_name_V_pair.png`.

What the checker will and will not tell you:

- **Resolution and squareness.** Worth trusting. An 887 px tile reached the tree once and the only
  clue was its file size.
- **Tonal key and black mass.** Worth reading, not obeying. Version A came in anywhere from 92.7
  to 146.1 on identical wording, which is the model's spread rather than something the prompt can
  fix.
- **The join.** It no longer looks for one. Every pair splits down the middle and every merge keeps
  it, so the join is 0.5; the heuristic that used to measure it found pillars and scaffold posts
  instead, and was wrong every time it could be checked against a source pair.
## The colour set (version C)

`C_*` is the same nine scenes on the palette the CITY actually uses, measured off
`05_city_B.webp` rather than chosen:

```
median chroma            2.4      the picture is essentially neutral
most saturated tenth    17.0      a single warm amber-cream, almost all of it sky
greys              #191917 #31302d #474542 #615e5a #7c7874 #a39c93
the one hue        #bda58c .. #d7c5ae
```

So this is **not a colourful set**. It is grisaille with one warm light, and that is what
"restricted to the city's colours" means once the city is measured. If you want real colour
variety, the city has to be regenerated first — it is the reference every other tile is matched
to, and `PALETTE = "full"` in `gen_duty_grid.py` would otherwise pull colourful tiles back toward
this grey.

**Where to put the results.** Straight into `duty-tiles/C/` as `NN_slug_C.webp`, with the source
pairs in `duty-tiles/sources/C/`. The refactor this section used to defer has been done: every
version pattern takes any single letter now, the picker discovers which versions exist instead of
listing them, and `gen_duty_grid.VERSION` says which one the board draws.

```
python3 ui/render/check_tile.py ui/assets-gothic/duty-tiles/C/*.webp \
        --version C --joins-out ui/assets-gothic/duty-tiles/joins.json
python3 ui/render/gen_picker_grid.py --tiles ui/assets-gothic/duty-tiles --open
python3 ui/render/gen_game_view.py --duty-version C --open
```

The advice this replaced was to save the C tiles under a `_B` suffix in a side folder, because the
tooling only knew `[AB]`. **Do not do that.** It was a workaround for a limitation that no longer
exists, and it files one set under another set's name — a tile's letter and number decide which
set it belongs to and which square it is drawn in, which is why there is a guard on exactly that.

## The merge step now makes both orders

`*_option3_step2_merge.txt` asks for **two** square images: the panels merged as they are, and
merged with the two scenes exchanged. Which scene reads better on the left is not obvious before
you see it, and the merge quality differs between the two.

The prompt guards hard against the failure this invites — a single picture containing both
merges side by side, which is exactly what produced the captioned comparison sheets earlier in
this project. If it happens anyway, ask for the second merge in a follow-up message rather than
rewording.
