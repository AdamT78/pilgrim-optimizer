# Prompts

The text that generated the art, kept beside the project rather than in a chat
history. Every committed image in `assets-gothic/` came out of one of these, and
`assets-gothic/attribution.json` names the prompt file in each asset's `source`
field — so a prompt moving without that record being updated breaks the only
link between a picture and how it was made.

These are **production inputs**, not documentation. That is why they sit here
rather than under `docs/`: `docs/` explains decisions, this folder is what you
copy and run.

| folder | what it makes |
| --- | --- |
| `duty-wheel/` | the nine duty tiles, in versions A, B and C, plus the panorama background halves |
| `banners/` | the blank parchment title banners the duty names are set over |

## Why the originals cannot be regenerated

`assets-gothic/attribution.json` states it plainly and it is worth repeating
here: the images came out of sessions with no seed on record, and image
generation is not deterministic. Re-running a prompt produces *different*
artwork, not the same artwork. A lost original is lost. The prompt is a recipe
for something of the same kind, not a way back to the same file.

## Layout

`duty-wheel/` keeps the bare prompt bodies — the text you paste, nothing else —
one folder per duty, with `notes/` holding the longer `.md` versions those were
extracted from. The notes carry the reasoning: which version is dimmed, why the
city tile is never darkened, what each variant was trying to fix. When a prompt
needs changing, read the note first.
