"""How much room the duty wheel actually gets, with everything else at its true size.

    python3 tools/ui_debug/generate_wheel_space_check.py --open

A measuring instrument, not a view of the game. It draws the oval duty wheel where the game view
puts it, the four player boards beside it, and a plain box at the correct size for every other
component, then reports what each one measures in real device pixels on whatever screen the page
is opened on.

WHAT IS REAL HERE AND WHAT IS A BOX

The player boards are built the way gen_game_view builds them -- build_board() per seat, then
merge_defs() -- so they are the same artwork at the same 1905 x 826 aspect, sized from
geometry() rather than from anything chosen here. Special Activities is gen_game_view's own
special_placeholder(), which reports for itself whether the six-by-four cube table still fits the
panel it is given. The alms table, market, banner and action box are plain boxes: correct size,
no art.

THE SLIDER IS A REAL LEVER

It moves board_width, and geometry() is stamped for every width it can reach, so nothing here
re-implements the layout. Widen a board and the action box widens with it -- it is drawn as a
fraction of the board's width -- and the wheel gets what is left. The action-box button goes
further: turning it off drops the panel_w term out of wheel_room, which is the same formula
gen_game_view uses with one term removed rather than a number invented here.

The wheel is centred in its column and lifted so its own centre line -- which is the west face's
-- lands in the gap between the second and third player boards.

THE ASPECT IS NOT SETTLED

Two wheels are carried: duty_wheel_v2_layout.json at 1.778, and duty_wheel_v2_1500_layout.json
at 1.500. Both come out of build_duty_wheel_v2.py -- the second with
`--aspect 1.5 --out duty_wheel_v2_1500_layout.json` -- and a test rebuilds both and compares
bytes, so neither can drift from the constants that make it. Which aspect the game takes is a
separate question, and it does not pay for itself until the canvas moves with it.

THE FIGURES ARE RULERS, NOT DECORATION

One acolyte per size in FIGURE_SIZES sits in a tray in the top-right corner of the wheel's box,
where the ellipse leaves the corner empty at every aspect. The tray never moves. Pressing one
mints a copy under the cursor and hands it the drag, so taking a piece to a tile is one motion;
a copy is dropped by releasing, removed by double-clicking, and `c` clears the board. That is
what answers the two questions worth asking here -- how the wheel reads with several pieces on
it, and whether placing them by hand feels like anything.

Every figure, tray and copy alike, is held at its own count of REAL DEVICE pixels whatever the
stage scale or the slider says, which is the same unit every other number on this page is quoted
in -- so dragging them across the wheel answers "is 60 enough, is 90 too much" directly, without
arithmetic. Size in stage units is therefore recomputed on every paint; a figure sized in stage
units would be a different number of real pixels at every canvas and would measure nothing.

The art is read from generated/figure_<px>.png (or --figures DIR), and each file must already BE
that many pixels tall. A file of the wrong height is left out with a note rather than drawn,
because the browser would then show its resample of the art and not what a piece of that size
actually looks like -- which is the one question this page exists to answer. Upscaling a 60 px
file to 90 is the same mistake: render each size down from the full-resolution original.

Those files are NOT committed: they are git-ignored debug input like everything else in
generated/, and the page simply leaves a figure out when its file is missing rather than failing.

The page it writes goes to generated/, which this folder already treats as local debug output:
git-ignored, rebuilt on demand, never committed. It is ~9 MB and carries the portrait art, which
is the other reason it is not committed.
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
sys.path.insert(0, str(ROOT / "ui" / "render"))
import gen_game_view as gv                                          # noqa: E402

# Into generated/, which this folder already treats as local debug output: git-ignored,
# rebuilt on demand, never committed. NOT into ~/Downloads -- a python.org interpreter has no
# macOS TCC grant for that folder and write_text() fails with "Operation not permitted".
OUT = HERE / "generated" / "wheel_space_check.html"
WIDTHS = list(range(200, 505, 5))
CANVASES = (1600, 2039, 2283)
SHIP = 0.06315                                  # one shipped tile / the square wheel box

# THE TILE COLOUR IS A MEASURED CHOICE, not a preference. Against the cream the pale sculpt is a
# dark mark (Weber contrast 0.49); against this slate it reads as a lit object (1.53), which is
# how a miniature reads on a table. The cost is real and worth knowing: ~11% of the silhouette
# goes, all of it on the figure's shadowed side, where its own dark edges come within 25
# luminance of the ground. The frame is the CHANNEL between faces -- the stage ground #17130d
# showing through -- and that now sits 28 luminance from the tile where the cream sat 209, so
# the spokes read softer. That is the price of the flip, not a bug in the drawing.
WHEEL_FACE = "#2b2f38"
WHEEL_CENTRE = "#23272f"

# The figures are quoted in REAL DEVICE pixels, the same unit as every other number here.
FIGURE_SIZES = (60, 90)
FIGURE_DIR = HERE / "generated"

# The boards, exactly as gen_game_view builds them. Sizes are stripped off the roots because
# the page sets them per slider stop; merge_defs gives the one shared <defs> they all point into.
import xml.etree.ElementTree as ET                                  # noqa: E402

ASSETS = ROOT / "ui" / "assets-gothic"
asm = gv.load_assembler(ROOT / "ui" / "render" / "gen_board_gothic.py")
seats = list(asm.SEAT_COLORS)[:int(gv.DEFAULTS["seats"])]
roots = [gv.build_board(asm, ASSETS, ASSETS / "production_test_config.json",
                        s, "lit" if s == seats[0] else "dim") for s in seats]
defs, _unique, _saved = gv.merge_defs(asm, roots)
DEFS = ET.tostring(defs, encoding="unicode")
boards = []
for root in roots:
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    boards.append(ET.tostring(root, encoding="unicode"))
assert len(boards) == 4, "expected four boards, found %d" % len(boards)

L, SA = {}, {}
for cw in CANVASES:
    for bw in WIDTHS:
        D = dict(gv.DEFAULTS)
        D["canvas_width"], D["board_width"] = cw, float(bw)
        G = gv.geometry(D)
        L["%d|%d" % (cw, bw)] = {
            "cw": cw, "ch": D["canvas_height"], "pad": G["pad"], "mt": D["margin_top"],
            "inner_w": G["inner_w"], "top_h": G["top_h"], "main_h": G["main_h"],
            "banner_h": G["banner_h"], "act_h": G["act_h"], "bw": G["bw"], "bh": G["bh"],
            "panel_w": G["panel_w"], "overhang": G["overhang"],
            "gap1": D["column_gap_1"], "gap2": D["column_gap_2"],
            "board_gap": D["board_gap"], "left_top": G["left_top"], "left_h": G["left_h"],
            "left_lift": G["left_lift"], "wheel_room": G["wheel_room"],
            "square_wheel": G["wheel"],
        }
        if bw not in SA:
            # THE REAL PLACEHOLDER, not a grey box of my own: gen_game_view draws this one and
            # it goes red when the six-by-four cube table stops fitting the panel it is given.
            # special_placeholder returns (markup, spec); the second is its own verdict text
            SA[bw] = gv.special_placeholder(
                G["panel_w"], G["top_h"], D["frame_border_y"], D["frame_border_x"])[0]

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
    """Area centroid, not the bounding-box centre. The faces are curved wedges and their bbox
    centre can sit outside the face entirely."""
    a2 = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        cr = x1 * y2 - x2 * y1
        a2 += cr
        cx += (x1 + x2) * cr
        cy += (y1 + y2) * cr
    assert abs(a2) > 1e-9, "degenerate face polygon"
    return cx / (3 * a2), cy / (3 * a2)


WH = {}
for a, name in ((1.5, "duty_wheel_v2_1500_layout.json"),
                (1.778, "duty_wheel_v2_layout.json")):
    d = json.loads((HERE / name).read_text(encoding="utf-8"))
    faces = []
    for c in d["cells"]:
        poly = _polygon(c)
        cx, cy = _centroid(poly)
        faces.append({
            "d": c["d"], "pos": c["position"],
            "frac": c["area"] / (d["box"] * d["box_h"]),
            # as fractions of the box, so the figure keeps its face at every slider stop
            "cx": cx / d["box"], "cy": cy / d["box_h"],
            "poly": [[round(x, 1), round(y, 1)] for x, y in poly],
        })
    WH[str(a)] = {"box": d["box"], "box_h": d["box_h"],
                  "palette": {"face": WHEEL_FACE, "centre": WHEEL_CENTRE},
                  "faces": faces}

# The figures, inlined so the page stays a single file. A missing one is not fatal -- the page
# just draws without it -- because this art is git-ignored debug input and a fresh clone has none.
fig_dir = pathlib.Path(args.figures).expanduser() if args.figures else FIGURE_DIR
FIGURES, fig_notes = [], []
for px in FIGURE_SIZES:
    p = fig_dir / ("figure_%d.png" % px)
    if not p.is_file():
        fig_notes.append("%3d px  missing %s, left out" % (px, p.name))
        continue
    raw = p.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % p
    w, h = struct.unpack(">II", raw[16:24])         # IHDR, straight off the header, no Pillow
    if h != px:
        # Drawing it anyway would put the BROWSER's resample on screen under a label saying it is
        # a px-tall piece, which is the one thing this page must not do.
        fig_notes.append("%3d px  %s is %d px tall, LEFT OUT -- render it down from the original "
                         "rather than scaling another size" % (px, p.name, h))
        continue
    FIGURES.append({"px": px, "ar": w / h,
                    "uri": "data:image/png;base64," + base64.b64encode(raw).decode("ascii")})
    fig_notes.append("%3d px  %s  %d × %d, draggable" % (px, p.name, w, h))

page = ((HERE / "wheel_space_check.html.tmpl").read_text(encoding="utf-8")
        .replace("__DEFS__", DEFS)
        .replace("__LAYOUTS__", json.dumps(L))
        .replace("__WHEELS__", json.dumps(WH))
        .replace("__BOARDS__", json.dumps(boards))
        .replace("__SA__", json.dumps({str(k): v for k, v in SA.items()}))
        .replace("__WIDTHS__", json.dumps(WIDTHS))
        .replace("__SHIP__", repr(SHIP))
        .replace("__FIGURES__", json.dumps(FIGURES)))
left = re.findall(r"__[A-Z_]+__", page)
assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

OUT = pathlib.Path(args.out).expanduser() if args.out else OUT
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")
print("wrote %s  (%.0f KB)" % (OUT, len(page) / 1024))
print("  %d layouts, %d SA placeholders, %d boards, defs %.1f MB"
      % (len(L), len(SA), len(boards), len(DEFS) / 1e6))
print("  wheel faces %s, hub %s" % (WHEEL_FACE, WHEEL_CENTRE))
for note in fig_notes:
    print("  %s" % note)
if args.open:
    webbrowser.open(OUT.resolve().as_uri())
