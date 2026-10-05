# Resource tokens

## Two treatments, and what each one means

There are two sets of art for the same three resources and the difference carries meaning.

`seal_*` is a grey wax seal. On this board a SEAL is a thing you can take, and its colour says
which kind: red for a duty action, grey for a resource. The Take Tithe column is the third choice
beside the two duty actions, so it draws seals and speaks the language the rest of the row speaks.

`token_*` is a coin. That is what a resource looks like once it is yours rather than on offer,
which is a different job on a different surface.

Both are built into `ui/board_v2/action_board`, which prefers the seal and falls back to the coin,
then to a letter. The fallbacks are not decoration: the page has to stay usable with no assets
at all.

**The seals carry the same correction as the coins, for the same reason.** As generated they
measured 0.919, 0.915 and 0.875 of their own square for wheat, stone and silver -- so silver read
about five per cent smaller than wheat at the same `tokenSize`, which looks like a fault in the
layout rather than a difference in the drawings. Wheat was re-exported at x0.9854, stone at
x0.9905 and silver at x1.0357 about their own centres, bringing all three to 0.905-0.907. That is
the coins' 0.906, which is deliberate: **a seal and a coin are interchangeable in the same slot.**
Nothing clips at the canvas edge.

**0.906 is no longer a figure in this file.** It is `SOLID_FRACTION` in
`../action_board/geometry.py`, and `tests/action_board` measures every disc the board draws
against it -- the three coins, the three grey seals and the red action seals alike. Three sets of
discs have now arrived at three different fractions and each correction was written down in prose,
which is not what the fourth set will be measured against. The paragraphs here say WHY a drawing
was changed and by how much; the number itself has one owner and a guard. Masters are excluded on
purpose: a master that measured 0.906 would mean its correction was never made.


**The prints are WebP and the masters are PNG.** At quality 90 the twenty shipped discs on this
board come to 7 MB where the PNGs were 40, and the worst single pixel moves 12 of 255 -- measured
on each disc composited over the panel it sits on, at the size the board actually inlines it,
which is the only place anyone ever sees it. `masters/` is not re-encoded: it is the archive, and
a lossy archive is not one. If a disc is ever wanted larger or at a different size, it comes off
the master, exactly as a duty's action crops do.

Which extensions this tree's walks look for is `imageSuffixes` in `../attribution.json`, because
three generators and the tests all have to agree about it. When the prints changed format, a walk
left looking only for `*.png` does not fail -- it quietly finds nothing, the board draws its
placeholders, and the note it prints says the files are missing while they sit right there.

The three circular tokens a tithe can gain: wheat, stone, silver. Square transparent PNGs at
1254 x 1254, generated for this project.

**Each PNG is the complete token.** The rim, the disc behind the motif and the material treatment
are all painted into the artwork, so the layout lab draws the image and nothing else -- no circle
behind it, no border around it. Putting one inside the old `.res` disc would give it two rims.

They stand in for the letters `W`, `S` and `Ag` that the lab shows when no icon is loaded. That
fallback is deliberate: the tool has to stay usable with no assets at all, so a missing token is a
letter rather than a broken image.

`masters/` holds the three as they were first generated; `resources/` holds what the lab and the
game actually draw. They differ, and on purpose. Measured as a fraction of their own square, the
solid discs came out at 0.906 for stone, 0.847 for wheat and 0.802 for silver -- so at the same
`tokenSize` silver read about a ninth smaller than stone, which looks like a mistake in the
layout rather than a difference in the drawings. Wheat was re-exported at x1.070 and silver at
x1.129 about their own centres, stone untouched, which brings all three to 0.906; neither
re-export clips at the canvas edge. **The three are meant to be interchangeable at one size, so
the correction belongs here rather than in a control.**

Sizing lives in the lab's TITHE panel, not in these files, and it is two numbers: one `tokenSize`
for all three, and a `tokenSpread` that is the distance from one centre to the next. It has meant
three arrangements now -- side by side, then the side of an invisible equilateral triangle, and
now the step down a column -- and it is the same number each time, which is the point of naming it
for the spacing rather than for the shape. There is no per-resource scale. There was one, and it was a slider that let the
studio correct silver by hand -- which would have papered over the fault above while leaving the
production pipeline to reproduce it.

**Provenance default.** Unless a file's entry in `../attribution.json` says otherwise, an image in
`ui/board_v2/` was generated with ChatGPT (OpenAI) and carries the `openai-generated` licence.
Anything with a different origin has to say so in its own entry. A new image with no entry at all
is a gap rather than an implicit default, and `tests/layout_lab/test_board_v2_attribution.py`
fails on one -- printing the line to paste, so recording a new image is one line rather than a
trip through the other entries to work out the shape.

`ui/assets/icons/resources/` is a different thing: flat single-colour glyphs, some of them
third-party with attribution obligations. These are painted tokens with no third-party rights.
