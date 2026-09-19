"""The duty wheel alone, at a size you set, with pieces you can put on it.

    python3 tools/ui_debug/generate_wheel_space_check_v2.py --open

WHAT THIS IS NOT

It is not a replacement for generate_wheel_space_check.py. That page answers "how much room does
the wheel GET" -- it draws the boards and every other component at its true size and leaves the
wheel whatever is left, so the wheel's size is an OUTPUT of gen_game_view's geometry and cannot
be typed in. This page answers the opposite question, "how big does the wheel NEED to be", and to
ask that it has to let you set the size directly. Neither number is the other's answer. When you
have picked a size here, v1 is where you find out whether the layout can afford it.

NO STAGE, SO NO ARITHMETIC

v1 draws into a canvas scaled by k and reports real pixels as units * k * dpr. There is no canvas
here and no transform, so a CSS pixel is exactly dpr device pixels and every number on the page
is a real device pixel with nothing to divide out. That is the whole reason this is a separate
page rather than a mode of the other one: the moment a stage scale comes back, so does the
arithmetic, and with it the chance of quoting a size that is not the size on the glass.

THE HEIGHT SLIDER REALLY STRETCHES

The two layouts are BUILT at their aspects by build_duty_wheel_v2.py -- the hub is held as a
ratio of the rim, the spokes are recomputed -- they are not one wheel scaled to two shapes. So
setting a width and height whose ratio is not the layout's own does not show you that layout at a
different size: it shows you the drawing stretched, and the faces are no longer the shape the
builder would produce. The page says so in the readout whenever it happens, and the wheel button
snaps the height back to the built ratio. Read a stretched wheel as a sketch of where the size
might go, then rebuild at that aspect if you want to trust it.

THE CANVAS LINES ARE NOT THE WHEEL'S COLUMN

Vertical rules mark where each of v1's three canvases ends, by v1's own rule: the canvas is a box
of units that is scaled to FIT the window, k = min(vw/cw, vh/ch), so how many real pixels a
canvas is worth depends on the display it is opened on. That is why the lines move when you
resize the window while the wheel does not -- the wheel here is an absolute number of device
pixels and the canvas is not. A canvas whose k is width-bound fills the window and its rules land
on the window edges, which is itself the answer to "is this canvas even the limit here".

Those rules are the OUTER edge of the canvas. The wheel never gets all of it: in the real layout
the boards, the alms column and the action box come out first and the wheel takes what is left.
A wheel that fits between these lines has not been shown to fit the game view -- v1 is what
answers that. These lines only say when it certainly does NOT.

THE FIGURES

The tray in the top-right corner holds one unmovable figure per size in FIGURE_SIZES. Pressing
one mints a copy under the cursor and hands it the drag, so taking a piece to a tile is one
motion; release to drop, double-click to remove, `c` clears the board. Copies hold their position
as a FRACTION of the wheel box, so they keep their tile while you work the sliders -- which is
the point, since the question is whether a piece still fits once the wheel shrinks.

Art comes from generated/figure_<px>.png (or --figures DIR) and each file must already BE that
many pixels tall; one of the wrong height is left out with a note rather than drawn, because the
browser would then show its resample under a label claiming a true size. Those files are
git-ignored debug input, and a missing one costs that figure, not the page.

Output goes to generated/, which this folder treats as local debug output: git-ignored, rebuilt
on demand, never committed.
"""
import argparse
import base64
import json
import pathlib
import re
import struct
import sys
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "wheel_space_check_v2.html"

# Only for the canvas sizes. Importing the module is cheap -- it is load_assembler() and
# build_board() that cost 8.8 MB, and this page calls neither.
sys.path.insert(0, str(ROOT / "ui" / "render"))
import gen_game_view as gv                                          # noqa: E402

GROUND = "#17130d"

# THE TILE COLOUR IS NOW A QUESTION, NOT A SETTING, so the page carries all three and `t` cycles.
#
# The slate was picked against one pale test sculpt, where it is plainly right. Measured against
# the seat-coloured plastic sculpts the tray actually carries, it is not so clear -- these are
# painted in the seat inks, and the darker two sit close to the slate's own luminance of 47:
#
#     piece      Weber on slate   outline lost      Weber on cream   outline lost
#     player 1       1.27              8%               0.53             4%
#     player 2       0.65             29%               0.66             0%
#     player 3       0.54             33%               0.68             0%
#
# A third of player 3's silhouette dissolves into the slate where none of it does on the cream.
# It is viable either way -- this is much better than the painted figures managed, which lost
# half to two thirds -- but it is a judgement about the real cast rather than about one test
# piece, so the page stopped asserting an answer and hands you the switch.
PALETTES = (("slate", "#2b2f38", "#23272f"),
            ("cream", "#efe3c8", "#e8dcc0"),
            ("parchment", "#ddc9a0", "#d5c097"))

# Rows of the tray, top to bottom, each at every size in FIGURE_SIZES. The art is read from
# generated/figure_<subject>_<px>.png; make_tray_figures.py renders every one of them DOWN from
# its full-resolution original, plinth-levelled across the players so their bases match.
FIGURE_SUBJECTS = (("player_1", "p1"),
                   ("player_2", "p2"),
                   ("player_3", "p3"),
                   ("player_4", "p4"))
FIGURE_SIZES = (90, 120, 150)
FIGURE_DIR = HERE / "generated"

# Both wheels build_duty_wheel_v2.py writes. The label is the built aspect and doubles as the key.
LAYOUTS = (("1.500", "duty_wheel_v2_1500_layout.json"),
           ("1.778", "duty_wheel_v2_layout.json"))

# Slider bounds, in REAL DEVICE pixels. The start is the 1.5 wheel as it actually measures on a
# MacBook at canvas 1600 -- the size every earlier measurement in this folder was taken at, so
# the page opens where the numbers already are rather than somewhere invented.
W_RANGE = (600, 2600)
H_RANGE = (300, 1800)
START_W, START_H = 1204, 803

# Percent, applied to the current width AND height together so the shape is preserved exactly.
S_RANGE = (25, 300)

# The same three canvases v1 puts on keys 1, 2 and 3. The height is not assumed: it is read back
# out of the dict AFTER geometry() has seen it, which is the route v1 takes, so if the height ever
# starts being derived from the width this page follows without being edited.
CANVAS_WIDTHS = (1600, 2039, 2283)
CANVASES = []
for _cw in CANVAS_WIDTHS:
    _D = dict(gv.DEFAULTS)
    _D["canvas_width"] = _cw
    gv.geometry(_D)
    CANVASES.append({"w": _cw, "h": _D["canvas_height"]})
    assert CANVASES[-1]["h"] > 0, "canvas %d came back with no height" % _cw

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("--out", default=None, help="where to write the page (default: beside this file)")
ap.add_argument("--figures", default=None,
                help="folder holding figure_<px>.png for %s (default: %s)"
                     % (" and ".join(str(s) for s in FIGURE_SIZES), FIGURE_DIR.relative_to(ROOT)))
ap.add_argument("--open", action="store_true", help="open the page when it is written")
args = ap.parse_args()

_NUM = re.compile(r"-?\d+\.?\d*")


def _polygon(cell):
    """The face as a flat list of points. `d` is the drawn outline with curves in it; `d_poly` is
    the same face already flattened by build_duty_wheel_v2, which is what a point-in-polygon test
    needs. Taking the numbers out of `d` instead would read the curve CONTROL points as vertices
    and quietly give a face a different shape than the one on screen."""
    v = [float(t) for t in _NUM.findall(cell["d_poly"])]
    assert len(v) >= 6 and len(v) % 2 == 0, "face %s has %d coordinates" % (cell["position"], len(v))
    return list(zip(v[0::2], v[1::2]))


def _centroid(poly):
    """Area centroid, not the bounding-box centre: the faces are curved wedges and their bbox
    centre can sit outside the face entirely."""
    a2 = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        cr = x1 * y2 - x2 * y1
        a2 += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    assert abs(a2) > 1e-9, "degenerate face polygon"
    return cx / (3 * a2), cy / (3 * a2)


WH, KEYS = {}, []
for label, name in LAYOUTS:
    p = HERE / name
    if not p.is_file():
        raise SystemExit(
            "%s is missing. Run `python3 tools/ui_debug/build_duty_wheel_v2.py` (the 1.5 one with "
            "`--aspect 1.5 --out duty_wheel_v2_1500_layout.json`); it carries the nine outlines "
            "and there is no wheel without them." % p)
    d = json.loads(p.read_text(encoding="utf-8"))
    faces = []
    for c in d["cells"]:
        poly = _polygon(c)
        cx, cy = _centroid(poly)
        faces.append({
            "d": c["d"], "pos": c["position"],
            "frac": c["area"] / (d["box"] * d["box_h"]),
            # fractions of the box, so a piece keeps its face at every slider position
            "cx": cx / d["box"], "cy": cy / d["box_h"],
            "poly": [[round(x, 1), round(y, 1)] for x, y in poly],
        })
    WH[label] = {"box": d["box"], "box_h": d["box_h"], "aspect": d["box"] / d["box_h"],
                 "faces": faces}
    KEYS.append(label)
    # The label IS the built aspect; if the file ever stops agreeing, the button would be lying.
    assert abs(WH[label]["aspect"] - float(label)) < 5e-3, \
        "%s is built at aspect %.4f but is labelled %s" % (name, WH[label]["aspect"], label)

# The figures, inlined so the page stays a single file. A missing one costs that piece, not the
# page, because this art is git-ignored debug input and a fresh clone has none of it.
fig_dir = pathlib.Path(args.figures).expanduser() if args.figures else FIGURE_DIR
ROWS, fig_notes = [], []
for subject, tag in FIGURE_SUBJECTS:
    items = []
    for px in FIGURE_SIZES:
        p = fig_dir / ("figure_%s_%d.png" % (subject, px))
        if not p.is_file():
            fig_notes.append("%-9s %3d px  missing %s, left out" % (tag, px, p.name))
            continue
        raw = p.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % p
        w, h = struct.unpack(">II", raw[16:24])     # IHDR, straight off the header, no Pillow
        # The nominal size is the ceiling of a set, not a promise each file is that tall: the
        # players are levelled on the plinth first and only the tallest lands on the nominal, so
        # `h` is what gets drawn and `nom` is only what it is filed under. A file TALLER than its
        # nominal is a different matter -- that one is a mistake, and gets left out.
        if h > px:
            fig_notes.append("%-9s %3d px  %s is %d px tall, LEFT OUT -- taller than its own "
                             "nominal, render it down from the original" % (tag, px, p.name, h))
            continue
        items.append({"nom": px, "w": w, "h": h,
                      "uri": "data:image/png;base64," + base64.b64encode(raw).decode("ascii")})
        fig_notes.append("%-9s %3d px  %s  %d × %d%s"
                         % (tag, px, p.name, w, h,
                            "" if h == px else "  (%d%% of nominal)" % round(100 * h / px)))
    if items:
        ROWS.append({"tag": tag, "items": items})
assert ROWS or fig_notes, "no figures and no notes -- FIGURE_SUBJECTS is empty"

page = ((HERE / "wheel_space_check_v2.html.tmpl").read_text(encoding="utf-8")
        .replace("__GROUND__", GROUND)
        .replace("__WHEELS__", json.dumps(WH))
        .replace("__KEYS__", json.dumps(KEYS))
        .replace("__ROWS__", json.dumps(ROWS))
        .replace("__PALETTES__", json.dumps([{"name": n, "face": f, "centre": c}
                                             for n, f, c in PALETTES]))
        .replace("__WRANGE__", json.dumps(list(W_RANGE)))
        .replace("__HRANGE__", json.dumps(list(H_RANGE)))
        .replace("__SRANGE__", json.dumps(list(S_RANGE)))
        .replace("__CANVASES__", json.dumps(CANVASES))
        .replace("__START__", json.dumps([START_W, START_H])))
left = re.findall(r"__[A-Z_]+__", page)
assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")
print("wrote %s  (%.0f KB)" % (OUT, len(page) / 1024))
print("  wheels %s  ·  tiles %s (t cycles, opens on %s)"
      % (", ".join(KEYS), ", ".join(p[0] for p in PALETTES), PALETTES[0][0]))
print("  opens at %d × %d real px, sliders %d-%d by %d-%d, scale %d-%d%%"
      % (START_W, START_H, W_RANGE[0], W_RANGE[1], H_RANGE[0], H_RANGE[1], S_RANGE[0], S_RANGE[1]))
print("  canvases %s" % ", ".join("%d × %d" % (c["w"], c["h"]) for c in CANVASES))
for note in fig_notes:
    print("  %s" % note)
if args.open:
    webbrowser.open(OUT.resolve().as_uri())
