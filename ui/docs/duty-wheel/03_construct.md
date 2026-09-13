# 3 · Construct

One block = one image request. Copy a block, paste it on its own, generate, save.

Two actions: **Construct a building** on the left, **Construct a road** on the right.

## Version A — engraved plate

Save as **`03_construct_A.png`**

```
Nineteenth-century steel-engraving style, dense cross-hatching, sepia and warm grey ink on aged paper. Fourteenth-century English setting. Even, neutral illumination across the whole frame - no dramatic side-light, no glow, no spotlight, no vignette. Overall tonal value light to middle, as a book illustration printed on cream paper: most of the picture in light and middle tones, with dark ink reserved for accents and never covering large areas. High detail but bold, readable forms.

Two scenes side by side, each occupying exactly half of a square frame.
Left (Construct a building): Masons raising a stone wall on scaffolding, a block swinging on a hoist.
Right (Construct a road): Labourers laying a cobbled road, one tamping stones with a mallet.

The two halves meet directly, edge to edge, with no dividing line, no rule, no border, no gutter and no gap of any kind between them. The transition is loose and organic - the change of place happens across a band of picture rather than along a straight edge. Each scene occupies exactly half the width, so the change of place falls at the centre of the square. Each half is tall and narrow: give each scene a single figure or one close action, seen near full height.

Square 1:1. Full bleed to all four edges - no border, no frame, no parchment margin, no torn edge, no caption or text of any kind. Keep the outer 6 per cent of the picture clear of anything important.
```

## Version B — grim dark Gothic

Save as **`03_construct_B.png`**

```
Fourteenth-century England in a grim, oppressive register. Heavy gothic architecture crowding the frame, weather-stained stone, bare branches, crows, guttering candles, faces gaunt and weary. Dense engraved cross-hatching in cold iron-grey and black ink, bitten deep. Overcast and joyless. Even illumination across the whole frame - no spotlight, no glow, no vignette - but a low, sunless key throughout. Blacks rich and detailed, never flat or blocked up; the cross-hatching must stay separable everywhere, with no solid black masses. High detail, bold readable silhouettes.

Two scenes side by side, each occupying exactly half of a square frame.
Left (Construct a building): Masons hauling stone up wet scaffolding in sleet, one man slipping on the boards.
Right (Construct a road): Labourers breaking stone in a mud track, an overseer standing over them with a switch.

The two halves meet directly, edge to edge, with no dividing line, no rule, no border, no gutter and no gap of any kind between them. The transition is loose and organic - the change of place happens across a band of picture rather than along a straight edge. Each scene occupies exactly half the width, so the change of place falls at the centre of the square. Each half is tall and narrow: give each scene a single figure or one close action, seen near full height.

Square 1:1. Full bleed to all four edges - no border, no frame, no parchment margin, no torn edge, no caption or text of any kind. Keep the outer 6 per cent of the picture clear of anything important.
```

---

## After generating

```
python3 check_tile.py 03_construct_A.png --version A
```

It reports the join position, whether a rule got drawn, and the tonal key. If the join is off centre, do not regenerate — send me the number and I move the gradient.
