"""The TRACED duty tiles, at a size you set, with banners and pieces you can put on them.

v3 IS v2 ON THE OTHER WHEEL

Same page, same true-size discipline, same trays -- drawn on the nine traced tiles from
`ui/assets-gothic/metadata/duty_grid_shapes.json` instead of the built 1.500 rosette, and with
two things the rosette could not carry.

WHY A SECOND PAGE RATHER THAN A MODE

The rosette pinches at the top: measured across its nine faces, the width available where a
title sits runs 186 to 346 units, so a banner has to shrink to about 116 to clear the
narrowest and the nine cannot be the same size as each other. The traced tiles hold their
width to the top -- 273 to 295, an 8% spread -- and take a 240-unit banner on all nine. That
is a different question about a different shape, not a setting on the same one.

THE BANNERS

Four buttons -- none, small, medium, large -- put a blank parchment on every tile with its duty
name set live from gen_duty_grid.DUTY_NAMES. `none` is the default, so with it selected this page
is simply v2 on the traced tiles. Drag a banner to move it, double-click to put it back on its
tile, and the turn slider fans them about the middle column. The art is embedded and downscaled
because it draws at a couple of hundred pixels from a 2172 px source; the TITLES ARE NOT IN THE
ART, so renaming a duty needs no new asset.

TILE SIZE AND SPACING ARE SLIDERS HERE

The rosette is a built tessellation and its faces cannot move without being rebuilt. These are
nine independent contours, so how big each tile is and how far apart they sit are free, and
both are questions the banner makes you ask: a banner wants a wide tile, and a wide tile wants
the gaps closed. Everything laid on a tile -- banner, duty picture -- follows it through both.

    python3 tools/ui_debug/generate_wheel_space_check_v3.py --open

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

These contours were TRACED off a square picture, so square is the shape they were drawn in rather
than a ratio a builder was asked for. Setting a width and height whose ratio is not 1:1 does not
show you the tiles some other aspect would have produced -- there is no such build -- it simply
distorts these. The page says so in the readout whenever it happens, and `m` squares it up.
Read a stretched wheel as a sketch of where the size might go, not as a shape anything can make.

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
motion; release to drop, double-click to remove, `c` clears the board and `u` brings a clear
back. Copies hold their position as a FRACTION of the wheel box, so they keep their tile while
you work the sliders -- which is the point, since the question is whether a piece still fits once
the wheel shrinks.

They stack by their FOOT rather than by who was dropped last, because sculpts put down in a
zig-zag overlap and creation order will happily draw a piece at the back over one in front. The
placed pieces also carry a drop-shadow, which `s` removes: three figures of one colour overlapping
read as a single silhouette without it. The TRAY carries none -- it is the true-size reference the
placed pieces are compared against, and a reference should not be dressed.

Art comes from generated/figure_<px>.png (or --figures DIR) and each file must already BE that
many pixels tall; one of the wrong height is left out with a note rather than drawn, because the
browser would then show its resample under a label claiming a true size. Those files are
git-ignored debug input, and a missing one costs that figure, not the page.

THE DUTY PICTURES, AND THE ONE THING THIS PAGE GIVES UP FOR THEM

`i` turns on image mode: click a face, then the arrow keys (or `[` `]`, or `,` `.`) put one of the
nine version-C duty pictures on it, drag moves it and scroll zooms it, `x` clears the face and `j`
copies the whole framing out as JSON. Each face keeps its own picture and its own framing, held as
offsets in that face's OWN bounding box, so a framing survives every slider on the page,
including tile and gap. The picture is clipped by the face's real outline, drawn at its own
aspect so nothing is cropped by the fit, and the tile colour stays painted underneath it.
The selected face also shows the whole picture dimmed around the outline, which is what is
being cut away.

TWO LIMITS, ONE ENFORCED AND ONE REPORTED

Scroll zoom stops where one source pixel is one DEVICE pixel -- past that the browser is inventing
detail. That limit moves with the wheel, so the width and height sliders can still carry a framing
beyond it; any face that ends up there is outlined in RED and `n` pulls the selected one back. The
wheel itself is deliberately NOT capped: its size is the question this page exists to ask, and the
scale is never adjusted for you, because doing so would silently re-crop a tile you had framed.

The other limit is about the assets rather than the screen. gen_duty_grid re-encodes every tile to
its own `px` before the board is built, so a crop holding fewer of the source's pixels than that is
finer than the build carries. The readout states it and nothing enforces it -- the right answer to
breaking that line is often a bigger source file, not a looser crop.

Those nine files are 2.2 MB each, so they are LINKED rather than inlined -- base64 would have made
this page 27 MB, and shrinking them would mean choosing a crop by looking at a resample, which is
the one thing a framing tool must not ask you to do. The cost is that this page alone among the
pages here is not portable: it reads the tiles from their place in the repository and will show
empty tiles anywhere else. That is the trade, taken deliberately.

The FIRST piece in every row is different in kind: the ACOLYTE, drawn as vector from
population_sets rather than read off disk. It is the mark the board already puts on a duty tile,
so it is the one piece here whose size is something the game has decided -- everything to its
right is a proposal about what might stand there instead, and the comparison only means anything
with the incumbent in the row. Being vector it is exact at any zoom, it needs no generated art,
and it is therefore the only piece that is always present on a fresh clone.

Output goes to generated/, which this folder treats as local debug output: git-ignored, rebuilt
on demand, never committed.
"""
import argparse
import base64
import inspect
import json
import os
import pathlib
import re
import io
import struct
import sys
import urllib.parse
import webbrowser

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "generated" / "wheel_space_check_v3.html"

# Only for the canvas sizes. Importing the module is cheap -- it is load_assembler() and
# build_board() that cost 8.8 MB, and this page calls neither.
sys.path.insert(0, str(ROOT / "ui" / "render"))
import gen_game_view as gv                                          # noqa: E402

# Which duty-tile version the board draws, and where those nine files are, both asked of the
# module that owns the answer. find_tiles() already rejects the _pair/_left/_right sources under
# duty-tiles/sources/, which a glob written here would have quietly picked up.
import gen_duty_grid as dg                                          # noqa: E402

# Pillow, for ONE thing: the source's pixel size. The figures above are read straight out of the
# PNG header because IHDR is four bytes at a fixed offset; WebP is a RIFF container with three
# different ways of stating its size, and hand-rolling that parser to avoid an import the rest of
# this toolchain already requires would be the wrong trade. Missing, the duty pictures drop out
# with a note and the page still builds.
try:
    import numpy as np
    from PIL import Image as _Img
except ModuleNotFoundError:                                         # pragma: no cover
    _Img = None

# The acolyte comes from the module that STORES the shape, not from one that borrows it.
# gen_game_view draws this mark too, in acolyte_mark(), and reaching through it would have been
# one import shorter -- but the outline, the face, the ink, the stroke and the seat colours all
# live here, and gen_game_view is a board renderer that happens to use them. Depending on the
# renderer to describe a shape it does not own is how a second copy of that shape gets made the
# day the renderer changes.
import population_sets as pop                                       # noqa: E402

# The alpha-safe downscale, from the module that already owns it. PIL weights an RGBA resize by
# alpha and divides it back out, which invents light pixels along a part-transparent edge; that
# function resizes the premultiplied RGB and the alpha SEPARATELY and is the one that was
# falsified against the fault. A third copy of it here is how the two would drift apart.
sys.path.insert(0, str(HERE))
import sculpt_metrics as sm                                         # noqa: E402

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

# The vector acolyte that opens every row. 60 px because that is the size the sculpts were being
# judged against when this tray started, and the acolyte is here to be the thing they are judged
# AGAINST -- a row whose incumbent is drawn at some other size compares two changes at once.
# A row's seat is its POSITION, not its name: player 1 is the first seat in population_sets'
# own order, so a re-dealt cast moves the colours here without this file being touched.
ACOLYTE_PX = 60

# NO OUTLINE, and that is a measurement rather than a preference.
#
# population_sets carries HOOD_INK #2b2114 because the seat colours "would vanish without
# something dark around them" against the brightest tile bottom -- true on the board, and it is
# still true on the two pale palettes here. It is NOT true on the one this page opens with.
# Contrast of the ink against each tile colour on this page:
#
#     slate #2b2f38   1.18        cream #efe3c8   12.40
#     slate centre    1.05        parchment       9.72
#
# At 1.18 and 1.05 the outline is not separating anything from the slate -- it is the same
# darkness as the tile. All it contributes there is mass, which on a 60 px figure is most of what
# you see. So it comes off.
#
# What it costs, stated rather than glossed: on PARCHMENT the seats run bone 1.56 and sage 1.94
# against the tile, and those two do get harder to read without it. Set this to "#2b2114" to put
# it back, or to any other colour to try one. Setting it to the tile colour was the other option
# and is not offered, because a figure standing ON the tile would have an outline the same colour
# as the thing behind it -- which is this line with extra steps, minus half a stroke of fill.
ACOLYTE_STROKE = None

# THE TITHE TOKENS, the second tray. Read from the production art rather than from generated/,
# because unlike the sculpts these are committed files that every clone has -- there is nothing
# to render first and nothing to go missing.
#
# Three resources and the cornucopia WILDCARD, where the tithing player chooses which resource to
# take. Piety is deliberately not here: it is not a token on the board at all, it is gained at the
# Clerical duty and lives on its own track.
TOKEN_DIR = ROOT / "ui" / "assets-gothic" / "resources"
TOKEN_SUBJECTS = (("token_wheat", "wheat"),
                  ("token_stone", "stone"),
                  ("token_silver", "silver"),
                  ("token_cornucopia", "wild"))
TOKEN_SIZES = (90, 120, 150)

# One wheel here, not two: the traced contours are a single set. The label is not an aspect the
# way v2's are -- these were traced off a picture rather than built to a ratio -- so nothing
# asserts it against the box.
TRACED = ROOT / "ui" / "assets-gothic" / "metadata" / "duty_grid_shapes.json"
TRACED_LABEL = "traced"
# Row-major, which is the order the shapes are stored in and the order gen_duty_grid names the
# duties. The names are v2's vocabulary on purpose: the template tests `pos === "centre"` for the
# middle tile's own colour, and giving these the same words keeps that code identical.
TRACED_POS = ("north_west", "north", "north_east",
              "west", "centre", "east",
              "south_west", "south", "south_east")

# Slider bounds, in REAL DEVICE pixels. The start is the 1.5 wheel as it actually measures on a
# MacBook at canvas 1600 -- the size every earlier measurement in this folder was taken at, so
# the page opens where the numbers already are rather than somewhere invented.
W_RANGE = (600, 2600)
H_RANGE = (300, 2000)
# THE START IS THE PRODUCTION SIZE, not a number that looked right. gen_duty_grid re-encodes
# every tile to PROD_PX before the board is built, so the wheel size at which a traced tile is
# drawn exactly that big is the one size on this page that already means something -- open there
# and the first thing you see is the board's own scale. Derived from the tiles rather than
# written down, so it follows if either the art or the grid changes.
# Square, because these contours were traced off a square picture: v2 opened at its built 1.500
# and opening at that here would stretch every tile before you had touched anything.

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

# RESOLVED HERE, not just before the write, because the duty-tile paths below are relative to the
# page's own directory. Left where it was, --out would have moved the page and left every tile
# pointing at where the page used to be -- and an <img> that resolves to nothing fails silently.
OUT = pathlib.Path(args.out).expanduser() if args.out else OUT

_NUM = re.compile(r"-?\d+\.?\d*")


def acolyte_svg(seat: str, px: int) -> tuple[str, int, int]:
    """One hooded acolyte `px` tall in `seat`'s colour, as an SVG data URI, plus its drawn size.

    THE VIEWBOX FOLLOWS THE STROKE, and it has to.

    With an outline, the box is hood_box() -- the path's bounds grown by the half of the stroke
    that falls outside them. A viewBox set to the bare bounds would clip that half away on every
    edge and the dome would come out flat, the shoulders square; population_sets documents this
    on hood_box() itself, and an <img> clips exactly the way the <symbol> it warns about does.

    With NO outline there is nothing outside the path, and using the grown box anyway would pad
    the figure with a half-stroke of nothing on all four sides -- so a piece labelled 60 px would
    draw 57, and the tray's whole point is that the label is the true size. Bare bounds then.

    Everything else is read from population_sets: the outline, the face, the stroke weight and
    the seat colour. Nothing about the figure is written down twice.
    """
    if ACOLYTE_STROKE:
        bx, by, bw, bh = pop.hood_box()
        edge = ' stroke="%s" stroke-width="%s" stroke-linejoin="round"' % (
            ACOLYTE_STROKE, pop.HOOD_STROKE)
    else:
        bx, by, bw, bh = -0.5, 0.0, 1.0, pop.HOOD_H
        edge = ""
    w = max(1, round(px * bw / bh))
    f = pop.HOOD_FACE
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="%.4f %.4f %.4f %.4f">'
           '<path d="%s" fill="%s"%s/>'
           '<ellipse cx="0" cy="%s" rx="%s" ry="%s" fill="#000000" opacity="0.22"/></svg>'
           % (w, px, bx, by, bw, bh, pop.hood_path(), pop.SEAT_SWATCH[seat], edge,
              f["cy"], f["rx"], f["ry"]))
    return ("data:image/svg+xml;base64,"
            + base64.b64encode(svg.encode("utf-8")).decode("ascii"), w, px)


def _polygon(cell):
    """The face as a flat list of points, read out of `d_poly`.

    v2 gets that field from build_duty_wheel_v2, which flattens its curves for exactly this
    reason: taking the numbers out of a `d` with curves in it would read the CONTROL points as
    vertices and quietly give a face a different shape than the one on screen. The traced
    contours have no curves -- M, L and Z and nothing else -- so this page hands its `d` straight
    in as `d_poly`, and asserts that it really is curve-free before doing so."""
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
if not TRACED.is_file():
    raise SystemExit("%s is missing -- it carries the nine traced outlines and there is no wheel "
                     "without them." % TRACED)
_traced = json.loads(TRACED.read_text(encoding="utf-8"))
assert len(_traced["shapes"]) == len(TRACED_POS), \
    "%s holds %d shapes, and this page names %d positions" % (TRACED, len(_traced["shapes"]),
                                                              len(TRACED_POS))
_faces = []
for _pos, _d in zip(TRACED_POS, _traced["shapes"]):
    # These contours are POLYLINES -- M, L and Z and nothing else -- so the numbers in `d` are
    # the vertices themselves and `d` doubles as the flattened outline v2 needs a separate
    # `d_poly` for. Asserted rather than assumed: the day somebody smooths these into curves,
    # reading `d` would take the control points for vertices and every face would quietly be a
    # different shape than the one drawn.
    _cmds = set(re.findall(r"[A-Za-z]", _d))
    assert _cmds <= set("MLZmlz"), \
        ("traced face %s carries %s, so its `d` is no longer a polygon and a point-in-polygon "
         "test on it would read curve control points as vertices"
         % (_pos, "".join(sorted(_cmds - set("MLZmlz")))))
    _poly = _polygon({"d_poly": _d, "position": _pos})
    _cx, _cy = _centroid(_poly)
    _faces.append({
        "d": _d, "pos": _pos,
        "frac": abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                        in zip(_poly, _poly[1:] + _poly[:1]))) / 2.0
                / (_traced["box"] * _traced["box"]),
        "cx": _cx / _traced["box"], "cy": _cy / _traced["box"],
        "poly": [[round(x, 1), round(y, 1)] for x, y in _poly],
        "bw": round(max(x for x, _ in _poly) - min(x for x, _ in _poly), 2),
        "bh": round(max(y for _, y in _poly) - min(y for _, y in _poly), 2),
    })
# The traced sheet records one `box` and no height: the contours were lifted off a square
# picture. Square is therefore the built shape, and the height slider stretching away from it is
# reported the same way v2 reports leaving 1.500.
WH[TRACED_LABEL] = {"box": _traced["box"], "box_h": _traced["box"],
                    "aspect": 1.0, "faces": _faces}
KEYS.append(TRACED_LABEL)
_mean_bw = sum(_f["bw"] for _f in _faces) / len(_faces)
print("  traced tiles  %d faces  box %g x %g" % (len(_faces), _traced["box"], _traced["box"]))

for _f in _faces:
    print("    %-11s centre %.3f,%.3f   bbox %6.1f x %6.1f   %4.1f%% of the box"
          % (_f["pos"], _f["cx"], _f["cy"], _f["bw"], _f["bh"], 100 * _f["frac"]))

# The figures, inlined so the page stays a single file. A missing one costs that piece, not the
# page, because this art is git-ignored debug input and a fresh clone has none of it.
fig_dir = pathlib.Path(args.figures).expanduser() if args.figures else FIGURE_DIR
# THE DUTY PICTURES ARE LINKED, NOT INLINED, and that is the one place this page stops being a
# single portable file. The nine version-C tiles are 2.2 MB each: base64 would take this page from
# 400 KB to about 27 MB, and re-encoding them small would mean judging a crop on a resample, which
# is the one thing a framing tool must not do. So they are referenced where they live, at full
# resolution, and the page only works from inside the repository. Said out loud in the header too.
#
# Relative to the PAGE, computed rather than written down: --out can put the page anywhere, and a
# hardcoded ../../../ would point at nothing the moment it did. An <img> that resolves to nothing
# shows no error, so this would fail as a blank tile rather than as a message.
# WHAT THE BOARD ACTUALLY DRAWS THESE AT. gen_duty_grid re-encodes every tile to this before the
# wheel is built -- its own docstring works it out from the wheel's real size: about 1247 device
# px at DPR 2, so one tile of the 3x3 lands near 416, rounded up to 448. Read off the function's
# signature rather than copied, so if that number ever moves this page moves with it instead of
# quietly reporting a limit the build stopped using.
try:
    PROD_PX = int(inspect.signature(dg.duty_grid_svg).parameters["px"].default)
except (AttributeError, KeyError, TypeError, ValueError):            # pragma: no cover
    PROD_PX = 0

# The opening size, derived from PROD_PX now that it exists. PROD_PX is 0 when the signature
# could not be read -- the same guard the line above admits to -- so this falls back to a square
# near the middle of the range rather than opening the page at zero.
if PROD_PX:
    START_W = START_H = int(round(PROD_PX * _traced["box"] / _mean_bw))
else:                                                                # pragma: no cover
    START_W = START_H = 1400
START_W = max(W_RANGE[0], min(W_RANGE[1], START_W))
START_H = max(H_RANGE[0], min(H_RANGE[1], START_H))
print("  opens at %d x %d real px -- %s"
      % (START_W, START_H,
         ("the size at which a tile is drawn at the board's own %d px "
          "(mean tile bbox %.1f units of %g)" % (PROD_PX, _mean_bw, _traced["box"]))
         if PROD_PX else "a fallback: the board's tile size could not be read"))

# ---- the banners ---------------------------------------------------------------------------
# EMBEDDED, unlike the duty pictures, which are linked. Two reasons and both are about what the
# banner is for: it is drawn at a couple of hundred pixels where the source is 2172, so linking
# the full file would ship 21 MB to draw 240 px of it; and the titles are the thing being judged,
# so the page has to be openable anywhere rather than only from inside the repository.
#
# The TITLE IS NOT IN THE ARTWORK. These parchments are blank, and the nine names are set live
# from gen_duty_grid's own list -- rename a duty and this page follows without a new asset.
BANNER_DIR = ROOT / "ui" / "assets-gothic" / "banners"
BANNER_FONT = ROOT / "ui" / "assets" / "fonts" / "PirataOne-Regular.ttf"
BANNER_RASTER = 560          # px wide in the embedded copy; drawn at ~240 box units
# Longest title on the widest clear parchment, which lifts the tightest clearance in the set from
# 4.0 to 5.3 points of banner width. Measured once; see ui/prompts/banners/README.md.
BANNER_ORDER = (1, 5, 8, 3, 9, 4, 7, 6, 2)
# Three sizes in BOX UNITS. The ceiling is what the narrowest tile can take: these contours hold
# their width to the top -- 273 to 295 units across where a title sits -- so 290 is about the
# largest that clears every one of the nine, and the other two step down from it.
BANNER_SIZES = (176, 240, 290)
BANNER_TOP = 0.502           # of the banner's own height: where the parchment's middle sits
BANNER_FS = 29.0 / 64.0      # font size as a fraction of banner height
BANNER_TRACK = 0.025         # letter-spacing, em
BANNER_INK = "#201b17"

BANNERS, banner_notes = [], []
_font_uri = ""
if not BANNER_FONT.is_file():
    banner_notes.append("%s is missing, so the titles would fall back to a serif -- banners left "
                        "out rather than shown in the wrong face" % BANNER_FONT)
elif _Img is None:
    banner_notes.append("Pillow is not installed, so the banner art cannot be downscaled for "
                        "embedding -- banners left out (pip3 install --user Pillow)")
else:
    _font_uri = ("data:font/ttf;base64,"
                 + base64.b64encode(BANNER_FONT.read_bytes()).decode("ascii"))
    for _n in BANNER_ORDER:
        _bp = BANNER_DIR / ("duty_banner_%02d.png" % _n)
        if not _bp.is_file():
            banner_notes.append("%s is missing" % _bp)
            BANNERS = []
            break
        _im = _Img.open(_bp).convert("RGBA")
        # Composited onto nothing and resized as RGBA would let PIL weight the resize by alpha
        # and divide it back out, inventing light pixels along the torn edge. These are already
        # premultiplied-clean, so the straightforward path is to resize and let the alpha ride.
        _k = BANNER_RASTER / _im.width
        _sm = _im.resize((BANNER_RASTER, max(1, round(_im.height * _k))), _Img.LANCZOS)
        _buf = io.BytesIO()
        _sm.save(_buf, "WEBP", quality=86, method=6)
        BANNERS.append("data:image/webp;base64,"
                       + base64.b64encode(_buf.getvalue()).decode("ascii"))
    if BANNERS:
        print("  %d banners embedded at %d px, %.0f KB total, titles set live in %s"
              % (len(BANNERS), BANNER_RASTER,
                 sum(len(b) for b in BANNERS) * 3 / 4 / 1024, BANNER_FONT.stem))
for _n in banner_notes:
    print("  %s" % _n)

TILES, tile_notes = [], []
try:
    found = dg.find_tiles()
except Exception as e:                                              # noqa: BLE001
    found = {}
    tile_notes.append("duty tiles unavailable (%s) -- the page builds without them" % e)
# find_tiles() keys by GRID INDEX, already zero-based -- it does the NN-minus-one itself. Indexing
# DUTY_NAMES with n-1 as well titled every picture with its neighbour's name and wrapped Allocation
# round to "Give Alms", which looked entirely plausible in a dropdown and would have had a crop
# filed against the wrong duty.
if found and _Img is None:
    found = {}
    tile_notes.append("Pillow is not installed, so the pictures' own sizes cannot be read -- "
                      "left out rather than guessed (pip3 install --user Pillow)")
for n in sorted(found):
    p = found[n]
    assert 0 <= n < len(dg.DUTY_NAMES), "grid index %d is outside the nine duties" % n
    # THE SOURCE'S OWN SIZE, carried through to the page, because the picture is laid out at its
    # OWN aspect there. Sized to the face's bounding box instead, a square picture in a 1.75:1
    # box loses 43% of its height to the fit before anyone has chosen anything -- and the crop is
    # invisible, so panning just moves you around inside what is left.
    with _Img.open(p) as im:
        iw, ih = im.size
    TILES.append({"n": n, "title": dg.DUTY_NAMES[n], "w": iw, "h": ih,
                  "src": urllib.parse.quote(
                      os.path.relpath(p, OUT.parent).replace(os.sep, "/"))})
if TILES:
    tile_notes.append("%d duty pictures, version %s, linked from %s"
                      % (len(TILES), dg.VERSION,
                         os.path.relpath(found[sorted(found)[0]].parent, OUT.parent)))
    if PROD_PX:
        # One number, not nine: the ratio is srcDim / (s * PROD_PX) whatever the face's shape.
        tile_notes.append("board draws a tile at %d px from a %d px source, so a crop tighter "
                          "than x%.2f is finer than the build carries"
                          % (PROD_PX, TILES[0]["w"], TILES[0]["w"] / PROD_PX))
    else:
        tile_notes.append("could not read the board's tile size from gen_duty_grid -- the "
                          "production line is left off the readout rather than guessed")
else:
    tile_notes.append("no duty pictures found -- `i` will have nothing to place")

# The tokens, levelled and inlined. They arrive at four diameters -- 1009 to 1138 px -- and a set
# whose discs disagree reads as four unrelated pictures, so they are levelled to the NARROWEST and
# nothing is ever upscaled. Same rule as the sculpt plinths and the concept browser's own card.
#
# Inlined at the sizes the tray uses rather than linked at full size: a 150 px sprite does not
# need a 2 MB file behind it, and re-encoding each one small costs a few KB. That is the opposite
# trade to the duty pictures above, and for the opposite reason -- nobody zooms a tray piece.
TOKEN_ROWS, token_notes = [], []
if _Img is None:
    token_notes.append("Pillow is not installed, so the tokens are left out (pip3 install --user Pillow)")
else:
    srcs = {}
    for name, tag in TOKEN_SUBJECTS:
        f = TOKEN_DIR / ("%s.png" % name)
        if not f.is_file():
            token_notes.append("%-6s missing %s, left out" % (tag, f.name))
            continue
        srcs[name] = sm.crop_to_art(_Img.open(f).convert("RGBA"))
    if srcs:
        target = min(im.width for im in srcs.values())
        for px in sorted(TOKEN_SIZES, reverse=True):
            for name, tag in TOKEN_SUBJECTS:
                im = srcs.get(name)
                if im is None:
                    continue
                k = (target / im.width) * (px / target)
                small = sm.down(im, max(1, round(im.width * k)), max(1, round(im.height * k)),
                                "%s at %d" % (name, px))
                a = np.array(small)
                # Snap the near-solid body. These arrive with no fully opaque pixel at all -- the
                # discs sit at 251-254 -- which lets the tile show through the artwork by a percent
                # or two. Only the body: the part-alpha rim is doing real work.
                a[..., 3] = np.where(a[..., 3] > 240, 255, a[..., 3])
                buf = io.BytesIO()
                _Img.fromarray(a, "RGBA").save(buf, "WEBP", quality=90, method=6, lossless=False)
                raw = buf.getvalue()
                # GROUPED BY SIZE, NOT BY TOKEN, and that is a layout decision with a reason.
                # A row per token is four rows of up to 150 px, and stacked under the figure
                # tray -- itself four rows -- the two collide on any window shorter than about
                # 1300 px. A row per size is three rows of 150, 120 and 90, which is 40% of the
                # height, and it also puts the comparison the right way round: each row is the
                # whole set at one size, which is what you are actually judging.
                row = next((r for r in TOKEN_ROWS if r["tag"] == "%d px" % px), None)
                if row is None:
                    row = {"tag": "%d px" % px, "items": []}
                    TOKEN_ROWS.append(row)
                row["items"].append({"nom": px, "w": small.width, "h": small.height, "fam": "token",
                                     "uri": "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")})
        token_notes.append("%d tokens levelled to %d px, the narrowest disc, then sized to %s"
                           % (len(srcs), target, ", ".join(str(s) for s in TOKEN_SIZES)))

ROWS, fig_notes = [], []
assert len(FIGURE_SUBJECTS) <= len(pop.SEAT_ORDER), (
    "%d tray rows against %d seats in population_sets -- a row past the end of the cast has no "
    "colour to be drawn in" % (len(FIGURE_SUBJECTS), len(pop.SEAT_ORDER)))
for n, (subject, tag) in enumerate(FIGURE_SUBJECTS):
    items = []
    # The incumbent first, and it is built rather than loaded: no file to be missing, so the row
    # exists on a fresh clone even with nothing in generated/.
    seat = pop.SEAT_ORDER[n]
    uri, aw, ah = acolyte_svg(seat, ACOLYTE_PX)
    items.append({"nom": ACOLYTE_PX, "w": aw, "h": ah, "fam": "figure", "uri": uri})
    fig_notes.append("%-9s %3d px  acolyte vector, %-6s %s  %d x %d  %s"
                     % (tag, ACOLYTE_PX, seat, pop.SEAT_SWATCH[seat], aw, ah,
                        "outline %s" % ACOLYTE_STROKE if ACOLYTE_STROKE else "no outline"))
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
        items.append({"nom": px, "w": w, "h": h, "fam": "figure",
                      "uri": "data:image/png;base64," + base64.b64encode(raw).decode("ascii")})
        fig_notes.append("%-9s %3d px  %s  %d × %d%s"
                         % (tag, px, p.name, w, h,
                            "" if h == px else "  (%d%% of nominal)" % round(100 * h / px)))
    if items:
        ROWS.append({"tag": tag, "items": items})
# Every row now carries its acolyte whatever else is missing, so an empty ROWS means the subject
# table itself is empty -- which the old `or fig_notes` would have let through silently.
assert len(ROWS) == len(FIGURE_SUBJECTS), (
    "%d rows built from %d subjects; every row should hold at least its acolyte"
    % (len(ROWS), len(FIGURE_SUBJECTS)))

page = ((HERE / "wheel_space_check_v3.html.tmpl").read_text(encoding="utf-8")
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
        .replace("__TOKENS__", json.dumps(TOKEN_ROWS))
        .replace("__TILES__", json.dumps(TILES))
        .replace("__PRODPX__", json.dumps(PROD_PX))
        .replace("__START__", json.dumps([START_W, START_H]))
        .replace("__BANNERS__", json.dumps(BANNERS))
        .replace("__BANNERFONT__", json.dumps(_font_uri))
        .replace("__BANNERSIZES__", json.dumps(list(BANNER_SIZES)))
        .replace("__BANNERTOP__", json.dumps(BANNER_TOP))
        .replace("__BANNERFS__", json.dumps(BANNER_FS))
        .replace("__BANNERTRACK__", json.dumps(BANNER_TRACK))
        .replace("__BANNERINK__", json.dumps(BANNER_INK))
        .replace("__DUTYNAMES__", json.dumps(list(getattr(dg, "DUTY_NAMES", [])))))
left = re.findall(r"__[A-Z_]+__", page)
assert not left, "placeholders left unsubstituted: %s" % sorted(set(left))

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
for note in tile_notes:
    print("  %s" % note)
for note in token_notes:
    print("  %s" % note)
if args.open:
    webbrowser.open(OUT.resolve().as_uri())
