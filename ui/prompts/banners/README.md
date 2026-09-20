# Duty tile banners

Blank parchment strips. The title is **not** in the artwork — it is set live in
Pirata One over the top, so a duty can be renamed, the banner rescaled or a
hover state added without regenerating anything.

    <div class="duty-banner">
      <img class="duty-banner__bg" src="banner-1.png" alt="">
      <div class="duty-banner__title">TAXATION</div>
    </div>

## What the numbers are, and where they came from

Every figure below was measured off the art rather than chosen, and each one
exists because getting it wrong cost a generation.

| property | value | why |
| --- | --- | --- |
| parchment aspect | 3.12 : 1 | one width carries all nine titles; see below |
| tone | mean luminance 176, saturation 0.37 | matches the dark set already filed |
| body colour | `#c9ac84` | lit `#e6d1af`, shadow `#a87d4d`, scorch `#57351a` |
| title-safe zone | central 70% | widest title, BUILD ROADS, fills 68% of it |
| face | Pirata One, one size for all nine | cap height identical on every banner |
| vertical centre | 50% of the strip | see BALANCED TOP AND BOTTOM in the prompt |

**One width, not four.** An earlier system had short / medium / long /
extra-long groups mapped to title length. Pirata One sets narrowly enough that a
single 3.12 banner carries every duty from CITY to BUILD ROADS inside the safe
zone, which removes the group table, the re-mapping when a duty is renamed, and
the risk of a longer name outgrowing its assigned group.

**Say "fill 94% of the frame height", not "make it 3.12 wide".** Two generations
asking for the ratio numerically returned 3.85 and 3.61. One asking it to fill
the frame vertically returned 3.10. The generator follows a spatial instruction
about the picture it is drawing; it does not measure its own output.

**Balanced top and bottom is not cosmetic.** Torn tops that bite deeper than the
bottoms put the parchment's optical centre at 51–54% of its box rather than 50%,
and a single CSS `top` value then lands differently on every variant. Getting
the middle balanced at generation time is what lets one number serve the set.

## Known generator artefacts, handled in code

- **Alpha never reaches 255.** Bodies come back at 251–254. Harmless on a dark
  ground; on a pale one it lets the background bleed through the shadows. Snap
  anything above 240 to opaque.
- **Colour survives in erased pixels.** Bright red and yellow sit at alpha 1–7
  along the edges and show up in any viewer that ignores alpha. 13 pixels of
  500,000 are genuinely visible. Zero the RGB below alpha 8 when filing.
- **The canvas is whatever the generator wants.** It ignored 1250 × 400 every
  time and returned 2172 × 724. Only the parchment's own ratio is controllable,
  so crop to the art before measuring anything.

## Files

- `duty_banner.txt` — the prompt, one run per variant
- `reference_medium.png` — attach it with the prompt. It is `banner-medium-3`
  recentred to 49.8% and placed on the target canvas, so it demonstrates the
  proportion and the balance rather than just the colour. It is a **specimen,
  not an asset** — it is a resample of a smaller original and must not be filed
  as a banner.
