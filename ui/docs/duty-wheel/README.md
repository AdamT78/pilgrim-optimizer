# Duty wheel — 3×3 grid redesign

Working notes and art-direction specs. **Nothing here is final.** The open questions are listed at
the bottom; the numbers are measured off the rendered page rather than computed, and are noted as
such where it matters.

## The idea

The circular duty wheel becomes a 3×3 grid of irregular torn tiles: eight duty tiles ringing the
city at centre. Each duty tile carries its one or two actions as pictures. Hovering an action
lights that half of the tile and the action box describes it.

## What the wheel is made of

Four things, and only the first is artwork:

1. **Nine tile pictures** — one generation each, neutral, no baked lighting.
2. **One background** — parchment with nine flat-coloured torn shapes. The colours are a region
   map, not a palette: they are segmented into nine masks and never appear in the finished wheel.
3. **Nine region masks + one union mask** — derived from the background, ~774 B each, 8 KB union.
4. **Two `feColorMatrix` filters and one gradient** — every visual state the wheel has.

The states are *not* assets. This is the central decision and it was settled by measurement, not
preference — see below.

## Why the states are filters

The obvious approach is three pictures per tile: neutral, left-lit, right-lit. Twenty-seven images.
Two measurements ruled it out.

**Size.** At 1448 px PNG that is 92 MB in the page, against a four-board page of 5.6 MB. Even
right-sized and WebP-encoded it is 3× the filtered version.

**Drift — the decisive one.** Each lit state would be a separate diffusion pass, and diffusion
merges are not deterministic. Comparing two of the first-experiment merges on a half that is
*unlit in both*:

```
mean level difference      5.50 of 255
pixels differing by >20    6.5%
edge difference           13.0        the drawing moved
worst 300 px window       48.4
```

A figure's arm moves, trees regroup, a cross shifts. Hovering would make the tile redraw itself
under the cursor. A filter leaves the drawing alone; a second generation cannot.

## Measured geometry

Off the rendered `layout-tool.html` under `ui/layout.json`, at a 1680×950 viewport (zoom 0.7917):

```
#wheel slot            787.8 x 787.8 canvas units
  artwork, framed      783.8 x 626.2   (frame_border_y 0.10 takes 78.8 top and bottom)
  artwork, unframed    787.8 x 787.8
tile, unframed grid    246.6 square, gap 24
one action half        123.3 wide  ->  about 195 device px at DPR 2
```

**The wheel must be unframed** — drop `"wheel"` from `framed` in `ui/layout.json`. The tiles bring
their own torn edges, and the frame's 10% vertical border makes the artwork box landscape (1.25:1)
while the tiles are square. The frame's round clip (`.wheel-in { border-radius: 50% }`) also has to
go; it cropped the first two renders into circles.

## The image tool's ceiling

The generator reshapes a fixed **1.57 Mpx** budget to whatever aspect is asked for:

```
1448 x 1086 = 1,572,528 px
1254 x 1254 = 1,572,516 px
```

Twelve pixels apart. So 1254 is the largest square available and 1536 is not reachable — asking
for it returns 1254. This is why the tiles are generated separately rather than as one grid: nine
tiles at 1254 each is three times the linear resolution of one 1254 grid.

Attachments are *not* downscaled — an attached file arrives byte-identical to the one on disk
(verified by md5). An earlier note in these files claimed otherwise; that was wrong.

## Budget

Nine tiles at 534×440 WebP q82, measured on real engraving: **~0.6–0.8 MB** in the page. Masks add
~15 KB, the highlight gradient 412 bytes. Against 92 MB for the naive 27-image version.

## Files here

```
00_background.md      the parchment sheet with nine flat-coloured shapes, both themes
01..09_*.md           one per tile, both themes, self-contained
```

`ui/render/check_tile.py` validates a generated tile: size, join position, whether a rule got
drawn, tonal key, near-black mass. Run it before sending anything.

## Open questions

- **Ring order.** `tools/ui_debug/duty_wheel_layout.json` is not in the checkout, so the order in
  these files comes from the `DUTY_TEXT` table in `gen_board.py`. `MERCHANT_ON = "Taxation"`
  suggests a token walks the ring, which makes adjacency a rules question. Settle before art is
  cut to fit.
- **Version A or B.** Engraved plate reads as nine distinct objects; grim dark is more atmospheric
  but the unselected tiles start merging into each other. Undecided.
- **Tonal drift.** Three generations have come in at mean 89–100 against a 122 first tile, on
  wording that explicitly asks for light-to-middle values. May be where the model sits; if so, lift
  the key in the composite instead.
- **Player squares.** The old wheel carried them. This design does not yet; numbers instead of
  cubes was mentioned but not designed.
- **Seam detection from source.** Whether the join can be found by comparing a merge against its
  source images is untested — it needs one matched set (two sources plus the merge made from them).
