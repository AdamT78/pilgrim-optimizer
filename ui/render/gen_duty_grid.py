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
VERSION = "B"

# Flat fills, one per tile. These are a REGION MAP, not a palette: each becomes a hover mask when
# the art lands, and none of them survives into the finished wheel. Chosen to be easy to tell
# apart, not to look good together.
TILE_FILLS = ["#67694a", "#4a5d70", "#ab4c38", "#c68335", "#9d8869",
              "#815977", "#45596e", "#636c4a", "#8d5b33"]
# Ring order as DUTY_TEXT in gen_board.py lists it, city at centre. Not confirmed against
# tools/ui_debug/duty_wheel_layout.json, which is not in the checkout -- see the duty-wheel README.
DUTY_NAMES = ["Allocation", "Clerical", "Construct", "Build Roads", "The City",
              "Ordination", "Produce", "Taxation", "Give Alms"]
# Which tiles carry two actions, and so have a join and two hover halves. Three duty tiles have
# a single action (Allocation, Build Roads, Taxation) and the city has none; measuring a join on
# those finds the strongest edge in a picture that has no join, which is noise.
TWO_ACTION = {1: ("Devotion", "Silversmith"), 2: ("Building", "Road"),
              5: ("Ordain", "Mission"), 6: ("Wheat", "Stone"), 8: ("Alms", "Donate")}
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
    """
    if not root or not root.is_dir():
        return {}
    pat = re.compile(r"^(\d{2})_([a-z_]+)_([AB])\.(png|webp|jpg)$", re.I)
    found: dict[int, pathlib.Path] = {}
    for p in sorted(root.rglob("*")):
        m = pat.match(p.name)
        if m and m.group(3).upper() == version.upper():
            i = int(m.group(1)) - 1
            if 0 <= i < 9:
                found[i] = p
    return found


def embed(p: pathlib.Path, px: int = 448, quality: int = 82) -> str:
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
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=quality, method=6)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        mime = {"png": "image/png", "webp": "image/webp",
                "jpg": "image/jpeg"}[p.suffix.lstrip(".").lower()]
        return "data:%s;base64," % mime + base64.b64encode(p.read_bytes()).decode()


def bbox(path_d: str) -> tuple[float, float, float, float]:
    n = [float(v) for v in path_d.replace("M", " ").replace("Z", " ").replace("L", " ").split()]
    xs, ys = n[0::2], n[1::2]
    return min(xs), min(ys), max(xs), max(ys)


# Two feColorMatrix blocks and nothing else generate every state the wheel has. They are filters
# rather than extra artwork because a second diffusion pass is not deterministic: two merges of
# one pair differ by edge-difference 13.0, so a generated "lit" tile would redraw itself under
# the cursor. A filter leaves the drawing alone.
DIM = ('<feColorMatrix type="saturate" values="0.40"/><feComponentTransfer>'
       '<feFuncR type="linear" slope=".94" intercept=".005"/>'
       '<feFuncG type="linear" slope=".96" intercept=".010"/>'
       '<feFuncB type="linear" slope="1.02" intercept=".025"/></feComponentTransfer>')
LIT = ('<feColorMatrix type="saturate" values="1.20"/><feComponentTransfer>'
       '<feFuncR type="linear" slope="1.34" intercept=".10"/>'
       '<feFuncG type="linear" slope="1.14" intercept=".055"/>'
       '<feFuncB type="linear" slope=".78" intercept="0"/></feComponentTransfer>')
# Whole-tile hover, not the per-half split the real wheel needs. The halves are driven by a
# mousemove handler in gen_picker_grid.py, which is where hover is being judged; this file has to
# stay a self-contained <svg> that the layout tool can drop into a slot, so it does the part that
# is pure CSS and leaves the rest to the page that owns the interaction.
HOVER_CSS = ('.dgt .dg-lit{opacity:0}'
             '.dgt:hover .dg-lit{opacity:1}'
             '.dgt:hover .dg-edge{stroke:#d8b23a;stroke-opacity:1}')


def duty_grid_svg(meta: dict | None = None, klass: str = "wheel",
                  labels: list[str] | None = None, tiles_dir: pathlib.Path | None = TILES,
                  version: str = VERSION, px: int = 448) -> str:
    """The grid as one self-contained <svg>, sized by its viewBox and nothing else.

    No width or height attributes: the slot decides how big it is, exactly as the circular wheel
    did. The parchment grain is feTurbulence rather than an image.

    Where a tile's artwork exists it is clipped into that shape and dimmed, and hovering lifts it.
    Where it does not, the shape keeps its flat region-map colour, so a half-finished set renders
    as a grid with holes rather than failing. Pass `tiles_dir=None` for the bare shapes.
    """
    meta = meta or load()
    box = meta["box"]
    parch = meta.get("parchment")
    fill = ("#%02x%02x%02x" % tuple(parch)) if parch else PARCHMENT_FALLBACK
    tiles = find_tiles(tiles_dir, version) if tiles_dir else {}
    art = {i: embed(p, px) for i, p in tiles.items()}

    out = [f'<svg class="{klass}" viewBox="0 0 {box} {box}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="Duty wheel, nine tiles">'
           f'<style>{HOVER_CSS}</style><defs>'
           f'<filter id="dg-grain" x="0" y="0" width="100%" height="100%">'
           f'<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="7"/>'
           f'<feColorMatrix type="saturate" values="0"/>'
           f'<feComponentTransfer><feFuncA type="linear" slope="0.07"/></feComponentTransfer>'
           f'</filter>'
           f'<filter id="dg-dim" color-interpolation-filters="sRGB">{DIM}</filter>'
           f'<filter id="dg-lit" color-interpolation-filters="sRGB">{LIT}</filter>']
    for i, d in enumerate(meta["shapes"]):
        if i in art:
            out.append(f'<clipPath id="dg-c{i}"><path d="{d}"/></clipPath>')
    out.append("</defs>")
    out.append(f'<rect width="{box}" height="{box}" fill="{fill}"/>'
               f'<rect width="{box}" height="{box}" filter="url(#dg-grain)" opacity="0.55"/>')

    for i, d in enumerate(meta["shapes"]):
        label = (labels[i] if labels and i < len(labels) else "")
        named = ' data-duty-name="%s"' % label if label else ""
        out.append(f'<g data-duty-tile="{i}"{named} class="dgt">')
        if i in art:
            x0, y0, x1, y1 = bbox(d)
            img = (f'<image href="{art[i]}" x="{x0}" y="{y0}" width="{x1 - x0}" '
                   f'height="{y1 - y0}" preserveAspectRatio="xMidYMid slice"/>')
            out.append(f'<g clip-path="url(#dg-c{i})">')
            if i == 4:                      # the city is the one tile that is never dimmed
                out.append(img)
            else:
                out.append(f'<g filter="url(#dg-dim)">{img}</g>'
                           f'<g class="dg-lit"><g filter="url(#dg-lit)">{img}</g></g>')
            out.append("</g>")
        else:
            out.append(f'<path d="{d}" fill="{TILE_FILLS[i % len(TILE_FILLS)]}"/>')
        out.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-opacity="0.85" '
                   f'stroke-width="{box * 0.0035:.2f}" stroke-linejoin="round" class="dg-edge"/>'
                   f'</g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="write an html preview here")
    z = ap.parse_args()
    svg = duty_grid_svg()
    print(f"{len(svg) / 1024:.1f} KB of SVG, {len(load()['shapes'])} tiles")
    if z.out:
        sized = svg.replace("<svg", '<svg width="100%"', 1)
        pathlib.Path(z.out).write_text(
            "<body style='margin:0;background:#2b2419'>"
            "<div style='width:800px'>" + sized + "</div></body>", encoding="utf-8")
        print("wrote", z.out)
