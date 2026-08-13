"""Structured renderer for the wax seal debug view.

The seals that will mark which duty tile a turn started from and which duty it took, drawn on
their own so the artwork can be judged before anything is built on it.

This is a debug/visual tool only. It emits SVG/HTML, is not connected to `GameState`, and decides
nothing about the game: a seal is a mark drawn on a tile, not a rule about the tile.

Unlike the other renderers here, this one reads nothing. There is no layout JSON and no config,
because there is nothing to reverse-engineer: everything the seal is made of is in the constants
below, which is what lets the seal be tuned here without the duty wheel around it. That also makes
`prototypes/seal_prototypes.html` unusual for this directory — it is the output of this module
rather than a hand-drawn baseline it is judged against, and the test suite holds the two to being
byte identical instead of merely alike.

WHAT IT RENDERS

The four glyphs on the tile parchment, which is the surface the seals sit on. `HEX_GREEN` and
`PAGE_BLACK` remain defined so a second or third ground can be put back by adding one entry to
`BACKGROUNDS`, and the keyline treatment is still wired through `seal()` so `TREATMENTS` can turn
it back on in one line. Neither is dead: they are the variants this page exists to compare, kept
switchable because the comparison will be wanted again.

Rendered at one size, `SEAL_PX`. That loses nothing: the seal is pure vector geometry expressed in
wheel units, so the pixel figure only sets the box it is drawn into and any later size is exact
rather than resampled. Two design thresholds are worth remembering when it is scaled DOWN, because
neither is a file-format problem: the wobble on the wax edge stops being distinguishable from a
circle below roughly 48px, and a keyline turns into a halo rather than an outline below roughly
24px.

THE ONE CONSTRAINT WORTH KNOWING

The glyph must clear the impression ring. A square of side B has a half-diagonal of B/2*sqrt(2),
and that -- not B -- is what has to stay inside the ring. At B=18 against a seal of r=20 the
corners reach 12.73 while the ring sits at 15.60, leaving about 3 units of bare wax. At B=23 the
corners reach 16.26 and cross it. `check_clearance()` asserts this on every render, so a future
tweak to either number fails loudly instead of quietly ruining the seal.
"""

from __future__ import annotations

import math
from collections.abc import Callable

# ------------------------------------------------------------------ tuning
SEAL_R = 20.0  # seal radius, in the wheel's own units
RING_R = 0.78  # impression ring, as a fraction of SEAL_R
GLYPH_BOX = 18.0  # both glyphs fill this square, centred
WOBBLE = (0.045, 0.026)  # 3-period and 5-period ripple on the wax edge
SEAL_PX = 96  # the one size rendered here; see the note on scaling

WAX = "#DC6A61"  # the wax body: pushed light so the glyph can be deep
WAX_RIM = "#5E1712"  # the blob outline
WAX_DEEP = "#A83F36"  # the die impression, between wax and glyph in value
GLYPH = "#6E1A14"  # the struck symbol
KEY = "#F6EFDD"  # optional keyline, for when two reds are not enough

PARCHMENT = "#EFE4C6"  # the tile face the seal sits on
HEX_GREEN = "#8FBF6B"  # the board under a tile's corner
PAGE_BLACK = "#000000"

# A glyph draws itself into the middle of a seal, given the keyline attributes to carry or "".
GlyphDrawer = Callable[[str], str]


# ------------------------------------------------------------------- glyphs
def g_square(k: str) -> str:
    h = GLYPH_BOX / 2
    return (
        f'<rect x="{-h:.2f}" y="{-h:.2f}" width="{GLYPH_BOX}" '
        f'height="{GLYPH_BOX}" rx="2" fill="{GLYPH}"{k}/>'
    )


def g_shield(k: str) -> str:
    """The duty tile's silhouette: half the height straight, half an arc."""
    h = GLYPH_BOX / 2
    return (
        f'<path d="M {-h:.2f},{-h:.2f} h {GLYPH_BOX} v {h:.2f} '
        f'a {h:.2f},{h:.2f} 0 0 1 {-GLYPH_BOX} 0 z" fill="{GLYPH}"{k}/>'
    )


def g_letter(ch: str) -> GlyphDrawer:
    def draw(k: str) -> str:
        return (
            f'<text x="0" y="{GLYPH_BOX * 0.36:.2f}" text-anchor="middle" '
            f'font-family="Georgia, serif" font-size="{GLYPH_BOX * 1.05:.1f}" '
            f'font-weight="700" fill="{GLYPH}"{k}>{ch}</text>'
        )

    return draw


# Positions 1, 3, 5 and 7 of the original ten: the four flat glyphs, with the
# keyline treatment and the T dropped. The keyline machinery below is kept
# because it costs nothing and the two reds may still need it at small sizes;
# it is simply not rendered here.
GLYPHS: list[tuple[str, GlyphDrawer]] = [
    ("square", g_square),
    ("shield", g_shield),
    ("S", g_letter("S")),
    ("A", g_letter("A")),
]
TREATMENTS = [False]


# --------------------------------------------------------------------- seal
def seal(glyph: GlyphDrawer, keyline: bool = False, seed: float = 0.4, ring: bool = True) -> str:
    """One seal, drawn about the origin so it can be placed anywhere."""
    pts = []
    n = 26
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = SEAL_R * (
            1 + WOBBLE[0] * math.sin(3 * a + seed) + WOBBLE[1] * math.sin(5 * a + seed * 1.7)
        )
        pts.append(f"{math.cos(a) * rr:.2f},{math.sin(a) * rr:.2f}")
    out = [
        f'<polygon points="{" ".join(pts)}" fill="{WAX}" stroke="{WAX_RIM}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
    ]
    if ring:
        out.append(
            f'<circle cx="0" cy="0" r="{SEAL_R * RING_R:.2f}" fill="none" '
            f'stroke="{WAX_DEEP}" stroke-width="1.6" '
            f'stroke-opacity="0.95"/>'
        )
    k = f' stroke="{KEY}" stroke-width="1.9" stroke-linejoin="round"' if keyline else ""
    out.append(glyph(k))
    return "".join(out)


def svg(glyph: GlyphDrawer, keyline: bool, px: int, seed: float = 0.4, ring: bool = True) -> str:
    m = SEAL_R * 1.22
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" '
        f'viewBox="{-m:.1f} {-m:.1f} {2 * m:.1f} {2 * m:.1f}">'
        f"{seal(glyph, keyline, seed, ring)}</svg>"
    )


# ---------------------------------------------------------------- self-check
def check_clearance() -> tuple[float, float, float]:
    """The glyph's corners, not its side, are what must clear the ring."""
    corner = GLYPH_BOX / 2 * math.sqrt(2)
    ring = SEAL_R * RING_R
    assert corner < ring, (
        f"glyph corners reach {corner:.2f} but the ring sits at {ring:.2f}: "
        f"shrink GLYPH_BOX below {ring / math.sqrt(2) * 2:.2f} or raise RING_R"
    )
    return corner, ring, ring - corner


# --------------------------------------------------------------------- page
# Only the surface the seals actually sit on. The green and the page black are
# kept as constants above, so adding a row back is one line here.
BACKGROUNDS = [("On the tile parchment", PARCHMENT, "#8B7B4E")]


def render_seal_prototypes_html() -> str:
    """The whole page. Checks the clearance first, so no page is ever written past the assert."""
    corner, ring, clear = check_clearance()

    blocks = []
    for title, bg, edge in BACKGROUNDS:
        cells = []
        for name, g in GLYPHS:
            for keyline in TREATMENTS:
                cells.append(
                    f'<figure><div class="chip" style="background:{bg};'
                    f'border-color:{edge}">{svg(g, keyline, SEAL_PX)}</div>'
                    f"<figcaption>{name}{' + keyline' if keyline else ''}"
                    f"</figcaption></figure>"
                )
        blocks.append(f'<h2>{title}</h2><div class="grid">{"".join(cells)}</div>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Pilgrim — seal prototypes</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:#0B0B0B; color:#F2EEDF; padding:28px 32px 56px;
          font-family:Helvetica,Arial,sans-serif; }}
  h1 {{ font-size:20px; font-weight:600; margin:0 0 6px; }}
  h2 {{ font-size:14px; font-weight:600; margin:30px 0 12px;
        border-top:1px solid #262622; padding-top:20px; }}
  .lede {{ color:#9A968C; font-size:13px; line-height:1.55; max-width:80ch;
           margin:0 0 4px; }}
  .grid {{ display:flex; flex-wrap:wrap; gap:14px; }}
  figure {{ margin:0; }}
  .chip {{ width:126px; height:126px; display:flex; align-items:center;
           justify-content:center; border-radius:10px; border:1px solid; }}
  figcaption {{ color:#8E877C; font-size:11.5px; margin-top:7px;
                text-align:center; }}
  table {{ border-collapse:collapse; font-size:12.5px; margin-top:6px; }}
  td {{ padding:3px 16px 3px 0; color:#9A968C; }}
  td b {{ color:#E7E1D3; font-weight:600; }}
  code {{ color:#D8CFA8; }}
</style></head><body>
  <h1>Wax seals — isolated</h1>
  <p class="lede">Four glyphs at {SEAL_PX}px on the tile parchment. Pure vector —
  scaling down later is exact, though the edge wobble stops reading below about
  48px.</p>

  <table>
    <tr><td>seal radius</td><td><b>{SEAL_R:.0f}</b> wheel units</td>
        <td>impression ring</td><td><b>{ring:.2f}</b> ({RING_R} &times; r)</td></tr>
    <tr><td>glyph box</td><td><b>{GLYPH_BOX:.0f}</b></td>
        <td>glyph corner reach</td><td><b>{corner:.2f}</b></td></tr>
    <tr><td>clearance</td><td><b>{clear:.2f}</b> units of bare wax</td>
        <td>colours</td>
        <td><code>{WAX}</code> wax &middot; <code>{GLYPH}</code> glyph
            &middot; <code>{WAX_DEEP}</code> ring</td></tr>
  </table>

  {"".join(blocks)}

</body></html>
"""
