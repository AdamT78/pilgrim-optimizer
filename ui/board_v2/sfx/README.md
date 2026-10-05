# The interface sounds

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
