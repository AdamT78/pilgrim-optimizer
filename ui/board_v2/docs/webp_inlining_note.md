# Inlining the board's pictures as WebP

**Status: measured, not done.** Nothing in the repository has been changed. This note exists so the
measurement does not have to be repeated, and so the one trap in it is not rediscovered the hard way.

Measured 2026-10-04 against the tree at `0fec958`/`c27f6f7`, with all fourteen duty action cards and
all forty-one marks present.

---

## 1. What the generator does today

`ui/board_v2/action_board/generate_action_board.py` inlines every picture as a `data:` URI through one
function, `_inline(path, size, fmt="JPEG")`. It encodes in two formats, chosen per call site:

| call site | what | drawn at | inlined at | format |
|---|---|---|---|---|
| `bundled_art`, line ~299 | the 14 duty action cards | 494 x 247 | 988 x 494 (`ART_SCALE = 2`) | JPEG, `ART_JPEG_Q = 82` |
| `bundled_seals`, line ~368 | the wax seals | 100 x 100 (`SEAL`) | 200 x 200 | PNG |
| tithe tokens, line ~433 | the three resource tokens | 100 x 100 (`TOKEN`) | 200 x 200 | PNG |

The split is not arbitrary: the cards are rectangular photographs, and the seals and tokens are
cut-outs with an alpha channel, which JPEG cannot carry. PNG was the only remaining option when that
code was written. WebP removes the constraint, because it does both.

**The marks are the larger half of the page.** This is the part that is easy to get wrong by
intuition — there are 41 of them at 200 x 200 against 14 cards at 988 x 494, and PNG is a poor
container for photographic wax:

```
cards (JPEG q82)    1 668 KB
marks (PNG)         2 697 KB
                    ---------
total                4 365 KB     (before base64, which inflates everything by 1/3 equally)
```

---

## 2. The cards: 27% smaller at matched quality

Quality was **matched, not assumed**. For each card, the JPEG q82 encoding was scored with SSIM
against the LANCZOS-resized source, and then the lowest WebP quality whose SSIM equals or beats that
score was found by search. So every number below is "same fidelity or better, fewer bytes".

SSIM here is an 11 x 11 Gaussian, sigma 1.5, Wang et al. constants, hand-rolled in numpy because
scikit-image would not install in the sandbox; it was self-checked to return exactly 1.000000 on
identical input before being used for anything.

| card | JPEG q82 | WebP | matched q | saved |
|---|---|---|---|---|
| allocation_relocate_acolytes_left_v01 | 104K | 75K | 80 | 28% |
| build_roads_build_road_left_v01 | 156K | 107K | 71 | 31% |
| build_roads_build_shrine_right_v01 | 103K | 81K | 82 | 21% |
| clerical_gain_coins_right_v04 | 126K | 90K | 77 | 28% |
| clerical_gain_piety_left_v04 | 106K | 81K | 81 | 24% |
| construct_construct_building_left_v01 | 115K | 81K | 78 | 29% |
| construct_construct_road_right_v01 | 115K | 85K | 79 | 26% |
| give_alms_donate_building_right_v01 | 132K | 91K | 76 | 32% |
| give_alms_give_alms_left_v01 | 120K | 90K | 78 | 25% |
| ordination_ordain_left_v03 | 92K | 68K | 81 | 26% |
| ordination_send_on_mission_right_v03 | 117K | 81K | 77 | 31% |
| produce_gain_stone_right_v01 | 138K | 101K | 77 | 27% |
| produce_gain_wheat_left_v01 | 142K | 105K | 77 | 26% |
| taxation_action_a_left_v01 | 103K | 80K | 81 | 23% |
| **total** | **1 668K** | **1 214K** | 71–82 | **27%** |

A single constant is wanted rather than a per-image search. q82 sits at the top of the matched range,
so it is at least as good as today's JPEG on every card and better on most, and still saves roughly a
quarter. That is the recommended setting.

---

## 3. The marks: 25% free, or 74% if you accept lossy wax

| encoding | size | fidelity |
|---|---|---|
| PNG (today) | 2 697 KB | — |
| WebP lossless, `exact=True` | 2 011 KB (-25%) | pixel- **and** alpha-identical, verified on all 41 |
| WebP lossy q90 | 695 KB (-74%) | alpha bit-exact; ~5.1/255 mean RGB error inside the mark (worst file 7.2) |

Lossy WebP keeps alpha exactly because the alpha plane is compressed losslessly even in lossy mode —
the measured deviation across all 41 marks was 0/255. What degrades is only the colour inside the
mark. Whether 5/255 on a 100px wax seal is visible is a judgement to make by looking at the real
board, not from this table.

---

## 4. THE TRAP: Pillow's WebP lossless is not lossless by default

`Image.save(buf, "WEBP", lossless=True)` **is not exact**. Pillow defaults to `exact=False`, which
lets the encoder discard the RGB values underneath fully-transparent pixels. On the first seal tested
(`clerical_actionA_seal_v01`, resized to 200 x 200) this rewrote **2 134 pixels**, every one of them
alpha = 0.

This matters more here than it would elsewhere. The alpha channel itself survives, so a check that
compares only alpha passes and reports success. But `attribution.json` says of these cut-outs that
"the alpha is the edge" — and the colour sitting under that edge is exactly what gets thrown away.
Any compositing, feathering or re-cut done later against those pixels would be working from data the
encoder invented.

`exact=True` fixes it; with it set, all 41 marks round-trip byte-identical.

**This belongs in a guard, not in a comment.** A test that inlines one mark, decodes the `data:` URI
and asserts the array is unchanged would catch it. A docstring claiming losslessness would not, and
would be believed.

---

## 5. Totals, and what they are worth

```
today                          4 365 KB
cards WebP + marks lossless    3 225 KB    -26%
cards WebP + marks lossy q90   1 909 KB    -56%
```

Do not oversell this. `action_board.html` is a local development page opened from disk, so the saving
buys how quickly it opens, how it feels to scroll, and how easily it can be handed to someone — not
bandwidth. It is a tidy win, not a problem being fixed.

---

## 6. Nothing blocks the change

- No test asserts `data:image/jpeg`. The only matches for "jpeg" under `tests/` are an unrelated
  fixture blob in `tests/layout_lab/fixtures/v3_session.json` and `accept=` attributes on file inputs.
- `action_board.html.tmpl` line 588 already sets `inp.accept = "image/png,image/jpeg,image/webp"`.
- The seal and icon **sources on disk are already `.webp`**. Only the inlining step converts away
  from it, re-encoding WebP sources as PNG.
- Pillow reports `features.check("webp") == True`; the CI lab lane already installs Pillow and numpy
  for other reasons, so no new dependency and no new workflow exception.

---

## 7. If and when this is picked up

1. In `_inline`, add WebP alongside the two existing branches: lossy with `quality=` for the cards,
   `lossless=True, exact=True` for the marks. Rename `ART_JPEG_Q` if the cards stop being JPEG, since
   a constant that names the wrong format is the kind of thing this tree tries not to leave lying
   around.
2. Switch the cards to `WEBP` at q82 and the marks to lossless-exact. That is the conservative -26%
   with no fidelity argument to have with anyone.
3. Add the round-trip guard from section 4.
4. **Time the build before settling on `method=6`.** All measurements above used it, and it is the
   slow end of the encoder. It was never timed against the generator's own runtime; `method=4` may be
   the better default and was not measured.
5. Leave lossy marks as a separate decision, made after looking at a seal at q90 on the real board.

---

## 8. How to reproduce

Everything above came from encoding the real files in the tree with Pillow and comparing decoded
arrays with numpy — no fixtures, no cached numbers. The card table needs the SSIM helper described in
section 2; the mark table needs only `Image.save` with the kwargs shown and `np.array_equal` on the
decoded RGBA. The file lists come from `attribution.json` (`slot` in `left`/`right`, excluding
`/icons/` and `/seals/`, newest version per folder) and from walking `duty_actions/*/seals/` and
`tokens/`.
