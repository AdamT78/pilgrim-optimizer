"""The panorama behind the game view, joined from its two committed halves.

WHY THIS IS A SCRIPT AND NOT JUST A COMMITTED PICTURE

The two halves are diffusion output with no seed on record, so they cannot be regenerated and are
committed under ui/assets-gothic/ui/sources/ as the masters they are. What joins them CAN be
regenerated, and it is not a concatenation: two corrections sit between the halves and the finished
picture, both derived by measuring the images rather than by choosing a number. Written in prose in
an attribution record, those are a claim about the past. Written here, they are re-runnable, and
`--check` is what keeps the committed file and this script from drifting apart.

    the level step      The right half's inner edge came back about 1.5 grey levels brighter than
                        the left's, consistently from top to bottom (+0.75 at the top, +2.01 at
                        the bottom). Corrected per channel and faded to nothing over the first
                        quarter of the right half's width, so the correction has died out long
                        before it reaches anything anyone looks at.

    the edge vignette   THE ONE WORTH READING. Both halves darken over their last ~28 columns --
                        a generated vignette, invisible in either picture on its own. Butted
                        together the two ramps meet and make a symmetric trough about 2 levels
                        deep and 56 px wide at dead centre, which reads as a soft seam even though
                        the STEP across the join is nearly zero. A level match does not touch it,
                        and the usual check -- compare the last column of one against the first
                        column of the other -- measures it as fine. It is a crease, not a step.
                        Flattened by lifting each inner edge back to the plateau its own columns
                        settle at 40-120 px further in.

Order matters: de-vignette first, then level-match. The vignette sits inside the columns the level
match measures, so matching first would measure the step against two sagging edges and bake the sag
into the correction.

    python3 ui/render/gen_panorama.py            # write ui/assets-gothic/ui/panorama.webp
    python3 ui/render/gen_panorama.py --check    # compare against the committed file, write nothing
"""

from __future__ import annotations

import argparse
import io
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
UI = HERE.parent / "assets-gothic" / "ui"
# TWO PANORAMAS, AND THE OLD ONE IS NOT A FOSSIL. The night field is the picture the wheel was
# composed against and every measurement in ui/README.md was taken over; the mist field is the
# lighter one, and what it buys is the TILE EDGE. Measured behind the wheel, the night field sits
# at L* 12.9 against a tile edge ink of L* 13.5 -- 0.6 apart, which is to say the outline of a duty
# tile is the same value as what is behind it and does nothing. Keeping both is what lets that be
# compared rather than remembered.
#
# The cost is stated because it is real and it points the other way: the wheel's acolyte marks sit
# on this same field, and pewter (L* 43.8) and plum (L* 45.3) are the two that a lighter ground
# closes on. Every seat keeps its dark outline, so the marks do not vanish -- but they read more by
# outline and less by fill than they did.
SETS = {
    "night": {
        "left": UI / "sources" / "panorama_left.webp",
        "right": UI / "sources" / "panorama_right.webp",
        "out": UI / "panorama.webp",
        "label": "cold night fog, inner edges at #1e1d1b",
    },
    "mist": {
        "left": UI / "sources" / "panorama_mist_left.webp",
        "right": UI / "sources" / "panorama_mist_right.webp",
        "out": UI / "panorama_mist.webp",
        "label": "pale daylight mist, inner edges near #464442",
    },
}
# Which one the board draws. gen_duty_grid.PANORAMA reads this rather than naming a file, so the
# page and the generator cannot disagree about which picture is the background.
DEFAULT = "mist"


def panorama_set(name: str | None = None) -> dict:
    """One set by name, or the default. Raises rather than falling back to the other picture."""
    name = DEFAULT if name is None else name
    if name not in SETS:
        raise SystemExit("no panorama set %r; this file has %s"
                         % (name, ", ".join(sorted(SETS))))
    return SETS[name]

# The vignette measured ~28 columns wide on both halves; 40 is that with room, and the plateau is
# read from the next 80 columns in. Widening this is safe (the correction is zero where there is
# no sag); narrowing it below ~30 leaves part of the trough behind.
EDGE = 40
# How far the level correction takes to die out, as a fraction of a half's width. A quarter puts
# its last non-zero pixel well clear of the right half's subject, which starts around 60%.
FADE = 0.25
QUALITY = 86


def _np():
    try:
        import numpy as np
    except ModuleNotFoundError as exc:                                   # pragma: no cover
        raise SystemExit("joining the halves needs numpy: pip install numpy") from exc
    return np


def devignette(a, side: str, edge: int = EDGE):
    """Lift `edge` columns at one end back to the level the columns just inside them settle at.

    Per column and per channel, from the image's own column means, so it removes a ramp without
    touching anything the ramp is laid over. A half with no vignette gets a correction of zero.
    """
    np = _np()
    b = a.copy()
    if side == "right":
        prof = a[:, -edge:, :].mean(axis=0)
        plateau = a[:, -3 * edge:-edge, :].mean(axis=(0, 1))
        b[:, -edge:, :] += (plateau[None, :] - prof)[None, :, :]
    else:
        prof = a[:, :edge, :].mean(axis=0)
        plateau = a[:, edge:3 * edge, :].mean(axis=(0, 1))
        b[:, :edge, :] += (plateau[None, :] - prof)[None, :, :]
    return np.clip(b, 0, 255)


def join(left_path: pathlib.Path | None = None, right_path: pathlib.Path | None = None,
         pano_set: str | None = None):
    """The finished panorama as a PIL image, plus the numbers worth printing."""
    np = _np()
    from PIL import Image

    # Resolved HERE and not as default arguments. A default binds at def time, so `left_path=LEFT`
    # would have pinned this function to one set the moment the module was imported and no caller
    # could have moved it. That exact trap has cost this tree two debugging sessions -- ARROW_OUTSET
    # and tile_placement -- and it is the reason a set is named rather than a path defaulted.
    spec = panorama_set(pano_set)
    left_path = spec["left"] if left_path is None else left_path
    right_path = spec["right"] if right_path is None else right_path

    for p in (left_path, right_path):
        if not p.is_file():
            raise SystemExit(
                "%s is missing. The halves are diffusion output with no seed on record -- they "
                "cannot be regenerated, only restored from git." % p)

    lo = Image.open(left_path).convert("RGB")
    ro = Image.open(right_path).convert("RGB")
    if lo.size != ro.size:
        raise SystemExit("the halves are %s and %s; they must match." % (lo.size, ro.size))

    left = devignette(np.asarray(lo).astype(np.float64), "right")
    right = devignette(np.asarray(ro).astype(np.float64), "left")

    step = right[:, :16, :].mean(axis=(0, 1)) - left[:, -16:, :].mean(axis=(0, 1))
    w = right.shape[1]
    fade = int(w * FADE)
    ramp = np.ones(w)
    ramp[:fade] = np.linspace(1.0, 0.0, fade)
    right = np.clip(right - step[None, None, :] * ramp[None, :, None], 0, 255)

    out = np.concatenate([left, right], axis=1)
    g = out.mean(2)
    mid = out.shape[1] // 2
    seam = {k: float(g[:, mid:mid + k].mean() - g[:, mid - k:mid].mean()) for k in (1, 4, 16, 64)}
    return Image.fromarray(out.round().astype("uint8")), step, seam


def encode(im, quality: int = QUALITY) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", dest="pano_set", default=DEFAULT, choices=sorted(SETS),
                    help="which panorama to join (default: %s, the one the board draws)" % DEFAULT)
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="defaults to the chosen set's own output path")
    ap.add_argument("--quality", type=int, default=QUALITY)
    ap.add_argument("--check", action="store_true",
                    help="compare against the committed file and write nothing")
    z = ap.parse_args()

    spec = panorama_set(z.pano_set)
    if z.out is None:
        z.out = spec["out"]
    im, step, seam = join(pano_set=z.pano_set)
    print("%s -- %s" % (z.pano_set, spec["label"]))
    print("%dx%d  %.4f:1" % (im.width, im.height, im.width / im.height))
    print("  level step at the join, per channel:  R %+.2f  G %+.2f  B %+.2f" % tuple(step))
    print("  seam after both corrections:          " +
          "  ".join("+-%d %+.2f" % (k, v) for k, v in seam.items()))
    data = encode(im, z.quality)
    print("  %d bytes at quality %d" % (len(data), z.quality))

    if z.check:
        if not z.out.is_file():
            raise SystemExit("%s is not in this checkout, so there is nothing to check." % z.out)
        have = z.out.read_bytes()
        if have != data:
            raise SystemExit(
                "%s is not what this script now produces (%d bytes committed, %d regenerated). "
                "Either the join changed and the picture was not rebuilt, or the picture was "
                "edited outside the script." % (z.out, len(have), len(data)))
        print("  matches the committed file byte for byte")
    else:
        z.out.parent.mkdir(parents=True, exist_ok=True)
        z.out.write_bytes(data)
        print("  written %s" % z.out)
