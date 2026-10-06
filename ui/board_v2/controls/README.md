# The board's three controls

Show Map, Hire Building and the commit: the column of marks at the right-hand end of the action
row. One folder, shaped exactly like a duty's `icons/` — the cut beside its `masters/` original.

```
controls/icons/control_map_icon_v01.webp        the cut the board draws
controls/icons/masters/control_map_icon_master_v01.png   the untouched download
```

## Why these are not under `duty_actions/`

A mark in this column is a **button you press**. Everything under `duty_actions/` is a **move the
engine scores**, and the whole tree is shaped around that: a duty icon is found by its duty and its
`actionA`/`actionB` slot, its wording lives under `duties` in `duty_text.json`, and
`attribution.json`'s `slotFolders` says which folder holds each action's pictures. A control has no
duty, no slot and no engine action, so a ninth folder beside the eight duties would have cost an
exception in every walk that treats `duty_actions/*` as a duty — the action board's, the duty art
lab's, the icon lab's — in exchange for making one of them shorter.

The same split runs through the rest of it. `duty_text.json` has a `controls` block beside its
`duties`; `geometry.py`'s `MARKS_ORDER` owns the column's order; `attribution.json` lists
`controls` in `assetDirs` so the provenance walk reaches these files.

## Naming

`control_<key>_icon[_master]_v<NN>.<ext>`, where `<key>` is the mark's own name from `MARKS_ORDER`
— `map`, `hire`, `commit`. The icon lab reads the key out of the filename and refuses a file whose
key is not one the `controls` block knows, rather than guessing which mark it belongs to.

**The cut and the master do not share an extension.** Prints are WebP at quality 90 and masters are
PNG, because a lossy archive is not one. `attribution.json`'s `imageSuffixesNote` has the reasoning;
the icon lab's `master_of()` hard-codes `.png` from the other end.

**Versions count up and nothing is overwritten.** A new cut is `_v02`, not a rewrite of `_v01`,
because a file whose `sha256` is recorded cannot be replaced in place without the record describing
pixels that are gone. The board draws the highest version it finds.

## Changing one

Put the new master in `icons/masters/`, record it in `attribution.json`, and rebuild the icon
sizer — it walks this folder as a second root beside `duty_actions/` and will show a card for it.
Frame it there, save the settings, and the page hands back a `framing.json` to drop into
`ui/board_v2/icon_lab/`. The cut itself is that framing's `crop` box taken out of the master at its
own resolution: whole source pixels, no resampling, no ground.

Cutting it outside the page is fine and is how the three here were made. The lab's own `cut` button
goes out through a canvas, which keeps colour premultiplied by alpha and so rounds every
part-transparent pixel on the way back; a straight crop does not, and is the more faithful of the
two by a little. The framing is the lab's either way.

## What they cost

The marks are drawn at `geometry.py`'s `MARK` — 68px, a duty tile's mark less its frame — and
bundled at twice that for a retina screen. The masters are about 1.2 MB each and are the archive;
the cuts are about 120 KB and are what the page inlines.

## Still open

**`reproducibleBy` is empty on all three masters.** Every duty icon points at
`duty_art_lab/prompts/icons/01-icons-from-seal-motifs.md` with that action's own wax seal attached
as the second image. These three have no seal to be a redrawing of, and the prompt that made them
was not kept. If they are ever regenerated, write the brief down first.

**A control with no cut draws Allocation's mark**, at 55% brightness and carrying a `stand-in`
class, so a borrowed emblem does not look as settled as a real one. That fallback is in the board's
template, not here; it exists because an empty column looks finished and a wrong emblem does not.
