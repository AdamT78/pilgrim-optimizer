# Resource tokens

The three circular tokens a tithe can gain: wheat, stone, silver. Square transparent PNGs at
1254 x 1254, generated for this project.

**Each PNG is the complete token.** The rim, the disc behind the motif and the material treatment
are all painted into the artwork, so the layout lab draws the image and nothing else -- no circle
behind it, no border around it. Putting one inside the old `.res` disc would give it two rims.

They stand in for the letters `W`, `S` and `Ag` that the lab shows when no icon is loaded. That
fallback is deliberate: the tool has to stay usable with no assets at all, so a missing token is a
letter rather than a broken image.

Sizing lives in the lab's TITHE panel, not in these files: one shared `tokenSize` for all three,
and a per-resource `scale` between 60% and 140% for optical correction, because a wheat sheaf and
a coin of the same pixel diameter do not carry the same visual weight. Each token sits in a fixed
square slot, so scaling one never pushes the other two.

`ui/assets/icons/resources/` is a different thing: flat single-colour glyphs, some of them
third-party with attribution obligations. These are painted tokens with no third-party rights.
