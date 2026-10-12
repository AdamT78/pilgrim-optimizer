# The board's sounds

## The interface cues

Two files, three cues. `tile.ogg` is both the hover and the selection of a duty tile — the same
mark of sound at two gains, because they are the same event at two strengths. `confirm.ogg` is the
Confirm button.

## Where they came from

All of it is **Kenney's Interface Sounds**, released **CC0** (public domain, no attribution
required). <https://kenney.nl/assets/interface-sounds>

What was downloaded was `preview.ogg` — the montage from that page, not the asset pack. It is 31.5
seconds of roughly a hundred sounds played back to back, 48 kHz stereo Vorbis at about 88 kbps.
These two clips were cut out of it:

| file | from `preview.ogg` | length | rings for | cue |
| --- | --- | --- | --- | --- |
| `tile.ogg` | 0.725 s | 70 ms | 46 ms | hover, select |
| `confirm.ogg` | 0.619 s | 80 ms | 52 ms | confirm |

Both contain the whole of their sound with silence to spare, so neither is a truncation.

## How they were cut, and why it is worth writing down

Mono as `(L + R) / 2`, **no fade in**, a short fade out, **no normalising**, Vorbis q6. Each is
under 5 KB. Three of those four decisions were got wrong first and are only here because the
mistakes were audible.

**No normalising.** The first cuts were peak-normalised to −1 dBFS, which is the reflex for a
sound effect and is wrong for a set of one-shots recorded together: it throws away the one thing
you were listening to, which is how loud they are relative to each other. It sent the confirm out
3.1 dB above the level it has in the montage, and the board plainly did not sound like the picker.

**`(L + R) / 2`, not ffmpeg's `-ac 1`.** That flag sums at `1/√2`, which is 3 dB hot against what
a listener actually hears from the stereo file. Normalising had been hiding it.

**No fade in.** Both sounds take 13–17 ms to reach half their peak, so a 3 ms ramp was inaudible —
but it was also unnecessary, since both start from silence at the cut point. It was removed once
it was measured rather than assumed.

The clips are verified against the source rather than trusted: decoded in a browser and correlated
against `preview.ogg`, `confirm.ogg` matches at 0.619 s with r = 0.9998 and a peak within 0.0002 of
that window; `tile.ogg` matches at 0.725 s with r = 0.9999.

## The cell numbers in the picker are not sound numbers

The clips were chosen from a throwaway page that split the montage by onset detection. It found
172 starts in a pack of about a hundred sounds, so one sound often spans several cells — cells 17,
18 and 19 are three slices of a single 600 ms tone. A cell's label is also not its playback length:
`playSeg` plays the segment plus 30 ms and polls for the stop every 16 ms, so cell 18's "90 ms"
is 120 ms in the ear.

Both of those cost a round trip. `confirm.ogg` was cut from cell 18 twice before cell 2 turned out
to be the sound that was wanted, and cell 2's 80 ms needs no extra 30, because unlike 18 it holds
the whole sound already.

## Why they are cut from a preview and not from the pack

Because that is what was to hand. The pack download from the same page is a hundred individually
named OGG and WAV files at full quality, and when these cues stop being a trial they should come
from there instead: `preview.ogg` is a demo encode, so every clip here has been through a lossy
montage once before being re-encoded. At these lengths and levels that is inaudible, and it is
still the wrong source to ship.

## How the page gets them

`generate_action_board.py` inlines them as `data:` URIs, byte for byte, exactly as it inlines the
pictures — the board is one file that gets opened from disk and handed around, so a cue loaded as
a separate request would be silent for everyone but the person who built it.

The page names cues, not files: it asks for `hover`, `select` and `confirm`, and `bundled_sfx()`
decides which file answers. Giving the hover a sound of its own is a line in the generator.

Gains live in the template, on the clips' natural levels: hover 0.12, select 0.5, confirm 0.7.
0.7 is the picker's own volume slider, so the board plays these at the level they were chosen at.


## The board's sounds, beyond the interface cues

The interface cues above are the whole of what the board plays today. What follows is the set
being gathered for the rest of it: one clip per duty action, per tithe resource and per building.
Most of it is **Sonniss GameAudioGDC 2026** material — royalty-free for personal and commercial
game use, modification and unlimited projects, with no attribution required. The per-file entry in
`../attribution.json` still names the bundle and pack, because where a thing came from is a
separate question from whether credit is owed.

**Two are not, and the difference is a condition rather than a credit.** Silver and Silversmith
come from **Pixabay**, under the Pixabay Content License: commercial use and modification
permitted, no attribution required — but the grant is *conditional on the file not being sold or
distributed standalone*, which the other two licences here are not. Shipping the clip inside the
game is a new creative work and is fine; re-publishing the `.ogg` as a sound effect would not be.
Pixabay also disclaims any guarantee that upstream consents exist, so these two rest on Pixabay's
word rather than on a chain of title. Both are credited to the `freesound_community` uploader.

**And one is neither.** Ordain is **ElevenLabs** text-to-SFX, which was recorded as Sonniss for
weeks and is not. Its permission rests on something no inspection of the file can show: under the
ElevenLabs Terms a free user may use the Services for *non-commercial purposes only* and a paid
user commercially, so the tier at the moment of generation is the whole of the licence. It was
generated on a paid plan. ElevenLabs also sublicenses SFX outputs to other users by default
unless that is turned off, so the clip is not exclusive to this project.

| file | from | what it is |
| --- | --- | --- |
| `duty_actions/ordination_actionA_sfx_v03.ogg` | ElevenLabs, `Sharp_metallic_sciss_#1-1791837288330.wav` | **Ordain.** Three snips at 210, 616 and 1282 ms, cut to 1550 ms. No MP3 anywhere in the chain. |
| `duty_actions/ordination_actionA_sfx_v02.ogg` | ElevenLabs, same WAV | *Superseded by v03, kept.* The full 2000 ms, of which the last ~470 were silence. |
| `duty_actions/ordination_actionA_sfx_v01.ogg` | ElevenLabs, `scissor_1.mp3` | *Superseded, kept.* Five events, two strong snips 526 ms apart. |
| `duty_actions/allocation_actionA_sfx_v01.ogg` | 344 Audio, *Antique Small Metals* | **Allocation.** The first 300 ms of *Tinkering Antique Lock*: two clicks at 12 and 172 ms, a settle at 236, quiet by 278. Allocation has one action, and this is two clicks and done. |
| `duty_actions/clerical_actionB_sfx_v01.ogg` | Pixabay, `freesound_community` | **Silversmith.** *bing1*, a struck bell, 758 ms. Unedited but for the container — and the master is already mono, so it is *not* summed. |
| `tithe/wheat_sfx_v01.ogg` | InMotionAudio, *Velcro* | **Wheat.** *VelcroRip29*, unedited but for the container. |
| `tithe/silver_sfx_v02.ogg` | Pixabay, `freesound_community` | **Silver.** *coins-falling-013*, head trimmed to 425 ms so it speaks at once. |
| `tithe/silver_sfx_v01.ogg` | Pixabay, `freesound_community` | *Superseded by v02, kept.* The full 720 ms, with 299 ms of silence on the front. |
| `buildings/library_sfx_v01.ogg` | 344 Audio, *Antiques — Books* | **Library.** One second of *Pile Of Antique Books Falling Over 8* from 0.806 s. |

### There are no masters here, and that is a departure

Every duty icon keeps its untouched master beside its cut, and for a while these clips did too.
They do not any more: `sfx/masters/` was deleted and the six records in `../attribution.json`
carry `"state": "absent"` instead.

**The reason the artwork keeps masters does not apply to audio.** An image master is model output
— the same prompt will not produce it twice, so losing it loses the artwork permanently. Every
audio master here was an unmodified third-party *download*, named in its record's `source`, and a
download can be fetched again. Keeping 4.1 MB of WAV to guard against a loss that is recoverable
was inheriting a rule rather than applying one.

**What that costs, stated plainly.** Re-deriving a cut now means re-fetching the source first, and
two of the clips are real edits rather than straight conversions — Allocation is the first 300 ms
of a 4049 ms master, Library is one second taken from 0.806 s into a 2796 ms one. Those cut points
are written down here and in the records, so the work is repeatable; it is just no longer
*immediate*. And the Sonniss bundle is a yearly GDC drop, so the four Sonniss sources may be
harder to find later than the two Pixabay ones, which are ordinary library downloads.

The records are kept rather than deleted because each shipped clip still says `derivedFrom` its
master, and the recorded `sha256` is the only way to tell a correctly re-fetched download from a
different take with the same name.

### `originalFilename`, and why prose was not enough

Deleting the masters makes re-fetching the recovery path, and re-fetching needs the name you
would type into a search box. That name now lives in a field of its own on every sound record —
`originalFilename` for the literal filename with its extension, `originalPath` for the bundle and
pack folder it sits in — beside the prose `source` rather than inside it.

**The split exists because the prose had already drifted, in three of six.** Both Pixabay entries
had lost the `freesound_community-` prefix, which is the part that actually finds them. The two
Sonniss entries had been reflowed from

```
METLMvmt_  Tinkering Antique Lock_344 Audio_Antique Small Metals.wav
```

into "…, 344 Audio - Antique Small Metals pack", which looks like a filename and is not one: the
`_` separators carry the creator/pack boundary and rewriting them as hyphens throws it away.
*Antiques - Books* already contains a hyphen, so "344 Audio - Antiques - Books" cannot be parsed
back. None of that was noticed while the masters were on disk, because nobody needed the name.

Which bundle archive each came from was never recorded at all, and Sonniss ships five:

```
wheat       Bundle 3of5  /InMotionAudio - Velcro
allocation  Bundle 1of5  /344 Audio - Antique Small Metals
library     Bundle 1of5  /344 Audio - Antique Books
```

Note the last one: the pack *folder* is "Antique Books" and the *filename* says "Antiques -
Books". They disagree at source. Recording both is the only way to keep that recoverable.

`tests/action_board/test_action_board.py` refuses a sound record with no `originalFilename`, and
refuses one whose value has no audio extension — because a description is exactly what the old
field had decayed into, and it read as a filename right up until someone tried to use it as one.

### Ordain v02, and what a second take from a generator is not

v02 was downloaded as a **WAV**, so Ordain is now the only duty sound with no lossy stage before
Vorbis. Measured on comparable material, the MP3 step v01 went through costs about **1.4 dB** of
extra error on top of what Vorbis does anyway — small, and the reason to take v02 is not really
that.

**It is a different take, not the same sound in a better format**, and that was worth proving
rather than assuming. Correlated against v01 at every 1 ms offset, the best-matching
equal-length window scores **r = 0.12**, where identical is 1.00 and the same performance would
be above 0.9. The snips land elsewhere too:

```
v01  three strong events at  100, 627,  764 ms
v02  three strong events at  210, 616, 1282 ms
```

Same prompt, new audio. A generator synthesises afresh every time, so asking twice gives two
takes of one idea and there is no "download the original as WAV" to be had — which is also why
both records say not reproducible.

**Filing v02 is the switch, and it only recently became one.** The bench resolved every slot by
writing `_sfx_v01.ogg` literally, in three places, so the first second take produced a file
nobody read and a slot still drawing the old one. It now takes the highest version, the way
`bundled_controls()` always has. v01 stays beside it rather than being overwritten, because its
`sha256` is on the record.

v02 peaks at **−0.1 dB** and its source touches 0.0 dBFS at exactly one sample with no run of
three, so it is hot but not clipped. Its last ~500 ms are silence; trimming would save 4 KB and
has not been done, since a tail costs nothing in response time the way a head does.

### Silver's 299 ms of silence, and the fix

`tithe/silver_sfx_v01.ogg` was taken **as downloaded**, and as downloaded its first 299 ms were
silence: it peaked at **−47.6 dB across its first 150 ms** and did not speak until a third of a
second in. That is the one rule this set is built around — *identity lands in the first ~150 ms*
— and it failed it outright rather than narrowly. Exactly the fault `buildings/library_sfx_v01
.ogg` had and had cut out of it, where the master's first 826 ms were silence.

**v02 cuts it**, starting at 295 ms of the master — 6 ms ahead of the first sample above −50 dB,
so no attack is clipped — with a 2 ms ramp seating the opening sample the way Allocation's cut
does. First 150 ms now peak at **−7.9 dB**.

Nothing else moved, which is worth stating because trimming silence looks like it should change
the level and must not. The peak is **−7.9 dB in both versions**: no gain was applied. The mean
rose from −33.2 to −31.1 dB, which is arithmetic rather than loudness — the same energy divided
by less file.

Silver remains the only clip in the set at **24 kHz**, so it is band-limited at 12 kHz and reads
duller than everything around it. No edit fixes that; only a different source would.

### Ordain's dead tail

`v02` ran the full 2000 ms it was generated at, but its content stopped at 1527 — the last ~470 ms
were silence, carried as base64 inside a `data:` URI. **v03 ends at 1550 ms** with a 20 ms cosine
fade across 1530–1550, which costs nothing because the signal is already under −60 dB by then. It
saves 4 KB.

The thing to check when trimming a tail is that you have not taken a transient with it. The three
snips sit at **210, 616 and 1282 ms in both versions**, unmoved, and the final millisecond of v03
reads −80.6 dB, so there is no edge for a click to live on.

A tail is a lesser fault than a head, which is why this one waited: silence at the front delays
the board's answer, silence at the back is only bytes.

**Both cuts were taken from the original downloads rather than from the shipped `.ogg`.** Re-cutting
a Vorbis file to Vorbis is a second lossy pass for nothing when the source is still on disk — and
`originalFilename` is what made it findable.

### What "as is" still costs

A clip used unedited is still **re-encoded**: mono and Vorbis q6, because the board inlines every
sound as a `data:` URI and a stereo 96 kHz master is forty times the size for no audible gain at
these lengths. Nothing else is touched — no trim, no fade, no level change.

**Mono is `(L+R)/2` and only when the source is stereo**, which is worth stating because getting
it wrong is silent. The first pass applied the downmix to every file including the ones that were
already mono, where `0.5*c0 + 0.5*c1` with no second channel means `0.5*c0` — a clean 6 dB drop
that looks like nothing in a waveform and sounds like the clip losing its nerve. Caught by
comparing the shipped peak against the source's.

### The levels, which are the thing to protect

| | peak | mean |
| --- | --- | --- |
| `tile.ogg` · `confirm.ogg` | −2.4 · −1.3 dB | |
| Ordain · Allocation · Library | −2.8 · −2.2 · −2.3 dB | |
| Wheat | −0.2 dB | |
| Silversmith | −0.3 dB | −12.7 dB |
| Silver | −7.9 dB | −33.2 dB |

Wheat and Silversmith are the hottest by about two decibels and may want pulling down once there
is more of the set to hear it against. **That would be a re-render, not a gain in the page**: the
set is levelled by ear and never normalised individually, for the reason the four decisions above
record.

**The mean is in the table for the two Pixabay clips because their peaks do not describe them.**
Silversmith and Silver are 20 dB apart in mean level while being only 7 dB apart at the peak —
Silversmith is a sustained ring that holds energy for most of its 758 ms, Silver is three sparse
transients in 720 ms of mostly nothing. Levelling these two by their peaks would put Silver far
too quiet to hear. They have to be set against each other by ear, which is what the bench's gain
sliders are for.

### A measurement to distrust

Analysing these with `ffmpeg -ac 1 -f f32le` and taking the maximum reports the velcro at
**+2.3 dBFS** and `scissor_2.wav` at **+2.6**, with samples over full scale; `volumedetect` on the
same files reports −0.3 and −0.4. The two methods disagree and the difference was briefly reported
here as the files being clipped. They are not known to be. Measure the **shipped** file with
`volumedetect` and trust that.

### The bench

`../sfx_lab/generate_sound_bench.py` builds a page holding every slot the board has — three tithe
resources, fourteen duty actions, twenty-four buildings — with the ones that have no sound shown
as gaps, because a list of what is missing is a plan and a list of what exists is not. It reads
the clips off disk and the lists out of `duty_text.json` and `configs/buildings.json`, so it
cannot disagree with what ships.
