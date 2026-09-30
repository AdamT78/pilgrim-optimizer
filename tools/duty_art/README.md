# Duty action art

Each duty's two actions are **one drawing, cropped twice**. A single wide master holds the whole
scene; the left and right production images are overlapping windows onto it. That is the entire
idea, and the overlap is the reason it works: two separately generated illustrations of "a priest
receiving coins" and "a priest at prayer" look like two pictures of two places, while two windows
onto one continuous environment look like one place seen twice. The shared middle ground is what
the eye uses to tie them together.

For Clerical the left window is **Gain Piety** and the right is **Gain Coins**.

## The workflow

1. Generate one continuous wide master for the duty, holding both actions.
2. Save it under `ui/board_v2/duty_actions/<duty>/masters/` and keep it forever — see below.
   It sits under `ui/board_v2/` beside the module it belongs to, which is also what keeps CI
   cheap: that path is routed as design-only, so adding art runs the layout lab lane in seconds
   rather than the full engine suite.
3. Crop it with `crop_duty_master.py` into the two overlapping action images.
4. Save those under `ui/board_v2/duty_actions/<duty>/<action>/`.
5. Load the pair into the Duty Wheel Layout Lab (`ui/board_v2/layout_lab/`), DUTY ART PAIR.
6. Judge them at real game size, in the composition, not in an image viewer.
7. If the slot dimensions later change, **re-crop the master** — do not re-generate the art.

Step 7 is why step 2 says forever. A crop is reversible as long as the master exists; a
regeneration is not, because the same prompt does not produce the same picture twice. The master
is the negative and the crops are prints.

## Running it

```
python tools/duty_art/crop_duty_master.py \
  ui/board_v2/duty_actions/clerical/masters/clerical_master_v01.png \
  --out-dir /tmp/clerical_crops \
  --left-name clerical_gain_piety_v01.png \
  --right-name clerical_gain_coins_v01.png
```

Needs `pillow`. Write to a scratch directory and move the files in deliberately, so a test run
can never overwrite a production crop.

Defaults are **1120 x 560**, the action slot's working size. Both crops are vertically centred on
the master so they stay on the same horizon; the left one is anchored to the left edge, the right
one to the right edge, and whatever they share in the middle is the overlap.

## What the committed Clerical pair actually is

The master is `clerical_master_v01.png`, **2172 x 724**. With the defaults the script produces:

| | box | |
| --- | --- | --- |
| vertical | `y = 82 → 642` | centred: `(724 - 560) // 2` |
| left | `x = 0 → 1120` | anchored left |
| right | `x = 1052 → 2172` | anchored right |
| overlap | **68 px** | `1120 * 2 - 2172` |

Re-running the command above reproduces `clerical_gain_piety_v01.png` and
`clerical_gain_coins_v01.png` **pixel for pixel**, which is the test in
`tests/layout_lab/test_duty_art_crop.py`. It does not reproduce them byte for byte: PNG encoders
differ between Pillow versions, so the test compares pixels rather than hashes.

An earlier master was 2048 x 682 and gave `y = 61 → 621`, a right box of `928 → 2048` and a 192 px
overlap. Those numbers appear in older notes and in the script's own docstring; they describe that
master, not this one. The overlap is not a constant — it falls out of the master's width, and a
wider master yields less of it. If you want a specific overlap, size the master for it:
`overlap = 2 * crop_width - master_width`.

## Naming

Lowercase snake_case, zero-padded versions.

```
<duty>_master_vNN.png          clerical_master_v01.png
<duty>_<action>_vNN.png        clerical_gain_piety_v01.png
                               produce_gain_wheat_v01.png
                               build_roads_build_shrine_v01.png
```

Never overwrite an older variant because a newer one is preferred. Add `v02` and leave `v01`
where it is: preference is not a fact about the file, and the comparison you want to make in three
weeks is the one you threw away.

The filenames are for humans and for the repository. **The studio does not parse them** — which
file lands on which action is decided by which file input you chose, never by the name. A file
called `clerical_gain_coins_v01.png` dropped into the Action A input becomes Action A's artwork,
because assuming otherwise would silently disagree with what you did.

## Where the art belongs

Artwork belongs to a **duty's action**, not to a screen position:

```
S.duties.clerical.actionA.scenic       Gain Piety
S.duties.clerical.actionB.scenic       Gain Coins
```

The two large boxes on the stage are display slots that normally show Action A on the left and
Action B on the right. They own geometry — position, size, fit — and nothing else. Moving a box
does not move the artwork's identity, and there is deliberately no `duty.leftImage`.
