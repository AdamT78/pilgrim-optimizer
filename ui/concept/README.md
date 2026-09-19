# Concept art

Where concept art stops being loose files in a downloads folder.

    python3 ui/concept/build_browser.py --open

One self-contained HTML page with a button per subject: the four player characters, the duty
wheel and the concept work behind it, the tithe resource components, and the generic acolytes
shown on a board. Click any image for a full-size overlay; keys `1`–`8` switch subject and the
arrows step through them.

## The names are derived, not invented

A file's path is `<subject>/<kind>.png`, and both halves come from the `SUBJECTS` table in
`build_browser.py` — the same table that orders the buttons and titles the cards. So
`duty_wheel_concept/labelled.png` says where it belongs without anybody looking it up, and a
filename cannot disagree with the page it appears on.

What a generator happened to call a file — `ChatGPT Image Sep 18, 2026, 02_24_31 PM.png` — is a
timestamp, not a name. It survives in `manifest.json` and nowhere else.

## manifest.json

What each file was called before it was filed here, who made it, its size and its sha256. This is
what stops the rename destroying the only link back to the export it came from: without it,
"which generation was this?" has no answer six months out.

`build_browser.py` names the page and `manifest.json` names the provenance. They are separate
because they answer different questions, and `tests/test_concept_art_manifest.py` checks they
still agree in both directions — every declared image has a manifest row, every manifest row is
claimed by the table, and every committed file still hashes to what the manifest says.

## What is not in here

`_reference/` is git-ignored. It holds third-party images kept for inspiration and never used in
the game. Looking at one is fine; committing it would put somebody else's work in every clone
forever, and the credit we would owe beside it would probably name the wrong person — a Pinterest
link is a re-post, not an artist.

So the manifest keeps the URL and the file stays out. An entry marked `optional` in the table is
embedded when the file is present and drawn as a card linking to its source when it is not:
complete on the machine that found the image, honest on a fresh clone, an error in neither case.
The test enforces the rule rather than trusting it — anything the manifest marks
`"committed": false` must live under a path `.gitignore` covers.

## The figures are levelled when the page is built

Each figure was drawn on its own, so each arrived on its own plinth at its own scale — the four
bases ranged over 24% and one was on a different canvas entirely. Four miniatures whose bases
disagree read as four unrelated pictures rather than as a set.

`build_browser.py` fixes that at build time rather than by editing the files. It measures each
figure's plinth from the alpha channel — the widest row of the base, not its bottom edge, because
the base is an ellipse seen from slightly above and its bottom edge is much narrower than its true
width — scales every figure so those widths agree, and stands them all on one floor line.

The target is the NARROWEST plinth in the set, so levelling only ever scales down. Scaling up
would enlarge a source, which is the one operation here that invents detail nobody drew.

Two consequences worth knowing. The figures end up at different heights, which is correct: a
miniature is identified by the base it stands on, and the figure above it is free to be as tall as
it is. And the files on disk are still exactly what the generator produced — the rule that makes
them agree lives in one place in the script, where it can be read and changed, rather than being
baked into pixels.

## Two things here that are not files here

The four portraits are production art, read from `ui/assets-gothic/portraits/` through the same
seat cast the board build uses — `gen_game_view.SEAT_PORTRAITS` over
`population_sets.SEAT_ORDER`. Re-deal that cast and this page follows it instead of disagreeing
with it. Concept art is filed here; production art is borrowed, never copied.

The duty wheel is geometry, not a picture. It is drawn as vector straight from
`tools/ui_debug/duty_wheel_v2_1500_layout.json`, so it costs 58 KB instead of a megapixel, stays
exact at any zoom in the overlay, and cannot drift from the layout the way a screenshot would.

## The output is not committed

It lands in `generated/`, which `ui/.gitignore` already covers for the whole `ui/` tree, and at
about 11 MB with every image embedded it is the last thing that should go into the repository.
Rebuild it instead; it takes a few seconds.
