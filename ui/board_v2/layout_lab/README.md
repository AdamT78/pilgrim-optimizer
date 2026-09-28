# Duty Wheel Layout Lab

An interactive page for deciding the geometry of the Duty Wheel module — how big the wheel is,
what the player reads before choosing, how the two action artworks sit above the wheel, where the
City goes, and whether four realistically sized acolytes still read on one duty — and then handing
back the exact coordinates.

**V4** is the current build, and it changes the layout concept rather than the dimensions. The
module is still 1400 × 1200, but the wheel now takes nearly all of it, the eight duty summaries
have become a ribbon of reference cards across the top, and there are **three** presentation
states rather than two. Build **4.1** corrects four things without changing any of those shapes:
a loaded wheel asset no longer reshapes the layout, a preview is dismissed only by an empty-stage
click, the Game Layout export carries the presentation settings the real UI needs, and the duty
cards stop advertising a click in ACTION SELECTION where none does anything. See *The wheel itself*, *Why the wheel takes the module* and *The three
view states* below. A V1, V2 or V3 layout still opens; see *Opening an older file*.

The wheel is no longer a stand-in. The page draws the **v2 duty wheel at an aspect of 1.887** —
the real vector geometry, nine faces on a true ellipse — recoloured into the slate the old
placeholder wore, so the composition is judged against the drawing rather than against an
approximation of it.

It decides nothing on its own. Everything it produces is a layout JSON in true 1400 × 1200 design
coordinates, for the game UI to be built from later.

## Running it

```
python3 ui/board_v2/layout_lab/generate_layout_lab.py           # write the page
python3 ui/board_v2/layout_lab/generate_layout_lab.py --open    # write it and open it
```

`--open` hands the file to your default browser and prints the URL either way, because
`webbrowser.open` reports failure by returning False and on some machines returns True having
done nothing. The page is written regardless, and the exit code does not depend on whether a
browser was found.

The page is written to `ui/board_v2/layout_lab/generated/duty_wheel_layout_lab.html`, which is
git-ignored — `ui/.gitignore` ignores every `generated/` under `ui/`, so the script and the
template are the source and the page is output. Open it by double-clicking. It needs no server,
no build step and no network: everything it draws is in the file, and it has been checked with
every outbound request blocked.

## The wheel itself

The page draws the **v2 duty wheel at an aspect of 1.887** — a hub and eight spokes built as
vector geometry by `build_duty_wheel_v2.py`, mirrored about both axes so the symmetry is exact,
with every face inset by half the frame along each edge. Nothing is traced.

**1.887 is a different drawing, not the 1.778 one squashed.** The faces are built from the
ellipse and the spokes and the hub is held as a proportion of the rim, so changing the aspect
rebuilds the geometry. The 1.778 baseline in `tools/ui_debug/prototypes/` is untouched and still
belongs to that tool; the 1.887 layout sits beside it as
`tools/ui_debug/duty_wheel_v2_1887_layout.json`, regenerable like every other layout there.

**It is a copy, not an import.** The drawing is vendored at
`ui/board_v2/layout_lab/assets/duty_wheel_v2.svg` and read as bytes at build time; this tool
imports nothing from `tools/ui_debug` and never reads out of that tree at runtime. The builder
over there parses argv at import time, needs numpy, and says in its own header that the aspect is
not settled — none of which should have to be true for this page to generate. To refresh the copy
after the geometry moves:

```
python3 tools/ui_debug/build_duty_wheel_v2.py --aspect 1.887 \
    --out duty_wheel_v2_1887_layout.json
python3 - <<'EOF'
import pathlib, sys; sys.path.insert(0, ".")
from tools.ui_debug.render_duty_wheel_v2 import (
    load_duty_wheel_v2_layout, render_duty_wheel_v2_svg)
lay = load_duty_wheel_v2_layout(pathlib.Path("tools/ui_debug/duty_wheel_v2_1887_layout.json"))
pathlib.Path("ui/board_v2/layout_lab/assets/duty_wheel_v2.svg").write_text(
    render_duty_wheel_v2_svg(lay, standalone=True), encoding="utf-8")
EOF
```

**The checked-in copy keeps the builder's own colours and the recolour happens at build time.**
Hand-editing a generated file is how a file stops being regenerable, which is the one rule that
tool's header insists on — so the drawing arrives in parchment and this generator converts it,
failing loudly if any colour in its palette no longer matches the drawing. A palette that
silently stopped applying would leave a cream wheel on a black field with nothing to say so.

| the drawing | the lab | |
|---|---|---|
| `#efe3c8` | `#3a3d45` | the faces, in the placeholder's slate |
| `#e8dcc0` | `#23262b` | the hub, darker |
| `#17130d` | `#2b2e34` | the ground, hidden by default |

The greys are the ones the old stand-in wore, which is what keeps every judgement made against
it — acolyte contrast, the reached-duty mark, how much the artwork above can carry — still worth
something.

**Its faces are named by position, never by duty** — `north_west`, `north`, `centre` — for the
same reason the builder gives: duty tiles are shuffled at setup, so a duty's space is an
arrangement and not a fact. The drawing carries no text at all, which is what keeps it consistent
with V4 identifying nothing on the wheel.

**The asset carries its own ground**, a dark rectangle filling its whole viewBox with five units
of bare board outside the ellipse. The lab hides it by default: inside a layout module that
rectangle states the board's colour for the wheel's bounding box and nowhere else, which is not a
shape the real board has. *asset ground on* in the wheel inspector shows it, and **preview
background** is where the board's colour actually belongs.

## Why the wheel takes the module

V2's module was 1200 square. V3 widened it to 1400 × 1200 and spent the two hundred new pixels on
**margins**, because four compact duty summaries stood in each one.

V4 inverts that. The summaries left the margins for a ribbon across the top, and with nothing to
put beside the wheel any more, the space went to the wheel: it opens **1372 × 727**, covering
about 59% of the module. That is the point of the redesign. The wheel is the board, and everything
else is a thin band of information above it.

**Its shape is the asset's and its size follows from that.** The drawing's `viewBox` is
1000 × 529.9 — an aspect of 1.887 — so the ratio is read from the file rather than derived from a
number this tool picked. The elevation that implies is 32.0°, which is what the old placeholder
was drawn at; the two agreeing is a coincidence rather than the reason, and the derivation runs
ratio first, elevation after.

**The wheel takes whichever ceiling binds.** There are two — the module's width less a margin
each side, and the height left under the action band — and which one bites depends entirely on
the drawing, so both are computed and the smaller wins. At 1.887 the width runs out first: 1372
wide is 727 high and finishes at 1165, leaving 35 px of module under it that nothing is reserved
for. At 1.778 it was the other way round, and the wheel came out 1354 × 761 with wider margins.
Both are right for their drawing, which is the point of deriving it rather than writing the
numbers down.

Inside a full board the module still leaves 639 px beside it on 2039 × 1200 and 883 px on
2283 × 1200, which is the number the side panel reports while you compose. 1600 × 1200 stays off
the list: a 1400 module inside it leaves 200 px for the entire rest of the board.

## The three view states

The toolbar switches between them — or press **1**, **2** and **3**, which is the fastest way to
see what actually differs.

**READY / CITY.** The board at rest. The wheel with its acolytes, the eight reference cards, the
instruction, and the City showing what each player has in reserve. Nothing is being chosen.

**SOWING.** Identical, except that the City's region becomes **ACOLYTES IN HAND** — one figure
carrying the number still to place — and the instruction counts down with it. The count is
substituted into the sentence from the same number the figure draws, so the two cannot disagree.

**ACTION SELECTION.** The band above the wheel fills with the reached duty's two scenic artworks
and **TAKE TITHE** beside them, the reached duty's card is marked, and a soft highlight appears at
that duty's place on the wheel.

**The wheel does not move or resize between them.** Not by a pixel: nothing in the page writes
wheel geometry per state, and neither does the City, the ribbon or the acolyte ring. Only the
band's contents change. That is what makes the three compositions comparable rather than merely
similar, and it is the reason flipping between them with 1, 2 and 3 is worth doing repeatedly.

In Edit Mode the stage shows the state you are in, so what you compose is what you will see.
**show ghosts** in the *view* panel puts another state's objects back faintly so they can be
positioned without leaving this one; ghosts are editing chrome and never appear in Clean Preview.

## Previewing a duty

The eight reference cards are **reference, not choices**. In READY and SOWING, clicking one opens
that duty's two artworks in the band, each badged **PREVIEW**. Clicking another card switches to
it; clicking the same card again, or anywhere off a card, closes it.

A preview is deliberately not dressed as a choice. The same two boxes are used for reading about a
duty and for choosing one of its actions, so the preview gets a badge and does not get the choice
treatment, and **Tithe never appears in a preview** — it is the alternative to taking what a duty
offers, not something a duty offers, so it has no business on screen while you are still reading.

**Escape closes a preview** too, which is the reflex most people already have for "put that away".

**Clicking the preview itself does nothing**, and nor does clicking the wheel, the City or an
acolyte. Only a click that lands on empty stage closes it. A preview is something you are reading,
and clicking the thing you are reading is not a request to put it away — an earlier build dismissed
on anything that was not a card, so the artwork vanished the moment you touched it.

In ACTION SELECTION the cards stop previewing entirely: the artwork shows the duty the sow
reached, which nobody had to ask for. Changing state closes any open preview.

## The turn instruction

A reserved band across the top, above the ribbon. **One line**, on the dark field, with no
parchment panel and no frame, because a heavy header would compete with the wheel for the one
thing the wheel is meant to have.

It is **one area with three messages**: the geometry and the styling are shared, but what it says
is per view state. The panel offers one field per state, generated from the list of states rather
than written out one at a time, so a field and its handler cannot disagree about which state they
belong to — which is exactly how V3.1 managed to read one state's text into another's box.

V3 carried a second, smaller context line above the instruction (a `SOW` or `CLERICAL` strap).
V4 removes it: the instruction is already unambiguous, and the strap was a second place where the
same fact could be stated and go stale.

The sow line carries `{n}`, replaced by the acolytes in hand. Typing a digit there instead is how
an instruction ends up disagreeing with the figure beside it.

**Resetting the band** puts the box, the type size, the alignment and the lock back to their
defaults and **keeps all three messages**. Retyping three sentences is not what anyone means by
putting a box back where it started.

The panel reports whether the instruction fits on one line at the current width and size, measured
rather than guessed.

## The ribbon of reference cards

Eight cards in one row across the top, in the **wheel's own order** — clerical at 12 o'clock, then
clockwise — so reading left to right is reading round the ring rather than down an arbitrary list.
They are evenly pitched and fill the ribbon's width exactly. Nothing in the page knows or cares
which half of the row a duty is in; V3's left/right split is gone with the margins.

Each card shows the duty name and, per action, a wax seal and a short planning label. Load a
transparent PNG, WebP or SVG seal per action in the *duty actions* panel; without one there is a
circular seal placeholder carrying **A** or **B**, so the cards stay readable before any final art
exists.

Action names and short labels are editable there too. The known wording is filled in — Gain Piety,
Gain Coins, Relocate Acolytes, Ordain, Send on Mission and so on — and **Taxation is deliberately
left as "Action A" and "Action B"**, because that wording is not decided and a plausible invented
placeholder is exactly the kind that survives into production unnoticed.

The cards are on screen in **every** state. A reference you have to summon is a reference you
stop using.

**They only look clickable where a click does something.** In READY and SOWING a card brightens
under the cursor and takes a pointer, because clicking it opens a preview. In ACTION SELECTION
they are static reference — the duty has been reached and clicking another card is meant to do
nothing — so the treatment goes with it. A card that brightens and then ignores the click is the
interface making a promise it does not keep.

## The two artwork slots

An action owns its **assets** — a name, a short label, a wax seal, a scenic image — and owns no box
at all. Two global display slots own the **geometry**, and whichever duty is being shown lends them
its two pictures. Two boxes for sixteen pictures, so a production layout never carries sixteen
large geometries that are never all used at once.

They open **375 × 184** side by side at the left of the action band — landscape, because that is
the shape a scenic illustration of a place wants and because the band is wide and shallow. V3's
slots were tall columns in the side margins overlapping the wheel's rim; V4's stand clear of the
wheel entirely. An image over the rim would cover the acolytes standing on the top of the wheel,
which is the part of the board a player reads while they choose.

Each slot has a caption showing its action's name, with its own size and visibility. Where no
scenic image is loaded, the slot shows a placeholder naming the action.

**No scenic artwork goes above the ribbon or below the wheel.** The band above is turn information
and the wheel runs to the bottom of the module. This is a design constraint rather than an accident
of the defaults, and the test suite enforces it.

## Tithe

The third choice during action selection, alongside the two duty actions — and deliberately not a
third large card. It sits in the action band to the right of the two artworks, a compact panel
carrying **TAKE TITHE** and the three resources as a 1-over-2 pyramid, with an optional seal image.

It appears in **ACTION SELECTION only**, and never in a preview.

V3.1 put Tithe in the centre of the wheel, sharing that medallion with the in-hand counter. V4
empties the centre: both left for the action band, where the decision is actually being made. What
is gained is a quiet middle — the wheel now reads as a board rather than as a frame around a
medallion, and a wheel asset with art of its own in the middle is no longer competing with the
layout.

## The reached-duty highlight

A soft mark or a thin ring at the reached duty's own anchor, in ACTION SELECTION only, sized and
positioned in the *artwork* panel. Before anything has been reached there is nothing to highlight,
and a highlight then would be claiming otherwise.

**Whether it can be seen is measured, not assumed.** This has been got wrong twice in opposite
directions: pale gold is right on slate and drops to a contrast ratio of 1.06 against the
drawing's cream parchment; deep oxblood fixes that and drops to 1.12 once the lab's palette turns
the faces slate again. Both times the mark was correctly sized, correctly placed and invisible.
So the acceptance run composites the highlight over the face's own fill at its own opacity and
fails below 1.5. The default — pale gold at 50% — measures 1.95 on slate.

It is drawn **above the wheel and below the acolytes**: above, or the wheel covers it entirely (the
first V4 build had it at z 19 against a wheel at 20, so it was composed correctly, positioned
correctly and invisible); below, because it marks the space the figures are standing on and a glow
over them would hide the thing it is pointing at.

**It never touches the imported wheel asset.** The final SVG may not expose its segments as
separate elements, and recolouring somebody's artwork from inside a layout tool is not this page's
business. The overlay exists to answer one question: can the reached duty be made obvious?

## Nothing identifies a duty space on the wheel

How the eight physical spaces get marked out — engraved names, 3D landmarks, emblems, plaques — is
a separate decision the brief explicitly keeps for later. So the wheel carries the acolytes
standing on it and nothing else, and the duty's name lives in its ribbon card.

V3 had a hideable parchment label per duty for exactly this job. It is **gone rather than hidden**:
a hidden object is one checkbox away from being back, and a default that can be flipped is not an
absence.

## Loading a different wheel

The built-in drawing can be replaced with any other. Select the wheel on the stage and use the
file input in the inspector; *clear svg* puts the built-in one back.

**A loaded file is art placed into the existing box.** It does not change the wheel's position,
its size, its ratio or where the acolytes stand. That is the opposite of how it first worked, and
the reason is what the old behaviour actually did: adopting the file's ratio and recomputing the
height meant that *loading a picture* was a layout edit. The wheel grew or shrank, its lower edge
could leave the 1200 px module, every attached acolyte moved with it, and the 32° projection the
whole composition is built on quietly became whatever the file happened to be — with nothing on
screen saying so.

The file's own shape is still read, because it is worth knowing. It is reported rather than
adopted: *asset ratio 0.5299 · matches the 32° wheel*, or a warning that it differs, with the
numbers. A file within 0.005 of the layout ratio counts as matching — about 7 px of height on a
1372 px wheel, which is rounding rather than a different projection.

**A mismatched asset is contained, never stretched.** Filling the box would hide the very thing
the warning is about; drawn at its own proportions inside the box, the mismatch is visible.

**The page never re-projects it.** Loading an SVG adopts that asset's own aspect ratio — read from
its `viewBox`, which is the authority, with the browser's measurement only as a fallback — and from
then on only position and uniform scale can change. The resize handles are corners only and the
width and height fields drive each other. The built-in wheel is treated exactly the same way: its
ratio is read from its own `viewBox` and stored as the asset's, not as the rounded ratio of the
box it happens to open at, so rescaling cannot compound a rounding error into a re-projection.

A responsive SVG — `width="100%" height="100%"`, which is what a drawing exported for a board
usually looks like — reports a natural size of 300 × 150 to a browser, a ratio of 0.5. That is
close enough to sin(32°) = 0.53 to look entirely plausible while being wrong, which is why the
`viewBox` is parsed rather than trusted to the layout engine.

**Resetting the wheel is about the box, not the artwork.** Position, size and the 0.5299 layout
ratio all go back to the defaults; a loaded asset stays loaded, because it is art in that box and
has no say in its shape. An earlier build preserved an asset-derived ratio through a reset, which
meant a reset could leave the wheel at somebody else's projection.

**An older session is normalised, not migrated.** A V4 file written before this correction may
carry a ratio taken from whatever asset was loaded at the time. On import the wheel is put back to
0.5299 and its height re-derived from its width, so it lands inside the module. The schema is
unchanged and the session still opens: `STATE_VERSION` stays at 4 and only the build label moves,
because bumping the schema would send every existing V4 session through the V3 → V4 migration,
which drops geometry on purpose.

## Edit Mode and Clean Preview

The toggle is top left.

- **Edit Mode** — bounding boxes, resize handles, object names, anchor markers, boundary
  warnings, guides, the selection ring and the inspector.
- **Clean Preview** — the composition alone, **for the state you are in**, and the cards become
  clickable for previewing. Every piece of editing chrome goes, including the ghosts, the boundary
  warnings and the selection ring on whatever happened to be selected.

In Edit Mode clicking an object selects it. The inspector shows the controls that apply to it,
numeric edits take effect immediately, and dragging updates the numbers immediately. Arrow keys
nudge the selection by 1px, Shift+arrow by 10px, and neither does anything while a field has the
caret.

**1, 2 and 3 switch view state**, and are ignored while a field has the caret.

**F is full screen.** The toolbar and the inspector go, and the stage takes the whole window on
a black field — Clean Preview with nothing around it, which is how the composition is worth
judging. F again brings everything back, and so does Escape: the page hangs the change off the
browser's `fullscreenchange` rather than off the keypress, because Escape leaves full screen
without the page hearing a key and a page that toggled itself would be stranded with its chrome
hidden. Like the arrow keys, F does nothing while a field has the caret. If a browser refuses
full screen outright, the chrome is hidden anyway and the status line says so.

## The two kinds of file

These answer to two different readers and are deliberately not the same thing.

**Lab Session** — for reopening the prototype. It carries everything: geometry, editor settings,
guide state, mode, the occupancy counts being tested, player colours, and optionally the image
bytes themselves. Export asks whether to embed the images; with them the session reopens exactly
as it looked, without them it is geometry and settings and the assets have to be reloaded. Its
only contract is with a future version of this same tool.

**Game Layout** — for the real game UI, at `version: 4`. The line it draws is not *geometry in,
everything else out* — it is **design decisions in, session state out**.

So it carries the instruction's box *and* its type size, alignment, opacity and all three
messages; the wheel's box *and* its 0.5299 ratio, ground flag and opacity; each duty's card box and
visibility, its two actions' wording, and its acolyte anchor; the two artwork slots with their fit,
opacity and caption settings; the reached-duty highlight in full; Tithe's label and its three
resources; the City's label; and the acolyte height and ratios. A box alone was too little — the
real UI could place the instruction and then not know what it says or whether it is centred, and
place the artwork slots without knowing whether they cover or contain.

What stays out is what somebody happened to be *doing* while composing: the selection, the mode,
the zoom, the guides, the ghosts, the undo history, the locks, the image pool, which duty is
reached or previewed, and which view state is on screen. The occupancy counts and seats go too —
those are the crowding test this session is running, not a fact about the layout. **The layout says
where the pieces go, not which pieces are on the board today.** *When* Tithe and the City appear is
a phase the game already knows and nothing here says.

It is built field by field rather than by deleting keys from the session, because a subtractive
export leaks every new editor setting into production the day it is added. `copy game layout` puts
the same thing on the clipboard.

Import reads a Lab Session, and also accepts a bare V1 layout file. Either way the file is
validated rather than trusted: all eight duties must be present, missing fields fall back to the
defaults, and out-of-range numbers are clamped.

## What the browser remembers

The layout is saved to this browser's `localStorage` as you work, and a refresh comes back where
you left off — **but the saved copy holds geometry and settings only, never image bytes.**

That is not a limitation so much as arithmetic: a few full-resolution scenic images as data URLs
run to tens of megabytes and `localStorage` gives a page about five, so an autosave that embedded
them would start failing at exactly the point the layout got interesting, and the failure would
look like "my work stopped saving" rather than like an image problem.

The page is built so this is structural rather than a rule to remember. An art object stores an
image *key* and a filename; the bytes live in a pool beside the state and are never saved with
it. The same indirection is why fifty undo steps cost kilobytes instead of hundreds of megabytes.

So after a refresh the geometry is exactly as you left it and the pictures are gone. Each one
says which file to reload — `Reload: clerical_piety.png` — rather than rendering an empty box.
To come back with the pictures too, export a Lab Session with images and import it.

## Where a duty's two actions live

Every duty offers two action options, so every duty owns two sets of **assets**: a name, a short
planning label, a wax seal and a scenic image each. What they do *not* own is a box — see *The two
artwork slots* above. The lab does not know what the actions mean; it only knows there are two of
each thing to place.

In the *duty actions* panel, pick a duty and edit both actions' wording and load both their
assets. The seal appears in that duty's ribbon card; the scenic image appears in whichever artwork
slot is showing that action, when that duty is the one being shown.

## Acolytes

**Acolyte Height**, 90–210 px in design coordinates, slider and number field, default 120.
This was the control V2 existed for: V1's placeholders were about fourteen pixels tall, which
answers "is there an anchor here" and not "can four of these stand on one duty without burying the
art". Turn it to 210 with four on a duty and the answer is visibly no, which is the kind of finding
the lab is for.

Everything scales by height and keeps its own width, so nothing can be squashed. The City's
representative figures and the in-hand one are percentages of the global height — 85% and 95% by
default, both adjustable — because they stand for a pool rather than for a piece on the board.

**The count is drawn inside the figure**, not beside it. In the action band there is no horizontal
room to spare, and a number on the robe reads at a glance. It flips to a light colour against a
dark or painted figure, computed from the seat's own luminance, because the seat colours are
editable and a fixed choice would be wrong for half of them.

**Acolyte Style: Painted | Colored.**

- **Colored** is a game piece identified by its player's colour. The placeholder is a miniature
  silhouette — head, flaring robe, integral base — rather than a circle, so the crowding question
  is asked of something the right shape.
- **Painted** is a fully painted miniature. Load a transparent PNG or WebP per player; **reuse
  p1's asset for all** copies one across all four seats, which answers the crowding question
  perfectly well. Colored-mode assets can be loaded too. Without an asset either mode falls back
  to the generated silhouette, painted in pewter so the two modes stay distinguishable.

Occupancy is 0–4 per duty. **Seats** in the figures inspector say which player each of the four
figures belongs to, so a duty can hold a mixed stack — which is a different question from
crowding, and the only way to ask whether a majority is readable. `all p1`…`all p4` set the whole
group at once. Arrangements are **row** (the honest worst case), **compact** (what the real UI
would do when it ran out of room) and **arc** (what figures standing on a foreshortened ring
actually look like).

**An acolyte stands on its anchor**, so it reaches upwards by its full height. The anchor ring is
an ellipse narrower vertically than it is horizontally — 0.385 of the wheel's width against 0.34 of
its height — because at 0.40 a 120 px figure at 12 o'clock reached past the wheel's top edge and
drew over the artwork in the band. On the 1.887 wheel that clearance is 10 px.

**Those two numbers are measured, not chosen.** Since the drawing is inlined in the page, every
anchor can be mapped into its `viewBox` and handed to `isPointInFill`, so "is this row standing on
its own duty's face" is a question with an answer. At 0.385 / 0.34 every anchor and both ends of
every row land on that duty's own face, with 58 to 77 asset units of clearance to the nearest
edge — the best of the fractions tried, and the acceptance run re-asks it every time.

## Riding the wheel

The wheel's size is the thing most likely to change while composing, and an anchor stored at an
absolute stage position is in the wrong place the moment it does. So the eight figure anchors —
**the only objects whose meaning is a place on the wheel** — store **normalized coordinates**
instead: `u` and `v`, fractions of the wheel's own box, where `u = (x − wheel.x) / wheel.width`
and likewise `v` down the height. Values outside 0…1 are ordinary and nothing is clamped.

`attached to wheel` in the side panel is the global switch and is on by default. Individual
anchors can be freed in the inspector. **Nothing moves when you flip any of these**: both
representations are kept current at all times, so detaching just makes the absolute one
authoritative, and attaching re-derives `u`/`v` from where things are now rather than restoring
where they used to be.

Everything else — the cards, the artwork, Tithe, the City, the instruction — is placed against the
**module**, not the wheel. V3.1 also had the duty labels and the two centre medallions riding the
wheel; all three left in V4, and `uvAnchor`, the field that existed only for the medallions, left
with them.

## Undo, zoom and the background

**Undo / Redo** are in the toolbar, on Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z (Ctrl+Y also redoes), up
to 50 steps. A whole drag is one entry, not sixty — the gesture is recorded once at pointer-up —
and a slider sweep collapses the same way on a short debounce. Selection is not history, and
neither are the mode toggle, the zoom, the view state or which duty is being previewed: those are
how the layout is being *looked at* rather than part of it, so an undo carries the current view
forward rather than restoring an old one. Flipping between the three states twenty times to
compare them must not cost twenty presses of undo.

**Zoom** is FIT (the default, and what V1 always did) plus 50 / 75 / 100 / 125 / 150 %. It is
display-only and never touches an object's geometry, so an export taken at 125% is identical to
one taken at FIT. At 100% one design pixel is one CSS pixel exactly. Beyond the room available
the workspace scrolls.

**Preview Background** is Black or Game Dark, defaulting to **pure `#000000`** — the scenic art
is generated to fade into black, and judging that fade against a warm near-black shows a seam
that will not exist in the game. The choice applies to the stage and the room around it, in both
Edit Mode and Clean Preview, and to the PNG export.

## The module boundary

Objects may be moved partly outside the 1400 × 1200 module and nothing is clamped — composing a
scene that bleeds off the edge is a legitimate thing to try, and a tool that silently prevented it
would be answering a design question on your behalf. Instead the object gets a red outline and a
badge saying how far over it is on each edge: `OUTSIDE MODULE  right +135`. The inspector says the
same thing for the selected object. Warnings are Edit Mode only — never in Clean Preview, never in
the PNG, never in either export — and can be turned off with the other guides.

## The City, and the acolytes in hand

**One region, two jobs.** In READY and ACTION SELECTION it is the City: a reserve at the right of
the action band, one representative figure and a count per player, always aggregated and never
expanded into one figure per acolyte, no duty action and no tithe. While SOWING the same region
becomes **ACOLYTES IN HAND**, one figure carrying the number still to place.

The two never share a phase, so reusing the region means there is one place to look for "what is
not yet on the board". It is independently movable, resizable, lockable and hideable, and its
geometry is identical in all three states.

V3 had the City below the wheel and the in-hand counter in the wheel's centre. V4 brings both into
the band: the wheel now runs to the bottom of the module, and the count reads better beside the
other reserve than it did in the middle of the board.

## Opening an older file

V1, V2 and V3 layouts all still open, and migration is one function so there is one place to look.

**Geometry is not carried across the V4 boundary.** Every band moved — the summary columns became a
ribbon, the artwork left the margins, the medallions left the wheel's centre, and the wheel itself
went from 950 px wide to 1372. A position in that layout is a position in a layout that no longer
exists: shifting it would put eight cards precisely where the old columns were, off the ribbon and
over the wheel. So the coordinates are dropped and this build's defaults supplied.

**Everything that is not a coordinate is kept**, because that is the part somebody spent time on:
the action wording, the assets and their filenames, the occupancy counts and seats, the City
counts and visibility, the player names and colours, the acolyte height and style, the guide flags,
and each state's instruction. The two states V3 had keep their own text and the state V4 added
starts from the default.

**What is removed** is what V4 has no place for: the per-duty summary and label objects, the
in-hand pool's box, Tithe's wheel-relative fields, the status band's context strap and presets, and
the `summaryDim`, `connectors`, `titheInSummary` and `inHandOverride` switches.

**Per-duty artwork becomes assets.** V2 gave each of the sixteen artworks its own box. Those boxes
are dropped, because there is nowhere for them to go — the two shared slots own the geometry now —
and each action keeps its picture as its `scenic` asset, along with its filename.

**From V1:** the single artwork per duty becomes Action A (and then its box is dropped, as above);
Action B starts from the defaults. Figure anchors move from `anchorX`/`anchorY` to `x`/`y`, the
`compact` flag becomes one of the three named arrangements, the City's single player list splits
into global player identity and per-City counts and visibility, and the in-hand pool's raw colour
becomes a seat. A V1 or V2 file on the 1200-wide module is accepted; its canvas is simply declared
to be 1400 × 1200, since its coordinates are not being reused.

In every case, any image data URL still inlined in the state is hoisted into the image pool.

## Decisions the brief left open

These were judgement calls. Each is here because the brief said to choose and write it down.

**The eight duties are the engine's own slugs.** `allocation`, `build_roads`, `clerical`,
`construct`, `give_alms`, `ordination`, `produce`, `taxation` — from `DUTY_CATEGORIES` in
`pilgrim/model/duties.py`, so an exported layout names duties the way the game does. Not from
`enums.py`: that is the event enum and carries names like `build_roads_deferred` that are not
duties, which is why the test asserts equality against `DUTY_CATEGORIES` rather than membership
of something larger.

**The starting clock arrangement** puts clerical at 12 and runs clockwise through taxation,
produce, build_roads, construct, give_alms, ordination, allocation. The brief says the mapping
does not matter; this one is only a starting point and every anchor moves independently.

**The cards are in the wheel's order, and the row knows nothing else.** V3's four-a-side split was
a starting point that the page's logic had to be told about twice. One row in one order needs no
such knowledge, and it means adding or reordering a duty is a change in one tuple.

**A preview is badged and a choice is not.** The same two boxes serve both, and the difference
between reading about a duty and taking one is the whole point of having a preview at all — so the
distinction is a badge plus the absence of the choice treatment, both answering the same function
so they cannot disagree.

**Tithe is never in a preview.** It is the alternative to taking what a duty offers rather than
something a duty offers, so showing it while somebody is still reading would misdescribe it.

**The wheel's centre is left empty.** Both medallions left for the action band. A quiet centre
means a wheel asset with art of its own in the middle is not competing with the layout, and it is
one fewer thing between the player and the board.

**Nothing on the wheel says which duty a space is.** That decision is explicitly out of scope, and
the V3 label objects are removed rather than defaulted to hidden, because a hidden object is one
checkbox away from being back.

**The acolyte count goes inside the figure.** The band has no horizontal room to spare and a
number on the robe reads at a glance. Its colour is computed from the seat's own luminance rather
than fixed, because the seat colours are editable.

**The anchor ring is narrower vertically than horizontally.** Not a cosmetic ratio: an acolyte
stands on its anchor and reaches upwards, so at 0.40 of the wheel's height the 12 o'clock figures
overhung the top edge and drew over the artwork above. The other constraint — every row on its
own face — is now measured against the real drawing rather than judged by eye.

**32° is a design invariant, and the built-in drawing is checked against it.** The ratio comes
from that drawing's own `viewBox` — the generator does not pick a number — but it then refuses to
build a wheel more than 0.0005 away from 0.5299, because re-rendering the wheel at another aspect
is a decision about the whole module: the lower edge, the acolyte ring and the action band all
follow from it. The check is a function rather than a bare assertion so the refusal itself can be
tested; an invariant whose only expression is a line that happens to be true today is being hoped
for, not checked.

**A loaded asset never gets a vote on the layout.** It is art in a box that was decided here.
Reading its ratio and adopting it made loading a picture into a layout edit, silently.

**The wheel's shape is read from the asset, never chosen here.** The ratio comes from the
drawing's own `viewBox`; the elevation it implies is reported and is not an input. A number picked
in this file would be this tool having an opinion about a drawing it did not make, and it would go
stale the first time the aspect moved — which the builder's own header says is still open, and
which has now happened once already.

**The recolour happens at build time, not in the checked-in file.** The drawing is the builder's
to own, parchment palette and all; wanting it slate is this lab's opinion, so the lab applies it
where it can be seen, tested and reversed. Every entry in the palette must match something or the
build fails — a palette that quietly stopped applying is a cream wheel on a black field with no
error anywhere.

**The drawing is vendored rather than imported.** One checked-in copy, read as bytes, so the page
is reproducible from this tree alone and nothing about the other tool — its argparse at import
time, its numpy dependency, its open questions — has to be true for a layout to generate. The cost
is a copy that can go stale, which is why the refresh recipe is in the generator's header and in
this file.

**The asset's ground rectangle is hidden by default.** It states the board's colour for the
wheel's bounding box and nowhere else, which is not a shape the real board has, and the stage's
own **preview background** is the honest control for that question. One toggle puts it back.

**The view state and the open preview are not undoable,** for the same reason as mode and zoom.
The brief lists what undo should cover and says not to record transient editor state; these are how
the layout is being looked at rather than part of it — the same reason the Game Layout export
leaves them out — so they are saved but never recorded, and an undo carries the current view
forward instead of restoring an old one.

**The starting state is a busy board on purpose.** Two duties full, eighteen acolytes on the
ring, one duty with a mixed stack, eighteen more in the City and four in hand. The question the lab
exists to answer is whether the composition survives a heavy game state, and a near-empty default
would let it pass by being empty.

**Images live in a pool beside the state, not in it.** An art object stores a key and a filename.
This one indirection is what makes the autosave small enough for `localStorage`, the undo history
cheap enough to keep fifty steps of, a Lab Session exportable with or without bytes from the same
object, and a lost asset able to name the file to reload. IndexedDB was not needed for any of it.

**The instruction is one object with three messages, and the panel generates its fields.** A single
text field would mean retyping the line on every flip — the one thing this version is designed to
do repeatedly. Generating one field per state from the list of states is what makes it impossible
for a field and its handler to disagree about which state they belong to, which is how V3.1 shipped
a panel that read one state's text into another's box.

**The Game Layout export is built field by field.** Not by cloning the state and deleting the
editor keys: a subtractive export leaks each new editor setting into production on the day it is
added, and this file is meant to be something the game UI can read without knowing what to
ignore.

**The City is aggregated, always.** One representative figure plus a count per player, even at a
count of one, and never expanded into one figure per acolyte. Same for the pool in hand.

**PNG export is best effort.** It snapshots the stage through an SVG `foreignObject`, which
needs no library but is the first thing to break if the page ever gains an image it does not
own. It reports failure rather than writing a blank file, it uses the chosen background, and it
snapshots in Clean Preview so no editing chrome or boundary warning can reach it. The Game
Layout JSON is the output that matters.

## What it does not do

It is not the game UI and does not try to be. There is no hover or selection styling for
gameplay, no sowing animation, no merchant, no player boards or resource tracks, no full
2039 × 1200 or 2283 × 1200 board, no gameplay logic behind the reached-duty control — it is a
simulation for judging the composition — and nothing outside the 1400 × 1200 module. It also does
not identify the eight physical spaces on the wheel, which is a decision kept for later. The spec's
interaction states are for the real UI to implement; this page only decides where things sit.

The one question it exists to answer: do the v2 wheel, the two action artworks, realistically
sized acolytes, the eight reference cards, Tithe and the City fit clearly and attractively inside
one fixed 1400 × 1200 module — in all three of the states the player will actually see?
