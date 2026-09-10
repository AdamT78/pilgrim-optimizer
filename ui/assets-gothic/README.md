# Pilgrim Gothic v2 minimal single-board assembler

This package contains a minimal production assembler for the recalibrated v2 player board.

It builds one board at a time and keeps the v2 frame architecture:

- `assets/frames/frame_base.png`
- `assets/frames/stones_red.png`
- `assets/frames/stones_black.png`

The script uses the corrected/recalibrated template and asset set, including the fixed acolyte, fixed silver coins, and fixed population divider.

## Self-contained output

Each asset is embedded once, in `<defs>`, and referenced by `<use>` at each placement. `set_href()`
mirrors the modern `href` into the legacy `xlink:href` only for paths and `#id` references, never
for a data URI — mirroring a Base64 payload writes the whole thing twice, which took one board from
about 6 MB to 12.6 MB with nothing visibly wrong. `assert_no_duplicated_payloads()` runs on every
build and refuses to write a file where any element carries both, because that failure is invisible:
the board renders correctly at twice the weight, so nothing complains and nobody looks.

## The picker

    python3 gen_picker_2.py --assets-dir ./assets --open

Swap the portrait and the gemstones on the real board and look at the result. It does not draw
anything of its own: it calls this assembler's `apply_config` and `embed_assets_once`, then adds a
symbol per candidate and repoints the relevant `<use>`. The board on the page is therefore the
board the assembler makes, which is the only way a picker stays honest as the assembler changes.

Options are directory listings, so adding a file adds an option and no code changes:

    assets/portraits/*.png       the portrait
    assets/frames/stones_*.png   the gemstones, plus "none" for no overlay at all

`portraits/full/` is skipped: those are the 1254 px reveal cuts, not board candidates.

The picker opens on whatever `production_test_config.json` specifies, so the first click is a
comparison rather than a correction.

**The picker is where normalization belongs.** The template fits each asset's canvas, not its
visible ink, so a replacement with different transparent margins draws smaller or offset. When that
becomes a problem, measure ink bounds here at render time — see the sizing section below — and
never by moving the production template's coordinates.

## The portrait opening is an oval

The frame's portrait opening is an **ellipse**: rx 213, ry 195.5 about (409.5, 360), measured by
flooding the enclosed transparent region of `frame_base.png`. The template used to clip the
portrait to a circle of r 190, which left a ring between the clip and the frame's inner edge with
nothing drawn in it — so the page behind the board showed through, which reads as white because it
is absence rather than a colour. Widening the circle does not fix it: at r 206 the widest points of
the oval were still 2.58% uncovered. `portraitClip` and `underlay-portrait` are therefore both
ellipses at 216 x 199, roughly three units under the frame's inner edge all round, so the frame
overlaps the ground and there is no seam.

If the frame artwork is ever regenerated, re-measure the opening and match these two shapes to it.
They are registration-bound to the frame in exactly the way the gemstone overlays are.

## The portrait ground is plain, and the config controls it

The ground is a single filled ellipse taking `portrait_background` from the config. It used to
carry a vertical gradient, a group of gothic tower silhouettes at 24% opacity and a paper-noise
overlay stacked on top of the plain fill, which meant `portrait_background` was very nearly inert —
the setting existed but the layers above it covered what it did. Those three layers are gone, along
with the now-unreferenced `portraitGround` gradient.

## Portraits: two cuts, two uses

    assets/portraits/leader_*.png        640x640   what the board draws
    assets/portraits/full/leader_*.png  1254x1254  the game-start reveal

The board's portrait box is 448 units of a 1905-unit viewBox, so at the usual 1400 px render the
portrait draws about 329 px and 640 is roughly twice that. Even at a 2x-density display it is 0.97x
— a 3% upscale, which is why 640 is the size rather than 1254. Measured against the 1254 master at
the drawn size, the 640 cut differs by a mean of 0.54 of 255, with under 2% of pixels off by more
than 4 levels; side by side at 2x zoom the two are indistinguishable.

The full cut is not an archive. It has a use — the leader reveal at game start, where the portrait
is drawn large — so it is a second production asset rather than a master, and it lives under
`portraits/full/` so the board's own directory holds exactly what the board uses. The template path
is unchanged, which is why swapping the cut required no template edit.

## Asset sizing, and what may never be normalized

The template places every asset into a fixed box with `preserveAspectRatio="xMidYMid meet"`. That
protects the aspect ratio, but it fits each asset's **full canvas, not its visible ink**. The
current artwork set has similar transparent margins — ink fills 0.94 to 0.98 of canvas across the
set — so the calibration done by eye against these files is sound. It is sound *because of a
property of these assets*, though, not because the coordinates alone make it so.

Replacement artwork with substantially different transparent margins will therefore appear smaller,
larger, or vertically offset in the same box. A replacement filling 85% of its canvas where the
current one fills 95% draws about 10% smaller; asymmetric margins shift it as well as shrink it.

**Do not compensate for replacement-asset padding by changing production template coordinates.**
The production template is calibrated against the approved asset set. Normalization of replacement
artwork belongs in the development picker, which measures visible ink at render time.

**Never normalize registration-bound artwork.** `frame_base.png`, `stones_red.png` and
`stones_black.png` share one coordinate system and must keep their full canvas dimensions and exact
pixel registration. Cropping, ink-centering or independently scaling any of them breaks gemstone
alignment — and it breaks it invisibly on one variant at a time.

Normalization is a property of an asset's role, not of the pipeline:

| asset | treatment |
| --- | --- |
| `frame_base.png`, `stones_*.png` | **never normalize.** Registration-bound; full canvas is the contract |
| serf, acolyte | normalizable in the picker: measure visible ink, anchor `ink-bottom-center` |
| resource artwork | normalizable in the picker: measure visible ink, anchor `ink-center` |
| portraits | **no ink-bound normalization.** A bounding box moves with a hood or a shoulder while the face does not; keep the authored composition, or add an explicit focal point |
| cubes and other SVG symbols | use the authored `viewBox`. Vector assets carry their own coordinate system, so the canvas/ink gap is a raster problem — but a viewBox looser than its geometry has the same failure, and `getBBox()` on a `<use>` reports unclipped geometry |

There is deliberately no `asset_metrics.json`. The assembler needs each asset's canvas and nothing
more, and it reads that from the file itself. Metadata describing visible ink would be a second
source of truth for a measurement this program never makes. When the picker needs those numbers it
should measure them at render time — the whole normalizable set measures in about 0.2 seconds — and
cache only if that ever stops being cheap.

## Render red stones

```bash
python3 assemble_pilgrim_playerboard_v2_minimal.py \
  --assets-dir ./assets \
  --gem-color red \
  --name pilgrim_v2_minimal_red \
  --output-dir ./build \
  --formats svg,html,png \
  --output-width 1400
```

## Render black stones

```bash
python3 assemble_pilgrim_playerboard_v2_minimal.py \
  --assets-dir ./assets \
  --gem-color black \
  --name pilgrim_v2_minimal_black \
  --output-dir ./build \
  --formats svg,html,png \
  --output-width 1400
```

PNG output requires CairoSVG:

```bash
python3 -m pip install cairosvg
```

SVG and HTML output use only the Python standard library.


## Divider fix

`assets/ui/population_divider.svg` has been replaced with a reference-style vertical divider:
a dark spear-ended line, a central fleur-de-lis, and a narrow bevel highlight. No Python logic
was changed.


## Divider line variant

`assets/ui/population_divider.svg` now uses a thin straight vertical divider in a dark parchment-compatible color, with spacing left above and below so it does not visually touch the upper or lower frame.


## Single-line divider variant

`assets/ui/population_divider.svg` is now one continuous straight vertical line.
It uses equal top and bottom margins inside the divider asset, so it leaves matching
space to the upper and lower frame rails.


## Single-line divider v2

The divider line has been moved slightly downward to account for the top frame ornament extending into the panel, and its tone/opacity have been softened so it integrates more naturally with the parchment background.


## Single-line divider v3

The divider line is thicker and uses three blended strokes for a soft shaded look, so it feels integrated with the parchment rather than like a scratch. It is also moved slightly further downward to better balance the visible top and bottom parchment margins against the surrounding dark frame.


## Single-line divider v4

The divider is now a visibly thicker shaded bar rather than a thin stroke. It remains one
continuous vertical line, but uses a small gradient, dark edge and bevel highlight so it
feels integrated with the parchment. It is also shifted lower to account for the top frame
ornament.

## Upper-panel alignment v5

The left-hand population group is the alignment reference.

- The acolyte is scaled to the same displayed height as the serf and starts at the same y-position.
- Horizontal spacing on the right of the divider mirrors the left side around divider centre x=1222.
- Right-side centres are: acolyte 1372, yellow cube 1479, count 1634.
- The gemstone colour does not affect any population/resource coordinates; red and black builds use the same template.


## Upper-panel alignment v6

- The second / acolyte figure is horizontally aligned to the center of the stone resource window below.
- Stone resource window center x = 1355.5.
- Acolyte box = x 1275, y 226, width 161, height 148.
- Red and black gemstone versions use the same template and therefore the same alignment.


## Upper-panel alignment v8

- The right-side number is aligned so the distance from the yellow cube to the number matches the distance from the grey cube to the left-side number.
- Left cube center = 965, left number center = 1072, gap = 107.
- Right cube center = 1511, right number center = 1618, gap = 107.
- Red and black gemstone versions use the same template and therefore the same alignment.


## Upper-panel alignment v9

- Both upper population numbers were shifted 12 units left.
- `8`: x 1072 → 1060.
- `2`: x 1618 → 1606.
- All other positions are unchanged.
- Red and black gemstone builds use the same template.


## Upper-panel alignment v10

The entire left population group was moved 36 units to the right:

- serf: x 730 → 766
- grey cube: x 930 → 966
- `8`: x 1060 → 1096

All three elements moved together, so their internal spacing is unchanged.
The right-side group, divider, frame, resources and gemstone assets are unchanged.
Red and black builds use the same template/alignment.


## Upper-panel alignment v11

The entire right population group was moved 36 units to the right:

- acolyte: x 1275 → 1311
- yellow cube: x 1476 → 1512
- `2`: x 1606 → 1642

All three elements moved together, so their internal spacing is unchanged.
The left-side group remains as in v10.
Frame, divider, resources, and gemstone assets are unchanged.
Red and black builds use the same template/alignment.


## v12 tweaks

- Nudged both upper parchment figures up by 1 px for cleaner horizontal alignment.
- Recolored the acolyte cube asset from yellow to red.
- Applied identically to red-gem and black-gem builds.
