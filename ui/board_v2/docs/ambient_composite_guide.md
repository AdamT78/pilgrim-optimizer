<!-- Added when this guide was filed. Everything from "# Allocation Duty Action Ambient" to
     "# 18. Conceptual final mix" is the document as it arrived, unedited. -->

# Building an ambient bed out of parts, rather than cutting one

**What this is.** Every other bed in `sfx/ambient/` is a window cut out of a single field
recording — the method for that is `ambient_loop_note.md`, and it does not apply here. This one
describes the other way: taking two short CC0 recordings and *constructing* a scene from them,
footfall by footfall. It is filed because the approach generalises even though the recipe does
not, and because the next duty action that wants a scene rather than a room will want it.

**It was written by ChatGPT**, which also wrote the script it describes, working to the project
owner's direction over nine iterations. That is recorded for the same reason every other
`how this was made` note in this tree is: it says how the decisions were reached, and it is not
a rights claim. No audio in the result is model output — every sample traces to one of the two
CC0 uploads named in section 1.

**What it produced.** `allocation_ambient_queue_v09_seamless_loop.wav`, 28.5 s, which ships as
`sfx/ambient/allocation_actionA/`, first as the single file `allocation_sfx_v02.ogg` and now as
the stems `footsteps_sfx_v01.ogg` and `keys_sfx_v01.ogg`, which carry the same wrap and the
same rotation and sum back to it — joined later by `wool_robe_sfx_v01.ogg`, which was placed
into the already-wrapped mix rather than split out of it. See `ambient_loop_note.md` section
11 for what that costs and how it was checked. The 24-bit master is not in this tree; see the
last bullet of that note's section 12 for why that is a question rather than a decision.

**Which parts travel.** Sections 3 to 5 and 17 are the general method — denoise *before* cutting
fragments, extract single events rather than passages, and vary position, level, filtering and
speed to make one recording sound like several sources. Sections 6 to 14 are Allocation's scene
and will not transfer. Section 15 is the loop, and it agrees with `ambient_loop_note.md`
sections 1 and 2 having been arrived at independently: bake the crossfade into the asset, use
equal power, and do not let the file fade to silence and restart.

**One thing to read with care.** Section 15's rotation step is safe exactly as it says — after
the cycle is already seamless — but rotation does not fix a length. See *What measurement said
afterwards* at the foot of this file.

---

# Allocation Duty Action Ambient — Recreation Guide

This document describes how to recreate the **Allocation duty-action ambience** from the two original source recordings used in the final mix.

The goal of the ambience is to simulate a **busy monastery allocation point** where:

- monks stand in a queue;
- the front monk receives a key;
- that monk immediately walks away into the cloister;
- the next monk advances;
- several monks behind him shuffle forward in sequence;
- the place feels active rather than empty;
- pauses are short and deliberate;
- the key handoff is audible as a restrained metallic clink;
- there is **no continuous crowd/voice bed**.

The final ambience is approximately **30 seconds, stereo, 48 kHz** and is intended to loop.

---

## 1. Source files

### Footsteps

**File**

`793361__sadiquecat__walking-to-dead-end-hallway-indoor-okm1-2025-03-16.wav`

**Source**

Freesound — Sadiquecat — *Walking to dead-end hallway indoor OKM1*

https://freesound.org/people/Sadiquecat/sounds/793361/

**Use in the mix**

This recording provides all footstep material. Individual footfalls are extracted from it and then recombined to simulate several different monks moving at different distances and positions.

---

### Keys

**File**

`565909__fenodyrie__keys-jingling.wav`

**Source**

Freesound — Fenodyrie — *keys jingling.wav*

https://freesound.org/people/Fenodyrie/sounds/565909/

**Use in the mix**

Short individual metallic contacts are extracted from the recording and used as the sound of a single heavy monastery key being handed to each monk.

The complete jangling recording is **not** used as-is.

---

## 2. Software / Python dependencies

The recreation script uses Python with:

```bash
pip install numpy scipy soundfile noisereduce
```

Modules:

```python
import numpy as np
import soundfile as sf
import noisereduce as nr
from scipy.signal import butter, sosfiltfilt, resample, resample_poly
```

---

# 3. Footstep source preparation

## 3.1 Remove the background noise first

The original binaural footstep recording contains a noticeable steady room/noise floor.

If short footstep fragments are cut directly from the file and placed into otherwise silent gaps, the background noise audibly switches on and off together with each footstep.

This was the main problem in the early versions of the ambience.

The solution is:

1. identify naturally quiet parts of the source recording;
2. combine these into a noise profile;
3. run stationary noise reduction on the entire source recording;
4. only then extract the individual footfalls.

The quiet intervals used were approximately:

```python
quiet_intervals = [
    (0.00, 0.22),
    (0.55, 0.78),
    (3.55, 3.82),
    (4.22, 4.48),
    (5.48, 5.78),
    (8.00, 8.27),
    (9.30, 9.55),
    (10.00, 10.22),
]
```

The noise reduction settings used were:

```python
nr.reduce_noise(
    stationary=True,
    prop_decrease=0.92,
    n_fft=2048,
    hop_length=512,
    freq_mask_smooth_hz=300,
    time_mask_smooth_ms=70,
)
```

The purpose is **not** to make the recording unnaturally sterile.

It is simply to stop the original recording's room noise from appearing every time a footstep excerpt begins.

---

## 3.2 Extract individual footfalls

Rather than reusing longer walking passages, the final approach extracts **individual footsteps**.

This is important because using intact walking sequences repeatedly makes the ambience sound like the **same person repeatedly walking a few steps**.

The individual footstep peak times used from the original recording were approximately:

```python
step_peaks = [
    0.964,
    1.539,
    2.229,
    2.868,
    4.579,
    5.214,
    5.897,
    7.049,
    7.781,
    8.285,
    9.046,
    9.651,
    10.835,
    11.525,
    12.314,
    14.657,
    15.340,
    15.981,
    16.509,
    17.278,
    17.877,
    18.716,
    19.368,
]
```

For each selected footfall, keep roughly:

```text
130 ms before impact
480 ms after impact
```

This preserves both the impact and some of the natural stone-room tail.

Apply short fades to every extracted footfall:

```text
fade in:  ~40 ms
fade out: ~220 ms
```

This prevents the denoised excerpts from starting or ending abruptly.

---

# 4. Make one source recording sound like several monks

All monks originate from the same recording, so several small variations are used to stop them sounding identical.

For each "monk", vary:

- stereo position;
- volume;
- low-pass filtering;
- walking cadence;
- very small playback-speed differences;
- distance over time.

Recommended speed variation:

```text
~0.95x to 1.04x
```

Keep this subtle.

The aim is not to create obvious pitch-shifted characters. The aim is only to stop repeated footfalls from sounding mechanically identical.

---

# 5. Distance simulation

A monk moving away from the prior should not simply become quieter.

As the monk walks away:

1. reduce level;
2. move the sound gradually toward one side of the stereo image;
3. progressively remove high frequencies.

Example departure:

```text
first step:
    level approximately -4 dB
    low-pass approximately 9 kHz
    near centre

last step:
    approximately 19 dB quieter
    low-pass approximately 2.4–3 kHz
    farther left or right
```

This gives a much stronger impression of someone **continuing down the cloister** rather than simply stopping after a few footsteps.

---

# 6. Queue behaviour

The key idea is that the queue behaves as a **chain reaction**.

Do not treat every monk as an isolated walking event.

A cycle should behave like:

```text
front monk receives key
        ↓
front monk immediately walks away
        ↓
next monk advances toward the prior
        ↓
monk behind him shuffles forward
        ↓
next monk behind also shuffles forward
        ↓
rear monk adjusts position
        ↓
very short settling pause
        ↓
next handoff
```

The departing monk and advancing queue should **overlap**.

This overlap is what makes the location feel busy.

---

# 7. Foreground monk advancing to receive a key

Use approximately **four footsteps** for a monk advancing from the queue to the front.

A useful pattern:

```text
step 1 — distant
step 2 — closer
step 3 — closer
step 4 — near the prior
```

Example relative levels:

```text
-11.5 dB
-8.8 dB
-6.2 dB
-4.4 dB
```

Example low-pass progression:

```text
5.0 kHz
6.2 kHz
7.6 kHz
9.5 kHz
```

Approximate interval between steps:

```text
0.54 seconds
```

The stereo position should also move gradually toward the centre.

---

# 8. Monk walking away after receiving the key

Once the key is received, the monk should **not stop**.

Use approximately **9–10 footsteps across 5–6 seconds**.

Typical cadence:

```text
~0.56–0.59 seconds per step
```

Progressively:

- reduce volume;
- filter more high frequencies;
- move farther left or right.

Alternate departure directions between monks.

Example:

```text
Monk A → exits right
Monk B → exits left
Monk C → exits right
Monk D → exits left
```

This gives the monastery space more width and avoids every monk following exactly the same path.

---

# 9. Make the entire queue move

After the next monk begins advancing, add a **queue ripple** behind him.

The final version used approximately four rear positions.

Example:

```text
Monk behind front:
    2 footsteps
    around -12.5 to -14.5 dB

Next monk:
    2 footsteps
    around -15 to -18 dB

Next monk:
    2 footsteps
    around -17.5 to -19 dB

Rear monk:
    1 footstep
    around -20 dB
```

The starts are staggered by roughly:

```text
0.2–0.3 seconds
```

Do not make all footsteps occur simultaneously.

The sound should resemble the line physically compressing forward:

```text
step-step
   step-step
      step-step
         step
```

---

# 10. Additional rear-cloister activity

The final "busy cloister" version also contains occasional additional rear-line adjustments while the main handoff sequence is happening.

These should be much quieter:

```text
approximately -20 to -22 dB relative to the strongest foreground steps
```

Low-pass around:

```text
2.5–3.0 kHz
```

Pan these farther left/right.

These footsteps are not meant to attract attention.

Their purpose is to stop the monastery from feeling like **only one queue exists in an otherwise dead building**.

---

# 11. Timing of the busy 30-second loop

The final approach used approximately **seven overlapping queue cycles within 30 seconds**.

A new handoff occurs roughly every four seconds.

Approximate departure starts:

```text
0.35 s
4.00 s
7.95 s
11.85 s
15.78 s
19.68 s
23.58 s
```

The next monk begins advancing **before the previous monk has disappeared into the distance**.

Example:

```text
0.35 s   Monk A begins leaving
0.95 s   Monk B begins advancing
1.35 s   queue behind B begins moving

4.00 s   Monk B begins leaving
4.55 s   Monk C begins advancing
4.95 s   queue behind C begins moving
```

The "pause" for receiving the key is therefore short.

The location should feel:

```text
busy → short deliberate handoff → busy → short handoff → busy
```

not:

```text
walk → silence → walk → silence
```

---

# 12. Key handoff sound

## 12.1 Do not use the whole key-jangle recording

The desired sound is:

> one old iron key being placed into a monk's palm

not:

> someone shaking a large ring of keys.

Three useful individual metallic contacts were extracted from the uploaded key recording at approximately:

```python
key_centers = [
    2.659,
    3.417,
    4.101,
]
```

For each key contact, extract approximately:

```text
120 ms before the transient
380 ms after the transient
```

---

## 12.2 Filter the key sound

Remove handling rumble and soften the brightest metallic frequencies.

The filtering used was approximately:

```text
high-pass: 160 Hz
low-pass: 7.2 kHz
```

This makes the key sound somewhat older/heavier and less like a modern bright keyring.

---

## 12.3 Narrow the stereo image slightly

The source is stereo.

For a close hand-to-hand exchange, make the sound somewhat narrower:

```python
mid = stereo.mean(axis=1, keepdims=True)

processed =
    0.65 * original_stereo
    + 0.35 * duplicated_mid
```

Do not collapse it fully to mono.

---

## 12.4 Key level

The extracted clinks were normalized to roughly:

```text
-11.5 dBFS peak
```

before being placed into the ambience.

Then add very small per-handoff level variation, approximately:

```text
±0.5 dB
```

This stops every handoff from sounding identical.

---

# 13. Add a tiny stone-room reflection to the key

The key should sound like it is inside the same cloister as the footsteps.

A simple two-tap reflection was used rather than a large artificial reverb.

Example:

```text
direct key sound

+65 ms reflection:
    -17 dB

+118 ms reflection:
    -23 dB
```

For the first reflection, swapping the stereo channels slightly helps create a natural wall-reflection impression.

Keep this subtle.

The listener should hear **the key**, not "reverb."

---

# 14. Key timing

In the final mix, key clinks occur just before each newly assigned monk begins his departure.

Approximate handoff times:

```text
3.84 s
7.79 s
11.69 s
15.62 s
19.52 s
23.42 s
27.35 s
```

Use the three different extracted key contacts in rotation:

```text
A → B → C → A → B → C → A
```

Apply tiny level and stereo variations.

---

# 15. Make the finished ambience genuinely seamless

The production loop is made from the completed footsteps + keys mix **after all events have been placed**.

Do not rely on a fade-to-silence at the end followed by starting the file again. That creates a recurring perceptual dip.

Instead, overlap the end of the finished mix with the beginning.

The final version uses:

```text
crossfade length: 1.50 seconds
crossfade type: equal-power
source: final footsteps + key mix
```

Conceptually:

```text
tail = final 1.50 s of mix
head = first 1.50 s of mix

wrap = equal_power_crossfade(tail → head)

seamless_loop =
    wrap
    + original audio from 1.50 s
      through 1.50 s before the original end
```

This is a **true overlap**, so the finished loop becomes shorter by the crossfade duration.

For a 30-second source:

```text
30.0 s source
-1.5 s overlap
----------------
28.5 s seamless loop
```

This is preferable to preserving an arbitrary 30-second duration. The important property is that the cycle can repeat indefinitely without an audible reset.

After creating the seamless cycle, the final file may be **circularly rotated** so playback starts during a relatively quiet deliberate pause rather than in the middle of a prominent foreground step.

Rotating is safe **only after the cycle has already been made seamless**.

The recreation script should therefore:

1. finish the complete 30-second footsteps + keys mix;
2. take the last 1.50 seconds and first 1.50 seconds;
3. combine them with an equal-power crossfade;
4. concatenate the remaining middle section;
5. optionally locate a low-energy ~0.6-second region;
6. circularly rotate the already-seamless loop so that region becomes the file start;
7. export the result.

A useful QA check is to concatenate the finished loop three times:

```text
loop | loop | loop
```

Listen specifically across both joins.

There should be:

- no click;
- no sudden change of noise floor;
- no fade-to-silence;
- no obvious restart of the queue;
- no key clink cut in half.

The final production file created from this guide is:

```text
allocation_ambient_queue_v09_seamless_loop.wav
allocation_ambient_queue_v09_seamless_loop.ogg
```

Its runtime is approximately:

```text
28.5 seconds
```

At runtime the game does **not** need to construct another crossfade. It can simply repeat the finished asset continuously:

```js
source.loop = true;
```

or the equivalent looping mechanism in the project's audio system.

When the player leaves Allocation or ends the turn, fade the entire ambience bus out normally. That selection/deselection fade is separate from the seamless internal loop.

---

# 16. Final output

Recommended production output:

```text
duration: approximately 28.5 seconds after seamless overlap
channels: stereo
sample rate: 48 kHz
master format: 24-bit WAV
shipping format: OGG Vorbis according to project conventions
loop behavior: direct continuous repeat
internal loop crossfade: already baked into the asset
```

The working mix retains a final peak around:

```text
-4 to -4.5 dBFS
```

Do **not** consider this the final game loudness.

The finished ambience should subsequently go through the project's dedicated **ambient-loop loudness / gainDb levelling process**.

Ambient loops should be levelled separately from short M200-style one-shot SFX.

---

# 17. Important lessons from the iterations

Several early approaches did not work well.

## Do not paste longer walking excerpts into silence

This makes the ambience sound like:

> one person repeatedly walking a few steps.

Instead:

> extract individual footfalls and reconstruct several different walkers.

---

## Do not leave the original background noise inside every excerpt

Otherwise every footstep causes the room noise to switch on and off.

Denoise the source **before** cutting the individual footfalls.

---

## Do not use a continuous background footstep bed

That removed the intended pauses and created audible editing artifacts.

The background activity should come from **separate low-level footsteps**, not from continuously looping the original recording underneath everything.

---

## Do not make monks stop after receiving their keys

The assigned monk should continue walking away into the distance.

This is one of the most important cues that makes the scene believable.

---

## Do not move only the front monk

When the front position becomes free, the **whole queue should ripple forward**.

This is what transformed the scene from a sequence of isolated footsteps into a busy monastery allocation point.

---

## Keep pauses short

The final interpretation is a **busy working location**.

Pauses represent the brief moment when the key is handed over.

They should not make the entire space go silent.

---

# 18. Conceptual final mix

The final sound should communicate:

```text
[monk leaving → fading into cloister]
          +
[next monk walking toward prior]
          +
[several monks behind shuffling forward]
          +
[occasional distant footsteps]
          ↓
      short key clink
          ↓
      process repeats
```

There should be **no voices, crowd murmur, chanting, music or continuous key jingling**.

The resulting ambience should sound like a physically busy but disciplined monastic administrative space.

---

# What measurement said afterwards

*Added when the file was filed. The guide above is the method; this is what the finished asset
measured, and the two places where measurement had something to add.*

**The problem section 15 solves is real, and here is its size.** The version before this one
(v08) was a 30 s mix whose first and last samples were both exact zeros, so butting it end to
start produced no click at all — which is why it looked loopable. It was not: the first 0.3 s
and last 0.6 s were digital silence and the material thinned from about 26.4 s, so plain
repetition dropped some 2.5 s of near-nothing into the bed every lap. Scored as five bands
across 1.5 s shoulders, head against tail, that butt join was **41.0 dB out with 68.5 dB in the
top band**. The absence of a click is not the absence of a seam, and a file that begins and ends
in silence is the one shape where those two come apart.

**The finished loop checks out.** Three laps measure identically to one pass, so the number on
the record describes what plays. The 1.5 s window straddling the wrap sits at the **19th
percentile** of the loop's own 1.5 s windows — 2.35 dB under its median, where the quietest
window anywhere in the loop is 12.7 dB under it. The step across the wrap is 0.0003 in both
channels, under the file's own median sample-to-sample difference. There is no seam to find.

**Note that the usual shoulder test cannot be used on a baked loop.** Comparing head and tail
shoulders is how `ambient_loop_note.md` section 5 scores a *candidate*; on a loop whose head has
already been crossfaded with its tail it measures the material's own variation and nothing else.
It reads 21.5 dB here, and that figure means nothing. Score candidates, not finished files.

**The keys do not quite keep the cadence the guide plans.** Section 11 asks for a handoff about
every four seconds, and the render gives 3.91, 3.90, 3.92, **4.99**, 3.96, 3.90 s, with the gap
across the wrap landing at 3.92 and so costing nothing. The odd one out is interior, between the
keys at 12.43 s and 17.42 s: a pause about a second longer than the others, repeating every lap.
It is not a seam and it does not read as a restart; it reads as one slower handoff. Whether it
is wanted is a question for the ear, and it is a one-line change to the placement list in
section 14 if it is not.

**Length is a loop's relationship with its neighbours, not only with itself.** This bed plays
under `allocation_wind_sfx_v01.ogg`, and two loops realign only when their lengths do. At 28.5 s
against the wind's 17 s the pair repeats every **969 s**, about sixteen minutes — against 391 s
for the 11.5 s bed this replaced. A 23.510 s cut of the same material, taken as exactly six key
periods, would have given 39,967 s, about eleven hours. All three are long enough; the point is
that **nothing in the tree computes this**, and a future length could as easily be a near
multiple of 17. It is worth a glance at the other lengths on the records before settling one.

**Levelling, as section 16 asks.** The finished loop measures −29.32 LUFS integrated ungated,
true peak −4.54 dBTP. Its authored trim is **−23.0 dB**, which lands it at −52.3 LUFS, between
Silversmith at −49.8 and Alms at −53.4. Bed level is set by ear and there is no target to check
it against; `sfx_levelling_note.md` section 11 records why not.
