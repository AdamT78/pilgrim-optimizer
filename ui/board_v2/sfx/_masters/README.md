# The WAV masters

**Everything in this folder except this file is gitignored.** The `.ogg` files under
`sfx/ambient/` are committed and are what the game plays; these are the 24-bit stereo masters
they were encoded from, kept exactly as delivered.

## Why they are here

They are the only thing in this project that cannot be regenerated. ChatGPT will not produce the
same bytes twice, and a package that leaves the Downloads folder is gone — on 2026-10-18 three of
Allocation's five package folders were cleaned from Downloads within hours of being measured, and
two of them had been the basis of a review earlier the same day. The ZIPs happened to survive.
Next time they might not.

**The second reason matters more.** `attribution.json` makes claims that only the master can
settle:

- *"the fifteen sum to their reference mix with zero differing 24-bit samples"*
- *"the stem reads 7.1% exact silence and the shipped file 54.0%, because the stem's non-zero
  samples have a median of −134.95 dBFS"*
- *"the five background workers can be re-merged at different levels"*

Without the stems those are unfalsifiable. A provenance record whose evidence has been deleted is
a story.

## What is NOT true of this folder

**Git is not backing this up.** Gitignored means the repository ignores it, not that anything is
protecting it. If this folder and `~/Downloads` sit on the same disk with the same backup
coverage, moving the masters here bought co-location and nothing else. Check that whatever backs
up the repository actually reaches an ignored folder.

**CI cannot see it either**, so any guard written over these files has to skip when they are
absent — the same pattern the ffmpeg-dependent checks already use. Stem checks protect this
machine and nobody else's.

## Layout

One folder per duty action, named for its `sfx/ambient/` folder, holding the package **as
delivered** — stems, reference mix, preview, manifest and verification file together. Do not
flatten or rename them: the value is being able to re-run the package's own reconstruction
check, and that needs the reference mix sitting beside the stems that sum to it.

```
_masters/
  allocation_actionA/
    Allocation_Final_Tracks_v38_14Stems_VERIFIED/      the fourteen in play, 17 files
    Allocation_Final_Tracks_v36_15Stems_VERIFIED/      the superseded fifteen, filed by sound type
    Allocation_16_Individual_Production_Stems_v35.zip  the superseded sixteen, kept as the "before"
  build_roads_actionA/
    Build_Roads_Final_Tracks_v15_11Stems_VERIFIED_R1/  the eleven in play
    Build_Roads_Individual_Stems_superseded_by_v15/    the eleven they replaced, one WAV each
    Build_Roads_Final_Tracks_v14/                      the six-stem merge, kept as the mix's record
  build_roads_actionB/  Build_Shrine_Final_Tracks/        covers all 7
  ordination_actionB/   Mission_Final_Tracks_v14/         covers 5 of its 10
  produce_actionA/
    Produce_Wheat_Final_Tracks_v3_VERIFIED/            the thirteen in play
    Produce_Wheat_Final_Tracks/                        the superseded eight
  produce_actionB/      Produce_Stone_Final_Tracks_v17_VERIFIED/   covers all 17
  taxation_actionA/     Taxation_Final_Tracks/            covers 3 of its 4
```

**A PACKAGE IS NOT NAMED FOR THE ACTION IT SERVES AND THREE OF THEM MISLEAD.** Build Shrine's
package is what `build_roads_actionB` plays; Mission's is what `ordination_actionB` plays; Produce
Wheat's is `produce_actionA`. The folders above are named for the `sfx/ambient/` folder, and the
package keeps its delivered name inside, so the mapping is visible rather than remembered. It was
worked out by matching each package's filenames against the beds' `originalFilename`, not by
reading the names.

Every WAV was hash-compared against its source after copying.

The v35 ZIP is kept because the records describe measurements on files that no longer exist in
the shipped set: the two wind passes before they were found to be one recording at two gains, and
the three stems that were exact dual mono before they were rebuilt. Those claims are checkable
only against it.

**Allocation keeps three generations and Produce Wheat two, which is the exception rather than
a new rule.** A superseded package is kept only while a live record still cites a measurement
taken on it — the 5.20 s key grid and the bit-identical peaks are claims about the v36 stems,
and the eight-stem Produce Wheat merges are what the split was checked against. When no record
points at a package any more it can go.

## Nothing is missing

**All 85 beds in the tree have the file they were encoded from here, as of 2026-10-19.** Every
one of the eleven duty actions is complete. *The number moved the same day it was written*: the
Devotion delivery retired three Clerical beds and filed six, and its package went in beside them
as `clerical_actionA/Devotion_Clerical_v02/` with the three new freesound sources added to
`clerical_actionA/Clerical_Devotion_Bed_Sources/`, hash-verified against the Downloads copies
they were taken from. A count in this file is a claim about the next filing as much as about the
last one. There is no bed in this project whose record cannot
be re-checked against the audio it was written from.

**That is not because anything was recovered. It is because nobody had looked properly.** On
2026-10-18 this file said twenty-one beds were probably gone for good, in the confident tone of
something that had been checked, and listed the actions it had given up on. It had been looking
for **package folders**. Twenty of the twenty-one were sitting loose in `~/Downloads` under their
own filenames, and the twenty-first was a `.aiff` where a `.wav` was expected.

| | | |
|---|---|---|
| believed lost on 2026-10-18 | 21 beds | across six actions |
| found by searching for the filenames instead | **21** | in two passes, the same day and the next |
| actually unrecoverable | **0** | |

*"No package folder exists" is not the same as "the stems are gone".* Build Roads was delivered
as eleven loose files rather than as a package, Clerical and Give Alms were cut here from library
masters that were never in a package at all, and Mission's five were loose stems beside the
package that held its other five. Every one of those cases reads as "missing" to a search that
looks for folders and as "present" to a search that looks for names.

### Each one was checked against its bed before it was kept

A file with the right name is not evidence; a file that reconstructs the bed is. Each candidate
was correlated against the shipped `.ogg` and the offset of the best match recorded:

| bed | r | cut begins at | the record says |
|---|---:|---:|---|
| `ordination_actionB/footsteps` | **+0.9996** | 0.000 s | a stem, not a cut |
| `ordination_actionB/door_close` | **+0.9973** | 7.600–13.600 s of the upload, laid in at 3.000 s | exactly that recipe |
| `give_alms_actionB/donate_building` | +0.9964 | 64.500 s | **64.50 s** |
| `ordination_actionB/bottle_knock` | +0.9963 | 0.000 s | a stem |
| `ordination_actionB/rat_squeaks` | +0.9949 | 0.000 s | a stem |
| `clerical_actionA/rosary` | +0.9942 | 0.000 s | a stem |
| `taxation_actionA/room` | +0.9901 | 49.750 s | **49.75 s** |
| `ordination_actionB/rats_crossing` | +0.9865 | 0.000 s | a stem |
| `clerical_actionB/silversmith` | +0.9809 | 15.500 s | **15.50 s** |
| `clerical_actionA/devotion` | +0.9801 | 81.500 s | **81.50 s** |
| `clerical_actionA/candle` | +0.9769 | 36.000 s | **36.00 s** |
| `give_alms_actionA/alms` | +0.9669 | 4.500 s | **4.50 s** |

**Six records state where in the master their cut begins, and an independent search found all six
to the hundredth of a second.** Those figures were written months apart by somebody reading a
waveform; none of them was consulted while searching. That is the strongest corroboration this
archive has produced, and it runs both ways — the files are the right files, and the records are
honest about what was done to them.

`door_close` is the one worth reading twice. Searching for the *whole* upload inside the bed
reads **r = +0.0028**, which looks like a different recording entirely; its record says to take
7.600 to 13.600 s and lay that in, and the six seconds it names match at **+0.9973**. *A
correlation against the wrong span is not evidence of absence*, and a record detailed enough to
say which span is what turns a failed check into a passed one.

### Two things this folder has already earned

**Build Roads was replaced the same day it was completed**, by
`Build_Roads_Final_Tracks_v15_11Stems_VERIFIED_R1` — the same eleven beds re-placed across the
stereo field, not rebuilt. The eleven loose stems collected that morning became the *superseded*
set within hours, which is the best argument this folder has for itself: they are now the only
evidence behind every pre-rebuild measurement the records cite, and they would have been
unrecoverable if Downloads had been cleaned in between.

The superseded eleven are kept under their own folder name rather than inside a package, because
they never arrived as one. Beside them sits `Build_Roads_Final_Tracks_v14`, the six-stem merge, which is
kept for a different reason: it is the only record of the accepted v14 reference mix, and its
`base_ambient`, `ox_stone_cart` and `oil_lamp` stems are the merges the eleven were split out of.
That split was verified rather than assumed, at r = +0.9967, +0.9935 and +0.9952 with residuals
about 20 dB down. **Its wind is not the tree's wind** — `wind_stem_v02_present` against the
tree's `wind_stem_v03_loopable` correlates at **+0.0056**, so the v14 mix cannot be reproduced
from what the game plays, and is a picture of an earlier scene.

## Hashes

The bed records carry `sha256` of the shipped `.ogg`. They do **not** yet carry a hash of the WAV
stem, which means a file in this folder cannot be shown to be *the* file a record was written
from — a re-download or a near-identical re-render would pass unnoticed. Adding `stemSha256` per
bed is what would turn this archive from a pile of plausible files into evidence.
