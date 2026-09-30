# Resource tokens

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
for all three, and a `tokenSpread` that is the side of the invisible equilateral triangle their
centres stand on. There is no per-resource scale. There was one, and it was a slider that let the
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
