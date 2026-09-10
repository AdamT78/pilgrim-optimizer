# The gothic frame, in layers

`frame_base.png` is the frame as it arrived: stonework, gold banding, tower, scroll **and a red
cloth drape**, all in one image. It is what the live template still draws, and it is kept.

The rest of this directory is that image taken apart, so that a player's colour can be a swapped
layer rather than a separate copy of the whole frame. Four seats needing four full frames is four
times a 1.3 MB asset; four seats needing four drapes is four times 250 KB over one shared base.

## The stack, bottom to top

| Layer | File | Per seat? |
| --- | --- | --- |
| Stonework and gold, no drape | `frame_base_nocloth.png` | shared |
| Tower, scroll and the loose specks | `frame_ornaments.png` | shared |
| The drape | `cloth_<colour>.png` / `cloth_<colour>_dim.png` | **yes** |
| The gemstones | `stones_<colour>.png` | **yes** |

The split is by hard alpha, not by blending: every pixel of the original belongs to exactly one
layer, antialiased rim included. Compositing base + ornaments + `cloth_red` + `stones_red` returns
`frame_base.png` with the drape and stones in place, pixel for pixel — the separation is lossless,
so nothing about the artwork was decided by the splitting.

`frame_ornaments.png` is separate from the base for one reason: the tower and the scroll sit
*inside* the drape's bounding box but are not part of the drape. Recolouring a cloth layer that
still contained them would turn the tower sage or plum along with it. They are colour-neutral, so
they ride above every seat colour unchanged.

The near-black specks in the lower left — small fragments that float free of the frame's main body —
travel with the ornaments rather than the base. They are unattached either way; keeping them with
the shared, colour-neutral layer is what stops them from vanishing when a seat's drape changes.

## The seat colours

Cloister: sage, pewter, plum and bone. Deliberately not the board-game default red / blue / yellow /
green — those are hard to place in a gothic scene, and yellow in particular fights the frame's gold.
Each pair is at least dE 28 from the others in CIE Lab, which is past the distance at which two
colours read as different colours rather than as two dye lots of one.

Bone's gem is the exception to "the gem matches the cloth". Bone's hue sits inside the frame's own
gold band, so a saturated bone gemstone reads as a third piece of gold rather than as a player's
marker; it is drawn as a pearl instead — almost no colour, carried by a raised value.

`cloth_red.png` and `stones_red.png` are the sources every other colour is derived from. They are
kept as provenance, and they are **not** a fifth seat: lit red measures L\* 20.6, below dimmed sage
(23.8) and dimmed bone (25.2), so a red player waiting for their turn would sit behind a board
dimmer than two boards that are not waiting. The assembler's `SEAT_COLORS` is the Cloister four.

## How the assembler draws this

The template no longer has one `frame` role. It has `frame_base`, `frame_ornaments`, `cloth_lit`,
`cloth_dim` and `gems`, and a config names a `seat` rather than five paths — one colour name expands
to the whole set, so a board cannot end up in a plum drape with sage gemstones. Explicit paths still
win over the seat, which is what lets the regression check below dress the layered board in the red
source.

`ui/render/check_frame_layers.py` builds the layered board wearing `cloth_red.png` and a board from
the old single-image markup, renders both at the frame's native 1905 px so nothing is resampled, and
requires that **every** pixel agrees. It does, exactly. That check is the reason to trust the split:
a wrong z-order or a one-pixel offset still looks like a perfectly good gothic frame on its own.

## Lit and dim: whose turn it is

Every drape exists twice. `cloth_<colour>.png` is the **lit** state, worn by the seat that is to
play; `cloth_<colour>_dim.png` is every other seat. Hue never changes between them, so a dim drape
still says plainly which seat it is — the turn rides on lightness, underneath the identity rather
than in place of it.

The dim set is **not** one multiplier applied to all four, and the reason is the thing to remember
if the palette is ever extended. The lit drapes do not sit at a common lightness: bone is near-white
at L\* 51 while plum and pewter sit at L\* 27. Dim everything by the same factor and dim bone lands
at L\* 34 — *lighter than lit plum*. The column then shows a board that looks lit while a darker
seat is actually to play, which is exactly the misread the scheme exists to prevent.

So sage, pewter and plum take the common factor (s ×1.25, v ×0.60) and bone takes a deeper one
(v ×0.45), chosen so the two bands clear each other:

| | sage | pewter | plum | bone |
| --- | --- | --- | --- | --- |
| lit L\* | 40 | 27 | 27 | 51 |
| dim L\* | 24 | 15 | 14 | 25 |

Brightest dim (bone, 25) sits below darkest lit (plum, 27). `--check` asserts that, so a future
palette edit that breaks the banding fails rather than shipping.

Pewter is the weakest signal of the four — lit and dim are dE 13 apart, against bone's 26 — because
lit pewter is already the darkest of the drapes. It reads, but if the turn indicator ever wants more
punch, raising lit pewter's value is the lever, not lowering dim pewter's.

**The gemstones have no dim state.** They carry the other signal — active player, first-player
marker — and dimming both at once would make the two indistinguishable.

## Changing or extending the palette

The tables live in `ui/render/recolor_seat_layers.py`, not in these files. Edit them there and
re-run; `--check` confirms the committed PNGs still match what the tables say they should be, and
that the lit and dim bands still clear each other.

```
python3 ui/render/recolor_seat_layers.py            # rewrite the twelve derived layers
python3 ui/render/recolor_seat_layers.py --check    # verify, change nothing
```

## Licensing

Every file here is derived from OpenAI-generated artwork, as with the rest of `assets-gothic/`.
The derived layers are alpha splits and hue rotations of that artwork and carry the same terms; in
particular, do not describe the originals as manually illustrated.
