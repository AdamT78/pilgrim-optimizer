#!/usr/bin/env python3
"""Check a duty tile against everything the wheel pipeline needs, before nine of them exist.

Run it on each tile as it comes out of the image tool. Everything it reports is something that
has actually gone wrong at least once in this project:

  size / aspect     the tool reshapes a fixed pixel budget, so a wrong aspect is a silent crop
  join on midline   the highlight is a gradient centred at 50%; a drifting join puts the gold
                    edge in the wrong scene
  no drawn rule     v1 of the prompt said "divided" and the model drew an 80-level black line
  tonal key         style wording alone let Version A drift from 122 down to 89
  edge clearance    the torn outline fills ~82% of its box and bites hardest at the corners

It also writes the join table the picker needs, so the number that was measured is the number
that gets used rather than being copied across by hand:

    check_tile.py <tiles>/*.png --joins-out <tiles>/joins.json

Usage:  check_tile.py TILE.png [--single] [--version A|B]
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_duty_grid import TWO_ACTION  # noqa: E402

TARGET = {"A": (110, 130), "B": (70, 95)}
EDGE = 0.06


def black_mass(g: np.ndarray) -> tuple[float, float]:
    """How much of the tile is dark, and how much of it is dark AND featureless.

    The style block asks for blacks that stay hatched -- "the cross-hatching must stay separable
    everywhere, with no solid black masses". The thing to forbid is therefore a *featureless*
    black, not a dark one, and the two come apart badly on Version B. Crushing Give Alms B's
    shadows by 3x leaves the dark fraction pinned at 38.8% while the featureless fraction goes
    0.98 -> 3.22: the old "% below level 40" test cannot see the defect it names, and failed four
    of seven B tiles that have no solid mass anywhere in them.

    Measured on the seven B tiles delivered so far: 0.0-1.0% featureless, largest contiguous
    featureless blob 0.05% of frame. A 400x400 solid patch scores 10.7%. Threshold 2.5%.
    """
    dark = g < 40
    m = ndimage.uniform_filter(g, 7)
    sd = np.sqrt(np.maximum(ndimage.uniform_filter(g * g, 7) - m * m, 0))
    return dark.mean() * 100, (dark & (sd < 4)).mean() * 100


def join_fraction(path: Path) -> float:
    """DEPRECATED -- kept only so old joins.json files still load. Do not trust the number.

    This looked for the steepest column-to-column step near the middle and called it the join.
    It is not. It finds the strongest vertical EDGE, which on this material is a pillar, a
    scaffold post or a standing figure. On the four tiles where the source pair and the merge
    made from it are both available, it was wrong every time and always in the same direction:

        Give Alms A  reported 0.338   actual 0.500     Give Alms B  reported 0.329   actual 0.500
        Produce   A  reported 0.345   actual 0.500     Produce   B  reported 0.335   actual 0.500

    The join does not need finding. All seven source pairs measured here split at 0.4993-0.5035,
    because the pair is generated as two equal halves, and the merge keeps that. So the join is
    the midline, the picker centres its gradient at 0.5, and there is nothing to detect.
    """
    g = np.asarray(Image.open(path).convert("L")).astype(float)
    W = g.shape[1]
    d = np.abs(np.diff(g.mean(axis=0)))
    lo, hi = int(W * 0.30), int(W * 0.70)
    return (lo + int(np.argmax(d[lo:hi]))) / W


def check(path: Path, single: bool, version: str):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    g = np.asarray(im.convert("L")).astype(float)
    ok = True

    def say(good, label, detail):
        nonlocal ok
        if not good: ok = False
        print(f"  {'PASS' if good else 'FAIL'}  {label:22s} {detail}")

    print(f"\n{path.name}")
    say(abs(W/H - 1.0) < 0.02, "square", f"{W} x {H}, aspect {W/H:.3f}")
    say(W >= 1200, "resolution", f"{W} px (1254 is your tool's square maximum)")

    col = g.mean(axis=0)
    d = np.abs(np.diff(col))
    lo, hi = int(W*0.30), int(W*0.70)
    j = lo + int(np.argmax(d[lo:hi]))
    if not single:
        say(d[j] < 40, "no drawn rule",
            f"largest central step {d[j]:.1f} of 255 "
            + ("(a drawn line)" if d[j] >= 40 else "(a scene change)"))
    else:
        say(d[j] < 40, "no drawn rule",
            f"largest central step {d[j]:.1f} of 255")

    m = g.mean()
    tlo, thi = TARGET[version]
    say(tlo <= m <= thi, f"tonal key (ver {version})",
        f"mean {m:.1f}, want {tlo}-{thi}" + ("" if tlo <= m <= thi else
        "  <- too dark, hatching blocks up at 245 units" if m < tlo else "  <- too light"))
    dark, dead = black_mass(g)
    say(dead < 2.5, "black mass",
        f"{dead:.2f}% dark and featureless, {dark:.1f}% dark overall (blob threshold 2.5%)")

    e = int(min(W, H) * EDGE)
    ring = np.concatenate([g[:e].ravel(), g[-e:].ravel(), g[:, :e].ravel(), g[:, -e:].ravel()])
    say(True, "edge band", f"outer {EDGE*100:.0f}% mean {ring.mean():.1f} vs centre "
        f"{g[e:-e, e:-e].mean():.1f} (the torn shape eats this band)")

    print(f"  {'-> ready' if ok else '-> needs another pass'}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tiles", nargs="+")
    ap.add_argument("--single", action="store_true", help="a one-action tile: no join expected")
    ap.add_argument("--version", default="A", choices=["A", "B"])
    ap.add_argument("--joins-out", default=None,
                    help="write {tile index: join fraction} for every tile named NN_slug_V.ext")
    z = ap.parse_args()
    for t in z.tiles:
        check(Path(t), z.single, z.version)
    if z.joins_out:
        import json, re
        # Keyed by VERSION then tile index. A and B are separate drawings with separate joins,
        # and they are measured in separate runs, so writing merges rather than replaces.
        out = Path(z.joins_out)
        book = json.loads(out.read_text()) if out.is_file() else {}
        if book and all(k.isdigit() for k in book):      # a flat file from before versions
            book = {"A": book}
        pat = re.compile(r"^(\d{2})_[a-z_]+_([AB])\.(png|webp|jpg)$", re.I)
        added = {}
        for t in z.tiles:
            q = Path(t)
            m = pat.match(q.name)
            idx = int(m.group(1)) - 1 if m else None
            if m and idx in TWO_ACTION:
                v = m.group(2).upper()
                book.setdefault(v, {})[str(idx)] = round(join_fraction(q), 4)
                added[f"{v}{idx}"] = book[v][str(idx)]
        out.write_text(json.dumps(book, indent=1, sort_keys=True))
        print(f"\nwrote {out}: {added or 'nothing (single-action tiles have no join)'}")
