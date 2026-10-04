# Duty action art

This folder holds **`file_seals.py`**, which files the wax seals. That is all it holds now; the
seals section below is the live half of this note.

## The crop workflow is gone

It used to hold `crop_duty_master.py` as well, and the idea behind it is worth recording even
though nothing runs it any more. Each duty's two actions were **one drawing, cropped twice**: a
single wide master held the whole scene and the left and right production images were overlapping
windows onto it. The overlap was the point — two separately generated illustrations of "a priest
receiving coins" and "a priest at prayer" look like two pictures of two places, while two windows
onto one continuous environment look like one place seen twice.

What replaced it is simpler, and is why the script went: each action is now generated as its own
picture at the card's exact 2:1 and used whole. No master to cut, no gutter to hide a seam in, no
shared scene, and nothing in the pipeline that has to agree with `geometry.py` about the card's
size. The last cards that came from a cut — Clerical's v03 pair and Ordination's v02 — were
replaced and then deleted, and the script and its guard went with them.

The masters those cuts came from are still committed and always will be. A crop is reversible as
long as the master exists; a generation is not, because the same prompt does not produce the same
picture twice. The master is the negative, and the prints it made are gone.

## Filing a card today

1. Generate one picture per action at the card's own 2:1 — 1774 x 887 is what the fourteen on the
   board are — and use it whole.
2. Save it under `ui/board_v2/duty_actions/<duty>/<action>/`, the folder `slotFolders` in
   `ui/board_v2/attribution.json` names. It sits under `ui/board_v2/` beside the module it belongs
   to, which is also what keeps CI cheap: that path is routed as design-only, so adding art runs
   the lab lane in seconds rather than the full engine suite.
3. Give it an entry in `attribution.json` with an explicit `slot`. **That is wiring, not
   bookkeeping**: a picture with no entry is dropped with "no slot recorded, left out".
4. Rebuild the action board and judge it at real game size, in the composition, not in an image
   viewer.
5. Record the prompt under `ui/board_v2/duty_art_lab/prompts/panels/` and point the entry's
   `reproducibleBy` at it.

**Provenance default.** Unless a file's entry in `ui/board_v2/attribution.json` says otherwise, an image in
`ui/board_v2/` was generated with ChatGPT (OpenAI) and carries the `openai-generated` licence.
Anything with a different origin has to say so in its own entry. A new image with no entry at all
is a gap rather than an implicit default, and `tests/layout_lab/test_board_v2_attribution.py`
fails on one.

## What the cut actually did, for the record

Kept because the masters are still here and someone may want to know what was taken off them. The
crop was vertically centred on the master so both halves stayed on the same horizon; the left box
was anchored to the left edge, the right to the right edge, and the middle they shared was the
overlap — `overlap = 2 * crop_width - master_width`, so it was never a constant and a wider master
yielded less of it.

The window came from `geometry.py` at cut time, which is why one recipe gave different sizes in
different months: Ordination's pair was recorded as 1065 x 522, the files on disk were 1071 x 536,
and re-running it on the last day it existed gave 1069 x 534. Three eras of one card, not three
pictures — and the trap any fixed table of numbers here would set for a later reader.

## Naming

Lowercase snake_case, zero-padded versions.

```
<duty>_master_vNN.png          clerical_master_v01.png
<duty>_<action>_vNN.png        clerical_gain_piety_v01.png
                               produce_gain_wheat_v01.png
                               build_roads_build_shrine_v01.png
```

Never overwrite an older variant because a newer one is preferred. Add `v02` and leave `v01`
where it is: the comparison you want to make in three weeks is the one you threw away.

**Which version draws is decided by the folder convention**, not by a setting. For anything in a
versioned folder the newest `vNN` wins; for the Tithe resources, whichever file is sitting at the
stable name wins. Both are facts about the files, which this note used to deny -- and that is
deliberate while nothing needs to flip back and forth. `metadata/action_board.json` already has a
`seals` key, written by the board's save and read by nothing; the day you want an older version
preferred without deleting the newer one, that is the file to start reading, and this paragraph is
the note saying so.

The filenames are for humans and for the repository. **The studio does not parse them** — which
file lands on which action is decided by which file input you chose, never by the name. A file
called `clerical_gain_coins_v01.png` dropped into the Action A input becomes Action A's artwork,
because assuming otherwise would silently disagree with what you did.

## The seals, which are now the only thing here

A duty also has **seals**: the small red wax marks in its tile on the action board, one per
action, under `ui/board_v2/duty_actions/<duty>/seals/`. They were never crops of a master and there
is no overlap to think about -- each is generated on its own, square and transparent.

Two things about them are worth knowing before adding any.

**They are recorded in the same vocabulary as the art**, `left` and `right`, under the same duty.
Every tool that walks `duty_actions/` therefore has to step over the folder, or it inlines a 78px
wax seal as a 590 x 295 action card -- which the layout lab did, for one commit, until a test
caught it. The folders a walk must skip are listed in `ui/board_v2/attribution.json` under
`nonSlotFolders`, read by all three generators and by `tests/layout_lab`. One list.

**Every set has arrived at a different size inside its own square** -- 0.939, 0.959, 0.963, 0.967,
0.969, 0.976, 0.982, 0.988, 0.998 of it. Two seals in one tile at the same `SEAL` then differ by
up to six per cent, which reads as a fault in the layout rather than a difference in the drawings.
`SOLID_FRACTION` in `ui/board_v2/action_board/geometry.py` is what every disc on this board is
held to -- the three coins, the three grey resource seals and the fourteen red ones alike -- and
`tests/action_board` measures the files against it.

### Running it

```
python tools/duty_art/file_seals.py duty clerical \
  ~/Downloads/red_seal_clerical_piety.png \
  ~/Downloads/red_seal_clerical_silver_smith.png
```

One image per action, in slot order. How many a duty takes is not the script's opinion:
`slotFolders` says, and Taxation and Allocation have one action each, so giving either of them
two files is refused rather than inventing a second slot. `--dry-run` measures and reports
without writing. Needs `pillow` and `numpy`.

The Tithe column's three grey seals go through the same tool, `file_seals.py tithe <wheat>
<stone> <silver>`, and follow a **different folder convention on purpose**. A duty's seal print
carries a version and the board draws the newest, so a new one supersedes by arriving. A
resource's print has a stable name -- `generate_action_board` looks it up as `seal_wheat` -- so
there is nothing to choose at draw time: a new one supersedes by replacing the print, the version
lives on the master, and the print's own record names the master it was exported from.

It normalises each image about its own centre, keeps the untouched original under `seals/masters/`
for the same reason the action art keeps its master, writes the next free `vNN` rather than
overwriting anything, and adds both to `attribution.json`. It refuses outright if a normalised
file lands outside tolerance, instead of filing something the test would catch later.

The same four steps happen when you drop a picture onto a seal in
`ui/board_v2/action_board --serve` and press save -- same folder, same filenames, same shape of
entry -- so a seal filed either way lands beside the other.

## Where the art belongs

Artwork belongs to a **duty's action**, not to a screen position:

```
S.duties.clerical.actionA.scenic       Gain Piety
S.duties.clerical.actionB.scenic       Gain Coins
```

The two large boxes on the stage are display slots that normally show Action A on the left and
Action B on the right. They own geometry — position, size, fit — and nothing else. Moving a box
does not move the artwork's identity, and there is deliberately no `duty.leftImage`.
