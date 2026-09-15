#!/usr/bin/env python3
"""The duty wheel as a 3x3 grid of torn tiles, drawn as vector rather than carried as a raster.

WHY THIS IS NOT A PICTURE

The grid arrived as a generated image, 1254 px square, because that is what the image tool makes.
But almost nothing in it is photographic: it is a parchment field and nine outlines. The field is
low-frequency and synthesises from its own measured grain; the outlines are *contours*, and a
contour is geometry, not pixels.

Carried as a raster the component would be ~1.8 MB, would soften on any display that draws it
larger than 1254, and would have to be regenerated to change a colour. Carried as paths it is
17 KB, is sharp at any size, and every colour is an attribute. Measured on the same edge: an
upscale to 3072 smears the transition from 3 px to 5; these paths hold it at 3.

The shapes themselves are still the artist's -- traced out of the generated sheet and smoothed,
not invented. `duty_grid_shapes.json` records where they came from.

WHAT IT CARRIES

The *shapes* are geometry, but the pictures inside them are not, and those are embedded: the tiles
of whichever version `VERSION` names, from `assets-gothic/duty-tiles/`, downscaled to the size the
component is actually drawn at. A tile with no artwork yet keeps its flat region-map colour, so a half-finished set
renders as a grid with holes rather than failing.

The lit and dim states are `feColorMatrix` filters, not further artwork. That is the decision the
whole component rests on, and it was settled by measurement: two diffusion merges of the same pair
differ by edge-difference 13.0, so a generated "lit" tile would visibly redraw itself under the
cursor. See `ui/docs/duty-wheel/`.
"""
from __future__ import annotations

import base64
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import population_sets as pop           # noqa: E402  (needs the path line above)

HERE = pathlib.Path(__file__).resolve().parent
SHAPES = HERE.parent / "assets-gothic" / "metadata" / "duty_grid_shapes.json"
TILES = HERE.parent / "assets-gothic" / "duty-tiles"
# The field this component is built to sit on and deliberately does not paint. BACKGROUND is None
# so the ground shows through the channels between the nine tiles, and the path lives here rather
# than in either caller because BOTH need it: the board that lays the wheel on it, and the picker,
# whose whole claim is to show what the board will show and which drew its own parchment instead.
GROUND = HERE.parent / "assets-gothic" / "ui" / "ground.webp"

# The panorama the game view paints on the PAGE rather than on the stage, and the difference is
# the whole point of it being a second file rather than a bigger GROUND.
#
# GROUND is stretched over the stage -- a fixed 1600 x 1200 canvas that is then zoom-to-fitted --
# so on a 3440-wide screen it stops where the canvas stops and leaves about 840 px of flat colour
# either side. The panorama is stretched over the viewport instead, so it has no edges to leave,
# and it is 2.600:1 because that is the screen it is composed for. Neither can do the other's job:
# a viewport-sized GROUND would have its noise scaled differently on every display, and a
# stage-sized panorama would be the clipped picture this replaces.
#
# The path lives here, beside GROUND, for the reason GROUND's does: more than one page needs it,
# and a second statement of where a file lives is a second thing to keep in step.
PANORAMA = HERE.parent / "assets-gothic" / "ui" / "panorama.webp"

# A 1x1 transparent GIF. What a missing field falls back to, so the caller's own flat colour shows
# and the page is plainer rather than broken.
_BLANK = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="


def _embed(path: pathlib.Path, missing: str) -> str:
    """`path` as a data: URI, or a transparent pixel with a note saying which file is absent.

    Embedded rather than linked: every page that uses one of these is written to ui/generated/ and
    then opened from wherever it lands, so a relative src would work in exactly one of those cases
    and silently show nothing in the rest.
    """
    import base64
    if not path.is_file():
        print("no %s -- falling back to flat colour. %s" % (path.name, missing))
        return _BLANK
    return "data:image/webp;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def ground_uri() -> str:
    """The field under the board, stretched over the stage."""
    return _embed(GROUND, "Run `python3 ui/render/gen_ground.py` to make it.")


def panorama_uri() -> str:
    """The field behind the page, stretched over the viewport.

    No generator to point at: this one is diffusion output, joined and level-matched by hand, and
    its provenance is the attribution record rather than a script.
    """
    return _embed(PANORAMA, "It is a committed asset, not a generated one -- restore it from git.")

# Version B -- grim dark -- chosen over A after both were generated in full and compared in the
# picker. The case was not only taste. Measured over the eight tiles of each:
#
#   tonal spread   A 92.7-146.1 (53 levels)     B 67-99 (32)
#   lit highlight  A blows 10.0% of the lit     B blows 1.1%
#                  area to paper white
#   hover signal   A warm grey -> warm gold     B cold grey -> amber
#                  (+54 R-B, but mostly         (+36 R-B, a temperature change
#                  a saturation change)         as well as a value one)
#
# A's clipping is the load-bearing one: it sits high enough that the lit filter pushes highlights
# past white and the engraving inside them is simply gone. B has the headroom.
#
# VERSION C -- the limited palette -- now supersedes B. The C prompts changed subject lines only;
# the palette paragraph is byte-identical, so this is the same instruction drawn again, with the
# people fixed: a nun overseeing the road gang instead of a slipping mason, roads and shrines
# instead of piles driven into a river, an ordinand and a friar who are no longer the same young
# man twice, and women among the reapers.
#
# The figures below are measured on the ASSEMBLED WHEEL -- through the palette, the dim filter and
# the lit filter, at DIM_SATURATE 1.00 -- and are NOT comparable to the A/B rows above, which were
# measured on the tiles themselves. B is repeated here on the same method so C has something
# honest to sit beside:
#
#                        B        C
#   tonal spread      18-203   23-230     2nd-98th percentile of resting luminance
#   lit blown           6.8%    11.4%     lit pixels with a channel at or over 250
#   hover signal      +61 R-B  +67 R-B    median resting-to-lit temperature change
#   edge separation    10.6     12.3      luminance across the silhouette, same ground
#
# C IS THE ONE WITH THE CLIPPING NOW, and that is the fault that disqualified A. It is smaller in
# kind -- A lost engraving inside large blown areas, C's are scattered highlights on a brighter
# set -- but it is the same mechanism and it is worth knowing before the LIT slopes are ever
# tuned: C has about half B's headroom under them. It buys a tile that separates better from the
# ground at rest (12.3 against 10.6) and a slightly stronger hover.
#
# Six of C's nine also sit below the tonal band check_tile enforces, against three of B's, and
# that band was deliberately left at B's values rather than widened to fit the delivery.
VERSION = "C"

# Flat fills, one per tile. These are a REGION MAP, not a palette: each becomes a hover mask when
# the art lands, and none of them survives into the finished wheel. Chosen to be easy to tell
# apart, not to look good together.
TILE_FILLS = ["#67694a", "#4a5d70", "#ab4c38", "#c68335", "#9d8869",
              "#815977", "#45596e", "#636c4a", "#8d5b33"]
# The nine duties, in the order their artwork is numbered: `01_allocation` is DUTY_NAMES[0],
# `09_give_alms` is DUTY_NAMES[8]. This is an IDENTITY, not a position -- it says which picture
# is which duty and nothing about where that duty sits on the board.
DUTY_NAMES = ["Allocation", "Clerical", "Construct", "Build Roads", "The City",
              "Ordination", "Produce", "Taxation", "Give Alms"]
# Which grid cell each duty is drawn in, as an ARRANGEMENT rather than a fact. Duty tiles are
# shuffled at setup and then fixed for the game, so there is no canonical order and this is a
# fixture for drawing -- exactly the status of the `duties` list in
# tools/ui_debug/duty_wheel_layout.json, which carries a different arrangement, and of the
# engine's _DEFAULT_DUTY_TILES, which carries a third. None of the three feeds the rules, and the
# fact that they disagree is not a bug in any of them.
#
# Pass `cells=` to draw a real game's board: cells[duty] is the 0..8 grid square that duty
# occupies, top-left to bottom-right. The default below is what this component has always drawn.
#
# NOTHING ABOUT ROUTING DEPENDS ON THIS. A sow runs over the SHAPES, which do not shuffle, and
# the graph saying which shape follows which is `configs/board.json` -- now the only copy, since
# the ring arrows took their hand-written `RING`/`CITY_ROUTES` out with them. Marking a shape
# during a sow will need one position->square mapping to get from that graph to these cells;
# see ui/docs/duty-wheel/sow-marking.md.
DEFAULT_CELLS = [0, 1, 2, 3, 4, 5, 6, 7, 8]
# Which tiles carry two actions, and so have a join and two hover halves. Three duty tiles have
# a single action (Allocation, Build Roads, Taxation) and the city has none; measuring a join on
# those finds the strongest edge in a picture that has no join, which is noise.
TWO_ACTION = {1: ("Devotion", "Silversmith"), 2: ("Building", "Road"),
              5: ("Ordain", "Mission"), 6: ("Wheat", "Stone"), 8: ("Donate", "Alms")}
# The pairs are in the order the ART draws them, left to right, because that is what decides
# which half of a tile a pointer is on. Give Alms was ("Alms", "Donate") until the artwork put the
# donation on the left, and the pair had to follow it: a tile whose halves are named in the wrong
# order sends every click and every caption to the other action, silently, on a picture that looks
# completely normal.
# The centre tile. It is a place, not an action: never dimmed, and nothing to light.
CITY = 4
INK = "#2b2114"
PARCHMENT_FALLBACK = "#f5c37b"


def load(path: pathlib.Path = SHAPES) -> dict:
    if not path.is_file():
        raise SystemExit(
            "%s is missing. It carries the nine tile outlines traced from the generated sheet; "
            "without it there is no grid to draw." % path)
    return json.loads(path.read_text(encoding="utf-8"))


def find_tiles(root: pathlib.Path = TILES, version: str = VERSION) -> dict[int, pathlib.Path]:
    """`NN_slug_V.png` anywhere under root, keyed by grid index. Absent tiles stay absent.

    NN is the tile's position in DUTY_NAMES, one-based -- so Produce is 07 and Taxation is 08,
    and getting that wrong silently draws a tile in its neighbour's square. The regex also
    rejects the `_pair`/`_left`/`_right` sources that sit under duty-tiles/sources/.

    The version group is ANY single letter, not a list of the versions that exist. Spelled `[AB]`
    it did not fail when version C arrived -- it matched nothing, `found` came back empty, and the
    wheel drew nine flat region colours and reported "no art", which is precisely what it does for
    a set nobody has drawn yet. The set was there, in the right folder, under the right names. A
    pattern that names today's versions turns tomorrow's into an absence, and absence is the one
    state this component is built to tolerate silently.
    """
    if not root or not root.is_dir():
        return {}
    pat = re.compile(r"^(\d{2})_([a-z_]+)_([A-Z])\.(png|webp|jpg)$", re.I)
    found: dict[int, pathlib.Path] = {}
    for p in sorted(root.rglob("*")):
        m = pat.match(p.name)
        if m and m.group(3).upper() == version.upper():
            i = int(m.group(1)) - 1
            if 0 <= i < 9:
                found[i] = p
    return found


def embed(p: pathlib.Path, px: int = 448, quality: int = 82,
          palette: str | None = None, ref=None) -> str:
    """One data URI per picture, re-encoded to the size this component actually draws.

    The sources are 1254 px PNGs of dense engraving, ~3.5 MB each; eight of them raw would be a
    28 MB component. The whole wheel measures about 1247 device pixels at DPR 2, so one tile of
    the 3x3 is drawn at roughly 416 -- and 448 is that, rounded up. Dense cross-hatching is
    expensive to encode and resists quality cuts, so oversizing is what costs here: the same set
    at 640 px is 1.9x the bytes for detail no display in the layout can resolve.
    """
    try:
        import io

        from PIL import Image
        im = Image.open(p).convert("RGB")
        if max(im.size) > px:
            k = px / max(im.size)
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        if palette and ref:            # after the resize: same result, a ninth of the pixels
            im = recolour(im, ref, palette)
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=quality, method=6)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        mime = {"png": "image/png", "webp": "image/webp",
                "jpg": "image/jpeg"}[p.suffix.lstrip(".").lower()]
        return "data:%s;base64," % mime + base64.b64encode(p.read_bytes()).decode()



# ---------------------------------------------------------------------------------------------
# Palette
#
# The nine were generated one at a time and their colour drifted: native LAB chroma runs 2.70 on
# Allocation, a cold grey, to 8.99 on Produce, a warm sepia. Matching them to one reference -- the
# city, which is the tile the others are seen against -- closes that.
#
# This is done here rather than by asking the image tool to recolour, because a re-render is a new
# drawing. Measured on the same tiles: this mapping moves the line work by 0.010-0.083, and a
# diffusion re-render moved it by 13.0. The whole lit/dim design rests on the art not moving.
#
# It also improves the city's separation rather than harming it. The city is the one tile never
# dimmed, and that -- not its palette -- is what sets it apart; matching the rest takes Produce
# from 1.2x the city's dimmed chroma to a clean 2.5x.
#
#   None      leave every tile as generated
#   "chroma"  match colour, keep each tile's own tonal key
#   "full"    match colour and key
#
# "full" is the default because "chroma" turns out to be nearly a no-op where it matters. The dim
# filter desaturates to 0.40, so a change that works on chroma alone loses most of itself on the
# eight dimmed tiles, and the city -- which would show it whole -- is the reference and does not
# move. Measured against "as generated" in the assembled wheel:
#
#                     resting                 hover
#   chroma      0.70 mean,  1.5% of px    2.04,  36.1%
#   full        9.54 mean, 51.0%         10.39,  55.6%
#
# Most of what "full" does is the tonal levelling, which also lifts Clerical from L 20.8 to 36.8
# -- it is the darkest tile in the set by 15 levels and the one the lit filter has least room to
# work on.
PALETTE: str | None = "full"
PALETTE_REF = 4                      # the city


def _to_lab(rgb):
    """sRGB 0..1 to CIE LAB. Written out rather than imported: scikit-image is not a dependency
    of this repo and CI does not install it, and this is twenty lines."""
    import numpy as np
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    e, k = (6 / 29) ** 3, (1 / 3) * (29 / 6) ** 2
    f = np.where(xyz > e, np.cbrt(xyz), k * xyz + 4 / 29)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def _to_rgb(lab):
    import numpy as np
    fy = (lab[..., 0] + 16) / 116
    f = np.stack([fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200], axis=-1)
    e = 6 / 29
    xyz = np.where(f > e, f ** 3, 3 * e ** 2 * (f - 4 / 29)) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2404542, -1.5371385, -0.4985314],
                  [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]])
    # clipped before the gamma: a shifted LAB value can land outside the sRGB gamut, and a
    # negative raised to a fractional power is NaN rather than an error
    lin = np.clip(xyz @ m.T, 0, None)
    srgb = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(srgb, 0, 1)


def palette_matrix(im, ref, mode):
    """The LAB transfer as one feColorMatrix, fitted to this tile.

    A per-channel shift and scale in LAB is not linear in RGB, so this is a least-squares fit
    rather than an identity -- but on this material it is a very close one: measured across the
    eight tiles the residual is 0.32 to 2.22 levels of 255, which is at or below the WebP q92
    error already baked into the files. What it buys is that the palette becomes a *filter*: the
    art is embedded once and switching palette costs nothing, instead of carrying a recoloured
    second copy of every tile.
    """
    import numpy as np
    a = np.asarray(im.convert("RGB"), float).reshape(-1, 3) / 255.0
    b = np.asarray(recolour(im, ref, mode), float).reshape(-1, 3) / 255.0
    x = np.hstack([a, np.ones((len(a), 1))])
    m, *_ = np.linalg.lstsq(x, b, rcond=None)                    # 4x3: rows r,g,b,offset
    # feColorMatrix wants 4 rows of 5: R' = r0*R + r1*G + r2*B + 0*A + offset
    return " ".join("%.5f" % v for v in (
        m[0, 0], m[1, 0], m[2, 0], 0, m[3, 0],
        m[0, 1], m[1, 1], m[2, 1], 0, m[3, 1],
        m[0, 2], m[1, 2], m[2, 2], 0, m[3, 2],
        0, 0, 0, 1, 0))


def palette_stats(im):
    """Per-channel mean and spread of one tile, the reference a transfer aims at."""
    import numpy as np
    lab = _to_lab(np.asarray(im.convert("RGB"), float) / 255.0)
    return [(float(lab[..., c].mean()), float(lab[..., c].std())) for c in range(3)]


def recolour(im, ref, mode):
    """Shift and scale each LAB channel to the reference's mean and spread (Reinhard).

    A per-pixel colour mapping: it restates the colour of a line, it cannot move one.
    """
    import numpy as np
    from PIL import Image
    lab = _to_lab(np.asarray(im.convert("RGB"), float) / 255.0)
    for c in (0, 1, 2) if mode == "full" else (1, 2):
        sd = lab[..., c].std()
        if sd > 1e-6:
            lab[..., c] = (lab[..., c] - lab[..., c].mean()) * (ref[c][1] / sd) + ref[c][0]
    lab[..., 0] = np.clip(lab[..., 0], 0, 100)
    return Image.fromarray((_to_rgb(lab) * 255).round().astype(np.uint8))


def bbox(path_d: str) -> tuple[float, float, float, float]:
    n = [float(v) for v in path_d.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    xs, ys = n[0::2], n[1::2]
    return min(xs), min(ys), max(xs), max(ys)


# Two feColorMatrix blocks and nothing else generate every state the wheel has. They are filters
# rather than extra artwork because a second diffusion pass is not deterministic: two merges of
# one pair differ by edge-difference 13.0, so a generated "lit" tile would redraw itself under
# the cursor. A filter leaves the drawing alone.
# HOW FAR THE EIGHT ARE HELD BACK FROM THE CITY'S PRESENTATION, as one knob.
#
# This was the answer to "the city looks coloured and the duty tiles do not", and the palette
# transfer -- the obvious suspect -- was not the cause. Measured on the assembled wheel, version C:
#
#                        the eight            the city
#                    L med  C p90  C p99    L med  C p90  C p99
#   saturate 0.40     57.3    5.1   10.9     58.1   22.3   36.7
#   saturate 0.70     57.4   10.2   29.7       "      "      "
#   saturate 1.00     57.5   13.7   37.0       "      "      "
#
# All of this art is near-neutral by prompt -- the city's own MEDIAN chroma is 4.0. Its colour is
# a top-decile event, a warm sky over grey stone, and `saturate` acts hardest exactly there. At
# 0.40 the eight kept 10.9 of the city's 36.7 at the 99th percentile, so the one thing that makes
# this palette read as coloured was the one thing being removed, and the tiles went cold blue-grey
# against a warm city. At 1.00 the top end matches within 0.3.
#
# Turning the PALETTE off instead makes it worse, not better: the eight then keep their own tonal
# key and sit at L 40.9 against the city's 58.1. The transfer is what lifts them to its level.
#
# The cost is hover headroom, and it is real: mean lit-vs-resting difference falls 24.6 -> 19.3,
# about a fifth. 0.70 is the middle if the hover ever feels weak.
DIM_SATURATE = 1.00


def _dim(sat: float) -> str:
    """The resting filter at a given saturation, with its tonal nudge scaled to match.

    One knob rather than two, because the nudge is part of holding a tile back and has no meaning
    on its own: at sat 1.00 it interpolates to identity, so the eight get the city's treatment
    exactly rather than its colour plus a leftover cold cast. At 0.40 it reproduces the original
    filter byte for byte, which is what makes this a setting and not a rewrite.
    """
    t = (1.0 - sat) / 0.60                      # 0 at sat 1.00, 1 at sat 0.40
    f = [("R", 1 - 0.06 * t, 0.005 * t),
         ("G", 1 - 0.04 * t, 0.010 * t),
         ("B", 1 + 0.02 * t, 0.025 * t)]
    return ('<feColorMatrix type="saturate" values="%.2f"/><feComponentTransfer>' % sat
            + "".join('<feFunc%s type="linear" slope="%s" intercept="%s"/>'
                      % (c, ("%.2f" % s).lstrip("0") or "0", ("%.3f" % i).lstrip("0") or "0")
                      for c, s, i in f)
            + '</feComponentTransfer>')


DIM = _dim(DIM_SATURATE)
LIT = ('<feColorMatrix type="saturate" values="1.20"/><feComponentTransfer>'
       '<feFuncR type="linear" slope="1.34" intercept=".10"/>'
       '<feFuncG type="linear" slope="1.14" intercept=".055"/>'
       '<feFuncB type="linear" slope=".78" intercept="0"/></feComponentTransfer>')
# Hover lights ONE ACTION, not one tile: a two-action tile has a left half and a right half, and
# lighting the whole of it would say the cursor had picked both.
#
# The picker drives this from a mousemove handler, which this file cannot do -- it has to stay a
# self-contained <svg> that the layout tool drops into a slot, with no page script to pair with.
# So the halves are hit areas stacked over the art and the lighting is selected by `:has()`,
# which needs no script at all. Chrome 105+, Safari 15.4+, Firefox 121+; where `:has()` is
# missing nothing lights and the board is merely static, which is the right way to fail.
# The edge, named rather than written twice. Both numbers below were literals at their use sites
# until a second page needed to draw the same edge: gen_border_studio lays candidate markings over
# it, and a studio whose baseline is a different weight or a different gold from the board's is
# measuring against the wrong thing. That is the fault this tree keeps paying for, so the values
# live here and both readers take them from here.
EDGE_STROKE = 0.0035        # of the box, so 3.5 units at the traced 1000
EDGE_HOVER = "#d8b23a"      # gold, and the ONLY thing on the board that says "yours to take"

HOVER_CSS = ('.dgt .dg-lit{opacity:0}'
             '.dg-hit{fill:transparent}'
             '.dgt:not([data-eligible="0"]):has(.dg-hit-f:hover) .dg-lit-F{opacity:1}'
             '.dgt:not([data-eligible="0"]):has(.dg-hit-l:hover) .dg-lit-L{opacity:1}'
             '.dgt:not([data-eligible="0"]):has(.dg-hit-r:hover) .dg-lit-R{opacity:1}'
             '.dgt:not([data-eligible="0"]):has(.dg-hit:hover) .dg-edge{stroke:' + EDGE_HOVER +
             ';stroke-opacity:1}')
# Where a two-action tile's scenes meet, as a fraction of its width. Measured: every source pair
# splits at 0.4993-0.5035 and every merge keeps it, so this is 0.5 and joins.json records why.
# Read rather than assumed, so a tile that ever genuinely differs is one file away.
# Switching palette is a class change, not a re-render: each tile carries a palette wrapper for
# every mode and CSS decides which one is live. `filter:none` as a CSS property beats the SVG
# `filter` presentation attribute, which is what lets "none" turn them all off.
PALETTE_CSS = ('.dg-pal{filter:none}'
               'svg[data-palette="chroma"] .dg-pal-chroma{filter:var(--dg-pal)}'
               'svg[data-palette="full"] .dg-pal-full{filter:var(--dg-pal)}')

# ---------------------------------------------------------------------------------------------
# MARKING A TILE, for the two states this wheel does not carry yet: which duties the active seat
# may act on, and which it may lift acolytes from. Both want the tile's edge, and the edge already
# means one thing -- EDGE_HOVER gold, on hover, gated on data-eligible -- so a persistent mark has
# to read as a different KIND of signal rather than a different shade. `MARK_FILL` is the emerald
# designed for that, at hue 146.
#
# INERT UNTIL A PAGE ASKS. Nothing below animates on its own: every rule needs `data-mark="1"` on a
# tile AND `data-mark-effect` on the svg, and this file sets neither. That is deliberate. This
# component is dropped into pages that have no script to pair with -- the layout tool slots it into
# a simulated screen, the picker shows two of them at once -- and a wheel that started animating
# because it was embedded would be a component with an opinion about its own page.
#
# WHY IT LIVES HERE AND NOT IN THE PAGES. Two pages draw it: the game view, and gen_border_studio,
# whose entire claim is that a choice made in it is a choice about the board. That claim holds only
# while both draw the same rings from the same rules. A second copy is the fault this tree has paid
# for three times, and the studio exists because of two scripts that died of it.
MARK_FILL = "#4BA672"       # hue 146 deg -- see the note above about the gold
MARK_PATH_LENGTH = 1000     # every marked path declares this, so one dash means one length
MARK_DASH = (44, 28, 20, 62, 34, 36, 16, 74, 24, 54, 18, 68)
MARK_PERIOD = 200.0         # of MARK_PATH_LENGTH, so the fixed pattern repeats with no seam
MARK_SEGMENTS = 9           # the wave-driven variant
MARK_SEGMENTS_V2 = 18       # half the run length; see gen_border_studio for the arithmetic
MARK_ANTS = 14              # the marching-ants dash, which v2 is sized against

MARK_EFFECTS = (("", "none"),
                ("portal", "portal ring + four dots"),
                ("segments", "portal ring, dynamic segments"),
                ("segmentsv2", "portal ring, dynamic segments v2"),
                ("steady", "steady"),
                ("pulse", "pulse"),
                ("ants", "marching ants"))


def mark_dash(raw=MARK_DASH, period=MARK_PERIOD) -> str:
    """The fixed portal pattern, rescaled to divide MARK_PATH_LENGTH a whole number of times.

    The effect this came from sums to 478 against a circumference of 754, so its pattern restarts
    part-way round and leaves a seam. Invisible on a smooth ring; here it would be nine seams in
    nine places and would read as the artwork being wrong rather than the dashes.
    """
    k = period / sum(raw)
    return " ".join("%.2f" % (v * k) for v in raw)


def mark_defs(uid: str) -> str:
    """The gradient and filters the marking needs, id-prefixed like everything else in this file."""
    return (f'<linearGradient id="{uid}-mg" x1="0%" y1="0%" x2="100%" y2="100%">'
            f'<stop class="dg-ms" offset="0%" stop-opacity=".28"/>'
            f'<stop class="dg-ms" offset="20%" stop-opacity=".95"/>'
            f'<stop class="dg-ms" offset="45%" stop-opacity=".70"/>'
            f'<stop class="dg-ms" offset="70%" stop-opacity=".78"/>'
            f'<stop class="dg-ms" offset="100%" stop-opacity=".28"/></linearGradient>'
            f'<filter id="{uid}-mglow" x="-40%" y="-40%" width="180%" height="180%">'
            f'<feGaussianBlur stdDeviation="2.4" result="b"/><feMerge>'
            f'<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'<filter id="{uid}-msoft" x="-60%" y="-60%" width="220%" height="220%">'
            f'<feGaussianBlur stdDeviation="11"/></filter>'
            f'<filter id="{uid}-mdot" x="-300%" y="-300%" width="600%" height="600%">'
            f'<feGaussianBlur stdDeviation="3.4" result="b"/><feMerge>'
            f'<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')


def mark_vars(uid: str) -> str:
    """Those ids as custom properties on the svg root, so MARK_CSS can stay a constant.

    Same arrangement PALETTE_CSS uses, and for the same reason: an inline <style> inside an SVG is
    DOCUMENT-scoped, so two wheels on one page share one stylesheet and the last one written would
    otherwise win for both. Names in the rules, ids on the element.
    """
    return (f"--dg-mgrad:url(#{uid}-mg);--dg-mglow:url(#{uid}-mglow);"
            f"--dg-msoft:url(#{uid}-msoft);--dg-mdot:url(#{uid}-mdot)")


def mark_paths(d: str) -> str:
    """One tile's marking: the plain stroke, the two portal rings, and four dots to ride the edge.

    All five are emitted whatever the effect, and each rule below turns on only what it needs. The
    alternative -- emitting per effect -- would mean the markup changed when the dropdown did, and
    the dropdown is a page thing.
    """
    # pointer-events="none" for the reason the acolyte row carries it, and it matters more here.
    # The mark straddles the outline, so half its width lies OUTSIDE the tile where the hit rect's
    # clip ends -- and the portal's dots orbit out there too, under a glow, MOVING. A decoration
    # that can take the pointer would make the hover flicker as a dot passed beneath the cursor,
    # which is a fault that only appears on marked tiles, only near the edge, and only sometimes.
    # Measured before this line existed: a point on the outline resolved to `.dg-mring`.
    pl = MARK_PATH_LENGTH
    out = [f'<g class="dg-mark" pointer-events="none" style="--dg-p:path(\'{d}\')">']
    for cls in ("dg-m", "dg-mring-soft", "dg-mring"):
        out.append(f'<path class="{cls}" d="{d}" pathLength="{pl}"/>')
    for k in range(1, 5):
        out.append(f'<circle class="dg-mdot dg-md{k}" cx="0" cy="0" r="7"/>')
    out.append("</g>")
    return "".join(out)

# Scoped to `[data-mark="1"]` on the tile and `[data-mark-effect]` on the svg. A page marks tiles
# by setting the first and picks an effect with the second; absent either, every rule below is
# inert and the marking costs nothing but markup.
MARK_CSS = (
    '.dg-ms{stop-color:var(--dg-mc,' + MARK_FILL + ')}'
    '.dg-m,.dg-mring,.dg-mring-soft{fill:none;stroke:var(--dg-mc,' + MARK_FILL + ');'
    'stroke-linejoin:round;stroke-linecap:round;opacity:0}'
    '.dg-m{stroke-width:calc(var(--dg-msw,3.5)*1.7)}'
    '.dg-mdot{fill:var(--dg-mc,' + MARK_FILL + ');opacity:0}'
    '.dgt:not([data-mark="1"]) .dg-mark{display:none}'

    'svg[data-mark-effect=steady] [data-mark="1"] .dg-m{opacity:.95}'
    'svg[data-mark-effect=pulse] [data-mark="1"] .dg-m{opacity:.95;'
    'animation:dg-pulse var(--dg-mdur,1800ms) ease-in-out infinite}'
    '@keyframes dg-pulse{0%,100%{opacity:.30}50%{opacity:1}}'
    'svg[data-mark-effect=ants] [data-mark="1"] .dg-m{opacity:.95;stroke-dasharray:'
    + str(MARK_ANTS) + ' 12;animation:dg-ants var(--dg-mdur,1800ms) linear infinite}'
    '@keyframes dg-ants{to{stroke-dashoffset:-' + str(MARK_ANTS + 12) + '}}'

    'svg[data-mark-effect^=segments] [data-mark="1"] .dg-mring-soft,'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-mring-soft{opacity:1;stroke-opacity:.16;'
    'stroke-width:calc(var(--dg-msw,3.5)*3.4);filter:var(--dg-msoft)}'
    'svg[data-mark-effect^=segments] [data-mark="1"] .dg-mring,'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-mring{opacity:1;stroke:var(--dg-mgrad);'
    'stroke-width:calc(var(--dg-msw,3.5)*1.5);filter:var(--dg-mglow)}'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-mring,'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-mring-soft{stroke-dasharray:'
    + mark_dash() + ';animation:dg-orbit calc(var(--dg-mdur,1800ms)*6.1) linear infinite}'
    '@keyframes dg-orbit{from{stroke-dashoffset:0}to{stroke-dashoffset:-'
    + ("%g" % MARK_PERIOD) + '}}'

    'svg[data-mark-effect=portal] [data-mark="1"] .dg-mdot{offset-path:var(--dg-p);'
    'offset-rotate:0deg;filter:var(--dg-mdot)}'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-md1{animation:'
    'dg-ride calc(var(--dg-mdur,1800ms)*3.8) linear infinite,'
    'dg-p1 calc(var(--dg-mdur,1800ms)*1.2) ease-in-out infinite alternate}'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-md2{offset-distance:25%;animation:'
    'dg-ride calc(var(--dg-mdur,1800ms)*5.3) linear infinite reverse,'
    'dg-p2 calc(var(--dg-mdur,1800ms)*1.6) ease-in-out infinite alternate}'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-md3{offset-distance:50%;animation:'
    'dg-ride calc(var(--dg-mdur,1800ms)*4.4) linear infinite,'
    'dg-p3 calc(var(--dg-mdur,1800ms)*1.3) ease-in-out infinite alternate-reverse}'
    'svg[data-mark-effect=portal] [data-mark="1"] .dg-md4{offset-distance:75%;animation:'
    'dg-ride calc(var(--dg-mdur,1800ms)*6.3) linear infinite reverse,'
    'dg-p4 calc(var(--dg-mdur,1800ms)*1.7) ease-in-out infinite alternate}'
    '@keyframes dg-ride{from{offset-distance:0%}to{offset-distance:100%}}'
    '@keyframes dg-p1{0%{opacity:.35;r:6px}50%{opacity:.95;r:8.4px}100%{opacity:.45;r:6.8px}}'
    '@keyframes dg-p2{0%{opacity:.18;r:4.6px}50%{opacity:.58;r:6.2px}100%{opacity:.26;r:5.2px}}'
    '@keyframes dg-p3{0%{opacity:.22;r:4.4px}50%{opacity:.74;r:7px}100%{opacity:.31;r:5.2px}}'
    '@keyframes dg-p4{0%{opacity:.16;r:4.1px}50%{opacity:.50;r:5.7px}100%{opacity:.21;r:4.6px}}'

    # Reduced motion has to be honoured HERE rather than left to the page, because the page cannot
    # see these rules. The segment loop checks the same query itself -- it has no keyframes to
    # suppress -- so both halves of the effect stop for the same reason.
    '@media (prefers-reduced-motion:reduce){'
    '[data-mark="1"] .dg-m,[data-mark="1"] .dg-mring,[data-mark="1"] .dg-mring-soft,'
    '[data-mark="1"] .dg-mdot{animation:none!important}'
    '[data-mark="1"] .dg-m{opacity:.95;stroke-dasharray:none;stroke-dashoffset:0}'
    '[data-mark="1"] .dg-mdot{opacity:0}}')


# The one effect that cannot be keyframes, and therefore the one thing here that needs a page.
#
# `segments` builds its dash array every frame from three sine waves at rates sharing no common
# period, then scales the array to fit MARK_PATH_LENGTH exactly. That last step is what removes the
# seam -- the pattern always closes on itself -- and it is also why one computation drives every
# marked tile: normalised, the same string means the same thing on all nine outlines.
#
# CSS can interpolate between two states. It cannot be a function of time, and a figure that never
# comes back round is not expressible as keyframes. So this is a script, and a page that wants that
# effect has to run it; `duty_grid_svg` emits no script of its own.
MARK_JS = """
window.dgMark = (function(){
  var raf = 0, reduced = matchMedia('(prefers-reduced-motion: reduce)');
  var SEG = %d, SEG2 = %d, PLEN = %d;
  function pulse(x){ return 0.5 + 0.5 * Math.sin(x); }
  function dashArray(t, n){
    var v = [], total = 0;
    for(var i = 0; i < n; i++){
      var p = i * 0.83;
      var lit = 14 + 24*pulse(t*1.15 + p) + 12*pulse(t*0.63 + p*1.9 + 0.7)
                   + 8*pulse(t*1.87 + p*0.55 + 1.3);
      var gap = 18 + 20*pulse(t*0.84 + p*1.4 + 2.1) + 10*pulse(t*1.42 + p*0.9 + 0.4);
      v.push(lit, gap); total += lit + gap;
    }
    var k = PLEN / total;
    return v.map(function(x){ return (x*k).toFixed(2); }).join(' ');
  }
  // Clearing the inline styles on the way out is not tidiness. Inline beats the stylesheet, so a
  // dash array left behind here would override the one `ants` sets and quietly corrupt every other
  // effect -- visible only after visiting this one first.
  function clear(svg){
    var r = svg.querySelectorAll('.dg-mring, .dg-mring-soft');
    for(var i = 0; i < r.length; i++){
      r[i].style.strokeDasharray = ''; r[i].style.strokeDashoffset = '';
    }
  }
  return function(svg, effect, durMs){
    if(raf){ cancelAnimationFrame(raf); raf = 0; }
    clear(svg);
    if(!svg || !effect || effect.indexOf('segments') !== 0 || reduced.matches) return;
    var n = effect === 'segmentsv2' ? SEG2 : SEG, dur = durMs || 1800;
    (function frame(ms){
      var t = ms / 1000 * (1800 / dur);
      var d = dashArray(t, n);
      var o = (-42*t - 10*Math.sin(t*0.55)).toFixed(2);
      var r = svg.querySelectorAll('[data-mark="1"] .dg-mring, [data-mark="1"] .dg-mring-soft');
      for(var i = 0; i < r.length; i++){
        r[i].style.strokeDasharray = d; r[i].style.strokeDashoffset = o;
      }
      raf = requestAnimationFrame(frame);
    })(performance.now());
  };
})();
""" % (MARK_SEGMENTS, MARK_SEGMENTS_V2, MARK_PATH_LENGTH)

JOINS = TILES / "joins.json"
# Where each tile sits, and how big it is relative to its square. Written by
# `gen_tile_offsets.py --serve` and read here, for the same reason ui/layout.json is: without the
# file this would be numbers retyped from a tool into a generator by hand, which is two sources of
# truth. The tile SCALE opens the channel below each tile for the acolyte row; the OFFSETS are
# per-tile nudges judged by eye, and the file itself records what they turned out to be.
OFFSETS = HERE.parent / "duty_tile_offsets.json"


def tile_placement(path: pathlib.Path = OFFSETS, box: float = 1000.0):
    """(scale, {i: (dx, dy)}, (sx, sy)) in GRID UNITS, or (1.0, {}, (0, 0)) when there is no file.

    THE THIRD VALUE IS THE WHOLE ARRANGEMENT'S POSITION, and it is a different kind of number from
    the nine. A per-tile offset says where one tile sits against its own acolyte row; the shift
    says where all nine, rows included, sit inside the box. So it is applied whether or not the
    per-tile offsets are -- `offsets=False` means "without the nudges", not "somewhere else
    entirely". That is what keeps the acolytes still relative to the tiles while the block moves:
    the rows are derived from the unoffset shapes, which carry the shift too.

    The file stores screen pixels, because that is what the eye judges in and what the tool's
    pointer moves in. The conversion needs the size the wheel was judged at, so the file records
    it rather than this guessing: a set of offsets measured on an 877.8 px wheel and applied as if
    they were grid units would be out by a factor of 1.14, which is small enough to look like a
    slightly wrong drag and not like a unit error.
    """
    if not path.is_file():
        return 1.0, {}, (0.0, 0.0)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit("%s is not valid JSON: %s" % (path, exc))
    per_unit = box / float(data.get("wheel_px") or box)
    out = {}
    for k, v in (data.get("offsets") or {}).items():
        if str(k).isdigit() and 0 <= int(k) < 9:
            out[int(k)] = (float(v.get("dx", 0)) * per_unit, float(v.get("dy", 0)) * per_unit)
    sh = data.get("arrangement_shift") or {}
    shift = (float(sh.get("dx", 0)) * per_unit, float(sh.get("dy", 0)) * per_unit)
    return float(data.get("tile_scale") or 1.0), out, shift


# THE ACOLYTE ROW. One PILE of figures under each tile per seat -- one figure per acolyte.
#
# The figure is the population asset itself, duotoned per seat, not a drawn token: four attempts at
# a drawn hood all read as a user-avatar icon at this size, and the asset already is the acolyte.
# It is 228 x 210 -- WIDER than tall -- and that is what makes the row affordable: the channel
# between two rows of tiles constrains height, not width.
#
# The duotone strength is measured, not chosen. Downsampled to the drawn size, the first attempt
# kept only 42% of each seat's chroma and the four read as grey-brown triangles; this keeps 66%.
# Pushing to 81% makes them poster-flat, plum worst.
ACOLYTE = HERE.parent / "assets-gothic" / "population" / "acolyte_gothic.png"
# THE DEFAULT SET'S OWN NUMBERS, not a second copy of them. These names stay because a dozen
# call sites and guards read them, and what they mean is unchanged: the wheel as it is drawn
# when nobody asks for anything else. A second set is `pop_set=` on the functions below.
ACOLYTE_ASPECT = pop.tile()["aspect"]
FIG_FRAC = pop.tile()["frac"]          # figure width as a fraction of the tile's width
FIG_OVERLAP = pop.tile()["overlap"]    # how much sits above the tile's bottom edge
# ONE TABLE, read from population_sets. The player card fills its hooded acolytes from the same
# one, and a wheel and a card disagreeing about plum is not a thing anyone would go looking
# for. The names stay here because everything in this file and its guards reads them.
SEAT_SWATCH = pop.SEAT_SWATCH
SEAT_ORDER = pop.SEAT_ORDER
# How a count is drawn: one figure per acolyte, piled upward, and no numeral anywhere. See
# `acolyte_row` for why five acolytes are five figures rather than one figure and a 5.
#
# STACK_STEP is the whole design, and the floor under it is a property of the artwork rather than
# a matter of taste. The acolyte's silhouette widens monotonically -- 9% of its width at the crown,
# 100% at the hem -- so copies offset by a small step merge into ONE larger triangle. At 0.26 a
# pile of five reads as a fir tree, not as five; a buried figure shows only its top STACK_STEP of
# height, and that band has to clear the hood before a second face appears at all.
#
# The cost is tile art, and it is the ONLY cost: the pile grows upward, so the foot never moves
# and the action box cut to that line never moves either. As a fraction of the tile's own height:
#
#                       n=3    n=5    n=7    n=9
#   step 0.26           24%    35%    46%    57%   crowns merge, reads as one shape
#   step 0.30 + lean    26%    38%    51%    64%   <- here
#   step 0.40           30%    47%    64%    81%
#   step 0.55           36%    60%    83%   106%   climbs off the top of the tile
#
# NOTHING CAPS A DUTY'S COUNT, and the top of that range is not drawn well. A sow places one
# acolyte per STEP of its route; the route is a free walk on a board graph with two four-cycles
# through the City, so a position visited twice takes two acolytes -- five picked up from the City
# puts two on north in a single sow, and four is the most one sow can add anywhere (thirteen
# picked up, lapping twice). Counts accumulate on top of that, so the ceiling the rules allow is a
# player's entire pool on one duty: 16, being 5 in the city, 3 in the abbey and 8 in the village
# with the village -> abbey -> city pipeline able to move all of them.
#
# At this step that pile is 104% of its own tile's height at 14 and is clipped by the wheel's box
# at 16, by 1.8 units. Both are ACCEPTED: a board with every acolyte a player owns on one duty is
# not a board anyone will play, and Adam decided that rather than me. There is no guard on it,
# also deliberately -- the only threshold available was one invented for the purpose, and it let a
# step of 0.34 through while catching 0.45. A guard that fires only on a change someone would make
# deliberately, having read this table, protects nothing. These numbers are the protection: a
# larger step buys separation and spends it here, and the count where it starts to cost is
#
#     step 0.30   clips at 16      step 0.34   clips at 15      step 0.45   clips at 11
#
# STACK_LEAN is what buys 0.30 the readability that 0.40 otherwise needs the extra height for:
# alternating sides gives each figure an edge the one below it does not have, so the silhouette
# breaks where the step alone would not separate it. It is not free -- it widens a pile by twice
# itself into a gap of 0.24 of a figure, and `acolyte_row` states the clearance that leaves.
STACK_STEP = pop.tile()["step"]        # of a figure's HEIGHT, one acolyte to the next
STACK_LEAN = pop.tile()["lean"]        # of a figure's WIDTH, alternating side to side
_TINTS: dict[str, str] | None = None


def acolyte_tints() -> dict[str, str]:
    """The acolyte in four seat duotones, as data URIs, built from the one asset and cached.

    Built rather than committed as four more files: they are derived, and four derived PNGs in the
    tree are four things to regenerate when the seat colours move. Generated at the asset's NATIVE
    size, so every drawn size is a downsample -- above about 114 px drawn at 2x it would start
    interpolating and the figure should be redrawn rather than enlarged.
    """
    global _TINTS
    if _TINTS is not None:
        return _TINTS
    import colorsys
    import io

    import numpy as np
    from PIL import Image, ImageFilter

    src = Image.open(ACOLYTE).convert("RGBA")
    out = {}
    for seat, hexv in SEAT_SWATCH.items():
        r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        dark = colorsys.hsv_to_rgb(h, min(1, s * 1.3), v * 0.30)
        light = colorsys.hsv_to_rgb(h, min(1, s * 0.95), min(1, v * 1.10))
        a = np.asarray(src).astype(float)
        lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]) / 255.0
        lum = np.clip((lum - 0.06) / 0.84, 0, 1) ** 0.80
        o = np.zeros_like(a)
        for c in range(3):
            o[..., c] = (dark[c] + (light[c] - dark[c]) * lum) * 255
        o[..., 3] = a[..., 3]
        fig = Image.fromarray(o.astype("uint8"), "RGBA")
        # A dark silhouette behind it. NOT decoration: pewter and plum fall to 1.2 : 1 against the
        # brightest tile bottom (Give Alms, L 91) and would vanish without it.
        alpha = np.asarray(fig)[..., 3]
        halo = Image.fromarray(alpha).filter(ImageFilter.MaxFilter(13))
        sil = Image.new("RGBA", fig.size, (0x22, 0x1c, 0x16, 255))
        sil.putalpha(halo)
        base = Image.new("RGBA", fig.size, (0, 0, 0, 0))
        base.alpha_composite(sil)
        base.alpha_composite(fig)
        buf = io.BytesIO()
        base.save(buf, "PNG")
        out[seat] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    _TINTS = out
    return out


HOOD_STROKE = 0.055           # of a figure's width, centred on the outline


def hood_defs(uid: str = "dg", seats: tuple[str, ...] = SEAT_ORDER) -> str:
    """The hooded mark in each seat's colour, defined once per svg for `<use>`.

    ONE UNIT WIDE with its crown at y=0, so the `<use>` that places it needs only a translate and
    a scale by the figure width -- the same two numbers the `<image>` of the other set is given.

    THE OUTLINE IS NOT DECORATION, and it is the same argument the gothic figure's halo is built
    on: pewter and plum fall to 1.2 : 1 against the brightest tile bottom (Give Alms, L 91) and
    would vanish without something dark around them. `acolyte_tints` dilates the asset's alpha by
    6 px of its 228 to get it; 0.055 of a width, centred, puts the same 2.6% outside the shape.

    The face is a flat 22% black rather than a fourth colour per seat, measured off the mock-up:
    its plum body is (138, 90, 146) and its face (106, 70, 109), a ratio of 0.77.
    """
    out = []
    d = pop.hood_path()
    f = pop.HOOD_FACE
    for seat in seats:
        out.append(
            f'<g id="{uid}-hood-{seat}">'
            f'<path d="{d}" fill="{SEAT_SWATCH[seat]}" stroke="{INK}" '
            f'stroke-width="{HOOD_STROKE}" stroke-linejoin="round"/>'
            f'<ellipse cx="0" cy="{f["cy"]}" rx="{f["rx"]}" ry="{f["ry"]}" '
            f'fill="#000" opacity="0.22"/></g>')
    return "".join(out)


def pop_defs(uid: str = "dg", pop_set: str | None = None,
             seats: tuple[str, ...] = SEAT_ORDER) -> str:
    """Whatever the chosen set has to define before a row can `<use>` it.

    Empty for a set that draws images, because a data URI needs no defs. A page that draws the
    hood set and forgets this renders NO ACOLYTES AT ALL -- an unresolved `<use>` is silent -- and
    a board with no acolytes is a board somebody will believe. The id guard in the duty-wheel
    tests is what catches it: every `url(#...)` and `href="#..."` must name an id the same svg
    defines.
    """
    return hood_defs(uid, seats) if pop.tile(pop_set)["kind"] == "hood" else ""


def acolyte_box(shape: str, seats: tuple[str, ...] = SEAT_ORDER,
                pop_set: str | None = None) -> dict:
    """Where one tile's row sits: {sx, sy, fw, fh, gap}, in grid units.

    SIZED BY HOW MANY SEATS ARE IN THE GAME, not always four. Pilgrim seats two to four, and a
    two-player board drawing four figures would be showing two players who do not exist.

    The figure itself does NOT grow when there are fewer of them. A figure is a figure; two
    players should see the same acolyte as four, with more ground either side, not a bigger one.

    Two things are invariant under the seat count, and both are load-bearing rather than
    incidental:

        the row's centre   `sx + span/2` is the tile's own centre whatever `span` is, so a row of
                           two sits where a row of four sat. That is what lets the per-tile offsets
                           in duty_tile_offsets.json mean the same thing at every player count --
                           they were judged at four and are not re-judged at two.
        the foot           `sy + fh` has no seat term in it at all. gen_game_view cuts the action
                           box to that line, so the board's layout cannot shift because a player
                           joined or left.

    THE ONE PLACE THIS IS WORKED OUT. It was two: this file emitted the row and the drag tool
    computed an identical copy to lay its frozen grid out against, with FIG_FRAC, the overlap and
    the aspect written down twice as well. They agreed, which is the only interesting moment to
    merge them -- once they disagree the tool is showing rows the board does not draw, and every
    offset judged in it is judged against the wrong thing. That exact fault has already happened
    here once, with `place`.

    The shape passed in is the tile BEFORE its per-tile offset. Deliberately: the grid is frozen,
    and an earlier version derived each row from its own tile's offset bounding box, so moving a
    tile moved its row with it and the relationship the offsets exist to set was invariant. Tiles
    move; the row does not. The ARRANGEMENT shift does move it, because that is carried in the
    unoffset shapes themselves.
    """
    n = [float(v) for v in shape.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    xs, ys = n[0::2], n[1::2]
    x0, x1, y1 = min(xs), max(xs), max(ys)
    w = x1 - x0
    m = pop.tile(pop_set)
    fw = w * m["frac"]
    fh = fw / m["aspect"]
    gap = fw * m["gap"]
    k = len(seats)
    return {"sx": x0 + (w - (k * fw + (k - 1) * gap)) / 2, "sy": y1 - fh * m["overlap"],
            "fw": fw, "fh": fh, "gap": gap}


def acolyte_foot(meta: dict | None = None, margin: float | None = None,
                 pop_set: str | None = None) -> float:
    """The lowest acolyte ink on the board, in grid units. The bottom of the drawn block.

    The tiles are not the bottom of this component -- the figures hang below the last row of them
    -- so anything on the board that wants to line up with what the eye sees as the wheel's foot
    has to ask for this rather than for the box.
    """
    return max(acolyte_box(d, pop_set=pop_set)["sy"]
               + acolyte_box(d, pop_set=pop_set)["fh"]
               for d in laid_shapes(meta, margin, offsets=False))


def acolyte_row(shape: str, counts, seats: tuple[str, ...] = SEAT_ORDER,
                pop_set: str | None = None, uid: str = "dg") -> str:
    """One row under a tile, drawn: a seat's count is that many FIGURES, piled upward.

    THERE IS NO NUMERAL. A count used to be one figure with a small number on its robe, and the
    number was the only part of it carrying information -- so reading the board meant reading
    thirty-six numerals and doing the arithmetic. What a player is actually asking is "who has
    the most here, and will sowing this way change that", and a pile answers it without being
    read: four against two is a taller heap next to a shorter one. That is the entire reason for
    this shape, and it is why the numeral is gone at EVERY count rather than kept as a fallback
    above some threshold -- a mixed scheme would make the tall piles the ones you have to read.

    The price is paid in tile art and nothing else. The pile grows UPWARD from the line the single
    figure stood on, so `sy + fh` is untouched: the foot has no count term, the same way it has no
    seat term, and gen_game_view cuts the action box to it.

    A SEAT WITH NO ACOLYTES HERE IS DRAWN AS NOTHING. A row of figures each labelled 0 said "four
    players, none of them here" and "four players, one of them here" with the same picture until
    four small numbers were read; with no numerals left, an empty slot is now the ONLY thing
    distinguishing those two boards, so it matters more than it did, not less.

    The others do NOT close up around it. Each seat keeps the slot its position in `seats` gives
    it, so a gap means a specific player is missing rather than merely that somebody is: the
    second pile is the second seat on every tile on the board, which is what makes a row readable
    at a glance across nine of them. Reflowing would make every row a small puzzle.

    A PILE IS A COUNT OF ACOLYTES, NOT A MAJORITY, and the difference is not academic: comparing
    piles to see whether sowing a particular way wins a duty is the whole reason this is figures
    rather than numerals. Two buildings break that equivalence, and both are Duty Bonus rather
    than Movement, so neither changes the number this function is given:

        Scriptorium     "+1 to the acolyte total on all Duty tiles that player occupies" -- a
                        majority the player holds with nothing extra standing there
        Customs House   changes how a majority is CLAIMED when taking Taxation, not the counts

    Nothing is drawn for either, deliberately and with Adam's agreement: there is no acolyte to
    draw, and inventing a figure for one would be the numeral problem again in a worse form -- a
    picture that cannot be trusted as a count. The sketched answer is a "temporary" acolyte,
    marked as provisional by blinking or similar, and it is NOT built. Recorded here so that a
    reader who finds the wheel disagreeing with a majority knows it is a known gap rather than a
    bug in this file.
    """
    m = pop.tile(pop_set)
    b = acolyte_box(shape, seats, pop_set)
    sx, sy, fw, fh, gap = b["sx"], b["sy"], b["fw"], b["fh"], b["gap"]
    uris = acolyte_tints() if m["kind"] == "image" else None
    step, lean = fh * m["step"], fw * m["lean"]
    out = []
    for j, seat in enumerate(seats):
        n = int(counts[j])
        if n <= 0:
            continue
        x = sx + j * (fw + gap)
        # THE BOTTOM FIGURE DOES NOT LEAN. Only the ones resting on it do.
        #
        # Leaning all of them and centring the pile afterwards also works and is what this did
        # first, but it moves the figure standing on the line by half a lean whenever the count
        # changes -- so a seat going from one acolyte to two shifts its foot sideways, and the
        # row of feet the eye compares pile heights against stops being a row. Anchoring the
        # bottom one keeps every seat's foot exactly on its slot at every count, and it makes a
        # lone acolyte land where it always landed without needing a case for n == 1.
        side = [0.0 if n - 1 - i == 0 else (lean if (n - 1 - i) % 2 else -lean)
                for i in range(n)]
        # A pile is 2 * STACK_LEAN wider than one figure, against a gap of 0.24 of a figure:
        # 0.04 of a figure of clearance between neighbouring seats, 2.0 px at the drawn size.
        # That is bounding boxes; the ink clears by more, because the leaning figures are the
        # upper ones and a figure is 9% of its width at the crown. Guarded either way.
        out.append(f'<g class="dg-ac" data-seat="{seat}">')
        # Drawn top DOWN, so each figure is overlapped from below by the next and the one standing
        # on the line is whole. Painted the other way the pile reads as a row lying down.
        for i in range(n):
            fy = sy - (n - 1 - i) * step
            if uris is not None:
                out.append(
                    f'<image href="{uris[seat]}" x="{x + side[i]:.1f}" '
                    f'y="{fy:.1f}" width="{fw:.1f}" height="{fh:.1f}" '
                    f'preserveAspectRatio="xMidYMid meet"/>')
            else:
                # A <use> of the one hood this svg defines. The mark is DEFINED ONCE and
                # used up to sixteen times per tile; inlining its 96-point outline at every
                # acolyte would be about a kilobyte a head.
                out.append(
                    f'<use href="#{uid}-hood-{seat}" '
                    f'transform="translate({x + side[i] + fw / 2:.1f} {fy:.1f}) '
                    f'scale({fw:.2f})"/>')
        out.append('</g>')
    return "".join(out)


def laid_shapes(meta: dict | None = None, margin: float | None = None,
                offsets: bool = True) -> list[str]:
    """The nine shapes exactly as the board draws them: re-laid, scaled, and offset.

    THE ONE PLACE THAT ANSWERS "where are the tiles". gen_tile_offsets.py used to work this out for
    itself and got a different answer: it started from the raw traced shapes and skipped `place`,
    which re-lays the nine as an even 3x3 and spreads them apart -- by up to 25.6 screen px when
    that was measured, at MARGIN 14. So the
    tool showed a tighter arrangement than the board built, and offsets dragged in it were judged
    against tiles that were never where the board would put them. The numbers applied perfectly and
    the result still looked wrong, which is the hardest kind of wrong to find.
    """
    meta = meta or load()
    box = meta["box"]
    margin = MARGIN if margin is None else margin
    laid = meta["shapes"] if margin is None else place(meta["shapes"], box, margin)
    return placed(laid, box, offsets=offsets)


def placed(shapes: list[str], box: float, offsets: bool = True) -> list[str]:
    """The nine shapes scaled about their own centres and moved by their saved offsets.

    Scaling about each tile's OWN centre shrinks the picture without moving it, so the gaps between
    tiles grow by exactly what each tile gives up. That USED to be the source of most of what is in
    the offsets file: the spread was opened here and closed again by hand, nine tiles at a time.

    It is closed once now, in MARGIN -- see the block above it. This docstring previously described
    that as the alternative, "written down in the file rather than done here"; it has since been
    done, and the offsets re-dragged against it came back a third the size with no column signal
    left in them. What remains in the file is per-tile judgement, which is what it is for.
    """
    scale, off, (sx, sy) = tile_placement(box=box)
    if not offsets:
        off = {}
    # `sx, sy` is NOT dropped with them: it moves the whole block, acolyte rows and all, and those
    # rows are built from exactly this call with offsets=False. Dropping it here would leave the
    # rows behind when the arrangement moved, which is the one thing the shift must never do.
    if scale == 1.0 and not off and not (sx or sy):
        return shapes
    out = []
    for i, d in enumerate(shapes):
        n = [float(v) for v in d.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
        P = [(n[k], n[k + 1]) for k in range(0, len(n), 2)]
        cx = sum(x for x, _ in P) / len(P)
        cy = sum(y for _, y in P) / len(P)
        dx, dy = off.get(i, (0.0, 0.0))
        dx += sx
        dy += sy
        Q = [(cx + (x - cx) * scale + dx, cy + (y - cy) * scale + dy) for x, y in P]
        out.append("M" + " L".join("%.2f %.2f" % q for q in Q) + " Z")
    return out


def joins_for(version: str = VERSION, path: pathlib.Path = JOINS) -> dict[int, float]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): float(v) for k, v in data.get(version, {}).items() if not k.startswith("_")}

# The ground the nine tiles sit on, drawn as a single <rect> with a known id.
#
# `None` draws NO ground at all, and that is the setting to reach for when the ground belongs to
# the page rather than to the component: the slot's own background -- a colour now, a picture
# later -- shows straight through the channels, and swapping one for the other never touches this
# file. A colour here is for when the wheel must carry its own sheet regardless of what it sits on.
BACKGROUND: str | None = None
# How much ground is left outside the grid, in viewBox units. Everything else follows from it:
# the nine keep their traced sizes, the outer tiles go flush against this margin, and whatever
# is left over becomes the channels between them. Reclaiming the rim is the only way to widen
# those channels, because the total ground is fixed at 32.6% of the box -- tiles can be moved
# but not shrunk, so space comes from the edge or nowhere.
#
#   margin 26.8 (as traced)   channels 19/24 units
#   margin 14                 channels 30/49
#   margin  8                 channels 36/54
#
# Below about 10 the outer tiles start crowding whatever sits next to the wheel on the board.
#
# RAISED FROM 14 TO 33, and it is worth saying exactly what that number is.
#
# The nine tiles are scaled to 92% about their OWN centres, which shrinks each picture without
# moving it -- so every gap grows by what its two neighbours lost. The arrangement got looser
# while the art got smaller, and nobody asked for that. It was then closed again by hand, nine
# tiles at a time, in `duty_tile_offsets.json`.
#
# That put a property of the LAYOUT into a file of per-tile judgements, where it does not belong:
# it made eight of the nine offsets mostly arithmetic, and it meant any future change to the tile
# scale silently invalidated all of them. The spread belongs here, in the one constant that
# already means "how far apart are the nine".
#
# 33 is fitted, and fitted to something specific: it is the margin at which this 3x3 matches the
# spread the offsets were dragged against, to 6.5 px mean and 10.3 px worst. It is not derived
# from the tile scale -- contracting by 0.92 was tried first and lands 24.9 px out, WORSE than
# leaving it at 14 (20.1). The relationship the offsets actually encode, each tile's depth over
# its acolyte row, is exactly invariant under this constant (measured: +0.0 px on all nine),
# because a tile and its row move together. So this changes the arrangement and changes nothing
# about what a saved offset means.
#
# Measured at the wheel's drawn size (877.8 px), tiles at 92%, offsets applied -- which is why
# these do not compare with the `channels` column above, taken on unscaled tiles in grid units:
#
#                        side-by-side gap        above-below gap
#   margin 14            min 22.9  mean 33.4     min 32.4  mean 36.4
#   margin 26.8          min 11.6  mean 22.2     min 21.1  mean 25.2
#   margin 33            min  6.2  mean 16.7     min 15.7  mean 19.7   <- here
#
# 6.2 px is thin. It is the narrowest pair on the board and the floor for this constant: the
# acolytes stand in these channels, drawn over the tiles rather than between them, and the row
# below is what they would start to read against.
MARGIN = 33.0


def _points(d: str):
    n = [float(v) for v in d.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    return [[n[i], n[i + 1]] for i in range(0, len(n), 2)]


def _path(pts) -> str:
    return "M " + " L ".join("%.1f %.1f" % (x, y) for x, y in pts) + " Z"


def place(shapes: list[str], box: float, margin: float = MARGIN) -> list[str]:
    """Re-lay the nine outlines as an even 3x3, each keeping the exact size it was traced at.

    Translation only -- no scaling anywhere. The tiles were traced off a generated sheet whose
    own spacing was whatever the image tool drew, so their positions are an accident while their
    shapes are not. Row by row the three are pushed out until the outer two touch the margin and
    the gaps between them are equal; then the same down each column.

    Sizes differ (the widest tile is 312.6 units, the narrowest 298.3), so equal *gaps* leave the
    row's own margins slightly unequal against a neighbouring row. That is invisible on a torn
    edge and preferable to the alternative, which pins the margins and lets the channels drift.
    """
    pts = [_points(d) for d in shapes]

    def spread(axis: int, bands: list[list[int]]) -> None:
        for band in bands:
            lo = [min(p[axis] for p in pts[i]) for i in band]
            size = [max(p[axis] for p in pts[i]) - lo[k] for k, i in enumerate(band)]
            gap = (box - sum(size) - 2 * margin) / 2
            at = margin
            for k, i in enumerate(band):
                shift = at - lo[k]
                for p in pts[i]:
                    p[axis] += shift
                at += size[k] + gap

    spread(0, [[3 * r + c for c in range(3)] for r in range(3)])     # x, within each row
    spread(1, [[3 * r + c for r in range(3)] for c in range(3)])     # y, within each column
    return [_path(p) for p in pts]



def eligible_tiles(acolytes, active: str, seats: tuple[str, ...] = SEAT_ORDER) -> set[int]:
    """Which duties `active` may act on: the ones its own acolytes are standing on.

    DERIVED FROM THE COUNTS BEING DRAWN, rather than taken as a second parameter, and that is the
    whole design. The board already shows four seat figures with a number under every tile, so
    "the sage player has two acolytes on Clerical" is on screen. If eligibility arrived separately
    it could disagree with what the picture says -- a tile reading 2 that refuses the click, or a
    tile reading 0 that accepts one -- and nothing would raise. Deriving it makes that
    unrepresentable.

    Returned keyed by DUTY, which is the space the caller's counts are in and the space the tile
    groups are emitted in, so it can be used directly against them. It is NOT square space; see
    the note beside the acolyte rows.

    This is the only rule in here, and it is a rule about the drawing, not about the game: a seat
    with no acolytes on a duty has nothing to lift and nothing to spend. Anything narrower --
    a duty already used this turn, a phase that forbids it -- is the engine's to say, and belongs
    in a parameter that can only ever SHRINK this set, never grow it.
    """
    if active not in seats:
        raise ValueError(
            "active=%r is not one of the seats in this game (%s). A seat name that does not match "
            "reads every count from the wrong column -- or, at fewer than four players, from a "
            "column belonging to somebody who is not playing."
            % (active, ", ".join(seats)))
    if acolytes is None:
        raise ValueError(
            "active=%r was given without acolytes, so which duties it may act on is unknown. "
            "Refusing rather than treating every duty as available: a board that lets a player "
            "act everywhere is a legal-looking board, and nothing downstream would catch it."
            % (active,))
    seat = list(seats).index(active)
    got = acolytes if isinstance(acolytes, dict) else dict(enumerate(acolytes))
    live = set()
    for i, counts in got.items():
        i = int(i)
        if not (0 <= i < 9) or counts is None:
            continue
        if len(counts) != len(seats):
            raise ValueError(
                "acolytes[%r] has %d counts; there are %d seats (%s)."
                % (i, len(counts), len(seats), ", ".join(seats)))
        if int(counts[seat]) > 0:
            live.add(i)
    return live


def duty_grid_svg(meta: dict | None = None, klass: str = "wheel",
                  labels: list[str] | None = None, tiles_dir: pathlib.Path | None = TILES,
                  version: str = VERSION, px: int = 448,
                  margin: float | None = MARGIN, background: str = BACKGROUND,
                  palette: str | None = PALETTE,
                  palettes: tuple[str, ...] = ("chroma", "full"),
                  acolytes: list[list[int]] | dict[int, list[int]] | None = None,
                  # False draws the tiles WITHOUT the saved offsets, for a caller that applies
                  # them itself. gen_tile_offsets.py is the one: it moves tiles live with a
                  # transform, so the shapes it starts from must not already carry the file's
                  # numbers or every offset lands twice.
                  offsets: bool = True,
                  # Which population set draws the acolyte rows. None is the default set and
                  # the board is byte-identical to what it was before sets existed.
                  pop_set: str | None = None,
                  cells: list[int] | None = None,
                  # The seat whose turn it is. Given, only the duties that seat's own acolytes
                  # stand on stay live; every other tile is drawn exactly as now and simply does
                  # not respond. Left None, all nine respond, which is what every caller got
                  # before this existed and what the pickers still want.
                  active: str | None = None,
                  # Who is actually playing. Two to four; None means all four. The row under each
                  # tile is drawn for these seats, in this order, and every row of `acolytes` must
                  # be the same length -- a four-long row on a two-player board would put a third
                  # player's acolytes on the board.
                  seats: tuple[str, ...] | None = None,
                  uid: str = "dg") -> str:
    """The grid as one self-contained <svg>, sized by its viewBox and nothing else.

    No width or height attributes: the slot decides how big it is, exactly as the circular wheel
    did.

    The ground is one flat `<rect id="{uid}-ground">`, a placeholder for the real sheet. Swapping it
    for an `<image>` that carries its own border is a one-element change and nothing else in here
    depends on it.

    `margin` re-lays the nine as an even 3x3 (see `place`); pass None to draw them exactly where
    they were traced. Where a tile's artwork exists it is clipped into that shape and dimmed, and
    hovering lifts it. Where it does not, the shape keeps its flat region-map colour, so a
    half-finished set renders as a grid with holes rather than failing. Pass `tiles_dir=None` for
    the bare shapes.
    """
    meta = meta or load()
    box = meta["box"]
    # Two versions of the same nine, both through laid_shapes so the offsets tool cannot disagree
    # with the board about where a tile starts. The tiles get the saved offsets; the acolyte rows
    # are built from the unoffset shapes and never move, which is the whole point of the offsets.
    frozen = laid_shapes(meta, margin, offsets=False)
    laid = laid_shapes(meta, margin, offsets=offsets)
    cells = list(cells or DEFAULT_CELLS)
    if sorted(cells) != list(range(9)):
        raise ValueError(
            "cells must place each of the nine duties in its own square: got %r. A duty missing "
            "or doubled would draw a board that quietly means something else." % (cells,))
    # shapes[duty] is the outline of the square that duty was dealt
    shapes = [laid[c] for c in cells]
    seats = tuple(seats) if seats else SEAT_ORDER
    unknown = [s for s in seats if s not in SEAT_SWATCH]
    if unknown:
        raise ValueError(
            "no colour on record for seat(s) %s; the four this board knows are %s."
            % (", ".join(map(repr, unknown)), ", ".join(SEAT_ORDER)))
    if len(set(seats)) != len(seats):
        raise ValueError("a seat is listed twice in %r, so two columns of counts are the same "
                         "player" % (list(seats),))
    if not 1 <= len(seats) <= len(SEAT_ORDER):
        raise ValueError("%d seats; this board draws between 1 and %d"
                         % (len(seats), len(SEAT_ORDER)))
    live = None if active is None else eligible_tiles(acolytes, active, seats)
    tiles = find_tiles(tiles_dir, version) if tiles_dir else {}
    art = {i: embed(p, px) for i, p in tiles.items()}
    joins = joins_for(version)
    # The palette is carried as two feColorMatrix filters per tile rather than as recoloured
    # pixels, so the art is embedded once and switching is free. The reference tile is what the
    # others are matched TO, so it is never matched itself.
    mats: dict[int, dict[str, str]] = {}
    if palettes and tiles and PALETTE_REF in tiles:
        from PIL import Image

        def shrink(path):
            im = Image.open(path).convert("RGB")
            k = px / max(im.size)
            return im.resize((round(im.width * k), round(im.height * k)),
                             Image.LANCZOS) if k < 1 else im

        ref = palette_stats(shrink(tiles[PALETTE_REF]))
        for i, path in tiles.items():
            if i == PALETTE_REF:
                continue
            im = shrink(path)
            mats[i] = {m: palette_matrix(im, ref, m) for m in palettes}

    # The marking rides along whenever eligibility is known, and is inert until a page sets
    # `data-mark-effect` here and `data-mark` on a tile. `--dg-msw` is the board's own edge weight,
    # so every marking rule scales from the line it is laid over rather than from a number of its
    # own.
    marking = live is not None
    root_style = ((' style="%s;--dg-msw:%.2f"' % (mark_vars(uid), box * EDGE_STROKE))
                  if marking else "")
    out = [f'<svg class="{klass}" viewBox="0 0 {box} {box}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" '
           f'data-palette="{palette or "none"}"{root_style} '
           f'aria-label="Duty wheel, nine tiles">'
           f'<style>{HOVER_CSS}{PALETTE_CSS}{MARK_CSS if marking else ""}</style><defs>'
           + (mark_defs(uid) if marking else "")
           + pop_defs(uid, pop_set),
           f'<filter id="{uid}-dim" color-interpolation-filters="sRGB">{DIM}</filter>'
           f'<filter id="{uid}-lit" color-interpolation-filters="sRGB">{LIT}</filter>']
    for i, d in enumerate(shapes):
        # every tile gets a clip, art or not: the hit areas are clipped by it too, so hovering
        # the ground beside a tile must not light the tile
        out.append(f'<clipPath id="{uid}-c{i}"><path d="{d}"/></clipPath>')
        for mode, values in mats.get(i, {}).items():
            out.append(f'<filter id="{uid}-pal-{mode}-{i}" color-interpolation-filters="sRGB">'
                       f'<feColorMatrix type="matrix" values="{values}"/></filter>')
        if i in art and i in TWO_ACTION:
            x0, y0, x1, y1 = bbox(d)
            j = joins.get(i, 0.5)
            # A soft band rather than a hard edge: the two scenes were merged across a band of
            # picture, so a lit half that stops on a straight line cuts across the drawing.
            out.append(
                f'<linearGradient id="{uid}-gr{i}" x1="{x0}" x2="{x1}" '
                f'gradientUnits="userSpaceOnUse">'
                f'<stop offset="{max(0.0, j - 0.09):.3f}" stop-color="#000"/>'
                f'<stop offset="{min(1.0, j + 0.09):.3f}" stop-color="#fff"/></linearGradient>'
                f'<mask id="{uid}-mR{i}" maskUnits="userSpaceOnUse" x="{x0}" y="{y0}" '
                f'width="{x1 - x0}" height="{y1 - y0}">'
                f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
                f'fill="url(#{uid}-gr{i})"/></mask>'
                f'<mask id="{uid}-mL{i}" maskUnits="userSpaceOnUse" x="{x0}" y="{y0}" '
                f'width="{x1 - x0}" height="{y1 - y0}">'
                f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="#fff"/>'
                f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
                f'fill="url(#{uid}-gr{i})" style="mix-blend-mode:difference"/></mask>')
    out.append("</defs>")
    # The ground. `None` draws none, and the slot's own background shows through the channels --
    # which is how a picture gets behind the tiles without this file knowing about it. A colour
    # still draws the one element an <image> would replace.
    if background is not None:
        out.append(f'<rect id="{uid}-ground" width="{box}" height="{box}" fill="{background}"/>')

    for i, d in enumerate(shapes):
        label = (labels[i] if labels and i < len(labels) else "")
        named = ' data-duty-name="%s"' % label if label else ""
        able = live is None or i in live
        # Machine-readable and invisible: whatever ends up handling the click needs to know, and
        # so does anything reading this board back. Absent entirely when no seat is active, so a
        # board with no turn in progress makes no claim either way.
        mark = "" if live is None else ' data-eligible="%d"' % (1 if able else 0)
        out.append(f'<g data-duty-tile="{i}"{named}{mark} class="dgt">')
        if i in art:
            x0, y0, x1, y1 = bbox(d)
            img = (f'<image href="{art[i]}" x="{x0}" y="{y0}" width="{x1 - x0}" '
                   f'height="{y1 - y0}" preserveAspectRatio="xMidYMid slice"/>')
            for mode in mats.get(i, {}):
                img = (f'<g class="dg-pal dg-pal-{mode}" '
                       f'style="--dg-pal:url(#{uid}-pal-{mode}-{i})">{img}</g>')
            out.append(f'<g clip-path="url(#{uid}-c{i})">')
            if i == CITY:                   # the city is the one tile that is never dimmed
                out.append(img)
            else:
                out.append(f'<g filter="url(#{uid}-dim)">{img}</g>')
                for side in (("L", "R") if i in TWO_ACTION else ("F",)):
                    m = f' mask="url(#{uid}-m{side}{i})"' if side != "F" else ""
                    out.append(f'<g class="dg-lit dg-lit-{side}"{m}>'
                               f'<g filter="url(#{uid}-lit)">{img}</g></g>')
            out.append("</g>")
        else:
            out.append(f'<path d="{d}" fill="{TILE_FILLS[i % len(TILE_FILLS)]}"/>')
        out.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-opacity="0.85" '
                   f'stroke-width="{box * EDGE_STROKE:.2f}" stroke-linejoin="round" '
                   f'class="dg-edge"/>')
        # After the edge so it lies over it, before the hit areas so it never intercepts a pointer.
        if marking:
            out.append(mark_paths(d))
        # The hit areas, last so they sit on top, clipped so only the tile itself responds.
        #
        # EMITTED ON EVERY TILE, including the ones the active seat cannot use. These carry more
        # than the click: the game view binds its duty description panel to `.dg-hit`, keyed by
        # the tile's name and which half, so removing them from closed tiles took away the text
        # that says what the duty DOES.
        #
        # This file did remove them, briefly, on the argument that a control which responds but
        # cannot be used is a lie. That conflated two different things. Responding to a pointer is
        # not inviting a click -- nothing here sets a pointer cursor, and the gold edge is the
        # only thing on the board that says "this is yours to take". Reading what a duty does is
        # not acting on it, and a player deciding where to put acolytes needs to read the ones
        # they cannot reach this turn most of all.
        #
        # So the hit area stays and the REVEALS are gated instead: see HOVER_CSS, where every rule
        # that lights something requires `:not([data-eligible="0"])`. Suppression is written into
        # the positive rule rather than layered over it as an override, so there is no specificity
        # contest to lose later. `data-eligible` on the group is the contract for whatever comes
        # to handle clicks: it must refuse a "0".
        x0, y0, x1, y1 = bbox(d)
        out.append(f'<g clip-path="url(#{uid}-c{i})">')
        if i in art and i in TWO_ACTION:
            xm = x0 + (x1 - x0) * joins.get(i, 0.5)
            out.append(f'<rect class="dg-hit dg-hit-l" x="{x0}" y="{y0}" '
                       f'width="{xm - x0}" height="{y1 - y0}"/>'
                       f'<rect class="dg-hit dg-hit-r" x="{xm}" y="{y0}" '
                       f'width="{x1 - xm}" height="{y1 - y0}"/>')
        else:
            out.append(f'<rect class="dg-hit dg-hit-f" x="{x0}" y="{y0}" '
                       f'width="{x1 - x0}" height="{y1 - y0}"/>')
        out.append("</g></g>")
    if acolytes:
        # AFTER every tile group and outside all of them. That is what freezes the rows against
        # the tiles: nothing a tile's own transform or offset does can reach these.
        got = acolytes if isinstance(acolytes, dict) else dict(enumerate(acolytes))
        # pointer-events="none" is load-bearing. The row is drawn after the tiles, so it is on top
        # of their hit areas and overlaps each tile's bottom 60%: without this a pointer on an
        # acolyte hits the figure instead of the tile and the hover simply does not fire. It would
        # not have shown up in a count of working hover targets either -- the hit rects' CENTRES
        # sit above the figures, so testing the centres passes while the bottom quarter is dead.
        out.append('<g class="dg-acolytes" aria-hidden="true" pointer-events="none">')
        for i, counts in sorted(got.items()):
            if not (0 <= int(i) < 9) or counts is None:
                continue
            if len(counts) != len(seats):
                raise ValueError(
                    "acolytes[%r] has %d counts; there are %d seats in this game (%s). A row "
                    "of the wrong length draws one seat's acolytes under another seat's figure."
                    % (i, len(counts), len(seats), ", ".join(seats)))
            # TWO INDEX SPACES, and they are not the same one.
            #
            # `counts` is keyed by DUTY -- the caller is saying "this many acolytes on Taxation".
            # `frozen` is keyed by SQUARE, because it is the grid's nine positions. The square a
            # duty has been dealt to is `cells[duty]`, so that is the shape its row belongs under.
            #
            # This read `frozen[int(i)]`, which is only right while cells is the identity. Pass a
            # real arrangement and every count was drawn under the square that shares its NUMBER
            # rather than under its own tile -- the Taxation bug again, by a different route, and
            # silent in exactly the same way. It was dormant because the default arrangement is
            # the identity and nothing yet passes a shuffled one outside the guards.
            out.append(acolyte_row(frozen[cells[int(i)]], counts, seats,
                                   pop_set=pop_set, uid=uid))
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="write an html preview here")
    ap.add_argument("--margin", type=float, default=MARGIN,
                    help="ground left outside the grid, in viewBox units (default %(default)s); "
                         "the nine keep their traced sizes, so this sets the channels between them")
    ap.add_argument("--background", default=(BACKGROUND or "none"),
                    help="flat ground colour, or 'none' to draw no ground and let whatever the "
                         "wheel sits on show through the channels (default %(default)s)")
    ap.add_argument("--palette", choices=("none", "chroma", "full"),
                    default=(PALETTE or "none"),
                    help="match every tile's colour to the city (default %(default)s)")
    z = ap.parse_args()
    svg = duty_grid_svg(margin=z.margin,
                        background=(None if z.background == "none" else z.background),
                        palette=(None if z.palette == "none" else z.palette))
    meta = load()
    laid = place(meta["shapes"], meta["box"], z.margin)
    gaps = []
    for r in range(3):
        b = [bbox(laid[3 * r + c]) for c in range(3)]
        gaps += [b[1][0] - b[0][2], b[2][0] - b[1][2]]
    print(f"{len(svg) / 1024:.1f} KB of SVG, {len(meta['shapes'])} tiles, "
          f"margin {z.margin:g}, gaps {min(gaps):.1f}-{max(gaps):.1f} units")
    if z.out:
        sized = svg.replace("<svg", '<svg width="100%"', 1)
        pathlib.Path(z.out).write_text(
            "<body style='margin:0;background:#2b2419'>"
            "<div style='width:800px'>" + sized + "</div></body>", encoding="utf-8")
        print("wrote", z.out)
