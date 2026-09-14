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

The *shapes* are geometry, but the pictures inside them are not, and those are embedded: the
version B tiles from `assets-gothic/duty-tiles/`, downscaled to the size the component is actually
drawn at. A tile with no artwork yet keeps its flat region-map colour, so a half-finished set
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

HERE = pathlib.Path(__file__).resolve().parent
SHAPES = HERE.parent / "assets-gothic" / "metadata" / "duty_grid_shapes.json"
TILES = HERE.parent / "assets-gothic" / "duty-tiles"
# The field this component is built to sit on and deliberately does not paint. BACKGROUND is None
# so the ground shows through the channels between the nine tiles, and the path lives here rather
# than in either caller because BOTH need it: the board that lays the wheel on it, and the picker,
# whose whole claim is to show what the board will show and which drew its own parchment instead.
GROUND = HERE.parent / "assets-gothic" / "ui" / "ground.webp"


def ground_uri() -> str:
    """The ground as a data: URI, or a transparent pixel if it is not in this checkout.

    Embedded rather than linked: every page that uses it is written to ui/generated/ and then
    opened from wherever it lands, so a relative src would work in exactly one of those cases and
    silently show nothing in the rest. Absent, the caller falls back to its own flat colour and
    the board is plainer rather than broken.
    """
    import base64
    if not GROUND.is_file():
        print("no %s -- falling back to flat colour. Run "
              "`python3 ui/render/gen_ground.py` to make it." % GROUND.name)
        return "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=="
    return "data:image/webp;base64," + base64.b64encode(GROUND.read_bytes()).decode("ascii")

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
# The ARROWS do not depend on this. They describe which squares are adjacent, which is a property
# of the grid and does not shuffle.
DEFAULT_CELLS = [0, 1, 2, 3, 4, 5, 6, 7, 8]
# Which tiles carry two actions, and so have a join and two hover halves. Three duty tiles have
# a single action (Allocation, Build Roads, Taxation) and the city has none; measuring a join on
# those finds the strongest edge in a picture that has no join, which is noise.
TWO_ACTION = {1: ("Devotion", "Silversmith"), 2: ("Building", "Road"),
              5: ("Ordain", "Mission"), 6: ("Wheat", "Stone"), 8: ("Alms", "Donate")}
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
HOVER_CSS = ('.dgt .dg-lit{opacity:0}'
             '.dg-hit{fill:transparent}'
             '.dgt:has(.dg-hit-f:hover) .dg-lit-F{opacity:1}'
             '.dgt:has(.dg-hit-l:hover) .dg-lit-L{opacity:1}'
             '.dgt:has(.dg-hit-r:hover) .dg-lit-R{opacity:1}'
             '.dgt:has(.dg-hit:hover) .dg-edge{stroke:#d8b23a;stroke-opacity:1}')
# Where a two-action tile's scenes meet, as a fraction of its width. Measured: every source pair
# splits at 0.4993-0.5035 and every merge keeps it, so this is 0.5 and joins.json records why.
# Read rather than assumed, so a tile that ever genuinely differs is one file away.
# Switching palette is a class change, not a re-render: each tile carries a palette wrapper for
# every mode and CSS decides which one is live. `filter:none` as a CSS property beats the SVG
# `filter` presentation attribute, which is what lets "none" turn them all off.
PALETTE_CSS = ('.dg-pal{filter:none}'
               'svg[data-palette="chroma"] .dg-pal-chroma{filter:var(--dg-pal)}'
               'svg[data-palette="full"] .dg-pal-full{filter:var(--dg-pal)}')
JOINS = TILES / "joins.json"


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
#   margin 14                 channels 30/49          <- here
#   margin  8                 channels 36/54
#
# Below about 10 the outer tiles start crowding whatever sits next to the wheel on the board.
MARGIN = 14.0


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



# ---------------------------------------------------------------------------------------------
# Arrows
#
# Two movements, both of them read off `configs/board.json` rather than written down again:
#
#   the ring    The Merchant rides the eight duty tiles clockwise, one step per round end, and
#               never enters the City. Its route is north -> north_east -> east -> south_east ->
#               south -> south_west -> west -> north_west -> north.
#   the City    Not symmetric. The City feeds OUT to north and south, and takes IN from east and
#               west -- four edges, not eight.
#
# On a 3x3 that ring is exactly eight horizontal and vertical steps, which is why these are all
# straight: the old wheel needed curved ring arrows because it was a circle, and this is not.
#
# NOTE these are a property of the GRID, not of which duty sits where. The walk top-left ->
# top-centre -> top-right -> ... is the same whatever art is in the cells, so these arrows stay
# correct even while DUTY_NAMES disagrees with the board graph (it currently does -- see the
# duty-wheel README). Fixing that moves the artwork, not these.
RING = [(0, 1), (1, 2), (2, 5), (5, 8), (8, 7), (7, 6), (6, 3), (3, 0)]
CITY_ROUTES = [(4, 1), (4, 7), (5, 4), (3, 4)]
# One length and one width for all twelve. The head is anchored at the tile it points AT rather
# than centred in the channel, so no arrow crosses into the next duty and the length can still be
# uniform -- centring cannot do both. Measured from the channel centre, the nearest destination
# edge is 13.5 units away and the furthest 42.0, so a centred arrow short enough to clear every
# destination would be 27 units long and its tail would reach under the source tile on none of
# the twelve. Anchored at the head, 90 clears the widest source gap (75.5) with margin.
ARROW_LEN = 90.0
ARROW_W = 23.0             # what the City arrows were; the ring's was heavier and read as a bar
# The gap you actually SEE between the arrow head and the tile it points at. Stated as the gap
# rather than as an inset because both shapes are stroked and the strokes sit centred on their
# paths: the arrow's reaches ARROW_W*0.22/2 beyond its tip, the tile outline's reaches
# box*0.0035/2 beyond its edge. An inset of 2.0 therefore left the two inked edges overlapping by
# 2.3 units -- no gap at all -- which is what `_inset` now corrects for.
ARROW_GAP = 5.0
ARROW_STROKE = 0.14        # outline weight, as a fraction of the arrow's width
# The arrows are filled, not just outlined, so that the half of an arrow lying over dense
# engraving still reads as one shape. That fill USED to be `BACKGROUND`, which was fine only
# while the ground was a flat colour: a ground of None (the page shows through) or an <image>
# leaves nothing for an arrow to be filled WITH, and an arrow cannot be filled with a picture.
# So it is its own colour, and it is parchment because that is what the arrows are made of --
# not because that is what is behind them.
ARROW_FILL = "#e7bd83"


def _channel(a: str, b: str) -> tuple[float, float, float]:
    """Where an arrow between two cells sits, and which way it points."""
    ax0, ay0, ax1, ay1 = bbox(a)
    bx0, by0, bx1, by1 = bbox(b)
    if abs((ax0 + ax1) - (bx0 + bx1)) > abs((ay0 + ay1) - (by0 + by1)):
        x = (ax1 + bx0) / 2 if ax1 < bx0 else (bx1 + ax0) / 2
        return x, (max(ay0, by0) + min(ay1, by1)) / 2, (0 if ax1 < bx0 else 180)
    y = (ay1 + by0) / 2 if ay1 < by0 else (by1 + ay0) / 2
    return (max(ax0, bx0) + min(ax1, bx1)) / 2, y, (90 if ay1 < by0 else 270)


def _ray_hit(shape: str, x: float, y: float, ang: float, limit: float = 300.0) -> float:
    """Distance from (x, y) along `ang` to the first crossing of this outline.

    The outlines are polylines of 140 points, so this is an exact segment intersection rather
    than a rasterised probe -- no PIL, and it stays right if the shapes are ever resampled.
    """
    import math
    dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    n = [float(v) for v in shape.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    pts = [(n[i], n[i + 1]) for i in range(0, len(n), 2)]
    best = limit
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        t = ((x1 - x) * ey - (y1 - y) * ex) / den          # along the ray
        u = ((x1 - x) * dy - (y1 - y) * dx) / den          # along the segment
        if 0 <= t < best and 0.0 <= u <= 1.0:
            best = t
    return best



def arrow(length: float, w: float, stroke: str, fill: str) -> str:
    """A flat-tailed arrow, outlined in the same ink as the tile edges.

    Outline AND fill, not outline alone: over cross-hatching a hollow arrow lets the engraving
    through its middle and the shape dissolves. The stroke is a smaller fraction of the width
    than it was when these were small, or at this size it reads as a black bar.
    """
    return (f'<path d="M{-length / 2:.1f} {-w * .3:.1f} L{length / 2 - w * .8:.1f} {-w * .3:.1f} '
            f'L{length / 2 - w * .8:.1f} {-w * .85:.1f} L{length / 2:.1f} 0 '
            f'L{length / 2 - w * .8:.1f} {w * .85:.1f} L{length / 2 - w * .8:.1f} {w * .3:.1f} '
            f'L{-length / 2:.1f} {w * .3:.1f} Z" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{w * ARROW_STROKE:.2f}" stroke-linejoin="round"/>')


def _inset(w: float, box: float) -> float:
    """How far back the arrow's PATH must stop for ARROW_GAP of clear ground to show."""
    return ARROW_GAP + (w * ARROW_STROKE) / 2 + (box * 0.0035) / 2


def arrows_svg(shapes: list[str], length: float = ARROW_LEN, w: float = ARROW_W,
               fill: str = ARROW_FILL, box: float = 1000, uid: str = "dg") -> str:
    """Both routes, one size, each rising out from under the tile it leaves.

    The whole arrow is drawn above the tiles and then masked by the SOURCE tile's outline, so the
    tail is hidden exactly where that tile covers it. Its head is placed at the DESTINATION tile's
    outline, so it stops there instead of crossing into the next duty.

    Every arrow is therefore the same length and the same width, while the length you can SEE is
    set by the torn edges -- short where a tile bulges into the channel, long where it falls away.

    `pointer-events:none` so they never steal a hover from the tile beneath.
    """
    defs, body = [], []
    for n, (a, b) in enumerate(RING + CITY_ROUTES):
        x, y, ang = _channel(shapes[a], shapes[b])
        reach = _ray_hit(shapes[b], x, y, ang) - _inset(w, box)   # to the destination outline
        defs.append(f'<mask id="{uid}-am{n}" maskUnits="userSpaceOnUse" x="0" y="0" '
                    f'width="{box}" height="{box}">'
                    f'<rect width="{box}" height="{box}" fill="#fff"/>'
                    f'<path d="{shapes[a]}" fill="#000"/></mask>')
        # the mask goes on an OUTER group with no transform of its own. A transform on the same
        # element establishes the user space the mask is then resolved in, so putting both here
        # would measure the tile outline in the arrow's rotated frame and mask the wrong region.
        body.append(f'<g mask="url(#{uid}-am{n})">'
                    f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang})">'
                    f'<g transform="translate({reach - length / 2:.1f} 0)">'
                    f'{arrow(length, w, INK, fill)}</g></g></g>')
    return ('<defs>' + "".join(defs) + '</defs>'
            '<g class="dg-arrows" pointer-events="none">' + "".join(body) + '</g>')


def duty_grid_svg(meta: dict | None = None, klass: str = "wheel",
                  labels: list[str] | None = None, tiles_dir: pathlib.Path | None = TILES,
                  version: str = VERSION, px: int = 448,
                  margin: float | None = MARGIN, background: str = BACKGROUND,
                  palette: str | None = PALETTE,
                  palettes: tuple[str, ...] = ("chroma", "full"),
                  arrows: bool = True,
                  cells: list[int] | None = None,
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
    laid = meta["shapes"] if margin is None else place(meta["shapes"], box, margin)
    cells = list(cells or DEFAULT_CELLS)
    if sorted(cells) != list(range(9)):
        raise ValueError(
            "cells must place each of the nine duties in its own square: got %r. A duty missing "
            "or doubled would draw a board that quietly means something else." % (cells,))
    # shapes[duty] is the outline of the square that duty was dealt
    shapes = [laid[c] for c in cells]
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

    out = [f'<svg class="{klass}" viewBox="0 0 {box} {box}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" '
           f'data-palette="{palette or "none"}" '
           f'aria-label="Duty wheel, nine tiles">'
           f'<style>{HOVER_CSS}{PALETTE_CSS}</style><defs>'
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
        out.append(f'<g data-duty-tile="{i}"{named} class="dgt">')
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
                   f'stroke-width="{box * 0.0035:.2f}" stroke-linejoin="round" class="dg-edge"/>')
        # The hit areas, last so they sit on top, and clipped so only the tile itself responds.
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
    if arrows:
        # `laid`, not `shapes`: the arrows are between SQUARES, and shapes has been
        # reindexed by duty. Passing the reindexed list makes them follow the shuffle.
        out.append(arrows_svg(laid, box=box, uid=uid))
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
