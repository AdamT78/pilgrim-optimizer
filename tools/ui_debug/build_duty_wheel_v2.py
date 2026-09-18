"""The v2 duty wheel: nine faces built as vector geometry, and the layout JSON they go into.

This writes `duty_wheel_v2_layout.json`. It is the parametric SOURCE for that file -- a live
script, not a `prototype_sources/*.py.txt` reference copy -- because the nine outlines are not
the base. The base is the dozen constants below, and at least one of them is still open (see
THE ASPECT, further down).

v2 does not replace the circular wheel. `duty_wheel_layout.json`, `render_duty_wheel.py` and
`prototypes/duty_wheel.html` are untouched and still describe what the game draws today.

WHAT IT IS

A hub and eight spokes on a true ellipse. The eight ring faces are the quads between the spokes;
the ninth is the hub. Every face is inset by half the frame width along each of its edges and
trimmed where the insets cross, so:

  * the channel between two faces is exactly 2 * D_FRAME wide, because both neighbours give up
    D_FRAME on the SAME curve rather than each being shrunk on its own;
  * the outer edge IS the ellipse, by construction, not by clipping something to it;
  * the wheel is MIRRORED about both axes, never rotated. North and south are each symmetric
    left to right, west is the flip of east, the lower three are the flip of the upper three.
    Two spokes are authored and the other six are their mirrors, so the symmetry is exact.

Nothing here is traced from a raster. An earlier pass did trace a generated sheet, and the
outlines it produced were as good as the ink in the picture -- which is to say uneven in a way
no amount of smoothing downstream could fix.

POSITIONS, NOT DUTIES

The nine entries are named by WHERE THEY ARE, not by which duty stands on them. Duty tiles are
shuffled at setup, so a duty's square is an arrangement and not a fact -- the same point
`gen_duty_grid.DUTY_NAMES` makes about its own list. `index` is the 0..8 grid square, top-left
to bottom-right, which is what `gen_duty_grid`'s `cells=` argument already speaks, so a real
game's board maps onto these without renaming anything. The centre is the City.

THE ASPECT

ASPECT is 1.778 and that number is NOT settled. Measured against the tile that ships today
(mean 63,148 units^2 of a square 1000 box, taken off `laid_shapes()` rather than off TILE_FRAC):

  * at today's canvas of 1600 the wheel is width-bound at 877.8 units, so a landscape wheel
    keeps the width and throws the height away -- these faces come out at 69% of a shipped tile
    on both measured screens. A LOSS.
  * at a canvas of 2283, which is where `gen_screen_budget.best_canvas` puts the crossing for
    this aspect, they come out at 2.19x -- for a 3.5% drop in stage scale on the MacBook and
    none at all on the ultrawide.

So the shape work does not pay for itself until the canvas moves with it. Change ASPECT here and
re-run; everything downstream follows.

Run from the repo root:

    python3 tools/ui_debug/build_duty_wheel_v2.py
    python3 tools/ui_debug/build_duty_wheel_v2.py --aspect 1.5 \
        --out duty_wheel_v2_1500_layout.json

The second is how duty_wheel_v2_1500_layout.json is made, and it has to stay that way: that file
is read by generate_wheel_space_check.py, and a layout nothing can regenerate is a layout that
quietly becomes wrong the first time anything else here moves.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "duty_wheel_v2_layout.json"
VERSION = 2

# ---------------------------------------------------------------- parameters

BOX = 1000.0
MARGIN = 5.0                        # bare ground outside the ellipse

# parse_known_args, not parse_args: these constants are needed at IMPORT time, so the parse runs
# on import too, and under pytest sys.argv belongs to pytest. Unknown flags are ignored rather
# than fatal.
_ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
_ap.add_argument("--aspect", type=float, default=1.778, help="wheel width : height")
_ap.add_argument("--out", default=None, help="layout file to write")
ARGS = _ap.parse_known_args()[0]

ASPECT = ARGS.aspect                # see THE ASPECT above; 1.778 is the default, not a verdict

# The centre face was drawn at 156.0 x 107.0 against the rim it had at aspect 1.778. Held as a
# PROPORTION of the rim rather than in units, so changing ASPECT rescales it instead of leaving
# a hub the wrong size in a taller box. Written as a ratio against that reference rim, so at
# 1.778 it comes back to exactly 156.0 x 107.0 and the layout does not move.
REF_RX, REF_RY = 495.0, 276.2       # the rim at aspect 1.778
HUB_REF_X, HUB_REF_Y = 156.0, 107.0
HUB_LOBE = 0.040                    # 8-fold swell peaking on the spokes
HUB_BULGE = 0.018                   # slower wander on top of it

D_FRAME = 3.0                       # half the channel: the frame reads 2 * D_FRAME
D_HUB = 4.7                         # half the channel around the centre
D_RIM = 3.0                         # inset from the ellipse
TAPER = 0.14                        # fraction of a spoke spent blending hub ring -> frame

ROUND_RIM = 18.0                    # corner radius where a spoke meets the rim
ROUND_HUB = 12.0                    # corner radius where a spoke meets the centre
N_CTRL = 150                        # cubic bezier segments per face; MUST stay even, see anchor()
SEED = 20260917
WOBBLE = 0.038                      # spoke wander, as a fraction of spoke length

# Spoke directions, degrees, 0 = east and increasing clockwise on screen.
#
# EQUAL 45 degree steps, because on an ellipse equal parametric angle means equal sector AREA --
# that one choice is what keeps the faces within about a tenth of each other while still reading
# as three across the top.
#
# The offset is 22.5, and it is the only offset that works. To be closed under BOTH mirrors an
# equal-spaced set has to start at 0 or at 22.5; starting at 0 puts a spoke due north and due
# east, which splits the north face in two and leaves no east face at all. At 22.5 the faces
# instead sit centred on 270, 0, 90, 180 and the four diagonals.
SPOKES = [202.5, 247.5, 292.5, 337.5, 22.5, 67.5, 112.5, 157.5]

# The face lying between spoke k and spoke k+1, by position.
RING = ["north_west", "north", "north_east", "east",
        "south_east", "south", "south_west", "west"]
HUB = "centre"
# 0..8 grid squares, top-left to bottom-right -- `gen_duty_grid`'s `cells=` order.
ORDER = ["north_west", "north", "north_east",
         "west", "centre", "east",
         "south_west", "south", "south_east"]

DRAWN = ("north_west", "north", "west", "centre")
MIRRORS = [("north_east", "north_west", "MV"),
           ("east", "west", "MV"),
           ("south_west", "north_west", "MH"),
           ("south", "north", "MH"),
           ("south_east", "north_east", "MH")]
# north, south, east, west and the centre are each their own mirror. That falls out of the
# construction rather than being imposed afterwards, and verify() checks it.
SELF = {"north": "MV", "west": "MH", "centre": "MV"}

BOX_H = round(BOX / ASPECT, 1)
CX, CY = BOX / 2.0, BOX_H / 2.0
RX, RY = BOX / 2.0 - MARGIN, BOX_H / 2.0 - MARGIN
HUB_RX, HUB_RY = HUB_REF_X * (RX / REF_RX), HUB_REF_Y * (RY / REF_RY)
N_PT = 700

rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- the two rings


def mirror_v(P):
    """Flip left to right about the vertical axis."""
    return np.c_[2 * CX - P[:, 0], P[:, 1]]


def mirror_h(P):
    """Flip top to bottom about the horizontal axis."""
    return np.c_[P[:, 0], 2 * CY - P[:, 1]]


MIRROR = {"MV": mirror_v, "MH": mirror_h}

# The hub outline wanders off its ellipse by EVEN cosines with NO phase. Both conditions are
# forced: cos(m*theta) survives the left-right flip only when m is even, and it survives the
# top-bottom flip only with zero phase. Any sine term, or any phase, and the centre stops being
# its own mirror.
HUB_H = ((2, 0.38), (4, -0.26), (6, 0.14))


def hub_point(deg):
    """The centre face. A CURVE, with no straight runs and no corners anywhere.

    It was a real octagon once -- eight flats meeting at eight corners on the spokes. The rhythm
    was right and the corners were not, so the polygon is gone and the rhythm is kept by a single
    8-fold swell instead: -cos(8t) peaks exactly where the spokes land, which is where the
    octagon put its corners, but it arrives there smoothly. Nothing here is piecewise, so there
    is nothing left to round off.
    """
    t = np.radians(np.asarray(deg, float))
    g = sum(a * np.cos(m * t) for m, a in HUB_H)
    f = 1.0 - HUB_LOBE * np.cos(8 * t) + HUB_BULGE * g
    return np.stack([CX + HUB_RX * f * np.cos(t), CY + HUB_RY * f * np.sin(t)], axis=-1)


def rim_point(deg):
    t = np.radians(np.asarray(deg, float))
    return np.stack([CX + RX * np.cos(t), CY + RY * np.sin(t)], axis=-1)


def span(a, b):
    """a to b the short way round, as degrees."""
    while b - a > 180.0:
        b -= 360.0
    while b - a < -180.0:
        b += 360.0
    return np.linspace(a, b, N_PT)


def hub_arc(a, b):
    return hub_point(span(a, b))


def rim_arc(a, b):
    return rim_point(span(a, b))

# ---------------------------------------------------------------- the spokes


def author_spoke(k):
    A, B = hub_point(SPOKES[k]), rim_point(SPOKES[k])
    L = float(np.hypot(*(B - A)))
    t = np.linspace(0.0, 1.0, N_PT)
    tan = (B - A) / L
    nrm = np.array([-tan[1], tan[0]])
    amp = WOBBLE * L
    w = sum(rng.uniform(-amp, amp) * np.sin(m * math.pi * t) / m for m in (1, 2, 3))
    return A + t[:, None] * (B - A) + w[:, None] * nrm


# Only spokes 2 (292.5) and 3 (337.5) are drawn. Under the two mirrors each lands on three more,
# which covers all eight.
SPOKE = {}
for _k, (_mv, _mh, _both) in ((2, (1, 5, 6)), (3, (0, 4, 7))):
    _P = author_spoke(_k)
    SPOKE[_k] = _P
    SPOKE[_mv] = mirror_v(_P)
    SPOKE[_mh] = mirror_h(_P)
    SPOKE[_both] = mirror_h(mirror_v(_P))

# ---------------------------------------------------------------- faces

HUB_ARC, SPOKE_OUT, RIM_ARC, SPOKE_IN = range(4)


def widths(kind, n):
    """The inset at each point of an edge. The heavy ring round the centre grows out of the
    ordinary frame over TAPER of each spoke instead of stepping at the junction."""
    if kind == HUB_ARC:
        return np.full(n, D_HUB)
    if kind == RIM_ARC:
        return np.full(n, D_RIM)
    t = np.linspace(0.0, 1.0, n)
    if kind == SPOKE_IN:                       # runs rim -> hub, so the hub end is t = 1
        t = 1.0 - t
    u = np.clip(t / TAPER, 0.0, 1.0)
    s = u * u * (3.0 - 2.0 * u)                # smoothstep
    return D_HUB + (D_FRAME - D_HUB) * s


def inside(poly, pt):
    x, y = pt
    xs, ys = poly[:, 0], poly[:, 1]
    xs2, ys2 = np.roll(xs, -1), np.roll(ys, -1)
    hit = ((ys > y) != (ys2 > y)) & (x < (xs2 - xs) * (y - ys) / (ys2 - ys + 1e-12) + xs)
    return bool(hit.sum() % 2)


def inward(P, poly):
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.c_[-T[:, 1], T[:, 0]]
    m = len(P) // 2
    if not inside(poly, P[m] + 0.6 * N[m]):
        N = -N
    return N


def cross_point(A, B):
    """Where the tail of A crosses the head of B. Every corner of every cell here is convex,
    so this is a plain segment crossing - there is no offset self-intersection to unpick."""
    ia0 = max(0, len(A) - 220)
    ib1 = min(len(B), 220)
    for i in range(len(A) - 2, ia0, -1):
        p, r = A[i], A[i + 1] - A[i]
        for j in range(ib1 - 1):
            q, s = B[j], B[j + 1] - B[j]
            den = r[0] * s[1] - r[1] * s[0]
            if abs(den) < 1e-12:
                continue
            t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den
            u = ((q[0] - p[0]) * r[1] - (q[1] - p[1]) * r[0]) / den
            if -0.02 <= t <= 1.02 and -0.02 <= u <= 1.02:
                return p + t * r, i, j + 1
    d = np.linalg.norm(A[ia0:, None, :] - B[None, :ib1, :], axis=2)
    i, j = np.unravel_index(np.argmin(d), d.shape)
    return 0.5 * (A[ia0 + i] + B[j]), ia0 + i, j


def build_cell(k):
    """The cell between spoke k and spoke k+1, inset and trimmed, plus where its four corners
    ended up - the corners are the only places the rounding is allowed to touch."""
    a, b = SPOKES[k], SPOKES[(k + 1) % 8]
    raw = [(HUB_ARC, hub_arc(a, b)),
           (SPOKE_OUT, SPOKE[(k + 1) % 8]),
           (RIM_ARC, rim_arc(b, a)),
           (SPOKE_IN, SPOKE[k][::-1])]
    poly = np.vstack([P for _, P in raw])
    segs = [P + widths(kind, len(P))[:, None] * inward(P, poly) for kind, P in raw]
    hits = [cross_point(segs[i], segs[(i + 1) % 4]) for i in range(4)]
    out, corners = [], []
    n = 0
    for i in range(4):
        piece = segs[i][hits[(i - 1) % 4][2]: hits[i][1] + 1]
        out.append(piece)
        n += len(piece)
        corners.append(n)                       # index of the corner point about to be added
        out.append(hits[i][0][None, :])
        n += 1
    # corner i sits between segment i and segment i+1: hub, rim, rim, hub
    return np.vstack(out), corners, [ROUND_HUB, ROUND_RIM, ROUND_RIM, ROUND_HUB]


def round_corners(P, corners, radii):
    """Round the four corners and nothing else.

    Smoothing the whole outline would round the corners, but it would also drag the rim arc in
    off its ellipse and flatten the hub facets, which is where the even 6.00 and 9.40 channels
    come from. So: smooth, then blend the smoothed curve back in only within a couple of radii
    of each corner, and leave the rest of the outline exactly where the offset put it.
    """
    L = np.r_[0.0, np.cumsum(np.hypot(*np.diff(np.r_[P, P[:1]], axis=0).T))]
    total = L[-1]
    Q = resample(P, 4000)
    s = np.arange(4000) / 4000.0 * total

    # All four blends come off the SAME starting curve and are added, never applied one after
    # another. Chaining them is not commutative, and a face's mirror visits its corners in the
    # opposite order - which quietly cost 0.9 units of symmetry until the sum replaced it.
    ws, ss = [], []
    for i, r in zip(corners, radii):
        d = np.abs(((s - L[i] + total / 2) % total) - total / 2)
        ws.append(np.exp(-0.5 * (d / (1.2 * r)) ** 2))
        ss.append(smooth(Q, r))
    W = np.sum(ws, axis=0)
    scale = np.where(W > 1.0, 1.0 / W, 1.0)          # keep it a convex blend where they overlap
    return Q + sum(((w * scale)[:, None] * (S - Q)) for w, S in zip(ws, ss))


def build_hub():
    P = hub_point(np.linspace(0.0, 360.0, 8 * N_PT, endpoint=False))
    poly = P
    return P + D_HUB * inward(P, poly)

# ---------------------------------------------------------------- curves out


def resample(P, n):
    d = np.r_[0.0, np.cumsum(np.hypot(*np.diff(np.r_[P, P[:1]], axis=0).T))]
    t = np.linspace(0, d[-1], n, endpoint=False)
    Q = np.r_[P, P[:1]]
    return np.c_[np.interp(t, d, Q[:, 0]), np.interp(t, d, Q[:, 1])]


def smooth(P, units):
    """Gaussian along the closed curve. The curve is already smooth, so this only rounds the
    four corners - it is the fillet, applied where a fillet is needed and nowhere else."""
    step = np.hypot(*np.diff(np.r_[P, P[:1]], axis=0).T).mean()
    sigma = max(1.0, units / step)
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.r_[P[-r:], P, P[:r]]
    return np.c_[np.convolve(pad[:, 0], k, "same")[r:-r],
                 np.convolve(pad[:, 1], k, "same")[r:-r]]


def anchor(P, axis):
    """Start a closed curve exactly where it crosses its own axis of symmetry.

    The curve coming out of build_cell is already symmetric to a hundredth of a unit, but the
    POLYGON that samples it need not be: mirror the shape and the 150 sample points land in
    different places, which showed up as a 1.0 unit difference that was sampling phase and not
    geometry. Starting on the axis, with an even sample count, puts sample j and sample n-j on
    opposite sides of it, so the sampled polygon is symmetric too.
    """
    v = P[:, 0] - CX if axis == "MV" else P[:, 1] - CY
    cross = np.nonzero(np.sign(v) != np.sign(np.roll(v, -1)))[0]
    other = P[cross, 1] if axis == "MV" else P[cross, 0]
    i = int(cross[np.argmin(other)])              # the crossing nearest the top, or the left
    j = (i + 1) % len(P)
    X = P[i] + v[i] / (v[i] - v[j]) * (P[j] - P[i])
    return np.r_[X[None, :], P[j:], P[:j]]



def build() -> dict:
    """Every face as a closed polygon of N_CTRL points, keyed by position."""
    assert N_CTRL % 2 == 0, "anchor() needs an even sample count to keep a face its own mirror"
    polys = {}
    for name in DRAWN:
        if name == HUB:
            fine = smooth(resample(build_hub(), 4000), 2.0)
        else:
            fine = round_corners(*build_cell(RING.index(name)))
        if name in SELF:
            fine = anchor(fine, SELF[name])
        polys[name] = resample(fine, N_CTRL)
    for dst, src, m in MIRRORS:                # exact, not approximate
        polys[dst] = MIRROR[m](polys[src])
    return polys

# ---------------------------------------------------------------- checks


def area(P):
    n = len(P)
    return 0.5 * abs(sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1]
                         for i in range(n)))


def gap(A, B):
    return float(np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2).min())


def shape_dist(A, B):
    """How far two OUTLINES are apart, as shapes. Not a point-by-point difference: the curves
    may start at different places and run in opposite directions, which says nothing about
    whether they are the same shape."""
    A, B = resample(A, 3000), resample(B, 3000)
    d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
    return float(max(d.min(axis=1).max(), d.min(axis=0).max()))


def longest_flat(P, tol=0.3):
    """The longest run of an outline that stays within tol of a straight line, in board units.

    Curvature is the wrong test for "are the straight edges gone": a smooth curve still has
    isolated points of zero curvature where it changes sense, and one such point is not an EDGE.
    What matters is how far the outline can travel while staying flat, so measure that. For
    scale, a plain circle the size of this hub measures about 17 at the same tolerance.
    """
    n = 1200
    Q = resample(P, n)
    step = np.hypot(*np.diff(np.r_[Q, Q[:1]], axis=0).T).mean()
    best = 0
    for i in range(n):
        j = 2
        while j < n // 2:
            seg = np.array([Q[(i + k) % n] for k in range(j + 1)])
            a, b = seg[0], seg[-1]
            d = b - a
            L = float(np.hypot(*d))
            if L < 1e-9:
                break
            u = d / L
            r = seg - a
            if np.abs(u[0] * r[:, 1] - u[1] * r[:, 0]).max() > tol:
                break
            j += 1
        best = max(best, j - 1)
    return best * step


def verify(polys: dict) -> dict:
    """The invariants worth guarding. These are what rot silently: a wheel that is three per cent
    asymmetric, or whose channel has drifted, still looks like a wheel."""
    A = np.vstack([polys[n] for n in ORDER])
    ring = [gap(polys[RING[k]], polys[RING[(k + 1) % 8]]) for k in range(8)]
    hub = [gap(polys[HUB], polys[n]) for n in RING]
    ar = [area(polys[n]) for n in RING]
    return {
        "max_radial_in_ellipse": round(float(
            np.hypot((A[:, 0] - CX) / RX, (A[:, 1] - CY) / RY).max()), 4),
        "frame_between_faces": [round(min(ring), 2), round(max(ring), 2)],
        "frame_around_centre": [round(min(hub), 2), round(max(hub), 2)],
        "ring_area_spread_pct": round(100 * (max(ar) / min(ar) - 1), 1),
        "mirror_error": round(max(
            shape_dist(polys[d], MIRROR[m](polys[s])) for d, s, m in MIRRORS), 4),
        "self_mirror_error": round(max(
            shape_dist(polys[n], MIRROR[m](polys[n]))
            for n, m in (("north", "MV"), ("south", "MV"), ("east", "MH"),
                         ("west", "MH"), ("centre", "MV"), ("centre", "MH"))), 4),
        "centre_longest_straight_run": round(longest_flat(polys[HUB]), 1),
    }

# ---------------------------------------------------------------- out


def beziers(P):
    n = len(P)
    seg = [(P[i] + (P[(i + 1) % n] - P[i - 1]) / 6.0,
            P[(i + 1) % n] - (P[(i + 2) % n] - P[i]) / 6.0,
            P[(i + 1) % n]) for i in range(n)]
    return "M %.2f %.2f " % tuple(P[0]) + " ".join(
        "C %.2f %.2f %.2f %.2f %.2f %.2f" % (c1[0], c1[1], c2[0], c2[1], p[0], p[1])
        for c1, c2, p in seg) + " Z"


def polyline(P):
    """The same outline as M/L/Z. `gen_duty_grid._points()` parses only M, L and Z, so this is
    what that side can read until it is taught to take a C."""
    return "M " + " L ".join("%.2f %.2f" % (x, y) for x, y in P) + " Z"


def layout(polys: dict) -> dict:
    return {
        "version": VERSION,
        "title": "Duty wheel v2",
        "source": ("Built as vector geometry by tools/ui_debug/build_duty_wheel_v2.py: a hub and "
                   "eight spokes on a true ellipse, two authored spokes plus their mirrors, each "
                   "face inset by half the frame along every edge and trimmed at the corners. "
                   "Mirrored about both axes, not rotated. Nothing traced."),
        "box": BOX,
        "box_h": BOX_H,
        "aspect": ASPECT,
        "aspect_is_open": ("69% of a shipped tile at canvas 1600, 2.19x at canvas 2283 -- see "
                           "THE ASPECT in build_duty_wheel_v2.py"),
        "frame": {"between_faces": 2 * D_FRAME, "around_centre": 2 * D_HUB,
                  "inset_from_rim": D_RIM},
        "ellipse": {"cx": CX, "cy": round(CY, 1), "rx": RX, "ry": round(RY, 1)},
        # Colour lives here because that is what this folder's other layout files do. It is a
        # debug palette and nothing else: the wheel that ships takes its parchment and ink from
        # the art, and the geometry above is the part of this file that is meant to be reused.
        "palette": {"ground": "#17130d", "face": "#efe3c8", "centre": "#e8dcc0",
                    "label": "#6b5f4a", "rule": "#3a3226"},
        "control_points": N_CTRL,
        "drawn": list(DRAWN),
        "mirrors": {d: {"of": s, "axis": "vertical" if m == "MV" else "horizontal"}
                    for d, s, m in MIRRORS},
        "spokes_deg": SPOKES,
        "checks": verify(polys),
        "cells": [{"index": i, "position": p,
                   "area": round(area(polys[p]), 1),
                   "d": beziers(polys[p]),
                   "d_poly": polyline(polys[p])}
                  for i, p in enumerate(ORDER)],
    }


def main() -> None:
    polys = build()
    data = layout(polys)
    out = Path(ARGS.out) if ARGS.out else OUT
    if not out.is_absolute():
        out = OUT.parent / out
    out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print("wrote %s  (aspect %.3f)" % (out, ASPECT))
    for k, v in data["checks"].items():
        print("  %-28s %s" % (k, v))


if __name__ == "__main__":
    main()
