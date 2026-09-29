# Layout Lab V4.1 brief — final pre-commit fixes

Kept for the same reason as the earlier briefs: it records what was asked for and what was left
to judgement. Verbatim, apart from this header.

Note on the V4 brief itself: it is **not** in this tree. It was given in a conversation whose
history was compacted before the brief could be filed, and reconstructing it from the
implementation would produce a document that agrees with the code by construction — which is the
one thing a brief must not do. The V3 brief plus this one bracket the change; the V4 design as
built is described in `../layout_lab/README.md`.

---

FINAL PRE-COMMIT FIXES FOR `duty-border-studio` / DUTY WHEEL LAYOUT LAB

This is a SMALL CORRECTIVE UPDATE to the current V4 implementation.

Do NOT redesign the layout.

The current composition is accepted:

- canvas 1400 × 1200
- built-in SVG Duty Wheel
- wheel default x=14, y=438, width=1372, height=727
- 32° projected ratio ≈ 0.5299
- tall 8-card Duty ribbon
- Ready / Sowing / Action Selection states
- two shared scenic action slots
- separate Tithe card
- City / Acolytes-in-Hand shared region
- wheel fixed between all states
- no Duty names/icons/models on the physical wheel yet

Do not change those decisions.

The goal of this update is to fix four remaining implementation inconsistencies
before committing.

======================================================================
1. THE 32° WHEEL LAYOUT RATIO MUST BE AUTHORITATIVE
======================================================================

The built-in wheel is now correct:

viewBox:
1000 × 529.9

ratio:
0.5299

Default layout:

x = 14
y = 438
width = 1372
height = 727

This is the geometry the rest of the composition has been designed around.

IMPORTANT:

Loading another SVG / PNG / WebP wheel asset must NOT silently change the
wheel's layout aspect ratio.

CURRENT INCORRECT BEHAVIOUR:

When a wheel file is loaded, the code reads the asset viewBox / natural ratio,
stores that as `naturalRatio`, then recalculates the wheel height.

That means merely loading another wheel image can:

- change the wheel height
- move its lower edge outside the 1200 px module
- move attached acolytes
- invalidate the composition
- potentially change the intended 32° projection

Remove this behaviour.

----------------------------------------------------------------------
NEW RULE
----------------------------------------------------------------------

The LAYOUT wheel ratio is always:

WHEEL_RATIO = 0.5299

The wheel layout geometry remains the authority.

A loaded wheel asset is ART placed into that existing wheel box.

Loading an asset must NOT change:

- wheel.x
- wheel.y
- wheel.width
- wheel.height
- wheel.naturalRatio
- attached acolyte positions
- u/v anchors

The default 1372 × 727 box therefore stays 1372 × 727 after loading an asset.

----------------------------------------------------------------------
ASSET RATIO VALIDATION
----------------------------------------------------------------------

It is still useful to inspect the incoming file's ratio.

When loading an SVG:

- parse its viewBox ratio

For PNG/WebP:

- inspect its natural pixel ratio

Store/display this as informational metadata if useful, e.g.:

assetRatio

But DO NOT adopt it as the layout ratio.

If:

abs(assetRatio - WHEEL_RATIO) <= 0.005

show something like:

"asset ratio 0.5299 · matches 32° wheel"

If it differs materially:

show a warning:

"asset ratio 0.5624 differs from the 32° wheel ratio 0.5299"

Do not silently reshape the layout.

----------------------------------------------------------------------
RENDERING A MISMATCHED ASSET
----------------------------------------------------------------------

Do not distort an asset merely because its ratio differs.

For externally loaded image assets use:

object-fit: contain

inside the fixed wheel box.

The user can then see that the source does not match the required geometry.

Do not non-uniformly stretch it to fill the box.

The built-in inline SVG already matches the target ratio and should continue to
fill the box normally.

----------------------------------------------------------------------
RESET BEHAVIOUR
----------------------------------------------------------------------

Wheel Reset should mean:

- restore default position
- restore default size
- restore WHEEL_RATIO = 0.5299
- preserve the currently loaded wheel asset if one exists

It should NOT preserve an arbitrary asset-derived layout ratio.

In other words:

reset wheel geometry
≠
reset / remove wheel artwork

Clearing the external wheel asset should return to the built-in SVG.

----------------------------------------------------------------------
STATE IMPORT NORMALISATION
----------------------------------------------------------------------

Older V4 lab sessions may contain:

naturalRatio = some asset-derived value

On apply/import, normalise the wheel to the current design invariant:

S.wheel.naturalRatio = WHEEL_RATIO

and ensure:

S.wheel.height = round(S.wheel.width * WHEEL_RATIO)

unless a future explicit projection feature is introduced.

Do NOT create such a projection feature now.

32° is currently a design invariant.

======================================================================
2. FIX PREVIEW DISMISSAL
======================================================================

The intended Ready / Sowing preview interaction is:

click Duty card
→ open preview

click another Duty card
→ switch preview

click SAME Duty card
→ close preview

click EMPTY BACKGROUND
→ close preview

press Escape
→ close preview

change turn state
→ close preview

CURRENT BUG:

The Clean Preview pointer handler currently closes the preview whenever the
clicked object is anything other than a Duty card.

This means clicking:

- the scenic preview art
- the wheel
- the City
- an acolyte
- another visible UI object

also closes the preview.

That is not intended.

----------------------------------------------------------------------
FIX
----------------------------------------------------------------------

In Clean Preview, only an actual empty-stage click should close the preview.

Conceptually change:

else if (!node || node.dataset.kind !== "card")

to:

else if (!node)

Therefore:

if card && view !== action:
    toggle / change preview

else if no object was clicked:
    close preview

else:
    do nothing

Preview artwork itself is informational and inert.

Clicking it should NOT:
- select an action
- close the preview
- alter the reached Duty

City / wheel / acolytes should likewise not accidentally dismiss it.

======================================================================
3. COMPLETE `export game layout`
======================================================================

The current Game Layout export is too minimal.

It correctly exports the major geometry, but it drops several settings that the
real UI needs in order to reproduce what was designed in the studio.

Keep the principle:

GAME LAYOUT
= production-relevant design configuration

Do NOT export:
- selection
- edit mode
- guides
- ghosts
- zoom
- history
- current previewDuty
- current lab view
- loaded binary image bytes
- locked state

But DO export presentation settings that affect the finished interface.

----------------------------------------------------------------------
STATUS
----------------------------------------------------------------------

Instead of only:

status: {x,y,width,height}

export:

status: {
  x,
  y,
  width,
  height,
  size,
  align,
  opacity,
  visible,
  byView: {
    ready: {main},
    sow: {main},
    action: {main}
  }
}

The game otherwise cannot reproduce the instruction typography or actual text.

----------------------------------------------------------------------
WHEEL
----------------------------------------------------------------------

Export:

wheel: {
  x,
  y,
  width,
  height,
  ratio: WHEEL_RATIO,
  ground,
  opacity
}

Do not export editor-only asset-pool keys.

If the production app already owns the wheel asset separately, keep that
separation.

----------------------------------------------------------------------
DUTY CARDS
----------------------------------------------------------------------

For each Duty export:

card: {
  x,
  y,
  width,
  height,
  visible
}

And retain:

name
actionA.name
actionA.shortLabel
actionB.name
actionB.shortLabel

Do not export lock state.

----------------------------------------------------------------------
ARTWORK SLOTS
----------------------------------------------------------------------

Currently only geometry + slot are exported.

Export:

artwork.left / artwork.right:

{
  x,
  y,
  width,
  height,
  slot,
  fit,
  opacity,
  visible,
  labelVisible,
  labelSize
}

These affect the actual rendered UI and therefore belong in the game layout.

----------------------------------------------------------------------
SELECTED DUTY HIGHLIGHT
----------------------------------------------------------------------

The highlight is currently designed in the studio but not exported.

Add:

highlight: {
  width,
  height,
  dy,
  style,
  visible,
  opacity,
  colour
}

The production UI otherwise cannot recreate the selected-Duty treatment.

----------------------------------------------------------------------
TITHE
----------------------------------------------------------------------

Export:

tithe: {
  x,
  y,
  width,
  height,
  visible,
  label,
  resources: [
    {key, name},
    {key, name},
    {key, name}
  ]
}

Do not encode phase visibility here.

The game knows Tithe appears only during Action Selection.

The export describes WHAT it looks like and WHERE it goes.

----------------------------------------------------------------------
CITY
----------------------------------------------------------------------

Export:

city: {
  x,
  y,
  width,
  height,
  visible,
  label
}

Do NOT export the temporary occupancy test counts as production layout unless
the runtime specifically needs seed/test data.

Counts currently entered in the lab are simulation/test state rather than
layout.

----------------------------------------------------------------------
ACOLYTES
----------------------------------------------------------------------

Keep:

height
ratios

and each Duty's:

x
y
u
v
spacing
arrangement
attached

The test occupancy count and temporary seat configuration do not have to go into
the production layout unless already required elsewhere.

The layout defines where pieces go, not which pieces happen to be there in this
lab session.

======================================================================
4. REMOVE MISLEADING DUTY-CARD HOVER DURING ACTION SELECTION
======================================================================

The current Clean Preview CSS makes Duty cards brighten and show a pointer
cursor on hover.

But in ACTION SELECTION, clicking another Duty card intentionally does nothing.

That creates a false affordance:

hover says:
"click me"

click says:
"nothing happens"

Fix this.

----------------------------------------------------------------------
READY / SOWING
----------------------------------------------------------------------

Duty cards are previewable.

They SHOULD have:

- subtle hover brightness
- pointer cursor

because clicking them opens a reference preview.

----------------------------------------------------------------------
ACTION SELECTION
----------------------------------------------------------------------

Duty cards are static reference information.

The reached Duty is highlighted.

Other Duty cards should NOT advertise clickability.

Use one of these approaches:

Preferred:

During render, add a class such as:

previewable

only when:

S.view !== "action"

Then use:

body.clean .card.previewable:hover {
    filter: brightness(...);
    cursor: pointer;
}

Do not apply pointer/hover treatment to cards in Action Selection.

Do not change the reached-card highlight.

======================================================================
5. VERSION / COMPATIBILITY
======================================================================

Keep:

STATE_VERSION = 4

The lab-state schema is still fundamentally V4.

Do NOT bump STATE_VERSION merely for these corrections, because the current
migration logic treats older versions as needing the V3 → V4 geometry rewrite.

Instead change:

BUILD_VERSION = "4.1"

or similar.

Keep existing V4 Lab Sessions importable.

Because the 32° wheel ratio is now an invariant, normalise imported V4 wheel
geometry as described above rather than creating a V5 migration.

======================================================================
6. DO NOT CHANGE THESE THINGS
======================================================================

Do NOT:

- redesign the wheel
- change the embedded SVG paths
- add Duty names to wheel spaces
- add Duty icons to the wheel
- add 3D Duty models
- change the 1400 × 1200 canvas
- change the 8-card ribbon layout
- change the City / in-hand dual use
- move Tithe
- add "OR"
- put anything back into the wheel centre
- introduce per-state wheel geometry
- shrink the wheel

Those are settled for this commit.

======================================================================
7. ACCEPTANCE TESTS
======================================================================

Before commit, verify all of the following.

TEST 1 — DEFAULT WHEEL

Fresh/reset lab:

wheel:
x = 14
y = 438
w = 1372
h = 727

ratio ≈ 0.5299

bottom = 1165

No out-of-bounds warning.

----------------------------------------------------------------------
TEST 2 — BUILT-IN SVG

Built-in SVG renders at:

1000 × 529.9 logical ratio

No distortion.

Its optional ground rectangle can still be toggled.

----------------------------------------------------------------------
TEST 3 — LOAD MATCHING SVG

Load an SVG with ratio ~0.5299.

Wheel geometry does NOT change.

Acolyte anchors do NOT move.

Tool reports that the asset ratio matches.

----------------------------------------------------------------------
TEST 4 — LOAD WRONG-RATIO SVG

Load a deliberately wrong-ratio SVG, e.g. 1000 × 562.

Wheel remains:

1372 × 727

Tool warns that the asset does not match the 32° ratio.

Asset is contained rather than stretched.

Acolytes do not move.

----------------------------------------------------------------------
TEST 5 — RESET WHEEL WITH EXTERNAL ASSET LOADED

Move / resize wheel.

Press wheel reset.

Result:

x=14
y=438
w=1372
h=727

External artwork remains loaded.

Ratio returns/remains 0.5299.

----------------------------------------------------------------------
TEST 6 — READY PREVIEW

Clean Preview → READY.

Click Clerical.

Clerical's two artworks appear with PREVIEW badge.

Click artwork itself.

Preview stays open.

Click wheel.

Preview stays open.

Click City.

Preview stays open.

Click empty black background.

Preview closes.

----------------------------------------------------------------------
TEST 7 — SAME / DIFFERENT CARD

Open Clerical preview.

Click Clerical again:
preview closes.

Open Clerical again.

Click Produce:
preview immediately switches to Produce.

----------------------------------------------------------------------
TEST 8 — SOWING

Same preview behaviour as READY.

City region continues to show Acolytes in Hand.

Preview does not interfere with the in-hand count.

----------------------------------------------------------------------
TEST 9 — ACTION SELECTION

Reached Duty artwork appears automatically.

Tithe appears.

Reached card is highlighted.

Cards no longer show misleading pointer/preview hover behaviour.

Changing state closes any previous preview.

----------------------------------------------------------------------
TEST 10 — GAME LAYOUT EXPORT

Export JSON and verify it contains:

- complete status presentation + byView text
- wheel geometry + ratio / ground / opacity
- Duty card geometry + visibility
- action wording
- artwork fit / opacity / captions
- selected-Duty highlight settings
- Tithe label + resource definitions
- City label + geometry
- acolyte sizing / anchors

And does NOT contain:

- editor selection
- guides
- ghosts
- zoom
- undo history
- previewDuty
- lab image byte pool
- lock flags

======================================================================
COMMIT CONDITION
======================================================================

After these four fixes pass the acceptance tests, the V4 layout tool is ready
to commit.

Duty-space identification on the physical wheel remains intentionally deferred.
