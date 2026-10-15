# Cutting an ambient bed into a seamless loop

**Status: ten files under six duty actions.** Four actions have one track each —
`clerical_actionB/silversmith` (25 s, fire), `clerical_actionA/devotion` (35 s, a service),
`give_alms_actionA/alms` (25 s, rain) and `give_alms_actionB/donate_building` (32.5 s, a
sheltered wind). Two have several: `allocation_actionA/` holds `footsteps` and `keys` (28.5 s,
one mix in two stems) under `allocation_wind` (17 s, an independent loop), and
`taxation_actionA/` holds `wheat`, `coins` and `barn_creaks` (30 s stems, not yet wrapped and
waiting on a background bed). They are in `sfx/ambient/`, one folder per duty action since a
fourth track made the filename the wrong place to say which action a bed belongs to, and
`sfx_lab/generate_sound_bench.py` builds `generated/ambient_bench.html` to hear them looping
under their own cues. The board itself still plays neither. This note is the method, worked out
before the first one was cut so the choices came from measurement rather than from the first
thing that sounded acceptable.

Measured 2026-10-14 against `EFX SD Fire in Metal Stove 03.wav` (96 kHz, 24-bit stereo, 87.5 s,
peak −5.77 dBFS) and three spans of a cathedral room-tone recording. Levelling is a separate
subject and lives in `sfx_levelling_note.md`; this note is only about getting the loop to join.

---

## 1. Bake the crossfade into the file

A loop can be made seamless two ways: fold the tail back over the head in the asset, or let the
player overlap two copies at the wrap. **Bake it.**

The asset version has a property worth having. Looping is periodic repetition, so the mean power
over N passes equals the mean power over one, exactly — the file *is* the signal:

| curve | one pass | three passes | delta |
| --- | --- | --- | --- |
| linear | −43.76 | −43.76 | −0.00 |
| equal power | −43.69 | −43.69 | −0.00 |

Gated agrees too: 247 of 247 blocks on one pass, 747 of 747 on three. So the loudness tool needs
no special case for loops, and the number on the record describes what the player hears.

Crossfading at runtime breaks that. The file on disk is then not what plays: a 27 s source
measured naively reads −43.80 while three laps as actually rendered read −43.66. **+0.13 dB**,
which is small but systematic, and it grows with crossfade length as a fraction of body length.
It also puts a second copy of the levelling question inside the player.

## 2. Equal power, not linear

The two ends of a long ambient span have nothing in common — the shoulders of the cathedral
material correlate at **+0.047**, the fire's at between −0.059 and +0.010. Decorrelated signals
sum by power, so the fade curve has to hold power rather than amplitude:

| join | level of the crossfade region against the rest of the file |
| --- | --- |
| butt join, no fade | no dip — but a discontinuity, heard as a click |
| linear fade | **−2.68 dB** |
| equal power (sin/cos) | **−0.89 dB** |

A linear crossfade on decorrelated material drops 2.7 dB at the same point on every lap, and a
periodic dip is itself the loop marker the crossfade was meant to hide. This is the channel
table in `../sfx/README.md` asked along a different axis: correlated material sums by amplitude,
decorrelated material sums by power.

The 0.89 dB equal power still loses is not the curve's fault — the two shoulders differ by
0.18 dB in their own right, and real material is never perfectly decorrelated at every
frequency. The fix for a residual dip is to move the crossfade point, not to change the curve.

## 3. Length is not the variable it looks like

The obvious knob is crossfade length, and it barely does anything. Two sweeps, both equal power,
both measuring the seam against the rest of the file:

| crossfade | cathedral | fire |
| --- | --- | --- |
| 0.25 s | −1.38 dB | −1.18 dB |
| 0.5 s | −1.34 dB | −1.08 dB |
| 1.0 s | −0.62 dB | −0.77 dB |
| 1.5 s | −0.99 dB | −0.45 dB |
| 2.0 s | −0.89 dB | −0.73 dB |
| 3.0 s | −0.47 dB | −0.42 dB |
| 4.0 s | −0.40 dB | −0.18 dB |
| 6.0 s | −0.59 dB | −0.15 dB |

A 24× range of length moves the seam by about a decibel, and **longer is cleaner, not worse**.
That contradicts the common advice that a 4–5 s crossfade produces an audible drop; on level, it
produces the smallest drop in the range. Below about 1 s is measurably worse and worth avoiding.
Above that, pick from the material and do not expect the number to matter much.

## 4. A mechanism that was proposed and did not survive measurement

Having found that length does not move the *level*, the next guess was that it moves the
*texture*: an equal-power overlap of decorrelated material holds power but ought to double the
event density, two fires' worth of crackle at half amplitude each, which would read as the
overlap sounding busier than the bed.

It was tested two ways on the fire — counting transient onsets in the overlap against the body,
and comparing five band levels — and **it does not show**. Onset ratios came back between 0.59
and 1.17 with no trend against length, and the band deltas were dominated by which slice of body
happened to be the comparison. The material's own window-to-window variation is larger than
anything the crossfade does to it.

Recorded because it was a plausible story that generated a plausible rule ("keep crossfades
short on event-y material") and the rule has no support. It also points directly at section 5:
if the material varies more than the process does, the material is what to optimise.

## 5. Shoulder match dominates everything, and level will not find it

The real variable is *which two shoulders are joined*. Searching every start time in the fire
recording for a 25 s body with a 1.5 s crossfade, scoring each candidate by how closely the head
and tail shoulders match across five bands:

| start | band mismatch (RMS of 5) | worst single band | resulting seam dip |
| --- | --- | --- | --- |
| 15.5 s | 0.70 dB | 1.2 dB | **−0.04 dB** |
| 45.5 s | 1.09 dB | 1.7 dB | |
| 16.0 s | 1.13 dB | 2.2 dB | |
| 33.0 s | 10.42 dB | 14.9 dB | |
| 7.0 s | 11.06 dB | 15.4 dB | −1.00 dB |

Two things. The spread is **15 dB in the 3–8 kHz band** between best and worst, which is the
difference between a join nobody notices and the fire audibly changing character. And the worst
candidate's seam dip is only −1.00 dB, so **a level-based check rates it unremarkable** — the
same lesson that keeps recurring in `../sfx/README.md`, arriving in a new place.

Shoulder choice is worth 15 dB; crossfade length is worth 1 dB. A loop checker should score
candidates by band match, not by level, and the by-hand version of this step — "move the
boundary a few seconds and try again" — is a search that can simply be run.

A short-term-RMS steadiness heuristic was also tried and is worse: it picked 22.2 s, giving a
−0.45 dB seam against the band search's −0.04 dB.

## 6. The first bed, concretely

For `EFX SD Fire in Metal Stove 03.wav`: **start 15.5 s, 25 s body, 1.5 s equal-power
crossfade.** All five bands within 1.2 dB, seam dip −0.04 dB. Avoid 78–79 s, which holds the
loudest event in the recording; avoid starting at 7 s or 33–34 s, which are the worst matches in
the file.

The resulting loop measures −35.88 LUFS integrated ungated, −35.88 gated with all 247 blocks
kept, M200 −32.50, true peak −9.91 dBTP. M200 sits 3.4 dB above integrated, which is why beds
are reported by the integrated figure — see `sfx_levelling_note.md` §11, which also records how
the bed *target* was chosen and then falsified by the second bed. A bed's level is authored by
ear; this note's numbers describe the loop, not where it should sit.

Ear test before filing, which no measurement replaces: write the loop three times end to end and
play across both joins. The question is not "can I hear a click" but "can I tell the fire
changed character".

## 7. Cut it with a script, not by hand

Audacity is the right place to *listen* — the three-copies test especially. It is the wrong
place to produce the asset. A hand-cut loop cannot be re-derived from its record, and this
tree's provenance rule is that it can: sha256 on every record, versions that count up, nothing
overwritten in place. Record source, start, body length, crossfade length and curve, bake with
`ffmpeg`, and the loop regenerates byte-identical.

**One specific trap: an editor exports at its project rate.** This source is 96 kHz. The audit
described in `sfx_levelling_note.md` §7 read four correct records as wrong for exactly this
reason — decode at 48 and a 96 kHz clip loses up to 2 dB of peak. A silent resample on export
makes the record describe a file that was never measured.

## 8. Start at a random offset

A seamless loop still announces itself if it begins at sample 0 every time the player selects
the tile. `source.start(when, offset)` with a random offset costs three lines, and it works
*because* the loop is seamless — a random offset into a loop with a seam would expose the seam
immediately.

Two riders: it has to compose with whatever fade-in the bed gets at select, and it makes
playback non-deterministic, which matters only for testing. With beds scoped to two duty actions
and heard repeatedly, this is where the anti-repetition budget is best spent.

## 9. Sparse event material, and a loop built in the mix instead of cut from one

Everything up to here was worked out on **continuous texture** — fire, rain, a room, a howl —
where every 200 ms window looks much like every other. Allocation's bed is not that. It
is a **composite** — shipped first as one file, `allocation_sfx_v02.ogg`, and since split into
the `footsteps` and `keys` stems that sum to it, which changes nothing in this section: single footfalls and single key contacts lifted out of two CC0 uploads and
assembled into a scene, footstep by footstep, rather than a window cut out of one recording.
The method is `ambient_composite_guide.md`, which is the other document; this section is only
what the material did to the rules above.

It also arrived **already looped**, which is new. Every bed before it was cut here from a master;
this one was made seamless in the mix, by the same equal-power overlap sections 1 and 2 argue
for, worked out independently and written down before this note was consulted. Two routes, one
answer, on different material — which is the strongest evidence either of them is right.

### The absence of a click is not the absence of a seam

The version before the one that shipped was a 30 s mix whose first and last samples were both
**exact zeros**. Butting the end against the start produced no discontinuity at all: nothing to
declick, nothing a waveform view would show. It still could not be looped that way. The first
0.3 s and last 0.6 s were digital silence and the material thinned out from about 26.4 s, so
plain repetition dropped some **2.5 s of near-nothing** into the bed every lap. Scored the way
section 5 scores a shoulder — five bands, 1.5 s head against 1.5 s tail — that butt join was
**41.0 dB out, with 68.5 dB in the top band**, against the 0.70–1.13 dB that counts as a good
match on continuous material.

So the two failure modes are independent, and a file that begins and ends in silence is exactly
the shape that separates them. Silence at both ends makes the *click* test pass and the *level*
test fail, which is the reverse of the usual case and the reason "it ends where it starts, so it
loops" reads as true. The shipped version exists because this was real.

### The shoulder test does not apply to a finished loop

Section 5 scores **candidates**: two spans of a master that a crossfade has not yet been built
between. Run the same test on a baked loop and it compares a head that has already been
crossfaded with its own tail against that tail — which measures the material's own variation and
nothing else. On the shipped bed it reads **21.5 dB**, and that figure means nothing whatever.

Worth stating because the number looks like a verdict and invites a rebuild of something that is
already correct. **Score candidates; verify finished files.** The three checks that do apply to a
baked loop are the one-pass-against-N-passes identity from section 1, the sample step across the
wrap against the file's own median sample-to-sample difference, and the window test below.

### Asking whether the wrap is a hole, properly

"Seam region against the rest of the file" (section 2) is the right question on continuous
material and a weak one here, because every 1.5 s window of this file differs from every other.
Slide a 1.5 s window across three laps instead and ask where the wrap falls in the distribution.
On the shipped bed it sits at the **19th percentile**, 2.35 dB under the loop's median, where the
loop's own quietest window is **12.7 dB** under it. The percentile answers the question the
decibel figure only looks like it is answering.

### The band search cannot see rhythm

This was found on a cut of the earlier mix that did not ship, and it outlives it. Run the
section 5 search over that 30 s file and the winner is a **22.0 s body from 0.0 s** at 0.87 dB
RMS across five bands — a better score than anything else in the file, and wrong. The keys sit
on a near-regular grid, gaps of 3.97, 3.89, 3.92, 3.92, 3.89 and 3.92 s, and 22.0 s is **5.6 of
those gaps**, so every lap the wrap would deliver a key 1.5 s early. One lap sounds fine; the
loop announces itself on the second.

**The rule: on material with a periodic event, the body length must be a whole number of event
periods, and the shoulder match chooses only among the lengths that already satisfy it.** The cut
taken was 23.510 s, exactly six of them, scoring 0.95 dB — slightly worse on the only number the
search knows about, and right.

**The tolerance is set by the material, not by the arithmetic.** Those gaps already vary by 80 ms
between longest and shortest, because a person placed them; six periods is measurable to about
±14 ms. A wrap 40 ms off sits inside jitter the listener is already hearing. A machine-sequenced
grid would have no such slack and would want its length from the sequencer's tempo rather than
measured off the audio.

**The shipped file does not need the rule, and shows why it is worth knowing anyway.** Its loop
is the whole mix wrapped onto itself, so the cadence across the wrap is whatever the mix had
there — 3.92 s, on grid, for free. What the mix does have is one *interior* gap of 4.99 s where
the others run 3.90 to 3.96. That is not a seam, it repeats identically every lap, and it reads
as one slower handoff. The distinction worth keeping is that **a rhythm fault at the wrap is a
loop artefact and a rhythm fault inside the body is content** — the first is always wrong, the
second is a question for the ear.

### A crossfade that lands a sound on itself

From the same unshipped cut, and the reason it scored as well as it did. Making the body a whole
number of grid periods has a consequence that looks like a coincidence and is not: the key six
periods from the head falls in the folded tail at exactly the position the head's own key
occupies. In that file the two happened to be **the same slice** of the source jingle,
correlating **+0.82 at zero lag** where every other pair in the file managed +0.07 to +0.14, so
the crossfade overlaid a recording on itself rather than mixing two different ones. It cost
**1.8 dB** on that hit — correlated material summing nearer to amplitude than to power — and
1.8 dB disappeared into the **5.85 dB** the seven jingles already spanned among themselves.
Section 4's lesson from a third direction: the material's own variation is larger than what the
process does to it.

**Worth recording as a thing that did not pay:** that search was given a second term penalising
candidates whose shoulders sat far below the body, on the theory that sparse material lets two
silences match perfectly while leaving a hole. It changed the ranking by almost nothing — the
butt join is caught by the band score alone, at 41 dB. The hole it was built to catch did not
exist. A negative result, not a recommendation.

### Replacing a layer re-rolls the beat cycle of everything it plays with

Section 11 below has carried "bed-to-bed transitions are unspecified" since the first two beds.
This is a narrower and more immediate version of the same gap. The wind layer's 17 s was chosen
against an 11.5 s bed to give 391 s before the pair realigns. That bed has been replaced twice
in one sitting: by a 23.510 s cut, which would have given 39,967 s, and then by the 28.5 s mix
that shipped, which gives **969 s** — about sixteen minutes. All three are long enough and none
of them was chosen for it.

A number arriving by accident three times is the warning, not the reassurance. Swapping one file
silently re-rolls this for every layer sharing its action, **nothing in the tree computes it**,
and the next swap could as easily land on a near multiple of 17. It is two lines of arithmetic
against the lengths already on the records.

## 10. Two more things the shoulder score cannot see

Section 5 settled that *which two shoulders you join* dominates everything else, and the band
match over a 1.5 s window at each end is how that gets scored. Section 9 found the first thing
it is blind to. The sixth bed, `donate_building_sfx_v01.ogg`, found a second, and the two are
the same shape: **the score reads two short windows and knows nothing about the thirty seconds
between them.**

### A body can climb

Searching the sheltered-wind master — 215 s, every start at 0.5 s, every length from 28 to 42 s
— the best band match in the file is a **28.5 s body from 52.50 s at 0.25 dB RMS**. It was
rejected. Measured first third against last, that body **climbs 7.3 dB**, so every lap would be
a crescendo that resets to quiet at the wrap. The shoulders match beautifully; the thing between
them does not hold still.

The body taken instead scores 0.30 dB and runs −51.70 to −51.78 across the same comparison —
**flat to within 0.08 dB** while still holding 10.79 dB of gust inside it, which is the
distinction that matters. Fluctuation is the material. A trend is a shape, and a shape that
resets every lap is a loop marker exactly like a key arriving early.

So the search wants a second term, and it is one line: the level of the first third of the body
against the last. On the eight best candidates here it ranged from −7.4 to +7.3 dB and picked
out the one that was flat. It costs nothing to compute and it would have changed the answer.

### "Seam against the rest of the file" measures two things at once

Section 2's number is crossfade region against the remainder, and on this bed it reads
**−7.54 dB** — which on the fire would have meant a hole and nearly caused a rebuild. It is not
one. Split in two:

| | |
| --- | --- |
| the crossfade against the **raw head it replaced** | **+0.72 dB** |
| that raw head against the **whole body** | **−8.09 dB** |

The curve costs nothing; it gains, two decorrelated shoulders summing by power. The 8 dB is the
material — 64.5 to 66.0 s is a lull in the wind, the 12th percentile of this body's own 1.5 s
windows — and a lull is the *best* place to wrap, not the worst.

**On continuous material the two terms are the same number**, which is why section 2's single
figure worked on fire and rain and why nothing noticed. Where the material fluctuates they come
apart by 8 dB and the combined figure is unreadable. Measure them separately: one is a property
of the curve, the other is a property of the start time, and only the first is ever a defect.

The percentile test from section 9 agrees and is quicker: the wrap window sits at the **16th**
percentile of the loop's own windows, 4.5 dB under their median where the quietest window
anywhere in the loop is 9.3 dB under it. Low, and inside the material's own range.

### A second tonal bed, and the narrow band earning its keep again

This master holds a resonance at **451 Hz, 10.3 dB above the local spectral trend**, with a
second at 649 Hz at +6.2 — so, like the howl and unlike the fire, two copies crossfaded at
arbitrary relative phase can cancel where broadband material simply sums. Candidates were scored
on a narrow 400–700 Hz band alongside the usual five and the chosen crossfade was then built and
measured: it costs **0.50 dB** in that band, against the howl's 0.46. Two tonal beds now, both
inside half a decibel, which is starting to look like a method rather than a one-off.

## 11. Not done

- **The board plays no bed.** All five are filed and audible on the ambient bench;
  `bundled_sfx()` still inlines only `tile.ogg` and `confirm.ogg`.
- **Bed-to-bed transitions are unspecified.** One global equal-power time, not a pairwise
  matrix: the matrix never converges, it grows as the square of a bed count that is expected to
  grow, a transition is heard once where a loop seam is heard every lap, and the only thing that
  genuinely varies pair to pair is the level difference, which the levelling removes. Left 12 dB
  apart, a transition swings 6.1 dB; matched, the excursion falls into the beds' own
  fluctuation. If one pair ever misbehaves, per-bed in and out times compose and stay linear.
- **Start and stop behaviour is unspecified.** Ambience ends on confirm, but hard or faded is
  undecided, as is the fade-in on select, and what happens on deselect or re-select.
- **The loop checker does not exist as a tool.** The band-match shoulder search, the N-lap
  render and the wrap-window percentile test have been written from scratch for each of the
  ten files. Three of them now have a settled shape and one of them, the percentile test, is
  the only check that works on a loop that arrives already baked.
- **The composite's master is the first audio source here that cannot be re-fetched.** Every
  other sound in the tree is a download, which is why `sfx/masters/` was deleted — the same
  file can be fetched again from the name in `source`. A DAW mix cannot, and the reason the
  artwork keeps its masters forever applies to it exactly. The two CC0 uploads it was built
  from are named on its record and are re-fetchable; the arrangement of them is not, and
  presently exists only on the project owner's disk. As FLAC it is 3.2 MB. `ambient_composite_
  guide.md` reduces the risk without removing it -- the guide reproduces the *method* and the
  intent, but it is explicit that its timings are approximate, and nine renders went by before
  this one.
- **Only the fire's span was searched exhaustively.** The cathedral's search covered the quiet
  passage from 78 to 162 s, not the whole 286 s master, because the choir passages are not
  bed material.
