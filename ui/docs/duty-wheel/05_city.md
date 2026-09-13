# 5 · The City

One block = one image request. Copy a block, paste it on its own, generate, save.

This is the centre tile and the only one **never dimmed**, so its generated brightness is what you actually see. Under Version A pitch it *no brighter* than the duty tiles — it separates by being the only thing still in full colour. Under Version B make it *clearly brighter and warmer*: the one lit place in a sunless world. Both prompts below already carry the right line.

Single action — the scene fills the whole square.

## Version A — engraved plate

Save as **`05_city_A.png`**

```
Nineteenth-century steel-engraving style, dense cross-hatching, sepia and warm grey ink on aged paper. Fourteenth-century English setting. Even, neutral illumination across the whole frame - no dramatic side-light, no glow, no spotlight, no vignette. Overall tonal value light to middle, as a book illustration printed on cream paper: most of the picture in light and middle tones, with dark ink reserved for accents and never covering large areas. High detail but bold, readable forms.

A walled medieval city seen from just outside its gate: curtain wall and towers, a cathedral spire above crowded roofs, carts and travellers passing through the gate. No figures in close foreground - this is a place, not an action. Overcast light, nothing brighter than the wall face.

Square 1:1. Full bleed to all four edges - no border, no frame, no parchment margin, no torn edge, no caption or text of any kind. Keep the outer 6 per cent of the picture clear of anything important.
```

## Version B — grim dark Gothic

Save as **`05_city_B.png`**

```
Fourteenth-century England in a grim, oppressive register. Heavy gothic architecture crowding the frame, weather-stained stone, bare branches, crows, guttering candles, faces gaunt and weary. Dense engraved cross-hatching in cold iron-grey and black ink, bitten deep. Overcast and joyless. Even illumination across the whole frame - no spotlight, no glow, no vignette - but a low, sunless key throughout. Blacks rich and detailed, never flat or blocked up; the cross-hatching must stay separable everywhere, with no solid black masses. High detail, bold readable silhouettes.

A walled city under a bruised sky, smoke rising from within, a gibbet standing outside the gate, carts and travellers still passing through. No figures in close foreground - this is a place, not an action. Warmer and better lit than the surrounding scenes: low sun breaking on the wall and spire.

Square 1:1. Full bleed to all four edges - no border, no frame, no parchment margin, no torn edge, no caption or text of any kind. Keep the outer 6 per cent of the picture clear of anything important.
```

---

## After generating

```
python3 check_tile.py 05_city_A.png --version A  --single
```

It reports the join position, whether a rule got drawn, and the tonal key. If the join is off centre, do not regenerate — send me the number and I move the gradient.
