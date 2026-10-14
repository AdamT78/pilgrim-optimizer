#!/usr/bin/env python3
"""What every clip's playback gain should be, measured rather than guessed.

    python3 ui/board_v2/sfx_lab/sfx_levels.py                 # report
    python3 ui/board_v2/sfx_lab/sfx_levels.py --write         # write gainDb into attribution.json
    python3 ui/board_v2/sfx_lab/sfx_levels.py --one <path>    # measure one new clip

WHY PEAK WAS THE WRONG NUMBER. This set was levelled by peak for a year and peak does not
predict loudness. misc/rock_dropping peaks at -4.0 dBFS, which looks like a normal clip, and
is the third quietest thing in the tree: it is sparse, so its energy is tiny next to its
peak. Chapel peaks 12 dB below Confession Box and sounds very much more than 12 dB quieter.
Measured properly the set spans 31.9 dB of loudness inside 17.1 dB of peak.

TWO CLASSES, TWO MEASURES, AND THE RECORD SAYS WHICH. A cue is an event and is measured by
M200; an ambient bed is a 25 s loop and is measured by ungated integrated loudness. They fail
in opposite directions, which is why one rule cannot serve both: a cue levelled by its average
disappears, and a bed levelled by its loudest fifth of a second sits too quiet for the other
24 seconds. `kind` in attribution.json picks the measure and the target, and it has to live
there rather than be inferred, because a bare `gainDb` does not say which rule produced it.

CHANNELS ARE SUMMED, NOT FOLDED. BS.1770 weights each channel at G = 1.0 and sums the powers.
Folding to mono first reads low by 3.01 dB on correlated material and 6.02 dB on uncorrelated,
and it is the variation rather than the offset that matters: it would place two beds of equal
true loudness up to 3 dB apart. This was harmless while all 38 clips were mono and stops being
harmless with the first stereo bed.

THE MEASURE FOR A CUE IS M200: the loudest 200 ms of K-weighted energy, ITU-R BS.1770-4
weighting, ungated. Three choices in that sentence, each deliberate.

K-weighting rather than raw RMS, because the ear is not flat; the filter is re-derived from
the analogue prototypes at the file's own rate rather than reusing the published 48 kHz
coefficients, which is what makes a 24 kHz or 96 kHz clip read correctly.

Ungated, because BS.1770's gates exist to ignore silence in programme material minutes long.
On a 70 ms cue the relative gate can discard the cue.

200 ms rather than BS.1770's 400 ms momentary window, because 400 ms is a programme measure
and over-penalises short cues by about 3 dB. 200 ms is roughly the ear's own integration
time, and a clip shorter than the window is ZERO-PADDED ON PURPOSE: that charges it
10*log10(length/200) for being brief, which is not an artefact but the temporal integration
a listener actually applies. A 67 ms tick really is quieter than a 670 ms wash of the same
amplitude, by about that much.

THE CEILING IS TRUE PEAK, NOT SAMPLE PEAK. Inter-sample peaks exceed the sample maxima on
anything with sharp transients, and a DAC reconstructs the signal between samples. Measured
at 4x, ordination_actionA_sfx_v03 sits at +0.75 dBTP today: it reads -0.1 dBFS and clips on
playback. Sample peak would not have found it.

WHY -24 LUFS. It is not a round number chosen for comfort: it is where set 1 already sits.
tile.ogg measures -24.4 and confirm.ogg -22.5, and that is the one set the board actually
plays and nobody has complained about. Normalising to -24 moves those two by 0.4 and 1.5 dB
and leaves 36 of the other 38 clips landing exactly on target, with the spread falling from
31.9 dB to 5.1.

THIS SCRIPT NEEDS ffmpeg AND THE BOARD DOES NOT. ffmpeg is not on the Mac's PATH -- the
same fact that made generate_sound_bench.py read Ogg headers by hand rather than shell out.
That is tolerable here only because this is a measuring tool, not a build step: it runs
wherever a decoder exists, writes `gainDb` into attribution.json, and from then on the board
and the bench read a number. Nothing in the shipping path decodes anything.

THE GAIN IS A FIELD, NOT A RE-RENDER. Writing gain into the files would destroy the check
this tree leans on hardest -- that a shipped clip's peak matches its master's, which has
caught three real filing errors. `gainDb` in attribution.json leaves every byte verifiable,
keeps one owner per fact, and is reversible. It also retires Mint's exception: that file can
be re-cut without its +22.3 dB and carry the number here instead.
"""
import argparse
import json
import math
import pathlib
import subprocess

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[3]
BOARD = ROOT / "ui" / "board_v2"
TARGET_LUFS = -24.0
# THERE IS NO BED TARGET, AND THAT IS A FINDING RATHER THAN AN OMISSION. A target was chosen
# (-39 LUFS) and then falsified by the second bed: trimmed to the same measured loudness, the
# cathedral sits about 5 dB forward of the fire. No measure explains it -- M200, 3 s short-term
# maximum, short-term p95 and p50 all agree with integrated to within 1.0 dB, against the 5 dB
# that was heard. What separates them is that the cathedral has voices in it, and loudness
# measures score energy, not salience. A bed's gainDb is therefore AUTHORED BY EAR, and this
# tool's job for a bed is to record the level and guard the ceiling, not to set the level.
CEILING_DBTP = -1.0
WINDOW_MS = 200.0
KINDS = ("cue", "bed")


def _biquad_coeffs(sr):
    """BS.1770-4's two stages, derived at `sr` from the analogue prototypes.

    The standard publishes its numbers for 48 kHz and reusing them at another rate is the
    quiet way to get this wrong: a quarter of this tree is 24 or 96 kHz.
    """
    f0, g, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / sr)
    vh = 10 ** (g / 20)
    a0 = 1 + k / q + k * k
    shelf = ([(vh + math.sqrt(vh) * k / q + k * k) / a0, 2 * (k * k - vh) / a0,
              (vh - math.sqrt(vh) * k / q + k * k) / a0],
             [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / sr)
    a0 = 1 + k / q + k * k
    rlb = ([1 / a0, -2 / a0, 1 / a0], [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    return shelf, rlb


def k_weight(x, sr):
    """The pre-filter, applied as an exact frequency response so this needs only numpy.

    NO SCIPY ON PURPOSE. generate_sound_bench.py learned the same lesson about ffprobe: a lab
    script that needs a package the machine it runs on has not got is a script that does not
    run. The clips here are seconds long, so filtering in the frequency domain costs nothing
    and is exact -- validated against scipy's lfilter at 0.000000 dB and 1e-12 per sample.
    The transform is zero-padded past twice the length so the circular convolution cannot
    wrap a decay back onto the attack.
    """
    n = len(x)
    size = 1
    while size < 2 * n:
        size *= 2
    spec = np.fft.rfft(x, size)
    w = 2 * math.pi * np.fft.rfftfreq(size)
    z1 = np.exp(-1j * w)
    z2 = z1 * z1
    for b, a in _biquad_coeffs(sr):
        spec = spec * ((b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2))
    return np.fft.irfft(spec, size)[:n]


def load(path):
    """EVERY CHANNEL, float, at the file's OWN rate. Shape is always (n, channels).

    Resampling first would move the peak -- a 96 kHz clip read at 48 can lose 2 dB, which is
    how an earlier audit 'found' four faults in four correct records.

    THIS USED TO FOLD TO MONO and that was safe only for as long as every clip was mono, which
    was true of all 38 cues and stops being true with the first ambient bed. BS.1770 does not
    measure the mono fold of a stereo programme; it sums the weighted power of each channel.
    The fold reads low, and -- this is the part that bites -- by an amount that depends on how
    wide the material is: 3.01 dB at correlation 1.0, 6.02 dB at 0. A flat offset would hide in
    the target. A width-dependent one puts two beds of equal true loudness up to 3 dB apart,
    which is the exact failure the levelling exists to prevent.
    """
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    sr, ch = (int(v) for v in info.split(",")[:2])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                          "-f", "f32le", "-acodec", "pcm_f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    return a.reshape(-1, ch), sr


def channels(a):
    """(n,) or (n, ch) in, (n, ch) out. Lets the measures take either shape."""
    return a if a.ndim == 2 else a.reshape(-1, 1)


def weighted_power(a, sr):
    """Per-channel K-weighted power, one float per channel.

    BS.1770 weights L and R at G = 1.0 and sums, so every measure below sums this rather than
    averaging it. Summing is why a stereo file is not 3 dB quieter than the same signal in mono.
    """
    a = channels(a)
    return [float(np.mean(k_weight(a[:, c], sr) ** 2)) for c in range(a.shape[1])]


def db(v):
    return 20 * math.log10(max(float(v), 1e-12))


def true_peak(x, sr, oversample=4):
    """Inter-sample peak by band-limited interpolation."""
    n = len(x)
    spec = np.fft.rfft(x, n)
    big = np.zeros(n * oversample // 2 + 1, dtype=complex)
    big[:len(spec)] = spec * oversample
    return db(np.abs(np.fft.irfft(big, n * oversample)).max())


def m200(x, sr, window_ms=WINDOW_MS, hop_ms=2.0):
    """Loudest `window_ms` of K-weighted energy; short clips zero-padded -- see the module note.

    THE WINDOW IS FOUND ON THE SUMMED POWER, not per channel and then maximised: the loudest
    moment of a stereo cue is the loudest moment of the pair, which need not be the loudest
    moment of either channel alone.
    """
    a = channels(x)
    w = int(window_ms * sr / 1000)
    p = sum(k_weight(a[:, c], sr) ** 2 for c in range(a.shape[1]))
    if len(p) < w:
        p = np.concatenate([p, np.zeros(w - len(p))])
    cum = np.concatenate([[0.0], np.cumsum(p)])
    hop = max(1, int(hop_ms * sr / 1000))
    best = max((cum[i + w] - cum[i]) / w for i in range(0, len(p) - w + 1, hop))
    return -np.inf if best <= 0 else -0.691 + 10 * math.log10(best)


def integrated(x, sr):
    """Ungated integrated loudness over the whole clip -- the measure for an ambient bed.

    UNGATED, LIKE THE CUES, but for the opposite reason. A cue is too short to survive the
    relative gate; a bed is too even to need it. Measured on four beds the gate discarded
    nothing at all (247 of 247 blocks, 0.02 dB), and where it would bite it throws away the
    quiet floor the player hears for most of the clip and levels the bed by its gusts.

    NOT M200, WHICH IS THE WHOLE POINT OF A SECOND MEASURE. M200 anchors a 25 s bed on its
    single loudest moment: 3.4 dB above integrated on a steady fire loop, 5 to 10 dB on
    cathedral spans. The gap varies with how peaky the material is, so using M200 for beds
    would change the trim between two beds by about 5 dB for no reason a listener would agree
    with.
    """
    tot = sum(weighted_power(x, sr))
    return -np.inf if tot <= 0 else -0.691 + 10 * math.log10(tot)


def derived(kind):
    """Whether this kind's gainDb is computed here or authored by ear elsewhere."""
    return kind != "bed"


def profile(path, kind="cue"):
    """What one clip measures. `kind` picks the measure, and the record owns `kind`.

    WHY THE RECORD HAS TO SAY. With one rule, gain_for() could be re-run on any file and
    reproduce its answer from the audio alone. With two, a bare `gainDb` no longer says which
    rule produced it, and re-measuring would have to guess.
    """
    a, sr = load(path)
    # THE CEILING BELONGS TO THE LOUDER CHANNEL. Taking it from a fold would understate the hot
    # side -- on the first bed source examined, L peaks at -9.47 dBTP and R at -10.91.
    tp = max(true_peak(a[:, c], sr) for c in range(a.shape[1]))
    loud = integrated(a, sr) if kind == "bed" else m200(a, sr)
    return {"ms": round(1000 * len(a) / sr), "sr": sr, "ch": a.shape[1], "kind": kind,
            "peak": db(np.abs(a).max()), "tp": tp, "loudness": loud,
            "measure": "integrated" if kind == "bed" else "M200"}


def gain_for(p, target=TARGET_LUFS, ceiling=CEILING_DBTP):
    """A CUE's trim, clamped so true peak cannot pass the ceiling. A clip whose crest factor is
    too wide to reach target lands short; that is reported, not hidden.

    Not for beds -- a bed's trim is authored, and `ceiling_breach` is the only check that still
    applies to it.
    """
    wanted = target - p["loudness"]
    allowed = ceiling - p["tp"]
    return round(min(wanted, allowed), 1)


def ceiling_breach(p, g, ceiling=CEILING_DBTP):
    """How far an authored trim pushes true peak past the ceiling, or 0.0 if it does not.

    THE ONE RULE THAT IS NOT TASTE. Where a bed sits is the author's call; whether it clips is
    not, and Ordain v03 is the reason this tree checks at all -- it reads -0.1 dBFS, measures
    +0.75 dBTP and has been clipping on playback the whole time.
    """
    over = (p["tp"] + g) - ceiling
    return round(over, 2) if over > 0 else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write gainDb into attribution.json")
    ap.add_argument("--one", metavar="PATH", help="measure a single file and stop")
    ap.add_argument("--kind", choices=KINDS, default="cue",
                    help="with --one: which measure to use (the record owns this otherwise)")
    ap.add_argument("--target", type=float, default=None,
                    help="override the cue target")
    ap.add_argument("--trim", type=float, default=None,
                    help="with --one --kind bed: check an authored trim rather than derive one")
    args = ap.parse_args()

    if args.one:
        p = profile(pathlib.Path(args.one), args.kind)
        print("%d ms, %d Hz, %s | peak %.1f dBFS | true peak %.2f dBTP | %s %.2f LUFS"
              % (p["ms"], p["sr"], "mono" if p["ch"] == 1 else "%d ch" % p["ch"],
                 p["peak"], p["tp"], p["measure"], p["loudness"]))
        if derived(args.kind):
            target = args.target if args.target is not None else TARGET_LUFS
            g = gain_for(p, target)
            print("gainDb %+.1f  -> %.1f LUFS, true peak %.1f dBTP%s"
                  % (g, p["loudness"] + g, p["tp"] + g,
                     "" if p["loudness"] + g >= target - 0.5 else "   CEILING-LIMITED"))
        elif args.trim is None:
            # NO TRIM PROPOSED FOR A BED, which is the point: nothing here knows where it
            # should sit. Pass --trim to check one that a pair of ears produced.
            print("bed: no trim derived -- set it by ear, then pass --trim to check it")
        else:
            over = ceiling_breach(p, args.trim)
            print("gainDb %+.1f  -> %.1f LUFS, true peak %.1f dBTP%s"
                  % (args.trim, p["loudness"] + args.trim, p["tp"] + args.trim,
                     "" if not over else "   OVER THE CEILING BY %+.2f dB" % over))
        return 0

    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))
    files = rec["files"]
    rows, short, hot, notes = [], [], [], []
    for key in sorted(files):
        if not key.startswith("sfx/") or files[key].get("state") != "present":
            continue
        if not key.endswith(".ogg"):
            continue
        kind = files[key].get("kind", "cue")
        p = profile(BOARD / key, kind)
        target = args.target if args.target is not None else TARGET_LUFS
        if derived(kind):
            g = gain_for(p, target)
            if p["loudness"] + g < target - 0.5:
                short.append((key, p, g, target))
        else:
            # AUTHORED. Read it back rather than compute it -- see the note at the top.
            g = files[key].get("gainDb")
            if g is None:
                notes.append("%s is a bed with no gainDb; it has never been set by ear"
                             % key.replace("sfx/", ""))
                g = 0.0
            over = ceiling_breach(p, g)
            if over:
                notes.append("%s is a bed whose authored %+.1f dB puts it %+.2f dB over the "
                             "ceiling" % (key.replace("sfx/", ""), g, over))
        rows.append((key, p, g, target))
        if p["tp"] > -0.3:
            hot.append((key, p))

    print("%-44s %4s %6s %9s %7s %7s %8s %8s"
          % ("clip", "kind", "ms", "measure", "LUFS", "dBTP", "gainDb", "after"))
    for key, p, g, target in sorted(rows, key=lambda r: (r[1]["kind"], -r[2])):
        print("%-44s %4s %6d %9s %7.1f %7.2f %+8.1f %8.1f"
              % (key.replace("sfx/", ""), p["kind"], p["ms"], p["measure"], p["loudness"],
                 p["tp"], g, p["loudness"] + g))
    # SPREAD IS PER KIND, because a cue's M200 and a bed's integrated loudness are different
    # quantities and one spread over both would be a number about nothing.
    for kind in KINDS:
        got = [(p, g) for _, p, g, _ in rows if p["kind"] == kind]
        if not got:
            continue
        after = [p["loudness"] + g for p, g in got]
        before = [p["loudness"] for p, _ in got]
        if derived(kind):
            print("\n%-4s n=%d  spread before %.1f dB   after %.1f dB   target %.0f LUFS, "
                  "ceiling %.0f dBTP"
                  % (kind, len(got), max(before) - min(before), max(after) - min(after),
                     args.target if args.target is not None else TARGET_LUFS, CEILING_DBTP))
        else:
            # NO TARGET AND SO NO "SPREAD AFTER" TO JUDGE. Beds are not levelled against each
            # other by number; the figures are reported so the record can be checked, not so
            # the spread can be minimised.
            print("\n%-4s n=%d  authored by ear, no target. Landing: %s   ceiling %.0f dBTP"
                  % (kind, len(got), ", ".join("%.1f" % a for a in sorted(after)),
                     CEILING_DBTP))
    for key, p, g, target in short:
        print("  CEILING-LIMITED %s lands %.1f (%.1f short), crest %.1f dB"
              % (key.replace("sfx/", ""), p["loudness"] + g, target - p["loudness"] - g,
                 p["tp"] - p["loudness"]))
    for key, p in hot:
        verdict = ("clips on playback today" if p["tp"] > 0
                   else "has no inter-sample headroom left")
        print("  TRUE PEAK  %s is %+.2f dBTP and %s"
              % (key.replace("sfx/", ""), p["tp"], verdict))

    for n in notes:
        print("  NOTE:", n)

    if args.write:
        # BEDS ARE SKIPPED ON PURPOSE. Their gainDb was set by ear and this tool cannot
        # reproduce it; writing a computed number over it would silently undo the one part
        # of a bed's record that took a person to produce.
        wrote = 0
        for key, p, g, _ in rows:
            if not derived(p["kind"]):
                continue
            files[key]["gainDb"] = g
            wrote += 1
        (BOARD / "attribution.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\nwrote gainDb to %d cue records; %d bed records left as authored"
              % (wrote, len(rows) - wrote))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
