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
| `misc/shrine_bell_sfx_v01.ogg` | Pixabay, `konpeito_sound` | *Never held a slot.* A suzu — the bell cluster on a rope — 1180 ms from 0.420–1.600 s. Cut for Build Shrine and not taken for it; the slot stays open. |
| `duty_actions/construct_actionA_sfx_v01.ogg` | 344 Audio, *Nuts And Bolts* (GDC **2023**) | **Construct Building.** Two hammer blows on a chisel at 20 and 376 ms, cut from a 21.9 s take of 56 strikes. Mono master, not summed. |
| `duty_actions/construct_actionB_sfx_v01.ogg` | Pixabay, `freesound_community` | **Construct Road.** *brick-dropped-on-other-bricks*, 224 ms cut from 3480. Touch, drop, bounce. Left channel only — the right one is dead. |
| `tithe/wheat_sfx_v01.ogg` | InMotionAudio, *Velcro* | **Wheat.** *VelcroRip29*, unedited but for the container. |
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
| Wheat | −0.2 dB | |
| Silversmith | −0.3 dB | −12.7 dB |
| Silver | −7.9 dB | −31.1 dB |
| Brewery | −4.3 dB | −20.5 dB |
| Stone | −1.4 dB | −21.9 dB |

**The three tithe cues, which are the one group meant to be told apart from each other:**

| | length | peak | centroid |
| --- | --- | --- | --- |
| Wheat — velcro rip | 417 ms | −0.2 dB | 8878 Hz |
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

### `ambient/`, the first sounds here that are not events

Two beds, and they are a different kind of thing from everything above. A cue is an event: it
fires, it is 70 ms to 1.6 s long, and it is over. A bed runs underneath a selected duty action
for as long as the player leaves it selected, so it loops, and almost every rule in this file
had to be asked again for it.

`ambient/silversmith_sfx_v01.ogg` is a fire in a metal stove, a 25 s loop cut from 15.50 s of
Coll Anderson's *Gentle Wind* master (Sonniss GDC 2020). `ambient/devotion_sfx_v01.ogg` is a
cathedral between responses, a 35 s loop from 81.50 s of Alexander Kopeikin's *St Petersburg*
master (GDC 2016) — taken from the quiet passage rather than the choir, because the master
alternates full choir at −22 to −25 dB with long stretches at −31 to −36 and only the quiet ones
are a setting rather than a performance.

`ambient/alms_sfx_v01.ogg` is light rain, a 25 s loop from 4.50 s of Soundholder's *Rain &
Thunder* master (GDC 2020). **Its filename ends `stereo MS` and that names the mic technique,
not an undecoded file** — a distinction worth making because getting it wrong is not cosmetic.
Read as raw Mid/Side and decoded, its bass comes out at −0.54 correlation: out of phase, and
mono-incompatible. As stored it reads +0.66 below 100 Hz and near zero above, which is a
delivered spaced pair. Broadband statistics cannot separate the two cases at all — the M/S and
L/R decompositions of two independent equal-power channels are the same pair of signals — so
only the per-band reading settles it. It is also the easiest thing here to loop: its best start
scores 0.17 dB of shoulder mismatch, the closest match in the tree.

`ambient/allocation_sfx_v01.ogg` is a Belgian cathedral with nobody in it, an **11.5 s** loop
from 40.10 s of 3maze's *INT* master (GDC 2019) — the second cathedral here and deliberately not
the same thing as Devotion's, which is a service heard from the back. It is the shortest bed in
the tree, and that is the master's doing rather than a preference.

**Broadband this recording is calm and filtered it is not.** It holds thirteen events above 8 dB
over their band's median in 200 ms windows, peaking at **+24.4 dB** — almost certainly footsteps
on stone — and not one shows in the broadband map, which spreads only 4.79 dB. The longest
window clear of all of them is **16.4 s**, and that caps any loop cut from this file.

**The detector that found them was built after one got through.** A first cut of 30 s was
rejected by ear for an event reading +10.8 dB at 5–10 kHz. The scan that chose that span used
1 s blocks, a 6 dB bar and five bands and walked straight past it; at 200 ms, 8 dB and six bands
it is obvious. The replacement reads +4.5 dB at worst.

**A short loop is the right trade here and would not be elsewhere.** This is featureless room
tone with nothing to recognise, so repetition costs little — whereas one footstep every lap is a
landmark the player learns. The cathedral with voices went to 35 s for the opposite reason.

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
