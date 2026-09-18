"""The duty wheel at both aspects, on both screens that were actually measured.

    python3 tools/ui_debug/generate_wheel_aspect_compare.py --open

One question: if the wheel goes 1.500 instead of 1.778, what changes on a real screen. The page
draws the four cases -- two aspects by two screens -- and labels each with the size it comes out
at in REAL DEVICE PIXELS, which is the only unit the artwork has to meet.

NOTHING HERE IS A NUMBER I CHOSE

The wheel outlines are the committed layouts. The room the wheel gets comes from
gen_game_view.geometry(), not from a measurement of the drawing. The screens are
gen_screen_budget.REFERENCE, filtered to the two marked `measured` -- read off the machines on
2026-09-17 rather than estimated. Change any of those and re-run; this script has no geometry of
its own.

THE PANELS ARE DRAWN TO SCALE ACROSS THE WHOLE PAGE

A panel's width on the page is its real-pixel width as a fraction of the largest of the four, so
the picture carries the finding instead of leaving it to the caption. That finding is the
counter-intuitive one gen_screen_budget records in prose: the 34-inch ultrawide shows a wheel
much wider in centimetres and resolves it with a fifth FEWER pixels than the 14-inch laptop,
because it reports a pixel ratio of one. The laptop sets the resolution the art has to meet.

The canvas is fixed at 1600, which is what the game ships today. The aspect question only pays
off at a wider canvas, and `gen_screen_budget` is the page for that trade; this one holds the
canvas still so the aspect is the only thing moving.

The output lands in generated/, which this folder treats as local debug output: git-ignored,
rebuilt on demand, never committed.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "ui" / "render"))

import gen_game_view as gv                                             # noqa: E402
import gen_screen_budget as gsb                                        # noqa: E402

OUT = HERE / "generated" / "wheel_aspect_compare.html"

CANVAS = 1600                       # what the game ships today; see the docstring
SHIP = 0.06315                      # one shipped duty tile / the square wheel box
# The four faces that are distinct. north_east mirrors north_west and east mirrors west, so the
# bottom row and east carry no area a label here does not already give.
FACES = ("north_west", "north", "north_east", "west")
LAYOUTS = ((1.778, "duty_wheel_v2_layout.json"), (1.500, "duty_wheel_v2_1500_layout.json"))

LABEL_H = 0.034                     # label type as a fraction of the box height, so it scales


def centroid(d_poly: str) -> tuple[float, float]:
    """The polygon centroid of one face, for standing a label in the middle of it.

    Off `d_poly` and not off `d`: the Beziers bulge outward from their control polygon, so a
    centroid taken from the curve would sit a hair further out. These faces are convex enough
    that the polygon centroid lands well inside the ink either way, which the rendered page is
    the check on -- a number half outside its own tile is visible immediately.
    """
    n = [float(t) for t in d_poly.replace("M", " ").replace("L", " ").replace("Z", " ").split()]
    xs, ys = n[0::2], n[1::2]
    a = cx = cy = 0.0
    for i in range(len(xs)):
        j = (i + 1) % len(xs)
        cross = xs[i] * ys[j] - xs[j] * ys[i]
        a += cross
        cx += (xs[i] + xs[j]) * cross
        cy += (ys[i] + ys[j]) * cross
    a *= 0.5
    return cx / (6.0 * a), cy / (6.0 * a)


def inside(d_poly: str, x: float, y: float) -> bool:
    """Ray cast: is this point within the face it is meant to label."""
    n = [float(t) for t in d_poly.replace("M", " ").replace("L", " ").replace("Z", " ").split()]
    xs, ys = n[0::2], n[1::2]
    hit = False
    for i in range(len(xs)):
        j = (i - 1) % len(xs)
        if (ys[i] > y) != (ys[j] > y) and \
                x < (xs[j] - xs[i]) * (y - ys[i]) / (ys[j] - ys[i]) + xs[i]:
            hit = not hit
    return hit


def wheel(path: pathlib.Path) -> dict:
    """A committed layout: the face paths, each face's share of the box, and where to label it."""
    d = json.loads(path.read_text(encoding="utf-8"))
    return {
        "box": (d["box"], d["box_h"]),
        "paths": "".join(
            '<path fill="%s" d="%s"/>' % ("#e2d7bb" if c["position"] == "centre" else "#efe3c8",
                                          c["d"])
            for c in d["cells"]),
        "frac": {c["position"]: c["area"] / (d["box"] * d["box_h"]) for c in d["cells"]},
        "at": {c["position"]: centroid(c["d_poly"]) for c in d["cells"]},
        "poly": {c["position"]: c["d_poly"] for c in d["cells"]},
    }


def cases() -> list[dict]:
    """Every (screen, aspect) pair, measured rather than described."""
    conf = dict(gv.DEFAULTS)
    conf["canvas_width"] = CANVAS
    geo = gv.geometry(conf)
    ch = conf["canvas_height"]
    room_h = geo["main_h"] - geo["banner_h"]

    out = []
    for screen in (s for s in gsb.REFERENCE if s.get("measured")):
        dpr = screen.get("dpr", 1.0)
        k = min(screen["vw"] / CANVAS, screen["vh"] / ch)
        # the square wheel at this scale is what one shipped tile is quoted against
        ship_px = SHIP * (geo["wheel"] * k * dpr) ** 2
        for aspect, name in LAYOUTS:
            w = wheel(HERE / name)
            ww = min(geo["wheel_room"], room_h * aspect)
            px_w, px_h = ww * k * dpr, (ww / aspect) * k * dpr
            box_w, box_h = w["box"]

            # The labels live INSIDE the svg, in box units, so they scale with the panel exactly
            # as the faces do -- which is the point, since the panels are drawn in proportion to
            # each other. A label in CSS pixels would stay the same size and break that.
            big, small = LABEL_H * box_h, LABEL_H * box_h * 0.82
            marks = ""
            for face in FACES:
                area = w["frac"][face] * px_w * px_h
                x, y = w["at"][face]
                # The centroid is where the BLOCK should sit, not where the first baseline should.
                # Two lines hung off the centroid read low in the face; lift by the difference.
                y -= 0.18 * big
                # A label outside its own face is a wrong picture, not an ugly one, and these
                # outlines change whenever a constant in build_duty_wheel_v2.py moves. Fail here
                # rather than ship a page that quietly misattributes an area.
                assert inside(w["poly"][face], x, y), (
                    "the %s label at aspect %.3f falls outside the %s face" % (face, aspect, face))
                marks += (
                    '<text x="%.1f" y="%.1f" font-size="%.1f" fill="#4a4034" '
                    'text-anchor="middle" font-family="ui-monospace,Menlo,monospace">'
                    '<tspan x="%.1f" dy="0">%s px&#178;</tspan>'
                    '<tspan x="%.1f" dy="%.1f" font-size="%.1f" fill="#7d7160">%.2f&#215; tile'
                    "</tspan></text>"
                ) % (x, y, big, x, "{:,}".format(round(area)), x, big * 1.05, small,
                     area / ship_px)

            out.append({
                "screen": screen["name"], "vw": screen["vw"], "vh": screen["vh"], "dpr": dpr,
                "scale": k, "bound": "height" if screen["vh"] / ch <= screen["vw"] / CANVAS
                                      else "width",
                "aspect": aspect,
                "svg": '<svg viewBox="0 0 %g %g" preserveAspectRatio="xMidYMid meet">%s%s</svg>'
                       % (box_w, box_h, w["paths"], marks),
                "w": round(px_w), "h": round(px_h),
                # width-bound means the aspect buys height and costs nothing sideways
                "wide": ww >= geo["wheel_room"] - 0.05,
                "faces": [{"name": f, "side": round((w["frac"][f] * px_w * px_h) ** 0.5),
                           "ship": w["frac"][f] * px_w * px_h / ship_px} for f in FACES],
            })
    return out


CASES = cases()
BIG = max(c["w"] for c in CASES)

SCREENS = list(dict.fromkeys(c["screen"] for c in CASES))

# One grid, screens across and aspects down, so a row is the SAME aspect on both machines and the
# eye can compare sideways. Two stacked columns would let the rows drift apart, which loses the
# only comparison this page is for.
GRID = ""
for name in SCREENS:
    head = next(c for c in CASES if c["screen"] == name)
    GRID += ('<div class="head"><h2>{name}</h2><p class="meta">{vw} &#215; {vh} css &#183; '
             "{dpr}&#215; pixel ratio &#183; stage {k}%, bound by {bound}</p></div>").format(
        name=name, vw=head["vw"], vh=head["vh"], dpr="%.2f" % head["dpr"],
        k="%.1f" % (head["scale"] * 100), bound=head["bound"])

for aspect, _ in LAYOUTS:
    for name in SCREENS:
        c = next(x for x in CASES
                 if x["screen"] == name and abs(x["aspect"] - aspect) < 1e-9)
        GRID += (
            '<figure class="panel" style="--w:{pct}%;--a:{aspect}">'
            '<figcaption><b>aspect {aspect_t}</b><span>{w} &#215; {h} real px</span>'
            '<span class="who">{name}</span></figcaption>'
            '<div class="art">{svg}</div>'
            "</figure>"
        ).format(pct=round(100.0 * c["w"] / BIG, 2), aspect=c["aspect"],
                 aspect_t="%.3f" % c["aspect"], w=c["w"], h=c["h"], svg=c["svg"],
                 name=name)

PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Duty wheel: 1.778 against 1.500</title>
<style>
 :root{color-scheme:dark}
 html,body{margin:0;background:#0b0907;color:#8b8071;
   font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
 .wrap{max-width:1500px;margin:0 auto;padding:28px 20px 56px}
 h1{font-size:15px;font-weight:600;color:#e8c97a;margin:0 0 4px;letter-spacing:.02em}
 .lede{margin:0 0 26px;max-width:78ch;color:#7b7160}
 .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:30px 26px;
   align-items:start}
 .who{display:none}
 @media (max-width:900px){
   .grid{grid-template-columns:minmax(0,1fr)}
   /* stacked, the column headings no longer sit over their own panels, so each panel says
      which machine it is for and the headings go away */
   .head{display:none}
   .who{display:inline;color:#cbbb98;font-size:12px}
 }
 .head{min-width:0;padding-bottom:10px;border-bottom:1px solid #221d16}
 h2{font-size:13px;font-weight:600;color:#cbbb98;margin:0 0 2px}
 .meta{margin:0;font-size:12px;color:#6f6556}
 .panel{margin:0;min-width:0}
 figcaption{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin:0 0 7px}
 figcaption b{color:#e8c97a;font-weight:600}
 figcaption span{font-size:12px;color:#6f6556}
 .art{width:var(--w);max-width:100%;aspect-ratio:var(--a);background:#17130d;
   border-radius:3px;overflow:hidden}
 .art svg{display:block;width:100%;height:100%}
 footer{margin-top:30px;padding-top:16px;border-top:1px solid #221d16;font-size:12px;
   color:#5f5749;max-width:86ch}
 footer b{color:#8b8071;font-weight:400}
</style>
<div class="wrap">
<h1>The duty wheel at 1.778 and at 1.500, on the two screens that were measured</h1>
<p class="lede">Canvas __CANVAS__. Each panel is drawn at its real-pixel width relative to the
largest of the four, so the sizes on this page are in proportion to the sizes on those machines.
Each face carries its own area in real device pixels, and that area as a multiple of one duty
tile as the game ships it today. Only the four distinct faces are marked: the bottom row mirrors
the top and east mirrors west, so they repeat these areas exactly.</p>
<div class="grid">__GRID__</div>
<footer>__NOTE__</footer>
</div>
</html>
"""

wide = [c for c in CASES if c["wide"]]
note = ("Every case here is <b>width-bound</b>: the wheel already has all the width the layout "
        "can give it, so going from 1.778 to 1.500 costs nothing sideways and only claims height "
        "that was idle. That is why the 1.500 faces come out larger on both screens."
        if len(wide) == len(CASES) else
        "Some of these cases are height-bound, so the aspect is trading width against height "
        "rather than taking height for free. Check the panel widths before reading the face "
        "figures as a gain.")
mac = next(c for c in CASES if "MacBook" in c["screen"])
uw = next(c for c in CASES if c["screen"] != mac["screen"])
note += (" The comparison across columns is the one worth keeping: the %s draws the wheel into "
         "<b>%d</b> real pixels and the %s into <b>%d</b>, so the bigger monitor shows a larger "
         "wheel and resolves it with fewer pixels. The laptop sets the resolution the artwork "
         "has to meet." % (mac["screen"], mac["w"], uw["screen"], uw["w"]))
note += (" The face multiples are the same in both columns on purpose: a face and the tile it is quoted against both scale with the stage, so that ratio is a property of the ASPECT and not of the screen. The pixel counts are where the screens differ.")

page = (PAGE.replace("__CANVAS__", "%d &#215; %d" % (CANVAS, gv.DEFAULTS["canvas_height"]))
            .replace("__GRID__", GRID)
            .replace("__NOTE__", note))

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--out", default=None, help="where to write the page (default: beside this file)")
ap.add_argument("--open", action="store_true", help="open the page when it is written")
args = ap.parse_args()

OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")
print("wrote %s  (%.0f KB)" % (OUT, len(page) / 1024))
for c in CASES:
    print("  %-22s aspect %.3f   %4d x %4d real px   %s" %
          (c["screen"], c["aspect"], c["w"], c["h"],
           " ".join("%s %.2fx" % (f["name"], f["ship"]) for f in c["faces"])))
if args.open:
    webbrowser.open(OUT.resolve().as_uri())
