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
| `duty_actions/clerical_actionA_sfx_v01.ogg` | Federico Soler Fernandez, *Complex Cinematic Mystery Sounds* (GDC **2023**) | **Devotion.** The last 1.6 s of a 47 s cue, dying away. The quietest clip in the set at −16.4 dB. |
| `duty_actions/taxation_actionA_sfx_v01.ogg` | Bluezone, *Steampunk Mechanical Sounds* (GDC **2023**) | **Taxation.** *mechanism_metal_008*, 1700 ms, as is. A mechanism turning twice, with a 140 ms pause between. Single-action duty, so no tile-mate. |
| `duty_actions/produce_actionA_sfx_v01.ogg` | Bluezone, *Forest Textures* (GDC **2023**) | **Produce Wheat.** *foliage_impact_short_012*, 1291 ms, as is. An impact and *then* a rustle — a stroke and stalks falling. The widest stereo source in the set. |
| `duty_actions/produce_actionB_sfx_v02.ogg` | Bluezone, *Annihilation — Mech* (GDC **2023**) | **Produce Stone.** *annihilation_debris_falling_rock_001*, 1800 ms, as is. A cascade rather than one impact. The longest and heaviest clip in the set. |
| `misc/rock_dropping_sfx_v01.ogg` | Sonic Bat, *Videogame Foley Essentials Vol. II* (GDC **2024**) | *Was Produce Stone, now unassigned.* *Medium Rock Dropping 011*, 599 ms. Impact at 4 ms. Moved, not re-cut. |
| `misc/shears_sfx_v01.ogg` | ElevenLabs, `scissor_1.mp3` | *Was the first Ordain cue, now unassigned.* Five events, two strong snips 526 ms apart. The one file here nothing can re-fetch. |
| `misc/mechanism_one_cycle_sfx_v01.ogg` | Bluezone, *Steampunk Mechanical Sounds* (GDC **2023**) | *Never held a slot.* The first 960 ms of Taxation's source — one cycle, cut inside its own pause. Kept beside the two-cycle version that ships. |
| `misc/many_coins_sfx_v01.ogg` | CB Sound Design, *Essential Sounds Vol.01 Coins* (GDC **2023**) | *Never held a slot.* 497 ms of coins, as is. Dual mono stored as stereo — the channels are identical, so summing is lossless. |
| `duty_actions/construct_actionA_sfx_v01.ogg` | 344 Audio, *Nuts And Bolts* (GDC **2023**) | **Construct Building.** Two hammer blows on a chisel at 20 and 376 ms, cut from a 21.9 s take of 56 strikes. Mono master, not summed. |
| `duty_actions/construct_actionB_sfx_v01.ogg` | Pixabay, `freesound_community` | **Construct Road.** *brick-dropped-on-other-bricks*, 224 ms cut from 3480. Touch, drop, bounce. Left channel only — the right one is dead. |
| `tithe/wheat_sfx_v01.ogg` | InMotionAudio, *Velcro* | **Wheat.** *VelcroRip29*, unedited but for the container. |
| `tithe/silver_sfx_v02.ogg` | Pixabay, `freesound_community` | **Silver.** *coins-falling-013*, head trimmed to 425 ms so it speaks at once. |
| `tithe/stone_sfx_v01.ogg` | Bluezone, *Stone Impact* (GDC **2024**) | **Stone.** The first 560 ms of *stone_impact_041* — the impact and the stones that follow it. No fade-in; the master starts at exactly zero. |
| `buildings/library_sfx_v01.ogg` | 344 Audio, *Antiques — Books* | **Library.** One second of *Pile Of Antique Books Falling Over 8* from 0.806 s. |
| `buildings/brewery_sfx_v01.ogg` | Eiravaein Works, *Flask* (GDC **2024**) | **Brewery.** A glass bottle uncorked — squeak, pop, slosh, settle. 70–920 ms of the master, head and tail trimmed, nothing else. |
| `buildings/bank_sfx_v01.ogg` | Pixabay, `universfield` | **Bank.** *coin-drop*, 1296 ms, as is. Stereo master, correctly summed. The set's second coin sound; see below. |
| `buildings/scriptorium_sfx_v01.ogg` | Pixabay, `freesound_community` | **Scriptorium.** A signature being written — 757 ms taken from 360–1120 ms of a 3.74 s take, holding four of its eight strokes. The quietest clip in the set. |
| `buildings/inquisition_sfx_v01.ogg` | David Dumais Audio, *Melee Weapons Pack 1* (GDC **2023**) | **Inquisition.** A blade sheathed, 914 ms, as is. The widest stereo source in the set, and the only master carrying an embedded PNG. |
| `buildings/grain_store_sfx_v01.ogg` | Eneas Mentzel, *Debris & Rubble* (GDC **2023**) | **Grain Store.** Dry branches rummaged, 845 ms from 225–1070 ms. Started late on purpose: the source ramps in. |
| `buildings/well_sfx_v01.ogg` | Pixabay, `tanweraman` | **Well.** A stone dropped in water, 1104 ms, as is. Strikes at 300 ms, swallowed at 700. |
| `buildings/quarry_sfx_v01.ogg` | Justsoundeffects, *Stones and Debris* (GDC **2023**) | **Quarry.** Loose stone settling, 1315 ms from 11.365–12.680 s — the tail of take 1 of five. Eight stones, no dominant impact, and no fade: it ends inside the library's own silence. |
| `buildings/chapel_sfx_v01.ogg` | Marek Klemczak *(disputed — see record)*, *ARTA Cinematic Sound FX* (GDC **2023**) | **Chapel.** A low swell, 947 ms from 300–1250 ms. The darkest clip in the set and the first non-diegetic one. Trimmed because the master carried both a dead head and a dead tail. |

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
Quarry's 96 kHz master cost 0.43, the second-cheapest sum in the tree. What the figures actually
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
| both alive, correlation near **0** | 2 | sum, but it costs **3 dB** — see below |
| one channel dead | 2 (nominally) | take the live channel alone |
| genuinely one channel | 1 | use as is; summing is a 6 dB cut |

**The uncorrelated case is a third behaviour, not a borderline version of the other two.** Devotion's
master correlates at −0.0081: the channels are independent rather than opposed. Summing two
independent signals at half amplitude each loses exactly 3 dB, which is what was measured, and it
also discards the width that was the point of recording it that way. It is still worth summing by
this set's convention, but a reading near zero should be expected to cost 3 dB rather than treated
as an anomaly.

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

The board's interface cues come in **sets**, and there are two. Set 1 is the Kenney montage the
board actually plays. Set 2 is `general/set2_select_sfx_v01.ogg` and
`general/set2_confirm_sfx_v01.ogg` — ElevenLabs output, **not in use**, and with **no hover at
all**, which the bench draws as a gap rather than hiding.

| | set 1 (in use) | set 2 |
| --- | --- | --- |
| hover | 67 ms | — |
| select | 67 ms | 2000 ms |
| confirm | 77 ms | 2000 ms |

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

### `misc/`, which is the one folder with no denominator

Every other group here counts against a list the game owns — three tithe resources, fourteen duty
actions, twenty-four buildings — so the bench can say *2 of 3* and a gap means work still to do.
`misc/` has no such list. A clip is in it because somebody kept it, and the only way to know what
is there is to look, so the bench discovers the folder's contents rather than being told them and
prints a count instead of a coverage bar.

**The board plays nothing from `misc/`.** It is for sound that was worth keeping without a slot: superseded by something better, found before there was anywhere to put it, or — with
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

By centroid these are **0.3 semitones apart** — tied for the tightest pair in the set, and between
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

**It is also the quietest clip in the set, by a wide margin**, at −11.7 dB against everything
else's −0.2 to −7.9. No gain was applied; the master's loudness simply lives in a final flourish
this window excludes. Levelling it by ear is not optional here the way it can be elsewhere.

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

### The bench

`../sfx_lab/generate_sound_bench.py` builds a page holding every slot the board has — three tithe
resources, fourteen duty actions, twenty-four buildings — with the ones that have no sound shown
as gaps, because a list of what is missing is a plan and a list of what exists is not. It reads
the clips off disk and the lists out of `duty_text.json` and `configs/buildings.json`, so it
cannot disagree with what ships.
