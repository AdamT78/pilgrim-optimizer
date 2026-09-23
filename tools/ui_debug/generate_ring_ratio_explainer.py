#!/usr/bin/env python3
"""Draw what the ring ratio is, for docs/architecture/ring-ratio.md.

WHY THIS IS A GENERATOR AND NOT A COMMITTED PICTURE. The ratio is a property of the plates
on file: the target and tolerance in generate_asset_check.py are read off them, so both move
when the set does. A picture with the old numbers painted on would go stale silently, which
is the failure this whole folder exists to prevent. This reads the constants and the art at
run time, so redrawing it is how you find out it changed.

THE FOURTH PANEL IS THE ONE THAT EARNS ITS PLACE. It used to draw a bounding box round an
ellipse and divide its sides, which is how the ring was measured until 2026-09-23 -- and that
method is biased, by more than the tolerance a plate is held to. A picture teaching it would
be teaching the bug. It now shows the bias instead: one ring, measured both ways, with the
numbers computed at draw time rather than written in.

THE RING IN THE BOTTOM-LEFT PANEL IS DRAWN HERE, not generated. The real ringed candidates live
in a download folder and are not in the repository, and committing a two-megabyte input just
to illustrate a diagram is the wrong trade. So the ring is drawn around the committed plate
at THAT PLATE'S OWN MEASURED ANGLE, which makes the panel reproducible from the repo alone --
and the panel says so rather than implying a generated ring. The evidence that a real ring
agrees with a real tile is a measurement, and it belongs in the prose: on the plate filed on
2026-09-23 the generated ring read 31.5 and the tile inside it 31.6.

EVERYTHING IS DRAWN AT 4x AND DOWNSCALED. ImageDraw has no antialiasing at all, and a
stepped diagram handed to someone who is already struggling with the idea adds a defect to
the thing they are trying to understand.

    python3 tools/ui_debug/generate_ring_ratio_explainer.py
"""
from __future__ import annotations

import importlib.util
import math
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "docs" / "architecture" / "ring-ratio.png"

S = 4
BG, INK, DIM = (26, 22, 16), (222, 212, 186), (125, 115, 98)
GREEN, GOLD, RED = (90, 215, 145), (226, 184, 96), (233, 110, 110)
FONTS = ("/usr/share/fonts/truetype/crosextra/Carlito-%s.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf",
         "/System/Library/Fonts/Supplemental/Arial%s.ttf")


def _checker():
    spec = importlib.util.spec_from_file_location(
        "generate_asset_check", HERE / "generate_asset_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_asset_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def font(px, bold=False):
    for pat in FONTS:
        for suffix in ((("-Bold", "-Bold", " Bold") if bold else ("-Regular", "", ""))):
            try:
                return ImageFont.truetype(pat % suffix, px * S)
            except OSError:
                continue
    return ImageFont.load_default()


def txt(d, xy, s, px=13, col=INK, bold=False, anchor="la"):
    d.text((xy[0] * S, xy[1] * S), s, font=font(px, bold), fill=col, anchor=anchor)


def _canvas(w, h):
    im = Image.new("RGB", (w * S, h * S), BG)
    return im, ImageDraw.Draw(im)


def panel_side(deg, w=400, h=250):
    """A circle on the ground and an eye above it, seen from the side."""
    im, d = _canvas(w, h)
    cx, cy, R = 200, 165, 110
    d.line([(cx - R - 30) * S, cy * S, (cx + R + 34) * S, cy * S], fill=DIM, width=1 * S)
    d.line([(cx - R) * S, cy * S, (cx + R) * S, cy * S], fill=GREEN, width=4 * S)
    txt(d, (cx, cy + 12), "the circle, seen edge-on", 12, GREEN, anchor="ma")
    ex = cx + 120 * math.cos(math.radians(180 - deg))
    ey = cy - 120 * math.sin(math.radians(deg))
    d.line([ex * S, ey * S, cx * S, cy * S], fill=GOLD, width=2 * S)
    d.ellipse([(ex - 7) * S, (ey - 7) * S, (ex + 7) * S, (ey + 7) * S], fill=GOLD)
    txt(d, (ex, ey - 22), "camera", 12, GOLD, anchor="ma")
    rr = 46
    d.arc([(cx - rr) * S, (cy - rr) * S, (cx + rr) * S, (cy + rr) * S],
          180, 180 + deg, fill=GOLD, width=2 * S)
    a = math.radians(180 - deg / 2.0)
    txt(d, (cx + rr * 1.42 * math.cos(a), cy + rr * 1.42 * math.sin(a) - 8),
        "%.1f°" % deg, 14, GOLD, bold=True, anchor="mm")
    txt(d, (w / 2, 14), "1. the camera sits %.1f° above the horizon" % deg,
        14, INK, bold=True, anchor="ma")
    txt(d, (w / 2, h - 30), "a flat circle on the ground", 12, DIM, anchor="ma")
    txt(d, (w / 2, h - 16), "and an eye looking down at it", 12, DIM, anchor="ma")
    return im.resize((w, h), Image.LANCZOS)


def panel_seen(deg, w=400, h=250):
    """What that camera sees: the circle squashed into an ellipse."""
    im, d = _canvas(w, h)
    s = math.sin(math.radians(deg))
    cx, cy, R = 175, 104, 98
    hh = R * s
    d.ellipse([(cx - R) * S, (cy - hh) * S, (cx + R) * S, (cy + hh) * S],
              outline=GREEN, width=4 * S)
    y = cy + hh + 18
    d.line([(cx - R) * S, y * S, (cx + R) * S, y * S], fill=INK, width=2 * S)
    for x in (cx - R, cx + R):
        d.line([x * S, (y - 6) * S, x * S, (y + 6) * S], fill=INK, width=2 * S)
    txt(d, (cx, y + 8), "width", 12, INK, anchor="ma")
    x = cx + R + 22
    d.line([x * S, (cy - hh) * S, x * S, (cy + hh) * S], fill=RED, width=2 * S)
    for yy in (cy - hh, cy + hh):
        d.line([(x - 6) * S, yy * S, (x + 6) * S, yy * S], fill=RED, width=2 * S)
    txt(d, (x + 8, cy), "height", 12, RED, anchor="lm")
    txt(d, (w / 2, 14), "2. so the camera sees an ellipse", 14, INK, bold=True, anchor="ma")
    txt(d, (w / 2, h - 42), "height ÷ width = %.3f" % s, 16, GREEN, bold=True, anchor="ma")
    txt(d, (w / 2, h - 17), "↑ THIS is the ring ratio", 12, DIM, anchor="ma")
    return im.resize((w, h), Image.LANCZOS)


def panel_range(target, tol, w=1400, h=340):
    """The same circle from every camera height, with the board's window marked."""
    im, d = _canvas(w, h)
    txt(d, (26, 16), "The same circle, from every camera height", 16, INK, bold=True)
    txt(d, (26, 38), "Flatter camera → shorter ellipse → smaller ratio. The ratio IS "
                     "sin(angle); nothing else about the picture changes.", 12, DIM)
    steps = [(90.0, "straight down"), (50.0, ""), (40.0, ""),
             (target, "the board"), (30.0, "sin = 0.500"), (20.0, ""), (10.0, "almost eye level")]
    x0, R, base = 96, 74, 168
    gap = (w - 2 * x0) / (len(steps) - 1)
    for i, (deg, note) in enumerate(steps):
        cx = x0 + i * gap
        s = math.sin(math.radians(deg))
        hot = abs(deg - target) < 1e-6 or abs(deg - 30.0) < 1e-6
        col = GOLD if abs(deg - target) < 1e-6 else (RED if abs(deg - 30.0) < 1e-6 else GREEN)
        d.ellipse([(cx - R) * S, (base - R * s) * S, (cx + R) * S, (base + R * s) * S],
                  outline=col, width=(4 if hot else 3) * S)
        txt(d, (cx, base + R + 16), "%.2f°" % deg if hot else "%.0f°" % deg,
            14, col, bold=hot, anchor="ma")
        txt(d, (cx, base + R + 36), "%.3f" % s, 15, col, bold=hot, anchor="ma")
        if note:
            txt(d, (cx, base + R + 56), note, 11, col if hot else DIM, anchor="ma")
    txt(d, (w - 26, 16), "window %.2f to %.2f°" % (target - tol, target + tol),
        13, GOLD, bold=True, anchor="ra")
    txt(d, (w - 26, 36), "ratios %.4f to %.4f"
        % (math.sin(math.radians(target - tol)), math.sin(math.radians(target + tol))),
        12, DIM, anchor="ra")
    return im.resize((w, h), Image.LANCZOS)


def _ringed(plate, deg, radius=1.18, stroke=0.018, key=(0, 255, 128)):
    """A ring drawn HERE around a committed plate, at that plate's own measured angle.

    DRAWN AS A BAND, not as PIL's ellipse outline. PIL strokes INWARD from the bounding box,
    so an outline drawn to a box at angle t has a CENTRELINE flatter than t -- and since
    ring_ellipse now fits the centreline, the illustration disagreed with its own caption by
    half a degree. The band between (a-t, b-t) and (a+t, b+t) has its centreline at exactly
    the angle asked for, which is what the caption claims.
    """
    import numpy as np
    s = math.sin(math.radians(deg))
    w, h = plate.width, plate.height
    a = w * radius / 2.0
    b = a * s
    t = max(3.0, w * stroke / 2.0)
    W, H = int(2 * (a + t) + 80), int(max(2 * (b + t), h) * 1.12 + 80)
    cx, cy = W / 2.0, H / 2.0
    yy, xx = np.mgrid[0:H, 0:W]
    inner = ((xx - cx) / (a - t)) ** 2 + ((yy - cy) / (b - t)) ** 2
    outer = ((xx - cx) / (a + t)) ** 2 + ((yy - cy) / (b + t)) ** 2
    px = np.zeros((H, W, 4), np.uint8)
    px[(outer <= 1.0) & (inner >= 1.0)] = key + (255,)
    out = Image.fromarray(px, "RGBA")
    out.alpha_composite(plate, (int(cx - w / 2), int(cy - h * 0.5)))
    return out


def panel_real(mod, w=1400, h=372):
    """The same arithmetic on the committed plate."""
    sm = mod.sm
    path = mod.GROUNDS / "cobbles_oval.png"
    if not path.is_file():
        path = sorted(mod.GROUNDS.glob("*.png"))[0]
    plate = Image.open(path).convert("RGBA")
    g = sm.ground_ellipse(plate, base_band=False)
    deg = g["degrees"]
    ringed = _ringed(plate, deg)
    r = sm.ring_ellipse(ringed)

    im, d = _canvas(w, h)
    txt(d, (26, 16), "The same thing on a plate that is actually on file", 16, INK, bold=True)
    txt(d, (26, 38), "%s, measured at %.2f°. The ring here is DRAWN at that same angle "
                     "rather than generated — see the module docstring." % (path.name, deg),
        12, DIM)

    CW = 430

    def place(img, x, label, sub, col):
        a = img.convert("RGBA")
        bb = a.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        a = a.crop(bb)
        hh = round(a.height * CW / a.width)
        cell = Image.new("RGB", (CW * S, hh * S), BG)
        big = a.resize((CW * S, hh * S), Image.LANCZOS)
        cell.paste(big, (0, 0), big)
        im.paste(cell, (x * S, 80 * S))
        txt(d, (x, 80 + hh + 10), label, 13, col, bold=True)
        txt(d, (x, 80 + hh + 28), sub, 12, DIM)

    place(ringed, 30, "ring and all",
          "ring measures %.3f  →  %.2f°" % (r["sin_theta"], r["degrees"]), GREEN)
    place(sm.without_ring(ringed), 500, "ring keyed out — this is the art",
          "tile itself measures %.3f  →  %.2f°" % (g["sin_theta"], deg), GOLD)

    return im.resize((w, h), Image.LANCZOS)


def _band(deg, a, t, W, H, key=(0, 255, 128)):
    """A ring whose CENTRELINE is known exactly: the band between (a-t,b-t) and (a+t,b+t)."""
    import numpy as np
    s = math.sin(math.radians(deg))
    b = a * s
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W / 2.0, H / 2.0
    inner = ((xx - cx) / (a - t)) ** 2 + ((yy - cy) / (b - t)) ** 2
    outer = ((xx - cx) / (a + t)) ** 2 + ((yy - cy) / (b + t)) ** 2
    px = np.zeros((H, W, 4), np.uint8)
    px[(outer <= 1.0) & (inner >= 1.0)] = key + (255,)
    return Image.fromarray(px, "RGBA"), (a, b, t)


def panel_bias(mod, w=1400, h=506, drawn=32.0):
    """Why the ring is FITTED and not bounded, with both numbers measured at draw time.

    Filling a ring recovers its OUTER edge, and an outer edge is a fatter ellipse than the
    centreline it was drawn around: adding half-stroke t to both semi-axes gives (b+t)/(a+t),
    which exceeds b/a whenever b < a. The old method therefore reported a steeper camera than
    the ring was drawn at. Nothing here is painted on -- the ring is built at a known angle and
    both readings are taken from it, so if the fit ever regresses this picture says so.
    """
    import numpy as np
    from scipy import ndimage
    sm = mod.sm
    A, T_, WW, HH = 690, 18, 1600, 900
    ring, (a, b, t) = _band(drawn, A, T_, WW, HH, key=sm.RING_KEY)

    fitted = sm.ring_ellipse(ring)
    m, _ = sm._ring_mask(ring)
    filled = ndimage.binary_fill_holes(m)
    px = np.zeros(filled.shape + (4,), np.uint8)
    px[filled] = [255, 255, 255, 255]
    bounded = sm.ground_ellipse(Image.fromarray(px, "RGBA"), base_band=False)

    im, d = _canvas(w, h)
    txt(d, (26, 16), "Why the ring is fitted, not bounded", 16, INK, bold=True)
    txt(d, (26, 38), "A ring is a stroke with thickness. Bound it and you measure its OUTER "
                     "edge, which is a fatter ellipse than the centreline it was drawn "
                     "around \u2014 so the camera comes back too steep.", 12, DIM)

    # the ring itself, to scale, with the two readings drawn over it
    cx, cy, k = 400, 240, 0.40
    aa, bb, tt = a * k, b * k, max(3.0, t * k)
    for r in (1.0,):
        d.ellipse([(cx - aa - tt) * S, (cy - bb - tt) * S, (cx + aa + tt) * S,
                   (cy + bb + tt) * S], outline=GREEN, width=2 * S)
        d.ellipse([(cx - aa + tt) * S, (cy - bb + tt) * S, (cx + aa - tt) * S,
                   (cy + bb - tt) * S], outline=GREEN, width=2 * S)
    d.ellipse([(cx - aa) * S, (cy - bb) * S, (cx + aa) * S, (cy + bb) * S],
              outline=GOLD, width=3 * S)
    d.rectangle([(cx - aa - tt) * S, (cy - bb - tt) * S, (cx + aa + tt) * S,
                 (cy + bb + tt) * S], outline=RED, width=2 * S)
    txt(d, (cx, cy + bb + tt + 16), "the stroke, and the box that bounds it",
        12, DIM, anchor="ma")

    # A MAGNIFIED INSET AT THE TOP EXTREME, because at true proportions the three curves sit
    # within a few pixels of each other and the panel would be asserting a difference it does
    # not show. The top is where the bias acts: the box touches the OUTER edge there, while
    # the angle is a property of the CENTRELINE, and the half-stroke between them is a far
    # larger fraction of the minor axis than of the major one. That asymmetry is the bug.
    zx, zy, zoom = 1080, 232, 4.0
    zw, zh = 470, 132
    d.rectangle([(zx - zw / 2) * S, (zy - zh / 2) * S, (zx + zw / 2) * S, (zy + zh / 2) * S],
                outline=DIM, width=1 * S)
    for off, col, lab in ((-tt, RED, "box, and the ring's outer edge"),
                          (0.0, GOLD, "the centreline \u2014 the actual angle"),
                          (tt, GREEN, "inner edge")):
        y = zy + off * zoom
        d.line([(zx - zw / 2 + 6) * S, y * S, (zx + 20) * S, y * S], fill=col, width=2 * S)
        txt(d, (zx + 28, y), lab, 11, col, anchor="lm")
    d.line([(zx - zw / 2 + 24) * S, (zy - tt * zoom) * S,
            (zx - zw / 2 + 24) * S, (zy + 0.0) * S], fill=INK, width=1 * S)
    txt(d, (zx - zw / 2 + 30, zy - tt * zoom / 2), "half-stroke", 10, INK, anchor="lm")
    txt(d, (zx, zy - zh / 2 - 14), "the top of the ring, magnified %.0fx" % zoom,
        11, DIM, anchor="ma")

    # the arithmetic, stated in full so neither number has to be taken on trust
    x = 860
    rows = [("drawn at", "%.2f\u00b0" % drawn, "ratio %.4f" % (b / a), INK),
            ("bounded (the old way)", "%.2f\u00b0" % bounded["degrees"],
             "%+.2f\u00b0" % (bounded["degrees"] - drawn), RED),
            ("fitted (now)", "%.2f\u00b0" % fitted["degrees"],
             "%+.2f\u00b0" % (fitted["degrees"] - drawn), GREEN)]
    for i, (lab, val, note, col) in enumerate(rows):
        y = 336 + i * 34
        txt(d, (x, y), lab, 13, DIM)
        txt(d, (x + 250, y - 4), val, 20, col, bold=True, anchor="ra")
        txt(d, (x + 268, y), note, 13, col)
    txt(d, (x, 336 + 3 * 34 + 10),
        "half-stroke %d px on a %d px semi-axis. A plate is held to \u00b1%.2f\u00b0,"
        % (t, a, mod.GROUND_TOLERANCE_DEGREES), 12, DIM)
    txt(d, (x, 336 + 3 * 34 + 28),
        "so the old method's error was larger than the thing it measured.", 12, DIM)
    return im.resize((w, h), Image.LANCZOS)


def build(out=OUT):
    mod = _checker()
    target = getattr(mod, "GROUND_TARGET_DEGREES", 32.0)
    tol = getattr(mod, "GROUND_TOLERANCE_DEGREES", 1.0)
    top = Image.new("RGB", (1400, 250), BG)
    top.paste(panel_side(target), (110, 0))
    top.paste(panel_seen(target), (545, 0))
    ImageDraw.Draw(top).line([(520, 60), (520, 200)], fill=DIM, width=1)
    page = Image.new("RGB", (1400, 250 + 340 + 372 + 506 + 40), BG)
    page.paste(top, (0, 0))
    page.paste(panel_range(target, tol), (0, 258))
    page.paste(panel_real(mod), (0, 608))
    page.paste(panel_bias(mod), (0, 992))
    out.parent.mkdir(parents=True, exist_ok=True)
    page.save(out, "PNG", optimize=True)
    return out, target, tol


if __name__ == "__main__":
    p, t, tl = build()
    print("wrote %s  (%.0f KB)" % (p, p.stat().st_size / 1024))
    print("  drawn against the plates on file: target %.2f deg, tolerance %.2f" % (t, tl))
