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
mistakes were audible. **One clip now breaks two of them on purpose** — see *Mint, the one
clip with gain and EQ* below — and it is an exception with its numbers written down, not a
change of practice.

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
Most of it is **Sonniss GameAudioGDC** material — royalty-free for personal and commercial game
use, modification and unlimited projects, with no attribution required. The per-file entry in
`../attribution.json` still names the bundle and pack, because where a thing came from is a
separate question from whether credit is owed.

**Which GDC bundle is a per-file fact, not a property of the set, and this paragraph used to get
it wrong.** It read "Sonniss GameAudioGDC **2026**" while Brewery and Stone were being added from
the **2024** archive — the records had the year right in both `licenceNote` and `originalPath`,
and the prose here restated it and went stale the moment the set stopped being uniform. The year
is no longer named in this paragraph at all. It lives in each record and in the per-file table
below, which has one owner each; the licence entry in `attribution.json` is deliberately
year-agnostic, since the terms are the same across bundles and only the contents differ. Sonniss
ships a different set of packs each year under separate archives, so `originalPath` naming the
year is what makes a source findable again.

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
| `duty_actions/allocation_actionA_sfx_v01.ogg` | 344 Audio, *Antique Small Metals* | **Allocation.** The first 300 ms of *Tinkering Antique Lock*: two clicks at 12 and 172 ms, a settle at 236, quiet by 278. Allocation has one action, and this is two clicks and done. |
| `duty_actions/clerical_actionB_sfx_v01.ogg` | Pixabay, `freesound_community` | **Silversmith.** *bing1*, a struck bell, 758 ms. Unedited but for the container — and the master is already mono, so it is *not* summed. |
| `duty_actions/clerical_actionA_sfx_v01.ogg` | Federico Soler Fernandez, *Complex Cinematic Mystery Sounds* (GDC **2023**) | **Devotion.** The last 1.6 s of a 47 s cue, dying away. −16.4 dB, the quietest of the duty actions. |
| `duty_actions/taxation_actionA_sfx_v01.ogg` | Bluezone, *Steampunk Mechanical Sounds* (GDC **2023**) | **Taxation.** *mechanism_metal_008*, 1700 ms, as is. A mechanism turning twice, with a 140 ms pause between. Single-action duty, so no tile-mate. |
| `duty_actions/produce_actionA_sfx_v01.ogg` | Bluezone, *Forest Textures* (GDC **2023**) | **Produce Wheat.** *foliage_impact_short_012*, 1291 ms, as is. An impact and *then* a rustle — a stroke and stalks falling. A wide stereo source: channels correlate +0.53. |
| `duty_actions/produce_actionB_sfx_v02.ogg` | Bluezone, *Annihilation — Mech* (GDC **2023**) | **Produce Stone.** *annihilation_debris_falling_rock_001*, 1800 ms, as is. A cascade rather than one impact. 1800 ms, with 20.9% of its energy below 250 Hz. |
| `misc/rock_dropping_sfx_v01.ogg` | Sonic Bat, *Videogame Foley Essentials Vol. II* (GDC **2024**) | *Was Produce Stone, now unassigned.* *Medium Rock Dropping 011*, 599 ms. Impact at 4 ms. Moved, not re-cut. |
| `misc/shears_sfx_v01.ogg` | ElevenLabs, `scissor_1.mp3` | *Was the first Ordain cue, now unassigned.* Five events, two strong snips 526 ms apart. The one file here nothing can re-fetch. |
| `misc/mechanism_one_cycle_sfx_v01.ogg` | Bluezone, *Steampunk Mechanical Sounds* (GDC **2023**) | *Never held a slot.* The first 960 ms of Taxation's source — one cycle, cut inside its own pause. Kept beside the two-cycle version that ships. |
| `misc/many_coins_sfx_v01.ogg` | CB Sound Design, *Essential Sounds Vol.01 Coins* (GDC **2023**) | *Never held a slot.* 497 ms of coins, as is. Dual mono stored as stereo — the channels are identical, so summing is lossless. |
| `misc/wood_groan_long_sfx_v01.ogg` | Pixabay, `voicebosch` | *Never held a slot.* 1230 ms from take 5 of the Pulpit master — a different take, sharing no material with the cue. Lost to Pulpit on shape, not quality: a wash where a cue wants an event. |
| `misc/velcro_rip_sfx_v01.ogg` | InMotionAudio, *Velcro* (GDC **2026**) | *Was the Wheat cue.* *VelcroRip29*, 417 ms, unedited but for the container. A rip of hooks and loops stood in for a handful of grain until a recording of an actual footfall in grass was available; it moved here byte-identical rather than being deleted. |
| `misc/shrine_bell_sfx_v01.ogg` | Pixabay, `konpeito_sound` | *Never held a slot.* A suzu — the bell cluster on a rope — 1180 ms from 0.420–1.600 s. Cut for Build Shrine and not taken for it; the slot stays open. |
| `duty_actions/construct_actionA_sfx_v01.ogg` | 344 Audio, *Nuts And Bolts* (GDC **2023**) | **Construct Building.** Two hammer blows on a chisel at 20 and 376 ms, cut from a 21.9 s take of 56 strikes. Mono master, not summed. |
| `duty_actions/construct_actionB_sfx_v01.ogg` | Pixabay, `freesound_community` | **Construct Road.** *brick-dropped-on-other-bricks*, 224 ms cut from 3480. Touch, drop, bounce. Left channel only — the right one is dead. |
| `tithe/wheat_sfx_v02.ogg` | RYK-Sounds, *Footstep* (GDC **2023**) | **Wheat.** *grass 3 single step 3*, one footfall in grass, 816 ms, unedited but for the container. It replaced a velcro rip, which is now in `misc/`. Near-dual-mono: the channels differ by 0.32 dB at the peak, so summing costs 0.16. |
| `tithe/silver_sfx_v02.ogg` | Pixabay, `freesound_community` | **Silver.** *coins-falling-013*, head trimmed to 425 ms so it speaks at once. |
| `tithe/stone_sfx_v01.ogg` | Bluezone, *Stone Impact* (GDC **2024**) | **Stone.** The first 560 ms of *stone_impact_041* — the impact and the stones that follow it. No fade-in; the master starts at exactly zero. |
| `buildings/library_sfx_v01.ogg` | 344 Audio, *Antiques — Books* | **Library.** One second of *Pile Of Antique Books Falling Over 8* from 0.806 s. |
| `buildings/brewery_sfx_v01.ogg` | Eiravaein Works, *Flask* (GDC **2024**) | **Brewery.** A glass bottle uncorked — squeak, pop, slosh, settle. 70–920 ms of the master, head and tail trimmed, nothing else. |
| `buildings/bank_sfx_v01.ogg` | Pixabay, `universfield` | **Bank.** *coin-drop*, 1296 ms, as is. Stereo master, correctly summed. The set's second coin sound; see below. |
| `buildings/scriptorium_sfx_v01.ogg` | Pixabay, `freesound_community` | **Scriptorium.** A signature being written — 757 ms taken from 360–1120 ms of a 3.74 s take, holding four of its eight strokes. −11.7 dB. |
| `buildings/inquisition_sfx_v01.ogg` | David Dumais Audio, *Melee Weapons Pack 1* (GDC **2023**) | **Inquisition.** A blade sheathed, 914 ms, as is. The widest stereo source here — channels correlate +0.41 — and the only master carrying an embedded PNG. |
| `buildings/grain_store_sfx_v01.ogg` | Eneas Mentzel, *Debris & Rubble* (GDC **2023**) | **Grain Store.** Dry branches rummaged, 845 ms from 225–1070 ms. Started late on purpose: the source ramps in. |
| `buildings/well_sfx_v01.ogg` | Pixabay, `tanweraman` | **Well.** A stone dropped in water, 1104 ms, as is. Strikes at 300 ms, swallowed at 700. |
| `buildings/quarry_sfx_v01.ogg` | Justsoundeffects, *Stones and Debris* (GDC **2023**) | **Quarry.** Loose stone settling, 1315 ms from 11.365–12.680 s — the tail of take 1 of five. Eight stones, no dominant impact, and no fade: it ends inside the library's own silence. |
| `buildings/chapel_sfx_v01.ogg` | Marek Klemczak *(disputed — see record)*, *ARTA Cinematic Sound FX* (GDC **2023**) | **Chapel.** A low swell, 947 ms from 300–1250 ms. The darkest clip in the set and the first non-diegetic one. Trimmed because the master carried both a dead head and a dead tail. |
| `buildings/confession_box_sfx_v01.ogg` | Rogue Waves, *Creaking Door* (GDC **2024**) | **Confession Box.** A wooden door shut, 895 ms from 4.585–5.460 s of an open-and-close take. Two impacts 156 ms apart — frame, then latch. The creak before it was passed over. |
| `buildings/pulpit_sfx_v01.ogg` | Pixabay, `voicebosch` | **Pulpit.** Wood creaking under weight, 707 ms from take 3 of seven. Three creaks at 20, 340 and 720 ms. No fade at either end. |
| `buildings/mint_sfx_v01.ogg` | Pixabay, `sunovia` | **Mint.** A silver chime, 1265 ms from 0.185–1.450 s. **The one clip here with EQ and gain** — a 1.2 kHz high-pass and +22.3 dB, both recorded in its entry. |
| `buildings/mill_sfx_v01.ogg` | Pixabay, `freesound_community` | **Mill.** A cog wheel, 1415 ms from 69.295–70.710 s. Two full turns at 0.645 s. The flattest spectrum here — seven octave bands inside 5.7 dB. |

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
velcro      Bundle 3of5  /InMotionAudio - Velcro
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

**Wide stereo sources cost more to sum, and three arrived in a row**: 1.02 dB for Taxation's
mechanism, 1.04 for Produce Wheat's foliage, 1.52 for Inquisition's blade, against 0.1–0.4 dB for
everything before them. Each was summed anyway — it is the convention for a genuinely stereo
source, and taking one channel of a wide recording changes its character more than a decibel does.
**That was written here as a trend and it was not one.** Well's download then *gained* 0.16 dB and
Quarry's 96 kHz master cost 0.43, behind many_coins' 0.00 and Stone's 0.4. What the figures actually
track is how the individual source was miked, which has no direction to it. Read the number per
file; there is nothing to extrapolate.

**One master carried an embedded PNG**, cover art as a second stream inside the WAV. The encode
has to select the audio stream explicitly or ffmpeg may carry it along; Inquisition's record notes
the check that the shipped file holds one stream and it is Vorbis.

**It has since tried to happen three more times**, and every time the check caught it rather than
the ear. Silversmith's `bing1`, Brewery's flask and Produce Stone's rock are all mono downloads;
run through the downmix they read −6.3, −10.4 and −10.0 dB against true peaks of −0.3, −4.4 and
−4.0. The habit that works is to probe the channels *before* converting — `ffprobe` for the
channel count, and the left/right correlation to confirm a stereo file is safe to sum — rather
than to apply one filter chain to everything and inspect afterwards. The sources here are split
almost evenly between mono and stereo, so neither default is right, and the mono ones give no
sign of the mistake: a 6 dB drop looks like nothing in a waveform.

**The cheap confirmation is the peak.** A clip that was meant to pass through unedited should come
back with the master's peak to within the codec's own tenth of a decibel. Where it does not, either
a downmix or a gain happened that was not intended, and the number says which.

**And the channel count is not enough, which Construct Road proved.** Its master *declares* stereo
and is not one: left peaks at −0.5 dB, right at −73.6, and the two correlate at −0.0004. Summed,
it would have come out at −6.5 dB — the identical 6 dB loss, wearing a disguise that `ffprobe
channels=2` walks straight past. The file wants its **left channel alone**.

So the check that actually works is three numbers, not one: the channel count, then **each
channel's own peak**, then the correlation between them. One channel 70 dB under the other means
take the live one; a correlation near zero on a file that claims stereo means the same. A single
summary figure is not enough — the loss heuristic used here first called this file *safe to sum*,
because a dead channel and a cancelling one look alike from a distance and need opposite handling.

| | channels | what to do |
| --- | --- | --- |
| both channels alive, correlation high | 2 | sum as `(L+R)/2` |
| both alive, correlation near −1 | 2 | do **not** sum; they cancel |
| both alive, correlation moderately negative | 2 | sum anyway if the loss buys definition — see Mill |
| both alive, correlation near **0** | 2 | sum, but it costs **3 dB** — see below |
| one channel dead | 2 (nominally) | take the live channel alone |
| genuinely one channel | 1 | use as is; summing is a 6 dB cut |
| one signal written twice | 2 (nominally) | sum or take one; both are free |

**The uncorrelated case is a third behaviour, not a borderline version of the other two.**
Devotion's master correlates at −0.0081: the channels are independent rather than opposed. Summing
two independent signals at half amplitude each loses exactly 3 dB, which is what was measured, and
it also discards the width that was the point of recording it that way. It is still worth summing
by this set's convention, but a reading near zero should be expected to cost 3 dB rather than
treated as an anomaly.

**A negative correlation is not automatically a veto, and Mill is why that row got a
neighbour.** Its channels correlate at −0.405 and summing costs 1.46 dB, which by the table above
is a reason to take one channel instead. It was summed anyway. What cancels in a partial
negative is the *diffuse* half of the field — here the wind — while a point source near the
centre survives, so the mono sum has a **crest factor of 14.8 dB against the left channel's 12.9
and the right's 9.9**. The cog clacks stand further above the background after summing than in
either channel alone.

The rule the table states is about protecting level, and that is usually the thing at risk. On a
recording where the subject is a point source inside a diffuse field, level is instead what you
spend to buy definition, and the number to look at is the crest factor rather than the peak.
Near −1 the original advice stands: there the two channels *are* the same signal inverted and
summing leaves nothing.

**And the last row is not a stereo file at all.** `misc/many_coins` found this case first:
two bit-identical channels, correlation 1.0000, a sum costing 0.00 dB. Pulpit's master is the
same thing arriving by a different route — a mono source written twice and then MP3'd, so the
channels differ by at most 3 LSB, about −80 dB, which is the decoder rounding rather than a
recording. It gets its own row because it is the one case where the choice does not matter:
sum it or take one channel, and the result is the same either way. The reason to recognise it
is not the decision but the *reading* — a 0.00 dB sum would otherwise look like a measurement
that failed, and an equality check would miss the MP3 variant entirely.

### A bed asks the same three numbers a different question

Everything above is about folding a stereo master down to mono safely, because every clip in this
tree is a point event and mono is where they all end up. **Ambient beds are meant to stay
stereo**, which turns the question around: not *is this safe to sum* but *is there a field here
worth keeping*. The same three numbers answer both, and the correlation reading that settles the
first misleads on the second.

The first bed source examined — a fireplace, 96 kHz stereo, intended for Silversmith — reports
two channels, L peaking at −6.11 dB against R's −5.04, and a broadband correlation of
**+0.9940**. Against the table above that is the first row: both alive, correlation high, sum it.
Read as an answer to the *bed* question it says there is no field here at all, and that is wrong.
Measured per band:

| band | L/R correlation |
| --- | --- |
| 20–200 Hz | +0.9958 |
| 200–800 Hz | +0.9617 |
| 800–3000 Hz | **+0.7456** |
| 3000–8000 Hz | **+0.7218** |
| 8000–20000 Hz | +0.8655 |
| broadband | +0.9940 |

There is real width through the midrange and the broadband figure hides it, because the heavily
correlated bass dominates the sum. Same failure as every other single-number spectrum summary
here — filter the audio and measure what comes out. It was reported in conversation as
*effectively mono* on the strength of that one number before the bands were looked at.

**The shape of the column is the test, not any single number in it.** Correlated in the bass and
decorrelated through the mids and top is what a well-made spaced pair looks like, and it is what
you want: low frequencies carry no directional information, so decorrelating them buys no width
and costs mono compatibility. A source reading near 1.0 in *every* band is mono in a stereo
wrapper and should be summed like any cue. A source reading low in the *bass* has a phase problem
rather than a field.

The table above still governs cues, which stay mono. This governs beds, which do not — and the
tool that measures them has to stop folding channels first, which is
`../docs/sfx_levelling_note.md` §10.

### The levels, which are the thing to protect

| | peak | mean |
| --- | --- | --- |
| `tile.ogg` · `confirm.ogg` | −2.4 · −1.3 dB | |
| Ordain · Allocation · Library | −0.1 · −2.2 · −2.3 dB | |
| Wheat | −4.0 dB | −30.3 dB |
| Silversmith | −0.3 dB | −12.7 dB |
| Silver | −7.9 dB | −31.1 dB |
| Brewery | −4.3 dB | −20.5 dB |
| Stone | −1.4 dB | −21.9 dB |

**The three tithe cues, which are the one group meant to be told apart from each other:**

| | length | peak | centroid |
| --- | --- | --- | --- |
| Wheat — a step in grass | 816 ms | −4.0 dB | 8968 Hz |
| Silver — coins falling | 443 ms | −7.9 dB | 7091 Hz |
| Stone — rubble landing | 559 ms | −1.4 dB | 6226 Hz |

Stone is the darkest, which is the right direction. But Silver sits only 870 Hz above it, so these
two are separated by *texture* — a jingle against a thud — rather than by brightness, and that is
worth knowing before anyone reaches for EQ to tell them apart. Silver is also 6 dB quieter than
the other two at the peak, which is the band-limited 24 kHz source showing, not a gain.

### Set 2, recovered

The board's interface cues come in **sets**, and there are three. Set 1 is the Kenney montage the
board actually plays. Set 2 is `general/set2_select_sfx_v01.ogg` and
`general/set2_confirm_sfx_v01.ogg` — ElevenLabs output, **not in use**, and with **no hover at
all**, which the bench draws as a gap rather than hiding. Set 3 is below.

| | set 1 (in use) | set 2 | set 3 |
| --- | --- | --- | --- |
| hover | 67 ms | — | 71 ms |
| select | 67 ms | 2000 ms | 742 ms |
| confirm | 77 ms | 2000 ms | 1222 ms |

**Twenty-five times the length**, which makes set 2 a different idea of an interface rather than a
longer version of this one. A two-second select on a board where selection resolves nothing until
Confirm is a real proposal, not an oversight, and that is the question the set poses. Set 2's two
cues also sit 5.5 dB apart where set 1's sit 1.1 dB apart, so the two were levelled on different
assumptions and should be judged whole rather than slot by slot.

**They were recovered rather than found.** Neither file carries source metadata beyond an ffmpeg
encoder tag, and the names `select.mp3` and `confirm.mp3` say nothing. They were identified by
hashing the clips embedded in an earlier standalone bench still sitting in the project owner's
downloads: its third and fourth clips hash identically to these two. Their provenance was then
confirmed rather than inferred — the lesson Ordain taught, where a generic name and a missing
source became a wrong licence that stood for weeks.

### Set 3, where the select is the confirm's own tail

`general/set3_hover_sfx_v01.ogg`, `general/set3_select_sfx_v01.ogg` and
`general/set3_confirm_sfx_v01.ogg` are all cut from one Pixabay drum track, **not in use**. It is
the only set besides the one shipping that answers all three slots — set 2 still has no hover.
The hover was added last and only works because it is filtered; see below.

What makes this set different from the other two is that its two cues are not siblings but
**nested**. Both are cut to the same sample at 17.800 s, so the select's 742 ms are the confirm's
*last* 742 ms, identical bar the select's own 8 ms ramp, and the confirm adds 477 ms of run-up in
front. Selecting asks and confirming answers on the same landing.

That is the proposal and it is also the risk. The bench fires a set at hover 0 ms, select 700,
confirm 2300, so a player hears the identical 742 ms twice about a second and a half apart.
Whether that reads as a rhyme or as a repeat is the thing to judge, and it cannot be judged slot
by slot. **Two shorter confirms were cut and rejected** on exactly that axis: one starting a beat
later, and one starting on the off-beat at 17.080, which was only 130 ms longer than the select
and stopped being a separate cue at all.

**The windows were chosen on the beat grid, not by duration.** The kick is regular at 0.310 s —
193 BPM — and every cut starts on a hit. Finding that grid took band-splitting below 180 Hz: a
plain onset detector finds almost nothing on this file, because the mix never drops far enough
between hits for a level jump to register. Both cues also end 580 ms past the track's final beat
and inside its own reverb, so what rings after the landing is the recording rather than a fade.

### The hover is the hardest slot, and the only one with a measurable spec

A hover fires on every pointer move, plays at gain **0.12** against confirm's 0.7, and must stop
before the next one starts. `tile.ogg` has done that job unexamined since the beginning; measured,
it turns out to be a tight specification:

| | length | crest | 20 dB down in | peak below 200 Hz |
| --- | --- | --- | --- | --- |
| `tile.ogg` — in use | 67 ms | 17.1 dB | 16 ms | −47.9 dB |
| set 3 hover | 71 ms | 18.2 dB | 12 ms | −101.2 dB |
| the same window, unfiltered | 60 ms | 10.2 dB | 36 ms | **−6.7 dB** |

**The last column is the one that decides it.** A hover has essentially no low end, and a drum
track is nothing but low end — the raw window carries 41 dB more energy below 200 Hz than
`tile.ogg` does, which is a kick on every pointer move. Crest factor and decay time say the same
thing more gently: 10.2 dB and 36 ms against 17.1 and 16.

**So set 3's hover is the tree's second filtered clip**, and the Mint test is what let it through:
the kick is under 200 Hz, the tick is above 2 kHz, and the band between them is 7 dB down, so
nothing worth keeping shares a band with what was removed. Filtered, it measures *better* than the
cue in use on both transient figures.

**The window was found by search rather than by ear.** All fifteen beat and off-beat positions on
the track's 0.310 s grid were cut to 60 ms, high-passed and scored; 15.040 won outright. The
runner-up was 17.065, which is exactly where the select opens, and was passed over to keep the
hover from sharing material with the rest of the set. **There is no unfiltered answer anywhere in
that file** — it runs full mix from sample 0 to its last beat, with no intro and no breakdown, so
no window of it is free of kick.

### `misc/`, which is the one folder with no denominator

Every other group here counts against a list the game owns — three tithe resources, fourteen duty
actions, twenty-four buildings — so the bench can say *2 of 3* and a gap means work still to do.
`misc/` has no such list. A clip is in it because somebody kept it, and the only way to know what
is there is to look, so the bench discovers the folder's contents rather than being told them and
prints a count instead of a coverage bar.

**The board plays nothing from `misc/`.** It is for sound that was worth keeping without a
slot: superseded by something better, found before there was anywhere to put it, or — with
`mechanism_one_cycle_sfx_v01.ogg` — a second reading of a source that ships in another shape.
That last kind never held a slot at all. It is there so a shape decision stays reversible by
listening rather than by re-fetching and re-cutting, which is the cheapest form of keeping an
option open.

A clip arrives here by being **moved, not re-cut.** `rock_dropping_sfx_v01.ogg` is byte-identical
to the file that was `duty_actions/produce_actionB_sfx_v01.ogg`, and its record carries the same
`sha256` it always had — which is how the move was checked, and why the record was rekeyed rather
than rewritten.

**The version number does not restart when a slot empties.** Produce Stone's new cue is `v02` even
though `v01` has left the folder, because a version is the slot's history and not a count of the
files currently in it. Reusing `v01` for different bytes would make every earlier reference to it
ambiguous.

### Not every superseded clip is worth keeping, and the test is recoverability

Three clips were sitting in slot folders that the bench had stopped drawing. They were not one
case, and treating them as one would have cost the only copy of something.

`tithe/silver_sfx_v01.ogg` **was deleted.** Its source is a named Pixabay download that anybody
can fetch again, and v02's record states the cut exactly, so the file was a convenience.

`duty_actions/ordination_actionA_sfx_v02.ogg` **was deleted**, after checking rather than
assuming: over their common span v02 and v03 correlate at **r = 1.00000**, and the 450 ms v02 held
beyond v03 peaks at **−62.1 dB**. It was half a second of silence in a file of its own.

`duty_actions/ordination_actionA_sfx_v01.ogg` **was kept**, and moved to `misc/shears_sfx_v01
.ogg`. Three things separate it from the other two. Its source is a loose mp3 with no catalogue
behind it. Its record says NOT REPRODUCIBLE — ElevenLabs output whose prompt was never written
down and whose generation has aged out, which was proved when the same brief returned a completely
different take. And it is not a superseded *cut* at all: against v03 it correlates at **−0.0029**,
a different sound that lost its job rather than an earlier trim of the current one.

**So the question to ask of a dead clip is not "is it still used" but "what exists if this goes".**
A catalogue page, a sibling file that contains it, or nothing at all. Only the third kind is worth
the space, and it is the one a tidying pass is most likely to sweep up — the whole exercise saved
40 KB from a 534 MB repository, which is no reason to spend an irreplaceable file.

Both deleted records are kept at `"state": "absent"` with their `sha256`, so a re-derivation can
be checked against the bytes that were here.

### Levelling: peak was the wrong number, and `gainDb` is the fix

This set was levelled by peak from the beginning, and **peak does not measure loudness**.
Measured properly, **31.9 dB of loudness variation was hiding inside 17.1 dB of peak
variation**, which is why the ear kept disagreeing with the figures in these records.

The clearest case is not one of the obviously quiet clips. `misc/rock_dropping` peaks at
−4.0 dBFS — louder at the peak than Bank, Brewery or Grain Store, nothing in its entry
suggesting a problem — and measures **−32.1 LUFS**, third quietest in the tree, within 2 dB of
Chapel. It is a rock landing and then air: peak sees the impact, the ear integrates the air.
And the Chapel/Silversmith tile, recorded here as 16.1 dB apart by peak, is **26.1 dB apart**
by loudness. The recorded figure understated it by ten decibels.

**The measure is M200**: the loudest 200 ms of K-weighted energy, ITU-R BS.1770-4 weighting,
ungated. Each of those choices changes the answer, and `sfx_lab/sfx_levels.py` carries the
reasoning in full — the weighting coefficients are re-derived at each file's own rate because a
quarter of this tree is 24 or 96 kHz; gating is off because BS.1770's relative gate can discard
a 70 ms cue; and the window is 200 ms rather than the standard's 400 because 400 is a programme
measure that over-penalises short cues by about 3 dB. A clip shorter than the window is
zero-padded deliberately, which applies the ear's own temporal integration rather than working
around it.

**The ceiling is true peak, and finding it found a live bug.**
`duty_actions/ordination_actionA_sfx_v03.ogg` reads −0.1 dBFS and measures **+0.75 dBTP** — it
is over full scale and clips on playback today. Sample-peak measurement could not have found
it. Three other clips have no inter-sample headroom left.

**The target is −24 LUFS because that is where set 1 already sits.** `tile.ogg` measures −24.4
and `confirm.ogg` −22.5, and that is the one interface set the board plays and nobody has
complained about. Normalising to −24 moves those two by 0.4 and 1.5 dB, lands 36 of 38 clips
exactly on target, and drops the spread to 5.2 dB. Of the two that fall short one misses by
0.6 dB; the other is `rock_dropping` again, 5.1 dB short because its crest factor is 28.1 dB.
(5.2 rather than 5.1 because `gainDb` is stored to a tenth of a decibel; the unrounded trims
would give 5.11. The shipped figure is the one the field produces.)
A sparse transient cannot be made to match a sustained sound by gain alone, and the alternatives
— limiting it, or re-cutting it — are decisions rather than arithmetic.

**It is a field, not a re-render.** Writing gain into the audio would destroy the check this
tree leans on hardest, that a shipped clip's peak matches its master's. `gainDb` in
`attribution.json` keeps every byte verifiable, keeps one owner per fact — the file owns the
audio, the record owns the playback level — and is reversible.

**Edit `attribution.json` in place; never round-trip it through a JSON writer.** Three ambient
levels were changed by loading the file, setting three floats and dumping it back. The values
were right and the diff was **8,013 lines**: the writer reformatted all 242 records, and the
change would have been unreviewable. It was caught only by diffing against the copy on the
other machine. The file is a record of what was decided, so a diff has to show the decision and
nothing else — locate the line, replace the value, and check the diff before anything else.
The same applies to adding a record: render the new block, splice it in at a located line, then
re-read the file and assert the record came back exactly as written.

**And it makes the board's own gains mean what they say.** The board applies
`SFX_GAIN = {hover: 0.12, select: 0.5, confirm: 0.7}` at playback, and set 1 works *because*
its two files are near-matched and that gain does the role balance. Set 3 bakes 12.5 dB of
hover-to-confirm imbalance into its files and then gets the role gain on top. Normalising every
file to one loudness and leaving the balance to `SFX_GAIN` removes the double accounting.

**Still to do.** The bench applies `gainDb`; the board does not yet, and today that would change
only `tile.ogg` by +0.4 dB and `confirm.ogg` by −1.5, since those are the only two clips it
plays. Mint keeps its +22.3 dB baked in — the field is measured from the file as it stands, so
nothing double-counts, but re-cutting it ungained and moving that number into `gainDb` would
retire the one gain exception in the tree.

### Mint, the one clip with gain — and the first of two with EQ

Almost every sound here is cut, summed and encoded, nothing more. Mint is high-passed at
1.2 kHz and lifted 22.3 dB, and both are departures from rules stated at the top of this file.
They are recorded here rather than inside the entry alone because the next person to want an
exception should be able to see what it cost to make this one — and one of them already has:
set 3's hover is filtered too, on the test this section set. **Mint remains the only clip with
gain.**

**The EQ was free, and that is unusual enough to be the reason it was allowed.** The master holds
two layers that do not overlap. A drone lives entirely in 200–600 Hz; it is running at 0.00 s
before the chime begins and still at −61 dB at 2.20 s after the chime has stopped. The chime
lives above 2 kHz and peaks in 9–16 kHz. Between them, 1–2 kHz is empty — 31 dB under the chime.
So a gentle high-pass removes the drone *completely* and costs the chime **1.01 dB**. That is a
separation, not a compromise, and the test for any future filter is the same: if the thing being
removed and the thing being kept share a band, the answer is no.

Two things fell out of it that a trim could not have given. The clip now starts from **true
silence**, so it needs no declick and no fade in. And its tail reaches −80 dB on its own, where
the drone had been holding the floor up at −61.

**The gain was necessary rather than free, and it is the real precedent.** The cut peaks at
−35.28 dB. The board gives every building the same gain, so at that level the file is not quiet,
it is absent — 18 dB below Quarry, which is itself the quietest thing shipping. The options were
to gain it, to give the board a per-clip gain it does not have, or to drop the clip.

**The ungained peak is written into the record, and that is the part that matters.** This tree
proves nothing was touched by checking the shipped peak against the master's. Applying gain
destroys that check unless the number it *should* have matched is written down, so
`modifications` carries −35.28 dB explicitly. A gained clip without that figure would be
unverifiable forever.

**Apply gain before quantising, not after.** The version auditioned was built the wrong way
round — written to 16-bit at −35 dB, then multiplied — and at that level the fade tail fell under
the least significant bit and quantised to literal zeros: 2878 of 2880 samples in one 60 ms
window were exactly 0. Multiplying zero by 13 leaves zero. The shipped file applies the gain in
floating point and is 15.8 dB louder in that tail, and the difference is signal rather than
noise. Neither version is audible down there; the point is that a quiet 16-bit intermediate
silently throws away what you are about to amplify.

**What does not follow from any of this.** Nothing else gets gained because it is a bit quiet.
Scriptorium, Devotion, Chapel, Quarry and Pulpit all sit between −11.7 and −17.2 dB and all keep
their levels, because they can be heard — the argument here was audibility, not preference, and
it only applied because the shortfall was 18 dB rather than 5.

### Fading a tail: length is not the variable that matters

Devotion's first cut used a 150 ms fade and sounded cut off. The diagnosis is measurable: that
fade dropped **57 dB in 150 ms**, where the material decays about **1.7 dB per 100 ms** on its own
— roughly twenty times steeper than the sound.

The obvious fix is a longer fade, and the obvious metric is dB per 100 ms. **Both are wrong.** Any
fade that reaches true silence is infinitely steep in dB at its very end, so every candidate looks
equally bad by that measure, including good ones.

What decides whether a stop is audible is **how loud the clip still is when the collapse happens**:

| | at 300 ms out | 150 ms | 100 ms |
| --- | --- | --- | --- |
| 150 ms fade (sounded cut) | −25.8 dB | −28.4 | −33.7 |
| 900 ms fade (shipped) | −33.1 dB | −40.4 | −45.3 |

Same window, same length, same peak. The fade simply arranges for the unavoidable collapse to
happen 12 dB further down, where nothing hears it. **The rule, then: a fade must put the clip well
under −40 dB before its final 150 ms** — and the length needed to do that depends on how loud the
source still is at the cut point, not on any fixed figure.

**And when every candidate clears the bar, measure how much of the clip is envelope.** Five
windows were cut from the shrine bell and all five ended 30 dB or more below their own peak, so
the rule above separated none of them. What did was the fraction of the clip being shaped: 14%
for the longest, 37% and 40% for the two middle ones, and **73%** for the version faded in over
its opening — nearly three quarters of that clip would have been envelope rather than recording.

The reason the fraction climbs is arithmetic, not taste. The bell decays 1.56 dB per 100 ms on
its own, so the earlier a window stops the further it still has to fall and the more of the
ending the fade has to invent: at 2.1 s the material is 25 dB down and 300 ms finishes it; at
1.3 s it is 11 dB down and needs 650. **Shorter is paid for in envelope**, and past about half
the clip what you are hearing is the fade rather than the instrument.

**There is also a length below which no fade is graceful, and it is set by the material.**
Confession Box's shut is two impacts 156 ms apart with a rattle behind them, and the first
window cut for it ran 475 ms and ended at −12.9 dB — the Devotion fault again. Lengthening it
to 665 ms reached −45.4, but only by steepening the curve, because the rattle is still at
−10 dB where that fade has to start. The window that works runs to 5.46 s, where the settle
has fallen to −25 dB on its own and an ordinary fade lands it.

So the question to ask of a short window is not "is the attack intact" but **"what is the
level at the moment I have to stop"** — and that is a property of the recording, not of the
edit. Below about 665 ms this clip had no graceful ending available at any fade setting:
cutting at 5.06 s meant fading through the latch itself. A clip can be too short for its own
material, and no amount of curve-shaping fixes it.

**The −40 dB in that rule is absolute, and this clip showed that it should not be.** Mint's
ungained cut peaks at −35.28 dB, so the *entire clip* is already within 5 dB of −40 and the rule
is satisfied by doing nothing whatever. The figure only ever worked because every clip before it
peaked somewhere near 0.

Measured properly — how far a clip has fallen **below its own peak** when it stops — the shipped
set is not uniform either:

| | ends below its own peak | |
| --- | --- | --- |
| `tile`, `confirm`, Allocation, Stone | 0.0–0.3 dB | short cues: the whole clip *is* the last 150 ms |
| Scriptorium, Construct Road, Grain Store | 7–11 dB | cut inside a continuing texture |
| Chapel, Pulpit, Mint, Ordain v03, Taxation | 30–34 dB | events with a faded tail |
| Confession Box, Produce Wheat, Construct Building | 44–48 dB | faded well into the decay |
| Quarry, Produce Stone, Inquisition, Bank | 59–71 dB | ran down into real silence |

So there is no single threshold to state, and the honest reading is narrower than the old rule
pretended: **a clip with a tail should end 30 dB or more under its own peak, and a clip without
one is exempt because the question does not arise.** The absolute figure stays usable as a quick
check for anything peaking above about −10 dB, which is most of the tree, and is meaningless
below that.

**The best fade is often no fade, and the silences in a library file say where to find one.**
Quarry's master is 63 s and reads as one long recording. It is not: it is **five separate takes**
divided by true digital silence, which an envelope at 250 ms shows instantly as five runs of
−240 dB. That changes the job from "find a window" to "find a window per take", and it hands over
something better than any fade — a take's tail decays into the silence the engineer left after it,
so a window ending just inside that silence stops because *the recording* stopped. Three of the
five candidates cut this way needed no fade at all and measure −60 dB or lower across their final
150 ms without anything being shaped.

So the first pass on any long source is an envelope looking for the gaps, before any listening.
Takes are nearly always separated by digital silence rather than by room tone, which makes them
free to find, and a boundary found this way is worth more than a good fade: there is no shaped
decay to be judged, because there is no shaping. **The counter-case is in the same batch** — the
cathedral ambience never fell below its own room tone anywhere, so every window of it had to be
faded. Continuous recordings have no seams; library takes usually do.

### The second duty with both actions voiced

`produce` now has sound on both actions too, and the pair separates on a different axis from
construct's.

| | length | centroid | <250 Hz |
| --- | --- | --- | --- |
| Produce Wheat — foliage | 1291 ms | 5361 Hz | 2.2% |
| Produce Stone — debris | 1800 ms | 3674 Hz | 21.3% |

**Weight does the work here, not duration.** Construct's two cues are 3:1 apart in length;
these are 1.4:1, which on its own would not be enough. What separates them is that the stone
carries ten times the low end — one lands, the other scatters. Worth noting because the obvious
check when filling a duty's second slot is "are they different lengths", and here that check
would have passed the pair on a margin too thin to rely on.

### The first duty with both actions voiced

Construct has sound on `actionA` and `actionB`, and they play from the same tile — the first pair
in the set that a player will hear against each other rather than minutes apart.

| | length | centroid | 85% rolloff |
| --- | --- | --- | --- |
| Construct Building — chisel | 690 ms | 2144 Hz | 3658 Hz |
| Construct Road — brick | 224 ms | 3373 Hz | 5777 Hz |

An octave apart in brightness and 3:1 in length, which is comfortably enough. **This is the
comparison worth running whenever a duty's second action gets a sound**: the set's other pairs are
still half empty, so nothing has had to be told apart at this distance before, and a collision
here would be far more noticeable than one between two different duties.

### How close two sounds are is a ratio, not a difference — and I had it wrong

Several records here name a clip's "nearest neighbour" by the gap in spectral centroid, measured in
hertz. **That ranking is unreliable and the ones written before Grain Store should be read with
that in mind.** Pitch distance is relative: 300 Hz between two cues at 2.7 and 3.0 kHz is nearly
two semitones and plainly audible, while 300 Hz between two at 8.9 and 9.2 kHz is half a semitone
and very nearly nothing. Ranking by hertz systematically overstates how close low pairs are and
understates high ones.

Ranked properly, by semitones between centroids, the tightest pairs in the set are not the ones
that got flagged:

| | apart | |
| --- | --- | --- |
| Inquisition · Ordain v03 | 0.2 st | 109 Hz |
| Taxation · Stone | 0.3 st | 100 Hz |
| Grain Store · Ordain v03 | 0.3 st | 162 Hz |
| Construct Building · `confirm` | 0.4 st | 50 Hz |
| Allocation · Construct Road | 0.4 st | 83 Hz |

**The fourth row is the one worth acting on.** `confirm` is not a duty cue heard occasionally — it
plays on every confirmation, so a duty action sitting within half a semitone of it is the
adjacency most often heard in practice. Nothing in the one-at-a-time checks would have surfaced
it, because `confirm` was never the neighbour anybody thought to look at.

**And all of this is still a weak proxy.** A centroid is one number describing a whole spectrum:
two sounds can share one and be nothing alike, which is exactly what is claimed for Taxation and
Silversmith. It should prompt a listen, never settle one. What it is good for is pointing at which
*pairs* to listen to, and the list above is a better answer to that than anything written above it.

### Quarry proved the paragraph above, and it is worse than "a weak proxy"

The sentence "two sounds can share a centroid and be nothing alike" was written as a caution. The
Quarry cue is the case where it actually happened, and the gap is not subtle:

| | centroid | 85% rolloff | where the energy actually is |
| --- | --- | --- | --- |
| Quarry — settling rubble | 3733 Hz | 1112 Hz | **62.7% in 500–1000 Hz** |
| Produce Stone — rubble landing | 3674 Hz | 709 Hz | **53.7% in 125–250 Hz**, 16.5% below 125 |

By centroid these are **0.3 semitones apart** — level with all but one of the tightest pairs in
the table above, and between
two stone cues, which is exactly the collision anyone would dread. By where the mass sits they are
**two octaves apart**. Both readings are correct arithmetic; only one describes a sound.

The reason is that a centroid is a *weighted mean*, and a mean does not locate a skewed
distribution. Both clips have a long thin tail pulling the mean away from their peak — Quarry's
tail reaches up, Produce Stone's reaches up further from much lower down — and the two means
happen to land in the same place from opposite directions. Nothing about the sounds is similar.
Quarry puts 6.5% of its energy below 250 Hz and Produce Stone puts 70.2% there.

**The rule this leaves:** a centroid quoted on its own is not a reading. Quote it with the 85%
rolloff, and **where the two disagree by more than roughly a factor of three, discard the
centroid** — on this pair the rolloffs are 1112 against 709, which is 7.8 semitones and agrees
with the ear. Better still, name the octave band holding the most energy, which is the only one of
the three numbers that cannot be dragged somewhere the sound is not. The same test clears Quarry
against the rest of the stone family at a glance: Construct Road puts 61.3% of its energy in
4000–8000 Hz, the Stone tithe spreads 33.5% into 2000–4000.

**This does not retract the semitone correction above it** — ranking by ratio instead of by hertz
is still right, and hertz is still wrong. It narrows what is being ranked. The earlier fix made
the *arithmetic* on centroids honest; this one says the centroid was the wrong input to that
arithmetic whenever a clip's spectrum is lopsided, which for falling stone is always.

**And the band share is not a safe replacement for it either.** Chapel arrived one clip later with
73.3% of its energy below 125 Hz, which read as a clip that would not reproduce on a laptop
speaker at all. It does. Filtering the audio rather than counting FFT bins shows the octave bands
sitting within about 3 dB of each other *at the peak* — the share figures are driven by rms, where
a 37 Hz fundamental dominates everything regardless of how audible it is — and modelling a
second-order speaker rolloff costs the clip 2.3 dB at 200 Hz and 5.1 dB at 400. Thinned, not gone.

So the honest summary of this whole section is narrower than any of the three fixes in it: **every
single-number summary of a spectrum has now misled here at least once.** Centroid in hertz,
centroid in semitones, and energy share by band have each produced a confident wrong answer about
a clip that was sitting right there to be played. They are useful for choosing which *pairs* to
listen to and for nothing else. Where a number is going to decide something, filter the audio and
measure what comes out.

**A fourth way the number misleads, found while replacing the Wheat cue: it does not carry its
own method.** Checking the new clip against this file's published centroids, a first pass put it
at 6556 Hz and Stone at 3700 — a table disagreeing with the one above by 2500 Hz on a file that
had not changed. Neither pass was wrong. The published figures are **magnitude**-weighted with a
Hann window over the whole clip, decoded at 48 kHz; the new pass was **power**-weighted. Squaring
the spectrum pulls the mean toward whatever is loudest, which on Stone's low-heavy distribution
is worth those 2500 Hz and on the grass step is worth 2400 in the other direction.

The method had never been written down anywhere, and was recovered only by running a small grid
of plausible ones until all three published numbers came back exactly — 8878, 7091 and 6226. That
worked because there were three to match; with one clip it would not have been checkable at all.
So: **magnitude spectrum, Hann window over the whole clip, decoded at 48 kHz**, and the same for
the 85% rolloff. Written down because a number nobody can reproduce is worse than no number — it
reads as a measurement and behaves as an opinion, and the next person adding a clip to a group
will compare against it.

### Writing is a texture, which makes shortening it a different problem

Every other clip here is an event with a decay, so making one shorter means cutting a tail and the
thing to protect is the attack. `buildings/scriptorium_sfx_v01.ogg` is not that. A pen on paper has
no transient to anchor on — what identifies it is the **rhythm of strokes**, so the test when
trimming is not "is the attack intact" but "are there enough strokes left to read as writing rather
than as a scrape".

The master holds eight strokes across 3.74 s. The window kept holds four of them: the long 480 ms
opening stroke and then three inside 230 ms at 20 ms spacing, which is unmistakably a pen moving.
Two other windows were cut and rejected, and both failures are instructive — one began
mid-signature so it arrived already underway, and one ended on the master's loudest sweep but was a
single continuous scrape, the most at risk of reading as *something scraping* rather than *someone
writing*.

**At −11.7 dB it was, when filed, the quietest clip here by a wide margin**, against everything
else's −0.2 to −7.9. Three have since gone lower — Quarry −17.2, Devotion and Chapel −16.4 — so
what matters is not the ranking but the reason: no gain was applied, and the master's loudness
simply lives in a final flourish this window excludes. Levelling it by ear is not optional here
the way it can be elsewhere.

### Two coin sounds, and why that turned out to be fine

Silver is coins falling and Bank is a coin dropped, which looked like a collision waiting to
happen. Measured, it is not:

| | centroid | 85% rolloff |
| --- | --- | --- |
| Silver — coins falling | 7091 Hz | 9811 Hz |
| Bank — a coin dropped | 11051 Hz | 16207 Hz |

Nearly 4 kHz apart, and the reason is an accident rather than a choice: Silver's download is
24 kHz and band-limited at 12, while Bank's is 48 kHz with its top octave intact. The same
limitation that makes Silver the dullest thing in the set is what keeps these two apart. Worth
knowing because **replacing Silver with a full-bandwidth source would create the collision this
table says does not exist** — the thing to check then is Bank, not Wheat or Stone.

Silversmith is now the hottest and may want pulling down once there is more of the set to hear
it against. **It was Wheat and Silversmith together until the velcro rip left the slot**: the
rip peaked at −0.2 dB and the grass step that replaced it peaks at −4.0, so a change made for
the sound's sake moved the set's top by nearly four decibels as a side effect. That is the
argument for the table rather than against it — the number is here to be re-read when a clip
changes, not filed once. **That would be a re-render, not a gain in the page**: the
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

### `ambient/`, the first sounds here that are not events

Thirty-one files under eight duty actions, and they are a different kind of thing from
everything above.

**They live one folder per duty action** — `ambient/<duty>_<slot>/`, which is the same string
the action's own cue is named with, so `ambient/taxation_actionA/` sits beside
`duty_actions/taxation_actionA_sfx_v01.ogg`. It was a flat folder until a duty action wanted
four tracks. A flat folder made the *filename* carry which action, by dropping trailing words
off the stem until one matched — `allocation_wind` found Allocation that way — and that holds
up for two tracks and stops at four, because a stem then wants a name saying what it **is**,
and *wheat* and *coins* collide across actions the moment two duties both involve them, which
Produce and Taxation already do. **The folder owns which action, the filename owns which track,
and neither repeats the other.** A folder naming no real duty action is reported rather than
guessed at, where the old prefix match quietly produced a bed belonging to nothing.

*Older filenames still carry their duty's name — `clerical_actionB/silversmith_sfx_v01.ogg`
says it twice — because moving a file is cheap and renaming one costs a record's continuity.
New tracks are named for what they are: `footsteps`, `keys`, `wheat`, `coins`, `barn_creaks`,
`candle`, `room`, `rosary`, `wool_robe`, `rammers`, `far_work`, `ox_breathing`, `wind`,
`oil_lamp_flame`, `horse_snorts`, `staff`, `distant_dogs`, `night_city`, `rat_squeaks`,
`rats_crossing`.* A cue is an
event: it
fires, it is 70 ms to 1.6 s long, and it is over. A bed runs underneath a selected duty action
for as long as the player leaves it selected, so it loops, and almost every rule in this file
had to be asked again for it.

`ambient/clerical_actionB/silversmith_sfx_v01.ogg` is a fire in a metal stove, a 25 s loop cut from 15.50 s of
Coll Anderson's *Gentle Wind* master (Sonniss GDC 2020). `ambient/clerical_actionA/devotion_sfx_v01.ogg` is a
cathedral between responses, a 35 s loop from 81.50 s of Alexander Kopeikin's *St Petersburg*
master (GDC 2016) — taken from the quiet passage rather than the choir, because the master
alternates full choir at −22 to −25 dB with long stretches at −31 to −36 and only the quiet ones
are a setting rather than a performance.

`ambient/give_alms_actionA/alms_sfx_v01.ogg` is light rain, a 25 s loop from 4.50 s of Soundholder's *Rain &
Thunder* master (GDC 2020). **Its filename ends `stereo MS` and that names the mic technique,
not an undecoded file** — a distinction worth making because getting it wrong is not cosmetic.
Read as raw Mid/Side and decoded, its bass comes out at −0.54 correlation: out of phase, and
mono-incompatible. As stored it reads +0.66 below 100 Hz and near zero above, which is a
delivered spaced pair. Broadband statistics cannot separate the two cases at all — the M/S and
L/R decompositions of two independent equal-power channels are the same pair of signals — so
only the per-band reading settles it. It is also the easiest thing here to loop: its best start
scores 0.17 dB of shoulder mismatch, the closest match in the tree.

`ambient/allocation_actionA/footsteps_sfx_v01.ogg` and `keys_sfx_v01.ogg` are a queue of monks
waiting with a key handed over at the front: a **28.5 s** loop in stems — two at first and
three since `wool_robe_sfx_v01.ogg` joined them, described below — and the first bed here that
was not cut from one recording.

**It shipped as one file first and was split afterwards**, which is worth recording because the
split is the only reason the two can be balanced against each other. `allocation_sfx_v02.ogg`
was the pair already mixed; it is deleted and its record kept. The stems carry the same wrap
and the same rotation as the mix they came out of, so summed at the same trim they *are* it —
checked rather than assumed, at r = +0.9970 with a residual 22.2 dB down, which is Vorbis and
not content. **Both are 28.500000 s to the sample**, and that is load-bearing: a wrap chosen
per stem would give each a different loop point, and the key placed to land against a footfall
would arrive somewhere new every lap.

**Splitting also gave each stem a single source**, where the composite needed two —
`footsteps` is Sadiquecat's hallway walk throughout and `keys` is Fenodyrie's jingle
throughout, and the wool that joined them later is Yuval's coat throughout. All three start at
−23.0, which is not a judgement but the identity: the composite was authored by ear at −23.0
and gain is linear, so the stems at −23.0 summed are the bed as it was approved. Moving them
apart is the point.
It was **assembled** from two CC0 freesound.org uploads: single footfalls lifted out of
Sadiquecat's *Walking to dead-end hallway* and recombined into several walkers at different
distances, with three single contacts from Fenodyrie's *keys jingling* as the handoffs.
Allocation is the action where a duty is given to someone, so a queue and a key is the sound of
the thing happening rather than of the building it happens in. The whole method is
`../docs/ambient_composite_guide.md`, which is worth reading before the next duty action that
wants a scene rather than a room.

**It also arrived already looped**, which is new here: every bed before it was made seamless in
this tree, and this one was made seamless in the mix — by the same equal-power overlap baked
into the asset that `../docs/ambient_loop_note.md` argues for, worked out independently and
written down before that note was read. Two routes to one answer on different material.

**It replaced a Belgian cathedral**, `allocation_sfx_v01.ogg`, an 11.5 s loop from 3maze's *INT*
master (GDC 2019). That one is deleted and its record keeps the whole of its reasoning, which is
worth reading for one finding that is not about it: broadband the recording was calm — 4.79 dB
across 5 s blocks — while filtered in 200 ms windows it held thirteen events above 8 dB over
their band's median, peaking at **+24.4 dB**, almost certainly footsteps on stone, and not one
showed in the broadband map. **The detector that found them was built after one got through**, a
first cut rejected by ear for an event at +10.8 dB in 5–10 kHz that a scan at 1 s blocks and a
6 dB bar walked straight past. At 200 ms, 8 dB and six bands it is obvious.

**The version before it looked loopable and was not**, which is why this one exists. That mix
began and ended on exact zeros, so butting the end against the start made no click whatever —
the trap, because the first 0.3 s and last 0.6 s were digital silence and the material thinned
from about 26.4 s, so plain repetition dropped some 2.5 s of near-nothing into the bed every
lap. Scored as five bands across 1.5 s shoulders that butt join was **41.0 dB out**, with 68.5 dB
in the top band. *The absence of a click is not the absence of a seam*, and a file that starts
and ends in silence is the one shape where those two come apart.

**The shipped loop checks out, and not by the usual test.** Three laps measure identically to one
pass; the step across the wrap is 0.0003 in both channels, under the file's own median
sample-to-sample difference; and the 1.5 s window straddling the wrap sits at the **19th
percentile** of the loop's own windows, 2.35 dB under its median where the quietest window
anywhere is 12.7 dB under. The shoulder test that scores every other bed here reads 21.5 dB on
it and **means nothing** — comparing head against tail on a loop whose head has already been
crossfaded with that tail measures the material's variation and not a seam. Score candidates;
verify finished files.

**Sparse events put a constraint on length that the band search cannot see.** The keys sit on a
near-regular grid, about 3.92 s apart, so a loop *cut* from this material has to be a whole
number of those gaps or one key arrives early every lap — and scored the way the band search
scores anything, the best candidate in the earlier mix was a 22.0 s body at 0.87 dB, which is
5.6 key periods and wrong. The shipped file sidesteps it by wrapping the whole mix onto itself,
so its cadence across the wrap is the mix's own 3.92 s for free. What it does have is one
*interior* gap of 4.99 s where the others run 3.90 to 3.96: not a seam, identical every lap, and
reading as one slower handoff. **A rhythm fault at the wrap is a loop artefact; a rhythm fault
inside the body is content.**

### A third stem, and the first file here proved to be what it says it is

`ambient/allocation_actionA/wool_robe_sfx_v01.ogg` is the cloth of the same queue — heavy
habits moving as the monks shift and walk — placed across the same **28.500000 s** from a
single **CC0** freesound upload by **Yuval**, a 145 s mono recording of a heavy wool coat made
on an MKH 60 into a ULN-2 in 2013. The feet were already here; this is what they are wearing.

**It is a pure addition to the approved mix, and that is arithmetic rather than a claim.**
Three identities on the 24-bit masters, each exact to one least significant bit:
`footsteps + keys` **is** v09, `footsteps + keys + wool` **is** the with-wool preview, and
`preview − v09` **is** this stem with a maximum sample difference of **zero**. Nothing in the
bed that was already approved has moved, and the three at −23.0 are the preview at −23.0, bit
for bit. *The earlier two-stem split could only be checked at r = +0.9970 with a residual
22.2 dB down* — because the composite it was checked against had been through Vorbis. With no
codec anywhere in the path the floor is the 24-bit LSB, 1.19 × 10⁻⁷, and all three of these
land on it. The weaker number was the codec, not the split.

**Its material was traced back into the source by measurement, which is new here.** Every
other record in this tree names a source because somebody wrote the name down. This one was
checked: 57 half-second windows of the stem loud enough to probe were cross-correlated against
the whole 145.262 s upload, and **13 matched decisively** — r between 0.33 and 0.90, each at
least three times the next peak anywhere else in the recording — locating the material at
about 24.4, 41.5, 46.0, 63.8–64.5 and 100.8–106.0 s of it. **Consecutive probes map to
consecutive source times at exactly 1:1**, so the material is cut and placed, not stretched.
The other 44 match nothing cleanly, and that is the expected result rather than a doubt:
several placed copies overlap at any instant, so no one window is a scaled copy of one span.
*A named source can now be confirmed and not merely recorded*, on any file whose source is
short enough to search.

**And a second sighting of the freesound filename trap.** The account is **`Yuval`** with a
capital Y; the download is `188208__yuval__fabric-movement-wool.wav`. The candle record found
that freesound flattens the dots out of a username — it also **folds the case**. Same rule from
the other side, and the same conclusion: a freesound filename gives you the id and the slug
reliably and the username only approximately.

**It has almost no width, and that is the one thing worth a second look.** Its side channel
sits **20.4 dB under its mid** and the channels correlate +0.97 *flat across every band*,
+0.977 to +0.982 from 20 Hz to 20 kHz — which is a mono source with a trace of uniform
decorrelation, not a placed field. The footsteps it belongs to run +0.69, +0.88, +0.36, +0.17,
+0.04, +0.01 up those same bands with the side only 3.7 dB under the mid, because they are
several walkers at several distances. **If the robes are the walkers' robes they should share
that spread.** They don't: the feet are across the cloister and the cloth is in the middle of
your head. Nothing to fix in this file — it is the stem as rendered — but it is the first thing
to try in the DAW.

**It has holes, and the footsteps cover them.** 22.4% of the stem is exact digital silence in
13 spans, the longest 1.570 s at 12.30 s. The footsteps stem has **no silence anywhere**, so
the three summed never drop out; alone this one would stutter. Which is the Taxation lesson
again from the other direction — *a stem is judged inside its mix, never on its own* — and the
reason it can be filed with holes in it where a bed could not.

**Adding it did not break the wrap**, which had to be checked because v09's wrap was baked
before this layer existed. The step across a butt join goes to 0.0004 / 0.0011, still under
the preview's own median sample-to-sample difference of 0.0019 / 0.0018; the 1.5 s window
straddling the wrap moves from the **17th percentile to the 16th**; and the dip at the wrap
deepens from 3.2 dB under the median to 4.4. Measurably worse, inaudibly so, and inside the
material's own fluctuation.

`ambient/allocation_actionA/allocation_wind_sfx_v01.ogg` is the first **second layer**: a 17 s howl from
Hzandbits' *Howling Winds — Interior* (GDC 2016), playing under Allocation alongside the room
tone rather than instead of it. One is the building, the other is the weather outside it.

**Seventeen seconds was a chosen number, not a found one.** Two loops only realign when their
lengths do, so layered under what was then an 11.5 s bed this pair repeated every **391 s**. A
23 s layer — exactly twice 11.5 — would have repeated every 23 s and bought nothing for a whole
extra file. Round lengths are the trap: two 25 s beds lock immediately.

**The bed it was chosen against has since been replaced, and the choice survived by luck.**
17 and 28.5 realign after 34 laps of the bed — **969 s**, about sixteen minutes, against the
391 s the old pairing gave. The 23.510 s cut that briefly stood in between would have given
39,967 s. All three are long enough and none of them was chosen for it, which is the point:
replacing one layer silently re-rolls the beat cycle of every layer it plays with, nothing in
the tree computes it, and the next length could as easily be a near multiple of 17. **The number
to re-check when either file moves is this one.**

**A tonal bed joins differently from a broadband one.** This howl holds a resonance at 617 Hz
sitting 12 dB above the local spectral trend, and two copies of a tone crossfaded at arbitrary
relative phase can cancel where rain or fire simply sum. Candidates were scored on a narrow
550–700 Hz band alongside the usual five, and each crossfade was then built and measured rather
than reasoned about: the chosen one costs 0.46 dB in the howl band. Every bed before this was
broadband enough that crossfade phase could be ignored.

**The event detector is not universal, and this file shows where it stops.** It flags 49 of 166
windows above 8 dB — but those are the gusts, which are the material rather than an intruder in
it. It earns its keep on steady material where a footstep is foreign; on gusty material it
measures the subject.

`ambient/give_alms_actionB/donate_building_sfx_v01.ogg` is a wind heard from inside somewhere sheltered, a
**32.5 s** loop from 64.50 s of Coll Anderson's *Sheltered from the Wind 02* (GDC 2020) — the
second bed from the same pack as Silversmith's fire, and the quietest source any of them is cut
from: it peaks at −24.95 dBFS and its 5 s blocks run −45 to −59.

**It makes Give Alms the first duty with a bed on both its actions** — rain over Alms, wind over
Donate Building. That pairing is the point rather than an accident: weather on both halves of
the duty about giving things away. They never sound together, being different actions, but the
player hears one after the other when switching between them, so they are levelled close on
purpose — Alms lands at −53.4 LUFS and this at −52.7. Neither action has a cue filed, so both
are beds with nothing to be set against, and the bench now says so twice rather than hiding it.

**The search's own best answer was wrong, for a new reason.** Scored across six bands over every
start and every length from 28 to 42 s, the best match in the master is a 28.5 s body at 0.25 dB
RMS against this one's 0.30 — and that body **climbs 7.3 dB from its first third to its last**,
so every lap would be a crescendo resetting to quiet at the wrap. This one runs −51.70 to −51.78
across the same comparison, flat to 0.08 dB, while still holding 10.79 dB of gust inside it.
*Fluctuation is the material; a trend is a shape*, and a shape that resets every lap is a loop
marker. The band score reads two 1.5 s windows and knows nothing about the thirty seconds
between them — the same blind spot as Allocation's key cadence, from a different direction.

**A seam figure that looked like a hole and was not.** Measured as the loop note's section 2
measures one — crossfade region against the rest of the file — it reads **−7.54 dB**, which on
the fire would have meant a rebuild. Split in two it is nothing of the kind: the crossfade
**gains 0.72 dB** over the raw head it replaced, and that raw head is 8.09 dB under the body
mean because 64.5–66.0 s is a lull in the wind, the 12th percentile of this body's own 1.5 s
windows. A lull is the best place to wrap, not the worst. On continuous material the two terms
are the same number, which is why the single figure worked on fire and rain; where the material
fluctuates they come apart by 8 dB and the combined reading is unusable.

**Tonal, like the howl.** A resonance at 451 Hz sits 10.3 dB above the local spectral trend,
with a second at 649 Hz at +6.2, so candidates were scored on a narrow 400–700 Hz band alongside
the five and the chosen crossfade was built and measured rather than reasoned about: 0.50 dB in
that band, against the howl's 0.46. Two tonal beds now, both inside half a decibel.

**And a delivered spaced pair, read per band.** Broadband the channels correlate +0.82, which
would pass for near-mono. Per band they run +0.71, +0.84, +0.73, −0.10 and +0.03 from the bottom
up: correlated bass, decorrelated top. That is a spaced pair and not raw M/S, the same reading
that settled Alms — and the reason equal power is the right curve here while the 451 Hz
resonance still needs its own check.

### A candle under the service, and the first source too steady to search

`ambient/clerical_actionA/candle_sfx_v01.ogg` is a double wood-wick candle burning close to the
listener, a **25.5 s** loop from 36.00 s of a 67.6 s **CC0** freesound recording by roisin.gleeson, made
on a Zoom H4n in 2023 — the recorder and the date come out of the file's own `bext` chunk
rather than from anyone's memory. It sits beside Devotion, so the service carries from the back
of the building while something burns near you.

**Its creator was filed wrong for an hour and the filename is why.** freesound names a download
`<id>__<user>__<slug>` with the username **flattened** — every dot removed — so
`680474__roisingleeson__…` was read as *roisingleeson* when the account is **roisin.gleeson**.
Plausible, wrong, and invisible to anything in the file: it would have gone on crediting a
person who does not exist until someone opened the page. The general form is worth keeping: a
freesound filename gives you an id and a slug reliably, and a username only approximately.

**It is the steadiest source any bed here is cut from, and that breaks the rule that has held
for every other one.** Its 2 s blocks span 4.94 dB across the whole recording, and every
candidate body in the search landed between −57.20 and −57.48 dBFS — a range of 0.28 dB. Where
the fire's shoulder search spread 0.70 to 11.06 dB and the sheltered wind's 0.30 to 325, this
spreads 0.37 to 6.12 with the top dozen all under 1 dB. **On material this even, which two
shoulders you join stops being the thing that decides.** That is the first counter-case to
§5 of the loop note, and it is worth having one.

**So the length was chosen for what it plays against instead.** 25.5 s realigns with Devotion's
35 s every 1785 s — half an hour — and with Silversmith's 25 s every 1275 s. Both hold, on
purpose: the duty was named without the action, so the cut had to survive being placed under
the wrong one. **A 35 s body scored 0.45 dB**, better than several kept, and would have locked
to Devotion on every single lap. Matching the length is the one thing not to do.

**Tonal, and for once it cost nothing.** Excesses of 9.4 dB at 9226 Hz and 8.2 dB at 1335 Hz
over the spectral trend, both scored as narrow bands and the crossfade then built and measured:
0.00 dB in the lower band and −0.04 in the upper, against the howl's 0.46 and the sheltered
wind's 0.50.

**The seam decomposes to almost nothing**, which is the other half of the steadiness: the
crossfade gains 0.38 dB over the raw head it replaced and that head is 0.90 dB under the body
mean, so the old single figure (−0.55 dB) is for once honest. That is the condition under which
it always was.

### Beads told under the sermon, and a length match the paragraph above argues against

`ambient/clerical_actionA/rosary_sfx_v01.ogg` is four movements of three or four bead strikes
placed irregularly across **35.000 s**, built for this project from a single ten-second **CC0**
freesound recording by jaset13045 — *"hit the beads from a rosary"* is the uploader's whole
description. It makes Clerical actionA the third folder here to hold more than two tracks,
after Allocation and Taxation: the service
carrying from the back of the building, a candle burning near you, and somebody in the
congregation telling their beads. Like the Taxation stems and the Allocation bed it was placed
with a script ChatGPT wrote, which is on its record as a `design` note with
`generatedContent: "none"` beside it — no audio here is model output, every sample is that one
upload cut up.

**It is 35 s because Devotion is 35 s, and the candle's own entry says not to do that.** Both
are right, and together they are the whole rule rather than two halves of a disagreement. The
candle is a recording of a different room with nothing placed against it, so a shared length
would buy only a lock and drift is free variation — a 35 s candle body scored *better* than the
25.5 s one taken and was refused for exactly this. The rosary was placed **against** the
sermon: the beads fall where they fall relative to it, and a lap that drifts moves them
somewhere nobody put them. **1,680,000 samples in each file**, so from a common start the two
never separate. *Matching lengths is the trap for independent loops and the requirement for
stems of one scene*, and this folder now holds one of each, which is the clearest statement of
it in the tree.

**It is not a seamless loop and does not need to be**, the same shape as Taxation's three
stems. Content runs 4.82 to 32.26 s, so it opens on 4.8 s of digital silence and closes on
2.7 s, and the step across a butt wrap is **exactly 0.000000 in both channels** — a figure that
means nothing whatever here, for the reason the deleted Allocation cathedral taught: silence
joined to silence makes no click and is not the absence of a seam. Alone the track would gap
every lap. It is not meant to play alone, and the sermon underneath fills precisely those
seconds.

**The gap the wrap makes is the one thing to listen for.** The movements begin at 4.80, 13.00,
21.80 and 29.20 s, so the interior intervals run 8.2, 8.8 and 7.4 s and the one across the wrap
is **10.6 s** — the longest, by about a fifth over the longest interior one. Irregular spacing
is what was asked for and 10.6 is inside the spirit of it rather than outside, but it is the
outlier, and if a lap ever sounds like it pauses, that is where to look. **Allocation's keys
are the same arithmetic the other way round** — there the wrap landed on the grid and an
*interior* gap was the odd length — and the rule that came out of them, that a rhythm fault at
the wrap is a loop artefact while one inside the body is content, needs the material to have a
rhythm before it can be applied. This has none on purpose, so the wrap gap is a question for
the ear and not for the arithmetic.

**And it is the file that broke a premise in the levelling note.** That note measures
everything here **ungated**, on the argument that a cue is too short to survive BS.1770's gate
and a bed is *too even to need it* — demonstrated at the time against four beds that agreed
with their gated figures to within 0.02 dB. This one disagrees with its own by **7.1 dB**
(−46.7 ungated, −39.6 gated), because four short events inside 35 s is not an even bed, and
five other tracks here now do the same. The note is corrected rather than the measurement: see
its *Ungated* section, which keeps the choice and drops the reason that stopped being true.

**So the trim was not set from the integrated figure, and the record says why in full.** At
−46.7 it sits 15.9 dB **under** Devotion's −30.8 while its peak sits 6.7 dB **over** — a crest
factor of 34.9 dB against the sermon's 12.3. Levelled to match on integrated it would want
−11.0 and the strikes would peak more than 20 dB above anything the service does. It is at
**−15.0**, landing 3.9 dB under Devotion, on the reading that beads told two pews away are
quieter than the service. A guess at taste, and one slider move from a different one.

**All but mono**: the channels correlate **+0.9993**, which is a single close strike rather
than a stereo field, and means the downmix costs nothing. It sits centred in front of
Devotion's +0.51 cathedral, which is the right way round.

### `taxation_actionA/`, four tracks and the hardest source here

`room_sfx_v01.ogg` is the barn the other three sit inside — a **30.000 s** loop from 49.75 s of
saintstereo's 143 s **CC0** barn interior, and the first Taxation track that is **not** a stem
of the project owner's composite. It is the layer those three were always missing: each of them
opens and closes on digital silence, and this is what belongs in between.

**Thirty seconds exactly, and here that is the requirement rather than the trap.** Everywhere
else in this tree a matching length is the thing to avoid — the wind layer's record argues it at
length — but these four are one scene rather than four loops drifting past each other, so the
bed holds step with the stems.

**It is the hardest source in the tree to loop, and the numbers say so.** Its best shoulder
match anywhere is **2.02 dB** across five bands, against 0.37 for the candle and 0.70 for the
fire. The recording is not room tone: 2 s blocks spanning **40 dB**, 315 of 715 windows more
than 10 dB over their band's median, and **the master is clipped** at eight points — 47.64,
86.78, 93.76, 95.30, 96.10, 99.46, 107.10 and 108.28 s. The cut and its fold run 49.75 to
81.25 s and contain none of them, and the footsteps at either end of the recording are nowhere
near it.

**There is no long neutral stretch in it at all, and the uploader's description says why.**
It is someone climbing to the second floor of their grandmother's barn on a Sony PCM-D50: the
footsteps at both ends are a person on a wooden staircase, and the loud events in between are a
squeaky pulley and a pedal-operated flywheel. A walk through a working space, not a room tone.
*Every measurement said so before the description was read* — which was the wrong order, and a
useful check on the measurements rather than on the description. The calmest region runs
109–124 s and is punctuated; the only span in 143 seconds with no loud event anywhere inside it
is **six seconds long**. That was one of three candidates auditioned side by side over the stems — level-matched
to within 0.03 dB so the comparison was of character rather than loudness — and it was not the
one taken. The cut that was has events in it because every usable cut in this file does.

### The three stems, one CC0 source each

`ambient/taxation_actionA/wheat_sfx_v01.ogg`, `coins_sfx_v01.ogg` and
`barn_creaks_sfx_v01.ogg` are the first duty action with **more than two tracks**, and the
reason this folder is a folder. They are stems of a Taxation ambience the project owner is
building: grain handled, coins counted, and the barn creaking around both.

**One CC0 source each**, unlike the Allocation bed's two: lucasfuchs' *Pouring grain or seeds*
behind the wheat, Breviceps' *Coin sounds* behind the coins, and Snake16547's *Old wood door
creak* behind the creaks. Public domain, nothing owed, all three named on the records anyway.

**Two of the three are not what they are called**, which is the kind of thing worth writing
down before the file outlives the memory. The grain is **a cherry stone pillow** — the
uploader's own description — poured close to the mic, because it sounds more like poured seed
than poured seed does. The barn is **one small wooden door**, creaked at various speeds on a
Zoom H4N. Only the coins are coins.

**Built with ChatGPT**, as the Allocation bed was — it wrote the script that cuts each source
up and places it across the 30 s stem. That is on the records as a `design` note, which
attribution.json defines as a record of method rather than a rights claim, and each of the
three asserts `generatedContent: "none"` alongside it: no audio here is model output, every
sample traces to one of the three freesound uploads. The licence guard requires that assertion
precisely so the note can be written down instead of hidden.

**The sources are much shorter than the stems and that shows in them.** 6.8 s of grain, 20.0 s
of coins and 69.2 s of door, each behind 30 s of stem — so the grain is placed over and over
while the creaks vary across the whole span, which is audible once you know to listen for it.

*These three were filed for several hours under `provenance-pending`*, a key attribution.json's
licence table is explicit is **not a licence** — only a statement that a file is here and
nobody has written down what may be done with it, enforced by a guard that refuses to let one
be inlined into the board and prints the list on every test run. The placeholder did the job it
exists for: it made the gap visible rather than fillable with a plausible value. The key stays
defined, because more stems are expected before their provenance is.

**They are not seamless loops and are not meant to be yet.** Content runs 4.01–24.93 s for
wheat, 2.04–27.84 for coins and 3.00–28.24 for the creaks, inside a 30 s frame — so all three
open and close on exact digital silence and go quiet between laps. That is the composite's
current shape rather than a fault: the background ambience that will fill those seconds is not
placed, and `../docs/ambient_composite_guide.md` section 15 puts the wrap on the **finished
mix**, after all events are placed, not on a stem.

**All three are the same 30.000 s and share a timebase**, so from a common start they stay in
step. Whatever wrap they eventually get has to be *the same wrap on all of them*: cut
separately they would each find a different loop point, and the coin that was placed to land
against the wheat would arrive somewhere new every lap.

**One of the three now has a trim.** Untrimmed they measure −47.4, −36.8 and −44.4 LUFS, so
coins ran about 10 dB above wheat; **coins was set by ear to −17.0** on 2026-10-15, which drops
it to −53.8 and puts it about 6 dB *under* wheat and 2 dB under the barn room it sits in.
Wheat and the creaks are still at unity and are now the loud ones in the group — and since
Build Roads was levelled they are **the only two untrimmed files left in the tree**. That
balance is the point of the per-track sliders and is not something to derive: the numbers here
were heard, not computed.

**It settled a headroom question as a side effect, and the answer was better than the note
feared.** `../docs/sfx_levelling_note.md` has carried a bullet warning that a bed plus a cue
can exceed full scale, and it named `coins` at −8.6 dBTP as the case that had stopped being
hypothetical. Measured rather than estimated, the four Taxation beds summed at their trims
read **−8.57 dBTP** before this change and **−20.02** after; with this action's own cue at its
worst possible alignment, **−4.45** before and **−9.73** after. *Neither was ever over full
scale.* The bullet was multiplying against the **−1 dBTP policy ceiling** — the limit a cue may
not exceed — as though some cue sat there, where the loudest cue in this tree after its own
trim is −3.97 dBTP and Taxation's is −12.90. The ceiling is a rule about what may be filed, not
a description of what is filed, and the note now says so.

### `build_roads_actionA/`, a work gang in eleven tracks — and the first duty here with no cue

`ambient/build_roads_actionA/rammers_sfx_v01.ogg`, `gravel_sfx_v01.ogg`,
`far_work_sfx_v01.ogg` and `worker_footsteps_sfx_v01.ogg` are a road being laid: the surface
compacted, stone going down, boots on it, and the same gang heard across the site. **35.000000 s
each, to the sample**, from two **CC0** freesound uploads — ldezem's tree stump struck with a
wooden mallet and Yuval's walk on river gravel. Three more arrived with the ox cart and are
described below. *More are expected*, so the counts in this file and both audio notes will
move again.

**The four are the whole of the v05 mix, and one number stands between them and it.** On the
24-bit masters, `rammers + far_work + worker_footsteps + gravel × 1.047129` **is**
`build_roads_base_ambient_v05_with_workers.wav`, exact to two least significant bits and
112.2 dB under the mix. So nothing is hidden in that mix that is not in these four — **and the
gravel sits 0.400 dB louder there than this stem is.** Inaudible, and worth writing down
because it is the only thing between four files at one trim and the mix as it was last heard:
to reproduce v05 exactly, gravel goes 0.40 dB above whatever the other three get.

**The mix still falls silent.** With all four playing, 2.344 s of the 35 is exact digital
silence across 12 spans, because not one of these four is continuous — they run 28.7% to 65.0%
silence individually. That is precisely Taxation's shape before the barn room arrived, and the
background layer that fills it is expected but not here.

**One of the four could be confirmed against its source and three could not**, which says
something about the method rather than about the files. `worker_footsteps` matches Yuval's
gravel decisively — r up to **+0.96** at 1:1, each match at least three times the next peak
anywhere else — locating material around 5.65, 50.8 and 51.0 s of it. The other three match
nothing, at any window from **25 ms to 400 ms** or any speed from **0.5× to 2×**. *That is the
expected failure, not a doubt*: cross-correlation only sees material carried through at 1:1
with its waveform intact, and anything pitched, stretched, convolved or resynthesised defeats
it — `far_work` most of all, being low-passed to −46 dB at 4 kHz. **The fallback was worse than
useless and is recorded as such**: an octave-band shape comparison puts the gravel stem 3.3 dB
from the gravel source and 3.5 dB from the mallet source, so it cannot tell the two apart and
is not evidence either way. **Which source is behind which of the three is therefore inferred
from character**, and is the first thing to correct if it is wrong.

**The rammers carry a tempo in their source and not in themselves.** 386227 is tagged 80 bpm
and four bars, and its 12.000 s is exactly sixteen 0.75 s beats — but nothing in the stem sits
on that grid. 56 strikes fall in 14 clusters of three to five, **0.12 s apart inside a
cluster**, six times faster than the beat, with 1.45 to 3.84 s between clusters. So the rhythm
constraint of §9 of the loop note does not apply here and the eventual loop length is not tied
to a whole number of anything.

**The gap across the wrap is 1.320 s and is the shortest interval in the file** — every
interior pause is at least 1.450 s, and the mean is 2.16. The rammers come back a tenth of a
second early every lap. Inside the irregularity rather than outside it, and *the exact opposite
of the rosary*, whose wrap gap is the longest interval it has. **Where a wrap gap is the
outlier in either direction, that is the second of the lap to listen to.**

#### The ox cart, in three, and the oldest recording in the tree

`ox_cart_mechanics_sfx_v01.ogg`, `ox_cart_stones_sfx_v01.ogg` and `ox_breathing_sfx_v01.ogg`
are the material arriving: the cart, the stone it carries, and the animal pulling it. Three
more **CC0** sources, one each, and three more 35.000000 s stems. They are filed as three
rather than one so the cart can be balanced against the animal.

**The cart is a Hollywood optical effect from somewhere between the 1930s and the 1960s**,
copied by USC Cinema to full-track tape and digitised by craigsmith without restoration — his
description says as much, and *the file says it too*. Its average spectrum falls off a cliff
between 6 kHz (−42.6 dB under its own peak) and 8 kHz (−65.5), **23 dB in about a third of an
octave**, onto a flat shelf near −68 dB out to 12 kHz which is transfer noise and not
programme. That is what a variable-area optical soundtrack looks like and what no field
recording looks like. **This is the first time a source's stated *history* has been
corroborated here rather than only its identity** — every other check in this tree answers
"is this that file", and this one answers "is that file what it says it is". It also leaves a
caution for whoever sets the trim: raising this track raises 1940s optical hiss with it.

**And the newest recording in the tree is in the same folder.** Oldome's stones were uploaded
on 2026-05-11, five months old when they were used, at 96 kHz and 32-bit float — the
highest-specified source here, every bit of which is thrown away by the 48 kHz, 8 kHz-limited
place it lands in. Ninety years between the two sources of one cart.

**Two of the three confirmed, which makes three of the folder's seven.** `ox_cart_mechanics`
is the cleanest match anywhere in this tree: 14 of 63 windows at 400 ms, r up to **+1.00**, and
consecutive probes landing at a **constant +2.50 s offset** — a span of the cart taken through
at 1:1 rather than cut into fragments. `ox_breathing` matches at r +0.54 to +0.87 across 12
windows, lower because the source is stereo and was probed in mono. `ox_cart_stones` matches
nothing, like `rammers`, `gravel` and `far_work`. *The method works here when the material
allows it*, which is the useful thing to know about the four that fail.

**The whole ox group is band-limited, and so is `far_work`.** All three read about −55 dB at
6 kHz and −80 to −96 at 8 kHz relative to their own peaks, where rammers, gravel and the worker
footsteps carry content well past that. The cart and the distant work are the depth in this
scene and are filtered like it — the optical ceiling on the cart is inherited, but the other
two were cut to match it.

**A cow stands in for the ox**, which the uploader explicitly offers and the licence makes
free, and the two are the same species. **But it is by some way the widest thing in this
tree**: channels correlating **+0.1929** with the side only **1.31 dB** under the mid, where
the next widest is Allocation's footsteps at +0.41 and 3.7 dB and most beds here sit above
+0.8. A single close-mic'd animal spread wider than a queue of monks will sit around the
listener's head rather than at the shaft of a cart. Worth a listen before it is accepted.

**v08 is v05 plus these three, and this time the sum is not exact.** `v05 − the four` is zero
to two least significant bits, so none of the earlier four moved when the ox arrived. But
fitted against v08 the three sit at −0.056, −0.052 and +0.008 dB — near enough unity — and
leave a remainder **20.3 dB under the ox group**, peaking at −36.7 dBFS. *It is not a missing
eighth layer*: where all three are exactly silent it measures −123.8 dB rms, and it decays to
nothing within about **100 ms** of each event (−9.7 dB immediately, −25.4 at 50 ms, −54.2 at
100). Nor is it bus compression — v08 over the fitted sum reads 0.00 dB at every level. It is
a short processing difference, the mix holding a slightly different pass of these same renders.
Audibly the same scene, not the bit-exact identity the four gave, and worth knowing before
anyone treats the filed set as that mix.

**The ox closes some of the holes and not all of them.** The four alone fall silent for
2.344 s of the 35; with the cart, the stone and the animal it is **1.168 s**. The wind below
closed the rest.

#### The wind, which is the floor, and the only track here that is not 35 seconds

`wind_sfx_v01.ogg` is the hill the road is being cut across — a **CC0** ORTF recording by
Sandy-Ogilvie made on top of Holehead Hill in the Campsie Fells with the mics behind a wall
for cover, Line Audio CM4s into a Tascam DR-60DmkII. It stands to this scene as
`allocation_wind` stands to the queue of monks: one track is the place, the rest are what is
happening in it.

**Thirty-one seconds, not thirty-five, and that is the whole point.** Everything else in the
folder is 35.000000 s because they are stems placed against each other. This is weather with
nothing placed against it, so a shared length would buy only a lock. **31 and 35 are coprime**,
so the wind realigns with the scene every **1085 s — eighteen minutes and five seconds**. The
first take of it, `wind_stem_v01_subtle`, *was* 35 s; changing it to 31 is what bought the
drift. The Allocation wind makes the same argument from 17 s against 28.5, which comes out at
969 s. **That number is the one to re-check if either length ever moves.**

**It is the first continuous track in the folder and the floor the scene was missing.** Zero
exact silence, gated and ungated agreeing to 0.02 dB with **all 307 blocks** surviving, where
the other seven run 28.7% to 75.3% silence and disagree with themselves by 1.2 to 6.3 dB. With
the seven alone the mix fell silent for 1.168 s of every 35. With this underneath it does not
fall silent at all.

**Its source was confirmed more completely than any other file here — and the two windows that
failed are the interesting part.** 28 of 30 one-second windows match the upload decisively,
r up to **+0.99**, at **two offsets rather than one**. From about 10 s onward the stem sits at
a constant **+0.748 s** against the source: that is the body. Its first eight seconds sit at
**+31.748 s** — the material that *follows* the body, folded back over the head. That is the
equal-power wrap `../docs/ambient_loop_note.md` §1 argues for, arrived at independently, with
a fold of about **eight seconds** rather than the 1.5 s this tree uses. On slow broadband wind
a long fold is right; on an event track it would smear the events. Windows 8 and 9 match
neither because that is where the crossfade holds the two at comparable weight. **Third time
an outside build has landed on this tree's own loop method.**

**One loop reading needed a second look, and the test was wrong rather than the file.** The
step across a butt join is 0.000295 left and 0.002281 right, and the right channel is
**3.50× the file's own median** sample-to-sample difference — the bar §9 sets, and the first
bed here to fail it. It is not a discontinuity. Against its own neighbours instead of the
whole file the step is **0.94× the largest difference in the 100 samples around it**: the
differences run −0.00164 into the join, −0.00228 across it and −0.00243 out of it, so the
slope is continuous and merely steep. *The whole-file median is dominated by the quiet parts
of a bed whose low end moves slowly and loudly*, so it understates the local slope and cries
wolf. **Compare the step with its neighbouring differences, not with a median over the file.**
The wrap window does sit at the **7th percentile**, the lowest of any bed here — it lands in a
lull — and the shoulder score reads 4.11 dB head against tail, which means nothing on a loop
already baked.

**It keeps its source's width, which nothing else in this folder does.** L/R **+0.3051** with
the side 2.69 dB under the mid, against the source's +0.2684 and 2.35 dB — carried through
almost unchanged, where the ox group was collapsed to +0.99 and near mono. One band moved:
below 100 Hz the source reads **−0.0388**, which is wind striking the two capsules
independently rather than a stereo image, and the stem reads +0.3065, so the low end was
tightened on the way in.

**And the lowest-specified source in the tree sits in the same folder as the highest.** This
one is **16-bit**, 44.1 kHz; Oldome's stones are 96 kHz and 32-bit float. Neither fact shows
in the result. What shows is that one was recorded on a hill in a gale with the mics behind a
wall and the other at home.

**Where it sits in the mix.** `v10` is `v08` plus this file at **×0.881 (−1.1 dB)**, tiled
from 7.2515 s into its own loop, with the preview's own fade at the two ends — which is why
that match is 6.4 dB rather than exact. Its internal loop point falls at 23.7485 s into the
preview and leaves no residue there at all, which is the loop verifying itself inside somebody
else's mix.

#### The oil lamp, in two, and a stereo field made out of a 4 ms delay

`oil_lamp_rattle_sfx_v01.ogg` and `oil_lamp_flame_sfx_v01.ogg` are the lamp that lights the
work: the lantern knocked as the gang moves it, and the wick burning under everything. Two
more **CC0** sources — ImAFoley's small oil lantern rattled by its handle, and Vrymaa's
complete action of lighting a candle.

**They are the cleanest arithmetic in the folder.** `rattle + flame` **is**
`oil_lamp_ambient_v03`, and `v10 + rattle + flame` **is** `v12`, both with a maximum sample
difference of **exactly zero** — not two least significant bits, zero — and both fitted at
×1.000000. Where the ox group left a remainder 20.3 dB down and the gravel sits 0.4 dB louder
in its mix than in its stem, these two at unity simply *are* the preview.

**The flame's source came with instructions.** Vrymaa's description says that removing the
lighter and the extinguishing from his recording leaves a loopable flame — and that is exactly
the part this stem uses, starting **6.000 s** in. *The first source in this tree whose uploader
supplied the method as well as the material.*

**And the probe that confirmed it exposed how the stereo was made.** The mono downmix matches
almost nothing — 1 of 37 windows — while each channel on its own matches cleanly, the left at
a constant **+6.000 s** against the source and the right at **+5.996 s**. Those two offsets
differ by **4 milliseconds**, and cross-correlating the channels peaks at exactly −4.000 ms
with **r = +0.9991**. One mono recording, one copy delayed 4 ms: a Haas widener. It is why the
downmix would not match, and why this is now the widest file in the tree at L/R +0.1822 —
wider than the ox breathing, and synthetic where that one was recorded.

**It is mono-incompatible, and not as a matter of level.** A 4 ms delay summed to mono combs.
Against the left channel alone the mono sum has **notches of 21 dB at 125, 375, 625, 875 and
1125 Hz** — every odd multiple of 125 Hz, which is 1/(2 × 4 ms) exactly — and swings
**22.8 dB peak to trough** between 60 Hz and 4 kHz. Broadband the sum reads only −2.29 dB, *so
a level check alone would never find this.* Anything folding the board to mono, a phone
speaker included, does not get a quieter flame; it gets a different one. The fix is a
decorrelator or a real stereo source, and it is in the DAW rather than here. Alms' record
settled a delivered spaced pair against raw M/S; this is the third case in that family, and
the reading that settles each of them is **per band, not broadband**.

**The flame also tripped the step test and passed the neighbour test**, exactly as the wind
did an hour earlier: 0.000345 left is 5.05× the file's own median sample-to-sample difference
and **0.64× the largest difference among its immediate neighbours**. Two files in one sitting
is what moved §9 of the loop note to say which comparison settles it.

**The rattle is the emptiest track in the tree**, at **90.3% exact silence** against
`ox_cart_stones`' 75.3%, with 3.418 s of content in six half-second events at 4.20, 9.85,
15.40, 21.70, 27.15 and 32.25 s. Its intervals run 5.10 to 6.30 s and the one across the wrap
is **6.95 s** — the longest, as the rosary's is and as the rammers' is not. It also owns the
widest gated-to-ungated gap here, **9.51 dB** with only 39 of 347 blocks surviving, which is
the plainest case yet for measuring beds ungated: the gated figure describes a ninth of a file
that is nine-tenths silence.

#### A horse, and a trend the band search cannot see

`horse_snorts_sfx_v01.ogg` is the second animal in the scene, beside the ox at the cart's
shaft — a **CC0** recording by ohmypro of, in his words, a relaxed horse blowing through his
nose. It closes the folder at eleven tracks. `v14` is `v12` plus this file at unity with a
maximum sample difference of **exactly zero**, the third bit-exact addition in a row.

**Its source was confirmed at three separate offsets.** 11 of 23 windows at 400 ms and 14 of
29 at 250 ms match the upload decisively, r up to **+0.95**, at constant offsets of +1.790,
−7.750 and −5.550 s — three lifts from a 24 s recording, placed at six points.

**And the snorts get closer together across the lap, which is a shape rather than a texture.**
Six events at 4.10, 12.85, 18.00, 23.10, 27.20 and 31.15 s: the intervals between their starts
run **8.75, 5.15, 5.10, 4.10, 3.95 s**, shortening almost monotonically, and then the gap
across the wrap is **7.95 s** and it starts again. Measured as silence rather than onsets the
picture holds — 7.05, 3.43, 4.20, 2.35, 3.15 s between events against 6.30 s across the wrap.
So each lap has a quiet quarter and a busy half, and the reset is audible in principle. **This
is the event-rate form of the trend §10 of the loop note describes for level**: fluctuation is
material, a trend that resets every lap is a loop marker. The band search cannot see it, and
it is a question for the ear rather than a fault in the file.

It is nearly mono from a stereo source, like the lantern rattle and the ox cart — L/R +0.9188,
and folding it down costs 0.16 dB. *The exact opposite of its folder-mate* `oil_lamp_flame`,
which is one mono recording widened with a 4 ms delay and loses 21 dB in notches when it is
summed.

#### All eleven levelled in one pass, and the headroom moves to the cue

Set by ear on 2026-10-16, across the whole folder at once rather than file by file, which is
the only way a scene of eleven can be balanced:

| | | | |
|---|---|---|---|
| `ox_cart_stones` **+6.0** | `oil_lamp_rattle` **+3.0** | `ox_breathing` **+2.0** | `horse_snorts` **+1.0** |
| `ox_cart_mechanics` **−2.0** | `far_work` **−2.5** | `worker_footsteps` **−3.5** | |
| `gravel` **−7.0** | `oil_lamp_flame` **−7.0** | `rammers` **−7.0** | `wind` **−7.0** |

*Two things happened to these numbers afterwards and the table is left as it was set, because
it records the balance that was judged. First `rammers` went from −7.0 to **+4.0** the same
day. Then on 2026-10-16 the whole action was taken to **−4.0** on the bench and folded into
all eleven. So the ten unchanged tracks each read 4 dB under their cell above, and `rammers`
reads **+2.0**. The record is the live number; this table is the reasoning.*

**The two extremes are the two measurements that predicted them.** `ox_cart_stones` was the
quietest file in the tree at −55.15 LUFS and takes the biggest lift here, +6.0, and *still*
lands under every other track in the folder. `rammers` was the loudest untrimmed file in the
tree at −7.93 dBTP and is pulled back furthest. Nothing computed either number —
`sfx_lab/sfx_levels.py` derives a cue's trim and refuses to touch a bed, because a bed target
was tried at −39 LUFS and falsified by the second bed ever filed.

**Eleven tracks that sum have to sit quieter per track than one that plays alone**, so reading
this folder's files against a lone rain bed compares nothing. The quantity that matters is the
action's own sum: at the trims in the table, rendered, the ten locked tracks came to
**−12.96 dBTP** and the drifting wind could add at most **−11.98 dBTP** at any phase. Twelve
decibels in hand, which is a healthy place for a bed group.

**Which moves the headroom question onto the cue that does not exist.** Add the loudest cue in
the tree after its own trim — `construct_actionA` at −3.97 dBTP — peak-aligned with that sum,
and the total is **−1.06 dBTP**: legal, and the tightest margin anywhere here. Add a cue at
the **−1.0 dBTP policy ceiling** instead and it reaches **+1.16 dBTP**, which is over. *The
ceiling that has governed cues since set 1 is not safe for this action.* A Build Roads cue
wants to land near −4 dBTP or quieter, and that is a consequence of the action having eleven
beds rather than one.

**And at the trims the record now carries it is tighter still, which is the open item on this
folder.** After `rammers` +4.0 and the −4.0 fold, the action renders at **−5.22 dBTP** — 6.8 dB
hotter than the figure the paragraph above reasons from. Peak-aligned with that same loudest
cue the worst case is **+1.45 dBTP**, over full scale; against a cue at the −1 ceiling it is
**+3.16**. So the conclusion has not changed but the number has: for the total to stay legal a
Build Roads cue has to land at **−9.29 dBTP** or quieter, against the −4 this paragraph
reasoned to before — or the action wants a few more decibels off it. Nothing clips today,
because no cue is filed for Build Roads at all.

**And it is the first duty action here to have beds and no cue of its own.** The bench says so
on every build. Every other bed in this tree was levelled against the cue it plays under —
that is where −24 LUFS and the whole levelling note come from — so the eleven were balanced
against each other and the group's absolute level is the one judgement here with no reference
behind it. Give Alms has the same gap on both its actions, with one bed each rather than
eleven.

### `ordination_actionB/`, Mission in six — and a loop that closes on arithmetic

Six tracks, and they divide cleanly by how they behave in time. `footsteps` and `staff` are
**metrical**: a gait, and a pole planted on a count. `distant_dogs` is **intermittent**: nine
barks in five groups. `rat_squeaks` and `rats_crossing` are **one event between them**, both
firing in the same second once a lap. `night_city` is **continuous**: crickets, wind and
distant town that never stop. The metrical pair is described first, then the others.

`footsteps_sfx_v01.ogg` and the staff (v01 then v02, below) are a pilgrim setting out: boots on stone at a
walking pace with a staff planted every third step. Two **CC0** sources — Fission9's six
hiking-boot steps and worthahep88's stick into soft dirt — and **36.000000 s** each, the first
length here that is neither 35, 30 nor 28.5. It is not arbitrary: at 100 steps a minute,
36 s is sixty steps of nominal space, and the walk uses 54 of them with two pauses in the rest.
`staff + footsteps` **is** the v02 mix, exact to one least significant bit.

**It is a real loop and not merely a clickless one, which are different things.** Both ends
are exact digital silence, so the butt-join step is 0.000000 in both channels — *and that
figure means nothing*, for the reason the deleted Allocation cathedral taught. On a metrical
walk the seam is the rhythm. The 54 footfalls run a median **0.605 s** apart, which is 99.2
steps a minute against the 100 the filename claims, and **the interval across the wrap is
0.600 s** — five milliseconds off the walking step. The gait continues through the loop point.
Compare `rammers`, whose wrap gap is 0.13 s shorter than its tightest interior pause, and
`horse_snorts`, whose event rate ramps across the body and resets.

**The loop closes because the counts divide, and that is worth having as a method.** The staff
lands on every third step without a single exception — steps 3, 6, 9 … 54, eighteen plants,
seventeen gaps all exactly three — and **54 ÷ 3 = 18 exactly**, so the staff returns to the
same foot at the wrap. The footfalls do the same thing one layer down: the six source steps are
cycled in a strict order and **54 ÷ 6 = 9 exactly**, so the rotation closes too. Two patterns,
both commensurate with the length, and **no crossfade anywhere**. Had there been 53 steps the
staff would have changed feet every lap, and no amount of wrap-window percentile would have
found it — that test reads energy.

**The two pauses are 2.400 and 2.405 s**, five milliseconds apart, after the 18th and 38th
step. They are what stops 36 s of metronome sounding like one. The staff's count carries
straight through them rather than restarting, which is what makes the arithmetic above work.

**Both sources confirmed, and the usual probe failed on both.** Event against event, the
footfalls match their source at **r up to 0.998** and the staff plants at **up to 0.962**,
eight of twelve above 0.70 across four distinct source hits. But the sliding cross-correlation
that confirmed the wind and the ox cart found **nothing** — 0 of 117 windows. It normalises
each candidate position by the source's local energy with a percentile floor, and on a source
that is 3.5 s of six isolated events in silence that floor clamps almost everywhere and
flattens the result. *On a short, sparse source, compare event against event rather than
sliding a window.* The probe's blind spot, not the file's.

**Two things to know before levelling.** The six source steps are heard **nine times each in
the same order**, so the same 3.6 s of material returns ten times a lap — unlikely to read
under a staff and whatever else Mission gets, audible soloed, and the same observation the
Taxation wheat record makes about 6.8 s of grain behind 30 s. And both are **essentially
mono**: the footsteps correlate +0.9994 and the staff read **+1.0000**, dual mono exactly,
the only file in the tree that was. Nothing is lost folding them down, which is the opposite of
`oil_lamp_flame` — but there is also no width at all. *That is now true of the footsteps only.*
The staff was rebuilt on 2026-10-16 from a different source and `staff_sfx_v02.ogg` reads
**+0.8465**, so the tree no longer holds a dual-mono file.

#### The dogs, which are an assembly and not a cut

`distant_dogs_sfx_v01.ogg` is nine barks over 36 s from felix.blume's **CC0** recording of a
Mexican village at night — uploaded 2023, recorded 2009 on a mid-side Schoeps pair. It is the
intermittent layer of Mission: 62.6% of the file is exact digital silence.

**It is five excerpts of one recording, placed, and the audio said so before the covering note
did.** Walking the stem in 100 ms steps against the source at every candidate offset recovers
five runs of about 2.5 s: stem 6.9–9.6 s from source 13.05–15.75 s, 10.7–13.3 from 29.60–32.20,
17.6–20.0 from 75.40–77.80, 24.7–27.3 from 63.70–66.30, and 31.0–33.8 from 112.00–114.80.
**They are not in source order** — 75.4 s is placed before 63.7 s — so the sequence was chosen.

**One event scored 0.301 and it was the probe's fault, not the file's.** Eight of nine barks
matched above r = 0.917; the ninth sits 0.75 s before the end of its excerpt, and the 1.2 s
event window ran off the splice into the silence after it. The boundary walk put that bark
inside the same run as the two either side. *An event probe that crosses a splice reports a
false negative.* That is a second named blind spot for this method, beside the sliding probe's
collapse on short sparse sources recorded above — and the two are opposites: one window too
wide, one source too thin.

**The mid-side claim was checked rather than taken.** The upload's description says the
recording is mid-side "encoded as stereo left-right", which could mean either a decoded pair or
raw M/S in two channels, and the two want different handling. Raw M/S reads a channel
correlation near zero; this file reads **+0.8009**, so it is decoded and nothing needs a
matrix. It carries a **7.14 dB left-over-right imbalance** which the stem reproduces at
7.03 dB — itself a small confirmation of provenance, and *a thing to know before placing it:*
these dogs sit well to the left.

**The wrap needs no crossfade and the reason is not the step.** Both ends are digital silence,
so the butt-join step is 0.000000 — which means nothing on its own, as the deleted Allocation
cathedral taught. What makes it loop is the gap: interior gaps of 0.80, 0.81, 3.14, 6.32, 0.91,
6.51, 6.27 and 0.92 s, and **10.32 s across the wrap**. The loop point lands in the longest
quiet in the file rather than inside a group, which is the opposite fault to `rammers`.

#### A new staff, and a replacement verified by what it no longer matches

`staff_sfx_v02.ogg` replaced `staff_sfx_v01.ogg` on 2026-10-16: the same walk, planted with a
wooden stick instead of driven into soft dirt. The source is deadrobotmusic's **CC0** *Random
Wooden Stick Foley*, 15.1 s at 44.1 kHz.

**The arrangement survived the swap, which is the thing that could have broken.** The eighteen
plants fall at 1.540, 3.368, 5.151 … 35.757 s against v01's 1.542, 3.374, 5.152 … 35.764 —
**every one within 8 ms**. So the whole of the metrical argument holds unchanged: 54 steps, a
plant on every third, 54 ÷ 3 = 18 so the staff returns to the same foot at the wrap, both
pauses still after the 18th and 38th step. The footsteps bed was not touched and did not need
to be.

**The cleanest evidence is negative.** Against worthahep88's stick-into-dirt — the source v01
was built from — **none of the eighteen plants reaches r = 0.33**. Whatever this is, it is not
the old file. A replacement is one of the few claims a correlation can settle outright, because
failing to match is exactly what it should do.

**The positive half is weaker than v01's was, and that is on the record rather than rounded
up.** The eighteen plants are **six distinct recorded sounds** — grouped by correlating each
against the others above r = 0.80 they come to 8, 3, 2, 2, 2 and 1 uses, in a non-repeating
order. **One of those six** matches the source cleanly, at **r = 0.9353** against a hit at
5.838 s, and it is the one used three times. The other five place nowhere above 0.46, all of
them dragged to the same loud source position, which is what a correlator does when it has
nothing. They are most likely pitch or filter variants of hits in the same upload — the
ordinary way to stop eighteen copies sounding alike — but that is an inference. v01 had eight
of twelve plants above r = 0.70 across four distinct source hits; this one is less corroborated
than what it replaced.

**And the tree no longer holds a dual-mono file.** v01 read +1.0000; v02 reads **+0.8465**. It
is also 1.67 dB louder integrated and 0.60 dB hotter at the peak, so it will want a trim sooner
than v01 would have. v01's record is kept at `"state": "absent"` with its sha256, per the
recoverability rule above — its source is re-fetchable and its arrangement lives on in v02, so
the bytes went, but the argument that produced it did not.

#### Two rats, which are one event in two files

`rats_crossing_sfx_v01.ogg` and `rat_squeaks_sfx_v01.ogg` fire in the same second — four
footfalls between 10.3 and 11.8 s and three squeaks between 10.5 and 11.5 — and are otherwise
silent. **They are not independent layers and were never meant to be:** one rat crosses the
road once a lap. The wrap gaps are 34.6 and 35.0 s, so the loop point cannot land on either.
*Both are silent at the same moments*, which matters for levelling: a pair like this can never
give each other a floor, the same way Build Roads' seven stems could not before the wind
arrived.

**The squeaks are the first Pixabay source behind an ambient bed, and the first lossy one.**
SOUND_GARAGE's *Rat Squeaks 4 FX*, **1.411 s of mp3** — the shortest source in the tree by a
long way, and the only conditional licence in it. The Pixabay grant lapses on *standalone*
redistribution, which a squeak inside a 36 s bed inside a game is expressly not. The first
squeak matches the upload at **r = 0.9779** at its 0.110 s position, which settles the source;
the other two reach 0.19 and 0.22, and are most likely two of the upload's other three squeaks
pitched or levelled. At **98.2% exact digital silence** this is the emptiest file in the tree,
and its gated-to-ungated delta of **13.80 dB** is the largest — which, per the levelling note,
is 10·log₁₀(357 ÷ 15) and therefore a block count rather than a statement about the squeaks.

**The crossing is the first bed here whose source the audio could not corroborate**, and it is
filed saying so. The covering note names IENBA's **CC0** *Animal Footsteps* — foley staged to
mimic a weasel, recorded by arts students in Uruguay, and the first mono source behind a bed
here. Event-against-event correlation, the method that placed the dogs at 0.999 and the first
squeak at 0.978, reaches **r = 0.074** on all four footfalls. A pitch or speed change would
destroy waveform correlation, so the source was resampled across fifteen ratios from ×0.5 to
×3.0 and re-probed at each: the best score anywhere in that sweep is **0.18**.

*An envelope comparison looked supportive and is not evidence.* Amplitude envelopes survive
pitch shifting, and the four events score 0.65 to 0.91 against their best-matching IENBA
footfall — but the source has **120 onsets**, so best-of-120 inflates any score, and the same
test against an unrelated wooden-stick file still reaches **0.74**. A method that cannot tell
those two apart cannot identify anything. It joins the octave-band fallback in the Build Roads
section under *tried, and recorded as not evidence*.

So the record carries `"provenanceConfidence": "stated-not-corroborated"`. **The licence
position is unaffected**: CC0 either way, and every alternative on the owner's disk that day
was CC0 or Pixabay. What is at stake is only the accuracy of the record, which is why it says
what it does not know.

**The owner supplied the missing half: sped up *and layered*.** That is the explanation, and it
is also why no amount of probing was going to work. Layering sums several source hits into one
event, so a probe is comparing a mixture against a single hit and the correlation collapses
however well the speed is guessed — the speed sweep was testing the wrong hypothesis, not
getting the wrong answer.

**The control is the real finding here.** Told what to look for, the sweep was run again on the
attacks alone — 80 ms windows, where whichever layer dominates the onset has the best chance of
surviving — across sixty-one speed ratios from ×1.00 to ×4.00. Best anywhere against IENBA:
**r = 0.226**. The identical sweep against deadrobotmusic's wooden stick, a file that is
certainly *not* in this stem, reaches **r = 0.2965** — higher than the true source scores.

*So the honest conclusion is not that the evidence is weak. It is that correlation cannot speak
to this file in either direction*, and the control is what demonstrates it rather than
asserting it. The flag stays because the audio still confirms nothing; what changed is that the
silence is now explained instead of open. **Worth keeping as a method note:** when a probe
fails, run it against something known to be absent before concluding anything. If the control
scores as well as the claim, the only finding is about the instrument.

#### The night town, where a wrong first reading was worth keeping

`night_city_sfx_v01.ogg` is 36 s of Articulated Sounds' *Quiet Streets* from the **Sonniss
GameAudioGDC 2017** bundle — crickets, slight wind, distant activity, and the continuous layer
the other three sit on. At **96 kHz** it is the highest-rate source in the tree, resampled to
48 on the way in, and the rate does not show in the result.

**The head is a fold, and the measurement dated it.** Thirty-six of thirty-six one-second
windows match the source at r = 0.78 to 0.97, at two offsets: thirty-four at **+0.0000 s** and
the first two at **+36.0000 s** — the material *following* the body laid back over its head,
which is the equal-power wrap of the loop note's section 1 arrived at independently. Scoring
each 100 ms window against both offsets puts the join at **2.0 s**: the head reads as the fold
until 1.9 s and as the body from 2.0 on. This tree's convention is 1.5 s and `build_roads/wind`
arrived with about 8 s. Three files, three lengths, and nothing yet says which is right.

**A residual that looked like a hidden layer was a high-pass.** Fitting the source to the body
at ×0.214464 leaves a residual 11.73 dB under the stem — but only **7.93 dB** under it below
100 Hz, 6 dB worse explained in that one band. Two large files had been downloaded in the same
minute as the source and named nowhere, and a city rumble was the obvious suspect. **Neither is
in the file:** probing the residual against both matched 0 of 15 windows each at r = 0.06 to
0.21, and a joint fit improved it by 0.00 dB at a scale of 0.0002. The band table says what is
really happening — the stem sits **8.88 dB below** the fitted source from 20–60 Hz and 1.4 to
2.0 dB *above* it in every band over 100 Hz. There is **less** bottom in the stem than in the
source. That is a high-pass, which is the opposite of an added rumble, and it makes the
residual LF-heavy for the same arithmetic reason. The covering note was right and the first
reading of it was wrong; it is recorded because the wrong reading was the plausible one.

**It is the third file to split the two wrap tests the same way.** The butt-join step is 2.74×
the file's median sample-to-sample difference and 0.40× the largest difference among its own
immediate neighbours — passing on the neighbour test, failing on the median, after
`build_roads/wind` at 3.50× against 0.94× and `oil_lamp_flame` at 5.05× against 0.64×.

#### A delta that turned out to be a block count

The gated-against-ungated difference has been read here as a density measure: a continuous bed
agrees inside 0.2 dB, a sparse stem disagrees by 5 to 10. The two Mission stems that are mostly
silence both read **exactly 7.01 dB** and both survive on **exactly 71 blocks** — different
material, different sources, different sources' sample rates. That is not a coincidence and it
is worth knowing what it is.

On a file whose quiet parts are *true digital silence*, every scrap of energy is inside the
blocks that survive the gate, so the delta collapses to **10·log₁₀(all blocks ÷ surviving
blocks)** and carries nothing beyond the duty cycle. Checked on all four Mission beds the
prediction holds to 0.03 dB: `distant_dogs` 71 of 357, delta +7.008 against +7.014 predicted;
`staff` 71 of 357, +7.007 against +7.014; `footsteps` 231 of 357, +1.861 against +1.891;
`night_city` 357 of 357, −0.004 against 0.000. **The delta is still worth printing — it is the
duty cycle, which is a real thing to know about a bed — but it is not a statement about what is
in the loud parts, and calling it "how dense the material is" overstates it.** Where the quiet
parts are a *floor* rather than silence the arithmetic does not apply and the figure means
something else again; no file here is that case yet.

**Mission has no cue either.** `ordination actionA` is Ordain and has one; `actionB` does not.
**Nineteen beds across four duty actions** now have nothing to be levelled against — eleven on
Build Roads, one on each of Give Alms' two actions, and six here.

### Two levels, and why they are not one number

A bed carries **`gainDb`**, which is its balance against the other beds of its action. An
action carries **`groupDb`** in `attribution.json`'s `ambientGroups` block, which is where that
whole action sits against the other actions. A track is heard at the sum of the two.

**Having only one of them would throw the structure away.** With a single number per track
there would be no action level to revisit, only eleven figures that happened to move together,
and the next adjustment would be eleven slider moves again. Kept apart, balancing *within* an
action and matching actions *to each other* stay separate jobs, which is how they are done.

**Folding one into the other on purpose is a different thing, and it is exact.** A track plays
at 10<sup>(trim + group)/20</sup> — one product of two gains — so adding an action's group
level onto every one of its trims and zeroing the group changes nothing audible, and changes
no ratio *inside* the action either, because the same number goes onto every trim. Both
controls step in 0.5 dB so the sum is a multiple of 0.5 and nothing rounds. The bench has a
**fold** button, and the point of it is to *commit* a round of matching: afterwards the trims
are the whole story, the action faders are back at zero, and the two-stage job starts again
from a new baseline. Verified on the bench against the live audio graph rather than the model
— eleven running layers, every one at exactly the level it was before the fold, and the 13 dB
spread inside the action unchanged.

**It is exact only inside the slider range**, and the range was widened to −60 to +30 to put
that out of reach. A group level can push a trim past either end, and a clamp would move one
track and not its neighbours — precisely what the group fader exists to prevent. With the
action fader spanning −40 to +12, a track would now have to sit under −48 or over +18 before a
fold could run off an end, and the tree's actual trims run −23 to +6. The check stays anyway:
an action whose fold would clamp is **left alone and named** rather than clamped, all-or-
nothing per action, which is the right granularity because the invariant being protected is
internal to an action. *The first range, −40 to +15, would have refused in practice* — not at
the top, where the worry started, but at the floor, since Allocation's four tracks already sit
at −19 to −23 and pushing that action back by −20 asks for −43.
*Folding also makes that action's `summedTruePeakDbtp` stale* — it was rendered at the filed
trims — so re-run `sfx_levels.py --groups --write` once the new trims are committed.

**The group cannot change the balance inside an action, by construction.** On the bench it is
one gain node per action that every track of that action feeds, so it scales all of them by
exactly the same factor. It is deliberately *not* added into each track's own gain, where a
clamp or a rounding could pull one track out of line — which is the one thing a master fader
must never do. Anything that eventually plays these beds has to do the same: per-track gain,
then one bus gain per action.

**`summedTruePeakDbtp` is a rendered measurement, not a sum of peaks.** It is the action's beds
mixed at their trims and measured. Adding the individual peaks instead assumes they all peak at
the same instant, which none of them do: on Build Roads that shortcut reads **+1.86 dBTP**
where the rendered mix reads **−3.05**, and on Taxation it is ten decibels out. The figure
scales exactly with `groupDb`, so the bench shows *summed + group* and that is exact rather
than pessimistic.

| duty action | beds | rendered sum at today's trims |
| --- | --- | --- |
| `build_roads_actionA` | 11 | **−5.22 dBTP** |
| `ordination_actionB` | 4 | −10.23 |
| `allocation_actionA` | 4 | −10.74 |
| `clerical_actionB` | 1 | −11.97 |
| `taxation_actionA` | 4 | −12.02 |
| `clerical_actionA` | 3 | −12.10 |
| `give_alms_actionB` | 1 | −22.83 |
| `give_alms_actionA` | 1 | −24.96 |

**That spread is the whole case for the second level, and it has now been used.** It was
**33 dB** when the eight were only ever balanced inside themselves — `give_alms_actionA` a
single rain bed at −35.96 against eleven tracks of work gang at −3.05, which is not a pair of
numbers anybody chose. One pass of matching actions against each other on the bench, folded
into the trims, brought it to **19.7 dB**, with five of the eight inside 2 dB of each other
between −10.2 and −12.1. Build Roads stays 5 dB hotter than that cluster and Give Alms' two sit
10 dB under it, which is a judgement rather than an accident, and the first time this table has
been able to record one.

*The trims under it are no longer all of one kind.* Some were set against the bed's own
neighbours and some arrived by folding an action level onto a track nobody had considered
individually — Taxation's `wheat` and `barn_creaks` went from 0 to +8 that way, and their
records say so. The level is right; the reasoning behind that particular number is not yet
there, and the next pass over those two is what supplies it.

**It goes stale silently, so it is fingerprinted.** `summedAtTrims` records a hash of the
gainDb values the sum was measured from, and a test refuses the pair when they disagree —
without decoding anything, which is what lets the check live in a suite that does not own
ffmpeg. `python3 ui/board_v2/sfx_lab/sfx_levels.py --groups --write` recomputes both. Moving a
*group* level does not invalidate it; moving a *trim* does.

**A track belongs to its action by folder, and nothing in a record says so.** It used to be by
prefix — `allocation_wind` resolved to Allocation by dropping trailing words until something
matched — and that paragraph is now the folder-per-action section above. What survives the
change is the reason behind it: no record here carries a `duty` field, because the path already
answers the question and `duty_text.json` already owns the list. Every track in a folder
answers to that action's own cue.

**Eleven of these sounds carried no sha256 at all until 2026-10-15**, and the gap was wider
than the sounds: 98 of the tree's 219 entries recorded none, whole families at a time — all 35
wax seals, all 35 of their masters, all 15 token files. Quarry, Chapel, Confession Box, Pulpit,
Mint, Mill, Shrine Bell, Wood Groan and the three set-3 clips were the audio share of it.

They were **not** filled in by running `sha256sum` over the tree, and the reason is a precedent
in the artwork. Ordination's v02 crops once described a 1065 x 522 cut while the files on disk
were 1071 x 536, and they were deliberately left *unhashed* rather than blessed with whatever
the files happened to contain — a hash over something that contradicts its own record reads as
verification and is the opposite of it. So each record was checked against its file first. For
these eleven that meant duration and peak, both of which every one of them states: all eleven
agree, durations within 40 ms and peaks within 1.2 dB. Nothing contradicted anything, in the
sounds or anywhere else.

What the hash now means is narrow and worth being exact about: **it identifies the bytes
committed, from the date it was recorded.** It says nothing about the file's history before
that. For a clip whose record already stated a duration and a peak it confirms an existing
claim; for the 82 entries across the tree that stated nothing checkable it is simply the first
independent fact anyone has about the file.

**A re-cut will never match its recorded sha256, and that is not a fault.** Re-running the cut
for this bed from the same master with the same parameters produced audio that is *bit*-
identical — maximum sample difference exactly zero, same 617677 bytes — inside a file with a
different hash, because ffmpeg randomises the Ogg stream serial number on every encode. The
sha256 on a record identifies the shipped bytes, not the recipe; the recipe is in
`modifications` and reproduces the sound, not the file.

**The loop is made by folding the tail back over the head with an equal-power crossfade**, and
which start time you choose matters far more than anything else about it. Searching the fire's
master for the closest band match between the two shoulders, the best start scores 0.70 dB
across five bands and the worst 11.06, with up to 15.4 dB in a single band — and the worst
one's seam reads only −1.00 dB by level, so a level check calls it fine. Crossfade *length*, by
contrast, moves the seam about a decibel across a 24× range. The reasoning and the measurements
are in `../docs/ambient_loop_note.md`.

**A bed's `gainDb` is set by ear, and that is a finding rather than laziness.** A target was
chosen the way −24 was chosen for the cues — derived from one bed judged against its own cue —
and the second bed falsified it: trimmed to the same measured loudness, the cathedral sits far
forward of the fire. No measure explains it. M200, 3 s short-term maximum, short-term p95 and
p50 all agree with integrated loudness to within 1.0 dB. What separates them is that the
cathedral has voices in it, and every loudness measure scores energy rather than salience. So
`sfx_levels.py` reports a bed's level and refuses to propose one, `--write` skips beds so it
cannot overwrite a judgement with a computation, and the only rule left that is not taste is the
true-peak ceiling.

**Both are 48 kHz, which departs from this tree's keep-the-source-rate convention**, and the
departure is deliberate. Both masters are 96 kHz. The convention exists to preserve the check
that a shipped clip's peak matches its master's — and that check cannot apply to a bed anyway,
because a crossfaded loop's peak comes from a 25 or 35 second window of a much longer recording
and was never going to match. Against a convention with no force here, 48 kHz is what the
browser resamples to on decode, it is what was auditioned and approved, and it saves about 12%
on files that are already five to ten times the size of any cue.

**Whoever wires these into the board needs one thing that is not in the file.** Chrome's
`decodeAudioData` returns 176 to 764 samples past the true end of a Vorbis file — 4 to 17 ms of
padding, 6 dB down on some and near-silent on others. Looped raw, that pads every wrap with a
dropout: rendered offline and measured in 2 ms windows, the hole reads −64.7 dB against a bed
sitting at −33. Setting `loopStart = 0` and `loopEnd` to the clip's true length removes it
entirely, and `loopEnd` is in seconds, which matters because the AudioContext runs at whatever
rate the device reports rather than at 48 kHz.

### The bench

`../sfx_lab/generate_sound_bench.py` builds a page holding every slot the board has — three tithe
resources, fourteen duty actions, twenty-four buildings — with the ones that have no sound shown
as gaps, because a list of what is missing is a plan and a list of what exists is not. It reads
the clips off disk and the lists out of `duty_text.json` and `configs/buildings.json`, so it
cannot disagree with what ships.
