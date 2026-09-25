"""Judge a freshly generated sculpt or ground plate before it is filed.

    python3 tools/ui_debug/generate_asset_check.py --serve

WHAT THIS IS FOR

Art arrives from an image model in batches and most of it is nearly right. The expensive part is
not generating another one, it is knowing which of the eight you just made is the one to keep --
and "looks about right" is not a judgement you can repeat tomorrow. Drop a PNG on this page and
it measures the things the board actually depends on and says which of them are inside tolerance.

WHY IT MEASURES ON THE SERVER

The measuring lives in `sculpt_metrics.py`, which `make_tray_figures.py` and `check_sculpt.py`
already share. A copy of it in JavaScript would agree on the day it was written and drift the
first time a threshold moved, and both halves would look correct alone. So the page is a front
end: it posts the file, the server measures with the same code that builds the pieces, and the
page draws what came back. Opened from disk with no server there is nothing to measure with, and
the page says so rather than guessing.

WHAT IT WILL AND WILL NOT GIVE A VERDICT ON

A sculpt's plinth is a turned disc, so its bottom outline IS an ellipse and the camera angle off
it is exact. The nine figures on record span 31.1 to 33.5 degrees, all inside a 2.5 tolerance.

A GROUND PLATE IS HARDER, and the fix is the measuring ring rather than an eye. A plate's edge
is ragged cobble, stepped stone or plank ends; the outline is not an ellipse, and fitting one to
it is a best guess that visibly misses -- on planks_rough the fit reads 30.66 where the ring
reads 31.14. So the briefs ask the generator to draw a green ring around the tile, a known
circle on the same ground, and sculpt_metrics measures that and then strips it. Plates now get a
verdict like sculpts do, against a window locked at 31.545 +/- 0.48.

This paragraph said something else until 2026-09-23 -- that a plate could not be judged, that
two plates read 25 and 17.8 degrees by outline against 38.5 by bounding box, and that plates
with circular outlines would fix it. All of that is superseded: the ring made ragged plates
measurable without changing the art, and the bounding-box figure was itself the bug, since
bounding a ring measures its outer edge and over-reads by up to 0.7 degrees.

EVERY NUMBER COMES WITH THE PICTURE THAT SHOWS WHERE IT LANDED

The overlay is not decoration. A measurement of a picture is worth exactly as much as your
ability to see what it found, and the one bug this tool has already caught in its own measuring
-- the widest row landing on player_4's robe rather than its plinth, reporting a 90 degree camera
-- was invisible in the number and obvious in the drawing.
"""

import argparse
import base64
import importlib.util
import io
import json
import math
import os
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "asset_check.html"


def href(path, rel_to=None):
    """Where the PAGE should point at a committed file, as a path and not as ten megabytes.

    THE SAME STRING HAS TO WORK IN BOTH MODES, which is the only reason this is a function.
    Opened from disk the page sits in tools/ui_debug/generated/, so a file three levels up is
    ../../../ui/... ; served, the page is handed out at that same path under a document root of
    the repository, so the identical relative href resolves to the identical file. Serving the
    page at "/" would have broken every one of these.

    Embedding was the alternative and it was measured: the originals and the attachments came to
    15.3 MB of base64 against 0.3 MB of the drawn previews that actually appear on screen -- 98%
    of the page was link targets nobody looks at. What embedding buys is a one-click download
    from a file:// page, because Chromium ignores the `download` attribute on a file:// link and
    navigates to the image instead. That is the whole trade, and --serve wins it back.
    """
    rel = os.path.relpath(str(path), str((rel_to or OUT.parent)))
    return rel.replace(os.sep, "/")

sys.path.insert(0, str(HERE))
import numpy as np                                                      # noqa: E402
import sculpt_metrics as sm                                             # noqa: E402

try:
    from PIL import Image, ImageDraw
except ModuleNotFoundError:                                             # pragma: no cover
    Image = ImageDraw = None

CONCEPT = ROOT / "ui" / "concept"
SCULPTS = ROOT / "ui" / "assets-gothic" / "sculpts"
GROUNDS = ROOT / "ui" / "assets-gothic" / "grounds"
GROUND_PLAN = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_grounds.json"
PLAYERS = ("player_1", "player_2", "player_3", "player_4")

# THE ANGLE THE SET IS BEING REDRAWN TO. A constant rather than a file because exactly one thing
# reads it; the page lets you change it without editing this, and the moment a second tool needs
# it, it moves into ui/assets-gothic/metadata/ like every other rule that outlived one caller.
# 32 BECAUSE THAT IS WHERE THIS GENERATOR LANDS, on both halves of the board, and because the
# ask stopped steering it. Two batches of ten, asks three degrees apart and reference cards to
# match: 32.1 then 31.9. Three degrees of instruction moved the result by two tenths. The ground
# plates converge on the same place unprompted -- nine style-varied plates averaged 32.6 -- so
# sculpts and grounds already agree with each other at 32, and an earlier 29 (itself chosen by
# looking at a composite, after 30 and 40 were picked from numbers and did not survive a picture)
# would have to be fought for on both sides to buy a difference of three degrees.
TARGET_DEGREES = 32.0
TOLERANCE_DEGREES = 2.5
# THERE IS NO HEIGHT TOLERANCE, AND THAT IS THE DECISION, not an omission.
#
# Height was judged against the median of whatever was on file. Two things were wrong with that.
# The median moves as the set fills, so the same sculpt passes or fails depending on what was
# filed before it -- a verdict that is a fact about the folder rather than about the figure. And
# the two sets on file disagree by 26% in proportion even after the camera is divided out (the
# concept art at 2.18, the sculpts drawn at the board's camera at 2.75), so the check fired on
# every new sculpt: arithmetically right, practically useless. Which proportion is wanted is a
# decision about how the game looks, and no median can make it.
#
# Height is still measured, still reported and still drawn on the figure picture. It is judged by
# looking at the candidates that got past the camera and the base.
#
# How far a plinth may be chunkier or thinner than the set's, measured as its own side wall over
# its own width. A separate question from the camera: a thin base and a chunky one photograph at
# the same angle and carry the same figure. Wide because it is a small measurement on a short
# edge, and so noisy. This one survives because the two sets AGREE on it -- concept 0.132-0.146,
# the new sculpts 0.126-0.141 -- so the median is not hostage to which art is on file.
#
# THE TWO SIDES ARE NOT THE SAME FAILURE, which is why there are two numbers rather than one.
#
# A single symmetric 12% was fitted before any monk existed, on a sample of a nun and three
# pilgrims, and the first monks broke it: they came back at 0.159-0.171 against a median of
# 0.141 -- outside the band, and, levelled onto a common plinth width the way
# make_tray_figures.py levels them, indistinguishable from the set. The band was measuring the
# sample it was fitted to.
#
# What the failures actually look like, across four batches of five:
#
#     in the set, levelled and judged by eye   0.136 - 0.171
#     the model ignoring the card entirely     0.217 - 0.279
#
# Nothing has ever landed between those. So the chunky side is set to admit the first population
# whole and still reject the second by a wide margin, and the thin side is left where it was,
# because the thin failure is real and separate: an undimensioned card produced bases near 0.08,
# which is 43% under and nowhere near this limit. A base below the set reads as a sliver and
# takes the camera down with it -- the anti-correlation between base thickness and camera height
# runs at r = +0.92 -- so there is no case for loosening that side to match this one.
# A GROUND PLATE IS HELD TIGHTER THAN A SCULPT, and it is a different number rather than the
# same one because the two are not the same measurement.
#
# A sculpt's camera is read off a plinth perhaps 150 px wide inside a figure the generator drew
# freehand, and five near-identical renders of one monk scatter by about 0.6 degrees -- so 2.5
# is a tolerance sized to the noise in the instrument. A plate is a single flat ellipse 1500 px
# across with nothing standing on it: the reading is far steadier, and what it has to agree with
# is the whole set of figures at once.
#
# THE PLATE WINDOW IS LOCKED. These two numbers are constants, not a formula over the
# folder, and a plate that falls outside them fails rather than widening them.
#
# They were DERIVED ONCE, on 2026-09-23, from the six plates then on file -- every one of
# which had been looked at under figures and kept, so the set was the best description of
# what "right" meant:
#
#     slate_irregular       31.07   -0.475
#     planks_rough          31.14   -0.405     (from its ring; its outline reads 30.66)
#     flagstones_grey       31.52   -0.025
#     cobbles_oval          31.63   +0.085
#     limestone_irregular   31.89   +0.345
#     flagstones_slab       32.02   +0.475
#
#     mean 31.545, largest deviation 0.475  ->  window 31.065 to 32.025
#
# THE TARGET IS THE UNROUNDED MEAN AND THE TOLERANCE IS THE DEVIATION ROUNDED UP, and both
# halves of that matter. Corrected 2026-09-24, from a target of 31.55 and this same table
# quoting -0.47 for slate and +0.48 for slab -- which had the two transposed. The six plates'
# mean is 31.545 exactly, and slate and slab sit 0.475 either side of it, equidistant.
# Rounding the target to 31.55 moved it five thousandths toward slab, which put slate at
# exactly 0.48 out. With the tolerance also 0.48 that plate then sat precisely ON the
# boundary, where `abs(31.55 - 31.07) <= 0.48` is FALSE in binary floating point by four parts
# in 10^16 -- so slate_irregular, which carries the construct duty, was judged `check` by the
# page and failed test_a_plate_is_held_tighter_than_a_sculpt, for no reason that exists in the
# art. The tolerance is NOT set to the exact largest deviation for the same reason: at 0.475
# both extreme plates would sit on the boundary instead of one. Rounding the tolerance up is
# what buys them any margin, and it is now five thousandths of a degree rather than zero.
#
# That replaced a target of 32.0 with a tolerance of 1.0, which were both picked rather than
# measured, and which the set never centred on: five of its six sat below 32.
#
# WHY THE RULE THAT PRODUCED THEM IS NOT THE RULE THAT KEEPS THEM. A window defined as the
# accepted set's mean and largest deviation is defined by the thing it judges, so every plate
# accepted rewrites the bar judging the next, and nothing anchors it. Simulated: filing eight
# plates each landing exactly on the current ceiling -- all legitimate, all green -- moves the
# target +0.54 and the ceiling +1.09 degrees.
#
# The realistic path is worse because it is invisible. Filing the BEST of each batch rather
# than an edge case, over twelve plates, the target slides DOWN from 31.55 to 31.43 while the
# ceiling stays pinned at 32.02, because the highest plate on file anchors the top and
# everything new lands below the mean. The set drifts away from the sculpts one plate at a
# time, and every individual step looks like tightening the standard.
#
# The tolerance was also decided by exactly ONE plate, whichever sat furthest out -- slab
# today, slate before the plank correction. Add a plate 0.48 past the ceiling and that
# statistic jumps 72% where two standard deviations would move 31%.
#
# So the numbers stay where the measurement put them. Changing them is now a deliberate edit
# to two literals that shows up in review, rather than a side effect of filing art.
GROUND_TARGET_DEGREES = 31.545      # LOCKED 2026-09-23, corrected 2026-09-24; see above


def _trim(x):
    """A number at three decimals with trailing zeros removed: 31.545, 0.48, 32.025.

    Two decimals is not enough for these -- it turns the target back into the 31.55 it was moved
    off -- and a fixed three turns a tolerance of 0.48 into "0.480", which reads as a precision
    that was not measured. So: three, then stripped.
    """
    return ("%.3f" % x).rstrip("0").rstrip(".")
GROUND_TOLERANCE_DEGREES = 0.48     # LOCKED 2026-09-23; window 31.065 to 32.025
BASE_TOLERANCE_PCT = 24.0        # chunkier than the set's median
BASE_THIN_PCT = 12.0             # thinner than it


def _board():
    spec = importlib.util.spec_from_file_location(
        "generate_duty_board_check", HERE / "generate_duty_board_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "ui" / "render"))
    sys.modules["generate_duty_board_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def _upright(ratio, degrees):
    """Any VERTICAL measurement over the base's width, with the camera divided out.

    Height over plinth width and wall over plinth width are both projected: raising the camera
    shortens the drawn height of anything standing up while leaving the base's width alone, so
    the same sculpt measures smaller the higher you look from. Both therefore need dividing by
    cos(theta) before one figure can be compared with another shot from elsewhere.
    """
    if ratio is None or degrees is None:
        return None
    c = math.cos(math.radians(max(0.0, min(89.0, degrees))))
    return ratio / c if c > 1e-6 else None


def _proportion(h_plinth, degrees):
    """Height over plinth width with the camera divided out -- the figure's real proportion.

    h_plinth is a PROJECTED measurement: raising the camera shortens a figure's drawn height by
    cos(theta) while leaving its base width alone, so the same physical sculpt measures smaller
    the higher you look from. Comparing a 30 degree figure against a 9 degree set therefore
    conflates "stockier" with "photographed from higher up", which is the precise confusion this
    tool exists to prevent. Dividing by cos(theta) recovers the proportion the sculptor made.
    """
    if h_plinth is None or degrees is None:
        return None
    c = math.cos(math.radians(max(0.0, min(89.0, degrees))))
    return h_plinth / c if c > 1e-6 else None


def reference_band(kind="sculpt_plastic"):
    """What the set already agrees about, so a newcomer is judged against its siblings.

    Ratios rather than pixels: a figure generated larger or smaller compares directly.
    """
    rows = []
    for name in PLAYERS:
        path = CONCEPT / name / ("%s.png" % kind)
        if not path.is_file():
            continue
        im = Image.open(path).convert("RGBA")
        m = sm.measure(im)
        g = sm.ground_ellipse(im)
        rows.append({"h_plinth": m["h_plinth"], "wall_ratio": m["wall_ratio"],
                     "degrees": g["degrees"] if g else None,
                     "proportion": _proportion(m["h_plinth"], g["degrees"] if g else None),
                     "base_ratio": _upright(m["wall_ratio"], g["degrees"] if g else None)})
    if not rows:
        return None
    out = {}
    for key in ("h_plinth", "wall_ratio", "degrees", "proportion", "base_ratio"):
        vals = [r[key] for r in rows if r[key] is not None]
        if vals:
            out[key] = {"lo": min(vals), "hi": max(vals),
                        "mid": statistics.median(vals), "n": len(vals)}
    return out


def overlay(im, g, kind):
    """The art with the measurement drawn on it, as a data URI."""
    art = sm.crop_to_art(im)
    scale = min(1.0, 520 / max(art.width, art.height))
    big = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))),
                     Image.LANCZOS).convert("RGBA")
    back = Image.new("RGBA", big.size, (23, 19, 13, 255))
    back.alpha_composite(big)
    d = ImageDraw.Draw(back, "RGBA")
    if g:
        f = lambda v: v * scale                                          # noqa: E731
        d.line([(0, f(g["widest_row"])), (back.width, f(g["widest_row"]))],
               fill=(255, 96, 96, 210), width=2)
        d.line([(0, f(g["bottom_edge"])), (back.width, f(g["bottom_edge"]))],
               fill=(120, 200, 255, 210), width=2)
        d.line([(0, f(g["bottom_centre"])), (back.width, f(g["bottom_centre"]))],
               fill=(120, 255, 150, 210), width=2)
        half = abs(g["minor"]) / 2.0
        top, bottom = f(g["bottom_edge"] - half), f(g["bottom_edge"] + half)
        if bottom > top:                      # a drawing helper is no place to raise
            d.ellipse([f(g["left"]), top, f(g["right"]), bottom],
                      outline=(255, 212, 126, 255), width=3)
    buf = io.BytesIO()
    back.convert("RGB").save(buf, "WEBP", quality=88, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def plinth_picture(im, width=340, degrees=None):
    """The base on its own, magnified, with the two numbers check (b) compares drawn on it.

    The band is printed as figures everywhere else, and a figure is a poor way to hold a shape in
    your head while looking at a new sculpt. The width is measured across the widest row of the
    base; the wall is the lit rim down to the bottom of the art, which is what `measure` finds by
    looking for the brightest row. Drawing both on the actual pixels they were taken from is the
    only way to see that they were taken from the right place.

    THE CAMERA IS STATED ON THE PICTURE because the wall is meaningless without it. A wall is a
    vertical edge, so it is drawn shorter the higher the camera sits: 67 px at 32 degrees is a
    different plinth from 67 px at 9. Two of these pictures side by side, each captioned with its
    own width and wall and nothing else, would invite exactly the comparison the whole tool
    exists to stop anyone making.
    """
    art = sm.crop_to_art(im)
    y, w, lo, hi = sm._base_row(art)
    wall = sm.measure(art)["wall"]
    H = art.height
    pad = max(18, int(wall * 0.9))
    box = (max(0, lo - pad), max(0, H - 1 - int(wall * 2.6) - pad),
           min(art.width, hi + pad), H)
    crop = art.crop(box)
    if crop.width < 4 or crop.height < 4:
        return None
    k = width / crop.width
    big = crop.resize((width, max(1, round(crop.height * k))), Image.LANCZOS).convert("RGBA")
    back = Image.new("RGBA", (big.width, big.height + 34), (23, 19, 13, 255))
    back.alpha_composite(big)
    d = ImageDraw.Draw(back, "RGBA")

    gold, ink = (255, 212, 126, 255), (150, 142, 124, 255)
    xl, xr = (lo - box[0]) * k, (hi - box[0]) * k
    yb = (H - 1 - box[1]) * k
    ytop = (H - 1 - wall - box[1]) * k

    d.line([(xl, yb + 12), (xr, yb + 12)], fill=gold, width=2)          # width, across the base
    for x in (xl, xr):
        d.line([(x, yb + 6), (x, yb + 18)], fill=gold, width=2)
    d.text((max(2, (xl + xr) / 2 - 34), yb + 18), "width %d" % w, fill=gold)

    xw = min(back.width - 3, xr + 10)                                   # wall, down the near side
    d.line([(xw, ytop), (xw, yb)], fill=gold, width=2)
    for yy in (ytop, yb):
        d.line([(xw - 6, yy), (xw + 6, yy)], fill=gold, width=2)
    d.line([(xl, ytop), (xr, ytop)], fill=ink, width=1)
    # above the bracket rather than beside it: beside it, the label sat on its own tick marks
    d.text((max(2, min(back.width - 56, xw - 26)), max(0, ytop - 15)), "wall %d" % wall,
           fill=gold)

    if degrees is not None:
        cap = "camera %.1f deg" % degrees
        up = _upright(wall / float(w), degrees) if w else None
        if up is not None:
            # ASCII only: the default bitmap font has no em dash and draws a missing-glyph box
            cap += "   wall/width %.3f, %.3f upright" % (wall / float(w), up)
        d.rectangle([0, 0, back.width, 17], fill=(23, 19, 13, 215))
        d.text((4, 3), cap, fill=(201, 178, 122, 255))

    buf = io.BytesIO()
    back.convert("RGB").save(buf, "WEBP", quality=90, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def figure_picture(im, height=250, degrees=None):
    """The whole sculpt with check (c) drawn on it: how tall it stands over its own base.

    Height alone is not a number anyone can use -- a figure generated larger or smaller is not a
    different sculpt -- so what is drawn is the span and what is reported is the span over the
    base's own width. And that ratio is projected like everything else standing up, so the camera
    is stated beside it and divided out, exactly as on the plinth below.
    """
    art = sm.crop_to_art(im)
    k = height / art.height
    fw = max(1, round(art.width * k))
    big = art.resize((fw, height), Image.LANCZOS).convert("RGBA")
    gutter = 112
    back = Image.new("RGBA", (fw + gutter, height + 18), (23, 19, 13, 255))
    back.alpha_composite(big, (0, 18))
    d = ImageDraw.Draw(back, "RGBA")
    gold = (255, 212, 126, 255)

    top, bot = 18, 18 + height - 1
    x = fw + 14
    d.line([(x, top), (x, bot)], fill=gold, width=2)
    for y in (top, bot):
        d.line([(x - 6, y), (x + 6, y)], fill=gold, width=2)

    m = sm.measure(art)
    plinth = m["plinth"] or 1
    d.text((x + 11, top + 4), "height", fill=gold)
    d.text((x + 11, top + 16), "%d" % art.height, fill=gold)
    d.text((x + 11, (top + bot) / 2 - 18), "over", fill=(150, 142, 124, 255))
    d.text((x + 11, (top + bot) / 2 - 6), "base", fill=(150, 142, 124, 255))
    d.text((x + 11, (top + bot) / 2 + 6), "%d" % plinth, fill=(150, 142, 124, 255))
    d.text((x + 11, bot - 26), "= %.2f" % m["h_plinth"], fill=gold)
    if degrees is not None:
        up = _proportion(m["h_plinth"], degrees)
        if up is not None:
            d.text((x + 11, bot - 14), "%.2f upright" % up, fill=gold)
    cap = "camera %.1f deg" % degrees if degrees is not None else "camera not measured"
    d.text((4, 3), cap, fill=(201, 178, 122, 255))

    buf = io.BytesIO()
    back.convert("RGB").save(buf, "WEBP", quality=88, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def seat_tint(im, hexv):
    """One monochrome sculpt in one seat's colour, as a duotone over its own luminance.

    THE GAME DOES NOT DO THIS, and that is worth knowing before trusting the picture. The four
    coloured sculpts in ui/concept/ arrived coloured from the generator; nothing in the pipeline
    recolours a grey one. So this is a PREVIEW of how the seats would read, built from the game's
    own SEAT_SWATCH so the hues are right, using the same dark-to-light luminance ramp that
    gen_duty_grid.acolyte_tints() uses for the acolyte icon.

    It is not shared with that function because that one is about a specific committed asset and
    wraps its result in a silhouette halo. If a recolour step ever becomes part of how sculpts are
    made, the ramp belongs in one place and this is the second caller that would move.
    """
    import colorsys
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, sat, v = colorsys.rgb_to_hsv(r, g, b)
    dark = colorsys.hsv_to_rgb(h, min(1, sat * 1.3), v * 0.30)
    light = colorsys.hsv_to_rgb(h, min(1, sat * 0.95), min(1, v * 1.10))
    a = np.asarray(im.convert("RGBA")).astype(float)
    lum = (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]) / 255.0
    lum = np.clip((lum - 0.06) / 0.84, 0, 1) ** 0.80
    out = np.zeros_like(a)
    for c in range(3):
        out[..., c] = (dark[c] + (light[c] - dark[c]) * lum) * 255
    out[..., 3] = a[..., 3]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def seat_swatch():
    """The seat colours the game actually uses, read rather than copied."""
    try:
        return dict(_board().dg.SEAT_SWATCH)
    except Exception:                                                   # noqa: BLE001
        return {}


def arrangement_picture(folder=SCULPTS, place=None, colour=False, plain=False):
    """A full tile: five sculpts on a plate, in the formation the placement file describes.

    The two checks above judge a figure ALONE. A set can pass both and still not work on a tile,
    because what collides there is the plinths, and a plinth's ellipse is as deep as its width
    times sin(camera). Raising the camera from 9 to 32 degrees made the base three times deeper
    without moving a single number in duty_placement.json, and the rank gap those numbers were
    tuned against stopped being enough.

    So this draws the file's own formation and then RASTERISES every plinth and intersects each
    pair, rather than inviting anyone to judge overlap by eye. Red means a clash. The picture
    follows the file: change `back` or `rank` there and this follows, which is the point -- it is
    a check, not a screenshot of one good arrangement.
    """
    grounds = ROOT / "ui" / "assets-gothic" / "grounds"
    place = place or ROOT / "ui" / "assets-gothic" / "metadata" / "duty_placement.json"
    if not folder.is_dir() or not place.is_file():
        return None
    P = json.loads(place.read_text(encoding="utf-8"))
    frame, spread = P["frame"], P["spread"]
    # `tuned_at` names a SET (`210_plastic`) and what this drawing wants is the pixel height
    # behind it. The two were the same value until two different sets were both 210 tall.
    back, rank, size = P["back"], P["rank"], _board().set_px(P["tuned_at"])
    # NAMED, not sorted()[0] -- which picked cobbles_oval, the one plate on file still at the
    # old 39.8 degree camera, and put the new sculpts on a ground drawn from somewhere else.
    plate_path = grounds / "flagstones_grey.png"
    if not plate_path.is_file():
        rest = sorted(grounds.glob("*.png"))
        plate_path = rest[0] if rest else None
    files = sorted(folder.glob("*.png"))
    if plate_path is None or not files:
        return None

    def trim(im):
        bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        return im.crop(bb) if bb else im

    raw = [trim(Image.open(f).convert("RGBA")) for f in files]
    pw = [sm.plinth_width(f) for f in raw]
    narrow = min(pw)
    tall = max(f.height * (narrow / w) for f, w in zip(raw, pw, strict=True))
    built = []
    for f, w in zip(raw, pw, strict=True):
        k = (narrow / w) * size / tall
        g = sm.ground_ellipse(f)
        built.append({"im": f.resize((max(1, round(f.width*k)), max(1, round(f.height*k))),
                                     Image.LANCZOS),
                      "pw": w * k, "minor": (g["width"] * g["sin_theta"] * k) if g else 0.0})

    W, H, drop = frame["w"], frame["h"], frame["drop"]
    pad, top = 22, 16
    # 62 rather than 48: a fourth caption line, the live width limit, sits at H + 45.
    card = Image.new("RGBA", (W + 2*pad, H + pad + top + 62), (23, 19, 13, 255))
    floor = H - drop

    plate = trim(Image.open(plate_path).convert("RGBA"))
    # the standing line is a property of the picture, so it is measured rather than assumed: the
    # widest row of the plate's own ink is where a figure's feet belong
    prows = (np.asarray(plate)[..., 3] > sm.ALPHA).sum(1)
    anchor = float(prows.argmax()) / max(1, len(prows))
    ph = max(1, round(plate.height * W / plate.width))
    pl = np.asarray(plate.resize((W, ph), Image.LANCZOS)).astype(float)
    rgb, al = pl[..., :3], pl[..., 3:]
    grey = (0.2126*rgb[..., 0] + 0.7152*rgb[..., 1] + 0.0722*rgb[..., 2])[..., None]
    pl = Image.fromarray(np.concatenate(
        [np.clip((grey + (rgb-grey)*0.65)*0.55, 0, 255), al], 2).astype(np.uint8))
    card.alpha_composite(pl, (pad, int(top + floor - anchor*ph)))

    pick = [i % len(built) for i in (0, 2, 1, 0, 2)]
    # THE MIDDLE STEPS FORWARD, far enough that the top of its plinth lands on the floor line the
    # outer two stand on -- minus half its own plinth depth, since y is height above the floor.
    # The file still says a set-BACK of `back`, and at 21 the middle plinth overlaps both of the
    # back rank's: a plinth is as deep as it is wide times sin(camera), so raising the camera
    # from 9 to 32 degrees made every base three times deeper without moving a number in that
    # file. Stepping forward clears it without growing `field`, which a larger rank gap would.
    forward = built[pick[3]]["minor"] / 2.0
    slots = [(-spread/2, rank), (spread/2, rank), (-spread, 0), (0, -forward), (spread, 0)]
    del back
    ells = [(W/2 + dx, floor - dy, built[i]["pw"]/2.0, built[i]["minor"]/2.0)
            for (dx, dy), i in zip(slots, pick, strict=True)]

    masks = []
    for cx, cy, a, b in ells:
        m = Image.new("L", card.size, 0)
        ImageDraw.Draw(m).ellipse([pad+cx-a, top+cy-b, pad+cx+a, top+cy+b], fill=255)
        masks.append(np.asarray(m) > 0)
    clash = [(i, j) for i in range(len(masks)) for j in range(i+1, len(masks))
             if (masks[i] & masks[j]).any()]

    # WHICH SEAT STANDS WHERE, for the coloured preview only. An illustrative deal rather than
    # a rule: two sage, one pewter, one plum, one bone, so every seat colour appears and one
    # repeats, which is what a real tile mostly looks like.
    swatch = seat_swatch() if colour else {}
    order = ["sage", "pewter", "plum", "bone", "sage"]

    for i in sorted(range(len(slots)), key=lambda k: -slots[k][1]):
        dx, dy = slots[i]
        b = built[pick[i]]
        im = b["im"]
        if colour and swatch:
            im = seat_tint(im, swatch.get(order[i % len(order)], "#A8A296"))
        if dy:
            a = np.asarray(im).astype(float)
            a[..., :3] *= 0.80
            im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        card.alpha_composite(im, (int(pad + W/2 + dx - im.width/2),
                                  int(top + floor - dy + b["minor"]/2 - im.height)))

    d = ImageDraw.Draw(card, "RGBA")
    hot = {i for pair in clash for i in pair}
    if not plain:
        for i, (cx, cy, a, b) in enumerate(ells):
            d.ellipse([pad+cx-a, top+cy-b, pad+cx+a, top+cy+b],
                      outline=(255, 96, 96, 235) if i in hot else (120, 220, 150, 200), width=2)
        d.rectangle([pad, top, pad+W, top+H], outline=(255, 212, 126, 200), width=2)
    xs = [W/2 + dx + s*built[i]["im"].width/2
          for (dx, _), i in zip(slots, pick, strict=True) for s in (-1, 1)]
    span = round(max(xs) - min(xs))
    low = round(max(cy + b for _, cy, _, b in ells) - floor)
    # THE WIDTH LIMIT IS A FUNCTION, NOT A CONSTANT, and quoting it from memory is how it went
    # wrong: `2 * spread + widest <= frame.w` leaves the widest figure frame.w - 2*spread px, so
    # the limit on a figure's width IN UNITS OF ITS OWN BASE is that over the levelled plinth --
    # and the plinth moves whenever the art does, because the set is levelled on the narrowest
    # base and then scaled until the tallest reaches the nominal size. A flat 1.136 was carried
    # around for a day; it was derived against an 88 px plinth this folder no longer produces.
    # Computed from the figures just drawn, so it cannot drift from them.
    plinth = built[0]["pw"] if built else 0.0
    limit = (W - 2*spread) / plinth if plinth else 0.0
    broad = max(b["im"].width / plinth for b in built) if plinth else 0.0
    # THREE SHORT LINES, not one long one: the card is only W + 2*pad wide and a single line ran
    # off its right edge, which the page happily rendered with the verdict missing.
    ok = (120, 220, 150, 255)
    if plain:
        # THE SAME CARD SIZE, caption area simply left empty. Cropping the strip off made this
        # image shorter than its neighbour, and the page sizes tile pictures by HEIGHT -- so the
        # shorter one was scaled wider than the cell and lost a figure off each edge. Two pictures
        # meant to be compared have to share a shape.
        buf = io.BytesIO()
        card.convert("RGB").save(buf, "WEBP", quality=86, method=6)
        return {"uri": "data:image/webp;base64,"
                       + base64.b64encode(buf.getvalue()).decode("ascii"),
                "span": span, "frame": W, "clashes": len(clash), "low": low, "drop": drop,
                "plate": plate_path.stem, "anchor": round(anchor * 100),
                "limit": round(limit, 3), "widest": round(broad, 3),
                "plinth": round(plinth)}
    d.text((pad, top + H + 6),
           "five sculpts, spread %d, middle forward %d, rank %d"
           % (spread, round(forward), rank),
           fill=(201, 178, 122, 255))
    d.text((pad, top + H + 19),
           "%d of %d px across" % (span, W),
           fill=ok if span <= W else (255, 120, 120, 255))
    d.text((pad, top + H + 32),
           "lowest plinth %d below the floor, frame drop %d" % (low, drop),
           fill=ok if low <= drop else (255, 120, 120, 255))
    d.text((pad + 168, top + H + 19),
           "no plinths overlap" if not clash else "%d plinth clash(es)" % len(clash),
           fill=ok if not clash else (255, 120, 120, 255))
    # SHORT, and split across the line like the row above it, for the reason stated there: one
    # long line runs off the card's right edge and the page renders it with the verdict missing.
    d.text((pad, top + H + 32 + 13),
           "widest %.3f of its own base" % broad,
           fill=ok if broad <= limit else (255, 120, 120, 255))
    d.text((pad + 168, top + H + 32 + 13),
           "limit %.3f at plinth %d" % (limit, round(plinth)),
           fill=ok if broad <= limit else (255, 120, 120, 255))
    buf = io.BytesIO()
    card.convert("RGB").save(buf, "WEBP", quality=86, method=6)
    return {"uri": "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii"),
            "span": span, "frame": W, "clashes": len(clash), "low": low, "drop": drop,
            "plate": plate_path.stem, "anchor": round(anchor*100),
            "limit": round(limit, 3), "widest": round(broad, 3),
            "plinth": round(plinth)}


def on_record(folder=SCULPTS, rel_to=None):
    """The sculpts a newcomer is being judged against, drawn rather than summarised."""
    out = []
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.png")):
        try:
            im = Image.open(path).convert("RGBA")
            m = sm.measure(im)
            g = sm.ground_ellipse(im)
            out.append({"name": path.stem,
                        # THE ORIGINAL, not the drawn preview beside it. Same reason the
                        # reference card is offered whole: this file is what you attach to a
                        # v2 brief, and the previews above it are 520 px with measurements
                        # burnt in -- handing one of those over under the sculpt's name would
                        # be handing over a different instruction that looks identical.
                        "file": path.name,
                        "kb": round(path.stat().st_size / 1024),
                        "orig": href(path, rel_to),
                        "degrees": round(g["degrees"], 1) if g else None,
                        "base": round(_upright(m["wall_ratio"], g["degrees"]) or 0, 3) if g
                        else None,
                        "proportion": round(_proportion(m["h_plinth"], g["degrees"]) or 0, 2) if g
                        else None,
                        "figure": figure_picture(
                            im, degrees=g["degrees"] if g else None),
                        "plinth": plinth_picture(
                            im, degrees=g["degrees"] if g else None)})
        except Exception as exc:                                        # noqa: BLE001
            print("  could not draw %s: %s" % (path.name, exc))
    return out


def ground_record(folder=GROUNDS, rel_to=None):
    """The ground plates, judged on the ONE check they share with a sculpt.

    A plate has no plinth and no figure, so two of the three sculpt checks have nothing to
    measure. The camera does transfer, and it is the check that matters: a circle on the ground
    seen from theta above draws an ellipse of sin(theta) x its width, which is the same
    arithmetic whether the circle is a figurine's base or the ground the figurine stands on. If
    the plate and the figure disagree about where you are standing, the tile is wrong however
    good either one looks alone.

    `base_band=False` is not a detail. The band exists to scan the bottom strip of a sculpt,
    where a plinth lives; a plate IS the ellipse, and scanning its bottom strip reports about
    17 degrees for everything.

    ANCHOR IS REPORTED AGAINST THE FILE AND NOT RECONCILED WITH IT. The widest row of the art is
    where the standing line falls, and duty_grounds.json carries a hand-set value per plate. The
    two differ by a point or so, consistently in one direction, which reads as deliberate -- feet
    set a little forward of the widest row -- rather than as drift. Two numbers side by side let
    that stay a judgement; one number would quietly make it an error.
    """
    out = []
    if not folder.is_dir():
        return out
    plan = {}
    if GROUND_PLAN.is_file():
        try:
            plan = json.loads(GROUND_PLAN.read_text(encoding="utf-8"))
        except ValueError as exc:
            print("  could not read %s: %s" % (GROUND_PLAN.name, exc))
    settings = plan.get("grounds") or {}
    by_duty = plan.get("by_duty") or {}
    for path in sorted(folder.glob("*.png")):
        try:
            im = Image.open(path).convert("RGBA")
            # A PLATE WITH NO RING TAKES THE PATH IT ALWAYS TOOK. The ring is something a fresh
            # generation carries so its camera can be read off a clean ellipse instead of off
            # its own edge; nothing on file has one, and nothing on file is re-measured.
            ringed = sm.has_measuring_ring(im)
            ring = sm.ring_ellipse(im) if ringed else None
            if ringed:
                im = sm.without_ring(im)
            g = ring or sm.ground_ellipse(im, base_band=False)
            art = sm.crop_to_art(im)
            # A RECORDED CAMERA, for a plate whose own outline cannot be trusted to give one.
            # ground_ellipse fits an ellipse; on a round rimmed plate that is what it is
            # looking at, and the fit tracks the rim all the way round. On a ragged patch it
            # is a best fit to a shape that is not an ellipse, and it visibly misses -- on
            # planks_rough the fit bulges past the timber on one side and falls inside it on
            # the other. That plate's measuring ring, which IS a circle, fits at 31.14 where its
            # outline read 30.66.
            #
            # So duty_grounds.json may carry the camera for such a plate, and this reports it
            # as the plate's angle. THE MEASURED OUTLINE IS STILL REPORTED ALONGSIDE and never
            # replaced, because a recorded number is exactly the kind of thing that goes
            # quietly wrong, so three guards keep it honest. Two refuse a recorded camera
            # further than the ring/outline agreement bar from the plate's own outline, and one
            # that does not say where it came from. The third is newer: the ring-bearing
            # generation has to be ON FILE, named by the block's `ring_source`, and the ring has
            # to still re-derive the recorded angle. Until 2026-09-24 it could not be, because
            # the ring was discarded once the art was stripped -- planks_rough's original was
            # recovered from its generating session, and stripping it reproduces the committed
            # plate byte for byte.
            rec = (settings.get(path.stem) or {}).get("camera") or {}
            measured = round(g["degrees"], 2) if g else None
            recorded = rec.get("degrees")
            import numpy as np
            rows = (np.asarray(art)[:, :, 3] > 128).sum(1)
            widest = int(rows.argmax()) if rows.size else 0
            duties = sorted(d for d, name in by_duty.items() if name == path.stem)
            out.append({
                "name": path.stem,
                "file": path.name,
                "kb": round(path.stat().st_size / 1024),
                "orig": href(path, rel_to),
                "degrees": round(float(recorded), 2) if recorded is not None else measured,
                "measured": measured,
                "camera_from": (rec.get("from") if recorded is not None
                                else ("ring" if ringed else "outline")),
                "camera_note": rec.get("why"),
                "ringed": bool(ringed),
                "anchor": round(100.0 * widest / max(1, art.height), 1),
                "anchor_set": (settings.get(path.stem) or {}).get("anchor"),
                "duties": duties,
                "w": art.width, "h": art.height,
                "preview": preview(art, 360),
            })
        except Exception as exc:                                        # noqa: BLE001
            print("  could not read %s: %s" % (path.name, exc))
    return out


def preview(art, width):
    """A plate, small, as a data URI. The ONLY thing embedded now, and deliberately.

    The originals are referenced -- see href() -- but a preview is generated here and exists
    nowhere on disk, so there is nothing to reference. At 360 px across, five of them cost
    about as much as one paragraph of the page's own prose.
    """
    k = min(1.0, float(width) / max(1, art.width))
    small = art.resize((max(1, round(art.width * k)), max(1, round(art.height * k))),
                       Image.LANCZOS)
    back = Image.new("RGBA", small.size, (23, 19, 13, 255))
    back.alpha_composite(small)
    buf = io.BytesIO()
    back.convert("RGB").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def prompts(folder=None, rel_to=None):
    """The briefs that produced the art on file, offered to the clipboard.

    A prompt is an INPUT, exactly as the reference card is, and it has the same problem: the one
    that worked is a thing you have to be able to reproduce next time, and retyping it from a
    chat window is how it quietly drifts. So the text that produced a filed sculpt lives beside
    the tool and the page hands it back verbatim.

    Named after the sculpt they made, so the pairing is visible in the folder rather than
    remembered. Copy rather than download because a prompt's destination is a text box.

    A brief may DECLARE WHAT TO ATTACH, on a first line of the form

        <!-- attach: ui/assets-gothic/sculpts/player_2_v1.png -->

    which the page offers as a download beside the button. This matters more than it looks: a
    brief that says "don't change the base or the angle, use the same as in the attached image"
    is worthless without the right image, and produced nine passes out of ten only because the
    thing attached was already correct. The declaration travels with the text so the pairing
    cannot be lost, and it is stripped before copying -- the clipboard gets the brief, not its
    bookkeeping.
    """
    folder = folder or (HERE / "prompts")
    out = []
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        attach = []
        # AS MANY AS THE BRIEF NAMES, in the order it names them, because that is the order they
        # are attached in and the briefs say "the first attached image" and "the second".
        # ANY leading HTML comment is bookkeeping, not brief. It used to be only `attach:`
        # lines, and the first note written for a human reader -- an eight-line explanation of
        # why cobbles_oval attaches the plate it REPLACED -- went straight to the clipboard and
        # into the image model. A brief has to be able to carry a reason without the reason
        # becoming part of the instruction.
        while True:
            m = re.match(r"\s*<!--(.*?)-->[ \t]*\n", text, re.S)
            if not m:
                break
            text = text[m.end():]
            body = m.group(1).strip()
            if not body.lower().startswith("attach:"):
                continue                     # a note to whoever reads the file; not copied
            target = ROOT / body[len("attach:"):].strip()
            if not target.is_file():
                print("  %s names an attachment that is not there: %s"
                      % (path.name, target))
                continue
            attach.append({"name": target.name, "bytes": target.stat().st_size,
                           "uri": href(target, rel_to)})
        # A brief belongs beside the thing it makes: one named after a plate in
        # grounds/ is offered on the ground-tiles tab, the rest with the sculpts.
        # A BRIEF FOR A PLATE THAT IS STILL A CANDIDATE IS STILL A GROUND BRIEF. The rule was
        # "is there grounds/<name>.png", which is true only AFTER a brief has succeeded --
        # so the brief for a plate being worked on showed up beside the sculpts, which is
        # exactly when it is most in the way. Candidates are named <name>_cNN.png.
        made = (GROUNDS / (path.stem + ".png")).is_file()
        held = any((GROUNDS / "candidates").glob(path.stem + "_c*.png"))
        out.append({"name": path.stem, "text": text, "attach": attach,
                    "makes": "ground" if (made or held) else "sculpt"})
    return out


def reference_card(path=None, rel_to=None):
    """The card the next batch should be generated FROM, offered as a download.

    WHICH card is a live decision, not a constant of nature. Cards are appended rather than
    redrawn -- tools/ui_debug/generate_sculpt_reference.py holds all of them in CARDS, each
    recorded beside the sculpts it produced -- so this button has to name one, and it names the
    current one. Every brief in prompts/ also declares its own card in an `attach:` line, and
    those are what a brief was measured with; this button is the convenience copy of whichever
    card the work has moved on to. If the two ever disagree, the brief is right.

    THE ORIGINAL BYTES, not a re-encode and not the downscaled copy the page shows elsewhere.
    This file is an input to an image model: it carries a base drawn at a stated ellipse ratio
    and a scale line at a stated multiple of that base's width, and both survive only at the
    resolution they were drawn. A page that handed over a 520 px preview under the same filename
    would be handing over a different instruction while looking identical in the browser.

    Returned as a data URI so the button works from a file:// page, which is how this page is
    usually opened -- there is nothing to measure with offline, but there is still a card to
    fetch, and needing a server to collect a committed file would be absurd.
    """
    path = path or (ROOT / "ui" / "assets-gothic" / "references"
                    / "base_scale_reference_27_wall_127.png")
    if not path.is_file():
        return None
    im = Image.open(path)
    return {"name": path.name, "w": im.width, "h": im.height, "bytes": path.stat().st_size,
            "uri": href(path, rel_to)}


def without_background(im):
    """A best guess at the art in a screenshot, for a file that arrived with no alpha.

    Studio viewers and image models both hand back opaque pictures on a flat or gently graded
    backdrop. Thresholding the luminance and keeping the largest connected blob recovers the
    subject well enough to measure -- but it IS a guess, it is labelled as one everywhere it
    appears, and it never becomes the verdict. The file still has to be cut out before it can be
    filed, because the board composites it over a tile.
    """
    import numpy as np
    try:
        from scipy import ndimage
    except ModuleNotFoundError:
        return None

    a = np.asarray(im.convert("RGB")).astype(float)
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    ring = np.concatenate([lum[:3].ravel(), lum[-3:].ravel(),
                           lum[:, :3].ravel(), lum[:, -3:].ravel()])
    base = float(np.median(ring))
    spread = float(np.median(np.abs(ring - base)))
    mask = lum > base + max(10.0, 5.0 * spread)
    mask = ndimage.binary_closing(mask, np.ones((5, 5)))
    lab, n = ndimage.label(mask)
    if not n:
        return None
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    mask = ndimage.binary_fill_holes(lab == (int(np.argmax(sizes)) + 1))
    if mask.mean() > 0.95 or mask.mean() < 0.01:
        return None                       # it took the whole frame, or nothing: no use pretending
    out = np.asarray(im.convert("RGBA")).copy()
    out[..., 3] = np.where(mask, 255, 0)
    return Image.fromarray(out)


def judge(raw, target, tol, base_tol=BASE_TOLERANCE_PCT, thin_tol=BASE_THIN_PCT):
    """Measure one dropped file and say what is inside tolerance and what is not.

    TWO QUESTIONS, NOT THREE. Height was the third and has been withdrawn -- see the note where
    the proportion is measured. It is still reported; it is no longer a verdict.
    """
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    W, H = im.size
    checks, notes = [], []

    try:
        x0, y0, x1, y1 = sm.bbox(im)
    except AssertionError:
        return {"error": "the image is entirely transparent"}
    ink_w, ink_h = x1 - x0, y1 - y0
    # WHETHER IT IS CUT OUT IS A QUESTION ABOUT ALPHA, NOT ABOUT MARGINS. This once asked only
    # whether the art touched the canvas edge, so a PNG cropped flush to its own silhouette --
    # which every tight crop is, and which recolouring produces -- was declared to have no
    # transparency and quietly measured by the background ESTIMATE instead. It reported 29.1
    # for a figure whose alpha says 29.8, with nothing on screen to say it had guessed.
    alpha = np.asarray(im)[..., 3]
    clear_frac = float((alpha <= sm.ALPHA).mean())
    cut_out = clear_frac > 0.005
    checks.append(["cut out", "yes" if cut_out else "no transparency at all",
                   "ok" if cut_out else "bad",
                   "%.0f%% of the canvas is transparent; the board composites this over a tile"
                   % (100.0 * clear_frac)])
    if cut_out and not (x0 > 0 or y0 > 0 or x1 < W or y1 < H):
        checks.append(["margin", "trimmed flush", "info",
                       "cut out, but cropped hard against its own silhouette, so there is no "
                       "spare pixel for the edge-rim check to look at"])

    # NOT CUT OUT MEANS NOT MEASURED, and saying so is the whole point. With no alpha every row
    # is the full canvas width, so the base's bottom outline is flat, the ellipse comes out zero
    # and the angle reads 0.0 -- which looks like a measurement of a flat camera rather than the
    # absence of a measurement. Three derived checks failing on one root cause is how an operator
    # ends up fixing the wrong thing.
    if not cut_out:
        guess = without_background(im)
        row = {"kind": "sculpt" if ink_h > ink_w else "plate",
               "canvas": [W, H], "ink": [ink_w, ink_h],
               "clear_pct": round(100.0 * clear_frac, 1)}
        notes.append("This file has no transparency, so nothing below could be measured from it. "
                     "It has to be cut out before it can be filed: the board composites a sculpt "
                     "over a tile, and a plate over a tile face.")
        if guess is None:
            checks.append(["everything else", "not measured", "cannot",
                           "no alpha, and the background could not be separated either"])
            return {"row": row, "checks": checks, "notes": notes,
                    "overlay": overlay(im, None, row["kind"])}
        g2 = sm.ground_ellipse(guess, base_band=(row["kind"] == "sculpt"))
        notes.append("The numbers marked estimated come from removing the background by "
                     "brightness, which is a guess and not a verdict.")
        if g2:
            row["degrees"] = round(g2["degrees"], 1)
            checks.append(["camera angle, estimated", "%.1f deg" % g2["degrees"], "info",
                           "background removed by brightness; cut the file out to get a verdict"])
        checks.append(["everything else", "not measured", "cannot",
                       "needs a cut-out file, not a screenshot"])
        return {"row": row, "checks": checks, "notes": notes,
                "overlay": overlay(guess, g2, row["kind"])}

    # A SCULPT IS TALLER THAN IT IS WIDE AND A PLATE IS NOT. Crude, and stated rather than hidden:
    # a plate generated portrait would be read as a figure and measured in the wrong band.
    kind = "sculpt" if ink_h > ink_w else "plate"
    g = sm.ground_ellipse(im, base_band=(kind == "sculpt"))

    row = {"kind": kind, "canvas": [W, H], "ink": [ink_w, ink_h],
           "clear_pct": round(100.0 * clear_frac, 1)}

    if g:
        row["degrees"] = round(g["degrees"], 1)
        row["base_width"] = g["width"]
        row["minor_over_major"] = round(g["sin_theta"], 3)
    if kind == "sculpt":
        m = sm.measure(im)
        row.update({"plinth": m["plinth"], "wall": m["wall"],
                    "h_plinth": round(m["h_plinth"], 3),
                    # None when no rim was found -- sculpt_metrics._rim refuses to invent one,
                    # and a verdict computed from an invented wall is worse than no verdict.
                    "wall_ratio": (round(m["wall_ratio"], 3)
                                   if m["wall_ratio"] is not None else None),
                    "ripple": round(m["ripple"], 2)})
        if g:
            off = abs(g["degrees"] - target)
            checks.append(["camera angle", "%.1f deg" % g["degrees"],
                           "ok" if off <= tol else ("check" if off <= tol * 2 else "bad"),
                           "target %.0f, tolerance %.1f" % (target, tol)])
        band = reference_band()
        deg = g["degrees"] if g else None

        # (b) THE BASE ITSELF, before anything standing on it. Its own side wall over its own
        # width says how chunky the plinth is, which neither the camera nor the figure's height
        # can see: a thin base and a chunky one photograph at the same angle and carry the same
        # figure. Ten nuns measured 0.22 against ten monks at 0.13 -- bases two thirds thicker,
        # with both batches passing every other check they were given.
        base = _upright(m["wall_ratio"], deg)
        if m["wall_ratio"] is None:
            checks.append(["base height / width", "no rim found", "check",
                           "the plinth's lit rim is not a peak anywhere it could be -- the "
                           "wall was not measured, and a number was not invented for it"])
        elif band and "base_ratio" in band and base is not None:
            b = band["base_ratio"]
            row["base_ratio"] = round(base, 3)
            off = 100.0 * (base - b["mid"]) / b["mid"] if b["mid"] else 0.0
            # ASYMMETRIC: see the constants. Chunky and thin are different failures with
            # different evidence, and one number could only be right about one of them.
            room = base_tol if off >= 0 else thin_tol
            checks.append(["base height / width", "%+.1f%% of the set" % off,
                           "ok" if abs(off) <= room
                           else ("check" if abs(off) <= room * 1.5 else "bad"),
                           "wall/width %.3f at %.1f deg is %.3f upright, against a median of "
                           "%.3f -- %.0f%% thinner to %.0f%% chunkier is %.3f to %.3f"
                           % (m["wall_ratio"], deg, base, b["mid"], thin_tol, base_tol,
                              b["mid"] * (1 - thin_tol / 100.0),
                              b["mid"] * (1 + base_tol / 100.0))])

        # HEIGHT IS MEASURED AND SHOWN, BUT NOT JUDGED. It was a third check and it has been
        # withdrawn, because a pass/fail on it was answering a question the tool cannot settle.
        #
        # What the numbers said: the concept set sits at proportion 2.18 and the sculpts drawn at
        # the board's camera at 2.75, a 26% gap that survives dividing the camera out -- so the
        # verdict fired on every new sculpt, correctly by its own arithmetic and uselessly in
        # practice. Which of the two is right is a decision about how the game looks, and a
        # median of whatever happens to be on file cannot make it. Worse, the median moves as the
        # set fills: the same sculpt passes or fails depending on what was filed before it.
        #
        # So the proportion is still measured, still written into the row, and still drawn on the
        # figure picture, because comparing candidates by eye is easier with the number beside
        # them. It simply no longer carries a verdict. Height is judged by looking at the
        # candidates that got through the camera and the base.
        prop = _proportion(m["h_plinth"], deg)
        if prop is not None:
            row["proportion"] = round(prop, 3)
        fr = sm.fringe(im)
        checks.append(["edge rim", "%+.1f" % fr, "ok" if fr <= 0 else "check",
                       "a part-transparent rim lighter than the body is a halo; the art runs "
                       "about -20"])
    else:
        notes.append("A plate's outline is not an ellipse unless it was drawn circular, so the "
                     "angle below under-reads. Look at the drawing rather than the number.")
        if g:
            checks.append(["angle, by outline", "%.1f deg" % g["degrees"], "info",
                           "sanity check only; a circular plate makes this exact"])
        rows = (np.array(sm.crop_to_art(im))[..., 3] > sm.ALPHA).sum(1)
        widest = int(rows.argmax())
        row["standing_line"] = round(100.0 * widest / max(1, len(rows)))
        checks.append(["standing line", "%d%% down the ink" % row["standing_line"], "info",
                       "the anchor to start from in duty_grounds.json"])
        board = _board()
        place = board.placement([])
        art = board.figures(board.FIGURE_DIR, [])
        label = place.get("tuned_at", "210_plastic")
        # EVERY POSE, not the first of each seat. A painted seat is three poses and they are
        # not one width, so a capacity read off pose 1 would pass a set whose pose 3 overflows.
        # `seat` rather than `row`: there is a `row` dict two lines up, and a generator's own
        # scope is the only reason shadowing it here was harmless. Not a thing to leave standing.
        widest = max((f["w"] for seat in art.get(label, []) for f in seat), default=0)
        poses = max((len(seat) for seat in art.get(label, [])), default=0)
        cap = 2 * place["spread"] + widest
        frame_w = (place.get("frame") or {}).get("w", 320)
        checks.append(["five sculpts fit", "need %d of %d px" % (cap, frame_w),
                       "info" if not widest else ("ok" if cap <= frame_w else "bad"),
                       "spread %d and the widest of the %d seats drawn (%d px, %d pose%s each) "
                       "in %s, against the frame"
                       % (place["spread"], len(board.FIGURE_SEATS), widest, poses,
                          "" if poses == 1 else "s", label)])

    return {"row": row, "checks": checks, "notes": notes, "overlay": overlay(im, g, kind)}


def serve(page, port, open_it):
    """Serve the page and measure what it posts. Bound to 127.0.0.1 and nothing else.

    THE DOCUMENT ROOT IS THE REPOSITORY, and the page is handed out at its own path within it
    rather than at "/". That looks like a detail and is the thing that makes one href work in
    both modes: the page references a committed file as ../../../ui/assets-gothic/..., which
    resolves from tools/ui_debug/generated/ whether that folder is a directory on disk or a
    path on this server. Serving the page at "/" would have left every one of those pointing
    above the root.

    Serving files at all is what buys back the one-click download that referencing costs --
    Chromium ignores `download` on a file:// link and navigates to the image instead, so from
    disk the page can show you a file but not hand it over. Here it can.

    Read-only, and confined: a GET resolves under the repository or it is refused. Nothing is
    written, nothing outside is reachable, and it listens on the loopback address only.
    """
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code, body, kind="application/json"):
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):                                               # noqa: N802
            import mimetypes
            import urllib.parse

            want = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0])
            if want in ("/", "/index.html"):
                self.send_response(302)
                self.send_header("Location", "/" + page_path)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            # CONFINED. realpath first, then ask whether it is still inside the repository --
            # checking the string before resolving it would be fooled by a symlink, and
            # checking after resolving cannot be.
            target = pathlib.Path(os.path.realpath(str(ROOT / want.lstrip("/"))))
            root = pathlib.Path(os.path.realpath(str(ROOT)))
            if root != target and root not in target.parents:
                return self._send(403, json.dumps({"error": "outside the repository"}))
            if not target.is_file():
                return self._send(404, json.dumps({"error": "not found"}))
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target == pathlib.Path(os.path.realpath(str(page))):
                kind = "text/html; charset=utf-8"
            self._send(200, target.read_bytes(), kind)

        def do_POST(self):                                              # noqa: N802
            if self.path != "/measure":
                return self._send(404, json.dumps({"error": "not found"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                sent = json.loads(self.rfile.read(n).decode("utf-8"))
                raw = base64.b64decode(sent["data"].split(",", 1)[-1])
                target = float(sent.get("target", TARGET_DEGREES))
                tol = float(sent.get("tolerance", TOLERANCE_DEGREES))
                btol = float(sent.get("base_tolerance", BASE_TOLERANCE_PCT))
                bthin = float(sent.get("base_thin", BASE_THIN_PCT))
                result = judge(raw, target, tol, btol, bthin)
            except Exception as exc:                                    # noqa: BLE001
                print("  could not measure %s: %s" % (sent.get("name", "?"), exc))
                return self._send(400, json.dumps({"error": str(exc)}))
            worst = [c for c in result.get("checks", []) if c[2] == "bad"]
            print("  %-34s %-7s %s" % (sent.get("name", "?"),
                                       result.get("row", {}).get("kind", "?"),
                                       "%d failed" % len(worst) if worst else "all inside"))
            return self._send(200, json.dumps(result))

        def log_message(self, *a):
            return

    page_path = href(page, ROOT)
    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/%s" % (srv.server_address[1], page_path)
    print("  serving %s -- drop PNGs on it" % url)
    print("  document root is the repository, so the download links work here")
    print("  ctrl-c to stop")
    if open_it:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")


def scan(folder, match=None):
    """Measure a whole folder in one pass, so a batch of generations is judged as a batch.

    One file at a time through the page answers "is this one good". A run of twenty answers a
    different and more useful question -- whether the generator is off, or these particular
    files are -- and that only shows up when the spread is in front of you. So the summary line
    reports the batch's own spread alongside each file's verdict against the target.
    """
    if not folder.is_dir():
        return "not a folder: %s" % folder
    files = sorted(p for p in (folder.glob(match) if match else folder.iterdir())
                   if p.suffix.lower() in (".png", ".webp") and not p.name.startswith("."))
    if not files:
        return "no PNGs in %s%s" % (folder, " matching %s" % match if match else "")
    print("%-52s %-7s %8s  %s" % ("file", "kind", "angle", "against %.0f deg" % TARGET_DEGREES))
    kept = []
    for f in files:
        try:
            r = judge(f.read_bytes(), TARGET_DEGREES, TOLERANCE_DEGREES)
        except Exception as exc:                                        # noqa: BLE001
            print("%-52s %s" % (f.name[:52], "could not be read: %s" % exc))
            continue
        row = r["row"]
        deg = row.get("degrees")
        worst = [c for c in r["checks"] if c[2] == "bad"]
        if deg is None:
            verdict = "not measured"
        else:
            off = abs(deg - TARGET_DEGREES)
            verdict = ("ok" if off <= TOLERANCE_DEGREES
                       else ("check" if off <= 2 * TOLERANCE_DEGREES else "BAD"))
            verdict = "%-5s %+.1f" % (verdict, deg - TARGET_DEGREES)
            kept.append(deg)
        if worst and deg is not None:
            verdict += "   (%d other check%s failed)" % (len(worst), "" if len(worst) == 1 else "s")
        print("%-52s %-7s %8s  %s"
              % (f.name[:52], row.get("kind", "?"),
                 "-" if deg is None else "%.1f" % deg, verdict))
    if len(kept) >= 2:
        import statistics
        print("\n%d measured: mean %.1f deg, spread %.1f, sd %.2f"
              % (len(kept), statistics.mean(kept), max(kept) - min(kept),
                 statistics.stdev(kept)))
        inside = [d for d in kept if abs(d - TARGET_DEGREES) <= TOLERANCE_DEGREES]
        print("%d of %d inside %.1f of the %.0f degree target"
              % (len(inside), len(kept), TOLERANCE_DEGREES, TARGET_DEGREES))
        # A SHARED BIAS IS ONLY A CLAIM YOU CAN MAKE ABOUT A BATCH. Told to measure a folder of
        # unrelated art this read a 90 degree spread and still announced that every generation
        # shared one bias -- true of a run from one prompt, nonsense about a mixed folder. So the
        # spread has to be tight enough to BE a batch before the tool says anything causal.
        sd = statistics.stdev(kept)
        off = statistics.mean(kept) - TARGET_DEGREES
        if sd > 2 * TOLERANCE_DEGREES:
            print("these are not one batch (sd %.1f deg), so the mean says nothing about a "
                  "prompt; read the rows rather than the summary" % sd)
        elif abs(off) > TOLERANCE_DEGREES:
            print("the BATCH is off, not the files: the generations agree with each other "
                  "(sd %.2f) and share a %+.1f deg bias, which is a prompt to change rather "
                  "than files to discard" % (sd, off))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="where to write the page (default: %s)" % OUT.relative_to(ROOT))
    ap.add_argument("--open", action="store_true", default=True, help=argparse.SUPPRESS)
    ap.add_argument("--no-open", dest="open", action="store_false",
                    help="write the page without opening it")
    ap.add_argument("--serve", nargs="?", type=int, const=8766, default=None, metavar="PORT",
                    help="serve the page so it can measure what you drop on it "
                         "(default port %(const)s); without this there is nothing to measure with")
    ap.add_argument("--scan", default=None, metavar="DIR",
                    help="measure every PNG in DIR and print one table, instead of writing the "
                         "page; for judging a batch of generations in one pass")
    ap.add_argument("--match", default=None, metavar="GLOB",
                    help="with --scan, only files matching this glob, so one run of generations "
                         "is measured rather than everything in the folder")
    args = ap.parse_args()
    if Image is None:
        raise SystemExit("Pillow is not installed, and there is nothing to measure without it "
                         "(pip3 install --user Pillow)")

    if args.scan:
        raise SystemExit(scan(pathlib.Path(args.scan).expanduser(), args.match))

    out = pathlib.Path(args.out).expanduser() if args.out else OUT
    band = reference_band()
    page = (TEMPLATE
            .replace("__TARGET__", json.dumps(TARGET_DEGREES))
            .replace("__TOL__", json.dumps(TOLERANCE_DEGREES))
            .replace("__BTOL__", json.dumps(BASE_TOLERANCE_PCT))
            .replace("__BTHIN__", json.dumps(BASE_THIN_PCT))
            .replace("__GTARGET__", json.dumps(GROUND_TARGET_DEGREES))
            .replace("__GTOL__", json.dumps(GROUND_TOLERANCE_DEGREES))
            .replace("__BAND__", json.dumps(band))
            .replace("__ONRECORD__", json.dumps(on_record(rel_to=out.parent)))
            .replace("__GROUNDS__", json.dumps(ground_record(rel_to=out.parent)))
            .replace("__CARD__", json.dumps(reference_card(rel_to=out.parent)))
            .replace("__PROMPTS__", json.dumps(prompts(rel_to=out.parent)))
            .replace("__ARRANGE__", json.dumps(arrangement_picture()))
            .replace("__INGAME__", json.dumps(
                arrangement_picture(colour=True, plain=True))))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    if band and "degrees" in band:
        b = band["degrees"]
        print("  the set on record sits %.1f to %.1f degrees (median %.1f, %d figures)"
              % (b["lo"], b["hi"], b["mid"], b["n"]))
    if band and "proportion" in band:
        b = band["proportion"]
        print("  and %.2f to %.2f in proportion (median %.2f) -- REPORTED, NOT JUDGED"
              % (b["lo"], b["hi"], b["mid"]))
    print("  target %.0f deg, tolerance %.1f  (height is not checked)"
          % (TARGET_DEGREES, TOLERANCE_DEGREES))
    # THREE DECIMALS, TRAILING ZEROS STRIPPED. At two this printed "31.55", which is the value
    # the target was deliberately moved AWAY from -- rounding it there is what put slate exactly
    # on the boundary, and a readout that shows the rounded number undoes the correction every
    # time someone reads it. The ring picture was fixed the same way on 2026-09-24.
    print("  ground plates: %s deg target, tolerance %s -- LOCKED, not derived per run"
          % (_trim(GROUND_TARGET_DEGREES), _trim(GROUND_TOLERANCE_DEGREES)))
    print("                 (window %s to %s; a sculpt's tolerance is %.1f)"
          % (_trim(GROUND_TARGET_DEGREES - GROUND_TOLERANCE_DEGREES),
             _trim(GROUND_TARGET_DEGREES + GROUND_TOLERANCE_DEGREES), TOLERANCE_DEGREES))
    if band and "base_ratio" in band:
        m = band["base_ratio"]["mid"]
        print("  base %.3f to %.3f  (median %.3f, %.0f%% thinner to %.0f%% chunkier)"
              % (m * (1 - BASE_THIN_PCT / 100.0), m * (1 + BASE_TOLERANCE_PCT / 100.0),
                 m, BASE_THIN_PCT, BASE_TOLERANCE_PCT))
    if args.serve is not None:
        serve(out, args.serve, args.open)
    else:
        print("  file://%s" % out.resolve())
        print("  (nothing to measure with: re-run with --serve)")


TEMPLATE = r"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Asset check</title>
<style>
html,body{margin:0;min-height:100%;background:#0d0b08;color:#8b8071;
  font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
#head{padding:14px 18px 4px;color:#5f574a}
#head b{color:#c9b27a;font-weight:400}
#bar{display:flex;gap:10px;align-items:center;padding:6px 18px 10px;flex-wrap:wrap}
#bar label{color:#4f483d}
#bar input{font:inherit;color:#c9b27a;background:#17130d;border:1px solid #332c20;
  border-radius:3px;padding:3px 6px;width:56px}
#drop{margin:4px 18px 14px;border:1px dashed #3a3226;border-radius:4px;padding:26px;
  text-align:center;color:#5f574a;transition:border-color .15s,background .15s}
#drop.over{border-color:#c9b27a;background:rgba(201,178,122,.06);color:#c9b27a}
#cards{display:flex;flex-direction:column;gap:12px;padding:0 18px 30px}
.card{display:flex;gap:14px;background:#17130d;border:1px solid #221c14;border-radius:3px;
  padding:12px}
.card img{display:block;max-width:360px;height:auto;border-radius:2px}
.meta{flex:1;min-width:280px}
.name{color:#c9b27a;margin-bottom:2px}
.kind{color:#4f483d;margin-bottom:8px}
table{border-collapse:collapse;width:100%}
td{padding:2px 8px 2px 0;vertical-align:top}
td.v{color:#c9b27a;white-space:nowrap}
td.why{color:#403a31}
.ok{color:#8fae6a} .check{color:#d8b45e} .bad{color:#e0705f} .info{color:#5f574a}
.note{color:#7a6f5d;margin-top:8px}
.key{color:#403a31;margin-top:10px;line-height:1.7}
.key i{font-style:normal}
.k1{color:#ff6060} .k2{color:#78c8ff} .k3{color:#78ff96} .k4{color:#ffd47e}
#record{padding:4px 18px 14px}
#record h2{font:11px/1.5 inherit;font-weight:400;color:#5f574a;margin:0 0 8px;max-width:96ch}
#record h2 b{color:#8b8071;font-weight:400}
#record .row{display:flex;gap:18px;flex-wrap:wrap}
#record .one{background:#17130d;border:1px solid #241d13;padding:8px;max-width:366px}
/* The reference card's download, above the row it produced. */
#card{margin:0 0 10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
#card .dl{display:inline-block;padding:6px 12px;border:1px solid #4a5a3a;border-radius:3px;
  background:#1c1811;color:#c9b27a;text-decoration:none;white-space:nowrap}
#card .dl:hover{border-color:#8fae6a;background:#201c13}
#card .note{color:#5f574a;max-width:720px;line-height:1.45}
#allsculpts{margin:0 0 10px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
#allsculpts .dlall{font:inherit;color:#c9b27a;background:#1c1811;border:1px solid #4a5a3a;
  border-radius:3px;padding:6px 12px;cursor:pointer;white-space:nowrap}
#allsculpts .dlall:hover{border-color:#8fae6a;background:#201c13}
#allsculpts .dlall[disabled]{color:#5f574a;border-color:#332c20;cursor:not-allowed}
#allsculpts .note{color:#5f574a;max-width:720px;line-height:1.45}
#allsculpts .note b{color:#8b8071;font-weight:400}
/* The briefs, on the same shelf as the card they were used with. */
#prompts{margin:0 0 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
#prompts .lab{color:#3f3930;letter-spacing:.06em;text-transform:uppercase}
#prompts .cp{font:inherit;color:#c9b27a;background:#1c1811;border:1px solid #4a5a3a;
  border-radius:3px;padding:6px 12px;cursor:pointer;white-space:nowrap}
#prompts .cp:hover{border-color:#8fae6a;background:#201c13}
#prompts .att{font:inherit;color:#8b8071;background:#17130d;border:1px solid #332c20;
  border-radius:3px;padding:6px 10px;text-decoration:none;white-space:nowrap}
#prompts .att:hover{border-color:#5a4c36;color:#c9b27a}
#tabs{margin:18px 0 0;display:flex;gap:6px}
#tabs .tab{font:inherit;color:#8b8071;background:#17130d;border:1px solid #332c20;border-bottom:none;border-radius:3px 3px 0 0;padding:6px 16px;cursor:pointer}
#tabs .tab.on{color:#d8d0c0;background:#221d14;border-color:#5a4c36}
#tabs .tab:hover{color:#c9b27a}
.plate{display:inline-block;vertical-align:top;margin:0 14px 18px 0;max-width:24em}
.plate img{display:block;max-width:100%;border:1px solid #2a241a}
.plate .who{font-size:11px;color:#8b8071;margin-top:3px}
.one .orig,.plate .orig{display:block;margin:5px auto 0;max-width:22em;font:11px/1.5 inherit;color:#8b8071;background:#17130d;border:1px solid #332c20;border-radius:3px;padding:3px 7px;text-decoration:none;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.one .orig:hover,.plate .orig:hover{border-color:#5a4c36;color:#c9b27a}
#prompts .note{color:#5f574a;max-width:700px;line-height:1.45}
#prompts .note.ok{color:#8fae6a} #prompts .note.bad{color:#e0705f}
/* the caption used to set the cell's width -- one long line made the tile cell 528 px and
   wrapped the row at 1600. It wraps to the picture's width instead. */
#record .one .num{white-space:normal;max-width:366px}
#record .one .nm{color:#c9b27a;padding-bottom:4px}
#record .one .num{color:#5f574a;padding-top:4px}
#record img{display:block}
#record .fig{height:250px}
#record .tileimg{height:476px}
#record .tile{margin-top:16px}
#record .tile .cap{color:#5f574a;padding-bottom:6px;max-width:96ch}
#record .tile .bad{color:#ff8a8a}
</style>
<div id=head>Drop a sculpt or a ground plate. It is measured by
<b>tools/ui_debug/sculpt_metrics.py</b> &#8212; the same code that builds the pieces &#8212;
and drawn back with the measurement on it.</div>
<div id=bar>
  <label for=target>target angle</label><input id=target value=__TARGET__>
  <label for=tol>tolerance</label><input id=tol value=__TOL__>
  <label for=btol>base, max % chunkier</label><input id=btol value=__BTOL__>
  <label for=bthin>max % thinner</label><input id=bthin value=__BTHIN__>
  <label for=gtarget>ground target</label><input id=gtarget value=__GTARGET__>
  <label for=gtol>ground tol</label><input id=gtol value=__GTOL__>
  <span id=ref class=info></span>
</div>
<div id=tabs><button class="tab on" data-t=record>sculpts</button><button class=tab data-t=grounds>ground tiles</button></div>
<div id=record></div>
<div id=grounds hidden></div>
<div id=drop>drop PNGs here</div>
<div id=cards></div>
<script>
var BAND = __BAND__;
var ONRECORD = __ONRECORD__;
var GROUNDS = __GROUNDS__;
var CARD = __CARD__;
var PROMPTS = __PROMPTS__;
var ARRANGE = __ARRANGE__;
var INGAME = __INGAME__;
(function(){
  if (!ONRECORD || !ONRECORD.length) return;
  var host = document.getElementById("record");
  var h = ["<h2>The sculpts on file in <b>ui/assets-gothic/sculpts/</b>. Below each figure, the "
           + "two numbers check (b) compares: the base's own width, and the lit wall above it."
           + "<br>Height is <b>reported, not judged</b>. It was a third check against the median "
           + "of whatever was on file, and that median is a fact about the folder rather than "
           + "about the figure &#8212; it moves as the set fills, and the two sets on file "
           + "disagree by 26&#37; in proportion with the camera already divided out. Which "
           + "proportion is wanted is a look, so it is decided by comparing the candidates that "
           + "got past the camera and the base."
           + "<br>The base median a newcomer IS judged against is <b>not</b> these figures: it still comes from <b>ui/concept/</b>, the 9&#176; art being replaced. That one survives because both sets agree on it &#8212; concept 0.132&#8211;0.146 against 0.126&#8211;0.141 here &#8212; but two sets on one page are two sets, so read the number knowing which it is."
           + "<br>The last cell is five of them on a tile, at the spread, rank and frame from "
           + "<b>duty_placement.json</b>, with the middle of the front three stepped FORWARD "
           + "until the top of its plinth reaches the floor line &#8212; where that file still "
           + "says set it back. A plinth is as deep as it is wide times sin(camera), so raising "
           + "the camera from 9&#176; to 32&#176; made every base three times deeper without "
           + "moving a number there, and at a set-back of 21 the middle plinth overlaps both of "
           + "the back rank's. Overlap is rasterised and intersected, not judged by eye.</h2>"];
  // THE CARD THESE WERE GENERATED FROM, to hand back to the image model for the next seat.
  // Above the figures rather than beside them because it comes FIRST in the actual job: you
  // fetch the card, you generate against it, and then you drop what comes back here.
  if (CARD) {
    h.push("<div id=card><a class=dl download='" + CARD.name + "' href='" + CARD.uri + "'>"
           + "&#8595;&nbsp; download " + CARD.name + "</a>"
           + "<span class=note>the reference the three sculpts below were generated from &#183; "
           + CARD.w + "&#215;" + CARD.h + " px, " + Math.round(CARD.bytes / 1024) + " KB, the "
           + "committed file byte for byte. Attach it when generating the next seat.</span>"
           + "</div>");
  }
  // EVERY FILED SCULPT AT ONCE, as the committed originals rather than the previews. Each cell
  // below already offers its own file; this is the same nine links without nine visits.
  //
  // IT REFUSES ON A file:// PAGE INSTEAD OF MISBEHAVING. Chromium ignores the `download`
  // attribute on a file:// link and NAVIGATES to the image, so firing nine of them would throw
  // the page away and leave you looking at a PNG with no way back but the back button. Served,
  // the identical hrefs download -- which is the trade href() already documents.
  (function(){
    var filed = (ONRECORD || []).filter(function(r){
      return r.orig && /^player_\d+/.test(r.name);
    });
    if (!filed.length) return;
    var kb = filed.reduce(function(a, r){ return a + (r.kb || 0); }, 0);
    var served = location.protocol === "http:" || location.protocol === "https:";
    h.push("<div id=allsculpts><button class=dlall" + (served ? "" : " disabled")
           + ">&#8595;&nbsp; download all sculpts</button>"
           + "<span class=note>" + filed.length + " committed files, "
           + (kb / 1024).toFixed(1) + " MB, byte for byte &#183; "
           + (served
              ? "the browser asks once to allow multiple downloads"
              : "<b>needs --serve</b>: from a file:// page the browser navigates to the image "
                + "instead of saving it, so the button is disabled here")
           + "</span><span class=note id=allsay></span></div>");
  })();
  // THE PROMPTS THAT WORKED, beside the card they were used with -- the two halves of one
  // instruction. Copied rather than downloaded: a prompt's destination is a text box.
  var SCULPT_PROMPTS = (PROMPTS || []).filter(function(p){ return p.makes !== "ground"; });
  if (SCULPT_PROMPTS.length) {
    var ph = ["<div id=prompts><span class=lab>copy the brief:</span>"];
    SCULPT_PROMPTS.forEach(function(p, i){
      // THE ATTACHMENT COMES FIRST, then the brief. "use the same base and angle as in the
      // attached image" is only an instruction if the attachment is the right file -- and the
      // order you do it in is attach, then paste. A link sitting after the button read as an
      // afterthought and was easy to copy the brief without.
      (p.attach || []).forEach(function(a, k){
        ph.push("<a class=att download='" + a.name + "' href='" + a.uri + "'>"
                + "&#128206;&nbsp; " + (k + 1) + ". " + a.name + "</a>");
      });
      ph.push("<button class=cp data-i='" + PROMPTS.indexOf(p) + "'>&#128203;&nbsp; "
              + p.name + "</button>");
    });
    ph.push("<span class=note id=cpsay>the brief that produced the sculpt of the same name, "
            + "verbatim from tools/ui_debug/prompts/</span></div>");
    h.push(ph.join(""));
  }
  // ONE ROW PER SEAT, rather than one long row that wraps wherever the window happens to end.
  // Seat 3 leads because it is the set a newcomer is compared against; the seats filed after it
  // sit underneath, so a row is a seat and not an accident of viewport width.
  var seats = {}, order = [];
  ONRECORD.forEach(function(r){
    var seat = (r.name.match(/^player_\d+/) || ["other"])[0];
    if (!seats[seat]) { seats[seat] = []; order.push(seat); }
    seats[seat].push(r);
  });
  order.sort(function(a, b){
    if (a === "player_3") return -1;              // the reference set leads
    if (b === "player_3") return 1;
    return a < b ? -1 : 1;
  });
  function cell(r){
    h.push("<div class=one><div class=nm>" + r.name + "</div>");
    h.push("<img class=fig src='" + r.figure + "' alt=''>");
    if (r.plinth) h.push("<img src='" + r.plinth + "' alt=''>");
    h.push("<div class=num>" + (r.degrees == null ? "&#8212;" : r.degrees.toFixed(1) + " deg")
           + " &#183; base " + (r.base == null ? "&#8212;" : r.base.toFixed(3))
           + " &#183; height " + (r.proportion == null ? "&#8212;" : r.proportion.toFixed(2))
           + "</div>");
    if (r.orig) {
      h.push("<a class=orig download='" + r.file + "' href='" + r.orig + "'>"
             + "&#8595;&nbsp; " + r.file + " &#183; " + r.kb + " KB</a>");
    }
    h.push("</div>");
  }
  order.forEach(function(seat){
    h.push("<div class=row>");
    seats[seat].forEach(cell);
    h.push("</div>");
  });
  // THE TILES GET THEIR OWN ROW, side by side. They were the tail of the seat-3 row until a
  // fifth card pushed one of them onto a line of its own at any ordinary window width -- and
  // these two exist to be compared with each other, so they have to sit together.
  (function(){
    if (!ARRANGE && !INGAME) return;
    h.push("<div class=row>");
    if (ARRANGE) {
      h.push("<div class=one><div class=nm>five on a tile &#183; " + ARRANGE.plate + "</div>"
             + "<img class=tileimg src='" + ARRANGE.uri + "' alt=''>"
             + "<div class=num>" + ARRANGE.span + " of " + ARRANGE.frame + " px across &#183; "
             + (ARRANGE.clashes ? "<span class=bad>" + ARRANGE.clashes + " plinth clash</span>"
                                : "no plinths overlap")
             + (ARRANGE.low > ARRANGE.drop
                ? " &#183; <span class=bad>front plinth needs " + (ARRANGE.low - ARRANGE.drop)
                  + " px more drop</span>" : "")
             + "</div></div>");
    }
    // THE SAME TILE WITH NOTHING WRITTEN ON IT, in the seat colours: the measurements answer
    // whether it fits, and this answers whether it reads. They are different questions and the
    // second one cannot be asked while the first one's ellipses are drawn over the figures.
    if (INGAME) {
      h.push("<div class=one><div class=nm>the same tile, in game</div>"
             + "<img class=tileimg src='" + INGAME.uri + "' alt=''>"
             + "<div class=num>seat colours over the grey sculpts, no measurements &#183; "
             + "a PREVIEW: nothing in the pipeline recolours a sculpt, the four on file came "
             + "coloured from the generator</div></div>");
    }
    h.push("</div>");
  })();
  host.innerHTML = h.join("");

  // TWO WAYS TO COPY, because this page is usually opened as a file. navigator.clipboard needs
  // a secure context and a user gesture; a click supplies the gesture, but if the context is
  // refused there is still execCommand on a temporary textarea. Falling back silently would
  // leave a button that looks like it worked, so the note says which happened either way.
  function toClipboard(text, done){
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function(){ done(true); },
                                              function(){ done(legacy(text)); });
      return;
    }
    done(legacy(text));
  }
  function legacy(text){
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed"; ta.style.top = "-1000px";
    document.body.appendChild(ta);
    ta.select(); ta.setSelectionRange(0, ta.value.length);
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  // ONE LINK AT A TIME, spaced out. A browser that is handed nine simultaneous downloads drops
  // most of them silently; 150 ms apart it keeps all nine. The count is reported when it is done
  // so a batch that was quietly refused does not look like a batch that arrived.
  (function(){
    var b = host.querySelector("#allsculpts .dlall");
    if (!b || b.disabled) return;
    b.onclick = function(){
      var filed = (ONRECORD || []).filter(function(r){
        return r.orig && /^player_\d+/.test(r.name);
      });
      var say = document.getElementById("allsay"), i = 0;
      b.disabled = true;
      say.textContent = "";
      (function next(){
        if (i >= filed.length) {
          b.disabled = false;
          say.textContent = "asked the browser for " + filed.length + " files \u2014 check the "
                            + "downloads list, and allow multiple downloads if it asked";
          return;
        }
        var r = filed[i++];
        var a = document.createElement("a");
        a.href = r.orig; a.download = r.file;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(next, 150);
      })();
    };
  })();
  host.querySelectorAll("#prompts .cp").forEach(function(b){
    b.onclick = function(){
      var p = PROMPTS[+b.dataset.i], say = document.getElementById("cpsay");
      toClipboard(p.text, function(ok){
        say.textContent = ok
          ? p.name + " copied — " + p.text.length + " characters, paste it as it is"
          : "could not reach the clipboard; the browser refused it on this page";
        say.className = ok ? "note ok" : "note bad";
      });
    };
  });
})();
if (BAND && BAND.degrees)
  document.getElementById("ref").textContent =
    "the set on record sits " + BAND.degrees.lo.toFixed(1) + " to "
    + BAND.degrees.hi.toFixed(1) + " deg"
    + (BAND.h_plinth ? ", height/plinth " + BAND.h_plinth.lo.toFixed(2) + " to "
       + BAND.h_plinth.hi.toFixed(2) + " (median " + BAND.h_plinth.mid.toFixed(2) + ")" : "");

var drop = document.getElementById("drop"), cards = document.getElementById("cards");
["dragenter", "dragover"].forEach(function(e){
  drop.addEventListener(e, function(ev){ ev.preventDefault(); drop.classList.add("over"); });
});
["dragleave", "drop"].forEach(function(e){
  drop.addEventListener(e, function(ev){ ev.preventDefault(); drop.classList.remove("over"); });
});
drop.addEventListener("drop", function(ev){
  [].forEach.call(ev.dataTransfer.files, measure);
});

function card(name, html){
  var el = document.createElement("div");
  el.className = "card";
  el.innerHTML = html;
  cards.insertBefore(el, cards.firstChild);
  return el;
}

// MEASURED ON THE SERVER, always. A copy of the maths in here would agree today and drift the
// first time a threshold moved, and both halves would look correct on their own.
function measure(file){
  if (location.protocol !== "http:" && location.protocol !== "https:"){
    card(file.name, "<div class=meta><div class=name>" + file.name
      + "</div><div class='kind bad'>This page was opened from disk, so there is nothing to "
      + "measure with. Re-run the generator with --serve.</div></div>");
    return;
  }
  var reader = new FileReader();
  reader.onload = function(){
    fetch("/measure", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: file.name, data: reader.result,
                            target: +document.getElementById("target").value,
                            tolerance: +document.getElementById("tol").value,
                            base_tolerance: +document.getElementById("btol").value,
                            base_thin: +document.getElementById("bthin").value})})
      .then(function(r){ return r.json().then(function(j){ return [r.ok, j]; }); })
      .then(function(pair){ show(file.name, pair[0], pair[1]); })
      .catch(function(e){ show(file.name, false, {error: String(e)}); });
  };
  reader.readAsDataURL(file);
}

function show(name, ok, res){
  if (!ok || res.error){
    card(name, "<div class=meta><div class=name>" + name
      + "</div><div class='kind bad'>" + (res.error || "refused") + "</div></div>");
    return;
  }
  var r = res.row, h = "";
  h += '<img src="' + res.overlay + '">';
  h += '<div class=meta><div class=name>' + name + '</div>';
  h += '<div class=kind>read as a <b>' + r.kind + '</b> &#183; canvas ' + r.canvas[0] + '&#215;'
     + r.canvas[1] + ' &#183; art ' + r.ink[0] + '&#215;' + r.ink[1]
     + ' &#183; ' + r.clear_pct + '% clear</div>';
  h += "<table>";
  res.checks.forEach(function(c){
    h += '<tr><td>' + c[0] + '</td><td class=v>' + c[1] + '</td><td class="v ' + c[2] + '">'
       + c[2] + '</td><td class=why>' + c[3] + '</td></tr>';
  });
  h += "</table>";
  (res.notes || []).forEach(function(n){ h += '<div class=note>' + n + '</div>'; });
  h += '<div class=key><i class=k1>red</i> the widest row of the base &#183; '
     + '<i class=k2>blue</i> the outline\'s bottom at the edges &#183; '
     + '<i class=k3>green</i> its bottom at the centre &#183; '
     + '<i class=k4>gold</i> the ellipse those imply. If the gold does not sit on the base, the '
     + 'numbers are measuring the wrong thing.</div>';
  h += '</div>';
  card(name, h);
}

(function(){
  // THE PLATES, on the one check they share with a sculpt. A plate nobody stands on is NAMED
  // rather than hidden: three of the five are kept precisely as the evidence of what a camera
  // mismatch looks like, and a panel that quietly dropped them would be throwing that away.
  if (!GROUNDS || !GROUNDS.length) return;
  // The target and the tolerance live in the boxes at the top, not in a constant -- they are
  // tunable while the page is open.
  // A PLATE HAS ITS OWN TARGET AS WELL AS ITS OWN TOLERANCE. It used to borrow the sculpts'
  // 32.0 and differ only in tolerance, on the reasoning that ground and figure must agree
  // about where you are standing -- which is true, and is still checked, but is not the same
  // as the two being judged by one number. Both plate numbers were derived once from the
  // plates on file and then LOCKED: 31.545 is what that set averaged and 0.48 is how far
  // its furthest member sat from that, rounded up -- at the exact 0.475 the two extreme
  // plates would sit on the boundary, where a binary comparison of equal decimals is a
  // coin toss. Derived once, then fixed, so filing a plate cannot
  // move the bar the next one is judged by. The sculpts keep 32.0, and the gap between the two --
  // four tenths of a degree, well inside either tolerance -- is itself the agreement.
  var TARGET = +document.getElementById("gtarget").value;
  var TOL = +document.getElementById("gtol").value;   // a plate's own, tighter than a sculpt's
  var host = document.getElementById("grounds");
  var h = ["<h2>The ground plates in <b>ui/assets-gothic/grounds/</b>, judged on the camera and "
           + "nothing else. A plate has no plinth and no figure, so the base and height checks "
           + "have nothing to measure &#8212; but the camera is the same arithmetic as a "
           + "sculpt's base, because a circle on the ground seen from above draws an ellipse of "
           + "sin(angle) &#215; its width whether it is a figurine's plinth or the floor it "
           + "stands on. Ground and figure have to agree about where you are standing."
           + "<br><b>anchor</b> is where down the plate the standing line falls. The measured "
           + "value is the widest row of the art; the second is what <b>duty_grounds.json</b> "
           + "sets. They differ by a point or so, always the same way, which reads as feet set "
           + "deliberately forward of the widest row rather than as drift &#8212; so both are "
           + "shown and neither is called wrong.</h2>"];
  var GROUND_PROMPTS = (PROMPTS || []).filter(function(p){ return p.makes === "ground"; });
  if (GROUND_PROMPTS.length) {
    var gp = ["<div id=prompts><span class=lab>copy the brief:</span>"];
    GROUND_PROMPTS.forEach(function(p){
      (p.attach || []).forEach(function(a, k){
        gp.push("<a class=att download='" + a.name + "' href='" + a.uri + "'>"
                + "&#128206;&nbsp; " + (k + 1) + ". " + a.name + "</a>");
      });
      gp.push("<button class=cp data-i='" + PROMPTS.indexOf(p) + "'>&#128203;&nbsp; "
              + p.name + "</button>");
    });
    gp.push("<span class=note>the brief that produced the plate of the same name, verbatim "
            + "from tools/ui_debug/prompts/</span></div>");
    h.push(gp.join(""));
  }
  GROUNDS.forEach(function(r){
    var off = r.degrees == null ? 99 : Math.abs(r.degrees - TARGET);
    var cls = off <= TOL ? "ok" : (off <= 2 * TOL ? "check" : "bad");
    h.push("<div class=plate><div class=nm>" + r.name + "</div>");
    h.push("<img src='" + r.preview + "' alt=''>");
    h.push("<div class=num><span class=" + cls + ">"
           + (r.degrees == null ? "&#8212;" : r.degrees.toFixed(1) + " deg") + "</span>"
           + " &#183; anchor " + r.anchor.toFixed(1) + "%"
           + (r.anchor_set == null ? "" : " (file says " + r.anchor_set + ")")
           + " &#183; " + r.w + "&#215;" + r.h + "</div>");
    // NOT "kept as evidence of a camera that missed". That was true when every duty-less plate
    // was also a failed one; two of them now pass and the line was calling them mistakes.
    // Standing on nobody and being wrong are separate facts, so they are separate sentences.
    h.push("<div class=who>" + (r.duties.length
           ? r.duties.length + " dut" + (r.duties.length === 1 ? "y" : "ies") + ": "
             + r.duties.join(", ")
           : (cls === "ok"
              ? "no duty stands on this one yet &#8212; ready for the next one added"
              : "no duty stands on this one &#8212; kept as evidence of a camera that missed"))
           + "</div>");
    h.push("<a class=orig download='" + r.file + "' href='" + r.orig + "'>"
           + "&#8595;&nbsp; " + r.file + " &#183; " + r.kb + " KB</a>");
    h.push("</div>");
  });
  host.innerHTML = h.join("");
})();
(function(){
  var tabs = document.querySelectorAll("#tabs .tab");
  Array.prototype.forEach.call(tabs, function(b){
    b.addEventListener("click", function(){
      Array.prototype.forEach.call(tabs, function(o){ o.classList.remove("on"); });
      b.classList.add("on");
      document.getElementById("record").hidden = b.dataset.t !== "record";
      document.getElementById("grounds").hidden = b.dataset.t !== "grounds";
    });
  });
})();
</script>
"""


if __name__ == "__main__":
    main()
