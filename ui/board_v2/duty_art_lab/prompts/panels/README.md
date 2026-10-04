# The panel briefs

One file per duty action panel, **word for word as it was sent**, each marked
`<!-- archival: -->` — the same mechanism `../seals/` uses, and the one
`generate_duty_art_board.py` already has for "somebody's text as they wrote it, kept because it
produced a particular picture". `<!-- produces: -->` names the file each one made, and that is
what `attribution.json`'s `reproducibleBy` points at.

Fourteen briefs for fourteen cards, one to one. The mapping was derived from `attribution.json`
(duty slug plus `slot`) rather than typed out, and each file's served text — what is left after the
HTML comments are stripped — was asserted byte-identical to the author's section before it was
written.

## They are here rather than in `../` on purpose

The briefs in `../` are ONE text with `{{LEFT_SUBJECT}}` and friends substituted in, run against a
duty to make a two-panel master for `crop_duty_master.py` to cut. These are the opposite: fourteen
separate prompts, each for one finished card, with no tokens and nothing to substitute. Keeping
them out of `../` means they are never offered as a master brief, which is the same reason the seal
briefs sit in their own folder.

## THE PREAMBLE BELOW DESCRIBES A PIPELINE THAT NO LONGER EXISTS

It is kept verbatim anyway, because it is what was sent and this folder is evidence. But read it
with this in mind, or it will mislead:

- **"Compositing … place the left and right panels side by side in the 2172 × 724 image, with a
  dark gutter in the 35 px centre strip"** — that is the master-and-crop workflow. No shipped card
  went through it. Each one was generated whole and is used whole.
- **"Crop safety: only y 190–534 is guaranteed to survive the crop"** — there is no crop. Nothing
  is cut off any of these.
- **"each prompt is for one panel … generate each at 2:1"** — THIS is the line that was actually
  followed. Every one of the fourteen shipped cards is 1774 × 887, exactly 2:1, matching the slot's
  2.0000 so `fit: cover` crops nothing.

The style, lighting and colour-grade notes still apply and are the reason the set hangs together.

## Nothing reads this folder yet

`generate_duty_art_board.py` shows the seal briefs through `seal_prompts()`, which is hardcoded to
`prompts/seals`. There is no equivalent for these, so for now `attribution.json` is their only
consumer. Wiring the duty art board to show a card beside the brief that made it is a follow-up,
not a loose end in the record.

---

## The preamble, as sent

# Pilgrim – Duty Action Art Prompts

Image-generation prompts for all 14 duty action boxes, grouped by duty tile.

## How to use these

- **Format:** each prompt is for one panel. Generate each at **2:1** using your generator's own aspect setting (for example `--ar 2:1`), not just the prompt text.
- **Compositing:** place the left and right panels of a tile side by side in the 2172 × 724 image, with a dark gutter in the 35 px centre strip. Nothing may span the middle.
- **Crop safety:** only y 190–534 is guaranteed to survive the crop, so keep heads, hands and key objects in the middle of each panel.
- **Style reference:** pick one anchor close-up image you're happy with and use it as the style reference for every prompt. Don't chain each new image off the previous one, as the style drifts.
- **Colour grade:** apply the same LUT or curves preset to every final image.
- **Warm light:** each scene has exactly one warm light source. On two-panel tiles, the left panel's light sits on the right of its frame and the right panel's light on the left, so the two lights face each other.

---
