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

THE MEASURE IS M200: the loudest 200 ms of K-weighted energy, ITU-R BS.1770-4 weighting,
ungated. Three choices in that sentence, each deliberate.

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
CEILING_DBTP = -1.0
WINDOW_MS = 200.0


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
    """Mono float at the file's OWN rate. Resampling first would move the peak -- a 96 kHz
    clip read at 48 can lose 2 dB, which is how an earlier audit 'found' four faults in four
    correct records."""
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    sr, ch = (int(v) for v in info.split(",")[:2])
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                          "-f", "f32le", "-acodec", "pcm_f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, sr


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
    """Loudest `window_ms` of K-weighted energy; short clips zero-padded -- see the module note."""
    w = int(window_ms * sr / 1000)
    p = k_weight(x, sr) ** 2
    if len(p) < w:
        p = np.concatenate([p, np.zeros(w - len(p))])
    cum = np.concatenate([[0.0], np.cumsum(p)])
    hop = max(1, int(hop_ms * sr / 1000))
    best = max((cum[i + w] - cum[i]) / w for i in range(0, len(p) - w + 1, hop))
    return -np.inf if best <= 0 else -0.691 + 10 * math.log10(best)


def profile(path):
    x, sr = load(path)
    return {"ms": round(1000 * len(x) / sr), "sr": sr,
            "peak": db(np.abs(x).max()), "tp": true_peak(x, sr), "m200": m200(x, sr)}


def gain_for(p, target=TARGET_LUFS, ceiling=CEILING_DBTP):
    """The trim, clamped so true peak cannot pass the ceiling. A clip whose crest factor is
    too wide to reach target lands short; that is reported, not hidden."""
    wanted = target - p["m200"]
    allowed = ceiling - p["tp"]
    return round(min(wanted, allowed), 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write gainDb into attribution.json")
    ap.add_argument("--one", metavar="PATH", help="measure a single file and stop")
    ap.add_argument("--target", type=float, default=TARGET_LUFS)
    args = ap.parse_args()

    if args.one:
        p = profile(pathlib.Path(args.one))
        g = gain_for(p, args.target)
        print("%d ms, %d Hz | peak %.1f dBFS | true peak %.2f dBTP | M200 %.1f LUFS"
              % (p["ms"], p["sr"], p["peak"], p["tp"], p["m200"]))
        print("gainDb %+.1f  -> %.1f LUFS, true peak %.1f dBTP%s"
              % (g, p["m200"] + g, p["tp"] + g,
                 "" if p["m200"] + g >= args.target - 0.5 else "   CEILING-LIMITED"))
        return 0

    rec = json.loads((BOARD / "attribution.json").read_text(encoding="utf-8"))
    files = rec["files"]
    rows, short, hot = [], [], []
    for key in sorted(files):
        if not key.startswith("sfx/") or files[key].get("state") != "present":
            continue
        if not key.endswith(".ogg"):
            continue
        p = profile(BOARD / key)
        g = gain_for(p, args.target)
        rows.append((key, p, g))
        if p["m200"] + g < args.target - 0.5:
            short.append((key, p, g))
        if p["tp"] > -0.3:
            hot.append((key, p))

    print("%-44s %6s %7s %7s %8s %8s" % ("clip", "ms", "M200", "dBTP", "gainDb", "after"))
    for key, p, g in sorted(rows, key=lambda r: -r[2]):
        print("%-44s %6d %7.1f %7.2f %+8.1f %8.1f"
              % (key.replace("sfx/", ""), p["ms"], p["m200"], p["tp"], g, p["m200"] + g))
    after = [p["m200"] + g for _, p, g in rows]
    before = [p["m200"] for _, p, _ in rows]
    print("\nspread before %.1f dB   after %.1f dB   target %.0f LUFS, ceiling %.0f dBTP"
          % (max(before) - min(before), max(after) - min(after), args.target, CEILING_DBTP))
    for key, p, g in short:
        print("  CEILING-LIMITED %s lands %.1f (%.1f short), crest %.1f dB"
              % (key.replace("sfx/", ""), p["m200"] + g, args.target - p["m200"] - g,
                 p["tp"] - p["m200"]))
    for key, p in hot:
        verdict = ("clips on playback today" if p["tp"] > 0
                   else "has no inter-sample headroom left")
        print("  TRUE PEAK  %s is %+.2f dBTP and %s"
              % (key.replace("sfx/", ""), p["tp"], verdict))

    if args.write:
        for key, p, g in rows:
            files[key]["gainDb"] = g
        (BOARD / "attribution.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("\nwrote gainDb to %d records" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
