"""Guards for ui/board_v2/sfx_lab/provenance.py.

The module exists to make one specific mistake impossible, so most of these tests are that
mistake, reproduced. Each names the failure it catches and how to falsify it.

Everything here is built from synthetic signals rather than from the tree's audio: a test
that needs ffmpeg and a 17 MB bench cannot run on every commit, and the properties being
guarded are properties of the arithmetic, not of any particular bed.

TWENTY-ONE MUTATIONS, TWENTY CAUGHT, AND THE SURVIVOR IS RECORDED HERE RATHER THAN HIDDEN.
Replacing `locate`'s exact re-scoring of the winning lag with the approximate score the lag
search ranked by passes every test above, because on well-conditioned synthetic input the
two agree to about 1e-12. The re-scoring earns its place only on ill-conditioned real audio
-- a 91-second recording whose running sums are large enough to eat the significant digits
-- and that file is not in this repository and will not be. It is kept as defence in depth
behind the variance floor, which IS tested both ways. *An untestable guard is worth keeping
and worth saying is untestable; it is not worth pretending the suite covers it.*
"""
import importlib.util
import math
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MOD = ROOT / "ui" / "board_v2" / "sfx_lab" / "provenance.py"


def _load():
    spec = importlib.util.spec_from_file_location("_provenance", MOD)
    if spec is None or spec.loader is None:                       # pragma: no cover
        pytest.skip("cannot import provenance.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["_provenance"] = m
    spec.loader.exec_module(m)
    return m


P = _load()
SR = 48000


def _transient(n, seed):
    """Noise under a fast decay -- the material that makes a 3 ms error catastrophic."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    return x * np.exp(-np.linspace(0, 12, n))


def _source_with_event(at_s, length_s=0.25, total_s=3.0, seed=1):
    src = np.zeros(int(total_s * SR))
    n = int(length_s * SR)
    i = int(at_s * SR)
    src[i:i + n] = _transient(n, seed)
    return src, i, n


def test_locate_finds_the_lag_to_the_sample():
    """The base claim: a copied stretch is found where it actually is.

    Falsified by any change that makes the search approximate -- a coarse lag grid, a
    decimated correlation, normalising globally instead of per lag.
    """
    src, i, n = _source_with_event(1.2345)
    window = src[i:i + n].copy()
    p = P.locate(window, src, SR)
    assert p is not None
    assert p.offset == i, "found %d, material is at %d" % (p.offset, i)
    assert p.r > 0.999


def test_a_three_millisecond_error_destroys_the_correlation():
    """THE TRAP ITSELF, stated as a measurement rather than a warning.

    This is why the module never returns a bare offset to slice with. If this test ever
    passes with a small difference, transient material has stopped being transient and the
    whole design rationale needs re-reading.
    """
    src, i, n = _source_with_event(1.2345)
    window = src[i:i + n].copy()
    at_right = np.corrcoef(window, src[i:i + n])[0, 1]
    off = i + int(round(0.003 * SR))
    at_wrong = np.corrcoef(window, src[off:off + n])[0, 1]
    assert at_right > 0.99
    assert abs(at_wrong) < 0.3, (
        "3 ms off still correlates at %.3f; the trap this module guards is not reproducible "
        "on this material and the test needs harder transients" % at_wrong)


def test_a_quiet_exact_copy_beats_a_loud_unrelated_burst():
    """Normalisation is per lag, so loudness cannot win a match.

    The source holds a quiet exact copy of the window and, elsewhere, an unrelated burst
    forty times louder. Correlation normalised over the whole source -- or by any constant
    -- reduces to a raw dot product and picks the burst. Falsified by normalising globally,
    which is the mutation this test exists for.
    """
    n = int(0.2 * SR)
    sig = _transient(n, 21)
    src = np.zeros(3 * SR)
    quiet_at, loud_at = int(0.4 * SR), int(2.0 * SR)
    src[quiet_at:quiet_at + n] = 0.01 * sig
    src[loud_at:loud_at + n] = 40.0 * _transient(n, 22)
    p = P.locate(sig, src, SR)
    assert p.offset == quiet_at, (
        "matched at %.4f s where the quiet exact copy is at %.4f s; loudness won"
        % (p.offset / SR, quiet_at / SR))
    assert p.r > 0.999


def test_the_placement_carries_the_aligned_samples_not_just_an_offset():
    """The design guarantee. A caller must never have to slice by hand.

    Falsified by dropping `aligned` from Placement, or by filling it from the window
    instead of the source.
    """
    src, i, n = _source_with_event(0.77)
    window = src[i:i + n].copy()
    p = P.locate(window, src, SR)
    assert len(p.aligned) == len(window)
    assert np.array_equal(p.aligned, src[i:i + n])
    assert not np.shares_memory(p.aligned, src), (
        "aligned must be a copy; a view into the source mutates under the caller")


def test_fit_recovers_a_known_gain_and_leaves_nothing_over():
    """A clean copy at a known gain fits that gain, and the residual matches the prediction.

    Falsified by fitting against the raw source rather than the aligned slice, or by
    dropping the mean-removal from the correlation that feeds `predicted_frac`.
    """
    src, i, n = _source_with_event(0.9)
    g = 0.5
    window = g * src[i:i + n]
    p = P.locate(window, src, SR)
    f = P.fit(window, p)
    assert abs(f.gain - g) < 1e-9
    assert abs(f.gain_db - 20 * math.log10(g)) < 1e-9
    assert f.residual_frac < 1e-9
    assert f.predicted_frac < 1e-3


def test_fit_flags_a_misaligned_slice_by_disagreeing_with_its_own_prediction():
    """The check that caught the arithmetic slice three times, now automatic.

    A Placement pointing at the wrong samples produces a residual far above sqrt(1 - r^2).
    Falsified by computing `predicted_frac` from the fit instead of from the correlation --
    then the two agree by construction and the disagreement can never appear.
    """
    src, i, n = _source_with_event(1.5)
    window = src[i:i + n].copy()
    good = P.locate(window, src, SR)
    off = i + int(round(0.003 * SR))
    bad = P.Placement(r=good.r, start=off, end=off + n, offset=off,
                      aligned=src[off:off + n].copy(), sr=SR)
    f_good, f_bad = P.fit(window, good), P.fit(window, bad)
    assert f_good.residual_frac <= f_good.predicted_frac + 0.05
    assert f_bad.residual_frac > f_bad.predicted_frac + 0.10, (
        "a 3 ms misalignment left residual %.3f against predicted %.3f and would not be "
        "flagged" % (f_bad.residual_frac, f_bad.predicted_frac))


def test_check_stated_offset_reports_the_drift_rather_than_hiding_it():
    """A covering note's placement is a claim, and the drift against the search is evidence.

    Falsified by returning only the searched result, or by silently snapping the stated
    offset to the searched one.
    """
    src, i, n = _source_with_event(2.0)
    window = src[i:i + n].copy()
    best, at_stated, drift_ms = P.check_stated_offset(window, src, SR, i / SR)
    assert abs(drift_ms) < 1e-6 and at_stated > 0.99
    wrong_s = (i + int(round(0.003 * SR))) / SR
    best, at_stated, drift_ms = P.check_stated_offset(window, src, SR, wrong_s)
    assert abs(at_stated) < 0.3
    assert abs(drift_ms + 3.0) < 0.05, "drift reported as %.3f ms, expected -3" % drift_ms


def test_runs_ignores_the_crumbs_vorbis_leaves_behind():
    """Only exact digital zero separates runs, and sub-threshold fragments are dropped.

    Falsified by using an amplitude threshold, or by dropping the min-length filter -- the
    sickle stem has 452 runs in the stem and 17 in the encode, and a tool that counts the
    encoder's ringing as gestures reports forty placements as four hundred.
    """
    x = np.zeros(2 * SR)
    x[1000:1000 + int(0.2 * SR)] = _transient(int(0.2 * SR), 3)
    x[40000:40000 + 100] = 1e-6          # 2 ms of signal: too short to be a gesture
    # A long, very quiet stretch IS material -- a fade tail, or dither under a decay. Exact
    # digital zero keeps it; any amplitude threshold throws it away and under-reports the
    # edit. 1e-10 sits below the thresholds a reasonable person would reach for.
    x[70000:70000 + int(0.3 * SR)] = 1e-10
    got = P.runs(x, SR, min_s=0.050)
    assert len(got) == 2, "expected two runs, got %r" % (got,)
    assert got[0][0] == 1000
    assert got[1][0] == 70000, (
        "the quiet 300 ms stretch was dropped; runs() is using a threshold, not zero")


def test_regions_collapse_many_placements_onto_the_little_source_they_use():
    """Forty placements can come from two places, and that is the reportable fact.

    Falsified by merging with a gap tolerance large enough to join genuinely separate
    regions, which would overstate how much of a recording was used.
    """
    mk = lambda a, b: P.Placement(r=1.0, start=int(a * SR), end=int(b * SR),  # noqa: E731
                                  offset=int(a * SR), aligned=np.zeros(1), sr=SR)
    # 2.2 -> 2.4 is a fifth of a second clear of the block that ends at 2.0, and must stay
    # its own region: a merge tolerance generous enough to swallow it would overstate how
    # much of the recording was used and understate how many places it came from.
    merged = P.regions([mk(0.0, 1.0), mk(0.5, 1.5), mk(4.0, 4.5), mk(1.5, 2.0),
                        mk(2.2, 2.4)], SR)
    assert merged == [(0.0, 2.0), (2.2, 2.4), (4.0, 4.5)], merged


def test_disjoint_separates_a_near_miss_from_an_overlap():
    """Two beds from one upload: do they share a sample, and how close do they come?

    Falsified by treating abutting regions as overlapping, or by reporting the closest gap
    only when there are no overlaps -- the straw_workers pair miss by 37.8 ms and that
    number is the finding.
    """
    a = [(0.0, 1.0), (2.0, 3.0)]
    b = [(1.5, 1.9), (5.0, 6.0)]
    ov, closest = P.disjoint(a, b)
    assert ov == []
    assert abs(closest - 0.1) < 1e-9, closest

    ov, closest = P.disjoint([(0.0, 1.0), (4.0, 5.0)], [(0.5, 2.0)])
    assert len(ov) == 1 and abs(ov[0][4] - 0.5) < 1e-9, ov
    assert closest is not None and abs(closest - 2.0) < 1e-9, (
        "the closest gap must still be reported when some pair overlaps, got %r" % (closest,))

    touching, _ = P.disjoint([(0.0, 1.0)], [(1.0, 2.0)])
    assert touching == [], "regions that abut at a sample do not overlap"


def test_a_correlation_never_exceeds_one_however_quiet_the_source_gets():
    """THE BUG THIS MODULE SHIPPED WITH, and the suite above did not catch.

    The per-lag variance comes from a running-sum identity that subtracts two large numbers
    to leave a small one. Over a long source with a DC offset the cumulative sums are large
    enough that the cancellation destroys the result wherever the source is nearly — but not
    exactly — silent, and dividing by its square root returns correlations above 1. On the
    first real bed it reported r = −3.4152 and r = −2.1443 on 51 ms windows, and invented two
    source regions out of them.

    Exact digital silence was always caught, which is why the first tests passed: the hole is
    specifically NEAR-silence. Falsified by removing the relative variance floor from
    `normalise`.

    THE DEFECT IS TESTED WHERE IT LIVES rather than through `locate`. Two attempts to
    reproduce it from synthetic audio both passed against the broken code -- the failure
    needs a particular ratio of total energy to window energy that is easy to miss by
    guessing and was only ever produced by a real recording. Feeding `normalise` the
    variance array the arithmetic actually hands it is deterministic, needs no audio, and
    tests the guard that matters. *Two failed attempts at a reproduction are the reason the
    guard was factored out of `locate` at all.*
    """
    nw = 5.0
    num = np.array([3.0, 0.5, -2.0, 0.1, 1.0])
    # what the running-sum identity really returns near silence: noise either side of zero,
    # a negative, and one honest loud window. 2.9e-10 is the value measured on the raven
    # source at the lag that produced r = -3.4152.
    var = np.array([4.0, -4.7e-13, 2.9e-10, 0.0, -1e-12])
    floor = 4.2e-9          # a window's energy at 1e-9 of the source's mean square
    r = P.normalise(num, nw, var, floor)
    assert np.all(np.isfinite(r)), r
    assert np.all(np.abs(r) <= 1.0), "normalise returned %r, which contains non-correlations" % r
    assert abs(r[0] - 3.0 / (nw * 2.0)) < 1e-12, "the honest lag was not left alone"
    assert np.all(r[1:] == 0.0), "lags with no usable variance must score zero, got %r" % r[1:]
    # AND THE FLOOR MUST BE THE REASON, not the sign test: 2.9e-10 is positive and finite,
    # so an absolute epsilon of 1e-20 lets it through -- and then the guard fires, loudly,
    # instead of returning a clipped number nobody would question. Both halves matter.
    with pytest.raises(AssertionError, match="not a correlation"):
        P.normalise(np.array([-2.0]), nw, np.array([2.9e-10]), 1e-20)
    # NaN in means the lag is unusable, not that the answer is unusable
    assert np.all(np.isfinite(P.normalise(np.array([1.0]), 1.0, np.array([np.nan]), floor)))


def test_a_window_with_no_energy_cannot_win_however_perfectly_it_correlates():
    """The variance floor, tested through `locate` and on the semantics rather than the
    arithmetic: *a stretch of source holding essentially nothing cannot be the answer.*

    The source carries two copies of the window. One at half amplitude with noise on it,
    which is the honest match at r ≈ 0.9. The other is a PERFECT copy scaled by 1e-5, about
    -100 dBFS -- correlation 1.0000, energy ten orders of magnitude down. Correlation is
    scale-invariant, so without an energy floor the ghost wins outright and the probe
    reports a placement in a region that is, to any ear and any meter, silence.

    THE GHOST'S LEVEL IS CHOSEN, NOT ARBITRARY. At 1e-6 this test passed against a floor of
    zero: that quiet, the running-sum variance is itself rounding noise and the ghost loses
    by accident rather than by the guard. It has to sit above the arithmetic's noise and
    below the energy floor, which is the band the floor exists to govern.

    Falsified by setting `locate`'s floor to zero, which is the state this module shipped
    in. It is also the companion to the normalise test above: that one guards the
    arithmetic, this one guards the meaning.
    """
    rng = np.random.default_rng(5)
    n = int(0.1 * SR)
    window = _transient(n, 41)
    src = rng.standard_normal(3 * SR) * 0.3
    honest, ghost = int(1.0 * SR), int(2.0 * SR)
    src[honest:honest + n] = 0.5 * window + rng.standard_normal(n) * 0.05
    src[ghost:ghost + n] = 1e-5 * window
    p = P.locate(window, src, SR)
    assert p.offset == honest, (
        "matched the 1e-5 ghost at %.3f s instead of the real copy at %.3f s"
        % (p.offset / SR, honest / SR))
    assert 0.8 < p.r < 1.0, p.r
    # And the reported r is the exact Pearson against the samples handed back, not the
    # approximate score the lag search ranked by.
    w = window - window.mean()
    a = p.aligned - p.aligned.mean()
    exact = float(w @ a) / math.sqrt(float(w @ w) * float(a @ a))
    assert abs(p.r - exact) < 1e-12, "reported %.12f, exact %.12f" % (p.r, exact)


def test_a_source_buried_under_subsonics_is_flagged_and_rescued_by_a_high_pass():
    """Inaudible energy defeats a normalised correlation, and the module says so.

    Cross-correlation divides by total energy, so a source carrying heavy sub-20 Hz rumble is
    measured mostly on the rumble. Cinetony's tawny owl is **97.76%** sub-20 Hz and its hoot is
    0.22% of the file; probed raw against a stem whose chain had removed the rumble it scored
    0.0337 against a control at 0.0308 and was filed as not corroborated. High-passed at 100 Hz
    the same comparison returns 0.9974. This reproduces that shape: an audible event buried
    under rumble forty times its amplitude.

    Falsified by making `highpass` a no-op, or by dropping `subsonic_fraction` -- the diagnosis
    is the useful half, because a score of 0.03 looks like a wrong source and not like a
    measurement problem.
    """
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    call = np.sin(2 * np.pi * 500 * t) * np.exp(-6 * t)      # the audible part
    rumble = 40.0 * np.sin(2 * np.pi * 7 * t)                # inaudible, and enormous
    src = np.zeros(4 * SR)
    at = int(1.5 * SR)
    src[at:at + n] = call + rumble
    stem = 0.5 * call                                        # the chain kept only the call

    assert P.subsonic_fraction(src, SR) > 0.9, P.subsonic_fraction(src, SR)
    assert P.subsonic_fraction(stem, SR) < 0.01

    raw = P.locate(stem, src, SR)
    hp = P.locate(P.highpass(stem, SR), P.highpass(src, SR), SR)
    assert abs(raw.r) < 0.3, "raw probe scored %.4f; the rumble is not dominating" % raw.r
    assert abs(hp.r) > 0.9, "high-passed probe scored %.4f, expected a clean match" % hp.r
    # Within a couple of milliseconds: a brick-wall filter smears the onset of a decaying
    # tone, so demanding the exact sample here would be testing the filter, not the match.
    assert abs(hp.offset - at) <= int(0.002 * SR), (
        "matched at %d, material is at %d" % (hp.offset, at))


def test_locate_refuses_rather_than_guesses_when_it_cannot_search():
    """Degenerate inputs return None instead of a confident wrong answer.

    Falsified by returning a Placement for a silent window, which would correlate with
    nothing and report r = 0 at lag 0 as though that meant something.
    """
    src, _, _ = _source_with_event(1.0)
    assert P.locate(np.zeros(1000), src, SR) is None
    assert P.locate(np.array([]), src, SR) is None
    # A window longer than the source has nowhere to sit. The window here is real signal,
    # not a constant: a flat window is caught by the zero-variance guard instead and would
    # let a padding mutation through.
    assert P.locate(_transient(5000, 11), _transient(500, 12), SR) is None


def test_mono_takes_the_mid_and_not_the_first_channel():
    """A hard-panned stem keeps its material in the mid.

    Falsified by indexing channel 0, which is the same class of error that once reported a
    36-second file as a single 400 ms block.
    """
    n = 2000
    sig = _transient(n, 7)
    quiet = np.stack([sig * 0.01, sig], axis=1)
    got = P.mono(quiet)
    assert np.corrcoef(got, sig)[0, 1] > 0.999
    assert got.std() > 0.4 * sig.std(), "mid collapsed towards the quiet channel"
