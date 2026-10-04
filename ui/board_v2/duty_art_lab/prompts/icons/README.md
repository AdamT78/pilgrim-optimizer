# The icon brief

**One brief, not fourteen.** Every icon master under `duty_actions/*/icons/masters/` came from the
same prompt, word for word; `01-icons-from-seal-motifs.md` holds it as it was sent. What changed
between runs was never the text — it was the second attached image.

That is why this folder has one file where `../panels/` has fourteen. The panels are fourteen
different texts. The icons are one text and fourteen different inputs, and splitting it into
fourteen identical copies would be inventing a difference that does not exist.

## The two attachments are the whole method

The prompt says "the attached image" and "the second image" and names neither, so without this note
the record is unreadable:

| attachment | what it was | where it is |
| --- | --- | --- |
| first, "the attached image" | the style sheet — nine grim-dark marks, bone-white on torn black plates against a purple-indigo ground | `../../_reference/icon_style_sheet__e.jpg`, **not committed** — see below |
| second, "the second image" | that action's own **wax seal**, from `duty_actions/<duty>/seals/` | committed, and recorded in `attribution.json` |

So an icon is its seal's motif redrawn in the sheet's style. That is the relationship between the
two marks a duty carries, and it was not written down anywhere until now: the seal came first and
the icon is derived from it, not the other way round and not independently.

**Which seal version was attached is not recorded.** Several actions have a `_v01`, `_v02` and
`_v03` seal, and the brief does not say which was on screen when the icons were made. Nothing in
the tree can recover it. It is left unknown rather than guessed.

## The style sheet is deliberately not committed

`ui/board_v2/duty_art_lab/_reference/` is gitignored, for the reason `.gitignore` already gives for
`ui/concept/_reference/`: it holds third-party work kept for inspiration, and committing it "would
put somebody else's work in every clone forever, and the credit we would have to write beside it
would probably name the wrong person".

So that the reference survives without the file — the same trick `ui/concept/manifest.json` uses —
here is enough to recognise it:

```
file      icon_style_sheet__e.jpg   (downloaded as __e.jpg)
size      98 727 bytes, 1200 x 1118, JPEG, RGB
sha256    d1c6750d3a70d38524a0871db55e2d7fb368f8236bd4abbd3c6737ab5719ec1e
content   a 3 x 3 sheet of nine icons: bone-white motifs -- a skull wreathed in
          flame, tentacles, three claw-slashes, an anatomical heart, an eye
          beneath a crown of spikes, a skull, a hooded figure, a clenched hand,
          a key -- each on a torn black plate, on a flat purple-indigo ground
```

That ground is worth noticing: the board's tiles are `--plate: #1E1935`, and the sheet is why.

## If the file is missing

Nothing in the repository reads it — no generator, no test. It is an input to a conversation with
an image model, not to a build. A clone without it is complete; only a future run of this brief
would need it back.
