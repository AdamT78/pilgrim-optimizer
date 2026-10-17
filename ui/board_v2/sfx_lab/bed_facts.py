#!/usr/bin/env python3
"""Every number a new bed's record and the three notes need, from one decode.

    python3 ui/board_v2/sfx_lab/bed_facts.py <file.ogg> [<file.ogg> ...]
    python3 ui/board_v2/sfx_lab/bed_facts.py --record <file.ogg>   # record-shaped prose

WHY THIS EXISTS. Filing a bed needs about fifteen measurements, and before this they were
taken by writing a throwaway script per question -- silence fraction one minute, gated
loudness the next, wrap gaps after that. Four scripts, four decodes, and the channel
indexing got done wrong in at least one of them because `channels()` returns an (n, ch)
array and a fresh script iterates its rows. That bug reported a 36-second file as one
400 ms block and the number looked plausible enough to write down. A tool that always
takes the same measurements the same way cannot have that fault twice.

IT IS DELIBERATELY ONLY ABOUT THE FILE ITSELF. Provenance -- does this stem trace to the
source its covering note names -- is not here, because that probe is different every time:
the window, the speed candidates and above all the CONTROL have to be chosen for the claim
being tested, and a tool that picked them by default would make the control a formality.
See the rats_crossing record for what happens when a correlation runs without one.

EVERYTHING IS MEASURED ON THE SHIPPED FILE, never on the stem it came from. That distinction
cost the tree fourteen wrong silence percentages: they were read off the WAV stems, and
Vorbis rings out across short gaps, so the shipped file is reliably the less silent of the
two -- by up to 4.76 points. Pass the stem as a second argument if you want both; they will
be printed side by side and labelled.
"""

import argparse
import hashlib
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sfx_levels as S  # noqa: E402

BLOCK_S = 0.400
HOP_S = 0.100
ABS_GATE_LUFS = -70.0
REL_GATE_LU = -10.0
PAUSE_S = 0.25        # the shortest silence this tree calls a pause rather than texture
# BELOW THIS FRACTION OF THE SHORTEST INTERIOR PAUSE, THE SEAM IS A TELL. 0.95 and not 0.90,
# which was the first value and was wrong in a checkable way: it put `rammers` at 0.91 into
# "listen" and so quietly overturned a judgement the loop note has carried since that bed was
# filed. 5% is also the conservative end of the published range for telling two multi-second
# intervals apart (5-10%), and a flag whose job is to fetch a human should sit at the
# conservative end. At 0.95 rammers is a tell and build_roads_actionB/fabric, 0.98, is not.
TELL_RATIO = 0.95


def _lufs(power):
    return -0.691 + 10 * math.log10(power) if power > 0 else -math.inf


def gated(a, sr):
    """BS.1770-4 gated integrated loudness, plus the block counts behind it.

    The block counts are not a diagnostic here, they are the point. On a file whose quiet
    parts are true digital silence the ungated-to-gated delta collapses to
    10*log10(all blocks / surviving blocks) and says nothing else -- it is the duty cycle
    wearing a loudness measure's clothes. Printing the prediction beside the measurement is
    what makes that visible rather than something to be rediscovered.
    """
    p = sum(S.k_weight(a[:, c], sr) ** 2 for c in range(a.shape[1]))
    blk, hop = int(round(BLOCK_S * sr)), int(round(HOP_S * sr))
    if len(p) < blk:
        return None
    cum = np.concatenate([[0.0], np.cumsum(p)])
    idx = np.arange(0, len(p) - blk + 1, hop)
    pw = (cum[idx + blk] - cum[idx]) / blk
    keep = pw > 10 ** ((ABS_GATE_LUFS + 0.691) / 10)
    if not keep.any():
        return None
    rel = _lufs(float(pw[keep].mean())) + REL_GATE_LU
    keep2 = keep & (pw > 10 ** ((rel + 0.691) / 10))
    if not keep2.any():
        return None
    return {"lufs": _lufs(float(pw[keep2].mean())), "kept": int(keep2.sum()),
            "above_abs": int(keep.sum()), "total": len(pw)}


def silence(a, sr):
    """Exact digital silence, and WHERE it is rather than only how much.

    How much is the famous number and the least useful one. A bed that is 97% silence in one
    unbroken burst and a bed that is 97% silence in three scattered ones behave differently
    under the gate, loop differently, and collide differently with the other tracks of their
    action -- `bottle_knock` and `rat_squeaks` are exactly that pair. So the runs, the head
    and tail, and the largest interior gap all come out together.
    """
    m = np.abs(a).max(axis=1)
    n = len(m)
    nz = np.flatnonzero(m > 0)
    out = {"pct": 100.0 * float((m == 0).sum()) / n, "runs": 0, "first": None, "last": None,
           "head": 0.0, "tail": 0.0, "wrap": 0.0, "interior_max": 0.0}
    if not len(nz):
        return out
    d = np.diff(nz)
    breaks = np.flatnonzero(d > 1)
    out["runs"] = len(breaks) + 1
    out["first"] = nz[0] / sr
    out["last"] = nz[-1] / sr
    out["head"] = nz[0] / sr
    out["tail"] = (n - 1 - nz[-1]) / sr
    out["wrap"] = out["head"] + out["tail"]
    out["interior_max"] = max(((d[b] - 1) / sr for b in breaks), default=0.0)
    # PAUSES, NOT EVERY GAP. Section 13's test is about whether the loop point breaks the
    # rhythm of the file's own silences, and a 3 ms hole between two transients is not one of
    # those -- it is texture. Below this threshold the interior minimum collapses towards zero
    # and the test stops being able to say anything. 0.25 s is the shortest thing anyone has
    # called a pause in these notes.
    out["pauses"] = sorted(g for g in ((d[b] - 1) / sr for b in breaks) if g >= PAUSE_S)
    return out


def wrap_verdict(sil):
    """Section 13's three-way test, stated as a RATIO rather than a difference.

    THE DIFFERENCE FORM MISREAD A FILE AND THIS IS THE REPAIR. `build_roads_actionB/fabric`
    has a wrap gap 60 ms under its shortest interior pause and was written up as `rammers'
    fault almost exactly`, because in seconds the two misses are the same size: 0.060 against
    0.068. In the terms that matter they are five and a half times apart -- 1.6% of a 3.6 s
    gap against 8.9% of a 0.77 s one. DURATION IS HEARD AS A RATIO. The published figure for
    telling two multi-second intervals apart is around 5-10% of their length, so a miss of a
    couple of percent cannot be heard however many milliseconds it is.

    Reporting only "the wrap is not the longest gap" was the other half of the fault: that is
    the condition for NOT BEING PROVABLY SAFE, which is a different claim from being wrong,
    and in capitals it reads like a failure. Three verdicts now, and the middle one says what
    to do rather than implying the file is broken.
    """
    p = sil["pauses"]
    w = sil["wrap"]
    if not p:
        return ("no interior pause to compare", None)
    if w >= p[-1]:
        return ("SAFE -- the wrap is the longest pause in the file", w / p[-1])
    if w < TELL_RATIO * p[0]:
        return ("A TELL -- the wrap is the short one; the loop point breaks the pattern", w / p[0])
    return ("listen -- between the thresholds, %.2fx the shortest interior pause" % (w / p[0]),
            w / p[0])


def seam(a, neighbours=10):
    """The butt-join step at the wrap, against the two yardsticks this tree uses.

    WHY TWO. The step is |first sample - last sample|: what a listener hears as a click when
    the loop comes round. On its own it is a number with no scale, so it gets compared to
    something -- and the obvious comparison, the file's MEDIAN sample-to-sample difference,
    fails silently on a sparse bed, where the median is exactly zero and the ratio is
    undefined or enormous. The honest comparison is against the file's OWN IMMEDIATE
    NEIGHBOURS: the largest step among the samples either side of the join. If the join is no
    bigger a jump than the waveform is already making right there, it cannot be heard.

    Three files have now split the two tests the same way -- passing on neighbours, failing on
    median -- which is the pattern that says the median test is the one at fault.
    """
    out = []
    for c in range(a.shape[1]):
        x = a[:, c]
        if len(x) < 2 * neighbours + 2:
            continue
        step = abs(float(x[0]) - float(x[-1]))
        d = np.abs(np.diff(x))
        med = float(np.median(d))
        near = np.concatenate([d[-neighbours:], d[:neighbours]])
        nmax = float(near.max()) if len(near) else 0.0
        out.append({"step": step, "median": med, "neighbour_max": nmax,
                    "x_median": step / med if med > 0 else None,
                    "x_neighbour": step / nmax if nmax > 0 else None})
    return out


def stereo(a, sr, max_lag_ms=20.0):
    """L/R correlation, exact dual mono, and the delayed-copy check.

    THE DELAYED-COPY CHECK IS HERE BECAUSE OF `oil_lamp_flame`, which was given a stereo
    field by delaying one channel about 4 ms. That reads as a wide, pleasant stereo file and
    combs badly the moment anything folds it to mono, which the board may well do. It is
    invisible in a correlation figure alone -- a delayed copy still correlates well -- so the
    lag has to be searched for. A non-zero best lag at high r means notches every 1/lag Hz.
    """
    if a.shape[1] < 2:
        return {"mono": True}
    L, R = a[:, 0], a[:, 1]
    if L.shape != R.shape:
        return {"mono": True}
    identical = bool(np.array_equal(L, R))
    sl, sr_ = L - L.mean(), R - R.mean()
    den = math.sqrt(float(sl @ sl) * float(sr_ @ sr_))
    corr = float(sl @ sr_) / den if den > 0 else float("nan")
    n = min(len(L), 1 << 20)
    span = int(max_lag_ms * sr / 1000)
    best_lag, best_r = 0, corr
    if not identical and span > 0 and den > 0:
        x, y = sl[:n], sr_[:n]
        fx = np.fft.rfft(x, 2 * n)
        fy = np.fft.rfft(y, 2 * n)
        cc = np.fft.irfft(fx * np.conj(fy), 2 * n)
        cc = np.concatenate([cc[-span:], cc[:span + 1]])
        lags = np.arange(-span, span + 1)
        nx = math.sqrt(float(x @ x) * float(y @ y))
        if nx > 0:
            k = int(np.argmax(np.abs(cc)))
            best_lag, best_r = int(lags[k]), float(cc[k] / nx)
    fold = (L + R) / 2.0
    rms = lambda v: math.sqrt(float(np.mean(v ** 2)))  # noqa: E731
    ref = max(rms(L), rms(R))
    loss = 20 * math.log10(rms(fold) / ref) if ref > 0 and rms(fold) > 0 else -math.inf
    return {"mono": False, "corr": corr, "identical": identical,
            "lag_ms": 1000.0 * best_lag / sr, "lag_r": best_r, "fold_loss_db": loss}


def probe(path):
    p = Path(path)
    a, sr = S.load(p)
    a = S.channels(a)
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=sample_rate,channels,bits_per_raw_sample,codec_name",
         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True).stdout.split()
    dur = len(a) / sr
    peak = S.db(np.abs(a).max())
    tp = max(S.true_peak(a[:, c], sr) for c in range(a.shape[1]))
    ung = S.integrated(a, sr)
    g = gated(a, sr)
    sil = silence(a, sr)
    st = stereo(a, sr)
    return {"path": p, "sr": sr, "ch": a.shape[1], "codec": info[0] if info else "?",
            "dur": dur, "peak": peak, "tp": tp, "ungated": ung, "gated": g,
            "sil": sil, "stereo": st, "m200": S.m200(a, sr), "seam": seam(a),
            "sha": hashlib.sha256(p.read_bytes()).hexdigest()}


def show(f):
    g, sil, st = f["gated"], f["sil"], f["stereo"]
    print("\n%s" % f["path"].name)
    print("  %.0f ms, %d Hz, %d ch, %s   sha %s"
          % (f["dur"] * 1000, f["sr"], f["ch"], f["codec"], f["sha"][:16]))
    print("  peak %.2f dBFS   true peak %.2f dBTP   M200 %.2f LUFS" % (f["peak"], f["tp"], f["m200"]))
    if g:
        delta = f["ungated"] - g["lufs"]
        pred = 10 * math.log10(g["total"] / g["kept"])
        agree = abs(abs(delta) - pred)
        print("  integrated %.2f LUFS (ungated)   gated %.2f   delta %.2f on %d of %d blocks"
              % (f["ungated"], g["lufs"], delta, g["kept"], g["total"]))
        print("    block-count identity predicts %.2f, out by %.3f dB%s"
              % (pred, agree, "" if agree <= 0.06 else "   <-- OUTSIDE 0.06, quiet parts are not true silence"))
        if g["above_abs"] != g["kept"]:
            print("    (%d blocks clear the absolute gate, %d the relative one)"
                  % (g["above_abs"], g["kept"]))
    else:
        print("  integrated %.2f LUFS (ungated)   gated: too short to block" % f["ungated"])
    print("  silence %.2f%% exact, in %d non-silent run%s"
          % (sil["pct"], sil["runs"], "" if sil["runs"] == 1 else "s"))
    if sil["first"] is not None:
        print("    material %.3f to %.3f s   head %.3f  tail %.3f  WRAP GAP %.3f  interior max %.3f"
              % (sil["first"], sil["last"], sil["head"], sil["tail"], sil["wrap"], sil["interior_max"]))
        # Section 13's test compares the wrap gap against the interior pauses, so it only has
        # anything to say about a bed that HAS them. A continuous bed has none, and an
        # unguarded comparison cries wolf on every one of those.
        if sil["pauses"]:
            verdict, ratio = wrap_verdict(sil)
            print("    pauses %s   wrap %.3f  ->  %s"
                  % (", ".join("%.3f" % g for g in sil["pauses"]), sil["wrap"], verdict))
    for c, s in enumerate(f["seam"]):
        xm = "n/a (median is zero -- sparse file)" if s["x_median"] is None else "%.2fx median" % s["x_median"]
        xn = "n/a" if s["x_neighbour"] is None else "%.2fx neighbours" % s["x_neighbour"]
        print("  butt-join ch%d  step %.6f   %s   %s%s"
              % (c, s["step"], xm, xn,
                 "   <-- louder than its own neighbours; the seam may click"
                 if s["x_neighbour"] and s["x_neighbour"] > 1.0 else ""))
    if st.get("mono"):
        print("  mono -- no stereo field to check")
    else:
        print("  L/R %+.6f%s" % (st["corr"], "   DUAL MONO, identical sample for sample" if st["identical"] else ""))
        if not st["identical"]:
            print("    best inter-channel lag %+.3f ms at r %+.4f   mono fold loses %.2f dB"
                  % (st["lag_ms"], st["lag_r"], -st["fold_loss_db"]))
            if abs(st["lag_ms"]) > 0.3 and abs(st["lag_r"]) > 0.7:
                print("    <-- DELAYED COPY, not a recorded field: folding to mono will comb every %.0f Hz"
                      % (1000.0 / abs(st["lag_ms"])))


def record_line(f):
    """The `measured` string, in the shape the records already use."""
    g, sil, st = f["gated"], f["sil"], f["stereo"]
    bits = ["%.0f ms, peak %.1f dB, integrated %.2f LUFS, true peak %.2f dBTP, %s %d kHz"
            % (f["dur"] * 1000, f["peak"], f["ungated"], f["tp"],
               "mono" if f["ch"] == 1 else "stereo", round(f["sr"] / 1000))]
    if not st.get("mono"):
        bits[0] += ", L/R correlation %+.6f" % st["corr"]
    bits.append("%.1f%% of the file is exact digital silence in %d run%s"
                % (sil["pct"], sil["runs"], "" if sil["runs"] == 1 else "s"))
    if sil["first"] is not None:
        bits.append("material runs %.3f to %.3f s and the wrap gap is %.3f s"
                    % (sil["first"], sil["last"], sil["wrap"]))
    if g:
        delta = f["ungated"] - g["lufs"]
        pred = 10 * math.log10(g["total"] / g["kept"])
        bits.append("Gated it reads %.2f LUFS, %.2f dB off the ungated figure on %d of %d "
                    "blocks, against 10*log10(%d/%d) = %.2f -- the block-count identity"
                    % (g["lufs"], abs(delta), g["kept"], g["total"], g["total"], g["kept"], pred))
    bits.append("THE TRIM IS ZERO BECAUSE NOBODY HAS SET IT")
    print("\n%s" % f["path"].name)
    print("  \"sha256\": \"%s\"" % f["sha"])
    print("  \"measured\": \"%s.\"" % ". ".join(bits))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--record", action="store_true",
                    help="also print a record-shaped `measured` string and the sha256")
    args = ap.parse_args()
    done = [probe(p) for p in args.files]
    for f in done:
        show(f)
    if args.record:
        for f in done:
            record_line(f)
    if len(done) > 1:
        print("\n%-34s %10s %10s %9s" % ("", "silence%", "true peak", "wrap"))
        for f in done:
            print("%-34s %9.2f%% %9.2f %8.3f"
                  % (f["path"].name[:34], f["sil"]["pct"], f["tp"], f["sil"]["wrap"]))


if __name__ == "__main__":
    main()
