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

`V` is `A` (engraved plate) or `B` (grim dark). **B is the chosen set**; A is kept as the record of
that comparison. Generating A again is only worth it if you are revisiting the decision.

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

**Where to put the results.** The tooling only knows versions A and B (`find_tiles` matches
`[AB]`, and the picker iterates over the two). Rather than widen that for a trial, save the C
tiles as `NN_slug_B.webp` in a *separate folder*, and point the tools at it:

```
python3 ui/render/gen_picker_grid.py --tiles ui/assets-gothic/duty-tiles-colour --open
```

That keeps the committed B set intact and needs no code change. If colour wins, adding a real
version C is a small refactor across four files and worth doing properly then.

## The merge step now makes both orders

`*_option3_step2_merge.txt` asks for **two** square images: the panels merged as they are, and
merged with the two scenes exchanged. Which scene reads better on the left is not obvious before
you see it, and the merge quality differs between the two.

The prompt guards hard against the failure this invites — a single picture containing both
merges side by side, which is exactly what produced the captioned comparison sheets earlier in
this project. If it happens anyway, ask for the second merge in a follow-up message rather than
rewording.
