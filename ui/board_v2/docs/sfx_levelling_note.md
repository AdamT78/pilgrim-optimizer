# Levelling the board's sounds by loudness

**Status: measured and applied.** `gainDb` is on every sound record, `sfx_lab/sfx_levels.py`
produces it, and the bench plays it behind a toggle. The board does **not** read it yet.

Measured 2026-10-13 against 38 shipping clips. This note exists so the reasoning does not have
to be reconstructed, and so the three traps in it are not rediscovered the hard way.

---

## 0. The four words, and which control moves which

This note and `sfx/README.md` use four terms for four different numbers, and until now defined
none of them. They apply in this order, and nothing later can undo something earlier:

**the file → trim → group level → monitor gain → your speakers**

**A trim** is the `gainDb` on a sound's own record: how much louder or quieter to play that
file than it is stored, in decibels. `0.0` is the file as encoded, `−7.0` plays it 7 dB
quieter, `+4.0` plays it 4 dB louder. **It never touches the file** — that is what every record
means by *"the container and nothing else: no trim, no fade, no level change"*. The `.ogg`
bytes stay exactly as encoded, so they remain verifiable against their sha256 forever, and a
level can be reconsidered without re-encoding anything or losing the chain back to the source.
The word is a mixing desk's: the trim is the input stage, which sets how hot a source arrives
before anything downstream happens to it. **The ambient bench labels its per-bed slider
"ambient level", and that slider edits the trim.** Three names for one number is one too many;
the field name `gainDb` is the one a machine reads and the one to trust.

**A group level** is the `groupDb` in `attribution.json`'s `ambientGroups`, one per duty
action: where that whole action sits against the other actions. It is applied as a single gain
node that every track of the action feeds, so it scales all of them equally and **cannot change
a balance already set between them**. The bench calls it the "duty action level". A cue has no
group level; this is a bed idea only, because only beds come in groups.

**The two add, which means they can be folded into one.** A track is heard at
10<sup>(trim + group)/20</sup>, a single product of two gains, so adding an action's group
level onto every one of its trims and setting the group to 0 changes nothing audible — and
leaves every ratio *inside* the action alone, because the same number went onto every trim.
Both controls step in 0.5 dB, so the sum is a multiple of 0.5 and nothing rounds. The bench has
a **fold** button for it, and it is how a round of matching gets committed: afterwards the
trims are the whole story and the action faders start again from zero. **It is exact only while
every folded trim stays inside the slider range** (−60 to +30). A clamp there would move one
track and not its neighbours, which is the one thing the group fader exists to prevent, so an
action whose fold would clamp is left alone and named rather than clamped. *Folding makes an
action's recorded `summedTruePeakDbtp` stale*, because that figure was rendered at the filed
trims; re-run `sfx_levels.py --groups --write` once the new trims are committed.

**The monitor gain** is `MONITOR_DB` on the bench, currently +6 dB, and it is **not a mix
value**. Everything on that page plays at board levels, and the cues sit twenty-odd decibels
under the files they came from, so without it the page is too quiet to judge. It is a fixed
constant rather than a knob on purpose: one slider on a page, and it can only move the thing
being decided. It is never saved and never reaches the board.

**The ceiling** is −1 dBTP, and it is **a rule about what may be filed, not a description of
what is filed**. No cue may be trimmed past it. Reading it as though some cue sits there is the
specific mistake section 11 records: the loudest cue in this tree after its own trim is
−3.97 dBTP, and multiplying against −1 instead produced a clipping alarm that measurement
then showed to be false.

**Two of the four are judgements and two are not.** A trim and a group level are set by ear and
there is no target for either — section 11 explains why a bed target was tried and falsified.
The monitor gain and the ceiling are fixed, and moving them to make something fit is the error
rather than the fix.

---

## 1. Peak was never measuring loudness

The set was levelled by peak from the beginning, and the ear kept disagreeing with the records.
Measured properly, **31.9 dB of loudness variation was hiding inside 17.1 dB of peak variation**.

The clearest case is not one of the obviously quiet clips:

| | peak | loudness (M200) |
|---|---|---|
| `misc/rock_dropping` | **−4.0 dBFS** | **−32.1 LUFS** |
| `buildings/bank` | −7.0 dBFS | −18.3 LUFS |
| `buildings/chapel` | −16.4 dBFS | −30.5 LUFS |

`rock_dropping` peaks *louder* than Bank, Brewery or Grain Store — nothing in its entry
suggested a problem — and is the third quietest thing in the tree, within 2 dB of Chapel. It is
a rock landing and then air. Peak sees the impact; the ear integrates the air.

The same failure runs the other way. Silversmith and Produce Stone are **0.0 dB apart at the
peak** and 9.5 dB apart in loudness. And the Chapel/Silversmith tile, which `sfx/README.md`
recorded as 16.1 dB apart by peak, is **26.1 dB apart** by loudness — the recorded figure
understated it by ten decibels.

---

## 2. The measure: M200

**The loudest 200 ms of K-weighted energy, ITU-R BS.1770-4 weighting, ungated.** Three choices,
each of which changes the answer.

### K-weighting, derived at the file's own rate

BS.1770's pre-filter — a +4 dB shelf at 1.68 kHz and an RLB high-pass at 38 Hz — approximates
the ear's frequency response. The standard publishes coefficients for 48 kHz. **A quarter of
this tree is 24, 44.1, 96 or 192 kHz**, so the tool re-derives them from the analogue
prototypes at each file's rate. Reusing the 48 kHz numbers is a silent error of a decibel or
two, on exactly the clips most likely to be unusual.

### Ungated

BS.1770's absolute and relative gates exist to stop silence dragging down an hour of programme.
On a 70 ms interface cue the relative gate can discard the cue itself. Gating is wrong at this
scale and is switched off.

**The same answer holds for a long ambient bed, for the opposite reason.** A cue is too short to
survive the gate; a bed is too even to need it. Measured against the gated figure:

| material | ungated | gated | delta | blocks kept |
|---|---|---|---|---|
| cathedral room tone | −40.61 | −40.59 | +0.02 | 247 of 247 |
| windmill, continuous | −19.70 | −19.68 | +0.02 | 247 of 247 |
| windmill, gusty span | −21.19 | −21.26 | −0.08 | 247 of 247 |
| fire in a metal stove, 25 s loop | −35.97 | −35.96 | +0.01 | 247 of 247 |
| drum track (control, not ambient) | −11.02 | −10.47 | +0.55 | 174 of 197 |

The gate only bites on material with more than 10 LU of internal spread, which the control
shows. The argument is not that gating makes no difference here; it is that where it *would*,
it discards the quiet floor the player hears for most of the clip and levels the bed by its
gusts. **Ungated for both classes**, so a bed and a cue are at least measured in the same unit.

#### "A bed is continuous by construction" was the reason, and it is no longer true

That sentence stood here from four beds that were each one continuous recording, and it stopped
being true the moment a duty action started taking **stems**. A stem is a layer of a scene —
grain handled, coins counted, beads told, robes moving — and a layer of a scene is mostly
silence waiting for the other layers. Measured across all sixty-three ambient tracks as they
stand:

| track | ungated | gated | delta | blocks kept |
|---|---|---|---|---|
| `allocation_actionA/allocation_wind` | −36.97 | −37.16 | +0.19 | 167 of 167 |
| `clerical_actionA/devotion` | −30.79 | −30.79 | −0.00 | 347 of 347 |
| `ordination_actionB/night_city` | −46.13 | −46.13 | +0.00 | 357 of 357 |
| `clerical_actionA/candle` | −53.69 | −53.69 | +0.00 | 252 of 252 |
| `clerical_actionB/silversmith` | −32.77 | −32.77 | +0.00 | 247 of 247 |
| `give_alms_actionA/alms` | −38.37 | −38.36 | −0.01 | 247 of 247 |
| `produce_actionB/quarry_wind` | −33.50 | −33.49 | −0.01 | 347 of 347 |
| `build_roads_actionB/wind` | −31.11 | −31.09 | −0.02 | 247 of 247 |
| `build_roads_actionA/wind` | −39.31 | −39.29 | −0.02 | 307 of 307 |
| `produce_actionA/wind` | −33.83 | −33.80 | −0.03 | 347 of 347 |
| `produce_actionA/field_rustle` | −36.17 | −36.15 | −0.03 | 347 of 347 |
| `produce_actionB/oil_lamp_flame` | −40.49 | −40.30 | −0.19 | 333 of 347 |
| `build_roads_actionA/oil_lamp_flame` | −44.29 | −44.02 | −0.27 | 327 of 347 |
| `produce_actionB/background_workers` | −41.57 | −40.96 | −0.62 | 303 of 347 |
| `give_alms_actionB/donate_building` | −49.68 | −48.91 | −0.77 | 269 of 322 |
| `allocation_actionA/footsteps` | −30.62 | −29.78 | −0.84 | 233 of 282 |
| `build_roads_actionA/worker_footsteps` | −38.59 | −37.35 | −1.24 | 262 of 347 |
| `allocation_actionA/wool_robe` | −31.08 | −29.29 | −1.79 | 187 of 282 |
| `ordination_actionB/footsteps` | −35.89 | −34.03 | −1.86 | 231 of 357 |
| `produce_actionA/sickle_cutting` | −39.58 | −36.41 | −3.16 | 167 of 347 |
| `taxation_actionA/room` | −38.16 | −34.77 | −3.40 | 134 of 297 |
| `build_roads_actionA/ox_cart_mechanics` | −38.00 | −34.30 | −3.70 | 149 of 347 |
| `ordination_actionB/distant_cart` | −45.19 | −41.16 | −4.03 | 141 of 357 |
| `build_roads_actionA/gravel` | −35.94 | −31.76 | −4.18 | 132 of 347 |
| `build_roads_actionB/fabric` | −44.09 | −39.89 | −4.19 | 95 of 247 |
| `ordination_actionB/two_horses` | −44.73 | −40.25 | −4.47 | 127 of 357 |
| `produce_actionA/straw_workers` | −44.05 | −39.16 | −4.88 | 113 of 347 |
| `build_roads_actionB/gallows_rope` | −49.35 | −44.44 | −4.91 | 80 of 247 |
| `build_roads_actionB/tinkering` | −42.09 | −37.16 | −4.94 | 80 of 247 |
| `build_roads_actionA/ox_breathing` | −42.53 | −37.52 | −5.01 | 110 of 347 |
| `produce_actionB/stone_sleigh` | −40.12 | −35.03 | −5.09 | 108 of 347 |
| `taxation_actionA/barn_creaks` | −44.40 | −39.19 | −5.20 | 90 of 297 |
| `produce_actionB/sleigh_crew_footsteps` | −48.22 | −42.89 | −5.33 | 102 of 347 |
| `build_roads_actionA/far_work` | −52.01 | −46.64 | −5.37 | 101 of 347 |
| `build_roads_actionB/gallows_timber` | −46.95 | −41.32 | −5.64 | 68 of 247 |
| `build_roads_actionA/rammers` | −35.88 | −30.02 | −5.86 | 90 of 347 |
| `build_roads_actionA/ox_cart_stones` | −55.15 | −48.82 | −6.33 | 81 of 347 |
| `ordination_actionB/staff` | −48.86 | −41.87 | −6.99 | 71 of 357 |
| `ordination_actionB/distant_dogs` | −48.96 | −41.95 | −7.01 | 71 of 357 |
| `clerical_actionA/rosary` | −46.71 | −39.55 | −7.16 | 67 of 347 |
| `produce_actionB/quarry_footsteps` | −59.90 | −52.65 | −7.26 | 65 of 347 |
| `produce_actionB/oil_lamp_rattle` | −46.93 | −39.51 | −7.42 | 63 of 347 |
| `allocation_actionA/keys` | −35.04 | −27.22 | −7.82 | 47 of 282 |
| `produce_actionA/sheaf_handling` | −39.58 | −31.48 | −8.10 | 54 of 347 |
| `taxation_actionA/wheat` | −47.40 | −39.27 | −8.13 | 46 of 297 |
| `produce_actionB/moth` | −53.95 | −45.59 | −8.36 | 51 of 347 |
| `build_roads_actionA/horse_snorts` | −44.88 | −36.18 | −8.70 | 47 of 347 |
| `produce_actionA/distant_rooster` | −45.25 | −36.45 | −8.80 | 46 of 347 |
| `build_roads_actionB/crows_ravens` | −45.75 | −36.71 | −9.04 | 31 of 247 |
| `taxation_actionA/coins` | −36.74 | −27.55 | −9.19 | 36 of 297 |
| `produce_actionA/stalk_brushing` | −49.46 | −40.06 | −9.40 | 40 of 347 |
| `build_roads_actionA/oil_lamp_rattle` | −48.48 | −38.97 | −9.51 | 39 of 347 |
| `produce_actionB/power_strikes` | −36.74 | −26.53 | −10.21 | 33 of 347 |
| `produce_actionB/quarry_hoist` | −54.88 | −43.76 | −11.12 | 27 of 347 |
| `produce_actionB/chisel_reposition` | −51.22 | −39.80 | −11.43 | 25 of 347 |
| `build_roads_actionB/monk_robe` | −47.86 | −36.23 | −11.63 | 17 of 247 |
| `ordination_actionB/door_close` | −28.84 | −15.90 | −12.94 | 18 of 357 |
| `produce_actionB/debris_cleave` | −42.51 | −29.21 | −13.30 | 16 of 347 |
| `produce_actionA/nearby_raven` | −51.58 | −38.21 | −13.36 | 16 of 347 |
| `ordination_actionB/rats_crossing` | −46.57 | −32.81 | −13.76 | 15 of 357 |
| `ordination_actionB/rat_squeaks` | −48.62 | −34.82 | −13.80 | 15 of 357 |
| `produce_actionB/distant_owl` | −51.21 | −36.21 | −15.00 | 11 of 347 |
| `ordination_actionB/bottle_knock` | −54.10 | −37.04 | −17.06 | 7 of 357 |

**The seven continuous beds still agree with their gated figures inside 0.2 dB** (`oil_lamp_flame` makes an eighth at 0.27), exactly as the
table above found. Thirteen stems disagree by 5 to 10 dB, and the last column says why without
needing the first two: the gated figure for `oil_lamp_rattle` is computed from **39 of its 347 blocks**,
so it describes about a ninth of a file that is nine-tenths silence and calls that the
loudness of the whole. At **9.51 dB** it is the widest gap among those thirteen, just past
`coins` — four tracks filed since run wider, and the paragraph after next is about them.

**The delta is a density reading, and the table sorts itself by it.** *Which stopped being
true for a while without anybody noticing: five rows filed between 2026-10-16 and 2026-10-17
were appended to the bottom of the table instead of placed, so the sentence described an
order the table no longer had. Re-sorted on 2026-10-17. A table that claims to be sorted is
exactly the kind of prose fact the bed-count guard exists for, and there is no guard on this
one.* It is not two classes
but a line, and where a track falls on it says how much of its own duration it occupies:
nothing through the six continuous recordings; −0.8 for `donate_building` and for `footsteps`
(which walks without a gap); −1.2 for `worker_footsteps` and **−1.8 for `wool_robe`** (a rustle
with 13 holes in it, 22% silence); −3.4 to −4.2 for the barn `room`, `ox_cart_mechanics` and
`gravel`; and 5 to 10 dB for the thirteen tracks that are a handful of placed events —
`ox_breathing`, `barn_creaks`, `far_work`, `rammers`, `ox_cart_stones`, `rosary`, `keys`,
`wheat`, `horse_snorts`, `staff`, `distant_dogs`, `coins` and `oil_lamp_rattle`. *(That list
said "eleven" while naming twelve for some weeks, which is the same class of fault as the bed
counts and had no test behind it either.)* **And the scale now runs past 10 dB**, which it did
not when this paragraph was written: `door_close`, `rats_crossing` and `rat_squeaks` read
**−12.94, −13.76 and −13.80**, on 18, 15 and 15 of 357 blocks, and `bottle_knock` reads
**−17.06** on **7**, the widest gap in the tree by over three decibels. `oil_lamp_rattle` at
90.3% silence used to set the end of it, and with the identity above that is all those
figures are saying — 10·log₁₀(357 ÷ 15) = 13.77, 10·log₁₀(357 ÷ 7) = 17.08.

**The end of the scale is the `far_work` / `rammers` inversion again, and it is worth seeing
it twice.** Measured on the shipped files, `rat_squeaks` is **97.8%** silence and
`bottle_knock` is **97.0%** — the bottle is the *less* empty file — and the bottle still reads
3.3 dB wider, on 7 blocks against 15. The squeaks are **three bursts** at 10.48, 10.97 and
11.48 s, each loud enough to carry its own blocks; the bottle is **one burst** of 1.09 s that
decays steeply, so most of what follows its first impact falls under the gate rather than
beside it. *Silence fraction and surviving-block count are different quantities*, and at both
ends of this table it is the second that governs the delta. How the events are spread matters
as much as how much there is: the same second of material, placed three times over, would have
read smaller.

*A measurement note that applies to every silence figure in this tree.* The two percentages
above are of the **shipped `.ogg`**. Almost every one filed in `attribution.json` before
2026-10-17 was measured on the **WAV stem** instead, and the shipped file is always the less
silent of the two, by 0.06 to 4.8 points — Vorbis rings out across short gaps, so what was 51
separate non-zero runs in the bottle's stem is one unbroken run in the file that ships. The
measured table is in `sfx/README.md`; the records have not yet been restated.
*Reading the delta is cheaper than reading the file*, and it is the number
that tells you whether a track's recorded loudness means anything on its own.

**Build Roads arrived as seven stems and fell straight onto that line** — `worker_footsteps`
−1.2, `ox_cart_mechanics` −3.7, `gravel` −4.2, `ox_breathing` −5.0, `far_work` −5.4,
`rammers` −5.9, `ox_cart_stones` −6.3, against 28.7%, 55.7%, 52.2%, 69.6%, 65.0%, 58.2% and
75.3% of their length in exact silence. **It ranks rather than measures**, and the middle of
that list shows the limit: `far_work` is emptier than `rammers` and still reads the smaller
delta. Near enough to tell at a glance which tracks have a recorded
loudness worth comparing; not near enough to quote as a duty cycle. Every one of the seven
fails that test, which is why the folder fell silent with all of them playing — 2.344 s of 35
with the first four, and 1.168 s once the ox cart was added.

**Then the wind arrived at −0.02 with all 307 blocks kept, and the scene stopped falling
silent.** That is the whole point of the delta in one line: *a folder of stems has no floor
until something in it reads near zero*. The seven stems that preceded it, between −1.2 and
−6.3, could not make one
between them, however many there are, because they are all silent at the same moments by
construction. This one number would have said so before anybody listened, and it is the
cheapest thing in this note to check.

**What the delta actually is, which took two files landing on the same figure to notice.**
`ordination_actionB/distant_dogs` and `ordination_actionB/staff` read **exactly 7.01 dB** and
survive on **exactly 71 blocks** each — different material, different sources, different source
sample rates. That is not a coincidence. When a file's quiet parts are *true digital silence*,
every scrap of its energy is inside the blocks the gate keeps, and the delta reduces to

> **delta = 10 · log₁₀( all blocks ÷ surviving blocks )**

Checked against all sixty-three beds, the prediction agrees with the measured delta to within
**0.06 dB on sixty-one of them**. *Produce Stone's thirteen added a second exception and it is
a hair's breadth one:* `produce_actionB/debris_cleave` reads 13.30 against a predicted 13.36,
out by **0.062**, which is over the line by two thousandths of a decibel and is reported
rather than rounded in. The real outlier is still `allocation_wind` at 0.19 dB, with
every one of its 167 blocks kept. `taxation_actionA/room` at 0.057 is the next worst and sits
just inside — it was carried here as 0.061 and reads a hair under when the table's own rounded
figures are used, which is the boundary rather than a counterexample either way. *The delta is
a block count.* Nothing else.

**That is what explains the `far_work` / `rammers` inversion above**, which this note previously
put down to the gate weighing how far events stand above the mean. The real reason is simpler
and exact: `far_work` is 67.0% silent and keeps **101 of 347** blocks; `rammers` is 59.4% silent
and keeps **90 of 347**. The emptier file keeps *more* blocks, so it reads the smaller delta. A
0.4 s block survives if any part of it carries an event, so the surviving-block count and the
silence fraction are different quantities and only loosely related — the gate is counting
blocks a sound touches, not time a sound fills.

**It is still worth printing, and it is still not a density.** A block count is a real thing to
know: it is the resolution at which the material is intermittent. But a sentence calling the
delta "how dense this track is" claims more than the number carries, and records should say
*what it is* — the block ratio — rather than what it was taken for. Where a bed's quiet parts
are a noise *floor* rather than silence the identity will not hold, because energy then lives
outside the kept blocks; no bed here is that case yet, and the first one that is will be worth
measuring rather than assuming.

**The conclusion is unchanged and the reasoning is stronger.** Gating a sparse stem does
precisely what this section already refuses to do to a gusty wind bed — it levels the material
by its events and throws away the silence the player is actually sitting in between them.
Ungated was the right choice for a reason that generalises; "a bed is continuous" was a
property of the four beds that existed when it was written.

**Two things follow for anyone reading a recorded number.** A bed's `measured` string is
documentation and not the control — every trim here is authored by ear — but it is the figure
a later pass will reach for, so: *do not compare a sparse stem's integrated loudness against a
continuous bed's*, because on `rosary` against `devotion` that comparison is 7 dB wrong before
it starts, and the crest factors behind the two numbers are 34.9 dB and 12.3. And where a
sparse stem's level has to be reasoned about rather than heard, the loudest 400 ms block is the
honest number: `rosary` reads −35.8 there against `devotion`'s −27.6, which is the right way
round and roughly the right distance.

### A 200 ms window, with short clips zero-padded

BS.1770's momentary window is 400 ms. That is a programme measure and **over-penalises short
cues by about 3 dB**. 200 ms is close to the ear's own temporal integration time.

A clip shorter than the window is zero-padded, which charges it `10·log10(length / 200)` for
being brief. **This is not a fudge, it is the psychoacoustics.** Below roughly 200 ms the ear
integrates energy rather than power, so a short burst of equal amplitude genuinely is quieter.
Three synthetic bursts of identical amplitude and spectrum:

| duration | whole-file mean | 200 ms window | 400 ms window |
|---|---|---|---|
| 67 ms | −7.7 | **−12.5** | −15.5 |
| 200 ms | −7.5 | **−7.5** | −10.5 |
| 1200 ms | −7.4 | **−7.3** | −7.3 |

Whole-file says all three are equally loud, which is wrong — a 67 ms blip does not sound like a
1.2 s wash. 400 ms charges the 200 ms burst 3 dB it should not pay. The middle column is right.

---

## 3. The ceiling is true peak, and finding it found a live bug

Gain needs a limit and the limit must be **inter-sample** peak. A DAC reconstructs the waveform
between samples, and on sharp transients the reconstruction overshoots the samples. Measured at
4× oversampling:

| clip | sample peak | true peak |
|---|---|---|
| `duty_actions/ordination_actionA_sfx_v03` | −0.1 dBFS | **+0.75 dBTP** |
| `misc/velcro_rip_sfx_v01` *(was `tithe/wheat_sfx_v01`)* | −0.2 dBFS | −0.04 dBTP |
| `duty_actions/clerical_actionB_sfx_v01` | −0.3 dBFS | −0.25 dBTP |
| `duty_actions/construct_actionB_sfx_v01` | −0.5 dBFS | −0.27 dBTP |

**Ordain v03 is over full scale and clips on playback today**, at a sample peak reading −0.1 that
looks entirely fine. Sample-peak measurement could not have found it. The defect predates this
work; levelling pulls it down by 4.1 dB and fixes it as a side effect.

---

## 4. Why −24 LUFS

**Because that is where set 1 already sits.** `tile.ogg` measures −24.4 LUFS and `confirm.ogg`
−22.5, and set 1 is the one interface set the board actually plays and that nobody has ever
complained about. Normalising to −24 moves those two by 0.4 and 1.5 dB. The target is not a
round number chosen for comfort; it is the working set described numerically.

With a **−1 dBTP ceiling**, 36 of 38 clips land exactly on target and the spread falls from
31.9 dB to 5.2.

A louder target costs clips that cannot reach it:

| target | ceiling-limited | worst shortfall |
|---|---|---|
| −18 | 13 | 11.1 dB |
| −20 | 10 | 9.1 dB |
| −22 | 4 | 7.1 dB |
| **−24** | **2** | **5.1 dB** |

Of the two that fall short at −24, one misses by 0.6 dB and does not matter. The other is
`rock_dropping`, 5.1 dB short because its crest factor is **28.1 dB** — it hits the ceiling long
before it reaches the target. That is the honest signal that a sparse transient cannot be made
to match a sustained sound by gain alone. Limiting it or re-cutting it are decisions, not
arithmetic, and neither has been done.

---

## 5. Let the board's role gains do the role balance

`action_board.html.tmpl` applies a per-cue gain at playback:

```js
var SFX_GAIN = {hover: 0.12, select: 0.5, confirm: 0.7};
```

**Set 1 works precisely because its files are near-matched in loudness and that gain does the
hover-versus-confirm balance.** Set 3 does not follow that pattern — its hover, select and
confirm measure −25.4, −13.0 and −12.9, so 12.5 dB of imbalance is baked into the files and the
role gain is applied *on top*, pushing the hover around 30 dB below the confirm.

Normalising every file to one loudness and leaving the balance to `SFX_GAIN` removes the double
accounting and makes the numbers in the template mean what they appear to mean.

---

## 6. A field, not a re-render

Writing gain into the audio would destroy the check this tree leans on hardest: that a shipped
clip's peak matches its master's. That check has caught three real filing errors, and Mint
already has to carry its ungained peak by hand to stay verifiable at all.

`gainDb` in `attribution.json`:

- every byte stays verifiable against the master
- one owner per fact — the file owns the audio, the record owns the playback level
- reversible, and re-derivable by re-running the tool
- retires Mint's gain exception if that clip is ever re-cut ungained

---

## 7. Three traps, each of which cost something

**Resampling before measuring.** The first version of the audit resampled everything to 48 kHz
and reported four clips as wrong. All four records were correct. Inquisition is 96 kHz and reads
−5.61 dB at 48 against its true −3.66, because the resampler discards the content making the
peak. Four correct records came within one edit of being "fixed". *Always decode at the file's
own rate.*

**Gain after quantising.** Mint's auditioned version was written to 16-bit at −35 dB and then
multiplied. At that level the fade tail fell under the least significant bit and quantised to
literal zeros — 2878 of 2880 samples in one 60 ms window. Multiplying zero by 13 leaves zero.
*Apply gain in float, before quantising.*

**`Audio.volume` is capped at 1.** The bench's first A/B could not turn a clip up, so "levelled"
was implemented by anchoring on the biggest lift and bringing everything *down* to meet it.
Arithmetically faithful, practically useless: the median clip lost 15.9 dB and it read as the
idea failing rather than the page failing. *Use a WebAudio GainNode, which has no cap* — the
board always did.

---

## 8. Adding a clip later

```
python3 ui/board_v2/sfx_lab/sfx_levels.py --one <path>     # measure one
python3 ui/board_v2/sfx_lab/sfx_levels.py                  # report the whole set
python3 ui/board_v2/sfx_lab/sfx_levels.py --write          # stamp gainDb into attribution.json
```

`test_every_sound_carries_a_measured_playback_trim` refuses a clip filed without a `gainDb`, and
re-measures every value against its audio where a decoder is available. The bench prints a
`NOTE` for any drawn clip missing the field.

**For a BED, use `bed_facts.py` instead, which is the one that knows what a record needs.**

```
python3 ui/board_v2/sfx_lab/bed_facts.py <path.ogg>            # everything, from one decode
python3 ui/board_v2/sfx_lab/bed_facts.py --record <path.ogg>   # + the `measured` string and sha256
```

`sfx_levels.py` answers *what should this play at*, and for a bed the answer is "nobody can
tell you, set it by ear". `bed_facts.py` answers the other question — *what is this file* —
and in one pass gives duration, peak, true peak, M200, ungated and gated loudness with the
block counts and the identity's prediction beside them, silence fraction and the run
structure under it, head, tail and wrap gaps against the longest interior gap, the butt-join
step against both yardsticks, L/R correlation, exact dual mono, and the delayed-copy check
that catches an `oil_lamp_flame`-style Haas widener. **It exists because those fifteen numbers
used to be taken by writing four throwaway scripts per bed**, and one of those scripts got the
channel indexing wrong — `channels()` returns an (n, ch) array and a fresh script iterates its
rows — which reported a 36-second file as a single 400 ms block, a number plausible enough to
have been written down. *A tool that always measures the same way the same way cannot have
that fault twice.* It takes about three seconds a file. It deliberately does **no provenance
work**: that probe has to pick its window, its speed candidates and above all its control for
the claim being tested, and a default control is not a control.

**The tool needs `ffmpeg`, which is not on the Mac's PATH** — the same fact that made
`generate_sound_bench.py` read Ogg headers by hand rather than shell out. That is tolerable only
because this is a measuring tool and not a build step: it runs where a decoder exists, writes a
number, and from then on the board and the bench read a field. Nothing in the shipping path
decodes anything.

---

## 9. Sample rates and file format, which were checked and left alone

The tree holds 24, 44.1, 48, 96 and 192 kHz clips. This is inherited — the convention has always
been to keep the source rate — and the rates map onto provenance exactly: every clip at 96 kHz
or above is a Sonniss library WAV, every 24 kHz clip is a Pixabay mp3.

**It is not a playback problem.** The browser's AudioContext resamples everything to the device
rate on decode. It is only a *measurement* hazard, and that is handled above.

**Normalising the rate is not worth it.** Re-encoding the eleven clips above 48 kHz down to 48
saves **14 KB**, 7% of those clips and about 2% of the set — Vorbis already allocates almost
nothing above 20 kHz. Against that: eleven re-renders, the master-peak check broken for all of
them, and true peak shifting by up to 2.05 dB, forcing a full re-measure.

**WAV would be a regression.** Every sound ships inlined as a `data:` URI and base64 adds a
third on top:

| | on disk | inlined |
|---|---|---|
| Vorbis q6 (today) | 602 KB | 802 KB |
| WAV 16-bit | 4388 KB | 5851 KB |

7.3× the bytes, taking the bench page from 0.8 MB to 5.7 MB. Vorbis q6 is transparent at these
lengths and the per-clip encode cost is tracked in the records at a few tenths of a decibel. The
masters were deliberately deleted as re-fetchable third-party downloads, so the `.ogg` files are
not an archival format — `originalFilename` and `originalPath` are the recovery path.

The one thing that *is* uniform, and matters more than either: **every clip is Vorbis q6.** That
is the consistency a set levelled against itself needs. Every clip is also mono, which is the
subject of the next section, because that one is about to stop being true on purpose.

---

## 10. Channels, and a fold that will go wrong

**All 38 clips in the tree today are mono.** That was never a decision so much as an inheritance
— interface cues are point events and carry no width — but the tool quietly depends on it.
`load()` folds any multi-channel file with `reshape(-1, ch).mean(axis=1)` and measures the fold.
For a mono file that is a no-op, so nothing has ever been wrong.

**Ambient beds are meant to be stereo**, which makes the fold wrong rather than redundant.
BS.1770 does not measure the mono fold of a stereo programme; it sums the weighted power of each
channel. The two disagree, and the disagreement depends on how wide the material is:

| L/R correlation | what the mono fold reads |
|---|---|
| +1.000 | 3.01 dB low |
| +0.968 | 3.08 dB low |
| +0.866 | 3.31 dB low |
| +0.662 | 3.81 dB low |
| 0.000 | 6.02 dB low |

**The offset is harmless; the spread is not.** A flat 3 dB would vanish into the target and
nobody would notice. But two beds of identical true loudness and different width come out of the
tool with trims up to 3 dB apart — which is the exact failure the levelling exists to prevent,
arriving through the back door. *Measure per channel and sum the powers when `ch > 1`.*

**`true_peak()` reads the fold too, and the ceiling must not be optimistic.** The ceiling belongs
to the louder channel. On the first bed source examined, L peaks at −6.11 dBFS and R at −5.04;
the fold understates R by about half a decibel.

**Container channels are not content channels.** That same source reports two channels and
correlates at +0.9940 broadband, which reads as mono in a stereo wrapper — until you measure it
per band, where 800 Hz–8 kHz sits at +0.72 to +0.75. The broadband figure is dominated by
heavily correlated bass and hides real midrange width. Per-band correlation is the honest test
for whether a bed source has a field worth carrying, and it lives with the channel table in
`sfx/README.md`, which owns that check.

---

## 11. The bed target, which was chosen and then falsified

Ambient beds arrived as a second class and got the full treatment: a second measure, a second
target, and a `kind` field on the record so the two could not be confused. Two of those three
survived contact with the second bed.

**A bed is measured by integrated loudness, not M200, and that part holds.** M200 anchors a 25 s
bed on its single loudest moment — 3.4 dB above integrated on a steady fire loop, 5 to 10 dB
above across three spans of a cathedral recording. The gap varies with how peaky the material
is, so using M200 on beds would shift the figure between two of them by about 5 dB for no reason
a listener would recognise. The classes fail in opposite directions: a cue levelled by its
average disappears, a bed levelled by its loudest fifth of a second sits too quiet for the other
twenty-four.

**The `kind` field holds too, with a better justification than it was given.** It was introduced
to say which target applied. It now says something more useful — whether a trim is *derived* or
*authored* — and that distinction is load-bearing, because `--write` must not recompute a number
a person produced.

**The target did not hold.** It was chosen the way −24 was, derived from the working set rather
than picked round: dialling the Silversmith fire against its own cue put it at −39 LUFS, 9.0 dB
under the cue. The second bed broke it. Trimmed to that same −39, the cathedral sat far forward
of the fire.

Before changing anything, five measures were checked to see whether a different one would have
predicted it. Trim both beds to match on integrated loudness, then ask what the others say:

| measure | cathedral against fire |
|---|---|
| integrated | 0.00 dB |
| short-term p50 | −0.16 dB |
| short-term p95 | +0.34 dB |
| 1 s maximum | +0.63 dB |
| M200 | +0.97 dB |
| 3 s maximum | +1.01 dB |

**The widest disagreement between any two is 1.0 dB, against roughly 5 dB heard.** No measure
sitting in the corner would have got this right, which means the gap is not about windows or
weighting. The cathedral has voices in it, and every loudness measure scores energy rather than
salience. A voice sits forward of broadband crackle at equal LUFS, and nothing in BS.1770 knows
that.

So **a bed's `gainDb` is authored by ear**, and the tool's job for a bed is to record the level
rather than choose it. `--one --kind bed` refuses to propose a trim and takes `--trim` to check
one instead. `--write` skips beds entirely and reports how many it left alone — without that,
the next run would have quietly overwritten the only part of a bed's record that takes a person
to produce. `test_every_sound_carries_a_measured_playback_trim` makes the same split: it still
demands that a bed *has* a trim, and checks the ceiling rather than re-deriving the number.

**The one rule that is not taste is the ceiling.** Where a bed sits is a judgement; whether it
clips is not. `ceiling_breach()` is what is left of the arithmetic.

---

## 12. Not done

- **The board does not read `gainDb`.** Today that would change only `tile.ogg` by +0.4 dB and
  `confirm.ogg` by −1.5, since those are the only two clips it plays.
- **Mint keeps its +22.3 dB baked in.** The field is measured from the file as it stands, so
  nothing double-counts, but re-cutting it ungained would retire the one gain exception.
- **`rock_dropping` stays 5.1 dB under the set.** It holds no slot, so this is not urgent.
- **Ordain v03's +0.75 dBTP** is fixed only in the sense that its trim is −4.1 dB. The file
  itself still clips if anything plays it at unity.

Still open for ambient:

- **Bed plus cue can clip in principle, and ducking cannot fix it** — the headroom problem is
  true peak rather than loudness, and a duck cannot help because the cue's own attack *is* the
  peak. **THE ALARM THIS BULLET RAISED WAS WRONG, AND THE ERROR IS WORTH KEEPING.** It said the
  case had stopped being hypothetical: `taxation_actionA/coins` at **−8.6 dBTP** untrimmed,
  "against a cue at the −1 dBTP ceiling, over full scale before anything is mixed". **−1 dBTP
  is the policy ceiling — the limit a cue may not exceed — not a cue.** No cue in this tree sits
  anywhere near it: the loudest after its own trim is `construct_actionA` at **−3.97 dBTP**,
  and Taxation's own cue is at **−12.90**. A rule about what may be filed was read as a
  description of what is filed, and three decibels of that gap did the rest.
- **Measured instead of multiplied, Taxation never came close.** Rendering the four beds at
  their trims and summing them, with this action's own cue added at its worst possible
  alignment:

  | | beds summed | + the cue |
  |---|---|---|
  | `coins` at unity | −8.57 dBTP | −4.45 dBTP |
  | `coins` at −17.0 (set by ear, 2026-10-15) | −20.02 dBTP | −9.73 dBTP |

  4.45 dB of margin at the worst moment the tree could previously produce, and 9.73 now. *The
  cheap estimate was 4 dB pessimistic on a quantity where 4 dB is the whole question.* Where
  headroom is the claim, render the sum: the files are on disk and it costs a minute.
- **THE PER-FILE SPAN HAS STOPPED BEING THE RIGHT QUANTITY.** This bullet has tracked where
  individual beds land since there were two of them, and Build Roads being levelled on
  2026-10-16 broke it: of the sixty-three ambient files, nine now sit between −26.5 and
  −45.5 dBTP and **fifty-four sit above −26.5**, the span running −3.4 to −37.5.
  **THIRTY-FIVE ARE STILL UNTRIMMED, AND THEY ARE EXACTLY THE FOUR NEWEST FOLDERS** — seven
  Mission, seven Build Shrine, eight Produce Wheat and all thirteen Produce Stone, which is
  now more than half the tree and is the honest shape of the backlog
  and not a scatter of oversights. *This sentence said "eight" through two days of filing and
  was re-derived rather than incremented on 2026-10-17; a count maintained by hand across a
  burst of additions is the same fault as a bed count in prose, and this one had no guard.*
  The loudest untrimmed is `ordination_actionB/footsteps`
  at −10.4 dBTP, which is unset rather than authored — the door was the loudest untrimmed bed
  until 2026-10-17, when it took the first trim in that folder; the top of the span is still
  `ordination_actionB/door_close` at −3.4
  after its own trim, which is a door rather than a level anybody chose, and the bottom is
  `ordination_actionB/rat_squeaks` at −37.5, which is one. Read per file that looks alarming and it
  is not: *tracks that sum have to be authored quieter per track than one track that plays
  alone*, and comparing one of Build Roads' eleven against a lone rain bed compares nothing.
  **The quantity that governs headroom is the sum of an action's own beds**, and the per-file
  span is kept only as a sorting aid.
- **Per action, measured rather than multiplied:**

  **PEAK IS NOT THE RANKING A TRANSITION HEARS, and the two orders differ sharply here.**
  Everything above is summed true peak, which answers *can this action clip*. The moment one
  action crossfades into another, the question becomes *will it step*, and that is loudness.
  The same render now reports both — `summedLoudnessLufs` beside `summedTruePeakDbtp`, under
  the same `summedAtTrims` fingerprint, because it is the same mix of the same files:

  | duty action | loudness | true peak | step from the one above |
  |---|---|---|---|
  | `ordination_actionB` | **−28.85** | −2.42 | |
  | `produce_actionB` | **−29.88** | −5.91 | −1.03 |
  | `produce_actionA` | **−30.16** | −13.58 | −0.28 |
  | `build_roads_actionB` | **−30.22** | −11.57 | −0.06 |
  | `build_roads_actionA` | **−32.44** | −5.22 | −2.22 |
  | `taxation_actionA` | **−33.83** | −12.02 | −1.39 |
  | `clerical_actionB` | **−35.31** | −11.97 | −1.48 |
  | `allocation_actionA` | **−35.80** | −10.74 | −0.49 |
  | `give_alms_actionA` | **−42.41** | −24.96 | −6.61 |
  | `clerical_actionA` | **−42.57** | −12.10 | −0.16 |
  | `give_alms_actionB` | **−43.72** | −22.83 | −1.15 |

  **`clerical_actionA` peaks 10.5 dB above `give_alms_actionA` and is 0.16 dB quieter.** That
  one line is the module header's argument about cues — peak does not predict loudness —
  arriving a second time one level up, on actions rather than clips. Anyone who matched these
  eleven by the peak column would put those two 10 dB apart and be wrong by 10 dB.

  **The shape of it: six actions inside 7 dB, then a 6.61 dB cliff, then three.** The top six
  are close enough that a transition between any pair of them is about the fade; below the
  cliff sit the three single-bed actions, and a crossfade into one of those is about the
  level, whatever the fade does. The full spread is **14.87 dB** against the peak column's
  22.55 — so the actions are better matched than the peaks suggest, and still not matched.
  *Nothing here is a judgement yet: every `groupDb` is 0, so this is where the beds happened
  to land, not where anybody put them.*

- **TWO ACTIONS SIT WITHIN A FIFTIETH OF A DECIBEL OF EACH OTHER, AND THE GAP MOVED WHILE
  THIS BULLET WAS BEING WRITTEN.** With its seventh bed in, Produce Wheat read **−30.22
  LUFS** and so did Build Shrine — a step of 0.00 dB. Replacing `sickle_cutting` with v02 a
  few hours later added one quiet gesture, moved Produce Wheat to **−30.20**, and put it
  *above* Build Shrine's −30.22 by **0.02 dB**. Nobody arranged either number: both actions
  carry `groupDb` 0 and no trim is set in either folder, so this is where forty-nine
  untouched beds happen to land. *It is still the one pair in the tree where a crossfade is
  essentially all fade and no step*, and the 0.02 dB reversal is the useful part — **a tie
  between two actions is not a property, it is a coincidence with a date on it**, and one
  added layer at −27 dB was enough to break it. The first trim set in either folder will end
  it properly. Their peaks are 2.01 dB apart, −11.57 against −13.58, which is the argument
  the paragraph below makes: the two measures answer different questions.
- **A SIXTH BED MADE PRODUCE WHEAT LOUDER AND ITS SUMMED PEAK LOWER.** Adding
  `produce_actionA/straw_workers` moved the action from −30.93 to −30.73 LUFS, which is the
  expected direction, and from **−13.85 to −14.21 dBTP**, which is not: 0.36 dB of true peak
  *removed* by adding a track. It is not a renderer fault and the mechanism was checked rather
  than assumed. The five-track mix peaks at −13.91 dBFS at **t = 15.1009 s** in the right
  channel, where the sum reads −0.201648; the new bed's sample at that same instant is
  **+0.008898**, so it partially cancels, and the global maximum relocates to t = 14.5328 s in
  the *left* channel at a lower level. **A summed peak is a statement about one sample**, and
  one sample is an alignment accident — add a sixth uncorrelated signal and the old maximum can
  simply stop being the maximum. Loudness, which integrates, cannot do this and did not.
  *This is the strongest form of the `coins` lesson in this note: an estimate that assumes
  peaks add would have predicted the opposite sign.*
- **All eleven, at the trims of 2026-10-17**, rendered rather than estimated:

  | duty action | beds | sum of peaks | rendered | + the loudest cue filed |
  |---|---|---|---|---|
  | `ordination_actionB` | 10 | +4.05 | **−2.42** | **+2.86** |
  | `produce_actionB` | 13 | +6.08 | **−5.91** | **+1.13** |
  | `build_roads_actionA` | 11 | +1.39 | **−5.22** | **+1.45** |
  | `produce_actionA` | 8 | −1.39 | **−13.58** | −1.49 |
  | `allocation_actionA` | 4 | −7.68 | **−10.74** | −0.69 |
  | `clerical_actionB` | 1 | −11.97 | **−11.97** | −1.06 |
  | `taxation_actionA` | 4 | −1.96 | **−12.02** | −1.07 |
  | `clerical_actionA` | 3 | −11.35 | **−12.10** | −1.10 |
  | `build_roads_actionB` | 7 | −0.70 | **−11.57** | −0.94 |
  | `give_alms_actionB` | 1 | −22.83 | **−22.83** | −3.03 |
  | `give_alms_actionA` | 1 | −24.96 | **−24.96** | −3.23 |

  The sum-of-peaks column assumes every track peaks at the same instant, which none of them
  do: it is **10.1 dB pessimistic** on Taxation, 6.6 on Build Roads and 6.5 on Mission, and
  10.9 dB on Build Shrine, whose seven beds barely overlap at all, and exactly nothing on the
  three actions with one bed, where the two columns are the same measurement. Rendering the sum costs a minute and is the only figure worth quoting — the
  same lesson the `coins` episode above taught, now across the whole tree.

  **Two actions are over full scale against the loudest cue filed**, Mission at **+2.86** and
  Build Roads at **+1.45**, and neither has a cue of its own. That is a constraint on what may
  be filed rather than a fault in what is. Holding the total to the **−1.0 dBTP** policy
  ceiling, a Mission cue has to land at **−17.4 dBTP or quieter** and a Build Roads cue at
  **−9.3** — against `construct_actionA`, the loudest cue in the tree, at −3.97. *So the
  ceiling that has governed cues since set 1 is not a usable target for either action, and on
  Mission it is 16 dB out.* The honest reading is that Mission's beds are too hot rather than
  its unwritten cue too loud: the door at −3.39 after its trim carries the action, and taking
  the group down is the move that buys the cue its room back.

  *The figures in the bullets around this table were each correct when written and several
  are not current: Taxation summed −20.02 when `coins` sat at −17.0 and reads −12.02 at the
  −9.0 it carries now, and Build Roads summed −11.98 before `rammers` was trimmed and the
  group folded. The bullets are kept as written; this table is the live one.*
- **THERE ARE TWO LEVELS NOW, AND THE SECOND ONE IS WHY THE FIRST CAN BE LEFT ALONE.** A bed's
  `gainDb` is its balance inside its action; an action's `groupDb`, in `attribution.json`'s
  `ambientGroups`, is where that action sits against the others. They multiply, and the group
  is applied as **one gain node per action that every track feeds** rather than added into each
  track's gain — so it cannot change a balance that has already been set, which is the only
  property that makes a master fader safe to use. The eight actions rendered between
  **−3.05 and −35.96 dBTP** when each had only ever been balanced inside itself — a 33 dB
  spread that nothing had a way to address. **One pass of matching them against each other, on
  2026-10-16, brought it to 19.7 dB**: −5.22 to −24.96, with five of the eight between −10.2
  and −12.1. The group levels that produced it were then folded into the trims, so the record
  carries one number per track again and every `groupDb` is back at 0, ready for the next pass.
- **`rammers` at +4.0 was the first trim that spent the action's headroom, and the group fader
  bought it back.** Build Roads went from −11.98 dBTP summed to **−3.05** on that one change —
  nine decibels on one track — and against the loudest cue filed the worst alignment reached
  **+2.52 dBTP**, over full scale, where a cue at the −1 dBTP policy ceiling gave **+4.06**.
  *That was never an argument against the trim*, which is a judgement about what Build Roads
  sounds like; it was the case for pulling the group down afterwards, which is exactly what the
  second level is for. That is what happened: the action was taken to **−4.0** on the bench and
  folded, which put `rammers` at **+2.0** and the action at **−5.22 dBTP** summed. The trim
  that caused the problem is still the loudest in the tree and the action now has room.
- **Build Roads is levelled, and it is where the headroom question now lives.** Eleven tracks
  summing to −11.98 dBTP is a healthy bed level with 12 dB in hand. Add the loudest cue in the
  tree after its own trim — `construct_actionA` at −3.97 dBTP — peak-aligned, and the total is
  **−1.06 dBTP**: legal, and the tightest margin anywhere here. Add a cue sitting at the
  **−1.0 dBTP policy ceiling** and it reaches **+1.16 dBTP**, which is over. *So the ceiling
  that has governed cues since set 1 is not safe for this action.* When a Build Roads cue is
  filed it should land near −4 dBTP or quieter, and that is a consequence of the action having
  eleven beds rather than one.
- **It was levelled without the cue every other bed was levelled against.** `build_roads_actionA`
  is still the first action with beds and **no cue filed at all** — the bench prints the
  warning on every build — so the eleven were balanced against each other by ear and the
  group's absolute level is the one judgement with no reference behind it. Give Alms has the
  same gap on both its actions, with one bed each rather than eleven.
- **The board plays the beds now**, as of 2026-10-18. `bundled_beds()` carries a manifest and
  the beds are fetched from the repository's own `sfx/ambient/` by `--serve`; the cues stay
  inlined so a page opened straight from disk keeps them. Both levels are applied the way
  `ambientGroupsNote` requires — one gain per bed, then **one** node per action, then
  `ambientMaster`. The bench is still where a bed is *auditioned*; the board is where the
  action-to-action transition is now heard.
- **`loopEnd` is pinned, and the length does not come from the decoder.** This bullet used to
  be a warning to whoever wired them in, and it was read in time: the first version of the
  player looped on `buf.duration` and would have wrapped through 4 to 17 ms of Vorbis padding
  on every bed. `ogg_seconds()` reads the true length off the container's last granule at build
  time and the manifest carries it. All sixty-three agree with the loader to under 0.05 ms.
  *A warning left in a note is only worth what the next person's search turns up* — this one
  was found by grepping for stale claims, not by remembering it.
