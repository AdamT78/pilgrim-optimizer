# Levelling the board's sounds by loudness

**Status: measured and applied.** `gainDb` is on every sound record, `sfx_lab/sfx_levels.py`
produces it, and the bench plays it behind a toggle. The board does **not** read it yet.

Measured 2026-10-13 against 38 shipping clips. This note exists so the reasoning does not have
to be reconstructed, and so the three traps in it are not rediscovered the hard way.

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
silence waiting for the other layers. Measured across all fourteen ambient tracks as they
stand:

| track | ungated | gated | delta | blocks kept |
|---|---|---|---|---|
| `clerical_actionA/devotion` | −30.79 | −30.79 | −0.00 | 347 of 347 |
| `clerical_actionA/candle` | −53.69 | −53.69 | +0.00 | 252 of 252 |
| `clerical_actionB/silversmith` | −32.77 | −32.77 | +0.00 | 247 of 247 |
| `give_alms_actionA/alms` | −38.37 | −38.36 | −0.01 | 247 of 247 |
| `allocation_actionA/allocation_wind` | −36.97 | −37.16 | +0.19 | 167 of 167 |
| `give_alms_actionB/donate_building` | −49.68 | −48.91 | −0.77 | 269 of 322 |
| `allocation_actionA/footsteps` | −30.62 | −29.78 | −0.84 | 233 of 282 |
| `allocation_actionA/wool_robe` | −31.08 | −29.29 | −1.79 | 187 of 282 |
| `taxation_actionA/room` | −38.16 | −34.77 | −3.40 | 134 of 297 |
| `taxation_actionA/barn_creaks` | −44.40 | −39.19 | −5.20 | 90 of 297 |
| `clerical_actionA/rosary` | −46.71 | −39.55 | −7.16 | 67 of 347 |
| `allocation_actionA/keys` | −35.04 | −27.22 | −7.82 | 47 of 282 |
| `taxation_actionA/wheat` | −47.40 | −39.27 | −8.13 | 46 of 297 |
| `taxation_actionA/coins` | −36.74 | −27.55 | −9.19 | 36 of 297 |

**The five continuous beds still agree with their gated figures inside 0.2 dB**, exactly as the
table above found. Five stems disagree by 5 to 9 dB, and the last column says why without
needing the first two: the gated figure for `coins` is computed from **36 of its 297 blocks**,
so it describes about a ninth of the file and calls that the loudness of the whole.

**The delta is a density reading, and the table sorts itself by it.** It is not two classes
but a line, and where a track falls on it says how much of its own duration it occupies:
nothing through the five continuous recordings; −0.8 for `donate_building` and for `footsteps`
(which walks without a gap); **−1.8 for `wool_robe`** (a rustle with 13 holes in it, 22%
silence); −3.4 for the barn `room`; and 5 to 9 dB for the five tracks that are a handful of
placed events — `barn_creaks`, `rosary`, `keys`, `wheat`, `coins`. *Reading the delta is
cheaper than reading the file*, and it is the number that tells you whether a track's recorded
loudness means anything on its own.

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
- **What remains true is narrower and still worth watching.** Of the fourteen ambient files,
  ten land between −26.5 and −45.5 dBTP after their trim. **Two have no trim at all**, `wheat`
  at −20.3 and `barn_creaks` at −21.5. Two have one and sit above that span: `room` at −21.4,
  and `coins` at −25.6 after the trim that fixed it. So the span to quote is **−21.4 to
  −45.5 dBTP** across the twelve tracks that have a trim, and `room` remains the case this
  bullet was really about — a bed authored above the span that said nothing about it. The
  arithmetic to distrust is the shortcut, not the concern.
- **The board plays no bed yet.** `bundled_sfx()` inlines `tile.ogg` and `confirm.ogg` and
  nothing else, so `generated/ambient_bench.html` is where beds are heard today.
- **Whoever wires them in must pin `loopEnd`.** Chrome's `decodeAudioData` returns up to 17 ms
  of Vorbis padding past the end, which loops as a dropout 30 dB below the bed. The reasoning
  and the measurement are in `ambient_loop_note.md`.
