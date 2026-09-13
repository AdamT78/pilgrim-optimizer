# The 3×3 background

## What you have

`Duty_wheel_base_1536.png` — your `Duty_wheel_base_v1` (1254², frameless) with 141 px of
synthesised parchment added on each side. The added border is matched to the sheet's own colour and
grain: the seam measures 2.9 of 255, and the synthesised grain follows the real one's blur profile
to within 7% out to a 16 px blur.

Note what the padding does and does not do. The tiles keep exactly the pixels they had; the grid
now fills 82% of the image instead of 100%, so each tile is **drawn 18% smaller** on screen. It
buys a margin, not detail. If you would rather the grid filled the slot, use the unpadded 1254
version — the component is unframed now, so nothing else supplies a border.

## Does it need more resolution?

No. The artwork box measures **783.8 × 626.2** canvas units framed, **787.8 square** unframed,
which at your window and DPR 2 comes to about **1247 device pixels**. The 1254 background is
therefore 1.01× — effectively pixel-perfect, with no upscaling.

This is the one asset where your generator's 1.57 Mpx cap is not a constraint, because the
background is low-frequency: flat parchment plus nine outlines. The tiles are where detail matters,
and that is why they are generated separately.

## If you regenerate it

Two requirements are technical rather than aesthetic, and both matter more than they look.

**Flat, distinct colours inside the shapes.** This is what let me pull the nine masks out by colour
segmentation instead of tracing edges by hand — and those masks are what give each tile its hover
region and its gold edge. Nine different flat colours, no texture or scene inside them.

**Even margin, no outer frame.** `Duty_grid_v1` had a dark frame drawn around it, which would sit
inside a component that already has its own border rules. `Duty_wheel_base_v1` dropped it, which is
right.

---

## Version A — warm parchment

```
An aged parchment sheet seen flat from directly above, filling a square frame. Laid on it, a
3 x 3 grid of nine irregular tile shapes, evenly spaced, each one a rounded square with a soft
wandering torn edge and a fine dark outline. Each tile is a single flat solid colour, all nine
colours different and muted: sage green, slate blue, brick red, ochre, warm grey, dull violet,
steel blue, olive, tan. No texture, no picture and no detail inside the tiles - flat colour only.
The parchment between and around them is warm cream with fine mottling. An even margin of
parchment all the way round. Square 1:1, flat even lighting, no shadows, no outer frame or border,
no text of any kind.
```

## Version B — dark weathered

Use this if the tiles are grim dark. Cold grey tiles on bright warm parchment is a strong contrast
— it can read as ink on a table, or it can fight. Worth generating both and judging in the wheel.

```
An old, dark, weather-stained parchment sheet seen flat from directly above, filling a square
frame - smoke-darkened, foxed and worn, in deep umber and cold grey-brown. Laid on it, a 3 x 3
grid of nine irregular tile shapes, evenly spaced, each one a rounded square with a soft wandering
torn edge and a fine dark outline. Each tile is a single flat solid colour, all nine colours
different, muted and desaturated: dark sage, iron blue, oxblood, dull gold, ash grey, faded
violet, slate, moss, umber. No texture, no picture and no detail inside the tiles - flat colour
only. An even margin all the way round. Square 1:1, flat even lighting, no shadows, no outer frame
or border, no text of any kind.
```

Save as `00_background_A.png` / `00_background_B.png`, alongside the nine tiles.

---

## What I do with it

Segment the nine flat colours into nine masks (~774 bytes each, 7 KB for the set), plus a tenth
mask for their union so the dim filter leaves the parchment alone. Then each tile's art is
composited into its shape, the parchment shows between them, and the hover takes its gold edge
from the shape's own alpha via `feMorphology`.

Which means the colours themselves never appear in the finished wheel — they are a region map, not
a palette. Pick them for being easy to tell apart, not for looking good together.
