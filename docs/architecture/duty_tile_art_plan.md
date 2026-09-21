# Duty tile art: where it stands and what comes next

A plan rather than a record, which is why it is here and not in `docs/design/` — that folder
keeps the reasoning behind decisions already taken. Written 2026-09-21, after the placement
sheet grew a wheel view, a frame and a ground picker.

## What exists today

Three pages share one set of rules. `tools/ui_debug/duty_sculpt_rules.js` owns the formation, the
seat order, the depth cue and the tile layout; `generate_duty_board_check.py` owns the art loading
and the validators; `generate_placement_sheet.py` tunes and saves; `generate_duty_sow.py` plays on
what was saved and has no settings of its own.

Two files carry every decision. `ui/assets-gothic/metadata/duty_placement.json` holds spread,
set-back, rank gap, seating order, the marking, the depth cue and the frame.
`ui/assets-gothic/metadata/duty_grounds.json` holds which duty stands on which plate and how each
plate is toned down. Both are written by the sheet's save button and read by everything else.

Numbers worth not re-deriving, all in real device pixels at the 210 px sculpt size:

| | |
|---|---|
| a full tile of five sculpts | 311 wide by 262 tall |
| the tile as drawn, banner included | 369 across, 410 down |
| a tile's share of the wheel | 633 square |
| spare, so how far the wheel could tighten | 224 per tile |
| the frame, provisional | 320 by 390, base 40 below the floor |

## A standing rule for new assets

**Every new asset gets an entry in `ui/concept/build_browser.py`.** That page is declared and not
globbed, on purpose: the `SUBJECTS` table names every file expected, so a file that is never added
is not quietly absent from the browser, it is simply invisible. Adding an asset means adding it to
the subject it belongs to, or opening a new subject when it belongs to none — and the file is then
named for what it *is*, because the table supplies both halves of `<subject>/<kind>.png`.

The two ground plates added on 2026-09-21 are the first case and are done both ways: registered in
`ui/assets-gothic/attribution.json`, which is what CI checks, and entered in `build_browser.py`
under a new `grounds` subject, which is what makes them visible. Provenance and visibility are two
different records, only one of them is enforced, and the unenforced one is the one that quietly
stops being true.

## The work, in the order it wants doing

### 1. Choose the camera angle — SETTLED AT 32 DEGREES

**This gated almost everything below. It is decided; what follows is how, and why not 29.**

The numbers this section first carried were wrong, and wrongly in the same direction. Measuring an
inset column instead of the extreme one costs height, because the ellipse has already begun to
drop there — so a drawn 10 degree disc measured back as 6.5. Corrected, the sculpts sit near 9 to
10 degrees rather than 6, and the ground plates near 32 rather than 38. The finding stands that
figures look pasted onto the ground until one side moves, and that the sculpts are the side that
moves; only the sizes changed.

The target is 32 because that is where this generator lands and the ask stopped steering it. Two
batches of ten hooded figurines, asks three degrees apart with reference cards drawn to match,
produced means of 32.1 and 31.9 — three degrees of instruction bought two tenths of a degree of
result. Ground plates converge on the same place without being asked: nine style-varied plates
averaged 32.6. Both halves of the board already agree at 32, so any other target has to be fought
for on both sides at once.

Two numbers were tried before it and neither survived. 30 was picked from an uncorrected
measurement; 40 from the corrected one, by arithmetic alone. 29 came from actually compositing
sculpts at 210 px on a plate at 320 px and looking — which was the right method and produced a
number the generator would not reach. That composite is still worth its place in the record for
what it ruled out: below about 20 degrees a ground plate stops reading as a floor and becomes a
puddle, and the failure is much more visible on the flat side than on the steep side.

Two things about the generator are worth writing down, because they are not obvious and both cost
a round to learn. A single word of style is worth degrees: swapping "limestone" for "slate" in an
otherwise identical prompt moved a plate 4.4 degrees, against a within-style scatter near 1. And a
figurine's camera cannot be steered by text at all — every photograph of a miniature ever taken is
at eye level, and that prior wins. What did work was attaching a diagram of the base alone, drawn
at the wanted ellipse ratio, with the instruction to keep it exactly as it is; the base pins the
camera, and the figure follows the base. Drawing any of the FIGURE into that diagram was tried
three times and produced two traffic cones and a lampshade, so the reference carries the base and
the empty room above it and nothing else.

`tools/ui_debug/generate_asset_check.py` holds the target as `TARGET_DEGREES`, with a test that
fails if it drifts. It moves when a composite says to, not when a batch misses it.

### 2. A tool to create and validate sculpts and ground plates — BUILT

`tools/ui_debug/generate_asset_check.py`. Drop a PNG on the served page, or `--scan` a folder of
them in one pass. What it reports, and what it refuses to report, is in `tools/ui_debug/README.md`.
Two of its findings changed this document: that the camera measurement was biased, and that
height over plinth width is a PROJECTED quantity which shrinks as the camera rises, so figures at
two different cameras cannot be compared on it without dividing the camera out first.

One piece of upkeep it needs when the set is redrawn: its reference band is computed from whatever
sits in `ui/concept/`, so until the four seats are replaced every new sculpt is judged against art
being discarded, and reports a height gap that is real but no longer relevant.


Drop a generated PNG onto a page, get back its measurements and a verdict. For a sculpt: plinth
width, wall height, the plinth ellipse and so the camera angle, overall height, the height-to-
plinth ratio, and the alpha rim check that `sculpt_metrics.py` already does. For a plate: ink box,
the standing line, and whether five sculpts at the current spread fit its surface.

This comes straight after the angle because it is what makes the redraw cheap. Generating sculpts is iterative, and
without a verdict each round trip is a guess. `check_sculpt.py` already does most of the sculpt
measuring from the command line; the work is a spec to measure against, a page to drop files on,
and the plate half, which does not exist at all.

Open questions: what the tolerances are measured against — a chosen spec or the spread of the
current set; and whether the page only reports, or also files the asset, which means registering
attribution and running `make_tray_figures.py`. Filing needs the `--serve` path, since a page
opened from disk cannot write to the repository.

### Not doing: a 3D pipeline

Generating actual 3D models and screenshotting arrangements from code was considered and set aside.
It would solve the camera problem outright — one scene, one camera, every figure and plate
guaranteed consistent, and rotations for free rather than begged for. It is the right answer
eventually and the wrong one now: it replaces a pipeline that works with one that has to be built,
learned and paid for before a single tile improves. The 2D route has since been made to hold a
camera to within a couple of degrees across both sculpts and plates, which was the thing in doubt.
Worth revisiting when the board is otherwise finished, or if per-seat variety turns out to be
unreachable by prompting.

### 3. The hand, and the City

These are one piece of work rather than two, because lifting from the City is what fills the hand.

The City is not a duty — `validate_duty_tiles` refuses it as a duty position, so no majority is
ever computed there and nothing on that tile is a contest. It is supply. Measured over thirty
random three-player games, a duty tile holds five or fewer 99.73% of the time and never exceeded
seven, while the City is over five nearly half the time and starts the game at fifteen, because
`_starting_player_state` gives every player five there. So the City needs its own idiom: counts
per player, or a stack with a different rule, but not the duty-tile formation.

The hand follows from it. One player's own City pile never exceeded six in those games and is five
or fewer 99.6% of the time, but the structural ceiling is their whole force, so design for six
comfortably and a dozen without breaking. The current tray is a vertical column that ran off the
screen at three 210 px sculpts; it wants to be horizontal, chunked so six reads as three and three
rather than as six, with the count also given as a numeral. Something carried — a plank, a tray, a
strip of sacking — rather than a drawn hand, which would have to be enormous to hold nine figures.

Placement is the open question: bottom-centre is where a hand lives and keeps every drag short,
but covers the southern tiles while you hold something. Tightening the wheel first would give the
strip a band of its own and dissolve the trade-off.

The hand is **different artwork per seat**, not one shape recoloured. That is a decision, and it
has a consequence worth stating now rather than discovering: it is four assets rather than one, it
multiplies with any later change to the idiom, and each carries its own `build_browser.py` entry.
It also means the tray's proportions cannot be tuned against a single picture — whatever holds six
acolytes has to hold them in all four.

### 4. Majority

Cheap, independent of the art, and testable now: both ideas below work on the sculpts that
already exist.

**Only majority gets a cue, initially.** Parity and minority get nothing. That is worth writing
down because the engine draws three distinctions, not two: `duty_strength()` compares a player's
count against `max(opponent_counts)` and returns majority, parity or minority, and they carry
different values and a different silver cost. Showing only one of the three is a deliberate
simplification rather than an oversight, and it is the right way round — majority is the state
worth spotting across the table, and a board that marks all three is a board covered in marks.
Note that it also sidesteps the awkward case: parity is a tie, so more than one seat would wear it
at once.

Two ideas to try, in this order:

1. **Glowing acolytes.** The cue sits on the figures, which are the thing being counted. A filter
   on the sculpts, so it costs no new art and can be tried this afternoon.
2. **A banner behind them, in the seat's colour** — hanging on a wall behind the acolytes rather
   than lying on the floor. Reads at a distance in a way a glow may not, and gives the tile a
   back wall, which the frame currently has no content for. It is new art per seat, and it has to
   sit inside the frame and behind the figures, so it interacts with step 1's angle and with the
   frame's own dimensions.

The second is the more interesting one for the look of the board and the more expensive one to
try, which is why the glow goes first: it answers "is marking majority enough" before anything is
drawn.

### 5. Stacking above five

Held until the sculpts are redrawn, because what makes a stack readable is the figures.

The formation knows five and no more — `dutyFormation` returns five slots for any larger count,
silently, which is why the sow page declines a sixth rather than drawing one. Duty tiles exceed
five in 0.27% of random-play states, but random play does not chase majorities, so that is a floor.
The useful reframe from earlier: the countability limit is per seat, not per tile. One player never
had more than four of their own on a duty tile, and a seven-tile read as 3+2+2 may be perfectly
legible when seven in a row would not be. That is an argument for extending the ranks rather than
for a count badge, and it makes `grouped` ordering load-bearing rather than a preference.

Room is not the constraint: rows hold three, so 3+3+2 reaches eight inside the current cell. The
depth cue is — at `full_at` 52 a figure at 104 px is 87% hazed and one at 156 is 95%, so a fourth
rank and a fifth are indistinguishable. Three ranks is the honest ceiling unless `full_at` grows
with the number of ranks, which costs separation between the first two.

### 6. Clickable floor objects instead of icons under the banner

To explore, once the frame and the grounds have settled, since the objects would sit on the ground
and inside the frame.

The current idea is an action icon row under the banner, which the board checker draws. Replacing
it with objects on the floor makes the tile itself the control. Questions before a sketch: does an
object replace the icon only, or the banner title as well; is the object the button, or does it
merely mark where the button is; and what does a duty with two actions look like — the board
checker already shows several tiles with two icons, and The City with none.

### 7. A looser arrangement

Explicitly later. Worth recording one tension: the current rules exist to make groups countable,
and `grouped` ordering is what lets a seven-figure tile read as three small groups. Randomness
bought at the cost of that read would make majority harder to see, which is the one thing the tile
has to say. A jitter within each slot — a degree or two of rotation, a few pixels of offset — buys
most of the life without touching which figures stand where.

## Carried over, unrelated to the art

`tools/ui_debug/README.md` keeps a prose section per tool and now owes four: the board checker, the
placement sheet, the sow page and the grounds. `tools/rebuild_generated_pages.py` fails when a page
in `generated/` was built by nothing, and ten now are — the single-page tools were each added with
their own command and never wired into the overview, so the README promises a guarantee the command
cannot currently deliver. And `noun_wagon_7392556.svg` is still untracked at the repository root.
