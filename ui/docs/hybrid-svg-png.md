# Hybrid SVG + PNG rendering contract

The player board stays a Python-generated SVG. Detailed raster artwork is embedded inside it as
transparent PNGs. SVG owns layout, geometry, counts, state, interaction and scaling; PNG supplies
the picture. The board is never rasterised whole.

**The central rule: icons are normalised by visible content, frames by coordinate canvas. A
transparent PNG's canvas bounds and its visual bounds are different objects, and nothing in SVG or
the DOM will tell you so.**

That splits every raster into one of two classes, which follow opposite rules:

| class | examples | canvas rule |
| --- | --- | --- |
| **content-normalised** | serfs, acolytes, small illustrated icons | crop tight to visible ink; the renderer supplies the padding |
| **coordinate-bound** | board frame, portrait ring, decorative collar | canvas corresponds exactly to a defined SVG coordinate rectangle |

Everything measured below was measured, not assumed: `verify_assets.py` recomputes it, and the
rendering claims were checked in the same headless Chromium this project screenshots with.

## 1. Population PNGs: normalise the ink, never the canvas

Do not size figures by giving every `<image>` the same width and height. SVG knows only the canvas;
it has no idea where the visible pixels start. `preserveAspectRatio` fits the canvas *including its
transparent margins* and can never normalise the artwork inside.

Measured on the concept assets in hand — three identical 1254² canvases:

| file | ink fill (w × h) | ink aspect |
| --- | --- | --- |
| `serf_wide_hat.png` | 0.592 × 0.689 | 0.859 |
| `acolyte_hood_cross.png` | 0.640 × 0.696 | 0.920 |
| `acolyte_tied_cloak.png` | 0.624 × 0.692 | 0.901 |

Their ink aspects differ by **7.1%**. Dropped into identical boxes the serf draws materially smaller
than the acolyte and floats off the baseline. **Treat these three as visual concepts, not production
assets.**

### Preparation

Find the alpha bounding box; crop to it, keeping only a small bleed for antialiased pixels;
normalise the set on a common **visible-ink height** — figures line up by how tall they stand, not
by how wide they happen to be; anchor on the **bottom centre of the ink**; add padding in the
renderer, not in the file. Canvases then differ and that is correct:

    serf_wide_hat.png          176 x 200
    acolyte_hood_cross.png     184 x 200
    acolyte_tied_cloak.png     180 x 200

A fixed square canvas is acceptable **only** with alpha-bound metadata and per-asset placement. On
its own it is not a normalisation method.

Tight crops also buy resolution: at 0.592 fill a 200 px canvas gives a 35 px icon only 118 px of
actual picture — 3.4×, not the 5.7× the number implies.

## 2. Neither DOM measurement sees PNG ink

`getBoundingClientRect()` and `getBBox()` both report the `<image>` **placement rectangle**.
Verified: a `serf_wide_hat.png` placed at 90 × 90 measures 90 × 90 from both, while its picture
fills 59% of that.

This matters more here than in most projects, because this board is sized by *measuring rendered
boxes* — every constant in `README.md` came out of that discipline, and a padded PNG reports a box
it does not fill. Raster artwork must therefore never take part in clearance or collision maths
based on DOM geometry alone.

Preferred: crop to the alpha bounds, so canvas and ink become the same object again.
Fallback: a sidecar for every raster. `assets/assets.json` holds one, generated from the files:

```json
{
  "src": "icons/population/serf/serf_wide_hat.png",
  "class": "content-normalized",
  "canvasPx": [1254, 1254],
  "inkBoxPx": [256, 195, 742, 864],
  "anchor": "ink-bottom-center",
  "normalization": "ink-height"
}
```

`inkBoxPx` is `[x, y, width, height]` in source pixels at an alpha threshold of 8. For a desired
visible height `H`:

    scale        = H / ink_height
    image_width  = canvas_width  * scale
    image_height = canvas_height * scale
    image_x      = target_center_x   - (ink_x + ink_width / 2) * scale
    image_y      = target_baseline_y - (ink_y + ink_height)    * scale

Anchors differ by category: population figures on the visible bottom centre, portraits on the eye
line or face centre, resource icons on the optical or alpha-box centre, frames on fixed canvas
coordinates.

## 3. The symbol viewBox can do the cropping

An asset that cannot be re-cut does not need the placement arithmetic above. Put its **ink box in a
`<symbol>` viewBox** and the viewBox does the crop:

```svg
<defs>
  <symbol id="serf" viewBox="256 195 742 864">        <!-- = inkBoxPx -->
    <image href="data:image/png;base64,…" x="0" y="0" width="1254" height="1254"/>
  </symbol>
</defs>
<use href="#serf" x="20" y="25" width="77.3" height="90"/>   <!-- 90 tall, 90 x 0.859 wide -->
```

Verified rendering correctly: two figures from untrimmed 1254² canvases, placed this way at a
common ink height, stand exactly the same height and share a baseline — while the same two placed
naively in equal 90 × 90 boxes come out unequal and floating.

Two conditions:

- **The `<use>` box must match the symbol viewBox's aspect.** The default `preserveAspectRatio` is
  `xMidYMid meet`, so a mismatch letterboxes and the normalisation silently fails. Derive the width
  from `height × inkAspect`, as above.
- **This fixes rendering, not measurement.** `getBBox()` on that `<use>` returns the *unclipped*
  referenced geometry: for the 77.3 × 90 placement above it reports **130.6 × 130.6**, the whole
  1254² canvas scaled. §2 still applies.

## 4. Frames are coordinate-bound

A frame deliberately contains transparent openings and overhang. Author its canvas against the exact
padded coordinate system it will be placed in, and treat the transparent margin as part of the
contract rather than as incidental space:

    visible board       320 x 120 units
    overhang allowance   20 units a side
    padded viewBox      -20 -20 360 160        ratio 2.25
    frame PNG           1800 x 800 px          ratio 2.25

`frame_01.png` is 1905 × 826 — ratio **2.306** — so forcing it into a 360 × 160 rect squashes it
2.4% horizontally, which is worst possible on circular portrait rings, jewels, symmetrical corner
ornaments and straight edges. Either re-export at the target ratio or change the SVG rect to the
PNG's native one.

**Never `preserveAspectRatio="none"` on a frame.** Use `xMidYMid meet`, or omit the attribute. The
real fix is a canvas and a target rectangle that are exactly proportional, so no fitting compromise
arises at all.

## 5. Base64 by default, embedded once

The deliverable is a single self-contained HTML file, so rasters are embedded as data URLs. A
relative `href` only resolves while the HTML sits beside its asset directory, and a board opened
anywhere else loses its artwork silently. The size cost is acceptable; a production build can switch
to relative paths.

What makes it affordable is embedding each raster **once** and reusing it. This requires `<symbol>`,
not a bare `<image>` in `<defs>`: verified, `<use>` **ignores width and height when it references an
`<image>`** — a 100 × 100 image referenced by `<use width="40" height="40">` still draws 100 × 100.
`<symbol>` establishes a viewport, so the `<use>` box sizes it.

One copy of the bytes, reuse across all four boards, easy switching between alternatives, and
predictable rendering from `file://` — all three mechanisms (relative href, data URL, `symbol`+`use`)
were confirmed to render in headless capture.

`pointer-events="none"` on every decorative raster layer, so it cannot eat taps or hovers.

For a missing-asset guard: SVG `<image>` elements are `SVGImageElement` and do **not** appear in
`document.images`, so the usual load check misses them entirely.

## 6. Player colour stays in SVG

The coloured spine, collar and portrait underlay are dynamic game state. Keeping them SVG lets one
neutral frame serve all four seats.

    SVG board base
    ├── neutral parchment
    ├── SVG player-colour spine
    ├── SVG player-colour portrait underlay
    ├── PNG portrait
    ├── neutral PNG portrait-ring decoration
    ├── neutral PNG outer frame
    ├── PNG or SVG population icons
    ├── SVG resource tiles
    ├── SVG counters and numbers
    └── SVG interaction states

Baking a seat colour into detailed artwork means four frame assets — a deliberate choice, not a
default.

## 7. Split the ring from the frame while geometry can still move

One merged frame freezes the relative geometry of ring, collar and outer frame. The collar has
already had to move once — 20 units right and 8 down, so the expanded log could cover it — and as
two constants that was trivial. Baked into a PNG it becomes a re-export, and the generator can no
longer answer where the ring is. So while anything can still move:

    player_frame_outer.png
    portrait_ring.png
    portrait_connector.png     (optional)

each placed independently. Merge them only when the geometry is final.

## 8. Production rules

**Population icons** — alpha-tight crop, common visible-ink height, bottom-centre anchor,
renderer-controlled padding, ink-box sidecar where recutting is impossible.

**Portraits** — transparent or intentionally coloured background, consistent head scale, eye-line or
face-centre anchor, kept separate from the portrait frame.

**Frames** — exact canvas-to-viewBox contract, transparent openings and intended overhang included,
no non-uniform stretching, neutral where colour is dynamic, outer frame split from portrait ring
while geometry may change.

**Embedding** — Base64 by default, each raster defined once in `<defs>` as a `<symbol>`, reused
through `<use>`, `pointer-events="none"` on decorative layers.

**Measurement** — DOM rectangles measure placement geometry only, never visible ink; layout and
collision logic reads explicit asset metadata.

## 9. Enforcing it

`assets/verify_assets.py` checks the contract rather than trusting it: it recomputes every alpha box
against the declared one, flags any content-normalised asset whose ink fills less than 95% of its
canvas, and flags a normalisation group whose members' ink aspects disagree by more than 2%. Run it
before an asset is used, not after a layout has been built on it. On the current concept assets it
reports four problems, which is correct — they are concepts.

    python3 verify_assets.py            # check
    python3 verify_assets.py --write    # recompute assets.json from the files

Third-party rasters carry licences where drawn SVG does not; see `assets/README.md`.
