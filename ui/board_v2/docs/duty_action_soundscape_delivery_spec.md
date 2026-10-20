# Duty Action Soundscape — Delivery Specification

**Revision 2026-10-20.** §§14–16 and the additions marked *(2026-10-20)* are new in this
revision; everything else is unchanged.

Send this with (or before) any Duty Action soundscape package. It is the full list of things
that get checked on arrival. Everything here has been failed by a real delivery at least once,
so none of it is theoretical.

*One qualification on that, added in this revision.* §§1–13 were written from supplier packages
that arrived and were rejected. §§14–16 come from a soundscape this project built in-house, and
every fault in them was made here rather than received. They are in the same document because
the rejection rate does not depend on who made the file, and because three of them are invisible
to every number §§1–13 already ask for.

The destination is a browser game board. Each **stem** you deliver becomes one independently
playable, independently level-adjustable ambient bed. They are started together, mixed in the
browser through one gain node per file plus one gain node per duty action, and looped. That is
why the structural rules below matter more than they would for a normal stereo deliverable.

---

## 1. Deliverables

Deliver exactly these, nothing else:

| Item | Count | Notes |
|---|---|---|
| Individual stems | one per scene element | the real deliverable |
| Reference mix | 1 | plain unity sum of the stems |
| Preview | 1 | 70 s, two passes of the loop |
| Sources & tracks document | 1 `.md` | see §9 |
| Verification file | 1 `.md` or `.txt` | see §10 |

**All audio as WAV.** Do not deliver, reference, or reason about `.ogg` files — the conversion to
Ogg Vorbis (q6, 48 kHz) happens at my end, after acceptance. If a document you write mentions a
filename, it must be a filename that exists in the package.

---

## 2. Format

- **48 000 Hz**, 24-bit PCM WAV, **stereo** (2 channels, interleaved).
- **The action's own length, to the sample**, which the request states. Not 34.98 when 35.000 is
  asked for. Most actions here are **35.000 s = 1 680 000 samples** and that is the default when
  the request says nothing; the tree also holds actions at 25, 25.5, 30, 31, 32.5 and 36 s, so
  the figure is never assumed.
- **Every stem in one action is the same length, with one deliberate exception.** A single
  *continuous* bed may be given a different length so that it drifts against the rest instead of
  pulsing with them every lap — Build Roads' wind runs 31 s under ten stems of 35, and Clerical's
  candle 25.5 s under two of 35. **That exception is asked for in the request or it does not
  exist.** Mixed lengths nobody asked for are rejected.
- All stems aligned to **00:00** — no leading offset, no "starts at 1.2 s so they don't collide".
- Rendered at **final mix level**. Do not normalise stems individually, do not peak-normalise
  anything, do not apply a limiter to individual stems.
- No sample-rate conversion artefacts: if a source was below 48 kHz, say so in the sources
  document. Do not upsample 22 kHz material and present it as full-bandwidth.
- **No DC offset.** No significant energy below 20 Hz unless the element is deliberately
  sub-bass and you say so. Inaudible rumble dominates automated width and correlation
  measurements and will cause a stem to be rejected for a reason that has nothing to do with
  how it sounds.

---

## 3. Structure — one stem per scene element

This is the rule that has been broken most often.

**Deliver one file per thing a listener could name.** If the scene has a cart, two workers, a
distant bell and wind, that is four files. Not one "background" file containing all of them.

- **No consolidated stems.** No "all_workers.wav", no "ambience_bed.wav", no "everything
  except the foreground".
- **No pre-merges for convenience.** If you have built a submix to audition, do not ship it.
- **No stem containing eight elements.** A previous package shipped one file with eight
  distinct scene elements in it; it had to be rebuilt from scratch.

**The one exception:** layers that are a single physical event stay together. A hammer strike
is the handle creak, the impact and the stone's response — that is *one* sound captured in
layers, and it ships as one stem. The test is: could a player plausibly hear these at different
times or from different directions? If yes, split. If no, keep together.

If you are unsure about a particular element, **split it and say so in the sources document.**
Splitting too far is cheap to fix; merging too far means a rebuild.

---

## 4. Naming

Lowercase, `snake_case`, one short element name, no version suffix, no spaces, no numbering
unless there are genuinely several of the same thing:

```
quarry_wind.wav
stone_stairs.wav
mason_chisel.wav
distant_cart_01.wav
distant_cart_02.wav
```

Not `Produce Stone - Wind (v14 FINAL).wav`.

---

## 5. Looping and one-shots

For **each** stem, state in the sources document whether it is:

- **looping** (plays end-to-end forever), or
- **one-shot** (a single event that must play once and stop).

A **one-shot** stem must have its event **at the very beginning** of the file, with the rest
silent. The engine starts one-shots at sample 0 and does not loop them. An event placed at 12 s
in a one-shot reads to the player as a sound that arrives late and never comes back.

Do not put a recognisable, identifiable event (a door, a shout, a single bell) in a **looping**
stem. It will repeat every 35 s and the player will notice. Recognisable events belong in
one-shots.

### Build the shape that cannot have a seam, wherever the material allows

**A stem made of events separated by silence has no seam, because nothing is playing at the
join.** Nothing needs to be crossfaded, nothing can click, and no craft is involved. Where the
material is events rather than texture, build it that way: begin and end in silence, and leave
the wrap gap long.

This is not a style preference. In the delivered beds this project holds today, every stem built
that way passes on arrival and several pass by a factor of forty; every loop failure that has
reached the tree has been a stem that *could* have been built that way and was not, or a
continuous texture whose fold was never measured.

### The three shapes and the number each one has to meet

"Seamless" was for a long time the only requirement here that carried no number, and so it was
the only one never checked on delivery. These are the numbers. **Report them per stem in the
verification file** (§10.7).

**1. Intermittent** — any stem containing a silence of 0.25 s or more. *A pause shorter than
0.25 s is texture, not a pause; counting it drags the minimum to nothing and the test says
nothing.*

Measure the silent gaps. The **wrap gap** is the leading silence plus the trailing silence; the
**interior gaps** are the rest.

- wrap gap **≥ the longest interior gap** → safe outright, ship it;
- wrap gap **< 0.95 × the shortest interior gap** → fails, rebuild it;
- in between → report it and say you listened.

*The rule is a ratio, not a difference, because duration is perceived as a ratio.* Two beds have
reached this tree whose wrap gaps were about 60 ms and 68 ms short of their shortest interior
pause — the same error in seconds, and 1.6% against 8.9% of the gap itself, which is five and a
half times apart and lands on opposite sides of what a listener can hear.

**2. Continuous** — no silence of 0.25 s anywhere. The tail has to be folded into the head, and
two numbers say whether it worked.

- **The step across the join**, measured as the absolute difference between the first and last
  sample, against **the file's own median sample-to-sample difference**. It must be **no more
  than 3×** that median. An absolute threshold is meaningless here: the same step is a click in
  a quiet room tone and is inaudible in a gale, which is why the file's own figure is the
  denominator.
- **Whether the join is a hole.** Slide a 1.5 s window across **three** consecutive passes and
  take the short-term level of each. The window centred on the wrap must sit **above the 5th
  percentile** of all those windows. Report the percentile, not only the decibels: a wrap 3 dB
  under the median is fine in a file whose own quietest window is 12 dB under it, and a hole in
  a file that never varies by more than 2 dB.

**The absence of a click is not the absence of a seam.** A mix that begins and ends on exact
zeros butts together with no discontinuity whatever — nothing a waveform view would show — and
still drops two and a half seconds of near-nothing into the bed every lap if the material thins
out at both ends. The two failure modes are independent and both numbers are required.

- **A third number, and the two above do not imply it: the two ends must match in LEVEL.**
  *(2026-10-20)* Report the mean level of the first 0.5 s against the mean level of the last
  0.5 s. **They must be within 1 dB.** A continuous bed built here passed both numbers above —
  its join step was 1.7× the median, comfortably inside the 3× limit — and its head measured
  **3.09 dB quieter than its tail**. There is no click and there is no hole; there is a 3 dB
  step once per lap, which is heard as the bed breathing. The join-step number is a measure of
  *continuity at one sample* and the percentile number is a measure of *a dip*, and a clean ramp
  from loud to quiet across 25 seconds is neither.

- **A gain ramp is not the repair, and it makes things worse.** *(2026-10-20)* The obvious fix
  for the above is to ramp the level back so the ends meet. It does not work: **a ramp's own
  endpoints do not meet**, so correcting a 3 dB step introduced a wrap step of **5.7× the
  median** where the limit is 3×. An audible level step was traded for an audible click. **Pick
  a different window instead** — choose the body for continuity across the seam, which is the
  slower answer and the only one that holds. If no window in the master has matched ends, the
  recording is not a continuous bed and §5's "what not to send" applies.

**3. Metrical** — a stem with a regular pulse: footfalls at a tempo, a tool being swung, a bell.
These close on arithmetic rather than on a crossfade. **The loop length must be a whole number
of cells**; report the cell length and how many fit. A fold that lands mid-cell delivers the next
hit early on every lap — it sounds fine once and announces itself on the second pass. Note that a
spectral or RMS match will happily choose a wrong length here, because it cannot see rhythm.

### What not to send

Do not send a stem that is seamless only because it fades to silence at both ends and back up
again. That is not a loop, it is a stem with a hole in it, and it reads as the scene stopping
and restarting every lap.

---

## 6. Stereo

Stems are played through a browser stereo path. A `StereoPannerNode` **folds** stereo input —
it does not rotate it — so anything delivered as fake stereo collapses badly.

- **No exact dual mono.** If both channels are sample-identical, the file is mono and should be
  declared mono, not dressed as stereo.
- **No Haas/delay widening.** A short inter-channel delay is detected by a ±400 ms lag search
  and will be rejected. Real decorrelated material reads low across the whole lag range; a Haas
  pair reads 0.8 or higher at its delay.
- **No scaled-copy "stereo" where the material is meant to be diffuse.** For a bed that should
  sound like a space or a group — wind, a crowd, water, several workers — a scalar fit of side
  against mid must leave most of the side energy unexplained. If it leaves only 20–30%, the
  side signal is largely a scaled copy of mid, which is a mono source panned, not a field.
  **This rule does not apply to a point source.** A single machine, a lamp, a bird, one tool in
  a fixed position *should* be placed by panning, and a fit that explains nearly all of its side
  energy is the correct answer for it. Say in the sources document which stems are point sources
  so the two cases can be told apart.
- **Every stem gets a width target, including the placed ones, and placing is not sizing.**
  Saying where a source sits says nothing about how much space it takes up, and a source given a
  position and no width is a direction with nothing in it. This has to be stated per stem,
  because a mono recording panned to a position lands near −27 dB side/mid on its own, and that
  is what happens when the instruction stops at "placed".
- **Width targets** (side/mid energy ratio):
  - continuous beds (wind, crowd, water, fire): **−6 to −8 dB**
  - a close or foreground source with a room around it: **−9 to −12 dB**
  - a distant or small point source: narrower, but still **not below about −14 dB** — a lamp has
    a flame around it, a bird has air around it
  - intermittent material is **placed** in the field rather than widened, which is a statement
    about how its width is made, not permission for it to have none
  - anything beyond about **−20 dB** is effectively a mono source with a pan on it. If that is
    genuinely wanted, say so per stem and say why
- Width comes from genuinely decorrelated material (different takes, different mic positions,
  real diffusion), not from a widener plugin on a mono source.

---

## 7. Mono fold-down

Everything must survive summing to mono, because some players will hear it that way.

- Sum L+R to mono and compare per-octave-band energy against the stereo original.
  **Each band must be within 1 dB — but only count bands carrying at least 1% of that stem's
  energy.** An empty band produces a large, meaningless deviation: two otherwise clean stems
  "failed" this test at 1.45 and 1.67 dB in bands holding 0.00% of their content. Report the
  energy share beside each band's figure so the weighting is visible.
- Report the **absolute** fold of the delivered stem, not a change against a previous version,
  and compute each band separately. A single broadband number repeated into nine band slots is
  not a per-band measurement, and a fold figure that comes out positive is not a fold figure.
- The *shape* matters more than the number: a flat span across octaves is the signature of real
  decorrelation. An uneven, scalloped pattern is comb filtering and means the width is fake.
- Note the arithmetic: a 1 dB fold limit mathematically caps width at about **−5.87 dB**
  side/mid. If a stem measures much wider than that *and* folds within 1 dB, one of the two
  measurements is wrong — recheck before shipping.

### Width is measured with the pan taken out, and here is why

**Panning a source creates side energy.** So `10·log10(E_side/E_mid)` on a stem that sits off
centre is partly a statement about *where* the source is, not about how big it is. Two
consequences, both of which have cost a round trip here:

**A pan imposes a floor on side/mid that no amount of narrowing can get under.** For balance *B*,
with `r = 10^(B/20)`, a perfectly correlated source cannot measure narrower than

> `20·log10( (r − 1) / (r + 1) )`

| balance | narrowest possible side/mid |
| ---: | ---: |
| 2 dB | −18.8 dB |
| 4 dB | −12.9 dB |
| 5 dB | −11.0 dB |
| 6.5 dB | **−8.93 dB** |
| 8 dB | −7.3 dB |

A request that asks for 6.5 dB L and −10 to −12 dB side/mid is asking for something that does not
exist. **If a width target is below the floor its balance imposes, say so and do not try to meet
it** — that combination has been written here and had to be withdrawn.

**And a stem can hit a width target while having no width at all.** Four beds in one recent
action measured −10 to −12 dB side/mid, inside their stated band, and were between −15 and
−32 dB once the pan was removed: direction with no size, which is the fault the band was meant to
prevent.

**So width is specified and reported as the de-panned figure.** Scale one channel so the two
carry equal energy, then take `10·log10(E_side/E_mid)` on the result. That number belongs to the
source rather than to its position, cannot conflict with a balance target, and is what the width
targets in §6 and in a request's layout table mean. Report the delivered side/mid as well — both
are useful, and the difference between them is the pan.

*Width therefore has a ceiling set by the fold limit and a floor set by nothing at all: once the
pan is out of it, a mono source reads −∞ and that is the honest answer for a point.*

### The fold ceiling is per band, and it tightens as you pan out

The −5.87 dB cap above is the figure **at centre, broadband**. Two corrections, both of which have
cost a round trip here:

**It applies band by band.** A stem can measure −11 dB wide overall and still fail, because the
average hides one octave that is far wider than the rest. Check the widest band that carries 1%
or more of the stem, not the broadband figure.

**And the cap falls the further the stem is panned**, because the pan contributes side energy of
its own on top of the stem's:

| balance | widest any band may be, de-panned |
| ---: | ---: |
| centre | −5.87 dB |
| 3 dB | −6.36 dB |
| 4.8 dB | **−7.22 dB** |
| 6.5 dB | −8.68 dB |
| 8 dB | −11.12 dB |

A bed whose 1 kHz octave was −5.9 dB wide passed at one placement and failed at another with not
one sample changed, because the move took the requirement from −5.87 to −7.22. **Neither figure
is visible in a broadband width number**, which is why the band table in §10.5 is required rather
than optional.

### Leave margin, because the encode widens *(2026-10-20)*

You deliver WAV and §1 keeps it that way. What ships is **Ogg Vorbis q6**, encoded at my end, and
**the encode is measured rather than assumed** — it is what the game plays. Vorbis quantisation
noise is uncorrelated between channels, so it lands in the side signal and every bed comes out of
the encoder slightly wider than it went in.

Measured across one nine-bed action: the broadband fold moved by 0.01 to 0.06 dB, which is
nothing, and **the worst octave moved by up to 0.3 dB**, which is not. Three beds that measured
−0.75 to −0.87 dB in their worst band on the 24-bit master came back at **−1.07 to −1.24 dB**
after encoding and had to be corrected and re-encoded.

**So treat 1 dB as the figure the `.ogg` has to meet, and deliver inside about −0.85 dB in every
band carrying 1% or more.** A stem that measures 0.95 dB on the master is not passing; it is
failing with the evidence not yet collected. *A fourth bed in that action measured −1.86 dB at
16 kHz on its own master and was never the encoder's fault at all — it arrived over the limit,
and the per-band table in §10.5 is what found it.*

### The mix folds too, and so does any 400 ms of it *(2026-10-20)*

§10.5 asks for the fold of each stem. **Run it on the reference mix as well, and run it on a
window around the loudest event in the action.** Stems that each pass can still sum to a mix that
does not, and a 450 ms window can fail inside a lap that passes.

In the action this was found in, every stem passed, the whole mix passed at −0.354 dB, and a
**450 ms window around the heaviest event folded −1.259 dB at 500 Hz**. Nothing could be done
about it — halving the side signal moved it 0.4 dB and shifting the pan 1.8 dB moved it 0.14 dB,
because the side energy in that band is intrinsic to the recording — but it is a declared
exception rather than a surprise, which is the difference §10's last line is about.

**Report: the mix's per-band fold, and the per-band fold of a 400–500 ms window centred on the
action's loudest event.**

---

## 8. Levels

- **If you replace the source behind an existing event, preserve its shape in time, not only
  its level and spectrum.** Matching RMS, peak and per-octave energy over the window does not
  constrain when the energy arrives, and that is usually what the event *is*. A cleave was once
  swapped for different rock at the same energy and the same spectrum to within 0.6 dB in every
  band: what changed was that a cascade building over a third of a second, followed by half a
  second of loud debris, became a single crack followed by a quiet wash. It passed every stated
  check and was not the same sound. State, for the window: when the peak arrives relative to the
  onset, how long the event takes to fall 20 dB below its own peak, and what fraction of the
  window's energy is still to come 0.3 s after the peak.
- **No single moment more than about 4 dB above the rest of its own stem**, unless that peak is
  the deliberate point of the stem and you say so in the sources document. A stem whose peak is
  8 dB above its own body cannot be level-matched against the others — any setting is either
  too loud for the peak or too quiet for the body.
- Set relative levels **within** the action so the scene is balanced as delivered. The reference
  mix is a unity sum, so the balance I hear is the balance you set.
- Do **not** attempt to match levels against a *different* duty action. You only ever hold one
  package at a time and cannot hear the relationship. Cross-action balance is set at my end with
  a single per-action gain, which preserves your internal balance exactly.
- No limiting, no bus compression, no "mastering" of individual stems or of the reference mix.

---

## 9. Sources & tracks document

One `.md` listing, per stem:

- filename
- what it is (one line, plain English)
- looping or one-shot
- source: generated, or a named library asset with its original filename and licence terms
- any sample-rate or bandwidth caveat
- anything deliberate that would otherwise look like a fault (intentional point source,
  intentional peak, intentional sub-bass)

Plus a short paragraph on what the scene is meant to depict as a whole.

---

## 10. Verification file

Not a claim that it was verified — the numbers themselves, produced by actually running the
checks on the files in the package as shipped.

Required:

1. **SHA256 for every file** in the package: every stem, the reference mix, the preview.
2. **Reference-mix proof**: the reference mix must be a bit-exact unity sum of the delivered
   stems. Report both:
   - maximum absolute sample difference, and
   - **count of differing samples — this must be 0**.
   "Sounds the same" and "difference below −90 dB" are not acceptable. Zero.
3. **Per-stem length in samples** (all equal, all 1 680 000).
4. **Per-stem side/mid ratio in dB, both as delivered and de-panned** (see §7), and whether the
   channels are identical.
5. **Per-stem mono-fold deviation**: worst octave band, in dB, with the share of the stem's
   energy that band carries — counting only bands carrying at least 1%.
6. **Per-stem peak and RMS**.
6b. **Per-event balance and per-event de-panned width, for any stem holding more than one
   placed event.** One number per stem describes a stem that is in one place; for anything else
   it is an average of positions the stem is never at, and it will hide the fault rather than
   report it.

   *Two deliveries have been accepted on a whole-stem figure and then found wrong.* A bed of
   four bird calls measured a tidy 4.8 dB right and held two calls at 2.6 dB right and two at
   **16.1 dB right** — the hardest-panned events this project has produced — and the whole-stem
   number was exactly on target throughout. The same bed measured −11.45 dB of de-panned width
   and had **none**: every event was exact panned mono, and the figure was the gap between the
   two positions being counted as width.

   So: if a stem has more than one placed event, report **balance and de-panned width for each
   event**, and say which events belong to which source. A stem whose events are meant to share
   one position should show them within about a decibel of each other.

7. **Per-stem loop numbers**, per §5, whichever of the three shapes applies:
   - *intermittent* — the wrap gap, the shortest and longest interior gap, and which of the three
     verdicts it lands on;
   - *continuous* — the step across the join as a multiple of the file's own median
     sample-to-sample difference, and the wrap window's percentile across three passes;
   - *metrical* — the cell length and how many fit the loop.
   A one-shot needs none of these; state that it is a one-shot and that its event starts at
   sample 0.
8. **Per-stem left/right balance**, as `10·log10(Eʟ/Eʀ)` over the whole stem, positive to the
   left, so the layout can be checked without re-deriving it from the audio.
9. **Per-stem loudest-to-second-loudest event gap**, in dB. *This is the statistic that catches a
   replayed sample, and an interquartile spread does not:* a stem whose five loudest events are
   one recording retriggered scores a healthy spread and reads 0.00 dB here.

If any number falls outside the spec, ship it anyway with a one-line note saying why it is
intentional. A declared exception is fine; an undeclared one costs a round trip.

---

## 11. Ordering — do this last, and once

If you change *any* audio after generating the reference mix, the preview, the hashes or the
documents, **all of them are stale**. This has broken three deliveries.

The order is:

1. Finalise every stem.
2. Then build the reference mix from those exact files.
3. Then render the preview.
4. Then compute all hashes and measurements.
5. Then write the documents.

Do not update one stem and patch the hash list by hand.

---

## 12. Checklist before you send

- [ ] Every stem 48 kHz / 24-bit / stereo, at the exact length the request states
- [ ] All stems the same length and aligned to 00:00, bar a drifting continuous bed that was asked for
- [ ] If this is an addition to an existing action: §13 read, mix is the sum of the new stems only
- [ ] One file per scene element; no consolidated or convenience stems
- [ ] Each stem declared looping or one-shot; one-shot events at sample 0
- [ ] No recognisable repeating event in any looping stem
- [ ] Every looping stem's §5 numbers measured and reported: wrap gap against interior gaps, or
      join step and wrap percentile, or cell count
- [ ] Anything built as events in silence rather than as texture, where the material allowed it
- [ ] Left/right balance and loudest-to-second-loudest gap reported per stem
- [ ] No dual-mono, no Haas widening; no scaled-copy side signal on anything diffuse
- [ ] Width in range **de-panned**, reported both ways; no width target below the floor its
      balance imposes; point sources and anything narrow or wide by intent are declared
- [ ] **No band carrying 1% or more is wider than the ceiling for that stem's balance** (§7)
- [ ] **Multi-event stems report balance and de-panned width per event**, not only per stem
- [ ] Mono fold within 1 dB on every band carrying 1% or more of the stem, energy shares shown
- [ ] **Every band carrying 1% or more folds inside −0.85 dB**, leaving the encode its margin (§7)
- [ ] **The reference mix's per-band fold reported**, and that of a 400–500 ms window centred on
      the action's loudest event (§7)
- [ ] **Head and tail of every continuous stem within 1 dB of each other** (§5)
- [ ] **Every licence read before the source was measured**; nothing NonCommercial or ShareAlike
      anywhere in the package (§14)
- [ ] **Every element's in-point stated to the millisecond** beside its source filename (§14)
- [ ] **Each source scanned for anti-phase regions** before the cut window was chosen (§14)
- [ ] **Any event within 250 ms of a louder one declares the gap and the band-level difference**
      (§15)
- [ ] **Any stem repaired after first measurement has every number re-reported**, not just the
      one that was fixed (§16)
- [ ] Any replaced event keeps its shape in time, stated as peak timing, decay and tail energy
- [ ] No stem peak more than ~4 dB above its own body unless declared
- [ ] No DC offset, no sub-20 Hz energy unless declared
- [ ] Reference mix is a unity sum with **0 differing samples**
- [ ] 70 s two-pass preview rendered from the final files
- [ ] SHA256 for every file, computed after all audio was final
- [ ] Sources document names only files that exist in the package
- [ ] No `.ogg` anywhere

---

## 13. Adding beds to an action that already has some

Most of this document assumes you are building a whole duty action. Sometimes you are adding two
or three beds to one that already exists and is in the game. Everything above still applies,
with five differences.

**You are delivering an addition, not an action.** The reference mix of §1 is the plain unity sum
of **the new stems only**, and that is the file the §10 reconstruction check runs against. You may
also supply a listening mix of the new stems together with the existing ones, named so it cannot
be mistaken for the deliverable; it is not verified and must not be the file the hashes describe.

**Length is matched, not assumed.** The request states the length the action already runs at, and
the new stems match it to the sample.

**The existing beds come to you as `.ogg`, and they are reference, never material.** This is the
one place where §1's "do not deliver, reference, or reason about `.ogg` files" is relaxed, and it
is relaxed in exactly one direction. Listen to them, measure them, match level and placement
against them, name them in your document. **Do not decode one and build a stem out of it, do not
re-encode one, and do not include one in the package.** Everything you deliver is built from
lossless sources, because the `.ogg` is already a lossy encode and a second generation through
the same codec is loss stacked on loss for no gain. If you need the lossless original of an
existing bed in order to match something, ask for it rather than working from the `.ogg`.

**The action already has a soundstage and the new beds join it.** The request gives their
positions, read off the action's artwork the same way the existing ones were. **Do not place a new
bed where an existing one already sits** unless the request says to — two sources at one position
is the fault this project has corrected more often than any other.

**Levels are set within the addition only.** Balance the new stems against each other as you would
any action. Their level against the beds already in the action is set at my end, with the same
per-action gain that preserves your internal balance exactly. Do not try to match the loudness of
a bed you were sent as an `.ogg`: that file carries a trim applied after you last saw it, so what
you are hearing is not the level it was delivered at.

---

## 14. Sources, and the order the checks go in *(2026-10-20)*

### The licence is read before anything is measured

**Not after it is chosen, not after it is built, not at filing.** This project has twice taken a
source a long way on measurement alone and then found it unusable:

- a wooden-chair recording was measured in full, ranked against four alternatives and written
  into a build prompt before its page was opened. **CC BY-NC 3.0.**
- a grain recording was cut, placed, mixed into a delivered lap and auditioned. It was caught
  only by a provenance audit, days later. **CC BY-NC 4.0.**

Both were thrown away along with the work resting on them. **Open the licence page first. If it
is not CC0, public domain, or a bundle this project already holds, it does not get measured.**
NonCommercial and ShareAlike are both disqualifying — this is a commercial game.

### Name the in-point, not just the file

§9 asks for the original filename and licence. **Also give the timestamp you cut from**, to the
millisecond, for every element: `264757__kessir__…wav @ 32.290 s`.

This costs you one line and it is the difference between provenance that can be checked and
provenance that has to be believed. Three records in this tree named a recording that was not in
the stem, each with a **sha256 that still matched its own file**, so every integrity test passed
for weeks. They were caught by cross-correlating the stem against the claimed source — which
works, and reads r = +1.0000 on a straight excerpt, but only tells you *which* file, not *where*.
With an in-point stated, the check is arithmetic.

### Check the source for anti-phase regions before you cut

A recording can be fine in one place and unusable 400 ms later. **Scan the whole source for mono
fold before choosing a window**, not just the window you like.

One recording used here folds **−3.4 to −5.8 dB in mono between 12.0 and 13.8 s** and is clean
elsewhere. An element was cut from 12.380 s, inside it, and the bed folded −4.46 dB whole and
−5.94 dB at 500 Hz. Worse: **re-cutting did not fix it** — seven alternative windows were
measured and 250 and 500 Hz fail across the entire file, so the repair had to be a side-scale
that cost 2 dB of width. All of that was visible in the source before a single cut was made.

### A filename is not a description, and neither is your memory of it

An element labelled `longer_stone_notch` was carried through three rounds as the third notch in a
tally. Measured, it is a **1.34 s low drag carrying 0.7% of its energy above 4 kHz**, where a real
knife cut in the same bed carries 12.6 to 14.5%. It is a good sound and it was the wrong name,
and the label survived because nothing anyone measured was the thing the label claimed.

**State what each element is in terms of what it measures**, not in terms of what the file it came
from was called.

### If it sounds broken rather than like the material, measure below 125 Hz

Five candidate cloth recordings were auditioned here; two cloth beds were built and rejected by
ear before the third worked. The difference turned out to be one number. **A recording that reads
as the material has almost nothing below 125 Hz. One that reads as a broken clip is dominated
there** — the rejected candidate carried **77.9% of its energy below 125 Hz**, which is
microphone handling noise, not fabric, and an LF thump firing in time with every movement is
exactly what "that doesn't sound like cloth" means. The one that worked has **1.6%**.

This generalises to any close-mic'd soft material: cloth, leather, paper, rope. **Run the check on
the audition pile, before building.** It is cheap and it sorts the pile.

---

## 15. Audibility is not level *(2026-10-20)*

**A quiet event placed just after a loud one is not heard, and no peak measurement will tell you
so.** Forward masking after a loud transient covers **100–200 ms**. Inside that window a sound
20 dB down is not quiet, it is absent.

This project built the same fault three times before naming it. A stone landing, with grain and
coins meant to jump in sympathy 30 ms later:

| | placed at +30 ms | placed at +210 / +250 ms |
|---|---|---|
| grain scatter, below 125 Hz | 31.2 dB under the landing | clears the mask, audible |
| coin pile shift, below 125 Hz | 60.7 dB under the landing | clears the mask, audible |

Each time, the check applied was **peak of the new thing against peak of everything else**, a
margin of a few decibels was called clear, and the result was reported as audible when nobody
could hear it.

**A peak-vs-peak margin is not a measure of audibility** and on this kind of event it is not even
weak evidence. The questions that matter are *how long after the masker* and *in which bands*.

**So: when an event is placed within 250 ms of a louder one, state the gap in milliseconds and the
level difference in the bands they share.** If the gap is under 100 ms, move it or say why it is
meant to be subliminal.

---

## 16. A repair aimed at one number can break another *(2026-10-20)*

Three beds here were too wide at 16 kHz after encoding. The fix is standard and correct: **sum the
two channels above 10 kHz.** It worked — every band came inside the limit.

It also destroyed each file's digital silence. **An FFT taken over the whole buffer is not
time-limited**, so energy from the loud moments leaked into every silent sample, and one bed went
from **91.7% exact digital silence to 0.0%**. Nothing in the width measurement could see it,
because width was the number being fixed.

The silence mattered: these are intermittent beds whose §5 loop verdict is computed from their
silent gaps, and a bed with no silence has no gaps to measure. The mask was restored — zero
everything below −90 dB of peak — and all three re-encoded and re-verified.

**The general rule: after any spectral or channel-domain repair, re-run every number the stem had
already passed, not only the one you were fixing.** In practice that means re-reporting §10.4
through §10.9 for any stem you touch after first measuring it, and §11's ordering rule exists for
the same reason one level up.

---

## Appendix — failures seen in previous packages

Listed so they can be avoided rather than rediscovered:

- One stem containing eight separate scene elements, shipped as "the background".
- A reference mix that was not rebuilt after stems changed, so hashes described files that no
  longer existed.
- A reference mix with bus processing on it, so it was not a unity sum and could not be
  verified against the stems.
- Stereo width produced by a short delay between channels, which collapsed to comb filtering on
  mono fold.
- A "stereo" wind that was exact dual mono.
- Four foreground stems delivered at −26.7 dB side/mid — position correct, no size at all —
  because the layout they were built to said *placed* and never said how wide.
- A replaced event matched on level and spectrum but not on its shape in time, so a cascade
  came back as a single crack with identical measurements.
- A verification file reporting one broadband mono-fold figure in nine per-octave slots, and a
  correlation against a file the supplier did not hold.
- A one-shot event placed mid-file, which in play sounded like a sound arriving late and then
  never returning.
- A stem whose single peak sat 8 dB above the rest of itself, making it impossible to balance.
- A verification document asserting that checks had passed, with no numbers in it.
- **A whole-stem balance that was exactly on target over a stem that was never there**: four
  bird calls averaging 4.8 dB right, two of them at 2.6 and two at 16.1. The average satisfied
  the layout table while the bed held the hardest-panned events in the project.
- **A whole-stem de-panned width of −11.45 dB on a stem with no width at all**, where every
  event was exact panned mono and the figure was the distance between two positions.
- **Four looping stems that do not loop**, found only when the whole tree was tested at once
  rather than package by package. Each had its wrap gap land shorter than its own shortest
  interior pause — in one case 8.8 s against 10.4 s — so the one moment that breaks the pattern
  is the loop point. All four had been declared seamless. This is what §5 now carries numbers
  for, and the numbers would have caught every one of them on the day it arrived.
- **Five keys on a 5.2-second grid, all five peaks bit-identical** at one raw sample value, with
  the footsteps of the same scene sitting on the same grid — five people doing the same thing at
  the same level at the same interval. The supplier's reported spread figure called this healthy,
  because an interquartile spread cannot see it. See §10.9.
- A continuous bed carrying a **6.4-second cell repeated five times** inside a 35-second loop, so
  the texture itself pulsed.

### Added 2026-10-20, from a soundscape built in-house rather than received

- **A continuous bed that passed both loop numbers and pumped once a lap.** Join step 1.7× the
  median, wrap window well above the 5th percentile, and a head **3.09 dB quieter than its tail**.
  Neither number can see a ramp. See §5.
- **The repair for it made it worse**: a gain ramp to bring the ends together introduced a wrap
  step of 5.7× the median, trading an audible step for an audible click.
- **Three beds that passed the fold limit on the master and failed it on the `.ogg`**, by up to
  0.3 dB in their worst octave, because Vorbis quantisation noise is uncorrelated between
  channels. A fourth was **−1.86 dB at 16 kHz on its own master** and had never been the
  encoder's fault.
- **The fix for those three destroyed their digital silence** — a 10 kHz channel sum via an FFT
  over the whole buffer is not time-limited, and one bed went from 91.7% silence to 0.0%. The
  number being fixed was the only one being watched.
- **Two CC BY-NC sources taken deep into the work on measurement alone**, one of them built,
  mixed, delivered and auditioned before anyone opened its licence page.
- **An element cut from the one anti-phase region of an otherwise clean recording**, folding
  −5.94 dB at 500 Hz, where the region had been measured and written down days earlier for a
  different purpose.
- **A sympathetic event placed 30 ms after a loud transient and reported as audible**, three
  separate times, on a peak-vs-peak margin that cannot see forward masking. It was 31 dB under
  the masker in the bands they shared.
- **An element carried through three rounds under a name taken from its filename**, which
  measurement showed it was not: 0.7% of its energy above 4 kHz where the thing it was called
  carries 12.6 to 14.5%.
- **Three `attribution.json` records naming a recording that was not in the stem**, each with a
  sha256 that still matched its own file, so every integrity test passed throughout. A hash
  proves the file has not changed; it says nothing about whether the record describes it.
