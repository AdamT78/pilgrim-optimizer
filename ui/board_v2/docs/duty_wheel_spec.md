# Duty Wheel UI Specification

## 1. Purpose

This document defines the current design direction for the **Duty Wheel** module in *Pilgrim*.

The module is a self-contained gameplay UI that combines:

- the eight Duty spaces,
- scenic artwork associated with each Duty,
- acolytes currently occupying Duty spaces,
- the City reserve,
- and the temporary pool of acolytes currently "in hand" while being sowed.

The goal is to preserve the strong miniature-board-game presentation while keeping the underlying game state immediately readable.

This document covers the visual and interaction model only. It does **not** define the rest of the game board, player boards, resource panels, or other surrounding UI.

---

## 2. Fixed Design Envelope

The complete Duty Wheel module must fit inside a fixed:

**1200 × 1200 px design area**

This same 1200 × 1200 module should be reusable unchanged in both supported full-board canvases:

- **2039 × 1200**
- **2283 × 1200** widescreen

The Duty Wheel module should therefore be designed as an independent square composition rather than being resized differently for the two full-board widths.

The 1200 × 1200 envelope contains all of the following:

- stone Duty Wheel,
- eight Duty spaces,
- all scenic Duty artwork,
- Duty labels,
- acolyte figures on Duty spaces,
- City reserve,
- temporary "in hand" / sowing display,
- visual selection and hover effects.

Nothing essential should depend on drawing outside the 1200 × 1200 boundary.

---

## 3. Core Structure

### 3.1 Eight Duties on one wheel

The wheel contains exactly eight Duty spaces:

1. Allocation
2. Build Roads
3. Clerical
4. Construct
5. Give Alms
6. Ordination
7. Produce
8. Taxation

These eight spaces form the functional ring of the wheel.

The wheel should read as **one coherent gameplay object**, not as eight independent cards.

Each Duty space must support visible acolyte occupancy.

### 3.2 The City is not a ninth Duty

The City is mechanically different and must be visually separated from the Duty ring.

The City:

- has **no Duty actions**,
- has **no tithe resource**,
- is **never visited by the merchant**,
- can contain substantially more acolytes than a normal Duty space,
- acts as a reserve / holding area for acolytes.

The City should therefore **not** be placed as a ninth wheel segment and should **not** occupy the centre of the wheel as if it were another Duty.

Instead, the City should be placed as a separate but visually related element, preferably centered beneath the wheel within the same 1200 × 1200 composition.

---

## 4. Wheel Geometry

The wheel artwork will be prepared separately as an SVG using the intended **32° elevated board-view appearance**.

The 32° projection is part of the wheel asset itself.

The layout system should treat the transformed wheel as a finished visual asset and should only change:

- X position,
- Y position,
- uniform scale,
- opacity when needed for layout work.

The layout process must **not** independently squash, stretch, or re-project the wheel.

A useful initial design target is a wheel around **740–800 px wide**, but this is a starting point rather than a fixed production dimension.

The wheel should sit slightly above the vertical centre of the 1200 × 1200 area so that the City can fit naturally beneath it without feeling detached.

---

## 5. Duty Spaces and Acolyte Figures

Each Duty space is part of the stone wheel.

Acolyte figures should stand on the actual Duty space rather than inside the scenic artwork.

The Duty space must remain the clear functional surface.

Each Duty should be designed to remain readable with approximately:

- 1 acolyte,
- 2 acolytes,
- 3 acolytes,
- 4 acolytes.

The crowded state matters more than the empty state when evaluating spacing.

Acolytes should remain visually distinct enough for the player to read occupancy and player ownership quickly.

The scenic artwork must never make the figures difficult to see.

---

## 6. Scenic Duty Artwork

### 6.1 Purpose

Each of the eight Duties has associated scenic artwork.

The scenic artwork exists to:

- reinforce theme,
- help distinguish Duties,
- add atmosphere,
- make each Duty recognizable at a glance.

It is **supporting artwork**, not the primary interaction surface.

### 6.2 Placement

Scenic artwork should live primarily **outside the wheel**, aligned with the corresponding Duty.

It may overlap slightly behind the wheel so the composition feels integrated rather than like eight separate pictures orbiting the wheel.

Artwork should be allowed to fade naturally into the dark background.

No visible rectangular frame is required around the scenic artwork.

### 6.3 Visual hierarchy

The intended visual hierarchy is:

1. wheel as one coherent system,
2. Duty spaces,
3. acolytes occupying those spaces,
4. Duty labels,
5. scenic artwork.

The scenic art must not overpower the wheel or make the layout feel like a 3 × 3 card grid.

### 6.4 Independent artwork regions

The eight scenic regions do not need identical dimensions.

Different scenes may benefit from different proportions, for example:

- a chapel may be taller,
- a road scene may be wider,
- a treasury scene may be compact.

Consistency should come from **visual weight and placement**, not necessarily from identical bounding-box sizes.

A useful placeholder starting size for layout testing is approximately **220 × 180 px** per scenic region, with individual adjustment allowed.

### 6.5 Overlap

The scenic artwork may extend partially behind the wheel edge.

The exact overlap should be determined visually during prototyping.

The art must never obscure critical Duty occupancy information.

---

## 7. Duty Labels

Each Duty should remain explicitly named.

Duty labels should feel visually attached to the wheel rather than floating as independent UI cards.

The preferred direction is a small parchment tab, cartouche, or similarly compact label positioned near the corresponding Duty.

All labels should be consistent in visual treatment and subordinate to the wheel itself.

The City label should be visually distinct from the Duty labels because the City is not a Duty.

---

## 8. City Reserve

### 8.1 Placement

The City should be a compact reserve positioned **outside the wheel**, preferably centered below it.

It should feel visually connected to the wheel composition but clearly different from a Duty space.

Possible visual language includes:

- a small cobbled forecourt,
- a city gate,
- a paved reserve area,
- another restrained architectural treatment.

The City should not require a large circular platform.

### 8.2 Why the City should not show all figures

The City may hold many more acolytes than a normal Duty.

Rendering every City acolyte as a separate miniature would force the City to become disproportionately large and visually dominant.

Therefore the City should use an **aggregated representation**.

### 8.3 Representation

For each player who has acolytes in the City, show:

**one representative acolyte miniature + count**

Examples:

- green acolyte ×5
- blue acolyte ×3
- red acolyte ×1

Use the same representation even when the count is one.

This keeps the visual language stable and prevents the City from constantly changing between individual and aggregated display modes.

A maximum of one representative miniature per player is shown in the City reserve.

---

## 9. Acolytes "In Hand" During Sowing

### 9.1 Purpose

When acolytes have been picked up and are about to be sowed, the player must always be able to see:

- which acolytes are currently being distributed,
- how many remain to be placed.

### 9.2 Centre of the wheel

The centre of the wheel should be used as the temporary **in-hand / sowing pool**.

In the normal idle state, the centre can remain decorative.

Possible idle treatments include:

- carved stone,
- pilgrimage emblem,
- subtle architectural motif,
- restrained central medallion.

When sowing begins, this centre temporarily becomes active UI.

### 9.3 Representation

Do not show every picked-up acolyte individually.

Show:

**one representative acolyte miniature + a prominent remaining count**

For example:

- miniature + `×6`
- or miniature + `6 LEFT`

As sowing proceeds, the count decreases:

`6 → 5 → 4 → 3 → 2 → 1 → empty`

When an acolyte is placed on a Duty, the destination gains the figure and the centre count decreases at the same time.

### 9.4 Multiple player colours

If a sowing pool can contain more than one player colour, the centre may show one compact representative entry per colour, for example:

- green ×3
- blue ×2
- red ×1

If sowing order depends on colour, the currently active / next acolyte can be emphasized while the remaining colours stay secondary.

### 9.5 Visual distinction from the City

The City and the in-hand pool must not look like the same type of storage.

- **City** = persistent reserve outside the wheel.
- **In hand** = temporary active state in the centre of the wheel.

The in-hand state should therefore use a more temporary treatment, such as a subtle illuminated ring or active highlight.

---

## 10. Interaction States

### 10.1 Idle

- all Duties readable,
- scenic artwork visible but restrained,
- City reserve visible,
- centre remains decorative when no sowing is occurring.

### 10.2 Hover

When hovering or otherwise focusing a Duty:

- Duty segment may brighten slightly,
- nearby scenic artwork may brighten slightly,
- label may gain contrast,
- figures should remain readable.

Hover effects are enhancements only; essential interaction should not depend on hover.

### 10.3 Selected Duty

For a selected Duty:

- the segment may receive a stronger highlight,
- scenic art may become slightly brighter,
- non-selected areas may dim subtly,
- the state should remain readable without excessive glow or animation.

### 10.4 Sowing

During sowing:

- centre shows representative acolyte + remaining count,
- valid next Duty destination(s) should be visually clear,
- placing one acolyte decrements the centre count,
- the destination Duty updates immediately.

### 10.5 City movement

When appropriate, an acolyte returning to or leaving the City may be animated between the wheel and the City reserve.

The persistent City display remains aggregated as one representative miniature per player plus count.

---

## 11. Layering / Z-Order

A practical default layer order is:

1. dark module background,
2. scenic Duty artwork,
3. wheel SVG,
4. Duty figures,
5. Duty labels,
6. City reserve,
7. City representative figures and counts,
8. centre in-hand display,
9. hover / selection effects,
10. layout/debug overlays in development mode only.

Some scenic art may visually overlap behind the wheel by design.

---

## 12. Layout Principles

The composition should prioritize:

- one strong central wheel,
- clear occupancy,
- restrained but recognizable scenic art,
- a compact City reserve,
- an immediately readable sowing counter,
- enough negative space to prevent visual clutter.

The final layout should not resemble a 3 × 3 grid of independent illustrated Duty cards.

The wheel must remain the dominant organizing object.

---

## 13. Prototype / Layout-Lab Requirements

Before finalizing all Duty artwork, use a 1200 × 1200 layout prototype to determine:

- final wheel scale,
- wheel X/Y position,
- individual scenic-art bounding boxes,
- scenic overlap with the wheel,
- City size and location,
- centre in-hand display size,
- crowded figure states,
- label placement.

The layout should be tested with:

- 4 acolytes on individual Duties,
- high City counts,
- active sowing state,
- both sparse and crowded configurations.

The prototype should support exact pixel values so the chosen layout can later be reproduced in the game UI.

---

## 14. Current Recommended Starting Values

These are prototype defaults, not hard production constraints:

| Element | Starting value |
|---|---:|
| Design envelope | 1200 × 1200 px |
| Wheel width | 740–800 px |
| Scenic-art region | ~220 × 180 px each |
| City width | ~220–300 px |
| Centre in-hand region | ~130–170 px |
| Outer safety margin | ~40–60 px |

The final values should be decided from the interactive layout prototype.

---

## 15. Non-Goals

This specification does not currently define:

- player boards,
- resource tracks outside the wheel,
- merchant UI outside the Duty module,
- complete full-board composition,
- final generated artwork for all Duties,
- final animation timing,
- responsive scaling rules for the full application.

Those can be designed after the Duty Wheel module itself is spatially resolved.
