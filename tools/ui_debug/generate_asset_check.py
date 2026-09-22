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
it is exact -- the four figures in the set agree to within a degree. A ground plate's edge is
ragged cobble or stepped stone, the outline is not an ellipse, and the same measurement
under-reads: the two plates on record come out 25 and 17.8 degrees by outline against 38.5 by
bounding box. So a plate gets numbers and a drawing of where they landed, and no verdict on its
angle. The honest reading of a plate is the aspect of a square paving stone on its surface, and
that still wants an eye. Generating plates with a circular outline makes them measurable.

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
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "asset_check.html"

sys.path.insert(0, str(HERE))
import numpy as np                                                      # noqa: E402
import sculpt_metrics as sm                                             # noqa: E402

try:
    from PIL import Image, ImageDraw
except ModuleNotFoundError:                                             # pragma: no cover
    Image = ImageDraw = None

CONCEPT = ROOT / "ui" / "concept"
SCULPTS = ROOT / "ui" / "assets-gothic" / "sculpts"
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
# How far a figure may stand from the set's median height before it is a problem.
# Height is carried as height/plinth because levelling makes every plinth the same
# width, so that ratio IS the levelled height -- a figure generated larger or
# smaller compares directly with its siblings.
HEIGHT_TOLERANCE_PCT = 8.0
# How far a plinth may be chunkier or thinner than the set's, measured as its own side wall over
# its own width. A separate question from the camera and from the figure's height: a thin base
# and a chunky one photograph at the same angle and carry the same figure. Wider than the height
# tolerance because it is a smaller measurement on a shorter edge, and so noisier.
BASE_TOLERANCE_PCT = 12.0


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


def plinth_picture(im, width=340):
    """The base on its own, magnified, with the two numbers check (b) compares drawn on it.

    The band is printed as figures everywhere else, and a figure is a poor way to hold a shape in
    your head while looking at a new sculpt. The width is measured across the widest row of the
    base; the wall is the lit rim down to the bottom of the art, which is what `measure` finds by
    looking for the brightest row. Drawing both on the actual pixels they were taken from is the
    only way to see that they were taken from the right place.
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

    buf = io.BytesIO()
    back.convert("RGB").save(buf, "WEBP", quality=90, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def figure_picture(im, height=250):
    art = sm.crop_to_art(im)
    k = height / art.height
    big = art.resize((max(1, round(art.width * k)), height), Image.LANCZOS).convert("RGBA")
    back = Image.new("RGBA", big.size, (23, 19, 13, 255))
    back.alpha_composite(big)
    buf = io.BytesIO()
    back.convert("RGB").save(buf, "WEBP", quality=88, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def on_record(folder=SCULPTS):
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
                        "degrees": round(g["degrees"], 1) if g else None,
                        "base": round(_upright(m["wall_ratio"], g["degrees"]) or 0, 3) if g
                        else None,
                        "proportion": round(_proportion(m["h_plinth"], g["degrees"]) or 0, 2) if g
                        else None,
                        "figure": figure_picture(im),
                        "plinth": plinth_picture(im)})
        except Exception as exc:                                        # noqa: BLE001
            print("  could not draw %s: %s" % (path.name, exc))
    return out


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


def judge(raw, target, tol, height_tol=HEIGHT_TOLERANCE_PCT,
          base_tol=BASE_TOLERANCE_PCT):
    """Measure one dropped file and say what is inside tolerance and what is not."""
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
                    "wall_ratio": round(m["wall_ratio"], 3),
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
        if band and "base_ratio" in band and base is not None:
            b = band["base_ratio"]
            row["base_ratio"] = round(base, 3)
            off = 100.0 * (base - b["mid"]) / b["mid"] if b["mid"] else 0.0
            checks.append(["base height / width", "%+.1f%% of the set" % off,
                           "ok" if abs(off) <= base_tol
                           else ("check" if abs(off) <= base_tol * 2 else "bad"),
                           "wall/width %.3f at %.1f deg is %.3f upright, against a median of "
                           "%.3f, tolerance %.0f%%"
                           % (m["wall_ratio"], deg, base, b["mid"], base_tol)])

        prop = _proportion(m["h_plinth"], g["degrees"] if g else None)
        if band and "proportion" in band and prop is not None:
            b = band["proportion"]
            row["proportion"] = round(prop, 3)
            off = 100.0 * (prop - b["mid"]) / b["mid"] if b["mid"] else 0.0
            verdict = ("ok" if abs(off) <= height_tol
                       else ("check" if abs(off) <= height_tol * 2 else "bad"))
            checks.append(["height", "%+.1f%% of the set" % off, verdict,
                           "height/plinth %.2f at %.1f deg is proportion %.2f, against a median "
                           "of %.2f, tolerance %.0f%%"
                           % (m["h_plinth"], g["degrees"], prop, b["mid"], height_tol)])
            if prop > b["hi"]:
                shrink = 100.0 * (1.0 - b["hi"] / prop)
                checks.append(["cost to the set", "everything else %.1f%% smaller" % shrink,
                               "check" if shrink <= height_tol else "bad",
                               "the tray scales so the tallest levelled figure reaches the "
                               "target size, and this one would become the tallest"])
            else:
                checks.append(["cost to the set", "none", "ok",
                               "it is not taller than the tallest, so nothing else rescales"])
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
        size = str(place.get("tuned_at", 210))
        widest = max((f["w"] for f in art.get(size, [])), default=0)
        cap = 2 * place["spread"] + widest
        frame_w = (place.get("frame") or {}).get("w", 320)
        checks.append(["five sculpts fit", "need %d of %d px" % (cap, frame_w),
                       "info" if not widest else ("ok" if cap <= frame_w else "bad"),
                       "spread %d and the widest of the %d seats drawn (%d px), against the "
                       "frame" % (place["spread"], len(board.FIGURE_SEATS), widest)])

    return {"row": row, "checks": checks, "notes": notes, "overlay": overlay(im, g, kind)}


def serve(page, port, open_it):
    """Serve the page and measure what it posts. Bound to 127.0.0.1 and nothing else."""
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
            if self.path in ("/", "/index.html"):
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):                                              # noqa: N802
            if self.path != "/measure":
                return self._send(404, json.dumps({"error": "not found"}))
            try:
                n = int(self.headers.get("Content-Length") or 0)
                sent = json.loads(self.rfile.read(n).decode("utf-8"))
                raw = base64.b64decode(sent["data"].split(",", 1)[-1])
                target = float(sent.get("target", TARGET_DEGREES))
                tol = float(sent.get("tolerance", TOLERANCE_DEGREES))
                htol = float(sent.get("height_tolerance", HEIGHT_TOLERANCE_PCT))
                btol = float(sent.get("base_tolerance", BASE_TOLERANCE_PCT))
                result = judge(raw, target, tol, htol, btol)
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

    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    print("  serving %s -- drop PNGs on it" % url)
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
            .replace("__HTOL__", json.dumps(HEIGHT_TOLERANCE_PCT))
            .replace("__BTOL__", json.dumps(BASE_TOLERANCE_PCT))
            .replace("__BAND__", json.dumps(band))
            .replace("__ONRECORD__", json.dumps(on_record())))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print("wrote %s  (%.0f KB)" % (out, len(page) / 1024))
    if band and "degrees" in band:
        b = band["degrees"]
        print("  the set on record sits %.1f to %.1f degrees (median %.1f, %d figures)"
              % (b["lo"], b["hi"], b["mid"], b["n"]))
    if band and "h_plinth" in band:
        b = band["h_plinth"]
        print("  and %.2f to %.2f height/plinth (median %.2f), the tallest %+.1f%% of it"
              % (b["lo"], b["hi"], b["mid"],
                 100.0 * (b["hi"] - b["mid"]) / b["mid"] if b["mid"] else 0.0))
    print("  target %.0f deg, tolerance %.1f, height tolerance %.0f%%, base tolerance %.0f%%"
          % (TARGET_DEGREES, TOLERANCE_DEGREES, HEIGHT_TOLERANCE_PCT, BASE_TOLERANCE_PCT))
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
#record .one{background:#17130d;border:1px solid #241d13;padding:8px}
#record .one .nm{color:#c9b27a;padding-bottom:4px}
#record .one .num{color:#5f574a;padding-top:4px}
#record img{display:block}
#record .fig{height:250px}
</style>
<div id=head>Drop a sculpt or a ground plate. It is measured by
<b>tools/ui_debug/sculpt_metrics.py</b> &#8212; the same code that builds the pieces &#8212;
and drawn back with the measurement on it.</div>
<div id=bar>
  <label for=target>target angle</label><input id=target value=__TARGET__>
  <label for=tol>tolerance</label><input id=tol value=__TOL__>
  <label for=htol>height tol %</label><input id=htol value=__HTOL__>
  <label for=btol>base tol %</label><input id=btol value=__BTOL__>
  <span id=ref class=info></span>
</div>
<div id=record></div>
<div id=drop>drop PNGs here</div>
<div id=cards></div>
<script>
var BAND = __BAND__;
var ONRECORD = __ONRECORD__;
(function(){
  if (!ONRECORD || !ONRECORD.length) return;
  var host = document.getElementById("record");
  var h = ["<h2>The sculpts on file in <b>ui/assets-gothic/sculpts/</b>. Below each figure, the "
           + "two numbers check (b) compares: the base's own width, and the lit wall above it."
           + "<br>These are NOT the band a newcomer is judged against &#8212; that still comes "
           + "from <b>ui/concept/</b>, the 9&#176; art being replaced, which is why a correct new "
           + "sculpt reports a height gap. Recompute it once the four seats exist.</h2>"
           + "<div class=row>"];
  ONRECORD.forEach(function(r){
    h.push("<div class=one><div class=nm>" + r.name + "</div>");
    h.push("<img class=fig src='" + r.figure + "' alt=''>");
    if (r.plinth) h.push("<img src='" + r.plinth + "' alt=''>");
    h.push("<div class=num>" + (r.degrees == null ? "&#8212;" : r.degrees.toFixed(1) + " deg")
           + " &#183; base " + (r.base == null ? "&#8212;" : r.base.toFixed(3))
           + " &#183; height " + (r.proportion == null ? "&#8212;" : r.proportion.toFixed(2))
           + "</div></div>");
  });
  h.push("</div>");
  host.innerHTML = h.join("");
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
                            height_tolerance: +document.getElementById("htol").value,
                            base_tolerance: +document.getElementById("btol").value})})
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
</script>
"""


if __name__ == "__main__":
    main()
