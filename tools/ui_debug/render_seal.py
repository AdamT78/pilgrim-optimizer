"""The wax seal itself: a blob of wax with a die impression in it, drawn at a point.

Shared because the seal is about to be struck in two places. It marks which duty tile a turn
started from and which duty was taken, on `render_seal_prototypes.py`, and the Piety Track is about
to draw the same seal for the first player marker. The wobbled outline and the impression ring are
what would otherwise be copied into the second one and left to drift.

What is here is the wax, not what is struck into it. Glyphs, grounds and page layout belong to
whatever is doing the striking, because they differ per caller; the blob and the ring do not.

This is a debug/visual tool only. It emits SVG, is not connected to `GameState`, and decides
nothing about the game: a seal is a mark drawn on a tile, not a rule about the tile.

THE ONE CONSTRAINT WORTH KNOWING

The glyph must clear the impression ring. A square of side B has a half-diagonal of B/2*sqrt(2),
and that -- not B -- is what has to stay inside the ring. At B=18 against a seal of r=20 the
corners reach 12.73 while the ring sits at 15.60, leaving about 3 units of bare wax. At B=23 the
corners reach 16.26 and cross it. `check_clearance()` asserts this, so a future tweak to either
number fails loudly instead of quietly ruining the seal.
"""

from __future__ import annotations

import math

# ------------------------------------------------------------------ tuning
SEAL_R = 20.0  # seal radius, in the wheel's own units
RING_R = 0.78  # impression ring, as a fraction of SEAL_R
GLYPH_BOX = 18.0  # both glyphs fill this square, centred
WOBBLE = (0.045, 0.026)  # 3-period and 5-period ripple on the wax edge

WAX = "#DC6A61"  # the wax body: pushed light so the glyph can be deep
WAX_RIM = "#5E1712"  # the blob outline
WAX_DEEP = "#A83F36"  # the die impression, between wax and glyph in value

# Both lines are drawn in proportion to the seal rather than at a fixed width, so a seal struck at
# some other size comes out the same drawing rather than the same drawing under a heavier pen.
# Against SEAL_R these are the 2 and the 1.6 the seal has always been drawn with.
RIM_STROKE_R = 0.10
RING_STROKE_R = 0.08


def render_seal(cx: float, cy: float, r: float, seed: float = 0.4, ring: bool = True) -> str:
    """One seal of radius `r` centred on `cx`, `cy`, as a fragment with no `<svg>` around it."""
    pts = []
    n = 26
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1 + WOBBLE[0] * math.sin(3 * a + seed) + WOBBLE[1] * math.sin(5 * a + seed * 1.7))
        pts.append(f"{cx + math.cos(a) * rr:.2f},{cy + math.sin(a) * rr:.2f}")
    out = [
        f'<polygon points="{" ".join(pts)}" fill="{WAX}" stroke="{WAX_RIM}" '
        f'stroke-width="{r * RIM_STROKE_R:g}" stroke-linejoin="round"/>'
    ]
    if ring:
        out.append(
            f'<circle cx="{cx:g}" cy="{cy:g}" r="{r * RING_R:.2f}" fill="none" '
            f'stroke="{WAX_DEEP}" stroke-width="{r * RING_STROKE_R:g}" '
            f'stroke-opacity="0.95"/>'
        )
    return "".join(out)


def check_clearance() -> tuple[float, float, float]:
    """The glyph's corners, not its side, are what must clear the ring."""
    corner = GLYPH_BOX / 2 * math.sqrt(2)
    ring = SEAL_R * RING_R
    assert corner < ring, (
        f"glyph corners reach {corner:.2f} but the ring sits at {ring:.2f}: "
        f"shrink GLYPH_BOX below {ring / math.sqrt(2) * 2:.2f} or raise RING_R"
    )
    return corner, ring, ring - corner
