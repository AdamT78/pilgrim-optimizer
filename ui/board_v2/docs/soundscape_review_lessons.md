# What reviewing the soundscapes taught, and what it cost to learn

Companion to `duty_action_soundscape_delivery_spec.md`. **The spec is what the supplier is asked
for; this is what we learned by checking it.** Where the spec states a rule, this says which
mistake produced it, what it measured, and how it was caught — because a rule whose reason has
been forgotten gets dropped at the first inconvenience, and several of these rules look arbitrary
until you know what they cost.

Written 2026-10-19, after six duty actions, eighty-five beds and four rounds of redelivery.
Nothing here is theoretical. Every item is a real file and a real number.

**It is also, deliberately, a record of our own faults.** Of the rounds this project spent on
redelivery, **both of the two that cost a full round were errors in the request, not in the
delivery.** A lessons document that only lists what the supplier got wrong would be the most
misleading thing in the tree.

---

## 1. A whole-stem number lies about a stem holding more than one placed thing

**This is the single most expensive lesson here and it arrived three times in three days, wearing
a different face each time.**

| | the number that lied | what it hid |
|---|---|---|
| Build Roads, 2026-10-17 | `side/mid` | the pan, counted as size |
| Allocation / Build Shrine, 2026-10-18 | whole-stem **balance** | two positions 13.5 dB apart |
| Build Shrine, 2026-10-19 | whole-stem **de-panned width** | that same split, counted as size |

**The balance case.** Allocation shipped a door bed reading **−0.23 dB** overall, which would have
filed it as centre. It held three doors at **+13.1, −5.5 and −8.0 dB** and nothing at centre at
all. Build Shrine then did it again from the other side: `crows_ravens` held two bright calls at
6.2 dB left and two darker ones at 7.3 dB right, averaging to the 4.1 dB left that was filed. *A
prescribed balance of 4.8 dB right translated that split as a block* and put two calls at
**16.1 dB right** — the hardest-panned events this project has produced, three decibels past
Allocation's door. The whole-stem figure read exactly on target throughout.

**The width case is subtler and nearly caused a wrong rejection.** When those four calls were
brought together, the stem's de-panned width fell from **−11.45 dB to −95.68**, which reads as a
bed losing everything. It had nothing to lose: measured individually, every event in the previous
version was *already* exact panned mono — **−102.7, −92.5, −93.5 and −106.1 dB**. The −11.45 was
the distance between the two positions being counted as width. De-panning a stem by its
whole-stem energy ratio does not de-pan an event sitting at a different balance from the stem
average, and the leftover per-event pan survives into the side channel. Modelling the old file as
four mono events at their measured balances predicts **−10.1 dB** of apparent width from the split
alone, against the −11.45 measured. Essentially all of it.

> **A de-panned width figure is meaningful only for a stem whose events share one position.**
> For anything else, measure per event — and that is now §10.6b of the spec and rule 6 of
> `soundstage_layout.md`.

*The supplier's verification file reported the per-event figure and ours did not.* It was not
asked for in that form and it is the number that settled it. That is the general shape of the
lesson: **the right granularity is a property of the stem, not of the report format.**

---

## 2. A pan imposes a floor on as-filed width, and a request can ask below it

For a balance *B*, with `r = 10^(B/20)`, the as-filed `side/mid` **cannot go below**

```
20 · log10( (r − 1) / (r + 1) )
```

At 6.5 dB that is **−8.93 dB**. The Build Roads request asked for −10 to −12 dB at that balance,
which does not exist. **Five rows were affected and two were wholly impossible**; the other three
straddled their floor and landed inside their bands, so nothing flagged them.

**The supplier caught it and declared it.** That is worth recording for its own sake — the check
that found this project's error was run by the party being checked.

The fix is not arithmetic, it is the convention: **state width de-panned.** A de-panned target
cannot conflict with a balance target, because the pan has been removed from it. Stated that way
there is no floor to fall under.

---

## 3. The fold ceiling is per band, and it tightens as you pan out

The familiar **−5.87 dB** cap is the figure **at centre, broadband**. It applies band by band, and
it falls the further a stem is placed:

| placement | widest a band may be |
|---:|---:|
| centre | −5.87 dB |
| 2 dB | −6.08 |
| 3 dB | −6.36 |
| 4 dB | −6.77 |
| 4.8 dB | **−7.22** |
| 5 dB | −7.35 |
| 6 dB | −8.16 |
| 6.5 dB | −8.68 |
| 7.2 dB | −9.61 |
| 8 dB | −11.12 |

**A bed can pass at one placement and fail at another with not one sample changed.**
`crows_ravens` has a 1 kHz octave that is −5.9 dB wide, right on the no-pan limit; the move past
4.8 dB took the requirement past what that band could meet. *Neither figure is visible in a
broadband width number.*

**And a band can fail while the broadband figure looks comfortable.** Produce Wheat's three centre
fields read −6.9 to −7.5 dB broadband, inside the no-pan ceiling, and all three exceed the 1 dB
fold limit in one band each — `field_rustle` −1.061 at 2 kHz, `stalk_brushing` −1.035 at 8 kHz,
`wind` −1.014 at 250 Hz. **None of that is pan.** They sit at centre; there is nothing to subtract.

---

## 4. A width that meets its target as filed can be nothing but pan

Produce Wheat is the worked example and it is a bad one. **Ten of its thirteen beds measure
−20.7 to −34.7 dB de-panned** — a direction with no size — while reading −8.3 to −23.6 dB as
filed, which is how every one of them passed. The layout table was written before the de-panned
convention existed, so it asked for as-filed numbers; the delivery met them, at every row.

> **They met the number. The number was the wrong number.**

Build Roads had the same thing in four of eleven: `horse_snorts` at −12.13 as filed and −19.82
de-panned, and the two cart stems at −9.5 as filed and **exact panned mono on the master**,
−111.6 and −96.2 dB.

*The contrast is what makes the case.* `gravel` was the one Build Roads bed that was really about
width, and it went from −21.55 to **−7.52 dB** de-panned — a point pretending to be stone going
down across a whole work site, rebuilt as a genuine field with 100% of its side energy unexplained
by any fit to mid.

**A width near −20 dB or beyond means a mono recording was panned and nothing else was done.**
That gives a direction with no size and is almost never what a scene wants.

---

## 5. The master is not the file the game plays

**Every width and fold figure this project quoted for its first six actions was measured on the
supplier's 24-bit WAV. The board plays the Vorbis encode.** Nobody measured both until
2026-10-19.

**q6 widens.** Quantisation noise is uncorrelated between channels, so it lands in the side signal
and reads as width that is not in the master:

| Devotion bed | de-panned, master → q6 | worst fold, master → q6 |
|---|---:|---:|
| `robe_movement` | −11.32 → **−10.50** | −0.579 → −0.602 |
| `candlelight` | −7.60 → −7.57 | −0.977 → −0.976 |
| `wood_cracks` | −13.54 → −13.45 | −0.952 → **−1.006** |

`wood_cracks` **crosses the 1 dB fold limit on the encode and passes on the master**, by 0.006 dB.
Its 2 kHz band alone widens 0.81 dB, and that band carries **1.4% of a bed that is 81% silence** —
which is exactly where coding noise is the largest share of what is there.

> **The amount of widening tracks how little signal a band has, not how wide it is.**
> The widest bed in that action moved 0.03 dB; the low-level broadband cloth bed moved 0.82.

**The right response was not to re-encode.** Sweeping every shipped `.ogg` found **fourteen of
eighty-five already over the limit**, worst at −4.664 dB, most of them wide when they were cut
rather than wide from the encoder. Clearing one bed's 0.006 dB while thirteen worse ones stand
would have bought tidiness in one record and nothing in the tree. **What should change is the
measurement, not the encoder**: a fold figure belongs to the shipped file.

---

## 6. Two loudness figures that moved while nothing about the level did

**The gate.** Build Shrine's summed loudness went from −30.22 to **−30.93 LUFS** across a rebuild
in which *not one sample of energy moved*. Ungated, the seven stems sum to **−29.88 LUFS before
and after, identically**, and per-stem energies agree to within 0.03 dB. What changed is that the
gate discarded 0.34 dB of the mix before and **1.06 dB** after, because a re-cut bed redistributed
its energy across the lap and more blocks fell under the relative threshold.

**The peak.** The same rebuild took the true peak from −11.57 to −12.03 dBTP. **A summed peak is a
statement about one sample**, and redistributing beds across the field moves where the maximum
lands. The same mechanism once made an action's peak *lower* when a sixth bed was added to it.

> **Check the ungated figure before concluding an action has been turned down.**

A third case, for the opposite reason: integrated loudness on a bed that is four short events
inside 35 s is mostly a measurement of its silence, and it points the wrong way. Clerical's rosary
read **15.9 dB under** the sermon on integrated while its **peak read 6.7 dB over** — a crest
factor of 34.9 dB against the sermon's 12.3. Levelling the two to match on integrated would have
put the bead strikes better than 20 dB above anything the service does. *The same caution applies
to Allocation's keys and is recorded there.*

---

## 7. A correlation proves nothing until it has been controlled

`slow_breathing` is the one bed of six in Devotion that could **not** be traced to its stated
source by waveform correlation — no match at any lag, and none at any local time-scale from ×0.60
to ×1.60. Its long-term average spectrum matched the claimed source at **r = +0.9921**.

**That figure meant nothing until the controls were run.** Against the five unrelated sources on
disk the same measure reads **+0.81, +0.80, +0.78, +0.73 and −0.70**. *Now* the +0.9921 is
evidence, with a 0.18 margin over the best rival.

The record files it as `provenanceConfidence` rather than as fact, because the difference between
+0.99 of spectrum and +0.99 of waveform is the difference between near-certain and settled.

**Related mistakes worth not repeating:**

- **A circular correlation run with the roll in the wrong direction** reported r ≈ 0 where the
  true answer was −0.709. Caught by a brute-force lag scan. *Any correlation that comes back
  suspiciously null deserves one dumb, slow confirmation.*
- **A whole-upload search read r = +0.0028** on a door that, cut to the 7.600–13.600 s excerpt its
  own record stated, matched at **+0.9973**. Searching the wrong span is indistinguishable from
  finding nothing.
- **Vorbis cannot encode a perfectly correlated pair.** Exact panned mono measures about −111 dB
  on the master and arrives at about −32 dB. A bed reading −30 de-panned is a point, not a narrow
  field.

---

## 8. Verify by audio, never by filename

The Devotion provenance pass traced each stem to a file on disk by correlation rather than by
name, and it paid immediately:

- `background_sermon` matched its master at **r = +0.9997** at a constant **85.000 s** offset —
  confirming the supplier's stated "1:25" to the sample.
- `robe_movement`'s four gestures each traced to their own place in the source: 0.26, 6.19, 30.44
  and 44.35 s, at r = +0.977 to +0.985. *The document said four cloth gestures and there are
  exactly four.*
- `prayer_beads` matched the project's own rosary stem strike by strike, twelve of fifteen
  clusters at **exactly zero offset**.

**A file with the right name is not evidence; a file that reconstructs the bed is.**

### The filename lies about the author, specifically

Freesound names a download `<id>__<user>__<slug>` with the username **flattened** — dots removed,
case lowered. `680474__roisingleeson__…` was filed crediting "roisingleeson" when the account is
**roisin.gleeson**, a plausible name belonging to nobody. `188159__yuval__` is **Yuval**, capital
Y. *A freesound filename gives an id and a slug reliably and a username only approximately.* Read
the page — and the page is also where the licence is confirmed, which is this tree's door rule:
**checked at source before anything is measured.**

### "No package folder exists" is not "the stems are gone"

This file's predecessor once declared twenty-one beds probably lost for good, in the confident
tone of something that had been checked, and listed the actions it had given up on. **It had been
searching for package folders.** Twenty of the twenty-one were sitting loose in `~/Downloads`
under their own filenames and the twenty-first was an `.aiff` where a `.wav` was expected.
Actually unrecoverable: **zero**.

---

## 9. A document can be wrong about its own file, and so can a record

- **`fabric` was called canvas.** Its record said *"cloth under tension, which is what a shrine
  under construction has"* and its delivered filename was `fabric_flapping`. The picture shows a
  finished shrine with no canvas anywhere; it is the monk changing posture, twice a lap. *The
  picture and the person who commissioned it settle it, not the filename and not the record.*
- **`slow_breathing`'s stated processing does not describe the file.** The document says
  "pitch-preserving time stretch to fill the 35 s cycle". A uniform stretch would align the
  envelopes once rescaled; rescaled they read **+0.23** against **+0.17** unrescaled, no better
  than chance. The source's exhales sit under a second apart and the bed's sit 4.3 to 6.7 s apart.
  It is a selection placed across 35 s.
- **The one licence left blank was the only one with restrictions.** A delivery document recorded
  four CC0 sources correctly and said of the fifth that its terms "were not supplied in this
  conversation". That fifth was the Sonniss grant — the only source in the folder whose terms
  constrain anything.
- **A later delivery document went backwards on the earlier one**, dropping two source filenames,
  a stated cut offset and every per-stem processing note. Nothing was lost because it had already
  been checked here, but *the package stopped carrying its own provenance* and the records had to
  supply it.

---

## 10. Run the whole tree at once; package review cannot see what a sweep sees

Three sweeps, three finds that package-by-package review had let through for weeks:

| sweep | what it found |
|---|---|
| loop test across every bed | **four looping stems that do not loop**, all four declared seamless |
| mono fold across every shipped `.ogg` | **fourteen beds over the 1 dB limit**, worst −4.664 dB |
| filename search for masters | **twenty-one** "lost" masters recovered, nothing unrecoverable |

**That is a finding about method, not about the files.** A loop test is cheap, and every one of
those beds was reviewed on arrival by somebody who meant to check it. What review cannot do is
compare a bed against the tree. The loop sweep took under three minutes and would have caught all
four on the days they landed.

> **After filing anything, run the sweep. The cost is minutes and it is the only check that sees
> the tree as a whole.**

---

## 11. Our own documents go stale silently, and no guard catches a tense

`test_the_prose_count_of_beds_is_the_number_of_beds` exists because the same mistake happened
twice in one sitting: a status line reading "ten files under six duty actions" while thirteen were
filed. **A bare integer has no tell** — the sentence is fluent, the number is plausible, and
nothing disagrees out loud.

**Prose is worse, and on 2026-10-19 `soundstage_layout.md` was proof.** Three of its six tables
carried headings saying *"and both now fixed"* and *"what the beds measured before"* over bodies
still reading *"it sits at 4.1 dB left"* and *"the ox cart is currently almost centred"* — about
files retired days earlier. Produce Wheat's entire section said **"PRESCRIBED, not yet delivered"**
with thirteen beds in the tree, all thirteen placements landed. None of it was wrong when written.
All of it was wrong by the time anybody read it.

**Three things came out of that**, and they generalise past this one file:

1. **A status table at the top**, one row per action, prescribed versus delivered — the one place
   where state is a fact rather than something inferred from prose.
2. **A rule that the layout file moves at filing**, in the same change as the beds, with every
   present-tense sentence about replaced beds put into the past and the delivered figure beside
   it.
3. **A machine check for the part that can be checked.** A short script parses every delivered
   figure out of the document's tables and measures the named bed: **37 delivered balances across
   six tables, zero disagreements.** It cannot check a tense, but it means the numbers never drift.

### And a guard that is red is a guard nobody reads

`test_every_asset_in_the_tree_has_an_entry` was failing with **197 unrecorded assets**. Every one
of the 197 is gitignored — 160 WAV masters, 36 files in deletion-workaround folders, one reference
image — so **not one shippable asset in the tree is unrecorded** and CI was green throughout. But
the guard had been shouting 197 false things for days, and anyone who glanced at it learned to
look away. *The exclusion it needs is the one it already applies to `generated/` and states in its
own comment: gitignored means not shipped, so it is not an asset here.*

---

## 12. A deliberate decision needs its reason written down, because the reason expires

Clerical's candle bed was **25.5 s against two beds of 35**, and that was on purpose: a continuous
bed at a length of its own drifts rather than pulsing in step, the same trick as Build Roads'
31 s wind under ten beds of 35.

When the Devotion delivery made all six stems 35.000 s, that looked like a regression and was
nearly raised as one. **The project owner pushed back and was right.** The argument was made when
the action had **two** beds, one of them the candle; with **three** continuous beds, moving one off
35 s leaves the other two locked anyway. Measured in 1.5 s windows the three vary by 1.10, 1.41
and 3.51 dB with no detectable event in any of them, and the rule that matters is that a looping
bed holds no recognisable event. Uniform length also buys the stronger check — a reference mix
that is the unity sum of **all six** rather than five with one held out.

> **A decision recorded without its reasoning cannot be re-examined when the conditions change;
> it can only be defended or broken.** This one was recorded with its reasoning and so it could be
> correctly retired.

---

## 13. Both rounds that cost a redelivery were faults in the request

Worth its own section because it is the opposite of what a review log usually says.

- **Build Roads**: the request asked five rows for a width below the floor their own pan imposed.
- **Build Shrine**: the request gave a four-event bed one balance, and the layout file *already
  recorded the rule that forbids it*.

**Both were caught — one by the supplier, one here — and both were cheap to fix and expensive in
rounds.** The structural response in each case was to move the check earlier: the de-panned
convention so a width target cannot conflict with a balance target, and the per-event requirement
so a split cannot hide in an average. **The per-band fold check is now run before the request is
written rather than against the delivery**, which is the point of having it.

The measure of whether that worked: Devotion's request predicted what each as-filed width would
become once the pan was added, before the files existed, and **all six predictions landed within
0.04 dB**. Every placement came back within a thousandth of a decibel.

---

## 14. Small practical rules that each cost something

- **Ask for energy preservation explicitly on a re-pan.** Panning moves energy between channels;
  it must not add or remove any. Where it was asked for, it came back at 0.0000 dB on every stem.
- **Reassemble the reference mix rather than reading the verification file.** It is the cheapest
  strong check there is — every delivery has been confirmed as a bit-exact unity sum by
  reassembling the stems here, and it also catches a mix that was not rebuilt after a stem changed.
- **Versions must count up, and a request has to say so.** Build Shrine's v05 reused the previous
  package's filenames for the six stems whose audio had not changed, because the request asked for
  "the existing names" and meant the stem's identity. **Six names now each denote two different
  pieces of audio.** Every record in that folder has to name its package, and `originalFilename`
  alone does not identify the file.
- **Read the granule, not the decoder.** A loop pinned to a decoder's duration wraps through
  Vorbis padding every lap — 4 to 17 ms of it. The container's last granulepos is the true length
  and must be read **signed**.
- **Side findings get reported, not fixed.** Fixing what you notice while doing something else is
  how a filing turns into a week. Every item in this document that is still open is open on
  purpose.

---

## What is still open

Carried here so it is in one place rather than scattered through five documents.

| | |
|---|---|
| **Produce Wheat's widths** | ten beds at −20.7 to −34.7 dB de-panned; the largest outstanding width job in the tree |
| **Fourteen beds over the fold limit** | worst `give_alms_actionA/alms` at −4.664 dB; `produce_actionB/distant_owl` is the one to open first, its failing band carrying 99.6% of the bed |
| **Two loop failures** | `taxation_actionA/coins` at 0.79× and `produce_actionA/stalk_brushing` at 0.85× |
| **One weak wrap** | `produce_actionB/background_worker_c`, 9th percentile, 10.65 dB under its own median |
| **Produce Stone's five background workers** | all at exactly 0.00 dB balance; needs a re-pan |
| **`build_roads_actionA/horse_snorts`** | lost real width in the rebuild, −14.38 → −19.82 de-panned |
| **`allocation_actionA/page_turns`** | folds −1.72 dB at 125 Hz |
| **Build Shrine's filename collision** | six names, two files each |
| **`bed_facts.py`** | measures padded decodes |
| **Build Roads v01 records** | prose states trims that disagree with their `gainDb` fields |
| **The censer in Devotion's artwork** | hangs at 94% with no sound; an omission that should be a decision |

---

*Everything above is cross-referenced in `duty_action_soundscape_delivery_spec.md` (the contract),
`soundstage_layout.md` (placement per action), `ambient_loop_note.md` (loops) and
`sfx_levelling_note.md` (levels, fold and the encode). This file is the why; those four are the
what.*
