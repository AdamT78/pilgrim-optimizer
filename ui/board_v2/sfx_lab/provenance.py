#!/usr/bin/env python3
"""Where in a source recording a stem's material came from, found by searching, never by arithmetic.

    python3 ui/board_v2/sfx_lab/provenance.py <stem> <source> [<control> ...]
    python3 ui/board_v2/sfx_lab/provenance.py --regions <stem> <source>
    python3 ui/board_v2/sfx_lab/provenance.py --against <other_bed> <stem> <source>

WHY THIS EXISTS, AND IT IS ONE MISTAKE MADE THREE TIMES IN TWO DAYS. A probe reports that a
stem run matches its source at +0.800 s. The obvious next step is to slice the source at
that offset and fit a gain, or correlate the whole run, or subtract and look at the
residual. Every one of those slices BY ARITHMETIC, and the reported offset is rounded to
however many decimals got printed. On transient material a three-millisecond error takes
r from 0.85 to 0.04, and the result does not look like a bug -- it looks like a finding.
It was caught three times by a residual that could not possibly be right (99.9% of rms
where the correlation predicted 59%), which is luck wearing the clothes of method.

SO THIS MODULE NEVER HANDS BACK A BARE OFFSET TO SLICE WITH. `locate` returns a Placement
carrying `aligned` -- the actual source samples, already cut at the searched lag and the
same length as the window. Fitting, subtracting and residuals all take the Placement, so
there is no step at which a caller converts seconds to samples. The offset is still
reported, because records quote it, but nothing in the pipeline consumes it.

THE OTHER SILENT FAILURE IS A RATE MISMATCH. Correlating a 48 kHz stem against a 44.1 kHz
source returns noise that looks exactly like "the stated source is wrong". `load_pair`
refuses to return a pair at two rates and resamples the source, saying so.

IT DOES NOT CHOOSE CONTROLS. bed_facts.py declines provenance work for the reason that
applies here too: the control has to be picked for the claim being tested, and a default
would make it a formality. Controls are arguments.
"""

import argparse
import math
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfx_levels as S  # noqa: E402

MIN_RUN_S = 0.050     # shorter than this is an encoder artefact, not a gesture
# BELOW THIS, A RUN CANNOT TELL ITS SOURCE FROM A CONTROL, and a match on one is not
# evidence. Measured on produce_actionA/nearby_raven, where the stated source and five
# other bird recordings were probed run by run: on runs of 150 ms and over the stated
# source beat the best control by 3.67x, and under 150 ms by 1.09x. A short broadband
# transient correlates with any other short broadband transient -- the crow control
# reached 0.79 on an 88 ms window against the stated source's 0.95. The runs are still
# reported, because they are still material; they just carry no weight on their own.
CONTROL_POWER_S = 0.150
STRONG_R = 0.50       # what this tree has always called a match
MERGE_GAP_S = 0.0     # source regions touching at a sample are one region

Placement = namedtuple("Placement", "r start end offset aligned sr")
Fit = namedtuple("Fit", "gain gain_db residual_frac predicted_frac")


def mono(a):
    """(n,) or (n, ch) in, one float64 channel out.

    The mid, not the left. A stem panned hard one way still has its material in the mid,
    and picking channel 0 found 0.14 where the mid found 0.88 on the first bed this was
    tried against.
    """
    a = S.channels(a)
    return (a.mean(axis=1) if a.shape[1] > 1 else a[:, 0]).astype(np.float64)


def load_pair(stem_path, source_path):
    """Both files as mid-channel float64 at ONE rate, resampling the source if it differs.

    A probe across a rate mismatch does not fail loudly. It returns small correlations at
    scattered lags, which is indistinguishable from a wrong source -- and the only source
    in this tree that needed it, a 44.1 kHz AIFF, would have been filed as unconfirmed.
    """
    a, sr_a = S.load(stem_path)
    b, sr_b = S.load(source_path)
    if sr_a == sr_b:
        return mono(a), mono(b), sr_a, False
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "resampled.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source_path),
                        "-ar", str(sr_a), "-c:a", "pcm_s24le", str(out)], check=True)
        b, _ = S.load(out)
    return mono(a), mono(b), sr_a, True


def runs(x, sr, min_s=MIN_RUN_S):
    """Sample ranges of exact non-silence, as (start, end) pairs.

    Exact digital zero is the boundary because that is what the edit left behind; anything
    with a threshold starts arguing with the encoder. Runs under `min_s` are dropped --
    Vorbis rings across short gaps and manufactures them by the hundred.
    """
    nz = np.abs(x) > 0
    if not nz.any():
        return []
    d = np.diff(nz.astype(np.int8))
    starts = list(np.where(d == 1)[0] + 1)
    ends = list(np.where(d == -1)[0] + 1)
    if nz[0]:
        starts = [0] + starts
    if nz[-1]:
        ends = ends + [len(nz)]
    need = int(round(min_s * sr))
    return [(s, e) for s, e in zip(starts, ends) if e - s >= need]


def locate(window, source, sr):
    """Find `window` in `source` by normalised cross-correlation at every lag.

    Returns a Placement whose `aligned` field is the matching stretch of source, already
    cut. THAT FIELD IS THE POINT OF THIS MODULE: everything downstream takes it instead of
    re-deriving a slice from `offset`.

    The normalisation is per-lag -- the source's own mean and variance inside each candidate
    window -- so a quiet stretch of source cannot win on loudness alone.
    """
    n = len(window)
    if n == 0 or len(source) < n:
        return None
    w = window - window.mean()
    nw = float(np.sqrt(w @ w))
    if nw == 0:
        return None
    # THE SOURCE IS CENTRED FIRST, AND THAT IS NOT COSMETIC. The per-lag variance comes out
    # of a running-sum identity, sum(x^2) - sum(x)^2/n, which subtracts two large numbers to
    # leave a small one. On a long source the cumulative sums are large enough that the
    # cancellation eats most of the significant digits, and over a NEARLY silent stretch the
    # result is numerical rubbish a few orders of magnitude below the true variance. Dividing
    # by its square root then returns correlations above 1 -- this module shipped doing
    # exactly that and reported r = -3.4152 on a 51 ms window, which is not a correlation at
    # all. Centring shrinks the sums; the relative floor below catches what survives.
    # `aligned` must stay the REAL samples, so the centred copy is used only for the search.
    # Returning centred samples would quietly change the gain `fit` reports.
    centred = source - source.mean()
    N = 1 << (len(source) + n - 1).bit_length()
    num = np.fft.irfft(np.fft.rfft(centred, N) * np.conj(np.fft.rfft(w, N)), N)[:len(source) - n + 1]
    cs = np.concatenate([[0.0], np.cumsum(centred)])
    cs2 = np.concatenate([[0.0], np.cumsum(centred ** 2)])
    k = np.arange(len(source) - n + 1)
    var = (cs2[k + n] - cs2[k]) - (cs[k + n] - cs[k]) ** 2 / n
    # The floor is a window's worth of energy at 1e-9 of the source's own mean square --
    # about -118 dBFS rms, under any real noise floor and well over the rounding error.
    floor = 1e-9 * float(centred @ centred) / len(centred) * n
    r = normalise(num, nw, var, floor)
    i = int(np.argmax(np.abs(r)))
    # THE WINNER IS RE-SCORED EXACTLY. The ranking above comes from the running-sum identity,
    # which is fast and approximate; one direct dot product at the chosen lag costs nothing
    # and is what gets reported, so no quoted correlation ever carries that approximation.
    seg = centred[i:i + n]
    sg = seg - seg.mean()
    den = float(np.sqrt(float(w @ w) * float(sg @ sg)))
    exact = float(w @ sg) / den if den > 0 else 0.0
    return Placement(r=exact, start=i, end=i + n, offset=i,
                     aligned=source[i:i + n].copy(), sr=sr)


def normalise(num, nw, var, floor=0.0):
    """Turn raw cross-correlation into r, refusing the lags where the arithmetic has failed.

    SEPARATE FROM `locate` BECAUSE THIS IS WHERE THE MODULE'S ONE SHIPPED BUG LIVED, and a
    bug worth a guard is worth a guard that can be tested without conjuring the audio that
    triggered it. `var` arrives from a running-sum identity -- sum(x^2) minus sum(x)^2/n --
    which subtracts two large numbers to leave a small one. Over a long source the
    accumulated rounding is around 1e-14 of the total energy, so any candidate window whose
    true variance is below that comes back as noise, or as a NEGATIVE number. Dividing by
    its square root returns a "correlation" of -3.4152, which this module did on a 51 ms
    window of a 91-second raven recording, and then invented two source regions from it.

    Exact digital silence was never the problem; it gives exactly zero and was always
    caught. NEAR-silence is the problem, and the floor has to be relative to the energy in
    play rather than an absolute epsilon, because that is what the error scales with.
    """
    var = np.asarray(var, dtype=np.float64).copy()
    var[var <= max(1e-20, float(floor))] = np.inf
    with np.errstate(invalid="ignore", divide="ignore"):
        r = num / (nw * np.sqrt(var))
    r[~np.isfinite(r)] = 0.0
    # The floor should make this unreachable. It is asserted rather than clipped because a
    # correlation outside [-1, 1] means the normalisation is wrong, and a clipped wrong
    # answer is harder to notice than a loud one.
    worst = float(np.abs(r).max()) if r.size else 0.0
    if worst > 1.0 + 1e-9:                                            # pragma: no cover
        raise AssertionError(
            "normalisation produced |r| = %.4f, which is not a correlation; the variance "
            "floor did not hold" % worst)
    return r


def fit(window, placement):
    """Least-squares gain of `window` against the ALIGNED source, and what is left over.

    `predicted_frac` is sqrt(1 - r^2), the residual the correlation alone implies. When the
    measured residual sits near it, nothing unexplained is present and the run is one
    continuous copy at one gain. When it is far above -- 99.9% against a predicted 59% --
    the alignment is wrong, and that disagreement is the check that caught the arithmetic
    slice three times. It is returned rather than left to be noticed.
    """
    s = placement.aligned
    n = min(len(window), len(s))
    w, s = window[:n], s[:n]
    denom = float(s @ s)
    if denom == 0:
        return None
    g = float(w @ s) / denom
    res = w - g * s
    rms = math.sqrt(float(np.mean(w ** 2)))
    frac = math.sqrt(float(np.mean(res ** 2))) / rms if rms > 0 else math.inf
    return Fit(gain=g, gain_db=20 * math.log10(abs(g)) if g != 0 else -math.inf,
               residual_frac=frac,
               predicted_frac=math.sqrt(max(0.0, 1.0 - placement.r ** 2)))


def check_stated_offset(window, source, sr, stated_s, tol_ms=1.0):
    """Correlate at a stated offset AND at the searched one, and report both.

    For when a covering note names a placement. The note is a claim; agreement to the
    sample is evidence, and a disagreement of a few milliseconds is the whole trap this
    module exists for. Returns (searched Placement, r at the stated offset, drift in ms).
    """
    best = locate(window, source, sr)
    if best is None:
        return None
    i = int(round(stated_s * sr))
    n = len(window)
    if i < 0 or i + n > len(source):
        return best, float("nan"), float("nan")
    s = source[i:i + n]
    w = window - window.mean()
    s0 = s - s.mean()
    den = math.sqrt(float(w @ w) * float(s0 @ s0))
    at = float(w @ s0) / den if den > 0 else 0.0
    return best, at, 1000.0 * (best.offset - i) / sr


def locate_all(stem, source, sr, min_s=MIN_RUN_S):
    """Every non-silent run of `stem` located in `source`. Returns (run, Placement) pairs."""
    out = []
    for s, e in runs(stem, sr, min_s):
        p = locate(stem[s:e], source, sr)
        if p is not None:
            out.append(((s, e), p))
    return out


def regions(placements, sr, merge_gap_s=MERGE_GAP_S):
    """The source intervals a set of placements draws on, merged, in seconds.

    Forty placements can come from two places. Collapsing them is what turns a list of
    offsets into a statement about how much of the recording was actually used.
    """
    spans = sorted((p.start / sr, p.end / sr) for p in placements)
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + merge_gap_s:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def disjoint(regions_a, regions_b):
    """Do two beds cut from one recording share any of it? Returns (overlaps, closest gap).

    The question that matters when one upload feeds two beds, and a correlation answers it
    weakly -- a low score says the cuts differ, while an empty overlap list says they cannot
    share a sample. `closest` is the smallest gap between any region of one and any of the
    other, which is what makes a deliberate near-miss visible as a near-miss.
    """
    overlaps, gaps = [], []
    for a, b in regions_a:
        for c, d in regions_b:
            lo, hi = max(a, c), min(b, d)
            if hi > lo:
                overlaps.append((a, b, c, d, hi - lo))
            elif b <= c:
                gaps.append(c - b)
            elif d <= a:
                gaps.append(a - d)
    return overlaps, (min(gaps) if gaps else None)


def _report(stem_path, source_path, controls, min_s, show_regions):
    stem, src, sr, resampled = load_pair(stem_path, source_path)
    print("%s  <-  %s" % (Path(stem_path).name, Path(source_path).name))
    if resampled:
        print("  SOURCE RESAMPLED to the stem's %d Hz before correlating" % sr)
    found = locate_all(stem, src, sr, min_s)
    if not found:
        print("  no runs over %.0f ms" % (1000 * min_s))
        return
    strong = [p for _, p in found if abs(p.r) >= STRONG_R]
    short = sum(1 for (s0, e0), _ in found if (e0 - s0) / sr < CONTROL_POWER_S)
    print("  %d of %d runs at |r| >= %.2f   max %.4f%s"
          % (len(strong), len(found), STRONG_R, max(abs(p.r) for _, p in found),
             "   (%d run(s) under %.0f ms carry no control power)" % (short, 1000 * CONTROL_POWER_S)
             if short else ""))
    for (s, e), p in found:
        f = fit(stem[s:e], p)
        flag = ""
        if f is not None and f.residual_frac > f.predicted_frac + 0.10:
            flag = "   <-- residual %.0f%% vs %.0f%% predicted; ALIGNMENT SUSPECT" % (
                100 * f.residual_frac, 100 * f.predicted_frac)
        if (e - s) / sr < CONTROL_POWER_S:
            flag += "   [short: no control power]"
        print("    run %7.3f-%7.3f  r %+.4f  <- source %7.4f-%7.4f  gain %+6.2f dB%s"
              % (s / sr, e / sr, p.r, p.start / sr, p.end / sr,
                 f.gain_db if f else float("nan"), flag))
    if show_regions:
        merged = regions([p for _, p in found if abs(p.r) >= STRONG_R], sr)
        used = sum(b - a for a, b in merged)
        print("  %d distinct source region(s), %.3f s of %.3f = %.1f%%"
              % (len(merged), used, len(src) / sr, 100 * used / (len(src) / sr)))
        for a, b in merged:
            print("     %7.4f - %7.4f" % (a, b))
    for c in controls:
        _, cs, csr, _ = load_pair(stem_path, c)
        worst = 0.0
        for (s, e), _p in found:
            cp = locate(stem[s:e], cs, csr)
            if cp is not None:
                worst = max(worst, abs(cp.r))
        print("  control %-44s max |r| %.4f%s"
              % (Path(c).name, worst, "   (0 of %d)" % len(found) if worst < STRONG_R else
                 "   *** REACHES THE MATCH THRESHOLD ***"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stem")
    ap.add_argument("source")
    ap.add_argument("controls", nargs="*")
    ap.add_argument("--regions", action="store_true", help="collapse placements into source regions")
    ap.add_argument("--min-run", type=float, default=MIN_RUN_S, metavar="S")
    ap.add_argument("--against", metavar="BED", action="append", default=[],
                    help="another bed from the same source: report shared source regions")
    a = ap.parse_args()
    _report(a.stem, a.source, a.controls, a.min_run, a.regions or bool(a.against))
    for other in a.against:
        stem, src, sr, _ = load_pair(a.stem, a.source)
        o_stem, o_src, o_sr, _ = load_pair(other, a.source)
        mine = regions([p for _, p in locate_all(stem, src, sr, a.min_run)
                        if abs(p.r) >= STRONG_R], sr)
        theirs = regions([p for _, p in locate_all(o_stem, o_src, o_sr, a.min_run)
                          if abs(p.r) >= STRONG_R], o_sr)
        ov, closest = disjoint(mine, theirs)
        print("\nagainst %s, in the same source:" % Path(other).name)
        if ov:
            print("  SHARED SOURCE MATERIAL in %d place(s):" % len(ov))
            for x in ov:
                print("     %.4f-%.4f and %.4f-%.4f overlap by %.4f s" % x)
        else:
            print("  no shared source material")
        if closest is not None:
            print("  closest approach %.4f s" % closest)


if __name__ == "__main__":
    main()
