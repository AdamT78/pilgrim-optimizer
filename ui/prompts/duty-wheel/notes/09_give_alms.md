# 9 · Give Alms

One block = one image request. Copy a block, paste it on its own, generate, save.

Two actions: **Give Alms** on the left, **Donate a building** on the right.

## Version A — engraved plate

Save as **`09_give_alms_A.png`**

```
Nineteenth-century steel-engraving style, dense cross-hatching, sepia and warm grey ink on aged paper. Fourteenth-century English setting. Even, neutral illumination across the whole frame - no dramatic side-light, no glow, no spotlight, no vignette. Overall tonal value light to middle, as a book illustration printed on cream paper: most of the picture in light and middle tones, with dark ink reserved for accents and never covering large areas. High detail but bold, readable forms.

Two scenes side by side, each occupying exactly half of a square frame.
Left (Give Alms): A donor placing coins and a loaf into the hands of the poor at an abbey gate.
Right (Donate a building): A patron presenting a small chapel or almshouse to a robed abbot.

The two halves meet directly, edge to edge, with no dividing line, no rule, no border, no gutter and no gap of any kind between them. The transition is loose and organic - the change of place happens across a band of picture rather than along a straight edge. Each scene occupies exactly half the width, so the change of place falls at the centre of the square. Each half is tall and narrow: give each scene a single figure or one close action, seen near full height.

Square 1:1. Full bleed to all four edges - no border, no frame, no parchment margin, no torn edge, no caption or text of any kind. Keep the outer 6 per cent of the picture clear of anything important.
```

## Version B — grim dark Gothic

Save as **`09_give_alms_B.png`**

```
Fourteenth-century England in a grim, oppressive register. Heavy gothic architecture crowding the frame, weather-stained stone, bare branches, crows, guttering candles, faces gaunt and weary. Dense engraved cross-hatching in cold iron-grey and black ink, bitten deep. Overcast and joyless. Even illumination across the whole frame - no spotlight, no glow, no vignette - but a low, sunless key throughout. Blacks rich and detailed, never flat or blocked up; the cross-hatching must stay separable everywhere, with no solid black masses. High detail, bold readable silhouettes.

Two scenes side by side, each occupying exactly half of a square frame.
Left (Give Alms): Bread handed down to a press of starving hands at the abbey gate, arms reaching up out of the dark.
Right (Donate a building): A well-fed patron gesturing at a new almshouse while a clerk records the gift, the poor waiting outside in the rain.

The two halves meet directly, edge to edge, with no dividing line, no rule, no border, no gutter and no gap of any kind between them. The transition is loose and organic - the change of place happens across a band of picture rather than along a straight edge. Each scene occupies exactly half the width, so the change of place falls at the centre of the square. Each half is tall and narrow: give each scene a single figure or one close action, seen near full height.

Square 1:1. Full bleed to all four edges - no border, no frame, no parchment margin, no torn edge, no caption or text of any kind. Keep the outer 6 per cent of the picture clear of anything important.
```

---

## After generating

```
python3 check_tile.py 09_give_alms_A.png --version A
```

It reports the join position, whether a rule got drawn, and the tonal key. If the join is off centre, do not regenerate — send me the number and I move the gradient.
