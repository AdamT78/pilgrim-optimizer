"""The wax seal itself: a blob of wax with a die impression in it, drawn at a point.

Shared because the seal is struck in two places. It marks which duty tile a turn started from and
which duty was taken, on `render_seal_prototypes.py`, and it marks who holds the first player marker
on `render_piety_track_v2.py`. The wobbled outline and the impression ring are what would otherwise
be copied into the second one and left to drift.

What is here is the wax, not what is struck into it, and not what colour the wax is. Glyphs, grounds
and page layout belong to whatever is doing the striking, because they differ per caller; the blob
and the ring do not. Colour is the same story: the duty-tile seals are one fixed red, and the first
player seal is whichever seat holds it, so the three colours are asked for rather than kept here.

`check_clearance()` used to live here and does not any more. It measures a glyph's box against the
ring, which is a property of the duty-tile glyphs and of nothing else -- the crown has no box and is
sized off `r` -- so it sits with them, in `render_seal_prototypes.py`. Left here it would have
covered one caller of two while reading as though it covered both.

This is a debug/visual tool only. It emits SVG, is not connected to `GameState`, and decides
nothing about the game: a seal is a mark drawn on a tile, not a rule about the tile.
"""

from __future__ import annotations

import math

# ------------------------------------------------------------------ tuning
SEAL_R = 20.0  # the radius the seal was drawn at, and the duty tiles still strike it at
RING_R = 0.78  # impression ring, as a fraction of the seal's radius
WOBBLE = (0.045, 0.026)  # 3-period and 5-period ripple on the wax edge

# Both lines are drawn in proportion to the seal rather than at a fixed width, so a seal struck at
# some other size comes out the same drawing rather than the same drawing under a heavier pen.
# Against SEAL_R these are the 2 and the 1.6 the seal has always been drawn with.
RIM_STROKE_R = 0.10
RING_STROKE_R = 0.08


def darken(colour: str, factor: float) -> str:
    """A colour pulled toward black, for striking a seal in a palette it was not drawn in.

    The duty-tile seals were drawn as three reds chosen by eye. The first player seal cannot be:
    it is whichever seat holds the marker, so its rim, ring and crown have to fall out of that
    seat's own colour. Scaling each channel keeps the hue and drops the value, which is what
    reading as the same seal in another colour needs, and it means a re-tuned palette needs no new
    constants -- the darker tones follow whatever the seat is drawn in.
    """
    bare = colour.lstrip("#")
    channels = (int(bare[at : at + 2], 16) for at in (0, 2, 4))
    return "#" + "".join(f"{round(value * factor):02X}" for value in channels)


def render_seal(
    cx: float,
    cy: float,
    r: float,
    wax: str,
    rim: str,
    ring_colour: str,
    seed: float = 0.4,
    ring: bool = True,
    tilt: float = 0.0,
    inner: str = "",
) -> str:
    """One seal of radius `r` centred on `cx`, `cy`, as a fragment with no `<svg>` around it.

    `tilt` turns the wax about its own centre, in degrees, so a seal need not sit square to what it
    is struck on. It costs a wrapping group, so it is only wrapped when there is a turn to make.

    `inner` is whatever the die struck into the wax, drawn over the ring and turned with it. It is
    taken as a fragment rather than drawn here because glyphs belong to their consumer -- but it has
    to be taken at all, because the ring and the glyph come off the same die. A caller that appended
    its glyph after this returned would be tilting half the die and leaving the other half square,
    which only looks survivable while the ring is a circle and its turn cannot be seen.
    """
    pts = []
    n = 26
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * (1 + WOBBLE[0] * math.sin(3 * a + seed) + WOBBLE[1] * math.sin(5 * a + seed * 1.7))
        pts.append(f"{cx + math.cos(a) * rr:.2f},{cy + math.sin(a) * rr:.2f}")
    out = [
        f'<polygon points="{" ".join(pts)}" fill="{wax}" stroke="{rim}" '
        f'stroke-width="{r * RIM_STROKE_R:g}" stroke-linejoin="round"/>'
    ]
    if ring:
        out.append(
            f'<circle cx="{cx:g}" cy="{cy:g}" r="{r * RING_R:.2f}" fill="none" '
            f'stroke="{ring_colour}" stroke-width="{r * RING_STROKE_R:g}" '
            f'stroke-opacity="0.95"/>'
        )
    struck = "".join(out) + inner
    if not tilt:
        return struck
    return f'<g transform="rotate({tilt:g} {cx:g} {cy:g})">{struck}</g>'
