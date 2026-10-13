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
| `tithe/wheat_sfx_v01` | −0.2 dBFS | −0.04 dBTP |
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

The one thing that *is* uniform, and matters more than either: **every clip is mono, Vorbis q6.**
That is the consistency a set levelled against itself needs.

---

## 10. Not done

- **The board does not read `gainDb`.** Today that would change only `tile.ogg` by +0.4 dB and
  `confirm.ogg` by −1.5, since those are the only two clips it plays.
- **Mint keeps its +22.3 dB baked in.** The field is measured from the file as it stands, so
  nothing double-counts, but re-cutting it ungained would retire the one gain exception.
- **`rock_dropping` stays 5.1 dB under the set.** It holds no slot, so this is not urgent.
- **Ordain v03's +0.75 dBTP** is fixed only in the sense that its trim is −4.1 dB. The file
  itself still clips if anything plays it at unity.
